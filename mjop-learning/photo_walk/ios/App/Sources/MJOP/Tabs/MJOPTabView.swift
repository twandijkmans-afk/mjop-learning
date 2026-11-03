import MJOPIntegration
import SwiftUI

/// MJOP: planning, maatregelen, begroting en rapportage. Voorlopig tonen we hier de bestaande website (die rekent en bewaart zoals altijd);
/// de keuzebalk en de projectbalk zijn native. Er is geen tweede rekenlogica in de app.
struct MJOPTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController

    private var hasProject: Bool { web.webStatus?.hasBuilding == true }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if hasProject {
                    Picker("Onderdeel", selection: $nav.mjopSection) {
                        ForEach(MJOPSection.allCases, id: \.self) { s in Text(s.title).tag(s) }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .accessibilityIdentifier("mjopSectionPicker")
                    WebScreen(web: web)
                } else if web.webStatus == nil {
                    ProgressView("Website laden…").frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    EmptyStateView(icon: "calendar", title: "Geen project geopend",
                                   message: web.webStatus?.loggedIn == false ? "Log in via Profiel en kies daarna een project." : "Kies eerst een project bij Projecten. Daarna zie je hier de planning, maatregelen, begroting en rapportage.",
                                   actionTitle: web.webStatus?.loggedIn == false ? "Naar Profiel" : "Naar Projecten",
                                   action: { nav.selected = web.webStatus?.loggedIn == false ? .profile : .projects })
                }
            }
            .navigationTitle("MJOP")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if hasProject && nav.mjopSection == .rapportage {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button { web.presentPrint() } label: { Image(systemName: "printer") }
                            .accessibilityLabel("Afdrukken of bewaren als PDF").accessibilityIdentifier("mjopPrint")
                    }
                }
            }
            .task(id: nav.mjopSection) { await nav.showMJOPSection() }
            .task(id: hasProject) { await nav.showMJOPSection() }
            // Navigeert de gebruiker binnen de website zelf (bijvoorbeeld via een link), dan volgt de keuzebalk.
            .onChange(of: web.webStatus?.tab) { tab in
                if let tab, let s = MJOPSection.from(webTab: tab), s != nav.mjopSection { nav.mjopSection = s }
            }
        }
    }
}
