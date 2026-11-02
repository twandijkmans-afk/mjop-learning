import XCTest
@testable import MJOPIntegration

final class RoundProposalBuilderTests: XCTestCase {
    let project = ScanProposalV2.Project(planRef: "plan-0123456789ab", mjopPlanId: nil, buildingId: "Kastanjelaan 12", bagPandId: "0363100012345678")

    func obj(_ id: String, facade: String = "Voor", frames: [String] = ["F000"], area: Decimal? = 1.8, sigma: Double? = 0.04, status: RoundObject.Status = .estimated,
             method: String = "LIDAR_DEPTH_MULTI_FRAME", auto: Bool = true, confirmed: Bool = false) -> RoundObject {
        RoundObject(id: id, facadeId: facade, frameIds: frames, areaM2: area, areaSigmaM2: sigma, status: status, method: method, autoDetected: auto, userConfirmed: confirmed, manual: false, flags: ["AUTO_DETECTED_UNCONFIRMED"])
    }
    func input(_ objects: [RoundObject], facades: [RoundFacade]? = nil, excluded: [String: Int] = [:], dups: [String: Int] = [:], dupTotal: Int? = nil) -> RoundBuildInput {
        RoundBuildInput(roundId: "0F3A9C1E-1111-2222-3333-444455556666", revision: 1, createdAt: "2026-10-23T10:00:00Z", project: project, elementKey: "kozijnen-onderhoud",
                        objects: objects, facades: facades ?? [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"])], excludedObjectsByFacade: excluded, duplicatesUnresolvedByFacade: dups,
                        duplicatesUnresolvedTotal: dupTotal)
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

    /// Audit gevelopbouw: een automatisch herkende, onbevestigde buitencontour mag geen aantal of oppervlak in een voorstel opleveren.
    func testUnconfirmedContoursBlockCountAndArea() throws {
        let unconfirmed = RoundObject(id: "U", facadeId: "Voor", frameIds: ["F000"], areaM2: nil, areaSigmaM2: nil, status: .unknown, method: "NONE",
                                      autoDetected: true, userConfirmed: false, manual: false, flags: ["OUTER_CONTOUR_UNVERIFIED"], contourUnconfirmed: true)
        let ps = RoundProposalBuilder.build(input([obj("A", confirmed: true), unconfirmed]))
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT)); let a = try XCTUnwrap(find(ps, .FRAME_AREA_GROSS))
        XCTAssertNil(c.value, "aantal met een onbevestigde contour is onvolledig")
        XCTAssertNil(c.partialValue, "geen deelaantal dat als hoeveelheid gebruikt kan worden")
        XCTAssertEqual(c.reliability.level, "INCOMPLETE")
        XCTAssertNil(a.value); XCTAssertEqual(a.partialValue, 1.8, "deelsom alleen informatief, uit het bevestigde kozijn")
        XCTAssertTrue(a.reliability.reasons.contains("UNMEASURED_OBJECTS")); XCTAssertTrue(c.reliability.reasons.contains("AUTO_DETECTED"))
        for p in ps { XCTAssertEqual(p.validate(), [], p.proposalId); XCTAssertFalse(p.bookingAllowed) }
        // alleen onbevestigde contouren: geen aantal, geen oppervlak, geen deelwaarden
        let only = RoundProposalBuilder.build(input([unconfirmed]))
        XCTAssertNil(find(only, .FRAME_COUNT)?.value); XCTAssertNil(find(only, .FRAME_AREA_GROSS)?.value); XCTAssertNil(find(only, .FRAME_AREA_GROSS)?.partialValue)
        // oude (LEGACY) objecten: contourUnconfirmed = false (standaard) -> gedrag ongewijzigd
        let legacy = RoundProposalBuilder.build(input([obj("A"), obj("B", area: 2.2)]))
        XCTAssertEqual(find(legacy, .FRAME_COUNT)?.value, 2); XCTAssertEqual(find(legacy, .FRAME_AREA_GROSS)?.value, 4.0)
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

    // MARK: mogelijke dubbeltelling blokkeert aantal én oppervlak (issue A)

    private let crossFacade = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1", "w2"])]

    /// Geblokkeerd voorstel: geen waarde, geen deelwaarde, INCOMPLETE, geldig volgens de eigen regels; basis en bewijs onaangetast.
    private func assertBlocked(_ p: ScanProposalV2?, reasons: [String], file: StaticString = #filePath, line: UInt = #line) throws {
        let p = try XCTUnwrap(p, file: file, line: line)
        XCTAssertNil(p.value, "\(p.proposalId): geen waarde", file: file, line: line)
        XCTAssertNil(p.partialValue, "\(p.proposalId): geen deelwaarde", file: file, line: line)
        XCTAssertEqual(p.reliability.level, "INCOMPLETE", file: file, line: line)
        for r in reasons { XCTAssertTrue(p.reliability.reasons.contains(r), "\(p.proposalId) mist \(r)", file: file, line: line) }
        XCTAssertEqual(p.validate(), [], p.proposalId, file: file, line: line)
        XCTAssertTrue(p.quantityBlocked, file: file, line: line)
    }

    func testUnresolvedDuplicatesBlockCount() throws {
        try assertBlocked(find(RoundProposalBuilder.build(input([obj("A", confirmed: true), obj("B", confirmed: true)], dups: ["Voor": 1])), .FRAME_COUNT), reasons: ["DUPLICATES_UNRESOLVED"])
    }

    func testUnresolvedDuplicatesBlockArea() throws {
        try assertBlocked(find(RoundProposalBuilder.build(input([obj("A"), obj("B", area: 2.2)], dups: ["Voor": 1])), .FRAME_AREA_GROSS), reasons: ["DUPLICATES_UNRESOLVED"])
        // ook geen deelsom als er daarnaast onbemeten kozijnen zijn
        let mixed = RoundProposalBuilder.build(input([obj("A"), obj("B", area: nil, sigma: nil, status: .unknown, method: "NONE")], dups: ["Voor": 1]))
        try assertBlocked(find(mixed, .FRAME_AREA_GROSS), reasons: ["DUPLICATES_UNRESOLVED", "UNMEASURED_OBJECTS"])
    }

    func testCrossSessionUncheckedBlocksCount() throws {
        let c = find(RoundProposalBuilder.build(input([obj("A", confirmed: true), obj("B", confirmed: true)], facades: crossFacade)), .FRAME_COUNT)
        try assertBlocked(c, reasons: ["CROSS_SESSION_UNCHECKED"])
        XCTAssertFalse(c!.reliability.reasons.contains("DUPLICATES_UNRESOLVED"))
    }

    func testCrossSessionUncheckedBlocksArea() throws {
        try assertBlocked(find(RoundProposalBuilder.build(input([obj("A"), obj("B", area: 2.2)], facades: crossFacade)), .FRAME_AREA_GROSS), reasons: ["CROSS_SESSION_UNCHECKED"])
        let mixed = RoundProposalBuilder.build(input([obj("A"), obj("B", area: nil, sigma: nil, status: .unknown, method: "NONE")], facades: crossFacade))
        try assertBlocked(find(mixed, .FRAME_AREA_GROSS), reasons: ["CROSS_SESSION_UNCHECKED", "UNMEASURED_OBJECTS"])
    }

    func testBothConditionsBlockBothKindsAndKeepEvidence() throws {
        let ps = RoundProposalBuilder.build(input([obj("A", frames: ["F000", "F001"]), obj("B", frames: ["F002"], area: 2.2)], facades: crossFacade, dups: ["Voor": 2]))
        XCTAssertEqual(ps.count, 2)
        for p in ps {
            try assertBlocked(p, reasons: ["DUPLICATES_UNRESOLVED", "CROSS_SESSION_UNCHECKED", "UNVALIDATED_LIDAR"])
            // bewijs en diagnose blijven beschikbaar voor de beoordeling
            XCTAssertEqual(p.basis.duplicatesUnresolved, 2); XCTAssertTrue(p.basis.crossSessionUnchecked)
            XCTAssertEqual(p.basis.objectsTotal, 2); XCTAssertEqual(p.basis.objectsMeasured, 2); XCTAssertEqual(p.basis.photos, 3)
            XCTAssertEqual(p.evidence.objectIds, ["A", "B"]); XCTAssertEqual(p.evidence.photoIds, ["F000", "F001", "F002"])
            XCTAssertEqual(p.evidence.detection.autoDetected, 2); XCTAssertTrue(p.evidence.qualityFlags.contains("AUTO_DETECTED_UNCONFIRMED"))
            XCTAssertEqual(p.measurement.methods, ["LIDAR_DEPTH_MULTI_FRAME"])
            XCTAssertFalse(p.bookingAllowed); XCTAssertEqual(p.confirmation.status, "PROPOSED")
        }
    }

    func testResolvedDuplicatesAndCheckedSessionsKeepNormalBehaviour() throws {
        let ps = RoundProposalBuilder.build(input([obj("A", confirmed: true), obj("B", area: 2.2, confirmed: true)], dups: ["Voor": 0]))
        let c = try XCTUnwrap(find(ps, .FRAME_COUNT)), a = try XCTUnwrap(find(ps, .FRAME_AREA_GROSS))
        XCTAssertEqual(c.value, 2); XCTAssertEqual(a.value, 4.0); XCTAssertNil(a.partialValue)
        XCTAssertEqual(c.reliability.level, "CHECK_REQUIRED"); XCTAssertEqual(a.reliability.level, "CHECK_REQUIRED")
        XCTAssertFalse(c.quantityBlocked)
        for p in ps { XCTAssertFalse(p.reliability.reasons.contains("DUPLICATES_UNRESOLVED")); XCTAssertFalse(p.reliability.reasons.contains("CROSS_SESSION_UNCHECKED")) }
        // de bestaande regels blijven gelden: onbemeten kozijn -> oppervlak nil met deelsom, aantal blijft
        let partial = RoundProposalBuilder.build(input([obj("A"), obj("B", area: nil, sigma: nil, status: .unknown, method: "NONE")]))
        XCTAssertEqual(find(partial, .FRAME_COUNT)?.value, 2); XCTAssertEqual(find(partial, .FRAME_AREA_GROSS)?.partialValue, 1.8)
    }

    func testDuplicatesOnOneFacadeBlockThatFacadeAndTheBuildingOnly() throws {
        let facades = [RoundFacade(id: "Voor", orientation: "S", worldIds: ["w1"]), RoundFacade(id: "Achter", orientation: "N", worldIds: ["w1"])]
        let ps = RoundProposalBuilder.build(input([obj("A"), obj("B"), obj("C", facade: "Achter", frames: ["F001"])], facades: facades, dups: ["Voor": 1], dupTotal: 1))
        try assertBlocked(find(ps, .FRAME_COUNT), reasons: ["DUPLICATES_UNRESOLVED"])
        try assertBlocked(find(ps, .FRAME_AREA_GROSS), reasons: ["DUPLICATES_UNRESOLVED"])
        try assertBlocked(find(ps, .FRAME_COUNT, facade: "Voor"), reasons: ["DUPLICATES_UNRESOLVED"])
        XCTAssertEqual(find(ps, .FRAME_COUNT, facade: "Achter")?.value, 1, "gevel zonder mogelijke duplicaten: ongewijzigd")
        // suggestie tussen twee gevels: beide gevels geblokkeerd, gebouw telt de suggestie één keer
        let cross = RoundProposalBuilder.build(input([obj("A"), obj("C", facade: "Achter", frames: ["F001"])], facades: facades, dups: ["Voor": 1, "Achter": 1], dupTotal: 1))
        XCTAssertEqual(find(cross, .FRAME_COUNT)?.basis.duplicatesUnresolved, 1)
        try assertBlocked(find(cross, .FRAME_COUNT, facade: "Achter"), reasons: ["DUPLICATES_UNRESOLVED"])
        try assertBlocked(find(cross, .FRAME_AREA_GROSS, facade: "Voor"), reasons: ["DUPLICATES_UNRESOLVED"])
    }

    func testValidationRejectsAQuantityWithUncheckedDuplicates() throws {
        let ok = try XCTUnwrap(find(RoundProposalBuilder.build(input([obj("A"), obj("B")], dups: ["Voor": 1])), .FRAME_COUNT))
        var v = ok; v.value = 2; v.reliability.level = "CHECK_REQUIRED"
        XCTAssertTrue(v.validate().contains(.quantityWithUncheckedDuplicates), "waarde bij mogelijke duplicaten")
        var p = ok; p.partialValue = 2
        XCTAssertTrue(p.validate().contains(.quantityWithUncheckedDuplicates), "deelwaarde bij mogelijke duplicaten")
        var l = ok; l.reliability.level = "CHECK_REQUIRED"
        XCTAssertTrue(l.validate().contains(.quantityWithUncheckedDuplicates), "niveau moet INCOMPLETE zijn")
        XCTAssertThrowsError(try ScanProposalV2.decode(try v.encoded()), "een ontvangen voorstel met zo'n waarde wordt geweigerd")
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

    /// Een vóór deze regel opgeslagen voorstel met een waarde ondanks mogelijke duplicaten gaat zonder waarde naar de website;
    /// het opgeslagen voorstel (outbox) zelf wordt niet gewijzigd.
    func testStoredProposalWithUncheckedDuplicatesIsSentWithoutValue() throws {
        var old = proposal(plan: "plan-AAAAAAAA", id: "idA-count-r1x")
        old.basis.duplicatesUnresolved = 1; old.basis.crossSessionUnchecked = true
        XCTAssertEqual(old.value, 3); XCTAssertEqual(old.reliability.level, "CHECK_REQUIRED")
        var o = ProposalOutbox()
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [old, proposal(plan: "plan-AAAAAAAA", id: "idB-count-r1x")]))
        let sent = o.proposals(forPlan: "plan-AAAAAAAA")
        let blocked = try XCTUnwrap(sent.first { $0.proposalId == "idA-count-r1x" })
        XCTAssertNil(blocked.value); XCTAssertNil(blocked.partialValue); XCTAssertEqual(blocked.reliability.level, "INCOMPLETE")
        XCTAssertTrue(blocked.reliability.reasons.contains("DUPLICATES_UNRESOLVED")); XCTAssertTrue(blocked.reliability.reasons.contains("CROSS_SESSION_UNCHECKED"))
        XCTAssertEqual(blocked.basis, old.basis); XCTAssertEqual(blocked.evidence, old.evidence); XCTAssertEqual(blocked.validate(), [])
        XCTAssertEqual(sent.first { $0.proposalId == "idB-count-r1x" }?.value, 3, "voorstel zonder mogelijke duplicaten ongewijzigd")
        XCTAssertEqual(o.rounds[0].proposals[0].value, 3, "opgeslagen gegevens blijven ongewijzigd")
        // wat de brug verstuurt (jsonObject) bevat de waarde ook niet
        let json = try XCTUnwrap(blocked.jsonObject())
        XCTAssertTrue(json["value"] is NSNull); XCTAssertTrue(json["partial_value"] is NSNull)
    }

    func testReCompletingKeepsDeliveredOnlyForSurvivingIds() {
        var o = ProposalOutbox()
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 1, objects: 3, revision: 1, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r1x")]))
        o.ack(planRef: "plan-AAAAAAAA", proposalIds: ["idA-count-r1x"])
        o.upsert(.init(roundId: "A", planRef: "plan-AAAAAAAA", status: "COMPLETED", photos: 2, objects: 4, revision: 2, proposals: [proposal(plan: "plan-AAAAAAAA", id: "idA-count-r2x")]))
        XCTAssertEqual(o.rounds.count, 1); XCTAssertFalse(o.rounds[0].isSynced, "nieuwe revisie is nog niet overgedragen")
    }
}
