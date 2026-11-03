import MJOPIntegration
import SwiftUI
import WebKit

struct WebViewHost: UIViewRepresentable {
    let webView: WKWebView
    func makeUIView(context: Context) -> WKWebView { webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}

struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: [url], applicationActivities: nil) }
    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

/// Mijn MJOP: de bestaande mobiele website in de app, met laadindicator, offline-melding, foutscherm en deelblad voor downloads.
struct MJOPContainerView: View {
    @ObservedObject var web: MJOPWebController
    var openScanner: () -> Void

    var body: some View {
        ZStack(alignment: .top) {
            WebViewHost(webView: web.webView)
                .accessibilityIdentifier("mjopWebView")
            if web.isLoading {
                ProgressView(value: web.progress).progressViewStyle(.linear).accessibilityIdentifier("mjopLoading")
            }
            VStack(spacing: 6) {
                if !web.isOnline && web.failure == nil {
                    banner("Je bent offline. Wijzigingen in Mijn MJOP worden pas opgeslagen als er weer internet is.", system: "wifi.slash", id: "mjopOfflineBanner")
                }
                Spacer()
                if let n = web.notice { banner(n, system: "info.circle", id: "mjopNotice").onTapGesture { web.notice = nil } }
            }.padding(8)
            if let f = web.failure {
                MJOPErrorView(failure: f, retry: web.retry, openScanner: openScanner)
            }
        }
        .sheet(item: $web.sharedFile) { f in ShareSheet(url: f.url) }
    }

    private func banner(_ text: String, system: String, id: String) -> some View {
        Label(text, systemImage: system).font(.footnote).padding(10).frame(maxWidth: .infinity, alignment: .leading)
            .background(.regularMaterial).cornerRadius(10).accessibilityIdentifier(id)
    }
}

struct MJOPErrorView: View {
    let failure: WebLoadFailure
    let retry: () -> Void
    let openScanner: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Image(systemName: failure.isOffline ? "wifi.slash" : "exclamationmark.triangle").font(.system(size: 44)).foregroundStyle(.secondary)
            Text(failure.title).font(.title3.bold()).accessibilityIdentifier("mjopErrorTitle")
            Text(failure.message).multilineTextAlignment(.center).foregroundStyle(.secondary).accessibilityIdentifier("mjopErrorMessage")
            if failure.canRetry { Button("Opnieuw proberen", action: retry).buttonStyle(.borderedProminent).accessibilityIdentifier("mjopRetry") }
            if failure.isOffline { Button("Losse scanner openen (werkt ook offline)", action: openScanner).buttonStyle(.bordered).accessibilityIdentifier("mjopToScanner") }
        }
        .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}
