import XCTest
@testable import PhotoWalkCore

/// Regressie: één vastgelegde foto is NOOIT MEASURED. Ondersteunende LiDAR-dieptekaders van één foto zijn geen aparte standpunten.
/// MEASURED vraagt >= 2 apart vastgelegde foto's met cameraposities >= Config.minBaselineM uit elkaar (bestaande drempel, niet versoepeld),
/// consistente metingen, een bevestigde buitencontour en geen afwaarderende codes. Referentiemaat (niveau C) blijft DERIVED.
/// Python-tegenhanger: python/tests/test_viewpoints.py. Alles SYNTHETISCH: rekenregels, geen nauwkeurigheid op echte gevels.
final class ViewpointTests: XCTestCase {
    private let cfg = Config()
    private let cam = Vec3(1.6, 1.6, 3.0)

    private func codes(_ o: MeasuredObject) -> Set<String> { Set(o.flags.map { $0.code }) }
    private func result(_ w: Double, _ h: Double, id: String) -> LevelResult {
        var r = LevelResult(level: .A, scaleMethod: "LIDAR_DEPTH_PLANE", viewIds: [id])
        r.width = w; r.height = h; r.sigmaW = 0.01; r.sigmaH = 0.01; r.sigmaArea = 0.02
        return r
    }
    private func capture(_ id: String, _ p: Vec3) -> Viewpoints.Capture { .init(keyframeId: id, position: p) }

    /// Zoals ScanStore.Measurer: combineren, dan makeObject met het aantal onafhankelijke foto's.
    private func object(_ items: [Viewpoints.ViewMeasurement], extra: [QualityFlag] = []) -> MeasuredObject {
        let c = Viewpoints.combineLevelA(items)!
        return makeObject(id: "PROV-1", observations: [], result: c.result, viewCount: c.viewCount, extraFlags: extra)
    }

    // 1 één foto + meerdere onafhankelijke LiDAR-kaders = ESTIMATED
    func testOnePhotoWithMultipleIndependentLidarFramesIsEstimated() {
        var s = SceneSpec(); s.recess = 0.06
        var v = Scene.render(s, pos: cam, id: "F000", seed: 1)
        for k in 0..<3 {
            let off = 0.06 * Double(k / 2 + 1) * (k % 2 == 0 ? 1 : -1)
            v.supports.append(Scene.render(s, pos: Vec3(cam.x + off, cam.y, cam.z), id: "F000-S\(k)", seed: 7 + UInt64(k) + 1))
        }
        let r = ContourGate.apply(measureDepthView(v, corners: Scene.corners(s, pos: cam), cfg: cfg, seed: 1), status: .USER_CONFIRMED)
        XCTAssertTrue(r.ok)
        XCTAssertEqual(r.scaleMethod, "LIDAR_DEPTH_MULTI_FRAME"); XCTAssertGreaterThanOrEqual(r.independentFrames, 2, "de kaders worden wel gebruikt")
        let c = Viewpoints.combineLevelA([.init(capture: capture("F000", cam), result: r)])!
        XCTAssertEqual(c.viewCount, 1, "ondersteunende kaders zijn geen extra standpunten")
        let o = makeObject(id: "PROV-1", observations: [], result: c.result, viewCount: c.viewCount)
        XCTAssertEqual(o.status, .ESTIMATED); XCTAssertTrue(codes(o).contains("SINGLE_VIEWPOINT"))
        XCTAssertEqual(Status.status(for: r, viewCount: 1), .ESTIMATED, "diagnose-export: één waarneming = één foto")
    }

    // 2 één foto + handmatig verbeterde hoeken = nooit MEASURED (ook niet met twee waarnemingen op dezelfde foto)
    func testOnePhotoWithManuallyCorrectedCornersIsNeverMeasured() {
        let fixed = [Flags.make("HUMAN_CORRECTED_CORNERS")]
        XCTAssertNotEqual(object([.init(capture: capture("F000", cam), result: result(1.2, 1.5, id: "F000"))], extra: fixed).status, .MEASURED)
        let twice = object([.init(capture: capture("F000", cam), result: result(1.2, 1.5, id: "F000")),
                            .init(capture: capture("F000", cam), result: result(1.201, 1.499, id: "F000"))], extra: fixed)
        XCTAssertEqual(twice.status, .ESTIMATED); XCTAssertTrue(codes(twice).contains("SINGLE_VIEWPOINT"))
    }

    // 3 twee apart vastgelegde, consistente foto's mogen MEASURED worden als al het andere klopt
    func testTwoSeparateConsistentPhotosCanBeMeasured() {
        let s = SceneSpec()
        let p2 = Vec3(2.4, 1.6, 3.0)
        let r1 = ContourGate.apply(measureDepthView(Scene.render(s, pos: cam, id: "F000", seed: 1), corners: Scene.corners(s, pos: cam), cfg: cfg, seed: 1), status: .USER_CONFIRMED)
        let r2 = ContourGate.apply(measureDepthView(Scene.render(s, pos: p2, id: "F001", seed: 2), corners: Scene.corners(s, pos: p2), cfg: cfg, seed: 1), status: .USER_CONFIRMED)
        XCTAssertTrue(r1.ok && r2.ok)
        let c = Viewpoints.combineLevelA([.init(capture: capture("F000", cam), result: r1), .init(capture: capture("F001", p2), result: r2)])!
        XCTAssertEqual(c.viewCount, 2)
        let o = makeObject(id: "PROV-1", observations: [], result: c.result, viewCount: c.viewCount)
        XCTAssertEqual(o.status, .MEASURED, "\(codes(o))"); XCTAssertFalse(codes(o).contains("SINGLE_VIEWPOINT"))
        // onbevestigde contour in één van beide: die waarneming telt niet mee -> één foto -> ESTIMATED
        let blocked = ContourGate.apply(r2, status: .UNVERIFIED)
        XCTAssertEqual(object([.init(capture: capture("F000", cam), result: r1), .init(capture: capture("F001", p2), result: blocked)]).status, .ESTIMATED)
    }

    // 4 twee foto's vanaf (vrijwel) hetzelfde standpunt = geen MEASURED
    func testTwoPhotosFromEffectivelyTheSameViewpointAreNotMeasured() {
        let near = Vec3(cam.x + cfg.minBaselineM * 0.5, cam.y, cam.z)
        let o = object([.init(capture: capture("F000", cam), result: result(1.2, 1.5, id: "F000")),
                        .init(capture: capture("F001", near), result: result(1.201, 1.499, id: "F001"))])
        XCTAssertEqual(o.status, .ESTIMATED); XCTAssertTrue(codes(o).contains("SINGLE_VIEWPOINT"))
    }

    // 5 tegenstrijdige standpunten = geen MEASURED (en geen maat)
    func testConflictingViewpointsAreNeverMeasured() {
        let o = object([.init(capture: capture("F000", cam), result: result(1.2, 1.5, id: "F000")),
                        .init(capture: capture("F001", Vec3(2.6, 1.6, 3.0)), result: result(1.5, 1.5, id: "F001"))])
        XCTAssertEqual(o.status, .UNKNOWN); XCTAssertNil(o.widthM); XCTAssertTrue(codes(o).contains("VIEWS_INCONSISTENT"))
    }

    // 6 de gevelopbouw (per foto) maakt nooit MEASURED, ook niet uit MEASURED-invoer; referentiemaat blijft DERIVED
    func testFacadeCompositionNeverUpgradesASinglePhotoToMeasured() {
        let pose = Pose(rows: [Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, 1)], t: Vec3(0, 1.5, 0))
        let intr = Intrinsics(fx: 1000, fy: 1000, cx: 600, cy: 350, width: 1200, height: 700)
        let t = SyntheticFacade.truth([SyntheticFacade.Window(outer: (200, 150, 420, 450), profile: 14)])
        let facade = [Pixel(100, 80), Pixel(1100, 80), Pixel(1100, 620), Pixel(100, 620)]
        let o = FacadeOpeningInput(id: "OBS-1", outerPx: t[0].outer, areaM2: Decimal(string: "0.660"), status: .MEASURED, planeN: Vec3(0, 0, 1), planeD: 5, panesPx: t[0].panes)
        let r = FacadeComposition.compose(openings: [o], pose: pose, intr: intr, facadePx: facade, facadePlane: (Vec3(0, 0, 1), 5), facadePlaneStatus: .MEASURED)
        for q in [r.facadeGross, r.openings, r.frameOuter, r.glass, r.closedFacadeNet, r.maintainableFrameSurface] { XCTAssertNotEqual(q.status, .MEASURED, q.basis) }
        XCTAssertEqual(r.facadeGross.status, .ESTIMATED); XCTAssertEqual(r.frameOuter.status, .ESTIMATED)
        XCTAssertEqual(FacadeComposition.singlePhoto(.DERIVED), .DERIVED); XCTAssertEqual(FacadeComposition.singlePhoto(.UNKNOWN), .UNKNOWN)
    }

    func testReferenceDistanceStaysDerived() {
        var c = LevelResult(level: .C, scaleMethod: "REFERENCE_DISTANCE", viewIds: ["F000"])
        c.width = 1.2; c.height = 1.5; c.sigmaW = 0.01; c.sigmaH = 0.01; c.sigmaArea = 0.02
        XCTAssertNil(Viewpoints.combineLevelA([.init(capture: capture("F000", cam), result: c)]), "niveau C loopt niet via de standpunttelling")
        XCTAssertEqual(makeObject(id: "P", observations: [], result: c, viewCount: 1).status, .DERIVED)
    }

    // pariteit met Python: telregel
    func testIndependentPhotoCountMatchesPython() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "facade_parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let vp = try XCTUnwrap(root["viewpoints"] as? [String: Any])
        let b = (vp["min_baseline_m"] as! NSNumber).doubleValue
        XCTAssertEqual(b, cfg.minBaselineM, "zelfde drempel in Swift en Python")
        let cases = vp["cases"] as! [[String: Any]]
        XCTAssertFalse(cases.isEmpty)
        for cs in cases {
            let caps = (cs["captures"] as! [[String: Any]]).map { c -> Viewpoints.Capture in
                let p = (c["position"] as! [Any]).map { ($0 as! NSNumber).doubleValue }
                return capture(c["keyframe_id"] as! String, Vec3(p[0], p[1], p[2]))
            }
            XCTAssertEqual(Viewpoints.independentPhotoCount(caps, minBaselineM: b), (cs["expected"] as! NSNumber).intValue, cs["name"] as! String)
        }
    }
}
