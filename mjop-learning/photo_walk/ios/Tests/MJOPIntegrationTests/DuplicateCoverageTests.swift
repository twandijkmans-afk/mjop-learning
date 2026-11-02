import XCTest
@testable import MJOPIntegration

/// Dekking van de duplicaatcontrole: nul suggesties is geen bewijs. Python-referentie: photo_walk_core/duplicate_coverage.py (pariteit hieronder).
final class DuplicateCoverageTests: XCTestCase {
    let project = ScanProposalV2.Project(planRef: "plan-0123456789ab", mjopPlanId: nil, buildingId: "Kastanjelaan 12", bagPandId: nil)

    func obj(_ id: String, facade: String = "Voor", frames: [String], area: Decimal? = 1.8, checkable: Bool = true) -> RoundObject {
        RoundObject(id: id, facadeId: facade, frameIds: frames, areaM2: area, areaSigmaM2: 0.04, status: .estimated, method: "LIDAR_DEPTH_PLANE",
                    autoDetected: false, userConfirmed: false, manual: true, flags: [], duplicateCheckable: checkable)
    }
    func build(_ objects: [RoundObject], facades: [RoundFacade], frameWorld: [String: String]?, dups: [String: Int] = [:], dupTotal: Int? = nil,
               reviewed: Bool = false) -> [ScanProposalV2] {
        RoundProposalBuilder.build(RoundBuildInput(roundId: "0F3A9C1E-1111-2222-3333-444455556666", revision: 1, createdAt: "2026-10-23T10:00:00Z", project: project,
                                                   elementKey: nil, objects: objects, facades: facades, excludedObjectsByFacade: [:], duplicatesUnresolvedByFacade: dups,
                                                   duplicatesUnresolvedTotal: dupTotal, frameWorld: frameWorld, duplicateReviewConfirmed: reviewed))
    }
    func find(_ ps: [ScanProposalV2], _ kind: ScanProposalV2.Target.Kind, facade: String? = nil) -> ScanProposalV2? {
        ps.first { $0.target.quantityKind == kind && $0.target.scope.facadeId == facade }
    }
    private func assertBlocked(_ p: ScanProposalV2?, reason: String, file: StaticString = #filePath, line: UInt = #line) throws {
        let p = try XCTUnwrap(p, file: file, line: line)
        XCTAssertNil(p.value, p.proposalId, file: file, line: line); XCTAssertNil(p.partialValue, p.proposalId, file: file, line: line)
        XCTAssertEqual(p.reliability.level, "INCOMPLETE", file: file, line: line)
        XCTAssertTrue(p.reliability.reasons.contains(reason), "\(p.proposalId) mist \(reason): \(p.reliability.reasons)", file: file, line: line)
        XCTAssertEqual(p.basis.duplicateReviewComplete, false, file: file, line: line)
        XCTAssertEqual(p.validate(), [], p.proposalId, file: file, line: line)
    }
    private let one = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"])]

    func testSameObjectOnTwoPhotosWithoutPlaneGeometryIsNotPassed() throws {
        // twee waarnemingen van hetzelfde kozijn zonder LiDAR-vlak: geen suggestie mogelijk, dus NIET "geen duplicaat"
        let ps = build([obj("A", frames: ["F0"], checkable: false), obj("B", frames: ["F1"], checkable: false)], facades: one, frameWorld: ["F0": "w1", "F1": "w1"])
        try assertBlocked(find(ps, .FRAME_COUNT), reason: "DUPLICATE_CHECK_INCOMPLETE")
        try assertBlocked(find(ps, .FRAME_AREA_GROSS), reason: "DUPLICATE_CHECK_INCOMPLETE")
        XCTAssertEqual(find(ps, .FRAME_COUNT)?.basis.duplicateCheckUncheckedObjects, 2)
        XCTAssertEqual(find(ps, .FRAME_COUNT)?.basis.duplicatesUnresolved, 0, "nul suggesties, maar toch geblokkeerd")
        // één object zonder geometrie, verder niets: er is niets om mee dubbel te tellen
        XCTAssertEqual(find(build([obj("A", frames: ["F0"], checkable: false)], facades: one, frameWorld: ["F0": "w1"]), .FRAME_COUNT)?.value, 1)
    }

    func testDifferentFacadesEachWithOwnWorldBlockOnlyTheBuildingTotal() throws {
        let facades = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"]), RoundFacade(id: "Achter", orientation: "N", worldIds: ["w2"])]
        let ps = build([obj("A", frames: ["F0"]), obj("B", facade: "Achter", frames: ["F1"])], facades: facades, frameWorld: ["F0": "w1", "F1": "w2"])
        // gebouw: twee AR-sessies, onderling niet vergelijkbaar (oude code zag dit niet: elke gevel had maar één sessie)
        try assertBlocked(find(ps, .FRAME_COUNT), reason: "CROSS_SESSION_UNCHECKED")
        try assertBlocked(find(ps, .FRAME_AREA_GROSS), reason: "CROSS_SESSION_UNCHECKED")
        XCTAssertTrue(find(ps, .FRAME_COUNT)!.basis.crossSessionUnchecked)
        // gevel: alleen de eigen foto's (één sessie, volledig gecontroleerd); een kozijn bij een andere gevel is binnen deze gevel geen duplicaat
        for f in ["Voor", "Achter"] {
            let c = try XCTUnwrap(find(ps, .FRAME_COUNT, facade: f))
            XCTAssertEqual(c.value, 1, f); XCTAssertEqual(c.basis.duplicateReviewComplete, true, f); XCTAssertEqual(c.validate(), [], f)
            XCTAssertEqual(find(ps, .FRAME_AREA_GROSS, facade: f)?.value, 1.8, f)
        }
    }

    func testMissingWorldIdsAndUnknownGeometry() throws {
        // foto F1 zonder bekende AR-sessie
        let ps = build([obj("A", frames: ["F0"]), obj("B", frames: ["F1"])], facades: one, frameWorld: ["F0": "w1"])
        try assertBlocked(find(ps, .FRAME_COUNT), reason: "DUPLICATE_CHECK_INCOMPLETE")
        XCTAssertEqual(find(ps, .FRAME_COUNT)?.basis.duplicateCheckUnknownWorldPhotos, 1)
        // geen enkele sessie bekend, objecten op twee foto's
        try assertBlocked(find(build([obj("A", frames: ["F0"]), obj("B", frames: ["F1"])], facades: [RoundFacade(id: "Voor", orientation: nil, worldIds: [])],
                                     frameWorld: [:]), .FRAME_AREA_GROSS), reason: "DUPLICATE_CHECK_INCOMPLETE")
        // gemengd: één object zonder geometrie en een onbekende sessie
        let mixed = build([obj("A", frames: ["F0"], checkable: false), obj("B", frames: ["F1"])], facades: one, frameWorld: ["F0": "w1"])
        XCTAssertEqual(find(mixed, .FRAME_COUNT)?.basis.duplicateCheckUncheckedObjects, 1); XCTAssertNil(find(mixed, .FRAME_COUNT)?.value)
    }

    func testReviewedDuplicatesRestoreNormalBehaviourButNotOpenSuggestions() throws {
        let facades = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"]), RoundFacade(id: "Achter", orientation: "N", worldIds: ["w2"])]
        let objs = [obj("A", frames: ["F0"], checkable: false), obj("B", facade: "Achter", frames: ["F1"])]
        let ps = build(objs, facades: facades, frameWorld: ["F0": "w1"], reviewed: true)
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT)), a = try XCTUnwrap(find(ps, .FRAME_AREA_GROSS))
        XCTAssertEqual(c.value, 2); XCTAssertEqual(a.value, 3.6); XCTAssertEqual(c.reliability.level, "CHECK_REQUIRED")
        XCTAssertEqual(c.basis.duplicateReviewComplete, true); XCTAssertEqual(c.basis.duplicateReviewManual, true, "herkomst: handmatige controle")
        XCTAssertFalse(c.basis.crossSessionUnchecked)
        XCTAssertEqual(c.basis.duplicateCheckUncheckedObjects, 1, "wat niet automatisch kon, blijft zichtbaar")
        XCTAssertFalse(c.reliability.reasons.contains("DUPLICATE_CHECK_INCOMPLETE")); XCTAssertFalse(c.reliability.reasons.contains("CROSS_SESSION_UNCHECKED"))
        for p in ps { XCTAssertEqual(p.validate(), [], p.proposalId) }
        // een openstaande koppelsuggestie moet altijd apart beoordeeld worden: de verklaring vervangt die niet
        let open = build(objs, facades: facades, frameWorld: ["F0": "w1"], dups: ["Voor": 1], dupTotal: 1, reviewed: true)
        try assertBlocked(find(open, .FRAME_COUNT), reason: "DUPLICATES_UNRESOLVED")
        // na beoordeling (gekoppeld of genegeerd) en een volledige automatische controle: normaal, zonder handmatige herkomst
        let done = build([obj("A", frames: ["F0"]), obj("B", frames: ["F1"])], facades: one, frameWorld: ["F0": "w1", "F1": "w1"])
        XCTAssertEqual(find(done, .FRAME_COUNT)?.value, 2); XCTAssertEqual(find(done, .FRAME_COUNT)?.basis.duplicateReviewManual, false)
    }

    func testFacadeGapBlocksThatFacadeAndTheBuildingNotTheOtherFacade() throws {
        let facades = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"]), RoundFacade(id: "Achter", orientation: "N", worldIds: ["w1"])]
        let ps = build([obj("A", frames: ["F0"]), obj("B", frames: ["F1"], checkable: false), obj("C", facade: "Achter", frames: ["F2"])], facades: facades,
                       frameWorld: ["F0": "w1", "F1": "w1", "F2": "w1"])
        try assertBlocked(find(ps, .FRAME_COUNT, facade: "Voor"), reason: "DUPLICATE_CHECK_INCOMPLETE")
        try assertBlocked(find(ps, .FRAME_COUNT), reason: "DUPLICATE_CHECK_INCOMPLETE")
        XCTAssertEqual(find(ps, .FRAME_COUNT, facade: "Achter")?.value, 1, "gevel met één, wel vergelijkbaar object")
    }

    func testOldInputWithoutCoverageDataKeepsPreviousRules() throws {
        // invoer zonder frameWorld (oude aanroepers/tests): alleen de bestaande gevelregel; geen nieuwe blokkade op ontbrekende gegevens
        let ps = build([obj("A", frames: ["F0"]), obj("B", frames: ["F1"])], facades: one, frameWorld: nil)
        XCTAssertEqual(find(ps, .FRAME_COUNT)?.value, 2); XCTAssertEqual(find(ps, .FRAME_COUNT)?.basis.duplicateReviewComplete, true)
    }

    func testValidationRejectsCompleteCoverageWithOpenPointsAndQuantitiesWithIncompleteCoverage() throws {
        let ps = build([obj("A", frames: ["F0"], checkable: false), obj("B", frames: ["F1"])], facades: one, frameWorld: ["F0": "w1", "F1": "w1"])
        var p = try XCTUnwrap(find(ps, .FRAME_COUNT))
        p.value = 2; p.reliability.level = "CHECK_REQUIRED"
        XCTAssertTrue(p.validate().contains(.quantityWithUncheckedDuplicates))
        XCTAssertThrowsError(try ScanProposalV2.decode(try p.encoded()))
        var q = try XCTUnwrap(find(build([obj("A", frames: ["F0"])], facades: one, frameWorld: ["F0": "w1"]), .FRAME_COUNT))
        q.basis.duplicatesUnresolved = 1; q.value = nil; q.reliability.level = "INCOMPLETE"
        XCTAssertTrue(q.validate().contains(.badBasis), "volledig + openstaande suggestie kan niet")
        // het outbox-vangnet herkent ook een opgeslagen voorstel met onvolledige dekking
        var stored = try XCTUnwrap(find(build([obj("A", frames: ["F0"])], facades: one, frameWorld: ["F0": "w1"]), .FRAME_COUNT))
        stored.basis.duplicateReviewComplete = false
        let sent = stored.withUncheckedQuantitiesBlocked()
        XCTAssertNil(sent.value); XCTAssertTrue(sent.reliability.reasons.contains("DUPLICATE_CHECK_INCOMPLETE")); XCTAssertEqual(sent.validate(), [])
    }

    // MARK: pariteit met Python

    private func fixture() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "duplicate_coverage_cases", withExtension: "json", subdirectory: "Fixtures"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }

    func testEvaluateMatchesPython() throws {
        let cases = try XCTUnwrap(try fixture()["cases"] as? [[String: Any]])
        XCTAssertGreaterThan(cases.count, 10)
        for cs in cases {
            let name = cs["name"] as! String
            let objs = (cs["objects"] as! [[String: Any]]).map { o in
                obj(o["id"] as! String, frames: o["frame_ids"] as! [String], checkable: o["duplicate_checkable"] as! Bool)
            }
            let fw = (cs["facade_world_ids"] as! [[String]]).map { Set($0) }
            let frameWorld = cs["frame_world"] as? [String: String]
            let r = DuplicateCoverage.evaluate(objects: objs, facadeWorldIds: fw, frameWorld: frameWorld,
                                               duplicatesUnresolved: (cs["duplicates_unresolved"] as! NSNumber).intValue, reviewed: cs["reviewed"] as! Bool)
            let e = cs["expected"] as! [String: Any]
            XCTAssertEqual(r.crossSessionUnchecked, e["cross_session_unchecked"] as? Bool, name)
            XCTAssertEqual(r.uncheckedObjects, (e["unchecked_objects"] as! NSNumber).intValue, name)
            XCTAssertEqual(r.unknownWorldPhotos, (e["unknown_world_photos"] as! NSNumber).intValue, name)
            XCTAssertEqual(r.checkIncomplete, e["check_incomplete"] as? Bool, name)
            XCTAssertEqual(r.manual, e["manual"] as? Bool, name)
            XCTAssertEqual(r.complete, e["complete"] as? Bool, name)
        }
    }

    func testFingerprintMatchesPythonAndIgnoresOrder() throws {
        for f in try XCTUnwrap(try fixture()["fingerprints"] as? [[String: Any]]) {
            XCTAssertEqual(DuplicateCoverage.fingerprint(f["parts"] as! [String]), f["expected"] as? String)
        }
        XCTAssertNotEqual(DuplicateCoverage.fingerprint(["A|F0"]), DuplicateCoverage.fingerprint(["A|F1"]), "elke wijziging geeft een andere vingerafdruk")
    }
}
