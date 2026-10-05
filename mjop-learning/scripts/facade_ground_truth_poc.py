"""Facade Ground Truth Quantity PoC v1 — vergelijkt berekende openingen met een echte fysieke maatbasis.

ANALYSE-SCRIPT (proof-of-concept). Leest testcase-manifesten (schemas/facade_ground_truth_case.schema.json) uit
reports/quantity/facade_ground_truth_poc_v1/cases/ en modeldetecties (gecommitte panorama-run v2, of later
detecties op bewonersfoto's). Schrijft reports/quantity/facade_ground_truth_poc_v1.{json,md}.
Geen API-calls, geen netwerk, geen canonical data.

Eén geometrische definitie: PROJECTED_OPENING_BBOX_AREA_IN_FACADE_PLANE
    breedte x hoogte van de omhullende rechthoek van het BUITENKOZIJN (buitenkant kozijnhout tot buitenkant
    kozijnhout; boven tot onderkant onderdorpel, excl. stenen raamdorpel), loodrecht geprojecteerd op het gevelvlak,
    in meters. Een paneel binnen hetzelfde kozijn hoort erbij. Dit is GEEN schilderoppervlak en GEEN
    "kozijn-m²" in MJOP-zin.

Ground truth = handmeting of maatvaste tekening (status MEASURED / DRAWING_DERIVED / PARTIAL). Ontbreekt die:
alle vergelijkingsvelden MISSING en geen accuracy-claim.

Foutklassen per verschil:
    DETECTION_ERROR                 — zichtbaar object gemist, of onterecht object
    MEASUREMENT_PROJECTION_ERROR    — object gevonden, maat wijkt af (rectificatie/registratie/randverfijning)
    COVERAGE_OCCLUSION              — object (deels) niet zichtbaar in het beeld dat het model kreeg
    SEMANTIC_DEFINITION_DIFFERENCE  — model meet iets anders dan de definitie (bv. paneel binnen kozijn apart)
    UNDETERMINED                    — de feiten om te classificeren ontbreken (niet gokken)

    python scripts/facade_ground_truth_poc.py [--cases DIR] [--out-json F] [--out-md F]
"""

import argparse
import json
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import jsonschema
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "reports" / "quantity" / "facade_ground_truth_poc_v1" / "cases"
SCHEMA = ROOT / "schemas" / "facade_ground_truth_case.schema.json"
OUT_JSON = ROOT / "reports" / "quantity" / "facade_ground_truth_poc_v1.json"
OUT_MD = ROOT / "reports" / "quantity" / "facade_ground_truth_poc_v1.md"
DEFINITION = "PROJECTED_OPENING_BBOX_AREA_IN_FACADE_PLANE"
MISSING = "MISSING"
OPENING_TYPES = ("window_frame", "door", "garage_door", "dormer")
MODEL_TYPE_MAP = {"window": "window_frame", "door": "door", "garage_door": "garage_door", "dormer": "dormer",
                  "facade_panel": "facade_panel"}
PANEL_IN_FRAME_GAP_M = Decimal("0.10")      # verticale naad tussen paneel en raam binnen één kozijn
PANEL_IN_FRAME_OVERLAP = Decimal("0.80")    # paneelbreedte die binnen de raambreedte valt
Q2, Q3 = Decimal("0.01"), Decimal("0.001")


def d(x):
    return Decimal(str(x))


def q2(x):
    return x.quantize(Q2, rounding=ROUND_HALF_UP)


# --- manifesten -----------------------------------------------------------------------------------------------------

def load_cases(cases_dir=CASES_DIR):
    schema = json.loads(Path(SCHEMA).read_text(encoding="utf-8"))
    cases = []
    for f in sorted(Path(cases_dir).glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        jsonschema.validate(c, schema)
        check_status_consistency(c)
        cases.append(c)
    return cases


def check_status_consistency(case):
    for s in case["scopes"]:
        st, objs = s["ground_truth_status"], s["measured_objects"]
        if st == "MISSING" and objs:
            raise ValueError(f"{case['case_id']}/{s['scope_id']}: status MISSING maar er zijn gemeten objecten")
        if st in ("MEASURED", "DRAWING_DERIVED", "PARTIAL") and not objs:
            raise ValueError(f"{case['case_id']}/{s['scope_id']}: status {st} zonder gemeten objecten")
        if st == "DRAWING_DERIVED" and any(o["measurement_source"] != "DRAWING" for o in objs):
            raise ValueError(f"{case['case_id']}/{s['scope_id']}: DRAWING_DERIVED met niet-tekening-bron")
        if st == "MEASURED" and any(o["measurement_source"] == "DRAWING" for o in objs):
            raise ValueError(f"{case['case_id']}/{s['scope_id']}: MEASURED met tekening-bron (gebruik PARTIAL of DRAWING_DERIVED)")


def gt_area(o):
    return q2(d(o["width_m"]) * d(o["height_m"]) * o["count"])


# --- modeldetecties -------------------------------------------------------------------------------------------------

def load_model_elements(scope, case):
    """-> lijst elementen {model_element_id, type, level, box_m[x0,y0,x1,y1], width_m, height_m, partially_hidden,
    image_id} of None als er geen modelbron is."""
    ms = scope["model_source"]
    if ms["status"] != "PRESENT" or not ms.get("ref"):
        return None
    data = json.loads((ROOT / ms["ref"]).read_text(encoding="utf-8"))
    if ms["source_type"] == "PANORAMA_V2_COMMITTED":
        wall = next(w for w in data["walls"]
                    if w["bag_pand_id"] == case["bag_pand_id"] and w["wall_index"] == ms["wall_index"])
        raw = [{**e, "level": e.get("band"), "image_id": e.get("pano_id")} for e in wall["elements"]]
        prefix = f"{case['bag_pand_id']}_w{ms['wall_index']:02d}"
    else:  # RESIDENT_PHOTO_DETECTION: {"elements":[{type, level, box_m, partially_hidden, image_id}]}
        raw = data["elements"]
        prefix = f"{case['case_id']}_{scope['scope_id']}"
    out = []
    for e in sorted(raw, key=lambda e: (e["box_m"][1], e["box_m"][0])):
        t = MODEL_TYPE_MAP.get(e["type"])
        if t is None:
            continue
        x0, y0, x1, y1 = (d(round(v, 3)) for v in e["box_m"])
        out.append({"model_element_id": f"{prefix}_e{len(out):02d}", "type": t, "level": e.get("level"),
                    "box_m": [x0, y0, x1, y1], "width_m": x1 - x0, "height_m": y1 - y0,
                    "partially_hidden": bool(e.get("partially_hidden")), "image_id": e.get("image_id")})
    return out


def panel_in_frame_pairs(elements):
    """Model-panelen die volgens de definitie bij het kozijn horen: een borstweringspaneel DIRECT ONDER een raam
    (naad <= 0,10 m) en binnen de raambreedte (>= 80% overlap). Panelen boven een raam (gevelbekleding) horen er
    niet bij. Heuristiek op de detectiegeometrie zelf; de ground truth (includes_panel_in_frame) is leidend.
    -> {panel_id: window_id}. Wandcoördinaten: y loopt van boven naar beneden."""
    wins = [e for e in elements if e["type"] == "window_frame"]
    pairs = {}
    for p in (e for e in elements if e["type"] == "facade_panel"):
        px0, py0, px1, py1 = p["box_m"]
        for w in wins:
            wx0, wy0, wx1, wy1 = w["box_m"]
            overlap = max(Decimal(0), min(px1, wx1) - max(px0, wx0))
            below = abs(py0 - wy1) <= PANEL_IN_FRAME_GAP_M and py1 > wy1
            if p["width_m"] > 0 and overlap / p["width_m"] >= PANEL_IN_FRAME_OVERLAP and below:
                pairs[p["model_element_id"]] = w["model_element_id"]
                break
    return pairs


def aligned_box(window, panels):
    x0, y0, x1, y1 = window["box_m"]
    for p in panels:
        x0, y0 = min(x0, p["box_m"][0]), min(y0, p["box_m"][1])
        x1, y1 = max(x1, p["box_m"][2]), max(y1, p["box_m"][3])
    return [x0, y0, x1, y1]


# --- vergelijking ---------------------------------------------------------------------------------------------------

def compare_scope(case, scope):
    gt_status = scope["ground_truth_status"]
    model = load_model_elements(scope, case)
    res = {"case_id": case["case_id"], "scope_id": scope["scope_id"], "facade_side": scope["facade_side"],
           "definition": DEFINITION, "ground_truth_status": gt_status,
           "model_source": scope["model_source"]["source_type"],
           "model_source_status": scope["model_source"]["status"]}
    gt_objs = [o for o in scope["measured_objects"] if o["type"] in OPENING_TYPES]

    # modelkant (los van ground truth te rapporteren)
    if model is None:
        res["model"] = MISSING
    else:
        pif = panel_in_frame_pairs(model)
        openings = [e for e in model if e["type"] in OPENING_TYPES]
        by_win = defaultdict(list)
        for pid, wid in pif.items():
            by_win[wid].append(next(e for e in model if e["model_element_id"] == pid))
        for e in openings:
            b = aligned_box(e, by_win.get(e["model_element_id"], []))
            e["aligned_box_m"] = b
            e["aligned_area_m2"] = q2((b[2] - b[0]) * (b[3] - b[1]))
            e["raw_area_m2"] = q2(e["width_m"] * e["height_m"])
        res["model"] = {
            "opening_count": len(openings),
            "total_m2_raw": str(sum((e["raw_area_m2"] for e in openings), Decimal(0))),
            "total_m2_definition_aligned": str(sum((e["aligned_area_m2"] for e in openings), Decimal(0))),
            "panels_merged_into_frame": sorted(pif),
            "elements": [{"model_element_id": e["model_element_id"], "type": e["type"], "level": e["level"],
                          "width_m": str(q2(e["width_m"])), "height_m": str(q2(e["height_m"])),
                          "raw_area_m2": str(e["raw_area_m2"]), "aligned_area_m2": str(e["aligned_area_m2"]),
                          "partially_hidden": e["partially_hidden"], "image_id": e["image_id"]} for e in openings]}

    if gt_status == "MISSING":
        res["ground_truth"] = MISSING
        res["comparison"] = MISSING
        res["accuracy_claim"] = False
        return res
    res["ground_truth"] = {"object_count": sum(o["count"] for o in gt_objs),
                           "total_m2": str(sum((gt_area(o) for o in gt_objs), Decimal(0))),
                           "objects": [{"object_id": o["object_id"], "type": o["type"], "level": o["level"],
                                        "width_m": o["width_m"], "height_m": o["height_m"], "count": o["count"],
                                        "area_m2": str(gt_area(o)), "measurement_source": o["measurement_source"]}
                                       for o in gt_objs]}
    if model is None:
        res["comparison"] = MISSING
        res["accuracy_claim"] = False
        return res
    res["comparison"] = match_and_score(scope, gt_objs, [e for e in model if e["type"] in OPENING_TYPES])
    res["accuracy_claim"] = res["comparison"]["status"] == "COMPLETE"
    return res


def match_and_score(scope, gt_objs, openings):
    manual = {m["model_element_id"]: m for m in scope.get("manual_matches", [])}
    gt_by_id = {o["object_id"]: o for o in gt_objs}
    pairs, fp, unresolved = [], [], []
    used_gt = set()
    # 1. handmatige koppelingen (door een mens vastgelegd)
    for e in openings:
        m = manual.get(e["model_element_id"])
        if m is None:
            continue
        if m["object_id"] is None:
            fp.append((e, m.get("cause", "UNDETERMINED")))
        else:
            pairs.append((gt_by_id[m["object_id"]], e)); used_gt.add(m["object_id"])
    rest_model = [e for e in openings if e["model_element_id"] not in manual]
    # 2. per (laag, type): bij gelijke aantallen op volgorde van links naar rechts; anders handmatig nodig
    groups = defaultdict(lambda: ([], []))
    for o in gt_objs:
        if o["object_id"] not in used_gt:
            groups[(o["level"], o["type"])][0].append(o)
    for e in rest_model:
        groups[(e["level"], e["type"])][1].append(e)
    misses = []
    for key, (g, m) in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        g = sorted(g, key=lambda o: o["order_from_left"])
        m = sorted(m, key=lambda e: e["box_m"][0])
        if len(g) == len(m):
            pairs += list(zip(g, m))
        elif not g:
            fp += [(e, "UNDETERMINED") for e in m]
        elif not m:
            misses += g
        else:
            unresolved.append({"level": key[0], "type": key[1], "gt_object_ids": [o["object_id"] for o in g],
                               "model_element_ids": [e["model_element_id"] for e in m]})
    if unresolved:
        return {"status": "NEEDS_MANUAL_MATCH", "unresolved_groups": unresolved,
                "note": "aantallen per laag/type verschillen; leg manual_matches vast in het manifest (geen gok)"}
    gt_count = sum(o["count"] for o in gt_objs)
    tp = len(pairs)
    per_obj, cause_m2 = [], defaultdict(Decimal)
    for o, e in pairs:
        ga = gt_area(o)
        da, ra = e["aligned_area_m2"], e["raw_area_m2"]
        rest = da - ga
        rest_cause = "COVERAGE_OCCLUSION" if e["partially_hidden"] else "MEASUREMENT_PROJECTION_ERROR"
        cause_m2[rest_cause] += rest
        per_obj.append({"object_id": o["object_id"], "model_element_id": e["model_element_id"],
                        "gt_width_m": o["width_m"], "gt_height_m": o["height_m"], "gt_area_m2": str(ga),
                        "model_width_m": str(q2(e["aligned_box_m"][2] - e["aligned_box_m"][0])),
                        "model_height_m": str(q2(e["aligned_box_m"][3] - e["aligned_box_m"][1])),
                        "model_area_m2_raw": str(ra), "model_area_m2_aligned": str(da),
                        "diff_m2_aligned": str(rest), "diff_cause": rest_cause,
                        "semantic_definition_difference_m2": str(ra - da)})
    miss_rows = []
    for o in misses:
        vis = o.get("visible_in_images") or {}
        imgs = {e["image_id"] for e in openings}
        flags = [vis[i] for i in imgs if i in vis]
        cause = ("COVERAGE_OCCLUSION" if flags and not any(flags) else
                 "DETECTION_ERROR" if flags and all(flags) else "UNDETERMINED")
        cause_m2[cause] -= gt_area(o)
        miss_rows.append({"object_id": o["object_id"], "gt_area_m2": str(gt_area(o)), "cause": cause})
    fp_rows = []
    for e, cause in fp:
        cause_m2[cause] += e["aligned_area_m2"]
        fp_rows.append({"model_element_id": e["model_element_id"], "area_m2": str(e["aligned_area_m2"]), "cause": cause})
    gt_total = sum((gt_area(o) for o in gt_objs), Decimal(0))
    model_total = sum((e["aligned_area_m2"] for e in openings), Decimal(0))
    model_total_raw = sum((e["raw_area_m2"] for e in openings), Decimal(0))
    diff = model_total - gt_total
    return {
        "status": "COMPLETE",
        "ground_truth_object_count": gt_count, "true_positives": tp, "false_positives": len(fp),
        "misses": len(misses),
        "precision": str((Decimal(tp) / Decimal(tp + len(fp))).quantize(Q3)) if tp + len(fp) else None,
        "recall": str((Decimal(tp) / Decimal(gt_count)).quantize(Q3)) if gt_count else None,
        "ground_truth_total_m2": str(gt_total),
        "calculated_total_m2_definition_aligned": str(model_total),
        "calculated_total_m2_raw": str(model_total_raw),
        "absolute_difference_m2": str(diff),
        "percentage_difference": str((diff / gt_total * 100).quantize(Q2)) if gt_total else None,
        "difference_by_cause_m2": {k: str(q2(v)) for k, v in sorted(cause_m2.items())},
        "semantic_definition_difference_m2": str(model_total_raw - model_total),
        "note_semantic": "verschil tussen ruwe modeloutput en de definitie (panelen binnen kozijn apart gemeten); "
                         "valt buiten het definitie-verschil hierboven",
        "matched_objects": per_obj, "missed_objects": miss_rows, "false_positive_objects": fp_rows,
    }


# --- bewonersfoto -> gevelvlak (voor als foto's binnenkomen) ---------------------------------------------------------

def homography(src_px, dst_m):
    """DLT-homografie uit 4 (of meer) puntparen: pixel (x,y) in de foto -> meter (u,v) in het gevelvlak.
    De 4 punten zijn door een mens aangewezen hoeken van een bekend rechthoekig vlak (bv. een gemeten kozijn of de
    gevelhoeken uit 3D BAG). Zonder zo'n referentiemaat bestaat er geen schaal."""
    A = []
    for (x, y), (u, v) in zip(src_px, dst_m):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vt = np.linalg.svd(np.array(A, float))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2]


def to_facade_m(H, pts_px):
    p = np.c_[np.asarray(pts_px, float), np.ones(len(pts_px))] @ H.T
    return p[:, :2] / p[:, 2:3]


def box_px_to_facade_m(H, box_px):
    x0, y0, x1, y1 = box_px
    c = to_facade_m(H, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return [float(c[:, 0].min()), float(c[:, 1].min()), float(c[:, 0].max()), float(c[:, 1].max())]


# --- rapport --------------------------------------------------------------------------------------------------------

def build(cases_dir=CASES_DIR):
    cases = load_cases(cases_dir)
    scopes = [compare_scope(c, s) for c in cases for s in c["scopes"]]
    overall = "MISSING" if all(s["ground_truth"] == MISSING for s in scopes) else "PARTIAL_OR_COMPLETE"
    return {"poc_version": "facade_ground_truth_poc_v1", "definition": DEFINITION,
            "definition_text": " ".join(" ".join(__doc__.split("Eén geometrische definitie: ")[1]
                                                .split("\n\nGround truth")[0].split("\n")[1:]).split()),
            "ground_truth_overall": overall,
            "accuracy_claim": any(s["accuracy_claim"] for s in scopes),
            "cases": [{"case_id": c["case_id"], "bag_pand_id": c["bag_pand_id"], "addresses": c["addresses"],
                       "selection_reason": c["selection_reason"]} for c in cases],
            "scopes": scopes}


def fmt(v):
    return v if isinstance(v, str) else ("—" if v is None else str(v))


def render_md(r):
    L = ["# Facade Ground Truth Quantity PoC v1 — resultaten", "",
         "Gegenereerd door `scripts/facade_ground_truth_poc.py` uit de manifesten in "
         "`reports/quantity/facade_ground_truth_poc_v1/cases/`. Toelichting, protocol en keuzes: "
         "`docs/facade_ground_truth_poc_v1.md`.", "",
         f"- Definitie: **{r['definition']}** — {r['definition_text']}",
         f"- Ground truth: **{r['ground_truth_overall']}**; accuracy-claim: **{'ja' if r['accuracy_claim'] else 'NEE'}**", "",
         "| Case | Scope | GT-status | Model | GT-objecten | TP | FP | Gemist | Precision | Recall | GT m² | Berekend m² | Δ m² | Δ % |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in r["scopes"]:
        c = s["comparison"]
        m = s["model"]
        model_txt = MISSING if m == MISSING else f"{m['opening_count']} openingen, {m['total_m2_definition_aligned']} m²"
        if c == MISSING or c.get("status") != "COMPLETE":
            st = MISSING if c == MISSING else c["status"]
            L.append(f"| {s['case_id']} | {s['scope_id']} | {s['ground_truth_status']} | {model_txt} | {st} | {st} | {st} | "
                     f"{st} | {st} | {st} | {st} | {st} | {st} | {st} |")
        else:
            L.append(f"| {s['case_id']} | {s['scope_id']} | {s['ground_truth_status']} | {model_txt} | "
                     f"{c['ground_truth_object_count']} | {c['true_positives']} | {c['false_positives']} | {c['misses']} | "
                     f"{fmt(c['precision'])} | {fmt(c['recall'])} | {c['ground_truth_total_m2']} | "
                     f"{c['calculated_total_m2_definition_aligned']} | {c['absolute_difference_m2']} | {fmt(c['percentage_difference'])} |")
    L += ["", "Verschil per oorzaak (alleen bij COMPLETE):", ""]
    for s in r["scopes"]:
        c = s["comparison"]
        if c != MISSING and c.get("status") == "COMPLETE":
            L.append(f"- {s['case_id']}/{s['scope_id']}: " + ", ".join(f"{k} {v} m²" for k, v in c["difference_by_cause_m2"].items()))
    if not any(s["comparison"] != MISSING and s["comparison"].get("status") == "COMPLETE" for s in r["scopes"]):
        L.append("- MISSING — er is nog geen echte meting of maatvaste tekening; er wordt geen nauwkeurigheid geclaimd.")
    L += ["", "Modelkant per scope (bestaande gecommitte detecties; geen nieuwe API-calls):", ""]
    for s in r["scopes"]:
        m = s["model"]
        if m == MISSING:
            L.append(f"- {s['case_id']}/{s['scope_id']}: MISSING")
        else:
            L.append(f"- {s['case_id']}/{s['scope_id']}: {m['opening_count']} openingen, ruw {m['total_m2_raw']} m², "
                     f"volgens definitie {m['total_m2_definition_aligned']} m² (panelen binnen kozijn samengevoegd: "
                     f"{len(m['panels_merged_into_frame'])})")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", default=str(CASES_DIR))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    a = ap.parse_args(argv)
    r = build(a.cases)
    Path(a.out_json).write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    Path(a.out_md).write_text(render_md(r), encoding="utf-8")
    print(json.dumps({"ground_truth_overall": r["ground_truth_overall"], "accuracy_claim": r["accuracy_claim"],
                      "scopes": len(r["scopes"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
