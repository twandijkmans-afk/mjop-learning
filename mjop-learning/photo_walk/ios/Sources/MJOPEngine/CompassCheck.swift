import Foundation

/// Kompascheck bij het fotograferen: wijst de camera naar de gevel die je hebt gekozen? Alleen een waarschuwing, nooit een blokkade:
/// het kompas van een telefoon kan bij staal, auto's of een betonnen gevel tientallen graden afwijken.
public enum CompassCheck {
    /// Boven deze afwijking (graden) vraagt de app of het de goede gevel is.
    public static let warnAbove = 60.0

    /// Windrichting (zoals in `FacadeSide.facing`) als graden vanaf het noorden.
    public static func azimuth(of facing: String) -> Double? {
        FootprintSides.directionNames.firstIndex(of: facing).map { Double($0) * 45 }
    }

    /// De richting waarin je kijkt als je recht voor deze gevel staat: tegengesteld aan de kant waar de gevel naartoe kijkt.
    public static func viewingHeading(facing: String) -> Double? {
        azimuth(of: facing).map { ($0 + 180).truncatingRemainder(dividingBy: 360) }
    }

    /// Hoeveel graden (0–180) de camera afwijkt van de kijkrichting voor deze gevel.
    public static func deviation(cameraHeading h: Double, facing: String) -> Double? {
        guard h.isFinite, let v = viewingHeading(facing: facing) else { return nil }
        let d = abs((h - v).truncatingRemainder(dividingBy: 360))
        return d > 180 ? 360 - d : d
    }

    /// Naam van een kijkrichting (noord, noordoost, ...).
    public static func name(of heading: Double) -> String {
        let n = FootprintSides.directionNames
        let i = Int(((heading.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360) / 45).rounded(.toNearestOrAwayFromZero)) % 8
        return n[i]
    }

    /// Kijkrichting van de achtercamera (langs de −z-as van het toestel) in graden vanaf magnetisch noord,
    /// uit de zwaartekracht en het magneetveld, beide in toestelcoördinaten. Nil als de richting niet te bepalen is
    /// (bijv. telefoon plat, of magneetveld evenwijdig aan de zwaartekracht).
    public static func heading(gravity g: [Double], magnetic b: [Double]) -> Double? {
        guard g.count == 3, b.count == 3 else { return nil }
        func cross(_ a: [Double], _ c: [Double]) -> [Double] { [a[1] * c[2] - a[2] * c[1], a[2] * c[0] - a[0] * c[2], a[0] * c[1] - a[1] * c[0]] }
        func norm(_ a: [Double]) -> [Double]? { let l = sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]); return l > 1e-9 ? a.map { $0 / l } : nil }
        func dot(_ a: [Double], _ c: [Double]) -> Double { a[0] * c[0] + a[1] * c[1] + a[2] * c[2] }
        guard let down = norm(g), let east = norm(cross(down, b)), let north = norm(cross(east, down)) else { return nil }
        let cam = [0.0, 0, -1]
        let cn = dot(cam, north), ce = dot(cam, east)
        guard hypot(cn, ce) > 0.3 else { return nil }   // camera wijst vrijwel recht omhoog of omlaag
        let deg = atan2(ce, cn) * 180 / .pi
        return (deg + 360).truncatingRemainder(dividingBy: 360)
    }
}
