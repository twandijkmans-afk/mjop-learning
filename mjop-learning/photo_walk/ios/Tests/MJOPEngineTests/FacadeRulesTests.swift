import XCTest
@testable import MJOPEngine

final class FacadeRulesTests: XCTestCase {
    let els = [
        FacadePhotoElement(id: 1, type: .metselwerk, points: [[0, 0], [1000, 0], [1000, 600], [0, 600]], material: nil, confidence: "high", note: nil),
        FacadePhotoElement(id: 2, type: .kozijn_raam, points: [[100, 100], [300, 100], [300, 300], [100, 300]], material: "hout", confidence: "high", note: nil),
    ]

    func testDefectOnAFrameGoesToFramesAndPaint() {
        let d = FacadeDefect(id: 1, type: .afbladderende_verf, point: [150, 150], note: "verf bladdert")
        let h = DefectHints.byKey([(sideId: 1, photoWidth: 1000, elements: els, defects: [d])])
        XCTAssertEqual(h["kozijnen-onderhoud"]?.first?.element?.id, 2)
        XCTAssertEqual(h["schilderwerk-buiten"]?.count, 1)
        XCTAssertNil(h["gevel-metselwerk"])
    }

    func testDefectOnBrickwork() {
        let d = FacadeDefect(id: 1, type: .voegwerk, point: [600, 500], note: nil)
        XCTAssertEqual(Set(DefectHints.byKey([(sideId: 1, photoWidth: 1000, elements: els, defects: [d])]).keys), ["voegwerk", "gevel-metselwerk"])
    }

    func testLooseOtherDefectWithoutElementHasNoPost() {
        XCTAssertEqual(DefectHints.keys(for: FacadeDefect(id: 1, type: .overig, point: [0, 0], note: nil), on: nil), [])
    }

    func testCopyOnlyForSimilarWidths() {
        XCTAssertTrue(FacadeCopy.allowed(sourceWidthM: 8.49, targetWidthM: 9.2))
        XCTAssertFalse(FacadeCopy.allowed(sourceWidthM: 8.49, targetWidthM: 11.16))
    }
}
