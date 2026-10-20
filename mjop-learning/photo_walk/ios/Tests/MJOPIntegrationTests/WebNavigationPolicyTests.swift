import XCTest
@testable import MJOPIntegration

final class WebNavigationPolicyTests: XCTestCase {
    let p = WebNavigationPolicy.production
    func u(_ s: String) -> URL { URL(string: s)! }

    func testSiteIsAllowedInApp() {
        XCTAssertEqual(p.decide(MJOPConfig.siteURL), .allowInApp)
        XCTAssertEqual(p.decide(u("https://twandijkmans-afk.github.io/MJOP-App/index.html?x=1#frag")), .allowInApp)
        XCTAssertEqual(p.decide(u("https://twandijkmans-afk.github.io/MJOP-App")), .allowInApp)
        XCTAssertEqual(p.decide(u("https://TWANDIJKMANS-AFK.github.io/MJOP-App/")), .allowInApp)
    }

    func testOtherPathsOnSameHostAreNotTheApp() {
        // andere GitHub Pages-projecten onder hetzelfde domein mogen niet in de app draaien
        XCTAssertEqual(p.decide(u("https://twandijkmans-afk.github.io/MJOP-App-evil/")), .block(reason: "automatische doorverwijzing naar een ander domein geblokkeerd"))
        XCTAssertEqual(p.decide(u("https://twandijkmans-afk.github.io/other/"), userInitiated: true), .openExternally(u("https://twandijkmans-afk.github.io/other/")))
    }

    func testLookalikeHostsAndCredentialsAreNotAllowed() {
        XCTAssertFalse(p.isAllowedInApp(u("https://twandijkmans-afk.github.io.evil.com/MJOP-App/")))
        XCTAssertFalse(p.isAllowedInApp(u("https://evil.com/twandijkmans-afk.github.io/MJOP-App/")))
        XCTAssertFalse(p.isAllowedInApp(u("https://user:pw@twandijkmans-afk.github.io/MJOP-App/")))
        XCTAssertFalse(p.isAllowedInApp(u("https://twandijkmans-afk.github.io:8443/MJOP-App/")))
    }

    func testSupabaseOnlyForAuthPaths() {
        XCTAssertTrue(p.isAllowedInApp(u("https://\(MJOPConfig.supabaseHost)/auth/v1/verify?token=x")))
        XCTAssertFalse(p.isAllowedInApp(u("https://\(MJOPConfig.supabaseHost)/rest/v1/saved_plans")))
        XCTAssertFalse(p.isAllowedInApp(u("https://other.supabase.co/auth/v1/verify")))
    }

    func testForeignLinksOpenInSafariOnlyWhenTapped() {
        let pdok = u("https://www.pdok.nl/")
        XCTAssertEqual(p.decide(pdok, userInitiated: true), .openExternally(pdok))
        guard case .block = p.decide(pdok, userInitiated: false) else { return XCTFail("automatische redirect naar vreemd domein moet geblokkeerd worden") }
        guard case .block = p.decide(pdok, isMainFrame: false, userInitiated: true) else { return XCTFail("vreemde iframes blokkeren") }
    }

    func testMailtoAndTelNeedATap() {
        XCTAssertEqual(p.decide(u("mailto:info@example.nl"), userInitiated: true), .openExternally(u("mailto:info@example.nl")))
        guard case .block = p.decide(u("tel:+31123456789")) else { return XCTFail() }
    }

    func testUnsafeSchemesAreBlocked() {
        for s in ["http://twandijkmans-afk.github.io/MJOP-App/", "javascript:alert(1)", "file:///etc/passwd", "data:text/html,hi", "mjoplive://auth-callback?code=abcdefgh", "itms-services://?action=x", "ftp://x.nl/"] {
            guard case .block = p.decide(u(s), userInitiated: true) else { return XCTFail("\(s) moet geblokkeerd worden") }
        }
        guard case .block = p.decide(nil) else { return XCTFail() }
    }

    func testBlobDownloadsOnlyFromTheSiteOrigin() {
        XCTAssertEqual(p.decide(u("blob:https://twandijkmans-afk.github.io/3f1c2d7e-1111-2222-3333-444455556666")), .allowInApp)
        guard case .block = p.decide(u("blob:https://evil.com/3f1c")) else { return XCTFail() }
        guard case .block = p.decide(u("blob:null/3f1c")) else { return XCTFail() }
    }

    func testAboutBlankOnly() {
        XCTAssertEqual(p.decide(u("about:blank")), .allowInApp)
        guard case .block = p.decide(u("about:srcdoc")) else { return XCTFail() }
    }
}
