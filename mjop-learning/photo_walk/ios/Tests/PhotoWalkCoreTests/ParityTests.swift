import XCTest
@testable import PhotoWalkCore

/// Controleert dat de Swift-kern dezelfde uitkomsten geeft als de Python-kern op de gedeelde, ruisvrije fixtures.
/// STATUS: geschreven, nog niet uitgevoerd (geen Swift-toolchain in de ontwikkelomgeving).
final class ParityTests: XCTestCase {
    private func load() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }
    private func d(_ x: Any?) -> Double { (x as! NSNumber).doubleValue }
    private func px(_ a: Any?) -> Pixel { let v = a as! [Any]; return Pixel(d(v[0]), d(v[1])) }
    private func intrinsics(_ c: [String: Any]) -> Intrinsics {
        let i = c["intrinsics"] as! [String: Any]
        return Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
    }
    private func pose(_ c: [String: Any]) -> Pose { Pose(rowMajor: (c["pose_row_major"] as! [Any]).map { d($0) }) }

    func testProjectAndUnproject() throws {
        let c = try load(), tol = d((c["tolerance"] as! [String: Any])["geometry_m"])
        let p = pose(c), k = intrinsics(c)
        let pr = c["project"] as! [String: Any]
        let worlds = pr["world"] as! [[Double]], expect = pr["expect"] as! [[Double]]
        for (w, e) in zip(worlds, expect) {
            let (pix, z) = project(pose: p, intr: k, world: Vec3(w[0], w[1], w[2]))
            XCTAssertEqual(pix.u, e[0], accuracy: 1e-4); XCTAssertEqual(pix.v, e[1], accuracy: 1e-4); XCTAssertEqual(z, e[2], accuracy: tol * 10)
        }
        let u = c["unproject"] as! [String: Any]
        let X = unprojectDepth(pose: p, intr: k, pixel: px(u["pixel"]), depthZ: d(u["depth_z"]))
        let e = u["expect"] as! [Double]
        XCTAssertEqual(X.x, e[0], accuracy: tol); XCTAssertEqual(X.y, e[1], accuracy: tol); XCTAssertEqual(X.z, e[2], accuracy: tol)
    }

    func testLevelAMatchesPython() throws {
        let c = try load(), a = c["level_a"] as! [String: Any]
        let tol = d((c["tolerance"] as! [String: Any])["level_a_m"])
        let vals = (a["depth"] as! [Any]).map { Float(d($0)) }
        let depth = DepthMap(width: Int(d(a["depth_width"])), height: Int(d(a["depth_height"])), values: vals.map { $0 == 0 ? Float.nan : $0 })
        let view = ViewInput(frameId: "PAR", intrinsics: intrinsics(c), pose: pose(c), trackingNormal: true, depth: depth)
        let r = measureDepthView(view, corners: (a["corners_px"] as! [Any]).map(px), seed: 1)
        XCTAssertEqual(r.ok, a["expect_ok"] as? Bool)
        XCTAssertEqual(try XCTUnwrap(r.width), d(a["expect_width_m"]), accuracy: tol)
        XCTAssertEqual(try XCTUnwrap(r.height), d(a["expect_height_m"]), accuracy: tol)
        XCTAssertEqual(r.flags.map { $0.code }.sorted(), a["expect_flags"] as! [String])
    }

    /// LiDAR-v2: terugliggend kozijn, meerdere dieptekaders en een verspringende gevel; zelfde uitkomsten als de Python-kern op ruisvrije scènes.
    func testLevelAV2MatchesPython() throws {
        let c = try load()
        let tol = d((c["tolerance"] as! [String: Any])["level_a_m"])
        var seen = 0
        for case let cs as [String: Any] in c["level_a_v2"] as! [Any] {
            let name = cs["name"] as! String
            let dw = Int(d(cs["depth_width"])), dh = Int(d(cs["depth_height"]))
            func depthOf(_ e: [String: Any]) -> DepthMap { DepthMap(width: dw, height: dh, values: (e["depth"] as! [Any]).map { Float(d($0)) == 0 ? Float.nan : Float(d($0)) }) }
            func poseOf(_ e: [String: Any]) -> Pose { Pose(rowMajor: (e["pose_row_major"] as! [Any]).map { d($0) }) }
            let intr = intrinsics(c)
            let cap = cs["capture"] as! [String: Any]
            let sups = (cs["supports"] as! [[String: Any]]).enumerated().map { ViewInput(frameId: "S\($0.offset)", intrinsics: intr, pose: poseOf($0.element), trackingNormal: true, depth: depthOf($0.element)) }
            let view = ViewInput(frameId: "CAP", intrinsics: intr, pose: poseOf(cap), trackingNormal: true, depth: depthOf(cap), supports: sups)
            let r = measureDepthView(view, corners: (cs["corners_px"] as! [Any]).map(px), seed: 1)
            XCTAssertEqual(r.ok, cs["expect_ok"] as? Bool, name)
            XCTAssertEqual(r.scaleMethod, cs["expect_scale_method"] as? String, name)
            XCTAssertEqual(r.independentFrames, Int(d(cs["expect_independent_frames"])), name)
            XCTAssertEqual(r.flags.filter { $0.severity == .BLOCKING }.map { $0.code }.sorted(), cs["expect_blocking"] as! [String], name)
            if let rep = cs["expect_representative"] as? Bool { XCTAssertEqual((r.diag["facade_assessment"] as? [String: Any])?["representative"] as? Bool, rep, name) }
            if cs["expect_ok"] as? Bool == true {
                XCTAssertEqual(try XCTUnwrap(r.width), d(cs["expect_width_m"]), accuracy: tol, name)
                XCTAssertEqual(try XCTUnwrap(r.height), d(cs["expect_height_m"]), accuracy: tol, name)
                XCTAssertEqual((r.diag["frame_plane"] as? [String: Any])?["final_mode"] as? String, cs["expect_frame_mode"] as? String, name)
            } else { XCTAssertNil(r.width, name) }
            seen += 1
        }
        XCTAssertEqual(seen, 6)
    }

    /// Puntenwolk-niveau: dezelfde vlakgates als Python (lokale ruis, conflicterende vlakken, zijdeverdeling, omvang) op gesimuleerde ringpunten.
    func testFacadePointCasesMatchPython() throws {
        let c = try load()
        var seen = 0
        for case let cs as [String: Any] in c["facade_point_cases"] as! [Any] {
            let name = cs["name"] as! String
            let flat = (cs["points"] as! [Any]).map { d($0) }
            var pts = PointSet()
            for i in stride(from: 0, to: flat.count, by: 3) { pts.X.append(Vec3(flat[i], flat[i + 1], flat[i + 2])) }
            pts.side = (cs["sides"] as! [Any]).map { Int(d($0)) }
            pts.kind = [Int](repeating: 1, count: pts.X.count)
            let cam = ViewInput(frameId: "CAP", intrinsics: intrinsics(c), pose: Pose(rows: [Vec3(1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, -1)], t: Vec3(0, 0, 1.262)), trackingNormal: true, depth: nil)
            let an = analyzePoints(capture: cam, pts, cfg: Config(), seed: 3, quadDiagPx: d(cs["quad_diag_px"]))
            XCTAssertEqual(an.facade != nil, cs["expect_facade"] as? Bool, name)
            XCTAssertEqual(an.flags.map { $0.code }.sorted(), cs["expect_codes"] as! [String], name)
            XCTAssertEqual(an.assessment["representative"] as? Bool, cs["expect_representative"] as? Bool, name)
            if let cov = cs["expect_covered"] as? [Bool] { XCTAssertEqual((an.assessment["sides"] as? [String: Any])?["covered"] as? [Bool], cov, name) }
            seen += 1
        }
        XCTAssertEqual(seen, 6)
    }

    func testLevelCMatchesPython() throws {
        let c = try load(), l = c["level_c"] as! [String: Any]
        let tol = d((c["tolerance"] as! [String: Any])["level_c_m"])
        let view = ViewInput(frameId: "PARC", intrinsics: intrinsics(c), pose: pose(c), trackingNormal: true, depth: nil)
        let ref = ReferenceMeasure(referenceId: "PAR-R", p1: px(l["p1_px"]), p2: px(l["p2_px"]), distanceM: d(l["distance_m"]), distanceSigmaM: 0.005, planeId: "P")
        let r = measureWithReference(view: view, target: (l["target_px"] as! [Any]).map(px), ref: ref, anchor: (l["anchor_px"] as! [Any]).map(px), seed: 1)
        XCTAssertTrue(r.ok)
        XCTAssertEqual(try XCTUnwrap(r.width), d(l["expect_width_m"]), accuracy: tol)
        XCTAssertEqual(try XCTUnwrap(r.height), d(l["expect_height_m"]), accuracy: tol)
    }

    func testAreaRulesAndRounding() throws {
        for case let row as [String: Any] in try load()["area"] as! [Any] {
            let w = roundedMillimeters(d(row["width_m"])), h = roundedMillimeters(d(row["height_m"]))
            XCTAssertEqual(w, Decimal(string: row["expect_width"] as! String)!)
            XCTAssertEqual(h, Decimal(string: row["expect_height"] as! String)!)
            XCTAssertEqual(grossAreaM2(width: w, height: h), Decimal(string: row["expect_area"] as! String)!)
        }
    }

    func testFlagInstructionsMatchPython() throws {
        let py = try load()["flag_instructions"] as! [String: String]
        for (code, (_, text)) in Flags.table { XCTAssertEqual(py[code], text, code) }
    }

    func testWrongCornerOrderAndTrackingLossGiveNoValue() throws {
        let c = try load(), a = c["level_a"] as! [String: Any]
        let depth = DepthMap(width: 64, height: 48, values: (a["depth"] as! [Any]).map { Float(d($0)) })
        var corners = (a["corners_px"] as! [Any]).map(px)
        var view = ViewInput(frameId: "X", intrinsics: intrinsics(c), pose: pose(c), trackingNormal: false, depth: depth)
        XCTAssertNil(measureDepthView(view, corners: corners).width)
        view.trackingNormal = true
        corners.swapAt(2, 3)
        let r = measureDepthView(view, corners: corners)
        XCTAssertNil(r.width); XCTAssertTrue(r.flags.contains { $0.code == "CORNER_ORDER_INVALID" })
    }
}

/// Workflow-/robuustheidstests zonder sensoren (zelfde fixture): geen LiDAR, onvoldoende diepte, referentie-terugval, export-invarianten.
final class WorkflowTests: XCTestCase {
    private func fixture() throws -> (ViewInput, [Pixel], [Pixel], Intrinsics, Pose) {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        let c = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        func d(_ x: Any?) -> Double { (x as! NSNumber).doubleValue }
        let i = c["intrinsics"] as! [String: Any], a = c["level_a"] as! [String: Any], l = c["level_c"] as! [String: Any]
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        let pose = Pose(rowMajor: (c["pose_row_major"] as! [Any]).map { d($0) })
        let target = (a["corners_px"] as! [[Double]]).map { Pixel($0[0], $0[1]) }
        let anchor = (l["anchor_px"] as! [[Double]]).map { Pixel($0[0], $0[1]) }
        let depth = DepthMap(width: 64, height: 48, values: (a["depth"] as! [Any]).map { Float(d($0)) == 0 ? Float.nan : Float(d($0)) })
        return (ViewInput(frameId: "F", intrinsics: intr, pose: pose, trackingNormal: true, depth: depth), target, anchor, intr, pose)
    }

    func testNoDepthGivesUnknownNotCrash() throws {
        var (v, target, _, _, _) = try fixture()
        v.depth = nil
        let r = measureDepthView(v, corners: target)
        XCTAssertNil(r.width); XCTAssertTrue(r.flags.contains { $0.code == "NO_DEPTH" })
        let o = makeObject(id: "P1", observations: [], result: r, viewCount: 1)
        XCTAssertEqual(o.status, .UNKNOWN); XCTAssertNil(o.areaM2); XCTAssertTrue(o.reviewRequired)
    }

    func testInsufficientDepthCoverageGivesUnknown() throws {
        var (v, target, _, _, _) = try fixture()
        v.depth = DepthMap(width: 64, height: 48, values: [Float](repeating: .nan, count: 64 * 48))
        let r = measureDepthView(v, corners: target)
        XCTAssertNil(r.width); XCTAssertTrue(r.flags.contains { $0.code == "DEPTH_COVERAGE_LOW" })
    }

    func testReferenceFallbackWithoutDepthGivesDerivedAndGrossArea() throws {
        var (v, target, anchor, _, _) = try fixture()
        v.depth = nil
        let ref = ReferenceMeasure(referenceId: "R", p1: anchor[0], p2: anchor[1], distanceM: 1.2, distanceSigmaM: 0.005, planeId: "P", kind: .measuredWithTool)
        let r = measureWithReference(view: v, target: target, ref: ref, anchor: anchor)
        XCTAssertTrue(r.ok)
        let o = makeObject(id: "P1", observations: [], result: r, viewCount: 1)
        XCTAssertEqual(o.status, .DERIVED)
        XCTAssertEqual(Decimal(string: o.areaM2 ?? "0"), Decimal(string: o.widthM!)! * Decimal(string: o.heightM!)!)   // bruto m2 = b x h, glas niet afgetrokken
        XCTAssertEqual(Double(o.widthM!)!, 1.2, accuracy: 0.005); XCTAssertEqual(Double(o.heightM!)!, 1.5, accuracy: 0.005)
    }

    func testReferenceOnWrongPlaneIsRejected() throws {
        var (v, target, anchor, _, _) = try fixture()
        v.depth = nil
        let ref = ReferenceMeasure(referenceId: "R", p1: anchor[0], p2: anchor[1], distanceM: 1.2, planeId: "P1", targetPlaneId: "P2")
        let r = measureWithReference(view: v, target: target, ref: ref)
        XCTAssertNil(r.width); XCTAssertTrue(r.flags.contains { $0.code == "REFERENCE_PLANE_MISMATCH" })
    }

    func testTrackingLossGivesNoValueAndInvariantsHold() throws {
        var (v, target, _, _, _) = try fixture()
        v.trackingNormal = false
        let o = makeObject(id: "P1", observations: [], result: measureDepthView(v, corners: target), viewCount: 1)
        XCTAssertEqual(o.status, .UNKNOWN)
        let j = o.json
        XCTAssertEqual(j["quantity_layer"] as? String, "PROVISIONAL"); XCTAssertEqual(j["approval_state"] as? String, "PENDING_HUMAN_APPROVAL")
        XCTAssertTrue(j["outer_width_m"] is NSNull); XCTAssertTrue(j["gross_area_m2"] is NSNull); XCTAssertTrue(j["measurement_uncertainty"] is NSNull)
    }

    func testPointsOutsideDepthMapDoNotCrash() throws {
        var (v, target, _, _, _) = try fixture()
        let ref = ReferenceMeasure(referenceId: "R", p1: Pixel(-50, -50), p2: Pixel(99999, 99999), distanceM: 1.0, planeId: "P")
        _ = measureWithReference(view: v, target: target, ref: ref)       // moet een resultaat (mogelijk UNKNOWN) geven, geen crash
        v.depth = DepthMap(width: 64, height: 48, values: [Float](repeating: 3, count: 64 * 48))
        _ = measureWithReference(view: v, target: target, ref: ref)
    }
}
