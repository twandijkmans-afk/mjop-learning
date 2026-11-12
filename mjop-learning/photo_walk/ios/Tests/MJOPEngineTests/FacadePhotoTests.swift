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
}
