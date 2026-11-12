import ARKit
import Foundation

/// Wat dit toestel en deze appversie kunnen; wordt aan de website gemeld (zelfde bron als het antwoord op `getCapabilities`).
enum DeviceCapabilities {
    static var hasLiDAR: Bool { ARWorldTrackingConfiguration.isSupported && ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) }
    static var appVersion: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "2" }
    /// Bouwnummer (in de bouwopdracht het runnummer), zodat te zien is welke versie op het toestel staat.
    static var buildNumber: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?" }
}
