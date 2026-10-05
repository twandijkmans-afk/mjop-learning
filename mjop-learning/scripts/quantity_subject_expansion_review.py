"""Quantity Subject Expansion Review v1 — read-only readiness review na ROOF_FLAT_AREA.

Onderzoekt ROOF_SLOPED_AREA, ROOF_TOTAL_AREA, OUTER_WALL_GROSS_AREA en BUILDING_HEIGHT tegen:
  - vocabularies/quantity_subjects_v1.json, vocabularies/app_element_crosswalk_v1.json
  - de MJOP-App-elementenbibliotheek (reports/quantity/subject_expansion_inputs/mjop_app_element_library_<ref>.json,
    letterlijk uit src/app.js geëvalueerd)
  - historische quantity observations (4712-inventaris)
  - de canonieke evidence van de twee bevestigde gebouwen (Maldenhof, DOC-012)

Neemt GEEN besluiten: geen VERIFY, geen subject-relatie in de vocabulaire, geen bundel, geen resolutie. Voorstellen
(bijv. een historisch dakpannen-onderwerp) staan alleen in dit rapport.

Schrijft: reports/quantity/quantity_subject_expansion_review_v1.json / .md

    python scripts/quantity_subject_expansion_review.py [--check]
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_LIBRARY = ROOT / "reports" / "quantity" / "subject_expansion_inputs" / "mjop_app_element_library_1afdeca.json"
BUNDLES = ROOT / "reports" / "quantity" / "app_bundles"
RESOLUTIONS = ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json"
OUT_JSON = ROOT / "reports" / "quantity" / "quantity_subject_expansion_review_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "quantity_subject_expansion_review_v1.md"
EXPECTED_BUNDLES = {"maldenhof_DOC-005_DOC-006_v3.json": "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933",
                    "doc012_meppelweg_v3.json": "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191"}
SUBJECTS = ("ROOF_FLAT_AREA", "ROOF_SLOPED_AREA", "ROOF_TOTAL_AREA", "OUTER_WALL_GROSS_AREA", "BUILDING_HEIGHT")
CATEGORIES = ("READY_NOW", "READY_WITHOUT_HISTORICAL_CONTEXT", "NEEDS_SEMANTIC_MAPPING", "ESTIMATE_ONLY", "NO_AUTOMATIC_QUANTITY")

# --------------------------------------------------------------------------
# 4712-classificatie: UITSLUITEND op exacte, in de bron vermelde omschrijving (geen fuzzy matching).
# Een omschrijving die hier niet staat, is AMBIGUOUS_4712.
# --------------------------------------------------------------------------
CLASSIFICATION_4712 = {
    "Dakpan beton": ("SAFE_DAKPAN_REPORTED_AREA", "expliciet 'dakpan', materiaal beton"),
    "Dakpan keramisch": ("SAFE_DAKPAN_REPORTED_AREA", "expliciet 'dakpan', materiaal keramisch"),
    "dakpannen leisteen": ("OTHER_SLOPED_ROOF_MATERIAL", "bron zegt 'dakpannen', maar het materiaal is leisteen (natuursteen); "
                                                         "ander onderhoud dan beton-/keramische pannen — menselijke beoordeling"),
    "Dakbedekking shingles bitumen": ("OTHER_SLOPED_ROOF_MATERIAL", "bitumen shingles: geen dakpan"),
    "Dakbedekking zink": ("AMBIGUOUS_4712", "zink kan plat of hellend liggen; de bron zegt niet welk dakvlak"),
}

APP_SOURCE_METHOD = {  # zoals MJOP-App src/quantity.js autoFor() de bron behandelt (na Missingness Safety v1)
    "dakPlatM2": ("b3_opp_dak_plat", "DIRECT_MEASURED (3D_BAG)", "ROOF_FLAT_AREA",
                  "veld ontbreekt -> expliciete schatting BAG-grondvlak (ESTIMATED)"),
    "dakSchuinM2": ("b3_opp_dak_schuin", "DIRECT_MEASURED (3D_BAG)", "ROOF_SLOPED_AREA",
                    "veld ontbreekt -> NOT_AVAILABLE (nooit 0); aanwezige 0 = geldige 0"),
    "dakM2": ("b3_opp_dak_plat + b3_opp_dak_schuin", "GEOMETRY_DERIVED", "ROOF_TOTAL_AREA",
              "alleen als beide velden aanwezig zijn; één ontbreekt -> NOT_AVAILABLE; beide ontbreken -> grondvlak ESTIMATED"),
    "gevelM2": ("b3_opp_buitenmuur", "DIRECT_MEASURED (3D_BAG)", "OUTER_WALL_GROSS_AREA",
                "veld ontbreekt -> expliciete schatting omtrek x 3 x 3 (ESTIMATED); aanwezige 0 = geldige 0"),
    "units": ("BAG aantal_verblijfsobjecten", "BAG (of MANUAL)", None, "geen 3D BAG-veld"),
    "none": (None, "geen automatische hoeveelheid", None, "—"),
}

# Per app-element: inhoudelijk oordeel (handmatig vastgelegd, met reden). Categorie volgt uit dit oordeel.
ELEMENT_ASSESSMENT = {
    "dak-plat": ("READY_NOW", "ROOF_FLAT_AREA", "Plat dakoppervlak = 3D BAG b3_opp_dak_plat; XW-dak-plat-4711-m2 VERIFIED; echte bundels "
                 "Maldenhof en DOC-012 met historische context (ROOF_COVERING_REPORTED_AREA, RELATED_NOT_EQUIVALENT)."),
    "dak-hellend": ("READY_WITHOUT_HISTORICAL_CONTEXT", "ROOF_SLOPED_AREA", "Geometrie is direct 3D BAG b3_opp_dak_schuin en missing-safe; "
                    "historische context vraagt een apart onderwerp + smalle mapping (4712 is gemengd); XW-dak-hellend-4712-m2 staat op REVIEW_REQUIRED."),
    "dakinspectie": ("READY_WITHOUT_HISTORICAL_CONTEXT", "ROOF_TOTAL_AREA", "Vast bedrag + € per m² totaal dakoppervlak; 3D BAG-som plat + hellend "
                     "(GEOMETRY_DERIVED) alleen bij beide velden; geen historische 'totaal dak'-hoeveelheid."),
    "dakisolatie": ("NEEDS_SEMANTIC_MAPPING", "ROOF_TOTAL_AREA?", "Na-isoleren gaat over het te isoleren dakvlak; dat is niet zonder meer het "
                    "totale 3D BAG-dakoppervlak (bijv. alleen plat dak, of al geïsoleerde delen)."),
    "dakgoten": ("ESTIMATE_ONLY", None, "Rekent per appartement (BAG-aantal) als benadering van goten/HWA (m1); UNIT_MISMATCH in de crosswalk."),
    "gevel-metselwerk": ("NEEDS_SEMANTIC_MAPPING", None, "Gebruikt bruto buitenmuur (incl. ramen/deuren) als metselwerkoppervlak; de app toont dit "
                         "nu als bron '3D BAG' i.p.v. als benadering. Historisch 2110 is netto metselwerk: niet OUTER_WALL_GROSS_AREA."),
    "schilderwerk-buiten": ("ESTIMATE_ONLY", None, "Hele bruto buitenmuur als benadering (al als ESTIMATED gemarkeerd); schilderwerk gaat over "
                            "kozijnen/houtwerk (46xx), niet over muuroppervlak."),
    "kozijnen-onderhoud": ("ESTIMATE_ONLY", None, "Aantallen = appartementen x vaste factor (1 / 0,25 / 0,125 / 0,125); geen telling."),
    "steiger": ("READY_WITHOUT_HISTORICAL_CONTEXT", "OUTER_WALL_GROSS_AREA", "Steiger/hoogwerker per m² gevel: bruto buitenmuur (incl. openingen) "
                "is de passende maat; werkhoogte komt uit 3D BAG-hoogte (of standaard 9 m). Menselijke bevestiging van deze koppeling nodig."),
    "voegwerk": ("NEEDS_SEMANTIC_MAPPING", None, "Voegwerk gaat over metselwerk (netto, zonder openingen); bruto buitenmuur is een benadering."),
    "balkonhekken": ("ESTIMATE_ONLY", None, "Per appartement als benadering van hekwerk (m1)."),
    "intercom": ("ESTIMATE_ONLY", None, "Per appartement (BAG-aantal) als prijsbasis; geen hoeveelheidsonderwerp."),
    "riolering": ("ESTIMATE_ONLY", None, "Vast + per appartement als prijsbasis."),
    "elektra": ("ESTIMATE_ONLY", None, "Vast + per appartement als prijsbasis."),
    "verlichting": ("ESTIMATE_ONLY", None, "Per appartement als benadering van het aantal armaturen."),
    "waterleiding": ("ESTIMATE_ONLY", None, "Vast + per appartement als prijsbasis."),
    "brandveiligheid": ("ESTIMATE_ONLY", None, "Per appartement als prijsbasis."),
    "cv-installatie": ("ESTIMATE_ONLY", None, "Vast + per appartement als prijsbasis."),
    "ventilatie": ("ESTIMATE_ONLY", None, "Per appartement als prijsbasis."),
    "lift": ("NO_AUTOMATIC_QUANTITY", None, "bron 'none': vast bedrag."),
    "trappenhuis": ("ESTIMATE_ONLY", None, "Per appartement als benadering van trappenhuisoppervlak."),
    "vloerafwerking": ("ESTIMATE_ONLY", None, "Per appartement als benadering van vloeroppervlak."),
    "bestrating": ("ESTIMATE_ONLY", None, "Vast + per appartement als benadering van terreinoppervlak."),
    "fietsenstalling": ("ESTIMATE_ONLY", None, "Per appartement als prijsbasis."),
}

OUTER_WALL_USE = {
    "steiger": ("DIRECT_GEOMETRY_USE", "steiger/hoogwerker wordt per m² gevel geprijsd; bruto buitenmuur incl. openingen past"),
    "gevel-metselwerk": ("ESTIMATED_PROXY", "metselwerkherstel = netto metselwerk; bruto muur overschat (ramen, deuren, ander gevelmateriaal). "
                         "App toont nu bron '3D BAG', geen 'benadering'"),
    "voegwerk": ("ESTIMATED_PROXY", "voegwerk = netto metselwerk; bruto muur is benadering; crosswalk NOT_SAFE"),
    "schilderwerk-buiten": ("NOT_SAFE", "schilderwerk is kozijnen/houtwerk; al als ESTIMATED benadering gemarkeerd; crosswalk NOT_SAFE"),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inventory_4712(qos):
    rows, excluded = [], []
    for o in qos:
        el = o["element"]
        if el["element_code_internal"] != "4712":
            continue
        base = {"document_id": o["document_id"], "quantity_observation_id": o["quantity_observation_id"],
                "description": el.get("element_description_original"), "location": el.get("location_original"),
                "value": o.get("quantity_value"), "unit": o.get("unit_normalized"),
                "provenance": {"page": (o.get("provenance") or {}).get("page"), "block_id": (o.get("provenance") or {}).get("block_id"),
                               "text_fragment": (o.get("provenance") or {}).get("text_fragment")},
                "status": o.get("status"), "requires_human_review": o.get("requires_human_review"),
                "material_original": el.get("material_original"), "source_cluster": o.get("source_cluster"),
                "same_object_document_ids": (o.get("dependency") or {}).get("same_object_document_ids", [])}
        if o.get("unit_normalized") != "m2":
            excluded.append(dict(base, reason="eenheid " + str(o.get("unit_normalized")) + ": geen dakoppervlak (vorst, loodslab, dakrand)"))
            continue
        cls, why = CLASSIFICATION_4712.get(el.get("element_description_original"), ("AMBIGUOUS_4712", "omschrijving niet expliciet herkend"))
        if cls == "AMBIGUOUS_4712" and (el.get("location_original") or "").lower().find("lichtstraat") >= 0:
            why += "; locatie 'Dak lichtstraat'"
        rows.append(dict(base, classification=cls, classification_reason=why))
    return rows, excluded


def building_matrix(evidence, links, name, docs):
    confirmed = sorted({r["bag_pand_id"] for r in links["records"] if r["document_id"] in docs and r["status"] == "ACTIVE"
                        and r["link_status"] == "CONFIRMED"})
    bid = bqe.building_id_for(confirmed)
    ev_scope = [e for e in evidence["evidence"] if e["building_id"] == bid and e["source_type"] == "3D_BAG"]
    per_pand = [e for e in evidence["evidence"] if e["source_type"] == "3D_BAG" and e["building_id"] in {"BAG:" + p for p in confirmed}]
    hist = [e for e in evidence["evidence"] if e["building_id"] == bid and e["source_type"] == "MJOP_ELEMENT_OVERVIEW"]
    qos = json.loads(bqe.QO_PATH.read_text(encoding="utf-8"))["observations"]
    rows = []
    for k in SUBJECTS:
        scope_ev = next((e for e in ev_scope if e["quantity_subject"]["subject_key"] == k), None)
        pand_ev = [e for e in per_pand if e["quantity_subject"]["subject_key"] == k]
        if scope_ev is not None:
            value, method, complete, eid = scope_ev["value"], scope_ev["method_class"], True, scope_ev["evidence_id"]
        elif k == "BUILDING_HEIGHT":
            value = (pand_ev[0]["value"] if len(pand_ev) == 1 else f"per pand ({len(pand_ev)} waarden; niet opgeteld)")
            method, complete, eid = "GEOMETRY_DERIVED", len(pand_ev) == len(confirmed), (pand_ev[0]["evidence_id"] if len(pand_ev) == 1 else None)
        else:
            value, method, complete, eid = None, None, False, None
        hist_cand = [e for e in hist if e["quantity_subject"]["subject_key"] in bqe.related_subjects(
            json.loads(xw.SUBJECTS.read_text(encoding="utf-8")), k)]
        cand_rows, not_comparable = [], []
        if k == "ROOF_SLOPED_AREA":
            cand_rows = [o for o in qos if o["document_id"] in docs and o["element"]["element_code_internal"] == "4712"
                         and o["unit_normalized"] == "m2" and o["element"].get("element_description_original") in CLASSIFICATION_4712
                         and CLASSIFICATION_4712[o["element"]["element_description_original"]][0] == "SAFE_DAKPAN_REPORTED_AREA"]
        if k == "OUTER_WALL_GROSS_AREA":  # 2110 = netto metselwerk: uitdrukkelijk GEEN kandidaat (not_mapped)
            not_comparable = [o for o in qos if o["document_id"] in docs and o["element"]["element_code_internal"] == "2110" and o["unit_normalized"] == "m2"]
        rows.append({
            "subject": k, "available": value is not None, "value": value, "unit": "m" if k == "BUILDING_HEIGHT" else "m2",
            "source": "3D_BAG" if value is not None else None, "method_class": method, "complete": complete,
            "evidence_id": eid, "pand_count": len(confirmed), "child_values_present": len(pand_ev),
            "app_element_candidates": [key + ("?" if a[1].endswith("?") else "") for key, a in ELEMENT_ASSESSMENT.items()
                                       if a[1] and a[1].rstrip("?") == k],
            "historical_context_existing": [{"evidence_id": e["evidence_id"], "subject_key": e["quantity_subject"]["subject_key"],
                                             "value": e["value"], "document_id": e["source_ref"]["document_id"]} for e in hist_cand],
            "historical_context_candidates": [{"quantity_observation_id": o["quantity_observation_id"], "description": o["element"]["element_description_original"],
                                               "location": o["element"]["location_original"], "value": o["quantity_value"], "unit": o["unit_normalized"]}
                                              for o in cand_rows],
            "historical_not_comparable": [{"quantity_observation_id": o["quantity_observation_id"], "description": o["element"]["element_description_original"],
                                           "value": o["quantity_value"], "unit": o["unit_normalized"],
                                           "reason": "2110 netto metselwerk != bruto buitenmuur (not_mapped)"} for o in not_comparable],
        })
    return {"name": name, "document_ids": list(docs), "building_id": bid, "bag_pand_ids": confirmed, "subjects": rows}


def build():
    vocab = json.loads(xw.SUBJECTS.read_text(encoding="utf-8"))
    app_cw = json.loads(xw.APP_CROSSWALK.read_text(encoding="utf-8"))
    lib = json.loads(APP_LIBRARY.read_text(encoding="utf-8"))
    eff = xw.effective()
    qos = json.loads(bqe.QO_PATH.read_text(encoding="utf-8"))["observations"]
    evidence = json.loads(bqe.OUT_EVIDENCE.read_text(encoding="utf-8"))
    links = bl.load_store()
    inv, inv_excluded = inventory_4712(qos)

    coverage = []
    for d in lib["elements"]:
        field, method, subj, missing = APP_SOURCE_METHOD.get(d.get("bron") or "none", APP_SOURCE_METHOD["none"])
        cat, safe_subject, why = ELEMENT_ASSESSMENT[d["key"]]
        method_now = method
        if d.get("benadering"):
            method_now = "ESTIMATED (benadering van " + (field or "?") + ")"
        if d["type"] == "kozijnen":
            field, method_now, missing = "appartementen x vaste factor (KOZ_FACTOREN)", "ESTIMATED", "—"
        unit = {"dakPlatM2": "m2", "dakSchuinM2": "m2", "dakM2": "m2", "gevelM2": "m2", "units": "app"}.get(d.get("bron"), "st" if d["type"] == "kozijnen" else None)
        xws = [m["mapping_id"] + " (" + eff[m["mapping_id"]]["status"] + ")" for m in app_cw["mappings"] if m["app_element_key"] == d["key"]]
        unres = [u["reason"] for u in app_cw["unresolved"] if u.get("app_element_key") == d["key"]]
        coverage.append({"key": d["key"], "label": d["naam"], "type": d["type"], "bron": d.get("bron"), "unit": unit,
                         "auto_source_field": field, "auto_method": method_now, "subject_of_source": subj,
                         "safe_quantity_subject": safe_subject, "missingness_rule": missing, "crosswalk": xws, "crosswalk_unresolved": unres,
                         "category": cat, "assessment": why, "optional": bool(d.get("optioneel"))})
    by_cat = {c: sum(1 for r in coverage if r["category"] == c) for c in CATEGORIES}

    maldenhof = building_matrix(evidence, links, "Maldenhof", ("DOC-005", "DOC-006"))
    doc012 = building_matrix(evidence, links, "DOC-012 Meppelweg", ("DOC-012",))

    def sub(m, k):
        return next(r for r in m["subjects"] if r["subject"] == k)
    mald_sloped = sub(maldenhof, "ROOF_SLOPED_AREA")
    mald_tiles = [c for c in mald_sloped["historical_context_candidates"]]
    tiles_cmp = [{"quantity_observation_id": c["quantity_observation_id"], "historical_value": c["value"], "bag3d_value": mald_sloped["value"],
                  "difference": str(Decimal(c["value"]) - Decimal(mald_sloped["value"])),
                  "pct_of_3dbag": str(((Decimal(c["value"]) - Decimal(mald_sloped["value"])) / Decimal(mald_sloped["value"]) * 100).quantize(Decimal("0.1"))),
                  "kind": "RELATED_SUBJECT_NOT_EQUIVALENT (informatief, geen accuracy-claim)"} for c in mald_tiles] if mald_sloped["value"] else []

    xw_hellend = next(m for m in app_cw["mappings"] if m["mapping_id"] == "XW-dak-hellend-4712-m2")
    safe_rows = [r for r in inv if r["classification"] == "SAFE_DAKPAN_REPORTED_AREA"]
    res = json.loads(RESOLUTIONS.read_text(encoding="utf-8"))
    return {
        "report_version": "quantity_subject_expansion_review_v1",
        "note": ("Read-only readiness review. Geen VERIFY, geen relatie in de vocabulaire, geen bundel, geen resolutie. "
                 "Voorstellen staan alleen in dit rapport."),
        "inputs": {"app_element_library": {"path": str(APP_LIBRARY.relative_to(ROOT)), "sha256": sha(APP_LIBRARY), "source": lib["source"]},
                   "subjects_vocab_sha256": sha(xw.SUBJECTS), "app_crosswalk_sha256": sha(xw.APP_CROSSWALK),
                   "quantity_observations_sha256": sha(bqe.QO_PATH), "evidence_sha256": sha(bqe.OUT_EVIDENCE)},
        "A_coverage_summary": by_cat,
        "B_roof_sloped_area": {
            "bag3d_field": "b3_opp_dak_schuin", "rule": "bag3d.roof_sloped_area (DIRECT_MEASURED)", "app_element": "dak-hellend",
            "app_uses_same_source": True, "unit_equal": True,
            "missingness": APP_SOURCE_METHOD["dakSchuinM2"][3],
            "geometry_readiness": "READY_WITHOUT_HISTORICAL_CONTEXT",
            "xw_dak_hellend": {
                "mapping_id": xw_hellend["mapping_id"], "current_status": eff[xw_hellend["mapping_id"]]["status"],
                "what_it_maps": "app-element 'dak-hellend' (27.2, pannen) <-> interne code 4712 in m2, met quantity_subject ROOF_SLOPED_AREA",
                "A_element_code_link": ("NIET VEILIG zoals hij nu is: 4712 is gemengd (dakpan, leisteen, shingles, zink; plus m1-randen). "
                                        "Alleen veilig als de koppeling wordt beperkt tot expliciete dakpan-omschrijvingen "
                                        f"({sum(1 for r in inv if r['classification'] == 'SAFE_DAKPAN_REPORTED_AREA')} van {len(inv)} m2-regels)."),
                "B_quantity_subject_link": ("NIET EQUIVALENT: gerapporteerd pannenoppervlak (MJOP) is niet het geometrische hellende "
                                            "dakoppervlak (3D BAG): overstekken, dakkapellen, goten, gemengde materialen en meetwijze verschillen. "
                                            "Hoogstens RELATED_NOT_EQUIVALENT via een apart historisch onderwerp."),
                "conclusion": "A en B krijgen een verschillend oordeel; de bestaande mapping combineert ze en blijft dus REVIEW_REQUIRED.",
            },
            "maldenhof_comparison": tiles_cmp,
        },
        "proposed_historical_subject": {
            "status": "PROPOSAL_ONLY (niet in de vocabulaire)",
            "subject": {"subject_key": "ROOF_TILES_REPORTED_AREA", "unit": "m2", "quantity_kind": "ELEMENT_QUANTITY",
                        "method_class": "SOURCE_REPORTED", "label_nl": "Door bron/MJOP gerapporteerde oppervlakte dakpannen"},
            "why_not_sloped_roof_covering": ("Een breder 'hellend-dak-bedekking'-onderwerp zou shingles, leisteen en zink "
                                             "samennemen met pannen; het app-element 'dak-hellend' is uitdrukkelijk 'pannen'."),
            "relation": {"relation_id": "SREL-ROOF_TILES_REPORTED_AREA-ROOF_SLOPED_AREA (voorstel)", "subjects": ["ROOF_TILES_REPORTED_AREA", "ROOF_SLOPED_AREA"],
                         "relation": "RELATED_NOT_EQUIVALENT", "resolvable_as_same_quantity": False},
            "mapping_pattern": ("per document exact (document_ids + 4712 + m2 + omschrijving exact uit SAFE_DAKPAN_REPORTED_AREA), "
                                "zoals HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006"),
            "eligible_observations": [{"quantity_observation_id": r["quantity_observation_id"], "document_id": r["document_id"],
                                       "description": r["description"], "value": r["value"]} for r in safe_rows],
            "eligible_with_confirmed_building": [r["quantity_observation_id"] for r in safe_rows if r["document_id"] in ("DOC-005", "DOC-006")],
        },
        "C_roof_total_area": {
            "definition": "ROOF_FLAT_AREA + ROOF_SLOPED_AREA (bag3d.roof_total_area, GEOMETRY_DERIVED); app dakM2 alleen bij beide velden",
            "app_elements_using_total": [r["key"] for r in coverage if r["bron"] == "dakM2"],
            "historical_evidence": "geen: vocabulaire not_mapped ('Geen historische code voor totaal dakoppervlak; optellen van 4711 + 4712 zou aggregatie zijn')",
            "user_selectable_source_needed": False,
            "status": "INFRASTRUCTURE_ONLY",
            "reason": ("Gebruikt als basis voor 'dakinspectie' (vast + per m²) en 'dakisolatie'; er is geen historische totaalwaarde om naast te "
                       "zetten, dus geen bundel-/keuzefunctie nodig. Geen nieuw app-element."),
        },
        "D_outer_wall_gross_area": {
            "bag3d_field": "b3_opp_buitenmuur (bruto: openingen niet afgetrokken)", "app_source": "gevelM2",
            "per_app_element": [{"key": k, "use": v[0], "reason": v[1]} for k, v in OUTER_WALL_USE.items()],
            "historical": "2110 'Gevelconstructie metselwerk' is netto metselwerk — NIET OUTER_WALL_GROSS_AREA (vocabulaire not_mapped, ongewijzigd)",
            "status": "PARTIAL: alleen 'steiger' is een directe geometrische toepassing; overige gevelposten zijn benaderingen",
            "finding": ("'gevel-metselwerk' en 'voegwerk' tonen bruto buitenmuur als bron '3D BAG' (niet als benadering), terwijl "
                        "'schilderwerk-buiten' al 'benadering' is. Productkeuze, geen missing-as-zero-bug: niet gewijzigd in deze milestone."),
        },
        "E_building_height": {
            "definition": "b3_h_dak_max - b3_h_maaiveld (bag3d.building_height, GEOMETRY_DERIVED, per pand, niet opgeteld)",
            "app_use": "alleen als werkhoogte voor 'steiger' (tarief tot/boven 8 m); ontbreekt de hoogte, dan standaard 9 m (expliciete aanname)",
            "maintenance_quantity_in_m": False,
            "status": "CONTEXT_ONLY",
        },
        "F_4712_inventory": {"m2_rows": inv, "by_classification": dict(Counter(r["classification"] for r in inv)),
                             "excluded_non_m2_rows": excluded_summary(inv_excluded)},
        "G_app_coverage": coverage,
        "H_buildings": {"maldenhof": maldenhof, "doc012": doc012},
        "I_recommendations": [
            {"rank": 1, "activation": "ROOF_SLOPED_AREA-geometrie voor 'dak-hellend' (zonder historische context)",
             "why": "direct 3D BAG-veld, zelfde eenheid, missing-safe, bestaande pipeline/bundel v3, handmatig overschrijfbaar; "
                    "beide gebouwen hebben een complete waarde (Maldenhof 1415.57 m2 als scope-som, DOC-012 een gemeten 0.0)",
             "needs": ["menselijk besluit over XW-dak-hellend (zie J): de huidige 4712-brede koppeling is niet veilig"]},
            {"rank": 2, "activation": "historische dakpannen-context (ROOF_TILES_REPORTED_AREA, RELATED_NOT_EQUIVALENT) — eerst Maldenhof",
             "why": "Maldenhof DOC-005/DOC-006 'Dakpan beton / Hellend dak' 1485.60 m2 is expliciet; zelfde patroon als plat dak",
             "needs": ["subject + relatie goedkeuren", "document-specifieke mapping VERIFY", "smalle XW-koppeling"]},
            {"rank": 3, "activation": "OUTER_WALL_GROSS_AREA alleen voor 'steiger' (bruto gevel = steigeroppervlak)",
             "why": "enige gevelpost waar bruto buitenmuur de bedoelde maat is; geen historische context nodig",
             "needs": ["menselijke bevestiging dat steiger per m² bruto gevel geprijsd wordt",
                       "(apart) besluit of 'gevel-metselwerk'/'voegwerk' als benadering gemarkeerd moeten worden"]},
        ],
        "J_human_decisions": [
            "1. ROOF_TILES_REPORTED_AREA als nieuw historisch onderwerp + relatie RELATED_NOT_EQUIVALENT met ROOF_SLOPED_AREA: goedkeuren of afwijzen.",
            "2. XW-dak-hellend-4712-m2: REJECT (te breed) en vervangen door een smalle koppeling 'dak-hellend' <-> 4712 m2 alleen voor "
            "expliciete dakpan-omschrijvingen — of de bestaande laten staan op REVIEW_REQUIRED.",
            "3. Voor Maldenhof: document-specifieke mapping DOC-005/DOC-006 'Dakpan beton' / 'Hellend dak' (QO-DOC-005-EL-027, QO-DOC-006-EL-027) "
            "naar ROOF_TILES_REPORTED_AREA: VERIFY of REJECT.",
            "4. 'dakpannen leisteen' (DOC-002): telt leisteen als 'pannen' voor dak-hellend? (nu OTHER_SLOPED_ROOF_MATERIAL).",
            "5. ROOF_TOTAL_AREA: bevestigen als INFRASTRUCTURE_ONLY (geen keuzebron in de app).",
            "6. OUTER_WALL_GROSS_AREA: koppeling met 'steiger' bevestigen; besluiten of 'gevel-metselwerk' en 'voegwerk' als benadering "
            "(ESTIMATED) getoond moeten worden (MJOP-App-wijziging).",
            "7. BUILDING_HEIGHT: bevestigen als CONTEXT_ONLY.",
        ],
        "state": {
            "crosswalk_decisions": sorted(r["decision_id"] for r in xw.load_store()["records"]),
            "building_links": len(links["records"]),
            "quantity_resolutions": len(res["records"]),
            "bundles": {name: {"sha256": sha(BUNDLES / name), "unchanged": sha(BUNDLES / name) == h} for name, h in sorted(EXPECTED_BUNDLES.items())},
            "subject_relations_in_vocab": [r["relation_id"] for r in vocab["subject_relations"]],
        },
    }


def excluded_summary(rows):
    return [{"quantity_observation_id": r["quantity_observation_id"], "description": r["description"], "value": r["value"],
             "unit": r["unit"], "reason": r["reason"]} for r in rows]


def _v(x):
    return "—" if x is None or x == "" else str(x)


def render(r):
    L = ["# Quantity Subject Expansion Review v1 (read-only)", "", r["note"], "",
         f"App-elementenbibliotheek: `{r['inputs']['app_element_library']['path']}` (MJOP-App `{r['inputs']['app_element_library']['source']['ref'][:7]}`).", "",
         "## A. Huidige quantity coverage", "",
         "| Categorie | App-elementen |", "|---|---|"]
    L += [f"| {c} | {n} |" for c, n in r["A_coverage_summary"].items()]
    b = r["B_roof_sloped_area"]
    x = b["xw_dak_hellend"]
    L += ["", "## B. ROOF_SLOPED_AREA", "",
          f"- 3D BAG `{b['bag3d_field']}` ({b['rule']}); app-element `dak-hellend` gebruikt dezelfde bron en eenheid. Missingness: {b['missingness']}.",
          f"- Geometrie: **{b['geometry_readiness']}**.",
          f"- `{x['mapping_id']}` ({x['current_status']}) koppelt {x['what_it_maps']}.",
          f"  - A. element/code-koppeling: {x['A_element_code_link']}",
          f"  - B. quantity-koppeling: {x['B_quantity_subject_link']}",
          f"  - {x['conclusion']}"]
    if b["maldenhof_comparison"]:
        L += ["", "Maldenhof (informatief, RELATED_NOT_EQUIVALENT): " + "; ".join(
            f"{c['quantity_observation_id']} {c['historical_value']} m2 vs 3D BAG {c['bag3d_value']} m2 → {c['difference']} ({c['pct_of_3dbag']}%)"
            for c in b["maldenhof_comparison"]) + "."]
    p = r["proposed_historical_subject"]
    L += ["", f"**Voorstel ({p['status']}):** `{p['subject']['subject_key']}` — {p['subject']['label_nl']} ({p['subject']['unit']}, "
              f"{p['subject']['method_class']}); relatie `{p['relation']['relation']}` met ROOF_SLOPED_AREA. {p['why_not_sloped_roof_covering']} "
              f"Mapping: {p['mapping_pattern']}. In aanmerking: " + ", ".join(f"{e['quantity_observation_id']} ({e['value']} m2)" for e in p["eligible_observations"]) +
          f"; met bevestigd gebouw: {', '.join(p['eligible_with_confirmed_building']) or '—'}."]
    c = r["C_roof_total_area"]
    L += ["", "## C. ROOF_TOTAL_AREA", "", f"**{c['status']}** — {c['reason']}", f"- App-elementen op totaal dak: {', '.join(c['app_elements_using_total'])}.",
          f"- Historisch: {c['historical_evidence']}.", f"- Definitie: {c['definition']}."]
    d = r["D_outer_wall_gross_area"]
    L += ["", "## D. OUTER_WALL_GROSS_AREA", "", f"**{d['status']}**. Bron: {d['bag3d_field']} (`{d['app_source']}`).", "",
          "| App-element | Gebruik | Reden |", "|---|---|---|"]
    L += [f"| {e['key']} | {e['use']} | {e['reason']} |" for e in d["per_app_element"]]
    L += ["", f"- Historisch: {d['historical']}.", f"- Bevinding: {d['finding']}"]
    e = r["E_building_height"]
    L += ["", "## E. BUILDING_HEIGHT", "", f"**{e['status']}** — {e['definition']}. App: {e['app_use']}."]
    f = r["F_4712_inventory"]
    L += ["", "## F. 4712-inventaris (m2)", "", "Classificatie: " + ", ".join(f"{k} {v}" for k, v in sorted(f["by_classification"].items())) + ".", "",
          "| Observation | Document | Omschrijving | Locatie | Waarde | Pagina/blok | Klasse | Reden |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {x['quantity_observation_id']} | {x['document_id']} | {x['description']} | {_v(x['location'])} | {x['value']} {x['unit']} | "
          f"p.{x['provenance']['page']} {x['provenance']['block_id']} | {x['classification']} | {x['classification_reason']} |" for x in f["m2_rows"]]
    L += ["", f"Buiten beschouwing ({len(f['excluded_non_m2_rows'])} rijen in m1): " + ", ".join(
        f"{x['quantity_observation_id']} {x['description']}" for x in f["excluded_non_m2_rows"]) + "."]
    L += ["", "## G. App ELEMENT_LIBRARY coverage", "",
          "| Element | Bron | Methode nu | Veilig onderwerp | Categorie | Toelichting |", "|---|---|---|---|---|---|"]
    L += [f"| {x['key']} | {_v(x['bron'])} | {x['auto_method']} | {_v(x['safe_quantity_subject'])} | {x['category']} | {x['assessment']} |" for x in r["G_app_coverage"]]
    L += ["", "## H. Maldenhof / DOC-012", ""]
    for m in r["H_buildings"].values():
        L += [f"**{m['name']}** (`{m['building_id'][:60]}{'…' if len(m['building_id']) > 60 else ''}`, {len(m['bag_pand_ids'])} pand(en))", "",
              "| Onderwerp | Beschikbaar | Waarde | Methode | Compleet | App-kandidaat | Historische context |", "|---|---|---|---|---|---|---|"]
        for s in m["subjects"]:
            hc = [f"{h['subject_key']} {h['value']} ({h['document_id']})" for h in s["historical_context_existing"]] + \
                 [f"kandidaat {h['quantity_observation_id']} {h['description']} {h['value']} {h['unit']}" for h in s["historical_context_candidates"]] + \
                 [f"NIET vergelijkbaar: {h['quantity_observation_id']} {h['description']} {h['value']} {h['unit']}" for h in s["historical_not_comparable"]]
            L.append(f"| {s['subject']} | {'ja' if s['available'] else 'nee'} | {_v(s['value'])} | {_v(s['method_class'])} | "
                     f"{'ja' if s['complete'] else 'nee'} | {', '.join(s['app_element_candidates']) or '—'} | {'; '.join(hc) or '—'} |")
        L.append("")
    L += ["## I. Aanbevolen volgende activaties", ""]
    L += [f"{x['rank']}. **{x['activation']}** — {x['why']}. Nodig: {'; '.join(x['needs'])}." for x in r["I_recommendations"]]
    L += ["", "## J. Menselijke beslissingen", ""] + [f"- {x}" for x in r["J_human_decisions"]]
    st = r["state"]
    L += ["", f"Stand: crosswalk-besluiten {', '.join(st['crosswalk_decisions'])}; building links {st['building_links']}; "
              f"quantity resolutions {st['quantity_resolutions']}; bundels ongewijzigd: "
              + ", ".join(f"{k} {'ja' if v['unchanged'] else 'NEE'}" for k, v in st["bundles"].items()) + ".", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = build()
    js, md = json.dumps(r, ensure_ascii=False, indent=1) + "\n", render(r)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("subject expansion review up-to-date" if ok else "subject expansion review NIET up-to-date")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"coverage": r["A_coverage_summary"], "4712": r["F_4712_inventory"]["by_classification"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
