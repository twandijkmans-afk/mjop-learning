import XCTest
@testable import PhotoWalkCore

final class FeedbackTests: XCTestCase {
    private func result(_ codes: [String], width: Double? = 1.2) -> LevelResult {
        var r = LevelResult(level: .A, scaleMethod: "LIDAR_DEPTH_PLANE")
        r.width = width; r.height = width.map { $0 * 1.25 }
        r.flags = codes.map { Flags.make($0) }
        return r
    }

    func testGreenOnlyForUsableMeasurementWithoutReviewWarnings() {
        XCTAssertEqual(Feedback.classify(result([])), .green)
        XCTAssertEqual(Feedback.classify(result(["SINGLE_VIEWPOINT", "MANUAL_CORNERS"])), .green)
        XCTAssertEqual(Feedback.classify(result(["GLASS_DEPTH_UNRELIABLE"])), .orange)
        XCTAssertEqual(Feedback.classify(result(["COPLANARITY_ASSUMED"])), .orange)
    }

    func testNeutralWithoutScaleAndOrangeForGeometryDoubts() {
        for c in ["NO_DEPTH", "TRACKING_LOST", "DEPTH_COVERAGE_LOW", "NO_METRIC_SCALE"] { XCTAssertEqual(Feedback.classify(result([c], width: nil)), .neutral, c) }
        for c in ["WRONG_CORNER_SELECTION", "MIXED_FACADE_DEPTH", "OBLIQUE_ANGLE", "CORNER_ORDER_INVALID"] { XCTAssertEqual(Feedback.classify(result([c], width: nil)), .orange, c) }
        XCTAssertEqual(Feedback.classify(result([], width: nil)), .neutral, "geen waarde en geen reden: neutraal, nooit groen")
        // een resultaat zonder maat is nooit groen, ook niet zonder blokkades
        XCTAssertNotEqual(Feedback.classify(result([], width: nil)), .green)
    }

    func testUnknownNeverCarriesMeasuredDimensions() {
        let r = result(["NO_DEPTH"], width: nil)
        let o = makeObject(id: "P", observations: [], result: r, viewCount: 1)
        XCTAssertEqual(o.status, .UNKNOWN); XCTAssertNil(o.widthM); XCTAssertNil(o.areaM2)
    }

    private func item(_ id: String, _ f: String, _ x: Double, w: Double = 1.2, h: Double = 1.5, d: Double = 0) -> LinkItem {
        LinkItem(id: id, frameId: f, center: Vec3(x, 1.6, 0), planeN: Vec3(0, 0, 1), planeD: d, width: w, height: h)
    }

    func testLinkSuggestionsOnlyForSamePlaneNearbySimilarSizeAndOtherPhoto() {
        let s = Linking.suggest([item("a", "F0", 1.6), item("b", "F1", 1.65), item("c", "F1", 3.8), item("d", "F0", 3.8, w: 2.4)])
        XCTAssertEqual(s.map { [$0.a, $0.b] }, [["a", "b"]], "c is te ver weg, d heeft een andere maat")
        XCTAssertTrue(Linking.suggest([item("a", "F0", 1.6), item("b", "F0", 1.62)]).isEmpty, "zelfde foto: nooit koppelen")
        XCTAssertTrue(Linking.suggest([item("a", "F0", 1.6), item("b", "F1", 1.6, d: 0.5)]).isEmpty, "ander vlak")
    }

    func testAmbiguousLinkIsNotSuggested() {
        let s = Linking.suggest([item("a", "F0", 1.6), item("b", "F1", 1.5), item("c", "F1", 1.72)])
        XCTAssertTrue(s.isEmpty)
    }

    func testViewportFitShowsWholeBoxAndRoundTripsNativePixels() {
        var t = ViewportTransform(nativeWidth: 1920, nativeHeight: 1440, orientation: .right, viewportWidth: 393, viewportHeight: 500)
        let box = [Pixel(700, 400), Pixel(1100, 400), Pixel(1100, 900), Pixel(700, 900)]
        t.fit(native: box)
        XCTAssertGreaterThan(t.zoom, 1)
        for p in box {
            let v = t.viewPoint(fromNative: p)
            XCTAssertTrue(v.u > 0 && v.u < 393 && v.v > 0 && v.v < 500, "hoek binnen de weergave")
            let b = t.nativePoint(fromView: v); XCTAssertEqual(b.u, p.u, accuracy: 1e-7); XCTAssertEqual(b.v, p.v, accuracy: 1e-7)
        }
        var tiny = ViewportTransform(nativeWidth: 1920, nativeHeight: 1440, orientation: .right, viewportWidth: 393, viewportHeight: 500)
        tiny.fit(native: [Pixel(900, 700), Pixel(910, 700), Pixel(910, 710), Pixel(900, 710)])
        XCTAssertEqual(tiny.zoom, ViewportTransform.maxZoom, "kleine kozijnen: maximaal inzoomen")
    }
}
