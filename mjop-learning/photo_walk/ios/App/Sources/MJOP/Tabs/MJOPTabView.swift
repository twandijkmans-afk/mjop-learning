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
                    header
                    WebScreen(web: web)
                } else if web.webStatus == nil {
                    ProgressView("Website laden…").frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    EmptyStateView(icon: "calendar", title: "Geen project geopend",
                                   message: web.webStatus?.loggedIn == false ? "Log in via Profiel en kies daarna een project." : "Kies eerst een project bij Projecten. Daarna zie je hier de planning, maatregelen, begroting en rapportage.",
                                   actionTitle: web.webStatus?.loggedIn == false ? "Naar Profiel" : "Naar Projecten",
                                   action: { nav.selected = web.webStatus?.loggedIn == false ? .profile : .projects })
                        .background(Premium.canvas)
                }
            }
            .navigationTitle("MJOP")
            .toolbar(hasProject ? .hidden : .visible, for: .navigationBar)
            .task(id: nav.mjopSection) { await nav.showMJOPSection() }
            .task(id: hasProject) { await nav.showMJOPSection() }
            // Navigeert de gebruiker binnen de website zelf (bijvoorbeeld via een link), dan volgt de keuzebalk.
            .onChange(of: web.webStatus?.tab) { tab in
                if let tab, let s = MJOPSection.from(webTab: tab), s != nav.mjopSection { nav.mjopSection = s }
            }
        }
    }

    /// Eén rustige kop in plaats van drie balken: projectnaam met opslagstatus, het onderdeel in grote letters en de keuzebalk.
    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .lastTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    projectLine
                    Text(nav.mjopSection.title).font(.largeTitle.weight(.bold))
                        .accessibilityAddTraits(.isHeader)
                }
                Spacer(minLength: 8)
                if nav.mjopSection == .rapportage {
                    Button { web.presentPrint() } label: {
                        Image(systemName: "square.and.arrow.up").font(.body.weight(.semibold))
                            .frame(width: 44, height: 44)
                            .background(Premium.accentSoft, in: Circle())
                    }
                    .accessibilityLabel("Afdrukken of bewaren als PDF").accessibilityIdentifier("mjopPrint")
                }
            }
            Picker("Onderdeel", selection: $nav.mjopSection) {
                ForEach(MJOPSection.allCases, id: \.self) { s in Text(s.title).tag(s) }
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("mjopSectionPicker")
        }
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 12)
        .background(.bar)
        .overlay(alignment: .bottom) { Divider() }
    }

    /// Projectnaam en of de wijzigingen zijn opgeslagen (vervangt de aparte projectbalk). Offline staat er ook bij.
    private var projectLine: some View {
        HStack(spacing: 6) {
            if let s = web.webStatus?.saveStatus, s.label != nil {
                Circle().fill(s.tint).frame(width: 7, height: 7).accessibilityHidden(true)
            }
            Text(web.webStatus?.label ?? "Geopend project").font(.subheadline.weight(.semibold)).lineLimit(1)
            if let l = web.webStatus?.saveStatus.label { Text("· \(l)").font(.subheadline).foregroundStyle(.secondary).lineLimit(1) }
            if !web.isOnline { Label("Offline", systemImage: "wifi.slash").font(.caption.weight(.semibold)).foregroundStyle(Premium.warn) }
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("projectContextBar")
    }
}
