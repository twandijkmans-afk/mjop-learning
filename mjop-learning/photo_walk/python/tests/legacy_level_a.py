"""LEGACY: niveau-A-algoritme van Photo Walk v1 (enkel RANSAC-vlak door een ring, hoeken op het WANDvlak). Alleen bewaard als baseline voor regressietests
(de nieuwe methode mag niet vaker foutieve maten accepteren). Niet gebruiken in productiecode."""
import numpy as np

from photo_walk_core import quality as q
from photo_walk_core.config import Config
from photo_walk_core.geometry import UP, in_convex_polygon, intersect_rays_plane, is_simple_convex_quad, rays_world, scale_polygon, signed_plane_distance, unproject_depth
from photo_walk_core.levels import LevelResult, _corner_inside, _depth_grid, _local_depth, _valid, dims_from_corners, rectangularity_flags
from photo_walk_core.model import TRACKING_NORMAL
from photo_walk_core.plane import fit_plane_ransac


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




def legacy_measure_depth_view(view, corners_px, cfg: Config, seed=0, obstruction=False):
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


