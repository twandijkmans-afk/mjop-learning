import XCTest
@testable import Gevelscan
import MJOPIntegration
import PhotoWalkCore

/// Integratie: een volledige fotoronde door de hele pijplijn, tot en met het contract, de outbox en het brugbericht naar de website.
final class PipelineTests: XCTestCase {
    // Voorgevel: kozijn A (2 vakken) en B (3 vakken); zijgevel (andere scansessie): kozijn C.
    let a = SynWindow(x0: 0.6, y0: 0.9, w: 1.2, h: 1.5, cols: 2)
    let b = SynWindow(x0: 2.4, y0: 0.9, w: 1.5, h: 1.5, cols: 3)
    let c = SynWindow(x0: 1.0, y0: 0.7, w: 0.9, h: 1.8)
    let project = ScanProposalV2.Project(planRef: "plan-abc12345", mjopPlanId: "11111111-2222", buildingId: "Singelstraat 8", bagPandId: "0363100012345678")

    func round(validation: PipelineValidation = .current, confirmed: Bool = false, userParts: Bool = false, secondViewOfC: Bool = true) -> (GevelscanInput, [ViewInput]) {
        let v1 = Syn.render([a, b], pos: Vec3(1.9, 1.6, 3.8), id: "F001", seed: 1)
        let v2 = Syn.render([a, b], pos: Vec3(2.6, 1.6, 3.8), id: "F002", seed: 2, yawDeg: 4)
        let v3 = Syn.render([a, b], pos: Vec3(2.25, 1.7, 3.7), id: "F003", seed: 3, yawDeg: -2)
        let s1 = Syn.render([c], pos: Vec3(1.2, 1.6, 3.2), id: "F004", seed: 4), s2 = Syn.render([c], pos: Vec3(1.9, 1.6, 3.2), id: "F005", seed: 5, yawDeg: 6)
        var sightings: [FrameSighting] = []
        for (k, v) in [v1, v2, v3].enumerated() {
            sightings.append(Syn.sighting(a, view: v, id: "OBS-F00\(k + 1)-01", confirmed: confirmed))
            sightings.append(Syn.sighting(b, view: v, id: "OBS-F00\(k + 1)-02", confirmed: confirmed))
        }
        sightings.append(Syn.sighting(c, view: s1, id: "OBS-F004-01", facade: "Zijgevel", world: "W2", confirmed: confirmed))
        if secondViewOfC { sightings.append(Syn.sighting(c, view: s2, id: "OBS-F005-01", facade: "Zijgevel", world: "W2", confirmed: confirmed)) }
        let photos = [v1, v2, v3].map { Syn.photo($0) } + [s1, s2].map { Syn.photo($0, facade: "Zijgevel", world: "W2") }
        var parts: [String: UserParts] = [:]
        if userParts { parts = ["OBS-F001-01": .init(operableParts: 1, fixedParts: 1), "OBS-F002-02": .init(operableParts: 2, fixedParts: 1), "OBS-F004-01": .init(operableParts: 1, fixedParts: 0)] }
        return (GevelscanInput(roundId: "3F2A9C10-AAAA-BBBB-CCCC-000000000001", facades: [.init(id: "Voorgevel", orientation: "S"), .init(id: "Zijgevel", orientation: "W")],
                               photos: photos, sightings: sightings, userParts: parts, validation: validation), [v1, v2, v3, s1, s2])
    }

    func testFullRoundCountsEachFrameOnceAndKeepsQuantitiesSeparate() {
        let r = GevelscanPipeline.run(round().0)
        XCTAssertEqual(r.facades.map { $0.facadeId }, ["Voorgevel", "Zijgevel"])
        let front = r.facades[0], side = r.facades[1]
        XCTAssertEqual(front.objects.count, 2); XCTAssertEqual(side.objects.count, 1)        // 8 waarnemingen -> 3 kozijnen
        XCTAssertEqual(front.totals.frameCount.value, 2); XCTAssertEqual(side.totals.frameCount.value, 1)
        XCTAssertEqual(front.totals.frameAreaGross.value ?? 0, 1.2 * 1.5 + 1.5 * 1.5, accuracy: 0.12)
        XCTAssertEqual(front.totals.glassArea.value ?? 0, a.glassAreaM2 + b.glassAreaM2, accuracy: 0.25)
        XCTAssertLessThan(front.totals.glassArea.value ?? 9, front.totals.frameAreaGross.value ?? 0)
        XCTAssertEqual(front.objects.map { $0.geometry.sections.value }.compactMap { $0 }.sorted(), [2, 3])     // vakken zijn geen kozijnen
        // draaiende delen: geen model, dus onbekend — en dat blokkeert de andere hoeveelheden niet
        XCTAssertNil(front.totals.operableParts.value); XCTAssertTrue(front.totals.operableParts.missing.contains("GEEN_MODEL_VOOR_DRAAIENDE_DELEN"))
        XCTAssertNil(front.totals.doorCount.value)
        // herkomst per hoeveelheid
        XCTAssertEqual(front.totals.frameCount.origin, .COUNTED_FROM_ASSOCIATION)
        XCTAssertEqual(front.totals.frameAreaGross.origin, .DERIVED_CALCULATION)
        XCTAssertEqual(front.totals.glassArea.origin, .DERIVED_SEGMENTATION_ON_MEASURED_PLANE)
        // gebouw: gevels uit verschillende scansessies zijn onderling niet vergeleken
        XCTAssertEqual(r.building.frameCount.value, 3); XCTAssertTrue(r.building.frameCount.missing.contains("GEVELS_ONDERLING_NIET_VERGELEKEN"))
        XCTAssertEqual(r.building.frameCount.outcome, .VOORLOPIG_VASTGESTELD)
    }

    func testNothingIsAutoProcessedWhileThePipelineIsUnvalidated() {
        let r = GevelscanPipeline.run(round(confirmed: true).0)
        XCTAssertFalse(r.autoProcessingAllowed)
        XCTAssertTrue(r.objects.allSatisfy { $0.outcome == .VOORLOPIG_VASTGESTELD })
        XCTAssertTrue(r.objects.allSatisfy { $0.outcomeReasons == ["GEOMETRIE_NIET_IN_HET_VELD_GEVALIDEERD", "HERKENNING_NIET_GEVALIDEERD"] }, "\(r.objects.map { $0.outcomeReasons })")
        XCTAssertTrue(r.facades.allSatisfy { $0.completeness == .VOORLOPIG_VASTGESTELD })
    }

    func testThreeOutcomeClassesWithAValidatedPipeline() {
        // betrouwbaar: twee standpunten, contour zeker, alles in beeld
        let ok = GevelscanPipeline.run(round(validation: Syn.validated, confirmed: true).0)
        XCTAssertTrue(ok.facades[0].objects.allSatisfy { $0.outcome == .BETROUWBAAR_VASTGESTELD }, "\(ok.facades[0].objects.map { $0.outcomeReasons })")
        XCTAssertEqual(ok.facades[0].totals.frameCount.outcome, .BETROUWBAAR_VASTGESTELD)
        XCTAssertEqual(ok.facades[0].totals.frameAreaGross.outcome, .BETROUWBAAR_VASTGESTELD)
        // voorlopig: zijgevel met maar één foto van het kozijn
        let single = GevelscanPipeline.run(round(validation: Syn.validated, confirmed: true, secondViewOfC: false).0)
        let c = single.facades[1].objects[0]
        XCTAssertEqual(c.outcome, .VOORLOPIG_VASTGESTELD); XCTAssertTrue(c.outcomeReasons.contains("ENKEL_STANDPUNT"))
        XCTAssertTrue(single.facades[1].requests.contains { $0.kind == .ANDERE_HOEK && $0.objectId == c.id })
        XCTAssertFalse(single.autoProcessingAllowed)
        // niet vast te stellen: geen LiDAR
        var (input, views) = round(validation: Syn.validated, confirmed: true)
        let plain = Syn.render([self.c], pos: views[3].pose.t, id: "F004", withDepth: false), plain2 = Syn.render([self.c], pos: views[4].pose.t, id: "F005", withDepth: false)
        input.photos = input.photos.filter { $0.facadeId == "Voorgevel" } + [Syn.photo(plain, facade: "Zijgevel", world: "W2"), Syn.photo(plain2, facade: "Zijgevel", world: "W2")]
        input.sightings = input.sightings.filter { $0.facadeId == "Voorgevel" } + [Syn.sighting(self.c, view: plain, id: "OBS-F004-01", facade: "Zijgevel", world: "W2", confirmed: true)]
        let none = GevelscanPipeline.run(input)
        let o = none.facades[1].objects[0]
        XCTAssertEqual(o.outcome, .NIET_VAST_TE_STELLEN); XCTAssertNil(o.geometry.area.value)
        XCTAssertNil(none.facades[1].totals.frameAreaGross.value)                           // geen verzonnen oppervlak
        XCTAssertEqual(none.facades[1].totals.frameCount.value, 1)                          // het kozijn is wel geteld
        XCTAssertTrue(none.facades[1].requests.contains { $0.kind == .BETERE_DIEPTE })
        XCTAssertNil(none.building.frameAreaGross.value); XCTAssertNotNil(none.building.frameAreaGross.partial)
    }

    func testAutomaticContourNeedsCorroborationOrConfirmation() {
        // terugliggend kozijn + glasvlakken + twee standpunten: automatisch ondersteund door de diepte-sprong op de kozijnrand
        let auto = GevelscanPipeline.run(round(validation: Syn.validated).0)
        XCTAssertTrue(auto.facades[0].objects.allSatisfy { $0.contourEvidence == .AUTO_CORROBORATED }, "\(auto.facades[0].objects.map { $0.contourEvidence })")
        // zonder glasvlakken (losse rechthoek): geen bewijs dat dit de buitencontour is
        var (input, _) = round(validation: Syn.validated)
        for k in input.sightings.indices { input.sightings[k].panes = []; input.sightings[k].evidence = .SINGLE }
        let loose = GevelscanPipeline.run(input)
        XCTAssertTrue(loose.objects.allSatisfy { $0.contourEvidence == .AUTO_UNCONFIRMED && $0.outcome == .VOORLOPIG_VASTGESTELD && $0.outcomeReasons.contains("BUITENCONTOUR_NIET_BEVESTIGD") })
        XCTAssertEqual(loose.facades[0].totals.frameCount.outcome, .VOORLOPIG_VASTGESTELD)
    }

    func testUncertainIdentityBlocksEveryQuantityOfThatFacade() {
        var (input, views) = round()
        var extra = Syn.sighting(a, view: views[1], id: "OBS-F002-09")
        extra.polygon = scalePolygon(extra.polygon, 0.62)                                   // binnenvak op dezelfde foto als extra "kozijn"
        input.sightings.append(extra)
        let r = GevelscanPipeline.run(input)
        let front = r.facades[0]
        XCTAssertTrue(front.objects.contains { $0.identity == .UNCERTAIN })
        for q in [front.totals.frameCount, front.totals.frameAreaGross, front.totals.glassArea] {
            XCTAssertNil(q.value); XCTAssertNil(q.partial); XCTAssertTrue(q.missing.contains("MOGELIJK_DUBBEL_GETELD"))
        }
        XCTAssertNil(r.building.frameCount.value)
        XCTAssertEqual(r.facades[1].totals.frameCount.value, 1)                             // de andere gevel is er niet door geraakt
    }

    func testTruncatedObjectAsksForTheRightPhoto() {
        // camera te laag gericht: het kozijn loopt onder uit beeld
        let tall = SynWindow(x0: 1.0, y0: 0.2, w: 0.9, h: 2.3)
        let v = Syn.render([tall], pos: Vec3(1.45, 2.4, 2.2), id: "F001")
        var s = Syn.sighting(tall, view: v, id: "OBS-F001-01")
        s.polygon = s.polygon.map { Pixel($0.u, min($0.v, 1439)) }
        XCTAssertEqual(DetectionGeometry.truncatedSides(s.polygon, width: 1920, height: 1440, marginPx: 6), [.BOTTOM])
        let r = GevelscanPipeline.run(GevelscanInput(roundId: "ROUND-0001", facades: [.init(id: "Voorgevel", orientation: nil)], photos: [Syn.photo(v)], sightings: [s]))
        XCTAssertEqual(r.objects[0].truncatedBy, [.BOTTOM])
        XCTAssertTrue(r.requests.contains { $0.kind == .ONDERZIJDE_GEVEL })
        XCTAssertNotEqual(r.objects[0].outcome, .BETROUWBAAR_VASTGESTELD)
    }

    func testEmptyFacadeIsUnknownNotZero() {
        let v = Syn.render([], pos: Vec3(1.5, 1.6, 3), id: "F001")
        let r = GevelscanPipeline.run(GevelscanInput(roundId: "ROUND-0001", facades: [.init(id: "Voorgevel", orientation: nil), .init(id: "Achtergevel", orientation: nil)], photos: [Syn.photo(v)], sightings: []))
        XCTAssertNil(r.facades[0].totals.frameCount.value)                                  // niets herkend is geen bewijs voor "0 kozijnen"
        XCTAssertEqual(r.facades[0].completenessReasons, ["GEEN_OBJECTEN_HERKEND"])
        XCTAssertEqual(r.facades[1].completenessReasons, ["GEEN_FOTOS"])
    }

    func testPipelineIsDeterministic() {
        let (input, _) = round(userParts: true)
        var shuffled = input; shuffled.sightings.reverse(); shuffled.photos.reverse()
        XCTAssertEqual(GevelscanPipeline.run(input), GevelscanPipeline.run(shuffled))
    }

    // MARK: contract, outbox, brug

    func contract(userParts: Bool = true, revision: Int = 1) throws -> GevelInventoryV1 {
        let (input, _) = round(userParts: userParts)
        return try InventoryContractBuilder.build(result: GevelscanPipeline.run(input), photos: input.photos, project: project, elementKey: nil, revision: revision, createdAt: "2026-11-11T10:15:00Z")
    }

    func testContractCarriesEvidenceProvenanceAndVersions() throws {
        let inv = try contract()
        XCTAssertEqual(inv.planRef, "plan-abc12345"); XCTAssertEqual(inv.revision, 1)
        let body = inv.body
        XCTAssertEqual(body["booking_allowed"]?.bool, false)
        XCTAssertEqual(body["validation"]?["auto_processing_allowed"]?.bool, false)
        XCTAssertEqual(body["versions"]?["pipeline"]?.string, "gevelscan-2.0.0")
        XCTAssertEqual(body["versions"]?["thresholds_status"]?.string, "PROVISIONAL_UNVALIDATED")
        XCTAssertEqual(body["recognition"]?["not_recognizable"]?.array?.contains(.string("DRAAIEND_DEEL")), true)
        let front = try XCTUnwrap(body["facades"]?.array?.first)
        XCTAssertEqual(front["totals"]?["frame_count"]?["value"]?.double, 2)
        XCTAssertEqual(front["totals"]?["operable_parts"]?["value"]?.double, 3)             // 1 + 2, door de gebruiker ingevoerd
        XCTAssertEqual(front["totals"]?["operable_parts"]?["origin"]?.string, "USER_INPUT")
        let obj = try XCTUnwrap(front["objects"]?.array?.first)
        XCTAssertEqual(obj["photo_ids"]?.array?.count, 3); XCTAssertEqual(obj["sighting_ids"]?.array?.count, 3)
        XCTAssertEqual(obj["width"]?["origin"]?.string, "LIDAR_PLANE_MEASUREMENT")
        XCTAssertEqual(obj["glass_area"]?["origin"]?.string, "DERIVED_SEGMENTATION_ON_MEASURED_PLANE")
        XCTAssertNotNil(obj["width"]?["sigma"]?.double)
        XCTAssertEqual(obj["nen2767_condition_score"], .null)
        XCTAssertEqual(obj["condition"]?.array?.first?["kind"]?.string, "NIET_BEOORDEELBAAR")
        let photo = try XCTUnwrap(body["photos"]?.array?.first)
        XCTAssertEqual(photo["depth_source"]?.string, "LIDAR_SCENE_DEPTH"); XCTAssertEqual(photo["intrinsics"]?["fx"]?.double, 1500)
        XCTAssertEqual(photo["camera_position_m"]?.array?.count, 3); XCTAssertEqual(photo["session_ref"]?.string, "S1")
        // geen prijs, kengetal of kostenveld in het hele contract
        let text = String(data: try inv.encoded(), encoding: .utf8)!
        for word in ["prijs", "price", "kengetal", "cost", "kosten", "tarief", "eur"] { XCTAssertFalse(text.lowercased().contains("\"\(word)"), word) }
    }

    func testContractRoundTripsAndRejectsTampering() throws {
        let inv = try contract()
        XCTAssertEqual(try GevelInventoryV1.decode(try inv.encoded()), inv)
        func tamper(_ edit: (inout [String: Any]) -> Void) -> [String] {
            var o = inv.jsonObject()!; edit(&o)
            return GevelInventoryV1.validate(JSONValue.from(any: o)!)
        }
        func facade0(_ o: inout [String: Any], _ edit: (inout [String: Any]) -> Void) { var f = o["facades"] as! [[String: Any]]; edit(&f[0]); o["facades"] = f }
        func object0(_ o: inout [String: Any], _ edit: (inout [String: Any]) -> Void) { facade0(&o) { f in var objs = f["objects"] as! [[String: Any]]; edit(&objs[0]); f["objects"] = objs } }
        XCTAssertFalse(tamper { $0["booking_allowed"] = true }.isEmpty)
        XCTAssertFalse(tamper { $0["contract"] = "mjop_gevel_inventory_v2" }.isEmpty)
        XCTAssertFalse(tamper { $0["extra"] = 1 }.isEmpty)
        XCTAssertFalse(tamper { var v = $0["validation"] as! [String: Any]; v["auto_processing_allowed"] = true; $0["validation"] = v }.isEmpty)
        XCTAssertFalse(tamper { o in object0(&o) { $0["outcome"] = "BETROUWBAAR_VASTGESTELD" } }.isEmpty)                 // niet zonder validatie
        XCTAssertFalse(tamper { o in object0(&o) { $0["nen2767_condition_score"] = 3 } }.isEmpty)
        XCTAssertFalse(tamper { o in object0(&o) { var g = $0["glass_area"] as! [String: Any]; g["origin"] = "LIDAR_PLANE_MEASUREMENT"; $0["glass_area"] = g } }.isEmpty)
        XCTAssertFalse(tamper { o in object0(&o) { var g = $0["glass_area"] as! [String: Any]; g["value"] = 99.0; $0["glass_area"] = g } }.isEmpty)
        XCTAssertFalse(tamper { o in object0(&o) { $0["identity"] = "UNCERTAIN" } }.isEmpty)                             // aantal ondanks mogelijke dubbeltelling
        XCTAssertFalse(tamper { o in object0(&o) { var a = $0["area"] as! [String: Any]; a["value"] = NSNull(); $0["area"] = a } }.isEmpty)
        XCTAssertFalse(tamper { o in facade0(&o) { var t = $0["totals"] as! [String: Any]; var q = t["frame_count"] as! [String: Any]; q["value"] = 2.5; t["frame_count"] = q; $0["totals"] = t } }.isEmpty)
        XCTAssertTrue(tamper { _ in }.isEmpty)
    }

    func testOutboxAndBridgeDeliverOnlyToTheRightProject() throws {
        let inv = try contract()
        var outbox = ProposalOutbox()
        outbox.upsert(.init(roundId: "R-00000001", planRef: "plan-abc12345", status: "COMPLETED", photos: 5, objects: 3, revision: 1, proposals: [], inventory: inv))
        XCTAssertEqual(outbox.inventories(forPlan: "plan-abc12345").count, 1)
        XCTAssertTrue(outbox.inventories(forPlan: "plan-OTHER000").isEmpty)                 // nooit naar een ander project
        // een niet-afgeronde ronde wordt niet aangeboden
        var open = outbox; open.rounds[0].status = "IN_PROGRESS"
        XCTAssertTrue(open.inventories(forPlan: "plan-abc12345").isEmpty)
        // overdracht bevestigen via de bestaande ackProposals; een nieuwe revisie is weer niet overgedragen
        outbox.ack(planRef: "plan-abc12345", proposalIds: [inv.inventoryId])
        XCTAssertEqual(outbox.rounds[0].inventoryDelivered, true)
        outbox.upsert(.init(roundId: "R-00000001", planRef: "plan-abc12345", status: "COMPLETED", photos: 5, objects: 3, revision: 2, proposals: [], inventory: try contract(revision: 2)))
        XCTAssertNil(outbox.rounds[0].inventoryDelivered)
        // opslag en terug (outbox.json)
        XCTAssertEqual(try JSONDecoder().decode(ProposalOutbox.self, from: try JSONEncoder().encode(outbox)), outbox)
        // brugbericht zoals de WebView het krijgt
        let reply = BridgeReply.facadeInventory(requestId: "w1", planRef: "plan-abc12345", inventories: outbox.inventories(forPlan: "plan-abc12345"))
        let script = try XCTUnwrap(BridgeReply.script(for: reply))
        XCTAssertTrue(script.hasPrefix("window.MJOPNativeBridge && window.MJOPNativeBridge.receive({"))
        let json = String(script.dropFirst("window.MJOPNativeBridge && window.MJOPNativeBridge.receive(".count).dropLast(2))
        let parsed = try XCTUnwrap(JSONValue.decode(Data(json.utf8)))
        XCTAssertEqual(parsed["type"]?.string, "facade-inventory"); XCTAssertEqual(parsed["v"]?.int, 1)
        XCTAssertEqual(GevelInventoryV1.validate(try XCTUnwrap(parsed["inventories"]?.array?.first)), [])
    }

    func testOutboxFilesFromBeforeGevelscanner2StillLoad() throws {
        let old = #"{"rounds":[{"roundId":"R-00000001","planRef":"plan-abc12345","status":"COMPLETED","photos":2,"objects":1,"revision":1,"proposals":[],"deliveredIds":[]}]}"#
        let o = try JSONDecoder().decode(ProposalOutbox.self, from: Data(old.utf8))
        XCTAssertNil(o.rounds[0].inventory); XCTAssertTrue(o.inventories(forPlan: "plan-abc12345").isEmpty)
    }

    func testBridgeRequestForInventoryIsParsedStrictly() {
        XCTAssertEqual(BridgeMessage.parse(["v": 1, "action": "listFacadeInventory", "requestId": "w1", "payload": ["planRef": "plan-abc12345"]] as [String: Any]),
                       .success(.listFacadeInventory(requestId: "w1", planRef: "plan-abc12345")))
        XCTAssertEqual(BridgeMessage.parse(["v": 1, "action": "listFacadeInventory", "requestId": "w1", "payload": ["planRef": "x"]] as [String: Any]), .failure(.invalidPayload))
        let caps = BridgeReply.capabilities(requestId: "w1", lidar: true, appVersion: "2.1")
        XCTAssertEqual(caps["features"] as? [String], ["gevelscan2"]); XCTAssertEqual(caps["lidar"] as? Bool, true)       // bestaande velden ongewijzigd
    }

    /// Het gedeelde voorbeeld (Fixtures/gevel_inventory_v1_example.json) wordt ook door de Python-schematest en de websitetests gebruikt.
    /// Deze test bewaakt dat de app precies dat voorbeeld produceert. Opnieuw maken: GEVELSCAN_WRITE_FIXTURE=1 swift test --filter testSharedFixture.
    func testSharedFixtureIsWhatTheAppProduces() throws {
        let inv = try contract()
        let data = try inv.encoded()
        if let dir = ProcessInfo.processInfo.environment["GEVELSCAN_WRITE_FIXTURE"] { try data.write(to: URL(fileURLWithPath: dir).appendingPathComponent("gevel_inventory_v1_example.json")); return }
        let url = try XCTUnwrap(Bundle.module.url(forResource: "gevel_inventory_v1_example", withExtension: "json", subdirectory: "Fixtures"))
        let stored = try GevelInventoryV1.decode(try Data(contentsOf: url))
        XCTAssertEqual(stored.body["facades"]?.array?.count, inv.body["facades"]?.array?.count)
        XCTAssertEqual(stored.body["building_totals"]?["frame_count"], inv.body["building_totals"]?["frame_count"])
        XCTAssertEqual(stored.body["versions"], inv.body["versions"])
        XCTAssertEqual(stored.body["recognition"], inv.body["recognition"])
    }
}
