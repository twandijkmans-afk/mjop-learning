import XCTest
@testable import MJOPEngine

final class ElementListTests: XCTestCase {
    func el(_ id: Int, _ t: FacadeElementType, _ pts: [[Double]], material: String? = nil, hidden: Double? = nil) -> FacadePhotoElement {
        FacadePhotoElement(id: id, type: t, points: pts, material: material, confidence: "high", note: nil, hiddenFraction: hidden)
    }
    func box(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> [[Double]] { [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] }

    /// Gevel van 10 × 6 m (in meters, al rechtgetrokken) met twee ramen, een deur, een goot en een afvoer.
    func facade() -> [FacadePhotoElement] {
        [el(1, .metselwerk, box(0, 0, 10, 6), material: "baksteen"),
         el(2, .kozijn_raam, box(1, 1, 1.2, 1.5), material: "hout"),
         el(3, .kozijn_raam, box(4, 1, 1.2, 1.5), material: "Hout"),
         el(4, .kozijn_deur, box(7, 3.9, 1, 2.1), material: "kunststof"),
         el(5, .dakgoot, [[0, 0], [10, 0]], material: "zink"),
         el(6, .hwa, [[9.8, 0], [9.8, 6]], hidden: 0.5)]
    }

    func testMeasuresPerElement() throws {
        let ms = ElementList.measures(metric: facade(), relative: 0.05)
        let raam = try XCTUnwrap(ms.first { $0.elementId == 2 })
        XCTAssertEqual(raam.widthM, 1.2); XCTAssertEqual(raam.heightM, 1.5); XCTAssertEqual(raam.areaM2, 1.8)
        XCTAssertEqual(try XCTUnwrap(raam.band), 1.8 * 0.05 * 2, accuracy: 0.01, "oppervlak: tweemaal de relatieve fout")
        let muur = try XCTUnwrap(ms.first { $0.elementId == 1 })
        XCTAssertEqual(try XCTUnwrap(muur.areaM2), 60 - 1.8 - 1.8 - 2.1, accuracy: 0.001, "netto, openingen afgetrokken")
        let goot = try XCTUnwrap(ms.first { $0.elementId == 5 })
        XCTAssertEqual(goot.lengthM, 10); XCTAssertEqual(try XCTUnwrap(goot.band), 0.5, accuracy: 0.001)
        let hwa = try XCTUnwrap(ms.first { $0.elementId == 6 })
        XCTAssertGreaterThan(try XCTUnwrap(hwa.band), 6 * 0.05, "half verborgen: grotere bandbreedte")
    }

    func testGroupsWithTotalsAndMaterials() throws {
        let gs = ElementList.groups(ElementList.measures(metric: facade(), relative: 0.05))
        XCTAssertEqual(gs.map(\.type), [.kozijn_raam, .kozijn_deur, .metselwerk, .hwa, .dakgoot], "vaste volgorde van de soorten")
        let ramen = try XCTUnwrap(gs.first { $0.type == .kozijn_raam })
        XCTAssertEqual(ramen.count, 2)
        XCTAssertEqual(try XCTUnwrap(ramen.total), 3.6, accuracy: 0.001)
        XCTAssertEqual(try XCTUnwrap(ramen.band), 0.36, accuracy: 0.01, "lineair opgeteld")
        XCTAssertEqual(ramen.materials, ["hout"], "zonder dubbelen, ongeacht hoofdletters")
    }

    func testUnknownMeasureMakesTheTotalUnknown() {
        let measured = ElementList.measures(metric: [el(1, .dakgoot, [[0, 0], [5, 0]])], relative: 0.05, sideId: 1)
        let unknown = ElementList.unmeasured([el(2, .dakgoot, [[0, 0], [300, 0]])], sideId: 1)
        let g = ElementList.groups(measured + unknown)
        XCTAssertEqual(g.first?.count, 2)
        XCTAssertNil(g.first?.total, "één onbekende maat: totaal onbekend, niet gokken")
        XCTAssertNil(unknown[0].band)
    }

    func testMergeTwoFacades() throws {
        let a = ElementList.groups(ElementList.measures(metric: [el(1, .dakgoot, [[0, 0], [10, 0]])], relative: 0.05, sideId: 1))
        let b = ElementList.groups(ElementList.measures(metric: [el(1, .dakgoot, [[0, 0], [8, 0]]), el(2, .hwa, [[0, 0], [0, 6]])], relative: 0.1, sideId: 2))
        let all = ElementList.merge([a, b])
        let goot = try XCTUnwrap(all.first { $0.type == .dakgoot })
        XCTAssertEqual(goot.count, 2)
        XCTAssertEqual(try XCTUnwrap(goot.total), 18, accuracy: 0.001)
        XCTAssertEqual(try XCTUnwrap(goot.band), 0.5 + 0.8, accuracy: 0.001)
        XCTAssertEqual(Set(goot.items.map(\.id)), ["1:1", "2:1"], "zelfde element-id op twee gevels blijft uit elkaar")
    }
}
