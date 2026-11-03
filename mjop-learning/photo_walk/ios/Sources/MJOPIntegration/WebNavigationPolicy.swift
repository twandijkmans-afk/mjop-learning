import Foundation

/// Wat er met een navigatie in de MJOP-webweergave moet gebeuren.
public enum WebNavigationDecision: Equatable {
    case allowInApp
    case openExternally(URL)
    case block(reason: String)
}

/// Domeinbeperking van de webweergave. Alleen de MJOP-site (met padvoorvoegsel) en de Supabase-auth-paden worden in de app geladen;
/// andere https-links gaan naar Safari, alles wat onveilig of onbekend is wordt geblokkeerd. Zuiver (geen WebKit) en dus testbaar.
public struct WebNavigationPolicy: Equatable {
    public var siteHost: String
    public var sitePathPrefix: String
    public var supabaseHost: String?
    public var supabaseAuthPathPrefix: String

    public init(siteHost: String, sitePathPrefix: String, supabaseHost: String?, supabaseAuthPathPrefix: String = MJOPConfig.supabaseAuthPathPrefix) {
        self.siteHost = siteHost.lowercased()
        self.sitePathPrefix = sitePathPrefix.hasSuffix("/") ? sitePathPrefix : sitePathPrefix + "/"
        self.supabaseHost = supabaseHost?.lowercased()
        self.supabaseAuthPathPrefix = supabaseAuthPathPrefix
    }

    public static let production = WebNavigationPolicy(
        siteHost: MJOPConfig.siteURL.host ?? "", sitePathPrefix: MJOPConfig.siteURL.path, supabaseHost: MJOPConfig.supabaseHost)

    private func isSitePath(_ path: String) -> Bool {
        // "/MJOP-App" (zonder slash) hoort ook bij de site; "/MJOP-App-evil/" niet.
        let p = path.isEmpty ? "/" : path
        return p.hasPrefix(sitePathPrefix) || p + "/" == sitePathPrefix
    }

    /// Is dit een https-adres binnen de toegestane MJOP-site (of Supabase-auth)?
    public func isAllowedInApp(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == "https", url.user == nil, url.password == nil,
              url.port == nil || url.port == 443, let host = url.host?.lowercased() else { return false }
        if host == siteHost { return isSitePath(url.path) }
        if let sb = supabaseHost, host == sb { return url.path.hasPrefix(supabaseAuthPathPrefix) }
        return false
    }

    /// - Parameters:
    ///   - isMainFrame: false voor iframes; die worden nooit extern geopend.
    ///   - userInitiated: true bij een tik op een link (alleen dan wordt een vreemd https-adres aan Safari overgedragen).
    public func decide(_ url: URL?, isMainFrame: Bool = true, userInitiated: Bool = false) -> WebNavigationDecision {
        guard let url = url, let scheme = url.scheme?.lowercased() else { return .block(reason: "geen geldig adres") }
        switch scheme {
        case "about":
            return url.absoluteString == "about:blank" ? .allowInApp : .block(reason: "onbekend about-adres")
        case "blob":
            // blob:https://host/uuid (bestandsdownloads van de website zelf); de oorsprong moet toegestaan zijn.
            let inner = String(url.absoluteString.dropFirst("blob:".count))
            if let u = URL(string: inner), u.scheme?.lowercased() == "https", u.host?.lowercased() == siteHost, u.port == nil || u.port == 443 { return .allowInApp }
            return .block(reason: "blob van onbekende oorsprong")
        case "https":
            if isAllowedInApp(url) { return .allowInApp }
            guard isMainFrame else { return .block(reason: "extern frame geblokkeerd") }
            guard userInitiated else { return .block(reason: "automatische doorverwijzing naar een ander domein geblokkeerd") }
            return .openExternally(url)
        case "mailto", "tel":
            return userInitiated && isMainFrame ? .openExternally(url) : .block(reason: "niet door gebruiker gestart")
        case "http":
            return .block(reason: "onversleuteld (http) adres geblokkeerd")
        default:
            return .block(reason: "schema \(scheme) niet toegestaan")
        }
    }
}
