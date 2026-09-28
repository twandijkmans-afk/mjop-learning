"""
Tests voor scripts/build_promoted_price_observations.py (cloud-only PO-promotie, batch1_v1) en
scripts/promotion_v3_dry_run.py (evidence-based review + scenario's STRICT / SOURCE_EVIDENCE).
Canonieke data wordt alleen gelezen.
"""
import copy
import glob
import hashlib
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import build_promoted_price_observations as bpp  # noqa: E402
import promote_deterministic_batch as pdb  # noqa: E402
import promotion_v3_dry_run as pv3  # noqa: E402

PROTECTED = ["data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
             "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions",
             "data/extracted_deterministic"]


def _hashes():
    out = {}
    for d in PROTECTED:
        for p in sorted(glob.glob(os.path.join(PROJECT_ROOT, d, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                out[os.path.relpath(p, PROJECT_ROOT)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


@pytest.fixture(scope="module")
def v3():
    before = _hashes()
    layer, report, reviews = pv3.build_all(PROJECT_ROOT)
    assert _hashes() == before, "build_all heeft canonieke data gewijzigd"
    return layer, report, reviews


@pytest.fixture(scope="module")
def promoted():
    return bpp.build_promoted(PROJECT_ROOT)


# ------------------------------------------------------------------ cloud-only PO-promotie

def test_cloud_only_promotion_keeps_404_and_amounts(promoted):
    po, info, _, _, _ = promoted
    assert len(po["observations"]) == 404
    assert po["promotion"]["statement"] == bpp.STATEMENT and "geen nieuwe PDF parsing" in bpp.STATEMENT
    assert po["promotion"]["scope"].startswith("uitsluitend batch1_v1")
    canonical = pdb.load_json(os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json"))
    assert bpp.invariant_violations(canonical, po, info) == []
    assert {i["link"] for i in info.values()} <= bpp.EXPLAINED_LINKS | {"ambiguous"}


def _drop_first(po):
    po = copy.deepcopy(po)
    po["observations"] = po["observations"][1:]
    return po


def test_missing_observation_is_hard_fail(promoted):
    po, info, _, _, _ = promoted
    canonical = pdb.load_json(os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json"))
    v = bpp.invariant_violations(canonical, _drop_first(po), info)
    assert any("observation count" in x for x in v) and any("verdwenen" in x for x in v)


def test_amount_change_is_hard_fail(promoted):
    po, info, _, _, _ = promoted
    canonical = pdb.load_json(os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json"))
    bad = copy.deepcopy(po)
    o = bad["observations"][0]
    y = next(iter(o["annual_amounts"]))
    o["annual_amounts"][y] = "999999"
    v = bpp.invariant_violations(canonical, bad, info)
    assert any(o["observation_id"] in x and "annual_amounts" in x for x in v)


def test_unexplained_or_unproven_link_is_hard_fail(promoted):
    po, info, _, _, _ = promoted
    canonical = pdb.load_json(os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json"))
    info = copy.deepcopy(info)
    oid_none, oid_amb = sorted(info)[0], next(i for i, x in sorted(info.items()) if x["link"] == "ambiguous")
    info[oid_none] = {"link": "none"}
    info[oid_amb] = dict(info[oid_amb], identical_rows=False)
    v = bpp.invariant_violations(canonical, po, info)
    assert any(oid_none in x and "geen verklaarde koppeling" in x for x in v)
    assert any(oid_amb in x and "identieke rijen" in x for x in v)


def test_invalid_manifest_refuses_promotion(monkeypatch):
    monkeypatch.setattr(pdb, "check_handoff", lambda root: {"ok": False, "errors": ["manifest.sha256 klopt niet"]})
    with pytest.raises(bpp.PromotionError) as e:
        bpp.build_promoted(PROJECT_ROOT)
    assert "manifest.sha256" in e.value.violations[0]


def test_builder_refuses_canonical_output():
    assert bpp.main(["--out", "data/price_observations/x.json"]) == 2


# ------------------------------------------------------------------ materiaalbewijs (synthetisch)

VOCAB = {"hout": "wood", "beton": "concrete", "pvc": "pvc", "staal": "steel", "zink": "zinc"}


def _case(name, action, old_orig, old_norm, loc=""):
    oid = "PO-X"
    old_norm_po = {"observations": [{"observation_id": oid, "material": {
        "material_original": old_orig, "material_normalized": old_norm, "material_from_text": None,
        "material_source": "verified_element"}}]}
    strict = {"observations": [{"observation_id": oid, "material": {
        "material_original": None, "material_normalized": None, "material_from_text": None, "material_source": None,
        "material_not_derived_reason": "verified_material_empty"}}]}
    po = {"observations": [{"observation_id": oid, "document_id": "DOC-900", "element": {"element_id": "E1"},
                            "action": {"action_text_original": action}}]}
    verified = {"DOC-900": {"elements": [{"element_id": "E1", "element_name": {"value": name},
                                          "location": {"value": loc}}]}}
    return pv3.classify_material_evidence(old_norm_po, strict, po, verified, VOCAB)["records"][0]


def test_explicit_source_evidence():
    r = _case("Hemelwaterafvoer pvc", "Vervangen hemelwaterafvoer pvc", "pvc", "pvc")
    assert r["classification"] == "EXPLICIT_SOURCE_EVIDENCE"
    assert r["promotion_candidate"]["material_normalized"] == "pvc"
    assert "niet canoniek" in r["promotion_candidate"]["status"]


def test_old_derivation_only():
    r = _case("Gevelconstructie metselwerk", "Reinigen", "baksteen", "brick")
    assert r["classification"] == "OLD_DERIVATION_ONLY"


def test_no_fuzzy_compound_word_is_not_evidence():
    r = _case("Buitenschilderwerk betonconstructie plafond", "Groot schilderwerk betonconstructie", "beton", "concrete")
    assert r["classification"] == "OLD_DERIVATION_ONLY" and "promotion_candidate" not in r


@pytest.mark.parametrize("name,action,orig,norm,why", [
    ("Kozijn hout", "Groot schilderwerk kozijn", "staal", "steel", "ander materiaal"),
    ("Hijsbalk hout en staal", "Vervangen", "hout", "wood", "meerdere"),
    ("Goot zink", "Vervangen goot zink -> pvc", "zink", "zinc", "actietekst"),
    ("Deur", "Vervangen deur hout", "hout", "wood", "actietekst"),
    ("Gevel metselwerk", "Reinigen", "metselwerk", "masonry", "niet in vocabularies"),
])
def test_ambiguous_source_evidence(name, action, orig, norm, why):
    r = _case(name, action, orig, norm)
    assert r["classification"] == "AMBIGUOUS_SOURCE_EVIDENCE" and why in r["reason"]


# ------------------------------------------------------------------ echte v3-run

def test_material_evidence_covers_all_class_a(v3):
    _, report, reviews = v3
    counts = report["material_evidence"]["counts"]
    assert sum(counts.values()) == 215
    recs = reviews[pv3.MATERIAL_REVIEW]["records"]
    assert all(("promotion_candidate" in r) == (r["classification"] == "EXPLICIT_SOURCE_EVIDENCE") for r in recs)


def test_accept_review_covers_all_non_exact(v3):
    _, report, reviews = v3
    acc = reviews[pv3.ACCEPT_REVIEW]
    assert acc["total"] == sum(acc["counts"].values()) == 89
    assert acc["counts"]["DUPLICATE_SKIP"] == 1
    assert all(r["proposal_only"] for r in acc["records"])


def test_decisions_by_observation_set(v3):
    _, report, reviews = v3
    for scen in pv3.SCENARIOS:
        d = reviews[pv3.DECISION_REVIEW][scen]
        assert sum(d["counts"].values()) == 30 and d["counts"]["PAIR_NO_LONGER_EXISTS"] == 0
        for r in d["records"]:
            assert r["observation_ids"] == sorted(r["observation_ids"]) and "pair_id_metadata" in r


def test_strict_vs_source_evidence(v3):
    _, report, _ = v3
    s, e = report["scenarios"]["STRICT"], report["scenarios"]["SOURCE_EVIDENCE"]
    for x in (s, e):
        assert x["amount_changes"] == 0 and x["comparability_unexplained"] == 0 and x["source_clusters_identical"]
        assert x["material_changes_vs_canonical"]["C_regression"] == 0
    assert e["material_unknown"] < s["material_unknown"]
    assert "AVAILABLE" not in s["kengetallen_status"]
    # geen geforceerde status: elk AVAILABLE-kengetal heeft geen insufficient-redenen en >= 3 clusters
    for k in e["kengetallen"]:
        if k["status"] == "AVAILABLE":
            assert not k["insufficient_data_reasons"] and len(k["clusters"]) >= 3


def test_overlay_only_explicit_evidence(v3):
    layer, _, reviews = v3
    explicit = {r["observation_id"] for r in reviews[pv3.MATERIAL_REVIEW]["records"]
                if r["classification"] == "EXPLICIT_SOURCE_EVIDENCE"}
    for a in layer["source_evidence_verified_overlay"]:
        assert set(a["observations"]) <= explicit


def test_no_blockers_and_canonical_unchanged(v3, tmp_path):
    layer, report, reviews = v3
    assert report["blockers"] == []
    before = _hashes()
    (tmp_path / "reports").mkdir()
    pv3.write_outputs(str(tmp_path), layer, report, reviews)
    assert _hashes() == before


def test_committed_v3_outputs_current():
    assert pv3.main(["--check"]) == 0
