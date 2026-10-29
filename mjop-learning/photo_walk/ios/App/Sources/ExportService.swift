import Foundation
import PhotoWalkCore

/// Schrijft een `photo_walk_capture_v1`-record naar de map Documents van de app (zichtbaar in de Bestanden-app dankzij UIFileSharingEnabled).
/// Handmatige actie van de gebruiker; geen automatische upload. Het record bevat geen beelden, geen dieptekaarten en geen locatie.
/// Valideer de export op een pc met `python -m photo_walk_core.validate <bestand>` (de Swift-uitvoer is nog niet tegen het schema gevalideerd).
enum ExportService {
    private static func intrinsicsKey(_ i: Intrinsics) -> String { "\(i.fx)|\(i.fy)|\(i.cx)|\(i.cy)|\(i.width)|\(i.height)" }

    private static func rowMajor(_ p: Pose) -> [Double] {
        [p.r[0].x, p.r[0].y, p.r[0].z, p.t.x, p.r[1].x, p.r[1].y, p.r[1].z, p.t.y, p.r[2].x, p.r[2].y, p.r[2].z, p.t.z, 0, 0, 0, 1]
    }

    @MainActor static func record(_ s: ScanStore) -> [String: Any] {
        let iso = ISO8601DateFormatter()
        var intrinsicsList: [[String: Any]] = []
        var ids: [String: String] = [:]
        for k in s.keyframes {
            let key = intrinsicsKey(k.intrinsics)
            if ids[key] == nil {
                let id = "K\(ids.count + 1)"
                ids[key] = id
                let e: [String: Any] = ["intrinsics_id": id, "fx": k.intrinsics.fx, "fy": k.intrinsics.fy, "cx": k.intrinsics.cx, "cy": k.intrinsics.cy,
                                        "width": k.intrinsics.width, "height": k.intrinsics.height]
                intrinsicsList.append(e)
            }
        }
        let hasDepth = s.keyframes.contains { $0.depth != nil }
        let allUnknown = s.results.allSatisfy { $0.status == .UNKNOWN }
        var r: [String: Any] = [:]
        r["contract"] = "photo_walk_capture_v1"
        r["contract_version"] = "1.2.0"          // 1.2.0: optionele gevelopbouw (facade_role, facade_composition); oudere records blijven geldig
        r["capture_mode"] = s.keyframes.isEmpty || s.observations.contains(where: { $0.detection == nil }) ? "KEYFRAME_MANUAL" : "PHOTO"
        r["session_id"] = s.sessionId
        r["building_id"] = s.buildingId
        r["facade_id"] = s.facadeId
        r["platform"] = s.isSimulation ? "SIMULATION" : "IOS"
        r["device_model"] = s.isSimulation ? "synthetic" : "iPhone"
        r["data_origin"] = s.isSimulation ? "SIMULATION" : "REAL_SENSOR"
        r["validation_level"] = s.isSimulation ? "SIMULATED" : "REAL_SENSOR_UNVALIDATED"
        let caps: [String: Any] = ["lidar": hasDepth, "scene_depth": hasDepth, "depth_api": false, "ar_world_tracking": true,
                                   "metric_tracking": true, "camera_intrinsics_available": true]
        r["sensor_capabilities"] = caps
        let coord: [String: Any] = [
            "pixel": "origin top-left corner of top-left pixel; u right, v down; unit px",
            "camera": "OpenCV: x right, y down, z forward; unit m",
            "world": "right-handed, Y up (gravity aligned), unit m; origin = AR session start",
            "pose": "camera_to_world 4x4 row-major as 16 numbers; x_world = R x_camera + t",
            "depth": "depth_z: distance along the optical axis in m; 0/NaN invalid",
            "units": "m, px, m2, degrees"]
        r["coordinate_system"] = coord
        r["camera_intrinsics"] = intrinsicsList
        r["camera_poses"] = s.keyframes.map { k -> [String: Any] in
            ["frame_id": k.id, "intrinsics_id": ids[intrinsicsKey(k.intrinsics)] ?? "K1", "camera_to_world": rowMajor(k.pose), "pose_valid": true]
        }
        r["capture_timestamp"] = iso.string(from: s.keyframes.map { $0.timestamp }.min() ?? Date())
        r["image_refs"] = s.keyframes.map { k -> [String: Any] in
            ["frame_id": k.id, "ref": "local://\(s.sessionId)/\(k.id).jpg", "timestamp": iso.string(from: k.timestamp)]
        }
        r["depth_refs"] = s.keyframes.compactMap { k -> [String: Any]? in
            guard let d = k.depth else { return nil }
            return ["frame_id": k.id, "ref": "local://\(s.sessionId)/\(k.id).depth", "width": d.width, "height": d.height, "unit": "m", "convention": "depth_z"]
        }
        r["tracking_quality"] = s.keyframes.map { k -> [String: Any] in ["frame_id": k.id, "state": k.trackingState] }
        let mode: [String: Any] = ["primary_level": hasDepth ? "A" : "C", "mode": hasDepth ? "A_METRIC_DEPTH" : "C_REFERENCE",
                                   "fallback_chain": hasDepth ? ["A", "C"] : ["C"], "reason": "automatisch bepaald uit de aanwezige dieptegegevens"]
        r["measurement_mode"] = mode
        let methods = Set(s.results.filter { $0.status != .UNKNOWN }.map { $0.result.scaleMethod })
        r["scale_method"] = methods.isEmpty || allUnknown ? "NONE" : (methods.count == 1 ? methods.first! : "MIXED")
        r["scale_evidence"] = [Any]()
        r["measurement_method_version"] = "photo_walk_levels_ABC_v2_lidar_multiframe"
        r["processing_version"] = "photo_walk_core_swift_0.1.0"
        r["thresholds"] = ["threshold_status": "PROVISIONAL_UNVALIDATED"]
        r["references"] = s.references.map { (fid, ref) -> [String: Any] in
            ["reference_id": ref.referenceId, "frame_id": fid, "p1_px": [ref.p1.u, ref.p1.v], "p2_px": [ref.p2.u, ref.p2.v], "distance_m": ref.distanceM,
             "distance_sigma_m": ref.distanceSigmaM ?? NSNull(), "plane_id": ref.planeId ?? NSNull(), "entered_by": "inspecteur",
             "anchor_observation_id": ref.anchorObservationId ?? NSNull(), "kind": ref.kind.rawValue]
        }.sorted { ($0["reference_id"] as? String ?? "") < ($1["reference_id"] as? String ?? "") }
        r["observations"] = s.observations.filter { !$0.rejected }.map { o -> [String: Any] in
            var d: [String: Any] = ["observation_id": o.id, "frame_id": o.frameId, "corner_source": o.source.rawValue, "obstruction_reported": o.obstruction]
            if let det = o.detection { d["detection"] = ["detector": det.detector, "score": det.score, "status": "CANDIDATE_UNVERIFIED"] as [String: Any] }
            d["facade_role"] = ["role": "FRAME_OUTER", "outer_contour_status": o.outerContour.rawValue, "evidence": o.evidence.rawValue,
                                "proposed_outer_px": o.proposedOuter.map { $0.map { [$0.u, $0.v] } } ?? NSNull(),
                                "glass_pane_refs": s.glassPanes(ofObservation: o.id).map { $0.id }] as [String: Any]
            return d
        }
        r["rejected_candidates"] = s.observations.filter { $0.rejected }.map { o -> [String: Any] in
            let asGlass = s.facadeElements.contains { $0.role == .GLASS_PANE && $0.frameId == o.frameId && $0.corners == o.corners }
            return ["observation_id": o.id, "frame_id": o.frameId, "detector": o.detection?.detector ?? "MANUAL",
                    "reason": asGlass ? "door inspecteur gemarkeerd als glasvlak: geen kozijn" : "door inspecteur afgewezen: geen kozijn"]
        }
        r["facade_composition"] = facadeComposition(s)
        let detectors = DetectorCatalog.available().map { $0.name }
        r["detection_summary"] = ["detectors": detectors, "core_ml_model_installed": DetectorCatalog.coreMLModelURL != nil, "validated_on_real_buildings": false,
                                  "note": "Kandidaten van een algemene rechthoekdetector; niet gevalideerd als kozijndetector."] as [String: Any]
        r["objects"] = s.results.map { $0.json }
        r["coverage"] = NSNull()
        let srcs = Set(s.observations.filter { !$0.rejected }.map { $0.source })
        r["scan_label"] = srcs.isEmpty ? "NO_OBSERVATIONS" : (srcs == [.AUTO_DETECTED_UNCONFIRMED] ? "AUTOMATIC_UNREVIEWED" : (srcs.isSubset(of: [.AUTO_DETECTED_CONFIRMED]) ? "AUTOMATIC_CANDIDATES_HUMAN_CONFIRMED" : "SEMI_AUTOMATIC"))
        var byStatus: [String: Any] = [:]
        for st in ["MEASURED", "DERIVED", "ESTIMATED", "UNKNOWN"] {
            let sel = s.results.filter { $0.status.rawValue == st }
            let total = sel.compactMap { $0.areaM2 }.compactMap { Decimal(string: $0) }.reduce(Decimal(0), +)
            byStatus[st] = ["count": sel.count, "gross_area_m2": st == "UNKNOWN" ? NSNull() : decimalString(total) as Any]
        }
        r["summary"] = ["object_count": s.results.count, "by_status": byStatus, "review_required": s.results.filter { $0.reviewRequired }.count,
                        "note": "Totalen zijn voorlopig en per status gescheiden; ze mogen niet worden opgeteld tot een definitieve hoeveelheid."] as [String: Any]
        r["privacy"] = ["raw_media_included": false, "external_calls": 0, "location_stored": false, "processing": "LOCAL_ONLY",
                        "retention_proposal": "VOORSTEL (nog niet vastgesteld): ruwe beelden en dieptekaarten blijven op het toestel; verwijderen na review of uiterlijk 30 dagen."] as [String: Any]
        r["invariants"] = ["quantity_layer": "PROVISIONAL", "approval_state": "PENDING_HUMAN_APPROVAL", "is_final": false, "human_decision_registered": false,
                           "approvals_simulated": false, "cost_link": NSNull(), "kengetal_link": NSNull(), "price_link": NSNull(),
                           "external_vision_calls": 0, "images_uploaded": false] as [String: Any]
        return r
    }

    /// Gevelopbouw per foto (photo_walk_capture_v1 1.2.0, optioneel). Voorlopig en niet gevalideerd; geen boeking, geen kosten.
    @MainActor static func facadeComposition(_ s: ScanStore) -> [String: Any] {
        func pts(_ p: [Pixel]) -> [[Double]] { p.map { [($0.u * 100).rounded() / 100, ($0.v * 100).rounded() / 100] } }
        var frames: [[String: Any]] = []
        for k in s.keyframes where s.observations.contains(where: { $0.frameId == k.id }) || s.facadeElements.contains(where: { $0.frameId == k.id }) {
            guard let fc = s.facadeComposition(frameId: k.id) else { continue }
            let elems = s.facadeElements.filter { $0.frameId == k.id }.map { e -> [String: Any] in
                var area: Any = NSNull()
                if e.role == .GLASS_PANE, !e.rejected, let pid = e.parentObservationId, let r = s.measures[pid]?.result, r.ok, let n = r.planeN, let d = r.planeD,
                   let a = FacadeComposition.planarPolygonAreaM2(e.corners, pose: k.pose, intr: k.intrinsics, n: n, d: d) {
                    area = decimalString(FacadeComposition.round3(a))
                }
                return ["element_id": e.id, "role": e.role.rawValue, "parent_observation_ref": e.parentObservationId ?? NSNull(), "polygon_px": pts(e.corners),
                        "original_polygon_px": pts(e.originalCorners), "source": e.source.rawValue, "rejected": e.rejected, "area_m2": area]
            }
            frames.append(["frame_id": k.id, "facade_polygon_px": s.facadePolygon(frameId: k.id).map { pts($0.corners) } ?? NSNull(),
                           "facade_plane_source": fc.planeSource.rawValue, "elements": elems, "quantities": fc.result.quantitiesJSON, "flags": fc.result.flags,
                           "plausibility": ["source": "3DBAG", "b3_opp_buitenmuur_m2": NSNull(), "flags": [String](),
                                            "note": "Alleen een aanvullende controle (nooit bewijs dat een fotometing klopt); 3D BAG-waarde niet beschikbaar in de scanner."] as [String: Any]])
        }
        return ["version": "1.0.0", "frames": frames,
                "note": "Voorlopig en niet gevalideerd op echte gebouwen. Opening = buitenmaat kozijn (aanname). Glas en buitenkozijn apart; het onderhouds-/schilderoppervlak van kozijnen wordt niet afgeleid. Zonder betrouwbare schaal: UNKNOWN."]
    }

    @MainActor static func write(_ s: ScanStore) throws -> URL {
        let data = try JSONSerialization.data(withJSONObject: record(s), options: [.sortedKeys, .prettyPrinted])
        let dir = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let url = dir.appendingPathComponent("photo_walk_\(s.sessionId).json")
        try data.write(to: url, options: .completeFileProtection)
        return url
    }
}
