import MJOPIntegration
import SwiftUI

/// Eén rij in de lijst van het projectdetailscherm: pictogram, titel en waarde (of toelichting).
struct DetailRow: View {
    let icon: String
    let title: String
    let value: String
    var chevron = false
    var identifier: String? = nil

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: icon).font(.body).foregroundStyle(MJOPTheme.accent).frame(width: 26)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body.weight(.medium)).foregroundStyle(Color.primary)
                Text(value).font(.subheadline).foregroundStyle(Color.secondary).multilineTextAlignment(.leading)
            }
            Spacer(minLength: 8)
            if chevron { Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary) }
        }
        .padding(.horizontal, 16).padding(.vertical, 13)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier(identifier ?? "detail-\(title)")
    }
}

/// Projectdetails zoals in het ontwerp: grote luchtfoto, naam en adres, en rijen naar Gebouwgegevens, Gevels, Foto's en inspecties en MJOP.
/// Alleen echte gegevens. De gebouwgegevens komen uit het geopende project in de website (alleen lezen); is het project niet geladen, dan staat er
/// "Onbekend" of "–" en nooit een verzonnen getal. Niet-opgeslagen werk in een ander project wordt nooit stil vervangen.
struct ProjectDetailView: View {
    let project: ProjectSummary
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @State private var loading = true
    @State private var notLoaded = false

    private var isOpen: Bool { web.webStatus?.planId == project.id }
    private var details: BuildingDetails? { isOpen ? web.webStatus?.details : nil }
    private var nextStep: String? { (isOpen ? web.webStatus?.nextStep : nil) ?? project.nextStep }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                AerialPhotoView(address: project.adres ?? project.label)
                    .frame(height: 220).frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                VStack(alignment: .leading, spacing: 4) {
                    Text(project.label).font(.title2.weight(.bold)).accessibilityIdentifier("detailTitle")
                    if let a = project.adres, a != project.label { Text(a).font(.subheadline).foregroundStyle(.secondary) }
                    if let d = project.updatedDate { Text("Laatst bijgewerkt \(relativeDateText(d))").font(.caption).foregroundStyle(.secondary) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                VStack(spacing: 0) {
                    DetailRow(icon: "arrow.right.circle", title: "Volgende stap", value: nextStep ?? "–", identifier: "detailNextStep")
                    Divider().padding(.leading, 56)
                    NavigationLink { BuildingFactsView(project: project, web: web, loading: $loading) } label: {
                        DetailRow(icon: "building.2", title: "Gebouwgegevens", value: factsSummary, chevron: true, identifier: "detailFacts")
                    }
                    .buttonStyle(.plain)
                    Divider().padding(.leading, 56)
                    Button { goMeasure() } label: {
                        DetailRow(icon: "square.grid.2x2", title: "Gevels en elementen", value: facadeText, chevron: true, identifier: "detailFacades")
                    }
                    .buttonStyle(.plain)
                    Divider().padding(.leading, 56)
                    Button { goMeasure() } label: {
                        DetailRow(icon: "camera", title: "Foto's en inspecties", value: inspectionText, chevron: true, identifier: "detailInspections")
                    }
                    .buttonStyle(.plain)
                    Divider().padding(.leading, 56)
                    Button { Task { await nav.open(project) } } label: {
                        DetailRow(icon: "calendar", title: "MJOP", value: "Planning, begroting en rapportage", chevron: true, identifier: "detailOpenMJOP")
                    }
                    .buttonStyle(.plain)
                }
                .background(Color(.secondarySystemGroupedBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))

                if notLoaded {
                    Label("De gebouwgegevens zijn nu niet geladen: er zijn niet-opgeslagen wijzigingen in een ander project, of je bent offline. Open het project bij MJOP voor alle gegevens.",
                          systemImage: "info.circle")
                        .font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityIdentifier("detailNotLoaded")
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Project").navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        loading = true
        let ok = await nav.loadForDetails(project)
        notLoaded = !ok && web.webStatus?.planId != project.id
        loading = false
    }

    private func goMeasure() {
        nav.measureProjectId = project.id
        nav.selected = .measure
    }

    private var factsSummary: String {
        if let d = details {
            var parts: [String] = []
            if let y = d.bouwjaar { parts.append("Bouwjaar \(y)") }
            if let u = d.units { parts.append(u == 1 ? "1 appartement" : "\(u) appartementen") }
            return parts.isEmpty ? "Onbekend" : parts.joined(separator: " · ")
        }
        return loading ? "Laden…" : "Niet beschikbaar"
    }

    private var facadeText: String {
        guard let d = details else { return loading ? "Laden…" : "–" }
        return d.gevelfotos == 1 ? "1 gevelfoto" : "\(d.gevelfotos) gevelfoto's"
    }

    private var inspectionText: String {
        guard isOpen, let n = web.webStatus?.pendingProposals else { return loading ? "Laden…" : "–" }
        return n == 0 ? "Geen voorstellen om te controleren" : (n == 1 ? "1 voorstel om te controleren" : "\(n) voorstellen om te controleren")
    }
}

/// Alle gebouwgegevens van een project onder elkaar. Onbekend blijft "Onbekend"; een afgeleid oppervlak wordt zo genoemd.
struct BuildingFactsView: View {
    let project: ProjectSummary
    @ObservedObject var web: MJOPWebController
    @Binding var loading: Bool

    /// Live uit de website: de gegevens kunnen binnenkomen terwijl dit scherm al open is.
    private var details: BuildingDetails? { web.webStatus?.planId == project.id ? web.webStatus?.details : nil }

    private static let euro: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency; f.currencyCode = "EUR"; f.locale = Locale(identifier: "nl_NL"); f.maximumFractionDigits = 0
        return f
    }()

    private func m2(_ v: Int?, derived: Bool) -> String {
        guard let v else { return "Onbekend" }
        return "\(v) m²" + (derived ? " (geschat)" : "")
    }

    var body: some View {
        List {
            if let d = details {
                Section {
                    row("Bouwjaar", d.bouwjaar.map(String.init) ?? "Onbekend", id: "factBouwjaar")
                    row("Appartementen", d.units.map(String.init) ?? "Onbekend", id: "factUnits")
                    row("Dakoppervlak", m2(d.dakM2, derived: d.dakGeschat), id: "factDak")
                    row("Geveloppervlak", m2(d.gevelM2, derived: d.gevelGeschat), id: "factGevel")
                } header: { Text("Gebouw") } footer: {
                    Text("Een oppervlak met \u{201C}geschat\u{201D} is afgeleid uit de BAG-pandgeometrie en niet gemeten. Onbekende gegevens blijven onbekend.")
                }
                Section {
                    row("Onderhoudsposten", d.posten.map(String.init) ?? "Onbekend", id: "factPosten")
                    row(periodeLabel(d), d.geraamdTotaal.map { Self.euro.string(from: NSNumber(value: $0)) ?? "Onbekend" } ?? "Onbekend", id: "factTotaal")
                    row("Gevelfoto's", "\(d.gevelfotos)", id: "factGevelfotos")
                } header: { Text("Plan") } footer: {
                    Text("Kosten zijn een schatting op basis van standaardbedragen, geen offerte.")
                }
            } else {
                Section {
                    Text(loading ? "Gegevens laden…" : "De gebouwgegevens zijn niet beschikbaar. Het voorbeeldgebouw heeft er geen, en bij een project dat niet geladen is of offline zijn ze er ook niet.")
                        .foregroundStyle(.secondary).accessibilityIdentifier("factsUnavailable")
                }
            }
        }
        .navigationTitle("Gebouwgegevens").navigationBarTitleDisplayMode(.inline)
    }

    private func periodeLabel(_ d: BuildingDetails) -> String {
        if let a = d.periodeVan, let b = d.periodeTot { return "Geraamd onderhoud \(a)–\(b)" }
        return "Geraamd onderhoud"
    }

    private func row(_ title: String, _ value: String, id: String) -> some View {
        HStack {
            Text(title).foregroundStyle(.secondary)
            Spacer()
            Text(value).accessibilityIdentifier(id)
        }
    }
}
