"""Testsuite Photo Walk & Scale Capture v1 (alleen synthetische data, geen netwerk, geen bestanden in de repo).

LET OP: deze tests bewijzen dat de GEOMETRIE klopt voor het gesimuleerde model. Ze bewijzen geen nauwkeurigheid op een echte gevel,
met echte LiDAR-ruis, AR-drift of lenzen. Zie docs/device_validation.md.
"""
import ast
import copy
import json
import socket
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

import photo_walk_core
from photo_walk_core import quality as q
from photo_walk_core.config import DEFAULT as CFG
from photo_walk_core.contract import build_record, schema_errors
from photo_walk_core.export import export_record, record_sha256
from photo_walk_core.geometry import Intrinsics, look_pose, project, unproject_depth
from photo_walk_core.levels import measure_depth_view, measure_triangulated, measure_with_reference
from photo_walk_core.model import Observation, correct_corner
from photo_walk_core.pipeline import determine_measurement_mode, mm, process_session
from photo_walk_core.simulate import SimFacade, SimFrame, annotate, make_view, phone_intrinsics, standard_facade

CAP_LIDAR = {"lidar": True, "scene_depth": True, "ar_world_tracking": True, "metric_tracking": True, "camera_intrinsics_available": True}
CAP_AR_ONLY = {"ar_world_tracking": True, "metric_tracking": True, "camera_intrinsics_available": True}
CAP_NONE = {"camera_intrinsics_available": True}


def session(cap=CAP_LIDAR, sid="SYN-T"):
    return {"session_id": sid, "building_id": "B-SYN", "facade_id": "F-SYN", "platform": "SIMULATION", "device_model": "synthetic",
            "data_origin": "SIMULATION", "validation_level": "SIMULATED", "capabilities": cap}


def codes(flags):
    return {f["code"] for f in flags}


@pytest.fixture(scope="module")
def facade():
    return standard_facade()


@pytest.fixture(scope="module")
def v1(facade):
    return make_view(facade, "F0", [1.6, 1.6, 4.0], seed=1)


@pytest.fixture(scope="module")
def v2(facade):
    return make_view(facade, "F1", [2.6, 1.6, 4.0], yaw_deg=8, seed=2)


def near(res_w, res_h, frame, tol=0.02):
    return abs(res_w - frame.width) < tol and abs(res_h - frame.height) < tol


# 1 ---------------------------------------------------------------------------
def test_01_one_frame_four_correct_corners(facade, v1):
    fr = facade.frames[0]
    ob = annotate(fr, v1, seed=3)
    r = measure_depth_view(v1, ob.corners_px, CFG, seed=1)
    assert r.ok and near(r.width_m, r.height_m, fr)
    assert r.scale_method == "LIDAR_DEPTH_PLANE" and r.sigma_w > 0


# 2 ---------------------------------------------------------------------------
def test_02_gross_area_from_measured_outer_dimensions(facade, v1, v2):
    fr = facade.frames[0]
    obs = [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)]
    res = process_session(session(), [v1, v2], obs)
    o = res["objects"][0]
    w, h = Decimal(o["outer_width_m"]), Decimal(o["outer_height_m"])
    assert Decimal(o["gross_area_m2"]) == w * h                    # exact, uit de getoonde buitenmaten
    assert abs(float(o["gross_area_m2"]) - fr.width * fr.height) < 0.05


def test_02b_parity_with_bruto_quantity_core():
    import bruto_quantity_core as core
    w, h = mm(1.2034), mm(1.4987)
    assert core.gross_area_exact(w, h, 1) == w * h


# 3 ---------------------------------------------------------------------------
@pytest.mark.parametrize("glass_mode", ["valid", "holes"])
def test_03_glass_counts_in_gross_area(glass_mode):
    f = standard_facade(glass_mode)
    v, v_b = make_view(f, "F0", [1.6, 1.6, 4.0], seed=1), make_view(f, "F1", [2.6, 1.6, 4.0], yaw_deg=8, seed=2)
    fr = f.frames[0]
    o = process_session(session(), [v, v_b], [annotate(fr, v, seed=3), annotate(fr, v_b, seed=4)])["objects"][0]
    assert abs(float(o["gross_area_m2"]) - fr.width * fr.height) < 0.05          # niet verminderd met glas
    assert abs(float(o["gross_area_m2"]) - fr.width * fr.height * 0.6) > 0.5


# 4 ---------------------------------------------------------------------------
def test_04_movable_parts_do_not_count_separately(facade, v1, v2):
    fr = facade.frames[0]
    obs = [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)]
    a = process_session(session(), [v1, v2], obs, frame_meta={obs[0].observation_id: {"movable_parts": 1, "fixed_parts": 0}})
    b = process_session(session(), [v1, v2], obs, frame_meta={obs[0].observation_id: {"movable_parts": 6, "fixed_parts": 4}})
    assert len(a["objects"]) == len(b["objects"]) == 1
    assert a["objects"][0]["gross_area_m2"] == b["objects"][0]["gross_area_m2"]
    assert b["objects"][0]["parts"]["movable_parts"] == 6


# 5 ---------------------------------------------------------------------------
def test_05_pixel_to_3d_roundtrip_and_known_point():
    intr = phone_intrinsics()
    pose = look_pose([1.0, 1.5, 4.0], yaw_deg=15)
    X = np.array([[2.0, 2.0, 0.0], [0.3, 0.8, 0.5]])
    uv, z = project(pose, intr, X)
    assert np.allclose(unproject_depth(pose, intr, uv, z), X, atol=1e-9)
    # hoofdpunt met depth 4 m ligt 4 m voor de camera langs de optische as (naar -Z)
    p = unproject_depth(look_pose([0, 0, 4.0]), intr, [[intr.cx, intr.cy]], [4.0])
    assert np.allclose(p, [[0, 0, 0]], atol=1e-9)
    # een pixel 100 px rechts van het hoofdpunt op 4 m: 4*100/fx meter in +X
    p = unproject_depth(look_pose([0, 0, 4.0]), intr, [[intr.cx + 100, intr.cy]], [4.0])
    assert np.isclose(p[0, 0], 4.0 * 100 / intr.fx)


# 6 ---------------------------------------------------------------------------
@pytest.mark.parametrize("fx,w,h", [(1100.0, 1920, 1440), (2100.0, 1920, 1440), (800.0, 1280, 960)])
def test_06_different_intrinsics(facade, fx, w, h):
    intr = phone_intrinsics(fx, w, h)
    fr = facade.frames[0]
    dist = 4.0 * fx / 1500 if fx < 1500 else 4.0
    v = make_view(facade, "FX", [1.6, 1.6, dist], seed=1, intr=intr)
    ob = annotate(fr, v, seed=3)
    r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
    assert r.ok and near(r.width_m, r.height_m, fr, 0.03)


# 7 ---------------------------------------------------------------------------
def test_07_perspective_correction_oblique_view(facade):
    v = make_view(facade, "FO", [5.2, 1.6, 2.6], yaw_deg=38, seed=7)
    k1, k2 = facade.frames[0], facade.frames[1]
    ob1, ob2 = annotate(k1, v, seed=8), annotate(k2, v, seed=9)
    # naief: pixelverhouding wijkt duidelijk af van de echte verhouding (perspectief)
    px_w = np.linalg.norm(ob1.corners_px[1] - ob1.corners_px[0])
    px_h = np.linalg.norm(ob1.corners_px[3] - ob1.corners_px[0])
    assert abs(px_w / px_h - k1.width / k1.height) / (k1.width / k1.height) > 0.05
    ref = dict(reference_id="R", p1_px=ob2.corners_px[0], p2_px=ob2.corners_px[1], distance_m=k2.width, distance_sigma_m=0.005, plane_id="P")
    r = measure_with_reference(v, ob1.corners_px, ref, CFG, seed=1, anchor_px=ob2.corners_px)
    assert r.ok and near(r.width_m, r.height_m, k1, 0.04)
    ra = measure_depth_view(v, ob1.corners_px, CFG, seed=1)       # ook de diepte-route corrigeert het perspectief
    assert ra.ok and near(ra.width_m, ra.height_m, k1, 0.03)


# 8 ---------------------------------------------------------------------------
def test_08_reference_on_same_plane(facade):
    v = make_view(facade, "FR", [1.6, 1.6, 4.0], seed=1, with_depth=False)
    fr = facade.frames[0]
    ob = annotate(fr, v, seed=3)
    ref = dict(reference_id="R1", p1_px=ob.corners_px[0], p2_px=ob.corners_px[1], distance_m=fr.width, distance_sigma_m=0.005, plane_id="P")
    r = measure_with_reference(v, ob.corners_px, ref, CFG, seed=1)
    assert r.ok and near(r.width_m, r.height_m, fr, 0.03)
    assert r.scale_method == "REFERENCE_DISTANCE"
    assert r.scale_evidence["reference_id"] == "R1"


# 9 ---------------------------------------------------------------------------
def test_09_reference_on_wrong_plane(facade):
    f = SimFacade(frames=facade.frames, protrusions=[(3.0, 4.8, 0.6, 2.8, 0.8)])      # balkonplaat 0,8 m voor de gevel
    v = make_view(f, "FW", [2.4, 1.6, 4.0], seed=5)
    k1 = f.frames[0]
    ob = annotate(k1, v, seed=3)
    pts, z = project(v.pose, v.intrinsics, [[3.4, 2.0, 0.8], [4.2, 2.0, 0.8]])
    ref = dict(reference_id="RW", p1_px=pts[0], p2_px=pts[1], distance_m=0.8, distance_sigma_m=0.005, plane_id="P")
    r = measure_with_reference(v, ob.corners_px, ref, CFG, seed=1)
    assert not r.ok and "REFERENCE_PLANE_MISMATCH" in codes(r.flags) and r.width_m is None
    # expliciet ander vlak-id zonder diepte
    v0 = make_view(f, "FW0", [2.4, 1.6, 4.0], seed=5, with_depth=False)
    r2 = measure_with_reference(v0, annotate(k1, v0, seed=3).corners_px, dict(ref, plane_id="P1", target_plane_id="P2"), CFG, seed=1)
    assert "REFERENCE_PLANE_MISMATCH" in codes(r2.flags) and r2.width_m is None


# 10 --------------------------------------------------------------------------
def test_10_depth_with_holes(facade):
    fr = facade.frames[0]
    v = make_view(facade, "FH", [1.6, 1.6, 4.0], seed=1, hole_p=0.30)
    r = measure_depth_view(v, annotate(fr, v, seed=3).corners_px, CFG, seed=1)
    assert r.ok and near(r.width_m, r.height_m, fr, 0.03)           # matige gaten: nog steeds goed
    v = make_view(facade, "FH2", [1.6, 1.6, 4.0], seed=1, hole_p=0.93)
    r = measure_depth_view(v, annotate(fr, v, seed=3).corners_px, CFG, seed=1)
    assert not r.ok and r.width_m is None and "DEPTH_COVERAGE_LOW" in codes(r.flags)
    assert any("Ga dichterbij" in f["instruction_nl"] for f in r.flags)


# 11 --------------------------------------------------------------------------
def test_11_tracking_loss(facade):
    fr = facade.frames[0]
    v = make_view(facade, "FT", [1.6, 1.6, 4.0], seed=1, tracking="LIMITED_EXCESSIVE_MOTION")
    ob = annotate(fr, v, seed=3)
    r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
    assert r.width_m is None and "TRACKING_LOST" in codes(r.flags)
    o = process_session(session(), [v], [ob])["objects"][0]
    assert o["dimension_status"] == "UNKNOWN" and o["gross_area_m2"] is None and o["observation_refs"] == [ob.observation_id]


# 12 --------------------------------------------------------------------------
def test_12_reflective_glass(facade):
    f = standard_facade("reflect")
    fr = f.frames[0]
    va, vb = make_view(f, "F0", [1.6, 1.6, 4.0], seed=1), make_view(f, "F1", [2.6, 1.6, 4.0], yaw_deg=8, seed=2)
    oa, ob_ = annotate(fr, va, seed=3), annotate(fr, vb, seed=4)
    r = measure_depth_view(va, oa.corners_px, CFG, seed=1)
    assert r.ok and near(r.width_m, r.height_m, fr, 0.03)           # plane uit omringende gevel, niet uit het glas
    assert "GLASS_DEPTH_UNRELIABLE" in codes(r.flags)
    o = process_session(session(), [va, vb], [oa, ob_])["objects"][0]
    assert o["dimension_status"] != "MEASURED" and o["review_required"]


# 13 --------------------------------------------------------------------------
def test_13_wrong_corner_order(facade, v1):
    fr = facade.frames[0]
    ob = annotate(fr, v1, seed=3)
    swapped = ob.corners_px[[0, 1, 3, 2]]                        # vlinderdas
    r = measure_depth_view(v1, swapped, CFG, seed=1)
    assert r.width_m is None and "CORNER_ORDER_INVALID" in codes(r.flags)
    rot = ob.corners_px[[3, 0, 1, 2]]                           # 90 graden gedraaide startpositie: maten niet verwisseld
    rr = measure_depth_view(v1, rot, CFG, seed=1)
    assert rr.ok and near(rr.width_m, rr.height_m, fr)
    skew = ob.corners_px.copy(); skew[2] += [90, -60]            # niet-rechthoekige selectie
    assert "WRONG_CORNER_SELECTION" in codes(measure_depth_view(v1, skew, CFG, seed=1).flags)


# 14 --------------------------------------------------------------------------
def test_14_one_frame_in_multiple_images_counts_once(facade):
    views = [make_view(facade, f"F{i}", [x, 1.6, 4.0], seed=i) for i, x in enumerate([0.6, 1.4, 2.2])]
    fr = facade.frames[0]
    obs = [annotate(fr, v, seed=20 + i) for i, v in enumerate(views)]
    assert all(o is not None for o in obs)
    res = process_session(session(), views, obs)
    assert len(res["objects"]) == 1 and len(res["objects"][0]["observation_refs"]) == 3
    assert res["summary"]["by_status"]["MEASURED"]["count"] == 1
    assert abs(float(res["summary"]["by_status"]["MEASURED"]["gross_area_m2"]) - 1.8) < 0.05
    # twee verschillende kozijnen in dezelfde beelden blijven apart
    both = obs + [annotate(facade.frames[1], v, seed=30 + i) for i, v in enumerate(views)]
    both = [o for o in both if o is not None]
    assert len(process_session(session(), views, both)["objects"]) == 2


# 15 --------------------------------------------------------------------------
def test_15_inconsistent_between_viewpoints(facade, v1, v2):
    fr = facade.frames[0]
    a, b = annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)
    b.corners_px[1] += [60, 0]; b.corners_px[2] += [60, 0]        # rechterrand 60 px verschoven in standpunt 2
    res = process_session(session(), [v1, v2], [a, b])
    o = res["objects"][0]
    assert o["dimension_status"] == "UNKNOWN" and o["outer_width_m"] is None
    assert "VIEWS_INCONSISTENT" in {f["code"] for f in o["quality_flags"]}
    assert len(o["observation_refs"]) == 2                            # waarnemingen blijven bewaard


# 16 --------------------------------------------------------------------------
def test_16_missing_metric_scale(facade):
    f = facade
    fr = f.frames[0]
    mode = determine_measurement_mode(CAP_NONE)
    assert mode["primary_level"] == "C"
    v = make_view(f, "FN", [1.6, 1.6, 4.0], seed=1, with_depth=False)
    v.pose_valid = False
    res = process_session(session(CAP_NONE), [v], [annotate(fr, v, seed=3)])
    o = res["objects"][0]
    assert o["dimension_status"] == "UNKNOWN" and o["outer_width_m"] is None and o["gross_area_m2"] is None
    assert "NO_METRIC_SCALE" in {x["code"] for x in o["quality_flags"]}
    assert any("referentie" in s.lower() for s in o["next_steps_nl"])
    # tracking die geen metrische schaal declareert: niveau B levert alleen een verhouding, geen meters
    vb = [make_view(f, "B0", [1.6, 1.6, 4.0], seed=1, with_depth=False), make_view(f, "B1", [0.2, 1.6, 4.0], seed=2, with_depth=False)]
    rb = measure_triangulated(vb, [annotate(fr, v, seed=3 + i).corners_px for i, v in enumerate(vb)], CFG, seed=1, metric_scale_trusted=False)
    assert rb.width_m is None and "NO_METRIC_SCALE" in codes(rb.flags) and abs(rb.aspect_ratio - fr.width / fr.height) < 0.03


# 17 --------------------------------------------------------------------------
def test_17_manually_corrected_corner(facade, v1, v2):
    fr = facade.frames[0]
    a, b = annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)
    orig = a.corners_px.copy()
    bad = correct_corner(a, 2, a.corners_px[2] + [10, 8], "tester", "2026-01-01T00:00:00Z")    # (kunstmatig 'fout' via correctie)
    fixed = correct_corner(bad, 2, orig[2], "tester", "2026-01-01T00:01:00Z", "terug naar juiste hoek")
    assert np.allclose(a.corners_px, orig) and np.allclose(fixed.original_corners_px, orig)           # brondata niet overschreven
    assert [r["revision"] for r in fixed.revisions] == [1, 2] and fixed.corner_source == "MANUAL_CORRECTED"
    r_bad = process_session(session(), [v1, v2], [bad, b])["objects"][0]
    r_fix = process_session(session(), [v1, v2], [fixed, b])["objects"][0]
    assert "HUMAN_CORRECTED_CORNERS" in {x["code"] for x in r_fix["quality_flags"]}
    assert r_fix["corner_pixels"][0]["original_points"] == [[round(float(x), 2) for x in p] for p in orig]
    assert r_fix["outer_width_m"] is not None and abs(float(r_fix["outer_width_m"]) - fr.width) < 0.03
    rec = build_record(session(), [v1, v2], [fixed, b], [], process_session(session(), [v1, v2], [fixed, b]))
    assert rec["scan_label"] == "SEMI_AUTOMATIC"            # geen claim van automatische herkenning


# 18 --------------------------------------------------------------------------
def test_18_no_unauthorized_final_quantities(facade, v1, v2):
    fr = facade.frames[0]
    obs = [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)]
    res = process_session(session(), [v1, v2], obs)
    rec = build_record(session(), [v1, v2], obs, [], res)
    inv = rec["invariants"]
    assert inv["is_final"] is False and inv["human_decision_registered"] is False and inv["approvals_simulated"] is False
    assert inv["cost_link"] is None and inv["kengetal_link"] is None and inv["price_link"] is None
    for o in rec["objects"]:
        assert o["quantity_layer"] == "PROVISIONAL" and o["approval_state"] == "PENDING_HUMAN_APPROVAL"
    for mutate in (lambda r: r["invariants"].update(is_final=True), lambda r: r["objects"][0].update(quantity_layer="CONFIRMED"),
                   lambda r: r["objects"][0].update(approval_state="APPROVED"), lambda r: r["invariants"].update(cost_link="x")):
        bad = copy.deepcopy(rec)
        mutate(bad)
        assert schema_errors(bad)
    assert not schema_errors(rec)


# 19 --------------------------------------------------------------------------
FORBIDDEN = {"socket", "requests", "urllib", "urllib3", "http", "httpx", "aiohttp", "anthropic", "openai", "boto3", "google", "ftplib", "smtplib",
             "subprocess", "websocket", "websockets", "grpc"}


def test_19_no_external_vision_calls(facade, v1, v2, monkeypatch):
    pkg = Path(photo_walk_core.__file__).parent
    for p in pkg.glob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            mods = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else [n.module.split(".")[0]] if isinstance(n, ast.ImportFrom) and n.module else []
            assert not (set(mods) & FORBIDDEN), f"{p.name} importeert {set(mods) & FORBIDDEN}"

    def boom(*a, **k):
        raise AssertionError("netwerkgebruik tijdens de meting")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    fr = facade.frames[0]
    obs = [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)]
    res = process_session(session(), [v1, v2], obs)
    assert res["invariants"]["external_vision_calls"] == 0 and res["invariants"]["images_uploaded"] is False


# 20 --------------------------------------------------------------------------
def test_20_reproducible_results(facade):
    def run():
        views = [make_view(facade, f"F{i}", [x, 1.6, 4.0], seed=i) for i, x in enumerate([0.6, 1.4, 2.2, 3.4])]
        obs = [o for v in views for k, fr in enumerate(facade.frames) for o in [annotate(fr, v, seed=20 + k)] if o]
        res = process_session(session(), views, obs)
        return record_sha256(build_record(session(), views, obs, [], res))
    assert run() == run()


# ---------------------------------------------------------------- aanvullende tests

def test_measurement_mode_selection_lidar_never_required():
    assert determine_measurement_mode(CAP_LIDAR)["primary_level"] == "A"
    assert determine_measurement_mode(CAP_AR_ONLY)["primary_level"] == "B"
    assert determine_measurement_mode(CAP_NONE)["fallback_chain"] == ["C"]
    assert determine_measurement_mode({"depth_api": True, "ar_world_tracking": True})["primary_level"] == "A"     # ARCore Depth API


def test_level_b_unverified_is_estimate_and_reference_verifies_scale(facade):
    fr = facade.frames[0]
    views = [make_view(facade, "B0", [2.4, 1.6, 4.0], seed=1, with_depth=False), make_view(facade, "B1", [3.4, 1.6, 4.0], yaw_deg=6, seed=2, with_depth=False)]
    obs = [annotate(fr, v, seed=3 + i) for i, v in enumerate(views)]
    o = process_session(session(CAP_AR_ONLY), views, obs)["objects"][0]
    assert o["dimension_status"] == "ESTIMATED" and o["measurement_source"]["level"] == "B"
    assert "METRIC_SCALE_UNVERIFIED" in {f["code"] for f in o["quality_flags"]}
    assert abs(float(o["outer_width_m"]) - fr.width) < 0.03
    k2 = facade.frames[1]
    ob2 = annotate(k2, views[0], seed=9)
    ref = dict(reference_id="R", frame_id="B0", p1_px=ob2.corners_px[0], p2_px=ob2.corners_px[1], distance_m=k2.width, distance_sigma_m=0.005, plane_id="P")
    o2 = process_session(session(CAP_AR_ONLY), views, obs, references=[ref])["objects"][0]
    assert o2["dimension_status"] == "DERIVED" and o2["measurement_source"]["scale_evidence"]["verified_by_reference"] is True


def test_level_b_scale_mismatch_uses_reference_and_flags(facade):
    """AR-schaal 15% te groot (gesimuleerde drift): de referentie is leidend en de afwijking wordt gemeld."""
    fr = facade.frames[0]
    s = 1.15
    raw = [make_view(facade, "B0", [2.4, 1.6, 4.0], seed=1, with_depth=False), make_view(facade, "B1", [3.4, 1.6, 4.0], yaw_deg=6, seed=2, with_depth=False)]
    obs = [annotate(fr, v, seed=3 + i) for i, v in enumerate(raw)]
    k2 = facade.frames[1]
    ob2 = annotate(k2, raw[0], seed=9)
    for v in raw:
        v.pose = v.pose.copy(); v.pose[:3, 3] *= s
    ref = dict(reference_id="R", frame_id="B0", p1_px=ob2.corners_px[0], p2_px=ob2.corners_px[1], distance_m=k2.width, distance_sigma_m=0.005, plane_id="P",
               anchor_px=ob2.corners_px)
    o = process_session(session(CAP_AR_ONLY), raw, obs, references=[ref])["objects"][0]
    assert o["measurement_source"]["level"] == "C" and o["dimension_status"] == "DERIVED"
    assert abs(float(o["outer_width_m"]) - fr.width) < 0.05
    assert o["measurement_source"]["scale_evidence"]["kind"] == "REFERENCE_DISTANCE"


def test_oblique_angle_and_range_gates(facade):
    fr = facade.frames[0]
    v = make_view(facade, "FOB", [8.0, 1.6, 1.5], yaw_deg=60, seed=3)
    ob = annotate(fr, v, seed=3)
    if ob is not None:
        r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
        assert r.width_m is None
    far = make_view(facade, "FFAR", [3.0, 1.6, 9.0], seed=3)
    r = measure_depth_view(far, annotate(fr, far, seed=3).corners_px, CFG, seed=1)
    assert r.width_m is None and ({"DEPTH_COVERAGE_LOW", "DEPTH_RANGE_EXCEEDED"} & codes(r.flags))


def test_mixed_facade_depth_blocks(facade):
    f = SimFacade(frames=facade.frames, protrusions=[(0.2, 1.0, 0.0, 3.0, 0.7), (2.2, 3.0, 0.0, 3.0, 0.7), (1.0, 2.2, 2.45, 3.0, 0.7)])
    v = make_view(f, "FM", [1.6, 1.6, 4.0], seed=1)
    r = measure_depth_view(v, annotate(f.frames[0], v, seed=3).corners_px, CFG, seed=1)
    assert r.width_m is None and codes(r.flags) & {"MIXED_FACADE_DEPTH", "PLANE_NOISY"}


def test_unknown_keeps_observation_and_gives_instruction(facade):
    fr = facade.frames[0]
    v = make_view(facade, "FU", [1.6, 1.6, 4.0], seed=1, tracking="NOT_AVAILABLE")
    o = process_session(session(), [v], [annotate(fr, v, seed=3)])["objects"][0]
    assert o["dimension_status"] == "UNKNOWN" and o["next_steps_nl"] and o["review_required"] and o["corner_pixels"]


def test_summary_keeps_statuses_separate(facade, v1, v2):
    fr = facade.frames[0]
    v3 = make_view(facade, "F3", [6.4, 1.6, 4.0], seed=3)
    res = process_session(session(), [v1, v2, v3], [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4), annotate(facade.frames[2], v3, seed=5)])
    s = res["summary"]
    assert s["by_status"]["MEASURED"]["count"] == 1 and s["by_status"]["ESTIMATED"]["count"] == 1     # K3 maar 1 standpunt
    assert "niet worden opgeteld" in s["note"]


def test_schema_is_closed_and_valid(facade, v1, v2):
    import jsonschema
    from photo_walk_core.contract import load_schema
    jsonschema.Draft7Validator.check_schema(load_schema())
    fr = facade.frames[0]
    obs = [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)]
    rec = build_record(session(), [v1, v2], obs, [], process_session(session(), [v1, v2], obs))
    for extra in ({"surprise": 1},):
        bad = {**rec, **extra}
        assert schema_errors(bad)
    bad = copy.deepcopy(rec); bad["image_refs"][0]["ref"] = "/home/x/foto.jpg"
    assert schema_errors(bad)
    bad = copy.deepcopy(rec); bad["objects"][0]["measurement_uncertainty"]["validated"] = True
    assert schema_errors(bad)
    bad = copy.deepcopy(rec); bad["objects"][0]["dimension_status"] = "UNKNOWN"
    assert schema_errors(bad)       # UNKNOWN mag geen schijnnauwkeurige waarde hebben


def test_export_refuses_repo_and_real_data_in_repo(facade, v1, v2, tmp_path):
    fr = facade.frames[0]
    obs = [annotate(fr, v1, seed=3), annotate(fr, v2, seed=4)]
    rec = build_record(session(), [v1, v2], obs, [], process_session(session(), [v1, v2], obs))
    with pytest.raises(ValueError):
        export_record(rec, Path(photo_walk_core.__file__).parent / "out")
    jp, cp = export_record(rec, tmp_path)
    assert json.loads(jp.read_text())["contract"] == "photo_walk_capture_v1" and "UNKNOWN" not in cp.read_text().split("\n")[1]
    real = dict(rec, data_origin="REAL_SENSOR")
    with pytest.raises(ValueError):
        export_record(real, Path(photo_walk_core.__file__).parents[2] / "examples", allow_in_repo=True)


def test_coverage_guidance_for_unseen_and_low_overlap(facade):
    from photo_walk_core.coverage import facade_coverage
    views = [make_view(facade, "C0", [1.0, 1.6, 4.0], seed=1, with_depth=False), make_view(facade, "C1", [9.0, 1.6, 4.0], seed=2, with_depth=False)]
    cov = facade_coverage(views, [0, 0, 1.0], 0.0, (0.0, 10.5, 0.0, 3.0), CFG)
    assert cov["coverage_fraction"] < 1.0 and cov["guidance_nl"]
    assert any("niet gezien" in g for g in cov["guidance_nl"]) and any("overlap" in g.lower() for g in cov["guidance_nl"])


def test_association_ambiguity_and_unverified_without_world_position(facade):
    # zonder dieptemeting en zonder triangulatie kan niet worden gekoppeld: gemeld, niet verzwegen
    views = [make_view(facade, f"N{i}", [x, 1.6, 4.0], seed=i, with_depth=False) for i, x in enumerate([1.2, 1.6])]
    for v in views:
        v.pose_valid = False
    fr = facade.frames[0]
    obs = [annotate(fr, v, seed=3 + i) for i, v in enumerate(views)]
    res = process_session(session(CAP_NONE), views, obs)
    assert len(res["objects"]) == 2
    assert all("ASSOCIATION_UNVERIFIED" in {f["code"] for f in o["quality_flags"]} for o in res["objects"])


def test_no_media_or_coordinates_of_real_buildings_committed():
    root = Path(photo_walk_core.__file__).resolve().parents[2]
    bad = [p for p in root.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic", ".mov", ".mp4", ".usdz", ".ply", ".bin", ".f32", ".depth"}]
    assert not bad, bad


def test_parity_fixture_is_current_with_python_core():
    """De Swift-pariteitsfixture moet de actuele Python-uitkomsten bevatten (numeriek, niet tekstueel)."""
    from photo_walk_core import parity
    cur, committed = parity.build(), json.loads(parity.FIXTURE.read_text())
    for k in ("expect_width_m", "expect_height_m"):
        assert abs(cur["level_a"][k] - committed["level_a"][k]) < 1e-6 and abs(cur["level_c"][k] - committed["level_c"][k]) < 1e-6
    assert cur["area"] == committed["area"] and cur["flag_instructions"] == committed["flag_instructions"]
    assert cur["unproject"] == committed["unproject"] and cur["project"] == committed["project"]


def test_committed_examples_validate_and_are_synthetic():
    ex = Path(photo_walk_core.__file__).resolve().parents[2] / "examples"
    for p in ex.glob("*.json"):
        rec = json.loads(p.read_text())
        assert not schema_errors(rec) and rec["data_origin"] == "SIMULATION" and rec["validation_level"] == "SIMULATED"


def test_swift_flag_table_is_subset_of_python_flags():
    swift = (Path(photo_walk_core.__file__).resolve().parents[2] / "ios" / "Sources" / "PhotoWalkCore" / "Quality.swift").read_text()
    import re
    for code in re.findall(r'^\s+"([A-Z_]+)": \(\.(?:BLOCKING|ADVISORY),', swift, flags=re.M):
        assert code in q.FLAGS, code
