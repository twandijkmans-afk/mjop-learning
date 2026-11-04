"""Ontwikkelbundel: roundtrip/replay, integriteit, privacy, verwijdering. Er worden GEEN echte foto's of bundels in de repository bewaard."""
import json
import re
from pathlib import Path

import numpy as np
import pytest

from scenes import build
from photo_walk_core import capture_bundle as cb
from photo_walk_core import diagnostics as dg
from photo_walk_core.config import DEFAULT as CFG
from photo_walk_core.levels import measure_depth_view

REPO = Path(__file__).resolve().parents[2]
FORBIDDEN = re.compile(r"(latitude|longitude|lat\b|lon\b|gps|location|compass|heading|address|adres|user|world_pose|absolute)", re.I)
SCENES = {"flat": dict(), "recess6": dict(recess=0.06, extra_frames=3), "oblique25": dict(pos=(1.6 + 3.0 * 0.4663, 1.6, 3.0), yaw=25),
          "limited_1p75m": dict(pos=(1.6, 1.65, 1.75))}


def snap(r):
    d = {"ok": r.ok, "w": r.width_m, "h": r.height_m, "flags": r.flags, "scale": r.scale_method, "indep": r.independent_frames}
    return d


def make(tmp_path, name, photo=None):
    s = build(**SCENES[name])
    d = cb.write_bundle(tmp_path, view=s["cap"], supports=tuple(s["extras"]), corners_px=s["corners"], session_id="S-1", observation_id="OBS-1",
                        photo_bytes=photo, created_utc="2026-01-01T00:00:00Z")
    return s, d


@pytest.mark.parametrize("name", list(SCENES))
def test_roundtrip_replay_equals_original(tmp_path, name):
    s, d = make(tmp_path, name)
    r0 = measure_depth_view(s["cap"], s["corners"], CFG, seed=1, supports=tuple(s["extras"]))
    cap, sups, corners, m = cb.read_bundle(d)
    r1 = measure_depth_view(cap, corners, CFG, seed=1, supports=tuple(sups))
    a, b = snap(r0), snap(r1)
    assert a["ok"] == b["ok"] and a["flags"] == b["flags"] and a["scale"] == b["scale"] and a["indep"] == b["indep"]
    for k in ("w", "h"):
        if a[k] is None or b[k] is None:
            assert a[k] == b[k]
        else:
            assert abs(a[k] - b[k]) < 1e-4
    assert cb.schema_errors(m) == []


def test_manifest_has_no_absolute_pose_or_location(tmp_path):
    _, d = make(tmp_path, "recess6")
    m = json.loads((d / "manifest.json").read_text())
    keys = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                keys.append(k)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: v for k, v in m.items() if k != "privacy"})  # privacy-blok bevat de ontkenningen zelf
    assert not [k for k in keys if FORBIDDEN.search(k)], keys
    cap = next(f for f in m["frames"] if f["role"] == "CAPTURE")
    assert np.allclose(cap["rotation_rel_row_major"], np.eye(3).reshape(-1)) and np.allclose(cap["translation_rel_m"], 0)
    p = m["privacy"]
    assert p["dev_mode_only"] and p["local_only"] and not p["absolute_pose_included"] and not p["location_included"] and not p["full_photo_included"]


def test_tampering_is_detected(tmp_path):
    _, d = make(tmp_path, "flat")
    f = next(d.glob("depth_*.f32"))
    b = bytearray(f.read_bytes())
    b[0] ^= 0xFF
    f.write_bytes(bytes(b))
    with pytest.raises(ValueError):
        cb.read_bundle(d)


def test_photo_is_optional_and_flagged(tmp_path):
    s, d = make(tmp_path, "flat", photo=b"\xff\xd8fake-test-bytes")
    m = json.loads((d / "manifest.json").read_text())
    assert m["privacy"]["full_photo_included"] and any(f["kind"] == "PHOTO_FULL_RESOLUTION" for f in m["files"])
    assert cb.schema_errors(m) == []


def test_delete_removes_everything(tmp_path):
    _, d = make(tmp_path, "recess6", photo=b"x")
    assert d.exists()
    cb.delete_bundle(d)
    assert not d.exists() and list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError):
        cb.delete_bundle(tmp_path)


def test_delete_all_only_touches_bundles(tmp_path):
    make(tmp_path, "flat")
    other = tmp_path / "keep.txt"
    other.write_text("x")
    assert cb.delete_all(tmp_path) == 1
    assert other.exists()


def test_no_raw_data_is_tracked_in_the_repository():
    bad = [p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.parts and
           (p.suffix.lower() in {".jpg", ".jpeg", ".heic", ".png", ".f32"} or p.name.startswith("bundle_"))
           and "Assets.xcassets" not in p.parts and "AppIcon" not in p.name]
    assert not [str(p) for p in bad if "ios/App" not in str(p) or p.suffix == ".f32"], bad
