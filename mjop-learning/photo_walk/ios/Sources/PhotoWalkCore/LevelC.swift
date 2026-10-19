import Foundation

public struct ReferenceMeasure {
    public var referenceId: String
    public var p1: Pixel, p2: Pixel
    public var distanceM: Double
    public var distanceSigmaM: Double?
    public var planeId: String?
    public var targetPlaneId: String?
    public init(referenceId: String, p1: Pixel, p2: Pixel, distanceM: Double, distanceSigmaM: Double? = nil, planeId: String? = nil, targetPlaneId: String? = nil) {
        self.referenceId = referenceId; self.p1 = p1; self.p2 = p2; self.distanceM = distanceM
        self.distanceSigmaM = distanceSigmaM; self.planeId = planeId; self.targetPlaneId = targetPlaneId
    }
}

/// Homografie eenheidsvierkant (TL=(0,0), TR=(1,0), BR=(1,1), BL=(0,1)) -> pixel, DLT met h33 = 1 (8x8 stelsel).
func homographyUnitSquare(_ q: [Pixel]) -> [[Double]]? {
    let src: [(Double, Double)] = [(0, 0), (1, 0), (1, 1), (0, 1)]
    var A = [[Double]](), b = [Double]()
    for (k, s) in src.enumerated() {
        let (x, y) = s, u = q[k].u, v = q[k].v
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    }
    guard let h = solveLinear(A, b) else { return nil }
    return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1]]
}

private func mulInvK(_ intr: Intrinsics, _ H: [[Double]]) -> [Vec3] {
    (0..<3).map { c in Vec3((H[0][c] - intr.cx * H[2][c]) / intr.fx, (H[1][c] - intr.cy * H[2][c]) / intr.fy, H[2][c]) }
}

struct RefSolution { var w: Double; var h: Double; var corners: [Vec3]; var ortho: Double }

func solveReference(_ intr: Intrinsics, upCam: Vec3, anchor: [Pixel], p1: Pixel, p2: Pixel, dist: Double, target: [Pixel]) -> RefSolution? {
    guard let H = homographyUnitSquare(anchor) else { return nil }
    var m = mulInvK(intr, H)
    if m[2].z < 0 { m = m.map { $0 * -1 } }
    let n = m[0].cross(m[1]).normalized
    let ortho = abs(m[0].dot(m[1])) / (m[0].norm * m[1].norm)
    let ds = n.dot(m[2])
    var pts: [Vec3] = []
    for p in [p1, p2] + target {
        let r = intr.cameraRay(p)
        let den = r.dot(n)
        if abs(den) < 1e-9 { return nil }
        let P = r * (ds / den)
        if P.z <= 0 { return nil }
        pts.append(P)
    }
    let dS = (pts[0] - pts[1]).norm
    if dS < 1e-9 { return nil }
    let k = dist / dS
    let C = pts[2...].map { $0 * k }
    let (w, h) = dimsFromCorners(Array(C), up: upCam)
    return RefSolution(w: w, h: h, corners: Array(C), ortho: ortho)
}

/// Niveau C: afgeleide maat uit een referentieafstand op hetzelfde vlak. `anchor` is een rechthoek op het referentievlak (standaard: het doelkozijn).
public func measureWithReference(view: ViewInput, target: [Pixel], ref: ReferenceMeasure, anchor: [Pixel]? = nil, cfg: Config = Config(), seed: UInt64 = 0,
                                 poseIsValid: Bool = true) -> LevelResult {
    var res = LevelResult(level: .C, scaleMethod: "REFERENCE_DISTANCE", viewIds: [view.frameId])
    let imgArea = Double(view.intrinsics.width * view.intrinsics.height)
    let anc = anchor ?? target
    let dpx = ((ref.p1.u - ref.p2.u) * (ref.p1.u - ref.p2.u) + (ref.p1.v - ref.p2.v) * (ref.p1.v - ref.p2.v)).squareRoot()
    if !(ref.distanceM > 0) || !ref.distanceM.isFinite || dpx < 2 { res.flags.append(Flags.make("REFERENCE_INVALID")); return res }
    if !isSimpleConvexQuad(target, imageArea: imgArea) || !isSimpleConvexQuad(anc, imageArea: imgArea) { res.flags.append(Flags.make("CORNER_ORDER_INVALID")); return res }
    if let a = ref.planeId, let b = ref.targetPlaneId, a != b { res.flags.append(Flags.make("REFERENCE_PLANE_MISMATCH", "\(a) != \(b)")); return res }
    if view.depth != nil, case let (fit?, _) = fitFacadePlane(view, corners: anc, cfg: cfg, seed: seed) {
        for p in [ref.p1, ref.p2] {
            if let zl = localDepth(view, p) {
                let X = unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: p, depthZ: zl)
                let dd = abs(X.dot(fit.n) - fit.d)
                if dd > cfg.refPlaneTolM { res.flags.append(Flags.make("REFERENCE_PLANE_MISMATCH", "punt ligt \(dd) m van het gevelvlak")) }
            }
        }
        if hasBlocking(res.flags) { return res }
    }
    let upCam = poseIsValid ? view.pose.rotateInverse(worldUp) : Vec3(0, -1, 0)
    guard let sol = solveReference(view.intrinsics, upCam: upCam, anchor: anc, p1: ref.p1, p2: ref.p2, dist: ref.distanceM, target: target) else {
        res.flags.append(Flags.make("REFERENCE_INVALID", "geometrie ontaard")); return res
    }
    if sol.ortho > cfg.refOrthogonalityTol { res.flags.append(Flags.make("RECT_ASSUMPTION_VIOLATED", "loodrechtheidsfout \(sol.ortho)")); return res }
    let bad = rectangularityProblems(sol.corners, edgeRatioTol: cfg.rectEdgeRatioTol, angleTolDeg: cfg.rectAngleTolDeg)
    if !bad.isEmpty { res.flags.append(Flags.make("WRONG_CORNER_SELECTION", bad.joined(separator: "; "))); return res }
    if !(cfg.minDimM...cfg.maxDimM).contains(sol.w) || !(cfg.minDimM...cfg.maxDimM).contains(sol.h) { res.flags.append(Flags.make("DIMENSION_OUT_OF_RANGE")); return res }
    if anchor != nil { res.flags.append(Flags.make("COPLANARITY_ASSUMED")) }
    if ref.distanceSigmaM == nil { res.flags.append(Flags.make("REFERENCE_UNCERTAINTY_NOT_PROVIDED")) }
    var rng = SplitMix64(seed: seed &+ 11)
    var ws: [Double] = [], hs: [Double] = []
    let s = cfg.cornerPixelSigmaPx
    func jit(_ p: Pixel) -> Pixel { Pixel(p.u + rng.gaussian() * s, p.v + rng.gaussian() * s) }
    for _ in 0..<cfg.mcSamples {
        let d2 = ref.distanceM + (ref.distanceSigmaM.map { rng.gaussian() * $0 } ?? 0)
        if let r = solveReference(view.intrinsics, upCam: upCam, anchor: anc.map(jit), p1: jit(ref.p1), p2: jit(ref.p2), dist: d2, target: target.map(jit)) { ws.append(r.w); hs.append(r.h) }
    }
    func sd(_ v: [Double]) -> Double { guard v.count > 1 else { return 0 }; let m = v.reduce(0, +) / Double(v.count); return (v.reduce(0) { $0 + pow($1 - m, 2) } / Double(v.count)).squareRoot() }
    res.width = sol.w; res.height = sol.h; res.sigmaW = sd(ws); res.sigmaH = sd(hs); res.sigmaArea = sd(zip(ws, hs).map { $0 * $1 })
    res.cornersWorld = sol.corners.map { view.pose.toWorld($0) }
    return res
}
