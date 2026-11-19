import XCTest
@testable import MJOPEngine

/// Week 1 van het scannerplan: kozijnen met 4 hoeken, de nalooplijst, vastklikken op randen en de kompascheck.
final class ScannerImprovementTests: XCTestCase {
    func el(_ id: Int, _ t: FacadeElementType, _ pts: [[Double]], conf: String = "high", hidden: Double? = nil) -> FacadePhotoElement {
        FacadePhotoElement(id: id, type: t, points: pts, material: nil, confidence: conf, note: nil, hiddenFraction: hidden)
    }
    func box(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> [[Double]] { [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] }

    // MARK: kozijnen met 4 hoeken (v0.4)

    func testPromptAsksFourCornersForOpeningsOnly() {
        let p = FacadePhoto.prompt(width: 1000, height: 800)
        XCTAssertEqual(FacadePhoto.promptVersion, "gevelfoto_v0.4")
        XCTAssertTrue(p.contains("- kozijn_raam (Raamkozijn): the 4 corners of the outer frame"))
        XCTAssertTrue(p.contains("- garagedeur (Garagedeur): the 4 corners of the outer frame"))
        XCTAssertTrue(p.contains("- rooster (Ventilatierooster): bounding box, exactly 2 points"))
    }

    func testSlantedFrameKeepsItsShape() {
        // Een raam schuin van opzij: de rechterkant is korter. Geen omsluitend kader maken.
        let raw: [[String: Any]] = [["type": "kozijn_raam", "points": [["x": 100, "y": 100], ["x": 300, "y": 120], ["x": 300, "y": 280], ["x": 100, "y": 300]]]]
        let r = FacadePhoto.parseElements(raw, width: 1000, height: 800, scale: 1)
        XCTAssertEqual(r.elements.first?.points, [[100, 100], [300, 120], [300, 280], [100, 300]])
        XCTAssertLessThan(FacadePhoto.area(r.elements[0].points), 200 * 200, "kleiner dan het rechte kader eromheen")
    }

    func testCornersInAnyOrderAreSorted() {
        let raw: [[String: Any]] = [["type": "kozijn_deur", "points": [["x": 100, "y": 100], ["x": 300, "y": 300], ["x": 300, "y": 100], ["x": 100, "y": 300]]]]
        let r = FacadePhoto.parseElements(raw, width: 1000, height: 800, scale: 1)
        XCTAssertEqual(r.elements.first?.points, box(100, 100, 200, 200))
    }

    // MARK: nalooplijst

    func testOnlyDoubtfulElementsAreListed() {
        let els = [el(1, .kozijn_raam, box(0, 0, 1, 1)),
                   el(2, .kozijn_raam, box(2, 0, 1, 1), conf: "low"),
                   el(3, .kozijn_deur, box(4, 0, 1, 2.1), hidden: 0.5),
                   el(4, .kozijn_raam, box(6, 0, 1, 5))]          // 5 m hoog raam
        let items = FacadeReview.items(els, metric: els, conflicts: [])
        XCTAssertEqual(Set(items.map(\.elementId)), [2, 3, 4])
        XCTAssertEqual(items.first { $0.elementId == 4 }?.reasons, [.implausibleSize])
        XCTAssertEqual(items.first { $0.elementId == 3 }?.reasons, [.hidden])
    }

    func testAlmostAlignedNeighboursAreFlagged() {
        let els = [el(1, .kozijn_raam, box(0, 1.00, 1.2, 1.5)),
                   el(2, .kozijn_raam, box(2, 1.08, 1.2, 1.5)),      // 8 cm lager: verdacht
                   el(3, .kozijn_raam, box(4, 1.00, 1.2, 1.5)),      // gelijk aan 1, maar ook 8 cm naast 2
                   el(4, .kozijn_raam, box(6, 3.00, 1.2, 1.5))]      // andere verdieping: in orde
        let ids = FacadeReview.items(els, metric: els, conflicts: []).filter { $0.reasons.contains(.offRow) }.map(\.elementId)
        XCTAssertEqual(Set(ids), [1, 2, 3])
    }

    func testConflictsAndTouchedElements() {
        var els = [el(1, .kozijn_raam, box(0, 0, 1, 1)), el(2, .kozijn_deur, box(0, 0, 1, 2), conf: "low")]
        XCTAssertEqual(FacadeReview.items(els, metric: nil, conflicts: [[1, 2]]).count, 2)
        els[1].editedByUser = true
        XCTAssertEqual(FacadeReview.items(els, metric: nil, conflicts: [[1, 2]]).map(\.elementId), [1], "wat de gebruiker heeft aangepast hoeft niet opnieuw")
    }

    func testConfirmRestAndStats() {
        var els = [el(1, .kozijn_raam, box(0, 0, 1, 1)), el(2, .kozijn_raam, box(2, 0, 1, 1), conf: "low"), el(3, .hwa, [[5, 0], [5, 3]])]
        XCTAssertEqual(FacadeReview.confirmRest(&els, except: [2]), 2)
        XCTAssertEqual(els.map { $0.confirmedByUser == true }, [true, false, true])
        XCTAssertEqual(els[0].points, box(0, 0, 1, 1), "bevestigen verandert de herkenning niet")
        XCTAssertTrue(FacadeReview.items(els, metric: nil, conflicts: []).map(\.elementId) == [2])
        FacadeEdit.retype(&els, id: 2, to: .kozijn_deur)
        var removed: [FacadePhotoElement] = []
        FacadeEdit.delete(&els, removed: &removed, id: 3)
        let s = FacadeReview.stats(els, removed: removed)
        XCTAssertEqual(s.retyped, 1); XCTAssertEqual(s.removed, 1); XCTAssertEqual(s.confirmed, 1); XCTAssertEqual(s.corrections, 2)
    }

    // MARK: vastklikken op randen

    func testSnapsToANearbyRectangleAndKeepsClaudesPoints() {
        var els = [el(1, .kozijn_raam, box(100, 100, 200, 300)), el(2, .metselwerk, box(0, 0, 1000, 800))]
        let found = [box(108, 95, 196, 310), box(600, 100, 100, 100)]
        XCTAssertEqual(EdgeSnap.apply(&els, candidates: found), 1)
        XCTAssertEqual(els[0].points, box(108, 95, 196, 310))
        XCTAssertEqual(els[0].aiPoints, box(100, 100, 200, 300))
        XCTAssertEqual(els[0].snappedByVision, true)
        XCTAssertEqual(els[1].points, box(0, 0, 1000, 800), "muren worden niet vastgeklikt")
    }

    func testDoesNotSnapToSomethingElse() {
        var els = [el(1, .kozijn_raam, box(100, 100, 200, 300))]
        XCTAssertEqual(EdgeSnap.apply(&els, candidates: [box(100, 100, 200, 150)]), 0, "half zo groot: een ander ding (bijv. één ruit)")
        XCTAssertEqual(EdgeSnap.apply(&els, candidates: [box(180, 100, 200, 300)]), 0, "te ver verschoven")
        var edited = els; edited[0].editedByUser = true
        XCTAssertEqual(EdgeSnap.apply(&edited, candidates: [box(105, 100, 200, 300)]), 0, "een aanpassing van de gebruiker blijft staan")
    }

    func testPlaneSnapIsStricter() {
        var planes = [FacadePlane(id: 1, kind: .hoofdgevel, corners: box(50, 50, 900, 700))]
        XCTAssertEqual(EdgeSnap.applyPlanes(&planes, candidates: [box(120, 50, 900, 700)]), 0, "70 px op 700: te ver voor een gevelhoek")
        XCTAssertEqual(EdgeSnap.applyPlanes(&planes, candidates: [box(60, 45, 890, 705)]), 1)
        XCTAssertEqual(planes[0].aiCorners, box(50, 50, 900, 700))
    }

    // MARK: kompas

    func testHeadingFromGravityAndMagneticField() throws {
        // Telefoon rechtop, camera naar het noorden: x = oost, y = omhoog, z = zuid (naar de gebruiker).
        // Magneetveld in de wereld: noord en omlaag (0, 20, -40) in (oost, noord, omhoog) → in toestelcoördinaten (0, -40, -20).
        XCTAssertEqual(try XCTUnwrap(CompassCheck.heading(gravity: [0, -1, 0], magnetic: [0, -40, -20])), 0, accuracy: 0.001)
        // Camera naar het oosten: x = zuid, z = west → veld (-20, -40, 0).
        XCTAssertEqual(try XCTUnwrap(CompassCheck.heading(gravity: [0, -1, 0], magnetic: [-20, -40, 0])), 90, accuracy: 0.001)
        XCTAssertNil(CompassCheck.heading(gravity: [0, 0, -1], magnetic: [0, 20, -40]), "telefoon plat: camera wijst omlaag")
    }

    func testDeviationFromTheChosenFacade() throws {
        // Een gevel op het noorden fotografeer je kijkend naar het zuiden (180°).
        XCTAssertEqual(CompassCheck.viewingHeading(facing: "noord"), 180)
        XCTAssertEqual(try XCTUnwrap(CompassCheck.deviation(cameraHeading: 170, facing: "noord")), 10, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(CompassCheck.deviation(cameraHeading: 350, facing: "noord")), 170, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(CompassCheck.deviation(cameraHeading: 10, facing: "zuid")), 10, accuracy: 1e-9)
        XCTAssertNil(CompassCheck.deviation(cameraHeading: 0, facing: "?"))
        XCTAssertEqual(CompassCheck.name(of: 358), "noord")
        XCTAssertEqual(CompassCheck.name(of: 136), "zuidoost")
    }
}
