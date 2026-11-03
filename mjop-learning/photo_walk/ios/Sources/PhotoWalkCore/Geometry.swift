import Foundation

public let worldUp = Vec3(0, 1, 0)

/// Intrinsics in pixels van HETZELFDE beeld. Geen lensvervorming gemodelleerd.
public struct Intrinsics: Codable, Equatable {
    public var fx: Double, fy: Double, cx: Double, cy: Double
    public var width: Int, height: Int
    public init(fx: Double, fy: Double, cx: Double, cy: Double, width: Int, height: Int) {
        self.fx = fx; self.fy = fy; self.cx = cx; self.cy = cy; self.width = width; self.height = height
    }
    /// Camerastraal (z = 1) door een pixel, ongenormaliseerd.
    public func cameraRay(_ p: Pixel) -> Vec3 { Vec3((p.u - cx) / fx, (p.v - cy) / fy, 1) }
}

public func raysWorld(pose: Pose, intr: Intrinsics, pixels: [Pixel]) -> (origin: Vec3, dirs: [Vec3]) {
    (pose.t, pixels.map { pose.rotate(intr.cameraRay($0).normalized) })
}

/// Wereld -> (pixel, depth_z). depth_z <= 0: achter de camera.
public func project(pose: Pose, intr: Intrinsics, world: Vec3) -> (Pixel, Double) {
    let c = pose.toCamera(world)
    return (Pixel(intr.fx * c.x / c.z + intr.cx, intr.fy * c.y / c.z + intr.cy), c.z)
}

/// Pixel + depth_z (afstand langs de optische as) -> wereldpunt. Puntmeting op precies die pixel.
public func unprojectDepth(pose: Pose, intr: Intrinsics, pixel: Pixel, depthZ: Double) -> Vec3 {
    pose.toWorld(Vec3((pixel.u - intr.cx) / intr.fx * depthZ, (pixel.v - intr.cy) / intr.fy * depthZ, depthZ))
}

public struct RayPlaneHit { public var point: Vec3; public var t: Double; public var cosIncidence: Double }

/// Snijpunt van een straal met n.x = d; nil bij parallel of achter de oorsprong.
public func intersectRayPlane(origin: Vec3, dir: Vec3, n: Vec3, d: Double) -> RayPlaneHit? {
    let den = dir.dot(n)
    if abs(den) < 1e-9 { return nil }
    let t = (d - origin.dot(n)) / den
    if t <= 0 { return nil }
    return RayPlaneHit(point: origin + dir * t, t: t, cosIncidence: abs(den))
}

public func signedArea(_ p: [Pixel]) -> Double {
    var s = 0.0
    for i in 0..<p.count { let j = (i + 1) % p.count; s += p[i].u * p[j].v - p[j].u * p[i].v }
    return 0.5 * s
}

public func scalePolygon(_ p: [Pixel], _ s: Double) -> [Pixel] {
    let cu = p.map { $0.u }.reduce(0, +) / Double(p.count), cv = p.map { $0.v }.reduce(0, +) / Double(p.count)
    return p.map { Pixel(cu + ($0.u - cu) * s, cv + ($0.v - cv) * s) }
}

public func inConvexPolygon(_ pt: Pixel, _ poly: [Pixel]) -> Bool {
    let sign: Double = signedArea(poly) >= 0 ? 1 : -1
    for i in 0..<poly.count {
        let a = poly[i], b = poly[(i + 1) % poly.count]
        if ((b.u - a.u) * (pt.v - a.v) - (b.v - a.v) * (pt.u - a.u)) * sign < 0 { return false }
    }
    return true
}

/// Simpele, convexe vierhoek met consistente winding (detecteert verwisselde hoeken).
public func isSimpleConvexQuad(_ p: [Pixel], imageArea: Double = 1, minRelArea: Double = 1e-4) -> Bool {
    guard p.count == 4, p.allSatisfy({ $0.u.isFinite && $0.v.isFinite }) else { return false }
    var pos = 0, neg = 0
    for i in 0..<4 {
        let a = p[i], b = p[(i + 1) % 4], c = p[(i + 2) % 4]
        let s = (b.u - a.u) * (c.v - b.v) - (b.v - a.v) * (c.u - b.u)
        if s > 0 { pos += 1 } else if s < 0 { neg += 1 }
    }
    return (pos == 4 || neg == 4) && abs(signedArea(p)) > minRelArea * imageArea
}

/// Breedte/hoogte uit 4 hoeken (TL,TR,BR,BL); breedte = randenpaar dat het minst met `up` meeloopt (90 graden gedraaide volgorde wisselt maten niet).
public func dimsFromCorners(_ c: [Vec3], up: Vec3) -> (width: Double, height: Double) {
    let e = [c[1] - c[0], c[2] - c[1], c[2] - c[3], c[3] - c[0]]
    let l = e.map { $0.norm }
    func vert(_ i: Int) -> Double { abs(e[i].dot(up)) / max(l[i], 1e-12) }
    let a = (vert(0) + vert(2)) / 2, b = (vert(1) + vert(3)) / 2
    let p02 = (l[0] + l[2]) / 2, p13 = (l[1] + l[3]) / 2
    return a <= b ? (p02, p13) : (p13, p02)
}

/// Lijst met afwijkingen van een rechthoek (leeg = ok).
public func rectangularityProblems(_ c: [Vec3], edgeRatioTol: Double, angleTolDeg: Double) -> [String] {
    var bad: [String] = []
    let e = [c[1] - c[0], c[2] - c[1], c[2] - c[3], c[3] - c[0]]
    let l = e.map { $0.norm }
    for (i, j) in [(0, 2), (1, 3)] where abs(l[i] - l[j]) / max((l[i] + l[j]) / 2, 1e-9) > edgeRatioTol {
        bad.append("overstaande randen \(i)/\(j) verschillen")
    }
    for i in 0..<4 {
        let a = c[(i + 1) % 4] - c[i], b = c[(i + 3) % 4] - c[i]
        let ang = acos(max(-1, min(1, a.dot(b) / (a.norm * b.norm)))) * 180 / Double.pi
        if abs(ang - 90) > angleTolDeg { bad.append("hoek \(i) = \(ang)") }
    }
    return bad
}
