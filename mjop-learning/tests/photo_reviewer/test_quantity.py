import copy
from decimal import Decimal

import pytest

from agent.photo.contract import PhotoError
from agent.photo.quantity import compute_quantity_state, state_problems, validate_dimension_input

import photo_support as S


def state(dims=None, pset=None):
    return compute_quantity_state(pset or S.proposal_set(), dims)


def group(st, key):
    return next(g for g in st["groups"] if g["group_key"] == key)


def test_valid_state_example_gross_area_outer_dimensions():
    st = state(S.dims())
    assert group(st, "RAAM_A")["gross_area_m2"] == "5.04"          # 1,200 x 1,400 x 3 volledig zichtbare kozijnen
    assert group(st, "RAAM_B")["gross_area_m2"] == "2.52"          # 1,800 x 1,400 x 1 (twee draaiende delen = 1 opening)
    assert group(st, "DEUR_A")["gross_area_m2"] == "2.04" and group(st, "DEUR_A")["gross_area_m2_exact"] == "2.042500"
    assert st["totals"]["photo_visible_full_gross_area_m2"] == "9.60" and st["totals"]["complete_for_photo_visible_full"]
    assert st["review_status"] == "PROPOSED" and state_problems(st) == []


def test_partial_and_occluded_never_counted_as_fully_measured():
    st = state(S.dims())
    a = group(st, "RAAM_A")
    assert a["count_full"] == 3 and len(a["observation_ids_partial_excluded"]) == 1 and len(a["observation_ids_occluded_excluded"]) == 1
    assert a["partial_treated_as_fully_measured"] is False
    counts = st["photo_visible_counts"]["by_type"]["WINDOW_OPENING"]
    assert (counts["full"], counts["partial"], counts["occluded"]) == (4, 1, 1)


def test_partial_only_group_has_null_area():
    d = S.dims()
    ps = S.fresh()
    for p in ps["proposals"]:
        if p["element_type"] == "WINDOW_OPENING" and p["visibility"] == "FULL":
            p["visibility"] = "PARTIAL"; p["uncertainties"] = [{"code": "CROPPED_AT_EDGE", "level": "MEDIUM"}]
    st = compute_quantity_state(S.reseal(ps), d)
    assert group(st, "RAAM_A")["area_status"] == "NULL_NO_FULL_MEMBERS" and group(st, "RAAM_A")["gross_area_m2"] is None
    assert st["totals"]["photo_visible_full_gross_area_m2"] == "2.04"     # alleen de deur is volledig zichtbaar; deels zichtbare kozijnen tellen niet mee


def test_missing_dimensions_leave_area_null_not_zero_and_total_unknown():
    st = state(None)
    assert all(g["gross_area_m2"] is None and g["area_status"] == "NULL_NO_TYPE_ASSIGNMENT" for g in st["groups"])
    assert st["totals"]["photo_visible_full_gross_area_m2"] is None and not st["totals"]["complete_for_photo_visible_full"]
    assert st["dimension_input_sha256"] is None


def test_missing_reference_for_one_type_makes_only_that_group_null():
    d = S.dims()
    d["dimension_references"] = [r for r in d["dimension_references"] if r["type_group_key"] != "DEUR_A"]
    st = state(d)
    assert group(st, "DEUR_A")["area_status"] == "NULL_NO_DIMENSION_REFERENCE" and group(st, "DEUR_A")["gross_area_m2"] is None
    assert group(st, "RAAM_A")["gross_area_m2"] == "5.04"
    assert st["totals"]["photo_visible_full_gross_area_m2"] is None and st["totals"]["known_groups_subtotal_m2"] == "7.56"
    assert st["totals"]["groups_missing_area"] == ["DEUR_A"]


@pytest.mark.parametrize("w,h", [("0", "1.4"), ("0.05", "1.4"), ("1.2", "0"), ("25", "1.4"), ("11", "2")])
def test_implausible_dimensions_give_null_area(w, h):
    d = S.dims()
    d["dimension_references"][0].update(outer_width_m=w, outer_height_m=h)
    assert group(state(d), "RAAM_A")["area_status"] == "NULL_INVALID_DIMENSIONS"


@pytest.mark.parametrize("w", ["-1.2", "1,2", "abc", "", "1.2345", "NaN", "Infinity", "1e3"])
def test_invalid_dimension_strings_rejected_by_schema(w):
    d = S.dims()
    d["dimension_references"][0]["outer_width_m"] = w
    assert validate_dimension_input(d)
    with pytest.raises(PhotoError):
        state(d)


def test_floats_are_not_accepted_for_dimensions():
    d = S.dims()
    d["dimension_references"][0]["outer_width_m"] = 1.2
    assert validate_dimension_input(d)


@pytest.mark.parametrize("kind", ["AI_ESTIMATE", "MODEL", "VISION_MODEL", "UNKNOWN"])
def test_dimensions_can_never_originate_from_ai(kind):
    d = S.dims()
    d["dimension_references"][0]["source"]["kind"] = kind
    assert validate_dimension_input(d)


def test_dimension_validation_must_be_human():
    d = S.dims()
    d["dimension_references"][0]["source"]["validated_by"]["reviewer_type"] = "model"
    assert validate_dimension_input(d)
    d = S.dims()
    d["type_assignments"][0]["assigned_by"]["reviewer_type"] = "model"
    assert validate_dimension_input(d)


def test_proposals_cannot_carry_dimensions():
    from agent.photo.verifier import verify_proposal_set
    ps = S.fresh()
    ps["proposals"][0]["outer_width_m"] = "1.2"
    assert "FORBIDDEN_FIELD" in verify_proposal_set(S.reseal(ps)).codes()


def test_wrong_type_group_assignment_yields_mismatch_not_area():
    d = S.dims()
    d["type_assignments"] = [a if a["observation_id"] != "PO-004" else {**a, "type_group_key": "RAAM_A"} for a in d["type_assignments"]]
    st = state(d)
    assert group(st, "RAAM_A")["area_status"] == "NULL_ELEMENT_TYPE_MISMATCH" and group(st, "RAAM_A")["gross_area_m2"] is None


def test_duplicate_or_unknown_assignments_rejected():
    d = S.dims(); d["type_assignments"].append(copy.deepcopy(d["type_assignments"][0]))
    assert validate_dimension_input(d)
    d = S.dims(); d["type_assignments"][0]["observation_id"] = "PO-077"
    with pytest.raises(PhotoError):
        state(d)
    d = S.dims(); d["photo_id"] = "andere_foto"
    with pytest.raises(PhotoError):
        state(d)


def test_context_types_never_get_area():
    st = state(S.dims())
    assert {g["element_type"] for g in st["groups"]} <= {"WINDOW_OPENING", "EXTERIOR_DOOR", "BALCONY_DOOR"}
    assert st["photo_visible_counts"]["by_type"]["UNKNOWN_OPENING"]["counts_toward_frame_counts"] is False


def test_building_total_is_unknown_and_no_downstream_links():
    st = state(S.dims())
    assert st["building_total"] == {"status": "UNKNOWN", "value": None} and st["photo_visible_counts"]["is_building_total"] is False
    assert st["invariants"]["painting_area_m2"] is None and st["invariants"]["kengetal_link"] is None and st["invariants"]["price_link"] is None
    assert st["invariants"]["is_maintenance_quantity"] is False and st["invariants"]["is_instance"] is False


def test_deterministic_and_input_not_mutated():
    ps, d = S.proposal_set(), S.dims()
    before = copy.deepcopy((ps, d))
    assert compute_quantity_state(ps, d) == compute_quantity_state(ps, d) and (ps, d) == before


def test_decimal_rounding_half_up_not_float():
    d = S.dims()
    d["dimension_references"][2].update(outer_width_m="1.005", outer_height_m="1.000")     # 1,005 -> 1,01 (half-up)
    g = group(state(d), "DEUR_A")
    assert g["gross_area_m2_exact"] == "1.005000" and g["gross_area_m2"] == "1.01"


def test_tampered_state_is_detected():
    st = state(S.dims())
    bad = copy.deepcopy(st)
    group(bad, "RAAM_A")["gross_area_m2"] = "9.99"
    assert state_problems(bad)
    bad = copy.deepcopy(st); bad["invariants"]["is_maintenance_quantity"] = True
    assert state_problems(bad)
    bad = copy.deepcopy(st); bad["building_total"] = {"status": "KNOWN", "value": "12"}
    assert state_problems(bad)


def test_invalid_proposal_set_is_not_processed():
    ps = S.fresh(); ps["proposals"][0]["human_decision"] = "ACCEPT"
    with pytest.raises(PhotoError):
        compute_quantity_state(ps, S.dims())


def test_gross_area_formula_matches_independent_decimal_calculation():
    st = state(S.dims())
    expected = Decimal("1.2") * Decimal("1.4") * 3 + Decimal("1.8") * Decimal("1.4") + Decimal("0.95") * Decimal("2.15")
    assert Decimal(st["totals"]["photo_visible_full_gross_area_m2"]) == expected.quantize(Decimal("0.01"))
