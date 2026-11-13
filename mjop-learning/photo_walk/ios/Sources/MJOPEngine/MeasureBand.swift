import Foundation

/// Bandbreedte van een maat uit een gevelfoto, met vaste regels (geen AI-schatting).
/// Elke bron van onzekerheid geeft een relatieve fout; ze worden gecombineerd als wortel uit de som van de kwadraten.
/// Een oppervlak heeft twee richtingen met dezelfde schaal, dus tweemaal de relatieve fout.
public enum MeasureBand {
    public struct Inputs: Equatable {
        public var widthSource: PlaneWidthSource?
        public var levelAtCapture: Bool?
        public var focalSource: FacadePerspective.FocalSource?
        public var rectified: Bool
        public var hiddenFraction: Double?
        public init(widthSource: PlaneWidthSource?, levelAtCapture: Bool?, focalSource: FacadePerspective.FocalSource?, rectified: Bool, hiddenFraction: Double? = nil) {
            self.widthSource = widthSource; self.levelAtCapture = levelAtCapture; self.focalSource = focalSource; self.rectified = rectified; self.hiddenFraction = hiddenFraction
        }
    }

    /// Maatbron: BAG-omtrek wijkt doorgaans enkele decimeters af (±3%); een deur van 2,1 m is een aanname (2,0–2,4 m, ±8%); zelf gemeten ±2%.
    static func sourceError(_ s: PlaneWidthSource?) -> Double {
        switch s {
        case .deurAanname: return 0.08
        case .gebruiker: return 0.02
        case .bag, .none: return 0.03
        }
    }
    /// Fotohoek: recht gehouden ±1%, scheef ±4%, onbekend (fotobibliotheek) ±3%.
    static func levelError(_ l: Bool?) -> Double { l == true ? 0.01 : l == false ? 0.04 : 0.03 }
    /// Perspectief: rechtgetrokken met lens uit EXIF ±1%, geschat ±3%, aangenomen (rechte foto) ±2%; niet rechtgetrokken ±8%.
    static func perspectiveError(_ rectified: Bool, _ f: FacadePerspective.FocalSource?) -> Double {
        guard rectified else { return 0.08 }
        switch f {
        case .exif: return 0.01
        case .geschat: return 0.03
        case .aangenomen, .none: return 0.02
        }
    }

    public static func relative(_ i: Inputs) -> Double {
        let hidden = (i.hiddenFraction ?? 0) * 0.5
        let parts = [sourceError(i.widthSource), levelError(i.levelAtCapture), perspectiveError(i.rectified, i.focalSource), hidden]
        return sqrt(parts.reduce(0) { $0 + $1 * $1 })
    }

    /// Absolute ± voor een waarde: lengte × relatief, oppervlak × 2 × relatief.
    public static func band(_ value: Double, relative: Double, area: Bool) -> Double { abs(value) * relative * (area ? 2 : 1) }

    public enum DoorCheck: Equatable { case ok, tooLow, tooHigh }
    /// Gebruikelijke hoogte van een buitendeurkozijn: 2,0–2,4 m. Daarbuiten: controleer de maat of de hoeken.
    public static let doorRange = 2.0...2.4
    public static func doorCheck(_ heightM: Double) -> DoorCheck {
        heightM < doorRange.lowerBound ? .tooLow : heightM > doorRange.upperBound ? .tooHigh : .ok
    }
}
