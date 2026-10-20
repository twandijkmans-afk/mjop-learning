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
    /// Ondersteunende dieptekaders uit de korte buffer vlak voor de foto (eigen pose, tracking en diepte). Alleen onafhankelijke kaders worden gebruikt.
    public var supports: [ViewInput] = []
    public init(frameId: String, intrinsics: Intrinsics, pose: Pose, trackingNormal: Bool, depth: DepthMap?, supports: [ViewInput] = []) {
        self.frameId = frameId; self.intrinsics = intrinsics; self.pose = pose; self.trackingNormal = trackingNormal; self.depth = depth; self.supports = supports
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
    public var independentFrames = 1
    public var scaleEvidence: [String: Any] = [:]
    public var diag: [String: Any] = [:]                 // meetdiagnose (numeriek, exporteerbaar)
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

func localDepth(_ view: ViewInput, _ p: Pixel) -> Double? {
    guard let d = view.depth, d.width > 0, d.height > 0, p.u.isFinite, p.v.isFinite else { return nil }
    let sx = Double(view.intrinsics.width) / Double(d.width), sy = Double(view.intrinsics.height) / Double(d.height)
    let j = min(max(Int(p.u / sx), 0), d.width - 1), i = min(max(Int(p.v / sy), 0), d.height - 1)   // geklemd: nooit buiten de kaart
    var vals: [Double] = []
    for ii in max(i - 1, 0)...min(i + 1, d.height - 1) {
        for jj in max(j - 1, 0)...min(j + 1, d.width - 1) {
            let z = Double(d.values[ii * d.width + jj])
            if z.isFinite && z > 0 { vals.append(z) }
        }
    }
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

func angleBetweenDeg(_ a: Vec3, _ b: Vec3) -> Double {
    acos(max(-1, min(1, abs(a.dot(b)) / (a.norm * b.norm)))) * 180 / Double.pi
}

private func flagList(_ flags: [QualityFlag]) -> [[String: Any]] {
    flags.map { ["code": $0.code, "severity": $0.severity.rawValue, "detail": $0.detail ?? NSNull()] as [String: Any] }
}

private let hintAdvisories: Set<String> = ["FRAME_OFFSET_FROM_CORNER_DEPTH", "CORNER_DEPTH_MISMATCH", "QUAD_LARGER_THAN_OPENING", "QUAD_INSIDE_OPENING", "GLASS_DEPTH_UNRELIABLE", "LIMITED_SIDE_COVERAGE"]

private func finishDiag(_ res: inout LevelResult, _ flags: [QualityFlag]) {
    res.diag["flags"] = flagList(flags)
    res.diag["blocking"] = flags.filter { $0.severity == .BLOCKING }.map { $0.code }
    var hints: [String] = []
    for f in flags where (f.severity == .BLOCKING || hintAdvisories.contains(f.code)) && !hints.contains(f.instruction_nl) { hints.append(f.instruction_nl) }
    res.diag["hints_nl"] = hints
    res.diag["ok"] = res.width != nil && !hasBlocking(flags)
}

/// Analyse van de punten van EEN frame (consistentiecontrole): vlak + kozijnoffset + maat op dezelfde capture-stralen.
private func analyzeSubset(capture: ViewInput, _ pts: PointSet, corners: [Pixel], cfg: Config, seed: UInt64, quadDiagPx: Double?) -> [String: Any] {
    var out: [String: Any] = ["ok": false]
    if pts.X.count < cfg.minPlanePoints { out["why"] = "te weinig punten"; return out }
    let an = analyzePoints(capture: capture, pts, cfg: cfg, seed: seed, quadDiagPx: quadDiagPx)
    guard let fac = an.facade, !hasBlocking(an.flags) else { out["why"] = an.flags.map { $0.code }.joined(separator: ","); return out }
    guard let frm = an.frame, ["FLUSH", "RECESSED", "PROTRUDING"].contains(frm.mode), let off = frm.offset else {
        out["why"] = "kozijnoffset " + (an.frame?.mode ?? "?"); return out
    }
    guard let g = planeGeometry(capture, corners: corners, n: fac.n, d: fac.d + off) else { out["why"] = "hoekstraal"; return out }
    let (w, h) = dimsFromCorners(g.points, up: worldUp)
    out["ok"] = true; out["width_m"] = w; out["height_m"] = h; out["offset_m"] = off
    out["inlier_ratio"] = rd(an.inlierRatio, 1000); out["plane_offset"] = fac.d + off
    out["normal"] = [fac.n.x, fac.n.y, fac.n.z]
    return out
}

/// Niveau A voor een foto, optioneel met ondersteunende dieptekaders (`view.supports`, uit de korte buffer vlak voor de foto).
/// Geeft altijd diagnostiek in `result.diag`; bij een blokkerende vlag is er GEEN metrische waarde.
public func measureDepthView(_ view: ViewInput, corners: [Pixel], cfg: Config = Config(), seed: UInt64 = 0, obstruction: Bool = false) -> LevelResult {
    var res = LevelResult(level: .A, scaleMethod: "LIDAR_DEPTH_PLANE", viewIds: [view.frameId])
    res.diag = ["algorithm": "LIDAR_PLANE_V2", "frame_id": view.frameId, "tracking_capture": view.trackingNormal ? "NORMAL" : "LIMITED"]
    if !view.trackingNormal { res.flags.append(Flags.make("TRACKING_LOST")) }
    if view.depth == nil { res.flags.append(Flags.make("NO_DEPTH")) }
    let imgArea = Double(view.intrinsics.width * view.intrinsics.height)
    if !isSimpleConvexQuad(corners, imageArea: imgArea) { res.flags.append(Flags.make("CORNER_ORDER_INVALID")) }
    else if corners.contains(where: { $0.u < 0 || $0.v < 0 || $0.u > Double(view.intrinsics.width) || $0.v > Double(view.intrinsics.height) }) {
        res.flags.append(Flags.make("CORNER_OUTSIDE_IMAGE"))
    }
    if obstruction { res.flags.append(Flags.make("OBSTRUCTION_REPORTED")) }
    if hasBlocking(res.flags) { finishDiag(&res, res.flags); return res }
    guard let dm = view.depth else { finishDiag(&res, res.flags); return res }

    let (frames, rejected) = selectSupportFrames(capture: view, supports: view.supports, cfg: cfg)
    let regions = Regions(quad: corners, cfg: cfg)
    // dekking in het capture-frame (alle pixels, ook ongeldige)
    let sx = Double(view.intrinsics.width) / Double(dm.width), sy = Double(view.intrinsics.height) / Double(dm.height)
    var ringTotal = 0, ringValid = 0, beyond = 0, glassTotal = 0, glassValid = 0
    var glassPix: [(Pixel, Double)] = []
    for i in 0..<dm.height {
        for j in 0..<dm.width {
            let p = Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy)
            let (kind, _) = regions.classify(p)
            if kind == 0 { continue }
            let z = Double(dm.values[i * dm.width + j])
            let valid = z.isFinite && z > 0
            if kind == 1 {
                ringTotal += 1
                if valid && z >= cfg.depthMinRangeM && z <= cfg.depthMaxRangeM { ringValid += 1 }
                if valid && z > cfg.depthMaxRangeM { beyond += 1 }
            } else if kind == 3 {
                glassTotal += 1
                if valid { glassValid += 1; glassPix.append((p, z)) }
            }
        }
    }
    let coverage = ringTotal > 0 ? Double(ringValid) / Double(ringTotal) : 0
    var baseline = 0.0
    for a in frames { for b in frames { baseline = max(baseline, (a.pose.t - b.pose.t).norm) } }
    res.diag["frames_total"] = 1 + view.supports.count
    res.diag["frames_independent_candidates"] = frames.count
    res.diag["frames_rejected"] = rejected.map { ["frame": $0.0, "why": $0.1] }
    res.diag["ring_pixels"] = ringTotal; res.diag["ring_valid"] = ringValid; res.diag["ring_coverage"] = rd(coverage); res.diag["baseline_m"] = rd(baseline)
    if ringTotal > 0 && Double(beyond) / Double(ringTotal) >= 0.3 {
        res.flags.append(Flags.make("DEPTH_RANGE_EXCEEDED", "\(beyond) van \(ringTotal) ringpixels voorbij \(cfg.depthMaxRangeM) m"))
    } else if ringValid < cfg.annulusMinPoints || coverage < 0.25 {
        res.flags.append(Flags.make("DEPTH_COVERAGE_LOW", String(format: "%d geldige ringpunten, dekking %.2f", ringValid, coverage)))
    }
    if hasBlocking(res.flags) { finishDiag(&res, res.flags); return res }

    // punten van alle onafhankelijke frames in het capture-beeldgebied
    var perFrame: [PointSet] = []
    var all = PointSet()
    for f in frames {
        let ps = collectPoints(frame: f, capture: view, isCapture: f.frameId == view.frameId && f.pose.t == view.pose.t, regions: regions, cfg: cfg)
        perFrame.append(ps); all.append(ps)
    }
    res.diag["points_valid_total"] = all.X.count
    res.diag["points_ring"] = all.kind.filter { $0 == 1 }.count
    res.diag["points_band"] = all.kind.filter { $0 == 2 }.count
    res.diag["points_glass"] = all.kind.filter { $0 == 3 }.count
    let qDiag = ((corners[2].u - corners[0].u) * (corners[2].u - corners[0].u) + (corners[2].v - corners[0].v) * (corners[2].v - corners[0].v)).squareRoot()
    let an = analyzePoints(capture: view, all, cfg: cfg, seed: seed, quadDiagPx: qDiag)
    res.flags += an.flags
    res.diag["planes"] = an.planes; res.diag["stats"] = an.stats; res.diag["range_median_m"] = rd(an.zMed); res.diag["facade_assessment"] = an.assessment
    if hasBlocking(res.flags) { finishDiag(&res, res.flags); return res }
    guard let fac = an.facade, let frm = an.frame else { finishDiag(&res, res.flags); return res }
    let n = fac.n, dWall = fac.d, zMed = an.zMed, thr = an.thr, sig = sigmaAt(zMed, cfg)
    var perSideDiag: [String: Any] = [:]
    for name in sideNames { if let e = frm.perSide[name] { perSideDiag[name] = ["offset_m": rdOpt(e.offset), "support": e.support] as [String: Any] } }
    var fpd: [String: Any] = ["mode": frm.mode, "offset_m": rdOpt(frm.offset), "per_side": perSideDiag, "group": frm.group, "ledge_sides": frm.ledge]
    res.diag["frame_plane"] = fpd

    let oCam = view.pose.t
    let zAxis = Vec3(view.pose.r[0].z, view.pose.r[1].z, view.pose.r[2].z)
    let vals = corners.map { cornerValues(view, $0) }
    var offset: Double = frm.offset ?? 0
    var mode = frm.mode
    if !["FLUSH", "RECESSED", "PROTRUDING"].contains(mode) {
        // terugval: terugligging uit de clusters van hoekdieptes (zwakker bewijs; altijd adviserend gemeld)
        var sAll: [Double] = []
        for (c, v) in zip(corners, vals) {
            for z in v {
                let X = unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: c, depthZ: z)
                let s = X.dot(n) - dWall
                if abs(s) <= cfg.frameSearchM { sAll.append(s) }
            }
        }
        var cl = depthClusters(sAll, thr: thr)
        let topCount = cl.map { $0.1 }.max() ?? 0
        cl = cl.filter { Double($0.1) >= max(8.0, 0.2 * Double(topCount)) }
        res.diag["corner_offset_clusters_m"] = cl.map { [rd($0.0), $0.1] as [Any] }
        let flush = max(0.015, cfg.flushTolK * sig)
        mode = frm.mode
        if cl.count == 1 && abs(cl[0].0) <= flush && cl[0].1 >= 20 { offset = 0; mode = "FLUSH_FROM_CORNERS" }
        else if cl.count >= 2 && cl[0].1 >= 12, let deep = cl.min(by: { $0.0 < $1.0 }), abs(deep.0) > flush, deep.1 >= 12 {
            // NIET gebruikt als maat: bij diepe dagkanten pakt dit cluster de dagkant i.p.v. het kozijn (gesimuleerd 3-9 % fout). Alleen indicatief.
            res.diag["indicative_corner_offset_m"] = ["offset_m": rd(deep.0), "note": "ALLEEN indicatief; terugligging niet betrouwbaar bepaald"] as [String: Any]
        }
        if mode == "FLUSH_FROM_CORNERS" {
            res.flags.append(Flags.make("FRAME_OFFSET_FROM_CORNER_DEPTH", String(format: "%.1f cm", offset * 100) + " (\(mode))"))
        } else {
            if let g0 = planeGeometry(view, corners: corners, n: n, d: dWall) {
                let (w0, h0) = dimsFromCorners(g0.points, up: worldUp)
                res.diag["indicative_if_flush_m"] = ["width": rd(w0, 1000), "height": rd(h0, 1000), "note": "ALLEEN indicatief; geen meting"] as [String: Any]
            }
            res.flags.append(Flags.make(frm.mode == "INCONSISTENT" ? "FRAME_PLANE_INCONSISTENT" : "FRAME_PLANE_UNDETERMINED", "modus \(frm.mode)"))
            finishDiag(&res, res.flags); return res
        }
    }
    let dPlane = dWall + offset
    fpd["final_mode"] = mode; fpd["final_offset_m"] = rd(offset); fpd["recess_cm"] = rd(-offset * 100, 10)
    res.diag["frame_plane"] = fpd
    guard let geo = planeGeometry(view, corners: corners, n: n, d: dPlane) else {
        res.flags.append(Flags.make("CORNERS_NOT_ON_PLANE")); finishDiag(&res, res.flags); return res
    }
    let C = geo.points
    if geo.cosMin < cfg.minIncidenceCos {
        res.flags.append(Flags.make("OBLIQUE_ANGLE", String(format: "min |cos|=%.2f", geo.cosMin))); finishDiag(&res, res.flags); return res
    }
    // hoekcontrole (onafhankelijk): ligt een deel van de dieptes rond elke hoek op het gekozen vlak?
    let tolC = cfg.cornerTolK * sig + 0.02
    var dev: [Any] = [], share: [Any] = []
    var contra = 0, checked = 0
    for k in 0..<4 {
        let v = vals[k]
        if v.count < 3 { dev.append(NSNull()); share.append(NSNull()); continue }
        let exp = (C[k] - oCam).dot(zAxis)
        let dd = v.map { $0 - exp }
        let near = dd.filter { abs($0) <= tolC }.count
        let nearest = dd.min(by: { abs($0) < abs($1) })!
        dev.append(rd(nearest)); share.append(rd(Double(near) / Double(dd.count), 1000))
        checked += 1
        if near == 0 { contra += 1 }
    }
    res.diag["corner_deviation_m"] = dev; res.diag["corner_share_on_plane"] = share; res.diag["corner_tolerance_m"] = rd(tolC)
    res.diag["corners_contradicting"] = contra; res.diag["corners_checked"] = checked
    if contra >= cfg.cornersContradictBlock {
        res.flags.append(Flags.make("CORNERS_OFF_PLANE", String(format: "%d hoeken: geen enkele diepte binnen %.1f cm van het gekozen vlak", contra, tolC * 100)))
        finishDiag(&res, res.flags); return res
    }
    if contra > 0 { res.flags.append(Flags.make("CORNER_DEPTH_MISMATCH", "\(contra) hoek(en)")) }
    let bad = rectangularityProblems(C, edgeRatioTol: cfg.rectEdgeRatioTol, angleTolDeg: cfg.rectAngleTolDeg)
    if !bad.isEmpty { res.flags.append(Flags.make("WRONG_CORNER_SELECTION", bad.joined(separator: "; "))); finishDiag(&res, res.flags); return res }
    let (w, h) = dimsFromCorners(C, up: worldUp)
    if !(cfg.minDimM...cfg.maxDimM).contains(w) || !(cfg.minDimM...cfg.maxDimM).contains(h) {
        res.flags.append(Flags.make("DIMENSION_OUT_OF_RANGE", String(format: "%.3f x %.3f m", w, h))); finishDiag(&res, res.flags); return res
    }
    // ligt het kader om de buitenrand van het kozijn?
    let qe = quadExtent(view, corners: corners, n: n, dPlane: dPlane, zMed: zMed, cfg: cfg)
    res.diag["quad_extent"] = ["sides": qe.sides, "sides_deeper_step_inside": qe.larger, "sides_closer_step_outside": qe.inside] as [String: Any]
    if qe.larger >= 3 { res.flags.append(Flags.make("QUAD_LARGER_THAN_OPENING", "\(qe.larger) zijden")) }
    if qe.inside >= 3 { res.flags.append(Flags.make("QUAD_INSIDE_OPENING", "\(qe.inside) zijden")) }
    // glas (adviserend; de maat gebruikt het glas nooit)
    if glassTotal > 0 {
        let fv = Double(glassValid) / Double(glassTotal)
        var fb = 0.0
        if !glassPix.isEmpty {
            var nb = 0
            for (p, z) in glassPix { if abs(unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: p, depthZ: z).dot(n) - dPlane) > cfg.glassBeyondPlaneM { nb += 1 } }
            fb = Double(nb) / Double(glassPix.count)
        }
        res.diag["glass"] = ["valid_fraction": rd(fv, 1000), "beyond_fraction": rd(fb, 1000)] as [String: Any]
        if fv < cfg.glassMinValidFraction || fb > cfg.glassMaxBeyondFraction {
            res.flags.append(Flags.make("GLASS_DEPTH_UNRELIABLE", String(format: "geldig %.2f, buiten vlak %.2f", fv, fb)))
        }
    }
    // onafhankelijke consistentie tussen frames
    var agree = 1
    if frames.count > 1 {
        var rows: [[String: Any]] = []
        var usable = 0, inconsistent = false
        for (fi, f) in frames.enumerated() {
            var sub = analyzeSubset(capture: view, perFrame[fi], corners: corners, cfg: cfg, seed: seed &+ UInt64(101 * (fi + 1)), quadDiagPx: qDiag)
            sub["frame"] = f.frameId
            if (sub["ok"] as? Bool) == true {
                usable += 1
                let nn = sub["normal"] as! [Double]
                let ndeg = angleBetweenDeg(Vec3(nn[0], nn[1], nn[2]), n)
                let sw = sub["width_m"] as! Double, sh = sub["height_m"] as! Double
                let okAgree = abs(sw - w) <= cfg.frameTolRel * w + cfg.frameTolAbsM && abs(sh - h) <= cfg.frameTolRel * h + cfg.frameTolAbsM && ndeg <= cfg.frameNormalDeg
                sub["normal_deg"] = rd(ndeg, 1000); sub["agrees"] = okAgree
                if !okAgree { inconsistent = true }
            }
            rows.append(sub)
        }
        res.diag["frames_usable"] = usable
        res.diag["per_frame"] = rows
        if inconsistent {
            let t = rows.filter { ($0["ok"] as? Bool) == true }.map { r -> String in
                let fid = r["frame"] as? String ?? "?"
                return fid + ": " + String(format: "%.3fx%.3f", r["width_m"] as? Double ?? 0, r["height_m"] as? Double ?? 0)
            }
            res.flags.append(Flags.make("FRAMES_INCONSISTENT", t.joined(separator: "; ")))
            finishDiag(&res, res.flags); return res
        }
        // onafhankelijkheid: kaders met alleen rotatie (zelfde positie) leveren extra punten maar geen ander standpunt; alleen verschillende
        // standpunten (>= minBaselineM) tellen als onafhankelijke metingen (LIDAR_DEPTH_MULTI_FRAME en MEASURED).
        var vps: [Vec3] = []
        for (fi, f) in frames.enumerated() {
            let c = f.pose.t
            var tr = 0.0
            for i in 0..<3 { tr += f.pose.r[i].dot(view.pose.r[i]) }
            rows[fi]["baseline_to_capture_m"] = rd((c - view.pose.t).norm)
            rows[fi]["rotation_to_capture_deg"] = rd(acos(max(-1, min(1, (tr - 1) / 2))) * 180 / Double.pi, 1000)
            if (rows[fi]["ok"] as? Bool) == true && vps.allSatisfy({ (c - $0).norm >= cfg.minBaselineM }) { vps.append(c) }
        }
        res.diag["per_frame"] = rows
        res.diag["independence"] = ["criteria": ["min_baseline_m": cfg.minBaselineM, "min_rotation_deg": cfg.minRotationDeg,
                                                 "rule": "kader geselecteerd bij baseline OF rotatie; onafhankelijk standpunt telt alleen bij baseline"] as [String: Any],
                                    "frames_selected": frames.count, "frames_usable": usable, "distinct_viewpoints": vps.count,
                                    "rotation_only_frames": max(usable - vps.count, 0)] as [String: Any]
        agree = vps.count
    } else { res.diag["per_frame"] = [Any]() }
    let independent = max(1, agree)
    res.independentFrames = independent
    if independent >= 2 { res.scaleMethod = "LIDAR_DEPTH_MULTI_FRAME" }

    // onzekerheid (Monte Carlo): hoekpixels, wandvlak (offset + kanteling) en kozijnoffset
    var rng = SplitMix64(seed: seed &+ 7)
    let nEff = Double(min(fac.count, cfg.planeEffectiveSamplesCap))
    let sigDepth = max(fac.rms, sig)
    let sigD = sigDepth / nEff.squareRoot()
    let frameSup = Double(max(frm.perSide.values.map { $0.support }.max() ?? 1, 1))
    let sigFrame = mode == "FLUSH" ? 0.0 : thr / min(frameSup, 50).squareRoot()
    let sigTilt = sigDepth / (max(fac.spread, 0.05) * nEff.squareRoot())
    var ws: [Double] = [], hs: [Double] = []
    for _ in 0..<cfg.mcSamples {
        let cp = corners.map { Pixel($0.u + rng.gaussian() * cfg.cornerPixelSigmaPx, $0.v + rng.gaussian() * cfg.cornerPixelSigmaPx) }
        var dl = Vec3(rng.gaussian() * sigTilt, rng.gaussian() * sigTilt, rng.gaussian() * sigTilt)
        dl = dl - n * dl.dot(n)
        let n2 = (n + dl).normalized
        let d2 = n2.dot(fac.centroid) + offset + rng.gaussian() * sigD + (sigFrame > 0 ? rng.gaussian() * sigFrame : 0)
        if let g2 = planeGeometry(view, corners: cp, n: n2, d: d2) { let (a, b) = dimsFromCorners(g2.points, up: worldUp); ws.append(a); hs.append(b) }
    }
    func sd(_ v: [Double]) -> Double { guard v.count > 1 else { return 0 }; let m = v.reduce(0, +) / Double(v.count); return (v.reduce(0) { $0 + pow($1 - m, 2) } / Double(v.count)).squareRoot() }
    res.width = w; res.height = h
    res.sigmaW = sd(ws); res.sigmaH = sd(hs); res.sigmaArea = sd(zip(ws, hs).map { $0 * $1 })
    res.cornersWorld = C; res.planeN = n; res.planeD = dPlane
    res.scaleEvidence = ["kind": "LIDAR_DEPTH_FRAME_PLANE_V2", "frame_plane_mode": mode, "recess_cm": rd(-offset * 100, 10), "facade_support": rd(fac.support, 1000),
                         "facade_rms_m": rd(fac.rms), "facade_inlier_ratio": rd(an.inlierRatio, 1000), "independent_frames": independent,
                         "depth_coverage": rd(coverage, 1000), "incidence_cos_min": rd(geo.cosMin, 1000)]
    res.diag["selected_plane"] = ["role": "FACADE", "inlier_ratio": rd(an.inlierRatio, 1000), "rms_m": rd(fac.rms), "sides_covered": fac.sidesCovered,
                                  "normal": [rd(n.x), rd(n.y), rd(n.z)]] as [String: Any]
    let ctr = C.reduce(Vec3.zero, +) * 0.25
    res.diag["distance_to_frame_m"] = rd((ctr - oCam).norm, 1000)
    res.diag["independent_frames"] = independent
    res.diag["result"] = ["width_m": rd(w), "height_m": rd(h)] as [String: Any]
    finishDiag(&res, res.flags)
    return res
}

/// Fusie van standpunten: inverse-variantie; inconsistent -> geen waarde (UNKNOWN).
public func fuse(_ results: [LevelResult], cfg: Config = Config()) -> LevelResult {
    let good = results.filter { $0.ok }
    var out = LevelResult(level: .A, scaleMethod: good.first?.scaleMethod ?? "NONE", viewIds: good.flatMap { $0.viewIds })
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
    out.independentFrames = good.map { $0.independentFrames }.max() ?? 1
    out.scaleEvidence = best.scaleEvidence; out.diag = best.diag
    return out
}
