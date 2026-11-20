import Foundation

/// Maat van één herkend element op een gevel, in meters, met de bandbreedte volgens vaste regels (MeasureBand).
public struct ElementMeasure: Equatable, Identifiable {
    public var elementId: Int
    public var type: FacadeElementType
    public var material: String?
    public var hiddenFraction: Double?
    /// Kader: breedte en hoogte; lijn: lengte; kader en vlak: oppervlak (muren netto, openingen afgetrokken). Nil = onbekend.
    public var widthM: Double?
    public var heightM: Double?
    public var lengthM: Double?
    public var areaM2: Double?
    /// ± op de hoofdmaat (lengte bij een lijn, oppervlak bij een kader of vlak). Nil als de maat onbekend is.
    public var band: Double?
    /// Gevel waar het element bij hoort (voor de lijst van het hele gebouw).
    public var sideId: Int?
    public var id: String { "\(sideId ?? 0):\(elementId)" }

    /// De hoofdmaat: lengte voor lijnen, anders oppervlak.
    public var value: Double? { type.kind == .line ? lengthM : areaM2 }
}

/// Alle elementen van één soort met hun totaal.
public struct ElementGroup: Equatable, Identifiable {
    public var type: FacadeElementType
    public var items: [ElementMeasure]
    public var count: Int { items.count }
    /// Totale lengte (lijnen) of oppervlak (kaders, vlakken); nil als één van de maten onbekend is.
    public var total: Double?
    /// ± op het totaal: lineair opgeteld, omdat de schaalfout bij alle elementen van een gevel dezelfde is (voorzichtig).
    public var band: Double?
    /// De materialen die Claude bij deze soort herkende (zonder dubbelen).
    public var materials: [String]
    public var id: String { type.rawValue }
}

public enum ElementList {
    /// Maten per element uit de elementen in meters (rechtgetrokken, zelfde id's). `relative` is de relatieve bandbreedte van de gevel;
    /// een (deels) verborgen element krijgt er een eigen deel bij, zoals in `MeasureBand.relative`.
    public static func measures(metric: [FacadePhotoElement], relative: Double, sideId: Int? = nil) -> [ElementMeasure] {
        metric.map { e in
            let q = FacadePhoto.quantities(e, mpp: 1, all: metric)
            let hidden = (e.hiddenFraction ?? 0) * 0.5
            let r = sqrt(relative * relative + hidden * hidden)
            var m = ElementMeasure(elementId: e.id, type: e.type, material: e.material, hiddenFraction: e.hiddenFraction,
                                   widthM: nil, heightM: nil, lengthM: nil, areaM2: nil, band: nil, sideId: sideId)
            switch e.type.kind {
            case .line: m.lengthM = FacadePhoto.round2(q.lengthM)
            case .quad: m.widthM = FacadePhoto.round2(q.widthM); m.heightM = FacadePhoto.round2(q.heightM); m.areaM2 = FacadePhoto.round2(q.areaM2)
            case .poly: m.areaM2 = FacadePhoto.round2(q.netM2)
            }
            m.band = m.value.map { FacadePhoto.round2(MeasureBand.band($0, relative: r, area: e.type.kind != .line)) ?? 0 }
            return m
        }
    }

    /// Elementen zonder maat (bijv. op een vlak dat nog geen breedte heeft): ze staan wel in de lijst, met onbekende maten.
    public static func unmeasured(_ els: [FacadePhotoElement], sideId: Int? = nil) -> [ElementMeasure] {
        els.map { ElementMeasure(elementId: $0.id, type: $0.type, material: $0.material, hiddenFraction: $0.hiddenFraction,
                                 widthM: nil, heightM: nil, lengthM: nil, areaM2: nil, band: nil, sideId: sideId) }
    }

    /// Per soort, in de vaste volgorde van de soorten. Is één maat onbekend, dan is het totaal ook onbekend.
    public static func groups(_ items: [ElementMeasure]) -> [ElementGroup] {
        FacadeElementType.allCases.compactMap { t in
            let sel = items.filter { $0.type == t }
            guard !sel.isEmpty else { return nil }
            var total: Double? = 0, band: Double? = 0
            for m in sel {
                if let v = m.value, let b = m.band { total = total.map { $0 + v }; band = band.map { $0 + b } }
                else { total = nil; band = nil }
            }
            var mats: [String] = []
            for m in sel { if let s = m.material?.lowercased(), !mats.contains(s) { mats.append(s) } }
            return ElementGroup(type: t, items: sel, total: FacadePhoto.round2(total), band: FacadePhoto.round2(band), materials: mats)
        }
    }

    /// Voegt de lijsten van meerdere gevels samen tot één lijst voor het hele gebouw.
    public static func merge(_ perSide: [[ElementGroup]]) -> [ElementGroup] {
        groups(perSide.flatMap { $0.flatMap(\.items) })
    }
}
