import Foundation
import PhotoWalkCore

// Onderdeel E — visuele conditie-waarnemingen.
//
// Wat deze laag WEL doet: waarnemingen van een (toekomstige) gebrekenherkenner ordenen in drie soorten, koppelen aan object, foto en plek,
// en eerlijk vastleggen wanneer iets niet te beoordelen is.
// Wat deze laag NIET doet: zelf gebreken "zien" (er is geen getraind gebrekenmodel in dit project), verborgen gebreken afleiden, of een
// NEN 2767-conditiescore geven. Een visuele AI-waarneming is geen NEN 2767-inspectie; het veld daarvoor bestaat bewust niet.

/// Uitbreidbare lijst van zichtbare gebreken (rawValue = stabiele code; nieuwe categorieën kunnen worden toegevoegd zonder contractwijziging,
/// want het contract draagt de code als tekst).
public struct DefectCategory: RawRepresentable, Hashable, Codable, Sendable {
    public var rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }
    public static let houtrotZichtbaar = DefectCategory(rawValue: "HOUTROT_ZICHTBAAR")
    public static let verfBeschadigd = DefectCategory(rawValue: "VERFLAAG_BESCHADIGD")
    public static let afbladderend = DefectCategory(rawValue: "SCHILDERWERK_AFBLADDEREND")
    public static let corrosie = DefectCategory(rawValue: "CORROSIE")
    public static let kitnaad = DefectCategory(rawValue: "KITNAAD_BESCHADIGD")
    public static let scheur = DefectCategory(rawValue: "SCHEUR")
    public static let glasschade = DefectCategory(rawValue: "GLAS_BESCHADIGD")
    public static let vervorming = DefectCategory(rawValue: "VERVORMING_ZICHTBAAR")
    public static let verouderdeAfwerking = DefectCategory(rawValue: "AFWERKING_VEROUDERD")
    public static let known: [DefectCategory] = [.houtrotZichtbaar, .verfBeschadigd, .afbladderend, .corrosie, .kitnaad, .scheur, .glasschade, .vervorming, .verouderdeAfwerking]
    public var labelNL: String {
        switch self {
        case .houtrotZichtbaar: return "Zichtbare houtrot"
        case .verfBeschadigd: return "Beschadigde verflaag"
        case .afbladderend: return "Afbladderend schilderwerk"
        case .corrosie: return "Corrosie (roest)"
        case .kitnaad: return "Beschadigde kitnaad"
        case .scheur: return "Scheur"
        case .glasschade: return "Beschadigd glas"
        case .vervorming: return "Zichtbare vervorming"
        case .verouderdeAfwerking: return "Verouderde afwerking"
        default: return rawValue
        }
    }
}

public enum ConditionKind: String, Codable, Sendable {
    /// Een daadwerkelijk zichtbaar gebrek (hoge modelscore op voldoende beelddetail).
    case ZICHTBAAR_GEBREK
    /// Een mogelijke indicatie: nader bekijken.
    case MOGELIJKE_INDICATIE
    /// Dit onderdeel kon niet beoordeeld worden (met reden).
    case NIET_BEOORDEELBAAR
}

/// Ruwe uitvoer van een gebrekenherkenner voor één plek op één foto.
public struct DefectDetection: Equatable {
    public var id: String
    public var photoId: String
    public var category: DefectCategory
    public var region: [Pixel]
    public var score: Double
    public var detector: DetectorDescriptor
    public init(id: String, photoId: String, category: DefectCategory, region: [Pixel], score: Double, detector: DetectorDescriptor) {
        self.id = id; self.photoId = photoId; self.category = category; self.region = region; self.score = score; self.detector = detector
    }
}

public struct ConditionObservation: Equatable {
    public var id: String
    public var objectId: String
    public var kind: ConditionKind
    public var category: DefectCategory?            // nil bij NIET_BEOORDEELBAAR
    public var photoId: String?
    public var region: [Pixel]?                     // plek op de bronfoto
    public var score: Double?                       // modelscore (niet gekalibreerd, geen kans)
    public var detector: DetectorDescriptor?
    public var reasons: [String]                    // bv. GEEN_GEBREKENMODEL, TE_WEINIG_BEELDDETAIL, ONSCHERP, SPIEGELING
}

public struct ConditionResult: Equatable {
    public var observations: [ConditionObservation]
    public var requests: [CaptureRequest]
    /// Formele NEN 2767-conditiescore: bewust niet aanwezig. Een visuele waarneming is geen NEN 2767-inspectie.
    public let nen2767ConditionScore: Int? = nil
}

public enum ConditionRules {
    /// Beelddetail (pixels per meter) op een gemeten object in een foto. nil = niet te bepalen.
    public static func pixelsPerMeter(_ s: FrameSighting) -> Double? {
        guard let sp = s.spatial else { return nil }
        let b = polygonBounds(s.polygon)
        return max((b.maxU - b.minU) / max(sp.width, 1e-9), (b.maxV - b.minV) / max(sp.height, 1e-9))
    }

    public static func assess(object: PhysicalObject, sightings: [FrameSighting], photoFlags: [String: [String]], detections: [DefectDetection], conditionDetector: DetectorDescriptor?,
                              cfg: GevelscanConfig = GevelscanConfig()) -> ConditionResult {
        let mine = sightings.filter { object.sightingIds.contains($0.id) }.sorted { $0.id < $1.id }
        var out: [ConditionObservation] = [], req: [CaptureRequest] = []
        func notAssessable(_ reasons: [String]) -> ConditionObservation {
            ConditionObservation(id: "\(object.id)-C0", objectId: object.id, kind: .NIET_BEOORDEELBAAR, category: nil, photoId: nil, region: nil, score: nil, detector: conditionDetector, reasons: reasons)
        }
        guard let det = conditionDetector else { return ConditionResult(observations: [notAssessable(["GEEN_GEBREKENMODEL"])], requests: []) }
        // welke foto's hebben genoeg detail en kwaliteit om dit object te beoordelen?
        var usable: [FrameSighting] = [], why = Set<String>()
        for s in mine {
            let flags = photoFlags[s.photoId] ?? []
            if flags.contains("ONSCHERP") { why.insert("ONSCHERP"); continue }
            if flags.contains("TE_DONKER") { why.insert("TE_DONKER"); continue }
            guard let ppm = pixelsPerMeter(s) else { why.insert("GEEN_SCHAAL_OP_FOTO"); continue }
            if ppm < cfg.conditionMinPxPerM { why.insert("TE_WEINIG_BEELDDETAIL"); continue }
            usable.append(s)
        }
        if usable.isEmpty {
            if why.contains("TE_WEINIG_BEELDDETAIL") || why.contains("GEEN_SCHAAL_OP_FOTO") { req.append(.init(kind: .DICHTERBIJ, facadeId: object.facadeId, objectId: object.id, reason: "TE_WEINIG_BEELDDETAIL")) }
            if why.contains("ONSCHERP") { req.append(.init(kind: .SCHERPERE_FOTO, facadeId: object.facadeId, objectId: object.id, reason: "ONSCHERP")) }
            return ConditionResult(observations: [notAssessable(why.sorted())], requests: req)
        }
        var k = 0
        for s in usable {
            for d in detections.filter({ $0.photoId == s.photoId }).sorted(by: { $0.id < $1.id }) {
                // het gebrek moet op dit object liggen (middelpunt binnen de buitencontour)
                guard inConvexPolygon(polygonCentroid(d.region), s.polygon), d.score >= cfg.defectIndicationMinScore else { continue }
                k += 1
                // een niet-gevalideerd model levert hoogstens een indicatie: "zichtbaar gebrek" vraagt een gevalideerde herkenner
                let kind: ConditionKind = (d.score >= cfg.defectVisibleMinScore && d.detector.validated) ? .ZICHTBAAR_GEBREK : .MOGELIJKE_INDICATIE
                out.append(ConditionObservation(id: "\(object.id)-C\(k)", objectId: object.id, kind: kind, category: d.category, photoId: d.photoId, region: d.region,
                                                score: round(d.score, 3), detector: d.detector, reasons: d.detector.validated ? [] : ["MODEL_NIET_GEVALIDEERD"]))
            }
        }
        _ = det
        return ConditionResult(observations: out, requests: req)
    }
}
