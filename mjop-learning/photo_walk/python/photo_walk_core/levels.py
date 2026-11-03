"""Meetniveaus A (metrische diepte), B (AR-geometrie / triangulatie) en C (referentiemeting).

Elk niveau geeft een LevelResult. Een resultaat met blokkerende flags bevat GEEN metrische maat (width/height None).
De onzekerheid is modelgebaseerd (Monte Carlo met vaste seed) en NIET gevalideerd tegen echte metingen.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import quality as q
from .config import Config
from .geometry import (UP, angle_between_deg, in_convex_polygon, intersect_rays_plane, is_simple_convex_quad, plane_basis,
                       project, rays_world, scale_polygon, signed_plane_distance, unproject_depth)
from .model import TRACKING_NORMAL
from . import depth_plane as dp
from .plane import fit_plane_ransac


@dataclass
class LevelResult:
    level: str                       # "A" | "B" | "C"
    scale_method: str                # LIDAR_DEPTH_PLANE | AR_TRIANGULATION_VIO | REFERENCE_DISTANCE | NONE
    flags: list = field(default_factory=list)
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    sigma_w: Optional[float] = None
    sigma_h: Optional[float] = None
    sigma_area: Optional[float] = None
    aspect_ratio: Optional[float] = None     # w/h; schaalvrij
    corners_w: Optional[np.ndarray] = None   # (4,3) wereldcoordinaten (m), TL,TR,BR,BL
    plane_n: Optional[np.ndarray] = None
    plane_d: Optional[float] = None
    center_w: Optional[np.ndarray] = None
    view_ids: tuple = ()
    scale_evidence: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    independent_frames: int = 1
    diag: dict = field(default_factory=dict)             # meetdiagnose (numeriek, exporteerbaar)

    @property
    def ok(self):
        return self.width_m is not None and not q.blocking(self.flags)


# ---------------------------------------------------------------- hulpfuncties

def dims_from_corners(C, up):
    """Breedte en hoogte uit 4 hoeken (TL,TR,BR,BL) in 3D. De 'breedte' is het paar randen dat het minst met `up` meeloopt, zodat
    een 90 graden gedraaide hoekvolgorde geen verwisselde maten geeft."""
    C = np.asarray(C, float)
    e = [C[1] - C[0], C[2] - C[1], C[2] - C[3], C[3] - C[0]]       # boven, rechts, onder, links
    l = [np.linalg.norm(x) for x in e]
    vert = lambda x, ln: abs(x @ up) / max(ln, 1e-12)
    a = (vert(e[0], l[0]) + vert(e[2], l[2])) / 2     # 'verticaliteit' van het paar (0,2)
    b = (vert(e[1], l[1]) + vert(e[3], l[3])) / 2
    pair02, pair13 = (l[0] + l[2]) / 2, (l[1] + l[3]) / 2
    if a <= b:
        return pair02, pair13
    return pair13, pair02


def rectangularity_flags(C, cfg: Config):
    C = np.asarray(C, float)
    e = [C[1] - C[0], C[2] - C[1], C[2] - C[3], C[3] - C[0]]
    l = [np.linalg.norm(x) for x in e]
    bad = []
    for i, j in ((0, 2), (1, 3)):
        if abs(l[i] - l[j]) / max((l[i] + l[j]) / 2, 1e-9) > cfg.rect_edge_ratio_tol:
            bad.append(f"overstaande randen {i}/{j} verschillen")
    for i in range(4):
        a = C[(i + 1) % 4] - C[i]
        b = C[(i - 1) % 4] - C[i]
        ang = np.degrees(np.arccos(np.clip(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1)))
        if abs(ang - 90) > cfg.rect_angle_tol_deg:
            bad.append(f"hoek {i} = {ang:.1f} graden")
    return bad


def _depth_grid(view):
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    jj, ii = np.meshgrid(np.arange(Wd), np.arange(Hd))
    return np.stack([(jj + 0.5) * sx, (ii + 0.5) * sy], axis=-1).reshape(-1, 2), view.depth.reshape(-1)


def _valid(z, cfg):
    return np.isfinite(z) & (z > 0)


def _local_depth(view, uv, r=1):
    Hd, Wd = view.depth.shape
    sx, sy = view.intrinsics.width / Wd, view.intrinsics.height / Hd
    j, i = int(uv[0] / sx), int(uv[1] / sy)
    patch = view.depth[max(i - r, 0):i + r + 1, max(j - r, 0):j + r + 1].ravel()
    patch = patch[np.isfinite(patch) & (patch > 0)]
    return float(np.median(patch)) if len(patch) >= 3 else None


def _corner_inside(view, corners):
    w, h = view.intrinsics.width, view.intrinsics.height
    return bool(np.all((corners[:, 0] >= 0) & (corners[:, 0] <= w) & (corners[:, 1] >= 0) & (corners[:, 1] <= h)))


def fit_facade_plane(view, corners_px, cfg: Config, seed=0):
    """Vlak van de gevel RONDOM het kozijn (annulus), niet uit de pixels op de hoeken of in het glas.
    Geeft (PlaneFit | None, flags, diag)."""
    flags, diag = [], {}
    uv, z = _depth_grid(view)
    zs = z
    ring = in_convex_polygon(uv, scale_polygon(corners_px, cfg.annulus_outer_scale)) & ~in_convex_polygon(uv, scale_polygon(corners_px, cfg.annulus_inner_scale))
    n_ring = int(ring.sum())
    ok = ring & _valid(zs, cfg)
    beyond = ok & (zs > cfg.depth_max_range_m)
    ok &= (zs >= cfg.depth_min_range_m) & (zs <= cfg.depth_max_range_m)
    n_ok = int(ok.sum())
    diag.update(annulus_pixels=n_ring, annulus_valid=n_ok, depth_coverage=(n_ok / n_ring if n_ring else 0.0))
    if n_ring and beyond.sum() / n_ring >= 0.3:
        flags.append(q.flag("DEPTH_RANGE_EXCEEDED", f"{int(beyond.sum())} van {n_ring} ringpixels voorbij {cfg.depth_max_range_m} m"))
        return None, flags, diag
    if n_ok < cfg.annulus_min_points or diag["depth_coverage"] < cfg.annulus_min_valid_fraction:
        flags.append(q.flag("DEPTH_COVERAGE_LOW", f"{n_ok} geldige punten, dekking {diag['depth_coverage']:.2f}"))
        return None, flags, diag
    P = unproject_depth(view.pose, view.intrinsics, uv[ok], zs[ok])
    fit = fit_plane_ransac(P, cfg.plane_ransac_threshold_m, cfg.plane_ransac_iterations, seed)
    if fit is None or fit.inlier_ratio < cfg.plane_min_inlier_ratio:
        flags.append(q.flag("MIXED_FACADE_DEPTH", f"inlierratio {0 if fit is None else fit.inlier_ratio:.2f}"))
        return fit, flags, diag
    if fit.rms_m > cfg.plane_max_rms_m:
        flags.append(q.flag("PLANE_NOISY", f"rms {fit.rms_m:.3f} m"))
        return fit, flags, diag
    # n zodanig dat hij naar de camera wijst
    if fit.n @ (view.pose[:3, 3] - fit.centroid) < 0:
        fit.n, fit.d = -fit.n, -fit.d
    diag.update(plane_inlier_ratio=fit.inlier_ratio, plane_rms_m=fit.rms_m)
    if abs(fit.n @ UP) > 0.3:
        flags.append(q.flag("FACADE_NOT_VERTICAL", f"|n.up|={abs(fit.n @ UP):.2f}"))
    return fit, flags, diag


def _tilt(n, delta):
    m = n + delta
    return m / np.linalg.norm(m)


# ---------------------------------------------------------------- niveau A (v2: meervlaks, meerdere onafhankelijke frames)

def _angle_deg(a, b):
    return float(np.degrees(np.arccos(np.clip(abs(a @ b) / (np.linalg.norm(a) * np.linalg.norm(b)), -1, 1))))


def measure_depth_view(view, corners_px, cfg: Config, seed=0, obstruction=False, supports=()):
    """Niveau A voor een foto, optioneel met ondersteunende dieptaframes (`supports`, uit de korte buffer vlak voor de foto).
    Geeft altijd diagnostiek in `result.diag`; bij een blokkerende vlag is er GEEN metrische waarde."""
    res = LevelResult("A", "LIDAR_DEPTH_PLANE", view_ids=(view.frame_id,))
    fl = res.flags
    corners_px = np.asarray(corners_px, float)
    diag = res.diag
    diag.update(algorithm="LIDAR_PLANE_V2", frame_id=view.frame_id, tracking_capture=view.tracking_state)
    if view.tracking_state != TRACKING_NORMAL:
        fl.append(q.flag("TRACKING_LOST", view.tracking_state))
    if view.depth is None:
        fl.append(q.flag("NO_DEPTH"))
    if not is_simple_convex_quad(corners_px, image_area=view.intrinsics.width * view.intrinsics.height):
        fl.append(q.flag("CORNER_ORDER_INVALID"))
    elif not _corner_inside(view, corners_px):
        fl.append(q.flag("CORNER_OUTSIDE_IMAGE"))
    if obstruction:
        fl.append(q.flag("OBSTRUCTION_REPORTED"))
    if q.blocking(fl):
        _finish_diag(res, fl)
        return res
    frames, rejected = dp.select_support_frames(view, supports, cfg)
    regions = dp.Regions(corners_px, cfg)
    # --- dekking in het capture-frame (alle pixels, ook ongeldige)
    uv_all, z_all = _depth_grid(view)
    kind_all, _ = regions.classify(uv_all)
    ring_total = int((kind_all == 1).sum())
    valid_z = np.isfinite(z_all) & (z_all > 0)
    ring_valid_range = int(((kind_all == 1) & valid_z & (z_all >= cfg.depth_min_range_m) & (z_all <= cfg.depth_max_range_m)).sum())
    beyond = int(((kind_all == 1) & valid_z & (z_all > cfg.depth_max_range_m)).sum())
    coverage = ring_valid_range / ring_total if ring_total else 0.0
    diag.update(frames_total=1 + len(supports), frames_independent_candidates=len(frames), frames_rejected=[{"frame": f, "why": w} for f, w in rejected],
                ring_pixels=ring_total, ring_valid=ring_valid_range, ring_coverage=round(coverage, 4),
                baseline_m=round(max([float(np.linalg.norm(a.pose[:3, 3] - b.pose[:3, 3])) for a in frames for b in frames] + [0.0]), 4))
    if ring_total and beyond / ring_total >= 0.3:
        fl.append(q.flag("DEPTH_RANGE_EXCEEDED", f"{beyond} van {ring_total} ringpixels voorbij {cfg.depth_max_range_m} m"))
    elif ring_valid_range < cfg.annulus_min_points or coverage < 0.25:
        fl.append(q.flag("DEPTH_COVERAGE_LOW", f"{ring_valid_range} geldige ringpunten, dekking {coverage:.2f}"))
    if q.blocking(fl):
        _finish_diag(res, fl)
        return res
    # --- punten van alle onafhankelijke frames naar het capture-beeldgebied
    chunks = []
    for fi, f in enumerate(frames):
        X, uv, z = dp.grid_points(f, cfg)
        if f is view:
            uvc, zc = uv, z
        else:
            uvc, zc = project(view.pose, view.intrinsics, X)
        ok = (zc > 0) & (uvc[:, 0] >= 0) & (uvc[:, 0] <= view.intrinsics.width) & (uvc[:, 1] >= 0) & (uvc[:, 1] <= view.intrinsics.height)
        X, uvc = X[ok], uvc[ok]
        kind, side = regions.classify(uvc)
        keep = kind > 0
        chunks.append((X[keep], kind[keep], side[keep], np.full(int(keep.sum()), fi)))
    Xa = np.vstack([c[0] for c in chunks]); ka = np.concatenate([c[1] for c in chunks]); sa = np.concatenate([c[2] for c in chunks])
    fa = np.concatenate([c[3] for c in chunks])
    diag.update(points_valid_total=int(len(Xa)), points_ring=int((ka == 1).sum()), points_band=int((ka == 2).sum()), points_glass=int((ka == 3).sum()))
    qdiag = float(np.linalg.norm(corners_px[2] - corners_px[0]))
    an = dp.analyze_points(view, Xa, ka, sa, cfg, seed, quad_diag_px=qdiag)
    fl.extend(an["flags"])
    diag.update(planes=an["planes"], stats=an["stats"], range_median_m=an["stats"].get("range_median_m"), facade_assessment=an.get("assessment"))
    if q.blocking(fl):
        _finish_diag(res, fl, an)
        return res
    fac, frm = an["facade"], an["frame"]
    n, d_wall = fac["n"], fac["d"]
    z_med = an["stats"]["range_median_m"]
    thr = an["stats"]["threshold_m"]
    sig = dp.sigma_at(z_med, cfg)
    diag["frame_plane"] = {"mode": frm["mode"], "offset_m": frm.get("offset_m"), "per_side": frm["per_side"], "group": frm.get("group"), "ledge_sides": frm.get("ledge", [])}
    # hoekdieptes in het capture-frame (onafhankelijk van de vlakfits); een hoek ligt op een rand: het venster bevat wand- en kozijnwaarden
    o_cam = view.pose[:3, 3]
    zax = view.pose[:3, :3][:, 2]
    vals = [dp.corner_values(view, c) for c in corners_px]
    offset, mode = frm.get("offset_m"), frm["mode"]
    if mode not in ("FLUSH", "RECESSED", "PROTRUDING"):
        # terugval: terugligging uit de clusters van hoekdieptes (zwakker bewijs; altijd adviserend gemeld)
        s_all = []
        for c, v in zip(corners_px, vals):
            if len(v):
                Xv = unproject_depth(view.pose, view.intrinsics, np.repeat(c[None, :], len(v), axis=0), v)
                s_all.extend((Xv @ n - d_wall).tolist())
        s_all = np.array(s_all)
        cl = dp._clusters(s_all[np.abs(s_all) <= cfg.frame_search_m], thr) if len(s_all) else []
        cl = [c for c in cl if c[1] >= max(8, 0.2 * (max([x[1] for x in cl]) if cl else 0))]
        diag["corner_offset_clusters_m"] = [[round(c[0], 4), c[1]] for c in cl]
        flush = max(0.015, cfg.flush_tol_k * sig)
        if len(cl) == 1 and abs(cl[0][0]) <= flush and cl[0][1] >= 20:
            offset, mode = 0.0, "FLUSH_FROM_CORNERS"
        elif len(cl) >= 2 and cl[0][1] >= 12:
            deep = min(cl, key=lambda x: x[0])
            if abs(deep[0]) > flush and deep[1] >= 12:
                # NIET gebruikt als maat: bij diepe dagkanten pakt dit cluster de dagkant i.p.v. het kozijn (gesimuleerd 3-9 % fout). Alleen indicatief.
                diag["indicative_corner_offset_m"] = {"offset_m": round(float(deep[0]), 4), "note": "ALLEEN indicatief; terugligging niet betrouwbaar bepaald"}
        if mode in ("FLUSH_FROM_CORNERS", "RECESSED_FROM_CORNERS", "PROTRUDING_FROM_CORNERS"):
            fl.append(q.flag("FRAME_OFFSET_FROM_CORNER_DEPTH", f"{offset * 100:.1f} cm ({mode})"))
        else:
            C0, t0, _ = dp.plane_geometry(view, corners_px, n, d_wall)
            if not np.any(np.isnan(t0)):
                w0, h0 = dims_from_corners(C0, UP)
                diag["indicative_if_flush_m"] = {"width": round(float(w0), 3), "height": round(float(h0), 3), "note": "ALLEEN indicatief; geen meting"}
            fl.append(q.flag("FRAME_PLANE_INCONSISTENT" if mode == "INCONSISTENT" else "FRAME_PLANE_UNDETERMINED", f"modus {mode}"))
            _finish_diag(res, fl, an)
            return res
    d_plane = d_wall + float(offset)
    diag["frame_plane"].update(final_mode=mode, final_offset_m=round(float(offset), 4), recess_cm=round(float(-offset) * 100, 1))
    C, t, cosinc = dp.plane_geometry(view, corners_px, n, d_plane)
    if np.any(np.isnan(t)):
        fl.append(q.flag("CORNERS_NOT_ON_PLANE"))
        _finish_diag(res, fl, an)
        return res
    if cosinc.min() < cfg.min_incidence_cos:
        fl.append(q.flag("OBLIQUE_ANGLE", f"min |cos|={cosinc.min():.2f}"))
        _finish_diag(res, fl, an)
        return res
    # --- hoekcontrole (onafhankelijk): ligt een deel van de dieptes rond elke hoek op het gekozen vlak? (alleen wand-/kozijnwaarden mengen is normaal op een rand)
    tol_c = cfg.corner_tol_k * sig + 0.02
    exp_z = (C - o_cam) @ zax
    dev, share, contra = [], [], 0
    for k in range(4):
        v = vals[k]
        if len(v) < 3:
            dev.append(None); share.append(None)
            continue
        dd = v - float(exp_z[k])
        near = np.abs(dd) <= tol_c
        dev.append(round(float(dd[np.argmin(np.abs(dd))]), 4))
        share.append(round(float(near.mean()), 3))
        if not near.any():
            contra += 1
    diag.update(corner_deviation_m=dev, corner_share_on_plane=share, corner_tolerance_m=round(tol_c, 4), corners_contradicting=contra,
                corners_checked=sum(v is not None for v in dev))
    if contra >= cfg.corners_contradict_block:
        fl.append(q.flag("CORNERS_OFF_PLANE", f"{contra} hoeken: geen enkele diepte binnen {tol_c * 100:.1f} cm van het gekozen vlak"))
        _finish_diag(res, fl, an)
        return res
    if contra:
        fl.append(q.flag("CORNER_DEPTH_MISMATCH", f"{contra} hoek(en)"))
    bad = rectangularity_flags(C, cfg)
    if bad:
        fl.append(q.flag("WRONG_CORNER_SELECTION", "; ".join(bad)))
        _finish_diag(res, fl, an)
        return res
    w, h = dims_from_corners(C, UP)
    if not (cfg.min_dim_m <= w <= cfg.max_dim_m and cfg.min_dim_m <= h <= cfg.max_dim_m):
        fl.append(q.flag("DIMENSION_OUT_OF_RANGE", f"{w:.3f} x {h:.3f} m"))
        _finish_diag(res, fl, an)
        return res
    # --- ligt het kader om de buitenrand van het kozijn? (dieptesprongen loodrecht op de kaderranden)
    qe, larger, inside = dp.quad_extent(view, corners_px, n, d_plane, z_med, cfg)
    diag["quad_extent"] = {"sides": qe, "sides_deeper_step_inside": larger, "sides_closer_step_outside": inside}
    if larger >= 3:
        fl.append(q.flag("QUAD_LARGER_THAN_OPENING", f"{larger} zijden"))
    if inside >= 3:
        fl.append(q.flag("QUAD_INSIDE_OPENING", f"{inside} zijden"))
    # --- uitlijning dieptekaart <-> beeld: alleen als diagnostiek bewaard (nog niet gevalideerd; leverde bij schuine opnamen vals alarm), geen vlag
    if mode not in ("FLUSH", "FLUSH_FROM_CORNERS"):
        ea = dp.edge_alignment(view, corners_px, cfg)
        if ea[3] is not None and ea[2] is not None:
            diag["edge_alignment"] = {"best_shift_depth_px": [ea[0], ea[1]], "score_best_m": round(ea[2], 4), "score_zero_m": round(ea[3], 4)}
    # --- glas (adviserend; de maat gebruikt het glas nooit)
    gm = kind_all == 3
    if gm.sum():
        vin = gm & valid_z
        frac_valid = float(vin.sum() / gm.sum())
        beyond_frac = 0.0
        if vin.sum():
            P = unproject_depth(view.pose, view.intrinsics, uv_all[vin], z_all[vin])
            beyond_frac = float((np.abs(P @ n - d_plane) > cfg.glass_beyond_plane_m).mean())
        diag["glass"] = {"valid_fraction": round(frac_valid, 3), "beyond_fraction": round(beyond_frac, 3)}
        if frac_valid < cfg.glass_min_valid_fraction or beyond_frac > cfg.glass_max_beyond_fraction:
            fl.append(q.flag("GLASS_DEPTH_UNRELIABLE", f"geldig {frac_valid:.2f}, buiten vlak {beyond_frac:.2f}"))
    # --- onafhankelijke consistentie tussen frames (zelfde analyse per frame, zelfde capture-stralen)
    per_frame = []
    agree = 0
    if len(frames) > 1:
        ref_wh = (w, h)
        for fi, f in enumerate(frames):
            m = fa == fi
            sub = analyze_subset(view, Xa[m], ka[m], sa[m], corners_px, cfg, seed + 101 * (fi + 1), qdiag)
            per_frame.append({"frame": f.frame_id, **sub})
        usable = [p for p in per_frame if p.get("ok")]
        diag["frames_usable"] = len(usable)
        for p in usable:
            p["normal_deg"] = round(_angle_deg(np.array(p["normal"]), n), 3)
            tol_w = cfg.frame_tol_rel * ref_wh[0] + cfg.frame_tol_abs_m
            tol_h = cfg.frame_tol_rel * ref_wh[1] + cfg.frame_tol_abs_m
            p["agrees"] = bool(abs(p["width_m"] - ref_wh[0]) <= tol_w and abs(p["height_m"] - ref_wh[1]) <= tol_h
                               and p["normal_deg"] <= cfg.frame_normal_deg)
        if any(not p["agrees"] for p in usable):
            fl.append(q.flag("FRAMES_INCONSISTENT", "; ".join(f"{p['frame']}: {p['width_m']:.3f}x{p['height_m']:.3f}" for p in usable)))
            diag["per_frame"] = per_frame
            _finish_diag(res, fl, an)
            return res
        # onafhankelijkheid: kaders met alleen rotatie (zelfde positie) leveren extra punten maar geen ander standpunt/parallax; alleen verschillende
        # standpunten (>= min_baseline_m) tellen als onafhankelijke metingen voor LIDAR_DEPTH_MULTI_FRAME en voor MEASURED.
        pos = {f.frame_id: f.pose[:3, 3] for f in frames}
        vps = []
        for p in per_frame:
            c = pos[p["frame"]]
            p["baseline_to_capture_m"] = round(float(np.linalg.norm(c - view.pose[:3, 3])), 4)
            p["rotation_to_capture_deg"] = round(float(np.degrees(np.arccos(np.clip((np.trace(frames[[g.frame_id for g in frames].index(p["frame"])].pose[:3, :3].T @ view.pose[:3, :3]) - 1) / 2, -1, 1)))), 3)
            if p.get("ok") and all(np.linalg.norm(c - q_) >= cfg.min_baseline_m for q_ in vps):
                vps.append(c)
        diag["independence"] = {"criteria": {"min_baseline_m": cfg.min_baseline_m, "min_rotation_deg": cfg.min_rotation_deg,
                                             "rule": "kader geselecteerd bij baseline OF rotatie; onafhankelijk standpunt telt alleen bij baseline"},
                                "frames_selected": len(frames), "frames_usable": len(usable), "distinct_viewpoints": len(vps),
                                "rotation_only_frames": max(len(usable) - len(vps), 0)}
        agree = len(vps)
    else:
        agree = 1
    diag["per_frame"] = per_frame
    independent = max(1, agree)
    res.independent_frames = independent
    if independent >= 2:
        res.scale_method = "LIDAR_DEPTH_MULTI_FRAME"
    # --- onzekerheid (Monte Carlo, vaste seed): hoekpixels, wandvlak (offset+kanteling) en kozijnoffset
    rng = np.random.default_rng(seed)
    n_eff = min(int(fac["count"]), cfg.plane_effective_samples_cap)
    sig_depth = max(fac["rms"], sig)
    sig_d = sig_depth / np.sqrt(n_eff)
    frame_sup = max([v["support"] for v in frm["per_side"].values()] + [1])
    sig_frame = (thr / np.sqrt(min(frame_sup, 50))) if mode not in ("FLUSH",) else 0.0
    sig_tilt = sig_depth / (max(fac["spread"], 0.05) * np.sqrt(n_eff))
    ws, hs = [], []
    ctr = fac["centroid"]
    for _ in range(cfg.mc_samples):
        cpx = corners_px + rng.normal(0, cfg.corner_pixel_sigma_px, corners_px.shape)
        dl = rng.normal(0, sig_tilt, 3)
        n2 = n + (dl - (dl @ n) * n)
        n2 = n2 / np.linalg.norm(n2)
        d2 = float(n2 @ ctr) + float(offset) + rng.normal(0, sig_d) + (rng.normal(0, sig_frame) if sig_frame else 0.0)
        C2, t2, _ = dp.plane_geometry(view, cpx, n2, d2)
        if np.any(np.isnan(t2)):
            continue
        a_, b_ = dims_from_corners(C2, UP)
        ws.append(a_)
        hs.append(b_)
    res.width_m, res.height_m = float(w), float(h)
    res.sigma_w, res.sigma_h = float(np.std(ws)), float(np.std(hs))
    res.sigma_area = float(np.std(np.array(ws) * np.array(hs)))
    res.aspect_ratio = float(w / h)
    res.corners_w, res.plane_n, res.plane_d, res.center_w = C, n, float(d_plane), C.mean(axis=0)
    res.scale_evidence = {"kind": "LIDAR_DEPTH_FRAME_PLANE_V2", "frame_plane_mode": mode, "recess_cm": round(float(-offset) * 100, 1),
                          "facade_support": round(float(fac["support"]), 3), "facade_rms_m": round(float(fac["rms"]), 4),
                          "facade_inlier_ratio": round(float(an["stats"]["facade_inlier_ratio"]), 3), "independent_frames": independent,
                          "depth_coverage": round(coverage, 3), "incidence_cos_min": round(float(cosinc.min()), 3)}
    diag.update(selected_plane={"role": "FACADE", "inlier_ratio": round(float(an["stats"]["facade_inlier_ratio"]), 3), "rms_m": round(float(fac["rms"]), 4),
                                "sides_covered": fac.get("sides_covered"), "normal": [round(float(x), 4) for x in n]},
                distance_to_frame_m=round(float(np.linalg.norm(C.mean(axis=0) - o_cam)), 3), independent_frames=independent,
                result={"width_m": round(float(w), 4), "height_m": round(float(h), 4)})
    _finish_diag(res, fl, an)
    return res


def analyze_subset(view, X, kind, side, corners_px, cfg, seed, qdiag=None):
    """Analyse van de punten van EEN frame (voor de consistentiecontrole): vlak + kozijnoffset + maat op dezelfde capture-stralen."""
    out = {"ok": False}
    if len(X) < cfg.min_plane_points:
        out["why"] = "te weinig punten"
        return out
    an = dp.analyze_points(view, X, kind, side, cfg, seed, quad_diag_px=qdiag)
    if an["facade"] is None or q.blocking(an["flags"]):
        out["why"] = ",".join(f["code"] for f in an["flags"])
        return out
    fac, frm = an["facade"], an["frame"]
    off = frm.get("offset_m")
    if frm["mode"] not in ("FLUSH", "RECESSED", "PROTRUDING") or off is None:
        out["why"] = "kozijnoffset " + frm["mode"]
        return out
    C, t, _ = dp.plane_geometry(view, corners_px, fac["n"], fac["d"] + off)
    if np.any(np.isnan(t)):
        out["why"] = "hoekstraal"
        return out
    w, h = dims_from_corners(C, UP)
    out.update(ok=True, width_m=float(w), height_m=float(h), offset_m=float(off), inlier_ratio=round(float(an["stats"]["facade_inlier_ratio"]), 3),
               plane_offset=float(fac["d"] + off), normal=[float(x) for x in fac["n"]], normal_deg=0.0)
    return out


def _finish_diag(res, flags, an=None):
    d = res.diag
    d["flags"] = [{"code": f["code"], "severity": f["severity"], "detail": f["detail"]} for f in flags]
    d["blocking"] = [f["code"] for f in q.blocking(flags)]
    d["hints_nl"] = list(dict.fromkeys(f["instruction_nl"] for f in flags if f["severity"] == q.BLOCKING or f["code"] in ("FRAME_OFFSET_FROM_CORNER_DEPTH", "CORNER_DEPTH_MISMATCH", "QUAD_LARGER_THAN_OPENING", "QUAD_INSIDE_OPENING", "GLASS_DEPTH_UNRELIABLE", "LIMITED_SIDE_COVERAGE")))
    d["ok"] = bool(res.width_m is not None and not q.blocking(flags))


def fuse_results(results, cfg: Config):
    """Fuseer geldige resultaten van meerdere standpunten (inverse-variantie). Inconsistent -> geen waarde (UNKNOWN), alle
    kandidaten blijven in diagnostics."""
    good = [r for r in results if r.ok]
    out = LevelResult(good[0].level if good else (results[0].level if results else "A"),
                      good[0].scale_method if good else "NONE",
                      view_ids=tuple(v for r in good for v in r.view_ids))
    out.flags = [f for r in results if not r.ok for f in r.flags]
    if not good:
        return out
    cand = [{"view_ids": list(r.view_ids), "width_m": r.width_m, "height_m": r.height_m, "sigma_w": r.sigma_w, "sigma_h": r.sigma_h}
            for r in good]
    out.diagnostics["candidates"] = cand
    for a in range(len(good)):
        for b in range(a + 1, len(good)):
            ra, rb = good[a], good[b]
            for key, sk in (("width_m", "sigma_w"), ("height_m", "sigma_h")):
                lim = cfg.consistency_k * np.hypot(max(getattr(ra, sk), 1e-4), max(getattr(rb, sk), 1e-4))
                dif = abs(getattr(ra, key) - getattr(rb, key))
                if dif > lim:
                    out.flags.append(q.flag("VIEWS_INCONSISTENT", f"{key}: |{getattr(ra, key):.3f}-{getattr(rb, key):.3f}|={dif:.3f} > {lim:.3f} m"))
    if q.blocking(out.flags):
        return out
    out.flags += [f for r in good for f in q.advisory(r.flags)]
    def wmean(key, sk):
        wt = np.array([1 / max(getattr(r, sk), 1e-4) ** 2 for r in good])
        val = np.array([getattr(r, key) for r in good])
        return float((wt * val).sum() / wt.sum()), float(1 / np.sqrt(wt.sum()))
    out.width_m, out.sigma_w = wmean("width_m", "sigma_w")
    out.height_m, out.sigma_h = wmean("height_m", "sigma_h")
    out.sigma_area = float(np.hypot(out.sigma_w * out.height_m, out.sigma_h * out.width_m))
    out.aspect_ratio = out.width_m / out.height_m
    best = max(good, key=lambda r: 1 / max(r.sigma_area, 1e-9))
    out.corners_w, out.plane_n, out.plane_d, out.center_w = best.corners_w, best.plane_n, best.plane_d, best.center_w
    out.scale_evidence = {"kind": "LIDAR_DEPTH_FACADE_PLANE_MULTI_VIEW", "views": len(good), "per_view": [r.scale_evidence for r in good]}
    out.diagnostics["n_consistent_views"] = len(good)
    return out


# ---------------------------------------------------------------- niveau B

def _triangulate(origins, dirs_list):
    A, b = np.zeros((3, 3)), np.zeros(3)
    for o, d in zip(origins, dirs_list):
        M = np.eye(3) - np.outer(d, d)
        A += M
        b += M @ o
    return np.linalg.solve(A, b)


def _tri_corners(views, cpx_list):
    pts = []
    for k in range(4):
        os_, ds = [], []
        for v, c in zip(views, cpx_list):
            o, D = rays_world(v.pose, v.intrinsics, c[k:k + 1])
            os_.append(o)
            ds.append(D[0])
        pts.append(_triangulate(os_, ds))
    return np.array(pts)


def measure_triangulated(views, corners_list, cfg: Config, seed=0, metric_scale_trusted=False):
    """Niveau B: >= 2 standpunten van dezelfde hoeken. Schaal is alleen metrisch als de tracking als metrisch is gedeclareerd; zelfs
    dan blijft ze `METRIC_SCALE_UNVERIFIED` tot een referentie ze bevestigt."""
    res = LevelResult("B", "AR_TRIANGULATION_VIO" if metric_scale_trusted else "NONE", view_ids=tuple(v.frame_id for v in views))
    fl = res.flags
    cl = [np.asarray(c, float) for c in corners_list]
    for v, c in zip(views, cl):
        if v.tracking_state != TRACKING_NORMAL:
            fl.append(q.flag("TRACKING_LOST", f"{v.frame_id}: {v.tracking_state}"))
        if not is_simple_convex_quad(c, image_area=v.intrinsics.width * v.intrinsics.height):
            fl.append(q.flag("CORNER_ORDER_INVALID", v.frame_id))
        elif not _corner_inside(v, c):
            fl.append(q.flag("CORNER_OUTSIDE_IMAGE", v.frame_id))
    if len({v.frame_id for v in views}) < 2:
        fl.append(q.flag("LOW_PARALLAX", "minder dan twee verschillende standpunten"))
    if q.blocking(fl):
        return res
    X = _tri_corners(views, cl)
    # parallax en cheirality per hoek
    min_ang = 180.0
    for k in range(4):
        dirs = [rays_world(v.pose, v.intrinsics, c[k:k + 1])[1][0] for v, c in zip(views, cl)]
        ang = max(np.degrees(np.arccos(np.clip(dirs[i] @ dirs[j], -1, 1))) for i in range(len(dirs)) for j in range(i + 1, len(dirs)))
        min_ang = min(min_ang, ang)
    res.diagnostics["min_triangulation_angle_deg"] = float(min_ang)
    if min_ang < cfg.min_triangulation_angle_deg:
        fl.append(q.flag("LOW_PARALLAX", f"{min_ang:.1f} graden"))
        return res
    max_err = 0.0
    for v, c in zip(views, cl):
        uv, z = project(v.pose, v.intrinsics, X)
        if np.any(z <= 0):
            fl.append(q.flag("BEHIND_CAMERA", v.frame_id))
            return res
        max_err = max(max_err, float(np.linalg.norm(uv - c, axis=1).max()))
    res.diagnostics["max_reprojection_px"] = max_err
    if max_err > cfg.max_reproj_px:
        fl.append(q.flag("INCONSISTENT_VIEWS", f"herprojectiefout {max_err:.1f} px"))
        return res
    ctr = X.mean(axis=0)
    _, _, vt = np.linalg.svd(X - ctr)
    n = vt[2]
    planarity = float(np.abs((X - ctr) @ n).max())
    res.diagnostics["corner_planarity_m"] = planarity
    scale_ok = metric_scale_trusted
    tol = cfg.max_corner_planarity_m if scale_ok else np.inf
    if planarity > tol:
        fl.append(q.flag("CORNERS_NOT_COPLANAR", f"{planarity:.3f} m"))
        return res
    Xp = X - np.outer((X - ctr) @ n, n)
    bad = rectangularity_flags(Xp, cfg)
    if bad:
        fl.append(q.flag("WRONG_CORNER_SELECTION", "; ".join(bad)))
        return res
    w, h = dims_from_corners(Xp, UP)
    res.aspect_ratio = float(w / h)
    res.corners_w, res.plane_n, res.plane_d, res.center_w = Xp, n, float(n @ ctr), Xp.mean(axis=0)
    if not scale_ok:
        fl.append(q.flag("NO_METRIC_SCALE", "tracking declareert geen metrische schaal; alleen verhouding w/h bekend"))
        return res
    if not (cfg.min_dim_m <= w <= cfg.max_dim_m and cfg.min_dim_m <= h <= cfg.max_dim_m):
        fl.append(q.flag("DIMENSION_OUT_OF_RANGE", f"{w:.3f} x {h:.3f} m"))
        return res
    rng = np.random.default_rng(seed)
    ws, hs = [], []
    for _ in range(cfg.mc_samples):
        cp = [c + rng.normal(0, cfg.corner_pixel_sigma_px, c.shape) for c in cl]
        X2 = _tri_corners(views, cp)
        c2 = X2.mean(axis=0)
        n2 = np.linalg.svd(X2 - c2)[2][2]
        X2p = X2 - np.outer((X2 - c2) @ n2, n2)
        a, b = dims_from_corners(X2p, UP)
        ws.append(a)
        hs.append(b)
    res.width_m, res.height_m = float(w), float(h)
    res.sigma_w, res.sigma_h = float(np.std(ws)), float(np.std(hs))
    res.sigma_area = float(np.std(np.array(ws) * np.array(hs)))
    fl.append(q.flag("METRIC_SCALE_UNVERIFIED"))
    res.scale_evidence = {"kind": "AR_VIO_METRIC_DECLARED", "verified_by_reference": False,
                          "note": "Schaal volgt uit visueel-inertiele tracking; niet onafhankelijk geverifieerd."}
    return res


# ---------------------------------------------------------------- niveau C

def _homography_unit_square(quad_px):
    """H: (u,v,1) in de eenheidsvierkant (TL=(0,0), TR=(1,0), BR=(1,1), BL=(0,1)) -> pixel (homogeen). DLT, 4 punten."""
    src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
    A = []
    for (x, y), (u, v) in zip(src, quad_px):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(A))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def reference_plane(intr, anchor_px):
    """Vlak (in cameracoordinaten, ONGESCHAALD) uit een rechthoek (anchor) en de cameralenzen. Geeft (m1, m2, m3, ortho_error):
    punt(u,v) = u*m1 + v*m2 + m3, met m1, m2 loodrecht als de hoeken echt een rechthoek vormen."""
    H = _homography_unit_square(np.asarray(anchor_px, float))
    M = np.linalg.inv(intr.K) @ H
    m1, m2, m3 = M[:, 0], M[:, 1], M[:, 2]
    if m3[2] < 0:
        m1, m2, m3 = -m1, -m2, -m3
    ortho = abs(m1 @ m2) / (np.linalg.norm(m1) * np.linalg.norm(m2))
    return m1, m2, m3, float(ortho)


def _cam_rays(intr, uv):
    uv = np.atleast_2d(uv)
    return np.stack([(uv[:, 0] - intr.cx) / intr.fx, (uv[:, 1] - intr.cy) / intr.fy, np.ones(len(uv))], axis=1)


def _ref_solve(intr, up_cam, anchor_px, p1, p2, dist_m, target_px):
    m1, m2, m3, ortho = reference_plane(intr, anchor_px)
    n = np.cross(m1, m2)
    n /= np.linalg.norm(n)
    ds = float(n @ m3)
    R = _cam_rays(intr, np.vstack([p1, p2, target_px]))
    den = R @ n
    if np.any(np.abs(den) < 1e-9):
        return None
    P = R * (ds / den)[:, None]
    if np.any(P[:, 2] <= 0):
        return None
    Ds = float(np.linalg.norm(P[0] - P[1]))
    if Ds < 1e-9:
        return None
    k = dist_m / Ds
    C = P[2:] * k
    w, h = dims_from_corners(C, up_cam)
    return dict(w=w, h=h, C=C, k=k, n=n, d=ds * k, ortho=ortho)


def up_in_camera(view):
    return view.pose[:3, :3].T @ UP if view.pose_valid else np.array([0.0, -1.0, 0.0])   # zonder tracking: beeld-omhoog als benadering


def measure_with_reference(view, target_px, ref, cfg: Config, seed=0, anchor_px=None, facade_plane=None):
    """Niveau C. `ref`: {reference_id, p1_px, p2_px, distance_m, distance_sigma_m|None, plane_id}. `anchor_px` is een rechthoek op het
    referentievlak (standaard: het doelkozijn zelf). Geeft altijd status DERIVED-achtig resultaat (afgeleid, nooit gemeten)."""
    res = LevelResult("C", "REFERENCE_DISTANCE", view_ids=(view.frame_id,))
    fl = res.flags
    target_px = np.asarray(target_px, float)
    anchor = target_px if anchor_px is None else np.asarray(anchor_px, float)
    p1, p2 = np.asarray(ref["p1_px"], float), np.asarray(ref["p2_px"], float)
    dist = ref.get("distance_m")
    if dist is None or not np.isfinite(dist) or dist <= 0 or np.linalg.norm(p1 - p2) < 2:
        fl.append(q.flag("REFERENCE_INVALID"))
        return res
    for name, c in (("doel", target_px), ("anker", anchor)):
        if not is_simple_convex_quad(c, image_area=view.intrinsics.width * view.intrinsics.height):
            fl.append(q.flag("CORNER_ORDER_INVALID", name))
    if q.blocking(fl):
        return res
    if ref.get("plane_id") is not None and ref.get("target_plane_id") is not None and ref["plane_id"] != ref["target_plane_id"]:
        fl.append(q.flag("REFERENCE_PLANE_MISMATCH", f"{ref['plane_id']} != {ref['target_plane_id']}"))
        return res
    # vlaklidmaatschap met diepte (als beschikbaar): referentiepunten moeten op het gevelvlak rond het anker liggen
    if view.depth is not None:
        fit, pf, _ = (facade_plane, [], {}) if facade_plane is not None else fit_facade_plane(view, anchor, cfg, seed)
        if fit is not None:
            for name, p in (("p1", p1), ("p2", p2)):
                zl = _local_depth(view, p)
                if zl is not None:
                    X = unproject_depth(view.pose, view.intrinsics, p, [zl])
                    dd = float(abs(signed_plane_distance(X, fit.n, fit.d)[0]))
                    if dd > cfg.ref_plane_tol_m:
                        fl.append(q.flag("REFERENCE_PLANE_MISMATCH", f"{name} ligt {dd:.2f} m van het gevelvlak"))
            if q.blocking(fl):
                return res
    sol = _ref_solve(view.intrinsics, up_in_camera(view), anchor, p1, p2, dist, target_px)
    if sol is None:
        fl.append(q.flag("REFERENCE_INVALID", "geometrie ontaard"))
        return res
    if sol["ortho"] > cfg.ref_orthogonality_tol:
        fl.append(q.flag("RECT_ASSUMPTION_VIOLATED", f"loodrechtheidsfout {sol['ortho']:.3f}"))
        return res
    bad = rectangularity_flags(sol["C"], cfg)
    if bad:
        fl.append(q.flag("WRONG_CORNER_SELECTION", "; ".join(bad)))
        return res
    w, h = sol["w"], sol["h"]
    if not (cfg.min_dim_m <= w <= cfg.max_dim_m and cfg.min_dim_m <= h <= cfg.max_dim_m):
        fl.append(q.flag("DIMENSION_OUT_OF_RANGE", f"{w:.3f} x {h:.3f} m"))
        return res
    if anchor_px is not None:
        fl.append(q.flag("COPLANARITY_ASSUMED"))
    if ref.get("kind", "MEASURED_WITH_TOOL") == "USER_ESTIMATE":        # een door de gebruiker geschatte referentie is geen meting
        fl.append(q.flag("REFERENCE_USER_ESTIMATE"))
    sig_ref = ref.get("distance_sigma_m")
    if sig_ref is None:
        fl.append(q.flag("REFERENCE_UNCERTAINTY_NOT_PROVIDED"))
    rng = np.random.default_rng(seed)
    ws, hs = [], []
    for _ in range(cfg.mc_samples):
        s = cfg.corner_pixel_sigma_px
        d2 = dist + (rng.normal(0, sig_ref) if sig_ref else 0.0)
        r = _ref_solve(view.intrinsics, up_in_camera(view), anchor + rng.normal(0, s, (4, 2)), p1 + rng.normal(0, s, 2),
                       p2 + rng.normal(0, s, 2), d2, target_px + rng.normal(0, s, (4, 2)))
        if r is not None:
            ws.append(r["w"])
            hs.append(r["h"])
    res.width_m, res.height_m = float(w), float(h)
    res.sigma_w, res.sigma_h = float(np.std(ws)), float(np.std(hs))
    res.sigma_area = float(np.std(np.array(ws) * np.array(hs)))
    res.aspect_ratio = float(w / h)
    # cameraframe -> wereld (alleen positie van de hoeken; schaal volgt uit de referentie)
    res.corners_w = sol["C"] @ view.pose[:3, :3].T + view.pose[:3, 3]
    res.plane_n = view.pose[:3, :3] @ sol["n"]
    res.plane_d = float(res.plane_n @ (view.pose[:3, :3] @ (sol["n"] * sol["d"]) + view.pose[:3, 3]))
    res.center_w = res.corners_w.mean(axis=0)
    res.scale_evidence = {"kind": "REFERENCE_DISTANCE", "reference_id": ref.get("reference_id"), "reference_distance_m": float(dist), "reference_kind": ref.get("kind", "MEASURED_WITH_TOOL"),
                          "reference_sigma_m": sig_ref, "plane_id": ref.get("plane_id"), "orthogonality_error": sol["ortho"],
                          "anchor_is_target": anchor_px is None}
    return res


def verify_vio_scale(b_result: LevelResult, view, ref, cfg: Config):
    """Vergelijk de AR-schaal met een ingevoerde referentie: reconstrueer de referentiestraal-afstand op het getrianguleerde vlak."""
    p = np.vstack([ref["p1_px"], ref["p2_px"]])
    o, D = rays_world(view.pose, view.intrinsics, p)
    P, t, _ = intersect_rays_plane(o, D, b_result.plane_n, b_result.plane_d)
    if np.any(np.isnan(t)):
        return None
    rec = float(np.linalg.norm(P[0] - P[1]))
    return rec / ref["distance_m"]
