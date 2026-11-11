import Foundation
import PhotoWalkCore

/// Gevelscanner 2.0 — gedeelde typen. Zie docs/gevelscanner_2.md.
///
/// Uitgangspunten (afgedwongen in code en tests):
/// * Onbekend blijft `nil`; er wordt nooit een waarde verzonnen of 0 ingevuld.
/// * Elke waarde draagt zijn HERKOMST (`ValueOrigin`): een glasoppervlak uit beeldsegmentatie is geen LiDAR-meting.
/// * Elke uitkomst is één van drie klassen (`Outcome`), met de redenen waarom een hogere klasse niet gehaald is.
/// * Alle drempels zijn `PROVISIONAL_UNVALIDATED`: niet getoetst op echte gevels. Zolang de pijplijn niet met referentiemetingen is
///   gevalideerd (`PipelineValidation`), is de hoogste klasse niet bereikbaar en wordt niets automatisch verwerkt.
public enum GevelscanVersion {
    public static let pipeline = "gevelscan-2.0.0"
    public static let captureAlgorithm = "capture-quality-1"
    public static let associationAlgorithm = "association-plane-iou-1"
    public static let geometryAlgorithm = "frame-geometry-1+level-a-v2"
    public static let conditionAlgorithm = "condition-rules-1"
    public static let thresholdsStatus = "PROVISIONAL_UNVALIDATED"
}

/// Herkenbare gevelelementen. Nederlandse benamingen zoals in het MJOP.
public enum ElementClass: String, Codable, CaseIterable, Sendable {
    case GEVELVLAK, KOZIJN, RAAM, DEUR, GLASVLAK, DRAAIEND_DEEL, VAST_DEEL, GEVELPANEEL, TUSSENSTIJL, TUSSENDORPEL, AANSLUITING, AFWERKING
    public var labelNL: String {
        switch self {
        case .GEVELVLAK: return "Gevelvlak"
        case .KOZIJN: return "Kozijn"
        case .RAAM: return "Raamkozijn"
        case .DEUR: return "Deurkozijn"
        case .GLASVLAK: return "Glasvlak"
        case .DRAAIEND_DEEL: return "Draaiend deel"
        case .VAST_DEEL: return "Vast deel"
        case .GEVELPANEEL: return "Gevelpaneel"
        case .TUSSENSTIJL: return "Tussenstijl"
        case .TUSSENDORPEL: return "Tussendorpel"
        case .AANSLUITING: return "Aansluiting (kit, lood, waterslag)"
        case .AFWERKING: return "Afwerking (schilderwerk)"
        }
    }
    /// Een kozijn-achtig object (telt als één kozijn in de inventaris).
    public var isFrame: Bool { self == .KOZIJN || self == .RAAM || self == .DEUR }
}

/// De drie soorten uitkomsten. Volgorde: beste eerst.
public enum Outcome: String, Codable, CaseIterable, Sendable {
    /// Voldoende bewijs voor automatische verwerking (alleen bereikbaar als de pijplijn gevalideerd is).
    case BETROUWBAAR_VASTGESTELD
    /// Er is een resultaat, maar aanvullende gegevens zijn nodig.
    case VOORLOPIG_VASTGESTELD
    /// Onvoldoende bewijs: geen waarde.
    case NIET_VAST_TE_STELLEN
    public var rank: Int { switch self { case .BETROUWBAAR_VASTGESTELD: return 0; case .VOORLOPIG_VASTGESTELD: return 1; case .NIET_VAST_TE_STELLEN: return 2 } }
    public static func worst(_ xs: [Outcome]) -> Outcome { xs.max { $0.rank < $1.rank } ?? .NIET_VAST_TE_STELLEN }
    public var labelNL: String {
        switch self {
        case .BETROUWBAAR_VASTGESTELD: return "Betrouwbaar vastgesteld"
        case .VOORLOPIG_VASTGESTELD: return "Voorlopig vastgesteld"
        case .NIET_VAST_TE_STELLEN: return "Niet vast te stellen"
        }
    }
}

/// Waar een waarde vandaan komt. Wordt nooit "opgewaardeerd": een afgeleide waarde blijft afgeleid.
public enum ValueOrigin: String, Codable, Sendable {
    /// Hoekstralen (camera-intrinsics + pose) gesneden met een vlak dat op LiDAR-diepte is gefit (bestaande niveau-A-meting).
    case LIDAR_PLANE_MEASUREMENT
    /// Schaal uit één ingevoerde referentiemaat (bestaande niveau-C-meting).
    case REFERENCE_DISTANCE
    /// Contour uit beeldherkenning, geprojecteerd op het gemeten kozijnvlak. Geen directe LiDAR-meting.
    case DERIVED_SEGMENTATION_ON_MEASURED_PLANE
    /// Berekend uit andere waarden (bv. oppervlak = breedte x hoogte, tussenstijl = tussenruimte van glasvlakken).
    case DERIVED_CALCULATION
    /// Geteld uit gekoppelde waarnemingen (objectassociatie).
    case COUNTED_FROM_ASSOCIATION
    /// Klasse van een getraind herkenningsmodel.
    case MODEL_CLASSIFICATION
    /// Door de gebruiker ingevoerd.
    case USER_INPUT
    case NONE
}

/// Eén getal met herkomst, onzekerheid en uitkomstklasse. `value == nil` betekent: niet vast te stellen (met in `missing` waarom).
public struct ScanValue: Equatable, Sendable {
    public var value: Double?
    public var unit: String                 // m | m2 | st
    public var sigma: Double?               // 1-sigma van een NIET-gevalideerd ruismodel; nil = geen onzekerheid bepaald
    public var origin: ValueOrigin
    public var outcome: Outcome
    public var missing: [String]            // codes: wat ontbreekt of waarom geen hogere klasse
    /// Som van wat wél bekend is; alleen informatief, nooit als totaal gebruiken.
    public var partial: Double?
    public init(value: Double?, unit: String, sigma: Double? = nil, origin: ValueOrigin, outcome: Outcome, missing: [String] = [], partial: Double? = nil) {
        self.value = value; self.unit = unit; self.sigma = sigma; self.origin = value == nil && partial == nil ? .NONE : origin
        self.outcome = value == nil ? .NIET_VAST_TE_STELLEN : outcome; self.missing = missing; self.partial = partial
    }
    public static func unknown(_ unit: String, _ missing: [String]) -> ScanValue {
        ScanValue(value: nil, unit: unit, origin: .NONE, outcome: .NIET_VAST_TE_STELLEN, missing: missing)
    }
}

/// Gerichte vraag om aanvullende opnames. Het systeem verzint niets, maar vraagt wat het nodig heeft.
public struct CaptureRequest: Equatable, Sendable {
    public enum Kind: String, Codable, CaseIterable, Sendable {
        case ANDERE_HOEK, VOLLEDIG_OBJECT_IN_BEELD, ONDERZIJDE_GEVEL, BETERE_DIEPTE, GLAS_CONTROLEREN, SCHERPERE_FOTO, GEVEL_DEKKING, ZELFDE_SCANSESSIE,
             OVERZICHTSFOTO, DICHTERBIJ
    }
    public var kind: Kind
    public var facadeId: String?
    public var objectId: String?
    public var photoId: String?
    public var reason: String               // code van de oorzaak
    public init(kind: Kind, facadeId: String? = nil, objectId: String? = nil, photoId: String? = nil, reason: String) {
        self.kind = kind; self.facadeId = facadeId; self.objectId = objectId; self.photoId = photoId; self.reason = reason
    }
    /// Aanwijzing in gewone taal voor de gebruiker.
    public var textNL: String {
        switch kind {
        case .ANDERE_HOEK: return "Maak nog een foto van dit kozijn vanaf een andere plek (een stap opzij is genoeg)."
        case .VOLLEDIG_OBJECT_IN_BEELD: return "Breng het hele kozijn in beeld, met rondom een stuk muur."
        case .ONDERZIJDE_GEVEL: return "Leg ook de onderzijde van de gevel vast: het kozijn loopt onder uit beeld."
        case .BETERE_DIEPTE: return "Maak de opname opnieuw op 1 tot 4 meter afstand en beweeg de telefoon rustig, zodat de dieptemeting beter wordt."
        case .GLAS_CONTROLEREN: return "Het glas spiegelt of is afgedekt. Maak een foto vanuit een hoek zonder spiegeling."
        case .SCHERPERE_FOTO: return "Deze foto is onscherp. Houd de telefoon stil en maak de foto opnieuw."
        case .GEVEL_DEKKING: return "Een deel van deze gevel is nog niet gefotografeerd. Maak foto's die elkaar een stukje overlappen."
        case .ZELFDE_SCANSESSIE: return "Foto's van deze gevel komen uit verschillende scanmomenten. Loop de gevel in één keer af, zodat dubbel tellen uitgesloten kan worden."
        case .OVERZICHTSFOTO: return "Maak één overzichtsfoto waarop deze kozijnen samen te zien zijn, zodat duidelijk is of het om hetzelfde kozijn gaat."
        case .DICHTERBIJ: return "Maak een foto van dichterbij, zodat details beoordeeld kunnen worden."
        }
    }
}

/// Is de pijplijn met echte referentiemetingen gevalideerd? Nu: nee. Dit is een bewuste schakelaar in code (geen instelling in de app):
/// pas na een veldvalidatie volgens docs/gevelscanner_2_meetplan.md mag dit wijzigen.
public struct PipelineValidation: Equatable, Sendable {
    public var geometryFieldValidated: Bool
    public var detectorValidated: Bool
    public init(geometryFieldValidated: Bool, detectorValidated: Bool) { self.geometryFieldValidated = geometryFieldValidated; self.detectorValidated = detectorValidated }
    /// De huidige stand: niets gevalideerd.
    public static let current = PipelineValidation(geometryFieldValidated: false, detectorValidated: false)
    public var blockingReasons: [String] {
        (geometryFieldValidated ? [] : ["GEOMETRIE_NIET_IN_HET_VELD_GEVALIDEERD"]) + (detectorValidated ? [] : ["HERKENNING_NIET_GEVALIDEERD"])
    }
    public var autoProcessingAllowed: Bool { blockingReasons.isEmpty }
}

/// Alle drempels van Gevelscanner 2.0. PROVISIONAL_UNVALIDATED: werkwaarden, geen acceptatiegrenzen voor nauwkeurigheid.
public struct GevelscanConfig: Sendable {
    // fotokwaliteit
    public var minSharpness = 35.0                  // variantie van de Laplaciaan op een verkleind grijsbeeld (0..255)
    public var maxOverexposedFraction = 0.25        // aandeel bijna-witte pixels in het hele beeld
    public var glareFractionInGlass = 0.30          // aandeel bijna-witte pixels binnen een glasvlak
    public var minDepthValidFraction = 0.35
    // gevelvlak en dekking
    public var facadePlaneThresholdM = 0.04, facadePlaneMinInlierRatio = 0.30, facadeMaxVertical = 0.35
    public var facadeSameNormalDeg = 15.0, facadeSameOffsetM = 0.40
    public var coverageCellM = 0.25, coverageMinFraction = 0.85
    public var truncationMarginPx = 6.0
    // associatie
    public var sameNormalDeg = 15.0, samePlaneOffsetM = 0.15
    public var strongIoU = 0.50, weakIoU = 0.15, strongSizeRatio = 1.30, weakCenterFactor = 0.5
    public var samePhotoMergeIoU = 0.80, samePhotoOverlap = 0.50
    // geometrie van de indeling
    public var paneClusterIoU = 0.50, paneInsideTol = 0.04, paneMaxMutualOverlap = 0.10
    public var paneAxisClusterTol = 0.5             // x (kleinste glasmaat): zelfde kolom/rij
    public var glassRecessRelativeError = 0.02      // glas ligt enkele cm achter het kozijnvlak: projectiefout, meegenomen in sigma
    public var cornerPixelSigmaPx = 1.5
    // conditie
    public var conditionMinPxPerM = 250.0           // beelddetail op het object om een gebrek te kunnen beoordelen
    public var defectVisibleMinScore = 0.80, defectIndicationMinScore = 0.40
    public init() {}
}

/// Deterministische FNV-1a (zelfde als de app gebruikt voor seeds); `hashValue` is per proces willekeurig.
public func gevelscanHash(_ s: String) -> UInt64 {
    var h: UInt64 = 0xcbf29ce484222325
    for b in s.utf8 { h = (h ^ UInt64(b)) &* 0x100000001b3 }
    return h
}

func round(_ x: Double, _ places: Int) -> Double {
    let p = pow(10.0, Double(places))
    return (x * p).rounded(.toNearestOrAwayFromZero) / p
}

func median(_ xs: [Double]) -> Double {
    let s = xs.sorted()
    guard !s.isEmpty else { return .nan }
    return s.count % 2 == 1 ? s[s.count / 2] : (s[s.count / 2 - 1] + s[s.count / 2]) / 2
}
