"""Bruto Quantity Model v2: contract-laden en validatie (alleen lezen).

Laadt de v2-schema's en -vocabulaires uit de repository en valideert records tegen schema en semantiek
(scripts/bruto_quantity_core.py). Schrijft niets, leest geen v1-store en kent geen netwerk.
"""
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bruto_quantity_core as core  # noqa: E402

SCHEMA_DIR = ROOT / "schemas"
VOCAB_DIR = ROOT / "vocabularies"
SCHEMA_NAMES = ("bruto_dimension_v2", "bruto_frame_type_v2", "bruto_observation_v2", "bruto_quantity_object_v2", "bruto_quantity_state_v2")
VOCAB_NAMES = ("bruto_quantity_concepts_v2", "bruto_quantity_actions_v2")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_schema(name):
    return load_json(SCHEMA_DIR / f"{name}.schema.json")


def load_vocabulary(name):
    return load_json(VOCAB_DIR / f"{name}.json")


def _store():
    return {f"{n}.schema.json": load_schema(n) for n in SCHEMA_NAMES}


def schema_errors(instance, name):
    schema = load_schema(name)
    store = _store()
    resolver = jsonschema.RefResolver(base_uri=f"{name}.schema.json", referrer=schema, store=store)
    validator = jsonschema.Draft7Validator(schema, resolver=resolver)
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in validator.iter_errors(instance))


def dimension_errors(dim):
    errs = schema_errors(dim, "bruto_dimension_v2")
    return errs or core.dimension_problems(dim)


def type_errors(t):
    errs = schema_errors(t, "bruto_frame_type_v2")
    if errs:
        return errs
    if t["material"] != "UNKNOWN" and not t.get("material_basis"):
        errs.append("materiaal bekend maar material_basis ontbreekt")
    ids = [r["reference_id"] for r in t["reference_dimensions"]] + [v["variant_id"] for v in t["variants"]]
    if len(set(ids)) != len(ids):
        errs.append("reference_id/variant_id niet uniek binnen het type")
    for r in t["reference_dimensions"]:
        if r["dimension"]["dimension_status"] == "REFERENCE_DERIVED_ESTIMATE":
            errs.append(f"{r['reference_id']}: een referentiemaat mag geen schatting zijn (geen schattingsketens)")
        errs += [f"{r['reference_id']}: {e}" for e in core.dimension_problems(r["dimension"])]
    for v in t["variants"]:
        errs += [f"{v['variant_id']}: {e}" for e in core.dimension_problems(v["dimension"])]
    return errs


def observation_errors(o):
    return schema_errors(o, "bruto_observation_v2")


def object_errors(o):
    errs = schema_errors(o, "bruto_quantity_object_v2")
    return errs or core.dimension_problems(o["dimension"])


def build_checked_state(types, objects, observations, **kw):
    """Valideert alle invoer tegen schema en bouwt daarna de staat; de staat wordt opnieuw gevalideerd."""
    errs = []
    errs += [f"type {t.get('type_id')}: {e}" for t in types for e in type_errors(t)]
    errs += [f"observatie {o.get('observation_id')}: {e}" for o in observations for e in observation_errors(o)]
    errs += [f"object {o.get('object_id')}: {e}" for o in objects for e in object_errors(o)]
    if errs:
        raise core.BrutoError("INPUT_INVALID", "; ".join(errs))
    state = core.build_state(types, objects, observations, **kw)
    problems = state_errors(state)
    if problems:
        raise core.BrutoError("OUTPUT_CONTRACT_VIOLATION", "; ".join(problems))
    return state


def state_errors(state):
    errs = schema_errors(state, "bruto_quantity_state_v2")
    if errs:
        return errs
    for lay in ("PROVISIONAL_UNIQUE", "CONFIRMED", "ESTIMATED"):
        a = state["areas"][lay]
        for cls in ("known", "estimated"):
            c = a[cls]
            if c["area_m2_presented"] is not None:
                from decimal import Decimal
                parts = sum((Decimal(g["area_m2_presented"]) for g in c["by_type_group"]), Decimal(0))
                if parts != Decimal(c["area_m2_presented"]):
                    errs.append(f"{lay}.{cls}: gepresenteerde subtotalen tellen niet op tot het totaal")
    if state["layers"]["CONFIRMED"]["layer_status"] == "BLOCKED_NO_VERIFIED_APPROVAL_SOURCE" and state["layers"]["CONFIRMED"]["object_ids"]:
        errs.append("CONFIRMED moet leeg zijn zolang er geen geverifieerde goedkeuringsbron is")
    ids = [i for lay in core.LAYERS for i in state["layers"][lay]["object_ids"]]
    if len(set(ids)) != len(ids):
        errs.append("een object staat in meer dan een laag (dubbeltelling)")
    return errs
