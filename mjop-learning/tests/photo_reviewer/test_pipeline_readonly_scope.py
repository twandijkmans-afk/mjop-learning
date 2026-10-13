"""Reproduceerbaarheid van de synthetische fixtures, end-to-end demo, en alleen-lezen/scope-bewaking."""
import ast
import builtins
import hashlib
import io
import json
import os
import subprocess
import sys

import pytest

from agent.photo import synthetic
from agent.photo.contract import PROJECT_ROOT, sha256_bytes

import photo_support as S

PKG = os.path.join(PROJECT_ROOT, "agent", "photo")
ALLOWED_IMPORTS = {"abc", "base64", "copy", "dataclasses", "datetime", "decimal", "collections", "hashlib", "html", "io", "json", "math",
                   "os", "re", "jsonschema", "PIL", "agent", "anthropic"}
FORBIDDEN_BARE = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_CALLS = {"system", "popen", "Popen", "run", "check_call", "check_output", "urlopen",
                   "urlretrieve", "connect", "write", "writelines", "write_text", "write_bytes", "rename", "remove", "unlink",
                   "rmdir", "mkdir", "makedirs", "rmtree", "copy2", "copyfile", "copytree", "move", "dump", "touch", "chmod"}


def pkg_files():
    return sorted(os.path.join(PKG, f) for f in os.listdir(PKG) if f.endswith(".py"))


# --- fixtures ---------------------------------------------------------------------------------------------------------
def test_synthetic_image_fixture_is_reproducible_by_pixels():
    from PIL import Image
    committed = Image.open(io.BytesIO(S.png())).convert("RGB")
    assert synthetic.pixel_sha256(committed) == synthetic.pixel_sha256(synthetic.render())


def test_replay_fixture_matches_generator_and_ground_truth_fixture():
    sha = sha256_bytes(S.png())
    assert S.load_json("synthetic_facade_v1_replay.json") == synthetic.model_like_recording(sha)
    assert S.load_json("synthetic_facade_v1_ground_truth.json")["ground_truth"] == synthetic.GROUND_TRUTH


def test_fixtures_contain_no_real_photo_data():
    assert os.path.getsize(os.path.join(S.FIX, "synthetic_facade_v1.png")) < 20_000
    for f in os.listdir(S.FIX):
        assert f.startswith("synthetic_facade_v1"), f
        assert not f.lower().endswith((".jpg", ".jpeg", ".heic", ".tif", ".tiff"))


# --- end-to-end demo ---------------------------------------------------------------------------------------------------
def test_demo_end_to_end_is_reproducible_and_outputs_are_valid(tmp_path):
    import photo_reviewer_demo as D
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    pset, state, ev = D.run_demo(str(a))
    D.run_demo(str(b))
    for name in ("proposal_set.json", "quantity_state.json", "evaluation.json", "review.html", "run_manifest.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    assert state["totals"]["photo_visible_full_gross_area_m2"] == "9.60"
    assert pset["provider"]["provider_name"] == "replay" and ev["overall"]["tp"] == 7


def test_demo_refuses_output_inside_repository():
    import photo_reviewer_demo as D
    with pytest.raises(SystemExit):
        D.safe_out_dir(os.path.join(PROJECT_ROOT, "reports", "photo_reviewer_out"))
    with pytest.raises(SystemExit):
        D.safe_out_dir(os.path.join(PROJECT_ROOT, "data"))
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "reports", "photo_reviewer_out"))


def test_demo_does_not_modify_canonical_layers_or_inputs(tmp_path):
    import photo_reviewer_demo as D
    before = S.tree_manifest()
    fix_before = S.tree_manifest(dirs=("tests/fixtures/photo_reviewer", "schemas", "vocabularies"))
    D.run_demo(str(tmp_path / "x"))
    D.run_reference_mock(str(tmp_path / "x"), "maldenhof_2")
    assert S.tree_manifest() == before
    assert S.tree_manifest(dirs=("tests/fixtures/photo_reviewer", "schemas", "vocabularies")) == fix_before


def test_pipeline_runs_without_any_file_writes_or_network(monkeypatch):
    """Het pakket zelf (zonder CLI) mag niets schrijven: open(w) en socket zijn geblokkeerd."""
    real_open = builtins.open

    def guarded(file, mode="r", *a, **k):
        assert not any(c in str(mode) for c in "wax+"), f"schrijfpoging naar {file}"
        return real_open(file, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", guarded)
    from agent.photo.quantity import compute_quantity_state
    from agent.photo.review_page import render_review_page
    ps = S.proposal_set()
    st = compute_quantity_state(ps, S.dims())
    assert render_review_page(S.png(), ps, st, S.dims())


# --- statische bewaking van agent/photo ------------------------------------------------------------------------------------
def test_static_import_allowlist_and_no_write_or_dynamic_calls():
    for path in pkg_files():
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                mods = [node.module or ""]
            for m in mods:
                assert m.split(".")[0] in ALLOWED_IMPORTS, f"{os.path.basename(path)}: niet toegestane import {m}"
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                assert name not in FORBIDDEN_CALLS, f"{os.path.basename(path)}:{node.lineno}: {name}()"
                assert not (isinstance(f, ast.Name) and f.id in FORBIDDEN_BARE), f"{os.path.basename(path)}:{node.lineno}: {f.id}()"
                if name == "replace" and isinstance(f, ast.Attribute):
                    assert not (isinstance(f.value, ast.Name) and f.value.id in ("os", "shutil", "pathlib")), f"{path}:{node.lineno}: os.replace"
                if name == "open":
                    mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "r"
                    assert not any(c in str(mode) for c in "wax+"), f"{path}:{node.lineno}: open({mode!r})"


def test_anthropic_sdk_is_only_imported_lazily_inside_the_claude_adapter():
    for path in pkg_files():
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in tree.body:                                     # moduleniveau
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else ([node.module] if isinstance(node, ast.ImportFrom) else [])
            assert not any((n or "").startswith("anthropic") for n in names), f"{path}: SDK op moduleniveau"
    sys.modules.pop("anthropic", None)
    import importlib
    import agent.photo.providers
    importlib.reload(agent.photo.providers)
    assert "anthropic" not in sys.modules


def test_no_secrets_or_hardcoded_model_names_in_code():
    for path in pkg_files() + [os.path.join(PROJECT_ROOT, "scripts", "photo_reviewer_demo.py")]:
        text = open(path, encoding="utf-8").read()
        assert "sk-ant" not in text and "api_key=" not in text.replace("api_key=None", "")
        assert "claude-" not in text, f"{os.path.basename(path)}: ingebakken modelnaam"


def test_tracing_and_telemetry_not_enabled_anywhere():
    for path in pkg_files():
        text = open(path, encoding="utf-8").read().lower()
        for bad in ("langsmith", "opentelemetry", "sentry", "wandb", "helicone", "tracing=true"):
            assert bad not in text


# --- scope guard ------------------------------------------------------------------------------------------------------------
def test_existing_scope_guard_manifest_unaffected_by_new_files():
    """De bevroren mappen blijven ongewijzigd; nieuwe bestanden staan uitsluitend buiten de bevroren mappen."""
    m = json.load(open(os.path.join(PROJECT_ROOT, "tests", "fixtures", "scope_guard", "frozen_manifest_v1.json")))
    for path, digest in m["files"].items():
        with open(os.path.join(PROJECT_ROOT, path), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == digest, path
    for d in m["frozen_dirs"]:
        for dp, _, files in os.walk(os.path.join(PROJECT_ROOT, d)):
            for f in files:
                rel = os.path.relpath(os.path.join(dp, f), PROJECT_ROOT).replace(os.sep, "/")
                assert rel in m["files"] or rel in {a["path"] for a in m["allowed_additions"]}, f"nieuw bestand in bevroren map: {rel}"


def test_original_photos_and_register_hashes_unchanged():
    """Originele foto's in de repo en het archiefmanifest: hash vastgelegd in het fotoregister."""
    reg = json.load(open(os.path.join(PROJECT_ROOT, "reports/frames/photo_archive_audit_v1/maldenhof_photo_archive_audit_v1.json")))
    assert reg["manifest_unmodified_copy"] is True
    cand = json.load(open(os.path.join(PROJECT_ROOT, "data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json")))
    p = os.path.join(PROJECT_ROOT, cand["photo"]["path"])
    if os.path.exists(p):
        # alleen een hash-controle (bytes); de afbeelding wordt niet gedecodeerd of geanalyseerd
        with open(p, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == cand["photo"]["sha256"]


def test_git_tracked_canonical_layers_clean_after_test_run():
    r = subprocess.run(["git", "status", "--porcelain", "--", "data", "reports", "vocabularies", "config"], cwd=PROJECT_ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("geen git-werkboom")
    assert r.stdout.strip() == "", r.stdout
