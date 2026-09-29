#!/usr/bin/env python3
"""
semantic_candidate_review_v1.py - READ-ONLY semantische vergelijking van de candidate groups die volgens
kengetal_readiness_v1 met de bestaande keten af te ronden zijn.

Alleen analyse: geen materiaal-, comparability- of familiebesluit, geen kengetal, geen canonieke data, geen nieuw
reviewmechanisme, geen score/ranking/confidence. Alle gegevens komen uit bestaande bron/provenance-velden
(genormaliseerde observations, comparability, comparability_review_v2, kengetal_readiness_v1).

Tekstverschillen worden EXACT bepaald: woordtokens (build_kengetallen.tokens), geen stemming, geen fuzzy matching
(enkelvoud/meervoud telt dus als verschil). Per observation worden objectomschrijving en actietekst samen bekeken.
Tokens worden ingedeeld met VASTE, hieronder gedocumenteerde termlijsten:

  FINISH_SYSTEM  afwerkingssysteem (dekkend, transparant, beits, lak, ...)
  MATERIAL       materiaal (hout, multiplex, stucwerk, ...)
  COMPONENT      bouwdeel/onderdeel (kozijn, raam, deur, panelen, diversen, ...)
  LOCATION       locatie/gebouwdeel (entree, bergingen, trappenhuis, gevels, ...)
  ACTION         onderhoudsactie (groot, klein, schilderwerk, beitsen, ...)
  FACADE_SIDE    de vaste, goedgekeurde gevelzijde-woorden (build_kengetallen.FACADE_SIDE_WORDS, regel 3)
  OTHER          alle overige tokens (bijv. 'en', 'm2', 'conform')

Per paar (feitelijk, geen oordeel over vergelijkbaarheid):
  CONTRAST        in dezelfde categorie heeft ELKE kant een term die de andere niet heeft (bijv. dekkend vs
                  transparant, multiplex vs stucwerk) -> "duidelijk inhoudelijk verschil" (ook: ander materiaal of
                  andere genormaliseerde actie/eenheid)
  ONE_SIDED       alleen één kant noemt (extra) termen in een categorie, de andere niets of een deelverzameling
                  (algemeen vs specifiek, bijv. 'hout (multiplex)' vs 'hout') -> gemarkeerd, beperkte variant
  Klasse: EXACT_SAME_SEMANTICS (object- en actietokens identiek), LIMITED_TEXT_VARIANT (geen CONTRAST) of
  SUBSTANTIVE_DIFFERENCE (minstens één CONTRAST). Dit is een markering voor de mens, geen besluit.

    python scripts/semantic_candidate_review_v1.py [--check]
"""
import argparse
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_kengetallen as bk  # noqa: E402
import comparability_review_v2 as crv  # noqa: E402

REPORT_VERSION = "semantic_candidate_review_v1"
OUT_JSON = os.path.join("reports", "review", "semantic_candidate_review_v1.json")
OUT_MD = os.path.join("reports", "review", "semantic_candidate_review_v1.md")
READINESS = os.path.join("reports", "review", "kengetal_readiness_v1.json")
GROUPS = ["4645|interior_painting|m2|wood", "4632|interior_painting|m2|wood", "4622|interior_painting|m2|wood",
          "4631|exterior_painting|m2|wood", "4621|exterior_painting|m2|wood"]
TERMS = {
    "FINISH_SYSTEM": ("dekkend", "transparant", "beits", "beitsen", "beitswerk", "lak", "lakken", "lakwerk", "vernis",
                      "olie", "coating", "blank"),
    "MATERIAL": ("hout", "houten", "multiplex", "stucwerk", "metaal", "staal", "aluminium", "kunststof", "beton",
                 "steen", "zink", "pvc", "glas", "trespa"),
    "COMPONENT": ("kozijn", "kozijnen", "raam", "ramen", "deur", "deuren", "draaiende", "delen", "panelen",
                  "gevelbekleding", "boeiboord", "boeiboorden", "boeidelen", "leuning", "leuningen", "puivulling",
                  "pui", "puien", "entreepuien", "balkonkastdeuren", "plafond", "plafonds", "dakoverstek", "hekwerk",
                  "lijsten", "luiken", "dakrand", "betonconstructie", "diversen"),
    "LOCATION": ("entree", "berging", "bergingen", "trappenhuis", "gevel", "gevels", "balkon", "balkons", "galerij",
                 "portiek"),
    "ACTION": ("groot", "klein", "schilderwerk", "binnenschilderwerk", "buitenschilderwerk", "bijwerken", "reinigen",
               "herstel", "onderhoud", "vervangen"),
}
CATEGORY_OF = {t: c for c, ts in TERMS.items() for t in ts}
CLASS_ORDER = ("EXACT_SAME_SEMANTICS", "LIMITED_TEXT_VARIANT", "SUBSTANTIVE_DIFFERENCE")
GROUP_CATEGORIES = {1: "NO_CLEAR_SUBSTANTIVE_DIFFERENCES", 2: "LIMITED_TEXT_VARIANTS_ONLY",
                    3: "CLEAR_MAINTENANCE_CONTENT_DIFFERENCES"}


def category(t):
    if t in bk.FACADE_SIDE_WORDS:
        return "FACADE_SIDE"
    return CATEGORY_OF.get(t, "OTHER")


def obs_view(ctx, oid):
    v = ctx.observation_view(oid)
    n = ctx.norm[oid]
    te = v["material_text_evidence"] or {}
    return {"observation_id": oid, "document_id": v["document_id"], "source_cluster": v["source_cluster"],
            "page": v["page"], "line": v["line"], "sheet": v["sheet"], "row": v["row"], "source_text": v["source_text"],
            "object_description": v["object_description"], "action_text": v["action_text"],
            "action_normalized": n["action"]["action_normalized"],
            "material_current": v["material"], "material_proposed": te.get("would_derive"),
            "unit_original": v["unit_original"], "unit_normalized": n["unit"]["unit_normalized"],
            "quantity": v["quantity"], "derived_price_per_execution": v["derived_price_per_execution"],
            "price_level_date": v["price_level_date"],
            "cycle_start_year": n["price"]["cycle_start_year"], "cycle_length_years": n["price"]["cycle_length_years"],
            "caveats": v["caveats"]}


def material_of(o):
    return o["material_current"]["value"] or o["material_proposed"]


def text_diff(a, b):
    ta, tb = bk.tokens(a), bk.tokens(b)
    return {"a": a, "b": b, "tokens_equal": ta == tb,
            "only_a": sorted(set(ta) - set(tb)), "only_b": sorted(set(tb) - set(ta))}


def semantic_diff(a, b):
    ta = set(bk.tokens(a["object_description"])) | set(bk.tokens(a["action_text"]))
    tb = set(bk.tokens(b["object_description"])) | set(bk.tokens(b["action_text"]))
    out = {}
    for cat in list(TERMS) + ["FACADE_SIDE", "OTHER"]:
        ca = sorted(t for t in ta if category(t) == cat)
        cb = sorted(t for t in tb if category(t) == cat)
        if ca == cb:
            continue
        only_a, only_b = sorted(set(ca) - set(cb)), sorted(set(cb) - set(ca))
        kind = ("CONTRAST" if only_a and only_b else "ONE_SIDED") if cat in TERMS else "VARIANT"
        out[cat] = {"a": ca, "b": cb, "kind": kind, "only_a": only_a, "only_b": only_b}
    return out


def pair_view(ctx, p, family, oa, ob):
    obj = text_diff(oa["object_description"], ob["object_description"])
    act = text_diff(oa["action_text"], ob["action_text"])
    sem = semantic_diff(oa, ob)
    structural = []
    if material_of(oa) != material_of(ob):
        structural.append(f"MATERIAL: {material_of(oa)} vs {material_of(ob)}")
    if oa["action_normalized"] != ob["action_normalized"]:
        structural.append(f"ACTION_NORMALIZED: {oa['action_normalized']} vs {ob['action_normalized']}")
    if oa["unit_normalized"] != ob["unit_normalized"]:
        structural.append(f"UNIT: {oa['unit_normalized']} vs {ob['unit_normalized']}")
    def both(d):                                   # zijden in vaste (alfabetische) volgorde: richting telt niet
        return " vs ".join(sorted([" ".join(d["a"]) or "-", " ".join(d["b"]) or "-"]))
    contrasts = [f"{c}: {both(d)}" for c, d in sem.items() if d["kind"] == "CONTRAST"]
    one_sided = [f"{c}: {both(d)}" for c, d in sem.items() if d["kind"] == "ONE_SIDED"]
    if obj["tokens_equal"] and act["tokens_equal"] and not structural:
        cls = "EXACT_SAME_SEMANTICS"
    elif contrasts or structural:
        cls = "SUBSTANTIVE_DIFFERENCE"
    else:
        cls = "LIMITED_TEXT_VARIANT"
    return {
        "pair_id": p["pair_id"], "observation_ids": p["observation_ids"],
        "document_ids": [oa["document_id"], ob["document_id"]], "source_clusters": p["source_clusters"],
        "review_family_id": family["id"], "review_family_state": family["state"],
        "system_class": p["class"], "unknown_reasons": p["unknown_reasons"], "hard_violations": p["hard_violations"],
        "pair_caveats": p["pair_caveats"], "observation_caveats": p["observation_caveats"],
        "object_text": obj, "action_text": act,
        "material": {"a": material_of(oa), "b": material_of(ob), "equal": material_of(oa) == material_of(ob),
                     "sources": [oa["material_current"]["source"] or "proposed (text evidence, not approved)",
                                 ob["material_current"]["source"] or "proposed (text evidence, not approved)"]},
        "quantity": {"a": oa["quantity"], "b": ob["quantity"],
                     "quantity_scale_difference": "QUANTITY_SCALE_DIFFERENCE" in p["pair_caveats"]},
        "price_per_execution": {"a": oa["derived_price_per_execution"], "b": ob["derived_price_per_execution"]},
        "price_level": {"a": oa["price_level_date"], "b": ob["price_level_date"],
                        "equal": oa["price_level_date"] == ob["price_level_date"]},
        "semantic_differences": sem,
        "clear_content_differences": structural + contrasts,
        "generic_vs_specific": one_sided,
        "semantic_class": cls,
    }


def _dec(s):
    return float(s) if s not in (None, "") else None


def build(root):
    ctx = crv.Context(root)
    review = crv.build(root)
    readiness = crv.load(root, READINESS)
    by = {g["candidate_group"]: g for g in readiness["groups"]}
    cur_family = {pid: f for f in review["families"] for pid in f["pair_ids"]}
    groups = []
    for name in GROUPS:
        g = by[name]
        post_family = {pid: f["review_family_id"] for f in g["review_families_to_decide"] for pid in f["pair_ids"]}
        obs = {i: obs_view(ctx, i) for i in g["observation_ids"]}
        pairs = []
        for x, y in combinations(g["observation_ids"], 2):
            if obs[x]["source_cluster"] == obs[y]["source_cluster"]:
                continue
            p = ctx.pair_by_set[frozenset((x, y))]
            if p["pair_id"] in cur_family:
                fam = {"id": cur_family[p["pair_id"]]["review_family_id"],
                       "state": "CURRENT:" + cur_family[p["pair_id"]]["current_status"]}
            elif p["pair_id"] in post_family:
                fam = {"id": post_family[p["pair_id"]], "state": "INDICATIVE_AFTER_MATERIAL_DECISION"}
            else:
                fam = {"id": None, "state": "DECIDED_OR_NOT_IN_QUEUE"}
            a, b = (obs[i] for i in p["observation_ids"])
            pairs.append(pair_view(ctx, p, fam, a, b))
        counts = {c: sum(1 for p in pairs if p["semantic_class"] == c) for c in CLASS_ORDER}
        contrasts, one_sided = {}, {}
        for p in pairs:
            for d in p["clear_content_differences"]:
                contrasts.setdefault(d, []).append(p["pair_id"])
            for d in p["generic_vs_specific"]:
                one_sided.setdefault(d, []).append(p["pair_id"])
        cat = 1 if counts["EXACT_SAME_SEMANTICS"] == len(pairs) else 3 if counts["SUBSTANTIVE_DIFFERENCE"] else 2
        sim = g["expected_kengetal_effect"] or {}
        levels = sorted({o["price_level_date"] for o in obs.values() if o["price_level_date"]},
                        key=lambda d: (bk.price_year(d) or 0, d))
        qs = sorted((o["quantity"] for o in obs.values() if o["quantity"]), key=_dec)
        h = g["human_actions"]
        groups.append({
            "candidate_group": name, "candidate_key": g["candidate_key"], "readiness": g["readiness"],
            "observations": list(obs.values()),
            "pairs": pairs,
            "summary": {
                "independent_source_clusters": g["potential_source_clusters_after_steps"]["count"],
                "material_approvals_needed": h["material_approvals"],
                "review_families_needed": h["review_family_decisions"],
                "human_actions_total": h["total"],
                "pairs": len(pairs),
                "pairs_exact_same_semantics": counts["EXACT_SAME_SEMANTICS"],
                "pairs_limited_text_variant": counts["LIMITED_TEXT_VARIANT"],
                "pairs_substantive_difference": counts["SUBSTANTIVE_DIFFERENCE"],
                "differences_requiring_human_judgement": [{"difference": d, "pair_ids": sorted(v)}
                                                          for d, v in sorted(contrasts.items())],
                "generic_vs_specific_to_check": [{"difference": d, "pair_ids": sorted(v)}
                                                 for d, v in sorted(one_sided.items())],
                "simulated_kengetal_if_all_positive": {
                    "status": sim.get("status"), "median": sim.get("simulated_value_display"),
                    "min": sim.get("min_display"), "max": sim.get("max_display"),
                    "source_cluster_count": sim.get("source_cluster_count")},
                "price_level_range": [levels[0], levels[-1]] if levels else None,
                "price_levels_missing": sum(1 for o in obs.values() if not o["price_level_date"]),
                "quantity_range": [qs[0], qs[-1]] if qs else None,
            },
            "work_category": GROUP_CATEGORIES[cat], "work_category_order": cat,
        })
    groups.sort(key=lambda g: (g["work_category_order"], g["summary"]["human_actions_total"], g["candidate_key"]))
    return {
        "report_version": REPORT_VERSION,
        "inputs": dict(review["inputs"], readiness_sha256=crv.sha256_file(os.path.join(root, READINESS))),
        "note": ("READ-ONLY: geen besluit, geen materiaal, geen kengetal, geen score/ranking/confidence. Verschillen "
                 "zijn feitelijk gemarkeerd op exacte woordtokens met vaste termlijsten; er wordt NIET uitgesproken "
                 "dat verschillen vergelijkbaar of onvergelijkbaar zijn. Family-ids met status "
                 "INDICATIVE_AFTER_MATERIAL_DECISION komen uit kengetal_readiness_v1 (gesimuleerd materiaalbesluit)."),
        "term_lists": {k: list(v) for k, v in TERMS.items()},
        "facade_side_words": sorted(bk.FACADE_SIDE_WORDS),
        "worklist_order": ["1 NO_CLEAR_SUBSTANTIVE_DIFFERENCES", "2 LIMITED_TEXT_VARIANTS_ONLY",
                           "3 CLEAR_MAINTENANCE_CONTENT_DIFFERENCES", "binnen categorie: minste menselijke acties, "
                           "dan candidate key"],
        "worklist": [{"position": n, "candidate_group": g["candidate_group"], "work_category": g["work_category"],
                      "human_actions_total": g["summary"]["human_actions_total"]} for n, g in enumerate(groups, 1)],
        "groups": groups,
    }


# ------------------------------------------------------------------ markdown

def render_md(rep):
    L = ["# Semantische candidate review v1", "", rep["note"], "",
         "Termlijsten: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in rep["term_lists"].items())
         + f"; FACADE_SIDE: {', '.join(rep['facade_side_words'])}.", "",
         "## Werklijst", "", "| # | groep | categorie | menselijke acties |", "|---|---|---|---|"]
    for w in rep["worklist"]:
        L.append(f"| {w['position']} | {w['candidate_group']} | {w['work_category']} | {w['human_actions_total']} |")
    for g in rep["groups"]:
        s = g["summary"]
        k = s["simulated_kengetal_if_all_positive"]
        L += ["", f"## {g['candidate_group']} - {g['work_category']}", "",
              f"- onafhankelijke clusters {s['independent_source_clusters']}; materiaalgoedkeuringen "
              f"{s['material_approvals_needed']}; reviewfamilies {s['review_families_needed']}; menselijke acties "
              f"{s['human_actions_total']}",
              f"- paren {s['pairs']}: exact dezelfde semantiek {s['pairs_exact_same_semantics']}, beperkte "
              f"tekstvariant {s['pairs_limited_text_variant']}, duidelijk inhoudelijk verschil "
              f"{s['pairs_substantive_difference']}",
              f"- gesimuleerd kengetal (alles positief): {k['status']} mediaan {k['median']}, min {k['min']}, "
              f"max {k['max']}, {k['source_cluster_count']} clusters",
              f"- prijspeil {' - '.join(s['price_level_range']) if s['price_level_range'] else '-'}"
              + (f" ({s['price_levels_missing']} zonder prijspeil)" if s["price_levels_missing"] else "")
              + f"; hoeveelheid {' - '.join(s['quantity_range']) if s['quantity_range'] else '-'}", "",
              "Verschillen die menselijke beoordeling vereisen (CONTRAST):", ""]
        L += [f"- {d['difference']} ({', '.join(d['pair_ids'])})" for d in s["differences_requiring_human_judgement"]] \
            or ["- geen"]
        L += ["", "Algemeen vs specifiek (ONE_SIDED, ter controle):", ""]
        L += [f"- {d['difference']} ({', '.join(d['pair_ids'])})" for d in s["generic_vs_specific_to_check"]] or ["- geen"]
        L += ["", "### Observations", "",
              "| observation | document | cluster | object | actie | bron | materiaal nu/voorgesteld | eenheid | "
              "hoeveelheid | prijs/uitv. | prijspeil | cyclus | caveats |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for o in g["observations"]:
            loc = f"p{o['page']} r{o['line']}" if o["page"] else f"{o['sheet']} r{o['row']}"
            L.append(f"| {o['observation_id']} | {o['document_id']} | {o['source_cluster']} | {o['object_description']} | "
                     f"{o['action_text']} | {loc}: `{o['source_text']}` | {o['material_current']['value'] or '-'} / "
                     f"{o['material_proposed'] or '-'} | {o['unit_original']} | {o['quantity']} | "
                     f"{o['derived_price_per_execution']} | {o['price_level_date'] or '-'} | "
                     f"{o['cycle_start_year'] or '-'}/{o['cycle_length_years'] or '-'} | {', '.join(o['caveats']) or '-'} |")
        L += ["", "### Paren", "",
              "| paar | familie | system_class | unknown_reasons | hard | paarcaveats | object alleen a / b | "
              "actie alleen a / b | materiaal | hoeveelheid | prijspeil | prijs | klasse | inhoudelijke verschillen |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in g["pairs"]:
            o, a = p["object_text"], p["action_text"]
            L.append(f"| {p['pair_id']} | {p['review_family_id'] or '-'} ({p['review_family_state']}) | "
                     f"{p['system_class']} | {', '.join(p['unknown_reasons']) or '-'} | {', '.join(p['hard_violations']) or '-'} | "
                     f"{', '.join(p['pair_caveats']) or '-'} | {' '.join(o['only_a']) or '-'} / {' '.join(o['only_b']) or '-'} | "
                     f"{' '.join(a['only_a']) or '-'} / {' '.join(a['only_b']) or '-'} | "
                     f"{p['material']['a']} / {p['material']['b']} | {p['quantity']['a']} / {p['quantity']['b']} | "
                     f"{p['price_level']['a'] or '-'} / {p['price_level']['b'] or '-'} | "
                     f"{p['price_per_execution']['a']} / {p['price_per_execution']['b']} | {p['semantic_class']} | "
                     f"{'; '.join(p['clear_content_differences']) or '-'} |")
    L += [""]
    return "\n".join(L)


def write(root):
    rep = build(root)
    with open(os.path.join(root, OUT_JSON), "w", encoding="utf-8", newline="\n") as f:
        f.write(crv.dump(rep))
    with open(os.path.join(root, OUT_MD), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(rep))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if args.check:
        ok = open(os.path.join(root, OUT_JSON), encoding="utf-8").read() == crv.dump(build(root))
        print("ACTUEEL" if ok else "NIET ACTUEEL")
        return 0 if ok else 1
    rep = write(root)
    for w in rep["worklist"]:
        print(w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
