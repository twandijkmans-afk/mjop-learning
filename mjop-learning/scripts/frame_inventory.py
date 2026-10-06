"""Frame Inventory Foundation v1 — kozijn-/raam-/deur-instances, groepen, repeat-groepen en quantity-semantiek.

Keten: EXTERIOR_FRAME PRESENT -> frame/window/door instances -> locatie -> subtype -> materiaal -> count ->
maatvoering (alleen aantoonbaar) -> afgeleide quantities -> human review.

Regels:
- Frame/window/door zijn aparte component types; frame-count, opening-area, outer-area, painting-area en glass-area
  zijn aparte quantity-concepten zonder automatische equality (vocabularies/frame_quantity_concepts_v1.json).
- opening_area_m2 / frame_outer_area_m2 alleen als dimension_basis klopt, de maten bekend zijn en de count
  bevestigd is. painting_area_m2 bestaat niet: nooit automatisch.
- Repeat groups zijn pas ACTIEF na USER_CONFIRMED_REPEAT; een REPEAT_CANDIDATE is nooit bruikbaar.
- Geen gebouwbrede multiplier zonder menselijk besluit.
- Bedragen/maten als Decimal-strings; geen floats.
"""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONCEPTS_VOCAB = ROOT / "vocabularies" / "frame_quantity_concepts_v1.json"
FRAME_INVENTORY = ROOT / "data" / "frame_inventory" / "frame_inventory_v1.json"
REPEAT_GROUPS = ROOT / "data" / "frame_inventory" / "component_repeat_groups_v1.json"

COMPONENT_TYPES = ("EXTERIOR_FRAME", "EXTERIOR_WINDOW", "EXTERIOR_DOOR")
FACADE_SIDES = ("FRONT", "REAR", "LEFT", "RIGHT", "COURTYARD", "UNKNOWN")
SUBTYPES = ("FIXED_WINDOW", "TURN_TILT", "CASEMENT", "SLIDING", "EXTERIOR_DOOR", "FRENCH_DOOR", "WINDOW_DOOR_COMBINATION", "OTHER", "UNKNOWN")
MATERIALS = ("WOOD", "PVC", "ALUMINIUM", "STEEL", "OTHER", "UNKNOWN")
DIMENSION_BASES = ("OPENING", "FRAME_OUTER", "DRAWING_DIMENSION", "UNKNOWN")
STATUSES = ("PROPOSED", "REVIEW_REQUIRED", "CONFIRMED", "USER_OVERRIDDEN")
HUMAN_STATUSES = ("CONFIRMED", "USER_OVERRIDDEN")
SOURCE_TYPES = ("DRAWING_MEASURED", "USER_ASSISTED_PHOTO", "USER_CONFIRMED_MANUAL", "SOURCE_REPORTED_HISTORICAL")
REPEAT_STATUSES = ("REPEAT_CANDIDATE", "ACTIVE", "REJECTED")
TRANSFORMATIONS = ("SAME", "MIRRORED")
QUANTITY_PRIORITY = ("USER_CONFIRMED_MANUAL", "DRAWING_MEASURED", "USER_ASSISTED_PHOTO", "SOURCE_REPORTED_HISTORICAL", "LEGACY_ESTIMATE_FALLBACK")
Q2 = Decimal("0.01")
DEC_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")


class FrameError(RuntimeError):
    pass


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dec(s):
    """Decimal uit een string; floats zijn niet toegestaan (quantity-conventie)."""
    if isinstance(s, float) or isinstance(s, bool) or not isinstance(s, (str, int, Decimal)):
        raise FrameError(f"geen Decimal-string: {s!r}")
    if isinstance(s, str) and not DEC_RE.match(s):
        raise FrameError(f"geen Decimal-string: {s!r}")
    return Decimal(s)


def fmt2(d):
    return str(d.quantize(Q2, rounding=ROUND_HALF_UP))


def concepts():
    return {c["concept"]: c for c in load_json(CONCEPTS_VOCAB)["concepts"]}


# --------------------------------------------------------------------------
# Afleiding (alleen onder expliciete voorwaarden)
# --------------------------------------------------------------------------

def is_count_confirmed(rec):
    return rec.get("status") in HUMAN_STATUSES and isinstance(rec.get("count"), int) and rec["count"] >= 1


def derive_area(rec, basis):
    """count x width x height als gesloten gevolgtrekking. basis: 'OPENING' (-> WINDOW_OPENING_AREA) of 'FRAME_OUTER'
    (-> FRAME_OUTER_AREA). Geeft {'status': 'DERIVED', 'value_m2': '14.40'} of {'status': 'UNKNOWN', 'reason': ...}.
    Nooit painting-area; nooit uit een andere basis."""
    if basis not in ("OPENING", "FRAME_OUTER"):
        raise FrameError("basis moet OPENING of FRAME_OUTER zijn")
    if rec.get("dimension_basis") != basis:
        return {"status": "UNKNOWN", "reason": f"dimension_basis is {rec.get('dimension_basis')!r}, niet {basis}"}
    if rec.get("width_m") is None or rec.get("height_m") is None:
        return {"status": "UNKNOWN", "reason": "width_m/height_m ontbreekt (dimensions UNKNOWN)"}
    if not is_count_confirmed(rec):
        return {"status": "UNKNOWN", "reason": "count is niet bevestigd (status CONFIRMED/USER_OVERRIDDEN vereist)"}
    total = rec["count"] * dec(rec["width_m"]) * dec(rec["height_m"])
    return {"status": "DERIVED", "value_m2": fmt2(total)}


# --------------------------------------------------------------------------
# Validatie
# --------------------------------------------------------------------------

INSTANCE_FIELDS = {"frame_instance_id", "building_id", "bag_pand_id", "component_type", "facade_side", "storey", "subtype", "material",
                   "count", "width_m", "height_m", "dimension_basis", "opening_area_m2", "frame_outer_area_m2", "source_refs", "provenance",
                   "status", "human_decision_ref", "repeat_group_id", "frame_group_id", "scale_evidence"}
INSTANCE_REQUIRED = {"frame_instance_id", "building_id", "bag_pand_id", "component_type", "facade_side", "storey", "subtype", "material", "count",
                     "source_refs", "provenance", "status"}


def instance_errors(r):
    e, rid = [], r.get("frame_instance_id")
    if "painting_area_m2" in r or "frame_painting_area" in r:
        e.append(f"{rid}: painting_area bestaat niet op een instance; nooit automatisch afleiden")
    for k in set(r) - INSTANCE_FIELDS - {"painting_area_m2", "frame_painting_area"}:
        e.append(f"{rid}: onbekend veld {k}")
    for k in INSTANCE_REQUIRED - set(r):
        e.append(f"{rid}: verplicht veld {k} ontbreekt")
    if e:
        return e
    for field, allowed in (("component_type", COMPONENT_TYPES), ("facade_side", FACADE_SIDES), ("subtype", SUBTYPES), ("material", MATERIALS),
                           ("status", STATUSES)):
        if r[field] not in allowed:
            e.append(f"{rid}: {field} {r[field]!r} niet toegestaan")
    if not (isinstance(r["count"], int) and not isinstance(r["count"], bool) and r["count"] >= 1):
        e.append(f"{rid}: count moet een geheel getal >= 1 zijn")
    st = r["storey"]
    if not (st == "UNKNOWN" or isinstance(st, int) and not isinstance(st, bool) or isinstance(st, str) and st):
        e.append(f"{rid}: storey moet integer, label of UNKNOWN zijn")
    if not r["source_refs"]:
        e.append(f"{rid}: source_refs (provenance) ontbreekt")
    if not isinstance(r["provenance"], dict) or r["provenance"].get("source_type") not in SOURCE_TYPES:
        e.append(f"{rid}: provenance.source_type moet een van {SOURCE_TYPES} zijn")
    basis = r.get("dimension_basis", "UNKNOWN")
    if basis not in DIMENSION_BASES:
        e.append(f"{rid}: dimension_basis {basis!r} niet toegestaan")
    for f in ("width_m", "height_m", "opening_area_m2", "frame_outer_area_m2"):
        v = r.get(f)
        if v is not None:
            if not isinstance(v, str) or not DEC_RE.match(v) or Decimal(v) <= 0:
                e.append(f"{rid}: {f} moet een positieve Decimal-string zijn")
    if (r.get("width_m") is None) != (r.get("height_m") is None):
        e.append(f"{rid}: width_m en height_m komen samen voor of ontbreken samen")
    if r.get("width_m") is not None and (basis == "UNKNOWN" or not r.get("scale_evidence") and r["provenance"].get("source_type") == "DRAWING_MEASURED"):
        e.append(f"{rid}: maten vereisen een bekende dimension_basis (en bij DRAWING_MEASURED scale_evidence); anders UNKNOWN")
    if r["status"] in HUMAN_STATUSES and not r.get("human_decision_ref"):
        e.append(f"{rid}: status {r['status']} vereist human_decision_ref")
    for field, b, concept in (("opening_area_m2", "OPENING", "WINDOW_OPENING_AREA"), ("frame_outer_area_m2", "FRAME_OUTER", "FRAME_OUTER_AREA")):
        if r.get(field) is not None:
            d = derive_area(r, b)
            if d["status"] != "DERIVED":
                e.append(f"{rid}: {field} ({concept}) niet toegestaan: {d['reason']}")
            elif d["value_m2"] != r[field]:
                e.append(f"{rid}: {field} {r[field]} wijkt af van count x breedte x hoogte = {d['value_m2']}")
    return e


GROUP_REQUIRED = {"frame_group_id", "building_id", "representative_instance", "count", "applies_to", "source_refs", "status"}


def group_errors(g):
    e, gid = [], g.get("frame_group_id")
    for k in GROUP_REQUIRED - set(g):
        e.append(f"{gid}: verplicht veld {k} ontbreekt")
    if e:
        return e
    rep = g["representative_instance"]
    e += instance_errors(rep)
    if not (isinstance(g["count"], int) and not isinstance(g["count"], bool) and g["count"] >= 2):
        e.append(f"{gid}: een groep heeft count >= 2 (een enkel object is een instance)")
    if rep.get("count") != 1:
        e.append(f"{gid}: representative_instance.count moet 1 zijn (de groep draagt het aantal)")
    if g["status"] not in STATUSES:
        e.append(f"{gid}: status {g['status']!r} niet toegestaan")
    if not g["source_refs"]:
        e.append(f"{gid}: source_refs ontbreekt")
    scopes = g["applies_to"]
    if not scopes or not isinstance(scopes, list):
        e.append(f"{gid}: applies_to ontbreekt")
    else:
        for s in scopes:
            if s.get("scope") == "BUILDING_WIDE" and not g.get("human_decision_ref"):
                e.append(f"{gid}: gebouwbrede multiplier vereist een menselijk besluit (human_decision_ref)")
    if g["status"] in HUMAN_STATUSES and not g.get("human_decision_ref"):
        e.append(f"{gid}: status {g['status']} vereist human_decision_ref")
    if g.get("occurrence_basis") == "SAME_DRAWING_SYMBOL" and not g.get("occurrence_evidence_refs"):
        e.append(f"{gid}: hetzelfde tekeningsymbool mag alleen als iedere occurrence aantoonbaar hetzelfde type is (occurrence_evidence_refs)")
    if g.get("occurrence_basis") == "SAME_DRAWING_SYMBOL" and len(g.get("occurrence_evidence_refs") or []) != g["count"]:
        e.append(f"{gid}: occurrence_evidence_refs moet precies één verwijzing per occurrence bevatten (count)")
    # afgeleide quantity van een groep: gebruik het groepsaantal
    probe = dict(rep, count=g["count"], status=g["status"] if g["status"] in HUMAN_STATUSES else rep["status"])
    for field, b in (("opening_area_m2", "OPENING"), ("frame_outer_area_m2", "FRAME_OUTER")):
        if g.get(field) is not None:
            d = derive_area(probe, b)
            if d["status"] != "DERIVED":
                e.append(f"{gid}: {field} niet toegestaan: {d['reason']}")
            elif d["value_m2"] != g[field]:
                e.append(f"{gid}: {field} {g[field]} wijkt af van {d['value_m2']}")
    if "painting_area_m2" in g:
        e.append(f"{gid}: painting_area bestaat niet; nooit automatisch afleiden")
    return e


REPEAT_REQUIRED = {"repeat_group_id", "building_id", "component_type", "representative_pand_id", "applies_to_pand_ids", "transformation",
                   "evidence_refs", "decision_ref", "status"}


def repeat_group_errors(g):
    e, gid = [], g.get("repeat_group_id")
    for k in REPEAT_REQUIRED - set(g):
        e.append(f"{gid}: verplicht veld {k} ontbreekt")
    if e:
        return e
    if g["component_type"] not in COMPONENT_TYPES:
        e.append(f"{gid}: component_type {g['component_type']!r} niet toegestaan (een groep geldt per componenttype)")
    if g["transformation"] not in TRANSFORMATIONS:
        e.append(f"{gid}: transformation moet SAME of MIRRORED zijn")
    if g["status"] not in REPEAT_STATUSES:
        e.append(f"{gid}: status {g['status']!r} niet toegestaan")
    if g["representative_pand_id"] in g["applies_to_pand_ids"]:
        e.append(f"{gid}: representative_pand_id hoort niet in applies_to_pand_ids")
    if not g["applies_to_pand_ids"]:
        e.append(f"{gid}: applies_to_pand_ids is leeg")
    if g["status"] == "ACTIVE":
        d = g.get("decision_ref")
        if not d or d.get("decision_type") != "USER_CONFIRMED_REPEAT" or d.get("reviewer", {}).get("reviewer_type") != "human":
            e.append(f"{gid}: ACTIVE vereist decision_ref met decision_type USER_CONFIRMED_REPEAT door een mens")
    elif g.get("decision_ref") is not None and g["status"] == "REPEAT_CANDIDATE":
        e.append(f"{gid}: een REPEAT_CANDIDATE heeft geen decision_ref")
    return e


def repeat_group_usable(g):
    """Alleen ACTIVE + USER_CONFIRMED_REPEAT is bruikbaar; een kandidaat nooit."""
    return g.get("status") == "ACTIVE" and not repeat_group_errors(g)


def repeat_group_candidate(*, repeat_group_id, building_id, component_type, representative_pand_id, applies_to_pand_ids, transformation, evidence_refs):
    """Vision/tekening mag alleen een REPEAT_CANDIDATE voorstellen."""
    g = {"repeat_group_id": repeat_group_id, "building_id": building_id, "component_type": component_type,
         "representative_pand_id": representative_pand_id, "applies_to_pand_ids": sorted(applies_to_pand_ids), "transformation": transformation,
         "evidence_refs": list(evidence_refs), "decision_ref": None, "status": "REPEAT_CANDIDATE"}
    errs = repeat_group_errors(g)
    if errs:
        raise FrameError("; ".join(errs))
    return g


# --------------------------------------------------------------------------
# Bronprioriteit — alleen binnen exact hetzelfde subject
# --------------------------------------------------------------------------

def select_quantity(candidates):
    """candidates: lijst {subject, source, value}. Alle kandidaten moeten EXACT hetzelfde subject hebben; anders FrameError
    (geen winnaar tussen verschillende subjects). Retourneert de kandidaat met de hoogste prioriteit, of None."""
    if not candidates:
        return None
    subjects = {json.dumps(c["subject"], sort_keys=True) for c in candidates}
    if len(subjects) != 1:
        raise FrameError("prioriteit geldt alleen binnen exact hetzelfde subject; verschillende subjects hebben geen automatische winnaar")
    for c in candidates:
        if c["source"] not in QUANTITY_PRIORITY:
            raise FrameError(f"onbekende bron {c['source']!r}")
    return min(candidates, key=lambda c: QUANTITY_PRIORITY.index(c["source"]))


def legacy_fallback_allowed(frame_inventory_state):
    """De legacy appartementfactor (KOZ_FACTOREN) mag alleen als er geen bevestigde/handmatige/tekening-gebaseerde frame-inventaris is."""
    return not frame_inventory_state.get("has_confirmed_manual_or_drawing_inventory", False)


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------

def store_errors(store):
    e = []
    ids = [r["frame_instance_id"] for r in store["instances"]] + [g["frame_group_id"] for g in store["frame_groups"]]
    if len(ids) != len(set(ids)):
        e.append("dubbele frame_instance_id/frame_group_id")
    for r in store["instances"]:
        e += instance_errors(r)
    for g in store["frame_groups"]:
        e += group_errors(g)
    return e


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
