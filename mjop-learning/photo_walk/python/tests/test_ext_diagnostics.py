"""Uitgebreide meetdiagnose 1.1.0: bewijs dat de meetuitkomst identiek blijft, dat het blok geldig/privacyveilig/deterministisch is en dat de schaduwevaluatie
overeenkomt met de echte poorten. Inclusief scenes met BEPERKTE opnameafstand, close-ups, schuine opnamen en zonder diepte (referentiemaat)."""
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scenes import build
from photo_walk_core import diagnostics as dg
from photo_walk_core import ext_diagnostics as ed
from photo_walk_core.config import DEFAULT as CFG
from photo_walk_core.levels import measure_depth_view

PY = Path(__file__).resolve().parents[1]
FACADE_CODES = {"AMBIGUOUS_FACADE_PLANES", "FACADE_NOT_PLANAR", "FACADE_ONE_SIDED", "NO_FACADE_PLANE", "FACADE_NOT_REPRESENTATIVE"}

SCENES = {
    "flat": dict(),
    "recess6_frames": dict(recess=0.06, extra_frames=3),
    "recess12": dict(recess=0.12),
    "sill": dict(sill=True),
    "relief3cm": dict(relief=0.03),
    "pier_one_side": dict(protrusions=[(0.2, 0.9, 0.0, 3.0, 0.15)]),
    "pier_two_sides": dict(protrusions=[(0.2, 0.9, 0.0, 3.0, 0.15), (2.3, 3.0, 0.0, 3.0, 0.15)]),
    "glass_reflect": dict(glass_mode="reflect"),
    "glass_holes": dict(glass_mode="holes"),
    "no_baseline_frames": dict(extra_frames=3, spacing=0.0),
    "bad_tracking": dict(tracking="LIMITED_EXCESSIVE_MOTION"),
    "oblique25": dict(pos=(1.6 + 3.0 * math.tan(math.radians(25)), 1.6, 3.0), yaw=25),
    # BEPERKTE opnameafstand (geen verplichte 2,5-3 m): kozijn vult het beeld, de ring valt deels buiten beeld
    "limited_1p75m": dict(pos=(1.6, 1.65, 1.75)),
    "limited_1p8m_recess": dict(pos=(1.6, 1.65, 1.8), recess=0.06, extra_frames=2),
    # beperkte afstand EN schuin (smalle tuin: je kunt alleen langs de gevel bewegen)
    "limited_oblique30_2m": dict(pos=(1.6 + 2.0 * math.tan(math.radians(30)), 1.65, 2.0), yaw=30),
    # close-up van het glas/profiel op korte afstand
    "closeup_glass_1p5m": dict(pos=(1.6, 1.6, 1.5), quad="glass"),
    "glass_quad_3m": dict(quad="glass"),
}


def scene(name):
    s = build(**SCENES[name])
    return s if s["corners"] is not None else None


def measure(s, **kw):
    return measure_depth_view(s["cap"], s["corners"], CFG, seed=1, supports=tuple(s["extras"]), **kw)


def snapshot(r):
    """Alles wat een meetuitkomst vormt, canoniek geserialiseerd."""
    d = {"ok": r.ok, "w": r.width_m, "h": r.height_m, "sw": r.sigma_w, "sh": r.sigma_h, "sa": r.sigma_area, "scale": r.scale_method, "indep": r.independent_frames,
         "flags": r.flags, "diag": r.diag, "cw": None if r.corners_w is None else r.corners_w.tolist(), "pn": None if r.plane_n is None else r.plane_n.tolist(), "pd": r.plane_d}
    return json.dumps(dg.json_safe(d), sort_keys=True)


def input_hash(s):
    h = hashlib.sha256()
    for v in [s["cap"]] + list(s["extras"]):
        h.update(v.pose.tobytes()); h.update(b"" if v.depth is None else v.depth.tobytes()); h.update(v.tracking_state.encode())
    h.update(np.asarray(s["corners"], float).tobytes())
    return h.hexdigest()


def compute(s, r, **kw):
    return ed.compute(s["cap"], s["corners"], r, cfg=CFG, seed=1, supports=tuple(s["extras"]), **kw)


@pytest.mark.parametrize("name", list(SCENES))
def test_measurement_outcome_is_identical_with_and_without_extended_diagnostics(name):
    s = scene(name)
    if s is None:
        pytest.skip("kader valt buiten het beeld in deze scene")
    h0 = input_hash(s)
    r_without = measure(s)                                  # 1) zonder extra diagnoseberekening
    snap_without = snapshot(r_without)
    ext = compute(s, r_without, contour_status="USER_CONFIRMED")   # 2) extra diagnose NA het resultaat
    assert snapshot(r_without) == snap_without              # resultaat niet gemuteerd door de extra diagnose
    assert input_hash(s) == h0                              # invoer (poses, diepte, hoeken) niet gemuteerd
    r_with = measure(s)                                     # 3) opnieuw meten na de extra diagnose
    assert snapshot(r_with) == snap_without                 # bit-identieke meetuitkomst en diagnostiek
    assert ext["computed_after_result"] is True


def test_measurement_outcome_is_identical_over_a_random_sweep():
    rng = np.random.default_rng(7)
    n_ok = 0
    for k in range(24):
        kw = dict(recess=float(rng.choice([0, 0.03, 0.08, 0.12])), relief=float(rng.choice([0, 0.01, 0.03])), noise=float(rng.choice([0.003, 0.005, 0.008])),
                  sill=bool(rng.random() < 0.3), pos=(float(rng.uniform(1.2, 2.2)), 1.6, float(rng.choice([1.6, 2.0, 2.6, 3.4, 4.2]))),
                  yaw=float(rng.choice([0, 10, 25])), seed=int(k + 1), extra_frames=int(rng.choice([0, 2, 3])))
        s = build(**kw)
        if s["corners"] is None:
            continue
        a = snapshot(measure(s)); r = measure(s)
        compute(s, r)
        assert snapshot(measure(s)) == a
        n_ok += 1
    assert n_ok >= 12


@pytest.mark.parametrize("name", ["flat", "recess6_frames", "pier_one_side", "limited_1p75m", "oblique25", "limited_oblique30_2m"])
def test_diagnostics_record_1_1_0_only_adds_a_block(name):
    s = scene(name)
    if s is None:
        pytest.skip("geen kader")
    r = measure(s)
    kw = dict(session_id="SYN", observation_id="O1", view=s["cap"], corners_px=s["corners"], status="UNKNOWN", feedback="orange", created_utc="2026-01-01T00:00:00Z")
    old = dg.build(r, **kw)
    ext = compute(s, r, contour_status="UNVERIFIED")
    new = dg.build(r, **kw, extended=ext)
    assert old["contract_version"] == "1.0.0" and new["contract_version"] == "1.1.0"
    assert dg.schema_errors(old) == [] and dg.schema_errors(new) == []
    a, b = copy.deepcopy(old), copy.deepcopy(new)
    b.pop("extended_diagnostics"); b["contract_version"] = "1.0.0"
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)          # alle bestaande velden en waarden ongewijzigd
    assert dg.forbidden_key_paths(new) == []
    text = json.dumps(new)
    assert len(text) < 150_000
    assert all(new["privacy"][k] is False for k in new["privacy"])
    for k in ("image_ref", "depth_ref", "latitude", "longitude", "gps"):
        assert k not in text


def test_schema_rejects_extended_block_with_old_contract_version():
    s = scene("flat"); r = measure(s)
    rec = dg.build(r, session_id="SYN", observation_id="O1", view=s["cap"], corners_px=s["corners"], status="UNKNOWN", feedback="orange", extended=compute(s, r))
    rec["contract_version"] = "1.0.0"
    assert dg.schema_errors(rec) != []


@pytest.mark.parametrize("name", [n for n in SCENES if n != "bad_tracking"])
def test_extended_block_is_deterministic(name):
    s = scene(name)
    if s is None:
        pytest.skip("geen kader")
    r = measure(s)
    a = json.dumps(dg.json_safe(compute(s, r, contour_status="USER_CONFIRMED")), sort_keys=True)
    b = json.dumps(dg.json_safe(compute(s, r, contour_status="USER_CONFIRMED")), sort_keys=True)
    assert a == b


GATE_FLAGS = {"INCIDENCE": {"OBLIQUE_ANGLE"}, "CORNER_DEPTH": {"CORNERS_OFF_PLANE"}, "RECTANGULARITY": {"WRONG_CORNER_SELECTION"},
              "DIMENSION_RANGE": {"DIMENSION_OUT_OF_RANGE"}, "QUAD_EXTENT": {"QUAD_LARGER_THAN_OPENING", "QUAD_INSIDE_OPENING"},
              "GLASS": {"GLASS_DEPTH_UNRELIABLE"}, "FRAMES_CONSISTENCY": {"FRAMES_INCONSISTENT"}}


@pytest.mark.parametrize("name", [n for n in SCENES if n != "bad_tracking"])
def test_shadow_gates_agree_with_the_real_gates(name):
    """Drift-bewaking: de schaduwevaluatie moet dezelfde uitslag geven als de echte meting waar die de poort bereikte."""
    s = scene(name)
    if s is None:
        pytest.skip("geen kader")
    r = measure(s)
    ext = compute(s, r, contour_status="USER_CONFIRMED")
    sh = ext["gates_shadow"]
    assert sh["reproduces_result_planes"] is True
    gates = {g["id"]: g for g in sh["gates"]}
    codes = {f["code"] for f in r.flags}
    blocking = {f["code"] for f in r.flags if f["severity"] == "BLOCKING"}
    # FACADE_SELECTION volgt exact de echte facade-poort
    if gates.get("FACADE_SELECTION"):
        assert (gates["FACADE_SELECTION"]["status"] == "FAIL") == bool(blocking & FACADE_CODES)
    if r.ok:
        assert sh["host_hypothesis"]["source"] == "SELECTED"
        for gid, fl in GATE_FLAGS.items():
            g = gates.get(gid)
            if g is None or g["status"] in ("NOT_APPLICABLE", "NOT_EVALUATED"):
                continue
            assert (g["status"] == "FAIL") == bool(codes & fl), (gid, g, codes)
        fp = gates["FRAME_PLANE"]
        if fp["status"] == "PASS":
            assert not ({"FRAME_PLANE_UNDETERMINED", "FRAME_PLANE_INCONSISTENT"} & codes)
        for gid in ("FACADE_SUPPORT", "FACADE_LOCAL_RMS", "FACADE_LOCAL_ROBUST", "FACADE_UNEXPLAINED", "FACADE_SIDE_COVERAGE", "FACADE_EXTENT", "FACADE_FACING"):
            assert gates[gid]["status"] == "PASS", gid
    else:
        # een blokkade in de eerste poort wordt ook in de schaduw teruggezien, nooit stil overgeslagen
        assert any(g["status"] == "FAIL" for g in sh["gates"]) or blocking - FACADE_CODES


def test_shadow_never_publishes_a_hypothetical_dimension():
    s = scene("pier_two_sides"); r = measure(s)
    ext = compute(s, r)
    text = json.dumps(dg.json_safe(ext["gates_shadow"]))
    assert "width_m" not in text and "height_m" not in text and "area_m2" not in text
    assert ext["gates_shadow"]["host_hypothesis"] is None or "hypothese" in ext["gates_shadow"]["host_hypothesis"]["note"] or ext["gates_shadow"]["host_hypothesis"]["source"] == "SELECTED"


@pytest.mark.parametrize("name", ["limited_1p75m", "limited_1p8m_recess", "limited_oblique30_2m", "closeup_glass_1p5m"])
def test_limited_standoff_is_handled_without_requiring_distance(name):
    """Beperkte opnameafstand: de ring valt deels buiten beeld. De diagnose beschrijft dat (marges, overflow, per zijde), eist geen afstand en crasht niet;
    alle poorten krijgen een uitslag of een uitleg."""
    s = scene(name)
    assert s is not None, "scene moet een geldig kader hebben"
    r = measure(s)
    ext = compute(s, r, contour_status="USER_CONFIRMED")
    fr = ext["framing"]
    assert max(fr["ring_out_overflow_px"].values()) > 0                    # de ring ligt deels buiten het beeld
    assert fr["ring_in_view_fraction"] < 1.0
    assert fr["distance_for_full_ring_m"] > r.diag.get("range_median_m", 0) * 0.99   # informatief getal, geen eis
    assert "geen eis" in fr["note"] and not any(k in fr for k in ("gate", "status", "required"))
    assert all(g["status"] in ("PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE") for g in ext["gates_shadow"]["gates"])
    assert dg.schema_errors(dg.build(r, session_id="S", observation_id="O", view=s["cap"], corners_px=s["corners"], status="UNKNOWN", feedback="orange", extended=ext)) == []


def test_close_up_profile_is_reported_per_distance_bin():
    s = scene("closeup_glass_1p5m")
    r = measure(s)
    ext = compute(s, r)
    dp_ = ext["depth_profiles"]
    assert set(dp_["sides"]) == {"TOP", "RIGHT", "BOTTOM", "LEFT"} and dp_["bin_cm"] == 2.0
    assert any(b["valid"] > 0 for b in dp_["sides"]["LEFT"])
    bins = dp_["sides"]["LEFT"]
    assert bins[0]["from_cm"] == -8.0 and bins[-1]["to_cm"] == 40.0


def test_oblique_capture_lowers_quad_facing_and_changes_nothing_else():
    flat, obl = scene("flat"), scene("oblique25")
    assert obl is not None
    f0 = compute(flat, measure(flat))["quad_from_corners"]["facing"]
    f1 = compute(obl, measure(obl))["quad_from_corners"]["facing"]
    assert f1 < f0 and f0 > 0.98


def test_reference_measure_path_without_depth_is_supported():
    """Referentiemaat (niveau C): geen diepte. De uitgebreide diagnose geeft dan alleen de pose-vrije blokken en loopt niet vast."""
    s = build(with_depth=False)
    r = measure(s)
    ext = compute(s, r)
    assert ext["gates_shadow"] is None and ext["planes_all"] == [] and ext["depth_profiles"] is None and ext["framing"] is None
    assert ext["quad_from_corners"]["aspect_w_over_h"] == pytest.approx(1.2 / 1.5, rel=0.02)
    assert ext["frames"][0]["has_depth"] is False


def test_frames_detail_matches_selection_rule():
    s = scene("no_baseline_frames")
    ext = compute(s, measure(s))
    sup = [f for f in ext["frames"] if f["role"] == "SUPPORT"]
    assert sup and all(f["used"] is False and f["reason"] == "CORRELATED_OR_LIMIT" and f["meets_baseline"] is False and f["meets_rotation"] is False for f in sup)
    s2 = scene("recess6_frames")
    sup2 = [f for f in compute(s2, measure(s2))["frames"] if f["role"] == "SUPPORT"]
    assert any(f["used"] and f["meets_baseline"] for f in sup2)
    s3 = scene("bad_tracking")
    assert compute(s3, measure(s3))["frames"][0]["tracking"] == "LIMITED_EXCESSIVE_MOTION"


def test_camera_gravity_of_a_level_camera():
    s = scene("flat")
    g = compute(s, measure(s))["camera_gravity"]
    assert abs(g["pitch_deg"]) < 0.01 and abs(g["roll_sensor_x_deg"]) < 0.01


def test_edge_ladder_contains_only_numbers_not_the_image():
    h, w = 120, 160
    gray = np.tile(np.linspace(0, 255, w), (h, 1))
    rgb = np.stack([gray, gray * 0.9, gray * 0.8], axis=-1)
    sat = ed.saturation_channel(rgb)
    lad = ed.edge_ladder(gray, sat, [[40, 30], [120, 30], [120, 90], [40, 90]])
    text = json.dumps(lad)
    assert set(lad["sides"]) == {"TOP", "RIGHT", "BOTTOM", "LEFT"}
    assert all(k in lad["sides"]["TOP"] for k in ("offsets_px", "strength_gray", "strength_saturation"))
    assert len(text) < 20_000 and not any(k in text.lower() for k in ("pixels\":", "image", "rgb"))
    assert dg.forbidden_key_paths(lad) == []


def test_gate_constants_are_documented_and_match_the_source():
    py = (PY / "photo_walk_core" / "depth_plane.py").read_text(encoding="utf-8") + (PY / "photo_walk_core" / "levels.py").read_text(encoding="utf-8")
    swift_dir = PY.parent / "ios" / "Sources" / "PhotoWalkCore"
    sw = (swift_dir / "DepthPlane.swift").read_text(encoding="utf-8") + (swift_dir / "LevelA.swift").read_text(encoding="utf-8")
    for g in ed.GATE_CONSTANTS:
        assert g["anchor_py"] in py, g["name"]
        assert g["anchor_swift"] in sw, g["name"]
    names = [g["name"] for g in ed.GATE_CONSTANTS]
    assert len(names) == len(set(names))
    exported = ed.gate_constants_export()
    assert [e["name"] for e in exported] == names and all(isinstance(e["value"], (int, float)) for e in exported)


def test_ext_diag_parity_fixture_is_up_to_date():
    """De Swift-tests lezen ios/Tests/.../ext_diag_parity_cases.json; die moet exact uit de Python-referentie komen (regenereren: python -m photo_walk_core.ext_diag_parity)."""
    from photo_walk_core import ext_diag_parity
    assert ext_diag_parity.main.__module__ == "photo_walk_core.ext_diag_parity"
    text = json.dumps(ext_diag_parity.build(), sort_keys=True, indent=0) + "\n"
    assert ext_diag_parity.OUT.read_text() == text
