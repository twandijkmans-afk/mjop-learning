import Foundation
import PhotoWalkCore

// Uitkomstklassen (sectie 6) en de inventaris per gevel en gebouw.

/// Waarop de zekerheid van de BUITENCONTOUR berust.
public enum ContourEvidence: String, Codable, Sendable {
    /// Door de gebruiker getekend of bevestigd.
    case USER_CONFIRMED
    /// Automatisch, en door onafhankelijk bewijs gesteund: op >= 2 foto's een diepte-sprong precies op de kozijnrand (terugliggend of uitstekend
    /// kozijn), geen aanwijzing dat het kader te groot of te klein is, en de contour omsluit herkende glasvlakken.
    case AUTO_CORROBORATED
    /// Automatisch herkend zonder zulk bewijs (bv. een vlak in de gevel liggend kozijn, of een losse rechthoek).
    case AUTO_UNCONFIRMED
}

public struct InventoryObject: Equatable {
    public var id: String
    public var facadeId: String
    public var elementClass: ElementClass
    public var classOrigin: ValueOrigin
    public var outcome: Outcome
    public var outcomeReasons: [String]             // waarom niet (hoger) vastgesteld
    public var identity: PhysicalObject.Identity
    public var identityReasons: [String]
    public var possibleSameAs: [String]
    public var contourEvidence: ContourEvidence
    public var geometry: FrameGeometry
    public var condition: [ConditionObservation]
    public var photoIds: [String]
    public var sightingIds: [String]
    public var detectors: [DetectorDescriptor]
    public var truncatedBy: [ImageBorder]           // op ALLE foto's afgesneden door deze beeldrand(en)
    /// Telt dit object mee als één kozijn? Niet zolang het mogelijk hetzelfde is als een ander object.
    public var countsAsFrame: Bool { identity != .UNCERTAIN }
}

/// Zes gescheiden hoeveelheden. Ze worden NOOIT gemengd of in elkaar omgerekend.
public struct InventoryTotals: Equatable {
    public var frameCount: ScanValue                // aantal kozijnen (st)
    public var frameAreaGross: ScanValue            // totale bruto kozijnoppervlakte (m2), buitenmaat b x h
    public var operableParts: ScanValue             // aantal draaiende delen (st)
    public var fixedParts: ScanValue                // aantal vaste delen (st)
    public var glassArea: ScanValue                 // totale zichtbare glasoppervlakte (m2)
    public var doorCount: ScanValue                 // aantal deurkozijnen (st); alleen met een model of gebruikersinvoer
}

public struct FacadeInventory: Equatable {
    public var facadeId: String
    public var orientation: String?
    public var objects: [InventoryObject]
    public var totals: InventoryTotals
    public var coverage: FacadeCoverage
    public var photoIds: [String]
    public var requests: [CaptureRequest]
    public var completeness: Outcome                // volledigheid van de inventaris van deze gevel
    public var completenessReasons: [String]
}

public enum OutcomeRules {
    public static func contourEvidence(_ sightings: [FrameSighting]) -> ContourEvidence {
        if sightings.contains(where: { $0.contourUserConfirmed }) { return .USER_CONFIRMED }
        func corroborated(_ s: FrameSighting) -> Bool {
            guard let r = s.result, r.ok, r.level == .A, s.evidence == .NESTED_PANES, !s.panes.isEmpty else { return false }
            if r.flags.contains(where: { $0.code == "QUAD_LARGER_THAN_OPENING" || $0.code == "QUAD_INSIDE_OPENING" }) { return false }
            guard let fp = r.diag["frame_plane"] as? [String: Any], let mode = (fp["final_mode"] ?? fp["mode"]) as? String else { return false }
            return mode == "RECESSED" || mode == "PROTRUDING"
        }
        let ok = sightings.filter(corroborated)
        let independent = Viewpoints.independentPhotoCount(ok.map { .init(keyframeId: $0.photoId, position: $0.pose.t) })
        return independent >= 2 ? .AUTO_CORROBORATED : .AUTO_UNCONFIRMED
    }

    /// Uitkomstklasse van één object. De hoogste klasse vraagt: MEASURED-maat, eenduidige identiteit, zekere buitencontour, volledig in beeld
    /// én een gevalideerde pijplijn. Ontbreekt alleen dat laatste, dan is de uitkomst VOORLOPIG met precies die reden.
    public static func classify(geometry g: FrameGeometry, identity: PhysicalObject.Identity, contour: ContourEvidence, truncated: Bool, validation: PipelineValidation)
        -> (Outcome, [String]) {
        if g.status == .UNKNOWN || g.area.value == nil { return (.NIET_VAST_TE_STELLEN, ["GEEN_MAAT"] + g.blockingCodes + (truncated ? ["OBJECT_AFGESNEDEN"] : [])) }
        var why: [String] = []
        if g.status != .MEASURED { why += g.width.missing.isEmpty ? ["MAAT_NIET_GEMETEN_UIT_TWEE_STANDPUNTEN"] : g.width.missing }
        if identity == .UNCERTAIN { why.append("IDENTITEIT_ONZEKER") }
        if identity == .UNCHECKED { why.append("DUBBELTELLING_NIET_UITGESLOTEN") }
        if contour == .AUTO_UNCONFIRMED { why.append("BUITENCONTOUR_NIET_BEVESTIGD") }
        if truncated { why.append("OBJECT_AFGESNEDEN") }
        if why.isEmpty { why += validation.blockingReasons }
        return (why.isEmpty ? .BETROUWBAAR_VASTGESTELD : .VOORLOPIG_VASTGESTELD, why)
    }

    /// Som over objecten. Een totaal bestaat alleen als ELK meetellend object de waarde heeft en niets dubbel geteld kan zijn; anders nil
    /// (met een informatieve deelsom als dubbeltelling is uitgesloten). De klasse van het totaal is die van het zwakste onderdeel.
    static func total(_ objects: [InventoryObject], unit: String, origin: ValueOrigin, value: (InventoryObject) -> ScanValue, extraMissing: [String] = []) -> ScanValue {
        if objects.isEmpty { return .unknown(unit, ["GEEN_OBJECTEN"] + extraMissing) }
        let identityOpen = objects.contains { $0.identity == .UNCERTAIN }
        let unchecked = objects.contains { $0.identity == .UNCHECKED }
        let vals = objects.map(value)
        let known = vals.compactMap { $0.value }
        var missing = extraMissing
        if identityOpen { missing.append("MOGELIJK_DUBBEL_GETELD") }
        if unchecked { missing.append("DUBBELTELLING_NIET_UITGESLOTEN") }
        if known.count < vals.count { missing.append("NIET_ALLE_OBJECTEN_BEPAALD") ; missing += Array(Set(vals.filter { $0.value == nil }.flatMap { $0.missing })).sorted() }
        if identityOpen || unchecked { return ScanValue(value: nil, unit: unit, origin: .NONE, outcome: .NIET_VAST_TE_STELLEN, missing: missing) }
        let sum = round(known.reduce(0, +), unit == "st" ? 0 : 3)
        if known.count < vals.count { return ScanValue(value: nil, unit: unit, origin: origin, outcome: .NIET_VAST_TE_STELLEN, missing: missing, partial: known.isEmpty ? nil : sum) }
        let sigmas = vals.compactMap { $0.sigma }
        let sigma: Double? = (unit != "st" && sigmas.count == vals.count) ? round(sigmas.reduce(0) { $0 + $1 * $1 }.squareRoot(), 4) : nil
        let oc = Outcome.worst(vals.map { $0.outcome })
        return ScanValue(value: sum, unit: unit, sigma: sigma, origin: origin, outcome: oc, missing: Array(Set(vals.flatMap { $0.missing } + missing)).sorted())
    }

    /// Een som over objecten erft de onzekerheid van de objecttelling (bv. niet-gevalideerde associatie of onbevestigde contouren).
    static func notBetterThanCount(_ v: ScanValue, _ count: ScanValue) -> ScanValue {
        guard v.value != nil, count.outcome.rank > v.outcome.rank else { return v }
        var c = v; c.outcome = count.outcome == .NIET_VAST_TE_STELLEN ? .VOORLOPIG_VASTGESTELD : count.outcome
        c.missing = Array(Set(v.missing + count.missing)).sorted()
        return c
    }

    public static func totals(_ objects: [InventoryObject], recognition: RecognitionCapability, validation: PipelineValidation, extraMissing: [String] = []) -> InventoryTotals {
        let frames = objects.filter { $0.elementClass.isFrame }
        // aantal kozijnen: elk object telt 1; een object zonder maat telt wel mee als kozijn, maar een onbevestigde automatische contour maakt het aantal voorlopig
        let count = total(frames, unit: "st", origin: .COUNTED_FROM_ASSOCIATION, value: { o in
            ScanValue(value: 1, unit: "st", origin: .COUNTED_FROM_ASSOCIATION,
                      outcome: (o.contourEvidence == .AUTO_UNCONFIRMED || !validation.autoProcessingAllowed) ? .VOORLOPIG_VASTGESTELD : .BETROUWBAAR_VASTGESTELD,
                      missing: (o.contourEvidence == .AUTO_UNCONFIRMED ? ["BUITENCONTOUR_NIET_BEVESTIGD"] : []) + (validation.autoProcessingAllowed ? [] : validation.blockingReasons))
        }, extraMissing: extraMissing)
        func capped(_ v: ScanValue, _ o: InventoryObject) -> ScanValue {
            // een waarde kan nooit zekerder zijn dan het object waar hij bij hoort
            guard v.value != nil, o.outcome.rank > v.outcome.rank else { return v }
            var c = v; c.outcome = o.outcome == .NIET_VAST_TE_STELLEN ? .VOORLOPIG_VASTGESTELD : o.outcome; c.missing = Array(Set(v.missing + o.outcomeReasons)).sorted(); return c
        }
        let area = total(frames, unit: "m2", origin: .DERIVED_CALCULATION, value: { capped($0.geometry.area, $0) }, extraMissing: extraMissing)
        // Herkomst van een totaal wordt nooit opgewaardeerd: USER_INPUT alleen als ELK deel door de gebruiker is ingevuld. En een totaal over
        // objecten kan nooit zekerder zijn dan de telling van die objecten zelf (die uit de associatie komt).
        func partsTotal(_ value: @escaping (InventoryObject) -> ScanValue) -> ScanValue {
            let allUser = !frames.isEmpty && frames.allSatisfy { value($0).origin == .USER_INPUT }
            return notBetterThanCount(total(frames, unit: "st", origin: allUser ? .USER_INPUT : .MODEL_CLASSIFICATION, value: value, extraMissing: extraMissing), count)
        }
        let operable = partsTotal { $0.geometry.operableParts }
        let fixed = partsTotal { $0.geometry.fixedParts }
        let glass = total(frames, unit: "m2", origin: .DERIVED_SEGMENTATION_ON_MEASURED_PLANE, value: { capped($0.geometry.glassArea, $0) }, extraMissing: extraMissing)
        var doors = ScanValue.unknown("st", ["GEEN_MODEL_VOOR_DEUR_OF_RAAM"] + extraMissing)
        if recognition.learnedClasses.contains(.DEUR) || frames.contains(where: { $0.classOrigin == .USER_INPUT }) {
            if frames.allSatisfy({ $0.elementClass != .KOZIJN }) {
                let allUser = frames.allSatisfy { $0.classOrigin == .USER_INPUT }
                doors = notBetterThanCount(total(frames, unit: "st", origin: allUser ? .USER_INPUT : .MODEL_CLASSIFICATION, value: { o in
                    ScanValue(value: o.elementClass == .DEUR ? 1 : 0, unit: "st", origin: o.classOrigin, outcome: o.classOrigin == .USER_INPUT ? .BETROUWBAAR_VASTGESTELD : .VOORLOPIG_VASTGESTELD)
                }, extraMissing: extraMissing), count)
            } else { doors = .unknown("st", ["NIET_ALLE_KOZIJNEN_GECLASSIFICEERD"] + extraMissing) }
        }
        return InventoryTotals(frameCount: count, frameAreaGross: area, operableParts: operable, fixedParts: fixed, glassArea: glass, doorCount: doors)
    }
}
