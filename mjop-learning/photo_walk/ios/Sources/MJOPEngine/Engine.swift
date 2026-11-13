import Foundation

// MJOPEngine: het rekenmodel van MJOP Live, overgezet uit de website (MJOP-App src/app.js + src/quantity.js).
// Deterministisch, alleen Foundation, geld als Decimal. De pariteitstests (Tests/MJOPEngineTests) controleren dat de uitkomsten
// exact gelijk zijn aan die van de website voor dezelfde invoer. Onbekend blijft nil: nooit stil 0 of een gok.

/// Gebouwgegevens zoals de app ze uit de BAG en de 3D BAG haalt. nil = onbekend.
public struct BuildingInput: Equatable, Codable {
    public var bouwjaar: Int?
    /// Aantal appartementen in het plan (door de gebruiker aanpasbaar).
    public var units: Int
    /// Aantal verblijfsobjecten volgens de BAG (om te weten of `units` uit de BAG komt).
    public var unitsBAG: Int?
    /// Grondvlak van het BAG-pand (m²).
    public var footprintM2: Double?
    /// Omtrek van het BAG-pand (m).
    public var omtrekM: Double?
    /// 3D BAG: plat dakoppervlak, hellend dakoppervlak en bruto buitenmuuroppervlak (m²). Een aanwezige 0 is een meting.
    public var dakPlatM2: Double?
    public var dakSchuinM2: Double?
    public var buitenmuurM2: Double?
    /// Bouwhoogte uit de 3D BAG (m), voor de werkhoogte van de steiger.
    public var hoogteM: Double?

    public init(bouwjaar: Int?, units: Int, unitsBAG: Int?, footprintM2: Double?, omtrekM: Double?, dakPlatM2: Double?, dakSchuinM2: Double?, buitenmuurM2: Double?, hoogteM: Double?) {
        self.bouwjaar = bouwjaar; self.units = units; self.unitsBAG = unitsBAG; self.footprintM2 = footprintM2; self.omtrekM = omtrekM
        self.dakPlatM2 = dakPlatM2; self.dakSchuinM2 = dakSchuinM2; self.buitenmuurM2 = buitenmuurM2; self.hoogteM = hoogteM
    }

    var has3DBAG: Bool { dakPlatM2 != nil || dakSchuinM2 != nil || buitenmuurM2 != nil }
    /// Werkhoogte (m) uit de bouwhoogte: afgerond op hele meters (zoals Q.workHeightFromBuildingHeight).
    public var werkhoogte: Int? {
        guard let h = hoogteM, h.isFinite else { return nil }
        return Int(Engine.roundHalfUp((h * 10).rounded(.toNearestOrAwayFromZero) / 10))
    }
}

/// Waar een hoeveelheid vandaan komt (zelfde codes als de website).
public enum QuantitySource: String, Codable, Equatable {
    case bag = "BAG"
    case threeDBAG = "3D_BAG"
    case geometryDerived = "GEOMETRY_DERIVED"
    case estimated = "ESTIMATED"
    case manual = "MANUAL"
    /// Gemeten op een gevelfoto (herkenning door Claude, maat uit de BAG-gevelbreedte) en door de gebruiker overgenomen.
    case gevelfoto = "GEVELFOTO"
    /// Uit een document (oud MJOP, offerte, inspectie), door de gebruiker overgenomen.
    case document = "DOCUMENT"
    case notAvailable = "NOT_AVAILABLE"
}

/// Een hoeveelheid met bron en uitleg. `value == nil` betekent onbekend.
public struct Quantity: Equatable, Codable {
    public var value: Decimal?
    public var unit: String
    public var source: QuantitySource
    public var basis: String

    public init(value: Decimal?, unit: String, source: QuantitySource, basis: String) {
        self.value = value; self.unit = unit; self.source = source; self.basis = basis
    }
}

public enum ElementType: String, Codable { case dak, gevel, kozijnen, steiger, perUnit = "per-unit", vastVariabel = "vast-variabel" }

/// Waar de automatische hoeveelheid van een post op gebaseerd is.
public enum QuantityBasis: String, Codable { case dakM2, dakPlatM2, dakSchuinM2, gevelM2, units, none }

/// Een post uit de standaardbibliotheek (prijzen: standaardbedragen, geen offerte).
public struct ElementDefinition: Equatable {
    public let key: String
    public let naam: String
    public let categorie: String
    public let sfb: String
    public let type: ElementType
    public let cyclus: Int
    public var kengetal: Decimal? = nil
    public var basis: Decimal? = nil
    public var perEenheid: Decimal? = nil
    public var bron: QuantityBasis = .none
    public var benadering = false
    public var optioneel = false
}

public enum KozijnMateriaal: String, Codable, CaseIterable {
    case hout, aluminium, kunststof, staal
    public var label: String { switch self { case .hout: return "Hout"; case .aluminium: return "Aluminium"; case .kunststof: return "Kunststof (pvc)"; case .staal: return "Staal" } }
    public var cyclus: Int { switch self { case .hout: return 6; case .aluminium: return 15; case .kunststof: return 20; case .staal: return 8 } }
    public var factor: Decimal { switch self { case .hout: return 1; case .aluminium: return Decimal(string: "0.35")!; case .kunststof: return Decimal(string: "0.2")!; case .staal: return Decimal(string: "1.1")! } }
}

public struct KozijnRij: Equatable, Codable {
    public var naam: String
    public var tarief: Decimal
    public var aantal: Quantity
    public var materiaal: KozijnMateriaal = .hout
    public var eigenTarief: Decimal? = nil
}

/// Een post in een plan.
public struct PlanElement: Equatable, Codable {
    public var key: String
    public var naam: String
    public var categorie: String
    public var type: ElementType
    public var cyclus: Int
    public var laatsteBeurt: Int
    public var kengetal: Decimal?
    public var basis: Decimal?
    public var perEenheid: Decimal?
    public var quantity: Quantity?
    public var kozijnen: [KozijnRij]?
    public var werkhoogte: Int?
    /// Staat volgens NEN 2767 (1 uitstekend … 6 zeer slecht); nil = niet beoordeeld.
    public var conditie: Int?
    /// Prijs van één beurt uit een offerte (actuele prijs); vervangt de standaardraming. nil = standaardbedrag.
    public var prijsOfferte: Decimal? = nil
    public var prijsBron: String? = nil
}

/// Eén geplande uitgave.
public struct PlannedCost: Equatable {
    public var key: String
    public var naam: String
    public var jaar: Int
    public var bedrag: Decimal
}

public struct FundYear: Equatable {
    public var jaar: Int
    public var kosten: Decimal
    public var saldo: Decimal
}

public enum Engine {
    public static let horizon = 10

    public static let kozijnDefaults: [(String, Decimal)] = [("Draaiend raam", 174), ("Vast glas", 96), ("Deur", 240), ("Dakkapel", 320)]
    static let kozFactoren: [Double] = [1, 0.25, 0.125, 0.125]
    static let kozMinima: [Int] = [1, 0, 1, 0]

    public static let library: [ElementDefinition] = [
        ElementDefinition(key: "dak-plat", naam: "Dakbedekking plat dak", categorie: "Dak", sfb: "27.1", type: .dak, cyclus: 25, kengetal: 165, bron: .dakPlatM2, optioneel: true),
        ElementDefinition(key: "dakgoten", naam: "Dakgoten en hemelwaterafvoeren", categorie: "Dak", sfb: "27.3", type: .vastVariabel, cyclus: 20, basis: 300, perEenheid: 90, bron: .units),
        ElementDefinition(key: "dakinspectie", naam: "Dakinspectie en klein onderhoud", categorie: "Dak", sfb: "27", type: .vastVariabel, cyclus: 2, basis: 420, perEenheid: 2, bron: .dakM2),
        ElementDefinition(key: "dak-hellend", naam: "Dakbedekking hellend dak (pannen)", categorie: "Dak", sfb: "27.2", type: .dak, cyclus: 40, kengetal: 95, bron: .dakSchuinM2, optioneel: true),
        ElementDefinition(key: "dakisolatie", naam: "Dakisolatie na-isoleren", categorie: "Dak", sfb: "47.2", type: .dak, cyclus: 30, kengetal: 60, bron: .dakM2, optioneel: true),
        ElementDefinition(key: "gevel-metselwerk", naam: "Gevelreiniging en metselwerkherstel", categorie: "Gevel", sfb: "21.1", type: .gevel, cyclus: 15, kengetal: 26, bron: .gevelM2, benadering: true),
        ElementDefinition(key: "schilderwerk-buiten", naam: "Schilderwerk buitenkozijnen en gevelhoutwerk", categorie: "Gevel", sfb: "31.2", type: .gevel, cyclus: 6, kengetal: 22, bron: .gevelM2, benadering: true),
        ElementDefinition(key: "kozijnen-onderhoud", naam: "Onderhoud buitenkozijnen", categorie: "Gevel", sfb: "31.1", type: .kozijnen, cyclus: 6),
        ElementDefinition(key: "steiger", naam: "Steiger of hoogwerker", categorie: "Gevel", sfb: "21", type: .steiger, cyclus: 6, bron: .gevelM2),
        ElementDefinition(key: "voegwerk", naam: "Voegwerk buitengevel", categorie: "Gevel", sfb: "21.1", type: .gevel, cyclus: 30, kengetal: 45, bron: .gevelM2, benadering: true, optioneel: true),
        ElementDefinition(key: "balkonhekken", naam: "Balkonhekken en borstweringen", categorie: "Gevel", sfb: "34.1", type: .perUnit, cyclus: 20, kengetal: 210, bron: .units, optioneel: true),
        ElementDefinition(key: "intercom", naam: "Intercom en video-deuropener", categorie: "Installaties", sfb: "66", type: .perUnit, cyclus: 20, kengetal: 575, bron: .units),
        ElementDefinition(key: "riolering", naam: "Riolering en hemelwaterafvoer (inpandig)", categorie: "Installaties", sfb: "52", type: .vastVariabel, cyclus: 10, basis: 1100, perEenheid: 120, bron: .units),
        ElementDefinition(key: "elektra", naam: "Elektrische installatie gemeenschappelijk", categorie: "Installaties", sfb: "62/63", type: .vastVariabel, cyclus: 25, basis: 800, perEenheid: 90, bron: .units, optioneel: true),
        ElementDefinition(key: "verlichting", naam: "Verlichting gemeenschappelijke ruimten", categorie: "Installaties", sfb: "64", type: .perUnit, cyclus: 15, kengetal: 65, bron: .units, optioneel: true),
        ElementDefinition(key: "waterleiding", naam: "Waterleiding gemeenschappelijk", categorie: "Installaties", sfb: "52", type: .vastVariabel, cyclus: 30, basis: 600, perEenheid: 55, bron: .units, optioneel: true),
        ElementDefinition(key: "brandveiligheid", naam: "Brandveiligheid (blusmiddelen, vluchtwegverlichting)", categorie: "Installaties", sfb: "67", type: .perUnit, cyclus: 10, kengetal: 45, bron: .units, optioneel: true),
        ElementDefinition(key: "cv-installatie", naam: "Collectieve cv-installatie (ketel)", categorie: "Installaties", sfb: "51", type: .vastVariabel, cyclus: 18, basis: 3500, perEenheid: 350, bron: .units, optioneel: true),
        ElementDefinition(key: "ventilatie", naam: "Mechanische ventilatie", categorie: "Installaties", sfb: "57", type: .perUnit, cyclus: 15, kengetal: 220, bron: .units, optioneel: true),
        ElementDefinition(key: "lift", naam: "Liftinstallatie — onderhoud en modernisering", categorie: "Installaties", sfb: "59", type: .vastVariabel, cyclus: 20, basis: 12000, perEenheid: 0, bron: .none, optioneel: true),
        ElementDefinition(key: "trappenhuis", naam: "Trappenhuis en entree", categorie: "Binnen", sfb: "42/43", type: .perUnit, cyclus: 8, kengetal: 480, bron: .units),
        ElementDefinition(key: "vloerafwerking", naam: "Vloerafwerking gemeenschappelijke ruimten", categorie: "Binnen", sfb: "43", type: .perUnit, cyclus: 15, kengetal: 120, bron: .units, optioneel: true),
        ElementDefinition(key: "bestrating", naam: "Bestrating en terreininrichting", categorie: "Terrein", sfb: "81/89", type: .vastVariabel, cyclus: 20, basis: 500, perEenheid: 60, bron: .units, optioneel: true),
        ElementDefinition(key: "fietsenstalling", naam: "Fietsenstalling en bergingen", categorie: "Terrein", sfb: "89", type: .perUnit, cyclus: 25, kengetal: 150, bron: .units, optioneel: true),
    ]

    // MARK: afronden (zoals JavaScript Math.round voor positieve getallen)

    static func roundHalfUp(_ x: Double) -> Double { (x + 0.5).rounded(.down) }

    static func round2(_ x: Double) -> Decimal {
        let r = roundHalfUp(x * 100) / 100
        return Decimal(string: String(format: "%.2f", r)) ?? Decimal(r)
    }

    public static func roundEuro(_ d: Decimal) -> Decimal {
        var v = d, out = Decimal()
        NSDecimalRound(&out, &v, 0, .plain)
        return out
    }

    // MARK: hoeveelheden (Q.autoFor, niet-voorbeeldgebouw)

    public static func autoQuantity(_ bron: QuantityBasis, _ b: BuildingInput, benadering: Bool = false) -> Quantity? {
        let has3D = b.has3DBAG
        switch bron {
        case .none: return nil
        case .dakPlatM2:
            if let p = b.dakPlatM2 { return Quantity(value: round2(p), unit: "m2", source: .threeDBAG, basis: "Plat dakoppervlak uit het 3D BAG-model.") }
            return footprintEstimate(b, has3D ? "Plat dakoppervlak ontbreekt in het 3D BAG-model" : "Geen 3D BAG-gegevens")
        case .dakSchuinM2:
            if let s = b.dakSchuinM2 { return Quantity(value: round2(s), unit: "m2", source: .threeDBAG, basis: "Hellend dakoppervlak uit het 3D BAG-model.") }
            return Quantity(value: nil, unit: "m2", source: .notAvailable, basis: (has3D ? "Het 3D BAG-model bevat geen hellend dakoppervlak" : "Geen 3D BAG-gegevens") + ": vul de hoeveelheid zelf in.")
        case .dakM2:
            if let p = b.dakPlatM2, let s = b.dakSchuinM2 {
                return Quantity(value: round2(p + s), unit: "m2", source: .geometryDerived, basis: "Som van plat en hellend dakoppervlak uit de 3D BAG.")
            }
            if b.dakPlatM2 != nil || b.dakSchuinM2 != nil {
                return Quantity(value: nil, unit: "m2", source: .notAvailable, basis: "Totaal dakoppervlak niet volledig beschikbaar in de 3D BAG: vul de hoeveelheid zelf in.")
            }
            return footprintEstimate(b, has3D ? "Plat en hellend dakoppervlak ontbreken in het 3D BAG-model" : "Geen 3D BAG-gegevens")
        case .gevelM2:
            if let g = b.buitenmuurM2 {
                return benadering
                    ? Quantity(value: round2(g), unit: "m2", source: .estimated, basis: "Benadering: het hele buitenmuuroppervlak uit de 3D BAG (bruto, incl. ramen).")
                    : Quantity(value: round2(g), unit: "m2", source: .threeDBAG, basis: "Buitenmuuroppervlak uit het 3D BAG-model (bruto).")
            }
            guard let o = b.omtrekM else { return Quantity(value: nil, unit: "m2", source: .notAvailable, basis: "Geen omtrek en geen 3D BAG-gegevens: vul de hoeveelheid zelf in.") }
            return Quantity(value: round2(o * 3 * 3), unit: "m2", source: .estimated,
                            basis: (has3D ? "Buitenmuuroppervlak ontbreekt in het 3D BAG-model" : "Geen 3D BAG-gegevens") + ": omtrek × aangenomen hoogte van 9 m.")
        case .units:
            let bag = b.unitsBAG != nil && b.units == b.unitsBAG
            return Quantity(value: Decimal(b.units), unit: "app", source: bag ? .bag : .manual,
                            basis: bag ? "Aantal verblijfsobjecten in de BAG." : "Aantal appartementen zoals ingevuld.")
        }
    }

    static func footprintEstimate(_ b: BuildingInput, _ reason: String) -> Quantity {
        guard let f = b.footprintM2 else { return Quantity(value: nil, unit: "m2", source: .notAvailable, basis: reason + ": geen grondvlak bekend.") }
        return Quantity(value: round2(f), unit: "m2", source: .estimated, basis: reason + ": het grondvlak van het BAG-pand is als schatting gebruikt.")
    }

    public static func autoKozijn(_ i: Int, _ b: BuildingInput) -> Quantity {
        let v = max(kozMinima[i], Int(roundHalfUp(Double(b.units) * kozFactoren[i])))
        return Quantity(value: Decimal(v), unit: "st", source: .estimated, basis: "Schatting: appartementen × vaste factor, niet geteld.")
    }

    // MARK: standaardplan

    /// De standaardposten voor een gebouw (zoals buildDefaultElements): plat en hellend dak alleen als ze bij dit gebouw horen.
    public static func defaultElements(for b: BuildingInput, year: Int) -> [PlanElement] {
        let schuin = b.dakSchuinM2
        let plat = b.dakPlatM2
        return library.filter { d in
            if d.key == "dak-hellend" { return (schuin ?? 0) > 0 }
            if d.key == "dak-plat" { return !((schuin ?? 0) > 0 && plat == 0) }
            return !d.optioneel
        }.map { instantiate($0, b, year: year) }
    }

    public static func instantiate(_ d: ElementDefinition, _ b: BuildingInput, year: Int) -> PlanElement {
        var el = PlanElement(key: d.key, naam: d.naam, categorie: d.categorie, type: d.type, cyclus: d.cyclus, laatsteBeurt: b.bouwjaar ?? (year - d.cyclus),
                             kengetal: d.kengetal, basis: d.basis, perEenheid: d.perEenheid,
                             quantity: d.bron == .none ? nil : autoQuantity(d.bron, b, benadering: d.benadering), kozijnen: nil, werkhoogte: nil, conditie: nil)
        if d.type == .kozijnen {
            el.kozijnen = kozijnDefaults.enumerated().map { i, def in KozijnRij(naam: def.0, tarief: def.1, aantal: autoKozijn(i, b)) }
        } else if d.type == .steiger {
            el.werkhoogte = b.werkhoogte
        }
        return el
    }

    // MARK: kosten

    static func kozTarief(_ k: KozijnRij) -> Decimal { k.eigenTarief ?? roundEuro(k.tarief * k.materiaal.factor) }

    /// Kosten van één beurt; nil = niet te berekenen (hoeveelheid of werkhoogte onbekend). Nooit stil € 0.
    public static func cost(_ el: PlanElement) -> Decimal? {
        if let p = el.prijsOfferte { return p }
        let q = el.quantity?.value
        switch el.type {
        case .dak, .gevel, .perUnit:
            guard let q, let k = el.kengetal else { return nil }
            return q * k
        case .vastVariabel:
            guard let basis = el.basis else { return nil }
            if el.quantity == nil { return basis }
            guard let q else { return nil }
            return basis + q * (el.perEenheid ?? 0)
        case .steiger:
            guard let q, let wh = el.werkhoogte else { return nil }
            let rate: Decimal = wh > 8 ? 11 : 6
            return roundEuro(q * rate)
        case .kozijnen:
            return (el.kozijnen ?? []).reduce(Decimal(0)) { $0 + ($1.aantal.value ?? 0) * kozTarief($1) }
        }
    }

    // MARK: planning

    static func nextOccurrence(_ cyclus: Int, _ start: Int, year: Int) -> Int {
        var j = start
        while j < year { j += cyclus }
        return j
    }

    /// Eerste jaar van een post: standaard de cyclus vanaf de laatste beurt; een beoordeling (1–6) schuift het jaar (NEN 2767, vereenvoudigd).
    public static func firstYear(cyclus: Int, laatsteBeurt: Int, conditie: Int?, year: Int) -> Int {
        let baseline = nextOccurrence(cyclus, laatsteBeurt + cyclus, year: year)
        guard let s = conditie else { return baseline }
        let rest = Int(roundHalfUp(Double(cyclus * (6 - s)) / 5))
        return max(year, year + rest)
    }

    public static func schedule(_ el: PlanElement, year: Int) -> [PlannedCost] {
        let end = year + horizon - 1
        var out: [PlannedCost] = []
        if el.type == .kozijnen && el.prijsOfferte == nil {
            // per cyclus (materiaal) een groep, in volgorde van eerste voorkomen
            var order: [Int] = []
            var groups: [Int: [KozijnRij]] = [:]
            for k in el.kozijnen ?? [] {
                let c = k.materiaal.cyclus
                if groups[c] == nil { order.append(c); groups[c] = [] }
                groups[c]!.append(k)
            }
            for c in order.sorted() {
                let rows = groups[c]!
                let bedrag = rows.reduce(Decimal(0)) { $0 + ($1.aantal.value ?? 0) * kozTarief($1) }
                var j = firstYear(cyclus: c, laatsteBeurt: el.laatsteBeurt, conditie: el.conditie, year: year)
                while j <= end { out.append(PlannedCost(key: el.key, naam: el.naam, jaar: j, bedrag: bedrag)); j += c }
            }
            return out
        }
        guard let bedrag = cost(el) else { return out }
        var j = firstYear(cyclus: el.cyclus, laatsteBeurt: el.laatsteBeurt, conditie: el.conditie, year: year)
        while j <= end { out.append(PlannedCost(key: el.key, naam: el.naam, jaar: j, bedrag: bedrag)); j += el.cyclus }
        return out
    }

    /// Alle uitgaven binnen de planningshorizon, op jaar en daarbinnen het duurste eerst (stabiel, zoals de website).
    public static func plan(_ elements: [PlanElement], year: Int) -> [PlannedCost] {
        let all = elements.flatMap { schedule($0, year: year) }
        return all.enumerated().sorted { a, b in
            if a.element.jaar != b.element.jaar { return a.element.jaar < b.element.jaar }
            if a.element.bedrag != b.element.bedrag { return a.element.bedrag > b.element.bedrag }
            return a.offset < b.offset
        }.map(\.element)
    }

    public static func perYear(_ plan: [PlannedCost]) -> [Int: Decimal] {
        plan.reduce(into: [:]) { $0[$1.jaar, default: 0] += $1.bedrag }
    }

    /// Fondsstand aan het eind van elk jaar bij een maandbijdrage per appartement.
    public static func fund(fonds: Decimal, bijdrage: Decimal, units: Int, perYear: [Int: Decimal], year: Int) -> [FundYear] {
        let inkomen = bijdrage * 12 * Decimal(max(1, units))
        var saldo = fonds
        return (year...(year + horizon - 1)).map { j in
            let k = perYear[j] ?? 0
            saldo = saldo + inkomen - k
            return FundYear(jaar: j, kosten: k, saldo: saldo)
        }
    }

    /// Laagste maandbijdrage (stappen van € 5) waarbij het fonds aan het eind van elk jaar niet onder 0 komt; minimaal € 5.
    public static func requiredContribution(fonds: Decimal, units: Int, perYear: [Int: Decimal], year: Int) -> Int {
        var b = 0
        var guardCount = 0
        while guardCount < 10000 {
            let lowest = fund(fonds: fonds, bijdrage: Decimal(b), units: units, perYear: perYear, year: year).map(\.saldo).min() ?? 0
            if lowest >= 0 { break }
            b += 5; guardCount += 1
        }
        return max(5, b)
    }
}
