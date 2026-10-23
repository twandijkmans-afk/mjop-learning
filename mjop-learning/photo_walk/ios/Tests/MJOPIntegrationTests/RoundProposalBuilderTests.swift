import XCTest
@testable import MJOPIntegration

final class RoundProposalBuilderTests: XCTestCase {
    let project = ScanProposalV2.Project(planRef: "plan-0123456789ab", mjopPlanId: nil, buildingId: "Kastanjelaan 12", bagPandId: "0363100012345678")

    func obj(_ id: String, facade: String = "Voor", frames: [String] = ["F000"], area: Decimal? = 1.8, sigma: Double? = 0.04, status: RoundObject.Status = .estimated,
             method: String = "LIDAR_DEPTH_MULTI_FRAME", auto: Bool = true, confirmed: Bool = false) -> RoundObject {
        RoundObject(id: id, facadeId: facade, frameIds: frames, areaM2: area, areaSigmaM2: sigma, status: status, method: method, autoDetected: auto, userConfirmed: confirmed, manual: false, flags: ["AUTO_DETECTED_UNCONFIRMED"])
    }
    func input(_ objects: [RoundObject], facades: [RoundFacade]? = nil, excluded: [String: Int] = [:], dups: [String: Int] = [:]) -> RoundBuildInput {
        RoundBuildInput(roundId: "0F3A9C1E-1111-2222-3333-444455556666", revision: 1, createdAt: "2026-10-23T10:00:00Z", project: project, elementKey: "kozijnen-onderhoud",
                        objects: objects, facades: facades ?? [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"])], excludedObjectsByFacade: excluded, duplicatesUnresolvedByFacade: dups)
    }
    func find(_ ps: [ScanProposalV2], _ kind: ScanProposalV2.Target.Kind, facade: String? = nil) -> ScanProposalV2? {
        ps.first { $0.target.quantityKind == kind && $0.target.scope.facadeId == facade }
    }

    func testCountAndAreaForOneFacade() throws {
        let ps = RoundProposalBuilder.build(input([obj("A"), obj("B", area: 2.2)]))
        XCTAssertEqual(ps.count, 2, "één gevel: alleen gebouwtotalen")
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT)); let a = try XCTUnwrap(find(ps, .FRAME_AREA_GROSS))
        XCTAssertEqual(c.value, 2); XCTAssertEqual(c.target.unit, "st"); XCTAssertEqual(c.target.elementKey, "kozijnen-onderhoud")
        XCTAssertEqual(a.value, 4.0); XCTAssertEqual(a.target.unit, "m2")
        for p in ps { XCTAssertEqual(p.validate(), [], "\(p.proposalId)"); XCTAssertFalse(p.bookingAllowed); XCTAssertEqual(p.confirmation.status, "PROPOSED"); XCTAssertFalse(p.measurement.uncertainty.validated) }
        XCTAssertTrue(c.reliability.reasons.contains("UNVALIDATED_LIDAR")); XCTAssertEqual(c.reliability.level, "CHECK_REQUIRED")
    }

    func testUnmeasuredObjectsBlockTheAreaButNotTheCount() throws {
        let ps = RoundProposalBuilder.build(input([obj("A"), obj("B", area: nil, sigma: nil, status: .unknown, method: "NONE")]))
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT)); let a = try XCTUnwrap(find(ps, .FRAME_AREA_GROSS))
        XCTAssertEqual(c.value, 2)
        XCTAssertNil(a.value, "oppervlak met onbemeten kozijn mag niet als totaal gepubliceerd worden")
        XCTAssertEqual(a.partialValue, 1.8); XCTAssertEqual(a.reliability.level, "INCOMPLETE")
        XCTAssertTrue(a.reliability.reasons.contains("UNMEASURED_OBJECTS")); XCTAssertEqual(a.basis.objectsUnmeasured, 1)
        XCTAssertEqual(a.measurement.dimensionStatus, "UNKNOWN", "slechtste status telt")
        for p in ps { XCTAssertEqual(p.validate(), []) }
    }

    func testNoObjectsGivesNilNotZero() throws {
        let ps = RoundProposalBuilder.build(input([]))
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT))
        XCTAssertNil(c.value); XCTAssertEqual(c.reliability.level, "INCOMPLETE"); XCTAssertTrue(c.reliability.reasons.contains("NO_OBJECTS"))
        XCTAssertNil(find(ps, .FRAME_AREA_GROSS)?.value)
    }

    func testExcludedObjectsAreCountedAsExcludedNotAsFrames() throws {
        let ps = RoundProposalBuilder.build(input([obj("A")], excluded: ["Voor": 3]))
        XCTAssertEqual(try XCTUnwrap(find(ps, .FRAME_COUNT)).basis.excludedObjects, 3)
        XCTAssertEqual(try XCTUnwrap(find(ps, .FRAME_COUNT)).value, 1)
    }

    func testUnresolvedDuplicatesAndCrossSessionAreFlagged() throws {
        let f = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1", "w2"])]
        let ps = RoundProposalBuilder.build(input([obj("A"), obj("B")], facades: f, dups: ["Voor": 2]))
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT))
        XCTAssertEqual(c.basis.duplicatesUnresolved, 2); XCTAssertTrue(c.basis.crossSessionUnchecked)
        XCTAssertTrue(c.reliability.reasons.contains("DUPLICATES_UNRESOLVED")); XCTAssertTrue(c.reliability.reasons.contains("CROSS_SESSION_UNCHECKED"))
        XCTAssertEqual(c.validate(), [])
    }

    func testConfirmedByHumanRemovesAutoDetectedReason() throws {
        let ps = RoundProposalBuilder.build(input([obj("A", confirmed: true)]))
        XCTAssertFalse(try XCTUnwrap(find(ps, .FRAME_COUNT)).reliability.reasons.contains("AUTO_DETECTED"))
        XCTAssertEqual(try XCTUnwrap(find(ps, .FRAME_COUNT)).evidence.detection.userCorrected, 1)
    }

    func testPerFacadeProposalsOnlyWithMultipleFacades() throws {
        let facades = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"]), RoundFacade(id: "Achter", orientation: "N", worldIds: ["w1"])]
        let ps = RoundProposalBuilder.build(input([obj("A"), obj("B", facade: "Achter", frames: ["F001"])], facades: facades))
        XCTAssertEqual(ps.count, 6)
        let voorArea = try XCTUnwrap(find(ps, .FRAME_AREA_GROSS, facade: "Voor"))
        XCTAssertEqual(voorArea.value, 1.8); XCTAssertEqual(voorArea.target.scope.orientation, "S"); XCTAssertEqual(voorArea.basis.photos, 1)
        XCTAssertEqual(try XCTUnwrap(find(ps, .FRAME_COUNT)).value, 2)
        XCTAssertEqual(Set(ps.map { $0.proposalId }).count, ps.count, "unieke id's")
        for p in ps { XCTAssertEqual(p.validate(), [], p.proposalId) }
    }

    func testFacadeWithoutObjectsGetsNoProposal() {
        let facades = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"]), RoundFacade(id: "Leeg", orientation: nil, worldIds: [])]
        let ps = RoundProposalBuilder.build(input([obj("A")], facades: facades))
        XCTAssertNil(find(ps, .FRAME_COUNT, facade: "Leeg"))
    }

    func testIdsAreStableAndRevisionedAndContractSafe() throws {
        let a = RoundProposalBuilder.build(input([obj("A")]))
        let b = RoundProposalBuilder.build(input([obj("A")]))
        XCTAssertEqual(a.map { $0.proposalId }, b.map { $0.proposalId })
        var i2 = input([obj("A")]); i2.revision = 2
        let c = RoundProposalBuilder.build(i2)
        XCTAssertNotEqual(a.map { $0.proposalId }, c.map { $0.proposalId })
        for p in a { XCTAssertNotNil(p.proposalId.range(of: "^[A-Za-z0-9_.-]{8,80}$", options: .regularExpression)); XCTAssertNotNil(p.roundId.range(of: "^[A-Za-z0-9_.-]{8,80}$", options: .regularExpression)) }
    }

    func testAreaSigmaCombinesIndependentErrors() throws {
        let ps = RoundProposalBuilder.build(input([obj("A", sigma: 0.03), obj("B", sigma: 0.04)]))
        XCTAssertEqual(try XCTUnwrap(find(ps, .FRAME_AREA_GROSS)).measurement.uncertainty.areaSigmaM2, 0.05)
    }
}

final class ProposalOutboxTests: XCTestCase {
    func proposal(plan: String, id: String = "r1a2b3c4-count-bld-r1") -> ScanProposalV2 {
        var p = ScanProposalV2(proposalId: id, roundId: "r1a2b3c4-demo", revision: 1, createdAt: "2026-10-23T10:00:00Z",
                               project: .init(planRef: plan, mjopPlanId: nil, buildingId: "B", bagPandId: nil),
                               target: .init(elementKey: nil, quantityKind: .FRAME_COUNT, unit: "st", scope: .init(type: .BUILDING, facadeId: nil, orientation: nil)),
                               value: 3, partialValue: nil, basis: .init(objectsTotal: 3, objectsMeasured: 3, objectsUnmeasured: 0, photos: 1, duplicatesUnresolved: 0, crossSessionUnchecked: false, excludedObjects: 0),
                               measurement: .init(methods: [], dimensionStatus: "ESTIMATED", uncertainty: .init(validated: false, areaSigmaM2: nil, note: "x")),
                               evidence: .init(photoIds: ["F000"], objectIds: ["A"], qualityFlags: [], detection: .init(autoDetected: 3, userCorrected: 0, manual: 0)),
                               reliability: .init(level: "CHECK_REQUIRED", reasons: ["UNVALIDATED_LIDAR"]))
        p.revision = 1
        return p
    }

    func testOnlyOwnProjectAndOnlyCompletedRoundsAreOffered() {
        var o = ProposalOutbox()
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r1x")]))
        o.upsert(.init(roundId: "B", planRef: "plan-BBBBBBBB", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [proposal(plan: "plan-BBBBBBBB", id: "idB-count-r1x")]))
        o.upsert(.init(roundId: "C", planRef: "plan-AAAAAAAA", status: "IN_PROGRESS", photos: 1, objects: 1, revision: 1, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idC-count-r1x")]))
        XCTAssertEqual(o.proposals(forPlan: "plan-AAAAAAAA").map { $0.proposalId }, ["idA-count-r1x"], "ander project en onafgeronde ronde worden niet aangeboden")
        XCTAssertEqual(o.proposals(forPlan: "plan-ZZZZZZZZ"), [])
    }

    func testAckOnlyMarksOwnIdsAndIsIdempotent() {
        var o = ProposalOutbox()
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r1x")]))
        o.ack(planRef: "plan-BBBBBBBB", proposalIds: ["idA-count-r1x"])
        XCTAssertFalse(o.rounds[0].isSynced, "ack van een ander project telt niet")
        o.ack(planRef: "plan-AAAAAAAA", proposalIds: ["idA-count-r1x", "onbekend-id-xx", "idA-count-r1x"])
        XCTAssertTrue(o.rounds[0].isSynced); XCTAssertEqual(o.rounds[0].deliveredIds, ["idA-count-r1x"])
    }

    func testProposalsStayOfferedAfterAck() {
        var o = ProposalOutbox()
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r1x")]))
        o.ack(planRef: "plan-AAAAAAAA", proposalIds: ["idA-count-r1x"])
        XCTAssertEqual(o.proposals(forPlan: "plan-AAAAAAAA").count, 1, "niets gaat verloren als de website-staat verdwijnt voordat het plan is opgeslagen")
    }

    func testReCompletingKeepsDeliveredOnlyForSurvivingIds() {
        var o = ProposalOutbox()
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r1x")]))
        o.ack(planRef: "plan-AAAAAAAA", proposalIds: ["idA-count-r1x"])
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 2, objects: 4, revision: 2, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r2x")]))
        XCTAssertEqual(o.rounds.count, 1); XCTAssertFalse(o.rounds[0].isSynced, "nieuwe revisie is nog niet overgedragen")
    }
}
