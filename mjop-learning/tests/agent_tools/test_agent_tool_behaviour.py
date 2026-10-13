"""Gedragstests: kandidaat zonder menselijk besluit krijgt NOOIT een effectieve prijs; menselijke besluiten worden
ongewijzigd overgenomen; bedragen zijn Decimal-strings; de uitvoer faalt gesloten bij een contractbreuk."""
import copy
import json
import re

import pytest

import support  # noqa: F401
from support import FIXTURE_ROOT, PROJECT_ROOT, root_with_store

import human_match_review as h
import match_kengetal as m
import mjop_kengetal_workflow as w
from agent.contract import ToolError
from agent.tools import get_kengetal_candidates as mod
from agent.tools.get_kengetal_candidates import get_kengetal_candidates

C1 = "KG-4645-exterior_painting-m2-concrete-2f1a7a14"
C2 = "KG-5211-replace-m1-pvc-67920b77"
HP = h.paths(FIXTURE_ROOT)
KENGETALLEN = h.load_json(HP["kengetallen"])
DECISION_SCHEMA, MATCH_SCHEMA = h.load_json(HP["schema"]), h.load_json(HP["match_schema"])
EMPTY = h.load_json(HP["store"])
CTX = m.load_context(FIXTURE_ROOT)
DECIMAL = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")


def value_of(kid):
    return next(k for k in KENGETALLEN["kengetallen"] if k["kengetal_id"] == kid)["value_exact"]


def c1(**over):
    base = dict(object_id="MJOP-1", element_code_internal="4645", action_normalized="exterior_painting",
                unit_normalized="m2", material_normalized="concrete", material_source="user",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80", vat_basis="inclusive")
    base.update(over)
    return base


def c2(**over):
    base = dict(object_id="MJOP-2", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive")
    base.update(over)
    return base


def run(raw, root=FIXTURE_ROOT):
    return get_kengetal_candidates(raw, root=root)


def decided(tmp_path, raw, decision, **kw):
    mr = m.match(FIXTURE_ROOT, raw, CTX)
    store, rec = h.add_decision(EMPTY, mr, decision, "twandijkmans", kw.pop("reason", "reden"), schema=DECISION_SCHEMA,
                                match_schema=MATCH_SCHEMA, kengetallen_doc=KENGETALLEN,
                                reviewed_at="2026-09-24T12:00:00Z", **kw)
    return root_with_store(tmp_path, store), rec


def assert_no_effective_price(out):
    pp = out["price_presentation"]
    assert pp["is_accepted_price"] is False
    assert pp["effective_amount"] is None and pp["effective_amount_unit"] is None
    assert pp["effective_amount_source"] is None
    f = out["financial_result"]
    assert f["effective_amount"] is None and f["effective_total"] is None and f["effective_amount_source"] is None
    assert all(c["is_accepted_price"] is False and c["presentation"] == "SYSTEM_CANDIDATE_NOT_ACCEPTED"
               for c in out["candidates"])
    assert out["decision_state"] in ("NO_HUMAN_DECISION", "HUMAN_REJECTED")


# --- zonder besluit: nooit een effectieve prijs ------------------------------------------------------------------

@pytest.mark.parametrize("raw,kid", [
    (c1(), C1),
    (c2(), C2),
    (c1(object_description="betonconstructie plafond buiten"), C1),   # ander woordgebruik: review vereist
    (c2(vat_basis="exclusive"), C2),                                 # BTW-verschil: review vereist
])
def test_candidate_without_human_decision_has_no_effective_price(raw, kid):
    out = run(raw)
    assert out["decision_state"] == "NO_HUMAN_DECISION"
    assert out["status"] in ("MATCH_PENDING_DECISION", "REVIEW_REQUIRED")
    assert [c["kengetal_id"] for c in out["candidates"]] == [kid]
    assert_no_effective_price(out)
    assert out["price_presentation"]["label"] == "SYSTEM_CANDIDATE_NOT_ACCEPTED"
    assert "GEEN geaccepteerde prijs" in out["price_presentation"]["statement"]
    # het voorstel is zichtbaar als informatie, niet als prijs
    assert out["price_presentation"]["system_candidate_amount"] == value_of(kid)
    assert out["candidates"][0]["value_exact"] == value_of(kid)


def test_exact_candidate_is_the_proposed_one_but_not_accepted():
    out = run(c2())
    assert out["status"] == "MATCH_PENDING_DECISION"
    c = out["candidates"][0]
    assert c["is_proposed_candidate"] is True and c["scope_status"] == "EXACT_MATCH"
    assert c["is_accepted_price"] is False
    assert out["financial_result"]["total_not_computed_reason"] == "NO_EFFECTIVE_AMOUNT"


@pytest.mark.parametrize("raw", [c2(element_code_internal="9999"), c2(material_normalized="unobtainium"),
                                 c2(unit_normalized="m2"), c2(action_normalized="inspect")])
def test_no_candidate_gives_no_price(raw):
    out = run(raw)
    assert out["status"] == "NO_KENGETAL" and out["candidates"] == []
    assert out["price_presentation"]["label"] == "NO_PRICE"
    assert_no_effective_price(out)


def test_missing_material_is_not_guessed():
    raw = c2()
    del raw["material_normalized"], raw["material_source"]
    out = run(raw)
    assert out["status"] == "NO_KENGETAL" and out["candidates"] == []
    assert "MATERIAL_UNKNOWN" in out["caveats"]["match_reasons"]


# --- met menselijk besluit: alleen dan een effectieve prijs ---------------------------------------------------------

def test_accept_gives_effective_price_from_the_kengetal_unchanged(tmp_path):
    root, rec = decided(tmp_path, c2(), "ACCEPT")
    out = run(c2(), root=root)
    assert out["decision_state"] == "HUMAN_ACCEPTED" and out["status"] == "ACCEPTED"
    pp = out["price_presentation"]
    assert pp["is_accepted_price"] is True and pp["label"] == "HUMAN_ACCEPTED_PRICE"
    assert pp["effective_amount"] == value_of(C2) and pp["effective_amount_source"] == "SYSTEM_KENGETAL_ACCEPTED"
    assert out["candidates"][0]["presentation"] == "HUMAN_SELECTED" and out["candidates"][0]["is_accepted_price"]
    assert out["current_decision"]["active_decision_id"] == rec["decision_id"]
    from decimal import Decimal
    assert out["financial_result"]["effective_total"] == format(Decimal(value_of(C2)) * Decimal("100"), "f")


def test_adjust_uses_the_human_amount(tmp_path):
    root, _ = decided(tmp_path, c2(), "ADJUST", chosen_kengetal_id=C2, amount="60.00", amount_basis="offerte")
    out = run(c2(), root=root)
    assert out["decision_state"] == "HUMAN_ADJUSTED"
    pp = out["price_presentation"]
    assert pp["is_accepted_price"] and pp["effective_amount"] == "60.00" and pp["label"] == "HUMAN_ADJUSTED_PRICE"
    assert pp["effective_amount_source"] == "HUMAN_ADJUSTMENT"
    assert pp["system_candidate_amount"] == value_of(C2)     # het systeemvoorstel blijft apart zichtbaar


def test_reject_gives_no_price_even_though_a_candidate_exists(tmp_path):
    root, _ = decided(tmp_path, c2(), "REJECT")
    out = run(c2(), root=root)
    assert out["decision_state"] == "HUMAN_REJECTED" and out["status"] == "REJECTED"
    assert out["price_presentation"]["label"] == "REJECTED_BY_HUMAN"
    assert_no_effective_price(out)


def test_decision_for_another_input_does_not_leak(tmp_path):
    root, _ = decided(tmp_path, c2(), "ACCEPT")
    other = run(c2(quantity="7"), root=root)     # ander genormaliseerd input-object => ander match_result_id
    assert other["decision_state"] == "NO_HUMAN_DECISION"
    assert_no_effective_price(other)


# --- Decimal-strings, nooit floats ----------------------------------------------------------------------------------

def _walk(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, node


def test_amounts_are_decimal_strings_and_no_floats_anywhere(tmp_path):
    root, _ = decided(tmp_path, c2(), "ACCEPT")
    for out in (run(c1()), run(c2()), run(c2(), root=root)):
        for path, value in _walk(out):
            assert not isinstance(value, float), path
        for c in out["candidates"]:
            for f in ("value_exact", "value_display", "min_exact", "max_exact"):
                assert DECIMAL.match(c[f]), f
            for sc in c["source_clusters"]:
                assert DECIMAL.match(sc["contribution_exact"])
        for key in ("effective_amount", "system_candidate_amount"):
            v = out["price_presentation"][key]
            assert v is None or DECIMAL.match(v)


# --- fail-closed ----------------------------------------------------------------------------------------------------

def test_fail_closed_if_the_workflow_ever_returned_an_effective_amount_without_a_decision(monkeypatch):
    real_run = w.run

    def corrupted(*args, **kwargs):
        r = real_run(*args, **kwargs)
        r = copy.deepcopy(r)
        r["financial_result"]["effective_amount"] = r["financial_result"]["system_candidate_amount"]
        return r
    monkeypatch.setattr(mod.mjop_kengetal_workflow, "run", corrupted)
    with pytest.raises(ToolError) as e:
        run(c2())
    assert e.value.code == "OUTPUT_CONTRACT_VIOLATION"


def test_fail_closed_on_integrity_error_in_the_decision_store(tmp_path):
    mr = m.match(FIXTURE_ROOT, c2(), CTX)
    store, _ = h.add_decision(EMPTY, mr, "ACCEPT", "twandijkmans", "r", schema=DECISION_SCHEMA, match_schema=MATCH_SCHEMA,
                              kengetallen_doc=KENGETALLEN, reviewed_at="2026-09-24T12:00:00Z")
    bad = copy.deepcopy(store)
    bad["records"].append(copy.deepcopy(bad["records"][0]))          # twee ACTIVE records voor één match
    bad["records"][1]["decision_id"] = "HMDR-DUPLICATE"
    with pytest.raises(ToolError) as e:
        run(c2(), root=root_with_store(tmp_path, bad))
    assert e.value.code == "SOURCE_INTEGRITY_ERROR"


def test_workflow_result_schema_still_validates_the_underlying_result():
    r = w.run(c2(), EMPTY, CTX, root=FIXTURE_ROOT)
    assert w.validate_output(r, w.paths(PROJECT_ROOT)["schema"]) == []
