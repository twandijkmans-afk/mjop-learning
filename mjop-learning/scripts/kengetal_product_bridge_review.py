"""Kengetal Product Bridge Review v1 — read-only product/architectuurreview.

Hoe kan de officiële kengetallenbibliotheek veilig aan MJOP-App gekoppeld worden, zonder app-defaultprijzen als
historische of officiële kengetallen te presenteren? Er wordt niets geactiveerd: geen prijs vervangen, geen kengetal
AVAILABLE gemaakt, geen observation goedgekeurd, geen indexatie, geen besluit.

Invoer (alles lokaal, geen netwerk):
  data/kengetallen/kengetallen_batch1.json            ENIGE officiële kengetallenbron (niet data/kentallen/,
                                                      niet data/kengetallen/history/, niet compute_kentallen.py)
  data/comparability/comparability_batch1.json        price observations met eligibility/cluster/afgeleide prijs
  data/price_observations/…_normalized.json           omschrijving, prijspeil, btw
  reports/review/kengetal_readiness_v1.json           bestaande readiness per candidate group
  reports/pricing/inputs/mjop_app_price_inventory.json  prijsliteralen + codefeiten van MJOP-App (extract_app_price_inventory.py)
  vocabularies/app_element_crosswalk_v1.json + data/crosswalk_decisions/  (alleen verified codekoppelingen gelden als veilig)

De koppeltabel app-element -> verwante interne codes/actie/materiaal hieronder (ELEMENTS) is een expliciete REVIEW-
interpretatie: kandidaatcodes, geen crosswalk. Een codekoppeling geldt alleen als 'veilig' als er een VERIFIED
app-crosswalk-mapping met interne code bestaat.

Geen eenheidsconversie: m1 != m2 != app. (per appartement) != piece; geen omrekenfactor, geen schaalfactor.

    python scripts/kengetal_product_bridge_review.py [--check]
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crosswalk as xw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_KG = ROOT / "data" / "kengetallen" / "kengetallen_batch1.json"
NOT_OFFICIAL = ["data/kentallen/", "data/kengetallen/history/", "scripts/compute_kentallen.py"]
COMPARABILITY = ROOT / "data" / "comparability" / "comparability_batch1.json"
NORMALIZED = ROOT / "data" / "price_observations" / "price_observations_batch1_normalized.json"
READINESS = ROOT / "reports" / "review" / "kengetal_readiness_v1.json"
APP_PRICES = ROOT / "reports" / "pricing" / "inputs" / "mjop_app_price_inventory.json"
RESOLUTIONS = ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json"
QUANTITY_OBS = ROOT / "data" / "quantity_observations" / "quantity_observations_v1.json"
EVIDENCE = ROOT / "data" / "quantity_evidence" / "building_quantity_evidence_v1.json"
BUNDLES = ROOT / "reports" / "quantity" / "app_bundles"
OUT_JSON = ROOT / "reports" / "pricing" / "kengetal_product_bridge_review_v1.json"
OUT_MD = ROOT / "reports" / "pricing" / "kengetal_product_bridge_review_v1.md"

PRICE_SOURCE_CATEGORIES = ("OFFICIAL_INTERNAL_KENGETAL", "APP_DEFAULT_ESTIMATE", "FORMULA_DEFAULT", "IMPORTED_HISTORICAL_PRICE",
                           "OFFER_PRICE", "USER_OVERRIDE", "NO_PRICE")
MATCH_RESULTS = ("READY_FOR_KG_INTEGRATION", "KG_EXISTS_BUT_NOT_COMPATIBLE", "REVIEWABLE_KG_CANDIDATE", "NO_KG_AVAILABLE",
                 "FORMULA_PRICING_ONLY")
REVIEWABLE_READINESS = ("READY_AFTER_REVIEW", "MATERIAL_APPROVAL_NEEDED", "MATERIAL_AND_REVIEW_NEEDED")

# App-hoeveelheidsbron -> eenheid van de app-hoeveelheid (zoals Q.autoFor die zet)
BRON_UNIT = {"dakPlatM2": "m2", "dakSchuinM2": "m2", "dakM2": "m2", "gevelM2": "m2", "units": "app", "none": None}
BRON_LABEL = {"dakPlatM2": "3D BAG b3_opp_dak_plat (ROOF_FLAT_AREA)", "dakSchuinM2": "3D BAG b3_opp_dak_schuin (ROOF_SLOPED_AREA)",
              "dakM2": "3D BAG plat + schuin (ROOF_TOTAL_AREA)", "gevelM2": "3D BAG b3_opp_buitenmuur (OUTER_WALL_GROSS_AREA, bruto)",
              "units": "aantal appartementen (BAG verblijfsobjecten)", "none": "geen hoeveelheid (vast bedrag)", None: "per kozijnrij (schatting uit appartementen)"}

# REVIEW-interpretatie per app-element: verwante interne codes (kandidaat), passende interne acties, materiaal, en of de
# app-hoeveelheid semantisch de grootheid is waar een prijs per eenheid voor zou gelden.
ELEMENTS = {
    "dak-plat": (["4711"], ["replace", "install"], "dakbedekking plat dak (APP/bitumen, niet expliciet)", True,
                 "Hoeveelheid ROOF_FLAT_AREA is betrouwbaar (XW-dak-plat-4711-m2 VERIFIED)."),
    "dakgoten": (["5211", "2716"], ["replace", "repair", "maintain"], "goten/HWA (materiaal niet gespecificeerd)", True,
                 "App rekent per appartement; interne HWA/goten zijn m1 of piece."),
    "dakinspectie": ([], ["inspect", "maintain"], None, True, "Vast bedrag + per m² totaal dakoppervlak; geen inspectie-kengetal per m²."),
    "dak-hellend": (["4712"], ["replace"], "dakpannen", True,
                    "Hoeveelheid ROOF_SLOPED_AREA is betrouwbaar (XQ VERIFIED); XW-dak-hellend-4712-m2 blijft REVIEW_REQUIRED (4712 is gemengd)."),
    "dakisolatie": ([], ["install"], "isolatie", True, "Geen interne code voor dakisolatie."),
    "gevel-metselwerk": (["2110"], ["clean", "repair", "impregnate"], "metselwerk", False,
                         "App-hoeveelheid is bruto buitenmuur als benadering (ESTIMATED), geen metselwerkoppervlak."),
    "schilderwerk-buiten": (["4621", "4631"], ["exterior_painting"], "hout (kozijnen/gevelhoutwerk)", False,
                            "App-hoeveelheid is bruto buitenmuur als benadering; geschilderd oppervlak is veel kleiner."),
    "kozijnen-onderhoud": (["3120", "3122", "3131", "4631"], ["maintain", "exterior_painting", "repair"], "per kozijnrij (hout/alu/kunststof/staal)", True,
                           "Samengestelde prijs: aantal per kozijntype × tarief × materiaalfactor."),
    "steiger": (["9999"], ["scaffolding"], None, True, "Tarief per m² bruto buitenmuur naar werkhoogte; historisch alleen lump sums."),
    "voegwerk": (["4111", "2110"], ["repair", "repoint"], "metselwerk/voegwerk", False,
                 "App-hoeveelheid is bruto buitenmuur als benadering (ESTIMATED)."),
    "balkonhekken": (["3410"], ["replace", "exterior_painting", "repair"], "hekwerk/balustrade", True, "App rekent per appartement."),
    "intercom": (["6422"], ["replace"], None, True, "App rekent per appartement."),
    "riolering": (["5240", "5211"], ["clean", "repair", "replace"], None, True, "Vast bedrag + per appartement."),
    "elektra": (["6111"], ["replace", "inspect"], None, True, "Vast bedrag + per appartement."),
    "verlichting": (["6311"], ["replace"], None, True, "App rekent per appartement; intern piece (armaturen)."),
    "waterleiding": (["5310"], ["replace", "inspect"], None, True, "Vast bedrag + per appartement."),
    "brandveiligheid": (["6511", "6513"], ["replace", "inspect"], None, True, "App rekent per appartement."),
    "cv-installatie": ([], ["replace"], "ketel", True, "Geen interne code voor een collectieve ketel (5610 = stadsverwarmingleidingen)."),
    "ventilatie": (["5721"], ["replace"], None, True, "App rekent per appartement."),
    "lift": (["6611", "6612"], ["replace", "maintain"], None, True, "Alleen vast bedrag, geen hoeveelheid."),
    "trappenhuis": (["2410", "4211"], ["repair", "interior_painting"], None, True, "App rekent per appartement."),
    "vloerafwerking": (["4321", "4322"], ["replace", "repair"], None, True, "App rekent per appartement; intern m2."),
    "bestrating": (["9041"], ["repair", "replace"], None, True, "Vast bedrag + per appartement; intern m2."),
    "fietsenstalling": ([], ["repair"], None, True, "Geen interne code."),
}
# Semantisch oordeel bij een BESTAAND officieel kengetal op een verwante code (review-interpretatie, met reden)
KG_SEMANTICS = {
    ("dak-plat", "4711"): "Kengetal 4711 aluminium m1 gaat over daktrim/dakrandafwerking, niet over dakbedekking per m².",
    ("dakgoten", "5211"): "Kengetal 5211 pvc m1 gaat over hemelwaterafvoer per strekkende meter; de app rekent goten+HWA per appartement.",
    ("riolering", "5211"): "Kengetal 5211 pvc m1 is hemelwaterafvoer, geen binnenriolering; de app rekent per appartement.",
}
FORMULA_TYPES = ("vast-variabel", "steiger", "kozijnen")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def unit_compatible(app_unit, kg_unit):
    """Alleen exact dezelfde eenheid; geen conversie (m1 -> m2, app. -> m1, …) en geen schaalfactor."""
    return app_unit is not None and app_unit == kg_unit


def indexation_class(kg):
    pl = kg["price_levels"]
    per_cluster = pl["per_cluster"]
    if pl.get("missing_price_level") or any(v is None for vals in per_cluster.values() for v in vals):
        return "INDEXATION_NOT_POSSIBLE"
    if pl.get("mixed_price_level") or len(set(pl.get("years") or [])) > 1:
        return "INDEXATION_AMBIGUOUS"
    return "INDEXATION_READY"


def official_kgs(raw):
    out = []
    for k in raw["kengetallen"]:
        if k["status"] != "AVAILABLE":
            continue
        pl = k["price_levels"]
        out.append({
            "kengetal_id": k["kengetal_id"], "element_code": k["element_code"], "action": k["action"],
            "material": k["material"]["normalized"], "unit": k["unit"], "value_display": k["value_display"],
            "min_display": k["min_display"], "max_display": k["max_display"],
            "source_cluster_count": k["source_cluster_count"], "independent_source_clusters": len(set(k["source_cluster_ids"])),
            "source_cluster_ids": k["source_cluster_ids"],
            "price_levels_per_cluster": pl["per_cluster"], "price_level_years": pl.get("years"),
            "mixed_price_level": pl.get("mixed_price_level"), "missing_price_level": pl.get("missing_price_level"),
            "vat_basis": k["vat_basis"], "calculation_method": k["calculation_method"],
            "caveats": {"decision_caveats": (k.get("decision_caveats") or {}).get("counts", {}),
                        "observation_caveats": sorted({c for cs in (k.get("observation_caveats") or {}).values() for c in cs}),
                        "presentation_note": pl.get("presentation_note")},
            "object_descriptions": sorted({r.get("object_description") for r in k.get("source_references", []) if r.get("object_description")}),
            "indexation_readiness": indexation_class(k),
            "presentation": "historisch, niet geïndexeerd; geen actuele marktprijs, geen normprijs, geen prijspeil van één jaar",
        })
    return out


def price_inventory(app):
    p = app["snapshots"][-1]["prices"]
    facts = app["snapshots"][-1]["code_facts"]
    rows = []
    for d in p["element_library"]:
        unit = BRON_UNIT.get(d.get("bron"))
        ul = {"m2": "€/m²", "app": "€/appartement", None: "€"}.get(unit, "€")
        if d["type"] in ("dak", "gevel", "per-unit"):
            rows.append({"component": f"{d['key']}.kengetal", "value": d["kengetal"], "unit": ul, "app_element": d["key"],
                         "category": "APP_DEFAULT_ESTIMATE", "source": "hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil",
                         "user_editable": facts["kengetal_input_handler"], "user_edit_tracked": False,
                         "offer_can_replace": facts["offers_used_in_element_cost"], "provenance": None})
        if d["type"] == "vast-variabel":
            rows.append({"component": f"{d['key']}.basis", "value": d["basis"], "unit": "€ vast per beurt", "app_element": d["key"],
                         "category": "APP_DEFAULT_ESTIMATE", "source": "hardcoded ELEMENT_LIBRARY, geen bron/prijspeil",
                         "user_editable": facts["basis_or_per_eenheid_input_handler"], "user_edit_tracked": False,
                         "offer_can_replace": facts["offers_used_in_element_cost"], "provenance": None})
            no_qty = d.get("bron") == "none"
            rows.append({"component": f"{d['key']}.perEenheid", "value": d["perEenheid"], "unit": ul, "app_element": d["key"],
                         "category": "NO_PRICE" if no_qty else "APP_DEFAULT_ESTIMATE",
                         "source": "bron 'none': geen hoeveelheid, alleen vast bedrag" if no_qty else "hardcoded ELEMENT_LIBRARY, geen bron/prijspeil",
                         "user_editable": facts["basis_or_per_eenheid_input_handler"], "user_edit_tracked": False,
                         "offer_can_replace": facts["offers_used_in_element_cost"], "provenance": None})
    s = p["scaffold"]
    rows.append({"component": "steiger.tarief", "value": f"€ {s['rate_low_eur_per_m2']} (werkhoogte <= {s['height_threshold_m']} m) / € {s['rate_high_eur_per_m2']} (> {s['height_threshold_m']} m)",
                 "unit": "€/m² bruto buitenmuur", "app_element": "steiger", "category": "FORMULA_DEFAULT",
                 "source": "hardcoded tariefregel (MJOP-App src/quantity.js), sinds de eerste commit; geen bron",
                 "user_editable": False, "user_edit_tracked": False, "offer_can_replace": facts["offers_used_in_element_cost"],
                 "provenance": None, "note": "Alleen de werkhoogte (context) en de hoeveelheid zijn aanpasbaar, niet de tarieven."})
    for naam, tarief in p["koz_def"]:
        rows.append({"component": f"kozijnen.{naam}", "value": tarief, "unit": "€/stuk (houten kozijn, vóór materiaalfactor)",
                     "app_element": "kozijnen-onderhoud", "category": "APP_DEFAULT_ESTIMATE", "source": "hardcoded KOZ_DEF, geen bron",
                     "user_editable": facts["koz_eigen_tarief_handler"], "user_edit_tracked": True,
                     "offer_can_replace": facts["offers_used_in_element_cost"], "provenance": None})
    for mk, m in sorted(p["koz_materiaal"].items()):
        rows.append({"component": f"kozijnen.materiaalfactor.{mk}", "value": m["factor"], "unit": "factor op het houten tarief",
                     "app_element": "kozijnen-onderhoud", "category": "FORMULA_DEFAULT", "source": "hardcoded KOZ_MATERIAAL, geen bron",
                     "user_editable": False, "user_edit_tracked": False, "offer_can_replace": False, "provenance": None})
    rows += [
        {"component": "custom.bedrag (geïmporteerd oud MJOP)", "value": None, "unit": "€ per post", "app_element": "custom",
         "category": "IMPORTED_HISTORICAL_PRICE", "source": "MJOP-upload; prijspeil (basisjaar) door de gebruiker ingevuld",
         "user_editable": facts["custom_bedrag_and_basisjaar_handlers"], "user_edit_tracked": False, "offer_can_replace": False,
         "provenance": "document/regel bij import; geïndexeerd vanaf basisjaar" if facts["custom_costs_indexed_from_basisjaar"] else None},
        {"component": "offerte (per post)", "value": None, "unit": "€ per offerteregel", "app_element": "alle",
         "category": "OFFER_PRICE", "source": "handmatig ingevoerde offertes (state.offertes)",
         "user_editable": True, "user_edit_tracked": True, "offer_can_replace": False, "provenance": "door de gebruiker ingevoerd",
         "note": "Alleen tonen en vergelijken; komt NIET in elementCost." if not facts["offers_used_in_element_cost"] else "Gebruikt in elementCost."},
        {"component": "kengetal handmatig aangepast", "value": None, "unit": "zoals het element", "app_element": "dak/gevel/per-unit",
         "category": "USER_OVERRIDE", "source": "invoerveld 'Prijs per m²/unit' overschrijft el.kengetal",
         "user_editable": True, "user_edit_tracked": False, "offer_can_replace": False, "provenance": None,
         "note": "Overschrijft de default in place: na opslaan niet te onderscheiden van de default."},
        {"component": "kozijnen eigen tarief", "value": None, "unit": "€/stuk", "app_element": "kozijnen-onderhoud",
         "category": "USER_OVERRIDE", "source": "k.eigenTarief", "user_editable": True, "user_edit_tracked": True,
         "offer_can_replace": False, "provenance": "door de gebruiker ingevoerd (apart veld)"},
        {"component": "indexatie", "value": f"CBS {p['indexation']['cbs_table']} {p['indexation']['cbs_field']} (laatste jaarmutatie) of terugval {p['indexation']['fallback_rate_per_year']:.0%}/jaar",
         "unit": "%/jaar", "app_element": "custom", "category": "FORMULA_DEFAULT", "source": "CBS OData; vaste terugval 3%",
         "user_editable": False, "user_edit_tracked": False, "offer_can_replace": False, "provenance": "CBS-tabel (alleen jaarmutatie)",
         "note": "Alleen op custom/geïmporteerde posten; bibliotheekposten worden niet geïndexeerd."},
    ]
    for r in rows:
        assert r["category"] in PRICE_SOURCE_CATEGORIES
    return rows


def readiness_groups(readiness, codes):
    return [g for g in readiness["groups"] if g["element_code"] in codes]


def matrix(app, kgs, readiness, cw_eff):
    lib = app["snapshots"][-1]["prices"]["element_library"]
    safe_codes = {m["app_element_key"]: m["internal_element_code"] for m in load(xw.APP_CROSSWALK)["mappings"]
                  if m.get("internal_element_code") and cw_eff[m["mapping_id"]]["status"] == "VERIFIED"}
    rows = []
    for d in lib:
        codes, actions, material, qty_ok, note = ELEMENTS[d["key"]]
        app_unit = BRON_UNIT.get(d.get("bron")) if d["type"] != "kozijnen" else "piece"
        if d["type"] in ("dak", "gevel", "per-unit"):
            formula, values = "hoeveelheid × kengetal", {"kengetal": d["kengetal"]}
        elif d["type"] == "vast-variabel":
            formula, values = "basis + hoeveelheid × perEenheid", {"basis": d["basis"], "perEenheid": d["perEenheid"]}
        elif d["type"] == "steiger":
            formula, values = "hoeveelheid × tarief(werkhoogte) (per pand bij een scope)", {"tarief_laag": 6, "tarief_hoog": 11}
        else:
            formula, values = "Σ aantal × round(tarief × materiaalfactor) per kozijnrij", {"KOZ_DEF": "zie B"}
        kg_hits = [k for k in kgs if k["element_code"] in codes]
        checks = []
        for k in kg_hits:
            sem = KG_SEMANTICS.get((d["key"], k["element_code"]))
            checks.append({"kengetal_id": k["kengetal_id"], "unit_match": unit_compatible(app_unit, k["unit"]),
                           "action_match": k["action"] in actions,
                           "material_match": bool(material) and k["material"] is not None and k["material"] in (material or ""),
                           "semantic_match": sem is None and qty_ok, "semantic_reason": sem})
        groups = [g for g in readiness_groups(readiness, codes) if g["readiness"] != "AVAILABLE"]
        reviewable = [g for g in groups if unit_compatible(app_unit, g["unit"]) and g["action"] in actions
                      and (g["readiness"] in REVIEWABLE_READINESS or g["potential_source_clusters_after_steps"]["count"] >= 3)]
        if any(all((c["unit_match"], c["action_match"], c["material_match"], c["semantic_match"])) for c in checks):
            result = "READY_FOR_KG_INTEGRATION"
        elif checks:
            result = "KG_EXISTS_BUT_NOT_COMPATIBLE"
        elif reviewable and qty_ok:
            result = "REVIEWABLE_KG_CANDIDATE"
        elif d["type"] in FORMULA_TYPES:
            result = "FORMULA_PRICING_ONLY"
        else:
            result = "NO_KG_AVAILABLE"
        rows.append({
            "app_element_key": d["key"], "naam": d["naam"], "type": d["type"],
            "quantity_source": BRON_LABEL.get(d.get("bron")), "quantity_unit": app_unit, "quantity_is_proxy": not qty_ok,
            "price_formula": formula, "price_values": values,
            "internal_element_code_safe": safe_codes.get(d["key"]), "related_internal_codes_candidate": codes,
            "maintenance_actions": actions, "material": material,
            "official_kg_checks": checks,
            "price_candidate_groups": [{"candidate_group": g["candidate_group"], "readiness": g["readiness"], "unit": g["unit"],
                                        "unit_match": unit_compatible(app_unit, g["unit"]),
                                        "potential_source_clusters": g["potential_source_clusters_after_steps"]["count"]}
                                       for g in sorted(groups, key=lambda g: (-g["potential_source_clusters_after_steps"]["count"], g["candidate_group"]))],
            "result": result, "note": note,
        })
    return rows


def roof_readiness(code, comp, norm, readiness, kgs, material_terms):
    obs = []
    for o in comp["observations"]:
        if o["candidate_key"][0] != code or o["candidate_key"][2] != "m2":
            continue
        n = norm[o["observation_id"]]
        dp = o["derived_unit_price_per_execution"]
        desc = n["element"]["element_description_original"] or ""
        text = (desc + " " + (n["action"]["action_text_original"] or "")).lower()
        obs.append({"observation_id": o["observation_id"], "document_id": o["document_id"], "source_cluster": o["source_cluster"],
                    "action": o["candidate_key"][1], "description": desc, "action_text": n["action"]["action_text_original"],
                    "material_terms": sorted(t for t in material_terms if t in text),
                    "derived_price_per_m2": dp.get("value") if isinstance(dp, dict) else dp,
                    "price_level": n["price"]["price_level_date"], "vat_basis": n["price"]["vat_basis"],
                    "independent_input": o["independent_input"], "exclusion_reasons": o["independent_input_exclusion_reasons"]})
    covering = [x for x in obs if "grind" not in (x["action_text"] or "").lower()]
    def clusters(rows):
        return sorted({x["source_cluster"] for x in rows})
    return {
        "official_available_m2_kg": [k["kengetal_id"] for k in kgs if k["element_code"] == code and k["unit"] == "m2"],
        "observations_m2": obs,
        "observations_m2_count": len(obs),
        "source_clusters_all": clusters(obs),
        "source_clusters_independent_input": clusters([x for x in obs if x["independent_input"]]),
        "covering_lines_excluding_ballast_gravel": {"count": len(covering), "source_clusters": clusters(covering),
                                                    "by_action": {a: clusters([x for x in covering if (x["action"] or "onbekend") == a]) for a in sorted({x["action"] or "onbekend" for x in covering})},
                                                    "by_material_term": {t: clusters([x for x in covering if t in x["material_terms"]]) for t in sorted({t for x in covering for t in x["material_terms"]})}},
        "readiness_groups": [{"candidate_group": g["candidate_group"], "readiness": g["readiness"], "observations": g["observations"],
                              "independent_source_clusters": g["independent_source_clusters"]["count"],
                              "potential_source_clusters": g["potential_source_clusters_after_steps"]["count"]}
                             for g in readiness["groups"] if g["element_code"] == code and g["unit"] == "m2"],
    }


def build():
    raw_kg = load(OFFICIAL_KG)
    kgs = official_kgs(raw_kg)
    comp = load(COMPARABILITY)
    norm = {o["observation_id"]: o for o in load(NORMALIZED)["observations"]}
    readiness = load(READINESS)
    app = load(APP_PRICES)
    eff = xw.effective()
    facts = app["snapshots"][-1]["code_facts"]
    before = app["snapshots"][0]["code_facts"]
    inv = price_inventory(app)
    mtx = matrix(app, kgs, readiness, eff)
    flat = roof_readiness("4711", comp, norm, readiness, kgs, ("app", "bitumen", "ballast", "grind", "aluminium", "zink"))
    sloped = roof_readiness("4712", comp, norm, readiness, kgs, ("dakpan", "pannen", "beton", "keramisch", "leisteen", "shingles", "zink", "bitumen", "lood"))
    tiles_price_obs = [x for x in sloped["observations_m2"] if {"dakpan", "pannen"} & set(x["material_terms"])]
    tile_qos = sorted(o["quantity_observation_id"] for o in load(QUANTITY_OBS)["observations"]
                      if o["element"]["element_code_internal"] == "4712" and o["unit_normalized"] == "m2"
                      and "dakpan" in (o["element"].get("element_description_original") or "").lower()
                      and "leisteen" not in (o["element"].get("element_description_original") or "").lower())  # leisteen = ander materiaal
    steiger_obs = []
    for o in comp["observations"]:
        n = norm[o["observation_id"]]
        t = " ".join(filter(None, [n["element"]["element_description_original"], n["action"]["action_text_original"]])).lower()
        if "steiger" in t or "hoogwerker" in t:
            steiger_obs.append({"observation_id": o["observation_id"], "source_cluster": o["source_cluster"], "unit": n["unit"]["unit_original"],
                                "unit_normalized": n["unit"]["unit_normalized"], "eligibility": o["eligibility"], "description": n["element"]["element_description_original"]})
    coverage = defaultdict(list)
    for r in mtx:
        coverage[r["result"]].append(r["app_element_key"])
    bundle_hashes = {p.name: sha(p) for p in sorted(BUNDLES.glob("*.json"))}
    return {
        "report_version": "kengetal_product_bridge_review_v1",
        "scope": "read-only review; geen activatie, geen prijswijziging, geen nieuw kengetal, geen indexatie, geen besluit",
        "inputs": {"official_kengetallen": {"path": str(OFFICIAL_KG.relative_to(ROOT)), "sha256": sha(OFFICIAL_KG),
                                            "rules_version": raw_kg["rules_version"], "note": raw_kg["note"]},
                   "not_used_as_official": NOT_OFFICIAL,
                   "comparability_sha256": sha(COMPARABILITY), "normalized_observations_sha256": sha(NORMALIZED),
                   "readiness_report_sha256": sha(READINESS),
                   "app_price_inventory": {"path": str(APP_PRICES.relative_to(ROOT)), "sha256": sha(APP_PRICES),
                                           "reference_commit": app["reference_commit"], "latest_commit": app["latest_commit"],
                                           "price_values_identical_across_commits": app["price_values_identical_across_commits"]}},
        "A_official_kengetallen": {"available_count": len(kgs), "kengetallen": kgs,
                                   "other_statuses": sorted({k["status"] for k in raw_kg["kengetallen"]} - {"AVAILABLE"})},
        "B_app_price_inventory": {"components": inv,
                                  "by_category": {c: sum(1 for r in inv if r["category"] == c) for c in PRICE_SOURCE_CATEGORIES},
                                  "official_internal_kengetal_in_app": sum(1 for r in inv if r["category"] == "OFFICIAL_INTERNAL_KENGETAL"),
                                  "code_facts": facts},
        "C_app_element_kg_matrix": mtx,
        "D_flat_roof": dict(flat, conclusion=(
            "Geen officieel AVAILABLE m2-kengetal voor 4711. Het enige 4711-kengetal is aluminium daktrim in m1 en is niet "
            "koppelbaar aan dak-plat (m2). De dakbedekkingsregels (zonder grind) noemen APP en/of bitumen; één bron noemt beide "
            "in dezelfde regel (APP is in de bronnen een bitumineuze dakbedekking). Volgens de huidige regels is elke 4711 "
            "m2-groep INSUFFICIENT_CLUSTERS. Blokkades voor één generiek dak-plat-kengetal: (1) APP en bitumen: één "
            "materiaalfamilie of twee (menselijk materiaalbesluit); (2) 'aanbrengen nieuwe laag' (overlagen) versus 'vervangen' "
            "(incl. ballast) zijn verschillende acties; (3) ballast/grind is een aparte deelpost; (4) twee bronnen hebben "
            "eligibility UNKNOWN (actie niet genormaliseerd) en DOC-005/DOC-006 vormen samen één source cluster (mogelijk "
            "afhankelijk). De 'aanbrengen nieuwe laag'-regels raken na die besluiten potentieel de meeste clusters en zijn de "
            "meest kansrijke toekomstige kandidaat. Readiness: NIET klaar; geen kengetal gemaakt.")),
        "E_sloped_roof": dict(sloped, tile_price_observations=len(tiles_price_obs), tile_quantity_observations_without_price=tile_qos, conclusion=(
            "Geen enkele dakpan-prijsobservation (beton of keramisch): de 4712 m2-prijsregels zijn alleen shingles en zink uit één "
            "bron. De dakpanregels bestaan alleen als hoeveelheid (zie tile_quantity_observations_without_price), zonder prijsregel. "
            "Leisteen, shingles, zink en loodslabben blijven aparte materialen. Readiness: geen kandidaat mogelijk met de huidige "
            "data (0 onafhankelijke dakpan-clusters); niets samengevoegd op basis van code 4712.")),
        "F_scaffolding_price": {
            "app_rule": "€ 6/m² bruto buitenmuur bij werkhoogte <= 8 m, € 11/m² daarboven (per pand bij een scope)",
            "origin": "hardcoded sinds de eerste commits van MJOP-App (2026-09-19); geen bron, geen prijspeil",
            "category": "FORMULA_DEFAULT (tariefregel) met APP_DEFAULT_ESTIMATE-tarieven",
            "historical_observations": steiger_obs,
            "historical_per_m2_evidence": [x for x in steiger_obs if x["unit_normalized"] not in ("lump_sum", None)],
            "conclusion": ("Alle historische steigerposten zijn lump sums (pst) per project, zonder m² of hoogte: er is geen "
                           "historische onderbouwing voor € 6 of € 11 per m². OUTER_WALL_GROSS_AREA en BUILDING_HEIGHT zijn "
                           "betrouwbare hoeveelheid/context, maar dat maakt het tarief niet betrouwbaar. Geen tarief gewijzigd.")},
        "G_facade": {
            "elements": [{"app_element_key": r["app_element_key"], "quantity_uncertainty": "PROXY: bruto buitenmuur (ESTIMATED)",
                          "price_per_unit_uncertainty": "APP_DEFAULT_ESTIMATE (geen bron)",
                          "price_candidate_groups": r["price_candidate_groups"][:3]}
                         for r in mtx if r["app_element_key"] in ("gevel-metselwerk", "voegwerk", "schilderwerk-buiten")],
            "rule": ("Hoeveelheidsonzekerheid en prijs-per-eenheid-onzekerheid zijn twee aparte problemen: een goed kengetal per m² "
                     "maakt een proxy-hoeveelheid (bruto buitenmuur incl. ramen) niet goed. Historische 2110-hoeveelheden zijn geen "
                     "bruto buitenmuur en worden er niet aan gelijkgesteld. Eerst een eigen hoeveelheidsdefinitie (bijv. geschilderd "
                     "oppervlak, metselwerkoppervlak), daarna pas een kengetal.")},
        "H_offer_and_override_flow": {
            "as_implemented": [
                "Effectieve prijs per element = el.kengetal (default uit de bibliotheek, in place overschreven als de gebruiker het "
                "veld 'Prijs per m²/unit' aanpast; daarna niet meer te onderscheiden van de default).",
                "Kozijnen: k.eigenTarief (apart bewaard) gaat vóór round(tarief × materiaalfactor).",
                "Vast + variabel (basis/perEenheid) en steigertarieven hebben geen prijsinvoer: alleen hoeveelheid/werkhoogte zijn aanpasbaar.",
                "Geïmporteerde/eigen posten: el.bedrag + basisjaar, geïndexeerd naar het uitvoeringsjaar.",
                "Offertes worden per post opgeslagen, gelezen (Q.parseOfferteAmounts) en vergeleken, maar komen NIET in elementCost "
                "of de planning. Er is geen 'offerte accepteren'.",
            ],
            "effective_hierarchy_today": ["USER_OVERRIDE (kengetal in place / eigenTarief)", "APP_DEFAULT_ESTIMATE / FORMULA_DEFAULT",
                                          "(OFFER_PRICE: alleen weergave)"],
            "proposed_hierarchy_not_implemented": ["USER_OVERRIDE of geaccepteerde OFFER_PRICE", "OFFICIAL_INTERNAL_KENGETAL",
                                                   "APP_DEFAULT_ESTIMATE"],
            "conflicts": [
                "Een offerte heeft nu geen effect op de kosten; 'geaccepteerde offerte' bestaat nog niet (eerst productbesluit).",
                "Een aangepast kengetal verliest zijn herkomst (geen USER_OVERRIDE-markering, geen oude waarde bewaard).",
                "Offertevergelijking vult ontbrekende regels met het gemiddelde van de andere offertes (alleen weergave); bij "
                "integratie in kosten mag dat geen bron worden.",
                "Een offerte is een totaalbedrag per post (regels), een kengetal is een prijs per eenheid: koppelen vraagt een "
                "expliciete keuze (offerte vervangt de post, niet het kengetal).",
                "UI beweerde 'een offerte overschrijft het tarief' (onjuist): gecorrigeerd in MJOP-App 'Price Source Labels v1'.",
            ]},
        "I_indexation": {
            "app_logic": ("CBS 83547NED 'BestaandeWoningen' — alleen de LAATSTE jaarmutatie, als vast percentage samengesteld vanaf "
                          "basisjaar; terugval 3%/jaar. Alleen op custom/geïmporteerde posten; bibliotheekprijzen worden niet geïndexeerd."),
            "per_kg": [{"kengetal_id": k["kengetal_id"], "indexation_readiness": k["indexation_readiness"],
                        "price_levels_per_cluster": k["price_levels_per_cluster"]} for k in kgs],
            "rule": ("READY alleen als ALLE source clusters één bekend prijspeil hebben; gemengde prijspeilen = AMBIGUOUS; een "
                     "ontbrekend prijspeil = NOT_POSSIBLE. Nooit stil naar één jaar omrekenen. Ook bij READY is de huidige app-logica "
                     "(laatste jaarmutatie als vast percentage) geen exacte indexreeks."),
            "applied": False},
        "J_ui_source_labels": {
            "before": {k: before[k] for k in ("ui_claims_offer_overrides_tariff", "ui_claims_current_year_price_level", "ui_calls_defaults_kengetallen")},
            "after": {k: facts[k] for k in ("ui_claims_offer_overrides_tariff", "ui_claims_current_year_price_level", "ui_calls_defaults_kengetallen",
                                             "ui_price_note_says_app_estimate")},
            "misleading_spots_fixed": [
                "Overzicht 'Waar komen deze cijfers vandaan?': 'indicatieve richtprijzen (… prijspeil <huidig jaar>)' — het jaar schoof elk jaar mee zonder prijsbron.",
                "Printrapport 'Kosten.': idem 'prijspeil <huidig jaar>'.",
                "Voetnoten start/scherm: 'Kengetallen zijn indicatieve richtprijzen' — app-defaults heten nu app-schattingen.",
                "Kozijnen: 'een offerte overschrijft het tarief' — onjuist, offertes komen niet in de kosten.",
                "Vast + variabel per appartement toonde '12 m² × € 90' — nu '12 app. × € 90'.",
            ],
            "remaining_for_later": [
                "Het prijsinvoerveld 'Prijs per m²/unit' toont geen bronlabel (App-schatting / Intern kengetal / Offerte / Door gebruiker aangepast).",
                "Het herkomstlabel van een post volgt de HOEVEELHEID (bijv. '3D BAG'), niet de prijs; een aangepaste prijs wordt niet als 'Door gebruiker aangepast' getoond.",
            ],
            "fix_pr": "MJOP-App 'Price Source Labels v1' (geen prijswaarden gewijzigd)"},
        "K_coverage": {"by_result": {r: sorted(coverage.get(r, [])) for r in MATCH_RESULTS},
                       "counts": {r: len(coverage.get(r, [])) for r in MATCH_RESULTS},
                       "app_elements": len(mtx),
                       "priority_elements": [
                           {"app_element_key": "dak-plat", "why": "grootste bedragen (€ 165/m²), hoeveelheid betrouwbaar (ROOF_FLAT_AREA), "
                            "meeste 4711 m2-prijsregels (meerdere clusters), semantiek redelijk helder; vraagt alleen menselijke groepsbesluiten."},
                           {"app_element_key": "schilderwerk-buiten", "why": "hoogste frequentie (6 jaar) en de sterkste prijsdata (4621/4631 "
                            "buitenschilderwerk hout m2, 6–7 potentiële clusters), maar eerst een eigen hoeveelheidsdefinitie (geen bruto buitenmuur)."},
                           {"app_element_key": "kozijnen-onderhoud", "why": "grote post met prijs per stuk; interne kozijn-/schilderwerkdata bestaat "
                            "maar per stuk/m1 en met materiaal; vraagt een stuks-hoeveelheid die nu een schatting is."},
                           {"app_element_key": "dakgoten", "why": "officieel kengetal 5211 pvc m1 bestaat al, maar de app rekent per appartement: "
                            "pas bruikbaar met een m1-hoeveelheid (nu geen bron; geen nieuwe subjects in deze stap)."},
                       ]},
        "L_next_price_milestones": [
            {"name": "Price Source Model v1 (MJOP-App)", "what": "prijsobject per post naast het hoeveelheidsobject: bron (APP_DEFAULT_ESTIMATE / "
             "OFFICIAL_INTERNAL_KENGETAL / OFFER_PRICE / USER_OVERRIDE), oude waarde bewaren bij aanpassen, bronlabel in de UI; nog geen "
             "kengetal-waarden activeren."},
            {"name": "Flat Roof Price Group Review (mjop-learning)", "what": "besluitpakket voor de 4711 m2-regels: APP vs bitumen, "
             "overlagen vs vervangen, ballast/grind apart, eligibility DOC-011/DOC-012, afhankelijkheid DOC-005/006 — doel: een eerste "
             "m2-kengetal-kandidaat voor dak-plat (niet automatisch AVAILABLE)."},
            {"name": "Offer Acceptance Decision (product)", "what": "beslissen of en hoe een geaccepteerde offerte de kosten van een post "
             "vervangt (totaal per post, niet per eenheid), inclusief prijspeil/indexatie van offertes."},
        ],
        "M_human_decisions_needed": [
            "Prijsbronhiërarchie: USER_OVERRIDE/geaccepteerde OFFER_PRICE > OFFICIAL_INTERNAL_KENGETAL > APP_DEFAULT_ESTIMATE — akkoord?",
            "Mag een geaccepteerde offerte de kosten van een post vervangen (totaal per post), en wat is dan het prijspeil?",
            "Indexatiebeleid voor kengetallen met ontbrekende/gemengde prijspeilen: niet tonen, of ongeïndexeerd tonen met caveat?",
            "4711 dakbedekking: is APP een eigen materiaal of een bitumen-subtype? Zijn 'aanbrengen nieuwe laag' en 'vervangen' één actie of twee?",
            "4711: ballast/grind-regels als aparte deelpost uitsluiten van een dakbedekkingskengetal?",
            "Steigertarief € 6/€ 11: als app-schatting behouden en zo labelen, of een bron zoeken?",
            "Gevel: eerst een eigen hoeveelheidsdefinitie (geschilderd oppervlak / metselwerkoppervlak) vóór een gevel-kengetal?",
            "Moeten basis/perEenheid (vast + variabel) door de gebruiker aanpasbaar worden?",
        ],
        "state_unchanged": {
            "official_kengetallen_sha256": sha(OFFICIAL_KG),
            "quantity_bundles_sha256": bundle_hashes,
            "crosswalk_decisions": sorted(r["decision_id"] for r in xw.load_store()["records"]),
            "crosswalk_decisions_sha256": sha(xw.DECISIONS),
            "quantity_evidence_sha256": sha(EVIDENCE),
            "quantity_resolutions": len(load(RESOLUTIONS)["records"]),
            "app_price_values_identical": app["price_values_identical_across_commits"],
        },
    }


def _num(x):
    return "—" if x is None else str(x)


def render(r):
    L = ["# Kengetal Product Bridge Review v1", "", r["scope"] + ".", "",
         f"Officiële bron: `{r['inputs']['official_kengetallen']['path']}` (niet: {', '.join(r['inputs']['not_used_as_official'])}). "
         f"App-prijzen: MJOP-App `{r['inputs']['app_price_inventory']['reference_commit'][:7]}` en `{r['inputs']['app_price_inventory']['latest_commit'][:7]}` "
         f"(prijswaarden identiek: {'ja' if r['inputs']['app_price_inventory']['price_values_identical_across_commits'] else 'NEE'}).", ""]
    a = r["A_official_kengetallen"]
    L += [f"## A. Officiële kengetallen ({a['available_count']} AVAILABLE)", "",
          "Historisch, niet geïndexeerd; geen actuele marktprijs, geen normprijs, geen prijspeil van één jaar.", "",
          "| kengetal | code | actie | materiaal | eenheid | waarde | min–max | clusters | prijspeilen per cluster | btw | indexatie |",
          "|---|---|---|---|---|---:|---|---:|---|---|---|"]
    for k in a["kengetallen"]:
        pl = "; ".join(f"{c}: {', '.join(_num(v) for v in vs)}" for c, vs in k["price_levels_per_cluster"].items())
        L.append(f"| {k['kengetal_id']} | {k['element_code']} | {k['action']} | {k['material']} | {k['unit']} | {k['value_display']} | "
                 f"{k['min_display']}–{k['max_display']} | {k['independent_source_clusters']} | {pl} | {', '.join(k['vat_basis'])} | {k['indexation_readiness']} |")
    L += [""] + [f"- `{k['kengetal_id']}`: {k['calculation_method']}. Caveats: {k['caveats']['decision_caveats'] or '—'}; objecten: {', '.join(k['object_descriptions'])}." for k in a["kengetallen"]] + [""]
    b = r["B_app_price_inventory"]
    L += ["## B. App-prijsinventaris", "", "Per categorie: " + ", ".join(f"{c} {n}" for c, n in b["by_category"].items() if n) +
          f". OFFICIAL_INTERNAL_KENGETAL in de app: {b['official_internal_kengetal_in_app']}.", "",
          "| component | waarde | eenheid | categorie | aanpasbaar | aanpassing herleidbaar | offerte vervangt | bron |", "|---|---|---|---|---|---|---|---|"]
    for c in b["components"]:
        L.append(f"| {c['component']} | {_num(c['value'])} | {c['unit']} | {c['category']} | {'ja' if c['user_editable'] else 'nee'} | "
                 f"{'ja' if c['user_edit_tracked'] else 'nee'} | {'ja' if c['offer_can_replace'] else 'nee'} | {c['source']} |")
    L += ["", "## C. App-element × kengetal", "",
          "| app-element | hoeveelheid (eenheid) | formule | prijs | veilige code | kandidaatcodes | officieel KG (unit/actie/materiaal/semantiek) | beste prijsgroep | resultaat |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in r["C_app_element_kg_matrix"]:
        kg = "; ".join(f"{c['kengetal_id']} ({'✓' if c['unit_match'] else '✗'}/{'✓' if c['action_match'] else '✗'}/{'✓' if c['material_match'] else '✗'}/{'✓' if c['semantic_match'] else '✗'})"
                       for c in m["official_kg_checks"]) or "—"
        g = m["price_candidate_groups"][0] if m["price_candidate_groups"] else None
        gs = f"{g['candidate_group']} ({g['readiness']}, {g['potential_source_clusters']} cl., unit {'=' if g['unit_match'] else '≠'})" if g else "—"
        L.append(f"| {m['app_element_key']} | {m['quantity_source']} ({_num(m['quantity_unit'])}){' — proxy' if m['quantity_is_proxy'] else ''} | {m['price_formula']} | "
                 f"{', '.join(f'{k}={v}' for k, v in m['price_values'].items())} | {_num(m['internal_element_code_safe'])} | {', '.join(m['related_internal_codes_candidate']) or '—'} | {kg} | {gs} | **{m['result']}** |")
    for key, title in (("D_flat_roof", "D. Plat dak (4711, m2)"), ("E_sloped_roof", "E. Hellend dak (4712, m2)")):
        d = r[key]
        L += ["", f"## {title}", "", f"- Officieel AVAILABLE m2-kengetal: {d['official_available_m2_kg'] or 'geen'}.",
              f"- Prijsregels m2: {d['observations_m2_count']} in clusters {', '.join(d['source_clusters_all']) or '—'}; als onafhankelijke invoer: {', '.join(d['source_clusters_independent_input']) or '—'}.",
              "- Dakbedekkingsregels (zonder grind) per actie: " + "; ".join(f"{a}: {', '.join(c) or '—'}" for a, c in d["covering_lines_excluding_ballast_gravel"]["by_action"].items()) + ".",
              "- Per materiaalterm in de tekst: " + ("; ".join(f"{t}: {', '.join(c)}" for t, c in d["covering_lines_excluding_ballast_gravel"]["by_material_term"].items()) or "—") + ".",
              f"- Readiness-groepen: " + ("; ".join(f"{g['candidate_group']} {g['readiness']} ({g['potential_source_clusters']} clusters)" for g in d["readiness_groups"]) or "—") + ".", "",
              "| observation | cluster | actie | omschrijving / actietekst | €/m² | prijspeil | onafhankelijk |", "|---|---|---|---|---:|---|---|"]
        for o in d["observations_m2"]:
            L.append(f"| {o['observation_id']} | {o['source_cluster']} | {o['action']} | {o['description']} / {o['action_text']} | {o['derived_price_per_m2']} | {_num(o['price_level'])} | {'ja' if o['independent_input'] else 'nee: ' + ', '.join(o['exclusion_reasons'])} |")
        if "tile_quantity_observations_without_price" in d:
            L += ["", f"Dakpan-prijsregels: {d['tile_price_observations']}. Dakpanregels met alleen een hoeveelheid: {', '.join(d['tile_quantity_observations_without_price'])}."]
        L += ["", d["conclusion"]]
    f = r["F_scaffolding_price"]
    L += ["", "## F. Steiger-prijsbron", "", f"- Regel: {f['app_rule']}.", f"- Herkomst: {f['origin']}. Categorie: {f['category']}.",
          f"- Historisch: {len(f['historical_observations'])} steiger-/hoogwerkerposten, eenheden {sorted({x['unit'] for x in f['historical_observations']})}; per-m²-onderbouwing: {len(f['historical_per_m2_evidence'])}.",
          "", f["conclusion"]]
    g = r["G_facade"]
    L += ["", "## G. Gevel: hoeveelheid versus prijs per eenheid", ""] + \
         [f"- `{e['app_element_key']}`: hoeveelheid {e['quantity_uncertainty']}; prijs {e['price_per_unit_uncertainty']}; prijsgroepen: "
          + (", ".join(f"{x['candidate_group']} ({x['readiness']})" for x in e["price_candidate_groups"]) or "—") for e in g["elements"]] + ["", g["rule"]]
    h = r["H_offer_and_override_flow"]
    L += ["", "## H. Offerte- en override-flow", ""] + [f"- {x}" for x in h["as_implemented"]] + \
         ["", "Werkelijke hiërarchie nu: " + " > ".join(h["effective_hierarchy_today"]) + ".",
          "Voorstel (niet geïmplementeerd): " + " > ".join(h["proposed_hierarchy_not_implemented"]) + ".", "", "Conflicten:"] + [f"- {x}" for x in h["conflicts"]]
    i = r["I_indexation"]
    L += ["", "## I. Indexatie", "", i["app_logic"], ""] + [f"- `{k['kengetal_id']}`: **{k['indexation_readiness']}**" for k in i["per_kg"]] + ["", i["rule"]]
    j = r["J_ui_source_labels"]
    L += ["", "## J. UI-bronlabels", "", "Aantoonbaar misleidend (opgelost in " + j["fix_pr"] + "):"] + [f"- {x}" for x in j["misleading_spots_fixed"]] + \
         ["", "Nog te doen (geen kleine fix):"] + [f"- {x}" for x in j["remaining_for_later"]]
    k = r["K_coverage"]
    L += ["", "## K. Dekking", "", f"{k['app_elements']} app-elementen:"] + [f"- {res}: {n} — {', '.join(k['by_result'][res]) or '—'}" for res, n in k["counts"].items()] + \
         ["", "Prioriteit voor een echt intern kengetal (geen score):"] + [f"{n}. `{p['app_element_key']}` — {p['why']}" for n, p in enumerate(k["priority_elements"], 1)]
    L += ["", "## L. Volgende 3 prijs-milestones", ""] + [f"{n}. **{x['name']}** — {x['what']}" for n, x in enumerate(r["L_next_price_milestones"], 1)]
    L += ["", "## M. Menselijke beslissingen", ""] + [f"- {x}" for x in r["M_human_decisions_needed"]]
    s = r["state_unchanged"]
    L += ["", "## Ongewijzigd", "", f"- Officiële kengetallen sha256 `{s['official_kengetallen_sha256']}`.",
          f"- Crosswalk-besluiten {', '.join(s['crosswalk_decisions'])}; quantity resolutions {s['quantity_resolutions']}; app-prijswaarden identiek: {'ja' if s['app_price_values_identical'] else 'NEE'}.",
          "- Bundels: " + ", ".join(f"{n} `{h[:12]}`" for n, h in s["quantity_bundles_sha256"].items()) + ".", ""]
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
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(f"-> {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
