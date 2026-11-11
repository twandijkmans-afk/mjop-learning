import XCTest
@testable import Gevelscan
import PhotoWalkCore

/// Onderdeel D: buitenmaat (bestaande meetkern), glasvlakken, tussenstijlen, draaiende delen, herkomst en onzekerheid.
/// De vergelijkingen met de "werkelijke" maat hieronder gaan over een SYNTHETISCHE scène en bewijzen alleen dat de rekenregels kloppen.
final class GeometryTests: XCTestCase {
    let w3 = SynWindow(x0: 1.0, y0: 0.9, w: 2.1, h: 1.5, cols: 3)                 // één kozijn met drie vakken
    lazy var v1 = Syn.render([w3], pos: Vec3(1.7, 1.6, 3.2), id: "F1", seed: 11)
    lazy var v2 = Syn.render([w3], pos: Vec3(2.5, 1.6, 3.2), id: "F2", seed: 12, yawDeg: 7)
    let rec = RecognitionCapability.summarize([.visionCandidates])

    func geometry(_ s: [FrameSighting], userParts: UserParts? = nil, validation: PipelineValidation = .current, recognition: RecognitionCapability? = nil) -> FrameGeometry {
        let o = ObjectAssociator.associate(s, roundId: "ROUND-0001").objects
        XCTAssertEqual(o.count, 1)
        return FrameGeometryRules.compute(object: o[0], sightings: s, photos: [:], recognition: recognition ?? rec, userParts: userParts, validation: validation)
    }

    func testThreeSectionFrameIsOneFrameWithThreePanesAndTwoMullions() {
        let g = geometry([Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")])
        XCTAssertEqual(g.status, .MEASURED)
        XCTAssertEqual(g.independentViewpoints, 2)
        XCTAssertEqual(g.width.value ?? 0, 2.1, accuracy: 0.03); XCTAssertEqual(g.height.value ?? 0, 1.5, accuracy: 0.03)
        XCTAssertEqual(g.area.value ?? 0, (g.width.value ?? 0) * (g.height.value ?? 0), accuracy: 1e-9)     // bruto = b x h (bestaande regel)
        XCTAssertEqual(g.sections.value, 3)                                   // drie vakken, NIET drie kozijnen
        XCTAssertEqual(g.panes.map { $0.column }, [0, 1, 2]); XCTAssertEqual(Set(g.panes.map { $0.row }), [0])
        XCTAssertEqual(g.mullions.count, 2); XCTAssertEqual(g.transoms.count, 0)
        for m in g.mullions { XCTAssertEqual(m.thicknessM, 0.06, accuracy: 0.03) }
        XCTAssertEqual(g.glassArea.value ?? 0, w3.glassAreaM2, accuracy: 0.06 * w3.glassAreaM2)
        XCTAssertLessThan(g.glassArea.value ?? 9, g.area.value ?? 0)
        XCTAssertTrue(g.panes.allSatisfy { $0.seenInViews == 2 })
        XCTAssertEqual(g.recessCm ?? 0, 6, accuracy: 2)
    }

    func testProvenanceSeparatesMeasuredFromDerived() {
        let g = geometry([Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")])
        XCTAssertEqual(g.width.origin, .LIDAR_PLANE_MEASUREMENT); XCTAssertEqual(g.height.origin, .LIDAR_PLANE_MEASUREMENT)
        XCTAssertEqual(g.area.origin, .DERIVED_CALCULATION)
        XCTAssertEqual(g.glassArea.origin, .DERIVED_SEGMENTATION_ON_MEASURED_PLANE)        // glas is NOOIT een directe LiDAR-meting
        XCTAssertEqual(g.sections.origin, .DERIVED_SEGMENTATION_ON_MEASURED_PLANE)
        XCTAssertNotNil(g.width.sigma); XCTAssertNotNil(g.area.sigma)
        XCTAssertGreaterThan(g.glassArea.sigma ?? 0, 0)                                     // onzekerheid is expliciet
        XCTAssertGreaterThan((g.glassArea.sigma ?? 0) / (g.glassArea.value ?? 1), (g.area.sigma ?? 0) / (g.area.value ?? 1))   // afgeleid = onzekerder dan gemeten
    }

    func testNothingIsReliableUntilThePipelineIsFieldValidated() {
        let s = [Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")]
        let now = geometry(s)
        XCTAssertEqual(now.status, .MEASURED)
        for v in [now.width, now.height, now.area, now.glassArea, now.sections] {
            XCTAssertEqual(v.outcome, .VOORLOPIG_VASTGESTELD); XCTAssertTrue(v.missing.contains("GEOMETRIE_NIET_IN_HET_VELD_GEVALIDEERD"))
        }
        let later = geometry(s, validation: Syn.validated)
        XCTAssertEqual(later.width.outcome, .BETROUWBAAR_VASTGESTELD); XCTAssertEqual(later.glassArea.outcome, .BETROUWBAAR_VASTGESTELD)
        XCTAssertEqual(now.width.value, later.width.value)                                  // de schakelaar verandert geen getal, alleen de klasse
    }

    func testSingleViewpointIsProvisionalEvenWhenValidated() {
        let g = geometry([Syn.sighting(w3, view: v1, id: "OBS-F1-01")], validation: Syn.validated)
        XCTAssertEqual(g.status, .ESTIMATED)
        XCTAssertEqual(g.width.outcome, .VOORLOPIG_VASTGESTELD); XCTAssertTrue(g.width.missing.contains("ENKEL_STANDPUNT"))
        XCTAssertEqual(g.glassArea.outcome, .VOORLOPIG_VASTGESTELD); XCTAssertTrue(g.glassArea.missing.contains("GLAS_OP_EEN_FOTO"))
    }

    func testStatusMatchesTheExistingMeasuringCore() {
        // dezelfde waarnemingen door de bestaande makeObject: status en maat moeten gelijk zijn (geen tweede rekenkern)
        let s = [Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")]
        for subset in [s, [s[0]]] {
            let g = geometry(subset)
            let items = subset.map { Viewpoints.ViewMeasurement(capture: .init(keyframeId: $0.photoId, position: $0.pose.t), result: $0.result!) }
            let c = Viewpoints.combineLevelA(items)!
            let obj = makeObject(id: "X", observations: [], result: c.result, viewCount: c.viewCount)
            XCTAssertEqual(g.status, obj.status)
            XCTAssertEqual(g.width.value, Double(obj.widthM!)); XCTAssertEqual(g.height.value, Double(obj.heightM!))
            XCTAssertEqual(g.area.value ?? 0, Double(obj.areaM2!)!, accuracy: 1e-9)
        }
    }

    func testNoLidarMeansNoDimensionsAndNoGlassArea() {
        let n = Syn.render([w3], pos: Vec3(1.7, 1.6, 3.2), id: "F1", withDepth: false)
        let g = geometry([Syn.sighting(w3, view: n, id: "OBS-F1-01")])
        XCTAssertEqual(g.status, .UNKNOWN)
        for v in [g.width, g.height, g.area, g.glassArea, g.sections] { XCTAssertNil(v.value); XCTAssertEqual(v.outcome, .NIET_VAST_TE_STELLEN); XCTAssertEqual(v.origin, .NONE) }
        XCTAssertTrue(g.blockingCodes.contains("NO_DEPTH"))
        XCTAssertTrue(g.panes.isEmpty)                                                      // geen schaal uit pixels
    }

    func testOperablePartsAreNeverGuessedFromShape() {
        let s = [Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")]
        let g = geometry(s)
        XCTAssertNil(g.operableParts.value); XCTAssertNil(g.fixedParts.value)
        XCTAssertEqual(g.operableParts.missing, ["GEEN_MODEL_VOOR_DRAAIENDE_DELEN"])
        XCTAssertTrue(g.panes.allSatisfy { $0.operability == nil })
        // gebruiker voert het in: herkomst USER_INPUT, los van de (voorlopige) meting
        let u = geometry(s, userParts: UserParts(operableParts: 2, fixedParts: 1))
        XCTAssertEqual(u.operableParts.value, 2); XCTAssertEqual(u.fixedParts.value, 1)
        XCTAssertEqual(u.operableParts.origin, .USER_INPUT); XCTAssertEqual(u.operableParts.outcome, .BETROUWBAAR_VASTGESTELD)
    }

    func testOperablePartsFromALearnedModelAreMappedToPanes() {
        let model = DetectorDescriptor(name: "test-model", version: "0.1", kind: .LEARNED_MODEL, validated: false, classes: [.KOZIJN, .GLASVLAK, .DRAAIEND_DEEL, .VAST_DEEL, .DEUR, .RAAM])
        var s = [Syn.sighting(w3, view: v1, id: "OBS-F1-01", detector: model), Syn.sighting(w3, view: v2, id: "OBS-F2-01", detector: model)]
        for k in s.indices {
            s[k].parts = s[k].panes.enumerated().map { ElementDetection(id: "\(s[k].id)-D\($0)", photoId: s[k].photoId, elementClass: $0 == 1 ? .VAST_DEEL : .DRAAIEND_DEEL, polygon: $1.polygon, score: 0.8, detector: model) }
        }
        let g = geometry(s, recognition: RecognitionCapability.summarize([model]))
        XCTAssertEqual(g.operableParts.value, 2); XCTAssertEqual(g.fixedParts.value, 1)
        XCTAssertEqual(g.operableParts.origin, .MODEL_CLASSIFICATION)
        XCTAssertEqual(g.operableParts.outcome, .VOORLOPIG_VASTGESTELD)                     // model niet gevalideerd
        XCTAssertEqual(g.panes.map { $0.operability }, [.DRAAIEND_DEEL, .VAST_DEEL, .DRAAIEND_DEEL])
        // tegenstrijdige klassen tussen foto's => onbekend, geen meerderheidsgok bij gelijke stand
        s[1].parts = s[1].panes.map { ElementDetection(id: "\($0.id)-X", photoId: s[1].photoId, elementClass: .VAST_DEEL, polygon: $0.polygon, score: 0.8, detector: model) }
        let c = geometry(s, recognition: RecognitionCapability.summarize([model]))
        XCTAssertNil(c.operableParts.value); XCTAssertEqual(c.operableParts.missing, ["VAKKEN_ZONDER_EENDUIDIGE_KLASSE"])
    }

    func testInconsistentPanesBetweenPhotosAndOverlappingPanes() {
        var s = [Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")]
        s[1].panes.removeLast()                                                             // op foto 2 is één glasvlak gemist
        let g = geometry(s, validation: Syn.validated)
        XCTAssertEqual(g.sections.value, 3)
        XCTAssertEqual(g.glassArea.outcome, .VOORLOPIG_VASTGESTELD)
        XCTAssertTrue(g.notes.contains { $0.contains("Niet elke foto") })
        // twee "glasvlakken" die elkaar grotendeels overlappen: herkenning onbruikbaar => geen glasoppervlak
        var o = [Syn.sighting(w3, view: v1, id: "OBS-F1-01")]
        o[0].panes.append(ElementDetection(id: "X", photoId: "F1", elementClass: .GLASVLAK, polygon: scalePolygon(o[0].panes[0].polygon, 0.7).map { Pixel($0.u + 60, $0.v) }, score: 0.5, detector: .visionCandidates))
        let bad = geometry(o)
        XCTAssertNil(bad.glassArea.value); XCTAssertEqual(bad.glassArea.missing, ["GLASVLAKKEN_OVERLAPPEN"])
        XCTAssertNotNil(bad.area.value)                                                     // de kozijnmaat zelf blijft staan
    }

    func testTransomsAndGridOfPanes() {
        let grid = SynWindow(x0: 1.0, y0: 0.8, w: 1.6, h: 1.8, cols: 2, rows: 2)
        let a = Syn.render([grid], pos: Vec3(1.6, 1.7, 3.2), id: "F1", seed: 5), b = Syn.render([grid], pos: Vec3(2.2, 1.7, 3.2), id: "F2", seed: 6)
        let g = geometry([Syn.sighting(grid, view: a, id: "OBS-F1-01"), Syn.sighting(grid, view: b, id: "OBS-F2-01")])
        XCTAssertEqual(g.sections.value, 4); XCTAssertEqual(g.mullions.count, 1); XCTAssertEqual(g.transoms.count, 1)
        XCTAssertEqual(g.panes.map { [$0.row, $0.column] }, [[0, 0], [0, 1], [1, 0], [1, 1]])
        XCTAssertEqual(g.glassArea.value ?? 0, grid.glassAreaM2, accuracy: 0.07 * grid.glassAreaM2)
    }

    func testObliqueViewsStillGiveAConsistentFrame() {
        let a = Syn.render([w3], pos: Vec3(0.6, 1.6, 3.0), id: "F1", seed: 21, yawDeg: -22), b = Syn.render([w3], pos: Vec3(3.6, 1.6, 3.0), id: "F2", seed: 22, yawDeg: 24)
        let s = [Syn.sighting(w3, view: a, id: "OBS-F1-01"), Syn.sighting(w3, view: b, id: "OBS-F2-01")]
        let g = geometry(s)
        if g.status != .UNKNOWN {                                                           // meten of weigeren, nooit stil fout
            XCTAssertEqual(g.width.value ?? 0, 2.1, accuracy: 0.05); XCTAssertEqual(g.sections.value, 3)
        } else { XCTAssertFalse(g.blockingCodes.isEmpty) }
    }

    func testGlareOnGlassMakesGlassProvisionalAndAsksForAnotherPhoto() {
        var s = [Syn.sighting(w3, view: v1, id: "OBS-F1-01"), Syn.sighting(w3, view: v2, id: "OBS-F2-01")]
        s[0].glareFractionByPane = [s[0].panes[0].id: 0.6]
        let g = geometry(s, validation: Syn.validated)
        XCTAssertTrue(g.panes[0].glareSuspected)
        XCTAssertEqual(g.glassArea.outcome, .VOORLOPIG_VASTGESTELD); XCTAssertTrue(g.glassArea.missing.contains("SPIEGELING_IN_GLAS"))
        XCTAssertEqual(g.width.outcome, .BETROUWBAAR_VASTGESTELD)                           // de buitenmaat lijdt er niet onder
    }
}
