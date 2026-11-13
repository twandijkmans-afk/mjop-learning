import Foundation
import MJOPEngine
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
    /// Eigen gevelfoto als projectfoto (pad in de bucket gevelfotos); nil = luchtfoto.
    var photoPath: String? = nil

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
                       updatedAt: str("updated_at").flatMap(Self.parseDate), rol: nil, photoPath: str("photo_path"))
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
                postenAantal: 11, geraamdTotaal: 14656, periodeVan: 2026, periodeTot: 2035, beoordeeld: 0, updatedAt: Date().addingTimeInterval(-2 * 3600), rol: "eigenaar"),
    ]
}

/// De projecten van de ingelogde gebruiker.
@MainActor
final class ProjectStore: ObservableObject {
    @Published private(set) var projects: [Project] = []
    @Published private(set) var loading = false
    @Published private(set) var error: String?
    /// Project dat geopend moet worden (bijv. na tikken op de widget).
    @Published var openRequest: String?
    @Published private(set) var loadedOnce = false

    func refresh(_ account: Account) async {
        if account.demo { projects = Project.demo; loadedOnce = true; return }
        loading = true
        defer { loading = false }
        do {
            let s = try await account.validSession()
            let cols = "id,naam,adres,postcode,plaats,bouwjaar,aantal_appartementen,posten_aantal,geraamd_totaal,periode_van,periode_tot,posten_beoordeeld,updated_at"
            let client = BackendClient(session: s)
            var (data, http) = try await client.request("rest/v1/projects", query: [URLQueryItem(name: "select", value: cols + ",photo_path"), URLQueryItem(name: "order", value: "updated_at.desc")])
            if http.statusCode == 400 {   // kolom photo_path bestaat nog niet (SQL voor gevelfoto's nog niet uitgevoerd)
                (data, http) = try await client.request("rest/v1/projects", query: [URLQueryItem(name: "select", value: cols), URLQueryItem(name: "order", value: "updated_at.desc")])
            }
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

    /// Maakt een project van een gevonden gebouw: standaardposten en planning met het rekenmodel, opslaan in `projects`.
    /// In de testbouw met `-mjop-demo` alleen lokaal.
    func create(from f: FoundBuilding, units: Int, account: Account) async throws -> Project {
        let year = Calendar.current.component(.year, from: Date())
        let input = BuildingLookup.buildingInput(pand: f.pand, threeD: f.threeD, units: units)
        let elements = Engine.defaultElements(for: input, year: year)
        let plan = Engine.plan(elements, year: year)
        let total = Engine.roundEuro(plan.reduce(Decimal(0)) { $0 + $1.bedrag })
        let totalInt = NSDecimalNumber(decimal: total).intValue
        let straat = [f.address.straat, f.address.huisnummer].compactMap { $0 }.joined(separator: " ")
        let naam = straat.isEmpty ? f.address.naam : straat

        var project = Project(id: UUID().uuidString.lowercased(), naam: naam, adres: straat.isEmpty ? nil : straat, postcode: f.address.postcode, plaats: f.address.plaats,
                              bouwjaar: f.pand.bouwjaar, appartementen: units, postenAantal: elements.count, geraamdTotaal: totalInt,
                              periodeVan: year, periodeTot: year + Engine.horizon - 1, beoordeeld: 0, updatedAt: Date(), rol: "eigenaar")
        if account.demo { projects.insert(project, at: 0); return project }

        let enc = JSONEncoder()
        let model: [String: Any] = [
            "building": (try? JSONSerialization.jsonObject(with: enc.encode(input))) ?? [:],
            "elements": (try? JSONSerialization.jsonObject(with: enc.encode(elements))) ?? [],
            "bronnen": ["bag_pand": f.pand.identificatie, "drie_d_bag": f.threeD != nil, "drie_d_kwaliteit_goed": jsonValue(f.threeD?.kwaliteitGoed)],
            "fonds": NSNull(), "bijdrage": NSNull(), "gevels": [],
            "sides": (try? JSONSerialization.jsonObject(with: enc.encode(f.pand.sides))) ?? [],
            "footprint": f.pand.ring,
        ]
        let row: [String: Any] = [
            "id": project.id, "naam": naam, "adres": jsonValue(project.adres), "postcode": jsonValue(project.postcode), "plaats": jsonValue(project.plaats),
            "bag_pand_id": f.pand.identificatie, "bouwjaar": jsonValue(f.pand.bouwjaar), "aantal_appartementen": units,
            "posten_aantal": elements.count, "posten_beoordeeld": 0, "geraamd_totaal": totalInt, "periode_van": year, "periode_tot": year + Engine.horizon - 1,
            "schema_version": 1, "model": model,
        ]
        let s = try await account.validSession()
        let (data, http) = try await BackendClient(session: s).request("rest/v1/projects", method: "POST", body: row, prefer: "return=representation")
        guard (200..<300).contains(http.statusCode) else { throw BackendError.message(BackendClient.message(data, status: http.statusCode)) }
        if let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]], let saved = rows.first.flatMap(Project.parse) { project = saved }
        projects.insert(project, at: 0)
        return project
    }
}

/// nil wordt JSON null (JSONSerialization kan geen Swift-Optional schrijven).
func jsonValue(_ v: Any?) -> Any { v ?? NSNull() }
