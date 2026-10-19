"""Bruto Quantity Model v2, fase 1 en 2: vocabulaires, schema's en deterministische rekenkern.

Uitsluitend synthetische fixtures. Geen v1-store, geen foto's, geen besluiten, geen prijzen.
"""
import ast
import copy
import json
import random
import sys
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import bruto_quantity_contracts as contracts  # noqa: E402
import bruto_quantity_core as core  # noqa: E402

SRC = {"source_kind": "HUMAN_MEASUREMENT", "source_id": "SYN-M1", "recorded_at": "2026-01-01T00:00:00Z", "recorded_by": "synthetisch", "authentication": "NONE_SELF_ASSERTED"}
SHA = "a" * 64


def dim(w="1.20", h="1.50", status="MEASURED"):
    if status == "UNKNOWN":
        return {"outer_width_m": None, "outer_height_m": None, "dimension_basis": "OUTER_FRAME", "dimension_status": "UNKNOWN",
                "measurement_method": "NONE", "source": {**SRC, "source_kind": "NONE", "source_id": None, "recorded_at": None, "recorded_by": None},
                "scale_evidence_ref": None, "validated_reference_ref": None, "uncertainty": None, "estimate": None}
    d = {"outer_width_m": w, "outer_height_m": h, "dimension_basis": "OUTER_FRAME", "dimension_status": status,
         "measurement_method": "MANUAL_MEASUREMENT", "source": dict(SRC), "scale_evidence_ref": None, "validated_reference_ref": None,
         "uncertainty": {"absolute_m": "0.01", "note": None}, "estimate": None}
    if status == "DRAWING_DERIVED":
        d["measurement_method"], d["scale_evidence_ref"] = "DRAWING_SCALE", "SYN-SCALE-1"
        d["source"] = {**SRC, "source_kind": "BUILDING_DRAWING"}
    return d


def ftype(tid="BQT-A", cat="FRAME", refs=None, cls="FRAME_CASEMENT", material="WOOD"):
    return {"contract_version": "bruto_frame_type_v2", "type_id": tid, "description": "synthetisch type", "type_classification": cls,
            "object_category": cat, "material": material, "material_basis": "synthetisch" if material != "UNKNOWN" else None,
            "reference_dimensions": refs if refs is not None else [{"reference_id": "R1", "dimension": dim()}],
            "variants": [], "sources": [dict(SRC)], "observation_refs": [], "is_physical_instance": False, "fi_ids": [], "status": "PROPOSED"}


def obs(i, cat="FRAME", vis="FULL"):
    return {"observation_id": f"OBS-{i}", "photo_id": "SYN-PHOTO-1", "object_category": cat, "visibility": vis}


def bobj(i, refs, *, cat="FRAME", d=None, q=1, tid="BQT-A", cert="HIGH", origin="OBSERVED", approvals=None, rep=None):
    cons = {"proposed_by": "AI_PROPOSAL", "certainty": cert, "basis_refs": []} if cert else None
    if origin == "ESTIMATED_MISSING":
        cons = None
    return {"contract_version": "bruto_quantity_object_v2", "object_id": f"BQO-{i}", "object_origin": origin, "object_category": cat,
            "type_id": tid, "quantity": q, "dimension": d if d is not None else dim(), "observation_refs": refs, "consolidation": cons,
            "approval_refs": approvals or [], "repetition_basis": rep, "is_physical_instance": False, "fi_id": None}


def approvals(*levels):
    return [{"level": lv, "record_ref": f"SYN-REC-{lv}", "record_sha256": SHA} for lv in levels]


class SyntheticVerifier:
    """Alleen voor testlogica: bewijst de beslislogica, niet dat er een echte goedkeuringsbron bestaat."""
    name = "SyntheticTestVerifier"
    provides_verified_approvals = True

    def __init__(self, levels=("A", "C")):
        self.levels = levels

    def verify(self, obj, level):
        return level in self.levels


def build(types, objects, observations, **kw):
    return contracts.build_checked_state(types, objects, observations, **kw)


# ------------------------------------------------------------------ Fase 1: vocabulaires en schema's

def test_all_v2_schemas_are_valid_json_schemas():
    for n in contracts.SCHEMA_NAMES:
        jsonschema.Draft7Validator.check_schema(contracts.load_schema(n))


def test_core_constants_match_vocabulary():
    v = contracts.load_vocabulary("bruto_quantity_concepts_v2")
    assert tuple(c["category"] for c in v["object_categories"]) == core.OBJECT_CATEGORIES
    assert tuple(s["status"] for s in v["dimension"]["statuses"]) == core.DIMENSION_STATUSES
    assert tuple(v["dimension"]["reliable_reference_statuses"]) == core.RELIABLE_REFERENCE_STATUSES
    assert tuple(v["dimension"]["estimate_comparability_bases"]) == core.COMPARABILITY_BASES
    assert tuple(v["dimension"]["estimate_proposal_origins"]) == core.PROPOSAL_ORIGINS
    assert tuple(x["layer"] for x in v["layers"] if x["partition"]) == ("PROVISIONAL_UNIQUE", "CONFIRMED", "ESTIMATED", "REVIEW_LOW_CERTAINTY")
    assert tuple(v["approval_policy"]["confirmed_requires_levels"]) == core.CONFIRMED_REQUIRES_LEVELS
    assert v["method"]["method_id"] == core.METHOD["method_id"]
    assert v["method"]["presentation_rounding"]["rule_id"] == core.METHOD["rounding_rule_id"]
    assert Decimal(v["method"]["min_dimension_m"]) == core.MIN_DIMENSION_M and Decimal(v["method"]["max_dimension_m"]) == core.MAX_DIMENSION_M
    assert v["method"]["glass_area_deducted"] is False and v["method"]["movable_parts_added_separately"] is False


def test_dimension_limits_follow_existing_photo_contract():
    from agent.photo.contract import MAX_DIMENSION_M, MIN_DIMENSION_M
    assert core.MIN_DIMENSION_M == Decimal(MIN_DIMENSION_M) and core.MAX_DIMENSION_M == Decimal(MAX_DIMENSION_M)


def test_actions_vocabulary_separates_the_five_concepts():
    v = contracts.load_vocabulary("bruto_quantity_actions_v2")
    acts = {a["action_id"]: a for a in v["actions"]}
    assert set(acts) == {"PAINT_EXTERIOR", "PAINT_INTERIOR", "FRAME_MAINTENANCE", "FRAME_REPLACEMENT", "DOOR_MAINTENANCE", "DOOR_REPLACEMENT"}
    for a in acts.values():
        for k in ("action_id", "quantity_unit", "measurement_basis", "historical_kengetal_ref", "price_unit"):
            assert k in a
        assert a["historical_kengetal_ref"] is None and a["price_unit"] is None     # koppeling volgt in een latere fase
        assert a["door_treatment_default"] == "UNDECIDED"
    assert acts["PAINT_EXTERIOR"]["measurement_basis"] == "GROSS_FRAME_AREA_OUTER" and acts["PAINT_EXTERIOR"]["measurement_basis_status"] == "DEFAULT"
    assert acts["PAINT_INTERIOR"]["measurement_basis"] == "UNKNOWN" and acts["PAINT_INTERIOR"]["quantity_unit"] is None
    assert acts["PAINT_INTERIOR"]["side"] == "INTERIOR" and acts["PAINT_EXTERIOR"]["side"] == "EXTERIOR"
    assert v["rules"]["interior_never_derived_from_exterior"] is True
    assert {t["treatment"] for t in v["door_treatments"]} == set(core.DOOR_TREATMENTS)


def test_legacy_window_terms_are_not_object_counts():
    v = contracts.load_vocabulary("bruto_quantity_concepts_v2")
    assert set(v["relation_to_v1"]["legacy_terms"]) == {"EXTERIOR_WINDOW", "WINDOW_COUNT"}
    o = bobj(1, ["OBS-1"])
    for bad in ("window_count", "sash_count", "glass_area_m2", "component_type"):
        assert contracts.object_errors({**o, bad: 3})        # gesloten schema: geen ramen of glas als eigen telling


def test_type_is_not_a_physical_instance():
    t = ftype()
    assert contracts.type_errors(t) == []
    assert contracts.type_errors({**t, "is_physical_instance": True})
    assert contracts.type_errors({**t, "fi_ids": ["FI-X-001"]})
    assert contracts.type_errors({**t, "status": "APPROVED"})


def test_type_requires_basis_for_known_material_and_rejects_estimate_as_reference():
    assert contracts.type_errors({**ftype(), "material_basis": None})
    est = dim(status="REFERENCE_DERIVED_ESTIMATE")
    assert contracts.dimension_errors(est)      # schatting zonder estimate-blok is ongeldig


def test_dimension_status_rules():
    assert contracts.dimension_errors(dim()) == []
    assert contracts.dimension_errors(dim(status="UNKNOWN")) == []
    assert contracts.dimension_errors(dim(status="DRAWING_DERIVED")) == []
    d = dim(status="DRAWING_DERIVED"); d["scale_evidence_ref"] = None
    assert contracts.dimension_errors(d)
    u = dim(status="UNKNOWN"); u["outer_width_m"] = "1.00"
    assert contracts.dimension_errors(u)
    m = dim(); m["outer_width_m"] = None
    assert contracts.dimension_errors(m)


def test_human_measurement_reference_is_not_authenticated_approval():
    d = dim(); d["source"]["authentication"] = "VERIFIED"
    assert contracts.dimension_errors(d)


# ------------------------------------------------------------------ Fase 2: rekenkern

@pytest.mark.parametrize("w,h,q,exp", [("1.20", "1.50", 1, "1.8"), ("1.20", "1.50", 3, "5.4"), ("0.995", "1.005", 2, "1.99995")])
def test_gross_area_is_width_times_height_times_quantity_exact(w, h, q, exp):
    assert core.gross_area_exact(w, h, q) == Decimal(exp)


@pytest.mark.parametrize("w,h", [("0", "1"), ("-1", "1"), ("1", "0.05"), ("11", "1"), ("1", "11"), ("abc", "1"), ("NaN", "1"), ("Infinity", "1"), (1.2, "1"), (True, "1"), (None, "1")])
def test_invalid_dimensions_are_refused(w, h):
    with pytest.raises(core.BrutoError):
        core.gross_area_exact(w, h, 1)


@pytest.mark.parametrize("q", [0, -1, 1.5, "2", None, True])
def test_invalid_quantity_is_refused(q):
    with pytest.raises(core.BrutoError):
        core.gross_area_exact("1.00", "1.00", q)


def test_one_frame_with_several_windows_counts_once_and_parts_do_not_add():
    # Een compleet kozijn met vaste en draaiende delen is één object, één observatie en één keer w x h.
    s = build([ftype()], [bobj(1, ["OBS-1"])], [obs(1)])
    assert s["layers"]["PROVISIONAL_UNIQUE"]["piece_count"] == 1 and s["layers"]["PROVISIONAL_UNIQUE"]["object_count"] == 1
    assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"] == "1.8"
    assert s["method"]["movable_parts_added_separately"] is False


def test_glass_stays_inside_gross_area():
    assert contracts.load_vocabulary("bruto_quantity_concepts_v2")["method"]["includes_glass"] is True
    s = build([ftype()], [bobj(1, ["OBS-1"])], [obs(1)])
    assert s["method"]["includes_glass"] is True and s["method"]["glass_area_deducted"] is False
    assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_presented"] == "1.80"


def test_three_identical_frames_with_one_reliable_dimension():
    s = build([ftype()], [bobj(1, ["OBS-1", "OBS-2", "OBS-3"], q=3)], [obs(1), obs(2), obs(3)])
    assert s["layers"]["PROVISIONAL_UNIQUE"]["piece_count"] == 3
    assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"] == "5.4"


def test_deviating_dimension_inside_a_type_group():
    objs = [bobj(1, ["OBS-1", "OBS-2"], q=2), bobj(2, ["OBS-3"], d=dim("1.30", "1.50"))]
    s = build([ftype()], objs, [obs(1), obs(2), obs(3)])
    k = s["areas"]["PROVISIONAL_UNIQUE"]["known"]
    assert len(k["by_type_group"]) == 1 and k["by_type_group"][0]["group_key"] == "BQT-A"
    assert Decimal(k["area_m2_exact"]) == Decimal("3.6") + Decimal("1.95") and k["area_m2_presented"] == "5.55"


def _est_inputs():
    ref = ftype("BQT-REF", refs=[{"reference_id": "R1", "dimension": dim("1.20", "1.50")}])
    tgt = ftype("BQT-TGT", refs=[])
    return ref, tgt


def test_estimate_from_known_reference_is_traceable():
    ref, tgt = _est_inputs()
    est = core.derive_estimate(ref, target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION", "SAME_MATERIAL"],
                               comparability_reason="zelfde klassiek draaikiepkozijn in dezelfde gevelrij", proposal_origin="AI_PROPOSAL", target_type=tgt)
    assert contracts.dimension_errors(est) == []
    e = est["estimate"]
    assert est["dimension_status"] == "REFERENCE_DERIVED_ESTIMATE" and e["estimate_status"] == "ESTIMATED"
    assert e["reference_type_id"] == "BQT-REF" and e["reference_ids"] == ["R1"] and e["derivation_method"] == "COPY_SINGLE_REFERENCE_V1"
    assert e["original_measure_sources"][0]["source_id"] == "SYN-M1" and e["comparability_reason"] and e["validated_measure"] is False
    assert e["uncertainty"]["reference_count"] == 1
    s = build([ref, tgt], [bobj(1, ["OBS-1"], tid="BQT-TGT", d=est)], [obs(1)])
    a = s["areas"]["PROVISIONAL_UNIQUE"]
    assert a["known"]["area_m2_exact"] is None and a["estimated"]["area_m2_exact"] == "1.8"


def test_estimate_median_keeps_spread():
    refs = [{"reference_id": f"R{i}", "dimension": dim(w, "1.50")} for i, w in enumerate(["1.10", "1.20", "1.40"], 1)]
    ref = ftype("BQT-REF", refs=refs)
    est = core.derive_estimate(ref, target_category="FRAME", comparability_basis=["SIMILAR_VISIBLE_PROPORTIONS"],
                               comparability_reason="vergelijkbare verhoudingen in dezelfde gevel", proposal_origin="RULE")
    assert est["outer_width_m"] == "1.20" and est["estimate"]["derivation_method"] == "MEDIAN_OF_REFERENCES_V1"
    assert est["estimate"]["uncertainty"]["spread_width_m"] == "0.30" and est["estimate"]["uncertainty"]["reference_count"] == 3


def test_estimate_refused_without_reliable_reference():
    unknown_ref = ftype("BQT-REF", refs=[{"reference_id": "R1", "dimension": dim(status="UNKNOWN")}])
    none_ref = ftype("BQT-REF", refs=[])
    kw = dict(target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION"], comparability_reason="zelfde type kozijn", proposal_origin="AI_PROPOSAL")
    for t in (unknown_ref, none_ref):
        with pytest.raises(core.BrutoError) as e:
            core.derive_estimate(t, target_type=ftype("BQT-T"), **kw)
        assert e.value.code == "ESTIMATE_NO_RELIABLE_REFERENCE"


def test_estimate_refused_for_estimate_chains_missing_reason_and_mismatches():
    ref, tgt = _est_inputs()
    kw = dict(target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION"], comparability_reason="zelfde type kozijn", proposal_origin="AI_PROPOSAL", target_type=tgt)
    first = core.derive_estimate(ref, **kw)
    chain = ftype("BQT-CHAIN", refs=[{"reference_id": "R1", "dimension": first}])
    with pytest.raises(core.BrutoError) as e:
        core.derive_estimate(chain, **kw)
    assert e.value.code == "ESTIMATE_NO_RELIABLE_REFERENCE"
    with pytest.raises(core.BrutoError):
        core.derive_estimate(ref, **{**kw, "comparability_reason": ""})
    with pytest.raises(core.BrutoError):
        core.derive_estimate(ref, **{**kw, "comparability_basis": []})
    with pytest.raises(core.BrutoError):
        core.derive_estimate(ref, **{**kw, "proposal_origin": "VISION_GUESS"})
    with pytest.raises(core.BrutoError) as e:
        core.derive_estimate(ref, **{**kw, "target_category": "DOOR"})
    assert e.value.code == "ESTIMATE_CATEGORY_MISMATCH"
    with pytest.raises(core.BrutoError):
        core.derive_estimate(ref, **{**kw, "target_type": ftype("BQT-T", cls="FRAME_FIXED")})
    with pytest.raises(core.BrutoError):
        core.derive_estimate(ref, **{**kw, "comparability_basis": ["SAME_MATERIAL"], "target_type": ftype("BQT-T", material="PVC")})
    with pytest.raises(core.BrutoError):
        core.derive_estimate(ref, **{**kw, "reference_ids": ["NOPE"]})


def test_ai_estimate_is_never_a_validated_measure():
    ref, tgt = _est_inputs()
    est = core.derive_estimate(ref, target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION"], comparability_reason="zelfde type kozijn", proposal_origin="AI_PROPOSAL", target_type=tgt)
    forged = copy.deepcopy(est); forged["estimate"]["validated_measure"] = True
    assert contracts.dimension_errors(forged)
    relabeled = copy.deepcopy(est); relabeled["dimension_status"] = "MEASURED"
    assert contracts.dimension_errors(relabeled)


def test_unknown_dimension_stays_unknown_and_unknown_area_is_not_zero():
    s = build([ftype()], [bobj(1, ["OBS-1"], d=dim(status="UNKNOWN"))], [obs(1)])
    a = s["areas"]["PROVISIONAL_UNIQUE"]
    assert a["known"]["area_m2_exact"] is None and a["known"]["area_m2_presented"] is None
    assert a["estimated"]["area_m2_exact"] is None
    assert a["unknown"] == {"object_count": 1, "piece_count": 1, "object_ids": ["BQO-1"], "area_m2": None}
    assert s["unknown"]["unknown_is_zero"] is False and s["unknown"]["unknown_area_object_ids"] == ["BQO-1"]
    assert s["areas"]["combined_total_m2"] is None and s["building_total"] == {"status": "UNKNOWN", "value": None}
    bad = copy.deepcopy(s); bad["areas"]["PROVISIONAL_UNIQUE"]["unknown"]["area_m2"] = "0"
    assert contracts.state_errors(bad)


def test_empty_input_yields_null_areas_not_zero():
    s = build([], [], [])
    for lay in ("PROVISIONAL_UNIQUE", "CONFIRMED", "ESTIMATED"):
        assert s["areas"][lay]["known"]["area_m2_exact"] is None and s["areas"][lay]["estimated"]["area_m2_exact"] is None
    assert s["layers"]["sum_across_layers"] is None


def test_known_estimated_and_unknown_areas_are_kept_apart():
    ref, tgt = _est_inputs()
    est = core.derive_estimate(ref, target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION"], comparability_reason="zelfde type kozijn", proposal_origin="RULE", target_type=tgt)
    objs = [bobj(1, ["OBS-1"], tid="BQT-REF"), bobj(2, ["OBS-2"], tid="BQT-TGT", d=est), bobj(3, ["OBS-3"], tid="BQT-TGT", d=dim(status="UNKNOWN"))]
    s = build([ref, tgt], objs, [obs(1), obs(2), obs(3)])
    a = s["areas"]["PROVISIONAL_UNIQUE"]
    assert (a["known"]["object_ids"], a["estimated"]["object_ids"], a["unknown"]["object_ids"]) == (["BQO-1"], ["BQO-2"], ["BQO-3"])
    assert a["known"]["area_m2_exact"] == "1.8" and a["estimated"]["area_m2_exact"] == "1.8"
    assert s["areas"]["combined_total_m2"] is None


def test_rounding_only_at_presentation_and_subtotals_add_up():
    t = [ftype(f"BQT-{c}") for c in "ABC"]
    objs = [bobj(i, [f"OBS-{i}"], tid=f"BQT-{c}", d=dim("1.003", "1.001")) for i, c in enumerate("ABC", 1)]
    s = build(t, objs, [obs(i) for i in (1, 2, 3)])
    k = s["areas"]["PROVISIONAL_UNIQUE"]["known"]
    assert k["area_m2_exact"] == "3.012009"                     # intern volledige precisie
    assert all(g["area_m2_exact"] == "1.004003" for g in k["by_type_group"])
    parts = sum(Decimal(g["area_m2_presented"]) for g in k["by_type_group"])
    assert str(parts) == k["area_m2_presented"] == "3.01"


def test_allocation_always_sums_to_rounded_total():
    rnd = random.Random(7)
    for _ in range(300):
        items = [(f"G{i}", Decimal(rnd.randint(1, 10 ** 7)) / Decimal(10 ** rnd.randint(2, 6))) for i in range(rnd.randint(1, 8))]
        total, parts = core.allocate_presented(items)
        assert sum(Decimal(v) for v in parts.values()) == Decimal(total) == Decimal(sum(v for _, v in items)).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")


def test_doors_are_registered_in_pieces_without_extra_maintenance():
    s = build([ftype(), ftype("BQT-D", cat="DOOR", cls="DOOR_ENTRANCE")],
              [bobj(1, ["OBS-1"]), bobj(2, ["OBS-2"], cat="DOOR", tid="BQT-D", d=dim("0.90", "2.10"), q=2)], [obs(1), obs(2, "DOOR")])
    assert s["doors"]["registered_in_pieces"]["PROVISIONAL_UNIQUE"] == 2 and s["doors"]["maintenance_quantities_created"] is False
    assert s["areas"]["door_treatment"] == "UNDECIDED" and s["areas"]["door_area_included"] is False
    assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"] == "1.8"      # deur niet in de m2
    assert s["layers"]["PROVISIONAL_UNIQUE"]["piece_count"] == 1                        # deuren niet bij de kozijnobjecten


def test_door_treatment_is_configurable_per_run():
    types = [ftype(), ftype("BQT-D", cat="DOOR", cls="DOOR_ENTRANCE")]
    objs = [bobj(1, ["OBS-1"]), bobj(2, ["OBS-2"], cat="DOOR", tid="BQT-D", d=dim("0.90", "2.10"))]
    o = [obs(1), obs(2, "DOOR")]
    inc = build(types, objs, o, door_treatment="PART_OF_GROSS_FRAME_AREA")
    assert inc["areas"]["door_area_included"] is True and Decimal(inc["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"]) == Decimal("1.8") + Decimal("1.89")
    for tr in ("AS_PIECES", "NOT_RELEVANT", "UNDECIDED"):
        s = build(types, objs, o, door_treatment=tr)
        assert s["areas"]["door_area_included"] is False and s["doors"]["registered_in_pieces"]["PROVISIONAL_UNIQUE"] == 1
    with pytest.raises(core.BrutoError):
        build(types, objs, o, door_treatment="WHATEVER")


def test_balcony_door_with_frame_is_one_object_and_not_a_door_count():
    t = ftype("BQT-B", cat="FRAME_WITH_DOOR", cls="DOOR_BALCONY_WITH_FRAME")
    s = build([t], [bobj(1, ["OBS-1"], cat="FRAME_WITH_DOOR", tid="BQT-B", d=dim("1.00", "2.30"))], [obs(1, "FRAME_WITH_DOOR")])
    assert s["layers"]["PROVISIONAL_UNIQUE"]["object_count"] == 1 and s["doors"]["registered_in_pieces"]["PROVISIONAL_UNIQUE"] == 0
    assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"] == "2.3"
    with pytest.raises(core.BrutoError):
        core.build_state([ftype()], [bobj(1, ["OBS-1"], cat="FRAME_WITH_DOOR")], [obs(1)])      # categorie wijkt af van type en observatie


def test_interior_and_exterior_painting_are_never_derived_from_each_other():
    acts = {a["action_id"]: a for a in contracts.load_vocabulary("bruto_quantity_actions_v2")["actions"]}
    ext, itr = acts["PAINT_EXTERIOR"], acts["PAINT_INTERIOR"]
    assert ext["action_id"] != itr["action_id"] and ext["side"] != itr["side"]
    assert itr["measurement_basis_status"] == "UNKNOWN" and itr["quantity_unit"] is None
    s = build([ftype()], [bobj(1, ["OBS-1"])], [obs(1)])
    assert "PAINT_INTERIOR" not in json.dumps(s) and s["doors"]["maintenance_quantities_created"] is False


def test_observations_are_not_automatically_unique_instances():
    # Zonder voorgestelde consolidatie of met lage zekerheid telt een observatie nergens als uniek kozijn.
    for cert in (None, "LOW", "UNKNOWN"):
        s = build([ftype()], [bobj(1, ["OBS-1"], cert=cert)], [obs(1)])
        assert s["layers"]["PROVISIONAL_UNIQUE"]["object_count"] == 0 and s["layers"]["REVIEW_LOW_CERTAINTY"]["object_count"] == 1
        assert s["observed"]["unconsolidated_observation_ids"] == ["OBS-1"] and s["observed"]["is_unique_count"] is False
        assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"] is None
    assert contracts.object_errors({**bobj(1, ["OBS-1"]), "is_physical_instance": True})
    assert contracts.object_errors({**bobj(1, ["OBS-1"]), "fi_id": "FI-X-001"})
    assert contracts.state_errors({**build([], [], []), "invariants": {**core.INVARIANTS, "fi_ids_created": True}})


def test_duplicate_observations_are_not_double_counted():
    s = build([ftype()], [bobj(1, ["OBS-1", "OBS-2"])], [obs(1), obs(2)])
    assert s["observed"]["observation_count"] == 2
    assert s["layers"]["PROVISIONAL_UNIQUE"]["object_count"] == 1 and s["layers"]["PROVISIONAL_UNIQUE"]["piece_count"] == 1
    assert s["areas"]["PROVISIONAL_UNIQUE"]["known"]["area_m2_exact"] == "1.8"
    with pytest.raises(core.BrutoError) as e:
        core.build_state([ftype()], [bobj(1, ["OBS-1"]), bobj(2, ["OBS-1"])], [obs(1)])
    assert e.value.code == "OBSERVATION_DOUBLE_CLAIM"
    with pytest.raises(core.BrutoError):
        core.build_state([ftype()], [bobj(1, ["OBS-1"]), bobj(1, ["OBS-2"])], [obs(1), obs(2)])
    with pytest.raises(core.BrutoError):
        core.build_state([ftype()], [bobj(1, ["OBS-1"])], [obs(1), obs(1)])


def test_no_unauthorized_confirmed_status():
    claims = approvals("A", "B", "C")
    s = build([ftype()], [bobj(1, ["OBS-1"], approvals=claims)], [obs(1)])
    assert s["layers"]["CONFIRMED"] == {"layer_status": "BLOCKED_NO_VERIFIED_APPROVAL_SOURCE", "object_count": 0, "object_ids": [], "piece_count": 0}
    assert s["layers"]["PROVISIONAL_UNIQUE"]["object_ids"] == ["BQO-1"]
    assert s["approval_verifier"] == {"name": "NullApprovalVerifier", "provides_verified_approvals": False}
    for forged in ({"layer": "CONFIRMED"}, {"identity_status": "CONFIRMED"}, {"status": "CONFIRMED"}):
        assert contracts.object_errors({**bobj(1, ["OBS-1"]), **forged})


def test_state_cannot_set_itself_to_a_final_status():
    s = build([ftype()], [bobj(1, ["OBS-1"])], [obs(1)])
    assert s["status"] == "PROPOSED" and s["release_status"] == "NOT_RELEASED" and s["usable_for_mjop"] is False
    for k, v in (("status", "APPROVED"), ("status", "RELEASED"), ("release_status", "RELEASED"), ("release_status", "APPROVED"), ("usable_for_mjop", True)):
        assert contracts.state_errors({**s, k: v})


def test_confirmed_layer_needs_verified_levels_a_and_c_and_stays_unreleased():
    types, objs, o = [ftype()], [bobj(1, ["OBS-1"], approvals=approvals("A", "C"))], [obs(1)]
    s = build(types, objs, o, approval_verifier=SyntheticVerifier())
    assert s["layers"]["CONFIRMED"]["object_ids"] == ["BQO-1"] and s["layers"]["CONFIRMED"]["layer_status"] == "OPEN_WITH_VERIFIED_APPROVALS"
    assert s["layers"]["PROVISIONAL_UNIQUE"]["object_ids"] == []
    assert s["release_status"] == "NOT_RELEASED" and s["usable_for_mjop"] is False and s["status"] == "PROPOSED"
    # alleen A (of de verifier bevestigt maar een niveau niet), of claim ontbreekt: niet bevestigd
    only_a = build(types, [bobj(1, ["OBS-1"], approvals=approvals("A"))], o, approval_verifier=SyntheticVerifier())
    assert only_a["layers"]["CONFIRMED"]["object_ids"] == []
    verifier_a_only = build(types, objs, o, approval_verifier=SyntheticVerifier(("A",)))
    assert verifier_a_only["layers"]["CONFIRMED"]["object_ids"] == []
    no_claim = build(types, [bobj(1, ["OBS-1"])], o, approval_verifier=SyntheticVerifier())
    assert no_claim["layers"]["CONFIRMED"]["object_ids"] == []

    class Raising(SyntheticVerifier):
        def verify(self, obj, level):
            raise RuntimeError("boom")

    class Truthy(SyntheticVerifier):
        def verify(self, obj, level):
            return "yes"

    class NoFlag:
        name = "NoFlag"

        def verify(self, obj, level):
            return True
    for v in (Raising(), Truthy(), NoFlag()):
        assert build(types, objs, o, approval_verifier=v)["layers"]["CONFIRMED"]["object_ids"] == []


def test_estimated_layer_never_flows_into_confirmed():
    rep = {"evidence_refs": ["SYN-REP-1"], "reason": "aantoonbare herhaling van hetzelfde type in de gevelrij"}
    ghost = bobj(9, [], origin="ESTIMATED_MISSING", rep=rep, approvals=approvals("A", "C"))
    assert contracts.object_errors(ghost)       # een geschat object kan geen goedkeuringen dragen
    ghost["approval_refs"] = []
    s = build([ftype()], [ghost], [], approval_verifier=SyntheticVerifier())
    assert s["layers"]["ESTIMATED"]["object_ids"] == ["BQO-9"] and s["layers"]["CONFIRMED"]["object_ids"] == []
    a = s["areas"]["ESTIMATED"]
    assert a["known"]["area_m2_exact"] is None and a["estimated"]["area_m2_exact"] == "1.8"      # geschat object heeft nooit een bekende m2
    assert contracts.object_errors({**ghost, "repetition_basis": None})
    assert contracts.object_errors({**ghost, "observation_refs": ["OBS-1"]})


def test_evidence_never_exceeds_the_weakest_component():
    ref, tgt = _est_inputs()
    est = core.derive_estimate(ref, target_category="FRAME", comparability_basis=["SAME_TYPE_CLASSIFICATION"], comparability_reason="zelfde type kozijn", proposal_origin="RULE", target_type=tgt)
    objs = [bobj(1, ["OBS-1"], tid="BQT-TGT", d=est, approvals=approvals("A", "C"))]
    s = build([ref, tgt], objs, [obs(1)], approval_verifier=SyntheticVerifier())
    c = s["areas"]["CONFIRMED"]
    assert s["layers"]["CONFIRMED"]["object_ids"] == ["BQO-1"]
    assert c["known"]["area_m2_exact"] is None and c["estimated"]["area_m2_exact"] == "1.8"      # bevestigde identiteit + geschatte maat = geschatte m2


def test_layers_do_not_overlap_and_do_not_sum():
    rep = {"evidence_refs": ["SYN-REP-1"], "reason": "aantoonbare herhaling van hetzelfde type in de gevelrij"}
    objs = [bobj(1, ["OBS-1"]), bobj(2, ["OBS-2"], cert="LOW"), bobj(3, [], origin="ESTIMATED_MISSING", rep=rep)]
    s = build([ftype()], objs, [obs(1), obs(2)])
    ids = [i for lay in core.LAYERS for i in s["layers"][lay]["object_ids"]]
    assert sorted(ids) == ["BQO-1", "BQO-2", "BQO-3"] and len(set(ids)) == 3
    assert s["layers"]["sum_across_layers"] is None and s["areas"]["combined_total_m2"] is None
    assert contracts.state_errors({**s, "areas": {**s["areas"], "combined_total_m2": "5.40"}})


def test_no_link_to_prices_costs_or_kengetallen():
    s = build([ftype()], [bobj(1, ["OBS-1"])], [obs(1)])
    assert s["invariants"]["price_link"] is None and s["invariants"]["kengetal_link"] is None and s["invariants"]["cost_link"] is None
    for k in ("price_link", "kengetal_link", "cost_link"):
        assert contracts.state_errors({**s, "invariants": {**s["invariants"], k: "X"}})
    for name in ("bruto_quantity_core.py", "bruto_quantity_contracts.py"):
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not [m for m in mods if any(w in m for w in ("price", "kengetal", "cost", "normalize", "promotion", "human_instance", "physical_instance", "vision"))], mods


def test_results_are_deterministic_and_order_independent():
    types = [ftype(), ftype("BQT-B")]
    objs = [bobj(1, ["OBS-1"]), bobj(2, ["OBS-2"], tid="BQT-B", d=dim("1.0", "2.0")), bobj(3, ["OBS-3"], cert="LOW")]
    o = [obs(1), obs(2), obs(3)]
    a = build(types, objs, o)
    b = build(list(reversed(types)), list(reversed(objs)), list(reversed(o)))
    assert json.dumps(a, sort_keys=False) == json.dumps(b, sort_keys=False) == json.dumps(build(types, objs, o))
    assert a["state_id"] == b["state_id"] and a["input_sha256"] == b["input_sha256"]
    changed = build(types, [bobj(1, ["OBS-1"], d=dim("1.21", "1.50"))] + objs[1:], o)
    assert changed["state_id"] != a["state_id"]


def test_inputs_are_not_mutated():
    types, objs, o = [ftype()], [bobj(1, ["OBS-1"])], [obs(1)]
    snap = copy.deepcopy((types, objs, o))
    build(types, objs, o)
    assert (types, objs, o) == snap


def test_invalid_object_input_is_refused_before_calculation():
    bad = bobj(1, ["OBS-1"], d=dim("0", "1.5"))
    with pytest.raises(core.BrutoError):
        build([ftype()], [bad], [obs(1)])
    with pytest.raises(core.BrutoError):
        build([ftype()], [bobj(1, ["OBS-1"], q=0)], [obs(1)])
    with pytest.raises(core.BrutoError):
        build([ftype()], [bobj(1, ["OBS-9"])], [obs(1)])


def test_core_is_pure_and_does_not_touch_frozen_or_v1_data():
    for name in ("bruto_quantity_core.py",):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        tree = ast.parse(src)
        calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        attrs = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not ({"open", "exec", "eval"} & calls) and not ({"write_text", "write_bytes", "mkdir", "unlink", "rename", "replace", "now", "random"} & attrs)
        for frozen in ("data/", "frame_inventory", "photo_evidence", "quantity_resolutions", "kentallen", "kengetallen", "bag_snapshots", "building_links", "instance_decisions"):
            assert frozen not in src
    assert not [n for n in ("os", "subprocess", "socket", "requests", "urllib", "random", "datetime", "time")
                if f"import {n}" in (ROOT / "scripts" / "bruto_quantity_core.py").read_text(encoding="utf-8")]


def test_v2_files_live_outside_frozen_directories():
    manifest = json.loads((ROOT / "tests/fixtures/scope_guard/frozen_manifest_v1.json").read_text(encoding="utf-8"))
    frozen = tuple(d + "/" for d in manifest["frozen_dirs"]) + tuple(d + "/" for d in manifest["readonly_dirs"])
    new = ["schemas/bruto_dimension_v2.schema.json", "schemas/bruto_frame_type_v2.schema.json", "schemas/bruto_observation_v2.schema.json",
           "schemas/bruto_quantity_object_v2.schema.json", "schemas/bruto_quantity_state_v2.schema.json",
           "vocabularies/bruto_quantity_concepts_v2.json", "vocabularies/bruto_quantity_actions_v2.json",
           "scripts/bruto_quantity_core.py", "scripts/bruto_quantity_contracts.py", "tests/test_bruto_quantity_model_v2.py", "docs/bruto_quantity_model_v2.md"]
    for p in new:
        assert (ROOT / p).exists() and not p.startswith(frozen)
        assert p not in manifest["files"]
    assert manifest["allowed_additions"] == []
