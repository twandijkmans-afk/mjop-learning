import Foundation
import XCTest
@testable import MJOPEngine

/// Lezen van echte antwoorden van PDOK, BAG en 3D BAG voor Singelstraat 8, Muiden (opgehaald op 12 november 2026, openbare gegevens).
final class BuildingLookupTests: XCTestCase {
    func fixture(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }

    func testSuggestAndLookup() throws {
        let s = BuildingLookup.parseSuggest(try fixture("pdok_suggest_singelstraat8"))
        XCTAssertFalse(s.isEmpty)
        let a = try XCTUnwrap(BuildingLookup.parseLookup(try fixture("pdok_lookup_singelstraat8")))
        XCTAssertEqual(a.naam, "Singelstraat 8, 1398BN Muiden")
        XCTAssertEqual(a.postcode, "1398 BN")
        XCTAssertEqual(a.plaats, "Muiden")
        XCTAssertEqual(a.lon, 5.06698347, accuracy: 1e-9)
        XCTAssertEqual(a.lat, 52.33004363, accuracy: 1e-9)
    }

    func testPicksThePandThatContainsTheAddress() throws {
        let p = try XCTUnwrap(BuildingLookup.pickPand(try fixture("bag_pand_singelstraat8"), lon: 5.06698347, lat: 52.33004363))
        XCTAssertEqual(p.identificatie, "0424100000003525")
        XCTAssertTrue(p.bevatAdres)
        XCTAssertEqual(p.bouwjaar, 1925)
        XCTAssertEqual(p.verblijfsobjecten, 1)
        XCTAssertEqual(p.footprintM2, 51.416, accuracy: 0.01)
        XCTAssertEqual(p.omtrekM, 32.910, accuracy: 0.01)
    }

    func testReads3DBAGAndBuildsAPlan() throws {
        let d = try XCTUnwrap(BuildingLookup.parse3DBAG(try fixture("3dbag_singelstraat8"), pandId: "0424100000003525"))
        XCTAssertEqual(d.dakPlatM2, 6.3)
        XCTAssertEqual(d.dakSchuinM2, 61.56)
        XCTAssertEqual(d.buitenmuurM2, 114.02)
        XCTAssertEqual(d.hoogteM, 7.7)
        XCTAssertEqual(d.kwaliteitGoed, false)

        let pand = try XCTUnwrap(BuildingLookup.pickPand(try fixture("bag_pand_singelstraat8"), lon: 5.06698347, lat: 52.33004363))
        let input = BuildingLookup.buildingInput(pand: pand, threeD: d)
        let els = Engine.defaultElements(for: input, year: 2026)
        XCTAssertTrue(els.contains { $0.key == "dak-hellend" }, "hellend dak hoort bij dit pand")
        XCTAssertEqual(els.first { $0.key == "dak-hellend" }?.quantity?.value, Decimal(string: "61.56"))
        let plan = Engine.plan(els, year: 2026)
        XCTAssertFalse(plan.isEmpty)
        XCTAssertTrue(plan.allSatisfy { $0.jaar >= 2026 && $0.jaar <= 2035 })
    }
}
