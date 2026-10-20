import Foundation

public enum Severity: String, Codable { case BLOCKING, ADVISORY }

public struct QualityFlag: Codable, Equatable {
    public var code: String
    public var severity: Severity
    public var detail: String?
    public var instruction_nl: String
    public init(code: String, severity: Severity, detail: String?, instruction_nl: String) {
        self.code = code; self.severity = severity; self.detail = detail; self.instruction_nl = instruction_nl
    }
}

/// Zelfde codes en instructies als photo_walk_core/quality.py (pariteit wordt bewaakt in ParityTests).
public enum Flags {
    static let table: [String: (Severity, String)] = [
        "TRACKING_LOST": (.BLOCKING, "AR-tracking was niet 'normal' tijdens dit beeld. Beweeg langzaam, richt op een gevel met textuur en herhaal de opname."),
        "NO_DEPTH": (.BLOCKING, "Geen dieptebeeld voor dit standpunt; gebruik een tweede standpunt (niveau B) of voer een referentiemaat in (niveau C)."),
        "CORNER_ORDER_INVALID": (.BLOCKING, "De vier hoeken vormen geen simpele vierhoek (verwisselde of dubbele hoeken). Tik de hoeken rond: linksboven, rechtsboven, rechtsonder, linksonder."),
        "CORNER_OUTSIDE_IMAGE": (.BLOCKING, "Een hoek ligt buiten het beeld. Sta verder weg zodat het hele kozijn in beeld is."),
        "DEPTH_COVERAGE_LOW": (.BLOCKING, "Te weinig geldige dieptepunten rond het kozijn. Ga dichterbij (binnen ca. 5 m), vermijd direct tegenlicht en scan de gevel rond het kozijn rustig."),
        "DEPTH_RANGE_EXCEEDED": (.BLOCKING, "Dieptepunten liggen buiten het bereik van de sensor. Ga dichterbij staan."),
        "MIXED_FACADE_DEPTH": (.BLOCKING, "Het gevelvlak rond het kozijn is niet vlak (verspringingen, balkon, begroeiing). Kies een standpunt met vrij zicht op de omringende gevel of voer een referentiemaat in."),
        "PLANE_NOISY": (.BLOCKING, "Het gevelvlak is te onrustig voor een betrouwbare vlakfit. Herhaal vanaf een ander standpunt."),
        "OBLIQUE_ANGLE": (.BLOCKING, "Te schuine kijkhoek op het kozijn. Sta meer recht voor het kozijn."),
        "CORNERS_NOT_ON_PLANE": (.BLOCKING, "Een hoekstraal raakt het gevelvlak niet. Controleer de hoekselectie."),
        "WRONG_CORNER_SELECTION": (.BLOCKING, "De gekozen hoeken vormen geen rechthoek op het gevelvlak. Corrigeer de hoeken (buitenhoeken van het kozijn)."),
        "DIMENSION_OUT_OF_RANGE": (.BLOCKING, "Berekende maat valt buiten 0,10-10 m; controleer hoeken en schaal."),
        "NO_METRIC_SCALE": (.BLOCKING, "Geen betrouwbare metrische schaal. Voer een referentieafstand in tussen twee punten op het kozijnvlak."),
        "REFERENCE_PLANE_MISMATCH": (.BLOCKING, "De referentie ligt niet op hetzelfde vlak als het kozijn. Geef een nieuwe referentie op het gevelvlak van dit kozijn."),
        "REFERENCE_INVALID": (.BLOCKING, "De referentie is ongeldig (afstand <= 0 of punten vallen samen)."),
        "RECT_ASSUMPTION_VIOLATED": (.BLOCKING, "De hoeken zijn niet consistent met een rechthoek en de cameralenzen. Corrigeer de hoeken."),
        "VIEWS_INCONSISTENT": (.BLOCKING, "Metingen vanuit verschillende standpunten komen niet overeen. Herhaal de opname; alle waarnemingen zijn bewaard."),
        "GLASS_DEPTH_UNRELIABLE": (.ADVISORY, "Diepte in het glas is onbetrouwbaar (reflectie of ontbrekende data); alleen de omringende gevel is gebruikt. Controleer de hoeken visueel."),
        "CORNER_DEPTH_MISMATCH": (.ADVISORY, "Diepte op een hoek wijkt af van het gevelvlak (verdiept kozijn of verkeerd gekozen hoek). Controleer de hoeken."),
        "FACADE_NOT_VERTICAL": (.ADVISORY, "Het vlak is niet verticaal; controleer of het een gevel is."),
        "SINGLE_VIEWPOINT": (.ADVISORY, "Slechts een standpunt; maak een tweede opname vanaf een ander standpunt voor een consistentiecontrole."),
        "COPLANARITY_ASSUMED": (.ADVISORY, "Het kozijn is op de referentieschaal gezet onder de aanname dat het in hetzelfde vlak ligt. Controleer dit."),
        "REFERENCE_UNCERTAINTY_NOT_PROVIDED": (.ADVISORY, "Bij de referentie is geen eigen onzekerheid opgegeven; die is niet in de onzekerheid meegenomen."),
        "AUTO_DETECTED_UNCONFIRMED": (.ADVISORY, "Hoeken komen van een automatische kandidaatdetector en zijn niet bevestigd; controleer ze (zoom in) of corrigeer ze."),
        "MANUAL_CORNERS": (.ADVISORY, "Hoeken zijn handmatig geselecteerd (semi-automatisch)."),
        "HUMAN_CORRECTED_CORNERS": (.ADVISORY, "Hoeken zijn door een mens gecorrigeerd; herberekend zonder brondata te overschrijven."),
        "OBSTRUCTION_REPORTED": (.ADVISORY, "Gebruiker meldt begroeiing of obstakel voor het kozijn; hoeken kunnen onjuist zijn."),
        "NO_FACADE_PLANE": (.BLOCKING, "Rond het kozijn is geen bruikbaar plat wandvlak gevonden. Zorg dat een stuk effen muur naast, boven en onder het kozijn in beeld is en sta recht op de gevel."),
        "FACADE_NOT_PLANAR": (.BLOCKING, "Het oppervlak rond het kozijn is te ruw of onregelmatig (reliëf, begroeiing, rommel) voor een betrouwbare vlakfit. Kies een standpunt met meer vlakke muur in beeld."),
        "AMBIGUOUS_FACADE_PLANES": (.BLOCKING, "Rond het kozijn liggen meerdere even grote vlakken op verschillende diepte (verspringende gevel). Fotografeer vanaf een standpunt waar één wandvlak duidelijk om het kozijn zit, of gebruik een referentiemaat."),
        "FACADE_ONE_SIDED": (.BLOCKING, "Het wandvlak is maar aan één of twee kanten van het kozijn gezien. Houd het kozijn met wand aan alle kanten in beeld."),
        "FRAME_PLANE_UNDETERMINED": (.BLOCKING, "De terugligging van het kozijn t.o.v. de wand is niet betrouwbaar te bepalen (te weinig diepte op de kozijnrand). Beweeg langzaam iets naar links en rechts en maak de foto opnieuw, of voer een gemeten referentiemaat in."),
        "FRAME_PLANE_INCONSISTENT": (.BLOCKING, "De kozijnrand ligt links/rechts/boven op verschillende diepte. Controleer of het kader precies om de buitenrand van het kozijn ligt."),
        "CORNERS_OFF_PLANE": (.BLOCKING, "Drie of vier hoeken liggen niet op het gekozen vlak (de gemeten diepte wijkt af). Controleer of het kader om de buitenrand van het kozijn ligt."),
        "FRAMES_INCONSISTENT": (.BLOCKING, "De dieptemetingen uit de korte beweging komen niet overeen (tracking-drift of bewegend object). Houd de telefoon rustig en herhaal de opname."),
        "FRAME_OFFSET_FROM_CORNER_DEPTH": (.ADVISORY, "De terugligging van het kozijn is afgeleid uit de diepte op de hoeken; dat is minder betrouwbaar. Beweeg iets zijwaarts voor een betere meting."),
        "LIMITED_SIDE_COVERAGE": (.ADVISORY, "Het wandvlak is maar aan twee kanten van het kozijn gezien. Houd wand aan alle vier de kanten in beeld voor een betere meting."),
        "DEPTH_MISALIGNMENT_SUSPECTED": (.ADVISORY, "De dieptekaart lijkt verschoven t.o.v. het beeld (randen vallen niet samen). Herhaal de opname; houd de telefoon stil tijdens het richten."),
        "QUAD_LARGER_THAN_OPENING": (.ADVISORY, "Het kader lijkt groter dan het kozijn (de gemeten dieptesprong ligt ver binnen het kader). Trek de hoeken naar de buitenrand van het kozijn."),
        "QUAD_INSIDE_OPENING": (.ADVISORY, "Het kader lijkt binnen het kozijn te liggen (buiten het kader ligt nog dieper glas of een dieptesprong naar het profiel). Trek de hoeken naar de buitenrand van het kozijn."),
        "REFERENCE_USER_ESTIMATE": (.ADVISORY, "De referentiemaat is door jou geschat, niet gemeten. De maat is daarom een schatting zonder metrische bevestiging; meet de referentie met duimstok of laser."),
    ]
    public static func make(_ code: String, _ detail: String? = nil) -> QualityFlag {
        let (sev, instr) = table[code] ?? (.BLOCKING, "Onbekende kwaliteitscode")
        return QualityFlag(code: code, severity: sev, detail: detail, instruction_nl: instr)
    }
}

public func hasBlocking(_ f: [QualityFlag]) -> Bool { f.contains { $0.severity == .BLOCKING } }

/// Alle drempels zijn PROVISIONAL_UNVALIDATED (zelfde waarden als photo_walk_core/config.py).
public struct Config {
    public var minDimM = 0.10, maxDimM = 10.0
    public var cornerPixelSigmaPx = 1.5, depthNoiseFloorM = 0.01
    public var planeEffectiveSamplesCap = 50, mcSamples = 100
    public var depthMinRangeM = 0.3, depthMaxRangeM = 5.0
    public var annulusInnerScale = 1.08, annulusOuterScale = 1.8
    public var annulusMinPoints = 60, annulusMinValidFraction = 0.35
    public var planeRansacThresholdM = 0.02, planeRansacIterations = 200
    public var planeMinInlierRatio = 0.6, planeMaxRmsM = 0.02
    public var minIncidenceCos = 0.35
    public var rectAngleTolDeg = 6.0, rectEdgeRatioTol = 0.05
    public var cornerDepthTolM = 0.08, cornerDepthBlockM = 0.25
    public var glassInnerScale = 0.85, glassMinValidFraction = 0.5, glassBeyondPlaneM = 0.30, glassMaxBeyondFraction = 0.25
    public var consistencyK = 3.0
    public var refPlaneTolM = 0.05, refOrthogonalityTol = 0.08
    // niveau A v2 (PROVISIONAL; zelfde waarden als config.py)
    public var lidarSigma0M = 0.004, lidarSigma1PerM = 0.004, reliefTolM = 0.012, thrK = 2.5
    public var ringInnerScale = 1.06, ringOuterScale = 1.6, bandLoScale = 0.88, bandHiScale = 0.985, bandClusterMinShare = 0.35, glassScale = 0.70
    public var maxPlanes = 3, minPlanePoints = 40, planeMinFraction = 0.06, ransacIterationsV2 = 150, maxRansacPoints = 2500
    public var facadeMinFacing = 0.35, facadeMaxVertical = 0.35, facadeSupportMin = 0.5, facadeRmsK = 1.5, ambiguityRatio = 0.6
    public var sideMinPoints = 15, frameSearchM = 0.35, frameSideMinPoints = 12, frameGroupTolK = 1.5, flushTolK = 1.2
    public var cornerTolK = 2.0, cornersContradictBlock = 3
    public var maxSupportFrames = 5, minBaselineM = 0.02, minRotationDeg = 1.5
    public var frameTolRel = 0.03, frameTolAbsM = 0.01, frameNormalDeg = 4.0
    public init() {}
}
