import Foundation

/// Veilige bestandsnamen voor downloads van de website (CSV-export, JSON-gegevens, PDF).
public enum DownloadNaming {
    public static func safeFileName(suggested: String?, mimeType: String? = nil) -> String {
        var name = (suggested ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        name = name.replacingOccurrences(of: "\\", with: "/")
        name = String(name.split(separator: "/").last ?? "")
        let bad = CharacterSet.controlCharacters.union(CharacterSet(charactersIn: "<>:\"|?*\u{0}"))
        name = name.unicodeScalars.filter { !bad.contains($0) }.map(String.init).joined()
        while name.hasPrefix(".") { name.removeFirst() }
        if name.count > 100 { name = String(name.prefix(100)) }
        if name.isEmpty { name = "mjop-export" }
        if !name.contains("."), let ext = fileExtension(for: mimeType) { name += "." + ext }
        return name
    }

    public static func fileExtension(for mime: String?) -> String? {
        switch (mime ?? "").lowercased().split(separator: ";").first.map(String.init) {
        case "text/csv": return "csv"
        case "application/pdf": return "pdf"
        case "application/json": return "json"
        case "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": return "xlsx"
        default: return nil
        }
    }
}
