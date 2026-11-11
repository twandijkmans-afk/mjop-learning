import Foundation
import PhotoWalkCore

// Onderdeel A — intelligente fotoronde: wat is er per foto vastgelegd, hoe bruikbaar is het, en welke delen van de gevel zijn gedekt.

/// Echte LiDAR-diepte (ARKit sceneDepth) of alleen een gewone foto. Zonder LiDAR claimt de pijplijn nooit een metrische meting uit het beeld.
public enum DepthSource: String, Codable, Sendable { case LIDAR_SCENE_DEPTH, NONE }

/// Eenvoudige, lokale beeldkwaliteitsmaten (geen AI): scherpte en over-/onderbelichting. Alleen om gericht om een betere foto te vragen.
public struct ImageQuality: Codable, Equatable, Sendable {
    public var sharpness: Double            // variantie van de Laplaciaan (verkleind grijsbeeld)
    public var overexposedFraction: Double  // aandeel pixels >= 250
    public var underexposedFraction: Double // aandeel pixels <= 8
    public var meanLuma: Double
    public init(sharpness: Double, overexposedFraction: Double, underexposedFraction: Double, meanLuma: Double) {
        self.sharpness = sharpness; self.overexposedFraction = overexposedFraction; self.underexposedFraction = underexposedFraction; self.meanLuma = meanLuma
    }
}

public enum ImageQualityMeter {
    /// Meet op een raster met ongeveer `targetWidth` kolommen (snel en onafhankelijk van de sensorresolutie).
    public static func measure(_ img: GrayImage, targetWidth: Int = 480) -> ImageQuality {
        let step = max(1, img.width / max(targetWidth, 1))
        let w = img.width / step, h = img.height / step
        guard w >= 3, h >= 3 else { return ImageQuality(sharpness: 0, overexposedFraction: 0, underexposedFraction: 0, meanLuma: 0) }
        func px(_ x: Int, _ y: Int) -> Double { Double(img.pixels[(y * step) * img.width + x * step]) }
        var sum = 0.0, sum2 = 0.0, n = 0.0, over = 0.0, under = 0.0, luma = 0.0
        for y in 0..<h { for x in 0..<w {
            let v = px(x, y)
            luma += v
            if v >= 250 { over += 1 } else if v <= 8 { under += 1 }
            if x > 0 && y > 0 && x < w - 1 && y < h - 1 {
                let l = px(x - 1, y) + px(x + 1, y) + px(x, y - 1) + px(x, y + 1) - 4 * v
                sum += l; sum2 += l * l; n += 1
            }
        } }
        let total = Double(w * h)
        let mean = n > 0 ? sum / n : 0
        return ImageQuality(sharpness: n > 0 ? max(0, sum2 / n - mean * mean) : 0, overexposedFraction: over / total, underexposedFraction: under / total, meanLuma: luma / total)
    }

    /// Aandeel bijna-witte pixels binnen een (convexe) contour: aanwijzing voor spiegeling in glas.
    public static func glareFraction(_ img: GrayImage, polygon: [Pixel], samples: Int = 24) -> Double? {
        guard polygon.count >= 3 else { return nil }
        let b = polygonBounds(polygon)
        var inside = 0, bright = 0
        for i in 0..<samples { for j in 0..<samples {
            let p = Pixel(b.minU + (Double(j) + 0.5) / Double(samples) * (b.maxU - b.minU), b.minV + (Double(i) + 0.5) / Double(samples) * (b.maxV - b.minV))
            guard inConvexPolygon(p, polygon), p.u >= 0, p.v >= 0, p.u < Double(img.width), p.v < Double(img.height) else { continue }
            inside += 1
            if img.sample(p.u, p.v) >= 250 { bright += 1 }
        } }
        return inside >= 20 ? Double(bright) / Double(inside) : nil
    }
}

/// Kwaliteit van de dieptekaart van één foto. Pixels met laag vertrouwen staan in de app al op NaN en tellen hier dus als ongeldig.
public struct DepthQuality: Codable, Equatable, Sendable {
    public var validFraction: Double
    public var medianRangeM: Double?
    public var inRangeFraction: Double      // aandeel geldige punten binnen het werkbereik van de meetkern
    public init(validFraction: Double, medianRangeM: Double?, inRangeFraction: Double) {
        self.validFraction = validFraction; self.medianRangeM = medianRangeM; self.inRangeFraction = inRangeFraction
    }
    public static func measure(_ d: DepthMap, cfg: Config = Config()) -> DepthQuality {
        var vals: [Double] = []
        vals.reserveCapacity(d.values.count / 4)
        var valid = 0, inRange = 0
        for (i, v) in d.values.enumerated() {
            let z = Double(v)
            guard z.isFinite, z > 0 else { continue }
            valid += 1
            if z >= cfg.depthMinRangeM && z <= cfg.depthMaxRangeM { inRange += 1 }
            if i % 4 == 0 { vals.append(z) }
        }
        let n = max(d.values.count, 1)
        return DepthQuality(validFraction: Double(valid) / Double(n), medianRangeM: vals.isEmpty ? nil : median(vals), inRangeFraction: valid > 0 ? Double(inRange) / Double(valid) : 0)
    }
}

/// Alles wat van één foto is vastgelegd (bewijs). De foto zelf en de dieptekaart blijven lokaal op het toestel; hier staan alleen de kenmerken.
public struct PhotoCapture {
    public var id: String
    public var facadeId: String
    /// AR-sessie (eigen coördinatenstelsel). Alleen binnen één sessie zijn posities vergelijkbaar. nil = onbekend.
    public var worldId: String?
    public var capturedAt: String           // ISO 8601
    public var intrinsics: Intrinsics
    public var pose: Pose
    public var trackingNormal: Bool
    public var depthSource: DepthSource
    public var depthQuality: DepthQuality?
    public var supportDepthFrames: Int      // ondersteunende LiDAR-kaders uit de korte buffer rond de foto
    public var imageQuality: ImageQuality?
    public var excluded: Bool               // door de gebruiker buiten beschouwing gelaten
    /// Dominant verticaal vlak in de dieptekaart van deze foto (wereldcoördinaten), als dat betrouwbaar te fitten was.
    public var facadePlane: FacadePlaneEstimate?
    public init(id: String, facadeId: String, worldId: String?, capturedAt: String, intrinsics: Intrinsics, pose: Pose, trackingNormal: Bool, depthSource: DepthSource,
                depthQuality: DepthQuality?, supportDepthFrames: Int = 0, imageQuality: ImageQuality? = nil, excluded: Bool = false, facadePlane: FacadePlaneEstimate? = nil) {
        self.id = id; self.facadeId = facadeId; self.worldId = worldId; self.capturedAt = capturedAt; self.intrinsics = intrinsics; self.pose = pose
        self.trackingNormal = trackingNormal; self.depthSource = depthSource; self.depthQuality = depthQuality; self.supportDepthFrames = supportDepthFrames
        self.imageQuality = imageQuality; self.excluded = excluded; self.facadePlane = facadePlane
    }

    /// Bouwt het bewijsrecord uit een keyframe van de meetkern (zelfde invoer als de bestaande meting).
    public static func from(view: ViewInput, facadeId: String, worldId: String?, capturedAt: String, imageQuality: ImageQuality?, excluded: Bool = false,
                            cfg: GevelscanConfig = GevelscanConfig()) -> PhotoCapture {
        let dq = view.depth.map { DepthQuality.measure($0) }
        let plane = FacadePlaneEstimator.dominantVerticalPlane(view: view, cfg: cfg, seed: gevelscanHash(view.frameId))
        return PhotoCapture(id: view.frameId, facadeId: facadeId, worldId: worldId, capturedAt: capturedAt, intrinsics: view.intrinsics, pose: view.pose,
                            trackingNormal: view.trackingNormal, depthSource: view.depth == nil ? .NONE : .LIDAR_SCENE_DEPTH, depthQuality: dq,
                            supportDepthFrames: view.supports.count, imageQuality: imageQuality, excluded: excluded, facadePlane: plane)
    }
}

/// Beoordeling van één foto: codes + of de foto geschikt is voor een metrische meting.
public struct PhotoAssessment: Equatable {
    public var photoId: String
    public var flags: [String]              // ONSCHERP, OVERBELICHT, GEEN_LIDAR, DIEPTE_ONVOLDOENDE, BUITEN_DIEPTEBEREIK, TRACKING_BEPERKT, GEEN_GEVELVLAK
    public var metricCapable: Bool          // echte LiDAR-diepte + normale tracking + voldoende dekking
    public var requests: [CaptureRequest]
}

public enum PhotoQualityRules {
    public static func assess(_ p: PhotoCapture, cfg: GevelscanConfig = GevelscanConfig()) -> PhotoAssessment {
        var flags: [String] = [], req: [CaptureRequest] = []
        var metric = true
        if let q = p.imageQuality {
            if q.sharpness < cfg.minSharpness { flags.append("ONSCHERP"); req.append(.init(kind: .SCHERPERE_FOTO, facadeId: p.facadeId, photoId: p.id, reason: "ONSCHERP")) }
            if q.overexposedFraction > cfg.maxOverexposedFraction { flags.append("OVERBELICHT"); req.append(.init(kind: .GLAS_CONTROLEREN, facadeId: p.facadeId, photoId: p.id, reason: "OVERBELICHT")) }
            if q.meanLuma < 30 { flags.append("TE_DONKER") }
        } else { flags.append("BEELDKWALITEIT_ONBEKEND") }
        if p.depthSource == .NONE { flags.append("GEEN_LIDAR"); metric = false }
        else if let d = p.depthQuality {
            if d.validFraction < cfg.minDepthValidFraction { flags.append("DIEPTE_ONVOLDOENDE"); metric = false; req.append(.init(kind: .BETERE_DIEPTE, facadeId: p.facadeId, photoId: p.id, reason: "DIEPTE_ONVOLDOENDE")) }
            else if d.inRangeFraction < 0.5 { flags.append("BUITEN_DIEPTEBEREIK"); metric = false; req.append(.init(kind: .BETERE_DIEPTE, facadeId: p.facadeId, photoId: p.id, reason: "BUITEN_DIEPTEBEREIK")) }
        } else { flags.append("DIEPTE_ONVOLDOENDE"); metric = false }
        if !p.trackingNormal { flags.append("TRACKING_BEPERKT"); metric = false; req.append(.init(kind: .BETERE_DIEPTE, facadeId: p.facadeId, photoId: p.id, reason: "TRACKING_BEPERKT")) }
        if p.depthSource == .LIDAR_SCENE_DEPTH && p.facadePlane == nil { flags.append("GEEN_GEVELVLAK") }
        return PhotoAssessment(photoId: p.id, flags: flags, metricCapable: metric, requests: req)
    }
}

// MARK: gevelvlak

/// Dominant verticaal vlak van één foto (n.x = d in wereldcoördinaten), met de kwaliteit van de fit.
public struct FacadePlaneEstimate: Equatable {
    public var n: Vec3
    public var d: Double
    public var inlierRatio: Double
    public var rmsM: Double
    public init(n: Vec3, d: Double, inlierRatio: Double, rmsM: Double) { self.n = n; self.d = d; self.inlierRatio = inlierRatio; self.rmsM = rmsM }
}

public enum FacadePlaneEstimator {
    /// Fit het grootste vlak door de (uitgedunde) LiDAR-punten van een foto en accepteert het alleen als het verticaal is en genoeg steun heeft.
    /// Gebruikt de bestaande RANSAC-vlakfit van de meetkern. Geen diepte of slechte tracking => nil (nooit een vlak uit alleen een foto).
    public static func dominantVerticalPlane(view: ViewInput, cfg: GevelscanConfig = GevelscanConfig(), seed: UInt64 = 1) -> FacadePlaneEstimate? {
        guard view.trackingNormal, let d = view.depth, d.width > 0, d.height > 0 else { return nil }
        let core = Config()
        let sx = Double(view.intrinsics.width) / Double(d.width), sy = Double(view.intrinsics.height) / Double(d.height)
        let stride = max(1, Int((Double(d.width * d.height) / 2500.0).squareRoot()))
        var pts: [Vec3] = []
        var i = stride / 2
        while i < d.height {
            var j = stride / 2
            while j < d.width {
                let z = Double(d.values[i * d.width + j])
                if z.isFinite, z >= core.depthMinRangeM, z <= core.depthMaxRangeM {
                    pts.append(unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy), depthZ: z))
                }
                j += stride
            }
            i += stride
        }
        guard pts.count >= 80, let fit = fitPlaneRansac(pts, threshold: cfg.facadePlaneThresholdM, iterations: 200, seed: seed) else { return nil }
        guard fit.inlierRatio >= cfg.facadePlaneMinInlierRatio, abs(fit.n.dot(worldUp)) <= cfg.facadeMaxVertical else { return nil }
        // normaal naar de camera gericht (eenduidig teken, zodat vlakken van verschillende foto's vergelijkbaar zijn)
        let toCam = view.pose.t.dot(fit.n) - fit.d
        let s: Double = toCam >= 0 ? 1 : -1
        return FacadePlaneEstimate(n: fit.n * s, d: fit.d * s, inlierRatio: fit.inlierRatio, rmsM: fit.rmsM)
    }
}

/// 2D-assenstelsel op een verticaal gevelvlak: x horizontaal langs de gevel, y omhoog. Voor dekking en objectvergelijking.
public struct PlaneFrame2D {
    public var n: Vec3, d: Double
    public var origin: Vec3, xAxis: Vec3, yAxis: Vec3
    public init?(n: Vec3, d: Double) {
        let nn = n.normalized
        var x = worldUp.cross(nn)
        if x.norm < 1e-6 { return nil }                 // horizontaal vlak: geen gevel
        x = x.normalized
        self.n = nn; self.d = d / max(n.norm, 1e-12); self.xAxis = x; self.yAxis = nn.cross(x).normalized; self.origin = nn * self.d
    }
    public func to2D(_ w: Vec3) -> Pixel { let r = w - origin; return Pixel(r.dot(xAxis), r.dot(yAxis)) }
    /// Doorsnijding van een beeldpunt-straal met het vlak, in 2D-vlakcoördinaten.
    public func project(pixel: Pixel, pose: Pose, intr: Intrinsics) -> Pixel? {
        let (o, dirs) = raysWorld(pose: pose, intr: intr, pixels: [pixel])
        guard let hit = intersectRayPlane(origin: o, dir: dirs[0], n: n, d: d) else { return nil }
        return to2D(hit.point)
    }
}

// MARK: actieve gevel herkennen

public enum FacadeRecognizer {
    /// Zijn twee gevelvlakken (zelfde AR-sessie) hetzelfde vlak?
    public static func samePlane(_ a: FacadePlaneEstimate, _ b: FacadePlaneEstimate, cfg: GevelscanConfig = GevelscanConfig()) -> Bool {
        let c = max(-1, min(1, a.n.dot(b.n)))
        return acos(c) * 180 / Double.pi <= cfg.facadeSameNormalDeg && abs(a.d - b.d) <= cfg.facadeSameOffsetM
    }

    /// Bij welke al gefotografeerde gevel hoort een nieuwe foto? Alleen binnen dezelfde AR-sessie te bepalen. nil = onbekend (geen gok).
    /// Twee gevels die allebei passen => nil (dubbelzinnig).
    public static func recognize(plane: FacadePlaneEstimate?, worldId: String?, known: [PhotoCapture], cfg: GevelscanConfig = GevelscanConfig()) -> String? {
        guard let plane, let worldId else { return nil }
        var hits = Set<String>()
        for k in known where !k.excluded && k.worldId == worldId {
            if let kp = k.facadePlane, samePlane(plane, kp, cfg: cfg) { hits.insert(k.facadeId) }
        }
        return hits.count == 1 ? hits.first : nil
    }

    /// Foto's die volgens hun gevelvlak NIET bij de gekozen gevel lijken te horen (zelfde sessie, duidelijk ander vlak dan de meerderheid).
    /// Alleen een signaal; de indeling wordt nooit stil gewijzigd.
    public static func mismatchedPhotos(_ photos: [PhotoCapture], cfg: GevelscanConfig = GevelscanConfig()) -> [String] {
        var out: [String] = []
        let groups = Dictionary(grouping: photos.filter { !$0.excluded && $0.facadePlane != nil && $0.worldId != nil }) { $0.facadeId + "|" + ($0.worldId ?? "") }
        for (_, g) in groups where g.count >= 3 {
            // meerderheidsvlak = de foto waar de meeste andere foto's mee overeenkomen; wie daar niet bij past, valt op
            func agreeing(_ p: PhotoCapture) -> Int { g.filter { $0.id != p.id && samePlane(p.facadePlane!, $0.facadePlane!, cfg: cfg) }.count }
            guard let ref = g.max(by: { (agreeing($0), $1.id) < (agreeing($1), $0.id) }), (agreeing(ref) + 1) * 2 > g.count else { continue }
            for p in g where p.id != ref.id && !samePlane(p.facadePlane!, ref.facadePlane!, cfg: cfg) { out.append(p.id) }
        }
        return out.sorted()
    }
}

// MARK: dekking van de gevel

/// Welk deel van een gevel is gefotografeerd? Raster op het gevelvlak (alleen met LiDAR-vlak te bepalen).
public struct FacadeCoverage: Equatable {
    public var facadeId: String
    public var determinable: Bool           // false: geen gevelvlak (geen LiDAR of meerdere sessies) => dekking onbekend, niet "volledig"
    public var widthM: Double?, heightM: Double?
    public var columns: Int, rows: Int
    /// Aantal foto's per rastercel (rij 0 = bovenaan), rij-hoofdvolgorde.
    public var cellViews: [Int]
    public var coveredFraction: Double?     // aandeel cellen binnen de omhullende rechthoek met >= 1 foto
    public var multiViewFraction: Double?   // aandeel met >= 2 foto's
    public var photosUsed: Int, photosWithoutPlane: Int
    public var flags: [String]              // DEKKING_ONBEKEND, GATEN_IN_DEKKING, MEERDERE_SESSIES
}

public enum FacadeCoverageRules {
    public static func evaluate(facadeId: String, photos: [PhotoCapture], cfg: GevelscanConfig = GevelscanConfig()) -> FacadeCoverage {
        let own = photos.filter { $0.facadeId == facadeId && !$0.excluded }
        let worlds = Set(own.compactMap { $0.worldId })
        var flags: [String] = []
        if worlds.count > 1 { flags.append("MEERDERE_SESSIES") }
        // referentievlak: de foto met de beste vlakfit in de grootste sessie; alleen foto's op hetzelfde vlak tellen mee
        let byWorld = Dictionary(grouping: own.filter { $0.facadePlane != nil && $0.worldId != nil }) { $0.worldId! }
        guard let main = byWorld.max(by: { ($0.value.count, $1.key) < ($1.value.count, $0.key) })?.value,
              let ref = main.max(by: { ($0.facadePlane!.inlierRatio, $1.id) < ($1.facadePlane!.inlierRatio, $0.id) }),
              let frame = PlaneFrame2D(n: ref.facadePlane!.n, d: ref.facadePlane!.d) else {
            return FacadeCoverage(facadeId: facadeId, determinable: false, widthM: nil, heightM: nil, columns: 0, rows: 0, cellViews: [], coveredFraction: nil,
                                  multiViewFraction: nil, photosUsed: 0, photosWithoutPlane: own.count, flags: flags + ["DEKKING_ONBEKEND"])
        }
        var quads: [[Pixel]] = []
        for p in main where FacadeRecognizer.samePlane(p.facadePlane!, ref.facadePlane!, cfg: cfg) {
            let W = Double(p.intrinsics.width), H = Double(p.intrinsics.height)
            let corners = [Pixel(0, 0), Pixel(W, 0), Pixel(W, H), Pixel(0, H)].compactMap { frame.project(pixel: $0, pose: p.pose, intr: p.intrinsics) }
            if corners.count == 4, isSimpleConvexQuad(corners) { quads.append(corners) }
        }
        guard !quads.isEmpty else {
            return FacadeCoverage(facadeId: facadeId, determinable: false, widthM: nil, heightM: nil, columns: 0, rows: 0, cellViews: [], coveredFraction: nil,
                                  multiViewFraction: nil, photosUsed: 0, photosWithoutPlane: own.count, flags: flags + ["DEKKING_ONBEKEND"])
        }
        let all = quads.flatMap { $0 }
        let x0 = all.map { $0.u }.min()!, x1 = all.map { $0.u }.max()!, y0 = all.map { $0.v }.min()!, y1 = all.map { $0.v }.max()!
        let cols = min(200, max(1, Int(((x1 - x0) / cfg.coverageCellM).rounded(.up)))), rows = min(200, max(1, Int(((y1 - y0) / cfg.coverageCellM).rounded(.up))))
        var cells = [Int](repeating: 0, count: cols * rows)
        for r in 0..<rows { for c in 0..<cols {
            let pt = Pixel(x0 + (Double(c) + 0.5) * (x1 - x0) / Double(cols), y1 - (Double(r) + 0.5) * (y1 - y0) / Double(rows))
            cells[r * cols + c] = quads.filter { inConvexPolygon(pt, $0) }.count
        } }
        let covered = Double(cells.filter { $0 >= 1 }.count) / Double(cells.count), multi = Double(cells.filter { $0 >= 2 }.count) / Double(cells.count)
        if covered < cfg.coverageMinFraction { flags.append("GATEN_IN_DEKKING") }
        return FacadeCoverage(facadeId: facadeId, determinable: true, widthM: round(x1 - x0, 2), heightM: round(y1 - y0, 2), columns: cols, rows: rows, cellViews: cells,
                              coveredFraction: round(covered, 3), multiViewFraction: round(multi, 3), photosUsed: quads.count,
                              photosWithoutPlane: own.count - quads.count, flags: flags)
    }
}
