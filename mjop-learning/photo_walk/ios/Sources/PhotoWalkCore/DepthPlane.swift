import Foundation

// Niveau A v2: robuuste LiDAR-meting met meerdere kandidaatvlakken en meerdere onafhankelijke dieptekaders.
// Port van python/photo_walk_core/depth_plane.py (zie docs/lidar_measurement_v2.md). Alle drempels zijn PROVISIONAL_UNVALIDATED.

public let sideNames = ["TOP", "RIGHT", "BOTTOM", "LEFT"]

func sigmaAt(_ z: Double, _ cfg: Config) -> Double { cfg.lidarSigma0M + cfg.lidarSigma1PerM * z }
func thrAt(_ z: Double, _ cfg: Config) -> Double { cfg.thrK * sigmaAt(z, cfg) + cfg.reliefTolM }

func medianOf(_ a: [Double]) -> Double {
    guard !a.isEmpty else { return 0 }
    let s = a.sorted(), n = s.count
    return n % 2 == 1 ? s[n / 2] : 0.5 * (s[n / 2 - 1] + s[n / 2])
}

public func rd(_ x: Double, _ places: Double = 10000) -> Any { x.isFinite ? (x * places).rounded() / places : NSNull() }
public func rdOpt(_ x: Double?, _ places: Double = 10000) -> Any { guard let x = x else { return NSNull() }; return rd(x, places) }

/// Maakt een [String: Any]-structuur geschikt voor JSONSerialization: niet-eindige getallen worden null.
public func jsonSafe(_ x: Any) -> Any {
    switch x {
    case let d as Double: return d.isFinite ? d : NSNull()
    case let f as Float: return f.isFinite ? Double(f) : NSNull()
    case let a as [Any]: return a.map { jsonSafe($0) }
    case let o as [String: Any]: return o.mapValues { jsonSafe($0) }
    default: return x
    }
}

// MARK: gebieden

struct Regions {
    let sgn: Double
    let edges: [(Pixel, Pixel)]
    let h: [Double]
    let ringIn: [Pixel], ringOut: [Pixel], bandLo: [Pixel], bandHi: [Pixel], glass: [Pixel]

    static func dist(_ a: Pixel, _ b: Pixel, _ u: Double, _ v: Double, _ sgn: Double) -> Double {
        let eu = b.u - a.u, ev = b.v - a.v
        return ((eu * (v - a.v) - ev * (u - a.u)) * sgn) / max((eu * eu + ev * ev).squareRoot(), 1e-9)
    }

    init(quad: [Pixel], cfg: Config) {
        sgn = signedArea(quad) >= 0 ? 1.0 : -1.0
        var e: [(Pixel, Pixel)] = []
        for i in 0..<4 { e.append((quad[i], quad[(i + 1) % 4])) }
        edges = e
        let cu = quad.map { $0.u }.reduce(0, +) / 4.0, cv = quad.map { $0.v }.reduce(0, +) / 4.0
        let s = sgn
        h = e.map { max(Regions.dist($0.0, $0.1, cu, cv, s), 1e-6) }
        ringIn = scalePolygon(quad, cfg.ringInnerScale); ringOut = scalePolygon(quad, cfg.ringOuterScale)
        bandLo = scalePolygon(quad, cfg.bandLoScale); bandHi = scalePolygon(quad, cfg.bandHiScale); glass = scalePolygon(quad, cfg.glassScale)
    }

    /// kind: 0 buiten, 1 ring, 2 binnenband, 3 glas; side: 0..3 (TOP, RIGHT, BOTTOM, LEFT).
    func classify(_ p: Pixel) -> (kind: Int, side: Int) {
        var kind = 0
        if inConvexPolygon(p, ringOut) && !inConvexPolygon(p, ringIn) { kind = 1 }
        if inConvexPolygon(p, bandHi) && !inConvexPolygon(p, bandLo) { kind = 2 }
        if inConvexPolygon(p, glass) { kind = 3 }
        if kind == 0 { return (0, 0) }
        var best = 0, bd = Double.infinity
        for i in 0..<4 {
            let d = Regions.dist(edges[i].0, edges[i].1, p.u, p.v, sgn) / h[i]
            if d < bd { bd = d; best = i }
        }
        return (kind, best)
    }
}

struct PointSet {
    var X: [Vec3] = []
    var kind: [Int] = []
    var side: [Int] = []
    mutating func append(_ o: PointSet) { X += o.X; kind += o.kind; side += o.side }
}

/// Geldige dieptepunten van een frame, ingedeeld naar de gebieden van het CAPTURE-beeld.
func collectPoints(frame: ViewInput, capture: ViewInput, isCapture: Bool, regions: Regions, cfg: Config) -> PointSet {
    var out = PointSet()
    guard let d = frame.depth, d.width > 0, d.height > 0 else { return out }
    let sx = Double(frame.intrinsics.width) / Double(d.width), sy = Double(frame.intrinsics.height) / Double(d.height)
    let W = Double(capture.intrinsics.width), H = Double(capture.intrinsics.height)
    for i in 0..<d.height {
        for j in 0..<d.width {
            let z = Double(d.values[i * d.width + j])
            guard z.isFinite, z >= cfg.depthMinRangeM, z <= cfg.depthMaxRangeM else { continue }
            let px = Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy)
            let X = unprojectDepth(pose: frame.pose, intr: frame.intrinsics, pixel: px, depthZ: z)
            var uvc = px
            if !isCapture {
                let (p, zc) = project(pose: capture.pose, intr: capture.intrinsics, world: X)
                if zc <= 0 { continue }
                uvc = p
            }
            if uvc.u < 0 || uvc.u > W || uvc.v < 0 || uvc.v > H { continue }
            let (k, s) = regions.classify(uvc)
            if k > 0 { out.X.append(X); out.kind.append(k); out.side.append(s) }
        }
    }
    return out
}

/// Onafhankelijke ondersteunende frames: tracking normaal, diepte aanwezig en voldoende standpuntverschil (translatie of rotatie) t.o.v. alle gekozen frames.
func selectSupportFrames(capture: ViewInput, supports: [ViewInput], cfg: Config) -> (chosen: [ViewInput], rejected: [(String, String)]) {
    var chosen = [capture]
    var rejected: [(String, String)] = []
    for v in supports {
        if v.depth == nil || !v.trackingNormal { rejected.append((v.frameId, "TRACKING_OR_DEPTH")); continue }
        var ok = true
        for c in chosen {
            let dt = (v.pose.t - c.pose.t).norm
            var tr = 0.0
            for i in 0..<3 { tr += v.pose.r[i].dot(c.pose.r[i]) }
            let rot = acos(max(-1, min(1, (tr - 1) / 2))) * 180 / Double.pi
            if dt < cfg.minBaselineM && rot < cfg.minRotationDeg { ok = false; break }
        }
        if ok && chosen.count < 1 + cfg.maxSupportFrames { chosen.append(v) } else { rejected.append((v.frameId, "CORRELATED_OR_LIMIT")) }
    }
    return (chosen, rejected)
}

// MARK: vlakken

struct MaskPlane { var n: Vec3; var d: Double; var mask: [Bool]; var rms: Double; var centroid: Vec3; var count: Int }

func ransacPlaneMask(_ P: [Vec3], threshold: Double, iterations: Int, seed: UInt64, maxPoints: Int) -> MaskPlane? {
    guard P.count >= 3 else { return nil }
    var rng = SplitMix64(seed: seed)
    var subIdx: [Int]
    if P.count <= maxPoints { subIdx = Array(0..<P.count) } else {
        var all = Array(0..<P.count)
        for i in 0..<maxPoints { let j = i + Int(rng.next() % UInt64(P.count - i)); all.swapAt(i, j) }
        subIdx = Array(all[0..<maxPoints])
    }
    let sub = subIdx.map { P[$0] }
    var best: (Vec3, Double)? = nil
    var bestCnt = -1
    for _ in 0..<iterations {
        let i = Int(rng.next() % UInt64(sub.count)), j = Int(rng.next() % UInt64(sub.count)), k = Int(rng.next() % UInt64(sub.count))
        if i == j || j == k || i == k { continue }
        let nn = (sub[j] - sub[i]).cross(sub[k] - sub[i])
        if nn.norm < 1e-9 { continue }
        let n = nn.normalized
        var cnt = 0
        for p in sub where abs((p - sub[i]).dot(n)) < threshold { cnt += 1 }
        if cnt > bestCnt { bestCnt = cnt; best = (n, n.dot(sub[i])) }
    }
    guard let b = best else { return nil }
    var n = b.0, d = b.1
    var mask = P.map { abs($0.dot(n) - d) < threshold }
    for _ in 0..<2 {
        let inl = zip(P, mask).filter { $0.1 }.map { $0.0 }
        if inl.count < 3 { break }
        let f = fitLeastSquaresPlane(inl)
        n = f.n; d = f.d
        mask = P.map { abs($0.dot(n) - d) < threshold }
    }
    let inl = zip(P, mask).filter { $0.1 }.map { $0.0 }
    guard !inl.isEmpty else { return nil }
    let ctr = inl.reduce(Vec3.zero, +) * (1.0 / Double(inl.count))
    let rms = (inl.reduce(0) { $0 + pow($1.dot(n) - d, 2) } / Double(inl.count)).squareRoot()
    return MaskPlane(n: n, d: d, mask: mask, rms: rms, centroid: ctr, count: inl.count)
}

struct PlaneCand {
    var n: Vec3, d: Double
    var idx: [Int]
    var rms: Double
    var centroid: Vec3
    var count: Int
    var sides: [Int]
    var spread: Double
    var facing = 0.0, vertical = 0.0
    var role = "REVEAL_OR_LEDGE"
    var support = 0.0, robustSigma = 0.0
    var sidesCovered = 0
}

func sequentialPlanes(_ P: [Vec3], side: [Int], thr: Double, cfg: Config, seed: UInt64) -> [PlaneCand] {
    var planes: [PlaneCand] = []
    var remaining = [Bool](repeating: true, count: P.count)
    for k in 0..<cfg.maxPlanes {
        let idx = (0..<P.count).filter { remaining[$0] }
        if idx.count < cfg.minPlanePoints { break }
        guard let res = ransacPlaneMask(idx.map { P[$0] }, threshold: thr, iterations: cfg.ransacIterationsV2, seed: seed &+ UInt64(17 * k), maxPoints: cfg.maxRansacPoints) else { break }
        if Double(res.count) < max(Double(cfg.minPlanePoints), cfg.planeMinFraction * Double(P.count)) { break }
        var gidx: [Int] = []
        for (m, g) in zip(res.mask, idx) where m { gidx.append(g) }
        var sides = [0, 0, 0, 0]
        for g in gidx { sides[side[g]] += 1 }
        var acc = 0.0
        for g in gidx { let q = P[g] - res.centroid; acc += q.dot(q) - pow(q.dot(res.n), 2) }
        let spread = (acc / Double(gidx.count)).squareRoot()
        planes.append(PlaneCand(n: res.n, d: res.d, idx: gidx, rms: res.rms, centroid: res.centroid, count: res.count, sides: sides, spread: spread))
        for g in gidx { remaining[g] = false }
    }
    return planes
}

func classifyPlanes(_ planes: inout [PlaneCand], camPos: Vec3, cfg: Config) {
    for i in planes.indices {
        if planes[i].n.dot(camPos - planes[i].centroid) < 0 { planes[i].n = planes[i].n * -1; planes[i].d = -planes[i].d }
        let v = (planes[i].centroid - camPos).normalized
        planes[i].facing = abs(planes[i].n.dot(v))
        planes[i].vertical = abs(planes[i].n.dot(worldUp))
        planes[i].role = (planes[i].facing >= cfg.facadeMinFacing && planes[i].vertical <= cfg.facadeMaxVertical) ? "FACADE_CANDIDATE" : "REVEAL_OR_LEDGE"
    }
}

/// Kiest het wandvlak of geeft een specifieke weigering: (index, code, detail).
func pickFacade(_ planes: inout [PlaneCand], ring: [Vec3], zMed: Double, cfg: Config) -> (Int?, String?, String) {
    let thr = thrAt(zMed, cfg)
    let cands = planes.indices.filter { planes[$0].role == "FACADE_CANDIDATE" }.sorted { a, b in
        planes[a].count != planes[b].count ? planes[a].count > planes[b].count : a < b
    }
    guard let bi = cands.first else { return (nil, "NO_FACADE_PLANE", "geen verticaal, naar de camera gericht vlak in de ring") }
    for pi in cands.dropFirst() {
        let parallel = abs(planes[pi].n.dot(planes[bi].n)) > 0.97
        let pd = planes[pi].n.dot(planes[bi].n) > 0 ? planes[pi].d : -planes[pi].d
        let step = abs(pd - planes[bi].d)
        if parallel && step > 1.5 * thr && Double(planes[pi].count) >= cfg.ambiguityRatio * Double(planes[bi].count) {
            planes[pi].role = "PARALLEL_STEP"
            return (nil, "AMBIGUOUS_FACADE_PLANES", String(format: "twee grote parallelle vlakken, %.2f m uit elkaar", step))
        }
        if parallel && step > 1.5 * thr { planes[pi].role = "PARALLEL_STEP" }
    }
    planes[bi].role = "FACADE"
    var explained = 0
    for (i, p) in planes.enumerated() where i != bi && (p.role == "REVEAL_OR_LEDGE" || p.role == "PARALLEL_STEP") { explained += p.count }
    let denom = max(ring.count - explained, 1)
    planes[bi].support = Double(planes[bi].count) / Double(denom)
    if planes[bi].support < cfg.facadeSupportMin {
        return (nil, "FACADE_NOT_PLANAR", String(format: "wandvlak verklaart slechts %.2f van de ringpunten", planes[bi].support))
    }
    if planes[bi].rms > cfg.facadeRmsK * sigmaAt(zMed, cfg) + 0.008 {
        return (nil, "FACADE_NOT_PLANAR", String(format: "vlak te ruw: rms %.3f m", planes[bi].rms))
    }
    let n = planes[bi].n, d = planes[bi].d
    planes[bi].robustSigma = 1.4826 * medianOf(ring.map { abs($0.dot(n) - d) })
    if planes[bi].robustSigma > 2.0 * sigmaAt(zMed, cfg) + 0.012 {
        return (nil, "FACADE_NOT_PLANAR", String(format: "robuuste ruis rond het vlak %.3f m (ruw oppervlak)", planes[bi].robustSigma))
    }
    let sidesOk = planes[bi].sides.filter { $0 >= cfg.sideMinPoints }.count
    planes[bi].sidesCovered = sidesOk
    if sidesOk < 2 { return (nil, "FACADE_ONE_SIDED", "wand slechts aan \(sidesOk) zijde(n) gezien") }
    if sidesOk == 2 {
        let s = planes[bi].sides, m = cfg.sideMinPoints
        let opposite = (s[0] >= m && s[2] >= m) || (s[1] >= m && s[3] >= m)
        if !opposite { return (nil, "FACADE_ONE_SIDED", "wand alleen aan twee aangrenzende zijden gezien") }
    }
    return (bi, nil, "")
}

// MARK: kozijnvlak (terugligging t.o.v. de wand)

/// Dieptaclusters (1D-histogram, bin thr/2): lijst van (offset, steun).
func depthClusters(_ s: [Double], thr: Double) -> [(Double, Int)] {
    guard let lo = s.min(), let hi = s.max() else { return [] }
    let bw = max(thr / 2, 1e-3)
    let nb = Int(((hi - lo) / bw).rounded(.up)) + 1
    var h = [Double](repeating: 0, count: nb)
    for v in s { h[min(max(Int((v - lo) / bw), 0), nb - 1)] += 1 }
    var hs = [Double](repeating: 0, count: nb)
    for i in 0..<nb { hs[i] = h[i] + (i > 0 ? h[i - 1] : 0) + (i + 1 < nb ? h[i + 1] : 0) }
    var out: [(Double, Int)] = []
    var used = [Bool](repeating: false, count: s.count)
    func clear(_ k: Int) { for i in max(k - 2, 0)...min(k + 2, nb - 1) { hs[i] = 0 } }
    for _ in 0..<4 {
        var k = 0
        for i in 1..<max(nb, 1) where hs[i] > hs[k] { k = i }
        if hs[k] <= 0 { break }
        let center = lo + (Double(k) + 0.5) * bw
        var members: [Double] = []
        var mi: [Int] = []
        for (i, v) in s.enumerated() where !used[i] && abs(v - center) <= thr { members.append(v); mi.append(i) }
        if members.isEmpty { clear(k); continue }
        out.append((medianOf(members), members.count))
        for i in mi { used[i] = true }
        clear(k)
    }
    return out
}

/// Offset van het kozijnprofiel op een zijde: van de clusters met voldoende steun het dichtstbijzijnde (het profiel ligt vóór het glas).
func modeOffset(_ s: [Double], thr: Double, minShare: Double) -> (Double?, Int) {
    let cl = depthClusters(s, thr: thr)
    guard !cl.isEmpty else { return (nil, 0) }
    let top = cl.map { $0.1 }.max()!
    let cand = cl.filter { Double($0.1) >= minShare * Double(top) }
    let best = cand.max { $0.0 < $1.0 }!
    return (best.0, best.1)
}

struct FrameOffset {
    var mode = "UNDETERMINED"
    var offset: Double?
    var group: [String] = []
    var ledge: [String] = []
    var perSide: [String: (offset: Double?, support: Int)] = [:]
    var thr = 0.0
}

func frameOffset(band: [Vec3], side: [Int], facade: PlaneCand, zMed: Double, cfg: Config) -> FrameOffset {
    let thr = thrAt(zMed, cfg)
    var out = FrameOffset()
    out.thr = thr
    var vals: [(String, Double)] = []
    for (k, name) in sideNames.enumerated() {
        var s: [Double] = []
        for (p, sd) in zip(band, side) where sd == k {
            let v = p.dot(facade.n) - facade.d
            if abs(v) <= cfg.frameSearchM { s.append(v) }
        }
        let (off, sup) = modeOffset(s, thr: thr, minShare: cfg.bandClusterMinShare)
        let valid = sup >= cfg.frameSideMinPoints
        out.perSide[name] = (valid ? off : nil, sup)
        if valid, let o = off { vals.append((name, o)) }
    }
    if vals.count < 2 { out.mode = "UNDETERMINED"; return out }
    var best: [(String, Double)] = []
    for (_, v0) in vals {
        let grp = vals.filter { abs($0.1 - v0) <= cfg.frameGroupTolK * thr }
        if grp.count > best.count { best = grp }
    }
    let bestNames = Set(best.map { $0.0 })
    let rest = vals.filter { !bestNames.contains($0.0) }
    let medBest = medianOf(best.map { $0.1 })
    let split = best.count == 2 && rest.count == 2 && abs(medBest - medianOf(rest.map { $0.1 })) > cfg.frameGroupTolK * thr
    if best.count < 2 || split {
        out.mode = (best.count >= 2 || vals.count >= 3) ? "INCONSISTENT" : "UNDETERMINED"
        out.group = best.map { $0.0 }
        return out
    }
    let off = medBest
    let flush = max(0.015, cfg.flushTolK * sigmaAt(zMed, cfg))
    out.mode = abs(off) <= flush ? "FLUSH" : (off < 0 ? "RECESSED" : "PROTRUDING")
    out.offset = out.mode == "FLUSH" ? 0.0 : off
    out.group = best.map { $0.0 }
    out.ledge = rest.map { $0.0 }
    return out
}

func cornerValues(_ view: ViewInput, _ p: Pixel, r: Int = 2) -> [Double] {
    guard let d = view.depth, d.width > 0, d.height > 0, p.u.isFinite, p.v.isFinite else { return [] }
    let sx = Double(view.intrinsics.width) / Double(d.width), sy = Double(view.intrinsics.height) / Double(d.height)
    let j = min(max(Int(p.u / sx), 0), d.width - 1), i = min(max(Int(p.v / sy), 0), d.height - 1)
    var out: [Double] = []
    for ii in max(i - r, 0)...min(i + r, d.height - 1) {
        for jj in max(j - r, 0)...min(j + r, d.width - 1) {
            let z = Double(d.values[ii * d.width + jj])
            if z.isFinite && z > 0 { out.append(z) }
        }
    }
    return out
}

/// Hoekstralen van het capture-beeld op het vlak n.x = d: (hoeken, kleinste |cos|) of nil als een straal het vlak niet raakt.
func planeGeometry(_ view: ViewInput, corners: [Pixel], n: Vec3, d: Double) -> (points: [Vec3], cosMin: Double)? {
    let rays = raysWorld(pose: view.pose, intr: view.intrinsics, pixels: corners)
    var pts: [Vec3] = [], cosMin = Double.infinity
    for dir in rays.dirs {
        guard let h = intersectRayPlane(origin: rays.origin, dir: dir, n: n, d: d) else { return nil }
        pts.append(h.point); cosMin = min(cosMin, h.cosIncidence)
    }
    return (pts, cosMin)
}

// MARK: analyse van een puntenset

struct Analysis {
    var flags: [QualityFlag] = []
    var planes: [[String: Any]] = []
    var facade: PlaneCand?
    var frame: FrameOffset?
    var stats: [String: Any] = [:]
    var zMed = 3.0
    var thr = 0.0
    var inlierRatio = 0.0
}

func analyzePoints(capture: ViewInput, _ pts: PointSet, cfg: Config, seed: UInt64) -> Analysis {
    var res = Analysis()
    var ring: [Vec3] = [], rs: [Int] = [], band: [Vec3] = [], bs: [Int] = []
    for i in 0..<pts.X.count {
        if pts.kind[i] == 1 { ring.append(pts.X[i]); rs.append(pts.side[i]) }
        else if pts.kind[i] == 2 { band.append(pts.X[i]); bs.append(pts.side[i]) }
    }
    let cam = capture.pose.t
    let zMed = ring.isEmpty ? 3.0 : medianOf(ring.map { ($0 - cam).norm })
    let thr = thrAt(zMed, cfg)
    res.zMed = zMed; res.thr = thr
    res.stats = ["ring_points": ring.count, "range_median_m": rd(zMed), "sigma_m": rd(sigmaAt(zMed, cfg)), "threshold_m": rd(thr)]
    if ring.count < cfg.minPlanePoints {
        res.flags.append(Flags.make("DEPTH_COVERAGE_LOW", "\(ring.count) ringpunten")); return res
    }
    var planes = sequentialPlanes(ring, side: rs, thr: thr, cfg: cfg, seed: seed)
    classifyPlanes(&planes, camPos: cam, cfg: cfg)
    let (fi, code, detail) = pickFacade(&planes, ring: ring, zMed: zMed, cfg: cfg)
    res.planes = planes.map { p in
        ["role": p.role, "count": p.count, "rms_m": rd(p.rms), "facing": rd(p.facing), "vertical": rd(p.vertical),
         "normal": [rd(p.n.x), rd(p.n.y), rd(p.n.z)], "offset": rd(p.d), "sides": p.sides] as [String: Any]
    }
    guard let f = fi else { res.flags.append(Flags.make(code ?? "NO_FACADE_PLANE", detail)); return res }
    let facade = planes[f]
    res.facade = facade
    res.inlierRatio = Double(facade.count) / Double(ring.count)
    res.stats["facade_support"] = rd(facade.support); res.stats["facade_rms_m"] = rd(facade.rms)
    res.stats["facade_sides"] = facade.sidesCovered; res.stats["facade_inlier_ratio"] = rd(res.inlierRatio)
    if facade.vertical > 0.2 { res.flags.append(Flags.make("FACADE_NOT_VERTICAL", String(format: "|n.up|=%.2f", facade.vertical))) }
    if facade.sidesCovered == 2 { res.flags.append(Flags.make("LIMITED_SIDE_COVERAGE")) }
    res.frame = frameOffset(band: band, side: bs, facade: facade, zMed: zMed, cfg: cfg)
    return res
}

// MARK: kaderomvang

/// Omvat het kader de buitenrand van het kozijn? Per kaderrand loodrecht de diepte-afwijking t.o.v. het gekozen vlak naar binnen en naar buiten volgen.
func quadExtent(_ view: ViewInput, corners: [Pixel], n: Vec3, dPlane: Double, zMed: Double, cfg: Config) -> (sides: [[String: Any]], larger: Int, inside: Int) {
    guard let dm = view.depth, dm.width > 0, dm.height > 0 else { return ([], 0, 0) }
    let sx = Double(view.intrinsics.width) / Double(dm.width), sy = Double(view.intrinsics.height) / Double(dm.height)
    let sgn = signedArea(corners) >= 0 ? 1.0 : -1.0
    let cu = corners.map { $0.u }.reduce(0, +) / 4.0, cv = corners.map { $0.v }.reduce(0, +) / 4.0
    let thr = thrAt(zMed, cfg)
    let mpp = zMed * sx / view.intrinsics.fx
    var out: [[String: Any]] = []
    var larger = 0, inside = 0
    let W = Double(view.intrinsics.width), H = Double(view.intrinsics.height)
    for i in 0..<4 {
        let a = corners[i], b = corners[(i + 1) % 4]
        let eu = b.u - a.u, ev = b.v - a.v
        let L = max((eu * eu + ev * ev).squareRoot(), 1e-9)
        let nu = -ev / L * sgn, nv = eu / L * sgn
        let hdep = abs((cu - a.u) * nu + (cv - a.v) * nv) / sx
        let K = Int(min(max(hdep * 0.8, 8), 60))
        var prof = [Double?](repeating: nil, count: 2 * K + 1)
        for k in -K...K {
            var pix: [Pixel] = [], zs: [Double] = []
            for t in 0..<7 {
                let f = 0.2 + 0.6 * Double(t) / 6.0
                let pu = a.u + f * eu + Double(k) * sx * nu, pv = a.v + f * ev + Double(k) * sx * nv
                if pu < 0 || pu >= W || pv < 0 || pv >= H { continue }
                let jj = min(max(Int(pu / sx), 0), dm.width - 1), ii = min(max(Int(pv / sy), 0), dm.height - 1)
                let z = Double(dm.values[ii * dm.width + jj])
                if z.isFinite && z > 0 { pix.append(Pixel(pu, pv)); zs.append(z) }
            }
            if zs.count < 3 { continue }
            var ds: [Double] = []
            for (p, z) in zip(pix, zs) { ds.append(unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: p, depthZ: z).dot(n) - dPlane) }
            prof[k + K] = medianOf(ds)
        }
        func first(_ ks: [Int]) -> (Int, Double)? {
            var run = 0
            for k in ks {
                if let v = prof[k + K], abs(v) > 1.2 * thr {
                    run += 1
                    if run >= 2 { return (k > 0 ? k - 1 : k + 1, v) }
                } else { run = 0 }
            }
            return nil
        }
        let inn = first(Array(1...K)), outt = first(Array((-K)...(-1)).reversed())
        var rec: [String: Any] = ["side": sideNames[i]]
        rec["d_in_m"] = inn.map { rd(Double(abs($0.0)) * mpp, 1000) } ?? NSNull()
        rec["s_in_m"] = inn.map { rd($0.1, 1000) } ?? NSNull()
        rec["d_out_m"] = outt.map { rd(Double(abs($0.0)) * mpp, 1000) } ?? NSNull()
        rec["s_out_m"] = outt.map { rd($0.1, 1000) } ?? NSNull()
        out.append(rec)
        if let r = inn, Double(abs(r.0)) * mpp > 0.12, r.1 < 0 { larger += 1 }
        if let r = outt, Double(abs(r.0)) * mpp > 0.12, r.1 > 0 { inside += 1 }
    }
    return (out, larger, inside)
}
