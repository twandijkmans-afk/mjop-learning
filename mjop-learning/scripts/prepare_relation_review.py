#!/usr/bin/env python3
"""
prepare_relation_review.py - reviewpakket voor een open relatiekandidaat (alleen lezen, geen besluit).

Vergelijkt een incoming document (staging) met één of meer canonieke documenten op:
  - bron (sha256, grootte, pagina's) en objectmetadata (naam, adres, postcode, bouwjaar, eenheden,
    inspectiedatum, prijspeil, BTW, indexatie) - met bronpagina;
  - elementen (code, naam, locatie; conditie waar aanwezig);
  - price observations: exacte rij-overlap (elementcode, actietekst, hoeveelheid, eenheid, Stj, Cy,
    jaarbedragen), gedeeltelijke overlap (zelfde actie/hoeveelheid, ander jaar of bedrag) en unieke rijen;
  - totalen ('Totaal object', som van de rijen);
  - tekstlaag: pagina's en regels die alleen in één van beide documenten voorkomen (bijv. printdatum).

Het pakket geeft de mogelijke relatietypen met hun gevolgen, maar BESLIST NIETS: geen relatie, geen
source cluster, geen wijziging van document_relations.json. Uitvoer is deterministisch (geen tijdstempels).

    python scripts/prepare_relation_review.py --document DOC-014 --batch-id IB-ad209360ab07 \\
        --against DOC-005 DOC-006 [--out reports/review/relation_review_DOC-014.json]
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import document_registry as dr  # noqa: E402
import text_layer as tl  # noqa: E402

VERSION = "relation_review_v1"
META_DOC = ("object_name", "object_postcode", "object_city", "price_level_date", "vat_statement",
            "vat_rate_text", "indexation_statement", "renovation_year")
META_BUILDING = ("address", "construction_year", "number_of_units", "inspection_date")
OPTIONS = [
    {"option": "DUPLICATE_OTHER_BYTES", "existing_relation_type": "duplicate_source",
     "meaning": "Hetzelfde MJOP, andere bytes (heruitgave/herafdruk/andere export).",
     "effect": "Het document levert GEEN eigen price observations (net als DOC-003); niet promoveren als "
               "zelfstandige bron, of alleen als duplicate_source vastleggen."},
    {"option": "SAME_MJOP_VERSION", "existing_relation_type": "version_of_same_mjop",
     "meaning": "Een andere versie van hetzelfde MJOP (zelfde object, gewijzigde inhoud of datum).",
     "effect": "Zelfde source cluster als de andere versie(s); rijen kunnen 'version_counterpart' "
               "(POSSIBLY_DEPENDENT) worden; telt niet als onafhankelijke bron voor kengetallen."},
    {"option": "SAME_BUILDING_DIFFERENT_INSPECTION", "existing_relation_type": "same_building_other_inspection",
     "meaning": "Zelfde gebouw, andere inspectie/plan (zoals DREL-004 DOC-002/DOC-004).",
     "effect": "Eigen source cluster; relatie wordt vastgelegd maar maakt de bron niet afhankelijk."},
    {"option": "INDEPENDENT_SOURCE", "existing_relation_type": None,
     "meaning": "Geen relevante relatie.",
     "effect": "Eigen source cluster; telt als onafhankelijke bron."},
]


def _v(ev):
    return ev.get("value") if isinstance(ev, dict) else ev


def _page(ev):
    p = (ev or {}).get("provenance") if isinstance(ev, dict) else None
    return p.get("page") if p else None


def _norm(t):
    return " ".join(str(t or "").lower().split())


def load_documents(root, document, batch_id, against):
    bdir = os.path.join(root, "data", "incoming_batches", batch_id)
    recs = {document: json.load(open(os.path.join(bdir, "extracted", f"{document}.json"), encoding="utf-8"))}
    pos = {document: json.load(open(os.path.join(bdir, "price_observations", f"{document}.json"),
                                    encoding="utf-8"))["observations"]}
    canon_po = json.load(open(os.path.join(root, "data", "price_observations", "price_observations_batch1.json"),
                              encoding="utf-8"))["observations"]
    for d in against:
        recs[d] = json.load(open(os.path.join(root, "data", "extracted", f"{d}.json"), encoding="utf-8"))
        pos[d] = [o for o in canon_po if o["document_id"] == d]
    return recs, pos


def metadata(recs):
    out = {}
    for key in META_DOC:
        out[key] = {d: {"value": _v(r["document_level_values"].get(key)),
                        "page": _page(r["document_level_values"].get(key))} for d, r in recs.items()}
    for key in META_BUILDING:
        out[key] = {d: {"value": _v(r["building"].get(key)), "page": _page(r["building"].get(key))}
                    for d, r in recs.items()}
    return out


def _el_key(e):
    return (((e.get("element_code") or {}).get("original_value")), _norm(_v(e.get("element_name"))),
            _norm(_v(e.get("location"))))


def elements(a, b):
    ka = Counter(_el_key(e) for e in a["elements"])
    kb = Counter(_el_key(e) for e in b["elements"])
    cond = lambda r: {o["element_id"]: (o["condition_score"] or {}).get("original_value") for o in r["observations"]}  # noqa: E731
    ca, cb = cond(a), cond(b)
    by_a = {_el_key(e): ca.get(e["element_id"]) for e in a["elements"]}
    by_b = {_el_key(e): cb.get(e["element_id"]) for e in b["elements"]}
    common = sorted((ka & kb).elements(), key=str)
    return {"count": [len(a["elements"]), len(b["elements"])], "common": len(common),
            "only_first": [list(k) for k in sorted((ka - kb).elements(), key=str)],
            "only_second": [list(k) for k in sorted((kb - ka).elements(), key=str)],
            "condition_differences": [{"element": list(k), "first": by_a.get(k), "second": by_b.get(k)}
                                      for k in sorted(set(common), key=str) if by_a.get(k) != by_b.get(k)]}


def _row(o):
    return {"observation_id": o["observation_id"], "element_code": o["element"]["element_code_original"],
            "action": o["action"]["action_text_original"], "quantity": o["quantity_value"],
            "unit": o["unit_original"], "stj": o["cycle_start_year_as_stated"], "cy": o["cycle_length_as_stated"],
            "annual_amounts": o["annual_amounts"], "total": o["total_value"]}


def _sum_totals(obs):
    return format(sum((Decimal(o["total_value"]) for o in obs if o["total_value"]), Decimal("0")), "f")


def observations(pa, pb):
    ex = lambda o: (o["element"]["element_code_original"], _norm(o["action"]["action_text_original"]),  # noqa: E731
                    o["quantity_value"], _norm(o["unit_original"]), o["cycle_start_year_as_stated"],
                    o["cycle_length_as_stated"], tuple(sorted(o["annual_amounts"].items())))
    loose = lambda o: (o["element"]["element_code_original"], _norm(o["action"]["action_text_original"]),  # noqa: E731
                       o["quantity_value"], _norm(o["unit_original"]))
    rest_b = list(pb)
    exact, partial, only_a = [], [], []
    for o in pa:
        m = next((x for x in rest_b if ex(x) == ex(o)), None)
        if m is not None:
            rest_b.remove(m)
            exact.append([o["observation_id"], m["observation_id"]])
    matched_a = {x[0] for x in exact}
    rest_a = [o for o in pa if o["observation_id"] not in matched_a]
    for o in rest_a:
        m = next((x for x in rest_b if loose(x) == loose(o)), None)
        if m is not None:
            rest_b.remove(m)
            diffs = {k: [_row(o)[k], _row(m)[k]] for k in ("stj", "cy", "annual_amounts", "total")
                     if _row(o)[k] != _row(m)[k]}
            partial.append({"first": o["observation_id"], "second": m["observation_id"], "differences": diffs})
        else:
            only_a.append(_row(o))
    return {"count": [len(pa), len(pb)], "exact_matches": len(exact), "partial_matches": len(partial),
            "coverage_first": f"{len(exact)}/{len(pa)}", "coverage_second": f"{len(exact)}/{len(pb)}",
            "sum_totals": [_sum_totals(pa), _sum_totals(pb)],
            "partial": partial, "only_first": only_a, "only_second": [_row(o) for o in rest_b],
            "exact_pairs": exact}


def text_differences(path_a, path_b, limit=40):
    """Regels (genormaliseerd) die alleen in één van beide PDF-tekstlagen voorkomen."""
    def lines(path):
        pages = tl.pdf_text_layer(path)
        return len(pages), Counter(re.sub(r"\s+", " ", ln["text"]).strip() for p in pages for ln in p.get("lines", []))
    na, la = lines(path_a)
    nb, lb = lines(path_b)
    only_a, only_b = la - lb, lb - la
    return {"pages": [na, nb], "lines_only_first": sum(only_a.values()), "lines_only_second": sum(only_b.values()),
            "examples_only_first": sorted(only_a)[:limit], "examples_only_second": sorted(only_b)[:limit]}


def build(root, document, batch_id, against):
    recs, pos = load_documents(root, document, batch_id, against)
    inc = json.load(open(os.path.join(root, "data", "incoming_registry.json"), encoding="utf-8"))
    canon = dr.load_registry(os.path.join(root, "reports", "document_registry.json"))
    src = {e["document_id"]: {"sha256": e["sha256"], "size": e["file_size_bytes"],
                              "path": "data/incoming/" + e["first_observed_path"]}
           for e in inc["documents"] if e["document_id"] == document}
    for d in canon["documents"]:
        if d["document_id"] in against:
            src[d["document_id"]] = {"sha256": d["sha256"], "size": d["file_size_bytes"],
                                     "path": "data/raw/" + d["relative_path"]}
    batch = json.load(open(os.path.join(root, "data", "incoming_batches", batch_id, "promotion_proposal.json"),
                           encoding="utf-8"))
    rels = json.load(open(os.path.join(root, "data", "price_observations", "document_relations.json"),
                          encoding="utf-8"))["relations"]
    comparisons = {}
    for d in against:
        comparisons[f"{document}_vs_{d}"] = {
            "same_bytes": src[document]["sha256"] == src[d]["sha256"],
            "elements": elements(recs[document], recs[d]),
            "price_observations": observations(pos[document], pos[d]),
            "text_layer": text_differences(os.path.join(root, *src[document]["path"].split("/")),
                                           os.path.join(root, *src[d]["path"].split("/"))),
        }
    return {
        "review_version": VERSION, "document": document, "batch_id": batch_id, "against": list(against),
        "status": "OPEN_REQUIRES_HUMAN_DECISION", "decision": None,
        "note": "Alleen bewijs. Er is niets besloten: geen relatie, geen source cluster, document_relations.json "
                "ongewijzigd. Kies een optie en leg die vast via een aparte, beoordeelde wijziging.",
        "sources": src,
        "open_relation_candidates": [r for r in batch["relation_candidates"] if document in r["document_ids"]],
        "existing_relations_between_compared_documents": [
            r for r in rels if set(r.get("document_ids") or []) <= set(against) and r.get("document_ids")],
        "metadata": metadata(recs), "comparisons": comparisons, "decision_options": OPTIONS,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--document", required=True)
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--against", nargs="+", required=True)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pkg = build(root, args.document, args.batch_id, args.against)
    out = args.out or os.path.join("reports", "review", f"relation_review_{args.document}.json")
    path = os.path.join(root, out)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(pkg, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    for k, c in pkg["comparisons"].items():
        po = c["price_observations"]
        print(f"{k}: bytes gelijk={c['same_bytes']}; elementen gemeenschappelijk {c['elements']['common']} "
              f"van {c['elements']['count']}; observations exact {po['exact_matches']} / gedeeltelijk "
              f"{po['partial_matches']} van {po['count']}; tekstregels alleen-eerste "
              f"{c['text_layer']['lines_only_first']} / alleen-tweede {c['text_layer']['lines_only_second']}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
