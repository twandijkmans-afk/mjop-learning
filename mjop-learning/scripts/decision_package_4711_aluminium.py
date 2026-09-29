#!/usr/bin/env python3
"""
decision_package_4711_aluminium.py - compact menselijk beslispakket voor 4711|replace|m1, materiaal aluminium
(alleen lezen).

Volgende kandidaatgroep na 5211 pvc. In tegenstelling tot 5211 is hier nog GEEN materiaalbesluit genomen; het
pakket toont daarom beide menselijke stappen die nodig zijn, in de volgorde waarin ze via de bestaande
ketenschakels zouden lopen:

  1. materiaal - voor elke independent_input observation van deze candidate key zonder materiaal, waarvoor de
     bestaande tekstregel aluminium (of zink) zou afleiden: het letterlijke bewijs en of
     scripts/record_material_decision.py het besluit zou accepteren (record_material_decision.validate met een
     placeholder-reviewer; schrijft niets);
  2. paren - alle cross-cluster aluminium-paren, met reviewfamilie VOOR en NA het materiaalbesluit (de
     familiesleutel bevat het materiaal, dus de family-id verandert), inhoudelijke controle per paar en
     simulaties met de BESTAANDE kengetalregels (build_kengetallen.evaluate) per familie en gecombineerd.

De toestand NA het materiaalbesluit wordt gesimuleerd door record_material_decision.record uit te voeren op een
tijdelijke kopie (hetzelfde pad als --dry-run); het echte repo wordt niet gewijzigd. Zink wordt ook doorgerekend
om te laten zien dat die groep met 2 source clusters INSUFFICIENT_DATA blijft.

Er wordt niets toegepast: geen materiaalbesluit, geen familiebesluit, geen kengetal.

    python scripts/decision_package_4711_aluminium.py [--check]
"""
import argparse
import copy
import os
import shutil
import sys
import tempfile
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_kengetallen as bk  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import promote_incoming_batch as pr  # noqa: E402
import record_material_decision as rmd  # noqa: E402

PACKAGE_VERSION = "decision_package_4711_aluminium_v1"
KEY = ("4711", "replace", "m1")
MATERIAL = "aluminium"
MATERIALS = ("aluminium", "zinc")   # zink alleen ter vergelijking: blijft INSUFFICIENT_DATA
OUT_JSON = os.path.join("reports", "review", "decision_package_4711_aluminium.json")
OUT_MD = os.path.join("reports", "review", "decision_package_4711_aluminium.md")
CHOICES = ("COMPARABLE", "COMPARABLE_WITH_CAVEATS", "NOT_COMPARABLE")
ALLOWED_DIFFERENCES = ("PRICE_LEVEL_DIFFERENCE", "QUANTITY_SCALE_DIFFERENCE")
CONTEXT_CAVEATS = ("PRICE_LEVEL_ABSENT",)            # prijspeil ontbreekt in de bron: ook een prijspeilverschil
PLACEHOLDER = {"reviewer": "SIMULATION-NOT-A-DECISION", "reviewed_at": "2000-01-01T00:00:00Z",
               "decision_reason": "simulatie voor het beslispakket; geen besluit"}
SIM_NOW = "2000-01-01T00:00:00Z"


def key_obs(ctx):
    ks = crv.key_str(KEY)
    return sorted(a["observation_id"] for a in ctx.comp["observations"] if crv.key_str(a["candidate_key"]) == ks)


def side(ctx, oid):
    v = ctx.observation_view(oid)
    n = ctx.norm[oid]
    te = v["material_text_evidence"] or {}
    return {"observation_id": oid, "document_id": v["document_id"], "source_cluster": v["source_cluster"],
            "independent_input": v["independent_input"],
            "object_description": v["object_description"], "action_text": v["action_text"],
            "action_normalized": n["action"]["action_normalized"], "material": v["material"],
            "material_decision_id": n["material"].get("material_decision_id"),
            "material_text_rule_would_derive": te.get("would_derive"), "material_text_token": te.get("token"),
            "unit_original": v["unit_original"], "unit_normalized": n["unit"]["unit_normalized"],
            "quantity": v["quantity"], "price_level_date": v["price_level_date"],
            "derived_price_per_execution": v["derived_price_per_execution"],
            "executions_in_window": v["executions_in_window"], "vat_basis": v["vat_basis"],
            "page": v["page"], "line": v["line"], "source_text": v["source_text"], "caveats": v["caveats"]}


def material_status(s):
    if s["material"]["value"]:
        return f"KNOWN:{s['material']['value']}"
    if s["material_text_rule_would_derive"]:
        return f"TEXT_EVIDENCE_PENDING_APPROVAL:{s['material_text_rule_would_derive']}"
    return "NO_MATERIAL_EVIDENCE"


def approval_for(s, material):
    # record_material_decision verwacht het woord zoals het in de objectomschrijving staat (bijv. zink -> zinc)
    return {"observation_id": s["observation_id"], "material": s["material_text_token"] or material,
            "evidence": {"element_description_original": s["object_description"],
                         "action_text_original": s["action_text"], "unit_original": s["unit_original"]}}


def material_steps(root, sides, material):
    """Per observation zonder materiaal met tekstbewijs voor `material`: wat record_material_decision.validate
    ervan vindt (placeholder-reviewer; schrijft niets). Het echte besluit vult een mens zelf in."""
    out = []
    for s in sides:
        if s["material"]["value"] or s["material_text_rule_would_derive"] != material or not s["independent_input"]:
            continue
        appr = approval_for(s, material)
        try:
            rmd.validate(root, dict(PLACEHOLDER, approvals=[appr]))
            verdict, reason = "WOULD_BE_ACCEPTED", None
        except rmd.MaterialDecisionError as e:
            verdict, reason = "WOULD_BE_REFUSED", str(e)
        out.append({"observation_id": s["observation_id"], "document_id": s["document_id"],
                    "source_cluster": s["source_cluster"], "material": appr["material"],
                    "material_normalized": material,
                    "evidence": appr["evidence"], "page": s["page"], "line": s["line"],
                    "source_text": s["source_text"],
                    "record_material_decision_precheck": verdict, "refusal_reason": reason})
    return out


def content_check(ctx, pair, a, b, material):
    dev = []
    if a["action_normalized"] != b["action_normalized"]:
        dev.append("MAINTENANCE_ACTION_DIFFERS")
    if crv.text_tokens(a["action_text"]) != crv.text_tokens(b["action_text"]):
        dev.append("ACTION_TEXT_DIFFERS")
    if crv.text_tokens(a["object_description"]) != crv.text_tokens(b["object_description"]):
        dev.append("OBJECT_TEXT_DIFFERS")
    if a["material"]["value"] != material or b["material"]["value"] != material:
        dev.append(f"NOT_BOTH_{material.upper()}")
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
    """build_kengetallen.evaluate (bestaande regels) met hypothetische ACTIVE records; alleen de groepen van
    deze candidate key. Niets wordt vastgelegd."""
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
    return [{"kengetal_id": k["kengetal_id"], "status": k["status"],
             "insufficient_data_reasons": k["insufficient_data_reasons"],
             "material": (k["material"] or {}).get("normalized"),
             "source_cluster_count": k["source_cluster_count"], "source_cluster_ids": k["source_cluster_ids"],
             "simulated_value_display": k["value_display"],
             "min_display": k["min_display"], "max_display": k["max_display"],
             "observation_ids": k["observation_ids"], "excluded_observation_ids": k["excluded_observation_ids"],
             "missing_cross_cluster_reviews": k["missing_cross_cluster_reviews"],
             "mixed_price_level": k["price_levels"]["mixed_price_level"],
             "missing_price_level": k["price_levels"]["missing_price_level"]}
            for k in kgs if tuple(k["candidate_key"]) == KEY]


def cross_cluster_pairs(ctx, obs):
    out = []
    for x, y in combinations(obs, 2):
        if ctx.assess[x]["source_cluster"] != ctx.assess[y]["source_cluster"]:
            out.append(ctx.pair_by_set[frozenset((x, y))])
    return out


def with_material_decision(root, approvals, fn):
    """Voert record_material_decision.record uit op een tijdelijke kopie (zoals --dry-run) en roept fn(tmp)
    aan op de toestand daarna. Het echte repo wordt niet aangeraakt."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel in pr.SIMULATION_COPY:
            s, d = os.path.join(root, rel), os.path.join(tmp, rel)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            elif os.path.isfile(s):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
        rmd.record(tmp, dict(PLACEHOLDER, approvals=approvals), now=SIM_NOW)
        return fn(tmp)


def material_group(root, material, pre_ctx, pre_review, pre_sides, steps):
    """Paren, families en simulaties voor één materiaal, vóór en na het (gesimuleerde) materiaalbesluit."""
    pre_fam = {pid: f["review_family_id"] for f in pre_review["families"] for pid in f["pair_ids"]}
    group_obs = sorted(s["observation_id"] for s in pre_sides if s["independent_input"] and
                       (s["material"]["value"] == material or s["material_text_rule_would_derive"] == material))
    pre_pairs = cross_cluster_pairs(pre_ctx, group_obs)
    pre_sets = [frozenset(p["observation_ids"]) for p in pre_pairs]
    # zonder materiaalbesluit: ook met alle paren positief blijft het materiaal blokkeren
    without = simulate(pre_ctx, {s: "COMPARABLE_WITH_CAVEATS" for s in pre_sets})

    def after(tmp):
        ctx = crv.Context(tmp)
        review = crv.build(tmp)
        fam_of = {pid: f for f in review["families"] for pid in f["pair_ids"]}
        pairs, open_sets = [], []
        for p in cross_cluster_pairs(ctx, group_obs):
            a, b = (side(ctx, i) for i in p["observation_ids"])
            active = [r for r in ctx.records.get(frozenset(p["observation_ids"]), []) if r["status"] == "ACTIVE"]
            is_open = not active or active[0]["decision"] not in bk.POSITIVE
            f = fam_of.get(p["pair_id"])
            pairs.append({"pair_id": p["pair_id"], "open": is_open,
                          "active_decision": {"decision_id": active[0]["decision_id"],
                                              "decision": active[0]["decision"]} if active else None,
                          "review_family_id_before_material_decision": pre_fam.get(p["pair_id"]),
                          "review_family_id_after_material_decision": f["review_family_id"] if f else None,
                          "system_class": p["class"], "pair_caveats": p["pair_caveats"],
                          "hard_violations": p["hard_violations"], "unknown_reasons": p["unknown_reasons"],
                          "observation_caveats": p["observation_caveats"],
                          "sides": [a, b], "content_check": content_check(ctx, p, a, b, material)})
            if is_open:
                open_sets.append(frozenset(p["observation_ids"]))
        families = []
        for fid in sorted({p["review_family_id_after_material_decision"] for p in pairs if p["open"]} - {None}):
            f = next(x for x in review["families"] if x["review_family_id"] == fid)
            fam_sets = [frozenset(p["observation_ids"]) for p in f["pairs"]]
            families.append({"review_family_id": fid,
                             "review_family_id_before_material_decision": sorted(
                                 {pre_fam[p] for p in f["pair_ids"] if p in pre_fam}),
                             "evidence_category": f["evidence_category"], "evidence_flags": f["evidence_flags"],
                             "family_input_sha256_after_simulated_material_decision": f["family_input_sha256"],
                             "pair_ids": f["pair_ids"], "document_ids": f["document_ids"],
                             "source_clusters": f["source_clusters"],
                             "pair_caveats": f["differences"]["pair_caveats"],
                             "observation_caveats": f["differences"]["observation_caveats"],
                             "simulations": {c: simulate(ctx, {s: c for s in fam_sets}) for c in CHOICES}})
        combos = {f"ALL_OPEN_FAMILIES_{c}": simulate(ctx, {s: c for s in open_sets}) for c in CHOICES}
        return pairs, families, combos

    approvals = [approval_for(next(s for s in pre_sides if s["observation_id"] == st["observation_id"]), material)
                 for st in steps if st["record_material_decision_precheck"] == "WOULD_BE_ACCEPTED"]
    # zonder open materiaalstap (besluit al vastgelegd): de huidige toestand, geen tijdelijke kopie
    pairs, families, combos = with_material_decision(root, approvals, after) if approvals else after(root)
    clusters = sorted({pre_ctx.assess[i]["source_cluster"] for i in group_obs})
    return {"material": material,
            "observation_ids": group_obs,
            "potential_source_clusters": {"count": len(clusters), "ids": clusters,
                                          "minimum_required": bk.MIN_SOURCE_CLUSTERS},
            "material_steps": steps,
            "simulation_without_material_decision_all_pairs_positive": without,
            "cross_cluster_pairs": pairs,
            "open_cross_cluster_pairs": sum(1 for p in pairs if p["open"]),
            "pairs_not_matching_description": [{"pair_id": p["pair_id"], "deviations": p["content_check"]["deviations"]}
                                               for p in pairs if p["open"] and not p["content_check"]["matches_description"]],
            "open_families_after_material_decision": families,
            "combined_scenarios_after_material_decision": combos}


def build(root):
    ctx = crv.Context(root)
    review = crv.build(root)
    ks = crv.key_str(KEY)
    sides = [side(ctx, i) for i in key_obs(ctx)]
    existing = [{"kengetal_id": k["kengetal_id"], "status": k["status"], "value_display": k["value_display"]}
                for k in ctx.kg["kengetallen"] if tuple(k["candidate_key"]) == KEY]
    groups = {m: material_group(root, m, ctx, review, sides, material_steps(root, sides, m)) for m in MATERIALS}
    return {
        "package_version": PACKAGE_VERSION,
        "candidate_group": ks, "material": MATERIAL, "compared_materials": list(MATERIALS),
        "inputs": review["inputs"],
        "note": ("Beslispakket, geen besluit. Materiaal-precheck: record_material_decision.validate met een "
                 "placeholder-reviewer (schrijft niets). De toestand na het materiaalbesluit is gesimuleerd met "
                 "record_material_decision.record op een tijdelijke kopie; family_input_sha256 daarvan is alleen "
                 "indicatief - het echte familiebesluit bindt aan comparability_review_v2.json zoals dat NA het "
                 "echte materiaalbesluit wordt herbouwd. Kengetalsimulaties gebruiken uitsluitend "
                 "build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische ACTIVE records en worden "
                 "nergens vastgelegd. COMPARABLE en COMPARABLE_WITH_CAVEATS tellen in de regels hetzelfde (regel 2). "
                 "Toepassen alleen via scripts/record_material_decision.py en daarna scripts/apply_family_decision.py."),
        "existing_kengetallen": existing,
        "observations": [dict(s, material_status=material_status(s)) for s in sides],
        "groups": groups,
    }


def _kg_line(r):
    reasons = sorted({x.split(":")[0] for x in r["insufficient_data_reasons"]})
    return (f"{r['kengetal_id']} {r['status']}" + (f" {r['simulated_value_display']}" if r["simulated_value_display"] else "")
            + f" ({r['source_cluster_count']} clusters"
            + (f"; min {r['min_display']}, max {r['max_display']}" if r["min_display"] else "")
            + (", gemengde prijspeilen" if r["mixed_price_level"] else "")
            + (", ontbrekend prijspeil" if r["missing_price_level"] else "")
            + (f"; redenen {', '.join(reasons)}" if reasons else "") + ")")


def _kg_lines(result, material):
    rel = [r for r in result if r["material"] == material or material in r["kengetal_id"]]
    return "; ".join(_kg_line(r) for r in rel) or "geen kengetalgroep"


def render_md(pkg):
    L = ["# Beslispakket 4711 replace m1 - aluminium", "",
         "Dit pakket neemt zelf geen besluit. Waar een materiaalbesluit nog ontbreekt, is de toestand daarna "
         "gesimuleerd op een tijdelijke kopie; waar het al vastligt, toont het pakket de huidige toestand en de "
         "ACTIVE besluiten. Simulaties gebruiken alleen de bestaande regels en worden nergens vastgelegd.", "",
         "## Bestaande kengetallen", "",
         ("; ".join(f"`{e['kengetal_id']}` {e['status']} {e['value_display'] or ''}" for e in pkg["existing_kengetallen"])
          or "Geen kengetal voor 4711|replace|m1.") + "", "",
         f"## Alle observations van {pkg['candidate_group']}", "",
         "| observation | document | cluster | object | actie | materiaalstatus | eenheid | hoeveelheid | prijspeil | prijs/uitvoering |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for s in pkg["observations"]:
        L.append(f"| {s['observation_id']} | {s['document_id']} | {s['source_cluster']} | {s['object_description']} | "
                 f"{s['action_text']} | {s['material_status']} ({s['material']['source'] or '-'}) | {s['unit_original']} | "
                 f"{s['quantity']} | {s['price_level_date'] or '-'} | {s['derived_price_per_execution']} |")
    for m, g in pkg["groups"].items():
        pc = g["potential_source_clusters"]
        L += ["", f"## {m} ({pc['count']} potentiële source clusters, minimum {pc['minimum_required']})", "",
              f"Observations: {', '.join(g['observation_ids'])}; clusters {', '.join(pc['ids'])}.", "",
              "### Stap 1 - materiaalbesluit (record_material_decision.py)", ""]
        if g["material_steps"]:
            L += ["| observation | document | objectomschrijving | actietekst | eenheid | bron | precheck |",
                  "|---|---|---|---|---|---|---|"]
            for st in g["material_steps"]:
                e = st["evidence"]
                L.append(f"| {st['observation_id']} | {st['document_id']} | {e['element_description_original']} | "
                         f"{e['action_text_original']} | {e['unit_original']} | p{st['page']} r{st['line']}: "
                         f"`{st['source_text']}` | {st['record_material_decision_precheck']}"
                         + (f" ({st['refusal_reason']})" if st["refusal_reason"] else "") + " |")
        else:
            L.append("Geen observations die een materiaalbesluit nodig hebben.")
        L += ["", "Met de huidige materiaalstatus (zonder nieuw materiaalbesluit), als alle cross-cluster paren "
              "positief beoordeeld worden: "
              + _kg_lines(g["simulation_without_material_decision_all_pairs_positive"], m) + ".", "",
              f"### Stap 2 - cross-cluster paren na het materiaalbesluit ({g['open_cross_cluster_pairs']} open, "
              f"{len(g['cross_cluster_pairs'])} totaal)", "",
              "| paar | familie vóór -> na materiaalbesluit | documenten | klasse | paarcaveats | hard | observation-caveats | verschillen | controle | ACTIVE besluit |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for p in g["cross_cluster_pairs"]:
            a, b = p["sides"]
            cc = p["content_check"]
            L.append(f"| {p['pair_id']} | {p['review_family_id_before_material_decision'] or '-'} -> "
                     f"{p['review_family_id_after_material_decision'] or '- (niet in de queue)'} | "
                     f"{a['document_id']} x {b['document_id']} | "
                     f"{p['system_class']} | {', '.join(p['pair_caveats']) or '-'} | {', '.join(p['hard_violations']) or '-'} | "
                     f"a: {', '.join(p['observation_caveats']['a']) or '-'}; b: {', '.join(p['observation_caveats']['b']) or '-'} | "
                     f"{', '.join(cc['differences']) or '-'} | "
                     f"{'OK' if cc['matches_description'] else 'AFWIJKING: ' + ', '.join(cc['deviations'])} | "
                     + (f"{p['active_decision']['decision_id']} {p['active_decision']['decision']}"
                        if p["active_decision"] else "-") + " |")
        L += ["", f"Paren die NIET aan de beschrijving voldoen (zelfde actie- en objecttekst, {m}, m1, geen relatie; "
              "verschil alleen prijspeil/hoeveelheid/prijs): "
              + (", ".join(f"{p['pair_id']} ({', '.join(p['deviations'])})" for p in g["pairs_not_matching_description"])
                 or "geen") + ".", ""]
        for f in g["open_families_after_material_decision"]:
            L += [f"#### {f['review_family_id']} (vóór materiaalbesluit: {', '.join(f['review_family_id_before_material_decision'])}) - "
                  f"{f['evidence_category']}, {len(f['pair_ids'])} paren", "",
                  f"- paren: {', '.join(f['pair_ids'])}; documenten {', '.join(f['document_ids'])}",
                  f"- paarcaveats: {f['pair_caveats'] or '-'}; observation-caveats: {f['observation_caveats'] or '-'}",
                  f"- family_input_sha256 (indicatief, gesimuleerd): `{f['family_input_sha256_after_simulated_material_decision']}`"]
            for c, res in f["simulations"].items():
                L.append(f"- **{c}** (alleen deze familie) -> {_kg_lines(res, m)}")
            L.append("")
        if g["combined_scenarios_after_material_decision"]:
            L += ["Gecombineerd (alle open families dezelfde keuze):", ""]
            for name, res in g["combined_scenarios_after_material_decision"].items():
                L.append(f"- **{name}** -> {_kg_lines(res, m)}")
    L += ["", "## Volgorde als een mens besluit", "",
          "1. Materiaalbesluit met `scripts/record_material_decision.py --decision <besluit.json>` (eerst `--dry-run`) "
          "voor exact de observations uit stap 1; reviewer, tijdstip en reden vult de mens in.",
          "2. `python scripts/comparability_review_v2.py` opnieuw draaien; de family-ids en family_input_sha256 uit dat "
          "herbouwde pakket (niet de indicatieve waarden hierboven) gaan in het familiebesluit.",
          "3. Familiebesluit(en) met `scripts/apply_family_decision.py --decision <besluit.json>` (eerst `--dry-run`); "
          "een nieuw AVAILABLE kengetal moet in `acknowledged_kengetal_effects` staan.", "",
          pkg["note"], ""]
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
    for m, g in pkg["groups"].items():
        print(f"{m}: {g['potential_source_clusters']['count']} clusters, {len(g['material_steps'])} materiaalstappen, "
              f"{g['open_cross_cluster_pairs']} open paren, {len(g['open_families_after_material_decision'])} families")
    return 0


if __name__ == "__main__":
    sys.exit(main())
