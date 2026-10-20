import Combine
import MJOPIntegration
import Network
import SwiftUI
import UIKit
import WebKit

struct SharedFile: Identifiable { let id = UUID(); let url: URL }

/// Beheert de ENIGE WKWebView voor Mijn MJOP. De instantie leeft zolang de app draait, dus wisselen naar de scanner en terug verliest geen
/// navigatiepositie of niet-opgeslagen invoer. Dit is de enige plek in de app met netwerk-/WebKit-code; de scanner blijft offline.
@MainActor
final class MJOPWebController: NSObject, ObservableObject {
    @Published private(set) var failure: WebLoadFailure?
    @Published private(set) var isLoading = false
    @Published private(set) var progress: Double = 0
    @Published private(set) var canGoBack = false
    @Published private(set) var isOnline = true
    @Published var notice: String?
    @Published var sharedFile: SharedFile?

    let webView: WKWebView
    private let policy = WebNavigationPolicy.production
    private let monitor = NWPathMonitor()
    private var observers: [NSKeyValueObservation] = []
    private var downloadTargets: [ObjectIdentifier: URL] = [:]
    private var noticeTask: Task<Void, Never>?

    override init() {
        let conf = WKWebViewConfiguration()
        conf.websiteDataStore = .default()                    // persistent: Supabase-sessie (localStorage) blijft na herstart bewaard
        conf.applicationNameForUserAgent = MJOPConfig.userAgentSuffix
        conf.allowsInlineMediaPlayback = true
        // window.print() doet niets in WKWebView; deze shim geeft de aanvraag door aan de native afdrukdialoog (opslaan als PDF/delen).
        let shim = "window.print = function () { try { window.webkit.messageHandlers.mjopNative.postMessage({ action: 'print' }); } catch (e) {} };"
        conf.userContentController.addUserScript(WKUserScript(source: shim, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        webView = WKWebView(frame: .zero, configuration: conf)
        super.init()
        conf.userContentController.add(WeakScriptHandler(self), name: "mjopNative")
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.isOpaque = false
        webView.backgroundColor = .clear
        observers = [
            webView.observe(\.estimatedProgress, options: [.new]) { [weak self] w, _ in Task { @MainActor in self?.progress = w.estimatedProgress } },
            webView.observe(\.canGoBack, options: [.new]) { [weak self] w, _ in Task { @MainActor in self?.canGoBack = w.canGoBack } },
        ]
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor in
                guard let self else { return }
                let online = path.status == .satisfied
                let regained = online && !self.isOnline
                self.isOnline = online
                if regained, self.failure?.isOffline == true { self.retry() }
            }
        }
        monitor.start(queue: DispatchQueue(label: "mjop.netpath"))
        Self.cleanDownloadDirectory()
        startInitialLoad()
    }

    deinit { monitor.cancel() }

    // MARK: laden

    private func startInitialLoad() {
        #if DEBUG
        let args = CommandLine.arguments
        if args.contains("-mjop-test-page") {            // alleen UI-tests: lokale pagina met teller, geen netwerk
            webView.loadHTMLString(Self.testPageHTML, baseURL: MJOPConfig.siteURL)
            return
        }
        if let i = args.firstIndex(of: "-mjop-simulate-failure"), args.indices.contains(i + 1) {
            failure = args[i + 1] == "offline" ? WebLoadFailure.classify(domain: NSURLErrorDomain, code: NSURLErrorNotConnectedToInternet)
                                                : WebLoadFailure.http(status: 503)
            return
        }
        #endif
        loadHome()
    }

    func loadHome() { load(MJOPConfig.siteURL) }

    func load(_ url: URL) {
        guard policy.isAllowedInApp(url) else { return }
        failure = nil
        webView.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
    }

    func retry() {
        failure = nil
        if webView.url == nil || webView.url?.absoluteString == "about:blank" { loadHome() } else { webView.reload() }
    }

    func goBack() { if webView.canGoBack { webView.goBack() } }

    func openCurrentInSafari() {
        let url = webView.url.flatMap { policy.isAllowedInApp($0) ? $0 : nil } ?? MJOPConfig.siteURL
        UIApplication.shared.open(url)
    }

    // MARK: inloggen (magic link)

    func handleAuthCallback(_ result: AuthCallback) {
        switch result {
        case .code(let code):
            if let url = AuthCallback.webURL(for: code) { load(url); show("Inloggen wordt afgerond…") }
        case .failure(let message):
            show("Inloggen via de link is niet gelukt: \(message)")
        case .rejected:
            show("Deze inloglink is ongeldig of niet bedoeld voor de app.")
        }
    }

    // MARK: afdrukken / PDF

    func presentPrint() {
        let info = UIPrintInfo(dictionary: nil)
        info.outputType = .general; info.jobName = "MJOP"
        let pic = UIPrintInteractionController.shared
        pic.printInfo = info
        pic.printFormatter = webView.viewPrintFormatter()
        pic.present(animated: true, completionHandler: nil)
    }

    // MARK: meldingen

    func show(_ text: String) {
        notice = text
        noticeTask?.cancel()
        noticeTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 6_000_000_000)
            if !Task.isCancelled { self?.notice = nil }
        }
    }

    // MARK: downloads

    private static var downloadRoot: URL { FileManager.default.temporaryDirectory.appendingPathComponent("mjop-downloads", isDirectory: true) }
    private static func cleanDownloadDirectory() { try? FileManager.default.removeItem(at: downloadRoot) }

    #if DEBUG
    private static let testPageHTML = """
    <!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body>
    <h1>MJOP testpagina</h1><button onclick="n++;document.getElementById('c').textContent='Teller: '+n">Teller verhogen</button>
    <p id="c">Teller: 0</p><script>var n=0</script></body></html>
    """
    #endif

    fileprivate static func topViewController() -> UIViewController? {
        let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first { $0.activationState == .foregroundActive }
        var vc = scene?.windows.first { $0.isKeyWindow }?.rootViewController
        while let p = vc?.presentedViewController { vc = p }
        return vc
    }
}

// MARK: - WKNavigationDelegate

extension MJOPWebController: WKNavigationDelegate {
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let main = navigationAction.targetFrame?.isMainFrame ?? true
        let tapped = navigationAction.navigationType == .linkActivated
        switch policy.decide(navigationAction.request.url, isMainFrame: main, userInitiated: tapped) {
        case .allowInApp:
            decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
        case .openExternally(let url):
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
        case .block(let reason):
            if main { show(WebLoadFailure.blocked(reason: reason).message) }
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        let http = navigationResponse.response as? HTTPURLResponse
        let attachment = (http?.value(forHTTPHeaderField: "Content-Disposition") ?? "").lowercased().hasPrefix("attachment")
        if navigationResponse.canShowMIMEType == false || attachment { decisionHandler(.download); return }
        if navigationResponse.isForMainFrame, let status = http?.statusCode, let f = WebLoadFailure.http(status: status) {
            failure = f; isLoading = false
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { isLoading = true }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { isLoading = false; failure = nil }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { handle(error) }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { handle(error) }

    private func handle(_ error: Error) {
        isLoading = false
        let ns = error as NSError
        // WebKit-fout 102 = navigatie onderbroken door een download/geannuleerd door beleid: geen foutscherm
        if ns.domain == "WebKitErrorDomain", ns.code == 102 || ns.code == 101 { return }
        if let f = WebLoadFailure.classify(domain: ns.domain, code: ns.code) { failure = f }
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        show("Mijn MJOP is opnieuw geladen omdat het geheugen vol was. Controleer of je laatste wijzigingen er nog staan.")
        webView.reload()
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
}

// MARK: - WKUIDelegate (nieuwe vensters, JavaScript-dialogen)

extension MJOPWebController: WKUIDelegate {
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        // target=_blank / window.open: nooit een tweede WebView; binnen het toegestane domein in dezelfde weergave, anders Safari.
        let tapped = navigationAction.navigationType == .linkActivated
        switch policy.decide(navigationAction.request.url, isMainFrame: true, userInitiated: tapped) {
        case .allowInApp: if let u = navigationAction.request.url { load(u) }
        case .openExternally(let u): UIApplication.shared.open(u)
        case .block(let reason): show(WebLoadFailure.blocked(reason: reason).message)
        }
        return nil
    }

    private func present(_ title: String?, _ message: String, actions: [UIAlertAction], field: ((UITextField) -> Void)? = nil) -> Bool {
        guard let vc = Self.topViewController() else { return false }
        let a = UIAlertController(title: title, message: message, preferredStyle: .alert)
        if let field { a.addTextField(configurationHandler: field) }
        actions.forEach(a.addAction)
        vc.present(a, animated: true)
        return true
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let ok = UIAlertAction(title: "OK", style: .default) { _ in completionHandler() }
        if !present(nil, message, actions: [ok]) { completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let ok = UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) }
        let cancel = UIAlertAction(title: "Annuleren", style: .cancel) { _ in completionHandler(false) }
        if !present(nil, message, actions: [cancel, ok]) { completionHandler(false) }
    }

    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        var tf: UITextField?
        let ok = UIAlertAction(title: "OK", style: .default) { _ in completionHandler(tf?.text) }
        let cancel = UIAlertAction(title: "Annuleren", style: .cancel) { _ in completionHandler(nil) }
        if !present(nil, prompt, actions: [cancel, ok], field: { tf = $0; $0.text = defaultText }) { completionHandler(nil) }
    }
}

// MARK: - Downloads (CSV, JSON, PDF) -> deelblad / Bestanden

extension MJOPWebController: WKDownloadDelegate {
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let dir = Self.downloadRoot.appendingPathComponent(UUID().uuidString, isDirectory: true)
        do { try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true) } catch { completionHandler(nil); show("Het bestand kon niet worden bewaard."); return }
        let name = DownloadNaming.safeFileName(suggested: suggestedFilename, mimeType: response.mimeType)
        let dest = dir.appendingPathComponent(name)
        downloadTargets[ObjectIdentifier(download)] = dest
        completionHandler(dest)
    }

    func downloadDidFinish(_ download: WKDownload) {
        guard let url = downloadTargets.removeValue(forKey: ObjectIdentifier(download)) else { return }
        sharedFile = SharedFile(url: url)
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        downloadTargets.removeValue(forKey: ObjectIdentifier(download))
        show("Downloaden is mislukt. Probeer het opnieuw.")
    }
}

// MARK: - Berichten van de pagina (alleen 'print', alleen van de eigen site)

extension MJOPWebController: WKScriptMessageHandler {
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "mjopNative", message.frameInfo.isMainFrame,
              let url = message.frameInfo.request.url, policy.isAllowedInApp(url),
              let body = message.body as? [String: Any], body["action"] as? String == "print" else { return }
        presentPrint()
    }
}

/// WKUserContentController houdt de handler sterk vast; deze wrapper voorkomt een retain cycle met de controller.
private final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { target?.userContentController(c, didReceive: m) }
}
