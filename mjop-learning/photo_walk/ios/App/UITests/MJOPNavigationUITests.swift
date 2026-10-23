import XCTest

/// UI-tests voor de geïntegreerde MJOP Live-interface in de iOS-simulator.
/// Geen netwerk: de WebView laadt een lokale testpagina (`-mjop-test-page`, alleen in Debug-builds) die via de ECHTE brug (`webkit.messageHandlers.mjopNative`)
/// berichten naar de app stuurt. Bewijst NIET: echt inloggen, camera/LiDAR, bestandsimport, PDF-export of synchronisatie op een fysieke iPhone.
final class MJOPNavigationUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    /// SwiftUI voegt labels/waarden soms samen tot één element (LabeledContent, tikbare banners): zoek daarom op een deel van het label, in elk elementtype.
    private func element(_ app: XCUIApplication, containing text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@ OR value CONTAINS %@", text, text)).firstMatch
    }

    /// Tikt via de coördinaat van het midden: omzeilt de "scroll to visible"-accessibility-actie die in de simulator voor elementen in een niet-scrollende kop kan mislukken.
    private func tapCenter(_ el: XCUIElement) {
        XCTAssertTrue(el.waitForExistence(timeout: 10), "element niet gevonden: \(el)")
        el.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
    }

    /// Scrolt zo nodig omhoog tot het element bestaat (lijsten bouwen alleen zichtbare rijen op).
    private func reveal(_ el: XCUIElement, in app: XCUIApplication) {
        var n = 0
        while !el.exists && n < 5 { app.swipeUp(); n += 1 }
    }

    private func launch(_ extra: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-test-page"] + extra
        app.launch()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 30), "Mijn MJOP toont de webweergave")
        return app
    }

    func testThereIsNoLongerASectionSwitcher_ButAMenu() {
        let app = launch()
        XCTAssertFalse(app.segmentedControls["sectionPicker"].exists, "geen aparte Mijn MJOP/Gevelscanner-schakelaar meer")
        XCTAssertFalse(app.buttons["Gevelscanner"].exists)
        XCTAssertTrue(app.buttons["mjopMenu"].exists)
    }

    func testRoundStartsFromTheWebBridgeAndReturnsToTheSameWebState() {
        let app = launch()
        let teller = app.webViews.buttons["Teller verhogen"]
        XCTAssertTrue(teller.waitForExistence(timeout: 30))
        teller.tap(); teller.tap()
        XCTAssertTrue(app.webViews.staticTexts["Teller: 2"].waitForExistence(timeout: 10))

        app.webViews.buttons["Start fotoronde"].tap()
        XCTAssertTrue(app.navigationBars["Fotoronde"].waitForExistence(timeout: 15), "de website kan de fotoronde starten via de brug")
        XCTAssertTrue(element(app, containing: "Testgebouw 1").waitForExistence(timeout: 5), "projectcontext (gebouw) is meegekomen")
        XCTAssertTrue(element(app, containing: "Voorgevel").waitForExistence(timeout: 5), "geplande gevel uit de website is voorgesteld")
        XCTAssertTrue(element(app, containing: "Zorg dat het hele kozijn in beeld staat").exists, "korte instructie in gewone taal")
        XCTAssertTrue(app.buttons["roundShoot-Voorgevel"].exists, "één duidelijke knop om foto's te maken")
        reveal(app.buttons["roundFinish"], in: app)
        XCTAssertFalse(app.buttons["roundFinish"].isEnabled, "zonder foto's valt er niets af te ronden")

        reveal(app.buttons["roundSuspend"], in: app)
        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(app.webViews.staticTexts["Teller: 2"].waitForExistence(timeout: 10), "terug in Mijn MJOP: webstaat behouden, geen herlaad")
        XCTAssertFalse(app.navigationBars["Fotoronde"].exists)
    }

    func testElementScanCarriesTheElementContext() {
        let app = launch()
        app.webViews.buttons["Scan voor element"].tap()
        XCTAssertTrue(app.navigationBars["Fotoronde"].waitForExistence(timeout: 15))
        XCTAssertTrue(element(app, containing: "Onderhoud buitenkozijnen").waitForExistence(timeout: 5), "gekozen onderhoudspost is zichtbaar in de scanner")
        XCTAssertTrue(element(app, containing: "stuks").exists, "meeteenheid van de post")
        reveal(app.buttons["roundSuspend"], in: app)
        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 10))
    }

    func testInvalidBridgeMessageIsRefusedWithoutOpeningTheScanner() {
        let app = launch()
        app.webViews.buttons["Start ongeldig"].tap()
        XCTAssertTrue(element(app, containing: "genegeerd").waitForExistence(timeout: 10), "de gebruiker ziet dat het bericht is geweigerd")
        XCTAssertFalse(app.navigationBars["Fotoronde"].exists)
    }

    func testListProposalsAnswersForTheRightProjectOnly() {
        let app = launch()
        app.webViews.buttons["Vraag voorstellen"].tap()
        XCTAssertTrue(app.webViews.staticTexts["Antwoord: proposals voorstellen=0 fout=-"].waitForExistence(timeout: 10), "lege lijst voor een project zonder afgeronde ronde")
    }

    func testReviewScreenWithoutPhotosIsUsable() {
        let app = launch()
        app.webViews.buttons["Start fotoronde"].tap()
        XCTAssertTrue(app.navigationBars["Fotoronde"].waitForExistence(timeout: 15))
        tapCenter(app.buttons["roundReview"])
        XCTAssertTrue(app.navigationBars["Overzicht en controle"].waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, containing: "Nog geen foto").waitForExistence(timeout: 10))
        app.navigationBars.buttons.element(boundBy: 0).tap()
        reveal(app.buttons["roundSuspend"], in: app)
        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 10))
    }

    func testOfflineErrorScreenOffersRetryAndTheLooseScanner() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-simulate-failure", "offline"]
        app.launch()
        XCTAssertTrue(app.staticTexts["mjopErrorTitle"].waitForExistence(timeout: 30))
        XCTAssertEqual(app.staticTexts["mjopErrorTitle"].label, "Je bent offline")
        XCTAssertTrue(app.buttons["mjopRetry"].exists)
        app.buttons["mjopToScanner"].tap()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 15), "de losse scanner blijft bereikbaar zonder internet")
    }

    func testServerErrorScreenHasNoScannerShortcutButCanRetry() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-simulate-failure", "http"]
        app.launch()
        XCTAssertTrue(app.staticTexts["mjopErrorTitle"].waitForExistence(timeout: 30))
        XCTAssertEqual(app.staticTexts["mjopErrorTitle"].label, "Pagina niet beschikbaar")
        XCTAssertTrue(app.buttons["mjopRetry"].exists)
        XCTAssertFalse(app.buttons["mjopToScanner"].exists)
    }

    func testScannerTestModeIsReachableFromTheMenu() {
        let app = launch()
        tapCenter(app.buttons["mjopMenu"])
        tapCenter(app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Scanner-testmodus")).firstMatch)
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 15))
        app.buttons["scannerTestClose"].tap()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 10))
    }
}
