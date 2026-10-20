import XCTest

/// UI-tests voor de hoofdnavigatie Mijn MJOP <-> Gevelscanner en de foutafhandeling van de webweergave.
/// Geen netwerk: de WebView laadt een lokale testpagina (`-mjop-test-page`, alleen in Debug-builds) of toont een gesimuleerde fout.
/// Bewijst NIET: echt inloggen, bestandsimport, PDF-export of synchronisatie op een fysieke iPhone (zie docs/mjop_integration.md).
final class MJOPNavigationUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    private func segment(_ app: XCUIApplication, _ title: String) -> XCUIElement { app.segmentedControls["sectionPicker"].buttons[title] }

    func testStartsOnMijnMJOPAndShowsBothSections() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-test-page", "-section", "mjop"]
        app.launch()
        XCTAssertTrue(app.segmentedControls["sectionPicker"].waitForExistence(timeout: 30))
        XCTAssertTrue(segment(app, "Mijn MJOP").exists)
        XCTAssertTrue(segment(app, "Gevelscanner").exists)
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 30), "Mijn MJOP toont de webweergave")
        XCTAssertTrue(app.buttons["mjopMenu"].exists)
    }

    func testSwitchingKeepsWebStateAndScannerPosition() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-test-page", "-section", "mjop", "-uitest-prefill"]
        app.launch()
        let tellerKnop = app.webViews.buttons["Teller verhogen"]
        XCTAssertTrue(tellerKnop.waitForExistence(timeout: 30))
        tellerKnop.tap(); tellerKnop.tap()
        XCTAssertTrue(app.webViews.staticTexts["Teller: 2"].waitForExistence(timeout: 10))

        // naar de scanner: native Photo Walk-scherm, en daar een stap dieper (simulatie) om de navigatiepositie te testen
        segment(app, "Gevelscanner").tap()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 15))
        let sim = app.buttons["Testscan met synthetische data (simulatie)"]
        var n = 0; while !(sim.exists && sim.isHittable) && n < 8 { app.swipeUp(); n += 1 }
        sim.tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "SIMULATIE")).firstMatch.waitForExistence(timeout: 15))

        // terug naar Mijn MJOP: niet-opgeslagen webstaat (teller) is behouden, geen herlaad
        segment(app, "Mijn MJOP").tap()
        XCTAssertTrue(app.webViews.staticTexts["Teller: 2"].waitForExistence(timeout: 10), "webstaat moet behouden blijven bij wisselen")

        // en weer naar de scanner: nog steeds op het diepere scherm
        segment(app, "Gevelscanner").tap()
        XCTAssertTrue(app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "SIMULATIE")).firstMatch.waitForExistence(timeout: 10), "scannerpositie moet behouden blijven")
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testOfflineErrorScreenOffersRetryAndScanner() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-simulate-failure", "offline", "-section", "mjop", "-uitest-prefill"]
        app.launch()
        XCTAssertTrue(app.staticTexts["mjopErrorTitle"].waitForExistence(timeout: 30))
        XCTAssertEqual(app.staticTexts["mjopErrorTitle"].label, "Je bent offline")
        XCTAssertTrue(app.buttons["mjopRetry"].exists)
        app.buttons["mjopToScanner"].tap()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 15), "offline blijft de scanner bereikbaar")
    }

    func testServerErrorScreenHasNoScannerShortcutButCanRetry() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-simulate-failure", "http", "-section", "mjop"]
        app.launch()
        XCTAssertTrue(app.staticTexts["mjopErrorTitle"].waitForExistence(timeout: 30))
        XCTAssertEqual(app.staticTexts["mjopErrorTitle"].label, "Pagina niet beschikbaar")
        XCTAssertTrue(app.buttons["mjopRetry"].exists)
        XCTAssertFalse(app.buttons["mjopToScanner"].exists)
    }

    func testScannerCanBeTheStartSection() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-test-page", "-section", "scanner"]
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
    }
}
