import XCTest
@testable import MJOPIntegration

final class AuthPasteTests: XCTestCase {
    let uuid = "3f1c2d7e-1111-2222-3333-444455556666"

    func testBareCode() { XCTAssertEqual(AuthPaste.parse("  \(uuid)\n"), .code(uuid)) }

    func testSchemeLink() {
        XCTAssertEqual(AuthPaste.parse("mjoplive://auth-callback?code=\(uuid)"), .code(uuid))
        guard case .rejected = AuthPaste.parse("mjoplive://auth-callback?access_token=abcdefgh12") else { return XCTFail() }
    }

    func testBridgePageLinkOnOwnSiteGivesTheCode() {
        XCTAssertEqual(AuthPaste.parse("https://twandijkmans-afk.github.io/MJOP-App/app-callback.html?code=\(uuid)"), .code(uuid))
        guard case .rejected = AuthPaste.parse("https://twandijkmans-afk.github.io/MJOP-App/app-callback.html?code=<x>") else { return XCTFail() }
    }

    func testSupabaseVerifyLinkOpensInTheWebViewSoThePKCEVerifierIsUsed() {
        let u = "https://\(MJOPConfig.supabaseHost)/auth/v1/verify?token=pkce_abc&type=magiclink&redirect_to=https://twandijkmans-afk.github.io/MJOP-App/app-callback.html"
        XCTAssertEqual(AuthPaste.parse(u), .openInWebView(URL(string: u)!))
    }

    func testForeignAndTokenLinksAreRejected() {
        for s in ["https://evil.com/auth/v1/verify?token=x", "http://\(MJOPConfig.supabaseHost)/auth/v1/verify?token=x", "https://\(MJOPConfig.supabaseHost)/rest/v1/saved_plans",
                  "https://twandijkmans-afk.github.io/MJOP-App/#access_token=abcdefghij&refresh_token=klmnopqrst", "javascript:alert(1)", "hallo wereld", "", "x"] {
            guard case .rejected = AuthPaste.parse(s) else { return XCTFail("\(s) moet geweigerd worden") }
        }
        guard case .rejected = AuthPaste.parse(String(repeating: "a", count: 3000)) else { return XCTFail() }
    }
}

final class AuthCallbackErrorMappingTests: XCTestCase {
    func testExpiredLinkGetsDutchExplanationMentioningPrefetch() {
        let url = URL(string: "mjoplive://auth-callback?error_description=Email+link+is+invalid+or+has+expired&error_code=otp_expired")!
        guard case .failure(let m) = AuthCallback.parse(url) else { return XCTFail() }
        XCTAssertTrue(m.contains("verlopen of al gebruikt")); XCTAssertTrue(m.contains("vooraf"))
    }
    func testUnknownErrorKeepsOriginalText() {
        guard case .failure(let m) = AuthCallback.parse(URL(string: "mjoplive://auth-callback?error_description=Iets+anders")!) else { return XCTFail() }
        XCTAssertTrue(m.contains("Iets"))
    }
}
