import Foundation

public struct DepthMap {
    public var width: Int, height: Int
    public var values: [Float]            // depth_z in meter, rij-hoofdvolgorde; 0/NaN/inf = ongeldig
    public init(width: Int, height: Int, values: [Float]) { precondition(values.count == width * height); self.width = width; self.height = height; self.values = values }
}

public struct ViewInput {
    public var frameId: String
    public var intrinsics: Intrinsics
    public var pose: Pose
    public var trackingNormal: Bool
    public var depth: DepthMap?
    public init(frameId: String, intrinsics: Intrinsics, pose: Pose, trackingNormal: Bool, depth: DepthMap?) {
        self.frameId = frameId; self.intrinsics = intrinsics; self.pose = pose; self.trackingNormal = trackingNormal; self.depth = depth
    }
}

public enum Level: String, Codable { case A, B, C }

public struct LevelResult {
    public var level: Level
    public var scaleMethod: String
    public var flags: [QualityFlag] = []
    public var width: Double?, height: Double?
    public var sigmaW: Double?, sigmaH: Double?, sigmaArea: Double?
    public var cornersWorld: [Vec3]?
    public var planeN: Vec3?, planeD: Double?
    public var viewIds: [String] = []
    public var ok: Bool { width != nil && !hasBlocking(flags) }
    public init(level: Level, scaleMethod: String, viewIds: [String] = []) { self.level = level; self.scaleMethod = scaleMethod; self.viewIds = viewIds }
}

private struct DepthSample { var pixel: Pixel; var z: Double }

private func depthSamples(_ view: ViewInput) -> [DepthSample] {
    guard let d = view.depth else { return [] }
    let sx = Double(view.intrinsics.width) / Double(d.width), sy = Double(view.intrinsics.height) / Double(d.height)
    var out: [DepthSample] = []
    out.reserveCapacity(d.values.count)
    for i in 0..<d.height { for j in 0..<d.width {
        let z = Double(d.values[i * d.width + j])
        out.append(DepthSample(pixel: Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy), z: z))
    } }
    return out
}

private func localDepth(_ view: ViewInput, _ p: Pixel) -> Double? {
    guard let d = view.depth else { return nil }
    let sx = Double(view.intrinsics.width) / Double(d.width), sy = Double(view.intrinsics.height) / Double(d.height)
    let j = Int(p.u / sx), i = Int(p.v / sy)
    var vals: [Double] = []
    for ii in max(i - 1, 0)...min(i + 1, d.height - 1) { for jj in max(j - 1, 0)...min(j + 1, d.width - 1) {
        let z = Double(d.values[ii * d.width + jj]); if z.isFinite && z > 0 { vals.append(z) }
    } }
    guard vals.count >= 3 else { return nil }
    vals.sort()
    return vals[vals.count / 2]
}

/// Vlak van de gevel RONDOM het kozijn (annulus); nooit uit de hoekpixels of het glas.
public func fitFacadePlane(_ view: ViewInput, corners: [Pixel], cfg: Config, seed: UInt64) -> (PlaneFit?, [QualityFlag]) {
    let outer = scalePolygon(corners, cfg.annulusOuterScale), inner = scalePolygon(corners, cfg.annulusInnerScale)
    var ring = 0, valid: [Vec3] = [], beyond = 0
    for s in depthSamples(view) where inConvexPolygon(s.pixel, outer) && !inConvexPolygon(s.pixel, inner) {
        ring += 1
        guard s.z.isFinite, s.z > 0 else { continue }
        if s.z > cfg.depthMaxRangeM { beyond += 1; continue }
        if s.z < cfg.depthMinRangeM { continue }
        valid.append(unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: s.pixel, depthZ: s.z))
    }
    if ring > 0 && Double(beyond) / Double(ring) >= 0.3 { return (nil, [Flags.make("DEPTH_RANGE_EXCEEDED")]) }
    let coverage = ring > 0 ? Double(valid.count) / Double(ring) : 0
    if valid.count < cfg.annulusMinPoints || coverage < cfg.annulusMinValidFraction {
        return (nil, [Flags.make("DEPTH_COVERAGE_LOW", "\(valid.count) punten, dekking \(coverage)")])
    }
    guard var fit = fitPlaneRansac(valid, threshold: cfg.planeRansacThresholdM, iterations: cfg.planeRansacIterations, seed: seed),
          fit.inlierRatio >= cfg.planeMinInlierRatio else { return (nil, [Flags.make("MIXED_FACADE_DEPTH")]) }
    if fit.rmsM > cfg.planeMaxRmsM { return (fit, [Flags.make("PLANE_NOISY", "rms \(fit.rmsM) m")]) }
    if fit.n.dot(view.pose.t - fit.centroid) < 0 { fit.n = fit.n * -1; fit.d = -fit.d }
    var flags: [QualityFlag] = []
    if abs(fit.n.dot(worldUp)) > 0.3 { flags.append(Flags.make("FACADE_NOT_VERTICAL")) }
    return (fit, flags)
}

/// Niveau A voor een standpunt: hoekstralen snijden het aangepaste gevelvlak (zie docs/measurement_levels.md).
public func measureDepthView(_ view: ViewInput, corners: [Pixel], cfg: Config = Config(), seed: UInt64 = 0, obstruction: Bool = false) -> LevelResult {
    var res = LevelResult(level: .A, scaleMethod: "LIDAR_DEPTH_PLANE", viewIds: [view.frameId])
    if !view.trackingNormal { res.flags.append(Flags.make("TRACKING_LOST")) }
    if view.depth == nil { res.flags.append(Flags.make("NO_DEPTH")) }
    let imgArea = Double(view.intrinsics.width * view.intrinsics.height)
    if !isSimpleConvexQuad(corners, imageArea: imgArea) { res.flags.append(Flags.make("CORNER_ORDER_INVALID")) }
    else if corners.contains(where: { $0.u < 0 || $0.v < 0 || $0.u > Double(view.intrinsics.width) || $0.v > Double(view.intrinsics.height) }) {
        res.flags.append(Flags.make("CORNER_OUTSIDE_IMAGE"))
    }
    if obstruction { res.flags.append(Flags.make("OBSTRUCTION_REPORTED")) }
    if hasBlocking(res.flags) { return res }

    let (fitOpt, pf) = fitFacadePlane(view, corners: corners, cfg: cfg, seed: seed)
    res.flags += pf
    guard let fit = fitOpt, !hasBlocking(res.flags) else { return res }

    let rays = raysWorld(pose: view.pose, intr: view.intrinsics, pixels: corners)
    var C: [Vec3] = [], cosMin = Double.infinity
    for dir in rays.dirs {
        guard let h = intersectRayPlane(origin: rays.origin, dir: dir, n: fit.n, d: fit.d) else { res.flags.append(Flags.make("CORNERS_NOT_ON_PLANE")); return res }
        C.append(h.point); cosMin = min(cosMin, h.cosIncidence)
    }
    if cosMin < cfg.minIncidenceCos { res.flags.append(Flags.make("OBLIQUE_ANGLE", "min |cos|=\(cosMin)")); return res }
    let bad = rectangularityProblems(C, edgeRatioTol: cfg.rectEdgeRatioTol, angleTolDeg: cfg.rectAngleTolDeg)
    if !bad.isEmpty { res.flags.append(Flags.make("WRONG_CORNER_SELECTION", bad.joined(separator: "; "))); return res }
    let (w, h) = dimsFromCorners(C, up: worldUp)
    if !(cfg.minDimM...cfg.maxDimM).contains(w) || !(cfg.minDimM...cfg.maxDimM).contains(h) {
        res.flags.append(Flags.make("DIMENSION_OUT_OF_RANGE", "\(w) x \(h) m")); return res
    }
    // hoekdiepte-controle: grof (>=3 hoeken) blokkeert, licht is adviserend
    let zAxis = Vec3(view.pose.r[0].z, view.pose.r[1].z, view.pose.r[2].z)
    var mism = 0, gross = 0
    for (k, c) in C.enumerated() {
        if let zl = localDepth(view, corners[k]) {
            let dz = abs(zl - (c - rays.origin).dot(zAxis))
            if dz > cfg.cornerDepthTolM { mism += 1 }
            if dz > cfg.cornerDepthBlockM { gross += 1 }
        }
    }
    if gross >= 3 { res.flags.append(Flags.make("MIXED_FACADE_DEPTH", "hoekdiepte wijkt sterk af van het vlak")); return res }
    if mism > 0 { res.flags.append(Flags.make("CORNER_DEPTH_MISMATCH", "\(mism) hoek(en)")) }
    // glas (adviserend)
    let glass = scalePolygon(corners, cfg.glassInnerScale)
    var nIn = 0, nValid = 0, nBeyond = 0
    for s in depthSamples(view) where inConvexPolygon(s.pixel, glass) {
        nIn += 1
        if s.z.isFinite && s.z > 0 {
            nValid += 1
            let p = unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: s.pixel, depthZ: s.z)
            if abs(p.dot(fit.n) - fit.d) > cfg.glassBeyondPlaneM { nBeyond += 1 }
        }
    }
    if nIn > 0 {
        let fv = Double(nValid) / Double(nIn), fb = nValid > 0 ? Double(nBeyond) / Double(nValid) : 0
        if fv < cfg.glassMinValidFraction || fb > cfg.glassMaxBeyondFraction { res.flags.append(Flags.make("GLASS_DEPTH_UNRELIABLE")) }
    }
    // onzekerheid: Monte Carlo met eigen PRNG (niet bit-exact gelijk aan Python)
    var rng = SplitMix64(seed: seed &+ 7)
    let nEff = Double(min(fit.nInliers, cfg.planeEffectiveSamplesCap))
    let sigDepth = max(fit.rmsM, cfg.depthNoiseFloorM)
    let sigD = sigDepth / nEff.squareRoot(), sigTilt = sigDepth / (max(fit.spreadM, 0.05) * nEff.squareRoot())
    var ws: [Double] = [], hs: [Double] = []
    for _ in 0..<cfg.mcSamples {
        let cp = corners.map { Pixel($0.u + rng.gaussian() * cfg.cornerPixelSigmaPx, $0.v + rng.gaussian() * cfg.cornerPixelSigmaPx) }
        var dl = Vec3(rng.gaussian() * sigTilt, rng.gaussian() * sigTilt, rng.gaussian() * sigTilt)
        dl = dl - fit.n * dl.dot(fit.n)
        let n2 = (fit.n + dl).normalized, d2 = n2.dot(fit.centroid) + rng.gaussian() * sigD
        let r2 = raysWorld(pose: view.pose, intr: view.intrinsics, pixels: cp)
        let hits = r2.dirs.compactMap { intersectRayPlane(origin: r2.origin, dir: $0, n: n2, d: d2)?.point }
        if hits.count == 4 { let (a, b) = dimsFromCorners(hits, up: worldUp); ws.append(a); hs.append(b) }
    }
    func sd(_ v: [Double]) -> Double { guard v.count > 1 else { return 0 }; let m = v.reduce(0, +) / Double(v.count); return (v.reduce(0) { $0 + pow($1 - m, 2) } / Double(v.count)).squareRoot() }
    res.width = w; res.height = h
    res.sigmaW = sd(ws); res.sigmaH = sd(hs); res.sigmaArea = sd(zip(ws, hs).map { $0 * $1 })
    res.cornersWorld = C; res.planeN = fit.n; res.planeD = fit.d
    return res
}

/// Fusie van standpunten: inverse-variantie; inconsistent -> geen waarde (UNKNOWN).
public func fuse(_ results: [LevelResult], cfg: Config = Config()) -> LevelResult {
    let good = results.filter { $0.ok }
    var out = LevelResult(level: .A, scaleMethod: good.isEmpty ? "NONE" : "LIDAR_DEPTH_PLANE", viewIds: good.flatMap { $0.viewIds })
    out.flags = results.filter { !$0.ok }.flatMap { $0.flags }
    if good.isEmpty { return out }
    for a in 0..<good.count { for b in (a + 1)..<max(good.count, a + 1) where b < good.count {
        for (va, vb, sa, sb) in [(good[a].width!, good[b].width!, good[a].sigmaW!, good[b].sigmaW!), (good[a].height!, good[b].height!, good[a].sigmaH!, good[b].sigmaH!)] {
            let lim = cfg.consistencyK * (pow(max(sa, 1e-4), 2) + pow(max(sb, 1e-4), 2)).squareRoot()
            if abs(va - vb) > lim { out.flags.append(Flags.make("VIEWS_INCONSISTENT", "\(abs(va - vb)) > \(lim) m")) }
        }
    } }
    if hasBlocking(out.flags) { return out }
    out.flags += good.flatMap { $0.flags.filter { $0.severity == .ADVISORY } }
    func wmean(_ vals: [Double], _ sig: [Double]) -> (Double, Double) {
        let wt = sig.map { 1 / pow(max($0, 1e-4), 2) }
        return (zip(wt, vals).reduce(0) { $0 + $1.0 * $1.1 } / wt.reduce(0, +), 1 / wt.reduce(0, +).squareRoot())
    }
    let (w, sw) = wmean(good.map { $0.width! }, good.map { $0.sigmaW! })
    let (h, sh) = wmean(good.map { $0.height! }, good.map { $0.sigmaH! })
    out.width = w; out.height = h; out.sigmaW = sw; out.sigmaH = sh; out.sigmaArea = (pow(sw * h, 2) + pow(sh * w, 2)).squareRoot()
    let best = good.min { ($0.sigmaArea ?? .infinity) < ($1.sigmaArea ?? .infinity) }!
    out.cornersWorld = best.cornersWorld; out.planeN = best.planeN; out.planeD = best.planeD
    return out
}
