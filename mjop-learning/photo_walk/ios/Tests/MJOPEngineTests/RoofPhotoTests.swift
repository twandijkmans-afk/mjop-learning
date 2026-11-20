import XCTest
@testable import MJOPEngine

final class RoofPhotoTests: XCTestCase {
    func box(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> [[Double]] { [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] }

    func testScaleFromTheMercatorFrame() throws {
        // 100 mercatormeter over 1000 pixels op 52° noorderbreedte: 0,1 × cos(52°) ≈ 0,0616 m per pixel.
        XCTAssertEqual(try XCTUnwrap(RoofPhoto.metersPerPixel(mercatorWidth: 100, pixelWidth: 1000, latitude: 52)), 0.0616, accuracy: 0.0002)
        XCTAssertNil(RoofPhoto.metersPerPixel(mercatorWidth: 0, pixelWidth: 1000, latitude: 52))
    }

    func testPromptAndSchemaOnlyAskRoofThings() throws {
        let p = RoofPhoto.prompt(width: 1600, height: 1200, outline: box(100, 100, 800, 600), metersPerPixel: 0.06)
        XCTAssertTrue(p.contains("- dakvlak_schuin (Schuin dakvlak): polygon"))
        XCTAssertTrue(p.contains("(900, 700)"), "de BAG-omtrek staat in de prompt")
        XCTAssertFalse(p.contains("kozijn_raam"))
        let props = try XCTUnwrap(RoofPhoto.schema["properties"] as? [String: Any])
        let els = try XCTUnwrap(((props["elements"] as? [String: Any])?["items"] as? [String: Any])?["properties"] as? [String: Any])
        XCTAssertEqual((els["type"] as? [String: Any])?["enum"] as? [String], RoofPhoto.types.map(\.rawValue))
        // De gevel vraagt geen dakvlakken.
        XCTAssertFalse(FacadePhoto.prompt(width: 100, height: 100).contains("dakvlak_plat"))
    }

    func testParseKeepsOnlyThisBuilding() throws {
        let json = """
        {"planes": [], "elements": [
          {"type": "dakvlak_schuin", "points": [{"x": 110, "y": 110}, {"x": 500, "y": 110}, {"x": 500, "y": 400}, {"x": 110, "y": 400}], "material": "pannen", "confidence": "high", "note": "", "plane": 1, "hidden_fraction": 0, "panes": 0, "opening_parts": 0},
          {"type": "dakkapel", "points": [{"x": 200, "y": 200}, {"x": 300, "y": 260}], "material": "", "confidence": "high", "note": "", "plane": 1, "hidden_fraction": 0, "panes": 0, "opening_parts": 0},
          {"type": "dakvlak_plat", "points": [{"x": 1200, "y": 100}, {"x": 1500, "y": 100}, {"x": 1500, "y": 400}], "material": "", "confidence": "high", "note": "buren", "plane": 1, "hidden_fraction": 0, "panes": 0, "opening_parts": 0},
          {"type": "kozijn_raam", "points": [{"x": 300, "y": 300}, {"x": 340, "y": 340}], "material": "", "confidence": "high", "note": "", "plane": 1, "hidden_fraction": 0, "panes": 0, "opening_parts": 0}],
         "defects": [{"type": "veroudering_dakbedekking", "point": {"x": 300, "y": 350}, "note": "pannen verschoven"}, {"type": "plasvorming", "point": {"x": 1300, "y": 200}, "note": "buren"}]}
        """
        let body: [String: Any] = ["content": [["type": "text", "text": json]], "stop_reason": "end_turn"]
        let data = try JSONSerialization.data(withJSONObject: body)
        let r = try RoofPhoto.parse(data, width: 1600, height: 1200, outline: box(100, 100, 800, 600), metersPerPixel: 0.06)
        XCTAssertEqual(r.recognition.elements.map(\.type), [.dakvlak_schuin, .dakkapel])
        XCTAssertEqual(r.outside, 1, "het dak van de buren telt niet mee")
        XCTAssertEqual(r.recognition.skipped, 1, "een kozijn hoort niet op een luchtfoto")
        XCTAssertEqual(r.recognition.defects.map(\.type), [.veroudering_dakbedekking])
    }

    func testSlopeFactorFrom3DBAG() throws {
        XCTAssertEqual(try XCTUnwrap(RoofPhoto.slopeFactor(projectedSchuinM2: 50, dakSchuin3DBAG: 61.56)), 1.2312, accuracy: 0.0001)
        XCTAssertNil(RoofPhoto.slopeFactor(projectedSchuinM2: 50, dakSchuin3DBAG: nil), "geen 3D BAG: onbekend, niet gokken")
        XCTAssertNil(RoofPhoto.slopeFactor(projectedSchuinM2: 50, dakSchuin3DBAG: 30), "kleiner dan van boven kan niet")
        XCTAssertNil(RoofPhoto.slopeFactor(projectedSchuinM2: 10, dakSchuin3DBAG: 60), "zes keer zo groot kan niet")
    }

    func testApplySlopeOnlyToSlopedFaces() throws {
        let metric = [FacadePhotoElement(id: 1, type: .dakvlak_schuin, points: box(0, 0, 10, 5), material: nil, confidence: "high", note: nil),
                      FacadePhotoElement(id: 2, type: .dakkapel, points: box(2, 1, 2, 1.5), material: nil, confidence: "high", note: nil)]
        let ms = ElementList.measures(metric: metric, relative: RoofPhoto.relativeBand)
        let sloped = RoofPhoto.applySlope(ms, factor: 1.2)
        XCTAssertEqual(try XCTUnwrap(sloped[0].areaM2), 60, accuracy: 0.001)
        XCTAssertGreaterThan(try XCTUnwrap(sloped[0].band), try XCTUnwrap(ms[0].band) * 1.2, "extra onzekerheid door de verdeling")
        XCTAssertEqual(sloped[1], ms[1], "het platte dak van de dakkapel verandert niet")
        XCTAssertNil(RoofPhoto.applySlope(ms, factor: nil)[0].areaM2)
    }

    func testFlatRoofCheck() {
        XCTAssertEqual(RoofPhoto.flatCheck(photoFlatM2: 6.5, bag: 6.3)?.differs, false)
        XCTAssertEqual(RoofPhoto.flatCheck(photoFlatM2: 9, bag: 6.3)?.differs, true)
        XCTAssertNil(RoofPhoto.flatCheck(photoFlatM2: nil, bag: 6.3))
    }

    // MARK: inspectieadvies

    func defect(_ t: FacadeDefectType, _ status: DefectStatus?, _ ernst: DefectSeverity?) -> FacadeDefect {
        var d = FacadeDefect(id: 1, type: t, point: [0, 0], note: nil); d.status = status; d.ernst = ernst; return d
    }

    func testInspectionRulesEachOnItsOwn() throws {
        let year = 2026
        let young = RoofInspection.Covering(key: "dak-plat", naam: "Plat dak", lastDone: 2020, cycle: 25)      // 24%
        let middle = RoofInspection.Covering(key: "dak-plat", naam: "Plat dak", lastDone: 2010, cycle: 25)     // 64%
        let old = RoofInspection.Covering(key: "dak-hellend", naam: "Pannen", lastDone: 1990, cycle: 40)       // 90%
        let unknown = RoofInspection.Covering(key: "dak-plat", naam: "Plat dak", lastDone: nil, cycle: 25)
        XCTAssertNil(RoofInspection.advice(confirmed: [], coverings: [young, unknown], year: year), "jong of onbekend: gewone cyclus")
        XCTAssertEqual(RoofInspection.advice(confirmed: [], coverings: [middle], year: year)?.year, 2028)
        XCTAssertEqual(RoofInspection.advice(confirmed: [], coverings: [old], year: year)?.year, 2026)
        XCTAssertEqual(RoofInspection.advice(confirmed: [defect(.plasvorming, .bevestigd, .gering)], coverings: [], year: year)?.year, 2027)
        XCTAssertEqual(RoofInspection.advice(confirmed: [defect(.plasvorming, .bevestigd, .serieus)], coverings: [middle], year: year)?.year, 2026, "het vroegste jaar wint")
        XCTAssertNil(RoofInspection.advice(confirmed: [defect(.plasvorming, .afgewezen, .ernstig), defect(.plasvorming, nil, nil)], coverings: [], year: year),
                     "afgewezen of niet beoordeeld telt niet")
        XCTAssertEqual(RoofInspection.advice(confirmed: [defect(.veroudering_dakbedekking, .bevestigd, .gering)], coverings: [middle], year: year)?.reasons.count, 2)
    }
}
