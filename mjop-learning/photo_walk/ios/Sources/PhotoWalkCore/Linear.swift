import Foundation

/// 3D-vector in meter (wereld/camera) tenzij anders vermeld. Geen simd, zodat de kern ook op Linux compileert.
public struct Vec3: Equatable, Codable {
    public var x: Double, y: Double, z: Double
    public init(_ x: Double, _ y: Double, _ z: Double) { self.x = x; self.y = y; self.z = z }
    public static let zero = Vec3(0, 0, 0)
    public static func + (a: Vec3, b: Vec3) -> Vec3 { Vec3(a.x + b.x, a.y + b.y, a.z + b.z) }
    public static func - (a: Vec3, b: Vec3) -> Vec3 { Vec3(a.x - b.x, a.y - b.y, a.z - b.z) }
    public static func * (a: Vec3, s: Double) -> Vec3 { Vec3(a.x * s, a.y * s, a.z * s) }
    public func dot(_ b: Vec3) -> Double { x * b.x + y * b.y + z * b.z }
    public func cross(_ b: Vec3) -> Vec3 { Vec3(y * b.z - z * b.y, z * b.x - x * b.z, x * b.y - y * b.x) }
    public var norm: Double { dot(self).squareRoot() }
    public var normalized: Vec3 { let n = norm; return n > 0 ? self * (1 / n) : self }
}

/// Pixel in het beeldstelsel: u rechts, v omlaag, oorsprong = linkerbovenhoek van de linkerbovenpixel (middens op +0.5).
public struct Pixel: Equatable, Codable {
    public var u: Double, v: Double
    public init(_ u: Double, _ v: Double) { self.u = u; self.v = v }
}

/// Camera-naar-wereld pose, OpenCV-cameraconventie (x rechts, y omlaag, z vooruit). x_wereld = R * x_camera + t.
public struct Pose: Codable {
    public var r: [Vec3]   // rijen van R
    public var t: Vec3
    public init(rows: [Vec3], t: Vec3) { precondition(rows.count == 3); self.r = rows; self.t = t }
    public static let identity = Pose(rows: [Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)], t: .zero)
    public func rotate(_ v: Vec3) -> Vec3 { Vec3(r[0].dot(v), r[1].dot(v), r[2].dot(v)) }
    public func toWorld(_ c: Vec3) -> Vec3 { rotate(c) + t }
    public func toCamera(_ w: Vec3) -> Vec3 {                 // R^T (w - t)
        let d = w - t
        let col0 = Vec3(r[0].x, r[1].x, r[2].x), col1 = Vec3(r[0].y, r[1].y, r[2].y), col2 = Vec3(r[0].z, r[1].z, r[2].z)
        return Vec3(col0.dot(d), col1.dot(d), col2.dot(d))
    }
    public func rotateInverse(_ w: Vec3) -> Vec3 {
        let col0 = Vec3(r[0].x, r[1].x, r[2].x), col1 = Vec3(r[0].y, r[1].y, r[2].y), col2 = Vec3(r[0].z, r[1].z, r[2].z)
        return Vec3(col0.dot(w), col1.dot(w), col2.dot(w))
    }
    /// Uit een rij-hoofdvolgorde 4x4 (16 getallen), zoals in `camera_to_world` van het contract.
    public init(rowMajor m: [Double]) {
        precondition(m.count == 16)
        self.init(rows: [Vec3(m[0], m[1], m[2]), Vec3(m[4], m[5], m[6]), Vec3(m[8], m[9], m[10])], t: Vec3(m[3], m[7], m[11]))
    }
}

/// Deterministische PRNG (SplitMix64); NIET gelijk aan de numpy-stroom, dus onzekerheden komen niet bit-exact overeen met Python.
public struct SplitMix64 {
    var state: UInt64
    public init(seed: UInt64) { state = seed }
    public mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
    public mutating func uniform() -> Double { Double(next() >> 11) / Double(1 << 53) }
    public mutating func gaussian() -> Double {
        let u1 = max(uniform(), 1e-12), u2 = uniform()
        return (-2 * log(u1)).squareRoot() * cos(2 * Double.pi * u2)
    }
}

/// Oplossen van een n x n stelsel (Gauss met partiele pivotering). nil bij (bijna) singulier.
public func solveLinear(_ a: [[Double]], _ b: [Double]) -> [Double]? {
    let n = b.count
    var m = a, y = b
    for c in 0..<n {
        var p = c
        for r in c..<n where abs(m[r][c]) > abs(m[p][c]) { p = r }
        if abs(m[p][c]) < 1e-12 { return nil }
        m.swapAt(c, p); y.swapAt(c, p)
        if c + 1 < n {
            for r in (c + 1)..<n {
                let f = m[r][c] / m[c][c]
                for k in c..<n { m[r][k] -= f * m[c][k] }
                y[r] -= f * y[c]
            }
        }
    }
    var x = [Double](repeating: 0, count: n)
    for r in stride(from: n - 1, through: 0, by: -1) {
        var s = y[r]
        if r + 1 < n { for k in (r + 1)..<n { s -= m[r][k] * x[k] } }
        x[r] = s / m[r][r]
    }
    return x
}
