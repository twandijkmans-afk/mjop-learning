"""
Tests voor de incoming / bulk MJOP pipeline v1 (scripts/process_incoming_batch.py,
incoming_registry.py, template_detection.py, xpdf_runner_setup.py).

xpdf wordt vervangen door de bestaande fake pdftotext (tests/fixtures/fake_pdftotext.py, DOC-010-
pagina's). Alle writes gaan naar tmp_path; canonieke data wordt alleen gelezen.
"""
import glob
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tests", "fixtures"))

import deterministic_extraction as de  # noqa: E402
import incoming_registry as ir  # noqa: E402
import process_incoming_batch as p  # noqa: E402
import template_detection as td  # noqa: E402
import xpdf_runner_setup as xs  # noqa: E402
from minimal_pdf import make_pdf  # noqa: E402

RAW = os.path.join(PROJECT_ROOT, "data", "raw")
DOC010 = os.path.join(RAW, "zomerdijkstraat-14", "Meerjarenonderhoudsplan 2023_VvE Zomerdijkstraat 14.pdf")
DOC003 = os.path.join(RAW, "jp-heijestraat", "2026_Overzicht 15 - Jarenplan (Gedetailleerd)_VvE 9690.xls")
FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "pdftotext_doc010", "pages.json")
FAKE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "fake_pdftotext.py")
XPDF = "pdftotext version 4.06 [www.xpdfreader.com]"
PROTECTED = ["data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
             "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions",
             "data/extracted_deterministic", "data/incoming_batches", "reports/incoming"]
PROTECTED_FILES = ["reports/document_registry.json", "data/incoming_registry.json"]


def _hashes():
    out = {}
    for d in PROTECTED:
        for f in sorted(glob.glob(os.path.join(PROJECT_ROOT, d, "**", "*"), recursive=True)):
            if os.path.isfile(f):
                out[f] = hashlib.sha256(open(f, "rb").read()).hexdigest()
    for f in PROTECTED_FILES:
        out[f] = hashlib.sha256(open(os.path.join(PROJECT_ROOT, f), "rb").read()).hexdigest()
    return out


@pytest.fixture(scope="module", autouse=True)
def canonical_data_unchanged():
    before = _hashes()
    yield
    assert _hashes() == before, "canonieke (of gecommitte incoming-) data is gewijzigd"


@pytest.fixture(scope="module")
def fake_xpdf(tmp_path_factory):
    d = tmp_path_factory.mktemp("bin")
    b = d / "pdftotext"
    b.write_text(f'#!/bin/sh\nFAKE_PDFTOTEXT_VERSION="{XPDF}" exec "{sys.executable}" "{FAKE}" "$@"\n')
    b.chmod(0o755)
    old = os.environ.get("FAKE_PDFTOTEXT_PAGES")
    os.environ["FAKE_PDFTOTEXT_PAGES"] = FIXTURE
    yield str(b)
    if old is None:
        os.environ.pop("FAKE_PDFTOTEXT_PAGES", None)
    else:
        os.environ["FAKE_PDFTOTEXT_PAGES"] = old


NO_XPDF = {"xpdf_available": False, "binary": None, "pdftotext_version": None, "unavailable_reason": "test",
           "runner_setup": None, "runner_setup_status": "NO_XPDF"}


def verified(fake):
    r = p.runner_info(fake)
    return dict(r, runner_setup_status="VERIFIED_RUNNER_SETUP")


def new_pdf(path, marker="incoming-test"):
    """Nieuw document van de ondersteunde familie: DOC-010-bytes + een PDF-commentaar (andere sha256)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copyfile(DOC010, path)
    with open(path, "ab") as f:
        f.write(f"%{marker}\n".encode())


def run(inc, state, runner, **kw):
    plan = p.plan_batch(PROJECT_ROOT, str(inc), state_root=str(state), runner=runner, **kw)
    files, report = p.build_outputs(plan)
    return plan, files, report


def process(inc, state, runner, **kw):
    plan, files, report = run(inc, state, runner, **kw)
    p.apply_writes(str(state), p.plan_writes(str(state), files, plan["batch_id"]))
    return plan, files, report


def by_path(plan):
    return {d["input_path"]: d for d in plan["docs"]}


# ------------------------------------------------------------------ formaat en familie

def test_format_detection_uses_content_not_name(tmp_path):
    (tmp_path / "a.pdf").write_bytes(make_pdf(["x"]))
    (tmp_path / "fake.pdf").write_bytes(b"not a pdf at all")
    (tmp_path / "pdf_as.xls").write_bytes(make_pdf(["x"]))
    (tmp_path / "notes.docx").write_bytes(b"PK\x03\x04rest")
    assert td.detect_format(str(tmp_path / "a.pdf")) == ("pdf", None)
    assert td.detect_format(DOC003) == ("xls", None)
    assert td.detect_format(str(tmp_path / "fake.pdf")) == (None, "UNRECOGNIZED_CONTENT")
    assert td.detect_format(str(tmp_path / "pdf_as.xls")) == (None, "FORMAT_MISMATCH")
    assert td.detect_format(str(tmp_path / "notes.docx")) == (None, "UNSUPPORTED_EXTENSION")


def test_family_needs_all_markers():
    full = {"pages": [{"page": 1, "text_status": "ok", "lines": [
        {"text": "Algemene Objectgegevens"}, {"text": "Elementenoverzicht"},
        {"text": "Overzicht 15 - Jarenplan (Gedetailleerd)"}, {"text": "Code HvhEhd Stj Cy 2026"},
        {"text": "Totaal object 100"}]}]}
    assert td.detect_family("pdf", full)["family_id"] == "pro_vve_overzicht15"
    partial = {"pages": [{"page": 1, "text_status": "ok", "lines": full["pages"][0]["lines"][:3]}]}
    r = td.detect_family("pdf", partial)
    assert r["family_id"] is None and r["reason"] == "PARTIAL_FAMILY_MARKERS"
    scanned = {"pages": [{"page": 1, "text_status": "no_text_layer", "lines": []}]}
    assert td.detect_family("pdf", scanned)["reason"] == "NO_TEXT_LAYER"


# ------------------------------------------------------------------ hoofdroute

@pytest.fixture(scope="module")
def mixed(tmp_path_factory, fake_xpdf):
    base = tmp_path_factory.mktemp("mixed")
    inc, state = base / "incoming", base / "state"
    new_pdf(str(inc / "gebouw-a" / "plan.pdf"))
    shutil.copyfile(DOC010, inc / "kopie_van_doc010.pdf")                   # exacte canonieke duplicate
    shutil.copyfile(DOC003, inc / "doc003_kopie.xls")                        # DOC-003 zelf
    (inc / "gebouw-b").mkdir()
    shutil.copyfile(DOC003, inc / "gebouw-b" / "export.xls")                 # DOC-003-achtig: andere bytes
    with open(inc / "gebouw-b" / "export.xls", "ab") as f:
        f.write(b"\0")
    (inc / "offerte.pdf").write_bytes(make_pdf(["Offerte schilderwerk", "Totaal 1.234,00"]))
    (inc / "notities.docx").write_bytes(b"PK\x03\x04docx")
    (inc / "README.md").write_text("genegeerd")
    return inc, state, process(inc, state, p.runner_info(fake_xpdf))


def test_statuses_and_totals(mixed):
    _, _, (plan, files, report) = mixed
    d = by_path(plan)
    assert d["gebouw-a/plan.pdf"]["status"] == "REVIEW_REQUIRED"          # relatiekandidaat met DOC-010
    assert "EXTRACTED" in d["gebouw-a/plan.pdf"]["status_history"]
    assert d["kopie_van_doc010.pdf"]["status"] == "DUPLICATE_SKIP"
    assert d["kopie_van_doc010.pdf"]["duplicate_of"] == "DOC-010" and d["kopie_van_doc010.pdf"]["document_id"] is None
    assert d["doc003_kopie.xls"]["status"] == "DUPLICATE_SKIP" and d["doc003_kopie.xls"]["duplicate_of"] == "DOC-003"
    assert d["gebouw-b/export.xls"]["status"] == "REVIEW_REQUIRED"
    assert "UNSUPPORTED_EXTRACTION" in d["gebouw-b/export.xls"]["reasons"]
    assert d["offerte.pdf"]["status"] == "UNKNOWN_TEMPLATE"
    assert d["notities.docx"]["status"] == "UNSUPPORTED_FORMAT" and d["notities.docx"]["document_id"] is None
    assert "README.md" not in d
    t = report["totals"]
    assert (t["total_files"], t["duplicates"], t["unknown_templates"], t["unsupported_formats"]) == (6, 2, 1, 1)
    assert t["extracted_successfully"] == 1 and t["new_price_observation_candidates"] > 0


def test_new_ids_are_stable_and_follow_canonical_registry(mixed):
    _, state, (plan, _, _) = mixed
    canonical = json.load(open(os.path.join(PROJECT_ROOT, "reports", "document_registry.json"), encoding="utf-8"))
    top = max(int(x["document_id"][4:]) for x in canonical["documents"])
    reg = ir.load(os.path.join(state, ir.REGISTRY_PATH))
    ids = [x["document_id"] for x in reg["documents"]]
    # nieuwe ID's in gesorteerde padvolgorde, direct na het canonieke register
    assert ids == [f"DOC-{n:03d}" for n in range(top + 1, top + 1 + len(ids))]
    assert {x["first_observed_path"] for x in reg["documents"]} == {"gebouw-a/plan.pdf", "gebouw-b/export.xls",
                                                                     "offerte.pdf"}
    assert ir.integrity_errors(reg, canonical) == []


def test_doc003_like_duplicate_is_candidate_only(mixed):
    _, _, (plan, _, report) = mixed
    export_id = by_path(plan)["gebouw-b/export.xls"]["document_id"]
    rel = [r for r in plan["relations"] if export_id in r["document_ids"]]
    assert rel and rel[0]["kind"] == "POSSIBLE_DUPLICATE_OTHER_BYTES" and "DOC-002" in rel[0]["document_ids"]
    assert rel[0]["status"] == "CANDIDATE_REQUIRES_HUMAN_CONFIRMATION" and rel[0]["source_cluster"] == "NOT_ASSUMED"


def test_staging_layout_and_check(mixed):
    _, state, (plan, _, _) = mixed
    bdir = os.path.join(state, p.BATCHES_DIR, plan["batch_id"])
    for sub in ("manifest.json", "promotion_proposal.json", "documents", "extracted", "validation"):
        assert os.path.exists(os.path.join(bdir, sub))
    assert os.path.isfile(os.path.join(state, p.REPORTS_DIR, f"{plan['batch_id']}.json"))
    assert p.check(PROJECT_ROOT, str(state)) == []
    m = json.load(open(os.path.join(bdir, "manifest.json"), encoding="utf-8"))
    assert m["canonical_write"] is False and m["uses_ai_api"] is False
    prop = json.load(open(os.path.join(bdir, "promotion_proposal.json"), encoding="utf-8"))
    assert prop["status"] == "PROPOSAL_ONLY_NOT_EXECUTED" and prop["requires_separate_promotion_step"] is True
    assert all(d["proposal"] == "NOT_PROMOTABLE_YET" for d in prop["documents"])    # runner niet geverifieerd


def test_rerun_same_input_is_noop_and_byte_identical(mixed, fake_xpdf):
    inc, state, (plan, files, _) = mixed
    plan2, files2, _ = run(inc, state, p.runner_info(fake_xpdf))
    assert files2 == files
    assert p.plan_writes(str(state), files2, plan2["batch_id"]) == []


def test_manifest_reproducible_in_fresh_state(mixed, fake_xpdf, tmp_path):
    inc, state, (plan, files, _) = mixed
    _, files2, _ = process(inc, tmp_path, p.runner_info(fake_xpdf))
    assert files2 == files
    for rel, content in files.items():
        assert open(os.path.join(tmp_path, *rel.split("/")), encoding="utf-8").read() == content


def test_tampered_batch_detected_by_check(mixed, tmp_path):
    _, state, (plan, _, _) = mixed
    copy = tmp_path / "state"
    shutil.copytree(state, copy)
    f = copy / p.BATCHES_DIR / plan["batch_id"] / "promotion_proposal.json"
    f.write_text(f.read_text() + " ")
    assert any("promotion_proposal.json" in e for e in p.check(PROJECT_ROOT, str(copy)))


# ------------------------------------------------------------------ register

def test_same_filename_other_hash_gets_new_id_and_old_ids_stay(tmp_path, fake_xpdf):
    inc, state = tmp_path / "in", tmp_path / "state"
    (inc / "a").mkdir(parents=True)
    (inc / "a" / "plan.pdf").write_bytes(make_pdf(["eerste"]))
    plan1, _, _ = process(inc, state, NO_XPDF)
    reg1 = ir.load(os.path.join(state, ir.REGISTRY_PATH))
    first = by_path(plan1)["a/plan.pdf"]["document_id"]
    # zelfde bestandsnaam, andere inhoud (en een extra bestand ervoor in de sortering)
    (inc / "a" / "plan.pdf").write_bytes(make_pdf(["tweede versie"]))
    (inc / "0-eerder.pdf").write_bytes(make_pdf(["nog een"]))
    plan2, _, _ = process(inc, state, NO_XPDF)
    reg2 = ir.load(os.path.join(state, ir.REGISTRY_PATH))
    assert ir.append_only_errors(reg1, reg2) == []
    second = by_path(plan2)["a/plan.pdf"]["document_id"]
    assert second != first and first in {d["document_id"] for d in reg2["documents"]}
    assert int(second[4:]) > int(first[4:]) and int(by_path(plan2)["0-eerder.pdf"]["document_id"][4:]) > int(first[4:])


def test_known_incoming_sha_keeps_its_id(tmp_path):
    inc, state = tmp_path / "in", tmp_path / "state"
    inc.mkdir()
    (inc / "x.pdf").write_bytes(make_pdf(["x"]))
    plan1, _, _ = process(inc, state, NO_XPDF)
    os.rename(inc / "x.pdf", inc / "hernoemd.pdf")                            # naam is geen identiteit
    plan2, _, _ = run(inc, state, NO_XPDF, batch_id="B2")
    d = by_path(plan2)["hernoemd.pdf"]
    assert d["document_id"] == by_path(plan1)["x.pdf"]["document_id"] and d["registration"] == "existing_incoming"


def test_in_batch_duplicate(tmp_path):
    inc = tmp_path / "in"
    (inc / "b").mkdir(parents=True)
    (inc / "a.pdf").write_bytes(make_pdf(["zelfde"]))
    (inc / "b" / "a-kopie.pdf").write_bytes(make_pdf(["zelfde"]))
    plan, _, _ = run(inc, tmp_path / "state", NO_XPDF)
    d = by_path(plan)
    assert d["b/a-kopie.pdf"]["status"] == "DUPLICATE_SKIP" and d["b/a-kopie.pdf"]["duplicate_of"] == d["a.pdf"]["document_id"]
    assert len(plan["registry"]["documents"]) == 1


def test_corrupt_registry_refused(tmp_path):
    inc, state = tmp_path / "in", tmp_path / "state"
    inc.mkdir()
    (inc / "x.pdf").write_bytes(make_pdf(["x"]))
    os.makedirs(state / "data")
    bad = ir.empty()
    bad["documents"] = [{"document_id": "DOC-001", "sha256": "0" * 64, "format": "pdf", "file_size_bytes": 1,
                         "first_batch_id": "b", "first_observed_path": "x"}]      # botst met canoniek DOC-001
    (state / ir.REGISTRY_PATH).write_text(ir.dumps(bad))
    with pytest.raises(p.PipelineError):
        run(inc, state, NO_XPDF)


# ------------------------------------------------------------------ xpdf / extractie / validatie

def test_supported_pdf_without_xpdf_waits(tmp_path):
    inc = tmp_path / "in"
    new_pdf(str(inc / "plan.pdf"))
    plan, _, report = run(inc, tmp_path / "state", NO_XPDF)
    d = plan["docs"][0]
    assert d["status"] == "READY_FOR_EXTRACTION" and d["reasons"] == ["XPDF_4_06_NOT_AVAILABLE"]
    assert d["family"]["family_id"] == "pro_vve_overzicht15" and plan["extracted"] == {}


def test_require_xpdf_flag_stops_early(monkeypatch):
    monkeypatch.setattr(p, "runner_info", lambda *a, **k: NO_XPDF)
    assert p.main(["--dry-run", "--require-xpdf"]) == 3


def test_new_supported_pdf_is_extracted_and_promotable_when_runner_verified(tmp_path, fake_xpdf, monkeypatch):
    monkeypatch.setattr(p, "known_documents", lambda *a: {})                # geen relatiekandidaten
    inc = tmp_path / "in"
    new_pdf(str(inc / "plan.pdf"))
    plan, files, report = run(inc, tmp_path / "state", verified(fake_xpdf))
    d = plan["docs"][0]
    assert d["status"] == "EXTRACTED" and d["validation_outcome"] == "EXTRACTED"
    rec = plan["extracted"][d["document_id"]]
    assert rec["extraction_metadata"]["uses_ai_api"] is False
    assert rec["extraction_metadata"]["source_sha256"] == d["sha256"]
    assert rec["extraction_metadata"]["source_relative_path"] == "incoming/plan.pdf"
    prop = json.loads(files[f"data/incoming_batches/{plan['batch_id']}/promotion_proposal.json"])
    assert prop["documents"][0]["proposal"] == "CANDIDATE_FOR_PROMOTION" and prop["global_blockers"] == []
    val = {c["check"]: c["result"] for c in plan["validations"][d["document_id"]]["checks"]}
    for name in ("schema", "source_hash", "provenance", "elements", "maintenance_actions", "quantities", "units",
                 "amounts", "vat", "price_level", "condition_legend", "unlinked_records", "review_flags"):
        assert name in val
    assert report["kengetallen_impact_if_promoted"]["existing_kengetallen_changed"] == 0


def test_extraction_schema_failure_is_failed_validation(tmp_path, fake_xpdf, monkeypatch):
    def broken(*a, **k):
        raise de.ExtractionError("validatie mislukt", ["building: 'x' is not of type 'object'"])
    inc = tmp_path / "in"
    new_pdf(str(inc / "plan.pdf"))
    plan, files, _ = run(inc, tmp_path / "state", p.runner_info(fake_xpdf), extractor=broken)
    d = plan["docs"][0]
    assert d["status"] == "FAILED_VALIDATION" and "EXTRACTION_VALIDATION_FAILED" in d["reasons"]
    assert plan["validations"][d["document_id"]]["checks"][0]["result"] == "FAIL"


def test_validation_flags_unlinked_and_amount_issues():
    rec = json.load(open(os.path.join(PROJECT_ROOT, "data", "extracted_deterministic", "batch1_v1", "DOC-007.json"),
                         encoding="utf-8"))
    sha = rec["extraction_metadata"]["source_sha256"]
    v = p.validate_extracted(rec, "DOC-007", sha, 26, [])
    res = {c["check"]: c for c in v["checks"]}
    assert res["unlinked_records"]["result"] == "REVIEW" and v["outcome"] == "REVIEW_REQUIRED"
    rec["maintenance_actions"][0]["total_cost_as_stated"] = None
    assert {c["check"]: c for c in p.validate_extracted(rec, "DOC-007", sha, 26, [])["checks"]}["amounts"]["result"] \
        == "REVIEW"
    assert p.validate_extracted(rec, "DOC-007", "0" * 64, 26, [])["outcome"] == "FAILED_VALIDATION"


def test_output_schema_failure_writes_nothing(tmp_path, monkeypatch):
    inc, state = tmp_path / "in", tmp_path / "state"
    inc.mkdir()
    (inc / "x.pdf").write_bytes(make_pdf(["x"]))
    plan = p.plan_batch(PROJECT_ROOT, str(inc), state_root=str(state), runner=NO_XPDF)
    plan["docs"][0]["format"] = "docx"                                          # buiten het schema-enum
    with pytest.raises(p.PipelineError):
        p.build_outputs(plan)
    assert not os.path.exists(state)


# ------------------------------------------------------------------ transactie

def test_partial_failure_rolls_back_everything(tmp_path, monkeypatch):
    inc, state = tmp_path / "in", tmp_path / "state"
    inc.mkdir()
    (inc / "a.pdf").write_bytes(make_pdf(["a"]))
    process(inc, state, NO_XPDF)
    snapshot = {f: open(f, "rb").read() for f in glob.glob(os.path.join(state, "**", "*"), recursive=True)
                if os.path.isfile(f)}
    (inc / "b.pdf").write_bytes(make_pdf(["b"]))
    plan, files, _ = run(inc, state, NO_XPDF)
    ops = p.plan_writes(str(state), files, plan["batch_id"])
    real, calls = os.replace, []

    def flaky(src, dst):
        calls.append(dst)
        if len(calls) == 3:
            raise OSError("schijf vol (gesimuleerd)")
        return real(src, dst)
    monkeypatch.setattr(p.os, "replace", flaky)
    with pytest.raises(OSError):
        p.apply_writes(str(state), ops)
    monkeypatch.setattr(p.os, "replace", real)
    after = {f: open(f, "rb").read() for f in glob.glob(os.path.join(state, "**", "*"), recursive=True)
             if os.path.isfile(f)}
    assert after == snapshot                                                  # geen halve batch, register gelijk
    assert not os.path.exists(os.path.join(state, p.BATCHES_DIR, plan["batch_id"]))


def test_guard_refuses_canonical_targets(tmp_path):
    for bad in ("data/extracted/DOC-011.json", "data/kengetallen/x.json", "reports/document_registry.json",
                "data/raw/x.pdf", "data/incoming_batches/../verified/x.json"):
        with pytest.raises(p.PipelineError):
            p._guard(str(tmp_path), bad)


def test_changed_batch_goes_to_history_not_deleted(tmp_path, fake_xpdf):
    inc, state = tmp_path / "in", tmp_path / "state"
    new_pdf(str(inc / "plan.pdf"))
    plan1, files1, _ = process(inc, state, NO_XPDF, batch_id="B1")
    plan2, files2, _ = process(inc, state, p.runner_info(fake_xpdf), batch_id="B1")   # nu mét xpdf
    assert plan2["docs"][0]["status"] != "READY_FOR_EXTRACTION"
    hist = glob.glob(os.path.join(state, p.BATCHES_DIR, "B1", "history", "*", "manifest.json"))
    assert len(hist) == 1 and open(hist[0], encoding="utf-8").read() == files1["data/incoming_batches/B1/manifest.json"]
    assert p.check(PROJECT_ROOT, str(state)) == []


# ------------------------------------------------------------------ geen AI, CLI

def test_no_ai_route():
    for name in ("process_incoming_batch.py", "incoming_registry.py", "template_detection.py",
                 "xpdf_runner_setup.py", "deterministic_extraction.py"):
        text = open(os.path.join(PROJECT_ROOT, "scripts", name), encoding="utf-8").read()
        for bad in ("import anthropic", "import openai", "import extract_batch", "from extract_batch"):
            assert bad not in text, (name, bad)
    code = ("import sys; sys.modules['anthropic'] = None; sys.modules['openai'] = None; "
            f"sys.path.insert(0, {os.path.join(PROJECT_ROOT, 'scripts')!r}); import process_incoming_batch as p; "
            "rc = p.main(['--dry-run']); "
            "assert 'extract_batch' not in sys.modules and 'anthropic' not in [m for m in sys.modules if sys.modules[m]]; "
            "sys.exit(rc)")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert r.returncode == 0, r.stderr


def test_cli_check_and_dry_run_on_repository():
    script = os.path.join(PROJECT_ROOT, "scripts", "process_incoming_batch.py")
    r = subprocess.run([sys.executable, script, "--check"], capture_output=True, text=True)
    assert r.returncode == 0 and "CHECK OK" in r.stdout
    r = subprocess.run([sys.executable, script], capture_output=True, text=True)
    assert r.returncode == 0


def test_workflow_is_cloud_only_and_pinned():
    wf = open(os.path.join(os.path.dirname(PROJECT_ROOT), ".github", "workflows", "process-incoming-mjops.yml"),
              encoding="utf-8").read()
    assert "xpdf_runner_setup.py" in wf and "--verify-reproduction" in wf and "workflow_dispatch" in wf
    low = wf.lower()
    assert "poppler" not in low and "anthropic_api_key" not in low and "openai_api_key" not in low
    req = open(os.path.join(PROJECT_ROOT, "requirements-pipeline.txt"), encoding="utf-8").read().lower()
    assert "anthropic" not in req.replace("geen anthropic", "") and "openai" not in req.replace("/openai", "")
    pin = xs.load_pin()
    assert pin["version"] == "4.06" and pin["expected_version_line"] == XPDF and pin["urls"]


# ------------------------------------------------------------------ runner setup

def _archive(version_line):
    script = f"#!/bin/sh\necho '{version_line}'\n".encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("xpdf-tools-linux-4.06/bin64/pdftotext")
        info.size, info.mode = len(script), 0o755
        tar.addfile(info, io.BytesIO(script))
    return buf.getvalue()


def test_runner_setup_statuses(tmp_path, monkeypatch):
    good = _archive(XPDF)
    sha = hashlib.sha256(good).hexdigest()
    pin = dict(xs.load_pin(), sha256=None)
    fetch = lambda urls: (urls[0], good, [])  # noqa: E731
    r = xs.setup(str(tmp_path / "a"), pin, fetch=fetch)
    assert r["status"] == "UNVERIFIED_RUNNER_SETUP" and "ARCHIVE_SHA256_NOT_PINNED" in r["reasons"]
    assert r["observed_archive_sha256"] == sha and r["version_line"] == XPDF
    r = xs.setup(str(tmp_path / "b"), dict(pin, sha256="0" * 64), fetch=fetch)
    assert r["status"] == "FAILED_RUNNER_SETUP" and r["reasons"] == ["ARCHIVE_SHA256_MISMATCH"]
    bad = _archive("pdftotext version 3.04")
    r = xs.setup(str(tmp_path / "c"), dict(pin, sha256=hashlib.sha256(bad).hexdigest()),
                 fetch=lambda urls: (urls[0], bad, []))
    assert r["status"] == "FAILED_RUNNER_SETUP" and r["reasons"] == ["VERSION_MISMATCH"]
    r = xs.setup(str(tmp_path / "d"), pin, fetch=lambda urls: (None, None, ["403"]))
    assert r["status"] == "FAILED_RUNNER_SETUP" and r["reasons"] == ["DOWNLOAD_FAILED"]
    monkeypatch.setattr(xs, "verify_reproduction", lambda b, v: [{"document_id": "DOC-010", "identical": True}])
    r = xs.setup(str(tmp_path / "e"), dict(pin, sha256=sha), reproduce=True, fetch=fetch)
    assert r["status"] == "VERIFIED_RUNNER_SETUP" and r["reasons"] == []
    monkeypatch.setattr(xs, "verify_reproduction", lambda b, v: [{"document_id": "DOC-010", "identical": False}])
    r = xs.setup(str(tmp_path / "f"), dict(pin, sha256=sha), reproduce=True, fetch=fetch)
    assert r["status"] == "UNVERIFIED_RUNNER_SETUP" and r["reasons"] == ["REPRODUCTION_MISMATCH:DOC-010"]


def test_reproduction_skips_entries_without_reference_hash(monkeypatch):
    import deterministic_extraction as de_mod
    import promote_deterministic_batch as pdb
    manifest = json.load(open(xs.HANDOFF, encoding="utf-8"))
    expected = {d["document_id"]: d.get("canonical_content_sha256") for d in manifest["documents"]}
    monkeypatch.setattr(de_mod, "extract_document", lambda did, root, b, v: {"doc": did})
    monkeypatch.setattr(pdb, "canonical_content_sha256", lambda rec: expected[rec["doc"]])
    res = {r["document_id"]: r for r in xs.verify_reproduction("pdftotext", XPDF)}
    assert res["DOC-003"]["identical"] is None and res["DOC-003"]["skipped"]
    assert all(r["identical"] for d, r in res.items() if d != "DOC-003")
