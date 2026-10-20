"""Vlakaanpassing (RANSAC + SVD-verfijning), deterministisch via vaste seed."""
from dataclasses import dataclass

import numpy as np


@dataclass
class PlaneFit:
    n: np.ndarray
    d: float
    inlier_ratio: float
    rms_m: float
    n_points: int
    n_inliers: int
    spread_m: float          # RMS-spreiding van de inliers in het vlak (voor kantelonzekerheid)
    centroid: np.ndarray = None


def _svd_plane(P):
    c = P.mean(axis=0)
    _, _, vt = np.linalg.svd(P - c, full_matrices=False)
    n = vt[2]
    return n, float(n @ c)


def fit_plane_ransac(P, threshold, iterations, seed=0):
    P = np.asarray(P, float)
    if len(P) < 3:
        return None
    rng = np.random.default_rng(seed)
    best = None
    best_cnt = -1
    for _ in range(iterations):
        idx = rng.choice(len(P), 3, replace=False)
        a, b, c = P[idx]
        n = np.cross(b - a, c - a)
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue
        n /= nn
        dist = np.abs((P - a) @ n)
        cnt = int((dist < threshold).sum())
        if cnt > best_cnt:
            best_cnt, best = cnt, (n, float(n @ a))
    if best is None:
        return None
    n, d = best
    inl = np.abs(P @ n - d) < threshold
    if inl.sum() >= 3:
        n, d = _svd_plane(P[inl])
        inl = np.abs(P @ n - d) < threshold
    Pin = P[inl]
    res = Pin @ n - d
    ctr = Pin.mean(axis=0)
    spread = float(np.sqrt(np.mean(np.sum((Pin - ctr) ** 2, axis=1) - ((Pin - ctr) @ n) ** 2)))
    return PlaneFit(n=n, d=d, inlier_ratio=float(inl.mean()), rms_m=float(np.sqrt(np.mean(res ** 2))),
                    n_points=len(P), n_inliers=int(inl.sum()), spread_m=spread, centroid=ctr)


def ransac_plane_mask(P, threshold, iterations, seed=0, max_points=2500):
    """RANSAC met deterministische subsample; verfijnt met SVD op alle inliers. Geeft (n, d, mask over ALLE punten, rms, centroid) of None."""
    P = np.asarray(P, float)
    if len(P) < 3:
        return None
    rng = np.random.default_rng(seed)
    sub = P if len(P) <= max_points else P[rng.choice(len(P), max_points, replace=False)]
    best, best_cnt = None, -1
    for _ in range(iterations):
        idx = rng.choice(len(sub), 3, replace=False)
        a, b, c = sub[idx]
        n = np.cross(b - a, c - a)
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue
        n /= nn
        cnt = int((np.abs((sub - a) @ n) < threshold).sum())
        if cnt > best_cnt:
            best_cnt, best = cnt, (n, float(n @ a))
    if best is None:
        return None
    n, d = best
    mask = np.abs(P @ n - d) < threshold
    for _ in range(2):                                  # verfijn en herbepaal inliers
        if mask.sum() < 3:
            break
        n, d = _svd_plane(P[mask])
        mask = np.abs(P @ n - d) < threshold
    Pin = P[mask]
    res = Pin @ n - d
    return n, d, mask, float(np.sqrt(np.mean(res ** 2))), Pin.mean(axis=0)
