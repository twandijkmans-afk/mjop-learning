"""Bouwt de Frame Inventory Foundation v1: data/frame_inventory/* en reports/frames/frame_inventory_foundation_v1.{json,md}.

Afgeleid, deterministisch, geen netwerk. Er worden GEEN instances, groepen of quantities verzonnen: zonder tekening/handmatige
bevestiging zijn alle zeven quantity-concepten UNKNOWN en blijft de legacy appartementfactor (KOZ_FACTOREN) de enige, als
LEGACY_ESTIMATE_FALLBACK gelabelde, schatting in de app.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import component_presence as cp  # noqa: E402
import frame_inventory as fi  # noqa: E402

BUILDER_VERSION = "frame_inventory_foundation_v1.0.0"
OUT_STORE, OUT_REPEAT = fi.FRAME_INVENTORY, fi.REPEAT_GROUPS
OUT_JSON = ROOT / "reports" / "frames" / "frame_inventory_foundation_v1.json"
OUT_MD = ROOT / "reports" / "frames" / "frame_inventory_foundation_v1.md"
EVIDENCE = ROOT / "data" / "component_presence" / "component_presence_evidence_v1.json"
INVENTORY = ROOT / "data" / "component_inventory" / "component_inventory_v1.json"
AUDIT = ROOT / "reports" / "drawing" / "vector_drawing_source_audit_v1.json"
LABELS = {"DOC-005": "Maldenhof 240-296 (DOC-005 + DOC-006)", "DOC-012": "Meppelweg (DOC-012)"}
QUANTITY_KEYS = ("FRAME_COUNT", "WINDOW_COUNT", "EXTERIOR_DOOR_COUNT", "WINDOW_OPENING_AREA", "FRAME_OUTER_AREA", "FRAME_PAINTING_AREA", "GLASS_AREA")
SEVEN = ["FRAME_COUNT", "WINDOW_COUNT", "EXTERIOR_DOOR_COUNT", "WINDOW_OPENING_AREA", "FRAME_OUTER_AREA", "FRAME_PAINTING_AREA", "GLASS_AREA"]


def validate_schema(obj, schema_name):
    import jsonschema
    from referencing import Registry, Resource
    resources = []
    for n in ("frame_component_instance", "frame_group", "frame_inventory", "component_repeat_group"):
        s = json.loads((ROOT / "schemas" / f"{n}.schema.json").read_text(encoding="utf-8"))
        resources.append((s["$id"], Resource.from_contents(s)))
    reg = Registry().with_resources(resources)
    schema = json.loads((ROOT / "schemas" / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema, registry=reg).validate(obj)


def build(decisions_store=None, evidence_store=None, inventory=None, audit=None):
    decisions_store = decisions_store or cp.load_store()
    evidence = (evidence_store or cp.load_json(EVIDENCE))["evidence"]
    inventory = inventory or cp.load_json(INVENTORY)
    audit = audit or cp.load_json(AUDIT)
    active = cp.active_decisions(decisions_store)
    ev_by_id = {e["evidence_id"]: e for e in evidence}
    real_world = audit["real_world_status"]
    buildings = []
    for b in inventory["buildings"]:
        d = active.get((b["building_id"], None, "EXTERIOR_FRAME"))
        if d is None:
            continue
        evs = [ev_by_id[i] for i in d["considered_evidence_ids"]]
        material = sorted({e["details"].get("material_as_reported") for e in evs if e["details"].get("material_as_reported")})
        hist = [{"document_id": e["source_ref"]["document_id"], "quantity_observation_id": e["details"]["historical_reported_quantity_context"]["quantity_observation_id"],
                 "element_description_as_reported": e["details"]["element_description_as_reported"],
                 "quantity_value": e["details"]["historical_reported_quantity_context"]["quantity_value"], "unit": "m2",
                 "interpretation": "HISTORICAL_REPORTED_QUANTITY_CONTEXT", "never_interpreted_as": list(SEVEN)} for e in evs]
        label = next((LABELS[x] for x in b["document_ids"] if x in LABELS), b["building_id"])
        buildings.append({
            "building_id": b["building_id"], "label": label, "bag_pand_ids": b["bag_pand_ids"],
            "exterior_frame_presence": {"state": "CONFIRMED_PRESENT", "decision_id": d["decision_id"], "considered_evidence_ids": d["considered_evidence_ids"],
                                        "material_as_reported": material[0] if material else None},
            "quantities": {k: {"status": "UNKNOWN", "value": None, "unit": "count" if k.endswith("COUNT") else "m2",
                               "reason": "geen bevestigde instances, geen tekening-meting; presence zegt niets over aantal/oppervlak"} for k in SEVEN},
            "historical_reported_quantity_context": hist,
            "legacy_estimate_fallback": {"source": "LEGACY_ESTIMATE_FALLBACK", "applies": True,
                                         "reason": "geen confirmed/manual/drawing-based frame inventory beschikbaar; app gebruikt appartementen x KOZ_FACTOREN als zichtbare schatting"},
            "drawing_source_status": real_world})
    buildings.sort(key=lambda x: x["building_id"])
    voc = cp.load_json(fi.CONCEPTS_VOCAB)
    store = {"store_version": "frame_inventory_v1", "builder_version": BUILDER_VERSION,
             "note": "Frame Inventory Foundation v1. Geen instances/groepen: er is nog geen tekening-meting of handmatige bevestiging. Presence is een ander concept dan quantity.",
             "instances": [], "frame_groups": [], "buildings": buildings,
             "policy": {"quantity_concepts": SEVEN, "auto_equal_to": "NONE", "painting_area": "NEVER_AUTOMATIC",
                        "legacy_estimate_fallback": voc["legacy_estimate_fallback"], "future_source_priority": voc["future_source_priority"],
                        "future_source_priority_scope": voc["future_source_priority_scope"]}}
    store.pop("builder_version")
    repeat = {"store_version": "component_repeat_group_v1",
              "note": "Repeat groups zijn pas ACTIVE na USER_CONFIRMED_REPEAT. Leeg: er is geen bevestiging gegeven; REPEAT_CANDIDATEs uit de Maldenhof facade-PoC (END_OF_ROW_1_ADDR 1, END_OF_ROW_2_ADDR 1, MIDDLE_2_ADDR 13) zijn context, geen records.",
              "groups": []}
    errs = fi.store_errors(store) + [e for g in repeat["groups"] for e in fi.repeat_group_errors(g)]
    if errs:
        raise fi.FrameError("; ".join(errs))
    return store, repeat, report(store, audit, decisions_store, voc)


def report(store, audit, decisions_store, voc):
    s = audit["summary"]
    docs = [{"paths": d["paths"], "registry_document_ids": d["registry_document_ids"], "pages": d["page_count"], "classification": d["classification"]} for d in audit["documents"]]
    maldenhof = next(b for b in store["buildings"] if "Maldenhof" in b["label"])
    return {
        "report_version": "frame_inventory_foundation_v1", "builder_version": BUILDER_VERSION,
        "A_frame_data_model": {"schemas": ["schemas/frame_component_instance.schema.json", "schemas/frame_group.schema.json", "schemas/frame_inventory.schema.json"],
                               "store": "data/frame_inventory/frame_inventory_v1.json", "component_types": list(fi.COMPONENT_TYPES), "facade_sides": list(fi.FACADE_SIDES),
                               "subtypes": list(fi.SUBTYPES), "materials": list(fi.MATERIALS), "dimension_bases": list(fi.DIMENSION_BASES), "statuses": list(fi.STATUSES),
                               "instances_in_store": len(store["instances"]), "groups_in_store": len(store["frame_groups"])},
        "B_quantity_semantics": {"concepts": voc["concepts"], "historical_context": voc["historical_context_only"]},
        "C_repeat_groups": {"schema": "schemas/component_repeat_group.schema.json", "store": "data/frame_inventory/component_repeat_groups_v1.json", "groups_in_store": 0,
                            "active_requires": "USER_CONFIRMED_REPEAT door een mens", "candidates_only_from_vision_or_drawing": True},
        "D_source_audit": {"report": "reports/drawing/vector_drawing_source_audit_v1.json", "summary": s, "documents": docs, "real_world_status": audit["real_world_status"]},
        "E_chosen_pdf_page": None,
        "F_vector_primitives": {"real_world": "NIET UITGEVOERD (geen tekening)", "reader": "scripts/vector_drawing_reader.py", "validated_on": "tests/fixtures/drawing/TEST_FIXTURE_synthetic_facade_v1.pdf (synthetische TEST FIXTURE, geen real-world resultaat)"},
        "G_scale_evidence": {"real_world": "geen", "rules": ["maatlijn (voorkeur): value_mm / lijnlengte; meerdere maatlijnen binnen 2%", "tekeningschaal 1:N + standaard ISO-papier (+ maatlijn binnen 2% indien aanwezig)", "anders UNKNOWN"]},
        "H_opening_candidates": {"real_world_count": None, "note": "geen echte gevel-/aanzichttekening; niets gedetecteerd, niets gerapporteerd"},
        "I_real_world_limitations": ["geen enkele bouwtekening in de repo; alleen MJOP-rapporten (tabellen, grafieken, foto's)", "reader gevalideerd op synthetische fixture; nooit op een echte tekening",
                                     "maatlijn-detectie veronderstelt losse numerieke tekst (mm) bij een rechte lijn; echte tekeningen met pijlen/ticks/tekst-als-paden kunnen aanpassing vragen",
                                     "geen OCR; tekst-als-afbeelding of tekst-als-paden wordt niet gelezen", "geen accuracy-claim mogelijk"],
        "J_maldenhof_historical_cross_check": {"classification": "NOT_COMPARABLE", "drawing_derived": {"count": None, "opening_area_m2": None, "frame_outer_area_m2": None},
                                               "historical": maldenhof["historical_reported_quantity_context"], "accuracy_percentage": None,
                                               "reason": "geen drawing-derived waarden; de betekenis van de historische m2 is niet bewezen"},
        "K_next_human_decisions": ["welke tekening(en)/gebouw voor de eerste echte PoC (Maldenhof of Meppelweg)", "goedkeuring frame-instance-model (granulariteit: pand x gevel x verdieping x subtype)",
                                   "bevestiging dat de zeven quantity-concepten gescheiden blijven", "repeat-policy: alleen na USER_CONFIRMED_REPEAT per componenttype",
                                   "legacy kozijnfactor: zichtbare ESTIMATED-fallback behouden / later verwijderen", "overige presence-besluiten (26 openstaand) blijven bij de gebruiker"],
        "L_exact_next_input": {"preferred": "originele vector-PDF (geen scan/foto/screenshot) van een gevelaanzicht met zichtbare maatvoering",
                               "details": ["voorgevel en achtergevel (liefst beide)", "maatlijnen/maatvoering zichtbaar of expliciete schaal (1:50/1:100) op een standaard papierformaat (A0-A3), niet 'passend' geschaald",
                                           "liefst dezelfde VvE: Maldenhof 240-296 of Meppelweg (DOC-012)", "ook welkom: kozijnstaat (kozijnenstaat) als PDF met tekst-laag"]},
        "legacy_appartementfactor": voc["legacy_estimate_fallback"], "future_source_priority": {"order": voc["future_source_priority"], "scope": voc["future_source_priority_scope"]},
        "presence_decisions": [{"decision_id": r["decision_id"], "building_id": r["building_id"], "component_type": r["component_type"], "decision": r["decision"],
                                "reviewer": r["reviewer"], "reviewed_at": r["reviewed_at"], "considered_evidence_ids": r["considered_evidence_ids"]} for r in decisions_store["records"]],
        "buildings": store["buildings"]}


def md(r):
    L = ["# Frame Inventory Foundation v1 + Vector Drawing Reader PoC v1", "",
         f"Status real-world PoC: **{r['D_source_audit']['real_world_status']}**. De foundation (model, semantiek, repeat-contract, presence-besluiten) is gebouwd; "
         "er is geen echte vector-tekening, dus geen real-world kozijnextractie en geen accuracy-claim.", "", "## Presence-besluiten (EXTERIOR_FRAME)", "",
         "| Besluit | Gebouw | Besluit | Reviewer | Evidence |", "|---|---|---|---|---|"]
    for d in r["presence_decisions"]:
        b = next(b for b in r["buildings"] if b["building_id"] == d["building_id"])
        L.append(f"| {d['decision_id']} | {b['label']} | {d['component_type']} = {d['decision']} | {d['reviewer']['reviewer_id']} ({d['reviewer']['reviewer_type']}) | {', '.join(d['considered_evidence_ids'])} |")
    L += ["", "Het besluit zegt alleen PRESENT. `material_as_reported = hout` blijft evidence-detail. Geen uitspraak over aantal, oppervlak, afmetingen, ramen/deuren of schilderoppervlak.", "",
          "## A. Frame data model", "",
          f"- Component types: {', '.join(r['A_frame_data_model']['component_types'])} (frame, raam en deur zijn gescheiden)",
          f"- facade_side: {', '.join(r['A_frame_data_model']['facade_sides'])}; subtype: {', '.join(r['A_frame_data_model']['subtypes'])}",
          f"- material: {', '.join(r['A_frame_data_model']['materials'])}; dimension_basis: {', '.join(r['A_frame_data_model']['dimension_bases'])}; status: {', '.join(r['A_frame_data_model']['statuses'])}",
          "- Instance: frame_instance_id, building_id, bag_pand_id, component_type, facade_side, storey, subtype, material, count, optioneel width_m/height_m/dimension_basis, optioneel opening_area_m2/frame_outer_area_m2, source_refs, provenance, status. Maten als Decimal-strings.",
          "- Er bestaat bewust GEEN `painting_area_m2`: schilderoppervlak wordt nooit automatisch afgeleid.",
          "- Groep (`frame_group`): representative_instance + count + applies_to + source_refs; één tekeningsymbool meerdere keren alleen met per-occurrence bewijs; geen gebouwbrede multiplier zonder menselijk besluit.",
          f"- Store: {r['A_frame_data_model']['instances_in_store']} instances, {r['A_frame_data_model']['groups_in_store']} groepen (niets verzonnen).", "",
          "## B. Quantity semantics", "", "Zeven aparte concepten, nooit automatisch gelijk:", "", "| Concept | Eenheid | Afleiding |", "|---|---|---|"]
    for c in r["B_quantity_semantics"]["concepts"]:
        L.append(f"| {c['concept']} | {c['unit']} | {c['derivation']} |")
    L += ["", "Voorbeeld: 8 ramen x 1,20 x 1,50 mag alleen WINDOW_OPENING_AREA = 14,40 m2 opleveren als de maten over de opening gaan EN count = 8 bevestigd is; nooit automatisch FRAME_PAINTING_AREA = 14,40.", "",
          "Historische context: Maldenhof 'Kozijn buiten hout' 756,80 m2 blijft uitsluitend HISTORICAL_REPORTED_QUANTITY_CONTEXT; niet FRAME_COUNT, WINDOW_COUNT, EXTERIOR_DOOR_COUNT, WINDOW_OPENING_AREA, FRAME_OUTER_AREA, FRAME_PAINTING_AREA of GLASS_AREA. Geen ratio, geen conversiefactor, geen accuracy-claim.", "",
          "## C. Repeat groups", "",
          "- Contract: repeat_group_id, building_id, component_type, representative_pand_id, applies_to_pand_ids, transformation (SAME/MIRRORED), evidence_refs, decision_ref, status (REPEAT_CANDIDATE/ACTIVE/REJECTED).",
          "- ACTIVE (bruikbaar) uitsluitend na een menselijk USER_CONFIRMED_REPEAT; vision/tekening stelt alleen een REPEAT_CANDIDATE voor. Geen automatische '13 middenpanden lijken hetzelfde dus x13'.", "- Store: 0 groepen.", "",
          "## D. Source audit", "", f"Zie `reports/drawing/vector_drawing_source_audit_v1.md`. {r['D_source_audit']['summary']['unique_pdfs']} unieke PDF's ({r['D_source_audit']['summary']['total_pdf_paths']} paden), "
          f"{r['D_source_audit']['summary']['total_pages']} pagina's: {r['D_source_audit']['summary']['by_document_classification']}. Pagina's met een sterk tekeninglabel: {r['D_source_audit']['summary']['pages_with_strong_drawing_label']}.", "",
          "## E. Gekozen PDF/pagina", "", "Geen: er is geen VECTOR_DRAWING_CANDIDATE. Een MJOP-tabel is niet als tekening behandeld.", "",
          "## F. Vector primitives", "", "De generieke reader (`scripts/vector_drawing_reader.py`: lines, rectangles, curves, text spans, coordinates, paginamaten, optional-content-aanwezigheid, dimension texts, provenance met source, sha256, pagina, bbox en extractiemethode/versie) is unit-getest op een kleine, duidelijk gemarkeerde synthetische TEST FIXTURE. Er zijn geen real-world observaties (`data/drawing_observations/` bevat geen tekeningdata).", "",
          "## G. Scale evidence", "", "Real-world: geen. Regels: maatlijn (voorkeur) of expliciete tekeningschaal + standaard papierformaat + consistente geometrie; anders dimensions = UNKNOWN. Nooit punten/pixels naar meters zonder bewijs.", "",
          "## H. Opening candidates", "", "Real-world: niet mogelijk, 0 gerapporteerd. De candidate-logica (alleen op een FACADE_ELEVATION; REVIEW_REQUIRED; gevelvlak + herhaling/label/maatvoering; SAME_SYMBOL_CANDIDATE != hetzelfde component) is alleen op de fixture getest.", "",
          "## I. Real-world beperkingen", ""] + [f"- {x}" for x in r["I_real_world_limitations"]]
    L += ["", "## J. Maldenhof historical cross-check", "", "Classificatie: **NOT_COMPARABLE**. Drawing-derived: count, opening area, frame outer area = geen (geen tekening). Historisch: 756,80 m2 'Kozijn buiten hout' (DOC-005 en DOC-006). Geen percentage accuracy.", "",
          "Publieke straatbeelden (eerdere Maldenhof-PoC: confirmed exterior facade coverage ca. 41%, achtergevel ca. 26%, geen pand >= 80% voor+achter) zijn geen ground truth en geen volledige frame-inventaris; ze zijn niet met tekeningmetingen gemengd.", "",
          "## Legacy appartementfactor en bronprioriteit", "", "- `KOZ_FACTOREN = [1, 0.25, 0.125, 0.125]` blijft bestaan als **LEGACY_ESTIMATE_FALLBACK**: alleen gebruiken als er geen confirmed/manual/drawing-based frame inventory is. App-code is niet gewijzigd.",
          "- Toekomstige prioriteit: " + " > ".join(r["future_source_priority"]["order"]) + ". " + r["future_source_priority"]["scope"], "",
          "## K. Volgende menselijke besluiten", ""] + [f"- {x}" for x in r["K_next_human_decisions"]]
    L += ["", "## L. Exact volgende input", "", "Nodig: **" + r["L_exact_next_input"]["preferred"] + "**.", ""] + [f"- {x}" for x in r["L_exact_next_input"]["details"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    store, repeat, rep = build()
    validate_schema(store, "frame_inventory")
    validate_schema(repeat, "component_repeat_group")
    outs = ((OUT_STORE, fi.dumps(store)), (OUT_REPEAT, fi.dumps(repeat)), (OUT_JSON, fi.dumps(rep)), (OUT_MD, md(rep)))
    if args.check:
        ok = all(p.exists() and p.read_text(encoding="utf-8") == c for p, c in outs)
        print("frame inventory actueel" if ok else "frame inventory NIET actueel")
        return 0 if ok else 1
    for p, c in outs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c, encoding="utf-8", newline="\n")
    print("frame inventory geschreven:", len(store["buildings"]), "gebouwen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
