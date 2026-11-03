"""Synthetische gevelscènes voor de LiDAR-meetalgoritmen (reproduceerbaar; alleen simulatie)."""
import numpy as np

from photo_walk_core.simulate import SimFacade, SimFrame, annotate, make_view

OUTER = (1.2, 1.5)
GLASS = (1.06, 1.36)          # glasruit: 7 cm naar binnen (profielbreedte van de simulator)


def build(recess=0.0, relief=0.0, noise=0.005, sill=False, pos=(1.6, 1.6, 3.0), yaw=0.0, quad="outer", seed=1, glass_mode="valid",
          protrusions=(), rough=(), hole_p=0.03, shift_px=(0, 0), tracking="NORMAL", extra_frames=0, spacing=0.06, with_depth=True):
    fr = SimFrame("K1", 1.0, 0.9, OUTER[0], OUTER[1], recess_m=recess)
    prot = list(protrusions) + ([(0.97, 2.23, 0.85, 0.9, 0.05)] if sill else [])
    f = SimFacade(frames=[fr], protrusions=prot, relief_m=relief, glass_mode=glass_mode, rough=list(rough))
    kw = dict(noise=noise, hole_p=hole_p, shift_px=shift_px)
    cap = make_view(f, "CAP", list(pos), yaw, seed=seed, tracking=tracking, with_depth=with_depth, **kw)
    extras = []
    for k in range(extra_frames):
        p = [pos[0] + spacing * ((k // 2 + 1) * (1 if k % 2 == 0 else -1)), pos[1], pos[2]]
        extras.append(make_view(f, f"EX{k}", p, yaw, seed=seed * 7 + k + 1, **kw))
    if quad == "outer":
        ob = annotate(fr, cap, seed=seed + 2)
        truth = OUTER
    elif quad == "glass":
        g = SimFrame("G", 1.07, 0.97, GLASS[0], GLASS[1], recess_m=recess + 0.06)   # glasrand ligt op het glasvlak
        ob = annotate(g, cap, seed=seed + 2)
        truth = GLASS
    else:
        raise ValueError(quad)
    return dict(facade=f, frame=fr, cap=cap, extras=extras, corners=None if ob is None else ob.corners_px, truth=truth)
