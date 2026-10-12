"""Scopebewaking voor bevroren stores.

Vergelijkt de werkboom met een vastgelegde manifest-baseline (hashes van de base-commit), niet met een lokale/verouderde origin/main.
Detecteert wijzigingen en verwijderingen van bestaande bestanden en niet-toegestane nieuwe bestanden in de bevroren mappen.
Expliciet toegestane uitbreidingen worden in tests/fixtures/scope_guard/frozen_manifest_v1.json onder allowed_additions vastgelegd.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "scope_guard" / "frozen_manifest_v1.json"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _walk(root, d):
    base = Path(root) / d
    out = set()
    for dp, dn, fn in os.walk(base):
        dn[:] = [x for x in dn if x != "__pycache__"]
        for f in fn:
            if not f.endswith((".pyc", ".pyo")):
                out.add(str(Path(dp, f).relative_to(root)).replace(os.sep, "/"))
    return out


def scope_violations(root, m):
    v = []
    for path, digest in m["files"].items():
        p = Path(root) / path
        if not p.exists():
            v.append(f"VERWIJDERD: {path}")
        elif _sha(p) != digest:
            v.append(f"GEWIJZIGD: {path}")
    allowed = {a["path"] for a in m["allowed_additions"]}
    for d in m["frozen_dirs"]:
        for path in sorted(_walk(root, d)):
            if path not in m["files"] and path not in allowed:
                v.append(f"NIEUW NIET TOEGESTAAN: {path}")
    for a in allowed:
        if not (Path(root) / a).exists():
            v.append(f"VERVALLEN TOEGESTANE UITBREIDING (bestand ontbreekt): {a}")
        if not any(a.startswith(d + "/") for d in m["frozen_dirs"]):
            v.append(f"TOEGESTANE UITBREIDING BUITEN BEVROREN MAP: {a}")
    return v


def _manifest():
    return json.loads(MANIFEST.read_text())


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_working_tree_matches_frozen_baseline():
    assert scope_violations(ROOT, _manifest()) == []


def test_manifest_is_honest_against_pinned_base_commit():
    m = _manifest()
    if _git("cat-file", "-e", m["base_commit"] + "^{commit}").returncode != 0:
        pytest.skip("base-commit niet beschikbaar in deze (ondiepe) clone")
    assert _git("merge-base", "--is-ancestor", m["base_commit"], "HEAD").returncode == 0, "base-commit is geen voorouder van HEAD"
    for path, digest in m["files"].items():
        blob = subprocess.run(["git", "show", f"{m['base_commit']}:./{path}"], cwd=ROOT, capture_output=True)
        assert blob.returncode == 0, path
        assert hashlib.sha256(blob.stdout).hexdigest() == digest, f"manifest wijkt af van base-commit: {path}"
    listed = {p for p in _git("ls-tree", "-r", "--name-only", m["base_commit"], "--", *m["frozen_dirs"], *m["readonly_dirs"]).stdout.split()}
    assert listed == set(m["files"]), "manifest mist bestanden van de base-commit of bevat extra"


def test_manifest_covers_known_frozen_stores():
    f = _manifest()["files"]
    for p in ("data/frame_inventory/frame_inventory_v1.json", "data/frame_inventory/maldenhof_photo_frame_instances_v1.json",
              "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json", "data/photo_evidence/maldenhof_3_candidate_human_decisions_v1.json",
              "data/photo_evidence/maldenhof_3_frame_annotation_v1.json", "data/photo_evidence/maldenhof_address_pand_evidence_v1.json",
              "data/photos/incoming/maldenhof/maldenhof_2.jpg", "data/kengetallen/kengetallen_batch1.json",
              "data/quantity_resolutions/quantity_resolution_records.json", "data/building_links/building_link_records.json",
              "reports/frames/photo_archive_audit_v1/maldenhof_photo_archive_audit_v1.json"):
        assert p in f, p


# --- de bewaking zelf moet wijziging, verwijdering en ongeoorloofde toevoeging aantonen -----------------------------------------
def _fake(tmp_path):
    (tmp_path / "data/frame_inventory").mkdir(parents=True)
    (tmp_path / "reports/frames").mkdir(parents=True)
    a, b = tmp_path / "data/frame_inventory/a.json", tmp_path / "reports/frames/r.md"
    a.write_text("{}")
    b.write_text("x")
    return {"frozen_dirs": ["data/frame_inventory"], "readonly_dirs": ["reports/frames"], "allowed_additions": [],
            "files": {"data/frame_inventory/a.json": _sha(a), "reports/frames/r.md": _sha(b)}}


def test_guard_detects_modification_deletion_and_new_file(tmp_path):
    m = _fake(tmp_path)
    assert scope_violations(tmp_path, m) == []
    (tmp_path / "data/frame_inventory/a.json").write_text('{"x":1}')
    assert scope_violations(tmp_path, m) == ["GEWIJZIGD: data/frame_inventory/a.json"]
    (tmp_path / "data/frame_inventory/a.json").unlink()
    assert scope_violations(tmp_path, m) == ["VERWIJDERD: data/frame_inventory/a.json"]
    (tmp_path / "data/frame_inventory/a.json").write_text("{}")
    (tmp_path / "data/frame_inventory/new.json").write_text("{}")
    assert scope_violations(tmp_path, m) == ["NIEUW NIET TOEGESTAAN: data/frame_inventory/new.json"]


def test_guard_allows_explicit_additions_and_new_reports(tmp_path):
    m = _fake(tmp_path)
    (tmp_path / "reports/frames/extra.md").write_text("ok")  # readonly dir: nieuw mag
    assert scope_violations(tmp_path, m) == []
    (tmp_path / "data/frame_inventory/new.json").write_text("{}")
    m["allowed_additions"] = [{"path": "data/frame_inventory/new.json", "milestone": "test", "reason": "expliciet toegestaan"}]
    assert scope_violations(tmp_path, m) == []
    (tmp_path / "reports/frames/r.md").write_text("gewijzigd")  # readonly: bestaand mag niet wijzigen
    assert scope_violations(tmp_path, m) == ["GEWIJZIGD: reports/frames/r.md"]


def test_guard_flags_stale_allowed_addition(tmp_path):
    m = _fake(tmp_path)
    m["allowed_additions"] = [{"path": "data/frame_inventory/gone.json", "milestone": "t", "reason": "r"}]
    assert any(x.startswith("VERVALLEN") for x in scope_violations(tmp_path, m))
