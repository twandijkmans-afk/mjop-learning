"""
Tests voor scripts/normalize_batch.py - de enige plek in de pipeline waar
"AI-achtige" output automatisch tot stand komt zonder mens ertussen, dus
hier moeten de CLAUDE.md-regels het strengst getest worden:
  - onbekende termen worden NOOIT geraden (normalized_value=null + review)
  - kostenberekeningen zijn deterministisch en reproduceerbaar
  - een conflict tussen vermeld totaalbedrag en berekend bedrag wordt
    gemarkeerd, niet automatisch opgelost
"""
import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

spec = importlib.util.spec_from_file_location(
    "normalize_batch", os.path.join(PROJECT_ROOT, "scripts", "normalize_batch.py")
)
normalize_batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(normalize_batch)


def test_known_term_gets_normalized():
    lookup = {"gevel": "facade"}
    pair = {"original_value": "gevel", "normalized_value": None}
    out = normalize_batch.normalize_pair(pair, lookup)
    assert out["normalized_value"] == "facade"


def test_unknown_term_stays_null_and_flagged():
    lookup = {"gevel": "facade"}
    pair = {"original_value": "een heel raar bouwdeel", "normalized_value": None}
    out = normalize_batch.normalize_pair(pair, lookup)
    assert out["normalized_value"] is None, "Onbekende term mag nooit geraden worden"
    assert out["requires_human_review"] is True


def test_missing_original_value_untouched():
    pair = {"original_value": None, "normalized_value": None}
    out = normalize_batch.normalize_pair(pair, {"gevel": "facade"})
    assert out == pair


def test_deterministic_cost_calculation():
    action = {
        "quantity": {"value": "12"},
        "unit_cost": {"value": "125.50"},
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["direct_cost_calculated"] == "1506.00"

    # nogmaals draaien moet exact hetzelfde resultaat geven (reproduceerbaar)
    out2 = normalize_batch.normalize_maintenance_action(dict(action))
    assert out2["direct_cost_calculated"] == out["direct_cost_calculated"]


def test_cost_conflict_is_flagged_not_resolved():
    action = {
        "quantity": {"value": "10"},
        "unit_cost": {"value": "100.00"},
        "total_cost_as_stated": "5000.00",  # wijkt af van 10 x 100 = 1000.00
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["direct_cost_calculated"] == "1000.00"
    assert out["cost_conflict"] is True
    assert out["requires_human_review"] is True
    # BELANGRIJK: het script kiest geen van beide bedragen als "het juiste" -
    # total_cost_as_stated blijft ongewijzigd staan naast de berekening
    assert out["total_cost_as_stated"] == "5000.00"


def test_no_conflict_when_costs_match():
    action = {
        "quantity": {"value": "4"},
        "unit_cost": {"value": "250.00"},
        "total_cost_as_stated": "1000.00",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out.get("cost_conflict", False) is False


def test_missing_quantity_or_cost_no_calculation():
    action = {"quantity": {"value": None}, "unit_cost": {"value": "100.00"}}
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert "direct_cost_calculated" not in out, (
        "Zonder quantity mag er geen berekend bedrag verschijnen (geen aanname invullen)"
    )
