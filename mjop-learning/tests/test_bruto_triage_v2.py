"""Quantity Review & Triage v1: deterministische triage, reviewpack (HTML + JSON) en kalibratiestructuur.

Uitsluitend synthetische fixtures. Geen foto-inhoud, geen persoonsgegevens, geen netwerk, geen besluiten.
"""
import ast
import copy
import json
import random
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import bruto_quantity_core as core  # noqa: E402
import bruto_review_pack as rp  # noqa: E402
import bruto_triage as tri  # noqa: E402
import bruto_triage_calibration as cal  # noqa: E402
import bruto_triage_contracts as contracts  # noqa: E402

SRC = {"source_kind": "HUMAN_MEASUREMENT", "source_id": "SYN-M1", "recorded_at": "2026-01-01T00:00:00Z", "recorded_by": "synthetisch", "authentication": "NONE_SELF_ASSERTED"}
SHA = "a" * 64
SHA2 = "b" * 64


def dim(w="1.20", h="1.50", status="MEASURED", unc="0.01"):
    if status == "UNKNOWN":
        return {"outer_width_m": None, "outer_height_m": None, "dimension_basis": "OUTER_FRAME", "dimension_status": "UNKNOWN", "measurement_method": "NONE",
                "source": {**SRC, "source_kind": "NONE", "source_id": None, "recorded_at": None, "recorded_by": None}, "scale_evidence_ref": None,
                "validated_reference_ref": None, "uncertainty": None, "estimate": None}
    return {"outer_width_m": w, "outer_height_m": h, "dimension_basis": "OUTER_FRAME", "dimension_status": status, "measurement_method": "MANUAL_MEASUREMENT",
            "source": dict(SRC), "scale_evidence_ref": None, "validated_reference_ref": None, "uncertainty": {"absolute_m": unc, "note": None}, "estimate": None}


def ftype(tid="BQT-A", refs=None, variants=None, cat="FRAME"):
    return {"contract_version": "bruto_frame_type_v2", "type_id": tid, "description": "synthetisch type", "type_classification": "FRAME_CASEMENT",
            "object_category": cat, "material": "WOOD", "material_basis": "synthetisch",
            "reference_dimensions": refs if refs is not None else [{"reference_id": "R1", "dimension": dim()}],
            "variants": variants or [], "sources": [dict(SRC)], "observation_refs": [], "is_physical_instance": False, "fi_ids": [], "status": "PROPOSED"}


def obs(i, photo="SYN-PHOTO-1", cat="FRAME", vis="FULL", src=True):
    return {"observation_id": f"OBS-{i}", "photo_id": photo, "object_category": cat, "visibility": vis, "source_ref": f"SYN-SRC-{i}" if src else None}


def bobj(i, refs, *, cat="FRAME", d=None, q=1, tid="BQT-A", cert="HIGH", origin="OBSERVED", approvals=None, rep=None):
    cons = {"proposed_by": "AI_PROPOSAL", "certainty": cert, "basis_refs": []} if cert else None
    if origin == "ESTIMATED_MISSING":
        cons = None
    return {"contract_version": "bruto_quantity_object_v2", "object_id": f"BQO-{i}", "object_origin": origin, "object_category": cat, "type_id": tid,
            "quantity": q, "dimension": d if d is not None else dim(), "observation_refs": refs, "consolidation": cons, "approval_refs": approvals or [],
            "repetition_basis": rep, "is_physical_instance": False, "fi_id": None}


def ev(i, a, b, basis="UNIQUE_CONFIGURATION", pol="SUPPORTS_SAME", src=True):
    return {"evidence_id": f"EV-{i}", "observation_ids": [f"OBS-{a}", f"OBS-{b}"], "evidence_basis": basis, "polarity": pol,
            "source_ref": f"SYN-EV-{i}" if src else None, "source_sha256": SHA if src else None}


def inp(objects, observations, *, types=None, evidence=None, flags=None, dev=None, ai=None):
    return {"contract_version": "bruto_triage_input_v2", "types": types if types is not None else [ftype()], "objects": objects, "observations": observations,
            "identity_evidence": evidence or [], "observation_flags": flags or [], "dimension_evidence": dev or [], "ai_confidence_info": ai or []}


def calibrated_config(**over):
    n, k, conf = 300, 0, 0.95
    cfg = {"contract_version": "bruto_triage_calibration_v2", "status": "CALIBRATED", "note": "synthetische testconfiguratie, geen echte kalibratie",
           "dataset": {"dataset_id": "SYN-SET", "version": "1", "dataset_sha256": "1" * 64, "labeling": "SYNTHETIC", "representative": True, "size": 900},
           "splits": {"development": {"split_sha256": "2" * 64, "size": 300}, "calibration": {"split_sha256": "3" * 64, "size": 300}, "test": {"split_sha256": "4" * 64, "size": 300}},
           "results": {"split": "test", "clean_predictions_n": n, "false_clean_k": k, "confidence_level": conf,
                       "declared_upper_bound": cal.clopper_pearson_upper(k, n, conf)},
           "error_budget": {"max_false_clean_rate": 0.02, "set_by": "USER", "set_in_ref": "SYN-TEST"}, "audit_sample": {"seed": "syn-seed", "size": 150},
           "parameters": {"min_independent_anchors": 1, "dimension_deviation_tolerance_m": "0.005", "estimate_min_references": 2,
                          "estimate_allowed_bases": ["SAME_TYPE_CLASSIFICATION"], "estimate_max_spread_m": "0.05"}, "authenticity": "NOT_VERIFIED"}
    cfg.update(over)
    return cfg


CAL = calibrated_config()


def run(i, calibrated=False, **kw):
    if calibrated:
        return tri.triage(i, CAL, allow_synthetic_calibration=True, **kw)
    return tri.triage(i, **kw)


def O(pack, oid):
    return next(o for o in pack["objects"] if o["object_id"] == oid)


def rules(o):
    return {r["rule_id"] for r in o["review_reasons"]}


def one_clean():
    return inp([bobj("1", ["OBS-1"])], [obs(1)])


# --------------------------------------------------------------------------
# Identiteitsas
# --------------------------------------------------------------------------

def test_two_photos_same_opening_with_anchor_supports_merge():
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2, "UNIQUE_CONFIGURATION")])
    o = O(run(i, calibrated=True), "BQO-1")
    assert o["identity_axis"]["class"] == "CLEAN_PROVISIONAL" and o["overall_class"] == "CLEAN_PROVISIONAL"


def test_two_photos_merged_with_similarity_only_is_insufficient():
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2, "SAME_LAYOUT")])
    p = run(i, calibrated=True)
    o = O(p, "BQO-1")
    assert "A-I3" in rules(o) and o["overall_class"] == "INSUFFICIENT_EVIDENCE" and o["work_state"] == "BLOCKED"
    assert not any(r["rule_id"] in ("A-R5",) for r in o["review_reasons"])


def test_no_distinguishing_identity_evidence_at_all():
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")])
    assert "A-I3" in rules(O(run(i, calibrated=True), "BQO-1"))
    j = inp([bobj("1", ["OBS-1"], cert=None)], [obs(1)])
    assert "A-I2" in rules(O(run(j, calibrated=True), "BQO-1"))
    k = inp([bobj("1", ["OBS-1"])], [obs(1, vis="PARTIAL")])
    assert "A-I1" in rules(O(run(k, calibrated=True), "BQO-1"))


def test_two_strongly_similar_but_different_frames_need_review_and_scenario():
    i = inp([bobj("1", ["OBS-1"]), bobj("2", ["OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2, "FEATURE_MATCH")])
    p = run(i, calibrated=True)
    for oid in ("BQO-1", "BQO-2"):
        assert "A-R2" in rules(O(p, oid)) and O(p, oid)["overall_class"] == "REVIEW_REQUIRED"
    sc = [s for s in p["scenarios"] if s["kind"] == "DUPLICATE_PAIR_IF_SAME_OBJECT"]
    assert len(sc) == 1 and sc[0]["effect"]["piece_change"] == -1
    assert sc[0]["effect"]["area_change_range"] == {"min_m2_exact": "-1.8", "max_m2_exact": "-1.8"}
    assert sc[0]["additive"] is False and sc[0]["is_final_quantity"] is False


def test_high_ai_confidence_without_evidence_does_not_help():
    base = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")])
    hi = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")], ai=[{"object_id": "BQO-1", "value": 0.999}])
    a, b = run(base, calibrated=True), run(hi, calibrated=True)
    assert O(b, "BQO-1")["overall_class"] == O(a, "BQO-1")["overall_class"] == "INSUFFICIENT_EVIDENCE"
    assert O(b, "BQO-1")["ai_confidence"] == {"value": 0.999, "used_in_decision": False, "calibrated": False}
    assert [o["review_reasons"] for o in a["objects"]] == [o["review_reasons"] for o in b["objects"]]


def test_observation_assigned_to_two_objects_is_conflict_and_blocked():
    i = inp([bobj("1", ["OBS-1"]), bobj("2", ["OBS-1"])], [obs(1)])
    p = run(i, calibrated=True)
    for oid in ("BQO-1", "BQO-2"):
        o = O(p, oid)
        assert "A-C1" in rules(o) and o["overall_class"] == "CONFLICT" and o["work_state"] == "BLOCKED" and o["contradictions"]
        assert o["effect_on_provisional_quantities"]["in_baseline"] is False
    assert p["baseline_state"]["layers"]["PROVISIONAL_UNIQUE"]["object_ids"] == []
    assert {s["kind"] for s in p["scenarios"]} == {"CONFLICT_AREA_AT_STAKE"}


def test_same_photo_twice_for_one_object_is_conflict():
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P1")], evidence=[ev(1, 1, 2)])
    assert "A-C2" in rules(O(run(i, calibrated=True), "BQO-1"))


def test_contradicting_and_cross_object_anchor_evidence_conflict():
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2, "UNIQUE_CONFIGURATION", "CONTRADICTS_SAME")])
    assert O(run(i, calibrated=True), "BQO-1")["overall_class"] == "CONFLICT" and "A-C3" in rules(O(run(i, calibrated=True), "BQO-1"))
    j = inp([bobj("1", ["OBS-1"]), bobj("2", ["OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2, "PLATE_ANCHOR")])
    p = run(j, calibrated=True)
    assert {O(p, "BQO-1")["overall_class"], O(p, "BQO-2")["overall_class"]} == {"CONFLICT"} and "A-C4" in rules(O(p, "BQO-1"))


def test_integrity_conflicts_do_not_crash_the_triage():
    unknown_type = inp([bobj("1", ["OBS-1"], tid="BQT-NOPE")], [obs(1)])
    assert "A-C5" in rules(O(run(unknown_type), "BQO-1"))
    instance = bobj("1", ["OBS-1"])
    instance["fi_id"], instance["is_physical_instance"] = "FI-X", True
    with pytest.raises(core.BrutoError) as ex:  # het schema weigert een FI-id of instance al aan de poort
        run(inp([instance], [obs(1)]))
    assert ex.value.code == "INPUT_SCHEMA_INVALID"


def test_blocking_basis_degraded_view_and_quantity_rules():
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2), ev(2, 1, 2, "REPETITION_RISK")])
    assert "A-I4" in rules(O(run(i, calibrated=True), "BQO-1"))
    j = inp([bobj("1", ["OBS-1"], q=3)], [obs(1)], flags=[{"observation_id": "OBS-1", "flags": ["OBLIQUE_VIEW"]}])
    o = O(run(j, calibrated=True), "BQO-1")
    assert {"A-R3", "A-R4"} <= rules(o) and o["work_state"] == "INDIVIDUAL_REVIEW"
    k = inp([bobj("1", ["OBS-1"])], [obs(1, src=False)])
    assert "A-R1" in rules(O(run(k, calibrated=True), "BQO-1"))


def test_estimated_missing_object_needs_review():
    est = bobj("9", [], origin="ESTIMATED_MISSING", rep={"evidence_refs": ["EV-REP"], "reason": "zelfde gevel, herhaling"}, d=dim(status="UNKNOWN"))
    p = run(inp([est], []), calibrated=True)
    assert "A-R7" in rules(O(p, "BQO-9"))


def test_calibrated_minimum_independent_anchors():
    cfg = calibrated_config(parameters={**CAL["parameters"], "min_independent_anchors": 2})
    i = inp([bobj("1", ["OBS-1", "OBS-2"])], [obs(1, "P1"), obs(2, "P2")], evidence=[ev(1, 1, 2)])
    p = tri.triage(i, cfg, allow_synthetic_calibration=True)
    assert "A-R6" in rules(O(p, "BQO-1"))


# --------------------------------------------------------------------------
# Maatas
# --------------------------------------------------------------------------

def test_measured_dimension_is_clean_on_dimension_axis():
    o = O(run(one_clean()), "BQO-1")
    assert o["dimension_axis"]["class"] == "CLEAN_PROVISIONAL" and o["dimension"]["gross_area_m2_exact"] == "1.8" and o["dimension"]["area_class"] == "KNOWN"


def _estimate(reference_ids=None, refs=None):
    refs = refs or [{"reference_id": "R1", "dimension": dim()}, {"reference_id": "R2", "dimension": dim("1.21", "1.50")}]
    ref_type = ftype("BQT-REF", refs=refs)
    d = core.derive_estimate(ref_type, target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION"],
                             comparability_reason="zelfde typeclassificatie en gevel", proposal_origin="RULE", target_type=ref_type)
    d = json.loads(json.dumps(d))
    if reference_ids is not None:
        d["estimate"]["reference_ids"] = reference_ids
    return ref_type, d


def test_reliable_type_based_estimate_is_review_when_uncalibrated_and_clean_when_calibrated():
    ref_type, d = _estimate()
    i = inp([bobj("1", ["OBS-1"], d=d, tid="BQT-A")], [obs(1)], types=[ftype(), ref_type])
    u = O(run(i), "BQO-1")
    assert "B-R1" in rules(u) and u["dimension"]["area_class"] == "ESTIMATED" and u["dimension_axis"]["class"] == "REVIEW_REQUIRED"
    c = O(run(i, calibrated=True), "BQO-1")
    assert c["dimension_axis"]["class"] == "CLEAN_PROVISIONAL" and c["dimension"]["area_class"] == "ESTIMATED"


def test_estimate_without_sufficient_reference():
    ref_type, d = _estimate(reference_ids=["R-NOPE"])
    i = inp([bobj("1", ["OBS-1"], d=d)], [obs(1)], types=[ftype(), ref_type])
    p = run(i, calibrated=True)
    o = O(p, "BQO-1")
    assert "B-I2" in rules(o) and o["dimension_axis"]["class"] == "INSUFFICIENT_EVIDENCE"
    assert p["baseline_state"]["areas"]["ESTIMATED"]["estimated"]["area_m2_exact"] is None
    ref_type2, d2 = _estimate(reference_ids=["R1"])
    j = inp([bobj("1", ["OBS-1"], d=d2)], [obs(1)], types=[ftype(), ref_type2])
    assert "B-R5" in rules(O(run(j, calibrated=True), "BQO-1"))  # 1 referentie, minimum 2
    ref_type3, d3 = _estimate()
    d4 = json.loads(json.dumps(d3))
    d4["estimate"]["reference_type_id"] = "BQT-A"
    d4["estimate"]["reference_type_id"] = "BQT-DOOR"
    l_ = inp([bobj("1", ["OBS-1"], d=d4)], [obs(1)], types=[ftype(), ftype("BQT-DOOR", cat="DOOR")])
    assert "B-C2" in rules(O(run(l_, calibrated=True), "BQO-1"))


def test_deviating_dimensions_in_one_type_group():
    t = ftype(variants=[{"variant_id": "V1", "description": "variant", "dimension": dim("1.00", "1.00")}])
    i = inp([bobj("1", ["OBS-1"]), bobj("2", ["OBS-2"], d=dim("1.30", "1.50")), bobj("3", ["OBS-3"], d=dim("1.00", "1.00"))],
            [obs(1), obs(2), obs(3)], types=[t])
    p = run(i, calibrated=True)
    assert "B-R2" in rules(O(p, "BQO-2")) and "B-R2" not in rules(O(p, "BQO-1")) | rules(O(p, "BQO-3"))
    t2 = ftype(refs=[])
    j = inp([bobj("1", ["OBS-1"]), bobj("2", ["OBS-2"]), bobj("3", ["OBS-3"], d=dim("1.30", "1.50"))], [obs(1), obs(2), obs(3)], types=[t2])
    q = run(j, calibrated=True)
    assert "B-R2" in rules(O(q, "BQO-3")) and "B-R2" not in rules(O(q, "BQO-1"))


def test_contradicting_dimension_sources_conflict():
    dev = [{"object_id": "BQO-1", "sources": [{"source_ref": "SYN-TEKENING", "outer_width_m": "1.50", "outer_height_m": "1.50", "uncertainty_m": "0.01"}]}]
    p = run(inp([bobj("1", ["OBS-1"])], [obs(1)], dev=dev), calibrated=True)
    o = O(p, "BQO-1")
    assert "B-C1" in rules(o) and o["overall_class"] == "CONFLICT" and o["work_state"] == "BLOCKED"
    ok = [{"object_id": "BQO-1", "sources": [{"source_ref": "SYN-TEKENING", "outer_width_m": "1.205", "outer_height_m": "1.50", "uncertainty_m": "0.01"}]}]
    assert "B-C1" not in rules(O(run(inp([bobj("1", ["OBS-1"])], [obs(1)], dev=ok), calibrated=True), "BQO-1"))


def test_unknown_dimension_missing_dimension_is_not_missing_identity():
    p = run(inp([bobj("1", ["OBS-1"], d=dim(status="UNKNOWN"))], [obs(1)]), calibrated=True)
    o = O(p, "BQO-1")
    assert o["identity_axis"]["class"] == "CLEAN_PROVISIONAL" and o["dimension_axis"]["class"] == "INSUFFICIENT_EVIDENCE" and "B-I1" in rules(o)
    assert o["dimension"]["gross_area_m2_exact"] is None and o["dimension"]["gross_area_m2_presented"] is None
    assert p["baseline_state"]["areas"]["PROVISIONAL_UNIQUE"]["unknown"]["area_m2"] is None
    sc = [s for s in p["scenarios"] if s["kind"] == "MISSING_DIMENSION_POTENTIAL_ESTIMATE"][0]
    assert sc["effect"]["potential_estimated_area_m2_exact"] == "1.8" and sc["effect"]["validated"] is False


def test_invalid_dimension_is_conflict():
    d = dim()
    d["outer_width_m"] = "99"
    o = O(run(inp([bobj("1", ["OBS-1"], d=d)], [obs(1)])), "BQO-1")
    assert "B-C3" in rules(o) and o["overall_class"] == "CONFLICT"


# --------------------------------------------------------------------------
# Kalibratie
# --------------------------------------------------------------------------

def test_uncalibrated_default_makes_nothing_clean():
    cfg = json.loads((ROOT / "config" / "bruto_triage_calibration_v2.json").read_text())
    assert cfg["status"] == "UNCALIBRATED" and all(v is None for v in cfg["parameters"].values()) and contracts.calibration_errors(cfg) == []
    p = run(one_clean())
    o = O(p, "BQO-1")
    assert p["calibration"]["effective_status"] == "UNCALIBRATED" and p["calibration"]["conservative_fallback"] is True
    assert o["overall_class"] == "REVIEW_REQUIRED" and "A-R5" in rules(o) and o["identity_axis"]["would_be_clean_if_calibrated"] is True
    assert p["summary"]["by_overall_class"]["CLEAN_PROVISIONAL"] == 0 and p["groups"] == []


def test_declared_calibrated_without_proof_falls_back_conservatively():
    bad = [calibrated_config(),  # synthetisch, zonder expliciete testtoestemming
           calibrated_config(splits={**CAL["splits"], "test": CAL["splits"]["calibration"]}),
           calibrated_config(error_budget={"max_false_clean_rate": 0.001, "set_by": "USER", "set_in_ref": "x"}),
           calibrated_config(results={**CAL["results"], "declared_upper_bound": 0.0001}),
           calibrated_config(audit_sample={"seed": "s", "size": 3}),
           calibrated_config(parameters={**CAL["parameters"], "estimate_max_spread_m": None})]
    for cfg in bad:
        p = tri.triage(one_clean(), cfg)
        assert p["calibration"]["effective_status"] == "UNCALIBRATED" and p["calibration"]["problems"]
        assert O(p, "BQO-1")["overall_class"] == "REVIEW_REQUIRED"
    human = calibrated_config(dataset={**CAL["dataset"], "labeling": "HUMAN_LABELED"})
    assert tri.triage(one_clean(), human)["calibration"]["effective_status"] == "CALIBRATED"
    assert tri.triage(one_clean(), calibrated_config(authenticity="NOT_VERIFIED"), allow_synthetic_calibration=True)["calibration"]["effective_status"] == "CALIBRATED"
    assert contracts.calibration_errors({**calibrated_config(), "authenticity": "VERIFIED"})


def test_clopper_pearson_and_audit_sample_helpers():
    assert abs(cal.clopper_pearson_upper(0, 300, 0.95) - (1 - 0.05 ** (1 / 300))) < 1e-9
    assert cal.clopper_pearson_upper(5, 5, 0.95) == 1.0
    assert 0.0 < cal.clopper_pearson_upper(3, 100, 0.95) < 0.1
    assert cal.min_audit_sample_size(0.02) == 149
    ids = [(f"BQO-{i}", f"{i:064x}") for i in range(40)]
    a, b = cal.audit_sample(ids, "seed", 7), cal.audit_sample(list(reversed(ids)), "seed", 7)
    assert a == b and len(a) == 7 and a != cal.audit_sample(ids, "ander", 7)


def test_group_is_prepared_never_released():
    objs = [bobj(str(n), [f"OBS-{n}"]) for n in range(1, 4)] + [bobj("4", ["OBS-4"], d=dim(status="UNKNOWN"))]
    p = run(inp(objs, [obs(n) for n in range(1, 5)]), calibrated=True)
    assert len(p["groups"]) == 1
    g = p["groups"][0]
    assert g["member_object_ids"] == ["BQO-1", "BQO-2", "BQO-3"] and g["release_executed"] is False and g["status"] == "PREPARED_NOT_RELEASED"
    assert g["exception_list_object_ids"] == ["BQO-4"] and set(g["audit_sample_object_ids"]) <= set(g["member_object_ids"])
    assert [O(p, f"BQO-{n}")["work_state"] for n in range(1, 5)] == ["READY_FOR_GROUP_REVIEW"] * 3 + ["BLOCKED"]
    assert all(o["released"] is False for o in p["objects"])
    single = run(inp([bobj("1", ["OBS-1"])], [obs(1)]), calibrated=True)
    assert O(single, "BQO-1")["work_state"] == "AUTO_PROVISIONAL" and single["groups"] == []


# --------------------------------------------------------------------------
# Pack: volledigheid, scheiding, scenario's, invarianten
# --------------------------------------------------------------------------

def mixed():
    objs = [bobj("1", ["OBS-1"]), bobj("2", ["OBS-2"], d=dim(status="UNKNOWN")), bobj("3", ["OBS-3"]), bobj("4", ["OBS-3"]),
            bobj("5", ["OBS-5", "OBS-6"], approvals=[{"level": "A", "record_ref": "SYN-REC", "record_sha256": SHA}]),
            bobj("D1", ["OBS-D"], cat="DOOR", tid="BQT-DOOR", d=dim("0.90", "2.10"))]
    ob = [obs(1), obs(2), obs(3), obs(5, "P1"), obs(6, "P2"), obs("D", cat="DOOR")]
    return inp(objs, ob, types=[ftype(), ftype("BQT-DOOR", cat="DOOR")], evidence=[ev(1, 5, 6, "SAME_LAYOUT")], ai=[{"object_id": "BQO-1", "value": 0.97}])


def test_completeness_and_schema():
    i = mixed()
    p = run(i, calibrated=True)
    assert contracts.pack_errors(p) == []
    assert sorted(o["object_id"] for o in p["objects"]) == sorted(o["object_id"] for o in i["objects"]) and p["summary"]["object_count"] == 6
    assert p["summary"]["complete"] is True and sum(p["summary"]["by_work_state"].values()) == 6
    assert sorted(p["work_queue"]) == sorted(o["object_id"] for o in p["objects"] if o["overall_class"] != "CLEAN_PROVISIONAL")
    assert [O(p, x)["review_priority"] for x in p["work_queue"]] == list(range(1, len(p["work_queue"]) + 1))
    assert p["work_queue"][0] in ("BQO-3", "BQO-4")  # CONFLICT eerst
    assert contracts.input_errors({**i, "extra": 1})


def test_pack_invariants_no_confirmed_no_decisions_no_instances():
    p = run(mixed(), calibrated=True)
    inv = p["invariants"]
    assert inv["release_state"] == "NOT_RELEASED" and inv["usable_for_mjop"] is False and inv["decisions_registered"] is False
    assert inv["approvals_simulated"] is False and inv["fi_ids_created"] is False and inv["confirmed_output"] is False
    assert inv["ai_confidence_used_in_decision"] is False and inv["group_release_executed"] is False and inv["final_building_total"] is None
    assert p["baseline_state"]["layers"]["CONFIRMED"]["object_ids"] == [] and p["baseline_state"]["layers"]["CONFIRMED"]["piece_count"] == 0
    assert '"FI-' not in json.dumps(p) and "decision" not in " ".join(k for k in p if k not in ("invariants",)).lower()
    assert all(o["released"] is False for o in p["objects"])
    claim = O(p, "BQO-5")
    assert {"flag": "APPROVAL_CLAIM_UNVERIFIED", "effect": "GEEN_EFFECT_OP_KLASSE"} in claim["info_flags"]
    assert claim["effect_on_provisional_quantities"]["layer"] != "CONFIRMED"
    plain = mixed()
    plain["objects"][4]["approval_refs"] = []
    assert O(run(plain, calibrated=True), "BQO-5")["overall_class"] == claim["overall_class"]


def test_layers_stay_separate_and_unknown_stays_null_no_total():
    p = run(mixed(), calibrated=True)
    st = p["baseline_state"]
    assert st["areas"]["combined_total_m2"] is None and st["building_total"] == {"status": "UNKNOWN", "value": None}
    assert st["areas"]["PROVISIONAL_UNIQUE"]["unknown"]["object_ids"] == ["BQO-2"] and st["areas"]["PROVISIONAL_UNIQUE"]["unknown"]["area_m2"] is None
    assert "BQO-3" not in json.dumps(st["layers"]) and "BQO-4" not in json.dumps(st["layers"])
    assert st["layers"]["REVIEW_LOW_CERTAINTY"]["object_ids"] == ["BQO-5"]  # onvoldoende identiteit telt niet als voorlopig-uniek
    door = O(p, "BQO-D1")
    assert "alleen in stuks" in door["effect_on_provisional_quantities"]["text"] and door["effect_on_provisional_quantities"]["counted_in_area"] is False
    assert "total" not in " ".join(k for s in p["scenarios"] for k in s["effect"]).lower()


def test_scenarios_independent_with_overlap_groups():
    objs = [bobj("1", ["OBS-1"]), bobj("2", ["OBS-2"]), bobj("3", ["OBS-3"]), bobj("4", ["OBS-4"], d=dim(status="UNKNOWN"))]
    i = inp(objs, [obs(n, f"P{n}") for n in range(1, 5)], evidence=[ev(1, 1, 2, "FEATURE_MATCH"), ev(2, 2, 3, "FEATURE_MATCH")])
    p = run(i, calibrated=True)
    pairs = [s for s in p["scenarios"] if s["kind"] == "DUPLICATE_PAIR_IF_SAME_OBJECT"]
    assert len(pairs) == 2 and pairs[0]["overlap_group"] == pairs[1]["overlap_group"] == "OG-BQO-1"
    assert all(s["additive"] is False and s["is_final_quantity"] is False and "niet optellen" in s["note"] for s in p["scenarios"])
    miss = [s for s in p["scenarios"] if s["kind"] == "MISSING_DIMENSION_POTENTIAL_ESTIMATE"][0]
    assert miss["overlap_group"] == "OG-BQO-4"


def test_no_reference_means_no_estimate_scenario_value():
    t = ftype(refs=[])
    p = run(inp([bobj("1", ["OBS-1"], d=dim(status="UNKNOWN"))], [obs(1)], types=[t]), calibrated=True)
    s = [x for x in p["scenarios"] if x["kind"] == "MISSING_DIMENSION_POTENTIAL_ESTIMATE"][0]
    assert s["effect"]["potential_estimated_area_m2_exact"] is None and s["effect"]["reason_code_if_none"] == "ESTIMATE_NO_RELIABLE_REFERENCE"


# --------------------------------------------------------------------------
# Determinisme, HTML, veiligheid
# --------------------------------------------------------------------------

def test_deterministic_json_and_html_independent_of_input_order():
    i = mixed()
    a = run(i, calibrated=True)
    j = copy.deepcopy(i)
    random.Random(7).shuffle(j["objects"])
    random.Random(8).shuffle(j["observations"])
    j["types"].reverse()
    b = run(j, calibrated=True)
    assert tri.pack_json(a) == tri.pack_json(b) and rp.render_html(a) == rp.render_html(b) and a["pack_id"] == b["pack_id"]
    assert tri.pack_json(run(i, calibrated=True)) == tri.pack_json(a)
    json.loads(tri.pack_json(a))


def test_html_is_offline_safe_and_escapes_input():
    evil = "<script>alert(1)</script>&\"'"
    i = mixed()
    i["observations"][0]["photo_id"] = evil
    i["observations"][0]["source_ref"] = evil
    i["types"][0]["description"] = evil
    i["objects"].append(bobj("E1", [], origin="ESTIMATED_MISSING", d=dim(status="UNKNOWN"), rep={"evidence_refs": ["EV-1"], "reason": evil}))
    p = run(i, calibrated=True)
    h = rp.render_html(p)
    assert "<script" not in h.lower() and "&lt;script&gt;alert(1)&lt;/script&gt;" in h
    for forbidden in ("<form", "<input", "<button", "<img", "<link", "<iframe", "<object", "<embed", "<video", "<audio", "src=", "href=", "onclick", "onload", "javascript:", "@import", "url("):
        assert forbidden not in h.lower(), forbidden
    assert not re.search(r"https?://", h) and "default-src 'none'" in h
    assert "Voorlopig. Niet vrijgegeven" in h and "registreert geen besluit" in h
    for o in p["objects"]:
        assert o["object_id"] in h


def test_no_network_during_triage_and_render(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("netwerkgebruik")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    p = run(mixed(), calibrated=True)
    rp.render_html(p)
    tri.pack_json(p)


def test_sources_have_no_network_or_model_or_write_dependencies():
    banned = {"socket", "urllib", "http", "requests", "httpx", "anthropic", "openai", "subprocess", "ftplib", "smtplib", "aiohttp", "shutil"}
    for name in ("bruto_triage.py", "bruto_triage_calibration.py", "bruto_triage_contracts.py", "bruto_review_pack.py"):
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        assert not (mods & banned), (name, mods & banned)
    for name in ("bruto_triage.py", "bruto_triage_calibration.py", "bruto_triage_contracts.py"):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "write_text" not in src and "open(" not in src, name


def _porcelain():
    return subprocess.run(["git", "status", "--porcelain", "--", "data", "reports", "vocabularies", "config", "schemas"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


def test_canonical_files_untouched_and_cli_refuses_repo_output(tmp_path):
    before = _porcelain()
    p = run(mixed(), calibrated=True)
    rp.render_html(p)
    f = tmp_path / "in.json"
    f.write_text(json.dumps(mixed()), encoding="utf-8")
    assert rp.main([str(f), "--out-dir", str(tmp_path / "out")]) == 0
    names = sorted(x.name for x in (tmp_path / "out").iterdir())
    assert len(names) == 2 and names[0].endswith(".html") and names[1].endswith(".json")
    with pytest.raises(SystemExit):
        rp.main([str(f), "--out-dir", str(ROOT / "reports" / "x")])
    assert _porcelain() == before
    assert not (ROOT / "reports" / "x").exists()


def test_rule_catalogue_matches_code_and_classes():
    voc = contracts.load_rules()
    ids = [r["rule_id"] for r in voc["rules"]]
    assert len(ids) == len(set(ids)) and set(voc["classes"]) == set(tri.CLASSES)
    assert all(r["class"] in tri.CLASSES and r["axis"] in ("IDENTITY", "DIMENSION") for r in voc["rules"])
    assert voc["identity_evidence_basis"]["anchors"] == list(tri.ANCHORS) and voc["identity_evidence_basis"]["blocking"] == list(tri.BLOCKING)
    assert voc["identity_evidence_basis"]["similarity_only"] == list(tri.SIMILARITY_ONLY)
    src = (ROOT / "scripts" / "bruto_triage.py").read_text(encoding="utf-8")
    used = set(re.findall(r'_reason\("([AB]-[A-Z]\d)"', src))
    assert used <= set(ids) and set(ids) - used == set()
    assert not any(r["rule_id"].startswith("I-") for r in voc["rules"])


def test_invalid_inputs_are_rejected_not_guessed():
    with pytest.raises(core.BrutoError) as ex:
        tri.triage({"contract_version": "bruto_triage_input_v2"})
    assert ex.value.code == "INPUT_SCHEMA_INVALID"
    dup = inp([bobj("1", ["OBS-1"]), bobj("1", ["OBS-2"])], [obs(1), obs(2)])
    with pytest.raises(core.BrutoError) as ex2:
        tri.triage(dup)
    assert ex2.value.code == "DUPLICATE_OBJECT_ID"
    bad_ev = inp([bobj("1", ["OBS-1"])], [obs(1)], evidence=[ev(1, 1, 99)])
    with pytest.raises(core.BrutoError) as ex3:
        tri.triage(bad_ev)
    assert ex3.value.code == "EVIDENCE_REFERENCE_INVALID"


def test_pack_schema_rejects_invariant_tampering():
    p = json.loads(tri.pack_json(run(mixed(), calibrated=True)))
    for path, val in ((("invariants", "confirmed_output"), True), (("invariants", "decisions_registered"), True), (("invariants", "release_state"), "RELEASED")):
        q = copy.deepcopy(p)
        q[path[0]][path[1]] = val
        assert contracts.pack_errors(q)
    q = copy.deepcopy(p)
    q["objects"][0]["released"] = True
    assert contracts.pack_errors(q)
    q = copy.deepcopy(p)
    q["scenarios"][0]["additive"] = True
    assert contracts.pack_errors(q)
