#!/usr/bin/env python3
"""
mjop_defects.py  (GEBREKEN ALS EENMALIGE B-POSTEN + HERSTART VAN HET RITME, v1)

Schema: schemas/defect_input.schema.json; documentatie: docs/mjop_actualisatie_light_v1.md.

Gebreken worden ingevoerd door een adviseur (geen AI, geen afleiding uit een oud MJOP: een oud MJOP
is geen inspectie). Elk gebrek:
  - wordt een eenmalige B-post in OPrognose (cyclus 0, urgentie, eventueel NEN 2767-code) in het
    opgegeven jaar; het wacht nooit op een koppeling of cyclus;
  - telt als definitieve uitgave in het reservefonds (eigen prijspeil);
  - kan het planmatige ritme herstarten (restart.action): het gebreksjaar wordt dan het laatste
    uitvoeringsjaar van die handeling bij dat element (last_replacement_year bij 'replace', anders
    last_maintenance_year). De planner en de koppelingen rekenen vanaf daar verder (vlag
    RESTARTED_BY_DEFECT). Bestaat de regel niet, dan geldt het jaar voor een eventueel toegevoegde
    vervanging (last_replacement_years van de planner).
"""
import copy
import json
import os
import sys
from decimal import ROUND_HALF_EVEN, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_maintenance_line_v2 as line_v2  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "defect_input.schema.json"), encoding="utf-8"))
CENT = Decimal("0.01")


class DefectError(ValueError):
    pass


def validate(data, doc=None):
    import jsonschema
    errors = [f"{'/'.join(str(x) for x in e.path) or '(invoer)'}: {e.message}"
              for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(data)]
    if errors:
        raise DefectError("; ".join(errors))
    ids, elements = set(), {e["element_id"] for e in (doc or {}).get("elements", [])}
    for d in data["defects"]:
        if d["id"] in ids:
            errors.append(f"dubbel gebrek-id {d['id']}")
        ids.add(d["id"])
        if not d["element_id"] and not d["element_code"]:
            errors.append(f"{d['id']}: element_id of element_code is verplicht")
        if doc is not None and d["element_id"] and d["element_id"] not in elements:
            errors.append(f"{d['id']}: element {d['element_id']} staat niet in {doc['document_id']}")
    if errors:
        raise DefectError("; ".join(errors))
    return data


def load(path, doc=None):
    return validate(json.load(open(path, encoding="utf-8")), doc)


def total(defect):
    if defect["unit_price"] is None:
        return None
    return (Decimal(defect["quantity"]) * Decimal(defect["unit_price"])).quantize(CENT, rounding=ROUND_HALF_EVEN)


def _matches(line, d, action):
    if line["action_normalized"] != action:
        return False
    if d["element_id"]:
        return line["object_id"] == d["element_id"]
    return line["element_code_internal"] == d["element_code"]


def apply_restarts(lines, data):
    """Vóór de planner: zet het gebreksjaar als laatste uitvoeringsjaar. Geeft (regels, extra
    last_replacement_years voor toe te voegen vervangingen, ids van herstarte regels)."""
    out, by_code, restarted = list(lines), {}, set()
    for d in data["defects"]:
        if not d["restart"]:
            continue
        action = d["restart"]["action"]
        hit = False
        for i, l in enumerate(out):
            if _matches(l, d, action) and l["planning_status"] not in line_v2.HUMAN_PLANNED + ("REJECTED",):
                field = "last_replacement_year" if action == "replace" else "last_maintenance_year"
                out[i] = line_v2.update_user_fields(l, **{field: d["year"]})
                restarted.add(l["maintenance_line_id"])
                hit = True
        if not hit and action == "replace" and d["element_code"]:
            by_code[d["element_code"]] = d["year"]
    return out, by_code, restarted


def mark_restarted(lines, restarted):
    """Na de planner (en koppelingen): vlag RESTARTED_BY_DEFECT op de herstarte regels."""
    out = []
    for l in lines:
        if l["maintenance_line_id"] in restarted and l["planning_status"] in ("PROPOSED", "NOT_PLANNED"):
            new = copy.deepcopy(l)
            new["planner_flags"] = sorted(set(new["planner_flags"]) | {"RESTARTED_BY_DEFECT"})
            l = line_v2.validated(new)
        out.append(l)
    return out


def fund_expenses(data):
    """Definitieve uitgaven voor het reservefonds."""
    return [{"id": d["id"], "year": d["year"], "amount": total(d), "price_level_year": data["price_level_year"]}
            for d in data["defects"] if total(d) is not None]
