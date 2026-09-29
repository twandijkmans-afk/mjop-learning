"""
Tests voor scripts/match_kengetal.py - matching v1: exacte candidate retrieval
(element_code + action + unit + bekend materiaal, alleen AVAILABLE) en
deterministische scope-check. Geen fuzzy matching, score of confidence.
"""
import copy
import json
import os
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import match_kengetal as m  # noqa: E402
import promotion_history as ph  # noqa: E402

SCHEMA = os.path.join(PROJECT_ROOT, "schemas", "match_result.schema.json")
CTX = m.load_context(PROJECT_ROOT)
# Na de canonieke promotie van batch1_v1 is C1 (4645) geen canoniek kengetal meer (het steunde op
# DF-1/DF-2-decisions die nu REVIEW_REQUIRED zijn). De matching-mechaniek met C1/C3 wordt daarom
# getest tegen de pre-promotie-kengetallen uit data/history als vaste, alleen-lezen fixture.
FIX_CTX = m.load_context(ph.pre_promotion_fixture_root(PROJECT_ROOT))
C1 = "KG-4645-exterior_painting-m2-concrete-2f1a7a14"
# C2 = canonieke 5211 pvc-versie na het menselijke familiebesluit RFD-00001 (5 clusters; vorige versie
# KG-5211-replace-m1-pvc-67920b77 / 51.79 staat in data/kengetallen/history)
C2 = "KG-5211-replace-m1-pvc-5cb98033"
# C4 = 4711 replace m1 aluminium na materiaalbesluit MATDEC-00002 en familiebesluit RFD-00002 (3 clusters)
C4 = "KG-4711-replace-m1-aluminium-d463b0a2"


def item(**over):
    base = dict(object_id="NEW-1", element_code_internal="4645", action_normalized="exterior_painting",
                unit_normalized="m2", material_normalized="concrete", material_source="user",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80",
                vat_basis="inclusive", price_level_requested=None)
    base.update(over)
    return base


def c2_item(**over):
    base = dict(element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", object_description="Hemelwaterafvoer pvc", quantity="100")
    base.update(over)
    return item(**base)


def run(raw, ctx=CTX):
    r = m.match(PROJECT_ROOT, raw, ctx)
    assert m.validate_output(r, SCHEMA) == []
    return r


# --------------------------------------------------------------------------
# Exacte retrieval
# --------------------------------------------------------------------------

def test_canonical_c1_no_longer_available_after_promotion():
    r = run(item())
    assert (r["retrieval_status"], r["final_status"]) == ("NO_CANDIDATE", "NO_SUITABLE_KENGETAL")
    assert r["reasons"] == ["NO_KENGETAL_FOR_KEY"] and r["candidate_kengetal_id"] is None
    assert [k["kengetal_id"] for k in CTX[0]["kengetallen"]] == [C4, C2]


def test_c1_exact_retrieval_and_scope():
    r = run(item(), FIX_CTX)
    assert (r["retrieval_status"], r["scope_status"], r["final_status"]) == ("CANDIDATES_RETRIEVED", "EXACT_MATCH", "CANDIDATE_FOUND")
    assert r["candidate_kengetal_id"] == C1 and r["historical_range"]["value_display"] == "33.48"
    assert all(f["equal"] for f in r["hard_match_fields"].values())
    assert r["scope_evidence"]["matched_member_observation_ids"]  # herleidbaar naar groepsleden


def test_c1_other_wording_is_candidate_but_needs_human_scope_review():
    r = run(item(object_description="betonconstructie plafond buiten"), FIX_CTX)
    assert r["retrieval_status"] == "CANDIDATES_RETRIEVED" and r["candidate_kengetal_id"] == C1
    assert r["final_status"] == "HUMAN_REVIEW_REQUIRED" and r["reasons"] == ["SCOPE_NOT_DETERMINISTIC"]
    assert r["required_human_review"] is True


def test_c2_exact_retrieval_and_scope():
    r = run(c2_item())
    assert r["final_status"] == "CANDIDATE_FOUND" and r["candidate_kengetal_id"] == C2
    assert r["historical_range"]["value_display"] == "54.39"


def test_input_is_normalized_with_existing_vocabularies():
    r = run(c2_item(action_normalized=None, action_text="Vervangen hemelwaterafvoer pvc",
                    unit_normalized=None, unit_text="m1", material_normalized=None, material_text="pvc"))
    n = r["input_normalized"]
    assert (n["action"], n["action_basis"]) == ("replace", "vocabulary_lookup")   # exacte lookup gaat vóór prefix
    assert (n["unit"], n["material"]) == ("m1", "pvc") and r["final_status"] == "CANDIDATE_FOUND"
    r = run(c2_item(action_normalized=None, action_text="Vervangen hwa pvc nieuwbouwdeel"))
    assert (r["input_normalized"]["action"], r["input_normalized"]["action_basis"]) == ("replace", "prefix_rule:vervangen")


def test_unnormalizable_action_text_is_not_guessed():
    r = run(item(action_normalized=None, action_text="Groot schilderwerk betonconstructie plafond"))
    assert r["final_status"] == "NO_SUITABLE_KENGETAL" and r["reasons"] == ["INPUT_KEY_INCOMPLETE"]


# --------------------------------------------------------------------------
# Harde mismatches
# --------------------------------------------------------------------------

@pytest.mark.parametrize("over", [
    {"action_normalized": "interior_painting"},      # C1 binnen i.p.v. buiten
    {"unit_normalized": "m1"},
    {"material_normalized": "wood"},                 # C1 hout i.p.v. beton
    {"element_code_internal": "4621"},
])
def test_hard_key_mismatch_gives_no_candidate(over):
    r = run(item(**over))
    assert (r["retrieval_status"], r["final_status"]) == ("NO_CANDIDATE", "NO_SUITABLE_KENGETAL")
    assert r["reasons"] == ["NO_KENGETAL_FOR_KEY"] and r["candidate_kengetal_id"] is None
    assert r["historical_range"] is None


def test_c2_steel_and_piece_are_no_candidate():
    assert run(c2_item(material_normalized="steel"))["final_status"] == "NO_SUITABLE_KENGETAL"
    assert run(c2_item(unit_normalized="piece"))["final_status"] == "NO_SUITABLE_KENGETAL"


# --------------------------------------------------------------------------
# Materiaal
# --------------------------------------------------------------------------

def test_unknown_material_never_retrieves():
    r = run(item(material_normalized=None, material_text=None))
    assert r["reasons"] == ["MATERIAL_UNKNOWN"] and r["retrieval_status"] == "NO_CANDIDATE"


def test_material_sources_are_carried_through():
    r = run(c2_item(material_source="element_text"))
    assert r["input_normalized"]["material_source"] == "element_text"
    assert "KENGETAL_MATERIAL_PARTLY_FROM_ELEMENT_TEXT" in r["caveats"]["match_caveats"]   # C2 bevat DOC-001 uit tekst
    assert run(c2_item(material_source="verified_element"))["final_status"] == "CANDIDATE_FOUND"


def test_kunststof_doorvoer_is_retrieved_but_not_auto_matched():
    # bekende edge case: 'kunststof' normaliseert naar pvc, dus de exacte sleutel haalt C2 op
    r = run(c2_item(material_normalized=None, material_text="kunststof", object_description="Doorvoer kunststof"))
    assert r["retrieval_key"]["material"] == "pvc" and r["retrieval_status"] == "CANDIDATES_RETRIEVED"
    assert r["final_status"] == "HUMAN_REVIEW_REQUIRED" and r["reasons"] == ["SCOPE_NOT_DETERMINISTIC"]


# --------------------------------------------------------------------------
# Status en scope
# --------------------------------------------------------------------------

def test_insufficient_data_kengetal_is_not_a_candidate():
    r = run(item(element_code_internal="4622", action_normalized="interior_painting", material_normalized=None,
                 material_text="stucwerk", object_description="Binnenschilderwerk stucwerk"), FIX_CTX)
    assert r["final_status"] == "NO_SUITABLE_KENGETAL" and r["reasons"] == ["KENGETAL_INSUFFICIENT_DATA"]
    assert r["provenance"]["insufficient_data_kengetal_ids"] == ["KG-4622-interior_painting-m2-stucwerk-1a17b521"]


def synthetic_ctx(**changes):
    kengetallen, normalized, vocabs, hashes, rel = copy.deepcopy(FIX_CTX)
    c3 = next(k for k in kengetallen["kengetallen"] if k["kengetal_id"].startswith("KG-4622"))
    c3.update(changes)
    return (kengetallen, normalized, vocabs, hashes, rel), c3


def test_scope_mismatch_from_human_not_comparable_evidence():
    # C3 als AVAILABLE gesimuleerd: de lambriseringspost is door een mens NOT_COMPARABLE verklaard
    ctx, _ = synthetic_ctx(status="AVAILABLE")
    r = run(item(element_code_internal="4622", action_normalized="interior_painting", material_normalized=None,
                 material_text="stucwerk", object_description="Binnenschilderwerk stucwerk (incl. lambrisering)"), ctx)
    assert r["retrieval_status"] == "CANDIDATES_RETRIEVED"
    assert (r["scope_status"], r["final_status"]) == ("MISMATCH", "NO_SUITABLE_KENGETAL")
    assert r["reasons"] == ["SCOPE_MISMATCH_HUMAN_NOT_COMPARABLE"]
    ev = r["candidate_evaluations"][0]["scope_evidence"]
    assert ev["human_not_comparable_evidence"]["PO-DOC-010-P012-L017"] == ["HUMAN_NOT_COMPARABLE:HDR-00005",
                                                                           "HUMAN_NOT_COMPARABLE:HDR-00007"]


def test_missing_description_needs_review():
    r = run(item(object_description=None), FIX_CTX)
    assert r["final_status"] == "HUMAN_REVIEW_REQUIRED" and r["reasons"] == ["OBJECT_DESCRIPTION_MISSING"]


def test_multiple_candidates_are_not_ranked():
    kengetallen, normalized, vocabs, hashes, rel = copy.deepcopy(FIX_CTX)
    c1 = next(k for k in kengetallen["kengetallen"] if k["kengetal_id"] == C1)
    twin = copy.deepcopy(c1)
    twin["kengetal_id"] = C1 + "-twin"
    kengetallen["kengetallen"].append(twin)
    r = run(item(), (kengetallen, normalized, vocabs, hashes, rel))
    assert r["final_status"] == "HUMAN_REVIEW_REQUIRED" and r["reasons"] == ["MULTIPLE_CANDIDATES"]
    assert r["candidate_kengetal_id"] is None and len(r["candidate_kengetal_ids"]) == 2


def test_vat_difference_needs_review():
    r = run(c2_item(vat_basis="exclusive"))
    assert r["scope_status"] == "EXACT_MATCH" and r["final_status"] == "HUMAN_REVIEW_REQUIRED"
    assert r["reasons"] == ["VAT_BASIS_DIFFERS"]


def test_price_and_quantity_are_presented_not_adjusted():
    r = run(c2_item(quantity="500", price_level_requested=2026))
    caveats = r["caveats"]["match_caveats"]
    assert {"QUANTITY_OUTSIDE_HISTORICAL_RANGE", "NOT_INDEXED", "PRICE_LEVEL_MIXED", "PRICE_LEVEL_MISSING_IN_SOURCE",
            "REQUESTED_PRICE_LEVEL_NOT_REPRESENTED"} <= set(caveats)
    kg = next(k for k in CTX[0]["kengetallen"] if k["kengetal_id"] == C2)
    assert r["historical_range"]["value_exact"] == kg["value_exact"]   # prijs ongewijzigd
    assert "QUANTITY_WITHIN_HISTORICAL_RANGE" in run(c2_item(quantity="100"))["caveats"]["match_caveats"]


def test_no_score_rank_or_confidence_fields():
    keys = set()

    def walk(x):
        if isinstance(x, dict):
            keys.update(k.lower() for k in x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(run(item(), FIX_CTX))
    assert not any(w in k for k in keys for w in ("score", "rank", "confidence", "weight"))


# --------------------------------------------------------------------------
# Integriteit en determinisme
# --------------------------------------------------------------------------

def test_matching_does_not_touch_inputs():
    p = m.paths(PROJECT_ROOT)
    files = [p["kengetallen"], p["normalized"]] + [os.path.join(p["vocab_dir"], f"{n}.json")
                                                   for n in ("maintenance_action", "unit", "material")]
    before = [m.sha256_file(f) for f in files]
    ctx_before = copy.deepcopy(CTX)
    run(item()), run(c2_item()), run(item(material_normalized=None))
    assert [m.sha256_file(f) for f in files] == before and CTX == ctx_before


def test_same_input_gives_byte_identical_result():
    assert m.dump(m.match(PROJECT_ROOT, item())) == m.dump(m.match(PROJECT_ROOT, item()))


def test_match_result_id_distinguishes_basis_versions(monkeypatch):
    base = run(item())
    n, hashes = base["input_normalized"], base["input_hashes"]
    rid = base["match_result_id"]
    assert rid == m.match_result_id(n, hashes, "kengetallen_rules_v1")
    assert run(item(quantity="81"))["match_result_id"] != rid                      # andere input
    for part in ("kengetallen_output_sha256", "normalized_observations_sha256"):
        assert m.match_result_id(n, dict(hashes, **{part: "0" * 64}), "kengetallen_rules_v1") != rid
    vocab = dict(hashes["vocabularies_sha256"], material="0" * 64)
    assert m.match_result_id(n, dict(hashes, vocabularies_sha256=vocab), "kengetallen_rules_v1") != rid
    assert m.match_result_id(n, hashes, "kengetallen_rules_v2") != rid
    monkeypatch.setattr(m, "RULE_VERSION", "matching_rules_v2")
    assert m.match_result_id(n, hashes, "kengetallen_rules_v1") != rid


def test_cli_refuses_to_write_into_data(tmp_path):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(c2_item()), encoding="utf-8")
    script = os.path.join(PROJECT_ROOT, "scripts", "match_kengetal.py")
    bad = subprocess.run([sys.executable, script, "--input", str(inp), "--out",
                          os.path.join(PROJECT_ROOT, "data", "x.json")], capture_output=True)
    assert bad.returncode == 2 and not os.path.exists(os.path.join(PROJECT_ROOT, "data", "x.json"))
    out = tmp_path / "out.json"
    ok = subprocess.run([sys.executable, script, "--input", str(inp), "--out", str(out)], capture_output=True)
    assert ok.returncode == 0 and json.loads(out.read_text(encoding="utf-8"))["final_status"] == "CANDIDATE_FOUND"
