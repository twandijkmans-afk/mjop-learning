"""
Tests voor scripts/normalize_price_observations.py - de afgeleide
normalisatie-/validatielaag bovenop de price observations. Getest wordt vooral
dat er niets verzonnen wordt:

  - acties alleen via de gekoppelde verified-actie of een exacte
    vocabulaire-lookup; conflict of niets -> null + review
  - eenheden alleen via vocabularies/unit.json; onbekend -> null + review
  - de interne elementcode wordt niet als officiële NL/SfB gepresenteerd
  - prijsvelden worden gecontroleerd, nooit aangepast
  - originele bronwaarden blijven 1-op-1 behouden
"""
import copy
import json
import os
import sys

import jsonschema
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import normalize_price_observations as npo  # noqa: E402
import promotion_ledger as pl  # noqa: E402

VOCAB = os.path.join(PROJECT_ROOT, "vocabularies")
ACTIONS = npo.load_vocab_utf8(VOCAB, "maintenance_action")
UNITS = npo.load_vocab_utf8(VOCAB, "unit")
CODES = {e["normalized_value"]: e for e in json.load(open(os.path.join(VOCAB, "element_code.json"), encoding="utf-8"))["entries"]}
SOURCE_REF = {"source_file": "data/price_observations/x.json", "source_file_sha256": "0" * 64}
SOURCE_PATH = os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json")


def base_obs(**over):
    o = {
        "observation_id": "PO-DOC-005-P011-L011", "document_id": "DOC-005",
        "element": {"element_code_original": "2110", "element_description_original": "Gevelconstructie metselwerk",
                    "element_location_original": "Alle gevels", "element_candidate_previous_page": None,
                    "element_id": "DOC-005-EL-001", "element_code_internal": "2110"},
        "action": {"action_text_original": "Reinigen metselwerk", "gebrek_or_location_text_original": None,
                   "action_normalized": "clean", "action_normalization_basis": "vocabulary"},
        "unit_original": "m2", "unit_normalized": "m2",
        "quantity_as_stated": "815,95", "quantity_value": "815.95",
        "total_as_stated": "17.910", "total_value": "17910", "amount_reconciliation": "consistent",
        "total_scope": "MULTIPLE_EXECUTIONS", "occurrences_in_window": 2,
        "annual_amounts": {"2033": "8955", "2040": "8955"}, "planned_years": ["2033", "2040"],
        "execution_window_start": 2026, "execution_window_end": 2040,
        "cycle_start_year": 2033, "cycle_start_year_as_stated": "2033",
        "cycle_length_years": 7, "cycle_length_as_stated": "7",
        "price_type": "calculated", "unit_price_literal": None, "unit_price_calculated": "21.95",
        "calculated_unit_price_basis": "row_total_over_multiple_executions_in_window",
        "calculation_method": "x", "calculated_unit_price_not_computed_reason": None,
        "price_level_date": "1-8-2026", "price_level_basis": "explicit", "vat_basis": "inclusive",
        "vat_text": "x", "vat_rate_text": "x", "indexation_statement": "x", "legacy_extracted_cost_years": [2033],
        "source_representations": [{"role": "primary_financial_row", "section": "JARENPLAN_GEDETAILLEERD",
                                    "page": 11, "line": 11, "source_text": "Reinigen metselwerk 815,95 m2 2033 7 8.955 8.955 17.910"}],
        "provenance_status": "complete", "provenance_gaps": [],
        "extraction_link": {"action_ids": ["DOC-005-ACT-001"], "method": "m", "score": 1.4},
        "dependency_status": "NO_DEPENDENCY_FOUND", "relation_ids": [], "document_relation_ids": [],
        "review_status": "not_reviewed", "requires_human_review": False, "review_reasons": [], "extraction_review": None,
    }
    for k, v in over.items():
        o[k] = v
    return o


def run(o):
    return npo.normalize_observation(o, ACTIONS, UNITS, CODES, SOURCE_REF)


def codes(n):
    return {r["code"] for r in n["review_reasons"]}


# --------------------------------------------------------------------------
# Actie
# --------------------------------------------------------------------------

def test_action_linked_and_vocabulary_agree():
    n = run(base_obs())
    assert n["action"]["action_normalized"] == "clean"
    assert n["action"]["normalization_basis"] == "verified_link+vocabulary_lookup"
    assert n["action"]["action_text_original"] == "Reinigen metselwerk"
    assert not n["requires_human_review"]


def test_action_conflict_is_not_resolved_automatically():
    o = base_obs()
    o["action"]["action_normalized"] = "replace"  # verified zegt iets anders dan de vocabulaire
    n = run(o)
    assert n["action"]["action_normalized"] is None
    assert n["action"]["status"] == "conflict"
    assert n["action"]["possible_values"] == ["clean", "replace"]
    assert "conflicting_action_normalization" in codes(n)


def unlinked(text):
    o = base_obs()
    o["action"].update(action_text_original=text, action_normalized=None, action_normalization_basis=None)
    return run(o)


def test_unknown_action_text_is_not_guessed():
    n = unlinked("Herstraten betontegels")
    assert n["action"]["action_normalized"] is None
    assert n["action"]["status"] == "unresolved"
    assert "action_not_normalized" in codes(n)


def test_vocabulary_lookup_ignores_case_and_whitespace_only():
    n = unlinked("  REINIGEN   metselwerk ")
    assert n["action"]["action_normalized"] == "clean"
    assert n["action"]["normalization_basis"] == "vocabulary_lookup_on_source_text"
    assert unlinked("Herstraten klinkers")["action"]["action_normalized"] is None  # geen fuzzy match


# --------------------------------------------------------------------------
# Patroonregels (expliciet goedgekeurd): alleen het eerste woord telt
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected,word", [
    ("Vervangen gootbekleding zink", "replace", "vervangen"),
    ("vervangen afsluiters", "replace", "vervangen"),
    ("Vervangen armaturen buiten TL", "replace", "vervangen"),                 # materiaalwissel -> gewoon replace
    ("Vervangen kozijn incl. glas (deel al vervangen)", "replace", "vervangen"),  # deelvervanging -> gewoon replace
    ("Vervangen groepenkast inclusief bedrading", "replace", "vervangen"),      # bundeling -> gewoon replace
    ("Herstellen metselwerk", "repair", "herstellen"),
    ("Herstel vloerafwerking dubbel hard gebakken tegels (gelijmd)", "repair", "herstel"),
    ("Reinigen rookgasafvoerkanaal", "clean", "reinigen"),
])
def test_prefix_pattern_rules(text, expected, word):
    n = unlinked(text)
    assert n["action"]["action_normalized"] == expected
    assert n["action"]["normalization_basis"] == f"prefix_pattern_rule:{word}"
    assert n["action"]["action_text_original"] == text  # extra betekenis blijft in de originele tekst
    assert "action_not_normalized" not in codes(n)


@pytest.mark.parametrize("text", [
    "Reinigen en controleren ventilatierooster",      # twee acties: bewust uitgesloten
    "Betontegels vervangen",                            # werkwoord achteraan
    "Liggende leidingen vervangen",
    "Personenlift vervangen staalkabels",
    "Plaatselijk herstel",                              # 'herstel' niet het eerste woord
    "Herstraten klinkers",                              # 'herstraten' is geen 'herstel'
    "Repareren/Schilderen voetjes (corrosie) balkonscherm staal",
    "Inspecteren en rapporteren",
    "Hoogwerker per week 18 meter hoog",
])
def test_excluded_or_ambiguous_actions_stay_unresolved(text):
    n = unlinked(text)
    assert n["action"]["action_normalized"] is None
    assert "action_not_normalized" in codes(n)


def test_prefix_rule_never_overrides_verified_or_vocabulary():
    o = base_obs()
    o["action"].update(action_text_original="Vervangen dakbedekking APP", action_normalized="install",
                       action_normalization_basis="vocabulary")
    n = run(o)  # verified 'install' vs vocabulaire 'replace' -> conflict, patroonregel speelt geen rol
    assert n["action"]["action_normalized"] is None
    assert n["action"]["status"] == "conflict"


def test_no_new_semantic_action_types_introduced():
    assert set(npo.ACTION_PREFIX_RULES.values()) <= set(ACTIONS.values())


# --------------------------------------------------------------------------
# Eenheid
# --------------------------------------------------------------------------

@pytest.mark.parametrize("original,expected", [("m²", "m2"), ("m1", "m1"), ("st", "piece"), ("pst", "lump_sum")])
def test_known_unit_variants_map_via_vocabulary(original, expected):
    n = run(base_obs(unit_original=original))
    assert n["unit"]["unit_normalized"] == expected
    assert n["unit"]["unit_original"] == original


@pytest.mark.parametrize("original,reason", [("Ver", "unit_unknown"), ("20", "unit_unknown"), (None, "unit_missing_or_unreadable")])
def test_unknown_or_unreadable_unit_needs_review(original, reason):
    n = run(base_obs(unit_original=original))
    assert n["unit"]["unit_normalized"] is None
    assert reason in codes(n)


def test_st_and_pst_are_not_merged():
    assert run(base_obs(unit_original="st"))["unit"]["unit_normalized"] != run(base_obs(unit_original="pst"))["unit"]["unit_normalized"]


# --------------------------------------------------------------------------
# Element
# --------------------------------------------------------------------------

def test_element_code_is_internal_not_official_nlsfb():
    n = run(base_obs())
    assert n["element"]["element_code_system"] == "internal_project_coding"
    assert "niet bevestigd" in n["element"]["element_code_system_note"]
    assert n["element"]["internal_code_label"] == CODES["2110"]["label_nl"]
    assert n["element"]["code_consistency"] == "match"


def test_element_code_mismatch_needs_review():
    o = base_obs()
    o["element"]["element_code_internal"] = "ZZZZ"
    n = run(o)
    assert n["element"]["code_consistency"] == "mismatch"
    assert "element_code_mismatch_source_vs_verified" in codes(n)


def test_missing_internal_code_is_not_filled_from_source_code():
    o = base_obs(document_id="DOC-004")
    o["element"]["element_code_internal"] = None
    n = run(o)
    assert n["element"]["element_code_internal"] is None
    assert "element_code_internal_missing" in codes(n)


# --------------------------------------------------------------------------
# Prijsvalidatie
# --------------------------------------------------------------------------

def test_price_fields_are_copied_unchanged():
    o = base_obs()
    n = run(o)
    for k in ("quantity_as_stated", "total_as_stated", "total_value", "annual_amounts", "unit_price_calculated",
              "cycle_start_year", "cycle_length_years", "price_level_date", "vat_basis"):
        assert n["price"][k] == o[k]


def test_multiple_executions_flags_row_total_ratio():
    n = run(base_obs())
    assert "multiple_executions_in_window" in n["validation"]["flags"]
    assert "calculated_unit_price_is_row_total_ratio" in n["validation"]["flags"]
    assert n["validation"]["checks"]["cycle_pattern_matches_annual_amounts"] is True


def test_inconsistent_calculated_price_is_flagged_not_corrected():
    n = run(base_obs(unit_price_calculated="99.99"))
    assert n["price"]["unit_price_calculated"] == "99.99"
    assert n["validation"]["checks"]["calculated_unit_price_recomputes"] is False
    assert "calculated_unit_price_inconsistent" in codes(n)


def test_cycle_pattern_mismatch_is_flagged():
    n = run(base_obs(cycle_length_years=5))  # 2033, 2038 verwacht; bron toont 2033, 2040
    assert "cycle_pattern_differs_from_annual_amounts" in n["validation"]["flags"]


def test_absent_price_level_and_exclusive_vat_are_flags_not_values():
    n = run(base_obs(price_level_date=None, price_level_basis="absent", vat_basis="exclusive"))
    assert n["price"]["price_level_date"] is None
    assert {"price_level_absent_in_source", "vat_exclusive"} <= set(n["validation"]["flags"])


def test_unknown_dependency_needs_review_possibly_dependent_is_flag():
    assert "unresolved_source_relationship" in codes(run(base_obs(dependency_status="UNKNOWN")))
    n = run(base_obs(dependency_status="POSSIBLY_DEPENDENT"))
    assert "possibly_dependent_relation" in n["validation"]["flags"]
    assert "unresolved_source_relationship" not in codes(n)


def test_source_review_reasons_are_preserved():
    o = base_obs(review_reasons=["element_context_missing", "action_not_normalized"])
    n = run(o)
    assert n["source_review_reasons"] == ["element_context_missing", "action_not_normalized"]
    assert "element_context_missing" in codes(n)


# --------------------------------------------------------------------------
# Integratie op de echte source layer
# --------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(SOURCE_PATH), reason="source layer niet gebouwd")
def test_normalize_full_batch1_source_layer():
    before = npo.sha256_file(SOURCE_PATH)
    result = npo.normalize(PROJECT_ROOT, SOURCE_PATH)
    assert npo.sha256_file(SOURCE_PATH) == before  # bron niet aangeraakt
    assert result["summary"]["observations"] == 404 + pl.added_price_observations(PROJECT_ROOT)
    assert result["source"]["source_file_sha256"] == before
    src = {o["observation_id"]: o for o in json.load(open(SOURCE_PATH, encoding="utf-8"))["observations"]}
    for n in result["observations"]:
        s = src[n["observation_id"]]
        assert n["action"]["action_text_original"] == s["action"]["action_text_original"]
        assert n["unit"]["unit_original"] == s["unit_original"]
        assert n["price"]["total_as_stated"] == s["total_as_stated"]
    errors = npo.validate_output(result, os.path.join(PROJECT_ROOT, "schemas", "price_observation_normalized.schema.json"))
    assert errors == []


# --------------------------------------------------------------------------
# Materiaal (DOC-001: afleiding uit elementtekst, apart veld)
# --------------------------------------------------------------------------

MATERIALS = npo.load_vocab_utf8(VOCAB, "material")


def mat(desc, action, oid="PO-DOC-001-P099-L001", doc="DOC-001", verified=None):
    obs = {"observation_id": oid, "document_id": doc,
           "element": {"element_id": "EL-X", "element_description_original": desc},
           "action": {"action_text_original": action}}
    return npo.normalize_material(obs, {"EL-X": verified or {"element_id": "EL-X"}}, MATERIALS)


@pytest.mark.parametrize("oid,desc,action,original,normalized", [
    ("PO-DOC-001-P024-L019", "Gootbekleding zink", "Herstellen", "zink", "zinc"),
    ("PO-DOC-001-P024-L021", "Gootbekleding zink", "Reinigen", "zink", "zinc"),
    ("PO-DOC-001-P024-L023", "Gootbekleding zink", "Vervangen gootbekleding zink", "zink", "zinc"),
    ("PO-DOC-001-P024-L057", "Ventilatierooster staal", "Herstellen", "staal", "steel"),
    ("PO-DOC-001-P024-L061", "Buitendeur hout", "Vervangen", "hout", "wood"),
    ("PO-DOC-001-P024-L069", "Balustrade aluminium", "Reinigen", "aluminium", "aluminium"),
    ("PO-DOC-001-P025-L023", "Buitenschilderwerk deur hout dekkend", "Schilderen", "hout", "wood"),
    ("PO-DOC-001-P025-L025", "Buitenschilderwerk deur hout dekkend", "Groot schilderwerk deur hout dekkend", "hout", "wood"),
    ("PO-DOC-001-P025-L095", "Buitenschilderwerk kozijn en raam hout dekkend",
     "Groot schilderwerk kozijn en raam hout dekkend", "hout", "wood"),
    ("PO-DOC-001-P026-L029", "Hemelwaterafvoer pvc", "Vervangen hemelwaterafvoer pvc", "pvc", "pvc"),
])
def test_doc001_exact_material_from_element_text(oid, desc, action, original, normalized):
    m = mat(desc, action, oid=oid)
    assert m["material_status"] == "MATERIAL_FROM_TEXT" and m["material_source"] == "element_text"
    assert m["material_from_text"] == {"original_value": original, "normalized_value": normalized,
                                       "source_field": "element_description_original"}
    assert m["material_original"] is None and m["material_normalized"] is None  # origineel veld niet overschreven
    assert m["verified_material_field"] == "absent"


@pytest.mark.parametrize("desc,action", [
    ("Gevelconstructie metselwerk", "Reinigen"),                            # geen vocabulairewoord
    ("Buitenschilderwerk betonconstructie plafond", "Groot schilderwerk"),  # 'beton' alleen in samenstelling
    ("Boeiboord volkern", "Reinigen boeiboord volkern"),
    ("Buitenbeglazing enkel", "Vervangen"),
])
def test_no_material_without_exact_vocabulary_word(desc, action):
    m = mat(desc, action)
    assert m["material_from_text"] is None and m["material_status"] == "MATERIAL_UNKNOWN"
    assert m["material_not_derived_reason"] == "no_vocabulary_token_in_element_text"


def test_metaal_versus_aluminium_is_not_resolved():
    # element zegt 'metaal' (niet in vocabulaire), actie zegt 'aluminium': niets afleiden, zeker niet uit de actie
    m = mat("Kozijn ventilatierooster metaal", "Reinigen ventilatierooster aluminium")
    assert m["material_from_text"] is None and m["material_status"] == "MATERIAL_UNKNOWN"
    # ook als het element wel een vocabulairewoord heeft: ander materiaal in de actie = conflict
    m = mat("Ventilatierooster staal", "Reinigen ventilatierooster aluminium")
    assert m["material_from_text"] is None
    assert m["material_not_derived_reason"] == "conflicting_material_in_action_text"


def test_material_change_ijzer_to_pvc_is_not_derived():
    m = mat("Binnenriolering ijzer", "Vervangen binneriolering ijzer > pvc")
    assert m["material_from_text"] is None  # 'pvc' uit de actie wordt nooit overgenomen
    m = mat("Gootbetimmering asbestcement (onderzijde goot)", "Vervangen boeiboord asbestcement- >kunststof")
    assert m["material_from_text"] is None
    m = mat("Gootbekleding zink", "Vervangen gootbekleding zink -> pvc")
    assert m["material_from_text"] is None and m["material_not_derived_reason"] == "material_change_in_action_text"


def test_multiple_materials_and_held_case_are_not_derived():
    assert mat("Hijsbalk hout en staal", "Vervangen")["material_not_derived_reason"] == \
        "multiple_vocabulary_tokens_in_element_text"
    m = mat("Buitenschilderwerk verzinkt staal roosters", "Groot schilderwerk verzinkt staal roosters",
            oid="PO-DOC-001-P025-L039")
    assert m["material_from_text"] is None and m["material_not_derived_reason"] == "held_for_human_interpretation"


def test_verified_material_is_kept_and_never_replaced_by_text():
    m = mat("Gootbekleding zink", "Vervangen", doc="DOC-002",
            verified={"element_id": "EL-X", "material": {"original_value": "hout", "normalized_value": "wood"}})
    assert (m["material_original"], m["material_normalized"], m["material_status"]) == \
        ("hout", "wood", "MATERIAL_FROM_VERIFIED")
    assert m["material_from_text"] is None
    m = mat("Gootbekleding zink", "Vervangen", doc="DOC-002",
            verified={"element_id": "EL-X", "material": {"original_value": None, "normalized_value": None}})
    assert m["material_from_text"] is None and m["material_not_derived_reason"] == "verified_material_empty"


def test_material_field_absent_outside_doc001_is_not_derived():
    m = mat("Hemelwaterafvoer pvc", "Vervangen hemelwaterafvoer pvc", oid="PO-DOC-004-P010-L010", doc="DOC-004")
    assert m["material_from_text"] is None
    assert m["material_not_derived_reason"] == "material_field_absent_document_not_in_scope"


@pytest.mark.skipif(not os.path.exists(SOURCE_PATH), reason="source layer niet gebouwd")
def test_batch1_has_exactly_ten_material_from_text():
    result = npo.normalize(PROJECT_ROOT, SOURCE_PATH)
    derived = {o["observation_id"] for o in result["observations"] if o["material"]["material_from_text"]}
    assert derived == {"PO-DOC-001-P024-L019", "PO-DOC-001-P024-L021", "PO-DOC-001-P024-L023",
                       "PO-DOC-001-P024-L057", "PO-DOC-001-P024-L061", "PO-DOC-001-P024-L069",
                       "PO-DOC-001-P025-L023", "PO-DOC-001-P025-L025", "PO-DOC-001-P025-L095",
                       "PO-DOC-001-P026-L029"}
    vdir = os.path.join(PROJECT_ROOT, "data", "verified")
    verified = {e["element_id"]: e for n in os.listdir(vdir)
                for e in json.load(open(os.path.join(vdir, n), encoding="utf-8"))["elements"]}
    decisions = npo.load_material_decisions(PROJECT_ROOT)
    for o in result["observations"]:  # originele materiaalvelden 1-op-1 uit verified
        el = verified.get(o["element"]["element_id"]) or {}
        if o["material"]["material_status"] == "MATERIAL_FROM_HUMAN_DECISION":
            # alleen de exact opgesomde observations van een menselijk materiaalbesluit (MATDEC-*)
            d = decisions[o["observation_id"]]
            assert not (el.get("material") or {}).get("original_value")
            assert o["material"]["material_original"] == d["material"]["original_value"]
            assert o["material"]["material_decision_id"] == d["decision_id"]
            continue
        assert o["material"]["material_original"] == (el.get("material") or {}).get("original_value")
    assert sorted(o["observation_id"] for o in result["observations"]
                  if o["material"]["material_status"] == "MATERIAL_FROM_HUMAN_DECISION") == sorted(decisions)


# --------------------------------------------------------------------------
# Besluit 2026-09-28: leeg/null materiaalveld (deterministische extractie) telt voor de
# bestaande MATERIAL_FROM_TEXT-regel als ontbrekend veld - zelfde regel, zelfde patronen.
# --------------------------------------------------------------------------

EMPTY_MATERIAL_FIELDS = [
    ("absent", {"element_id": "EL-X"}),
    ("empty_pair", {"element_id": "EL-X", "material": {"original_value": None, "normalized_value": None}}),
    ("empty_string", {"element_id": "EL-X", "material": {"original_value": "", "normalized_value": None}}),
    ("null", {"element_id": "EL-X", "material": None}),
]


@pytest.mark.parametrize("label,verified", EMPTY_MATERIAL_FIELDS)
def test_material_from_text_applies_when_field_missing_empty_or_null(label, verified):
    m = mat("Gootbekleding zink", "Herstellen", oid="PO-DOC-001-P024-L019", verified=verified)
    assert m["material_status"] == "MATERIAL_FROM_TEXT" and m["material_source"] == "element_text"
    assert m["material_from_text"] == {"original_value": "zink", "normalized_value": "zinc",
                                       "source_field": "element_description_original"}
    assert m["material_original"] in (None, "") and m["material_normalized"] is None   # veld niet overschreven
    assert m["verified_material_field"] == ("absent" if label == "absent" else "present")


def test_non_empty_material_field_stays_leading_in_scope_document():
    m = mat("Gootbekleding zink", "Herstellen", oid="PO-DOC-001-P024-L019",
            verified={"element_id": "EL-X", "material": {"original_value": "koper", "normalized_value": "copper"}})
    assert (m["material_original"], m["material_normalized"], m["material_status"]) == \
        ("koper", "copper", "MATERIAL_FROM_VERIFIED")
    assert m["material_from_text"] is None


@pytest.mark.parametrize("label,verified", EMPTY_MATERIAL_FIELDS[1:])
def test_empty_field_without_valid_text_rule_stays_unknown(label, verified):
    m = mat("Gevelconstructie metselwerk", "Reinigen", verified=verified)
    assert m["material_from_text"] is None and m["material_status"] == "MATERIAL_UNKNOWN"
    assert m["material_not_derived_reason"] == "no_vocabulary_token_in_element_text"
    m = mat("Gootbekleding zink", "Vervangen gootbekleding zink -> pvc", verified=verified)
    assert m["material_from_text"] is None and m["material_not_derived_reason"] == "material_change_in_action_text"


@pytest.mark.parametrize("label,verified", EMPTY_MATERIAL_FIELDS[1:])
def test_empty_field_outside_scope_document_unchanged(label, verified):
    m = mat("Gootbekleding zink", "Vervangen", doc="DOC-002", verified=verified)
    assert m["material_from_text"] is None and m["material_not_derived_reason"] == "verified_material_empty"
