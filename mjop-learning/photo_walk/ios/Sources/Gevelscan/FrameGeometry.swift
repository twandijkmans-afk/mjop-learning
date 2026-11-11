import Foundation
import PhotoWalkCore

// Onderdeel D — geometrie van één fysiek kozijn uit alle waarnemingen samen.
//
// Buitenmaat: de BESTAANDE niveau-A-meting (hoekstralen op het LiDAR-kozijnvlak) en de BESTAANDE fusie over standpunten
// (`Viewpoints.combineLevelA`, `Status.status`). Hier wordt niets opnieuw uitgerekend en geen drempel gewijzigd.
// Indeling (glasvlakken, tussenstijlen, dorpels): herkende glascontouren geprojecteerd op het gemeten kozijnvlak. Dat is een AFGELEIDE
// waarde (beeldsegmentatie + geometrie), nadrukkelijk geen directe LiDAR-meting, en zo staat het ook in de herkomst.

/// Eén glasvlak van een kozijn, in kozijn-eigen coördinaten (x van links, y van boven, in meter).
public struct GlassPane: Equatable {
    public var id: String
    public var xM: Double, yM: Double, widthM: Double, heightM: Double
    public var areaM2: Double
    public var sigmaAreaM2: Double
    public var seenInViews: Int
    public var sourceDetectionIds: [String]
    public var column: Int, row: Int
    /// DRAAIEND_DEEL / VAST_DEEL als een getraind model of de gebruiker dat heeft aangegeven; anders nil (onbekend, nooit gegokt).
    public var operability: ElementClass?
    public var glareSuspected: Bool
}

public struct FrameMember: Equatable {
    public var kind: ElementClass           // TUSSENSTIJL | TUSSENDORPEL
    public var positionM: Double            // midden, vanaf links (stijl) of vanaf boven (dorpel)
    public var thicknessM: Double           // zichtbare breedte tussen de glasvlakken (inclusief glaslatten/draaiend kader)
}

/// Door de gebruiker opgegeven indeling (ontwikkelfase: zolang er geen model is dat draaiende delen herkent).
public struct UserParts: Equatable, Codable, Sendable {
    public var operableParts: Int
    public var fixedParts: Int
    public init(operableParts: Int, fixedParts: Int) { self.operableParts = operableParts; self.fixedParts = fixedParts }
}

public struct FrameGeometry: Equatable {
    public var objectId: String
    public var status: DimensionStatus                      // bestaande statusregels (MEASURED vereist >= 2 onafhankelijke foto's)
    public var width: ScanValue, height: ScanValue, area: ScanValue
    public var scaleMethod: String                          // LIDAR_DEPTH_PLANE | LIDAR_DEPTH_MULTI_FRAME | REFERENCE_DISTANCE | NONE
    public var independentViewpoints: Int
    public var measuredSightingIds: [String]
    public var blockingCodes: [String]                      // waarom er geen maat is
    public var advisoryCodes: [String]
    public var recessCm: Double?                            // terugligging t.o.v. de wand (uit de meetdiagnose), indien bepaald
    public var panes: [GlassPane]
    public var glassArea: ScanValue                         // totaal zichtbaar glas (dagmaat)
    public var sections: ScanValue                          // aantal vakken (= glasvlakken)
    public var mullions: [FrameMember], transoms: [FrameMember]
    public var operableParts: ScanValue, fixedParts: ScanValue
    public var notes: [String]
}

public enum FrameGeometryRules {
    struct RelRect { var x0: Double, y0: Double, x1: Double, y1: Double
        var w: Double { x1 - x0 }; var h: Double { y1 - y0 }
        func iou(_ o: RelRect) -> Double {
            let iw = max(0, min(x1, o.x1) - max(x0, o.x0)), ih = max(0, min(y1, o.y1) - max(y0, o.y0))
            let inter = iw * ih, uni = w * h + o.w * o.h - inter
            return uni > 0 ? inter / uni : 0
        }
        func overlapOfSmaller(_ o: RelRect) -> Double {
            let iw = max(0, min(x1, o.x1) - max(x0, o.x0)), ih = max(0, min(y1, o.y1) - max(y0, o.y0))
            let small = min(w * h, o.w * o.h)
            return small > 0 ? iw * ih / small : 0
        }
    }

    /// Contour op de foto -> rechthoek in relatieve kozijncoördinaten (0..1) via het gemeten kozijnvlak van DEZE waarneming.
    static func relativeRect(_ polygon: [Pixel], sighting s: FrameSighting) -> RelRect? {
        guard let sp = s.spatial else { return nil }
        let (o, dirs) = raysWorld(pose: s.pose, intr: s.intrinsics, pixels: polygon)
        var pts: [Vec3] = []
        for d in dirs { guard let hit = intersectRayPlane(origin: o, dir: d, n: sp.n, d: sp.d) else { return nil }; pts.append(hit.point) }
        // kozijn-assen uit de gemeten hoeken (TL, TR, BR, BL); breedte = de rand die het minst met "omhoog" meeloopt (zelfde regel als dimsFromCorners)
        let c = sp.corners
        var ex = c[1] - c[0], ey = c[3] - c[0]
        var origin = c[0]
        if abs(ex.normalized.dot(worldUp)) > abs(ey.normalized.dot(worldUp)) { swap(&ex, &ey) }      // 90 graden gedraaide hoekvolgorde
        if ey.dot(worldUp) > 0 { origin = origin + ey; ey = ey * -1 }                                 // y loopt omlaag vanaf de bovenrand
        // x loopt van LINKS naar RECHTS zoals je vóór de gevel staat, ongeacht bij welke hoek de contour begint of hoe de telefoon gehouden is:
        // rechts = omhoog x (normaal naar de camera). Zonder dit zouden twee foto's met een andere hoekvolgorde gespiegelde vakken geven.
        let towardCamera: Vec3 = (s.pose.t.dot(sp.n) - sp.d) >= 0 ? sp.n : sp.n * -1
        if ex.dot(worldUp.cross(towardCamera)) < 0 { origin = origin + ex; ex = ex * -1 }
        let lx = ex.norm, ly = ey.norm
        guard lx > 1e-6, ly > 1e-6 else { return nil }
        let xs = pts.map { ($0 - origin).dot(ex) / (lx * lx) }, ys = pts.map { ($0 - origin).dot(ey) / (ly * ly) }
        var r = RelRect(x0: xs.min()!, y0: ys.min()!, x1: xs.max()!, y1: ys.max()!)
        if r.x0 > r.x1 { swap(&r.x0, &r.x1) }
        return r
    }

    static func cluster1D(_ values: [(Double, Int)], tol: Double) -> [Int: Int] {        // (waarde, index) -> index -> clusternummer (oplopend)
        var out: [Int: Int] = [:]
        var k = -1, last = -Double.infinity
        for (v, i) in values.sorted(by: { ($0.0, $0.1) < ($1.0, $1.1) }) {
            if v - last > tol { k += 1 }
            out[i] = k; last = v
        }
        return out
    }

    public static func compute(object: PhysicalObject, sightings: [FrameSighting], photos: [String: PhotoCapture], recognition: RecognitionCapability, userParts: UserParts? = nil,
                               validation: PipelineValidation = .current, cfg: GevelscanConfig = GevelscanConfig()) -> FrameGeometry {
        let mine = sightings.filter { object.sightingIds.contains($0.id) }.sorted { $0.id < $1.id }
        // 1. buitenmaat: bestaande fusie en statusregels
        let items = mine.compactMap { s -> Viewpoints.ViewMeasurement? in
            guard let r = s.result else { return nil }
            return Viewpoints.ViewMeasurement(capture: .init(keyframeId: s.photoId, position: s.pose.t), result: r)
        }
        var final: LevelResult? = nil
        var viewCount = 1
        if let a = Viewpoints.combineLevelA(items) { final = a.result; viewCount = a.viewCount }
        else if let c = mine.compactMap({ $0.result }).first(where: { $0.ok }) { final = c }
        else { final = mine.compactMap { $0.result }.first }
        var status: DimensionStatus = .UNKNOWN
        var flags: [QualityFlag] = final?.flags ?? []
        if let f = final, f.ok {
            if viewCount == 1 && f.level == .A { flags.append(Flags.make("SINGLE_VIEWPOINT")) }
            status = Status.status(for: f, viewCount: viewCount)
            // zelfde aanscherping als makeObject: elke afwaarderende adviescode sluit MEASURED uit
            if status == .MEASURED, !Set(flags.filter { $0.severity == .ADVISORY }.map { $0.code }).isDisjoint(with: downgradingAdvisories) { status = .ESTIMATED }
        }
        let blocking = Array(Set(flags.filter { $0.severity == .BLOCKING }.map { $0.code })).sorted()
        let advisory = Array(Set(flags.filter { $0.severity == .ADVISORY }.map { $0.code })).sorted()
        let dimOrigin: ValueOrigin = final?.level == .C ? .REFERENCE_DISTANCE : .LIDAR_PLANE_MEASUREMENT
        let dimOutcome: Outcome = status == .MEASURED ? .BETROUWBAAR_VASTGESTELD : .VOORLOPIG_VASTGESTELD
        var width = ScanValue.unknown("m", blocking.isEmpty ? ["GEEN_METING"] : blocking), height = width, area = ScanValue.unknown("m2", width.missing)
        var W = 0.0, H = 0.0
        if let f = final, f.ok, status != .UNKNOWN, let w = f.width, let h = f.height {
            // afronden op mm en bruto oppervlak = b x h: de bestaande regels (Area.swift)
            let dw = roundedMillimeters(w), dh = roundedMillimeters(h)
            W = Double(decimalString(dw)) ?? w; H = Double(decimalString(dh)) ?? h          // via de decimale tekst: exact dezelfde waarde als de meetkern exporteert
            let why = status == .MEASURED ? [] : (viewCount < 2 && f.level == .A ? ["ENKEL_STANDPUNT"] : []) + advisory.filter { downgradingAdvisories.contains($0) && $0 != "SINGLE_VIEWPOINT" }
                + (f.level == .C ? ["REFERENTIEMAAT_GEEN_LIDAR"] : [])
            width = ScanValue(value: W, unit: "m", sigma: f.sigmaW.map { round($0, 4) }, origin: dimOrigin, outcome: dimOutcome, missing: why)
            height = ScanValue(value: H, unit: "m", sigma: f.sigmaH.map { round($0, 4) }, origin: dimOrigin, outcome: dimOutcome, missing: why)
            area = ScanValue(value: Double(decimalString(grossAreaM2(width: dw, height: dh))) ?? w * h, unit: "m2", sigma: f.sigmaArea.map { round($0, 4) },
                             origin: .DERIVED_CALCULATION, outcome: dimOutcome, missing: why)
        }
        var recess: Double? = nil
        if let fp = final?.diag["frame_plane"] as? [String: Any], let rc = fp["recess_cm"] as? Double { recess = rc }
        var notes: [String] = []

        // 2. glasvlakken: per waarneming naar relatieve kozijncoördinaten, daarna over waarnemingen heen samenvoegen
        struct Obs { var rect: RelRect; var sightingId: String; var detId: String; var glare: Bool; var mPerPxX: Double; var mPerPxY: Double; var view: Int }
        var obs: [Obs] = []
        var viewsWithPanes = 0
        var dropped = 0
        let measuredViews = mine.filter { $0.spatial != nil }
        for (vi, s) in measuredViews.enumerated() where !s.panes.isEmpty {
            viewsWithPanes += 1
            let b = polygonBounds(s.polygon), sp = s.spatial!
            let mx = sp.width / max(b.maxU - b.minU, 1), my = sp.height / max(b.maxV - b.minV, 1)
            for p in s.panes.sorted(by: { $0.id < $1.id }) {
                guard let r = relativeRect(p.polygon, sighting: s) else { dropped += 1; continue }
                let t = cfg.paneInsideTol
                guard r.x0 >= -t, r.y0 >= -t, r.x1 <= 1 + t, r.y1 <= 1 + t, r.w > 0.02, r.h > 0.02 else { dropped += 1; continue }
                let cl = RelRect(x0: max(0, r.x0), y0: max(0, r.y0), x1: min(1, r.x1), y1: min(1, r.y1))
                obs.append(Obs(rect: cl, sightingId: s.id, detId: p.id, glare: (s.glareFractionByPane[p.id] ?? 0) >= cfg.glareFractionInGlass, mPerPxX: mx, mPerPxY: my, view: vi))
            }
        }
        if dropped > 0 { notes.append("\(dropped) glascontour(en) buiten het kozijn of niet te projecteren: niet meegeteld.") }
        var clusters: [[Obs]] = []
        for o in obs {
            if let k = clusters.firstIndex(where: { c in !c.contains { $0.view == o.view } && c.contains { $0.rect.iou(o.rect) >= cfg.paneClusterIoU } }) { clusters[k].append(o) }
            else { clusters.append([o]) }
        }
        var glassMissing: [String] = []
        var panes: [GlassPane] = []
        var mullions: [FrameMember] = [], transoms: [FrameMember] = []
        let paneOutcomeBase: Outcome = status == .MEASURED ? .BETROUWBAAR_VASTGESTELD : .VOORLOPIG_VASTGESTELD
        var paneOutcome = paneOutcomeBase
        if W <= 0 || H <= 0 { glassMissing.append("GEEN_KOZIJNMAAT") }
        if !recognition.canRecognize(.GLASVLAK) { glassMissing.append("GEEN_GLASHERKENNING") }
        if clusters.isEmpty { glassMissing.append(measuredViews.isEmpty ? "GEEN_GEMETEN_KOZIJNVLAK" : "GEEN_GLASVLAKKEN_HERKEND") }
        if glassMissing.isEmpty {
            let rects = clusters.map { c in RelRect(x0: median(c.map { $0.rect.x0 }), y0: median(c.map { $0.rect.y0 }), x1: median(c.map { $0.rect.x1 }), y1: median(c.map { $0.rect.y1 })) }
            // onderlinge overlap van verschillende glasvlakken: herkenning is dan niet bruikbaar
            var overlap = false
            for a in 0..<rects.count { for b in (a + 1)..<max(rects.count, a + 1) where b < rects.count && rects[a].overlapOfSmaller(rects[b]) > cfg.paneMaxMutualOverlap { overlap = true } }
            if overlap { glassMissing.append("GLASVLAKKEN_OVERLAPPEN") }
            else {
                // niet in elke waarneming hetzelfde gezien => voorlopig (een vak kan gemist of valselijk gevonden zijn)
                let inconsistent = viewsWithPanes >= 2 && clusters.contains { $0.count < viewsWithPanes }
                if inconsistent { paneOutcome = .VOORLOPIG_VASTGESTELD; notes.append("Niet elke foto toont dezelfde glasvlakken: de indeling is voorlopig.") }
                if viewsWithPanes < 2 { paneOutcome = .VOORLOPIG_VASTGESTELD }
                let minW = rects.map { $0.w }.min() ?? 1, minH = rects.map { $0.h }.min() ?? 1
                let cols = cluster1D(rects.enumerated().map { (($1.x0 + $1.x1) / 2, $0) }, tol: cfg.paneAxisClusterTol * minW)
                let rws = cluster1D(rects.enumerated().map { (($1.y0 + $1.y1) / 2, $0) }, tol: cfg.paneAxisClusterTol * minH)
                let relW = (width.sigma ?? 0) / max(W, 1e-9), relH = (height.sigma ?? 0) / max(H, 1e-9)
                for (k, r) in rects.enumerated() {
                    let c = clusters[k]
                    let pw = r.w * W, ph = r.h * H
                    // sigma: schaal van het kozijn + 2 hoekpixels per zijde + projectiefout door de diepteligging van het glas (model, niet gevalideerd)
                    let mx = median(c.map { $0.mPerPxX }), my = median(c.map { $0.mPerPxY })
                    let sw = (pow(pw * relW, 2) + 2 * pow(cfg.cornerPixelSigmaPx * mx, 2) + pow(pw * cfg.glassRecessRelativeError, 2)).squareRoot()
                    let sh = (pow(ph * relH, 2) + 2 * pow(cfg.cornerPixelSigmaPx * my, 2) + pow(ph * cfg.glassRecessRelativeError, 2)).squareRoot()
                    panes.append(GlassPane(id: "\(object.id)-G\(k + 1)", xM: round(r.x0 * W, 3), yM: round(r.y0 * H, 3), widthM: round(pw, 3), heightM: round(ph, 3),
                                           areaM2: round(pw * ph, 4), sigmaAreaM2: round((pow(sw * ph, 2) + pow(sh * pw, 2)).squareRoot(), 4), seenInViews: c.count,
                                           sourceDetectionIds: c.map { $0.detId }.sorted(), column: cols[k] ?? 0, row: rws[k] ?? 0, operability: nil,
                                           glareSuspected: c.contains { $0.glare }))
                }
                panes.sort { ($0.row, $0.column, $0.id) < ($1.row, $1.column, $1.id) }
                for (k, _) in panes.enumerated() { panes[k].id = "\(object.id)-G\(k + 1)" }
                // tussenstijlen/-dorpels: tussenruimte tussen naburige kolommen/rijen
                let nCols = (panes.map { $0.column }.max() ?? -1) + 1, nRows = (panes.map { $0.row }.max() ?? -1) + 1
                if nCols >= 2 { for c in 0..<(nCols - 1) {
                    let left = panes.filter { $0.column == c }.map { $0.xM + $0.widthM }.max()!, right = panes.filter { $0.column == c + 1 }.map { $0.xM }.min()!
                    if right > left { mullions.append(FrameMember(kind: .TUSSENSTIJL, positionM: round((left + right) / 2, 3), thicknessM: round(right - left, 3))) }
                } }
                if nRows >= 2 { for r in 0..<(nRows - 1) {
                    let top = panes.filter { $0.row == r }.map { $0.yM + $0.heightM }.max()!, bottom = panes.filter { $0.row == r + 1 }.map { $0.yM }.min()!
                    if bottom > top { transoms.append(FrameMember(kind: .TUSSENDORPEL, positionM: round((top + bottom) / 2, 3), thicknessM: round(bottom - top, 3))) }
                } }
            }
        }
        var glassArea = ScanValue.unknown("m2", glassMissing), sections = ScanValue.unknown("st", glassMissing)
        if glassMissing.isEmpty, !panes.isEmpty {
            let total = panes.reduce(0) { $0 + $1.areaM2 }
            var why: [String] = paneOutcome == .BETROUWBAAR_VASTGESTELD ? [] : (viewsWithPanes < 2 ? ["GLAS_OP_EEN_FOTO"] : []) + (status == .MEASURED ? [] : ["KOZIJNMAAT_VOORLOPIG"])
            if panes.contains(where: { $0.glareSuspected }) { paneOutcome = .VOORLOPIG_VASTGESTELD; why.append("SPIEGELING_IN_GLAS") }
            if total > (area.value ?? .infinity) { glassArea = .unknown("m2", ["GLAS_GROTER_DAN_KOZIJN"]); sections = .unknown("st", ["GLAS_GROTER_DAN_KOZIJN"]) }
            else {
                glassArea = ScanValue(value: round(total, 3), unit: "m2", sigma: round(panes.reduce(0) { $0 + $1.sigmaAreaM2 * $1.sigmaAreaM2 }.squareRoot(), 4),
                                      origin: .DERIVED_SEGMENTATION_ON_MEASURED_PLANE, outcome: paneOutcome, missing: Array(Set(why)).sorted())
                sections = ScanValue(value: Double(panes.count), unit: "st", origin: .DERIVED_SEGMENTATION_ON_MEASURED_PLANE, outcome: paneOutcome, missing: Array(Set(why)).sorted())
            }
        }

        // 3. draaiende en vaste delen: alleen van een getraind model of de gebruiker; anders onbekend (nooit afgeleid uit de vorm)
        var operable = ScanValue.unknown("st", ["GEEN_MODEL_VOOR_DRAAIENDE_DELEN"]), fixed = ScanValue.unknown("st", ["GEEN_MODEL_VOOR_DRAAIENDE_DELEN"])
        if let u = userParts {
            operable = ScanValue(value: Double(u.operableParts), unit: "st", origin: .USER_INPUT, outcome: .BETROUWBAAR_VASTGESTELD)
            fixed = ScanValue(value: Double(u.fixedParts), unit: "st", origin: .USER_INPUT, outcome: .BETROUWBAAR_VASTGESTELD)
        } else if recognition.learnedClasses.contains(.DRAAIEND_DEEL) && recognition.learnedClasses.contains(.VAST_DEEL) {
            if panes.isEmpty { operable = .unknown("st", ["GEEN_VAKKEN_BEPAALD"]); fixed = operable }
            else {
                var votes = [[ElementClass]](repeating: [], count: panes.count)
                for s in measuredViews { for part in s.parts where part.elementClass == .DRAAIEND_DEEL || part.elementClass == .VAST_DEEL {
                    guard let r = relativeRect(part.polygon, sighting: s) else { continue }
                    let rects = panes.map { RelRect(x0: $0.xM / W, y0: $0.yM / H, x1: ($0.xM + $0.widthM) / W, y1: ($0.yM + $0.heightM) / H) }
                    if let k = rects.indices.max(by: { rects[$0].overlapOfSmaller(r) < rects[$1].overlapOfSmaller(r) }), rects[k].overlapOfSmaller(r) >= 0.5 { votes[k].append(part.elementClass) }
                } }
                var undecided = 0
                for k in panes.indices {
                    let d = votes[k].filter { $0 == .DRAAIEND_DEEL }.count, v = votes[k].filter { $0 == .VAST_DEEL }.count
                    if d + v == 0 || d == v { undecided += 1 } else { panes[k].operability = d > v ? .DRAAIEND_DEEL : .VAST_DEEL }
                }
                if undecided > 0 { operable = .unknown("st", ["VAKKEN_ZONDER_EENDUIDIGE_KLASSE"]); fixed = operable }
                else {
                    // model niet gevalideerd => hoogstens voorlopig
                    let oc: Outcome = paneOutcome
                    operable = ScanValue(value: Double(panes.filter { $0.operability == .DRAAIEND_DEEL }.count), unit: "st", origin: .MODEL_CLASSIFICATION, outcome: oc)
                    fixed = ScanValue(value: Double(panes.filter { $0.operability == .VAST_DEEL }.count), unit: "st", origin: .MODEL_CLASSIFICATION, outcome: oc)
                }
            }
        }
        var scale = "NONE"
        if let f = final, f.ok { scale = f.scaleMethod }
        // Zolang de pijplijn niet met referentiemetingen is gevalideerd, is geen enkele gemeten, afgeleide of door een model bepaalde waarde
        // "betrouwbaar vastgesteld". Alleen wat de gebruiker zelf heeft ingevoerd blijft dat.
        func cap(_ v: ScanValue) -> ScanValue {
            guard !validation.autoProcessingAllowed, v.value != nil, v.outcome == .BETROUWBAAR_VASTGESTELD, v.origin != .USER_INPUT else { return v }
            var c = v; c.outcome = .VOORLOPIG_VASTGESTELD; c.missing = Array(Set(c.missing + validation.blockingReasons)).sorted(); return c
        }
        width = cap(width); height = cap(height); area = cap(area); glassArea = cap(glassArea); sections = cap(sections); operable = cap(operable); fixed = cap(fixed)
        return FrameGeometry(objectId: object.id, status: status, width: width, height: height, area: area, scaleMethod: scale, independentViewpoints: status == .UNKNOWN ? 0 : viewCount,
                             measuredSightingIds: mine.filter { $0.result?.ok == true }.map { $0.id }, blockingCodes: blocking, advisoryCodes: advisory, recessCm: recess,
                             panes: panes, glassArea: glassArea, sections: sections, mullions: mullions, transoms: transoms, operableParts: operable, fixedParts: fixed, notes: notes)
    }

    /// Adviescodes die MEASURED uitsluiten: de verzameling van de meetkern zelf (één bron).
    static var downgradingAdvisories: Set<String> { Status.downgrading }
}
