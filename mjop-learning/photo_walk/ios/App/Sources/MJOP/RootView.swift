import MJOPIntegration
import SwiftUI

private struct ScannerVisibleKey: EnvironmentKey { static let defaultValue = true }
extension EnvironmentValues {
    /// false zodra de gebruiker naar Mijn MJOP wisselt: de scanner blijft bestaan (positie en data behouden), maar de camera moet stoppen.
    var scannerVisible: Bool {
        get { self[ScannerVisibleKey.self] }
        set { self[ScannerVisibleKey.self] = newValue }
    }
}

/// Hoofdnavigatie: Mijn MJOP (website in WebView) en Gevelscanner (native Photo Walk). Beide blijven levend bij wisselen.
struct RootView: View {
    @EnvironmentObject var store: ScanStore
    @StateObject private var web = MJOPWebController()
    @State private var section: AppSection = AppSection.initial(arguments: CommandLine.arguments, stored: UserDefaults.standard.string(forKey: "mjop.section"))

    var body: some View {
        VStack(spacing: 0) {
            header
            ZStack {
                MJOPContainerView(web: web, openScanner: { section = .scanner })
                    .opacity(section == .mjop ? 1 : 0).allowsHitTesting(section == .mjop).accessibilityHidden(section != .mjop)
                NavigationStack { StartScanView().environmentObject(store) }
                    .environment(\.scannerVisible, section == .scanner)
                    .opacity(section == .scanner ? 1 : 0).allowsHitTesting(section == .scanner).accessibilityHidden(section != .scanner)
            }
        }
        .onChange(of: section) { UserDefaults.standard.set($0.rawValue, forKey: "mjop.section") }
        .onOpenURL { url in
            guard url.scheme?.lowercased() == MJOPConfig.appURLScheme else { return }
            section = .mjop
            web.handleAuthCallback(AuthCallback.parse(url))
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            Picker("Onderdeel", selection: $section) {
                ForEach(AppSection.allCases, id: \.self) { Text($0.title).tag($0) }
            }
            .pickerStyle(.segmented).accessibilityIdentifier("sectionPicker")
            if section == .mjop {
                Menu {
                    Button { web.retry() } label: { Label("Opnieuw laden", systemImage: "arrow.clockwise") }
                    if web.canGoBack { Button { web.goBack() } label: { Label("Terug", systemImage: "chevron.backward") } }
                    Button { web.loadHome() } label: { Label("Naar start", systemImage: "house") }
                    Button { web.presentPrint() } label: { Label("Afdrukken of bewaren als PDF", systemImage: "printer") }
                    Button { web.openCurrentInSafari() } label: { Label("Openen in Safari", systemImage: "safari") }
                } label: { Image(systemName: "ellipsis.circle").font(.title3) }
                .accessibilityIdentifier("mjopMenu").accessibilityLabel("Meer opties voor Mijn MJOP")
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(Color(.systemBackground))
        .overlay(alignment: .bottom) { Divider() }
    }
}
