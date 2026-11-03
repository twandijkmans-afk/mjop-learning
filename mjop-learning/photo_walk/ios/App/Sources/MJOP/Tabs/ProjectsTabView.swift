import MJOPIntegration
import SwiftUI

/// Projecten van de ingelogde gebruiker, rechtstreeks uit de backend (via de website). Geen voorbeeldprojecten, niets verzonnen.
struct ProjectsTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController

    var body: some View {
        NavigationStack {
            content
                .navigationTitle("Projecten")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        NavigationLink {
                            WebScreenPage(title: "Nieuw project", command: .newProject, web: web)
                        } label: {
                            Image(systemName: "plus")
                        }
                        .accessibilityLabel("Nieuw project")
                        .accessibilityIdentifier("newProject")
                    }
                }
                .task { await nav.refreshProjects() }
                .refreshable { await nav.refreshProjects() }
                .onChange(of: web.webStatus?.loggedIn) { _ in Task { await nav.refreshProjects() } }
        }
    }

    @ViewBuilder private var content: some View {
        if let list = nav.projectList {
            if !list.loggedIn {
                EmptyStateView(icon: "person.crop.circle.badge.exclamationmark", title: "Niet ingelogd",
                               message: "Log in om je opgeslagen projecten te zien.", actionTitle: "Naar Profiel", action: { nav.selected = .profile })
            } else if list.projects.isEmpty {
                EmptyStateView(icon: "folder", title: "Nog geen opgeslagen projecten",
                               message: "Maak een nieuw project met het plusje rechtsboven. Het verschijnt hier zodra het is opgeslagen.")
            } else {
                projectList(list)
            }
        } else if let e = nav.projectsError {
            EmptyStateView(icon: "exclamationmark.triangle", title: "Projecten laden mislukt", message: e,
                           actionTitle: "Opnieuw proberen", action: { Task { await nav.refreshProjects() } })
        } else {
            ProgressView("Projecten laden…").frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private func projectList(_ list: ProjectList) -> some View {
        List {
            if !web.isOnline {
                Section { Label("Je bent offline. Deze lijst kan verouderd zijn.", systemImage: "wifi.slash").foregroundStyle(.orange) }
            }
            if let e = nav.projectsError {
                Section { Label(e, systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
            }
            Section {
                ForEach(list.projects) { p in
                    Button { Task { await nav.open(p) } } label: {
                        ProjectRow(project: p, isOpen: p.id == web.webStatus?.planId)
                    }
                    .accessibilityIdentifier("projectRow-\(p.label)")
                }
            } footer: {
                Text("Een project openen toont het in MJOP. Nieuwe projecten maak je voorlopig met de stappen van de website (plusje rechtsboven).")
            }
        }
    }
}
