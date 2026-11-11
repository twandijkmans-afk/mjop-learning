import Foundation
import PhotoWalkCore

// Onderdeel B — herkenning. Deze laag beschrijft WAT een herkenner levert en WELKE herkenner het was. De herkenners zelf (Apple Vision,
// een eventueel Core ML-model) draaien in de app; hier staat het model-onafhankelijke contract plus de eerlijke boekhouding van wat
// met de aanwezige herkenners wél en níet herkend kan worden.

/// Beschrijving van een herkenner, zodat elk resultaat herleidbaar is naar methode en versie.
public struct DetectorDescriptor: Codable, Equatable, Hashable, Sendable {
    public enum Kind: String, Codable, Sendable {
        /// Getraind model (bv. Core ML) dat elementklassen levert.
        case LEARNED_MODEL
        /// Algemene vorm-/randzoeker (Apple Vision-rechthoeken en -contouren). GEEN kozijnherkenning: levert alleen kandidaat-vierhoeken.
        case GEOMETRIC_CANDIDATE
        case USER
    }
    public var name: String
    public var version: String
    public var kind: Kind
    /// Is deze herkenner op echte gevels gevalideerd? Voor alles wat nu in de app zit: nee.
    public var validated: Bool
    public var classes: [ElementClass]
    public init(name: String, version: String, kind: Kind, validated: Bool, classes: [ElementClass]) {
        self.name = name; self.version = version; self.kind = kind; self.validated = validated; self.classes = classes
    }
    public static let user = DetectorDescriptor(name: "gebruiker", version: "1", kind: .USER, validated: true, classes: ElementClass.allCases)
    /// De herkenning die nu in de app aanwezig is: Vision-kandidaten, geordend door `ContourOrganizer` tot buitencontour + glasvlakken.
    public static let visionCandidates = DetectorDescriptor(name: "apple-vision-rectangles+contours/ContourOrganizer", version: "facade-composition-1",
                                                            kind: .GEOMETRIC_CANDIDATE, validated: false, classes: [.KOZIJN, .GLASVLAK])
}

/// Eén herkend element op één foto.
public struct ElementDetection: Equatable {
    public var id: String
    public var photoId: String
    public var elementClass: ElementClass
    public var polygon: [Pixel]             // pixels van de originele foto
    public var score: Double?               // score van de herkenner (geen kans, niet gekalibreerd)
    public var detector: DetectorDescriptor
    public var parentId: String?            // bv. glasvlak -> kozijn
    public init(id: String, photoId: String, elementClass: ElementClass, polygon: [Pixel], score: Double?, detector: DetectorDescriptor, parentId: String? = nil) {
        self.id = id; self.photoId = photoId; self.elementClass = elementClass; self.polygon = polygon; self.score = score; self.detector = detector; self.parentId = parentId
    }
}

/// Wat kan er met de aanwezige herkenners herkend worden, en wat ontbreekt? Voor de UI, het contract en het eindrapport.
public struct RecognitionCapability: Equatable {
    public var detectors: [DetectorDescriptor]
    public var recognizable: [ElementClass]                 // klassen waarvoor een herkenner aanwezig is
    public var learnedClasses: [ElementClass]               // klassen die een GETRAIND model levert
    public var notRecognizable: [ElementClass]              // geen herkenner aanwezig
    public var derivedByGeometry: [ElementClass]            // volgt uit de geometrie van andere elementen (geen herkenning nodig)
    public var anyValidated: Bool

    public static func summarize(_ detectors: [DetectorDescriptor]) -> RecognitionCapability {
        let auto = detectors.filter { $0.kind != .USER }
        let rec = Set(auto.flatMap { $0.classes })
        let learned = Set(auto.filter { $0.kind == .LEARNED_MODEL }.flatMap { $0.classes })
        // gevelvlak: uit de LiDAR-vlakfit; tussenstijl/-dorpel: uit de tussenruimte van glasvlakken
        let derived: [ElementClass] = [.GEVELVLAK, .TUSSENSTIJL, .TUSSENDORPEL]
        let missing = ElementClass.allCases.filter { !rec.contains($0) && !derived.contains($0) }
        return RecognitionCapability(detectors: detectors, recognizable: ElementClass.allCases.filter { rec.contains($0) }, learnedClasses: ElementClass.allCases.filter { learned.contains($0) },
                                     notRecognizable: missing, derivedByGeometry: derived, anyValidated: auto.contains { $0.validated })
    }
    public func canRecognize(_ c: ElementClass) -> Bool { recognizable.contains(c) }
}

public enum ImageBorder: String, Codable, Sendable { case LEFT, RIGHT, TOP, BOTTOM }

public enum DetectionGeometry {
    /// Welke beeldranden raakt een contour? Een afgesneden object kan niet volledig gemeten worden.
    public static func truncatedSides(_ polygon: [Pixel], width: Int, height: Int, marginPx: Double) -> [ImageBorder] {
        guard !polygon.isEmpty else { return [] }
        let b = polygonBounds(polygon)
        var out: [ImageBorder] = []
        if b.minU <= marginPx { out.append(.LEFT) }
        if b.maxU >= Double(width) - marginPx { out.append(.RIGHT) }
        if b.minV <= marginPx { out.append(.TOP) }
        if b.maxV >= Double(height) - marginPx { out.append(.BOTTOM) }
        return out
    }

    /// Welke beeldrand is "onder" in de wereld? De foto's zijn in sensor-oriëntatie opgeslagen (meestal liggend), dus "onder" is niet altijd v = max.
    public static func worldDownBorder(pose: Pose) -> ImageBorder {
        let downCam = pose.rotateInverse(worldUp * -1)          // wereld-omlaag in camera-assen (x rechts, y omlaag in beeld)
        if abs(downCam.x) > abs(downCam.y) { return downCam.x > 0 ? .RIGHT : .LEFT }
        return downCam.y > 0 ? .BOTTOM : .TOP
    }
}
