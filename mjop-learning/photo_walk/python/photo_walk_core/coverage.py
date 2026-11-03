"""Welke delen van de gevel zijn gezien? Raster op het gevelvlak (vlakcoordinaten, meter), per keyframe een voetafdruk."""
import numpy as np

from .config import Config
from .geometry import in_convex_polygon, intersect_rays_plane, plane_basis, rays_world


def footprint(view, n, d):
    """Voetafdruk van het beeld op het vlak (4 hoeken in 3D) of None als een hoekstraal het vlak niet raakt."""
    w, h = view.intrinsics.width, view.intrinsics.height
    o, D = rays_world(view.pose, view.intrinsics, [[0, 0], [w, 0], [w, h], [0, h]])
    P, t, c = intersect_rays_plane(o, D, n, d)
    if np.any(np.isnan(t)):
        return None
    return P


def facade_coverage(views, plane_n, plane_d, extent_uv, cfg: Config):
    """extent_uv: (u0,u1,v0,v1) in vlakcoordinaten (m), of None -> bounding box van de voetafdrukken (dan `extent_assumed`)."""
    n = np.asarray(plane_n, float)
    eu, ev = plane_basis(n)
    foots = {}
    for v in views:
        P = footprint(v, n, plane_d)
        if P is not None:
            foots[v.frame_id] = np.stack([P @ eu, P @ ev], axis=1)
    assumed = extent_uv is None
    if assumed:
        if not foots:
            return {"extent_assumed": True, "coverage_fraction": 0.0, "cells_total": 0, "cells_seen": 0, "views": [], "overlap": [], "guidance_nl": ["Geen enkel beeld snijdt het gevelvlak."]}
        allp = np.vstack(list(foots.values()))
        extent_uv = (allp[:, 0].min(), allp[:, 0].max(), allp[:, 1].min(), allp[:, 1].max())
    u0, u1, v0, v1 = extent_uv
    cs = cfg.coverage_cell_m
    us = np.arange(u0 + cs / 2, u1, cs)
    vs = np.arange(v0 + cs / 2, v1, cs)
    UU, VV = np.meshgrid(us, vs)
    cells = np.stack([UU.ravel(), VV.ravel()], axis=1)
    masks, good_masks = {}, {}
    for v in views:
        if v.frame_id not in foots:
            continue
        inside = in_convex_polygon(cells, foots[v.frame_id])
        # incidentie per celmidden
        X = (cells[:, :1] * eu + cells[:, 1:] * ev) + n * plane_d
        dirs = X - v.pose[:3, 3]
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        cosinc = np.abs(dirs @ n)
        masks[v.frame_id] = inside
        good_masks[v.frame_id] = inside & (cosinc >= cfg.coverage_min_incidence_cos)
    seen_any = np.zeros(len(cells), bool)
    seen_good = np.zeros(len(cells), bool)
    for fid in masks:
        seen_any |= masks[fid]
        seen_good |= good_masks[fid]
    overlap = []
    ids = [v.frame_id for v in views if v.frame_id in masks]
    for a, b in zip(ids, ids[1:]):
        inter = (masks[a] & masks[b]).sum()
        small = max(min(masks[a].sum(), masks[b].sum()), 1)
        overlap.append({"frame_a": a, "frame_b": b, "overlap_fraction": float(inter / small), "enough": bool(inter / small >= cfg.min_overlap_fraction)})
    guidance = []
    unseen = ~seen_any
    oblique_only = seen_any & ~seen_good
    if unseen.any():
        c = cells[unseen]
        guidance.append(f"{int(unseen.sum())} gevelcellen nog niet gezien (vlakcoordinaten u {c[:,0].min():.1f}..{c[:,0].max():.1f} m, v {c[:,1].min():.1f}..{c[:,1].max():.1f} m): loop daarheen en maak opnamen.")
    if oblique_only.any():
        guidance.append(f"{int(oblique_only.sum())} cellen alleen onder een zeer schuine hoek gezien: maak extra opnamen meer frontaal.")
    for o in overlap:
        if not o["enough"]:
            guidance.append(f"Te weinig overlap tussen {o['frame_a']} en {o['frame_b']} ({o['overlap_fraction']:.2f}): neem kleinere stappen.")
    total = len(cells)
    return {"extent_assumed": assumed, "extent_uv_m": [float(x) for x in extent_uv], "cell_m": cs, "cells_total": int(total),
            "cells_seen": int(seen_any.sum()), "cells_seen_frontal": int(seen_good.sum()),
            "coverage_fraction": float(seen_any.sum() / total) if total else 0.0, "overlap": overlap,
            "views": [{"frame_id": k, "cells": int(m.sum())} for k, m in masks.items()], "guidance_nl": guidance}
