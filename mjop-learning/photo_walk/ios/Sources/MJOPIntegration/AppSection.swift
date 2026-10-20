import Foundation

/// Hoofdnavigatie van de app. De keuze wordt onthouden; de inhoud van beide secties blijft levend bij wisselen.
public enum AppSection: String, CaseIterable, Equatable {
    case mjop, scanner

    public var title: String { self == .mjop ? "Mijn MJOP" : "Gevelscanner" }

    /// Startsectie: expliciet launch-argument (`-section scanner|mjop`) wint van de bewaarde keuze; standaard Mijn MJOP.
    public static func initial(arguments: [String], stored: String?) -> AppSection {
        if let i = arguments.firstIndex(of: "-section"), arguments.indices.contains(i + 1), let s = AppSection(rawValue: arguments[i + 1]) { return s }
        if let stored = stored, let s = AppSection(rawValue: stored) { return s }
        return .mjop
    }
}
