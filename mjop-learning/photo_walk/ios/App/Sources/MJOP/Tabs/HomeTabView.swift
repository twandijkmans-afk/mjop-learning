import MJOPIntegration
import SwiftUI

/// Home: het laatst geopende project groot met luchtfoto, de volgende stap, de kerncijfers van het geopende project en recente projecten.
/// Alleen echte gegevens: wat niet bekend is, staat er als "–" en wordt nooit geschat.
struct HomeTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController

    /// Het project dat nu in de website geopend is, anders het laatst bijgewerkte uit de backend. Nooit een verzonnen project.
    private var lastProject: ProjectSummary? {
        if let s = web.webStatus, s.hasBuilding, let id = s.planId {
            return nav.projectList?.projects.first { $0.id == id } ?? ProjectSummary(id: id, label: s.label ?? "Geopend project", nextStep: s.nextStep, isCurrent: true)
        }
        return nav.projectList?.projects.max { ($0.updatedDate ?? .distantPast) < ($1.updatedDate ?? .distantPast) }
    }
    private var isOpen: Bool { lastProject.map { $0.id == web.webStatus?.planId } ?? false }
    private var details: BuildingDetails? { isOpen ? web.webStatus?.details : nil }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(todayText().uppercased())
                        .font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
                        .padding(.horizontal, 4).padding(.top, -6)
                    if !web.isOnline { OfflineNote(text: "Je bent offline. Projectgegevens zijn pas weer te zien met internet.") }
                    hero
                    nextStepCard
                    figuresCard
                    recentProjects
                    statusFooter
                }
                .padding(.horizontal, 16).padding(.bottom, 24)
            }
            .background(Premium.canvas)
            .navigationTitle("Home")
            .toolbar {
                if web.webStatus?.loggedIn != false {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        NavigationLink { WebScreenPage(title: "Nieuw project", command: .newProject, web: web) } label: {
                            Image(systemName: "plus")
                        }
                        .accessibilityLabel("Nieuw project")
                        .accessibilityIdentifier("homeNewProject")
                    }
                }
            }
            .task { await nav.refreshProjects() }
            .refreshable { await nav.refreshProjects() }
        }
    }

    private func continueInMJOP(_ p: ProjectSummary) {
        if isOpen { nav.selected = .mjop } else { Task { await nav.open(p) } }
    }

    // MARK: held

    @ViewBuilder private var hero: some View {
        if let p = lastProject {
            ZStack(alignment: .bottomLeading) {
                LinearGradient(colors: [.black.opacity(0), .black.opacity(0.8)], startPoint: .center, endPoint: .bottom)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(isOpen ? "Geopend" : "Laatst bijgewerkt").font(.footnote.weight(.semibold)).opacity(0.75)
                    Text(p.label).font(.title2.weight(.bold)).lineLimit(2).accessibilityIdentifier("homeProjectLabel")
                    if let a = p.adres, a != p.label { Text(a).font(.subheadline).opacity(0.82).lineLimit(1) }
                    else if let d = p.updatedDate { Text("Bijgewerkt \(relativeDateText(d))").font(.subheadline).opacity(0.82) }
                    HStack(spacing: 8) {
                        if let y = details?.bouwjaar { GlassChip(text: "Bouwjaar \(y)") }
                        if let u = details?.units { GlassChip(text: "\(u) app.") }
                        Spacer(minLength: 0)
                        Button { continueInMJOP(p) } label: {
                            Text(isOpen ? "Open MJOP" : "Openen").font(.subheadline.weight(.semibold))
                                .padding(.horizontal, 16).padding(.vertical, 9)
                                .background(.white, in: Capsule()).foregroundStyle(Color.black)
                        }
                        .accessibilityIdentifier("homeOpenProject")
                    }
                    .padding(.top, 10)
                }
                .foregroundStyle(.white)
                .padding(18)
                if isOpen, let s = web.webStatus?.saveStatus.label {
                    GlassChip(text: "Geopend · \(s.lowercased())", dot: web.webStatus?.saveStatus == .saved ? Premium.ok : Premium.warn)
                        .padding(14).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                }
            }
            .frame(maxWidth: .infinity).frame(height: 300)
            // De foto als achtergrond: een vullende foto mag de breedte van de kaart niet oprekken.
            .background { AerialPhotoView(address: p.adres ?? p.label) }
            .clipShape(RoundedRectangle(cornerRadius: Premium.heroRadius, style: .continuous))
            .shadow(color: .black.opacity(0.16), radius: 20, x: 0, y: 14)
        } else {
            emptyHero
        }
    }

    private var emptyHero: some View {
        VStack(spacing: 12) {
            Image(systemName: "building.2.crop.circle").font(.largeTitle).foregroundStyle(MJOPTheme.accent).accessibilityHidden(true)
            if web.webStatus?.loggedIn == false {
                Text("Je bent niet ingelogd").font(.headline)
                Button("Naar Profiel") { nav.selected = .profile }.buttonStyle(PrimaryButtonStyle())
            } else if nav.projectsLoading || web.webStatus == nil {
                ProgressView("Project laden…")
            } else if let e = nav.projectsError {
                Text(e).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                Button("Opnieuw proberen") { Task { await nav.refreshProjects() } }.buttonStyle(SecondaryButtonStyle())
            } else {
                Text("Nog geen projecten").font(.headline)
                Text("Maak je eerste project met het plusje rechtsboven.").font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity).padding(24)
        .premiumCard(radius: Premium.heroRadius)
    }

    // MARK: volgende stap

    @ViewBuilder private var nextStepCard: some View {
        if let n = web.webStatus?.pendingProposals, n > 0, isOpen {
            stepButton(title: n == 1 ? "Er wacht 1 voorstel op controle" : "Er wachten \(n) voorstellen op controle",
                       subtitle: "Uit je gevelfoto's", icon: "checklist", id: "homeToMeasure") { nav.selected = .measure }
        } else if let p = lastProject, let step = (isOpen ? web.webStatus?.nextStep : nil) ?? p.nextStep {
            stepButton(title: step, subtitle: isOpen ? "In dit project" : p.label, icon: "arrow.right", id: "homeNextStep") { continueInMJOP(p) }
        }
    }

    private func stepButton(title: String, subtitle: String, icon: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                GradientTile(systemName: icon)
                VStack(alignment: .leading, spacing: 2) {
                    Text("VOLGENDE STAP").font(.caption.weight(.semibold)).foregroundStyle(MJOPTheme.accent)
                    Text(title).font(.headline).foregroundStyle(Color.primary).multilineTextAlignment(.leading)
                    Text(subtitle).font(.subheadline).foregroundStyle(Color.secondary).lineLimit(1)
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .premiumCard()
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier(id)
    }

    // MARK: kerncijfers

    private var figuresCard: some View {
        InkCard {
            HStack(alignment: .firstTextBaseline) {
                Text(periodTitle).font(.footnote.weight(.semibold)).opacity(0.6)
                Spacer()
                if !isOpen { Text("Open een project").font(.caption.weight(.semibold)).opacity(0.6) }
            }
            Text(details?.geraamdTotaal.map(EuroText.string) ?? "–")
                .font(.largeTitle.weight(.bold)).monospacedDigit()
                .padding(.top, 2)
                .accessibilityIdentifier("homeTotal")
            HStack(spacing: 0) {
                figure(details?.posten.map(String.init) ?? "–", "posten", id: "homePosten")
                figure(isOpen ? (details.map { String($0.gevelfotos) } ?? "–") : "–", "gevelfoto's", id: "homeGevelfotos")
                figure(isOpen ? "\(web.webStatus?.pendingProposals ?? 0)" : "–", "te controleren", id: "homePending")
            }
            .padding(.top, 14)
            Text("Geraamde kosten op basis van standaardbedragen, geen offerte.")
                .font(.caption2).opacity(0.5).padding(.top, 12)
        }
    }

    private var periodTitle: String {
        if let a = details?.periodeVan, let b = details?.periodeTot { return "Geraamd onderhoud \(a)–\(b)" }
        return "Geraamd onderhoud"
    }

    private func figure(_ value: String, _ label: String, id: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value).font(.title3.weight(.bold)).monospacedDigit().accessibilityIdentifier(id)
            Text(label).font(.caption).opacity(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    // MARK: recente projecten

    private var recent: [ProjectSummary] {
        let others = (nav.projectList?.projects ?? []).filter { $0.id != lastProject?.id }
        return Array(others.sorted { ($0.updatedDate ?? .distantPast) > ($1.updatedDate ?? .distantPast) }.prefix(6))
    }

    @ViewBuilder private var recentProjects: some View {
        let list = recent
        if !list.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                SectionHeader(title: "Recente projecten") {
                    Button("Alle") { nav.selected = .projects }.font(.subheadline.weight(.semibold))
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(list) { p in
                            NavigationLink { ProjectDetailView(project: p, web: web) } label: { recentCard(p) }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("homeRecent-\(p.label)")
                        }
                    }
                    .padding(.horizontal, 16).padding(.vertical, 12)
                }
                .padding(.horizontal, -16).padding(.vertical, -12)
            }
        }
    }

    private func recentCard(_ p: ProjectSummary) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            AerialPhotoView(address: p.adres ?? p.label).frame(width: 200, height: 112).clipped()
            VStack(alignment: .leading, spacing: 2) {
                Text(p.label).font(.subheadline.weight(.semibold)).foregroundStyle(Color.primary).lineLimit(1)
                Text(p.updatedDate.map { "Bijgewerkt \(relativeDateText($0))" } ?? "Bijgewerkt: onbekend")
                    .font(.caption).foregroundStyle(Color.secondary).lineLimit(1)
            }
            .padding(12)
        }
        .frame(width: 200, alignment: .leading)
        .premiumCard(radius: 18)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .contentShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    // MARK: status

    /// Verbinding, account en opslag klein onderaan: belangrijk om te kunnen zien, maar niet het eerste waar je naar kijkt.
    private var statusFooter: some View {
        VStack(spacing: 8) {
            StatusRow(label: "Verbinding", value: web.isOnline ? "Verbonden" : "Offline", tint: web.isOnline ? Premium.ok : Premium.warn, identifier: "homeConnection")
            StatusRow(label: "Account", value: accountText, identifier: "homeAccount")
            if let s = web.webStatus?.saveStatus.label, web.webStatus?.hasBuilding == true {
                StatusRow(label: "Opslag project", value: s, tint: web.webStatus?.saveStatus.tint ?? .primary, identifier: "homeSave")
            }
        }
        .padding(14)
        .premiumCard(radius: 18)
        .padding(.top, 4)
    }

    private var accountText: String {
        guard let s = web.webStatus else { return "Wordt gecontroleerd…" }
        return s.loggedIn ? "Ingelogd" : "Niet ingelogd"
    }
}
