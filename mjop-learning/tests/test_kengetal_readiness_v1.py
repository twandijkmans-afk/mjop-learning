"""
Tests voor de read-only kengetal-readiness analyse (scripts/kengetal_readiness_v1.py):

  - alleen lezen: het echte repo (canonieke data, besluiten, materialen, kengetallen) blijft byte-gelijk;
  - het vastgelegde rapport is actueel en deterministisch;
  - classificatie en sortering volgen de gedocumenteerde regels; AVAILABLE komt uit het echte kengetallenbestand;
  - geen scoring of confidence.
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import comparability_review_v2 as crv  # noqa: E402
import kengetal_readiness_v1 as kr  # noqa: E402
import promotion_ledger as pl  # noqa: E402


def _protected():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for rel in (kr.OUT_JSON, kr.OUT_MD, crv.OUT_JSON, crv.OUT_MD):
        out[rel] = pl.sha256_file(os.path.join(PROJECT_ROOT, rel))
    return out


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = _protected()
    yield
    assert _protected() == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def report():
    return kr.build(PROJECT_ROOT)


def test_report_committed_and_deterministic(report):
    assert crv.dump(report) == open(os.path.join(PROJECT_ROOT, kr.OUT_JSON), encoding="utf-8").read()
    assert kr.render_md(report) == open(os.path.join(PROJECT_ROOT, kr.OUT_MD), encoding="utf-8").read()


def test_groups_cover_all_independent_observations_once(report):
    comp = json.load(open(os.path.join(PROJECT_ROOT, crv.COMP), encoding="utf-8"))
    indep = sorted(a["observation_id"] for a in comp["observations"] if a["independent_input"])
    seen = sorted(i for g in report["groups"] for i in g["observation_ids"])
    assert seen == indep
    assert report["summary"]["candidate_groups"] == len(report["groups"])
    assert sum(report["summary"]["by_readiness"].values()) == len(report["groups"])
    assert set(report["summary"]["by_readiness"]) == set(kr.STATUSES)
    for g in report["groups"]:
        assert g["candidate_key"] == "|".join((g["element_code"], g["action"], g["unit"]))
        assert all(comp_key == g["candidate_key"] for comp_key in
                   {crv.key_str(a["candidate_key"]) for a in comp["observations"] if a["observation_id"] in
                    set(g["observation_ids"])})


def test_available_matches_kengetallen_file(report):
    kg = json.load(open(os.path.join(PROJECT_ROOT, crv.KG), encoding="utf-8"))["kengetallen"]
    avail = sorted(f"{crv.key_str(k['candidate_key'])}|{k['material']['normalized']}" for k in kg
                   if k["status"] == "AVAILABLE")
    assert sorted(g["candidate_group"] for g in report["groups"] if g["readiness"] == "AVAILABLE") == avail
    by = {g["candidate_group"]: g for g in report["groups"]}
    a = by["4711|replace|m1|aluminium"]["existing_available_kengetal"]
    assert (a["kengetal_id"], a["value_display"], a["source_cluster_count"]) == \
        ("KG-4711-replace-m1-aluminium-d463b0a2", "37.47", 3)
    assert by["5211|replace|m1|pvc"]["existing_available_kengetal"]["value_display"] == "54.39"
    # bekende gevallen uit de eerdere beslispakketten
    assert by["4711|replace|m1|zinc"]["readiness"] == "INSUFFICIENT_CLUSTERS"
    assert by["4645|exterior_painting|m2|wood"]["readiness"] == "INSUFFICIENT_CLUSTERS"


def test_classification_follows_rules(report):
    for g in report["groups"]:
        b, h, r = set(g["blockers"]), g["human_actions"], g["readiness"]
        assert g["other_blockers"] == [x for x in g["blockers"] if x not in kr.REVIEW_BLOCKERS]
        if r == "AVAILABLE":
            assert g["existing_available_kengetal"]
            continue
        if g["potential_source_clusters_after_steps"]["count"] < 3:
            assert r == "INSUFFICIENT_CLUSTERS" and "INSUFFICIENT_CLUSTERS" in b
        elif g["other_blockers"]:
            assert r == "BLOCKED_OTHER"
        else:
            assert r in ("READY_AFTER_REVIEW", "MATERIAL_APPROVAL_NEEDED", "MATERIAL_AND_REVIEW_NEEDED")
            assert g["available_directly_after_steps"]
        if g["material"] is None:
            assert "NO_MATERIAL_EVIDENCE" in b and h["total"] is None
        else:
            assert h["total"] == h["material_approvals"] + h["review_family_decisions"] + \
                h["pair_decisions_outside_review_queue"]
            assert h["material_approvals"] == len(g["missing_material_approvals"])
            assert h["pair_decisions_outside_review_queue"] == len(g["pairs_outside_review_queue"])
            assert ("MATERIAL_APPROVAL_NEEDED" in b) == bool(g["missing_material_approvals"])
            assert ("PAIRS_OUTSIDE_REVIEW_QUEUE" in b) == bool(g["pairs_outside_review_queue"])


def test_sorted_deterministically(report):
    keys = [(g["readiness"] != "AVAILABLE", len(g["blockers"]),
             g["human_actions"]["total"] if g["human_actions"]["total"] is not None else 10 ** 9,
             -g["potential_source_clusters_after_steps"]["count"], g["candidate_group"]) for g in report["groups"]]
    assert keys == sorted(keys)
    assert [g["rank"] for g in report["groups"]] == list(range(1, len(report["groups"]) + 1))


def test_next_groups_and_least_work(report):
    by = {g["candidate_group"]: g for g in report["groups"]}
    nxt = [by[n] for n in report["next_groups"]]
    assert len(nxt) <= kr.DETAIL_COUNT
    assert all(g["readiness"] != "AVAILABLE" and g["expected_kengetal_effect"]["status"] == "AVAILABLE" for g in nxt)
    assert [g["rank"] for g in nxt] == sorted(g["rank"] for g in nxt)
    if nxt:
        least = by[report["least_work_group"]]
        assert least["human_actions"]["total"] == min(g["human_actions"]["total"] for g in nxt)


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_no_scoring_or_confidence_fields(report):
    bad = sorted({k for k in _keys(report) if "score" in k.lower() or "confidence" in k.lower()})
    assert bad == []


def test_no_ai_in_module():
    text = open(os.path.join(PROJECT_ROOT, "scripts", "kengetal_readiness_v1.py"), encoding="utf-8").read()
    for bad in ("import anthropic", "import openai", "import extract_batch", "from extract_batch"):
        assert bad not in text
