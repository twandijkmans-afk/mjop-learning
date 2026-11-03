"""Samenstellen en valideren van een `photo_walk_capture_v1`-record."""
import json
from pathlib import Path

import jsonschema
import numpy as np

from .config import DEFAULT, MEASUREMENT_METHOD_VERSION, PROCESSING_VERSION, Config

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "photo_walk_capture_v1.schema.json"
RETENTION_PROPOSAL = ("VOORSTEL (nog niet vastgesteld): ruwe beelden en dieptekaarten blijven alleen op het toestel; verwijderen na afronding van de "
                      "review of uiterlijk 30 dagen na de scan; het exportrecord (zonder media, zonder locatie) mag bij het dossier blijven.")


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_errors(record):
    v = jsonschema.Draft7Validator(load_schema())
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in v.iter_errors(record))


def scan_label(observations):
    src = {o.corner_source for o in observations}
    if not src:
        return "NO_OBSERVATIONS"
    if src <= {"AUTO_DETECTED_CONFIRMED"}:
        return "AUTOMATIC_CANDIDATES_HUMAN_CONFIRMED"
    if src <= {"AUTO_DETECTED_UNCONFIRMED"}:
        return "AUTOMATIC_UNREVIEWED"
    return "SEMI_AUTOMATIC"     # elke handmatige of gecorrigeerde hoek maakt de scan semi-automatisch; geen claim van automatische herkenning


def _scale_method(objects):
    m = {o["measurement_source"]["scale_method"] for o in objects if o["measurement_source"]["scale_method"] != "NONE"}
    return "NONE" if not m else (m.pop() if len(m) == 1 else "MIXED")


def build_record(session, views, observations, references, result, coverage=None, cfg: Config = DEFAULT):
    intr, ids = [], {}
    for v in views:
        key = (v.intrinsics.fx, v.intrinsics.fy, v.intrinsics.cx, v.intrinsics.cy, v.intrinsics.width, v.intrinsics.height)
        if key not in ids:
            ids[key] = f"K{len(ids) + 1}"
            intr.append({"intrinsics_id": ids[key], "fx": key[0], "fy": key[1], "cx": key[2], "cy": key[3], "width": key[4], "height": key[5]})
    objects = [{k: v for k, v in o.items() if not k.startswith("_")} for o in result["objects"]]
    rec = {
        "contract": "photo_walk_capture_v1", "contract_version": "1.0.0",
        "session_id": session["session_id"], "building_id": session["building_id"], "facade_id": session["facade_id"],
        "platform": session["platform"], "device_model": session["device_model"], "data_origin": session["data_origin"],
        "validation_level": session["validation_level"],
        "sensor_capabilities": {k: bool(session["capabilities"].get(k, False)) for k in
                                ("lidar", "scene_depth", "depth_api", "ar_world_tracking", "metric_tracking", "camera_intrinsics_available")},
        "coordinate_system": {
            "pixel": "origin top-left corner of top-left pixel; u right, v down; unit px",
            "camera": "OpenCV: x right, y down, z forward; unit m",
            "world": "right-handed, Y up (gravity aligned), unit m; origin = AR session start",
            "pose": "camera_to_world 4x4 row-major as 16 numbers; x_world = R x_camera + t",
            "depth": "depth_z: distance along the optical axis in m; 0/NaN invalid",
            "units": "m, px, m2, degrees"},
        "camera_intrinsics": intr,
        "camera_poses": [{"frame_id": v.frame_id, "intrinsics_id": ids[(v.intrinsics.fx, v.intrinsics.fy, v.intrinsics.cx, v.intrinsics.cy, v.intrinsics.width, v.intrinsics.height)],
                          "camera_to_world": [round(float(x), 6) for x in v.pose.reshape(-1)], "pose_valid": bool(v.pose_valid)} for v in views],
        "capture_timestamp": min((v.timestamp for v in views), default="1970-01-01T00:00:00Z"),
        "image_refs": [{"frame_id": v.frame_id, "ref": v.image_ref or f"local://{v.frame_id}", "timestamp": v.timestamp} for v in views],
        "depth_refs": [{"frame_id": v.frame_id, "ref": v.depth_ref or f"local://{v.frame_id}.depth", "width": int(v.depth.shape[1]), "height": int(v.depth.shape[0]),
                        "unit": "m", "convention": "depth_z"} for v in views if v.depth is not None],
        "tracking_quality": [{"frame_id": v.frame_id, "state": v.tracking_state} for v in views],
        "measurement_mode": result["mode"],
        "scale_method": _scale_method(objects),
        "scale_evidence": [{"object": o["provisional_object_id"], "dimension_status": o["dimension_status"], **o["measurement_source"]["scale_evidence"]}
                           for o in objects if o["measurement_source"]["scale_evidence"]],
        "measurement_method_version": MEASUREMENT_METHOD_VERSION, "processing_version": PROCESSING_VERSION,
        "thresholds": cfg.as_dict(),
        "references": [{"reference_id": r["reference_id"], "frame_id": r["frame_id"], "p1_px": [float(x) for x in r["p1_px"]],
                        "p2_px": [float(x) for x in r["p2_px"]], "distance_m": float(r["distance_m"]), "distance_sigma_m": r.get("distance_sigma_m"),
                        "plane_id": r.get("plane_id"), "entered_by": r.get("entered_by", "onbekend"),
                        "anchor_px": None if r.get("anchor_px") is None else np.asarray(r["anchor_px"], float).tolist()} for r in references],
        "observations": [{"observation_id": o.observation_id, "frame_id": o.frame_id, "corner_source": o.corner_source,
                          "obstruction_reported": bool(o.obstruction_reported)} for o in observations],
        "objects": objects, "coverage": coverage, "summary": result["summary"], "scan_label": scan_label(observations),
        "privacy": {"raw_media_included": False, "external_calls": 0, "location_stored": False, "processing": "LOCAL_ONLY",
                    "retention_proposal": RETENTION_PROPOSAL},
        "invariants": dict(result["invariants"]),
    }
    errs = schema_errors(rec)
    if errs:
        raise ValueError("record voldoet niet aan photo_walk_capture_v1: " + "; ".join(errs[:8]))
    return rec
