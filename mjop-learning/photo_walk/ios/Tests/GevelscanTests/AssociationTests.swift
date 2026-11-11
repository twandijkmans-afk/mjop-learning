import XCTest
@testable import Gevelscan
import PhotoWalkCore

/// Onderdeel C: hetzelfde kozijn op meerdere foto's is één object; onzeker of niet-vergelijkbaar wordt nooit stil opgelost.
final class AssociationTests: XCTestCase {
    let a = SynWindow(x0: 0.6, y0: 0.9, w: 1.2, h: 1.5, cols: 2)
    let b = SynWindow(x0: 2.7, y0: 0.9, w: 1.2, h: 1.5, cols: 2)       // zelfde maat, 0,9 m ernaast
    lazy var v1 = Syn.render([a, b], pos: Vec3(1.6, 1.6, 3.6), id: "F1", seed: 1)
    lazy var v2 = Syn.render([a, b], pos: Vec3(2.6, 1.6, 3.6), id: "F2", seed: 2, yawDeg: 6)
    lazy var v3 = Syn.render([a, b], pos: Vec3(2.1, 1.7, 3.3), id: "F3", seed: 3, yawDeg: -4)

    func testSameWindowOnTwoPhotosIsOneObjectAndNeighboursStayApart() {
        let s = [Syn.sighting(a, view: v1, id: "OBS-F1-01"), Syn.sighting(b, view: v1, id: "OBS-F1-02"), Syn.sighting(a, view: v2, id: "OBS-F2-01"), Syn.sighting(b, view: v2, id: "OBS-F2-02")]
        for x in s { XCTAssertTrue(x.result?.ok == true, "\(x.id): \(codes(x.result))") }
        let r = ObjectAssociator.associate(s, roundId: "ROUND-0001")
        XCTAssertEqual(r.objects.count, 2)                                   // 4 waarnemingen, 2 kozijnen: niet dubbel geteld
        XCTAssertEqual(Set(r.objects.map { Set($0.sightingIds) }), [["OBS-F1-01", "OBS-F2-01"], ["OBS-F1-02", "OBS-F2-02"]])
        XCTAssertTrue(r.objects.allSatisfy { $0.identity == .RESOLVED && $0.photoIds == ["F1", "F2"] })
        XCTAssertEqual(r.decisions.filter { $0.kind == .SAME_STRONG }.count, 2)
        XCTAssertTrue(r.decisions.filter { $0.kind == .SAME_STRONG }.allSatisfy { ($0.iou ?? 0) > 0.8 })
    }

    func testIdsAreStableWhenPhotosAreAddedAndIndependentOfInputOrder() {
        let s2 = [Syn.sighting(a, view: v1, id: "OBS-F1-01"), Syn.sighting(b, view: v1, id: "OBS-F1-02"), Syn.sighting(a, view: v2, id: "OBS-F2-01"), Syn.sighting(b, view: v2, id: "OBS-F2-02")]
        let s3 = s2 + [Syn.sighting(a, view: v3, id: "OBS-F3-01"), Syn.sighting(b, view: v3, id: "OBS-F3-02")]
        let r2 = ObjectAssociator.associate(s2, roundId: "ROUND-0001"), r3 = ObjectAssociator.associate(s3, roundId: "ROUND-0001")
        XCTAssertEqual(r2.objects.map { $0.id }, r3.objects.map { $0.id })   // een derde foto verandert de object-id's niet
        XCTAssertEqual(r3.objects.map { $0.sightingIds.count }, [3, 3])
        XCTAssertEqual(ObjectAssociator.associate(s3.reversed(), roundId: "ROUND-0001"), r3)     // reproduceerbaar
        XCTAssertNotEqual(ObjectAssociator.associate(s3, roundId: "ROUND-0002").objects.map { $0.id }, r3.objects.map { $0.id })
        XCTAssertTrue(r3.objects.allSatisfy { $0.id.hasPrefix("GO-") && $0.id.count == 11 })
    }

    func testPhotosFromDifferentSessionsAreNotComparedAndNotCountedAsDistinct() {
        let s = [Syn.sighting(a, view: v1, id: "OBS-F1-01", world: "W1"), Syn.sighting(a, view: v2, id: "OBS-F2-01", world: "W2")]
        let r = ObjectAssociator.associate(s, roundId: "ROUND-0001")
        XCTAssertEqual(r.objects.count, 2)
        XCTAssertTrue(r.objects.allSatisfy { $0.identity == .UNCHECKED && $0.identityReasons == ["MEERDERE_SESSIES"] })
        XCTAssertTrue(r.requests.contains { $0.kind == .ZELFDE_SCANSESSIE })
        // een uitdrukkelijke verklaring van de gebruiker (alles nagelopen) heft "niet gecontroleerd" op, en dat blijft zichtbaar
        let reviewed = ObjectAssociator.associate(s, roundId: "ROUND-0001", userReviewedAll: true)
        XCTAssertTrue(reviewed.objects.allSatisfy { $0.identity == .RESOLVED_BY_USER })
    }

    func testWithoutLidarNothingCanBeLinkedAcrossPhotos() {
        let n1 = Syn.render([a], pos: Vec3(1.2, 1.6, 3.0), id: "F1", withDepth: false), n2 = Syn.render([a], pos: Vec3(1.8, 1.6, 3.0), id: "F2", withDepth: false)
        let s = [Syn.sighting(a, view: n1, id: "OBS-F1-01"), Syn.sighting(a, view: n2, id: "OBS-F2-01")]
        XCTAssertNil(s[0].spatial)
        let r = ObjectAssociator.associate(s, roundId: "ROUND-0001")
        XCTAssertEqual(r.objects.count, 2)
        XCTAssertTrue(r.objects.allSatisfy { $0.identity == .UNCHECKED && $0.identityReasons == ["GEEN_RUIMTELIJKE_METING"] })
        // één object op één foto heeft niets om mee te verwarren
        XCTAssertEqual(ObjectAssociator.associate([s[0]], roundId: "ROUND-0001").objects.first?.identity, .RESOLVED)
    }

    func testWeakOverlapIsUncertainNotMergedAndNotCounted() {
        // tweede waarneming is een half verschoven kader (bv. een deel van het kozijn): niet hetzelfde, niet zeker iets anders
        var shifted = a; shifted.x0 += 0.55
        let s1 = Syn.sighting(a, view: v1, id: "OBS-F1-01")
        var s2 = Syn.sighting(a, view: v2, id: "OBS-F2-01")
        let quad = Syn.frameQuad(shifted, pose: v2.pose)
        s2.polygon = quad
        var res = s2.result!
        let frame = try! XCTUnwrap(s2.spatial)
        let (o, dirs) = raysWorld(pose: v2.pose, intr: Syn.intr, pixels: quad)
        res.cornersWorld = dirs.map { intersectRayPlane(origin: o, dir: $0, n: frame.n, d: frame.d)!.point }
        s2.result = res
        let r = ObjectAssociator.associate([s1, s2], roundId: "ROUND-0001")
        XCTAssertEqual(r.objects.count, 2)
        XCTAssertTrue(r.objects.allSatisfy { $0.identity == .UNCERTAIN && $0.possibleSameAs.count == 1 })
        XCTAssertEqual(r.decisions.map { $0.kind }, [.UNCERTAIN_WEAK_OVERLAP])
        XCTAssertTrue(r.requests.contains { $0.kind == .OVERZICHTSFOTO })
    }

    func testUserDecisionsAlwaysWin() {
        let s = [Syn.sighting(a, view: v1, id: "OBS-F1-01"), Syn.sighting(a, view: v2, id: "OBS-F2-01"), Syn.sighting(b, view: v2, id: "OBS-F2-02")]
        // gebruiker: dit zijn VERSCHILLENDE kozijnen (ook al overlappen ze sterk)
        let apart = ObjectAssociator.associate(s, roundId: "ROUND-0001", constraints: .init(cannotLink: [["OBS-F1-01", "OBS-F2-01"]]))
        XCTAssertEqual(apart.objects.count, 3)
        XCTAssertTrue(apart.decisions.contains { $0.kind == .DISTINCT_USER })
        XCTAssertTrue(apart.objects.allSatisfy { $0.identity == .RESOLVED })
        // gebruiker: koppel twee waarnemingen die het systeem nooit zou koppelen
        let linked = ObjectAssociator.associate(s, roundId: "ROUND-0001", constraints: .init(mustLink: [["OBS-F1-01", "OBS-F2-02"]]))
        XCTAssertTrue(linked.decisions.contains { $0.kind == .SAME_USER })
        XCTAssertTrue(linked.objects.contains { Set($0.sightingIds).isSuperset(of: ["OBS-F1-01", "OBS-F2-02"]) })
    }

    func testSamePhotoDuplicatesMergeAndPartialOverlapIsUncertain() {
        let s1 = Syn.sighting(a, view: v1, id: "OBS-F1-01")
        var dup = Syn.sighting(a, view: v1, id: "OBS-F1-02"); dup.polygon = dup.polygon.map { Pixel($0.u + 3, $0.v - 2) }     // tweede detector, bijna hetzelfde kader
        let r = ObjectAssociator.associate([s1, dup], roundId: "ROUND-0001")
        XCTAssertEqual(r.objects.count, 1); XCTAssertEqual(r.decisions.first?.kind, .SAME_PHOTO_DUPLICATE)
        var inner = Syn.sighting(a, view: v1, id: "OBS-F1-03"); inner.polygon = scalePolygon(inner.polygon, 0.6)                 // binnenvak als "kozijn" gezien
        let u = ObjectAssociator.associate([s1, inner], roundId: "ROUND-0001")
        XCTAssertEqual(u.objects.count, 2); XCTAssertTrue(u.objects.allSatisfy { $0.identity == .UNCERTAIN })
    }

    func testFacadeConflictIsReportedNotResolved() {
        let s = [Syn.sighting(a, view: v1, id: "OBS-F1-01", facade: "Voorgevel"), Syn.sighting(a, view: v2, id: "OBS-F2-01", facade: "Zijgevel")]
        let r = ObjectAssociator.associate(s, roundId: "ROUND-0001")
        XCTAssertEqual(r.objects.count, 1); XCTAssertTrue(r.objects[0].facadeConflict)
    }
}
