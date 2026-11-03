import XCTest
@testable import PhotoWalkCore

/// Synthetische LiDAR-scènes voor niveau A v2 (reproduceerbaar; SIMULATIE). Spiegelt de Python-scenario's in python/tests/test_lidar_v2.py.
/// Echte iPhone-LiDAR-ruis, randvervaging en uitlijning van diepte en beeld zijn hiermee NIET bewezen.
struct SceneSpec {
    var recess = 0.0
    var noise = 0.005
    var sill = false
    var protrusions: [(x0: Double, x1: Double, z: Double)] = []      // verticale stroken (volle hoogte) vóór de gevel
    var glassHoles = false
    var holeP = 0.03
    var shiftPx = 0
}

enum Scene {
    static let outer = (x0: 1.0, y0: 0.9, w: 1.2, h: 1.5)
    static let profile = 0.07, glassRecess = 0.06
    static func intrinsics(scale: Double = 1) -> Intrinsics {
        Intrinsics(fx: 1500 * scale, fy: 1500 * scale, cx: 960 * scale, cy: 720 * scale, width: Int(1920 * scale), height: Int(1440 * scale))
    }

    /// Camera kijkt langs -Z (OpenCV-camera = diag(1,-1,-1)); gevel op Z = 0, kozijn op Z = -recess, glas nog `glassRecess` dieper.
    static func pose(_ p: Vec3, yawDeg: Double = 0) -> Pose {
        let a = yawDeg * Double.pi / 180, c = cos(a), s = sin(a)
        return Pose(rows: [Vec3(c, 0, -s), Vec3(0, -1, 0), Vec3(-s, 0, -c)], t: p)      // Ry * diag(1,-1,-1)
    }

    static func render(_ s: SceneSpec, pos: Vec3, id: String, seed: UInt64, yawDeg: Double = 0, tracking: Bool = true, intr: Intrinsics = intrinsics(), withDepth: Bool = true,
                       depthSize: (Int, Int) = (192, 256)) -> ViewInput {
        let (Hd, Wd) = depthSize
        var rng = SplitMix64(seed: seed)
        var vals = [Float](repeating: .nan, count: Hd * Wd)
        let sx = Double(intr.width) / Double(Wd), sy = Double(intr.height) / Double(Hd)
        let o = outer
        func inRect(_ x: Double, _ y: Double, _ inset: Double) -> Bool { x > o.x0 + inset && x < o.x0 + o.w - inset && y > o.y0 + inset && y < o.y0 + o.h - inset }
        for i in 0..<Hd { for j in 0..<Wd {
            let a = ((Double(j) + 0.5) * sx - intr.cx) / intr.fx, b = ((Double(i) + 0.5) * sy - intr.cy) / intr.fy
            let yc = cos(yawDeg * Double.pi / 180), ys = sin(yawDeg * Double.pi / 180)
            let dx = yc * a - ys, dy = -b, dz = -ys * a - yc               // wereldrichting van de (a, b, 1)-straal
            func hit(_ z: Double) -> (d: Double, x: Double, y: Double) { let t = (z - pos.z) / dz; return (t, pos.x + t * dx, pos.y + t * dy) }
            var depth: Double? = nil
            for p in s.protrusions where depth == nil { let h = hit(p.z); if h.x > p.x0 && h.x < p.x1 { depth = h.d } }
            if depth == nil && s.sill { let h = hit(0.05); if h.x > o.x0 - 0.03 && h.x < o.x0 + o.w + 0.03 && h.y > o.y0 - 0.05 && h.y < o.y0 { depth = h.d } }
            if depth == nil {
                let w = hit(0.0)
                if !inRect(w.x, w.y, 0) { depth = w.d }
                else {
                    let f = hit(-s.recess)
                    if inRect(f.x, f.y, 0) {
                        if inRect(f.x, f.y, profile) {
                            if s.glassHoles { depth = nil } else { depth = hit(-(s.recess + glassRecess)).d }
                        } else { depth = f.d }
                    }
                }
            }
            if let d = depth, rng.uniform() >= s.holeP {
                vals[i * Wd + j] = Float(d + rng.gaussian() * (s.noise + 0.002 * d))
            }
        } }
        if s.shiftPx != 0 {
            var sh = vals
            for i in 0..<Hd { for j in 0..<Wd { sh[i * Wd + (j + s.shiftPx) % Wd] = vals[i * Wd + j] } }
            vals = sh
        }
        return ViewInput(frameId: id, intrinsics: intr, pose: pose(pos, yawDeg: yawDeg), trackingNormal: tracking, depth: withDepth ? DepthMap(width: Wd, height: Hd, values: vals) : nil)
    }

    /// Hoeken (TL, TR, BR, BL) van het kozijn op zijn eigen vlak, geprojecteerd in de camera.
    static func corners(_ s: SceneSpec, pos: Vec3, intr: Intrinsics = intrinsics(), inset: Double = 0, planeRecess: Double? = nil) -> [Pixel] {
        let o = outer, z = -(planeRecess ?? s.recess), d = pos.z - z
        let pts = [(o.x0 + inset, o.y0 + o.h - inset), (o.x0 + o.w - inset, o.y0 + o.h - inset), (o.x0 + o.w - inset, o.y0 + inset), (o.x0 + inset, o.y0 + inset)]
        return pts.map { Pixel(intr.cx + intr.fx * ($0.0 - pos.x) / d, intr.cy + intr.fy * (pos.y - $0.1) / d) }
    }

    static func relErr(_ r: LevelResult) -> Double {
        guard let w = r.width, let h = r.height else { return .infinity }
        return max(abs(w / outer.w - 1), abs(h / outer.h - 1))
    }
}

final class LidarV2Tests: XCTestCase {
    let cam = Vec3(1.6, 1.6, 3.0)
    let cfg = Config()

    private func run(_ s: SceneSpec, supports: Int = 0, spacing: Double = 0.06, seed: UInt64 = 1, cornerNoise: Double = 0) -> LevelResult {
        var v = Scene.render(s, pos: cam, id: "CAP", seed: seed)
        for k in 0..<supports {
            let off = spacing * Double(k / 2 + 1) * (k % 2 == 0 ? 1 : -1)
            v.supports.append(Scene.render(s, pos: Vec3(cam.x + off, cam.y, cam.z), id: "S\(k)", seed: seed * 7 + UInt64(k) + 1))
        }
        var c = Scene.corners(s, pos: cam)
        if cornerNoise > 0 { var r = SplitMix64(seed: 99); c = c.map { Pixel($0.u + r.gaussian() * cornerNoise, $0.v + r.gaussian() * cornerNoise) } }
        return measureDepthView(v, corners: c, cfg: cfg, seed: 1)
    }
    private func codes(_ r: LevelResult) -> Set<String> { Set(r.flags.map { $0.code }) }

    // 1 vlakke gevel met raam
    func testS01FlatFacade() {
        let r = run(SceneSpec())
        XCTAssertTrue(r.ok, "\(codes(r))"); XCTAssertLessThan(Scene.relErr(r), 0.01)
        XCTAssertEqual(r.scaleMethod, "LIDAR_DEPTH_PLANE")
    }

    // 2 terugliggend kozijn: gemeten op het kozijnvlak, niet op de wand (de oude methode onderschatte hier)
    func testS02RecessedWindowMeasuredOnFramePlane() {
        for rec in [0.02, 0.06, 0.12] {
            var s = SceneSpec(); s.recess = rec
            let r = run(s)
            XCTAssertTrue(r.ok, "recess \(rec): \(codes(r))"); XCTAssertLessThan(Scene.relErr(r), 0.012, "recess \(rec)")
        }
    }

    // 3 uitstekende vensterbank, 4 glas zonder diepte
    func testS03SillAndS04UnreliableGlass() {
        var s = SceneSpec(); s.sill = true; s.recess = 0.05
        XCTAssertLessThan(Scene.relErr(run(s)), 0.012)
        var g = SceneSpec(); g.glassHoles = true; g.recess = 0.05
        let r = run(g); XCTAssertTrue(r.ok, "\(codes(r))"); XCTAssertLessThan(Scene.relErr(r), 0.012)
    }

    // 5 meerdere gevelvlakken in één foto: nooit stilzwijgend een verkeerd vlak
    func testS05MultipleFacadePlanesNeverSilentlyWrong() {
        var s = SceneSpec(); s.protrusions = [(x0: 0.2, x1: 0.9, z: 0.15), (x0: 2.3, x1: 3.0, z: 0.15)]
        let r = run(s)
        if r.ok { XCTAssertLessThan(Scene.relErr(r), 0.02) }
        else { XCTAssertFalse(codes(r).isDisjoint(with: ["AMBIGUOUS_FACADE_PLANES", "FACADE_NOT_PLANAR", "FACADE_ONE_SIDED", "NO_FACADE_PLANE"]), "\(codes(r))"); XCTAssertNil(r.width) }
    }

    // 7 onvoldoende dieptedekking, 14 geen diepte
    func testS07CoverageAndNoDepth() {
        var s = SceneSpec(); s.holeP = 0.97
        let r = run(s); XCTAssertNil(r.width); XCTAssertTrue(codes(r).contains("DEPTH_COVERAGE_LOW"), "\(codes(r))")
        let v = Scene.render(SceneSpec(), pos: cam, id: "N", seed: 1, withDepth: false)
        let n = measureDepthView(v, corners: Scene.corners(SceneSpec(), pos: cam)); XCTAssertNil(n.width); XCTAssertTrue(codes(n).contains("NO_DEPTH"))
    }

    // 9/10 verkeerde hoeken: te groot kader en kader binnen het kozijn mogen nooit als buitenmaat worden geclaimd
    func testS10WrongCornersAreNotAcceptedAsOuterDimensions() {
        var s = SceneSpec(); s.recess = 0.05
        let v = Scene.render(s, pos: cam, id: "CAP", seed: 1)
        let good = Scene.corners(s, pos: cam)
        let c = good.reduce(Pixel(0, 0)) { Pixel($0.u + $1.u / 4, $0.v + $1.v / 4) }
        let big = good.map { Pixel(c.u + ($0.u - c.u) * 1.25, c.v + ($0.v - c.v) * 1.25) }
        let r = measureDepthView(v, corners: big, cfg: cfg, seed: 1)
        XCTAssertTrue(!r.ok || !codes(r).isDisjoint(with: ["QUAD_LARGER_THAN_OPENING"]) || Scene.relErr(r) > 0.1, "\(codes(r)) \(Scene.relErr(r))")
        let inner = Scene.corners(s, pos: cam, inset: 0.20, planeRecess: s.recess + Scene.glassRecess)
        let r2 = measureDepthView(v, corners: inner, cfg: cfg, seed: 1)
        if r2.ok { XCTAssertGreaterThan(abs((r2.width ?? 0) - Scene.outer.w), 0.05, "binnenkader mag niet de buitenmaat opleveren") }
    }

    // 11 meerdere LiDAR-frames: multi-frame label alleen bij onafhankelijke kaders
    func testS11MultiFrameAndCorrelatedFramesDoNotCount() {
        var s = SceneSpec(); s.recess = 0.06
        let r = run(s, supports: 3)
        XCTAssertTrue(r.ok, "\(codes(r))"); XCTAssertEqual(r.scaleMethod, "LIDAR_DEPTH_MULTI_FRAME"); XCTAssertGreaterThanOrEqual(r.independentFrames, 2)
        XCTAssertLessThan(Scene.relErr(r), 0.012)
        let same = run(s, supports: 3, spacing: 0.0)
        XCTAssertTrue(same.ok); XCTAssertEqual(same.independentFrames, 1); XCTAssertEqual(same.scaleMethod, "LIDAR_DEPTH_PLANE")
    }

    // 12 tegenstrijdige frames
    func testS12ContradictoryFramesRejected() {
        let s = SceneSpec()
        var v = Scene.render(s, pos: cam, id: "CAP", seed: 1)
        var bad = Scene.render(s, pos: Vec3(cam.x + 0.06, cam.y, cam.z), id: "BAD", seed: 3)
        bad.depth = DepthMap(width: bad.depth!.width, height: bad.depth!.height, values: bad.depth!.values.map { $0 * 1.12 })
        v.supports = [bad, Scene.render(s, pos: Vec3(cam.x - 0.06, cam.y, cam.z), id: "OK", seed: 5)]
        let r = measureDepthView(v, corners: Scene.corners(s, pos: cam), cfg: cfg, seed: 1)
        XCTAssertTrue((!r.ok && codes(r).contains("FRAMES_INCONSISTENT")) || (r.ok && Scene.relErr(r) < 0.015), "\(codes(r))")
    }

    // 13 slechte AR-tracking
    func testS13BadTracking() {
        let v = Scene.render(SceneSpec(), pos: cam, id: "T", seed: 1, tracking: false)
        let r = measureDepthView(v, corners: Scene.corners(SceneSpec(), pos: cam))
        XCTAssertNil(r.width); XCTAssertTrue(codes(r).contains("TRACKING_LOST"))
        var ok = Scene.render(SceneSpec(), pos: cam, id: "CAP", seed: 1)
        ok.supports = [Scene.render(SceneSpec(), pos: Vec3(1.7, 1.6, 3), id: "BADS", seed: 2, tracking: false)]
        let r2 = measureDepthView(ok, corners: Scene.corners(SceneSpec(), pos: cam))
        XCTAssertTrue(r2.ok); XCTAssertEqual(r2.independentFrames, 1, "een frame met slechte tracking telt niet mee")
    }

    // 11b rotatie zonder verplaatsing: extra punten, maar geen onafhankelijk standpunt
    func testS11bRotationOnlyFramesAreNotIndependentViewpoints() {
        let s = SceneSpec()
        var v = Scene.render(s, pos: cam, id: "CAP", seed: 1)
        for k in 0..<3 { v.supports.append(Scene.render(s, pos: cam, id: "R\(k)", seed: UInt64(10 + k), yawDeg: 2.0 * Double(k + 1))) }
        let r = measureDepthView(v, corners: Scene.corners(s, pos: cam), cfg: cfg, seed: 1)
        XCTAssertTrue(r.ok, "\(codes(r))")
        let ind = r.diag["independence"] as? [String: Any]
        XCTAssertEqual(ind?["distinct_viewpoints"] as? Int, 1)
        XCTAssertGreaterThanOrEqual(ind?["rotation_only_frames"] as? Int ?? 0, 1)
        XCTAssertEqual(r.independentFrames, 1); XCTAssertEqual(r.scaleMethod, "LIDAR_DEPTH_PLANE")
    }

    // 14 verkeerd uitgelijnde dieptekaart: begrensde fout, of weigering
    func testS14MisalignedDepthBoundedError() {
        for shift in [3, 8] {
            for rec in [0.0, 0.08] {
                var s = SceneSpec(); s.shiftPx = shift; s.recess = rec
                let r = run(s)
                XCTAssertTrue(!r.ok || Scene.relErr(r) < 0.02, "shift \(shift) recess \(rec): \(Scene.relErr(r))")
            }
        }
    }

    // 15 schaalconsistentie bij een andere beeldresolutie (intrinsics horen bij hetzelfde beeld; digitale zoom raakt origineelpixels niet: zie ZoomTests)
    func testS15ScaleConsistencyAcrossResolutions() {
        for sc in [0.5, 1.0, 1.5] {
            let intr = Scene.intrinsics(scale: sc)
            let s = SceneSpec()
            let v = Scene.render(s, pos: cam, id: "R", seed: 4, intr: intr)
            let r = measureDepthView(v, corners: Scene.corners(s, pos: cam, intr: intr), cfg: cfg, seed: 1)
            XCTAssertTrue(r.ok, "\(sc): \(codes(r))"); XCTAssertLessThan(Scene.relErr(r), 0.015, "schaal \(sc)")
        }
    }

    // regressie: niet vaker verkeerde maten accepteren dan een dun, beschermend algoritme zou doen; hier: geen enkele foutieve acceptatie in een sweep
    func testRegressionSweepNeverAcceptsWrongSizes() {
        var wrong = 0, accepted = 0, total = 0
        var rng = SplitMix64(seed: 2026)
        for n in 0..<24 {
            var s = SceneSpec()
            s.recess = [0, 0.02, 0.05, 0.08, 0.12][Int(rng.next() % 5)]
            s.noise = [0.004, 0.008, 0.012][Int(rng.next() % 3)]
            s.sill = rng.uniform() < 0.4; s.glassHoles = rng.uniform() < 0.3
            s.holeP = [0.02, 0.1, 0.3][Int(rng.next() % 3)]
            let r = run(s, supports: Int(rng.next() % 3), seed: UInt64(n + 1))
            total += 1
            if r.ok { accepted += 1; if Scene.relErr(r) > 0.02 { wrong += 1 } }
        }
        XCTAssertEqual(wrong, 0, "foutieve acceptaties")
        XCTAssertGreaterThanOrEqual(accepted, total * 7 / 10, "te veel weigeringen: de controles zijn ontoelaatbaar streng")
    }

    // referentiesoort: een geschatte afstand is geen meting
    func testUserEstimatedReferenceIsNotMeasured() {
        let s = SceneSpec()
        let v = Scene.render(s, pos: cam, id: "R", seed: 1, withDepth: false)
        let c = Scene.corners(s, pos: cam)
        func status(_ k: ReferenceMeasure.Kind) -> (DimensionStatus, Set<String>) {
            let ref = ReferenceMeasure(referenceId: "R", p1: c[0], p2: c[1], distanceM: Scene.outer.w, distanceSigmaM: 0.005, planeId: "P", kind: k)
            let r = measureWithReference(view: v, target: c, ref: ref)
            return (Status.status(for: r, viewCount: 1), codes(r))
        }
        let est = status(.userEstimate), meas = status(.measuredWithTool)
        XCTAssertEqual(est.0, .ESTIMATED); XCTAssertTrue(est.1.contains("REFERENCE_USER_ESTIMATE"))
        XCTAssertEqual(meas.0, .DERIVED); XCTAssertFalse(meas.1.contains("REFERENCE_USER_ESTIMATE"))
        XCTAssertEqual(Feedback.classify({ var r = LevelResult(level: .C, scaleMethod: "REFERENCE_DISTANCE"); r.width = 1; r.height = 1; r.flags = [Flags.make("REFERENCE_USER_ESTIMATE")]; return r }()), .orange)
    }

    // diagnose: bij weigering een specifieke code, nooit meer alleen MIXED_FACADE_DEPTH
    func testDiagnosticsCarrySpecificReason() {
        var s = SceneSpec(); s.protrusions = [(x0: 0.2, x1: 0.9, z: 0.15), (x0: 2.3, x1: 3.0, z: 0.15)]
        let r = run(s)
        XCTAssertNotNil(r.diag["blocking"]); XCTAssertNotNil(r.diag["stats"])
        if !r.ok { XCTAssertFalse((r.diag["blocking"] as? [String] ?? []).contains("MIXED_FACADE_DEPTH")) }
        let json = try? JSONSerialization.data(withJSONObject: jsonSafe(r.diag))
        XCTAssertNotNil(json, "diag moet als JSON te schrijven zijn")
    }
}
