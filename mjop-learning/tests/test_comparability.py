"""
Tests voor scripts/build_comparability.py - vergelijkbaarheidsregels v1
(docs/comparability_rules_v1.md). Getest worden de afzonderlijke regels op
observation-niveau (O), paarniveau (P) en bronniveau (D), en dat er geen
bronwaarden veranderen, geen scores en geen kengetallen ontstaan.
"""
import copy
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import build_comparability as bc  # noqa: E402

SIGNALS = bc.load_signals(os.path.join(PROJECT_ROOT, "vocabularies", "comparability_signal_words.json"))
RELATIONS = json.load(open(os.path.join(PROJECT_ROOT, "data", "price_observations", "document_relations.json"),
                           encoding="utf-8"))["relations"]
NORMALIZED = os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1_normalized.json")
SOURCE = os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json")


def obs(oid="PO-DOC-006-P015-L093", doc="DOC-006", code="5211", label="Hemelwaterafvoer / doorvoer",
        desc="Hemelwaterafvoer pvc", action_text="Vervangen hemelwaterafvoer pvc", action="replace", unit="m1",
        qty="91.6", annual=None, scope="ONE_EXECUTION", price_level="1-3-2023", vat="inclusive",
        element_id="EL-1", review=(), dependency="NO_DEPENDENCY_FOUND", code_original=None):
    annual = annual if annual is not None else {"2032": "4487"}
    total = str(sum(int(v) for v in annual.values()))
    return {
        "observation_id": oid, "document_id": doc,
        "element": {"element_code_original": code if code_original is None else code_original,
                    "element_code_internal": code, "internal_code_label": label,
                    "element_description_original": desc, "element_id": element_id},
        "action": {"action_text_original": action_text, "action_normalized": action},
        "unit": {"unit_normalized": unit},
        "price": {"quantity_value": qty, "total_as_stated": total, "total_value": total, "annual_amounts": annual,
                  "total_scope": scope, "unit_price_calculated": "48.98", "price_level_date": price_level,
                  "price_level_basis": "explicit" if price_level else "absent", "vat_basis": vat},
        "validation": {"checks": {"amount_reconciliation": "consistent"}},
        "review_reasons": [{"code": c} for c in review],
        "dependency_status": dependency,
    }


ELEMENTS = {"EL-1": {"material": {"original_value": "pvc", "normalized_value": None}},
            "EL-STAAL": {"material": {"original_value": "staal", "normalized_value": None}},
            "EL-NONE": {"material": None},
            "EL-APP": {"material": {"original_value": "APP", "normalized_value": None}},
            "EL-APPB": {"material": {"original_value": "APP+ballast", "normalized_value": None}},
            "EL-MIX": {"material": {"original_value": "hout/staal", "normalized_value": None}}}


def assess(o):
    return bc.assess_observation(o, ELEMENTS, SIGNALS)


def pair(o1, o2):
    return bc.assess_pair(assess(o1), assess(o2), o1, o2, set())


def other(**kw):
    base = dict(oid="PO-DOC-010-P012-L093", doc="DOC-010", qty="13", annual={"2034": "588"}, price_level="1-4-2023")
    base.update(kw)
    return obs(**base)


# --------------------------------------------------------------------------
# A. Observation
# --------------------------------------------------------------------------

def test_clean_observation_is_eligible():
    a = assess(obs())
    assert a["eligibility"] == "ELIGIBLE" and a["caveats"] == []


def test_lump_sum_not_eligible():
    a = assess(obs(unit="lump_sum", qty="1"))
    assert a["eligibility"] == "NOT_ELIGIBLE" and "LUMP_SUM" in a["eligibility_reasons"]


def test_fractional_piece_count_is_caveat():
    a = assess(obs(unit="piece", qty="11.05"))
    assert a["eligibility"] == "ELIGIBLE_WITH_CAVEATS" and "FRACTIONAL_PIECE_COUNT" in a["caveats"]


def test_unknown_element_context():
    a = assess(obs(code_original="", review=("element_context_missing",)))
    assert a["eligibility"] == "UNKNOWN" and "ELEMENT_CONTEXT_MISSING" in a["eligibility_reasons"]


def test_incomplete_description_is_unknown():
    a = assess(obs(desc="Binnenschilderwerk stucwerk (incl."))
    assert a["eligibility"] == "UNKNOWN" and "INCOMPLETE_DESCRIPTION" in a["eligibility_reasons"]


def test_bundling_signal_not_eligible():
    a = assess(obs(action_text="Vervangen voegwerk (incl. bereikbaarheid)"))
    assert a["eligibility"] == "NOT_ELIGIBLE" and "BUNDLED_COST" in a["eligibility_reasons"]
    assert assess(obs(action_text="Vervangen groepenkast inclusief bedrading"))["eligibility"] == "NOT_ELIGIBLE"


@pytest.mark.parametrize("text,code", [
    ("Vervangen armaturen binnenlamp LED", "UPGRADE"),
    ("Vervangen binneriolering ijzer->pvc", "UPGRADE"),
    ("Vervangen lichtkoepel dubbelwandig restant", "PARTIAL_SCOPE"),
    ("Vervangen kozijn (deel al vervangen)", "PARTIAL_SCOPE"),
    ("Vervangen kitvoeg voorzijde gelijktijdig met schilderwerk", "COMBINED_EXECUTION"),
])
def test_qualifier_signals_are_caveats(text, code):
    a = assess(obs(action_text=text))
    assert code in a["caveats"] and a["eligibility"] == "ELIGIBLE_WITH_CAVEATS"


def test_signal_list_is_not_extended_by_similar_words():
    # 'onderdeel', 'gelijktijdig' alleen, 'geled' zijn geen goedgekeurde signalen
    for text in ("Vervangen onderdeel", "Schilderen gelijktijdig", "Vervangen geledingen"):
        assert assess(obs(action_text=text))["signals_found"] == []


def test_missing_price_level_is_caveat_not_derived():
    a = assess(obs(price_level=None))
    assert "PRICE_LEVEL_ABSENT" in a["caveats"]


def test_unknown_material_is_caveat():
    a = assess(obs(element_id="EL-NONE"))
    assert "MATERIAL_UNKNOWN" in a["caveats"] and a["eligibility"] == "ELIGIBLE_WITH_CAVEATS"


def test_doc004_without_internal_code_not_eligible_and_not_mapped():
    o = obs(doc="DOC-004", code=None, code_original="5211")
    a = assess(o)
    assert a["eligibility"] == "NOT_ELIGIBLE" and "NO_INTERNAL_CODE" in a["eligibility_reasons"]
    assert o["element"]["element_code_internal"] is None  # geen automatische codekoppeling


def test_unresolved_dependency_is_unknown():
    assert assess(obs(dependency="UNKNOWN"))["eligibility"] == "UNKNOWN"


# --------------------------------------------------------------------------
# E1. Prijs per uitvoering
# --------------------------------------------------------------------------

def test_derived_price_per_execution_when_conditions_met():
    o = obs(qty="815.95", annual={"2033": "8955", "2040": "8955"}, scope="MULTIPLE_EXECUTIONS")
    a = assess(o)
    d = a["derived_unit_price_per_execution"]
    assert d["value"] == "10.97" and d["executions_in_window"] == 2 and d["annual_amount_used"] == "8955"  # 8955/815.95
    assert d["source_total_as_stated"] == "17910"  # bronwaarde blijft zichtbaar
    assert "ROW_TOTAL_RATIO" not in a["caveats"]
    assert o["price"]["total_as_stated"] == "17910" and o["price"]["unit_price_calculated"] == "48.98"


def test_no_derivation_when_annual_amounts_differ():
    a = assess(obs(annual={"2030": "100", "2036": "120"}, scope="MULTIPLE_EXECUTIONS"))
    assert a["derived_unit_price_per_execution"] is None
    assert "annual_amounts_differ" in a["per_execution_not_derived_reasons"]
    assert "ROW_TOTAL_RATIO" in a["caveats"]


def test_no_derivation_when_row_total_not_reconciled():
    o = obs(annual={"2030": "100", "2036": "100"}, scope="MULTIPLE_EXECUTIONS")
    o["validation"]["checks"]["amount_reconciliation"] = "mismatch"
    assert assess(o)["derived_unit_price_per_execution"] is None


# --------------------------------------------------------------------------
# B. Paar
# --------------------------------------------------------------------------

def test_same_unit_object_action_material_year_is_comparable():
    assert pair(obs(), other())["class"] == "COMPARABLE"


def test_different_units_not_comparable():
    p = pair(obs(), other(unit="m2"))
    assert p["class"] == "NOT_COMPARABLE" and "UNIT_DIFFERS" in p["hard_violations"]


def test_different_object_same_code_requires_review():
    p = pair(obs(), other(desc="Doorvoer kunststof"))
    assert p["class"] == "UNKNOWN" and "OBJECT_EQUIVALENCE_REQUIRES_REVIEW" in p["unknown_reasons"]


def test_generic_vs_specific_object_is_caveat():
    p = pair(obs(desc="Elektra armaturen"), other(desc="Elektra armaturen binnenlamp"))
    assert p["class"] == "COMPARABLE_WITH_CAVEATS" and "GENERIC_VS_SPECIFIC_OBJECT" in p["pair_caveats"]


def test_material_difference_not_comparable():
    p = pair(obs(), other(element_id="EL-STAAL"))
    assert p["class"] == "NOT_COMPARABLE" and "MATERIAL_DIFFERS" in p["hard_violations"]


def test_material_variant_is_caveat():
    p = pair(obs(element_id="EL-APP"), other(element_id="EL-APPB"))
    assert "MATERIAL_VARIANT" in p["pair_caveats"] and p["class"] == "COMPARABLE_WITH_CAVEATS"


def test_unknown_material_pair_is_caveat_not_unknown():
    p = pair(obs(), other(element_id="EL-NONE"))
    assert p["class"] == "COMPARABLE_WITH_CAVEATS" and "MATERIAL_UNKNOWN" in p["observation_caveats"]["b"]


def test_price_year_difference_is_caveat_without_indexation():
    p = pair(obs(), other(price_level="21-4-2025"))
    assert p["class"] == "COMPARABLE_WITH_CAVEATS" and "PRICE_LEVEL_DIFFERENCE" in p["pair_caveats"]
    assert "index" not in json.dumps(p).lower()


def test_vat_basis_difference_not_comparable():
    p = pair(obs(), other(vat="exclusive"))
    assert p["class"] == "NOT_COMPARABLE" and "VAT_BASIS_DIFFERS" in p["hard_violations"]


def test_quantity_scale_difference_is_caveat():
    p = pair(obs(qty="580"), other(qty="30.71"))
    assert "QUANTITY_SCALE_DIFFERENCE" in p["pair_caveats"]


def test_action_text_prefix_is_caveat_and_different_text_needs_review():
    p = pair(obs(action_text="Aanbrengen nieuwe laag dakbedekking APP"),
             other(action_text="Aanbrengen nieuwe laag dakbedekking APP dakvlak 1-4-5"))
    assert "ACTION_TEXT_VARIANT" in p["pair_caveats"]
    p = pair(obs(action_text="Groot schilderwerk trap hout dekkend"),
             other(action_text="Groot schilderwerk trap hout transparant"))
    assert p["class"] == "UNKNOWN" and "ACTION_EQUIVALENCE_REQUIRES_REVIEW" in p["unknown_reasons"]


def test_pair_has_no_score_field():
    p = pair(obs(), other())
    assert not any("score" in k for k in p)


# --------------------------------------------------------------------------
# C. Bronnen / clusters
# --------------------------------------------------------------------------

def test_clusters_from_document_relations():
    cluster_of, dup = bc.build_clusters(["DOC-002", "DOC-004", "DOC-005", "DOC-006", "DOC-008", "DOC-009"], RELATIONS)
    assert cluster_of["DOC-005"] == cluster_of["DOC-006"]          # versie
    assert cluster_of["DOC-008"] == cluster_of["DOC-009"]          # deelplannen
    assert cluster_of["DOC-002"] != cluster_of["DOC-004"]          # zelfde gebouw, andere inspectie
    assert dup == {"DOC-003": "DOC-002"} and cluster_of["DOC-003"] == cluster_of["DOC-002"]  # duplicaat


def test_same_cluster_is_not_compared_and_counts_as_no_independent_counterpart():
    a = obs(oid="PO-DOC-005-P012-L091", doc="DOC-005", price_level="1-8-2026")
    b = obs(oid="PO-DOC-006-P015-L093", doc="DOC-006")
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert r["pairs"] == [] and len(r["same_source_links"]) == 1
    assert {o["comparison_class_reason"] for o in r["observations"]} == {"NO_INDEPENDENT_COUNTERPART"}


def test_same_building_other_inspection_is_compared_without_content_reuse_caveat():
    a = obs(oid="PO-DOC-002-P026-L011", doc="DOC-002")
    b = obs(oid="PO-DOC-004-P026-L011", doc="DOC-004")
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert len(r["pairs"]) == 1
    assert "CONTENT_REUSE" not in r["pairs"][0]["pair_caveats"]   # P11 alleen met expliciet bewijs


def test_content_reuse_only_with_explicit_evidence():
    rel = copy.deepcopy(RELATIONS)
    for r_ in rel:
        if r_["type"] == "same_building_other_inspection":
            r_["content_reuse_evidence"] = "testbewijs"
    a = obs(oid="PO-DOC-002-P026-L011", doc="DOC-002")
    b = obs(oid="PO-DOC-004-P026-L011", doc="DOC-004")
    r = bc.evaluate([a, b], rel, ELEMENTS, SIGNALS)
    assert "CONTENT_REUSE" in r["pairs"][0]["pair_caveats"]


def test_same_inspector_creates_no_dependency():
    # DOC-005 en DOC-010: in batch 1 dezelfde inspecteur, geen documentrelatie
    a = obs(oid="PO-DOC-005-P012-L091", doc="DOC-005", price_level="1-4-2023")
    b = other()
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert r["observations"][0]["source_cluster"] != r["observations"][1]["source_cluster"]
    assert len(r["pairs"]) == 1


def test_pair_results_are_kept_per_observation():
    a, b, c = obs(), other(), other(oid="PO-DOC-007-P018-L065", doc="DOC-007", qty="25.5")
    r = bc.evaluate([a, b, c], RELATIONS, ELEMENTS, SIGNALS)
    assert len(r["pairs"]) == 3
    first = next(o for o in r["observations"] if o["observation_id"] == a["observation_id"])
    assert len(first["pair_ids"]) == 2 and first["comparison_class_reason"].startswith("best_pair:")


def test_tariff_group_within_document():
    a = obs(oid="PO-DOC-002-P014-L033", doc="DOC-002", qty="51", annual={"2030": "926"})
    b = obs(oid="PO-DOC-002-P014-L049", doc="DOC-002", qty="51", annual={"2030": "926"})
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert len(r["tariff_groups"]) == 1 and len(r["tariff_groups"][0]["observation_ids"]) == 2


# --------------------------------------------------------------------------
# Beslissingen na audit (docs/comparability_rules_v1.md sectie F)
# --------------------------------------------------------------------------

def test_unknown_observation_with_hard_material_difference_is_not_comparable():
    # F1: harde schending > UNKNOWN
    p = pair(obs(dependency="UNKNOWN"), other(element_id="EL-STAAL"))
    assert p["class"] == "NOT_COMPARABLE"
    assert "MATERIAL_DIFFERS" in p["hard_violations"] and "OBSERVATION_UNKNOWN" in p["unknown_reasons"]


def test_unknown_observation_without_hard_violation_is_unknown():
    p = pair(obs(dependency="UNKNOWN"), other())
    assert p["class"] == "UNKNOWN" and p["unknown_reasons"] == ["OBSERVATION_UNKNOWN"]


def test_possibly_dependent_observation_makes_pair_unknown():
    # F2: mogelijke afhankelijkheid is geen onafhankelijke vergelijkingsbasis
    o = obs(dependency="POSSIBLY_DEPENDENT")
    assert assess(o)["eligibility"] == "ELIGIBLE"  # eligibility zelf ongewijzigd
    p = pair(o, other())
    assert p["class"] == "UNKNOWN" and "POSSIBLY_DEPENDENT_OBSERVATION" in p["unknown_reasons"]
    p = pair(other(), obs(dependency="POSSIBLY_DEPENDENT"))
    assert p["class"] == "UNKNOWN"


def test_tariff_group_uses_exact_price_not_rounded_value():
    # F3: 926/85 = 10.894.. en 1089/100 = 10.89 ronden beide af op 10.89, maar zijn niet gelijk
    a = obs(oid="PO-DOC-002-P014-L033", doc="DOC-002", qty="85", annual={"2030": "926"})
    b = obs(oid="PO-DOC-002-P014-L049", doc="DOC-002", qty="100", annual={"2030": "1089"})
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    values = {o["derived_unit_price_per_execution"]["value"] for o in r["observations"]}
    assert values == {"10.89"} and r["tariff_groups"] == []
    # exact gelijke breuk (926/85 == 1852/170) vormt wel een tariefgroep
    c = obs(oid="PO-DOC-002-P014-L049", doc="DOC-002", qty="170", annual={"2030": "1852"})
    r = bc.evaluate([a, c], RELATIONS, ELEMENTS, SIGNALS)
    assert len(r["tariff_groups"]) == 1 and len(r["tariff_groups"][0]["observation_ids"]) == 2


def test_derived_price_kept_for_not_eligible_but_not_in_tariff_groups():
    # F4
    a = obs(oid="PO-DOC-002-P014-L033", doc="DOC-002", qty="51", annual={"2030": "926"},
            action_text="Vervangen voegwerk incl. steiger")
    b = obs(oid="PO-DOC-002-P014-L049", doc="DOC-002", qty="51", annual={"2030": "926"},
            action_text="Vervangen voegwerk incl. steiger")
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert all(o["eligibility"] == "NOT_ELIGIBLE" and o["derived_unit_price_per_execution"] for o in r["observations"])
    assert r["tariff_groups"] == [] and all(o["tariff_group_id"] is None for o in r["observations"])
    assert r["summary"]["derived_price_per_execution"] == 2
    assert r["summary"]["derived_price_per_execution_eligible"] == 0


def test_vat_unknown_on_one_side_is_unknown_not_hard():
    # F5
    for p in (pair(obs(vat=None), other()), pair(obs(), other(vat=None))):
        assert p["class"] == "UNKNOWN" and "VAT_BASIS_UNKNOWN" in p["unknown_reasons"]
        assert "VAT_BASIS_DIFFERS" not in p["hard_violations"]


@pytest.mark.parametrize("va,vb,cls,reason", [
    ("inclusive", "exclusive", "NOT_COMPARABLE", "VAT_BASIS_DIFFERS"),   # beide bekend, verschillend
    ("inclusive", None, "UNKNOWN", "VAT_BASIS_UNKNOWN"),                # een kant onbekend
    (None, None, "UNKNOWN", "VAT_BASIS_UNKNOWN"),                       # beide onbekend
])
def test_vat_basis_three_situations(va, vb, cls, reason):
    p = pair(obs(vat=va), other(vat=vb))
    assert p["class"] == cls
    assert reason in (p["hard_violations"] if cls == "NOT_COMPARABLE" else p["unknown_reasons"])
    if cls == "UNKNOWN":
        assert p["hard_violations"] == []


def test_same_known_vat_basis_is_no_issue():
    p = pair(obs(vat="inclusive"), other(vat="inclusive"))
    assert p["class"] == "COMPARABLE" and "VAT_BASIS_UNKNOWN" not in p["unknown_reasons"]


def test_possibly_dependent_with_hard_violation_is_not_comparable():
    p = pair(obs(dependency="POSSIBLY_DEPENDENT"), other(element_id="EL-STAAL"))
    assert p["class"] == "NOT_COMPARABLE" and "POSSIBLY_DEPENDENT_OBSERVATION" in p["unknown_reasons"]


def test_possibly_dependent_kept_with_derived_price_but_not_independent_input():
    # F6: blijft bestaan, eligibility/dependency ongewijzigd, afgeleide prijs aanwezig,
    # maar geen onafhankelijke input en geen tariefgroep
    a = obs(oid="PO-DOC-005-P012-L091", doc="DOC-005", qty="51", annual={"2030": "926"}, dependency="POSSIBLY_DEPENDENT")
    b = obs(oid="PO-DOC-005-P012-L095", doc="DOC-005", qty="51", annual={"2030": "926"}, dependency="POSSIBLY_DEPENDENT")
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert len(r["observations"]) == 2
    for o in r["observations"]:
        assert o["eligibility"] == "ELIGIBLE" and o["dependency_status"] == "POSSIBLY_DEPENDENT"
        assert o["derived_unit_price_per_execution"]["value"] == "18.16"
        assert o["independent_input"] is False and o["independent_input_exclusion_reasons"] == ["POSSIBLY_DEPENDENT"]
        assert o["tariff_group_id"] is None
    assert r["tariff_groups"] == []
    s = r["summary"]
    assert (s["derived_price_per_execution"], s["derived_price_per_execution_eligible"],
            s["derived_price_per_execution_independent_input"]) == (2, 2, 0)


def test_independent_observations_are_independent_input_and_form_tariff_group():
    a = obs(oid="PO-DOC-005-P012-L091", doc="DOC-005", qty="51", annual={"2030": "926"})
    b = obs(oid="PO-DOC-005-P012-L095", doc="DOC-005", qty="51", annual={"2030": "926"})
    r = bc.evaluate([a, b], RELATIONS, ELEMENTS, SIGNALS)
    assert all(o["independent_input"] and o["independent_input_exclusion_reasons"] == [] for o in r["observations"])
    assert len(r["tariff_groups"]) == 1
    assert r["summary"]["derived_price_per_execution_independent_input"] == 2


def test_not_eligible_is_not_independent_input():
    a = assess(obs(unit="lump_sum", qty="1"))
    a["dependency_status"] = "NO_DEPENDENCY_FOUND"
    ok, reasons = bc.independent_input(a)
    assert ok is False and "ELIGIBILITY_NOT_ELIGIBLE" in reasons


def test_signal_word_in_element_description_is_not_an_action_signal():
    for desc in ("Elektra armaturen binnen TL naar led", "Binnenschilderwerk stucwerk (incl. lambrisering)"):
        a = assess(obs(desc=desc, action_text="Vervangen armaturen"))
        assert a["signals_found"] == [] and a["eligibility"] == "ELIGIBLE"


@pytest.mark.parametrize("code", sorted(bc.OPEN_REVIEW_BLOCKING - {"element_context_missing"}))
def test_open_review_blocks_eligibility(code):
    a = assess(obs(review=(code,)))
    assert a["eligibility"] == "UNKNOWN" and f"OPEN_REVIEW:{code}" in a["eligibility_reasons"]


def test_unknown_unit_is_unknown():
    a = assess(obs(unit=None))
    assert a["eligibility"] == "UNKNOWN" and "UNIT_UNKNOWN" in a["eligibility_reasons"]
    assert a["derived_unit_price_per_execution"] is None


def test_unknown_total_scope_is_unknown():
    a = assess(obs(scope="UNKNOWN"))
    assert a["eligibility"] == "UNKNOWN" and "TOTAL_SCOPE_UNKNOWN" in a["eligibility_reasons"]
    assert a["derived_unit_price_per_execution"] is None


def test_mixed_material_is_caveat():
    a = assess(obs(element_id="EL-MIX"))
    assert a["eligibility"] == "ELIGIBLE_WITH_CAVEATS" and "MIXED_MATERIAL" in a["caveats"]


@pytest.mark.parametrize("label,action", [("Binnenschilderwerk stucwerk", "exterior_painting"),
                                          ("Buitenschilderwerk kozijnen", "interior_painting")])
def test_code_label_mismatch_is_caveat(label, action):
    a = assess(obs(label=label, action=action))
    assert a["eligibility"] == "ELIGIBLE_WITH_CAVEATS" and "CODE_LABEL_MISMATCH" in a["caveats"]
    assert "CODE_LABEL_MISMATCH" not in assess(obs(label=label, action="replace"))["caveats"]


# --------------------------------------------------------------------------
# Integratie op batch 1
# --------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(NORMALIZED), reason="normalized output ontbreekt")
def test_build_batch1_does_not_touch_sources_and_validates():
    before = (bc.sha256_file(NORMALIZED), bc.sha256_file(SOURCE))
    result = bc.build(PROJECT_ROOT)
    assert (bc.sha256_file(NORMALIZED), bc.sha256_file(SOURCE)) == before
    assert result["summary"]["observations"] == 404
    assert result["summary"]["source_clusters"] == 7
    assert result["duplicate_documents"] == [{"document_id": "DOC-003", "duplicate_of": "DOC-002",
                                              "source_cluster": "SC-DOC-002"}]
    assert all(p["source_clusters"][0] != p["source_clusters"][1] for p in result["pairs"])
    assert bc.validate_output(result, os.path.join(PROJECT_ROOT, "schemas", "comparability.schema.json")) == []
    keys = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                keys.add(k.lower())
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(result)
    forbidden = [k for k in keys if any(w in k for w in ("score", "median", "mean", "average", "kengetal", "p25", "p75"))]
    assert forbidden == []  # geen score- of kengetalvelden
