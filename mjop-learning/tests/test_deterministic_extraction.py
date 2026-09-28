"""
Deterministische route (extract_batch.py --mode deterministic) zonder echte xpdf:
alleen de EXTERNE executable pdftotext wordt vervangen door tests/fixtures/
fake_pdftotext.py met de fixture tests/fixtures/pdftotext_doc010/pages.json.
mjop_source_sections, registry, tekstlaag (echte DOC-010-PDF, alleen gelezen),
schemas en record_validation draaien echt. Alle output gaat naar tmp; data/ wordt
alleen gelezen.
"""
import glob
import hashlib
import json
import os
import socket
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import compare_extractions as ce  # noqa: E402
import deterministic_extraction as de  # noqa: E402
import record_validation as rv  # noqa: E402
import text_layer as tl  # noqa: E402

FIXTURE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "pdftotext_doc010", "pages.json")
FAKE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "fake_pdftotext.py")
PROTECTED = ["data/raw", "data/verified", "data/extracted", "data/normalized", "data/kengetallen",
             "data/comparability", "data/price_observations", "data/review_decisions", "data/match_review_decisions"]
XPDF = "pdftotext version 4.06 [www.xpdfreader.com]"


def _hashes():
    out = {}
    for d in PROTECTED:
        for p in sorted(glob.glob(os.path.join(PROJECT_ROOT, d, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                out[os.path.relpath(p, PROJECT_ROOT)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


@pytest.fixture(scope="module", autouse=True)
def protected_data_unchanged():
    before = _hashes()
    yield
    assert _hashes() == before, "beschermde data is gewijzigd"


def _fake_bin(tmp_path, version=XPDF, name="pdftotext"):
    d = tmp_path / f"bin_{abs(hash(version))}"
    d.mkdir(exist_ok=True)
    p = d / name
    p.write_text(f'#!/bin/sh\nFAKE_PDFTOTEXT_VERSION="{version}" exec "{sys.executable}" "{FAKE}" "$@"\n')
    p.chmod(0o755)
    return str(p)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PDFTOTEXT_PAGES", FIXTURE)
    monkeypatch.delenv("PDFTOTEXT", raising=False)
    return _fake_bin(tmp_path)


@pytest.fixture(scope="module")
def record():
    import tempfile
    from pathlib import Path
    mp = pytest.MonkeyPatch()
    with tempfile.TemporaryDirectory() as t:
        mp.setenv("FAKE_PDFTOTEXT_PAGES", FIXTURE)
        binary = _fake_bin(Path(t))
        b, v = de.check_pdftotext(binary)
        rec = de.extract_document("DOC-010", PROJECT_ROOT, b, v)
    mp.undo()
    return rec


@pytest.fixture(scope="module")
def layer():
    return tl.build_text_layer("DOC-010", os.path.join(PROJECT_ROOT, "data", "raw"),
                               os.path.join(PROJECT_ROOT, "reports", "document_registry.json"))


# ------------------------------------------------------------------ fixture-herkomst

def test_fixture_content_is_literal_doc010(layer):
    """Elke inhoudsregel van de fixture bestaat letterlijk in DOC-010: jarenplanrijen in de vastgelegde
    xpdf-uitvoer (price_observations), overige regels in de tekstlaag van de echte PDF."""
    import mjop_source_sections as src
    pages = json.load(open(FIXTURE))["pages"]
    po = json.load(open(os.path.join(PROJECT_ROOT, "data", "price_observations", "price_observations_batch1.json")))
    recorded = {r["source_text"] for o in po["observations"] if o["document_id"] == "DOC-010"
                for r in o["source_representations"]}
    rows, _, _ = src.parse_jarenplan_page(pages[9], 10)
    for r in rows:
        if r["annual_amounts_raw"]:
            assert r["raw_line"] in recorded, r["raw_line"]
    keys = {}
    for p in layer["pages"]:
        keys[p["page"]] = {rv._source_key(l["text"]) for l in p["lines"]}
    for pno, text in enumerate(pages, start=1):
        for line in text.splitlines():
            if line.strip() and not line.startswith("Code/Element") and not line.startswith("Code    Element"):
                assert rv._source_key(line) in keys[pno], (pno, line)


# ------------------------------------------------------------------ dependency

def test_dependency_ok_for_xpdf_406(fake):
    assert de.check_pdftotext(fake) == (fake, XPDF)


@pytest.mark.parametrize("version", ["pdftotext version 24.02.0", "pdftotext version 3.04",
                                     "pdftotext version 4.05 [www.xpdfreader.com]"])
def test_dependency_rejects_poppler_and_other_versions(tmp_path, monkeypatch, version):
    monkeypatch.setenv("FAKE_PDFTOTEXT_PAGES", FIXTURE)
    b = _fake_bin(tmp_path, version)
    with pytest.raises(de.DependencyError) as e:
        de.check_pdftotext(b)
    assert "4.06" in str(e.value) and "geen fallback" in str(e.value)


def test_dependency_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("PDFTOTEXT", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(de.DependencyError) as e:
        de.check_pdftotext()
    assert "niet gevonden" in str(e.value)


def test_cli_fails_early_without_dependency_and_writes_nothing(tmp_path):
    out = tmp_path / "pilot"
    env = dict(os.environ, PATH=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")
    env.pop("PDFTOTEXT", None)
    r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "extract_batch.py"),
                        "--mode", "deterministic", "--document", "DOC-010", "--pilot-out-dir", str(out)],
                       capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)
    assert r.returncode == 3
    assert "xpdf pdftotext 4.06" in r.stderr
    assert not out.exists()


def test_poppler_on_path_is_not_used_as_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PDFTOTEXT_PAGES", FIXTURE)
    monkeypatch.delenv("PDFTOTEXT", raising=False)
    poppler = _fake_bin(tmp_path, "pdftotext version 24.02.0")
    monkeypatch.setenv("PATH", os.path.dirname(poppler))
    with pytest.raises(de.DependencyError):
        de.check_pdftotext()


# ------------------------------------------------------------------ route + inhoud

def test_cli_deterministic_route_writes_only_pilot(fake, tmp_path):
    out = tmp_path / "pilot"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", ANTHROPIC_API_KEY="")
    r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "extract_batch.py"),
                        "--mode", "deterministic", "--document", "DOC-010", "--pdftotext", fake,
                        "--pilot-out-dir", str(out)], capture_output=True, text=True, env=env, cwd=PROJECT_ROOT)
    assert r.returncode == 0, r.stderr
    assert sorted(os.listdir(out)) == ["DOC-010.json"]
    rec = json.load(open(out / "DOC-010.json"))
    assert rec["extraction_mode"] == "deterministic"


def test_no_network_and_no_ai_api(fake, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("netwerkverbinding geprobeerd")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    rec = de.extract_document("DOC-010", PROJECT_ROOT, fake, XPDF)
    assert rec["extraction_metadata"]["uses_ai_api"] is False
    assert rec["extraction_metadata"]["network_calls"] is False
    assert "anthropic" not in sys.modules and "openai" not in sys.modules
    src = open(os.path.join(PROJECT_ROOT, "scripts", "deterministic_extraction.py")).read()
    for bad in ("import anthropic", "import openai", "urllib.request", "import requests", "http.client"):
        assert bad not in src


def test_metadata(record):
    m = record["extraction_metadata"]
    assert m["parser"] == "mjop_source_sections" and m["parser_text_mode"] == "-table"
    assert m["pdftotext_version"] == XPDF
    assert m["document_profile"] == "pro_vve_overzicht15" and m["rules_version"]
    assert m["source_sha256"] == "d102f1f7f0faf8641e9874efab2a3d0516a7add2eb333e6c2f4e60965dc3099a"
    assert len(m["text_layer_sha256"]) == 64 and m["text_layer_generator"]["version"]
    assert "extracted_at" not in record and "timestamp" not in json.dumps(m)


def test_object_fields(record):
    b = record["building"]
    assert b["construction_year"]["value"] == 1935
    assert b["number_of_units"]["value"] == 4
    assert b["address"]["value"] == "Zomerdijkstraat 14, Uiterwaardenstraat 141"   # Object-sectie, niet Opdrachtgever
    assert b["inspection_date"]["value"] == "1-4-2023"
    assert b["building_type"]["value"] is None
    assert b["mjop_period"]["value"] is None and b["mjop_period"]["requires_human_review"]
    assert b["mjop_period"]["possible_values"][0]["value"] == "2023-2037"
    dv = record["document_level_values"]
    assert dv["renovation_year"]["value"] == 2005
    assert dv["price_level_date"]["value"] == "1-4-2023"
    assert dv["price_level_date"]["provenance"]["extraction_rule"].startswith("mjop_source_sections.")
    assert dv["vat_statement"]["value"] == "De bedragen in de begrotingen zijn inclusief BTW"
    assert "0 Procent" in dv["indexation_statement"]["value"]


def test_condition_legend(record):
    assert record["document_level_values"]["condition_legend"]["value"] == [
        "1 = Uitstekende conditie", "2 = Goed", "3 = Redelijk", "4 = Matig", "5 = Slecht", "6 = Zeer slecht",
        "8 = Nader onderzoek nodig", "9 = Niet te inspecteren"]


def test_elements_and_nothing_guessed(record):
    els = record["elements"]
    assert [(e["element_code"]["original_value"], e["element_name"]["value"], e["location"]["value"],
             e["quantity"]["value"], e["unit"]["original_value"]) for e in els] == [
        ("2110", "Gevelconstructie metselwerk", "Voor- en achtergevel", "148.25", "m2"),
        ("2110", "Loodslabben opgaand werk", "Dak", "10.00", "m1"),
        ("2120", "Hijsbalk staal", "Achtergevel", "1.00", "st"),
        ("3120", "Kozijn buiten aluminium", "Voor- en achtergevel", "84.28", "m2"),
        ("6710", "Dakbeveiliging algemeen", "Dak", "1.00", "pst"),
        ("9999", "Hoogwerker tot 18 meter hoog", None, "1.00", "pst")]
    for e in els:
        assert e["material"]["original_value"] is None
        assert e["construction_year"]["value"] is None
        assert e["gemeenschappelijk_of_prive"] is None
        assert e["element_type"]["normalized_value"] is None
    assert record["deterministic_trace"]["unclassified_element_overview_lines"] == []


def test_condition_scores(record):
    obs = {o["element_id"]: o for o in record["observations"]}
    assert [o["condition_score"]["original_value"] for o in record["observations"]] == ["2", "2", "8", "3", "0", "0"]
    assert all(o["condition_score"]["normalized_value"] is None and o["condition_score"]["scale"] is None
               for o in record["observations"])
    assert [o["requires_human_review"] for o in record["observations"]] == [False, False, True, False, True, True]
    assert obs["DOC-010-EL-003"]["condition_score"]["original_value"] == "8"


def test_actions_from_leading_source_layer(record):
    acts = [(a["element_id"], a["action"]["original_value"], a["planned_year"]["value"], a["quantity"]["value"],
             a["unit"]["original_value"], a["total_cost_as_stated"]) for a in record["maintenance_actions"]]
    assert acts == [
        ("DOC-010-EL-001", "Herstellen metselwerk", 2028, "5.93", "m2", "1351"),
        ("DOC-010-EL-003", "Keuren hanebalk", 2028, "1.00", "m2", "491"),
        ("DOC-010-EL-003", "Keuren hanebalk", 2034, "1.00", "m2", "491"),
        ("DOC-010-EL-004", "Onderhoud kozijnen (confrom offerte Kemo)", 2028, "84.28", "m2", "11024")]
    for a in record["maintenance_actions"]:
        assert a["cost_year"] is None and a["unit_cost"] == {"value": None, "is_estimated": False}
        assert "direct_cost_calculated" not in a and "unit_cost_calculated" not in a
    assert [r["text"] for r in record["deterministic_trace"]["rows_without_positive_amount"]] == [
        "Vervangen hijswerk staal 1,00 st 2052 0"]


def test_currency_profile_rule_visible_in_provenance(record):
    rules = {a["total_cost_as_stated"]: a["field_provenance"]["total_cost_as_stated"]["extraction_rule"]
             for a in record["maintenance_actions"]}
    assert rules["1351"] == "nl_values.profile:pdf_whole_euro_dot_thousands"
    assert rules["11024"] == "nl_values.profile:pdf_whole_euro_dot_thousands"
    assert rules["491"] == "nl_values.generic"
    ev = record["extraction_metadata"]["currency_evidence"]
    assert ev["consistent"] and ev["with_decimals"] == 0


def test_currency_rule_refused_without_evidence(fake, tmp_path, monkeypatch):
    pages = json.load(open(FIXTURE))
    pages["pages"][9] = pages["pages"][9].replace("  491", "49,10", 1)   # één bedrag met decimalen -> geen bewijs
    alt = tmp_path / "pages.json"
    alt.write_text(json.dumps(pages))
    monkeypatch.setenv("FAKE_PDFTOTEXT_PAGES", str(alt))
    rec = de.extract_document("DOC-010", PROJECT_ROOT, fake, XPDF)
    a = rec["maintenance_actions"][0]
    assert a["total_cost_as_stated"] is None and a["requires_human_review"] is True
    assert rec["extraction_metadata"]["currency_evidence"]["consistent"] is False


def test_block_provenance(record, layer):
    assert rv.verify_block_provenance(record, layer) == []
    assert record["elements"][0]["element_name"]["provenance"]["block_id"] == "P06-L005"
    a = record["maintenance_actions"][3]
    p = a["field_provenance"]["total_cost_as_stated"]
    assert p["block_id"] == "P10-L033" and p["related_block_ids"] == ["P10-L034"]
    assert p["text_fragment"].split("\n")[1] == "Kemo)"
    # dubbel voorkomende regels (Postcode/Plaats op p2) krijgen GEEN block_id
    assert "block_id" not in record["document_level_values"]["object_city"]["provenance"]
    assert rv.validate_entities(record) == []


def test_output_isolation_and_canonical_refusal(record, tmp_path):
    default = de.pilot_output_path("DOC-010", PROJECT_ROOT)
    assert default == os.path.join(PROJECT_ROOT, "data", "extracted", "_deterministic_pilot", "DOC-010.json")
    for d in ("data/extracted", "data/normalized", "data/verified"):
        with pytest.raises(de.ExtractionError):
            de.pilot_output_path("DOC-010", PROJECT_ROOT, os.path.join(PROJECT_ROOT, d))
    # de normale pipeline pakt de pilotmap niet op (niet-recursieve glob in normalize_batch)
    ext = tmp_path / "extracted"
    (ext / "_deterministic_pilot").mkdir(parents=True)
    (ext / "_deterministic_pilot" / "DOC-010.json").write_text(de.dumps(record))
    import normalize_batch
    old = sys.argv
    sys.argv = ["normalize_batch.py", "--extracted-dir", str(ext), "--normalized-dir", str(tmp_path / "norm")]
    try:
        normalize_batch.main()
    finally:
        sys.argv = old
    assert not os.path.exists(tmp_path / "norm" / "DOC-010.json")


def test_two_runs_byte_identical(fake, tmp_path):
    a = de.dumps(de.extract_document("DOC-010", PROJECT_ROOT, fake, XPDF))
    b = de.dumps(de.extract_document("DOC-010", PROJECT_ROOT, fake, XPDF))
    assert a == b
    p1 = de.write_pilot(json.loads(a), PROJECT_ROOT, str(tmp_path / "r1"))
    p2 = de.write_pilot(json.loads(b), PROJECT_ROOT, str(tmp_path / "r2"))
    assert open(p1, "rb").read() == open(p2, "rb").read()


def test_llm_route_default_unchanged(tmp_path):
    """Zonder --mode blijft extract_batch de LLM-route (hier: dry-run placeholders)."""
    rep = tmp_path / "reports"
    rep.mkdir()
    (rep / "document_inventory.json").write_text(json.dumps([{"document_id": "DOC-001"}]))
    r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "extract_batch.py"), "--dry-run",
                        "--reports-dir", str(rep), "--out-dir", str(tmp_path / "out")],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert r.returncode == 0
    assert json.load(open(tmp_path / "out" / "DOC-001.json"))["status"] == "pending_extraction"


def test_unknown_document_profile_refused(fake):
    with pytest.raises(de.ExtractionError):
        de.extract_document("DOC-001", PROJECT_ROOT, fake, XPDF)


# ------------------------------------------------------------------ review + vergelijking

def test_review_export_from_pilot_path(record, tmp_path):
    pilot = tmp_path / "_deterministic_pilot"
    de.write_pilot(record, PROJECT_ROOT, str(pilot))
    out = tmp_path / "review" / "DOC-010_pilot_review.xlsx"
    r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "export_review_sheet.py"),
                        "--normalized-dir", str(pilot), "--out", str(out)],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert r.returncode == 0, r.stderr
    from openpyxl import load_workbook
    wb = load_workbook(out)
    obs = list(wb["observations"].iter_rows(values_only=True))
    header = obs[0]
    rows = [dict(zip(header, row)) for row in obs[1:]]
    assert sorted(r["condition_score"] for r in rows) == ["0", "0", "8"]
    assert all(r["bron_pagina"] in (6, 8) and r["bron_block_id"] for r in rows)


def test_comparison_report(record, tmp_path):
    verified_path = os.path.join(PROJECT_ROOT, "data", "verified", "DOC-010.json")
    before = open(verified_path, "rb").read()
    rep = ce.compare(json.load(open(verified_path)), record)
    assert open(verified_path, "rb").read() == before
    by = {(i["category"], i["key"]): i for i in rep["items"]}
    assert by[("building", "construction_year")]["outcome"] == "exact_equal"
    assert by[("building", "address")]["outcome"] == "different_value"
    assert by[("building", "building_type")]["outcome"] == "only_existing"
    assert by[("amounts", "hijsbalk staal | achtergevel -> keuren hanebalk [2034]")]["outcome"] == "exact_equal"
    assert by[("condition_scores", "hoogwerker tot 18 meter hoog | ")]["outcome"] == "only_deterministic"
    assert by[("maintenance_actions",
               "kozijn buiten aluminium | voor- en achtergevel -> onderhoud kozijnen (confrom offerte kemo)")
              ]["outcome"] == "only_deterministic"
    assert all(i["human_review_needed"] for i in rep["items"] if i["outcome"] != "exact_equal"
               and i["outcome"] != "null_or_unknown")
    assert "correct" not in json.dumps(rep["summary"])
    assert set(rep["summary"]) == set(ce.CATEGORIES)


def test_comparison_cli_refuses_output_in_data(record, tmp_path):
    p = tmp_path / "pilot.json"
    p.write_text(de.dumps(record))
    r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "compare_extractions.py"),
                        "--existing", os.path.join(PROJECT_ROOT, "data", "verified", "DOC-010.json"),
                        "--pilot", str(p), "--out", os.path.join(PROJECT_ROOT, "data", "x.json")],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert r.returncode == 2 and not os.path.exists(os.path.join(PROJECT_ROOT, "data", "x.json"))
    out = tmp_path / "cmp.json"
    r = subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "compare_extractions.py"),
                        "--existing", os.path.join(PROJECT_ROOT, "data", "verified", "DOC-010.json"),
                        "--pilot", str(p), "--out", str(out)],
                       capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert r.returncode == 0 and json.load(open(out))["comparison"].startswith("read-only")
