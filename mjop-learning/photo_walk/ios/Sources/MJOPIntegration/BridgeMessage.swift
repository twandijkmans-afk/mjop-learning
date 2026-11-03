import Foundation

/// Berichten van de website (WebView) naar de app. Elk bericht wordt gecontroleerd op versie, actie, requestId, grootte en inhoud; de afzender
/// (hoofdframe op het eigen domein) wordt door de WebView-controller gecontroleerd voordat dit wordt aangeroepen.
public enum BridgeRequest: Equatable {
    case startPhotoRound(requestId: String, context: PhotoRoundContext)
    case startElementScan(requestId: String, context: PhotoRoundContext)
    case listProposals(requestId: String, planRef: String)
    case ackProposals(requestId: String, planRef: String, proposalIds: [String])
    case getCapabilities(requestId: String)
    case print
}

public enum BridgeParseError: Error, Equatable {
    case notAnObject, tooLarge, wrongVersion, unknownAction(String), badRequestId, invalidContext(String), invalidPayload
}

public enum BridgeMessage {
    public static let version = 1
    public static let maxBytes = 20_000

    static func ok(_ s: String, _ pattern: String) -> Bool { s.range(of: pattern, options: .regularExpression) != nil }

    public static func parse(_ body: Any) -> Result<BridgeRequest, BridgeParseError> {
        guard let d = body as? [String: Any] else { return .failure(.notAnObject) }
        // oude printshim: {action: "print"} (zonder versie)
        if d["v"] == nil, d["action"] as? String == "print" { return .success(.print) }
        if let data = try? JSONSerialization.data(withJSONObject: d), data.count > maxBytes { return .failure(.tooLarge) }
        guard let v = d["v"] as? Int, v == version else { return .failure(.wrongVersion) }
        guard let action = d["action"] as? String else { return .failure(.unknownAction("")) }
        guard let rid = d["requestId"] as? String, ok(rid, "^[A-Za-z0-9_-]{1,64}$") else { return .failure(.badRequestId) }
        let payload = d["payload"] as? [String: Any]
        switch action {
        case "startPhotoRound", "startElementScan":
            switch PhotoRoundContext.validate(payload) {
            case .failure(let e): if case .field(let f) = e { return .failure(.invalidContext(f)) } else { return .failure(.invalidPayload) }
            case .success(let ctx):
                if action == "startPhotoRound" { return ctx.mode == .round ? .success(.startPhotoRound(requestId: rid, context: ctx)) : .failure(.invalidContext("mode")) }
                return ctx.mode == .element ? .success(.startElementScan(requestId: rid, context: ctx)) : .failure(.invalidContext("mode"))
            }
        case "listProposals":
            guard let ref = payload?["planRef"] as? String, ok(ref, "^[A-Za-z0-9_-]{8,80}$") else { return .failure(.invalidPayload) }
            return .success(.listProposals(requestId: rid, planRef: ref))
        case "ackProposals":
            guard let ref = payload?["planRef"] as? String, ok(ref, "^[A-Za-z0-9_-]{8,80}$"),
                  let ids = payload?["proposalIds"] as? [String], ids.count <= 200, ids.allSatisfy({ ok($0, "^[A-Za-z0-9_.-]{8,80}$") }) else { return .failure(.invalidPayload) }
            return .success(.ackProposals(requestId: rid, planRef: ref, proposalIds: ids))
        case "getCapabilities":
            return .success(.getCapabilities(requestId: rid))
        default:
            return .failure(.unknownAction(String(action.prefix(40))))
        }
    }
}

/// Antwoorden van de app naar de website. Worden als JavaScript-aanroep `window.MJOPNativeBridge.receive(<json>)` geleverd.
public enum BridgeReply {
    public static func script(for message: [String: Any]) -> String? {
        var m = message; m["v"] = BridgeMessage.version
        guard JSONSerialization.isValidJSONObject(m), let data = try? JSONSerialization.data(withJSONObject: m, options: [.sortedKeys]),
              var json = String(data: data, encoding: .utf8) else { return nil }
        json = json.replacingOccurrences(of: "\u{2028}", with: "\\u2028").replacingOccurrences(of: "\u{2029}", with: "\\u2029")
        return "window.MJOPNativeBridge && window.MJOPNativeBridge.receive(\(json));"
    }
    public static func capabilities(requestId: String, lidar: Bool, appVersion: String) -> [String: Any] {
        ["type": "capabilities", "requestId": requestId, "lidar": lidar, "appVersion": appVersion]
    }
    public static func error(requestId: String?, message: String) -> [String: Any] {
        var m: [String: Any] = ["type": "error", "message": message]
        if let r = requestId { m["requestId"] = r }
        return m
    }
}
