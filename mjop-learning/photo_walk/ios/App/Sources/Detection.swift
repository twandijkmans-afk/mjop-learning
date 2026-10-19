import CoreML
import UIKit
import Vision
import PhotoWalkCore

/// Een KANDIDAAT voor een kozijn. Nooit een bevestigd kozijn: de herkenning is niet gevalideerd op echte gebouwen.
struct WindowCandidate {
    var corners: [Pixel]        // NATIVE pixels van het keyframe, volgorde TL, TR, BR, BL zoals het kozijn rechtop staat
    var detector: String
    var score: Double
}

protocol WindowDetecting {
    var name: String { get }
    func detect(_ image: CGImage) -> [WindowCandidate]
}

/// Welke lokale herkenning er daadwerkelijk beschikbaar is (voor de UI en het exportrecord).
enum DetectorCatalog {
    /// Een eigen Core ML-kozijnmodel (YOLO-achtig, `WindowDetector.mlmodelc`) wordt gebruikt ALS het in de app-bundle zit. Er is geen model meegeleverd:
    /// er zijn geen trainingsdata en geen vrij te gebruiken, gevalideerd kozijnmodel in deze repository; zie docs/photo_to_quantity_v2.md.
    static var coreMLModelURL: URL? { Bundle.main.url(forResource: "WindowDetector", withExtension: "mlmodelc") }

    static func available() -> [WindowDetecting] {
        var list: [WindowDetecting] = []
        if let m = CoreMLWindowDetector() { list.append(m) }
        list.append(VisionRectangleDetector())
        return list
    }

    static var statusText: String {
        let ml = coreMLModelURL != nil ? "Core ML-kozijnmodel: geladen (niet gevalideerd)" : "Core ML-kozijnmodel: niet geïnstalleerd"
        return "Herkenning: Apple Vision-rechthoekdetector als KANDIDAAT-generator (geen kozijndetector, niet gevalideerd). \(ml). Alles lokaal op het toestel."
    }
}

/// Algemene rechthoekdetector van Apple Vision (VNDetectRectanglesRequest, on-device). Vindt contrastrijke vierhoeken: ramen, maar ook deuren,
/// borden, steenpatronen, schaduwen. Daarom ALLEEN kandidaten; mogelijk wordt de glasruit of een deel van het kozijn gevonden i.p.v. de buitenmaat.
struct VisionRectangleDetector: WindowDetecting {
    let name = "VN_RECTANGLE_CANDIDATE"

    func detect(_ image: CGImage) -> [WindowCandidate] {
        let W = Double(image.width), H = Double(image.height)
        let req = VNDetectRectanglesRequest()
        req.maximumObservations = 40
        req.minimumConfidence = 0.3
        req.minimumAspectRatio = 0.12
        req.maximumAspectRatio = 1.0
        req.minimumSize = 0.025
        req.quadratureTolerance = 25
        #if targetEnvironment(simulator)
        req.usesCPUOnly = true
        #endif
        // .right: het native landscape-beeld wordt als rechtop (portret) geanalyseerd, zodat ramen als staande rechthoeken worden gezien.
        let handler = VNImageRequestHandler(cgImage: image, orientation: .right, options: [:])
        do { try handler.perform([req]) } catch { return [] }
        let vt = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 1, viewportHeight: 1)
        let dispW = H, dispH = W                         // afmeting van het rechtop getoonde beeld in pixels
        func native(_ p: CGPoint) -> Pixel { vt.nativePoint(fromDisplay: Pixel(Double(p.x) * dispW, (1 - Double(p.y)) * dispH)) }
        let cands: [WindowCandidate] = (req.results ?? []).map {
            WindowCandidate(corners: [native($0.topLeft), native($0.topRight), native($0.bottomRight), native($0.bottomLeft)], detector: name, score: Double($0.confidence))
        }
        return CandidateFilter.clean(cands, imageWidth: W, imageHeight: H)
    }
}

/// Optioneel eigen Core ML-model (objectdetectie, klasse "window"/"kozijn"). Zonder model in de bundle bestaat dit pad niet.
struct CoreMLWindowDetector: WindowDetecting {
    let name = "COREML_WINDOW_MODEL"
    private let model: VNCoreMLModel

    init?() {
        guard let url = DetectorCatalog.coreMLModelURL, let ml = try? MLModel(contentsOf: url), let vm = try? VNCoreMLModel(for: ml) else { return nil }
        model = vm
    }

    func detect(_ image: CGImage) -> [WindowCandidate] {
        let W = Double(image.width), H = Double(image.height)
        let req = VNCoreMLRequest(model: model)
        req.imageCropAndScaleOption = .scaleFit
        let handler = VNImageRequestHandler(cgImage: image, orientation: .right, options: [:])
        do { try handler.perform([req]) } catch { return [] }
        let vt = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 1, viewportHeight: 1)
        let dispW = H, dispH = W
        func native(_ x: Double, _ y: Double) -> Pixel { vt.nativePoint(fromDisplay: Pixel(x * dispW, (1 - y) * dispH)) }
        let cands: [WindowCandidate] = ((req.results as? [VNRecognizedObjectObservation]) ?? []).compactMap { o in
            guard let top = o.labels.first, ["window", "kozijn", "raam"].contains(where: { top.identifier.lowercased().contains($0) }) else { return nil }
            let b = o.boundingBox          // genormaliseerd, oorsprong linksonder, in het rechtop getoonde beeld
            let corners = [native(b.minX, b.maxY), native(b.maxX, b.maxY), native(b.maxX, b.minY), native(b.minX, b.minY)]
            return WindowCandidate(corners: corners, detector: name, score: Double(top.confidence))
        }
        return CandidateFilter.clean(cands, imageWidth: W, imageHeight: H)
    }
}

/// Filtert en ontdubbelt kandidaten (deterministisch). Bij sterk overlappende kaders blijft de GROTERE staan (buitenmaat i.p.v. glasruit).
enum CandidateFilter {
    static func area(_ c: [Pixel]) -> Double { abs(signedArea(c)) }
    static func bounds(_ c: [Pixel]) -> (Double, Double, Double, Double) {
        (c.map { $0.u }.min()!, c.map { $0.v }.min()!, c.map { $0.u }.max()!, c.map { $0.v }.max()!)
    }
    static func iou(_ a: [Pixel], _ b: [Pixel]) -> Double {
        let (ax0, ay0, ax1, ay1) = bounds(a), (bx0, by0, bx1, by1) = bounds(b)
        let iw = max(0, min(ax1, bx1) - max(ax0, bx0)), ih = max(0, min(ay1, by1) - max(ay0, by0))
        let inter = iw * ih, uni = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
        return uni > 0 ? inter / uni : 0
    }

    static func clean(_ cands: [WindowCandidate], imageWidth W: Double, imageHeight H: Double, maxCount: Int = 25) -> [WindowCandidate] {
        let total = W * H
        let valid = cands.filter { c in
            let a = area(c.corners); return a > 0.0015 * total && a < 0.6 * total && isSimpleConvexQuad(c.corners, imageArea: total)
        }
        let ordered = valid.sorted { (area($0.corners), $0.score) > (area($1.corners), $1.score) }          // groot -> klein
        var kept: [WindowCandidate] = []
        for c in ordered where !kept.contains(where: { iou($0.corners, c.corners) > 0.55 }) { kept.append(c) }
        // reproduceerbare volgorde: van links naar rechts, dan boven naar onder in het rechtop getoonde beeld
        let vt = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 1, viewportHeight: 1)
        func key(_ c: WindowCandidate) -> (Double, Double) { let d = vt.displayPoint(fromNative: c.corners[0]); return (d.u, d.v) }
        return Array(kept.prefix(maxCount)).sorted { key($0) < key($1) }
    }
}
