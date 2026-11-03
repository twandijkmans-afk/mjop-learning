import MJOPIntegration
import SwiftUI
import UIKit

/// Eén MJOP Live-interface: Mijn MJOP (de website) is de hoofdinterface. De scanner is geen aparte app of sectie meer maar een functie van het MJOP:
/// een fotoronde of een scan vanuit een onderhoudspost opent de camera schermvullend en keert terug naar het juiste scherm in Mijn MJOP.
struct RootView: View {
    @EnvironmentObject var store: ScanStore
    @StateObject private var web = MJOPWebController()
    @StateObject private var rounds = RoundCoordinator()
    @State private var showScannerTest = CommandLine.arguments.contains("-scanner-test")

    var body: some View {
        VStack(spacing: 0) {
            header
            MJOPContainerView(web: web, openScanner: { showScannerTest = true })
        }
        .onAppear {
            rounds.store = store
            rounds.deliver = { web.deliver($0) }
            rounds.notice = { web.show($0) }
            web.bridgeHandler = rounds
        }
        .onOpenURL { url in
            guard url.scheme?.lowercased() == MJOPConfig.appURLScheme else { return }
            web.handleAuthCallback(AuthCallback.parse(url))
        }
        .fullScreenCover(item: $rounds.presented) { p in
            RoundFlowView(context: p.context).environmentObject(store).environmentObject(rounds)
        }
        .fullScreenCover(isPresented: $showScannerTest) { ScannerTestView(close: { showScannerTest = false }).environmentObject(store) }
    }

    private var header: some View {
        HStack(spacing: 10) {
            Text("MJOP Live").font(.headline)
            Spacer()
            Menu {
                Button { web.retry() } label: { Label("Opnieuw laden", systemImage: "arrow.clockwise") }
                if web.canGoBack { Button { web.goBack() } label: { Label("Terug", systemImage: "chevron.backward") } }
                Button { web.loadHome() } label: { Label("Naar start", systemImage: "house") }
                Button { web.pasteLogin(UIPasteboard.general.string ?? "") } label: { Label("Inloglink of code plakken", systemImage: "doc.on.clipboard") }
                Button { web.presentPrint() } label: { Label("Afdrukken of bewaren als PDF", systemImage: "printer") }
                Button { web.openCurrentInSafari() } label: { Label("Openen in Safari", systemImage: "safari") }
                Button { showScannerTest = true } label: { Label("Scanner-testmodus (zonder project)", systemImage: "viewfinder") }
            } label: { Image(systemName: "ellipsis.circle").font(.title3) }
            .accessibilityIdentifier("mjopMenu").accessibilityLabel("Meer opties voor MJOP Live")
        }
        .padding(.horizontal, 12).padding(.vertical, 6)
        .background(Color(.systemBackground))
        .overlay(alignment: .bottom) { Divider() }
    }
}

/// De losse scanner zonder projectcontext (LiDAR-/meetdiagnose en testen). Geen hoofdnavigatie: alleen bereikbaar via het menu.
struct ScannerTestView: View {
    let close: () -> Void
    @EnvironmentObject var store: ScanStore
    var body: some View {
        NavigationStack {
            StartScanView().environmentObject(store)
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Sluiten", action: close).accessibilityIdentifier("scannerTestClose") } }
        }
    }
}
