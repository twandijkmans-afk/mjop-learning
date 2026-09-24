#!/usr/bin/env python3
"""
mjop_maintenance_line.py  (DOMEINMODEL: ÉÉN ONDERHOUDSREGEL VAN EEN NIEUW MJOP, v1)

Model: schemas/mjop_maintenance_line.schema.json; documentatie:
docs/mjop_maintenance_line_v1.md. Niet te verwarren met
maintenance_action.schema.json (historische, geëxtraheerde posten).

Verantwoordelijkheden:
  - deze module: de toestand van een MJOP-regel (wat, hoeveel, planning,
    status, bedrag + herkomst) aanmaken, bijwerken en valideren;
  - scripts/mjop_kengetal_workflow.py: normalisatie -> matching -> menselijke
    beslissing -> effectief bedrag. Deze module roept die niet zelf aan en
    herhaalt geen matchinglogica; to_workflow_input() levert de input en
    apply_workflow_result() neemt het resultaat over.

Alle functies geven een NIEUWE regel terug (de invoer wordt niet gemuteerd) en
valideren het resultaat. Er is geen opslag: persistentie hoort bij het
(nog niet in deze repository aanwezige) planbeheer.
Geen indexatie, schaalcorrectie, planningslogica, score of learning loop.
"""
import copy
import json
import os
import sys
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_kengetal_workflow  # noqa: E402

LINE_VERSION = "mjop_maintenance_line_v1"
DISPLAY = Decimal("0.01")   # alleen presentatie; zelfde als de workflow (ROUND_HALF_EVEN)
CONTEXT_FIELDS = ("building_type", "construction_year", "location", "condition_defect", "maintenance_type")
# velden die het matchresultaat bepalen: wijzigen maakt een kengetalbedrag ongeldig
MATCH_INPUT_FIELDS = ("element_code_internal", "object_description", "action_normalized", "action_text",
                      "unit_normalized", "unit_text", "material_normalized", "material_text", "material_source",
                      "vat_basis", "price_level_requested", "quantity", "context")
PLANNING_FIELDS = ("planned_year", "cycle_years", "last_maintenance_year", "last_replacement_year")
USER_EDITABLE_FIELDS = MATCH_INPUT_FIELDS + PLANNING_FIELDS
SYSTEM_DERIVED_FIELDS = ("line_status", "price_status", "kengetal_match", "financial", "provenance",
                         "proposed_planned_year")
WORKFLOW_AMOUNT_SOURCE = {"SYSTEM_KENGETAL_ACCEPTED": "SYSTEM_KENGETAL",
                          "HUMAN_SELECTED_KENGETAL": "HUMAN_SELECTED_KENGETAL",
                          "HUMAN_ADJUSTMENT": "HUMAN_ADJUSTMENT"}
WORKFLOW_PRICE_STATUS = {"ACCEPTED": "HUMAN_ACCEPTED", "ADJUSTED": "HUMAN_ADJUSTED", "REJECTED": "REJECTED",
                         "MATCH_PENDING_DECISION": "SYSTEM_PROPOSED", "NO_KENGETAL": "NO_AMOUNT"}
DEFINITIVE = ("HUMAN_ACCEPTED", "HUMAN_ADJUSTED", "MANUALLY_SET")


class LineError(ValueError):
    """Ongeldige MJOP-regel of ongeldige bewerking."""


def schema_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas",
                        "mjop_maintenance_line.schema.json")


SCHEMA = json.load(open(schema_path(), encoding="utf-8"))


def display(value):
    return None if value is None else format(Decimal(value).quantize(DISPLAY), "f")


def decimal_str(value):
    if value is None or value == "":
        return None
    try:
        return format(Decimal(str(value)), "f")
    except InvalidOperation as e:
        raise LineError(f"geen geldig getal: {value!r}") from e


def empty_financial():
    return {"amount_source": None, "unit_amount": None, "unit_amount_display": None, "unit": None,
            "effective_total": None, "effective_total_display": None,
            "total_not_computed_reason": "NO_EFFECTIVE_AMOUNT", "price_level": None, "vat_basis": None,
            "indexation": "none"}


def total(amount, amount_unit, quantity, line_unit):
    """Zelfde regel als de workflow: amount x quantity, exact Decimal, alleen bij positieve
    quantity en exact dezelfde eenheid. Geeft (total, reason)."""
    if amount is None:
        return None, "NO_EFFECTIVE_AMOUNT"
    if quantity is None:
        return None, "QUANTITY_MISSING"
    if amount_unit != line_unit:
        return None, "UNIT_MISMATCH"
    if Decimal(quantity) <= 0:
        return None, "QUANTITY_NOT_POSITIVE"
    return format(Decimal(amount) * Decimal(quantity), "f"), None


def line_status_for(price_status, kengetal_match):
    if price_status in DEFINITIVE:
        return "READY"
    if kengetal_match and kengetal_match["workflow_status"] in ("MATCH_PENDING_DECISION", "REVIEW_REQUIRED"):
        return "REVIEW_REQUIRED"
    return "DRAFT"


# --------------------------------------------------------------------------
# Validatie
# --------------------------------------------------------------------------

def line_errors(line):
    """Schema + controles die het schema niet kan uitdrukken."""
    import jsonschema
    errors = [f"{'/'.join(str(x) for x in e.path) or '(regel)'}: {e.message}"
              for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(line)]
    if errors:
        return errors
    f, km = line["financial"], line["kengetal_match"]
    if f["unit_amount"] is not None and f["unit"] != line["unit_normalized"]:
        errors.append(f"eenheid van het bedrag ({f['unit']}) is niet de eenheid van de regel "
                      f"({line['unit_normalized']}); geen conversie")
    expected_total, reason = total(f["unit_amount"], f["unit"], line["quantity"], line["unit_normalized"])
    if f["effective_total"] != expected_total or f["total_not_computed_reason"] != reason:
        errors.append("effective_total past niet bij unit_amount x quantity")
    if f["unit_amount_display"] != display(f["unit_amount"]) or f["effective_total_display"] != display(f["effective_total"]):
        errors.append("display-waarden passen niet bij de exacte waarden")
    if line["manual_amount"] is not None:
        ma = line["manual_amount"]
        if ma["unit"] != line["unit_normalized"]:
            errors.append("eenheid van het handmatige bedrag is niet de eenheid van de regel")
        if line["price_status"] == "MANUALLY_SET" and f["unit_amount"] != ma["amount"]:
            errors.append("unit_amount wijkt af van het handmatige bedrag")
    if line["price_status"] != "MANUALLY_SET" and line["manual_amount"] is not None:
        errors.append("manual_amount aanwezig maar price_status is niet MANUALLY_SET")
    if km is not None and line["price_status"] != "MANUALLY_SET":
        if WORKFLOW_PRICE_STATUS.get(km["workflow_status"]) not in (line["price_status"], None) and not (
                km["workflow_status"] == "REVIEW_REQUIRED" and line["price_status"] in ("SYSTEM_PROPOSED", "NO_AMOUNT")):
            errors.append("price_status past niet bij het toegepaste workflowresultaat")
    if km is None and line["price_status"] in ("SYSTEM_PROPOSED", "HUMAN_ACCEPTED", "HUMAN_ADJUSTED", "REJECTED"):
        errors.append(f"price_status {line['price_status']} zonder workflowresultaat")
    if line["line_status"] != line_status_for(line["price_status"], km):
        errors.append(f"line_status {line['line_status']} past niet bij price_status {line['price_status']}")
    if line["proposed_planned_year"] is not None:
        errors.append("proposed_planned_year wordt in v1 niet gevuld")
    return errors


def validated(line):
    errors = line_errors(line)
    if errors:
        raise LineError("; ".join(errors))
    return line


# --------------------------------------------------------------------------
# Aanmaken en bewerken
# --------------------------------------------------------------------------

def new_line(maintenance_line_id, mjop_id, object_id, **fields):
    """Nieuwe regel zonder bedrag (DRAFT / NO_AMOUNT). Onbekende jaren blijven null; het
    bouwjaar (context.construction_year) wordt nooit als onderhouds- of vervangingsjaar gebruikt."""
    unknown = set(fields) - set(USER_EDITABLE_FIELDS)
    if unknown:
        raise LineError(f"niet door de gebruiker te zetten of onbekend: {sorted(unknown)}")
    context = {k: None for k in CONTEXT_FIELDS}
    context.update(fields.pop("context", None) or {})
    line = {
        "maintenance_line_id": maintenance_line_id, "mjop_id": mjop_id, "object_id": object_id,
        "line_version": LINE_VERSION,
        **{k: None for k in MATCH_INPUT_FIELDS if k != "context"},
        "context": context,
        **{k: None for k in PLANNING_FIELDS},
        "proposed_planned_year": None,
        "line_status": "DRAFT", "price_status": "NO_AMOUNT",
        "kengetal_match": None, "manual_amount": None, "financial": empty_financial(), "provenance": None,
    }
    for k, v in fields.items():
        line[k] = decimal_str(v) if k == "quantity" else v
    return validated(line)


def update_user_fields(line, **changes):
    """Alleen user-editable velden. Wijzigt een veld dat het matchresultaat bepaalt, dan vervalt een
    kengetal-afgeleid bedrag (workflow opnieuw draaien); een handmatig bedrag blijft, tenzij de
    eenheid verandert. Planningvelden raken het bedrag niet."""
    forbidden = set(changes) - set(USER_EDITABLE_FIELDS)
    if forbidden:
        raise LineError(f"system-derived of onbekende velden kunnen niet worden aangepast: {sorted(forbidden)}")
    new = copy.deepcopy(line)
    for k, v in changes.items():
        if k == "context":
            new["context"].update(v)
        else:
            new[k] = decimal_str(v) if k == "quantity" else v
    match_changed = any(new[k] != line[k] for k in MATCH_INPUT_FIELDS)
    if match_changed:
        new["kengetal_match"], new["provenance"] = None, None
        if new["price_status"] == "MANUALLY_SET" and new["manual_amount"]["unit"] == new["unit_normalized"]:
            ma = new["manual_amount"]
            new["financial"] = manual_financial(ma, new["quantity"], new["unit_normalized"])
        else:
            new["manual_amount"], new["price_status"], new["financial"] = None, "NO_AMOUNT", empty_financial()
    new["line_status"] = line_status_for(new["price_status"], new["kengetal_match"])
    return validated(new)


def to_workflow_input(line):
    """Input-object v1 voor scripts/mjop_kengetal_workflow.py (zelfde velden en betekenis)."""
    item = {"object_id": line["object_id"]}
    for k in ("element_code_internal", "object_description", "action_normalized", "action_text", "unit_normalized",
              "unit_text", "material_normalized", "material_text", "material_source", "quantity",
              "price_level_requested", "vat_basis"):
        if line[k] is not None:
            item[k] = line[k]
    for k, v in line["context"].items():
        if v is not None:
            item[k] = v
    return item


def apply_workflow_result(line, workflow_result):
    """Neemt het resultaat van mjop_kengetal_workflow.run() over. Het resultaat moet bij exact deze
    regel horen (zelfde input). Een handmatig bedrag blijft leidend; alleen kengetal_match en
    provenance worden dan bijgewerkt."""
    if workflow_result["input"] != to_workflow_input(line):
        raise LineError("workflowresultaat hoort niet bij deze regel (andere input)")
    mr, cur, fin = workflow_result["match_result"], workflow_result["current_decision"], workflow_result["financial_result"]
    new = copy.deepcopy(line)
    new["kengetal_match"] = {
        "workflow_status": workflow_result["status"], "match_result_id": mr["match_result_id"],
        "match_status": mr["final_status"], "match_reasons": list(mr["reasons"]),
        "kengetal_id": mr["candidate_kengetal_id"], "system_candidate_amount": fin["system_candidate_amount"],
        "human_match_decision_id": cur["active_decision_id"], "decision_status": cur["status"],
        "human_selected_kengetal_id": fin["human_selected_kengetal_id"]}
    p = workflow_result["provenance"]
    new["provenance"] = {"workflow_result_id": workflow_result["workflow_result_id"],
                         "match_result_sha256": p["match_result_sha256"],
                         "decision_store_sha256": p["decision_store_sha256"],
                         "rule_versions": dict(p["rule_versions"]), "input_hashes": p["input_hashes"]}
    if new["price_status"] != "MANUALLY_SET":
        status = workflow_result["status"]
        new["price_status"] = WORKFLOW_PRICE_STATUS.get(status) or (
            "SYSTEM_PROPOSED" if mr["candidate_kengetal_id"] else "NO_AMOUNT")
        if fin["effective_amount"] is not None:
            new["financial"] = {
                "amount_source": WORKFLOW_AMOUNT_SOURCE[fin["effective_amount_source"]],
                "unit_amount": fin["effective_amount"], "unit_amount_display": fin["effective_amount_display"],
                "unit": fin["effective_amount_unit"], "effective_total": fin["effective_total"],
                "effective_total_display": fin["effective_total_display"],
                "total_not_computed_reason": fin["total_not_computed_reason"],
                "price_level": fin["price_levels"], "vat_basis": line["vat_basis"], "indexation": "none"}
        else:
            new["financial"] = empty_financial()
    new["line_status"] = line_status_for(new["price_status"], new["kengetal_match"])
    return validated(new)


def manual_financial(manual, quantity, line_unit):
    t, reason = total(manual["amount"], manual["unit"], quantity, line_unit)
    return {"amount_source": "MANUAL_AMOUNT", "unit_amount": manual["amount"], "unit_amount_display": display(manual["amount"]),
            "unit": manual["unit"], "effective_total": t, "effective_total_display": display(t),
            "total_not_computed_reason": reason, "price_level": {"manual_price_level": manual["price_level"]},
            "vat_basis": manual["vat_basis"], "indexation": "none"}


def set_manual_amount(line, amount, unit, price_level, vat_basis, reason):
    """Expliciet handmatig bedrag (bron MANUAL_AMOUNT) in de eenheid van de regel. Wordt geen
    historische kennis. Kengetal_match/provenance blijven als informatie bewaard."""
    amount = decimal_str(amount)
    if amount is None or Decimal(amount) < 0:
        raise LineError("handmatig bedrag moet een niet-negatief getal zijn")
    if unit != line["unit_normalized"]:
        raise LineError(f"eenheid {unit!r} is niet de eenheid van de regel ({line['unit_normalized']!r}); geen conversie")
    new = copy.deepcopy(line)
    new["manual_amount"] = {"amount": amount, "unit": unit, "price_level": price_level, "vat_basis": vat_basis,
                            "reason": reason, "source": "MANUAL_AMOUNT"}
    new["price_status"] = "MANUALLY_SET"
    new["financial"] = manual_financial(new["manual_amount"], new["quantity"], new["unit_normalized"])
    new["line_status"] = line_status_for(new["price_status"], new["kengetal_match"])
    return validated(new)


def clear_manual_amount(line):
    """Verwijdert een handmatig bedrag. De regel komt terug in NO_AMOUNT / DRAFT zonder effectief
    bedrag of totaal. Er is geen fallback naar een eerder kengetal of bedrag en er wordt geen
    matching uitgevoerd: ook kengetal_match en provenance vervallen, zodat een kengetal alleen
    terugkomt door de workflow opnieuw te draaien."""
    if line["price_status"] != "MANUALLY_SET":
        raise LineError("er is geen handmatig bedrag om te wissen")
    new = copy.deepcopy(line)
    new["manual_amount"], new["kengetal_match"], new["provenance"] = None, None, None
    new["price_status"], new["financial"] = "NO_AMOUNT", empty_financial()
    new["line_status"] = line_status_for(new["price_status"], new["kengetal_match"])
    return validated(new)


def run_workflow_for_line(line, decision_store, context=None, root=None):
    """Gemak: to_workflow_input -> mjop_kengetal_workflow.run -> apply_workflow_result."""
    result = mjop_kengetal_workflow.run(to_workflow_input(line), decision_store, context, root=root)
    return apply_workflow_result(line, result), result
