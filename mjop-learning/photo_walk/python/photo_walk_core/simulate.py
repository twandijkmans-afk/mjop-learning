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
    glass_recess_m: float = 0.06       # glas ligt zoveel ACHTER het kozijnvlak
    recess_m: float = 0.0              # kozijnvlak ligt zoveel achter het wandvlak (terugliggend kozijn; 0 = gelijk met de wand)
    frame_type: str = "FRAME"
    movable_parts: int = 2
    fixed_parts: int = 1

    @property
    def corners_w(self):          # TL, TR, BR, BL op het gevelvlak
        x1, y1 = self.x0 + self.width, self.y0 + self.height
        z = -self.recess_m                       # de buitenrand van het kozijn ligt op het kozijnvlak (bij terugliggend kozijn achter de wand)
        return np.array([[self.x0, y1, z], [x1, y1, z], [x1, self.y0, z], [self.x0, self.y0, z]], float)


@dataclass
class SimFacade:
    frames: List[SimFrame]
    glass_mode: str = "valid"                 # valid | holes | reflect
    protrusions: list = field(default_factory=list)   # [(x0,x1,y0,y1,z)] platen vóór de gevel (bv. balkon, vensterbank, verspringende wand)
    relief_m: float = 0.0                             # baksteenreliëf: voegen liggen zoveel dieper (0,012 = 12 mm)
    rough: list = field(default_factory=list)         # [(x0,x1,y0,y1,sigma_m)] ruwe/onregelmatige zones (begroeiing)
    facade_id: str = "FACADE-A"


def _render_depth(facade: SimFacade, pose, intr, rng, noise=0.005, hole_p=0.03, max_range=5.0, size=(DEPTH_H, DEPTH_W), glass_mode=None, shift_px=(0, 0)):
    Hd, Wd = size
    sx, sy = intr.width / Wd, intr.height / Hd
    jj, ii = np.meshgrid(np.arange(Wd), np.arange(Hd))
    u, v = (jj + 0.5) * sx, (ii + 0.5) * sy
    dcam = np.stack([(u - intr.cx) / intr.fx, (v - intr.cy) / intr.fy, np.ones_like(u)], -1)
    Rm, o = pose[:3, :3], pose[:3, 3]
    dw = dcam @ Rm.T                                   # niet-genormaliseerd: z_cam = 1 => t is depth_z
    depth = np.full((Hd, Wd), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        t0 = (0 - o[2]) / dw[..., 2]
    P0 = o + dw * t0[..., None]
    ok = t0 > 0
    depth[ok] = t0[ok]
    if facade.relief_m > 0:                            # baksteenreliëf: voegen (horizontaal elke 7,5 cm, verticaal elke 22,5 cm, versprongen)
        course = np.floor(P0[..., 1] / 0.075)
        jh = np.mod(P0[..., 1], 0.075) < 0.010
        jv = np.mod(P0[..., 0] + (course % 2) * 0.1125, 0.225) < 0.010
        rel = (jh | jv) * facade.relief_m
        depth[ok] = (t0 + rel / np.maximum(np.abs(dw[..., 2]), 1e-6))[ok]
    gm = glass_mode or facade.glass_mode
    for f in facade.frames:
        x0, x1, y0, y1 = f.x0, f.x0 + f.width, f.y0, f.y0 + f.height
        inside = ok & (P0[..., 0] > x0) & (P0[..., 0] < x1) & (P0[..., 1] > y0) & (P0[..., 1] < y1)
        r = f.recess_m
        with np.errstate(divide="ignore", invalid="ignore"):
            if r > 0:
                tf = (-r - o[2]) / dw[..., 2]           # kozijnvlak
                cand = [np.where(inside, tf, np.inf)]
                for axis, val in ((0, x0), (0, x1), (1, y0), (1, y1)):     # dagkanten (leggers) van de opening
                    ts = (val - o[axis]) / dw[..., axis]
                    Ps = o + dw * ts[..., None]
                    okz = (ts > t0) & (Ps[..., 2] <= 1e-9) & (Ps[..., 2] >= -r - 1e-9)
                    oth = 1 - axis
                    lo, hi = (y0, y1) if axis == 0 else (x0, x1)
                    okr = (Ps[..., oth] >= lo) & (Ps[..., oth] <= hi)
                    cand.append(np.where(inside & okz & okr, ts, np.inf))
                tt = np.min(np.stack(cand), axis=0)
                hit = inside & np.isfinite(tt)
                depth[hit] = tt[hit]
                Pf = o + dw * tf[..., None]
                at_front = hit & np.isclose(tt, tf)
            else:
                tf = t0
                Pf = P0
                at_front = inside
            inner = at_front & (Pf[..., 0] > x0 + 0.07) & (Pf[..., 0] < x1 - 0.07) & (Pf[..., 1] > y0 + 0.07) & (Pf[..., 1] < y1 - 0.07)
            tg = (-(r + f.glass_recess_m) - o[2]) / dw[..., 2]
        if gm == "valid":
            depth[inner] = tg[inner]
        elif gm == "holes":
            depth[inner] = np.nan
        elif gm == "reflect":                             # spiegelbeeld: veel te diep, ruis
            depth[inner] = tf[inner] * 2.4 + rng.normal(0, 0.2, inner.sum())
    for (px0, px1, py0, py1, z) in facade.protrusions:
        with np.errstate(divide="ignore", invalid="ignore"):
            tp = (z - o[2]) / dw[..., 2]
        Pp = o + dw * tp[..., None]
        hit = (tp > 0) & (Pp[..., 0] > px0) & (Pp[..., 0] < px1) & (Pp[..., 1] > py0) & (Pp[..., 1] < py1)
        depth[hit] = tp[hit]
    for (rx0, rx1, ry0, ry1, sg) in facade.rough:
        zone = ok & (P0[..., 0] > rx0) & (P0[..., 0] < rx1) & (P0[..., 1] > ry0) & (P0[..., 1] < ry1)
        depth[zone] = depth[zone] + rng.normal(0, sg, zone.sum())
    depth = depth + rng.normal(0, noise, depth.shape) + rng.normal(0, 0.002, depth.shape) * np.nan_to_num(depth)
    depth[rng.random(depth.shape) < hole_p] = np.nan
    depth[(depth > max_range) | (depth <= 0)] = np.nan
    if shift_px != (0, 0):                              # verkeerd uitgelijnde dieptekaart (in dieptepixels)
        depth = np.roll(depth, shift=(int(shift_px[1]), int(shift_px[0])), axis=(0, 1))
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


def sensor_ring(facade, position, n=4, spacing=0.06, yaw_deg=0.0, seed=0, **kw):
    """Capture-view + (n-1) extra views met een klein zijwaarts verschil (zoals tijdens het richten): [capture, extra, ...]."""
    out = []
    for k in range(n):
        p = [position[0] + (k - (n - 1) / 2.0) * spacing * (1 if k else 0) + (0 if k else 0), position[1], position[2]]
        p[0] = position[0] + (0.0 if k == 0 else spacing * (k if k % 2 else -k))
        out.append(make_view(facade, f"R{k}", p, yaw_deg, seed=seed * 31 + k, **kw))
    return out
