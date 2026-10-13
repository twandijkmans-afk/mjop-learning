import copy
import json
import os
import re

from agent.photo import evaluate as EV
from agent.photo.contract import PROJECT_ROOT, iou
from agent.photo.quantity import compute_quantity_state
from agent.photo.review_page import render_review_page

import photo_support as S


def synthetic_ref():
    return [{"ref_id": g["gt_id"], "element_type": g["element_type"], "bbox_norm": g["bbox_norm"], "visibility": g["visibility"]}
            for g in S.load_json("synthetic_facade_v1_ground_truth.json")["ground_truth"]]


def test_synthetic_evaluation_precision_recall_and_count_error():
    ev = EV.evaluate_proposals(S.proposal_set()["proposals"], synthetic_ref())
    o = ev["overall"]
    assert (o["tp"], o["fp"], o["fn"]) == (7, 1, 1) and o["precision"] == 0.875 and o["recall"] == 0.875
    w = ev["per_type"]["WINDOW_OPENING"]
    assert (w["tp"], w["fp"], w["fn"], w["count_error"], w["visibility_agreement"]) == (6, 0, 0, 0, 1.0)
    assert ev["per_type"]["ROOF_WINDOW"]["recall"] == 0.0 and ev["per_type"]["UNKNOWN_OPENING"]["precision"] == 0.0
    assert o["count_error_frame_types"] == 0


def test_evaluation_detects_double_count_and_miss():
    props = copy.deepcopy(S.proposal_set()["proposals"])
    dup = copy.deepcopy(props[0]); dup["observation_id"] = "PO-090"; dup["bbox_norm"] = [v + 0.003 for v in dup["bbox_norm"]]
    ev = EV.evaluate_proposals(props + [dup], synthetic_ref())
    assert ev["per_type"]["WINDOW_OPENING"]["fp"] == 1 and ev["per_type"]["WINDOW_OPENING"]["count_error"] == 1
    ev2 = EV.evaluate_proposals([p for p in props if p["element_type"] != "EXTERIOR_DOOR"], synthetic_ref())
    assert ev2["per_type"]["EXTERIOR_DOOR"]["recall"] == 0.0 and ev2["per_type"]["EXTERIOR_DOOR"]["count_error"] == -1


def test_evaluation_empty_denominators_are_null_not_zero():
    ev = EV.evaluate_proposals([], synthetic_ref())
    assert ev["overall"]["precision"] is None and ev["overall"]["recall"] == 0.0


def test_matching_is_one_to_one_and_deterministic():
    ref = [{"ref_id": "R", "element_type": "WINDOW_OPENING", "bbox_norm": [0.1, 0.1, 0.3, 0.3], "visibility": "FULL"}]
    props = [{"observation_id": f"PO-00{i}", "element_type": "WINDOW_OPENING", "bbox_norm": [0.1 + i * 0.001, 0.1, 0.3, 0.3], "visibility": "FULL"} for i in (1, 2)]
    pairs, fp, fn = EV.match(props, ref)
    assert len(pairs) == 1 and len(fp) == 1 and fn == [] and pairs == EV.match(props, ref)[0]


def test_iou_basics():
    assert iou([0, 0, 1, 1], [0, 0, 1, 1]) == 1 and iou([0, 0, .1, .1], [.5, .5, .6, .6]) == 0


def test_maldenhof_photo2_reference_is_read_only_json_and_matches_frozen_counts():
    ref, meta = EV.load_maldenhof_photo2_reference()
    frames = [r for r in ref if r["element_type"] == "WINDOW_OPENING"]
    assert len(frames) == 11 and sum(r["element_type"] == "EXTERIOR_DOOR" for r in ref) == 1       # 11 kozijnen + 1 buitendeur (bevroren)
    assert sum(r["visibility"] == "FULL" for r in frames) == 9 and sum(r["visibility"] == "PARTIAL" for r in frames) == 2
    assert sum(r["element_type"] == "ROOF_WINDOW" for r in ref) == 5 and sum(r["element_type"] == "DORMER_OPENING" for r in ref) == 1
    assert meta["usage"] == "EVALUATION_ONLY_NOT_MODEL_INPUT" and meta["source_sha256"].startswith("a316ce71")


def test_maldenhof_reference_never_used_as_model_input():
    """Geen enkel modul behalve evaluate.py leest data/ of foto's; geen module opent een afbeelding van schijf."""
    for name in os.listdir(os.path.join(PROJECT_ROOT, "agent", "photo")):
        if name.endswith(".py") and name != "evaluate.py":
            text = open(os.path.join(PROJECT_ROOT, "agent", "photo", name), encoding="utf-8").read()
            if name == "safety_gate.py":                                  # decodeert uitsluitend bytes in het geheugen, nooit een pad
                assert text.count("Image.open") == text.count("Image.open(io.BytesIO("), "safety_gate.py: Image.open alleen op in-memory bytes"
                text = text.replace("Image.open(io.BytesIO(", "")
            for needle in ("data/photos", "data/photo_evidence", "data/frame_inventory", ".jpg", ".jpeg", "Image.open"):
                assert needle not in text, f"{name}: {needle}"
    ev_text = open(os.path.join(PROJECT_ROOT, "agent", "photo", "evaluate.py"), encoding="utf-8").read()
    assert "Image" not in ev_text and "data/photos" not in ev_text


def test_maldenhof_mock_harness_end_to_end(tmp_path):
    import photo_reviewer_demo as D
    ev = D.run_reference_mock(str(tmp_path), "maldenhof_2")
    assert ev["overall"]["tp"] == 17 and ev["overall"]["fp"] == 1 and ev["overall"]["fn"] == 1
    saved = json.load(open(tmp_path / "reference_mock_evaluation.json"))
    assert saved["reference_meta"]["usage"] == "EVALUATION_ONLY_NOT_MODEL_INPUT"


def page():
    ps, d = S.proposal_set(), S.dims()
    st = compute_quantity_state(ps, d)
    ev = EV.evaluate_proposals(ps["proposals"], synthetic_ref())
    return render_review_page(S.png(), ps, st, d, ev), ps, st


def test_page_shows_boxes_ids_uncertainty_counts_dimensions_area_and_proposal_banner():
    html, ps, st = page()
    assert "VOORSTELLEN" in html and "PROPOSED" in html and "geen geaccepteerde instances" in html and "onderhoudshoeveelheden" in html
    for p in ps["proposals"]:
        assert p["observation_id"] in html
    assert html.count('class="box"') == len(ps["proposals"])
    assert "OCCLUDED_BY_VEGETATION (HIGH)" in html and "1.200 m" in html and "9.60 m²" in html and "Gebouwtotaal: <b>onbekend</b>" in html
    assert "Evaluatie" in html


def test_page_is_self_contained_and_has_no_external_resources():
    html, *_ = page()
    assert not re.findall(r'(?:src|href)="(?!data:image/png;base64)[a-z]+://', html)
    assert "http://" not in html and "https://" not in html


def test_page_escapes_untrusted_text_and_shows_null_area_as_dash():
    ps = S.fresh()
    ps["proposals"][0]["observation"] = "<script>alert(1)</script>"
    ps["proposals"][0]["uncertainties"] = [{"code": "OTHER", "level": "LOW", "note": "<img src=x onerror=alert(1)>"}]
    ps = S.reseal(ps)
    st = compute_quantity_state(ps, None)
    html = render_review_page(S.png(), ps, st, None)
    assert "<script>alert" not in html and "onerror=alert" not in html
    assert "niet volledig bekend" in html and "Geen gevalideerde maten opgegeven" in html
