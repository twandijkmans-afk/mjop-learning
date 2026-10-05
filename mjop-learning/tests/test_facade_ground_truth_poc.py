"""Tests voor het Ground Truth Quantity framework (scripts/facade_ground_truth_poc.py).

De gecommitte testcases hebben (nog) geen ground truth: die moeten MISSING blijven zonder accuracy-claim.
De vergelijkingslogica wordt getest met SYNTHETISCHE testdata die alleen in tmp_path bestaat — dit is geen ground
truth en wordt nergens gecommit.
"""
import copy
import json
import os
import sys
from decimal import Decimal

import jsonschema
import pytest

np = pytest.importorskip("numpy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import facade_ground_truth_poc as gt  # noqa: E402

SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "facade_ground_truth_case.schema.json"), encoding="utf-8"))
T = "2026-10-05T10:00:00Z"   # synthetisch tijdstip (alleen in tests)


# --- gecommitte cases ----------------------------------------------------------------------------------------------

def test_committed_cases_validate_and_have_no_ground_truth_yet():
    cases = gt.load_cases()
    assert [c["case_id"] for c in cases] == ["GT-MAL-01", "GT-MAL-02", "GT-MAL-03"]
    assert {c["bag_pand_id"] for c in cases} == {"0363100012143647", "0363100012070344", "0363100012127361"}
    for c in cases:
        assert c["selection_reason"]
        for s in c["scopes"]:
            assert s["ground_truth_status"] == "MISSING" and s["measured_objects"] == []
            assert s["objects_to_measure"]


def test_committed_report_is_missing_and_makes_no_accuracy_claim():
    r = gt.build()
    assert r["ground_truth_overall"] == "MISSING" and r["accuracy_claim"] is False
    for s in r["scopes"]:
        assert s["ground_truth"] == "MISSING" and s["comparison"] == "MISSING" and s["accuracy_claim"] is False
    committed = json.load(open(os.path.join(ROOT, "reports", "quantity", "facade_ground_truth_poc_v1.json"), encoding="utf-8"))
    assert committed == json.loads(json.dumps(r))
    md = open(os.path.join(ROOT, "reports", "quantity", "facade_ground_truth_poc_v1.md"), encoding="utf-8").read()
    assert md == gt.render_md(r)


def test_model_side_comes_from_committed_v2_run_without_api():
    r = gt.build()
    front = {s["case_id"]: s["model"] for s in r["scopes"] if s["scope_id"] == "FRONT_MAIN"}
    rear = [s["model"] for s in r["scopes"] if s["scope_id"] == "REAR"]
    assert all(m == "MISSING" for m in rear)
    # GT-MAL-02: wit borstweringspaneel apart gedetecteerd -> volgens definitie bij het kozijn gevoegd
    assert front["GT-MAL-02"]["total_m2_raw"] == "4.63"
    assert front["GT-MAL-02"]["total_m2_definition_aligned"] == "5.38"
    assert len(front["GT-MAL-02"]["panels_merged_into_frame"]) == 1
    # donkere gevelbekleding BOVEN het raam wordt nooit samengevoegd
    assert front["GT-MAL-01"]["panels_merged_into_frame"] == []


# --- synthetische vergelijking ---------------------------------------------------------------------------------------

def gt_obj(oid, level, order, w, h, typ="window_frame", visible=None, src="PHYSICAL_TAPE"):
    o = {"object_id": oid, "type": typ, "level": level, "order_from_left": order, "width_m": w, "height_m": h,
         "count": 1, "unit": "m", "includes_panel_in_frame": True, "measurement_source": src,
         "provenance": "SYNTHETISCH testobject", "measured_by": "pytest", "measured_at": T, "notes": None}
    if visible is not None:
        o["visible_in_images"] = visible
    return o


def model_el(typ, level, box, hidden=False, img="IMG1"):
    return {"type": typ, "level": level, "box_m": box, "partially_hidden": hidden, "image_id": img}


def make_case(tmp_path, gt_objects, model_elements, status="MEASURED", manual=None):
    det = tmp_path / "det.json"
    det.write_text(json.dumps({"elements": model_elements}), encoding="utf-8")
    case = {"case_id": "GT-TST-01", "bag_pand_id": "0000000000000001", "addresses": ["Synthetisch 1"],
            "selection_reason": "synthetische test", "geometric_definition": gt.DEFINITION, "notes": None,
            "scopes": [{"scope_id": "S", "facade_side": "REAR", "description": "synthetisch", "wall_ref": None,
                        "ground_truth_status": status,
                        "images": [{"image_id": "IMG1", "source_type": "RESIDENT_PHOTO", "viewpoint": "FRONTAL",
                                    "path": "synthetic.jpg", "captured_at": T, "camera_distance_m": 6.0,
                                    "status": "PRESENT", "notes": None}],
                        "measured_objects": gt_objects, "objects_to_measure": [],
                        "model_source": {"source_type": "RESIDENT_PHOTO_DETECTION", "status": "PRESENT",
                                         "ref": str(det), "wall_index": None},
                        "manual_matches": manual or []}]}
    jsonschema.validate(case, SCHEMA)
    return case


def test_complete_comparison_metrics_and_causes(tmp_path):
    gts = [gt_obj("BG-1", "BG", 1, "2.00", "1.20", visible={"IMG1": True}),
           gt_obj("1e-1", "1e", 1, "2.00", "1.60", visible={"IMG1": True}),
           gt_obj("1e-2", "1e", 2, "1.00", "1.60", typ="door", visible={"IMG1": False})]
    model = [model_el("window", "BG", [0.0, 3.8, 2.0, 5.0]),                       # exact
             model_el("window", "1e", [0.0, 1.0, 2.1, 2.2]),                       # te kort: paneel apart
             model_el("facade_panel", "1e", [0.1, 2.25, 1.0, 2.6]),                # borstweringspaneel eronder
             model_el("facade_panel", "1e", [0.0, 0.2, 2.1, 0.95])]                # gevelbekleding erboven
    case = make_case(tmp_path, gts, model)
    r = gt.compare_scope(case, case["scopes"][0])
    c = r["comparison"]
    assert c["status"] == "COMPLETE" and r["accuracy_claim"] is True
    assert (c["ground_truth_object_count"], c["true_positives"], c["false_positives"], c["misses"]) == (3, 2, 0, 1)
    assert c["precision"] == "1.000" and c["recall"] == "0.667"
    assert c["ground_truth_total_m2"] == "7.20"                      # 2.40 + 3.20 + 1.60
    # 1e-raam volgens definitie: 2.1 x (2.6 - 1.0) = 3.36; BG 2.40 -> 5.76
    assert c["calculated_total_m2_definition_aligned"] == "5.76"
    assert c["calculated_total_m2_raw"] == "4.92"                    # 2.40 + 2.1 x 1.2
    assert c["absolute_difference_m2"] == "-1.44"
    assert c["percentage_difference"] == "-20.00"
    assert c["semantic_definition_difference_m2"] == "-0.84"
    assert c["difference_by_cause_m2"] == {"COVERAGE_OCCLUSION": "-1.60", "MEASUREMENT_PROJECTION_ERROR": "0.16"}
    assert c["missed_objects"] == [{"object_id": "1e-2", "gt_area_m2": "1.60", "cause": "COVERAGE_OCCLUSION"}]


def test_miss_cause_detection_error_and_undetermined(tmp_path):
    vis = gt.compare_scope(*(lambda c: (c, c["scopes"][0]))(make_case(
        tmp_path, [gt_obj("BG-1", "BG", 1, "1.00", "1.00", typ="door", visible={"IMG1": True})],
        [model_el("window", "1e", [0, 0, 1, 1])])))["comparison"]
    assert vis["missed_objects"][0]["cause"] == "DETECTION_ERROR"
    assert vis["false_positive_objects"][0]["cause"] == "UNDETERMINED"   # geen menselijke uitspraak -> niet gokken
    und = gt.compare_scope(*(lambda c: (c, c["scopes"][0]))(make_case(
        tmp_path, [gt_obj("BG-1", "BG", 1, "1.00", "1.00", typ="door")],
        [model_el("window", "1e", [0, 0, 1, 1])])))["comparison"]
    assert und["missed_objects"][0]["cause"] == "UNDETERMINED"


def test_partially_hidden_match_is_coverage_not_ai_error(tmp_path):
    case = make_case(tmp_path, [gt_obj("BG-1", "BG", 1, "2.00", "1.20")],
                     [model_el("window", "BG", [0.0, 3.8, 2.0, 4.24], hidden=True)])
    c = gt.compare_scope(case, case["scopes"][0])["comparison"]
    assert c["matched_objects"][0]["diff_cause"] == "COVERAGE_OCCLUSION"
    assert "MEASUREMENT_PROJECTION_ERROR" not in c["difference_by_cause_m2"]


def test_unequal_counts_require_manual_match_then_resolve(tmp_path):
    gts = [gt_obj("1e-1", "1e", 1, "2.00", "1.60")]
    model = [model_el("window", "1e", [0.0, 1.0, 1.0, 2.6]), model_el("window", "1e", [1.0, 1.0, 2.0, 2.6])]
    case = make_case(tmp_path, gts, model)
    c = gt.compare_scope(case, case["scopes"][0])
    assert c["comparison"]["status"] == "NEEDS_MANUAL_MATCH" and c["accuracy_claim"] is False
    ids = c["comparison"]["unresolved_groups"][0]["model_element_ids"]
    case = make_case(tmp_path, gts, model, manual=[
        {"model_element_id": ids[0], "object_id": "1e-1", "decided_by": "pytest", "notes": None},
        {"model_element_id": ids[1], "object_id": None, "decided_by": "pytest", "cause": "SEMANTIC_DEFINITION_DIFFERENCE",
         "notes": "kozijn in tweeën gesplitst"}])
    c = gt.compare_scope(case, case["scopes"][0])["comparison"]
    assert c["status"] == "COMPLETE" and (c["true_positives"], c["false_positives"]) == (1, 1)
    assert c["difference_by_cause_m2"]["SEMANTIC_DEFINITION_DIFFERENCE"] == "1.60"


def test_missing_ground_truth_never_produces_comparison(tmp_path):
    case = make_case(tmp_path, [], [model_el("window", "BG", [0, 0, 1, 1])], status="MISSING")
    r = gt.compare_scope(case, case["scopes"][0])
    assert r["ground_truth"] == r["comparison"] == "MISSING" and r["accuracy_claim"] is False
    assert r["model"]["opening_count"] == 1


@pytest.mark.parametrize("status,objs,src", [
    ("MISSING", 1, "PHYSICAL_TAPE"), ("MEASURED", 0, "PHYSICAL_TAPE"), ("MEASURED", 1, "DRAWING"),
    ("DRAWING_DERIVED", 1, "PHYSICAL_TAPE")])
def test_status_consistency_is_enforced(tmp_path, status, objs, src):
    case = make_case(tmp_path, [gt_obj("A", "BG", 1, "1.0", "1.0", src=src)][:objs], [], status=status)
    with pytest.raises(ValueError):
        gt.check_status_consistency(case)


def test_schema_rejects_unknown_status_and_confidence_fields(tmp_path):
    case = make_case(tmp_path, [], [], status="MISSING")
    bad = copy.deepcopy(case); bad["scopes"][0]["ground_truth_status"] = "ESTIMATED"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)
    bad = copy.deepcopy(case); bad["confidence"] = 0.9
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)


# --- bewonersfoto -> gevelvlak -------------------------------------------------------------------------------------

def test_homography_maps_marked_reference_rectangle_to_metres():
    # synthetische perspectieffoto van een 2,00 x 1,50 m kozijn
    src = [(100, 120), (520, 90), (540, 430), (90, 400)]
    dst = [(0, 0), (2.0, 0), (2.0, 1.5), (0, 1.5)]
    H = gt.homography(src, dst)
    np.testing.assert_allclose(gt.to_facade_m(H, src), np.array(dst), atol=1e-9)
    b = gt.box_px_to_facade_m(H, (100, 120, 520, 430))
    assert b[0] == pytest.approx(0.0, abs=0.1) and b[2] == pytest.approx(2.0, abs=0.15)


def test_areas_use_decimal_not_float():
    o = gt_obj("A", "BG", 1, "1.105", "1.205")
    assert gt.gt_area(o) == Decimal("1.33")
