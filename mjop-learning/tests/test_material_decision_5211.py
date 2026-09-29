"""
Tests voor milestone approve-5211-pvc-material-v1:

  - menselijk materiaalbesluit pvc voor EXACT PO-DOC-012-P015-L033 en PO-DOC-013-P019-L025 (MATDEC-00001);
  - geen scope leak, gebonden aan de bron, rollback;
  - beslispakket 5211 pvc (scripts/decision_package_5211_pvc.py): niets toegepast, simulaties met de
    bestaande kengetalregels.

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

import canonical_change as cc  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import decision_package_5211_pvc as dp  # noqa: E402
import normalize_price_observations as npo  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import record_material_decision as rmd  # noqa: E402

CHANGE = "MATDEC-00001"
STATE = os.path.join(PROJECT_ROOT, pl.STATE_DIR, f"{CHANGE}.json")
TARGETS = ["PO-DOC-012-P015-L033", "PO-DOC-013-P019-L025"]
KG5211 = "KG-5211-replace-m1-pvc-67920b77"
EVIDENCE = {"element_description_original": "Hemelwaterafvoer pvc",
            "action_text_original": "Vervangen hemelwaterafvoer pvc", "unit_original": "m1"}

pytestmark = pytest.mark.skipif(not os.path.isfile(STATE), reason="materiaalbesluit 5211 niet vastgelegd")


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
def state():
    return load(pl.STATE_DIR, f"{CHANGE}.json")


def pre(state, rel):
    with open(os.path.join(PROJECT_ROOT, state["history"], "pre", rel), encoding="utf-8") as f:
        return json.load(f)


def make_copy(dst):
    for rel in pr.SIMULATION_COPY + ("reports/review",):
        s, d = os.path.join(PROJECT_ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return dst


def decision(obs_ids=TARGETS, **over):
    d = {"reviewer": "twandijkmans", "reviewed_at": "2026-09-29T11:15:00Z", "decision_reason": "test",
         "approvals": [{"observation_id": i, "material": "pvc", "evidence": dict(EVIDENCE)} for i in obs_ids]}
    d.update(over)
    return d


# ------------------------------------------------------------------ het vastgelegde besluit

def test_exactly_two_material_approvals(state):
    store = load("data", "review_decisions", "material_decision_records.json")
    store["records"] = store["records"][:2]                                   # latere besluiten volgen erna
    assert [r["observation_id"] for r in store["records"]] == TARGETS
    assert [r["decision_id"] for r in store["records"]] == ["MDR-00001", "MDR-00002"]
    source = {o["observation_id"]: o for o in load("data", "price_observations",
                                                     "price_observations_batch1.json")["observations"]}
    reg = {d["document_id"]: d["sha256"] for d in load("reports", "document_registry.json")["documents"]}
    for r in store["records"]:
        assert r["scope"] == "EXACT_OBSERVATION" and r["status"] == "ACTIVE"
        assert r["reviewer"] == {"reviewer_id": "twandijkmans", "reviewer_type": "human"}
        assert r["material"] == {"original_value": "pvc", "normalized_value": "pvc"}
        assert {k: r["evidence"][k] for k in EVIDENCE} == EVIDENCE
        assert r["source_observation_sha256"] == npo.observation_fingerprint(source[r["observation_id"]])
        assert r["source_document_sha256"] == reg[r["document_id"]]
    assert state["status"] == "APPLIED" and state["change_kind"] == "material_decision"
    assert pl.chain_errors(PROJECT_ROOT) == [] and pr.verify(PROJECT_ROOT) == []


def test_material_is_pvc_with_human_source_and_caveat_gone():
    norm = {o["observation_id"]: o for o in load("data", "price_observations",
                                                   "price_observations_batch1_normalized.json")["observations"]}
    comp = {a["observation_id"]: a for a in load("data", "comparability", "comparability_batch1.json")["observations"]}
    for oid, mdr in zip(TARGETS, ("MDR-00001", "MDR-00002")):
        m = norm[oid]["material"]
        assert (m["material_original"], m["material_normalized"], m["material_source"], m["material_status"],
                m["material_decision_id"]) == ("pvc", "pvc", "human_material_decision",
                                               "MATERIAL_FROM_HUMAN_DECISION", mdr)
        assert comp[oid]["material"] == {"original": "pvc", "normalized": "pvc", "source": "human_material_decision"}
        assert "MATERIAL_UNKNOWN" not in comp[oid]["caveats"]


def test_no_scope_leak_to_other_observations(state):
    old = {o["observation_id"]: o for o in pre(state, pr.NORM_PO_PATH)["observations"]}
    new = {o["observation_id"]: o for o in load("data", "price_observations",
                                                  "price_observations_batch1_normalized.json")["observations"]}
    assert set(old) == set(new) and len(new) == 545
    # latere, eigen materiaalbesluiten (andere observations, eigen ketenschakel) tellen hier niet mee
    later = {r["observation_id"] for r in load("data", "review_decisions", "material_decision_records.json")["records"]
             if r["decision_id"] not in ("MDR-00001", "MDR-00002")}
    assert not later & set(TARGETS)
    changed = sorted(i for i in new if new[i] != old[i] and i not in later)
    assert changed == TARGETS
    for oid in TARGETS:
        assert {k: v for k, v in new[oid].items() if k != "material"} == \
            {k: v for k, v in old[oid].items() if k != "material"}               # bedragen/overige velden gelijk
    assert sum(o["material"]["material_status"] == "MATERIAL_FROM_HUMAN_DECISION" for o in new.values()) == 2 + len(later)
    # andere observations van dezelfde documenten blijven zonder materiaal (bijv. staal gegalvaniseerd)
    assert new["PO-DOC-012-P015-L039"]["material"]["material_status"] == "MATERIAL_UNKNOWN"
    old_c = {a["observation_id"]: a for a in pre(state, pr.COMP_PATH)["observations"]}
    new_c = {a["observation_id"]: a for a in load("data", "comparability", "comparability_batch1.json")["observations"]}
    moved = [i for i in new_c if i not in TARGETS and i not in later and pr._assess_without_derived(new_c[i]) !=
             pr._assess_without_derived(old_c[i])]
    assert moved == []


def test_amounts_clusters_relations_and_decisions_unchanged(state):
    for rel in ("data/price_observations/price_observations_batch1.json",
                "data/price_observations/document_relations.json",
                "data/review_decisions/human_decision_records.json"):
        assert state["pre_manifest"][rel] == state["post_manifest"][rel], rel         # het besluit zelf
    for rel in ("data/price_observations/price_observations_batch1.json",
                "data/price_observations/document_relations.json"):
        assert pl.sha256_file(os.path.join(PROJECT_ROOT, rel)) == state["post_manifest"][rel], rel
    comp = load("data", "comparability", "comparability_batch1.json")
    assert len(comp["source_clusters"]) == 11
    assert comp["source_clusters"] == pre(state, pr.COMP_PATH)["source_clusters"]
    assert len(load("data", "price_observations", "price_observations_batch1.json")["observations"]) == 545


def test_material_decision_kept_kg5211_and_made_no_family_decision(state):
    # het materiaalbesluit zelf: KG-5211 inhoudelijk ongewijzigd (51.79, 3 clusters), geen pair decisions
    kg = state["summary"]["kengetallen"]
    assert kg["content_changed"] is False and kg["before"] == kg["after"] == [
        {"kengetal_id": KG5211, "status": "AVAILABLE", "value": "51.79", "clusters": 3}]
    rel = "data/review_decisions/human_decision_records.json"
    assert state["pre_manifest"][rel] == state["post_manifest"][rel]
    # familiebesluiten komen pas later, als aparte menselijke ketenschakel
    assert not [s for s in pl.states(PROJECT_ROOT) if s.get("change_kind") == "family_decision"
                and s["sequence"] < state["sequence"]]


# ------------------------------------------------------------------ binding, weigeringen, rollback

def test_changed_source_invalidates_approval():
    source = {o["observation_id"]: o for o in load("data", "price_observations",
                                                     "price_observations_batch1.json")["observations"]}
    decisions = npo.load_material_decisions(PROJECT_ROOT)
    verified = {e["element_id"]: e for n in os.listdir(os.path.join(PROJECT_ROOT, "data", "verified"))
                for e in load("data", "verified", n)["elements"]}
    vocab = npo.load_vocab_utf8(os.path.join(PROJECT_ROOT, "vocabularies"), "material")
    obs = source[TARGETS[0]]
    assert npo.normalize_material(obs, verified, vocab, decisions)["material_status"] == "MATERIAL_FROM_HUMAN_DECISION"
    changed = copy.deepcopy(obs)
    changed["quantity_value"] = "81.00"
    m = npo.normalize_material(changed, verified, vocab, decisions)
    assert m["material_status"] == "MATERIAL_UNKNOWN" and m["material_not_derived_reason"] == \
        "material_decision_input_changed" and m["material_original"] is None
    other = source["PO-DOC-012-P015-L039"]                                  # geen besluit: geen materiaal
    assert npo.normalize_material(other, verified, vocab, decisions)["material_status"] == "MATERIAL_UNKNOWN"


def test_tool_refuses_scope_expansion_and_mismatches():
    with pytest.raises(rmd.MaterialDecisionError, match="al een ACTIVE|al een materiaal"):
        rmd.validate(PROJECT_ROOT, decision())
    bad = decision(["PO-DOC-012-P015-L039"])                                 # staal gegalvaniseerd
    with pytest.raises(rmd.MaterialDecisionError, match="niet letterlijk gelijk"):
        rmd.validate(PROJECT_ROOT, bad)
    src = {o["observation_id"]: o for o in load("data", "price_observations",
                                                  "price_observations_batch1_normalized.json")["observations"]}
    o = src["PO-DOC-012-P015-L039"]
    ev = {"element_description_original": o["element"]["element_description_original"],
          "action_text_original": o["action"]["action_text_original"], "unit_original": o["unit"]["unit_original"]}
    bad = decision(["PO-DOC-012-P015-L039"])
    bad["approvals"][0]["evidence"] = ev
    with pytest.raises(rmd.MaterialDecisionError, match="los woord"):
        rmd.validate(PROJECT_ROOT, bad)                                      # pvc staat niet in de brontekst
    with pytest.raises(rmd.MaterialDecisionError, match="reviewer"):
        rmd.validate(PROJECT_ROOT, decision(reviewer=""))


def test_rollback_and_reapply_on_copy(tmp_path, state):
    root = make_copy(str(tmp_path / "p"))
    while pl.latest(root)["promotion_id"] != CHANGE:                         # latere schakels eerst terug
        cc.rollback(root, pl.latest(root)["promotion_id"])
    assert cc.rollback(root, CHANGE).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(root) == state["pre_manifest"] and pl.chain_errors(root) == []
    assert os.path.isfile(os.path.join(root, state["history"], "rolled_back_state.json"))
    norm = {o["observation_id"]: o for o in pr.load(os.path.join(root, pr.NORM_PO_PATH))["observations"]}
    assert all(norm[i]["material"]["material_status"] == "MATERIAL_UNKNOWN" for i in TARGETS)
    # hetzelfde menselijke besluit opnieuw: exact dezelfde canonieke uitkomst (behalve kengetal-metadata)
    st = rmd.record(root, state["decision"]["material_decision"], now=state["applied_at"])
    assert st["promotion_id"].startswith("MATDEC-")                          # nieuw volgnummer; ids in history blijven
    for rel in (npo.MATERIAL_DECISIONS_PATH.replace(os.sep, "/"),
                "data/price_observations/price_observations_batch1_normalized.json",
                "data/comparability/comparability_batch1.json"):
        assert pl.sha256_file(os.path.join(root, rel)) == state["post_manifest"][rel], rel


# ------------------------------------------------------------------ beslispakket 5211 pvc

@pytest.fixture(scope="module")
def package():
    return dp.build(PROJECT_ROOT)


def test_package_committed_and_deterministic(package):
    assert crv.dump(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_JSON), encoding="utf-8").read()
    assert dp.render_md(package) == open(os.path.join(PROJECT_ROOT, dp.OUT_MD), encoding="utf-8").read()


SEVEN = ["PAIR-00583", "PAIR-00585", "PAIR-00632", "PAIR-00634", "PAIR-00635", "PAIR-00637", "PAIR-00641"]


def test_seven_pvc_pairs_match_the_description(package):
    pairs = {p["pair_id"]: p for p in package["cross_cluster_pairs"]}
    assert set(SEVEN) <= set(pairs) and len(pairs) == 10                  # 5 clusters -> 10 cross-cluster paren
    assert package["pairs_not_matching_description"] == []
    assert package["potential_source_clusters"]["count"] == 5
    for p in (pairs[i] for i in SEVEN):
        assert p["content_check"]["matches_description"], p["pair_id"]
        # open, of beslist door het menselijke familiebesluit (RFD-*)
        assert p["open"] or p["active_decision"]["decision"] == "COMPARABLE_WITH_CAVEATS"
        assert p["hard_violations"] == [] and p["system_class"] == "COMPARABLE_WITH_CAVEATS"
        assert set(p["pair_caveats"]) <= set(dp.ALLOWED_DIFFERENCES)


def test_simulations_follow_existing_rules(package):
    combos = package["combined_scenarios"]
    pos = combos["ALL_OPEN_FAMILIES_COMPARABLE_WITH_CAVEATS"]["result"]
    assert len(pos) == 1 and pos[0]["status"] == "AVAILABLE" and pos[0]["source_cluster_count"] == 5
    assert combos["ALL_OPEN_FAMILIES_COMPARABLE"]["result"] == pos
    assert combos["ALL_OPEN_FAMILIES_NOT_COMPARABLE"]["effect_on_existing_kengetal"] == "UNCHANGED"
    for f in package["open_families"]:
        assert f["simulations"]["NOT_COMPARABLE"]["effect_on_existing_kengetal"] == "UNCHANGED"
        linked = set(f["document_ids"]) & {"DOC-001", "DOC-009", "DOC-010"}
        eff = f["simulations"]["COMPARABLE_WITH_CAVEATS"]["effect_on_existing_kengetal"]
        # één familie alleen: groep onvolledig (geen deelverzameling, geen transitiviteit)
        assert eff.startswith("REPLACED_BY") and "INSUFFICIENT_DATA" in eff if linked else eff == "UNCHANGED"
    # het pakket past niets toe
    assert package["inputs"]["human_decisions_sha256"] == pl.sha256_file(
        os.path.join(PROJECT_ROOT, "data", "review_decisions", "human_decision_records.json"))
