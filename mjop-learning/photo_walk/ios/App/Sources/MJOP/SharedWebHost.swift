import SwiftUI
import UIKit
import WebKit

/// Eén gedeelde `WKWebView` voor alle websiteonderdelen van de app. Een WebView kan maar op één plek in de schermhiërarchie hangen; dit bestand
/// zorgt dat hij steeds aan de zichtbare tab hangt, zonder nieuwe WebView, zonder herladen en dus zonder verlies van sessie, `sessionStorage` of paginastaat.
///
/// Werking: elke plek waar de website getoond kan worden is een `WebContainerView`. Zodra zo'n container in een venster komt (zichtbaar wordt) meldt hij
/// zich aan bij het register; verdwijnt hij uit het venster, dan meldt hij zich af. Het register hangt de WebView aan de laatst aangemelde zichtbare
/// container. Is er geen enkele zichtbaar (bijvoorbeeld op de tab Home), dan hangt hij aan een onzichtbare "parkeerplek" van 1×1 punt, zodat de website
/// blijft draaien (nodig voor het starten van een meting vanuit Meten en voor statusmeldingen).
final class WebContainerView: UIView {
    let isParking: Bool
    weak var registry: WebHostRegistry?

    init(parking: Bool) {
        isParking = parking
        super.init(frame: .zero)
        backgroundColor = .clear
        clipsToBounds = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) is niet beschikbaar") }

    override func didMoveToWindow() {
        super.didMoveToWindow()
        if window != nil { registry?.activate(self) } else { registry?.deactivate(self) }
    }

    func attach(_ web: UIView) {
        web.translatesAutoresizingMaskIntoConstraints = false
        addSubview(web)
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: leadingAnchor), web.trailingAnchor.constraint(equalTo: trailingAnchor),
            web.topAnchor.constraint(equalTo: topAnchor), web.bottomAnchor.constraint(equalTo: bottomAnchor),
        ])
    }
}

@MainActor
final class WebHostRegistry {
    let webView: WKWebView
    /// Zichtbare containers in volgorde van aanmelden; de laatste niet-parkeerplek wint.
    private var visible: [WebContainerView] = []
    /// Hoe vaak de WebView naar een andere plek is verplaatst (diagnose; de WebView zelf is altijd dezelfde instantie).
    private(set) var moveCount = 0
    var onMove: ((Int) -> Void)?

    init(webView: WKWebView) { self.webView = webView }

    func activate(_ c: WebContainerView) {
        visible.removeAll { $0 === c }
        visible.append(c)
        reconcile()
    }

    func deactivate(_ c: WebContainerView) {
        visible.removeAll { $0 === c }
        reconcile()
    }

    /// De container waar de WebView nu hoort te hangen, of nil als niets zichtbaar is (dan blijft hij waar hij is, zoals bij een schermvullende scanner).
    var target: WebContainerView? {
        visible.last(where: { !$0.isParking }) ?? visible.last(where: { $0.isParking })
    }

    private func reconcile() {
        guard let target else { return }
        guard webView.superview !== target else { return }
        webView.removeFromSuperview()
        target.attach(webView)
        moveCount += 1
        onMove?(moveCount)
    }
}

/// SwiftUI-plek voor de gedeelde WebView. `parking: true` is de onzichtbare standplaats die de WebView levend houdt als geen tab hem toont.
struct SharedWebHost: UIViewRepresentable {
    let registry: WebHostRegistry
    var parking = false

    func makeUIView(context: Context) -> WebContainerView {
        let v = WebContainerView(parking: parking)
        v.registry = registry
        return v
    }

    func updateUIView(_ uiView: WebContainerView, context: Context) {}
}
