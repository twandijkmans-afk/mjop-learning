import Foundation

/// Een lange gevel in meerdere foto's, van links naar rechts. Elke foto is rechtgetrokken met breedte 1 (eigen eenheid).
/// De kozijnen in de overlap (de laatste n van de vorige foto en de eerste n van de volgende) koppelen de foto's: daaruit volgen de
/// onderlinge schaal en verschuiving. De hele strook krijgt de gevelbreedte uit de BAG. Alles wordt bij de rechterrand van de
/// overlapkozijnen geknipt, zodat elk kozijn en elk stuk muur één keer telt. Zonder overlap is de maat niet te bepalen: geen uitkomst.
public enum FacadeStrip {
    public struct Part: Equatable {
        /// Elementen van het hoofdvlak, rechtgetrokken met breedte 1.
        public var elements: [FacadePhotoElement]
        /// Aantal kozijnen dat deze foto deelt met de vorige (genegeerd bij de eerste foto).
        public var overlap: Int
        public init(elements: [FacadePhotoElement], overlap: Int) { self.elements = elements; self.overlap = overlap }
    }

    public struct Result: Equatable {
        /// Alle elementen in meters op de hele gevel.
        public var elements: [FacadePhotoElement]
        public var widthM: Double
        /// Kozijnen die in een overlap stonden en daardoor één keer zijn geteld.
        public var duplicates: Int
    }

    public enum Failure: Error, Equatable {
        /// Foto `part` (1-based) heeft geen overlap met de vorige.
        case noOverlap(part: Int)
        /// De kozijnen in de overlap passen niet bij elkaar (aantal of soort).
        case mismatch(part: Int)
    }

    static func openings(_ els: [FacadePhotoElement]) -> [FacadePhotoElement] {
        els.filter { $0.type.isOpening }.sorted { FacadePhoto.centroid($0.points)[0] < FacadePhoto.centroid($1.points)[0] }
    }
    static func width(_ e: FacadePhotoElement) -> Double { FacadePhoto.quantities(e, mpp: 1, all: []).widthM ?? 0 }

    /// Knipt een element af op het bereik lo ≤ x ≤ hi. Kaders gaan mee op hun middelpunt, muren en lijnen worden echt geknipt.
    static func clip(_ e: FacadePhotoElement, lo: Double, hi: Double) -> FacadePhotoElement? {
        switch e.type.kind {
        case .quad:
            let cx = FacadePhoto.centroid(e.points)[0]
            return cx >= lo && cx < hi ? e : nil
        case .poly:
            let l = max(lo, -1e12), h = min(hi, 1e12)   // geen oneindig in de meetkunde
            let box: [[Double]] = [[l, -1e9], [h, -1e9], [h, 1e9], [l, 1e9]]
            let p = FacadePhoto.intersection(e.points, box)
            guard p.count >= 3, FacadePhoto.area(p) > 1e-9 else { return nil }
            var r = e; r.points = p; return r
        case .line:
            var out: [[Double]] = []
            for i in 1..<max(1, e.points.count) {
                var a = e.points[i - 1], b = e.points[i]
                if a[0] > b[0] { swap(&a, &b) }
                guard b[0] >= lo, a[0] <= hi else { continue }
                func at(_ x: Double) -> [Double] { b[0] == a[0] ? a : [x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])] }
                let s = a[0] < lo ? at(lo) : a, t = b[0] > hi ? at(hi) : b
                if out.last != s { out.append(s) }
                out.append(t)
            }
            guard out.count >= 2, FacadePhoto.length(out) > 1e-9 else { return nil }
            var r = e; r.points = out; return r
        }
    }

    public static func stitch(_ parts: [Part], totalWidthM: Double) -> Swift.Result<Result, Failure> {
        guard !parts.isEmpty, totalWidthM > 0 else { return .failure(.noOverlap(part: 1)) }
        var scale = [1.0], offset = [0.0], cuts: [Double] = []   // cuts[k-1]: grens tussen foto k-1 en k, globaal
        var duplicates = 0
        for k in 1..<parts.count {
            let n = parts[k].overlap
            guard n > 0 else { return .failure(.noOverlap(part: k + 1)) }
            let prev = openings(parts[k - 1].elements), cur = openings(parts[k].elements)
            guard prev.count >= n, cur.count >= n else { return .failure(.mismatch(part: k + 1)) }
            let a = Array(prev.suffix(n)), b = Array(cur.prefix(n))
            guard zip(a, b).allSatisfy({ $0.type == $1.type && width($1) > 0 }) else { return .failure(.mismatch(part: k + 1)) }
            let ratio = zip(a, b).map { width($0) / width($1) }.reduce(0, +) / Double(n)
            let s = scale[k - 1] * ratio
            let gx = { (e: FacadePhotoElement) in offset[k - 1] + scale[k - 1] * FacadePhoto.centroid(e.points)[0] }
            let off = zip(a, b).map { gx($0) - s * FacadePhoto.centroid($1.points)[0] }.reduce(0, +) / Double(n)
            scale.append(s); offset.append(off)
            // Grens: rechterrand van de overlapkozijnen (in de vorige foto).
            cuts.append(a.map { e in e.points.map { offset[k - 1] + scale[k - 1] * $0[0] }.max() ?? 0 }.max() ?? 0)
            duplicates += n
        }
        let total = offset[parts.count - 1] + scale[parts.count - 1] * 1
        guard total > 0 else { return .failure(.mismatch(part: parts.count)) }
        let m = totalWidthM / total
        var out: [FacadePhotoElement] = []
        var nextId = 1
        for (k, part) in parts.enumerated() {
            let lo = k == 0 ? -Double.infinity : cuts[k - 1], hi = k == parts.count - 1 ? Double.infinity : cuts[k]
            for e in part.elements {
                var g = e
                g.points = e.points.map { [(offset[k] + scale[k] * $0[0]), scale[k] * $0[1]] }
                guard var c = clip(g, lo: lo, hi: hi) else { continue }
                c.points = c.points.map { [$0[0] * m, $0[1] * m] }
                c.id = nextId; nextId += 1
                out.append(c)
            }
        }
        return .success(Result(elements: out, widthM: totalWidthM, duplicates: duplicates))
    }
}
