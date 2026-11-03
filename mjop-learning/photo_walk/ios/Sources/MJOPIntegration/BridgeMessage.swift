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
    // Native navigatie (app-versie 2), alleen optellend. Een oudere website stuurt deze nooit; een oudere app kent ze niet en de website stuurt ze dan ook niet.
    case webReady(requestId: String, features: [String], webVersion: String?)
    case webReply(requestId: String, result: WebCommandResult)
    case webState(requestId: String, state: JSONValue)
}

public enum BridgeParseError: Error, Equatable {
    case notAnObject, tooLarge, wrongVersion, unknownAction(String), badRequestId, invalidContext(String), invalidPayload
}

public enum BridgeMessage {
    public static let version = 1
    public static let maxBytes = 20_000
    /// Een antwoord op een commando (bijvoorbeeld de projectlijst) mag groter zijn dan een gewoon bericht.
    public static let maxReplyBytes = 150_000

    static func ok(_ s: String, _ pattern: String) -> Bool { s.range(of: pattern, options: .regularExpression) != nil }

    public static func parse(_ body: Any) -> Result<BridgeRequest, BridgeParseError> {
        guard let d = body as? [String: Any] else { return .failure(.notAnObject) }
        // oude printshim: {action: "print"} (zonder versie)
        if d["v"] == nil, d["action"] as? String == "print" { return .success(.print) }
        let limit = (d["action"] as? String) == "webReply" ? maxReplyBytes : maxBytes
        if let data = try? JSONSerialization.data(withJSONObject: d), data.count > limit { return .failure(.tooLarge) }
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
        case "webReady":
            guard let feats = payload?["features"] as? [String], feats.count <= 20, feats.allSatisfy({ ok($0, "^[a-z0-9_-]{1,32}$") }) else { return .failure(.invalidPayload) }
            var ver: String? = nil
            if let s = payload?["webVersion"] as? String, ok(s, "^[A-Za-z0-9._-]{1,40}$") { ver = s }
            return .success(.webReady(requestId: rid, features: feats, webVersion: ver))
        case "webReply":
            guard let p = payload, let cmd = p["command"] as? String, ok(cmd, "^[A-Za-z]{1,40}$"), let okFlag = p["ok"] as? Bool else { return .failure(.invalidPayload) }
            var data: JSONValue? = nil
            if let raw = p["data"], !(raw is NSNull) {
                guard let j = JSONValue.from(any: raw) ?? (raw as? [Any]).flatMap({ JSONValue.from(any: $0) }) else { return .failure(.invalidPayload) }
                data = j
            }
            var code: String? = nil, message: String? = nil
            if let e = p["error"] as? [String: Any] {
                if let c = e["code"] as? String, ok(c, "^[A-Z_]{1,40}$") { code = c }
                if let m = e["message"] as? String { message = String(m.prefix(200)) }
            }
            if !okFlag && code == nil { code = "FAILED" }
            return .success(.webReply(requestId: rid, result: WebCommandResult(command: cmd, ok: okFlag, data: data, errorCode: code, errorMessage: message)))
        case "webState":
            guard let p = payload, let state = JSONValue.from(any: p) else { return .failure(.invalidPayload) }
            return .success(.webState(requestId: rid, state: state))
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
    /// Antwoord op `webReady`: de app toont zelf de tabbalk, dus de website mag zijn eigen verbergen.
    public static func nativeReady(lidar: Bool, appVersion: String) -> [String: Any] {
        ["type": "nativeReady", "features": [NativeNav.tabsFeature], "appVersion": appVersion, "lidar": lidar]
    }
    public static func error(requestId: String?, message: String) -> [String: Any] {
        var m: [String: Any] = ["type": "error", "message": message]
        if let r = requestId { m["requestId"] = r }
        return m
    }
}
