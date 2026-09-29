"""
Tests voor scripts/human_match_review.py - human match review v1
(docs/human_match_review_v1.md). Matchresultaten komen uit de bestaande
Matching v1-gevallen (C1, C2); er worden geen historische observaties gemaakt.
Beslissingen in deze tests leven alleen in het geheugen of in tmp_path.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys

import jsonschema
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import human_match_review as h  # noqa: E402
import match_kengetal as m  # noqa: E402
import promotion_history as ph  # noqa: E402

# Na de canonieke promotie van batch1_v1 is C1 (4645) geen canoniek kengetal meer. Deze workflowtests
# gebruiken de pre-promotie-kengetallen (C1/C2) uit data/history als vaste, alleen-lezen fixture.
FIXTURE_ROOT = ph.pre_promotion_fixture_root(PROJECT_ROOT)
P = h.paths(FIXTURE_ROOT)
SCHEMA = h.load_json(P["schema"])
MATCH_SCHEMA = h.load_json(P["match_schema"])
KENGETALLEN = h.load_json(P["kengetallen"])
EMPTY = h.load_json(P["store"])
CTX = m.load_context(FIXTURE_ROOT)
C1 = "KG-4645-exterior_painting-m2-concrete-2f1a7a14"
C2 = "KG-5211-replace-m1-pvc-67920b77"
RECORD_VALIDATOR = jsonschema.Draft7Validator({**SCHEMA["definitions"]["decision_record"],
                                               "definitions": SCHEMA["definitions"]})


def mr(ctx=CTX, **over):
    base = dict(object_id="NEW-1", element_code_internal="4645", action_normalized="exterior_painting",
                unit_normalized="m2", material_normalized="concrete",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80", vat_basis="inclusive")
    base.update(over)
    return m.match(PROJECT_ROOT, base, ctx)


C1_EXACT = mr()
C1_REVIEW = mr(object_description="betonconstructie plafond buiten")
C2_EXACT = mr(object_id="NEW-2", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
              material_normalized="pvc", object_description="Hemelwaterafvoer pvc", quantity="100")
C2_VAT = mr(object_id="NEW-3", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
            material_normalized="pvc", object_description="Hemelwaterafvoer pvc", vat_basis="exclusive")
NO_SUITABLE = mr(object_id="NEW-4", action_normalized="interior_painting")


def multi_candidate_result():
    kengetallen, normalized, vocabs, hashes, rel = copy.deepcopy(CTX)
    twin = copy.deepcopy(next(k for k in kengetallen["kengetallen"] if k["kengetal_id"] == C1))
    twin["kengetal_id"] = C1 + "-twin"
    kengetallen["kengetallen"].append(twin)
    return mr((kengetallen, normalized, vocabs, hashes, rel), object_id="NEW-5")


MULTI = multi_candidate_result()


def add(store, result, decision, reason="reden", at="2026-09-24T12:00:00Z", **kw):
    return h.add_decision(store, result, decision, "twandijkmans", reason, schema=SCHEMA, match_schema=MATCH_SCHEMA,
                          kengetallen_doc=KENGETALLEN, reviewed_at=at, **kw)


def test_fixtures_cover_the_required_situations():
    assert C1_EXACT["final_status"] == "CANDIDATE_FOUND" and C1_EXACT["candidate_kengetal_id"] == C1
    assert C1_REVIEW["final_status"] == "HUMAN_REVIEW_REQUIRED" and C1_REVIEW["candidate_kengetal_id"] == C1
    assert C2_EXACT["final_status"] == "CANDIDATE_FOUND" and C2_EXACT["candidate_kengetal_id"] == C2
    assert C2_VAT["reasons"] == ["VAT_BASIS_DIFFERS"]
    assert MULTI["reasons"] == ["MULTIPLE_CANDIDATES"] and MULTI["candidate_kengetal_id"] is None
    assert NO_SUITABLE["final_status"] == "NO_SUITABLE_KENGETAL"


# --------------------------------------------------------------------------
# Basis
# --------------------------------------------------------------------------

def test_no_decision():
    assert h.current_decision(EMPTY, C1_REVIEW["match_result_id"])["status"] == "NO_DECISION"


def test_accept():
    store, rec = add(EMPTY, C1_REVIEW, "ACCEPT", reason="Zelfde betonplafond buiten als de C1-groep")
    assert rec["chosen_kengetal_id"] == C1 and rec["adjustment"] is None and rec["decision_status"] == "ACTIVE"
    cur = h.current_decision(store, C1_REVIEW["match_result_id"])
    assert cur["status"] == "ACCEPTED" and cur["active_record"]["decision_id"] == rec["decision_id"]


def test_adjust_with_other_kengetal_on_multiple_candidates():
    store, rec = add(EMPTY, MULTI, "ADJUST", chosen_kengetal_id=C1, reason="Het echte C1-kengetal")
    assert rec["system_candidate_kengetal_id"] is None and rec["system_candidate_kengetal_ids"] == [C1, C1 + "-twin"]
    assert rec["chosen_kengetal_id"] == C1 and rec["adjustment"]["kengetal_id"] == C1
    assert h.current_decision(store, MULTI["match_result_id"])["status"] == "ADJUSTED"


def test_adjust_with_amount_on_vat_review():
    store, rec = add(EMPTY, C2_VAT, "ADJUST", amount="42.80", amount_basis="door reviewer excl. btw berekend",
                     reason="Input excl. btw", caveats=["VAT_BASIS_DIFFERS"],
                     evidence=[{"reference": C2, "note": "kengetal incl. btw"}])
    adj = rec["adjustment"]
    assert (adj["amount_per_unit_exact"], adj["unit"], adj["kengetal_id"]) == ("42.80", "m1", None)
    assert rec["system_candidate_kengetal_id"] == C2   # oorspronkelijk voorstel blijft zichtbaar
    assert rec["decision_caveats"] == ["VAT_BASIS_DIFFERS"] and rec["evidence"][0]["reference"] == C2


def test_reject():
    store, rec = add(EMPTY, C1_REVIEW, "REJECT", reason="Dakoverstek met afwijkende scope")
    assert rec["chosen_kengetal_id"] is None and rec["adjustment"] is None
    assert rec["system_candidate_kengetal_id"] == C1
    assert h.current_decision(store, C1_REVIEW["match_result_id"])["status"] == "REJECTED"


@pytest.mark.parametrize("result,decision,kw", [
    (NO_SUITABLE, "ACCEPT", {}),                                  # niets om te accepteren
    (MULTI, "ACCEPT", {}),                                        # geen enkel voorstel
    (C1_REVIEW, "ADJUST", {}),                                    # ADJUST zonder aanpassing
    (C1_REVIEW, "ADJUST", {"chosen_kengetal_id": C1}),            # zelfde als voorstel -> ACCEPT
    (C1_REVIEW, "ADJUST", {"chosen_kengetal_id": "KG-bestaat-niet"}),
    (C1_REVIEW, "ADJUST", {"chosen_kengetal_id": "KG-4622-interior_painting-m2-stucwerk-1a17b521"}),  # INSUFFICIENT
    (C2_VAT, "ADJUST", {"amount": "-1"}),
])
def test_invalid_decisions_are_refused(result, decision, kw):
    with pytest.raises(ValueError):
        add(EMPTY, result, decision, **kw)


def test_adjust_to_other_kengetal_requires_same_unit():
    # ander kengetal met dezelfde eenheid (m2): toegestaan - via een kopie van C1 in de kengetallen-output
    kengetallen = copy.deepcopy(KENGETALLEN)
    twin = copy.deepcopy(next(k for k in kengetallen["kengetallen"] if k["kengetal_id"] == C1))
    twin["kengetal_id"] = C1 + "-twin"
    kengetallen["kengetallen"].append(twin)
    _, rec = h.add_decision(EMPTY, C1_REVIEW, "ADJUST", "twandijkmans", "zelfde eenheid", schema=SCHEMA,
                            match_schema=MATCH_SCHEMA, kengetallen_doc=kengetallen, chosen_kengetal_id=C1 + "-twin",
                            reviewed_at="2026-09-24T12:00:00Z")
    assert rec["chosen_kengetal_id"] == C1 + "-twin"
    # ander kengetal met andere eenheid (C2 in m1 voor een m2-regel): geweigerd
    with pytest.raises(ValueError, match="eenheid"):
        add(EMPTY, C1_REVIEW, "ADJUST", chosen_kengetal_id=C2)
    # eigen bedrag in de eenheid van de inputregel: toegestaan
    _, rec = add(EMPTY, C1_REVIEW, "ADJUST", amount="40.00")
    assert rec["adjustment"]["unit"] == "m2"


def test_unknown_decision_value_and_non_human_are_refused():
    with pytest.raises(ValueError):
        add(EMPTY, C1_REVIEW, "APPROVE")
    rec = h.build_record(C1_REVIEW, "ACCEPT", "x", "r", reviewed_at="2026-09-24T12:00:00Z")
    rec["reviewer"]["reviewer_type"] = "ai"
    assert list(RECORD_VALIDATOR.iter_errors(rec))


def test_tampered_match_result_is_refused():
    tampered = copy.deepcopy(C1_REVIEW)
    tampered["input_normalized"]["quantity"] = "9999"
    with pytest.raises(ValueError):
        add(EMPTY, tampered, "ACCEPT")


# --------------------------------------------------------------------------
# ACTIVE / SUPERSEDED
# --------------------------------------------------------------------------

def test_second_decision_supersedes_first_and_keeps_history():
    s1, r1 = add(EMPTY, C1_REVIEW, "ACCEPT", reason="eerst")
    s2, r2 = add(s1, C1_REVIEW, "REJECT", reason="toch niet", at="2026-09-24T13:00:00Z")
    assert r1["decision_status"] == "ACTIVE" and r2["supersedes"] == r1["decision_id"]
    old = next(r for r in s2["records"] if r["decision_id"] == r1["decision_id"])
    assert old["decision_status"] == "SUPERSEDED"
    assert {k: v for k, v in old.items() if k != "decision_status"} == {k: v for k, v in r1.items() if k != "decision_status"}
    cur = h.current_decision(s2, C1_REVIEW["match_result_id"])
    assert cur["status"] == "REJECTED" and cur["history"] == [r1["decision_id"], r2["decision_id"]]
    assert sum(r["decision_status"] == "ACTIVE" for r in s2["records"]) == 1
    assert h.append_only_errors(s1, s2) == [] and h.validate_store(s2, SCHEMA, KENGETALLEN) == []
    assert s1["records"][0]["decision_status"] == "ACTIVE"      # vorige opslag niet gemuteerd


def test_decisions_per_match_result_are_independent():
    s1, _ = add(EMPTY, C1_REVIEW, "ACCEPT")
    s2, _ = add(s1, C2_EXACT, "ACCEPT")
    assert h.current_decision(s2, C1_REVIEW["match_result_id"])["status"] == "ACCEPTED"
    assert h.current_decision(s2, C2_EXACT["match_result_id"])["status"] == "ACCEPTED"
    assert all(r["decision_status"] == "ACTIVE" for r in s2["records"])


def test_two_active_records_are_an_integrity_error():
    s1, r1 = add(EMPTY, C1_REVIEW, "ACCEPT")
    bad = copy.deepcopy(s1)
    r2 = h.build_record(C1_REVIEW, "REJECT", "twandijkmans", "nog een", reviewed_at="2026-09-24T13:00:00Z")
    bad["records"].append(r2)                                    # beide ACTIVE, zonder supersedes
    with pytest.raises(h.IntegrityError):
        h.current_decision(bad, C1_REVIEW["match_result_id"])
    assert any("meer dan één ACTIVE" in e for e in h.store_invariant_errors(bad))
    assert h.validate_store(bad, SCHEMA, KENGETALLEN) != []
    with pytest.raises(h.IntegrityError):
        add(bad, C1_REVIEW, "ACCEPT")


def test_append_only_violations_are_detected():
    s1, r1 = add(EMPTY, C1_REVIEW, "ACCEPT")
    s2, _ = add(s1, C1_REVIEW, "REJECT", reason="later")
    changed = copy.deepcopy(s2)
    changed["records"][0]["decision_reason"] = "herschreven"
    assert any("overschreven" in e for e in h.append_only_errors(s2, changed))
    assert any("verwijderd" in e for e in h.append_only_errors(s2, dict(s2, records=s2["records"][1:])))
    back = copy.deepcopy(s2)
    back["records"][0]["decision_status"] = "ACTIVE"
    assert any("niet toegestaan" in e for e in h.append_only_errors(s2, back))


# --------------------------------------------------------------------------
# Determinisme van het record-ID
# --------------------------------------------------------------------------

def rec(**over):
    r = h.build_record(C1_REVIEW, "REJECT", "twandijkmans", "reden", reviewed_at="2026-09-24T12:00:00Z")
    r.update(over)
    return r


def test_same_content_same_id_timestamp_not_part_of_fingerprint():
    a = h.build_record(C1_REVIEW, "REJECT", "twandijkmans", "reden", reviewed_at="2026-09-24T12:00:00Z")
    b = h.build_record(C1_REVIEW, "REJECT", "twandijkmans", "reden", reviewed_at="2030-01-01T00:00:00Z")
    assert a["decision_id"] == b["decision_id"] == h.human_match_decision_record_id(a)


@pytest.mark.parametrize("over", [
    {"decision": "ACCEPT", "chosen_kengetal_id": C1},
    {"decision_reason": "andere reden"},
    {"match_result_sha256": "0" * 64},
    {"rule_versions": {"human_match_review_version": "human_match_review_v1", "matching_rule_version": "matching_rules_v2",
                       "kengetallen_rule_version": "kengetallen_rules_v1"}},
    {"supersedes": "HMD-0000000000000000"},
])
def test_id_changes_with_relevant_content(over):
    base = rec()
    assert h.human_match_decision_record_id(rec(**over)) != base["decision_id"]


# --------------------------------------------------------------------------
# Herleidbaarheid
# --------------------------------------------------------------------------

def test_traceability_fields_are_preserved():
    s1, r1 = add(EMPTY, C1_REVIEW, "ACCEPT")
    s2, _ = add(s1, C1_REVIEW, "REJECT", reason="later")
    old = next(r for r in s2["records"] if r["decision_id"] == r1["decision_id"])
    assert old["match_result_id"] == C1_REVIEW["match_result_id"]
    assert old["match_result"] == C1_REVIEW and old["match_result_sha256"] == h.canonical_sha256(C1_REVIEW)
    assert old["rule_versions"] == {"human_match_review_version": "human_match_review_v1",
                                    "matching_rule_version": "matching_rules_v1",
                                    "kengetallen_rule_version": "kengetallen_rules_v1"}
    assert old["input_hashes"]["kengetallen_output_sha256"] == h.hashlib.sha256(open(P["kengetallen"], "rb").read()).hexdigest()
    assert old["reviewer"] == {"reviewer_id": "twandijkmans", "reviewer_type": "human"}
    assert h.record_errors(old, KENGETALLEN) == []


def test_tampered_stored_record_is_detected():
    s1, _ = add(EMPTY, C1_REVIEW, "ACCEPT")
    bad = copy.deepcopy(s1)
    bad["records"][0]["match_result"]["historical_range"]["value_exact"] = "1"
    assert any("match_result_sha256" in e for e in h.validate_store(bad, SCHEMA, KENGETALLEN))
    bad = copy.deepcopy(s1)
    bad["records"][0]["decision_reason"] = "stil gewijzigd"
    assert any("decision_id past niet" in e for e in h.validate_store(bad, SCHEMA, KENGETALLEN))


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

def test_empty_store_is_valid():
    assert h.validate_store(EMPTY, SCHEMA) == [] and EMPTY["records"] == []


def test_valid_records_for_all_decisions():
    for r in (add(EMPTY, C1_REVIEW, "ACCEPT")[1], add(EMPTY, MULTI, "ADJUST", chosen_kengetal_id=C1)[1],
              add(EMPTY, C1_REVIEW, "REJECT")[1]):
        assert list(RECORD_VALIDATOR.iter_errors(r)) == []


@pytest.mark.parametrize("field", SCHEMA["definitions"]["decision_record"]["required"])
def test_missing_required_field_fails(field):
    r = rec()
    del r[field]
    assert list(RECORD_VALIDATOR.iter_errors(r))


@pytest.mark.parametrize("over", [
    {"decision": "APPROVE"},
    {"decision_status": "DELETED"},
    {"decision": "REJECT", "chosen_kengetal_id": C1},
    {"decision": "ACCEPT", "chosen_kengetal_id": None},
    {"decision": "ADJUST", "adjustment": None},
    {"score": 1},
])
def test_invalid_records_fail_schema(over):
    assert list(RECORD_VALIDATOR.iter_errors(rec(**over)))


# --------------------------------------------------------------------------
# Data-integriteit, opslag en CLI
# --------------------------------------------------------------------------

def data_hashes():
    out = {}
    for base in ("data", "vocabularies"):
        for dirpath, _, files in os.walk(os.path.join(PROJECT_ROOT, base)):
            for f in files:
                path = os.path.join(dirpath, f)
                out[os.path.relpath(path, PROJECT_ROOT)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return out


def test_review_layer_does_not_change_existing_data_or_match_result():
    before, result_before = data_hashes(), copy.deepcopy(C1_REVIEW)
    s1, _ = add(EMPTY, C1_REVIEW, "ACCEPT")
    s2, _ = add(s1, C2_VAT, "ADJUST", amount="42.80")
    add(s2, C1_REVIEW, "REJECT")
    assert data_hashes() == before and C1_REVIEW == result_before
    assert EMPTY["records"] == []


def test_save_store_is_append_only_and_detects_concurrent_change(tmp_path):
    path = tmp_path / "store.json"
    path.write_text(json.dumps(EMPTY), encoding="utf-8")
    s1, _ = add(EMPTY, C1_REVIEW, "ACCEPT")
    h.save_store(str(path), EMPTY, s1, SCHEMA, KENGETALLEN)
    assert h.load_json(str(path)) == s1
    with pytest.raises(h.IntegrityError):                      # oude basis t.o.v. schijf
        h.save_store(str(path), EMPTY, s1, SCHEMA, KENGETALLEN)
    with pytest.raises(ValueError):                            # overschrijven wordt geweigerd
        h.save_store(str(path), s1, dict(s1, records=[]), SCHEMA, KENGETALLEN)


def test_cli_record_and_status(tmp_path):
    store, result = tmp_path / "store.json", tmp_path / "mr.json"
    store.write_text(json.dumps(EMPTY), encoding="utf-8")
    result.write_text(json.dumps(C2_EXACT), encoding="utf-8")
    script = os.path.join(PROJECT_ROOT, "scripts", "human_match_review.py")
    before = data_hashes()
    r = subprocess.run([sys.executable, script, "record", "--match-result", str(result), "--decision", "ACCEPT",
                        "--reviewer", "twandijkmans", "--reason", "Exact hwa pvc", "--store", str(store)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    s = subprocess.run([sys.executable, script, "status", "--match-result-id", C2_EXACT["match_result_id"],
                        "--store", str(store)], capture_output=True, text=True, encoding="utf-8")
    assert json.loads(s.stdout)["status"] == "ACCEPTED" and data_hashes() == before
