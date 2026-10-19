import Foundation
import PhotoWalkCore

/// Schrijft een `photo_walk_capture_v1`-record naar de tijdelijke map van de app. Handmatige actie van de gebruiker; geen automatische upload.
/// De uitvoer moet op een Mac/pc worden gevalideerd met `python -m photo_walk_core.validate <bestand>` (de Swift-uitvoer is niet tegen het schema getest).
enum ExportService {
    @MainActor static func write(_ s: ScanStore) throws -> URL {
        let iso = ISO8601DateFormatter()
        var intrinsicsList: [[String: Any]] = [], idx: [String: String] = [:]
        for k in s.keyframes {
            let key = "\(k.intrinsics.fx)|\(k.intrinsics.fy)|\(k.intrinsics.cx)|\(k.intrinsics.cy)|\(k.intrinsics.width)|\(k.intrinsics.height)"
            if idx[key] == nil {
                idx[key] = "K\(idx.count + 1)"
                intrinsicsList.append(["intrinsics_id": idx[key]!, "fx": k.intrinsics.fx, "fy": k.intrinsics.fy, "cx": k.intrinsics.cx, "cy": k.intrinsics.cy,
                                       "width": k.intrinsics.width, "height": k.intrinsics.height])
            }
        }
        func rowMajor(_ p: Pose) -> [Double] {
            [p.r[0].x, p.r[0].y, p.r[0].z, p.t.x, p.r[1].x, p.r[1].y, p.r[1].z, p.t.y, p.r[2].x, p.r[2].y, p.r[2].z, p.t.z, 0, 0, 0, 1]
        }
        let objects: [[String: Any]] = s.results.map { $0.json }
        let lidar = s.keyframes.contains { $0.depth != nil }
        let record: [String: Any] = [
            "contract": "photo_walk_capture_v1", "contract_version": "1.0.0", "session_id": s.sessionId, "building_id": s.buildingId, "facade_id": s.facadeId,
            "platform": s.isSimulation ? "SIMULATION" : "IOS", "device_model": s.isSimulation ? "synthetic" : "iPhone (onbekend model: UIDevice.current.model wordt bewust niet uitgelezen in dit prototype)",
            "data_origin": s.isSimulation ? "SIMULATION" : "REAL_SENSOR", "validation_level": s.isSimulation ? "SIMULATED" : "REAL_SENSOR_UNVALIDATED",
            "sensor_capabilities": ["lidar": lidar, "scene_depth": lidar, "depth_api": false, "ar_world_tracking": true, "metric_tracking": true, "camera_intrinsics_available": true],
            "coordinate_system": ["pixel": "origin top-left corner of top-left pixel; u right, v down; unit px", "camera": "OpenCV: x right, y down, z forward; unit m",
                                  "world": "right-handed, Y up (gravity aligned), unit m; origin = AR session start",
                                  "pose": "camera_to_world 4x4 row-major as 16 numbers; x_world = R x_camera + t",
                                  "depth": "depth_z: distance along the optical axis in m; 0/NaN invalid", "units": "m, px, m2, degrees"],
            "camera_intrinsics": intrinsicsList,
            "camera_poses": s.keyframes.map { ["frame_id": $0.id, "intrinsics_id": idx["\($0.intrinsics.fx)|\($0.intrinsics.fy)|\($0.intrinsics.cx)|\($0.intrinsics.cy)|\($0.intrinsics.width)|\($0.intrinsics.height)"]!,
                                               "camera_to_world": rowMajor($0.pose), "pose_valid": true] as [String: Any] },
            "capture_timestamp": iso.string(from: s.keyframes.map { $0.timestamp }.min() ?? Date()),
            "image_refs": s.keyframes.map { ["frame_id": $0.id, "ref": "local://\(s.sessionId)/\($0.id).jpg", "timestamp": iso.string(from: $0.timestamp)] },
            "depth_refs": s.keyframes.compactMap { k in k.depth.map { ["frame_id": k.id, "ref": "local://\(s.sessionId)/\(k.id).depth", "width": $0.width, "height": $0.height, "unit": "m", "convention": "depth_z"] as [String: Any] } },
            "tracking_quality": s.keyframes.map { ["frame_id": $0.id, "state": $0.trackingState] },
            "measurement_mode": ["primary_level": lidar ? "A" : "C", "mode": lidar ? "A_METRIC_DEPTH" : "C_REFERENCE", "fallback_chain": lidar ? ["A", "B", "C"] : ["C"], "reason": "automatisch bepaald uit sensoren"] as [String: Any],
            "scale_method": s.results.allSatisfy { $0.status == .UNKNOWN } ? "NONE" : (lidar ? "LIDAR_DEPTH_PLANE" : "REFERENCE_DISTANCE"),
            "scale_evidence": [Any](), "measurement_method_version": "photo_walk_levels_ABC_v1", "processing_version": "photo_walk_core_swift_0.1.0",
            "thresholds": ["threshold_status": "PROVISIONAL_UNVALIDATED"],
            "references": s.references.map { (fid, r) -> [String: Any] in
                ["reference_id": r.referenceId, "frame_id": fid, "p1_px": [r.p1.u, r.p1.v], "p2_px": [r.p2.u, r.p2.v], "distance_m": r.distanceM,
                 "distance_sigma_m": r.distanceSigmaM ?? NSNull(), "plane_id": r.planeId ?? NSNull(), "entered_by": "inspecteur"] }.sorted { ($0["reference_id"] as! String) < ($1["reference_id"] as! String) }, "observations": s.observations.map { ["observation_id": $0.id, "frame_id": $0.frameId, "corner_source": $0.source.rawValue, "obstruction_reported": $0.obstruction] as [String: Any] },
            "objects": objects, "coverage": NSNull(), "scan_label": "SEMI_AUTOMATIC",
            "summary": ["object_count": s.results.count, "by_status": [String: Any](), "review_required": s.results.filter { $0.reviewRequired }.count,
                        "note": "Totalen zijn voorlopig en per status gescheiden; ze mogen niet worden opgeteld tot een definitieve hoeveelheid."] as [String: Any],
            "privacy": ["raw_media_included": false, "external_calls": 0, "location_stored": false, "processing": "LOCAL_ONLY", "retention_proposal": "VOORSTEL (nog niet vastgesteld): ruwe beelden en dieptekaarten blijven op het toestel; verwijderen na review of uiterlijk 30 dagen."] as [String: Any],
            "invariants": ["quantity_layer": "PROVISIONAL", "approval_state": "PENDING_HUMAN_APPROVAL", "is_final": false, "human_decision_registered": false, "approvals_simulated": false,
                           "cost_link": NSNull(), "kengetal_link": NSNull(), "price_link": NSNull(), "external_vision_calls": 0, "images_uploaded": false] as [String: Any],
        ]
        let data = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys, .prettyPrinted])
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("photo_walk_\(s.sessionId).json")
        try data.write(to: url, options: .completeFileProtection)
        return url
    }
}
