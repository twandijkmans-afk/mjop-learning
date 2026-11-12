import Foundation
import XCTest
@testable import MJOPEngine

/// Pariteit met de website: dezelfde invoer moet dezelfde posten, bedragen, fondsstanden en benodigde bijdrage geven.
/// De verwachte waarden komen uit de echte JavaScript-functies (make_fixtures.js); niet met de hand aangepast.
final class EngineParityTests: XCTestCase {
    struct File: Decodable { let year: Int; let cases: [Case] }
    struct Case: Decodable {
        let name: String; let year: Int; let building: B; let fonds: Double; let bijdrage: Double; let scores: [String: Int]
        let elements: [E]; let posten: [P]; let saldi: [S]; let benodigdeBijdrage: Int
    }
    struct B: Decodable {
        let bouwjaar: Int?; let units: Int; let unitsBAG: Int?; let footprint: Double?; let omtrek: Double?
        let plat: Double?; let schuin: Double?; let buitenmuur: Double?; let hoogte: Double?
    }
    struct E: Decodable { let id: String; let cyclus: Int; let laatsteBeurt: Int; let quantity: Double?; let source: String?; let cost: Double?; let koz: [Double]? }
    struct P: Decodable { let el: String; let jaar: Int; let bedrag: Double }
    struct S: Decodable { let jaar: Int; let kosten: Double; let saldo: Double }

    func load() throws -> File {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "engine_cases", withExtension: "json", subdirectory: "Fixtures"))
        return try JSONDecoder().decode(File.self, from: Data(contentsOf: url))
    }

    func d(_ x: Decimal?) -> Double? { x.map { NSDecimalNumber(decimal: $0).doubleValue } }

    func testMatchesWebsiteForAllCases() throws {
        let file = try load()
        XCTAssertGreaterThan(file.cases.count, 10)
        for c in file.cases {
            let b = BuildingInput(bouwjaar: c.building.bouwjaar, units: c.building.units, unitsBAG: c.building.unitsBAG, footprintM2: c.building.footprint,
                                  omtrekM: c.building.omtrek, dakPlatM2: c.building.plat, dakSchuinM2: c.building.schuin, buitenmuurM2: c.building.buitenmuur, hoogteM: c.building.hoogte)
            var els = Engine.defaultElements(for: b, year: c.year)
            for i in els.indices { els[i].conditie = c.scores[els[i].key] }

            XCTAssertEqual(els.map(\.key), c.elements.map(\.id), "\(c.name): standaardposten")
            for (mine, theirs) in zip(els, c.elements) {
                XCTAssertEqual(mine.laatsteBeurt, theirs.laatsteBeurt, "\(c.name) \(theirs.id): laatste beurt")
                if mine.type != .kozijnen {
                    XCTAssertEqual(d(mine.quantity?.value), theirs.quantity, "\(c.name) \(theirs.id): hoeveelheid")
                    XCTAssertEqual(mine.quantity?.source.rawValue, theirs.source, "\(c.name) \(theirs.id): bron")
                } else {
                    XCTAssertEqual(mine.kozijnen?.map { d($0.aantal.value) ?? -1 }, theirs.koz, "\(c.name): kozijnaantallen")
                }
                let cost = d(Engine.cost(mine))
                if let t = theirs.cost { XCTAssertEqual(cost ?? -1, t, accuracy: 0.005, "\(c.name) \(theirs.id): kosten") } else { XCTAssertNil(cost, "\(c.name) \(theirs.id): kosten onbekend") }
            }

            let plan = Engine.plan(els, year: c.year)
            XCTAssertEqual(plan.count, c.posten.count, "\(c.name): aantal geplande uitgaven")
            for (mine, theirs) in zip(plan, c.posten) {
                XCTAssertEqual(mine.key, theirs.el, "\(c.name): volgorde")
                XCTAssertEqual(mine.jaar, theirs.jaar, "\(c.name) \(theirs.el): jaar")
                XCTAssertEqual(d(mine.bedrag) ?? -1, theirs.bedrag, accuracy: 0.005, "\(c.name) \(theirs.el) \(theirs.jaar): bedrag")
            }

            let per = Engine.perYear(plan)
            let fund = Engine.fund(fonds: Decimal(c.fonds), bijdrage: Decimal(c.bijdrage), units: b.units, perYear: per, year: c.year)
            XCTAssertEqual(fund.count, c.saldi.count)
            for (mine, theirs) in zip(fund, c.saldi) {
                XCTAssertEqual(mine.jaar, theirs.jaar)
                XCTAssertEqual(d(mine.kosten) ?? -1, theirs.kosten, accuracy: 0.01, "\(c.name) \(theirs.jaar): kosten per jaar")
                XCTAssertEqual(d(mine.saldo) ?? -1, theirs.saldo, accuracy: 0.01, "\(c.name) \(theirs.jaar): saldo")
            }
            XCTAssertEqual(Engine.requiredContribution(fonds: Decimal(c.fonds), units: b.units, perYear: per, year: c.year), c.benodigdeBijdrage, "\(c.name): benodigde bijdrage")
        }
    }

    func testUnknownStaysUnknown() {
        let b = BuildingInput(bouwjaar: 1990, units: 4, unitsBAG: 4, footprintM2: nil, omtrekM: nil, dakPlatM2: nil, dakSchuinM2: nil, buitenmuurM2: nil, hoogteM: nil)
        let els = Engine.defaultElements(for: b, year: 2026)
        let gevel = els.first { $0.key == "gevel-metselwerk" }!
        XCTAssertNil(gevel.quantity?.value, "zonder omtrek en 3D BAG is het geveloppervlak onbekend, niet 0")
        XCTAssertNil(Engine.cost(gevel), "onbekende hoeveelheid geeft geen bedrag")
        XCTAssertNil(Engine.cost(els.first { $0.key == "steiger" }!), "zonder werkhoogte geen steigerkosten")
    }
}
