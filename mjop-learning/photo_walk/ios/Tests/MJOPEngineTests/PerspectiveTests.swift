import Foundation
import XCTest
@testable import MJOPEngine

final class PerspectiveTests: XCTestCase {
    /// Een virtuele camera (brandpunt f pixels, hoofdpunt in het midden) fotografeert een vlak; geeft pixels terug.
    struct Camera {
        var f = 2800.0, W = 3000.0, H = 4000.0
        var yaw = 0.0, pitch = 0.0, roll = 0.0, distance = 25.0
        func project(_ x: Double, _ y: Double, _ z: Double = 0) -> [Double] {   // x naar rechts, y omhoog, z naar de camera toe, in meters
            var p = [x, y, -z]
            func rx(_ v: [Double], _ a: Double) -> [Double] { [v[0], cos(a) * v[1] - sin(a) * v[2], sin(a) * v[1] + cos(a) * v[2]] }
            func ry(_ v: [Double], _ a: Double) -> [Double] { [cos(a) * v[0] + sin(a) * v[2], v[1], -sin(a) * v[0] + cos(a) * v[2]] }
            func rz(_ v: [Double], _ a: Double) -> [Double] { [cos(a) * v[0] - sin(a) * v[1], sin(a) * v[0] + cos(a) * v[1], v[2]] }
            p = rz(ry(rx(p, pitch), yaw), roll)
            p[2] += distance
            return [f * p[0] / p[2] + W / 2, H / 2 - f * p[1] / p[2]]
        }
        /// Rechthoek van w × h meter rond het midden: linksboven, rechtsboven, rechtsonder, linksonder.
        func rect(_ w: Double, _ h: Double, x0: Double = 0, y0: Double = 0, z: Double = 0) -> [[Double]] {
            [project(x0 - w / 2, y0 + h / 2, z), project(x0 + w / 2, y0 + h / 2, z), project(x0 + w / 2, y0 - h / 2, z), project(x0 - w / 2, y0 - h / 2, z)]
        }
    }

    func testAspectWithKnownFocal() throws {
        for (w, h, yaw, pitch) in [(12.0, 8.0, 0.5, 0.1), (20.0, 6.0, -0.6, -0.2), (9.0, 14.0, 0.3, 0.25)] {
            let cam = Camera(yaw: yaw, pitch: pitch, roll: 0.03)
            let a = try XCTUnwrap(FacadePerspective.aspect(corners: cam.rect(w, h), focalPx: cam.f, width: cam.W, height: cam.H))
            XCTAssertEqual(a.ratio, w / h, accuracy: 1e-6)
            XCTAssertEqual(a.source, .exif)
        }
    }

    func testFocalIsEstimatedFromTheCornersWhenExifIsMissing() throws {
        let cam = Camera(yaw: 0.5, pitch: 0.15)
        let a = try XCTUnwrap(FacadePerspective.aspect(corners: cam.rect(12, 8), focalPx: nil, width: cam.W, height: cam.H))
        XCTAssertEqual(a.ratio, 1.5, accuracy: 1e-4)
        XCTAssertEqual(a.source, .geschat)
    }

    func testStraightOnPhotoNeedsNoFocal() throws {
        let cam = Camera()
        let a = try XCTUnwrap(FacadePerspective.aspect(corners: cam.rect(10, 5), focalPx: nil, width: cam.W, height: cam.H))
        XCTAssertEqual(a.ratio, 2, accuracy: 1e-6)
        XCTAssertEqual(a.source, .aangenomen)
    }

    func testRectifiedQuantitiesMatchTheRealFacade() throws {
        // Gevel 12 × 8 m schuin gefotografeerd, met een raam van 1,2 × 1,5 m en een deur van 1 × 2,2 m.
        let cam = Camera(yaw: 0.55, pitch: 0.12, roll: 0.02)
        let plane = FacadePlane(id: 1, kind: .hoofdgevel, corners: cam.rect(12, 8))
        let raam = cam.rect(1.2, 1.5, x0: -3, y0: 1)
        let deur = cam.rect(1, 2.2, x0: 2, y0: -2.9)
        let els = [
            FacadePhotoElement(id: 1, type: .metselwerk, points: cam.rect(12, 8), material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 2, type: .kozijn_raam, points: raam, material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 3, type: .kozijn_deur, points: deur, material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 4, type: .kozijn_raam, points: cam.rect(1, 1, x0: 5, y0: 5), material: nil, confidence: "high", note: nil, plane: 2),
        ]
        let r = try XCTUnwrap(FacadePerspective.rectify(els, plane: plane, widthM: 12, focalPx: cam.f, imageWidth: cam.W, imageHeight: cam.H))
        XCTAssertEqual(r.heightM, 8, accuracy: 1e-6)
        XCTAssertEqual(r.leftOut, 1, "het raam op een ander vlak telt hier niet mee")
        let q = FacadePhoto.quantities(r.elements[1], mpp: 1, all: r.elements)
        XCTAssertEqual(try XCTUnwrap(q.widthM), 1.2, accuracy: 1e-6)
        XCTAssertEqual(try XCTUnwrap(q.heightM), 1.5, accuracy: 1e-6)
        let s = FacadePhoto.summary(r.elements, mpp: 1)
        XCTAssertEqual(s.metselwerkNetM2, 92)
        XCTAssertEqual(s.raamkozijnen, 1)

        // Zonder perspectiefcorrectie (oude methode, breedte over de foto) zou de deur er duidelijk anders uitkomen.
        let ref = try XCTUnwrap(FacadePhoto.defaultReference(els))
        let naive = FacadePhoto.quantities(els[2], mpp: FacadePhoto.metersPerPixel(facadeWidthM: 12, leftX: ref.left, rightX: ref.right), all: els)
        XCTAssertGreaterThan(abs(try XCTUnwrap(naive.heightM) - 2.2), 0.2)
    }

    func testExtensionGetsItsOwnWidthFromADoor() throws {
        // Hoofdgevel 12 × 8 m; een uitbouw van 4 × 3 m staat 3 m naar voren met een deur van 1 × 2,1 m en een raam van 1,5 × 1 m.
        let cam = Camera(yaw: 0.4, pitch: 0.1)
        let hoofd = FacadePlane(id: 1, kind: .hoofdgevel, corners: cam.rect(12, 8))
        let uitbouw = FacadePlane(id: 2, kind: .uitbouw, corners: cam.rect(4, 3, x0: 2, y0: -2.5, z: 3))
        let els = [
            FacadePhotoElement(id: 1, type: .kozijn_raam, points: cam.rect(1.2, 1.5, x0: -3, y0: 2), material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 2, type: .kozijn_deur, points: cam.rect(1, 2.1, x0: 1.2, y0: -2.95, z: 3), material: nil, confidence: "high", note: nil, plane: 2),
            FacadePhotoElement(id: 3, type: .kozijn_raam, points: cam.rect(1.5, 1, x0: 3, y0: -2.5, z: 3), material: nil, confidence: "high", note: nil, plane: 2),
        ]
        let w = try XCTUnwrap(FacadePerspective.planeWidthFromDoor(els, plane: uitbouw, focalPx: cam.f, imageWidth: cam.W, imageHeight: cam.H))
        XCTAssertEqual(w, 4, accuracy: 1e-6)
        XCTAssertNil(FacadePerspective.planeWidthFromDoor(els, plane: hoofd, focalPx: cam.f, imageWidth: cam.W, imageHeight: cam.H), "geen deur op dit vlak: geen maat")

        // De maat van de hoofdgevel geldt niet voor de uitbouw: met de BAG-breedte erop zou het raam op de uitbouw fout uitkomen.
        let main = try XCTUnwrap(FacadePerspective.rectify(els, plane: hoofd, widthM: 12, focalPx: cam.f, imageWidth: cam.W, imageHeight: cam.H))
        XCTAssertEqual(main.elements.map(\.id), [1])
        let ext = try XCTUnwrap(FacadePerspective.rectify(els, plane: uitbouw, widthM: w, focalPx: cam.f, imageWidth: cam.W, imageHeight: cam.H, includeUnassigned: false))
        let raam = FacadePhoto.quantities(try XCTUnwrap(ext.elements.first { $0.id == 3 }), mpp: 1, all: ext.elements)
        XCTAssertEqual(try XCTUnwrap(raam.widthM), 1.5, accuracy: 1e-6)
        XCTAssertEqual(ext.heightM, 3, accuracy: 1e-6)

        let total = FacadePhoto.combine([FacadePhoto.summary(main.elements, mpp: 1), FacadePhoto.summary(ext.elements, mpp: 1)])
        XCTAssertEqual(total.raamkozijnen, 2)
        XCTAssertEqual(total.deurkozijnen, 1)
        XCTAssertEqual(total.kozijnOppervlakM2, 5.4)
    }

    func testCombineKeepsUnknownUnknown() {
        let a = FacadePhoto.Summary(metselwerkNetM2: 10, gevelvlakNetM2: 10, raamkozijnen: 1, deurkozijnen: 0, kozijnOppervlakM2: 2, hwaM1: 0, dakgootM1: 0)
        var b = a; b.metselwerkNetM2 = nil
        XCTAssertNil(FacadePhoto.combine([a, b]).metselwerkNetM2)
        XCTAssertEqual(FacadePhoto.combine([a, a]).metselwerkNetM2, 20)
        XCTAssertEqual(FacadePhoto.combine([a, b]).raamkozijnen, 2)
    }

    func testParsesPlanesDefectsAndHiddenFraction() throws {
        let text = """
        {"planes": [{"id": 1, "kind": "hoofdgevel", "corners": [{"x": 900, "y": 50}, {"x": 100, "y": 60}, {"x": 120, "y": 580}, {"x": 880, "y": 590}]},
                    {"id": 2, "kind": "uitbouw", "corners": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}]},
                    {"id": 3, "kind": "dakkapel", "corners": [{"x": 0, "y": 0}, {"x": 500, "y": 500}, {"x": 500, "y": 0}, {"x": 0, "y": 500}]}],
         "elements": [{"type": "kozijn_raam", "points": [{"x": 200, "y": 200}, {"x": 300, "y": 350}], "material": "hout", "confidence": "high", "note": "deels achter struik", "plane": 1, "hidden_fraction": 0.4},
                      {"type": "kozijn_raam", "points": [{"x": 400, "y": 200}, {"x": 500, "y": 350}], "material": "", "confidence": "high", "note": "", "plane": 7, "hidden_fraction": 3}],
         "defects": [{"type": "afbladderende_verf", "point": {"x": 250, "y": 210}, "note": "verf bladdert"}, {"type": "onzin", "point": {"x": 1, "y": 1}, "note": ""},
                     {"type": "scheur", "point": {"x": 5000, "y": 1}, "note": ""}]}
        """
        let data = try JSONSerialization.data(withJSONObject: ["stop_reason": "end_turn", "content": [["type": "text", "text": text]]] as [String: Any])
        let r = try FacadePhoto.parseRecognition(data, width: 1000, height: 600)
        XCTAssertEqual(r.planes.count, 2, "vlak met drie hoeken overgeslagen; gekruiste hoeken worden op volgorde gezet")
        XCTAssertEqual(r.planes[0].corners[0], [100, 60], "hoeken op volgorde: linksboven eerst")
        XCTAssertEqual(r.elements[0].hiddenFraction, 0.4)
        XCTAssertEqual(r.elements[0].plane, 1)
        XCTAssertNil(r.elements[1].plane, "onbekend vlak wordt niet gegokt")
        XCTAssertNil(r.elements[1].hiddenFraction, "onmogelijke waarde wordt niet overgenomen")
        XCTAssertEqual(r.defects.map(\.type), [.afbladderende_verf])
    }

    func testFocalFromExif() {
        // iPhone-hoofdcamera 26 mm-equivalent, foto 3024 × 4032.
        XCTAssertEqual(FacadePerspective.focalPx(focal35mm: 26, width: 3024, height: 4032)!, 26 * 5040 / hypot(36, 24), accuracy: 1e-9)
    }

    func testOnlyTheMeasuredFacadeCounts() throws {
        // Recht van voren: gevelvlak 0–1000 × 100–700 px. Rechts op de foto nog een stukje zijgevel met een raam (x > 1000).
        let plane = FacadePlane(id: 1, kind: .hoofdgevel, corners: [[0, 100], [1000, 100], [1000, 700], [0, 700]])
        let els = [
            FacadePhotoElement(id: 1, type: .metselwerk, points: [[0, 100], [1300, 100], [1300, 700], [0, 700]], material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 2, type: .kozijn_raam, points: [[100, 200], [300, 200], [300, 400], [100, 400]], material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 3, type: .kozijn_raam, points: [[1100, 200], [1250, 200], [1250, 400], [1100, 400]], material: nil, confidence: "high", note: nil, plane: 1),
            FacadePhotoElement(id: 4, type: .boeiboord, points: [[0, 85], [1000, 85]], material: nil, confidence: "high", note: nil, plane: 1),
        ]
        let r = try XCTUnwrap(FacadePerspective.rectify(els, plane: plane, widthM: 10, focalPx: nil, imageWidth: 1400, imageHeight: 800))
        XCTAssertEqual(r.outside, 1, "het raam op de zijgevel telt niet mee")
        XCTAssertEqual(Set(r.elements.map(\.id)), [1, 2, 4], "het boeideel net boven het muurvlak hoort er wel bij")
        let s = FacadePhoto.summary(r.elements, mpp: 1)
        XCTAssertEqual(try XCTUnwrap(s.metselwerkNetM2), 60 - 4, accuracy: 0.01, "muur geknipt op de gevel: 10 × 6 m min het raam")
        XCTAssertEqual(s.raamkozijnen, 1)
    }
}
