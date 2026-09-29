"""
Tests voor scripts/build_kengetallen.py - kengetallen v1 (docs/kengetallen_rules_v1.md).
Synthetische gevallen voor de afzonderlijke regels en integratie op batch 1.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import build_kengetallen as bk  # noqa: E402

KEY = ("4645", "exterior_painting", "m2")
CONCRETE = {"original": "beton", "normalized": "concrete", "source": "verified_element"}


def make(oid, cluster, amount, qty, key=KEY, material=CONCRETE, independent=True, price_level="1-4-2023",
         element_line=(10, 5), text="Groot schilderwerk betonconstructie plafond", desc="Buitenschilderwerk plafond",
         caveats=()):
    doc = oid[3:10]
    norm = {
        "observation_id": oid, "document_id": doc,
        "action": {"action_text_original": text, "action_normalized": key[1]},
        "unit": {"unit_normalized": key[2], "unit_original": key[2]},
        "element": {"element_description_original": desc},
        "price": {"quantity_value": qty, "price_level_date": price_level, "cycle_start_year": 2030,
                  "cycle_length_years": 12, "vat_basis": "inclusive"},
        "source_ref": {"source_representations": [{
            "role": "primary_financial_row", "page": element_line[0], "line": element_line[1] + 2,
            "element_line": {"page": element_line[0], "line": element_line[1]} if element_line else None,
            "source_text": text}]},
    }
    value = (Decimal(amount) / Decimal(qty)).quantize(Decimal("0.01"))
    cmp_ = {
        "observation_id": oid, "document_id": doc, "source_cluster": cluster, "candidate_key": list(key),
        "independent_input": independent,
        "independent_input_exclusion_reasons": [] if independent else ["POSSIBLY_DEPENDENT"],
        "material": dict(material) if material else {"original": None, "normalized": None, "source": None},
        "caveats": list(caveats),
        "derived_unit_price_per_execution": {"annual_amount_used": amount, "quantity_value": qty,
                                             "executions_in_window": 1, "value": str(value)},
    }
    return norm, cmp_


def decision(did, a, b, kind="COMPARABLE_WITH_CAVEATS", caveats=(), status="ACTIVE"):
    return {"decision_id": did, "pair_id": f"PAIR-{did[4:]}", "observation_ids": [a, b], "decision": kind,
            "system_class": "COMPARABLE_WITH_CAVEATS", "decision_caveats": list(caveats), "status": status}


def run(observations, decisions):
    norm = [n for n, _ in observations]
    cmp_ = [c for _, c in observations]
    return bk.evaluate(norm, cmp_, decisions)


def all_pairs(ids, start=1):
    out, n = [], start
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            out.append(decision(f"HDR-{n:05d}", a, b))
            n += 1
    return out


A = "PO-DOC-001-P010-L010"
B = "PO-DOC-002-P010-L010"
C = "PO-DOC-003-P010-L010"
D = "PO-DOC-004-P010-L010"


# --------------------------------------------------------------------------
# Groepsvorming en minimum
# --------------------------------------------------------------------------

def test_three_clusters_complete_review_is_available_with_exact_median():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "1000", "10")]
    _, [k] = run(obs, all_pairs([A, B, C]))
    assert k["status"] == "AVAILABLE" and k["value_exact"] == "40" and k["source_cluster_count"] == 3
    assert (k["min_exact"], k["max_exact"], k["range_exact"]) == ("30", "100", "70")


def test_fewer_than_three_clusters_is_insufficient_data():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10")]
    _, [k] = run(obs, all_pairs([A, B]))
    assert k["status"] == "INSUFFICIENT_DATA" and k["value_exact"] is None
    assert k["insufficient_data_reasons"] == ["FEWER_THAN_3_SOURCE_CLUSTERS:2"]
    assert (k["min_display"], k["max_display"]) == ("30.00", "40.00")   # spreiding blijft zichtbaar


def test_incomplete_cross_cluster_review_blocks_without_transitivity():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    decisions = [decision("HDR-00001", A, B), decision("HDR-00002", B, C)]   # A-C nooit beoordeeld
    _, [k] = run(obs, decisions)
    assert k["status"] == "INSUFFICIENT_DATA" and "INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW" in k["insufficient_data_reasons"]
    assert k["missing_cross_cluster_reviews"] == [[A, C]] and k["human_review_complete"] is False


def test_not_comparable_inside_group_blocks():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    decisions = [decision("HDR-00001", A, B), decision("HDR-00002", B, C),
                 decision("HDR-00003", A, C, kind="NOT_COMPARABLE")]
    _, [k] = run(obs, decisions)
    assert k["status"] == "INSUFFICIENT_DATA"
    assert "NOT_COMPARABLE_WITHIN_GROUP:HDR-00003" in k["insufficient_data_reasons"]


def test_not_comparable_to_outsider_is_recorded_as_exclusion():
    E = "PO-DOC-005-P010-L010"
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10"),
           make(E, "SC-5", "900", "10")]
    _, [k] = run(obs, all_pairs([A, B, C]) + [decision("HDR-00009", A, E, kind="NOT_COMPARABLE")])
    assert k["status"] == "AVAILABLE" and E not in k["observation_ids"]
    assert k["exclusion_reasons"][E] == ["HUMAN_NOT_COMPARABLE:HDR-00009"]


def test_not_independent_observation_is_excluded():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10", independent=False)]
    _, [k] = run(obs, all_pairs([A, B, C]))
    assert C in k["excluded_observation_ids"] and k["exclusion_reasons"][C][0].startswith("NOT_INDEPENDENT_INPUT")
    assert C not in k["observation_ids"] and k["status"] == "INSUFFICIENT_DATA"   # nog maar 2 clusters


def test_superseded_decisions_are_ignored():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    decisions = all_pairs([A, B, C])
    decisions[2]["status"] = "SUPERSEDED"   # B-C niet meer actief
    _, [k] = run(obs, decisions)
    assert k["status"] == "INSUFFICIENT_DATA" and k["missing_cross_cluster_reviews"] == [[B, C]]


def test_same_key_without_human_decisions_gives_no_kengetal():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    summary, kengetallen = run(obs, [])
    assert kengetallen == [] and summary["candidate_groups"] == 0


def test_material_rules():
    text_pvc = {"original": "pvc", "normalized": "pvc", "source": "element_text"}
    pvc = {"original": "pvc", "normalized": "pvc", "source": "verified_element"}
    obs = [make(A, "SC-1", "300", "10", material=text_pvc), make(B, "SC-2", "400", "10", material=pvc),
           make(C, "SC-3", "500", "10", material=pvc)]
    _, [k] = run(obs, all_pairs([A, B, C]))
    assert k["status"] == "AVAILABLE" and k["material_source"] == ["element_text", "verified_element"]
    obs[2] = make(C, "SC-3", "500", "10", material={"original": "staal", "normalized": "steel", "source": "verified_element"})
    assert "MATERIAL_DIFFERS" in run(obs, all_pairs([A, B, C]))[1][0]["insufficient_data_reasons"]
    obs[2] = make(C, "SC-3", "500", "10", material=None)
    assert "MATERIAL_UNKNOWN" in run(obs, all_pairs([A, B, C]))[1][0]["insufficient_data_reasons"]


# --------------------------------------------------------------------------
# Clusters, posten en mediaan
# --------------------------------------------------------------------------

def test_one_contribution_per_source_cluster():
    A2, A3 = "PO-DOC-001-P010-L020", "PO-DOC-001-P010-L030"
    obs = [make(A, "SC-1", "100", "10", element_line=(10, 5)), make(A2, "SC-1", "200", "10", element_line=(10, 15)),
           make(A3, "SC-1", "900", "10", element_line=(10, 25)),
           make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    decisions = all_pairs([A, B, C]) + [decision("HDR-00010", A2, B), decision("HDR-00011", A2, C),
                                        decision("HDR-00012", A3, B), decision("HDR-00013", A3, C)]
    _, [k] = run(obs, decisions)
    assert len(k["cluster_contributions"]) == 3
    sc1 = next(c for c in k["cluster_contributions"] if c["source_cluster"] == "SC-1")
    assert sc1["contribution_exact"] == "20" and len(sc1["post_ids"]) == 3   # mediaan van 10, 20, 90
    assert k["value_exact"] == "40"


def test_front_back_split_is_one_post_and_keeps_all_observations():
    A2 = "PO-DOC-001-P010-L014"
    obs = [make(A, "SC-1", "300", "10", text="Groot schilderwerk plafond achter"),
           make(A2, "SC-1", "300", "10", text="Groot schilderwerk plafond voor"),
           make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    _, [k] = run(obs, all_pairs([A, A2, B, C]))
    post = next(p for p in k["posts"] if p["source_cluster"] == "SC-1")
    assert post["consolidated"] and post["observation_ids"] == [A, A2] and "achter" in post["consolidation_reason"]
    assert {A, A2} <= set(k["observation_ids"]) and len(k["source_references"]) == 4


@pytest.mark.parametrize("change", [
    {"element_line": (10, 9)},                               # andere elementregel (zelfde prijs!)
    {"qty": "20", "amount": "600"},                          # andere hoeveelheid
    {"text": "Groot schilderwerk plafond noord"},           # geen gevelzijde-woord
    {"text": "Groot schilderwerk plafond achter"},           # identieke tekst: geen gevelzijde-verschil
    {"text": "Groot schilderwerk plafond dakoverstek voor"},  # extra inhoudelijk woord
])
def test_no_consolidation_without_source_evidence(change):
    A2 = "PO-DOC-001-P010-L014"
    a2 = dict(amount="300", qty="10", text="Groot schilderwerk plafond voor", element_line=(10, 5))
    a2.update(change)
    obs = [make(A, "SC-1", "300", "10", text="Groot schilderwerk plafond achter"),
           make(A2, "SC-1", a2["amount"], a2["qty"], text=a2["text"], element_line=a2["element_line"]),
           make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    _, [k] = run(obs, all_pairs([A, A2, B, C]))
    assert not any(p["consolidated"] for p in k["posts"])
    assert len([p for p in k["posts"] if p["source_cluster"] == "SC-1"]) == 2


def test_even_number_of_contributions_uses_exact_decimal_median():
    obs = [make(A, "SC-1", "1", "3"), make(B, "SC-2", "2", "3"), make(C, "SC-3", "4", "3"), make(D, "SC-4", "8", "3")]
    _, [k] = run(obs, all_pairs([A, B, C, D]))
    expected = (Decimal("2") / Decimal("3") + Decimal("4") / Decimal("3")) / 2
    assert Decimal(k["value_exact"]) == expected and k["value_display"] == "1.00"


def test_price_level_flags():
    obs = [make(A, "SC-1", "300", "10", price_level="1-4-2023"), make(B, "SC-2", "400", "10", price_level="21-4-2025"),
           make(C, "SC-3", "500", "10", price_level=None)]
    _, [k] = run(obs, all_pairs([A, B, C]))
    pl = k["price_levels"]
    assert pl["mixed_price_level"] and pl["missing_price_level"] and pl["years"] == [2023, 2025]
    assert pl["indexation"] == "none" and "niet presenteren als prijs van één specifiek jaar" in pl["presentation_note"]
    assert pl["per_observation"][C] is None


def test_traceability_and_caveats():
    obs = [make(A, "SC-1", "300", "10", caveats=("CODE_LABEL_MISMATCH",)), make(B, "SC-2", "400", "10"),
           make(C, "SC-3", "500", "10")]
    decisions = all_pairs([A, B, C])
    decisions[0]["decision_caveats"] = ["PRICE_LEVEL_DIFFERENCE"]
    _, [k] = run(obs, decisions)
    assert k["decision_ids"] == ["HDR-00001", "HDR-00002", "HDR-00003"]
    assert k["decision_caveats"]["counts"] == {"PRICE_LEVEL_DIFFERENCE": 1}
    assert k["observation_caveats"][A] == ["CODE_LABEL_MISMATCH"]
    for ref in k["source_references"]:
        assert ref["page"] and ref["line"] and ref["element_line"] and ref["post_id"] and ref["price_per_execution_exact"]
    keys = set()

    def walk(x):
        if isinstance(x, dict):
            keys.update(str(key).lower() for key in x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(k)
    assert not any(w in key for key in keys for w in ("confidence", "score", "weight", "rank"))  # geen zulke velden


def test_evaluate_does_not_mutate_inputs():
    obs = [make(A, "SC-1", "300", "10"), make(B, "SC-2", "400", "10"), make(C, "SC-3", "500", "10")]
    decisions = all_pairs([A, B, C])
    before = copy.deepcopy((obs, decisions))
    run(obs, decisions)
    assert (obs, decisions) == before


# --------------------------------------------------------------------------
# Batch 1
# --------------------------------------------------------------------------

def batch1():
    return bk.build(PROJECT_ROOT, generated_at="2000-01-01T00:00:00Z")


def by_key(result):
    return {tuple(k["candidate_key"]): k for k in result["kengetallen"]}


def test_batch1_expected_outcomes():
    # Canonieke toestand: alleen kengetallen die door geldige ACTIVE human decisions worden gedragen.
    # De DF-1/DF-2-decisions staan op REVIEW_REQUIRED, dus C1 (4645) en de vier INSUFFICIENT_DATA-groepen van
    # vóór de promotie van batch1_v1 ontstaan niet meer (besluit A). Na het menselijke familiebesluit RFD-00001
    # (7 cross-cluster pvc-paren met DOC-012/DOC-013) draagt 5211 replace m1 pvc 5 source clusters. Na het
    # materiaalbesluit MATDEC-00002 en het familiebesluit RFD-00002 (3 aluminium-paren) draagt 4711 replace m1
    # aluminium 3 source clusters.
    result = batch1()
    k = by_key(result)
    assert result["summary"]["candidate_groups"] == 2 and result["summary"]["active_human_decisions"] == 15
    assert set(k) == {("5211", "replace", "m1"), ("4711", "replace", "m1")}
    c3 = k[("4711", "replace", "m1")]
    assert (c3["status"], c3["value_display"], c3["source_cluster_count"]) == ("AVAILABLE", "37.47", 3)
    assert (c3["min_display"], c3["max_display"]) == ("33.88", "39.06")
    assert c3["source_cluster_ids"] == ["SC-DOC-008+DOC-009", "SC-DOC-011", "SC-DOC-012"]
    c2 = k[("5211", "replace", "m1")]
    assert (c2["status"], c2["value_display"], c2["source_cluster_count"]) == ("AVAILABLE", "54.39", 5)
    assert (c2["min_display"], c2["max_display"]) == ("45.23", "61.09")


def test_batch1_values_come_from_observation_data():
    result = batch1()
    cmp_ = json.load(open(os.path.join(PROJECT_ROOT, "data", "comparability", "comparability_batch1.json"), encoding="utf-8"))
    obs = {a["observation_id"]: a for a in cmp_["observations"]}
    c2 = by_key(result)[("5211", "replace", "m1")]

    def p(i):
        d = obs[i]["derived_unit_price_per_execution"]
        return Decimal(d["annual_amount_used"]) / Decimal(d["quantity_value"])
    ids = ["PO-DOC-001-P026-L029", "PO-DOC-009-P021-L095", "PO-DOC-010-P012-L093", "PO-DOC-012-P015-L033",
           "PO-DOC-013-P019-L025"]
    assert Decimal(c2["value_exact"]) == sorted(p(i) for i in ids)[2]         # mediaan van 5 clusters
    assert not [p_ for p_ in c2["posts"] if p_["consolidated"]]
    assert c2["observation_ids"] == ids   # alle observations bewaard


def test_batch1_price_level_and_material_visibility():
    c2 = by_key(batch1())[("5211", "replace", "m1")]
    assert c2["price_levels"]["mixed_price_level"] and c2["price_levels"]["missing_price_level"]
    assert "element_text" in c2["material_source"]


def test_batch1_schema_and_determinism():
    r1, r2 = batch1(), batch1()
    assert bk.dump(r1) == bk.dump(r2)
    assert bk.validate_output(r1, os.path.join(PROJECT_ROOT, "schemas", "kengetal.schema.json")) == []


def test_batch1_build_does_not_touch_inputs():
    p = bk.paths(PROJECT_ROOT)
    before = {k: bk.sha256_file(v) for k, v in p.items()}
    batch1()
    assert {k: bk.sha256_file(v) for k, v in p.items()} == before


def test_committed_output_matches_rebuild():
    out = os.path.join(PROJECT_ROOT, "data", "kengetallen", "kengetallen_batch1.json")
    if not os.path.exists(out):
        pytest.skip("output nog niet gebouwd")
    assert bk.content(json.load(open(out, encoding="utf-8"))) == bk.content(batch1())


def test_writer_never_silently_overwrites(tmp_path):
    out = tmp_path / "k.json"
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "build_kengetallen.py"), "--out", str(out)]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    first = out.read_bytes()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and out.read_bytes() == first          # zelfde inhoud: niets geschreven
    tampered = json.loads(first)
    tampered["kengetallen"][0]["value_display"] = "999.99"
    out.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_bytes = out.read_bytes()
    assert subprocess.run(cmd, capture_output=True).returncode == 2 and out.read_bytes() == tampered_bytes
    assert subprocess.run(cmd + ["--supersede"], capture_output=True).returncode == 0
    new = json.loads(out.read_bytes())
    hist = tmp_path / "history" / f"k.{hashlib.sha256(tampered_bytes).hexdigest()[:12]}.json"
    assert hist.read_bytes() == tampered_bytes and new["supersedes"]["sha256"] == hashlib.sha256(tampered_bytes).hexdigest()
