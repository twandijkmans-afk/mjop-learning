import Foundation

public struct PlaneFit {
    public var n: Vec3, d: Double
    public var inlierRatio: Double, rmsM: Double, nPoints: Int, nInliers: Int, spreadM: Double
    public var centroid: Vec3
}

/// Kleinste eigenvector van de covariantiematrix via inverse iteratie (3x3), zonder externe bibliotheken.
func smallestEigenvector(_ cov: [[Double]]) -> Vec3 {
    var shifted = cov
    let eps = 1e-9 * max(1e-12, cov[0][0] + cov[1][1] + cov[2][2])
    for i in 0..<3 { shifted[i][i] += eps }
    var v = [1.0, 0.7, 0.3]
    for _ in 0..<40 {
        guard let w = solveLinear(shifted, v) else { break }
        let n = (w[0] * w[0] + w[1] * w[1] + w[2] * w[2]).squareRoot()
        if n == 0 { break }
        v = w.map { $0 / n }
    }
    return Vec3(v[0], v[1], v[2]).normalized
}

func fitLeastSquaresPlane(_ pts: [Vec3]) -> (n: Vec3, d: Double, centroid: Vec3) {
    let c = pts.reduce(Vec3.zero, +) * (1.0 / Double(pts.count))
    var cov = [[Double]](repeating: [0, 0, 0], count: 3)
    for p in pts {
        let q = p - c, a = [q.x, q.y, q.z]
        for i in 0..<3 { for j in 0..<3 { cov[i][j] += a[i] * a[j] } }
    }
    let n = smallestEigenvector(cov)
    return (n, n.dot(c), c)
}

public func fitPlaneRansac(_ pts: [Vec3], threshold: Double, iterations: Int, seed: UInt64) -> PlaneFit? {
    guard pts.count >= 3 else { return nil }
    var rng = SplitMix64(seed: seed)
    var best: (Vec3, Double)? = nil
    var bestCount = -1
    for _ in 0..<iterations {
        let i = Int(rng.next() % UInt64(pts.count)), j = Int(rng.next() % UInt64(pts.count)), k = Int(rng.next() % UInt64(pts.count))
        if i == j || j == k || i == k { continue }
        let nn = (pts[j] - pts[i]).cross(pts[k] - pts[i])
        if nn.norm < 1e-9 { continue }
        let n = nn.normalized
        let cnt = pts.reduce(0) { $0 + (abs((($1 - pts[i]).dot(n))) < threshold ? 1 : 0) }
        if cnt > bestCount { bestCount = cnt; best = (n, n.dot(pts[i])) }
    }
    guard let b = best else { return nil }
    var n = b.0, d = b.1
    var inl = pts.filter { abs($0.dot(n) - d) < threshold }
    if inl.count >= 3 {
        let f = fitLeastSquaresPlane(inl)
        n = f.n; d = f.d
        inl = pts.filter { abs($0.dot(n) - d) < threshold }
    }
    guard !inl.isEmpty else { return nil }
    let ctr = inl.reduce(Vec3.zero, +) * (1.0 / Double(inl.count))
    let rms = (inl.reduce(0) { $0 + pow($1.dot(n) - d, 2) } / Double(inl.count)).squareRoot()
    let spread = (inl.reduce(0) { acc, p in let q = p - ctr; return acc + q.dot(q) - pow(q.dot(n), 2) } / Double(inl.count)).squareRoot()
    return PlaneFit(n: n, d: d, inlierRatio: Double(inl.count) / Double(pts.count), rmsM: rms, nPoints: pts.count, nInliers: inl.count, spreadM: spread, centroid: ctr)
}
