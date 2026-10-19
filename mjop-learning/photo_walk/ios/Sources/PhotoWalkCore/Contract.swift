import Foundation

/// Per-kozijn deel van `photo_walk_capture_v1` (zie ../../schemas/photo_walk_capture_v1.schema.json). Het JSON wordt met `json` als
/// dictionary opgebouwd (niet via Codable) omdat het schema verplichte sleutels met waarde null kent.
/// De Swift-uitvoer is NIET tegen het schema getest: valideer exports met `python -m photo_walk_core.validate <bestand>`.
public enum DimensionStatus: String { case MEASURED, DERIVED, ESTIMATED, UNKNOWN }

public struct CornerRevisionRecord {
    public var index: Int, before: Pixel, after: Pixel, editedBy: String, editedAt: String, reason: String?
    public init(index: Int, before: Pixel, after: Pixel, editedBy: String, editedAt: String, reason: String?) {
        self.index = index; self.before = before; self.after = after; self.editedBy = editedBy; self.editedAt = editedAt; self.reason = reason
    }
}

public struct ObservationRecord {
    public var id: String, frameId: String, corners: [Pixel], originalCorners: [Pixel], source: String, revisions: [CornerRevisionRecord]
    public init(id: String, frameId: String, corners: [Pixel], originalCorners: [Pixel], source: String, revisions: [CornerRevisionRecord] = []) {
        self.id = id; self.frameId = frameId; self.corners = corners; self.originalCorners = originalCorners; self.source = source; self.revisions = revisions
    }
}

public struct MeasuredObject {
    public var id: String
    public var status: DimensionStatus
    public var widthM: String?, heightM: String?, areaM2: String?, areaPresented: String?
    public var reviewRequired: Bool
    public var flags: [QualityFlag]
    public var nextSteps: [String]
    public var observations: [ObservationRecord]
    public var result: LevelResult
    public var json: [String: Any] { MeasuredObject.build(self) }

    private static func px(_ p: Pixel) -> [Double] { [(p.u * 100).rounded() / 100, (p.v * 100).rounded() / 100] }
    private static func fmt4(_ x: Double?) -> String { String(format: "%.4f", x ?? 0) }
    private static let cornerNames = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_RIGHT", "BOTTOM_LEFT"]

    static func build(_ o: MeasuredObject) -> [String: Any] {
        let ok = o.status != .UNKNOWN
        let flags: [[String: Any]] = o.flags.map { ["code": $0.code, "severity": $0.severity.rawValue, "detail": $0.detail ?? NSNull(), "instruction_nl": $0.instruction_nl] }
        let corner: Any = (ok && o.result.cornersWorld != nil)
            ? ["coordinate_system": "WORLD_M_Y_UP", "unit": "m", "points": o.result.cornersWorld!.map { [$0.x, $0.y, $0.z] }] as [String: Any] : NSNull()
        let unc: Any = ok ? ["model": "MONTE_CARLO_PIXEL_PLANE_NOISE_V1", "validated": false, "samples": 100, "width_sigma_m": fmt4(o.result.sigmaW), "height_sigma_m": fmt4(o.result.sigmaH),
                             "area_sigma_m2": fmt4(o.result.sigmaArea), "note": "1-sigma van een ruismodel met provisional parameters; geen gevalideerde tolerantie."] as [String: Any] : NSNull()
        let sources = Array(Set(o.observations.map { $0.source })).sorted()
        let detection = o.observations.contains { $0.source == "MANUAL" || $0.source == "MANUAL_CORRECTED" } ? "SEMI_AUTOMATIC" : "AUTOMATIC_CANDIDATE"
        return [
            "provisional_object_id": o.id, "observation_refs": o.observations.map { $0.id }, "frame_type": "UNKNOWN",
            "parts": ["fixed_parts": NSNull(), "movable_parts": NSNull(), "note": "informatief; heeft geen invloed op het bruto oppervlak (regel 2)"] as [String: Any],
            "detection_method": detection, "corner_sources": sources, "corner_order": cornerNames, "outer_corner_coordinates": corner,
            "corner_pixels": o.observations.map { ob -> [String: Any] in
                ["observation_ref": ob.id, "frame_id": ob.frameId, "unit": "px", "points": ob.corners.map(px), "original_points": ob.originalCorners.map(px),
                 "revisions": ob.revisions.enumerated().map { (i, r) -> [String: Any] in
                    ["revision": i + 1, "corner_index": r.index, "corner_name": cornerNames[r.index], "before_px": px(r.before), "after_px": px(r.after),
                     "edited_by": r.editedBy, "edited_at": r.editedAt, "reason": r.reason ?? NSNull()] }] },
            "outer_width_m": o.widthM ?? NSNull(), "outer_height_m": o.heightM ?? NSNull(), "gross_area_m2": o.areaM2 ?? NSNull(),
            "gross_area_m2_presented": o.areaPresented ?? NSNull(), "dimension_status": o.status.rawValue, "measurement_uncertainty": unc,
            "measurement_source": ["level": ok ? o.result.level.rawValue : NSNull(), "scale_method": ok ? o.result.scaleMethod : "NONE", "views": ok ? o.result.viewIds : [String](),
                                   "scale_evidence": [String: Any]()] as [String: Any],
            "review_required": o.reviewRequired, "quality_flags": flags, "next_steps_nl": o.nextSteps,
            "quantity_layer": "PROVISIONAL", "approval_state": "PENDING_HUMAN_APPROVAL",
        ]
    }
}

public enum Status {
    /// Zelfde regels als pipeline._status_from: MEASURED vereist >= 2 consistente standpunten en geen downgrading-advisories.
    static let downgrading: Set<String> = ["GLASS_DEPTH_UNRELIABLE", "CORNER_DEPTH_MISMATCH", "FACADE_NOT_VERTICAL", "SINGLE_VIEWPOINT",
                                           "COPLANARITY_ASSUMED", "REFERENCE_UNCERTAINTY_NOT_PROVIDED", "OBSTRUCTION_REPORTED", "AUTO_DETECTED_UNCONFIRMED"]
    public static func status(for r: LevelResult, viewCount: Int) -> DimensionStatus {
        guard r.ok else { return .UNKNOWN }
        if r.level == .C { return .DERIVED }
        let adv = Set(r.flags.filter { $0.severity == .ADVISORY }.map { $0.code })
        return (viewCount >= 2 && adv.isDisjoint(with: downgrading)) ? .MEASURED : .ESTIMATED
    }
}

public func makeObject(id: String, observations: [ObservationRecord], result: LevelResult, viewCount: Int, extraFlags: [QualityFlag] = []) -> MeasuredObject {
    var flags = result.flags + extraFlags
    if viewCount == 1 && result.level == .A && result.ok { flags.append(Flags.make("SINGLE_VIEWPOINT")) }
    let status = Status.status(for: result, viewCount: viewCount)
    var w: String? = nil, h: String? = nil, a: String? = nil, ap: String? = nil
    if result.ok, let rw = result.width, let rh = result.height {
        let dw = roundedMillimeters(rw), dh = roundedMillimeters(rh)
        let area = grossAreaM2(width: dw, height: dh)
        w = decimalString(dw); h = decimalString(dh); a = decimalString(area)
        var r = Decimal(); var v = area; NSDecimalRound(&r, &v, 2, .plain); ap = NSDecimalNumber(decimal: r).stringValue
    }
    let steps = flags.filter { $0.severity == .BLOCKING }.map { $0.instruction_nl }
    return MeasuredObject(id: id, status: status, widthM: w, heightM: h, areaM2: a, areaPresented: ap,
                          reviewRequired: status != .MEASURED || !flags.isEmpty, flags: flags, nextSteps: steps, observations: observations, result: result)
}
