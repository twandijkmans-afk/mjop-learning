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


def test_unit_cost_calculated_from_total_and_quantity():
    action = {
        "quantity": {"value": "5911,10"},
        "unit": {"original_value": "m1", "normalized_value": "m1"},
        "unit_cost": {"value": None},
        "total_cost_as_stated": "59508.00",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["unit_cost_calculated"] == "10.07"


def test_unit_cost_calculated_skipped_for_lump_sum():
    action = {
        "quantity": {"value": "1,00"},
        "unit": {"original_value": "pst", "normalized_value": "lump_sum"},
        "unit_cost": {"value": None},
        "total_cost_as_stated": "225692.00",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["unit_cost_calculated"] is None, (
        "Een stelpost is niet deelbaar tot een eenheidsprijs - nooit total/1 als kental presenteren"
    )


def test_unit_cost_calculated_skipped_when_unit_unknown():
    action = {
        "quantity": {"value": "10"},
        "unit": {"original_value": "een rare eenheid", "normalized_value": None},
        "unit_cost": {"value": None},
        "total_cost_as_stated": "1000.00",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["unit_cost_calculated"] is None, (
        "Onbekende eenheid -> niet gokken of hij deelbaar is, eerst vocabulaire aanvullen"
    )


def test_unit_cost_calculated_skipped_when_total_is_zero():
    """Regressie: 'total_cost_as_stated: 0' betekent in deze MJOP-tabellen niet
    'gratis' - het item valt buiten het getoonde jarenvenster (planned_year
    ligt vaak decennia verderop) en krijgt daardoor '€ 0' als totaal in de
    huidige weergave. Een unit_cost_calculated van 0.00 zou dat verkeerd
    voorstellen als een echte prijs (en zo'n kental zou onbruikbaar zijn)."""
    action = {
        "quantity": {"value": "165,80"},
        "unit": {"original_value": "m1", "normalized_value": "m1"},
        "unit_cost": {"value": None},
        "total_cost_as_stated": "€ 0",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["unit_cost_calculated"] is None


def test_to_decimal_handles_euro_formatted_thousands():
    """Regressie: 'total_cost_as_stated' komt bij een LLM-extractie soms
    letterlijk met eurosymbool en Nederlandse duizendtal-punt uit het
    document ('€ 17.910'), i.p.v. de schone vorm die normalize_batch zelf
    schrijft ('1815.00'). Beide moeten correct geparsed worden."""
    assert normalize_batch.to_decimal("€ 17.910") == normalize_batch.to_decimal("17910.00")
    assert normalize_batch.to_decimal("1.815,00") == normalize_batch.to_decimal("1815.00")
    assert normalize_batch.to_decimal("€ 989") == normalize_batch.to_decimal("989.00")
    assert normalize_batch.to_decimal("125.50") == normalize_batch.to_decimal("125.50")  # ongewijzigd gedrag


def test_unit_cost_calculated_from_euro_formatted_total():
    action = {
        "quantity": {"value": "815,95"},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "unit_cost": {"value": None},
        "total_cost_as_stated": "€ 17.910",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["unit_cost_calculated"] is not None


def test_derive_exterior_painting_from_linked_element():
    action = {
        "element_id": "EL-1",
        "action": {"original_value": "Groot schilderwerk kozijn en raam hout dekkend", "normalized_value": None, "requires_human_review": True},
    }
    element_by_id = {"EL-1": {"element_type": {"original_value": "Buitenschilderwerk kozijn en raam hout"}}}
    out = normalize_batch.derive_action_from_linked_element(action, element_by_id)
    assert out["action"]["normalized_value"] == "exterior_painting"
    assert out["action"]["requires_human_review"] is False, (
        "Eenmaal ondubbelzinnig afgeleid via het gekoppelde element hoeft dit niet meer gecontroleerd te worden"
    )
    assert out["action"]["normalization_source"] == "derived_from_linked_element_type"


def test_derive_interior_painting_from_linked_element():
    action = {
        "element_id": "EL-2",
        "action": {"original_value": "Groot schilderwerk stucwerk", "normalized_value": None, "requires_human_review": True},
    }
    element_by_id = {"EL-2": {"element_type": {"original_value": "Binnenschilderwerk stucwerk"}}}
    out = normalize_batch.derive_action_from_linked_element(action, element_by_id)
    assert out["action"]["normalized_value"] == "interior_painting"


def test_derive_skips_when_already_normalized():
    action = {
        "element_id": "EL-1",
        "action": {"original_value": "buitenschilderwerk", "normalized_value": "exterior_painting"},
    }
    element_by_id = {"EL-1": {"element_type": {"original_value": "Binnenschilderwerk stucwerk"}}}
    out = normalize_batch.derive_action_from_linked_element(action, element_by_id)
    assert out["action"]["normalized_value"] == "exterior_painting", (
        "Een al opgeloste waarde mag nooit overschreven worden door de afleidingsregel"
    )


def test_derive_skips_when_action_text_has_no_schilderwerk():
    action = {
        "element_id": "EL-1",
        "action": {"original_value": "Herstellen kozijn hardhout", "normalized_value": None, "requires_human_review": True},
    }
    element_by_id = {"EL-1": {"element_type": {"original_value": "Buitenschilderwerk kozijn"}}}
    out = normalize_batch.derive_action_from_linked_element(action, element_by_id)
    assert out["action"]["normalized_value"] is None
    assert out["action"]["requires_human_review"] is True


def test_derive_skips_when_linked_element_type_ambiguous():
    action = {
        "element_id": "EL-3",
        "action": {
            "original_value": "Vervangen kitvoeg achterzijde gelijktijdig met schilderwerk",
            "normalized_value": None,
            "requires_human_review": True,
        },
    }
    element_by_id = {"EL-3": {"element_type": {"original_value": "Kitvoeg t.p.v. elementen > 5mm tot 10 mm"}}}
    out = normalize_batch.derive_action_from_linked_element(action, element_by_id)
    assert out["action"]["normalized_value"] is None, (
        "Geen ondubbelzinnige buiten/binnen-koppeling -> niet gokken, blijft voor mens"
    )
    assert out["action"]["requires_human_review"] is True


def test_derive_skips_when_element_missing():
    action = {
        "element_id": "EL-DOES-NOT-EXIST",
        "action": {"original_value": "Groot schilderwerk hout dekkend", "normalized_value": None, "requires_human_review": True},
    }
    out = normalize_batch.derive_action_from_linked_element(action, {})
    assert out["action"]["normalized_value"] is None


def test_bubble_action_review_flag_from_nested_action_pair():
    action = {
        "action": {"original_value": "een compleet onbekende actie", "normalized_value": None, "requires_human_review": True},
    }
    out = normalize_batch.bubble_action_review_flag(action)
    assert out["requires_human_review"] is True, (
        "Zonder deze bubbling verdwijnt een post met een onbekende actieterm stilzwijgend uit de review-wachtrij"
    )


def test_bubble_action_review_flag_from_nested_unit_pair():
    action = {
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "unit": {"original_value": "een rare eenheid", "normalized_value": None, "requires_human_review": True},
    }
    out = normalize_batch.bubble_action_review_flag(action)
    assert out["requires_human_review"] is True


def test_bubble_action_review_flag_leaves_resolved_action_untouched():
    action = {"action": {"original_value": "vervangen", "normalized_value": "replace"}}
    out = normalize_batch.bubble_action_review_flag(action)
    assert out.get("requires_human_review", False) is False


def test_bubble_observation_review_flag():
    obs = {"defect": {"original_value": "een rare term", "normalized_value": None, "requires_human_review": True}}
    out = normalize_batch.bubble_observation_review_flag(obs)
    assert out["requires_human_review"] is True


def test_unit_cost_calculated_skipped_when_literal_unit_cost_present():
    action = {
        "quantity": {"value": "10"},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "unit_cost": {"value": "50.00"},
        "total_cost_as_stated": "500.00",
    }
    out = normalize_batch.normalize_maintenance_action(dict(action))
    assert out["unit_cost_calculated"] is None, (
        "Als het document al een letterlijke eenheidsprijs geeft, is een berekende versie overbodig"
    )
    assert out["direct_cost_calculated"] == "500.00"
