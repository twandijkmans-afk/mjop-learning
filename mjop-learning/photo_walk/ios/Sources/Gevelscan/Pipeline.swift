import Foundation
import PhotoWalkCore

// De pijplijn: foto's + waarnemingen -> fotokwaliteit -> gevelvlak/dekking -> objectassociatie -> geometrie -> conditie -> uitkomstklassen
// -> inventaris per gevel en gebouw + gerichte vragen om aanvullende opnames. Puur en deterministisch: zelfde invoer = zelfde uitvoer.

public struct GevelscanInput {
    public struct Facade: Equatable { public var id: String; public var orientation: String?
        public init(id: String, orientation: String?) { self.id = id; self.orientation = orientation } }
    public var roundId: String
    public var facades: [Facade]
    public var photos: [PhotoCapture]
    public var sightings: [FrameSighting]                   // alleen meetellende waarnemingen (niet afgewezen, niet op uitgesloten foto's)
    public var constraints: AssociationConstraints
    public var userReviewedAllDuplicates: Bool
    public var userParts: [String: UserParts]               // per waarneming-id: door de gebruiker opgegeven draaiende/vaste delen
    public var userClasses: [String: ElementClass]          // per waarneming-id: door de gebruiker gekozen RAAM/DEUR
    public var detectors: [DetectorDescriptor]              // aanwezige elementherkenners
    public var conditionDetector: DetectorDescriptor?       // aanwezige gebrekenherkenner (nu: geen)
    public var defectDetections: [DefectDetection]
    public var validation: PipelineValidation
    public var config: GevelscanConfig
    public init(roundId: String, facades: [Facade], photos: [PhotoCapture], sightings: [FrameSighting], constraints: AssociationConstraints = .init(),
                userReviewedAllDuplicates: Bool = false, userParts: [String: UserParts] = [:], userClasses: [String: ElementClass] = [:],
                detectors: [DetectorDescriptor] = [.visionCandidates], conditionDetector: DetectorDescriptor? = nil, defectDetections: [DefectDetection] = [],
                validation: PipelineValidation = .current, config: GevelscanConfig = GevelscanConfig()) {
        self.roundId = roundId; self.facades = facades; self.photos = photos; self.sightings = sightings; self.constraints = constraints
        self.userReviewedAllDuplicates = userReviewedAllDuplicates; self.userParts = userParts; self.userClasses = userClasses; self.detectors = detectors
        self.conditionDetector = conditionDetector; self.defectDetections = defectDetections; self.validation = validation; self.config = config
    }
}

public struct GevelscanResult: Equatable {
    public var roundId: String
    public var pipelineVersion: String
    public var facades: [FacadeInventory]
    public var building: InventoryTotals
    public var photoAssessments: [PhotoAssessment]
    public var mismatchedPhotoIds: [String]                 // foto's die volgens hun gevelvlak bij een andere gevel lijken te horen
    public var association: AssociationResult
    public var recognition: RecognitionCapability
    public var validation: PipelineValidation
    public var requests: [CaptureRequest]                   // alle gerichte vragen, ontdubbeld
    public var objects: [InventoryObject] { facades.flatMap { $0.objects } }
    /// Mag dit resultaat zonder menselijke controle in het MJOP verwerkt worden? Alleen bij een gevalideerde pijplijn én alles betrouwbaar vastgesteld.
    public var autoProcessingAllowed: Bool {
        validation.autoProcessingAllowed && !facades.isEmpty && facades.allSatisfy { $0.completeness == .BETROUWBAAR_VASTGESTELD }
    }
}

public enum GevelscanPipeline {
    static let depthCodes: Set<String> = ["NO_DEPTH", "DEPTH_COVERAGE_LOW", "DEPTH_RANGE_EXCEEDED", "TRACKING_LOST", "NO_METRIC_SCALE", "NO_FACADE_PLANE", "FACADE_NOT_PLANAR",
                                          "FACADE_ONE_SIDED", "FRAMES_INCONSISTENT", "PLANE_NOISY", "MIXED_FACADE_DEPTH", "FACADE_NOT_REPRESENTATIVE"]
    static let angleCodes: Set<String> = ["OBLIQUE_ANGLE", "VIEWS_INCONSISTENT", "AMBIGUOUS_FACADE_PLANES", "FRAME_PLANE_UNDETERMINED", "FRAME_PLANE_INCONSISTENT"]
    static let framingCodes: Set<String> = ["CORNER_OUTSIDE_IMAGE", "CORNERS_OFF_PLANE", "CORNERS_NOT_ON_PLANE", "WRONG_CORNER_SELECTION", "CORNER_ORDER_INVALID"]

    public static func run(_ input: GevelscanInput) -> GevelscanResult {
        let cfg = input.config
        let photos = input.photos.filter { !$0.excluded }
        let photoById = Dictionary(uniqueKeysWithValues: photos.map { ($0.id, $0) })
        let sightings = input.sightings.filter { photoById[$0.photoId] != nil }
        let assessments = photos.sorted { $0.id < $1.id }.map { PhotoQualityRules.assess($0, cfg: cfg) }
        let flagsByPhoto = Dictionary(uniqueKeysWithValues: assessments.map { ($0.photoId, $0.flags) })
        let recognition = RecognitionCapability.summarize(input.detectors)
        let assoc = ObjectAssociator.associate(sightings, roundId: input.roundId, constraints: input.constraints, userReviewedAll: input.userReviewedAllDuplicates, cfg: cfg)
        let sightingById = Dictionary(uniqueKeysWithValues: sightings.map { ($0.id, $0) })

        var objects: [InventoryObject] = []
        var requests: [CaptureRequest] = assoc.requests
        for o in assoc.objects {
            let mine = o.sightingIds.compactMap { sightingById[$0] }
            // invoer van de gebruiker geldt alleen als ze eenduidig is (na samenvoegen kunnen twee waarnemingen elk een andere invoer hebben)
            let given = o.sightingIds.compactMap { input.userParts[$0] }
            let parts: UserParts? = Set(given.map { "\($0.operableParts)|\($0.fixedParts)" }).count == 1 ? given.first : nil
            let geo = FrameGeometryRules.compute(object: o, sightings: mine, photos: photoById, recognition: recognition, userParts: parts, validation: input.validation, cfg: cfg)
            let cond = ConditionRules.assess(object: o, sightings: mine, photoFlags: flagsByPhoto, detections: input.defectDetections, conditionDetector: input.conditionDetector, cfg: cfg)
            // afgesneden: alleen als het object op GEEN enkele foto volledig in beeld is
            let perSighting = mine.map { DetectionGeometry.truncatedSides($0.polygon, width: $0.intrinsics.width, height: $0.intrinsics.height, marginPx: cfg.truncationMarginPx) }
            let truncatedEverywhere = !perSighting.isEmpty && perSighting.allSatisfy { !$0.isEmpty }
            let truncatedBy: [ImageBorder] = truncatedEverywhere ? Array(Set(perSighting.flatMap { $0 })).sorted { $0.rawValue < $1.rawValue } : []
            let contour = OutcomeRules.contourEvidence(mine)
            let (outcome, why) = OutcomeRules.classify(geometry: geo, identity: o.identity, contour: contour, truncated: truncatedEverywhere, validation: input.validation)
            // klasse: gebruiker > getraind model > onbepaald kozijn
            var cls: ElementClass = .KOZIJN, clsOrigin: ValueOrigin = .DERIVED_SEGMENTATION_ON_MEASURED_PLANE
            let userCls = Set(o.sightingIds.compactMap { input.userClasses[$0] })
            let modelCls = Set(mine.filter { $0.detector.kind == .LEARNED_MODEL && $0.elementClass != .KOZIJN }.map { $0.elementClass })
            if userCls.count == 1, let c = userCls.first, c.isFrame { cls = c; clsOrigin = .USER_INPUT }
            else if modelCls.count == 1, let c = modelCls.first, c.isFrame { cls = c; clsOrigin = .MODEL_CLASSIFICATION }
            objects.append(InventoryObject(id: o.id, facadeId: o.facadeId, elementClass: cls, classOrigin: clsOrigin, outcome: outcome, outcomeReasons: Array(Set(why)).sorted(),
                                           identity: o.identity, identityReasons: o.identityReasons + (o.facadeConflict ? ["WAARNEMINGEN_BIJ_VERSCHILLENDE_GEVELS"] : []),
                                           possibleSameAs: o.possibleSameAs, contourEvidence: contour, geometry: geo, condition: cond.observations, photoIds: o.photoIds,
                                           sightingIds: o.sightingIds, detectors: Array(Set(mine.map { $0.detector })).sorted { $0.name < $1.name }, truncatedBy: truncatedBy))
            requests += cond.requests
            // gerichte vragen per object
            if truncatedEverywhere, let s = mine.first {
                let down = DetectionGeometry.worldDownBorder(pose: s.pose)
                requests.append(.init(kind: truncatedBy.contains(down) ? .ONDERZIJDE_GEVEL : .VOLLEDIG_OBJECT_IN_BEELD, facadeId: o.facadeId, objectId: o.id, reason: "OBJECT_AFGESNEDEN"))
            }
            if geo.status == .UNKNOWN {
                let codes = Set(geo.blockingCodes)
                if !codes.isDisjoint(with: depthCodes) || codes.isEmpty { requests.append(.init(kind: .BETERE_DIEPTE, facadeId: o.facadeId, objectId: o.id, reason: codes.intersection(depthCodes).sorted().first ?? "GEEN_METING")) }
                if !codes.isDisjoint(with: angleCodes) { requests.append(.init(kind: .ANDERE_HOEK, facadeId: o.facadeId, objectId: o.id, reason: codes.intersection(angleCodes).sorted().first!)) }
                if !codes.isDisjoint(with: framingCodes) && !truncatedEverywhere { requests.append(.init(kind: .VOLLEDIG_OBJECT_IN_BEELD, facadeId: o.facadeId, objectId: o.id, reason: codes.intersection(framingCodes).sorted().first!)) }
            } else if geo.status != .MEASURED && geo.scaleMethod != "REFERENCE_DISTANCE" && geo.independentViewpoints < 2 {
                requests.append(.init(kind: .ANDERE_HOEK, facadeId: o.facadeId, objectId: o.id, reason: "ENKEL_STANDPUNT"))
            }
            if geo.panes.contains(where: { $0.glareSuspected }) || (geo.advisoryCodes.contains("GLASS_DEPTH_UNRELIABLE") && geo.glassArea.value == nil && recognition.canRecognize(.GLASVLAK)) {
                requests.append(.init(kind: .GLAS_CONTROLEREN, facadeId: o.facadeId, objectId: o.id, reason: "SPIEGELING_IN_GLAS"))
            }
        }
        for a in assessments { requests += a.requests }

        // gevels: de opgegeven gevels + gevels waar objecten of foto's bij staan
        var facadeIds = input.facades.map { $0.id }
        for id in (photos.map { $0.facadeId } + objects.map { $0.facadeId }) where !facadeIds.contains(id) { facadeIds.append(id) }
        var facades: [FacadeInventory] = []
        for fid in facadeIds {
            let objs = objects.filter { $0.facadeId == fid }.sorted { $0.id < $1.id }
            let fphotos = photos.filter { $0.facadeId == fid }
            let cov = FacadeCoverageRules.evaluate(facadeId: fid, photos: photos, cfg: cfg)
            var freq = requests.filter { $0.facadeId == fid }
            if cov.flags.contains("GATEN_IN_DEKKING") { freq.append(.init(kind: .GEVEL_DEKKING, facadeId: fid, reason: "GATEN_IN_DEKKING")) }
            if cov.flags.contains("MEERDERE_SESSIES") && objs.count > 1 { freq.append(.init(kind: .ZELFDE_SCANSESSIE, facadeId: fid, reason: "MEERDERE_SESSIES")) }
            freq = dedupe(freq)
            var why: [String] = []
            var comp: Outcome = .BETROUWBAAR_VASTGESTELD
            if fphotos.isEmpty { comp = .NIET_VAST_TE_STELLEN; why.append("GEEN_FOTOS") }
            else if objs.isEmpty { comp = .NIET_VAST_TE_STELLEN; why.append("GEEN_OBJECTEN_HERKEND") }
            else {
                if !cov.determinable { why.append("DEKKING_ONBEKEND") }
                if cov.flags.contains("GATEN_IN_DEKKING") { why.append("GATEN_IN_DEKKING") }
                if objs.contains(where: { $0.outcome != .BETROUWBAAR_VASTGESTELD }) { why.append("OBJECTEN_NIET_BETROUWBAAR_VASTGESTELD") }
                if !freq.isEmpty { why.append("AANVULLENDE_OPNAMES_NODIG") }
                if !input.validation.autoProcessingAllowed { why += input.validation.blockingReasons }
                // De app kent de werkelijke omvang van de gevel niet: de dekking is relatief aan wat gefotografeerd is. Dat alle kozijnen van de
                // gevel zijn vastgelegd kan alleen de gebruiker verklaren (de bestaande verklaring "alle foto's nagelopen").
                if !input.userReviewedAllDuplicates { why.append("GEVELOMVANG_ONBEKEND") }
                if !why.isEmpty { comp = .VOORLOPIG_VASTGESTELD }
            }
            facades.append(FacadeInventory(facadeId: fid, orientation: input.facades.first { $0.id == fid }?.orientation, objects: objs,
                                           totals: OutcomeRules.totals(objs, recognition: recognition, validation: input.validation), coverage: cov,
                                           photoIds: fphotos.map { $0.id }.sorted(), requests: freq, completeness: comp, completenessReasons: Array(Set(why)).sorted()))
        }
        // gebouw: gevels zijn onderling alleen vergeleken als ze in dezelfde AR-sessie zijn gefotografeerd
        let withObjects = facades.filter { !$0.objects.isEmpty }
        var crossFacade: [String] = []
        if withObjects.count > 1 && !input.userReviewedAllDuplicates {
            let worlds = withObjects.map { f in Set(photos.filter { $0.facadeId == f.facadeId }.compactMap { $0.worldId }) }
            let common = worlds.dropFirst().reduce(worlds.first ?? []) { $0.intersection($1) }
            // per paar objecten nagegaan (associatie), plus de grove controle op een gedeelde scansessie
            if common.isEmpty || assoc.crossFacadeUnchecked { crossFacade = ["GEVELS_ONDERLING_NIET_VERGELEKEN"] }
        }
        var building = OutcomeRules.totals(objects, recognition: recognition, validation: input.validation)
        if !crossFacade.isEmpty {
            func cap(_ v: ScanValue) -> ScanValue { var c = v; c.missing = Array(Set(c.missing + crossFacade)).sorted(); if c.value != nil && c.outcome == .BETROUWBAAR_VASTGESTELD { c.outcome = .VOORLOPIG_VASTGESTELD }; return c }
            building = InventoryTotals(frameCount: cap(building.frameCount), frameAreaGross: cap(building.frameAreaGross), operableParts: cap(building.operableParts),
                                       fixedParts: cap(building.fixedParts), glassArea: cap(building.glassArea), doorCount: cap(building.doorCount))
        }
        let allRequests = dedupe(facades.flatMap { $0.requests } + requests.filter { $0.facadeId == nil })
        return GevelscanResult(roundId: input.roundId, pipelineVersion: GevelscanVersion.pipeline, facades: facades, building: building, photoAssessments: assessments,
                               mismatchedPhotoIds: FacadeRecognizer.mismatchedPhotos(photos, cfg: cfg), association: assoc, recognition: recognition, validation: input.validation,
                               requests: allRequests)
    }

    static func dedupe(_ r: [CaptureRequest]) -> [CaptureRequest] {
        var seen = Set<String>(), out: [CaptureRequest] = []
        for x in r {
            let k = [x.kind.rawValue, x.facadeId ?? "-", x.objectId ?? "-", x.photoId ?? "-"].joined(separator: "|")
            if seen.insert(k).inserted { out.append(x) }
        }
        return out.sorted { ($0.facadeId ?? "", $0.objectId ?? "", $0.photoId ?? "", $0.kind.rawValue) < ($1.facadeId ?? "", $1.objectId ?? "", $1.photoId ?? "", $1.kind.rawValue) }
    }
}
