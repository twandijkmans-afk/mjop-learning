"""
Tests voor scripts/apply_review.py - verwerkt de door een mens ingevulde
review-Excel (export_review_sheet.py) naar data/verified/*.json. Test hier
vooral dat een edit zonder waarde nooit een aanname invult (zie CLAUDE.md)
en dat reject een post niet stilzwijgend als opgelost markeert.
"""
import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

spec = importlib.util.spec_from_file_location(
    "apply_review", os.path.join(PROJECT_ROOT, "scripts", "apply_review.py")
)
apply_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_review)

TS = "2026-09-21T12:00:00Z"


def test_accept_clears_review_flag_but_keeps_value():
    pair = {"original_value": "iets onbekends", "normalized_value": None, "requires_human_review": True}
    out, warning = apply_review.apply_pair_decision(pair, "accept", None, "r@x.nl", TS)
    assert warning is None
    assert out["normalized_value"] is None, "accept bevestigt de bestaande waarde, verzint er geen bij"
    assert out["requires_human_review"] is False
    assert out["human_verification"]["status"] == "accept"


def test_edit_applies_corrected_value():
    pair = {"original_value": "Vervangen kozijn zachthout", "normalized_value": None, "requires_human_review": True}
    out, warning = apply_review.apply_pair_decision(pair, "edit", "replace", "r@x.nl", TS)
    assert warning is None
    assert out["normalized_value"] == "replace"
    assert out["requires_human_review"] is False
    assert out["human_verification"]["edited_value"] == "replace"
    assert out["human_verification"]["original_ai_value"] is None


def test_edit_without_corrected_value_is_rejected_not_guessed():
    pair = {"original_value": "iets", "normalized_value": None, "requires_human_review": True}
    out, warning = apply_review.apply_pair_decision(pair, "edit", None, "r@x.nl", TS)
    assert warning is not None
    assert out["normalized_value"] is None, "zonder GECORRIGEERDE_WAARDE mag er nooit een waarde verschijnen"
    assert "human_verification" not in out


def test_reject_leaves_value_and_review_flag_untouched():
    pair = {"original_value": "iets raars", "normalized_value": None, "requires_human_review": True}
    out, warning = apply_review.apply_pair_decision(pair, "reject", None, "r@x.nl", TS, notes="niet te herleiden")
    assert warning is None
    assert out["normalized_value"] is None
    assert out["requires_human_review"] is True, (
        "reject betekent 'ook een mens weet het niet zeker', niet 'opgelost' - blijft in de wachtrij"
    )
    assert out["human_verification"]["status"] == "reject"
    assert out["human_verification"]["notes"] == "niet te herleiden"


def test_unknown_decision_is_rejected():
    pair = {"original_value": "iets", "normalized_value": None}
    out, warning = apply_review.apply_pair_decision(pair, "misschien", None, "r@x.nl", TS)
    assert warning is not None
    assert "human_verification" not in out


def test_process_action_row_edit_targets_action_field():
    action = {
        "action_id": "A-1",
        "action": {"original_value": "Vervangen kozijn zachthout", "normalized_value": None, "requires_human_review": True},
        "unit": {"original_value": "m1", "normalized_value": "m1"},
    }
    row = {"veld": "actie", "BESLISSING": "edit", "GECORRIGEERDE_WAARDE": "replace", "NOTITIES": None}
    warning, new_value = apply_review.process_action_row(action, row, "r@x.nl", TS)
    assert warning is None
    assert action["action"]["normalized_value"] == "replace"
    assert new_value == "replace"
    assert action["requires_human_review"] is False
    assert "review_note" in action


def test_process_action_row_edit_targets_unit_field_not_action():
    action = {
        "action_id": "A-2",
        "action": {"original_value": "Standleidingen schoon frezen", "normalized_value": "clean"},
        "unit": {"original_value": "Ver", "normalized_value": None, "requires_human_review": True},
        "requires_human_review": True,
    }
    row = {"veld": "eenheid", "BESLISSING": "edit", "GECORRIGEERDE_WAARDE": "piece", "NOTITIES": None}
    warning, new_value = apply_review.process_action_row(action, row, "r@x.nl", TS)
    assert warning is None
    assert action["unit"]["normalized_value"] == "piece"
    assert action["action"]["normalized_value"] == "clean", "een unit-correctie mag de actieterm niet aanraken"
    assert action["requires_human_review"] is False


def test_process_action_row_edit_refused_without_vocab_field():
    action = {
        "action_id": "A-3",
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "cost_conflict": True,
        "requires_human_review": True,
    }
    row = {"veld": "geen", "BESLISSING": "edit", "GECORRIGEERDE_WAARDE": "replace", "NOTITIES": None}
    warning, new_value = apply_review.process_action_row(action, row, "r@x.nl", TS)
    assert warning is not None
    assert new_value is None
    assert action["requires_human_review"] is True, (
        "een kostenconflict-rij heeft geen vocabulaire-veld om te editen en mag niet stilzwijgend opgelost worden"
    )


def test_process_action_row_accept_with_no_vocab_field_still_records_note():
    action = {
        "action_id": "A-4",
        "action": {"original_value": "vervangen", "normalized_value": "replace"},
        "unit_cost_calculated": "10.07",
        "requires_human_review": True,
    }
    row = {"veld": "geen", "BESLISSING": "accept", "GECORRIGEERDE_WAARDE": None, "NOTITIES": "plausibel bedrag"}
    warning, new_value = apply_review.process_action_row(action, row, "r@x.nl", TS)
    assert warning is None
    assert action["requires_human_review"] is False
    assert "plausibel bedrag" in action["review_note"]


def test_process_observation_row_edit():
    obs = {
        "observation_id": "O-1",
        "defect": {"original_value": "een rare term", "normalized_value": None, "requires_human_review": True},
        "requires_human_review": True,
    }
    row = {"BESLISSING": "edit", "GECORRIGEERDE_WAARDE": "corrosion", "NOTITIES": None}
    warning, new_value = apply_review.process_observation_row(obs, row, "r@x.nl", TS)
    assert warning is None
    assert obs["defect"]["normalized_value"] == "corrosion"
    assert new_value == "corrosion"
    assert obs["requires_human_review"] is False
