import Foundation

/// Gemeenschappelijke muren: zijden van de eigen BAG-omtrek die tegen een buurpand liggen (rijtjeswoning, hoekwoning).
/// Pure meetkunde op de BAG-omtrekken; de BAG kan enkele decimeters afwijken, vandaar de marge.
public enum PartyWalls {
    /// Afstand tot de rand van een buurpand waarbinnen een punt als "tegen het buurpand" telt.
    public static let toleranceM = 0.5
    /// Vanaf dit deel geldt een zijde als helemaal gedeeld (marge voor de onnauwkeurigheid van de BAG).
    public static let fullyShared = 0.95

    /// Deel van de zijde (meters, zelfde oorsprong als de buurpanden) dat binnen de marge van de rand van een buurpand ligt.
    public static func sharedFraction(from a: [Double], to b: [Double], neighbours: [[[Double]]], toleranceM tol: Double = toleranceM) -> Double {
        guard a.count == 2, b.count == 2, !neighbours.isEmpty else { return 0 }
        let n = 40
        var hits = 0
        for k in 0..<n {
            let t = (Double(k) + 0.5) / Double(n)
            let p = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
            if neighbours.contains(where: { ring in distance(p, toRing: ring) <= tol }) { hits += 1 }
        }
        return Double(hits) / Double(n)
    }

    /// Vult `sharedFraction` in voor elke zijde met begin- en eindpunt. `ownRing` en `neighbours` in lon/lat; de zijden zijn in meters
    /// rond het eerste punt van de eigen omtrek (zoals `FootprintSides.sides`).
    public static func annotate(_ sides: [FacadeSide], ownRing: [[Double]], neighbours: [[(Double, Double)]]) -> [FacadeSide] {
        guard let o = ownRing.first, o.count == 2 else { return sides }
        let origin = (o[0], o[1])
        let own = FootprintSides.meters(ownRing.map { ($0[0], $0[1]) }, origin: origin)
        func centre(_ r: [[Double]]) -> [Double] { [r.map { $0[0] }.reduce(0, +) / Double(r.count), r.map { $0[1] }.reduce(0, +) / Double(r.count)] }
        let c0 = centre(own)
        // Het eigen pand zelf (zelfde midden) telt niet als buur.
        let ns = neighbours.map { FootprintSides.meters($0, origin: origin) }.filter { r in
            guard r.count >= 3 else { return false }
            let c = centre(r)
            return hypot(c[0] - c0[0], c[1] - c0[1]) > 1
        }
        return sides.map { s in
            var c = s
            if let f = s.from, let t = s.to { c.sharedFraction = (sharedFraction(from: f, to: t, neighbours: ns) * 100).rounded() / 100 }
            return c
        }
    }

    static func distance(_ p: [Double], toRing r: [[Double]]) -> Double {
        guard r.count >= 2 else { return .infinity }
        var best = Double.infinity
        for i in 0..<r.count {
            let a = r[i], b = r[(i + 1) % r.count]
            let dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy
            let t = l2 == 0 ? 0 : max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
            best = min(best, hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)))
        }
        return best
    }
}
