import ARKit
import PhotoWalkCore

/// Omzetting van ARKit-types naar het platformonafhankelijke contract (zie docs/arkit_adapter.md). Vrij van actor-isolatie, zodat het ook vanuit de ARSession-delegate kan.
enum ARConvert {
    static func trackingString(_ s: ARCamera.TrackingState) -> String {
        switch s {
        case .normal: return "NORMAL"
        case .notAvailable: return "NOT_AVAILABLE"
        case .limited(let r):
            switch r {
            case .initializing: return "LIMITED_INITIALIZING"
            case .excessiveMotion: return "LIMITED_EXCESSIVE_MOTION"
            case .insufficientFeatures: return "LIMITED_INSUFFICIENT_FEATURES"
            case .relocalizing: return "LIMITED_RELOCALIZING"
            @unknown default: return "NOT_AVAILABLE"
            }
        }
    }

    static func intrinsics(_ f: ARFrame) -> Intrinsics {
        let K = f.camera.intrinsics, res = f.camera.imageResolution
        return Intrinsics(fx: Double(K[0][0]), fy: Double(K[1][1]), cx: Double(K[2][0]), cy: Double(K[2][1]), width: Int(res.width), height: Int(res.height))
    }

    /// ARKit-camera (x rechts, y omhoog, z achteruit) -> OpenCV-camera (x rechts, y omlaag, z vooruit): R_cv = R_arkit * diag(1,-1,-1).
    static func pose(_ f: ARFrame) -> Pose {
        let T = f.camera.transform
        let flip: [Float] = [1, -1, -1]
        func row(_ i: Int) -> Vec3 { Vec3(Double(T.columns.0[i] * flip[0]), Double(T.columns.1[i] * flip[1]), Double(T.columns.2[i] * flip[2])) }
        return Pose(rows: [row(0), row(1), row(2)], t: Vec3(Double(T.columns.3.x), Double(T.columns.3.y), Double(T.columns.3.z)))
    }

    /// depth_z in meter; laag vertrouwen (0) wordt als ongeldig behandeld (drempelbesluit niet gevalideerd).
    static func depthMap(_ d: ARDepthData?) -> DepthMap? {
        guard let sd = d else { return nil }
        let buf = sd.depthMap
        CVPixelBufferLockBaseAddress(buf, .readOnly); defer { CVPixelBufferUnlockBaseAddress(buf, .readOnly) }
        let w = CVPixelBufferGetWidth(buf), h = CVPixelBufferGetHeight(buf)
        guard let base = CVPixelBufferGetBaseAddress(buf) else { return nil }
        let stride = CVPixelBufferGetBytesPerRow(buf) / MemoryLayout<Float32>.size
        var vals = [Float](repeating: .nan, count: w * h)
        var conf: [UInt8]? = nil
        if let cm = sd.confidenceMap {
            CVPixelBufferLockBaseAddress(cm, .readOnly)
            if let cb = CVPixelBufferGetBaseAddress(cm) {
                let cs = CVPixelBufferGetBytesPerRow(cm)
                conf = (0..<h).flatMap { r in (0..<w).map { c in cb.load(fromByteOffset: r * cs + c, as: UInt8.self) } }
            }
            CVPixelBufferUnlockBaseAddress(cm, .readOnly)
        }
        let ptr = base.assumingMemoryBound(to: Float32.self)
        for r in 0..<h { for c in 0..<w {
            let z = ptr[r * stride + c]
            if z.isFinite, z > 0, (conf?[r * w + c] ?? 2) >= 1 { vals[r * w + c] = z }
        } }
        return DepthMap(width: w, height: h, values: vals)
    }
}

/// Korte rolling buffer van LiDAR-dieptekaders (pose, tracking, tijdstempel, geldige punten). Draait buiten de hoofdthread (ARSession-delegate); thread-safe via een lock.
/// Doel: bij de foto een paar GEOMETRISCH ONAFHANKELIJKE kaders (kleine camerabeweging) beschikbaar hebben. De kern gebruikt alleen kaders met voldoende
/// standpuntverschil; bijna identieke kaders worden verworpen (gecorreleerd, geen extra bewijs).
final class DepthRingBuffer: @unchecked Sendable {
    struct Entry {
        let timestamp: TimeInterval
        let intrinsics: Intrinsics
        let pose: Pose
        let tracking: String
        let depth: DepthMap
        let validFraction: Double
    }
    private let lock = NSLock()
    private var entries: [Entry] = []
    private var lastTs: TimeInterval = -1
    let capacity = 14
    let minInterval = 0.08          // s tussen opgeslagen kaders (~12 Hz)
    let maxAge = 1.8                // s

    func reset() { lock.lock(); entries = []; lastTs = -1; lock.unlock() }

    func offer(_ f: ARFrame) {
        guard let sd = f.sceneDepth else { return }
        lock.lock(); let last = lastTs; lock.unlock()
        if f.timestamp - last < minInterval { return }
        guard let dm = ARConvert.depthMap(sd) else { return }
        let valid = Double(dm.values.filter { $0.isFinite && $0 > 0 }.count) / Double(max(dm.values.count, 1))
        let e = Entry(timestamp: f.timestamp, intrinsics: ARConvert.intrinsics(f), pose: ARConvert.pose(f), tracking: ARConvert.trackingString(f.camera.trackingState), depth: dm, validFraction: valid)
        lock.lock()
        entries.append(e); lastTs = f.timestamp
        if entries.count > capacity { entries.removeFirst(entries.count - capacity) }
        lock.unlock()
    }

    /// Recente kaders (nieuwste eerst) tot `maxAge` seconden voor `timestamp`, exclusief een kader met precies dat tijdstempel.
    func recent(before timestamp: TimeInterval) -> [Entry] {
        lock.lock(); defer { lock.unlock() }
        return entries.filter { $0.timestamp < timestamp && timestamp - $0.timestamp <= maxAge }.reversed()
    }

    /// Aantal onderling onafhankelijke kaders (alleen pose-vergelijking; goedkoop). Zelfde regel als de kern: >= minBaselineM of >= minRotationDeg t.o.v. alle gekozen kaders.
    func independentCount(cfg: Config = Config()) -> Int {
        lock.lock(); let es = entries.filter { $0.tracking == "NORMAL" }; lock.unlock()
        var chosen: [Pose] = []
        for e in es.reversed() {
            var ok = true
            for c in chosen {
                let dt = (e.pose.t - c.t).norm
                var tr = 0.0
                for i in 0..<3 { tr += e.pose.r[i].dot(c.r[i]) }
                let rot = acos(max(-1, min(1, (tr - 1) / 2))) * 180 / Double.pi
                if dt < cfg.minBaselineM && rot < cfg.minRotationDeg { ok = false; break }
            }
            if ok { chosen.append(e.pose) }
            if chosen.count >= 1 + cfg.maxSupportFrames { break }
        }
        return chosen.count
    }
}
