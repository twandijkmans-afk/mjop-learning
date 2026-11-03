"""Replay-tests op de twee ECHTE iPhone-LiDAR-metingen (REAL_SENSOR) OBS-F005-04 en OBS-F014-03 + de door de eigenaar opgegeven werkelijke maten.

Dit zijn KARAKTERISERINGSTESTS: ze leggen het huidige gedrag van de bestaande code vast en bewaken de pose-vrije feiten. Ze veranderen geen drempel
en geen poort. Er worden geen foto's gebruikt (die staan niet in de repository).
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from photo_walk_core import depth_plane as dp
from photo_walk_core import diagnostics as dg
from photo_walk_core import ext_diagnostics as ed
from photo_walk_core.config import DEFAULT as CFG
from photo_walk_core.geometry import Intrinsics
from photo_walk_core.model import View

DIR = Path(__file__).parent / "real_captures"
F005 = json.loads((DIR / "meetdiagnose_acb1d24b5cd6_OBS-F005-04.json").read_text(encoding="utf-8"))
F014 = json.loads((DIR / "meetdiagnose_acb1d24b5cd6_OBS-F014-03.json").read_text(encoding="utf-8"))
GT = json.loads((DIR / "ground_truth_kozijn_F005_F014.json").read_text(encoding="utf-8"))
REAL = {"F005": F005, "F014": F014}
KOZIJN = (GT["kozijn_outer_cm"]["width"] / 100, GT["kozijn_outer_cm"]["height"] / 100)
GLASS = (GT["glass_cm"]["width"] / 100, GT["glass_cm"]["height"] / 100)


def intr(rec):
    c = rec["camera"]
    return Intrinsics(c["fx"], c["fy"], c["cx"], c["cy"], c["width"], c["height"])


def dummy_view(rec, shape=(192, 256)):
    """View met alleen een diepte-RASTER (NaN): genoeg om geometrie-alleen-velden (ring, marges) te reproduceren; geen echte diepte."""
    return View(frame_id=rec["frame_id"], intrinsics=intr(rec), pose=np.eye(4), depth=np.full(shape, np.nan, np.float32))


@pytest.mark.parametrize("name", ["F005", "F014"])
def test_files_are_valid_real_sensor_without_images(name):
    rec = REAL[name]
    assert rec["data_origin"] == "REAL_SENSOR" and rec["platform"] == "IOS"
    assert dg.schema_errors(rec) == [] and dg.forbidden_key_paths(rec) == []
    assert all(v is False for v in rec["privacy"].values())
    a = rec["algorithm"]
    assert a["points_ring"] + a["points_band"] + a["points_glass"] == a["points_valid_total"]
    assert a["ring_valid"] / a["ring_pixels"] == pytest.approx(a["ring_coverage"], abs=1e-4)
    assert rec["measurement"]["status"] == "UNKNOWN" and rec["measurement"]["width_m"] is None
    assert not (DIR.parent.parent.parent / "ios").is_symlink()
    assert not [p for p in DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".webp", ".zip")]


def test_blocking_sets():
    assert {f["code"] for f in F005["result_flags"]} == {"AMBIGUOUS_FACADE_PLANES", "OUTER_CONTOUR_UNVERIFIED"}
    assert {f["code"] for f in F014["result_flags"]} == {"FACADE_ONE_SIDED", "OUTER_CONTOUR_UNVERIFIED"}
    for r in (F005, F014):
        assert all(f["severity"] == "BLOCKING" for f in r["result_flags"])


def _planes_from_export(rec):
    a = rec["algorithm"]
    out, start = [], 0
    for p in a["planes"]:
        out.append({"n": np.array(p["normal"], float), "d": float(p["offset"]), "count": int(p["count"]), "role": p["role"], "rms": float(p["rms_m"]),
                    "idx": np.arange(start, start + int(p["count"])), "sides": np.array(p["sides"]), "centroid": np.zeros(3), "facing": float(p["facing"]),
                    "vertical": float(p["vertical"]), "spread": 0.5})
        start += int(p["count"])
    return out, a


def test_gate_replay_f005_is_ambiguous_with_the_existing_code():
    planes, a = _planes_from_export(F005)
    # eerste classificatie als in de app: alle drie zijn 'FACADE_CANDIDATE' (verticaal en facing >= 0,35)
    assert [p["role"] for p in planes] == ["FACADE_CANDIDATE"] * 3
    fac, code, detail, A = dp.pick_facade(planes, np.zeros((a["points_ring"], 3)), np.zeros(a["points_ring"], int), a["range_median_m"], CFG, None)
    assert fac is None and code == "AMBIGUOUS_FACADE_PLANES"
    assert detail == a["facade_assessment"]["reasons"][0]
    p0, p1 = a["planes"][0], a["planes"][1]
    assert abs(np.dot(p0["normal"], p1["normal"])) < 0.2                         # loodrecht (83 graden)
    assert p1["count"] / p0["count"] >= CFG.ambiguity_ratio and p1["facing"] >= CFG.facade_min_facing
    assert p1["sides"] == [0, 0, 0, p1["count"]]                                  # het concurrerende vlak ligt op EEN zijde


def test_gate_replay_f014_is_one_sided_with_the_existing_code():
    planes, a = _planes_from_export(F014)
    planes[0]["role"] = "FACADE_CANDIDATE"
    fac, code, detail, A = dp.pick_facade(planes, np.zeros((a["points_ring"], 3)), np.zeros(a["points_ring"], int), a["range_median_m"], CFG, None)
    exp = a["facade_assessment"]
    assert fac is None and code == "FACADE_ONE_SIDED" and detail.startswith(exp["reasons"][0])
    assert A["support"] == pytest.approx(exp["support"], abs=1e-3)
    assert A["unexplained"]["share"] == pytest.approx(exp["unexplained"]["share"], abs=1e-3)
    assert A["excluded_other_layer"]["share"] == pytest.approx(exp["excluded_other_layer"]["share"], abs=1e-3)
    # geen enkel vlak in de ring is frontaal; het gekozen 'gevel'-vlak is een schuine zijwand (incidentie > 60 graden)
    assert max(p["facing"] for p in a["planes"]) < 0.5
    assert a["planes"][0]["facing"] >= CFG.facade_min_facing


@pytest.mark.parametrize("name", ["F005", "F014"])
def test_ring_geometry_is_reproduced_exactly(name):
    rec = REAL[name]
    v = dummy_view(rec)
    reg = dp.Regions(np.array(rec["corners_px"], float), CFG)
    Hd, Wd = v.depth.shape
    sx, sy = v.intrinsics.width / Wd, v.intrinsics.height / Hd
    jj, ii = np.meshgrid(np.arange(Wd), np.arange(Hd))
    uv = np.stack([(jj + 0.5) * sx, (ii + 0.5) * sy], -1).reshape(-1, 2)
    kind, _ = reg.classify(uv)
    assert int((kind == 1).sum()) == rec["algorithm"]["ring_pixels"]


def test_framing_is_geometry_only_and_not_a_distance_requirement():
    f5 = ed.framing(dummy_view(F005), F005["corners_px"], CFG, F005["algorithm"]["range_median_m"])
    f14 = ed.framing(dummy_view(F014), F014["corners_px"], CFG, F014["algorithm"]["range_median_m"])
    assert f5["ring_per_side"]["BOTTOM"]["ring_pixels"] == 314 and f5["ring_per_side"]["TOP"]["ring_pixels"] == 4162
    assert f14["ring_per_side"]["TOP"]["ring_pixels"] == 1979 and f14["ring_per_side"]["BOTTOM"]["ring_pixels"] == 2421
    assert 0.60 <= f5["ring_in_view_fraction"] <= 0.68
    assert min(f5["margins_px"].values()) < 80          # native sensorpixels (landscape): de kleinste marge is 'right' = onderzijde in het portretbeeld
    assert f5["distance_for_full_ring_m"] > F005["algorithm"]["range_median_m"]
    assert "geen eis" in f5["note"] and not any(k in f5 for k in ("gate", "status", "required"))


@pytest.mark.parametrize("name", ["F005", "F014"])
def test_corners_are_consistent_with_a_rectangle_and_the_lens(name):
    """Het kader is een rechthoek volgens de lens (assen 90 +- 2 graden). Het verschil boven/onder in pixels is perspectief, geen niet-rechthoek."""
    q = ed.quad_pose_free(REAL[name]["corners_px"], intr(REAL[name]))
    assert abs(q["axes_angle_deg"] - 90.0) < 2.0
    assert q["facing"] > 0.95


@pytest.mark.parametrize("name", ["F005", "F014"])
def test_quad_is_the_glass_not_the_frame_from_the_corners_alone(name):
    asp_glass, asp_frame = GLASS[0] / GLASS[1], KOZIJN[0] / KOZIJN[1]
    q = ed.quad_pose_free(REAL[name]["corners_px"], intr(REAL[name]))
    a = q["aspect_w_over_h"]
    assert abs(a - asp_glass) < abs(a - asp_frame)
    assert abs(a / asp_glass - 1) < 0.03 and a / asp_frame - 1 < -0.05
    # robuust tegen hoekruis tot 10 px (P5-P95): het kozijn-aspect valt er buiten
    rng = np.random.default_rng(1)
    vals = []
    for _ in range(300):
        c = np.array(REAL[name]["corners_px"], float) + rng.normal(0, 10.0, (4, 2))
        vals.append(ed.quad_pose_free(c, intr(REAL[name]))["aspect_w_over_h"])
    lo, hi = np.percentile(vals, [5, 95])
    assert not (lo <= asp_frame <= hi)


def test_error_budget_if_the_glass_were_published_as_frame():
    area_f, area_g = KOZIJN[0] * KOZIJN[1], GLASS[0] * GLASS[1]
    assert area_g / area_f - 1 == pytest.approx(-0.190, abs=0.001)
    assert GLASS[0] / KOZIJN[0] - 1 == pytest.approx(-0.141, abs=0.001) and GLASS[1] / KOZIJN[1] - 1 == pytest.approx(-0.057, abs=0.001)
    # de contourpoort heeft dit hier voorkomen: geen enkele geblokkeerde meting publiceert een maat
    for rec in (F005, F014):
        assert any(f["code"] == "OUTER_CONTOUR_UNVERIFIED" for f in rec["result_flags"])
        assert rec["measurement"]["width_m"] is None and rec["measurement"]["area_m2"] is None


def test_frame_rejections_follow_from_the_existing_rule():
    """CORRELATED_OR_LIMIT kan hier alleen 'gecorreleerd' betekenen: met 1 gekozen frame is de limiet (1 + max_support_frames) onbereikbaar."""
    a5, a14 = F005["algorithm"], F014["algorithm"]
    assert a5["frames_total"] == 9 and a5["frames_independent_candidates"] == 1 and {f["why"] for f in a5["frames_rejected"]} == {"CORRELATED_OR_LIMIT"}
    assert 1 < 1 + CFG.max_support_frames
    reasons = [f["why"] for f in a14["frames_rejected"]]
    assert a14["frames_independent_candidates"] == 1 and reasons.count("CORRELATED_OR_LIMIT") == 2 and reasons.count("TRACKING_OR_DEPTH") == 6
    assert F014["algorithm"]["tracking_capture"] == "NORMAL"


def test_same_kozijn_in_both_captures():
    """Zelfde kozijn volgens de eigenaar; de pose-vrije aspecten komen binnen 1% overeen."""
    a5 = ed.quad_pose_free(F005["corners_px"], intr(F005))["aspect_w_over_h"]
    a14 = ed.quad_pose_free(F014["corners_px"], intr(F014))["aspect_w_over_h"]
    assert abs(a5 / a14 - 1) < 0.01


def test_pose_free_cross_check_separates_host_planes():
    """Het kader impliceert een vlak met facing ~0,98-0,99. F005: alleen P0 (0,999) komt overeen. F014: geen enkel LiDAR-vlak komt overeen."""
    f5 = ed.quad_pose_free(F005["corners_px"], intr(F005))["facing"]
    f14 = ed.quad_pose_free(F014["corners_px"], intr(F014))["facing"]
    p5 = [p["facing"] for p in F005["algorithm"]["planes"]]
    p14 = [p["facing"] for p in F014["algorithm"]["planes"]]
    assert min(range(3), key=lambda i: abs(p5[i] - f5)) == 0 and abs(p5[0] - f5) < 0.05 and abs(p5[1] - f5) > 0.5
    assert all(abs(p - f14) > 0.5 for p in p14)
