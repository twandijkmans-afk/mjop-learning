import CryptoKit
import Foundation

/// Ontwikkelbundel (`photo_walk_capture_bundle_v1`): alleen voor ONTWIKKELING en KALIBRATIE, standaard UIT, uitsluitend lokaal op het toestel.
/// Zelfde formaat als de Python-referentie (`photo_walk_core/capture_bundle.py`). Bewaard: dieptekaarten, intrinsics, kaderhoeken, tracking, de helling t.o.v. de zwaartekracht
/// en de poses van de steunframes RELATIEF aan het hoofdframe; optioneel de volledige foto. NIET bewaard: locatie, kompas, absolute positie of oriëntatie, gebruiker, adres.
/// Zie docs/dev_capture_bundle.md.
public enum CaptureBundle {
    public static let contract = "photo_walk_capture_bundle_v1"
    public static let dirPrefix = "bundle_"
    public struct BundleError: Error { public let message: String }

    static func sha(_ d: Data) -> String { SHA256.hash(data: d).map { String(format: "%02x", $0) }.joined() }
    public static func sessionRef(_ id: String) -> String { String(sha(Data(id.utf8)).prefix(12)) }
    static func r9(_ x: Double) -> Double { (x * 1e9).rounded() / 1e9 }

    /// Kolommen van R (rotatie uit rijen).
    static func cols(_ p: Pose) -> [Vec3] {
        [Vec3(p.r[0].x, p.r[1].x, p.r[2].x), Vec3(p.r[0].y, p.r[1].y, p.r[2].y), Vec3(p.r[0].z, p.r[1].z, p.r[2].z)]
    }

    /// R_rel = Rc^T R (rijen-hoofdvolgorde, 9 getallen); t_rel = Rc^T (t - tc). Geen absolute positie of oriëntatie.
    public static func relativePose(capture: Pose, pose: Pose) -> (rotation: [Double], translation: [Double]) {
        let cc = cols(capture), c = cols(pose)
        var rot: [Double] = []
        for i in 0..<3 { for j in 0..<3 { rot.append(cc[i].dot(c[j])) } }
        let t = capture.rotateInverse(pose.t - capture.t)
        return (rot, [t.x, t.y, t.z])
    }

    /// Camera->wereld-rotatie met R^T * UP = u en een vaste, willekeurige yaw (de uitkomst is yaw-onafhankelijk).
    static func captureRotation(_ uIn: Vec3) -> Pose {
        let u = uIn.normalized
        var x = Vec3(1, 0, 0) - u * Vec3(1, 0, 0).dot(u)
        if x.norm < 1e-6 { x = Vec3(0, 0, 1) - u * u.z }
        x = x.normalized
        let z = x.cross(u).normalized
        return Pose(rows: [x, u, z], t: .zero)
    }

    static func intr(_ i: Intrinsics) -> [String: Any] { ["fx": i.fx, "fy": i.fy, "cx": i.cx, "cy": i.cy, "width": i.width, "height": i.height] }

    public static func thresholdsSha256(_ thresholds: [String: Any]) -> String {
        let d = (try? JSONSerialization.data(withJSONObject: thresholds, options: [.sortedKeys])) ?? Data()
        return sha(d)
    }

    @discardableResult
    public static func write(root: URL, view: ViewInput, corners: [Pixel], sessionId: String, observationId: String, appBuild: String, thresholds: [String: Any],
                             photo: Data?, createdUTC: String? = nil, trackingLabels: [String: String] = [:]) throws -> URL {
        let fm = FileManager.default
        let dir = root.appendingPathComponent("\(dirPrefix)\(sessionRef(sessionId))_\(observationId)", isDirectory: true)
        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        var files: [[String: Any]] = [], frames: [[String: Any]] = []
        let all: [(String, ViewInput)] = [("CAPTURE", view)] + view.supports.map { ("SUPPORT", $0) }
        for (role, v) in all {
            let rel = relativePose(capture: view.pose, pose: v.pose)
            var fr: [String: Any] = ["id": v.frameId, "role": role, "tracking": trackingLabels[v.frameId] ?? (v.trackingNormal ? "NORMAL" : "LIMITED"), "intrinsics": intr(v.intrinsics),
                                     "rotation_rel_row_major": rel.rotation.map(r9), "translation_rel_m": rel.translation.map(r9), "depth": NSNull()]
            if let dm = v.depth {
                var le = [UInt32](); le.reserveCapacity(dm.values.count)
                for f in dm.values { le.append(f.bitPattern.littleEndian) }
                let raw = le.withUnsafeBufferPointer { Data(buffer: $0) }
                let fn = "depth_\(v.frameId).f32"
                try raw.write(to: dir.appendingPathComponent(fn), options: .completeFileProtection)
                files.append(["name": fn, "kind": "DEPTH_F32_LE", "bytes": raw.count, "sha256": sha(raw)])
                fr["depth"] = ["file": fn, "width": dm.width, "height": dm.height, "dtype": "float32_le", "invalid": "NaN of 0"] as [String: Any]
            }
            frames.append(fr)
        }
        if let p = photo {
            try p.write(to: dir.appendingPathComponent("photo.jpg"), options: .completeFileProtection)
            files.append(["name": "photo.jpg", "kind": "PHOTO_FULL_RESOLUTION", "bytes": p.count, "sha256": sha(p)])
        }
        let u = view.pose.rotateInverse(Vec3(0, 1, 0))
        let created = createdUTC ?? ISO8601DateFormatter().string(from: Date())
        let manifest: [String: Any] = [
            "contract": contract, "contract_version": "1.0.0", "created_utc": created, "app_build": appBuild, "session_ref": sessionRef(sessionId), "observation_id": observationId,
            "frame_id": view.frameId, "corners_px": corners.map { [($0.u * 10000).rounded() / 10000, ($0.v * 10000).rounded() / 10000] },
            "capture_attitude": ["gravity_up_in_camera": [r9(u.x), r9(u.y), r9(u.z)],
                                 "note": "richting van 'omhoog' in het camerastelsel van het hoofdframe; geen positie, geen kompas, geen absolute oriëntatie"] as [String: Any],
            "frames": frames, "thresholds_sha256": thresholdsSha256(thresholds), "files": files,
            "privacy": ["dev_mode_only": true, "local_only": true, "full_photo_included": photo != nil, "absolute_pose_included": false, "location_included": false,
                        "compass_included": false, "user_or_address_included": false] as [String: Any],
            "storage": ["excluded_from_backup": true, "never_uploaded": true,
                        "delete": "app: meetdiagnose-scherm > Verwijder ontwikkelbundels; of verwijder de app (het hele toestel-sandbox gaat dan weg)"] as [String: Any],
        ]
        let data = try JSONSerialization.data(withJSONObject: manifest, options: [.sortedKeys, .prettyPrinted])
        try data.write(to: dir.appendingPathComponent("manifest.json"), options: .completeFileProtection)
        excludeFromBackup(dir)
        return dir
    }

    /// Sluit de map (en wat erin staat) uit van iCloud/iTunes-back-ups.
    public static func excludeFromBackup(_ dir: URL) {
        var u = dir
        var rv = URLResourceValues(); rv.isExcludedFromBackup = true
        try? u.setResourceValues(rv)
    }

    public static func isExcludedFromBackup(_ dir: URL) -> Bool {
        ((try? dir.resourceValues(forKeys: [.isExcludedFromBackupKey]))?.isExcludedFromBackup) ?? false
    }

    /// Leest een bundel, controleert alle sha256's en bouwt het ViewInput voor een exacte replay.
    public static func read(_ dir: URL) throws -> (view: ViewInput, corners: [Pixel], manifest: [String: Any]) {
        guard let m = try JSONSerialization.jsonObject(with: Data(contentsOf: dir.appendingPathComponent("manifest.json"))) as? [String: Any],
              m["contract"] as? String == contract, let files = m["files"] as? [[String: Any]], let frames = m["frames"] as? [[String: Any]],
              let att = m["capture_attitude"] as? [String: Any], let g = att["gravity_up_in_camera"] as? [Double], g.count == 3,
              let cs = m["corners_px"] as? [[Double]] else { throw BundleError(message: "geen geldige ontwikkelbundel") }
        for f in files {
            let d = try Data(contentsOf: dir.appendingPathComponent(f["name"] as? String ?? ""))
            if sha(d) != (f["sha256"] as? String) || d.count != (f["bytes"] as? Int) { throw BundleError(message: "bundelbestand beschadigd of gewijzigd: \(f["name"] ?? "?")") }
        }
        let rc = captureRotation(Vec3(g[0], g[1], g[2]))
        var views: [(String, ViewInput)] = []
        for fr in frames {
            guard let i = fr["intrinsics"] as? [String: Any], let rr = fr["rotation_rel_row_major"] as? [Double], rr.count == 9, let tr = fr["translation_rel_m"] as? [Double], tr.count == 3,
                  let fx = i["fx"] as? Double, let fy = i["fy"] as? Double, let cx = i["cx"] as? Double, let cy = i["cy"] as? Double, let w = i["width"] as? Int, let h = i["height"] as? Int
            else { throw BundleError(message: "frame onvolledig") }
            // R = Rc * R_rel (rijen): rij_k(R)[j] = sum_i Rc[k][i] * R_rel[i][j]
            var rows: [Vec3] = []
            for k in 0..<3 {
                let rck = rc.r[k]
                rows.append(Vec3(rck.x * rr[0] + rck.y * rr[3] + rck.z * rr[6], rck.x * rr[1] + rck.y * rr[4] + rck.z * rr[7], rck.x * rr[2] + rck.y * rr[5] + rck.z * rr[8]))
            }
            let t = rc.rotate(Vec3(tr[0], tr[1], tr[2]))
            var depth: DepthMap? = nil
            if let dd = fr["depth"] as? [String: Any], let fn = dd["file"] as? String, let dw = dd["width"] as? Int, let dh = dd["height"] as? Int {
                let raw = try Data(contentsOf: dir.appendingPathComponent(fn))
                guard raw.count == dw * dh * 4 else { throw BundleError(message: "diepte heeft onverwachte grootte") }
                var vals = [Float](); vals.reserveCapacity(dw * dh)
                raw.withUnsafeBytes { (p: UnsafeRawBufferPointer) in
                    for k in 0..<(dw * dh) { vals.append(Float(bitPattern: UInt32(littleEndian: p.loadUnaligned(fromByteOffset: k * 4, as: UInt32.self)))) }
                }
                depth = DepthMap(width: dw, height: dh, values: vals)
            }
            views.append((fr["role"] as? String ?? "", ViewInput(frameId: fr["id"] as? String ?? "", intrinsics: Intrinsics(fx: fx, fy: fy, cx: cx, cy: cy, width: w, height: h),
                                                                   pose: Pose(rows: rows, t: t), trackingNormal: (fr["tracking"] as? String) == "NORMAL", depth: depth)))
        }
        guard var cap = views.first(where: { $0.0 == "CAPTURE" })?.1 else { throw BundleError(message: "hoofdframe ontbreekt") }
        cap.supports = views.filter { $0.0 == "SUPPORT" }.map { $0.1 }
        return (cap, cs.map { Pixel($0[0], $0[1]) }, m)
    }

    public static func list(root: URL) -> [URL] {
        ((try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.lastPathComponent.hasPrefix(dirPrefix) && FileManager.default.fileExists(atPath: $0.appendingPathComponent("manifest.json").path) }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    /// Verwijdert één bundel volledig.
    public static func delete(_ dir: URL) throws {
        guard dir.lastPathComponent.hasPrefix(dirPrefix), FileManager.default.fileExists(atPath: dir.appendingPathComponent("manifest.json").path) else { throw BundleError(message: "geen ontwikkelbundel") }
        try FileManager.default.removeItem(at: dir)
    }

    @discardableResult public static func deleteAll(root: URL) -> Int {
        var n = 0
        for d in list(root: root) { if (try? delete(d)) != nil { n += 1 } }
        return n
    }
}
