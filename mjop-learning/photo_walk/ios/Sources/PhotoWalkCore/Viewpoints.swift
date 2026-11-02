import Foundation

/// Onafhankelijke standpunten voor de status MEASURED. Python-referentie: photo_walk_core/pipeline.py (independent_photo_count).
///
/// Een standpunt is een APART VASTGELEGDE foto (keyframe) met een eigen camerapose. Ondersteunende LiDAR-dieptekaders uit de korte buffer
/// rond één foto zijn GEEN aparte foto's: ze kunnen de meting van die foto verbeteren (LIDAR_DEPTH_MULTI_FRAME), maar tellen nooit als extra
/// standpunt. Eén foto komt dus hoogstens tot ESTIMATED. Twee foto's tellen alleen als twee standpunten als hun cameraposities minstens
/// `Config.minBaselineM` uit elkaar liggen (dezelfde drempel als voor onafhankelijke dieptekaders; niet versoepeld, PROVISIONAL_UNVALIDATED).
public enum Viewpoints {
    public struct Capture: Equatable {
        public var keyframeId: String
        public var position: Vec3             // cameracentrum in wereldcoördinaten (pose.t)
        public init(keyframeId: String, position: Vec3) { self.keyframeId = keyframeId; self.position = position }
    }

    public struct ViewMeasurement {
        public var capture: Capture
        public var result: LevelResult
        public init(capture: Capture, result: LevelResult) { self.capture = capture; self.result = result }
    }

    /// Aantal apart vastgelegde foto's met onderling verschillende cameraposities. Dubbele keyframes tellen één keer; deterministisch.
    public static func independentPhotoCount(_ captures: [Capture], minBaselineM: Double = Config().minBaselineM) -> Int {
        var seen = Set<String>(), chosen: [Vec3] = []
        for c in captures.sorted(by: { $0.keyframeId < $1.keyframeId }) where !seen.contains(c.keyframeId) {
            seen.insert(c.keyframeId)
            if chosen.allSatisfy({ ($0 - c.position).norm >= minBaselineM }) { chosen.append(c.position) }
        }
        return chosen.count
    }

    /// Niveau-A-metingen van één voorlopig kozijn combineren tot (resultaat, aantal standpunten voor de status).
    /// Alleen geldige (en dus bevestigde, zie ContourGate) metingen tellen. Twee of meer: fusie (tegenstrijdig = VIEWS_INCONSISTENT, geen maat);
    /// het aantal standpunten is het aantal onafhankelijke FOTO'S, nooit het aantal ondersteunende dieptekaders. nil = geen geldige niveau-A-meting.
    public static func combineLevelA(_ items: [ViewMeasurement], minBaselineM: Double = Config().minBaselineM) -> (result: LevelResult, viewCount: Int)? {
        let ok = items.filter { $0.result.ok && $0.result.level == .A }
        if ok.count >= 2 { return (fuse(ok.map { $0.result }), max(1, independentPhotoCount(ok.map { $0.capture }, minBaselineM: minBaselineM))) }
        if let a = ok.first { return (a.result, 1) }       // één foto: ondersteunende LiDAR-kaders zijn geen extra standpunten
        return nil
    }
}
