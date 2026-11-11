import Foundation
import MJOPIntegration
import PhotoWalkCore

// Koppeling naar het MJOP: het pijplijnresultaat als `mjop_gevel_inventory_v1`. Geen prijzen, geen kengetallen, geen MJOP-berekening:
// de website rekent met zijn eigen kengetallenbibliotheek. De app levert alleen hoeveelheden, herkomst, onzekerheid en bewijs.

public enum InventoryContractBuilder {
    static func q(_ v: ScanValue) -> JSONValue {
        .object(["value": .optional(v.value), "unit": .string(v.unit), "sigma": .optional(v.sigma), "origin": .string(v.origin.rawValue), "outcome": .string(v.outcome.rawValue),
                 "missing": .strings(v.missing.map(code)), "partial": .optional(v.partial)])
    }
    /// Codes in het contract: alleen hoofdletters, cijfers en _ (kwaliteitscodes van de meetkern voldoen daar al aan).
    static func code(_ s: String) -> String {
        String(String(s.uppercased().unicodeScalars.map { ("A"..."Z").contains($0) || ("0"..."9").contains($0) ? Character($0) : "_" }).prefix(60))
    }
    static func totals(_ t: InventoryTotals) -> JSONValue {
        .object(["frame_count": q(t.frameCount), "frame_area_gross": q(t.frameAreaGross), "operable_parts": q(t.operableParts), "fixed_parts": q(t.fixedParts),
                 "glass_area": q(t.glassArea), "door_count": q(t.doorCount)])
    }
    static func px(_ p: [Pixel]) -> JSONValue { .array(p.map { .array([.number(round($0.u, 1)), .number(round($0.v, 1))]) }) }
    static func detector(_ d: DetectorDescriptor) -> JSONValue {
        .object(["name": .string(d.name), "version": .string(d.version), "kind": .string(d.kind.rawValue), "validated": .bool(d.validated), "classes": .strings(d.classes.map { $0.rawValue })])
    }
    static func request(_ r: CaptureRequest) -> JSONValue {
        .object(["kind": .string(r.kind.rawValue), "object_id": .optional(r.objectId), "photo_id": .optional(r.photoId), "reason": .string(code(r.reason)), "text_nl": .string(r.textNL)])
    }
    static func clean(_ s: String) -> String { String(s.unicodeScalars.map { CharacterSet.alphanumerics.contains($0) && $0.isASCII ? Character($0) : "-" }) }

    static func object(_ o: InventoryObject) -> JSONValue {
        let g = o.geometry
        let panes: [JSONValue] = g.panes.map { p in
            .object(["id": .string(p.id), "x_m": .number(p.xM), "y_m": .number(p.yM), "width_m": .number(p.widthM), "height_m": .number(p.heightM), "area_m2": .number(p.areaM2),
                     "sigma_area_m2": .number(p.sigmaAreaM2), "seen_in_views": .number(Double(p.seenInViews)), "column": .number(Double(p.column)), "row": .number(Double(p.row)),
                     "operability": .optional(p.operability?.rawValue), "glare_suspected": .bool(p.glareSuspected), "origin": .string(ValueOrigin.DERIVED_SEGMENTATION_ON_MEASURED_PLANE.rawValue)])
        }
        func members(_ m: [FrameMember]) -> JSONValue { .array(m.map { .object(["position_m": .number($0.positionM), "thickness_m": .number($0.thicknessM), "origin": .string(ValueOrigin.DERIVED_CALCULATION.rawValue)]) }) }
        let cond: [JSONValue] = o.condition.map { c in
            .object(["id": .string(c.id), "kind": .string(c.kind.rawValue), "category": .optional(c.category?.rawValue), "label_nl": .optional(c.category?.labelNL),
                     "photo_id": .optional(c.photoId), "region_px": c.region.map(px) ?? .null, "score": .optional(c.score), "detector": c.detector.map(detector) ?? .null,
                     "reasons": .strings(c.reasons.map(code))])
        }
        return .object([
            "object_id": .string(o.id), "element_class": .string(o.elementClass.rawValue), "class_origin": .string(o.classOrigin.rawValue), "label_nl": .string(o.elementClass.labelNL),
            "count": .number(1), "outcome": .string(o.outcome.rawValue), "outcome_reasons": .strings(o.outcomeReasons.map(code)),
            "identity": .string(o.identity.rawValue), "identity_reasons": .strings(o.identityReasons.map(code)), "possible_same_as": .strings(o.possibleSameAs),
            "contour_evidence": .string(o.contourEvidence.rawValue),
            "width": q(g.width), "height": q(g.height), "area": q(g.area),
            "dimension_status": .string(g.status.rawValue), "scale_method": .string(g.scaleMethod), "independent_viewpoints": .number(Double(g.independentViewpoints)),
            "recess_cm": .optional(g.recessCm.map { round($0, 1) }),
            "sections": q(g.sections), "glass_area": q(g.glassArea), "operable_parts": q(g.operableParts), "fixed_parts": q(g.fixedParts),
            "panes": .array(panes), "mullions": members(g.mullions), "transoms": members(g.transoms),
            "condition": .array(cond), "nen2767_condition_score": .null,
            "photo_ids": .strings(o.photoIds), "sighting_ids": .strings(o.sightingIds), "measured_sighting_ids": .strings(g.measuredSightingIds),
            "detectors": .array(o.detectors.map(detector)), "quality_flags": .strings((g.blockingCodes + g.advisoryCodes).map(code)),
            "truncated_by": .strings(o.truncatedBy.map { $0.rawValue }), "notes_nl": .strings(g.notes),
        ])
    }

    static func photo(_ p: PhotoCapture, flags: [String], worldRef: String?) -> JSONValue {
        let f = p.pose.rotate(Vec3(0, 0, 1))
        return .object([
            "photo_id": .string(p.id), "facade_id": .string(p.facadeId), "session_ref": .optional(worldRef), "captured_at": .string(p.capturedAt),
            "depth_source": .string(p.depthSource.rawValue), "depth_valid_fraction": .optional(p.depthQuality.map { round($0.validFraction, 3) }),
            "depth_median_range_m": .optional(p.depthQuality?.medianRangeM.map { round($0, 2) }), "support_depth_frames": .number(Double(p.supportDepthFrames)),
            "tracking_normal": .bool(p.trackingNormal),
            "intrinsics": .object(["fx": .number(round(p.intrinsics.fx, 2)), "fy": .number(round(p.intrinsics.fy, 2)), "cx": .number(round(p.intrinsics.cx, 2)), "cy": .number(round(p.intrinsics.cy, 2)),
                                   "width": .number(Double(p.intrinsics.width)), "height": .number(Double(p.intrinsics.height))]),
            // positie en kijkrichting in het lokale stelsel van de AR-sessie (meter, y omhoog); geen GPS, geen adres
            "camera_position_m": .array([p.pose.t.x, p.pose.t.y, p.pose.t.z].map { .number(round($0, 3)) }),
            "camera_direction": .array([f.x, f.y, f.z].map { .number(round($0, 4)) }),
            "sharpness": .optional(p.imageQuality.map { round($0.sharpness, 1) }), "overexposed_fraction": .optional(p.imageQuality.map { round($0.overexposedFraction, 3) }),
            "flags": .strings(flags.map(code)),
        ])
    }

    public static func build(result r: GevelscanResult, photos: [PhotoCapture], project: ScanProposalV2.Project, elementKey: String?, revision: Int, createdAt: String) throws -> GevelInventoryV1 {
        let flags = Dictionary(uniqueKeysWithValues: r.photoAssessments.map { ($0.photoId, $0.flags) })
        // AR-sessies krijgen een korte, betekenisloze verwijzing (S1, S2, ...) zodat alleen zichtbaar is welke foto's samen vergelijkbaar zijn
        let worlds = Array(Set(photos.compactMap { $0.worldId })).sorted()
        let worldRef = Dictionary(uniqueKeysWithValues: worlds.enumerated().map { ($1, "S\($0 + 1)") })
        let facades: [JSONValue] = r.facades.map { f in
            let c = f.coverage
            return .object([
                "facade_id": .string(f.facadeId), "orientation": .optional(f.orientation), "completeness": .string(f.completeness.rawValue),
                "completeness_reasons": .strings(f.completenessReasons.map(code)),
                "coverage": .object(["determinable": .bool(c.determinable), "width_m": .optional(c.widthM), "height_m": .optional(c.heightM), "covered_fraction": .optional(c.coveredFraction),
                                     "multi_view_fraction": .optional(c.multiViewFraction), "photos_used": .number(Double(c.photosUsed)),
                                     "photos_without_plane": .number(Double(c.photosWithoutPlane)), "flags": .strings(c.flags.map(code))]),
                "photo_ids": .strings(f.photoIds), "totals": totals(f.totals), "capture_requests": .array(f.requests.map(request)), "objects": .array(f.objects.map(object)),
            ])
        }
        let rid = String(clean(r.roundId).prefix(60))
        let body: JSONValue = .object([
            "contract": .string(GevelInventoryV1.contractID),
            "inventory_id": .string("\(String(rid.prefix(24)))-inv-r\(revision)"), "round_id": .string(rid), "revision": .number(Double(revision)), "created_at": .string(createdAt),
            "project": .object(["plan_ref": .string(project.planRef), "mjop_plan_id": .optional(project.mjopPlanId), "building_id": .string(project.buildingId), "bag_pand_id": .optional(project.bagPandId)]),
            "element_key": .optional(elementKey),
            "versions": .object(["pipeline": .string(r.pipelineVersion), "capture": .string(GevelscanVersion.captureAlgorithm), "association": .string(GevelscanVersion.associationAlgorithm),
                                 "geometry": .string(GevelscanVersion.geometryAlgorithm), "condition": .string(GevelscanVersion.conditionAlgorithm),
                                 "thresholds_status": .string(GevelscanVersion.thresholdsStatus)]),
            "recognition": .object(["detectors": .array(r.recognition.detectors.map(detector)), "not_recognizable": .strings(r.recognition.notRecognizable.map { $0.rawValue }),
                                    "derived_by_geometry": .strings(r.recognition.derivedByGeometry.map { $0.rawValue })]),
            "validation": .object(["geometry_field_validated": .bool(r.validation.geometryFieldValidated), "detector_validated": .bool(r.validation.detectorValidated),
                                   "auto_processing_allowed": .bool(r.autoProcessingAllowed), "reasons": .strings(r.validation.blockingReasons)]),
            "facades": .array(facades), "building_totals": totals(r.building),
            "photos": .array(photos.filter { !$0.excluded }.sorted { $0.id < $1.id }.map { photo($0, flags: flags[$0.id] ?? [], worldRef: $0.worldId.flatMap { worldRef[$0] }) }),
            "confirmation": .object(["status": .string("PROPOSED")]), "booking_allowed": .bool(false),
        ])
        return try GevelInventoryV1(validating: body)
    }
}
