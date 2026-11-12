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
        .alert(item: $nav.alert) { a in
            switch a {
            case .info(let title, let message):
                return Alert(title: Text(title), message: Text(message), dismissButton: .default(Text("OK")))
            case .unsavedOpen(let p):
                return Alert(title: Text("Niet-opgeslagen wijzigingen"),
                             message: Text("Het geopende project heeft wijzigingen die nog niet zijn opgeslagen. Als je \"\(p.label)\" opent, gaan die verloren."),
                             primaryButton: .destructive(Text("Toch openen")) { Task { await nav.confirmOpenAnyway(p) } },
                             secondaryButton: .cancel(Text("Annuleren")))
            case .unsavedMeasure(let p):
                return Alert(title: Text("Niet-opgeslagen wijzigingen"),
                             message: Text("Het geopende project heeft wijzigingen die nog niet zijn opgeslagen. Als je de meting voor \"\(p.label)\" start, gaan die verloren."),
                             primaryButton: .destructive(Text("Toch starten")) { Task { await nav.startMeasurement(force: true) } },
                             secondaryButton: .cancel(Text("Annuleren")))
            }
        }
    }
}
