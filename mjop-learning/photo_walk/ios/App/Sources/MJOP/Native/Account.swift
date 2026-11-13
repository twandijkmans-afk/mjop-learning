import AuthenticationServices
import CryptoKit
import Foundation
import MJOPIntegration
import Security
import SwiftUI

/// Supabase-gegevens van MJOP Live (zelfde project als de website). De publieke sleutel mag in de app staan: wat iemand mag lezen of schrijven
/// bepaalt row-level security in de database. De service-role-sleutel hoort hier nooit.
enum Backend {
    static let url = URL(string: "https://\(MJOPConfig.supabaseHost)")!
    static let anonKey = "sb_publishable_IfhXai-_KQiHnf2tNcXeLQ_k2FsUaN0"
    static let redirect = "\(MJOPConfig.appURLScheme)://\(MJOPConfig.authCallbackHost)"
    static let subscribeURL = URL(string: "https://twandijkmans-afk.github.io/MJOP-App/")!
}

/// Een ingelogde sessie. De tokens staan alleen in de Keychain van dit toestel.
struct Session: Codable, Equatable {
    var accessToken: String
    var refreshToken: String
    var expiresAt: Date
    var userId: String
    var email: String?
}

enum BackendError: LocalizedError {
    case message(String)
    case notConfigured(String)
    case offline

    var errorDescription: String? {
        switch self {
        case .message(let m): return m
        case .notConfigured(let m): return m
        case .offline: return "Geen verbinding. Controleer je internet en probeer het opnieuw."
        }
    }
}

/// Kleine REST-client voor Supabase Auth (GoTrue) en de database (PostgREST). Geen externe bibliotheek nodig.
struct BackendClient {
    var session: Session?

    static let offlineCodes: [URLError.Code] = [.notConnectedToInternet, .networkConnectionLost, .timedOut, .cannotFindHost, .cannotConnectToHost]

    func request(_ path: String, method: String = "GET", query: [URLQueryItem] = [], body: Any? = nil, prefer: String? = nil) async throws -> (Data, HTTPURLResponse) {
        var c = URLComponents(url: Backend.url.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { c.queryItems = query }
        var r = URLRequest(url: c.url!)
        r.httpMethod = method
        r.timeoutInterval = 20
        r.setValue(Backend.anonKey, forHTTPHeaderField: "apikey")
        r.setValue("Bearer \(session?.accessToken ?? Backend.anonKey)", forHTTPHeaderField: "Authorization")
        r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let prefer { r.setValue(prefer, forHTTPHeaderField: "Prefer") }
        if let body { r.httpBody = try JSONSerialization.data(withJSONObject: body) }
        do {
            let (data, resp) = try await URLSession.shared.data(for: r)
            guard let http = resp as? HTTPURLResponse else { throw BackendError.offline }
            return (data, http)
        } catch let e as URLError where Self.offlineCodes.contains(e.code) {
            throw BackendError.offline
        }
    }

    /// Nederlandse foutmelding uit een antwoord van Supabase.
    static func message(_ data: Data, status: Int) -> String {
        let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        let code = (obj["error_code"] as? String) ?? (obj["code"] as? String) ?? (obj["error"] as? String) ?? ""
        switch code {
        case "invalid_credentials", "invalid_grant": return "E-mailadres of wachtwoord klopt niet."
        case "email_not_confirmed": return "Bevestig eerst je e-mailadres via de mail die je hebt gekregen."
        case "user_already_exists": return "Er bestaat al een account met dit e-mailadres. Log in of kies 'Wachtwoord vergeten'."
        case "weak_password": return "Kies een sterker wachtwoord (minstens 8 tekens)."
        case "over_email_send_rate_limit", "over_request_rate_limit": return "Even te veel pogingen. Probeer het over een paar minuten opnieuw."
        case "PGRST205", "42P01": return "De database is nog niet bijgewerkt voor de nieuwe app (tabel 'projects' ontbreekt)."
        default:
            let msg = (obj["msg"] as? String) ?? (obj["message"] as? String) ?? (obj["error_description"] as? String)
            return msg.map { "Er ging iets mis: \($0)" } ?? "Er ging iets mis (\(status)). Probeer het opnieuw."
        }
    }

    static func session(from data: Data) -> Session? {
        guard let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let at = o["access_token"] as? String, let rt = o["refresh_token"] as? String,
              let user = o["user"] as? [String: Any], let uid = user["id"] as? String else { return nil }
        let expiresIn = (o["expires_in"] as? Double) ?? 3600
        return Session(accessToken: at, refreshToken: rt, expiresAt: Date().addingTimeInterval(expiresIn - 60), userId: uid, email: user["email"] as? String)
    }
}

/// Opslag van de sessie in de Keychain (alleen dit toestel, alleen na ontgrendelen).
enum SessionVault {
    private static let service = "nl.mjop.live.session"

    static func save(_ s: Session?) {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "default"]
        SecItemDelete(base as CFDictionary)
        guard let s, let data = try? JSONEncoder().encode(s) else { return }
        var add = base
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    static func load() -> Session? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "default",
                                kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else { return nil }
        return try? JSONDecoder().decode(Session.self, from: data)
    }
}

/// Het account van de gebruiker: inloggen, registreren, wachtwoord herstellen, uitloggen, en een geldige sessie voor de database.
@MainActor
final class Account: ObservableObject {
    enum State: Equatable { case loading, signedOut, signedIn, newPassword }

    @Published private(set) var state: State = .loading
    @Published private(set) var session: Session?
    @Published var firstName: String?
    @Published var lastName: String?
    @Published var info: String?
    /// Vergrendeld met Face ID: de sessie is er, maar de app toont het vergrendelscherm tot de gebruiker ontgrendelt.
    @Published private(set) var locked = false

    let demo: Bool
    private var pkceVerifier: String? {
        get { UserDefaults.standard.string(forKey: "mjop.pkce") }
        set { UserDefaults.standard.set(newValue, forKey: "mjop.pkce") }
    }
    /// Waarvoor de lopende PKCE-aanvraag is: "recovery" (nieuw wachtwoord) of "oauth" (inloggen met Google).
    private var pkcePurpose: String? {
        get { UserDefaults.standard.string(forKey: "mjop.pkce.purpose") }
        set { UserDefaults.standard.set(newValue, forKey: "mjop.pkce.purpose") }
    }
    private var webAuth: ASWebAuthenticationSession?
    private let webAuthAnchor = WebAuthAnchor()

    init() {
        #if DEBUG
        demo = CommandLine.arguments.contains("-mjop-demo")
        #else
        demo = false
        #endif
    }

    var client: BackendClient { BackendClient(session: session) }
    var displayName: String? {
        let n = [firstName, lastName].compactMap { $0?.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }.joined(separator: " ")
        return n.isEmpty ? nil : n
    }

    func start() async {
        if demo {
            session = Session(accessToken: "demo", refreshToken: "demo", expiresAt: .distantFuture, userId: "demo", email: "demo@voorbeeld.nl")
            firstName = "Twan"; lastName = "Dijkmans"
            state = .signedIn
            return
        }
        guard let s = SessionVault.load() else { state = .signedOut; return }
        session = s
        locked = BiometricLock.enabled
        state = .signedIn
        _ = try? await validSession()
        await loadProfile()
    }

    /// Ververst de sessie als die (bijna) verlopen is. Lukt dat niet omdat de sessie ongeldig is, dan uitgelogd.
    func validSession() async throws -> Session {
        guard let s = session else { throw BackendError.message("Je bent niet ingelogd.") }
        if demo || s.expiresAt > Date() { return s }
        let (data, http) = try await BackendClient(session: nil).request("auth/v1/token", method: "POST", query: [URLQueryItem(name: "grant_type", value: "refresh_token")], body: ["refresh_token": s.refreshToken])
        guard http.statusCode == 200, let fresh = BackendClient.session(from: data) else {
            if (400..<500).contains(http.statusCode) { signOutLocally() }
            throw BackendError.message(BackendClient.message(data, status: http.statusCode))
        }
        session = fresh
        SessionVault.save(fresh)
        return fresh
    }

    func signIn(email: String, password: String) async throws {
        let (data, http) = try await BackendClient(session: nil).request("auth/v1/token", method: "POST", query: [URLQueryItem(name: "grant_type", value: "password")],
                                                                          body: ["email": email.trimmingCharacters(in: .whitespaces), "password": password])
        guard http.statusCode == 200, let s = BackendClient.session(from: data) else { throw BackendError.message(BackendClient.message(data, status: http.statusCode)) }
        adopt(s)
        await loadProfile()
    }

    /// Nieuw account. Vraagt Supabase om bevestiging per mail, dan is er nog geen sessie: we melden dat.
    func signUp(email: String, password: String) async throws {
        let (data, http) = try await BackendClient(session: nil).request("auth/v1/signup", method: "POST", query: [URLQueryItem(name: "redirect_to", value: Backend.redirect)],
                                                                          body: ["email": email.trimmingCharacters(in: .whitespaces), "password": password])
        guard (200..<300).contains(http.statusCode) else { throw BackendError.message(BackendClient.message(data, status: http.statusCode)) }
        if let s = BackendClient.session(from: data) { adopt(s); await loadProfile() }
        else { info = "Account aangemaakt. Bevestig je e-mailadres via de mail die je net hebt gekregen, en log daarna in." }
    }

    /// Mail om een (nieuw) wachtwoord in te stellen. Met PKCE: de link brengt alleen een eenmalige code terug naar de app.
    func sendPasswordReset(email: String) async throws {
        let verifier = Self.randomVerifier()
        pkceVerifier = verifier
        pkcePurpose = "recovery"
        let challenge = Self.challenge(for: verifier)
        let (data, http) = try await BackendClient(session: nil).request("auth/v1/recover", method: "POST", query: [URLQueryItem(name: "redirect_to", value: Backend.redirect)],
                                                                          body: ["email": email.trimmingCharacters(in: .whitespaces), "code_challenge": challenge, "code_challenge_method": "s256"])
        guard (200..<300).contains(http.statusCode) else { throw BackendError.message(BackendClient.message(data, status: http.statusCode)) }
        info = "Als er een account met dit adres bestaat, krijg je een mail met een link. Open die op deze iPhone."
    }

    /// Terugkeer uit de mail (`mjoplive://auth-callback?code=…`): de code inwisselen voor een sessie en een nieuw wachtwoord laten kiezen.
    func handle(url: URL) async {
        switch AuthCallback.parse(url) {
        case .code(let code):
            guard let verifier = pkceVerifier else { info = "Deze link hoort bij een andere aanvraag. Vraag een nieuwe aan."; return }
            do {
                let (data, http) = try await BackendClient(session: nil).request("auth/v1/token", method: "POST", query: [URLQueryItem(name: "grant_type", value: "pkce")],
                                                                                  body: ["auth_code": code, "code_verifier": verifier])
                guard http.statusCode == 200, let s = BackendClient.session(from: data) else { info = BackendClient.message(data, status: http.statusCode); return }
                pkceVerifier = nil
                let viaOAuth = pkcePurpose == "oauth"
                pkcePurpose = nil
                adopt(s)
                if !viaOAuth { state = .newPassword }   // wachtwoordherstel: nieuw wachtwoord kiezen; Google: gewoon ingelogd
                await loadProfile()
            } catch { info = error.localizedDescription }
        case .failure(let m): info = m
        case .rejected: info = "Deze link kan de app niet gebruiken. Vraag een nieuwe aan."
        }
    }

    /// Staat een externe inlogdienst (bijv. "google") aan in Supabase? Leest de openbare instellingen; nil als dat niet lukt.
    func providerEnabled(_ provider: String) async -> Bool? {
        guard let res = try? await BackendClient(session: nil).request("auth/v1/settings"), res.1.statusCode == 200,
              let o = (try? JSONSerialization.jsonObject(with: res.0)) as? [String: Any],
              let ext = o["external"] as? [String: Any] else { return nil }
        return ext[provider] as? Bool
    }

    /// Inloggen met Google via Supabase (OAuth met PKCE). Het venster van Apple (ASWebAuthenticationSession) opent de inlogpagina;
    /// de terugkeer (`mjoplive://auth-callback?code=…`) gaat door dezelfde inwisseling als het wachtwoordherstel.
    func signInWithGoogle() async throws {
        if await providerEnabled("google") == false {
            throw BackendError.message("Inloggen met Google is nog niet ingesteld in Supabase. Log voorlopig in met je e-mailadres.")
        }
        let verifier = Self.randomVerifier()
        pkceVerifier = verifier
        pkcePurpose = "oauth"
        var c = URLComponents(url: Backend.url.appendingPathComponent("auth/v1/authorize"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "provider", value: "google"), URLQueryItem(name: "redirect_to", value: Backend.redirect),
                        URLQueryItem(name: "code_challenge", value: Self.challenge(for: verifier)), URLQueryItem(name: "code_challenge_method", value: "s256")]
        guard let url = c.url else { return }
        let callback: URL = try await withCheckedThrowingContinuation { cont in
            let session = ASWebAuthenticationSession(url: url, callbackURLScheme: MJOPConfig.appURLScheme) { url, error in
                if let url { cont.resume(returning: url) }
                else if let e = error as? ASWebAuthenticationSessionError, e.code == .canceledLogin { cont.resume(throwing: CancellationError()) }
                else { cont.resume(throwing: BackendError.message("Inloggen met Google is niet gelukt.")) }
            }
            session.presentationContextProvider = webAuthAnchor
            session.prefersEphemeralWebBrowserSession = false
            webAuth = session
            session.start()
        }
        webAuth = nil
        await handle(url: callback)
    }

    func setPassword(_ password: String) async throws {
        let s = try await validSession()
        let (data, http) = try await BackendClient(session: s).request("auth/v1/user", method: "PUT", body: ["password": password])
        guard http.statusCode == 200 else { throw BackendError.message(BackendClient.message(data, status: http.statusCode)) }
        state = .signedIn
    }

    func skipNewPassword() { state = .signedIn }

    func signOut() async {
        if let s = session, !demo { _ = try? await BackendClient(session: s).request("auth/v1/logout", method: "POST") }
        signOutLocally()
    }

    /// Vergrendelt na een tijd op de achtergrond (alleen met een sessie en als Face ID aan staat).
    func lockIfNeeded() {
        guard !demo, state == .signedIn, BiometricLock.enabled else { return }
        locked = true
    }

    func unlock() { locked = false }

    private func signOutLocally() {
        session = nil; firstName = nil; lastName = nil
        locked = false
        SessionVault.save(nil)
        state = .signedOut
    }

    private func adopt(_ s: Session) {
        session = s
        SessionVault.save(s)
        state = .signedIn
    }

    /// Voornaam en achternaam uit de bestaande tabel `profiles` (zelfde als de website). Ontbreken ze, dan blijft het leeg.
    func loadProfile() async {
        guard !demo, let s = try? await validSession() else { return }
        guard let res = try? await BackendClient(session: s).request("rest/v1/profiles", query: [URLQueryItem(name: "id", value: "eq.\(s.userId)"), URLQueryItem(name: "select", value: "voornaam,achternaam")]),
              res.1.statusCode == 200, let rows = (try? JSONSerialization.jsonObject(with: res.0)) as? [[String: Any]], let row = rows.first else { return }
        firstName = row["voornaam"] as? String
        lastName = row["achternaam"] as? String
    }

    // MARK: PKCE

    static func randomVerifier() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64URL
    }

    static func challenge(for verifier: String) -> String {
        Data(SHA256.hash(data: Data(verifier.utf8))).base64URL
    }
}

extension Data {
    var base64URL: String {
        base64EncodedString().replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
    }
}

/// Venster waarin het inlogscherm van Google verschijnt.
final class WebAuthAnchor: NSObject, ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first ?? ASPresentationAnchor()
    }
}
