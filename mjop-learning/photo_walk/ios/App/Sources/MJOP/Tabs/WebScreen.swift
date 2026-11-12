import MJOPIntegration
import SwiftUI

/// De gedeelde WebView, op verzoek met daarboven de projectbalk. Alle websiteonderdelen in de tabs gebruiken dit; er bestaat maar één WebView.
struct WebScreen: View {
    @ObservedObject var web: MJOPWebController
    @EnvironmentObject var nav: AppNavigator
    /// Projectbalk erboven: alleen waar de kop zelf niet al zegt in welk project je werkt (bijvoorbeeld de gevelfoto).
    var showProject = false

    var body: some View {
        VStack(spacing: 0) {
            if showProject { ProjectContextBar(status: web.webStatus, online: web.isOnline) }
            MJOPContainerView(web: web)
        }
    }
}

/// Een pagina (in een NavigationStack) die één websiteonderdeel toont. Stuurt bij openen het navigatiecommando naar de website.
struct WebScreenPage: View {
    let title: String
    let command: NativeCommand
    @ObservedObject var web: MJOPWebController

    var body: some View {
        WebScreen(web: web)
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .task { _ = await web.send(command) }
    }
}
