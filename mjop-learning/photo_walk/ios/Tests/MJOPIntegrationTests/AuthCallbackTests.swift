import XCTest
@testable import MJOPIntegration

final class AuthCallbackTests: XCTestCase {
    func u(_ s: String) -> URL { URL(string: s)! }

    func testValidCode() {
        XCTAssertEqual(AuthCallback.parse(u("mjoplive://auth-callback?code=3f1c2d7e-1111-2222-3333-444455556666")), .code("3f1c2d7e-1111-2222-3333-444455556666"))
    }

    func testTokensAreNeverAccepted() {
        for s in ["mjoplive://auth-callback?access_token=abc12345&refresh_token=def45678",
                  "mjoplive://auth-callback?code=abcdefgh&access_token=x",
                  "mjoplive://auth-callback#access_token=abcdefgh&refresh_token=zzzzzzzz"] {
            guard case .rejected = AuthCallback.parse(u(s)) else { return XCTFail("\(s) moet geweigerd worden") }
        }
    }

    func testWrongHostSchemeOrPath() {
        for s in ["mjoplive://other?code=abcdefgh", "https://auth-callback?code=abcdefgh", "mjoplive://auth-callback/extra?code=abcdefgh", "mjoplive://auth-callback?code=abcdefgh&redirect=https://evil.com"] {
            guard case .rejected = AuthCallback.parse(u(s)) else { return XCTFail("\(s) moet geweigerd worden") }
        }
    }

    func testImplausibleCodes() {
        for s in ["mjoplive://auth-callback", "mjoplive://auth-callback?code=", "mjoplive://auth-callback?code=short",
                  "mjoplive://auth-callback?code=abc%20defgh%3Cscript%3E", "mjoplive://auth-callback?code=" + String(repeating: "a", count: 300)] {
            guard case .rejected = AuthCallback.parse(u(s)) else { return XCTFail("\(s) moet geweigerd worden") }
        }
    }

    func testErrorFromSupabaseIsShownNotLoaded() {
        guard case .failure(let m) = AuthCallback.parse(u("mjoplive://auth-callback?error=access_denied&error_description=Email+link+is+invalid+or+has+expired")) else { return XCTFail() }
        XCTAssertTrue(m.contains("expired"))
    }

    func testWebURLStaysOnSiteAndCarriesOnlyTheCode() {
        let w = AuthCallback.webURL(for: "3f1c2d7e-1111-2222-3333-444455556666")!
        XCTAssertEqual(w.absoluteString, "https://twandijkmans-afk.github.io/MJOP-App/?code=3f1c2d7e-1111-2222-3333-444455556666")
        XCTAssertTrue(WebNavigationPolicy.production.isAllowedInApp(w))
        XCTAssertNil(AuthCallback.webURL(for: "x&y=z"))
    }
}
