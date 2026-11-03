"""Export van een meetresultaat (JSON + CSV). Schrijft alleen naar een expliciet opgegeven map BUITEN de repository,
tenzij `allow_in_repo=True` (alleen voor de synthetische voorbeelden)."""
import csv
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def canonical_json(rec):
    return json.dumps(rec, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def record_sha256(rec):
    return hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def export_record(rec, out_dir, stem="photo_walk_result", allow_in_repo=False):
    out = Path(out_dir).resolve()
    if not allow_in_repo and (out == REPO_ROOT or REPO_ROOT in out.parents):
        raise ValueError("uitvoer binnen de repository is niet toegestaan (gebruik een map daarbuiten)")
    if rec.get("data_origin") != "SIMULATION" and allow_in_repo:
        raise ValueError("alleen synthetische records mogen in de repository")
    out.mkdir(parents=True, exist_ok=True)
    jp, cp = out / f"{stem}.json", out / f"{stem}.csv"
    jp.write_text(canonical_json(rec), encoding="utf-8")
    with cp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["provisional_object_id", "dimension_status", "outer_width_m", "outer_height_m", "gross_area_m2", "area_sigma_m2",
                    "scale_method", "level", "review_required", "observations", "flags"])
        for o in rec["objects"]:
            u = o["measurement_uncertainty"]
            w.writerow([o["provisional_object_id"], o["dimension_status"], o["outer_width_m"] or "UNKNOWN", o["outer_height_m"] or "UNKNOWN",
                        o["gross_area_m2"] or "UNKNOWN", u["area_sigma_m2"] if u else "", o["measurement_source"]["scale_method"],
                        o["measurement_source"]["level"] or "", o["review_required"], ";".join(o["observation_refs"]),
                        ";".join(f["code"] for f in o["quality_flags"])])
    return jp, cp
