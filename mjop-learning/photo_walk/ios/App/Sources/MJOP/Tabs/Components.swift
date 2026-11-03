import MJOPIntegration
import SwiftUI

extension SaveStatus {
    /// Korte Nederlandse tekst; nil als de status onbekend is (dan tonen we niets i.p.v. iets te raden).
    var label: String? {
        switch self {
        case .saved: return "Opgeslagen"
        case .pending: return "Niet-opgeslagen wijzigingen"
        case .notSaved: return "Wijzigingen worden niet opgeslagen"
        case .error: return "Opslaan mislukt"
        case .notLoggedIn: return "Niet ingelogd"
        case .unknown: return nil
        }
    }
    var tint: Color {
        switch self {
        case .saved: return MJOPTheme.green
        case .pending, .notSaved: return .orange
        case .error: return .red
        case .notLoggedIn, .unknown: return .secondary
        }
    }
}

func relativeDateText(_ date: Date) -> String {
    let f = RelativeDateTimeFormatter()
    f.locale = Locale(identifier: "nl_NL")
    f.unitsStyle = .full
    return f.localizedString(for: date, relativeTo: Date())
}

/// Toont altijd in welk project de gebruiker werkt en of de wijzigingen worden opgeslagen.
struct ProjectContextBar: View {
    let status: WebStatus?
    let online: Bool

    private var hasProject: Bool { status?.hasBuilding == true }

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "building.2").foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 1) {
                Text(hasProject ? (status?.label ?? "Geopend project") : "Geen project geopend")
                    .font(.subheadline.weight(.semibold)).lineLimit(1)
                if hasProject || status?.loggedIn == false, let s = status?.saveStatus.label {
                    Text(s).font(.caption).foregroundStyle(status?.saveStatus.tint ?? Color.secondary)
                }
            }
            Spacer()
            if !online { Label("Offline", systemImage: "wifi.slash").font(.caption).foregroundStyle(.orange) }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(Color(.secondarySystemBackground))
        .overlay(alignment: .bottom) { Divider() }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("projectContextBar")
    }
}

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon).font(.system(size: 40)).foregroundStyle(.secondary)
            Text(title).font(.headline).multilineTextAlignment(.center)
            Text(message).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            if let actionTitle, let action {
                Button(actionTitle, action: action).buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .accessibilityElement(children: .contain)
    }
}

struct CardView<Content: View>: View {
    let title: String
    let icon: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(title, systemImage: icon).font(.subheadline.weight(.semibold)).foregroundStyle(.secondary)
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

struct StatusRow: View {
    let label: String
    let value: String
    var tint: Color = .primary
    var identifier: String? = nil

    var body: some View {
        HStack {
            Text(label).foregroundStyle(.secondary)
            Spacer()
            Text(value).foregroundStyle(tint).accessibilityIdentifier(identifier ?? "status-\(label)")
        }
        .font(.subheadline)
    }
}

struct OfflineNote: View {
    let text: String
    var body: some View {
        Label(text, systemImage: "wifi.slash")
            .font(.footnote).padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.orange.opacity(0.15)).clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .accessibilityIdentifier("offlineNote")
    }
}

struct ProjectRow: View {
    let project: ProjectSummary
    let isOpen: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(project.label).font(.headline).foregroundStyle(.primary)
                if let a = project.adres, a != project.label { Text(a).font(.subheadline).foregroundStyle(.secondary) }
                Text(project.updatedDate.map { "Laatst bijgewerkt \(relativeDateText($0))" } ?? "Laatst bijgewerkt: onbekend")
                    .font(.caption).foregroundStyle(.secondary)
                if let n = project.nextStep { Text("Volgende stap: \(n)").font(.caption).foregroundStyle(.secondary) }
            }
            Spacer()
            if isOpen {
                Text("Geopend").font(.caption.weight(.semibold)).padding(.horizontal, 8).padding(.vertical, 3)
                    .background(MJOPTheme.green.opacity(0.18)).foregroundStyle(MJOPTheme.green).clipShape(Capsule())
            } else {
                Image(systemName: "chevron.right").font(.footnote).foregroundStyle(.tertiary)
            }
        }
        .contentShape(Rectangle())
    }
}
