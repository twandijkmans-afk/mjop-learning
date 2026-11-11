import XCTest
@testable import Gevelscan
import PhotoWalkCore

/// Onderdeel A: fotokwaliteit, echte LiDAR vs. gewone foto, gevelvlak, actieve gevel, dekking.
final class CaptureTests: XCTestCase {
    let win = SynWindow(x0: 1.0, y0: 0.9, w: 1.2, h: 1.5, cols: 2)

    func checker(_ w: Int, _ h: Int, cell: Int) -> GrayImage {
        var px = [UInt8](repeating: 0, count: w * h)
        for y in 0..<h { for x in 0..<w { px[y * w + x] = ((x / cell + y / cell) % 2 == 0) ? 40 : 210 } }
        return GrayImage(width: w, height: h, pixels: px)
    }

    func testSharpnessSeparatesSharpFromBlurred() {
        let sharp = ImageQualityMeter.measure(checker(480, 360, cell: 6))
        // zelfde patroon, sterk vervaagd (gemiddelde over 9x9)
        let src = checker(480, 360, cell: 6)
        var blur = [UInt8](repeating: 0, count: 480 * 360)
        for y in 0..<360 { for x in 0..<480 {
            var s = 0, n = 0
            for dy in -4...4 { for dx in -4...4 { let xx = min(max(x + dx, 0), 479), yy = min(max(y + dy, 0), 359); s += Int(src.pixels[yy * 480 + xx]); n += 1 } }
            blur[y * 480 + x] = UInt8(s / n)
        } }
        let blurred = ImageQualityMeter.measure(GrayImage(width: 480, height: 360, pixels: blur))
        XCTAssertGreaterThan(sharp.sharpness, 20 * max(blurred.sharpness, 1))
        XCTAssertLessThan(blurred.sharpness, GevelscanConfig().minSharpness)
        XCTAssertGreaterThan(sharp.sharpness, GevelscanConfig().minSharpness)
    }

    func testOverexposureAndGlareInGlass() {
        var px = [UInt8](repeating: 100, count: 200 * 200)
        for y in 50..<150 { for x in 50..<150 { px[y * 200 + x] = 255 } }
        let img = GrayImage(width: 200, height: 200, pixels: px)
        XCTAssertEqual(ImageQualityMeter.measure(img).overexposedFraction, 0.25, accuracy: 0.02)
        let glass = [Pixel(50, 50), Pixel(150, 50), Pixel(150, 150), Pixel(50, 150)]
        XCTAssertGreaterThan(ImageQualityMeter.glareFraction(img, polygon: glass) ?? 0, 0.9)
        XCTAssertLessThan(ImageQualityMeter.glareFraction(img, polygon: [Pixel(0, 0), Pixel(40, 0), Pixel(40, 40), Pixel(0, 40)]) ?? 1, 0.05)
    }

    func testLidarPhotoIsMetricCapableAndPlainPhotoIsNot() {
        let lidar = Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F1"))
        let a = PhotoQualityRules.assess(lidar)
        XCTAssertEqual(lidar.depthSource, .LIDAR_SCENE_DEPTH)
        XCTAssertTrue(a.metricCapable, "\(a.flags)")
        XCTAssertNotNil(lidar.facadePlane)
        let plain = Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F2", withDepth: false))
        let b = PhotoQualityRules.assess(plain)
        XCTAssertEqual(plain.depthSource, .NONE)
        XCTAssertFalse(b.metricCapable)                       // een gewone foto geeft nooit een metrische meting
        XCTAssertTrue(b.flags.contains("GEEN_LIDAR"))
        XCTAssertNil(plain.facadePlane)                       // geen vlak uit alleen een foto
    }

    func testPoorTrackingBlurAndSparseDepthAreFlaggedWithRequests() {
        let limited = PhotoQualityRules.assess(Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F1", tracking: false)))
        XCTAssertFalse(limited.metricCapable); XCTAssertTrue(limited.flags.contains("TRACKING_BEPERKT"))
        let sparse = PhotoQualityRules.assess(Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F2", holeP: 0.8)))
        XCTAssertTrue(sparse.flags.contains("DIEPTE_ONVOLDOENDE")); XCTAssertTrue(sparse.requests.contains { $0.kind == .BETERE_DIEPTE })
        let blurry = PhotoQualityRules.assess(Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F3"), quality: ImageQuality(sharpness: 3, overexposedFraction: 0, underexposedFraction: 0, meanLuma: 15)))
        XCTAssertTrue(blurry.flags.contains("ONSCHERP")); XCTAssertTrue(blurry.flags.contains("TE_DONKER"))
        XCTAssertTrue(blurry.requests.contains { $0.kind == .SCHERPERE_FOTO })
        let far = PhotoQualityRules.assess(Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 9.0), id: "F4")))
        XCTAssertTrue(far.flags.contains("BUITEN_DIEPTEBEREIK")); XCTAssertFalse(far.metricCapable)
    }

    func testDominantPlaneIsTheWallAndFacesTheCamera() throws {
        let p = try XCTUnwrap(FacadePlaneEstimator.dominantVerticalPlane(view: Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F1", yawDeg: 15)))
        XCTAssertEqual(p.n.z, 1, accuracy: 0.03); XCTAssertEqual(p.d, 0, accuracy: 0.03)
    }

    func testActiveFacadeIsRecognizedOnlyWithinTheSameSessionAndNeverGuessed() {
        let front = Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "F1"), facade: "Voorgevel")
        let next = Syn.render([win], pos: Vec3(2.4, 1.6, 3.2), id: "F2", yawDeg: 8)
        let plane = FacadePlaneEstimator.dominantVerticalPlane(view: next)
        XCTAssertEqual(FacadeRecognizer.recognize(plane: plane, worldId: "W1", known: [front]), "Voorgevel")
        XCTAssertNil(FacadeRecognizer.recognize(plane: plane, worldId: "W2", known: [front]))         // andere AR-sessie: niet vergelijkbaar
        XCTAssertNil(FacadeRecognizer.recognize(plane: nil, worldId: "W1", known: [front]))           // geen vlak: geen gok
        var other = front; other.id = "F9"; other.facadeId = "Zijgevel"
        XCTAssertNil(FacadeRecognizer.recognize(plane: plane, worldId: "W1", known: [front, other]))  // twee gevels passen: dubbelzinnig
    }

    func testPhotoOnADifferentPlaneIsReportedNotSilentlyMoved() {
        var photos = (0..<3).map { Syn.photo(Syn.render([win], pos: Vec3(1.2 + 0.4 * Double($0), 1.6, 3.0), id: "F\($0)")) }
        var odd = Syn.photo(Syn.render([win], pos: Vec3(1.6, 1.6, 3.0), id: "FX"))
        odd.facadePlane = FacadePlaneEstimate(n: Vec3(1, 0, 0), d: 4, inlierRatio: 0.8, rmsM: 0.01)     // haaks vlak (zijgevel)
        photos.append(odd)
        XCTAssertEqual(FacadeRecognizer.mismatchedPhotos(photos), ["FX"])
        XCTAssertEqual(photos.first { $0.id == "FX" }?.facadeId, "Voorgevel")                            // indeling blijft zoals de gebruiker koos
    }

    func testCoverageGridShowsWhatIsCapturedAndFindsGaps() {
        let a = Syn.photo(Syn.render([win], pos: Vec3(1.0, 1.6, 3.0), id: "F1")), b = Syn.photo(Syn.render([win], pos: Vec3(2.2, 1.6, 3.0), id: "F2"))
        let c = FacadeCoverageRules.evaluate(facadeId: "Voorgevel", photos: [a, b])
        XCTAssertTrue(c.determinable); XCTAssertEqual(c.photosUsed, 2)
        XCTAssertEqual(c.coveredFraction ?? 0, 1, accuracy: 0.02)
        XCTAssertGreaterThan(c.multiViewFraction ?? 0, 0.4)
        XCTAssertEqual(c.cellViews.count, c.columns * c.rows)
        XCTAssertEqual(c.heightM ?? 0, 2 * 3.0 * 720 / 1500, accuracy: 0.1)
        // twee foto's ver uit elkaar: er zit een niet-gefotografeerd stuk tussen
        let far = Syn.photo(Syn.render([win], pos: Vec3(9.0, 1.6, 3.0), id: "F3"))
        let gap = FacadeCoverageRules.evaluate(facadeId: "Voorgevel", photos: [a, far])
        XCTAssertTrue(gap.flags.contains("GATEN_IN_DEKKING")); XCTAssertLessThan(gap.coveredFraction ?? 1, 0.85)
        // zonder LiDAR-vlak is de dekking ONBEKEND, niet "volledig"
        let none = FacadeCoverageRules.evaluate(facadeId: "Voorgevel", photos: [Syn.photo(Syn.render([win], pos: Vec3(1, 1.6, 3), id: "F4", withDepth: false))])
        XCTAssertFalse(none.determinable); XCTAssertNil(none.coveredFraction); XCTAssertTrue(none.flags.contains("DEKKING_ONBEKEND"))
    }

    func testTruncationAndWorldDownBorder() {
        XCTAssertEqual(DetectionGeometry.truncatedSides([Pixel(100, 900), Pixel(600, 900), Pixel(600, 1438), Pixel(100, 1438)], width: 1920, height: 1440, marginPx: 6), [.BOTTOM])
        XCTAssertEqual(DetectionGeometry.truncatedSides([Pixel(100, 100), Pixel(600, 100), Pixel(600, 700), Pixel(100, 700)], width: 1920, height: 1440, marginPx: 6), [])
        XCTAssertEqual(DetectionGeometry.worldDownBorder(pose: Syn.pose(Vec3(0, 1.6, 3))), .BOTTOM)
        // telefoon rechtop gehouden: het sensorbeeld is een kwartslag gedraaid, "onder" is dan een zijrand
        let rolled = Pose(rows: [Vec3(0, 1, 0), Vec3(1, 0, 0), Vec3(0, 0, -1)], t: Vec3(0, 1.6, 3))
        XCTAssertTrue([.LEFT, .RIGHT].contains(DetectionGeometry.worldDownBorder(pose: rolled)))
    }
}
