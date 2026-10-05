"""Tests voor de facade quantity PoC v2 (Maldenhof): reproduceerbaarheid uit de gecommitte run, de gemeten
kernbevindingen, eerlijke metric-namen, ontdubbel-regels, inputsnapshot en de MJOP-756,8-ontleding.

Geen netwerk en geen API: alles draait op reports/quantity/facade_poc_v2_run/ (gecommitte run + inputsnapshot).
"""
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
from decimal import Decimal

import pytest

pytest.importorskip("numpy")
pytest.importorskip("pyproj")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import facade_coverage_poc_v2 as fc  # noqa: E402
import facade_poc_v2_report as rep  # noqa: E402

QDIR = os.path.join(ROOT, "reports", "quantity")
RUN = os.path.join(QDIR, "facade_poc_v2_run")
REPORT_JSON = os.path.join(QDIR, "facade_element_detection_poc_v2_maldenhof.json")
REPORT_MD = os.path.join(QDIR, "facade_element_detection_poc_v2_maldenhof.md")
SNAPSHOT = os.path.join(RUN, "inputs", "maldenhof_DOC-005-006")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def all_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from all_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from all_keys(v)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report():
    return load(REPORT_JSON)


@pytest.fixture(scope="module")
def aggregate():
    return load(os.path.join(RUN, "aggregate_v2.json"))


# --- reproduceerbaarheid ------------------------------------------------------------------------------------------

def test_aggregate_and_report_reproduce_byte_identical_from_committed_run(tmp_path):
    for f in ("coverage.json", "detections_v2.json"):
        shutil.copy(os.path.join(RUN, f), tmp_path / f)
    fc.run_aggregate(tmp_path)
    assert sha(os.path.join(RUN, "aggregate_v2.json")) == sha(tmp_path / "aggregate_v2.json")
    rep.build(tmp_path, tmp_path / "report.json")
    assert sha(REPORT_JSON) == sha(tmp_path / "report.json")


def test_input_snapshot_sha256_matches_source_manifest():
    src = load(os.path.join(SNAPSHOT, "SOURCE.json"))
    assert src["status"].startswith("EVIDENCE_SNAPSHOT_FOR_POC")
    assert len(src["copied_raw_files"]) == 69          # 40 x 3D BAG + 29 BAG-VBO
    for f in src["copied_raw_files"]:
        with open(os.path.join(SNAPSHOT, f["path"]), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == f["sha256"], f["path"]


def test_snapshot_scope_is_maldenhof_even_only():
    pkg = load(os.path.join(SNAPSHOT, "candidates", "DOC-005-006.json"))
    (hyp,) = pkg["building_project_candidate"]["scope_hypotheses"]
    assert hyp["hypothesis_id"] == "EVEN_ONLY"
    assert len(hyp["bag_pand_ids"]) == 15
    assert len(hyp["addresses_found"]) == 29
    assert all(a["street"] == "Maldenhof" and int(a["number"]) % 2 == 0 for a in hyp["addresses_found"])


# --- kernbevindingen (moeten behouden blijven) ---------------------------------------------------------------------

def test_no_dwelling_has_sufficient_front_and_rear_coverage(report):
    assert report["coverage_status_counts_addresses"] == {"INSUFFICIENT": 29}
    assert len(report["address_records"]) == 29


def test_confirmed_visible_share_about_41_percent_and_rear_about_26(report):
    allc = report["v2_coverage_m2_by_side"]["ALL"]
    assert Decimal(allc["TOTAL"]) == Decimal("1563.43")
    assert Decimal(allc["VISIBLE"]) == Decimal("638.96")
    assert round(Decimal(allc["VISIBLE"]) / Decimal(allc["TOTAL"]), 2) == Decimal("0.41")
    rear = report["v2_coverage_m2_by_side"]["REAR"]
    assert round(Decimal(rear["VISIBLE"]) / Decimal(rear["TOTAL"]), 2) == Decimal("0.26")


def test_review_round_b_counts(report):
    b = report["detection_review_summary"]["B_selection_final_frontal"]
    assert (b["visible_actual"], b["true_positive"], b["missed"], b["false_positive"]) == (42, 39, 3, 8)
    assert b["images"] == 14 and b["panden"] == 14
    assert "GEEN menselijke controle" in b["reviewer"]


def test_multi_panorama_gain_about_7_5_percent(report):
    g = report["multi_panorama_gain"]
    single, union = Decimal(g["visible_m2_single_best_panorama_per_wall"]), Decimal(g["visible_m2_union_multi_panorama"])
    assert Decimal(g["gain_m2"]) == Decimal("88.54")
    assert round((union - single) / single * 100, 1) == Decimal("7.5")


def test_dedup_count_and_registration_offsets(aggregate):
    offs = [(o["offset_m"][0] ** 2 + o["offset_m"][1] ** 2) ** 0.5
            for w in aggregate["walls"] for e in w["elements"] for o in e.get("also_seen_in", []) if isinstance(o, dict)]
    assert len(offs) == 56
    assert round(statistics.median(offs), 2) == 0.24
    assert round(sorted(offs)[int(0.9 * len(offs))], 2) == 0.56


def test_mjop_756_8_is_not_ground_truth(report):
    d = report["mjop_decomposition"]
    recs = d["records"]
    assert {r["document_id"] for r in recs} == {"DOC-005", "DOC-006"}
    # dezelfde 756,80 met andere eenheid/semantiek
    assert any(r["quantity"] == "756.80" and r["unit"] == "st" and "ventilatierooster" in (r["maintenance_action"] or "")
               for r in recs)
    assert all("geen metingen worden verricht" in v["text"] for v in rep.DISCLAIMER.values())
    bm = next(b for b in report["benchmarks"] if "756,80" in b["mjop_quantity"])
    assert bm["classification"] == "NOT_COMPARABLE"
    assert not any(b["classification"] == "DIRECT_COMPARABLE" for b in report["benchmarks"])


def test_decision_and_core_statements_in_markdown():
    md = open(REPORT_MD, encoding="utf-8").read()
    assert "**Beslissing: ITERATE_COVERAGE**" in md
    assert "**0 van 29**" in md
    assert "639,0 van 1563,4 m² (41%)" in md
    assert "Openbare straatbeelden alleen zijn voor dit complextype onvoldoende" in md


# --- metrics en regels ---------------------------------------------------------------------------------------------

def test_no_misleading_frame_area_metric_in_v2_outputs(report, aggregate):
    keys = set(all_keys(report)) | set(all_keys(aggregate))
    assert "frame_area_m2" not in keys and "kozijn_m2" not in keys
    q = report["v2_quantities_by_side"]["ALL"]
    for k in ("window_opening_area_m2", "door_opening_area_m2", "garage_door_area_m2", "dormer_bbox_area_m2",
              "total_opening_bbox_area_m2", "facade_panel_area_m2", "window_sill_m1"):
        assert k in q
    total = sum(Decimal(q[k]) for k in ("window_opening_area_m2", "door_opening_area_m2", "garage_door_area_m2",
                                        "dormer_bbox_area_m2"))
    assert total == Decimal(q["total_opening_bbox_area_m2"])


def test_wall_denominators_exclude_model_unusable(report):
    w = report["v2_wall_m2"]
    assert Decimal(w["wall_m2_model_usable"]) + Decimal(w["wall_m2_model_unusable"]) == Decimal(w["wall_m2_attempted"])
    v1 = report["v1_relabelled"]
    assert Decimal(v1["wall_m2_model_usable"]) + Decimal(v1["wall_m2_model_unusable"]) == Decimal(v1["wall_m2_attempted"])
    assert v1["visible_opening_ratio_on_model_usable"] == str(
        (Decimal(v1["total_opening_bbox_area_m2"]) / Decimal(v1["wall_m2_model_usable"])).quantize(Decimal("0.001")))


def test_same_element_rules():
    a = {"box_m": [0.0, 0.0, 1.0, 1.0]}
    assert fc.same_element(a, {"box_m": [0.1, 0.1, 1.1, 1.1]})            # IoU > 0,3
    assert fc.same_element(a, {"box_m": [0.45, 0.0, 1.45, 1.0]})          # middelpunt 0,45 m, gelijke breedte
    assert not fc.same_element(a, {"box_m": [0.7, 0.0, 1.7, 1.0]})        # 0,7 m verschoven
    assert not fc.same_element(a, {"box_m": [0.2, 0.0, 0.5, 1.0]})        # andere breedte
    assert fc.iou(a["box_m"], a["box_m"]) == 1.0


def test_band_and_zone_helpers():
    assert [fc.band_of(h) for h in (-0.1, 0.0, 2.79, 2.8, 5.6, 9.0)] == ["BG", "BG", "BG", "1e", "kap", "kap"]
    assert fc.final_zone({"zone": "SIDE_REAR_PART", "wall_m2": 31.9}) == "GABLE"
    assert fc.final_zone({"zone": "SIDE_FRONT_PART", "wall_m2": 7.0}) == "SIDE_FRONT_PART"
    assert fc.final_zone({"zone": "FRONT", "wall_m2": 40.0}) == "FRONT"


def test_panoramas_without_height_were_excluded():
    cov = load(os.path.join(RUN, "coverage.json"))
    assert len(cov["panoramas_excluded_no_height"]) == 25
    used = {p["pano_id"] for w in cov["walls"] for p in w["chosen_panoramas"]}
    assert not used & set(cov["panoramas_excluded_no_height"])
    assert all(p["geometry"]["coordinates"][2] > 1.0 for w in cov["walls"] for p in w["chosen_panoramas"])


# --- veiligheid / geen canonical data ------------------------------------------------------------------------------

def test_no_api_key_material_in_facade_files():
    pat = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")
    paths = [os.path.join(ROOT, "scripts", f) for f in os.listdir(os.path.join(ROOT, "scripts")) if f.startswith("facade_")]
    for dirpath, _, files in os.walk(QDIR):
        paths += [os.path.join(dirpath, f) for f in files if f.endswith((".json", ".md")) and "facade" in dirpath + f]
    assert paths
    for p in paths:
        with open(p, encoding="utf-8", errors="ignore") as fh:
            assert not pat.search(fh.read()), p


def test_poc_inputs_and_outputs_live_outside_data_layers():
    """De PoC leest data/extracted (MJOP-ontleding) maar schrijft alleen onder reports/quantity/."""
    assert os.path.commonpath([SNAPSHOT, QDIR]) == QDIR
    assert os.path.commonpath([RUN, QDIR]) == QDIR
    src = open(os.path.join(ROOT, "scripts", "facade_poc_v2_report.py"), encoding="utf-8").read()
    assert 'default=str(ROOT / "reports" / "quantity" / "facade_element_detection_poc_v2_maldenhof.json")' in src
