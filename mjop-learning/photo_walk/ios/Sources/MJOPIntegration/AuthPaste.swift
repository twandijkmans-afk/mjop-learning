import Foundation

/// Handmatige terugkeer na het aanvragen van een inloglink: de gebruiker plakt de link uit de e-mail of de via de brugpagina gekopieerde code.
/// Alleen een eenmalige code of een Supabase-/brugpagina-adres van het eigen project wordt geaccepteerd; tokens nooit.
public enum AuthPaste: Equatable {
    case code(String)
    case openInWebView(URL)
    case rejected(String)

    public static func parse(_ text: String, policy: WebNavigationPolicy = .production) -> AuthPaste {
        let s = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.isEmpty || s.count > 2048 { return .rejected("leeg of te lang") }
        if AuthCallback.isPlausibleCode(s) { return .code(s) }
        guard let url = URL(string: s), let scheme = url.scheme?.lowercased() else { return .rejected("geen link of code") }
        if scheme == MJOPConfig.appURLScheme {
            switch AuthCallback.parse(url) {
            case .code(let c): return .code(c)
            case .failure(let m): return .rejected(m)
            case .rejected(let m): return .rejected(m)
            }
        }
        guard scheme == "https", policy.isAllowedInApp(url) else { return .rejected("alleen links van MJOP Live zijn toegestaan") }
        let comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let names = Set((comps?.queryItems ?? []).map { $0.name })
        var fragNames = Set<String>()
        if let f = url.fragment { var fc = URLComponents(); fc.query = f; fragNames = Set((fc.queryItems ?? []).map { $0.name }) }
        if !names.union(fragNames).isDisjoint(with: ["access_token", "refresh_token", "provider_token"]) { return .rejected("tokens in een link worden niet geaccepteerd") }
        // bruglink van de eigen site met ?code=...: alleen de code gebruiken
        if let c = comps?.queryItems?.first(where: { $0.name == "code" })?.value, url.host?.lowercased() == policy.siteHost {
            return AuthCallback.isPlausibleCode(c) ? .code(c) : .rejected("geen geldige code")
        }
        // de verificatielink van Supabase: de WebView volgt hem en komt op de brugpagina uit (die in de app direct naar ./?code=... gaat)
        if url.host?.lowercased() == policy.supabaseHost, url.path.hasPrefix("/auth/v1/verify") { return .openInWebView(url) }
        return .rejected("onbekende link")
    }
}
