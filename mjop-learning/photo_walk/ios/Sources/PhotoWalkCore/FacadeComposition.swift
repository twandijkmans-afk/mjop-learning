import Foundation

/// Eén hoeveelheid van de gevelopbouw. `valueM2 == nil` betekent: geen betrouwbare waarde (status UNKNOWN), met in `missing` wat ontbreekt.
/// `partialValueM2` is de som van wat wel bekend is (alleen informatief; nooit als totaal gebruiken).
public struct FacadeQuantity: Equatable {
    public var valueM2: Decimal?
    public var status: DimensionStatus
    public var basis: String
    public var missing: [String]
    public var partialValueM2: Decimal?
    public init(valueM2: Decimal?, status: DimensionStatus, basis: String, missing: [String] = [], partialValueM2: Decimal? = nil) {
        self.valueM2 = valueM2; self.status = status; self.basis = basis; self.missing = missing; self.partialValueM2 = partialValueM2
    }
    public var json: [String: Any] {
        ["value_m2": valueM2.map { decimalString($0) } ?? NSNull(), "status": status.rawValue, "basis": basis, "missing": missing,
         "partial_value_m2": partialValueM2.map { decimalString($0) } ?? NSNull()]
    }
}

/// Een kozijn (opening) op de foto zoals de gevelopbouw het nodig heeft. De bruto buitenmaat komt uit de BESTAANDE kozijnmeting (LiDAR of
/// referentiemaat); is die er niet (of is de buitencontour niet bevestigd), dan is `areaM2` nil.
public struct FacadeOpeningInput {
    public var id: String
    public var outerPx: [Pixel]
    public var areaM2: Decimal?
    public var status: DimensionStatus
    public var planeN: Vec3?
    public var planeD: Double?
    public var panesPx: [[Pixel]]
    public init(id: String, outerPx: [Pixel], areaM2: Decimal?, status: DimensionStatus, planeN: Vec3?, planeD: Double?, panesPx: [[Pixel]]) {
        self.id = id; self.outerPx = outerPx; self.areaM2 = areaM2; self.status = status; self.planeN = planeN; self.planeD = planeD; self.panesPx = panesPx
    }
}

public struct FacadeCompositionResult {
    public var facadeGross: FacadeQuantity
    public var openings: FacadeQuantity
    public var frameOuter: FacadeQuantity
    public var glass: FacadeQuantity
    public var closedFacadeNet: FacadeQuantity
    public var maintainableFrameSurface: FacadeQuantity
    public var flags: [String]
    public var openingsInFacade: [String]
    public var quantitiesJSON: [String: Any] {
        ["facade_gross": facadeGross.json, "openings": openings.json, "frame_outer": frameOuter.json, "glass": glass.json,
         "closed_facade_net": closedFacadeNet.json, "maintainable_frame_surface": maintainableFrameSurface.json]
    }
}

/// Gevelopbouw van één foto: bruto gevel, openingen, buitenkozijn, glas en netto gesloten gevel. Python-referentie: facade.compose.
/// * Alleen met betrouwbare schaal; anders UNKNOWN met de ontbrekende onderdelen.
/// * Opening = buitenmaat van het kozijn (aanname; dagkant/sponning niet gemeten).
/// * Het onderhouds-/schilderoppervlak van een kozijn wordt NIET afgeleid (niet gelijk aan buitenkozijn min glas).
public enum FacadeComposition {
    public static let maintainableFrameNote = "Niet afgeleid: buitenkozijn min glas is niet het onderhouds- of schilderoppervlak (profieldiepte, dagkanten, roeden, glaslatten en binnen-/buitenzijde ontbreken). Meet of schat dit apart."
    public static let openingAssumption = "Aanname: opening = buitenmaat van het kozijn (dagkant/sponning niet gemeten)."

    static let order: [DimensionStatus: Int] = [.UNKNOWN: 0, .ESTIMATED: 1, .DERIVED: 2, .MEASURED: 3]
    public static func worst(_ s: [DimensionStatus]) -> DimensionStatus { s.min { order[$0]! < order[$1]! } ?? .UNKNOWN }

    /// m² afgerond op 0,001 (half-up).
    public static func round3(_ x: Double) -> Decimal { Decimal((x * 1000).rounded(.toNearestOrAwayFromZero)) / 1000 }

    /// Oppervlak (m²) van een pixelpolygoon geprojecteerd op het vlak n.x = d, met de ORIGINELE intrinsics en camerapose van de foto.
    public static func planarPolygonAreaM2(_ pixels: [Pixel], pose: Pose, intr: Intrinsics, n: Vec3, d: Double) -> Double? {
        var pts: [Vec3] = []
        for p in pixels {
            let dw = pose.rotate(intr.cameraRay(p).normalized)
            let den = dw.dot(n)
            if abs(den) < 1e-9 { return nil }
            let s = (d - pose.t.dot(n)) / den
            if s <= 0 { return nil }
            pts.append(pose.t + dw * s)
        }
        guard pts.count >= 3 else { return nil }
        var acc = Vec3.zero
        for i in 0..<pts.count { acc = acc + pts[i].cross(pts[(i + 1) % pts.count]) }
        return abs(acc.dot(n)) / 2
    }

    public static func compose(openings: [FacadeOpeningInput], pose: Pose?, intr: Intrinsics?, facadePx: [Pixel]?, facadePlane: (n: Vec3, d: Double)?,
                               facadePlaneStatus: DimensionStatus) -> FacadeCompositionResult {
        var flags: [String] = []
        let inside: [FacadeOpeningInput] = facadePx.map { f in openings.filter { inConvexPolygon(polygonCentroid($0.outerPx), f) } } ?? openings
        // bruto gevel
        let gross: FacadeQuantity
        if facadePx == nil {
            gross = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Geen gevelvlak getekend.", missing: ["FACADE_POLYGON"])
        } else if facadePlane == nil || facadePlaneStatus == .UNKNOWN || pose == nil || intr == nil {
            gross = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Geen betrouwbaar gevelvlak (schaal) voor deze foto.", missing: ["FACADE_PLANE"])
        } else if let a = planarPolygonAreaM2(facadePx!, pose: pose!, intr: intr!, n: facadePlane!.n, d: facadePlane!.d) {
            gross = FacadeQuantity(valueM2: round3(a), status: facadePlaneStatus, basis: "Getekend gevelvlak geprojecteerd op het gevelvlak.")
        } else {
            gross = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Projectie op het gevelvlak mislukt.", missing: ["FACADE_PLANE"])
        }
        // buitenkozijnen (= openingen, aanname)
        let known = inside.filter { $0.areaM2 != nil && $0.status != .UNKNOWN }
        let missingFrames = inside.filter { o in !known.contains { $0.id == o.id } }.map { $0.id }
        let part = known.reduce(Decimal(0)) { $0 + $1.areaM2! }
        let frameOuter: FacadeQuantity
        if inside.isEmpty {
            // geen herkende kozijnen is GEEN bewijs dat er geen openingen zijn (herkenning kan ze missen): onbekend, nooit 0
            frameOuter = FacadeQuantity(valueM2: nil, status: .UNKNOWN,
                                        basis: "Geen kozijnen herkend of aangegeven in dit gevelvlak; dat betekent niet dat er geen openingen zijn.", missing: ["NO_FRAMES_IN_FACADE"])
        } else if !missingFrames.isEmpty {
            frameOuter = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Niet alle kozijnen hebben een betrouwbare buitenmaat.", missing: missingFrames,
                                        partialValueM2: known.isEmpty ? nil : part)
        } else {
            frameOuter = FacadeQuantity(valueM2: part, status: worst(known.map { $0.status }), basis: "Som van de bruto buitenmaten (breedte x hoogte) van de kozijnen.")
        }
        var openingsQ = frameOuter
        openingsQ.basis = openingAssumption + " " + frameOuter.basis
        // glas
        var glassKnown = Decimal(0), glassMissing: [String] = [], glassStatus: [DimensionStatus] = []
        for o in inside {
            if o.panesPx.isEmpty { glassMissing.append(o.id + ":GEEN_GLASVLAKKEN"); continue }
            guard let n = o.planeN, let d = o.planeD, o.status != .UNKNOWN, let pose, let intr else { glassMissing.append(o.id + ":GEEN_SCHAAL"); continue }
            var s = Decimal(0), ok = true
            for p in o.panesPx {
                guard let a = planarPolygonAreaM2(p, pose: pose, intr: intr, n: n, d: d) else { ok = false; break }
                s += round3(a)
            }
            if !ok { glassMissing.append(o.id + ":PROJECTIE"); continue }
            glassKnown += s
            glassStatus.append(o.status == .MEASURED ? .ESTIMATED : o.status)
        }
        let glass: FacadeQuantity
        if !glassMissing.isEmpty {
            glass = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Niet van alle kozijnen zijn de glasvlakken met schaal bekend.", missing: glassMissing,
                                   partialValueM2: glassStatus.isEmpty ? nil : glassKnown)
        } else if inside.isEmpty {
            glass = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Geen kozijnen in dit gevelvlak.")
        } else {
            glass = FacadeQuantity(valueM2: glassKnown, status: worst(glassStatus), basis: "Som van de glasvlakken, geprojecteerd op het vlak van het eigen kozijn.")
        }
        // netto gesloten gevel
        let net: FacadeQuantity
        if let g = gross.valueM2, let o = frameOuter.valueM2 {
            if o > g {
                flags.append("OPENINGS_EXCEED_FACADE")
                net = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "De openingen zijn groter dan het getekende gevelvlak; controleer de contouren.", missing: ["CONSISTENT_CONTOURS"])
            } else {
                net = FacadeQuantity(valueM2: g - o, status: worst([gross.status, frameOuter.status]), basis: "Bruto gevel min openingen (buitenmaat kozijnen).")
            }
        } else {
            net = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: "Bruto gevel en alle openingen zijn nodig.", missing: gross.missing + frameOuter.missing)
        }
        let maintainable = FacadeQuantity(valueM2: nil, status: .UNKNOWN, basis: maintainableFrameNote, missing: ["NOT_DERIVED"])
        return FacadeCompositionResult(facadeGross: gross, openings: openingsQ, frameOuter: frameOuter, glass: glass, closedFacadeNet: net,
                                       maintainableFrameSurface: maintainable, flags: flags, openingsInFacade: inside.map { $0.id })
    }

    /// Alleen een aanvullende controle, nooit bewijs dat een fotometing klopt.
    public static func plausibility3DBAG(facadeGrossTotalM2: Decimal?, buitenmuurM2: Double?) -> [String] {
        guard let f = facadeGrossTotalM2, let b = buitenmuurM2 else { return [] }
        return f > Decimal(b) * Decimal(string: "1.05")! ? ["FACADE_GROSS_EXCEEDS_3DBAG_WALL_AREA"] : []
    }

    /// Gevelvlak uit de LiDAR-diepte BINNEN het getekende gevelvlak, zonder de kozijnen (glas en terugliggende profielen vertekenen het vlak).
    /// nil als er te weinig of te onrustige diepte is (dan geen bruto gevel-m²). Drempels PROVISIONAL_UNVALIDATED.
    public static func fitFacadePlane(view: ViewInput, polygon: [Pixel], exclude: [[Pixel]], seed: UInt64,
                                      threshold: Double = 0.03, minInliers: Int = 150, minInlierRatio: Double = 0.6) -> PlaneFit? {
        guard let dm = view.depth, dm.width > 0, dm.height > 0, polygon.count >= 3 else { return nil }
        let sx = Double(view.intrinsics.width) / Double(dm.width), sy = Double(view.intrinsics.height) / Double(dm.height)
        var pts: [Vec3] = []
        for i in 0..<dm.height {
            for j in 0..<dm.width {
                let z = Double(dm.values[i * dm.width + j])
                guard z.isFinite, z > 0.1 else { continue }
                let p = Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy)
                guard inConvexPolygon(p, polygon), !exclude.contains(where: { inConvexPolygon(p, $0) }) else { continue }
                pts.append(unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: p, depthZ: z))
            }
        }
        guard pts.count >= minInliers, let fit = fitPlaneRansac(pts, threshold: threshold, iterations: 200, seed: seed),
              fit.nInliers >= minInliers, fit.inlierRatio >= minInlierRatio else { return nil }
        return fit
    }
}
