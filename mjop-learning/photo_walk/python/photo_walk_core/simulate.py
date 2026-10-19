"""Synthetische gevel, camera's, dieptebeelden en hoekannotaties. UITSLUITEND SIMULATIE.

Een geslaagde meting op deze data bewijst alleen dat de geometrie klopt voor het gesimuleerde model; het bewijst GEEN nauwkeurigheid op een echte
gevel, echte LiDAR-ruis, echte AR-drift of echte lenzen. De simulator rendert geen RGB; alleen dieptekaarten (float, meter, depth_z).

Wereld: gevelvlak Z = 0, normaal +Z (naar de lopende inspecteur), X langs de gevel, Y omhoog. Kozijnen zitten in dit vlak (buitenmaat);
het glas ligt `glass_recess_m` dieper (Z < 0).
"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .geometry import Intrinsics, look_pose, project
from .model import Observation, View

RGB_W, RGB_H = 1920, 1440
DEPTH_W, DEPTH_H = 256, 192


def phone_intrinsics(fx=1500.0, w=RGB_W, h=RGB_H):
    return Intrinsics(fx, fx, w / 2, h / 2, w, h)


@dataclass
class SimFrame:
    frame_id: str
    x0: float            # linkeronderhoek (m), langs de gevel
    y0: float
    width: float
    height: float
    glass_recess_m: float = 0.06
    frame_type: str = "FRAME"
    movable_parts: int = 2
    fixed_parts: int = 1

    @property
    def corners_w(self):          # TL, TR, BR, BL op het gevelvlak
        x1, y1 = self.x0 + self.width, self.y0 + self.height
        return np.array([[self.x0, y1, 0], [x1, y1, 0], [x1, self.y0, 0], [self.x0, self.y0, 0]], float)


@dataclass
class SimFacade:
    frames: List[SimFrame]
    glass_mode: str = "valid"                 # valid | holes | reflect
    protrusions: list = field(default_factory=list)   # [(x0,x1,y0,y1,z)] platen vóór de gevel (bv. balkon)
    facade_id: str = "FACADE-A"


def _render_depth(facade: SimFacade, pose, intr, rng, noise=0.005, hole_p=0.03, max_range=5.0, size=(DEPTH_H, DEPTH_W), glass_mode=None):
    Hd, Wd = size
    sx, sy = intr.width / Wd, intr.height / Hd
    jj, ii = np.meshgrid(np.arange(Wd), np.arange(Hd))
    u, v = (jj + 0.5) * sx, (ii + 0.5) * sy
    dcam = np.stack([(u - intr.cx) / intr.fx, (v - intr.cy) / intr.fy, np.ones_like(u)], -1)
    Rm, o = pose[:3, :3], pose[:3, 3]
    dw = dcam @ Rm.T
    depth = np.full((Hd, Wd), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (0 - o[2]) / dw[..., 2]
    P = o + dw * t[..., None]
    zc = t * (dcam[..., 2] / 1.0) * 1.0     # dcam z=1 -> t is afstand langs de niet-genormaliseerde straal = depth_z
    ok = (t > 0)
    depth[ok] = zc[ok]
    gm = glass_mode or facade.glass_mode
    for f in facade.frames:
        inside = ok & (P[..., 0] > f.x0 + 0.07) & (P[..., 0] < f.x0 + f.width - 0.07) & (P[..., 1] > f.y0 + 0.07) & (P[..., 1] < f.y0 + f.height - 0.07)
        if gm == "valid":
            with np.errstate(divide="ignore", invalid="ignore"):
                tg = (-f.glass_recess_m - o[2]) / dw[..., 2]
            depth[inside] = tg[inside]
        elif gm == "holes":
            depth[inside] = np.nan
        elif gm == "reflect":                                # spiegelbeeld: veel te diep, ruis
            depth[inside] = zc[inside] * 2.4 + rng.normal(0, 0.2, inside.sum())
    for (x0, x1, y0, y1, z) in facade.protrusions:
        with np.errstate(divide="ignore", invalid="ignore"):
            tp = (z - o[2]) / dw[..., 2]
        Pp = o + dw * tp[..., None]
        hit = (tp > 0) & (Pp[..., 0] > x0) & (Pp[..., 0] < x1) & (Pp[..., 1] > y0) & (Pp[..., 1] < y1)
        depth[hit] = tp[hit]
    depth = depth + rng.normal(0, noise, depth.shape) + rng.normal(0, 0.002, depth.shape) * np.nan_to_num(depth)
    depth[rng.random(depth.shape) < hole_p] = np.nan
    depth[(depth > max_range) | (depth <= 0)] = np.nan
    return depth.astype(np.float32)


def make_view(facade, frame_id, position, yaw_deg=0.0, seed=0, intr=None, with_depth=True, tracking="NORMAL", **kw):
    rng = np.random.default_rng(seed)
    intr = intr or phone_intrinsics()
    pose = look_pose(position, yaw_deg)
    depth = _render_depth(facade, pose, intr, rng, **kw) if with_depth else None
    return View(frame_id=frame_id, intrinsics=intr, pose=pose, tracking_state=tracking, depth=depth,
                timestamp="2026-01-01T00:00:00Z", image_ref=f"local://synthetic/{frame_id}.jpg",
                depth_ref=f"local://synthetic/{frame_id}.depth.f32" if with_depth else None)


def annotate(facade_frame: SimFrame, view: View, px_sigma=1.0, seed=0, source="MANUAL"):
    """Simuleert een (handmatige) hoekselectie: ware hoekprojectie + pixelruis."""
    rng = np.random.default_rng(seed)
    uv, z = project(view.pose, view.intrinsics, facade_frame.corners_w)
    if np.any(z <= 0):
        return None
    uv = uv + rng.normal(0, px_sigma, uv.shape)
    w, h = view.intrinsics.width, view.intrinsics.height
    if np.any(uv < 0) or np.any(uv[:, 0] > w) or np.any(uv[:, 1] > h):
        return None
    return Observation(f"OBS-{view.frame_id}-{facade_frame.frame_id}", view.frame_id, uv, corner_source=source)


def standard_facade(glass_mode="valid"):
    """Vier kozijnen met verschillende maten (m)."""
    return SimFacade(glass_mode=glass_mode, frames=[
        SimFrame("K1", 1.0, 0.9, 1.20, 1.50),
        SimFrame("K2", 3.2, 0.9, 1.20, 1.50),
        SimFrame("K3", 5.4, 0.9, 2.10, 1.50, fixed_parts=2, movable_parts=3),
        SimFrame("K4", 8.2, 0.9, 0.90, 1.20, movable_parts=1),
    ])


def walk(facade, distance=4.0, step=1.5, x_start=0.0, x_end=10.0, yaw_deg=0.0, seed=0, camera_height=1.6, **kw):
    views, k = [], 0
    for x in np.arange(x_start, x_end + 1e-9, step):
        views.append(make_view(facade, f"F{k:03d}", [x, camera_height, distance], yaw_deg, seed=seed + k, **kw))
        k += 1
    return views
