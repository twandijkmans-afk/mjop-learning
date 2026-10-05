"""Tests voor Quantity Subject Expansion Review v1 (read-only readiness review)."""
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import quantity_subject_expansion_review as rev  # noqa: E402

STORES = [bl.LINK_STORE, xw.DECISIONS, rev.RESOLUTIONS, bqe.OUT_EVIDENCE, xw.SUBJECTS, xw.APP_CROSSWALK,
          rev.BUNDLES / "maldenhof_DOC-005_DOC-006_v3.json", rev.BUNDLES / "doc012_meppelweg_v3.json"]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture(scope="module")
def report():
    before = [sha(p) for p in STORES]
    r = rev.build()
    assert [sha(p) for p in STORES] == before, "de review mag geen store, vocabulaire of bundel wijzigen"
    return r


def test_committed_report_up_to_date(report):
    assert open(rev.OUT_JSON, encoding="utf-8").read() == json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    assert open(rev.OUT_MD, encoding="utf-8").read() == rev.render(report)


def test_no_decisions_resolutions_or_bundle_changes(report):
    st = report["state"]
    assert st["crosswalk_decisions"] == ["XWD-00001", "XWD-00002", "XWD-00003"]
    assert st["quantity_resolutions"] == 0 and st["building_links"] == 81
    assert all(b["unchanged"] for b in st["bundles"].values())
    assert st["bundles"]["maldenhof_DOC-005_DOC-006_v3.json"]["sha256"] == "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933"
    assert st["bundles"]["doc012_meppelweg_v3.json"]["sha256"] == "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191"
    assert xw.effective()["XW-dak-hellend-4712-m2"]["status"] == "REVIEW_REQUIRED"


def test_proposal_is_not_activated(report):
    vocab = json.load(open(xw.SUBJECTS, encoding="utf-8"))
    assert not any(s["subject_key"] == "ROOF_TILES_REPORTED_AREA" for s in vocab["subjects"])
    assert "ROOF_SLOPED_AREA" not in {k for r in vocab["subject_relations"] for k in r["subjects"]}
    assert report["proposed_historical_subject"]["status"].startswith("PROPOSAL_ONLY")


def test_4712_inventory_exact_and_m2_only(report):
    inv = report["F_4712_inventory"]
    rows = {r["quantity_observation_id"]: r["classification"] for r in inv["m2_rows"]}
    assert rows == {
        "QO-DOC-001-EL-041": "SAFE_DAKPAN_REPORTED_AREA", "QO-DOC-002-EL-103": "OTHER_SLOPED_ROOF_MATERIAL",
        "QO-DOC-005-EL-027": "SAFE_DAKPAN_REPORTED_AREA", "QO-DOC-006-EL-027": "SAFE_DAKPAN_REPORTED_AREA",
        "QO-DOC-010-EL-034": "AMBIGUOUS_4712", "QO-DOC-013-EL-021": "SAFE_DAKPAN_REPORTED_AREA",
        "QO-DOC-013-EL-022": "OTHER_SLOPED_ROOF_MATERIAL", "QO-DOC-013-EL-023": "AMBIGUOUS_4712"}
    assert all(r["unit"] == "m2" for r in inv["m2_rows"])
    assert len(inv["excluded_non_m2_rows"]) == 8 and all(r["unit"] == "m1" for r in inv["excluded_non_m2_rows"])


def test_classification_is_not_fuzzy():
    qo = {"quantity_observation_id": "X", "document_id": "DOC-X", "unit_normalized": "m2", "quantity_value": "10",
          "element": {"element_code_internal": "4712", "element_description_original": "Dakpannen beton", "location_original": None},
          "provenance": {}, "dependency": {}}
    rows, _ = rev.inventory_4712([qo])
    assert rows[0]["classification"] == "AMBIGUOUS_4712"  # net andere schrijfwijze: niet automatisch 'dakpan'


def test_subject_statuses(report):
    assert report["C_roof_total_area"]["status"] == "INFRASTRUCTURE_ONLY"
    assert report["E_building_height"]["status"] == "CONTEXT_ONLY"
    uses = {e["key"]: e["use"] for e in report["D_outer_wall_gross_area"]["per_app_element"]}
    assert uses == {"steiger": "DIRECT_GEOMETRY_USE", "gevel-metselwerk": "ESTIMATED_PROXY", "voegwerk": "ESTIMATED_PROXY",
                    "schilderwerk-buiten": "NOT_SAFE"}
    x = report["B_roof_sloped_area"]["xw_dak_hellend"]
    assert x["A_element_code_link"].startswith("NIET VEILIG") and x["B_quantity_subject_link"].startswith("NIET EQUIVALENT")


def test_app_coverage_covers_whole_library(report):
    lib = json.load(open(rev.APP_LIBRARY, encoding="utf-8"))
    assert lib["source"]["ref"] == "1afdeca57b5ff6e33d44495a8c71df85b7b466c6"
    assert [r["key"] for r in report["G_app_coverage"]] == [e["key"] for e in lib["elements"]]
    assert sum(report["A_coverage_summary"].values()) == len(lib["elements"]) == 24
    assert report["A_coverage_summary"] == {"READY_NOW": 1, "READY_WITHOUT_HISTORICAL_CONTEXT": 3, "NEEDS_SEMANTIC_MAPPING": 3,
                                            "ESTIMATE_ONLY": 16, "NO_AUTOMATIC_QUANTITY": 1}
    assert len(report["I_recommendations"]) <= 3


def test_missing_is_not_zero_in_matrix(report):
    doc012 = {s["subject"]: s for s in report["H_buildings"]["doc012"]["subjects"]}
    # DOC-012: b3_opp_dak_schuin is AANWEZIG met 0.0 -> geldige 0, compleet
    assert doc012["ROOF_SLOPED_AREA"]["value"] == "0.0" and doc012["ROOF_SLOPED_AREA"]["complete"]
    mald = {s["subject"]: s for s in report["H_buildings"]["maldenhof"]["subjects"]}
    assert mald["ROOF_SLOPED_AREA"]["value"] == "1415.57" and mald["ROOF_SLOPED_AREA"]["child_values_present"] == 15
    # een onderwerp zonder waarde is 'niet beschikbaar' (None), nooit '0'
    for m in report["H_buildings"].values():
        for s in m["subjects"]:
            assert (s["value"] is None) == (not s["available"])
