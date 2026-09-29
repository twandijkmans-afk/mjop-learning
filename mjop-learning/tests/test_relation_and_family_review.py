"""
Tests voor milestone relation-and-comparability-review-v1:

  - relatiebesluit DOC-014 duplicate_source DOC-006 (scripts/record_relation_decision.py, DREL-005);
  - comparability review v2: reviewfamilies (scripts/comparability_review_v2.py);
  - veilige toepassing van één menselijk familiebesluit (scripts/apply_family_decision.py).

Het echte repo wordt alleen gelezen (gecontroleerd met hashes); alle writes gebeuren in een tijdelijke kopie.
"""
import copy
import glob
import hashlib
import json
import os
import random
import shutil
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import apply_family_decision as afd  # noqa: E402
import build_comparability as bc  # noqa: E402
import canonical_change as cc  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import document_registry as dr  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import record_relation_decision as rrd  # noqa: E402

RELDEC = "RELDEC-DREL-005"
RELDEC_STATE = os.path.join(PROJECT_ROOT, pl.STATE_DIR, f"{RELDEC}.json")
KG5211 = "KG-5211-replace-m1-pvc-67920b77"
KG5211_NEW = "KG-5211-replace-m1-pvc-5cb98033"
# de familie DOC-009/DOC-010 x DOC-012/DOC-013 (5211 pvc); de id hangt af van het materiaal (familiesleutel)
PVC_FAMILY_PAIRS = ["PAIR-00632", "PAIR-00634", "PAIR-00635", "PAIR-00637"]


def pvc_family_id(pkg):
    return next(f["review_family_id"] for f in pkg["families"] if f["pair_ids"] == PVC_FAMILY_PAIRS)

pytestmark = pytest.mark.skipif(not os.path.isfile(RELDEC_STATE), reason="relatiebesluit DOC-014 niet vastgelegd")


def load(*rel):
    with open(os.path.join(PROJECT_ROOT, *rel), encoding="utf-8") as f:
        return json.load(f)


def _protected():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for rel in ("data/incoming_registry.json", crv.OUT_JSON, crv.OUT_MD):
        out[rel] = pl.sha256_file(os.path.join(PROJECT_ROOT, rel))
    return out


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = _protected()
    yield
    assert _protected() == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def reldec():
    return load(pl.STATE_DIR, f"{RELDEC}.json")


def relations():
    return load("data", "price_observations", "document_relations.json")["relations"]


def make_copy(dst):
    for rel in pr.SIMULATION_COPY + ("reports/review", "data/incoming_batches", "data/incoming"):
        s, d = os.path.join(PROJECT_ROOT, rel), os.path.join(dst, rel)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.isfile(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
    return dst


# ------------------------------------------------------------------ relatiebesluit DOC-014

def test_doc014_is_duplicate_source_of_doc006(reldec):
    rel = [r for r in relations() if r.get("secondary_document_id") == "DOC-014"]
    assert len(rel) == 1
    r = rel[0]
    assert (r["relation_id"], r["type"], r["primary_document_id"]) == ("DREL-005", "duplicate_source", "DOC-006")
    d = r["decision"]
    assert d["option"] == "DUPLICATE_OTHER_BYTES" and d["decided_by"] == {"reviewer_id": "twandijkmans",
                                                                          "reviewer_type": "human"}
    assert d["review_package_sha256"] == pl.sha256_file(os.path.join(PROJECT_ROOT, d["review_package"]))
    inc = {e["document_id"]: e["sha256"] for e in load("data", "incoming_registry.json")["documents"]}
    reg = {e["document_id"]: e["sha256"] for e in load("reports", "document_registry.json")["documents"]}
    assert d["secondary_sha256"] == inc["DOC-014"] and d["primary_sha256"] == reg["DOC-006"]
    # geen redundante relatie met DOC-005: die volgt uit DREL-005 + DREL-002
    assert not [x for x in relations() if {"DOC-005", "DOC-014"} <= set(x.get("document_ids", [])) |
                {x.get("primary_document_id"), x.get("secondary_document_id")}]
    assert d["implied_relations"] == [{"document_id": "DOC-005", "via": ["DREL-005", "DREL-002"],
                                       "note": d["implied_relations"][0]["note"]}]
    assert reldec["status"] == "APPLIED" and reldec["change_kind"] == "relation_decision"
    assert reldec["decision"]["relation"] == r


def test_existing_relations_intact(reldec):
    with open(os.path.join(PROJECT_ROOT, reldec["history"], "pre", "data", "price_observations",
                           "document_relations.json"), encoding="utf-8") as f:
        before = json.load(f)["relations"]
    assert relations()[:len(before)] == before and len(relations()) == len(before) + 1
    drel2 = {r["relation_id"]: r for r in relations()}["DREL-002"]
    assert drel2["type"] == "version_of_same_mjop" and drel2["document_ids"] == ["DOC-005", "DOC-006"]


def test_doc014_contributes_no_observations(reldec):
    po = load("data", "price_observations", "price_observations_batch1.json")["observations"]
    assert len(po) == 545 and not [o for o in po if o["document_id"] == "DOC-014"]
    for rel in ("data/price_observations/price_observations_batch1.json",
                "data/price_observations/price_observations_batch1_normalized.json",
                "data/review_decisions/human_decision_records.json"):
        assert reldec["pre_manifest"][rel] == reldec["post_manifest"][rel], rel     # byte-gelijk
    assert "DOC-014" not in dr.by_id(dr.load_registry(os.path.join(PROJECT_ROOT, pr.REGISTRY)))
    assert reldec["summary"]["price_observations"] == {"before": 545, "added": 0, "after": 545,
                                                       "of_secondary_document": 0}


def test_source_cluster_count_not_increased():
    comp = load("data", "comparability", "comparability_batch1.json")
    assert len(comp["source_clusters"]) == comp["summary"]["source_clusters"] == 11
    assert not [c for c in comp["source_clusters"] if "DOC-014" in c["document_ids"]]
    dup = {d["document_id"]: d for d in comp["duplicate_documents"]}
    assert dup["DOC-014"] == {"document_id": "DOC-014", "duplicate_of": "DOC-006", "source_cluster": "SC-DOC-005+DOC-006"}
    cluster_of, _ = bc.build_clusters(["DOC-005", "DOC-006"], relations())
    assert cluster_of["DOC-014"] == cluster_of["DOC-006"] == cluster_of["DOC-005"]


def test_relation_graph_valid():
    doc = load("data", "price_observations", "document_relations.json")
    rels = doc["relations"]
    assert len({r["relation_id"] for r in rels}) == len(rels)
    canonical = {d["document_id"] for d in load("reports", "document_registry.json")["documents"]}
    secondaries = [r["secondary_document_id"] for r in rels if r["type"] == "duplicate_source"]
    assert len(secondaries) == len(set(secondaries))
    for r in rels:
        assert r["type"] in doc["relation_types"]
        if r["type"] == "duplicate_source":
            assert r["primary_document_id"] in canonical and r["primary_document_id"] not in secondaries
            assert r["secondary_document_id"] != r["primary_document_id"]
        else:
            assert len(r["document_ids"]) == 2 and set(r["document_ids"]) <= canonical
            assert not set(r["document_ids"]) & set(secondaries)      # duplicaten zitten niet in clusterrelaties


def test_incoming_promotion_treats_doc014_as_confirmed_duplicate():
    batch = pr.load_batch(PROJECT_ROOT, "IB-ad209360ab07")
    d = {x["document_id"]: x for x in pr.decide(PROJECT_ROOT, batch, pr.load_approval(batch)) if x["input_path"]}
    assert d["DOC-014"]["decision"] == "SKIPPED_DUPLICATE"
    assert d["DOC-014"]["reasons"] == ["CONFIRMED_DUPLICATE_SOURCE:DREL-005", "duplicate_of:DOC-006"]


def test_relation_decision_refuses_contradicting_or_repeated_decisions():
    pkg = load("reports", "review", "relation_review_DOC-014.json")
    assert rrd.evidence_errors(pkg, "DOC-014", "DOC-006") == []
    assert rrd.evidence_errors(pkg, "DOC-014", "DOC-005")                              # andere inspectie
    with pytest.raises(rrd.DecisionError, match="secundair"):                         # al besloten
        rrd.build_relation(PROJECT_ROOT, os.path.join("reports", "review", "relation_review_DOC-014.json"),
                           "DOC-014", "DOC-005", "DUPLICATE_OTHER_BYTES", "x", "x", "2026-01-01T00:00:00Z")
    with pytest.raises(rrd.DecisionError, match="al"):
        rrd.build_relation(PROJECT_ROOT, os.path.join("reports", "review", "relation_review_DOC-014.json"),
                           "DOC-014", "DOC-006", "DUPLICATE_OTHER_BYTES", "x", "x", "2026-01-01T00:00:00Z")
    with pytest.raises(rrd.DecisionError, match="niet vastgelegd"):
        rrd.build_relation(PROJECT_ROOT, os.path.join("reports", "review", "relation_review_DOC-014.json"),
                           "DOC-014", "DOC-006", "INDEPENDENT_SOURCE", "x", "x", "2026-01-01T00:00:00Z")


def test_relation_decision_rollback_and_reapply_on_copy(tmp_path, reldec):
    root = make_copy(str(tmp_path / "p"))
    # alleen de laatste schakel kan terug; rol terug tot en met RELDEC
    while pl.latest(root)["promotion_id"] != RELDEC:
        cc.rollback(root, pl.latest(root)["promotion_id"])
    assert cc.rollback(root, RELDEC).startswith("ROLLBACK OK")
    assert pl.tracked_hashes(root) == reldec["pre_manifest"] and pl.chain_errors(root) == []
    assert os.path.isfile(os.path.join(root, reldec["history"], "rolled_back_state.json"))
    batch = pr.load_batch(root, "IB-ad209360ab07")
    d = {x["document_id"]: x for x in pr.decide(root, batch, pr.load_approval(batch)) if x["input_path"]}
    assert d["DOC-014"]["decision"] == "REVIEW_REQUIRED"
    r = reldec["decision"]["relation"]
    st = rrd.record(root, "DOC-014", "DOC-006", "DUPLICATE_OTHER_BYTES", "twandijkmans",
                    r["decision"]["decision_reason"], now=r["decision"]["decided_at"])
    assert st["promotion_id"] == "RELDEC-DREL-005-2"                   # history van de eerste blijft bewaard
    for rel in ("data/price_observations/document_relations.json", "data/comparability/comparability_batch1.json"):
        assert pl.sha256_file(os.path.join(root, rel)) == reldec["post_manifest"][rel], rel


# ------------------------------------------------------------------ comparability review v2

@pytest.fixture(scope="module")
def package():
    return crv.build(PROJECT_ROOT)


def test_committed_package_is_current_and_deterministic(package):
    assert crv.dump(package) == open(os.path.join(PROJECT_ROOT, crv.OUT_JSON), encoding="utf-8").read()
    assert crv.render_md(package) == open(os.path.join(PROJECT_ROOT, crv.OUT_MD), encoding="utf-8").read()
    assert crv.dump(crv.build(PROJECT_ROOT)) == crv.dump(package)


def test_family_grouping_is_order_independent():
    ctx = crv.Context(PROJECT_ROOT)
    import export_human_review_queue as hrq
    queue = hrq.select_pairs(ctx.comp)
    a = crv.build_families(ctx, queue)
    shuffled = list(queue)
    random.Random(7).shuffle(shuffled)
    b = crv.build_families(ctx, shuffled)
    assert [f["review_family_id"] for f in a] == [f["review_family_id"] for f in b]
    assert [f["family_input_sha256"] for f in a] == [f["family_input_sha256"] for f in b]


def test_every_queue_pair_in_exactly_one_family(package):
    ids = [pid for f in package["families"] for pid in f["pair_ids"]]
    v1 = [pid for f in package["families"] if f["review_track"] != crv.UNKNOWN_TRACK for pid in f["pair_ids"]]
    unknown = [pid for f in package["families"] if f["review_track"] == crv.UNKNOWN_TRACK for pid in f["pair_ids"]]
    assert len(ids) == len(set(ids)) == len(v1) + len(unknown)
    assert len(v1) == package["queue"]["pairs"] == 76                        # queue v1 onveranderd
    assert sorted(unknown) == sorted(package["unknown_pair_review"]["reviewable_pair_ids"])
    assert package["summary"]["review_families"] == len(package["families"]) < len(ids)


def test_family_members_share_the_same_review_question(package):
    for f in package["families"]:
        for p in f["pairs"]:
            assert "|".join(f["family_key"]["candidate_key"]) == f["candidate_group"]
            assert ("QUANTITY_SCALE_DIFFERENCE" in p["pair_caveats"]) == f["family_key"]["quantity_scale_difference"]
        assert f["evidence_category"] in crv.CATEGORY_ORDER and f["evidence_category"] in f["evidence_flags"]
        expected = set(crv.UNKNOWN_TRACK_CHOICES) if f["review_track"] == crv.UNKNOWN_TRACK else set(crv.CHOICES)
        assert {c["choice"] for c in f["allowed_human_choices"]} == expected


def test_package_creates_no_decisions_and_no_kengetal(package):
    store = load("data", "review_decisions", "human_decision_records.json")
    assert package["inputs"]["human_decisions_sha256"] == pl.sha256_file(
        os.path.join(PROJECT_ROOT, "data", "review_decisions", "human_decision_records.json"))
    active = {frozenset(r["observation_ids"]) for r in store["records"] if r["status"] == "ACTIVE"}
    for f in package["families"]:
        for p in f["pairs"]:
            assert (p["status"] == "ACTIVE_DECISION") == (frozenset(p["observation_ids"]) in active)
    text = json.dumps(package)
    assert "value_exact" not in text and "median" not in text.lower()


def test_kg5211_follows_human_decisions_only(package):
    kgs = [k for k in load("data", "kengetallen", "kengetallen_batch1.json")["kengetallen"]
           if k["kengetal_id"].startswith("KG-5211-replace-m1-pvc-")]
    assert len(kgs) == 1 and kgs[0]["status"] == "AVAILABLE" and kgs[0]["human_review_complete"]
    fam = next(f for f in package["families"] if f["review_family_id"] == pvc_family_id(package))
    choices = {c["choice"]: c["kengetal_effect"] for c in fam["allowed_human_choices"]}
    if fam["current_status"] == "DECIDED_ACTIVE":                   # na het familiebesluit RFD-00001
        assert (kgs[0]["kengetal_id"], kgs[0]["value_display"], kgs[0]["source_cluster_count"]) == \
            (KG5211_NEW, "54.39", 5)
        # een latere NOT_COMPARABLE zou het kengetal laten vervallen: expliciete bevestiging vereist
        assert choices["NOT_COMPARABLE"]["acknowledgement_required"] == [KG5211_NEW]
    else:
        assert (kgs[0]["kengetal_id"], kgs[0]["value_display"]) == (KG5211, "51.79")
        assert choices["COMPARABLE_WITH_CAVEATS"]["acknowledgement_required"] == [KG5211]
    g = next(g for g in package["candidate_groups"] if g["candidate_group"] == "5211|replace|m1")
    sem = g["pvc_review"]["new_observations_by_semantics"]
    # na het menselijke materiaalbesluit MATDEC-00001 hebben DOC-012/DOC-013 exact de pvc-semantiek
    assert {o["document_id"] for o in sem["PVC_EXACT_SEMANTICS"]} == {"DOC-012", "DOC-013"}
    assert "PVC_BY_ELEMENT_TEXT_PENDING_MATERIAL_APPROVAL" not in sem


# ------------------------------------------------------------------ familiebesluit toepassen

@pytest.fixture
def proj(tmp_path):
    return make_copy(str(tmp_path / "p"))


def decision_for(root, family_id, pair_ids=None, **over):
    pkg_path = os.path.join(root, crv.OUT_JSON)
    pkg = json.load(open(pkg_path, encoding="utf-8"))
    fam = next(f for f in pkg["families"] if f["review_family_id"] == family_id)
    chosen = [p for p in fam["pairs"] if p["pair_id"] in (pair_ids or fam["pair_ids"])]
    # alleen voorbehouden die het systeem voor elk gekozen paar al gaf (geen nieuwe caveats)
    caveats = sorted(set.intersection(*[set(p["pair_caveats"]) | set(p["observation_caveats"]["a"]) |
                                        set(p["observation_caveats"]["b"]) for p in chosen]))
    d = {"review_package_sha256": pl.sha256_file(pkg_path), "review_family_id": family_id,
         "family_input_sha256": fam["family_input_sha256"], "pair_ids": pair_ids or fam["pair_ids"],
         "decision": "COMPARABLE_WITH_CAVEATS", "decision_reason": "testbesluit",
         "decision_caveats": caveats, "reviewer": "tester", "reviewed_at": "2026-09-29T12:00:00Z",
         "notes": None, "acknowledged_kengetal_effects": []}
    d.update(over)
    return d, fam


def open_family_without_kg_effect(root):
    pkg = json.load(open(os.path.join(root, crv.OUT_JSON), encoding="utf-8"))
    return next(f for f in pkg["families"] if f["current_status"] == "OPEN_NO_DECISION" and len(f["pair_ids"]) >= 2
                and not next(c for c in f["allowed_human_choices"]
                             if c["choice"] == "COMPARABLE_WITH_CAVEATS")["kengetal_effect"]["acknowledgement_required"])


def test_family_decision_applies_only_exact_pair_ids(proj):
    fam = open_family_without_kg_effect(proj)
    chosen = fam["pair_ids"][:1]
    d, _ = decision_for(proj, fam["review_family_id"], chosen)
    store_before = json.load(open(os.path.join(proj, pr.DECISIONS_PATH), encoding="utf-8"))
    st = afd.apply(proj, d, now="2026-09-29T12:00:00Z")
    store = json.load(open(os.path.join(proj, pr.DECISIONS_PATH), encoding="utf-8"))
    new = store["records"][len(store_before["records"]):]
    assert [r["pair_id"] for r in new] == chosen and all(r["status"] == "ACTIVE" for r in new)
    assert new[0]["family_decision"]["review_family_id"] == fam["review_family_id"]
    assert new[0]["reviewer"] == {"reviewer_id": "tester", "reviewer_type": "human"}
    others = set(fam["pair_ids"]) - set(chosen)
    assert not [r for r in new if r["pair_id"] in others]
    saved = json.load(open(os.path.join(proj, afd.FAMILY_DIR, f"{st['promotion_id']}.json"), encoding="utf-8"))
    assert saved["pair_ids"] == chosen and saved["applied_decision_ids"] == [r["decision_id"] for r in new]
    assert pl.chain_errors(proj) == [] and pr.verify(proj) == []
    # rollback: exact terug, history bewaard
    assert cc.rollback(proj, st["promotion_id"]).startswith("ROLLBACK OK")
    assert json.load(open(os.path.join(proj, pr.DECISIONS_PATH), encoding="utf-8")) == store_before
    assert pl.tracked_hashes(proj) == st["pre_manifest"]


def test_family_decision_refuses_pairs_outside_family_and_bad_decisions(proj):
    fam = open_family_without_kg_effect(proj)
    other = next(f for f in json.load(open(os.path.join(proj, crv.OUT_JSON)))["families"]
                 if f["review_family_id"] != fam["review_family_id"])
    d, _ = decision_for(proj, fam["review_family_id"], fam["pair_ids"] + [other["pair_ids"][0]])
    with pytest.raises(afd.FamilyDecisionError, match="buiten de familie"):
        afd.apply(proj, d)
    for over, msg in (({"decision": "ACCEPT"}, "ongeldige"), ({"decision_reason": " "}, "verplicht"),
                      ({"pair_ids": []}, "niet-lege"), ({"family_input_sha256": "0" * 64}, "family_input_sha256"),
                      ({"review_package_sha256": "0" * 64}, "reviewpakket")):
        d, _ = decision_for(proj, fam["review_family_id"])
        d.update(over)
        with pytest.raises(afd.FamilyDecisionError, match=msg):
            afd.apply(proj, d)
    assert pl.states(proj) == pl.states(PROJECT_ROOT)                    # niets toegepast


def test_input_change_invalidates_family_decision(proj):
    fam = open_family_without_kg_effect(proj)
    d, _ = decision_for(proj, fam["review_family_id"])
    # andere invoer voor een paar van deze familie: bestaande beslissing erbij (REVIEW_REQUIRED-record)
    path = os.path.join(proj, pr.DECISIONS_PATH)
    store = json.load(open(path, encoding="utf-8"))
    template = copy.deepcopy(store["records"][0])
    p = fam["pairs"][0]
    template.update(decision_id=f"HDR-{len(store['records']) + 1:05d}", pair_id=p["pair_id"],
                    observation_ids=p["observation_ids"], status="REVIEW_REQUIRED", supersedes=None)
    store["records"].append(template)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with pytest.raises(afd.FamilyDecisionError, match="family_input_sha256"):
        afd.validate(proj, d)
    # andere comparability-invoer: hele pakket vervalt
    comp_path = os.path.join(proj, crv.COMP)
    with open(comp_path, "a", encoding="utf-8") as f:
        f.write("\n")
    with pytest.raises(afd.FamilyDecisionError, match="invoer gewijzigd"):
        afd.validate(proj, d)


def rollback_family_decisions(root):
    """Alle familiebesluiten en de schakels daarna terugdraaien (laatste eerst) en het reviewpakket op die toestand
    herbouwen."""
    while any(s.get("change_kind") == "family_decision" for s in pl.states(root)):
        cc.rollback(root, pl.latest(root)["promotion_id"])
    crv.write(root)


def test_kg5211_only_changes_after_explicit_acknowledged_decision(proj):
    rollback_family_decisions(proj)
    d, fam = decision_for(proj, pvc_family_id(json.load(open(os.path.join(proj, crv.OUT_JSON), encoding="utf-8"))))
    with pytest.raises(afd.FamilyDecisionError, match="kengetal-effect"):
        afd.apply(proj, d)
    kg = json.load(open(os.path.join(proj, pr.KG_PATH), encoding="utf-8"))
    assert {k["kengetal_id"]: k["status"] for k in kg["kengetallen"]}[KG5211] == "AVAILABLE"
    d["acknowledged_kengetal_effects"] = [KG5211]
    st = afd.apply(proj, d, now="2026-09-29T12:00:00Z")
    kg = json.load(open(os.path.join(proj, pr.KG_PATH), encoding="utf-8"))
    assert KG5211 not in {k["kengetal_id"] for k in kg["kengetallen"] if k["status"] == "AVAILABLE"}
    assert kg["supersedes"] and os.path.isfile(os.path.join(proj, kg["supersedes"]["file"]))  # oude versie bewaard
    assert st["summary"]["kengetallen"]["content_changed"] is True
    assert cc.rollback(proj, st["promotion_id"]).startswith("ROLLBACK OK")
    kg = json.load(open(os.path.join(proj, pr.KG_PATH), encoding="utf-8"))
    assert {k["kengetal_id"]: k["value_display"] for k in kg["kengetallen"]}[KG5211] == "51.79"


def test_no_ai_in_new_modules():
    for name in ("canonical_change.py", "record_relation_decision.py", "comparability_review_v2.py",
                 "apply_family_decision.py"):
        text = open(os.path.join(PROJECT_ROOT, "scripts", name), encoding="utf-8").read()
        for bad in ("import anthropic", "import openai", "import extract_batch", "from extract_batch"):
            assert bad not in text, (name, bad)
