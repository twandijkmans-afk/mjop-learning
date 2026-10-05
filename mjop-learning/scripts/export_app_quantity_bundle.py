"""Exporteer quantity evidence voor één gebouw als bundel om in MJOP-App te importeren.

Tenant-/bronscheiding (CLAUDE.md): de bundel bevat historische hoeveelheden van één VvE en is bedoeld om
door de eigenaar/beheerder van die VvE zelf in zijn eigen plan te importeren. Hij wordt NIET in de publieke
app-code of een gedeelde bundel opgenomen.

Alleen evidence voor onderwerpen met een door een mens geverifieerde app-crosswalk (XW-*, status VERIFIED)
komt in de bundel; zonder zo'n mapping weigert het script. De bundel bevat alle evidence (3D BAG én
historisch) naast elkaar: er wordt niets gekozen of gemiddeld.

Bundelversies (backwards-compatible):
  v1  één BAG-pand (building_id 'BAG:<id>'): ongewijzigd formaat.
  v2  gebouwscope met meerdere panden ('BAG:<id1>+<id2>+…'): building_scope met alle pand-ID's; de 3D BAG-
      evidence is het scope-aggregaat (GEOMETRY_DERIVED) met per pand de onderliggende waarde in 'components';
      historische evidence staat op complexniveau (scope_level COMPLEX). Pandwaarden zijn géén losse kiesbare
      bronnen en worden niet over panden verdeeld.

    python scripts/export_app_quantity_bundle.py --building "BAG:0363100012345678" --out exports/bundle.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_building_quantity_evidence as bqe  # noqa: E402
import crosswalk as xw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_VERSION = "mjop_app_quantity_bundle_v1"
BUNDLE_VERSION_MULTI = "mjop_app_quantity_bundle_v2"


class BundleError(RuntimeError):
    pass


def _app_ref(ev):
    sr = ev["source_ref"]
    prov = sr.get("provenance") or {}
    return {
        "document_id": sr.get("document_id"),
        "quantity_observation_id": sr.get("quantity_observation_id"),
        "page": prov.get("page"),
        "text_fragment": prov.get("text_fragment"),
        "quantity_as_stated": sr.get("quantity_as_stated"),
        "bag_pand_id": sr.get("bag_pand_id"),
        "fields": sr.get("fields"),
        "raw_inputs": sr.get("raw_inputs"),
        "fetched_at": sr.get("fetched_at"),
        "rule_id": sr.get("rule_id"),
        "rule_version": sr.get("rule_version"),
    }


def _components(ev, by_id):
    out = []
    for cid in (ev.get("calculation") or {}).get("input_evidence_ids") or []:
        c = by_id.get(cid)
        if c is None:
            raise BundleError(f"child evidence {cid} van {ev['evidence_id']} ontbreekt")
        sr = c["source_ref"]
        out.append({"bag_pand_id": sr.get("bag_pand_id"), "evidence_id": c["evidence_id"], "value": c["value"],
                    "unit": c["unit_normalized"], "method_class": c["method_class"], "rule_id": sr.get("rule_id"),
                    "fields": sr.get("fields"), "raw_inputs": sr.get("raw_inputs"), "snapshot_id": sr.get("snapshot_id"),
                    "fetched_at": sr.get("fetched_at")})
    return out


def build_bundle(building_id, evidence, app_crosswalk, effective):
    verified = [m for m in app_crosswalk["mappings"]
                if effective.get(m["mapping_id"], {}).get("status") == "VERIFIED" and m.get("quantity_subject")]
    if not verified:
        raise BundleError("geen door een mens geverifieerde app-crosswalk-mapping met een hoeveelheidsonderwerp")
    pand_ids = building_id.split(":", 1)[1].split("+")
    multi = len(pand_ids) > 1
    by_id = {e["evidence_id"]: e for e in evidence}
    entries = []
    for m in sorted(verified, key=lambda x: x["mapping_id"]):
        for ev in evidence:
            if ev["quantity_subject"].get("subject_key") != m["quantity_subject"]:
                continue
            if ev["unit_normalized"] != m["unit"]:
                continue
            if not (ev["building_id"] == building_id or ev["building_id"] == "BAG:" + building_id.split(":", 1)[1]):
                continue
            e_out = {
                "app_element_key": m["app_element_key"], "crosswalk_mapping_id": m["mapping_id"],
                "crosswalk_decision_id": effective[m["mapping_id"]]["decision_id"],
                "subject_key": m["quantity_subject"],
                "evidence": {
                    "evidence_id": ev["evidence_id"], "source_type": ev["source_type"], "method_class": ev["method_class"],
                    "value": ev["value"], "unit": ev["unit_normalized"], "status": ev["status"],
                    "review_reasons": ev["review_reasons"], "scope_caveats": ev["scope_caveats"],
                    "source_cluster": (ev.get("dependency") or {}).get("source_cluster"),
                    "same_object_document_ids": (ev.get("dependency") or {}).get("same_object_document_ids", []),
                    "source_ref": _app_ref(ev),
                },
            }
            if multi:
                is_agg = bool(ev["source_ref"].get("aggregation"))
                e_out["evidence"]["scope_level"] = "COMPLEX"
                e_out["evidence"]["aggregation"] = ev["source_ref"].get("aggregation") if is_agg else None
                e_out["evidence"]["formula"] = (ev.get("calculation") or {}).get("formula") if is_agg else None
                e_out["evidence"]["components"] = _components(ev, by_id) if is_agg else []
            entries.append(e_out)
    if not entries:
        raise BundleError(f"geen evidence voor {building_id} bij de geverifieerde mappings")
    if not multi:
        return {"bundle_version": BUNDLE_VERSION, "building_id": building_id, "bag_pand_ids": pand_ids,
                "tenant_note": "Bevat historische hoeveelheden van één VvE; alleen importeren in het plan van die VvE.",
                "entries": entries}
    return {"bundle_version": BUNDLE_VERSION_MULTI, "building_id": building_id, "bag_pand_ids": pand_ids,
            "building_scope": {"building_id": building_id, "kind": "MULTI_PAND_SCOPE", "bag_pand_ids": pand_ids,
                               "pand_count": len(pand_ids)},
            "tenant_note": "Bevat historische hoeveelheden van één VvE (meerdere panden); alleen importeren in een plan van die VvE.",
            "entries": entries}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--building", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    store = json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))
    app_cw = json.loads(xw.APP_CROSSWALK.read_text(encoding="utf-8"))
    try:
        bundle = build_bundle(args.building, store["evidence"], app_cw, xw.effective())
    except BundleError as e:
        print(f"FOUT: {e}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(bundle['entries'])} evidence-regels -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
