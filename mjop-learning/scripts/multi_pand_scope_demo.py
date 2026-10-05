"""Maldenhof multi-pand scope demo v1 — read-only bronnenvergelijking op de canonieke BAG/3D BAG-snapshots.

SOURCE COMPARISON, geen accuracy-benchmark. Schrijft NIETS in data/: geen building links, geen crosswalk-besluiten,
geen evidence-store, geen quantity resolution. Alleen:
    reports/quantity/maldenhof_multi_pand_scope_demo_v1.json
    reports/quantity/maldenhof_multi_pand_scope_demo_v1.md

Gebruikt dezelfde code als de echte keten (build_building_quantity_evidence.bag3d_evidence + scope_aggregate) op
de canonieke snapshots (data/bag_snapshots, bag_snapshot_v1). De scope is een PREVIEW-hypothese (panden waarvan
alle adressen de documentpostcode hebben) en is NIET door een mens bevestigd; de evidence-ID's in dit rapport zijn
berekend maar niet opgeslagen.

    python scripts/multi_pand_scope_demo.py [--check]
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag3d_quantity_rules as rules_mod  # noqa: E402
import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import quantity_evidence as qe  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("DOC-005", "DOC-006")
SUBJECT = "ROOF_FLAT_AREA"
OUT_JSON = ROOT / "reports" / "quantity" / "maldenhof_multi_pand_scope_demo_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "maldenhof_multi_pand_scope_demo_v1.md"
QO_PATH = ROOT / "data" / "quantity_observations" / "quantity_observations_v1.json"
MAPPINGS = ("HSM-ROOF_FLAT_AREA-4711-m2", "XW-dak-plat-4711-m2", "HSM-ROOF_SLOPED_AREA-4712-m2", "XW-dak-hellend-4712-m2",
            "XW-gevel-metselwerk-2110-m2")


def build():
    snaps = {s["document_id"]: s for s in bs.load_snapshots() if s["document_id"] in DOCS}
    missing_docs = [d for d in DOCS if d not in snaps]
    if missing_docs:
        raise SystemExit(f"geen canonieke snapshot voor {missing_docs} (scripts/bag_snapshots.py fetch-range)")
    snap = snaps["DOC-005"]
    rules, vocab = rules_mod.load_rules()
    subjects = {s["subject_key"]: s for s in vocab["subjects"]}
    agg_rule = next(r for r in vocab["scope_aggregation_rules"] if r["status"] == "ACTIVE")
    match = {m["pdok_id"]: m for m in snap["address_matches"]}

    # PREVIEW-scope: panden waarvan ALLE adrespunten in het bereik de documentpostcode hebben (geen menselijke bevestiging)
    scope = []
    for p in snap["panden"]:
        addrs = [match[a] for a in p["contains_address_point_of"]]
        if addrs and all(a["postcode_matches_document"] for a in addrs):
            scope.append(p["bag_pand_id"])
    scope = sorted(scope)
    others = sorted(p["bag_pand_id"] for p in snap["panden"] if p["bag_pand_id"] not in scope)

    per_pand, children, not_available = [], {}, []
    for pid in scope:
        evs, na = bqe.bag3d_evidence(pid, snap, rules, subjects, [])
        not_available += na
        ev = next((e for e in evs if e["quantity_subject"]["subject_key"] == SUBJECT), None)
        if ev:
            children[pid] = ev
        p = next(x for x in snap["panden"] if x["bag_pand_id"] == pid)
        per_pand.append({
            "bag_pand_id": pid,
            "addresses": sorted((match[a]["weergavenaam"] for a in p["contains_address_point_of"]),
                                key=lambda w: int(w.split(",")[0].split()[-1])),
            "b3_opp_dak_plat": ev["value"] if ev else None,
            "evidence_id_preview": ev["evidence_id"] if ev else None,
            "method_class": ev["method_class"] if ev else None,
            "threedbag_url": p["threedbag"]["url"], "threedbag_response_sha256": p["threedbag"]["response_sha256"],
            "fetched_at": p["threedbag"]["fetched_at"],
        })
    agg, not_pub = bqe.scope_aggregate(scope, subjects[SUBJECT], agg_rule, children, [])
    # DOC-006-snapshot: zelfde panden en dezelfde 3D BAG-waarden?
    s6 = snaps["DOC-006"]
    same_panden = sorted(p["bag_pand_id"] for p in s6["panden"]) == sorted(p["bag_pand_id"] for p in snap["panden"])
    same_values = all((next(x for x in s6["panden"] if x["bag_pand_id"] == pid)["threedbag"]["attributes"] or {}).get("b3_opp_dak_plat")
                      == (next(x for x in snap["panden"] if x["bag_pand_id"] == pid)["threedbag"]["attributes"] or {}).get("b3_opp_dak_plat")
                      for pid in scope)

    qos = json.loads(QO_PATH.read_text(encoding="utf-8"))["observations"]
    hist = [o for o in qos if o["document_id"] in DOCS and o["element"]["element_code_internal"] == "4711" and o["unit_normalized"] == "m2"]
    hist_rows = [{"quantity_observation_id": o["quantity_observation_id"], "document_id": o["document_id"],
                  "description": o["element"]["element_description_original"], "location": o["element"]["location_original"],
                  "value": o["quantity_value"], "unit": o["unit_normalized"], "method_class": o["method_class"],
                  "page": o["provenance"]["page"], "text_fragment": o["provenance"]["text_fragment"],
                  "source_cluster": o["source_cluster"], "document_relations": o["document_relations"],
                  "caveats": o["caveats"], "status": o["status"]} for o in hist]
    hist_values = sorted({r["value"] for r in hist_rows})
    diff = None
    if agg and len(hist_values) == 1:
        h, b = Decimal(hist_values[0]), Decimal(agg["value"])
        diff = {"historical_minus_3dbag_m2": str(h - b), "pct_of_3dbag": str(((h - b) / b * 100).quantize(Decimal("0.01"))),
                "note": "feitelijk verschil; geen fout van één bron, geen gemiddelde, geen winnaar"}
    eff = xw.effective()
    links = bl.load_store()
    res_store = json.loads((ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json").read_text(encoding="utf-8"))
    building_id = bqe.building_id_for(scope)
    return {
        "report_version": "maldenhof_multi_pand_scope_demo_v1",
        "note": "SOURCE COMPARISON, geen accuracy-benchmark. Niets opgeslagen; scope is een PREVIEW-hypothese, niet door een mens bevestigd.",
        "snapshots": [{"document_id": d, "snapshot_id": s["snapshot_id"], "fetched_at": s["fetched_at"],
                       "query": s["query"]["q"], "requests": len(s["requests"]),
                       "addresses_found": len(s["address_matches"]),
                       "addresses_matching_document_postcode": sum(1 for m in s["address_matches"] if m["postcode_matches_document"]),
                       "candidate_panden": len(s["panden"])} for d, s in sorted(snaps.items())],
        "doc006_snapshot_same_panden_and_flat_roof_values": bool(same_panden and same_values),
        "preview_scope": {"rule": "panden waarvan alle adrespunten de documentpostcode (1106 EZ) hebben",
                          "status": "PREVIEW_NOT_HUMAN_CONFIRMED", "building_id": building_id,
                          "bag_pand_ids": scope, "pand_count": len(scope),
                          "address_count": sum(len(p["addresses"]) for p in per_pand),
                          "other_candidate_panden_in_snapshot": others},
        "bag3d_per_pand": per_pand,
        "bag3d_rules_not_available": not_available,
        "derived_complex_total": None if agg is None else {
            "value": agg["value"], "unit": agg["unit_normalized"], "method_class": agg["method_class"],
            "quantity_kind": agg["quantity_subject"]["quantity_kind"], "subject_key": SUBJECT,
            "evidence_id_preview": agg["evidence_id"], "formula": agg["calculation"]["formula"],
            "rule_id": agg["calculation"]["rule_id"], "rule_version": agg["calculation"]["rule_version"],
            "child_evidence_ids": agg["calculation"]["input_evidence_ids"], "snapshot_ids": agg["source_ref"]["snapshot_ids"],
            "missing_bag_pand_ids": agg["source_ref"]["missing_bag_pand_ids"]},
        "derived_complex_total_not_published": not_pub,
        "historical": {"rows": hist_rows, "values": hist_values, "level": "COMPLEX (hele VvE-scope; niet over panden verdeeld)",
                       "dependency": "DOC-005 en DOC-006 zijn version_of_same_mjop (DREL-002): één historische bron, geen twee metingen"},
        "difference": diff,
        "external_definition": next(d for d in vocab["bag3d_field_definitions_external"] if d["field"] == "b3_opp_dak_plat"),
        "mapping_status": {m: eff[m]["status"] for m in MAPPINGS},
        "why_no_quantity_resolution": [
            f"building links: {len(links['records'])} vastgelegd (geen enkel pand is door een mens bevestigd)",
            f"HSM-ROOF_FLAT_AREA-4711-m2: {eff['HSM-ROOF_FLAT_AREA-4711-m2']['status']} (niet geverifieerd) — zonder geverifieerde "
            "mapping ontstaat geen historische evidence",
            f"XW-dak-plat-4711-m2: {eff['XW-dak-plat-4711-m2']['status']} — zonder geverifieerde app-crosswalk geen app-bundel",
            f"quantity_resolution_records: {len(res_store['records'])} — een resolutie is altijd een menselijk besluit",
        ],
    }


def render(r):
    sc, agg, d = r["preview_scope"], r["derived_complex_total"], r["difference"]
    L = ["# Maldenhof multi-pand scope demo v1 (read-only)", "", r["note"], "",
         "## Canonieke snapshots (bag_snapshot_v1)", "",
         "| Document | Snapshot | Opgehaald | Query | Requests | Adressen | Postcode = document | Kandidaat-panden |",
         "|---|---|---|---|---|---|---|---|"]
    L += [f"| {s['document_id']} | {s['snapshot_id']} | {s['fetched_at']} | {s['query']} | {s['requests']} | {s['addresses_found']} | "
          f"{s['addresses_matching_document_postcode']} | {s['candidate_panden']} |" for s in r["snapshots"]]
    L += ["", f"DOC-006-snapshot: zelfde panden en dezelfde plat-dakwaarden als DOC-005: "
              f"{'ja' if r['doc006_snapshot_same_panden_and_flat_roof_values'] else 'NEE'}.", "",
          f"## Gebouwscope (PREVIEW, niet bevestigd): {sc['pand_count']} panden, {sc['address_count']} adressen", "",
          f"Regel: {sc['rule']}. building_id: `{sc['building_id']}`. Overige kandidaat-panden in de snapshot (oneven zijde): "
          f"{len(sc['other_candidate_panden_in_snapshot'])}.", "",
          "| BAG-pand | Adressen | 3D BAG plat dak (m²) | Methode | Evidence (preview, niet opgeslagen) |", "|---|---|---|---|---|"]
    L += [f"| {p['bag_pand_id']} | {', '.join(a.split(',')[0] for a in p['addresses'])} | {p['b3_opp_dak_plat'] or 'NOT_AVAILABLE'} | "
          f"{p['method_class'] or '—'} | {p['evidence_id_preview'] or '—'} |" for p in r["bag3d_per_pand"]]
    L += [""]
    if agg:
        L += [f"**Afgeleid complextotaal (3D BAG): {agg['value']} {agg['unit']}** — {agg['method_class']}, {agg['quantity_kind']}, "
              f"{agg['rule_id']} v{agg['rule_version']}, formule `{agg['formula']}`, {len(agg['child_evidence_ids'])} child evidence, "
              f"ontbrekende panden: {len(agg['missing_bag_pand_ids'])}. Preview-ID {agg['evidence_id_preview']}.", ""]
    else:
        L += [f"**Geen complextotaal gepubliceerd:** {r['derived_complex_total_not_published']}", ""]
    L += ["## Historisch MJOP (complexniveau)", "", "| Observation | Document | Omschrijving | Locatie | Waarde | Pagina | Fragment |",
          "|---|---|---|---|---|---|---|"]
    L += [f"| {h['quantity_observation_id']} | {h['document_id']} | {h['description']} | {h['location']} | {h['value']} {h['unit']} | "
          f"{h['page']} | `{h['text_fragment']}` |" for h in r["historical"]["rows"]]
    L += ["", f"- Niveau: {r['historical']['level']}.", f"- {r['historical']['dependency']}.", ""]
    if d:
        L += ["## Naast elkaar (geen keuze)", "", "| Plat dak | Waarde | Methode | Bron |", "|---|---|---|---|",
              f"| Historisch MJOP | {r['historical']['values'][0]} m² | SOURCE_REPORTED | DOC-005 / DOC-006, complexniveau |",
              f"| 3D BAG | {agg['value']} m² | GEOMETRY_DERIVED | som van {sc['pand_count']} panden (preview-scope) |", "",
              f"Verschil historisch − 3D BAG: {d['historical_minus_3dbag_m2']} m² ({d['pct_of_3dbag']}% van 3D BAG) — {d['note']}.", ""]
    ext = r["external_definition"]
    L += ["## Definitie 3D BAG-veld", "", f"`{ext['field']}`: \"{ext['definition_nl']}\" ({ext['unit']}) — {ext['source']}. {ext['caution']}", "",
          "## Status mappings en resolutie", ""]
    L += [f"- {k}: {v}" for k, v in r["mapping_status"].items()]
    L += ["", "Waarom nog geen quantity resolution:", ""] + [f"- {x}" for x in r["why_no_quantity_resolution"]] + [""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = build()
    js, md = json.dumps(r, ensure_ascii=False, indent=1) + "\n", render(r)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("multi-pand demo up-to-date" if ok else "multi-pand demo NIET up-to-date")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"panden": r["preview_scope"]["pand_count"], "adressen": r["preview_scope"]["address_count"],
                      "totaal": (r["derived_complex_total"] or {}).get("value"), "historisch": r["historical"]["values"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
