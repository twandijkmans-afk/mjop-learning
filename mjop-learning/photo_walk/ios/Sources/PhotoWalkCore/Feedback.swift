import Foundation

/// Kleur van een kader in de UI. UITSLUITEND weergave-feedback; GEEN goedkeuring, geen besluit en geen status in het contract.
public enum BoxFeedback: String, Codable {
    case green     // voorlopig bruikbare meting (nog steeds onbevestigd en onbevestigd op echte gebouwen)
    case orange    // controle nodig: meting met waarschuwing of twijfel aan de geometrie/hoeken
    case neutral   // geen betrouwbare schaal/diepte: geen maat (UNKNOWN)
}

public enum Feedback {
    static let reviewAdvisories: Set<String> = ["GLASS_DEPTH_UNRELIABLE", "CORNER_DEPTH_MISMATCH", "FACADE_NOT_VERTICAL", "OBSTRUCTION_REPORTED",
                                                "COPLANARITY_ASSUMED", "REFERENCE_UNCERTAINTY_NOT_PROVIDED"]
    /// Blokkades die betekenen dat er geen betrouwbare schaal/diepte is (niet: dat het kader fout is).
    static let noScale: Set<String> = ["NO_DEPTH", "TRACKING_LOST", "DEPTH_COVERAGE_LOW", "DEPTH_RANGE_EXCEEDED", "NO_METRIC_SCALE", "REFERENCE_INVALID"]

    public static func classify(_ r: LevelResult) -> BoxFeedback {
        if r.ok {
            let adv = Set(r.flags.filter { $0.severity == .ADVISORY }.map { $0.code })
            return adv.isDisjoint(with: reviewAdvisories) ? .green : .orange
        }
        let blocking = Set(r.flags.filter { $0.severity == .BLOCKING }.map { $0.code })
        if blocking.isEmpty { return .neutral }
        return blocking.isDisjoint(with: noScale) ? .orange : .neutral
    }
}

/// Voorlopige koppelsuggestie tussen waarnemingen in verschillende foto's. Een suggestie koppelt NIETS; de inspecteur beslist.
public struct LinkCandidate: Equatable {
    public var a: String, b: String, distanceM: Double
}

public struct LinkItem {
    public var id: String, frameId: String
    public var center: Vec3, planeN: Vec3, planeD: Double
    public var width: Double, height: Double
    public init(id: String, frameId: String, center: Vec3, planeN: Vec3, planeD: Double, width: Double, height: Double) {
        self.id = id; self.frameId = frameId; self.center = center; self.planeN = planeN; self.planeD = planeD; self.width = width; self.height = height
    }
}

public enum Linking {
    /// Zelfde regels als photo_walk_core/association.py: zelfde vlak (normaal <= 15 graden, offset <= 15 cm), middelpunt binnen 0,5 x kleinste afmeting,
    /// vergelijkbare maat (< 1,5x), nooit hetzelfde beeld. Onduidelijk (twee kandidaten van vergelijkbare afstand in hetzelfde andere beeld) => geen suggestie.
    public static func suggest(_ items: [LinkItem], gateFactor: Double = 0.5, normalAngleDeg: Double = 15, planeOffsetM: Double = 0.15) -> [LinkCandidate] {
        var pairs: [(Double, Int, Int)] = []
        for i in 0..<items.count { for j in (i + 1)..<max(items.count, i + 1) where j < items.count {
            let a = items[i], b = items[j]
            if a.frameId == b.frameId { continue }
            let cosA = abs(a.planeN.dot(b.planeN)) / (a.planeN.norm * b.planeN.norm)
            if acos(min(1, cosA)) * 180 / Double.pi > normalAngleDeg { continue }
            let s: Double = a.planeN.dot(b.planeN) >= 0 ? 1 : -1
            if abs(a.planeD - s * b.planeD) > planeOffsetM { continue }
            let rw = max(a.width, b.width) / max(min(a.width, b.width), 1e-9), rh = max(a.height, b.height) / max(min(a.height, b.height), 1e-9)
            if rw >= 1.5 || rh >= 1.5 { continue }
            let d = (a.center - b.center).norm
            if d <= gateFactor * min(a.width, a.height, b.width, b.height) { pairs.append((d, i, j)) }
        } }
        var best: [String: [Double]] = [:]
        for (d, i, j) in pairs {
            best["\(i)|\(items[j].frameId)", default: []].append(d)
            best["\(j)|\(items[i].frameId)", default: []].append(d)
        }
        var ambiguous = Set<Int>()
        for (k, ds) in best where ds.count >= 2 {
            let s = ds.sorted()
            if s[1] < 1.5 * s[0] { ambiguous.insert(Int(k.split(separator: "|")[0])!) }
        }
        return pairs.sorted { $0.0 < $1.0 }.filter { !ambiguous.contains($0.1) && !ambiguous.contains($0.2) }
            .map { LinkCandidate(a: items[$0.1].id, b: items[$0.2].id, distanceM: $0.0) }
    }
}
