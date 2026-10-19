import XCTest
@testable import PhotoWalkCore

/// Regressietests: zoom/pan/schermformaat/oriëntatie mogen de teruggerekende originele pixels en dus de metrische uitkomst NIET veranderen.
final class ZoomTests: XCTestCase {
    private let W = 1920.0, H = 1440.0
    private func vt(_ vw: Double = 393, _ vh: Double = 700, _ o: DisplayOrientation = .right) -> ViewportTransform {
        ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: o, viewportWidth: vw, viewportHeight: vh)
    }
    private func close(_ a: Pixel, _ b: Pixel, _ tol: Double = 1e-9, _ msg: String = "", file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(a.u, b.u, accuracy: tol, msg, file: file, line: line); XCTAssertEqual(a.v, b.v, accuracy: tol, msg, file: file, line: line)
    }

    // 4 + 10: omzetting naar originele pixels, oriëntatie, geen uitsnede
    func testOrientationRightMapsNativeCornersToPortraitCorners() {
        var t = vt(); t.reset()
        let tl = t.viewPoint(fromNative: Pixel(0, 0)), br = t.viewPoint(fromNative: Pixel(W, H))
        XCTAssertGreaterThan(tl.u, br.u, "native linksboven staat bij .right rechtsboven in het getoonde (portret)beeld")
        XCTAssertLessThan(tl.v, br.v)
        close(t.nativePoint(fromView: tl), Pixel(0, 0), 1e-9)
        close(t.nativePoint(fromView: br), Pixel(W, H), 1e-9)
        // beeld past volledig, niet afgesneden
        XCTAssertLessThanOrEqual(t.contentWidth, 393 + 1e-9); XCTAssertLessThanOrEqual(t.contentHeight, 700 + 1e-9)
    }

    func testOrientationUpIsIdentityOnDisplay() {
        let t = vt(400, 300, .up)
        close(t.displayPoint(fromNative: Pixel(10, 20)), Pixel(10, 20))
        XCTAssertEqual(t.displayWidth, W); XCTAssertEqual(vt().displayWidth, H)
    }

    func testRoundTripAtManyZoomsAndPans() {
        var t = vt()
        let pts = [Pixel(0, 0), Pixel(W, H), Pixel(960, 720), Pixel(123.456, 1300.5), Pixel(1800, 40)]
        for z in [1.0, 1.7, 2.0, 4.0, 8.0] {
            t.reset(); t.setZoom(z, anchor: Pixel(200, 350))
            for (dx, dy) in [(0.0, 0.0), (35.0, -20.0), (-300.0, 400.0)] {
                t.pan(byX: dx, y: dy)
                for p in pts { close(t.nativePoint(fromView: t.viewPoint(fromNative: p)), p, 1e-7, "zoom \(z)") }
            }
        }
    }

    // 1 + 2 + 3: dezelfde fysieke hoek op 1x, 2x, 4x en na pannen geeft dezelfde native pixel
    func testSamePhysicalCornerAtDifferentZoomsAndAfterPanning() {
        let corner = Pixel(1180.25, 417.5)
        var results: [Pixel] = []
        for z in [1.0, 2.0, 4.0, 4.0] {
            var t = vt(); t.setZoom(z, anchor: Pixel(196, 350))
            if z == 4.0 && results.count == 3 { t.pan(byX: -120, y: 80) }        // pannen en daarna selecteren
            let tapAt = t.viewPoint(fromNative: corner)                          // waar de gebruiker fysiek tikt
            results.append(t.nativePoint(fromView: tapAt))
        }
        for r in results { close(r, corner, 1e-9) }
    }

    func testZoomKeepsAnchorPointFixed() {
        var t = vt()
        let anchor = Pixel(300, 200)
        let before = t.nativePoint(fromView: anchor)
        t.zoom(by: 3, anchor: anchor)
        close(t.nativePoint(fromView: anchor), before, 1e-9)
        XCTAssertEqual(t.zoom, 3, accuracy: 1e-12)
        t.zoom(by: 100, anchor: anchor); XCTAssertEqual(t.zoom, ViewportTransform.maxZoom)
        t.zoom(by: 1e-9, anchor: anchor); XCTAssertEqual(t.zoom, ViewportTransform.minZoom)
        XCTAssertGreaterThanOrEqual(ViewportTransform.maxZoom, 4)
    }

    func testPanIsClampedButEdgeCornersStayReachable() {
        var t = vt(); t.setZoom(4, anchor: Pixel(196, 350))
        t.pan(byX: 1e6, y: 1e6)
        // de hoek linksboven van het getoonde beeld moet dan met enige marge in de weergave kunnen komen
        let topLeftDisplayOnScreen = Pixel(t.contentOriginX, t.contentOriginY)
        XCTAssertLessThanOrEqual(topLeftDisplayOnScreen.u, t.edgeMargin + 1e-9)
        XCTAssertLessThanOrEqual(topLeftDisplayOnScreen.v, t.edgeMargin + 1e-9)
        t.pan(byX: -1e6, y: -1e6)
        XCTAssertGreaterThanOrEqual(t.contentOriginX + t.contentWidth, 393 - t.edgeMargin - 1e-9)
        t.reset(); t.pan(byX: 500, y: 500)
        XCTAssertEqual(t.panX, 0); XCTAssertEqual(t.panY, 0, "bij zoom 1 past het beeld; geen pan")
    }

    func testDoubleTapResetRestoresFit() {
        var t = vt(); let fit = t
        t.setZoom(5, anchor: Pixel(100, 100)); t.pan(byX: 50, y: 50); t.reset()
        XCTAssertEqual(t, fit)
    }

    // 9: verschillende schermformaten
    func testDifferentScreenSizesGiveConsistentNativeCoordinates() {
        let corner = Pixel(700.5, 900.25)
        for (vw, vh) in [(375.0, 600.0), (390.0, 700.0), (430.0, 850.0), (744.0, 1000.0), (320.0, 480.0)] {
            for z in [1.0, 2.0, 4.0] {
                var t = vt(vw, vh); t.setZoom(z, anchor: Pixel(vw / 2, vh / 2))
                close(t.nativePoint(fromView: t.viewPoint(fromNative: corner)), corner, 1e-9, "\(vw)x\(vh) zoom \(z)")
            }
        }
        // resize / rotatie van het scherm: zelfde native punt blijft terug te rekenen
        var t = vt(); t.setZoom(2, anchor: Pixel(196, 350)); t.setViewport(width: 700, height: 393)
        close(t.nativePoint(fromView: t.viewPoint(fromNative: corner)), corner, 1e-9)
    }

    func testPointingPrecisionImprovesWithZoom() {
        var t = vt(); let p1 = t.nativePixelsPerPoint
        t.setZoom(4, anchor: Pixel(196, 350))
        XCTAssertEqual(t.nativePixelsPerPoint, p1 / 4, accuracy: 1e-9)
    }

    // 5 + 6 + 7 + 8: zoom verandert de metrische uitkomst niet; intrinsics en dieptedata blijven ongemoeid
    private func fixture() throws -> (ViewInput, [Pixel], [Pixel], Intrinsics) {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        let c = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        func d(_ x: Any?) -> Double { (x as! NSNumber).doubleValue }
        let i = c["intrinsics"] as! [String: Any], a = c["level_a"] as! [String: Any], l = c["level_c"] as! [String: Any]
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        let depth = DepthMap(width: 64, height: 48, values: (a["depth"] as! [Any]).map { Float(d($0)) == 0 ? Float.nan : Float(d($0)) })
        let v = ViewInput(frameId: "F", intrinsics: intr, pose: Pose(rowMajor: (c["pose_row_major"] as! [Any]).map { d($0) }), trackingNormal: true, depth: depth)
        return (v, (a["corners_px"] as! [[Double]]).map { Pixel($0[0], $0[1]) }, (l["anchor_px"] as! [[Double]]).map { Pixel($0[0], $0[1]) }, intr)
    }

    private func tapped(_ truth: [Pixel], zoom: Double, pan: (Double, Double)) -> [Pixel] {
        var t = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 393, viewportHeight: 700)
        t.setZoom(zoom, anchor: Pixel(250, 300)); t.pan(byX: pan.0, y: pan.1)
        return truth.map { t.nativePoint(fromView: t.viewPoint(fromNative: $0)) }
    }

    func testZoomDoesNotChangeMetricResultsLevelA() throws {
        let (v, corners, _, intr) = try fixture()
        let depthBefore = v.depth!.values
        let base = measureDepthView(v, corners: corners, seed: 1)
        XCTAssertTrue(base.ok)
        for (z, p) in [(1.0, (0.0, 0.0)), (2.0, (30.0, -40.0)), (4.0, (-90.0, 60.0)), (8.0, (0.0, 0.0))] {
            let r = measureDepthView(v, corners: tapped(corners, zoom: z, pan: p), seed: 1)
            XCTAssertEqual(r.width!, base.width!, accuracy: 1e-6, "breedte bij zoom \(z)")
            XCTAssertEqual(r.height!, base.height!, accuracy: 1e-6)
            let a0 = roundedMillimeters(base.width!) * roundedMillimeters(base.height!), a1 = roundedMillimeters(r.width!) * roundedMillimeters(r.height!)
            XCTAssertEqual(a0, a1, "bruto m2 mag niet door zoom veranderen")
        }
        XCTAssertEqual(v.depth!.values, depthBefore, "LiDAR-dieptedata blijft ongewijzigd")
        XCTAssertEqual(v.intrinsics, intr, "intrinsics blijven ongewijzigd")
    }

    func testZoomDoesNotChangeReferenceMeasurement() throws {
        var (v, corners, anchor, _) = try fixture()
        v.depth = nil
        func run(_ z: Double, _ p: (Double, Double)) -> LevelResult {
            let a = tapped(anchor, zoom: z, pan: p), c = tapped(corners, zoom: z, pan: p)
            let ref = ReferenceMeasure(referenceId: "R", p1: a[0], p2: a[1], distanceM: 1.2, distanceSigmaM: 0.005, planeId: "P")
            return measureWithReference(view: v, target: c, ref: ref, anchor: a, seed: 1)
        }
        let base = run(1, (0, 0))
        XCTAssertTrue(base.ok)
        for (z, p) in [(2.0, (10.0, 20.0)), (4.0, (-70.0, 30.0))] {
            let r = run(z, p)
            XCTAssertEqual(r.width!, base.width!, accuracy: 1e-6); XCTAssertEqual(r.height!, base.height!, accuracy: 1e-6)
        }
    }

    func testCornerCorrectionOnZoomedImageUsesNativePixels() throws {
        let (v, corners, _, _) = try fixture()
        var t = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 393, viewportHeight: 700)
        t.setZoom(4, anchor: Pixel(200, 300)); t.pan(byX: -50, y: 20)
        // een misgeklikte hoek 18 punten verderop wordt op de ingezoomde weergave naar de juiste plek gesleept
        var wrong = corners; let wrongView = t.viewPoint(fromNative: corners[2]); wrong[2] = t.nativePoint(fromView: Pixel(wrongView.u + 18, wrongView.v - 11))
        let fixed = (0..<4).map { $0 == 2 ? t.nativePoint(fromView: t.viewPoint(fromNative: corners[2])) : wrong[$0] }
        let r = measureDepthView(v, corners: fixed, seed: 1), base = measureDepthView(v, corners: corners, seed: 1)
        XCTAssertEqual(r.width!, base.width!, accuracy: 1e-6); XCTAssertEqual(r.height!, base.height!, accuracy: 1e-6)
    }

    /// Zoom verbetert de metrische uitkomst NIET zelf; hij maakt alleen preciezer aanwijzen mogelijk (zelfde vingerfout = kleinere pixelfout).
    func testSameFingerJitterGivesSmallerNativeErrorWhenZoomedIn() throws {
        let (v, corners, _, _) = try fixture()
        let jitter = [(1.2, -0.8), (-0.9, 1.1), (0.7, 0.9), (-1.0, -1.3)]       // vaste vingerfout in schermpunten
        func err(_ z: Double) -> (Double, Double) {
            var t = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 393, viewportHeight: 700)
            t.setZoom(z, anchor: Pixel(196, 350))
            let noisy = corners.enumerated().map { (i, c) -> Pixel in
                let vp = t.viewPoint(fromNative: c); return t.nativePoint(fromView: Pixel(vp.u + jitter[i].0, vp.v + jitter[i].1))
            }
            let maxPix = zip(noisy, corners).map { hypot($0.u - $1.u, $0.v - $1.v) }.max()!
            let r = measureDepthView(v, corners: noisy, seed: 1), b = measureDepthView(v, corners: corners, seed: 1)
            return (maxPix, abs((r.width ?? 0) * (r.height ?? 0) - b.width! * b.height!))
        }
        let e1 = err(1), e4 = err(4)
        XCTAssertLessThan(e4.0, e1.0 / 3.9, "pixelfout bij 4x moet ca. 4x kleiner zijn")
        XCTAssertLessThan(e4.1, e1.1, "oppervlaktefout door vingerfout moet bij 4x kleiner zijn")
    }
}
