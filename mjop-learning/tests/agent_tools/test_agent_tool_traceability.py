"""Bronherleidbaarheid: elk kengetal-, cluster- en observation-ID bestaat in de bronnen; de bronhashes kloppen met
de bestanden op schijf; de herleidingscontrole vangt gemanipuleerde uitvoer."""
import copy
import hashlib

import pytest

import support  # noqa: F401
from support import FIXTURE_ROOT, PROJECT_ROOT, sha256_file

import human_match_review as h
import match_kengetal as m
from agent.tools import get_kengetal_candidates as mod
from agent.tools.get_kengetal_candidates import get_kengetal_candidates

CTX = m.load_context(FIXTURE_ROOT)
KENGETALLEN, NORMALIZED = CTX[0], CTX[1]
MP = m.paths(FIXTURE_ROOT)


def c1():
    return dict(object_id="MJOP-1", element_code_internal="4645", action_normalized="exterior_painting",
                unit_normalized="m2", material_normalized="concrete", material_source="user",
                object_description="Buitenschilderwerk betonconstructie plafond", quantity="80", vat_basis="inclusive")


def c2():
    return dict(object_id="MJOP-2", element_code_internal="5211", action_normalized="replace", unit_normalized="m1",
                material_normalized="pvc", material_source="user", object_description="Hemelwaterafvoer pvc",
                quantity="100", vat_basis="inclusive")


@pytest.mark.parametrize("raw", [c1(), c2()])
def test_every_id_exists_in_the_sources(raw):
    out = get_kengetal_candidates(raw, root=FIXTURE_ROOT)
    assert out["candidates"]
    by_id = {k["kengetal_id"]: k for k in KENGETALLEN["kengetallen"]}
    for c in out["candidates"]:
        k = by_id[c["kengetal_id"]]
        assert c["source_cluster_ids"] and c["observation_ids"] and c["source_clusters"]
        assert set(c["source_cluster_ids"]) == set(k["source_cluster_ids"])
        assert set(c["observation_ids"]) == set(k["observation_ids"])
        for oid in c["observation_ids"]:
            assert oid in NORMALIZED
        for sc in c["source_clusters"]:
            assert sc["source_cluster"] in k["source_cluster_ids"]
            assert set(sc["observation_ids"]) <= set(c["observation_ids"])
        # elke observation hoort bij precies één bronwaarde met document-herkomst
        assert all(NORMALIZED[o]["document_id"] for o in c["observation_ids"])


@pytest.mark.parametrize("raw", [c1(), c2()])
def test_source_hashes_match_the_files_on_disk(raw):
    out = get_kengetal_candidates(raw, root=FIXTURE_ROOT)
    sh = out["provenance"]["source_hashes"]
    assert sh["kengetallen_output_sha256"] == sha256_file(MP["kengetallen"])
    assert sh["normalized_observations_sha256"] == sha256_file(MP["normalized"])
    store = h.load_json(h.paths(FIXTURE_ROOT)["store"])
    assert sh["decision_store_sha256"] == h.canonical_sha256(store)
    for name, digest in sh["vocabularies_sha256"].items():
        assert digest == sha256_file(f"{MP['vocab_dir']}/{name}.json")
    assert out["provenance"]["kengetallen_file"].endswith("kengetallen_batch1.json")
    assert out["provenance"]["rule_versions"]["matching_rule_version"] == "matching_rules_v1"


def test_values_are_copied_verbatim_from_the_kengetal():
    out = get_kengetal_candidates(c2(), root=FIXTURE_ROOT)
    k = next(x for x in KENGETALLEN["kengetallen"] if x["kengetal_id"] == out["candidates"][0]["kengetal_id"])
    c = out["candidates"][0]
    assert (c["value_exact"], c["min_exact"], c["max_exact"], c["value_display"]) == \
        (k["value_exact"], k["min_exact"], k["max_exact"], k["value_display"])
    assert [sc["contribution_exact"] for sc in c["source_clusters"]] == \
        [cc["contribution_exact"] for cc in k["cluster_contributions"]]
    assert c["decision_ids"] == k["decision_ids"]


def _out():
    return get_kengetal_candidates(c2(), root=FIXTURE_ROOT)


@pytest.mark.parametrize("mutate,fragment", [
    (lambda o: o["candidates"][0].update(kengetal_id="KG-DOES-NOT-EXIST"), "bestaat niet in de bron"),
    (lambda o: o["candidates"][0].update(value_exact="1.00"), "value_exact wijkt af"),
    (lambda o: o["candidates"][0]["observation_ids"].append("PO-FAKE-P001-L001"), "observation"),
    (lambda o: o["candidates"][0]["source_clusters"][0].update(source_cluster="SC-FAKE"), "cluster"),
    (lambda o: o["candidates"][0]["source_cluster_ids"].append("SC-FAKE"), "source_cluster_ids"),
])
def test_traceability_check_catches_tampered_output(mutate, fragment):
    out = copy.deepcopy(_out())
    mutate(out)
    errors = mod._traceability_errors(out, KENGETALLEN, NORMALIZED)
    assert errors and any(fragment in e for e in errors), errors


def test_untampered_output_has_no_traceability_errors():
    assert mod._traceability_errors(_out(), KENGETALLEN, NORMALIZED) == []


def test_live_data_smoke_invariants_only():
    """Tegen de actuele canonieke data: alleen invarianten, geen vaste waarden (die veranderen bij nieuwe kengetallen)."""
    live = m.load_context(PROJECT_ROOT)
    for k in live[0]["kengetallen"]:
        if k["status"] != "AVAILABLE":
            continue
        raw = dict(object_id="LIVE-1", element_code_internal=k["candidate_key"][0], action_normalized=k["candidate_key"][1],
                   unit_normalized=k["candidate_key"][2], material_normalized=(k["material"]["normalized"] or None))
        if not raw["material_normalized"]:
            continue
        out = get_kengetal_candidates(raw)      # echte root
        assert out["status"] in ("MATCH_PENDING_DECISION", "REVIEW_REQUIRED", "ACCEPTED", "ADJUSTED", "REJECTED")
        assert any(c["kengetal_id"] == k["kengetal_id"] for c in out["candidates"])
        if out["decision_state"] == "NO_HUMAN_DECISION":
            assert out["price_presentation"]["is_accepted_price"] is False
            assert out["price_presentation"]["effective_amount"] is None
        assert mod._traceability_errors(out, live[0], live[1]) == []
