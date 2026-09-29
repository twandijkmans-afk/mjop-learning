"""
Tests voor scripts/compute_kentallen.py - de stap die daadwerkelijk
kentallen (eenheidsprijs-benchmarks) berekent. Test vooral de filters:
alleen betrouwbare, ondubbelzinnig gecategoriseerde posten mogen meetellen,
en literal/calculated prijzen worden nooit gemengd tot 1 cijfer.
"""
import importlib.util
import os
import sys
from decimal import Decimal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

spec = importlib.util.spec_from_file_location(
    "compute_kentallen", os.path.join(PROJECT_ROOT, "scripts", "compute_kentallen.py")
)
ck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ck)


def make_action(**overrides):
    action = {
        "action_id": "A-1",
        "element_id": "EL-1",
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "unit_cost": {"value": None},
        "unit_cost_calculated": None,
        "cost_year": 2026,
        "requires_human_review": False,
        "cost_conflict": False,
    }
    action.update(overrides)
    return action


def make_element(**overrides):
    element = {
        "element_id": "EL-1",
        "element_code": {"original_value": "4711", "normalized_value": "4711"},
    }
    element.update(overrides)
    return element


def test_is_reliable_rejects_flagged_action():
    action = make_action(requires_human_review=True)
    element = make_element()
    assert ck.is_reliable(action, element) is False


def test_is_reliable_rejects_cost_conflict():
    action = make_action(cost_conflict=True)
    element = make_element()
    assert ck.is_reliable(action, element) is False


def test_is_reliable_rejects_flagged_element_code():
    action = make_action()
    element = make_element(element_code={"original_value": "9876", "normalized_value": None, "requires_human_review": True})
    assert ck.is_reliable(action, element) is False


def test_is_reliable_accepts_clean_action():
    assert ck.is_reliable(make_action(), make_element()) is True


def test_collect_price_points_prefers_literal_over_calculated(tmp_path):
    rec = {
        "document_id": "DOC-X",
        "elements": [make_element()],
        "maintenance_actions": [
            make_action(unit_cost={"value": "50.00"}, unit_cost_calculated="999.00"),
        ],
    }
    import json
    (tmp_path / "DOC-X.json").write_text(json.dumps(rec))
    points, skipped = ck.collect_price_points(str(tmp_path))
    assert len(points) == 1
    assert points[0]["price_type"] == "literal"
    assert points[0]["price"] == Decimal("50.00")


def test_collect_price_points_skips_actions_without_element_code(tmp_path):
    rec = {
        "document_id": "DOC-X",
        "elements": [{"element_id": "EL-1"}],  # geen element_code veld (bijv. DOC-004/Innax)
        "maintenance_actions": [make_action(unit_cost_calculated="50.00")],
    }
    import json
    (tmp_path / "DOC-X.json").write_text(json.dumps(rec))
    points, skipped = ck.collect_price_points(str(tmp_path))
    assert len(points) == 0
    assert skipped["geen_element_code"] == 1


def test_collect_price_points_skips_actions_without_price(tmp_path):
    rec = {
        "document_id": "DOC-X",
        "elements": [make_element()],
        "maintenance_actions": [make_action()],  # geen unit_cost, geen unit_cost_calculated
    }
    import json
    (tmp_path / "DOC-X.json").write_text(json.dumps(rec))
    points, skipped = ck.collect_price_points(str(tmp_path))
    assert len(points) == 0
    assert skipped["geen_prijs"] == 1


def test_stats_for_computes_min_max_median():
    result = ck.stats_for([Decimal("10.00"), Decimal("20.00"), Decimal("30.00")])
    assert result["n"] == 3
    assert result["min"] == "10.00"
    assert result["max"] == "30.00"
    assert result["median"] == "20.00"


def test_stats_for_empty_list_returns_none():
    assert ck.stats_for([]) is None


def test_aggregate_keeps_literal_and_calculated_separate():
    points = [
        {"element_code": "4711", "action": "replace", "unit": "m2", "price": Decimal("50.00"),
         "price_type": "literal", "cost_year": 2026, "document_id": "DOC-1", "action_id": "A-1"},
        {"element_code": "4711", "action": "replace", "unit": "m2", "price": Decimal("80.00"),
         "price_type": "calculated", "cost_year": 2026, "document_id": "DOC-2", "action_id": "A-2"},
    ]
    results = ck.aggregate(points, {"4711": {"label_nl": "Dakbedekking APP", "hoofdgroep_code": "47", "hoofdgroep_label": "Dakafwerkingen"}})
    assert len(results) == 1
    g = results[0]
    assert g["literal"]["n"] == 1
    assert g["literal"]["min"] == "50.00"
    assert g["calculated"]["n"] == 1
    assert g["calculated"]["min"] == "80.00"
    assert g["n_documents"] == 2
