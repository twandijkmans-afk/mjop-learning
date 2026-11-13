import Foundation
import XCTest
@testable import MJOPEngine

final class PerspectiveTests: XCTestCase {
    /// Een virtuele camera (brandpunt f pixels, hoofdpunt in het midden) fotografeert een vlak; geeft pixels terug.
    struct Camera {
        var f = 2800.0, W = 3000.0, H = 4000.0
        var yaw = 0.0, pitch = 0.0, roll = 0.0, distance = 25.0
        func project(_ x: Double, _ y: Double) -> [Double] {   // x naar rechts, y omhoog, in meters op het vlak
            var p = [x, y, 0.0]
            func rx(_ v: [Double], _ a: Double) -> [Double] { [v[0], cos(a) * v[1] - sin(a) * v[2], sin(a) * v[1] + cos(a) * v[2]] }
            func ry(_ v: [Double], _ a: Double) -> [Double] { [cos(a) * v[0] + sin(a) * v[2], v[1], -sin(a) * v[0] + cos(a) * v[2]] }
            func rz(_ v: [Double], _ a: Double) -> [Double] { [cos(a) * v[0] - sin(a) * v[1], sin(a) * v[0] + cos(a) * v[1], v[2]] }
            p = rz(ry(rx(p, pitch), yaw), roll)
            p[2] += distance
            return [f * p[0] / p[2] + W / 2, H / 2 - f * p[1] / p[2]]
        }
        /// Rechthoek van w × h meter rond het midden: linksboven, rechtsboven, rechtsonder, linksonder.
        func rect(_ w: Double, _ h: Double, x0: Double = 0, y0: Double = 0) -> [[Double]] {
            [project(x0 - w / 2, y0 + h / 2), project(x0 + w / 2, y0 + h / 2), project(x0 + w / 2, y0 - h / 2), project(x0 - w / 2, y0 - h / 2)]
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
}
