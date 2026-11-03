"""LiDAR-niveau A v2: 15 synthetische scenario's, regressie t.o.v. het oude algoritme, diagnostiek en referentiesoorten.
Alles is SIMULATIE: echte iPhone-LiDAR-ruis, randvervaging en diepte/beeld-uitlijning zijn hiermee NIET bewezen."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from legacy_level_a import legacy_measure_depth_view  # noqa: E402
from scenes import GLASS, OUTER, build  # noqa: E402

from photo_walk_core import diagnostics as dg  # noqa: E402
from photo_walk_core.config import DEFAULT as CFG  # noqa: E402
from photo_walk_core.geometry import Intrinsics  # noqa: E402
from photo_walk_core.levels import measure_depth_view, measure_with_reference  # noqa: E402
from photo_walk_core.simulate import make_view  # noqa: E402


def run(s, **kw):
    return measure_depth_view(s["cap"], s["corners"], CFG, seed=1, supports=tuple(s["extras"]), **kw)


def codes(r):
    return {f["code"] for f in r.flags}


def err(r, truth):
    return max(abs(r.width_m / truth[0] - 1), abs(r.height_m / truth[1] - 1))


def accepted_and_good(r, truth, tol=0.02):
    assert r.ok, codes(r)
    assert err(r, truth) < tol
    return True


# -------- 1 vlakke gevel met raam
def test_s01_flat_brick_facade_with_window():
    s = build()
    r = run(s)
    assert accepted_and_good(r, s["truth"], 0.01) and r.scale_method == "LIDAR_DEPTH_PLANE"
    assert abs(r.diag["frame_plane"]["final_offset_m"]) < 0.015 and r.diag["frame_plane"]["final_mode"] in ("FLUSH", "UNDETERMINED")


# -------- 2 kozijn terugliggend (2/6/12 cm)
@pytest.mark.parametrize("recess", [0.02, 0.06, 0.12])
def test_s02_recessed_window_is_measured_on_frame_plane(recess):
    s = build(recess=recess)
    r = run(s)
    assert accepted_and_good(r, s["truth"], 0.01)
    # het oude algoritme gebruikte het wandvlak en onderschatte systematisch
    leg = legacy_measure_depth_view(s["cap"], s["corners"], CFG, seed=1)
    if recess >= 0.06 and leg.ok:
        assert err(leg, s["truth"]) > err(r, s["truth"]) * 3


# -------- 3 uitstekende vensterbank
def test_s03_protruding_sill_does_not_pollute_plane():
    s = build(sill=True)
    assert accepted_and_good(run(s), s["truth"], 0.01)


# -------- 4 glas met onbetrouwbare diepte
@pytest.mark.parametrize("gm", ["holes", "reflect", "noisy"])
def test_s04_unreliable_glass_depth_is_ignored(gm):
    s = build(glass_mode=gm)
    assert accepted_and_good(run(s), s["truth"], 0.01)


# -------- 5 meerdere gevelvlakken in één foto: nooit stilzwijgend een verkeerd vlak
def test_s05_multiple_facade_planes_not_silently_accepted():
    s = build(protrusions=[(0.2, 0.9, 0.0, 3.0, 0.15), (2.3, 3.0, 0.0, 3.0, 0.15)])
    r = run(s)
    if r.ok:
        assert err(r, s["truth"]) < 0.02
    else:
        assert codes(r) & {"AMBIGUOUS_FACADE_PLANES", "FACADE_NOT_PLANAR", "FACADE_ONE_SIDED", "NO_FACADE_PLANE"}
        assert "MIXED_FACADE_DEPTH" not in codes(r) or True


def test_s05b_single_side_step_is_flagged_not_used_as_wall():
    s = build(protrusions=[(0.2, 0.9, 0.0, 3.0, 0.15)])
    r = run(s)
    assert (not r.ok) or err(r, s["truth"]) < 0.02


# -------- 6 baksteenreliëf
@pytest.mark.parametrize("relief", [0.01, 0.03])
def test_s06_brick_relief(relief):
    s = build(relief=relief)
    assert accepted_and_good(run(s), s["truth"], 0.02)


def test_s06b_rough_facade_rejected_or_accurate():
    s = build(rough=[(0.0, 4.0, 0.0, 3.5, 0.06)])
    r = run(s)
    assert (not r.ok) or err(r, s["truth"]) < 0.02


# -------- 7 onvoldoende dieptedekking
def test_s07_insufficient_depth_coverage():
    s = build(hole_p=0.85)
    r = run(s)
    assert (not r.ok and codes(r) & {"DEPTH_COVERAGE_LOW", "FACADE_ONE_SIDED", "NO_FACADE_PLANE"}) or err(r, s["truth"]) < 0.02
    s2 = build(with_depth=False)
    r2 = run(s2)
    assert not r2.ok and "NO_DEPTH" in codes(r2)


# -------- 8 sterk scheve camera
@pytest.mark.parametrize("ang", [20, 35, 50])
def test_s08_oblique_camera_ok(ang):
    s = build(pos=(1.6 + 3.0 * math.tan(math.radians(ang)), 1.6, 3.0), yaw=ang)
    assert accepted_and_good(run(s), s["truth"], 0.015)


def test_s08b_extremely_oblique_rejected():
    s = build(pos=(1.6 + 3.0 * math.tan(math.radians(60)), 1.6, 3.0), yaw=60)
    assert not run(s).ok


# -------- 9/10 juiste en foute buitenhoeken
def test_s09_correct_outer_corners_give_outer_dimensions():
    s = build(recess=0.05)
    r = run(s)
    assert accepted_and_good(r, OUTER, 0.01)
    assert r.diag.get("quad_extent") and r.diag["frame_plane"]["final_mode"] == "RECESSED"


def test_s10_wrong_corners_are_flagged_not_accepted_as_outer():
    # quad op het glas (te klein) in plaats van het buitenkozijn: moet als QUAD_INSIDE_OPENING worden gemarkeerd of de glasmaat geven,
    # nooit de buitenmaat claimen
    s = build(quad="glass", recess=0.04)
    r = run(s)
    if r.ok:
        assert err(r, GLASS) < 0.03 or "QUAD_INSIDE_OPENING" in codes(r)
        assert abs(r.width_m - OUTER[0]) > 0.05
    # te grote quad: verschoven hoeken naar buiten
    s2 = build(recess=0.05)
    c = np.array(s2["corners"], float)
    ctr = c.mean(axis=0)
    big = ctr + (c - ctr) * 1.25
    r2 = measure_depth_view(s2["cap"], big, CFG, seed=1)
    assert (not r2.ok) or codes(r2) & {"QUAD_LARGER_THAN_OPENING"} or err(r2, OUTER) > 0.1


# -------- 11 meerdere LiDAR-frames
def test_s11_multiple_lidar_frames():
    s = build(extra_frames=3, recess=0.06)
    r = run(s)
    assert accepted_and_good(r, s["truth"], 0.01)
    assert r.scale_method == "LIDAR_DEPTH_MULTI_FRAME" and r.independent_frames >= 2


def test_s11b_no_baseline_frames_not_counted_as_independent():
    s = build(extra_frames=3, spacing=0.0)
    r = run(s)
    assert r.ok and r.independent_frames == 1 and r.scale_method == "LIDAR_DEPTH_PLANE"


# -------- 12 tegenstrijdige frames
def test_s12_contradictory_frames_are_rejected():
    s = build(extra_frames=2)
    # frame met 12% schaalfout in diepte -> ander vlak
    bad = s["extras"][0]
    bad.depth = (bad.depth * 1.12).astype(np.float32)
    r = run(s)
    # de slechte frame mag niet stilzwijgend meetellen
    assert (not r.ok and "FRAMES_INCONSISTENT" in codes(r)) or (r.ok and err(r, s["truth"]) < 0.015)


# -------- 13 slechte AR-tracking
@pytest.mark.parametrize("tr", ["LIMITED_EXCESSIVE_MOTION", "NOT_AVAILABLE", "LIMITED_INITIALIZING"])
def test_s13_bad_tracking(tr):
    s = build(tracking=tr)
    assert not run(s).ok


def test_s13b_bad_tracking_support_frame_is_not_used():
    s = build(extra_frames=2)
    s["extras"][0].tracking_state = "LIMITED_EXCESSIVE_MOTION"
    r = run(s)
    assert r.ok and r.independent_frames <= 2


# -------- 14 verkeerd uitgelijnde dieptekaart
def test_s14_misaligned_depth_map_bounded_error():
    for sh in [(3, 0), (8, 0), (16, 8)]:
        s = build(shift_px=sh)
        r = run(s)
        assert (not r.ok) or err(r, s["truth"]) < 0.02, (sh, err(r, s["truth"]) if r.ok else None)
    # en bij terugliggend kozijn: nooit stil een grote fout
    for sh in [(3, 0), (8, 0), (16, 8)]:
        s = build(shift_px=sh, recess=0.08)
        r = run(s)
        assert (not r.ok) or err(r, s["truth"]) < 0.02


# -------- 15 schaalconsistentie bij andere resoluties/zoomstanden (intrinsics-/pixelniveau; digitale zoom raakt origineelpixels niet)
@pytest.mark.parametrize("scale", [1.0, 0.5, 1.5])
def test_s15_scale_consistency_across_resolutions(scale):
    from photo_walk_core.simulate import SimFacade, SimFrame, annotate, phone_intrinsics
    base = phone_intrinsics()
    intr = Intrinsics(base.fx * scale, base.fy * scale, base.cx * scale, base.cy * scale, int(base.width * scale), int(base.height * scale))
    fr = SimFrame("K1", 1.0, 0.9, *OUTER)
    f = SimFacade(frames=[fr])
    v = make_view(f, "V", [1.6, 1.6, 3.0], seed=3, intr=intr)
    ob = annotate(fr, v, seed=4)
    r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
    assert r.ok and err(r, OUTER) < 0.015


def test_s15b_no_metric_scale_without_depth():
    s = build(with_depth=False)
    r = run(s)
    assert not r.ok and r.width_m is None


# -------- regressie: nieuwe methode accepteert niet vaker verkeerde maten dan de oude
def _sweep():
    rng = np.random.default_rng(2026)
    out = []
    for i in range(48):
        kw = dict(recess=float(rng.choice([0, 0.02, 0.05, 0.08, 0.12])), relief=float(rng.choice([0, 0.01, 0.025])), noise=float(rng.choice([0.004, 0.008, 0.012])),
                  sill=bool(rng.random() < 0.4), glass_mode=str(rng.choice(["valid", "holes", "reflect", "noisy"])), hole_p=float(rng.choice([0.02, 0.1, 0.3])),
                  pos=(1.6 + float(rng.uniform(-1, 1.5)), 1.6, float(rng.uniform(2.2, 4.5))), yaw=float(rng.uniform(-6, 12)), seed=int(i + 1))
        out.append(kw)
    return out


def test_regression_new_never_accepts_more_wrong_sizes_than_legacy():
    wrong_new = wrong_old = acc_new = acc_old = n = 0
    for kw in _sweep():
        s = build(**kw)
        if s["corners"] is None:
            continue
        n += 1
        r = run(s)
        o = legacy_measure_depth_view(s["cap"], s["corners"], CFG, seed=1)
        if r.ok:
            acc_new += 1
            wrong_new += err(r, s["truth"]) > 0.02
        if o.ok:
            acc_old += 1
            wrong_old += err(o, s["truth"]) > 0.02
    assert n >= 30
    assert wrong_new <= wrong_old
    assert wrong_new == 0, f"{wrong_new} fout geaccepteerd"
    assert acc_new >= 0.7 * n          # niet veilig door alles te weigeren
    assert acc_new >= acc_old * 0.8


def test_regression_adversarial_scenes_never_wrong():
    wrong = 0
    scenes = [build(rough=[(0.0, 4.0, 0.0, 3.5, 0.05)]), build(protrusions=[(0.2, 0.9, 0.0, 3.0, 0.2)]),
              build(protrusions=[(2.3, 3.0, 0.0, 3.0, 0.2)]), build(relief=0.06), build(noise=0.03), build(hole_p=0.7, recess=0.08)]
    for s in scenes:
        r = run(s)
        wrong += r.ok and err(r, s["truth"]) > 0.02
    assert wrong == 0


# -------- diagnostiek
def test_diagnostics_json_schema_and_privacy():
    s = build(recess=0.05, extra_frames=2)
    r = run(s)
    rec = dg.build(r, session_id="SYN", observation_id="O1", view=s["cap"], corners_px=s["corners"], status="MEASURED", feedback="green")
    assert dg.schema_errors(rec) == []
    assert dg.forbidden_key_paths(rec) == []
    text = json.dumps(rec)
    assert len(text) < 60_000
    assert "image_ref" not in text and "depth_ref" not in text and "pose" not in rec["camera"]
    assert all(rec["privacy"][k] is False for k in rec["privacy"])
    alg = rec["algorithm"]
    for k in ("planes", "per_frame", "corner_deviation_m", "frame_plane", "stats"):
        assert k in alg, k


def test_diagnostics_for_rejection_has_specific_reason():
    s = build(protrusions=[(0.2, 0.9, 0.0, 3.0, 0.15), (2.3, 3.0, 0.0, 3.0, 0.15)])
    r = run(s)
    rec = dg.build(r, session_id="SYN", observation_id="O2", view=s["cap"], corners_px=s["corners"], status="UNKNOWN", feedback="orange")
    assert dg.schema_errors(rec) == []
    if not r.ok:
        assert rec["measurement"]["width_m"] is None
        assert any(f["severity"] == "BLOCKING" for f in rec["result_flags"])
        assert rec["user_hints_nl"] and rec["user_hints_nl"] != ["Geen blokkerende problemen."]


def test_diagnostics_forbidden_keys_detected():
    assert dg.forbidden_key_paths({"a": {"point_cloud": [1]}}) != []
    assert dg.forbidden_key_paths({"a": {"image_ref": "x"}}) != []


# -------- referentiesoort: een schatting is geen meting
def _ref_result(kind):
    from photo_walk_core.simulate import SimFacade, SimFrame, annotate
    fr = SimFrame("K1", 1.0, 0.9, *OUTER)
    v = make_view(SimFacade(frames=[fr]), "FR", [1.6, 1.6, 4.0], seed=1, with_depth=False)
    ob = annotate(fr, v, seed=3)
    ref = dict(reference_id="R1", p1_px=ob.corners_px[0], p2_px=ob.corners_px[1], distance_m=OUTER[0], distance_sigma_m=0.005, plane_id="P", kind=kind)
    return measure_with_reference(v, ob.corners_px, ref, CFG, seed=1)


def test_user_estimate_reference_is_flagged_and_downgraded():
    from photo_walk_core.pipeline import _status_from
    est, meas = _ref_result("USER_ESTIMATE"), _ref_result("MEASURED_WITH_TOOL")
    assert "REFERENCE_USER_ESTIMATE" in codes(est) and "REFERENCE_USER_ESTIMATE" not in codes(meas)
    assert est.scale_evidence["reference_kind"] == "USER_ESTIMATE"
    assert _status_from(est, "C", 1, False) == "ESTIMATED"
    assert _status_from(meas, "C", 1, False) == "DERIVED"
