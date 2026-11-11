import XCTest
@testable import Gevelscan
import PhotoWalkCore

/// Onderdeel E: zichtbaar gebrek / mogelijke indicatie / niet beoordeelbaar. Geen verborgen gebreken, geen NEN 2767-score.
final class ConditionTests: XCTestCase {
    let win = SynWindow(x0: 1.0, y0: 0.9, w: 1.2, h: 1.5, cols: 2)
    lazy var view = Syn.render([win], pos: Vec3(1.6, 1.6, 2.2), id: "F1")
    lazy var sighting = Syn.sighting(win, view: view, id: "OBS-F1-01")
    lazy var object = ObjectAssociator.associate([sighting], roundId: "ROUND-0001").objects[0]
    let model = DetectorDescriptor(name: "gebreken-test", version: "0.1", kind: .LEARNED_MODEL, validated: false, classes: [])
    func defect(_ score: Double, _ cat: DefectCategory = .afbladderend, detector: DetectorDescriptor? = nil, at: Pixel? = nil) -> DefectDetection {
        let c = at ?? polygonCentroid(sighting.polygon)
        return DefectDetection(id: "D\(Int(score * 100))", photoId: "F1", category: cat, region: [Pixel(c.u - 20, c.v - 20), Pixel(c.u + 20, c.v - 20), Pixel(c.u + 20, c.v + 20), Pixel(c.u - 20, c.v + 20)],
                               score: score, detector: detector ?? model)
    }

    func testWithoutADefectModelEverythingIsNotAssessable() {
        let r = ConditionRules.assess(object: object, sightings: [sighting], photoFlags: [:], detections: [], conditionDetector: nil)
        XCTAssertEqual(r.observations.map { $0.kind }, [.NIET_BEOORDEELBAAR])
        XCTAssertEqual(r.observations[0].reasons, ["GEEN_GEBREKENMODEL"])
        XCTAssertNil(r.nen2767ConditionScore)                               // nooit een formele score
    }

    func testUnvalidatedModelGivesIndicationsOnlyWithSourcePhotoAndLocation() {
        let r = ConditionRules.assess(object: object, sightings: [sighting], photoFlags: [:], detections: [defect(0.95), defect(0.5, .kitnaad), defect(0.2, .scheur)], conditionDetector: model)
        XCTAssertEqual(r.observations.count, 2)                             // score 0,2 is te zwak om te melden
        XCTAssertTrue(r.observations.allSatisfy { $0.kind == .MOGELIJKE_INDICATIE && $0.photoId == "F1" && $0.region?.count == 4 && $0.reasons == ["MODEL_NIET_GEVALIDEERD"] })
        XCTAssertEqual(Set(r.observations.compactMap { $0.category }), [.afbladderend, .kitnaad])
    }

    func testVisibleDefectRequiresAValidatedModelAndAHighScore() {
        var ok = model; ok.validated = true
        let r = ConditionRules.assess(object: object, sightings: [sighting], photoFlags: [:], detections: [defect(0.95, detector: ok), defect(0.6, .corrosie, detector: ok)], conditionDetector: ok)
        XCTAssertEqual(r.observations.map { $0.kind }, [.MOGELIJKE_INDICATIE, .ZICHTBAAR_GEBREK])
    }

    func testDefectOutsideTheObjectIsNotAttributedToIt() {
        let r = ConditionRules.assess(object: object, sightings: [sighting], photoFlags: [:], detections: [defect(0.9, at: Pixel(40, 40))], conditionDetector: model)
        XCTAssertTrue(r.observations.isEmpty)
    }

    func testBlurOrTooLittleDetailMeansNotAssessableWithATargetedRequest() {
        let blurry = ConditionRules.assess(object: object, sightings: [sighting], photoFlags: ["F1": ["ONSCHERP"]], detections: [defect(0.95)], conditionDetector: model)
        XCTAssertEqual(blurry.observations.map { $0.kind }, [.NIET_BEOORDEELBAAR]); XCTAssertTrue(blurry.requests.contains { $0.kind == .SCHERPERE_FOTO })
        // van ver: te weinig pixels per meter om afbladderen te kunnen zien
        let far = Syn.render([win], pos: Vec3(1.6, 1.6, 4.6), id: "F1")
        let s = Syn.sighting(win, view: far, id: "OBS-F1-01")
        XCTAssertLessThan(ConditionRules.pixelsPerMeter(s) ?? 999, 400)
        var cfg = GevelscanConfig(); cfg.conditionMinPxPerM = 400
        let r = ConditionRules.assess(object: object, sightings: [s], photoFlags: [:], detections: [defect(0.95)], conditionDetector: model, cfg: cfg)
        XCTAssertEqual(r.observations.first?.reasons, ["TE_WEINIG_BEELDDETAIL"]); XCTAssertTrue(r.requests.contains { $0.kind == .DICHTERBIJ })
    }

    func testCategoriesAreExtensible() {
        let new = DefectCategory(rawValue: "ZETTINGSSCHADE_ZICHTBAAR")
        XCTAssertEqual(new.labelNL, "ZETTINGSSCHADE_ZICHTBAAR")
        let r = ConditionRules.assess(object: object, sightings: [sighting], photoFlags: [:], detections: [defect(0.7, new)], conditionDetector: model)
        XCTAssertEqual(r.observations.first?.category, new)
        XCTAssertEqual(DefectCategory.known.count, 9)
    }
}
