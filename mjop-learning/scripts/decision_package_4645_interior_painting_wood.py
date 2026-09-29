#!/usr/bin/env python3
"""
decision_package_4645_interior_painting_wood.py - READ-ONLY beslispakket voor 4645|interior_painting|m2, hout.

Uitgangspunt: reports/review/kengetal_readiness_v1 (groep 4645|interior_painting|m2|wood). Het pakket toont:

  MATERIAL   de observations die een menselijk materiaalbesluit nodig hebben, met bron en of
             record_material_decision het besluit zou accepteren (validate met placeholder-reviewer; schrijft niets);
  PAIRS      de cross-cluster paren met systeemklasse UNKNOWN, met alle bronverschillen en of ze - nu en na het
             materiaalbesluit - in de reviewtrack UNKNOWN_PAIR_REVIEW van comparability_review_v2 vallen;
  SIMULATIES uitsluitend build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische records:
             huidige toestand; alleen materiaal; materiaal + 1 / 2 / 3 positieve paren; één paar NOT_COMPARABLE.

De toestand na het materiaalbesluit wordt gesimuleerd met record_material_decision.record op een TIJDELIJKE kopie.
Er wordt niets toegepast: geen materiaalbesluit, geen paar- of familiebesluit, geen kengetal.

    python scripts/decision_package_4645_interior_painting_wood.py [--check]
"""
import argparse
import copy
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_kengetallen as bk  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402
import kengetal_readiness_v1 as kr  # noqa: E402

PACKAGE_VERSION = "decision_package_4645_interior_painting_wood_v1"
KEY = "4645|interior_painting|m2"
MATERIAL = "wood"
GROUP = f"{KEY}|{MATERIAL}"
OUT_JSON = os.path.join("reports", "review", "decision_package_4645_interior_painting_wood.json")
OUT_MD = os.path.join("reports", "review", "decision_package_4645_interior_painting_wood.md")
# verwacht volgens kengetal_readiness_v1 (main 0fbfc62); het pakket verifieert ze tegen de actuele data
EXPECTED_OBSERVATIONS = ["PO-DOC-006-P015-L059", "PO-DOC-007-P017-L097", "PO-DOC-012-P014-L085"]
EXPECTED_PAIRS = ["PAIR-00529", "PAIR-00531", "PAIR-00533"]


def obs_view(ctx, oid):
    v = ctx.observation_view(oid)
    return {"observation_id": oid, "document_id": v["document_id"], "source_cluster": v["source_cluster"],
            "page": v["page"], "line": v["line"], "sheet": v["sheet"], "row": v["row"], "source_text": v["source_text"],
            "object_description": v["object_description"], "action_text": v["action_text"],
            "unit_original": v["unit_original"], "quantity": v["quantity"],
            "derived_price_per_execution": v["derived_price_per_execution"],
            "price_level_date": v["price_level_date"], "caveats": v["caveats"],
            "current_material": v["material"],
            "proposed_material": (v["material_text_evidence"] or {}).get("would_derive"),
            "proposed_material_token": (v["material_text_evidence"] or {}).get("token")}


def text_diff(a, b):
    ta, tb = crv.text_tokens(a), crv.text_tokens(b)
    return {"a": a, "b": b, "equal": ta == tb, "only_a": sorted(set(ta) - set(tb)), "only_b": sorted(set(tb) - set(ta))}


def pair_view(ctx, p, unknown_track_families):
    a, b = (obs_view(ctx, i) for i in p["observation_ids"])
    return {
        "pair_id": p["pair_id"], "observation_ids": p["observation_ids"],
        "document_ids": [a["document_id"], b["document_id"]], "source_clusters": [a["source_cluster"], b["source_cluster"]],
        "source_texts": [a["source_text"], b["source_text"]],
        "provenance": [{k: s[k] for k in ("observation_id", "document_id", "source_cluster", "page", "line", "sheet",
                                          "row")} for s in (a, b)],
        "object_text": text_diff(a["object_description"], b["object_description"]),
        "action_text": text_diff(a["action_text"], b["action_text"]),
        "quantity": {"a": a["quantity"], "b": b["quantity"], "equal": a["quantity"] == b["quantity"],
                     "quantity_scale_difference": "QUANTITY_SCALE_DIFFERENCE" in p["pair_caveats"]},
        "price_per_execution": {"a": a["derived_price_per_execution"], "b": b["derived_price_per_execution"],
                                "equal": a["derived_price_per_execution"] == b["derived_price_per_execution"]},
        "price_level": {"a": a["price_level_date"], "b": b["price_level_date"],
                        "equal": a["price_level_date"] == b["price_level_date"]},
        "system_class": p["class"], "unknown_reasons": p["unknown_reasons"], "hard_violations": p["hard_violations"],
        "pair_caveats": p["pair_caveats"], "observation_caveats": p["observation_caveats"],
        "unknown_track_blockers": crv.unknown_pair_blockers(ctx, p),
        "unknown_track_family_id": unknown_track_families.get(p["pair_id"]),
        "active_decision": next(({"decision_id": r["decision_id"], "decision": r["decision"]}
                                 for r in ctx.records.get(frozenset(p["observation_ids"]), [])
                                 if r["status"] == "ACTIVE"), None),
    }


def simulate(ctx, members, decisions):
    """build_kengetallen.evaluate met hypothetische ACTIVE records {pair_set: decision}. Niets vastgelegd."""
    records = copy.deepcopy(ctx.store["records"])
    for n, (s, d) in enumerate(sorted(decisions.items(), key=lambda x: sorted(x[0]))):
        for r in records:
            if frozenset(r["observation_ids"]) == s and r["status"] == "ACTIVE":
                r["status"] = "SUPERSEDED"
        p = ctx.pair_by_set[s]
        records.append({"decision_id": f"SIMULATED-{n + 1:05d}", "pair_id": p["pair_id"],
                        "observation_ids": list(p["observation_ids"]), "decision": d, "status": "ACTIVE",
                        "system_class": p["class"], "decision_caveats": []})
    _, kgs = bk.evaluate(list(ctx.norm.values()), ctx.comp["observations"], records)
    material_status = {i: ctx.material(i) for i in members}
    hits = [k for k in kgs if crv.key_str(k["candidate_key"]) == KEY and set(k["observation_ids"]) & set(members)]
    out = {"material_status": material_status, "kengetal_groups": []}
    for k in sorted(hits, key=lambda k: k["kengetal_id"]):
        out["kengetal_groups"].append({
            "kengetal_id": k["kengetal_id"], "status": k["status"],
            "insufficient_data_reasons": k["insufficient_data_reasons"],
            "material": (k["material"] or {}).get("normalized"),
            "source_cluster_count": k["source_cluster_count"], "source_cluster_ids": k["source_cluster_ids"],
            "observation_ids": k["observation_ids"], "excluded_observation_ids": k["excluded_observation_ids"],
            "missing_cross_cluster_reviews": k["missing_cross_cluster_reviews"],
            "median_display": k["value_display"], "min_display": k["min_display"], "max_display": k["max_display"],
            "mixed_price_level": k["price_levels"]["mixed_price_level"],
            "missing_price_level": k["price_levels"]["missing_price_level"]})
    out["available_kengetal"] = any(g["status"] == "AVAILABLE" for g in out["kengetal_groups"])
    if not hits:
        out["note"] = ("Geen kengetalgroep: build_kengetallen vormt alleen kandidaten uit ACTIVE positieve menselijke "
                       "beslissingen (regel 2); zonder zulke beslissingen ontstaat er niets.")
    return out


def build(root):
    ctx = crv.Context(root)
    readiness = kr.build(root)
    g = next(x for x in readiness["groups"] if x["candidate_group"] == GROUP)
    members = g["observation_ids"]
    needs_material = g["missing_material_approvals"]
    cross = [ctx.pair_by_set[frozenset((x, y))] for x, y in combinations(members, 2)
             if ctx.assess[x]["source_cluster"] != ctx.assess[y]["source_cluster"]]
    cur_review = crv.build(root)
    cur_track = {pid: f["review_family_id"] for f in cur_review["families"]
                 if f["review_track"] == crv.UNKNOWN_TRACK for pid in f["pair_ids"]}

    material = []
    approvals = []
    for oid in needs_material:
        v = obs_view(ctx, oid)
        appr = kr.approval_for(ctx, oid, v["proposed_material_token"] or v["proposed_material"])
        reason = kr.precheck(root, appr)
        if not reason:
            approvals.append(appr)
        material.append(dict(v, approval=appr, record_material_decision_precheck="WOULD_BE_ACCEPTED" if not reason
                             else "WOULD_BE_REFUSED", refusal_reason=reason))

    sets = [frozenset(p["observation_ids"]) for p in cross]
    pid_of = {frozenset(p["observation_ids"]): p["pair_id"] for p in cross}

    def label(ss):
        return [pid_of[s] for s in sorted(ss, key=lambda s: pid_of[s])]

    current = {"pairs": [pair_view(ctx, p, cur_track) for p in cross],
               "simulation": simulate(ctx, members, {})}

    def after(tmp):
        c2 = crv.Context(tmp)
        r2 = crv.build(tmp)
        track = {pid: f for f in r2["families"] if f["review_track"] == crv.UNKNOWN_TRACK for pid in f["pair_ids"]}
        pairs2 = [pair_view(c2, c2.pairs[p["pair_id"]], {k: v["review_family_id"] for k, v in track.items()})
                  for p in cross]
        families = []
        for fid in sorted({track[p["pair_id"]]["review_family_id"] for p in cross if p["pair_id"] in track}):
            f = next(x for x in r2["families"] if x["review_family_id"] == fid)
            families.append({"review_family_id": fid, "review_track": f["review_track"],
                             "evidence_category": f["evidence_category"], "pair_ids": f["pair_ids"],
                             "unknown_reasons": f["unknown_reasons"],
                             "allowed_human_choices": [c["choice"] for c in f["allowed_human_choices"]],
                             "indicative_family_input_sha256": f["family_input_sha256"]})
        scen = [("CURRENT_PLUS_MATERIAL_ONLY", "na alleen de materiaalgoedkeuringen", {})]
        for n in (1, 2):
            for combo in combinations(sets, n):
                scen.append((f"MATERIAL_PLUS_{n}_POSITIVE:" + "+".join(label(combo)),
                             f"materiaal + {n} positief paar/paren ({', '.join(label(combo))})",
                             {s: "COMPARABLE_WITH_CAVEATS" for s in combo}))
        scen.append(("MATERIAL_PLUS_ALL_3_POSITIVE", "materiaal + alle 3 paren positief",
                     {s: "COMPARABLE_WITH_CAVEATS" for s in sets}))
        for s in sets:
            d = {x: "COMPARABLE_WITH_CAVEATS" for x in sets}
            d[s] = "NOT_COMPARABLE"
            scen.append((f"MATERIAL_PLUS_2_POSITIVE_1_NOT_COMPARABLE:{pid_of[s]}",
                         f"materiaal + {pid_of[s]} NOT_COMPARABLE, de andere twee positief", d))
        sims = [{"scenario": k, "description": desc,
                 "hypothetical_decisions": {pid_of[s]: d for s, d in sorted(dec.items(), key=lambda x: pid_of[x[0]])},
                 **simulate(c2, members, dec)} for k, desc, dec in scen]
        return pairs2, families, sims

    pairs2, families, sims = kr.with_material_decisions(root, approvals, after)
    return {
        "package_version": PACKAGE_VERSION,
        "candidate_group": GROUP, "candidate_key": KEY, "material": MATERIAL,
        "inputs": cur_review["inputs"],
        "note": ("READ-ONLY beslispakket: niets toegepast (geen materiaalbesluit, geen paar- of familiebesluit, geen "
                 "kengetal). Materiaal-precheck via record_material_decision.validate (schrijft niets); de toestand "
                 "na het materiaalbesluit is gesimuleerd op een tijdelijke kopie, dus family-ids en "
                 "family_input_sha256 na het materiaalbesluit zijn indicatief - het echte familiebesluit bindt aan "
                 "comparability_review_v2.json zoals dat NA het echte materiaalbesluit wordt herbouwd. Simulaties "
                 "uitsluitend met build_kengetallen.evaluate (kengetallen_rules_v1)."),
        "readiness": {"rank": g["rank"], "readiness": g["readiness"], "blockers": g["blockers"],
                      "human_actions": g["human_actions"]},
        "id_verification": {
            "expected_observations": EXPECTED_OBSERVATIONS, "actual_observations": needs_material,
            "observations_match": needs_material == EXPECTED_OBSERVATIONS,
            "expected_pairs": EXPECTED_PAIRS, "actual_pairs": [p["pair_id"] for p in cross],
            "pairs_match": [p["pair_id"] for p in cross] == EXPECTED_PAIRS,
            "mapping": {e: a for e, a in zip(EXPECTED_PAIRS, [p["pair_id"] for p in cross]) if e != a}},
        "group_observations": members,
        "material": material,
        "pairs_current": current["pairs"],
        "pairs_after_material_decision": pairs2,
        "review_families_after_material_decision": families,
        "simulations": [dict(scenario="CURRENT", description="huidige toestand", hypothetical_decisions={},
                             **current["simulation"])] + sims,
    }


# ------------------------------------------------------------------ markdown

def _kg(sim):
    if not sim["kengetal_groups"]:
        return "geen kengetalgroep"
    return "; ".join(
        f"`{k['kengetal_id']}` **{k['status']}**" + (f" mediaan {k['median_display']}" if k["median_display"] else "")
        + f", {k['source_cluster_count']} clusters, min {k['min_display']}, max {k['max_display']}"
        + (f", redenen {', '.join(r.split(':')[0] for r in k['insufficient_data_reasons'])}"
           if k["insufficient_data_reasons"] else "")
        + (f", uitgesloten {', '.join(k['excluded_observation_ids'])}" if k["excluded_observation_ids"] else "")
        + (f", ontbrekende reviews {len(k['missing_cross_cluster_reviews'])}" if k["missing_cross_cluster_reviews"] else "")
        for k in sim["kengetal_groups"])


def render_md(pkg):
    iv = pkg["id_verification"]
    L = [f"# Beslispakket {pkg['candidate_group']}", "", pkg["note"], "",
         f"Readiness: rang {pkg['readiness']['rank']}, {pkg['readiness']['readiness']}; blockers "
         f"{', '.join(pkg['readiness']['blockers'])}; menselijke acties {pkg['readiness']['human_actions']['total']}.",
         "", f"ID-controle: observations {'gelijk' if iv['observations_match'] else 'AFWIJKEND'} aan het "
             f"readiness-rapport, paren {'gelijk' if iv['pairs_match'] else 'AFWIJKEND'}"
             + (f" (mapping {iv['mapping']})" if iv["mapping"] else "") + ".", "",
         "## MATERIAL", "",
         "| observation | document | cluster | bron | objectomschrijving | actietekst | eenheid | huidig materiaal | "
         "voorgesteld | record_material_decision |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m in pkg["material"]:
        cm = m["current_material"]
        L.append(f"| {m['observation_id']} | {m['document_id']} | {m['source_cluster']} | p{m['page']} r{m['line']}: "
                 f"`{m['source_text']}` | {m['object_description']} | {m['action_text']} | {m['unit_original']} | "
                 f"{cm['value'] or 'onbekend'} ({cm['source'] or '-'}) | {m['proposed_material']} "
                 f"(woord '{m['proposed_material_token']}') | {m['record_material_decision_precheck']}"
                 + (f": {m['refusal_reason']}" if m["refusal_reason"] else "") + " |")
    L += ["", "## PAIRS", ""]
    after = {p["pair_id"]: p for p in pkg["pairs_after_material_decision"]}
    for p in pkg["pairs_current"]:
        a2 = after[p["pair_id"]]
        o, ac = p["object_text"], p["action_text"]
        L += [f"### {p['pair_id']}: {p['document_ids'][0]} x {p['document_ids'][1]}", "",
              f"- observations: {p['observation_ids'][0]} ({p['source_clusters'][0]}) x {p['observation_ids'][1]} "
              f"({p['source_clusters'][1]})",
              f"- brontekst a: `{p['source_texts'][0]}`",
              f"- brontekst b: `{p['source_texts'][1]}`",
              f"- objecttekst: '{o['a']}' vs '{o['b']}'" + ("" if o["equal"] else
                                                            f" (alleen a: {o['only_a'] or '-'}; alleen b: {o['only_b'] or '-'})"),
              f"- actietekst: '{ac['a']}' vs '{ac['b']}'" + ("" if ac["equal"] else
                                                             f" (alleen a: {ac['only_a'] or '-'}; alleen b: {ac['only_b'] or '-'})"),
              f"- hoeveelheid: {p['quantity']['a']} vs {p['quantity']['b']}; prijs per uitvoering: "
              f"{p['price_per_execution']['a']} vs {p['price_per_execution']['b']}; prijspeil: "
              f"{p['price_level']['a'] or '-'} vs {p['price_level']['b'] or '-'}",
              f"- system_class: **{p['system_class']}**; unknown_reasons: {', '.join(p['unknown_reasons']) or '-'}; "
              f"hard violations: {', '.join(p['hard_violations']) or '-'}",
              f"- caveats: paar {', '.join(p['pair_caveats']) or '-'}; observations a "
              f"{', '.join(p['observation_caveats']['a']) or '-'}, b {', '.join(p['observation_caveats']['b']) or '-'}",
              f"- UNKNOWN-reviewtrack nu: " + ("reviewbaar, familie " + p["unknown_track_family_id"]
                                               if not p["unknown_track_blockers"] else
                                               "geblokkeerd door " + ", ".join(p["unknown_track_blockers"])),
              f"- na het materiaalbesluit: system_class {a2['system_class']}; caveats observations a "
              f"{', '.join(a2['observation_caveats']['a']) or '-'}, b {', '.join(a2['observation_caveats']['b']) or '-'}; "
              + ("reviewbaar, familie " + a2["unknown_track_family_id"] if not a2["unknown_track_blockers"]
                 else "geblokkeerd door " + ", ".join(a2["unknown_track_blockers"])), ""]
    L += ["## Reviewfamilies na het materiaalbesluit (indicatief)", "",
          "| familie | track | categorie | paren | unknown_reasons | keuzes |", "|---|---|---|---|---|---|"]
    for f in pkg["review_families_after_material_decision"]:
        L.append(f"| {f['review_family_id']} | {f['review_track']} | {f['evidence_category']} | {', '.join(f['pair_ids'])} "
                 f"| {', '.join(f['unknown_reasons'])} | {', '.join(f['allowed_human_choices'])} |")
    L += ["", "## SIMULATIES (kengetallen_rules_v1)", "",
          "| scenario | hypothetische besluiten | materiaal | kengetal | AVAILABLE |", "|---|---|---|---|---|"]
    for s in pkg["simulations"]:
        mats = ", ".join(f"{i}: {m['value'] or 'onbekend'}"
                         for i, m in s["material_status"].items())
        dec = ", ".join(f"{k} {v}" for k, v in s["hypothetical_decisions"].items()) or "-"
        L.append(f"| {s['description']} | {dec} | {mats} | {_kg(s)} | {'ja' if s['available_kengetal'] else 'nee'} |")
    L += ["", "Observations en ontbrekende cross-cluster reviews per scenario staan in het JSON-bestand "
              "(`simulations[].kengetal_groups[]`).", ""]
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
    iv = pkg["id_verification"]
    print(f"observations {iv['actual_observations']} (match {iv['observations_match']}); "
          f"pairs {iv['actual_pairs']} (match {iv['pairs_match']})")
    for s in pkg["simulations"]:
        print(s["scenario"], [(k["status"], k["median_display"], k["source_cluster_count"]) for k in s["kengetal_groups"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
