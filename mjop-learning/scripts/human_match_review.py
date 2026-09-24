#!/usr/bin/env python3
"""
human_match_review.py  (MENSELIJKE BESLISSING OVER EEN MATCHRESULTAAT, human match review v1)

Registreert append-only de beslissing van een mens over een matchresultaat van
scripts/match_kengetal.py in
data/match_review_decisions/human_match_decision_records.json
(schema: schemas/human_match_decision_record.schema.json,
werkwijze: docs/human_match_review_v1.md).

Beslissingen: ACCEPT / ADJUST / REJECT; decision_status: ACTIVE / SUPERSEDED.
Per match_result_id hoogstens één ACTIVE beslissing. Een nieuwe beslissing
voor hetzelfde matchresultaat maakt de vorige SUPERSEDED (de enige toegestane
wijziging aan een bestaand record) en verwijst ernaar via 'supersedes'. Er
wordt niets verwijderd of overschreven.

Een beslissing is uitsluitend een beslissing over het gebruik van het
matchresultaat. Deze module schrijft alleen de beslissingenopslag: nooit
historische observations, kengetallen, comparability- of human
comparability-data, en past het matchresultaat niet aan. Geen score,
ranking, confidence of fuzzy matching.

Gebruik:
    python scripts/human_match_review.py record --match-result mr.json --decision ACCEPT \
        --reviewer twandijkmans --reason "..." [--kengetal-id KG-...] [--amount 12.34] \
        [--amount-basis "..."] [--caveat CODE]... [--evidence REF[::NOTE]]... [--notes "..."] [--dry-run]
    python scripts/human_match_review.py status --match-result-id MR-...
"""
import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_kengetal  # noqa: E402

REVIEW_VERSION = "human_match_review_v1"
DECISIONS = ("ACCEPT", "ADJUST", "REJECT")
CURRENT_STATUS = {"ACCEPT": "ACCEPTED", "ADJUST": "ADJUSTED", "REJECT": "REJECTED"}
# inhoudelijke fingerprint: alles behalve auditinformatie (reviewed_at) en decision_status
FINGERPRINT_FIELDS = ("match_result_id", "match_result_sha256", "decision", "chosen_kengetal_id", "adjustment",
                      "decision_reason", "decision_caveats", "evidence", "reviewer", "notes", "supersedes",
                      "rule_versions", "input_hashes")


class IntegrityError(Exception):
    """De opslag schendt een invariant (bijv. meer dan één ACTIVE beslissing per matchresultaat)."""


def canonical_sha256(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def human_match_decision_record_id(record):
    """Deterministisch record-ID uit de inhoud en de relevante versies/hashes; geen tijdstempel."""
    return "HMD-" + canonical_sha256({f: record.get(f) for f in FINGERPRINT_FIELDS})[:16]


def paths(root):
    return {"store": os.path.join(root, "data", "match_review_decisions", "human_match_decision_records.json"),
            "schema": os.path.join(root, "schemas", "human_match_decision_record.schema.json"),
            "match_schema": os.path.join(root, "schemas", "match_result.schema.json"),
            "kengetallen": os.path.join(root, "data", "kengetallen", "kengetallen_batch1.json")}


# --------------------------------------------------------------------------
# Controles
# --------------------------------------------------------------------------

def match_result_errors(match_result, match_schema=None):
    """Het matchresultaat moet geldig en ongewijzigd zijn (ID herberekenbaar uit de inhoud)."""
    errors = []
    if match_schema is not None:
        import jsonschema
        errors += [f"match_result: {e.message}" for e in jsonschema.Draft7Validator(match_schema).iter_errors(match_result)]
        if errors:
            return errors
    expected = match_kengetal.match_result_id(match_result["input_normalized"], match_result["input_hashes"],
                                              match_result["kengetallen_rule_version"])
    if match_result["rule_version"] != match_kengetal.RULE_VERSION:
        errors.append(f"match_result: rule_version {match_result['rule_version']} is niet {match_kengetal.RULE_VERSION}")
    elif expected != match_result["match_result_id"]:
        errors.append("match_result: match_result_id past niet bij de inhoud (resultaat gewijzigd?)")
    return errors


def record_errors(record, kengetallen_doc=None):
    """Controles per record die het JSON-schema niet kan uitdrukken."""
    errors, rid = [], record.get("decision_id")
    mr = record["match_result"]
    if canonical_sha256(mr) != record["match_result_sha256"]:
        errors.append(f"{rid}: match_result_sha256 past niet bij het bewaarde matchresultaat")
    for field, source in (("match_result_id", "match_result_id"), ("input_object_id", "input_object_id"),
                          ("system_final_status", "final_status"), ("system_scope_status", "scope_status"),
                          ("system_reasons", "reasons"), ("system_candidate_kengetal_id", "candidate_kengetal_id"),
                          ("system_candidate_kengetal_ids", "candidate_kengetal_ids"), ("input_hashes", "input_hashes")):
        if record[field] != mr[source]:
            errors.append(f"{rid}: {field} wijkt af van het matchresultaat")
    if record["rule_versions"]["matching_rule_version"] != mr["rule_version"] or \
            record["rule_versions"]["kengetallen_rule_version"] != mr["kengetallen_rule_version"]:
        errors.append(f"{rid}: rule_versions wijken af van het matchresultaat")
    if human_match_decision_record_id(record) != rid:
        errors.append(f"{rid}: decision_id past niet bij de inhoud")

    d = record["decision"]
    if d == "ACCEPT":
        if not mr["candidate_kengetal_id"]:
            errors.append(f"{rid}: ACCEPT kan alleen bij een matchresultaat met een voorgesteld kengetal")
        elif record["chosen_kengetal_id"] != mr["candidate_kengetal_id"]:
            errors.append(f"{rid}: ACCEPT moet het voorgestelde kengetal kiezen")
    elif d == "ADJUST":
        adj = record["adjustment"] or {}
        if not adj.get("kengetal_id") and not adj.get("amount_per_unit_exact"):
            errors.append(f"{rid}: ADJUST vereist een ander kengetal_id en/of een bedrag")
        if adj.get("kengetal_id") == mr["candidate_kengetal_id"] and not adj.get("amount_per_unit_exact"):
            errors.append(f"{rid}: ADJUST zonder wijziging ten opzichte van het voorstel; gebruik ACCEPT")
        if record["chosen_kengetal_id"] != adj.get("kengetal_id"):
            errors.append(f"{rid}: chosen_kengetal_id moet gelijk zijn aan adjustment.kengetal_id")
        if adj.get("unit") is not None and adj["unit"] != mr["input_normalized"]["unit"]:
            errors.append(f"{rid}: adjustment.unit moet de eenheid van het input-object zijn")
        if adj.get("amount_per_unit_exact"):
            try:
                if Decimal(adj["amount_per_unit_exact"]) <= 0:
                    errors.append(f"{rid}: bedrag moet positief zijn")
            except InvalidOperation:
                errors.append(f"{rid}: bedrag is geen decimaal getal")
        if adj.get("kengetal_id") and kengetallen_doc is not None:
            k = next((x for x in kengetallen_doc["kengetallen"] if x["kengetal_id"] == adj["kengetal_id"]), None)
            if k is None:
                errors.append(f"{rid}: kengetal {adj['kengetal_id']} bestaat niet")
            elif k["status"] != "AVAILABLE":
                errors.append(f"{rid}: kengetal {adj['kengetal_id']} heeft status {k['status']}")
    return errors


def store_invariant_errors(store):
    """Invarianten over records heen: unieke decision_id, per match_result_id hoogstens
    één ACTIVE, 'supersedes' naar een bestaand SUPERSEDED record van hetzelfde matchresultaat,
    en elk SUPERSEDED record is door precies één later record vervangen."""
    errors, by_id = [], {}
    for r in store["records"]:
        if r["decision_id"] in by_id:
            errors.append(f"{r['decision_id']}: decision_id komt meer dan eens voor")
        by_id[r["decision_id"]] = r
    active, superseded_by = {}, {}
    for pos, r in enumerate(store["records"]):
        if r["decision_status"] == "ACTIVE":
            active.setdefault(r["match_result_id"], []).append(r["decision_id"])
        if r["supersedes"]:
            old = by_id.get(r["supersedes"])
            if old is None:
                errors.append(f"{r['decision_id']}: supersedes verwijst naar onbekende {r['supersedes']}")
            elif old["match_result_id"] != r["match_result_id"] or old["decision_status"] != "SUPERSEDED" \
                    or store["records"].index(old) >= pos:
                errors.append(f"{r['decision_id']}: vervangen record {old['decision_id']} moet eerder, van hetzelfde "
                              "matchresultaat en SUPERSEDED zijn")
            superseded_by.setdefault(r["supersedes"], []).append(r["decision_id"])
    for r in store["records"]:
        n = len(superseded_by.get(r["decision_id"], []))
        if r["decision_status"] == "SUPERSEDED" and n != 1:
            errors.append(f"{r['decision_id']}: SUPERSEDED maar door {n} records vervangen")
    errors += [f"{mid}: meer dan één ACTIVE beslissing ({', '.join(ids)})" for mid, ids in sorted(active.items())
               if len(ids) > 1]
    return errors


def append_only_errors(old_store, new_store):
    """Alleen toevoegen; bestaand record ongewijzigd behalve decision_status ACTIVE -> SUPERSEDED."""
    new = {r["decision_id"]: r for r in new_store["records"]}
    errors = []
    if [r["decision_id"] for r in new_store["records"][:len(old_store["records"])]] != \
            [r["decision_id"] for r in old_store["records"]]:
        errors.append("volgorde van bestaande records gewijzigd")
    for r in old_store["records"]:
        n = new.get(r["decision_id"])
        if n is None:
            errors.append(f"{r['decision_id']}: record verwijderd")
            continue
        if {k: v for k, v in n.items() if k != "decision_status"} != \
                {k: v for k, v in r.items() if k != "decision_status"}:
            errors.append(f"{r['decision_id']}: record overschreven")
        if n["decision_status"] != r["decision_status"] and \
                (r["decision_status"], n["decision_status"]) != ("ACTIVE", "SUPERSEDED"):
            errors.append(f"{r['decision_id']}: statuswijziging {r['decision_status']} -> {n['decision_status']} "
                          "niet toegestaan")
    return errors


def validate_store(store, schema, kengetallen_doc=None):
    import jsonschema
    errors = [f"{'/'.join(str(x) for x in e.path)}: {e.message}"
              for e in jsonschema.Draft7Validator(schema).iter_errors(store)]
    if errors:
        return errors
    for r in store["records"]:
        errors += record_errors(r, kengetallen_doc)
    return errors + store_invariant_errors(store)


# --------------------------------------------------------------------------
# Beslissing toevoegen en actuele status
# --------------------------------------------------------------------------

def build_record(match_result, decision, reviewer_id, decision_reason, *, chosen_kengetal_id=None, amount=None,
                 amount_basis=None, caveats=(), evidence=(), notes=None, reviewed_at=None, supersedes=None):
    if decision not in DECISIONS:
        raise ValueError(f"onbekende beslissing {decision!r}; toegestaan: {', '.join(DECISIONS)}")
    mr = copy.deepcopy(match_result)
    adjustment, chosen = None, None
    if decision == "ACCEPT":
        chosen = mr["candidate_kengetal_id"]
    elif decision == "ADJUST":
        adjustment = {"kengetal_id": chosen_kengetal_id,
                      "amount_per_unit_exact": None if amount is None else format(Decimal(str(amount)), "f"),
                      "unit": mr["input_normalized"]["unit"] if amount is not None else None,
                      "amount_basis": amount_basis}
        chosen = chosen_kengetal_id
    record = {
        "decision_id": None,
        "match_result_id": mr["match_result_id"],
        "match_result_sha256": canonical_sha256(mr),
        "match_result": mr,
        "input_object_id": mr["input_object_id"],
        "system_final_status": mr["final_status"],
        "system_scope_status": mr["scope_status"],
        "system_reasons": list(mr["reasons"]),
        "system_candidate_kengetal_id": mr["candidate_kengetal_id"],
        "system_candidate_kengetal_ids": list(mr["candidate_kengetal_ids"]),
        "decision": decision,
        "chosen_kengetal_id": chosen,
        "adjustment": adjustment,
        "decision_reason": decision_reason,
        "decision_caveats": list(caveats),
        "evidence": [dict(e) for e in evidence],
        "reviewer": {"reviewer_id": reviewer_id, "reviewer_type": "human"},
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule_versions": {"human_match_review_version": REVIEW_VERSION,
                          "matching_rule_version": mr["rule_version"],
                          "kengetallen_rule_version": mr["kengetallen_rule_version"]},
        "input_hashes": copy.deepcopy(mr["input_hashes"]),
        "notes": notes,
        "supersedes": supersedes,
        "decision_status": "ACTIVE",
    }
    record["decision_id"] = human_match_decision_record_id(record)
    return record


def add_decision(store, match_result, decision, reviewer_id, decision_reason, *, schema, match_schema=None,
                 kengetallen_doc=None, **kwargs):
    """Geeft een NIEUWE opslag terug met de beslissing toegevoegd; de vorige ACTIVE beslissing voor
    hetzelfde matchresultaat wordt SUPERSEDED. Invoer wordt niet gemuteerd. Fout -> ValueError."""
    errors = match_result_errors(match_result, match_schema)
    if errors:
        raise ValueError("; ".join(errors))
    current_decision(store, match_result["match_result_id"])   # IntegrityError bij >1 ACTIVE
    new_store = copy.deepcopy(store)
    previous = next((r for r in new_store["records"] if r["match_result_id"] == match_result["match_result_id"]
                     and r["decision_status"] == "ACTIVE"), None)
    record = build_record(match_result, decision, reviewer_id, decision_reason,
                          supersedes=previous["decision_id"] if previous else None, **kwargs)
    if previous:
        previous["decision_status"] = "SUPERSEDED"
    new_store["records"].append(record)
    errors = validate_store(new_store, schema, kengetallen_doc) + append_only_errors(store, new_store)
    if errors:
        raise ValueError("; ".join(errors))
    return new_store, record


def current_decision(store, match_result_id):
    """Actuele situatie voor één matchresultaat: NO_DECISION / ACCEPTED / ADJUSTED / REJECTED.
    Meer dan één ACTIVE beslissing -> IntegrityError. SUPERSEDED records blijven in 'history'."""
    history = [r for r in store["records"] if r["match_result_id"] == match_result_id]
    active = [r for r in history if r["decision_status"] == "ACTIVE"]
    if len(active) > 1:
        raise IntegrityError(f"{match_result_id}: meer dan één ACTIVE beslissing "
                             f"({', '.join(r['decision_id'] for r in active)})")
    if not active:
        return {"match_result_id": match_result_id, "status": "NO_DECISION", "active_record": None,
                "history": [r["decision_id"] for r in history]}
    return {"match_result_id": match_result_id, "status": CURRENT_STATUS[active[0]["decision"]],
            "active_record": active[0], "history": [r["decision_id"] for r in history]}


# --------------------------------------------------------------------------
# Bestanden en CLI
# --------------------------------------------------------------------------

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_store(path, old_store, new_store, schema, kengetallen_doc=None):
    """Schrijft alleen na volledige validatie én append-only-controle tegen de huidige inhoud op schijf."""
    on_disk = load_json(path)
    if on_disk != old_store:
        raise IntegrityError("opslag is gewijzigd sinds het laden; opnieuw laden en opnieuw beslissen")
    errors = validate_store(new_store, schema, kengetallen_doc) + append_only_errors(on_disk, new_store)
    if errors:
        raise ValueError("; ".join(errors))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(new_store, ensure_ascii=False, indent=2) + "\n")


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = paths(root)
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--match-result", required=True)
    rec.add_argument("--decision", required=True, choices=DECISIONS)
    rec.add_argument("--reviewer", required=True)
    rec.add_argument("--reason", required=True)
    rec.add_argument("--kengetal-id")
    rec.add_argument("--amount")
    rec.add_argument("--amount-basis")
    rec.add_argument("--caveat", action="append", default=[])
    rec.add_argument("--evidence", action="append", default=[], help="REF of REF::NOTE")
    rec.add_argument("--notes")
    rec.add_argument("--store", default=p["store"])
    rec.add_argument("--dry-run", action="store_true")
    st = sub.add_parser("status")
    st.add_argument("--match-result-id", required=True)
    st.add_argument("--store", default=p["store"])
    args = ap.parse_args()

    store = load_json(args.store)
    if args.cmd == "status":
        cur = current_decision(store, args.match_result_id)
        print(json.dumps({k: v for k, v in cur.items() if k != "active_record"}
                         | {"active_decision_id": cur["active_record"]["decision_id"] if cur["active_record"] else None},
                         ensure_ascii=False, indent=2))
        return
    schema, match_schema, kengetallen = load_json(p["schema"]), load_json(p["match_schema"]), load_json(p["kengetallen"])
    evidence = [{"reference": e.split("::", 1)[0], "note": e.split("::", 1)[1] if "::" in e else None}
                for e in args.evidence]
    new_store, record = add_decision(
        store, load_json(args.match_result), args.decision, args.reviewer, args.reason, schema=schema,
        match_schema=match_schema, kengetallen_doc=kengetallen, chosen_kengetal_id=args.kengetal_id,
        amount=args.amount, amount_basis=args.amount_basis, caveats=args.caveat, evidence=evidence, notes=args.notes)
    print(json.dumps({k: record[k] for k in ("decision_id", "match_result_id", "decision", "chosen_kengetal_id",
                                             "supersedes", "decision_status")}, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("--dry-run: niets geschreven.")
        return
    save_store(args.store, store, new_store, schema, kengetallen)
    print(f"-> {os.path.relpath(args.store, root)}")


if __name__ == "__main__":
    main()
