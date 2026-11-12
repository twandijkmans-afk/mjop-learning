import SwiftUI
import UIKit

/// Ontwerpbouwstenen van MJOP Live: één accentkleur (kobaltblauw), diep inkt-zwart voor de belangrijkste cijfers, ruime witruimte en grote getallen.
/// Alles werkt in licht en donker en schaalt mee met de tekstgrootte van de gebruiker. Geen eigen namaak van systeemonderdelen.
enum Premium {
    /// Hoofdvlak achter de kaarten.
    static let canvas = Color(.systemGroupedBackground)
    /// Kaartvlak (wit in licht, verhoogd grijs in donker).
    static let surface = Color(.secondarySystemGroupedBackground)
    /// Inkt-vlak voor de kerncijfers: in donker iets lichter dan de achtergrond, zodat het als kaart blijft lezen.
    static let ink = Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(white: 0.13, alpha: 1) : UIColor(red: 16 / 255, green: 18 / 255, blue: 17 / 255, alpha: 1) })
    static let accentDeep = Color(red: 27 / 255, green: 46 / 255, blue: 204 / 255)
    static let accentSoft = Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 47 / 255, green: 75 / 255, blue: 255 / 255, alpha: 0.28) : UIColor(red: 233 / 255, green: 236 / 255, blue: 255 / 255, alpha: 1) })
    /// Statuskleuren: de standaardkleuren van iOS, alleen voor status (niet als huisstijl).
    static let ok = Color.green
    static let warn = Color.orange
    static let bad = Color.red

    static let cardRadius: CGFloat = 22
    static let heroRadius: CGFloat = 28
}

/// Kaart met zachte schaduw (alleen in licht; in donker zou schaduw modder geven).
struct PremiumCard: ViewModifier {
    var radius: CGFloat = Premium.cardRadius
    @Environment(\.colorScheme) private var scheme

    func body(content: Content) -> some View {
        content
            .background(Premium.surface, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .shadow(color: .black.opacity(scheme == .dark ? 0 : 0.06), radius: 15, x: 0, y: 8)
            .shadow(color: .black.opacity(scheme == .dark ? 0 : 0.04), radius: 1, x: 0, y: 1)
    }
}

extension View {
    func premiumCard(radius: CGFloat = Premium.cardRadius) -> some View { modifier(PremiumCard(radius: radius)) }
}

/// Donkere kaart met een blauwe gloed: voor de kerncijfers van het project.
struct InkCard<Content: View>: View {
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) { content() }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(18)
            .foregroundStyle(.white)
            .background {
                ZStack(alignment: .topTrailing) {
                    Premium.ink
                    Circle()
                        .fill(RadialGradient(colors: [MJOPTheme.accent.opacity(0.55), MJOPTheme.accent.opacity(0)], center: .center, startRadius: 0, endRadius: 130))
                        .frame(width: 260, height: 260)
                        .offset(x: 80, y: -90)
                        .accessibilityHidden(true)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(.white.opacity(0.08)))
    }
}

/// Klein label op glas, voor bovenop een foto.
struct GlassChip: View {
    let text: String
    var dot: Color? = nil

    var body: some View {
        HStack(spacing: 6) {
            if let dot { Circle().fill(dot).frame(width: 7, height: 7).accessibilityHidden(true) }
            Text(text).font(.caption.weight(.semibold)).lineLimit(1)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .foregroundStyle(.white)
        .background(.ultraThinMaterial, in: Capsule())
        .environment(\.colorScheme, .dark)
        .overlay(Capsule().strokeBorder(.white.opacity(0.25), lineWidth: 0.5))
    }
}

/// Gekleurd label op een gewone achtergrond.
struct TintChip: View {
    let text: String
    var tint: Color = MJOPTheme.accent

    var body: some View {
        Text(text).font(.caption.weight(.semibold)).lineLimit(1)
            .padding(.horizontal, 10).padding(.vertical, 4)
            .foregroundStyle(tint)
            .background(tint.opacity(0.14), in: Capsule())
    }
}

/// Afgerond pictogramvlak zoals in Instellingen.
struct IconTile: View {
    let systemName: String
    var color: Color = MJOPTheme.accent
    var size: CGFloat = 30

    var body: some View {
        Image(systemName: systemName)
            .font(.system(size: size * 0.5, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(color, in: RoundedRectangle(cornerRadius: size * 0.27, style: .continuous))
            .accessibilityHidden(true)
    }
}

/// Groot pictogram met kleurverloop, voor de belangrijkste actie op een kaart.
struct GradientTile: View {
    let systemName: String

    var body: some View {
        Image(systemName: systemName)
            .font(.title3.weight(.semibold))
            .foregroundStyle(.white)
            .frame(width: 46, height: 46)
            .background(LinearGradient(colors: [MJOPTheme.accent, Premium.accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing),
                        in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .shadow(color: MJOPTheme.accent.opacity(0.35), radius: 7, x: 0, y: 5)
            .accessibilityHidden(true)
    }
}

/// Rij in een kaartlijst die oplicht bij aantikken, zoals een systeemlijst.
struct PressableRowStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .contentShape(Rectangle())
            .background(configuration.isPressed ? Color(.systemFill) : Color.clear)
    }
}

/// Grote blauwe hoofdknop met gloed.
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 52)
            .foregroundStyle(.white)
            .background(MJOPTheme.accent.opacity(enabled ? 1 : 0.4), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .shadow(color: MJOPTheme.accent.opacity(enabled ? 0.32 : 0), radius: 10, x: 0, y: 8)
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .opacity(configuration.isPressed ? 0.9 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// Tweede knop: lichtblauw vlak met blauwe tekst.
struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 52)
            .foregroundStyle(MJOPTheme.accent)
            .background(Premium.accentSoft, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .opacity(configuration.isPressed ? 0.7 : 1)
    }
}

/// Kopje boven een groep, met optioneel een knop rechts.
struct SectionHeader<Trailing: View>: View {
    let title: String
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title).font(.title3.weight(.bold))
            Spacer()
            trailing()
        }
        .padding(.horizontal, 4)
        .accessibilityAddTraits(.isHeader)
    }
}

extension SectionHeader where Trailing == EmptyView {
    init(title: String) { self.init(title: title) { EmptyView() } }
}

/// Eén kerncijfer met label eronder (voor de cijferstrook op het projectscherm).
struct StatCell: View {
    let value: String
    let label: String
    var identifier: String? = nil

    var body: some View {
        VStack(spacing: 2) {
            Text(value).font(.title3.weight(.bold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
                .accessibilityIdentifier(identifier ?? "stat-\(label)")
            Text(label).font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center).lineLimit(2)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
    }
}

/// Bedragen in euro's zonder centen, Nederlandse notatie.
enum EuroText {
    private static let formatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency; f.currencyCode = "EUR"; f.locale = Locale(identifier: "nl_NL"); f.maximumFractionDigits = 0
        return f
    }()
    static func string(_ v: Int) -> String { formatter.string(from: NSNumber(value: v)) ?? "€ \(v)" }
}

/// Dag en datum bovenaan Home, bijvoorbeeld "donderdag 12 november".
func todayText(_ date: Date = Date()) -> String {
    let f = DateFormatter()
    f.locale = Locale(identifier: "nl_NL")
    f.setLocalizedDateFormatFromTemplate("EEEEdMMMM")
    return f.string(from: date)
}
