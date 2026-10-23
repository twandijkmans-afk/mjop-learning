import XCTest
@testable import MJOPIntegration

final class DownloadNamingTests: XCTestCase {
    func testSanitizesPathsAndControlChars() {
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: "../../etc/passwd"), "passwd")
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: "a\\b\\mjop.csv"), "mjop.csv")
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: ".hidden"), "hidden")
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: "mjop:<x>|y?.csv"), "mjopxy.csv")
    }
    func testDefaultsAndExtensions() {
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: nil, mimeType: "text/csv"), "mjop-export.csv")
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: "   ", mimeType: "application/pdf; charset=x"), "mjop-export.pdf")
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: "rapport", mimeType: "application/pdf"), "rapport.pdf")
        XCTAssertEqual(DownloadNaming.safeFileName(suggested: "mjop-live-mijn-gegevens.json"), "mjop-live-mijn-gegevens.json")
    }
    func testLengthLimit() {
        XCTAssertLessThanOrEqual(DownloadNaming.safeFileName(suggested: String(repeating: "a", count: 500) + ".csv").count, 100)
    }
}
