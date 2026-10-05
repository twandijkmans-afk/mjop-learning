"""Scaffolding height review v1 (Outer Wall + Scaffolding Semantics v1).

Read-only review uit de canonieke evidence (data/quantity_evidence/): per bevestigd pand OUTER_WALL_GROSS_AREA en
BUILDING_HEIGHT, de tariefklasse volgens de HUIDIGE app-regel en de steigerkosten volgens
  A. de foutgevoelige methode: scopetotaal x tarief(werkhoogte van één planpand);
  B. de correcte per-pand-methode: SOM(pand-m2 x tarief(eigen werkhoogte)).
Geen netwerk, geen nieuwe tarieven, geen indexatie, geen besluiten.

De app-regel is hier alleen gerepliceerd om te kunnen rapporteren (MJOP-App src/quantity.js scaffoldRate /
workHeightFromBuildingHeight): werkhoogte = gebouwhoogte afgerond op 0,1 m en daarna op hele meters;
werkhoogte > 8 m -> EUR 11/m2, anders EUR 6/m2. De bundel bevat geen tarieven: de app rekent.

    python scripts/scaffolding_height_review.py [--check]
"""

import argparse
import hashlib
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "reports" / "quantity" / "scaffolding_height_review_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "scaffolding_height_review_v1.md"
BUNDLES = ROOT / "reports" / "quantity" / "app_bundles"
RESOLUTIONS = ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json"
EXPECTED_BUNDLES = {
    "maldenhof_DOC-005_DOC-006_v3.json": "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933",
    "doc012_meppelweg_v3.json": "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191",
    "maldenhof_expanded_v3.json": "c78f387e66ce7963d7a434270350f0ee8fa4c9f232099f871e83ed202cd2975d",
}
XQ_STEIGER = "XQ-steiger-OUTER_WALL_GROSS_AREA-m2"
RATE_LOW, RATE_HIGH, THRESHOLD_M = Decimal(6), Decimal(11), Decimal(8)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def work_height(h):
    """Zelfde afronding als de app: Math.round(Math.round(h * 10) / 10) (half-up voor positieve hoogtes)."""
    if h is None:
        return None
    return int(Decimal(h).quantize(Decimal("0.1"), ROUND_HALF_UP).quantize(Decimal("1"), ROUND_HALF_UP))


def rate(wh):
    return None if wh is None else (RATE_HIGH if wh > THRESHOLD_M else RATE_LOW)


def band(r):
    return {RATE_HIGH: "> 8 m", RATE_LOW: "<= 8 m"}.get(r)


def eur(d):
    return int(Decimal(d).quantize(Decimal("1"), ROUND_HALF_UP))


def buildings_from_links(links):
    """Gebouwscopes uit de bevestigde building links: documenten met precies dezelfde set bevestigde panden vormen
    één scope (zelfde object). Generiek: geen gebouw- of documentnamen in de code."""
    per_doc = {}
    for r in links["records"]:
        if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED":
            per_doc.setdefault(r["document_id"], set()).add(r["bag_pand_id"])
    groups = {}
    for doc, panden in sorted(per_doc.items()):
        groups.setdefault(frozenset(panden), []).append(doc)
    return sorted((" + ".join(docs), tuple(docs)) for docs in groups.values())


def confirmed_panden(links, docs):
    return sorted({r["bag_pand_id"] for r in links["records"] if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED"
                   and r["document_id"] in docs})


def building_review(name, docs, evidence, links):
    panden = confirmed_panden(links, docs)
    def one(pid, subj):
        f = [e for e in evidence if e["building_id"] == f"BAG:{pid}" and e["source_type"] == "3D_BAG"
             and e["quantity_subject"].get("subject_key") == subj]
        return f[0] if f else None
    rows = []
    for pid in panden:
        w, h = one(pid, "OUTER_WALL_GROSS_AREA"), one(pid, "BUILDING_HEIGHT")
        wh = work_height(h["value"]) if h else None
        r = rate(wh)
        rows.append({"bag_pand_id": pid,
                     "outer_wall_gross_area_m2": w["value"] if w else None, "outer_wall_evidence_id": w["evidence_id"] if w else None,
                     "building_height_m": h["value"] if h else None, "building_height_evidence_id": h["evidence_id"] if h else None,
                     "height_raw_inputs": (h or {}).get("source_ref", {}).get("raw_inputs"),
                     "snapshot_id": (h or w or {}).get("source_ref", {}).get("snapshot_id"),
                     "app_work_height_m": wh, "tariff_band": band(r), "rate_eur_per_m2": None if r is None else str(r),
                     "pand_cost_eur": None if r is None or not w else str(Decimal(w["value"]) * r)})
    scope_id = bqe.building_id_for(panden) if len(panden) > 1 else f"BAG:{panden[0]}"
    agg = [e for e in evidence if e["building_id"] == scope_id and e["quantity_subject"].get("subject_key") == "OUTER_WALL_GROSS_AREA"]
    total = Decimal(agg[0]["value"]) if agg else None
    walls = [Decimal(r["outer_wall_gross_area_m2"]) for r in rows if r["outer_wall_gross_area_m2"] is not None]
    heights = [Decimal(r["building_height_m"]) for r in rows if r["building_height_m"] is not None]
    missing_h = [r["bag_pand_id"] for r in rows if r["building_height_m"] is None]
    bands = {}
    for r in rows:
        bands[r["tariff_band"] or "ONBEKEND"] = bands.get(r["tariff_band"] or "ONBEKEND", 0) + 1
    # A: foutgevoelig — scopetotaal x tarief van één planpand (voor elk mogelijk planpand)
    method_a = sorted({eur(total * Decimal(r["rate_eur_per_m2"])) for r in rows if r["rate_eur_per_m2"]}) if total is not None else []
    # B: correct — som per pand (in centen exact, één afronding aan het eind)
    method_b = None if missing_h or len(walls) != len(rows) else eur(sum(Decimal(r["pand_cost_eur"]) for r in rows))
    return {
        "name": name, "documents": list(docs), "kind": "MULTI_PAND_SCOPE" if len(panden) > 1 else "SINGLE_PAND",
        "building_id": scope_id, "pand_count": len(panden), "rows": rows,
        "outer_wall_scope_evidence_id": agg[0]["evidence_id"] if agg else None,
        "outer_wall_total_m2": None if total is None else str(total),
        "sum_of_pand_walls_equals_scope_total": total is not None and sum(walls) == total,
        "height_min_m": str(min(heights)) if heights else None, "height_max_m": str(max(heights)) if heights else None,
        "panden_per_tariff_band": dict(sorted(bands.items())), "panden_missing_height": missing_h,
        "single_tariff_band": len([b for b in bands if b != "ONBEKEND"]) == 1 and not missing_h,
        "cost_A_scope_total_x_plan_pand_rate_eur": method_a,
        "cost_B_per_pand_sum_eur": method_b,
        "A_equals_B": method_b is not None and method_a == [method_b],
    }


def build():
    evidence = json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))["evidence"]
    links = bl.load_store()
    vocab = json.loads(xw.SUBJECTS.read_text(encoding="utf-8"))
    roles = {s["subject_key"]: s.get("product_role") for s in vocab["subjects"]}
    eff = xw.effective()
    res = json.loads(RESOLUTIONS.read_text(encoding="utf-8"))
    return {
        "report_version": "scaffolding_height_review_v1",
        "inputs": {"evidence_sha256": sha(bqe.OUT_EVIDENCE), "subjects_vocab_sha256": sha(xw.SUBJECTS),
                   "app_crosswalk_sha256": sha(xw.APP_CROSSWALK), "network": "geen (alleen canonieke evidence/snapshots)"},
        "app_rule_replicated_for_review": {
            "source": "MJOP-App src/quantity.js (scaffoldRate, workHeightFromBuildingHeight); bestaande tarieven, geen nieuwe",
            "work_height": "round(round(BUILDING_HEIGHT, 0.1 m), 1 m)", "rate": "werkhoogte > 8 m -> EUR 11/m2, anders EUR 6/m2",
            "indexation": "geen"},
        "buildings": [building_review(n, d, evidence, links) for n, d in buildings_from_links(links)],
        "generic_rule": {
            "SINGLE_PAND": "hoeveelheid OUTER_WALL_GROSS_AREA x tarief(werkhoogte van het pand)",
            "MULTI_PAND_SAME_BAND": "scopetotaal OUTER_WALL_GROSS_AREA x gemeenschappelijk tarief",
            "MULTI_PAND_MIXED_BANDS": "SOM(pand OUTER_WALL_GROSS_AREA x tarief(eigen BUILDING_HEIGHT)); geen gemiddelde hoogte, geen max-hoogte, geen stille fallback",
            "MISSING_HEIGHT": "kosten onbekend / review required (nooit EUR 0, nooit een willekeurige hoogte)",
            "carrier": "bundel v3 PRIMARY-regel steiger: optionele pricing_context met per pand BUILDING_HEIGHT-evidence-ref + waarde (geen schema-ophoging)"},
        "state": {
            "xq_steiger_status": eff[XQ_STEIGER]["status"], "xq_steiger_decision_id": eff[XQ_STEIGER]["decision_id"],
            "building_height_product_role": roles.get("BUILDING_HEIGHT"),
            "historical_2110_mappings_verified": sorted(k for k, v in eff.items() if "2110" in k and v["status"] == "VERIFIED"),
            "crosswalk_decisions": sorted(r["decision_id"] for r in xw.load_store()["records"]),
            "quantity_resolutions": len(res["records"]),
            "reference_bundles": {n: {"sha256": sha(BUNDLES / n), "unchanged": sha(BUNDLES / n) == h} for n, h in sorted(EXPECTED_BUNDLES.items())},
        },
    }


def render(r):
    L = ["# Scaffolding height review v1", "",
         "Read-only, uit de canonieke evidence. Tariefklasse volgens de huidige app-regel (werkhoogte = gebouwhoogte op 0,1 m "
         "en dan op hele meters; > 8 m -> EUR 11/m2, anders EUR 6/m2). Geen nieuwe tarieven, geen indexatie, geen netwerk.", ""]
    for b in r["buildings"]:
        L += [f"## {b['name']} — {b['kind']}, {b['pand_count']} pand(en)", "",
              "| BAG pand | OUTER_WALL_GROSS_AREA (m2) | BUILDING_HEIGHT (m) | werkhoogte app | tariefklasse | EUR/m2 |",
              "|---|---:|---:|---:|---|---:|"]
        for x in b["rows"]:
            hm = "ONTBREEKT" if x["building_height_m"] is None else str(Decimal(x["building_height_m"]).quantize(Decimal("0.001")))
            L.append(f"| {x['bag_pand_id']} | {x['outer_wall_gross_area_m2']} | {hm} | {x['app_work_height_m']} | {x['tariff_band']} | {x['rate_eur_per_m2']} |")
        L += ["", f"- Totaal OUTER_WALL_GROSS_AREA: **{b['outer_wall_total_m2']} m2** (`{b['outer_wall_scope_evidence_id']}`; som van de panden = totaal: "
                  f"{'ja' if b['sum_of_pand_walls_equals_scope_total'] else 'NEE'}).",
              f"- Hoogte min/max: {Decimal(b['height_min_m']).quantize(Decimal('0.001'))} / {Decimal(b['height_max_m']).quantize(Decimal('0.001'))} m. Panden per tariefklasse: "
                  + ", ".join(f"{k}: {v}" for k, v in b["panden_per_tariff_band"].items()) + ".",
              f"- Eén tariefklasse: **{'ja' if b['single_tariff_band'] else 'nee'}**.",
              f"- A (foutgevoelig, scopetotaal x tarief van één planpand): EUR {', '.join(str(v) for v in b['cost_A_scope_total_x_plan_pand_rate_eur'])}.",
              f"- B (correct, som per pand): EUR {b['cost_B_per_pand_sum_eur']}. A = B: {'ja' if b['A_equals_B'] else 'nee'}.", ""]
    g = r["generic_rule"]
    L += ["## Generieke regel", ""] + [f"- **{k}**: {v}" for k, v in g.items()] + [""]
    s = r["state"]
    L += ["## Stand", "",
          f"- {XQ_STEIGER}: {s['xq_steiger_status']} ({s['xq_steiger_decision_id'] or 'geen besluit'}).",
          f"- BUILDING_HEIGHT product_role: {s['building_height_product_role']}. Geverifieerde 2110-mappings: {s['historical_2110_mappings_verified'] or 'geen'}.",
          f"- Crosswalk-besluiten: {', '.join(s['crosswalk_decisions'])}. Quantity resolutions: {s['quantity_resolutions']}.",
          "- Referentiebundels ongewijzigd: " + ", ".join(f"{k} {'ja' if v['unchanged'] else 'NEE'}" for k, v in s["reference_bundles"].items()) + ".", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = build()
    js, md = json.dumps(r, ensure_ascii=False, indent=1) + "\n", render(r)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("OK" if ok else "VEROUDERD")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(f"-> {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
