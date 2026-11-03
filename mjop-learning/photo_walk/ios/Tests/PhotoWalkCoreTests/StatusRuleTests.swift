import XCTest
@testable import PhotoWalkCore

/// Eindstatus van een object: Swift (makeObject) == Python (pipeline.final_status). Regressie: een afwaarderende code van een WAARNEMING
/// (extraFlags, bv. AUTO_DETECTED_UNCONFIRMED van een oude LEGACY-waarneming of van een onbevestigde, wel gekoppelde kandidaat) sloot in Swift
/// MEASURED niet uit, in Python wel. Synthetische resultaten; zegt niets over nauwkeurigheid op echte gevels.
final class StatusRuleTests: XCTestCase {
    private func result(level: Level, codes: [String]) -> LevelResult {
        var r = LevelResult(level: level, scaleMethod: level == .A ? "LIDAR_DEPTH_PLANE" : "REFERENCE_DISTANCE", viewIds: ["F000", "F001"])
        r.width = 1.2; r.height = 1.5; r.sigmaW = 0.01; r.sigmaH = 0.01; r.sigmaArea = 0.02
        r.flags = codes.map { Flags.make($0) }
        return r
    }

    func testObservationLevelDowngradingCodeExcludesMeasured() {
        let r = result(level: .A, codes: [])
        XCTAssertEqual(makeObject(id: "P", observations: [], result: r, viewCount: 2).status, .MEASURED, "twee consistente standpunten, schoon")
        let auto = makeObject(id: "P", observations: [], result: r, viewCount: 2, extraFlags: [Flags.make("AUTO_DETECTED_UNCONFIRMED")])
        XCTAssertEqual(auto.status, .ESTIMATED, "onbevestigde automatische waarneming in het object: nooit MEASURED")
        XCTAssertTrue(auto.reviewRequired)
        XCTAssertEqual(makeObject(id: "P", observations: [], result: r, viewCount: 2, extraFlags: [Flags.make("OBSTRUCTION_REPORTED")]).status, .ESTIMATED)
        // codes die niet afwaarderen: bestaand gedrag blijft (handmatig/gecorrigeerd met twee consistente standpunten)
        XCTAssertEqual(makeObject(id: "P", observations: [], result: r, viewCount: 2, extraFlags: [Flags.make("MANUAL_CORNERS")]).status, .MEASURED)
        XCTAssertEqual(makeObject(id: "P", observations: [], result: r, viewCount: 2, extraFlags: [Flags.make("HUMAN_CORRECTED_CORNERS")]).status, .MEASURED)
        // referentiemaat blijft DERIVED (de regel raakt alleen MEASURED)
        XCTAssertEqual(makeObject(id: "P", observations: [], result: result(level: .C, codes: []), viewCount: 1,
                                  extraFlags: [Flags.make("AUTO_DETECTED_UNCONFIRMED")]).status, .DERIVED)
    }

    func testStatusRulesMatchPython() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "facade_parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let rules = try XCTUnwrap(root["status_rules"] as? [String: Any])
        XCTAssertEqual(Status.downgrading, Set(try XCTUnwrap(rules["downgrading"] as? [String])), "zelfde afwaarderende codes in Swift en Python")
        let cases = try XCTUnwrap(rules["cases"] as? [[String: Any]])
        XCTAssertGreaterThanOrEqual(cases.count, 10)
        for cs in cases {
            let name = cs["name"] as! String
            let level: Level = (cs["level"] as! String) == "A" ? .A : .C
            let r = result(level: level, codes: cs["result_flags"] as! [String])
            let obj = makeObject(id: "P", observations: [], result: r, viewCount: (cs["view_count"] as! NSNumber).intValue,
                                 extraFlags: (cs["object_flags"] as! [String]).map { Flags.make($0) })
            XCTAssertEqual(obj.status.rawValue, cs["expected"] as? String, name)
        }
    }
}
