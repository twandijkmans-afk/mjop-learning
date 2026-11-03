"""Gerichte regressietests voor FACADE_NOT_PLANAR (echte iPhone-diagnose, LiDAR-v2).
Oorzaak: pickFacade/pick_facade beoordeelde de ruis van het gekozen vlak over ALLE ringpunten, dus ook over reeds herkende dagkanten/vensterbanken.
Alles hier is SIMULATIE; de echte puntenwolk was niet beschikbaar (de diagnose bevat alleen samenvattingen)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from scenes import OUTER, build  # noqa: E402

from photo_walk_core import depth_plane as dp  # noqa: E402
from photo_walk_core.config import DEFAULT as CFG  # noqa: E402
from photo_walk_core.geometry import look_pose  # noqa: E402
from photo_walk_core.levels import measure_depth_view  # noqa: E402
from photo_walk_core.model import View  # noqa: E402
from photo_walk_core.simulate import SimFacade, SimFrame, annotate, make_view, phone_intrinsics  # noqa: E402


def codes(r):
    return {f["code"] for f in r.flags}


# ------------------------------------------------------------ scene-niveau
def interior_scene(recess=0.35, pos=(1.7, 1.5, 1.3), seed=1, noise=0.006, rough=()):
    fr = SimFrame("K", 1.25, 1.25, 0.7, 0.7, recess_m=recess)
    f = SimFacade(frames=[fr], ledges=[(1.0, 2.2, 1.25, 0.5)], rough=list(rough))
    v = make_view(f, "C", list(pos), seed=seed, noise=noise)
    return fr, v, annotate(fr, v, seed=2)


def test_interior_deep_reveal_and_sill_is_not_rejected_by_foreign_layers():
    fr, v, ob = interior_scene()
    r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
    assert r.ok, codes(r)
    assert abs(r.width_m / 0.7 - 1) < 0.015 and abs(r.height_m / 0.7 - 1) < 0.015
    a = r.diag["facade_assessment"]
    # de oude maat (alle ringpunten) zou dit vlak hebben afgekeurd; de lokale maat niet
    assert a["ring_total_spread_m"] > a["local"]["robust_limit_m"] > a["local"]["robust_sigma_m"]
    assert a["excluded_other_layer"]["share"] > 0.3 and a["representative"] is True
    assert a["local"]["points"] < a["ring_points"]


@pytest.mark.parametrize("kw", [dict(), dict(recess=0.06), dict(recess=0.12, sill=True)])
def test_exterior_flat_and_recessed_with_reveals_still_accepted(kw):
    s = build(**kw)
    r = measure_depth_view(s["cap"], s["corners"], CFG, seed=1)
    assert r.ok and abs(r.width_m / OUTER[0] - 1) < 0.012 and abs(r.height_m / OUTER[1] - 1) < 0.012


def test_frame_plane_still_required_when_reveals_hide_the_profile():
    fr, v, ob = interior_scene(recess=0.45)
    r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
    assert not r.ok and r.width_m is None and codes(r) & {"FRAME_PLANE_UNDETERMINED", "FRAME_PLANE_INCONSISTENT"}   # goed wandvlak bewijst geen kozijnvlak
    assert r.diag["facade_assessment"]["representative"] is True


def test_rough_noise_on_the_chosen_plane_is_still_rejected():
    s = build(rough=[(0.0, 4.0, 0.0, 3.5, 0.05)])
    r = measure_depth_view(s["cap"], s["corners"], CFG, seed=1)
    assert not r.ok or abs(r.width_m / OUTER[0] - 1) < 0.02
    if not r.ok:
        assert "FACADE_NOT_PLANAR" in codes(r)


def test_wrong_corners_still_not_claimed_as_outer():
    s = build(quad="glass", recess=0.1)
    r = measure_depth_view(s["cap"], s["corners"], CFG, seed=1)
    assert (not r.ok) or abs(r.width_m - OUTER[0]) > 0.05


def test_rotation_only_frames_do_not_count_as_independent_viewpoints():
    f = SimFacade(frames=[SimFrame("K1", 1.0, 0.9, 1.2, 1.5)])
    cap = make_view(f, "CAP", [1.6, 1.6, 3.0], seed=1)
    fr = f.frames[0]
    ob = annotate(fr, cap, seed=2)
    ex = [make_view(f, f"R{k}", [1.6, 1.6, 3.0], yaw_deg=2.0 * (k + 1), seed=10 + k) for k in range(3)]
    r = measure_depth_view(cap, ob.corners_px, CFG, seed=1, supports=tuple(ex))
    assert r.ok
    ind = r.diag["independence"]
    assert ind["distinct_viewpoints"] == 1 and ind["rotation_only_frames"] >= 1 and ind["frames_selected"] >= 2
    assert r.independent_frames == 1 and r.scale_method == "LIDAR_DEPTH_PLANE"
    assert ind["criteria"]["min_baseline_m"] == CFG.min_baseline_m


# ------------------------------------------------------------ punt-niveau (nabootsing van de echte ringverdeling)
def capture(z=1.262):
    return View("CAP", phone_intrinsics(), look_pose([0, 0, z], 0), "NORMAL", None)


REG = {0: ((-0.6, 0.6), (0.35, 0.7)), 1: ((0.35, 0.7), (-0.6, 0.6)), 2: ((-0.6, 0.6), (-0.7, -0.35)), 3: ((-0.7, -0.35), (-0.6, 0.6))}


def wall(rng, counts, sigma=0.009):
    P, S = [], []
    for side, n in enumerate(counts):
        (x0, x1), (y0, y1) = REG[side]
        x, y = rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)
        P.append(np.stack([x, y, rng.normal(0, sigma, n)], 1)); S += [side] * n
    return np.vstack(P), np.array(S)


def ledge(rng, y, counts, zmax=0.25, sigma=0.008):
    P, S = [], []
    for side, n in enumerate(counts):
        (x0, x1), _ = REG[side]
        x, z = rng.uniform(x0, x1, n), rng.uniform(0.0, zmax, n)
        P.append(np.stack([x, np.full(n, y) + rng.normal(0, sigma, n), z], 1)); S += [side] * n
    return np.vstack(P), np.array(S)


def run_points(parts, quad_diag_px=800.0, seed=3):
    X = np.vstack([p[0] for p in parts]); S = np.concatenate([p[1] for p in parts])
    return dp.analyze_points(capture(), X, np.ones(len(X), int), S, CFG, seed, z_hint=1.262, quad_diag_px=quad_diag_px)


def test_real_diagnosis_distribution_selects_facade_not_the_largest_ledge():
    rng = np.random.default_rng(7)
    parts = [wall(rng, [5, 1059, 142, 135]), ledge(rng, -0.45, [0, 279, 2006, 86]), ledge(rng, -0.55, [0, 176, 695, 32])]
    sc = rng.uniform([-0.6, -0.7, -0.3], [0.6, 0.7, 0.3], (1000, 3))
    parts.append((sc, rng.integers(0, 4, 1000)))
    an = run_points(parts)
    assert an["facade"] is not None, an["flags"]
    A = an["assessment"]
    assert abs(an["facade"]["n"][2]) > 0.99                       # de muur, niet de (grootste) vensterbank
    assert A["ring_total_spread_m"] > A["local"]["robust_limit_m"] > A["local"]["robust_sigma_m"]
    assert A["sides"]["covered"] == [False, True, True, True] and A["representative"]
    assert "LIMITED_SIDE_COVERAGE" in {f["code"] for f in an["flags"]}          # 3 van 4 zijden: adviserend, nooit MEASURED
    assert A["excluded_other_layer"]["share"] > 0.4


def test_only_a_ledge_is_never_a_facade():
    rng = np.random.default_rng(1)
    an = run_points([ledge(rng, -0.45, [800, 800, 800, 800], zmax=0.4)])
    assert an["facade"] is None and {f["code"] for f in an["flags"]} == {"NO_FACADE_PLANE"}


def test_narrow_profile_strip_is_not_representative():
    rng = np.random.default_rng(2)
    n = 1500
    x = np.concatenate([rng.uniform(-0.7, -0.4, n), rng.uniform(0.4, 0.7, n)])
    P = np.stack([x, rng.uniform(-0.01, 0.01, 2 * n), rng.normal(0, 0.004, 2 * n)], 1)       # vensterbank-/profielstrook, 2 cm hoog
    S = np.where(x < 0, 3, 1)
    an = run_points([(P, S)])
    assert an["facade"] is None and {f["code"] for f in an["flags"]} == {"FACADE_NOT_REPRESENTATIVE"}
    assert an["assessment"]["extent"]["minor_std_m"] < an["assessment"]["extent"]["min_required_m"]


def test_two_conflicting_vertical_planes_stay_unknown():
    rng = np.random.default_rng(3)
    a, sa = wall(rng, [800, 800, 800, 800])
    b, sb = wall(rng, [700, 700, 700, 700])
    c, ang = np.cos(0.6), np.sin(0.6)                            # tweede muur, ~34 graden gedraaid (hoek/uitbouw)
    b = np.stack([b[:, 0] * c + b[:, 2] * ang, b[:, 1], -b[:, 0] * ang + b[:, 2] * c], 1)
    an = run_points([(a, sa), (b, sb)])
    assert an["facade"] is None and {f["code"] for f in an["flags"]} == {"AMBIGUOUS_FACADE_PLANES"}


def test_many_points_on_one_side_do_not_hide_missing_sides():
    rng = np.random.default_rng(4)
    an = run_points([wall(rng, [3, 9000, 4, 5])])
    assert an["facade"] is None and {f["code"] for f in an["flags"]} == {"FACADE_ONE_SIDED"}
    assert an["assessment"]["sides"]["covered"] == [False, True, False, False]


def test_noise_on_the_chosen_plane_itself_is_rejected():
    rng = np.random.default_rng(5)
    P, S = wall(rng, [900, 900, 900, 900], sigma=0.06)
    an = run_points([(P, S)])
    assert an["facade"] is None and {f["code"] for f in an["flags"]} == {"FACADE_NOT_PLANAR"}


def test_mostly_unexplained_points_are_not_a_facade():
    rng = np.random.default_rng(6)
    P, S = wall(rng, [300, 300, 300, 300])
    sc = rng.uniform([-0.6, -0.7, -0.4], [0.6, 0.7, 0.4], (6000, 3))
    an = run_points([(P, S), (sc, rng.integers(0, 4, 6000))])
    assert an["facade"] is None and {f["code"] for f in an["flags"]} == {"FACADE_NOT_PLANAR"}


@pytest.mark.parametrize("size", [(72, 96), (192, 256)])
def test_deep_reveals_never_yield_a_wrong_accepted_size(size):
    """Regressie: de terugval 'terugligging uit hoekdieptes' gaf bij diepe dagkanten 3-9 % te kleine maten. Nu: nooit een foute maat, hooguit UNKNOWN."""
    from photo_walk_core.simulate import _render_depth
    intr = phone_intrinsics()
    bad = 0
    for rec in (0.2, 0.3, 0.4, 0.45, 0.5):
        for pos in ((1.7, 1.5, 1.3), (1.6, 1.6, 1.3), (1.5, 1.55, 1.4)):
            fr = SimFrame("K", 1.25, 1.25, 0.7, 0.7, recess_m=rec)
            f = SimFacade(frames=[fr], ledges=[(1.0, 2.2, 1.25, 0.5)])
            ps = look_pose(list(pos), 0)
            v = View("C", intr, ps, "NORMAL", _render_depth(f, ps, intr, np.random.default_rng(1), noise=0.006, hole_p=0.03, size=size))
            ob = annotate(fr, v, seed=2)
            r = measure_depth_view(v, ob.corners_px, CFG, seed=1)
            if r.ok and max(abs(r.width_m / 0.7 - 1), abs(r.height_m / 0.7 - 1)) > 0.015:
                bad += 1
    assert bad == 0
