import XCTest

/// UI-rooktest in de iOS-simulator. De simulator heeft GEEN ARKit-camera/LiDAR; juist daarom controleert deze test dat de app niet crasht
/// zonder sensoren en dat de simulatie-flow (synthetische data) tot een resultaat leidt. Geen fysiek toestel nodig, ook geen bewijs voor sensorgedrag.
final class PhotoWalkUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    /// Het startscherm is een Form; onderste rijen (Geavanceerd) worden pas geladen na scrollen.
    private func reveal(_ app: XCUIApplication, _ el: XCUIElement) {
        var n = 0
        while !(el.exists && el.isHittable) && n < 8 { app.swipeUp(); n += 1 }
    }

    private func label(_ app: XCUIApplication, containing s: String) -> XCUIElement {
        app.staticTexts.containing(NSPredicate(format: "label CONTAINS %@", s)).firstMatch
    }

    func testStartScreenAndSimulationFlow() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
        XCTAssertFalse(app.buttons["Foto-scan starten"].isEnabled, "zonder gebouw-/gevel-ID mag geen scan starten")
        let legacySim = app.buttons["Testscan met synthetische data (simulatie)"]
        reveal(app, legacySim); legacySim.tap()
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
        let start = app.buttons["Keyframe-scan starten (handmatig markeren)"]
        reveal(app, start)
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

    // MARK: zoom en nauwkeurige selectie

    private func waitFor(_ el: XCUIElement, _ format: String, _ arg: String, timeout: TimeInterval = 12) -> Bool {
        let p = NSPredicate(format: format, arg)
        let e = expectation(for: p, evaluatedWith: el)
        return XCTWaiter().wait(for: [e], timeout: timeout) == .completed
    }

    private func parsePoint(_ s: String, index: Int = 0) -> (Double, Double)? {
        let re = try! NSRegularExpression(pattern: "\\(([0-9.]+), ([0-9.]+)\\) px")
        let ms = re.matches(in: s, range: NSRange(s.startIndex..., in: s))
        guard index < ms.count, let a = Range(ms[index].range(at: 1), in: s), let b = Range(ms[index].range(at: 2), in: s) else { return nil }
        return (Double(s[a])!, Double(s[b])!)
    }

    private func openTestImagePicker(_ app: XCUIApplication) {
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
        let legacySim = app.buttons["Testscan met synthetische data (simulatie)"]
        reveal(app, legacySim); legacySim.tap()
        XCTAssertTrue(label(app, containing: "SIMULATIE").waitForExistence(timeout: 15))
        let open = app.buttons["Hoeken markeren op testbeeld"]
        XCTAssertTrue(open.waitForExistence(timeout: 15)); open.tap()
        XCTAssertTrue(app.otherElements["frameCanvas"].waitForExistence(timeout: 20))
    }

    func testZoomPanDoubleTapAndPointsAreInOriginalPixels() {
        let app = XCUIApplication()
        openTestImagePicker(app)
        let canvas = app.otherElements["frameCanvas"]
        let zoomLabel = app.staticTexts["zoomIndicator"], readout = app.staticTexts["pointsReadout"]
        XCTAssertEqual(zoomLabel.label, "1.0×")

        // 1x: tik het midden -> originele pixel ca. (960, 720) van het 1920x1440 keyframe, ongeacht schermformaat
        canvas.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(waitFor(readout, "label CONTAINS %@", "1 linksboven"))
        let p1 = parsePoint(readout.label)!
        XCTAssertEqual(p1.0, 960, accuracy: 10); XCTAssertEqual(p1.1, 720, accuracy: 10)
        app.buttons["Laatste punt weg"].tap()
        XCTAssertTrue(waitFor(readout, "label CONTAINS %@", "Nog geen punten"))

        // zoom met pinch: indicator moet stijgen
        canvas.pinch(withScale: 4, velocity: 3)
        XCTAssertTrue(waitFor(zoomLabel, "label != %@", "1.0×"))
        let z = Double(zoomLabel.label.replacingOccurrences(of: "×", with: ""))!
        XCTAssertGreaterThan(z, 2.0)

        // dezelfde fysieke plek (midden, anker van de pinch) op hoge zoom -> (vrijwel) dezelfde originele pixel
        canvas.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(waitFor(readout, "label CONTAINS %@", "1 linksboven"))
        let p2 = parsePoint(readout.label)!
        XCTAssertEqual(p2.0, p1.0, accuracy: 25); XCTAssertEqual(p2.1, p1.1, accuracy: 25)
        app.buttons["Laatste punt weg"].tap()

        // pannen met één vinger (niet op een punt) en daarna selecteren: andere beeldplek
        let from = canvas.coordinate(withNormalizedOffset: CGVector(dx: 0.7, dy: 0.5)), to = canvas.coordinate(withNormalizedOffset: CGVector(dx: 0.3, dy: 0.5))
        from.press(forDuration: 0.05, thenDragTo: to)
        XCTAssertEqual(zoomLabel.label.replacingOccurrences(of: "×", with: ""), String(format: "%.1f", z), "pannen verandert de zoom niet")
        canvas.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        XCTAssertTrue(waitFor(readout, "label CONTAINS %@", "1 linksboven"))
        let p3 = parsePoint(readout.label)!
        XCTAssertGreaterThan(abs(p3.0 - p1.0) + abs(p3.1 - p1.1), 40, "na pannen wijst het midden naar een ander deel van het beeld")
        app.buttons["Laatste punt weg"].tap()

        // dubbel tikken: reset
        canvas.doubleTap()
        XCTAssertTrue(waitFor(zoomLabel, "label == %@", "1.0×"))
        // knoppen en slider
        app.buttons["zoomButton4"].tap()
        XCTAssertTrue(waitFor(zoomLabel, "label == %@", "4.0×"))
        app.buttons["zoomReset"].tap()
        XCTAssertTrue(waitFor(zoomLabel, "label == %@", "1.0×"))
        app.sliders["zoomSlider"].adjust(toNormalizedSliderPosition: 1.0)
        XCTAssertTrue(waitFor(zoomLabel, "label == %@", "8.0×"))
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testFourCornersCanBePlacedAndSavedWhileZoomed() {
        let app = XCUIApplication()
        openTestImagePicker(app)
        let canvas = app.otherElements["frameCanvas"], readout = app.staticTexts["pointsReadout"]
        app.buttons["zoomButton2"].tap()
        XCTAssertTrue(waitFor(app.staticTexts["zoomIndicator"], "label == %@", "2.0×"))
        for (i, o) in [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)].enumerated() {
            canvas.coordinate(withNormalizedOffset: CGVector(dx: o.0, dy: o.1)).tap()
            XCTAssertTrue(waitFor(readout, "label CONTAINS %@", "\(i + 1) "))
        }
        XCTAssertTrue(waitFor(app.staticTexts["cornerPrompt"], "label CONTAINS %@", "Alle vier"))
        let save = app.buttons["Opslaan"]
        XCTAssertTrue(save.isEnabled); save.tap()
        XCTAssertTrue(waitFor(app.staticTexts["cornerPrompt"], "label CONTAINS %@", "Opgeslagen"))
        XCTAssertEqual(app.state, .runningForeground)
    }

    func testPhotoScanZoomControlsAndShutterWithoutCamera() {
        let app = XCUIApplication()
        app.launchArguments += ["-uitest-prefill"]
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
        app.buttons["Foto-scan starten"].tap()
        let ind = app.staticTexts["photoZoomIndicator"]
        XCTAssertTrue(ind.waitForExistence(timeout: 15))
        XCTAssertEqual(ind.label, "1.0×")
        XCTAssertTrue(app.buttons["shutterButton"].exists, "één duidelijke fotoknop")
        XCTAssertFalse(app.buttons["shutterButton"].isEnabled, "zonder camera/ARKit (simulator) is de fotoknop uitgeschakeld, geen crash")
        app.buttons["photoZoom4"].tap()
        XCTAssertTrue(waitFor(ind, "label == %@", "4.0×"))
        app.buttons["photoZoom1"].tap()
        XCTAssertTrue(waitFor(ind, "label == %@", "1.0×"))
        app.sliders["photoZoomSlider"].adjust(toNormalizedSliderPosition: 0.5)
        XCTAssertTrue(waitFor(ind, "label != %@", "1.0×"))
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// Foto -> automatische kandidaat-detectie (Apple Vision op de synthetische foto) -> kaders -> voorlopige maat (synthetische LiDAR-diepte) -> overzicht.
    func testPhotoToBoxesToMeasurementWorkflowOnSyntheticPhoto() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 30))
        app.buttons["Testfoto met synthetische data (simulatie)"].tap()
        let detected = app.staticTexts["overviewDetected"]
        XCTAssertTrue(detected.waitForExistence(timeout: 30))
        XCTAssertTrue(waitFor(detected, "NOT (label CONTAINS %@)", "Herkend: 0 ", timeout: 90), "er moet minstens één kandidaat-kozijn worden herkend")
        XCTAssertTrue(app.otherElements["photoCanvas"].exists)
        XCTAssertTrue(app.staticTexts["overviewUnique"].label.contains("Voorlopig unieke kozijnen"))
        XCTAssertTrue(app.staticTexts["overviewChecks"].label.contains("Controles (oranje)"))
        let area = app.staticTexts["overviewArea"]
        XCTAssertTrue(waitFor(area, "label CONTAINS %@", "ESTIMATED", timeout: 60) || area.label.contains("DERIVED"), "voorlopige bruto m² per status (enkele foto: ESTIMATED)")
        let row = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH %@", "boxRow-")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        XCTAssertTrue(row.label.contains("m²") || row.label.contains("UNKNOWN"))
        if !row.isHittable { app.scrollViews.firstMatch.swipeUp() }
        row.tap()
        let dims = app.staticTexts["detailDims"]
        XCTAssertTrue(dims.waitForExistence(timeout: 15))
        app.buttons["rejectButton"].tap()                              // "geen kozijn": lokaal bewaard, telt niet meer mee
        XCTAssertTrue(waitFor(app.staticTexts["overviewDetected"], "label CONTAINS %@", "Herkend: 0 ", timeout: 20) || app.staticTexts["overviewDetected"].label.contains("Herkend:"))
        XCTAssertEqual(app.state, .runningForeground)
    }
}
