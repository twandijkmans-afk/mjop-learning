"""
Tests voor het atomaire familiebesluit RFD-00001: drie 5211-pvc-reviewfamilies als COMPARABLE_WITH_CAVEATS
(reviewer twandijkmans), toegepast als één canonieke ketenschakel.

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
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402

CHANGE = "RFD-00001"
STATE = os.path.join(PROJECT_ROOT, pl.STATE_DIR, f"{CHANGE}.json")
OLD_KG, NEW_KG = "KG-5211-replace-m1-pvc-67920b77", "KG-5211-replace-m1-pvc-5cb98033"
FAMILIES = {"RF-5211-6d02e2e719": (["PAIR-00632", "PAIR-00634", "PAIR-00635", "PAIR-00637"], ["PRICE_LEVEL_DIFFERENCE"]),
            "RF-5211-0ad5841f33": (["PAIR-00583", "PAIR-00585"], ["PRICE_LEVEL_ABSENT"]),
            "RF-5211-76b81abb4c": (["PAIR-00641"], ["PRICE_LEVEL_DIFFERENCE"])}
NEW_IDS = [f"HDR-{n:05d}" for n in range(36, 43)]

pytestmark = pytest.mark.skipif(not os.path.isfile(STATE), reason="familiebesluit 5211 pvc niet vastgelegd")


def load(*rel):
    with open(os.path.join(PROJECT_ROOT, *rel), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = pl.tracked_hashes(PROJECT_ROOT)
    yield
    assert pl.tracked_hashes(PROJECT_ROOT) == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def state():
    return load(pl.STATE_DIR, f"{CHANGE}.json")


def pre(state, rel):
    with open(os.path.join(PROJECT_ROOT, state["history"], "pre", rel), encoding="utf-8") as f:
        return json.load(f)


def kg_history_file(state):
    """De kengetallen-historyversie die DEZE schakel aanmaakte (latere schakels maken er eigen versies bij)."""
    (rel,) = [k for k in state["post_manifest"] if k.startswith("data/kengetallen/history/")
              and k not in state["pre_manifest"]]
    return rel


def test_one_atomic_audited_transaction(state):
    assert state["status"] == "APPLIED" and state["change_kind"] == "family_decision"
    d = state["decision"]["family_decision"]
    assert d["reviewer"] == "twandijkmans" and d["decision"] == "COMPARABLE_WITH_CAVEATS"
    assert {f["review_family_id"]: (f["pair_ids"], f["decision_caveats"]) for f in d["families"]} == FAMILIES
    assert sorted(d["acknowledged_kengetal_effects"]) == [NEW_KG, OLD_KG]
    assert state["summary"]["applied_decision_ids"] == NEW_IDS
    saved = load("data", "review_decisions", "family_decisions", f"{CHANGE}.json")
    assert saved["applied_decision_ids"] == NEW_IDS and saved["families"] == d["families"]
    assert pl.chain_errors(PROJECT_ROOT) == [] and pr.verify(PROJECT_ROOT) == []


def test_seven_new_active_decisions_only(state):
    store = load("data", "review_decisions", "human_decision_records.json")["records"]
    old = pre(state, pr.DECISIONS_PATH)["records"]
    assert store[:len(old)] == old                                             # niets anders gewijzigd
    new = store[len(old):len(old) + len(NEW_IDS)]                              # latere besluiten volgen erna
    assert [r["decision_id"] for r in new] == NEW_IDS
    by_pair = {r["pair_id"]: r for r in new}
    for fid, (pairs, caveats) in FAMILIES.items():
        for pid in pairs:
            r = by_pair[pid]
            assert r["status"] == "ACTIVE" and r["decision"] == "COMPARABLE_WITH_CAVEATS"
            assert r["reviewer"] == {"reviewer_id": "twandijkmans", "reviewer_type": "human"}
            assert r["decision_caveats"] == caveats and r["supersedes"] is None
            assert r["family_decision"]["family_decision_id"] == CHANGE
            assert r["family_decision"]["review_family_id"] == fid
            system = set(r["system_reasons"]["pair_caveats"]) | set(r["system_reasons"]["observation_caveats"]["a"]) \
                | set(r["system_reasons"]["observation_caveats"]["b"])
            assert set(caveats) <= system                                     # geen nieuwe caveat-types
            assert r["system_reasons"]["hard_violations"] == []


def test_kg5211_new_version_and_old_in_history(state):
    kg = load("data", "kengetallen", "kengetallen_batch1.json")
    assert [k["kengetal_id"] for k in kg["kengetallen"] if k["kengetal_id"].startswith("KG-5211-")] == [NEW_KG]
    k = next(k for k in kg["kengetallen"] if k["kengetal_id"] == NEW_KG)
    assert (k["status"], k["value_display"], k["min_display"], k["max_display"], k["source_cluster_count"]) == \
        ("AVAILABLE", "54.39", "45.23", "61.09", 5)
    assert k["source_cluster_ids"] == ["SC-DOC-001", "SC-DOC-008+DOC-009", "SC-DOC-010", "SC-DOC-012", "SC-DOC-013"]
    assert k["human_review_complete"] and k["missing_cross_cluster_reviews"] == []
    assert set(NEW_IDS) | {"HDR-00031", "HDR-00032", "HDR-00033"} == set(k["decision_ids"])
    hist = kg_history_file(state)
    with open(os.path.join(PROJECT_ROOT, hist), encoding="utf-8") as f:
        old = json.load(f)
    assert pl.sha256_file(os.path.join(PROJECT_ROOT, hist)) == state["post_manifest"][hist]
    assert [(x["kengetal_id"], x["value_display"], x["source_cluster_count"]) for x in old["kengetallen"]] == \
        [(OLD_KG, "51.79", 3)]


def test_nothing_else_changed(state):
    changed = sorted(k for k in set(state["pre_manifest"]) | set(state["post_manifest"])
                     if state["pre_manifest"].get(k) != state["post_manifest"].get(k))
    assert changed == sorted(["data/review_decisions/human_decision_records.json",
                              f"data/review_decisions/family_decisions/{CHANGE}.json",
                              "data/kengetallen/kengetallen_batch1.json",
                              kg_history_file(state)])
    assert len(load("data", "price_observations", "price_observations_batch1.json")["observations"]) == 545
    pkg = crv.build(PROJECT_ROOT)
    other = [f for f in pkg["families"] if f["review_family_id"] not in FAMILIES
             and any(p["existing_decisions"] and p["existing_decisions"][-1]["decision_id"] in NEW_IDS
                     for p in f["pairs"])]
    assert other == []                                                        # geen andere reviewfamilies geraakt


def make_copy(dst):
    for rel in pr.SIMULATION_COPY + ("reports/review",):
        s, d = os.path.join(PROJECT_ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return dst


def test_rollback_restores_old_kg_and_transaction_is_atomic(tmp_path, state):
    root = make_copy(str(tmp_path / "p"))
    while pl.latest(root)["promotion_id"] != CHANGE:                         # latere schakels eerst terug
        cc.rollback(root, pl.latest(root)["promotion_id"])
    assert cc.rollback(root, CHANGE).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(root) == state["pre_manifest"]
    kg = pr.load(os.path.join(root, pr.KG_PATH))
    assert [(k["kengetal_id"], k["value_display"]) for k in kg["kengetallen"]] == [(OLD_KG, "51.79")]
    crv.write(root)
    pkg = json.load(open(os.path.join(root, crv.OUT_JSON), encoding="utf-8"))
    d = copy.deepcopy(state["decision"]["family_decision"])
    d.pop("family_decision_id")
    d["review_package_sha256"] = pl.sha256_file(os.path.join(root, crv.OUT_JSON))
    fam = {f["review_family_id"]: f for f in pkg["families"]}
    for e in d["families"]:
        assert e["family_input_sha256"] == fam[e["review_family_id"]]["family_input_sha256"]
    # één familie met een fout -> NIETS wordt toegepast (atomair)
    bad = copy.deepcopy(d)
    bad["families"][2]["family_input_sha256"] = "0" * 64
    with pytest.raises(afd.FamilyDecisionError, match="family_input_sha256"):
        afd.apply(root, bad)
    bad = copy.deepcopy(d)
    bad["families"][0]["decision_caveats"] = ["PRICE_LEVEL_DIFFERENCE", "QUANTITY_SCALE_DIFFERENCE"]
    with pytest.raises(afd.FamilyDecisionError, match="geen nieuwe caveats"):
        afd.apply(root, bad)
    bad = copy.deepcopy(d)
    bad["acknowledged_kengetal_effects"] = [OLD_KG]
    with pytest.raises(afd.FamilyDecisionError, match="kengetal-effect"):
        afd.apply(root, bad)
    assert pl.tracked_hashes(root) == state["pre_manifest"]
    # opnieuw toepassen geeft exact dezelfde beslissingen en hetzelfde kengetal
    st = afd.apply(root, d, now=state["applied_at"])
    assert st["summary"]["applied_decision_ids"] == NEW_IDS
    rel = "data/review_decisions/human_decision_records.json"
    new = [r for r in pr.load(os.path.join(root, rel))["records"] if r["decision_id"] in NEW_IDS]
    real = [r for r in load(*rel.split("/"))["records"] if r["decision_id"] in NEW_IDS]
    strip = lambda r: {k: v for k, v in r.items() if k != "family_decision"}  # noqa: E731
    assert [strip(r) for r in new] == [strip(r) for r in real]
    kg = pr.load(os.path.join(root, pr.KG_PATH))
    assert [(k["kengetal_id"], k["value_display"], k["source_cluster_count"]) for k in kg["kengetallen"]] == \
        [(NEW_KG, "54.39", 5)]
