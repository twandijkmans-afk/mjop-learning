import XCTest
@testable import MJOPEngine

final class EditorAndQualityTests: XCTestCase {
    func box(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> [[Double]] { [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] }
    func el(_ id: Int, _ t: FacadeElementType, _ pts: [[Double]]) -> FacadePhotoElement {
        FacadePhotoElement(id: id, type: t, points: pts, material: "hout", confidence: "high", note: nil)
    }

    // MARK: gelijk maken en kopiëren

    func testMatchSizeWithoutPlaneIsInPixels() throws {
        var els = [el(1, .kozijn_raam, box(100, 100, 120, 150)), el(2, .kozijn_raam, box(400, 110, 100, 140))]
        XCTAssertTrue(FacadeEdit.matchSize(&els, id: 2, to: 1, plane: nil, width: 1000, height: 800))
        XCTAssertEqual(els[1].points, box(400, 110, 120, 150), "linkerbovenhoek blijft, maat van het voorbeeld")
        XCTAssertEqual(els[1].originalPoints, box(400, 110, 100, 140))
        XCTAssertEqual(els[1].editedByUser, true)
        XCTAssertFalse(FacadeEdit.matchSize(&els, id: 2, to: 2, plane: nil, width: 1000, height: 800))
    }

    func testMatchSizeWithPlaneIsEqualWhenStraightened() throws {
        // Gevelvlak in perspectief: rechts kleiner dan links.
        let plane = FacadePlane(id: 1, kind: .hoofdgevel, corners: [[50, 50], [950, 120], [950, 680], [50, 750]])
        var els = [el(1, .kozijn_raam, [[150, 200], [300, 210], [300, 400], [150, 405]]), el(2, .kozijn_raam, [[600, 230], [700, 236], [700, 380], [600, 384]])]
        XCTAssertTrue(FacadeEdit.matchSize(&els, id: 2, to: 1, plane: plane, width: 1000, height: 800))
        // Rechtgetrokken in hetzelfde eenheidsvierkant als matchSize (de echte gevel op schaal per richting).
        let rect = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
        let h = try XCTUnwrap(Homography(from: plane.corners, to: rect))
        func size(_ q: [[Double]]) -> (Double, Double) {
            let r = q.compactMap { h.apply($0) }
            return ((FacadePhoto.dist(r[0], r[1]) + FacadePhoto.dist(r[3], r[2])) / 2, (FacadePhoto.dist(r[0], r[3]) + FacadePhoto.dist(r[1], r[2])) / 2)
        }
        let s1 = size(els[0].points), s2 = size(els[1].points)
        XCTAssertEqual(s2.0, s1.0, accuracy: 1e-6); XCTAssertEqual(s2.1, s1.1, accuracy: 1e-6)
        XCTAssertLessThan(FacadePhoto.dist(els[1].points[0], els[1].points[1]), FacadePhoto.dist(els[0].points[0], els[0].points[1]),
                          "verder weg in het perspectief: in pixels kleiner")
    }

    func testDuplicateGetsANewIdAndStaysInThePhoto() throws {
        var els = [el(1, .kozijn_raam, box(800, 100, 150, 150))]
        let id = try XCTUnwrap(FacadeEdit.duplicate(&els, id: 1, dx: 150, dy: 0, width: 1000, height: 800, takenIds: [5]))
        XCTAssertEqual(id, 6, "nooit een id van een verwijderd element")
        XCTAssertEqual(els[1].points, box(850, 100, 150, 150), "tegen de rand van de foto gezet")
        XCTAssertEqual(els[1].copiedFrom, 1)
        XCTAssertEqual(els[1].addedByUser, true)
        XCTAssertNil(FacadeEdit.duplicate(&els, id: 99, dx: 0, dy: 0, width: 1000, height: 800))
    }

    // MARK: fotokwaliteit

    func image(_ w: Int, _ h: Int, _ f: (Int, Int) -> UInt8) -> [UInt8] {
        var g = [UInt8](repeating: 0, count: w * h)
        for y in 0..<h { for x in 0..<w { g[y * w + x] = f(x, y) } }
        return g
    }

    func testDarkPhoto() {
        let g = image(64, 48) { x, y in ((x / 4 + y / 4) % 2 == 0) ? 10 : 60 }
        XCTAssertTrue(PhotoQuality.assess(gray: g, width: 64, height: 48).contains(.dark))
    }

    func testSharpPhotoIsFine() {
        let g = image(64, 48) { x, y in ((x / 4 + y / 4) % 2 == 0) ? 60 : 200 }
        XCTAssertEqual(PhotoQuality.assess(gray: g, width: 64, height: 48), [])
    }

    func testBlurryPhoto() {
        let g = image(64, 48) { x, _ in UInt8(80 + x) }   // vloeiend verloop zonder randen
        XCTAssertEqual(PhotoQuality.assess(gray: g, width: 64, height: 48), [.blurry])
    }

    func testBacklight() {
        // Felle lucht boven, donkere gevel met wat structuur onder.
        let g = image(64, 48) { x, y in y < 24 ? 255 : ((x / 3 + y / 3) % 2 == 0 ? 20 : 120) }
        XCTAssertTrue(PhotoQuality.assess(gray: g, width: 64, height: 48).contains(.backlight))
    }

    // MARK: tweede kijkronde

    func testCropsAndMapBack() throws {
        let plane = FacadePlane(id: 1, kind: .hoofdgevel, corners: [[50, 300], [1950, 300], [1950, 1400], [50, 1400]])
        let cs = FacadeDetail.crops(photoW: 2000, photoH: 1500, plane: plane)
        XCTAssertEqual(cs.map(\.name), ["dakrand", "links", "rechts"])
        XCTAssertEqual(cs[0].y, 300 - 180, accuracy: 1e-9, "rond de bovenrand van het hoofdvlak")
        XCTAssertEqual(cs[2].x, 2000 - 440, accuracy: 1e-9)
        // De rechterstrook (440 breed) als beeld van 220 breed: punt (110, 50) → (1560 + 220, 100).
        XCTAssertEqual(cs[2].mapBack([110, 50], imageW: 220), [1780, 100])
    }

    func testParseAndMergeOnlyAddsNewOnes() throws {
        let cs = [FacadeDetail.Crop(name: "links", x: 0, y: 0, w: 400, h: 1500), FacadeDetail.Crop(name: "rechts", x: 1600, y: 0, w: 400, h: 1500)]
        let json = """
        {"elements": [
          {"image": 0, "type": "hwa", "points": [{"x": 100, "y": 50}, {"x": 100, "y": 700}], "material": "pvc", "confidence": "high"},
          {"image": 1, "type": "hwa", "points": [{"x": 100, "y": 50}, {"x": 100, "y": 700}], "material": "zink", "confidence": "medium"},
          {"image": 1, "type": "kozijn_raam", "points": [{"x": 10, "y": 10}, {"x": 100, "y": 100}], "material": "", "confidence": "high"},
          {"image": 5, "type": "hwa", "points": [{"x": 1, "y": 1}, {"x": 1, "y": 99}], "material": "", "confidence": "high"}]}
        """
        let body: [String: Any] = ["content": [["type": "text", "text": json]], "stop_reason": "end_turn"]
        let found = try FacadeDetail.parse(try JSONSerialization.data(withJSONObject: body), crops: cs, sizes: [(200, 750), (200, 750)], photoW: 2000, photoH: 1500)
        XCTAssertEqual(found.count, 2, "kozijn en onbekend beeld overgeslagen")
        XCTAssertEqual(found[1].points, [[1800, 100], [1800, 1400]], "teruggerekend naar de hele foto")
        XCTAssertEqual(found.allSatisfy { $0.detailPass == true }, true)
        // De linker afvoer was al gevonden (net iets anders getekend); de rechter is nieuw.
        let existing = [el(1, .hwa, [[205, 110], [203, 1380]]), el(2, .kozijn_raam, box(800, 400, 200, 300))]
        let merged = FacadeDetail.merge(existing: existing, found: found, photoW: 2000, takenIds: [7])
        XCTAssertEqual(merged.count, 3)
        XCTAssertEqual(merged.last?.id, 8)
        XCTAssertEqual(merged.last?.material, "zink")
        let items = FacadeReview.items(merged, metric: nil, conflicts: [])
        XCTAssertEqual(items.map(\.elementId), [8])
        XCTAssertEqual(items.first?.reasons, [.detailPass])
    }
}
