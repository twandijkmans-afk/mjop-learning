#!/usr/bin/env python3
"""
match_kengetal.py  (NIEUW MJOP-OBJECT -> KENGETAL-KANDIDAAT, matching v1)

Deterministische candidate retrieval + match evaluation tegen
data/kengetallen/kengetallen_batch1.json. Leest alleen; schrijft geen
historische kennis, geen human decisions en past geen prijs aan.

Input-object v1 (één JSON-object):
  gebruikt in v1
    object_id                 verplicht
    element_code_internal     interne elementcode (geen automatische codekoppeling)
    action_normalized | action_text     tekst -> exacte lookup in
                              vocabularies/maintenance_action.json, anders de
                              goedgekeurde prefixregel (zelfde als normalisatie)
    unit_normalized | unit_text         tekst -> exacte lookup in vocabularies/unit.json
    material_normalized | material_text tekst -> exacte lookup in vocabularies/material.json
    material_source           herkomst van het materiaal (bijv. user, verified_element, element_text)
    object_description        voor de scope-check
    quantity                  alleen om het historische bereik te tonen (geen schaalcorrectie)
    price_level_requested     jaar; alleen presentatie (geen indexatie)
    vat_basis                 inclusive / exclusive / null
  context/future (worden alleen doorgegeven)
    building_type, construction_year, location, condition_defect, maintenance_type

Regels (matching v1):
  1. Retrieval: alleen kengetallen met status AVAILABLE en exact gelijke
     element_code + action + unit + bekend materiaal. Onbekend materiaal
     haalt geen materiaalgebonden kengetal op. Dit is alleen retrieval, geen
     match.
  2. Scope (per kandidaat, zonder fuzzy matching; woordtokens, kleine letters):
     - objectomschrijving token-gelijk aan die van een groepslid  -> EXACT_MATCH
     - token-gelijk aan die van een observation die met een menselijke
       NOT_COMPARABLE uit de groep is uitgesloten             -> MISMATCH
     - beide                                                   -> HUMAN_REVIEW_REQUIRED
     - anders of geen omschrijving                             -> HUMAN_REVIEW_REQUIRED
  3. Eindstatus: CANDIDATE_FOUND alleen bij precies één niet-MISMATCH
     kandidaat met EXACT_MATCH en geen bekend BTW-verschil;
     NO_SUITABLE_KENGETAL bij geen kandidaat of alleen MISMATCH; anders
     HUMAN_REVIEW_REQUIRED. Altijd met machine-leesbare redenen.
Geen score, ranking, confidence, indexatie of schaalcorrectie.

Gebruik:
    python scripts/match_kengetal.py --input item.json [--out result.json]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_price_observations import load_vocab_utf8, lookup_key, prefix_rule  # noqa: E402

RULE_VERSION = "matching_rules_v1"
CONTEXT_FIELDS = ("building_type", "construction_year", "location", "condition_defect", "maintenance_type")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tokens(text):
    return tuple(re.findall(r"[a-z0-9]+", (text or "").lower()))


def material_id(original, normalized):
    if normalized:
        return normalized
    return original.strip().lower() if original and original.strip() else None


# --------------------------------------------------------------------------
# 1. Input normaliseren (bestaande vocabularies, exacte lookup)
# --------------------------------------------------------------------------

def normalize_input(raw, vocabs):
    def field(norm_key, text_key, vocab, allow_prefix=False):
        if raw.get(norm_key):
            return raw[norm_key], "given"
        text = raw.get(text_key)
        if not text:
            return None, None
        hit = vocab.get(lookup_key(text))
        if hit:
            return hit, "vocabulary_lookup"
        if allow_prefix:
            value, word = prefix_rule(text)
            if value:
                return value, f"prefix_rule:{word}"
        return None, "not_normalized"

    action, action_basis = field("action_normalized", "action_text", vocabs["maintenance_action"], allow_prefix=True)
    unit, unit_basis = field("unit_normalized", "unit_text", vocabs["unit"])
    mat_norm, mat_basis = field("material_normalized", "material_text", vocabs["material"])
    mat_original = raw.get("material_text") or raw.get("material_normalized")
    quantity = raw.get("quantity")
    return {
        "object_id": raw["object_id"],
        "element_code": str(raw["element_code_internal"]) if raw.get("element_code_internal") else None,
        "action": action, "action_basis": action_basis,
        "unit": unit, "unit_basis": unit_basis,
        "material_original": mat_original, "material_normalized": mat_norm, "material_basis": mat_basis,
        "material_source": raw.get("material_source"),
        "material": material_id(mat_original if not mat_norm else None, mat_norm),
        "object_description": raw.get("object_description"),
        "quantity": None if quantity in (None, "") else format(Decimal(str(quantity)), "f"),
        "price_level_requested": raw.get("price_level_requested"),
        "vat_basis": raw.get("vat_basis"),
        "context": {k: raw.get(k) for k in CONTEXT_FIELDS},
    }


# --------------------------------------------------------------------------
# 2. Scope
# --------------------------------------------------------------------------

def assess_scope(item, kengetal, normalized_by_id):
    members = {}
    for r in kengetal["source_references"]:
        members.setdefault(tokens(r["object_description"]), []).append(r["observation_id"])
    excluded = {}
    for oid, reasons in kengetal["exclusion_reasons"].items():
        if any(x.startswith("HUMAN_NOT_COMPARABLE:") for x in reasons) and oid in normalized_by_id:
            desc = normalized_by_id[oid]["element"]["element_description_original"]
            excluded.setdefault(tokens(desc), []).append(oid)
    new = tokens(item["object_description"])
    evidence = {
        "rule": "token-equal object description (lowercase word tokens); no fuzzy matching",
        "input_description_tokens": list(new),
        "group_member_descriptions": sorted({r["object_description"] for r in kengetal["source_references"]}),
        "matched_member_observation_ids": sorted(members.get(new, [])),
        "matched_excluded_observation_ids": sorted(excluded.get(new, [])),
        "human_not_comparable_evidence": {oid: kengetal["exclusion_reasons"][oid]
                                          for oid in sorted(excluded.get(new, []))},
        "kengetal_decision_ids": list(kengetal["decision_ids"]),
    }
    if not new:
        return "HUMAN_REVIEW_REQUIRED", ["OBJECT_DESCRIPTION_MISSING"], evidence
    if new in members and new in excluded:
        return "HUMAN_REVIEW_REQUIRED", ["CONFLICTING_SCOPE_EVIDENCE"], evidence
    if new in members:
        return "EXACT_MATCH", [], evidence
    if new in excluded:
        return "MISMATCH", ["SCOPE_MISMATCH_HUMAN_NOT_COMPARABLE"], evidence
    return "HUMAN_REVIEW_REQUIRED", ["SCOPE_NOT_DETERMINISTIC"], evidence


# --------------------------------------------------------------------------
# 3. Retrieval + evaluatie
# --------------------------------------------------------------------------

def kengetal_material(k):
    return material_id(k["material"]["original"], k["material"]["normalized"])


def match_caveats(item, k):
    out = []
    q = item["quantity"]
    qmin, qmax = k["quantity"]["min"], k["quantity"]["max"]
    if q is None:
        out.append("QUANTITY_NOT_GIVEN")
    elif qmin is not None and not (Decimal(qmin) <= Decimal(q) <= Decimal(qmax)):
        out.append("QUANTITY_OUTSIDE_HISTORICAL_RANGE")
    else:
        out.append("QUANTITY_WITHIN_HISTORICAL_RANGE")
    pl = k["price_levels"]
    out.append("NOT_INDEXED")
    if pl["mixed_price_level"]:
        out.append("PRICE_LEVEL_MIXED")
    if pl["missing_price_level"]:
        out.append("PRICE_LEVEL_MISSING_IN_SOURCE")
    req = item["price_level_requested"]
    if req is not None and (pl["mixed_price_level"] or pl["missing_price_level"] or int(req) not in pl["years"]):
        out.append("REQUESTED_PRICE_LEVEL_NOT_REPRESENTED")
    if "element_text" in k["material_source"]:
        out.append("KENGETAL_MATERIAL_PARTLY_FROM_ELEMENT_TEXT")
    if item["vat_basis"] is None:
        out.append("VAT_BASIS_NOT_GIVEN")
    return out


def evaluate(raw_input, kengetallen_doc, normalized_by_id, vocabs, input_hashes, kengetallen_file):
    item = normalize_input(raw_input, vocabs)
    key = {"element_code": item["element_code"], "action": item["action"], "unit": item["unit"],
           "material": item["material"]}
    reasons, candidates, insufficient = [], [], []
    if not (item["element_code"] and item["action"] and item["unit"]):
        reasons.append("INPUT_KEY_INCOMPLETE")
    elif item["material"] is None:
        reasons.append("MATERIAL_UNKNOWN")
    else:
        for k in sorted(kengetallen_doc["kengetallen"], key=lambda x: x["kengetal_id"]):
            if tuple(k["candidate_key"]) == (item["element_code"], item["action"], item["unit"]) \
                    and kengetal_material(k) == item["material"]:
                (candidates if k["status"] == "AVAILABLE" else insufficient).append(k)
        if not candidates:
            reasons.append("KENGETAL_INSUFFICIENT_DATA" if insufficient else "NO_KENGETAL_FOR_KEY")

    evaluations = []
    for k in candidates:
        status, why, evidence = assess_scope(item, k, normalized_by_id)
        evaluations.append({"kengetal_id": k["kengetal_id"], "scope_status": status, "scope_reasons": why,
                            "scope_evidence": evidence})

    chosen = None
    viable = [e for e in evaluations if e["scope_status"] != "MISMATCH"]
    if not candidates:
        final, scope = "NO_SUITABLE_KENGETAL", "NOT_EVALUATED"
    elif not viable:
        final, scope = "NO_SUITABLE_KENGETAL", "MISMATCH"
        reasons += sorted({r for e in evaluations for r in e["scope_reasons"]})
    elif len(viable) > 1:
        final, scope = "HUMAN_REVIEW_REQUIRED", "HUMAN_REVIEW_REQUIRED"
        reasons.append("MULTIPLE_CANDIDATES")
    else:
        chosen = viable[0]
        scope = chosen["scope_status"]
        reasons += chosen["scope_reasons"]
        k = next(x for x in candidates if x["kengetal_id"] == chosen["kengetal_id"])
        if item["vat_basis"] and len(k["vat_basis"]) == 1 and k["vat_basis"][0] and k["vat_basis"][0] != item["vat_basis"]:
            reasons.append("VAT_BASIS_DIFFERS")
        final = "CANDIDATE_FOUND" if scope == "EXACT_MATCH" and not reasons else "HUMAN_REVIEW_REQUIRED"

    k = next((x for x in candidates if chosen and x["kengetal_id"] == chosen["kengetal_id"]), None)
    ref = k or (candidates[0] if candidates else None)   # alle kandidaten hebben per definitie dezelfde sleutel
    hard = {f: {"input": key[f],
                "candidate": (ref["candidate_key"][i] if i < 3 else kengetal_material(ref)) if ref else None,
                "equal": ref is not None}
            for i, f in enumerate(("element_code", "action", "unit", "material"))}
    result = {
        "match_result_id": None,
        "input_object_id": item["object_id"],
        "input_normalized": item,
        "retrieval_key": key,
        "retrieval_status": "CANDIDATES_RETRIEVED" if candidates else "NO_CANDIDATE",
        "candidate_kengetal_ids": [c["kengetal_id"] for c in candidates],
        "candidate_evaluations": evaluations,
        "candidate_kengetal_id": k["kengetal_id"] if k else None,
        "scope_status": scope,
        "final_status": final,
        "reasons": reasons,
        "hard_match_fields": hard,
        "scope_evidence": chosen["scope_evidence"] if chosen else {},
        "historical_range": None if not k else {
            "value_exact": k["value_exact"], "value_display": k["value_display"], "min_exact": k["min_exact"],
            "max_exact": k["max_exact"], "range_exact": k["range_exact"], "quantity_min": k["quantity"]["min"],
            "quantity_max": k["quantity"]["max"], "unit": k["unit"],
            "note": "Historisch kengetal v1: niet geïndexeerd, geen marktprijs of normprijs; prijs niet aangepast."},
        "historical_source_clusters": [] if not k else [
            {"source_cluster": c["source_cluster"], "contribution_exact": c["contribution_exact"],
             "observation_ids": c["observation_ids"], "price_levels": c["price_levels"]}
            for c in k["cluster_contributions"]],
        "price_levels": None if not k else dict(k["price_levels"], requested=item["price_level_requested"]),
        "caveats": {"match_caveats": match_caveats(item, k) if k else [],
                    "decision_caveats": dict(k["decision_caveats"]["counts"]) if k else {},
                    "observation_caveats": sorted({c for v in k["observation_caveats"].values() for c in v}) if k else []},
        "required_human_review": final == "HUMAN_REVIEW_REQUIRED",
        "provenance": {"kengetallen_file": kengetallen_file,
                       "kengetal_decision_ids": list(k["decision_ids"]) if k else [],
                       "kengetal_observation_ids": list(k["observation_ids"]) if k else [],
                       "insufficient_data_kengetal_ids": [x["kengetal_id"] for x in insufficient]},
        "rule_version": RULE_VERSION,
        "kengetallen_rule_version": kengetallen_doc["rules_version"],
        "input_hashes": input_hashes,
    }
    result["match_result_id"] = match_result_id(item, input_hashes, kengetallen_doc["rules_version"])
    return result


def match_result_id(item, input_hashes, kengetallen_rules_version):
    """Deterministische fingerprint van alles waarop het resultaat rust: matching-regelversie,
    kengetallen-regelversie, kengetallen-output, genormaliseerde observations, vocabularies en de
    genormaliseerde input. Geen tijdstempel of willekeur."""
    basis = json.dumps({"matching_rule_version": RULE_VERSION, "kengetallen_rule_version": kengetallen_rules_version,
                        "input_hashes": input_hashes, "input": item}, sort_keys=True, ensure_ascii=False)
    return "MR-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------
# Bestanden
# --------------------------------------------------------------------------

def paths(root):
    return {
        "kengetallen": os.path.join(root, "data", "kengetallen", "kengetallen_batch1.json"),
        "normalized": os.path.join(root, "data", "price_observations", "price_observations_batch1_normalized.json"),
        "vocab_dir": os.path.join(root, "vocabularies"),
    }


def load_context(root):
    p = paths(root)
    vocabs = {n: load_vocab_utf8(p["vocab_dir"], n) for n in ("maintenance_action", "unit", "material")}
    hashes = {
        "kengetallen_output_sha256": sha256_file(p["kengetallen"]),
        "normalized_observations_sha256": sha256_file(p["normalized"]),
        "vocabularies_sha256": {n: sha256_file(os.path.join(p["vocab_dir"], f"{n}.json"))
                                for n in ("maintenance_action", "unit", "material")},
    }
    kengetallen = json.load(open(p["kengetallen"], encoding="utf-8"))
    normalized = {o["observation_id"]: o for o in
                  json.load(open(p["normalized"], encoding="utf-8"))["observations"]}
    rel = os.path.relpath(p["kengetallen"], root).replace("\\", "/")
    return kengetallen, normalized, vocabs, hashes, rel


def match(root, raw_input, context=None):
    kengetallen, normalized, vocabs, hashes, rel = context or load_context(root)
    return evaluate(raw_input, kengetallen, normalized, vocabs, hashes, rel)


def validate_output(result, schema_path):
    import jsonschema
    schema = json.load(open(schema_path, encoding="utf-8"))
    return [f"{'/'.join(str(x) for x in e.path)}: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(result)]


def dump(result):
    return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON-bestand met één input-object")
    ap.add_argument("--out", help="optioneel: schrijf het resultaat naar dit bestand (niet onder data/)")
    args = ap.parse_args()
    raw = json.load(open(args.input, encoding="utf-8"))
    result = match(root, raw)
    errors = validate_output(result, os.path.join(root, "schemas", "match_result.schema.json"))
    if errors:
        print(f"SCHEMA-FOUTEN ({len(errors)}):", *errors[:20], sep="\n  ")
        sys.exit(1)
    if args.out:
        out = os.path.abspath(args.out)
        if out.startswith(os.path.join(root, "data") + os.sep):
            print("Weigert te schrijven onder data/: de matchinglaag schrijft geen historische kennis.")
            sys.exit(2)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump(result))
        print(f"-> {args.out}")
    else:
        sys.stdout.write(dump(result))


if __name__ == "__main__":
    main()
