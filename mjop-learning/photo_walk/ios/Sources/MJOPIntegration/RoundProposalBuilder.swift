import Foundation

/// Eén uniek voorlopig kozijn in een fotoronde (na samenvoegen van waarnemingen op meerdere foto's), als invoer voor de voorstellen.
public struct RoundObject: Equatable {
    public enum Status: Int { case measured = 0, derived = 1, estimated = 2, unknown = 3
        var name: String { ["MEASURED", "DERIVED", "ESTIMATED", "UNKNOWN"][rawValue] } }
    public var id: String
    public var facadeId: String
    public var frameIds: [String]
    public var areaM2: Decimal?
    public var areaSigmaM2: Double?
    public var status: Status
    public var method: String                  // LIDAR_DEPTH_MULTI_FRAME | LIDAR_DEPTH_PLANE | AR_TRIANGULATION_VIO | REFERENCE_DISTANCE | MANUAL_CORNERS | NONE
    public var autoDetected: Bool
    public var userConfirmed: Bool              // hoeken bevestigd of gecorrigeerd door een persoon
    public var manual: Bool
    public var flags: [String]
    /// Automatisch herkende buitencontour die de gebruiker nog niet heeft bevestigd (gevelopbouw): het is nog niet zeker dat dit een kozijn is
    /// (kan glas of een valse kandidaat zijn). Zo'n object telt niet mee in een aantal en heeft geen oppervlak. Standaard false (oude scans: LEGACY).
    public var contourUnconfirmed: Bool
    public init(id: String, facadeId: String, frameIds: [String], areaM2: Decimal?, areaSigmaM2: Double?, status: Status, method: String,
                autoDetected: Bool, userConfirmed: Bool, manual: Bool, flags: [String], contourUnconfirmed: Bool = false) {
        self.id = id; self.facadeId = facadeId; self.frameIds = frameIds; self.areaM2 = areaM2; self.areaSigmaM2 = areaSigmaM2; self.status = status
        self.method = method; self.autoDetected = autoDetected; self.userConfirmed = userConfirmed; self.manual = manual; self.flags = flags
        self.contourUnconfirmed = contourUnconfirmed }

    /// Een maat telt alleen als er een oppervlak is én de status niet UNKNOWN is.
    public var isMeasured: Bool { areaM2 != nil && status != .unknown }
}

public struct RoundFacade: Equatable {
    public var id: String
    public var orientation: String?
    public var worldIds: Set<String>            // AR-sessies (coördinatenstelsels) waarin foto's van deze gevel zijn gemaakt
    public init(id: String, orientation: String?, worldIds: Set<String>) { self.id = id; self.orientation = orientation; self.worldIds = worldIds }
}

public struct RoundBuildInput {
    public var roundId: String
    public var revision: Int
    public var createdAt: String
    public var project: ScanProposalV2.Project
    public var elementKey: String?
    public var objects: [RoundObject]           // uniek, niet-uitgesloten
    public var facades: [RoundFacade]
    public var excludedObjectsByFacade: [String: Int]
    public var duplicatesUnresolvedByFacade: [String: Int]
    public init(roundId: String, revision: Int, createdAt: String, project: ScanProposalV2.Project, elementKey: String?, objects: [RoundObject], facades: [RoundFacade],
                excludedObjectsByFacade: [String: Int], duplicatesUnresolvedByFacade: [String: Int]) {
        self.roundId = roundId; self.revision = revision; self.createdAt = createdAt; self.project = project; self.elementKey = elementKey; self.objects = objects
        self.facades = facades; self.excludedObjectsByFacade = excludedObjectsByFacade; self.duplicatesUnresolvedByFacade = duplicatesUnresolvedByFacade }
}

/// Bouwt de voorstellen (aantal en bruto oppervlak, voor het gebouw en per gevel) uit de objecten van een fotoronde. Deterministisch, zonder prijzen of kengetallen:
/// kosten blijven bij de bestaande kengetallen van het MJOP. Rekent met Decimal.
public enum RoundProposalBuilder {
    static func clean(_ s: String) -> String {
        String(s.unicodeScalars.map { CharacterSet.alphanumerics.contains($0) && $0.isASCII ? Character($0) : "-" })
    }

    public static func build(_ input: RoundBuildInput) -> [ScanProposalV2] {
        var out: [ScanProposalV2] = []
        let multiFacade = input.facades.count > 1
        out += proposals(input, scope: .init(type: .BUILDING, facadeId: nil, orientation: nil), objects: input.objects,
                         excluded: input.excludedObjectsByFacade.values.reduce(0, +), duplicates: input.duplicatesUnresolvedByFacade.values.reduce(0, +),
                         crossSession: input.facades.contains { $0.worldIds.count > 1 }, tag: "bld")
        if multiFacade {
            for f in input.facades {
                let objs = input.objects.filter { $0.facadeId == f.id }
                if objs.isEmpty { continue }
                out += proposals(input, scope: .init(type: .FACADE, facadeId: f.id, orientation: f.orientation), objects: objs,
                                 excluded: input.excludedObjectsByFacade[f.id] ?? 0, duplicates: input.duplicatesUnresolvedByFacade[f.id] ?? 0,
                                 crossSession: f.worldIds.count > 1, tag: "f-" + clean(f.id))
            }
        }
        return out
    }

    private static func proposals(_ input: RoundBuildInput, scope: ScanProposalV2.Target.Scope, objects: [RoundObject], excluded: Int, duplicates: Int, crossSession: Bool, tag: String) -> [ScanProposalV2] {
        let total = objects.count
        let measured = objects.filter { $0.isMeasured }
        let unmeasured = total - measured.count
        let photos = Array(Set(objects.flatMap { $0.frameIds })).sorted()
        let methods = Array(Set(objects.map { $0.method }.filter { $0 != "NONE" })).sorted()
        let worst = objects.map { $0.status.rawValue }.max().flatMap { RoundObject.Status(rawValue: $0) }
        let status = worst?.name ?? "UNKNOWN"
        var sum = Decimal(0); for o in measured { sum += o.areaM2 ?? 0 }
        let sumD = NSDecimalNumber(decimal: sum).doubleValue
        let rounded = (sumD * 100).rounded() / 100
        let sigma: Double? = (unmeasured == 0 && total > 0 && measured.allSatisfy { $0.areaSigmaM2 != nil })
            ? ((measured.reduce(0.0) { $0 + ($1.areaSigmaM2 ?? 0) * ($1.areaSigmaM2 ?? 0) }).squareRoot() * 1000).rounded() / 1000 : nil
        var flags = Array(Set(objects.flatMap { $0.flags })).sorted(); if flags.count > 20 { flags = Array(flags.prefix(20)) }
        let detection = ScanProposalV2.Evidence.Detection(
            autoDetected: objects.filter { $0.autoDetected }.count,
            userCorrected: objects.filter { $0.userConfirmed && $0.autoDetected }.count,
            manual: objects.filter { $0.manual }.count)
        let basis = ScanProposalV2.Basis(objectsTotal: total, objectsMeasured: measured.count, objectsUnmeasured: unmeasured, photos: photos.count,
                                         duplicatesUnresolved: duplicates, crossSessionUnchecked: crossSession, excludedObjects: excluded)
        var reasons: [String] = ["UNVALIDATED_LIDAR"]
        if total == 0 { reasons.append("NO_OBJECTS") }
        if unmeasured > 0 { reasons.append("UNMEASURED_OBJECTS") }
        if duplicates > 0 { reasons.append("DUPLICATES_UNRESOLVED") }
        if crossSession { reasons.append("CROSS_SESSION_UNCHECKED") }
        if objects.contains(where: { $0.autoDetected && !$0.userConfirmed }) { reasons.append("AUTO_DETECTED") }
        let measurement = ScanProposalV2.Measurement(methods: methods, dimensionStatus: status,
            uncertainty: .init(validated: ScanProposalV2.lidarValidated, areaSigmaM2: sigma, note: "PROVISIONAL_UNVALIDATED"))
        let evidence = ScanProposalV2.Evidence(photoIds: photos, objectIds: objects.map { $0.id }.sorted(), qualityFlags: flags, detection: detection)
        let idBase = String(clean(input.roundId).prefix(24))

        func make(_ kind: ScanProposalV2.Target.Kind, _ unit: String, value: Double?, partial: Double?, level: String) -> ScanProposalV2 {
            let suffix = kind == .FRAME_COUNT ? "count" : "area"
            return ScanProposalV2(
                proposalId: "\(idBase)-\(suffix)-\(tag)-r\(input.revision)", roundId: String(clean(input.roundId).prefix(80)), revision: input.revision, createdAt: input.createdAt,
                project: input.project, target: .init(elementKey: input.elementKey, quantityKind: kind, unit: unit, scope: scope), value: value, partialValue: partial,
                basis: basis, measurement: measurement, evidence: evidence, reliability: .init(level: level, reasons: reasons))
        }
        // aantal: zonder kozijnen is er geen aantal (nil), niet 0. Zolang er een automatisch herkende, onbevestigde buitencontour bij zit, is het
        // aantal onvolledig (nil): zo'n object kan glas of een valse kandidaat zijn. Geen deelaantal (partial) om misbruik als hoeveelheid te voorkomen.
        let unconfirmedContours = objects.contains { $0.contourUnconfirmed }
        let countComplete = total > 0 && !unconfirmedContours
        let count = make(.FRAME_COUNT, "st", value: countComplete ? Double(total) : nil, partial: nil, level: countComplete ? "CHECK_REQUIRED" : "INCOMPLETE")
        // oppervlak: alleen als ALLE meetellende kozijnen een maat hebben; anders nil + deelsom ter informatie
        let complete = total > 0 && unmeasured == 0
        let area = make(.FRAME_AREA_GROSS, "m2", value: complete ? rounded : nil, partial: (!complete && !measured.isEmpty) ? rounded : nil, level: complete ? "CHECK_REQUIRED" : "INCOMPLETE")
        return [count, area]
    }
}
