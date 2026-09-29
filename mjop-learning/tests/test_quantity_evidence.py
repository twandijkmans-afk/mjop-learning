"""Tests voor het quantity-evidence-contract en de append-only resolutie (scripts/quantity_evidence.py)."""
import copy
import json
import os
import sys

import jsonschema
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import quantity_evidence as qe  # noqa: E402

EVIDENCE_SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "quantity_evidence.schema.json")))
STORE_SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "quantity_resolution_record.schema.json")))
QO_PATH = os.path.join(ROOT, "data", "quantity_observations", "quantity_observations_v1.json")
STORE_PATH = os.path.join(ROOT, "data", "quantity_resolutions", "quantity_resolution_records.json")

BUILDING = "BLD-TEST-0001"
T = "2026-10-01T10:00:00Z"


@pytest.fixture
def subject_id():
    return qe.make_subject_id(BUILDING, "4711", "Dak", "m2", "ELEMENT_QUANTITY")


def _subject(sid):
    return {"subject_id": sid, "element_code_internal": "4711", "subject_text": "Plat dak", "location_scope": "Dak",
            "material_normalized": None, "quantity_kind": "ELEMENT_QUANTITY"}


@pytest.fixture
def three_sources(subject_id):
    """Het scenario uit docs/quantity_engine_feasibility_v1.md §9: 3D BAG 312.6, oud MJOP 308, tekening 311.8."""
    s = _subject(subject_id)
    bag = qe.make_evidence(building_id=BUILDING, subject=s, value="312.6", unit_normalized="m2", method_class="DIRECT_MEASURED",
                           source_type="3D_BAG", source_ref={"field": "b3_opp_dak_plat", "pand_id": "NL.IMBAG.Pand.1"},
                           created_by="test")
    mjop = qe.make_evidence(building_id=BUILDING, subject=s, value="308", unit_normalized="m2", method_class="SOURCE_REPORTED",
                            source_type="MJOP_ELEMENT_OVERVIEW", source_ref={"quantity_observation_id": "QO-DOC-900-EL-001"},
                            created_by="test")
    drw = qe.make_evidence(building_id=BUILDING, subject=s, value="311.8", unit_normalized="m2", method_class="GEOMETRY_DERIVED",
                           source_type="DRAWING", source_ref={"document_id": "DRW-1", "page": 3}, created_by="test",
                           calculation={"rule_id": "geometry.polygon_area", "rule_version": "1.0.0", "formula": "polygon area × scale²",
                                        "input_evidence_ids": []})
    return {e["evidence_id"]: e for e in (bag, mjop, drw)}, (bag, mjop, drw)


# --- evidence ----------------------------------------------------------------

def test_subject_id_is_deterministic_and_text_free():
    a = qe.make_subject_id(BUILDING, "4711", "Dak", "m2", "ELEMENT_QUANTITY")
    assert a == qe.make_subject_id(BUILDING, "4711", "Dak", "m2", "ELEMENT_QUANTITY")
    assert a != qe.make_subject_id(BUILDING, "4711", "Dak", "m2", "ACTION_QUANTITY")
    with pytest.raises(qe.QuantityEvidenceError):
        qe.make_subject_id("", "4711", "Dak", "m2", "ELEMENT_QUANTITY")


def test_evidence_matches_schema_and_is_content_addressed(three_sources):
    index, evs = three_sources
    for ev in evs:
        jsonschema.validate(ev, EVIDENCE_SCHEMA)
        assert qe.evidence_errors(ev) == []
    tampered = copy.deepcopy(evs[0])
    tampered["value"] = "400"
    assert qe.evidence_errors(tampered)


def test_geometry_derived_requires_calculation(subject_id):
    with pytest.raises(qe.QuantityEvidenceError):
        qe.make_evidence(building_id=BUILDING, subject=_subject(subject_id), value="10", unit_normalized="m1",
                         method_class="GEOMETRY_DERIVED", source_type="3D_BAG", source_ref={}, created_by="t")


def test_unknown_method_class_rejected(subject_id):
    with pytest.raises(qe.QuantityEvidenceError):
        qe.make_evidence(building_id=BUILDING, subject=_subject(subject_id), value="10", unit_normalized="m1",
                         method_class="CONFIDENT", source_type="3D_BAG", source_ref={}, created_by="t")


def test_evidence_from_quantity_observation_requires_explicit_building_link(subject_id):
    qo = json.load(open(QO_PATH))["observations"][0]
    with pytest.raises(qe.QuantityEvidenceError):
        qe.evidence_from_quantity_observation(qo, building_id=BUILDING, subject_id=subject_id, building_link_ref=None)
    ev = qe.evidence_from_quantity_observation(qo, building_id=BUILDING, subject_id=subject_id, building_link_ref="LINK-TEST-1")
    jsonschema.validate(ev, EVIDENCE_SCHEMA)
    assert ev["method_class"] == "SOURCE_REPORTED" and ev["value"] == qo["quantity_value"]
    assert ev["source_ref"]["provenance"] == qo["provenance"]
    assert ev["dependency"]["source_cluster"] == qo["source_cluster"]


def test_review_reasons_of_observation_carry_into_evidence(subject_id):
    obs = json.load(open(QO_PATH))["observations"]
    flagged = next(o for o in obs if o["requires_human_review"])
    ev = qe.evidence_from_quantity_observation(flagged, building_id=BUILDING, subject_id=subject_id, building_link_ref="L")
    assert ev["status"] == "REVIEW_REQUIRED" and set(flagged["review_reasons"]) <= set(ev["review_reasons"])
    lump = next(o for o in obs if not o["measurable"])
    ev = qe.evidence_from_quantity_observation(lump, building_id=BUILDING, subject_id=subject_id, building_link_ref="L")
    assert "NOT_A_MEASURED_QUANTITY" in ev["review_reasons"]


# --- resolutie -----------------------------------------------------------------

def test_committed_store_is_empty_and_valid():
    store = json.load(open(STORE_PATH))
    jsonschema.validate(store, STORE_SCHEMA)
    assert store["records"] == [] and store["append_only"] is True
    assert qe.store_invariant_errors(store) == []


def test_accept_evidence_takes_exact_value_never_average(three_sources, subject_id):
    index, (bag, mjop, drw) = three_sources
    store = qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                                 selected_evidence_id=drw["evidence_id"], considered_evidence_ids=list(index),
                                 decision_reason="Tekening is recenter dan 3D BAG-opname", reviewer_id="twan", reviewed_at=T,
                                 evidence_index=index)
    r = store["records"][0]
    jsonschema.validate(store, STORE_SCHEMA)
    assert r["resolved_value"] == "311.8" and r["status"] == "ACTIVE"
    assert sorted(r["considered_evidence_ids"]) == sorted(index)     # alle bronnen bewaard in de beslissing
    # een gemiddelde (310.8) kan niet als resolutie bestaan
    averaged = dict(r, resolved_value="310.8")
    assert any("middelen" in e for e in qe.validate_resolution(averaged, index))


def test_user_value_requires_manual_evidence(three_sources, subject_id):
    index, evs = three_sources
    with pytest.raises(qe.QuantityEvidenceError):
        qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="USER_VALUE",
                             manual_evidence_id=evs[0]["evidence_id"], considered_evidence_ids=list(index),
                             decision_reason="x", reviewer_id="twan", reviewed_at=T, evidence_index=index)
    manual = qe.make_evidence(building_id=BUILDING, subject=_subject(subject_id), value="305.5", unit_normalized="m2",
                              method_class="MANUAL", source_type="MANUAL", source_ref={"entered_by": "twan", "note": "ingemeten"},
                              created_by="twan")
    index2 = dict(index, **{manual["evidence_id"]: manual})
    store = qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="USER_VALUE",
                                 manual_evidence_id=manual["evidence_id"], considered_evidence_ids=list(index2),
                                 decision_reason="Zelf ingemeten op het dak", reviewer_id="twan", reviewed_at=T, evidence_index=index2)
    assert store["records"][0]["resolved_value"] == "305.5"


def test_supersede_chain_is_append_only(three_sources, subject_id):
    index, (bag, mjop, drw) = three_sources
    s1 = qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                              selected_evidence_id=bag["evidence_id"], considered_evidence_ids=list(index),
                              decision_reason="3D BAG", reviewer_id="twan", reviewed_at=T, evidence_index=index)
    s2 = qe.record_resolution(s1, building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                              selected_evidence_id=drw["evidence_id"], considered_evidence_ids=list(index),
                              decision_reason="Toch de tekening", reviewer_id="twan", reviewed_at="2026-10-02T10:00:00Z",
                              evidence_index=index)
    assert [r["status"] for r in s2["records"]] == ["SUPERSEDED", "ACTIVE"]
    assert s2["records"][1]["supersedes"] == s1["records"][0]["resolution_id"]
    assert s1["records"][0]["status"] == "ACTIVE"          # invoer niet gemuteerd
    assert qe.append_only_errors(s1, s2) == []
    assert qe.store_invariant_errors(s2, index) == []
    assert qe.active_resolution(s2, BUILDING, subject_id)["resolved_value"] == "311.8"
    # de oude waarde blijft bewaard
    assert s2["records"][0]["resolved_value"] == "312.6"


def test_overwrite_and_delete_are_detected(three_sources, subject_id):
    index, (bag, _, _) = three_sources
    s1 = qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                              selected_evidence_id=bag["evidence_id"], considered_evidence_ids=list(index),
                              decision_reason="3D BAG", reviewer_id="twan", reviewed_at=T, evidence_index=index)
    edited = copy.deepcopy(s1)
    edited["records"][0]["decision_reason"] = "anders"
    assert qe.append_only_errors(s1, edited)
    assert qe.append_only_errors(s1, qe.new_store())


def test_two_active_records_is_invariant_error(three_sources, subject_id):
    index, (bag, mjop, _) = three_sources
    s1 = qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                              selected_evidence_id=bag["evidence_id"], considered_evidence_ids=list(index),
                              decision_reason="a", reviewer_id="twan", reviewed_at=T, evidence_index=index)
    bad = copy.deepcopy(s1)
    extra = dict(bad["records"][0], resolution_id="QRR-00002")
    bad["records"].append(extra)
    assert any("meer dan één ACTIVE" in e for e in qe.store_invariant_errors(bad))


def test_review_required_then_new_decision(three_sources, subject_id):
    index, (bag, mjop, _) = three_sources
    s1 = qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                              selected_evidence_id=bag["evidence_id"], considered_evidence_ids=list(index),
                              decision_reason="a", reviewer_id="twan", reviewed_at=T, evidence_index=index)
    s2 = qe.mark_review_required(s1, "QRR-00001")
    assert qe.append_only_errors(s1, s2) == [] and qe.active_resolution(s2, BUILDING, subject_id) is None
    s3 = qe.record_resolution(s2, building_id=BUILDING, subject_id=subject_id, decision="UNKNOWN",
                              considered_evidence_ids=list(index), decision_reason="bronnen spreken elkaar tegen",
                              reviewer_id="twan", reviewed_at=T, evidence_index=index)
    assert [r["status"] for r in s3["records"]] == ["SUPERSEDED", "ACTIVE"]
    assert s3["records"][1]["resolved_value"] is None
    assert qe.append_only_errors(s2, s3) == [] and qe.store_invariant_errors(s3, index) == []


def test_evidence_from_other_subject_rejected(three_sources, subject_id):
    index, (bag, _, _) = three_sources
    other = qe.make_evidence(building_id="BLD-OTHER", subject=_subject(qe.make_subject_id("BLD-OTHER", "4711", "Dak", "m2", "ELEMENT_QUANTITY")),
                             value="99", unit_normalized="m2", method_class="MANUAL", source_type="MANUAL", source_ref={}, created_by="t")
    index2 = dict(index, **{other["evidence_id"]: other})
    with pytest.raises(qe.QuantityEvidenceError):
        qe.record_resolution(qe.new_store(), building_id=BUILDING, subject_id=subject_id, decision="ACCEPT_EVIDENCE",
                             selected_evidence_id=other["evidence_id"], considered_evidence_ids=list(index2),
                             decision_reason="x", reviewer_id="twan", reviewed_at=T, evidence_index=index2)
