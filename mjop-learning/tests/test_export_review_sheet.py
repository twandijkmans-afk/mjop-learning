"""
Tests voor scripts/export_review_sheet.py - vooral dat de REDEN/veld-
kolommen precies verklaren waarom een post gemarkeerd is, want daar
vertrouwt apply_review.py op om te weten welk vocabulaire-veld (actie of
eenheid) een GECORRIGEERDE_WAARDE mag ontvangen.
"""
import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

spec = importlib.util.spec_from_file_location(
    "export_review_sheet", os.path.join(PROJECT_ROOT, "scripts", "export_review_sheet.py")
)
export_review_sheet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_review_sheet)


def test_action_review_field_prefers_action_over_unit():
    action = {
        "action": {"original_value": "iets", "normalized_value": None, "requires_human_review": True},
        "unit": {"original_value": "raar", "normalized_value": None, "requires_human_review": True},
    }
    assert export_review_sheet.action_review_field(action) == "actie"


def test_action_review_field_unit_only():
    action = {
        "action": {"original_value": "Standleidingen schoon frezen", "normalized_value": "clean"},
        "unit": {"original_value": "Ver", "normalized_value": None, "requires_human_review": True},
    }
    assert export_review_sheet.action_review_field(action) == "eenheid"


def test_action_review_field_none_when_only_cost_conflict():
    action = {
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "cost_conflict": True,
    }
    assert export_review_sheet.action_review_field(action) == "geen"


def test_action_review_reasons_reports_cost_conflict():
    action = {
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "cost_conflict": True,
    }
    reasons = export_review_sheet.action_review_reasons(action)
    assert any("kostenconflict" in r for r in reasons)


def test_action_review_reasons_reports_derived_unit_cost():
    action = {
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "unit_cost": {"value": None, "provenance": {"source_confidence": "low"}},
    }
    reasons = export_review_sheet.action_review_reasons(action)
    assert any("afgeleide eenheidsprijs" in r for r in reasons)


def test_action_review_reasons_vocab_takes_precedence_over_low_confidence_label():
    action = {
        "action": {"original_value": "iets onbekends", "normalized_value": None, "requires_human_review": True},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "unit_cost": {"value": None, "provenance": {"source_confidence": "low"}},
    }
    reasons = export_review_sheet.action_review_reasons(action)
    assert reasons == ["onbekende actieterm"], (
        "als de actieterm zelf al onbekend is, hoeft de generieke lage-confidence-reden niet ook getoond"
    )


def test_build_action_rows_only_includes_flagged_actions():
    rec = {
        "document_id": "DOC-TEST",
        "elements": [{"element_id": "EL-1", "element_type": {"original_value": "Kozijn hout"}}],
        "maintenance_actions": [
            {"action_id": "A-1", "element_id": "EL-1", "action": {"original_value": "vervangen", "normalized_value": "replace"}},
            {"action_id": "A-2", "element_id": "EL-1", "action": {"original_value": "iets raars", "normalized_value": None, "requires_human_review": True}, "requires_human_review": True},
        ],
    }
    rows = export_review_sheet.build_action_rows(rec, {"EL-1": rec["elements"][0]})
    assert len(rows) == 1
    assert rows[0][1] == "A-2"
