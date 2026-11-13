import Foundation
import XCTest
@testable import MJOPEngine

final class DocumentExtractionTests: XCTestCase {
    func response(_ json: String) -> Data {
        try! JSONSerialization.data(withJSONObject: ["stop_reason": "end_turn", "content": [["type": "text", "text": json]]] as [String: Any])
    }

    func testOldMJOPNeverGivesAPriceAndInvalidFactsAreSkipped() throws {
        let data = response("""
        {"kind": "oud_mjop", "facts": [
          {"element_key": "schilderwerk-buiten", "name": "Schilderwerk kozijnen", "field": "hoeveelheid", "value": 52, "unit": "m2", "year": null, "page": 11, "quote": "Schilderwerk buitenkozijnen 52 m2", "confidence": "high"},
          {"element_key": "schilderwerk-buiten", "name": "Schilderwerk kozijnen", "field": "prijs", "value": 4100, "unit": "eur", "year": 2019, "page": 11, "quote": "€ 4.100", "confidence": "high"},
          {"element_key": null, "name": "Zinken dakgoten", "field": "laatst_uitgevoerd", "value": 2016, "unit": "jaar", "year": null, "page": 14, "quote": "zink vernieuwd in 2016", "confidence": "medium"},
          {"element_key": "bestaat-niet", "name": "Iets", "field": "cyclus", "value": 0, "unit": "jaar", "year": null, "page": 3, "quote": "elke 0 jaar", "confidence": "low"},
          {"element_key": "dakgoten", "name": "Goten", "field": "hoeveelheid", "value": 18, "unit": "m1", "year": null, "page": 14, "quote": "", "confidence": "low"}
        ]}
        """)
        let r = try DocumentExtraction.parse(data, fallbackKind: .overig)
        XCTAssertEqual(r.kind, .oudMJOP)
        XCTAssertEqual(r.proposals.count, 2)
        XCTAssertEqual(r.skipped, 3, "prijs uit oud MJOP, cyclus 0 en een feit zonder citaat worden overgeslagen")
        XCTAssertFalse(r.proposals.contains { $0.field == .prijs })
        XCTAssertEqual(r.proposals[1].elementKey, "dakgoten", "zonder sleutel wordt op trefwoord gekoppeld")
    }

    func testApplyingProposalsChangesThePlanWithSource() throws {
        let b = BuildingInput(bouwjaar: 1925, units: 1, unitsBAG: 1, footprintM2: 51.42, omtrekM: 32.91, dakPlatM2: 6.3, dakSchuinM2: 61.56, buitenmuurM2: 114.02, hoogteM: 7.7)
        var els = Engine.defaultElements(for: b, year: 2026)
        let q = DocumentProposal(id: "p1", elementKey: "schilderwerk-buiten", documentNaam: "Schilderwerk", field: .hoeveelheid, value: 52, unit: "m2", jaar: nil, page: 11, quote: "52 m2", confidence: "high")
        XCTAssertTrue(DocumentExtraction.apply(q, documentNaam: "MJOP 2019", to: &els))
        let el = try XCTUnwrap(els.first { $0.key == "schilderwerk-buiten" })
        XCTAssertEqual(el.quantity?.value, 52)
        XCTAssertEqual(el.quantity?.source, .document)
        XCTAssertEqual(Engine.cost(el), 52 * 22)

        let offer = DocumentProposal(id: "p2", elementKey: "schilderwerk-buiten", documentNaam: "Schilderwerk", field: .prijs, value: 3875.5, unit: "eur", jaar: 2026, page: 1, quote: "Totaal € 3.875,50", confidence: "high")
        DocumentExtraction.apply(offer, documentNaam: "Offerte schilder", to: &els)
        XCTAssertEqual(Engine.cost(els.first { $0.key == "schilderwerk-buiten" }!), 3876, "offerteprijs vervangt de standaardraming")

        let none = DocumentProposal(id: "p3", elementKey: nil, documentNaam: "?", field: .cyclus, value: 10, unit: nil, jaar: nil, page: nil, quote: "x", confidence: nil)
        XCTAssertFalse(DocumentExtraction.apply(none, documentNaam: "x", to: &els), "zonder post wordt niets veranderd")
    }

    func testMatchingIsConservative() {
        XCTAssertEqual(DocumentExtraction.matchElement("Vernieuwen dakpannen"), "dak-hellend")
        XCTAssertNil(DocumentExtraction.matchElement("Diversen"), "geen gok")
        XCTAssertNil(DocumentExtraction.matchElement("Schilderwerk kozijnen"), "twee mogelijke posten: niet kiezen")
    }
}
