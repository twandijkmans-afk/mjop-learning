import SwiftUI
import UIKit

/// Ontwerpsysteem van MJOP Live 3: licht en luchtig, kobaltblauw als enige accent, glas over foto's, grote ronde hoeken.
/// Alle schermen gebruiken deze tokens en onderdelen; een kleur of hoek aanpassen gebeurt hier, op één plek.
enum DS {
    // MARK: kleuren (licht / donker)
    static let accent = dyn(light: 0x2F4BFF, dark: 0x5C74FF)
    static let accentDeep = Color(hex: 0x1B2ECC)
    static let accentSoft = dyn(light: 0xEAF0FF, dark: 0x1B2347)
    static let onAccentSoft = dyn(light: 0x1B2ECC, dark: 0xA9B4FF)
    static let canvas = dyn(light: 0xF3F6FD, dark: 0x05070D)
    static let surface = dyn(light: 0xFFFFFF, dark: 0x11151F)
    static let surface2 = dyn(light: 0xF5F7FB, dark: 0x1A1F2B)
    static let text = dyn(light: 0x0E1424, dark: 0xF2F4FA)
    static let text2 = dyn(light: 0x667085, dark: 0x98A2B3)
    static let line = dyn(light: 0xE6EAF2, dark: 0x232836)
    static let ok = dyn(light: 0x1E7A45, dark: 0x4ADE80)
    static let okSoft = dyn(light: 0xE7F8EE, dark: 0x0F2A1B)
    static let warn = dyn(light: 0xA15C00, dark: 0xFFB547)
    static let warnSoft = dyn(light: 0xFFF4E5, dark: 0x2E2212)
    static let bad = dyn(light: 0xC7362E, dark: 0xFF7A70)

    // MARK: maten
    static let radiusCard: CGFloat = 22
    static let radiusHero: CGFloat = 26
    static let pad: CGFloat = 16

    static func dyn(light: UInt32, dark: UInt32) -> Color {
        Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) })
    }
}

extension UIColor {
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255, blue: CGFloat(hex & 0xFF) / 255, alpha: alpha)
    }
}

extension Color {
    init(hex: UInt32) { self.init(UIColor(hex: hex)) }
}

// MARK: - Kaart

struct DSCard: ViewModifier {
    var radius: CGFloat = DS.radiusCard
    @Environment(\.colorScheme) private var scheme

    func body(content: Content) -> some View {
        content
            .background(DS.surface, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous).strokeBorder(Color.white.opacity(scheme == .dark ? 0.06 : 0), lineWidth: 0.5))
            .shadow(color: DS.accent.opacity(scheme == .dark ? 0 : 0.07), radius: 16, x: 0, y: 10)
            .shadow(color: .black.opacity(scheme == .dark ? 0 : 0.04), radius: 1, x: 0, y: 1)
    }
}

extension View {
    func dsCard(radius: CGFloat = DS.radiusCard) -> some View { modifier(DSCard(radius: radius)) }
}

// MARK: - Knoppen

/// Grote blauwe pilknop met gloed.
struct DSPrimaryButton: ButtonStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 54)
            .foregroundStyle(.white)
            .background(DS.accent.opacity(enabled ? 1 : 0.45), in: Capsule())
            .shadow(color: DS.accent.opacity(enabled ? 0.35 : 0), radius: 12, x: 0, y: 8)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// Lichtblauwe pilknop.
struct DSSecondaryButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 54)
            .foregroundStyle(DS.onAccentSoft)
            .background(DS.accentSoft, in: Capsule())
            .opacity(configuration.isPressed ? 0.75 : 1)
    }
}

/// Witte (of donkere) pilknop met rand, voor bijvoorbeeld "Doorgaan met Google".
struct DSOutlineButton: ButtonStyle {
    var filledDark = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 54)
            .foregroundStyle(filledDark ? Color.white : DS.text)
            .background(filledDark ? Color(hex: 0x0E1424) : DS.surface, in: Capsule())
            .overlay(Capsule().strokeBorder(filledDark ? Color.clear : DS.line, lineWidth: 1))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

/// Rij die oplicht bij aantikken.
struct DSRowStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .contentShape(Rectangle())
            .background(configuration.isPressed ? DS.surface2 : Color.clear)
    }
}

// MARK: - Kleine onderdelen

/// Pictogram in een lichtblauw vlak.
struct DSIcon: View {
    let systemName: String
    var size: CGFloat = 34

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: size * 0.48, weight: .semibold))
            .foregroundStyle(DS.accent)
            .frame(width: size, height: size)
            .background(DS.accentSoft, in: RoundedRectangle(cornerRadius: size * 0.32, style: .continuous))
            .accessibilityHidden(true)
    }
}

/// Label op glas, bovenop een foto.
struct DSGlassChip: View {
    let text: String
    var dot: Color? = nil

    var body: some View {
        HStack(spacing: 6) {
            if let dot { Circle().fill(dot).frame(width: 7, height: 7) }
            Text(text).font(.caption.weight(.semibold)).lineLimit(1)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .foregroundStyle(.white)
        .background(.ultraThinMaterial, in: Capsule())
        .environment(\.colorScheme, .dark)
    }
}

/// Gekleurd label.
struct DSChip: View {
    let text: String
    var fg: Color = DS.onAccentSoft
    var bg: Color = DS.accentSoft

    var body: some View {
        Text(text).font(.caption.weight(.semibold)).lineLimit(1)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .foregroundStyle(fg).background(bg, in: Capsule())
    }
}

/// Rond knopje op glas (terug, delen, meer).
struct DSGlassCircle: View {
    let systemName: String
    var body: some View {
        Image(systemName: systemName).font(.system(size: 16, weight: .semibold))
            .foregroundStyle(DS.text)
            .frame(width: 40, height: 40)
            .background(.regularMaterial, in: Circle())
    }
}

/// Het logo: blauw vierkant met een M.
struct DSLogo: View {
    var size: CGFloat = 52
    var body: some View {
        Text("M").font(.system(size: size * 0.54, weight: .bold)).foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(Color(hex: 0x2F4BFF), in: RoundedRectangle(cornerRadius: size * 0.29, style: .continuous))
            .shadow(color: Color(hex: 0x2F4BFF).opacity(0.4), radius: 12, x: 0, y: 8)
            .accessibilityLabel("MJOP Live")
    }
}

/// Invoerveld in de stijl van de app.
struct DSField<Field: View>: View {
    let icon: String
    @ViewBuilder var field: () -> Field

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: icon).foregroundStyle(DS.text2).frame(width: 22).accessibilityHidden(true)
            field()
        }
        .padding(.horizontal, 16)
        .frame(minHeight: 54)
        .background(DS.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(DS.line, lineWidth: 1))
    }
}

/// Melding in een kaart (fout, waarschuwing, info).
struct DSNotice: View {
    enum Kind { case info, warn, bad }
    let kind: Kind
    let text: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: kind == .info ? "info.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(kind == .bad ? DS.bad : (kind == .warn ? DS.warn : DS.accent))
            Text(text).font(.subheadline).foregroundStyle(DS.text).frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(14)
        .background(kind == .info ? DS.accentSoft : DS.warnSoft, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

enum DSFormat {
    private static let euro: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency; f.currencyCode = "EUR"; f.locale = Locale(identifier: "nl_NL"); f.maximumFractionDigits = 0
        return f
    }()
    static func euros(_ v: Int) -> String { euro.string(from: NSNumber(value: v)) ?? "€ \(v)" }

    static func relative(_ d: Date) -> String {
        let f = RelativeDateTimeFormatter(); f.locale = Locale(identifier: "nl_NL"); f.unitsStyle = .full
        return f.localizedString(for: d, relativeTo: Date())
    }

    static func today() -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "nl_NL"); f.setLocalizedDateFormatFromTemplate("EEEEdMMMM")
        let s = f.string(from: Date())
        return s.prefix(1).uppercased() + s.dropFirst()
    }

    static func greeting() -> String {
        let h = Calendar.current.component(.hour, from: Date())
        switch h {
        case 5..<12: return "Goedemorgen"
        case 12..<18: return "Goedemiddag"
        default: return "Goedenavond"
        }
    }
}
