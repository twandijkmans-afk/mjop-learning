#!/usr/bin/env python3
"""
mjop_oprognose_cycles.py  (CYCLI UIT OPROGNOSE-EXPORTS ALS BRON VOOR DE LEVENSDUURTABEL, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md (sectie Levensduurtabel).

Leest één of meer OPrognose-exports (.xml, mappen of .zip; buiten de repository: ze bevatten
klantgegevens) en verzamelt per (elementcode, actie) de cycli die adviseurs in OPrognose hebben gezet.

  - alleen geplande handelingen (han_type 'H') met een 4-cijferige ele_nlsfb;
  - han_cyclus > 0 telt als cyclus; 0 (eenmalig) en de waarden in out_of_plan_cycles (48 =
    'buiten de planperiode') worden alleen geteld;
  - actie: exacte lookup in vocabularies/maintenance_action.json, daarna de trefwoordregels in
    config/oprognose/action_text_rules.json. Ambigu of onbekend -> niet ingedeeld (gemeld);
  - per bestand wordt alleen een sha256 bewaard. Er worden geen namen, adressen, projectcodes of
    teksten in de levensduurtabel opgenomen; het (lokale) rapport met niet-ingedeelde teksten
    blijft buiten de repository.
"""
import hashlib
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "config", "oprognose", "action_text_rules.json")
NON_PHYSICAL_CODES = ("ZZZZ", "9999")


def load_rules(path=RULES_PATH):
    rules = json.load(open(path, encoding="utf-8"))
    vocab = json.load(open(os.path.join(ROOT, "vocabularies", "maintenance_action.json"), encoding="utf-8"))
    exact = {str(o).strip().lower(): e["normalized_value"] for e in vocab["entries"]
             for o in e.get("known_original_values", [])}
    labels = {e["normalized_value"]: (e.get("label_nl") or "") for e in
              json.load(open(os.path.join(ROOT, "vocabularies", "element_code.json"), encoding="utf-8"))["entries"]}
    return {"keywords": rules["keywords"], "precedence": rules.get("precedence", []), "exact": exact,
            "code_labels": labels, "version": rules["rules_version"],
            "strip_clauses": rules.get("strip_clauses", []), "strip_parentheses": rules.get("strip_parentheses", False),
            "combinations": rules.get("combinations", []), "out_of_plan": set(rules.get("out_of_plan_cycles", []))}


def core_text(text, rules):
    """Tekst voor de indeling: planningsnotities ('gelijktijdig met ...') en tekst tussen haakjes eruit."""
    t = (text or "").strip().lower()
    if rules.get("strip_parentheses"):
        t = re.sub(r"\([^)]*\)", " ", t)
    for clause in rules.get("strip_clauses", []):
        i = t.find(clause)
        if i >= 0:
            t = t[:i]
    return " ".join(t.split())


def classify(text, code, rules):
    """(actie of None, reden). Exact > trefwoorden; ambigu of onbekend -> None."""
    raw = (text or "").strip().lower()
    if not raw:
        return None, "EMPTY_TEXT"
    if raw in rules["exact"] and rules["exact"][raw]:
        return rules["exact"][raw], "EXACT"
    t = core_text(raw, rules)
    if t in rules["exact"] and rules["exact"][t]:
        return rules["exact"][t], "EXACT"
    combo = [c["action"] for c in rules.get("combinations", []) if all(w in t for w in c["all"])]
    hits = set(combo) if len(combo) == 1 else {a for a, words in rules["keywords"].items() if any(w in t for w in words)}
    for winner, loser in rules["precedence"]:
        if winner in hits:
            hits.discard(loser)
    if "PAINTING" in hits and len(hits) > 1:
        return None, "AMBIGUOUS"
    if len(hits) > 1:
        return None, "AMBIGUOUS"
    if not hits:
        return None, "NO_RULE"
    action = hits.pop()
    if action != "PAINTING":
        return action, "KEYWORD"
    if "buiten" in t:
        return "exterior_painting", "KEYWORD"
    if "binnen" in t:
        return "interior_painting", "KEYWORD"
    label = rules["code_labels"].get(code, "").lower()
    if label.startswith("buitenschilderwerk"):
        return "exterior_painting", "CODE_LABEL"
    if label.startswith("binnenschilderwerk"):
        return "interior_painting", "CODE_LABEL"
    return "paint", "KEYWORD"


def iter_xml_sources(paths):
    """(naam, bytes) voor elk .xml-bestand in de opgegeven bestanden, mappen en zips."""
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _, files in sorted(os.walk(p)):
                for f in sorted(files):
                    yield from iter_xml_sources([os.path.join(dirpath, f)])
        elif p.lower().endswith(".zip"):
            with zipfile.ZipFile(p) as z:
                for info in sorted(z.infolist(), key=lambda i: i.filename):
                    if info.filename.lower().endswith(".xml") and not info.is_dir():
                        yield f"{os.path.basename(p)}:{info.filename}", z.read(info)
        elif p.lower().endswith(".xml"):
            with open(p, "rb") as f:
                yield os.path.basename(p), f.read()


def read_export(data, rules):
    """Handelingen uit één export: [(code, actie|None, cyclus, reden, tekst)]."""
    root = ET.fromstring(data)
    if root.tag != "NewDataSet" or root.find("opo") is None:
        raise ValueError("geen OPrognose-export (NewDataSet/opo ontbreekt)")
    out = []
    for ope in root.iter("ope"):
        code = (ope.findtext("ele_nlsfb") or "").strip()
        for oph in ope.findall("oph"):
            if (oph.findtext("han_type") or "").strip() != "H":
                continue
            try:
                cycle = int(oph.findtext("han_cyclus") or 0)
            except ValueError:
                cycle = 0
            text = oph.findtext("han_tekst") or ""
            if not (code.isdigit() and len(code) == 4) or code in NON_PHYSICAL_CODES:
                out.append((code or None, None, cycle, "NO_PHYSICAL_CODE", text))
                continue
            action, reason = classify(text, code, rules)
            out.append((code, action, cycle, reason, text))
    return out


def _stats(cycles):
    if not cycles:
        return None, None, None, None
    m = Decimal(statistics.median_low(cycles) + statistics.median_high(cycles)) / 2
    whole = m == m.to_integral()
    return min(cycles), (str(int(m)) if whole else format(m, "f")), max(cycles), (int(m) if whole else None)


def collect(paths, rules=None):
    """Geeft (observations, summary, local_report). observations: {(code, actie): {...}} zonder klantgegevens."""
    rules = rules or load_rules()
    per_key = defaultdict(lambda: {"cycles": [], "files": set(), "one_off": 0, "out_of_plan": 0})
    files, failed, reasons, unmapped = [], [], Counter(), Counter()
    for name, data in iter_xml_sources(paths):
        sha = hashlib.sha256(data).hexdigest()
        if sha in files:
            continue   # dubbele export telt één keer
        try:
            actions = read_export(data, rules)
        except (ET.ParseError, ValueError) as e:
            failed.append({"file": name, "error": str(e)[:200]})
            continue
        files.append(sha)
        for code, action, cycle, reason, text in actions:
            reasons[reason] += 1
            if action is None:
                if reason in ("AMBIGUOUS", "NO_RULE"):
                    unmapped[(reason, text.strip().lower())] += 1
                continue
            entry = per_key[(code, action)]
            entry["files"].add(sha)
            if cycle in rules["out_of_plan"]:
                entry["out_of_plan"] += 1   # 'buiten de planperiode', geen levensduur
            elif cycle > 0:
                entry["cycles"].append(cycle)
            else:
                entry["one_off"] += 1
    observations = {}
    for key, e in sorted(per_key.items()):
        lo, med, hi, proposed = _stats(e["cycles"])
        observations[key] = {"n_files": len(e["files"]), "n_actions": len(e["cycles"]) + e["one_off"] + e["out_of_plan"],
                             "n_one_off": e["one_off"], "n_out_of_plan": e["out_of_plan"], "cycle_min": lo, "cycle_median": med, "cycle_max": hi,
                             "cycle_counts": {str(c): n for c, n in sorted(Counter(e["cycles"]).items())},
                             "proposed_cycle_years": proposed}
    summary = {"rules_version": rules["version"], "n_files": len(files), "file_sha256": sorted(files),
               "classification_counts": dict(sorted(reasons.items())),
               "unmapped_actions": sum(n for (r, _), n in unmapped.items())}
    local_report = {"failed_files": failed,
                    "unmapped_texts": [{"reason": r, "text": t, "count": n} for (r, t), n in unmapped.most_common()]}
    return observations, summary, local_report
