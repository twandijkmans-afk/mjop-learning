import MJOPIntegration
import SwiftUI

/// Projecten van de ingelogde gebruiker, rechtstreeks uit de backend (via de website). Geen voorbeeldprojecten, niets verzonnen.
struct ProjectsTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @State private var query = ""

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

    private func filtered(_ list: ProjectList) -> [ProjectSummary] {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return list.projects }
        return list.projects.filter { p in
            p.label.range(of: q, options: [.caseInsensitive, .diacriticInsensitive]) != nil
                || (p.adres?.range(of: q, options: [.caseInsensitive, .diacriticInsensitive]) != nil)
        }
    }

    private func projectList(_ list: ProjectList) -> some View {
        let shown = filtered(list)
        return ScrollView {
            LazyVStack(spacing: 14) {
                if !web.isOnline { OfflineNote(text: "Je bent offline. Deze lijst kan verouderd zijn.") }
                if let e = nav.projectsError {
                    Label(e, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(.orange)
                        .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.orange.opacity(0.15)).clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
                if shown.isEmpty {
                    Text("Geen project gevonden voor \u{201C}\(query)\u{201D}.").font(.subheadline).foregroundStyle(.secondary).padding(.top, 24)
                }
                ForEach(shown) { p in
                    NavigationLink { ProjectDetailView(project: p, web: web) } label: {
                        ProjectCard(project: p, isOpen: p.id == web.webStatus?.planId)
                    }
                    .buttonStyle(.plain)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("projectRow-\(p.label)")
                }
                Text("Een project openen toont eerst de details. Nieuwe projecten maak je voorlopig met de stappen van de website (plusje rechtsboven).")
                    .font(.footnote).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 4)
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .searchable(text: $query, prompt: "Zoek een project")
    }
}
