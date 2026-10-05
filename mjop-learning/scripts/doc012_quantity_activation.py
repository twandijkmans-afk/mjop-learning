"""DOC-012 Quantity Activation v1 — read-only rapport over de bevestigde DOC-012-scope en de echte bundel v3.

Leest de append-only stores, de evidence, de vergelijkingen en de bundel; schrijft alleen:
  reports/quantity/doc012_quantity_activation_v1.json / .md

Het scopebesluit (H1 gekozen, H2 niet) staat hieronder als vastlegging van het menselijke besluit. H2 kwam uit de
niet-canonieke objectnaam-hypothese; daarvoor worden bewust GEEN REJECT-building-links geschreven (die panden zijn
geen canonieke kandidaat van DOC-012).

    python scripts/doc012_quantity_activation.py [--check]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import validate_app_quantity_bundle as vab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOC = "DOC-012"
BUNDLE = ROOT / "reports" / "quantity" / "app_bundles" / "doc012_meppelweg_v3.json"
MALDENHOF_BUNDLE = ROOT / "reports" / "quantity" / "app_bundles" / "maldenhof_DOC-005_DOC-006_v3.json"
OUT_JSON = ROOT / "reports" / "quantity" / "doc012_quantity_activation_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "doc012_quantity_activation_v1.md"
MAPPING = "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012"

SCOPE_DECISION = {
    "document_id": DOC, "decided_by": "user-approved", "decided_on": "2026-10-05",
    "chosen": "H1",
    "interpretation": ("H1 = het volledige BAG-pand van het canonieke documentadres Meppelweg 819 (pand 0518100000354752: "
                       "Meppelweg 803-883 oneven, 42 verblijfsobjecten), niet alleen de woning 819."),
    "H2_FULL_RANGE": "NOT_SELECTED",
    "H2_reason": ("De objectnaamrange omvat ook de even straatzijde met andere postcodes, twee gesloopte panden, nieuwbouw "
                  "uit 2013 en niet-woonfuncties. Dit past niet bij de documentkenmerken. Het pand van het canonieke adres "
                  "verklaart daarentegen zelfstandig de 42 verblijfsobjecten."),
    "H2_records": "geen building-link-records: de H2-panden zijn geen canonieke kandidaat (alleen read-only hypothese-opname)",
    "facade": "2110 metselwerk 1326.46 m2 blijft NEEDS_SEMANTIC_REVIEW t.o.v. OUTER_WALL_GROSS_AREA; geen relatie, mapping of bundelregel",
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    links = [r for r in bl.load_store()["records"] if r["document_id"] == DOC]
    confirmed = sorted(r["bag_pand_id"] for r in links if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED")
    building_id = bqe.building_id_for(confirmed)
    decisions = [r for r in xw.load_store()["records"] if r["mapping_id"] == MAPPING]
    store = json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))
    ev = [e for e in store["evidence"] if e["building_id"] == building_id]
    comps = [c for c in json.loads(bqe.OUT_JSON.read_text(encoding="utf-8"))["comparisons"] if c["document_id"] == DOC]
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    res = json.loads(vab.RESOLUTIONS.read_text(encoding="utf-8"))

    def row(e):
        return {"evidence_id": e["evidence_id"], "subject_key": e["quantity_subject"]["subject_key"], "value": e["value"],
                "unit": e["unit_normalized"], "method_class": e["method_class"], "source_type": e["source_type"], "status": e["status"],
                "quantity_observation_id": e["source_ref"].get("quantity_observation_id"),
                "subject_mapping_ref": e["source_ref"].get("subject_mapping_ref"), "snapshot_id": e["source_ref"].get("snapshot_id")}
    return {
        "report_version": "doc012_quantity_activation_v1",
        "note": "Read-only. Menselijke besluiten staan in de append-only stores; geen quantity resolution, geen gemiddelde, geen winnaar.",
        "scope_decision": SCOPE_DECISION,
        "building_links": [{k: r[k] for k in ("link_id", "bag_pand_id", "link_status", "status", "decision_reason")} |
                           {"snapshot_id": r["evidence"]["snapshot_id"], "reviewer": r["reviewer"]} for r in links],
        "building_id": building_id, "bag_pand_ids": confirmed,
        "mapping_decisions": [{k: r[k] for k in ("decision_id", "mapping_id", "decision", "status", "decision_reason", "reviewer")} for r in decisions],
        "mapping_status": xw.effective()[MAPPING]["status"],
        "evidence": [row(e) for e in sorted(ev, key=lambda e: (e["source_type"], e["quantity_subject"]["subject_key"]))],
        "comparisons": [{k: c[k] for k in ("subject_key", "bag3d_subject_key", "comparison_kind", "historical_value", "bag3d_value",
                                           "absolute_difference", "percentage_difference", "review_status")} for c in comps],
        "bundle": {"path": str(BUNDLE.relative_to(ROOT)), "sha256": sha(BUNDLE), "bundle_version": bundle["bundle_version"],
                   "building_scope": bundle["building_scope"],
                   "entries": [{"app_element_key": e["app_element_key"], "subject_key": e["subject_key"], "role": e.get("role"),
                                "selectable": e.get("selectable"), "value": e["evidence"]["value"], "unit": e["evidence"]["unit"],
                                "evidence_id": e["evidence"]["evidence_id"]} for e in bundle["entries"]],
                   "validator_errors": vab.validate(bundle, expect_panden=len(confirmed))},
        "quantity_resolution": {"records_for_scope": sum(1 for r in res["records"] if r["building_id"] == building_id),
                                "records_total": len(res["records"])},
        "maldenhof_bundle_sha256": sha(MALDENHOF_BUNDLE),
    }


def render(r):
    sd = r["scope_decision"]
    L = ["# DOC-012 Quantity Activation v1 (read-only)", "", r["note"], "", "## Scopebesluit", "",
         f"- Gekozen: **{sd['chosen']}** — {sd['interpretation']}",
         f"- H2_FULL_RANGE: **{sd['H2_FULL_RANGE']}** — {sd['H2_reason']}", f"- {sd['H2_records']}.", f"- Gevel: {sd['facade']}.", "",
         "## Building link", "", "| Link | Pand | Status | Snapshot | Reviewer |", "|---|---|---|---|---|"]
    L += [f"| {l['link_id']} | {l['bag_pand_id']} | {l['link_status']} ({l['status']}) | {l['snapshot_id']} | {l['reviewer']['reviewer_id']} "
          f"({l['reviewer']['reviewer_type']}) |" for l in r["building_links"]]
    L += ["", f"building_id: `{r['building_id']}`", "", "## Mapping", ""]
    L += [f"- {d['decision_id']} {d['mapping_id']}: {d['decision']} ({d['status']}) — {d['decision_reason']}" for d in r["mapping_decisions"]]
    L += ["", "## Evidence (PROPOSED)", "", "| Evidence | Onderwerp | Waarde | Methode | Bron |", "|---|---|---|---|---|"]
    L += [f"| {e['evidence_id']} | {e['subject_key']} | {e['value']} {e['unit']} | {e['method_class']} | "
          f"{e['quantity_observation_id'] or e['snapshot_id']} |" for e in r["evidence"]]
    L += ["", "## Bronverschil (andere definitie; geen keuze)", ""]
    L += [f"- {c['subject_key']} {c['historical_value']} vs {c['bag3d_subject_key']} {c['bag3d_value']}: {c['absolute_difference']} "
          f"({c['percentage_difference']}%) — {c['comparison_kind']}, {c['review_status']}" for c in r["comparisons"]]
    b = r["bundle"]
    L += ["", f"## Bundel `{b['path']}`", "", f"{b['bundle_version']}, sha256 `{b['sha256']}`, scope {b['building_scope']['kind']} "
          f"({b['building_scope']['pand_count']} pand). Validator: {'GELDIG' if not b['validator_errors'] else '; '.join(b['validator_errors'])}.", "",
          "| App-element | Onderwerp | Rol | Kiesbaar | Waarde |", "|---|---|---|---|---|"]
    L += [f"| {e['app_element_key']} | {e['subject_key']} | {e['role']} | {'ja' if e['selectable'] else 'nee'} | {e['value']} {e['unit']} |"
          for e in b["entries"]]
    q = r["quantity_resolution"]
    L += ["", f"Quantity resolution: {q['records_for_scope']} voor deze scope (totaal {q['records_total']}). "
              f"Maldenhof-bundel sha256 `{r['maldenhof_bundle_sha256']}`.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = build()
    js, md = json.dumps(r, ensure_ascii=False, indent=1) + "\n", render(r)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("doc012 activation up-to-date" if ok else "doc012 activation NIET up-to-date")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"building_id": r["building_id"], "bundle_sha256": r["bundle"]["sha256"], "validator": r["bundle"]["validator_errors"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
