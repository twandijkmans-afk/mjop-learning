"""Uitgebreide meetdiagnose (spec 1.1.0): ALLEEN extra diagnostiek, nooit invloed op een meetuitkomst.

Ontwerpregels (afgesproken met de eigenaar):
  * Deze module wordt NA het definitieve resultaat aangeroepen en leest alleen. `levels.py`, `depth_plane.py`, `config.py`, `plane.py` en `geometry.py`
    zijn ongewijzigd; alle bestaande drempels en poorten blijven precies zoals ze waren.
  * Alle nieuwe velden zijn getallen/labels: geen foto's, geen dieptekaarten, geen puntenwolken, geen locatie, geen absolute pose. Oriëntaties zijn
    CAMERA-RELATIEF (of t.o.v. de zwaartekracht); er staat geen wereldpositie in.
  * De "schaduwevaluatie" (`gates_shadow`) rekent de poorten die de echte meting na een eerdere blokkade niet meer bereikte onder een GEMARKEERDE
    hypothese (`host_hypothesis`). Er wordt nooit een hypothetische maat gepubliceerd; alleen waarden, limieten en uitslag per poort.
  * Alleen voor ontwikkeling en kalibratie. Alle drempels blijven PROVISIONAL_UNVALIDATED.
"""
import copy
import math

import numpy as np

from . import depth_plane as dp
from . import quality as q
from .config import DEFAULT, Config
from .geometry import UP, project, scale_polygon, signed_area, unproject_depth
from .levels import _angle_deg, analyze_subset, dims_from_corners, rectangularity_flags

SPEC_VERSION = "1.1.0"
SIDES = dp.SIDES                                  # TOP, RIGHT, BOTTOM, LEFT (randen van het kader: TL-TR, TR-BR, BR-BL, BL-TL)
CONTOUR_BLOCKING = ("UNVERIFIED", "PROPOSED_EXPANSION", "DETECTED_ENCLOSING_PANES", "EDITED_UNCONFIRMED")

# Beslisconstanten in de bestaande code die NIET in `Config` staan. Ze worden hier uitsluitend GEDOCUMENTEERD (en geëxporteerd) zodat een diagnose
# reproduceerbaar is; de code zelf is niet verplaatst of gewijzigd. `anchor_*` is een tekstfragment dat in de bron moet voorkomen: een test bewaakt dit,
# zodat een stille wijziging van de code of van deze lijst direct opvalt.
GATE_CONSTANTS = [
    {"name": "plane_parallel_abs_cos", "value": 0.97, "where": "depth_plane.pick_facade", "anchor_py": "abs(dot) > 0.97", "anchor_swift": "abs(dot) > 0.97"},
    {"name": "plane_step_factor_thr", "value": 1.5, "where": "depth_plane.pick_facade", "anchor_py": "step > 1.5 * thr", "anchor_swift": "step > 1.5 * thr"},
    {"name": "facade_robust_sigma_k_sigma", "value": 2.0, "where": "depth_plane.pick_facade", "anchor_py": "2.0 * sig + 0.012", "anchor_swift": "2.0 * sig + 0.012"},
    {"name": "facade_robust_sigma_add_m", "value": 0.012, "where": "depth_plane.pick_facade", "anchor_py": "2.0 * sig + 0.012", "anchor_swift": "2.0 * sig + 0.012"},
    {"name": "facade_rms_add_m", "value": 0.008, "where": "depth_plane.pick_facade", "anchor_py": "cfg.facade_rms_k * sig + 0.008", "anchor_swift": "cfg.facadeRmsK * sig + 0.008"},
    {"name": "facade_not_vertical_abs_ny", "value": 0.2, "where": "depth_plane.analyze_points", "anchor_py": 'facade["vertical"] > 0.2', "anchor_swift": "facade.vertical > 0.2"},
    {"name": "depth_coverage_min_fraction", "value": 0.25, "where": "levels.measure_depth_view", "anchor_py": "coverage < 0.25", "anchor_swift": "coverage < 0.25"},
    {"name": "depth_range_exceeded_fraction", "value": 0.3, "where": "levels.measure_depth_view", "anchor_py": "beyond / ring_total >= 0.3", "anchor_swift": "Double(beyond) / Double(ringTotal) >= 0.3"},
    {"name": "corner_tolerance_add_m", "value": 0.02, "where": "levels.measure_depth_view", "anchor_py": "cfg.corner_tol_k * sig + 0.02", "anchor_swift": "cfg.cornerTolK * sig + 0.02"},
    {"name": "flush_min_m", "value": 0.015, "where": "depth_plane.frame_offset", "anchor_py": "max(0.015, cfg.flush_tol_k", "anchor_swift": "max(0.015, cfg.flushTolK"},
    {"name": "quad_extent_step_factor_thr", "value": 1.2, "where": "depth_plane.quad_extent", "anchor_py": "abs(v) > 1.2 * thr", "anchor_swift": "1.2 * thr"},
    {"name": "quad_extent_min_distance_m", "value": 0.12, "where": "depth_plane.quad_extent", "anchor_py": '["d_in_m"] > 0.12', "anchor_swift": "mpp > 0.12"},
]


def _r(x, nd=4):
    if x is None:
        return None
    x = float(x)
    return round(x, nd) if math.isfinite(x) else None


def _median(vals):
    """Bovenmediaan: vaste definitie (gesorteerd, element n//2) zodat Swift en Python identiek zijn."""
    s = sorted(float(v) for v in vals)
    return s[len(s) // 2] if s else None


def _percentile_nr(vals, p):
    """Nearest-rank percentiel (geen interpolatie): index = ceil(p/100*n)-1."""
    s = sorted(float(v) for v in vals)
    if not s:
        return None
    k = max(1, int(math.ceil(p / 100.0 * len(s))))
    return s[min(k, len(s)) - 1]


def _depth_grid(view):
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    jj, ii = np.meshgrid(np.arange(Wd), np.arange(Hd))
    uv = np.stack([(jj + 0.5) * sx, (ii + 0.5) * sy], axis=-1).reshape(-1, 2)
    return uv, view.depth.reshape(-1).astype(float), sx, sy


# ------------------------------------------------------------------ frames, camera, kader (pose-vrij)

def frames_detail(view, supports, cfg: Config = DEFAULT):
    """Per frame: gebruikt/afgewezen met reden en de getallen waarop de bestaande selectieregel beslist (dt, rotatie, tracking, diepte)."""
    chosen, rejected = dp.select_support_frames(view, supports, cfg)
    chosen_ids = {id(f) for f in chosen}
    rej = iter(rejected)
    t0, R0 = view.pose[:3, 3], view.pose[:3, :3]
    out = [{"frame": view.frame_id, "role": "CAPTURE", "used": True, "reason": None, "has_depth": view.depth is not None,
            "tracking": view.tracking_state, "dt_to_capture_m": 0.0, "rot_to_capture_deg": 0.0, "meets_baseline": None, "meets_rotation": None}]
    for v in supports:
        used = id(v) in chosen_ids
        why = None if used else next(rej)[1]
        dt = float(np.linalg.norm(v.pose[:3, 3] - t0))
        cosr = (np.trace(v.pose[:3, :3].T @ R0) - 1) / 2
        rot = float(np.degrees(np.arccos(np.clip(cosr, -1, 1))))
        out.append({"frame": v.frame_id, "role": "SUPPORT", "used": used, "reason": why, "has_depth": v.depth is not None, "tracking": v.tracking_state,
                    "dt_to_capture_m": _r(dt, 5), "rot_to_capture_deg": _r(rot, 4), "meets_baseline": bool(dt >= cfg.min_baseline_m),
                    "meets_rotation": bool(rot >= cfg.min_rotation_deg)})
    return out


def camera_gravity(view):
    """Helling van de camera t.o.v. de zwaartekracht. pitch: optische as t.o.v. horizontaal (+ = omhoog). roll: de sensor-x-as t.o.v. horizontaal
    (de native sensor is landscape: bij een telefoon in portret is dit ongeveer +-90 graden). Geen positie, geen kompas, geen absolute oriëntatie."""
    R = view.pose[:3, :3]
    fwd, xax = R[:, 2], R[:, 0]
    return {"pitch_deg": _r(math.degrees(math.asin(max(-1.0, min(1.0, float(fwd @ UP))))), 3),
            "roll_sensor_x_deg": _r(math.degrees(math.asin(max(-1.0, min(1.0, float(xax @ UP))))), 3)}


def _solve(A, b):
    """Gauss-eliminatie met partiele pivotering (zelfde stappen als Swift)."""
    n = len(b)
    M = [list(map(float, A[i])) + [float(b[i])] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x


def quad_pose_free(corners_px, intr):
    """Uit alleen de vier hoeken + intrinsics, aangenomen dat het kader een rechthoek is: aspect b/h, hoek tussen de kaderassen (90 = consistent
    met een rechthoek en de lens) en de facing van het kadervlak t.o.v. de kijkstraal naar het kadermidden. Geen diepte, geen pose."""
    P = np.asarray(corners_px, float).reshape(4, 2)
    unit = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    A, b = [], []
    for (x, y), (u, v) in zip(unit, P):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    h = _solve(A, b)
    if h is None:
        return None
    H = np.array([[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]])
    Ki = np.linalg.inv(intr.K)
    a_, b_, t_ = Ki @ H[:, 0], Ki @ H[:, 1], Ki @ H[:, 2]
    if t_[2] < 0:
        a_, b_ = -a_, -b_
    na, nb = float(np.linalg.norm(a_)), float(np.linalg.norm(b_))
    if na < 1e-12 or nb < 1e-12:
        return None
    ang = math.degrees(math.acos(max(-1.0, min(1.0, float(a_ @ b_) / (na * nb)))))
    n = np.cross(a_, b_)
    n = n / np.linalg.norm(n)
    c = P.mean(axis=0)
    ray = Ki @ np.array([c[0], c[1], 1.0])
    ray = ray / np.linalg.norm(ray)
    if n[2] > 0:
        n = -n
    return {"aspect_w_over_h": _r(na / nb, 5), "axes_angle_deg": _r(ang, 3), "facing": _r(abs(float(n @ ray)), 5),
            "plane_normal_cam": [_r(x, 5) for x in n]}


# ------------------------------------------------------------------ herberekening van de punten/vlakken (zelfde stappen als de meting, read-only)

def _reanalyze(view, corners_px, cfg, seed, supports):
    """Zelfde invoer, zelfde seed en dezelfde bouwstenen als `levels.measure_depth_view` tot en met `sequential_planes`; geeft de ruwe vlakken terug."""
    corners = np.asarray(corners_px, float)
    v = copy.copy(view)
    frames, _ = dp.select_support_frames(v, supports, cfg)
    regions = dp.Regions(corners, cfg)
    chunks = []
    for f in frames:
        X, uv, z = dp.grid_points(f, cfg)
        if f is view:
            uvc, zc = uv, z
        else:
            uvc, zc = project(view.pose, view.intrinsics, X)
        ok = (zc > 0) & (uvc[:, 0] >= 0) & (uvc[:, 0] <= view.intrinsics.width) & (uvc[:, 1] >= 0) & (uvc[:, 1] <= view.intrinsics.height)
        X, uvc = X[ok], uvc[ok]
        kind, side = regions.classify(uvc)
        keep = kind > 0
        chunks.append((X[keep], kind[keep], side[keep], np.full(int(keep.sum()), len(chunks))))
    X = np.vstack([c[0] for c in chunks]); kind = np.concatenate([c[1] for c in chunks]); side = np.concatenate([c[2] for c in chunks])
    fidx = np.concatenate([c[3] for c in chunks])
    ring = kind == 1
    Pr, sr = X[ring], side[ring]
    cam = view.pose[:3, 3]
    z_med = float(np.median(np.linalg.norm(Pr - cam, axis=1))) if len(Pr) else 3.0
    thr = dp.thr_at(z_med, cfg)
    planes = []
    if len(Pr) >= cfg.min_plane_points:
        planes, _ = dp.sequential_planes(Pr, sr, thr, cfg, seed)
        dp.classify_planes(planes, cam, cfg)
    qdiag_m = float(np.linalg.norm(corners[2] - corners[0])) * z_med / view.intrinsics.fx
    return dict(frames=frames, regions=regions, X=X, kind=kind, side=side, fidx=fidx, Pr=Pr, sr=sr, planes=planes, z_med=z_med, thr=thr, qdiag_m=qdiag_m)


def planes_all(view, planes, Pr):
    """Alle vlakken, CAMERA-RELATIEF (normaal en zwaartepunt in het camerastelsel), met omvang, aandeel per zijde en hoek t.o.v. het grootste vlak."""
    if not planes:
        return []
    R, t = view.pose[:3, :3], view.pose[:3, 3]
    big = max(planes, key=lambda p: p["count"])
    out = []
    for i, p in enumerate(planes):
        n_cam = R.T @ p["n"]
        c_cam = R.T @ (p["centroid"] - t)
        sides = np.asarray(p["sides"])
        maj, mnr = dp.inplane_std(Pr[p["idx"]], p["n"])
        out.append({"index": i, "role": p["role"], "count": int(p["count"]), "facing": _r(p["facing"], 5), "vertical": _r(p["vertical"], 5),
                    "rms_m": _r(p["rms"], 5), "spread_m": _r(p["spread"], 5), "normal_cam": [_r(x, 5) for x in n_cam], "centroid_cam": [_r(x, 4) for x in c_cam],
                    "sides_counts": [int(x) for x in sides], "sides_shares": [_r(float(x) / max(int(p["count"]), 1), 4) for x in sides],
                    "angle_to_largest_deg": _r(math.degrees(math.acos(min(1.0, abs(float(p["n"] @ big["n"]))))), 3),
                    "is_largest": bool(p is big), "extent_major_std_m": _r(maj, 5), "extent_minor_std_m": _r(mnr, 5)})
    return out


# ------------------------------------------------------------------ diepteprofielen, glas, kader in beeld

def _ring_depth_median(view, corners, cfg):
    uv, z, _, _ = _depth_grid(view)
    reg = dp.Regions(corners, cfg)
    kind, _ = reg.classify(uv)
    ok = (kind == 1) & np.isfinite(z) & (z >= cfg.depth_min_range_m) & (z <= cfg.depth_max_range_m)
    return _median(z[ok]) if ok.any() else None


def depth_profiles(view, corners_px, cfg: Config, z_med, ring_depth_median):
    """Per zijde: pixels, geldige pixels en mediane diepteafwijking (t.o.v. de ringmediaan, langs de optische as) per afstandsklasse van 2 cm vanaf de
    kaderrand: van 8 cm binnen het kader tot 40 cm buiten het kader. Afstand in cm via mediane afstand / brandpuntsafstand. Alleen getallen."""
    corners = np.asarray(corners_px, float)
    uv, z, sx, sy = _depth_grid(view)
    reg = dp.Regions(corners, cfg)
    dist = np.stack([reg._cross_dist(a, b, uv) for a, b in reg.edges], axis=1)          # inwaarts positief, pixels
    norm = dist / np.array(reg.h)[None, :]
    side = np.argmin(norm, axis=1)
    idx = np.arange(len(uv))
    d_in = dist[idx, side]
    cm_per_px = z_med / view.intrinsics.fx * 100.0
    outward_cm = -d_in * cm_per_px
    t_par = np.zeros(len(uv))
    for k, (a, b) in enumerate(reg.edges):
        e = b - a
        m = side == k
        t_par[m] = ((uv[m] - a) @ e) / float(e @ e)
    valid = np.isfinite(z) & (z >= cfg.depth_min_range_m) & (z <= cfg.depth_max_range_m)
    BIN, LO, HI = 2.0, -8.0, 40.0
    nb = int(round((HI - LO) / BIN))
    sides_out = {}
    for k, name in enumerate(SIDES):
        m = (side == k) & (t_par >= 0.0) & (t_par <= 1.0)
        bins = []
        bi = np.floor((outward_cm - LO) / BIN).astype(int)
        for b in range(nb):
            mb = m & (bi == b)
            vb = mb & valid
            med = None
            if vb.any() and ring_depth_median is not None:
                med = _median(z[vb] - ring_depth_median)
            bins.append({"from_cm": LO + b * BIN, "to_cm": LO + (b + 1) * BIN, "pixels": int(mb.sum()), "valid": int(vb.sum()), "median_dz_m": _r(med, 4)})
        sides_out[name] = bins
    return {"unit": "cm uitwaarts vanaf de kaderrand (negatief = binnen het kader)", "bin_cm": BIN, "cm_per_px": _r(cm_per_px, 5),
            "ring_depth_median_m": _r(ring_depth_median, 4), "sides": sides_out}


def glass_depth_summary(view, corners_px, cfg: Config, ring_depth_median):
    """Diepteverdeling binnen het glasgebied (< 0,70 x kader) t.o.v. de ringmediaan: percentielen (nearest-rank) en aandeel voorbij de ring."""
    corners = np.asarray(corners_px, float)
    uv, z, _, _ = _depth_grid(view)
    reg = dp.Regions(corners, cfg)
    kind, _ = reg.classify(uv)
    g = kind == 3
    total = int(g.sum())
    valid = g & np.isfinite(z) & (z > 0)
    nv = int(valid.sum())
    out = {"pixels": total, "valid": nv, "valid_fraction": _r(nv / total, 4) if total else None, "reference": "ring_depth_median"}
    if nv and ring_depth_median is not None:
        dz = z[valid] - ring_depth_median
        out.update(percentiles_dz_m={str(p): _r(_percentile_nr(dz, p), 4) for p in (5, 25, 50, 75, 95)},
                   beyond_ring_fraction=_r(float((dz > cfg.glass_beyond_plane_m).mean()), 4), beyond_limit_m=cfg.glass_beyond_plane_m)
    else:
        out.update(percentiles_dz_m=None, beyond_ring_fraction=None, beyond_limit_m=cfg.glass_beyond_plane_m)
    return out


def framing(view, corners_px, cfg: Config, z_med):
    """Kader t.o.v. de beeldrand (in NATIVE sensorpixels, landscape; bij een telefoon in portret is native rechts = onderkant) en hoeveel van de ring in beeld ligt. `ring_fit_*` zegt alleen hoe ver de ring buiten het beeld valt; er is
    GEEN verplichte afstand: de analyse mag met de zichtbare ring werken."""
    corners = np.asarray(corners_px, float)
    W, H = view.intrinsics.width, view.intrinsics.height
    reg = dp.Regions(corners, cfg)
    uv, z, sx, sy = _depth_grid(view)
    kind, side = reg.classify(uv)
    ring = kind == 1
    valid = np.isfinite(z) & (z >= cfg.depth_min_range_m) & (z <= cfg.depth_max_range_m)
    per_side = {SIDES[k]: {"ring_pixels": int((ring & (side == k)).sum()), "ring_valid": int((ring & (side == k) & valid).sum())} for k in range(4)}
    ro, ri = reg.poly["ring_out"], reg.poly["ring_in"]
    full = abs(signed_area(ro)) - abs(signed_area(ri))
    in_img = float(ring.sum()) * sx * sy
    bb = (float(ro[:, 0].min()), float(ro[:, 1].min()), float(ro[:, 0].max()), float(ro[:, 1].max()))
    res = {"margins_px": {"left": _r(corners[:, 0].min(), 2), "right": _r(W - corners[:, 0].max(), 2), "top": _r(corners[:, 1].min(), 2),
                          "bottom": _r(H - corners[:, 1].max(), 2)},
           "ring_in_view_fraction": _r(in_img / full, 4) if full > 0 else None, "ring_per_side": per_side,
           "ring_out_overflow_px": {"left": _r(max(0.0, -bb[0]), 1), "right": _r(max(0.0, bb[2] - W), 1), "top": _r(max(0.0, -bb[1]), 1),
                                    "bottom": _r(max(0.0, bb[3] - H), 1)},
           "ring_fit_factor_u": _r((bb[2] - bb[0]) / W, 4), "ring_fit_factor_v": _r((bb[3] - bb[1]) / H, 4)}
    f = max(res["ring_fit_factor_u"], res["ring_fit_factor_v"], 1.0)
    res["distance_for_full_ring_m"] = _r(z_med * f, 3) if z_med else None
    res["note"] = "informatief; geen eis. Bij een beperkte opnameafstand werkt de analyse met de zichtbare ring."
    return res


# ------------------------------------------------------------------ schaduwevaluatie van de poorten

def _gate(gid, status, value=None, limit=None, note=None):
    return {"id": gid, "status": status, "value": value, "limit": limit, "note": note}


def _side_rule(covered):
    c = int(sum(covered))
    if c < 2:
        return False
    if c == 2 and not ((covered[0] and covered[2]) or (covered[1] and covered[3])):
        return False
    return True


def gates_shadow(view, corners_px, cfg: Config, seed, supports, result, contour_status=None, re=None):
    """Elke poort afzonderlijk, onder een gemarkeerde hypothese voor het gastvlak. Verandert niets aan `result`."""
    corners = np.asarray(corners_px, float)
    re = re or _reanalyze(view, corners, cfg, seed, supports)
    planes, Pr, sr, z_med, thr = re["planes"], re["Pr"], re["sr"], re["z_med"], re["thr"]
    gates = []
    ring_valid = result.diag.get("ring_valid")
    cov = result.diag.get("ring_coverage")
    gates.append(_gate("DEPTH_COVERAGE", "NOT_EVALUATED" if cov is None else ("PASS" if (ring_valid >= cfg.annulus_min_points and cov >= 0.25) else "FAIL"),
                       value={"ring_valid": ring_valid, "coverage": cov}, limit={"min_points": cfg.annulus_min_points, "min_coverage": 0.25}))
    if not planes:
        gates.append(_gate("FACADE_SELECTION", "FAIL", note="geen vlakken gevonden"))
        return {"host_hypothesis": None, "gates": gates, "reproduces_result_planes": False}
    reproduces = [int(p["count"]) for p in planes] == [int(p["count"]) for p in (result.diag.get("planes") or [])]
    # 1) echte selectie (zelfde aanroep als de meting)
    sel_planes = [dict(p) for p in planes]
    sel_fac, sel_code, sel_detail, _ = dp.pick_facade(sel_planes, Pr, sr, z_med, cfg, re["qdiag_m"])
    gates.append(_gate("FACADE_SELECTION", "PASS" if sel_fac is not None else "FAIL", note=None if sel_fac is not None else f"{sel_code}: {sel_detail}"))
    # 2) hypothese voor het gastvlak
    if sel_fac is not None:
        hi = next(i for i, p in enumerate(sel_planes) if p is sel_fac)
        src = "SELECTED"
    else:
        cands = [i for i, p in enumerate(planes) if p["vertical"] <= cfg.facade_max_vertical]
        if not cands:
            gates.append(_gate("FACADE_FACING", "FAIL", note="geen verticaal vlak"))
            return {"host_hypothesis": None, "gates": gates, "reproduces_result_planes": reproduces}
        hi = max(cands, key=lambda i: (round(planes[i]["facing"], 6), planes[i]["count"]))
        src = "BEST_FACING_VERTICAL"
    host = planes[hi]
    hyp = {"source": src, "plane_index": hi, "facing": _r(host["facing"], 5), "count": int(host["count"]), "vertical": _r(host["vertical"], 5),
           "note": "hypothese voor diagnose; geen uitspraak dat dit de gevel is" if src != "SELECTED" else "gekozen door de meting"}
    gates.append(_gate("FACADE_FACING", "PASS" if host["facing"] >= cfg.facade_min_facing else "FAIL", value=_r(host["facing"], 5), limit=cfg.facade_min_facing))
    # 3) alle gastvlak-poorten afzonderlijk (zelfde pick_facade, alleen dit vlak als kandidaat)
    forced = [dict(p) for p in planes]
    for i, p in enumerate(forced):
        p["role"] = "FACADE_CANDIDATE" if i == hi else "REVEAL_OR_LEDGE"
    fac_f, code_f, detail_f, A = dp.pick_facade(forced, Pr, sr, z_med, cfg, re["qdiag_m"])
    hostf = forced[hi]
    loc = A.get("local") or {}
    sup = A.get("support")
    gates.append(_gate("FACADE_SUPPORT", "NOT_EVALUATED" if sup is None else ("PASS" if sup >= cfg.facade_support_min else "FAIL"), value=_r(sup, 4), limit=cfg.facade_support_min))
    gates.append(_gate("FACADE_LOCAL_RMS", "NOT_EVALUATED" if not loc else ("PASS" if loc["rms_m"] <= loc["rms_limit_m"] else "FAIL"), value=loc.get("rms_m"), limit=loc.get("rms_limit_m")))
    gates.append(_gate("FACADE_LOCAL_ROBUST", "NOT_EVALUATED" if not loc else ("PASS" if loc["robust_sigma_m"] <= loc["robust_limit_m"] else "FAIL"), value=loc.get("robust_sigma_m"), limit=loc.get("robust_limit_m")))
    un = A.get("unexplained")
    gates.append(_gate("FACADE_UNEXPLAINED", "NOT_EVALUATED" if un is None else ("PASS" if un["share"] <= cfg.unexplained_max else "FAIL"), value=None if un is None else un["share"], limit=cfg.unexplained_max))
    sd = A.get("sides")
    gates.append(_gate("FACADE_SIDE_COVERAGE", "NOT_EVALUATED" if sd is None else ("PASS" if _side_rule(sd["covered"]) else "FAIL"),
                       value=None if sd is None else {"covered": sd["covered"], "counts": sd["counts"]}, limit={"min_points_per_side": None if sd is None else sd["min_points_per_side"]}))
    ex = A.get("extent")
    gates.append(_gate("FACADE_EXTENT", "NOT_EVALUATED" if ex is None or ex["min_required_m"] is None else ("PASS" if ex["minor_std_m"] >= ex["min_required_m"] else "FAIL"),
                       value=None if ex is None else ex["minor_std_m"], limit=None if ex is None else ex["min_required_m"]))
    # 4) kozijnvlak en geometrie onder dezelfde hypothese
    band = re["kind"] == 2
    frm = dp.frame_offset(re["X"][band], re["side"][band], hostf, z_med, cfg)
    mode_ok = frm["mode"] in ("FLUSH", "RECESSED", "PROTRUDING")
    gates.append(_gate("FRAME_PLANE", "PASS" if mode_ok else "FAIL", value={"mode": frm["mode"], "offset_m": _r(frm.get("offset_m"), 4),
                                                                      "support": {k: v["support"] for k, v in frm["per_side"].items()}}, limit={"min_sides": 2}))
    offset = float(frm["offset_m"]) if mode_ok else 0.0
    note_off = None if mode_ok else "offset 0 aangenomen om de overige poorten te kunnen beoordelen"
    n, dpl = hostf["n"], hostf["d"] + offset
    C, t, cosinc = dp.plane_geometry(view, corners, n, dpl)
    if np.any(np.isnan(t)):
        gates.append(_gate("CORNERS_ON_PLANE", "FAIL", note=note_off))
        geom_ok = False
    else:
        geom_ok = True
        gates.append(_gate("INCIDENCE", "PASS" if float(cosinc.min()) >= cfg.min_incidence_cos else "FAIL", value=_r(float(cosinc.min()), 4), limit=cfg.min_incidence_cos, note=note_off))
    if geom_ok:
        sig = dp.sigma_at(z_med, cfg)
        tol_c = cfg.corner_tol_k * sig + 0.02
        zax = view.pose[:3, :3][:, 2]
        o_cam = view.pose[:3, 3]
        exp_z = (C - o_cam) @ zax
        contra, dev = 0, []
        for k in range(4):
            vals = dp.corner_values(view, corners[k])
            if len(vals) < 3:
                dev.append(None)
                continue
            dd = vals - float(exp_z[k])
            dev.append(_r(float(dd[np.argmin(np.abs(dd))]), 4))
            if not (np.abs(dd) <= tol_c).any():
                contra += 1
        gates.append(_gate("CORNER_DEPTH", "PASS" if contra < cfg.corners_contradict_block else "FAIL", value={"contradicting": contra, "deviation_m": dev}, limit={"block_at": cfg.corners_contradict_block, "tolerance_m": _r(tol_c, 4)}, note=note_off))
        bad = rectangularity_flags(C, cfg)
        gates.append(_gate("RECTANGULARITY", "PASS" if not bad else "FAIL", value=bad or None, limit={"edge_ratio": cfg.rect_edge_ratio_tol, "angle_deg": cfg.rect_angle_tol_deg}, note=note_off))
        w, h = dims_from_corners(C, UP)
        in_rng = bool(cfg.min_dim_m <= w <= cfg.max_dim_m and cfg.min_dim_m <= h <= cfg.max_dim_m)
        gates.append(_gate("DIMENSION_RANGE", "PASS" if in_rng else "FAIL", limit={"min_m": cfg.min_dim_m, "max_m": cfg.max_dim_m}, note="alleen het bereik; de waarde zelf wordt niet gepubliceerd (hypothetisch)"))
        qe, larger, inside = dp.quad_extent(view, corners, n, dpl, z_med, cfg)
        gates.append(_gate("QUAD_EXTENT", "PASS" if (larger < 3 and inside < 3) else "FAIL", value={"sides_deeper_step_inside": larger, "sides_closer_step_outside": inside, "sides": qe}, limit={"block_at_sides": 3}, note=note_off))
        # glas (adviserend in de meting)
        uv, zz, _, _ = _depth_grid(view)
        kind_all, _ = dp.Regions(corners, cfg).classify(uv)
        gm = kind_all == 3
        valid_z = np.isfinite(zz) & (zz > 0)
        if gm.sum():
            vin = gm & valid_z
            fv = float(vin.sum() / gm.sum())
            bf = 0.0
            if vin.sum():
                Pg = unproject_depth(view.pose, view.intrinsics, uv[vin], zz[vin])
                bf = float((np.abs(Pg @ n - dpl) > cfg.glass_beyond_plane_m).mean())
            gates.append(_gate("GLASS", "PASS" if (fv >= cfg.glass_min_valid_fraction and bf <= cfg.glass_max_beyond_fraction) else "FAIL",
                               value={"valid_fraction": _r(fv, 4), "beyond_fraction": _r(bf, 4)}, limit={"min_valid": cfg.glass_min_valid_fraction, "max_beyond": cfg.glass_max_beyond_fraction}, note="adviserend in de meting"))
        else:
            gates.append(_gate("GLASS", "NOT_APPLICABLE", note="geen glasgebied"))
        # consistentie tussen onafhankelijke frames
        frames = re["frames"]
        if len(frames) > 1:
            ref_w, ref_h = w, h
            fails, usable = [], 0
            for fi, f in enumerate(frames):
                m = re["fidx"] == fi
                sub = analyze_subset(view, re["X"][m], re["kind"][m], re["side"][m], corners, cfg, seed + 101 * (fi + 1), float(np.linalg.norm(corners[2] - corners[0])))
                if not sub.get("ok"):
                    continue
                usable += 1
                if ((abs(sub["width_m"] - ref_w) > cfg.frame_tol_rel * ref_w + cfg.frame_tol_abs_m) or (abs(sub["height_m"] - ref_h) > cfg.frame_tol_rel * ref_h + cfg.frame_tol_abs_m)
                        or _angle_deg(np.array(sub["normal"]), n) > cfg.frame_normal_deg):
                    fails.append(f.frame_id)
            gates.append(_gate("FRAMES_CONSISTENCY", "FAIL" if fails else "PASS", value={"usable": usable, "inconsistent": fails}, limit={"tol_rel": cfg.frame_tol_rel, "tol_abs_m": cfg.frame_tol_abs_m}, note=note_off))
        else:
            gates.append(_gate("FRAMES_CONSISTENCY", "NOT_APPLICABLE", note="één onafhankelijk frame"))
    else:
        for gid in ("CORNER_DEPTH", "RECTANGULARITY", "DIMENSION_RANGE", "QUAD_EXTENT", "GLASS", "FRAMES_CONSISTENCY"):
            gates.append(_gate(gid, "NOT_EVALUATED", note="hoekstralen snijden het vlak niet"))
    if contour_status is None:
        gates.append(_gate("OUTER_CONTOUR_CONFIRMED", "NOT_EVALUATED", note="status niet meegegeven"))
    else:
        gates.append(_gate("OUTER_CONTOUR_CONFIRMED", "FAIL" if contour_status in CONTOUR_BLOCKING else "PASS", value=contour_status,
                           note="poort van de app (ContourGate); niet onderdeel van de LiDAR-meting"))
    return {"host_hypothesis": hyp, "gates": gates, "reproduces_result_planes": reproduces}


# ------------------------------------------------------------------ beeldranden (alleen getallen)

def saturation_channel(rgb):
    """RGB (H,W,3, 0..255) -> verzadiging 0..255 (HSV: (max-min)/max)."""
    a = np.asarray(rgb, float)
    mx, mn = a.max(axis=-1), a.min(axis=-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0) * 255.0
    return np.clip(np.rint(s), 0, 255)                      # afgerond zoals de Swift-versie (UInt8)


def edge_ladder(gray, sat, corners_px, max_offsets=160):
    """Randsterkte (en consistentie) langs elke kaderzijde naar buiten, voor grijs en verzadiging. Alleen getallenreeksen; het beeld is niet te reconstrueren."""
    from .facade import edge_profile
    quad = [tuple(map(float, p)) for p in np.asarray(corners_px, float)]
    out = {"unit": "px uitwaarts in het beeld", "sides": {}}
    for s, name in enumerate(SIDES):
        offs, st, co, _n = edge_profile(gray, quad, s)
        entry = {"offsets_px": [int(o) for o in offs[:max_offsets]], "strength_gray": [_r(v, 2) for v in st[:max_offsets]], "consistency_gray": [_r(v, 3) for v in co[:max_offsets]]}
        if sat is not None:
            o2, st2, co2, _ = edge_profile(sat, quad, s)
            entry["strength_saturation"] = [_r(v, 2) for v in st2[:max_offsets]]
        out["sides"][name] = entry
    return out


def gate_constants_export():
    return [{"name": g["name"], "value": g["value"], "where": g["where"]} for g in GATE_CONSTANTS]


# ------------------------------------------------------------------ samenstelling

def compute(view, corners_px, result, *, cfg: Config = DEFAULT, seed=0, supports=(), contour_status=None, image_gray=None, image_saturation=None):
    """Bouwt het blok `extended_diagnostics`. Leest alleen; `result` en alle invoer blijven onveranderd."""
    corners = np.asarray(corners_px, float)
    out = {"spec_version": SPEC_VERSION, "computed_after_result": True,
           "privacy_note": "camera-relatief; geen locatie, geen absolute pose, geen beeld, geen puntenwolk"}
    out["frames"] = frames_detail(view, list(supports), cfg)
    out["camera_gravity"] = camera_gravity(view)
    out["quad_from_corners"] = quad_pose_free(corners, view.intrinsics)
    if view.depth is None:
        out.update(planes_all=[], gates_shadow=None, depth_profiles=None, glass_depth_summary=None, framing=None)
    else:
        re = _reanalyze(view, corners, cfg, seed, list(supports))
        out["planes_all"] = planes_all(view, re["planes"], re["Pr"])
        out["gates_shadow"] = gates_shadow(view, corners, cfg, seed, list(supports), result, contour_status, re)
        rdm = _ring_depth_median(view, corners, cfg)
        out["depth_profiles"] = depth_profiles(view, corners, cfg, re["z_med"], rdm)
        out["glass_depth_summary"] = glass_depth_summary(view, corners, cfg, rdm)
        out["framing"] = framing(view, corners, cfg, re["z_med"])
    out["edge_ladder_px"] = edge_ladder(image_gray, image_saturation, corners) if image_gray is not None else None
    out["gate_constants"] = gate_constants_export()
    return out
