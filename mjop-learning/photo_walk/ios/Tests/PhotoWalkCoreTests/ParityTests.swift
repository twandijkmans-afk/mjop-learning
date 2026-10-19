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
