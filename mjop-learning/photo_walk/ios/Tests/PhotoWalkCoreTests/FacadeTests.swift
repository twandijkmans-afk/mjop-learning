import XCTest
@testable import PhotoWalkCore

/// Gevelopbouw (rollen, voorstel glas -> buitenkozijn, hoeveelheden) tegen de Python-referentie (facade_parity_cases.json).
/// Alles SYNTHETISCH: bewijst gelijke rekenregels in Swift en Python, niet de herkenning op echte gevels.
final class FacadeTests: XCTestCase {
    private func load() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "facade_parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }
    private func d(_ x: Any?) -> Double { (x as! NSNumber).doubleValue }
    private func px(_ a: Any) -> Pixel { let v = a as! [Any]; return Pixel(d(v[0]), d(v[1])) }
    private func poly(_ a: Any?) -> [Pixel] { (a as! [Any]).map(px) }
    private func assertPoly(_ a: [Pixel], _ b: [Pixel], _ tol: Double, _ msg: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(a.count, b.count, msg, file: file, line: line)
        for (p, q) in zip(a, b) {
            XCTAssertEqual(p.u, q.u, accuracy: tol, msg, file: file, line: line); XCTAssertEqual(p.v, q.v, accuracy: tol, msg, file: file, line: line)
        }
    }
    private func windows(_ c: [String: Any]) -> [SyntheticFacade.Window] {
        (c["windows"] as! [[String: Any]]).map { w in
            let o = (w["outer"] as! [Any]).map { Int(d($0)) }
            return SyntheticFacade.Window(outer: (o[0], o[1], o[2], o[3]), profile: Int(d(w["profile"])), mullions: Int(d(w["mullions"])), transom: (w["transom"] as? Bool) ?? false)
        }
    }
    private func image(_ c: [String: Any]) -> GrayImage {
        let im = c["image"] as! [String: Any]
        return SyntheticFacade.gray(width: Int(d(im["width"])), height: Int(d(im["height"])), windows: windows(c))
    }

    func testSyntheticImageIdenticalToPython() throws {
        let c = try load()
        XCTAssertEqual(SyntheticFacade.checksum(image(c)), Int64(d(c["image_checksum"])))
    }

    func testOrganizerMatchesPython() throws {
        let c = try load()
        let im = c["image"] as! [String: Any]
        for cs in c["organizer"] as! [[String: Any]] {
            let name = cs["name"] as! String
            let cands = (cs["candidates"] as! [[String: Any]]).map { QuadCandidate(corners: poly($0["corners"]), detector: $0["detector"] as! String, score: d($0["score"])) }
            let (groups, ignored) = ContourOrganizer.organize(cands, imageWidth: d(im["width"]), imageHeight: d(im["height"]))
            let expected = cs["groups"] as! [[String: Any]]
            XCTAssertEqual(groups.count, expected.count, name)
            for (g, e) in zip(groups, expected) {
                assertPoly(g.outer, poly(e["outer"]), 1e-9, name)
                XCTAssertEqual(g.outerDetected, e["outer_detected"] as! Bool, name)
                XCTAssertEqual(g.evidence.rawValue, e["evidence"] as! String, name)
                XCTAssertEqual(g.status.rawValue, e["status"] as! String, name)
                XCTAssertEqual(g.detector, e["detector"] as! String, name)
                XCTAssertEqual(g.score, d(e["score"]), accuracy: 1e-12, name)
                let ep = (e["panes"] as! [Any]).map(poly)
                XCTAssertEqual(g.panes.count, ep.count, name)
                for (p, q) in zip(g.panes, ep) { assertPoly(p, q, 1e-9, name) }
                if let cov = e["glass_coverage"] as? NSNumber { XCTAssertEqual(g.glassCoverage ?? -1, cov.doubleValue, accuracy: 1e-6, name) } else { XCTAssertNil(g.glassCoverage, name) }
            }
            let er = (cs["ignored"] as! [[String: Any]]).map { "\($0["reason"] as! String)|\($0["detector"] as! String)" }
            XCTAssertEqual(ignored.map { "\($0.reason)|\($0.detector)" }.sorted(), er.sorted(), name)
        }
    }

    func testGlassPaneIsNeverAutomaticallyAFrame() {
        let w = [SyntheticFacade.Window(outer: (200, 150, 420, 450), profile: 14)]
        let t = SyntheticFacade.truth(w)
        let (g, _) = ContourOrganizer.organize([QuadCandidate(corners: t[0].panes[0], detector: "VN", score: 0.9)], imageWidth: 1200, imageHeight: 700)
        XCTAssertEqual(g.map { $0.status }, [.UNVERIFIED])
        XCTAssertTrue(g[0].status.blocksArea)
        XCTAssertTrue(OuterContourStatus.PROPOSED_EXPANSION.blocksArea)
        XCTAssertFalse(OuterContourStatus.USER_CONFIRMED.blocksArea || OuterContourStatus.LEGACY.blocksArea || OuterContourStatus.MANUAL.blocksArea)
    }

    func testExpansionMatchesPython() throws {
        let c = try load()
        let img = image(c)
        for cs in c["expansion"] as! [[String: Any]] {
            let name = cs["name"] as! String
            let r = OuterFrameSearch.proposeOuter(img, quad: poly(cs["quad"]))
            if let e = cs["result"] as? [String: Any] {
                let rr = try XCTUnwrap(r, name)
                assertPoly(rr.quad, poly(e["quad"]), 1e-4, name)
                XCTAssertEqual(rr.offsetsPx, (e["offsets_px"] as! [Any]).map { d($0) }, name)
            } else {
                XCTAssertNil(r, name)
            }
        }
    }

    private func dec(_ s: Any?) -> Decimal? { (s as? String).flatMap { Decimal(string: $0) } }

    func testCompositionMatchesPython() throws {
        let c = try load()
        let comp = c["compose"] as! [String: Any]
        let cam = comp["camera"] as! [String: Any]
        let rows = (cam["rows"] as! [[Any]]).map { r in Vec3(d(r[0]), d(r[1]), d(r[2])) }
        let t = (cam["t"] as! [Any]).map { d($0) }
        let pose = Pose(rows: rows, t: Vec3(t[0], t[1], t[2]))
        let intr = Intrinsics(fx: d(cam["fx"]), fy: d(cam["fy"]), cx: d(cam["cx"]), cy: d(cam["cy"]), width: 1200, height: 700)
        let fp = comp["facade_plane"] as! [String: Any]
        let fn = (fp["n"] as! [Any]).map { d($0) }
        let plane = (n: Vec3(fn[0], fn[1], fn[2]), d: d(fp["d"]))
        for cs in comp["cases"] as! [[String: Any]] {
            let name = cs["name"] as! String
            let withScale = cs["with_scale"] as! Bool, withPlane = cs["with_facade_plane"] as! Bool
            let openings = (cs["openings"] as! [[String: Any]]).map { o -> FacadeOpeningInput in
                let n = (o["plane_n"] as? [Any]).map { v in Vec3(d(v[0]), d(v[1]), d(v[2])) }
                return FacadeOpeningInput(id: o["id"] as! String, outerPx: poly(o["outer_px"]), areaM2: dec(o["area_m2"]),
                                          status: DimensionStatus(rawValue: o["status"] as! String)!, planeN: n, planeD: (o["plane_d"] as? NSNumber)?.doubleValue,
                                          panesPx: (o["panes_px"] as! [Any]).map(poly))
            }
            let r = FacadeComposition.compose(openings: openings, pose: withScale ? pose : nil, intr: withScale ? intr : nil, facadePx: poly(comp["facade_px"]),
                                              facadePlane: withPlane ? plane : nil, facadePlaneStatus: withPlane ? .ESTIMATED : .UNKNOWN)
            let e = cs["expected"] as! [String: Any]
            let got: [String: FacadeQuantity] = ["facade_gross": r.facadeGross, "openings": r.openings, "frame_outer": r.frameOuter, "glass": r.glass,
                                                 "closed_facade_net": r.closedFacadeNet, "maintainable_frame_surface": r.maintainableFrameSurface]
            for (k, q) in got {
                let eq = e[k] as! [String: Any]
                XCTAssertEqual(q.status.rawValue, eq["status"] as! String, "\(name).\(k)")
                XCTAssertEqual(q.missing, eq["missing"] as! [String], "\(name).\(k)")
                XCTAssertEqual(q.basis, eq["basis"] as! String, "\(name).\(k)")
                if let ev = dec(eq["value_m2"]) {
                    let v = try XCTUnwrap(q.valueM2, "\(name).\(k)")
                    XCTAssertEqual(NSDecimalNumber(decimal: v).doubleValue, NSDecimalNumber(decimal: ev).doubleValue, accuracy: 1e-9, "\(name).\(k)")
                } else { XCTAssertNil(q.valueM2, "\(name).\(k)") }
            }
            XCTAssertEqual(r.flags, e["flags"] as! [String], name)
            XCTAssertNil(r.maintainableFrameSurface.valueM2, "onderhoudsoppervlak wordt nooit afgeleid")
        }
    }

    func testPlausibilityIsOnlyAdvisory() {
        XCTAssertEqual(FacadeComposition.plausibility3DBAG(facadeGrossTotalM2: Decimal(120), buitenmuurM2: 114.02), ["FACADE_GROSS_EXCEEDS_3DBAG_WALL_AREA"])
        XCTAssertEqual(FacadeComposition.plausibility3DBAG(facadeGrossTotalM2: Decimal(60), buitenmuurM2: 114.02), [])
        XCTAssertEqual(FacadeComposition.plausibility3DBAG(facadeGrossTotalM2: nil, buitenmuurM2: 114.02), [])
    }

    /// Synthetische diepte: verticale gevel op 5 m met een 8 cm terugliggend kozijn; het gevelvlak komt uit de diepte BUITEN het kozijn.
    func testFacadePlaneFitIgnoresOpenings() {
        let intr = Intrinsics(fx: 1000, fy: 1000, cx: 600, cy: 350, width: 1200, height: 700)
        let pose = Pose(rows: [Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, 1)], t: Vec3(0, 1.5, 0))
        let dw = 120, dh = 70
        let opening = [Pixel(400, 200), Pixel(800, 200), Pixel(800, 500), Pixel(400, 500)]
        var vals = [Float](repeating: 5.0, count: dw * dh)
        for i in 0..<dh { for j in 0..<dw {
            let p = Pixel((Double(j) + 0.5) * 10, (Double(i) + 0.5) * 10)
            if inConvexPolygon(p, opening) { vals[i * dw + j] = 5.08 }
        } }
        let view = ViewInput(frameId: "F", intrinsics: intr, pose: pose, trackingNormal: true, depth: DepthMap(width: dw, height: dh, values: vals))
        let facade = [Pixel(100, 80), Pixel(1100, 80), Pixel(1100, 620), Pixel(100, 620)]
        let fit = FacadeComposition.fitFacadePlane(view: view, polygon: facade, exclude: [opening], seed: 7)
        XCTAssertNotNil(fit)
        if let f = fit {
            XCTAssertEqual(abs(f.n.z), 1, accuracy: 1e-6)
            XCTAssertEqual(abs(f.d), 5, accuracy: 1e-6)
            let a = FacadeComposition.planarPolygonAreaM2(facade, pose: pose, intr: intr, n: f.n, d: f.d)
            XCTAssertEqual(a ?? 0, 13.5, accuracy: 1e-6)
        }
        let noDepth = ViewInput(frameId: "F", intrinsics: intr, pose: pose, trackingNormal: true, depth: nil)
        XCTAssertNil(FacadeComposition.fitFacadePlane(view: noDepth, polygon: facade, exclude: [], seed: 7), "zonder diepte geen gevelvlak")
    }
}
