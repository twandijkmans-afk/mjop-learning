import Foundation
import XCTest
@testable import Gevelscan
import PhotoWalkCore

/// SYNTHETISCHE gevel voor de tests van Gevelscanner 2.0: wand op Z = 0, kozijnen terugliggend, glas nog dieper, met tussenstijlen/-dorpels.
/// Hiermee wordt de LOGICA getest (koppelen, tellen, herkomst, statussen). Het bewijst NIETS over de nauwkeurigheid van echte iPhone-LiDAR.
struct SynWindow {
    var x0: Double, y0: Double, w: Double, h: Double
    var cols = 1, rows = 1
    var profile = 0.07, mullion = 0.06, recess = 0.06, glassRecess = 0.06
    /// Glasvlakken (x0, y0, w, h) in wereldcoördinaten, rij voor rij van boven naar beneden.
    var panes: [(Double, Double, Double, Double)] {
        let gw = (w - 2 * profile - Double(cols - 1) * mullion) / Double(cols), gh = (h - 2 * profile - Double(rows - 1) * mullion) / Double(rows)
        var out: [(Double, Double, Double, Double)] = []
        for r in 0..<rows { for c in 0..<cols {
            out.append((x0 + profile + Double(c) * (gw + mullion), y0 + h - profile - Double(r + 1) * gh - Double(r) * mullion, gw, gh))
        } }
        return out
    }
    var glassAreaM2: Double { panes.reduce(0) { $0 + $1.2 * $1.3 } }
}

enum Syn {
    static let intr = Intrinsics(fx: 1500, fy: 1500, cx: 960, cy: 720, width: 1920, height: 1440)

    /// Camera kijkt langs -Z met een draaiing om de verticale as (zelfde conventie als de bestaande LiDAR-tests).
    static func pose(_ p: Vec3, yawDeg: Double = 0) -> Pose {
        let a = yawDeg * Double.pi / 180, c = cos(a), s = sin(a)
        return Pose(rows: [Vec3(c, 0, -s), Vec3(0, -1, 0), Vec3(-s, 0, -c)], t: p)
    }

    static func render(_ windows: [SynWindow], pos: Vec3, id: String, seed: UInt64 = 1, yawDeg: Double = 0, noise: Double = 0.004, holeP: Double = 0.02, tracking: Bool = true,
                       withDepth: Bool = true, glassHoles: Bool = false, depthSize: (Int, Int) = (192, 256)) -> ViewInput {
        let (Hd, Wd) = depthSize
        let p = pose(pos, yawDeg: yawDeg)
        guard withDepth else { return ViewInput(frameId: id, intrinsics: intr, pose: p, trackingNormal: tracking, depth: nil) }
        var rng = SplitMix64(seed: seed)
        var vals = [Float](repeating: .nan, count: Hd * Wd)
        let sx = Double(intr.width) / Double(Wd), sy = Double(intr.height) / Double(Hd)
        func inside(_ x: Double, _ y: Double, _ r: (Double, Double, Double, Double)) -> Bool { x > r.0 && x < r.0 + r.2 && y > r.1 && y < r.1 + r.3 }
        for i in 0..<Hd { for j in 0..<Wd {
            let dir = p.rotate(intr.cameraRay(Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy)))
            guard dir.z < -1e-6 else { continue }
            func hit(_ z: Double) -> (t: Double, x: Double, y: Double) { let t = (z - pos.z) / dir.z; return (t, pos.x + t * dir.x, pos.y + t * dir.y) }
            let wall = hit(0)
            var depth: Double? = wall.t
            if let w = windows.first(where: { inside(wall.x, wall.y, ($0.x0, $0.y0, $0.w, $0.h)) }) {
                let f = hit(-w.recess)
                if inside(f.x, f.y, (w.x0, w.y0, w.w, w.h)) {
                    let g = hit(-(w.recess + w.glassRecess))
                    if w.panes.contains(where: { inside(f.x, f.y, $0) }) { depth = glassHoles ? nil : g.t } else { depth = f.t }
                } else { depth = nil }                       // dagkant: geen waarde
            }
            if let d = depth, rng.uniform() >= holeP { vals[i * Wd + j] = Float(d + rng.gaussian() * (noise + 0.002 * d)) }
        } }
        return ViewInput(frameId: id, intrinsics: intr, pose: p, trackingNormal: tracking, depth: DepthMap(width: Wd, height: Hd, values: vals))
    }

    static func px(_ x: Double, _ y: Double, _ z: Double, _ pose: Pose) -> Pixel { project(pose: pose, intr: intr, world: Vec3(x, y, z)).0 }

    /// Buitencontour (TL, TR, BR, BL) op het kozijnvlak, in pixels; `inset` < 0 maakt het kader groter.
    static func frameQuad(_ w: SynWindow, pose: Pose, inset: Double = 0) -> [Pixel] {
        let z = -w.recess
        return [px(w.x0 + inset, w.y0 + w.h - inset, z, pose), px(w.x0 + w.w - inset, w.y0 + w.h - inset, z, pose), px(w.x0 + w.w - inset, w.y0 + inset, z, pose), px(w.x0 + inset, w.y0 + inset, z, pose)]
    }

    /// Glascontouren zoals de camera ze ziet (op de werkelijke diepte van het glas).
    static func paneQuads(_ w: SynWindow, pose: Pose) -> [[Pixel]] {
        let z = -(w.recess + w.glassRecess)
        return w.panes.map { r in [px(r.0, r.1 + r.3, z, pose), px(r.0 + r.2, r.1 + r.3, z, pose), px(r.0 + r.2, r.1, z, pose), px(r.0, r.1, z, pose)] }
    }

    /// Eén waarneming van een kozijn op een foto, gemeten met de BESTAANDE niveau-A-meting.
    static func sighting(_ w: SynWindow, view: ViewInput, id: String, facade: String = "Voorgevel", world: String? = "W1", confirmed: Bool = false, withPanes: Bool = true,
                         inset: Double = 0, detector: DetectorDescriptor = .visionCandidates) -> FrameSighting {
        let quad = frameQuad(w, pose: view.pose, inset: inset)
        let r = measureDepthView(view, corners: quad, seed: gevelscanHash(id))
        let panes = withPanes ? paneQuads(w, pose: view.pose).enumerated().map { ElementDetection(id: "\(id)-P\($0 + 1)", photoId: view.frameId, elementClass: .GLASVLAK, polygon: $1, score: 0.9, detector: detector, parentId: id) } : []
        return FrameSighting(id: id, photoId: view.frameId, facadeId: facade, worldId: world, polygon: quad, pose: view.pose, intrinsics: view.intrinsics, result: r,
                             contourUserConfirmed: confirmed, contourStatus: confirmed ? .USER_CONFIRMED : .DETECTED_ENCLOSING_PANES, evidence: withPanes ? .NESTED_PANES : .SINGLE,
                             detector: detector, score: 0.9, panes: panes)
    }

    static func photo(_ view: ViewInput, facade: String = "Voorgevel", world: String? = "W1", quality: ImageQuality? = ImageQuality(sharpness: 400, overexposedFraction: 0.01, underexposedFraction: 0.01, meanLuma: 120)) -> PhotoCapture {
        PhotoCapture.from(view: view, facadeId: facade, worldId: world, capturedAt: "2026-11-11T10:00:00Z", imageQuality: quality)
    }

    static let validated = PipelineValidation(geometryFieldValidated: true, detectorValidated: true)
}

extension XCTestCase {
    func codes(_ r: LevelResult?) -> [String] { (r?.flags ?? []).map { $0.code } }
}
