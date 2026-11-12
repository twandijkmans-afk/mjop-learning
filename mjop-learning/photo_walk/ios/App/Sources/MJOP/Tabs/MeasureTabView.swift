import MJOPIntegration
import SwiftUI

/// Meten: de gevelfoto. Project kiezen en een foto van een gevel maken; Claude herkent de elementen, de app rekent de hoeveelheden met vaste regels.
/// De oude camera-scanner (fotoronde met LiDAR) bestaat niet meer. De uitkomst is altijd een voorstel; er wordt niets automatisch overgenomen.
struct MeasureTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @State private var showPicker = false

    private var project: ProjectSummary? { nav.measureProject }
    private var isOpen: Bool { project.map { $0.id == web.webStatus?.planId } ?? false }

    var body: some View {
        NavigationStack {
            List {
                if !web.isOnline {
                    Section { Label("Je bent offline. Een gevelfoto maken vraagt internet: het project wordt geopend en de herkenning loopt via Claude.", systemImage: "wifi.slash").font(.footnote).foregroundStyle(.orange) }
                }
                Section {
                    HStack(spacing: 14) {
                        GradientTile(systemName: "camera.viewfinder")
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Gevelfoto").font(.title3.weight(.bold))
                            Text("Eén foto per gevel. Claude herkent de elementen, de app rekent de hoeveelheden.")
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 6)
                    .accessibilityElement(children: .combine)
                }
                Section("Project") {
                    Button { showPicker = true } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(project?.label ?? "Geen project gekozen").font(.headline).foregroundStyle(Color.primary)
                                Text(projectHint).font(.caption).foregroundStyle(Color.secondary)
                            }
                            Spacer()
                            Text("Kies").foregroundStyle(.tint)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("measureProjectButton")
                }
                Section {
                    if let p = project {
                        NavigationLink { GevelfotoScreen(project: p, web: web) } label: {
                            Label("Gevelfoto maken", systemImage: "camera.viewfinder")
                        }
                        .accessibilityIdentifier("measureStart")
                    } else {
                        // Zonder project kan er geen gevelfoto gemaakt worden: deze knop vraagt dan eerst om het project (geen knop die niets doet).
                        Button { showPicker = true } label: {
                            Label("Gevelfoto maken", systemImage: "camera.viewfinder")
                        }
                        .accessibilityHint("Kies eerst het project")
                        .accessibilityIdentifier("measureStart")
                    }
                } header: {
                    Text("Gevel meten")
                } footer: {
                    Text("Maak een foto van een gevel. Claude herkent kozijnen, metselwerk, afvoeren en de dakgoot; de hoeveelheden rekent de app zelf uit met vaste regels. De uitkomst is een voorstel: er wordt niets automatisch aan het MJOP toegevoegd. Onbekende maten blijven onbekend.")
                }
                if isOpen, let s = web.webStatus {
                    Section("Dit project") {
                        StatusRow(label: "Gevelfoto's", value: s.details.map { String($0.gevelfotos) } ?? "–", identifier: "measureGevelfotos")
                        StatusRow(label: "Voorstellen te controleren", value: String(s.pendingProposals), identifier: "measurePending")
                    }
                }
            }
            .navigationTitle("Meten")
            .sheet(isPresented: $showPicker) { ProjectPickerView() }
            .task { await nav.refreshProjects() }
        }
    }

    private var projectHint: String {
        if project == nil { return web.webStatus?.loggedIn == false ? "Log eerst in via Profiel" : "Kies het project waar de gevelfoto bij hoort" }
        return "De gevelfoto hoort bij dit project"
    }
}

/// Opent het gekozen project in de website (zonder stil niet-opgeslagen werk te vervangen) en toont daar de pagina Gevelfoto.
/// De gevelfoto zelf (camera met waterpas, herkenning door Claude, maat uit de BAG) draait in de website.
struct GevelfotoScreen: View {
    let project: ProjectSummary
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @State private var phase: Phase = .loading

    enum Phase { case loading, ready, notOpened }

    var body: some View {
        Group {
            switch phase {
            case .loading:
                ProgressView("Project openen…").frame(maxWidth: .infinity, maxHeight: .infinity)
            case .ready:
                WebScreen(web: web, showProject: true)
            case .notOpened:
                EmptyStateView(icon: "exclamationmark.triangle", title: "Project niet geopend",
                               message: "Er zijn niet-opgeslagen wijzigingen in een ander project, of je bent offline. Sla dat project eerst op, of open dit project bij MJOP.",
                               actionTitle: "Opnieuw proberen", action: { Task { await load() } })
            }
        }
        .navigationTitle("Gevelfoto")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load() async {
        phase = .loading
        guard await nav.loadForDetails(project) else { phase = .notOpened; return }
        _ = await web.send(.navigate(tab: "fotoronde", sub: nil))
        phase = .ready
    }
}

struct ProjectPickerView: View {
    @EnvironmentObject var nav: AppNavigator
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if let list = nav.projectList, list.loggedIn, !list.projects.isEmpty {
                    List(list.projects) { p in
                        Button {
                            nav.measureProjectId = p.id
                            dismiss()
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(p.label).font(.headline).foregroundStyle(.primary)
                                    if let a = p.adres, a != p.label { Text(a).font(.caption).foregroundStyle(.secondary) }
                                }
                                Spacer()
                                if nav.measureProject?.id == p.id { Image(systemName: "checkmark").foregroundStyle(MJOPTheme.accent) }
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    .accessibilityIdentifier("pickProject-\(p.label)")
                    }
                } else if nav.projectList?.loggedIn == false {
                    EmptyStateView(icon: "person.crop.circle.badge.exclamationmark", title: "Niet ingelogd", message: "Log in via Profiel om een project te kiezen.")
                } else if nav.projectList != nil {
                    EmptyStateView(icon: "folder", title: "Nog geen opgeslagen projecten", message: "Maak eerst een project aan en sla het op.")
                } else if let e = nav.projectsError {
                    EmptyStateView(icon: "exclamationmark.triangle", title: "Projecten laden mislukt", message: e, actionTitle: "Opnieuw proberen", action: { Task { await nav.refreshProjects() } })
                } else {
                    ProgressView("Projecten laden…")
                }
            }
            .navigationTitle("Project kiezen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Sluiten") { dismiss() } } }
        }
    }
}
