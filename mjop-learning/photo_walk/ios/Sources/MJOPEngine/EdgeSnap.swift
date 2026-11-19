import Foundation

/// Vastklikken op echte randen: de telefoon zoekt zelf rechthoeken in de foto (Apple Vision, op het toestel) en zet de hoeken van een
/// herkend kozijn of gevelvlak op de dichtstbijzijnde gevonden rechthoek, maar alleen als die duidelijk hetzelfde ding is.
/// De punten van Claude blijven bewaard (`aiPoints` / `aiCorners`); er wordt niets toegevoegd of weggelaten.
public enum EdgeSnap {
    /// Hoeveel een hoek mag verschuiven, als deel van de kortste zijde van het element (en minstens `minShiftPx`).
    public static let maxShift = 0.2
    public static let minShiftPx = 6.0
    /// Minimale overlap tussen element en kandidaat.
    public static let minOverlap = 0.7

    /// De best passende kandidaat voor een vierhoek (pixels, linksboven, rechtsboven, rechtsonder, linksonder), of nil.
    public static func match(_ q: [[Double]], candidates: [[[Double]]], maxShift f: Double = maxShift) -> [[Double]]? {
        guard q.count == 4 else { return nil }
        let sides = (0..<4).map { FacadePhoto.dist(q[$0], q[($0 + 1) % 4]) }
        guard let short = sides.min(), short > 0 else { return nil }
        let tol = max(minShiftPx, f * short)
        var best: (q: [[Double]], d: Double)?
        for c0 in candidates where c0.count == 4 {
            let c = FacadePhoto.orderQuad(c0)
            guard FacadePerspective.isConvex(c) else { continue }
            let d = (0..<4).map { FacadePhoto.dist(q[$0], c[$0]) }.max() ?? .infinity
            guard d <= tol, d < (best?.d ?? .infinity), FacadePhoto.overlap(q, c) >= minOverlap else { continue }
            let ac = FacadePhoto.area(c), aq = FacadePhoto.area(q)
            guard ac > 0, max(ac, aq) / min(ac, aq) < 1.6 else { continue }
            best = (c, d)
        }
        return best?.q
    }

    /// Klikt de openingen (kozijnen, deuren, garagedeuren) vast. Elementen die de gebruiker al heeft aangepast blijven zoals ze zijn.
    /// Geeft terug hoeveel elementen zijn vastgeklikt.
    @discardableResult
    public static func apply(_ els: inout [FacadePhotoElement], candidates: [[[Double]]]) -> Int {
        var n = 0
        for i in els.indices where els[i].type.isOpening && els[i].editedByUser != true && els[i].addedByUser != true && els[i].snappedByVision != true {
            guard let q = match(els[i].points, candidates: candidates) else { continue }
            els[i].aiPoints = els[i].points
            els[i].points = q
            els[i].snappedByVision = true
            n += 1
        }
        return n
    }

    /// Klikt de hoeken van gevelvlakken vast als er een grote rechthoek is gevonden die er duidelijk bij hoort (krappe marge: 6% van de kortste zijde).
    @discardableResult
    public static func applyPlanes(_ planes: inout [FacadePlane], candidates: [[[Double]]]) -> Int {
        var n = 0
        for i in planes.indices where planes[i].editedByUser != true && planes[i].snappedByVision != true {
            guard let q = match(planes[i].corners, candidates: candidates, maxShift: 0.06) else { continue }
            planes[i].aiCorners = planes[i].corners
            planes[i].corners = q
            planes[i].snappedByVision = true
            n += 1
        }
        return n
    }
}
