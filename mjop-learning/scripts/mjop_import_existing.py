#!/usr/bin/env python3
"""
mjop_import_existing.py  (BESTAAND MJOP -> STARTREGELS VOOR EEN NIEUW 30-JAARS MJOP, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md.

Zet de geverifieerde posten van één bestaand MJOP (data/verified/<DOC>.json, eigen of van
derden) om naar Maintenance Lines v2 met origin FROM_EXISTING_MJOP. Eén regel per
(element, actie); de planjaren uit het document worden als herkomst bewaard
(origin_source.document_planned_years) en NIET als planned_year overgenomen: een planjaar uit
een oud MJOP is geen actuele beslissing (de horizon-planner doet een voorstel, een mens beslist).

Bedragen: het vermelde bedrag per keer wordt alleen als price_update (historisch bedrag,
expliciet geïndexeerd, status PROPOSED) meegenomen — nooit als effectief bedrag of marktprijs.
Elke regel krijgt de vlag NOT_INSPECTED: een oud MJOP is geen actuele inspectie.

Documenten van derden (geen elementcode) worden gewoon ingelezen; regels zonder code krijgen
ELEMENT_CODE_MISSING en regels zonder genormaliseerde actie ACTION_UNKNOWN.
"""
import os
import sys
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_maintenance_line_v2 as line_v2  # noqa: E402
import mjop_price_index  # noqa: E402


def _v(field):
    if isinstance(field, dict):
        return field.get("normalized_value", field.get("value"))
    return field


def _orig(field):
    return field.get("original_value") if isinstance(field, dict) else None


def _doc_value(doc, key):
    f = (doc.get("document_level_values") or {}).get(key)
    return f.get("value") if isinstance(f, dict) else f


def vat_basis(statement):
    s = (statement or "").lower()
    if "exclusief" in s or "excl." in s:
        return "exclusive"
    if "inclusief" in s or "incl." in s:
        return "inclusive"
    return None


def price_level_year(doc):
    """Jaar uit price_level_date (d-m-jjjj); anders None (niet afleiden uit inspectiedatum)."""
    raw = _doc_value(doc, "price_level_date")
    if not raw:
        return None
    tail = str(raw).strip().split("-")[-1]
    return int(tail) if tail.isdigit() and len(tail) == 4 else None


def _positive(q):
    try:
        d = Decimal(str(q))
    except (InvalidOperation, TypeError):
        return None
    return format(d, "f") if d > 0 else None


def _groups(doc):
    groups = OrderedDict()
    for a in doc["maintenance_actions"]:
        action = _v(a["action"])
        text = _orig(a["action"])
        key = (a["element_id"], action if action else f"text:{(text or '').strip().lower()}")
        groups.setdefault(key, []).append(a)
    return groups


def import_document(doc, *, mjop_id, target_price_year, index, line_prefix=None):
    """Geeft (lines, summary). Puur: leest alleen het meegegeven document."""
    elements = {e["element_id"]: e for e in doc["elements"]}
    construction_year = _v(doc["building"].get("construction_year"))
    vat_statement = _doc_value(doc, "vat_statement")
    base_year = price_level_year(doc)
    prefix = line_prefix or mjop_id
    lines, summary = [], {"document_id": doc["document_id"], "source_actions": len(doc["maintenance_actions"]),
                          "lines": 0, "without_element_code": 0, "without_action": 0, "quantity_conflicts": 0,
                          "amounts_differ": 0, "price_level_year": base_year, "vat_statement": vat_statement}
    for n, ((element_id, _), actions) in enumerate(_groups(doc).items(), start=1):
        el = elements.get(element_id, {})
        code = _v(el.get("element_code"))
        action = _v(actions[0]["action"])
        units = {_v(a["unit"]) for a in actions}
        quantities = {_positive(_v(a["quantity"])) for a in actions}
        flags = ["NOT_INSPECTED"]
        if not code:
            flags.append("ELEMENT_CODE_MISSING")
            summary["without_element_code"] += 1
        if not action:
            flags.append("ACTION_UNKNOWN")
            summary["without_action"] += 1
        quantity = quantities.pop() if len(quantities) == 1 else None
        unit = units.pop() if len(units) == 1 else None
        summary["quantity_conflicts"] += quantity is None and len({_v(a["quantity"]) for a in actions}) > 1
        years = [a["planned_year"].get("value") for a in actions if isinstance(a["planned_year"].get("value"), int)]
        src = line_v2.origin_source(
            "DOCUMENT", document_id=doc["document_id"],
            pages=[a["source_page"] for a in actions if isinstance(a.get("source_page"), int)],
            source_action_ids=[a["action_id"] for a in actions], source_element_id=element_id,
            document_planned_years=years)
        line = line_v2.new_line(
            f"{prefix}-L{n:04d}", mjop_id, element_id, origin="FROM_EXISTING_MJOP", origin_source=src,
            planner_flags=flags,
            element_code_internal=code, object_description=_v(el.get("element_name")),
            action_normalized=action, action_text=_orig(actions[0]["action"]),
            unit_normalized=unit, unit_text=_orig(actions[0]["unit"]),
            material_normalized=_v(el.get("material")), material_text=_orig(el.get("material")),
            vat_basis=vat_basis(vat_statement), quantity=quantity,
            context={"construction_year": construction_year, "location": _v(el.get("location"))})
        amounts = {a["total_cost_as_stated"] for a in actions if a.get("total_cost_as_stated") not in (None, "")}
        reason = "SOURCE_AMOUNTS_DIFFER" if len(amounts) > 1 else None
        summary["amounts_differ"] += reason is not None
        first = min(actions, key=lambda a: (a["planned_year"].get("value") or 0))
        pu = mjop_price_index.price_update(
            source_document_id=doc["document_id"], source_action_id=first["action_id"],
            source_total=amounts.pop() if len(amounts) == 1 else None, source_vat_statement=vat_statement,
            base_year=base_year, target_year=target_price_year, index=index, not_computed_reason=reason)
        lines.append(line_v2.set_price_update(line, pu))
    summary["lines"] = len(lines)
    return lines, summary
