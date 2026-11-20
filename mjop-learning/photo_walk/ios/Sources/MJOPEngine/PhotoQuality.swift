import Foundation

/// Een probleem met een foto dat de herkenning slechter maakt.
public enum PhotoIssue: String, Codable, CaseIterable {
    case dark, blurry, backlight

    public var label: String {
        switch self {
        case .dark: return "De foto is erg donker."
        case .blurry: return "De foto lijkt onscherp (bewogen of niet scherpgesteld)."
        case .backlight: return "Er is veel tegenlicht: de lucht is overbelicht en de gevel donker."
        }
    }
}

/// Controle van de fotokwaliteit vóór de foto naar Claude gaat, met vaste drempels op een grijswaardenbeeld (0–255, rij voor rij).
/// Alleen een waarschuwing: de gebruiker kan de foto toch gebruiken.
public enum PhotoQuality {
    /// Gemiddelde helderheid waaronder een foto te donker is.
    public static let darkMean = 55.0
    /// Variantie van de Laplaciaan waaronder een foto onscherp lijkt (op een beeld van ongeveer 512 pixels breed).
    public static let blurVariance = 60.0
    /// Tegenlicht: meer dan dit deel van de bovenste helft overbelicht, en de onderste helft donker.
    public static let clippedShare = 0.25
    public static let darkBottomMean = 90.0

    public static func assess(gray g: [UInt8], width w: Int, height h: Int) -> [PhotoIssue] {
        guard w >= 8, h >= 8, g.count >= w * h else { return [] }
        var issues: [PhotoIssue] = []
        let n = Double(w * h)
        let mean = g.prefix(w * h).reduce(0.0) { $0 + Double($1) } / n
        if mean < darkMean { issues.append(.dark) }

        // Scherpte: variantie van de 4-buren-Laplaciaan.
        var sum = 0.0, sum2 = 0.0, count = 0.0
        for y in 1..<(h - 1) {
            for x in 1..<(w - 1) {
                let c = Int(g[y * w + x])
                let l = Int(g[y * w + x - 1]) + Int(g[y * w + x + 1]) + Int(g[(y - 1) * w + x]) + Int(g[(y + 1) * w + x]) - 4 * c
                let d = Double(l)
                sum += d; sum2 += d * d; count += 1
            }
        }
        let m = sum / count
        let variance = sum2 / count - m * m
        if variance < blurVariance && mean >= darkMean { issues.append(.blurry) }

        // Tegenlicht: felle bovenkant, donkere onderkant.
        let half = h / 2
        var clipped = 0, bottomSum = 0.0
        for y in 0..<half { for x in 0..<w where g[y * w + x] >= 250 { clipped += 1 } }
        for y in half..<h { for x in 0..<w { bottomSum += Double(g[y * w + x]) } }
        let topShare = Double(clipped) / Double(half * w)
        let bottomMean = bottomSum / Double((h - half) * w)
        if topShare > clippedShare && bottomMean < darkBottomMean { issues.append(.backlight) }
        return issues
    }
}
