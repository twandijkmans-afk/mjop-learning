import Foundation
import PhotoWalkCore

/// Ontwikkelbundel op het toestel (zie docs/dev_capture_bundle.md). STANDAARD UIT. Lokaal in Application Support, uitgesloten van back-ups, nooit geüpload.
/// De bundel wordt uitsluitend geschreven door een expliciete actie in het diagnosescherm, nooit door de selftest of de gewone meetflow.
enum DevBundleStore {
    static let enabledKey = "photowalk.devBundle.enabled"
    static let photoKey = "photowalk.devBundle.includePhoto"

    static var enabled: Bool { UserDefaults.standard.bool(forKey: enabledKey) }
    static var includePhoto: Bool { UserDefaults.standard.bool(forKey: photoKey) }

    static func root(create: Bool = false) throws -> URL {
        let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let dir = base.appendingPathComponent("devbundles", isDirectory: true)
        if create {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            CaptureBundle.excludeFromBackup(dir)
        }
        return dir
    }

    static func count() -> Int { ((try? root()).map { CaptureBundle.list(root: $0).count }) ?? 0 }

    /// Verwijdert ALLE ontwikkelbundels (foto's en dieptekaarten). Geeft het aantal verwijderde bundels.
    @discardableResult static func deleteAll() -> Int { ((try? root()).map { CaptureBundle.deleteAll(root: $0) }) ?? 0 }

    @MainActor static func writeIfEnabled(_ s: ScanStore, observationId: String) throws -> URL? {
        guard enabled, let o = s.observation(observationId), let kf = s.keyframe(o.frameId) else { return nil }
        var photo: Data? = nil
        if includePhoto, let u = kf.imageURL { photo = try? Data(contentsOf: u) }
        var labels: [String: String] = [kf.id: kf.trackingState]
        for sd in kf.supportDepths { labels[sd.id] = sd.trackingState }
        return try CaptureBundle.write(root: root(create: true), view: Measurer.input(kf), corners: o.corners, sessionId: s.sessionId, observationId: observationId,
                                       appBuild: "photo_walk_ios_lidar_v2/" + ((Bundle.main.infoDictionary?["CFBundleVersion"] as? String) ?? "dev"),
                                       thresholds: DiagnosticsExport.thresholds(), photo: photo, trackingLabels: labels)
    }
}
