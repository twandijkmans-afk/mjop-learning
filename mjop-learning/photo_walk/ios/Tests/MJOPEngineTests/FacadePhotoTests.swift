import Foundation
import XCTest
@testable import MJOPEngine

final class FacadePhotoTests: XCTestCase {
    /// Een antwoord zoals de Messages API het geeft, met één ongeldig element (te weinig punten) dat moet worden overgeslagen.
    func response(_ elements: String) -> Data {
        let text = "{\"elements\": [\(elements)]}"
        let o: [String: Any] = ["stop_reason": "end_turn", "content": [["type": "text", "text": text]]]
        return try! JSONSerialization.data(withJSONObject: o)
    }

    func testParsesAndComputesQuantitiesWithFixedRules() throws {
        let data = response("""
        {"type": "metselwerk", "points": [{"x": 0, "y": 0}, {"x": 1000, "y": 0}, {"x": 1000, "y": 600}, {"x": 0, "y": 600}], "material": "baksteen", "confidence": "high", "note": ""},
        {"type": "kozijn_raam", "points": [{"x": 100, "y": 100}, {"x": 300, "y": 300}], "material": "hout", "confidence": "high", "note": ""},
        {"type": "kozijn_deur", "points": [{"x": 500, "y": 300}, {"x": 600, "y": 600}], "material": "", "confidence": "medium", "note": ""},
        {"type": "hwa", "points": [{"x": 980, "y": 0}, {"x": 980, "y": 600}], "material": "zink", "confidence": "high", "note": ""},
        {"type": "dakgoot", "points": [{"x": 10, "y": 10}], "material": "", "confidence": "low", "note": ""}
        """)
        let (els, skipped) = try FacadePhoto.parseResponse(data, width: 1000, height: 600)
        XCTAssertEqual(els.count, 4)
        XCTAssertEqual(skipped, 1, "een lijn met één punt wordt overgeslagen, niet gerepareerd")
        XCTAssertNil(els.first { $0.type == .kozijn_raam }?.note)

        // Gevel 10 m breed over 1000 pixels: 1 cm per pixel.
        let ref = try XCTUnwrap(FacadePhoto.defaultReference(els))
        let mpp = try XCTUnwrap(FacadePhoto.metersPerPixel(facadeWidthM: 10, leftX: ref.left, rightX: ref.right))
        XCTAssertEqual(mpp, 0.01, accuracy: 1e-9)
        let s = FacadePhoto.summary(els, mpp: mpp)
        // 10 × 6 = 60 m² bruto, min raam 2 × 2 = 4 m² en deur 1 × 3 = 3 m²
        XCTAssertEqual(s.metselwerkNetM2, 53)
        XCTAssertEqual(s.raamkozijnen, 1)
        XCTAssertEqual(s.deurkozijnen, 1)
        XCTAssertEqual(s.kozijnOppervlakM2, 7)
        XCTAssertEqual(s.hwaM1, 6)
        XCTAssertEqual(s.dakgootM1, 0)
    }

    func testWithoutScaleEverythingIsUnknown() throws {
        let data = response("""
        {"type": "metselwerk", "points": [{"x": 0, "y": 0}, {"x": 1000, "y": 0}, {"x": 1000, "y": 600}], "material": "", "confidence": "high", "note": ""}
        """)
        let (els, _) = try FacadePhoto.parseResponse(data, width: 1000, height: 600)
        XCTAssertNil(FacadePhoto.summary(els, mpp: nil).metselwerkNetM2, "zonder maat geen oppervlak, nooit 0")
    }

    func testRefusalAndGarbage() {
        let refusal = try! JSONSerialization.data(withJSONObject: ["stop_reason": "refusal", "content": []] as [String: Any])
        XCTAssertThrowsError(try FacadePhoto.parseResponse(refusal, width: 10, height: 10)) { XCTAssertEqual($0 as? FacadeError, .refused) }
        XCTAssertThrowsError(try FacadePhoto.parseResponse(Data("geen json".utf8), width: 10, height: 10))
    }

    func testFacadeSidesFromTheRealFootprint() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "bag_pand_singelstraat8", withExtension: "json", subdirectory: "Fixtures"))
        let p = try XCTUnwrap(BuildingLookup.pickPand(try Data(contentsOf: url), lon: 5.06698347, lat: 52.33004363))
        XCTAssertEqual(p.sides.count, 6)
        XCTAssertEqual(p.sides[0].lengthM, 8.49, accuracy: 0.01)
        XCTAssertEqual(p.sides[0].facing, "noord")
        XCTAssertEqual(p.sides[4].lengthM, 11.16, accuracy: 0.01)
        XCTAssertEqual(p.sides[4].facing, "zuid")
    }

    func el(_ id: Int, _ t: FacadeElementType, _ x1: Double, _ y1: Double, _ x2: Double, _ y2: Double, conf: String = "high", hidden: Double? = nil) -> FacadePhotoElement {
        FacadePhotoElement(id: id, type: t, points: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], material: nil, confidence: conf, note: nil, hiddenFraction: hidden)
    }

    func testDuplicateWindowsAreMergedWithProvenance() {
        let d = FacadePhoto.dedupe([el(1, .kozijn_raam, 100, 100, 200, 250, conf: "medium"), el(2, .kozijn_raam, 105, 102, 203, 248), el(3, .kozijn_raam, 400, 100, 500, 250)])
        XCTAssertEqual(d.elements.map(\.id), [2, 3], "het zekerste element blijft")
        XCTAssertEqual(d.elements[0].mergedFrom, [1])
        XCTAssertEqual(d.merged, 1)
        XCTAssertTrue(d.conflicts.isEmpty)
    }

    func testNeighboursAndHalfOverlapStaySeparate() {
        let d = FacadePhoto.dedupe([el(1, .kozijn_raam, 0, 0, 100, 100), el(2, .kozijn_raam, 100, 0, 200, 100), el(3, .kozijn_raam, 150, 0, 250, 100)])
        XCTAssertEqual(d.elements.count, 3, "naast elkaar of maar half over elkaar: geen dubbel")
        XCTAssertEqual(FacadePhoto.overlap(el(1, .kozijn_raam, 0, 0, 10, 10).points, el(2, .kozijn_raam, 1, 1, 11, 11).points), 0.81, accuracy: 1e-9)
    }

    func testDifferentTypesOverlappingAreAConflictNotAMerge() {
        let d = FacadePhoto.dedupe([el(1, .kozijn_raam, 0, 0, 100, 200), el(2, .kozijn_deur, 5, 5, 100, 200)])
        XCTAssertEqual(d.elements.count, 2)
        XCTAssertEqual(d.conflicts, [[1, 2]])
        XCTAssertEqual(d.merged, 0)
    }

    func testWallsAndLinesAreNotDeduplicated() {
        let wall = FacadePhotoElement(id: 1, type: .metselwerk, points: [[0, 0], [100, 0], [100, 100], [0, 100]], material: nil, confidence: "high", note: nil)
        var wall2 = wall; wall2.id = 2
        let pipe = FacadePhotoElement(id: 3, type: .hwa, points: [[5, 0], [5, 100]], material: nil, confidence: "high", note: nil)
        var pipe2 = pipe; pipe2.id = 4
        XCTAssertEqual(FacadePhoto.dedupe([wall, wall2, pipe, pipe2]).elements.count, 4)
    }

    func testTotalsPerTypeIncludeFascia() {
        let els = [
            FacadePhotoElement(id: 1, type: .boeiboord, points: [[0, 10], [1000, 10]], material: "hout", confidence: "high", note: nil),
            FacadePhotoElement(id: 2, type: .latei, points: [[100, 95], [300, 95]], material: "staal", confidence: "high", note: nil),
            FacadePhotoElement(id: 3, type: .brievenbus, points: [[500, 300], [540, 300], [540, 320], [500, 320]], material: nil, confidence: "medium", note: nil),
        ]
        let t = FacadePhoto.totals(els, mpp: 0.01)
        XCTAssertEqual(t.first { $0.type == .boeiboord }?.lengthM, 10)
        XCTAssertEqual(t.first { $0.type == .latei }?.lengthM, 2)
        XCTAssertEqual(t.first { $0.type == .brievenbus }?.count, 1)
        XCTAssertNil(FacadePhoto.totals(els, mpp: nil).first { $0.type == .boeiboord }?.lengthM, "zonder maat geen lengte")
        XCTAssertFalse(FacadeElementType.dakbedekking.isWall, "dakbedekking is geen gevelvlak")
    }
}
