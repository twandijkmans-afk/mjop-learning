import XCTest

/// UI-rooktest in de iOS-simulator. De simulator heeft GEEN ARKit-camera/LiDAR; juist daarom controleert deze test dat de app niet crasht
/// zonder sensoren en dat de simulatie-flow (synthetische data) tot een resultaat leidt. Geen fysiek toestel nodig, ook geen bewijs voor sensorgedrag.
final class PhotoWalkUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    private func label(_ app: XCUIApplication, containing s: String) -> XCUIElement {
        app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", s)).firstMatch
    }

    func testStartScreenAndSimulationFlow() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
        XCTAssertFalse(app.buttons["Nieuwe scan starten"].isEnabled, "zonder gebouw-/gevel-ID mag geen scan starten")
        app.buttons["Testscan met synthetische data (simulatie)"].tap()
        XCTAssertTrue(label(app, containing: "SIMULATIE").waitForExistence(timeout: 15))
        XCTAssertTrue(label(app, containing: "1.2").exists)
        app.buttons["Resultaten openen"].tap()
        XCTAssertTrue(label(app, containing: "PROV-").waitForExistence(timeout: 15))
        XCTAssertTrue(label(app, containing: "m2").exists)
        XCTAssertTrue(label(app, containing: "NIET gevalideerd").exists, "onzekerheid moet als niet-gevalideerd worden getoond")
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testScanWithoutArKitDoesNotCrashAndGivesNoMeasurement() {
        let app = XCUIApplication()
        app.launchArguments += ["-uitest-prefill"]
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
        let start = app.buttons["Nieuwe scan starten"]
        XCTAssertTrue(start.waitForExistence(timeout: 10))
        XCTAssertTrue(start.isEnabled)
        start.tap()
        XCTAssertTrue(label(app, containing: "niet ondersteund").waitForExistence(timeout: 15), "zonder ARKit moet de app dit melden")
        app.buttons["Keyframe"].tap()                       // geen frame beschikbaar: mag niet crashen
        XCTAssertEqual(app.state, .runningForeground)
        app.buttons["Resultaten"].tap()
        XCTAssertTrue(app.navigationBars["Resultaten"].waitForExistence(timeout: 10))
        XCTAssertFalse(label(app, containing: "m2  [").exists, "zonder keyframes mag er geen maat zijn")
        XCTAssertEqual(app.state, .runningForeground)
    }
}
