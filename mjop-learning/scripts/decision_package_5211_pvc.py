#!/usr/bin/env python3
"""
decision_package_5211_pvc.py - compact menselijk beslispakket voor 5211|replace|m1, materiaal pvc (alleen lezen).

Bouwt uit de huidige canonieke lagen en comparability review v2:
  - het bestaande kengetal KG-5211-replace-m1-pvc-* (status, waarde, clusters, beslissingen);
  - alle independent_input pvc-observations van deze candidate key en hun source clusters;
  - elk cross-cluster pvc-paar zonder ACTIVE positieve beslissing, met alle velden voor de beoordeling en de
    reviewfamilie waarin het zit (en de vorige family-id uit het pakket vóór het materiaalbesluit);
  - de inhoudelijke controle per paar (zelfde actie, pvc, m1, geen relatie; verschil alleen prijspeil,
    hoeveelheid, prijs) - afwijkingen worden expliciet gemeld;
  - simulaties met de BESTAANDE kengetalregels (build_kengetallen.evaluate) per open familie voor COMPARABLE,
    COMPARABLE_WITH_CAVEATS en NOT_COMPARABLE, en voor de combinaties. Een simulatie is geen besluit en wordt
    nergens vastgelegd.

Er wordt niets toegepast: geen beslissing, geen kengetal.

    python scripts/decision_package_5211_pvc.py [--check]
"""
import argparse
import copy
import json
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_kengetallen as bk  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402

PACKAGE_VERSION = "decision_package_5211_pvc_v1"
KEY = ("5211", "replace", "m1")
MATERIAL = "pvc"
OUT_JSON = os.path.join("reports", "review", "decision_package_5211_pvc.json")
OUT_MD = os.path.join("reports", "review", "decision_package_5211_pvc.md")
CHOICES = ("COMPARABLE", "COMPARABLE_WITH_CAVEATS", "NOT_COMPARABLE")
# family-ids in comparability_review_v2 vóór het materiaalbesluit MATDEC-00001 (main 31ccb2b); de familiesleutel
# bevat het materiaal, dus met pvc als vastgesteld materiaal krijgen dezelfde paren een nieuwe id
PREVIOUS_FAMILY_IDS = {"RF-5211-1e814339c4": ["PAIR-00632", "PAIR-00634", "PAIR-00635", "PAIR-00637"],
                       "RF-5211-4c4e7cd188": ["PAIR-00583", "PAIR-00585"],
                       "RF-5211-4e9a81167e": ["PAIR-00641"]}
ALLOWED_DIFFERENCES = ("PRICE_LEVEL_DIFFERENCE", "QUANTITY_SCALE_DIFFERENCE")
CONTEXT_CAVEATS = ("PRICE_LEVEL_ABSENT",)            # prijspeil ontbreekt in de bron: ook een prijspeilverschil


def side(ctx, oid):
    v = ctx.observation_view(oid)
    n = ctx.norm[oid]
    return {"observation_id": oid, "document_id": v["document_id"], "source_cluster": v["source_cluster"],
            "object_description": v["object_description"], "action_text": v["action_text"],
            "action_normalized": n["action"]["action_normalized"], "material": v["material"],
            "material_decision_id": n["material"].get("material_decision_id"),
            "unit_original": v["unit_original"], "unit_normalized": n["unit"]["unit_normalized"],
            "quantity": v["quantity"], "price_level_date": v["price_level_date"],
            "derived_price_per_execution": v["derived_price_per_execution"],
            "executions_in_window": v["executions_in_window"], "vat_basis": v["vat_basis"],
            "page": v["page"], "line": v["line"], "source_text": v["source_text"], "caveats": v["caveats"]}


def content_check(ctx, pair, a, b):
    dev = []
    if a["action_normalized"] != b["action_normalized"]:
        dev.append("MAINTENANCE_ACTION_DIFFERS")
    if crv.text_tokens(a["action_text"]) != crv.text_tokens(b["action_text"]):
        dev.append("ACTION_TEXT_DIFFERS")
    if crv.text_tokens(a["object_description"]) != crv.text_tokens(b["object_description"]):
        dev.append("OBJECT_TEXT_DIFFERS")
    if a["material"]["value"] != MATERIAL or b["material"]["value"] != MATERIAL:
        dev.append("NOT_BOTH_PVC")
    if a["unit_original"] != "m1" or b["unit_original"] != "m1":
        dev.append("UNIT_NOT_M1")
    if a["source_cluster"] == b["source_cluster"]:
        dev.append("SAME_SOURCE_CLUSTER")
    risk = ctx.relation_risk(pair)
    if risk:
        dev.append("RELATION_OR_DEPENDENCY:" + ",".join(risk))
    if pair["hard_violations"]:
        dev.append("HARD_VIOLATIONS:" + ",".join(pair["hard_violations"]))
    other_pair = [c for c in pair["pair_caveats"] if c not in ALLOWED_DIFFERENCES]
    if other_pair:
        dev.append("OTHER_PAIR_CAVEATS:" + ",".join(other_pair))
    other_obs = sorted({c for s in ("a", "b") for c in pair["observation_caveats"][s] if c not in CONTEXT_CAVEATS})
    if other_obs:
        dev.append("OTHER_OBSERVATION_CAVEATS:" + ",".join(other_obs))
    differences = []
    if a["price_level_date"] != b["price_level_date"]:
        differences.append("price_level")
    if a["quantity"] != b["quantity"]:
        differences.append("quantity")
    if a["derived_price_per_execution"] != b["derived_price_per_execution"]:
        differences.append("price")
    return {"matches_description": not dev, "deviations": dev, "differences": differences,
            "material_sources": [a["material"]["source"], b["material"]["source"]]}


def simulate(ctx, decisions_by_pairset):
    """build_kengetallen.evaluate (bestaande regels) met hypothetische ACTIVE records. Alleen de groepen met
    5211-pvc-observations. Niets wordt vastgelegd."""
    records = copy.deepcopy(ctx.store["records"])
    for n, (obs_ids, decision) in enumerate(sorted(decisions_by_pairset.items(), key=lambda x: sorted(x[0]))):
        for r in records:
            if frozenset(r["observation_ids"]) == obs_ids and r["status"] == "ACTIVE":
                r["status"] = "SUPERSEDED"
        p = ctx.pair_by_set[obs_ids]
        records.append({"decision_id": f"SIMULATED-{n + 1:05d}", "pair_id": p["pair_id"],
                        "observation_ids": list(p["observation_ids"]), "decision": decision, "status": "ACTIVE",
                        "system_class": p["class"], "decision_caveats": []})
    _, kgs = bk.evaluate(list(ctx.norm.values()), ctx.comp["observations"], records)
    out = []
    for k in kgs:
        if tuple(k["candidate_key"]) != KEY:
            continue
        out.append({"kengetal_id": k["kengetal_id"], "status": k["status"],
                    "insufficient_data_reasons": k["insufficient_data_reasons"],
                    "source_cluster_count": k["source_cluster_count"], "source_cluster_ids": k["source_cluster_ids"],
                    "simulated_value_display": k["value_display"],
                    "min_display": k["min_display"], "max_display": k["max_display"],
                    "observation_ids": k["observation_ids"],
                    "excluded_observation_ids": k["excluded_observation_ids"],
                    "missing_cross_cluster_reviews": k["missing_cross_cluster_reviews"],
                    "mixed_price_level": k["price_levels"]["mixed_price_level"],
                    "missing_price_level": k["price_levels"]["missing_price_level"]})
    return out


def effect_on_existing(existing, result):
    same = next((r for r in result if r["kengetal_id"] == existing["kengetal_id"]), None)
    if same and same["status"] == existing["status"] and same["simulated_value_display"] == existing["value_display"]:
        return "UNCHANGED"
    if same:
        return f"CHANGED:{same['status']}"
    return "REPLACED_BY:" + ",".join(f"{r['kengetal_id']}({r['status']})" for r in result) if result else "REMOVED"


def build(root):
    ctx = crv.Context(root)
    review = crv.build(root)
    ks = crv.key_str(KEY)
    kg = next(k for k in ctx.kg["kengetallen"] if tuple(k["candidate_key"]) == KEY
              and (k["material"] or {}).get("normalized") == MATERIAL)
    existing = {"kengetal_id": kg["kengetal_id"], "status": kg["status"], "value_display": kg["value_display"],
                "source_cluster_count": kg["source_cluster_count"], "source_cluster_ids": kg["source_cluster_ids"],
                "observation_ids": kg["observation_ids"], "decision_ids": kg["decision_ids"]}
    obs = sorted(a["observation_id"] for a in ctx.comp["observations"]
                 if crv.key_str(a["candidate_key"]) == ks and a["independent_input"]
                 and ctx.material(a["observation_id"])["value"] == MATERIAL)
    fam_of = {pid: f for f in review["families"] for pid in f["pair_ids"]}
    prev_of = {pid: fid for fid, pids in PREVIOUS_FAMILY_IDS.items() for pid in pids}
    pairs, open_sets = [], []
    for x, y in combinations(obs, 2):
        if ctx.assess[x]["source_cluster"] == ctx.assess[y]["source_cluster"]:
            continue
        p = ctx.pair_by_set[frozenset((x, y))]
        a, b = (side(ctx, i) for i in p["observation_ids"])
        active = [r for r in ctx.records.get(frozenset(p["observation_ids"]), []) if r["status"] == "ACTIVE"]
        is_open = not active or active[0]["decision"] not in bk.POSITIVE
        f = fam_of.get(p["pair_id"])
        pairs.append({"pair_id": p["pair_id"], "open": is_open,
                      "active_decision": {"decision_id": active[0]["decision_id"], "decision": active[0]["decision"]}
                      if active else None,
                      "review_family_id": f["review_family_id"] if f else None,
                      "previous_review_family_id": prev_of.get(p["pair_id"]),
                      "system_class": p["class"], "pair_caveats": p["pair_caveats"],
                      "hard_violations": p["hard_violations"], "unknown_reasons": p["unknown_reasons"],
                      "observation_caveats": p["observation_caveats"], "checks": p["checks"],
                      "sides": [a, b], "content_check": content_check(ctx, p, a, b)})
        if is_open:
            open_sets.append(frozenset(p["observation_ids"]))
    open_pairs = [p for p in pairs if p["open"]]
    families = []
    for fid in sorted({p["review_family_id"] for p in open_pairs}):
        f = next(x for x in review["families"] if x["review_family_id"] == fid)
        fam_sets = [frozenset(p["observation_ids"]) for p in f["pairs"]]
        sims = {}
        for c in CHOICES:
            res = simulate(ctx, {s: c for s in fam_sets})
            sims[c] = {"result": res, "effect_on_existing_kengetal": effect_on_existing(existing, res)}
        families.append({"review_family_id": fid,
                         "previous_review_family_id": sorted({prev_of[p] for p in f["pair_ids"] if p in prev_of}),
                         "evidence_category": f["evidence_category"], "evidence_flags": f["evidence_flags"],
                         "family_input_sha256": f["family_input_sha256"], "pair_ids": f["pair_ids"],
                         "document_ids": f["document_ids"], "source_clusters": f["source_clusters"],
                         "pair_caveats": f["differences"]["pair_caveats"],
                         "observation_caveats": f["differences"]["observation_caveats"],
                         "simulations": sims})
    combos = {}
    for c in CHOICES:
        res = simulate(ctx, {s: c for s in open_sets})
        combos[f"ALL_OPEN_FAMILIES_{c}"] = {"result": res, "effect_on_existing_kengetal": effect_on_existing(existing, res)}
    clusters = sorted({ctx.assess[i]["source_cluster"] for i in obs})
    return {
        "package_version": PACKAGE_VERSION,
        "candidate_group": ks, "material": MATERIAL,
        "inputs": review["inputs"],
        "note": ("Beslispakket, geen besluit. Simulaties gebruiken uitsluitend build_kengetallen.evaluate "
                 "(kengetallen_rules_v1) met hypothetische ACTIVE records; ze worden nergens vastgelegd. "
                 "COMPARABLE en COMPARABLE_WITH_CAVEATS tellen in de regels hetzelfde (regel 2); het verschil is "
                 "de vastgelegde voorbehoud-informatie. Toepassen alleen via scripts/apply_family_decision.py."),
        "existing_kengetal": existing,
        "pvc_observations": [side(ctx, i) for i in obs],
        "potential_source_clusters": {"count": len(clusters), "ids": clusters},
        "cross_cluster_pairs": pairs,
        "open_cross_cluster_pairs": len(open_pairs),
        "pairs_not_matching_description": [{"pair_id": p["pair_id"], "deviations": p["content_check"]["deviations"]}
                                           for p in open_pairs if not p["content_check"]["matches_description"]],
        "open_families": families,
        "combined_scenarios": combos,
    }


def render_md(pkg):
    e = pkg["existing_kengetal"]
    L = [f"# Beslispakket 5211 replace m1 - pvc", "",
         "Geen besluit: niets toegepast. Simulaties gebruiken alleen de bestaande kengetalregels en worden nergens "
         "vastgelegd.", "",
         "## Bestaand kengetal", "",
         f"`{e['kengetal_id']}`: {e['status']}, {e['value_display']}, {e['source_cluster_count']} clusters "
         f"({', '.join(e['source_cluster_ids'])}); decisions {', '.join(e['decision_ids'])}.", "",
         "## PVC-observations (independent_input)", "",
         "| observation | document | cluster | object | actie | materiaal (bron) | eenheid | hoeveelheid | prijspeil | prijs/uitvoering |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for s in pkg["pvc_observations"]:
        L.append(f"| {s['observation_id']} | {s['document_id']} | {s['source_cluster']} | {s['object_description']} | "
                 f"{s['action_text']} | {s['material']['value']} ({s['material']['source']}"
                 + (f", {s['material_decision_id']}" if s["material_decision_id"] else "") + f") | {s['unit_original']} | "
                 f"{s['quantity']} | {s['price_level_date'] or '-'} | {s['derived_price_per_execution']} |")
    pc = pkg["potential_source_clusters"]
    L += ["", f"Potentiële pvc source clusters: **{pc['count']}** ({', '.join(pc['ids'])}).", "",
          f"## Open cross-cluster paren ({pkg['open_cross_cluster_pairs']})", "",
          "| paar | familie (vorige id) | documenten | klasse | paarcaveats | hard | observation-caveats | verschillen | controle |",
          "|---|---|---|---|---|---|---|---|---|"]
    for p in pkg["cross_cluster_pairs"]:
        if not p["open"]:
            continue
        a, b = p["sides"]
        cc = p["content_check"]
        L.append(f"| {p['pair_id']} | {p['review_family_id']} ({p['previous_review_family_id']}) | "
                 f"{a['document_id']} x {b['document_id']} | {p['system_class']} | {', '.join(p['pair_caveats']) or '-'} | "
                 f"{', '.join(p['hard_violations']) or '-'} | a: {', '.join(p['observation_caveats']['a']) or '-'}; "
                 f"b: {', '.join(p['observation_caveats']['b']) or '-'} | {', '.join(cc['differences']) or '-'} | "
                 f"{'OK' if cc['matches_description'] else 'AFWIJKING: ' + ', '.join(cc['deviations'])} |")
    L += ["", "Paren die NIET aan de beschrijving voldoen (zelfde actie, pvc, m1, geen relatie; verschil alleen "
          "prijspeil/hoeveelheid/prijs): " + (", ".join(f"{p['pair_id']} ({', '.join(p['deviations'])})"
                                                        for p in pkg["pairs_not_matching_description"]) or "geen") + ".",
          "", "## Simulaties per open familie", ""]
    for f in pkg["open_families"]:
        L += [f"### {f['review_family_id']} (was {', '.join(f['previous_review_family_id'])}) - "
              f"{f['evidence_category']}, {len(f['pair_ids'])} paren", "",
              f"- paren: {', '.join(f['pair_ids'])}; documenten {', '.join(f['document_ids'])}",
              f"- paarcaveats: {f['pair_caveats'] or '-'}; observation-caveats: {f['observation_caveats'] or '-'}",
              f"- family_input_sha256: `{f['family_input_sha256']}`", ""]
        for c, s in f["simulations"].items():
            L.append(f"- **{c}** -> bestaand kengetal: `{s['effect_on_existing_kengetal']}`; "
                     + "; ".join(f"{r['kengetal_id']} {r['status']} {r['simulated_value_display'] or ''} "
                                 f"({r['source_cluster_count']} clusters"
                                 + (f", redenen {', '.join(x.split(':')[0] for x in r['insufficient_data_reasons'])}"
                                    if r["insufficient_data_reasons"] else "") + ")" for r in s["result"]))
        L.append("")
    L += ["## Gecombineerde scenario's (alle open families dezelfde keuze)", ""]
    for name, s in pkg["combined_scenarios"].items():
        L.append(f"- **{name}** -> bestaand kengetal: `{s['effect_on_existing_kengetal']}`; "
                 + "; ".join(f"{r['kengetal_id']} {r['status']} {r['simulated_value_display'] or ''} "
                             f"({r['source_cluster_count']} clusters; min {r['min_display']}, max {r['max_display']}"
                             + (", gemengde prijspeilen" if r["mixed_price_level"] else "")
                             + (", ontbrekend prijspeil" if r["missing_price_level"] else "") + ")"
                             for r in s["result"]))
    L += ["", pkg["note"], ""]
    return "\n".join(L)


def write(root):
    pkg = build(root)
    with open(os.path.join(root, OUT_JSON), "w", encoding="utf-8", newline="\n") as f:
        f.write(crv.dump(pkg))
    with open(os.path.join(root, OUT_MD), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(pkg))
    return pkg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.check:
        ok = open(os.path.join(root, OUT_JSON), encoding="utf-8").read() == crv.dump(build(root))
        print("ACTUEEL" if ok else "NIET ACTUEEL")
        return 0 if ok else 1
    pkg = write(root)
    print(f"{pkg['open_cross_cluster_pairs']} open paren, {len(pkg['open_families'])} open families, "
          f"{pkg['potential_source_clusters']['count']} potentiële clusters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
