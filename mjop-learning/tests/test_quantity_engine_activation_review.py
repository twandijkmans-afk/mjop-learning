"""Tests voor de read-only Quantity Engine Activation Review v1 (scripts/quantity_engine_activation_review.py).

Bewaakt dat de review niets beslist of schrijft buiten reports/, dat de gecommitte output reproduceerbaar is, en dat
de kernfeiten (15 panden, 29 VBO's, 756,8-label, geen besluiten) blijven kloppen.
"""
import hashlib
import json
import os
import sys

import pytest

pytest.importorskip("pyproj")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import quantity_engine_activation_review as qer  # noqa: E402

DECISION_STORES = [
    os.path.join(ROOT, "data", "building_links", "building_link_records.json"),
    os.path.join(ROOT, "data", "crosswalk_decisions", "crosswalk_decision_records.json"),
    os.path.join(ROOT, "data", "quantity_resolutions", "quantity_resolution_records.json"),
    os.path.join(ROOT, "data", "quantity_evidence", "building_quantity_evidence_v1.json"),
    os.path.join(ROOT, "data", "quantity_observations", "quantity_observations_v1.json"),
]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def report():
    before = {p: sha(p) for p in DECISION_STORES}
    rep = qer.build()
    assert {p: sha(p) for p in DECISION_STORES} == before, "de review mag geen data-store wijzigen"
    return rep


def test_committed_report_is_up_to_date(report):
    js = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    assert open(qer.OUT_JSON, encoding="utf-8").read() == js
    assert open(qer.OUT_MD, encoding="utf-8").read() == qer.render(report)


def test_human_decisions_are_read_from_the_stores_not_simulated(report):
    s = report["state_of_human_decisions"]
    # Maldenhof Quantity Activation v1: 15 CONFIRMED + 25 REJECTED per document, 2 crosswalk-besluiten, geen resolutie
    # + DOC-012 Quantity Activation: 1 CONFIRMED link en XWD-00003 (andere VvE; telt mee in de totalen)
    # + Sloped Roof Quantity Activation v1: XWD-00004/XWD-00005; + Scaffolding Quantity Activation v1: XWD-00006
    assert (s["building_links_records"], s["crosswalk_decisions_records"], s["quantity_resolutions_records"]) == (81, 6, 0)
    assert all(r["link_status"] == "CONFIRMED" for r in report["B_building_link_review"]["rows"])
    assert all(r["link_status"] == "REJECTED" for r in report["B_building_link_review"]["odd_side_context"])
    md = open(qer.OUT_MD, encoding="utf-8").read()
    assert "[x]" not in md.lower()
    assert {m["advice"] for m in report["D_crosswalk_review"]} <= {"SAFE_TO_VERIFY", "NEEDS_REVIEW", "REJECT"}
    status = {m["mapping_id"]: m["current_status"] for m in report["D_crosswalk_review"] if m["mapping_id"]}
    assert status["XW-dak-plat-4711-m2"] == "VERIFIED"
    assert [k for k, v in status.items() if v == "VERIFIED"] == ["XW-dak-plat-4711-m2"]


def test_maldenhof_inputs_facts(report):
    a = report["A_inputs"]
    assert (a["bag_panden_in_scope"], a["vbo_count"]) == (15, 29)
    assert a["addresses_equal_even_240_296"] is True
    assert a["vbo_points_inside_own_pand_polygon"] == 29
    assert a["raw_files_sha256_ok"] == a["raw_files"] == 69
    assert a["verdict"] == "NOT_FEEDABLE_OFFLINE_INTO_CANONICAL_PIPELINE"
    assert len(report["B_building_link_review"]["rows"]) == 30          # 15 panden x DOC-005/DOC-006
    # sinds multi-pand-quantity-scope-v1: range-opvraging bereikt alle 15 panden
    assert report["B_building_link_review"]["lookup_plan_is_range"] is True
    assert len(report["B_building_link_review"]["panden_reachable_via_canonical_lookup"]) == 15


def test_756_8_is_labelled_not_ground_truth_but_kept(report):
    c = report["C_historical_quantities"]
    ids = c["label_756"]["observation_ids"]
    assert sorted(ids) == ["QO-DOC-005-EL-007", "QO-DOC-005-EL-022", "QO-DOC-006-EL-007", "QO-DOC-006-EL-022"]
    rows = {r["quantity_observation_id"]: r for r in c["rows"]}
    for i in ids:
        assert "NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY" in rows[i]["labels"]
        assert rows[i]["method_class"] == "SOURCE_REPORTED"
        assert rows[i]["comparability_vs_3dbag"]["class"] == "NO_3DBAG_SUBJECT"
    assert c["counts"] == {"DOC-005": 36, "DOC-006": 35}


def test_only_roof_rows_are_comparable_candidates(report):
    comp = [r for r in report["C_historical_quantities"]["rows"] if r["comparability_vs_3dbag"]["class"] == "COMPARABLE_CANDIDATE"]
    assert sorted((r["element_code"], r["value"]) for r in comp) == [("4711", "425.80"), ("4711", "425.80"),
                                                                      ("4712", "1485.60"), ("4712", "1485.60")]


def test_bag3d_preview_is_not_evidence_and_not_summed_as_evidence(report):
    d = report["D_bag3d_preview"]
    assert "GEEN evidence" in d["note"]
    assert d["sum_over_15_panden_informative"]["ROOF_FLAT_AREA"] == "190.65"
    assert d["sum_over_15_panden_informative"]["ROOF_SLOPED_AREA"] == "1415.57"
    e = report["E_demo_readiness"]
    assert e["smallest_safe_demo_status"].startswith("ACTIVATED")
    assert "HSM-ROOF_FLAT_AREA-4711-m2 PROPOSED" in e["smallest_safe_demo_status"]
    assert "geen gemiddelde" in e["app_would_show_conceptually"]["rule"]
