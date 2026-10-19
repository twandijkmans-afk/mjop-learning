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


# ---------------------------------------------------------------- niveau A

def measure_depth_view(view, corners_px, cfg: Config, seed=0, obstruction=False):
    """Niveau A voor een standpunt. De hoeken worden NIET via hun eigen dieptepixel gemeten: de hoekstralen worden gesneden
    met het gevelvlak dat uit de omringende dieptepunten is aangepast (RANSAC)."""
    res = LevelResult("A", "LIDAR_DEPTH_PLANE", view_ids=(view.frame_id,))
    fl = res.flags
    corners_px = np.asarray(corners_px, float)
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
        return res
    fit, pf, diag = fit_facade_plane(view, corners_px, cfg, seed)
    res.diagnostics.update(diag)
    fl.extend(pf)
    if q.blocking(fl):
        return res
    o, D = rays_world(view.pose, view.intrinsics, corners_px)
    C, t, cosinc = intersect_rays_plane(o, D, fit.n, fit.d)
    if np.any(np.isnan(t)):
        fl.append(q.flag("CORNERS_NOT_ON_PLANE"))
        return res
    if cosinc.min() < cfg.min_incidence_cos:
        fl.append(q.flag("OBLIQUE_ANGLE", f"min |cos|={cosinc.min():.2f}"))
        return res
    bad = rectangularity_flags(C, cfg)
    if bad:
        fl.append(q.flag("WRONG_CORNER_SELECTION", "; ".join(bad)))
        return res
    w, h = dims_from_corners(C, UP)
    if not (cfg.min_dim_m <= w <= cfg.max_dim_m and cfg.min_dim_m <= h <= cfg.max_dim_m):
        fl.append(q.flag("DIMENSION_OUT_OF_RANGE", f"{w:.3f} x {h:.3f} m"))
        return res
    # hoekdiepte-controle (adviserend)
    zc_plane = (C - o) @ view.pose[:3, :3][:, 2]
    mism, gross = [], []
    for k in range(4):
        zl = _local_depth(view, corners_px[k])
        if zl is not None and abs(zl - zc_plane[k]) > cfg.corner_depth_tol_m:
            mism.append(k)
            if abs(zl - zc_plane[k]) > cfg.corner_depth_block_m:
                gross.append(k)
    res.diagnostics["corner_depth_mismatch"] = mism
    if len(gross) >= 3:
        fl.append(q.flag("MIXED_FACADE_DEPTH", f"hoekdiepte wijkt >{cfg.corner_depth_block_m} m af van het aangepaste vlak (hoeken {gross}): vlak ligt waarschijnlijk niet op het kozijn"))
        return res
    if mism:
        fl.append(q.flag("CORNER_DEPTH_MISMATCH", f"hoeken {mism}"))
    # glas (adviserend): interieurdiepte niet gebruikt voor de maat, wel beoordeeld
    uv, z = _depth_grid(view)
    inner = in_convex_polygon(uv, scale_polygon(corners_px, cfg.glass_inner_scale))
    n_in = int(inner.sum())
    if n_in:
        vin = inner & _valid(z, cfg)
        frac_valid = vin.sum() / n_in
        beyond_frac = 0.0
        if vin.sum():
            P = unproject_depth(view.pose, view.intrinsics, uv[vin], z[vin])
            beyond_frac = float((np.abs(signed_plane_distance(P, fit.n, fit.d)) > cfg.glass_beyond_plane_m).mean())
        res.diagnostics.update(glass_valid_fraction=float(frac_valid), glass_beyond_fraction=beyond_frac)
        if frac_valid < cfg.glass_min_valid_fraction or beyond_frac > cfg.glass_max_beyond_fraction:
            fl.append(q.flag("GLASS_DEPTH_UNRELIABLE", f"geldig {frac_valid:.2f}, buiten vlak {beyond_frac:.2f}"))
    # onzekerheid (Monte Carlo, vaste seed)
    rng = np.random.default_rng(seed)
    n_eff = min(fit.n_inliers, cfg.plane_effective_samples_cap)
    sig_depth = max(fit.rms_m, cfg.depth_noise_floor_m)
    sig_d = sig_depth / np.sqrt(n_eff)
    sig_tilt = sig_depth / (max(fit.spread_m, 0.05) * np.sqrt(n_eff))
    ws, hs = [], []
    for _ in range(cfg.mc_samples):
        cpx = corners_px + rng.normal(0, cfg.corner_pixel_sigma_px, corners_px.shape)
        dl = rng.normal(0, sig_tilt, 3)
        n2 = _tilt(fit.n, dl - (dl @ fit.n) * fit.n)
        d2 = float(n2 @ fit.centroid) + rng.normal(0, sig_d)
        o2, D2 = rays_world(view.pose, view.intrinsics, cpx)
        C2, t2, _ = intersect_rays_plane(o2, D2, n2, d2)
        if np.any(np.isnan(t2)):
            continue
        a, b = dims_from_corners(C2, UP)
        ws.append(a)
        hs.append(b)
    res.width_m, res.height_m = float(w), float(h)
    res.sigma_w, res.sigma_h = float(np.std(ws)), float(np.std(hs))
    res.sigma_area = float(np.std(np.array(ws) * np.array(hs)))
    res.aspect_ratio = float(w / h)
    res.corners_w, res.plane_n, res.plane_d, res.center_w = C, fit.n, fit.d, C.mean(axis=0)
    res.scale_evidence = {"kind": "LIDAR_DEPTH_FACADE_PLANE", "plane_inlier_ratio": fit.inlier_ratio, "plane_rms_m": fit.rms_m,
                          "plane_points": fit.n_points, "depth_coverage": diag["depth_coverage"],
                          "incidence_cos_min": float(cosinc.min())}
    return res


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
    res.scale_evidence = {"kind": "REFERENCE_DISTANCE", "reference_id": ref.get("reference_id"), "reference_distance_m": float(dist),
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
