"""Regressietests voor de herstelronde op PR #48: (1) generieke demo-CLI zonder casusverwijzing, (2) afgedwongen uitvoerpaden en
afgesplitste fixture-generator, (3) zelfstandig validerende HTML-renderer."""
import copy
import json
import os
import subprocess
import sys

import pytest

from agent.photo import evaluate
from agent.photo.contract import PROJECT_ROOT, PhotoError, canonical_sha256
from agent.photo.quantity import compute_quantity_state
from agent.photo.review_page import render_review_page
import photo_support as S

DEMO = os.path.join(PROJECT_ROOT, "scripts", "photo_reviewer_demo.py")


# --- 1. generalization-audit ----------------------------------------------------------------------------------------------
def test_demo_script_is_generic_and_audit_does_not_flag_it():
    import doc012_generalization_review as G
    text = open(DEMO, encoding="utf-8").read()
    assert not [p for p in G.AUDIT_PATTERNS if p in text]
    rel = "scripts/photo_reviewer_demo.py"
    assert rel not in G.REPORT_ONLY_SCRIPTS and rel not in G.REVIEWED_NOT_A_PROBLEM        # niet via een uitzondering gepasseerd
    hits = {h["file"]: h["classification"] for h in G.generalization_audit()}
    assert rel not in hits
    assert not [f for f, k in hits.items() if k == "GENERIC_CODE_PROBLEM" and f.startswith(("scripts/photo_", "tests/photo_"))]


def test_reference_sets_are_registered_outside_the_cli_and_cli_takes_them_by_id():
    assert "maldenhof_2" in evaluate.REFERENCE_SETS
    r = subprocess.run([sys.executable, DEMO, "eval-reference-mock", "--reference-set", "does_not_exist", "--out", "/tmp/x"], capture_output=True, text=True)
    assert r.returncode == 2 and "invalid choice" in r.stderr


# --- 2. uitvoerpaden ------------------------------------------------------------------------------------------------------
def test_direct_run_functions_enforce_safe_out_dir_inside_repository():
    import photo_reviewer_demo as D
    for target in (os.path.join(PROJECT_ROOT, "reports", "photo_reviewer_out"), os.path.join(PROJECT_ROOT, "data"),
                   os.path.join(PROJECT_ROOT, "data", "photo_evidence", "x"), PROJECT_ROOT, os.path.dirname(PROJECT_ROOT)):
        before = S.tree_manifest()
        with pytest.raises(SystemExit):
            D.run_demo(target)
        with pytest.raises(SystemExit):
            D.run_reference_mock(target, "maldenhof_2")
        assert S.tree_manifest() == before
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "reports", "photo_reviewer_out"))


def test_symlink_into_repository_is_resolved_and_refused(tmp_path):
    import photo_reviewer_demo as D
    link = tmp_path / "link"
    link.symlink_to(os.path.join(PROJECT_ROOT, "data"))
    with pytest.raises(SystemExit):
        D.run_demo(str(link))
    with pytest.raises(SystemExit):
        D.run_demo(str(link / "sub"))


def test_existing_foreign_files_are_never_overwritten_or_mixed(tmp_path):
    import photo_reviewer_demo as D
    (tmp_path / "keep.txt").write_text("gevoelig")
    with pytest.raises(SystemExit):
        D.run_demo(str(tmp_path))
    assert (tmp_path / "keep.txt").read_text() == "gevoelig" and sorted(os.listdir(tmp_path)) == ["keep.txt"]


def test_output_that_is_a_symlink_or_not_a_directory_is_refused(tmp_path):
    import photo_reviewer_demo as D
    secret = tmp_path / "secret.json"
    secret.write_text("origineel")
    out = tmp_path / "out"
    out.mkdir()
    (out / "evaluation.json").symlink_to(secret)
    with pytest.raises(SystemExit):
        D.run_demo(str(out))
    assert secret.read_text() == "origineel"
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(SystemExit):
        D.run_demo(str(f))


def test_rerun_into_own_output_dir_is_allowed_and_reproducible(tmp_path):
    import photo_reviewer_demo as D
    D.run_demo(str(tmp_path))
    first = (tmp_path / "review.html").read_bytes()
    D.run_demo(str(tmp_path))
    D.run_reference_mock(str(tmp_path), "maldenhof_2")
    assert (tmp_path / "review.html").read_bytes() == first


def test_unknown_reference_set_is_refused_without_writing(tmp_path):
    import photo_reviewer_demo as D
    with pytest.raises(SystemExit):
        D.run_reference_mock(str(tmp_path), "nope")
    assert os.listdir(tmp_path) == []


def test_demo_script_has_no_fixture_write_path_and_cli_rejects_write_fixtures():
    import photo_reviewer_demo as D
    assert not hasattr(D, "write_fixtures")
    text = open(DEMO, encoding="utf-8").read()
    assert "write_fixtures" not in text and "write-fixtures" not in text and "tests/fixtures" not in text.split('FIX = ')[0]
    before = S.tree_manifest(dirs=("tests/fixtures/photo_reviewer",))
    r = subprocess.run([sys.executable, DEMO, "write-fixtures"], capture_output=True, text=True)
    assert r.returncode == 2
    assert S.tree_manifest(dirs=("tests/fixtures/photo_reviewer",)) == before


def test_fixture_generator_is_gated_and_reproducible(tmp_path, monkeypatch):
    import regenerate_fixtures as R
    before = S.tree_manifest(dirs=("tests/fixtures/photo_reviewer",))
    for kw in ({"confirmed": False, "env": {R.ENV_FLAG: "1"}}, {"confirmed": True, "env": {}}, {"confirmed": True, "env": {R.ENV_FLAG: "0"}}):
        with pytest.raises(SystemExit):
            R.write_fixtures(**kw)
    with pytest.raises(SystemExit):
        R.write_fixtures(str(tmp_path), confirmed=True, env={R.ENV_FLAG: "1"})
    monkeypatch.delenv(R.ENV_FLAG, raising=False)
    with pytest.raises(SystemExit):
        R.main([])
    assert S.tree_manifest(dirs=("tests/fixtures/photo_reviewer",)) == before and os.listdir(tmp_path) == []
    files = R.build_fixture_files()                                   # zuiver: schrijft niets
    assert S.tree_manifest(dirs=("tests/fixtures/photo_reviewer",)) == before
    for name in ("synthetic_facade_v1_replay.json", "synthetic_facade_v1_ground_truth.json"):
        assert files[name] == open(os.path.join(S.FIX, name), "rb").read(), name


# --- 3. renderer ----------------------------------------------------------------------------------------------------------
def _inputs():
    ps, d = S.proposal_set(), S.dims()
    return S.png(), ps, compute_quantity_state(ps, d), d


def test_renderer_accepts_valid_inputs_and_still_escapes():
    png, ps, st, d = _inputs()
    assert "VOORSTELLEN" in render_review_page(png, ps, st, d)
    ps2 = S.fresh()
    ps2["proposals"][0]["observation"] = "<script>alert(1)</script>"
    ps2 = S.reseal(ps2)
    html = render_review_page(png, ps2, compute_quantity_state(ps2, None), None)
    assert "<script>alert" not in html


@pytest.mark.parametrize("mutate", [
    lambda st: st["groups"][0].update(count_full=st["groups"][0]["count_full"] + 3),
    lambda st: st["groups"][0].update(gross_area_m2="999.00"),
    lambda st: st["totals"].update(photo_visible_full_gross_area_m2="1.00"),
    lambda st: st["photo_visible_counts"]["by_type"]["WINDOW_OPENING"].update(full=99),
    lambda st: st["photo_visible_counts"].update(is_building_total=True),
    lambda st: st["building_total"].update(status="KNOWN", value="123"),
    lambda st: st["invariants"].update(is_instance=True),
    lambda st: st["invariants"].update(painting_area_m2="12.00"),
    lambda st: st.update(state_id="PQS-0000000000000000"),
    lambda st: st["groups"][0].update(observation_ids_full=[]),
    lambda st: st["proposal_set_ref"].update(set_sha256="0" * 64),
    lambda st: st.update(dimension_input_sha256=None),
    lambda st: st.pop("totals"),
    lambda st: st["groups"][0].update(outer_width_m="-1.000"),
])
def test_renderer_rejects_manipulated_quantity_state(mutate):
    png, ps, st, d = _inputs()
    st = copy.deepcopy(st)
    mutate(st)
    with pytest.raises(PhotoError) as e:
        render_review_page(png, ps, st, d)
    assert e.value.code in ("RENDER_INPUT_INVALID", "OUTPUT_CONTRACT_VIOLATION")


def test_renderer_rejects_state_that_belongs_to_other_inputs():
    png, ps, st, d = _inputs()
    other = copy.deepcopy(d)
    other["dimension_references"][0]["outer_width_m"] = "9.999"
    with pytest.raises(PhotoError):
        render_review_page(png, ps, st, other)                                       # staat gebouwd met andere maten
    with pytest.raises(PhotoError):
        render_review_page(png, ps, compute_quantity_state(ps, None), d)             # staat zonder maten, maten wel getoond
    ps2 = S.fresh()
    ps2["proposals"].pop()
    with pytest.raises(PhotoError):
        render_review_page(png, S.reseal(ps2), st, d)                                # andere voorstelset


def test_renderer_rejects_invalid_proposal_set_and_image():
    png, ps, st, d = _inputs()
    bad = copy.deepcopy(ps)
    bad["proposals"][0]["review_status"] = "ACCEPTED"
    with pytest.raises(PhotoError):
        render_review_page(png, bad, st, d)
    tampered = copy.deepcopy(ps)
    tampered["proposals"][0]["bbox_norm"] = [0.0, 0.0, 0.5, 0.5]                      # set_id klopt niet meer
    with pytest.raises(PhotoError):
        render_review_page(png, tampered, st, d)
    with pytest.raises(PhotoError):
        render_review_page(png + b"x", ps, st, d)                                      # afbeelding komt niet overeen met de hash
    with pytest.raises(PhotoError):
        render_review_page(b"<html>", ps, st, d)
    with pytest.raises(PhotoError):
        render_review_page(png, ps, "geen object", d)


def test_renderer_rejects_invalid_dimension_input_and_evaluation():
    png, ps, st, d = _inputs()
    badd = copy.deepcopy(d)
    badd["dimension_references"][0]["outer_height_m"] = 5
    with pytest.raises(PhotoError):
        render_review_page(png, ps, st, badd)
    ev = evaluate.evaluate_proposals(ps["proposals"], [])
    assert render_review_page(png, ps, st, d, ev)
    for mut in (lambda e: e["per_type"]["WINDOW_OPENING"].update(tp="<b>1</b>"), lambda e: e["per_type"]["WINDOW_OPENING"].update(recall=7),
                lambda e: e["per_type"].update({"X": {}}), lambda e: e.pop("overall")):
        e2 = copy.deepcopy(ev)
        mut(e2)
        with pytest.raises(PhotoError):
            render_review_page(png, ps, st, d, e2)
