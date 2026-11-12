import MJOPIntegration
import SwiftUI
import UIKit

/// Profiel: account, organisatie, weergave, abonnement, privacy, uitloggen en geavanceerde instellingen. Het beheer zelf blijft op de website;
/// hier wordt alleen genavigeerd (en gelezen). Aan abonnementen of betalingen verandert deze app niets.
struct ProfileTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @State private var confirmSignOut = false

    private var loggedIn: Bool? { web.webStatus?.loggedIn }

    var body: some View {
        NavigationStack {
            List {
                if loggedIn == false {
                    Section {
                        NavigationLink {
                            WebScreenPage(title: "Inloggen", command: .navigate(tab: "account", sub: "profiel"), web: web)
                        } label: { Label("Inloggen of account maken", systemImage: "person.crop.circle.badge.plus") }
                        .accessibilityIdentifier("profileLogin")
                        Button { web.pasteLogin(UIPasteboard.general.string ?? "") } label: { Label("Inloglink of code plakken", systemImage: "doc.on.clipboard") }
                            .accessibilityIdentifier("profilePasteLogin")
                    } header: { Text("Je bent niet ingelogd") } footer: {
                        Text("Vraag op de inlogpagina een inloglink aan. Opent de link niet in deze app? Kopieer de link of code en kies \"Inloglink of code plakken\".")
                    }
                } else {
                    Section(loggedIn == true ? "Ingelogd" : "Account") {
                        ForEach(ProfileSection.allCases, id: \.self) { s in
                            NavigationLink {
                                WebScreenPage(title: s.title, command: .navigate(tab: s.target.tab, sub: s.target.sub), web: web)
                            } label: { Label(s.title, systemImage: Self.icon(s)) }
                            .accessibilityIdentifier("profile-\(s.rawValue)")
                        }
                        if web.webStatus?.subscribed == true {
                            StatusRow(label: "Abonnement", value: "Actief", tint: Premium.ok, identifier: "profileSubscribed")
                        }
                    }
                    Section {
                        Button(role: .destructive) { confirmSignOut = true } label: { Label("Uitloggen", systemImage: "rectangle.portrait.and.arrow.right") }
                            .accessibilityIdentifier("profileSignOut")
                    }
                }
                Section {
                    NavigationLink { AdvancedSettingsView(web: web) } label: { Label("Geavanceerde instellingen", systemImage: "gearshape.2") }
                        .accessibilityIdentifier("profileAdvanced")
                } footer: {
                    Text("MJOP Live \(DeviceCapabilities.appVersion) (build \(DeviceCapabilities.buildNumber))")
                }
            }
            .navigationTitle("Profiel")
            .confirmationDialog("Uitloggen?", isPresented: $confirmSignOut, titleVisibility: .visible) {
                Button("Uitloggen", role: .destructive) { Task { await nav.signOut() } }
                Button("Annuleren", role: .cancel) {}
            } message: {
                Text(web.webStatus?.dirty == true && web.webStatus?.hasBuilding == true
                     ? "Let op: het geopende project heeft wijzigingen die nog niet zijn opgeslagen. Die gaan verloren als je uitlogt."
                     : "Je kunt daarna opnieuw inloggen met een inloglink.")
            }
        }
    }

    static func icon(_ s: ProfileSection) -> String {
        switch s {
        case .account: return "person.crop.circle"
        case .organisatie: return "building.2"
        case .weergave: return "textformat.size"
        case .abonnement: return "creditcard"
        case .privacy: return "hand.raised"
        }
    }
}

/// Geavanceerde instellingen en diagnose. Hier staan ook de opties die vroeger in het menu bovenin stonden.
struct AdvancedSettingsView: View {
    @EnvironmentObject var nav: AppNavigator
    @ObservedObject var web: MJOPWebController
    @AppStorage("mjop.classicMode") private var classicMode = false

    private var navModeText: String {
        switch web.navMode {
        case .tabs: return "Actief"
        case .classic: return "Klassiek (website kent de nieuwe navigatie niet)"
        case .pending: return "Wachten op de website…"
        }
    }

    var body: some View {
        Form {
            Section("Website") {
                Button { web.retry() } label: { Label("Website opnieuw laden", systemImage: "arrow.clockwise") }.accessibilityIdentifier("advReload")
                Button { web.loadHome() } label: { Label("Naar de startpagina van de website", systemImage: "house") }
                Button { web.presentPrint() } label: { Label("Afdrukken of bewaren als PDF", systemImage: "printer") }
                Button { web.openCurrentInSafari() } label: { Label("Openen in Safari", systemImage: "safari") }
                Button { web.pasteLogin(UIPasteboard.general.string ?? "") } label: { Label("Inloglink of code plakken", systemImage: "doc.on.clipboard") }
            }
            Section {
                Toggle("Klassieke weergave gebruiken", isOn: $classicMode).accessibilityIdentifier("advClassic")
            } footer: {
                Text("Toont de website zonder de vijf tabs, zoals in eerdere versies. Alleen nodig als de nieuwe navigatie niet goed werkt.")
            }
            Section("Diagnose") {
                diag("App-versie", DeviceCapabilities.appVersion, "diagVersion")
                diag("LiDAR beschikbaar", DeviceCapabilities.hasLiDAR ? "Ja" : "Nee", "diagLidar")
                diag("Nieuwe navigatie", navModeText, "diagNavMode")
                diag("Website-functies", web.webFeatures.isEmpty ? "–" : web.webFeatures.joined(separator: ", "), "diagFeatures")
                diag("Gedeelde WebView", "1 exemplaar", "diagWebViewCount")
                diag("Website volledig geladen", "\(web.loadCount)×", "diagLoadCount")
                diag("WebView verplaatst tussen tabs", "\(web.hostMoves)×", "diagMoves")
            }
        }
        .navigationTitle("Geavanceerd")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func diag(_ label: String, _ value: String, _ id: String) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value).foregroundStyle(.secondary).multilineTextAlignment(.trailing).accessibilityIdentifier(id)
        }
        .font(.subheadline)
    }
}
