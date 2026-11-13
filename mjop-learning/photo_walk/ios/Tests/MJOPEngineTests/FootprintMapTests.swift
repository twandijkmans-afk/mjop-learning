import XCTest
@testable import MJOPEngine

final class FootprintMapTests: XCTestCase {
    func testMetersRoundTrip() {
        let origin = [5.06698, 52.33004]
        let ll = FootprintMap.lonLat(meters: [8.49, -3.2], origin: origin)
        let back = FootprintSides.meters([(origin[0], origin[1]), (ll[0], ll[1])])[1]
        XCTAssertEqual(back[0], 8.49, accuracy: 1e-6)
        XCTAssertEqual(back[1], -3.2, accuracy: 1e-6)
    }

    func testFrameKeepsAspectAndPutsTheBuildingInside() throws {
        let ring = [[5.0670, 52.3300], [5.0672, 52.3300], [5.0672, 52.3301], [5.0670, 52.3301], [5.0670, 52.3300]]
        let f = try XCTUnwrap(FootprintMap.frame(ring: ring, aspect: 1.5, marginM: 15))
        XCTAssertEqual((f.maxX - f.minX) / (f.maxY - f.minY), 1.5, accuracy: 1e-9)
        for p in ring {
            let px = f.pixel(p, w: 600, h: 400)
            XCTAssertTrue((0...600).contains(px[0]) && (0...400).contains(px[1]))
        }
        XCTAssertLessThan(f.pixel(ring[2], w: 600, h: 400)[1], f.pixel(ring[0], w: 600, h: 400)[1], "noord is boven")
    }

    func testStandpointIsOutsideInFrontOfTheMiddle() {
        // Vierkant 10 × 10 m, tegen de klok in; zuidzijde van (0,0) naar (10,0).
        let ring = [[0.0, 0.0], [10, 0], [10, 10], [0, 10]]
        let s = FootprintMap.standpoint(from: [0, 0], to: [10, 0], ringM: ring)
        XCTAssertEqual(s.point[0], 5, accuracy: 1e-9)
        XCTAssertLessThan(s.point[1], 0, "voor de gevel, buiten het gebouw")
        XCTAssertEqual(s.distanceM, 5 / tan(42.5 * .pi / 180) * 1.15, accuracy: 1e-9)
        XCTAssertGreaterThan(FootprintMap.standpoint(from: [0, 0], to: [10, 0], ringM: ring, ultraWide: false).distanceM, s.distanceM, "met 1× verder weg")
        // Zelfde zijde, omtrek met de klok mee: nog steeds naar buiten.
        XCTAssertLessThan(FootprintMap.standpoint(from: [10, 0], to: [0, 0], ringM: Array(ring.reversed())).point[1], 0)
    }

    func testSidesCarryTheirEndpoints() throws {
        let sides = FootprintSides.sides([[0, 0], [10, 0], [10, 6], [0, 6], [0, 0]])
        XCTAssertEqual(sides.count, 4)
        XCTAssertEqual(try XCTUnwrap(sides.first?.from), [0, 0])
        XCTAssertEqual(try XCTUnwrap(sides.first?.to), [10, 0])
    }
}
