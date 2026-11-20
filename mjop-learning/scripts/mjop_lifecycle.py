#!/usr/bin/env python3
"""
mjop_lifecycle.py  (LEVENSDUURTABEL PER ELEMENTCODE + ACTIE, v1)

Schema: schemas/lifecycle_table.schema.json; documentatie: docs/mjop_actualisatie_light_v1.md.

Doel: cycli (aantal jaren tussen herhalingen) voor de 30-jaars horizon-planner.

  1. observe: deterministisch uit geverifieerde MJOP's (data/verified/) per document de
     planjaren van dezelfde (element, actie) verzamelen en de intervallen meten.
     Alleen posten MET elementcode tellen mee (= eigen MJOP's; documenten van derden
     zoals DOC-004 hebben geen code en vallen er vanzelf buiten).
  2. voorstel: per (elementcode, actie) min/mediaan/max; proposed_cycle_years alleen
     als de mediaan een geheel getal is (niet afronden, niet gokken).
  3. mens: ACCEPT (voorstel overnemen), EDIT (eigen waarde) of REJECT. Pas daarna is
     cycle_years effectief. Een mens kan ook een cyclus vastleggen voor een combinatie
     die nooit is waargenomen (bv. vervanging lift).

Beperking die de tool zichtbaar maakt i.p.v. verbergt: historische MJOP's beslaan
10-15 jaar. Langcyclische vervangingen (dak, lift, kozijnen, installaties) komen daar
hooguit één keer in voor; hun levensduur is NIET waarneembaar
(max_observable_interval) en moet door een mens worden vastgelegd.

Geen VvE-specifieke inhoud in de tabel: alleen document-IDs, element-IDs en jaren.

Gebruik:
  python scripts/mjop_lifecycle.py build [--out vocabularies/lifecycle_table.json]
  python scripts/mjop_lifecycle.py decide CODE ACTION ACCEPT|EDIT|REJECT --by NAAM [--value N] [--note ..]
"""
import argparse
import copy
import datetime
import glob
import json
import os
import statistics
import sys
from collections import defaultdict
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE_VERSION = "lifecycle_table_v1"
DEFAULT_TABLE = os.path.join(ROOT, "vocabularies", "lifecycle_table.json")
SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "lifecycle_table.schema.json"), encoding="utf-8"))
# staartkosten/advies: geen fysiek element met een levensduur
NON_PHYSICAL_CODES = ("ZZZZ", "9999")


class LifecycleError(ValueError):
    pass


def _value(field):
    if isinstance(field, dict):
        return field.get("normalized_value", field.get("value"))
    return field


def _labels():
    path = os.path.join(ROOT, "vocabularies", "element_code.json")
    return {e["normalized_value"]: e.get("label_nl") for e in json.load(open(path, encoding="utf-8"))["entries"]}


def plan_span(doc):
    years = [a["planned_year"].get("value") for a in doc["maintenance_actions"]]
    years = [y for y in years if isinstance(y, int)]
    return (max(years) - min(years)) if years else None


def document_groups(doc):
    """{(element_code, action): [observation]} voor één document + tellers van overgeslagen groepen."""
    elements = {e["element_id"]: e for e in doc["elements"]}
    years = defaultdict(set)
    for a in doc["maintenance_actions"]:
        y = a["planned_year"].get("value")
        if not isinstance(y, int):
            continue
        code = _value(elements.get(a["element_id"], {}).get("element_code"))
        years[(a["element_id"], code, _value(a["action"]))].add(y)
    groups, skipped = defaultdict(list), {"groups_without_element_code": 0, "groups_without_action": 0}
    for (element_id, code, action), ys in sorted(years.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        if not code:
            skipped["groups_without_element_code"] += 1
            continue
        if code in NON_PHYSICAL_CODES:
            continue
        if not action:
            skipped["groups_without_action"] += 1
            continue
        ys = sorted(ys)
        groups[(code, action)].append({"document_id": doc["document_id"], "element_id": element_id, "years": ys,
                                       "intervals": [b - a for a, b in zip(ys, ys[1:])]})
    return groups, skipped


def _observed(observations, max_span):
    intervals = [i for o in observations for i in o["intervals"]]
    median = None
    proposed = None
    if intervals:
        m = Decimal(statistics.median_low(intervals) + statistics.median_high(intervals)) / 2
        whole = m == m.to_integral()
        median = str(int(m)) if whole else format(m, "f")
        proposed = int(m) if whole else None
    return {"n_documents": len({o["document_id"] for o in observations}), "n_intervals": len(intervals),
            "n_single_occurrence": sum(1 for o in observations if len(o["years"]) == 1),
            "interval_min": min(intervals) if intervals else None, "interval_median": median,
            "interval_max": max(intervals) if intervals else None, "max_observable_interval": max_span,
            "proposed_cycle_years": proposed, "observations": observations}


def build_table(docs, generated_at, previous=None):
    """Nieuwe tabel uit geverifieerde documenten. Menselijke beslissingen uit 'previous' blijven
    behouden (ook voor niet-waargenomen combinaties)."""
    labels = _labels()
    merged, skipped, spans = defaultdict(list), {"groups_without_element_code": 0, "groups_without_action": 0}, {}
    for doc in sorted(docs, key=lambda d: d["document_id"]):
        groups, sk = document_groups(doc)
        for k in skipped:
            skipped[k] += sk[k]
        for key, obs in groups.items():
            merged[key].extend(obs)
        if groups:
            spans[doc["document_id"]] = plan_span(doc)
    prev = {(e["element_code"], e["action"]): e for e in (previous or {}).get("entries", [])}
    entries = []
    for key in sorted(set(merged) | {k for k, e in prev.items() if e["human_verification"]}):
        obs = merged.get(key, [])
        max_span = max((spans[d] for d in {o["document_id"] for o in obs} if spans.get(d) is not None), default=None)
        e = {"element_code": key[0], "action": key[1], "label_nl": labels.get(key[0]),
             "observed": _observed(obs, max_span), "cycle_years": None, "human_verification": None}
        if key in prev and prev[key]["human_verification"]:
            e["human_verification"] = prev[key]["human_verification"]
            e["cycle_years"] = prev[key]["cycle_years"]
        entries.append(e)
    table = {"table_version": TABLE_VERSION, "generated_at": generated_at,
             "source_documents": sorted(spans), "skipped": skipped, "entries": entries}
    return validated(table)


def table_errors(table):
    import jsonschema
    errors = [f"{'/'.join(str(x) for x in e.path) or '(tabel)'}: {e.message}"
              for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(table)]
    if errors:
        return errors
    seen = set()
    for e in table["entries"]:
        key = (e["element_code"], e["action"])
        if key in seen:
            errors.append(f"dubbele entry {key}")
        seen.add(key)
        hv = e["human_verification"]
        expected = hv["value"] if hv and hv["decision"] in ("ACCEPT", "EDIT") else None
        if e["cycle_years"] != expected:
            errors.append(f"{key}: cycle_years zonder (passende) menselijke beslissing")
    return errors


def validated(table):
    errors = table_errors(table)
    if errors:
        raise LifecycleError("; ".join(errors))
    return table


def decide(table, element_code, action, decision, *, by, at, value=None, note=None):
    """Menselijke beslissing. ACCEPT neemt proposed_cycle_years over (moet bestaan); EDIT vereist
    een eigen waarde >= 1; REJECT maakt de cyclus leeg. Een niet-waargenomen combinatie kan alleen
    via EDIT worden toegevoegd."""
    if decision not in ("ACCEPT", "EDIT", "REJECT"):
        raise LifecycleError(f"onbekende beslissing {decision!r}")
    if not by:
        raise LifecycleError("'by' (gebruiker) is verplicht")
    t = copy.deepcopy(table)
    entry = next((e for e in t["entries"] if e["element_code"] == element_code and e["action"] == action), None)
    if entry is None:
        if decision != "EDIT":
            raise LifecycleError(f"({element_code}, {action}) is niet waargenomen; alleen EDIT met een waarde kan")
        entry = {"element_code": element_code, "action": action, "label_nl": _labels().get(element_code),
                 "observed": _observed([], None), "cycle_years": None, "human_verification": None}
        t["entries"].append(entry)
        t["entries"].sort(key=lambda e: (e["element_code"], e["action"]))
    proposed = entry["observed"]["proposed_cycle_years"]
    if decision == "ACCEPT":
        if proposed is None:
            raise LifecycleError(f"({element_code}, {action}) heeft geen voorstel om te accepteren; gebruik EDIT")
        value = proposed
    elif decision == "EDIT":
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise LifecycleError("EDIT vereist een geheel aantal jaren >= 1")
    else:
        value = None
    entry["cycle_years"] = value
    entry["human_verification"] = {"decision": decision, "original_proposed_value": proposed, "value": value,
                                   "by": by, "at": at, "note": note}
    return validated(t)


def effective_cycle(table, element_code, action):
    """Cyclus alleen als een mens die heeft vastgesteld; anders None."""
    for e in table["entries"]:
        if e["element_code"] == element_code and e["action"] == action:
            return e["cycle_years"]
    return None


def entry_for(table, element_code, action):
    return next((e for e in table["entries"] if e["element_code"] == element_code and e["action"] == action), None)


def load_verified_docs(root=ROOT):
    return [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(root, "data", "verified", "DOC-*.json")))]


def load_table(path=DEFAULT_TABLE):
    return validated(json.load(open(path, encoding="utf-8")))


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write(table, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=DEFAULT_TABLE)
    d = sub.add_parser("decide")
    d.add_argument("element_code")
    d.add_argument("action")
    d.add_argument("decision", choices=["ACCEPT", "EDIT", "REJECT"])
    d.add_argument("--by", required=True)
    d.add_argument("--value", type=int)
    d.add_argument("--note")
    d.add_argument("--table", default=DEFAULT_TABLE)
    a = p.parse_args(argv)
    if a.cmd == "build":
        previous = load_table(a.out) if os.path.exists(a.out) else None
        table = build_table(load_verified_docs(), _now(), previous)
        _write(table, a.out)
        n_prop = sum(1 for e in table["entries"] if e["observed"]["proposed_cycle_years"])
        print(f"{len(table['entries'])} entries, {n_prop} met voorstel, "
              f"{sum(1 for e in table['entries'] if e['cycle_years'])} vastgesteld -> {a.out}")
    else:
        table = decide(load_table(a.table), a.element_code, a.action, a.decision, by=a.by, at=_now(),
                       value=a.value, note=a.note)
        _write(table, a.table)
        print(f"({a.element_code}, {a.action}) -> {a.decision} cycle_years={effective_cycle(table, a.element_code, a.action)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
