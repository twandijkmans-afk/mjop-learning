import Foundation

/// Contract `mjop_scan_proposal_v1`: wat de gevelscanner later aan het MJOP VOORSTELT. Schema: schemas/mjop_scan_proposal_v1.schema.json.
/// Dit is geen boeking: `bookingAllowed` is in v1 altijd false. Fase 1 bevat alleen het contract, de regels en de validatie.
public struct ScanProposal: Codable, Equatable {
    public static let contractID = "mjop_scan_proposal_v1"

    public struct Project: Codable, Equatable {
        public var mjopPlanId: String?
        public var buildingId: String
        public var facadeId: String
        public var bagPandId: String?
        enum CodingKeys: String, CodingKey { case mjopPlanId = "mjop_plan_id", buildingId = "building_id", facadeId = "facade_id", bagPandId = "bag_pand_id" }
        public func encode(to encoder: Encoder) throws {   // nil blijft expliciet null: het schema eist de sleutels
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(mjopPlanId, forKey: .mjopPlanId); try c.encode(buildingId, forKey: .buildingId)
            try c.encode(facadeId, forKey: .facadeId); try c.encode(bagPandId, forKey: .bagPandId)
        }
        public init(mjopPlanId: String?, buildingId: String, facadeId: String, bagPandId: String?) {
            self.mjopPlanId = mjopPlanId; self.buildingId = buildingId; self.facadeId = facadeId; self.bagPandId = bagPandId }
    }
    public struct Element: Codable, Equatable {
        public enum Kind: String, Codable { case FRAME, FRAME_WITH_DOOR, DOOR, UNKNOWN }
        public var type: Kind
        public var mjopElementKey: String?
        enum CodingKeys: String, CodingKey { case type, mjopElementKey = "mjop_element_key" }
        public func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(type, forKey: .type); try c.encode(mjopElementKey, forKey: .mjopElementKey)
        }
        public init(type: Kind, mjopElementKey: String?) { self.type = type; self.mjopElementKey = mjopElementKey }
    }
    public struct Quantity: Codable, Equatable {
        public enum Unit: String, Codable { case m2, m1, st }
        public var unit: Unit
        public var value: Double?
        public var widthM: Double?
        public var heightM: Double?
        enum CodingKeys: String, CodingKey { case unit, value, widthM = "width_m", heightM = "height_m" }
        public func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(unit, forKey: .unit); try c.encode(value, forKey: .value)
            try c.encode(widthM, forKey: .widthM); try c.encode(heightM, forKey: .heightM)
        }
        public init(unit: Unit, value: Double?, widthM: Double?, heightM: Double?) { self.unit = unit; self.value = value; self.widthM = widthM; self.heightM = heightM }
    }
    public struct Measurement: Codable, Equatable {
        public enum Method: String, Codable { case LIDAR_DEPTH_PLANE, LIDAR_DEPTH_MULTI_FRAME, AR_TRIANGULATION_VIO, REFERENCE_DISTANCE, MANUAL_CORNERS, NONE }
        public enum DimensionStatus: String, Codable { case MEASURED, DERIVED, ESTIMATED, UNKNOWN }
        public struct Uncertainty: Codable, Equatable {
            public var validated: Bool
            public var areaSigmaM2: Double?
            public var note: String
            enum CodingKeys: String, CodingKey { case validated, areaSigmaM2 = "area_sigma_m2", note }
            public func encode(to encoder: Encoder) throws {
                var c = encoder.container(keyedBy: CodingKeys.self)
                try c.encode(validated, forKey: .validated); try c.encode(areaSigmaM2, forKey: .areaSigmaM2); try c.encode(note, forKey: .note)
            }
            public init(validated: Bool, areaSigmaM2: Double?, note: String) { self.validated = validated; self.areaSigmaM2 = areaSigmaM2; self.note = note }
        }
        public var method: Method
        public var dimensionStatus: DimensionStatus
        public var uncertainty: Uncertainty
        enum CodingKeys: String, CodingKey { case method, dimensionStatus = "dimension_status", uncertainty }
        public init(method: Method, dimensionStatus: DimensionStatus, uncertainty: Uncertainty) { self.method = method; self.dimensionStatus = dimensionStatus; self.uncertainty = uncertainty }
    }
    public struct Evidence: Codable, Equatable {
        public var sourcePhotoId: String
        public var provisionalObjectId: String
        public var qualityFlags: [String]
        enum CodingKeys: String, CodingKey { case sourcePhotoId = "source_photo_id", provisionalObjectId = "provisional_object_id", qualityFlags = "quality_flags" }
        public init(sourcePhotoId: String, provisionalObjectId: String, qualityFlags: [String]) {
            self.sourcePhotoId = sourcePhotoId; self.provisionalObjectId = provisionalObjectId; self.qualityFlags = qualityFlags }
    }
    public struct Confirmation: Codable, Equatable {
        public enum Status: String, Codable { case PROPOSED, CONFIRMED_BY_USER, REJECTED_BY_USER }
        public var status: Status
        public var uncertaintyAcknowledged: Bool
        public var confirmedAt: String?
        enum CodingKeys: String, CodingKey { case status, uncertaintyAcknowledged = "uncertainty_acknowledged", confirmedAt = "confirmed_at" }
        public func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(status, forKey: .status); try c.encode(uncertaintyAcknowledged, forKey: .uncertaintyAcknowledged)
            try c.encode(confirmedAt, forKey: .confirmedAt)
        }
        public init(status: Status, uncertaintyAcknowledged: Bool, confirmedAt: String?) { self.status = status; self.uncertaintyAcknowledged = uncertaintyAcknowledged; self.confirmedAt = confirmedAt }
    }

    public var contract: String
    public var proposalId: String
    public var createdAt: String
    public var project: Project
    public var element: Element
    public var quantity: Quantity
    public var measurement: Measurement
    public var evidence: Evidence
    public var confirmation: Confirmation
    public var bookingAllowed: Bool

    enum CodingKeys: String, CodingKey {
        case contract, project, element, quantity, measurement, evidence, confirmation
        case proposalId = "proposal_id", createdAt = "created_at", bookingAllowed = "booking_allowed"
    }

    public init(proposalId: String, createdAt: String, project: Project, element: Element, quantity: Quantity,
                measurement: Measurement, evidence: Evidence) {
        self.contract = Self.contractID; self.proposalId = proposalId; self.createdAt = createdAt; self.project = project
        self.element = element; self.quantity = quantity; self.measurement = measurement; self.evidence = evidence
        self.confirmation = Confirmation(status: .PROPOSED, uncertaintyAcknowledged: false, confirmedAt: nil)
        self.bookingAllowed = false
    }

    // MARK: regels

    /// Een maat is alleen "zeker" als de methode een gevalideerde onzekerheid heeft én de status MEASURED is. Alle LiDAR-uitkomsten van
    /// deze prototypefase zijn PROVISIONAL_UNVALIDATED en dus onzeker.
    public var isUncertain: Bool {
        measurement.dimensionStatus != .MEASURED || !measurement.uncertainty.validated || quantity.value == nil
    }

    public enum Issue: Equatable {
        case wrongContract, bookingMustBeDisallowed, noValueButConfirmed, unknownStatusConfirmed
        case uncertainConfirmedWithoutAcknowledgement, confirmedWithoutTimestamp, invalidQuantity, acknowledgedWhileProposed
    }

    /// Alle schendingen van de contractregels (leeg = geldig).
    public func validate() -> [Issue] {
        var out: [Issue] = []
        if contract != Self.contractID { out.append(.wrongContract) }
        if bookingAllowed { out.append(.bookingMustBeDisallowed) }
        if let v = quantity.value, !(v.isFinite && v >= 0) { out.append(.invalidQuantity) }
        if confirmation.status == .PROPOSED && confirmation.uncertaintyAcknowledged { out.append(.acknowledgedWhileProposed) }
        if confirmation.status == .CONFIRMED_BY_USER {
            if quantity.value == nil { out.append(.noValueButConfirmed) }
            if measurement.dimensionStatus == .UNKNOWN { out.append(.unknownStatusConfirmed) }
            if isUncertain && !confirmation.uncertaintyAcknowledged { out.append(.uncertainConfirmedWithoutAcknowledgement) }
            if confirmation.confirmedAt == nil { out.append(.confirmedWithoutTimestamp) }
        }
        return out
    }

    public enum ConfirmationError: Error, Equatable { case notAllowed([Issue]), alreadyDecided }

    /// Enige toegestane weg naar "bevestigd": een expliciete gebruikershandeling. Bij onzekere maten moet de gebruiker de onzekerheid
    /// uitdrukkelijk accepteren (`acknowledgingUncertainty`). Geeft een nieuwe waarde terug; het origineel blijft ongewijzigd.
    public func confirmed(byUserAt timestamp: String, acknowledgingUncertainty: Bool) throws -> ScanProposal {
        guard confirmation.status == .PROPOSED else { throw ConfirmationError.alreadyDecided }
        var c = self
        c.confirmation = Confirmation(status: .CONFIRMED_BY_USER, uncertaintyAcknowledged: acknowledgingUncertainty, confirmedAt: timestamp)
        let issues = c.validate()
        guard issues.isEmpty else { throw ConfirmationError.notAllowed(issues) }
        return c
    }

    public func rejected(byUserAt timestamp: String) throws -> ScanProposal {
        guard confirmation.status == .PROPOSED else { throw ConfirmationError.alreadyDecided }
        var c = self
        c.confirmation = Confirmation(status: .REJECTED_BY_USER, uncertaintyAcknowledged: false, confirmedAt: timestamp)
        return c
    }

    // MARK: (de)serialisatie

    public enum DecodeError: Error, Equatable { case unsupportedContract(String), invalid([Issue]) }

    /// Strikt decoderen: onbekend contract (andere versie) of een regelschending wordt geweigerd.
    public static func decode(_ data: Data) throws -> ScanProposal {
        let p = try JSONDecoder().decode(ScanProposal.self, from: data)
        if p.contract != contractID { throw DecodeError.unsupportedContract(p.contract) }
        let issues = p.validate()
        if !issues.isEmpty { throw DecodeError.invalid(issues) }
        return p
    }

    public func encode() throws -> Data {
        let e = JSONEncoder(); e.outputFormatting = [.sortedKeys, .prettyPrinted]
        return try e.encode(self)
    }
}
