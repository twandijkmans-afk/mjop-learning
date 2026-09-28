#!/usr/bin/env python3
"""
compare_extractions.py - READ-ONLY vergelijking van twee extracties van hetzelfde document,
bijv. de bestaande geverifieerde DOC-010 met de deterministische pilot.

Geen oordeel over welke versie klopt: het rapport zegt alleen per item of de
waarden gelijk zijn, verschillen, of maar aan één kant voorkomen, en markeert
wat een mens moet bekijken. Records worden op INHOUD gekoppeld (niet op ID,
want ID's worden per route anders genummerd):

  elementen           (elementnaam, locatie)             - hoofdletterongevoelig, witruimte samengevoegd
  onderhoudsacties    (elementsleutel, actietekst, jaar)  - geen fuzzy matching
  conditiescores      via het gekoppelde element

Uitkomsten: exact_equal, different_value, only_deterministic, only_existing,
null_or_unknown (beide leeg), ambiguous_duplicate_key. human_review_needed is
waar bij elk verschil, eenzijdig item, dubbelzinnige sleutel, of als een van
beide kanten zelf requires_human_review heeft.

Gebruik:
    python3 scripts/compare_extractions.py --existing data/verified/DOC-010.json \\
        --pilot data/extracted/_deterministic_pilot/DOC-010.json \\
        --out reports/deterministic_pilot/DOC-010_comparison.json
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nl_values as nv  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORIES = ["building", "elements", "condition_scores", "maintenance_actions", "quantities", "units",
              "planned_years", "amounts", "provenance"]


def _txt(v):
    return None if v is None else re.sub(r"\s+", " ", str(v)).strip().casefold()


def _num(v):
    """Getal voor gelijkheidsvergelijking; beide notaties ('5,93', '1351.00', 1935). Niet
    herleidbaar -> None (dan wordt op tekst vergeleken)."""
    if v is None:
        return None
    if isinstance(v, (int, Decimal)):
        return Decimal(v)
    s = str(v).strip()
    if re.fullmatch(r"\d+(\.\d+)?", s) and not re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        try:
            return Decimal(s)
        except InvalidOperation:
            return None
    d, _ = nv.parse_decimal_nl(s)
    return d


def _val(obj, key):
    x = (obj or {}).get(key)
    if isinstance(x, dict):
        if "value" in x:
            return x.get("value")
        if "original_value" in x:
            return x.get("original_value")
    return x


def _review(obj, key=None):
    x = (obj or {}).get(key) if key else obj
    return bool(isinstance(x, dict) and x.get("requires_human_review"))


def _prov(obj, key):
    x = (obj or {}).get(key)
    return x.get("provenance") if isinstance(x, dict) else None


def _outcome(a, b, numeric=False):
    if a is None and b is None:
        return "null_or_unknown"
    if a is None:
        return "only_deterministic"
    if b is None:
        return "only_existing"
    if numeric:
        na, nb = _num(a), _num(b)
        if na is not None and nb is not None:
            return "exact_equal" if na == nb else "different_value"
    return "exact_equal" if _txt(a) == _txt(b) else "different_value"


def _item(category, key, existing, deterministic, outcome, review=False, **extra):
    it = {"category": category, "key": key, "existing": existing, "deterministic": deterministic,
          "outcome": outcome,
          "human_review_needed": bool(review) or outcome not in ("exact_equal", "null_or_unknown")}
    it.update(extra)
    return it


def _el_key(el):
    return (_txt(_val(el, "element_name") or _val(el, "element_type")), _txt(_val(el, "location")) or "")


def _index(records, keyf):
    idx = defaultdict(list)
    for r in records:
        idx[keyf(r)].append(r)
    return idx


def compare(existing, pilot):
    items = []
    eb, pb = existing.get("building") or {}, pilot.get("building") or {}
    for f in ("construction_year", "number_of_units", "building_type", "address", "inspection_date", "mjop_period"):
        a, b = _val(eb, f), _val(pb, f)
        items.append(_item("building", f, a, b, _outcome(a, b, numeric=f in ("construction_year", "number_of_units")),
                           review=_review(eb, f) or _review(pb, f)))

    # elementen
    e_idx = _index(existing.get("elements", []), _el_key)
    p_idx = _index(pilot.get("elements", []), _el_key)
    e_key_of = {e["element_id"]: _el_key(e) for e in existing.get("elements", [])}
    p_key_of = {e["element_id"]: _el_key(e) for e in pilot.get("elements", [])}
    for key in sorted(set(e_idx) | set(p_idx), key=str):
        E, P = e_idx.get(key, []), p_idx.get(key, [])
        k = f"{key[0]} | {key[1]}"
        if len(E) > 1 or len(P) > 1:
            items.append(_item("elements", k, len(E), len(P), "ambiguous_duplicate_key"))
            continue
        e, p = (E or [None])[0], (P or [None])[0]
        if e is None or p is None:
            items.append(_item("elements", k, e and e["element_id"], p and p["element_id"],
                               "only_deterministic" if e is None else "only_existing"))
            continue
        items.append(_item("elements", k, e["element_id"], p["element_id"], "exact_equal",
                           code=[_val(e, "element_code"), _val(p, "element_code")]))
        items.append(_item("quantities", f"element {k}", _val(e, "quantity"), _val(p, "quantity"),
                           _outcome(_val(e, "quantity"), _val(p, "quantity"), numeric=True),
                           review=_review(e, "quantity") or _review(p, "quantity")))
        items.append(_item("units", f"element {k}", _val(e, "unit"), _val(p, "unit"),
                           _outcome(_val(e, "unit"), _val(p, "unit"))))
        pe, pp = _prov(e, "element_name"), _prov(p, "element_name")
        items.append(_item("provenance", f"element {k}", pe and pe.get("page"), pp and pp.get("page"),
                           _outcome(pe and pe.get("page"), pp and pp.get("page"), numeric=True),
                           deterministic_block_id=pp and pp.get("block_id")))

    # conditiescores via element
    def cond_by_key(rec, key_of):
        out = defaultdict(list)
        for o in rec.get("observations", []):
            cs = (o.get("condition_score") or {}).get("original_value")
            if cs is not None:
                out[key_of.get(o["element_id"])].append((cs, o.get("requires_human_review")))
        return out
    ce, cp = cond_by_key(existing, e_key_of), cond_by_key(pilot, p_key_of)
    for key in sorted(set(ce) | set(cp), key=str):
        k = f"{key[0]} | {key[1]}" if key else "(geen element)"
        E, P = ce.get(key, []), cp.get(key, [])
        if len(E) > 1 or len(P) > 1:
            items.append(_item("condition_scores", k, [x[0] for x in E], [x[0] for x in P], "ambiguous_duplicate_key"))
            continue
        a, b = (E[0][0] if E else None), (P[0][0] if P else None)
        items.append(_item("condition_scores", k, a, b, _outcome(a, b),
                           review=(E and E[0][1]) or (P and P[0][1])))

    # onderhoudsacties: groep (element, actietekst) -> jaren; daarna per (element, actie, jaar)
    def act_key(a, key_of):
        el = key_of.get(a.get("element_id"), ("(ongekoppeld)", ""))
        return (el, _txt(_val(a, "action")))
    ga = _index(existing.get("maintenance_actions", []), lambda a: act_key(a, e_key_of))
    gp = _index(pilot.get("maintenance_actions", []), lambda a: act_key(a, p_key_of))
    for key in sorted(set(ga) | set(gp), key=str):
        (el, act) = key
        k = f"{el[0]} | {el[1]} -> {act}"
        E, P = ga.get(key, []), gp.get(key, [])
        ye, yp = sorted(_val(a, "planned_year") for a in E), sorted(_val(a, "planned_year") for a in P)
        if not E or not P:
            items.append(_item("maintenance_actions", k, len(E) or None, len(P) or None,
                               "only_deterministic" if not E else "only_existing", years_existing=ye,
                               years_deterministic=yp))
            continue
        items.append(_item("maintenance_actions", k, len(E), len(P),
                           "exact_equal" if len(E) == len(P) else "different_value"))
        items.append(_item("planned_years", k, ye, yp, "exact_equal" if ye == yp else "different_value"))
        by_year_e, by_year_p = _index(E, lambda a: _val(a, "planned_year")), _index(P, lambda a: _val(a, "planned_year"))
        for y in sorted(set(by_year_e) & set(by_year_p), key=str):
            if len(by_year_e[y]) > 1 or len(by_year_p[y]) > 1:
                items.append(_item("amounts", f"{k} [{y}]", None, None, "ambiguous_duplicate_key"))
                continue
            a, p = by_year_e[y][0], by_year_p[y][0]
            rv_ = a.get("requires_human_review") or p.get("requires_human_review")
            items.append(_item("amounts", f"{k} [{y}]", a.get("total_cost_as_stated"), p.get("total_cost_as_stated"),
                               _outcome(a.get("total_cost_as_stated"), p.get("total_cost_as_stated"), numeric=True),
                               review=rv_))
            items.append(_item("quantities", f"{k} [{y}]", _val(a, "quantity"), _val(p, "quantity"),
                               _outcome(_val(a, "quantity"), _val(p, "quantity"), numeric=True), review=rv_))
            items.append(_item("units", f"{k} [{y}]", _val(a, "unit"), _val(p, "unit"),
                               _outcome(_val(a, "unit"), _val(p, "unit"))))
            pe = (a.get("planned_year") or {}).get("provenance") or {}
            pp = (p.get("planned_year") or {}).get("provenance") or {}
            items.append(_item("provenance", f"{k} [{y}]", pe.get("page"), pp.get("page"),
                               _outcome(pe.get("page"), pp.get("page"), numeric=True),
                               deterministic_block_id=pp.get("block_id")))

    summary = {c: dict(Counter(i["outcome"] for i in items if i["category"] == c)) for c in CATEGORIES}
    return {
        "comparison": "read-only; geen automatische keuze welke versie correct is",
        "document_id": pilot.get("document_id") or existing.get("document_id"),
        "existing_extraction_mode": existing.get("extraction_mode", "llm"),
        "deterministic_extraction_mode": pilot.get("extraction_mode"),
        "matching": {"elements": "element_name + location (casefold, witruimte samengevoegd)",
                     "maintenance_actions": "elementsleutel + actietekst, daarna per planned_year; geen fuzzy matching"},
        "summary": summary,
        "human_review_needed": sum(1 for i in items if i["human_review_needed"]),
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--existing", required=True)
    ap.add_argument("--pilot", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_real = os.path.realpath(args.out)
    if out_real.startswith(os.path.realpath(os.path.join(PROJECT_ROOT, "data")) + os.sep):
        print("Weigering: het vergelijkingsrapport hoort niet in data/ (bijv. reports/deterministic_pilot/)",
              file=sys.stderr)
        raise SystemExit(2)
    with open(args.existing, encoding="utf-8") as f:
        existing = json.load(f)
    with open(args.pilot, encoding="utf-8") as f:
        pilot = json.load(f)
    report = compare(existing, pilot)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"{report['human_review_needed']} items vragen menselijke beoordeling -> {args.out}")


if __name__ == "__main__":
    main()
