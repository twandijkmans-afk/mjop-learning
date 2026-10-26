import Foundation

/// Rol van een contour op een gevelfoto (zie docs/facade_composition_v1.md). Python-referentie: photo_walk_core/facade.py.
/// FACADE_GROSS = bruto gevelvlak, OPENING = raam-/deuropening (hier gelijkgesteld aan de buitenmaat van het kozijn),
/// FRAME_OUTER = buitencontour van het kozijn, GLASS_PANE = één glasvlak binnen een kozijn (telt NOOIT als kozijn).
public enum FacadeRole: String, Codable, CaseIterable { case FACADE_GROSS, OPENING, FRAME_OUTER, GLASS_PANE }

/// Hoe zeker de buitencontour van een kozijn is.
/// LEGACY: waarneming van vóór deze indeling (gedrag ongewijzigd). MANUAL: door de gebruiker getekend. USER_CONFIRMED: door de gebruiker bevestigd.
/// DETECTED_ENCLOSING_PANES: automatisch, een gedetecteerde vierhoek die glasvlakken omsluit (sterkste automatische aanwijzing, maar onbevestigd).
/// UNVERIFIED: losse rechthoek (glas of kozijn?) of twijfelachtige omsluiting. PROPOSED_EXPANSION: voorgestelde vergroting vanaf het glas.
/// ALLE automatisch herkende buitencontouren (DETECTED_ENCLOSING_PANES, UNVERIFIED, PROPOSED_EXPANSION) blijven voorlopig: ze leveren alleen een
/// INDICATIEVE maat (zichtbaar, nooit in export, voorstel of gevelopbouw) tot de gebruiker de buitencontour bevestigt of zelf aangeeft.
/// LEGACY (oudere scans), MANUAL en USER_CONFIRMED blokkeren niet; een maat vraagt daarnaast altijd een betrouwbare schaal.
public enum OuterContourStatus: String, Codable, CaseIterable {
    case LEGACY, MANUAL, USER_CONFIRMED, DETECTED_ENCLOSING_PANES, UNVERIFIED, PROPOSED_EXPANSION
    /// De gebruiker moet de buitencontour nog bevestigen.
    public var requiresConfirmation: Bool { self == .UNVERIFIED || self == .PROPOSED_EXPANSION || self == .DETECTED_ENCLOSING_PANES }
    /// Geen bruikbare kozijnmaat (export, voorstel, gevelopbouw) zolang de contour niet bevestigd is.
    public var blocksArea: Bool { requiresConfirmation }
}

/// Poort tussen meting en hoeveelheid: een meting op een onbevestigde automatische buitencontour wordt INDICATIEF (alleen zichtbaar in de app)
/// en krijgt de blokkerende code OUTER_CONTOUR_UNVERIFIED, zodat er geen kozijnmaat, exportwaarde of oppervlakvoorstel uit volgt.
/// Zonder betrouwbare schaal is er sowieso geen maat (ook geen indicatieve).
public enum ContourGate {
    public static func apply(_ r: LevelResult, status: OuterContourStatus) -> LevelResult {
        guard status.blocksArea else { return r }
        var g = r
        if r.ok, let w = r.width, let h = r.height {
            g.diag["indicative_width_m"] = w
            g.diag["indicative_height_m"] = h
            g.diag["indicative_note"] = "Indicatief: automatisch herkende buitencontour (\(status.rawValue)), nog niet bevestigd. Geen hoeveelheid."
        }
        g.flags.append(Flags.make("OUTER_CONTOUR_UNVERIFIED", status.rawValue))
        return g
    }

    /// Indicatieve maat (breedte, hoogte) van een geblokkeerde meting, of nil.
    public static func indicativeDims(_ r: LevelResult) -> (width: Double, height: Double)? {
        guard let w = r.diag["indicative_width_m"] as? Double, let h = r.diag["indicative_height_m"] as? Double else { return nil }
        return (w, h)
    }
}

/// Waarop de indeling van een automatisch gevonden opening berust.
public enum OpeningEvidence: String, Codable { case NESTED_PANES, PANE_GROUP, SINGLE, MANUAL, LEGACY }

// MARK: polygonen in pixels

public func polygonBounds(_ p: [Pixel]) -> (minU: Double, minV: Double, maxU: Double, maxV: Double) {
    (p.map { $0.u }.min() ?? 0, p.map { $0.v }.min() ?? 0, p.map { $0.u }.max() ?? 0, p.map { $0.v }.max() ?? 0)
}

public func polygonCentroid(_ p: [Pixel]) -> Pixel {
    Pixel(p.map { $0.u }.reduce(0, +) / Double(max(p.count, 1)), p.map { $0.v }.reduce(0, +) / Double(max(p.count, 1)))
}

public func polygonArea(_ p: [Pixel]) -> Double { abs(signedArea(p)) }

private func counterClockwise(_ p: [Pixel]) -> [Pixel] { signedArea(p) >= 0 ? p : Array(p.reversed()) }

/// Oppervlak van de doorsnede van twee convexe polygonen (Sutherland-Hodgman). Zelfde stappen als facade.convex_intersection_area.
public func convexIntersectionArea(_ a: [Pixel], _ b: [Pixel]) -> Double {
    var output = counterClockwise(a)
    let clip = counterClockwise(b)
    for i in 0..<clip.count {
        if output.isEmpty { return 0 }
        let c1 = clip[i], c2 = clip[(i + 1) % clip.count]
        let input = output
        output = []
        func inside(_ p: Pixel) -> Bool { (c2.u - c1.u) * (p.v - c1.v) - (c2.v - c1.v) * (p.u - c1.u) >= 0 }
        func crossPoint(_ p: Pixel, _ q: Pixel) -> Pixel {
            let dx1 = q.u - p.u, dy1 = q.v - p.v, dx2 = c2.u - c1.u, dy2 = c2.v - c1.v
            let den = dx1 * dy2 - dy1 * dx2
            if abs(den) < 1e-12 { return q }
            let t = ((c1.u - p.u) * dy2 - (c1.v - p.v) * dx2) / den
            return Pixel(p.u + t * dx1, p.v + t * dy1)
        }
        for k in 0..<input.count {
            let cur = input[k], prev = input[(k + input.count - 1) % input.count]
            if inside(cur) {
                if !inside(prev) { output.append(crossPoint(prev, cur)) }
                output.append(cur)
            } else if inside(prev) {
                output.append(crossPoint(prev, cur))
            }
        }
    }
    return output.count >= 3 ? polygonArea(output) : 0
}

public func polygonIoU(_ a: [Pixel], _ b: [Pixel]) -> Double {
    let inter = convexIntersectionArea(a, b)
    let uni = polygonArea(a) + polygonArea(b) - inter
    return uni > 0 ? inter / uni : 0
}
