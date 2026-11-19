import UIKit
import Vision

/// Zoekt rechthoeken (kozijnen, deuren, soms het hele gevelvlak) in de foto met Apple Vision, op het toestel zelf: gratis, zonder internet.
/// De uitkomst gebruikt `EdgeSnap` om de hoeken van Claude op de echte randen te zetten.
enum VisionRectangles {
    /// Rechthoeken in pixels van een rechtopstaand beeld van `size` (dezelfde schaal als de herkenning), als vier hoeken
    /// linksboven, rechtsboven, rechtsonder, linksonder.
    static func detect(in image: UIImage, size: CGSize) async -> [[[Double]]] {
        guard let cg = image.cgImage else { return [] }
        return await withCheckedContinuation { cont in
            DispatchQueue.global(qos: .userInitiated).async {
                let req = VNDetectRectanglesRequest()
                req.maximumObservations = 0          // geen maximum
                req.minimumSize = 0.02
                req.minimumConfidence = 0.4
                req.minimumAspectRatio = 0.1
                req.maximumAspectRatio = 1.0
                req.quadratureTolerance = 25         // graden: een kozijn schuin van opzij is geen perfecte rechthoek
                do { try VNImageRequestHandler(cgImage: cg, orientation: .up).perform([req]) } catch { cont.resume(returning: []); return }
                let W = Double(size.width), H = Double(size.height)
                func p(_ q: CGPoint) -> [Double] { [Double(q.x) * W, (1 - Double(q.y)) * H] }   // Vision: oorsprong linksonder, genormaliseerd
                let out: [[[Double]]] = (req.results ?? []).map { o in [p(o.topLeft), p(o.topRight), p(o.bottomRight), p(o.bottomLeft)] }
                cont.resume(returning: out)
            }
        }
    }
}
