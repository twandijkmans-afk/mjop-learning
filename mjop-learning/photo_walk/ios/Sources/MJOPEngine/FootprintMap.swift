import Foundation

/// Kaart bij de gevelscan: de BAG-omtrek op een luchtfoto (Web Mercator, EPSG:3857), de gekozen gevelzijde en een
/// aanbevolen standplaats om de hele gevel recht van voren op de foto te krijgen. Pure meetkunde, geen netwerk.
public enum FootprintMap {
    static let R = 6_378_137.0

    /// Lengte/breedtegraad naar Web Mercator-meters.
    public static func mercator(_ ll: [Double]) -> [Double] {
        let lat = max(-85, min(85, ll[1])) * .pi / 180
        return [R * ll[0] * .pi / 180, R * log(tan(.pi / 4 + lat / 2))]
    }

    /// Terug van meters rond het eerste punt van de omtrek (zoals `FootprintSides.meters`) naar lengte/breedtegraad.
    public static func lonLat(meters p: [Double], origin: [Double]) -> [Double] {
        let kx = 111_320 * cos(origin[1] * .pi / 180), ky = 110_540.0
        return [origin[0] + p[0] / kx, origin[1] + p[1] / ky]
    }

    /// Uitsnede rond de omtrek, met marge in echte meters, in de gevraagde beeldverhouding (breedte / hoogte).
    public struct Frame: Equatable {
        public var minX: Double, minY: Double, maxX: Double, maxY: Double
        /// Punt (lengte/breedtegraad) naar pixels in een beeld van `w` × `h` (y omlaag).
        public func pixel(_ ll: [Double], w: Double, h: Double) -> [Double] {
            let m = FootprintMap.mercator(ll)
            return [(m[0] - minX) / (maxX - minX) * w, (maxY - m[1]) / (maxY - minY) * h]
        }
    }

    public static func frame(ring: [[Double]], aspect: Double, marginM: Double) -> Frame? {
        guard ring.count >= 3, aspect > 0 else { return nil }
        let ms = ring.map(mercator)
        let lat = ring.map { $0[1] }.reduce(0, +) / Double(ring.count) * .pi / 180
        let pad = marginM / cos(lat)   // mercator-meters zijn op 52° ongeveer 1,6× zo groot als echte meters
        var minX = ms.map { $0[0] }.min()! - pad, maxX = ms.map { $0[0] }.max()! + pad
        var minY = ms.map { $0[1] }.min()! - pad, maxY = ms.map { $0[1] }.max()! + pad
        let w = maxX - minX, h = maxY - minY
        if w / h < aspect { let d = (h * aspect - w) / 2; minX -= d; maxX += d } else { let d = (w / aspect - h) / 2; minY -= d; maxY += d }
        return Frame(minX: minX, minY: minY, maxX: maxX, maxY: maxY)
    }

    /// Aanbevolen standplaats voor een gevelzijde: recht voor het midden, naar buiten, op een afstand waarop de hele
    /// zijde in beeld past (telefoon rechtop; horizontale beeldhoek 0,5× ≈ 85°, 1× ≈ 50°) met wat ruimte eromheen.
    /// `ringM` is de omtrek in meters (voor de richting naar buiten). Het blijft een advies: bomen, hekken en verkeer bepalen of het kan.
    public static func standpoint(from a: [Double], to b: [Double], ringM: [[Double]], ultraWide: Bool = true) -> (point: [Double], distanceM: Double) {
        var signed = 0.0
        for i in 0..<ringM.count { let p = ringM[i], q = ringM[(i + 1) % ringM.count]; signed += p[0] * q[1] - q[0] * p[1] }
        let dx = b[0] - a[0], dy = b[1] - a[1], len = max(hypot(dx, dy), 0.1)
        let nx = (signed > 0 ? dy : -dy) / len, ny = (signed > 0 ? -dx : dx) / len
        let fov = (ultraWide ? 85.0 : 50.0) * .pi / 180
        let d = min(60, max(3, (len / 2) / tan(fov / 2) * 1.15))
        let mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        return ([mid[0] + nx * d, mid[1] + ny * d], d)
    }
}
