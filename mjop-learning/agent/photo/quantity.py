"""Deterministische hoeveelhedenmodule: PHOTO_VISIBLE-aantallen en bruto kozijnoppervlakte.

Meetmethode GROSS_FRAME_AREA_OUTER_V1: bruto m2 = buitenbreedte x buitenhoogte x aantal. Het volledige kozijn telt mee,
glas telt mee, vaste en draaiende delen vallen binnen de buitenmaat en worden niet extra opgeteld.
Afmetingen komen NOOIT uit een AI-voorstel: alleen uit gevalideerde menselijke/tekening-/referentiemaatinvoer.
Alleen Decimal (geen float); zonder maten blijft de oppervlakte null; PARTIAL en OCCLUDED tellen niet mee in oppervlakte."""
from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from agent.photo.contract import (AREA_TYPES, COUNTING_TYPES, ELEMENT_TYPES, MAX_DIMENSION_M, MIN_DIMENSION_M, PhotoError,
                                  canonical_sha256, load_schema, schema_errors)
from agent.photo.verifier import verify_or_raise

CENT = Decimal("0.01")
METHOD = OrderedDict([("method_id", "GROSS_FRAME_AREA_OUTER_V1"), ("formula", "outer_width_m * outer_height_m * count_full"),
                      ("includes_glass", True), ("includes_movable_parts_within_outer_dimensions", True),
                      ("movable_parts_added_separately", False), ("dimension_basis", "OUTER_FRAME"), ("decimal_places", 2)])
INVARIANTS = {"is_instance": False, "counts_in_any_total": False, "is_building_total": False, "is_maintenance_quantity": False,
              "painting_area_m2": None, "kengetal_link": None, "price_link": None}


def _dec(s):
    try:
        d = Decimal(s)
    except (InvalidOperation, TypeError):
        return None
    return d if d.is_finite() else None


def _valid_dimension(width, height):
    w, h = _dec(width), _dec(height)
    if w is None or h is None:
        return None
    lo, hi = Decimal(MIN_DIMENSION_M), Decimal(MAX_DIMENSION_M)
    if not (lo <= w <= hi and lo <= h <= hi):
        return None
    return w, h


def validate_dimension_input(dim):
    """Schema + semantiek van de maatinvoer. Geeft een lijst fouten (leeg = geldig)."""
    errs = schema_errors(dim, load_schema("photo_dimension_input.schema.json"))
    if errs:
        return errs
    ids = [r["dimension_ref_id"] for r in dim["dimension_references"]]
    keys = [r["type_group_key"] for r in dim["dimension_references"]]
    if len(set(ids)) != len(ids):
        errs.append("dimension_ref_id komt meer dan eens voor")
    if len(set(keys)) != len(keys):
        errs.append("type_group_key komt meer dan eens voor in de maatreferenties")
    seen = set()
    for a in dim["type_assignments"]:
        if a["observation_id"] in seen:
            errs.append(f"{a['observation_id']}: meerdere type-toewijzingen")
        seen.add(a["observation_id"])
    return errs


def compute_quantity_state(proposal_set, dimension_input=None, *, source_registry=None):
    """Bouwt een PhotoQuantityState uit een (opnieuw geverifieerde) voorstelset en optionele gevalideerde maatinvoer."""
    verify_or_raise(proposal_set, source_registry=source_registry)
    if dimension_input is not None:
        errs = validate_dimension_input(dimension_input)
        if errs:
            raise PhotoError("INVALID_DIMENSION_INPUT", "maatinvoer afgewezen", errs)
        if dimension_input["photo_id"] != proposal_set["photo"]["photo_id"]:
            raise PhotoError("INVALID_DIMENSION_INPUT", "maatinvoer hoort bij een andere foto")
    props = {p["observation_id"]: p for p in proposal_set["proposals"]}

    # 1. PHOTO_VISIBLE-aantallen per type.
    by_type = OrderedDict()
    for t in ELEMENT_TYPES:
        rows = [p for p in proposal_set["proposals"] if p["element_type"] == t]
        if rows:
            by_type[t] = {"counts_toward_frame_counts": t in COUNTING_TYPES,
                          "full": sum(p["visibility"] == "FULL" for p in rows),
                          "partial": sum(p["visibility"] == "PARTIAL" for p in rows),
                          "occluded": sum(p["visibility"] == "OCCLUDED" for p in rows)}

    # 2. Groepen: alleen waar een type-toewijzing (mens / goedgekeurde relatie) bestaat; de rest blijft ongegroepeerd.
    refs = {r["type_group_key"]: r for r in (dimension_input or {}).get("dimension_references", [])}
    assigned = {}
    for a in (dimension_input or {}).get("type_assignments", []):
        if a["observation_id"] not in props:
            raise PhotoError("INVALID_DIMENSION_INPUT", f"{a['observation_id']}: onbekende observatie")
        assigned[a["observation_id"]] = a["type_group_key"]

    members = OrderedDict()
    for oid in sorted(props):
        p = props[oid]
        if p["element_type"] not in AREA_TYPES:
            continue
        key = assigned.get(oid) or f"UNASSIGNED_{p['element_type']}"
        members.setdefault(key, []).append(p)

    groups = []
    for key, rows in members.items():
        etype = rows[0]["element_type"]
        full = [p["observation_id"] for p in rows if p["visibility"] == "FULL"]
        part = [p["observation_id"] for p in rows if p["visibility"] == "PARTIAL"]
        occ = [p["observation_id"] for p in rows if p["visibility"] == "OCCLUDED"]
        g = OrderedDict([("group_key", key), ("element_type", etype), ("dimension_ref_id", None), ("observation_ids_full", full),
                         ("observation_ids_partial_excluded", part), ("observation_ids_occluded_excluded", occ),
                         ("count_full", len(full)), ("outer_width_m", None), ("outer_height_m", None), ("gross_area_m2", None),
                         ("gross_area_m2_exact", None), ("area_status", None), ("partial_treated_as_fully_measured", False)])
        ref = refs.get(key)
        if key.startswith("UNASSIGNED_"):
            g["area_status"] = "NULL_NO_TYPE_ASSIGNMENT"
        elif ref is None:
            g["area_status"] = "NULL_NO_DIMENSION_REFERENCE"
        elif any(p["element_type"] != ref["element_type"] for p in rows):
            g["dimension_ref_id"], g["area_status"] = ref["dimension_ref_id"], "NULL_ELEMENT_TYPE_MISMATCH"
        else:
            g["dimension_ref_id"] = ref["dimension_ref_id"]
            dims = _valid_dimension(ref["outer_width_m"], ref["outer_height_m"])
            if dims is None:
                g["area_status"] = "NULL_INVALID_DIMENSIONS"
            elif not full:
                g["outer_width_m"], g["outer_height_m"] = ref["outer_width_m"], ref["outer_height_m"]
                g["area_status"] = "NULL_NO_FULL_MEMBERS"
            else:
                w, h = dims
                exact = w * h * len(full)
                g["outer_width_m"], g["outer_height_m"] = ref["outer_width_m"], ref["outer_height_m"]
                g["gross_area_m2_exact"] = format(exact, "f")
                g["gross_area_m2"] = format(exact.quantize(CENT, rounding=ROUND_HALF_UP), "f")
                g["area_status"] = "COMPUTED"
        groups.append(g)

    # 3. Totalen: alleen volledig als elke FULL-opening in een groep met berekende oppervlakte valt.
    computed = [g for g in groups if g["area_status"] == "COMPUTED"]
    missing = [g["group_key"] for g in groups if g["count_full"] > 0 and g["area_status"] != "COMPUTED"]
    subtotal = sum((Decimal(g["gross_area_m2_exact"]) for g in computed), Decimal(0))
    has_full = any(g["count_full"] > 0 for g in groups)
    complete = has_full and not missing
    totals = {"photo_visible_full_gross_area_m2": format(subtotal.quantize(CENT, rounding=ROUND_HALF_UP), "f") if complete else None,
              "known_groups_subtotal_m2": format(subtotal.quantize(CENT, rounding=ROUND_HALF_UP), "f") if computed else None,
              "complete_for_photo_visible_full": complete, "groups_missing_area": missing}

    set_sha = canonical_sha256(proposal_set)
    state = OrderedDict([
        ("contract_version", "photo_quantity_state_v1"), ("state_id", ""), ("review_status", "PROPOSED"),
        ("photo_id", proposal_set["photo"]["photo_id"]),
        ("proposal_set_ref", {"set_id": proposal_set["set_id"], "set_sha256": set_sha}),
        ("dimension_input_sha256", canonical_sha256(dimension_input) if dimension_input is not None else None),
        ("area_method", dict(METHOD)),
        ("photo_visible_counts", {"count_basis": "PHOTO_VISIBLE_ONLY", "is_building_total": False, "by_type": by_type}),
        ("groups", groups), ("totals", totals), ("building_total", {"status": "UNKNOWN", "value": None}),
        ("invariants", dict(INVARIANTS))])
    state = dict(state)
    state["state_id"] = "PQS-" + canonical_sha256({k: v for k, v in state.items() if k != "state_id"})[:16]
    problems = state_problems(state)
    if problems:
        raise PhotoError("OUTPUT_CONTRACT_VIOLATION", "hoeveelhedenstaat voldoet niet aan het contract", problems)
    return state


def state_problems(state):
    """Schema + interne consistentie (herberekent de oppervlakten uit de vastgelegde maten)."""
    errs = schema_errors(state, load_schema("photo_quantity_state.schema.json"))
    if errs:
        return errs
    for g in state["groups"]:
        if g["area_status"] == "COMPUTED":
            exact = Decimal(g["outer_width_m"]) * Decimal(g["outer_height_m"]) * g["count_full"]
            if format(exact, "f") != g["gross_area_m2_exact"] or format(exact.quantize(CENT, rounding=ROUND_HALF_UP), "f") != g["gross_area_m2"]:
                errs.append(f"{g['group_key']}: oppervlakte komt niet overeen met breedte x hoogte x aantal")
        elif g["gross_area_m2"] is not None:
            errs.append(f"{g['group_key']}: oppervlakte moet null zijn bij status {g['area_status']}")
    return errs
