"""
Controles op de canonieke promotie van Testbatch 01 (IB-ad209360ab07-P1).

  - DOC-011/012/013/015 canoniek, met dezelfde DOC-ID's als in het incoming register;
  - DOC-014 NIET gepromoveerd (expliciet uitgesloten; later menselijk besluit: duplicate_source van DOC-006);
  - Batch 1 intact: de bestaande 404 price observations byte-gelijk aan de toestand vóór de promotie;
  - geen relatie of source cluster stil bevestigd (document_relations.json ongewijzigd);
  - kengetallen alleen volgens de officiële regels (inhoud gelijk, geen nieuwe human decisions);
  - het relatiereviewpakket voor DOC-014 is deterministisch en beslist niets.

Alleen lezen; vergelijkingen tegen de promotiehistorie (data/history/incoming_promotions/<id>/pre).
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import document_registry as dr  # noqa: E402
import incoming_registry as ir  # noqa: E402
import prepare_relation_review as rr  # noqa: E402
import promote_canonical_batch1 as pcb  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import promotion_ledger as pl  # noqa: E402

BATCH = "IB-ad209360ab07"
PROMOTION = "IB-ad209360ab07-P1"
PROMOTED = ["DOC-011", "DOC-012", "DOC-013", "DOC-015"]
STATE = os.path.join(PROJECT_ROOT, pl.STATE_DIR, f"{PROMOTION}.json")

pytestmark = pytest.mark.skipif(not os.path.isfile(STATE), reason="Testbatch 01 niet gepromoveerd")


def load(*rel):
    with open(os.path.join(PROJECT_ROOT, *rel), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def state():
    return load(pl.STATE_DIR, f"{PROMOTION}.json")


def pre(state, *rel):
    return os.path.join(PROJECT_ROOT, state["history"], "pre", *rel)


def test_promotion_state_and_chain(state):
    assert state["status"] == "PROMOTED" and state["batch_id"] == BATCH
    assert [d["document_id"] for d in state["summary"]["promoted_documents"]] == PROMOTED
    assert state["approval"]["reviewer"] == "twandijkmans"
    assert pl.chain_errors(PROJECT_ROOT) == [] and pr.verify(PROJECT_ROOT) == [] and pcb.verify(PROJECT_ROOT) == []


def test_approval_excludes_doc014_explicitly():
    a = load(pr.pib.BATCHES_DIR, BATCH, "approval.json")
    assert a["approved_document_ids"] == PROMOTED and a["excluded_document_ids"] == ["DOC-014"]
    assert a["exclusion_reason"] and a["review_acknowledgements"] == {}
    manifest = os.path.join(PROJECT_ROOT, pr.pib.BATCHES_DIR, BATCH, "manifest.json")
    assert a["manifest_sha256"] == pl.sha256_file(manifest)


def test_promoted_documents_canonical_with_same_doc_ids():
    reg = dr.by_id(dr.load_registry(os.path.join(PROJECT_ROOT, pr.REGISTRY)))
    incoming = {e["document_id"]: e for e in ir.load(os.path.join(PROJECT_ROOT, ir.REGISTRY_PATH))["documents"]}
    for did in PROMOTED:
        entry = reg[did]
        assert entry["sha256"] == incoming[did]["sha256"]                         # zelfde bytes, zelfde ID
        assert entry["relative_path"].startswith(f"incoming/{did}/")
        path = os.path.join(PROJECT_ROOT, "data", "raw", *entry["relative_path"].split("/"))
        assert pl.sha256_file(path) == entry["sha256"]
        for layer in ("extracted", "normalized", "verified"):
            assert os.path.isfile(os.path.join(PROJECT_ROOT, "data", layer, f"{did}.json"))


def test_doc014_not_promoted_and_still_review_required(state):
    reg = dr.by_id(dr.load_registry(os.path.join(PROJECT_ROOT, pr.REGISTRY)))
    assert "DOC-014" not in reg
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "data", "raw", "incoming", "DOC-014"))
    for layer in ("extracted", "normalized", "verified"):
        assert not os.path.exists(os.path.join(PROJECT_ROOT, "data", layer, "DOC-014.json"))
    po = load(pr.PO_PATH)["observations"]
    assert not [o for o in po if o["document_id"] == "DOC-014"]
    d = {x["document_id"]: x for x in state["decisions"]}["DOC-014"]
    assert d["decision"] == "REVIEW_REQUIRED"
    assert d["reasons"][0] == "EXCLUDED_BY_REVIEWER"
    assert "RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION" in d["reasons"]


def test_batch1_observations_unchanged(state):
    with open(pre(state, pr.PO_PATH), encoding="utf-8") as f:
        old = json.load(f)["observations"]
    new = load(pr.PO_PATH)["observations"]
    assert len(old) == 404 and new[:404] == old                                    # bedragen byte-gelijk
    assert {o["document_id"] for o in new[404:]} == set(PROMOTED)
    assert len(new) - len(old) == state["summary"]["price_observations"]["added"]
    assert len({o["observation_id"] for o in new}) == len(new)                      # geen duplicaten
    for did in ("DOC-001", "DOC-002", "DOC-004", "DOC-005", "DOC-006", "DOC-007", "DOC-008", "DOC-009", "DOC-010"):
        for layer in ("extracted", "normalized", "verified"):
            rel = f"data/{layer}/{did}.json"
            assert pl.sha256_file(os.path.join(PROJECT_ROOT, rel)) == state["pre_manifest"][rel], rel


def test_no_relation_or_source_cluster_confirmed(state):
    rel = "data/price_observations/document_relations.json"
    assert state["post_manifest"][rel] == state["pre_manifest"][rel]                 # promotie wijzigde niets
    # latere wijzigingen alleen via een vastgelegd menselijk relatiebesluit in de keten (RELDEC-*)
    later = [s for s in pl.states(PROJECT_ROOT) if s["sequence"] > state["sequence"]]
    if pl.sha256_file(os.path.join(PROJECT_ROOT, rel)) != state["pre_manifest"][rel]:
        assert any(s.get("change_kind") == "relation_decision" for s in later)
    comp = load(pr.COMP_PATH)
    clusters = [c["source_cluster"] for c in comp["source_clusters"]]
    assert {f"SC-{d}" for d in PROMOTED} <= set(clusters)                            # elk eigen cluster
    assert not [c for c in clusters if "+" in c and any(d in c for d in PROMOTED)]
    assert state["summary"]["comparability_impact"]["new_pairs_have_human_decisions"] == 0


def test_kengetallen_follow_official_rules_only(state):
    # de promotie zelf veranderde de kengetallen niet en maakte geen beslissingen
    kg_summary = state["summary"]["kengetallen"]
    assert kg_summary["content_changed"] is False and kg_summary["before"] == kg_summary["after"]
    assert kg_summary["before"][0]["kengetal_id"] == "KG-5211-replace-m1-pvc-67920b77"
    rel = pr.DECISIONS_PATH.replace(os.sep, "/")
    assert state["post_manifest"][rel] == state["pre_manifest"][rel]
    # latere wijzigingen alleen via een vastgelegd menselijk familiebesluit in de keten
    with open(pre(state, pr.KG_PATH), encoding="utf-8") as f:
        old = json.load(f)
    kg = load(pr.KG_PATH)
    if kg["kengetallen"] != old["kengetallen"]:
        later = [s for s in pl.states(PROJECT_ROOT) if s["sequence"] > state["sequence"]]
        assert any(s.get("change_kind") == "family_decision" for s in later)


def test_relation_review_package_decides_nothing():
    path = os.path.join(PROJECT_ROOT, "reports", "review", "relation_review_DOC-014.json")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    committed = json.loads(text)
    assert committed["status"] == "OPEN_REQUIRES_HUMAN_DECISION" and committed["decision"] is None
    assert {o["option"] for o in committed["decision_options"]} >= {
        "DUPLICATE_OTHER_BYTES", "SAME_MJOP_VERSION", "SAME_BUILDING_DIFFERENT_INSPECTION", "INDEPENDENT_SOURCE"}
    rebuilt = rr.build(PROJECT_ROOT, "DOC-014", BATCH, ["DOC-005", "DOC-006"])
    assert rebuilt == committed                                                      # deterministisch
    # het besluit staat in document_relations.json, gebonden aan precies dit (bekeken) pakket
    rels = load("data", "price_observations", "document_relations.json")["relations"]
    decided = [r for r in rels if r.get("secondary_document_id") == "DOC-014"]
    assert all(r["decision"]["review_package_sha256"] == pl.sha256_file(path) for r in decided)
