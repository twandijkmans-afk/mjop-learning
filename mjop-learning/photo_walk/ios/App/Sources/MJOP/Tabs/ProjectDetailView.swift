import MJOPIntegration
import SwiftUI

/// Eén rij in de lijst van het projectdetailscherm: pictogramvlak, titel met toelichting, en een pijltje.
struct DetailRow: View {
    let icon: String
    var tint: Color = MJOPTheme.accent
    let title: String
    let value: String
    var chevron = false
    var identifier: String? = nil

    var body: some View {
        HStack(spacing: 14) {
            IconTile(systemName: icon, color: tint)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body).foregroundStyle(Color.primary)
                Text(value).font(.subheadline).foregroundStyle(Color.secondary).multilineTextAlignment(.leading)
            }
            Spacer(minLength: 8)
            if chevron { Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary) }
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier(identifier ?? "detail-\(title)")
    }
}

/// Projectdetails: luchtfoto over de volle breedte met de naam erop, een strook met kerncijfers, de knop naar het MJOP en rijen naar de onderdelen.
/// Alleen echte gegevens. De gebouwgegevens komen uit het geopende project in de website (alleen lezen); is het project niet geladen, dan staat er
/// "–" en nooit een verzonnen getal. Niet-opgeslagen werk in een ander project wordt nooit stil vervangen.
struct ProjectDetailView: View {
    let project: ProjectSummary
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @State private var loading = true
    @State private var notLoaded = false

    private var isOpen: Bool { web.webStatus?.planId == project.id }
    private var details: BuildingDetails? { isOpen ? web.webStatus?.details : nil }
    private var nextStep: String? { (isOpen ? web.webStatus?.nextStep : nil) ?? project.nextStep }

    private let heroHeight: CGFloat = 340

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                hero
                VStack(spacing: 16) {
                    statStrip
                    Button { openMJOP() } label: { Text("Open MJOP") }
                        .buttonStyle(PrimaryButtonStyle())
                        .accessibilityHint("Planning, begroting en rapportage")
                        .accessibilityIdentifier("detailOpenMJOP")
                    if let step = nextStep {
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "arrow.right.circle.fill").foregroundStyle(MJOPTheme.accent).accessibilityHidden(true)
                            VStack(alignment: .leading, spacing: 1) {
                                Text("Volgende stap").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                                Text(step).font(.subheadline.weight(.medium))
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(.horizontal, 4)
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("detailNextStep")
                    }
                    rows
                    if notLoaded {
                        Label("De gebouwgegevens zijn nu niet geladen: er zijn niet-opgeslagen wijzigingen in een ander project, of je bent offline. Open het project bij MJOP voor alle gegevens.",
                              systemImage: "info.circle")
                            .font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                            .accessibilityIdentifier("detailNotLoaded")
                    }
                }
                .padding(.horizontal, 16).padding(.top, 16).padding(.bottom, 24)
            }
        }
        .background(Premium.canvas)
        .ignoresSafeArea(edges: .top)
        .navigationTitle("Project").navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.hidden, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task { await load() }
    }

    /// Luchtfoto die meerekt als je naar beneden trekt, met naam en adres erop.
    private var hero: some View {
        GeometryReader { g in
            let pull = max(0, g.frame(in: .global).minY)
            ZStack(alignment: .bottomLeading) {
                LinearGradient(stops: [.init(color: .black.opacity(0.45), location: 0), .init(color: .black.opacity(0), location: 0.3),
                                       .init(color: .black.opacity(0), location: 0.5), .init(color: .black.opacity(0.8), location: 1)],
                               startPoint: .top, endPoint: .bottom)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    if isOpen { GlassChip(text: "Geopend", dot: Premium.ok).padding(.bottom, 6) }
                    Text(project.label).font(.largeTitle.weight(.bold)).lineLimit(2).minimumScaleFactor(0.7)
                        .accessibilityIdentifier("detailTitle")
                    if let a = project.adres, a != project.label { Text(a).font(.subheadline).opacity(0.85) }
                    if let d = project.updatedDate { Text("Laatst bijgewerkt \(relativeDateText(d))").font(.caption).opacity(0.75) }
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 20).padding(.bottom, 20)
            }
            .frame(width: g.size.width, height: heroHeight + pull)
            .background { AerialPhotoView(address: project.adres ?? project.label) }
            .clipped()
            .offset(y: -pull)
        }
        .frame(height: heroHeight)
    }

    private var statStrip: some View {
        HStack(spacing: 0) {
            StatCell(value: details?.bouwjaar.map(String.init) ?? "–", label: "Bouwjaar", identifier: "detailStatBouwjaar")
            Divider().frame(height: 34)
            StatCell(value: details?.units.map(String.init) ?? "–", label: "Appartementen", identifier: "detailStatUnits")
            Divider().frame(height: 34)
            StatCell(value: details?.gevelM2.map { $0.formatted() } ?? "–", label: details?.gevelGeschat == true ? "m² gevel · geschat" : "m² gevel", identifier: "detailStatGevel")
            Divider().frame(height: 34)
            StatCell(value: details?.posten.map(String.init) ?? "–", label: "Posten", identifier: "detailStatPosten")
        }
        .padding(.vertical, 14)
        .premiumCard()
        .redacted(reason: loading && details == nil ? .placeholder : [])
    }

    private var rows: some View {
        VStack(spacing: 0) {
            NavigationLink { BuildingFactsView(project: project, web: web, loading: $loading) } label: {
                DetailRow(icon: "building.2.fill", tint: Premium.ink, title: "Gebouwgegevens", value: factsSummary, chevron: true, identifier: "detailFacts")
            }
            .buttonStyle(PressableRowStyle())
            Divider().padding(.leading, 60)
            NavigationLink { GevelfotoScreen(project: project, web: web) } label: {
                DetailRow(icon: "camera.viewfinder", title: "Gevelfoto's en voorstellen", value: facadeText, chevron: true, identifier: "detailFacades")
            }
            .buttonStyle(PressableRowStyle())
        }
        .premiumCard(radius: 18)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func load() async {
        loading = true
        let ok = await nav.loadForDetails(project)
        notLoaded = !ok && web.webStatus?.planId != project.id
        loading = false
    }

    /// Staat het project al in de website (het detailscherm heeft het geladen), dan schakelen we meteen naar MJOP en laten de website op de achtergrond
    /// naar de planning gaan; anders opent `nav.open` het project eerst (met de bevestiging bij niet-opgeslagen werk).
    private func openMJOP() {
        if isOpen {
            nav.mjopSection = .planning
            nav.measureProjectId = project.id
            nav.selected = .mjop
            Task { await nav.showMJOPSection() }
        } else {
            Task { await nav.open(project) }
        }
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
        guard let d = details else { return loading ? "Laden…" : "Gevelfoto maken en voorstellen controleren" }
        let fotos = d.gevelfotos == 1 ? "1 gevelfoto" : "\(d.gevelfotos) gevelfoto's"
        guard let n = web.webStatus?.pendingProposals, n > 0 else { return fotos }
        return fotos + " · " + (n == 1 ? "1 voorstel te controleren" : "\(n) voorstellen te controleren")
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
