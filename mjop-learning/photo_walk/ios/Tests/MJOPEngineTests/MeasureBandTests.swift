import XCTest
@testable import MJOPEngine

final class MeasureBandTests: XCTestCase {
    func testBestCase() {
        let r = MeasureBand.relative(.init(widthSource: .bag, levelAtCapture: true, focalSource: .exif, rectified: true))
        XCTAssertEqual(r, sqrt(0.03 * 0.03 + 0.01 * 0.01 + 0.01 * 0.01), accuracy: 1e-12)
        XCTAssertEqual(MeasureBand.band(52, relative: r, area: true), 52 * 2 * r, accuracy: 1e-12)
        XCTAssertEqual(MeasureBand.band(6, relative: r, area: false), 6 * r, accuracy: 1e-12)
    }

    func testEachSourceMakesItWider() {
        let base = MeasureBand.relative(.init(widthSource: .bag, levelAtCapture: true, focalSource: .exif, rectified: true))
        XCTAssertGreaterThan(MeasureBand.relative(.init(widthSource: .deurAanname, levelAtCapture: true, focalSource: .exif, rectified: true)), base)
        XCTAssertGreaterThan(MeasureBand.relative(.init(widthSource: .bag, levelAtCapture: false, focalSource: .exif, rectified: true)), base)
        XCTAssertGreaterThan(MeasureBand.relative(.init(widthSource: .bag, levelAtCapture: true, focalSource: nil, rectified: false)), base)
        XCTAssertGreaterThan(MeasureBand.relative(.init(widthSource: .bag, levelAtCapture: true, focalSource: .exif, rectified: true, hiddenFraction: 0.4)), base)
    }

    func testDoorCheck() {
        XCTAssertEqual(MeasureBand.doorCheck(2.15), .ok)
        XCTAssertEqual(MeasureBand.doorCheck(1.7), .tooLow)
        XCTAssertEqual(MeasureBand.doorCheck(2.8), .tooHigh)
    }
}
