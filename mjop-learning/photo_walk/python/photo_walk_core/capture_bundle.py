"""Ontwikkelbundel (`photo_walk_capture_bundle_v1`): alleen voor ONTWIKKELING en KALIBRATIE, standaard UIT, uitsluitend lokaal op het toestel.

Doel: een meting exact kunnen herhalen (replay) zonder de ruwe sensordata in Git, in een PR, in CI-artifacts of in externe opslag te zetten.

Bewaard (zie docs/dev_capture_bundle.md): de originele foto (volledige resolutie, alleen op verzoek van de ontwikkelmodus), de dieptekaarten van het hoofd- en de
steunframes, intrinsics, kaderhoeken, tracking per frame, de HELLING t.o.v. de zwaartekracht en de poses van de steunframes RELATIEF aan het hoofdframe.
NIET bewaard: locatie, kompas, absolute positie of oriëntatie van het toestel, gebruikersgegevens, adres.

Deze module is de Python-referentie; de Swift-app schrijft hetzelfde formaat (PhotoWalkCore/CaptureBundle.swift) en de tests lezen elkaars bundels.
"""
import datetime
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

from .config import DEFAULT, Config
from .geometry import UP, Intrinsics
from .model import View

CONTRACT = "photo_walk_capture_bundle_v1"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "photo_walk_capture_bundle_v1.schema.json"
DIR_PREFIX = "bundle_"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def thresholds_sha256(cfg: Config = DEFAULT) -> str:
    return _sha(json.dumps(cfg.as_dict(), sort_keys=True).encode())


def session_ref(session_id: str) -> str:
    return _sha(session_id.encode())[:12]


def _intr(i: Intrinsics):
    return {"fx": i.fx, "fy": i.fy, "cx": i.cx, "cy": i.cy, "width": i.width, "height": i.height}


def relative_pose(cap_pose, pose):
    """Pose van `pose` uitgedrukt in het camerastelsel van het hoofdframe: R_rel = Rc^T R; t_rel = Rc^T (t - tc). Geen absolute positie of oriëntatie."""
    Rc, tc = cap_pose[:3, :3], cap_pose[:3, 3]
    R, t = pose[:3, :3], pose[:3, 3]
    return Rc.T @ R, Rc.T @ (t - tc)


def write_bundle(root, *, view: View, supports=(), corners_px, session_id, observation_id, app_build="photo_walk_core", cfg: Config = DEFAULT, photo_bytes=None,
                 created_utc=None, tracking_labels=None):
    root = Path(root)
    name = f"{DIR_PREFIX}{session_ref(session_id)}_{observation_id}"
    d = root / name
    d.mkdir(parents=True, exist_ok=False)
    files, frames = [], []
    labels = tracking_labels or {}
    allv = [("CAPTURE", view)] + [("SUPPORT", s) for s in supports]
    for role, v in allv:
        R_rel, t_rel = relative_pose(view.pose, v.pose)
        fr = {"id": v.frame_id, "role": role, "tracking": labels.get(v.frame_id, v.tracking_state), "intrinsics": _intr(v.intrinsics),
              "rotation_rel_row_major": [round(float(x), 9) for x in R_rel.reshape(-1)], "translation_rel_m": [round(float(x), 9) for x in t_rel], "depth": None}
        if v.depth is not None:
            raw = np.ascontiguousarray(v.depth.astype("<f4")).tobytes()
            fn = f"depth_{v.frame_id}.f32"
            (d / fn).write_bytes(raw)
            files.append({"name": fn, "kind": "DEPTH_F32_LE", "bytes": len(raw), "sha256": _sha(raw)})
            fr["depth"] = {"file": fn, "width": int(v.depth.shape[1]), "height": int(v.depth.shape[0]), "dtype": "float32_le", "invalid": "NaN of 0"}
        frames.append(fr)
    if photo_bytes is not None:
        (d / "photo.jpg").write_bytes(photo_bytes)
        files.append({"name": "photo.jpg", "kind": "PHOTO_FULL_RESOLUTION", "bytes": len(photo_bytes), "sha256": _sha(photo_bytes)})
    u = view.pose[:3, :3].T @ UP
    manifest = {
        "contract": CONTRACT, "contract_version": "1.0.0", "created_utc": created_utc or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "app_build": app_build, "session_ref": session_ref(session_id), "observation_id": observation_id, "frame_id": view.frame_id,
        "corners_px": [[round(float(a), 4), round(float(b), 4)] for a, b in np.asarray(corners_px, float)],
        "capture_attitude": {"gravity_up_in_camera": [round(float(x), 9) for x in u],
                             "note": "richting van 'omhoog' in het camerastelsel van het hoofdframe; geen positie, geen kompas, geen absolute oriëntatie"},
        "frames": frames, "thresholds_sha256": thresholds_sha256(cfg), "files": files,
        "privacy": {"dev_mode_only": True, "local_only": True, "full_photo_included": photo_bytes is not None, "absolute_pose_included": False, "location_included": False,
                    "compass_included": False, "user_or_address_included": False},
        "storage": {"excluded_from_backup": True, "never_uploaded": True, "delete": "app: meetdiagnose-scherm > Verwijder ontwikkelbundels; of verwijder de app (het hele toestel-sandbox gaat dan weg)"},
    }
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return d


def schema_errors(manifest):
    import jsonschema
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return sorted(f"{'/'.join(str(x) for x in e.absolute_path) or '<root>'}: {e.message}" for e in jsonschema.Draft7Validator(schema).iter_errors(manifest))


def _capture_rotation(u):
    """Camera->wereld-rotatie met R^T * UP = u en een vaste, willekeurige yaw (de uitkomst is yaw-onafhankelijk)."""
    u = np.asarray(u, float)
    u = u / np.linalg.norm(u)
    ex = np.array([1.0, 0.0, 0.0])
    x = ex - (ex @ u) * u
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0.0, 0.0, 1.0]) - (u[2]) * u
    x = x / np.linalg.norm(x)
    z = np.cross(x, u)
    return np.stack([x, u, z / np.linalg.norm(z)])


def read_bundle(path):
    """Leest een bundel, controleert alle sha256's en bouwt de views voor een exacte replay. Geeft (view, supports, corners_px, manifest)."""
    d = Path(path)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    for f in m["files"]:
        b = (d / f["name"]).read_bytes()
        if _sha(b) != f["sha256"] or len(b) != f["bytes"]:
            raise ValueError(f"bundelbestand beschadigd of gewijzigd: {f['name']}")
    Rc = _capture_rotation(m["capture_attitude"]["gravity_up_in_camera"])
    views = []
    for fr in m["frames"]:
        i = fr["intrinsics"]
        R_rel = np.array(fr["rotation_rel_row_major"], float).reshape(3, 3)
        t_rel = np.array(fr["translation_rel_m"], float)
        pose = np.eye(4)
        pose[:3, :3] = Rc @ R_rel
        pose[:3, 3] = Rc @ t_rel
        depth = None
        if fr["depth"]:
            dd = fr["depth"]
            depth = np.frombuffer((d / dd["file"]).read_bytes(), dtype="<f4").reshape(dd["height"], dd["width"]).astype(np.float32)
        views.append(View(frame_id=fr["id"], intrinsics=Intrinsics(i["fx"], i["fy"], i["cx"], i["cy"], i["width"], i["height"]), pose=pose, tracking_state=fr["tracking"], depth=depth))
    cap = next(v for v, fr in zip(views, m["frames"]) if fr["role"] == "CAPTURE")
    sups = [v for v, fr in zip(views, m["frames"]) if fr["role"] == "SUPPORT"]
    return cap, sups, np.array(m["corners_px"], float), m


def delete_bundle(path):
    """Verwijdert één bundel volledig (alle bestanden en de map)."""
    p = Path(path)
    if not p.name.startswith(DIR_PREFIX) or not (p / "manifest.json").exists():
        raise ValueError("geen ontwikkelbundel")
    shutil.rmtree(p)


def delete_all(root):
    n = 0
    for p in sorted(Path(root).glob(DIR_PREFIX + "*")):
        if (p / "manifest.json").exists():
            delete_bundle(p)
            n += 1
    return n
