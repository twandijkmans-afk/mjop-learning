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
    @Published var hasFrame = false
    @Published var hint: String? = nil
    private(set) var capabilities = (lidarDepth: false, worldTracking: ARWorldTrackingConfiguration.isSupported)
    private var lastFrame: ARFrame?
    private weak var store: ScanStore?
    /// Rolling buffer van recente LiDAR-dieptekaders (zie DepthRingBuffer). `nonisolated`: wordt gevuld vanuit de ARSession-delegate.
    nonisolated let ring = DepthRingBuffer()
    static let motionHint = "Beweeg je telefoon langzaam iets naar links en rechts voor een betere meting."
    private var lastMotionCheck: TimeInterval = 0

    func start(store: ScanStore) {
        self.store = store
        guard ARWorldTrackingConfiguration.isSupported else {
            trackingText = "ARWorldTracking niet ondersteund op dit toestel (bv. simulator) -> geen keyframes; alleen niveau C (referentie) mogelijk"
            modeText = "C_REFERENCE"
            return
        }
        let cfg = ARWorldTrackingConfiguration()
        cfg.worldAlignment = .gravity                       // Y omhoog, meters
        cfg.planeDetection = [.vertical]
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) { cfg.frameSemantics.insert(.sceneDepth); capabilities.lidarDepth = true }
        if capabilities.lidarDepth && ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth) { cfg.frameSemantics.insert(.smoothedSceneDepth) }
        ring.reset()
        sensorText = "LiDAR/sceneDepth: \(capabilities.lidarDepth ? "ja" : "nee") - wereldtracking: ja"
        modeText = capabilities.lidarDepth ? "A_METRIC_DEPTH (terugval B/C)" : "B_AR_GEOMETRY / C_REFERENCE"
        session.delegate = self
        session.run(cfg, options: [.resetTracking, .removeExistingAnchors])
    }

    nonisolated func session(_ session: ARSession, didUpdate frame: ARFrame) {
        ring.offer(frame)                                   // buiten de hoofdthread; goedkoop begrensd (max ~12 Hz)
        Task { @MainActor in
            self.lastFrame = frame
            if !self.hasFrame { self.hasFrame = true }
            self.trackingText = Self.trackingString(frame.camera.trackingState)
            if case .normal = frame.camera.trackingState { self.hint = nil } else { self.hint = "Beweeg langzaam en richt op een gevel met textuur." }
            // bewegingshint: zonder voldoende onafhankelijke dieptekaders is een betrouwbare LiDAR-meting niet mogelijk
            if self.capabilities.lidarDepth, case .normal = frame.camera.trackingState, frame.timestamp - self.lastMotionCheck > 0.5 {
                self.lastMotionCheck = frame.timestamp
                if self.ring.independentCount() < 2 { self.hint = Self.motionHint }
            }
        }
    }

    nonisolated func session(_ session: ARSession, didFailWithError error: Error) {
        let msg = error.localizedDescription
        Task { @MainActor in self.trackingText = "AR-fout: \(msg) - controleer de cameratoestemming; gebruik anders een referentiemaat" }
    }

    nonisolated func sessionWasInterrupted(_ session: ARSession) {
        Task { @MainActor in self.trackingText = "Sessie onderbroken (tracking niet beschikbaar)" }
    }

    static func trackingString(_ s: ARCamera.TrackingState) -> String { ARConvert.trackingString(s) }

    /// Legt het huidige frame vast als keyframe (lokaal; geen upload), samen met de korte buffer van recente dieptekaders.
    @discardableResult
    func captureKeyframe() -> Keyframe? {
        guard let f = lastFrame, let store else { return nil }
        let intr = ARConvert.intrinsics(f), pose = ARConvert.pose(f)
        let id = String(format: "F%03d", store.keyframes.count)
        var kf = Keyframe(id: id, timestamp: Date(), intrinsics: intr, pose: pose, trackingState: ARConvert.trackingString(f.camera.trackingState),
                          depth: ARConvert.depthMap(f.sceneDepth), imageURL: Self.saveImage(f.capturedImage, id: id, sessionId: store.sessionId))
        kf.smoothedDepth = ARConvert.depthMap(f.smoothedSceneDepth)
        // ondersteunende kaders: ruime baseline eerst; de kern houdt alleen geometrisch onafhankelijke kaders over
        let recent = Array(ring.recent(before: f.timestamp).sorted { (a, b) in (a.pose.t - pose.t).norm > (b.pose.t - pose.t).norm }.prefix(8))
        let now = Date()
        kf.supportDepths = recent.enumerated().map { (i, e) in
            SupportDepth(id: "\(id)-S\(i)", timestamp: now.addingTimeInterval(e.timestamp - f.timestamp), intrinsics: e.intrinsics, pose: e.pose, trackingState: e.tracking, depth: e.depth)
        }
        store.keyframes.append(kf)
        keyframeCount = store.keyframes.count
        if kf.depth == nil { hint = "Geen dieptebeeld: maten blijven UNKNOWN tenzij je een referentiemaat invoert." }
        else if kf.supportDepths.isEmpty { hint = Self.motionHint }
        return kf
    }

    /// Slaat het camerabeeld lokaal op in de sessiemap (Application Support, uitgesloten van back-up). Nooit een upload.
    private static func saveImage(_ pb: CVPixelBuffer, id: String, sessionId: String) -> URL? {
        let ci = CIImage(cvPixelBuffer: pb)
        guard let jpeg = CIContext().jpegRepresentation(of: ci, colorSpace: CGColorSpaceCreateDeviceRGB(), options: [:]),
              let dir = Persistence.sessionDir(sessionId) else { return nil }
        let url = dir.appendingPathComponent("\(id).jpg")
        return (try? jpeg.write(to: url, options: [.atomic, .completeFileProtection])) != nil ? url : nil
    }
}
