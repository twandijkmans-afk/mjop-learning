"""Beoordeling van de gevelscanner tegen ground truth (facade_ground_truth_v1): HERKENNING en METING strikt gescheiden.

    python -m photo_walk_core.facade_eval ground_truth.json app_export.json [rapport.json]

Herkenning (zonder schaal, in pixels):
  * kozijnen: elke ware buitencontour (FRAME_OUTER) wordt gekoppeld aan hoogstens één voorspeld kozijn (polygoon-IoU >= 0,5).
    Fout-positieven worden ingedeeld als GLASS_AS_FRAME (de voorspelling valt samen met een glasvlak), SPLIT_FRAME (meer voorspellingen
    binnen één waar kozijn) of OTHER. Gemiste kozijnen: FN.
  * glasvlakken en gevelvlak idem (IoU >= 0,5).
  * contournauwkeurigheid: gemiddelde hoekafstand (px) van goed herkende kozijnen.
Meting (alleen voor GOED herkende kozijnen met een rolmaatmeting én een app-maat met status != UNKNOWN):
  * fout in breedte/hoogte (mm en relatief) en bruto oppervlak. Een maat van een glasvlak telt hier nooit mee: dat is een herkenningsfout.

Er worden geen nauwkeurigheidsclaims gedaan: het rapport vermeldt de steekproefgrootte en dat een kleine set niets zegt over gebouwen
in het algemeen. Gebruik deze set nooit om drempels op af te stemmen (data/evaluation-regel uit CLAUDE.md).
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

import jsonschema

from .facade import area, centroid, polygon_iou

SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "facade_ground_truth_v1.schema.json"
MATCH_IOU = 0.5


def gt_errors(gt):
    return [e.message for e in jsonschema.Draft7Validator(json.loads(SCHEMA.read_text())).iter_errors(gt)]


def _pts(p):
    return [(float(a), float(b)) for a, b in p]


def predictions(export):
    """Voorspellingen per foto uit een app-export (photo_walk_capture_v1, 1.0-1.2): kozijnen, glasvlakken, gevelvlak."""
    roles = {o["observation_id"]: (o.get("facade_role") or {}) for o in export.get("observations", [])}
    frames = {}
    for obj in export.get("objects", []):
        for cp in obj.get("corner_pixels", []):
            fr = roles.get(cp["observation_ref"], {})
            if fr.get("role", "FRAME_OUTER") != "FRAME_OUTER":
                continue
            frames.setdefault(cp["frame_id"], []).append({
                "observation_ref": cp["observation_ref"], "polygon": _pts(cp["points"]),
                "outer_contour_status": fr.get("outer_contour_status", "LEGACY"),
                "width_m": obj.get("outer_width_m"), "height_m": obj.get("outer_height_m"), "area_m2": obj.get("gross_area_m2"),
                "dimension_status": obj.get("dimension_status", "UNKNOWN"),
            })
    panes, facades = {}, {}
    for f in (export.get("facade_composition") or {}).get("frames", []):
        for e in f.get("elements", []):
            if e.get("role") == "GLASS_PANE" and not e.get("rejected"):
                panes.setdefault(f["frame_id"], []).append({"element_id": e["element_id"], "polygon": _pts(e["polygon_px"])})
        if f.get("facade_polygon_px"):
            facades[f["frame_id"]] = _pts(f["facade_polygon_px"])
    return frames, panes, facades


def _greedy_match(truth, pred, key=lambda x: x):
    pairs = sorted(((polygon_iou(key(t), key(p)), i, j) for i, t in enumerate(truth) for j, p in enumerate(pred)), reverse=True)
    used_t, used_p, out = set(), set(), []
    for iou, i, j in pairs:
        if iou < MATCH_IOU:
            break
        if i in used_t or j in used_p:
            continue
        used_t.add(i)
        used_p.add(j)
        out.append((i, j, iou))
    return out, [i for i in range(len(truth)) if i not in used_t], [j for j in range(len(pred)) if j not in used_p]


def _corner_error_px(a, b):
    if len(a) != 4 or len(b) != 4:
        return None
    # beste cyclische koppeling (hoekvolgorde kan verschillen)
    best = None
    for s in range(4):
        d = sum(((a[k][0] - b[(k + s) % 4][0]) ** 2 + (a[k][1] - b[(k + s) % 4][1]) ** 2) ** 0.5 for k in range(4)) / 4
        best = d if best is None or d < best else best
    return best


def _inside_fraction(small, big):
    from .facade import convex_intersection_area
    a = area(small)
    return convex_intersection_area(small, big) / a if a > 0 else 0.0


def evaluate(gt, export):
    errs = gt_errors(gt)
    if errs:
        raise ValueError("ground truth voldoet niet aan het schema: " + "; ".join(errs[:5]))
    frames_p, panes_p, facades_p = predictions(export)
    rec = {"frames": {"tp": 0, "fp": 0, "fn": 0, "fp_glass_as_frame": 0, "fp_split_frame": 0, "fp_other": 0,
                      "tp_by_contour_status": {}, "corner_error_px": []},
           "glass_panes": {"tp": 0, "fp": 0, "fn": 0},
           "facade": {"evaluated": 0, "iou": []}}
    meas = {"rows": [], "frames_with_tape": 0, "matched_with_tape": 0, "unmeasured_matched": 0}
    per_photo = []
    for photo in gt["photos"]:
        pid = photo["photo_id"]
        els = photo["elements"]
        gt_frames = [e for e in els if e["role"] == "FRAME_OUTER"]
        gt_panes = [e for e in els if e["role"] == "GLASS_PANE"]
        gt_fac = [e for e in els if e["role"] == "FACADE_GROSS"]
        pf_all = frames_p.get(pid, [])
        # een voorspeld kozijn dat beter op een glasvlak past dan op een buitenkozijn is een GLAS-ALS-KOZIJN-fout (ook als de IoU
        # met het buitenkozijn >= 0,5 is: bij smalle profielen ligt de glasmaat dicht bij de buitenmaat, maar het blijft de verkeerde contour)
        glass_like = set()
        for j, p in enumerate(pf_all):
            bp = max((polygon_iou(p["polygon"], _pts(g["polygon_px"])) for g in gt_panes), default=0.0)
            bf = max((polygon_iou(p["polygon"], _pts(g["polygon_px"])) for g in gt_frames), default=0.0)
            if bp >= MATCH_IOU and bp > bf:
                glass_like.add(j)
        idx = [j for j in range(len(pf_all)) if j not in glass_like]
        pf = [pf_all[j] for j in idx] + [pf_all[j] for j in sorted(glass_like)]
        m, fn, fp = _greedy_match([_pts(e["polygon_px"]) for e in gt_frames], [p["polygon"] for p in pf[:len(idx)]])
        fp = fp + list(range(len(idx), len(pf)))
        rec["frames"]["tp"] += len(m)
        rec["frames"]["fn"] += len(fn)
        photo_rows = {"photo_id": pid, "frames_tp": len(m), "frames_fn": len(fn), "frames_fp": [], "panes": None}
        for i, j, iou in m:
            st = pf[j]["outer_contour_status"]
            rec["frames"]["tp_by_contour_status"][st] = rec["frames"]["tp_by_contour_status"].get(st, 0) + 1
            ce = _corner_error_px(_pts(gt_frames[i]["polygon_px"]), pf[j]["polygon"])
            if ce is not None:
                rec["frames"]["corner_error_px"].append(round(ce, 2))
        matched_gt_of = {j: i for i, j, _ in m}
        for j in fp:
            poly = pf[j]["polygon"]
            kind = "OTHER"
            if j >= len(idx) or any(polygon_iou(poly, _pts(g["polygon_px"])) >= MATCH_IOU for g in gt_panes):
                kind = "GLASS_AS_FRAME"
            else:
                for gi, g in enumerate(gt_frames):
                    if _inside_fraction(poly, _pts(g["polygon_px"])) >= 0.85:
                        others = [k for k, p in enumerate(pf) if k != j and _inside_fraction(p["polygon"], _pts(g["polygon_px"])) >= 0.85]
                        if others or gi in matched_gt_of.values():
                            kind = "SPLIT_FRAME"
                            break
            rec["frames"]["fp"] += 1
            rec["frames"]["fp_" + {"GLASS_AS_FRAME": "glass_as_frame", "SPLIT_FRAME": "split_frame", "OTHER": "other"}[kind]] += 1
            photo_rows["frames_fp"].append({"observation_ref": pf[j]["observation_ref"], "kind": kind})
        pp = panes_p.get(pid, [])
        mp, fnp, fpp = _greedy_match([_pts(e["polygon_px"]) for e in gt_panes], [p["polygon"] for p in pp])
        rec["glass_panes"]["tp"] += len(mp)
        rec["glass_panes"]["fn"] += len(fnp)
        rec["glass_panes"]["fp"] += len(fpp)
        photo_rows["panes"] = {"tp": len(mp), "fn": len(fnp), "fp": len(fpp)}
        if gt_fac:
            rec["facade"]["evaluated"] += 1
            pfac = facades_p.get(pid)
            rec["facade"]["iou"].append(round(polygon_iou(_pts(gt_fac[0]["polygon_px"]), pfac), 4) if pfac else 0.0)
        # meting: alleen goed herkende kozijnen
        tape = {t["element_id"]: t for t in photo["tape_measurements"]}
        meas["frames_with_tape"] += sum(1 for e in gt_frames if e["id"] in tape)
        for i, j, _ in m:
            t = tape.get(gt_frames[i]["id"])
            if not t:
                continue
            meas["matched_with_tape"] += 1
            p = pf[j]
            if p["dimension_status"] == "UNKNOWN" or p["width_m"] is None or p["height_m"] is None:
                meas["unmeasured_matched"] += 1
                continue
            tw, th = Decimal(t["outer_width_m"]), Decimal(t["outer_height_m"])
            pw, ph = Decimal(str(p["width_m"])), Decimal(str(p["height_m"]))
            meas["rows"].append({
                "photo_id": pid, "element_id": gt_frames[i]["id"], "observation_ref": p["observation_ref"],
                "dimension_status": p["dimension_status"], "outer_contour_status": p["outer_contour_status"], "tool": t["tool"],
                "width_error_mm": str((pw - tw) * 1000), "height_error_mm": str((ph - th) * 1000),
                "width_rel_error": str(((pw - tw) / tw).quantize(Decimal("0.0001"))),
                "height_rel_error": str(((ph - th) / th).quantize(Decimal("0.0001"))),
                "area_error_m2": str((pw * ph - tw * th).quantize(Decimal("0.0001"))),
            })
        per_photo.append(photo_rows)
    n_frames = rec["frames"]["tp"] + rec["frames"]["fn"]
    return {
        "report": "facade_eval_v1",
        "dataset_id": gt["dataset_id"], "data_origin": gt.get("data_origin"),
        "recognition": rec,
        "measurement": meas,
        "per_photo": per_photo,
        "sample_size": {"photos": len(gt["photos"]), "true_frames": n_frames, "measured_rows": len(meas["rows"])},
        "claims": ("Geen nauwkeurigheidsclaim. Herkenning en meting zijn apart beoordeeld; een kleine set (en zeker een synthetische) "
                   "zegt niets over de prestaties op gebouwen in het algemeen."),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    r = evaluate(json.loads(Path(sys.argv[1]).read_text()), json.loads(Path(sys.argv[2]).read_text()))
    out = json.dumps(r, indent=2, ensure_ascii=False)
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(out + "\n")
    print(out)
