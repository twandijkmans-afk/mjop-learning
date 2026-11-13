import XCTest
@testable import MJOPEngine

final class FacadeStripTests: XCTestCase {
    /// Gevel van 20 × 6 m met vijf ramen van 1,2 × 1,5 m op x = 2, 6, 10, 14, 18 (midden) en een muur over de hele breedte.
    /// Foto 1 ziet 0–11,5 m, foto 2 ziet 9–20 m: het raam op x = 10 staat op beide. Elke foto heeft zijn eigen eenheid (breedte 1).
    func part(from x0: Double, to x1: Double, overlap: Int) -> FacadeStrip.Part {
        let w = x1 - x0
        func u(_ x: Double) -> Double { (x - x0) / w }
        func v(_ y: Double) -> Double { y / w }
        var els = [FacadePhotoElement(id: 100, type: .metselwerk, points: [[0, 0], [1, 0], [1, v(6)], [0, v(6)]], material: nil, confidence: "high", note: nil)]
        for (i, cx) in [2.0, 6, 10, 14, 18].enumerated() where cx - 0.6 >= x0 && cx + 0.6 <= x1 {
            els.append(FacadePhotoElement(id: i + 1, type: .kozijn_raam, points: [[u(cx - 0.6), v(2)], [u(cx + 0.6), v(2)], [u(cx + 0.6), v(3.5)], [u(cx - 0.6), v(3.5)]],
                                          material: nil, confidence: "high", note: nil))
        }
        els.append(FacadePhotoElement(id: 200, type: .dakgoot, points: [[0, 0], [1, 0]], material: nil, confidence: "high", note: nil))
        return FacadeStrip.Part(elements: els, overlap: overlap)
    }

    func testTwoPhotosGiveTheWholeFacadeOnce() throws {
        let r = try FacadeStrip.stitch([part(from: 0, to: 11.5, overlap: 0), part(from: 9, to: 20, overlap: 1)], totalWidthM: 20).get()
        let s = FacadePhoto.summary(r.elements, mpp: 1)
        XCTAssertEqual(s.raamkozijnen, 5, "het raam in de overlap telt één keer")
        XCTAssertEqual(r.duplicates, 1)
        XCTAssertEqual(try XCTUnwrap(s.metselwerkNetM2), 120 - 5 * 1.8, accuracy: 0.01)
        XCTAssertEqual(try XCTUnwrap(s.dakgootM1), 20, accuracy: 0.01)
        XCTAssertEqual(try XCTUnwrap(s.kozijnOppervlakM2), 9, accuracy: 0.01)
    }

    func testThreePhotos() throws {
        let r = try FacadeStrip.stitch([part(from: 0, to: 7.5, overlap: 0), part(from: 5, to: 15, overlap: 1), part(from: 13, to: 20, overlap: 1)], totalWidthM: 20).get()
        let s = FacadePhoto.summary(r.elements, mpp: 1)
        XCTAssertEqual(s.raamkozijnen, 5)
        XCTAssertEqual(try XCTUnwrap(s.metselwerkNetM2), 111, accuracy: 0.01)
    }

    func testWithoutOverlapThereIsNoMeasure() {
        XCTAssertEqual(FacadeStrip.stitch([part(from: 0, to: 11.5, overlap: 0), part(from: 9, to: 20, overlap: 0)], totalWidthM: 20), .failure(.noOverlap(part: 2)))
        XCTAssertEqual(FacadeStrip.stitch([part(from: 0, to: 11.5, overlap: 0), part(from: 9, to: 20, overlap: 9)], totalWidthM: 20), .failure(.mismatch(part: 2)))
    }
}
