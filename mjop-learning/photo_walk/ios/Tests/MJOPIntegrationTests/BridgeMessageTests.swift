import XCTest
@testable import MJOPIntegration

final class BridgeMessageTests: XCTestCase {
    func ctx(mode: String = "round", element: Any = NSNull(), extra: [String: Any] = [:]) -> [String: Any] {
        var d: [String: Any] = ["planRef": "plan-0123456789abcdef01234567", "mjopPlanId": NSNull(), "buildingLabel": "Kastanjelaan 12", "bagPandId": "0363100012345678",
                                "mode": mode, "element": element, "plannedFacades": [["name": "Voorgevel", "orientation": "S"]]]
        for (k, v) in extra { d[k] = v }
        return d
    }
    func msg(_ action: String, _ payload: [String: Any], v: Any = 1, rid: Any = "w1-abc") -> [String: Any] { ["v": v, "action": action, "requestId": rid, "payload": payload] }

    func testValidRoundStart() {
        guard case .success(.startPhotoRound(let rid, let c)) = BridgeMessage.parse(msg("startPhotoRound", ctx())) else { return XCTFail() }
        XCTAssertEqual(rid, "w1-abc"); XCTAssertEqual(c.buildingLabel, "Kastanjelaan 12"); XCTAssertEqual(c.mode, .round)
        XCTAssertEqual(c.plannedFacades, [.init(name: "Voorgevel", orientation: "S")]); XCTAssertEqual(c.bagPandId, "0363100012345678")
    }

    func testValidElementStartCarriesElementContext() {
        let el: [String: Any] = ["key": "kozijnen-onderhoud", "name": "Onderhoud buitenkozijnen", "unit": "st"]
        guard case .success(.startElementScan(_, let c)) = BridgeMessage.parse(msg("startElementScan", ctx(mode: "element", element: el))) else { return XCTFail() }
        XCTAssertEqual(c.element, .init(key: "kozijnen-onderhoud", name: "Onderhoud buitenkozijnen", unit: "st"))
    }

    func testModeMustMatchAction() {
        let el: [String: Any] = ["key": "kozijnen-onderhoud", "name": "x", "unit": "st"]
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(mode: "element", element: el))), .failure(.invalidContext("mode")))
        XCTAssertEqual(BridgeMessage.parse(msg("startElementScan", ctx())), .failure(.invalidContext("mode")))
        XCTAssertEqual(BridgeMessage.parse(msg("startElementScan", ctx(mode: "element"))), .failure(.invalidContext("element")))
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(element: el))), .failure(.invalidContext("element")))
    }

    func testWrongProjectContextIsRejected() {
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(extra: ["planRef": "x"]))), .failure(.invalidContext("planRef")))
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(extra: ["planRef": 5]))), .failure(.invalidContext("planRef")))
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(extra: ["buildingLabel": "  "]))), .failure(.invalidContext("buildingLabel")))
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(extra: ["bagPandId": "123"]))), .failure(.invalidContext("bagPandId")))
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ctx(extra: ["plannedFacades": [["name": "A", "orientation": "UP"]]]))), .failure(.invalidContext("plannedFacades")))
        XCTAssertEqual(BridgeMessage.parse(msg("startPhotoRound", ["foo": 1])), .failure(.invalidContext("planRef")))
    }

    func testVersionAndShape() {
        XCTAssertEqual(BridgeMessage.parse("x"), .failure(.notAnObject))
        XCTAssertEqual(BridgeMessage.parse(msg("getCapabilities", [:], v: 2)), .failure(.wrongVersion))
        XCTAssertEqual(BridgeMessage.parse(msg("getCapabilities", [:], rid: "bad id!")), .failure(.badRequestId))
        XCTAssertEqual(BridgeMessage.parse(msg("deleteEverything", [:])), .failure(.unknownAction("deleteEverything")))
        XCTAssertEqual(BridgeMessage.parse(msg("getCapabilities", [:])), .success(.getCapabilities(requestId: "w1-abc")))
    }

    func testOversizeIsRejected() {
        let big = msg("startPhotoRound", ctx(extra: ["junk": String(repeating: "a", count: 30_000)]))
        XCTAssertEqual(BridgeMessage.parse(big), .failure(.tooLarge))
    }

    func testListAndAck() {
        XCTAssertEqual(BridgeMessage.parse(msg("listProposals", ["planRef": "plan-0123456789ab"])), .success(.listProposals(requestId: "w1-abc", planRef: "plan-0123456789ab")))
        XCTAssertEqual(BridgeMessage.parse(msg("listProposals", [:])), .failure(.invalidPayload))
        XCTAssertEqual(BridgeMessage.parse(msg("ackProposals", ["planRef": "plan-0123456789ab", "proposalIds": ["r1a2b3c4-count-bld-r1"]])),
                       .success(.ackProposals(requestId: "w1-abc", planRef: "plan-0123456789ab", proposalIds: ["r1a2b3c4-count-bld-r1"])))
        XCTAssertEqual(BridgeMessage.parse(msg("ackProposals", ["planRef": "plan-0123456789ab", "proposalIds": ["<script>"]])), .failure(.invalidPayload))
    }

    func testLegacyPrintShimStillWorks() {
        XCTAssertEqual(BridgeMessage.parse(["action": "print"]), .success(.print))
        XCTAssertEqual(BridgeMessage.parse(["action": "format"]), .failure(.wrongVersion))
    }

    func testReplyScriptIsValidAndEscaped() throws {
        let s = try XCTUnwrap(BridgeReply.script(for: BridgeReply.capabilities(requestId: "w1", lidar: true, appVersion: "1.0")))
        XCTAssertTrue(s.hasPrefix("window.MJOPNativeBridge && window.MJOPNativeBridge.receive({"))
        XCTAssertTrue(s.contains("\"v\":1")); XCTAssertTrue(s.contains("\"lidar\":true"))
        let e = try XCTUnwrap(BridgeReply.script(for: BridgeReply.error(requestId: nil, message: "a\u{2028}b</script>")))
        XCTAssertFalse(e.contains("\u{2028}"))
    }
}
