import MJOPIntegration
import SwiftUI

/// Wat er lokaal op dit toestel speelt (scanner). Komt uit de bestaande lokale opslag; er wordt niets gewijzigd.
struct LocalMeasureSummary: Equatable {
    var inProgress = 0
    var unsynced = 0

    @MainActor static func load(_ rounds: RoundCoordinator) -> LocalMeasureSummary {
        let inProgress = Persistence.rounds().filter { $0.0.round?.status != "COMPLETED" }.count
        let unsynced = rounds.outbox.rounds.filter { !$0.isSynced }.count
        return LocalMeasureSummary(inProgress: inProgress, unsynced: unsynced)
    }
}

struct HomeTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @EnvironmentObject var rounds: RoundCoordinator
    @ObservedObject var web: MJOPWebController
    @State private var local = LocalMeasureSummary()

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
                    nextStepCard
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
        local = LocalMeasureSummary.load(rounds)
    }

    private func continueInMJOP(_ p: ProjectSummary) {
        if isOpen { nav.selected = .mjop } else { Task { await nav.open(p) } }
    }

    private var projectCard: some View {
        CardView(title: "Laatst geopende project", icon: "folder") {
            if let p = lastProject {
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
        CardView(title: "Metingen en voorstellen", icon: "viewfinder") {
            StatusRow(label: "Voorstellen te controleren (geopend project)", value: isOpen ? "\(web.webStatus?.pendingProposals ?? 0)" : "–", identifier: "homePending")
            StatusRow(label: "Onderbroken fotorondes op dit toestel", value: "\(local.inProgress)", identifier: "homeInProgress")
            StatusRow(label: "Nog niet overgedragen aan MJOP", value: "\(local.unsynced)", tint: local.unsynced > 0 ? .orange : .primary, identifier: "homeUnsynced")
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
