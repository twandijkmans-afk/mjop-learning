import CryptoKit
import Foundation
import PhotoWalkCore
import UIKit

/// Meetdiagnose-export (`photo_walk_measure_diagnostics_v1`, versie 1.1.0: voegt het blok `extended_diagnostics` toe): klein, lokaal JSON-bestand met uitsluitend numerieke diagnostiek van EEN kozijnmeting.
/// Bevat bewust GEEN foto's, GEEN puntenwolken, GEEN absolute camerapositie en GEEN locatie. De sessie wordt alleen als 12 hex-tekens van een sha256 vermeld.
/// Valideren/analyseren op een pc: `python -m photo_walk_core.validate <bestand>`.
enum DiagnosticsExport {
    static func snake(_ s: String) -> String {
        var out = ""
        for ch in s { if ch.isUppercase { out += "_" + String(ch).lowercased() } else { out.append(ch) } }
        return out
    }

    /// De gebruikte (provisional) drempels, uit de Config van de kern.
    static func thresholds() -> [String: Any] {
        var d: [String: Any] = [:]
        for c in Mirror(reflecting: Config()).children {
            guard let l = c.label else { continue }
            if let v = c.value as? Double { d[snake(l)] = v } else if let v = c.value as? Int { d[snake(l)] = v }
        }
        d["threshold_status"] = "PROVISIONAL_UNVALIDATED"
        return d
    }

    static func sessionRef(_ id: String) -> String {
        SHA256.hash(data: Data(id.utf8)).map { String(format: "%02x", $0) }.joined().prefix(12).description
    }

    @MainActor static func record(_ s: ScanStore, observationId: String) -> [String: Any]? {
        guard let o = s.observation(observationId), let kf = s.keyframe(o.frameId), let m = s.measures[observationId] else { return nil }
        let r = m.result
        let status = Status.status(for: r, viewCount: 1)          // diagnose van één waarneming = één foto: nooit MEASURED
        var width: Any = NSNull(), height: Any = NSNull(), area: Any = NSNull()
        if r.ok, let w = r.width, let h = r.height {
            let dw = roundedMillimeters(w), dh = roundedMillimeters(h)
            width = NSDecimalNumber(decimal: dw).doubleValue; height = NSDecimalNumber(decimal: dh).doubleValue
            area = NSDecimalNumber(decimal: grossAreaM2(width: dw, height: dh)).doubleValue
        }
        let flags: [[String: Any]] = r.flags.map { ["code": $0.code, "severity": $0.severity.rawValue, "detail": $0.detail ?? NSNull()] }
        var hints: [String] = []
        for f in r.flags where f.severity == .BLOCKING && !hints.contains(f.instruction_nl) { hints.append(f.instruction_nl) }
        if let dh = r.diag["hints_nl"] as? [String] { for h in dh where !hints.contains(h) { hints.append(h) } }
        if hints.isEmpty { hints = ["Geen blokkerende problemen."] }
        let iso = ISO8601DateFormatter()
        // Spec 1.1.0: extra, ALLEEN-LEZEN diagnostiek, berekend NA het resultaat (zie ExtendedDiagnostics). Geen invloed op een maat, vlag of status.
        var labels: [String: String] = [kf.id: kf.trackingState]
        for sd in kf.supportDepths { labels[sd.id] = sd.trackingState }
        var gray: GrayImage? = nil, sat: GrayImage? = nil
        if let url = kf.imageURL, let imgs = ladderImages(url) { gray = imgs.gray; sat = imgs.saturation }
        let ext = ExtendedDiagnostics.compute(view: Measurer.input(kf), corners: o.corners, result: r, seed: stableSeed(o.id), contourStatus: o.outerContour.rawValue,
                                              trackingLabels: labels, imageGray: gray, imageSaturation: sat)
        return [
            "contract": "photo_walk_measure_diagnostics_v1", "contract_version": "1.1.0", "created_utc": iso.string(from: Date()),
            "platform": s.isSimulation ? "SIMULATION" : "IOS", "data_origin": s.isSimulation ? "SIMULATION" : "REAL_SENSOR",
            "app_build": "photo_walk_ios_lidar_v2/" + ((Bundle.main.infoDictionary?["CFBundleVersion"] as? String) ?? "dev"),
            "session_ref": sessionRef(s.sessionId), "frame_id": o.frameId, "observation_id": o.id,
            "camera": ["fx": kf.intrinsics.fx, "fy": kf.intrinsics.fy, "cx": kf.intrinsics.cx, "cy": kf.intrinsics.cy, "width": kf.intrinsics.width, "height": kf.intrinsics.height] as [String: Any],
            "corners_px": o.corners.map { [($0.u * 100).rounded() / 100, ($0.v * 100).rounded() / 100] },
            "measurement": ["status": status.rawValue, "width_m": width, "height_m": height, "area_m2": area, "scale_method": r.scaleMethod,
                            "level": r.ok ? r.level.rawValue : NSNull(), "feedback": m.feedback.rawValue] as [String: Any],
            "result_flags": flags, "algorithm": jsonSafe(r.diag), "thresholds": thresholds(), "user_hints_nl": hints,
            "privacy": ["images_included": false, "point_cloud_included": false, "absolute_pose_included": false, "location_included": false] as [String: Any],
            "extended_diagnostics": ext,
        ]
    }

    /// Grijs- en verzadigingsbeeld (alleen voor de randsterkte-getallen in de diagnose) uit het lokaal bewaarde beeld. Het beeld zelf verlaat de functie niet
    /// en komt niet in het diagnosebestand.
    static func ladderImages(_ url: URL) -> (gray: GrayImage, saturation: GrayImage)? {
        guard let cg = UIImage(contentsOfFile: url.path)?.cgImage, let g = GrayImageLoader.gray(cg) else { return nil }
        let w = cg.width, h = cg.height
        var rgba = [UInt8](repeating: 0, count: w * h * 4)
        let ok: Bool = rgba.withUnsafeMutableBytes { (buf: UnsafeMutableRawBufferPointer) -> Bool in
            guard let ctx = CGContext(data: buf.baseAddress, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        guard ok else { return nil }
        return (g, ExtendedDiagnostics.saturationChannel(rgba: rgba, width: w, height: h))
    }

    @MainActor static func write(_ s: ScanStore, observationId: String) throws -> URL {
        guard let rec = record(s, observationId: observationId) else { throw CocoaError(.fileNoSuchFile) }
        let data = try JSONSerialization.data(withJSONObject: jsonSafe(rec), options: [.sortedKeys, .prettyPrinted])
        let dir = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let url = dir.appendingPathComponent("meetdiagnose_\(sessionRef(s.sessionId))_\(observationId).json")
        try data.write(to: url, options: .completeFileProtection)
        return url
    }
}
