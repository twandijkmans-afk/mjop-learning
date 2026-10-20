"""Pariteitsfixtures Python <-> Swift. Genereert deterministische rekengevallen met de verwachte uitkomsten van de Python-kern.
De Swift-tests (ios/Tests) lezen ios/Tests/PhotoWalkCoreTests/Fixtures/parity_cases.json en moeten dezelfde uitkomsten geven.
Ruisvrije diepte: de vergelijking test de geometrie, niet de ruis (PRNG's verschillen)."""
import json
import sys
from pathlib import Path

import numpy as np

from . import quality as q
from .config import DEFAULT
from .geometry import Intrinsics, look_pose, project, unproject_depth
from .levels import measure_depth_view, measure_with_reference
from .pipeline import gross_area_exact, mm
from .simulate import SimFrame, SimFacade, _render_depth, annotate, phone_intrinsics
from .model import View, Observation

FIXTURE = Path(__file__).resolve().parents[2] / "ios" / "Tests" / "PhotoWalkCoreTests" / "Fixtures" / "parity_cases.json"


def _intr(i):
    return dict(fx=i.fx, fy=i.fy, cx=i.cx, cy=i.cy, width=i.width, height=i.height)


def facade_point_cases():
    """Puntenwolk-niveau (ringpunten met zijde): dezelfde gates in Python en Swift. Aantallen zijn 1/4 van de echte diagnose; alles gesimuleerd."""
    from .depth_plane import analyze_points
    REG = {0: ((-0.6, 0.6), (0.35, 0.7)), 1: ((0.35, 0.7), (-0.6, 0.6)), 2: ((-0.6, 0.6), (-0.7, -0.35)), 3: ((-0.7, -0.35), (-0.6, 0.6))}
    rng = np.random.default_rng(11)

    def wall(counts, sigma=0.009, rot=0.0):
        P, S = [], []
        for side, n in enumerate(counts):
            (x0, x1), (y0, y1) = REG[side]
            x, y = rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)
            z = rng.normal(0, sigma, n)
            if rot:
                x, z = x * np.cos(rot) + z * np.sin(rot), -x * np.sin(rot) + z * np.cos(rot)
            P.append(np.stack([x, y, z], 1)); S += [side] * n
        return np.vstack(P), np.array(S)

    def ledge(y, counts, zmax=0.25):
        P, S = [], []
        for side, n in enumerate(counts):
            (x0, x1), _ = REG[side]
            x, z = rng.uniform(x0, x1, n), rng.uniform(0.0, zmax, n)
            P.append(np.stack([x, np.full(n, y) + rng.normal(0, 0.008, n), z], 1)); S += [side] * n
        return np.vstack(P), np.array(S)
    scatter = (rng.uniform([-0.6, -0.7, -0.3], [0.6, 0.7, 0.3], (250, 3)), rng.integers(0, 4, 250))
    strip_x = np.concatenate([rng.uniform(-0.7, -0.4, 400), rng.uniform(0.4, 0.7, 400)])
    strip = (np.stack([strip_x, rng.uniform(-0.01, 0.01, 800), rng.normal(0, 0.004, 800)], 1), np.where(strip_x < 0, 3, 1))
    defs = {
        "real_distribution": [wall([1, 265, 36, 34]), ledge(-0.45, [0, 70, 500, 22]), ledge(-0.55, [0, 44, 174, 8]), scatter],
        "only_ledge": [ledge(-0.45, [200, 200, 200, 200], 0.4)],
        "narrow_strip": [strip],
        "conflicting_vertical_planes": [wall([200, 200, 200, 200]), wall([175, 175, 175, 175], rot=0.6)],
        "one_side_dominates": [wall([1, 2250, 1, 1])],
        "noise_on_chosen_plane": [wall([225, 225, 225, 225], sigma=0.06)],
    }
    intr = phone_intrinsics()
    cam = View("CAP", intr, look_pose([0, 0, 1.262], 0), "NORMAL", None)
    out = []
    for name, parts in defs.items():
        X = np.vstack([p[0] for p in parts]); S = np.concatenate([p[1] for p in parts])
        X = np.round(X, 5)
        an = analyze_points(cam, X, np.ones(len(X), int), S, DEFAULT, 3, quad_diag_px=800.0)
        A = an["assessment"]
        out.append({"name": name, "points": X.reshape(-1).tolist(), "sides": [int(x) for x in S], "quad_diag_px": 800.0,
                    "expect_facade": an["facade"] is not None, "expect_codes": sorted(f["code"] for f in an["flags"]),
                    "expect_covered": A.get("sides", {}).get("covered"), "expect_representative": A["representative"]})
    return out


def build():
    intr_full = phone_intrinsics()
    f = SimFacade(frames=[SimFrame("K1", 1.0, 0.9, 1.2, 1.5), SimFrame("K2", 3.2, 0.9, 1.2, 1.5)])
    pose = look_pose([1.6, 1.6, 4.0], yaw_deg=10)
    rng = np.random.default_rng(0)
    depth = _render_depth(f, pose, intr_full, rng, noise=0.0, hole_p=0.0, size=(48, 64))
    depth = np.round(np.nan_to_num(depth, nan=0.0), 6)
    depth_view = depth.copy()
    depth_view[depth_view == 0] = np.nan
    view = View("PAR", intr_full, pose, "NORMAL", depth_view)
    # kleine ruisvrije annotatie
    corners = project(pose, intr_full, f.frames[0].corners_w)[0]
    ra = measure_depth_view(view, corners, DEFAULT, seed=1)
    corners2 = project(pose, intr_full, f.frames[1].corners_w)[0]
    ref = dict(reference_id="PAR-R", p1_px=corners2[0], p2_px=corners2[1], distance_m=1.2, distance_sigma_m=0.005, plane_id="P")
    vnod = View("PARC", intr_full, pose, "NORMAL", None)
    rc = measure_with_reference(vnod, corners, ref, DEFAULT, seed=1, anchor_px=corners2)
    v2_cases = []
    for name, rec, prot, nsup in (("flush", 0.0, [], 0), ("recessed_8cm", 0.08, [], 0), ("recessed_8cm_multi_frame", 0.08, [], 2),
                                  ("ambiguous_planes", 0.0, [(0.2, 0.9, 0.0, 3.0, 0.15), (2.3, 3.0, 0.0, 3.0, 0.15)], 0),
                                  ("interior_deep_reveal_sill", 0.35, "interior", 0), ("interior_reveals_hide_profile", 0.45, "interior", 0)):
        if prot == "interior":      # binnenopname: diep terugliggend kozijn met dagkanten en vensterbank (regressie echte iPhone-diagnose)
            fr = SimFrame("K1", 1.25, 1.25, 0.7, 0.7, recess_m=rec)
            fac = SimFacade(frames=[fr], ledges=[(1.0, 2.2, 1.25, 0.5)])
            cam_pos = [1.7, 1.5, 1.3]
        else:
            fr = SimFrame("K1", 1.0, 0.9, 1.2, 1.5, recess_m=rec)
            fac = SimFacade(frames=[fr], protrusions=prot)
            cam_pos = [1.6, 1.6, 3.0]

        def mkview(pos, fid):
            ps = look_pose(pos, 0.0)
            dd = np.round(_render_depth(fac, ps, intr_full, np.random.default_rng(0), noise=0.0, hole_p=0.0, size=(72, 96)), 6)
            return ps, dd, View(fid, intr_full, ps, "NORMAL", dd)
        cps, cdd, cview = mkview(cam_pos, "CAP")
        sups = [mkview([cam_pos[0] + 0.08 * (k + 1) * (1 if k % 2 == 0 else -1), cam_pos[1], cam_pos[2]], f"S{k}") for k in range(nsup)]
        cc = project(cps, intr_full, fr.corners_w)[0]
        rr = measure_depth_view(cview, cc, DEFAULT, seed=1, supports=tuple(x[2] for x in sups))
        fmt = lambda dd: [round(float(x), 6) for x in np.nan_to_num(dd, nan=0.0).reshape(-1)]
        v2_cases.append({"name": name, "depth_width": 96, "depth_height": 72, "corners_px": [[round(float(x), 6) for x in c] for c in cc],
                         "capture": {"pose_row_major": [round(float(x), 9) for x in cps.reshape(-1)], "depth": fmt(cdd)},
                         "supports": [{"pose_row_major": [round(float(x), 9) for x in ps.reshape(-1)], "depth": fmt(dd)} for ps, dd, _ in sups],
                         "expect_ok": bool(rr.ok), "expect_width_m": rr.width_m, "expect_height_m": rr.height_m, "expect_scale_method": rr.scale_method,
                         "expect_independent_frames": rr.independent_frames, "expect_blocking": sorted(f["code"] for f in rr.flags if f["severity"] == "BLOCKING"),
                         "expect_frame_mode": rr.diag.get("frame_plane", {}).get("final_mode"),
                         "expect_representative": (rr.diag.get("facade_assessment") or {}).get("representative")})
    cases = {
        "facade_point_cases": facade_point_cases(),
        "level_a_v2": v2_cases,
        "version": "photo_walk_parity_v1",
        "tolerance": {"geometry_m": 1e-6, "level_a_m": 2e-3, "level_c_m": 1e-6},
        "pose_row_major": [round(float(x), 9) for x in pose.reshape(-1)],
        "intrinsics": _intr(intr_full),
        "project": {"world": [[2.0, 2.0, 0.0], [0.3, 0.8, 0.5]],
                    "expect": [[round(float(x), 6) for x in project(pose, intr_full, w)[0][0]] + [round(float(project(pose, intr_full, w)[1][0]), 9)]
                               for w in ([2.0, 2.0, 0.0], [0.3, 0.8, 0.5])]},
        "unproject": {"pixel": [900.0, 700.0], "depth_z": 4.2,
                      "expect": [round(float(x), 9) for x in unproject_depth(pose, intr_full, [[900.0, 700.0]], [4.2])[0]]},
        "level_a": {"depth_width": 64, "depth_height": 48, "depth": [round(float(x), 6) for x in np.nan_to_num(depth_view, nan=0.0).reshape(-1)],
                    "corners_px": [[round(float(x), 6) for x in c] for c in corners], "expect_ok": bool(ra.ok),
                    "expect_width_m": ra.width_m, "expect_height_m": ra.height_m, "expect_flags": sorted(f["code"] for f in ra.flags)},
        "level_c": {"target_px": [[round(float(x), 6) for x in c] for c in corners], "anchor_px": [[round(float(x), 6) for x in c] for c in corners2],
                    "p1_px": [round(float(x), 6) for x in corners2[0]], "p2_px": [round(float(x), 6) for x in corners2[1]], "distance_m": 1.2,
                    "expect_ok": bool(rc.ok), "expect_width_m": rc.width_m, "expect_height_m": rc.height_m},
        "area": [{"width_m": w, "height_m": h, "expect_width": format(mm(w), "f"), "expect_height": format(mm(h), "f"),
                  "expect_area": format(gross_area_exact(mm(w), mm(h), 1), "f")} for w, h in ((1.2034, 1.4987), (2.1, 1.5), (0.9004, 1.2006))],
        "flag_instructions": {code: q.FLAGS[code][1] for code in sorted(q.FLAGS)},
    }
    return cases


def main():
    cases = build()
    text = json.dumps(cases, sort_keys=True, indent=0) + "\n"
    if "--check" in sys.argv:
        return 0 if FIXTURE.read_text() == text else 1
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text)
    print("geschreven", FIXTURE, len(text) // 1024, "kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
