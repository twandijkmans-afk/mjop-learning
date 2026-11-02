"""Regressie: één vastgelegde foto is NOOIT MEASURED (besluit november 2026).

Ondersteunende LiDAR-dieptekaders rond één foto (support_views) verbeteren de meting van die foto (LIDAR_DEPTH_MULTI_FRAME), maar zijn geen
apart vastgelegde standpunten. MEASURED vraagt >= 2 APART vastgelegde foto's (keyframes) met verschillende cameraposities (>= min_baseline_m,
bestaande drempel, niet versoepeld) die consistent meten, plus een bevestigde buitencontour en geen afwaarderende codes.
Referentiemaat (niveau C) blijft DERIVED. Alles is SIMULATIE: dit bewijst rekenregels, geen nauwkeurigheid op echte gevels.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from scenes import build  # noqa: E402

from photo_walk_core import facade as F  # noqa: E402
from photo_walk_core.config import DEFAULT as CFG  # noqa: E402
from photo_walk_core.contract import build_record  # noqa: E402
from photo_walk_core.model import Observation, correct_corner  # noqa: E402
from photo_walk_core.pipeline import independent_photo_count, process_session  # noqa: E402
from photo_walk_core.simulate import annotate, make_view, standard_facade  # noqa: E402

CAP = {"lidar": True, "scene_depth": True, "ar_world_tracking": True, "metric_tracking": True, "camera_intrinsics_available": True}


def session():
    return {"session_id": "SYN-VP", "building_id": "B-SYN", "facade_id": "F-SYN", "platform": "SIMULATION", "device_model": "synthetic",
            "data_origin": "SIMULATION", "validation_level": "SIMULATED", "capabilities": CAP}


def codes(o):
    return {f["code"] for f in o["quality_flags"]}


@pytest.fixture(scope="module")
def facade():
    return standard_facade()


# 1 --------------------------------------------------------------------------------------------- één foto + meerdere LiDAR-kaders
def test_one_photo_with_multiple_independent_lidar_frames_is_estimated():
    s = build(recess=0.06, extra_frames=3, spacing=0.06)
    cap = s["cap"]
    cap.support_views = tuple(s["extras"])
    ob = Observation("OBS-CAP-K1", cap.frame_id, s["corners"].copy())
    res = process_session(session(), [cap], [ob])
    o = res["objects"][0]
    assert o["measurement_source"]["scale_method"] == "LIDAR_DEPTH_MULTI_FRAME", "de ondersteunende kaders worden wel gebruikt"
    assert o["outer_width_m"] is not None
    assert o["dimension_status"] == "ESTIMATED"
    assert "SINGLE_VIEWPOINT" in codes(o)
    assert o["measurement_source"]["views"] == [cap.frame_id]


# 2 --------------------------------------------------------------------------------------------- één foto + handmatig verbeterde hoeken
def test_one_photo_with_manually_corrected_corners_is_never_measured(facade):
    v = make_view(facade, "F0", [1.6, 1.6, 4.0], seed=1)
    fr = facade.frames[0]
    a = annotate(fr, v, seed=3)
    fixed = correct_corner(a, 2, a.corners_px[2] + [1.0, 1.0], "tester", "2026-01-01T00:00:00Z")
    o = process_session(session(), [v], [fixed])["objects"][0]
    assert o["dimension_status"] != "MEASURED" and o["dimension_status"] == "ESTIMATED"
    assert "HUMAN_CORRECTED_CORNERS" in codes(o)
    # dezelfde foto twee keer aangeklikt (twee waarnemingen op één keyframe) is nog steeds één standpunt
    b = annotate(fr, v, seed=4)
    b.observation_id = "OBS-F0-K1-bis"
    for ob in process_session(session(), [v], [fixed, b])["objects"]:
        assert ob["dimension_status"] != "MEASURED"


# 3 --------------------------------------------------------------------------------------------- twee aparte foto's, consistent
def test_two_separate_consistent_photos_can_be_measured(facade):
    v1 = make_view(facade, "F0", [1.6, 1.6, 4.0], seed=1)
    v2 = make_view(facade, "F1", [2.6, 1.6, 4.0], yaw_deg=8, seed=2)
    fr = facade.frames[0]
    o = process_session(session(), [v1, v2], [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)])["objects"][0]
    assert o["dimension_status"] == "MEASURED"
    assert "SINGLE_VIEWPOINT" not in codes(o)


# 4 --------------------------------------------------------------------------------------------- twee foto's vanaf (vrijwel) hetzelfde standpunt
def test_two_photos_from_effectively_the_same_viewpoint_are_not_measured(facade):
    d = CFG.min_baseline_m * 0.5                               # onder de bestaande onafhankelijkheidsdrempel
    v1 = make_view(facade, "F0", [1.6, 1.6, 4.0], seed=1)
    v2 = make_view(facade, "F1", [1.6 + d, 1.6, 4.0], seed=2)
    fr = facade.frames[0]
    res = process_session(session(), [v1, v2], [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)])
    assert len(res["objects"]) == 1
    o = res["objects"][0]
    assert len(o["observation_refs"]) == 2 and o["dimension_status"] == "ESTIMATED" and "SINGLE_VIEWPOINT" in codes(o)


# 5 --------------------------------------------------------------------------------------------- tegenstrijdige standpunten
def test_conflicting_viewpoints_are_never_measured(facade):
    v1 = make_view(facade, "F0", [1.6, 1.6, 4.0], seed=1)
    v2 = make_view(facade, "F1", [2.6, 1.6, 4.0], yaw_deg=8, seed=2)
    fr = facade.frames[0]
    a, b = annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)
    b.corners_px[1] += [60, 0]
    b.corners_px[2] += [60, 0]
    o = process_session(session(), [v1, v2], [a, b])["objects"][0]
    assert o["dimension_status"] == "UNKNOWN" and "VIEWS_INCONSISTENT" in codes(o)


# 6 --------------------------------------------------------------------------------------------- gevelopbouw en MJOP-export waarderen niet op
def test_facade_composition_never_upgrades_a_single_photo_to_measured():
    case = json.loads((Path(__file__).resolve().parents[2] / "ios" / "Tests" / "PhotoWalkCoreTests" / "Fixtures" / "facade_parity_cases.json").read_text())
    c = case["compose"]
    R, t = c["camera"]["rows"], c["camera"]["t"]
    cam = (c["camera"]["fx"], c["camera"]["fy"], c["camera"]["cx"], c["camera"]["cy"])
    n, d = c["facade_plane"]["n"], c["facade_plane"]["d"]
    full = next(x for x in c["cases"] if x["name"] == "full")
    ops = [F.OpeningInput(o["id"], [tuple(p) for p in o["outer_px"]], F._mm3(float(o["area_m2"])), "MEASURED", tuple(n), d,
                          [[tuple(p) for p in q] for q in o["panes_px"]]) for o in full["openings"]]
    out = F.compose(ops, (R, t), cam, [tuple(p) for p in c["facade_px"]], (n, d), "MEASURED")
    statuses = {k: v["status"] for k, v in out.items() if isinstance(v, dict) and "status" in v}
    assert "MEASURED" not in json.dumps(out), statuses
    assert out["facade_gross"]["status"] == "ESTIMATED" and out["frame_outer"]["status"] == "ESTIMATED"
    assert F.single_photo("DERIVED") == "DERIVED" and F.single_photo("UNKNOWN") == "UNKNOWN"     # referentiemaat ongewijzigd


def test_single_photo_export_and_bruto_intake_contain_no_measured():
    from photo_walk_core import to_bruto
    s = build(recess=0.06, extra_frames=3, spacing=0.06)
    cap = s["cap"]
    cap.support_views = tuple(s["extras"])
    obs = [Observation("OBS-CAP-K1", cap.frame_id, s["corners"].copy())]
    res = process_session(session(), [cap], obs)
    rec = build_record(session(), [cap], obs, [], res)
    assert all(o["dimension_status"] != "MEASURED" for o in rec["objects"])
    assert rec["summary"]["by_status"]["MEASURED"]["count"] == 0
    intake = to_bruto.convert(rec)
    to_bruto.validate(intake)
    assert '"MEASURED"' not in json.dumps(intake)


# ------------------------------------------------------------------------------------------------ telregel zelf
def test_independent_photo_count_rules():
    b = CFG.min_baseline_m
    assert independent_photo_count([], b) == 0
    assert independent_photo_count([("F0", [0, 0, 0])], b) == 1
    assert independent_photo_count([("F0", [0, 0, 0]), ("F0", [1, 0, 0])], b) == 1, "zelfde keyframe telt één keer"
    assert independent_photo_count([("F0", [0, 0, 0]), ("F1", [b * 0.5, 0, 0])], b) == 1, "te dicht bij elkaar"
    assert independent_photo_count([("F0", [0, 0, 0]), ("F1", [b, 0, 0])], b) == 2, "precies de drempel telt (>=)"
    assert independent_photo_count([("F1", [b * 0.6, 0, 0]), ("F0", [0, 0, 0]), ("F2", [b * 1.2, 0, 0])], b) == 2
