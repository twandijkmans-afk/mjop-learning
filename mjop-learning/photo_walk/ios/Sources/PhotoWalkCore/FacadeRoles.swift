import Foundation

/// Rol van een contour op een gevelfoto (zie docs/facade_composition_v1.md). Python-referentie: photo_walk_core/facade.py.
/// FACADE_GROSS = bruto gevelvlak, OPENING = raam-/deuropening (hier gelijkgesteld aan de buitenmaat van het kozijn),
/// FRAME_OUTER = buitencontour van het kozijn, GLASS_PANE = één glasvlak binnen een kozijn (telt NOOIT als kozijn).
public enum FacadeRole: String, Codable, CaseIterable { case FACADE_GROSS, OPENING, FRAME_OUTER, GLASS_PANE }

/// Hoe zeker de buitencontour van een kozijn is.
/// LEGACY: waarneming van vóór deze indeling (gedrag ongewijzigd). MANUAL: door de gebruiker getekend. USER_CONFIRMED: door de gebruiker bevestigd.
/// DETECTED_ENCLOSING_PANES: automatisch, een gedetecteerde vierhoek die glasvlakken omsluit (blijft een onbevestigde kandidaat).
/// UNVERIFIED: losse rechthoek (glas of kozijn?) of twijfelachtige omsluiting. PROPOSED_EXPANSION: voorgestelde vergroting vanaf het glas.
/// UNVERIFIED en PROPOSED_EXPANSION leveren GEEN kozijnmaat tot de gebruiker de buitencontour bevestigt of zelf aangeeft.
public enum OuterContourStatus: String, Codable, CaseIterable {
    case LEGACY, MANUAL, USER_CONFIRMED, DETECTED_ENCLOSING_PANES, UNVERIFIED, PROPOSED_EXPANSION
    public var blocksArea: Bool { self == .UNVERIFIED || self == .PROPOSED_EXPANSION }
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
