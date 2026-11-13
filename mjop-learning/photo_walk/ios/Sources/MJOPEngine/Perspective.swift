import Foundation

/// Projectieve afbeelding van het vlak (3×3, rij voor rij, h[8] = 1).
public struct Homography: Equatable {
    public var h: [Double]

    /// Van vier bronpunten naar vier doelpunten. Nil als de punten geen geldige vierhoek vormen.
    public init?(from src: [[Double]], to dst: [[Double]]) {
        guard src.count == 4, dst.count == 4 else { return nil }
        var a = [[Double]](), b = [Double]()
        for i in 0..<4 {
            let x = src[i][0], y = src[i][1], X = dst[i][0], Y = dst[i][1]
            a.append([x, y, 1, 0, 0, 0, -X * x, -X * y]); b.append(X)
            a.append([0, 0, 0, x, y, 1, -Y * x, -Y * y]); b.append(Y)
        }
        guard let s = Homography.solve(a, b) else { return nil }
        h = s + [1]
    }

    public func apply(_ p: [Double]) -> [Double]? {
        let w = h[6] * p[0] + h[7] * p[1] + h[8]
        guard abs(w) > 1e-12 else { return nil }
        return [(h[0] * p[0] + h[1] * p[1] + h[2]) / w, (h[3] * p[0] + h[4] * p[1] + h[5]) / w]
    }

    /// Gauss-eliminatie met spilkeuze.
    static func solve(_ a0: [[Double]], _ b0: [Double]) -> [Double]? {
        var a = a0, b = b0
        let n = b.count
        for c in 0..<n {
            guard let p = (c..<n).max(by: { abs(a[$0][c]) < abs(a[$1][c]) }), abs(a[p][c]) > 1e-12 else { return nil }
            a.swapAt(c, p); b.swapAt(c, p)
            for r in 0..<n where r != c {
                let f = a[r][c] / a[c][c]
                if f == 0 { continue }
                for k in c..<n { a[r][k] -= f * a[c][k] }
                b[r] -= f * b[c]
            }
        }
        return (0..<n).map { b[$0] / a[$0][$0] }
    }
}

/// Perspectiefcorrectie van één gevelvlak. Pure meetkunde, geen AI: Claude geeft alleen de vier hoeken in pixels.
public enum FacadePerspective {
    /// Waar de brandpuntsafstand vandaan komt (voor de bandbreedte van de maten).
    public enum FocalSource: String, Codable { case exif, geschat, aangenomen }

    public struct Rectified: Equatable {
        /// Elementen in meters op het rechtgetrokken vlak (x naar rechts, y naar beneden, linksboven = 0,0).
        public var elements: [FacadePhotoElement]
        public var widthM: Double
        public var heightM: Double
        public var focalSource: FocalSource
        /// Elementen die niet op dit vlak liggen of niet af te beelden waren; die tellen hier niet mee.
        public var leftOut: Int
    }

    /// Brandpuntsafstand in pixels uit de 35mm-equivalent (EXIF), over de diagonaal van de foto.
    public static func focalPx(focal35mm: Double, width: Double, height: Double) -> Double? {
        guard focal35mm > 0 else { return nil }
        return focal35mm * hypot(width, height) / hypot(36, 24)
    }

    public static func isConvex(_ q: [[Double]]) -> Bool {
        guard q.count == 4 else { return false }
        var sign = 0.0
        for i in 0..<4 {
            let a = q[i], b = q[(i + 1) % 4], c = q[(i + 2) % 4]
            let z = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(z) < 1e-9 { return false }
            if sign == 0 { sign = z } else if (z > 0) != (sign > 0) { return false }
        }
        return true
    }

    /// Breedte gedeeld door hoogte van de echte rechthoek achter vier hoeken (linksboven, rechtsboven, rechtsonder, linksonder),
    /// met het hoofdpunt in het midden van de foto (Zhang & He, 2006). Zonder brandpunt uit EXIF wordt het uit de vier hoeken geschat;
    /// lukt dat niet en lopen de randen vrijwel evenwijdig, dan hangt de uitkomst nauwelijks van het brandpunt af en wordt een gangbare waarde aangenomen.
    public static func aspect(corners q: [[Double]], focalPx: Double?, width W: Double, height H: Double) -> (ratio: Double, source: FocalSource)? {
        guard isConvex(q) else { return nil }
        let cx = W / 2, cy = H / 2
        // Volgorde voor de formule: linksboven, rechtsboven, linksonder, rechtsonder.
        let m = [q[0], q[1], q[3], q[2]].map { [$0[0] - cx, $0[1] - cy, 1.0] }
        func cross(_ a: [Double], _ b: [Double]) -> [Double] { [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]] }
        func dot(_ a: [Double], _ b: [Double]) -> Double { a[0] * b[0] + a[1] * b[1] + a[2] * b[2] }
        let c14 = cross(m[0], m[3])
        let d2 = dot(cross(m[1], m[3]), m[2]), d3 = dot(cross(m[2], m[3]), m[1])
        guard abs(d2) > 1e-9, abs(d3) > 1e-9 else { return nil }
        let k2 = dot(c14, m[2]) / d2, k3 = dot(c14, m[1]) / d3
        let n2 = m[1].map { $0 * k2 }.enumerated().map { $1 - m[0][$0] }
        let n3 = m[2].map { $0 * k3 }.enumerated().map { $1 - m[0][$0] }
        let diag = hypot(W, H)
        var f: Double?, source = FocalSource.exif
        if let focalPx, focalPx > 0 { f = focalPx }
        else if abs(n2[2]) > 1e-6, abs(n3[2]) > 1e-6 {
            let v = -(n2[0] * n3[0] + n2[1] * n3[1]) / (n2[2] * n3[2])
            if v > 0, sqrt(v) > 0.2 * diag, sqrt(v) < 2.5 * diag { f = sqrt(v); source = .geschat }
        }
        if f == nil {
            // Randen bijna evenwijdig: het brandpunt doet er nauwelijks toe. Gangbare telefoonlens (26 mm-equivalent).
            let parallel = abs(n2[2]) < 0.02 && abs(n3[2]) < 0.02
            guard parallel else { return nil }
            f = 26 * diag / hypot(36, 24); source = .aangenomen
        }
        guard let fl = f else { return nil }
        let num = (n2[0] * n2[0] + n2[1] * n2[1]) / (fl * fl) + n2[2] * n2[2]
        let den = (n3[0] * n3[0] + n3[1] * n3[1]) / (fl * fl) + n3[2] * n3[2]
        guard den > 0 else { return nil }
        let r = sqrt(num / den)
        guard r.isFinite, r > 0.05, r < 20 else { return nil }
        return (r, source)
    }

    /// Trekt het vlak recht: de bovenrand van het vlak krijgt de gevelbreedte uit de BAG, de hoogte volgt uit de beeldverhouding.
    /// Alleen elementen die op dit vlak liggen (of zonder vlak, bij oudere scans) worden meegenomen.
    public static func rectify(_ els: [FacadePhotoElement], plane: FacadePlane, widthM: Double, focalPx: Double?, imageWidth W: Double, imageHeight H: Double) -> Rectified? {
        guard widthM > 0, let a = aspect(corners: plane.corners, focalPx: focalPx, width: W, height: H) else { return nil }
        let heightM = widthM / a.ratio
        guard let hom = Homography(from: plane.corners, to: [[0, 0], [widthM, 0], [widthM, heightM], [0, heightM]]) else { return nil }
        var out: [FacadePhotoElement] = []
        var leftOut = 0
        for e in els {
            if let p = e.plane, p != plane.id { leftOut += 1; continue }
            let pts = e.points.compactMap { hom.apply($0) }
            guard pts.count == e.points.count else { leftOut += 1; continue }
            var r = e; r.points = pts
            out.append(r)
        }
        return Rectified(elements: out, widthM: widthM, heightM: heightM, focalSource: a.source, leftOut: leftOut)
    }
}
