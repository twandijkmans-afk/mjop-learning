import Foundation

/// Waarom een herkend element nagelopen moet worden. De app bepaalt dit met vaste regels; de zekerheid die Claude zelf opgeeft
/// is maar één van de signalen. Alles wat níet in de lijst staat kan de gebruiker in één keer bevestigen.
public enum ReviewReason: String, Codable, CaseIterable {
    /// Claude gaf zelf "low" als zekerheid.
    case lowConfidence
    /// Ligt over een element van een andere soort heen (niet automatisch opgelost).
    case conflict
    /// Voor meer dan een kwart verborgen (achter een boom, auto, ...).
    case hidden
    /// De maat valt buiten wat voor deze soort gebruikelijk is (bijv. een raamkozijn van 5 m hoog).
    case implausibleSize
    /// Staat bijna, maar net niet, op één lijn met een gelijk kozijn ernaast: mogelijk een onnauwkeurige rand.
    case offRow

    public var label: String {
        switch self {
        case .lowConfidence: return "Claude twijfelt"
        case .conflict: return "Ligt over een ander element"
        case .hidden: return "Grotendeels verborgen"
        case .implausibleSize: return "Ongebruikelijke maat"
        case .offRow: return "Net niet op één lijn met de buren"
        }
    }
}

public struct ReviewItem: Equatable, Identifiable {
    public var elementId: Int
    public var reasons: [ReviewReason]
    public var id: Int { elementId }
}

/// Telling van wat de gebruiker heeft gecorrigeerd (de handwerkteller), uit de herkomstgegevens die per element al worden bewaard.
public struct ReviewStats: Codable, Equatable {
    public var total: Int
    public var added: Int
    public var removed: Int
    public var retyped: Int
    public var reshaped: Int
    public var confirmed: Int
    /// Alle correcties samen (toegevoegd, verwijderd, soort gewijzigd, verschoven of vervormd).
    public var corrections: Int { added + removed + retyped + reshaped }
}

public enum FacadeReview {
    /// Gebruikelijke maten per soort opening (breedte, hoogte in meter). Dit zijn controlegrenzen, geen gegevens: daarbuiten vraagt de app om te kijken.
    public static let plausible: [FacadeElementType: (w: ClosedRange<Double>, h: ClosedRange<Double>)] = [
        .kozijn_raam: (0.3...4.5, 0.3...3.5),
        .kozijn_deur: (0.6...3.0, 1.7...3.2),
        .garagedeur: (1.8...6.5, 1.8...3.5),
    ]
    /// Boven deze verborgen fractie loopt de gebruiker het element na.
    public static let hiddenLimit = 0.25
    /// Twee gelijke kozijnen waarvan de bovenkant tussen deze afstanden (m) verschilt staan "net niet" op één lijn.
    public static let rowSlack: ClosedRange<Double> = 0.04...0.15

    /// De elementen die de gebruiker moet nalopen, met de reden(en). `metric` zijn dezelfde elementen in meters (rechtgetrokken, zelfde id's);
    /// zonder metric worden alleen de maatloze signalen gebruikt. Elementen die de gebruiker al heeft aangepast, toegevoegd of bevestigd vallen weg.
    public static func items(_ els: [FacadePhotoElement], metric: [FacadePhotoElement]?, conflicts: [[Int]]) -> [ReviewItem] {
        let inConflict = Set(conflicts.flatMap { $0 })
        var size: [Int: (w: Double, h: Double, top: Double)] = [:]
        for m in metric ?? [] where m.type.kind == .quad && m.points.count == 4 {
            let q = FacadePhoto.quantities(m, mpp: 1, all: [])
            if let w = q.widthM, let h = q.heightM { size[m.id] = (w, h, (m.points[0][1] + m.points[1][1]) / 2) }
        }
        var offRow = Set<Int>()
        let openings = els.filter { $0.type.isOpening && size[$0.id] != nil }
        for (n, a) in openings.enumerated() {
            for b in openings[(n + 1)...] where a.type == b.type {
                guard let sa = size[a.id], let sb = size[b.id] else { continue }
                let sameSize = abs(sa.h - sb.h) / max(sa.h, sb.h) < 0.1 && abs(sa.w - sb.w) / max(sa.w, sb.w) < 0.1
                if sameSize && rowSlack.contains(abs(sa.top - sb.top)) { offRow.insert(a.id); offRow.insert(b.id) }
            }
        }
        var out: [ReviewItem] = []
        for e in els {
            if e.confirmedByUser == true || e.editedByUser == true || e.addedByUser == true { continue }
            var r: [ReviewReason] = []
            if e.confidence == "low" { r.append(.lowConfidence) }
            if inConflict.contains(e.id) { r.append(.conflict) }
            if (e.hiddenFraction ?? 0) > hiddenLimit { r.append(.hidden) }
            if let s = size[e.id], let p = plausible[e.type], !p.w.contains(s.w) || !p.h.contains(s.h) { r.append(.implausibleSize) }
            if offRow.contains(e.id) { r.append(.offRow) }
            if !r.isEmpty { out.append(ReviewItem(elementId: e.id, reasons: r)) }
        }
        return out.sorted { ($0.reasons.count, -$0.elementId) > ($1.reasons.count, -$1.elementId) }
    }

    /// Bevestigt alle elementen die niet in de nalooplijst staan (de gebruiker heeft ze gezien en goedgekeurd).
    /// De herkenning zelf verandert niet; alleen het vinkje `confirmedByUser` wordt gezet.
    public static func confirmRest(_ els: inout [FacadePhotoElement], except flagged: Set<Int>) -> Int {
        var n = 0
        for i in els.indices where !flagged.contains(els[i].id) && els[i].confirmedByUser != true && els[i].addedByUser != true {
            els[i].confirmedByUser = true; n += 1
        }
        return n
    }

    public static func stats(_ els: [FacadePhotoElement], removed: [FacadePhotoElement]) -> ReviewStats {
        var s = ReviewStats(total: els.count + removed.count, added: 0, removed: removed.count, retyped: 0, reshaped: 0, confirmed: 0)
        for e in els {
            if e.addedByUser == true { s.added += 1; continue }
            if e.confirmedByUser == true { s.confirmed += 1 }
            guard e.editedByUser == true else { continue }
            if let t = e.originalType, t != e.type { s.retyped += 1 }
            if let p = e.originalPoints, p != e.points { s.reshaped += 1 }
        }
        return s
    }
}
