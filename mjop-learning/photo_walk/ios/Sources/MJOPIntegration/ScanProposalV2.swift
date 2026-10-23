import Foundation

/// Contract `mjop_scan_proposal_v2`: geaggregeerd hoeveelheidsvoorstel van een fotoronde. Schema: schemas/mjop_scan_proposal_v2.schema.json.
/// Uitbreiding op v1 (v1 blijft geldig voor een los kozijn). Altijd PROPOSED, nooit een boeking; onbekend = nil (nooit 0).
public struct ScanProposalV2: Codable, Equatable {
    public static let contractID = "mjop_scan_proposal_v2"
    /// De LiDAR-onzekerheid is in deze prototypefase op echte gebouwen niet gevalideerd.
    public static let lidarValidated = false

    public struct Project: Codable, Equatable {
        public var planRef: String
        public var mjopPlanId: String?
        public var buildingId: String
        public var bagPandId: String?
        enum CodingKeys: String, CodingKey { case planRef = "plan_ref", mjopPlanId = "mjop_plan_id", buildingId = "building_id", bagPandId = "bag_pand_id" }
        public init(planRef: String, mjopPlanId: String?, buildingId: String, bagPandId: String?) {
            self.planRef = planRef; self.mjopPlanId = mjopPlanId; self.buildingId = buildingId; self.bagPandId = bagPandId }
        public func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(planRef, forKey: .planRef); try c.encode(mjopPlanId, forKey: .mjopPlanId)
            try c.encode(buildingId, forKey: .buildingId); try c.encode(bagPandId, forKey: .bagPandId)
        }
    }
    public struct Target: Codable, Equatable {
        public enum Kind: String, Codable { case FRAME_COUNT, FRAME_AREA_GROSS }
        public struct Scope: Codable, Equatable {
            public enum ScopeType: String, Codable { case BUILDING, FACADE }
            public var type: ScopeType
            public var facadeId: String?
            public var orientation: String?
            enum CodingKeys: String, CodingKey { case type, facadeId = "facade_id", orientation }
            public init(type: ScopeType, facadeId: String?, orientation: String?) { self.type = type; self.facadeId = facadeId; self.orientation = orientation }
            public func encode(to encoder: Encoder) throws {
                var c = encoder.container(keyedBy: CodingKeys.self)
                try c.encode(type, forKey: .type); try c.encode(facadeId, forKey: .facadeId); try c.encode(orientation, forKey: .orientation)
            }
        }
        public var elementKey: String?
        public var quantityKind: Kind
        public var unit: String
        public var scope: Scope
        enum CodingKeys: String, CodingKey { case elementKey = "element_key", quantityKind = "quantity_kind", unit, scope }
        public init(elementKey: String?, quantityKind: Kind, unit: String, scope: Scope) {
            self.elementKey = elementKey; self.quantityKind = quantityKind; self.unit = unit; self.scope = scope }
        public func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(elementKey, forKey: .elementKey); try c.encode(quantityKind, forKey: .quantityKind)
            try c.encode(unit, forKey: .unit); try c.encode(scope, forKey: .scope)
        }
    }
    public struct Basis: Codable, Equatable {
        public var objectsTotal: Int
        public var objectsMeasured: Int
        public var objectsUnmeasured: Int
        public var photos: Int
        public var duplicatesUnresolved: Int
        public var crossSessionUnchecked: Bool
        public var excludedObjects: Int
        enum CodingKeys: String, CodingKey {
            case objectsTotal = "objects_total", objectsMeasured = "objects_measured", objectsUnmeasured = "objects_unmeasured", photos
            case duplicatesUnresolved = "duplicates_unresolved", crossSessionUnchecked = "cross_session_unchecked", excludedObjects = "excluded_objects"
        }
        public init(objectsTotal: Int, objectsMeasured: Int, objectsUnmeasured: Int, photos: Int, duplicatesUnresolved: Int, crossSessionUnchecked: Bool, excludedObjects: Int) {
            self.objectsTotal = objectsTotal; self.objectsMeasured = objectsMeasured; self.objectsUnmeasured = objectsUnmeasured; self.photos = photos
            self.duplicatesUnresolved = duplicatesUnresolved; self.crossSessionUnchecked = crossSessionUnchecked; self.excludedObjects = excludedObjects }
    }
    public struct Measurement: Codable, Equatable {
        public struct Uncertainty: Codable, Equatable {
            public var validated: Bool
            public var areaSigmaM2: Double?
            public var note: String
            enum CodingKeys: String, CodingKey { case validated, areaSigmaM2 = "area_sigma_m2", note }
            public init(validated: Bool, areaSigmaM2: Double?, note: String) { self.validated = validated; self.areaSigmaM2 = areaSigmaM2; self.note = note }
            public func encode(to encoder: Encoder) throws {
                var c = encoder.container(keyedBy: CodingKeys.self)
                try c.encode(validated, forKey: .validated); try c.encode(areaSigmaM2, forKey: .areaSigmaM2); try c.encode(note, forKey: .note)
            }
        }
        public var methods: [String]
        public var dimensionStatus: String
        public var uncertainty: Uncertainty
        enum CodingKeys: String, CodingKey { case methods, dimensionStatus = "dimension_status", uncertainty }
        public init(methods: [String], dimensionStatus: String, uncertainty: Uncertainty) { self.methods = methods; self.dimensionStatus = dimensionStatus; self.uncertainty = uncertainty }
    }
    public struct Evidence: Codable, Equatable {
        public struct Detection: Codable, Equatable {
            public var autoDetected: Int
            public var userCorrected: Int
            public var manual: Int
            enum CodingKeys: String, CodingKey { case autoDetected = "auto_detected", userCorrected = "user_corrected", manual }
            public init(autoDetected: Int, userCorrected: Int, manual: Int) { self.autoDetected = autoDetected; self.userCorrected = userCorrected; self.manual = manual }
        }
        public var photoIds: [String]
        public var objectIds: [String]
        public var qualityFlags: [String]
        public var detection: Detection
        enum CodingKeys: String, CodingKey { case photoIds = "photo_ids", objectIds = "object_ids", qualityFlags = "quality_flags", detection }
        public init(photoIds: [String], objectIds: [String], qualityFlags: [String], detection: Detection) {
            self.photoIds = photoIds; self.objectIds = objectIds; self.qualityFlags = qualityFlags; self.detection = detection }
    }
    public struct Reliability: Codable, Equatable {
        public var level: String            // CHECK_REQUIRED | INCOMPLETE
        public var reasons: [String]
        public init(level: String, reasons: [String]) { self.level = level; self.reasons = reasons }
    }
    public struct Confirmation: Codable, Equatable {
        public var status: String
        public var uncertaintyAcknowledged: Bool
        public var confirmedAt: String?
        enum CodingKeys: String, CodingKey { case status, uncertaintyAcknowledged = "uncertainty_acknowledged", confirmedAt = "confirmed_at" }
        public init() { status = "PROPOSED"; uncertaintyAcknowledged = false; confirmedAt = nil }
        public func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(status, forKey: .status); try c.encode(uncertaintyAcknowledged, forKey: .uncertaintyAcknowledged); try c.encode(confirmedAt, forKey: .confirmedAt)
        }
    }

    public var contract: String
    public var proposalId: String
    public var roundId: String
    public var revision: Int
    public var createdAt: String
    public var project: Project
    public var target: Target
    public var value: Double?
    public var partialValue: Double?
    public var basis: Basis
    public var measurement: Measurement
    public var evidence: Evidence
    public var reliability: Reliability
    public var confirmation: Confirmation
    public var bookingAllowed: Bool

    enum CodingKeys: String, CodingKey {
        case contract, revision, project, target, value, basis, measurement, evidence, reliability, confirmation
        case proposalId = "proposal_id", roundId = "round_id", createdAt = "created_at", partialValue = "partial_value", bookingAllowed = "booking_allowed"
    }

    public init(proposalId: String, roundId: String, revision: Int, createdAt: String, project: Project, target: Target, value: Double?, partialValue: Double?,
                basis: Basis, measurement: Measurement, evidence: Evidence, reliability: Reliability) {
        self.contract = Self.contractID; self.proposalId = proposalId; self.roundId = roundId; self.revision = revision; self.createdAt = createdAt
        self.project = project; self.target = target; self.value = value; self.partialValue = partialValue; self.basis = basis
        self.measurement = measurement; self.evidence = evidence; self.reliability = reliability
        self.confirmation = Confirmation(); self.bookingAllowed = false
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(contract, forKey: .contract); try c.encode(proposalId, forKey: .proposalId); try c.encode(roundId, forKey: .roundId)
        try c.encode(revision, forKey: .revision); try c.encode(createdAt, forKey: .createdAt); try c.encode(project, forKey: .project)
        try c.encode(target, forKey: .target); try c.encode(value, forKey: .value); try c.encode(partialValue, forKey: .partialValue)
        try c.encode(basis, forKey: .basis); try c.encode(measurement, forKey: .measurement); try c.encode(evidence, forKey: .evidence)
        try c.encode(reliability, forKey: .reliability); try c.encode(confirmation, forKey: .confirmation); try c.encode(bookingAllowed, forKey: .bookingAllowed)
    }

    // MARK: regels (zelfde regels als de website in src/photo-round.js)

    public enum Issue: Equatable {
        case wrongContract, bookingMustBeDisallowed, notProposed, badBasis, unitMismatch, valueWithoutObjects
        case areaWithUnmeasured, nullValueNotIncomplete, uncertaintyNotNamed, negativeValue, facadeWithoutId
    }

    public func validate() -> [Issue] {
        var out: [Issue] = []
        if contract != Self.contractID { out.append(.wrongContract) }
        if bookingAllowed { out.append(.bookingMustBeDisallowed) }
        if confirmation.status != "PROPOSED" || confirmation.uncertaintyAcknowledged || confirmation.confirmedAt != nil { out.append(.notProposed) }
        if basis.objectsMeasured + basis.objectsUnmeasured != basis.objectsTotal || [basis.objectsTotal, basis.objectsMeasured, basis.objectsUnmeasured, basis.photos, basis.duplicatesUnresolved, basis.excludedObjects].contains(where: { $0 < 0 }) { out.append(.badBasis) }
        let expectedUnit = target.quantityKind == .FRAME_COUNT ? "st" : "m2"
        if target.unit != expectedUnit { out.append(.unitMismatch) }
        if let v = value, !(v.isFinite && v >= 0) { out.append(.negativeValue) }
        if value == nil && reliability.level != "INCOMPLETE" { out.append(.nullValueNotIncomplete) }
        if value != nil && basis.objectsTotal == 0 { out.append(.valueWithoutObjects) }
        if target.quantityKind == .FRAME_AREA_GROSS && value != nil && basis.objectsUnmeasured > 0 { out.append(.areaWithUnmeasured) }
        if !measurement.uncertainty.validated && !reliability.reasons.contains("UNVALIDATED_LIDAR") { out.append(.uncertaintyNotNamed) }
        if target.scope.type == .FACADE && target.scope.facadeId == nil { out.append(.facadeWithoutId) }
        return out
    }

    public enum DecodeError: Error, Equatable { case unsupportedContract(String), invalid([Issue]) }

    public static func decode(_ data: Data) throws -> ScanProposalV2 {
        let p = try JSONDecoder().decode(ScanProposalV2.self, from: data)
        if p.contract != contractID { throw DecodeError.unsupportedContract(p.contract) }
        let issues = p.validate()
        if !issues.isEmpty { throw DecodeError.invalid(issues) }
        return p
    }

    public func encoded() throws -> Data {
        let e = JSONEncoder(); e.outputFormatting = [.sortedKeys, .prettyPrinted]
        return try e.encode(self)
    }

    /// JSON-object voor de brug (zelfde sleutels als het schema).
    public func jsonObject() -> [String: Any]? {
        guard let data = try? JSONEncoder().encode(self), let o = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        return o
    }
}
