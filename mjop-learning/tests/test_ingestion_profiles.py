"""
Tests voor de uitgebreide ingestion-profielen (milestone expand-ingestion-profiles-v1):

  - PDF-familie pro_vve_overzicht15 met varianten standard / multi_object_projects /
    jarenplan_without_objectblad (scripts/template_detection.py)
  - spreadsheetfamilie pro_vve_overzicht15_spreadsheet met deterministische parser
    (scripts/spreadsheet_extraction.py)

Integratie op de ECHTE Testbatch 01 (data/incoming/Testbatch 01/). xpdf wordt afgespeeld uit
tests/fixtures/xpdf_pages/<sha256>.json: exact de uitvoer van de geverifieerde GitHub-runner
(xpdf 4.06, vastgelegd door tests/fixtures/capture_xpdf_pages.py). Alle writes naar tmp_path;
canonieke data en de gecommitte staging worden alleen gelezen.
"""
import copy
import glob
import hashlib
import json
import os
import shutil
import sys
from decimal import Decimal

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import incoming_registry as ir  # noqa: E402
import mjop_source_sections as src  # noqa: E402
import process_incoming_batch as p  # noqa: E402
import promotion_ledger as pl  # noqa: E402
import spreadsheet_extraction as sx  # noqa: E402
import template_detection as td  # noqa: E402
import text_layer as tl  # noqa: E402

TESTBATCH = os.path.join(PROJECT_ROOT, "data", "incoming", "Testbatch 01")
PAGES_DIR = os.path.join(PROJECT_ROOT, "tests", "fixtures", "xpdf_pages")
FAKE = os.path.join(PROJECT_ROOT, "tests", "fixtures", "fake_pdftotext.py")
XPDF = "pdftotext version 4.06 [www.xpdfreader.com]"
COMMITTED_BATCH = os.path.join(PROJECT_ROOT, "data", "incoming_batches", "IB-ad209360ab07")
DOC003 = os.path.join(PROJECT_ROOT, "data", "raw", "jp-heijestraat",
                      "2026_Overzicht 15 - Jarenplan (Gedetailleerd)_VvE 9690.xls")
NAMES = {"DOC-011": "Actualisatie MJOP VvE Granidastraat 46-80 2020 pdf.pdf", "DOC-012": "Actualisatie MOP 2024.pdf",
         "DOC-013": "MOP 2026 totaal.pdf", "DOC-014": "Meerjarenonderhoudsplan 2023_VvE 9261.pdf",
         "DOC-015": "Overzicht 15 - Jarenplan (Gedetailleerd) v3.xls"}

pytestmark = pytest.mark.skipif(not os.path.isdir(TESTBATCH), reason="Testbatch 01 niet aanwezig")


def _protected():
    out = pl.tracked_hashes(PROJECT_ROOT)
    for rel in ("data/incoming_registry.json", "data/price_observations/document_relations.json"):
        out[rel] = pl.sha256_file(os.path.join(PROJECT_ROOT, rel))
    for f in glob.glob(os.path.join(PROJECT_ROOT, "data", "incoming_batches", "**", "*"), recursive=True):
        if os.path.isfile(f):
            out[f] = pl.sha256_file(f)
    return out


@pytest.fixture(scope="module", autouse=True)
def canonical_and_committed_staging_unchanged():
    before = _protected()
    yield
    assert _protected() == before, "canonieke data of gecommitte staging is gewijzigd"


@pytest.fixture(scope="module")
def runner(tmp_path_factory):
    d = tmp_path_factory.mktemp("bin")
    b = d / "pdftotext"
    b.write_text(f'#!/bin/sh\nFAKE_PDFTOTEXT_VERSION="{XPDF}" exec "{sys.executable}" "{FAKE}" "$@"\n')
    b.chmod(0o755)
    old = os.environ.get("FAKE_PDFTOTEXT_PAGES_DIR")
    os.environ["FAKE_PDFTOTEXT_PAGES_DIR"] = PAGES_DIR
    r = p.runner_info(str(b))
    yield dict(r, runner_setup_status="VERIFIED_RUNNER_SETUP", runner_setup={"status": "VERIFIED_RUNNER_SETUP"})
    if old is None:
        os.environ.pop("FAKE_PDFTOTEXT_PAGES_DIR", None)
    else:
        os.environ["FAKE_PDFTOTEXT_PAGES_DIR"] = old


def _state(tmp):
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    shutil.copy2(os.path.join(PROJECT_ROOT, ir.REGISTRY_PATH), os.path.join(tmp, ir.REGISTRY_PATH))
    return tmp


TESTBATCH_PROMOTION = "IB-ad209360ab07"


def pre_promotion_root(dst):
    """Testbatch 01 is (deels) canoniek gepromoveerd. De profieltests beoordelen de Testbatch-documenten als
    INCOMING documenten: tegen de canonieke toestand vlak vóór die promotie, exact zoals vastgelegd in de
    promotiehistorie (data/history/incoming_promotions/<id>/pre, gecontroleerd tegen pre_manifest).
    Alles wat de promotie niet raakte wordt gesymlinkt (alleen lezen). Zonder promotie: het echte project."""
    state = next((s for s in pl.states(PROJECT_ROOT) if s["batch_id"] == TESTBATCH_PROMOTION), None)
    if state is None:
        return PROJECT_ROOT
    pre = os.path.join(PROJECT_ROOT, state["history"], "pre")
    for top in os.listdir(PROJECT_ROOT):
        if top not in ("data", "reports"):
            os.symlink(os.path.join(PROJECT_ROOT, top), os.path.join(dst, top))
    for top in ("data", "reports"):
        os.makedirs(os.path.join(dst, top))
        for name in os.listdir(os.path.join(PROJECT_ROOT, top)):
            snap = os.path.join(pre, top, name)
            if os.path.exists(snap):
                (shutil.copytree if os.path.isdir(snap) else shutil.copy2)(snap, os.path.join(dst, top, name))
            else:
                os.symlink(os.path.join(PROJECT_ROOT, top, name), os.path.join(dst, top, name))
    view = pl.tracked_hashes(dst, dirs=[d for d in pl.TRACKED_DIRS if d != "data/raw"])
    assert view == {k: v for k, v in state["pre_manifest"].items() if not k.startswith("data/raw/")}
    return dst


@pytest.fixture(scope="module")
def pre_root(tmp_path_factory):
    return pre_promotion_root(str(tmp_path_factory.mktemp("pre_root")))


@pytest.fixture(scope="module")
def batch(tmp_path_factory, runner, pre_root):
    state = _state(str(tmp_path_factory.mktemp("state")))
    plan = p.plan_batch(pre_root, os.path.join(PROJECT_ROOT, p.INCOMING_DIR), state_root=state, runner=runner)
    files, report = p.build_outputs(plan)
    p.apply_writes(state, p.plan_writes(state, files, plan["batch_id"]))
    return state, plan, files, report


def doc(plan, did):
    return next(d for d in plan["docs"] if d["document_id"] == did)


# ------------------------------------------------------------------ familie / variant

def test_doc011_detected_as_jarenplan_without_objectblad(batch):
    _, plan, _, _ = batch
    d = doc(plan, "DOC-011")
    assert d["family"]["family_id"] == "pro_vve_overzicht15" and d["family"]["variant"] == "jarenplan_without_objectblad"
    assert d["family"]["markers"]["object_sheet"] is None and d["family"]["markers"]["element_overview"] is None
    assert "jarenplan_without_objectblad" in d["family"]["explanation"][0]
    assert d["status"] == "EXTRACTED"
    rec = plan["extracted"]["DOC-011"]
    assert rec["extraction_metadata"]["profile_variant"] == "jarenplan_without_objectblad"
    assert rec["elements"] and all(e["element_code"]["provenance"]["extraction_rule"].endswith(
        "elements.jarenplan_element_line") for e in rec["elements"])
    assert all(e["quantity"]["value"] is None and e["unit"]["original_value"] is None for e in rec["elements"])
    assert not [a for a in rec["maintenance_actions"] if a["element_id"].endswith("-EL-UNLINKED")]
    vat = rec["document_level_values"]["vat_statement"]
    assert vat["value"].startswith("Alle prijzen zijn inclusief BTW")
    assert vat["provenance"]["extraction_rule"].endswith("jarenplan_toelichting_vat_fallback")
    assert rec["document_level_values"]["price_level_date"]["value"] is None       # geen Prijspeil in de bron


def test_doc013_detected_as_multi_object_projects_and_object_lines_are_not_actions(batch):
    _, plan, _, _ = batch
    d = doc(plan, "DOC-013")
    assert d["family"]["variant"] == "multi_object_projects" and d["status"] == "EXTRACTED"
    assert d["family"]["markers"]["jarenplan_title"] is None and d["family"]["markers"]["projects_overview"]
    po = plan["price_observations"]["DOC-013"]
    assert not [o for o in po["observations"] if o["source_representations"][0]["source_text"].startswith("93461")]
    diff, n = Decimal(po["checks"]["totaal_object_difference"]), len(po["observations"])
    assert abs(diff) <= (Decimal(n) + 1) / 2                                          # alleen afronding


def test_existing_standard_documents_keep_standard_variant_and_profile(batch):
    _, plan, _, _ = batch
    for did in ("DOC-012", "DOC-014"):
        assert doc(plan, did)["family"]["variant"] == "standard"
        assert "profile_variant" not in plan["extracted"][did]["extraction_metadata"]
    assert td.profile_for("pro_vve_overzicht15", "standard") == td.FAMILY_PROFILES["pro_vve_overzicht15"]
    assert set(td.profile_for("pro_vve_overzicht15", "standard")) == {"profile_id", "profile_version",
                                                                      "currency_rule", "note"}


def test_doc012_and_doc014_byte_identical_to_committed_staging(batch):
    _, _, files, _ = batch
    for did in ("DOC-012", "DOC-014"):
        for sub in ("extracted", "normalized", "price_observations"):
            rel = f"data/incoming_batches/IB-ad209360ab07/{sub}/{did}.json"
            assert files[rel] == open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8").read(), rel


def test_unknown_pdf_variant_stays_unknown():
    lines = [{"text": "Code/Element/Handeling Locatie Element/Gebrek Hvh Ehd Stj Cy 2024"},
             {"text": "Totaal object 1.000"}]
    r = td.detect_family("pdf", {"pages": [{"page": 1, "text_status": "ok", "lines": lines}]})
    assert r["family_id"] is None and r["variant"] is None and r["reason"] == "PARTIAL_FAMILY_MARKERS"
    assert len(r["explanation"]) == len(td.PDF_VARIANTS)
    both = lines + [{"text": "Overzicht 15 - Jarenplan (Gedetailleerd)"}, {"text": "Algemene Objectgegevens"}]
    r = td.detect_family("pdf", {"pages": [{"page": 1, "text_status": "ok", "lines": both}]})
    assert r["variant"] is None                        # objectblad zonder elementenoverzicht: geen variant


# varianten van via de incoming pipeline gepromoveerde documenten (Testbatch 01); de rest is batch 1
PROMOTED_VARIANTS = {"DOC-011": "jarenplan_without_objectblad", "DOC-012": "standard",
                     "DOC-013": "multi_object_projects", "DOC-015": "jarenplan_sheet"}


def test_batch1_documents_still_standard():
    reg = json.load(open(os.path.join(PROJECT_ROOT, "reports", "document_registry.json"), encoding="utf-8"))
    promoted = set(pl.promoted_document_ids(PROJECT_ROOT))
    assert promoted <= set(PROMOTED_VARIANTS)
    for d in reg["documents"]:
        path = os.path.join(PROJECT_ROOT, "data", "raw", *d["relative_path"].split("/"))
        fmt, _ = td.detect_format(path)
        fam = td.detect_family(fmt, tl.build_text_layer_for_file(path, d["document_id"], d["sha256"], "x"))
        expected = PROMOTED_VARIANTS[d["document_id"]] if d["document_id"] in promoted else (
            "jarenplan_sheet" if fmt == "xls" else "standard")
        assert fam["variant"] == expected, d["document_id"]


# ------------------------------------------------------------------ spreadsheet (echt)

def test_doc015_spreadsheet_extracted_deterministically(batch):
    _, plan, _, report = batch
    d = doc(plan, "DOC-015")
    assert d["family"]["family_id"] == "pro_vve_overzicht15_spreadsheet" and d["status"] == "EXTRACTED"
    assert "UNSUPPORTED_EXTRACTION" not in d["reasons"]
    rec = plan["extracted"]["DOC-015"]
    assert (len(rec["elements"]), len(rec["maintenance_actions"]), d["price_observation_candidates"]) == (23, 26, 18)
    t = rec["deterministic_trace"]
    assert t["unclassified_rows"] == [] and len(t["subtotal_rows"]) == 10 and len(t["footer_rows"]) == 1
    total = sum(Decimal(a["total_cost_as_stated"]) for a in rec["maintenance_actions"])
    assert total == Decimal(t["totaal_object"]["total"]) == Decimal("343877.7")      # tot op de cent
    assert rec["extraction_metadata"]["uses_ai_api"] is False
    assert rec["document_level_values"]["price_level_date"]["value"] is None          # geen Prijspeil in de bron
    assert not [o for o in report["spreadsheet_content_overlap"] if o["spreadsheet"] == "DOC-015"]


def test_doc015_sheet_and_cell_provenance(batch):
    _, plan, _, _ = batch
    rec = plan["extracted"]["DOC-015"]
    path = os.path.join(TESTBATCH, NAMES["DOC-015"])
    layer = tl.build_text_layer_for_file(path, "DOC-015", rec["extraction_metadata"]["source_sha256"], "x")
    cells = {c["id"]: (s["sheet"], c["cell_ref"]) for s in layer["sheets"] for r in s["rows"] for c in r["cells"]}
    provs = [pr for _, pr in __import__("record_validation").iter_provenance(rec)]
    assert provs and all(pr["page"] is None and cells[pr["block_id"]] == (pr["sheet"], pr["cell_ref"]) for pr in provs)
    for o in plan["price_observations"]["DOC-015"]["observations"]:
        rep = o["source_representations"][0]
        assert o["observation_id"].startswith("PO-DOC-015-S01-R") and rep["sheet"] and rep["row"]
        assert {"action_text", "quantity", "total"} <= set(rep["cell_refs"])


def test_doc003_spreadsheet_matches_canonical_pdf_extraction_of_doc002():
    sha = hashlib.sha256(open(DOC003, "rb").read()).hexdigest()
    layer = tl.build_text_layer_for_file(DOC003, "DOC-003", sha, "x")
    rec, _ = sx.extract_spreadsheet("DOC-003", layer, {"relative_path": "x", "sha256": sha}, src.UNIT_TOKENS)
    doc002 = json.load(open(os.path.join(PROJECT_ROOT, "data", "extracted", "DOC-002.json"), encoding="utf-8"))
    assert (len(rec["elements"]), len(rec["maintenance_actions"])) == \
        (len(doc002["elements"]), len(doc002["maintenance_actions"]))
    assert sum(Decimal(a["total_cost_as_stated"]) for a in rec["maintenance_actions"]) == \
        Decimal(rec["deterministic_trace"]["totaal_object"]["total"])


# ------------------------------------------------------------------ spreadsheet (synthetisch)

HEADER = ["Code/Element/Handeling", None, None, None, "Locatie Element/Gebrek", None, "Hvh", "Ehd", "Stj", None, "Cy",
          2024, 2025, "Totaal"]


def sheet_rows(extra=()):
    return [["Overzicht 15 - Jarenplan (Gedetailleerd)"],
            ["123 • VvE Teststraat 1-9\n\nTeststraat 1-9\n1234 AB Plaats"],
            ["Alle prijzen zijn inclusief BTW - (hoog/laag BTW tarief is toegepast)"],
            HEADER,
            ["21", None, "Buitenwanden"],
            ["2110", None, "Gevel metselwerk", None, "Voorgevel"],
            [None, None, "Reinigen gevel", None, None, None, 10, "m2", 2025, None, 6, 0, 100.5, 100.5],
            [None] * 11 + [0, 100.5, 100.5],                                   # subtotaal
            HEADER,                                                           # herhaalde kopregel
            ["46", None, "Schilderwerk"],
            ["4621", None, "Schilderwerk hout"],
            [None, None, "Groot schilderwerk", None, None, None, 5, "m2", 2024, None, 0, 200, 0, 200],
            [None] * 11 + [200, 0, 200],                                       # subtotaal
            *extra,
            ["Totaal object"] + [None] * 10 + [200, 100.5, 300.5],
            [None] * 13 + ["1"]]                                              # paginanummer


def make_xlsx(path, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet"
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return str(path)


def run_single(tmp_path, runner, name, rows=None, raw=None):
    inc = tmp_path / "in"
    inc.mkdir()
    if raw is not None:
        (inc / name).write_bytes(raw)
    else:
        make_xlsx(inc / name, rows)
    plan = p.plan_batch(PROJECT_ROOT, str(inc), state_root=_state(str(tmp_path / "st")), runner=runner)
    p.build_outputs(plan)
    return plan, plan["docs"][0]


def test_totals_headers_and_footers_are_never_actions(tmp_path, runner):
    plan, d = run_single(tmp_path, runner, "jarenplan.xlsx", sheet_rows())
    assert d["status"] == "EXTRACTED" and d["family"]["variant"] == "jarenplan_sheet"
    rec = plan["extracted"][d["document_id"]]
    t = rec["deterministic_trace"]
    assert [a["total_cost_as_stated"] for a in rec["maintenance_actions"]] == ["100.5", "200"]
    assert len(t["subtotal_rows"]) == 2 and len(t["repeated_header_rows"]) == 1 and len(t["footer_rows"]) == 1
    assert Decimal(t["totaal_object"]["total"]) == Decimal("300.5") and t["unclassified_rows"] == []
    po = plan["price_observations"][d["document_id"]]["observations"]
    assert [o["cycle_length_as_stated"] for o in po] == ["6", None]            # Cy 0 = lege cyclus
    assert rec["document_level_values"]["object_postcode"]["value"] == "1234 AB"


def test_malformed_spreadsheet_row_is_review_not_guessed(tmp_path, runner):
    plan, d = run_single(tmp_path, runner, "raar.xlsx", sheet_rows(extra=[["x?", None, None, None, None, None,
                                                                          None, None, None, None, None, "abc"]]))
    assert d["status"] == "REVIEW_REQUIRED" and any(i.startswith("spreadsheet_structure") for i in d["open_review_items"])


def test_empty_spreadsheet_is_unknown_template(tmp_path, runner):
    _, d = run_single(tmp_path, runner, "leeg.xlsx", [[None]])
    assert d["status"] == "UNKNOWN_TEMPLATE" and d["reasons"] == ["NO_FAMILY_MARKERS"]


def test_spreadsheet_without_complete_header_is_unknown_template(tmp_path, runner):
    rows = sheet_rows()
    rows[3] = [c if c != "Cy" else None for c in HEADER]
    rows[8] = rows[3]
    _, d = run_single(tmp_path, runner, "zonder_cy.xlsx", rows)
    assert d["status"] == "UNKNOWN_TEMPLATE"


def test_corrupt_xls_fails_cleanly(tmp_path, runner):
    _, d = run_single(tmp_path, runner, "kapot.xls", raw=bytes.fromhex("D0CF11E0A1B11AE1") + b"\0" * 64)
    assert d["status"] == "FAILED_VALIDATION" and d["reasons"][0].startswith("TEXT_LAYER_FAILED")


# ------------------------------------------------------------------ register, reproduceerbaarheid, relaties

def test_same_hashes_keep_same_doc_ids(batch, runner, tmp_path, pre_root):
    state, plan, _, _ = batch
    committed = ir.load(os.path.join(PROJECT_ROOT, ir.REGISTRY_PATH))
    assert ir.load(os.path.join(state, ir.REGISTRY_PATH)) == committed               # geen nieuwe ID's
    by_sha = {e["sha256"]: e["document_id"] for e in committed["documents"]}
    assert {d["document_id"] for d in plan["docs"]} == {"DOC-011", "DOC-012", "DOC-013", "DOC-014", "DOC-015"}
    assert all(by_sha[d["sha256"]] == d["document_id"] for d in plan["docs"])
    other = p.plan_batch(pre_root, os.path.join(PROJECT_ROOT, p.INCOMING_DIR), state_root=_state(str(tmp_path)),
                         runner=runner, batch_id="IB-rerun")
    assert {d["registration"] for d in other["docs"]} == {"existing_incoming"}
    assert [d["document_id"] for d in other["docs"]] == [d["document_id"] for d in plan["docs"]]


def test_rerun_is_byte_identical_and_noop(batch, runner, pre_root):
    state, plan, files, _ = batch
    plan2 = p.plan_batch(pre_root, os.path.join(PROJECT_ROOT, p.INCOMING_DIR), state_root=state, runner=runner)
    files2, _ = p.build_outputs(plan2)
    assert files2 == files and p.plan_writes(state, files2, plan2["batch_id"]) == []


def test_relations_remain_proposals_only(batch):
    _, plan, _, _ = batch
    rel = {tuple(r["document_ids"]): r for r in plan["relations"]}
    assert rel[("DOC-005", "DOC-014")]["kind"] == "SAME_BUILDING_CANDIDATE"
    assert rel[("DOC-006", "DOC-014")]["kind"] == "POSSIBLE_DUPLICATE_OTHER_BYTES"
    assert all(r["status"] == "CANDIDATE_REQUIRES_HUMAN_CONFIRMATION" and r["source_cluster"] == "NOT_ASSUMED"
               for r in plan["relations"])
    assert doc(plan, "DOC-014")["status"] == "REVIEW_REQUIRED"
    assert not [r for r in plan["relations"] if {"DOC-011", "DOC-013", "DOC-015"} & set(r["document_ids"])]


def test_no_ai_in_new_modules():
    for name in ("spreadsheet_extraction.py", "template_detection.py", "process_incoming_batch.py"):
        text = open(os.path.join(PROJECT_ROOT, "scripts", name), encoding="utf-8").read()
        for bad in ("import anthropic", "import openai", "import extract_batch", "from extract_batch"):
            assert bad not in text, (name, bad)
