"""
Tests voor de human-review-laag v1 (docs/human_review_v1.md):
schemas/human_decision_record.schema.json, de lege opslag in
data/review_decisions/ en de reproduceerbare reviewqueue
(scripts/export_human_review_queue.py). Er worden nergens beslissingen
aangemaakt; de records hieronder zijn alleen testinvoer voor het schema.
"""
import copy
import hashlib
import json
import os
import sys

import jsonschema
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import export_human_review_queue as q  # noqa: E402

SCHEMA = json.load(open(os.path.join(PROJECT_ROOT, "schemas", "human_decision_record.schema.json"), encoding="utf-8"))
STORE = os.path.join(PROJECT_ROOT, "data", "review_decisions", "human_decision_records.json")
COMPARABILITY = os.path.join(PROJECT_ROOT, "data", "comparability", "comparability_batch1.json")
STORE_VALIDATOR = jsonschema.Draft7Validator(SCHEMA)
RECORD_VALIDATOR = jsonschema.Draft7Validator({**SCHEMA["definitions"]["decision_record"],
                                               "definitions": SCHEMA["definitions"]})


def record(**over):
    r = {
        "decision_id": "HDR-00001",
        "pair_id": "PAIR-00335",
        "observation_ids": ["PO-DOC-009-P021-L095", "PO-DOC-010-P012-L093"],
        "candidate_key": ["5211", "replace", "m1"],
        "system_class": "COMPARABLE_WITH_CAVEATS",
        "system_reasons": {"hard_violations": [], "unknown_reasons": [],
                           "pair_caveats": ["PRICE_LEVEL_DIFFERENCE", "QUANTITY_SCALE_DIFFERENCE"],
                           "observation_caveats": {"a": [], "b": []}},
        "decision": "COMPARABLE_WITH_CAVEATS",
        "decision_reason": "testinvoer",
        "decision_caveats": [],
        "reviewer": {"reviewer_id": "tester", "reviewer_type": "human"},
        "reviewed_at": "2026-09-24T10:00:00Z",
        "rule_version": "comparability_rules_v1",
        "input_hashes": {"comparability_output_sha256": "0" * 64, "normalized_observations_sha256": "1" * 64},
        "evidence": [{"observation_id": "PO-DOC-009-P021-L095", "document_id": "DOC-009", "page": 21, "line": 95}],
        "notes": None,
        "supersedes": None,
        "status": "ACTIVE",
    }
    r.update(over)
    return r


def valid(r):
    return list(RECORD_VALIDATOR.iter_errors(r)) == []


# --------------------------------------------------------------------------
# Schema en opslag
# --------------------------------------------------------------------------

def test_empty_store_is_valid():
    empty = {"store_version": "human_review_v1", "append_only": True, "records": []}
    assert list(STORE_VALIDATOR.iter_errors(empty)) == []


def test_current_store_is_valid_and_only_human_decisions():
    store = json.load(open(STORE, encoding="utf-8"))
    assert list(STORE_VALIDATOR.iter_errors(store)) == [] and store["append_only"] is True
    assert all(r["reviewer"]["reviewer_type"] == "human" for r in store["records"])


@pytest.mark.parametrize("decision", ["COMPARABLE", "COMPARABLE_WITH_CAVEATS", "NOT_COMPARABLE", "UNKNOWN"])
def test_all_allowed_decisions(decision):
    assert valid(record(decision=decision))


@pytest.mark.parametrize("field", SCHEMA["definitions"]["decision_record"]["required"])
def test_every_required_field_is_enforced(field):
    r = record()
    del r[field]
    assert not valid(r)


def test_required_fields_cover_the_agreed_minimum():
    assert set(SCHEMA["definitions"]["decision_record"]["required"]) >= {
        "decision_id", "pair_id", "observation_ids", "candidate_key", "system_class", "system_reasons",
        "decision", "decision_reason", "decision_caveats", "reviewer", "reviewed_at", "rule_version",
        "input_hashes", "evidence", "notes", "supersedes", "status"}


@pytest.mark.parametrize("decision", ["MAYBE", "comparable", "", None])
def test_invalid_decision_is_rejected(decision):
    assert not valid(record(decision=decision))


@pytest.mark.parametrize("status", ["DELETED", "active", "DRAFT", None])
def test_invalid_status_is_rejected(status):
    assert not valid(record(status=status))


def test_supersedes_accepts_decision_id_or_null_only():
    assert valid(record(decision_id="HDR-00002", supersedes="HDR-00001"))
    assert valid(record(supersedes=None))
    assert not valid(record(supersedes="PAIR-00335"))
    assert not valid(record(supersedes="HDR-1"))


def test_system_class_stays_separate_from_human_decision():
    # een mens mag anders beslissen dan het systeem; beide blijven apart bewaard
    r = record(system_class="COMPARABLE_WITH_CAVEATS", decision="NOT_COMPARABLE")
    assert valid(r) and r["system_class"] != r["decision"]
    assert not valid(record(system_class=None))
    assert not valid(record(system_reasons={"pair_caveats": []}))


def test_no_score_or_confidence_and_reviewer_is_human():
    props = SCHEMA["definitions"]["decision_record"]["properties"]
    assert not any(w in k for k in props for w in ("score", "confidence", "rank", "weight"))
    assert not valid(record(confidence=0.9))
    assert not valid(record(reviewer={"reviewer_id": "model", "reviewer_type": "ai"}))
    assert not valid(record(decision_reason=""))


def test_store_with_records_is_validated_per_record():
    store = {"store_version": "human_review_v1", "append_only": True,
             "records": [record(), record(decision_id="HDR-00002", supersedes="HDR-00001")]}
    assert list(STORE_VALIDATOR.iter_errors(store)) == []
    store["records"].append(record(decision="MAYBE"))
    assert list(STORE_VALIDATOR.iter_errors(store)) != []


# --------------------------------------------------------------------------
# Invarianten over records heen (append-only, hoogstens één ACTIVE per paar)
# --------------------------------------------------------------------------

def store(*records):
    return {"store_version": "human_review_v1", "append_only": True, "records": list(records)}


def test_two_active_records_for_same_pair_are_invalid():
    s = store(record(), record(decision_id="HDR-00002", decision="NOT_COMPARABLE"))
    assert list(STORE_VALIDATOR.iter_errors(s)) == []            # schema ziet het niet ...
    errors = q.store_invariant_errors(s)                         # ... de invariantcontrole wel
    assert any("meer dan één ACTIVE" in e for e in errors)


def test_valid_supersede_chain():
    s = store(record(status="SUPERSEDED"),
              record(decision_id="HDR-00002", decision="NOT_COMPARABLE", supersedes="HDR-00001"))
    assert q.store_invariant_errors(s) == []
    other_pair = ["PO-DOC-009-P021-L095", "PO-DOC-001-P026-L029"]
    assert q.store_invariant_errors(store(record(), record(decision_id="HDR-00002", pair_id="PAIR-00306",
                                                           observation_ids=other_pair))) == []


def test_pair_identity_is_observation_set_not_pair_id():
    """pair_id is een volgnummer (metadata): na een herbouw mag hetzelfde paar een ander pair_id hebben."""
    s = store(record(status="SUPERSEDED"),
              record(decision_id="HDR-00002", pair_id="PAIR-00001", supersedes="HDR-00001",
                     observation_ids=list(reversed(record()["observation_ids"]))))
    assert q.store_invariant_errors(s) == []
    two_active = store(record(), record(decision_id="HDR-00002", pair_id="PAIR-00001"))
    assert any("meer dan één ACTIVE" in e for e in q.store_invariant_errors(two_active))


def test_review_required_status_transitions():
    old = store(record())
    assert q.append_only_errors(old, store(record(status="REVIEW_REQUIRED"))) == []
    assert list(STORE_VALIDATOR.iter_errors(store(record(status="REVIEW_REQUIRED")))) == []
    rr = store(record(status="REVIEW_REQUIRED"))
    assert q.append_only_errors(rr, store(record(status="SUPERSEDED"),
                                          record(decision_id="HDR-00002", supersedes="HDR-00001"))) == []
    assert q.append_only_errors(rr, store(record(status="ACTIVE"))) != []   # niet stil terug naar ACTIVE
    # REVIEW_REQUIRED telt niet als ACTIVE
    assert q.store_invariant_errors(store(record(status="REVIEW_REQUIRED"), record(decision_id="HDR-00002"))) == []


@pytest.mark.parametrize("records,fragment", [
    ([record(), record(decision_id="HDR-00002", supersedes="HDR-00001")], "SUPERSEDED"),   # oude nog ACTIVE
    ([record(decision_id="HDR-00002", supersedes="HDR-00009")], "onbekende"),
    ([record(status="SUPERSEDED"), record(decision_id="HDR-00002", pair_id="PAIR-00306", supersedes="HDR-00001",
                                          observation_ids=["PO-DOC-009-P021-L095", "PO-DOC-001-P026-L029"])],
     "hetzelfde paar"),
    ([record(), record()], "meer dan eens"),
])
def test_invalid_supersede_or_duplicate_ids(records, fragment):
    assert any(fragment in e for e in q.store_invariant_errors(store(*records)))


def test_append_only_allows_only_new_records_and_active_to_superseded():
    old = store(record())
    new = store(record(status="SUPERSEDED"), record(decision_id="HDR-00002", supersedes="HDR-00001"))
    assert q.append_only_errors(old, new) == []
    assert any("overschreven" in e for e in q.append_only_errors(old, store(record(decision="NOT_COMPARABLE"))))
    assert any("verwijderd" in e for e in q.append_only_errors(old, store()))
    back = store(record(status="SUPERSEDED"))
    assert any("niet toegestaan" in e for e in q.append_only_errors(back, store(record())))


def test_current_store_satisfies_invariants():
    s = json.load(open(STORE, encoding="utf-8"))
    assert q.store_invariant_errors(s) == []


# --------------------------------------------------------------------------
# Reviewqueue
# --------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(COMPARABILITY), reason="comparability output ontbreekt")
def test_queue_selection_on_batch1():
    rows, meta = q.build(PROJECT_ROOT)
    cmp_ = json.load(open(COMPARABILITY, encoding="utf-8"))
    obs = {a["observation_id"]: a for a in cmp_["observations"]}
    pairs = {p["pair_id"]: p for p in cmp_["pairs"]}
    assert meta["pairs_in_queue"] == len(rows) == 22
    for r in rows:
        p = pairs[r["pair_id"]]
        assert p["class"] == "COMPARABLE_WITH_CAVEATS" and r["system_class"] == p["class"]
        for oid in p["observation_ids"]:
            a = obs[oid]
            assert a["independent_input"]
            assert "EXECUTED_DURING_INSPECTION_PRICE_MEANING_UNCLEAR" not in a["independent_input_exclusion_reasons"]
            assert not (a["document_id"] == "DOC-001" and not a["material"]["source"])
        assert all(r[c] is None for c in q.HUMAN_COLUMNS)  # geen beslissing ingevuld
    assert [r["pair_id"] for r in rows] == sorted(r["pair_id"] for r in rows)


@pytest.mark.skipif(not os.path.exists(COMPARABILITY), reason="comparability output ontbreekt")
def test_queue_export_is_reproducible(tmp_path):
    rows1, meta1 = q.build(PROJECT_ROOT)
    rows2, meta2 = q.build(PROJECT_ROOT)
    assert rows1 == rows2 and meta1 == meta2
    before = hashlib.sha256(open(COMPARABILITY, "rb").read()).hexdigest()
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    q.write_xlsx(rows1, meta1, str(a))
    q.write_xlsx(copy.deepcopy(rows2), meta2, str(b))
    assert a.read_bytes() == b.read_bytes()
    assert hashlib.sha256(open(COMPARABILITY, "rb").read()).hexdigest() == before  # alleen gelezen
