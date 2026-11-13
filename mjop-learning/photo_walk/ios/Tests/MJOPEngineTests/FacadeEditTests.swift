import XCTest
@testable import MJOPEngine

final class FacadeEditTests: XCTestCase {
    func sample() -> [FacadePhotoElement] {
        [FacadePhotoElement(id: 1, type: .metselwerk, points: [[0, 0], [1000, 0], [1000, 600], [0, 600]], material: nil, confidence: "high", note: nil),
         FacadePhotoElement(id: 2, type: .kozijn_raam, points: [[100, 100], [300, 100], [300, 300], [100, 300]], material: "hout", confidence: "high", note: nil),
         FacadePhotoElement(id: 3, type: .hwa, points: [[980, 0], [980, 600]], material: nil, confidence: "high", note: nil)]
    }

    func testRetypeKeepsTheOriginal() {
        var els = sample()
        XCTAssertTrue(FacadeEdit.retype(&els, id: 2, to: .kozijn_deur))
        XCTAssertEqual(els[1].type, .kozijn_deur)
        XCTAssertEqual(els[1].originalType, .kozijn_raam)
        XCTAssertEqual(els[1].editedByUser, true)
        XCTAssertFalse(FacadeEdit.retype(&els, id: 2, to: .hwa), "een kader wordt geen lijn")
        FacadeEdit.retype(&els, id: 2, to: .garagedeur)
        XCTAssertEqual(els[1].originalType, .kozijn_raam, "de eerste herkenning blijft het origineel")
    }

    func testMoveStaysInsideThePhoto() {
        var els = sample()
        FacadeEdit.move(&els, id: 2, dx: -500, dy: 10, width: 1000, height: 600)
        XCTAssertEqual(els[1].points[0], [0, 110])
        XCTAssertEqual(els[1].originalPoints?[0], [100, 100])
    }

    func testDeleteKeepsWhatWasRecognised() {
        var els = sample(), removed: [FacadePhotoElement] = []
        FacadeEdit.delete(&els, removed: &removed, id: 2)
        XCTAssertEqual(els.map(\.id), [1, 3])
        XCTAssertEqual(removed.map(\.id), [2])
    }

    func testAddAndHit() throws {
        var els = sample()
        let id = try XCTUnwrap(FacadeEdit.add(&els, type: .kozijn_raam, from: [600, 100], to: [500, 300], plane: 1, takenIds: [7]))
        XCTAssertEqual(id, 8, "nooit een id van een verwijderd element hergebruiken")
        XCTAssertEqual(els.last?.addedByUser, true)
        XCTAssertEqual(els.last?.points[0], [500, 100])
        XCTAssertNil(FacadeEdit.add(&els, type: .kozijn_raam, from: [0, 0], to: [2, 2], plane: nil), "te klein")
        XCTAssertEqual(FacadeEdit.hit(els, at: [150, 150], tolerance: 10), 2, "kleinste kader wint van de muur")
        XCTAssertEqual(FacadeEdit.hit(els, at: [975, 300], tolerance: 10), 3, "lijn binnen de tolerantie")
        XCTAssertEqual(FacadeEdit.hit(els, at: [700, 500], tolerance: 10), 1, "anders de muur")
        var removed: [FacadePhotoElement] = []
        FacadeEdit.delete(&els, removed: &removed, id: id)
        XCTAssertTrue(removed.isEmpty, "zelf toegevoegd en weer weg: niets te bewaren")
    }

    func testTapCyclesThroughOverlappingElements() {
        var els = sample()
        els.append(FacadePhotoElement(id: 4, type: .kozijn_deur, points: [[120, 120], [280, 120], [280, 290], [120, 290]], material: nil, confidence: "high", note: nil))
        XCTAssertEqual(FacadeEdit.candidates(els, at: [150, 150], tolerance: 10), [4, 2, 1])
        XCTAssertEqual(FacadeEdit.nextSelection(els, at: [150, 150], tolerance: 10, current: nil), 4)
        XCTAssertEqual(FacadeEdit.nextSelection(els, at: [150, 150], tolerance: 10, current: 4), 2)
        XCTAssertEqual(FacadeEdit.nextSelection(els, at: [150, 150], tolerance: 10, current: 1), 4, "na de muur weer het kleinste")
        XCTAssertEqual(FacadeEdit.nextSelection(els, at: [600, 500], tolerance: 10, current: 2), 1, "elders tikken kiest wat daar ligt")
    }

    func testMoveOneCorner() {
        var els = sample()
        FacadeEdit.moveVertex(&els, id: 2, index: 2, to: [320, 310], width: 1000, height: 600)
        XCTAssertEqual(els[1].points[2], [320, 310])
        XCTAssertEqual(els[1].points[0], [100, 100])
        XCTAssertEqual(els[1].originalPoints?[2], [300, 300])
    }

    func testExtendDownpipeToTheRoofEdge() throws {
        var els = sample()
        els[2].points = [[980, 600], [980, 350]]   // afvoer van onder tot halverwege (rest achter planten)
        let roofEdge = [[0.0, 40.0], [1000.0, 20.0]]
        XCTAssertTrue(FacadeEdit.extendLine(&els, id: 3, to: roofEdge, upward: true, width: 1000, height: 600))
        let top = try XCTUnwrap(els[2].points.min { $0[1] < $1[1] })
        XCTAssertEqual(top[0], 980, accuracy: 1e-9)
        XCTAssertEqual(top[1], 40 - 20 * 0.98, accuracy: 1e-9, "snijpunt met de schuine dakrand")
        XCTAssertEqual(els[2].points.first, [980, 600], "onderkant blijft staan")
        XCTAssertFalse(FacadeEdit.extendLine(&els, id: 2, to: roofEdge, upward: true, width: 1000, height: 600), "een kader is geen lijn")
    }
}
