import XCTest

/// UI-tests voor de native navigatie met vijf tabs (app-versie 2), in de iOS-simulator.
/// Geen netwerk: de WebView laadt een lokale, nagebootste website (`-mjop-tabs-test-page`, alleen in Debug-builds) die de nieuwe navigatiecommando's kent en via de
/// ECHTE brug (`webkit.messageHandlers.mjopNative`) met de app praat. De "projecten" in die pagina zijn testgegevens; de Release-app haalt ze uit de backend.
/// Bewijst NIET: echt inloggen bij Supabase, camera/LiDAR, of het gedrag op een fysieke iPhone.
final class MainTabsUITests: XCTestCase {
    override func setUp() { continueAfterFailure = false }

    // MARK: hulpjes

    private func launch(_ extra: [String] = [], tabsPage: Bool = true, overrideClassic: Bool = true) -> XCUIApplication {
        let app = XCUIApplication()
        // "-mjop.classicMode NO" overschrijft de bewaarde keuze, zodat tests elkaar niet beïnvloeden. Let op: een opstartargument blijft ook
        // gelden als de app de waarde wijzigt; een test die de schakelaar zelf bedient moet dus zonder overschrijving starten.
        app.launchArguments += [tabsPage ? "-mjop-tabs-test-page" : "-mjop-test-page"] + (overrideClassic ? ["-mjop.classicMode", "NO"] : []) + extra
        app.launch()
        return app
    }

    private func launchWithTabs(overrideClassic: Bool = true) -> XCUIApplication {
        let app = launch(overrideClassic: overrideClassic)
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 40), "de vijf tabs verschijnen zodra de website meldt dat hij de nieuwe navigatie kent")
        return app
    }

    private func any(_ app: XCUIApplication, _ id: String) -> XCUIElement { app.descendants(matching: .any)[id] }

    private func element(_ app: XCUIApplication, containing text: String) -> XCUIElement {
        app.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS %@ OR value CONTAINS %@", text, text)).firstMatch
    }

    private func tapCenter(_ el: XCUIElement) {
        XCTAssertTrue(el.waitForExistence(timeout: 15), "element niet gevonden: \(el)")
        el.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
    }

    private func tab(_ app: XCUIApplication, _ name: String) { tapCenter(app.tabBars.buttons[name]) }

    /// Wacht tot een tabblad gekozen is: de app schakelt pas nadat de website het project heeft geopend, dus direct controleren is te vroeg.
    private func waitSelected(_ el: XCUIElement, timeout: TimeInterval = 20) -> Bool {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "isSelected == true"), object: el)
        return XCTWaiter().wait(for: [expectation], timeout: timeout) == .completed
    }

    private func reveal(_ el: XCUIElement, in app: XCUIApplication) {
        var n = 0
        while !el.exists && n < 5 { app.swipeUp(); n += 1 }
    }

    /// Lijsten bouwen alleen zichtbare rijen op: scroll tot het element bestaat en aantikbaar is.
    private func scrollTo(_ el: XCUIElement, in app: XCUIApplication) {
        var n = 0
        while !(el.exists && el.isHittable) && n < 8 { app.swipeUp(); n += 1 }
    }

    private func webText(_ app: XCUIApplication, _ text: String, timeout: TimeInterval = 20) -> Bool {
        app.webViews.staticTexts[text].waitForExistence(timeout: timeout)
    }

    /// Terug naar de projectlijst als er nog een detailscherm open staat (de lijst blijft in de tab Projecten staan).
    private func showProjectList(_ app: XCUIApplication, expecting row: String) {
        tab(app, "Projecten")
        if !any(app, row).waitForExistence(timeout: 5) { app.navigationBars.buttons.element(boundBy: 0).tap() }
    }

    /// Opent "Testproject A" via de tab Projecten (eerst het detailscherm, daarna de rij MJOP); de app schakelt daarna naar MJOP.
    private func openProjectA(_ app: XCUIApplication) {
        tab(app, "Projecten")
        tapCenter(any(app, "projectRow-Testproject A"))
        tapCenter(any(app, "detailOpenMJOP"))
        XCTAssertTrue(webText(app, "Project: Testproject A", timeout: 30), "het project is in de website geopend")
        XCTAssertTrue(waitSelected(app.tabBars.buttons["MJOP"]), "na het openen staat de gebruiker in het MJOP-gedeelte")
    }

    private func pageId(_ app: XCUIApplication) -> String {
        let el = app.webViews.staticTexts.matching(NSPredicate(format: "label BEGINSWITH %@", "Pagina-id:")).firstMatch
        XCTAssertTrue(el.waitForExistence(timeout: 15))
        return el.label
    }

    // MARK: de vijf tabs

    func testFiveNativeTabsReplaceTheWebsiteNavigation() {
        let app = launchWithTabs()
        for name in ["Home", "Projecten", "Meten", "MJOP", "Profiel"] {
            XCTAssertTrue(app.tabBars.buttons[name].exists, "tab \(name) ontbreekt")
        }
        XCTAssertFalse(app.buttons["mjopMenu"].exists, "geen klassieke kopbalk met menu meer wanneer de native tabs actief zijn")
        XCTAssertTrue(app.tabBars.buttons["Home"].isSelected)
    }

    func testHomeShowsConnectionLastProjectAndNextStepWithoutInventingData() {
        let app = launchWithTabs()
        XCTAssertTrue(any(app, "homeProjectLabel").waitForExistence(timeout: 30), "laatst bijgewerkte project uit de backend")
        XCTAssertEqual(any(app, "homeProjectLabel").label, "Testproject A", "het project met de meest recente datum; project B heeft geen datum en wordt niet verzonnen")
        XCTAssertTrue(any(app, "homeConnection").exists, "verbindingsstatus")
        XCTAssertTrue(["Verbonden", "Offline"].contains(any(app, "homeConnection").label))
        XCTAssertEqual(any(app, "homeAccount").label, "Ingelogd")
        XCTAssertTrue(element(app, containing: "Bekijk je voorstel").exists || element(app, containing: "ga verder").exists, "volgende stap")
        XCTAssertNotNil(Int(any(app, "homeInProgress").label), "aantal onderbroken fotorondes op dit toestel is een getal (lokale opslag)")
        XCTAssertNotNil(Int(any(app, "homeUnsynced").label), "aantal nog niet overgedragen rondes is een getal")
    }

    // MARK: projecten

    func testProjectsTabListsProjectsFromTheWebsiteBackend() {
        let app = launchWithTabs()
        tab(app, "Projecten")
        XCTAssertTrue(any(app, "projectRow-Testproject A").waitForExistence(timeout: 30))
        XCTAssertTrue(any(app, "projectRow-Testproject B").exists)
        XCTAssertTrue(element(app, containing: "Teststraat 1, Testdorp").exists, "adres")
        XCTAssertTrue(element(app, containing: "Laatst bijgewerkt").exists, "laatst bijgewerkt")
        XCTAssertTrue(element(app, containing: "Laatst bijgewerkt: onbekend").exists, "ontbrekende datum blijft onbekend")
        XCTAssertTrue(any(app, "newProject").exists, "nieuw project via de websiteflow")
    }

    func testOpeningAProjectOpensItInMJOPWithProjectBar() {
        let app = launchWithTabs()
        openProjectA(app)
        XCTAssertTrue(webText(app, "Tabblad: planning"), "MJOP opent bij Planning")
        XCTAssertTrue(any(app, "projectContextBar").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, containing: "Testproject A").exists, "de gebruiker ziet altijd in welk project hij werkt")
    }

    func testMJOPSectionsNavigateTheWebsiteWithoutClickingOnIt() {
        let app = launchWithTabs()
        openProjectA(app)
        for (title, tabName) in [("Maatregelen", "gebouw"), ("Begroting", "home"), ("Rapportage", "rapport"), ("Planning", "planning")] {
            app.buttons[title].firstMatch.tap()
            XCTAssertTrue(webText(app, "Tabblad: \(tabName)"), "\(title) toont website-tabblad \(tabName)")
        }
    }

    func testMJOPWithoutAProjectExplainsWhatToDo() {
        let app = launchWithTabs()
        tab(app, "MJOP")
        XCTAssertTrue(element(app, containing: "Geen project geopend").waitForExistence(timeout: 20))
        XCTAssertTrue(app.buttons["Naar Projecten"].exists)
    }

    // MARK: één gedeelde WebView

    func testSharedWebViewKeepsStateSessionAndLoginAcrossAllTabs() {
        let app = launchWithTabs()
        openProjectA(app)
        let web = app.webViews
        XCTAssertTrue(web.buttons["Teller verhogen"].waitForExistence(timeout: 20))
        web.buttons["Teller verhogen"].tap(); web.buttons["Teller verhogen"].tap()
        XCTAssertTrue(webText(app, "Teller: 2"))
        web.buttons["Opslag schrijven"].tap()
        XCTAssertTrue(webText(app, "Opslag: sessie=sessie-bewaard lokaal=ingelogd-bewaard"))
        let id0 = pageId(app)

        // alle tabs langs, ook de native zonder WebView, en terug naar MJOP
        for name in ["Home", "Projecten", "Meten", "Profiel", "Projecten", "Home", "MJOP"] { tab(app, name) }
        XCTAssertTrue(webText(app, "Teller: 2", timeout: 20), "paginastaat behouden: de website is niet opnieuw geladen")
        XCTAssertEqual(pageId(app), id0, "dezelfde pagina-instantie (geen herlaad)")
        web.buttons["Opslag lezen"].tap()
        XCTAssertTrue(webText(app, "Opslag: sessie=sessie-bewaard lokaal=ingelogd-bewaard"), "sessionStorage en lokale opslag (hier loopt de inlogsessie in) zijn behouden")
        XCTAssertTrue(webText(app, "Ingelogd: ja"), "de gebruiker is ingelogd gebleven")
        XCTAssertTrue(webText(app, "Project: Testproject A"), "het geopende project is gebleven")

        // de diagnose bevestigt het: één keer geladen, wel degelijk verplaatst
        tab(app, "Profiel")
        tapCenter(any(app, "profileAdvanced"))
        scrollTo(any(app, "diagMoves"), in: app)
        XCTAssertTrue(any(app, "diagLoadCount").waitForExistence(timeout: 10))
        XCTAssertEqual(any(app, "diagLoadCount").label, "1×", "de website is in totaal één keer geladen")
        XCTAssertEqual(any(app, "diagWebViewCount").label, "1 exemplaar")
        XCTAssertNotEqual(any(app, "diagMoves").label, "0×", "de gedeelde WebView is aantoonbaar tussen tabs verplaatst")
    }

    func testRoundStartedFromTheWebsiteReturnsToTheSameTabAndState() {
        let app = launchWithTabs()
        openProjectA(app)
        XCTAssertTrue(app.webViews.buttons["Teller verhogen"].waitForExistence(timeout: 20))
        app.webViews.buttons["Teller verhogen"].tap()
        XCTAssertTrue(webText(app, "Teller: 1"))
        let id0 = pageId(app)
        app.webViews.buttons["Start fotoronde"].tap()
        XCTAssertTrue(app.navigationBars["Fotoronde"].waitForExistence(timeout: 20), "de bestaande brug start de fotoronde")
        XCTAssertTrue(element(app, containing: "Testproject A").waitForExistence(timeout: 10), "projectcontext is meegekomen")
        reveal(app.buttons["roundSuspend"], in: app)
        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(webText(app, "Teller: 1", timeout: 20), "terug op dezelfde plek met dezelfde paginastaat")
        XCTAssertTrue(app.tabBars.buttons["MJOP"].isSelected, "terug in dezelfde tab")
        XCTAssertEqual(pageId(app), id0, "de website is niet opnieuw geladen")
    }

    // MARK: Meten

    // MARK: Projectdetails

    func testProjectDetailShowsRealBuildingFactsAndKeepsUnknownUnknown() {
        let app = launchWithTabs()
        tab(app, "Projecten")
        tapCenter(any(app, "projectRow-Testproject A"))
        XCTAssertTrue(any(app, "detailTitle").waitForExistence(timeout: 20))
        XCTAssertEqual(any(app, "detailTitle").label, "Testproject A")
        XCTAssertTrue(any(app, "detailFacts").waitForExistence(timeout: 20))
        let facts = any(app, "detailFacts")
        let expect = NSPredicate(format: "label CONTAINS %@", "1972")
        expectation(for: expect, evaluatedWith: facts)
        waitForExpectations(timeout: 30)
        XCTAssertTrue(facts.label.contains("12 appartementen"), "bouwjaar en appartementen komen uit het geopende project")
        tapCenter(facts)
        XCTAssertEqual(any(app, "factBouwjaar").label, "1972")
        XCTAssertEqual(any(app, "factGevel").label, "Onbekend", "een onbekend geveloppervlak blijft onbekend, nooit 0")
        XCTAssertTrue(any(app, "factDak").label.contains("313"))
        XCTAssertFalse(any(app, "factDak").label.contains("geschat"), "een 3D BAG-waarde is niet geschat")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        tapCenter(any(app, "detailOpenMJOP"))
        XCTAssertTrue(waitSelected(app.tabBars.buttons["MJOP"]), "de rij MJOP schakelt naar het MJOP-gedeelte")
        XCTAssertTrue(webText(app, "Project: Testproject A", timeout: 30), "de rij MJOP opent het project in de website")
    }

    func testMeasureTabStartsARoundForTheChosenProjectAndReturnsToMeasure() {
        let app = launchWithTabs()
        tab(app, "Meten")
        XCTAssertTrue(any(app, "measureStart").waitForExistence(timeout: 20))
        XCTAssertFalse(any(app, "measureStart").isEnabled, "zonder gekozen project kan er niet gemeten worden")
        tapCenter(any(app, "measureProjectButton"))
        tapCenter(any(app, "pickProject-Testproject A"))
        XCTAssertTrue(element(app, containing: "De meting hoort bij dit project").waitForExistence(timeout: 10))
        XCTAssertTrue(any(app, "measureStart").isEnabled)
        tapCenter(any(app, "measureStart"))
        XCTAssertTrue(app.navigationBars["Fotoronde"].waitForExistence(timeout: 30), "de website opent het project en start de bestaande scanner via de brug")
        XCTAssertTrue(element(app, containing: "Testproject A").waitForExistence(timeout: 10), "projectcontext in de scanner")
        reveal(app.buttons["roundSuspend"], in: app)
        app.buttons["roundSuspend"].tap()
        XCTAssertTrue(app.tabBars.buttons["Meten"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.tabBars.buttons["Meten"].isSelected, "terug in de tab Meten")
    }

    func testResultsAndScannerTestModeAreReachableFromMeasure() {
        let app = launchWithTabs()
        tab(app, "Meten")
        tapCenter(any(app, "measureResults"))
        XCTAssertTrue(any(app, "resultsEmpty").waitForExistence(timeout: 10), "lege staat: nog geen afgeronde fotorondes")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        scrollTo(any(app, "measureScannerTest"), in: app)
        tapCenter(any(app, "measureScannerTest"))
        XCTAssertTrue(app.navigationBars["Photo Walk"].waitForExistence(timeout: 20), "de losse scanner blijft bereikbaar onder Meten")
        app.buttons["scannerTestClose"].tap()
        XCTAssertTrue(any(app, "measureStart").waitForExistence(timeout: 10))
    }

    // MARK: niet-opgeslagen werk

    func testSwitchingProjectWithUnsavedChangesAsksForConfirmation() {
        let app = launchWithTabs()
        openProjectA(app)
        showProjectList(app, expecting: "projectRow-Testproject B")
        tapCenter(any(app, "projectRow-Testproject B"))
        XCTAssertTrue(any(app, "detailNotLoaded").waitForExistence(timeout: 20), "het detailscherm vervangt het open project niet stil: het meldt dat de gegevens niet geladen zijn")
        tapCenter(any(app, "detailOpenMJOP"))
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 20), "de website weigert stil vervangen; de gebruiker moet bevestigen")
        XCTAssertTrue(app.alerts.firstMatch.label.contains("Niet-opgeslagen wijzigingen"))
        app.alerts.buttons["Annuleren"].tap()
        XCTAssertTrue(app.tabBars.buttons["Projecten"].isSelected, "bij annuleren blijft de gebruiker waar hij was")
        tapCenter(any(app, "detailOpenMJOP"))
        XCTAssertTrue(app.alerts.buttons["Toch openen"].waitForExistence(timeout: 20))
        app.alerts.buttons["Toch openen"].tap()
        XCTAssertTrue(webText(app, "Project: Testproject B", timeout: 30), "na uitdrukkelijke bevestiging wordt het andere project geopend")
    }

    // MARK: Profiel

    func testProfileOffersAccountSectionsAndAdvancedSettings() {
        let app = launchWithTabs()
        tab(app, "Profiel")
        for id in ["profile-account", "profile-organisatie", "profile-weergave", "profile-abonnement", "profile-privacy", "profileSignOut", "profileAdvanced"] {
            XCTAssertTrue(any(app, id).waitForExistence(timeout: 15), "\(id) ontbreekt in Profiel")
        }
        tapCenter(any(app, "profile-organisatie"))
        XCTAssertTrue(app.navigationBars["Organisatie"].waitForExistence(timeout: 15))
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 15), "websiteonderdeel binnen Profiel")
        XCTAssertTrue(webText(app, "Tabblad: account"), "de app navigeerde de website naar Account")
        app.navigationBars.buttons.element(boundBy: 0).tap()
        tapCenter(any(app, "profileAdvanced"))
        // van boven naar beneden, met scrollen: rijen onder de rand bestaan pas als ze in beeld zijn
        for id in ["advReload", "advScannerTest", "advClassic", "diagVersion", "diagLidar", "diagNavMode"] {
            scrollTo(any(app, id), in: app)
            XCTAssertTrue(any(app, id).waitForExistence(timeout: 10), "\(id) ontbreekt in Geavanceerd")
        }
        XCTAssertEqual(any(app, "diagNavMode").label, "Actief")
    }

    func testSignOutAsksConfirmationAndThenShowsTheLoginOptions() {
        let app = launchWithTabs()
        tab(app, "Profiel")
        tapCenter(any(app, "profileSignOut"))
        XCTAssertTrue(app.buttons["Annuleren"].waitForExistence(timeout: 10), "eerst een bevestiging met de keuze Annuleren")
        app.buttons["Annuleren"].tap()
        XCTAssertTrue(any(app, "profileSignOut").waitForExistence(timeout: 10), "geannuleerd: nog ingelogd")
        tapCenter(any(app, "profileSignOut"))
        XCTAssertTrue(app.buttons["Annuleren"].waitForExistence(timeout: 10))
        // de bevestigingsknop heet ook "Uitloggen" (net als de rij zelf): de knop in het actieblad is de laatste
        let confirm = app.sheets.buttons["Uitloggen"].firstMatch
        if confirm.waitForExistence(timeout: 5) { confirm.tap() } else { app.buttons.matching(NSPredicate(format: "label == %@", "Uitloggen")).allElementsBoundByIndex.last?.tap() }
        XCTAssertTrue(any(app, "profileLogin").waitForExistence(timeout: 20), "na uitloggen: inlogopties")
        XCTAssertTrue(any(app, "profilePasteLogin").exists)
    }

    // MARK: terugval en oudere websites

    func testOlderWebsiteWithoutTheNewNavigationKeepsTheClassicScreen() {
        let app = launch(tabsPage: false)         // de bestaande testpagina meldt zich nooit met webReady
        XCTAssertTrue(app.webViews.firstMatch.waitForExistence(timeout: 30))
        XCTAssertTrue(app.buttons["mjopMenu"].exists, "klassieke kopbalk direct zichtbaar")
        sleep(9)                                  // langer dan de wachttijd op webReady
        XCTAssertTrue(app.buttons["mjopMenu"].exists, "en nog steeds: oudere websites blijven werken")
        XCTAssertEqual(app.tabBars.count, 0, "geen native tabs zonder ondersteuning van de website")
        XCTAssertTrue(app.webViews.buttons["Start fotoronde"].waitForExistence(timeout: 15), "de bestaande brug (fotoronde) werkt ongewijzigd")
    }

    func testClassicModeCanBeChosenAndLeftAgain() {
        let app = launchWithTabs(overrideClassic: false)      // de schakelaar moet de bewaarde keuze echt kunnen wijzigen
        tab(app, "Profiel")
        tapCenter(any(app, "profileAdvanced"))
        let classicSwitch = app.switches["advClassic"]
        scrollTo(classicSwitch, in: app)
        XCTAssertTrue(classicSwitch.waitForExistence(timeout: 10))
        classicSwitch.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.5)).tap()      // de schakelaar zelf, niet het label
        XCTAssertTrue(app.buttons["mjopMenu"].waitForExistence(timeout: 15), "klassieke weergave met menu")
        XCTAssertEqual(app.tabBars.count, 0)
        tapCenter(app.buttons["mjopMenu"])
        tapCenter(app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Nieuwe navigatie gebruiken")).firstMatch)
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 15), "de vijf tabs zijn terug")
    }
}
