"""Rapportdata facade PoC v2 Maldenhof — dekking per adres, herhaling, MJOP-ontleding, benchmarks, detectiereview.

ANALYSE-SCRIPT. Leest de uitvoer van facade_coverage_poc_v2.py (--run-dir: coverage.json, detections_v2.json,
aggregate_v2.json), de geëxtraheerde MJOP's (data/extracted/DOC-005.json, DOC-006.json), de v1-detectie
(reports/quantity/facade_element_detection_poc_v1_maldenhof.json) en de visuele review
(reports/quantity/facade_detection_review_v2_maldenhof.json). Schrijft één JSON:

    python scripts/facade_poc_v2_report.py --run-dir /tmp/fc2 \\
        --out reports/quantity/facade_element_detection_poc_v2_maldenhof.json

Geen wijziging aan stores of canonical data. Alle getallen deterministisch (Decimal voor m²/m¹).
"""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facade_coverage_poc_v2 as fc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRONT_ZONES = ("FRONT", "SIDE_FRONT_PART")
REAR_ZONES = ("REAR", "SIDE_REAR_PART")
SUFFICIENT = Decimal("0.80")     # aandeel bevestigd zichtbaar per gevelzijde voor "voldoende"
PHOTO_MIN_M2 = Decimal("1.0")    # ontbrekende zone per pand/zijde/laag vanaf 1 m² -> foto nodig
MJOP_ELEMENT_SUFFIX = ("EL-006", "EL-007", "EL-012", "EL-015", "EL-022")
D2 = Decimal("0.01")


def dec(x):
    return Decimal(str(x)).quantize(D2)


# --- MJOP-ontleding -------------------------------------------------------------------------------------------------

# Regels die in de PDF staan maar niet als maintenance_action zijn geëxtraheerd (buiten de begrotingshorizon, € 0).
PDF_ONLY_ROWS = [
    {"document_id": "DOC-005", "page": 11, "element_code": "3120", "element": "Kozijn buiten hout",
     "location": "Alle gevels", "action": "Vervangen kozijn hout", "quantity": "756.80", "unit": "m2",
     "planned_year": 2070, "cost_in_horizon": "0",
     "provenance": "PDF-tekst p.11: 'Vervangen kozijn hout 756,80m2 2070 48 € 0'"},
    {"document_id": "DOC-006", "page": 14, "element_code": "3120", "element": "Kozijn buiten hout",
     "location": "Alle gevels", "action": "Vervangen kozijn hout", "quantity": "756.80", "unit": "m2",
     "planned_year": 2070, "cost_in_horizon": "0",
     "provenance": "PDF-tekst p.14: 'Vervangen kozijn hout 756,80m2 2070 48 € 0'"},
]
DISCLAIMER = {
    "DOC-005": {"page": 4, "text": "specialistische onderzoeken niet worden uitgevoerd, er geen metingen worden verricht, er "
                                   "geen berekeningen worden uitgevoerd"},
    "DOC-006": {"page": 4, "text": "specialistische onderzoeken niet worden uitgevoerd, er geen metingen worden verricht, er "
                                   "geen berekeningen worden uitgevoerd"},
}


def mjop_decomposition():
    recs = []
    for doc in ("DOC-005", "DOC-006"):
        j = json.loads((ROOT / "data" / "extracted" / f"{doc}.json").read_text(encoding="utf-8"))
        els = {e["element_id"]: e for e in j["elements"]}
        for eid, e in els.items():
            if not eid.endswith(MJOP_ELEMENT_SUFFIX):
                continue
            pv = e["element_name"]["provenance"]
            recs.append({"document_id": doc, "element_id": eid, "record": "element_overview",
                         "element_code": e["element_code"]["original_value"], "element": e["element_name"]["value"],
                         "location": (e.get("location") or {}).get("value"), "material": (e.get("material") or {}).get("value"),
                         "maintenance_action": None, "quantity": (e.get("quantity") or {}).get("value"),
                         "unit": (e.get("unit") or {}).get("value") if isinstance(e.get("unit"), dict) else e.get("unit"),
                         "page": pv["page"], "provenance": pv["text_fragment"]})
        for a in j["maintenance_actions"]:
            if not a["element_id"].endswith(MJOP_ELEMENT_SUFFIX):
                continue
            pv = a["action"]["provenance"]
            e = els[a["element_id"]]
            unit = a.get("unit")
            recs.append({"document_id": doc, "element_id": a["element_id"], "record": "maintenance_action",
                         "action_id": a["action_id"], "element": e["element_name"]["value"],
                         "location": (e.get("location") or {}).get("value"), "material": (e.get("material") or {}).get("value"),
                         "maintenance_action": a["action"]["original_value"], "quantity": a["quantity"].get("value"),
                         "unit": unit.get("original_value") if isinstance(unit, dict) else unit,
                         "planned_year": a["planned_year"].get("value"), "page": pv["page"], "provenance": pv["text_fragment"]})
    for r in PDF_ONLY_ROWS:
        recs.append({**r, "record": "pdf_only_not_extracted"})

    answers = {
        "single_line_or_sum": "EÉN regel: element 3120 'Kozijn buiten hout', locatie 'Alle gevels', 756,80 m2 (DOC-005 en "
                              "DOC-006 p.6 elementenoverzicht). Dezelfde 756,80 wordt hergebruikt bij 4631 "
                              "'Buitenschilderwerk kozijn hout dekkend' en bij 'Vervangen kozijn hout'. Geen optelling van "
                              "deelregels zichtbaar in de bron.",
        "window_frame_area": "NIET UIT DE BRON AF TE LEIDEN. De bron noemt alleen 'Kozijn buiten hout', m2, 'Alle gevels'; "
                             "geen meetinstructie (aanzicht, dagmaat of ontwikkeld oppervlak).",
        "paint_area": "DEELS: de schilderhandeling heet 'Groot schilderwerk kozijn (en draaiende delen) hout dekkend' met "
                      "dezelfde 756,80 m2 — de hoeveelheid dient dus (ook) als schilderhoeveelheid en omvat volgens de "
                      "omschrijving ook draaiende delen. Hoe die m2 is bepaald staat er niet.",
        "doors_included": "ONBEKEND. Geen aparte regel voor buitendeuren of bergingsdeuren in beide MJOP's; of deuren in "
                          "de 756,80 zitten staat nergens.",
        "panels_included": "ONBEKEND voor borstweringen; houten gevelbekleding staat APART (4112, 332,00 m2, "
                           "'Voorgevel - gevelbekleding'), dus die zit er vermoedelijk niet in — maar ook dat staat er "
                           "niet expliciet.",
        "facade_sides": "'Alle gevels' (geen uitsplitsing per gevelzijde).",
        "doc005_vs_doc006": "Identiek: 756,80 m2 (en ook metselwerk 1631,90, raamdorpel 281,20, gevelbekleding 332,00) in "
                            "DOC-006 (inspectie 2023) en DOC-005 (inspectie 14-8-2026). De hoeveelheden zijn overgenomen, "
                            "niet opnieuw bepaald. Verschil: prijs/m2 schilderwerk (DOC-006 € 40.237, DOC-005 € 32.823 "
                            "voor dezelfde 756,80 m2) en DOC-005 heeft een extra regel 'Reinigen en controleren "
                            "ventilatierooster 756,80 st'.",
        "convention_indications": [
            "Beide rapporten: 'er geen metingen worden verricht, er geen berekeningen worden uitgevoerd' (p.4).",
            "DOC-005 p.11: 'Reinigen en controleren ventilatierooster 756,80 st' — hetzelfde getal met eenheid 'st'; "
            "756 ventilatieroosters is voor 29 woningen niet aannemelijk. Wijst op een hergebruikte hoeveelheid, geen "
            "telling.",
            "756,80 m2 kozijn tegen 1631,90 m2 metselwerk 'Alle gevels' = 46%; tegen de 3D BAG-buitenwand (1747,3 m2) "
            "43%. Als aanzichtoppervlak van openingen is dat voor deze gevels (visueel en gemeten ~20%) niet "
            "plausibel; als ontwikkeld schilderoppervlak incl. draaiende delen wél denkbaar. Dat is een hypothese, "
            "geen bronfeit.",
        ],
    }
    return {"records": recs, "answers": answers}


# --- dekking per adres ----------------------------------------------------------------------------------------------

def pand_layout_evidence(package_dir, hyp):
    out = {}
    for p in hyp["panden"]:
        pid = p["bag_pand_id"]
        vbos = []
        for f in sorted((package_dir / "raw" / "pdok").glob(f"bag-pand-{pid}__bag-vbo__*.json")):
            v = json.loads(f.read_text(encoding="utf-8"))
            vbos.append({"huisnummer": v["properties"]["huisnummer"], "oppervlakte_m2": v["properties"]["oppervlakte"],
                         "vbo_id": v["properties"]["identificatie"]})
        out[pid] = sorted(vbos, key=lambda v: v["huisnummer"])
    return out


def ratio(a, b):
    return (Decimal(str(a)) / Decimal(str(b))).quantize(Decimal("0.001")) if b else None


def build(run_dir, out_path):
    run_dir = Path(run_dir)
    cov = json.loads((run_dir / "coverage.json").read_text(encoding="utf-8"))
    agg = json.loads((run_dir / "aggregate_v2.json").read_text(encoding="utf-8"))
    det = json.loads((run_dir / "detections_v2.json").read_text(encoding="utf-8"))
    package, pkg, hyp, cand, surfaces, maaiveld = fc.load_package(cov["package"])
    layout = pand_layout_evidence(Path(cov["package"]), hyp)
    walls_by_pand = defaultdict(list)
    for w in agg["walls"]:
        walls_by_pand[w["bag_pand_id"]].append(w)

    # per pand: m² per zijde en reden
    pand_side = {}
    for pid, ws in walls_by_pand.items():
        sides = defaultdict(lambda: defaultdict(Decimal))
        panos = defaultdict(set)
        for w in ws:
            side = "FRONT" if w["zone"] in FRONT_ZONES else "REAR" if w["zone"] in REAR_ZONES else w["zone"]
            sides[side]["TOTAL"] += dec(w["wall_m2"])
            for r, m2 in w["m2_by_reason"].items():
                sides[side][r] += dec(m2)
            panos[side] |= set(w["panoramas_used"])
        pand_side[pid] = (sides, panos)

    def side_rec(sides, panos, side):
        s = sides.get(side)
        if not s:
            return None
        vis = s.get("VISIBLE", Decimal(0))
        return {"wall_m2": str(s["TOTAL"]), "confirmed_visible_m2": str(vis),
                "confirmed_visible_share": str(ratio(vis, s["TOTAL"])),
                "obstructed_m2": {k: str(v) for k, v in s.items() if k in ("GEOMETRY", "VEGETATION_EXG", "MODEL_OCCLUDED_OR_UNUSABLE")},
                "no_panorama_m2": str(s.get("NO_PANORAMA_IN_RANGE", Decimal(0))),
                "panorama_ids": sorted(panos[side])}

    def status(sides):
        f = sides.get("FRONT"); r = sides.get("REAR")
        fs = ratio(f.get("VISIBLE", 0), f["TOTAL"]) if f else Decimal(0)
        rs = ratio(r.get("VISIBLE", 0), r["TOTAL"]) if r else Decimal(0)
        g = sides.get("GABLE")
        gs = ratio(g.get("VISIBLE", 0), g["TOTAL"]) if g else None
        ok = fs >= SUFFICIENT and rs >= SUFFICIENT and (gs is None or gs >= SUFFICIENT)
        if ok:
            return "SUFFICIENT"
        if fs >= SUFFICIENT:
            return "FRONT_ONLY_SUFFICIENT"
        return "INSUFFICIENT"

    # missende zones per band (voor bewonersfoto's)
    def missing_by_band(pid):
        res = defaultdict(Decimal)
        for w in walls_by_pand[pid]:
            side = "FRONT" if w["zone"] in FRONT_ZONES else "REAR" if w["zone"] in REAR_ZONES else w["zone"]
            for b, rr in w["m2_by_band_reason"].items():
                for r, m2 in rr.items():
                    if r != "VISIBLE":
                        res[f"{side}|{b}"] += dec(m2)
        return {k: str(v) for k, v in sorted(res.items()) if v >= PHOTO_MIN_M2}

    pand_records, address_records = {}, []
    for p in hyp["panden"]:
        pid = p["bag_pand_id"]
        sides, panos = pand_side[pid]
        q = agg["per_pand_quantities"].get(pid, {})
        rec = {"bag_pand_id": pid, "addresses": p["numbers_in_scope"], "vbo": layout[pid],
               "end_of_row": "GABLE" in sides,
               "expected_facade_sides": sorted(sides.keys()),
               "front": side_rec(sides, panos, "FRONT"), "rear": side_rec(sides, panos, "REAR"),
               "gable": side_rec(sides, panos, "GABLE"),
               "coverage_status": status(sides), "missing_for_resident_photos_m2": missing_by_band(pid),
               "quantities_by_zone": q}
        pand_records[pid] = rec
    for a in hyp["addresses_found"]:
        pid = a["bag_pand_ids"][0]
        pr = pand_records[pid]
        address_records.append({
            "address": a["weergavenaam"], "bag_pand_id": pid,
            "dwelling_layout": "STACKED_LIKELY_UNCONFIRMED" if len(pr["addresses"]) == 2 else "SINGLE_DWELLING_PAND",
            "dwelling_zone_assignment": "UNRESOLVED — welke woning welke gevelzone/verdieping heeft is niet uit BAG af te "
                                        "leiden; dekking wordt op pandniveau gerapporteerd",
            "expected_facade_sides": pr["expected_facade_sides"],
            "front_coverage": pr["front"], "rear_coverage": pr["rear"], "side_coverage": pr["gable"],
            "coverage_status_pand": pr["coverage_status"],
            "missing_areas_m2_by_side_band": pr["missing_for_resident_photos_m2"]})

    # herhaling: groepen op pandtype (visueel bevestigd: één gespiegeld rijtype; eindpanden wijken af) en
    # vergelijking van de terugliggende hoofdvoorgevelwand (grootste FRONT-wand per pand, ~17 m², 2,9 x 5,9 m)
    def group_of(pid):
        pr = pand_records[pid]
        return ("END_OF_ROW" if pr["end_of_row"] else "MIDDLE") + f"_{len(pr['addresses'])}_ADDR"

    def spread(rows, key):
        vals = sorted(Decimal(r[key]) for r in rows)
        if not vals:
            return None
        med = statistics.median(vals)
        return {"n": len(vals), "min": str(vals[0]), "median": str(med), "max": str(vals[-1])}

    groups = defaultdict(list)
    for pid in pand_records:
        groups[group_of(pid)].append(pid)
    rep = []
    for g, pids in sorted(groups.items()):
        rows = []
        for pid in pids:
            qf = agg["per_pand_quantities"].get(pid, {})
            tot = defaultdict(Decimal)
            for z in FRONT_ZONES:
                for k in ("total_opening_bbox_area_m2", "window_opening_area_m2", "window_sill_m1", "facade_panel_area_m2"):
                    tot[k] += Decimal(qf.get(z, {}).get(k, "0"))
                tot["window_count"] += qf.get(z, {}).get("window_count", 0)
            fronts = [w for w in walls_by_pand[pid] if w["zone"] == "FRONT"]
            main = max(fronts, key=lambda w: w["wall_m2"]) if fronts else None
            mq = defaultdict(Decimal)
            if main:
                for e in main["elements"]:
                    if e["type"] in fc.OPENING_TYPES:
                        mq["main_wall_opening_bbox_m2"] += Decimal(e["area_m2"])
                    if e["type"] == "window":
                        mq["main_wall_window_count"] += 1
                        mq["main_wall_sill_m1"] += Decimal(e["width_m"])
                    if e["type"] == "facade_panel":
                        mq["main_wall_panel_m2"] += Decimal(e["area_m2"])
                vis = Decimal(str(main["m2_by_reason"].get("VISIBLE", 0)))
                mq["main_wall_confirmed_visible_share"] = ratio(vis, main["wall_m2"])
            fr = pand_records[pid]["front"]
            rows.append({"bag_pand_id": pid, "addresses": pand_records[pid]["addresses"],
                         "front_confirmed_visible_share": fr["confirmed_visible_share"] if fr else None,
                         **{k: (str(v) if isinstance(v, Decimal) else v) for k, v in tot.items()},
                         "main_wall_index": main["wall_index"] if main else None,
                         "main_wall_m2": main["wall_m2"] if main else None,
                         **{k: (str(v) if isinstance(v, Decimal) else int(v) if k.endswith("count") else v) for k, v in mq.items()}})
        for key in ("total_opening_bbox_area_m2", "main_wall_opening_bbox_m2"):
            vals = [Decimal(r.get(key, "0")) for r in rows]
            med = statistics.median(vals) if vals else None
            for r in rows:
                v = Decimal(r.get(key, "0"))
                r[f"{key}_rel_median"] = str((v / med).quantize(Decimal("0.01"))) if med else None
                r[f"{key}_outlier"] = bool(med and (v < med * Decimal("0.6") or v > med * Decimal("1.4")))
        rep.append({"group": g, "n_panden": len(pids),
                    "front_opening_bbox_m2": spread(rows, "total_opening_bbox_area_m2"),
                    "front_window_count": spread([{"x": str(r["window_count"])} for r in rows], "x"),
                    "front_sill_m1": spread(rows, "window_sill_m1"),
                    "front_panel_m2": spread(rows, "facade_panel_area_m2"),
                    "main_wall_opening_bbox_m2": spread([r for r in rows if "main_wall_opening_bbox_m2" in r], "main_wall_opening_bbox_m2"),
                    "main_wall_window_count": spread([{"x": str(r.get("main_wall_window_count", 0))} for r in rows], "x"),
                    "panden": rows})

    # totalen per zijde (ontdubbeld)
    tot_q = defaultdict(lambda: defaultdict(Decimal))
    for pid, zs in agg["per_pand_quantities"].items():
        for z, q in zs.items():
            if "|" in z:
                continue
            side = "FRONT" if z in FRONT_ZONES else "REAR" if z in REAR_ZONES else z
            for k, v in q.items():
                tot_q[side][k] += Decimal(str(v))
                tot_q["ALL"][k] += Decimal(str(v))
    tot_cov = defaultdict(lambda: defaultdict(Decimal))
    for pid, (sides, _) in pand_side.items():
        for side, d in sides.items():
            for k, v in d.items():
                tot_cov[side][k] += v
                tot_cov["ALL"][k] += v

    # winst multi-panorama: unie (geometrie + groen) t.o.v. alleen het beste panorama per wand
    single = union = Decimal(0)
    per_n = Counter()
    for w in cov["walls"]:
        pm2 = Decimal(str(w["point_m2"]))
        if w["chosen_panoramas"]:
            single += pm2 * max(p["clear_points"] for p in w["chosen_panoramas"])
        union += pm2 * sum(1 for r in w["point_reason"] if r == "VISIBLE")
        per_n[len(w["chosen_panoramas"])] += 1
    multi_gain = {"visible_m2_single_best_panorama_per_wall": str(single.quantize(D2)),
                  "visible_m2_union_multi_panorama": str(union.quantize(D2)),
                  "gain_m2": str((union - single).quantize(D2)),
                  "walls_by_number_of_panoramas": dict(sorted(per_n.items())),
                  "note": "vóór modelcontrole (alleen 3D-zichtlijn + groenfilter); unie = elk gevelpunt één keer"}

    # v1 met eerlijke namen
    v1 = json.loads((ROOT / "reports" / "quantity" / "facade_element_detection_poc_v1_maldenhof.json").read_text(encoding="utf-8"))
    q1 = fc.empty_q()
    for w in v1["walls"]:
        if w["image_usable_model"]:
            for e in w["elements"]:
                fc.add_el(q1, e)
    att = sum(Decimal(str(w["wall_m2"])) for w in v1["walls"])
    us = sum(Decimal(str(w["wall_m2"])) for w in v1["walls"] if w["image_usable_model"])
    wel = sum(Decimal(str(w["wall_m2"])) for w in v1["walls"] if w["elements"] and w["image_usable_model"])
    v1_relabel = {"wall_m2_attempted": str(att), "wall_m2_model_usable": str(us), "wall_m2_model_unusable": str(att - us),
                  "wall_m2_with_detected_elements": str(wel), **fc.fmt(q1),
                  "visible_opening_ratio_on_model_usable": str(ratio(q1["total_opening_bbox_area_m2"], us)),
                  "note": "v1 noemde total_opening_bbox_area_m2 'frame_area_m2' en deelde door 836,26 m2 incl. 77,81 m2 "
                          "die het model onbruikbaar vond."}

    # benchmarks
    allq = tot_q["ALL"]
    front_vis = tot_cov["FRONT"].get("VISIBLE", Decimal(0))
    benchmarks = [
        {"our_metric": "total_opening_bbox_area_m2 (alle zichtbare gevels)", "our_value": str(allq["total_opening_bbox_area_m2"]),
         "mjop_quantity": "3120/4631 Kozijn buiten hout / schilderwerk kozijn (en draaiende delen), 756,80 m2",
         "classification": "NOT_COMPARABLE",
         "why": "MJOP-grootheid ongedefinieerd (bron noemt geen meetmethode; 'geen metingen verricht'), omvat volgens "
                "omschrijving draaiende delen, en is identiek overgenomen 2023->2026. Onze grootheid is een "
                "aanzicht-bounding-box van openingen op het zichtbare deel. Geen foutpercentage."},
        {"our_metric": "window_sill_m1 (breedte ramen, alle zichtbare gevels)", "our_value": str(allq["window_sill_m1"]),
         "mjop_quantity": "3120 Raamdorpel gres/ijzerklinker, Alle gevels, 281,20 m1",
         "classification": "PARTIAL_COMPARABLE",
         "why": "Zelfde fysieke soort grootheid (strekkende meter onder ramen), maar: niet elk raam heeft een "
                "gres/klinkerdorpel (kozijnen tot maaiveld, deuren, dakkapellen), dekking < 100%, en de MJOP-waarde is "
                "niet gemeten. Beide waarden getoond, geen accuracy-claim."},
        {"our_metric": "facade_panel_area_m2 (voorzijde)", "our_value": str(tot_q["FRONT"]["facade_panel_area_m2"]),
         "mjop_quantity": "4112/4621 Gevelbekleding hout, Voorgevel - gevelbekleding, 332,00 m2",
         "classification": "PARTIAL_COMPARABLE",
         "why": "Zelfde element en zijde; maar het model markeert bekleding als rechthoeken (onderschatting bij "
                "doorlopende/gedeeltelijk verborgen vlakken) en de MJOP-waarde is niet gemeten. Geen accuracy-claim."},
        {"our_metric": "exterior wall m2 (3D BAG LoD2.2, ext. wanden)", "our_value": str(tot_cov["ALL"]["TOTAL"]),
         "mjop_quantity": "2110/4111 Gevelconstructie metselwerk / voegwerk, Alle gevels, 1631,90 m2",
         "classification": "PARTIAL_COMPARABLE",
         "why": "Beide bruto gevel-m2-achtig; MJOP zegt niet of openingen en bekleding zijn afgetrokken. 3D BAG "
                "b3_opp_buitenmuur (1747,3 m2) is een onafhankelijke bron voor dezelfde orde."},
    ]

    review_path = ROOT / "reports" / "quantity" / "facade_detection_review_v2_maldenhof.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else None
    review_summary = None
    if review:
        review_summary = {}
        for rnd in review.get("rounds", {"ALL": ""}):
            its = [it for it in review["images"] if it.get("round", "ALL") == rnd]
            c = Counter()
            for it in its:
                for k in ("visible_actual", "true_positive", "false_positive", "missed", "missed_vegetation",
                          "missed_crop_or_coverage", "missed_model"):
                    c[k] += it[k]
            fpr = Counter(r.split(":")[0].split(" ")[0] for it in its for r in it["false_positive_reasons"])
            review_summary[rnd] = {**c, "images": len(its), "panden": len({it["bag_pand_id"] for it in its}),
                                   "neighbour_block_intrudes_images": sum(1 for it in its if it["neighbour_block_intrudes"]),
                                   "false_positive_reasons": dict(fpr),
                                   "precision": str(ratio(c["true_positive"], c["true_positive"] + c["false_positive"])),
                                   "recall": str(ratio(c["true_positive"], c["visible_actual"])),
                                   "reviewer": review["reviewer"]}

    result = {
        "poc_version": "facade_element_detection_poc_v2", "building_project": "BPRJ-00001 (Maldenhof 240-296, EVEN_ONLY)",
        "label": "ESTIMATED_FROM_PANORAMA — analyse, geen canonical data; openingen = bounding-box-aanzicht",
        "run": {"panoramas_considered": cov["panoramas_considered"], "sample_m": cov["sample_m"],
                "height_method": cov["height_method"], "params": cov["params"],
                "wall_panorama_pairs": sum(len(w["chosen_panoramas"]) for w in cov["walls"]),
                "detection_calls": sum(1 for v in det["pairs"].values() if not v.get("skipped")),
                "usage": det["usage"], "model": fc.MODEL},
        "v1_relabelled": v1_relabel,
        "multi_panorama_gain": multi_gain,
        "v2_wall_m2": agg["wall_m2"],
        "v2_coverage_m2_by_side": {s: {k: str(v) for k, v in d.items()} for s, d in tot_cov.items()},
        "v2_quantities_by_side": {s: {k: str(v) for k, v in d.items()} for s, d in tot_q.items()},
        "v2_visible_opening_ratio_front": str(ratio(tot_q["FRONT"]["total_opening_bbox_area_m2"], front_vis)),
        "coverage_status_counts_panden": dict(Counter(r["coverage_status"] for r in pand_records.values())),
        "coverage_status_counts_addresses": dict(Counter(r["coverage_status_pand"] for r in address_records)),
        "pand_records": pand_records, "address_records": address_records,
        "repetition_groups": rep, "mjop_decomposition": mjop_decomposition(), "benchmarks": benchmarks,
        "detection_review_summary": review_summary,
    }
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default=str(ROOT / "reports" / "quantity" / "facade_element_detection_poc_v2_maldenhof.json"))
    a = ap.parse_args(argv)
    r = build(a.run_dir, a.out)
    print(json.dumps({k: r[k] for k in ("v2_wall_m2", "coverage_status_counts_panden", "v2_visible_opening_ratio_front",
                                        "detection_review_summary")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
