"""
Tests voor scripts/backfill_element_codes.py - vult element_code met terug-
werkende kracht in voor de 9 documenten die zijn geextraheerd voordat dit
veld aan het schema is toegevoegd. Test vooral dat er nooit een code
verzonnen wordt: alleen een letterlijk citaat (methode A) of een
positionele match waarvan de beschrijving daadwerkelijk overeenkomt
(methode B) telt, anders blijft normalized_value null.
"""
import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

spec = importlib.util.spec_from_file_location(
    "backfill_element_codes", os.path.join(PROJECT_ROOT, "scripts", "backfill_element_codes.py")
)
bec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bec)

KNOWN_CODES = {"2110", "4711", "9999"}


def test_find_literal_code_from_element_type_provenance():
    element = {
        "element_type": {
            "original_value": "Gevelconstructie metselwerk",
            "provenance": {"text_fragment": "2110 | Gevelconstructie metselwerk | Voorgevel"},
        }
    }
    code, source = bec.find_literal_code(element)
    assert code == "2110"


def test_find_literal_code_checks_multiple_fields():
    element = {
        "element_type": {"original_value": "Iets", "provenance": {"text_fragment": None}},
        "quantity": {"provenance": {"text_fragment": "4711 Dakbedekking APP 100,00m2 3"}},
    }
    code, source = bec.find_literal_code(element)
    assert code == "4711"


def test_find_literal_code_returns_none_without_leading_digits():
    element = {"element_type": {"provenance": {"text_fragment": "Gevelconstructie metselwerk zonder code"}}}
    code, source = bec.find_literal_code(element)
    assert code is None


def test_align_positionally_matches_in_order():
    elements = [
        {"element_id": "EL-1", "element_type": {"original_value": "Gevelconstructie metselwerk"}},
        {"element_id": "EL-2", "element_type": {"original_value": "Loodslabben opgaand werk"}},
    ]
    code_rows = [
        ("2110", "Gevelconstructie metselwerk Gevels"),
        ("2110", "Loodslabben opgaand werk Gevels"),
    ]
    result = bec.align_positionally(elements, code_rows)
    assert result["EL-1"] == ("2110", "Gevelconstructie metselwerk Gevels")
    assert result["EL-2"] == ("2110", "Loodslabben opgaand werk Gevels")


def test_align_positionally_skips_ahead_within_window():
    """Als er een tussenliggende regel is die niet als element is opgenomen
    (bijv. een hoofdgroep-kop die de regex al filtert), moet de aligner
    daar overheen kunnen kijken binnen het lookahead-venster."""
    elements = [
        {"element_id": "EL-1", "element_type": {"original_value": "Kozijn buiten hout"}},
    ]
    code_rows = [
        ("2110", "Iets heel anders"),
        ("3120", "Kozijn buiten hout Gevels"),
    ]
    result = bec.align_positionally(elements, code_rows)
    assert result["EL-1"] == ("3120", "Kozijn buiten hout Gevels")


def test_align_positionally_never_forces_a_bad_match():
    elements = [
        {"element_id": "EL-1", "element_type": {"original_value": "Iets wat nergens in de brontekst voorkomt"}},
    ]
    code_rows = [("2110", "Compleet iets anders")]
    result = bec.align_positionally(elements, code_rows)
    assert result["EL-1"] == (None, None)


def test_set_element_code_with_known_code():
    element = {}
    bec.set_element_code(element, "2110", KNOWN_CODES, "2110 | iets")
    assert element["element_code"]["normalized_value"] == "2110"
    assert element["element_code"]["original_value"] == "2110"
    assert "requires_human_review" not in element["element_code"]


def test_set_element_code_with_unknown_code_flags_for_review():
    element = {}
    bec.set_element_code(element, "1234", KNOWN_CODES, "1234 | iets")
    assert element["element_code"]["original_value"] == "1234"
    assert element["element_code"]["normalized_value"] is None, (
        "een code die niet in vocabularies/element_code.json staat mag nooit gevalideerd worden"
    )
    assert element["element_code"]["requires_human_review"] is True


def test_set_element_code_with_no_match_never_guesses():
    element = {}
    bec.set_element_code(element, None, KNOWN_CODES, None)
    assert element["element_code"]["original_value"] is None
    assert element["element_code"]["normalized_value"] is None
    assert element["element_code"]["requires_human_review"] is True
