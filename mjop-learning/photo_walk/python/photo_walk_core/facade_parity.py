"""Pariteitscases voor de Swift-port van de gevelopbouw (PhotoWalkCoreTests/FacadeTests.swift).

    python -m photo_walk_core.facade_parity            # schrijft ios/Tests/PhotoWalkCoreTests/Fixtures/facade_parity_cases.json

Alle cases zijn SYNTHETISCH (getekende gevel, exacte waarheid): ze bewijzen dat Swift en Python hetzelfde rekenen, niet dat de
herkenning op echte gevels werkt.
"""
import json
from pathlib import Path

import numpy as np

from . import facade as F

OUT = Path(__file__).resolve().parents[2] / "ios" / "Tests" / "PhotoWalkCoreTests" / "Fixtures" / "facade_parity_cases.json"

IMAGE = {"width": 1200, "height": 700}
WINDOWS = [
    {"outer": [200, 150, 420, 450], "profile": 14, "mullions": 0, "transom": False},
    {"outer": [600, 140, 900, 460], "profile": 12, "mullions": 1, "transom": True},
]


def _windows():
    return [dict(w, outer=tuple(w["outer"])) for w in WINDOWS]


def _q(p):
    return [[float(a), float(b)] for a, b in p]


def organizer_cases():
    tr = F.synthetic_truth(_windows())
    panes = [p for t in tr for p in t["panes"]]
    outers = [t["outer"] for t in tr]
    facade_rect = [(150, 100), (950, 100), (950, 520), (150, 520)]
    door_outer = [(950, 200), (1060, 200), (1060, 600), (950, 600)]
    door_glass = [(980, 230), (1030, 230), (1030, 300), (980, 300)]
    tilted = [(300.0, 520.0), (380.0, 515.0), (384.0, 600.0), (304.0, 606.0)]
    cases = {
        "panes_only": [(p, "VN_RECTANGLE_CANDIDATE", 0.9) for p in panes],
        "panes_and_outers": [(p, "VN_RECTANGLE_CANDIDATE", 0.9) for p in panes] + [(o, "VN_CONTOUR_QUAD_CANDIDATE", 0.7) for o in outers],
        "facade_contains_frames": [(p, "VN_RECTANGLE_CANDIDATE", 0.9) for p in panes] + [(o, "VN_RECTANGLE_CANDIDATE", 0.8) for o in outers]
                                  + [(facade_rect, "VN_RECTANGLE_CANDIDATE", 0.5)],
        "door_small_glass": [(door_outer, "VN_RECTANGLE_CANDIDATE", 0.8), (door_glass, "VN_RECTANGLE_CANDIDATE", 0.9)],
        "duplicates_and_noise": [(outers[0], "VN_RECTANGLE_CANDIDATE", 0.6), ([(a + 1, b + 1) for a, b in outers[0]], "VN_CONTOUR_QUAD_CANDIDATE", 0.9),
                                 ([(10, 10), (14, 10), (14, 13), (10, 13)], "VN_RECTANGLE_CANDIDATE", 0.9),
                                 ([(0, 0), (1200, 0), (1200, 700), (0, 700)], "VN_RECTANGLE_CANDIDATE", 0.9),
                                 ([(500, 500), (560, 500), (500, 560), (560, 560)], "VN_RECTANGLE_CANDIDATE", 0.9), (tilted, "VN_RECTANGLE_CANDIDATE", 0.4)],
        "closeup_single_window": [([(100, 50), (1100, 50), (1100, 650), (100, 650)], "VN_RECTANGLE_CANDIDATE", 0.8),
                                  ([(160, 110), (1040, 110), (1040, 590), (160, 590)], "VN_RECTANGLE_CANDIDATE", 0.9)],
    }
    out = []
    for name, cands in cases.items():
        qc = [F.QuadCandidate(list(c), d, s) for c, d, s in cands]
        groups, ignored = F.organize(qc, IMAGE["width"], IMAGE["height"])
        out.append({
            "name": name,
            "candidates": [{"corners": _q(c), "detector": d, "score": s} for c, d, s in cands],
            "groups": [{"outer": _q(g.outer), "outer_detected": g.outer_detected, "panes": [_q(p) for p in g.panes], "evidence": g.evidence,
                        "status": g.status, "detector": g.detector, "score": g.score, "glass_coverage": g.glass_coverage} for g in groups],
            "ignored": sorted([{"detector": i.detector, "reason": i.reason} for i in ignored], key=lambda x: (x["reason"], x["detector"])),
        })
    return out


def expansion_cases():
    img = F.synthetic_facade_gray(IMAGE["width"], IMAGE["height"], _windows())
    tr = F.synthetic_truth(_windows())
    quads = {"single_pane": tr[0]["panes"][0], "pane_of_multipane": tr[1]["panes"][0],
             "pane_group_bbox": [(612, 152), (888, 152), (888, 448), (612, 448)],
             "on_plain_wall": [(40, 520), (120, 520), (120, 600), (40, 600)]}
    out = []
    for name, q in quads.items():
        r = F.propose_outer(img, q)
        out.append({"name": name, "quad": _q(q), "result": None if r is None else {"quad": _q(r["quad"]), "offsets_px": r["offsets_px"]}})
    return out


def compose_case():
    # camera recht voor een verticale gevel op 5 m (z vooruit), wereld: y omhoog -> R draait y; t = camera in de oorsprong
    fx = fy = 1000.0
    cx, cy = 600.0, 350.0
    R = [[-1, 0, 0], [0, -1, 0], [0, 0, 1]]           # rotatie (det = +1): camera-y omlaag = wereld-y omhoog
    t = [0.0, 1.5, 0.0]
    n, d = [0.0, 0.0, 1.0], 5.0                      # gevelvlak z = 5
    tr = F.synthetic_truth(_windows())
    openings = [
        F.OpeningInput("OBS-1", tr[0]["outer"], F._mm3(F.planar_polygon_area_m2(tr[0]["outer"], (R, t), (fx, fy, cx, cy), n, d)), "ESTIMATED", tuple(n), d, tr[0]["panes"]),
        F.OpeningInput("OBS-2", tr[1]["outer"], F._mm3(F.planar_polygon_area_m2(tr[1]["outer"], (R, t), (fx, fy, cx, cy), n, d)), "DERIVED", tuple(n), d, tr[1]["panes"]),
    ]
    facade = [(100, 80), (1100, 80), (1100, 620), (100, 620)]
    full = F.compose(openings, (R, t), (fx, fy, cx, cy), facade, (n, d), "ESTIMATED")
    no_scale = F.compose([F.OpeningInput("OBS-1", tr[0]["outer"], None, "UNKNOWN", None, None, tr[0]["panes"])], None, None, facade, None, "UNKNOWN")
    missing_panes = F.compose([F.OpeningInput("OBS-1", tr[0]["outer"], openings[0].area_m2, "ESTIMATED", tuple(n), d, [])], (R, t), (fx, fy, cx, cy), facade, (n, d), "ESTIMATED")

    def enc(o):
        return {"id": o.id, "outer_px": _q(o.outer_px), "area_m2": None if o.area_m2 is None else str(o.area_m2), "status": o.status,
                "plane_n": None if o.plane_n is None else list(o.plane_n), "plane_d": o.plane_d, "panes_px": [_q(p) for p in o.panes_px]}
    return {
        "camera": {"fx": fx, "fy": fy, "cx": cx, "cy": cy, "rows": R, "t": t},
        "facade_plane": {"n": n, "d": d, "status": "ESTIMATED"}, "facade_px": _q(facade),
        "cases": [
            {"name": "full", "openings": [enc(o) for o in openings], "with_scale": True, "with_facade_plane": True, "expected": full},
            {"name": "no_scale", "openings": [enc(F.OpeningInput("OBS-1", tr[0]["outer"], None, "UNKNOWN", None, None, tr[0]["panes"]))],
             "with_scale": False, "with_facade_plane": False, "expected": no_scale},
            {"name": "missing_panes", "openings": [enc(F.OpeningInput("OBS-1", tr[0]["outer"], openings[0].area_m2, "ESTIMATED", tuple(n), d, []))],
             "with_scale": True, "with_facade_plane": True, "expected": missing_panes},
            {"name": "no_frames_in_facade", "openings": [], "with_scale": True, "with_facade_plane": True,
             "expected": F.compose([], (R, t), (fx, fy, cx, cy), facade, (n, d), "ESTIMATED")},
        ],
    }


def build_parity_cases():
    img = F.synthetic_facade_gray(IMAGE["width"], IMAGE["height"], _windows())
    return {
        "note": "SYNTHETISCH; gegenereerd door photo_walk_core.facade_parity. Niet met de hand bewerken.",
        "image": IMAGE, "windows": WINDOWS,
        "image_checksum": int(np.sum(img.astype(np.int64) * (np.arange(img.size, dtype=np.int64).reshape(img.shape) % 9973 + 1)) % 1000000007),
        "organizer": organizer_cases(),
        "expansion": expansion_cases(),
        "compose": compose_case(),
    }


def main():
    OUT.write_text(json.dumps(build_parity_cases(), indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    print(OUT)


if __name__ == "__main__":
    main()
