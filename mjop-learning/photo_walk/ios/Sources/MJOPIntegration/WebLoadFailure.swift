import Foundation

/// Gebruikersgerichte classificatie van een mislukte paginalading in de webweergave.
public struct WebLoadFailure: Equatable {
    public enum Kind: Equatable { case offline, timeout, unreachable, security, http(Int), blocked, other }
    public let kind: Kind
    public let title: String
    public let message: String
    public let canRetry: Bool

    public var isOffline: Bool { kind == .offline }

    /// nil = geen melding nodig (bijv. zelf geannuleerde navigatie).
    public static func classify(domain: String, code: Int) -> WebLoadFailure? {
        guard domain == NSURLErrorDomain else {
            return WebLoadFailure(kind: .other, title: "Pagina niet geladen", message: "Er ging iets mis bij het laden van Mijn MJOP. Probeer het opnieuw.", canRetry: true)
        }
        switch code {
        case NSURLErrorCancelled:
            return nil
        case NSURLErrorNotConnectedToInternet, NSURLErrorNetworkConnectionLost, NSURLErrorDataNotAllowed, NSURLErrorInternationalRoamingOff, NSURLErrorCallIsActive:
            return WebLoadFailure(kind: .offline, title: "Je bent offline",
                                  message: "Mijn MJOP heeft internet nodig (adres opzoeken, inloggen, opslaan). De Gevelscanner werkt ook zonder internet. Je opgeslagen plannen blijven veilig bewaard.", canRetry: true)
        case NSURLErrorTimedOut:
            return WebLoadFailure(kind: .timeout, title: "Verbinding te traag", message: "De verbinding met Mijn MJOP duurde te lang. Controleer je internet en probeer het opnieuw.", canRetry: true)
        case NSURLErrorCannotFindHost, NSURLErrorCannotConnectToHost, NSURLErrorDNSLookupFailed:
            return WebLoadFailure(kind: .unreachable, title: "Mijn MJOP niet bereikbaar", message: "De website is nu niet bereikbaar. Probeer het later opnieuw.", canRetry: true)
        case NSURLErrorSecureConnectionFailed, NSURLErrorServerCertificateUntrusted, NSURLErrorServerCertificateHasBadDate,
             NSURLErrorServerCertificateHasUnknownRoot, NSURLErrorServerCertificateNotYetValid, NSURLErrorClientCertificateRejected,
             NSURLErrorAppTransportSecurityRequiresSecureConnection:
            return WebLoadFailure(kind: .security, title: "Beveiligde verbinding mislukt", message: "Er kon geen veilige verbinding met Mijn MJOP worden gemaakt. Gebruik geen openbare wifi en probeer het opnieuw.", canRetry: true)
        default:
            return WebLoadFailure(kind: .other, title: "Pagina niet geladen", message: "Er ging iets mis bij het laden van Mijn MJOP (code \(code)). Probeer het opnieuw.", canRetry: true)
        }
    }

    public static func http(status: Int) -> WebLoadFailure? {
        guard status >= 400 else { return nil }
        let msg = status == 404 ? "Deze pagina bestaat niet (meer)." : status >= 500 ? "De website heeft een storing. Probeer het later opnieuw." : "De website gaf een foutmelding (\(status))."
        return WebLoadFailure(kind: .http(status), title: "Pagina niet beschikbaar", message: msg, canRetry: true)
    }

    public static func blocked(reason: String) -> WebLoadFailure {
        WebLoadFailure(kind: .blocked, title: "Link geblokkeerd", message: "Deze link is om veiligheidsredenen niet in de app geopend (\(reason)).", canRetry: false)
    }
}
