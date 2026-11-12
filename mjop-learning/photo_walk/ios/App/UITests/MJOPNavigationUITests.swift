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

    func testInvalidBridgeMessageIsRefusedWithoutOpeningTheScanner() {
        let app = launch()
        XCTAssertTrue(app.webViews.buttons["Start ongeldig"].waitForExistence(timeout: 15), "testpagina nog niet geladen: Start ongeldig")   // wacht tot de WebView-knop in de toegankelijkheidsboom staat
        app.webViews.buttons["Start ongeldig"].tap()
        XCTAssertTrue(element(app, containing: "genegeerd").waitForExistence(timeout: 10), "de gebruiker ziet dat het bericht is geweigerd")
        XCTAssertFalse(app.navigationBars["Fotoronde"].exists)
    }

    func testListProposalsAnswersForTheRightProjectOnly() {
        let app = launch()
        XCTAssertTrue(app.webViews.buttons["Vraag voorstellen"].waitForExistence(timeout: 15), "testpagina nog niet geladen: Vraag voorstellen")   // wacht tot de WebView-knop in de toegankelijkheidsboom staat
        app.webViews.buttons["Vraag voorstellen"].tap()
        XCTAssertTrue(app.webViews.staticTexts["Antwoord: proposals voorstellen=0 fout=-"].waitForExistence(timeout: 10), "lege lijst voor een project zonder afgeronde ronde")
    }

    /// Gevelscanner 2.0: de website kan de gevelinventaris opvragen via de echte brug; zonder afgeronde ronde is dat een lege lijst voor dít project.
    func testFacadeInventoryIsAnsweredOverTheBridge() {
        let app = launch()
        XCTAssertTrue(app.webViews.buttons["Vraag gevelinventaris"].waitForExistence(timeout: 15), "testpagina nog niet geladen: Vraag gevelinventaris")
        app.webViews.buttons["Vraag gevelinventaris"].tap()
        XCTAssertTrue(app.webViews.staticTexts["Inventaris: 0 voor plan-0123456789abcdef01234567"].waitForExistence(timeout: 10), "lege inventaris voor een project zonder afgeronde ronde")
    }

    func testOfflineErrorScreenOffersRetryAndNoLongerTheOldScanner() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-simulate-failure", "offline"]
        app.launch()
        XCTAssertTrue(app.staticTexts["mjopErrorTitle"].waitForExistence(timeout: 30))
        XCTAssertEqual(app.staticTexts["mjopErrorTitle"].label, "Je bent offline")
        XCTAssertTrue(app.buttons["mjopRetry"].exists)
        XCTAssertFalse(app.buttons["mjopToScanner"].exists, "de oude camera-scanner is uit de app")
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

}
