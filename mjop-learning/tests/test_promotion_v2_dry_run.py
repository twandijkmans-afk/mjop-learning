"""
Tests voor scripts/promotion_v2_dry_run.py (Promotion v2: downstream dry-run vanaf batch1_v1).
De echte dry-run wordt één keer per module gebouwd (in het geheugen); canonieke data wordt
alleen gelezen.
"""
import copy
import glob
import hashlib
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import promotion_v2_dry_run as pv2  # noqa: E402

PROTECTED = ["data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
             "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions",
             "data/extracted_deterministic"]


def _hashes():
    out = {}
    for d in PROTECTED:
        for p in sorted(glob.glob(os.path.join(PROJECT_ROOT, d, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                out[os.path.relpath(p, PROJECT_ROOT)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


@pytest.fixture(scope="module")
def built():
    before = _hashes()
    layer, report = pv2.build_all(PROJECT_ROOT)
    assert _hashes() == before, "build_all heeft canonieke data gewijzigd"
    return layer, report


# ------------------------------------------------------------------ echte dry-run

def test_canonical_data_unchanged_and_outputs_only_in_dry_run_dir(built, tmp_path):
    before = _hashes()
    layer, report = built
    (tmp_path / "reports").mkdir()
    pv2.write_outputs(str(tmp_path), layer, report)
    assert _hashes() == before
    assert os.path.isfile(tmp_path / pv2.REPORT)
    assert os.path.isfile(tmp_path / pv2.OUT_DIR / "manifest.json")


def test_refuses_canonical_output_dir(built, tmp_path):
    layer, report = built
    with pytest.raises(SystemExit):
        pv2.write_outputs(str(tmp_path), layer, report, out_dir=os.path.join("data", "verified"))


def test_committed_dry_run_is_current_and_deterministic():
    assert pv2.main(["--check"]) == 0


def test_observation_ids_stable_and_no_amount_changes(built):
    _, report = built
    po = report["price_observations"]
    assert po["old_observations"] == po["new_observations"] == 404
    assert po["category_counts"]["F_missing_or_new"] == 0
    assert po["category_counts"]["G_amount_changed"] == 0 and report["amount_changes"] == 0
    assert not [b for b in report["blockers"] if b["blocker"] in ("amount_changed", "observation_missing_or_new")]


def test_doc003_excluded(built):
    layer, _ = built
    assert "DOC-003" not in layer["normalized"] and "DOC-003" not in layer["verified"]
    assert not any(o["document_id"] == "DOC-003" for o in layer["price_observations"]["observations"])


def test_doc004_external_codes_stay_external(built):
    layer, report = built
    assert all(e["element_code"]["normalized_value"] is None for e in layer["normalized"]["DOC-004"]["elements"])
    assert report["normalization_differences"]["DOC-004"]["new_internal_codes_on_external_document"] == 0
    assert not any(o["element"]["element_code_internal"] for o in layer["price_observations"]["observations"]
                   if o["document_id"] == "DOC-004")


def test_unlinked_placeholder_is_never_an_element_id(built):
    layer, _ = built
    for o in layer["price_observations"]["observations"]:
        assert not str(o["element"]["element_id"]).endswith("-EL-UNLINKED")


def test_accept_simulation_counts(built):
    _, report = built
    sim = report["accept_simulation"]
    assert sum(sim["simulation"].values()) == 220
    assert sim["classification"] == {"AMBIGUOUS": 2, "EXACT_MATCH_CANDIDATE": 131, "NO_MATCH": 87}


def test_kengetallen_dry_run_compares_by_id_and_candidate_key(built):
    layer, report = built
    kg = report["kengetallen"]
    assert kg["old"] == len(json.load(open(os.path.join(PROJECT_ROOT, pv2.KG_PATH)))["kengetallen"])
    assert {tuple(c["candidate_key"]) for c in kg["by_candidate_key"]} <= \
        {tuple(k["candidate_key"]) for k in layer["kengetallen"]["kengetallen"]} | \
        {tuple(k["candidate_key"]) for k in json.load(open(os.path.join(PROJECT_ROOT, pv2.KG_PATH)))["kengetallen"]}
    assert "generated_at" not in layer["kengetallen"]


def test_source_clusters_unchanged(built):
    _, report = built
    assert report["comparability"]["source_clusters_identical"] is True


# ------------------------------------------------------------------ synthetische vergelijkingen

def _po_obs(oid, amounts=None, action_ids=("A1",), code="2110", action="clean"):
    return {"observation_id": oid, "annual_amounts": amounts or {"2025": "100"}, "total_value": "100",
            "total_as_stated": "100", "quantity_value": "1.00", "unit_price_calculated": "100.00",
            "extraction_link": {"action_ids": list(action_ids), "method": "m", "score": None},
            "element": {"element_id": "E1", "element_code_internal": code},
            "action": {"action_normalized": action, "action_normalization_basis": "vocabulary"}}


def _norm(oid, material=None):
    return {"observation_id": oid, "material": {"material_original": material, "material_normalized": material,
                                               "material_from_text": None}}


def _cmp(old, new, info=None):
    return pv2.compare_po({"observations": old}, {"observations": new},
                          {"observations": [_norm(o["observation_id"]) for o in old]},
                          {"observations": [_norm(o["observation_id"]) for o in new]},
                          info or {o["observation_id"]: {"link": "unique", "amounts_equal": True} for o in new})


def test_po_comparison_by_observation_id():
    old = [_po_obs("PO-1"), _po_obs("PO-2"), _po_obs("PO-3")]
    new = [_po_obs("PO-3", action_ids=("B9",)), _po_obs("PO-1"), _po_obs("PO-4")]   # volgorde irrelevant
    res = _cmp(old, new)
    assert res["per_observation"]["PO-1"]["categories"] == ["A_exact_equal"]
    assert res["per_observation"]["PO-3"]["categories"] == ["B_link_changed"]
    assert res["per_observation"]["PO-2"]["categories"] == ["F_missing_or_new"]
    assert res["per_observation"]["PO-4"]["categories"] == ["F_missing_or_new"]


def test_amount_change_is_blocking():
    res = _cmp([_po_obs("PO-1")], [_po_obs("PO-1", amounts={"2025": "101"})])
    assert "G_amount_changed" in res["per_observation"]["PO-1"]["categories"]
    assert res["amount_blocking"] and res["amount_blocking"][0]["observation_id"] == "PO-1"


def test_amount_difference_against_batch1_v1_is_blocking():
    res = _cmp([_po_obs("PO-1")], [_po_obs("PO-1")], {"PO-1": {"link": "unique", "amounts_equal": False}})
    assert "G_amount_changed" in res["per_observation"]["PO-1"]["categories"] and res["amount_blocking"]


def test_code_action_material_categories():
    old, new = [_po_obs("PO-1")], [_po_obs("PO-1", code=None, action="repair")]
    res = pv2.compare_po({"observations": old}, {"observations": new}, {"observations": [_norm("PO-1", "wood")]},
                         {"observations": [_norm("PO-1")]}, {"PO-1": {"link": "unique", "amounts_equal": True}})
    assert set(res["per_observation"]["PO-1"]["categories"]) == {
        "C_action_normalization_changed", "D_internal_code_changed", "E_material_changed"}


def _pair(pid, ids, cls="COMPARABLE", extra=None):
    return dict({"pair_id": pid, "observation_ids": list(ids), "class": cls, "candidate_key": ["2110", "clean", "m2"]},
                **(extra or {}))


def _comp(pairs, clusters=None):
    obs = sorted({i for p in pairs for i in p["observation_ids"]})
    return {"pairs": pairs, "observations": [{"observation_id": o, "source_cluster": (clusters or {}).get(o, "SC-" + o)}
                                             for o in obs], "duplicate_documents": []}


def test_pair_comparison_ignores_pair_id_numbering():
    old = _comp([_pair("PAIR-00001", ["a", "b"]), _pair("PAIR-00002", ["c", "d"]), _pair("PAIR-00003", ["e", "f"])])
    new = _comp([_pair("PAIR-00001", ["d", "c"], cls="UNKNOWN"), _pair("PAIR-00002", ["b", "a"]),
                 _pair("PAIR-00003", ["a", "e"])])
    res = pv2.compare_comparability(old, new)
    assert res["counts"] == {"same_class": 1, "changed_class": 1, "new": 1, "disappeared": 1}


def test_decision_classification():
    old = _comp([_pair("PAIR-00001", ["a", "b"]), _pair("PAIR-00002", ["c", "d"]), _pair("PAIR-00003", ["e", "f"])])
    new = _comp([_pair("PAIR-00007", ["b", "a"]), _pair("PAIR-00008", ["c", "d"], cls="UNKNOWN")])
    norm = {"observations": [{"observation_id": i, "x": 1} for i in "abcdef"]}
    decisions = {"records": [
        {"decision_id": "HDR-1", "status": "ACTIVE", "observation_ids": ["a", "b"], "decision": "COMPARABLE"},
        {"decision_id": "HDR-2", "status": "ACTIVE", "observation_ids": ["c", "d"], "decision": "COMPARABLE"},
        {"decision_id": "HDR-3", "status": "ACTIVE", "observation_ids": ["e", "f"], "decision": "COMPARABLE"}]}
    res = pv2.classify_decisions(decisions, old, new, norm, copy.deepcopy(norm))
    cls = {r["decision_id"]: r["classification"] for r in res["records"]}
    assert cls == {"HDR-1": "STILL_APPLICABLE", "HDR-2": "INPUT_CHANGED_REVIEW_REQUIRED",
                   "HDR-3": "PAIR_NO_LONGER_EXISTS"}
    changed = copy.deepcopy(norm)
    changed["observations"][0]["x"] = 2
    res = pv2.classify_decisions(decisions, old, new, norm, changed)
    assert res["records"][0]["classification"] == "INPUT_CHANGED_REVIEW_REQUIRED"


def test_kengetallen_rename_detected_by_candidate_key():
    old = {"kengetallen": [{"kengetal_id": "KG-x-metaal", "candidate_key": ["4634", "p", "m2"], "status": "AVAILABLE",
                            "value_display": "10.00", "source_cluster_count": 3, "source_cluster_ids": ["a", "b", "c"],
                            "insufficient_data_reasons": []}]}
    new = {"kengetallen": [{"kengetal_id": "KG-x-unknown", "candidate_key": ["4634", "p", "m2"],
                            "status": "INSUFFICIENT_DATA", "value_display": None, "source_cluster_count": 3,
                            "source_cluster_ids": ["a", "b", "c"], "insufficient_data_reasons": ["MATERIAL_UNKNOWN"]}]}
    res = pv2.compare_kengetallen(old, new)
    assert {c["change"] for c in res["changes"]} == {"new", "disappeared"}
    assert res["by_candidate_key"][0]["new"][0]["status"] == "INSUFFICIENT_DATA"


def test_strip_volatile_and_as_json():
    assert pv2.strip_volatile({"a": 1, "inputs": 2, "b": [{"source_file_sha256": "x", "c": 3}]}) == {"a": 1, "b": [{"c": 3}]}
    assert pv2.as_json({None: 1}) == {"null": 1}


# ------------------------------------------------------------------ afronding: ambiguïteit, verklaringen, blockers

def test_only_identical_rows_remain_ambiguous_and_are_not_amount_blockers(built):
    _, report = built
    groups = report["ambiguous_groups"]
    assert groups, "verwacht de identieke DOC-007-rijen"
    for g in groups:
        assert g["document_id"] == "DOC-007"
        assert g["rows_identical"] and g["amounts_equal"] and g["multiset_sizes_equal"]
    assert not [b for b in report["blockers"] if b["blocker"] in ("amount_changed", "ambiguous_rows_not_identical")]
    assert report["price_observations"]["link_counts"].get("none", 0) == 0


def test_all_comparability_changes_explained(built):
    _, report = built
    pc = report["comparability_explained"]
    assert pc["unexplained"] == 0
    assert pc["counts"]["changed"] == report["comparability"]["counts"]["changed_class"]
    assert pc["counts"]["disappeared"] == report["comparability"]["counts"]["disappeared"]


def test_kengetallen_semantic_changes_traceable(built):
    _, report = built
    for k in report["kengetallen_semantic"]:
        assert k["traceable"], k["candidate_key"]
        if k["semantic_match"] and k["old"]["kengetal_ids"] != k["new"]["kengetal_ids"]:
            assert any("zelfde candidate_key" in c for c in k["cause"])


def test_material_classes_cover_all_material_changes(built):
    _, report = built
    m = report["material_changes"]
    assert sum(m["counts"].values()) == report["price_observations"]["category_counts"]["E_material_changed"]
    assert m["counts"]["C_regression"] == 0   # besluit 2026-09-28: MATERIAL_FROM_TEXT ook bij leeg veld
    assert not any(d["observation_id"].startswith("PO-DOC-001") for d in m["details"])


def test_no_blockers_after_material_decision(built):
    _, report = built
    assert report["blockers"] == []


def test_no_internal_code_regression(built):
    _, report = built
    assert report["internal_code_changes"]["counts"]["C_regression"] == 0


def _rows(*acts):
    import promote_deterministic_batch as pdb
    return pdb.new_rows({"maintenance_actions": list(acts)})


def _act(aid, el, year=2025, text="Herstellen", frag="Herstellen 1,00 pst 2025 100", block=None):
    return {"action_id": aid, "element_id": el, "source_page": 9,
            "action": {"original_value": text, "provenance": {"text_fragment": frag, "block_id": block}},
            "quantity": {"value": "1.00"}, "unit": {"original_value": "pst"}, "planned_year": {"value": year},
            "total_cost_as_stated": "100"}


def test_identical_text_rows_of_different_elements_are_not_merged():
    rows = _rows(_act("A1", "E1"), _act("A2", "E2"))
    assert [r["action_ids"] for r in rows] == [["A1"], ["A2"]]


def test_repeated_year_starts_new_row_same_element():
    rows = _rows(_act("A1", "E1"), _act("A2", "E1", year=2032), _act("A3", "E1"))
    assert [r["action_ids"] for r in rows] == [["A1", "A2"], ["A3"]]


def test_rows_identical_proof():
    same = _rows(_act("A1", "E1"), _act("A2", "E2"))
    assert pv2.rows_identical(same)
    other = _rows(_act("A1", "E1"), dict(_act("A2", "E2"), total_cost_as_stated="101"))
    assert not pv2.rows_identical(other)


def test_explain_material_classes():
    def norm(oid, source, value, field="present", reason=None):
        return {"observation_id": oid, "material": {"material_original": value if source == "verified_element" else None,
                "material_normalized": value if source == "verified_element" else None,
                "material_from_text": {"normalized_value": value} if source == "element_text" else None,
                "material_source": source, "verified_material_field": field, "material_not_derived_reason": reason}}
    old = {"observations": [norm("A", "verified_element", "wood"), norm("B", "verified_element", "wood"),
                            norm("C", "element_text", "pvc", field="absent")]}
    new = {"observations": [norm("A", None, None, reason="verified_material_empty"),
                            norm("B", None, None, field="no_element_link", reason="no_element_link"),
                            norm("C", None, None, reason="verified_material_empty")]}
    res = pv2.explain_material(old, new)
    assert res["counts"] == {"A_old_verified_derivation": 1, "B_unlinked_or_ambiguous": 1, "C_regression": 1}
