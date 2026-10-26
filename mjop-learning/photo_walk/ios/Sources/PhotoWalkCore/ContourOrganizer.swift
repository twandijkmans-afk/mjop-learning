import Foundation

/// Een kandidaat-vierhoek van een detector (Vision-rechthoek of -contour), in NATIVE pixels, TL, TR, BR, BL.
public struct QuadCandidate: Equatable {
    public var corners: [Pixel]
    public var detector: String
    public var score: Double
    public init(corners: [Pixel], detector: String, score: Double) { self.corners = corners; self.detector = detector; self.score = score }
}

/// Eén opening (kozijn) met buitencontour en glasvlakken. Glasvlakken zijn nooit zelf een kozijn.
public struct OpeningGroup: Equatable {
    public var outer: [Pixel]                  // gedetecteerde of voorgestelde buitencontour
    public var outerDetected: Bool             // true: de buitencontour is zelf een gedetecteerde vierhoek
    public var panes: [[Pixel]]                // glasvlakken; leeg = onbekend
    public var evidence: OpeningEvidence       // NESTED_PANES | PANE_GROUP | SINGLE
    public var status: OuterContourStatus      // DETECTED_ENCLOSING_PANES | UNVERIFIED | PROPOSED_EXPANSION
    public var detector: String
    public var score: Double
    public var glassCoverage: Double?
}

public struct IgnoredCandidate: Equatable {
    public var corners: [Pixel]
    public var detector: String
    public var reason: String                  // INVALID_SHAPE | TOO_SMALL | TOO_LARGE | DUPLICATE | CONTAINS_OPENINGS
}

/// Drempels: PROVISIONAL_UNVALIDATED (niet getoetst op echte gevels). Gelijk aan facade.ContourConfig.
public struct ContourConfig {
    public var minRelArea = 0.0015, maxRelArea = 0.9
    public var duplicateIoU = 0.8
    public var containFraction = 0.85, containMinAreaRatio = 1.15
    public var minGlassCoverage = 0.30
    public var paneOverlap = 0.6, paneMaxGap = 0.35, paneSizeRatio = 0.6
    public init() {}
}

/// Ordent kandidaat-vierhoeken tot openingen (buitenkozijn + glasvlakken). Deterministisch; zelfde regels als facade.organize:
/// * een vierhoek die andere vierhoeken omsluit = buitenkozijn met glasvlakken (DETECTED_ENCLOSING_PANES; bij weinig glas UNVERIFIED);
/// * een vierhoek die zelf kozijnen omsluit (gevelvlak, paneel) is geen kozijn;
/// * losse vierhoeken naast elkaar = glasvlakken van één kozijn (PANE_GROUP, buitencontour alleen als voorstel);
/// * een losse vierhoek = glas of kozijn? (UNVERIFIED, geen maat tot bevestiging).
public enum ContourOrganizer {
    private static func lexLess(_ a: [Double], _ b: [Double]) -> Bool {
        for (x, y) in zip(a, b) where x != y { return x < y }
        return a.count < b.count
    }
    private static func boundsKey(_ p: [Pixel]) -> [Double] { let b = polygonBounds(p); return [b.minU, b.minV, b.maxU, b.maxV] }

    public static func contains(_ big: [Pixel], _ small: [Pixel], _ cfg: ContourConfig) -> Bool {
        let ab = polygonArea(big), asm = polygonArea(small)
        if asm <= 0 || ab < cfg.containMinAreaRatio * asm { return false }
        return convexIntersectionArea(big, small) / asm >= cfg.containFraction
    }

    static func adjacent(_ a: [Pixel], _ b: [Pixel], _ cfg: ContourConfig) -> Bool {
        let A = polygonBounds(a), B = polygonBounds(b)
        let configs: [(Double, Double, Double, Double, Double, Double, Double, Double)] = [
            (A.minV, A.maxV, B.minV, B.maxV, A.minU, A.maxU, B.minU, B.maxU),
            (A.minU, A.maxU, B.minU, B.maxU, A.minV, A.maxV, B.minV, B.maxV),
        ]
        for (a0, a1, b0, b1, c0, c1, d0, d1) in configs {
            let ha = a1 - a0, hb = b1 - b0
            if min(ha, hb) <= 0 || min(ha, hb) / max(ha, hb) < cfg.paneSizeRatio { continue }
            let overlap = min(a1, b1) - max(a0, b0)
            if overlap < cfg.paneOverlap * min(ha, hb) { continue }
            let wa = c1 - c0, wb = d1 - d0
            let gap = max(d0 - c1, c0 - d1)
            if gap >= -0.05 * min(wa, wb) && gap <= cfg.paneMaxGap * min(wa, wb) { return true }
        }
        return false
    }

    static func bboxQuad(_ polys: [[Pixel]]) -> [Pixel] {
        let all = polys.flatMap { $0 }
        let b = polygonBounds(all)
        return [Pixel(b.minU, b.minV), Pixel(b.maxU, b.minV), Pixel(b.maxU, b.maxV), Pixel(b.minU, b.maxV)]
    }

    private static func sortPanes(_ p: [[Pixel]]) -> [[Pixel]] {
        p.sorted { let x = polygonBounds($0), y = polygonBounds($1); return lexLess([x.minV, x.minU], [y.minV, y.minU]) }
    }

    public static func organize(_ candidates: [QuadCandidate], imageWidth: Double, imageHeight: Double, config cfg: ContourConfig = ContourConfig())
        -> (groups: [OpeningGroup], ignored: [IgnoredCandidate]) {
        let total = imageWidth * imageHeight
        var ignored: [IgnoredCandidate] = []
        var valid: [QuadCandidate] = []
        for c in candidates {
            if !isSimpleConvexQuad(c.corners, imageArea: total) { ignored.append(IgnoredCandidate(corners: c.corners, detector: c.detector, reason: "INVALID_SHAPE")); continue }
            let a = polygonArea(c.corners)
            if a < cfg.minRelArea * total { ignored.append(IgnoredCandidate(corners: c.corners, detector: c.detector, reason: "TOO_SMALL")); continue }
            if a > cfg.maxRelArea * total { ignored.append(IgnoredCandidate(corners: c.corners, detector: c.detector, reason: "TOO_LARGE")); continue }
            valid.append(c)
        }
        // dubbelingen: hoogste score, dan grootste, blijft
        valid.sort { x, y in lexLess([-x.score, -polygonArea(x.corners)] + boundsKey(x.corners), [-y.score, -polygonArea(y.corners)] + boundsKey(y.corners)) }
        var uniq: [QuadCandidate] = []
        for c in valid {
            if uniq.contains(where: { polygonIoU($0.corners, c.corners) > cfg.duplicateIoU }) {
                ignored.append(IgnoredCandidate(corners: c.corners, detector: c.detector, reason: "DUPLICATE"))
            } else { uniq.append(c) }
        }
        uniq.sort { x, y in lexLess([-polygonArea(x.corners)] + boundsKey(x.corners), [-polygonArea(y.corners)] + boundsKey(y.corners)) }
        let n = uniq.count
        var parent = [Int?](repeating: nil, count: n)
        for i in 0..<n {
            var best: Int? = nil
            for j in 0..<n where i != j && contains(uniq[j].corners, uniq[i].corners, cfg) {
                if best == nil || polygonArea(uniq[j].corners) < polygonArea(uniq[best!].corners) { best = j }
            }
            parent[i] = best
        }
        let children: [[Int]] = (0..<n).map { i in (0..<n).filter { parent[$0] == i } }
        let hasChildren = children.map { !$0.isEmpty }
        var groups: [OpeningGroup] = []
        for i in 0..<n where hasChildren[i] {
            if children[i].contains(where: { hasChildren[$0] }) {
                ignored.append(IgnoredCandidate(corners: uniq[i].corners, detector: uniq[i].detector, reason: "CONTAINS_OPENINGS"))
                continue
            }
            let panes = sortPanes(children[i].map { uniq[$0].corners })
            let cov = min(1.0, panes.map(polygonArea).reduce(0, +) / polygonArea(uniq[i].corners))
            groups.append(OpeningGroup(outer: uniq[i].corners, outerDetected: true, panes: panes, evidence: .NESTED_PANES,
                                       status: cov >= cfg.minGlassCoverage ? .DETECTED_ENCLOSING_PANES : .UNVERIFIED,
                                       detector: uniq[i].detector, score: uniq[i].score, glassCoverage: (cov * 1e6).rounded() / 1e6))
        }
        var roots: [Int] = []
        for i in 0..<n where !hasChildren[i] {
            if let p = parent[i], !children[p].contains(where: { hasChildren[$0] }) { continue }   // glasvlak van een kozijn hierboven
            roots.append(i)
        }
        var comp: [Int: Int] = [:]
        for i in roots { comp[i] = i }
        func find(_ x0: Int) -> Int {
            var x = x0
            while comp[x]! != x { comp[x] = comp[comp[x]!]!; x = comp[x]! }
            return x
        }
        for ai in 0..<roots.count {
            for bi in (ai + 1)..<max(roots.count, ai + 1) {
                let ia = roots[ai], ib = roots[bi]
                if adjacent(uniq[ia].corners, uniq[ib].corners, cfg) {
                    let ra = find(ia), rb = find(ib)
                    if ra != rb { comp[max(ra, rb)] = min(ra, rb) }
                }
            }
        }
        var members: [Int: [Int]] = [:]
        for i in roots { members[find(i), default: []].append(i) }
        for key in members.keys.sorted() {
            let ms = members[key]!
            if ms.count == 1 {
                let c = uniq[ms[0]]
                groups.append(OpeningGroup(outer: c.corners, outerDetected: true, panes: [], evidence: .SINGLE, status: .UNVERIFIED,
                                           detector: c.detector, score: c.score, glassCoverage: nil))
            } else {
                let panes = sortPanes(ms.map { uniq[$0].corners })
                let best = ms.max { x, y in uniq[x].score != uniq[y].score ? uniq[x].score < uniq[y].score : x > y }!
                groups.append(OpeningGroup(outer: bboxQuad(panes), outerDetected: false, panes: panes, evidence: .PANE_GROUP, status: .PROPOSED_EXPANSION,
                                           detector: uniq[best].detector, score: uniq[best].score, glassCoverage: nil))
            }
        }
        // stabiel sorteren (zoals Python): boven -> onder, links -> rechts; bij gelijke positie de invoegvolgorde
        let indexed = groups.enumerated().map { ($0.offset, $0.element) }
        let sorted = indexed.sorted { x, y in
            let bx = polygonBounds(x.1.outer), by = polygonBounds(y.1.outer)
            return lexLess([bx.minV, bx.minU, Double(x.0)], [by.minV, by.minU, Double(y.0)])
        }
        return (sorted.map { $0.1 }, ignored)
    }
}
