"""Meetdiagnose-export: klein JSON-bestand met numerieke diagnostiek van een kozijnmeting (geen foto's, geen puntenwolken, geen absolute pose/locatie)."""
import datetime
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import numpy as np

from .config import DEFAULT, PROCESSING_VERSION

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "photo_walk_measure_diagnostics_v1.schema.json"
FORBIDDEN_KEYS = ("image", "photo", "pointcloud", "point_cloud", "latitude", "longitude", "gps", "location", "pose", "points_xyz")


def json_safe(x):
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, np.ndarray):
        return json_safe(x.tolist())
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def build(result, *, session_id, observation_id, view, corners_px, status, feedback, platform="SIMULATION", data_origin="SIMULATION", app_build=PROCESSING_VERSION,
          cfg=DEFAULT, created_utc=None):
    w, h = result.width_m, result.height_m
    area = None
    if result.ok and w is not None and h is not None:
        wm, hm = Decimal(repr(round(w, 3))), Decimal(repr(round(h, 3)))
        area = float(wm * hm)
    rec = {
        "contract": "photo_walk_measure_diagnostics_v1", "contract_version": "1.0.0",
        "created_utc": created_utc or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform, "data_origin": data_origin, "app_build": app_build,
        "session_ref": hashlib.sha256(session_id.encode()).hexdigest()[:12], "frame_id": view.frame_id, "observation_id": observation_id,
        "camera": {"fx": view.intrinsics.fx, "fy": view.intrinsics.fy, "cx": view.intrinsics.cx, "cy": view.intrinsics.cy,
                   "width": view.intrinsics.width, "height": view.intrinsics.height},
        "corners_px": [[round(float(a), 2), round(float(b), 2)] for a, b in np.asarray(corners_px)],
        "measurement": {"status": status, "width_m": None if not result.ok else round(float(w), 4), "height_m": None if not result.ok else round(float(h), 4),
                        "area_m2": area, "scale_method": result.scale_method, "level": result.level if result.ok else None, "feedback": feedback},
        "result_flags": [{"code": f["code"], "severity": f["severity"], "detail": f["detail"]} for f in result.flags],
        "algorithm": json_safe(result.diag),
        "thresholds": json_safe(cfg.as_dict()),
        "user_hints_nl": list(dict.fromkeys(f["instruction_nl"] for f in result.flags if f["severity"] == "BLOCKING")) or ["Geen blokkerende problemen."],
        "privacy": {"images_included": False, "point_cloud_included": False, "absolute_pose_included": False, "location_included": False},
    }
    return rec


def schema_errors(rec):
    import jsonschema
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(rec))


def forbidden_key_paths(obj, path=""):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(f in str(k).lower() for f in FORBIDDEN_KEYS) and not path.endswith("privacy"):
                out.append(f"{path}/{k}")
            out += forbidden_key_paths(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += forbidden_key_paths(v, f"{path}/{i}")
    return out
