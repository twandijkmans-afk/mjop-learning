import MJOPIntegration
import SwiftUI

/// De gedeelde WebView met daarboven de projectbalk. Alle websiteonderdelen in de tabs gebruiken dit; er bestaat maar één WebView.
struct WebScreen: View {
    @ObservedObject var web: MJOPWebController
    @EnvironmentObject var nav: AppNavigator

    var body: some View {
        VStack(spacing: 0) {
            ProjectContextBar(status: web.webStatus, online: web.isOnline)
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
