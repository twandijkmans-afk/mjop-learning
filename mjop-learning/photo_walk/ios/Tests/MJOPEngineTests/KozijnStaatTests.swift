import Foundation
import XCTest
@testable import MJOPEngine

final class KozijnStaatTests: XCTestCase {
    func item(_ side: Int, _ el: Int, _ w: Double?, _ h: Double?, type t: FacadeElementType = .kozijn_raam, hidden: Double? = 0, material: String? = "hout") -> KozijnItem {
        KozijnItem(sideId: side, elementId: el, type: t, material: material, widthM: w, heightM: h, hiddenFraction: hidden)
    }

    func testGroupsWithinSevenPercentAndSplitsAbove() {
        let r = KozijnStaat.make([
            item(1, 1, 1.20, 1.50), item(1, 2, 1.24, 1.46), item(2, 1, 1.18, 1.52),   // zelfde type (binnen 7%)
            item(1, 3, 1.35, 1.50),                                                   // 12,5% breder: ander type
            item(1, 4, 1.0, 2.2, type: .kozijn_deur),
        ])
        XCTAssertEqual(r.types.map(\.count), [3, 1, 1])
        XCTAssertEqual(r.types[0].letter, "A")
        XCTAssertEqual(r.types[0].widthM, 1.24, "maat van het best zichtbare kozijn (bij gelijke zichtbaarheid het grootste)")
        XCTAssertEqual(r.types[1].type, .kozijn_raam, "bij gelijk aantal eerst ramen, dan deuren")
        XCTAssertEqual(r.types[2].type, .kozijn_deur)
        XCTAssertEqual(r.total, 5)
    }

    func testMaterialsAreNotMixed() {
        let r = KozijnStaat.make([item(1, 1, 1.2, 1.5, material: "hout"), item(1, 2, 1.2, 1.5, material: "kunststof"), item(1, 3, 1.2, 1.5, material: nil)])
        XCTAssertEqual(r.types.count, 2)
        XCTAssertEqual(r.types[0].count, 2, "onbekend materiaal past bij elk type")
    }

    func testHiddenWindowTakesTheSizeOfItsType() throws {
        let r = KozijnStaat.make([
            item(1, 1, 1.2, 1.5), item(1, 2, 1.2, 1.5),
            item(1, 3, 1.0, 2.2, type: .kozijn_deur),
            item(1, 4, 1.22, 0.7, hidden: 0.55),   // onderste helft achter een struik: hoogte telt niet
        ])
        let a = try XCTUnwrap(r.types.first { $0.type == .kozijn_raam })
        XCTAssertEqual(a.count, 3)
        XCTAssertEqual(a.derivedCount, 1)
        XCTAssertEqual(a.heightM, 1.5, "het type houdt de maat van het zichtbare kozijn")
        XCTAssertTrue(r.unassigned.isEmpty)
    }

    func testAmbiguousOrUnknownHiddenWindowIsNotGuessed() {
        let r = KozijnStaat.make([
            item(1, 1, 1.20, 1.50), item(1, 2, 1.20, 0.60),          // twee typen met dezelfde breedte
            item(1, 3, 1.21, 0.4, hidden: 0.7),                       // past bij allebei: niet gokken
            item(1, 4, 2.40, 1.0, hidden: 0.5),                       // geen type met deze breedte
            item(1, 5, nil, nil, hidden: 0.9),                        // geen maat
        ])
        XCTAssertEqual(r.unassigned.map(\.elementId), [3, 4, 5])
        XCTAssertEqual(r.total, 5, "niet toegewezen kozijnen tellen wel mee in het aantal")
    }

    func testLettersFollowCount() {
        let r = KozijnStaat.make([item(1, 1, 0.6, 0.6), item(1, 2, 1.2, 1.5), item(1, 3, 1.2, 1.5)])
        XCTAssertEqual(r.types.first?.widthM, 1.2)
        XCTAssertEqual(r.types.map(\.letter), ["A", "B"])
    }

    func testUserCanMergeAndSeparate() throws {
        let items = [item(1, 1, 1.20, 1.50), item(1, 2, 1.20, 1.50), item(1, 3, 1.35, 1.50)]
        let auto = KozijnStaat.make(items)
        XCTAssertEqual(auto.types.count, 2)
        let small = try XCTUnwrap(auto.types.first { $0.widthM == 1.35 }), big = auto.types[0]

        let merged = KozijnStaat.make(items, overrides: KozijnOverrides(merge: [small.id: big.id]))
        XCTAssertEqual(merged.types.count, 1)
        XCTAssertEqual(merged.types[0].count, 3)
        XCTAssertTrue(merged.types[0].editedByUser)
        XCTAssertEqual(merged.types[0].widthM, 1.20, "het type waarin wordt samengevoegd houdt zijn maat")

        let split = KozijnStaat.make(items, overrides: KozijnOverrides(separate: ["1:2"]))
        XCTAssertEqual(split.types.map(\.count), [1, 1, 1])
        XCTAssertTrue(split.types.contains { $0.id == "1:2" && $0.editedByUser })

        let stale = KozijnStaat.make(items, overrides: KozijnOverrides(merge: ["9:9": big.id]))
        XCTAssertEqual(stale, auto, "een verouderde keuze verandert niets")
    }

    func testOnlyOpeningsCount() {
        let r = KozijnStaat.make([item(1, 1, 0.1, 6, type: .hwa), item(1, 2, 1.2, 1.5)])
        XCTAssertEqual(r.total, 1)
    }
}
