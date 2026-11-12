import Foundation
import SwiftUI

/// Een project (gebouw) uit de tabel `projects` (nieuw datamodel, zie supabase/migrations in MJOP-App). Alleen echte gegevens: onbekend is `nil`.
struct Project: Identifiable, Equatable {
    var id: String
    var naam: String
    var adres: String?
    var postcode: String?
    var plaats: String?
    var bouwjaar: Int?
    var appartementen: Int?
    var postenAantal: Int?
    var geraamdTotaal: Int?
    var periodeVan: Int?
    var periodeTot: Int?
    var beoordeeld: Int?
    var updatedAt: Date?
    var rol: String?

    /// Volledig adres voor de luchtfoto en de weergave.
    var fullAddress: String? {
        let a = [adres, [postcode, plaats].compactMap { $0 }.joined(separator: " ")].compactMap { $0 }.filter { !$0.isEmpty }
        return a.isEmpty ? nil : a.joined(separator: ", ")
    }

    var subtitle: String {
        var parts: [String] = []
        if let p = plaats { parts.append(p) }
        if let b = bouwjaar { parts.append("bouwjaar \(b)") }
        return parts.isEmpty ? (fullAddress ?? "Adres onbekend") : parts.joined(separator: " · ")
    }

    static func parse(_ o: [String: Any]) -> Project? {
        guard let id = o["id"] as? String, let naam = o["naam"] as? String else { return nil }
        func int(_ k: String) -> Int? { (o[k] as? Int) ?? (o[k] as? Double).map { Int($0) } }
        func str(_ k: String) -> String? { (o[k] as? String).flatMap { $0.isEmpty ? nil : $0 } }
        return Project(id: id, naam: naam, adres: str("adres"), postcode: str("postcode"), plaats: str("plaats"), bouwjaar: int("bouwjaar"),
                       appartementen: int("aantal_appartementen"), postenAantal: int("posten_aantal"), geraamdTotaal: int("geraamd_totaal"),
                       periodeVan: int("periode_van"), periodeTot: int("periode_tot"), beoordeeld: int("posten_beoordeeld"),
                       updatedAt: str("updated_at").flatMap(Self.parseDate), rol: nil)
    }

    static func parseDate(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }

    /// Voorbeeldproject alleen voor de schermafbeeldingen in de testbouw (`-mjop-demo`): gegevens van de gebruiker zelf (Singelstraat 8).
    static let demo: [Project] = [
        Project(id: "demo-1", naam: "Singelstraat 8", adres: "Singelstraat 8", postcode: "1398 BN", plaats: "Muiden", bouwjaar: 1925, appartementen: 1,
                postenAantal: 11, geraamdTotaal: 14656, periodeVan: 2026, periodeTot: 2035, beoordeeld: 0, updatedAt: Date(), rol: "eigenaar"),
    ]
}

/// De projecten van de ingelogde gebruiker.
@MainActor
final class ProjectStore: ObservableObject {
    @Published private(set) var projects: [Project] = []
    @Published private(set) var loading = false
    @Published private(set) var error: String?
    @Published private(set) var loadedOnce = false

    func refresh(_ account: Account) async {
        if account.demo { projects = Project.demo; loadedOnce = true; return }
        loading = true
        defer { loading = false }
        do {
            let s = try await account.validSession()
            let cols = "id,naam,adres,postcode,plaats,bouwjaar,aantal_appartementen,posten_aantal,geraamd_totaal,periode_van,periode_tot,posten_beoordeeld,updated_at"
            let (data, http) = try await BackendClient(session: s).request("rest/v1/projects", query: [URLQueryItem(name: "select", value: cols), URLQueryItem(name: "order", value: "updated_at.desc")])
            guard http.statusCode == 200, let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
                error = BackendClient.message(data, status: http.statusCode); loadedOnce = true; return
            }
            projects = rows.compactMap(Project.parse)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        loadedOnce = true
    }

    func clear() { projects = []; loadedOnce = false; error = nil }
}
