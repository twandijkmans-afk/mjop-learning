import XCTest
@testable import Gevelscan
import PhotoWalkCore

/// Onderdeel B: eerlijke boekhouding van wat herkend kan worden, en de aansluiting van een (toekomstig) getraind model.
final class RecognitionTests: XCTestCase {
    let win = SynWindow(x0: 1.0, y0: 0.9, w: 2.1, h: 1.5, cols: 3)
    let model = DetectorDescriptor(name: "GevelElementDetector", version: "test-0", kind: .LEARNED_MODEL, validated: false, classes: [.RAAM, .DEUR, .GLASVLAK, .DRAAIEND_DEEL, .VAST_DEEL])

    func testCurrentAppRecognizesCandidatesOnlyAndSaysWhatIsMissing() {
        let c = RecognitionCapability.summarize([.visionCandidates])
        XCTAssertEqual(c.recognizable, [.KOZIJN, .GLASVLAK])
        XCTAssertTrue(c.learnedClasses.isEmpty); XCTAssertFalse(c.anyValidated)             // geen getraind model, niets gevalideerd
        XCTAssertEqual(Set(c.notRecognizable), [.RAAM, .DEUR, .DRAAIEND_DEEL, .VAST_DEEL, .GEVELPANEEL, .AANSLUITING, .AFWERKING])
        XCTAssertEqual(c.derivedByGeometry, [.GEVELVLAK, .TUSSENSTIJL, .TUSSENDORPEL])
        XCTAssertEqual(DetectorDescriptor.visionCandidates.kind, .GEOMETRIC_CANDIDATE)      // een vormzoeker is geen AI-kozijnherkenning
        let withModel = RecognitionCapability.summarize([.visionCandidates, model])
        XCTAssertTrue(withModel.learnedClasses.contains(.DRAAIEND_DEEL)); XCTAssertFalse(withModel.notRecognizable.contains(.DEUR))
    }

    func testModelLabelsMapToElementClassesAndUnknownLabelsAreIgnored() {
        XCTAssertEqual(ModelLabelMap.elementClass(forLabel: "window"), .RAAM)
        XCTAssertEqual(ModelLabelMap.elementClass(forLabel: "Deur"), .DEUR)
        XCTAssertEqual(ModelLabelMap.elementClass(forLabel: "glass pane"), .GLASVLAK)
        XCTAssertEqual(ModelLabelMap.elementClass(forLabel: "draaiend deel"), .DRAAIEND_DEEL)
        XCTAssertEqual(ModelLabelMap.elementClass(forLabel: "vast-deel"), .VAST_DEEL)
        XCTAssertEqual(ModelLabelMap.elementClass(forLabel: "window_frame"), .RAAM)
        XCTAssertNil(ModelLabelMap.elementClass(forLabel: "car")); XCTAssertNil(ModelLabelMap.elementClass(forLabel: "glasgow"))
    }

    func testModelDetectionsAreAttachedToTheRightFrame() {
        let v = Syn.render([win], pos: Vec3(1.7, 1.6, 3.2), id: "F1")
        let s = Syn.sighting(win, view: v, id: "OBS-F1-01", withPanes: false)
        let panes = Syn.paneQuads(win, pose: v.pose)
        var dets = panes.enumerated().map { ElementDetection(id: "M-G\($0)", photoId: "F1", elementClass: .GLASVLAK, polygon: $1, score: 0.9, detector: model) }
        dets += panes.enumerated().map { ElementDetection(id: "M-P\($0)", photoId: "F1", elementClass: $0 == 0 ? .DRAAIEND_DEEL : .VAST_DEEL, polygon: $1, score: 0.8, detector: model) }
        dets.append(ElementDetection(id: "M-W", photoId: "F1", elementClass: .RAAM, polygon: s.polygon, score: 0.95, detector: model))
        dets.append(ElementDetection(id: "M-X", photoId: "F1", elementClass: .GLASVLAK, polygon: [Pixel(5, 5), Pixel(40, 5), Pixel(40, 40), Pixel(5, 40)], score: 0.9, detector: model))   // los glas, geen kozijn
        dets.append(ElementDetection(id: "M-Y", photoId: "F2", elementClass: .GLASVLAK, polygon: panes[0], score: 0.9, detector: model))                                       // andere foto
        let r = PartAssembler.attach(dets, to: [s])
        XCTAssertEqual(r.sightings[0].panes.count, 3); XCTAssertEqual(r.sightings[0].parts.count, 3)
        XCTAssertEqual(r.sightings[0].elementClass, .RAAM); XCTAssertEqual(r.sightings[0].detector, model)
        XCTAssertEqual(r.unassigned.map { $0.id }, ["M-X", "M-Y"])
        // en door de pijplijn: draaiende delen komen dan van het model (voorlopig: model niet gevalideerd)
        var sight = r.sightings[0]; sight.evidence = .NESTED_PANES
        let out = GevelscanPipeline.run(GevelscanInput(roundId: "ROUND-0001", facades: [.init(id: "Voorgevel", orientation: nil)], photos: [Syn.photo(v)], sightings: [sight], detectors: [.visionCandidates, model]))
        let o = out.objects[0]
        XCTAssertEqual(o.elementClass, .RAAM); XCTAssertEqual(o.classOrigin, .MODEL_CLASSIFICATION)
        XCTAssertEqual(o.geometry.operableParts.value, 1); XCTAssertEqual(o.geometry.fixedParts.value, 2)
        XCTAssertEqual(o.geometry.operableParts.origin, .MODEL_CLASSIFICATION); XCTAssertEqual(o.geometry.operableParts.outcome, .VOORLOPIG_VASTGESTELD)
        XCTAssertEqual(out.facades[0].totals.doorCount.value, 0)                            // alles geclassificeerd: 0 deuren is nu een uitkomst, geen onbekende
    }
}
