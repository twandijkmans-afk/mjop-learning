#!/usr/bin/env python3
"""
mjop_kengetal_workflow.py  (MJOP-REGEL -> MATCH -> MENSELIJKE BESLISSING -> GEBRUIKT BEDRAG, workflow v1)

Integratielaag die één MJOP-onderhoudsregel door de bestaande lagen haalt:
  input-object v1 (docs/matching_rules_v1.md)
    -> normalisatie + retrieval + scope-check  : scripts/match_kengetal.py (match)
    -> actuele menselijke beslissing           : scripts/human_match_review.py (current_decision)
    -> gebruikt bedrag                         : alleen als de actieve beslissing dat rechtvaardigt
Deze module implementeert zelf geen matching- of beslisregels, leest alleen en
schrijft niets (geen historische data, geen kengetallen, geen beslissingen).

Status:
  NO_KENGETAL            match NO_SUITABLE_KENGETAL en geen beslissing
  REVIEW_REQUIRED        match HUMAN_REVIEW_REQUIRED en geen beslissing
  MATCH_PENDING_DECISION match CANDIDATE_FOUND en geen beslissing (nog niet geaccepteerd)
  ACCEPTED / ADJUSTED / REJECTED   actieve menselijke beslissing (leidend)
Een integriteitsfout in de beslissingen (bijv. twee ACTIVE records, of een record
dat niet bij dit matchresultaat past) laat de workflow expliciet falen.

Bedragen (Decimal, geen tussentijdse afronding; display = 0.01 ROUND_HALF_EVEN):
  system_candidate_amount  kengetalwaarde van het voorgestelde kengetal (alleen informatie)
  human_selected_amount    ACCEPT: kengetal van het voorstel; ADJUST: het aangepaste bedrag,
                           anders de waarde van het door de mens gekozen kengetal; REJECT: null
  effective_amount         = human_selected_amount bij ACCEPTED/ADJUSTED, anders null
  effective_total          = effective_amount x quantity, alleen bij een positieve quantity en
                           dezelfde eenheid. Geen schaalcorrectie, geen indexatie.

Gebruik:
    python scripts/mjop_kengetal_workflow.py --input item.json [--decisions store.json] [--out result.json]
"""
import argparse
import hashlib
import json
import os
import sys
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import human_match_review  # noqa: E402
import match_kengetal  # noqa: E402

WORKFLOW_VERSION = "mjop_kengetal_workflow_v1"
DISPLAY = Decimal("0.01")
MATCH_STATUS = {"NO_SUITABLE_KENGETAL": "NO_KENGETAL", "HUMAN_REVIEW_REQUIRED": "REVIEW_REQUIRED",
                "CANDIDATE_FOUND": "MATCH_PENDING_DECISION"}


class WorkflowError(Exception):
    """De workflow kan geen betrouwbaar resultaat geven (integriteitsfout in de onderliggende lagen)."""


def display(value):
    return None if value is None else format(Decimal(value).quantize(DISPLAY), "f")


def paths(root):
    review = human_match_review.paths(root)
    return {"schema": os.path.join(root, "schemas", "mjop_kengetal_workflow_result.schema.json"),
            "store": review["store"]}


def kengetal_by_id(kengetallen_doc, kengetal_id):
    return next((k for k in kengetallen_doc["kengetallen"] if k["kengetal_id"] == kengetal_id), None)


def decision_view(decision_store, match_result, kengetallen_doc):
    """Actuele beslissing via human_match_review.current_decision; controleert dat een
    actief record exact bij dit matchresultaat hoort. Integriteitsfout -> WorkflowError."""
    try:
        cur = human_match_review.current_decision(decision_store, match_result["match_result_id"])
    except human_match_review.IntegrityError as e:
        raise WorkflowError(str(e)) from e
    rec = cur["active_record"]
    if rec is not None:
        errors = human_match_review.record_errors(rec, kengetallen_doc)
        if rec["match_result_sha256"] != human_match_review.canonical_sha256(match_result):
            errors.append(f"{rec['decision_id']}: beslissing hoort bij een ander matchresultaat (hash wijkt af)")
        if errors:
            raise WorkflowError("; ".join(errors))
    return {"status": cur["status"],
            "active_decision_id": rec["decision_id"] if rec else None,
            "decision": rec["decision"] if rec else None,
            "chosen_kengetal_id": rec["chosen_kengetal_id"] if rec else None,
            "adjustment": rec["adjustment"] if rec else None,
            "decision_reason": rec["decision_reason"] if rec else None,
            "decision_caveats": list(rec["decision_caveats"]) if rec else [],
            "reviewer": rec["reviewer"] if rec else None,
            "history": list(cur["history"])}


def financial(match_result, decision, kengetallen_doc):
    unit = match_result["input_normalized"]["unit"]
    quantity = match_result["input_normalized"]["quantity"]
    candidate = match_result["candidate_kengetal_id"]
    system_amount = match_result["historical_range"]["value_exact"] if match_result["historical_range"] else None

    selected_id, selected_amount, amount_unit, source, amount_basis, price_levels = None, None, None, None, None, None
    if decision["status"] == "ACCEPTED":
        k = kengetal_by_id(kengetallen_doc, decision["chosen_kengetal_id"])
        selected_id, selected_amount, amount_unit = k["kengetal_id"], k["value_exact"], k["unit"]
        source, price_levels = "SYSTEM_KENGETAL_ACCEPTED", k["price_levels"]
    elif decision["status"] == "ADJUSTED":
        adj = decision["adjustment"]
        selected_id = adj["kengetal_id"]
        if adj["amount_per_unit_exact"] is not None:
            selected_amount, amount_unit, source = adj["amount_per_unit_exact"], adj["unit"], "HUMAN_ADJUSTMENT"
            amount_basis = adj["amount_basis"]
        else:
            k = kengetal_by_id(kengetallen_doc, adj["kengetal_id"])
            selected_amount, amount_unit, source = k["value_exact"], k["unit"], "HUMAN_SELECTED_KENGETAL"
            price_levels = k["price_levels"]
    effective = selected_amount if decision["status"] in ("ACCEPTED", "ADJUSTED") else None

    total, reason, calculation = None, None, None
    if effective is None:
        reason = "NO_EFFECTIVE_AMOUNT"
    elif quantity is None:
        reason = "QUANTITY_MISSING"
    elif amount_unit != unit:
        reason = "UNIT_MISMATCH"
    else:
        try:
            q = Decimal(quantity)
        except InvalidOperation:
            q = Decimal(0)
        if q <= 0:
            reason = "QUANTITY_NOT_POSITIVE"
        else:
            total = format(Decimal(effective) * q, "f")
            calculation = f"effective_amount ({effective} per {unit}) x quantity ({quantity} {unit}); exact Decimal"
    return {
        "unit": unit, "quantity": quantity,
        "system_candidate_kengetal_id": candidate, "system_candidate_amount": system_amount,
        "system_candidate_amount_display": display(system_amount),
        "human_selected_kengetal_id": selected_id, "human_selected_amount": selected_amount,
        "effective_amount": effective, "effective_amount_display": display(effective),
        "effective_amount_unit": amount_unit if effective is not None else None,
        "effective_amount_source": source if effective is not None else None,
        "effective_total": total, "effective_total_display": display(total),
        "total_not_computed_reason": reason, "calculation": calculation, "indexation": "none",
        "price_levels": price_levels if price_levels is not None else match_result["price_levels"],
        "amount_basis": amount_basis,
    }


def run(raw_input, decision_store, context=None, root=None):
    """Kern: dezelfde input, datasets en beslissingen geven hetzelfde resultaat (geen tijd of willekeur)."""
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = context or match_kengetal.load_context(root)
    kengetallen_doc = ctx[0]
    match_result = match_kengetal.match(root, raw_input, ctx)
    decision = decision_view(decision_store, match_result, kengetallen_doc)
    status = MATCH_STATUS[match_result["final_status"]] if decision["status"] == "NO_DECISION" else decision["status"]
    match_sha = human_match_review.canonical_sha256(match_result)
    result = {
        "workflow_result_id": None,
        "workflow_version": WORKFLOW_VERSION,
        "status": status,
        "input": raw_input,
        "normalization": match_result["input_normalized"],
        "match_result": match_result,
        "current_decision": decision,
        "financial_result": financial(match_result, decision, kengetallen_doc),
        "caveats": {"match_reasons": list(match_result["reasons"]),
                    "match_caveats": list(match_result["caveats"]["match_caveats"]),
                    "kengetal_decision_caveats": dict(match_result["caveats"]["decision_caveats"]),
                    "kengetal_observation_caveats": list(match_result["caveats"]["observation_caveats"]),
                    "human_decision_caveats": list(decision["decision_caveats"])},
        "provenance": {"match_result_id": match_result["match_result_id"], "match_result_sha256": match_sha,
                       "active_decision_id": decision["active_decision_id"],
                       "decision_store_sha256": human_match_review.canonical_sha256(decision_store),
                       "rule_versions": {"workflow_version": WORKFLOW_VERSION,
                                         "matching_rule_version": match_result["rule_version"],
                                         "kengetallen_rule_version": match_result["kengetallen_rule_version"],
                                         "human_match_review_version": human_match_review.REVIEW_VERSION},
                       "input_hashes": match_result["input_hashes"]},
    }
    result["workflow_result_id"] = "WF-" + human_match_review.canonical_sha256(
        {"workflow_version": WORKFLOW_VERSION, "match_result_sha256": match_sha,
         "active_decision_id": decision["active_decision_id"]})[:16]
    return result


def validate_output(result, schema_path):
    import jsonschema
    schema = json.load(open(schema_path, encoding="utf-8"))
    return [f"{'/'.join(str(x) for x in e.path)}: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(result)]


def dump(result):
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = paths(root)
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON-bestand met één MJOP-regel (input-object v1)")
    ap.add_argument("--decisions", default=p["store"], help="beslissingenopslag (alleen gelezen)")
    ap.add_argument("--out", help="optioneel: resultaatbestand (niet onder data/)")
    args = ap.parse_args()
    raw = json.load(open(args.input, encoding="utf-8"))
    store = json.load(open(args.decisions, encoding="utf-8"))
    try:
        result = run(raw, store, root=root)
    except WorkflowError as e:
        print(f"WORKFLOW-FOUT: {e}", file=sys.stderr)
        sys.exit(3)
    errors = validate_output(result, p["schema"])
    if errors:
        print(f"SCHEMA-FOUTEN ({len(errors)}):", *errors[:20], sep="\n  ", file=sys.stderr)
        sys.exit(1)
    if args.out:
        out = os.path.abspath(args.out)
        if out.startswith(os.path.join(root, "data") + os.sep):
            print("Weigert te schrijven onder data/: de workflow schrijft geen data.", file=sys.stderr)
            sys.exit(2)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump(result))
        print(f"-> {args.out}")
    else:
        sys.stdout.buffer.write(dump(result).encode("utf-8"))   # altijd UTF-8, ook op een Windows-console


if __name__ == "__main__":
    main()
