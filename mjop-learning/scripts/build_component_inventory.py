"""Building Element Inventory builder v1 — deterministisch en afgeleid (nooit met de hand aanpassen).

Leest (read-only):
  data/building_links/building_link_records.json        ACTIVE + CONFIRMED links (menselijk) -> gebouwscopes
  data/bag_snapshots/*.json                             canonieke 3D BAG-antwoorden per pand
  data/quantity_observations/quantity_observations_v1.json   expliciete historische MJOP-elementregels
  data/quantity_evidence/building_quantity_evidence_v1.json  alleen voor verwijzingen (quantity_evidence_id)
  data/component_presence/component_presence_decision_records.json  menselijke besluiten (append-only)
  vocabularies/building_component_types_v1.json, component_presence_rules_v1.json, quantity_subjects_v1.json

Schrijft (afgeleid):
  data/component_presence/component_presence_evidence_v1.json
  data/component_inventory/component_inventory_v1.json

Regels:
- Geen netwerkcalls; geen besluiten schrijven; geen hoeveelheden afleiden of wijzigen.
- Presence-evidence per bevestigd pand (3D BAG) en per gebouwscope (historisch MJOP). Een scope-brede MJOP-uitspraak
  wordt nooit aan één pand toegeschreven.
- Een historische hoeveelheid bij een expliciete bronregel blijft HISTORICAL_REPORTED_QUANTITY_CONTEXT; ze wordt nooit als
  geometrie-/presence-hoeveelheid gebruikt (ook niet als raamopening, kozijnoppervlak, schilderoppervlak of aantal).
- Stilte is nooit ABSENT; ontbrekend bronveld is UNKNOWN; zonder bewijs blijft een component 'unknown'.
- Zonder menselijk besluit is niets 'confirmed' of 'absent': de uitvoer is dan hoofdzakelijk PROPOSED / UNKNOWN.

    python scripts/build_component_inventory.py [--check]
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag_snapshots as bs  # noqa: E402
import building_links as bl  # noqa: E402
import component_presence as cp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QO_PATH = ROOT / "data" / "quantity_observations" / "quantity_observations_v1.json"
QE_PATH = ROOT / "data" / "quantity_evidence" / "building_quantity_evidence_v1.json"
SUBJECTS_PATH = ROOT / "vocabularies" / "quantity_subjects_v1.json"
OUT_EVIDENCE = ROOT / "data" / "component_presence" / "component_presence_evidence_v1.json"
OUT_INVENTORY = ROOT / "data" / "component_inventory" / "component_inventory_v1.json"
BUILDER_VERSION = "component_inventory_v1.0.0"
LIST_KEYS = ("confirmed", "proposed", "proposed_absent", "absent", "unknown", "review_required")


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def building_id_for(pand_ids):
    ids = sorted({str(p) for p in pand_ids})
    if not ids:
        raise ValueError("een gebouwscope heeft minstens één bevestigd pand nodig")
    return "BAG:" + "+".join(ids)


def gather_scopes(links_store):
    """building_id -> {pand_ids, document_ids, link_ids, snapshot_by_pand} uit ACTIVE + CONFIRMED links."""
    active = [r for r in links_store["records"] if r["status"] == "ACTIVE" and r["link_status"] == "CONFIRMED"]
    by_doc = defaultdict(list)
    for r in active:
        by_doc[r["document_id"]].append(r)
    scopes = {}
    for doc, recs in sorted(by_doc.items()):
        bid = building_id_for([r["bag_pand_id"] for r in recs])
        sc = scopes.setdefault(bid, {"pand_ids": sorted({r["bag_pand_id"] for r in recs}), "document_ids": set(),
                                     "link_ids": set(), "snapshot_by_pand": {}})
        sc["document_ids"].add(doc)
        sc["link_ids"] |= {r["link_id"] for r in recs}
        for r in sorted(recs, key=lambda x: x["link_id"]):
            sc["snapshot_by_pand"].setdefault(r["bag_pand_id"], r["evidence"]["snapshot_id"])
    return scopes


def bag3d_presence_evidence(scope_id, scope, snap_by_id, presence_rules, quantity_rules, qe_index, notes):
    out = []
    for pand_id in scope["pand_ids"]:
        snap = snap_by_id.get(scope["snapshot_by_pand"][pand_id])
        pand = next((p for p in (snap or {}).get("panden", []) if p["bag_pand_id"] == pand_id), None)
        if snap is None or pand is None:
            notes.append({"building_id": scope_id, "bag_pand_id": pand_id, "note": "SNAPSHOT_OF_PAND_MISSING"})
            continue
        tb = pand.get("threedbag") or {}
        link_ids = sorted(scope["link_ids"])
        for pr in presence_rules:
            qrule = quantity_rules[pr["quantity_subject_rule_id"]]
            assertion, method, absence_basis, res = cp.bag3d_presence(pr, qrule, tb.get("attributes"))
            ref = {"bag_pand_id": pand_id, "snapshot_id": snap["snapshot_id"], "fields": qrule["fields"],
                   "raw_inputs": res["raw_inputs"], "rule_id": pr["rule_id"], "rule_version": pr["rule_version"],
                   "quantity_rule_id": qrule["rule_id"], "url": tb.get("url"), "fetched_at": tb.get("fetched_at"),
                   "response_sha256": tb.get("response_sha256"), "live_api_status": snap.get("live_api_status"),
                   "building_link_ids": link_ids,
                   "quantity_evidence_id": qe_index.get(("BAG:" + pand_id, pr["quantity_subject_key"]))}
            details = {"rule_status": res["status"], "missing_fields": res["missing_fields"]} if assertion == "UNKNOWN" else {}
            out.append(cp.make_evidence(
                building_id=scope_id, scope_level="PAND", bag_pand_id=pand_id, component_type=pr["component_type"],
                assertion=assertion, source_type="3D_BAG", method_class=method, source_ref=ref, details=details,
                absence_basis=absence_basis, scope_caveats=[pr["caveat"]],
                review_reasons=["GEOMETRY_ABSENCE_NEEDS_HUMAN_REVIEW"] if assertion == "ABSENT" else [],
                status="REVIEW_REQUIRED" if assertion == "ABSENT" else "PROPOSED",
                created_by=BUILDER_VERSION, input_hashes={"snapshot_id": snap["snapshot_id"]}))
    return out


def historical_presence_evidence(scope_id, scope, observations_by_doc, hist_rules, comp_index):
    out = []
    for doc in sorted(scope["document_ids"]):
        for o in observations_by_doc.get(doc, []):
            el = o["element"]
            for rule in cp.matching_rules(hist_rules, el):
                material = el.get("material_original") or rule.get("material_as_reported_from_description")
                comp = comp_index[rule["component_type"]]
                inference = rule.get("inference", "NONE")
                reasons = list(o.get("review_reasons") or []) + ([] if inference == "NONE" else ["INFERENCE_" + inference])
                status = "REVIEW_REQUIRED" if (o.get("requires_human_review") or inference != "NONE") else "PROPOSED"
                details = {
                    "element_code_internal": el["element_code_internal"],
                    "element_description_as_reported": el["element_description_original"],
                    "location_as_reported": el.get("location_original"),
                    "material_as_reported": material,
                    "material_normalized": el.get("material_normalized"),
                    "presence_rule_id": rule["rule_id"],
                    "presence_rule_inference": inference,
                    "historical_reported_quantity_context": {
                        "quantity_observation_id": o["quantity_observation_id"],
                        "quantity_as_stated": o["quantity_as_stated"],
                        "quantity_value": o["quantity_value"],
                        "unit_normalized": o["unit_normalized"],
                        "interpretation": "HISTORICAL_REPORTED_QUANTITY_CONTEXT",
                        "not_interpreted_as": cp.DEFAULT_NOT_INTERPRETED_AS + list(comp.get("quantity_not_implied", [])),
                    },
                }
                ref = {"document_id": doc, "quantity_observation_id": o["quantity_observation_id"], "provenance": o["provenance"],
                       "source_file_sha256": o["source_file"]["sha256"], "rule_id": rule["rule_id"]}
                out.append(cp.make_evidence(
                    building_id=scope_id, scope_level="BUILDING_SCOPE", bag_pand_id=None, component_type=rule["component_type"],
                    assertion="PRESENT", source_type="MJOP",
                    method_class="SOURCE_EXPLICIT_ELEMENT" if inference == "NONE" else "SOURCE_EXPLICIT_ELEMENT_WITH_INFERENCE",
                    source_ref=ref, details=details,
                    scope_caveats=[
                        "Expliciete bronregel van een historisch MJOP: bewijs dat het bouwdeel in dat document staat, geen actuele inspectie.",
                        "De gerapporteerde hoeveelheid is context en geen gemeten of geometrische hoeveelheid van dit bouwdeel."],
                    review_reasons=reasons, status=status,
                    dependency={"source_cluster": o.get("source_cluster"),
                                "same_object_document_ids": (o.get("dependency") or {}).get("same_object_document_ids", [])},
                    created_by=BUILDER_VERSION, input_hashes={"quantity_observation_id": o["quantity_observation_id"]}))
    return out


# --------------------------------------------------------------------------
# Inventaris
# --------------------------------------------------------------------------

def _summaries(evs):
    s = {a: {"pand_ids": [], "scope_sources": [], "evidence_ids": []} for a in cp.ASSERTIONS}
    for e in sorted(evs, key=lambda x: x["evidence_id"]):
        d = s[e["assertion"]]
        d["evidence_ids"].append(e["evidence_id"])
        if e["scope_level"] == "PAND":
            d["pand_ids"].append(e["bag_pand_id"])
        else:
            d["scope_sources"].append({"document_id": e["source_ref"].get("document_id"), "evidence_id": e["evidence_id"],
                                       "source_cluster": (e.get("dependency") or {}).get("source_cluster")})
    for a in s:
        s[a]["pand_ids"] = sorted(set(s[a]["pand_ids"]))
    return s


def component_entry(component_type, evs, decision, pand_ids):
    summ = _summaries(evs)
    current_ids = sorted(e["evidence_id"] for e in evs)
    entry = {"component_type": component_type, "evidence_ids": current_ids, "by_assertion": summ,
             "pand_coverage": {"scope_pand_count": len(pand_ids), "present": len(summ["PRESENT"]["pand_ids"]),
                               "absent": len(summ["ABSENT"]["pand_ids"]), "unknown": len(summ["UNKNOWN"]["pand_ids"])},
             "human_decision_ref": None, "notes": []}
    if decision is not None:
        entry["human_decision_ref"] = decision["decision_id"]
        if set(current_ids) - set(decision["considered_evidence_ids"]):
            entry.update(state="DECISION_REVIEW_REQUIRED", list="review_required")
            entry["notes"].append("Er is evidence bijgekomen sinds het menselijk besluit; het besluit moet opnieuw worden bekeken.")
            return entry
        state = {"PRESENT": ("CONFIRMED_PRESENT", "confirmed"), "ABSENT": ("CONFIRMED_ABSENT", "absent"),
                 "UNKNOWN": ("HUMAN_UNKNOWN", "unknown")}[decision["decision"]]
        entry.update(state=state[0], list=state[1])
        return entry
    asserted = {a for a in ("PRESENT", "ABSENT") if summ[a]["evidence_ids"]}
    if asserted == {"PRESENT", "ABSENT"}:
        entry.update(state="MIXED_EVIDENCE", list="review_required")
        entry["notes"].append("Evidence spreekt zichzelf tegen (PRESENT en ABSENT, tussen bronnen of tussen panden); geen automatische winnaar, geen middeling.")
    elif asserted == {"PRESENT"}:
        entry.update(state="PROPOSED_PRESENT", list="proposed")
        if summ["UNKNOWN"]["pand_ids"]:
            entry["notes"].append("Voor sommige panden kon de bron het niet zeggen (UNKNOWN).")
    elif asserted == {"ABSENT"}:
        entry.update(state="PROPOSED_ABSENT", list="proposed_absent")
    elif summ["UNKNOWN"]["evidence_ids"]:
        entry.update(state="UNKNOWN_FIELD_MISSING", list="unknown")
    else:
        entry.update(state="UNKNOWN_NO_EVIDENCE", list="unknown")
        entry["notes"].append("Geen enkel bewijs; stilte telt niet als afwezigheid.")
    return entry


def build_inventory(scopes, evidence, comp_index, decisions_store):
    active = cp.active_decisions(decisions_store)
    by_bc = defaultdict(list)
    for e in evidence:
        by_bc[(e["building_id"], e["component_type"])].append(e)
    buildings = []
    for scope_id, sc in sorted(scopes.items()):
        lists = {k: [] for k in LIST_KEYS}
        for ct in sorted(comp_index):
            entry = component_entry(ct, by_bc.get((scope_id, ct), []), active.get((scope_id, None, ct)), sc["pand_ids"])
            pand_level = sorted(k[1] for k in active if k[0] == scope_id and k[2] == ct and k[1] is not None)
            if pand_level:
                entry["pand_level_decision_pand_ids"] = pand_level
            lists[entry.pop("list")].append(entry)
        buildings.append({"building_id": scope_id, "bag_pand_ids": sc["pand_ids"], "document_ids": sorted(sc["document_ids"]),
                          "building_link_ids": sorted(sc["link_ids"]), "components": lists,
                          "counts": {k: len(v) for k, v in lists.items()}})
    return buildings


def build(links_store=None, snapshots=None, quantity_observations=None, qe_store=None, subjects_vocab=None,
          components_vocab=None, rules_vocab=None, decisions_store=None):
    links_store = links_store if links_store is not None else bl.load_store()
    snapshots = snapshots if snapshots is not None else bs.load_snapshots()
    qos = quantity_observations if quantity_observations is not None else cp.load_json(QO_PATH)["observations"]
    qe_store = qe_store if qe_store is not None else (cp.load_json(QE_PATH) if QE_PATH.exists() else {"evidence": []})
    subjects_vocab = subjects_vocab if subjects_vocab is not None else cp.load_json(SUBJECTS_PATH)
    components_vocab = components_vocab if components_vocab is not None else cp.load_json(cp.COMPONENT_TYPES)
    rules_vocab = rules_vocab if rules_vocab is not None else cp.load_json(cp.PRESENCE_RULES)
    decisions_store = decisions_store if decisions_store is not None else cp.load_store()

    comp_index = cp.component_type_index(components_vocab)
    quantity_rules = {r["rule_id"]: r for r in subjects_vocab["bag3d_rules"] if r["status"] == "ACTIVE"}
    presence_rules = [r for r in rules_vocab["bag3d_presence_rules"] if r["status"] == "ACTIVE"]
    hist_rules = [r for r in rules_vocab["historical_mjop_presence_rules"] if r["status"] == "ACTIVE"]
    for r in presence_rules + hist_rules:
        if r["component_type"] not in comp_index:
            raise cp.PresenceError(f"{r['rule_id']}: onbekend component_type {r['component_type']}")
    qe_index = {(e["building_id"], e["quantity_subject"]["subject_key"]): e["evidence_id"] for e in qe_store["evidence"]}
    snap_by_id = {s["snapshot_id"]: s for s in snapshots}
    obs_by_doc = defaultdict(list)
    for o in qos:
        obs_by_doc[o["document_id"]].append(o)

    scopes = gather_scopes(links_store)
    evidence, notes = [], []
    for scope_id, sc in sorted(scopes.items()):
        evidence += bag3d_presence_evidence(scope_id, sc, snap_by_id, presence_rules, quantity_rules, qe_index, notes)
        evidence += historical_presence_evidence(scope_id, sc, obs_by_doc, hist_rules, comp_index)
    seen, unique = set(), []
    for e in evidence:
        if e["evidence_id"] not in seen:
            seen.add(e["evidence_id"])
            unique.append(e)
    unique.sort(key=lambda e: (e["building_id"], e["component_type"], e["source_type"], e["bag_pand_id"] or "", e["evidence_id"]))
    errs = [x for e in unique for x in cp.evidence_errors(e, set(comp_index))] + cp.store_errors(decisions_store)
    if errs:
        raise cp.PresenceError("; ".join(errs))

    input_hashes = {"building_links": sha_file(bl.LINK_STORE), "quantity_observations": sha_file(QO_PATH),
                    "component_types": sha_file(cp.COMPONENT_TYPES), "presence_rules": sha_file(cp.PRESENCE_RULES),
                    "decision_store": sha_file(cp.DECISIONS)} if all(
        p.exists() for p in (bl.LINK_STORE, QO_PATH, cp.COMPONENT_TYPES, cp.PRESENCE_RULES, cp.DECISIONS)) else {}
    evidence_store = {"builder_version": BUILDER_VERSION,
                      "note": "Afgeleide component presence evidence (PROPOSED/REVIEW_REQUIRED). Besluiten staan in "
                              "data/component_presence/component_presence_decision_records.json. Geen hoeveelheden.",
                      "evidence": unique, "notes": notes}
    buildings = build_inventory(scopes, unique, comp_index, decisions_store)
    summary = {"buildings": len(buildings), "component_types": len(comp_index), "evidence_records": len(unique),
               "by_assertion": {a: sum(1 for e in unique if e["assertion"] == a) for a in cp.ASSERTIONS},
               "by_source_type": {t: sum(1 for e in unique if e["source_type"] == t) for t in sorted({e["source_type"] for e in unique})},
               "decisions_in_store": len(decisions_store["records"]),
               "active_decisions": sum(1 for r in decisions_store["records"] if r["status"] == "ACTIVE")}
    inventory = {"builder_version": BUILDER_VERSION, "contract_version": "component_inventory_v1",
                 "note": "Afgeleide gebouwinventaris (component presence). Niet met de hand aanpassen. Zonder menselijk besluit "
                         "is niets 'confirmed' of 'absent'. Bevat GEEN hoeveelheden, onderhoudsplannen of prijzen.",
                 "input_hashes": input_hashes, "summary": summary, "buildings": buildings}
    return {"evidence_store": evidence_store, "inventory": inventory}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Building Element Inventory builder v1")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    res = build()
    outputs = ((OUT_EVIDENCE, dumps(res["evidence_store"])), (OUT_INVENTORY, dumps(res["inventory"])))
    if args.check:
        ok = all(p.exists() and p.read_text(encoding="utf-8") == c for p, c in outputs)
        print("component inventory up-to-date" if ok else "component inventory NIET up-to-date")
        return 0 if ok else 1
    for p, c in outputs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c, encoding="utf-8", newline="\n")
    s = res["inventory"]["summary"]
    print(f"{s['evidence_records']} presence-evidences, {s['buildings']} gebouwen, {s['active_decisions']} besluiten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
