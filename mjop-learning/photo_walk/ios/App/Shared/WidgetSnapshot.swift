import Foundation

/// Samenvatting van het laatst geopende project voor de widget op het beginscherm. De app schrijft hem in de gedeelde
/// App Group; de widget leest hem alleen (geen netwerk). Onbekend blijft onbekend (nil): niets wordt aangevuld.
struct WidgetSnapshot: Codable, Equatable {
    static let appGroup = "group.nl.mjop.photowalk"
    static let key = "mjop.widget.snapshot"

    var projectId: String
    var naam: String
    /// Huidige stand van het reservefonds (zoals ingevuld); nil als onbekend.
    var fondsNu: Int?
    /// Laagste stand in de planperiode en het jaar; nil zonder fonds of bijdrage.
    var laagsteStand: Int?
    var laagsteJaar: Int?
    /// Eerstvolgend jaar met gepland onderhoud, de eerste posten en het geraamde bedrag van dat jaar.
    var volgendJaar: Int?
    var volgendPosten: [String]
    var volgendBedrag: Int?
    var bijgewerkt: Date

    static func load() -> WidgetSnapshot? {
        guard let d = UserDefaults(suiteName: appGroup)?.data(forKey: key) else { return nil }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return try? dec.decode(WidgetSnapshot.self, from: d)
    }

    func save() {
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        guard let d = try? enc.encode(self) else { return }
        UserDefaults(suiteName: Self.appGroup)?.set(d, forKey: Self.key)
    }

    static func euro(_ v: Int) -> String {
        let f = NumberFormatter(); f.numberStyle = .currency; f.currencyCode = "EUR"; f.locale = Locale(identifier: "nl_NL"); f.maximumFractionDigits = 0
        return f.string(from: NSNumber(value: v)) ?? "€ \(v)"
    }
}
