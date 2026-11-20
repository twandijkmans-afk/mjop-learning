import Foundation

/// Hulplijn in de camera: uit de grootste rechthoek die de telefoon live ziet (genormaliseerd 0–1, y omlaag) een korte aanwijzing.
/// Geen rechthoek: geen hint (niet gokken).
public enum FramingHint: Equatable {
    case tooWide
    case moveLeft
    case moveRight

    public var text: String {
        switch self {
        case .tooWide: return "Gevel past niet helemaal in beeld: stap achteruit of kies 0,5×"
        case .moveLeft: return "Ga iets naar links"
        case .moveRight: return "Ga iets naar rechts"
        }
    }

    public static let edgeMargin = 0.02
    public static let offCenter = 0.15

    public static func hint(quad q: [[Double]]?) -> FramingHint? {
        guard let q, q.count == 4 else { return nil }
        let xs = q.map { $0[0] }
        guard let minX = xs.min(), let maxX = xs.max(), maxX > minX else { return nil }
        if minX <= edgeMargin || maxX >= 1 - edgeMargin { return .tooWide }
        let cx = (minX + maxX) / 2
        if cx < 0.5 - offCenter { return .moveLeft }    // gevel staat links in beeld: draai of stap naar links
        if cx > 0.5 + offCenter { return .moveRight }
        return nil
    }
}
