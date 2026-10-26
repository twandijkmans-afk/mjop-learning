import Foundation

/// SYNTHETISCH testbeeld (geen foto): metselwerk met voegen en assen-rechte kozijnen met profiel, glas, tussenstijlen en tussendorpel.
/// Exact gelijk aan facade.synthetic_facade_gray (Python), zodat beide kernen op hetzelfde beeld getest worden. Alleen voor tests en de selftest.
public enum SyntheticFacade {
    public struct Window {
        public var outer: (u0: Int, v0: Int, u1: Int, v1: Int)
        public var profile: Int
        public var mullions: Int
        public var transom: Bool
        public init(outer: (Int, Int, Int, Int), profile: Int, mullions: Int = 0, transom: Bool = false) {
            self.outer = (outer.0, outer.1, outer.2, outer.3); self.profile = profile; self.mullions = mullions; self.transom = transom
        }
    }

    /// Python: round() rondt half-naar-even af.
    private static func pyRound(_ x: Double) -> Int { Int(x.rounded(.toNearestOrEven)) }

    /// Ruitvakken (u0, v0, u1, v1) binnen een kozijn.
    public static func paneRects(_ w: Window) -> [(Int, Int, Int, Int)] {
        let iu0 = w.outer.u0 + w.profile, iv0 = w.outer.v0 + w.profile, iu1 = w.outer.u1 - w.profile, iv1 = w.outer.v1 - w.profile
        let n = w.mullions, bar = max(2, w.profile / 2)
        let innerW = iu1 - iu0
        let edges = (0...(n + 1)).map { k in iu0 + pyRound(Double(innerW * k) / Double(n + 1)) }
        let cols: [(Int, Int)] = (0...n).map { k in (edges[k] + (k > 0 ? bar / 2 : 0), edges[k + 1] - (k < n ? bar - bar / 2 : 0)) }
        var rows: [(Int, Int)] = [(iv0, iv1)]
        if w.transom { let mid = iv0 + (iv1 - iv0) / 3; rows = [(iv0, mid - bar / 2), (mid + bar - bar / 2, iv1)] }
        var out: [(Int, Int, Int, Int)] = []
        for (a, b) in cols { for (c, d) in rows { out.append((a, c, b, d)) } }
        return out
    }

    public static func gray(width: Int, height: Int, windows: [Window], wall: UInt8 = 118, mortar: UInt8 = 196, frame: UInt8 = 236, glass: UInt8 = 58,
                            brickH: Int = 24, brickW: Int = 60) -> GrayImage {
        var px = [UInt8](repeating: wall, count: width * height)
        for v in 0..<height {
            let row = v / brickH
            if v % brickH == 0 || v % brickH == 1 { for u in 0..<width { px[v * width + u] = mortar }; continue }
            let off = row % 2 == 0 ? 0 : brickW / 2
            for u in 0..<width where (u + off) % brickW == 0 || (u + off) % brickW == 1 { px[v * width + u] = mortar }
        }
        func fill(_ u0: Int, _ v0: Int, _ u1: Int, _ v1: Int, _ val: UInt8) {
            guard u1 > u0, v1 > v0 else { return }
            for v in max(v0, 0)..<min(v1, height) { for u in max(u0, 0)..<min(u1, width) { px[v * width + u] = val } }
        }
        for w in windows {
            fill(w.outer.u0, w.outer.v0, w.outer.u1, w.outer.v1, frame)
            for r in paneRects(w) { fill(r.0, r.1, r.2, r.3, glass) }
        }
        return GrayImage(width: width, height: height, pixels: px)
    }

    public static func quad(_ r: (Int, Int, Int, Int)) -> [Pixel] {
        [Pixel(Double(r.0), Double(r.1)), Pixel(Double(r.2), Double(r.1)), Pixel(Double(r.2), Double(r.3)), Pixel(Double(r.0), Double(r.3))]
    }

    /// Ware buitencontour en glasvlakken.
    public static func truth(_ windows: [Window]) -> [(outer: [Pixel], panes: [[Pixel]])] {
        windows.map { w in (quad((w.outer.u0, w.outer.v0, w.outer.u1, w.outer.v1)), paneRects(w).map(quad)) }
    }

    /// Controlegetal over het hele beeld (gelijk aan facade_parity.image_checksum).
    public static func checksum(_ img: GrayImage) -> Int64 {
        var s: Int64 = 0
        for (i, p) in img.pixels.enumerated() { s = (s + Int64(p) * Int64(i % 9973 + 1)) % 1_000_000_007 }
        return s
    }
}
