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
        r["contract_version"] = "1.0.0"
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
        r["measurement_method_version"] = "photo_walk_levels_ABC_v1"
        r["processing_version"] = "photo_walk_core_swift_0.1.0"
        r["thresholds"] = ["threshold_status": "PROVISIONAL_UNVALIDATED"]
        r["references"] = s.references.map { (fid, ref) -> [String: Any] in
            ["reference_id": ref.referenceId, "frame_id": fid, "p1_px": [ref.p1.u, ref.p1.v], "p2_px": [ref.p2.u, ref.p2.v], "distance_m": ref.distanceM,
             "distance_sigma_m": ref.distanceSigmaM ?? NSNull(), "plane_id": ref.planeId ?? NSNull(), "entered_by": "inspecteur"]
        }.sorted { ($0["reference_id"] as? String ?? "") < ($1["reference_id"] as? String ?? "") }
        r["observations"] = s.observations.map { o -> [String: Any] in
            ["observation_id": o.id, "frame_id": o.frameId, "corner_source": o.source.rawValue, "obstruction_reported": o.obstruction]
        }
        r["objects"] = s.results.map { $0.json }
        r["coverage"] = NSNull()
        r["scan_label"] = s.observations.allSatisfy({ $0.source == .AUTO_DETECTED_CONFIRMED }) && !s.observations.isEmpty ? "AUTOMATIC_CANDIDATES_HUMAN_CONFIRMED" : "SEMI_AUTOMATIC"
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

    @MainActor static func write(_ s: ScanStore) throws -> URL {
        let data = try JSONSerialization.data(withJSONObject: record(s), options: [.sortedKeys, .prettyPrinted])
        let dir = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let url = dir.appendingPathComponent("photo_walk_\(s.sessionId).json")
        try data.write(to: url, options: .completeFileProtection)
        return url
    }
}
