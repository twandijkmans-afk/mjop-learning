"""
Tests voor de READ-ONLY semantische candidate review (scripts/semantic_candidate_review_v1.py):
determinisme en read-only gedrag (plus de expliciet gevraagde 4645-markeringen en ID-controle).
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import comparability_review_v2 as crv  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import semantic_candidate_review_v1 as scr  # noqa: E402


def _protected():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for rel in (scr.OUT_JSON, scr.OUT_MD, scr.READINESS, crv.OUT_JSON, crv.OUT_MD):
        out[rel] = pl.sha256_file(os.path.join(PROJECT_ROOT, rel))
    return out


@pytest.fixture(scope="module", autouse=True)
def real_repo_unchanged():
    before = _protected()
    yield
    assert _protected() == before, "het echte repo is gewijzigd"


@pytest.fixture(scope="module")
def report():
    return scr.build(PROJECT_ROOT)


def test_committed_and_deterministic(report):
    assert crv.dump(report) == open(os.path.join(PROJECT_ROOT, scr.OUT_JSON), encoding="utf-8").read()
    assert scr.render_md(report) == open(os.path.join(PROJECT_ROOT, scr.OUT_MD), encoding="utf-8").read()
    assert crv.dump(scr.build(PROJECT_ROOT)) == crv.dump(report)


def test_ids_exist_in_current_data(report):
    ctx = crv.Context(PROJECT_ROOT)
    readiness = json.load(open(os.path.join(PROJECT_ROOT, scr.READINESS), encoding="utf-8"))
    by = {g["candidate_group"]: g for g in readiness["groups"]}
    assert sorted(g["candidate_group"] for g in report["groups"]) == sorted(scr.GROUPS)
    for g in report["groups"]:
        assert [o["observation_id"] for o in g["observations"]] == by[g["candidate_group"]]["observation_ids"]
        for p in g["pairs"]:
            assert ctx.pairs[p["pair_id"]]["observation_ids"] == p["observation_ids"]
            assert p["system_class"] == ctx.pairs[p["pair_id"]]["class"]


def test_worklist_order_is_deterministic(report):
    keys = [(g["work_category_order"], g["summary"]["human_actions_total"], g["candidate_key"]) for g in report["groups"]]
    assert keys == sorted(keys)
    assert [w["candidate_group"] for w in report["worklist"]] == [g["candidate_group"] for g in report["groups"]]


def test_4645_required_markings(report):
    g = next(x for x in report["groups"] if x["candidate_group"] == "4645|interior_painting|m2|wood")
    pairs = {p["pair_id"]: p for p in g["pairs"]}
    assert sorted(pairs) == ["PAIR-00529", "PAIR-00531", "PAIR-00533"]
    m = pairs["PAIR-00529"]["semantic_differences"]["MATERIAL"]
    assert m["kind"] == "CONTRAST" and {"multiplex", "stucwerk"} == set(m["only_a"] + m["only_b"])
    for pid in ("PAIR-00531", "PAIR-00533"):
        f = pairs[pid]["semantic_differences"]["FINISH_SYSTEM"]
        assert f["kind"] == "CONTRAST" and {"dekkend", "transparant"} == set(f["only_a"] + f["only_b"])
    assert all(p["semantic_class"] == "SUBSTANTIVE_DIFFERENCE" for p in pairs.values())


def test_no_scoring_fields(report):
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not [k for k in keys(report) if any(w in k.lower() for w in ("score", "confidence", "rank"))]
