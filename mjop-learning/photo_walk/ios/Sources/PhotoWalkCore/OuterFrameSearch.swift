import Foundation

/// Grijswaardenbeeld (0..255), rij-hoofdvolgorde: pixels[v * width + u]. Pixelmiddens op +0.5, zoals in de rest van de kern.
public struct GrayImage {
    public let width: Int, height: Int
    public let pixels: [UInt8]
    public init(width: Int, height: Int, pixels: [UInt8]) {
        precondition(pixels.count == width * height)
        self.width = width; self.height = height; self.pixels = pixels
    }
    /// Bilineaire grijswaarde (randen geklemd). Zelfde formule als facade._sample.
    public func sample(_ u: Double, _ v: Double) -> Double {
        let x = u - 0.5, y = v - 0.5
        let x0 = Int(floor(x)), y0 = Int(floor(y))
        let fx = x - Double(x0), fy = y - Double(y0)
        func px(_ xx: Int, _ yy: Int) -> Double {
            Double(pixels[min(max(yy, 0), height - 1) * width + min(max(xx, 0), width - 1)])
        }
        let p00: Double = px(x0, y0), p10: Double = px(x0 + 1, y0), p01: Double = px(x0, y0 + 1), p11: Double = px(x0 + 1, y0 + 1)
        let top: Double = (1 - fx) * p00 + fx * p10
        let bottom: Double = (1 - fx) * p01 + fx * p11
        return (1 - fy) * top + fy * bottom
    }
}

/// PROVISIONAL_UNVALIDATED; gelijk aan facade.ExpansionConfig.
public struct ExpansionConfig {
    public var samples = 24
    public var sideMargin = 0.15
    public var minOffsetPx = 4.0
    public var maxOffsetRel = 0.30
    public var minEdgeStrength = 6.0
    public var relToInnerEdge = 0.35
    public var minConsistency = 0.7
    public init() {}
}

public struct ExpansionProposal: Equatable {
    public var quad: [Pixel]
    public var offsetsPx: [Double]
    public var strengths: [Double]
}

/// Voorstel "vergroot naar buitenkozijn": zoekt per zijde de eerste duidelijke, evenwijdige rand buiten de vierhoek (meestal de overgang
/// kozijnprofiel -> muur) en snijdt de verschoven zijden. Het resultaat is ALTIJD een voorstel (PROPOSED_EXPANSION) dat de gebruiker moet
/// bevestigen; nil als een zijde geen duidelijke rand heeft (dan tekent de gebruiker de buitencontour zelf). Zelfde regels als facade.propose_outer.
/// Beperking: vanaf één ruit van een kozijn met meerdere ruiten eindigt de zoektocht bij de tussenstijl; daarom eerst glasvlakken groeperen.
public enum OuterFrameSearch {
    public struct Profile { public var offsets: [Double]; public var strengths: [Double]; public var consistency: [Double]; public var normal: Pixel }

    public static func edgeProfile(_ img: GrayImage, quad: [Pixel], side: Int, config cfg: ExpansionConfig = ExpansionConfig()) -> Profile {
        let c = polygonCentroid(quad)
        let a = quad[side], b = quad[(side + 1) % 4]
        let du = b.u - a.u, dv = b.v - a.v
        let length = (du * du + dv * dv).squareRoot()
        var nu = -dv / length, nv = du / length
        let mu = (a.u + b.u) / 2, mv = (a.v + b.v) / 2
        if (mu - c.u) * nu + (mv - c.v) * nv < 0 { nu = -nu; nv = -nv }
        let prev = quad[(side + 3) % 4], nxt = quad[(side + 2) % 4]
        let la: Double = hypot(a.u - prev.u, a.v - prev.v)
        let lb: Double = hypot(b.u - nxt.u, b.v - nxt.v)
        let adj: Double = 0.5 * (la + lb)
        let tMax = Int(floor(cfg.maxOffsetRel * adj))
        var offsets: [Double] = [], strengths: [Double] = [], consistency: [Double] = []
        for t in 0...max(tMax, 0) {
            var g: [Double] = []
            g.reserveCapacity(cfg.samples)
            for k in 0..<cfg.samples {
                let s = cfg.sideMargin + (1 - 2 * cfg.sideMargin) * (Double(k) + 0.5) / Double(cfg.samples)
                let pu = a.u + du * s + nu * Double(t), pv = a.v + dv * s + nv * Double(t)
                g.append(img.sample(pu + nu, pv + nv) - img.sample(pu - nu, pv - nv))
            }
            let mean = g.reduce(0, +) / Double(g.count)
            let sign: Double = mean >= 0 ? 1 : -1
            offsets.append(Double(t))
            strengths.append(abs(mean))
            consistency.append(Double(g.filter { $0 * sign > 0 }.count) / Double(g.count))
        }
        return Profile(offsets: offsets, strengths: strengths, consistency: consistency, normal: Pixel(nu, nv))
    }

    private static func intersect(_ p: Pixel, _ d: Pixel, _ q: Pixel, _ e: Pixel) -> Pixel? {
        let den = d.u * e.v - d.v * e.u
        if abs(den) < 1e-9 { return nil }
        let t = ((q.u - p.u) * e.v - (q.v - p.v) * e.u) / den
        return Pixel(p.u + t * d.u, p.v + t * d.v)
    }

    public static func proposeOuter(_ img: GrayImage, quad: [Pixel], config cfg: ExpansionConfig = ExpansionConfig()) -> ExpansionProposal? {
        guard quad.count == 4 else { return nil }
        var shifts: [(Double, Pixel, Double)] = []
        for side in 0..<4 {
            let p = edgeProfile(img, quad: quad, side: side, config: cfg)
            let st = p.strengths, co = p.consistency, offs = p.offsets
            if st.count < 3 { return nil }
            let innerEnd = min(Int(cfg.minOffsetPx), st.count - 1)
            let inner = st[0...innerEnd].max() ?? 0
            let threshold = max(cfg.minEdgeStrength, cfg.relToInnerEdge * inner)
            var chosen: (Double, Double)? = nil
            for i in 1..<(st.count - 1) {
                if offs[i] < cfg.minOffsetPx { continue }
                if st[i] >= threshold && co[i] >= cfg.minConsistency && st[i] >= st[i - 1] && st[i] >= st[i + 1] { chosen = (offs[i], st[i]); break }
            }
            guard let ch = chosen else { return nil }
            shifts.append((ch.0, p.normal, ch.1))
        }
        var lines: [(Pixel, Pixel)] = []
        for side in 0..<4 {
            let a = quad[side], b = quad[(side + 1) % 4]
            let (t, n, _) = shifts[side]
            lines.append((Pixel(a.u + n.u * t, a.v + n.v * t), Pixel(b.u - a.u, b.v - a.v)))
        }
        var out: [Pixel] = []
        for i in 0..<4 {
            let l0 = lines[(i + 3) % 4], l1 = lines[i]
            guard let p = intersect(l0.0, l0.1, l1.0, l1.1) else { return nil }
            out.append(Pixel((p.u * 1e6).rounded() / 1e6, (p.v * 1e6).rounded() / 1e6))
        }
        guard isSimpleConvexQuad(out) else { return nil }
        return ExpansionProposal(quad: out, offsetsPx: shifts.map { $0.0 }, strengths: shifts.map { ($0.2 * 1e6).rounded() / 1e6 })
    }
}
