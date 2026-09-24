#!/usr/bin/env python3
"""
build_kengetallen.py  (HUMAN-REVIEWED GROUPS -> KENGETALLEN v1)

Past docs/kengetallen_rules_v1.md toe op:
  - data/price_observations/price_observations_batch1_normalized.json
  - data/comparability/comparability_batch1.json
  - data/review_decisions/human_decision_records.json
en schrijft data/kengetallen/kengetallen_batch1.json
(schema: schemas/kengetal.schema.json).

Groepen ontstaan uitsluitend uit expliciete ACTIVE human decisions:
  1. kandidaatsets = verbonden delen van de graaf met menselijke
     COMPARABLE / COMPARABLE_WITH_CAVEATS-beslissingen (alleen om kandidaten te
     vinden);
  2. een kandidaatset is pas een vergelijkbare groep als regel 2 volledig
     geldt: één sleutel, één bekend materiaal, independent_input, ELKE
     combinatie tussen verschillende source clusters menselijk C/CW en geen
     NOT_COMPARABLE. Er wordt geen transitiviteit aangenomen en geen
     deelverzameling gezocht; faalt de controle, dan INSUFFICIENT_DATA met
     reden.
Daarna: post consolidation (regel 3) -> cluster contribution = mediaan van
postwaarden (regel 4) -> kengetal = mediaan van contributions bij >= 3 source
clusters (regels 6-8). Exacte Decimal-berekening, geen weging, geen
indexatie, geen score of confidence. Er ontstaat nooit een kengetal alleen
omdat observations dezelfde code/actie/eenheid hebben.

Versies (regels 15-16): bestaat de output al met dezelfde inhoud, dan wordt
niets geschreven. Wijkt de inhoud af, dan wordt niet overschreven tenzij
--supersede: de oude versie wordt dan bewaard in data/kengetallen/history/ en
de nieuwe verwijst ernaar. --check meldt of de bestaande output nog bij de
huidige invoer hoort.

Gebruik:
    python scripts/build_kengetallen.py [--dry-run | --check | --supersede]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from itertools import combinations

RULES_VERSION = "kengetallen_rules_v1"
RULES_DOCUMENT = "docs/kengetallen_rules_v1.md"
POSITIVE = ("COMPARABLE", "COMPARABLE_WITH_CAVEATS")
# regel 3: vaste, goedgekeurde gevelzijde-lijst (niet automatisch uitbreiden)
FACADE_SIDE_WORDS = frozenset({"achter", "voor", "achterzijde", "voorzijde", "achtergevel", "voorgevel"})
MIN_SOURCE_CLUSTERS = 3
DISPLAY = Decimal("0.01")  # alleen presentatie; zelfde afronding als comparability (ROUND_HALF_EVEN)
CALCULATION_METHOD = ("median of source-cluster contributions; contribution = median of post values within the "
                      "cluster; post value = median of its observations' derived_unit_price_per_execution "
                      "(annual_amount_used / quantity_value); exact Decimal; no weighting; no indexation")


# --------------------------------------------------------------------------
# Hulpfuncties
# --------------------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dec(x):
    return None if x is None else format(x, "f")


def display(x):
    return None if x is None else format(x.quantize(DISPLAY), "f")


def median(values):
    """Standaard mediaan op exacte Decimals; even aantal -> gemiddelde van de twee middelste."""
    v = sorted(values)
    n = len(v)
    if not n:
        return None
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def tokens(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def exact_price(assessment):
    d = assessment["derived_unit_price_per_execution"]
    return Decimal(d["annual_amount_used"]) / Decimal(d["quantity_value"])


def primary_repr(norm):
    return next(r for r in norm["source_ref"]["source_representations"] if r["role"] == "primary_financial_row")


def material_id(material):
    if not material or not material.get("original"):
        return None
    return material.get("normalized") or material["original"].strip().lower()


def price_year(date_str):
    m = re.search(r"(\d{4})$", date_str or "")
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# Regel 3: post consolidation
# --------------------------------------------------------------------------

def same_post(x, y, norm):
    """Reden (tekst) als x en y volgens regel 3 dezelfde post zijn, anders None."""
    nx, ny = norm[x], norm[y]
    if nx["document_id"] != ny["document_id"]:
        return None
    ex, ey = primary_repr(nx).get("element_line"), primary_repr(ny).get("element_line")
    if not ex or ex != ey:
        return None
    if nx["action"]["action_normalized"] != ny["action"]["action_normalized"]:
        return None
    if nx["unit"]["unit_normalized"] != ny["unit"]["unit_normalized"]:
        return None
    if nx["price"]["quantity_value"] != ny["price"]["quantity_value"]:
        return None
    if nx["element"]["element_description_original"] != ny["element"]["element_description_original"]:
        return None  # ander inhoudelijk verschil in de bron
    tx, ty = tokens(nx["action"]["action_text_original"]), tokens(ny["action"]["action_text_original"])
    diff = set(tx) ^ set(ty)
    if not diff or not diff <= FACADE_SIDE_WORDS:
        return None
    if [t for t in tx if t not in FACADE_SIDE_WORDS] != [t for t in ty if t not in FACADE_SIDE_WORDS]:
        return None
    return (f"zelfde element_line (p{ex['page']} r{ex['line']}), action, unit en quantity; "
            f"actietekst verschilt alleen in gevelzijde {sorted(diff)}")


def consolidate(members, norm):
    """Posten binnen één cluster; deterministisch op observation_id."""
    parent = {m: m for m in members}

    def find(a):
        while parent[a] != a:
            a = parent[a]
        return a

    pair_reasons = []
    for x, y in combinations(sorted(members), 2):
        r = same_post(x, y, norm)
        if r:
            pair_reasons.append((x, r))
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[max(rx, ry)] = min(rx, ry)
    groups, reasons = defaultdict(list), defaultdict(list)
    for m in sorted(members):
        groups[find(m)].append(m)
    for x, r in pair_reasons:
        if r not in reasons[find(x)]:
            reasons[find(x)].append(r)
    return [(ids, "; ".join(reasons[root]) if len(ids) > 1 else None) for root, ids in sorted(groups.items())]


# --------------------------------------------------------------------------
# Groepen en kengetallen
# --------------------------------------------------------------------------

def candidate_sets(decisions):
    """Kandidaatsets: verbonden delen van de C/CW-graaf. Alleen om kandidaten te vinden;
    de geldigheid wordt apart en volledig gecontroleerd (geen transitiviteit)."""
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            a = parent[a]
        return a

    for r in decisions:
        if r["decision"] in POSITIVE:
            a, b = sorted(r["observation_ids"])
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    sets = defaultdict(set)
    for n in list(parent):
        sets[find(n)].add(n)
    return [sorted(s) for _, s in sorted(sets.items())]


def kengetal_id(key, material, members):
    slug = re.sub(r"[^a-z0-9]+", "_", (material_id(material) or "unknown").lower()).strip("_")
    digest = hashlib.sha256(",".join(sorted(members)).encode()).hexdigest()[:8]
    return "KG-" + "-".join(str(k) for k in key) + f"-{slug}-{digest}"


def assess_group(members, obs, norm, active):
    reasons, exclusion = [], defaultdict(list)
    for i in members:
        if not obs[i]["independent_input"]:
            exclusion[i].append("NOT_INDEPENDENT_INPUT:" + ",".join(obs[i]["independent_input_exclusion_reasons"]))
    usable = [i for i in members if i not in exclusion]
    usable_set = set(usable)
    by_pair = {frozenset(r["observation_ids"]): r for r in active}

    # menselijke NOT_COMPARABLE: binnen de groep blokkeert, naar buiten wordt vastgelegd
    related_nc = []
    for r in active:
        if r["decision"] != "NOT_COMPARABLE":
            continue
        a, b = r["observation_ids"]
        if a in usable_set and b in usable_set:
            reasons.append(f"NOT_COMPARABLE_WITHIN_GROUP:{r['decision_id']}")
        elif (a in usable_set) != (b in usable_set):
            outsider = b if a in usable_set else a
            exclusion[outsider].append(f"HUMAN_NOT_COMPARABLE:{r['decision_id']}")
            related_nc.append(r["decision_id"])

    if not usable:
        reasons.append("NO_INDEPENDENT_OBSERVATIONS")
    keys = {tuple(obs[i]["candidate_key"]) for i in usable}
    if len(keys) > 1:
        reasons.append("MIXED_CANDIDATE_KEY")
    key = sorted(keys, key=str)[0] if keys else (None, None, None)
    mats = {material_id(obs[i].get("material")) for i in usable}
    if None in mats:
        reasons.append("MATERIAL_UNKNOWN")
    if len(mats - {None}) > 1:
        reasons.append("MATERIAL_DIFFERS")
    ref_material = next((obs[i]["material"] for i in usable if material_id(obs[i].get("material"))), {})

    cluster_of = {i: obs[i]["source_cluster"] for i in usable}
    missing = [[x, y] for x, y in combinations(usable, 2) if cluster_of[x] != cluster_of[y]
               and (frozenset((x, y)) not in by_pair or by_pair[frozenset((x, y))]["decision"] not in POSITIVE)]
    if missing:
        reasons.append("INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW")

    # posten en cluster contributions
    by_cluster = defaultdict(list)
    for i in usable:
        by_cluster[cluster_of[i]].append(i)
    kid = kengetal_id(key, ref_material, members)
    posts, contributions, post_of = [], [], {}
    for c in sorted(by_cluster):
        c_posts = []
        for ids, why in consolidate(by_cluster[c], norm):
            pid = f"{kid}-POST-{len(posts) + 1:02d}"
            value = median(exact_price(obs[i]) for i in ids)
            posts.append({"post_id": pid, "source_cluster": c, "document_id": norm[ids[0]]["document_id"],
                          "observation_ids": ids, "element_line": primary_repr(norm[ids[0]]).get("element_line"),
                          "consolidated": len(ids) > 1, "consolidation_reason": why,
                          "post_value_exact": dec(value)})
            c_posts.append((pid, value))
            for i in ids:
                post_of[i] = pid
        contrib = median(v for _, v in c_posts)
        contributions.append({"source_cluster": c, "contribution_exact": dec(contrib),
                              "contribution_display": display(contrib), "post_ids": [p for p, _ in c_posts],
                              "observation_ids": sorted(by_cluster[c]),
                              "price_levels": sorted({norm[i]["price"]["price_level_date"] for i in by_cluster[c]},
                                                     key=lambda s: (s is None, s or ""))})
    if len(contributions) < MIN_SOURCE_CLUSTERS:
        reasons.append(f"FEWER_THAN_{MIN_SOURCE_CLUSTERS}_SOURCE_CLUSTERS:{len(contributions)}")

    values = [Decimal(c["contribution_exact"]) for c in contributions]
    status = "AVAILABLE" if not reasons else "INSUFFICIENT_DATA"
    value = median(values) if status == "AVAILABLE" else None
    lo, hi = (min(values), max(values)) if values else (None, None)

    # prijspeil (regel 11)
    pl_obs = {i: norm[i]["price"]["price_level_date"] for i in usable}
    years = sorted({price_year(d) for d in pl_obs.values() if price_year(d)})
    mixed, missing_pl = len(years) > 1, any(d is None for d in pl_obs.values())
    note = "Historisch, niet geïndexeerd; geen marktprijs of normprijs."
    if mixed or missing_pl:
        span = f"{years[0]}–{years[-1]}" if len(years) > 1 else (str(years[0]) if years else "onbekend")
        note += (f" Prijspeilen {span}" + (" en ontbrekend" if missing_pl else "") +
                 ": niet presenteren als prijs van één specifiek jaar.")
    elif years:
        note += f" Prijspeil {years[0]}."

    group_decisions = sorted((r for r in active if set(r["observation_ids"]) <= usable_set),
                             key=lambda r: r["decision_id"])
    quantities = [Decimal(norm[i]["price"]["quantity_value"]) for i in usable if norm[i]["price"]["quantity_value"]]
    refs = []
    for i in usable:
        n, a, p = norm[i], obs[i], primary_repr(norm[i])
        d = a["derived_unit_price_per_execution"] or {}
        refs.append({
            "observation_id": i, "document_id": n["document_id"], "source_cluster": a["source_cluster"],
            "post_id": post_of.get(i), "page": p["page"], "line": p["line"], "element_line": p.get("element_line"),
            "source_text": p["source_text"], "object_description": n["element"]["element_description_original"],
            "action_text": n["action"]["action_text_original"], "quantity": n["price"]["quantity_value"],
            "unit_original": n["unit"]["unit_original"],
            "price_per_execution_exact": dec(exact_price(a)) if d else None,
            "price_per_execution_display": d.get("value"), "executions_in_window": d.get("executions_in_window"),
            "cycle_start_year": n["price"]["cycle_start_year"], "cycle_length_years": n["price"]["cycle_length_years"],
            "price_level_date": n["price"]["price_level_date"], "vat_basis": n["price"]["vat_basis"],
            "material": a.get("material") or {}, "independent_input": a["independent_input"],
            "caveats": list(a["caveats"]),
        })
    return {
        "kengetal_id": kid,
        "candidate_key": list(key),
        "element_code": key[0], "action": key[1], "unit": key[2],
        "material": {"original": ref_material.get("original"), "normalized": ref_material.get("normalized")},
        "material_source": sorted({(obs[i].get("material") or {}).get("source") for i in usable}, key=str),
        "vat_basis": sorted({norm[i]["price"]["vat_basis"] for i in usable}, key=str),
        "status": status,
        "insufficient_data_reasons": reasons,
        "value_exact": dec(value), "value_display": display(value),
        "min_exact": dec(lo), "max_exact": dec(hi), "range_exact": dec(hi - lo) if values else None,
        "min_display": display(lo), "max_display": display(hi), "range_display": display(hi - lo) if values else None,
        "calculation_method": CALCULATION_METHOD,
        "source_cluster_ids": [c["source_cluster"] for c in contributions],
        "source_cluster_count": len(contributions),
        "cluster_contributions": contributions,
        "posts": posts,
        "observation_ids": usable,
        "observations_per_cluster": {c: sorted(v) for c, v in sorted(by_cluster.items())},
        "excluded_observation_ids": sorted(exclusion),
        "exclusion_reasons": {k: v for k, v in sorted(exclusion.items())},
        "decision_ids": [r["decision_id"] for r in group_decisions] + sorted(set(related_nc)),
        "human_review_complete": not missing and bool(usable),
        "missing_cross_cluster_reviews": missing,
        "rule_version": RULES_VERSION,
        "price_levels": {"per_observation": pl_obs,
                         "per_cluster": {c["source_cluster"]: c["price_levels"] for c in contributions},
                         "years": years, "mixed_price_level": mixed, "missing_price_level": missing_pl,
                         "indexation": "none", "presentation_note": note},
        "decision_caveats": {
            "by_decision": [{"decision_id": r["decision_id"], "pair_id": r["pair_id"], "decision": r["decision"],
                             "system_class": r["system_class"], "decision_caveats": list(r["decision_caveats"])}
                            for r in group_decisions],
            "counts": dict(sorted(Counter(c for r in group_decisions for c in r["decision_caveats"]).items())),
        },
        "observation_caveats": {i: list(obs[i]["caveats"]) for i in usable},
        "quantity": {"min": dec(min(quantities)) if quantities else None,
                     "max": dec(max(quantities)) if quantities else None,
                     "max_min_ratio": dec((max(quantities) / min(quantities)).quantize(DISPLAY)) if quantities else None,
                     "note": "Hoeveelheid is bronkenmerk; geen schaalcorrectie in v1."},
        "source_references": refs,
    }


def evaluate(normalized_observations, comparability_observations, decision_records):
    """Kern zonder bestands-I/O."""
    norm = {o["observation_id"]: o for o in normalized_observations}
    obs = {a["observation_id"]: a for a in comparability_observations}
    active = [r for r in decision_records if r["status"] == "ACTIVE"]
    kengetallen = [assess_group(members, obs, norm, active) for members in candidate_sets(active)]
    kengetallen.sort(key=lambda k: k["kengetal_id"])
    summary = {
        "candidate_groups": len(kengetallen),
        "status": dict(Counter(k["status"] for k in kengetallen)),
        "insufficient_data_reasons": dict(Counter(r.split(":")[0] for k in kengetallen
                                                  for r in k["insufficient_data_reasons"])),
        "active_human_decisions": len(active),
        "human_positive_decisions": sum(1 for r in active if r["decision"] in POSITIVE),
        "human_not_comparable_decisions": sum(1 for r in active if r["decision"] == "NOT_COMPARABLE"),
    }
    return summary, kengetallen


def paths(root):
    return {
        "normalized": os.path.join(root, "data", "price_observations", "price_observations_batch1_normalized.json"),
        "comparability": os.path.join(root, "data", "comparability", "comparability_batch1.json"),
        "decisions": os.path.join(root, "data", "review_decisions", "human_decision_records.json"),
        "rules": os.path.join(root, RULES_DOCUMENT),
    }


def input_hashes(root):
    p = paths(root)
    return {"normalized_observations_sha256": sha256_file(p["normalized"]),
            "comparability_output_sha256": sha256_file(p["comparability"]),
            "human_decisions_sha256": sha256_file(p["decisions"]),
            "rules_document_sha256": sha256_file(p["rules"])}


def build(root, generated_at=None):
    p = paths(root)
    normalized = json.load(open(p["normalized"], encoding="utf-8"))
    comparability = json.load(open(p["comparability"], encoding="utf-8"))
    decisions = json.load(open(p["decisions"], encoding="utf-8"))
    summary, kengetallen = evaluate(normalized["observations"], comparability["observations"], decisions["records"])
    return {
        "rules_version": RULES_VERSION,
        "rules_document": RULES_DOCUMENT,
        "comparability_rules_version": comparability["rules_version"],
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": input_hashes(root),
        "supersedes": None,
        "note": ("Kengetallen v1: mediaan van source-cluster contributions van volledig menselijk beoordeelde "
                 "vergelijkbare groepen met minimaal 3 source clusters. Historisch, niet geïndexeerd, geen "
                 "marktprijs of normprijs. Geen weging, score of confidence."),
        "summary": summary,
        "kengetallen": kengetallen,
    }


def validate_output(result, schema_path):
    import jsonschema
    schema = json.load(open(schema_path, encoding="utf-8"))
    return [f"{'/'.join(str(x) for x in e.path)}: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(result)]


def content(result):
    """Inhoud zonder generatietijdstip en versieverwijzing (voor vergelijking)."""
    return {k: v for k, v in result.items() if k not in ("generated_at", "supersedes")}


def dump(result):
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("data", "kengetallen", "kengetallen_batch1.json"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="meld of de bestaande output bij de huidige invoer hoort")
    ap.add_argument("--supersede", action="store_true", help="vervang een afwijkende bestaande versie (oude bewaard)")
    args = ap.parse_args()
    out = os.path.join(root, args.out)
    existing = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else None

    if args.check:
        if existing is None:
            print("GEEN OUTPUT"); sys.exit(1)
        stale = existing["inputs"] != input_hashes(root) or existing["rules_version"] != RULES_VERSION
        print("OPNIEUW CONTROLEREN/OPBOUWEN: invoer of regels gewijzigd" if stale else "ACTUEEL")
        sys.exit(1 if stale else 0)

    result = build(root)
    errors = validate_output(result, os.path.join(root, "schemas", "kengetal.schema.json"))
    if errors:
        print(f"SCHEMA-FOUTEN ({len(errors)}):")
        for e in errors[:20]:
            print("  ", e)
        sys.exit(1)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    for k in result["kengetallen"]:
        print(f"  {k['kengetal_id']}: {k['status']} {k['value_display'] or '-'} "
              f"({k['source_cluster_count']} clusters) {k['insufficient_data_reasons']}")
    if args.dry_run:
        print("\n--dry-run: niets geschreven.")
        return
    if existing is not None:
        if content(existing) == content(result):
            print(f"\nongewijzigd: {args.out} (niets geschreven)")
            return
        if not args.supersede:
            print(f"\nNIET GESCHREVEN: {args.out} bestaat met andere inhoud. Bestaande versies worden niet "
                  "stilzwijgend overschreven; gebruik --supersede om de oude versie te bewaren en te vervangen.")
            sys.exit(2)
        old_sha = sha256_file(out)
        hist = os.path.join(os.path.dirname(out), "history",
                            os.path.basename(out).replace(".json", f".{old_sha[:12]}.json"))
        os.makedirs(os.path.dirname(hist), exist_ok=True)
        shutil.copyfile(out, hist)  # oude versie byte-exact bewaren
        result["supersedes"] = {"file": os.path.relpath(hist, root).replace("\\", "/"), "sha256": old_sha}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(result))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
