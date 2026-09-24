#!/usr/bin/env python3
"""
build_comparability.py  (NORMALIZED PRICE OBSERVATIONS -> ELIGIBILITY -> SOURCE CLUSTERS -> PAREN)

Past de vergelijkbaarheidsregels versie 1 toe (docs/comparability_rules_v1.md):

  A. per observation: ELIGIBLE / ELIGIBLE_WITH_CAVEATS / NOT_ELIGIBLE / UNKNOWN
     (O1-O11 + D5), incl. derived_unit_price_per_execution waar toegestaan;
  C. source clusters uit data/price_observations/document_relations.json
     (D1-D4; D6 tariefgroepen; D7 bewust niet gebruikt);
  B. per kandidaatpaar uit verschillende clusters: COMPARABLE /
     COMPARABLE_WITH_CAVEATS / NOT_COMPARABLE / UNKNOWN (P1-P11);
  D. klasse per observation afgeleid uit haar paren (paren blijven bewaard).

Leest alleen: de genormaliseerde observations, de documentrelaties, de
verified-elementen (materiaal) en de goedgekeurde signaalwoorden. Schrijft
naar een aparte output (data/comparability/). Bron- en normalisatiedata worden
niet gewijzigd.

Geen kengetallen, geen gemiddelden/medianen/percentielen, geen scores, geen
indexatie, geen matching-aanbevelingen.

Gebruik:
    python scripts/build_comparability.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from itertools import combinations

RULES_VERSION = "comparability_rules_v1"

ELIG_RANK = {"ELIGIBLE": 0, "ELIGIBLE_WITH_CAVEATS": 1, "UNKNOWN": 2, "NOT_ELIGIBLE": 3}
PAIR_BEST = ["COMPARABLE", "COMPARABLE_WITH_CAVEATS", "UNKNOWN", "NOT_COMPARABLE"]

# O11: reviewredenen uit de normalisatielaag die een vergelijking raken
OPEN_REVIEW_BLOCKING = {"action_not_normalized", "conflicting_action_normalization", "unit_unknown",
                        "unit_missing_or_unreadable", "element_context_missing",
                        "element_code_mismatch_source_vs_verified"}
CLUSTER_RELATION_TYPES = {"version_of_same_mjop", "subplans_same_complex"}
QUANTITY_RATIO_LIMIT = Decimal("10")
# F7: letterlijke bronmarkering "(uitgevoerd JJJJ)" in de actietekst (DOC-005). De bron zegt alleen
# "Tijdens de schouw werd PO (schilderwerk) uitgevoerd"; wat de prijs van zulke rijen betekent is
# niet vastgesteld. Zulke observations blijven bestaan, maar zijn geen onafhankelijke input.
EXECUTED_MARKER = re.compile(r"\(uitgevoerd \d{4}\)", re.IGNORECASE)


# --------------------------------------------------------------------------
# Hulpfuncties
# --------------------------------------------------------------------------

def tokens(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def token_relation(a, b):
    """'equal', 'prefix' (de ene tokenreeks is het begin van de andere) of
    'differs'. None als een van beide leeg is."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return None
    if ta == tb:
        return "equal"
    short, long_ = (ta, tb) if len(ta) < len(tb) else (tb, ta)
    return "prefix" if long_[:len(short)] == short else "differs"


def is_incomplete(text):
    t = (text or "").strip()
    if not t:
        return False
    return t.count("(") != t.count(")") or t[-1] in "(-/&,"


def price_year(date_str):
    m = re.search(r"(\d{4})$", date_str or "")
    return int(m.group(1)) if m else None


def D(v):
    return None if v is None else Decimal(str(v))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_signals(path):
    return json.load(open(path, encoding="utf-8"))["signals"]


def find_signals(text, signals):
    """Alleen goedgekeurde signalen; token- of letterlijke match, geen fuzzy."""
    low = (text or "").lower()
    toks = tokens(text)
    found = []
    for s in signals:
        sig = s["signal"].lower()
        if s["match"] == "substring":
            hit = sig in low
        else:
            st = tokens(sig)
            hit = any(toks[i:i + len(st)] == st for i in range(len(toks) - len(st) + 1))
        if hit:
            found.append({"signal": s["signal"], "type": s["type"]})
    return found


# --------------------------------------------------------------------------
# A. Observation
# --------------------------------------------------------------------------

def material_of(obs, elements):
    """F8: bronvolgorde voor het materiaal. 1) verified-element (leidend, nooit
    overschreven); 2) anders material_from_text uit de normalisatielaag, alleen
    met status MATERIAL_FROM_TEXT en bron element_text; 3) anders onbekend.
    Spreken 1 en 2 elkaar tegen, dan blijft het materiaal onbekend."""
    el = elements.get(obs["element"]["element_id"]) if obs["element"]["element_id"] else None
    m = (el or {}).get("material") or {}
    verified = {"original": m.get("original_value"), "normalized": m.get("normalized_value")}
    nm = obs.get("material") or {}
    text = (nm.get("material_from_text") if nm.get("material_status") == "MATERIAL_FROM_TEXT"
            and nm.get("material_source") == "element_text" else None)
    if verified["original"]:
        if text and (text["normalized_value"] or text["original_value"].lower()) != \
                (verified["normalized"] or verified["original"].lower()):
            return {"original": None, "normalized": None, "source": "conflict_verified_vs_element_text"}
        return dict(verified, source="verified_element")
    if text:
        return {"original": text["original_value"], "normalized": text["normalized_value"], "source": "element_text"}
    return {"original": None, "normalized": None, "source": None}


def derive_per_execution(obs):
    """E1: prijs per uitvoering, alleen als alle voorwaarden aantoonbaar gelden."""
    p = obs["price"]
    qty = D(p["quantity_value"])
    amounts = [D(v) for v in p["annual_amounts"].values()]
    reasons = []
    if not qty or qty <= 0:
        reasons.append("quantity_not_positive")
    if not amounts:
        reasons.append("no_annual_amounts")
    if amounts and len(set(amounts)) > 1:
        reasons.append("annual_amounts_differ")
    if obs["validation"]["checks"].get("amount_reconciliation") != "consistent":
        reasons.append("row_total_not_reconciled")
    if p["total_scope"] not in ("ONE_EXECUTION", "MULTIPLE_EXECUTIONS"):
        reasons.append("total_scope_unknown")
    if obs["unit"]["unit_normalized"] in (None, "lump_sum"):
        reasons.append("unit_not_divisible")
    if reasons:
        return None, reasons
    return {
        "value": str((amounts[0] / qty).quantize(Decimal("0.01"))),
        "method": "annual_amount / quantity_value (Decimal, 2 decimalen)",
        "annual_amount_used": str(amounts[0]),
        "executions_in_window": len(amounts),
        "quantity_value": p["quantity_value"],
        "source_total_as_stated": p["total_as_stated"],
        "source_unit_price_calculated": p["unit_price_calculated"],
    }, []


def assess_observation(obs, elements, signals):
    status, reasons, caveats, info = "ELIGIBLE", [], [], []

    def worse(new):
        nonlocal status
        if ELIG_RANK[new] > ELIG_RANK[status]:
            status = new

    el, unit, price = obs["element"], obs["unit"], obs["price"]
    review_codes = {r["code"] for r in obs["review_reasons"]}

    # O1
    if unit["unit_normalized"] is None:
        worse("UNKNOWN"); reasons.append("UNIT_UNKNOWN")
    elif unit["unit_normalized"] == "lump_sum":
        worse("NOT_ELIGIBLE"); reasons.append("LUMP_SUM")
    elif unit["unit_normalized"] == "piece" and D(price["quantity_value"]) % 1 != 0:
        caveats.append("FRACTIONAL_PIECE_COUNT")
    # O2
    if not el["element_code_original"] or "element_context_missing" in review_codes:
        worse("UNKNOWN"); reasons.append("ELEMENT_CONTEXT_MISSING")
    # O3 (onvolledige omschrijving)
    if is_incomplete(el["element_description_original"]) or is_incomplete(obs["action"]["action_text_original"]):
        worse("UNKNOWN"); reasons.append("INCOMPLETE_DESCRIPTION")
    # O5/O6
    sig = find_signals(obs["action"]["action_text_original"], signals)
    for t in sorted({s["type"] for s in sig}):
        if t == "BUNDLED_COST":
            worse("NOT_ELIGIBLE"); reasons.append("BUNDLED_COST")
        else:
            caveats.append(t)
    # O7
    derived, not_derived = derive_per_execution(obs)
    if price["total_scope"] == "UNKNOWN":
        worse("UNKNOWN"); reasons.append("TOTAL_SCOPE_UNKNOWN")
    elif price["total_scope"] == "MULTIPLE_EXECUTIONS":
        if derived:
            info.append("PRICE_PER_EXECUTION_DERIVED")
        elif unit["unit_normalized"] not in (None, "lump_sum"):
            caveats.append("ROW_TOTAL_RATIO")  # alleen relevant bij een deelbare eenheid
    # O8
    if price["price_level_basis"] != "explicit":
        caveats.append("PRICE_LEVEL_ABSENT")
    # O9
    mat = material_of(obs, elements)
    if not mat["original"]:
        caveats.append("MATERIAL_UNKNOWN")
    elif "/" in mat["original"]:
        caveats.append("MIXED_MATERIAL")
    # O10
    if not el["element_code_internal"]:
        worse("NOT_ELIGIBLE"); reasons.append("NO_INTERNAL_CODE")
    label = (el.get("internal_code_label") or "").lower()
    act = obs["action"]["action_normalized"]
    if (label.startswith("binnenschilderwerk") and act == "exterior_painting") or \
       (label.startswith("buitenschilderwerk") and act == "interior_painting"):
        caveats.append("CODE_LABEL_MISMATCH")
    # O11
    for code in sorted(review_codes & OPEN_REVIEW_BLOCKING):
        if code != "element_context_missing":
            worse("UNKNOWN"); reasons.append(f"OPEN_REVIEW:{code}")
    # D5
    if obs["dependency_status"] == "UNKNOWN":
        worse("UNKNOWN"); reasons.append("UNRESOLVED_DEPENDENCY")

    if status == "ELIGIBLE" and caveats:
        status = "ELIGIBLE_WITH_CAVEATS"
    return {
        "eligibility": status,
        "eligibility_reasons": reasons,
        "caveats": sorted(set(caveats)),
        "info": info,
        "signals_found": sig,
        "material": mat,
        "derived_unit_price_per_execution": derived,
        "per_execution_not_derived_reasons": not_derived if not derived else [],
    }


# --------------------------------------------------------------------------
# C. Source clusters
# --------------------------------------------------------------------------

def build_clusters(document_ids, doc_relations):
    parent = {d: d for d in document_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    duplicates = {}
    for rel in doc_relations:
        if rel["type"] == "duplicate_source":
            duplicates[rel["secondary_document_id"]] = rel["primary_document_id"]
        elif rel["type"] in CLUSTER_RELATION_TYPES:
            a, b = rel["document_ids"]
            if a in parent and b in parent:
                parent[find(a)] = find(b)
    members = defaultdict(list)
    for d in document_ids:
        members[find(d)].append(d)
    cluster_of = {}
    for docs in members.values():
        cid = "SC-" + "+".join(sorted(docs))
        for d in docs:
            cluster_of[d] = cid
    for sec, prim in duplicates.items():
        cluster_of[sec] = cluster_of.get(prim)
    return cluster_of, duplicates


def independent_input(a, obs=None):
    """F6/F7: mag de afgeleide prijs als onafhankelijke input voor tariefgroepen /
    latere aggregatie dienen? Verandert eligibility en dependency_status niet."""
    reasons = []
    if not a["derived_unit_price_per_execution"]:
        reasons.append("NO_DERIVED_PRICE")
    if a["eligibility"] not in ("ELIGIBLE", "ELIGIBLE_WITH_CAVEATS"):
        reasons.append(f"ELIGIBILITY_{a['eligibility']}")
    if a["dependency_status"] == "POSSIBLY_DEPENDENT":
        reasons.append("POSSIBLY_DEPENDENT")
    if obs is not None and EXECUTED_MARKER.search(obs["action"]["action_text_original"] or ""):
        reasons.append("EXECUTED_DURING_INSPECTION_PRICE_MEANING_UNCLEAR")
    return not reasons, reasons


def tariff_groups(assessed):
    """D6: zelfde document, zelfde kandidaatsleutel, exact dezelfde prijs per
    uitvoering (jaarbedrag / hoeveelheid als exacte breuk, niet afgerond).
    Alleen observations die onafhankelijke input zijn (F4, F6)."""
    groups = defaultdict(list)
    for a in assessed:
        d = a["derived_unit_price_per_execution"]
        if a["independent_input"]:
            exact = Fraction(Decimal(d["annual_amount_used"])) / Fraction(Decimal(d["quantity_value"]))
            groups[(a["document_id"], tuple(a["candidate_key"]), exact)].append(a)
    out = []
    for (doc, key, exact), members in sorted(groups.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
        if len(members) > 1:
            out.append({"tariff_group_id": f"TG-{len(out) + 1:04d}", "document_id": doc, "candidate_key": list(key),
                        "derived_unit_price_per_execution": members[0]["derived_unit_price_per_execution"]["value"],
                        "price_equality_basis": "exact: annual_amount_used / quantity_value (breuk, geen afronding)",
                        "observation_ids": sorted(m["observation_id"] for m in members),
                        "note": "D6: één bronbijdrage (vastgelegd, niet samengevoegd)"})
    return out


# --------------------------------------------------------------------------
# B. Paren
# --------------------------------------------------------------------------

def material_relation(ma, mb):
    if not ma["original"] or not mb["original"]:
        return None
    if ma["normalized"] and mb["normalized"]:
        return "equal" if ma["normalized"] == mb["normalized"] else token_relation(ma["original"], mb["original"])
    return token_relation(ma["original"], mb["original"])


def assess_pair(a, b, obs_a, obs_b, content_reuse_pairs):
    hard, unknown, caveats, checks = [], [], [], {}
    if a["eligibility"] == "UNKNOWN" or b["eligibility"] == "UNKNOWN":
        unknown.append("OBSERVATION_UNKNOWN")
    # D5: een mogelijke, onopgeloste afhankelijkheid is geen onafhankelijke vergelijkingsbasis
    if "POSSIBLY_DEPENDENT" in (obs_a["dependency_status"], obs_b["dependency_status"]):
        unknown.append("POSSIBLY_DEPENDENT_OBSERVATION")
    # P1
    if obs_a["unit"]["unit_normalized"] != obs_b["unit"]["unit_normalized"]:
        hard.append("UNIT_DIFFERS")
    # P2 / P8
    rel_obj = token_relation(obs_a["element"]["element_description_original"],
                             obs_b["element"]["element_description_original"])
    checks["object_description"] = rel_obj
    if rel_obj == "prefix":
        caveats.append("GENERIC_VS_SPECIFIC_OBJECT")
    elif rel_obj in ("differs", None):
        unknown.append("OBJECT_EQUIVALENCE_REQUIRES_REVIEW")
    # P3
    rel_act = token_relation(obs_a["action"]["action_text_original"], obs_b["action"]["action_text_original"])
    checks["action_text"] = rel_act
    if rel_act == "prefix":
        caveats.append("ACTION_TEXT_VARIANT")
    elif rel_act in ("differs", None):
        unknown.append("ACTION_EQUIVALENCE_REQUIRES_REVIEW")
    # P4 / P9
    rel_mat = material_relation(a["material"], b["material"])
    checks["material"] = rel_mat
    if rel_mat == "differs":
        hard.append("MATERIAL_DIFFERS")
    elif rel_mat == "prefix":
        caveats.append("MATERIAL_VARIANT")
    # P5
    va, vb = obs_a["price"]["vat_basis"], obs_b["price"]["vat_basis"]
    checks["vat_basis"] = [va, vb]
    if va is None or vb is None:  # een of beide kanten onbekend: geen aantoonbaar verschil
        unknown.append("VAT_BASIS_UNKNOWN")
    elif va != vb:
        hard.append("VAT_BASIS_DIFFERS")
    # P6
    ya, yb = price_year(obs_a["price"]["price_level_date"]), price_year(obs_b["price"]["price_level_date"])
    checks["price_level_year"] = [ya, yb]
    if ya and yb and ya != yb:
        caveats.append("PRICE_LEVEL_DIFFERENCE")
    # P7
    qa, qb = D(obs_a["price"]["quantity_value"]), D(obs_b["price"]["quantity_value"])
    if qa and qb:
        ratio = max(qa, qb) / min(qa, qb)
        checks["quantity_ratio"] = str(ratio.quantize(Decimal("0.01")))
        if ratio > QUANTITY_RATIO_LIMIT:
            caveats.append("QUANTITY_SCALE_DIFFERENCE")
    # P11 (alleen met expliciet bewijs)
    if frozenset((obs_a["document_id"], obs_b["document_id"])) in content_reuse_pairs:
        caveats.append("CONTENT_REUSE")
    # P10: observation-voorbehouden gaan mee
    side = {"a": a["caveats"], "b": b["caveats"]}

    if hard:
        cls = "NOT_COMPARABLE"
    elif unknown:
        cls = "UNKNOWN"
    elif caveats or side["a"] or side["b"]:
        cls = "COMPARABLE_WITH_CAVEATS"
    else:
        cls = "COMPARABLE"
    return {"class": cls, "hard_violations": hard, "unknown_reasons": unknown, "pair_caveats": sorted(set(caveats)),
            "observation_caveats": side, "checks": checks}


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build(project_root, normalized_path=None):
    normalized_path = normalized_path or os.path.join(project_root, "data", "price_observations",
                                                      "price_observations_batch1_normalized.json")
    rel_path = os.path.join(project_root, "data", "price_observations", "document_relations.json")
    sig_path = os.path.join(project_root, "vocabularies", "comparability_signal_words.json")
    norm = json.load(open(normalized_path, encoding="utf-8"))
    doc_relations = json.load(open(rel_path, encoding="utf-8"))["relations"]
    signals = load_signals(sig_path)
    elements = {}
    for p in sorted(os.listdir(os.path.join(project_root, "data", "verified"))):
        if p.endswith(".json"):
            for e in json.load(open(os.path.join(project_root, "data", "verified", p), encoding="utf-8"))["elements"]:
                elements[e["element_id"]] = e

    result = evaluate(norm["observations"], doc_relations, elements, signals)
    return {
        "rules_version": RULES_VERSION,
        "rules_document": "docs/comparability_rules_v1.md",
        "inputs": {
            "normalized_observations": os.path.relpath(normalized_path, project_root).replace("\\", "/"),
            "normalized_observations_sha256": sha256_file(normalized_path),
            "document_relations_sha256": sha256_file(rel_path),
            "signal_words_sha256": sha256_file(sig_path),
        },
        "note": ("Vergelijkbaarheid volgens regels v1. Geen kengetallen, gemiddelden, medianen, scores, indexatie "
                 "of matching-aanbevelingen. Bronwaarden ongewijzigd; derived_unit_price_per_execution is een "
                 "afgeleide waarde naast de bronprijs."),
        **result,
    }


def evaluate(observations, doc_relations, elements, signals):
    """Kern zonder bestands-I/O: eligibility, clusters, paren, afgeleide klassen."""
    doc_ids = sorted({o["document_id"] for o in observations} |
                     {d for r in doc_relations for d in r.get("document_ids", [])} |
                     {r.get("primary_document_id") for r in doc_relations if r.get("primary_document_id")})
    cluster_of, duplicates = build_clusters(doc_ids, doc_relations)
    content_reuse_pairs = {frozenset(r["document_ids"]) for r in doc_relations
                           if r.get("content_reuse_evidence") and r.get("document_ids")}

    assessed = []
    by_id = {}
    for o in observations:
        a = assess_observation(o, elements, signals)
        a.update(observation_id=o["observation_id"], document_id=o["document_id"],
                 source_cluster=cluster_of[o["document_id"]], dependency_status=o["dependency_status"],
                 candidate_key=(o["element"]["element_code_internal"], o["action"]["action_normalized"],
                                o["unit"]["unit_normalized"]))
        assessed.append(a)
        by_id[o["observation_id"]] = o

    # kandidaatparen
    groups = defaultdict(list)
    for a in assessed:
        if a["eligibility"] != "NOT_ELIGIBLE" and all(a["candidate_key"]):
            groups[a["candidate_key"]].append(a)
    pairs, same_source = [], []
    for key in sorted(groups, key=str):
        for x, y in combinations(sorted(groups[key], key=lambda r: r["observation_id"]), 2):
            if x["source_cluster"] == y["source_cluster"]:
                same_source.append({"observation_ids": [x["observation_id"], y["observation_id"]],
                                    "source_cluster": x["source_cluster"], "candidate_key": list(key)})
                continue
            res = assess_pair(x, y, by_id[x["observation_id"]], by_id[y["observation_id"]], content_reuse_pairs)
            res.update(pair_id=f"PAIR-{len(pairs) + 1:05d}", candidate_key=list(key),
                       observation_ids=[x["observation_id"], y["observation_id"]],
                       source_clusters=[x["source_cluster"], y["source_cluster"]])
            pairs.append(res)

    # D. klasse per observation
    pair_idx = defaultdict(list)
    for p in pairs:
        for oid in p["observation_ids"]:
            pair_idx[oid].append(p)
    for a in assessed:
        mine = pair_idx.get(a["observation_id"], [])
        a["pair_ids"] = [p["pair_id"] for p in mine]
        if a["eligibility"] == "NOT_ELIGIBLE":
            a["comparison_class"], a["comparison_class_reason"] = "NOT_COMPARABLE", "NOT_ELIGIBLE"
        elif a["eligibility"] == "UNKNOWN":
            a["comparison_class"], a["comparison_class_reason"] = "UNKNOWN", "OBSERVATION_UNKNOWN"
        elif not mine:
            a["comparison_class"], a["comparison_class_reason"] = "NOT_COMPARABLE", "NO_INDEPENDENT_COUNTERPART"
        else:
            best = min(mine, key=lambda p: PAIR_BEST.index(p["class"]))
            a["comparison_class"], a["comparison_class_reason"] = best["class"], f"best_pair:{best['pair_id']}"
        a["candidate_key"] = list(a["candidate_key"])

    for a in assessed:
        a["independent_input"], a["independent_input_exclusion_reasons"] = independent_input(a, by_id[a["observation_id"]])
    tgs = tariff_groups(assessed)
    tg_of = {oid: t["tariff_group_id"] for t in tgs for oid in t["observation_ids"]}
    for a in assessed:
        a["tariff_group_id"] = tg_of.get(a["observation_id"])

    clusters = sorted({c for d, c in cluster_of.items() if d not in duplicates})
    summary = {
        "observations": len(assessed),
        "eligibility": dict(Counter(a["eligibility"] for a in assessed)),
        "observation_comparison_class": dict(Counter(a["comparison_class"] for a in assessed)),
        "pairs": len(pairs),
        "pair_class": dict(Counter(p["class"] for p in pairs)),
        "same_source_links": len(same_source),
        "source_clusters": len(clusters),
        "tariff_groups": len(tgs),
        "derived_price_per_execution": sum(1 for a in assessed if a["derived_unit_price_per_execution"]),
        "derived_price_per_execution_eligible": sum(
            1 for a in assessed if a["derived_unit_price_per_execution"]
            and a["eligibility"] in ("ELIGIBLE", "ELIGIBLE_WITH_CAVEATS")),
        "derived_price_per_execution_independent_input": sum(1 for a in assessed if a["independent_input"]),
        "eligibility_reasons": dict(Counter(r for a in assessed for r in a["eligibility_reasons"])),
        "observation_caveats": dict(Counter(c for a in assessed for c in a["caveats"])),
        "pair_hard_violations": dict(Counter(h for p in pairs for h in p["hard_violations"])),
        "pair_unknown_reasons": dict(Counter(u for p in pairs for u in p["unknown_reasons"])),
        "pair_caveats": dict(Counter(c for p in pairs for c in p["pair_caveats"])),
    }
    return {
        "summary": summary,
        "source_clusters": [{"source_cluster": c, "document_ids": sorted(d for d, cc in cluster_of.items()
                                                                          if cc == c and d not in duplicates)}
                            for c in clusters],
        "duplicate_documents": [{"document_id": s, "duplicate_of": p, "source_cluster": cluster_of.get(s)}
                                for s, p in sorted(duplicates.items())],
        "observations": assessed,
        "pairs": pairs,
        "same_source_links": same_source,
        "tariff_groups": tgs,
    }


def validate_output(result, schema_path):
    import jsonschema
    schema = json.load(open(schema_path, encoding="utf-8"))
    errors = []
    obs_v = jsonschema.Draft7Validator({**schema["definitions"]["observation_assessment"],
                                        "definitions": schema["definitions"]})
    pair_v = jsonschema.Draft7Validator({**schema["definitions"]["pair"], "definitions": schema["definitions"]})
    for a in result["observations"]:
        errors += [f"{a['observation_id']}: {e.message}" for e in obs_v.iter_errors(a)]
    for p in result["pairs"]:
        errors += [f"{p['pair_id']}: {e.message}" for e in pair_v.iter_errors(p)]
    return errors


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("data", "comparability", "comparability_batch1.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = build(root)
    errors = validate_output(result, os.path.join(root, "schemas", "comparability.schema.json"))
    if errors:
        print(f"SCHEMA-FOUTEN ({len(errors)}):")
        for e in errors[:20]:
            print("  ", e)
        sys.exit(1)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    if args.dry_run:
        print("\n--dry-run: niets geschreven.")
        return
    out = os.path.join(root, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
