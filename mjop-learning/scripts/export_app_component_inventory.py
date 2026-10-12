"""Exporteer de Building Element Inventory als component-inventarisbundel voor MJOP-App (App Component Inventory Bundle v1).

Leest (read-only, geen netwerk, geen nieuwe besluiten):
  data/component_inventory/component_inventory_v1.json      afgeleide inventaris (presence per component)
  data/component_presence/component_presence_evidence_v1.json   evidence per component (bron, pagina, fragment)
  data/component_presence/component_presence_decision_records.json   menselijke besluiten (CPD-*)
  data/frame_inventory/frame_inventory_v1.json              frame-beleid (bronvolgorde, legacy fallback)
  data/frame_inventory/maldenhof_photo_frame_instances_v1.json   PHOTO_VISIBLE-tellingen (alleen als building_id past)
  vocabularies/building_component_types_v1.json, vocabularies/app_element_requirements_v1.json

Schrijft (deterministisch, zonder tijdstempel van generatie):
  reports/inventory/app_bundles/maldenhof_component_inventory_v1.json
  reports/inventory/app_bundles/doc012_component_inventory_v1.json

Statusmapping (UNKNOWN != ABSENT):
  CONFIRMED_PRESENT (menselijk besluit)     -> PRESENT, presence_basis HUMAN_DECISION
  CONFIRMED_ABSENT  (menselijk besluit)     -> ABSENT,  presence_basis HUMAN_DECISION
  PROPOSED_PRESENT  (bronbewijs, geen besluit) -> PRESENT, presence_basis SOURCE_EVIDENCE_NOT_CONFIRMED
  PROPOSED_ABSENT   (bijv. 3D BAG nulwaarde)   -> UNKNOWN, presence_basis PROPOSED_ABSENT_NOT_DECIDED (nooit stil ABSENT)
  geen bewijs / stilte                      -> UNKNOWN, presence_basis NO_EVIDENCE
Alleen een expliciete ABSENT (menselijk besluit) levert NOT_APPLICABLE op.

Geen scores, geen confidence-percentages, geen hoeveelheden afgeleid, geen prijzen.

    python scripts/export_app_component_inventory.py [--check]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTORY = ROOT / "data" / "component_inventory" / "component_inventory_v1.json"
EVIDENCE = ROOT / "data" / "component_presence" / "component_presence_evidence_v1.json"
DECISIONS = ROOT / "data" / "component_presence" / "component_presence_decision_records.json"
FRAME_INVENTORY = ROOT / "data" / "frame_inventory" / "frame_inventory_v1.json"
PHOTO_INSTANCES = ROOT / "data" / "frame_inventory" / "maldenhof_photo_frame_instances_v1.json"
COMPONENT_TYPES = ROOT / "vocabularies" / "building_component_types_v1.json"
REQUIREMENTS = ROOT / "vocabularies" / "app_element_requirements_v1.json"
OUT_DIR = ROOT / "reports" / "inventory" / "app_bundles"

BUNDLE_VERSION = "mjop_app_component_inventory_bundle_v1"
BUILDER_VERSION = "app_component_inventory_bundle_v1.0.0"
# bundelbestand per set documenten van het gebouwscope
OUTPUT_NAMES = {("DOC-005", "DOC-006"): "maldenhof_component_inventory_v1.json", ("DOC-012",): "doc012_component_inventory_v1.json"}
STATUS_BY_STATE = {
    "CONFIRMED_PRESENT": ("PRESENT", "HUMAN_DECISION"),
    "CONFIRMED_ABSENT": ("ABSENT", "HUMAN_DECISION"),
    "PROPOSED_PRESENT": ("PRESENT", "SOURCE_EVIDENCE_NOT_CONFIRMED"),
    "PROPOSED_ABSENT": ("UNKNOWN", "PROPOSED_ABSENT_NOT_DECIDED"),
    "UNKNOWN_NO_EVIDENCE": ("UNKNOWN", "NO_EVIDENCE"),
}
INVENTORY_RESULTS = {
    "APPLICABLE": "Alle benodigde bouwdelen zijn aanwezig; de post kan voorgesteld worden (PROPOSED).",
    "NOT_APPLICABLE": "Een benodigd bouwdeel is expliciet ABSENT (menselijk besluit); de post vervalt.",
    "NEEDS_CONFIRMATION": "Aanwezigheid van minstens één benodigd bouwdeel is niet vastgesteld (UNKNOWN); de post blijft zichtbaar.",
    "NEEDS_ATTRIBUTE_CONFIRMATION": "Bouwdeel aanwezig, maar het vereiste attribuut (materiaal/afwerking) is niet vastgesteld.",
    "NOT_PRESENCE_DRIVEN": "Aanwezigheid van bouwdelen bepaalt deze post niet (ondersteunende kostenpost).",
    "USER_SELECTED": "Optionele verbetering; alleen via gebruikerskeuze, nooit door aanwezigheid.",
}
SOURCE_PRIORITY_NOTE = ("Alleen binnen EXACT hetzelfde quantity-subject (zelfde concept, zelfde gebouw/scope). Geen automatische vergelijking "
                        "van bijv. FRAME_COUNT met een historische m2.")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def source_summary(ev):
    ref = ev.get("source_ref", {})
    prov = ref.get("provenance") or {}
    det = ev.get("details", {})
    row = {"evidence_id": ev["evidence_id"], "source_type": ev["source_type"], "assertion": ev["assertion"],
           "method_class": ev["method_class"], "evidence_status": ev["status"], "scope_level": ev["scope_level"]}
    if ev["source_type"] == "MJOP":
        row.update(document_id=ref.get("document_id"), page=prov.get("page"), text_fragment=prov.get("text_fragment"),
                   element_description_as_reported=det.get("element_description_as_reported"))
    else:
        row.update(bag_pand_id=ev.get("bag_pand_id"), snapshot_id=ref.get("snapshot_id"), fields=ref.get("fields"))
    if ev.get("absence_basis"):
        row["absence_basis"] = ev["absence_basis"]["statement"]
    return row


def build_components(building, evidence_by_id, decisions_by_id, ctypes):
    comps = []
    by_type = {}
    for lst, items in building["components"].items():
        for c in items:
            by_type[c["component_type"]] = c
    for ct in ctypes:
        c = by_type[ct["component_type"]]
        status, basis = STATUS_BY_STATE[c["state"]]
        evs = [evidence_by_id[e] for e in c["evidence_ids"]]
        materials = sorted({e["details"]["material_as_reported"] for e in evs
                            if e["assertion"] == "PRESENT" and e["details"].get("material_as_reported")})
        dec = decisions_by_id.get(c["human_decision_ref"]) if c["human_decision_ref"] else None
        comps.append({
            "component_type": c["component_type"],
            "label_nl": ct["label_nl"],
            "status": status,
            "presence_basis": basis,
            "user_confirmed": False,
            "decision_ref": c["human_decision_ref"],
            "evidence_refs": list(c["evidence_ids"]),
            "source_summary": [source_summary(e) for e in evs],
            "material_as_reported": materials[0] if len(materials) == 1 else None,
            "materials_as_reported": materials,
            "material_basis": "SOURCE_REPORTED_BUILDING_LEVEL" if materials else None,
            "scope_building_id": building["building_id"],
            "last_reviewed": ({"decision_id": dec["decision_id"], "reviewed_at": dec["reviewed_at"], "reviewer_type": dec["reviewer"]["reviewer_type"],
                               "decision": dec["decision"]} if dec else {"state": "NOT_REVIEWED"}),
            "notes": list(c["notes"]),
        })
    return comps


def requirement_result(req, status_of, comp_by_type):
    mode = req["activation_mode"]
    needed = req["requires"] or req["requires_any"]
    st = [status_of[c] for c in needed]
    if mode == "NOT_PRESENCE_DRIVEN":
        return "NOT_PRESENCE_DRIVEN", "Ondersteunende kostenpost; niet door aanwezigheid bepaald."
    if mode == "USER_SELECTED":
        return "USER_SELECTED", "Optionele verbetering; alleen via gebruikerskeuze."
    if mode == "PRESENCE_DRIVEN_ALL":
        if "ABSENT" in st:
            return "NOT_APPLICABLE", "Benodigd bouwdeel expliciet ABSENT."
        if all(s == "PRESENT" for s in st):
            return "APPLICABLE", "Alle benodigde bouwdelen PRESENT."
        return "NEEDS_CONFIRMATION", "Aanwezigheid van het benodigde bouwdeel is UNKNOWN; niet als afwezig behandeld."
    # PRESENCE_DRIVEN_ANY en PRESENCE_AND_ATTRIBUTE: minstens een van requires_any
    if "PRESENT" not in st:
        if all(s == "ABSENT" for s in st):
            return "NOT_APPLICABLE", "Alle mogelijke bouwdelen expliciet ABSENT."
        return "NEEDS_CONFIRMATION", "Geen bouwdeel PRESENT en minstens één UNKNOWN; niet als afwezig behandeld."
    if mode == "PRESENCE_DRIVEN_ANY":
        return "APPLICABLE", "Minstens één bouwdeel PRESENT."
    # PRESENCE_AND_ATTRIBUTE: materiaal/afwerking uit een bron volstaat niet; er is geen menselijk attribuutbesluit
    present = [c for c in needed if status_of[c] == "PRESENT"]
    return "NEEDS_ATTRIBUTE_CONFIRMATION", ("Bouwdeel PRESENT (" + ", ".join(present) + ") maar materiaal/afwerking is alleen door de bron gemeld "
                                            "(geen vastgestelde afwerking); presence alleen volstaat niet.")


def build_requirements(reqs, comps):
    status_of = {c["component_type"]: c["status"] for c in comps}
    comp_by_type = {c["component_type"]: c for c in comps}
    rows = []
    for r in reqs["requirements"]:
        result, reason = requirement_result(r, status_of, comp_by_type)
        row = {"app_element_id": r["app_element_key"], "app_label": r["app_label"], "classification": r["classification"],
               "activation_mode": r["activation_mode"], "required_components": list(r["requires"]),
               "required_any_components": list(r["requires_any"]), "inventory_result": result, "reason": reason,
               "component_status": {c: status_of[c] for c in (r["requires"] + r["requires_any"] + r.get("physical_context_any", []))}}
        if r["activation_mode"] == "PRESENCE_AND_ATTRIBUTE":
            row["attribute_basis"] = {c: comp_by_type[c]["materials_as_reported"] for c in r["requires_any"]}
        if r.get("legacy_estimate_fallback_id"):
            row["legacy_estimate_fallback_id"] = r["legacy_estimate_fallback_id"]
        rows.append(row)
    return rows


def build_frame_status(building, comps, evidence_by_id, frame_policy, photo_store, reqs):
    frame = next(c for c in comps if c["component_type"] == "EXTERIOR_FRAME")
    hist = []
    for eid in frame["evidence_refs"]:
        h = evidence_by_id[eid]["details"].get("historical_reported_quantity_context")
        if h:
            hist.append({"evidence_id": eid, "quantity_observation_id": h["quantity_observation_id"], "quantity_as_stated": h["quantity_as_stated"],
                         "quantity_value": h["quantity_value"], "unit": h["unit_normalized"], "interpretation": h["interpretation"],
                         "comparability_to_frame_count": "NOT_COMPARABLE", "not_interpreted_as": list(h["not_interpreted_as"])})
    lef = reqs["legacy_estimate_fallbacks"][0]
    photo = None
    totals = {k: {"status": "UNKNOWN", "value": None} for k in ("FRAME_COUNT", "WINDOW_COUNT", "EXTERIOR_DOOR_COUNT")}
    if photo_store and photo_store["building_id"] == building["building_id"]:
        pv = photo_store["photo_visible_counts"]
        photo = {"count_basis": pv["count_basis"], "photo": pv["photo"], "is_building_total": pv["is_building_total"],
                 "PHOTO_VISIBLE_FRAME_COUNT": pv["PHOTO_VISIBLE_FRAME_COUNT"], "PHOTO_VISIBLE_WINDOW_COUNT": pv["PHOTO_VISIBLE_WINDOW_COUNT"],
                 "PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT": pv["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"],
                 "provenance": "USER_ASSISTED_PHOTO", "store": "data/frame_inventory/maldenhof_photo_frame_instances_v1.json"}
        for k in totals:
            totals[k] = dict(photo_store["building_totals"][k])
    return {
        "component_type": "EXTERIOR_FRAME",
        "presence": frame["status"], "presence_decision_ref": frame["decision_ref"],
        "material_as_reported": frame["material_as_reported"], "material_basis": frame["material_basis"],
        "photo_visible_evidence": photo,
        "building_totals": totals,
        "building_total_note": "Gebouwtotalen zijn UNKNOWN; geen extrapolatie, geen vermenigvuldiging over panden, geen repeat multiplier.",
        "historical_reported_quantity_context": hist,
        "repeat_groups": "NOT_ACTIVE", "quantity_resolution": "NOT_WRITTEN",
        "legacy_estimate_fallback": {"fallback_id": lef["fallback_id"], "classification": lef["classification"], "method_class": lef["method_class"],
                                     "ui_label_nl": "Schatting op basis van aantal appartementen", "factors": lef["factors"], "minima": lef["minima"],
                                     "types": lef["types"], "formula": lef["formula"],
                                     "forbidden_labels": ["gemeten", "bevestigd", "uit foto bepaald"],
                                     "behaviour": "App-gedrag ongewijzigd; blijft beschikbaar als gelabelde schatting."},
        "source_priority": list(frame_policy["future_source_priority"]), "source_priority_scope": SOURCE_PRIORITY_NOTE,
    }


def build_bundle(building, ctx):
    comps = build_components(building, ctx["evidence"], ctx["decisions"], ctx["ctypes"])
    reviewed = sorted(c["last_reviewed"]["reviewed_at"] for c in comps if "reviewed_at" in c["last_reviewed"])
    counts = {s: sum(1 for c in comps if c["status"] == s) for s in ("PRESENT", "ABSENT", "UNKNOWN")}
    reqrows = build_requirements(ctx["reqs"], comps)
    return {
        "bundle_version": BUNDLE_VERSION,
        "builder_version": BUILDER_VERSION,
        "note": ("Component-inventarisbundel voor MJOP-App. PRESENT/ABSENT/UNKNOWN voor fysieke bouwdelen; UNKNOWN is niet ABSENT. "
                 "Bevat geen scores, geen confidence-percentages, geen hoeveelheden-afleiding en geen prijzen. Bundel hoort bij één VvE (tenant-scheiding)."),
        "building": {"building_id": building["building_id"], "document_ids": building["document_ids"], "bag_pand_ids": building["bag_pand_ids"],
                     "pand_count": len(building["bag_pand_ids"])},
        "inventory_last_reviewed_at": reviewed[-1] if reviewed else None,
        "input_hashes": {k: sha_file(p) for k, p in (("component_inventory", INVENTORY), ("component_presence_evidence", EVIDENCE),
                                                      ("component_presence_decisions", DECISIONS), ("app_element_requirements", REQUIREMENTS),
                                                      ("building_component_types", COMPONENT_TYPES), ("frame_inventory", FRAME_INVENTORY))},
        "status_vocabulary": {"PRESENT": "aanwezig", "ABSENT": "niet aanwezig (alleen expliciet)", "UNKNOWN": "nog te bevestigen"},
        "inventory_result_vocabulary": INVENTORY_RESULTS,
        "summary": {"component_status_counts": counts,
                    "inventory_result_counts": {k: sum(1 for r in reqrows if r["inventory_result"] == k) for k in INVENTORY_RESULTS}},
        "components": comps,
        "maintenance_requirements": reqrows,
        "frame_status": build_frame_status(building, comps, ctx["evidence"], ctx["frame_policy"], ctx["photo_store"], ctx["reqs"]),
        "policy": {
            "unknown_is_not_absent": True,
            "only_explicit_absent_yields_not_applicable": True,
            "no_silent_removal_of_maintenance_items": True,
            "user_confirmation": "Gebruikerskeuze JA/NEE/ONBEKEND wordt in de app als USER_CONFIRMED_MANUAL vastgelegd en overschrijft deze bundel binnen hetzelfde component; de bundel zelf wordt niet gewijzigd.",
            "prices": "NOT_CHANGED", "kengetallen": "NOT_CHANGED", "quantity_resolutions": "NOT_WRITTEN",
        },
    }


def context():
    inv = load(INVENTORY)
    return inv, {
        "evidence": {e["evidence_id"]: e for e in load(EVIDENCE)["evidence"]},
        "decisions": {r["decision_id"]: r for r in load(DECISIONS)["records"] if r["status"] == "ACTIVE"},
        "ctypes": load(COMPONENT_TYPES)["component_types"],
        "reqs": load(REQUIREMENTS),
        "frame_policy": load(FRAME_INVENTORY)["policy"],
        "photo_store": load(PHOTO_INSTANCES) if PHOTO_INSTANCES.exists() else None,
    }


def render_all():
    inv, ctx = context()
    outs = {}
    for b in inv["buildings"]:
        name = OUTPUT_NAMES.get(tuple(sorted(b["document_ids"])))
        if name:
            outs[OUT_DIR / name] = dump(build_bundle(b, ctx))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    outs = render_all()
    if args.check:
        bad = [str(p) for p, t in outs.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        if bad:
            print("OUT OF DATE:", *bad, sep="\n  ")
            return 1
        print("OK")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p, t in outs.items():
        p.write_text(t, encoding="utf-8")
    print("written", *[str(p.relative_to(ROOT)) for p in outs])
    return 0


if __name__ == "__main__":
    sys.exit(main())
