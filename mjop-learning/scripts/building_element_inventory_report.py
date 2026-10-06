"""Building Element Inventory Foundation v1 — reviewrapport (read-only, afgeleid).

Schrijft: reports/inventory/building_element_inventory_foundation_v1.json / .md

Secties: A (waarom ELEMENT_LIBRARY geen inventaris is) · B (vocabulaire) · C (app-element -> componenten) · D (evidence-model) ·
E (besluitmodel) · F (Maldenhof) · G (DOC-012) · H (kozijn-bevindingen) · I (legacy appartementfactor) · J (voorgesteld
kozijn-instance-model) · K (repeat-group-model) · L (menselijke besluiten voor de volgende milestone).

Geen besluiten, geen hoeveelheden, geen productiegedrag: dit rapport leest alleen bestaande canonical data en de
afgeleide inventaris (scripts/build_component_inventory.py).

    python scripts/building_element_inventory_report.py [--check]
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_component_inventory as bci  # noqa: E402
import component_presence as cp  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_LIBRARY = ROOT / "reports" / "quantity" / "subject_expansion_inputs" / "mjop_app_element_library_eaeb256.json"
APP_LIBRARY_PREV = ROOT / "reports" / "quantity" / "subject_expansion_inputs" / "mjop_app_element_library_1afdeca.json"
FACADE_POC = ROOT / "reports" / "quantity" / "facade_element_detection_poc_v2_maldenhof.json"
OUT_JSON = ROOT / "reports" / "inventory" / "building_element_inventory_foundation_v1.json"
OUT_MD = ROOT / "reports" / "inventory" / "building_element_inventory_foundation_v1.md"
KOZIJN_CODES = ("3120", "3230", "4631", "4632", "4634")
KOZIJN_KEYWORDS = ("kozijn",)
FRAME_BUILDING_LABEL = {"BAG:0518100000354752": "DOC-012 Meppelweg (1 pand)"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Secties
# --------------------------------------------------------------------------

def section_a(lib, prev, reqs):
    by_key = {r["app_element_key"]: r for r in reqs["requirements"]}
    rows = []
    for el in lib["elements"]:
        r = by_key[el["key"]]
        rows.append({"app_element_key": el["key"], "label": el["naam"], "categorie": el["categorie"], "sfb": el["sfb"],
                     "app_type": el["type"], "quantity_source": el.get("bron") or ("autoKozijn (KOZ_FACTOREN)" if el["type"] == "kozijnen" else None), "app_optional": bool(el.get("optioneel")),
                     "app_marks_as_estimate": bool(el.get("benadering")), "classification": r["classification"],
                     "activation_mode": r["activation_mode"], "requires": r["requires"], "requires_any": r["requires_any"]})
    prev_by = {e["key"]: e for e in prev["elements"]}
    changed = [{"key": e["key"], "added_fields": sorted(set(e) - set(prev_by[e["key"]]))} for e in lib["elements"] if e != prev_by.get(e["key"])]
    return {
        "reason": "ELEMENT_LIBRARY (MJOP-App src/app.js) mengt drie concepten: fysieke bouwdelen waarop onderhoud plaatsvindt, "
                  "onderhoud/service op die bouwdelen en ondersteunende kostenposten. Een post 'aanwezig' in de bibliotheek zegt dus "
                  "niet dat het gebouw dat bouwdeel heeft: 'dakinspectie' is een service, 'steiger' een kostenpost, 'dakisolatie' een "
                  "gebruikersgekozen verbetering, 'schilderwerk-buiten' hangt van materiaal/afwerking af. Daarom een aparte Building "
                  "Element Inventory van FYSIEKE componenten.",
        "app_source": lib["source"], "element_count": len(lib["elements"]),
        "classification_counts": dict(sorted(Counter(r["classification"] for r in rows).items())),
        "activation_mode_counts": dict(sorted(Counter(r["activation_mode"] for r in rows).items())),
        "quantity_source_counts": dict(sorted(Counter(str(r["quantity_source"]) for r in rows).items())),
        "app_optional_count": sum(1 for r in rows if r["app_optional"]),
        "elements": rows,
        "differences_vs_previous_snapshot_1afdeca": changed,
        "difference_note": "Sinds snapshot 1afdeca heeft de app voor gevel-metselwerk en voegwerk het veld 'benadering: true' gekregen "
                           "(Missingness Safety / Price Source Labels); verder is ELEMENT_LIBRARY ongewijzigd. De MJOP-App is niet aangepast.",
    }


def section_b(comp):
    return {"count": len(comp["component_types"]), "presence_implies_quantity": comp["presence_implies_quantity"],
            "component_types": comp["component_types"], "explicitly_not_components": comp["explicitly_not_components"],
            "naming_note": "Eigen beschrijvende ids; geen claim dat dit of de interne element_code-codes officiële NL-SfB zijn."}


def section_c(reqs, lib):
    return {"requirements": reqs["requirements"], "classifications": reqs["classifications"],
            "activation_modes": reqs["activation_modes"], "no_production_change": True,
            "steiger": "SUPPORT_SERVICE, NOT_PRESENCE_DRIVEN", "dakisolatie": "OPTIONAL_IMPROVEMENT, USER_SELECTED",
            "schilderwerk_buiten": "ATTRIBUTE_DEPENDENT_MAINTENANCE: component + materiaal/afwerking nodig, 'gevel aanwezig' volstaat niet"}


def section_d(evidence, rules):
    evs = evidence["evidence"]
    return {
        "contract": "schemas/component_presence_evidence.schema.json", "evidence_id": "CPE-<sha256(canonieke inhoud)[:16]> (content-addressed)",
        "assertions": rules["assertion_semantics"],
        "silence_rule": "Niet gevonden in oud MJOP / niet zichtbaar op foto / niet getekend != ABSENT. Zulke stilte levert geen evidence op; "
                        "de component blijft 'unknown'. ABSENT vereist een expliciete absence_basis (expliciete nulwaarde of expliciete "
                        "bronuitspraak) en is altijd REVIEW_REQUIRED.",
        "missing_rule": "Ontbrekend 3D BAG-veld = UNKNOWN (GEOMETRY_FIELD_MISSING), nooit ABSENT en nooit 0.",
        "bag3d_rules": rules["bag3d_presence_rules"],
        "historical_rules": [{"rule_id": r["rule_id"], "component_type": r["component_type"], "element_code_internal": r["element_code_internal"],
                              "descriptions": r["element_description_original_exact"], "inference": r["inference"]}
                             for r in rules["historical_mjop_presence_rules"]],
        "deliberately_not_mapped": rules["deliberately_not_mapped"],
        "historical_quantity_rule": "Een historische hoeveelheid bij een expliciete bronregel blijft HISTORICAL_REPORTED_QUANTITY_CONTEXT in "
                                    "details.historical_reported_quantity_context; ze is nooit geometrie, raamopening, kozijnoppervlak, "
                                    "schilderoppervlak of aantal.",
        "stats": {"records": len(evs), "by_assertion": dict(sorted(Counter(e["assertion"] for e in evs).items())),
                  "by_source_type": dict(sorted(Counter(e["source_type"] for e in evs).items())),
                  "by_method_class": dict(sorted(Counter(e["method_class"] for e in evs).items())),
                  "by_status": dict(sorted(Counter(e["status"] for e in evs).items()))},
    }


def section_e(store):
    return {"contract": "schemas/component_presence_decision.schema.json", "store": "data/component_presence/component_presence_decision_records.json",
            "key": "building_id + component_type (of building_id + bag_pand_id + component_type indien nodig)",
            "decision_values": ["PRESENT", "ABSENT", "UNKNOWN"], "reviewer_type": "human",
            "stores": ["considered_evidence_ids", "decision", "decision_reason", "reviewer", "reviewed_at", "supersedes"],
            "rules": ["append-only (alleen status ACTIVE -> SUPERSEDED / REVIEW_REQUIRED)", "per sleutel hoogstens één ACTIVE record",
                      "geen meerderheidstem, geen middeling, geen automatische winnaar",
                      "PRESENT/ABSENT vereisen overwogen evidence; menselijke kennis zonder document eerst als MANUAL-evidence",
                      "komt er evidence bij na een besluit, dan wordt de component DECISION_REVIEW_REQUIRED"],
            "records_in_store": len(store["records"]), "decisions_made_in_this_milestone": 0}


def _entry_rows(inv_building, evidence_by_id):
    rows = []
    for list_name in bci.LIST_KEYS:
        for e in inv_building["components"][list_name]:
            if e["state"] == "UNKNOWN_NO_EVIDENCE":
                continue
            present = e["by_assertion"]["PRESENT"]
            srcs = sorted({s["document_id"] for s in present["scope_sources"]})
            materials = sorted({evidence_by_id[i]["details"].get("material_as_reported") for i in present["evidence_ids"]
                                if evidence_by_id[i]["source_type"] == "MJOP" and evidence_by_id[i]["details"].get("material_as_reported")})
            rows.append({"component_type": e["component_type"], "state": e["state"], "list": list_name,
                         "pand_coverage": e["pand_coverage"], "mjop_documents": srcs, "materials_as_reported": materials,
                         "review_required_evidence": sum(1 for i in e["evidence_ids"] if evidence_by_id[i]["status"] == "REVIEW_REQUIRED"),
                         "evidence_ids": e["evidence_ids"], "notes": e["notes"]})
    return rows


def building_section(inv_building, evidence_by_id, comp_index):
    unknown = [e["component_type"] for e in inv_building["components"]["unknown"] if e["state"] == "UNKNOWN_NO_EVIDENCE"]
    return {"building_id": inv_building["building_id"], "document_ids": inv_building["document_ids"], "pand_count": len(inv_building["bag_pand_ids"]),
            "counts": inv_building["counts"], "components_with_evidence": _entry_rows(inv_building, evidence_by_id),
            "unknown_no_evidence": unknown,
            "unknown_note": "Geen bewijs, dus 'unknown'. Dat betekent niet 'afwezig': een bouwdeel dat een oud MJOP niet noemt, kan er wel zijn."}


def section_h(qos, inv_buildings, evidence_by_id, poc):
    rows = defaultdict(list)
    for o in qos:
        if o["document_id"] not in {d for b in inv_buildings for d in b["document_ids"]}:
            continue
        el = o["element"]
        if el["element_code_internal"] in KOZIJN_CODES or any(k in (el["element_description_original"] or "").casefold() for k in KOZIJN_KEYWORDS):
            rows[o["document_id"]].append({
                "quantity_observation_id": o["quantity_observation_id"], "element_code": el["element_code_internal"],
                "description": el["element_description_original"], "location": el["location_original"], "material_as_reported": el["material_original"],
                "quantity_as_stated": o["quantity_as_stated"], "unit": o["unit_normalized"], "observation_status": o["status"],
                "review_reasons": o["review_reasons"], "page": o["provenance"].get("page"), "text_fragment": o["provenance"].get("text_fragment"),
                "role": ("PRESENCE_EVIDENCE_EXTERIOR_FRAME" if any(
                    e["source_ref"].get("quantity_observation_id") == o["quantity_observation_id"] and e["component_type"] == "EXTERIOR_FRAME"
                    for e in evidence_by_id.values())
                         else "NOT_EXTERIOR_FRAME_PRESENCE")})
    frame_ev = [e for e in evidence_by_id.values() if e["component_type"] == "EXTERIOR_FRAME"]
    b = poc.get("benchmarks")
    return {
        "exterior_frame_evidence": [{"evidence_id": e["evidence_id"], "building_id": e["building_id"], "document_id": e["source_ref"]["document_id"],
                                     "assertion": e["assertion"], "status": e["status"], "review_reasons": e["review_reasons"],
                                     "material_as_reported": e["details"]["material_as_reported"],
                                     "historical_reported_quantity_context": e["details"]["historical_reported_quantity_context"]}
                                    for e in sorted(frame_ev, key=lambda x: x["evidence_id"])],
        "related_source_rows": {d: v for d, v in sorted(rows.items())},
        "what_we_know": ["Maldenhof (DOC-005/006): 3120 'Kozijn buiten hout' (Alle gevels, hout) staat expliciet in beide MJOP's -> EXTERIOR_FRAME PRESENT, "
                         "material_as_reported = hout (PROPOSED/REVIEW_REQUIRED, geen besluit).",
                         "DOC-012: 3120 'Kozijn buiten hout' staat expliciet -> EXTERIOR_FRAME PRESENT (materiaal komt uit de omschrijving).",
                         "Gevelmateriaal en kozijnmateriaal zijn alleen zoals gerapporteerd (hout); geen meting."],
        "what_we_do_not_know": ["aantal kozijnen (FRAME_COUNT)", "raamopeningoppervlak (WINDOW_OPENING_AREA)", "schilderoppervlak (FRAME_PAINTING_AREA)",
                                "verdeling over gevels/verdiepingen/subtypen (draai-kiep, vast, deur, dakkapel)", "of alle kozijnen hout zijn",
                                "of EXTERIOR_WINDOW en EXTERIOR_DOOR als aparte componenten aanwezig zijn (geen expliciete bronregel)"],
        "reported_quantity_treatment": "756,80 m2 (Maldenhof) en 1296,59 m2 (DOC-012) zijn HISTORICAL_REPORTED_QUANTITY_CONTEXT: niet de raamopening, "
                                       "niet het fysieke kozijnoppervlak, niet het schilderoppervlak en niet het aantal kozijnen. Ze blijven bestaande, "
                                       "aparte historische quantity observations (QO-DOC-005-EL-007 e.d.).",
        "facade_poc_context": "Facade PoC v2 (Maldenhof): openbare panorama's geven onvoldoende dekking voor een complete kozijnhoeveelheid "
                              "(0 van 29 woningen met voldoende dekking; 41% van de buitengevel bevestigd zichtbaar); 756,8 m2 is volgens de PoC "
                              "geen geldige benchmark (NOT_COMPARABLE). Geen accuracy-claim.",
        "poc_coverage_status_counts_panden": poc.get("coverage_status_counts_panden"),
    }


def section_i(reqs, lib, units):
    lef = reqs["legacy_estimate_fallbacks"][0]
    illus = []
    for i, (name, _price) in enumerate(lib["koz_def"]):
        f, m = Decimal(str(lib["koz_factoren"][i])), lib["koz_minima"][i]
        raw = Decimal(units) * f
        illus.append({"type": name, "factor": lib["koz_factoren"][i], "minimum": m,
                      "result_for_illustration": max(m, int(raw.quantize(Decimal(1), rounding="ROUND_HALF_EVEN")))})
    return {
        "classification": "LEGACY_ESTIMATE_FALLBACK", "definition": lef,
        "app_values_snapshot": {"KOZ_FACTOREN": lib["koz_factoren"], "KOZ_MINIMA": lib["koz_minima"], "KOZ_DEF": lib["koz_def"], "ref": lib["source"]["ref"]},
        "treatment": ["niet verwijderd of gewijzigd in de MJOP-App (productiecode ongewijzigd)", "nooit canonical measured evidence",
                      "later alleen gebruiken als er geen betere component-/instance-evidence is, en dan altijd als ESTIMATED zichtbaar",
                      "de factor staat los van elke historische kozijnhoeveelheid (bijv. 756,80 m2)"],
        "illustration_only_not_evidence": {"appartementen": units, "formula": lef["formula"], "per_type": illus,
                                           "note": "ILLUSTRATIE van de legacy-formule (JS-afronding kan bij .5 afwijken); geen evidence, geen invoer voor enige bundel."},
    }


FRAME_INSTANCE_MODEL = {
    "status": "VOORSTEL voor de volgende milestone (niet geïmplementeerd; geen schema/store in deze milestone)",
    "record": "component_instance_group",
    "fields": {
        "component_instance_id": "content-addressed id (CIG-<sha256[:16]>)", "building_id": "BAG:<scope>", "bag_pand_id": "pand waarop de groep betrekking heeft (nullable alleen voor scope-brede groepen)",
        "component_type": "EXTERIOR_WINDOW | EXTERIOR_DOOR | EXTERIOR_FRAME", "facade_side": "FRONT | REAR | LEFT | RIGHT | UNKNOWN", "storey": "integer | 'GROUND' | UNKNOWN",
        "subtype": "bijv. TURN_TILT | FIXED | TURN | DOOR | DORMER", "material": "genormaliseerd (WOOD | ALUMINIUM | PVC | STEEL) + material_as_reported",
        "count": "integer, verplicht per groep", "width": "m, Decimal-string, nullable", "height": "m, Decimal-string, nullable",
        "opening_area_m2": "afgeleid: count x width x height, alleen als width en height expliciet zijn en 'dimension_basis' = OPENING",
        "dimension_basis": "OPENING | FRAME_OUTER | UNKNOWN", "evidence_refs": ["component presence evidence ids", "toekomstige drawing/photo evidence ids"],
        "repeat_group_id": "verwijzing naar een repeat group (nullable)", "status": "PROPOSED | REVIEW_REQUIRED | CONFIRMED",
        "source_type": "DRAWING | PHOTO | MANUAL | ...", "method_class": "bijv. VECTOR_DRAWING_COUNT | MANUAL_COUNT"},
    "separate_quantities": {
        "FRAME_COUNT": "aantal kozijnen (som van count)", "WINDOW_OPENING_AREA": "som count x width x height op openingsmaat",
        "FRAME_PAINTING_AREA": "schilderoppervlak: heeft een eigen rekenregel (profiel, zijden, aantal lagen) en eigen menselijke bevestiging"},
    "hard_rule": "FRAME_COUNT, WINDOW_OPENING_AREA en FRAME_PAINTING_AREA zijn verschillende hoeveelheden en worden nooit automatisch aan elkaar gelijkgesteld.",
    "example": {"component_type": "EXTERIOR_WINDOW", "subtype": "TURN_TILT", "material": "WOOD", "count": 8, "width": "1.20", "height": "1.50",
                "dimension_basis": "OPENING", "opening_area_m2": str((Decimal(8) * Decimal("1.20") * Decimal("1.50")).quantize(Decimal("0.01"))),
                "note": "Alleen een voorbeeld van de vorm; geen data van een echt gebouw."},
}


def section_k(poc):
    groups = [{"group": g["group"], "n_panden": g["n_panden"]} for g in poc.get("repetition_groups", [])]
    return {
        "status": "VOORSTEL voor de volgende milestone (niet geïmplementeerd)",
        "record": "repeat_group",
        "fields": {"repeat_group_id": "RG-<sha256[:16]>", "representative": {"building_id": "BAG:<scope>", "bag_pand_id": "pand A (volledig gemeten/getekend)"},
                   "applies_to": [{"bag_pand_id": "A"}, {"bag_pand_id": "B"}], "multiplier": "aantal panden in applies_to (inclusief representative); moet gelijk zijn aan len(applies_to)",
                   "component_types": "alleen de componenttypen waarvoor de herhaling is bevestigd", "decision": "PROPOSED | USER_CONFIRMED_REPEAT | REJECTED",
                   "decision_ref": "verwijzing naar menselijk besluit (reviewer_type=human)", "deviations": "per pand expliciete afwijkingen (nul of meer)", "status": "PROPOSED | CONFIRMED"},
        "example": {"representative": "pand A", "applies_to": ["A", "B", "C", "D", "E"], "multiplier": 5, "decision": "USER_CONFIRMED_REPEAT"},
        "rules": ["alleen na menselijke bevestiging (USER_CONFIRMED_REPEAT)", "geen automatische symmetrie-aanname (ook geen spiegeling)",
                  "geen patroon uit één pand stil over het hele complex kopiëren", "een afwijkend pand valt uit de groep of krijgt een expliciete afwijking",
                  "een groep geldt per componenttype; bevestiging voor kozijnen zegt niets over daken of installaties"],
        "candidate_groups_from_facade_poc_v2_not_decisions": groups,
        "candidate_note": "Facade PoC v2 vond visueel een gespiegelde rij met eindpanden en middenpanden; dat zijn kandidaten, geen besluit en geen evidence.",
    }


def section_l(inventory, rules):
    items = []
    n = 0

    def add(kind, text, options, recommended):
        nonlocal n
        n += 1
        items.append({"nr": n, "kind": kind, "decision": text, "options": options, "recommended": recommended})
    def label(b):
        return "+".join(b["document_ids"]) + f" ({len(b['bag_pand_ids'])} pand{'en' if len(b['bag_pand_ids']) != 1 else ''})"

    for b in inventory["buildings"]:
        for list_name in ("proposed", "review_required"):
            for e in b["components"][list_name]:
                add("PRESENCE_DECISION", f"{label(b)}: {e['component_type']} bevestigen als aanwezig?",
                    ["PRESENT", "UNKNOWN"], "PRESENT" if e["state"] == "PROPOSED_PRESENT" else "UNKNOWN")
        for e in b["components"]["proposed_absent"]:
            add("ABSENCE_DECISION", f"{label(b)}: {e['component_type']} afwezig verklaren op basis van een expliciete 3D BAG-nulwaarde?",
                ["ABSENT", "UNKNOWN"], "UNKNOWN (3D BAG-geometrie is geen universeel bewijs; liefst bevestigen met foto/tekening)")
    inferences = sorted({r["rule_id"] for r in rules["historical_mjop_presence_rules"] if r["inference"] != "NONE"})
    add("RULE_APPROVAL", "Zijn de presence-regels met inferentie acceptabel (" + ", ".join(inferences) + ")?", ["ACCEPT", "REJECT", "RESTRICT_TO_EXPLICIT"], "ACCEPT als REVIEW_REQUIRED-evidence")
    add("SEMANTIC_MAPPING", "Is 'Deurbelinstallatie' (6411, DOC-012) een INTERCOM_INSTALLATION?", ["YES", "NO", "ADD_COMPONENT_TYPE_DOORBELL"], "NO")
    add("SEMANTIC_MAPPING", "Welk bouwdeel is 'Standleidingen' (5240, DOC-012): binnenriolering of waterleiding?", ["SEWERAGE_DRAINAGE_INTERNAL", "COMMON_WATER_INSTALLATION", "NEITHER"], "geen mapping zonder bron")
    add("ATTRIBUTE_RULE", "Welke kozijn-/gevelmaterialen maken 'schilderwerk-buiten' relevant?", ["WOOD", "WOOD+STEEL", "ALL_PAINTED_ONLY"], "WOOD+STEEL, alleen met materiaalbewijs")
    add("FRAME_MODEL", "Instance-model voor kozijnen goedkeuren (granulariteit: pand x gevel x verdieping x subtype)?", ["APPROVE", "COARSER", "FINER"], "APPROVE")
    add("FRAME_QUANTITIES", "FRAME_COUNT, WINDOW_OPENING_AREA en FRAME_PAINTING_AREA als drie aparte quantity-onderwerpen vastleggen?", ["YES", "NO"], "YES")
    add("REPEAT_POLICY", "Repeat groups alleen na expliciete bevestiging per componenttype en per pand?", ["YES", "NO"], "YES")
    add("LEGACY_FALLBACK", "Legacy kozijnfactor mag later alleen als zichtbare ESTIMATED-fallback zonder component-/instance-evidence?", ["YES", "NO", "REMOVE_LATER"], "YES")
    add("DRAWING_SOURCE", "Welke vectortekening(en) gebruiken we voor de Vector Drawing Reader PoC (Maldenhof en/of Meppelweg)?", ["MALDENHOF", "MEPPELWEG", "BOTH"], "één gebouw eerst")
    return items


# --------------------------------------------------------------------------
# Samenstellen + MD
# --------------------------------------------------------------------------

def build_report(res=None):
    res = res if res is not None else bci.build()
    evidence, inventory = res["evidence_store"], res["inventory"]
    comp = cp.load_json(cp.COMPONENT_TYPES)
    reqs = cp.load_json(cp.APP_REQUIREMENTS)
    rules = cp.load_json(cp.PRESENCE_RULES)
    lib, prev = cp.load_json(APP_LIBRARY), cp.load_json(APP_LIBRARY_PREV)
    poc = cp.load_json(FACADE_POC)
    qos = cp.load_json(bci.QO_PATH)["observations"]
    store = cp.load_store()
    comp_index = cp.component_type_index(comp)
    ev_by_id = {e["evidence_id"]: e for e in evidence["evidence"]}
    by_building = {b["building_id"]: building_section(b, ev_by_id, comp_index) for b in inventory["buildings"]}
    maldenhof = next(b for b in inventory["buildings"] if "DOC-005" in b["document_ids"])
    doc012 = next(b for b in inventory["buildings"] if "DOC-012" in b["document_ids"])
    rep = {
        "report_version": "building_element_inventory_foundation_v1", "builder_version": bci.BUILDER_VERSION,
        "status": "ANALYSE / FOUNDATION: geen besluiten, geen hoeveelheden, geen productiegedrag",
        "scope": "Alleen de twee bestaande testgebouwen: Maldenhof (DOC-005/006) en DOC-012 Meppelweg. Geen derde gebouw, geen Drawing Reader, geen vision-model, geen prijsactivatie.",
        "inputs": {"app_library_snapshot": {"path": str(APP_LIBRARY.relative_to(ROOT)), "sha256": sha(APP_LIBRARY), "source": lib["source"]},
                   "component_types": sha(cp.COMPONENT_TYPES), "app_element_requirements": sha(cp.APP_REQUIREMENTS), "presence_rules": sha(cp.PRESENCE_RULES),
                   "evidence_records": len(evidence["evidence"])},
        "A_why_element_library_is_not_an_inventory": section_a(lib, prev, reqs),
        "B_component_vocabulary": section_b(comp),
        "C_app_element_requirements": section_c(reqs, lib),
        "D_evidence_model": section_d(evidence, rules),
        "E_human_decision_model": section_e(store),
        "F_maldenhof_proposed_inventory": by_building[maldenhof["building_id"]],
        "G_doc012_proposed_inventory": by_building[doc012["building_id"]],
        "H_frame_findings": section_h(qos, inventory["buildings"], ev_by_id, poc),
        "I_legacy_apartment_factor": section_i(reqs, lib, "29"),
        "J_proposed_frame_instance_model": FRAME_INSTANCE_MODEL,
        "K_repeat_group_model": section_k(poc),
        "L_human_decisions_next_milestone": section_l(inventory, rules),
        "unchanged_guarantees": {"production_code_changed": False, "mjop_app_modified": False, "decisions_written": 0, "quantity_resolutions_written": 0,
                                 "quantity_bundles_changed": False, "prices_changed": False, "crosswalk_decisions_changed": False},
    }
    return rep


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return out


def _coverage_text(r):
    c = r["pand_coverage"]
    if c["present"] + c["absent"] + c["unknown"] == 0:
        return "scope-brede bron (geen 3D BAG-regel)"
    return f"3D BAG: {c['present']} aanwezig / {c['absent']} afwezig / {c['unknown']} onbekend van {c['scope_pand_count']}"


def _building_md(title, b):
    L = [f"## {title}", "", f"Gebouwscope `{b['building_id'][:60]}{'…' if len(b['building_id']) > 60 else ''}` · documenten {', '.join(b['document_ids'])} · "
         f"{b['pand_count']} bevestigd(e) pand(en). Geen menselijk besluit: alles is PROPOSED of unknown.", "",
         f"Telling: {', '.join(f'{k} {v}' for k, v in b['counts'].items())}.", ""]
    L += md_table(["component", "staat", "3D BAG per pand", "MJOP-documenten", "materiaal (zoals gerapporteerd)", "review-evidence"],
                  [(r["component_type"], r["state"], _coverage_text(r),
                    ", ".join(r["mjop_documents"]) or "—", ", ".join(r["materials_as_reported"]) or "—", r["review_required_evidence"]) for r in b["components_with_evidence"]])
    L += ["", f"Unknown (geen enkel bewijs; stilte is geen afwezigheid): {', '.join(b['unknown_no_evidence'])}.", ""]
    return L


def render_md(rep):
    A, B, C, D, E = (rep[k] for k in ("A_why_element_library_is_not_an_inventory", "B_component_vocabulary", "C_app_element_requirements",
                                       "D_evidence_model", "E_human_decision_model"))
    H, I, J, K = rep["H_frame_findings"], rep["I_legacy_apartment_factor"], rep["J_proposed_frame_instance_model"], rep["K_repeat_group_model"]
    L = ["# Building Element Inventory Foundation v1", "", f"Status: **{rep['status']}**. {rep['scope']}", "",
         "Keten: BUILDING SCOPE → COMPONENT PRESENCE EVIDENCE → HUMAN COMPONENT DECISION → COMPONENT INVENTORY → COMPONENT QUANTITIES → MAINTENANCE TEMPLATES → PRICE. "
         "Deze milestone bouwt alleen de eerste vier stappen; presence is een ander concept dan quantity.", "",
         "## A. Waarom de app ELEMENT_LIBRARY geen building inventory is", "", A["reason"], "",
         f"Audit van MJOP-App `{A['app_source']['ref'][:7]}` ({A['element_count']} elementen): " +
         ", ".join(f"{k} {v}" for k, v in A["classification_counts"].items()) + f". Hoeveelheidsbron: " + ", ".join(f"{k} {v}" for k, v in A["quantity_source_counts"].items()) +
         f". {A['difference_note']}", ""]
    L += md_table(["app-element", "klasse", "activatie", "vereist", "vereist één van", "bron"],
                  [(r["app_element_key"], r["classification"], r["activation_mode"], ", ".join(r["requires"]) or "—", ", ".join(r["requires_any"]) or "—", r["quantity_source"]) for r in A["elements"]])
    L += ["", "## B. Component-vocabulaire", "", f"{B['count']} fysieke componenttypes (`vocabularies/building_component_types_v1.json`). {B['naming_note']}", ""]
    L += md_table(["component", "categorie", "NL", "hint"], [(c["component_type"], c["category"], c["label_nl"], c["sfb_like_hint"]) for c in B["component_types"]])
    L += ["", "Geen componenten: " + "; ".join(f"{x['term']} ({x['reason']})" for x in B["explicitly_not_components"]), "",
          "## C. Mapping app-element → vereiste componenten", "",
          "Volledige tabel in sectie A; vastgelegd in `vocabularies/app_element_requirements_v1.json`. Steiger = SUPPORT_SERVICE (niet presence-driven); "
          "dakisolatie = OPTIONAL_IMPROVEMENT (gebruikersgekozen); schilderwerk-buiten = ATTRIBUTE_DEPENDENT (component + materiaal/afwerking). "
          "Geen productiegedrag gewijzigd; geen automatische activatie of verwijdering.", "",
          "## D. Evidence-model", "", f"Schema `{D['contract']}`; id: {D['evidence_id']}.", "", f"- Stilte: {D['silence_rule']}", f"- Ontbrekend: {D['missing_rule']}",
          f"- Historische hoeveelheid: {D['historical_quantity_rule']}", f"- Stand: {D['stats']['records']} records; per assertion {D['stats']['by_assertion']}; per bron {D['stats']['by_source_type']}; per status {D['stats']['by_status']}.", "",
          "## E. Menselijk besluitmodel", "", f"Schema `{E['contract']}`, store `{E['store']}` ({E['records_in_store']} records; **{E['decisions_made_in_this_milestone']} besluiten in deze milestone**).", ""]
    L += [f"- {r}" for r in E["rules"]] + [""]
    L += _building_md("F. Maldenhof — voorgestelde inventaris", rep["F_maldenhof_proposed_inventory"])
    L += _building_md("G. DOC-012 — voorgestelde inventaris", rep["G_doc012_proposed_inventory"])
    L += ["## H. Kozijn-specifieke bevindingen", "", "**Wat we weten**", ""] + [f"- {x}" for x in H["what_we_know"]] + ["", "**Wat we niet weten**", ""] + [f"- {x}" for x in H["what_we_do_not_know"]]
    L += ["", f"**756,80 m²:** {H['reported_quantity_treatment']}", "", f"**Facade PoC:** {H['facade_poc_context']}", "", "Relevante bronregels:", ""]
    for doc, rows in H["related_source_rows"].items():
        L += [f"*{doc}*", ""] + md_table(["observation", "code", "omschrijving", "locatie", "materiaal", "hoeveelheid", "rol"],
                                         [(r["quantity_observation_id"], r["element_code"], r["description"], r["location"] or "—", r["material_as_reported"] or "—",
                                           f"{r['quantity_as_stated']} {r['unit']}", r["role"]) for r in rows]) + [""]
    L += ["## I. Legacy appartementfactor", "", f"Classificatie **{I['classification']}**. App-waarden: factoren {I['app_values_snapshot']['KOZ_FACTOREN']}, minima {I['app_values_snapshot']['KOZ_MINIMA']}.", ""]
    L += [f"- {x}" for x in I["treatment"]] + ["", f"Illustratie bij {I['illustration_only_not_evidence']['appartementen']} appartementen (geen evidence): " +
         ", ".join(f"{r['type']} {r['result_for_illustration']}" for r in I["illustration_only_not_evidence"]["per_type"]) + ".", "",
         "## J. Voorgesteld frame-instance-model (volgende milestone)", "", f"{J['status']}. {J['hard_rule']}", "", "```json", json.dumps(J["example"], indent=1, ensure_ascii=False), "```", "",
         "Velden: " + ", ".join(f"`{k}`" for k in J["fields"]) + ".", "",
         "## K. Repeat-group-model (volgende milestone)", "", f"{K['status']}.", ""]
    L += [f"- {r}" for r in K["rules"]] + ["", f"Kandidaat-groepen uit Facade PoC v2 (geen besluit): " + ", ".join(f"{g['group']} ({g['n_panden']})" for g in K["candidate_groups_from_facade_poc_v2_not_decisions"]) + ".", "",
          "## L. Menselijke besluiten voor de volgende milestone", ""]
    L += md_table(["#", "type", "besluit", "opties", "aanbeveling"], [(i["nr"], i["kind"], i["decision"], " / ".join(i["options"]), i["recommended"]) for i in rep["L_human_decisions_next_milestone"]])
    g = rep["unchanged_guarantees"]
    L += ["", "## Ongewijzigd", "", "MJOP-App-productiecode, quantity bundles, quantity resolutions, crosswalk-besluiten, prijzen en building links zijn ongewijzigd; "
          f"er zijn {g['decisions_written']} presence-besluiten geschreven.", ""]
    return "\n".join(L)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Building Element Inventory Foundation v1 — rapport")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    rep = build_report()
    outputs = ((OUT_JSON, dumps(rep)), (OUT_MD, render_md(rep) + "\n"))
    if args.check:
        ok = all(p.exists() and p.read_text(encoding="utf-8") == c for p, c in outputs)
        print("inventory report up-to-date" if ok else "inventory report NIET up-to-date")
        return 0 if ok else 1
    for p, c in outputs:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(c, encoding="utf-8", newline="\n")
    print(f"rapport geschreven: {len(rep['L_human_decisions_next_milestone'])} voorgelegde besluiten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
