"""3D BAG quantity rules v1 — pure, deterministische regels over 3D BAG-attributen.

Regels staan in vocabularies/quantity_subjects_v1.json (bag3d_rules). Geen afronding: de uitkomst is een
exacte Decimal-string van de ruwe JSON-getallen (afronden alleen voor weergave). Ontbreekt een veld, dan
levert de regel NOT_AVAILABLE op (nooit een aanname of 0).
"""

import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBJECTS = ROOT / "vocabularies" / "quantity_subjects_v1.json"


def load_rules(path=SUBJECTS):
    v = json.loads(Path(path).read_text(encoding="utf-8"))
    return [r for r in v["bag3d_rules"] if r["status"] == "ACTIVE"], v


def _dec(x):
    # via str(): een JSON-float 312.64 wordt exact '312.64', niet de binaire benadering
    return Decimal(str(x))


def apply_rule(rule, attributes):
    attributes = attributes or {}
    raw = {f: attributes.get(f) for f in rule["fields"]}
    missing = [f for f, v in raw.items() if v is None or isinstance(v, bool) or not isinstance(v, (int, float, str))]
    if missing:
        return {"rule_id": rule["rule_id"], "rule_version": rule["rule_version"], "subject_key": rule["subject_key"],
                "status": "NOT_AVAILABLE", "missing_fields": missing, "raw_inputs": raw, "value": None}
    vals = [_dec(raw[f]) for f in rule["fields"]]
    if rule["formula"] == rule["fields"][0] and len(vals) == 1:
        value = vals[0]
    elif rule["formula"] == f"{rule['fields'][0]} + {rule['fields'][1]}":
        value = vals[0] + vals[1]
    elif rule["formula"] == f"{rule['fields'][0]} - {rule['fields'][1]}":
        value = vals[0] - vals[1]
    else:
        raise ValueError(f"onbekende formule {rule['formula']!r} in {rule['rule_id']}")
    status = "OK" if value >= 0 else "NEGATIVE_RESULT"
    return {"rule_id": rule["rule_id"], "rule_version": rule["rule_version"], "subject_key": rule["subject_key"],
            "status": status, "missing_fields": [], "raw_inputs": raw, "value": str(value)}


def apply_rules(attributes, rules=None):
    rules = rules if rules is not None else load_rules()[0]
    return [apply_rule(r, attributes) for r in rules]
