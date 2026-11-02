import XCTest
@testable import PhotoWalkCore

/// Issue D: hoeken verslepen is BEWERKEN, geen bevestiging. Alleen "Dit is de buitenmaat" bevestigt een (bewerkte) automatische contour.
/// ScanStore.correctCorner / confirmCorners gebruiken precies deze overgangen (afterCornerEdit / afterExplicitConfirmation); de app-selftest
/// (SELFTEST_CORNER_EDIT, gecontroleerd in de CI) doorloopt dezelfde stappen via ScanStore, export en fotorondevoorstellen.
/// Python-tegenhanger: facade.after_corner_edit / after_explicit_confirmation (pariteit via facade_parity_cases.json).
final class ContourEditTests: XCTestCase {
    private let automatic: [OuterContourStatus] = [.DETECTED_ENCLOSING_PANES, .UNVERIFIED, .PROPOSED_EXPANSION]

    private func measured(_ w: Double = 1.2, _ h: Double = 1.5) -> LevelResult {
        var r = LevelResult(level: .A, scaleMethod: "LIDAR_DEPTH_PLANE", viewIds: ["F000"])
        r.width = w; r.height = h; r.sigmaW = 0.01; r.sigmaH = 0.01; r.sigmaArea = 0.02
        return r
    }
    private func codes(_ r: LevelResult) -> Set<String> { Set(r.flags.map { $0.code }) }

    // 1 + 10: één hoek (ook 1 pixel) verschuiven bevestigt niets en maakt een automatische contour nooit "zelf getekend"
    func testCornerEditNeverConfirmsAndNeverBecomesManual() {
        for s in automatic {
            let e = s.afterCornerEdit
            XCTAssertEqual(e, .EDITED_UNCONFIRMED, s.rawValue)
            XCTAssertNotEqual(e, .MANUAL, "een bewerkte automatische contour is niet zelf getekend")
            XCTAssertNotEqual(e, .USER_CONFIRMED)
            XCTAssertTrue(e.requiresConfirmation && e.blocksArea, s.rawValue)
            XCTAssertEqual(e.afterCornerEdit, .EDITED_UNCONFIRMED, "meer bewerkingen blijven onbevestigd")
        }
        // ook een eerder bevestigde contour moet na een bewerking opnieuw bevestigd worden
        XCTAssertEqual(OuterContourStatus.USER_CONFIRMED.afterCornerEdit, .EDITED_UNCONFIRMED)
    }

    // 2 + 3: de bewerkte contour blijft geblokkeerd voor meting, aantal en oppervlak (alleen indicatief zichtbaar)
    func testEditedContourStaysBlockedForMeasurementCountAndArea() {
        let g = ContourGate.apply(measured(), status: OuterContourStatus.UNVERIFIED.afterCornerEdit)
        XCTAssertFalse(g.ok, "geen maat")
        XCTAssertTrue(codes(g).contains("OUTER_CONTOUR_UNVERIFIED"))
        XCTAssertNotNil(ContourGate.indicativeDims(g), "wel een indicatieve maat in de app")
        let obj = makeObject(id: "P", observations: [], result: g, viewCount: 1)
        XCTAssertEqual(obj.status, .UNKNOWN); XCTAssertNil(obj.widthM); XCTAssertNil(obj.areaM2, "geen kozijnoppervlak in de export")
        // gevelopbouw: zoals ScanStore een geblokkeerde meting doorgeeft (geen oppervlak, UNKNOWN) -> geen buitenkozijnwaarde
        let o = FacadeOpeningInput(id: "OBS-1", outerPx: [Pixel(200, 150), Pixel(420, 150), Pixel(420, 450), Pixel(200, 450)], areaM2: nil, status: .UNKNOWN,
                                   planeN: nil, planeD: nil, panesPx: [])
        let pose = Pose(rows: [Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, 1)], t: Vec3(0, 1.5, 0))
        let r = FacadeComposition.compose(openings: [o], pose: pose, intr: Intrinsics(fx: 1000, fy: 1000, cx: 600, cy: 350, width: 1200, height: 700),
                                          facadePx: [Pixel(100, 80), Pixel(1100, 80), Pixel(1100, 620), Pixel(100, 620)], facadePlane: (Vec3(0, 0, 1), 5), facadePlaneStatus: .ESTIMATED)
        XCTAssertNil(r.frameOuter.valueM2); XCTAssertNil(r.openings.valueM2); XCTAssertNil(r.closedFacadeNet.valueM2)
    }

    // 5: bewerken, "Herstel detectie" (originele hoeken terug) en "Toepassen" = twee bewerkingen: nog steeds onbevestigd
    func testRestoreDetectionThenApplyStaysUnconfirmed() {
        for s in automatic {
            let afterEdit = s.afterCornerEdit
            let afterRestoreApply = afterEdit.afterCornerEdit           // "Toepassen" van de herstelde hoeken loopt via dezelfde correctie
            XCTAssertEqual(afterRestoreApply, .EDITED_UNCONFIRMED, s.rawValue)
            XCTAssertFalse(ContourGate.apply(measured(), status: afterRestoreApply).ok, "dezelfde geometrie als de detectie, maar nooit bevestigd")
        }
    }

    // 6: de bevestigingsknop blijft zichtbaar na een hoekcorrectie (ook als de bron dan MANUAL_CORRECTED is, niet meer AUTO_DETECTED_UNCONFIRMED)
    func testConfirmActionStaysVisibleAfterCornerEdit() {
        for s in automatic + [.USER_CONFIRMED] {
            XCTAssertTrue(OuterContourStatus.showsConfirmAction(status: s.afterCornerEdit, autoDetectedUnconfirmed: false), s.rawValue)
        }
        XCTAssertFalse(OuterContourStatus.showsConfirmAction(status: .USER_CONFIRMED, autoDetectedUnconfirmed: false), "na bevestiging geen knop meer")
        XCTAssertFalse(OuterContourStatus.showsConfirmAction(status: .MANUAL, autoDetectedUnconfirmed: false))
    }

    // 7 + 8: alleen de expliciete bevestiging opent de contourpoort; alle andere regels blijven gelden
    func testExplicitConfirmationOnlyOpensTheContourGate() {
        let confirmed = OuterContourStatus.EDITED_UNCONFIRMED.afterExplicitConfirmation
        XCTAssertEqual(confirmed, .USER_CONFIRMED)
        XCTAssertFalse(confirmed.blocksArea)
        for s in automatic { XCTAssertEqual(s.afterCornerEdit.afterExplicitConfirmation, .USER_CONFIRMED, s.rawValue) }
        // contourpoort open, maar: zonder schaal geen maat
        var noScale = LevelResult(level: .A, scaleMethod: "NONE", viewIds: ["F000"]); noScale.flags = [Flags.make("NO_METRIC_SCALE")]
        XCTAssertFalse(ContourGate.apply(noScale, status: confirmed).ok, "bevestigen levert geen schaal")
        // één foto blijft hoogstens ESTIMATED (standpuntregel), met reviewmarkering
        let one = makeObject(id: "P", observations: [], result: ContourGate.apply(measured(), status: confirmed), viewCount: 1,
                             extraFlags: [Flags.make("HUMAN_CORRECTED_CORNERS")])
        XCTAssertEqual(one.status, .ESTIMATED); XCTAssertTrue(one.reviewRequired); XCTAssertTrue(one.flags.contains { $0.code == "SINGLE_VIEWPOINT" })
        // een afwaarderende meetcode blijft afwaarderen, ook na bevestiging
        var glass = fuse([measured(), measured(1.201, 1.499)]); glass.flags.append(Flags.make("GLASS_DEPTH_UNRELIABLE"))
        XCTAssertNotEqual(makeObject(id: "P", observations: [], result: ContourGate.apply(glass, status: confirmed), viewCount: 2).status, .MEASURED)
        // tegenstrijdige standpunten blijven geblokkeerd
        XCTAssertFalse(ContourGate.apply(fuse([measured(1.2, 1.5), measured(1.5, 1.5)]), status: confirmed).ok)
    }

    // 9: een volledig zelf getekende vierhoek is MANUAL en blijft dat, ook na het verschuiven van een eigen hoek
    func testFullySelfDrawnQuadIsManual() {
        XCTAssertEqual(OuterContourStatus.MANUAL.afterCornerEdit, .MANUAL)
        XCTAssertEqual(OuterContourStatus.MANUAL.afterExplicitConfirmation, .MANUAL)
        XCTAssertFalse(OuterContourStatus.MANUAL.blocksArea)
        XCTAssertTrue(ContourGate.apply(measured(), status: .MANUAL).ok)
    }

    // 11: oude scans (LEGACY) gedragen zich zoals vroeger
    func testLegacyBehaviourUnchanged() {
        XCTAssertEqual(OuterContourStatus.LEGACY.afterCornerEdit, .LEGACY)
        XCTAssertEqual(OuterContourStatus.LEGACY.afterExplicitConfirmation, .LEGACY)
        XCTAssertFalse(OuterContourStatus.LEGACY.blocksArea)
        XCTAssertTrue(ContourGate.apply(measured(), status: .LEGACY).ok)
    }

    func testBlockingSetIsExactlyTheUnconfirmedStates() {
        XCTAssertEqual(Set(OuterContourStatus.allCases.filter { $0.blocksArea }), [.DETECTED_ENCLOSING_PANES, .UNVERIFIED, .PROPOSED_EXPANSION, .EDITED_UNCONFIRMED])
        XCTAssertEqual(Set(OuterContourStatus.allCases.filter { !$0.blocksArea }), [.LEGACY, .MANUAL, .USER_CONFIRMED])
    }

    // pariteit met de Python-referentie
    func testTransitionsMatchPython() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "facade_parity_cases", withExtension: "json", subdirectory: "Fixtures"))
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let rows = try XCTUnwrap(root["contour_transitions"] as? [[String: Any]])
        XCTAssertEqual(Set(rows.compactMap { $0["status"] as? String }), Set(OuterContourStatus.allCases.map { $0.rawValue }), "zelfde statussen in Swift en Python")
        for row in rows {
            let s = try XCTUnwrap(OuterContourStatus(rawValue: row["status"] as! String))
            XCTAssertEqual(s.blocksArea, row["blocks_area"] as? Bool, s.rawValue)
            XCTAssertEqual(s.afterCornerEdit.rawValue, row["after_corner_edit"] as? String, s.rawValue)
            XCTAssertEqual(s.afterExplicitConfirmation.rawValue, row["after_explicit_confirmation"] as? String, s.rawValue)
            XCTAssertEqual(s.afterCornerEdit.afterExplicitConfirmation.rawValue, row["after_edit_then_confirm"] as? String, s.rawValue)
            XCTAssertEqual(s.afterExplicitConfirmation.afterCornerEdit.rawValue, row["after_confirm_then_edit"] as? String, s.rawValue)
            XCTAssertEqual(OuterContourStatus.showsConfirmAction(status: s.afterCornerEdit, autoDetectedUnconfirmed: false), row["shows_confirm_after_edit"] as? Bool, s.rawValue)
        }
    }
}
