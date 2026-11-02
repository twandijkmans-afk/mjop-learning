import Foundation

/// Vaste, niet-geheime configuratie van de MJOP-webweergave. Alleen publieke adressen; geen sleutels of tokens.
public enum MJOPConfig {
    /// Productieadres van de bestaande MJOP-website (GitHub Pages van twandijkmans-afk/MJOP-App).
    public static let siteURL = URL(string: "https://twandijkmans-afk.github.io/MJOP-App/")!
    /// Publiek Supabase-projectadres (staat ook in src/config.js van de website). Alleen /auth/v1/ mag in de app worden geopend.
    public static let supabaseHost = "tcxmkmbupbknklwiijoq.supabase.co"
    public static let supabaseAuthPathPrefix = "/auth/v1/"
    /// Eigen URL-schema voor het terugkeren uit de browser na inloggen (zie docs/mjop_integration.md).
    public static let appURLScheme = "mjoplive"
    public static let authCallbackHost = "auth-callback"
    /// Wordt aan de User-Agent toegevoegd zodat de website kan herkennen dat hij in de app draait.
    /// Versie 2 = de app toont zelf de tabbalk (native navigatie). De bestaande website herkent elk `MJOPLiveApp/<n>`, dus dit breekt niets;
    /// een website die de native navigatie niet kent meldt zich nooit met `webReady` en de app valt dan terug op de klassieke weergave.
    public static let userAgentSuffix = "MJOPLiveApp/\(NativeNav.appLevel)"
}
