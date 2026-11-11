import XCTest
@testable import Gevelscan
import MJOPIntegration
import PhotoWalkCore

/// Regressietests voor de bevindingen uit de onafhankelijke review van Gevelscanner 2.0.
final class ReviewRegressionTests: XCTestCase {
    let a = SynWindow(x0: 0.6, y0: 0.9, w: 1.2, h: 1.5, cols: 2)
    let b = SynWindow(x0: 2.4, y0: 0.9, w: 1.5, h: 1.5, cols: 3)
    let project = ScanProposalV2.Project(planRef: "plan-abc12345", mjopPlanId: nil, buildingId: "Testgebouw", bagPandId: nil)
    lazy var v1 = Syn.render([a, b], pos: Vec3(1.9, 1.6, 3.8), id: "F001", seed: 1)
    lazy var v2 = Syn.render([a, b], pos: Vec3(2.6, 1.6, 3.8), id: "F002", seed: 2, yawDeg: 4)

    func input(_ sightings: [FrameSighting], photos: [PhotoCapture]? = nil) -> GevelscanInput {
        GevelscanInput(roundId: "ROUND-0001", facades: [.init(id: "Voorgevel", orientation: nil)], photos: photos ?? [Syn.photo(v1), Syn.photo(v2)], sightings: sightings)
    }
    func contract(_ i: GevelscanInput) throws -> GevelInventoryV1 {
        try InventoryContractBuilder.build(result: GevelscanPipeline.run(i), photos: i.photos, project: project, elementKey: nil, revision: 1, createdAt: "2026-11-11T10:15:00Z")
    }

    /// Bevinding 1: de gebruiker merkt alle kozijnen aan als raam/deur -> het contract moet blijven kloppen (deurtotaal was BETROUWBAAR + MODEL).
    func testUserClassifiedFramesStillProduceAValidContract() throws {
        var i = input([Syn.sighting(a, view: v1, id: "OBS-F001-01"), Syn.sighting(a, view: v2, id: "OBS-F002-01"), Syn.sighting(b, view: v1, id: "OBS-F001-02"), Syn.sighting(b, view: v2, id: "OBS-F002-02")])
        i.userClasses = ["OBS-F001-01": .RAAM, "OBS-F001-02": .DEUR]
        i.userParts = ["OBS-F001-01": .init(operableParts: 1, fixedParts: 1), "OBS-F001-02": .init(operableParts: 1, fixedParts: 2)]
        let r = GevelscanPipeline.run(i)
        let t = r.facades[0].totals
        XCTAssertEqual(t.doorCount.value, 1); XCTAssertEqual(t.doorCount.origin, .USER_INPUT)
        XCTAssertEqual(t.operableParts.value, 2); XCTAssertEqual(t.operableParts.origin, .USER_INPUT)
        // een totaal over objecten is nooit zekerder dan de (niet-gevalideerde) telling van die objecten
        XCTAssertEqual(t.doorCount.outcome, .VOORLOPIG_VASTGESTELD); XCTAssertEqual(t.operableParts.outcome, .VOORLOPIG_VASTGESTELD)
        XCTAssertEqual(r.objects.first { $0.elementClass == .DEUR }?.geometry.operableParts.outcome, .BETROUWBAAR_VASTGESTELD)   // de invoer zelf blijft van de gebruiker
        XCTAssertNoThrow(try contract(i))
        // gemengd: één kozijn door de gebruiker ingevuld, het andere niet -> totaal onbekend, herkomst niet opgewaardeerd
        i.userParts = ["OBS-F001-01": .init(operableParts: 1, fixedParts: 1)]
        let mixed = GevelscanPipeline.run(i).facades[0].totals.operableParts
        XCTAssertNil(mixed.value); XCTAssertEqual(mixed.partial, 1)
        XCTAssertNoThrow(try contract(i))
    }

    /// Bevinding 3: een andere starthoek van de contour (of een gedraaide telefoon) mag de vakken niet spiegelen of dubbel tellen.
    func testCornerOrderDoesNotMirrorOrDoubleCountPanes() {
        let asym = SynWindow(x0: 1.0, y0: 0.9, w: 2.1, h: 1.5, cols: 3)
        let p1 = Syn.render([asym], pos: Vec3(1.7, 1.6, 3.2), id: "F1", seed: 11), p2 = Syn.render([asym], pos: Vec3(2.5, 1.6, 3.2), id: "F2", seed: 12, yawDeg: 7)
        let s1 = Syn.sighting(asym, view: p1, id: "OBS-F1-01")
        var s2 = Syn.sighting(asym, view: p2, id: "OBS-F2-01")
        s2.panes.removeLast()                                              // asymmetrisch: op foto 2 ontbreekt het rechtervak
        // zelfde kozijn, maar de contour begint rechtsonder (BR, BL, TL, TR)
        let q = s2.polygon; let rot = [q[2], q[3], q[0], q[1]]
        s2.polygon = rot
        s2.result = measureDepthView(p2, corners: rot, seed: 7)
        XCTAssertTrue(s2.result?.ok == true, "\(codes(s2.result))")
        let o = ObjectAssociator.associate([s1, s2], roundId: "ROUND-0001").objects
        XCTAssertEqual(o.count, 1)
        let g = FrameGeometryRules.compute(object: o[0], sightings: [s1, s2], photos: [:], recognition: .summarize([.visionCandidates]))
        XCTAssertEqual(g.sections.value, 3)                                // niet 5: de twee gedeelde vakken vallen samen
        XCTAssertEqual(g.panes.map { $0.seenInViews }, [2, 2, 1])          // het ontbrekende vak is het RECHTER vak (x van links)
        XCTAssertEqual(g.glassArea.value ?? 0, asym.glassAreaM2, accuracy: 0.07 * asym.glassAreaM2)
        XCTAssertLessThan(g.panes[0].xM, g.panes[1].xM); XCTAssertLessThan(g.panes[1].xM, g.panes[2].xM)
    }

    /// Bevinding 4: een slechte vlakfit of drift (zelfde plek, ander vlak) is geen bewijs voor twee kozijnen.
    func testPlaneMismatchAtTheSamePlaceIsUncertainNotDistinct() {
        let s1 = Syn.sighting(a, view: v1, id: "OBS-F001-01")
        var s2 = Syn.sighting(a, view: v2, id: "OBS-F002-01")
        var r = s2.result!
        r.planeD = (r.planeD ?? 0) + 0.4                                    // vlak 40 cm verschoven
        r.cornersWorld = r.cornersWorld?.map { $0 + (r.planeN ?? Vec3(0, 0, 1)) * 0.4 }
        s2.result = r
        let out = ObjectAssociator.associate([s1, s2], roundId: "ROUND-0001")
        XCTAssertEqual(out.objects.count, 2)
        XCTAssertTrue(out.objects.allSatisfy { $0.identity == .UNCERTAIN })
        XCTAssertEqual(out.decisions.map { $0.kind }, [.UNCERTAIN_PLANE_MISMATCH])
        XCTAssertNil(GevelscanPipeline.run(input([s1, s2])).facades[0].totals.frameCount.value)
    }

    /// Bevinding 5: objecten op verschillende gevels die niet vergeleken konden worden maken het gebouwtotaal voorlopig, ook binnen één sessie.
    func testCrossFacadeUncheckedObjectsCapTheBuildingTotal() {
        let plain = Syn.render([b], pos: Vec3(2.6, 1.6, 3.8), id: "F002", withDepth: false)
        let s = [Syn.sighting(a, view: v1, id: "OBS-F001-01", facade: "Voorgevel"), Syn.sighting(b, view: plain, id: "OBS-F002-01", facade: "Zijgevel")]
        let i = GevelscanInput(roundId: "ROUND-0001", facades: [.init(id: "Voorgevel", orientation: nil), .init(id: "Zijgevel", orientation: nil)],
                               photos: [Syn.photo(v1), Syn.photo(plain, facade: "Zijgevel")], sightings: s)
        let r = GevelscanPipeline.run(i)
        XCTAssertTrue(r.association.crossFacadeUnchecked)
        XCTAssertTrue(r.building.frameCount.missing.contains("GEVELS_ONDERLING_NIET_VERGELEKEN"))
        XCTAssertEqual(r.facades.map { $0.totals.frameCount.value }, [1, 1])                 // per gevel wel een telling
    }

    /// Bevinding 6: de app kent de gevelomvang niet; volledigheid is zonder verklaring van de gebruiker nooit "betrouwbaar".
    func testCompletenessNeedsTheUsersDeclarationEvenWhenValidated() {
        let s = [Syn.sighting(a, view: v1, id: "OBS-F001-01", confirmed: true), Syn.sighting(a, view: v2, id: "OBS-F002-01", confirmed: true),
                 Syn.sighting(b, view: v1, id: "OBS-F001-02", confirmed: true), Syn.sighting(b, view: v2, id: "OBS-F002-02", confirmed: true)]
        var i = input(s); i.validation = Syn.validated
        let r = GevelscanPipeline.run(i)
        XCTAssertTrue(r.objects.allSatisfy { $0.outcome == .BETROUWBAAR_VASTGESTELD }, "\(r.objects.map { $0.outcomeReasons })")
        XCTAssertEqual(r.facades[0].completeness, .VOORLOPIG_VASTGESTELD); XCTAssertEqual(r.facades[0].completenessReasons, ["GEVELOMVANG_ONBEKEND"])
        XCTAssertFalse(r.autoProcessingAllowed)
        i.userReviewedAllDuplicates = true
        let reviewed = GevelscanPipeline.run(i)
        XCTAssertEqual(reviewed.facades[0].completeness, .BETROUWBAAR_VASTGESTELD); XCTAssertTrue(reviewed.autoProcessingAllowed)
    }

    /// Bevinding 8: één onleesbare inventaris mag de outbox (met v2-voorstellen) niet leegmaken.
    func testOutboxSurvivesAnInventoryThatNoLongerValidates() throws {
        let stored = #"{"rounds":[{"roundId":"R-00000001","planRef":"plan-abc12345","status":"COMPLETED","photos":2,"objects":1,"revision":1,"proposals":[],"deliveredIds":["x"],"inventory":{"contract":"mjop_gevel_inventory_v1","kapot":true},"inventoryDelivered":true}]}"#
        let o = try JSONDecoder().decode(ProposalOutbox.self, from: Data(stored.utf8))
        XCTAssertEqual(o.rounds.count, 1); XCTAssertEqual(o.rounds[0].deliveredIds, ["x"])
        XCTAssertNil(o.rounds[0].inventory); XCTAssertNil(o.rounds[0].inventoryDelivered)
    }

    /// Bevinding 14/16: "verschillend" van de gebruiker wordt ook via een derde waarneming niet stil overruled; tegenstrijdige invoer telt niet.
    func testTransitiveCannotLinkAndConflictingUserParts() {
        let v3 = Syn.render([a, b], pos: Vec3(2.25, 1.7, 3.7), id: "F003", seed: 3, yawDeg: -2)
        let s = [Syn.sighting(a, view: v1, id: "OBS-F001-01"), Syn.sighting(a, view: v2, id: "OBS-F002-01"), Syn.sighting(a, view: v3, id: "OBS-F003-01")]
        let r = ObjectAssociator.associate(s, roundId: "ROUND-0001", constraints: .init(cannotLink: [["OBS-F001-01", "OBS-F002-01"]]))
        XCTAssertEqual(r.objects.count, 1)                                  // 1 en 2 komen via 3 toch samen ...
        XCTAssertEqual(r.objects[0].identity, .UNCERTAIN); XCTAssertEqual(r.objects[0].identityReasons, ["TEGENSTRIJDIGE_KOPPELING"])   // ... maar dat wordt gemeld, niet geteld
        var i = input([Syn.sighting(a, view: v1, id: "OBS-F001-01"), Syn.sighting(a, view: v2, id: "OBS-F002-01")])
        i.userParts = ["OBS-F001-01": .init(operableParts: 1, fixedParts: 1), "OBS-F002-01": .init(operableParts: 2, fixedParts: 0)]
        XCTAssertNil(GevelscanPipeline.run(i).objects[0].geometry.operableParts.value)
    }

    /// Bevinding 10: een vraag om extra foto's zonder tekst wordt door het contract geweigerd (de website zou erop stuklopen).
    func testCaptureRequestsAreValidatedElementWise() throws {
        let inv = try contract(input([Syn.sighting(a, view: v1, id: "OBS-F001-01")]))
        var o = inv.jsonObject()!
        var f = o["facades"] as! [[String: Any]]
        XCTAssertFalse((f[0]["capture_requests"] as! [[String: Any]]).isEmpty)
        f[0]["capture_requests"] = [["kind": "ANDERE_HOEK", "object_id": NSNull(), "photo_id": NSNull(), "reason": "X", "text_nl": NSNull()]]
        o["facades"] = f
        XCTAssertFalse(GevelInventoryV1.validate(JSONValue.from(any: o)!).isEmpty)
    }
}
