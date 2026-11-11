"""Veldvalidatie van Gevelscanner 2.0: vergelijkt een gevelinventaris van de app (`mjop_gevel_inventory_v1`) met handmatige
referentiemetingen (`gevelscan_reference_v1`).

    python -m photo_walk_core.gevel_eval referentie.json inventaris.json [rapport.json]

Meet per goed gekoppeld kozijn de fout in breedte, hoogte, oppervlak en glasoppervlak en het verschil in draaiende delen; per gevel de fout
in het aantal kozijnen; en over alles het aandeel dubbel getelde en gemiste kozijnen plus objecten die geen kozijn bleken.

Dit script geeft GEEN oordeel "goed/fout" en kent GEEN acceptatiegrenzen: die moeten na de veldmetingen door de eigenaar worden vastgesteld.
Het rapport noemt altijd de steekproefgrootte en de herkomst van de referentie. Synthetische referenties bewijzen niets over echte gevels.
Deterministisch, alleen standaardbibliotheek + jsonschema; geen netwerk.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import jsonschema

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


def _summary(values: list[float]) -> dict:
    """Beschrijvende statistiek zonder oordeel; None bij een lege steekproef."""
    if not values:
        return {"n": 0, "mean": None, "median": None, "mean_abs": None, "max_abs": None}
    return {"n": len(values), "mean": round(statistics.fmean(values), 5), "median": round(statistics.median(values), 5),
            "mean_abs": round(statistics.fmean(abs(v) for v in values), 5), "max_abs": round(max(abs(v) for v in values), 5)}


def evaluate(reference: dict, inventory: dict) -> dict:
    jsonschema.Draft7Validator(_schema("gevelscan_reference_v1")).validate(reference)
    jsonschema.Draft7Validator(_schema("mjop_gevel_inventory_v1")).validate(inventory)
    objects = {o["object_id"]: (f["facade_id"], o) for f in inventory["facades"] for o in f["objects"]}
    inv_facades = {f["facade_id"]: f for f in inventory["facades"]}
    rows, used = [], {}
    errs = {k: [] for k in ("width_m", "height_m", "area_m2", "glass_area_m2", "width_rel", "height_rel", "area_rel", "glass_area_rel", "operable_parts", "fixed_parts")}
    n_ref = matched = double = missed = unknown_ids = 0
    count_errors = []
    for fac in reference["facades"]:
        for fr in fac["frames"]:
            n_ref += 1
            ids = [i for i in fr["matched_object_ids"] if i in objects]
            unknown_ids += len(fr["matched_object_ids"]) - len(ids)
            for i in ids:
                used[i] = used.get(i, 0) + 1
            row = {"reference_id": fr["reference_id"], "facade_id": fac["facade_id"], "object_ids": ids,
                   "result": "MISSED" if not ids else ("DOUBLE_COUNTED" if len(ids) > 1 else "MATCHED"), "errors": {}}
            if not ids:
                missed += 1
            elif len(ids) > 1:
                double += 1
            else:
                matched += 1
                o = objects[ids[0]][1]
                row["outcome"] = o["outcome"]
                row["dimension_status"] = o["dimension_status"]

                def diff(key, ref, app, rel=True):
                    if ref is None or app is None:
                        return
                    d = app - ref
                    row["errors"][key] = round(d, 5)
                    errs[key].append(d)
                    if rel and ref > 0:
                        errs[key.replace("_m2", "").replace("_m", "") + "_rel"].append(d / ref)

                w, h = fr["width_m"], fr["height_m"]
                diff("width_m", w, o["width"]["value"])
                diff("height_m", h, o["height"]["value"])
                diff("area_m2", w * h if w is not None and h is not None else None, o["area"]["value"])
                diff("glass_area_m2", fr["glass_area_m2"], o["glass_area"]["value"])
                diff("operable_parts", fr["operable_parts"], o["operable_parts"]["value"], rel=False)
                diff("fixed_parts", fr["fixed_parts"], o["fixed_parts"]["value"], rel=False)
            rows.append(row)
        if fac["frames_complete"]:
            app = inv_facades.get(fac["facade_id"], {}).get("totals", {}).get("frame_count", {}).get("value")
            count_errors.append({"facade_id": fac["facade_id"], "reference": len(fac["frames"]), "app": app,
                                 "error": None if app is None else app - len(fac["frames"])})
    ref_facades = {f["facade_id"] for f in reference["facades"] if f["frames_complete"]}
    spurious = sorted(i for i, (fid, _) in objects.items() if i not in used and fid in ref_facades)
    return {
        "report": "gevelscan_field_evaluation_v1",
        "reference": {"dataset_id": reference["dataset_id"], "data_origin": reference["data_origin"], "purpose": reference["purpose"],
                      "measured_by": reference["measured_by"], "tool": reference["tool"]},
        "inventory": {"inventory_id": inventory["inventory_id"], "pipeline": inventory["versions"]["pipeline"],
                      "thresholds_status": inventory["versions"]["thresholds_status"]},
        "sample": {"reference_frames": n_ref, "matched": matched, "double_counted": double, "missed": missed,
                   "spurious_objects": len(spurious), "unknown_object_ids_in_reference": unknown_ids},
        "rates": {"double_counted": round(double / n_ref, 4) if n_ref else None, "missed": round(missed / n_ref, 4) if n_ref else None},
        "errors": {k: _summary(v) for k, v in errs.items()},
        "frame_count_per_facade": count_errors,
        "spurious_object_ids": spurious,
        "frames": rows,
        "verdict": None,
        "note": ("Geen oordeel en geen acceptatiegrenzen: beschrijvende cijfers over deze steekproef. "
                 + ("SYNTHETISCHE referentie: zegt niets over echte gevels of echte LiDAR. " if reference["data_origin"] != "REAL_BUILDING" else "")
                 + "Een kleine steekproef is geen nauwkeurigheidsclaim."),
    }


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print(__doc__)
        return 2
    report = evaluate(json.loads(Path(argv[1]).read_text()), json.loads(Path(argv[2]).read_text()))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if len(argv) == 4:
        out = Path(argv[3]).resolve()
        if Path(__file__).resolve().parents[3] in out.parents:
            print("Weigering: schrijf het rapport buiten de repository.")
            return 2
        out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
