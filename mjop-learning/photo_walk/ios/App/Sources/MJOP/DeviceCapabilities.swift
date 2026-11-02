import ARKit
import Foundation

/// Wat dit toestel en deze appversie kunnen; wordt aan de website gemeld (zelfde bron als het antwoord op `getCapabilities`).
enum DeviceCapabilities {
    static var hasLiDAR: Bool { ARWorldTrackingConfiguration.isSupported && ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) }
    static var appVersion: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "2" }
}
