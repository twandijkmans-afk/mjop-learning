"""
Tests voor 4711|replace|m1 aluminium:

  - menselijk materiaalbesluit MATDEC-00002: aluminium voor EXACT PO-DOC-011-P021-L083 en PO-DOC-012-P014-L107
    (MDR-00003, MDR-00004), letterlijk bewijs, geen scope leak;
  - atomair familiebesluit RFD-00002: RF-4711-17297bd2b3 en RF-4711-0f1822792b als COMPARABLE_WITH_CAVEATS
    (reviewer twandijkmans), alleen bestaande caveats; nieuw AVAILABLE kengetal met 3 clusters;
  - beslispakket (scripts/decision_package_4711_aluminium.py): actueel, deterministisch, neemt zelf niets besluit;
  - rollback van beide schakels op een kopie herstelt de vorige toestand exact.

Het echte repo wordt alleen gelezen (gecontroleerd met hashes); writes alleen in een tijdelijke kopie.
"""
import copy
import json
import os
import shutil
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import apply_family_decision as afd  # noqa: E402
import canonical_change as cc  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import decision_package_4711_aluminium as dp  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402

MATDEC, RFD = "MATDEC-00002", "RFD-00002"
TARGETS = ["PO-DOC-011-P021-L083", "PO-DOC-012-P014-L107"]
EVIDENCE = {"element_description_original": "Dakrandafwerking aluminium trim",
            "action_text_original": "Vervangen daktrim aluminium", "unit_original": "m1"}
FAMILIES = {"RF-4711-17297bd2b3": (["PAIR-00557", "PAIR-00558"], ["PRICE_LEVEL_ABSENT"]),
            "RF-4711-0f1822792b": (["PAIR-00561"], ["PRICE_LEVEL_ABSENT"])}
NEW_IDS = ["HDR-00043", "HDR-00044", "HDR-00045"]
KG = "KG-4711-replace-m1-aluminium-d463b0a2"
CLUSTERS = ["SC-DOC-008+DOC-009", "SC-DOC-011", "SC-DOC-012"]

pytestmark = pytest.mark.skipif(not os.path.isfile(os.path.join(PROJECT_ROOT, pl.STATE_DIR, f"{RFD}.json")),
                                reason="besluiten 4711 aluminium niet vastgelegd")


def load(*rel):
    with open(os.path.join(PROJECT_ROOT, *rel), encoding="utf-8") as f:
        return json.load(f)


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
def matdec():
    return load(pl.STATE_DIR, f"{MATDEC}.json")


@pytest.fixture(scope="module")
def rfd():
    return load(pl.STATE_DIR, f"{RFD}.json")


def pre(state, rel):
    with open(os.path.join(PROJECT_ROOT, state["history"], "pre", rel), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ materiaalbesluit MATDEC-00002

def test_material_decision_exact_two_observations(matdec):
    assert matdec["status"] == "APPLIED" and matdec["change_kind"] == "material_decision"
    d = matdec["decision"]["material_decision"]
    assert d["reviewer"] == "twandijkmans"
    assert [(a["observation_id"], a["material"], a["evidence"]) for a in d["approvals"]] == \
        [(i, "aluminium", EVIDENCE) for i in TARGETS]
    recs = {r["decision_id"]: r for r in load("data", "review_decisions", "material_decision_records.json")["records"]}
    for mdr, oid in zip(("MDR-00003", "MDR-00004"), TARGETS):
        r = recs[mdr]
        assert (r["observation_id"], r["scope"], r["status"]) == (oid, "EXACT_OBSERVATION", "ACTIVE")
        assert r["material"] == {"original_value": "aluminium", "normalized_value": "aluminium"}
        assert {k: r["evidence"][k] for k in EVIDENCE} == EVIDENCE
        assert r["reviewer"] == {"reviewer_id": "twandijkmans", "reviewer_type": "human"}
    # het materiaalbesluit zelf veranderde geen kengetal en geen pair decisions
    assert matdec["summary"]["kengetallen"]["content_changed"] is False
    rel = "data/review_decisions/human_decision_records.json"
    assert matdec["pre_manifest"][rel] == matdec["post_manifest"][rel]


def test_material_decision_no_scope_leak(matdec):
    old = {o["observation_id"]: o for o in pre(matdec, pr.NORM_PO_PATH)["observations"]}
    new = {o["observation_id"]: o for o in load("data", "price_observations",
                                                  "price_observations_batch1_normalized.json")["observations"]}
    assert set(old) == set(new) and len(new) == 545
    assert sorted(i for i in new if new[i] != old[i]) == TARGETS
    for oid in TARGETS:
        assert {k: v for k, v in new[oid].items() if k != "material"} == \
            {k: v for k, v in old[oid].items() if k != "material"}
        assert new[oid]["material"]["material_status"] == "MATERIAL_FROM_HUMAN_DECISION"
    # andere 4711-observations van dezelfde documenten blijven zonder materiaal
    assert new["PO-DOC-012-P014-L111"]["material"]["material_status"] == "MATERIAL_UNKNOWN"
    assert new["PO-DOC-013-P018-L087"]["material"]["material_status"] == "MATERIAL_UNKNOWN"
    for rel in ("data/price_observations/price_observations_batch1.json",
                "data/price_observations/document_relations.json"):
        assert matdec["pre_manifest"][rel] == matdec["post_manifest"][rel] == \
            pl.sha256_file(os.path.join(PROJECT_ROOT, rel)), rel
    assert len(load("data", "comparability", "comparability_batch1.json")["source_clusters"]) == 11


# ------------------------------------------------------------------ familiebesluit RFD-00002

def test_family_decision_one_atomic_transaction(rfd):
    assert rfd["status"] == "APPLIED" and rfd["change_kind"] == "family_decision"
    d = rfd["decision"]["family_decision"]
    assert d["reviewer"] == "twandijkmans" and d["decision"] == "COMPARABLE_WITH_CAVEATS"
    assert {f["review_family_id"]: (f["pair_ids"], f["decision_caveats"]) for f in d["families"]} == FAMILIES
    assert d["acknowledged_kengetal_effects"] == [KG]
    assert rfd["summary"]["applied_decision_ids"] == NEW_IDS
    saved = load("data", "review_decisions", "family_decisions", f"{RFD}.json")
    assert saved["applied_decision_ids"] == NEW_IDS and saved["superseded_decision_ids"] == []
    assert pl.chain_errors(PROJECT_ROOT) == [] and pr.verify(PROJECT_ROOT) == []


def test_three_new_active_decisions_only_existing_caveats(rfd):
    store = load("data", "review_decisions", "human_decision_records.json")["records"]
    old = pre(rfd, pr.DECISIONS_PATH)["records"]
    assert store[:len(old)] == old
    new = store[len(old):len(old) + len(NEW_IDS)]
    assert [r["decision_id"] for r in new] == NEW_IDS
    by_pair = {r["pair_id"]: r for r in new}
    for fid, (pairs, caveats) in FAMILIES.items():
        for pid in pairs:
            r = by_pair[pid]
            assert r["status"] == "ACTIVE" and r["decision"] == "COMPARABLE_WITH_CAVEATS"
            assert r["decision_caveats"] == caveats and r["supersedes"] is None
            assert r["family_decision"] == {**r["family_decision"], "family_decision_id": RFD,
                                            "review_family_id": fid}
            system = set(r["system_reasons"]["pair_caveats"]) | set(r["system_reasons"]["observation_caveats"]["a"]) \
                | set(r["system_reasons"]["observation_caveats"]["b"])
            assert set(caveats) <= system and r["system_reasons"]["hard_violations"] == []


def test_new_available_kengetal(rfd):
    kgs = {k["kengetal_id"]: k for k in load("data", "kengetallen", "kengetallen_batch1.json")["kengetallen"]}
    k = kgs[KG]
    assert (k["status"], k["value_display"], k["min_display"], k["max_display"], k["source_cluster_count"]) == \
        ("AVAILABLE", "37.47", "33.88", "39.06", 3)
    assert k["source_cluster_ids"] == CLUSTERS and k["human_review_complete"]
    assert k["observation_ids"] == ["PO-DOC-008-P009-L045"] + TARGETS
    assert k["decision_ids"] == NEW_IDS and k["price_levels"]["missing_price_level"]
    # 5211 pvc onveranderd
    assert (kgs["KG-5211-replace-m1-pvc-5cb98033"]["value_display"],
            kgs["KG-5211-replace-m1-pvc-5cb98033"]["source_cluster_count"]) == ("54.39", 5)
    changed = sorted(p for p in set(rfd["pre_manifest"]) | set(rfd["post_manifest"])
                     if rfd["pre_manifest"].get(p) != rfd["post_manifest"].get(p))
    hist = [p for p in changed if p.startswith("data/kengetallen/history/")]
    assert len(hist) == 1 and changed == sorted(["data/review_decisions/human_decision_records.json",
                                                 f"data/review_decisions/family_decisions/{RFD}.json",
                                                 "data/kengetallen/kengetallen_batch1.json"] + hist)


# ------------------------------------------------------------------ rollback op een kopie

def make_copy(dst):
    for rel in pr.SIMULATION_COPY + ("reports/review",):
        s, d = os.path.join(PROJECT_ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return dst


def test_rollback_both_links_and_atomicity_on_copy(tmp_path, matdec, rfd):
    root = make_copy(str(tmp_path / "p"))
    while pl.latest(root)["promotion_id"] != RFD:
        cc.rollback(root, pl.latest(root)["promotion_id"])
    assert cc.rollback(root, RFD).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(root) == rfd["pre_manifest"]
    assert KG not in {k["kengetal_id"] for k in pr.load(os.path.join(root, pr.KG_PATH))["kengetallen"]}
    # één familie met een nieuwe caveat -> niets toegepast
    crv.write(root)
    d = copy.deepcopy(rfd["decision"]["family_decision"])
    d.pop("family_decision_id", None)
    d["review_package_sha256"] = pl.sha256_file(os.path.join(root, crv.OUT_JSON))
    bad = copy.deepcopy(d)
    bad["families"][1]["decision_caveats"] = ["PRICE_LEVEL_DIFFERENCE"]
    with pytest.raises(afd.FamilyDecisionError, match="geen nieuwe caveats"):
        afd.apply(root, bad)
    bad = copy.deepcopy(d)
    bad["acknowledged_kengetal_effects"] = []
    with pytest.raises(afd.FamilyDecisionError, match="kengetal-effect"):
        afd.apply(root, bad)
    assert pl.tracked_hashes(root) == rfd["pre_manifest"]
    assert cc.rollback(root, MATDEC).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(root) == matdec["pre_manifest"]
    norm = {o["observation_id"]: o for o in pr.load(os.path.join(root, pr.NORM_PO_PATH))["observations"]}
    assert all(norm[i]["material"]["material_status"] == "MATERIAL_UNKNOWN" for i in TARGETS)


# ------------------------------------------------------------------ beslispakket

@pytest.fixture(scope="module")
def package():
    return dp.build(PROJECT_ROOT)


def test_package_committed_and_deterministic(package):
    assert crv.dump(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_JSON), encoding="utf-8").read()
    assert dp.render_md(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_MD), encoding="utf-8").read()


def test_package_shows_decided_state(package):
    assert [e["kengetal_id"] for e in package["existing_kengetallen"]] == [KG]
    alu = package["groups"]["aluminium"]
    assert alu["material_steps"] == [] and alu["potential_source_clusters"]["ids"] == CLUSTERS
    pairs = {p["pair_id"]: p for p in alu["cross_cluster_pairs"]}
    assert sorted(pairs) == ["PAIR-00557", "PAIR-00558", "PAIR-00561"]
    assert alu["pairs_not_matching_description"] == [] and alu["open_cross_cluster_pairs"] == 0
    for fid, (pids, _) in FAMILIES.items():
        for pid in pids:
            p = pairs[pid]
            assert p["content_check"]["matches_description"] and p["review_family_id_after_material_decision"] == fid
            assert p["active_decision"]["decision"] == "COMPARABLE_WITH_CAVEATS"
    for s in package["observations"]:
        if s["observation_id"] in TARGETS:
            assert s["material_status"] == "KNOWN:aluminium"
            assert s["material"]["source"] == "human_material_decision"
    # zink blijft INSUFFICIENT_DATA (2 clusters), ook als alles positief zou worden
    zinc = package["groups"]["zinc"]
    assert zinc["potential_source_clusters"]["count"] == 2
    for res in zinc["combined_scenarios_after_material_decision"].values():
        assert all(r["status"] == "INSUFFICIENT_DATA" for r in res if r["material"] == "zinc")
