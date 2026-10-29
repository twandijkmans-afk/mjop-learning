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
        list.append(VisionContourDetector())
        return list
    }

    static var statusText: String {
        let ml = coreMLModelURL != nil ? "Core ML-kozijnmodel: geladen (niet gevalideerd)" : "Core ML-kozijnmodel: niet geïnstalleerd"
        return "Herkenning: Apple Vision-rechthoeken en -contouren als KANDIDAAT-generator, geordend tot buitenkozijn en glasvlakken (geen kozijndetector, niet gevalideerd). \(ml). Alles lokaal op het toestel."
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
        // GEEN ontdubbeling van binnenvakken meer: geneste vierhoeken zijn juist het bewijs voor buitenkozijn + glas (zie ContourOrganizer).
        return CandidateFilter.basic(cands, imageWidth: W, imageHeight: H)
    }
}

/// Contourherkenning van Apple Vision (VNDetectContoursRequest, on-device). Vindt gesloten contouren met hun hiërarchie (buitenrand met
/// binnenranden); hier worden alleen contouren gebruikt die als convexe vierhoek te benaderen zijn. Vult de rechthoekdetector aan, vooral voor
/// de buitenrand van het kozijn tegen metselwerk. Alleen KANDIDATEN; niet gevalideerd op echte gevels.
struct VisionContourDetector: WindowDetecting {
    let name = "VN_CONTOUR_QUAD_CANDIDATE"
    var maxContours = 2000

    func detect(_ image: CGImage) -> [WindowCandidate] {
        let W = Double(image.width), H = Double(image.height)
        let req = VNDetectContoursRequest()
        req.contrastAdjustment = 1.5
        req.detectsDarkOnLight = true
        req.maximumImageDimension = 1024
        #if targetEnvironment(simulator)
        req.usesCPUOnly = true
        #endif
        let handler = VNImageRequestHandler(cgImage: image, orientation: .right, options: [:])
        do { try handler.perform([req]) } catch { return [] }
        guard let obs = req.results?.first else { return [] }
        let vt = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 1, viewportHeight: 1)
        let dispW = H, dispH = W
        func native(_ x: Float, _ y: Float) -> Pixel { vt.nativePoint(fromDisplay: Pixel(Double(x) * dispW, (1 - Double(y)) * dispH)) }
        var out: [WindowCandidate] = []
        let n = min(obs.contourCount, maxContours)
        for i in 0..<n {
            guard let c = try? obs.contour(at: i), c.pointCount >= 4 else { continue }
            guard let approx = try? c.polygonApproximation(epsilon: 0.01), approx.pointCount == 4 else { continue }
            let p = approx.normalizedPoints
            var q = [native(p[0].x, p[0].y), native(p[1].x, p[1].y), native(p[2].x, p[2].y), native(p[3].x, p[3].y)]
            q = CandidateFilter.orderTLTRBRBL(q, imageWidth: W, imageHeight: H)
            out.append(WindowCandidate(corners: q, detector: name, score: 0.5))
        }
        return CandidateFilter.basic(out, imageWidth: W, imageHeight: H)
    }
}

/// CGImage -> grijswaardenbeeld in NATIVE pixels (voor de randzoeker "vergroot naar buitenkozijn"). Alleen lokaal in het geheugen.
enum GrayImageLoader {
    static func gray(_ image: CGImage) -> GrayImage? {
        let w = image.width, h = image.height
        guard w > 0, h > 0 else { return nil }
        var px = [UInt8](repeating: 0, count: w * h)
        let ok: Bool = px.withUnsafeMutableBytes { (buf: UnsafeMutableRawBufferPointer) -> Bool in
            guard let ctx = CGContext(data: buf.baseAddress, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w, space: CGColorSpaceCreateDeviceGray(),
                                      bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return false }
            ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        return ok ? GrayImage(width: w, height: h, pixels: px) : nil
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
        return CandidateFilter.basic(cands, imageWidth: W, imageHeight: H)
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

    /// Een kleinere kandidaat die (vrijwel) geheel binnen een grotere, niet gevelgrote kandidaat ligt, is waarschijnlijk de glasruit of een vak van hetzelfde kozijn.
    static func contained(_ small: [Pixel], in big: [Pixel], totalArea: Double) -> Bool {
        let (sx0, sy0, sx1, sy1) = bounds(small), (bx0, by0, bx1, by1) = bounds(big)
        let iw = max(0, min(sx1, bx1) - max(sx0, bx0)), ih = max(0, min(sy1, by1) - max(sy0, by0))
        let smallBox = (sx1 - sx0) * (sy1 - sy0)
        return smallBox > 0 && (iw * ih) / smallBox > 0.85 && area(big) < 0.3 * totalArea
    }

    /// Alleen geldige vormen (convexe vierhoek, niet te klein, niet het hele beeld). Ontdubbelen en ordenen gebeurt in ContourOrganizer (PhotoWalkCore, getest).
    static func basic(_ cands: [WindowCandidate], imageWidth W: Double, imageHeight H: Double) -> [WindowCandidate] {
        let total = W * H
        return cands.filter { c in let a = area(c.corners); return a > 0.0015 * total && a < 0.9 * total && isSimpleConvexQuad(c.corners, imageArea: total) }
    }

    /// Zet vier punten in de volgorde linksboven, rechtsboven, rechtsonder, linksonder zoals het beeld RECHTOP getoond wordt (portret, .right).
    static func orderTLTRBRBL(_ q: [Pixel], imageWidth W: Double, imageHeight H: Double) -> [Pixel] {
        let vt = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 1, viewportHeight: 1)
        let d = q.map { vt.displayPoint(fromNative: $0) }
        let cu = d.map { $0.u }.reduce(0, +) / 4, cv = d.map { $0.v }.reduce(0, +) / 4
        // hoek t.o.v. het midden, beginnend linksboven, met de klok mee (v omlaag)
        let idx = (0..<4).sorted { atan2(d[$0].v - cv, d[$0].u - cu) < atan2(d[$1].v - cv, d[$1].u - cu) }
        let ordered = idx.map { q[$0] }          // volgorde: linksboven (hoek ~ -135°), rechtsboven, rechtsonder, linksonder
        return ordered
    }

    /// Oude filter (v1): hield bij overlap de grotere en verwijderde binnenvakken. Niet meer gebruikt voor de detectie; blijft voor vergelijking.
    static func clean(_ cands: [WindowCandidate], imageWidth W: Double, imageHeight H: Double, maxCount: Int = 25) -> [WindowCandidate] {
        let total = W * H
        let valid = cands.filter { c in
            let a = area(c.corners); return a > 0.0015 * total && a < 0.6 * total && isSimpleConvexQuad(c.corners, imageArea: total)
        }
        let ordered = valid.sorted { (area($0.corners), $0.score) > (area($1.corners), $1.score) }          // groot -> klein
        var kept: [WindowCandidate] = []
        for c in ordered where !kept.contains(where: { iou($0.corners, c.corners) > 0.55 || contained(c.corners, in: $0.corners, totalArea: total) }) { kept.append(c) }
        // reproduceerbare volgorde: van links naar rechts, dan boven naar onder in het rechtop getoonde beeld
        let vt = ViewportTransform(nativeWidth: W, nativeHeight: H, orientation: .right, viewportWidth: 1, viewportHeight: 1)
        func key(_ c: WindowCandidate) -> (Double, Double) { let d = vt.displayPoint(fromNative: c.corners[0]); return (d.u, d.v) }
        return Array(kept.prefix(maxCount)).sorted { key($0) < key($1) }
    }
}
