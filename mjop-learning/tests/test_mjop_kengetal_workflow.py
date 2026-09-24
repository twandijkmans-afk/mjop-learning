"""
Integratietests voor scripts/mjop_kengetal_workflow.py (MJOP kengetal workflow v1):
input -> match_kengetal (normalisatie, retrieval, scope) -> human_match_review
(current_decision) -> gebruikt bedrag. Echte C1/C2-voorbeelden; beslissingen alleen
in het geheugen of in tmp_path; geen nieuwe historische observaties.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import human_match_review as h  # noqa: E402
import match_kengetal as m  # noqa: E402
import mjop_kengetal_workflow as w  # noqa: E402

HP = h.paths(PROJECT_ROOT)
DECISION_SCHEMA, MATCH_SCHEMA = h.load_json(HP["schema"]), h.load_json(HP["match_schema"])
KENGETALLEN = h.load_json(HP["kengetallen"])
EMPTY = h.load_json(HP["store"])
RESULT_SCHEMA = w.paths(PROJECT_ROOT)["schema"]
CTX = m.load_context(PROJECT_ROOT)
C1 = "KG-4645-exterior_painting-m2-concrete-2f1a7a14"
C2 = "KG-5211-replace-m1-pvc-67920b77"
C1_VALUE = next(k for k in KENGETALLEN["kengetallen"] if k["kengetal_id"] == C1)["value_exact"]
C2_VALUE = next(k for k in KENGETALLEN["kengetallen"] if k["kengetal_id"] == C2)["value_exact"]


def c1(**over):
    base = dict(object_id="MJOP-1", element_code_internal="4645", action_normalized="exterior_painting",
                unit_normalized="m2", material_normalized="concrete", material_source="user",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80", vat_basis="inclusive",
                building_type="VvE appartementen", construction_year=1975)
    base.update(over)
    return base


def c2(**over):
    base = dict(object_id="MJOP-2", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive")
    base.update(over)
    return base


def run(raw, store=EMPTY, ctx=CTX):
    r = w.run(raw, store, ctx, root=PROJECT_ROOT)
    assert w.validate_output(r, RESULT_SCHEMA) == []
    return r


def decide(raw, decision, store=EMPTY, ctx=CTX, **kw):
    mr = m.match(PROJECT_ROOT, raw, ctx)
    new_store, rec = h.add_decision(store, mr, decision, "twandijkmans", kw.pop("reason", "reden"),
                                    schema=DECISION_SCHEMA, match_schema=MATCH_SCHEMA, kengetallen_doc=KENGETALLEN,
                                    reviewed_at="2026-09-24T12:00:00Z", **kw)
    return new_store, rec


def multi_ctx():
    kengetallen, normalized, vocabs, hashes, rel = copy.deepcopy(CTX)
    twin = copy.deepcopy(next(k for k in kengetallen["kengetallen"] if k["kengetal_id"] == C1))
    twin["kengetal_id"] = C1 + "-twin"
    kengetallen["kengetallen"].append(twin)
    return kengetallen, normalized, vocabs, hashes, rel


# --------------------------------------------------------------------------
# Zonder beslissing: nooit een effectief bedrag
# --------------------------------------------------------------------------

def assert_no_effective_amount(r):
    f = r["financial_result"]
    assert f["effective_amount"] is None and f["effective_total"] is None and f["effective_amount_source"] is None
    assert f["total_not_computed_reason"] == "NO_EFFECTIVE_AMOUNT"


def test_c1_exact_is_pending_decision_without_amount():
    r = run(c1())
    assert r["status"] == "MATCH_PENDING_DECISION" and r["current_decision"]["status"] == "NO_DECISION"
    assert r["financial_result"]["system_candidate_kengetal_id"] == C1
    assert r["financial_result"]["system_candidate_amount"] == C1_VALUE   # voorstel zichtbaar, niet gebruikt
    assert_no_effective_amount(r)


def test_c1_other_wording_is_review_required_without_amount():
    r = run(c1(object_description="betonconstructie plafond buiten"))
    assert r["status"] == "REVIEW_REQUIRED" and r["match_result"]["final_status"] == "HUMAN_REVIEW_REQUIRED"
    assert r["match_result"]["candidate_kengetal_id"] == C1                # volledige match_result beschikbaar
    assert_no_effective_amount(r)


def test_c2_exact_is_pending_decision_without_amount():
    r = run(c2())
    assert r["status"] == "MATCH_PENDING_DECISION" and r["financial_result"]["system_candidate_amount"] == C2_VALUE
    assert_no_effective_amount(r)


def test_no_suitable_kengetal_gives_no_amount():
    r = run(c1(action_normalized="interior_painting"))
    assert r["status"] == "NO_KENGETAL" and r["financial_result"]["system_candidate_amount"] is None
    assert_no_effective_amount(r)


def test_multiple_candidates_need_review_without_choice():
    r = run(c1(), ctx=multi_ctx())
    assert r["status"] == "REVIEW_REQUIRED" and r["caveats"]["match_reasons"] == ["MULTIPLE_CANDIDATES"]
    assert r["financial_result"]["system_candidate_kengetal_id"] is None
    assert_no_effective_amount(r)


def test_vat_conflict_needs_review_without_choice():
    r = run(c2(vat_basis="exclusive"))
    assert r["status"] == "REVIEW_REQUIRED" and r["caveats"]["match_reasons"] == ["VAT_BASIS_DIFFERS"]
    assert_no_effective_amount(r)


# --------------------------------------------------------------------------
# Met menselijke beslissing
# --------------------------------------------------------------------------

def test_accept_uses_kengetal_and_exact_total():
    store, rec = decide(c1(), "ACCEPT")
    r = run(c1(), store)
    f = r["financial_result"]
    assert r["status"] == "ACCEPTED" and r["current_decision"]["active_decision_id"] == rec["decision_id"]
    assert f["effective_amount"] == C1_VALUE and f["effective_amount_source"] == "SYSTEM_KENGETAL_ACCEPTED"
    assert Decimal(f["effective_total"]) == Decimal(C1_VALUE) * Decimal("80")    # exact, niet tussentijds afgerond
    assert f["effective_amount_display"] == "33.48" and f["effective_total_display"] == "2678.29"
    assert f["indexation"] == "none" and "NOT_INDEXED" in r["caveats"]["match_caveats"]
    assert r["financial_result"]["price_levels"]["mixed_price_level"] is True


def test_accept_on_review_required_result():
    raw = c1(object_description="betonconstructie plafond buiten")
    store, _ = decide(raw, "ACCEPT", reason="Zelfde betonplafond buiten")
    r = run(raw, store)
    assert r["match_result"]["final_status"] == "HUMAN_REVIEW_REQUIRED" and r["status"] == "ACCEPTED"
    assert r["financial_result"]["effective_amount"] == C1_VALUE


def test_adjust_amount_uses_exact_human_amount_and_keeps_system_value():
    store, _ = decide(c1(), "ADJUST", amount="40.00", amount_basis="offerte aannemer")
    r = run(c1(), store)
    f = r["financial_result"]
    assert r["status"] == "ADJUSTED"
    assert (f["effective_amount"], f["effective_amount_source"], f["human_selected_amount"]) == ("40.00", "HUMAN_ADJUSTMENT", "40.00")
    assert f["system_candidate_amount"] == C1_VALUE and f["amount_basis"] == "offerte aannemer"
    assert Decimal(f["effective_total"]) == Decimal("40.00") * Decimal("80") and f["effective_total_display"] == "3200.00"


def test_adjust_other_kengetal_on_multiple_candidates():
    ctx = multi_ctx()
    store, _ = decide(c1(), "ADJUST", ctx=ctx, chosen_kengetal_id=C1)
    r = run(c1(), store, ctx)
    f = r["financial_result"]
    assert r["status"] == "ADJUSTED" and f["effective_amount_source"] == "HUMAN_SELECTED_KENGETAL"
    assert f["human_selected_kengetal_id"] == C1 and f["effective_amount"] == C1_VALUE


def test_adjust_to_other_kengetal_with_same_unit_is_used_with_total():
    ctx = multi_ctx()   # tweede AVAILABLE kengetal in m2 (kopie van C1), zelfde bron als de matchingtests
    raw = c1(object_description="betonconstructie plafond buiten")
    mr = m.match(PROJECT_ROOT, raw, ctx)
    store, _ = h.add_decision(EMPTY, mr, "ADJUST", "twandijkmans", "zelfde eenheid", schema=DECISION_SCHEMA,
                              match_schema=MATCH_SCHEMA, kengetallen_doc=ctx[0], chosen_kengetal_id=C1 + "-twin",
                              reviewed_at="2026-09-24T12:00:00Z")
    f = run(raw, store, ctx)["financial_result"]
    assert f["human_selected_kengetal_id"] == C1 + "-twin" and f["effective_amount_unit"] == "m2" == f["unit"]
    assert Decimal(f["effective_total"]) == Decimal(f["effective_amount"]) * Decimal("80")


def test_adjust_to_kengetal_with_other_unit_is_refused():
    with pytest.raises(ValueError, match="eenheid"):
        decide(c1(object_description="betonconstructie plafond buiten"), "ADJUST", chosen_kengetal_id=C2)


def test_existing_record_with_other_unit_fails_workflow():
    # een record dat de eenheidsregel schendt (bijv. met de hand toegevoegd) wordt niet gebruikt
    raw = c1(object_description="betonconstructie plafond buiten")
    mr = m.match(PROJECT_ROOT, raw, CTX)
    rec = h.build_record(mr, "ADJUST", "twandijkmans", "andere eenheid", chosen_kengetal_id=C2,
                         reviewed_at="2026-09-24T12:00:00Z")
    with pytest.raises(w.WorkflowError, match="eenheid"):
        w.run(raw, dict(EMPTY, records=[rec]), CTX, root=PROJECT_ROOT)


def test_reject_gives_no_amount():
    store, _ = decide(c1(), "REJECT")
    r = run(c1(), store)
    assert r["status"] == "REJECTED" and r["current_decision"]["status"] == "REJECTED"
    assert_no_effective_amount(r)
    assert r["financial_result"]["system_candidate_amount"] == C1_VALUE


def test_latest_decision_is_leading_and_history_kept():
    s1, r1 = decide(c1(), "ACCEPT")
    mr = m.match(PROJECT_ROOT, c1(), CTX)
    s2, r2 = h.add_decision(s1, mr, "REJECT", "twandijkmans", "later", schema=DECISION_SCHEMA,
                            match_schema=MATCH_SCHEMA, kengetallen_doc=KENGETALLEN, reviewed_at="2026-09-24T13:00:00Z")
    r = run(c1(), s2)
    assert r["status"] == "REJECTED" and r["current_decision"]["history"] == [r1["decision_id"], r2["decision_id"]]


@pytest.mark.parametrize("quantity,reason", [(None, "QUANTITY_MISSING"), ("0", "QUANTITY_NOT_POSITIVE")])
def test_total_only_with_valid_quantity(quantity, reason):
    raw = c1(quantity=quantity)
    store, _ = decide(raw, "ACCEPT")
    f = run(raw, store)["financial_result"]
    assert f["effective_amount"] == C1_VALUE and f["effective_total"] is None and f["total_not_computed_reason"] == reason


def test_decision_for_other_match_result_does_not_apply():
    store, _ = decide(c1(), "ACCEPT")
    r = run(c1(quantity="81"), store)            # andere input -> ander matchresultaat
    assert r["current_decision"]["status"] == "NO_DECISION" and r["status"] == "MATCH_PENDING_DECISION"
    assert_no_effective_amount(r)


# --------------------------------------------------------------------------
# Integriteit
# --------------------------------------------------------------------------

def test_two_active_decisions_fail_explicitly():
    store, _ = decide(c1(), "ACCEPT")
    mr = m.match(PROJECT_ROOT, c1(), CTX)
    bad = copy.deepcopy(store)
    bad["records"].append(h.build_record(mr, "REJECT", "twandijkmans", "tweede", reviewed_at="2026-09-24T13:00:00Z"))
    with pytest.raises(w.WorkflowError):
        w.run(c1(), bad, CTX, root=PROJECT_ROOT)


def test_tampered_active_record_fails_explicitly():
    store, _ = decide(c1(), "ACCEPT")
    bad = copy.deepcopy(store)
    bad["records"][0]["decision_reason"] = "stil gewijzigd"
    with pytest.raises(w.WorkflowError):
        w.run(c1(), bad, CTX, root=PROJECT_ROOT)


def data_hashes():
    out = {}
    for base in ("data", "vocabularies"):
        for dirpath, _, files in os.walk(os.path.join(PROJECT_ROOT, base)):
            for f in files:
                path = os.path.join(dirpath, f)
                out[os.path.relpath(path, PROJECT_ROOT)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return out


def test_full_workflow_does_not_change_data_or_inputs():
    before = data_hashes()
    raw, store_before = c1(), copy.deepcopy(EMPTY)
    raw_before = copy.deepcopy(raw)
    s1, _ = decide(raw, "ACCEPT")
    s2, _ = decide(raw, "ADJUST", store=s1, amount="40.00")
    for store in (EMPTY, s1, s2):
        run(raw, store)
    run(c2(vat_basis="exclusive")), run(c1(action_normalized="interior_painting"))
    assert data_hashes() == before and raw == raw_before and EMPTY == store_before


def test_deterministic_result():
    store, _ = decide(c1(), "ACCEPT")
    a, b = run(c1(), store), run(c1(), store)
    assert w.dump(a) == w.dump(b)
    assert a["workflow_result_id"] != run(c1())["workflow_result_id"]   # andere beslissing -> ander resultaat-ID


def test_provenance_uses_existing_ids_and_hashes():
    store, rec = decide(c1(), "ACCEPT")
    r = run(c1(), store)
    p = r["provenance"]
    assert p["match_result_id"] == r["match_result"]["match_result_id"]
    assert p["match_result_sha256"] == h.canonical_sha256(r["match_result"]) == rec["match_result_sha256"]
    assert p["active_decision_id"] == rec["decision_id"] and p["input_hashes"] == r["match_result"]["input_hashes"]
    assert p["rule_versions"] == {"workflow_version": "mjop_kengetal_workflow_v1", "matching_rule_version": "matching_rules_v1",
                                  "kengetallen_rule_version": "kengetallen_rules_v1",
                                  "human_match_review_version": "human_match_review_v1"}
    assert r["normalization"] == r["match_result"]["input_normalized"] and r["input"] == c1()


def test_cli(tmp_path):
    inp, store_file = tmp_path / "in.json", tmp_path / "store.json"
    inp.write_text(json.dumps(c2()), encoding="utf-8")
    store, _ = decide(c2(), "ACCEPT")
    store_file.write_text(json.dumps(store), encoding="utf-8")
    script = os.path.join(PROJECT_ROOT, "scripts", "mjop_kengetal_workflow.py")
    ok = subprocess.run([sys.executable, script, "--input", str(inp), "--decisions", str(store_file)],
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0 and json.loads(ok.stdout)["status"] == "ACCEPTED"
    bad = subprocess.run([sys.executable, script, "--input", str(inp), "--decisions", str(store_file),
                          "--out", os.path.join(PROJECT_ROOT, "data", "wf.json")], capture_output=True)
    assert bad.returncode == 2 and not os.path.exists(os.path.join(PROJECT_ROOT, "data", "wf.json"))
    broken = copy.deepcopy(store)
    broken["records"][0]["decision_reason"] = "x"
    store_file.write_text(json.dumps(broken), encoding="utf-8")
    err = subprocess.run([sys.executable, script, "--input", str(inp), "--decisions", str(store_file)], capture_output=True)
    assert err.returncode == 3
