"""
Tests voor scripts/prepare_promotion_review.py: compact reviewpakket (SOURCE_EVIDENCE-approval-set,
accepts, decisions) en het canonieke promotieplan (niet uitgevoerd). Canonieke data alleen gelezen.
"""
import glob
import hashlib
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import prepare_promotion_review as ppr  # noqa: E402
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
def pkg():
    before = _hashes()
    out = ppr.build(PROJECT_ROOT)
    assert _hashes() == before
    return out


def test_approval_set_contains_only_explicit_evidence_with_full_provenance(pkg):
    a = pkg["approval"]
    review = json.load(open(os.path.join(PROJECT_ROOT, pv3.MATERIAL_REVIEW), encoding="utf-8"))
    explicit = {r["observation_id"] for r in review["records"] if r["classification"] == "EXPLICIT_SOURCE_EVIDENCE"}
    covered = [o for c in a["candidates"] for o in c["observation_ids"]]
    assert sorted(covered) == sorted(explicit) and len(covered) == len(set(covered))
    for c in a["candidates"]:
        assert c["classification"] == "EXPLICIT_SOURCE_EVIDENCE"
        assert c["source_fragment"] and c["page"] and c["material"]["normalized"] and c["material_rule"]
        assert c["document_id"] != "DOC-003"
    assert a["approval"]["status"] == "PENDING_HUMAN_DECISION"
    assert a["approval_statement"] == "approve all EXPLICIT_SOURCE_EVIDENCE candidates in this reviewed set"
    assert sum(a["summary"]["by_material"].values()) == sum(a["summary"]["by_document"].values()) == len(covered)


def test_approval_set_hash_is_content_bound(pkg):
    a = pkg["approval"]
    assert a["approval_set_sha256"] == pv3.pdb.canonical_content_sha256({"candidates": a["candidates"]})


def test_accepts_reduced_to_real_review(pkg):
    c = pkg["accepts"]
    assert c["counts"]["total"] == 89
    assert c["counts"]["batch_confirmation_candidates"] == len(c["batch_confirmation"]["records"])
    assert c["counts"]["human_review_cases"] == len(c["human_review"]) <= 28
    assert {h["classification"] for h in c["human_review"]} <= {"SOURCE_CHANGED_REVIEW", "AMBIGUOUS"}
    for h in c["human_review"]:
        assert h["decision"] is None and h["options"] and h["changed_fields"] and h["new_candidates"]
    assert {h["classification"] for h in c["history_only"]} <= {"NO_NEW_ACTION", "DUPLICATE_SKIP"}


def test_decisions_grouped_not_decided(pkg):
    d = pkg["decisions"]
    groups = d["material_only_groups"]
    assert sum(g["decisions"] for g in groups) == d["counts"]["material_only_decisions"]
    assert sum(f["decisions"] for f in d["material_only_families"]) == d["counts"]["material_only_decisions"]
    ids = [r["decision_id"] for g in groups for r in g["records"]] + \
          [r["decision_id"] for r in d["same_evidence_batch"]["records"]]
    assert len(ids) == len(set(ids)) == 30
    for g in groups:
        assert g["classification"] == "INPUT_CHANGED_MATERIAL_ONLY"
        assert all(r["observation_ids"] == sorted(r["observation_ids"]) for r in g["records"])


def test_plan_not_executed_and_complete(pkg):
    p = pkg["plan"]
    assert p["status"] == "NOT_EXECUTED"
    for k in ("A_to_history", "B_new_canonical", "C_ids", "D_new_review_records", "E_active_to_superseded",
              "F_rollback", "G_hashes_manifests"):
        assert p[k]
    assert len(p["E_active_to_superseded"]["records"]) == 30
    assert "niets verwijderen zonder history" in p["A_to_history"]["rule"]


def test_kengetallen_reported_from_v3_without_forcing(pkg):
    kg = json.load(open(os.path.join(PROJECT_ROOT, ppr.V3, "source_evidence", "kengetallen_batch1.json"), encoding="utf-8"))
    assert [k["status"] for k in pkg["plan"]["kengetallen_source_evidence"]] == \
        [k["status"] for k in sorted(kg["kengetallen"], key=lambda x: x["candidate_key"])]


def test_committed_package_current_and_canonical_unchanged():
    before = _hashes()
    assert ppr.main(["--check"]) == 0
    assert _hashes() == before
