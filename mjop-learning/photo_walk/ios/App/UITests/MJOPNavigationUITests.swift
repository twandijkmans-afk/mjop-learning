import XCTest

/// UI-tests voor de geïntegreerde MJOP Live-interface in de iOS-simulator.
/// Geen netwerk: de WebView laadt een lokale testpagina (`-mjop-test-page`, alleen in Debug-builds) die via de ECHTE brug (`webkit.messageHandlers.mjopNative`)
/// berichten naar de app stuurt. Bewijst NIET: echt inloggen, camera/LiDAR, bestandsimport, PDF-export of synchronisatie op een fysieke iPhone.
final class MJOPNavigationUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

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
        XCTAssertTrue(app.staticTexts["Testgebouw 1"].waitForExistence(timeout: 5), "projectcontext (gebouw) is meegekomen")
        XCTAssertTrue(app.staticTexts["Voorgevel"].exists, "geplande gevel uit de website is voorgesteld")
        XCTAssertFalse(app.buttons["roundFinish"].isEnabled, "zonder foto's valt er niets af te ronden")

        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(app.webViews.staticTexts["Teller: 2"].waitForExistence(timeout: 10), "terug in Mijn MJOP: webstaat behouden, geen herlaad")
        XCTAssertFalse(app.navigationBars["Fotoronde"].exists)
    }

    func testElementScanCarriesTheElementContext() {
        let app = launch()
        app.webViews.buttons["Scan voor element"].tap()
        XCTAssertTrue(app.navigationBars["Fotoronde"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.staticTexts["Onderhoud buitenkozijnen"].waitForExistence(timeout: 5), "gekozen onderhoudspost is zichtbaar in de scanner")
        XCTAssertTrue(app.staticTexts["stuks"].exists, "meeteenheid van de post")
        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 10))
    }

    func testInvalidBridgeMessageIsRefusedWithoutOpeningTheScanner() {
        let app = launch()
        app.webViews.buttons["Start ongeldig"].tap()
        XCTAssertTrue(app.otherElements["mjopNotice"].waitForExistence(timeout: 10) || app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", "genegeerd")).firstMatch.waitForExistence(timeout: 10))
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
        app.buttons["roundReview"].tap()
        XCTAssertTrue(app.navigationBars["Overzicht en controle"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Nog geen foto's."].exists)
        app.navigationBars.buttons.element(boundBy: 0).tap()
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
        app.buttons["mjopMenu"].tap()
        app.buttons["Scanner-testmodus (zonder project)"].tap()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 15))
        app.buttons["scannerTestClose"].tap()
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 10))
    }
}
