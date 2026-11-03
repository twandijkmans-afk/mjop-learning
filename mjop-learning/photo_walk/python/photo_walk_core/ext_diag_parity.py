"""Pariteitsfixture voor de uitgebreide diagnose (1.1.0): Python-referentie <-> Swift.
Leest de bestaande invoer (ios/Tests/PhotoWalkCoreTests/Fixtures/parity_cases.json, `level_a_v2`) en schrijft de verwachte uitgebreide diagnose naar
ios/Tests/PhotoWalkCoreTests/Fixtures/ext_diag_parity_cases.json. De Swift-tests (ExtendedDiagnosticsTests) lezen beide bestanden en moeten dezelfde uitkomst geven.
Ruisvrije scènes: de vergelijking test de geometrie en de bookkeeping, niet de ruis (PRNG's verschillen). Geen foto's, alleen synthetische getallen.
Gebruik: python -m photo_walk_core.ext_diag_parity [--check]"""
import json
import sys
from pathlib import Path

import numpy as np

from . import ext_diagnostics as ed
from .config import DEFAULT
from .diagnostics import json_safe
from .geometry import Intrinsics
from .levels import measure_depth_view
from .model import View

FIX = Path(__file__).resolve().parents[2] / "ios" / "Tests" / "PhotoWalkCoreTests" / "Fixtures"
SRC, OUT = FIX / "parity_cases.json", FIX / "ext_diag_parity_cases.json"
# echte kaders + intrinsics (alleen getallen) van OBS-F005-04 en OBS-F014-03, voor de pose-vrije velden en de geometrie van de ring
REAL = Path(__file__).resolve().parents[1] / "tests" / "real_captures"


def _view(c, fid, entry, intr, dw, dh):
    pose = np.array(entry["pose_row_major"], float).reshape(4, 4)
    z = np.array(entry["depth"], float)
    z[z == 0] = np.nan
    return View(frame_id=fid, intrinsics=intr, pose=pose, depth=z.reshape(dh, dw).astype(np.float32))


def build():
    c = json.loads(SRC.read_text())
    i = c["intrinsics"]
    intr = Intrinsics(i["fx"], i["fy"], i["cx"], i["cy"], i["width"], i["height"])
    cases = []
    for cs in c["level_a_v2"]:
        dw, dh = cs["depth_width"], cs["depth_height"]
        sups = [_view(c, f"S{k}", e, intr, dw, dh) for k, e in enumerate(cs["supports"])]
        cap = _view(c, "CAP", cs["capture"], intr, dw, dh)
        corners = np.array(cs["corners_px"], float)
        res = measure_depth_view(cap, corners, DEFAULT, seed=1, supports=tuple(sups))
        ext = ed.compute(cap, corners, res, cfg=DEFAULT, seed=1, supports=tuple(sups), contour_status="USER_CONFIRMED")
        cases.append({"name": cs["name"], "expect": json_safe(ext)})
    real = []
    for name in ("F005-04", "F014-03"):
        rec = json.loads((REAL / f"meetdiagnose_acb1d24b5cd6_OBS-{name}.json").read_text())
        cam = rec["camera"]
        ic = Intrinsics(cam["fx"], cam["fy"], cam["cx"], cam["cy"], cam["width"], cam["height"])
        v = View(frame_id=rec["frame_id"], intrinsics=ic, pose=np.eye(4), depth=np.full((192, 256), np.nan, np.float32))
        real.append({"name": name, "intrinsics": cam, "corners_px": rec["corners_px"], "range_median_m": rec["algorithm"]["range_median_m"],
                     "expect_quad_from_corners": json_safe(ed.quad_pose_free(rec["corners_px"], ic)),
                     "expect_framing": json_safe(ed.framing(v, rec["corners_px"], DEFAULT, rec["algorithm"]["range_median_m"]))})
    return {"version": "photo_walk_ext_diag_parity_v1", "tolerance": {"abs": 5e-3, "angle_deg": 5e-2}, "cases": cases, "real_quads": real}


def main():
    text = json.dumps(build(), sort_keys=True, indent=0) + "\n"
    if "--check" in sys.argv:
        return 0 if OUT.read_text() == text else 1
    OUT.write_text(text)
    print("geschreven", OUT, len(text) // 1024, "kB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
