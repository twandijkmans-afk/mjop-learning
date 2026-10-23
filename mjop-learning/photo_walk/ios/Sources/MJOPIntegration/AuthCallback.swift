import Foundation

/// Terugkeer uit de browser na een Supabase-magic-link: `mjoplive://auth-callback?code=<eenmalige PKCE-code>`.
/// Alleen de eenmalige code (nutteloos zonder de code-verifier in de WebView-opslag) wordt doorgegeven; sessietokens worden geweigerd.
public enum AuthCallback: Equatable {
    case code(String)
    case failure(String)
    case rejected(String)

    private static let allowedKeys: Set<String> = ["code", "error", "error_code", "error_description"]
    private static let forbiddenKeys: Set<String> = ["access_token", "refresh_token", "provider_token", "token", "token_hash", "id_token"]

    public static func parse(_ url: URL) -> AuthCallback {
        guard url.scheme?.lowercased() == MJOPConfig.appURLScheme, url.host?.lowercased() == MJOPConfig.authCallbackHost,
              url.path.isEmpty || url.path == "/" else { return .rejected("onbekend adres") }
        // Tokens horen nooit in een URL van dit schema (ook niet in het fragment).
        let items = (URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? [])
        var fragmentKeys = Set<String>()
        if let f = url.fragment { var fc = URLComponents(); fc.query = f; fragmentKeys = Set((fc.queryItems ?? []).map { $0.name }) }
        if !forbiddenKeys.isDisjoint(with: Set(items.map { $0.name }).union(fragmentKeys)) { return .rejected("tokens in de URL worden niet geaccepteerd") }
        if items.contains(where: { !allowedKeys.contains($0.name) }) { return .rejected("onbekende parameters") }
        let errorCode = items.first(where: { $0.name == "error_code" })?.value
        if let e = (items.first(where: { $0.name == "error_description" })?.value ?? items.first(where: { $0.name == "error" })?.value), !e.isEmpty {
            return .failure(friendlyMessage(code: errorCode, fallback: String(e.prefix(200))))
        }
        guard let code = items.first(where: { $0.name == "code" })?.value, isPlausibleCode(code) else { return .rejected("geen geldige code") }
        return .code(code)
    }

    /// Nederlandse uitleg bij bekende fouten van de inlogservice. `otp_expired` komt ook voor als een e-mailprogramma of virusscanner de link al heeft geopend.
    public static func friendlyMessage(code: String?, fallback: String) -> String {
        switch code {
        case "otp_expired":
            return "De inloglink is verlopen of al gebruikt. Sommige e-mailprogramma's openen links vooraf. Vraag een nieuwe link aan en open die direct in Safari op deze iPhone."
        case "access_denied":
            return "Inloggen is geweigerd. Vraag een nieuwe inloglink aan."
        default:
            return fallback
        }
    }

    public static func isPlausibleCode(_ s: String) -> Bool {
        guard (8...256).contains(s.count) else { return false }
        return s.unicodeScalars.allSatisfy { ($0.value < 128) && (CharacterSet.alphanumerics.contains($0) || "-_.~".unicodeScalars.contains($0)) }
    }

    /// Adres waarmee de website in de WebView de code zelf inwisselt (supabase-js `detectSessionInUrl`, PKCE).
    public static func webURL(for code: String, base: URL = MJOPConfig.siteURL) -> URL? {
        guard isPlausibleCode(code), var c = URLComponents(url: base, resolvingAgainstBaseURL: false) else { return nil }
        c.queryItems = [URLQueryItem(name: "code", value: code)]
        return c.url
    }
}
