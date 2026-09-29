"""
Tests voor scripts/mjop_maintenance_line.py - domeinmodel voor één onderhoudsregel van
een nieuw MJOP (docs/mjop_maintenance_line_v1.md). Workflow-integratie met echte
C1/C2-matchresultaten; beslissingen alleen in het geheugen.
"""
import copy
import hashlib
import os
import sys
from decimal import Decimal

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import human_match_review as h  # noqa: E402
import match_kengetal as m  # noqa: E402
import mjop_maintenance_line as L  # noqa: E402
import promotion_history as ph  # noqa: E402

# Na de canonieke promotie van batch1_v1 is C1 (4645) geen canoniek kengetal meer. Deze workflowtests
# gebruiken de pre-promotie-kengetallen (C1/C2) uit data/history als vaste, alleen-lezen fixture.
FIXTURE_ROOT = ph.pre_promotion_fixture_root(PROJECT_ROOT)
HP = h.paths(FIXTURE_ROOT)
DECISION_SCHEMA, MATCH_SCHEMA = h.load_json(HP["schema"]), h.load_json(HP["match_schema"])
KENGETALLEN, EMPTY = h.load_json(HP["kengetallen"]), h.load_json(HP["store"])
CTX = m.load_context(FIXTURE_ROOT)
C1 = "KG-4645-exterior_painting-m2-concrete-2f1a7a14"
C1_VALUE = next(k for k in KENGETALLEN["kengetallen"] if k["kengetal_id"] == C1)["value_exact"]


def c1_line(**over):
    base = dict(element_code_internal="4645", action_normalized="exterior_painting", unit_normalized="m2",
                material_normalized="concrete", material_source="user",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80", vat_basis="inclusive",
                planned_year=2028, cycle_years=14, context={"construction_year": 1975, "building_type": "VvE"})
    base.update(over)
    return L.new_line("ML-1", "MJOP-TEST", "OBJ-1", **base)


def c2_line(**over):
    base = dict(element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive")
    base.update(over)
    return L.new_line("ML-2", "MJOP-TEST", "OBJ-2", **base)


def with_decision(line, decision, store=EMPTY, ctx=CTX, **kw):
    _, result = L.run_workflow_for_line(line, store, ctx, root=PROJECT_ROOT)
    new_store, _ = h.add_decision(store, result["match_result"], decision, "twandijkmans", "reden",
                                  schema=DECISION_SCHEMA, match_schema=MATCH_SCHEMA, kengetallen_doc=KENGETALLEN,
                                  reviewed_at="2026-09-24T12:00:00Z", **kw)
    return L.run_workflow_for_line(line, new_store, ctx, root=PROJECT_ROOT)[0]


# --------------------------------------------------------------------------
# Basis
# --------------------------------------------------------------------------

def test_minimal_valid_line():
    line = L.new_line("ML-0", "MJOP-TEST", "OBJ-0")
    assert (line["line_status"], line["price_status"]) == ("DRAFT", "NO_AMOUNT")
    assert line["financial"]["unit_amount"] is None and L.line_errors(line) == []


def test_line_without_amount_is_valid():
    line = c1_line(quantity=None)
    assert line["price_status"] == "NO_AMOUNT" and line["financial"]["effective_total"] is None
    assert L.line_errors(line) == []


def test_manual_amount():
    line = L.set_manual_amount(c1_line(), "45.00", "m2", "2026", "inclusive", "offerte schilder")
    f = line["financial"]
    assert (line["price_status"], line["line_status"], f["amount_source"]) == ("MANUALLY_SET", "READY", "MANUAL_AMOUNT")
    assert line["manual_amount"] == {"amount": "45.00", "unit": "m2", "price_level": "2026", "vat_basis": "inclusive",
                                     "reason": "offerte schilder", "source": "MANUAL_AMOUNT"}
    assert f["effective_total"] == "3600.00" and f["indexation"] == "none"


def test_system_kengetal_without_decision_is_only_a_proposal():
    line, result = L.run_workflow_for_line(c1_line(), EMPTY, CTX, root=PROJECT_ROOT)
    assert result["match_result"]["final_status"] == "CANDIDATE_FOUND"
    assert (line["price_status"], line["line_status"]) == ("SYSTEM_PROPOSED", "REVIEW_REQUIRED")
    assert line["kengetal_match"]["kengetal_id"] == C1 and line["kengetal_match"]["system_candidate_amount"] == C1_VALUE
    assert line["financial"]["unit_amount"] is None and line["financial"]["effective_total"] is None


def test_human_accept_c1_exact_total():
    line = with_decision(c1_line(), "ACCEPT")
    f = line["financial"]
    assert (line["price_status"], line["line_status"], f["amount_source"]) == ("HUMAN_ACCEPTED", "READY", "SYSTEM_KENGETAL")
    assert Decimal(f["effective_total"]) == Decimal(C1_VALUE) * Decimal("80")
    assert f["effective_total"].startswith("2678.2884") and f["effective_total_display"] == "2678.29"
    assert f["unit_amount_display"] == "33.48" and line["kengetal_match"]["human_match_decision_id"].startswith("HMD-")


def test_human_adjust():
    line = with_decision(c1_line(), "ADJUST", amount="40.00", amount_basis="offerte")
    f = line["financial"]
    assert (line["price_status"], f["amount_source"], f["unit_amount"]) == ("HUMAN_ADJUSTED", "HUMAN_ADJUSTMENT", "40.00")
    assert Decimal(f["effective_total"]) == Decimal("3200") and line["kengetal_match"]["system_candidate_amount"] == C1_VALUE


def test_human_reject():
    line = with_decision(c1_line(), "REJECT")
    assert (line["price_status"], line["line_status"]) == ("REJECTED", "DRAFT")
    assert line["financial"]["unit_amount"] is None and line["kengetal_match"]["decision_status"] == "REJECTED"


def test_c2_accept():
    line = with_decision(c2_line(), "ACCEPT")
    assert line["price_status"] == "HUMAN_ACCEPTED" and line["financial"]["unit"] == "m1"
    assert line["financial"]["price_level"]["missing_price_level"] is True   # C2: DOC-001 zonder prijspeil


@pytest.mark.parametrize("over,price,line_status", [
    ({"action_normalized": "interior_painting"}, "NO_AMOUNT", "DRAFT"),          # geen kengetal
    ({"object_description": "betonconstructie plafond buiten"}, "SYSTEM_PROPOSED", "REVIEW_REQUIRED"),
    ({"vat_basis": "exclusive"}, "SYSTEM_PROPOSED", "REVIEW_REQUIRED"),           # btw-review
])
def test_workflow_outcomes_without_decision(over, price, line_status):
    line, _ = L.run_workflow_for_line(c1_line(**over), EMPTY, CTX, root=PROJECT_ROOT)
    assert (line["price_status"], line["line_status"]) == (price, line_status)
    assert line["financial"]["unit_amount"] is None


def test_multiple_candidates_no_amount_review_required():
    kengetallen, normalized, vocabs, hashes, rel = copy.deepcopy(CTX)
    twin = copy.deepcopy(next(k for k in kengetallen["kengetallen"] if k["kengetal_id"] == C1))
    twin["kengetal_id"] = C1 + "-twin"
    kengetallen["kengetallen"].append(twin)
    line, _ = L.run_workflow_for_line(c1_line(), EMPTY, (kengetallen, normalized, vocabs, hashes, rel), root=PROJECT_ROOT)
    assert (line["price_status"], line["line_status"]) == ("NO_AMOUNT", "REVIEW_REQUIRED")


# --------------------------------------------------------------------------
# Validatie
# --------------------------------------------------------------------------

def broken(line, path, value):
    bad = copy.deepcopy(line)
    target = bad
    for p in path[:-1]:
        target = target[p]
    target[path[-1]] = value
    return L.line_errors(bad)


@pytest.mark.parametrize("path,value", [
    (("quantity",), "-5"),
    (("quantity",), "0"),
    (("line_status",), "DONE"),
    (("price_status",), "APPROVED"),
    (("financial", "amount_source"), "GUESS"),
    (("financial", "unit_amount"), "-1.00"),
])
def test_invalid_values_fail(path, value):
    assert broken(c1_line(), path, value)


def test_missing_unit_with_amount_fails():
    line = L.set_manual_amount(c1_line(), "45.00", "m2", "2026", "inclusive", "offerte")
    assert broken(line, ("financial", "unit"), None)


def test_adjust_without_decision_fails():
    line = with_decision(c1_line(), "ADJUST", amount="40.00")
    assert broken(line, ("kengetal_match", "human_match_decision_id"), None)
    no_match = copy.deepcopy(line)
    no_match["kengetal_match"] = None
    assert L.line_errors(no_match)


def test_human_selected_kengetal_requires_decision():
    line = with_decision(c1_line(), "ACCEPT")
    bad = copy.deepcopy(line)
    bad["financial"]["amount_source"] = "HUMAN_SELECTED_KENGETAL"   # zonder ADJUST-beslissing
    assert L.line_errors(bad)


def test_effective_amount_without_valid_source_fails():
    line = c1_line()
    bad = copy.deepcopy(line)
    bad["financial"].update(unit_amount="30.00", unit_amount_display="30.00", unit="m2")   # geen amount_source
    assert L.line_errors(bad)


def test_effective_total_without_valid_quantity_fails():
    line = L.set_manual_amount(c1_line(quantity=None), "45.00", "m2", "2026", "inclusive", "offerte")
    assert line["financial"]["effective_total"] is None and line["financial"]["total_not_computed_reason"] == "QUANTITY_MISSING"
    assert broken(line, ("financial", "effective_total"), "999")


def test_total_must_match_amount_times_quantity():
    line = L.set_manual_amount(c1_line(), "45.00", "m2", "2026", "inclusive", "offerte")
    assert broken(line, ("financial", "effective_total"), "3600.01")


# --------------------------------------------------------------------------
# Eenheden
# --------------------------------------------------------------------------

def test_units_no_conversion():
    line = c1_line()
    assert L.set_manual_amount(line, "45", "m2", None, "inclusive", "ok")["financial"]["unit"] == "m2"
    for wrong in ("m1", "m²", "piece"):                  # geen conversie, ook niet 'm²' -> 'm2'
        with pytest.raises(L.LineError):
            L.set_manual_amount(line, "45", wrong, None, "inclusive", "fout")
    ok = L.set_manual_amount(line, "45", "m2", None, "inclusive", "ok")
    assert broken(ok, ("financial", "unit"), "m1")


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------

def test_construction_year_is_not_maintenance_year():
    line = c1_line()
    assert line["context"]["construction_year"] == 1975
    assert line["last_maintenance_year"] is None and line["last_replacement_year"] is None


def test_unknown_years_stay_null_and_planned_year_is_independent():
    line = c1_line(planned_year=None, cycle_years=None)
    assert all(line[k] is None for k in ("planned_year", "cycle_years", "last_maintenance_year",
                                         "last_replacement_year", "proposed_planned_year"))
    a = L.update_user_fields(line, planned_year=2030)
    assert a["planned_year"] == 2030 and a["last_maintenance_year"] is None
    b = L.update_user_fields(a, last_maintenance_year=2019)
    assert b["planned_year"] == 2030 and b["last_maintenance_year"] == 2019


def test_proposed_planned_year_not_filled_in_v1():
    assert broken(c1_line(), ("proposed_planned_year",), 2031)


# --------------------------------------------------------------------------
# Financieel
# --------------------------------------------------------------------------

def test_decimal_without_intermediate_rounding():
    line = L.set_manual_amount(c1_line(quantity="3"), "33.478605388272583", "m2", None, "inclusive", "exact")
    assert line["financial"]["effective_total"] == "100.435816164817749"
    assert line["financial"]["effective_total_display"] == "100.44"


def test_no_total_without_quantity():
    line = with_decision(c1_line(quantity=None), "ACCEPT")
    assert line["financial"]["unit_amount"] == C1_VALUE and line["financial"]["effective_total"] is None


# --------------------------------------------------------------------------
# Mutability en relatie met de workflow
# --------------------------------------------------------------------------

def test_system_derived_fields_are_not_user_editable():
    for field in ("price_status", "financial", "kengetal_match", "provenance", "line_status", "proposed_planned_year"):
        with pytest.raises(L.LineError):
            L.update_user_fields(c1_line(), **{field: None})
    with pytest.raises(L.LineError):
        L.new_line("ML-9", "MJOP", "OBJ", price_status="HUMAN_ACCEPTED")


def test_changing_match_input_invalidates_kengetal_price_but_planning_does_not():
    accepted = with_decision(c1_line(), "ACCEPT")
    planning = L.update_user_fields(accepted, planned_year=2031, cycle_years=12)
    assert planning["price_status"] == "HUMAN_ACCEPTED" and planning["financial"] == accepted["financial"]
    changed = L.update_user_fields(accepted, quantity="90")
    assert (changed["price_status"], changed["kengetal_match"], changed["financial"]["unit_amount"]) == ("NO_AMOUNT", None, None)


def test_manual_amount_stays_leading_over_workflow():
    manual = L.set_manual_amount(c1_line(), "45.00", "m2", "2026", "inclusive", "offerte")
    after, _ = L.run_workflow_for_line(manual, EMPTY, CTX, root=PROJECT_ROOT)
    assert after["price_status"] == "MANUALLY_SET" and after["financial"]["unit_amount"] == "45.00"
    assert after["kengetal_match"]["kengetal_id"] == C1                   # voorstel wel zichtbaar
    requantified = L.update_user_fields(manual, quantity="10")
    assert requantified["financial"]["effective_total"] == "450.00"
    other_unit = L.update_user_fields(manual, unit_normalized="m1")
    assert other_unit["price_status"] == "NO_AMOUNT" and other_unit["manual_amount"] is None


def test_clear_manual_amount_without_fallback():
    accepted = with_decision(c1_line(), "ACCEPT")                          # eerst een kengetalbedrag
    manual = L.set_manual_amount(accepted, "45.00", "m2", "2026", "inclusive", "offerte")
    assert manual["price_status"] == "MANUALLY_SET" and manual["financial"]["unit_amount"] == "45.00"
    cleared = L.clear_manual_amount(manual)
    f = cleared["financial"]
    assert (cleared["price_status"], cleared["line_status"]) == ("NO_AMOUNT", "DRAFT")
    assert cleared["manual_amount"] is None and cleared["kengetal_match"] is None and cleared["provenance"] is None
    assert (f["amount_source"], f["unit_amount"], f["effective_total"]) == (None, None, None)   # geen fallback
    assert L.line_errors(cleared) == [] and manual["price_status"] == "MANUALLY_SET"           # invoer niet gemuteerd
    with pytest.raises(L.LineError):
        L.clear_manual_amount(cleared)                                     # niets meer te wissen


def test_workflow_can_run_again_after_clearing():
    line = c1_line()
    _, result = L.run_workflow_for_line(line, EMPTY, CTX, root=PROJECT_ROOT)
    decided_store, _ = h.add_decision(EMPTY, result["match_result"], "ACCEPT", "twandijkmans", "ok",
                                      schema=DECISION_SCHEMA, match_schema=MATCH_SCHEMA, kengetallen_doc=KENGETALLEN,
                                      reviewed_at="2026-09-24T12:00:00Z")
    cleared = L.clear_manual_amount(L.set_manual_amount(line, "45.00", "m2", None, "inclusive", "tijdelijk"))
    again, _ = L.run_workflow_for_line(cleared, decided_store, CTX, root=PROJECT_ROOT)
    assert again["price_status"] == "HUMAN_ACCEPTED" and again["financial"]["unit_amount"] == C1_VALUE
    fresh, _ = L.run_workflow_for_line(cleared, EMPTY, CTX, root=PROJECT_ROOT)
    assert fresh["price_status"] == "SYSTEM_PROPOSED" and fresh["financial"]["unit_amount"] is None


def test_clear_manual_amount_does_not_change_existing_data():
    before = data_hashes()
    L.clear_manual_amount(L.set_manual_amount(with_decision(c1_line(), "ACCEPT"), "45", "m2", None, None, "x"))
    assert data_hashes() == before


def test_vat_basis_is_taken_over_not_derived():
    # kengetalbedrag: btw-basis van de regel (door de matching tegen het kengetal gecontroleerd)
    assert with_decision(c1_line(), "ACCEPT")["financial"]["vat_basis"] == "inclusive"
    assert with_decision(c1_line(), "ADJUST", amount="40.00")["financial"]["vat_basis"] == "inclusive"
    # onbekende btw-basis blijft onbekend: niet afgeleid uit het kengetal (dat incl. btw is)
    assert with_decision(c1_line(vat_basis=None), "ACCEPT")["financial"]["vat_basis"] is None
    # bekend verschil: de matching vraagt review, geen bedrag
    line, _ = L.run_workflow_for_line(c1_line(vat_basis="exclusive"), EMPTY, CTX, root=PROJECT_ROOT)
    assert line["kengetal_match"]["match_reasons"] == ["VAT_BASIS_DIFFERS"] and line["financial"]["unit_amount"] is None
    # handmatig bedrag: de door de gebruiker opgegeven btw-basis, zonder conversie van het bedrag
    manual = L.set_manual_amount(c1_line(), "45.00", "m2", "2026", "exclusive", "offerte excl. btw")
    assert manual["financial"]["vat_basis"] == "exclusive" and manual["financial"]["unit_amount"] == "45.00"


def test_workflow_result_of_other_line_is_refused():
    _, result = L.run_workflow_for_line(c2_line(), EMPTY, CTX, root=PROJECT_ROOT)
    with pytest.raises(L.LineError):
        L.apply_workflow_result(c1_line(), result)


def test_workflow_input_matches_existing_input_object():
    item = L.to_workflow_input(c1_line())
    assert item["object_id"] == "OBJ-1" and item["construction_year"] == 1975 and "planned_year" not in item
    assert m.match(PROJECT_ROOT, item, CTX)["final_status"] == "CANDIDATE_FOUND"


def test_provenance_uses_existing_ids():
    line = with_decision(c1_line(), "ACCEPT")
    p = line["provenance"]
    assert p["workflow_result_id"].startswith("WF-") and len(p["match_result_sha256"]) == 64
    assert p["rule_versions"]["matching_rule_version"] == "matching_rules_v1"
    assert line["kengetal_match"]["match_result_id"].startswith("MR-")


def test_functions_do_not_mutate_input_and_are_deterministic():
    line = c1_line()
    before = copy.deepcopy(line)
    a = with_decision(line, "ACCEPT")
    b = with_decision(line, "ACCEPT")
    L.set_manual_amount(line, "1", "m2", None, None, "x")
    L.update_user_fields(line, quantity="5")
    assert line == before and a == b


# --------------------------------------------------------------------------
# Data-integriteit
# --------------------------------------------------------------------------

def data_hashes():
    out = {}
    for base in ("data", "vocabularies"):
        for dirpath, _, files in os.walk(os.path.join(PROJECT_ROOT, base)):
            for f in files:
                path = os.path.join(dirpath, f)
                out[os.path.relpath(path, PROJECT_ROOT)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return out


def test_domain_layer_does_not_change_existing_data():
    before = data_hashes()
    line = with_decision(c1_line(), "ADJUST", amount="40.00")
    L.set_manual_amount(line, "50", "m2", "2026", "inclusive", "offerte")
    with_decision(c2_line(), "REJECT")
    assert data_hashes() == before
