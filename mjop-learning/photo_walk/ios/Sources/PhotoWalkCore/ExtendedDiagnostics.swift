import Foundation

// Uitgebreide meetdiagnose (spec 1.1.0). Port van python/photo_walk_core/ext_diagnostics.py.
//
// Afspraken (zie ook de Python-module):
// * ALLEEN extra diagnostiek, NA het definitieve resultaat. `measureDepthView`, `DepthPlane.swift`, `LevelA.swift`, `Quality.swift` (Config) zijn niet gewijzigd:
//   dit bestand roept de bestaande bouwstenen alleen aan. Een gelijkheidstest bewijst dat de meetuitkomst met en zonder deze berekening identiek is.
// * Alleen getallen en labels, CAMERA-RELATIEF: geen foto, geen dieptekaart, geen puntenwolk, geen locatie, geen absolute pose.
// * De schaduwevaluatie rekent poorten onder een GEMARKEERDE hypothese; er wordt nooit een hypothetische maat gepubliceerd.

public enum ExtendedDiagnostics {
    public static let specVersion = "1.1.0"
    static let contourBlocking: Set<String> = ["UNVERIFIED", "PROPOSED_EXPANSION", "DETECTED_ENCLOSING_PANES", "EDITED_UNCONFIRMED"]

    /// Beslisconstanten van de bestaande code die NIET in `Config` staan; alleen gedocumenteerd/geëxporteerd, niet verplaatst (zie GATE_CONSTANTS in Python).
    public static let gateConstants: [(name: String, value: Double, whereUsed: String)] = [
        ("plane_parallel_abs_cos", 0.97, "depth_plane.pick_facade"), ("plane_step_factor_thr", 1.5, "depth_plane.pick_facade"),
        ("facade_robust_sigma_k_sigma", 2.0, "depth_plane.pick_facade"), ("facade_robust_sigma_add_m", 0.012, "depth_plane.pick_facade"),
        ("facade_rms_add_m", 0.008, "depth_plane.pick_facade"), ("facade_not_vertical_abs_ny", 0.2, "depth_plane.analyze_points"),
        ("depth_coverage_min_fraction", 0.25, "levels.measure_depth_view"), ("depth_range_exceeded_fraction", 0.3, "levels.measure_depth_view"),
        ("corner_tolerance_add_m", 0.02, "levels.measure_depth_view"), ("flush_min_m", 0.015, "depth_plane.frame_offset"),
        ("quad_extent_step_factor_thr", 1.2, "depth_plane.quad_extent"), ("quad_extent_min_distance_m", 0.12, "depth_plane.quad_extent"),
    ]

    // MARK: hulpfuncties (zelfde definities als Python)

    static func r(_ x: Double?, _ nd: Int = 4) -> Any {
        guard let x = x, x.isFinite else { return NSNull() }
        let f = pow(10.0, Double(nd))
        return (x * f).rounded() / f
    }
    /// Bovenmediaan: gesorteerd, element n/2.
    static func upperMedian(_ a: [Double]) -> Double? { a.isEmpty ? nil : a.sorted()[a.count / 2] }
    /// Nearest-rank percentiel: index = ceil(p/100*n)-1.
    static func percentileNR(_ a: [Double], _ p: Double) -> Double? {
        guard !a.isEmpty else { return nil }
        let s = a.sorted()
        let k = max(1, Int((p / 100.0 * Double(s.count)).rounded(.up)))
        return s[min(k, s.count) - 1]
    }
    static func gate(_ id: String, _ status: String, value: Any? = nil, limit: Any? = nil, note: String? = nil) -> [String: Any] {
        ["id": id, "status": status, "value": value ?? NSNull(), "limit": limit ?? NSNull(), "note": note ?? NSNull()]
    }
    static func sideRule(_ covered: [Bool]) -> Bool {
        let c = covered.filter { $0 }.count
        if c < 2 { return false }
        if c == 2 && !((covered[0] && covered[2]) || (covered[1] && covered[3])) { return false }
        return true
    }
    static func firstIndexOfMaxCount(_ planes: [PlaneCand]) -> Int {
        var best = 0
        for i in planes.indices where planes[i].count > planes[best].count { best = i }
        return best
    }

    // MARK: frames, camera, kader (pose-vrij)

    /// Per frame: gebruikt/afgewezen met reden en de getallen waarop de bestaande selectieregel beslist. `trackingLabels` (frameId -> label) is optioneel;
    /// zonder label wordt "NORMAL"/"LIMITED" uit `trackingNormal` afgeleid.
    public static func framesDetail(_ view: ViewInput, cfg: Config = Config(), trackingLabels: [String: String] = [:]) -> [[String: Any]] {
        let (_, rejected) = selectSupportFrames(capture: view, supports: view.supports, cfg: cfg)
        func label(_ v: ViewInput) -> String { trackingLabels[v.frameId] ?? (v.trackingNormal ? "NORMAL" : "LIMITED") }
        var out: [[String: Any]] = [["frame": view.frameId, "role": "CAPTURE", "used": true, "reason": NSNull(), "has_depth": view.depth != nil, "tracking": label(view),
                                     "dt_to_capture_m": 0.0, "rot_to_capture_deg": 0.0, "meets_baseline": NSNull(), "meets_rotation": NSNull()]]
        var ri = 0
        for v in view.supports {
            var used = true
            var why: Any = NSNull()
            if ri < rejected.count && rejected[ri].0 == v.frameId { used = false; why = rejected[ri].1; ri += 1 }
            let dt = (v.pose.t - view.pose.t).norm
            var tr = 0.0
            for i in 0..<3 { tr += v.pose.r[i].dot(view.pose.r[i]) }
            let rot = acos(max(-1, min(1, (tr - 1) / 2))) * 180 / Double.pi
            out.append(["frame": v.frameId, "role": "SUPPORT", "used": used, "reason": why, "has_depth": v.depth != nil, "tracking": label(v),
                        "dt_to_capture_m": r(dt, 5), "rot_to_capture_deg": r(rot, 4), "meets_baseline": dt >= cfg.minBaselineM, "meets_rotation": rot >= cfg.minRotationDeg])
        }
        return out
    }

    /// Helling van de camera t.o.v. de zwaartekracht (geen positie, geen kompas, geen absolute oriëntatie).
    public static func cameraGravity(_ view: ViewInput) -> [String: Any] {
        let fwd = Vec3(view.pose.r[0].z, view.pose.r[1].z, view.pose.r[2].z), xax = Vec3(view.pose.r[0].x, view.pose.r[1].x, view.pose.r[2].x)
        return ["pitch_deg": r(asin(max(-1, min(1, fwd.dot(worldUp)))) * 180 / Double.pi, 3),
                "roll_sensor_x_deg": r(asin(max(-1, min(1, xax.dot(worldUp)))) * 180 / Double.pi, 3)]
    }

    /// K^-1 * (a, b, c) voor een intrinsics zonder scheefstand.
    private static func kInv(_ i: Intrinsics, _ a: Double, _ b: Double, _ c: Double) -> Vec3 { Vec3((a - i.cx * c) / i.fx, (b - i.cy * c) / i.fy, c) }

    /// Uit alleen de vier hoeken + intrinsics (rechthoekaanname): aspect b/h, assenhoek, facing t.o.v. de kijkstraal naar het kadermidden.
    public static func quadFromCorners(_ corners: [Pixel], _ intr: Intrinsics) -> [String: Any]? {
        let unit: [(Double, Double)] = [(0, 0), (1, 0), (1, 1), (0, 1)]
        var A: [[Double]] = [], b: [Double] = []
        for ((x, y), p) in zip(unit, corners) {
            A.append([x, y, 1, 0, 0, 0, -p.u * x, -p.u * y]); b.append(p.u)
            A.append([0, 0, 0, x, y, 1, -p.v * x, -p.v * y]); b.append(p.v)
        }
        guard let h = solveLinear(A, b) else { return nil }
        let a = kInv(intr, h[0], h[3], h[6]), bb = kInv(intr, h[1], h[4], h[7])
        let na = a.norm, nb = bb.norm
        if na < 1e-12 || nb < 1e-12 { return nil }
        let ang = acos(max(-1, min(1, a.dot(bb) / (na * nb)))) * 180 / Double.pi
        var n = a.cross(bb).normalized
        let cu = corners.map { $0.u }.reduce(0, +) / 4.0, cv = corners.map { $0.v }.reduce(0, +) / 4.0
        let ray = kInv(intr, cu, cv, 1).normalized
        if n.z > 0 { n = n * -1 }
        return ["aspect_w_over_h": r(na / nb, 5), "axes_angle_deg": r(ang, 3), "facing": r(abs(n.dot(ray)), 5), "plane_normal_cam": [r(n.x, 5), r(n.y, 5), r(n.z, 5)]]
    }

    // MARK: herberekening (zelfde stappen en seed als de meting; alleen lezen)

    struct Reanalysis {
        var frames: [ViewInput] = []
        var perFrame: [PointSet] = []
        var all = PointSet()
        var ring: [Vec3] = [], ringSide: [Int] = [], band: [Vec3] = [], bandSide: [Int] = []
        var planes: [PlaneCand] = []
        var zMed = 3.0, thr = 0.0, quadDiagM = 0.0
    }

    static func reanalyze(_ view: ViewInput, corners: [Pixel], cfg: Config, seed: UInt64) -> Reanalysis {
        var re = Reanalysis()
        let (frames, _) = selectSupportFrames(capture: view, supports: view.supports, cfg: cfg)
        let regions = Regions(quad: corners, cfg: cfg)
        re.frames = frames
        for f in frames {
            let ps = collectPoints(frame: f, capture: view, isCapture: f.frameId == view.frameId && f.pose.t == view.pose.t, regions: regions, cfg: cfg)
            re.perFrame.append(ps); re.all.append(ps)
        }
        for i in 0..<re.all.X.count {
            if re.all.kind[i] == 1 { re.ring.append(re.all.X[i]); re.ringSide.append(re.all.side[i]) }
            else if re.all.kind[i] == 2 { re.band.append(re.all.X[i]); re.bandSide.append(re.all.side[i]) }
        }
        let cam = view.pose.t
        re.zMed = re.ring.isEmpty ? 3.0 : medianOf(re.ring.map { ($0 - cam).norm })
        re.thr = thrAt(re.zMed, cfg)
        if re.ring.count >= cfg.minPlanePoints {
            re.planes = sequentialPlanes(re.ring, side: re.ringSide, thr: re.thr, cfg: cfg, seed: seed)
            classifyPlanes(&re.planes, camPos: cam, cfg: cfg)
        }
        let qd = ((corners[2].u - corners[0].u) * (corners[2].u - corners[0].u) + (corners[2].v - corners[0].v) * (corners[2].v - corners[0].v)).squareRoot()
        re.quadDiagM = qd * re.zMed / view.intrinsics.fx
        return re
    }

    /// Alle vlakken, CAMERA-RELATIEF.
    static func planesAll(_ view: ViewInput, _ re: Reanalysis) -> [[String: Any]] {
        guard !re.planes.isEmpty else { return [] }
        let bi = firstIndexOfMaxCount(re.planes)
        var out: [[String: Any]] = []
        for (i, p) in re.planes.enumerated() {
            let nCam = view.pose.rotateInverse(p.n), cCam = view.pose.toCamera(p.centroid)
            let ext = inplaneStd(p.idx.map { re.ring[$0] }, p.n)
            let cnt = Double(max(p.count, 1))
            out.append(["index": i, "role": p.role, "count": p.count, "facing": r(p.facing, 5), "vertical": r(p.vertical, 5), "rms_m": r(p.rms, 5), "spread_m": r(p.spread, 5),
                        "normal_cam": [r(nCam.x, 5), r(nCam.y, 5), r(nCam.z, 5)], "centroid_cam": [r(cCam.x, 4), r(cCam.y, 4), r(cCam.z, 4)],
                        "sides_counts": p.sides, "sides_shares": p.sides.map { r(Double($0) / cnt, 4) },
                        "angle_to_largest_deg": r(acos(min(1.0, abs(p.n.dot(re.planes[bi].n)))) * 180 / Double.pi, 3), "is_largest": i == bi,
                        "extent_major_std_m": r(ext.major, 5), "extent_minor_std_m": r(ext.minor, 5)])
        }
        return out
    }

    // MARK: dieptekaart-gebaseerde blokken

    struct Cell { var p: Pixel; var z: Double; var kind: Int; var side: Int }

    static func depthCells(_ view: ViewInput, regions: Regions) -> (cells: [Cell], sx: Double, sy: Double)? {
        guard let dm = view.depth, dm.width > 0, dm.height > 0 else { return nil }
        let sx = Double(view.intrinsics.width) / Double(dm.width), sy = Double(view.intrinsics.height) / Double(dm.height)
        var cells: [Cell] = []
        cells.reserveCapacity(dm.width * dm.height)
        for i in 0..<dm.height { for j in 0..<dm.width {
            let p = Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy)
            let (k, s) = regions.classify(p)
            cells.append(Cell(p: p, z: Double(dm.values[i * dm.width + j]), kind: k, side: s))
        } }
        return (cells, sx, sy)
    }

    static func ringDepthMedian(_ cells: [Cell], cfg: Config) -> Double? {
        upperMedian(cells.filter { $0.kind == 1 && $0.z.isFinite && $0.z >= cfg.depthMinRangeM && $0.z <= cfg.depthMaxRangeM }.map { $0.z })
    }

    static func depthProfiles(_ view: ViewInput, corners: [Pixel], regions: Regions, cfg: Config, zMed: Double, ringMedian: Double?) -> [String: Any]? {
        guard let dm = view.depth, dm.width > 0, dm.height > 0 else { return nil }
        let sx = Double(view.intrinsics.width) / Double(dm.width), sy = Double(view.intrinsics.height) / Double(dm.height)
        let cmPerPx = zMed / view.intrinsics.fx * 100.0
        let BIN = 2.0, LO = -8.0, HI = 40.0
        let nb = Int(((HI - LO) / BIN).rounded())
        var pixels = [[Int]](repeating: [Int](repeating: 0, count: nb), count: 4)
        var valid = pixels
        var dz = [[[Double]]](repeating: [[Double]](repeating: [], count: nb), count: 4)
        for i in 0..<dm.height { for j in 0..<dm.width {
            let p = Pixel((Double(j) + 0.5) * sx, (Double(i) + 0.5) * sy)
            var dists = [Double](repeating: 0, count: 4)
            var side = 0, bd = Double.infinity
            for k in 0..<4 {
                dists[k] = Regions.dist(regions.edges[k].0, regions.edges[k].1, p.u, p.v, regions.sgn)
                let nrm = dists[k] / regions.h[k]
                if nrm < bd { bd = nrm; side = k }
            }
            let a = regions.edges[side].0, b = regions.edges[side].1
            let ex = b.u - a.u, ey = b.v - a.v
            let tPar = ((p.u - a.u) * ex + (p.v - a.v) * ey) / (ex * ex + ey * ey)
            if tPar < 0 || tPar > 1 { continue }
            let outward = -dists[side] * cmPerPx
            let bi = Int(((outward - LO) / BIN).rounded(.down))
            if bi < 0 || bi >= nb { continue }
            pixels[side][bi] += 1
            let z = Double(dm.values[i * dm.width + j])
            if z.isFinite && z >= cfg.depthMinRangeM && z <= cfg.depthMaxRangeM {
                valid[side][bi] += 1
                if let rm = ringMedian { dz[side][bi].append(z - rm) }
            }
        } }
        var sides: [String: Any] = [:]
        for (k, name) in sideNames.enumerated() {
            var bins: [[String: Any]] = []
            for b in 0..<nb {
                bins.append(["from_cm": LO + Double(b) * BIN, "to_cm": LO + Double(b + 1) * BIN, "pixels": pixels[k][b], "valid": valid[k][b], "median_dz_m": r(upperMedian(dz[k][b]), 4)])
            }
            sides[name] = bins
        }
        return ["unit": "cm uitwaarts vanaf de kaderrand (negatief = binnen het kader)", "bin_cm": BIN, "cm_per_px": r(cmPerPx, 5), "ring_depth_median_m": r(ringMedian, 4), "sides": sides]
    }

    static func glassDepthSummary(_ cells: [Cell], cfg: Config, ringMedian: Double?) -> [String: Any] {
        let g = cells.filter { $0.kind == 3 }
        let valid = g.filter { $0.z.isFinite && $0.z > 0 }
        var out: [String: Any] = ["pixels": g.count, "valid": valid.count, "valid_fraction": g.isEmpty ? NSNull() : r(Double(valid.count) / Double(g.count), 4), "reference": "ring_depth_median",
                                  "beyond_limit_m": cfg.glassBeyondPlaneM]
        if !valid.isEmpty, let rm = ringMedian {
            let dz = valid.map { $0.z - rm }
            var pc: [String: Any] = [:]
            for p in [5.0, 25.0, 50.0, 75.0, 95.0] { pc[String(Int(p))] = r(percentileNR(dz, p), 4) }
            out["percentiles_dz_m"] = pc
            out["beyond_ring_fraction"] = r(Double(dz.filter { $0 > cfg.glassBeyondPlaneM }.count) / Double(dz.count), 4)
        } else { out["percentiles_dz_m"] = NSNull(); out["beyond_ring_fraction"] = NSNull() }
        return out
    }

    /// Kader t.o.v. de beeldrand (NATIVE sensorpixels) en hoeveel van de ring in beeld ligt. Informatief; GEEN verplichte afstand.
    static func framing(_ view: ViewInput, corners: [Pixel], regions: Regions, cells: [Cell], sx: Double, sy: Double, cfg: Config, zMed: Double?) -> [String: Any] {
        let W = Double(view.intrinsics.width), H = Double(view.intrinsics.height)
        let us = corners.map { $0.u }, vs = corners.map { $0.v }
        var perSide: [String: Any] = [:]
        var ringCount = 0
        for (k, name) in sideNames.enumerated() {
            let rc = cells.filter { $0.kind == 1 && $0.side == k }
            let rv = rc.filter { $0.z.isFinite && $0.z >= cfg.depthMinRangeM && $0.z <= cfg.depthMaxRangeM }
            perSide[name] = ["ring_pixels": rc.count, "ring_valid": rv.count] as [String: Any]
            ringCount += rc.count
        }
        let full = abs(signedArea(regions.ringOut)) - abs(signedArea(regions.ringIn))
        let inView = Double(ringCount) * sx * sy
        let ro = regions.ringOut
        let bbMinU = ro.map { $0.u }.min()!, bbMaxU = ro.map { $0.u }.max()!, bbMinV = ro.map { $0.v }.min()!, bbMaxV = ro.map { $0.v }.max()!
        let fu = (bbMaxU - bbMinU) / W, fv = (bbMaxV - bbMinV) / H
        var res: [String: Any] = [
            "margins_px": ["left": r(us.min(), 2), "right": r(W - us.max()!, 2), "top": r(vs.min(), 2), "bottom": r(H - vs.max()!, 2)] as [String: Any],
            "ring_in_view_fraction": full > 0 ? r(inView / full, 4) : NSNull(), "ring_per_side": perSide,
            "ring_out_overflow_px": ["left": r(max(0, -bbMinU), 1), "right": r(max(0, bbMaxU - W), 1), "top": r(max(0, -bbMinV), 1), "bottom": r(max(0, bbMaxV - H), 1)] as [String: Any],
            "ring_fit_factor_u": r(fu, 4), "ring_fit_factor_v": r(fv, 4),
            "note": "informatief; geen eis. Bij een beperkte opnameafstand werkt de analyse met de zichtbare ring.",
        ]
        if let z = zMed { res["distance_for_full_ring_m"] = r(z * max(r4(fu), r4(fv), 1.0), 3) } else { res["distance_for_full_ring_m"] = NSNull() }
        return res
    }
    private static func r4(_ x: Double) -> Double { (x * 10000).rounded() / 10000 }

    // MARK: schaduwevaluatie

    /// Consistentie per frame: zelfde stappen als de (private) `analyzeSubset` van de meting.
    private static func subsetResult(_ view: ViewInput, _ pts: PointSet, corners: [Pixel], cfg: Config, seed: UInt64, quadDiagPx: Double) -> (ok: Bool, w: Double, h: Double, normal: Vec3)? {
        if pts.X.count < cfg.minPlanePoints { return nil }
        let an = analyzePoints(capture: view, pts, cfg: cfg, seed: seed, quadDiagPx: quadDiagPx)
        guard let fac = an.facade, !hasBlocking(an.flags), let frm = an.frame, ["FLUSH", "RECESSED", "PROTRUDING"].contains(frm.mode), let off = frm.offset,
              let g = planeGeometry(view, corners: corners, n: fac.n, d: fac.d + off) else { return nil }
        let (w, h) = dimsFromCorners(g.points, up: worldUp)
        return (true, w, h, fac.n)
    }

    static func gatesShadow(_ view: ViewInput, corners: [Pixel], cfg: Config, seed: UInt64, result: LevelResult, contourStatus: String?, re: Reanalysis, regions: Regions, cells: [Cell]) -> [String: Any] {
        var gates: [[String: Any]] = []
        let ringValid = result.diag["ring_valid"] as? Int
        let cov = result.diag["ring_coverage"] as? Double
        if let rv = ringValid, let cv = cov {
            gates.append(gate("DEPTH_COVERAGE", (rv >= cfg.annulusMinPoints && cv >= 0.25) ? "PASS" : "FAIL", value: ["ring_valid": rv, "coverage": cv] as [String: Any],
                              limit: ["min_points": cfg.annulusMinPoints, "min_coverage": 0.25] as [String: Any]))
        } else { gates.append(gate("DEPTH_COVERAGE", "NOT_EVALUATED", limit: ["min_points": cfg.annulusMinPoints, "min_coverage": 0.25] as [String: Any])) }
        guard !re.planes.isEmpty else {
            gates.append(gate("FACADE_SELECTION", "FAIL", note: "geen vlakken gevonden"))
            return ["host_hypothesis": NSNull(), "gates": gates, "reproduces_result_planes": false]
        }
        let resultCounts = ((result.diag["planes"] as? [[String: Any]]) ?? []).compactMap { $0["count"] as? Int }
        let reproduces = re.planes.map { $0.count } == resultCounts
        // 1) echte selectie
        var sel = re.planes
        let (selIdx, selCode, selDetail, _) = pickFacade(&sel, ring: re.ring, zMed: re.zMed, cfg: cfg, quadDiagM: re.quadDiagM)
        gates.append(gate("FACADE_SELECTION", selIdx != nil ? "PASS" : "FAIL", note: selIdx != nil ? nil : "\(selCode ?? "?"): \(selDetail)"))
        // 2) hypothese
        var hi: Int
        var src: String
        if let s = selIdx { hi = s; src = "SELECTED" } else {
            let cands = re.planes.indices.filter { re.planes[$0].vertical <= cfg.facadeMaxVertical }
            guard var best = cands.first else {
                gates.append(gate("FACADE_FACING", "FAIL", note: "geen verticaal vlak"))
                return ["host_hypothesis": NSNull(), "gates": gates, "reproduces_result_planes": reproduces]
            }
            func key(_ i: Int) -> (Double, Int) { ((re.planes[i].facing * 1e6).rounded() / 1e6, re.planes[i].count) }
            for i in cands.dropFirst() { let a = key(i), b = key(best); if a.0 > b.0 || (a.0 == b.0 && a.1 > b.1) { best = i } }
            hi = best; src = "BEST_FACING_VERTICAL"
        }
        let host = re.planes[hi]
        let hyp: [String: Any] = ["source": src, "plane_index": hi, "facing": r(host.facing, 5), "count": host.count, "vertical": r(host.vertical, 5),
                                  "note": src == "SELECTED" ? "gekozen door de meting" : "hypothese voor diagnose; geen uitspraak dat dit de gevel is"]
        gates.append(gate("FACADE_FACING", host.facing >= cfg.facadeMinFacing ? "PASS" : "FAIL", value: r(host.facing, 5), limit: cfg.facadeMinFacing))
        // 3) gastvlak-poorten afzonderlijk
        var forced = re.planes
        for i in forced.indices { forced[i].role = i == hi ? "FACADE_CANDIDATE" : "REVEAL_OR_LEDGE" }
        let (_, _, _, A) = pickFacade(&forced, ring: re.ring, zMed: re.zMed, cfg: cfg, quadDiagM: re.quadDiagM)
        let hostF = forced[hi]
        let loc = A["local"] as? [String: Any]
        let sup = A["support"] as? Double
        gates.append(gate("FACADE_SUPPORT", sup == nil ? "NOT_EVALUATED" : (sup! >= cfg.facadeSupportMin ? "PASS" : "FAIL"), value: r(sup, 4), limit: cfg.facadeSupportMin))
        if let l = loc, let a = l["rms_m"] as? Double, let al = l["rms_limit_m"] as? Double {
            gates.append(gate("FACADE_LOCAL_RMS", a <= al ? "PASS" : "FAIL", value: a, limit: al))
        } else { gates.append(gate("FACADE_LOCAL_RMS", "NOT_EVALUATED")) }
        if let l = loc, let a = l["robust_sigma_m"] as? Double, let al = l["robust_limit_m"] as? Double {
            gates.append(gate("FACADE_LOCAL_ROBUST", a <= al ? "PASS" : "FAIL", value: a, limit: al))
        } else { gates.append(gate("FACADE_LOCAL_ROBUST", "NOT_EVALUATED")) }
        if let u = A["unexplained"] as? [String: Any], let sh = u["share"] as? Double {
            gates.append(gate("FACADE_UNEXPLAINED", sh <= cfg.unexplainedMax ? "PASS" : "FAIL", value: sh, limit: cfg.unexplainedMax))
        } else { gates.append(gate("FACADE_UNEXPLAINED", "NOT_EVALUATED")) }
        if let sd = A["sides"] as? [String: Any], let cov = sd["covered"] as? [Bool] {
            gates.append(gate("FACADE_SIDE_COVERAGE", sideRule(cov) ? "PASS" : "FAIL", value: ["covered": cov, "counts": sd["counts"] ?? NSNull()] as [String: Any],
                              limit: ["min_points_per_side": sd["min_points_per_side"] ?? NSNull()] as [String: Any]))
        } else { gates.append(gate("FACADE_SIDE_COVERAGE", "NOT_EVALUATED")) }
        if let ex = A["extent"] as? [String: Any], let mn = ex["minor_std_m"] as? Double, let req = ex["min_required_m"] as? Double {
            gates.append(gate("FACADE_EXTENT", mn >= req ? "PASS" : "FAIL", value: mn, limit: req))
        } else { gates.append(gate("FACADE_EXTENT", "NOT_EVALUATED")) }
        // 4) kozijnvlak en geometrie onder dezelfde hypothese
        let fo = frameOffset(band: re.band, side: re.bandSide, facade: hostF, zMed: re.zMed, cfg: cfg)
        let modeOk = ["FLUSH", "RECESSED", "PROTRUDING"].contains(fo.mode)
        var supMap: [String: Any] = [:]
        for name in sideNames { supMap[name] = fo.perSide[name]?.support ?? 0 }
        gates.append(gate("FRAME_PLANE", modeOk ? "PASS" : "FAIL", value: ["mode": fo.mode, "offset_m": r(fo.offset, 4), "support": supMap] as [String: Any], limit: ["min_sides": 2]))
        let offset = modeOk ? (fo.offset ?? 0) : 0.0
        let noteOff: String? = modeOk ? nil : "offset 0 aangenomen om de overige poorten te kunnen beoordelen"
        let dPlane = hostF.d + offset
        let ids = ["CORNER_DEPTH", "RECTANGULARITY", "DIMENSION_RANGE", "QUAD_EXTENT", "GLASS", "FRAMES_CONSISTENCY"]
        if let geo = planeGeometry(view, corners: corners, n: hostF.n, d: dPlane) {
            gates.append(gate("INCIDENCE", geo.cosMin >= cfg.minIncidenceCos ? "PASS" : "FAIL", value: r(geo.cosMin, 4), limit: cfg.minIncidenceCos, note: noteOff))
            let C = geo.points
            let sig = sigmaAt(re.zMed, cfg)
            let tolC = cfg.cornerTolK * sig + 0.02
            let zAxis = Vec3(view.pose.r[0].z, view.pose.r[1].z, view.pose.r[2].z)
            var contra = 0
            var dev: [Any] = []
            for k in 0..<4 {
                let v = cornerValues(view, corners[k])
                if v.count < 3 { dev.append(NSNull()); continue }
                let exp = (C[k] - view.pose.t).dot(zAxis)
                let dd = v.map { $0 - exp }
                dev.append(r(dd.min(by: { abs($0) < abs($1) }), 4))
                if !dd.contains(where: { abs($0) <= tolC }) { contra += 1 }
            }
            gates.append(gate("CORNER_DEPTH", contra < cfg.cornersContradictBlock ? "PASS" : "FAIL", value: ["contradicting": contra, "deviation_m": dev] as [String: Any],
                              limit: ["block_at": cfg.cornersContradictBlock, "tolerance_m": r(tolC, 4)] as [String: Any], note: noteOff))
            let bad = rectangularityProblems(C, edgeRatioTol: cfg.rectEdgeRatioTol, angleTolDeg: cfg.rectAngleTolDeg)
            gates.append(gate("RECTANGULARITY", bad.isEmpty ? "PASS" : "FAIL", value: bad.isEmpty ? nil : bad, limit: ["edge_ratio": cfg.rectEdgeRatioTol, "angle_deg": cfg.rectAngleTolDeg] as [String: Any], note: noteOff))
            let (w, h) = dimsFromCorners(C, up: worldUp)
            let inRange = (cfg.minDimM...cfg.maxDimM).contains(w) && (cfg.minDimM...cfg.maxDimM).contains(h)
            gates.append(gate("DIMENSION_RANGE", inRange ? "PASS" : "FAIL", limit: ["min_m": cfg.minDimM, "max_m": cfg.maxDimM] as [String: Any], note: "alleen het bereik; de waarde zelf wordt niet gepubliceerd (hypothetisch)"))
            let qe = quadExtent(view, corners: corners, n: hostF.n, dPlane: dPlane, zMed: re.zMed, cfg: cfg)
            gates.append(gate("QUAD_EXTENT", (qe.larger < 3 && qe.inside < 3) ? "PASS" : "FAIL",
                              value: ["sides_deeper_step_inside": qe.larger, "sides_closer_step_outside": qe.inside, "sides": qe.sides] as [String: Any], limit: ["block_at_sides": 3], note: noteOff))
            // glas
            let glass = cells.filter { $0.kind == 3 }
            if !glass.isEmpty {
                let vin = glass.filter { $0.z.isFinite && $0.z > 0 }
                let fv = Double(vin.count) / Double(glass.count)
                var bf = 0.0
                if !vin.isEmpty {
                    var nb = 0
                    for c in vin where abs(unprojectDepth(pose: view.pose, intr: view.intrinsics, pixel: c.p, depthZ: c.z).dot(hostF.n) - dPlane) > cfg.glassBeyondPlaneM { nb += 1 }
                    bf = Double(nb) / Double(vin.count)
                }
                gates.append(gate("GLASS", (fv >= cfg.glassMinValidFraction && bf <= cfg.glassMaxBeyondFraction) ? "PASS" : "FAIL", value: ["valid_fraction": r(fv, 4), "beyond_fraction": r(bf, 4)] as [String: Any],
                                  limit: ["min_valid": cfg.glassMinValidFraction, "max_beyond": cfg.glassMaxBeyondFraction] as [String: Any], note: "adviserend in de meting"))
            } else { gates.append(gate("GLASS", "NOT_APPLICABLE", note: "geen glasgebied")) }
            // frames
            if re.frames.count > 1 {
                var fails: [String] = [], usable = 0
                let qd = ((corners[2].u - corners[0].u) * (corners[2].u - corners[0].u) + (corners[2].v - corners[0].v) * (corners[2].v - corners[0].v)).squareRoot()
                for (fi, f) in re.frames.enumerated() {
                    guard let sub = subsetResult(view, re.perFrame[fi], corners: corners, cfg: cfg, seed: seed &+ UInt64(101 * (fi + 1)), quadDiagPx: qd) else { continue }
                    usable += 1
                    let ndeg = angleBetweenDeg(sub.normal, hostF.n)
                    if abs(sub.w - w) > cfg.frameTolRel * w + cfg.frameTolAbsM || abs(sub.h - h) > cfg.frameTolRel * h + cfg.frameTolAbsM || ndeg > cfg.frameNormalDeg { fails.append(f.frameId) }
                }
                gates.append(gate("FRAMES_CONSISTENCY", fails.isEmpty ? "PASS" : "FAIL", value: ["usable": usable, "inconsistent": fails] as [String: Any],
                                  limit: ["tol_rel": cfg.frameTolRel, "tol_abs_m": cfg.frameTolAbsM] as [String: Any], note: noteOff))
            } else { gates.append(gate("FRAMES_CONSISTENCY", "NOT_APPLICABLE", note: "één onafhankelijk frame")) }
        } else {
            gates.append(gate("CORNERS_ON_PLANE", "FAIL", note: noteOff))
            for id in ids { gates.append(gate(id, "NOT_EVALUATED", note: "hoekstralen snijden het vlak niet")) }
        }
        if let cs = contourStatus {
            gates.append(gate("OUTER_CONTOUR_CONFIRMED", contourBlocking.contains(cs) ? "FAIL" : "PASS", value: cs, note: "poort van de app (ContourGate); niet onderdeel van de LiDAR-meting"))
        } else { gates.append(gate("OUTER_CONTOUR_CONFIRMED", "NOT_EVALUATED", note: "status niet meegegeven")) }
        return ["host_hypothesis": hyp, "gates": gates, "reproduces_result_planes": reproduces]
    }

    // MARK: beeldranden (alleen getallen)

    /// Randsterkte (en consistentie) per kaderzijde naar buiten, voor grijs (en optioneel verzadiging). Alleen getallenreeksen.
    public static func edgeLadder(gray: GrayImage, saturation: GrayImage?, corners: [Pixel], maxOffsets: Int = 160) -> [String: Any] {
        var sides: [String: Any] = [:]
        for (s, name) in sideNames.enumerated() {
            let p = OuterFrameSearch.edgeProfile(gray, quad: corners, side: s)
            var entry: [String: Any] = ["offsets_px": p.offsets.prefix(maxOffsets).map { Int($0) }, "strength_gray": p.strengths.prefix(maxOffsets).map { r($0, 2) },
                                        "consistency_gray": p.consistency.prefix(maxOffsets).map { r($0, 3) }]
            if let sat = saturation {
                let q = OuterFrameSearch.edgeProfile(sat, quad: corners, side: s)
                entry["strength_saturation"] = q.strengths.prefix(maxOffsets).map { r($0, 2) }
            }
            sides[name] = entry
        }
        return ["unit": "px uitwaarts in het beeld", "sides": sides]
    }

    /// Verzadiging 0...255 (HSV: (max-min)/max) uit RGBA-bytes (rij-hoofdvolgorde, 4 bytes per pixel); afgerond zoals de Python-referentie.
    public static func saturationChannel(rgba: [UInt8], width: Int, height: Int) -> GrayImage {
        var px = [UInt8](repeating: 0, count: width * height)
        for i in 0..<(width * height) {
            let r = Double(rgba[4 * i]), g = Double(rgba[4 * i + 1]), b = Double(rgba[4 * i + 2])
            let mx = max(r, g, b), mn = min(r, g, b)
            let s = mx > 1e-6 ? (mx - mn) / mx * 255.0 : 0
            px[i] = UInt8(max(0, min(255, s.rounded(.toNearestOrEven))))
        }
        return GrayImage(width: width, height: height, pixels: px)
    }

    public static func gateConstantsExport() -> [[String: Any]] { gateConstants.map { ["name": $0.name, "value": $0.value, "where": $0.whereUsed] } }

    // MARK: samenstelling

    /// Bouwt het blok `extended_diagnostics`. Leest alleen; `result` en alle invoer blijven onveranderd (value types).
    public static func compute(view: ViewInput, corners: [Pixel], result: LevelResult, cfg: Config = Config(), seed: UInt64 = 0, contourStatus: String? = nil,
                               trackingLabels: [String: String] = [:], imageGray: GrayImage? = nil, imageSaturation: GrayImage? = nil) -> [String: Any] {
        var out: [String: Any] = ["spec_version": specVersion, "computed_after_result": true,
                                  "privacy_note": "camera-relatief; geen locatie, geen absolute pose, geen beeld, geen puntenwolk"]
        out["frames"] = framesDetail(view, cfg: cfg, trackingLabels: trackingLabels)
        out["camera_gravity"] = cameraGravity(view)
        if let q = quadFromCorners(corners, view.intrinsics) { out["quad_from_corners"] = q } else { out["quad_from_corners"] = NSNull() }
        if view.depth == nil {
            out["planes_all"] = [Any](); out["gates_shadow"] = NSNull(); out["depth_profiles"] = NSNull(); out["glass_depth_summary"] = NSNull(); out["framing"] = NSNull()
        } else {
            let re = reanalyze(view, corners: corners, cfg: cfg, seed: seed)
            let regions = Regions(quad: corners, cfg: cfg)
            let dc = depthCells(view, regions: regions)!
            let rm = ringDepthMedian(dc.cells, cfg: cfg)
            out["planes_all"] = planesAll(view, re)
            out["gates_shadow"] = gatesShadow(view, corners: corners, cfg: cfg, seed: seed, result: result, contourStatus: contourStatus, re: re, regions: regions, cells: dc.cells)
            if let dpf = depthProfiles(view, corners: corners, regions: regions, cfg: cfg, zMed: re.zMed, ringMedian: rm) { out["depth_profiles"] = dpf } else { out["depth_profiles"] = NSNull() }
            out["glass_depth_summary"] = glassDepthSummary(dc.cells, cfg: cfg, ringMedian: rm)
            out["framing"] = framing(view, corners: corners, regions: regions, cells: dc.cells, sx: dc.sx, sy: dc.sy, cfg: cfg, zMed: re.zMed)
        }
        if let g = imageGray { out["edge_ladder_px"] = edgeLadder(gray: g, saturation: imageSaturation, corners: corners) } else { out["edge_ladder_px"] = NSNull() }
        out["gate_constants"] = gateConstantsExport()
        return out
    }
}
