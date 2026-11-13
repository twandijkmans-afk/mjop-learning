import XCTest

/// MJOP Live 3: rooktest en schermafbeeldingen (licht en donker) van de native schermen.
/// `-mjop-demo` (alleen Debug) logt in met een voorbeeldsessie en het voorbeeldproject, zonder netwerk naar de database.
/// De schermafbeeldingen komen in het testresultaat; de bouwopdracht zet ze in het artefact en in het log.
final class ScreenshotTourUITests: XCTestCase {
    override func setUp() { continueAfterFailure = true }

    override func tearDown() {
        if #available(iOS 17.0, *) { XCUIDevice.shared.appearance = .light }
    }

    /// Zonder sessie start de app op het inlogscherm.
    func testLoginScreenAppearsWithoutSession() {
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-uitest"]
        app.launch()
        XCTAssertTrue(el(app, "loginEmail").waitForExistence(timeout: 20), "inlogscherm met e-mailveld")
        XCTAssertTrue(el(app, "loginSubmit").exists)
        settle(); shot(app, "0-inloggen-licht")
    }

    func testTourLight() { tour(dark: false) }
    func testTourDark() { tour(dark: true) }

    private func tour(dark: Bool) {
        if #available(iOS 17.0, *) { XCUIDevice.shared.appearance = dark ? .dark : .light } else if dark { return }
        let mode = dark ? "donker" : "licht"
        let app = XCUIApplication()
        app.launchArguments += ["-mjop-demo"] + (dark ? ["-mjop-dark"] : [])
        app.launch()

        XCTAssertTrue(el(app, "homeGreeting").waitForExistence(timeout: 30), "Home na inloggen")
        settle(2); shot(app, "1-home-\(mode)")

        tap(el(app, "tab-Projecten"))
        XCTAssertTrue(el(app, "project-Singelstraat 8").waitForExistence(timeout: 15))
        settle(); shot(app, "2-projecten-\(mode)")

        tap(el(app, "project-Singelstraat 8"))
        XCTAssertTrue(el(app, "projectTitle").waitForExistence(timeout: 15))
        settle(2); shot(app, "3-project-\(mode)")
        if app.buttons["Documenten"].firstMatch.waitForExistence(timeout: 5) {
            app.buttons["Documenten"].firstMatch.tap(); settle()
            tap(el(app, "addDocument"))
            // In de testbouw opent dit de bestandskiezer van iOS; die sluiten we weer.
            settle(2); shot(app, "3b-documenten-kiezer-\(mode)")
            if app.buttons["Cancel"].firstMatch.exists { app.buttons["Cancel"].firstMatch.tap() } else if app.buttons["Annuleer"].firstMatch.exists { app.buttons["Annuleer"].firstMatch.tap() }
            settle()
        }
        app.buttons["Terug"].firstMatch.tap()

        tap(el(app, "tab-MJOP")); settle(2); shot(app, "4-mjop-planning-\(mode)")
        tap(el(app, "assess")); settle(); shot(app, "4a-beoordelen-\(mode)")
        tap(el(app, "score-3")); settle(0.5); shot(app, "4a2-beoordelen-gekozen-\(mode)")
        app.buttons["Stop"].firstMatch.tap(); settle()
        tap(el(app, "seg-Kosten")); settle(); shot(app, "4b-mjop-kosten-\(mode)")
        tap(el(app, "seg-Rapport")); settle(); shot(app, "4c-mjop-rapport-\(mode)")
        tap(el(app, "tab-Profiel")); settle(); shot(app, "5-profiel-\(mode)")
        tap(el(app, "tabScan")); settle(2); shot(app, "6-scan-\(mode)")
        app.buttons["Sluiten"].firstMatch.tap(); settle()
        tap(el(app, "tab-Projecten")); tap(el(app, "newProject"))
        let search = el(app, "addressSearch")
        if search.waitForExistence(timeout: 10) {
            search.tap(); search.typeText("Singelstraat 8 Muiden")
            settle(3); shot(app, "7-nieuw-adres-\(mode)")
            let hit = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH %@", "address-")).firstMatch
            if hit.waitForExistence(timeout: 10) { hit.tap(); settle(6); shot(app, "8-nieuw-gebouw-\(mode)") }
        }
    }

    private func el(_ app: XCUIApplication, _ id: String) -> XCUIElement { app.descendants(matching: .any)[id].firstMatch }

    private func tap(_ e: XCUIElement) {
        XCTAssertTrue(e.waitForExistence(timeout: 15), "niet gevonden: \(e)")
        e.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
    }

    private func settle(_ seconds: TimeInterval = 1.5) { Thread.sleep(forTimeInterval: seconds) }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let a = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        a.name = name
        a.lifetime = .keepAlways
        add(a)
    }
}
