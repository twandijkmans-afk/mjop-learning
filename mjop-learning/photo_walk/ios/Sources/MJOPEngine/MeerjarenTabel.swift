import Foundation

/// De meerjarentabel voor het rapport: per post de kosten per jaar over de planningshorizon, gegroepeerd per NL-SfB-hoofdgroep,
/// met subtotalen per groep en een totaal per jaar. Puur rekenwerk op het plan van `Engine`; niets wordt geschat.
/// Een post waarvan de kosten niet te berekenen zijn staat er wel in, gemarkeerd als "bedrag onbekend" (nooit stil € 0).
public enum MeerjarenTabel {
    public struct Row: Equatable {
        public var key: String
        public var naam: String
        /// NL-SfB-code zoals in de elementenbibliotheek (bijv. "27.1"); nil voor een post buiten de bibliotheek.
        public var sfb: String?
        /// Hoeveelheid; nil als die onbekend is of de post geen hoeveelheid heeft (vast bedrag).
        public var quantity: Decimal?
        public var unit: String?
        /// Eerste jaar binnen de horizon; nil als er niets gepland is.
        public var startYear: Int?
        /// Cyclus in jaren; meerdere bij kozijnen van verschillend materiaal.
        public var cycles: [Int]
        /// Staat volgens NEN 2767 (1–6), nil = niet beoordeeld.
        public var conditie: Int?
        public var perYear: [Int: Decimal]
        public var total: Decimal
        /// De kosten zijn niet te berekenen (hoeveelheid of werkhoogte ontbreekt).
        public var costUnknown: Bool
        /// Prijs uit een offerte in plaats van de standaardraming.
        public var fromQuote: Bool
    }

    public struct Group: Equatable {
        /// Hoofdgroep, de eerste twee cijfers van de NL-SfB-code (bijv. "27"); "–" zonder code.
        public var code: String
        public var naam: String
        public var rows: [Row]
        public var perYear: [Int: Decimal]
        public var total: Decimal
        public var hasUnknown: Bool { rows.contains(where: \.costUnknown) }
    }

    public struct Result: Equatable {
        public var years: [Int]
        public var groups: [Group]
        public var perYear: [Int: Decimal]
        public var total: Decimal
        public var hasUnknown: Bool { groups.contains(where: \.hasUnknown) }
    }

    /// Namen van de NL-SfB-hoofdgroepen die in de elementenbibliotheek voorkomen. Een onbekende code krijgt de categorie van de post.
    public static let groupNames: [String: String] = [
        "21": "Buitenwanden", "22": "Binnenwanden", "23": "Vloeren", "24": "Trappen en hellingen", "27": "Daken",
        "28": "Hoofddraagconstructies", "31": "Buitenwandopeningen", "32": "Binnenwandopeningen", "34": "Balustrades en leuningen",
        "37": "Dakopeningen", "41": "Buitenwandafwerkingen", "42": "Binnenwandafwerkingen", "43": "Vloerafwerkingen",
        "45": "Plafondafwerkingen", "47": "Dakafwerkingen", "51": "Warmteopwekking", "52": "Afvoeren", "53": "Water",
        "56": "Warmtedistributie", "57": "Luchtbehandeling", "61": "Centrale elektrotechnische voorzieningen",
        "62": "Krachtstroom", "63": "Verlichting", "64": "Communicatie", "65": "Beveiliging", "66": "Transport",
    ]

    /// De hoofdgroep van een NL-SfB-code: "27.1" → "27", "62/63" → "62"; nil bij geen of een onleesbare code.
    public static func mainGroup(_ sfb: String?) -> String? {
        guard let s = sfb else { return nil }
        let digits = s.prefix { $0.isNumber }
        return digits.count >= 2 ? String(digits.prefix(2)) : nil
    }

    public static func make(elements: [PlanElement], year: Int, horizon: Int = Engine.horizon) -> Result {
        let years = Array(year...(year + horizon - 1))
        let plan = Engine.plan(elements, year: year)
        let byKey = Dictionary(grouping: plan, by: \.key)
        let sfbByKey = Dictionary(Engine.library.map { ($0.key, $0.sfb) }, uniquingKeysWith: { a, _ in a })

        var rows: [(group: String, groupName: String, row: Row)] = []
        for el in elements {
            let items = byKey[el.key] ?? []
            var py: [Int: Decimal] = [:]
            for c in items { py[c.jaar, default: 0] += c.bedrag }
            let total = items.reduce(Decimal(0)) { $0 + $1.bedrag }
            let unknown = Engine.cost(el) == nil
            var q: Decimal? = el.quantity?.value, unit: String? = el.quantity?.unit
            var cycles = [el.cyclus]
            if el.type == .kozijnen, el.prijsOfferte == nil, let k = el.kozijnen, !k.isEmpty {
                let known = k.compactMap(\.aantal.value)
                q = known.count == k.count ? known.reduce(0, +) : nil
                unit = "st"
                cycles = Array(Set(k.map(\.materiaal.cyclus))).sorted()
            }
            let sfb = sfbByKey[el.key]
            let g = mainGroup(sfb)
            let row = Row(key: el.key, naam: el.naam, sfb: sfb, quantity: q, unit: q == nil ? nil : unit,
                          startYear: items.map(\.jaar).min(), cycles: cycles, conditie: el.conditie,
                          perYear: py, total: total, costUnknown: unknown, fromQuote: el.prijsOfferte != nil)
            rows.append((g ?? "–", g.flatMap { groupNames[$0] } ?? el.categorie, row))
        }

        var groups: [Group] = []
        let codes = Array(Set(rows.map(\.group))).sorted { a, b in
            if a == "–" { return false }
            if b == "–" { return true }
            return a < b
        }
        for code in codes {
            let rs = rows.filter { $0.group == code }
            var py: [Int: Decimal] = [:]
            for r in rs { for (j, v) in r.row.perYear { py[j, default: 0] += v } }
            let sorted = rs.map(\.row).sorted { ($0.sfb ?? "", $0.naam) < ($1.sfb ?? "", $1.naam) }
            groups.append(Group(code: code, naam: rs.first?.groupName ?? "Overig", rows: sorted, perYear: py,
                                total: sorted.reduce(Decimal(0)) { $0 + $1.total }))
        }
        var py: [Int: Decimal] = [:]
        for g in groups { for (j, v) in g.perYear { py[j, default: 0] += v } }
        return Result(years: years, groups: groups, perYear: py, total: groups.reduce(Decimal(0)) { $0 + $1.total })
    }
}
