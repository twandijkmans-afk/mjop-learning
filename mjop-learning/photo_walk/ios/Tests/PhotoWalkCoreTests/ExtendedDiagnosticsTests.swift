import XCTest
@testable import PhotoWalkCore

/// Uitgebreide meetdiagnose 1.1.0 (Swift): pariteit met de Python-referentie op ruisvrije scènes, en bewijs dat de meetuitkomst met en zonder de extra
/// diagnoseberekening IDENTIEK is. De diagnose leest alleen; ze wordt na het resultaat berekend en heeft geen invloed op een maat, vlag of status.
final class ExtendedDiagnosticsTests: XCTestCase {
    let cfg = Config()

    // MARK: fixtures en vergelijking

    private func load(_ name: String) throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }
    private func d(_ x: Any?) -> Double { (x as! NSNumber).doubleValue }
    private func px(_ a: Any?) -> Pixel { let v = a as! [Any]; return Pixel(d(v[0]), d(v[1])) }

    /// Recursieve vergelijking met tolerantie voor getallen; verwachte sleutels moeten aanwezig en gelijk zijn.
    private func assertJSON(_ exp: Any, _ act: Any?, _ path: String, tol: Double, skip: Set<String> = [], file: StaticString = #filePath, line: UInt = #line) {
        if exp is NSNull { XCTAssertTrue(act == nil || act is NSNull, "\(path): verwacht null, kreeg \(String(describing: act))", file: file, line: line); return }
        guard let act = act, !(act is NSNull) else { XCTFail("\(path): ontbreekt of null (verwacht \(exp))", file: file, line: line); return }
        switch exp {
        case let e as [String: Any]:
            guard let a = act as? [String: Any] else { XCTFail("\(path): geen object", file: file, line: line); return }
            for (k, v) in e where !skip.contains(k) { assertJSON(v, a[k], path + "/" + k, tol: tol, skip: skip, file: file, line: line) }
        case let e as [Any]:
            guard let a = act as? [Any] else { XCTFail("\(path): geen array", file: file, line: line); return }
            XCTAssertEqual(e.count, a.count, "\(path): lengte", file: file, line: line)
            for i in 0..<min(e.count, a.count) { assertJSON(e[i], a[i], "\(path)[\(i)]", tol: tol, skip: skip, file: file, line: line) }
        case let e as String:
            XCTAssertEqual(act as? String, e, path, file: file, line: line)
        case let e as NSNumber:
            if CFGetTypeID(e) == CFBooleanGetTypeID() { XCTAssertEqual(act as? Bool, e.boolValue, path, file: file, line: line) }
            else {
                guard let a = (act as? NSNumber)?.doubleValue else { XCTFail("\(path): geen getal", file: file, line: line); return }
                XCTAssertEqual(a, e.doubleValue, accuracy: tol, path, file: file, line: line)
            }
        default: XCTFail("\(path): onbekend type", file: file, line: line)
        }
    }

    /// Canonieke tekst van alles wat een meetuitkomst vormt.
    private func snapshot(_ r: LevelResult) -> String {
        let flags = r.flags.map { ["code": $0.code, "severity": $0.severity.rawValue, "detail": $0.detail ?? NSNull()] as [String: Any] }
        func opt(_ x: Double?) -> Any { if let x = x { return x } else { return NSNull() } }
        let o: [String: Any] = ["ok": r.ok, "w": opt(r.width), "h": opt(r.height), "sw": opt(r.sigmaW), "sh": opt(r.sigmaH), "scale": r.scaleMethod,
                                "indep": r.independentFrames, "flags": flags, "diag": r.diag, "pd": opt(r.planeD)]
        let data = try! JSONSerialization.data(withJSONObject: jsonSafe(o), options: [.sortedKeys])
        return String(decoding: data, as: UTF8.self)
    }

    // MARK: pariteit met Python

    func testExtendedDiagnosticsMatchPythonOnNoiseFreeScenes() throws {
        let src = try load("parity_cases"), fx = try load("ext_diag_parity_cases")
        let tol = d((fx["tolerance"] as! [String: Any])["abs"])
        let i = src["intrinsics"] as! [String: Any]
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        var byName: [String: [String: Any]] = [:]
        for case let cs as [String: Any] in src["level_a_v2"] as! [Any] { byName[cs["name"] as! String] = cs }
        var seen = 0
        for case let c as [String: Any] in fx["cases"] as! [Any] {
            let name = c["name"] as! String
            let cs = try XCTUnwrap(byName[name], name)
            let dw = Int(d(cs["depth_width"])), dh = Int(d(cs["depth_height"]))
            func depthOf(_ e: [String: Any]) -> DepthMap { DepthMap(width: dw, height: dh, values: (e["depth"] as! [Any]).map { Float(d($0)) == 0 ? Float.nan : Float(d($0)) }) }
            func poseOf(_ e: [String: Any]) -> Pose { Pose(rowMajor: (e["pose_row_major"] as! [Any]).map { d($0) }) }
            let cap = cs["capture"] as! [String: Any]
            let sups = (cs["supports"] as! [[String: Any]]).enumerated().map { ViewInput(frameId: "S\($0.offset)", intrinsics: intr, pose: poseOf($0.element), trackingNormal: true, depth: depthOf($0.element)) }
            let view = ViewInput(frameId: "CAP", intrinsics: intr, pose: poseOf(cap), trackingNormal: true, depth: depthOf(cap), supports: sups)
            let corners = (cs["corners_px"] as! [Any]).map(px)
            let r = measureDepthView(view, corners: corners, cfg: cfg, seed: 1)
            let ext = ExtendedDiagnostics.compute(view: view, corners: corners, result: r, cfg: cfg, seed: 1, contourStatus: "USER_CONFIRMED")
            XCTAssertTrue(JSONSerialization.isValidJSONObject(jsonSafe(ext)), name)
            assertJSON(c["expect"] as Any, jsonSafe(ext), name, tol: tol)
            seen += 1
        }
        XCTAssertEqual(seen, 6)
    }

    func testPoseFreeQuadAndFramingOnTheRealCorners() throws {
        let fx = try load("ext_diag_parity_cases")
        let tol = d((fx["tolerance"] as! [String: Any])["abs"])
        var seen = 0
        for case let c as [String: Any] in fx["real_quads"] as! [Any] {
            let name = c["name"] as! String
            let i = c["intrinsics"] as! [String: Any]
            let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
            let corners = (c["corners_px"] as! [Any]).map(px)
            let q = try XCTUnwrap(ExtendedDiagnostics.quadFromCorners(corners, intr), name)
            assertJSON(c["expect_quad_from_corners"] as Any, jsonSafe(q), name + "/quad", tol: 5e-3)
            // geometrie-alleen-framing op een leeg dieptekaart-raster (zoals in de Python-test)
            let dm = DepthMap(width: 256, height: 192, values: [Float](repeating: .nan, count: 256 * 192))
            let view = ViewInput(frameId: "X", intrinsics: intr, pose: .identity, trackingNormal: true, depth: dm)
            let regions = Regions(quad: corners, cfg: cfg)
            let dc = try XCTUnwrap(ExtendedDiagnostics.depthCells(view, regions: regions))
            let fr = ExtendedDiagnostics.framing(view, corners: corners, regions: regions, cells: dc.cells, sx: dc.sx, sy: dc.sy, cfg: cfg, zMed: d(c["range_median_m"]))
            assertJSON(c["expect_framing"] as Any, jsonSafe(fr), name + "/framing", tol: tol)
            seen += 1
        }
        XCTAssertEqual(seen, 2)
    }

    // MARK: de meetuitkomst blijft identiek

    private func scene(_ s: SceneSpec, pos: Vec3, yaw: Double = 0, supports: Int = 0, spacing: Double = 0.06, glassCorners: Bool = false) -> (ViewInput, [Pixel]) {
        var v = Scene.render(s, pos: pos, id: "CAP", seed: 1, yawDeg: yaw)
        for k in 0..<supports {
            let off = spacing * Double(k / 2 + 1) * (k % 2 == 0 ? 1 : -1)
            v.supports.append(Scene.render(s, pos: Vec3(pos.x + off, pos.y, pos.z), id: "S\(k)", seed: 7 + UInt64(k) + 1, yawDeg: yaw))
        }
        return (v, Scene.corners(s, pos: pos, inset: glassCorners ? Scene.profile : 0, planeRecess: glassCorners ? s.recess + Scene.glassRecess : nil))
    }

    func testMeasurementOutcomeIsIdenticalWithAndWithoutExtendedDiagnostics() {
        var rec6 = SceneSpec(); rec6.recess = 0.06
        var sill = SceneSpec(); sill.sill = true; sill.recess = 0.05
        var pier = SceneSpec(); pier.protrusions = [(x0: 0.2, x1: 0.9, z: 0.15)]
        var pier2 = SceneSpec(); pier2.protrusions = [(x0: 0.2, x1: 0.9, z: 0.15), (x0: 2.3, x1: 3.0, z: 0.15)]
        var holes = SceneSpec(); holes.glassHoles = true; holes.recess = 0.05
        let cases: [(String, SceneSpec, Vec3, Double, Int, Double, Bool)] = [
            ("flat", SceneSpec(), Vec3(1.6, 1.6, 3.0), 0, 0, 0.06, false),
            ("recess6_frames", rec6, Vec3(1.6, 1.6, 3.0), 0, 3, 0.06, false),
            ("sill", sill, Vec3(1.6, 1.6, 3.0), 0, 0, 0.06, false),
            ("pier_one_side", pier, Vec3(1.6, 1.6, 3.0), 0, 0, 0.06, false),
            ("pier_two_sides", pier2, Vec3(1.6, 1.6, 3.0), 0, 0, 0.06, false),
            ("glass_holes", holes, Vec3(1.6, 1.6, 3.0), 0, 0, 0.06, false),
            ("no_baseline_frames", SceneSpec(), Vec3(1.6, 1.6, 3.0), 0, 3, 0.0, false),
            // BEPERKTE opnameafstand: geen verplichte 2,5-3 m
            ("limited_1p75m", SceneSpec(), Vec3(1.6, 1.65, 1.75), 0, 0, 0.06, false),
            ("limited_1p8m_recess", rec6, Vec3(1.6, 1.65, 1.8), 0, 2, 0.06, false),
            ("limited_oblique30_2m", SceneSpec(), Vec3(1.6 + 2.0 * tan(30 * Double.pi / 180), 1.65, 2.0), 30, 0, 0.06, false),
            ("closeup_glass_1p5m", SceneSpec(), Vec3(1.6, 1.6, 1.5), 0, 0, 0.06, true),
        ]
        for (name, spec, pos, yaw, sup, spacing, glass) in cases {
            let (view, corners) = scene(spec, pos: pos, yaw: yaw, supports: sup, spacing: spacing, glassCorners: glass)
            let before = measureDepthView(view, corners: corners, cfg: cfg, seed: 1)
            let snapBefore = snapshot(before)
            let ext = ExtendedDiagnostics.compute(view: view, corners: corners, result: before, cfg: cfg, seed: 1, contourStatus: "UNVERIFIED")
            XCTAssertEqual(snapshot(before), snapBefore, "\(name): resultaat veranderd door de extra diagnose")
            let after = measureDepthView(view, corners: corners, cfg: cfg, seed: 1)
            XCTAssertEqual(snapshot(after), snapBefore, "\(name): meetuitkomst na de extra diagnose wijkt af")
            XCTAssertEqual(ext["computed_after_result"] as? Bool, true, name)
            XCTAssertTrue(JSONSerialization.isValidJSONObject(jsonSafe(ext)), name)
        }
    }

    func testLimitedStandoffIsDescribedWithoutRequiringADistance() throws {
        let (view, corners) = scene(SceneSpec(), pos: Vec3(1.6, 1.65, 1.75))
        let r = measureDepthView(view, corners: corners, cfg: cfg, seed: 1)
        let ext = ExtendedDiagnostics.compute(view: view, corners: corners, result: r, cfg: cfg, seed: 1)
        let fr = try XCTUnwrap(ext["framing"] as? [String: Any])
        let over = try XCTUnwrap(fr["ring_out_overflow_px"] as? [String: Any])
        XCTAssertTrue(over.values.contains { (($0 as? Double) ?? 0) > 0 }, "de ring valt deels buiten beeld")
        XCTAssertLessThan(try XCTUnwrap(fr["ring_in_view_fraction"] as? Double), 1.0)
        XCTAssertTrue((fr["note"] as? String ?? "").contains("geen eis"))
        for k in ["gate", "status", "required"] { XCTAssertNil(fr[k]) }
        let sh = try XCTUnwrap(ext["gates_shadow"] as? [String: Any])
        for g in sh["gates"] as! [[String: Any]] { XCTAssertTrue(["PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE"].contains(g["status"] as! String)) }
    }

    func testReferenceMeasurePathWithoutDepthIsSupported() {
        let v = Scene.render(SceneSpec(), pos: Vec3(1.6, 1.6, 3.0), id: "N", seed: 1, withDepth: false)
        let corners = Scene.corners(SceneSpec(), pos: Vec3(1.6, 1.6, 3.0))
        let r = measureDepthView(v, corners: corners, cfg: cfg, seed: 1)
        let ext = ExtendedDiagnostics.compute(view: v, corners: corners, result: r, cfg: cfg, seed: 1)
        XCTAssertTrue(ext["gates_shadow"] is NSNull); XCTAssertEqual((ext["planes_all"] as? [Any])?.count, 0)
        XCTAssertNotNil(ext["quad_from_corners"] as? [String: Any])
    }

    func testFramesDetailFlagsCorrelatedSupports() throws {
        let (view, corners) = scene(SceneSpec(), pos: Vec3(1.6, 1.6, 3.0), supports: 3, spacing: 0.0)
        let r = measureDepthView(view, corners: corners, cfg: cfg, seed: 1)
        let ext = ExtendedDiagnostics.compute(view: view, corners: corners, result: r, cfg: cfg, seed: 1)
        let frames = try XCTUnwrap(ext["frames"] as? [[String: Any]])
        let sup = frames.filter { $0["role"] as? String == "SUPPORT" }
        XCTAssertEqual(sup.count, 3)
        for f in sup {
            XCTAssertEqual(f["used"] as? Bool, false); XCTAssertEqual(f["reason"] as? String, "CORRELATED_OR_LIMIT")
            XCTAssertEqual(f["meets_baseline"] as? Bool, false); XCTAssertEqual(f["meets_rotation"] as? Bool, false)
        }
    }

    // MARK: beeldranden en privacy

    func testSaturationChannelAndEdgeLadderContainOnlyNumbers() {
        let rgba: [UInt8] = [255, 0, 0, 255, 128, 128, 128, 255, 200, 100, 100, 255, 0, 0, 0, 255]
        let s = ExtendedDiagnostics.saturationChannel(rgba: rgba, width: 4, height: 1)
        XCTAssertEqual(Array(s.pixels), [255, 0, 128, 0])                       // 127,5 -> 128 (afronden op even, zoals numpy.rint)
        var px = [UInt8](repeating: 0, count: 160 * 120)
        for y in 0..<120 { for x in 0..<160 { px[y * 160 + x] = UInt8(min(255, x * 255 / 159)) } }
        let g = GrayImage(width: 160, height: 120, pixels: px)
        let lad = ExtendedDiagnostics.edgeLadder(gray: g, saturation: g, corners: [Pixel(40, 30), Pixel(120, 30), Pixel(120, 90), Pixel(40, 90)])
        let sides = lad["sides"] as! [String: Any]
        XCTAssertEqual(Set(sides.keys), Set(["TOP", "RIGHT", "BOTTOM", "LEFT"]))
        let top = sides["TOP"] as! [String: Any]
        XCTAssertNotNil(top["offsets_px"]); XCTAssertNotNil(top["strength_gray"]); XCTAssertNotNil(top["strength_saturation"])
        assertNoForbiddenKeys(lad, "ladder")
    }

    private func assertNoForbiddenKeys(_ o: Any, _ path: String) {
        let forbidden = ["image", "photo", "pointcloud", "point_cloud", "latitude", "longitude", "gps", "location", "pose", "points_xyz"]
        if let d = o as? [String: Any] {
            for (k, v) in d {
                XCTAssertFalse(forbidden.contains { k.lowercased().contains($0) }, "verboden sleutel: \(path)/\(k)")
                assertNoForbiddenKeys(v, path + "/" + k)
            }
        } else if let a = o as? [Any] { for (i, v) in a.enumerated() { assertNoForbiddenKeys(v, "\(path)[\(i)]") } }
    }

    func testExtendedBlockHasNoForbiddenKeysAndIsDeterministic() {
        var rec = SceneSpec(); rec.recess = 0.06
        let (view, corners) = scene(rec, pos: Vec3(1.6, 1.6, 3.0), supports: 2)
        let r = measureDepthView(view, corners: corners, cfg: cfg, seed: 1)
        let a = ExtendedDiagnostics.compute(view: view, corners: corners, result: r, cfg: cfg, seed: 1, contourStatus: "USER_CONFIRMED")
        let b = ExtendedDiagnostics.compute(view: view, corners: corners, result: r, cfg: cfg, seed: 1, contourStatus: "USER_CONFIRMED")
        assertNoForbiddenKeys(a, "ext")
        let da = try! JSONSerialization.data(withJSONObject: jsonSafe(a), options: [.sortedKeys]), db = try! JSONSerialization.data(withJSONObject: jsonSafe(b), options: [.sortedKeys])
        XCTAssertEqual(da, db)
        XCTAssertLessThan(da.count, 150_000)
    }
}
