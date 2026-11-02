import Combine
import MJOPIntegration
import Network
import SwiftUI
import UIKit
import WebKit

struct SharedFile: Identifiable { let id = UUID(); let url: URL }

/// Ontvanger van de gevalideerde berichten van de website (de fotoronde-coördinator).
@MainActor protocol BridgeHandling: AnyObject {
    func handle(_ request: BridgeRequest) -> [[String: Any]]
}

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

    /// Native navigatie (app-versie 2). `pending` = nog geen antwoord van de website (klassieke weergave, zoals voorheen); `tabs` = de website kent de
    /// navigatiecommando's en de app toont zijn eigen tabbalk; `classic` = oudere website, klassieke weergave blijft.
    enum NavMode: Equatable { case pending, tabs, classic }
    @Published private(set) var navMode: NavMode = .pending
    /// Laatste status die de website meldde (alleen lezen).
    @Published private(set) var webStatus: WebStatus?
    @Published private(set) var webFeatures: [String] = []
    /// Hoe vaak de pagina volledig is geladen en hoe vaak de gedeelde WebView is verplaatst (diagnose; bewijst dat tabwissels niet herladen).
    @Published private(set) var loadCount = 0
    @Published private(set) var hostMoves = 0

    let webView: WKWebView
    let hostRegistry: WebHostRegistry
    weak var bridgeHandler: BridgeHandling?
    private var pendingCommands: [String: CheckedContinuation<WebCommandResult, Never>] = [:]
    private var commandSeq = 0
    private var readyFallback: Task<Void, Never>?
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
        hostRegistry = WebHostRegistry(webView: webView)
        super.init()
        hostRegistry.onMove = { [weak self] n in self?.hostMoves = n }
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
        if args.contains("-mjop-tabs-test-page") {       // alleen UI-tests: nagebootste website die de native navigatie kent (zie TabsTestPage.swift)
            webView.loadHTMLString(Self.tabsTestPageHTML, baseURL: MJOPConfig.siteURL)
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

    // MARK: native navigatie (app-versie 2)

    /// De website meldt zich. Kent hij de navigatiecommando's, dan toont de app zijn eigen tabbalk en bevestigt dat aan de website (die verbergt dan de zijne).
    /// Een oudere website meldt zich nooit: de app blijft dan in de klassieke weergave.
    private func handleWebReady(_ features: [String]) {
        webFeatures = features
        guard features.contains(NativeNav.webNavFeature) else { navMode = .classic; return }
        readyFallback?.cancel(); readyFallback = nil
        navMode = .tabs
        deliver(BridgeReply.nativeReady(lidar: DeviceCapabilities.hasLiDAR, appVersion: DeviceCapabilities.appVersion))
    }

    private func handleWebState(_ value: JSONValue) {
        if let s = WebStatus.parse(value) { webStatus = s }
    }

    private func resolveCommand(requestId: String, result: WebCommandResult) {
        guard let c = pendingCommands.removeValue(forKey: requestId) else { return }
        c.resume(returning: result)
    }

    /// Valt terug op de klassieke weergave als de website niet binnen enkele seconden na het laden meldt dat hij de navigatie kent.
    private func scheduleReadyFallback() {
        guard navMode == .pending, readyFallback == nil else { return }
        readyFallback = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(NativeNav.readyTimeout * 1_000_000_000))
            guard !Task.isCancelled, let self else { return }
            if self.navMode == .pending { self.navMode = .classic }
            self.readyFallback = nil
        }
    }

    /// Stuurt een gevalideerd commando naar de website en wacht op het antwoord. Alleen lezen/navigeren: de app schrijft nooit naar de planopslag.
    /// Altijd een resultaat, nooit een hangende aanroep: zonder antwoord volgt na `NativeNav.commandTimeout` een TIMEOUT-fout.
    func send(_ command: NativeCommand) async -> WebCommandResult {
        guard navMode == .tabs else {
            return .failure(command: command.name, code: "NOT_READY", message: "De website ondersteunt de nieuwe navigatie nog niet.")
        }
        guard command.isValid else {
            return .failure(command: command.name, code: "INVALID", message: "Dit commando is niet toegestaan.")
        }
        commandSeq += 1
        let rid = "a\(commandSeq)-\(String(UInt32.random(in: 0...UInt32.max), radix: 36))"
        return await withCheckedContinuation { (cont: CheckedContinuation<WebCommandResult, Never>) in
            pendingCommands[rid] = cont
            if !deliverChecked(command.message(requestId: rid)) {
                pendingCommands.removeValue(forKey: rid)
                cont.resume(returning: .failure(command: command.name, code: "NOT_DELIVERED", message: "De website is nog niet geladen."))
                return
            }
            let name = command.name
            Task { [weak self] in
                try? await Task.sleep(nanoseconds: UInt64(NativeNav.commandTimeout * 1_000_000_000))
                guard let self, let c = self.pendingCommands.removeValue(forKey: rid) else { return }
                c.resume(returning: .failure(command: name, code: "TIMEOUT", message: "De website reageerde niet op tijd."))
            }
        }
    }

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

    /// Handmatige terugkeer: de gebruiker plakt de inloglink of -code uit de e-mail/brugpagina.
    func pasteLogin(_ text: String) {
        switch AuthPaste.parse(text) {
        case .code(let c): handleAuthCallback(.code(c))
        case .openInWebView(let u): load(u); show("Inloggen wordt afgerond…")
        case .rejected: show("Dit is geen geldige inloglink of -code voor MJOP Live. Kopieer de link uit de e-mail of de code van de terugkeerpagina.")
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
    <p id="c">Teller: 0</p>
    <button onclick="post('startPhotoRound', {planRef:'plan-0123456789abcdef01234567', mjopPlanId:null, buildingLabel:'Testgebouw 1', bagPandId:null, mode:'round', element:null, plannedFacades:[{name:'Voorgevel',orientation:'S'}]})">Start fotoronde</button>
    <button onclick="post('startElementScan', {planRef:'plan-0123456789abcdef01234567', mjopPlanId:null, buildingLabel:'Testgebouw 1', bagPandId:null, mode:'element', element:{key:'kozijnen-onderhoud', name:'Onderhoud buitenkozijnen', unit:'st'}, plannedFacades:[]})">Scan voor element</button>
    <button onclick="post('startPhotoRound', {planRef:'x', buildingLabel:'', mode:'round'})">Start ongeldig</button>
    <button onclick="post('listProposals', {planRef:'plan-0123456789abcdef01234567'})">Vraag voorstellen</button>
    <p id="antwoord">Antwoord: geen</p>
    <script>var n=0, k=0;
    function post(a,p){ k++; window.webkit.messageHandlers.mjopNative.postMessage({v:1, action:a, requestId:'t'+k, payload:p}); }
    window.MJOPNativeBridge = { receive: function(m){ document.getElementById('antwoord').textContent = 'Antwoord: ' + m.type + ' voorstellen=' + (m.proposals ? m.proposals.length : '-') + ' fout=' + (m.message || '-'); } };
    </script></body></html>
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

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        isLoading = false; failure = nil
        loadCount += 1
        scheduleReadyFallback()
    }

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
    /// Eén smalle brug: alleen berichten van de hoofdpagina op het eigen domein, alleen bekende acties, volledig gevalideerd (versie, requestId, grootte, context).
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "mjopNative", message.frameInfo.isMainFrame,
              let url = message.frameInfo.request.url, policy.isAllowedInApp(url) else { return }
        switch BridgeMessage.parse(message.body) {
        case .success(.print):
            presentPrint()
        // Native navigatie (app-versie 2): wordt hier afgehandeld en bereikt de fotoronde-coördinator niet.
        case .success(.webReady(_, let features, _)):
            handleWebReady(features)
        case .success(.webReply(let rid, let result)):
            resolveCommand(requestId: rid, result: result)
        case .success(.webState(_, let state)):
            handleWebState(state)
        case .success(let request):
            guard let handler = bridgeHandler else { return }
            for reply in handler.handle(request) { deliver(reply) }
        case .failure(let e):
            show("Een bericht van de pagina is genegeerd omdat het niet klopte.")
            deliver(BridgeReply.error(requestId: nil, message: "Ongeldig bericht (\(String(describing: e).prefix(60)))."))
        }
    }

    /// Stuurt een antwoord naar de pagina, maar nooit naar een pagina buiten het eigen domein.
    func deliver(_ message: [String: Any]) { _ = deliverChecked(message) }

    /// Zoals `deliver`, maar meldt of het bericht ook echt is overgedragen (alleen als er een pagina van het eigen domein staat).
    func deliverChecked(_ message: [String: Any]) -> Bool {
        guard let url = webView.url, policy.isAllowedInApp(url), let js = BridgeReply.script(for: message) else { return false }
        webView.evaluateJavaScript(js, completionHandler: nil)
        return true
    }
}

/// WKUserContentController houdt de handler sterk vast; deze wrapper voorkomt een retain cycle met de controller.
private final class WeakScriptHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) { target?.userContentController(c, didReceive: m) }
}
