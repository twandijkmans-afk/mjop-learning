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

final class LooptijdTests: XCTestCase {
    let b = BuildingInput(bouwjaar: 1990, units: 6, unitsBAG: 6, footprintM2: 200, omtrekM: 60, dakPlatM2: 200, dakSchuinM2: 0, buitenmuurM2: 540, hoogteM: 9)

    func testThirtyYearsMatchesThePlan() {
        let els = Engine.defaultElements(for: b, year: 2026)
        let t = MeerjarenTabel.make(elements: els, year: 2026, horizon: 30)
        let plan = Engine.plan(els, year: 2026, horizon: 30)
        XCTAssertEqual(t.years, Array(2026...2055))
        XCTAssertEqual(t.total, plan.reduce(Decimal(0)) { $0 + $1.bedrag })
        XCTAssertEqual(t.perYear, Engine.perYear(plan))
        XCTAssertGreaterThan(t.total, MeerjarenTabel.make(elements: els, year: 2026).total)
        XCTAssertLessThan(MeerjarenTabel.make(elements: els, year: 2026, horizon: 5).total, MeerjarenTabel.make(elements: els, year: 2026).total + 1)
    }

    func testDefaultHorizonUnchanged() {
        let els = Engine.defaultElements(for: b, year: 2026)
        XCTAssertEqual(Engine.plan(els, year: 2026), Engine.plan(els, year: 2026, horizon: 10))
    }

    func testLongCycleRepeatsWithinThirtyYears() {
        var els = Engine.defaultElements(for: b, year: 2026)
        let i = try! XCTUnwrap(els.firstIndex { $0.key == "dak-plat" })
        els[i].laatsteBeurt = 2001   // cyclus 25: 2026 en 2051
        let row = try! XCTUnwrap(MeerjarenTabel.make(elements: els, year: 2026, horizon: 30).groups.flatMap(\.rows).first { $0.key == "dak-plat" })
        XCTAssertEqual(row.perYear.keys.sorted(), [2026, 2051])
    }

    func testBlocks() {
        XCTAssertEqual(MeerjarenTabel.blocks(Array(2026...2030)), [Array(2026...2030)])
        XCTAssertEqual(MeerjarenTabel.blocks(Array(2026...2055)).map(\.count), [10, 10, 10])
        XCTAssertEqual(MeerjarenTabel.blocks(Array(2026...2050)).map(\.count), [10, 10, 5])
        XCTAssertEqual(MeerjarenTabel.blocks(Array(2026...2040)).last?.first, 2036)
    }

    func testFundOverThirtyYears() {
        let els = Engine.defaultElements(for: b, year: 2026)
        let py = Engine.perYear(Engine.plan(els, year: 2026, horizon: 30))
        XCTAssertEqual(Engine.fund(fonds: 10000, bijdrage: 50, units: 6, perYear: py, year: 2026, horizon: 30).count, 30)
        XCTAssertEqual(Engine.reportHorizons, [5, 10, 15, 20, 25, 30])
        let r30 = Engine.requiredContribution(fonds: 10000, units: 6, perYear: py, year: 2026, horizon: 30)
        let r10 = Engine.requiredContribution(fonds: 10000, units: 6, perYear: py, year: 2026)
        XCTAssertGreaterThanOrEqual(r30, r10)
    }
}
