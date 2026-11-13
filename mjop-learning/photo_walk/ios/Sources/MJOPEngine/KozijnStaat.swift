import Foundation

// Kozijnstaat: kozijnen van alle gescande gevels gegroepeerd per type, met vaste regels (geen AI).
// Het best zichtbare kozijn van een type geeft de maat; het aantal komt uit de telling.
// Een deels verborgen kozijn krijgt de maat van zijn type (afgeleid) als dat eenduidig is, anders blijft het niet toegewezen.

/// Eén kozijn zoals gemeten op een gevelfoto.
public struct KozijnItem: Codable, Equatable, Identifiable {
    /// Sleutel `gevelzijde:element`, waarmee de keuzes van de gebruiker worden bewaard.
    public var id: String { "\(sideId):\(elementId)" }
    public var sideId: Int
    public var elementId: Int
    public var type: FacadeElementType
    public var material: String?
    public var widthM: Double?
    public var heightM: Double?
    public var hiddenFraction: Double?

    public init(sideId: Int, elementId: Int, type: FacadeElementType, material: String?, widthM: Double?, heightM: Double?, hiddenFraction: Double?) {
        self.sideId = sideId; self.elementId = elementId; self.type = type; self.material = material
        self.widthM = widthM; self.heightM = heightM; self.hiddenFraction = hiddenFraction
    }

    /// Goed genoeg zichtbaar om zelf de maat te geven.
    public var wellVisible: Bool {
        guard let w = widthM, let h = heightM, w > 0, h > 0 else { return false }
        return (hiddenFraction ?? 0) <= KozijnStaat.hiddenLimit
    }
}

public struct KozijnMember: Equatable, Identifiable {
    public var id: String { item.id }
    public var item: KozijnItem
    /// Maat overgenomen van het type (kozijn deels verborgen) in plaats van zelf gemeten.
    public var derived: Bool
}

public struct KozijnType: Equatable, Identifiable {
    /// Vaste sleutel: het referentiekozijn waarmee het type begon.
    public var id: String
    public var letter: String
    public var type: FacadeElementType
    public var material: String?
    public var widthM: Double
    public var heightM: Double
    public var members: [KozijnMember]
    /// Door de gebruiker samengevoegd of apart gezet.
    public var editedByUser: Bool

    public var count: Int { members.count }
    public var derivedCount: Int { members.filter(\.derived).count }
    public var label: String { [type.label, material].compactMap { $0 }.joined(separator: " ") }
}

/// Keuzes van de gebruiker: typen samenvoegen en kozijnen apart zetten. De automatische indeling blijft daarnaast altijd te herleiden.
public struct KozijnOverrides: Codable, Equatable {
    /// Typesleutel → typesleutel waarin het is opgegaan.
    public var merge: [String: String]
    /// Kozijnen (sleutel `gevelzijde:element`) die een eigen type krijgen.
    public var separate: [String]
    public init(merge: [String: String] = [:], separate: [String] = []) { self.merge = merge; self.separate = separate }
    public var isEmpty: Bool { merge.isEmpty && separate.isEmpty }
}

public struct KozijnStaatResult: Equatable {
    public var types: [KozijnType]
    /// Kozijnen waarvan de maat niet eenduidig is af te leiden: ze tellen mee in het aantal, maar hebben (nog) geen type.
    public var unassigned: [KozijnItem]
    public var total: Int { types.reduce(0) { $0 + $1.count } + unassigned.count }
}

public enum KozijnStaat {
    /// Breedte en hoogte binnen ±7% = zelfde type.
    public static let tolerance = 0.07
    /// Een verborgen kozijn hoort bij een type als de breedte binnen ±10% ligt (de hoogte is vaak niet te zien).
    public static let hiddenTolerance = 0.10
    /// Meer dan 25% verborgen: de eigen maat telt niet.
    public static let hiddenLimit = 0.25

    static func rel(_ a: Double, _ b: Double) -> Double { abs(a - b) / b }
    static func sameMaterial(_ a: String?, _ b: String?) -> Bool {
        guard let a = a?.lowercased(), let b = b?.lowercased(), !a.isEmpty, !b.isEmpty else { return true }
        return a == b
    }
    static func order(_ t: FacadeElementType) -> Int {
        switch t { case .kozijn_raam: return 0; case .kozijn_deur: return 1; case .garagedeur: return 2; default: return 3 }
    }

    private struct Group {
        var key: String
        var type: FacadeElementType
        var material: String?
        var w: Double, h: Double
        var members: [KozijnMember]
        var single: Bool
        var edited: Bool
    }

    public static func make(_ all: [KozijnItem], overrides: KozijnOverrides = KozijnOverrides()) -> KozijnStaatResult {
        let items = all.filter { $0.type.isOpening }
        let separate = Set(overrides.separate)
        let visible = items.filter(\.wellVisible).sorted {
            let ha = $0.hiddenFraction ?? 0, hb = $1.hiddenFraction ?? 0
            if ha != hb { return ha < hb }
            let aa = $0.widthM! * $0.heightM!, ab = $1.widthM! * $1.heightM!
            if aa != ab { return aa > ab }
            return $0.id < $1.id
        }
        var groups: [Group] = []
        for it in visible {
            let w = it.widthM!, h = it.heightM!
            if separate.contains(it.id) {
                groups.append(Group(key: it.id, type: it.type, material: it.material, w: w, h: h, members: [KozijnMember(item: it, derived: false)], single: true, edited: true))
                continue
            }
            let fits = groups.indices.filter { i in
                let g = groups[i]
                return !g.single && g.type == it.type && sameMaterial(g.material, it.material) && rel(w, g.w) <= tolerance && rel(h, g.h) <= tolerance
            }
            if let best = fits.min(by: { rel(w, groups[$0].w) + rel(h, groups[$0].h) < rel(w, groups[$1].w) + rel(h, groups[$1].h) }) {
                groups[best].members.append(KozijnMember(item: it, derived: false))
                if groups[best].material == nil { groups[best].material = it.material }
            } else {
                groups.append(Group(key: it.id, type: it.type, material: it.material, w: w, h: h, members: [KozijnMember(item: it, derived: false)], single: false, edited: false))
            }
        }

        var unassigned: [KozijnItem] = []
        for it in items where !it.wellVisible {
            guard !separate.contains(it.id), let w = it.widthM, w > 0 else { unassigned.append(it); continue }
            let fits = groups.indices.filter { i in
                let g = groups[i]
                return g.type == it.type && sameMaterial(g.material, it.material) && rel(w, g.w) <= hiddenTolerance
            }
            if fits.count == 1 { groups[fits[0]].members.append(KozijnMember(item: it, derived: true)) }
            else { unassigned.append(it) }   // geen of meer dan één passend type: niet gokken
        }

        // Samenvoegen door de gebruiker (ketens volgen, onbekende sleutels negeren).
        func target(_ k: String) -> String {
            var k = k, seen: Set<String> = []
            while let n = overrides.merge[k], !seen.contains(n) { seen.insert(k); k = n }
            return k
        }
        for i in groups.indices {
            let t = target(groups[i].key)
            guard t != groups[i].key, let j = groups.firstIndex(where: { $0.key == t }), j != i else { continue }
            groups[j].members += groups[i].members
            groups[j].edited = true
            groups[i].members = []
        }
        groups.removeAll { $0.members.isEmpty }

        groups.sort {
            if $0.members.count != $1.members.count { return $0.members.count > $1.members.count }
            if order($0.type) != order($1.type) { return order($0.type) < order($1.type) }
            if $0.w * $0.h != $1.w * $1.h { return $0.w * $0.h > $1.w * $1.h }
            return $0.key < $1.key
        }
        let letters = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        let types = groups.enumerated().map { i, g in
            KozijnType(id: g.key, letter: i < letters.count ? String(letters[i]) : "T\(i + 1)", type: g.type, material: g.material,
                       widthM: g.w, heightM: g.h, members: g.members, editedByUser: g.edited)
        }
        return KozijnStaatResult(types: types, unassigned: unassigned.sorted { $0.id < $1.id })
    }
}
