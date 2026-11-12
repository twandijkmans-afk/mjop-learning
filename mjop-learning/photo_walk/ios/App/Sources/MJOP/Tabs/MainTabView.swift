import MJOPIntegration
import SwiftUI

/// De vijf hoofdtabs van MJOP Live. Alle websiteonderdelen gebruiken dezelfde ene WebView (`web.hostRegistry`).
struct MainTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController

    var body: some View {
        TabView(selection: $nav.selected) {
            HomeTabView(web: web)
                .tabItem { Label("Home", systemImage: "house") }
                .tag(AppNavigator.Tab.home)
            ProjectsTabView(web: web)
                .tabItem { Label("Projecten", systemImage: "folder") }
                .tag(AppNavigator.Tab.projects)
            MeasureTabView(web: web)
                .tabItem { Label("Meten", systemImage: "viewfinder") }
                .tag(AppNavigator.Tab.measure)
            MJOPTabView(web: web)
                .tabItem { Label("MJOP", systemImage: "calendar") }
                .tag(AppNavigator.Tab.mjop)
            ProfileTabView(web: web)
                .tabItem { Label("Profiel", systemImage: "person.crop.circle") }
                .tag(AppNavigator.Tab.profile)
        }
        .tint(MJOPTheme.accent)
        .alert(alertTitle, isPresented: alertShown, presenting: nav.alert) { a in
            switch a {
            case .info:
                Button("OK", role: .cancel) {}
            case .unsavedOpen(let p):
                Button("Toch openen", role: .destructive) { Task { await nav.confirmOpenAnyway(p) } }
                Button("Annuleren", role: .cancel) {}
            }
        } message: { a in
            switch a {
            case .info(_, let message): Text(message)
            case .unsavedOpen(let p): Text("Het geopende project heeft wijzigingen die nog niet zijn opgeslagen. Als je \"\(p.label)\" opent, gaan die verloren.")
            }
        }
    }

    private var alertTitle: String {
        switch nav.alert {
        case .info(let title, _): return title
        case .unsavedOpen: return "Niet-opgeslagen wijzigingen"
        case nil: return ""
        }
    }

    private var alertShown: Binding<Bool> {
        Binding(get: { nav.alert != nil }, set: { if !$0 { nav.alert = nil } })
    }
}
