import ARKit
import Combine
import PhotoWalkCore
import UIKit

/// ARKit-adapter: vertaalt ARFrame naar het platformonafhankelijke capture-contract.
/// Conventies (zie docs/arkit_adapter.md): ARKit-camera = x rechts, y OMHOOG, z ACHTERUIT -> OpenCV-camera = x rechts, y omlaag, z vooruit,
/// dus R_cv = R_arkit * diag(1,-1,-1). Intrinsics zijn in pixels van `capturedImage` (native landscape-oriëntatie); de dieptekaart hoort bij dezelfde oriëntatie.
/// STATUS: niet gecompileerd en niet op een toestel getest.
@MainActor
final class CaptureCoordinator: NSObject, ObservableObject, ARSessionDelegate {
    let session = ARSession()
    @Published var trackingText = "Niet gestart"
    @Published var sensorText = ""
    @Published var modeText = ""
    @Published var keyframeCount = 0
    @Published var hint: String? = nil
    private(set) var capabilities = (lidarDepth: false, worldTracking: ARWorldTrackingConfiguration.isSupported)
    private var lastFrame: ARFrame?
    private weak var store: ScanStore?

    func start(store: ScanStore) {
        self.store = store
        guard ARWorldTrackingConfiguration.isSupported else { trackingText = "ARWorldTracking niet ondersteund -> alleen niveau C (referentie)"; modeText = "C_REFERENCE"; return }
        let cfg = ARWorldTrackingConfiguration()
        cfg.worldAlignment = .gravity                       // Y omhoog, meters
        cfg.planeDetection = [.vertical]
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) { cfg.frameSemantics.insert(.sceneDepth); capabilities.lidarDepth = true }
        sensorText = "LiDAR/sceneDepth: \(capabilities.lidarDepth ? "ja" : "nee") - wereldtracking: ja"
        modeText = capabilities.lidarDepth ? "A_METRIC_DEPTH (terugval B/C)" : "B_AR_GEOMETRY / C_REFERENCE"
        session.delegate = self
        session.run(cfg, options: [.resetTracking, .removeExistingAnchors])
    }

    nonisolated func session(_ session: ARSession, didUpdate frame: ARFrame) {
        Task { @MainActor in
            self.lastFrame = frame
            self.trackingText = Self.trackingString(frame.camera.trackingState)
            if case .normal = frame.camera.trackingState { self.hint = nil } else { self.hint = "Beweeg langzaam en richt op een gevel met textuur." }
        }
    }

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

    /// Legt het huidige frame vast als keyframe (lokaal; geen upload).
    func captureKeyframe() {
        guard let f = lastFrame, let store else { return }
        let K = f.camera.intrinsics
        let res = f.camera.imageResolution
        let intr = Intrinsics(fx: Double(K[0][0]), fy: Double(K[1][1]), cx: Double(K[2][0]), cy: Double(K[2][1]), width: Int(res.width), height: Int(res.height))
        let T = f.camera.transform
        let flip: [Float] = [1, -1, -1]
        func row(_ i: Int) -> Vec3 { Vec3(Double(T.columns.0[i] * flip[0]), Double(T.columns.1[i] * flip[1]), Double(T.columns.2[i] * flip[2])) }
        let pose = Pose(rows: [row(0), row(1), row(2)], t: Vec3(Double(T.columns.3.x), Double(T.columns.3.y), Double(T.columns.3.z)))
        let id = String(format: "F%03d", store.keyframes.count)
        let kf = Keyframe(id: id, timestamp: Date(), intrinsics: intr, pose: pose, trackingState: Self.trackingString(f.camera.trackingState),
                          depth: Self.depthMap(f), imageURL: Self.saveImage(f.capturedImage, id: id))
        store.keyframes.append(kf)
        keyframeCount = store.keyframes.count
        if kf.depth == nil { hint = "Geen dieptebeeld: gebruik een tweede standpunt of voer een referentiemaat in." }
    }

    private static func depthMap(_ f: ARFrame) -> DepthMap? {
        guard let sd = f.sceneDepth else { return nil }
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
        for r in 0..<h { for c in 0..<w {
            let z = base.assumingMemoryBound(to: Float32.self)[r * stride + c]
            // laag vertrouwen (0) wordt als ongeldig behandeld; dit drempelbesluit is niet gevalideerd
            if z.isFinite, z > 0, (conf?[r * w + c] ?? 2) >= 1 { vals[r * w + c] = z }
        } }
        return DepthMap(width: w, height: h, values: vals)
    }

    /// Slaat het camerabeeld lokaal op in Application Support, uitgesloten van back-up. Nooit een upload.
    private static func saveImage(_ pb: CVPixelBuffer, id: String) -> URL? {
        let ci = CIImage(cvPixelBuffer: pb)
        guard let jpeg = CIContext().jpegRepresentation(of: ci, colorSpace: CGColorSpaceCreateDeviceRGB(), options: [:]) else { return nil }
        guard var dir = try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true).appendingPathComponent("PhotoWalk", isDirectory: true) else { return nil }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        var rv = URLResourceValues(); rv.isExcludedFromBackup = true; try? dir.setResourceValues(rv)
        let url = dir.appendingPathComponent("\(id).jpg")
        return (try? jpeg.write(to: url)) != nil ? url : nil
    }
}
