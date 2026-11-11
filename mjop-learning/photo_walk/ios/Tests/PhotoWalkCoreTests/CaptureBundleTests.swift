import XCTest
@testable import PhotoWalkCore

/// Ontwikkelbundel: roundtrip/replay, integriteit, privacy, verwijdering en uitsluiting van back-ups. Er staan GEEN foto's of bundels in de repository.
final class CaptureBundleTests: XCTestCase {
    let cfg = Config()
    var root: URL!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("bundle_tests_\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }
    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: root) }

    private func scene(recess: Double = 0, supports: Int = 0, pos: Vec3 = Vec3(1.6, 1.6, 3.0), yaw: Double = 0) -> (ViewInput, [Pixel]) {
        var s = SceneSpec(); s.recess = recess
        var v = Scene.render(s, pos: pos, id: "CAP", seed: 1, yawDeg: yaw)
        for k in 0..<supports {
            let off = 0.06 * Double(k / 2 + 1) * (k % 2 == 0 ? 1 : -1)
            v.supports.append(Scene.render(s, pos: Vec3(pos.x + off, pos.y, pos.z), id: "S\(k)", seed: 8 + UInt64(k), yawDeg: yaw))
        }
        return (v, Scene.corners(s, pos: pos))
    }

    private func write(_ v: ViewInput, _ c: [Pixel], photo: Data? = nil) throws -> URL {
        try CaptureBundle.write(root: root, view: v, corners: c, sessionId: "S-1", observationId: "OBS-1", appBuild: "test", thresholds: ["a": 1.0], photo: photo, createdUTC: "2026-01-01T00:00:00Z")
    }

    func testRoundTripReplayEqualsOriginal() throws {
        let cases: [(String, Double, Int, Vec3, Double)] = [("flat", 0, 0, Vec3(1.6, 1.6, 3.0), 0), ("recess6", 0.06, 3, Vec3(1.6, 1.6, 3.0), 0),
                                                            ("oblique25", 0, 0, Vec3(1.6 + 3.0 * tan(25 * Double.pi / 180), 1.6, 3.0), 25), ("limited", 0, 0, Vec3(1.6, 1.65, 1.75), 0)]
        for (name, rec, sup, pos, yaw) in cases {
            let (v, c) = scene(recess: rec, supports: sup, pos: pos, yaw: yaw)
            let r0 = measureDepthView(v, corners: c, cfg: cfg, seed: 1)
            let dir = try write(v, c)
            let back = try CaptureBundle.read(dir)
            let r1 = measureDepthView(back.view, corners: back.corners, cfg: cfg, seed: 1)
            XCTAssertEqual(r0.ok, r1.ok, name)
            XCTAssertEqual(r0.flags.map { $0.code }, r1.flags.map { $0.code }, name)
            XCTAssertEqual(r0.scaleMethod, r1.scaleMethod, name)
            XCTAssertEqual(r0.independentFrames, r1.independentFrames, name)
            if let a = r0.width, let b = r1.width { XCTAssertEqual(a, b, accuracy: 1e-4, name) } else { XCTAssertEqual(r0.width == nil, r1.width == nil, name) }
            if let a = r0.height, let b = r1.height { XCTAssertEqual(a, b, accuracy: 1e-4, name) } else { XCTAssertEqual(r0.height == nil, r1.height == nil, name) }
            try CaptureBundle.delete(dir)
        }
    }

    func testManifestHasNoAbsolutePoseOrLocation() throws {
        let (v, c) = scene(recess: 0.06, supports: 2)
        let dir = try write(v, c)
        let m = try CaptureBundle.read(dir).manifest
        var keys: [String] = []
        func walk(_ o: Any) {
            if let d = o as? [String: Any] { for (k, x) in d { keys.append(k); walk(x) } } else if let a = o as? [Any] { a.forEach(walk) }
        }
        walk(m.filter { $0.key != "privacy" })
        let bad = keys.filter { k in ["latitude", "longitude", "gps", "location", "compass", "heading", "address", "adres", "user", "world_pose", "absolute"].contains { k.lowercased().contains($0) } }
        XCTAssertTrue(bad.isEmpty, "\(bad)")
        let cap = (m["frames"] as! [[String: Any]]).first { $0["role"] as? String == "CAPTURE" }!
        XCTAssertEqual((cap["translation_rel_m"] as! [Double]).map { abs($0) }.max()!, 0, accuracy: 1e-12)
        XCTAssertEqual((cap["rotation_rel_row_major"] as! [Double]), [1, 0, 0, 0, 1, 0, 0, 0, 1])
        let p = m["privacy"] as! [String: Any]
        XCTAssertEqual(p["dev_mode_only"] as? Bool, true); XCTAssertEqual(p["local_only"] as? Bool, true)
        XCTAssertEqual(p["absolute_pose_included"] as? Bool, false); XCTAssertEqual(p["location_included"] as? Bool, false); XCTAssertEqual(p["full_photo_included"] as? Bool, false)
    }

    func testTamperingIsDetected() throws {
        let (v, c) = scene()
        let dir = try write(v, c)
        let f = dir.appendingPathComponent("depth_CAP.f32")
        var d = try Data(contentsOf: f); d[0] ^= 0xFF; try d.write(to: f)
        XCTAssertThrowsError(try CaptureBundle.read(dir))
    }

    func testPhotoIsOptionalAndFlagged() throws {
        let (v, c) = scene()
        let dir = try write(v, c, photo: Data([0xFF, 0xD8, 1, 2, 3]))
        let m = try CaptureBundle.read(dir).manifest
        XCTAssertEqual((m["privacy"] as! [String: Any])["full_photo_included"] as? Bool, true)
        XCTAssertTrue((m["files"] as! [[String: Any]]).contains { $0["kind"] as? String == "PHOTO_FULL_RESOLUTION" })
    }

    func testDeleteRemovesEverythingAndOnlyBundles() throws {
        let (v, c) = scene(recess: 0.06, supports: 2)
        let dir = try write(v, c, photo: Data([1]))
        let keep = root.appendingPathComponent("keep.txt"); try Data("x".utf8).write(to: keep)
        XCTAssertEqual(CaptureBundle.list(root: root).count, 1)
        XCTAssertEqual(CaptureBundle.deleteAll(root: root), 1)
        XCTAssertFalse(FileManager.default.fileExists(atPath: dir.path))
        XCTAssertTrue(FileManager.default.fileExists(atPath: keep.path))
        XCTAssertThrowsError(try CaptureBundle.delete(root))
    }

    func testBundleIsExcludedFromBackup() throws {
        let (v, c) = scene()
        let dir = try write(v, c)
        XCTAssertTrue(CaptureBundle.isExcludedFromBackup(dir))
    }
}
