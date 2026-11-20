import XCTest
@testable import MJOPEngine

final class PartyWallTests: XCTestCase {
    func sq(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> [[Double]] { [[x, y], [x + w, y], [x + w, y + h], [x, y + h]] }

    func testTerracedHouseSharesBothSideWalls() {
        let left = sq(-6, 0, 6, 10), right = sq(6, 0, 6, 10)
        // eigen huis: 0..6 × 0..10; zijwand rechts (x = 6) en links (x = 0)
        XCTAssertEqual(PartyWalls.sharedFraction(from: [6, 0], to: [6, 10], neighbours: [left, right]), 1)
        XCTAssertEqual(PartyWalls.sharedFraction(from: [0, 10], to: [0, 0], neighbours: [left, right]), 1)
        XCTAssertLessThan(PartyWalls.sharedFraction(from: [0, 0], to: [6, 0], neighbours: [left, right]), 0.2, "voorgevel vrij (alleen de hoeken raken de buren)")
    }

    func testCornerHouseAndSteppedRow() {
        let neighbour = sq(6, 0, 6, 10)
        XCTAssertEqual(PartyWalls.sharedFraction(from: [0, 10], to: [0, 0], neighbours: [neighbour]), 0, "hoekhuis: de kopgevel is vrij")
        let stepped = sq(6, 5, 6, 10)   // buurhuis 5 m naar achteren: half gedeeld
        XCTAssertEqual(PartyWalls.sharedFraction(from: [6, 0], to: [6, 10], neighbours: [stepped]), 0.55, accuracy: 0.03, "de helft plus de marge van 0,5 m")
        XCTAssertEqual(PartyWalls.sharedFraction(from: [6, 0], to: [6, 10], neighbours: [sq(8, 0, 6, 10)]), 0, "buurpand op 2 m")
        XCTAssertEqual(PartyWalls.sharedFraction(from: [6, 0], to: [6, 10], neighbours: [sq(6.3, 0, 6, 10)]), 1, "0,3 m verschil in de BAG: nog gedeeld")
    }

    func testAnnotateFromLonLat() {
        // Twee panden naast elkaar rond 52°N (ongeveer 6 m breed).
        let own: [[Double]] = [[5.0, 52.0], [5.0000879, 52.0], [5.0000879, 52.00009], [5.0, 52.00009], [5.0, 52.0]]
        let right: [(Double, Double)] = [(5.0000879, 52.0), (5.0001758, 52.0), (5.0001758, 52.00009), (5.0000879, 52.00009), (5.0000879, 52.0)]
        let sides = FootprintSides.sides(FootprintSides.meters(own.map { ($0[0], $0[1]) }))
        let a = PartyWalls.annotate(sides, ownRing: own, neighbours: [right])
        XCTAssertEqual(a.filter(\.isPartyWall).count, 1)
        XCTAssertEqual(a.filter { !$0.isPartyWall }.count, 3)
    }

    func testFramingHints() {
        XCTAssertNil(FramingHint.hint(quad: nil))
        XCTAssertEqual(FramingHint.hint(quad: [[0.01, 0.2], [0.8, 0.2], [0.8, 0.8], [0.01, 0.8]]), .tooWide)
        XCTAssertEqual(FramingHint.hint(quad: [[0.05, 0.2], [0.55, 0.2], [0.55, 0.8], [0.05, 0.8]]), .moveLeft)
        XCTAssertEqual(FramingHint.hint(quad: [[0.45, 0.2], [0.95, 0.2], [0.95, 0.8], [0.45, 0.8]]), .moveRight)
        XCTAssertNil(FramingHint.hint(quad: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]), "netjes in beeld: geen hint")
    }
}
