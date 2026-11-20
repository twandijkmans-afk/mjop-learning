import XCTest
@testable import MJOPEngine

final class MeerjarenTabelTests: XCTestCase {
    let b = BuildingInput(bouwjaar: 1990, units: 6, unitsBAG: 6, footprintM2: 200, omtrekM: 60, dakPlatM2: 200, dakSchuinM2: 0, buitenmuurM2: 540, hoogteM: 9)

    func testMainGroup() {
        XCTAssertEqual(MeerjarenTabel.mainGroup("27.1"), "27")
        XCTAssertEqual(MeerjarenTabel.mainGroup("62/63"), "62")
        XCTAssertEqual(MeerjarenTabel.mainGroup("81/89"), "81")
        XCTAssertNil(MeerjarenTabel.mainGroup("7"))
        XCTAssertNil(MeerjarenTabel.mainGroup(nil))
    }

    func testTotalsMatchThePlan() {
        let els = Engine.defaultElements(for: b, year: 2026)
        let t = MeerjarenTabel.make(elements: els, year: 2026)
        let plan = Engine.plan(els, year: 2026)
        XCTAssertEqual(t.years, Array(2026...2035))
        XCTAssertEqual(t.total, plan.reduce(Decimal(0)) { $0 + $1.bedrag }, "het totaal is precies de som van het plan")
        XCTAssertEqual(t.perYear, Engine.perYear(plan))
        for g in t.groups {
            XCTAssertEqual(g.total, g.rows.reduce(Decimal(0)) { $0 + $1.total })
            XCTAssertEqual(g.total, g.perYear.values.reduce(0, +))
        }
        XCTAssertEqual(t.groups.flatMap(\.rows).count, els.count, "elke post precies één keer")
    }

    func testGroupedBySfbInOrder() {
        let t = MeerjarenTabel.make(elements: Engine.defaultElements(for: b, year: 2026), year: 2026)
        let codes = t.groups.map(\.code)
        XCTAssertEqual(codes, codes.sorted())
        XCTAssertEqual(t.groups.first { $0.code == "27" }?.naam, "Daken")
        XCTAssertTrue(t.groups.first { $0.code == "27" }?.rows.contains { $0.key == "dak-plat" } ?? false)
    }

    func testUnknownCostIsMarkedNotZero() {
        var els = Engine.defaultElements(for: b, year: 2026)
        let i = try! XCTUnwrap(els.firstIndex { $0.key == "dak-plat" })
        els[i].quantity = Quantity(value: nil, unit: "m2", source: .notAvailable, basis: "onbekend")
        let row = try! XCTUnwrap(MeerjarenTabel.make(elements: els, year: 2026).groups.flatMap(\.rows).first { $0.key == "dak-plat" })
        XCTAssertTrue(row.costUnknown)
        XCTAssertNil(row.quantity)
        XCTAssertNil(row.startYear)
        XCTAssertTrue(row.perYear.isEmpty)
    }

    func testKozijnenSumAndCycles() {
        var els = Engine.defaultElements(for: b, year: 2026)
        let i = try! XCTUnwrap(els.firstIndex { $0.key == "kozijnen-onderhoud" })
        els[i].kozijnen = [KozijnRij(naam: "Raam", tarief: 100, aantal: Quantity(value: 10, unit: "st", source: .manual, basis: "x"), materiaal: .hout),
                           KozijnRij(naam: "Deur", tarief: 200, aantal: Quantity(value: 2, unit: "st", source: .manual, basis: "x"), materiaal: .kunststof)]
        let row = try! XCTUnwrap(MeerjarenTabel.make(elements: els, year: 2026).groups.flatMap(\.rows).first { $0.key == "kozijnen-onderhoud" })
        XCTAssertEqual(row.quantity, 12)
        XCTAssertEqual(row.unit, "st")
        XCTAssertEqual(row.cycles, [6, 20])
    }

    func testConditionMovesStartYear() {
        var els = Engine.defaultElements(for: b, year: 2026)
        let i = try! XCTUnwrap(els.firstIndex { $0.key == "gevel-metselwerk" })
        els[i].conditie = 6
        let row = try! XCTUnwrap(MeerjarenTabel.make(elements: els, year: 2026).groups.flatMap(\.rows).first { $0.key == "gevel-metselwerk" })
        XCTAssertEqual(row.startYear, 2026)
        XCTAssertEqual(row.conditie, 6)
    }
}
