#!/usr/bin/env python3
"""
evaluate_dataset.py  (stap: NORMALIZED/VERIFIED -> EVALUATION)

Vergelijkt data/normalized/ (AI-output) met data/verified/ (door een mens
gecontroleerde waarden) en berekent nauwkeurigheidscijfers per veld.

BELANGRIJK (zie CLAUDE.md):
  - Dit script leest NOOIT uit data/evaluation/ om regels/prompts aan te
    passen. data/evaluation/ dient alleen om, los van dit script, de
    einduitkomst van de pipeline te toetsen op een set die niet is gebruikt
    om op te optimaliseren.
  - Zolang data/verified/ leeg is (nog geen menselijke verificatie gedaan)
    kan dit script geen zinvolle cijfers geven - dat is dan de uitkomst,
    geen bug. Doe geen aannames over "AI is X% accuraat" zonder deze
    meting (zie masterplan sectie 12).

Gebruik:
    python3 scripts/evaluate_dataset.py
"""
import glob
import json
import os


FIELDS_TO_CHECK = [
    ("elements", "element_type", "normalized_value"),
    ("elements", "material", "normalized_value"),
    ("maintenance_actions", "action", "normalized_value"),
    ("maintenance_actions", "planned_year", "value"),
    ("maintenance_actions", "direct_cost_calculated", None),
]


def load_records(directory):
    out = {}
    for path in glob.glob(os.path.join(directory, "*.json")):
        rec = json.load(open(path))
        doc_id = rec.get("document_id")
        if doc_id:
            out[doc_id] = rec
    return out


def get_nested(rec, list_key, field_key, sub_key):
    """Haalt een lijst waarden op voor vergelijking, bijv. alle
    elements[*].element_type.normalized_value in een document."""
    values = []
    for item in rec.get(list_key, []):
        v = item.get(field_key)
        if v is None:
            continue
        values.append(v.get(sub_key) if sub_key and isinstance(v, dict) else v)
    return values


def main():
    normalized = load_records("data/normalized")
    verified = load_records("data/verified")

    if not verified:
        print("data/verified/ is leeg - er is nog geen golden dataset om tegen te "
              "evalueren. Voer eerst menselijke verificatie uit (ACCEPT/EDIT/REJECT) "
              "voordat dit script een betrouwbaar cijfer kan geven.")
        print(f"({len(normalized)} genormaliseerde documenten gevonden, 0 geverifieerd)")
        return

    report = {}
    for list_key, field_key, sub_key in FIELDS_TO_CHECK:
        matches, total = 0, 0
        for doc_id, v_rec in verified.items():
            n_rec = normalized.get(doc_id)
            if not n_rec:
                continue
            v_vals = get_nested(v_rec, list_key, field_key, sub_key)
            n_vals = get_nested(n_rec, list_key, field_key, sub_key)
            total += len(v_vals)
            matches += sum(1 for a, b in zip(v_vals, n_vals) if a == b)
        report[f"{list_key}.{field_key}"] = {
            "matches": matches,
            "total": total,
            "accuracy": round(matches / total, 3) if total else None,
        }

    os.makedirs("reports", exist_ok=True)
    json.dump(report, open("reports/evaluation_report.json", "w"), indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\nGeschreven naar reports/evaluation_report.json")


if __name__ == "__main__":
    main()
