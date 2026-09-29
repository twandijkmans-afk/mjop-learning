"""
Tests voor het beslispakket 4711|replace|m1 aluminium (scripts/decision_package_4711_aluminium.py):

  - alleen lezen: het echte repo (incl. besluit- en materiaalopslag) blijft byte-gelijk;
  - het vastgelegde pakket is actueel en deterministisch;
  - materiaal-precheck via record_material_decision.validate, zonder iets vast te leggen;
  - simulaties volgen de bestaande kengetalregels: zonder materiaalbesluit MATERIAL_UNKNOWN, met materiaalbesluit
    en alle drie paren positief AVAILABLE met 3 clusters; zink blijft INSUFFICIENT_DATA.
"""
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import comparability_review_v2 as crv  # noqa: E402
import decision_package_4711_aluminium as dp  # noqa: E402
import promotion_ledger as pl  # noqa: E402

ALU_PENDING = ["PO-DOC-011-P021-L083", "PO-DOC-012-P014-L107"]
ALU_PAIRS = ["PAIR-00557", "PAIR-00558", "PAIR-00561"]


def _protected():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for rel in (dp.OUT_JSON, dp.OUT_MD, crv.OUT_JSON, crv.OUT_MD):
        out[rel] = pl.sha256_file(os.path.join(PROJECT_ROOT, rel))
    return out


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = _protected()
    yield
    assert _protected() == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def package():
    return dp.build(PROJECT_ROOT)


def test_package_committed_and_deterministic(package):
    assert crv.dump(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_JSON), encoding="utf-8").read()
    assert dp.render_md(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_MD), encoding="utf-8").read()
    assert crv.dump(dp.build(PROJECT_ROOT)) == crv.dump(package)


def test_no_existing_kengetal_and_nothing_decided(package):
    assert package["existing_kengetallen"] == []
    alu = package["groups"]["aluminium"]
    assert all(p["active_decision"] is None for p in alu["cross_cluster_pairs"])
    for oid in ALU_PENDING:
        s = next(o for o in package["observations"] if o["observation_id"] == oid)
        assert s["material"]["value"] is None and s["material_decision_id"] is None
        assert s["material_status"] == "TEXT_EVIDENCE_PENDING_APPROVAL:aluminium"


def test_material_precheck_exact_and_literal(package):
    steps = package["groups"]["aluminium"]["material_steps"]
    assert [s["observation_id"] for s in steps] == ALU_PENDING
    for s in steps:
        assert s["record_material_decision_precheck"] == "WOULD_BE_ACCEPTED"
        assert s["evidence"] == {"element_description_original": "Dakrandafwerking aluminium trim",
                                 "action_text_original": "Vervangen daktrim aluminium", "unit_original": "m1"}
    zinc = package["groups"]["zinc"]["material_steps"]
    assert [(s["observation_id"], s["material"], s["record_material_decision_precheck"]) for s in zinc] == \
        [("PO-DOC-013-P018-L087", "zink", "WOULD_BE_ACCEPTED")]
    # observations zonder tekstbewijs komen niet in een materiaalstap
    no_ev = {o["observation_id"] for o in package["observations"] if o["material_status"] == "NO_MATERIAL_EVIDENCE"}
    assert no_ev == {"PO-DOC-007-P018-L015", "PO-DOC-007-P018-L033", "PO-DOC-012-P014-L111"}
    assert not no_ev & {s["observation_id"] for g in package["groups"].values() for s in g["material_steps"]}


def test_aluminium_pairs_match_the_description(package):
    alu = package["groups"]["aluminium"]
    assert alu["potential_source_clusters"]["count"] == 3
    assert sorted(p["pair_id"] for p in alu["cross_cluster_pairs"] if p["open"]) == ALU_PAIRS
    assert alu["pairs_not_matching_description"] == []
    for p in alu["cross_cluster_pairs"]:
        assert p["content_check"]["matches_description"]
        assert set(p["pair_caveats"]) <= set(dp.ALLOWED_DIFFERENCES)
        assert p["review_family_id_before_material_decision"] != p["review_family_id_after_material_decision"]


def _kg(result, material):
    return [r for r in result if r["material"] == material]


def test_simulations_follow_existing_rules(package):
    alu = package["groups"]["aluminium"]
    without = _kg(alu["simulation_without_material_decision_all_pairs_positive"], "aluminium")
    assert [r["status"] for r in without] == ["INSUFFICIENT_DATA"]
    assert any(x.startswith("MATERIAL_UNKNOWN") for x in without[0]["insufficient_data_reasons"])
    combos = alu["combined_scenarios_after_material_decision"]
    for c in ("COMPARABLE", "COMPARABLE_WITH_CAVEATS"):
        (kg,) = _kg(combos[f"ALL_OPEN_FAMILIES_{c}"], "aluminium")
        assert kg["status"] == "AVAILABLE" and kg["source_cluster_count"] == 3
        assert kg["missing_price_level"]
    assert _kg(combos["ALL_OPEN_FAMILIES_NOT_COMPARABLE"], "aluminium") == []
    # één familie alleen is nooit genoeg
    for f in alu["open_families_after_material_decision"]:
        for r in _kg(f["simulations"]["COMPARABLE_WITH_CAVEATS"], "aluminium"):
            assert r["status"] == "INSUFFICIENT_DATA"
    zinc = package["groups"]["zinc"]
    assert zinc["potential_source_clusters"]["count"] == 2
    for res in zinc["combined_scenarios_after_material_decision"].values():
        assert all(r["status"] == "INSUFFICIENT_DATA" for r in _kg(res, "zinc"))
