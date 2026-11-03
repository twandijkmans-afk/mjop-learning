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
        if let e = (items.first(where: { $0.name == "error_description" })?.value ?? items.first(where: { $0.name == "error" })?.value), !e.isEmpty {
            return .failure(String(e.prefix(200)))
        }
        guard let code = items.first(where: { $0.name == "code" })?.value, isPlausibleCode(code) else { return .rejected("geen geldige code") }
        return .code(code)
    }

    static func isPlausibleCode(_ s: String) -> Bool {
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
