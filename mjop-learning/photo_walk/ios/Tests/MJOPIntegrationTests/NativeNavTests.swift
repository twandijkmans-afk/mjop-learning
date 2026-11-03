import XCTest
@testable import MJOPIntegration

/// Contracttests voor de native navigatie (app-versie 2). Het bestand `contract_v1.json` is hetzelfde als in de website (`test/fixtures/native-bridge`),
/// zodat de Swift-kant en de JavaScript-kant aantoonbaar dezelfde berichten gebruiken.
final class NativeNavTests: XCTestCase {
    func contract() throws -> [String: Any] {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "contract_v1", withExtension: "json", subdirectory: "Fixtures"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: try Data(contentsOf: url)) as? [String: Any])
    }
    func envelope(_ action: String, _ payload: [String: Any], rid: String = "n1-abc") -> [String: Any] {
        ["v": 1, "action": action, "requestId": rid, "payload": payload]
    }
    let p1 = "11111111-2222-3333-4444-555555555555"

    // MARK: commando's komen overeen met het gedeelde contract

    func testEveryCommandMatchesTheSharedContractExactly() throws {
        let c = try contract()
        let valid = try XCTUnwrap(c["commands_valid"] as? [[String: Any]])
        let built: [(String, NativeCommand)] = [
            ("c-1", .navigate(tab: "planning", sub: nil)),
            ("c-2", .navigate(tab: "account", sub: "abonnement")),
            ("c-3", .getProjects),
            ("c-4", .openProject(id: p1, tab: "home", force: false)),
            ("c-5", .openProject(id: p1, tab: nil, force: true)),
            ("c-6", .startMeasurement(mode: .round, planId: p1, elementKey: nil, force: false)),
            ("c-7", .startMeasurement(mode: .element, planId: nil, elementKey: "kozijnen-onderhoud", force: false)),
            ("c-8", .getStatus), ("c-9", .getProposals), ("c-10", .signOut), ("c-11", .newProject),
        ]
        XCTAssertEqual(valid.count, built.count)
        for (i, (rid, cmd)) in built.enumerated() {
            XCTAssertTrue(cmd.isValid, "\(cmd) hoort geldig te zijn")
            var m = cmd.message(requestId: rid)
            m["v"] = BridgeMessage.version
            XCTAssertEqual(NSDictionary(dictionary: m), NSDictionary(dictionary: valid[i]), "commando \(rid) wijkt af van het contract")
        }
    }

    func testCommandsOutsideTheClosedSchemaAreNeverSent() {
        XCTAssertFalse(NativeCommand.navigate(tab: "javascript:alert(1)", sub: nil).isValid)
        XCTAssertFalse(NativeCommand.navigate(tab: "planning", sub: "profiel").isValid, "sub alleen bij account/instellingen")
        XCTAssertFalse(NativeCommand.navigate(tab: "account", sub: "geheim").isValid)
        XCTAssertFalse(NativeCommand.openProject(id: "../etc", tab: nil, force: false).isValid)
        XCTAssertFalse(NativeCommand.openProject(id: p1, tab: "onbekend", force: false).isValid)
        XCTAssertFalse(NativeCommand.startMeasurement(mode: .element, planId: nil, elementKey: nil, force: false).isValid)
        XCTAssertFalse(NativeCommand.startMeasurement(mode: .element, planId: nil, elementKey: "Slechte Sleutel", force: false).isValid)
        XCTAssertFalse(NativeCommand.startMeasurement(mode: .round, planId: "x", elementKey: nil, force: false).isValid)
    }

    func testForceIsOnlySentWhenTheUserConfirmed() {
        XCTAssertNil(NativeCommand.openProject(id: p1, tab: nil, force: false).message(requestId: "a")["force"])
        XCTAssertEqual(NativeCommand.openProject(id: p1, tab: nil, force: true).message(requestId: "a")["force"] as? Bool, true)
    }

    func testTabMappingsOnlyUseTabsTheWebsiteAccepts() {
        for s in MJOPSection.allCases { XCTAssertTrue(NativeNav.allowedTabs.contains(s.webTab), s.title); XCTAssertEqual(MJOPSection.from(webTab: s.webTab)?.webTab, s.webTab) }
        for p in ProfileSection.allCases { XCTAssertTrue(NativeCommand.navigate(tab: p.target.tab, sub: p.target.sub).isValid, p.title) }
    }

    // MARK: berichten van de website

    func testWebReadyFromTheContractParses() throws {
        let c = try contract()
        let msg = try XCTUnwrap(c["web_ready"] as? [String: Any])
        XCTAssertEqual(BridgeMessage.parse(msg), .success(.webReady(requestId: "n1-abc", features: ["nav1"], webVersion: "native-nav-1")))
    }

    func testWebReadyWithBadFeaturesIsRejected() {
        XCTAssertEqual(BridgeMessage.parse(envelope("webReady", ["features": ["NAV 1"]])), .failure(.invalidPayload))
        XCTAssertEqual(BridgeMessage.parse(envelope("webReady", ["features": "nav1"])), .failure(.invalidPayload))
        XCTAssertEqual(BridgeMessage.parse(envelope("webReady", ["features": Array(repeating: "a", count: 21)])), .failure(.invalidPayload))
    }

    func testProjectListReplyParsesAndKeepsUnknownAsNil() throws {
        let c = try contract()
        let example = try XCTUnwrap(c["projects_reply_example"] as? [String: Any])
        let msg = envelope("webReply", ["command": "getProjects", "ok": true, "data": example], rid: "q1")
        guard case .success(.webReply(let rid, let result)) = BridgeMessage.parse(msg) else { return XCTFail("webReply niet herkend") }
        XCTAssertEqual(rid, "q1"); XCTAssertTrue(result.ok); XCTAssertEqual(result.command, "getProjects")
        let list = try XCTUnwrap(ProjectList.parse(result.data))
        XCTAssertTrue(list.loggedIn)
        XCTAssertEqual(list.projects.map { $0.id }, [p1, "66666666-7777-8888-9999-000000000000"])
        XCTAssertEqual(list.projects[0].label, "Teststraat 1, Amsterdam"); XCTAssertTrue(list.projects[0].isCurrent)
        XCTAssertNotNil(list.projects[0].updatedDate)
        XCTAssertNil(list.projects[1].adres, "ontbrekend adres blijft nil"); XCTAssertNil(list.projects[1].updatedAt, "ontbrekende datum blijft nil"); XCTAssertNil(list.projects[1].updatedDate)
    }

    func testProjectListSkipsInvalidEntriesAndRejectsAMissingLoginFlag() {
        let entries: [[String: Any]] = [
            ["id": "../x", "label": "Slecht"],
            ["id": "11111111-2222-3333-4444-555555555555", "label": "Goed", "onbekendVeld": 1],
            ["id": "66666666-7777-8888-9999-000000000000", "label": ""],
        ]
        let payload: [String: Any] = ["loggedIn": true, "projects": entries]
        let data = JSONValue.from(any: payload)
        XCTAssertEqual(ProjectList.parse(data)?.projects.map { $0.label }, ["Goed"])
        let noLogin: [String: Any] = ["projects": [String]()]
        XCTAssertNil(ProjectList.parse(JSONValue.from(any: noLogin)), "zonder loggedIn is de lijst ongeldig")
        XCTAssertNil(ProjectList.parse(nil))
    }

    func testWebStateFromTheContractParses() throws {
        let c = try contract()
        let st = try XCTUnwrap(c["web_state_example"] as? [String: Any])
        guard case .success(.webState(_, let state)) = BridgeMessage.parse(envelope("webState", st)) else { return XCTFail("webState niet herkend") }
        let s = try XCTUnwrap(WebStatus.parse(state))
        XCTAssertTrue(s.loggedIn); XCTAssertEqual(s.planId, p1); XCTAssertTrue(s.hasBuilding); XCTAssertFalse(s.isExample)
        XCTAssertEqual(s.label, "Teststraat 1, Amsterdam"); XCTAssertEqual(s.saveStatus, .saved); XCTAssertEqual(s.pendingProposals, 2)
        XCTAssertEqual(s.planRef, "plan-0123456789abcdef01234567"); XCTAssertEqual(s.nextStep, "Bekijk je voorstel")
    }

    func testWebStateWithoutProjectKeepsUnknownAsNil() throws {
        let raw: [String: Any] = ["loggedIn": true, "planId": NSNull(), "label": NSNull(), "nextStep": NSNull(), "saveStatus": "IETS_NIEUWS"]
        let s = try XCTUnwrap(WebStatus.parse(JSONValue.from(any: raw)))
        XCTAssertNil(s.planId); XCTAssertNil(s.label); XCTAssertNil(s.nextStep); XCTAssertEqual(s.saveStatus, .unknown); XCTAssertEqual(s.pendingProposals, 0)
        XCTAssertNil(WebStatus.parse(.string("geen object")))
    }

    func testErrorRepliesCarryTheCode() {
        guard case .success(.webReply(_, let r)) = BridgeMessage.parse(envelope("webReply", ["command": "openProject", "ok": false, "error": ["code": "UNSAVED_CHANGES", "message": "Wijzigingen"]])) else { return XCTFail() }
        XCTAssertFalse(r.ok); XCTAssertEqual(r.errorCode, "UNSAVED_CHANGES"); XCTAssertEqual(r.errorMessage, "Wijzigingen"); XCTAssertNil(r.data)
        guard case .success(.webReply(_, let r2)) = BridgeMessage.parse(envelope("webReply", ["command": "x", "ok": false])) else { return XCTFail() }
        XCTAssertEqual(r2.errorCode, "FAILED", "een mislukking heeft altijd een code")
    }

    func testProposalListNeverTurnsUnknownIntoZero() throws {
        let pending: [[String: Any]] = [["id": "prop-1-aaaaaaaa", "kind": "FRAME_AREA_GROSS", "unit": "m2", "scope": "Hele gebouw", "value": NSNull(), "partialValue": 17.4, "level": "INCOMPLETE"]]
        let raw: [String: Any] = ["planRef": "plan-0123456789abcdef01234567", "total": 1, "pending": pending]
        let l = try XCTUnwrap(ProposalList.parse(JSONValue.from(any: raw)))
        XCTAssertEqual(l.pending.count, 1); XCTAssertNil(l.pending[0].value, "onbekend is nil, nooit 0"); XCTAssertEqual(l.pending[0].partialValue, 17.4)
    }

    // MARK: groottelimieten en bestaand gedrag

    func testSizeLimitsDifferForRepliesAndOtherMessages() {
        let big25 = String(repeating: "a", count: 25_000), big100 = String(repeating: "a", count: 100_000), big200 = String(repeating: "a", count: 200_000)
        XCTAssertEqual(BridgeMessage.parse(envelope("webState", ["label": big25])), .failure(.tooLarge))
        guard case .success(.webReply) = BridgeMessage.parse(envelope("webReply", ["command": "getProjects", "ok": true, "data": ["blob": big100]])) else { return XCTFail("100 kB antwoord hoort mogelijk te zijn") }
        XCTAssertEqual(BridgeMessage.parse(envelope("webReply", ["command": "getProjects", "ok": true, "data": ["blob": big200]])), .failure(.tooLarge))
        XCTAssertEqual(BridgeMessage.parse(envelope("getCapabilities", ["x": big25])), .failure(.tooLarge), "bestaande limiet voor gewone berichten blijft 20 kB")
    }

    func testExistingActionsAndRejectionsAreUnchanged() {
        XCTAssertEqual(BridgeMessage.parse(envelope("getCapabilities", [:], rid: "w1-abc")), .success(.getCapabilities(requestId: "w1-abc")))
        XCTAssertEqual(BridgeMessage.parse(envelope("listProposals", ["planRef": "plan-0123456789abcdef01234567"])), .success(.listProposals(requestId: "n1-abc", planRef: "plan-0123456789abcdef01234567")))
        let printShim: [String: Any] = ["action": "print"]
        XCTAssertEqual(BridgeMessage.parse(printShim), .success(.print), "oude printshim zonder versie")
        XCTAssertEqual(BridgeMessage.parse(envelope("deleteEverything", [:])), .failure(.unknownAction("deleteEverything")))
        let wrongVersion: [String: Any] = ["v": 2, "action": "webReady", "requestId": "a1", "payload": ["features": ["nav1"]]]
        XCTAssertEqual(BridgeMessage.parse(wrongVersion), .failure(.wrongVersion))
        XCTAssertEqual(BridgeMessage.parse(envelope("webReady", ["features": ["nav1"]], rid: "a b")), .failure(.badRequestId))
    }

    // MARK: antwoorden naar de website

    func testNativeReadyAndCommandScriptsAreSafeDataCalls() throws {
        let ready = BridgeReply.nativeReady(lidar: true, appVersion: "2")
        XCTAssertEqual(ready["features"] as? [String], ["tabs1"])
        let s1 = try XCTUnwrap(BridgeReply.script(for: ready))
        XCTAssertTrue(s1.hasPrefix("window.MJOPNativeBridge && window.MJOPNativeBridge.receive({"))
        XCTAssertTrue(s1.contains("\"type\":\"nativeReady\"") && s1.contains("\"v\":1"))
        let s2 = try XCTUnwrap(BridgeReply.script(for: NativeCommand.navigate(tab: "planning", sub: nil).message(requestId: "a1-b")))
        XCTAssertTrue(s2.contains("\"command\":\"navigate\"") && s2.contains("\"tab\":\"planning\""))
        // een kwaadaardige waarde wordt data, nooit code
        let s3 = try XCTUnwrap(BridgeReply.script(for: ["type": "command", "x": "\"});alert(1);//\u{2028}"]))
        XCTAssertFalse(s3.contains("\u{2028}"))
    }

    func testUserAgentSuffixIsVersion2AndStillMatchesTheWebsitePattern() {
        XCTAssertEqual(MJOPConfig.userAgentSuffix, "MJOPLiveApp/2")
        XCTAssertTrue(MJOPConfig.userAgentSuffix.range(of: "^MJOPLiveApp/[0-9]+$", options: .regularExpression) != nil, "de bestaande website herkent elke versie")
    }

    func testDatesWithMicrosecondsParse() {
        XCTAssertNotNil(NativeDates.parse("2026-10-30T09:15:00.123456+00:00"))
        XCTAssertNotNil(NativeDates.parse("2026-10-30T09:15:00Z"))
        XCTAssertNil(NativeDates.parse("gisteren"))
    }

    func testJSONValueKeepsBooleansAndNumbersApart() throws {
        let raw: [String: Any] = ["a": true, "b": 1, "c": 1.5, "d": NSNull(), "e": "x", "f": [1, 2]]
        let v = try XCTUnwrap(JSONValue.from(any: raw))
        XCTAssertEqual(v["a"]?.bool, true); XCTAssertNil(v["a"]?.double)
        XCTAssertEqual(v["b"]?.int, 1); XCTAssertNil(v["b"]?.bool)
        XCTAssertNil(v["c"]?.int, "1,5 wordt nooit stil afgerond"); XCTAssertEqual(v["c"]?.double, 1.5)
        XCTAssertTrue(v["d"]?.isNull == true); XCTAssertEqual(v["e"]?.string, "x"); XCTAssertEqual(v["f"]?.array?.count, 2)
    }
}
