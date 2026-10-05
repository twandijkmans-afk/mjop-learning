"""Maldenhof Quantity Activation v1 — read-only rapport over de echte, door een mens bevestigde Maldenhof-scope.

Leest alleen (schrijft niets in data/):
  data/building_links/building_link_records.json        menselijke building links (CONFIRMED / REJECTED)
  data/crosswalk_decisions/crosswalk_decision_records.json  menselijke mapping-besluiten
  data/quantity_evidence/building_quantity_evidence_v1.json  evidence uit scripts/build_building_quantity_evidence.py
  reports/quantity/3dbag_vs_historical_v1.json           vergelijkingen
  data/quantity_resolutions/quantity_resolution_records.json
  vocabularies/quantity_subjects_v1.json, vocabularies/app_element_crosswalk_v1.json

Schrijft:
  reports/quantity/maldenhof_quantity_activation_v1.json / .md

Geen resolutie, geen keuze, geen gemiddelde. Historische dakbedekking (ROOF_COVERING_REPORTED_AREA) en 3D BAG
plat dakoppervlak (ROOF_FLAT_AREA) zijn verwante, NIET gelijke onderwerpen.

    python scripts/maldenhof_quantity_activation.py [--check]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import quantity_evidence as qe  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("DOC-005", "DOC-006")
RESOLUTIONS = ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json"
OUT_JSON = ROOT / "reports" / "quantity" / "maldenhof_quantity_activation_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "maldenhof_quantity_activation_v1.md"
MAPPINGS = ("XW-dak-plat-4711-m2", "HSM-ROOF_FLAT_AREA-4711-m2", "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006")


def build():
    links = bl.load_store()
    snaps = {s["snapshot_id"]: s for s in bs.load_snapshots()}
    active = [r for r in links["records"] if r["status"] == "ACTIVE" and r["document_id"] in DOCS]
    per_doc = {}
    for d in DOCS:
        recs = [r for r in active if r["document_id"] == d]
        snap_ids = sorted({r["evidence"]["snapshot_id"] for r in recs})
        postcode = {m["pdok_id"]: m["postcode"] for sid in snap_ids for m in snaps[sid]["address_matches"]}

        def row(r):
            return {"link_id": r["link_id"], "bag_pand_id": r["bag_pand_id"],
                    "postcodes": sorted({postcode[a] for a in r["evidence"]["address_matches_containing_pand"]}),
                    "addresses": len(r["evidence"]["address_matches_containing_pand"])}
        per_doc[d] = {
            "snapshot_ids": snap_ids,
            "confirmed": [row(r) for r in sorted(recs, key=lambda x: x["bag_pand_id"]) if r["link_status"] == "CONFIRMED"],
            "rejected": [row(r) for r in sorted(recs, key=lambda x: x["bag_pand_id"]) if r["link_status"] == "REJECTED"],
            "reviewers": sorted({(r["reviewer"]["reviewer_id"], r["reviewer"]["reviewer_type"]) for r in recs}),
            "reasons": sorted({(r["link_status"], r["decision_reason"]) for r in recs}),
        }
    scopes = {d: bqe.building_id_for([x["bag_pand_id"] for x in v["confirmed"]]) for d, v in per_doc.items() if v["confirmed"]}
    building_id = scopes.get("DOC-005")

    eff = xw.effective()
    decisions = [{"decision_id": r["decision_id"], "mapping_id": r["mapping_id"], "decision": r["decision"],
                  "reviewer": r["reviewer"], "reviewed_at": r["reviewed_at"], "decision_reason": r["decision_reason"],
                  "status": r["status"]} for r in xw.load_store()["records"] if r["mapping_id"] in MAPPINGS]
    vocab = json.loads(xw.SUBJECTS.read_text(encoding="utf-8"))
    subj = {s["subject_key"]: s for s in vocab["subjects"]}

    store = json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))
    ev_by_id = {e["evidence_id"]: e for e in store["evidence"]}
    in_scope = [e for e in store["evidence"] if e["building_id"] == building_id]
    agg = next((e for e in in_scope if e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"
                and e["source_ref"].get("aggregation")), None)
    children = [ev_by_id[c] for c in (agg["calculation"]["input_evidence_ids"] if agg else [])]
    hist = sorted((e for e in in_scope if e["source_type"] == "MJOP_ELEMENT_OVERVIEW"), key=lambda e: e["source_ref"]["document_id"])
    comps = [c for c in json.loads(bqe.OUT_JSON.read_text(encoding="utf-8"))["comparisons"] if c["building_id"] == building_id]
    rel = next(r for r in vocab["subject_relations"] if r["relation_id"] == "SREL-ROOF_COVERING_REPORTED_AREA-ROOF_FLAT_AREA")

    app_cw = json.loads(xw.APP_CROSSWALK.read_text(encoding="utf-8"))
    bundle = eab.build_bundle(building_id, store["evidence"], app_cw, eff, vocab) if building_id else None
    res = json.loads(RESOLUTIONS.read_text(encoding="utf-8"))
    res_scope = [r for r in res["records"] if r["building_id"] == building_id]

    def ev_row(e):
        return {"evidence_id": e["evidence_id"], "subject_key": e["quantity_subject"]["subject_key"],
                "subject_id": e["quantity_subject"]["subject_id"], "value": e["value"], "unit": e["unit_normalized"],
                "method_class": e["method_class"], "source_type": e["source_type"], "status": e["status"]}
    return {
        "report_version": "maldenhof_quantity_activation_v1",
        "note": ("Read-only. Menselijke besluiten zijn vastgelegd in de append-only stores; dit rapport beslist niets. "
                 "Geen quantity resolution, geen gemiddelde, geen automatische winnaar."),
        "building_links": per_doc,
        "building_id": building_id,
        "scope_identical_for_documents": len(set(scopes.values())) == 1 and len(scopes) == len(DOCS),
        "bag_pand_ids": building_id.split(":", 1)[1].split("+") if building_id else [],
        "crosswalk_decisions": decisions,
        "mapping_status": {m: eff[m]["status"] for m in MAPPINGS},
        "subjects": {k: subj[k] for k in ("ROOF_FLAT_AREA", "ROOF_COVERING_REPORTED_AREA")},
        "subject_relation": rel,
        "bag3d": None if agg is None else {
            "aggregate": dict(ev_row(agg), formula=agg["calculation"]["formula"], rule_id=agg["calculation"]["rule_id"],
                              rule_version=agg["calculation"]["rule_version"],
                              missing_bag_pand_ids=agg["source_ref"]["missing_bag_pand_ids"],
                              snapshot_ids=agg["source_ref"]["snapshot_ids"]),
            "children": [dict(ev_row(c), bag_pand_id=c["source_ref"]["bag_pand_id"]) for c in children],
        },
        "scope_aggregates_not_published": [n for n in store["scope_aggregates_not_published"] if n["building_id"] == building_id],
        "historical": [dict(ev_row(e), document_id=e["source_ref"]["document_id"],
                            quantity_observation_id=e["source_ref"]["quantity_observation_id"],
                            page=(e["source_ref"].get("provenance") or {}).get("page"),
                            text_fragment=(e["source_ref"].get("provenance") or {}).get("text_fragment"),
                            subject_mapping_ref=e["source_ref"].get("subject_mapping_ref"),
                            source_cluster=e["dependency"].get("source_cluster"),
                            same_object_document_ids=e["dependency"].get("same_object_document_ids"),
                            identical_in_same_object_documents=e["dependency"].get("identical_in_same_object_documents"))
                       for e in hist],
        "historical_independent_source_clusters": len({e["dependency"].get("source_cluster") for e in hist}),
        "comparisons": [{k: c[k] for k in ("document_id", "subject_key", "bag3d_subject_key", "comparison_kind", "subject_relation_id",
                                           "historical_value", "bag3d_value", "absolute_difference", "percentage_difference",
                                           "difference_band", "review_status", "mismatch_reasons", "dependency_note")} for c in comps],
        "app_bundle_preview": None if bundle is None else {
            "bundle_version": bundle["bundle_version"], "building_scope": bundle["building_scope"],
            "entries": [{"app_element_key": e["app_element_key"], "subject_key": e["subject_key"], "role": e.get("role"),
                         "selectable": e.get("selectable"), "value": e["evidence"]["value"], "unit": e["evidence"]["unit"],
                         "method_class": e["evidence"]["method_class"], "source_type": e["evidence"]["source_type"],
                         "components": len(e["evidence"].get("components") or [])} for e in bundle["entries"]],
            "note": "Niet weggeschreven (tenant-scheiding): de VvE exporteert zelf met scripts/export_app_quantity_bundle.py."},
        "quantity_resolution": {
            "records_for_scope": len(res_scope), "records_total": len(res["records"]),
            "status": {"ROOF_FLAT_AREA": "UNRESOLVED (3D BAG-evidence PROPOSED)",
                       "ROOF_COVERING_REPORTED_AREA": "UNRESOLVED (historische context; niet resolveerbaar als dezelfde hoeveelheid als ROOF_FLAT_AREA)"},
            "active_resolution": {k: qe.active_resolution(res, building_id, qe.make_building_subject_id(building_id, k, "m2"))
                                  for k in ("ROOF_FLAT_AREA", "ROOF_COVERING_REPORTED_AREA")} if building_id else {},
        },
    }


def render(r):
    L = ["# Maldenhof Quantity Activation v1 (read-only)", "", r["note"], "", "## Building links (menselijk besluit)", "",
         "| Document | Snapshot | CONFIRMED | REJECTED | Postcodes CONFIRMED | Postcodes REJECTED |", "|---|---|---|---|---|---|"]
    for d, v in r["building_links"].items():
        L.append(f"| {d} | {', '.join(v['snapshot_ids'])} | {len(v['confirmed'])} | {len(v['rejected'])} | "
                 f"{', '.join(sorted({p for x in v['confirmed'] for p in x['postcodes']}))} | "
                 f"{', '.join(sorted({p for x in v['rejected'] for p in x['postcodes']}))} |")
    L += ["", f"Gebouwscope ({len(r['bag_pand_ids'])} panden, gelijk voor DOC-005 en DOC-006: "
              f"{'ja' if r['scope_identical_for_documents'] else 'NEE'}): `{r['building_id']}`", "",
          "## Crosswalk-besluiten", "", "| Besluit | Mapping | Uitkomst | Reviewer | Reden |", "|---|---|---|---|---|"]
    L += [f"| {d['decision_id']} | {d['mapping_id']} | {d['decision']} ({d['status']}) | {d['reviewer']['reviewer_id']} ({d['reviewer']['reviewer_type']}) | "
          f"{d['decision_reason']} |" for d in r["crosswalk_decisions"]]
    L += ["", "Effectieve status:", ""] + [f"- {k}: **{v}**" for k, v in r["mapping_status"].items()]
    rc = r["subjects"]["ROOF_COVERING_REPORTED_AREA"]
    rel = r["subject_relation"]
    L += ["", "## Twee onderwerpen, niet gelijkgesteld", "",
          f"- `ROOF_FLAT_AREA` — {r['subjects']['ROOF_FLAT_AREA']['label_nl']} (3D BAG, geometrisch).",
          f"- `ROOF_COVERING_REPORTED_AREA` — {rc['label_nl']} ({rc['unit']}, {rc['quantity_kind']}, {rc['method_class']}).",
          f"- Relatie `{rel['relation_id']}`: **{rel['relation']}**, zelfde bouwdeel ({rel['same_building_part']}); "
          f"resolveerbaar als dezelfde hoeveelheid: {rel['resolvable_as_same_quantity']}; naast elkaar: {rel['show_side_by_side']}; "
          f"verschil als: {rel['show_difference_as']}; middelen: {rel['average']}; één resolutie: {rel['single_resolution']}; "
          f"automatische winnaar: {rel['auto_select_winner']}.", ""]
    b = r["bag3d"]
    if b:
        a = b["aggregate"]
        L += ["## 3D BAG (ROOF_FLAT_AREA)", "",
              f"**{a['value']} {a['unit']}** — {a['evidence_id']}, {a['method_class']}, {a['rule_id']} v{a['rule_version']}, "
              f"`{a['formula']}`, {len(b['children'])} child evidence, ontbrekende panden: {len(a['missing_bag_pand_ids'])}, status {a['status']}.", "",
              "| BAG-pand | b3_opp_dak_plat (m²) | Evidence | Methode |", "|---|---|---|---|"]
        L += [f"| {c['bag_pand_id']} | {c['value']} | {c['evidence_id']} | {c['method_class']} |" for c in b["children"]]
        L.append("")
    L += ["## Historisch (ROOF_COVERING_REPORTED_AREA, complexniveau)", "",
          "| Evidence | Document | Waarde | Methode | Pagina | Fragment | Broncluster | Zelfde object als |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {h['evidence_id']} | {h['document_id']} | {h['value']} {h['unit']} | {h['method_class']} | {h['page']} | `{h['text_fragment']}` | "
          f"{h['source_cluster']} | {', '.join(h['same_object_document_ids'])} |" for h in r["historical"]]
    L += ["", f"Onafhankelijke historische bronnen (bronclusters): **{r['historical_independent_source_clusters']}** — "
              "DOC-005 en DOC-006 tellen niet als twee waarnemingen.", "",
          "## Bronverschil (andere definitie; geen keuze, geen statistiek)", "",
          "| Document | Historisch | 3D BAG | Verschil | % | Soort | Status |", "|---|---|---|---|---|---|---|"]
    L += [f"| {c['document_id']} | {c['historical_value']} ({c['subject_key']}) | {c['bag3d_value']} ({c['bag3d_subject_key']}) | "
          f"{c['absolute_difference']} | {c['percentage_difference']} | {c['comparison_kind']} | {c['review_status']} |" for c in r["comparisons"]]
    ab = r["app_bundle_preview"]
    if ab:
        L += ["", f"## App-bundel (preview, {ab['bundle_version']})", "", "| App-element | Onderwerp | Rol | Kiesbaar | Waarde | Methode | Componenten |",
              "|---|---|---|---|---|---|---|"]
        L += [f"| {e['app_element_key']} | {e['subject_key']} | {e['role']} | {'ja' if e['selectable'] else 'nee'} | {e['value']} {e['unit']} | "
              f"{e['method_class']} | {e['components']} |" for e in ab["entries"]]
        L += ["", ab["note"]]
    q = r["quantity_resolution"]
    L += ["", "## Quantity resolution", "", f"- Records voor deze scope: {q['records_for_scope']} (totaal {q['records_total']})"]
    L += [f"- {k}: {v}" for k, v in q["status"].items()]
    L.append("")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = build()
    js, md = json.dumps(r, ensure_ascii=False, indent=1) + "\n", render(r)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("maldenhof activation up-to-date" if ok else "maldenhof activation NIET up-to-date")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"building_id_panden": len(r["bag_pand_ids"]), "bag3d": (r["bag3d"] or {}).get("aggregate", {}).get("value"),
                      "historisch": [h["value"] for h in r["historical"]], "mappings": r["mapping_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
