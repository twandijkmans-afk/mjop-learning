import MJOPIntegration
import SwiftUI

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

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    if !web.isOnline { OfflineNote(text: "Je bent offline. Metingen op dit toestel werken gewoon door; projectgegevens zijn pas weer te zien met internet.") }
                    projectCard
                    newProjectButton
                    nextStepCard
                    recentProjectsCard
                    measureCard
                    statusCard
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Home")
            .task { await reload() }
            .refreshable { await reload() }
        }
    }

    private func reload() async {
        await nav.refreshProjects()
    }

    private func continueInMJOP(_ p: ProjectSummary) {
        if isOpen { nav.selected = .mjop } else { Task { await nav.open(p) } }
    }

    private var projectCard: some View {
        CardView(title: "Laatst geopende project", icon: "folder") {
            if let p = lastProject {
                AerialPhotoView(address: p.adres ?? p.label)
                    .frame(height: 130).frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                VStack(alignment: .leading, spacing: 4) {
                    Text(p.label).font(.headline).accessibilityIdentifier("homeProjectLabel")
                    if let a = p.adres, a != p.label { Text(a).font(.subheadline).foregroundStyle(.secondary) }
                    if let d = p.updatedDate { Text("Laatst bijgewerkt \(relativeDateText(d))").font(.caption).foregroundStyle(.secondary) }
                }
                Button { continueInMJOP(p) } label: { Text(isOpen ? "Verder in MJOP" : "Project openen").frame(maxWidth: .infinity) }
                    .buttonStyle(.borderedProminent).accessibilityIdentifier("homeOpenProject")
            } else if web.webStatus?.loggedIn == false {
                Text("Je bent niet ingelogd.").foregroundStyle(.secondary)
                Button("Naar Profiel") { nav.selected = .profile }.buttonStyle(.bordered)
            } else if nav.projectsLoading || web.webStatus == nil {
                HStack { ProgressView(); Text("Project laden…").foregroundStyle(.secondary) }
            } else if let e = nav.projectsError {
                Text(e).foregroundStyle(.secondary)
                Button("Opnieuw proberen") { Task { await reload() } }.buttonStyle(.bordered)
            } else {
                Text("Je hebt nog geen opgeslagen projecten.").foregroundStyle(.secondary)
                Button("Naar Projecten") { nav.selected = .projects }.buttonStyle(.bordered)
            }
        }
    }

    /// Een nieuw project start met de stappen van de website (zelfde als het plusje bij Projecten).
    @ViewBuilder private var newProjectButton: some View {
        if web.webStatus?.loggedIn != false {
            NavigationLink { WebScreenPage(title: "Nieuw project", command: .newProject, web: web) } label: {
                Label("Nieuw project", systemImage: "plus").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent).controlSize(.large).accessibilityIdentifier("homeNewProject")
        }
    }

    /// De andere recent bijgewerkte projecten (maximaal drie), zonder het project dat hierboven al staat.
    private var recentProjects: [ProjectSummary] {
        let others = (nav.projectList?.projects ?? []).filter { $0.id != lastProject?.id }
        return Array(others.sorted { ($0.updatedDate ?? .distantPast) > ($1.updatedDate ?? .distantPast) }.prefix(3))
    }

    @ViewBuilder private var recentProjectsCard: some View {
        let list = recentProjects
        if !list.isEmpty {
            CardView(title: "Recente projecten", icon: "clock") {
                ForEach(list) { p in
                    NavigationLink { ProjectDetailView(project: p, web: web) } label: {
                        HStack(spacing: 12) {
                            AerialPhotoView(address: p.adres ?? p.label)
                                .frame(width: 64, height: 48)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(p.label).font(.subheadline.weight(.medium)).foregroundStyle(Color.primary).multilineTextAlignment(.leading)
                                if let d = p.updatedDate {
                                    Text("Laatst bijgewerkt \(relativeDateText(d))").font(.caption).foregroundStyle(Color.secondary)
                                }
                            }
                            Spacer(minLength: 0)
                            Image(systemName: "chevron.right").font(.footnote).foregroundStyle(.tertiary)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("homeRecent-\(p.label)")
                }
                Button("Alle projecten") { nav.selected = .projects }.buttonStyle(.bordered)
            }
        }
    }

    private var nextStepCard: some View {
        CardView(title: "Volgende stap", icon: "arrow.right.circle") {
            if let n = web.webStatus?.pendingProposals, n > 0, isOpen {
                Text(pendingText(n))
                Button("Naar Meten") { nav.selected = .measure }.buttonStyle(.bordered).accessibilityIdentifier("homeToMeasure")
            } else if let p = lastProject, let step = (isOpen ? web.webStatus?.nextStep : nil) ?? p.nextStep {
                Text(step)
                Button("Ga verder") { continueInMJOP(p) }.buttonStyle(.bordered)
            } else {
                Text("Open een project om te zien wat de volgende stap is.").foregroundStyle(.secondary)
            }
        }
    }

    private var measureCard: some View {
        CardView(title: "Gevelfoto en voorstellen", icon: "camera.viewfinder") {
            StatusRow(label: "Gevelfoto's (geopend project)", value: isOpen ? (web.webStatus?.details.map { String($0.gevelfotos) } ?? "–") : "–", identifier: "homeGevelfotos")
            StatusRow(label: "Voorstellen te controleren (geopend project)", value: isOpen ? "\(web.webStatus?.pendingProposals ?? 0)" : "–", identifier: "homePending")
            Button("Naar Meten") { nav.selected = .measure }.buttonStyle(.bordered)
        }
    }

    private var statusCard: some View {
        CardView(title: "Verbinding en synchronisatie", icon: "arrow.triangle.2.circlepath") {
            StatusRow(label: "Verbinding", value: web.isOnline ? "Verbonden" : "Offline", tint: web.isOnline ? MJOPTheme.green : .orange, identifier: "homeConnection")
            StatusRow(label: "Account", value: accountText, identifier: "homeAccount")
            if let s = web.webStatus?.saveStatus.label, web.webStatus?.hasBuilding == true {
                StatusRow(label: "Opslag project", value: s, tint: web.webStatus?.saveStatus.tint ?? .primary, identifier: "homeSave")
            }
        }
    }

    private func pendingText(_ n: Int) -> String {
        n == 1 ? "Er wacht 1 voorstel uit de fotoronde op controle." : "Er wachten \(n) voorstellen uit de fotoronde op controle."
    }

    private var accountText: String {
        guard let s = web.webStatus else { return "Wordt gecontroleerd…" }
        return s.loggedIn ? "Ingelogd" : "Niet ingelogd"
    }
}
