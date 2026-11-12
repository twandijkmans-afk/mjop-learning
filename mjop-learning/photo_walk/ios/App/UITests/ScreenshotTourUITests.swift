import XCTest

/// Maakt schermafbeeldingen van de belangrijkste schermen (licht en donker) met de nagebootste website, zodat het ontwerp zonder iPhone te controleren is.
/// De afbeeldingen komen in het testresultaat (`ui-tests.xcresult`); de bouwopdracht zet ze in het artefact `schermafbeeldingen`.
/// Controleert alleen dat de schermen te bereiken zijn; de inhoud wordt in MainTabsUITests getest.
final class ScreenshotTourUITests: XCTestCase {
    override func setUp() { continueAfterFailure = true }

    override func tearDown() {
        if #available(iOS 17.0, *) { XCUIDevice.shared.appearance = .light }
    }

    func testTourLight() { tour(dark: false) }
    func testTourDark() { tour(dark: true) }

    private func tour(dark: Bool) {
        if #available(iOS 17.0, *) { XCUIDevice.shared.appearance = dark ? .dark : .light }
        else if dark { return }
        let mode = dark ? "donker" : "licht"
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-tabs-test-page", "-mjop.classicMode", "NO"]
        app.launch()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 40))

        XCTAssertTrue(el(app, "homeProjectLabel").waitForExistence(timeout: 30))
        settle(); shot(app, "1-home-\(mode)")
        app.swipeUp(); settle(); shot(app, "1b-home-onder-\(mode)")

        tab(app, "Projecten")
        XCTAssertTrue(el(app, "projectRow-Testproject A").waitForExistence(timeout: 30))
        settle(); shot(app, "2-projecten-\(mode)")

        tap(el(app, "projectRow-Testproject A"))
        let facts = el(app, "detailFacts")
        XCTAssertTrue(facts.waitForExistence(timeout: 20))
        _ = XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "label CONTAINS %@", "1972"), object: facts)], timeout: 20)
        settle(); shot(app, "3-project-\(mode)")

        let open = el(app, "detailOpenMJOP")
        var n = 0
        while !(open.exists && open.isHittable) && n < 6 { app.swipeUp(); n += 1 }
        tap(open)
        _ = XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: NSPredicate(format: "isSelected == true"), object: app.tabBars.buttons["MJOP"])], timeout: 20)
        settle(3); shot(app, "4-mjop-\(mode)")

        tab(app, "Meten"); settle(); shot(app, "5-meten-\(mode)")
        tab(app, "Profiel"); settle(); shot(app, "6-profiel-\(mode)")
    }

    private func el(_ app: XCUIApplication, _ id: String) -> XCUIElement { app.descendants(matching: .any)[id] }

    private func tap(_ e: XCUIElement) {
        XCTAssertTrue(e.waitForExistence(timeout: 15), "niet gevonden: \(e)")
        e.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
    }

    private func tab(_ app: XCUIApplication, _ name: String) { tap(app.tabBars.buttons[name]) }

    /// Even wachten tot animaties en luchtfoto's (offline: plaatshouder) klaar zijn.
    private func settle(_ seconds: TimeInterval = 1.5) { Thread.sleep(forTimeInterval: seconds) }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        a.name = name
        a.lifetime = .keepAlways
        add(a)
    }
}
