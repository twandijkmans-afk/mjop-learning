import XCTest
@testable import MJOPIntegration

final class WebLoadFailureTests: XCTestCase {
    func testOfflineCodes() {
        for c in [NSURLErrorNotConnectedToInternet, NSURLErrorNetworkConnectionLost, NSURLErrorDataNotAllowed] {
            let f = WebLoadFailure.classify(domain: NSURLErrorDomain, code: c)
            XCTAssertEqual(f?.kind, .offline)
            XCTAssertEqual(f?.isOffline, true)
            XCTAssertEqual(f?.canRetry, true)
            XCTAssertTrue(f!.message.contains("Gevelscanner werkt ook zonder internet"), "offline-melding verwijst naar de scanner")
        }
    }

    func testCancelledNavigationShowsNoError() {
        XCTAssertNil(WebLoadFailure.classify(domain: NSURLErrorDomain, code: NSURLErrorCancelled))
    }

    func testOtherClasses() {
        XCTAssertEqual(WebLoadFailure.classify(domain: NSURLErrorDomain, code: NSURLErrorTimedOut)?.kind, .timeout)
        XCTAssertEqual(WebLoadFailure.classify(domain: NSURLErrorDomain, code: NSURLErrorCannotFindHost)?.kind, .unreachable)
        XCTAssertEqual(WebLoadFailure.classify(domain: NSURLErrorDomain, code: NSURLErrorServerCertificateUntrusted)?.kind, .security)
        XCTAssertEqual(WebLoadFailure.classify(domain: NSURLErrorDomain, code: -9999)?.kind, .other)
        XCTAssertEqual(WebLoadFailure.classify(domain: "WKErrorDomain", code: 5)?.kind, .other)
    }

    func testHttpStatuses() {
        XCTAssertNil(WebLoadFailure.http(status: 200))
        XCTAssertNil(WebLoadFailure.http(status: 304))
        XCTAssertEqual(WebLoadFailure.http(status: 404)?.kind, .http(404))
        XCTAssertTrue(WebLoadFailure.http(status: 503)!.message.contains("storing"))
    }

    func testBlockedHasNoRetry() {
        XCTAssertFalse(WebLoadFailure.blocked(reason: "x").canRetry)
    }
}
