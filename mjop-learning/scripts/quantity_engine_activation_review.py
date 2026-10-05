"""Quantity Engine Activation Review v1 — read-only bronnenvergelijking voor één echt gebouw (Maldenhof).

ANALYSE-/REVIEWSCRIPT. Beslist niets en schrijft niets in data/: geen building links, geen crosswalk-besluiten,
geen evidence, geen resoluties. Geen netwerk, geen API. Schrijft alleen:
    reports/quantity/quantity_engine_activation_review_v1.json
    reports/quantity/quantity_engine_activation_review_v1.md

Leest (read-only) de bestaande foundations en hergebruikt hun code:
    data/quantity_observations/quantity_observations_v1.json         (662 observations)
    reports/quantity/building_link_candidates_v1.json                 (opvraagplan, relaties)  via building_links
    vocabularies/quantity_subjects_v1.json + app_element_crosswalk_v1.json + crosswalk-besluiten  via crosswalk
    scripts/bag3d_quantity_rules.py                                   (3D BAG-regels, exact Decimal)
    data/building_links/building_link_records.json                    (moet leeg blijven)
    reports/quantity/facade_poc_v2_run/inputs/maldenhof_DOC-005-006/  (PoC-snapshot: 3D BAG + BAG-VBO, sha256)
    reports/quantity/facade_poc_v2_run/bag_panden_bbox.json           (BAG OGC pand-respons rond het complex)

Alle 3D BAG-waarden in dit rapport zijn een PREVIEW van wat de bestaande regels zouden opleveren; het zijn
GEEN evidence-records. Sommen over panden zijn alleen informatief (de pipeline telt bewust niet op).

    python scripts/quantity_engine_activation_review.py [--check]
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bag3d_quantity_rules as rules_mod  # noqa: E402
import bag_snapshots as bs  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("DOC-005", "DOC-006")
QO_PATH = ROOT / "data" / "quantity_observations" / "quantity_observations_v1.json"
CANDIDATES = ROOT / "reports" / "quantity" / "building_link_candidates_v1.json"
SNAP = ROOT / "reports" / "quantity" / "facade_poc_v2_run" / "inputs" / "maldenhof_DOC-005-006"
BBOX = ROOT / "reports" / "quantity" / "facade_poc_v2_run" / "bag_panden_bbox.json"
OUT_JSON = ROOT / "reports" / "quantity" / "quantity_engine_activation_review_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "quantity_engine_activation_review_v1.md"
REPORT_VERSION = "quantity_engine_activation_review_v1"

# MJOP-App: feit uit de default branch (gelezen, niet uitgevoerd). Zie MJOP-App src/quantity.js bundleEntries.
MJOP_APP = {
    "repository": "twandijkmans-afk/MJOP-App",
    "default_branch": "claude/mjop-live-implementation-smz60g",
    "commit": "fbe09d887244ab3ae3ddc83c6c32d9545ad34e34",
    "quantity_sources_v1": "aanwezig (PR #2, merge fbe09d8)",
    "bundle_rule": "src/quantity.js bundleEntries: een bundel met bag_pand_ids.length !== 1 wordt geweigerd "
                   "('De bundel gaat over N panden; de app werkt per pand.'); het pand moet gelijk zijn aan het pand van het plan.",
    "dak_plat_auto_source": "src/app.js lookupBuilding: dak-plat gebruikt 3D BAG b3_opp_dak_plat van één pand (adres-lookup)",
}

NOT_GROUND_TRUTH_ROWS = {"3120": "Kozijn buiten hout", "4631": "Buitenschilderwerk kozijn hout dekkend"}
LABEL_756 = "NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY"


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def sha_bytes(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# A — inputs
# --------------------------------------------------------------------------

def inputs_review():
    src = load(SNAP / "SOURCE.json")
    pkg = load(SNAP / "candidates" / "DOC-005-006.json")
    (hyp,) = pkg["building_project_candidate"]["scope_hypotheses"]
    cand = {c["bag_pand_id"]: c for c in pkg["candidate_panden"]}
    sha_ok = {f["path"]: sha_bytes(SNAP / f["path"]) == f["sha256"] for f in src["copied_raw_files"]}
    bbox = load(BBOX)
    bag_feat = {f["properties"]["identificatie"]: f for f in bbox["features"]}

    panden = []
    for pid in sorted(hyp["bag_pand_ids"]):
        vbos = []
        for f in sorted((SNAP / "raw" / "pdok").glob(f"bag-pand-{pid}__bag-vbo__*.json")):
            v = load(f)
            p = v["properties"]
            lon, lat = v["geometry"]["coordinates"]
            feat = bag_feat.get(pid)
            inside = None
            if feat:
                inside = any(bs.point_in_ring(r, lon, lat) for r in bs.outer_rings(feat["geometry"]))
            vbos.append({"huisnummer": p["huisnummer"], "huisletter": p.get("huisletter"), "toevoeging": p.get("toevoeging"),
                         "postcode": p["postcode"], "vbo_id": p["identificatie"], "status": p["status"],
                         "gebruiksdoel": p["gebruiksdoel"], "oppervlakte_m2": p["oppervlakte"],
                         "point_in_bag_pand_polygon": inside,
                         "raw_file": f"raw/pdok/{f.name}", "raw_sha256_ok": sha_ok.get(f"raw/pdok/{f.name}")})
        vbos.sort(key=lambda v: (int(v["huisnummer"]), v["huisletter"] or "", v["toevoeging"] or ""))
        c = cand[pid]
        raw_rel = c["threedbag"]["raw_response_path"]
        raw = load(SNAP / raw_rel)
        attrs = ((raw.get("feature") or {}).get("CityObjects") or {}).get(f"NL.IMBAG.Pand.{pid}", {}).get("attributes")
        props = (bag_feat.get(pid) or {}).get("properties") or {}
        panden.append({
            "bag_pand_id": pid,
            "addresses": [f"Maldenhof {v['huisnummer']}{v['huisletter'] or ''}{('-' + v['toevoeging']) if v['toevoeging'] else ''}" for v in vbos],
            "vbo": vbos,
            "bag_properties": {k: props.get(k) for k in ("status", "bouwjaar", "aantal_verblijfsobjecten", "gebruiksdoel")},
            "threedbag": {"raw_file": raw_rel, "file_sha256": c["threedbag"]["raw_response_sha256"],
                          "file_sha256_ok": sha_ok.get(raw_rel),
                          "canonical_sha256_bag_snapshot_convention": canonical_sha256(raw),
                          "fetched_at": "NOT_RECORDED_IN_MAIN_SNAPSHOT", "has_attributes": bool(attrs)},
            "_attributes": attrs,
        })
    numbers = sorted(int(v["huisnummer"]) for p in panden for v in p["vbo"])
    even_range = list(range(240, 297, 2))
    all_range = list(range(240, 297))
    odd = sorted(set(cand) - set(hyp["bag_pand_ids"]))
    contract_mismatch = [
        {"field": "requests[] + raw PDOK Locatieserver 'free' respons",
         "canonical": "verplicht (bag_snapshot_v1: elke request + ruwe respons, exacte adresmatch)",
         "poc_snapshot": "ontbreekt (adressen staan alleen als afgeleide lijst addresses_found)"},
        {"field": "BAG OGC pand-items per adrespunt (bbox rond het adres) + punt-in-polygoon",
         "canonical": "verplicht; bepaalt welke panden kandidaat zijn",
         "poc_snapshot": "niet per adres; wel één bbox-respons rond het hele complex (bag_panden_bbox.json, zonder request-URL/sha in een snapshot)"},
        {"field": "3D BAG-respons per pand", "canonical": "ruwe respons + canonical_sha256 + url + fetched_at + api_version",
         "poc_snapshot": "ruwe respons + bestands-sha256 (andere hash-conventie); fetched_at en url niet vastgelegd op main"},
        {"field": "snapshot_id (BAGSNAP-…)", "canonical": "content-addressed per (document, adres-query)",
         "poc_snapshot": "geen; één snapshot voor het hele complex en beide documenten"},
        {"field": "document_id", "canonical": "één document per snapshot", "poc_snapshot": "groep DOC-005-006"},
    ]
    return {
        "source_manifest": "reports/quantity/facade_poc_v2_run/inputs/maldenhof_DOC-005-006/SOURCE.json",
        "source_status": src["status"],
        "raw_files": len(sha_ok), "raw_files_sha256_ok": sum(sha_ok.values()),
        "bag_panden_in_scope": len(panden), "vbo_count": sum(len(p["vbo"]) for p in panden),
        "addresses_numbers": numbers,
        "addresses_equal_even_240_296": numbers == even_range,
        "even_numbers_in_range": len(even_range), "all_numbers_in_range": len(all_range),
        "panden_by_vbo_count": dict(sorted(Counter(len(p["vbo"]) for p in panden).items())),
        "vbo_points_inside_own_pand_polygon": sum(1 for p in panden for v in p["vbo"] if v["point_in_bag_pand_polygon"]),
        "other_candidate_panden_odd_side": odd,
        "panden": panden,
        "canonical_snapshot_contract": "bag_snapshot_v1 (scripts/bag_snapshots.py)",
        "contract_mismatches": contract_mismatch,
        "verdict": "NOT_FEEDABLE_OFFLINE_INTO_CANONICAL_PIPELINE",
        "verdict_reason": "De PoC-inputs bevatten 3D BAG en VBO's met sha256, maar niet de PDOK-adresrespons en de BAG-pandrespons "
                          "per adres die bag_snapshot_v1 vereist. Een BAGSNAP samenstellen uit andere queries zou de opvraagketen "
                          "veinzen; dat is niet gedaan. Er is geen adapter naar data/ geschreven en geen tweede snapshotsysteem gemaakt.",
    }


def bbox_context(inputs):
    """BAG-panden zonder verblijfsobject binnen 2 m van een pand in scope (context, geen kandidaat)."""
    from pyproj import Transformer
    T = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
    feats = {f["properties"]["identificatie"]: f for f in load(BBOX)["features"]}

    def ring(f):
        g = f["geometry"]
        r = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        return [T.transform(x, y) for x, y in r]

    def area(r):
        return abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1))) / 2

    def segd(p, a, b):
        (ax, ay), (bx, by), (px, py) = a, b, p
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5

    def dist(r1, r2):
        return min(min(segd(p, r2[i], r2[i + 1]) for i in range(len(r2) - 1)) for p in r1[:-1])

    scope = [p["bag_pand_id"] for p in inputs["panden"]]
    rings = {pid: ring(feats[pid]) for pid in scope}
    rows = []
    for pid, f in sorted(feats.items()):
        pr = f["properties"]
        if pid in scope or (pr.get("aantal_verblijfsobjecten") or 0) != 0:
            continue
        r = ring(f)
        d = min(min(dist(r, rings[s]), dist(rings[s], r)) for s in scope)
        if d < 2.0:
            rows.append({"bag_pand_id": pid, "status": pr.get("status"), "bouwjaar": pr.get("bouwjaar"),
                         "footprint_m2": str(Decimal(str(round(area(r), 1)))), "distance_to_scope_m": str(Decimal(str(round(d, 2))))})
    in_use = [r for r in rows if r["status"] == "Pand in gebruik"]
    return {"note": "Context, geen kandidaat en geen evidence. BAG-panden zonder verblijfsobject binnen 2 m van de 15 panden "
                    "(bron: bag_panden_bbox.json). Het MJOP sluit 'tuinopstallen' en 'aan-, uit- en/of dakopbouwen' als "
                    "bewonerseigen uit (DOC-005 p.3).",
            "panden_without_vbo_within_2m": rows, "in_use": len(in_use),
            "in_use_footprint_m2_sum_informative": str(sum((Decimal(r["footprint_m2"]) for r in in_use), Decimal(0)))}


# --------------------------------------------------------------------------
# B — building link review
# --------------------------------------------------------------------------

def link_review(inputs, candidates):
    docs = {d["document_id"]: d for d in candidates["documents"] if d["document_id"] in DOCS}
    plan_numbers = sorted({str(n) for d in docs.values() for p in d["lookup_plan"]
                           for n in ([p["number"]] if "number" in p else range(int(p["number_from"]), int(p["number_to"]) + 1))},
                          key=int)
    range_plan = any(p.get("kind") == "range" for d in docs.values() for p in d["lookup_plan"])
    reachable = sorted({p["bag_pand_id"] for p in inputs["panden"]
                        for v in p["vbo"] if str(v["huisnummer"]) in plan_numbers})
    rows = []
    for p in inputs["panden"]:
        for doc in DOCS:
            d = docs[doc]
            reasons = ["huisnummers " + ", ".join(str(v["huisnummer"]) for v in p["vbo"]) + " liggen in 'Maldenhof 240 - 296' (even)",
                       "postcode VBO " + ", ".join(sorted({v["postcode"] for v in p["vbo"]})) + f" = documentpostcode {d['postcode']}",
                       f"{sum(1 for v in p['vbo'] if v['point_in_bag_pand_polygon'])}/{len(p['vbo'])} VBO-punten liggen in de BAG-polygoon van dit pand"]
            ambiguity = ["ADDRESS_RANGE: het document noemt geen even/oneven; 29 eenheden (DOC p.2) = het aantal even nummers 240–296"]
            if p["bag_pand_id"] not in reachable:
                ambiguity.append("NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN: building_links.lookup_plan vraagt alleen 240 en 296 op; "
                                 "dit pand wordt via bag_snapshots.py geen kandidaat en 'record' weigert het")
            if len(p["vbo"]) > 1:
                ambiguity.append("MULTIPLE_ADDRESSES_IN_PAND: " + str(len(p["vbo"])) + " VBO's (woningindeling niet bevestigd)")
            rows.append({"document_id": doc, "address_as_stated": d["address_as_stated"], "postcode": d["postcode"],
                         "address_provenance": d["address_provenance"], "bag_pand_id": p["bag_pand_id"],
                         "vbo_addresses": p["addresses"], "bag_properties": p["bag_properties"],
                         "provenance": {"vbo_raw_files": [v["raw_file"] for v in p["vbo"]], "threedbag_raw_file": p["threedbag"]["raw_file"],
                                        "sha256_ok": all(v["raw_sha256_ok"] for v in p["vbo"]) and p["threedbag"]["file_sha256_ok"],
                                        "fetched_at": "NOT_RECORDED_IN_MAIN_SNAPSHOT"},
                         "source_cluster": d["source_cluster"], "document_relations": d["document_relations"],
                         "within_scope_assessment": "LIKELY_IN_SCOPE", "why": reasons, "ambiguity": ambiguity,
                         "link_status": "UNREVIEWED"})
    odd_rows = [{"bag_pand_id": pid, "within_scope_assessment": "LIKELY_OUT_OF_SCOPE",
                 "why": "kandidaat in de ALL_NUMBERS-hypothese (oneven zijde); 29 eenheden passen bij alleen de even nummers",
                 "vbo_addresses": "NOT_IN_MAIN_SNAPSHOT", "link_status": "UNREVIEWED"}
                for pid in inputs["other_candidate_panden_odd_side"]]
    return {"lookup_plan_numbers": plan_numbers, "lookup_plan_is_range": range_plan,
            "panden_reachable_via_canonical_lookup": reachable,
            "rows": rows, "odd_side_context": odd_rows,
            "note": "Geen link is CONFIRMED of REJECTED. Een link ontstaat alleen via 'scripts/building_links.py record' door een mens, "
                    "en vereist een canonieke BAG-snapshot (netwerk) met het pand als kandidaat."}


# --------------------------------------------------------------------------
# C — historische hoeveelheden
# --------------------------------------------------------------------------

def historical_review(qos, vocab, app_cw):
    by_code_unit = {}
    for m in vocab["historical_subject_mappings"]:
        by_code_unit[(m["element_code_internal"], m["unit_normalized"])] = ("MAPPING_PROPOSED", m["mapping_id"], m["subject_key"])
    not_mapped = {n["element_code_internal"]: n for n in vocab["not_mapped"] if n["element_code_internal"]}
    unresolved = {(u.get("internal_element_code"), u.get("unit")): u for u in app_cw["unresolved"] if u.get("internal_element_code")}
    rows = []
    for o in qos:
        if o["document_id"] not in DOCS:
            continue
        e = o["element"]
        code, unit = e["element_code_internal"], o["unit_normalized"]
        hit = by_code_unit.get((code, unit))
        if hit:
            comp = {"class": "COMPARABLE_CANDIDATE", "mapping_id": hit[1], "subject_key": hit[2]}
        elif code in not_mapped and unit == "m2":
            comp = {"class": "NOT_COMPARABLE", "reason": not_mapped[code]["reason"], "subject_key": not_mapped[code]["subject_key"]}
        elif o["quantity_kind"] == "ELEMENT_QUANTITY" and unit == "lump_sum":
            comp = {"class": "NOT_A_MEASURED_QUANTITY"}
        else:
            comp = {"class": "NO_3DBAG_SUBJECT",
                    "reason": (unresolved.get((code, unit)) or {}).get("reason") or "geen 3D BAG-onderwerp voor deze code/eenheid"}
        labels = []
        if code in NOT_GROUND_TRUTH_ROWS and o["quantity_value"] == "756.80":
            labels.append(LABEL_756)
        rows.append({"quantity_observation_id": o["quantity_observation_id"], "document_id": o["document_id"],
                     "element_code": code, "description": e["element_description_original"], "location": e["location_original"],
                     "value": o["quantity_value"], "unit": unit, "quantity_kind": o["quantity_kind"],
                     "method_class": o["method_class"], "source_cluster": o["source_cluster"], "status": o["status"],
                     "review_reasons": o["review_reasons"], "caveats": o["caveats"],
                     "identical_in": o["dependency"]["identical_in_same_object_documents"],
                     "differs_in": o["dependency"]["differs_in_same_object_documents"],
                     "page": o["provenance"]["page"], "text_fragment": o["provenance"]["text_fragment"],
                     "comparability_vs_3dbag": comp, "labels": labels})
    pairs = Counter()
    for r in rows:
        if r["document_id"] == "DOC-005":
            pairs["IDENTICAL_IN_DOC-006" if r["identical_in"] else "DIFFERS_IN_DOC-006" if r["differs_in"] else "NO_COUNTERPART_SAME_KEY"] += 1
    return {"rows": rows, "counts": {"DOC-005": sum(1 for r in rows if r["document_id"] == "DOC-005"),
                                     "DOC-006": sum(1 for r in rows if r["document_id"] == "DOC-006")},
            "by_status": dict(sorted(Counter(r["status"] for r in rows).items())),
            "by_comparability": dict(sorted(Counter(r["comparability_vs_3dbag"]["class"] for r in rows).items())),
            "doc005_vs_doc006": dict(sorted(pairs.items())),
            "dependency_note": "DOC-005 (MJOP 2026) en DOC-006 (MJOP 2023) zijn versies van hetzelfde MJOP (DREL-002, SAME_OBJECT; "
                               "zelfde source cluster). Identieke waarden zijn GEEN twee onafhankelijke metingen. DOC-006 is daarnaast "
                               "duplicate_source van DOC-014 (DREL-005; DOC-014 heeft geen quantity observations op main).",
            "label_756": {"label": LABEL_756, "observation_ids": [r["quantity_observation_id"] for r in rows if LABEL_756 in r["labels"]],
                          "status_kept": "blijft bestaan als SOURCE_REPORTED-observation (niet verwijderd, niet gewijzigd)",
                          "why": "docs/facade PoC v2 §5: één ongedefinieerde regel, identiek 2023→2026, rapport zegt 'geen metingen', "
                                 "zelfde getal ook als '756,80 st ventilatierooster' (DOC-005 p.11)"}}


# --------------------------------------------------------------------------
# D — subject / crosswalk review
# --------------------------------------------------------------------------

def bag3d_preview(inputs, vocab):
    rules = [r for r in vocab["bag3d_rules"] if r["status"] == "ACTIVE"]
    per = []
    sums = defaultdict(Decimal)
    for p in inputs["panden"]:
        vals = {}
        for res in rules_mod.apply_rules(p["_attributes"], rules):
            vals[res["subject_key"]] = {"value": res["value"], "status": res["status"], "rule_id": res["rule_id"],
                                        "method_class": next(r["method_class"] for r in rules if r["rule_id"] == res["rule_id"]),
                                        "raw_inputs": res["raw_inputs"]}
            if res["status"] == "OK":
                sums[res["subject_key"]] += Decimal(res["value"])
        per.append({"bag_pand_id": p["bag_pand_id"], "addresses": p["addresses"], "values": vals})
    return {"note": "PREVIEW van de bestaande 3D BAG-regels op de PoC-snapshot. GEEN evidence. Bron: 3D BAG-respons per pand "
                    "(sha256 gecontroleerd), fetched_at niet vastgelegd op main.",
            "per_pand": per,
            "sum_over_15_panden_informative": {k: str(v) for k, v in sorted(sums.items()) if k != "BUILDING_HEIGHT"},
            "sum_note": "Informatief. De bestaande pipeline telt bewust NIET op over panden (MULTI_PAND_NOT_SUMMED); een som als "
                        "evidence vereist eerst een menselijk architectuurbesluit (zie E)."}


def crosswalk_review(vocab, app_cw, eff, hist, preview):
    sums = preview["sum_over_15_panden_informative"]
    rows_by_code = defaultdict(list)
    for r in hist["rows"]:
        rows_by_code[(r["element_code"], r["unit"])].append(r)

    def mal(code, unit):
        return [f"{r['quantity_observation_id']} '{r['description']}' / {r['location']} = {r['value']} {unit}"
                for r in rows_by_code.get((code, unit), [])]
    out = [
        {"mapping_id": "HSM-ROOF_FLAT_AREA-4711-m2", "kind": "HISTORICAL_SUBJECT", "historical_elements": "4711 m2 (alle documenten)",
         "app_element": None, "quantity_subject": "ROOF_FLAT_AREA", "unit": "m2",
         "semantics": "historisch: dakbedekking (APP/bitumen) in m2 zoals de adviseur noteerde, kan opstanden/overlappen bevatten; "
                      "3D BAG: b3_opp_dak_plat = plat dakoppervlak per pand volgens de attribuutnaam; de precieze definitie is in deze repo "
                      "niet tegen de 3D BAG-documentatie gecontroleerd (USED_IN_MJOP_APP_NOT_VERIFIED_AGAINST_LIVE_API)",
         "evidence_in_repo": mal("4711", "m2") + [f"3D BAG Σ15 panden b3_opp_dak_plat = {sums.get('ROOF_FLAT_AREA')} m2 (informatief)",
                                                  "alle 4711-m2-rijen in de 662 observations zijn dakbedekking (o.a. ook 'liftdak', 'portiek dak': deeldaken)"],
         "risk": "Maldenhof: 425,80 vs Σ 190,65 (factor ~2,2). Onbekend welke dakdelen 'Platte dak' omvat; de 3D BAG-som betreft alleen "
                 "de 15 woonpanden. Verschil is een feit, geen fout van één bron.",
         "current_status": eff["HSM-ROOF_FLAT_AREA-4711-m2"]["status"], "advice": "NEEDS_REVIEW",
         "advice_reason": "Code-semantiek is homogeen (dakbedekking m2), maar scope van 'plat dak' verschilt per document; verifiëren "
                          "zet ALLE 4711-m2-rijen naast b3_opp_dak_plat. Acceptabel als 'naast elkaar tonen', niet als gelijkstelling."},
        {"mapping_id": "XW-dak-plat-4711-m2", "kind": "APP_ELEMENT", "historical_elements": "4711 m2",
         "app_element": "dak-plat (27.1 'Dakbedekking plat dak')", "quantity_subject": "ROOF_FLAT_AREA", "unit": "m2",
         "semantics": "element-identiteit: app 'Dakbedekking plat dak' ↔ intern 4711 'Dakbedekking (APP/bitumen)'; app rekent met b3_opp_dak_plat",
         "evidence_in_repo": ["vocabularies/app_element_crosswalk_v1.json", MJOP_APP["dak_plat_auto_source"]],
         "risk": "laag op element-niveau (zelfde bouwdeel); m1-rijen (dakrand) vallen buiten door de eenheid",
         "current_status": eff["XW-dak-plat-4711-m2"]["status"], "advice": "SAFE_TO_VERIFY",
         "advice_reason": "Koppelt alleen het bouwdeel; de hoeveelheden blijven naast elkaar staan en een mens kiest via quantity_resolution."},
        {"mapping_id": "HSM-ROOF_SLOPED_AREA-4712-m2", "kind": "HISTORICAL_SUBJECT", "historical_elements": "4712 m2 (alle documenten)",
         "app_element": None, "quantity_subject": "ROOF_SLOPED_AREA", "unit": "m2",
         "semantics": "historisch: 4712 is een gemengde code; 3D BAG: b3_opp_dak_schuin = hellend vlak (niet de projectie)",
         "evidence_in_repo": mal("4712", "m2") + [f"3D BAG Σ15 panden b3_opp_dak_schuin = {sums.get('ROOF_SLOPED_AREA')} m2 (informatief)",
                                                  "andere 4712-m2-rijen in de 662: 'Dakbedekking zink' (lichtstraat 0,78; 4,25), 'shingles', 'leisteen', 'keramisch'"],
         "risk": "Generiek verifiëren brengt ook zink-/shinglerijen onder ROOF_SLOPED_AREA. Voor Maldenhof is de rij wel 'Dakpan beton / Hellend dak'.",
         "current_status": eff["HSM-ROOF_SLOPED_AREA-4712-m2"]["status"], "advice": "NEEDS_REVIEW",
         "advice_reason": "Gemengde code; een mapping per omschrijving bestaat niet in v1."},
        {"mapping_id": "XW-dak-hellend-4712-m2", "kind": "APP_ELEMENT", "historical_elements": "4712 m2",
         "app_element": "dak-hellend (27.2 'Dakbedekking hellend dak (pannen)')", "quantity_subject": "ROOF_SLOPED_AREA", "unit": "m2",
         "semantics": "app 'pannen' ↔ gemengde code 4712", "evidence_in_repo": ["vocabularies/app_element_crosswalk_v1.json"],
         "risk": "zink/shingles onder 'pannen'", "current_status": eff["XW-dak-hellend-4712-m2"]["status"], "advice": "NEEDS_REVIEW",
         "advice_reason": "zelfde reden als HSM-ROOF_SLOPED_AREA-4712-m2"},
        {"mapping_id": "XW-gevel-metselwerk-2110-m2", "kind": "APP_ELEMENT", "historical_elements": "2110 m2",
         "app_element": "gevel-metselwerk (21.1)", "quantity_subject": None, "unit": "m2",
         "semantics": "historisch: metselwerk 'Alle gevels' 1631,90 m2 (netto of bruto onbekend); 3D BAG b3_opp_buitenmuur = bruto buitenmuur incl. openingen",
         "evidence_in_repo": mal("2110", "m2") + [f"3D BAG Σ15 panden b3_opp_buitenmuur = {sums.get('OUTER_WALL_GROSS_AREA')} m2 (informatief)"],
         "risk": "bruto ≠ netto; quantity_subject staat terecht op null (vocabulary not_mapped)",
         "current_status": eff["XW-gevel-metselwerk-2110-m2"]["status"], "advice": "NEEDS_REVIEW",
         "advice_reason": "Alleen als code-koppeling zonder hoeveelheidsonderwerp; NIET als ROOF/OUTER_WALL-vergelijking gebruiken."},
        {"mapping_id": None, "kind": "NO_MAPPING (kozijn/schilderwerk)", "historical_elements": "3120 m2 'Kozijn buiten hout', 4631 m2 'Buitenschilderwerk kozijn hout dekkend'",
         "app_element": "schilderwerk-buiten (31.2) is UNRESOLVED (NOT_SAFE)", "quantity_subject": None, "unit": "m2",
         "semantics": "kozijn-/schilderhoeveelheid, ongedefinieerd ('incl. draaiende delen'); geen 3D BAG-onderwerp",
         "evidence_in_repo": mal("3120", "m2") + mal("4631", "m2"),
         "risk": "hoog: " + LABEL_756, "current_status": "UNRESOLVED", "advice": "REJECT",
         "advice_reason": "Geen mapping maken naar een 3D BAG-onderwerp; de rijen blijven SOURCE_REPORTED."},
        {"mapping_id": None, "kind": "NO_MAPPING (dakrand/goot/HWA)", "historical_elements": "4711 m1 dakrand 70,00; 2716 m1 dakgoot 165,80; 5211 m1 HWA 41,40 + 91,60",
         "app_element": "UNRESOLVED (APP_HAS_NO_EQUIVALENT_ELEMENT / UNIT_MISMATCH)", "quantity_subject": None, "unit": "m1",
         "semantics": "strekkende meters; 3D BAG heeft geen m1-onderwerp", "evidence_in_repo": mal("4711", "m1") + mal("2716", "m1") + mal("5211", "m1"),
         "risk": "geen vergelijkbaar onderwerp", "current_status": "UNRESOLVED", "advice": "REJECT",
         "advice_reason": "Niet in deze milestone; geen 3D BAG-regel voor m1."},
    ]
    return out


# --------------------------------------------------------------------------
# E — demo readiness
# --------------------------------------------------------------------------

def demo_readiness(inputs, links, hist, preview):
    snaps = sorted(s["snapshot_id"] for s in bs.load_snapshots() if s["document_id"] in DOCS)
    flat_rows = [r for r in hist["rows"] if r["element_code"] == "4711" and r["unit"] == "m2"]
    per_pand_flat = [{"bag_pand_id": p["bag_pand_id"], "addresses": p["addresses"],
                      "b3_opp_dak_plat": p["values"]["ROOF_FLAT_AREA"]["value"]} for p in preview["per_pand"]]
    blockers = [
        ({"id": "B1_NO_CANONICAL_SNAPSHOT", "status": "RESOLVED",
          "what": "Canonieke bag_snapshot_v1-snapshots aanwezig: " + ", ".join(snaps) + " (de PoC-inputs zelf blijven niet-canoniek).",
          "unblock": "—"} if snaps else
         {"id": "B1_NO_CANONICAL_SNAPSHOT", "status": "OPEN",
          "what": "Er is geen bag_snapshot_v1 voor DOC-005/DOC-006; de PoC-inputs voldoen niet aan het contract (zie A).",
          "unblock": "netwerktoegang tot api.pdok.nl en api.3dbag.nl + scripts/bag_snapshots.py fetch (expliciete toestemming nodig)"}),
        ({"id": "B2_LOOKUP_PLAN_RANGE_ENDPOINTS_ONLY", "status": "RESOLVED",
          "what": f"Het opvraagplan is een range-opvraging ({links['lookup_plan_numbers'][0]}–{links['lookup_plan_numbers'][-1]}, "
                  f"zonder pariteit-aanname); {len(links['panden_reachable_via_canonical_lookup'])} van {inputs['bag_panden_in_scope']} "
                  "panden in scope zijn bereikbaar.", "unblock": "—"} if links["lookup_plan_is_range"] else
         {"id": "B2_LOOKUP_PLAN_RANGE_ENDPOINTS_ONLY", "status": "OPEN",
          "what": f"Het opvraagplan vraagt alleen {', '.join(links['lookup_plan_numbers'])} op; "
                  f"daarmee zijn {len(links['panden_reachable_via_canonical_lookup'])} van {inputs['bag_panden_in_scope']} panden kandidaat "
                  f"({', '.join(links['panden_reachable_via_canonical_lookup'])}). 'record' weigert panden buiten de snapshot.",
          "unblock": "menselijk besluit: opvraagplan voor een bereik uitbreiden — toolingwijziging"}),
        {"id": "B3_MULTI_PAND_BUILDING", "status": "DECIDED_OPTION_A (2026-10-05): gebouwscope BAG:<gesorteerde pand-ID's>, per-pand-evidence + "
         "GEOMETRY_DERIVED scope-aggregaat; app-bundel v2 (multi-pand). Zie docs/building_link_3dbag_evidence_v1.md §8.",
         "what": "15 panden. De evidence-builder telt niet op (MULTI_PAND_NOT_SUMMED): historische evidence krijgt "
         "building_id BAG:<15 ids>, 3D BAG-evidence BAG:<1 id> per pand; export_app_quantity_bundle neemt voor één building_id dus niet "
         "beide bronnen mee; MJOP-App bundleEntries weigert bundels met >1 pand.",
         "unblock": "ARCHITECTUURBESLUIT (CLAUDE.md: eerst melden): (a) VvE-gebouw = meerdere panden met een expliciete, menselijk "
                    "goedgekeurde 3D BAG-somregel (GEOMETRY_DERIVED) en een app die meerdere panden per plan accepteert; of (b) per pand "
                    "werken, waarbij de historische complexwaarde niet aan één pand gehangen kan worden"},
        {"id": "B4_ROOF_FLAT_SCOPE", "what": "Historisch 4711 'Dakbedekking APP / Platte dak' = 425,80 m2 vs 3D BAG Σ b3_opp_dak_plat = "
         f"{preview['sum_over_15_panden_informative'].get('ROOF_FLAT_AREA')} m2 (informatief).",
         "unblock": "geen correctie; beide naast elkaar tonen, een mens beslist in quantity_resolution"},
    ]
    return {
        "recommended_first_subject": "ROOF_FLAT_AREA (plat dak / dakbedekking, app-element dak-plat)",
        "why": "Schoonste element-koppeling (4711 m2 is overal dakbedekking; XW-dak-plat-4711-m2 is element-identiteit) en de app "
               "rekent al met b3_opp_dak_plat. Het grote verschil is juist wat het demo moet tonen: twee bronnen naast elkaar, "
               "geen winnaar. ROOF_SLOPED_AREA ligt numeriek dichter bij elkaar, maar 4712 is een gemengde code.",
        "blockers": blockers,
        "smallest_safe_demo_status": "BLOCKED_BY_HUMAN_DECISIONS (building links, HSM-/XW-mapping)",
        "human_decisions_in_order": [
            "1. Building links: per pand per document accepteren/afwijzen (checklist B) — pas vast te leggen na B1/B2.",
            "2. HSM-ROOF_FLAT_AREA-4711-m2: VERIFY of REJECT (advies NEEDS_REVIEW → als 'naast elkaar tonen' verantwoord).",
            "3. XW-dak-plat-4711-m2: VERIFY of REJECT (advies SAFE_TO_VERIFY).",
            "4. Architectuur B3: (a) meerdere panden per VvE-gebouw incl. 3D BAG-somregel + app-aanpassing, of (b) per pand.",
            "5. Toestemming netwerk (B1) en opvraagplan voor bereiken (B2).",
        ],
        "after_decisions_historical_evidence": [
            {"quantity_observation_id": r["quantity_observation_id"], "value": r["value"], "unit": r["unit"],
             "method_class": "SOURCE_REPORTED", "source_type": "MJOP_ELEMENT_OVERVIEW", "page": r["page"],
             "text_fragment": r["text_fragment"], "source_cluster": r["source_cluster"],
             "dependency": "DOC-005 en DOC-006 zelfde object: geen onafhankelijke bevestiging"} for r in flat_rows],
        "after_decisions_3dbag_evidence": {"per_pand_b3_opp_dak_plat": per_pand_flat, "method_class": "DIRECT_MEASURED",
                                           "rule_id": "bag3d.roof_flat_area",
                                           "complex_sum_informative": preview["sum_over_15_panden_informative"].get("ROOF_FLAT_AREA"),
                                           "complex_sum_note": "alleen als evidence na besluit B3(a), dan als GEOMETRY_DERIVED met somregel"},
        "app_would_show_conceptually": {
            "element": "Dakbedekking plat dak (dak-plat)",
            "sources": [{"label": "Uit oud MJOP", "value": "425,80 m²", "basis": "DOC-005 (2026) en DOC-006 (2023), elementenoverzicht p." + "/".join(sorted({str(r["page"]) for r in flat_rows})) + " — SOURCE_REPORTED; "
                                                                                 "zelfde waarde in beide versies, geen onafhankelijke bevestiging"},
                        {"label": "3D BAG", "value": f"{preview['sum_over_15_panden_informative'].get('ROOF_FLAT_AREA')} m² over 15 panden (pas na besluit B3a) "
                                                     "of per pand (B3b)", "basis": "b3_opp_dak_plat — DIRECT_MEASURED per pand"}],
            "status": "Nog niet door gebruiker bevestigd (geen quantity_resolution)",
            "rule": "geen gemiddelde, geen score, geen automatische keuze; effectieve waarde pas via een ACTIVE quantity_resolution"},
    }


# --------------------------------------------------------------------------

def build():
    qos = load(QO_PATH)["observations"]
    vocab = load(xw.SUBJECTS)
    app_cw = load(xw.APP_CROSSWALK)
    eff = xw.effective()
    candidates = load(CANDIDATES)
    link_store = bl.load_store()
    inputs = inputs_review()
    links = link_review(inputs, candidates)
    hist = historical_review(qos, vocab, app_cw)
    preview = bag3d_preview(inputs, vocab)
    xwr = crosswalk_review(vocab, app_cw, eff, hist, preview)
    demo = demo_readiness(inputs, links, hist, preview)
    for p in inputs["panden"]:
        p.pop("_attributes", None)
    return {
        "report_version": REPORT_VERSION,
        "note": "Read-only SOURCE COMPARISON / ACTIVATION REVIEW. Geen accuracy-benchmark, geen besluiten, geen evidence, "
                "geen API-/netwerk-calls. Maldenhof is testcase, niet meetlat.",
        "state_of_human_decisions": {
            "building_links_records": len(link_store["records"]),
            "crosswalk_decisions_records": len(xw.load_store()["records"]),
            "quantity_resolutions_records": len(load(ROOT / "data" / "quantity_resolutions" / "quantity_resolution_records.json")["records"]),
            "building_quantity_evidence": len(load(ROOT / "data" / "quantity_evidence" / "building_quantity_evidence_v1.json")["evidence"]),
        },
        "input_hashes": {"quantity_observations_sha256": sha_bytes(QO_PATH), "building_link_candidates_sha256": sha_bytes(CANDIDATES),
                         "subjects_vocab_sha256": sha_bytes(xw.SUBJECTS), "app_crosswalk_sha256": sha_bytes(xw.APP_CROSSWALK),
                         "poc_source_manifest_sha256": sha_bytes(SNAP / "SOURCE.json"), "bag_bbox_sha256": sha_bytes(BBOX)},
        "mjop_app": MJOP_APP,
        "A_inputs": inputs,
        "A_context_panden_without_vbo": bbox_context(inputs),
        "B_building_link_review": links,
        "C_historical_quantities": hist,
        "D_bag3d_preview": preview,
        "D_crosswalk_review": xwr,
        "E_demo_readiness": demo,
    }


def render(r):
    A, B, C, D, X, E = (r["A_inputs"], r["B_building_link_review"], r["C_historical_quantities"], r["D_bag3d_preview"],
                        r["D_crosswalk_review"], r["E_demo_readiness"])
    s = r["state_of_human_decisions"]
    L = ["# Quantity Engine Activation Review v1 — Maldenhof (DOC-005 / DOC-006)", "",
         "Read-only bronnenvergelijking. **Geen accuracy-benchmark, geen besluiten, geen evidence, geen API- of netwerkcalls.** "
         "Gegenereerd door `scripts/quantity_engine_activation_review.py`.", "",
         f"Stand menselijke besluiten: building links {s['building_links_records']}, crosswalk-besluiten {s['crosswalk_decisions_records']}, "
         f"quantity resolutions {s['quantity_resolutions_records']}, building evidence {s['building_quantity_evidence']}.", "",
         "## A — Maldenhof-inputs (PoC v2-snapshot)", "",
         f"- BAG-panden in scope: **{A['bag_panden_in_scope']}**; VBO's/adressen: **{A['vbo_count']}** "
         f"(per pand: {', '.join(f'{k} VBO: {v} panden' for k, v in A['panden_by_vbo_count'].items())}).",
         f"- Huisnummers = alle even nummers 240–296: **{'ja' if A['addresses_equal_even_240_296'] else 'nee'}** "
         f"({A['even_numbers_in_range']} even van {A['all_numbers_in_range']} nummers in het bereik; document: 29 eenheden).",
         f"- VBO-punten binnen de BAG-polygoon van hun pand: {A['vbo_points_inside_own_pand_polygon']}/{A['vbo_count']}.",
         f"- Ruwe bestanden met kloppende sha256: {A['raw_files_sha256_ok']}/{A['raw_files']}; fetched_at niet vastgelegd op main.",
         f"- Overige kandidaat-panden (oneven zijde, context): {len(A['other_candidate_panden_odd_side'])}.",
         f"- **Oordeel: {A['verdict']}** — {A['verdict_reason']}", "",
         "| Veld | Canoniek (bag_snapshot_v1) | PoC-snapshot |", "|---|---|---|"]
    L += [f"| {m['field']} | {m['canonical']} | {m['poc_snapshot']} |" for m in A["contract_mismatches"]]
    ctx = r["A_context_panden_without_vbo"]
    L += ["", f"Context: {len(ctx['panden_without_vbo_within_2m'])} BAG-panden zonder VBO binnen 2 m ({ctx['in_use']} in gebruik, "
              f"samen {ctx['in_use_footprint_m2_sum_informative']} m² footprint, ~5 m² per stuk). {ctx['note']}", "",
          "## B — Building link review", "",
          f"Canoniek opvraagplan: {('bereik ' + B['lookup_plan_numbers'][0] + '–' + B['lookup_plan_numbers'][-1]) if B['lookup_plan_is_range'] else 'huisnummers ' + ', '.join(B['lookup_plan_numbers'])} → bereikbaar: {', '.join(B['panden_reachable_via_canonical_lookup'])} "
          f"({len(B['panden_reachable_via_canonical_lookup'])} van {A['bag_panden_in_scope']}). {B['note']}", "",
          "### BUILDING LINK REVIEW (beslislijst — nog niets vastgelegd)", "",
          "| BAG-pand | Adressen | DOC-005 | DOC-006 | Waarom in scope | Ambiguïteit |", "|---|---|---|---|---|---|"]
    by_pand = defaultdict(list)
    for row in B["rows"]:
        by_pand[row["bag_pand_id"]].append(row)
    for pid, rows in sorted(by_pand.items()):
        rw = rows[0]
        amb = "; ".join(a.split(":")[0] for a in rw["ambiguity"])
        L.append(f"| {pid} | {', '.join(rw['vbo_addresses'])} | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | "
                 f"{rw['why'][2]} | {amb} |")
    L += ["", "Oneven zijde (kandidaten uit de ALL_NUMBERS-hypothese; adressen niet in de main-snapshot; inschatting: buiten scope):", "",
          "| BAG-pand | DOC-005 | DOC-006 |", "|---|---|---|"]
    L += [f"| {o['bag_pand_id']} | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |" for o in B["odd_side_context"]]
    L += ["", "## C — Historische hoeveelheden DOC-005 / DOC-006", "",
          f"- Observations: DOC-005 {C['counts']['DOC-005']}, DOC-006 {C['counts']['DOC-006']}; status {C['by_status']}.",
          f"- Vergelijkbaarheid met 3D BAG: {C['by_comparability']}.",
          f"- DOC-005 t.o.v. DOC-006: {C['doc005_vs_doc006']}.",
          f"- {C['dependency_note']}",
          f"- **756,80 m²** ({', '.join(C['label_756']['observation_ids'])}): **{C['label_756']['label']}** — {C['label_756']['status_kept']}.", "",
          "| Observation | Code | Omschrijving | Locatie | Waarde | Eenh. | Status | Caveats | DOC-005↔006 | Vs 3D BAG | Labels |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in C["rows"]:
        rel = "gelijk" if x["identical_in"] else ("verschilt" if x["differs_in"] else "—")
        comp = x["comparability_vs_3dbag"]
        ctext = comp["class"] + (f" ({comp.get('mapping_id')})" if comp.get("mapping_id") else "")
        L.append(f"| {x['quantity_observation_id']} | {x['element_code']} | {x['description']} | {x['location'] or '—'} | {x['value']} | {x['unit']} | "
                 f"{x['status']} | {', '.join(x['caveats'] + x['review_reasons']) or '—'} | {rel} | {ctext} | {', '.join(x['labels']) or '—'} |")
    L += ["", "## D — 3D BAG-preview (geen evidence) en crosswalk review", "", D["note"], "",
          "| BAG-pand | Adressen | Plat dak m² | Hellend dak m² | Buitenmuur bruto m² |", "|---|---|---|---|---|"]
    for p in D["per_pand"]:
        v = p["values"]
        L.append(f"| {p['bag_pand_id']} | {', '.join(p['addresses'])} | {v['ROOF_FLAT_AREA']['value']} | {v['ROOF_SLOPED_AREA']['value']} | "
                 f"{v['OUTER_WALL_GROSS_AREA']['value']} |")
    sm = D["sum_over_15_panden_informative"]
    L += [f"| **Σ 15 panden (informatief)** | | {sm.get('ROOF_FLAT_AREA')} | {sm.get('ROOF_SLOPED_AREA')} | {sm.get('OUTER_WALL_GROSS_AREA')} |",
          "", D["sum_note"], "",
          "| Voorstel | Historisch | App-element | Onderwerp | Eenh. | Huidige status | Advies | Risico |", "|---|---|---|---|---|---|---|---|"]
    for m in X:
        L.append(f"| {m['mapping_id'] or m['kind']} | {m['historical_elements']} | {m['app_element'] or '—'} | {m['quantity_subject'] or '—'} | "
                 f"{m['unit']} | {m['current_status']} | **{m['advice']}** | {m['risk']} |")
    L += ["", "Semantiek per voorstel:", ""]
    L += [f"- **{m['mapping_id'] or m['kind']}** — {m['semantics']}. Advies-reden: {m['advice_reason']}" for m in X]
    L += ["", "## E — Eerste end-to-end demo", "",
          f"- Aanbevolen eerste onderwerp: **{E['recommended_first_subject']}** — {E['why']}",
          f"- Status: **{E['smallest_safe_demo_status']}**", "", "Blokkades:", ""]
    L += [f"- **{b['id']}**{(' [' + b['status'] + ']') if b.get('status') else ''} — {b['what']} → {b['unblock']}" for b in E["blockers"]]
    L += ["", "Menselijke besluiten (volgorde):", ""] + [f"- {d}" for d in E["human_decisions_in_order"]]
    L += ["", "Historische evidence die daarna ontstaat (SOURCE_REPORTED):", ""]
    L += [f"- {h['quantity_observation_id']}: {h['value']} {h['unit']} (p.{h['page']}: \"{h['text_fragment']}\") — {h['dependency']}"
          for h in E["after_decisions_historical_evidence"]]
    ev3 = E["after_decisions_3dbag_evidence"]
    L += ["", f"3D BAG-evidence die daarna ontstaat ({ev3['rule_id']}, {ev3['method_class']}): per pand "
              + "; ".join(f"{p['bag_pand_id']} {p['b3_opp_dak_plat']} m²" for p in ev3["per_pand_b3_opp_dak_plat"])
          + f". Complexsom {ev3['complex_sum_informative']} m² — {ev3['complex_sum_note']}.", "",
          "Wat MJOP-App daarna conceptueel zou tonen:", "", f"> **{E['app_would_show_conceptually']['element']}**  "]
    for src in E["app_would_show_conceptually"]["sources"]:
        L.append(f"> {src['label']}: {src['value']} — {src['basis']}  ")
    L += [f"> Status: {E['app_would_show_conceptually']['status']}  ", f"> {E['app_would_show_conceptually']['rule']}", "",
          f"MJOP-App: {r['mjop_app']['repository']} @ {r['mjop_app']['commit'][:7]} ({r['mjop_app']['default_branch']}); "
          f"Quantity Sources v1 {r['mjop_app']['quantity_sources_v1']}. {r['mjop_app']['bundle_rule']}", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    rep = build()
    js = json.dumps(rep, ensure_ascii=False, indent=1) + "\n"
    md = render(rep)
    if a.check:
        ok = OUT_JSON.exists() and OUT_JSON.read_text(encoding="utf-8") == js and OUT_MD.read_text(encoding="utf-8") == md
        print("activation review up-to-date" if ok else "activation review NIET up-to-date")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8", newline="\n")
    OUT_MD.write_text(md, encoding="utf-8", newline="\n")
    print(json.dumps({"panden": rep["A_inputs"]["bag_panden_in_scope"], "vbo": rep["A_inputs"]["vbo_count"],
                      "verdict": rep["A_inputs"]["verdict"], "demo": rep["E_demo_readiness"]["smallest_safe_demo_status"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
