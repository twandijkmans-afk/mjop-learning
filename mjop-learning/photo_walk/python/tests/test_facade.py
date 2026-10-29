"""Gevelopbouw: rollen (buitenkozijn / glas / gevel), voorstel glas -> buitenkozijn, hoeveelheden en de beoordeling tegen ground truth.

Alle beelden zijn SYNTHETISCH (getekende gevel, exacte waarheid). Deze tests bewijzen de logica en de rekenregels, NIET de herkenning op
echte gevels; daarvoor is de ground-truthprocedure in docs/facade_ground_truth_protocol.md nodig.
"""
import copy
import json
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest

from photo_walk_core import facade as F
from photo_walk_core import facade_eval as E
from photo_walk_core import facade_parity as P

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCHEMA = json.loads((ROOT / "schemas" / "photo_walk_capture_v1.schema.json").read_text())
WINDOWS = [dict(w, outer=tuple(w["outer"])) for w in P.WINDOWS]
TRUTH = F.synthetic_truth(WINDOWS)
IMG = F.synthetic_facade_gray(1200, 700, WINDOWS)


def qc(polys, det="VN_RECTANGLE_CANDIDATE", score=0.9):
    return [F.QuadCandidate(list(p), det, score) for p in polys]


# ------------------------------------------------------------------ ordenen: glas is nooit vanzelf een kozijn

def test_lone_glass_pane_is_unverified_not_a_frame():
    groups, _ = F.organize(qc([TRUTH[0]["panes"][0]]), 1200, 700)
    assert [(g.evidence, g.status) for g in groups] == [("SINGLE", "UNVERIFIED")]
    assert groups[0].status in F.AREA_BLOCKING_STATUSES          # geen kozijnmaat zonder bevestiging


def test_multiple_panes_of_one_frame_form_one_opening():
    groups, _ = F.organize(qc(TRUTH[1]["panes"]), 1200, 700)
    assert len(groups) == 1 and groups[0].evidence == "PANE_GROUP" and len(groups[0].panes) == 4
    assert groups[0].status == "PROPOSED_EXPANSION" and not groups[0].outer_detected


def test_detected_outer_with_inner_panes():
    groups, _ = F.organize(qc([p for t in TRUTH for p in t["panes"]]) + qc([t["outer"] for t in TRUTH], "VN_CONTOUR_QUAD_CANDIDATE", 0.7), 1200, 700)
    assert [(g.evidence, g.status, len(g.panes)) for g in groups] == [("NESTED_PANES", "DETECTED_ENCLOSING_PANES", 4),
                                                                      ("NESTED_PANES", "DETECTED_ENCLOSING_PANES", 1)]
    assert [g.outer for g in groups] == [[tuple(map(float, p)) for p in TRUTH[1]["outer"]], [tuple(map(float, p)) for p in TRUTH[0]["outer"]]]
    # ook een automatisch gevonden buitencontour rond glas blijft voorlopig: geen kozijnmaat tot de gebruiker bevestigt
    assert all(g.status in F.AREA_BLOCKING_STATUSES for g in groups)


def test_only_confirmed_manual_or_legacy_contours_give_a_frame_area():
    assert set(F.OUTER_STATUSES) - set(F.AREA_BLOCKING_STATUSES) == {"LEGACY", "MANUAL", "USER_CONFIRMED"}


def test_region_containing_frames_is_not_a_frame():
    big = [(150, 100), (950, 100), (950, 520), (150, 520)]
    groups, ignored = F.organize(qc([p for t in TRUTH for p in t["panes"]] + [t["outer"] for t in TRUTH] + [big]), 1200, 700)
    assert len(groups) == 2 and [i.reason for i in ignored] == ["CONTAINS_OPENINGS"]


def test_closeup_keeps_outer_frame_and_glass_apart():
    # regressie: het oude filter hield bij een close-up (kozijn > 30 % van het beeld) glas en kozijn allebei als kozijn
    outer = [(100, 50), (1100, 50), (1100, 650), (100, 650)]
    glass = [(160, 110), (1040, 110), (1040, 590), (160, 590)]
    groups, _ = F.organize(qc([outer, glass]), 1200, 700)
    assert len(groups) == 1 and groups[0].evidence == "NESTED_PANES" and groups[0].panes == [[tuple(map(float, p)) for p in glass]]


def test_door_with_small_glass_needs_confirmation():
    groups, _ = F.organize(qc([[(950, 200), (1060, 200), (1060, 600), (950, 600)], [(980, 230), (1030, 230), (1030, 300), (980, 300)]]), 1200, 700)
    assert groups[0].status == "UNVERIFIED" and groups[0].glass_coverage < 0.3


def test_duplicates_and_invalid_shapes_are_ignored():
    o = TRUTH[0]["outer"]
    groups, ignored = F.organize(qc([o]) + qc([[(a + 1, b + 1) for a, b in o]], "VN_CONTOUR_QUAD_CANDIDATE", 0.95)
                                 + qc([[(500, 500), (560, 500), (500, 560), (560, 560)]]), 1200, 700)
    assert len(groups) == 1 and sorted(i.reason for i in ignored) == ["DUPLICATE", "INVALID_SHAPE"]
    assert groups[0].detector == "VN_CONTOUR_QUAD_CANDIDATE"     # hoogste score blijft


def test_organize_is_deterministic_under_input_order():
    c = qc([p for t in TRUTH for p in t["panes"]] + [t["outer"] for t in TRUTH])
    a, _ = F.organize(c, 1200, 700)
    b, _ = F.organize(list(reversed(c)), 1200, 700)
    assert [(g.outer, g.panes, g.status) for g in a] == [(g.outer, g.panes, g.status) for g in b]


# ------------------------------------------------------------------ voorstel glas -> buitenkozijn

def test_expansion_from_single_pane_finds_outer_frame():
    r = F.propose_outer(IMG, TRUTH[0]["panes"][0])
    assert r["quad"] == [tuple(map(float, p)) for p in TRUTH[0]["outer"]] and r["offsets_px"] == [14.0] * 4


def test_expansion_from_pane_group_finds_outer_frame():
    groups, _ = F.organize(qc(TRUTH[1]["panes"]), 1200, 700)
    r = F.propose_outer(IMG, groups[0].outer)
    assert r["quad"] == [tuple(map(float, p)) for p in TRUTH[1]["outer"]]


def test_expansion_from_one_pane_of_multipane_stops_at_mullion():
    # daarom eerst glasvlakken groeperen: één ruit vergroten levert hier GEEN buitenkozijn op
    r = F.propose_outer(IMG, TRUTH[1]["panes"][0])
    assert r["quad"] != [tuple(map(float, p)) for p in TRUTH[1]["outer"]]


def test_no_proposal_without_clear_edge():
    assert F.propose_outer(IMG, [(40, 520), (120, 520), (120, 600), (40, 600)]) is None


# ------------------------------------------------------------------ hoeveelheden

CAM = ([[-1, 0, 0], [0, -1, 0], [0, 0, 1]], [0.0, 1.5, 0.0])
INTR = (1000.0, 1000.0, 600.0, 350.0)
PLANE = ((0.0, 0.0, 1.0), 5.0)
FACADE = [(100, 80), (1100, 80), (1100, 620), (100, 620)]


def test_planar_area_fronto_parallel():
    # 1000 x 540 px op 5 m met f = 1000 px -> 5,0 x 2,7 m
    assert F.planar_polygon_area_m2(FACADE, CAM, INTR, *PLANE) == pytest.approx(13.5, abs=1e-9)


def _openings(statuses=("ESTIMATED", "DERIVED"), panes=True):
    out = []
    for k, t in enumerate(TRUTH):
        a = F._mm3(F.planar_polygon_area_m2(t["outer"], CAM, INTR, *PLANE))
        out.append(F.OpeningInput(f"OBS-{k + 1}", t["outer"], a, statuses[k], PLANE[0], PLANE[1], t["panes"] if panes else []))
    return out


def test_compose_full():
    r = F.compose(_openings(), CAM, INTR, FACADE, PLANE, "ESTIMATED")
    assert r["facade_gross"]["value_m2"] == "13.500" and r["frame_outer"]["value_m2"] == "4.050"
    assert r["openings"]["value_m2"] == "4.050" and "Aanname" in r["openings"]["basis"]
    assert r["closed_facade_net"]["value_m2"] == "9.450"
    assert r["frame_outer"]["status"] == "ESTIMATED"                            # slechtste status van de kozijnen
    assert Decimal(r["glass"]["value_m2"]) < Decimal(r["frame_outer"]["value_m2"])
    assert r["maintainable_frame_surface"] == {"value_m2": None, "status": "UNKNOWN", "basis": F.MAINTAINABLE_FRAME_NOTE,
                                               "missing": ["NOT_DERIVED"], "partial_value_m2": None}


def test_compose_without_scale_gives_no_m2():
    r = F.compose([F.OpeningInput("OBS-1", TRUTH[0]["outer"], None, "UNKNOWN", None, None, TRUTH[0]["panes"])], None, None, FACADE, None, "UNKNOWN")
    assert all(r[k]["value_m2"] is None and r[k]["status"] == "UNKNOWN" for k in ("facade_gross", "openings", "frame_outer", "glass", "closed_facade_net"))


def test_compose_unknown_glass_when_panes_missing():
    r = F.compose(_openings(panes=False), CAM, INTR, FACADE, PLANE, "ESTIMATED")
    assert r["glass"]["value_m2"] is None and r["glass"]["missing"] == ["OBS-1:GEEN_GLASVLAKKEN", "OBS-2:GEEN_GLASVLAKKEN"]
    assert r["frame_outer"]["value_m2"] == "4.050"                              # buitenkozijn blijft bekend


def test_compose_unmeasured_frame_blocks_net_but_keeps_partial():
    o = _openings()
    o[1].area_m2, o[1].status = None, "UNKNOWN"
    r = F.compose(o, CAM, INTR, FACADE, PLANE, "ESTIMATED")
    assert r["frame_outer"]["value_m2"] is None and r["frame_outer"]["partial_value_m2"] == "1.650" and r["frame_outer"]["missing"] == ["OBS-2"]
    assert r["closed_facade_net"]["value_m2"] is None


def test_compose_openings_larger_than_facade_flagged():
    small = [(190, 140), (430, 140), (430, 460), (190, 460)]
    r = F.compose(_openings()[:1], CAM, INTR, small, PLANE, "ESTIMATED")
    assert r["closed_facade_net"]["value_m2"] is not None
    tiny_plane_area = F.compose([F.OpeningInput("OBS-X", small, Decimal("99.000"), "ESTIMATED", PLANE[0], PLANE[1], [])], CAM, INTR, small, PLANE, "ESTIMATED")
    assert tiny_plane_area["flags"] == ["OPENINGS_EXCEED_FACADE"] and tiny_plane_area["closed_facade_net"]["value_m2"] is None


def test_no_detected_frames_is_unknown_not_zero():
    # audit: geen herkende kozijnen in het gevelvlak mag geen "0 m² openingen" en dus geen netto = bruto opleveren
    r = F.compose([], CAM, INTR, FACADE, PLANE, "ESTIMATED")
    assert r["facade_gross"]["value_m2"] == "13.500"
    for k in ("openings", "frame_outer", "glass", "closed_facade_net"):
        assert r[k]["value_m2"] is None and r[k]["status"] == "UNKNOWN", k
    assert r["frame_outer"]["missing"] == ["NO_FRAMES_IN_FACADE"]


def test_unknown_quantities_are_null_never_zero_in_all_compose_paths():
    o = _openings()
    cases = [F.compose(o, CAM, INTR, FACADE, PLANE, "ESTIMATED"), F.compose(o, None, None, FACADE, None, "UNKNOWN"),
             F.compose(o, CAM, INTR, None, None, "UNKNOWN"), F.compose([], None, None, None, None, "UNKNOWN"),
             F.compose(_openings(panes=False), CAM, INTR, FACADE, PLANE, "ESTIMATED")]
    for r in cases:
        for k in ("facade_gross", "openings", "frame_outer", "glass", "closed_facade_net", "maintainable_frame_surface"):
            q = r[k]
            assert (q["value_m2"] is None) == (q["status"] == "UNKNOWN"), (k, q)
            if q["value_m2"] is not None:
                assert Decimal(q["value_m2"]) > 0, (k, q)


def test_3dbag_is_only_an_advisory_plausibility_check():
    assert F.plausibility_3dbag("120.000", 114.02) == ["FACADE_GROSS_EXCEEDS_3DBAG_WALL_AREA"]
    assert F.plausibility_3dbag("60.000", 114.02) == []
    assert F.plausibility_3dbag(None, 114.02) == []


# ------------------------------------------------------------------ pariteitsfixture voor Swift is actueel

def test_parity_fixture_is_up_to_date():
    on_disk = json.loads(P.OUT.read_text())
    assert on_disk == json.loads(json.dumps(P.build_parity_cases(), sort_keys=True)), "draai: python -m photo_walk_core.facade_parity"


# ------------------------------------------------------------------ exportformaat: nieuw optioneel, oud blijft geldig

def _validator():
    return jsonschema.Draft7Validator(CAPTURE_SCHEMA)


def test_old_exports_still_valid():
    for f in ("single_frame_measurement.json", "walk_measurement.json"):
        rec = json.loads((ROOT / "examples" / f).read_text())
        assert list(_validator().iter_errors(rec)) == [], f


def _export_with_facade():
    rec = json.loads((ROOT / "examples" / "single_frame_measurement.json").read_text())
    rec["contract_version"] = "1.2.0"
    rec["observations"][0]["facade_role"] = {"role": "FRAME_OUTER", "outer_contour_status": "USER_CONFIRMED", "evidence": "SINGLE",
                                             "proposed_outer_px": None, "glass_pane_refs": ["GLS-F000-01"]}
    comp = F.compose(_openings(), CAM, INTR, FACADE, PLANE, "ESTIMATED")
    rec["facade_composition"] = {"version": "1.0.0", "note": "voorlopig", "frames": [{
        "frame_id": "F000", "facade_polygon_px": [list(p) for p in FACADE], "facade_plane_source": "LIDAR_FIT",
        "elements": [{"element_id": "GLS-F000-01", "role": "GLASS_PANE", "parent_observation_ref": rec["observations"][0]["observation_id"],
                      "polygon_px": [list(p) for p in TRUTH[0]["panes"][0]], "original_polygon_px": [list(p) for p in TRUTH[0]["panes"][0]],
                      "source": "AUTO_DETECTED_UNCONFIRMED", "rejected": False, "area_m2": "1.300"}],
        "quantities": {k: comp[k] for k in ("facade_gross", "openings", "frame_outer", "glass", "closed_facade_net", "maintainable_frame_surface")},
        "flags": comp["flags"], "plausibility": {"source": "3DBAG", "b3_opp_buitenmuur_m2": None, "flags": [], "note": "alleen aanvullende controle"}}]}
    return rec


def test_new_facade_fields_valid_and_closed():
    rec = _export_with_facade()
    assert list(_validator().iter_errors(rec)) == []
    bad = copy.deepcopy(rec)
    bad["facade_composition"]["frames"][0]["elements"][0]["role"] = "FRAME_OUTER"      # een kozijn is nooit een los 'element'
    assert list(_validator().iter_errors(bad))
    bad = copy.deepcopy(rec)
    bad["observations"][0]["facade_role"]["role"] = "GLASS_PANE"                      # een waarneming (kozijn) kan geen glas zijn
    assert list(_validator().iter_errors(bad))


# ------------------------------------------------------------------ ground truth en beoordeling (herkenning en meting apart)

def _gt():
    return json.loads((ROOT / "examples" / "ground_truth" / "facade_ground_truth_synthetic.json").read_text())


def test_ground_truth_example_valid():
    assert E.gt_errors(_gt()) == []
    bad = _gt()
    bad["photos"][0]["tape_measurements"][0]["outer_width_m"] = "ongeveer 1 m"
    assert E.gt_errors(bad)


def _fake_export(frames):
    """frames: lijst (observation_id, polygon, width, height, status, contour_status)."""
    obs, objs = [], []
    for i, (oid, poly, w, h, st, cs) in enumerate(frames):
        obs.append({"observation_id": oid, "frame_id": "F000", "corner_source": "AUTO_DETECTED_UNCONFIRMED", "obstruction_reported": False,
                    "facade_role": {"role": "FRAME_OUTER", "outer_contour_status": cs}})
        objs.append({"corner_pixels": [{"observation_ref": oid, "frame_id": "F000", "points": [list(p) for p in poly]}],
                     "outer_width_m": w, "outer_height_m": h, "gross_area_m2": None, "dimension_status": st})
    return {"observations": obs, "objects": objs, "facade_composition": {"frames": []}}


def test_glass_measured_as_frame_is_a_recognition_error_not_a_measurement():
    exp = _fake_export([("OBS-1", TRUTH[0]["panes"][0], "0.960", "1.360", "ESTIMATED", "UNVERIFIED")])
    r = E.evaluate(_gt(), exp)
    f = r["recognition"]["frames"]
    assert f["tp"] == 0 and f["fn"] == 2 and f["fp_glass_as_frame"] == 1
    assert r["measurement"]["rows"] == []                                         # de glasmaat telt NIET als meetfout


def test_split_frame_and_measurement_errors_reported_separately():
    exp = _fake_export([
        ("OBS-1", TRUTH[0]["outer"], "1.110", "1.495", "ESTIMATED", "USER_CONFIRMED"),
        ("OBS-2", [(600, 140), (900, 140), (900, 290), (600, 290)], None, None, "UNKNOWN", "UNVERIFIED"),   # bovenste helft
        ("OBS-3", [(600, 310), (900, 310), (900, 460), (600, 460)], None, None, "UNKNOWN", "UNVERIFIED"),   # onderste helft
    ])
    r = E.evaluate(_gt(), exp)
    f = r["recognition"]["frames"]
    assert (f["tp"], f["fn"], f["fp"], f["fp_split_frame"]) == (1, 1, 2, 2)
    assert f["tp_by_contour_status"] == {"USER_CONFIRMED": 1} and f["corner_error_px"] == [0.0]
    rows = r["measurement"]["rows"]
    assert len(rows) == 1 and rows[0]["width_error_mm"] == "10.000" and rows[0]["height_error_mm"] == "-5.000"
    assert "Geen nauwkeurigheidsclaim" in r["claims"]


def test_unmeasured_but_recognised_frame_counted_separately():
    exp = _fake_export([("OBS-1", TRUTH[0]["outer"], None, None, "UNKNOWN", "UNVERIFIED")])
    r = E.evaluate(_gt(), exp)
    assert r["recognition"]["frames"]["tp"] == 1 and r["measurement"]["unmeasured_matched"] == 1 and r["measurement"]["rows"] == []


def test_legacy_export_without_roles_is_readable():
    rec = json.loads((ROOT / "examples" / "single_frame_measurement.json").read_text())
    frames, panes, facades = E.predictions(rec)
    assert frames["F000"][0]["outer_contour_status"] == "LEGACY" and panes == {} and facades == {}


# ------------------------------------------------------------------ audit: compatibiliteit 1.0 / 1.1 / 1.2 en doorgifte naar de hoeveelheidsmodule

def _as_v11(rec):
    """Een 1.1.0-record: zoals de app vóór de gevelopbouw exporteerde (detectievelden wel, gevelvelden niet)."""
    r = copy.deepcopy(rec)
    r["contract_version"] = "1.1.0"
    r.pop("facade_composition", None)
    for o in r["observations"]:
        o.pop("facade_role", None)
        o["detection"] = {"detector": "VN_RECTANGLE_CANDIDATE", "score": 0.8, "status": "CANDIDATE_UNVERIFIED"}
    r["capture_mode"] = "PHOTO"
    r["rejected_candidates"] = []
    r["detection_summary"] = {"detectors": ["VN_RECTANGLE_CANDIDATE"], "core_ml_model_installed": False, "validated_on_real_buildings": False, "note": "1.1"}
    return r


def test_v11_record_without_facade_fields_still_valid_and_readable():
    rec = _as_v11(_export_with_facade())
    assert list(_validator().iter_errors(rec)) == []
    frames, panes, facades = E.predictions(rec)
    assert all(f["outer_contour_status"] == "LEGACY" for fs in frames.values() for f in fs) and panes == {} and facades == {}


def test_v12_facade_fields_do_not_leak_into_bruto_intake():
    from photo_walk_core import to_bruto
    rec = _export_with_facade()
    # een geblokkeerd (onbevestigd) kozijn: geen maat in het object
    o = rec["objects"][0]
    o.update({"outer_width_m": None, "outer_height_m": None, "gross_area_m2": None, "gross_area_m2_presented": None, "dimension_status": "UNKNOWN",
              "measurement_uncertainty": None, "outer_corner_coordinates": None})
    o["measurement_source"] = dict(o["measurement_source"], level=None, scale_method="NONE", views=[])
    rec["observations"][0]["facade_role"]["outer_contour_status"] = "DETECTED_ENCLOSING_PANES"
    assert list(_validator().iter_errors(rec)) == []
    intake = to_bruto.convert(rec)
    to_bruto.validate(intake)
    assert all(ob["dimension"]["dimension_status"] == "UNKNOWN" for ob in intake["objects"])
    assert not any(p.get("proposed_gross_area_m2") for p in intake["sensor_proposals"]), "geen voorstel-m² uit een onbevestigde contour"
    assert "facade_composition" not in json.dumps(intake) and "GLASS_PANE" not in json.dumps(intake), "glas/gevel gaan niet als kozijnhoeveelheid door"
