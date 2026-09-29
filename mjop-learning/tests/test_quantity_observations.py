"""Tests voor quantity observations v1 (scripts/build_quantity_observations.py)."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal

import jsonschema
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_quantity_observations as bqo  # noqa: E402


@pytest.fixture(scope="module")
def result():
    return bqo.build()


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# --- de echte data -----------------------------------------------------------

def test_committed_output_is_up_to_date(result):
    assert open(bqo.OUT_JSON, encoding="utf-8").read() == bqo.dumps(result)
    assert open(bqo.OUT_MD, encoding="utf-8").read() == bqo.render_report(result)


def test_build_is_deterministic(result):
    assert bqo.dumps(bqo.build()) == bqo.dumps(result)


def test_output_matches_schema(result):
    schema = json.load(open(os.path.join(ROOT, "schemas", "quantity_observation.schema.json")))
    jsonschema.validate(json.loads(bqo.dumps(result)), schema)


def test_totals_and_units(result):
    s = result["summary"]
    assert s["quantity_observations"] == 662
    assert s["by_unit"] == {"lump_sum": 48, "m1": 172, "m2": 283, "null": 2, "piece": 157}
    assert s["documents_without_quantities"] == ["DOC-011", "DOC-015"]


def test_every_observation_is_element_quantity_source_reported(result):
    for o in result["observations"]:
        assert o["quantity_kind"] == "ELEMENT_QUANTITY"
        assert o["method_class"] == "SOURCE_REPORTED"
        assert o["source_type"] == "MJOP_ELEMENT_OVERVIEW"


def test_provenance_complete_and_matches_verified(result):
    verified = {}
    for f in sorted(os.listdir(os.path.join(ROOT, "data", "verified"))):
        d = json.load(open(os.path.join(ROOT, "data", "verified", f)))
        for e in d["elements"]:
            verified[e["element_id"]] = e
    for o in result["observations"]:
        assert o["provenance_check"]["complete"], o["quantity_observation_id"]
        e = verified[o["element"]["element_id"]]
        assert o["provenance"] == e["quantity"]["provenance"]          # volledig overgenomen
        assert o["quantity_value"] == e["quantity"]["value"]            # ongewijzigde waarde
        assert o["source_file"]["sha256"] and len(o["source_file"]["sha256"]) == 64


def test_quantity_as_stated_parses_to_value(result):
    for o in result["observations"]:
        if o["quantity_as_stated"] is None:
            assert "QUANTITY_TEXT_NOT_LOCATED" in o["review_reasons"]
            continue
        raw = o["quantity_as_stated"].replace(".", "").replace(",", ".")
        assert Decimal(raw) == Decimal(o["quantity_value"])
        assert o["quantity_as_stated"] in o["provenance"]["text_fragment"]


def test_action_quantities_are_references_only(result):
    price = json.load(open(bqo.PRICE_OBS))["observations"]
    by_id = {p["observation_id"]: p for p in price}
    n = 0
    for o in result["observations"]:
        for link in o["linked_action_quantities"]:
            n += 1
            p = by_id[link["price_observation_id"]]
            assert link["quantity_kind"] == "ACTION_QUANTITY"
            assert link["quantity_value"] == p["quantity_value"]
            assert link["unit_normalized"] == p["unit_normalized"]
            assert p["element"]["element_id"] == o["element"]["element_id"]
    assert n == result["summary"]["linked_action_quantities"] == 474


def test_inputs_are_not_modified():
    before = {p: _sha(p) for p in (bqo.PRICE_OBS, bqo.DOC_RELATIONS, bqo.COMPARABILITY, bqo.REGISTRY)}
    bqo.build()
    assert {p: _sha(p) for p in before} == before


def test_recorded_input_hashes_match_files(result):
    h = result["input_hashes"]
    assert h["price_observations_sha256"] == _sha(bqo.PRICE_OBS)
    assert h["comparability_sha256"] == _sha(bqo.COMPARABILITY)
    for doc, sha in h["verified_sha256"].items():
        assert sha == _sha(os.path.join(ROOT, "data", "verified", doc + ".json"))


def test_no_scores_confidence_or_averages(result):
    text = bqo.dumps(result).lower()
    for forbidden in ('"confidence"', '"score"', '"average"', '"mean"', '"median"', '"weight"'):
        assert forbidden not in text


def test_source_clusters_are_taken_unchanged_from_comparability(result):
    comp = json.load(open(bqo.COMPARABILITY))
    cluster_of = {d: c["source_cluster"] for c in comp["source_clusters"] for d in c["document_ids"]}
    for o in result["observations"]:
        assert o["source_cluster"] == cluster_of[o["document_id"]]


def test_same_object_relations_mark_dependency_not_confirmation(result):
    by_id = {o["quantity_observation_id"]: o for o in result["observations"]}
    same = [o for o in result["observations"] if o["dependency"]["identical_in_same_object_documents"]]
    assert same and all("SAME_IN_RELATED_DOCUMENT" in o["caveats"] for o in same)
    # DOC-005 en DOC-006: versies van hetzelfde MJOP
    assert any(o["document_id"] == "DOC-005" for o in same)
    # DOC-002 en DOC-004: zelfde gebouw, andere inspectie (andere source clusters!)
    doc2 = [o for o in same if o["document_id"] == "DOC-002"]
    assert doc2 and all(by_id[x]["document_id"] == "DOC-004" for o in doc2 for x in o["dependency"]["identical_in_same_object_documents"])
    assert doc2[0]["source_cluster"] != by_id[doc2[0]["dependency"]["identical_in_same_object_documents"][0]]["source_cluster"]


def test_subplans_are_not_compared(result):
    for o in result["observations"]:
        if o["document_id"] in ("DOC-008", "DOC-009"):
            assert o["dependency"]["same_object_document_ids"] == []
            assert not o["dependency"]["identical_in_same_object_documents"]


def test_differences_between_related_documents_are_kept_not_resolved(result):
    differs = [o for o in result["observations"] if o["dependency"]["differs_in_same_object_documents"]]
    assert len(differs) == 18
    pair = {o["quantity_observation_id"]: o["quantity_value"] for o in differs
            if o["quantity_observation_id"] in ("QO-DOC-005-EL-017", "QO-DOC-006-EL-017")}
    assert pair == {"QO-DOC-005-EL-017": "61.00", "QO-DOC-006-EL-017": "42.00"}


def test_review_required_counts(result):
    s = result["summary"]
    assert s["review_required"] == 48
    assert s["review_reasons"] == {
        "ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY": 2, "AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH": 9,
        "DUPLICATE_KEY_DIFFERENT_QUANTITY": 3, "QUANTITY_ONE_IN_MEASURED_UNIT": 31,
        "QUANTITY_TEXT_NOT_LOCATED": 1, "UNIT_IN_TEXT_DIFFERS": 2, "UNIT_UNKNOWN": 2}
    for o in result["observations"]:
        assert o["requires_human_review"] == bool(o["review_reasons"])
        assert o["status"] == ("REVIEW_REQUIRED" if o["review_reasons"] else "SOURCE_REPORTED")


def test_price_observations_and_kengetallen_unchanged():
    k = json.load(open(os.path.join(ROOT, "data", "kengetallen", "kengetallen_batch1.json")))
    by_id = {x["kengetal_id"]: x for x in k["kengetallen"]}
    assert by_id["KG-5211-replace-m1-pvc-5cb98033"]["value_display"] == "54.39"
    assert by_id["KG-5211-replace-m1-pvc-5cb98033"]["status"] == "AVAILABLE"
    assert by_id["KG-4711-replace-m1-aluminium-d463b0a2"]["value_display"] == "37.47"
    assert by_id["KG-4711-replace-m1-aluminium-d463b0a2"]["status"] == "AVAILABLE"
    assert len(json.load(open(bqo.PRICE_OBS))["observations"]) == 545
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_kengetallen.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_mode_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(bqo, "OUT_JSON", tmp_path / "q.json")
    monkeypatch.setattr(bqo, "OUT_MD", tmp_path / "q.md")
    assert bqo.main(["--check"]) == 1
    assert not (tmp_path / "q.json").exists()


def test_refuses_silent_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(bqo, "OUT_JSON", tmp_path / "q.json")
    monkeypatch.setattr(bqo, "OUT_MD", tmp_path / "q.md")
    (tmp_path / "q.json").write_text("{}", encoding="utf-8")
    assert bqo.main([]) == 2
    assert (tmp_path / "q.json").read_text(encoding="utf-8") == "{}"
    assert bqo.main(["--replace"]) == 0


# --- regels op synthetische invoer --------------------------------------------

def _element(eid, value, unit_orig, unit_norm, name="Dakbedekking bitumen", location="Dak", fragment=None, code="4711"):
    frag = fragment if fragment is not None else f"{code} {name} {location} {value.replace('.', ',')}{unit_orig} 1"
    prov = {"document_id": "DOC-900", "page": 3, "text_fragment": frag, "extraction_rule": "profile:test", "block_id": "P03-L001",
            "source_confidence": "high", "table_index": None}
    return {"element_id": eid, "building_id": "DOC-900-BLD-001",
            "element_code": {"original_value": code, "normalized_value": code, "provenance": prov},
            "element_name": {"value": name, "provenance": prov}, "location": {"value": location},
            "material": {"original_value": None, "normalized_value": None},
            "quantity": {"value": value, "conflict": False, "requires_human_review": False, "provenance": prov},
            "unit": {"original_value": unit_orig, "normalized_value": unit_norm, "provenance": prov}}


def _price(pid, eid, qty, unit):
    return {"observation_id": pid, "element": {"element_id": eid}, "quantity_value": qty, "unit_normalized": unit,
            "action": {"action_normalized": "replace"}}


def _synthetic(elements, price_obs=(), extra_docs=None, relations=()):
    verified = {"DOC-900": ("x", {"document_id": "DOC-900", "elements": elements})}
    for doc, els in (extra_docs or {}).items():
        verified[doc] = ("x", {"document_id": doc, "elements": els})
    price = {"observations": list(price_obs)}
    rels = {"relations": list(relations)}
    comp = {"source_clusters": [{"source_cluster": "SC-" + d, "document_ids": [d]} for d in verified]}
    reg = {"documents": [{"document_id": d, "relative_path": d + ".pdf", "sha256": "0" * 64} for d in verified]}
    return verified, price, rels, comp, reg


def _build_synthetic(monkeypatch, *args, **kw):
    monkeypatch.setattr(bqo, "input_hashes", lambda verified: {})
    return {o["element"]["element_id"]: o for o in bqo.build(_synthetic(*args, **kw))["observations"]}


def test_rule_fractional_piece(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "4.40", "st", "piece", name="Draairaam hout")])["E1"]
    assert "FRACTIONAL_PIECE_COUNT" in o["review_reasons"]


def test_rule_unit_unknown(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "30.00", "app", None, name="Binnenriolering")])["E1"]
    assert "UNIT_UNKNOWN" in o["review_reasons"] and not o["measurable"]


def test_rule_quantity_one_in_measured_unit(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "1.00", "m2", "m2")])["E1"]
    assert "QUANTITY_ONE_IN_MEASURED_UNIT" in o["review_reasons"]


def test_rule_lump_sum_is_caveat_not_review(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "1.00", "pst", "lump_sum")])["E1"]
    assert "LUMP_SUM_NOT_A_MEASURED_QUANTITY" in o["caveats"] and not o["requires_human_review"]


def test_rule_quantity_text_not_located(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "312.60", "m2", "m2", fragment="4711 Dakbedekking 999,00m2")])["E1"]
    assert "QUANTITY_TEXT_NOT_LOCATED" in o["review_reasons"] and o["quantity_as_stated"] is None


def test_rule_quantity_as_stated_with_thousands(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "1292.50", "m2", "m2", fragment="4711 Dakbedekking bitumen 1.292,50m2 1")])["E1"]
    assert o["quantity_as_stated"] == "1.292,50" and not o["review_reasons"]


def test_rule_unit_in_text_differs(monkeypatch):
    o = _build_synthetic(monkeypatch, [_element("E1", "18.70", "m1", "m1", name="Buitenschilderwerk kozijn m2 bergingen")])["E1"]
    assert "UNIT_IN_TEXT_DIFFERS" in o["review_reasons"]


def test_rule_duplicate_key(monkeypatch):
    obs = _build_synthetic(monkeypatch, [_element("E1", "8.00", "st", "piece", name="MV-unit"),
                                         _element("E2", "1.00", "st", "piece", name="MV-unit"),
                                         _element("E3", "5.00", "st", "piece", name="Lift"),
                                         _element("E4", "5.00", "st", "piece", name="Lift")])
    assert "DUPLICATE_KEY_DIFFERENT_QUANTITY" in obs["E1"]["review_reasons"]
    assert "DUPLICATE_KEY_SAME_QUANTITY" in obs["E3"]["caveats"] and not obs["E3"]["requires_human_review"]


def test_rule_action_relations(monkeypatch):
    obs = _build_synthetic(monkeypatch,
                           [_element("E1", "312.60", "m2", "m2"), _element("E2", "100.00", "m1", "m1", name="Goot"),
                            _element("E3", "50.00", "m2", "m2", name="Gevel")],
                           price_obs=[_price("PO-DOC-900-P001-L001", "E1", "312.60", "m2"),
                                      _price("PO-DOC-900-P001-L002", "E1", "15.63", "m2"),
                                      _price("PO-DOC-900-P001-L003", "E2", "100.00", "m2"),
                                      _price("PO-DOC-900-P001-L004", "E3", "80.00", "m2"),
                                      _price("PO-DOC-900-P001-L005", "E3", "1.00", "lump_sum")])
    rel = {l["price_observation_id"][-4:]: l["relation_to_element_quantity"] for o in obs.values() for l in o["linked_action_quantities"]}
    assert rel == {"L001": "SAME_AS_ELEMENT", "L002": "FRACTION_OF_ELEMENT", "L003": "DIFFERENT_UNIT",
                   "L004": "EXCEEDS_ELEMENT", "L005": "ACTION_LUMP_SUM_OR_UNKNOWN_UNIT"}
    assert not obs["E1"]["review_reasons"]
    assert "AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH" in obs["E2"]["review_reasons"]
    assert "ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY" in obs["E3"]["review_reasons"]


def test_related_documents_exact_match_only(monkeypatch):
    rel = {"relation_id": "DREL-900", "type": "version_of_same_mjop", "document_ids": ["DOC-900", "DOC-901"]}
    obs = _build_synthetic(monkeypatch, [_element("E1", "312.60", "m2", "m2"), _element("E2", "84.00", "m1", "m1", name="HWA pvc")],
                           extra_docs={"DOC-901": [_element("F1", "312.60", "m2", "m2"),
                                                   _element("F2", "80.00", "m1", "m1", name="HWA pvc"),
                                                   _element("F3", "84.00", "m1", "m1", name="HWA  pvc")]},
                           relations=[rel])
    assert obs["E1"]["dependency"]["identical_in_same_object_documents"] == ["QO-F1"]
    assert obs["E2"]["dependency"]["differs_in_same_object_documents"] == ["QO-F2"]   # 'HWA  pvc' telt niet (geen fuzzy)
    assert obs["E2"]["quantity_value"] == "84.00" and obs["F2"]["quantity_value"] == "80.00"   # niets gemiddeld


def test_synthetic_inputs_not_mutated(monkeypatch):
    inputs = _synthetic([_element("E1", "312.60", "m2", "m2")])
    before = copy.deepcopy(inputs)
    monkeypatch.setattr(bqo, "input_hashes", lambda verified: {})
    bqo.build(inputs)
    assert inputs == before
