"""
Tests voor scripts/promote_deterministic_batch.py (Promotion Foundations v1) en de
external_element_coding-regel in scripts/normalize_batch.py.

De manifesttests draaien op een tijdelijke kopie van de handoff-laag (ruwe bestanden
via symlink); de echte data/ wordt alleen gelezen.
"""
import copy
import glob
import hashlib
import json
import os
import shutil
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import normalize_batch as nb  # noqa: E402
import promote_deterministic_batch as pdb  # noqa: E402

BATCH = os.path.join(PROJECT_ROOT, pdb.BATCH_DIR)
PROTECTED = ["data/raw", "data/extracted", "data/normalized", "data/verified", "data/price_observations",
             "data/comparability", "data/kengetallen", "data/review_decisions", "data/match_review_decisions",
             "data/extracted_deterministic"]


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


@pytest.fixture
def root(tmp_path):
    """Minimale kopie: handoff-laag, registry, document_relations; data/raw als symlink."""
    shutil.copytree(BATCH, tmp_path / pdb.BATCH_DIR)
    (tmp_path / "reports").mkdir()
    shutil.copy(os.path.join(PROJECT_ROOT, "reports", "document_registry.json"), tmp_path / "reports")
    (tmp_path / "data" / "price_observations").mkdir(parents=True)
    shutil.copy(os.path.join(PROJECT_ROOT, "data", "price_observations", "document_relations.json"),
                tmp_path / "data" / "price_observations")
    os.symlink(os.path.join(PROJECT_ROOT, "data", "raw"), tmp_path / "data" / "raw")
    return tmp_path


def _manifest(root):
    return json.load(open(root / pdb.BATCH_DIR / "manifest.json", encoding="utf-8"))


def _write_manifest(root, m, fix_sha=True):
    p = root / pdb.BATCH_DIR / "manifest.json"
    p.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if fix_sha:
        (root / pdb.BATCH_DIR / "manifest.sha256").write_text(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  manifest.json\n", encoding="utf-8")


def _entry(m, doc):
    return next(e for e in m["documents"] if e["document_id"] == doc)


def _errors(root, **kw):
    res = pdb.check_handoff(str(root), **kw)
    return res["ok"], " | ".join(res["errors"])


# ------------------------------------------------------------------ --check

def test_committed_v11_handoff_passes():
    res = pdb.check_handoff(PROJECT_ROOT)
    assert res["ok"], res["errors"]
    assert sorted(d for d, i in res["documents"].items() if i["status"] == "PASS") == pdb.EXPECTED_PASS
    for doc in pdb.EXPECTED_PASS:
        i = res["documents"][doc]
        assert i["repository_output_sha256_ok"] and i["canonical_content_sha256_ok"]
        assert i["windows_validation_bytes_reproducible"]
    assert res["documents"]["DOC-003"]["status"] == "DUPLICATE_SKIP"
    assert res["manifest"]["manifest_version"] == "1.1.0" and res["manifest"]["xpdf_version"] == pdb.XPDF


def test_copy_of_handoff_passes(root):
    ok, err = _errors(root)
    assert ok, err


def _crlf_sha(root, e):
    return hashlib.sha256((root / e["output_path"]).read_bytes().replace(b"\n", b"\r\n")).hexdigest()


def test_crlf_hash_as_repository_hash_is_never_accepted(root):
    m = _manifest(root)
    e = _entry(m, "DOC-006")
    e["repository_output_sha256"] = _crlf_sha(root, e)
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-006: repository_output_sha256 klopt niet" in err


def test_wrong_canonical_content_sha_fails(root):
    m = _manifest(root)
    _entry(m, "DOC-001")["canonical_content_sha256"] = "a" * 64
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-001: canonical_content_sha256 klopt niet" in err


def test_wrong_windows_validation_hash_fails(root):
    m = _manifest(root)
    e = _entry(m, "DOC-002")
    e["validated_windows_output_sha256"] = e["repository_output_sha256"]
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-002: validated_windows_output_sha256 is niet exact reproduceerbaar" in err


def test_output_file_with_cr_fails_windows_reproducibility(root):
    """Een CRLF-bestand in de repository wordt niet 'goedgerekend': repository-hash en
    Windows-relatie falen allebei."""
    m = _manifest(root)
    e = _entry(m, "DOC-008")
    p = root / e["output_path"]
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    ok, err = _errors(root)
    assert not ok and "DOC-008: repository_output_sha256 klopt niet" in err
    assert "DOC-008: validated_windows_output_sha256 is niet exact reproduceerbaar" in err


def test_history_missing_fails(root):
    (root / pdb.BATCH_DIR / "history" / "manifest_v1.0.0.json").unlink()
    ok, err = _errors(root)
    assert not ok and "historisch manifest ontbreekt" in err


def test_history_changed_fails(root):
    p = root / pdb.BATCH_DIR / "history" / "manifest_v1.0.0.json"
    p.write_bytes(p.read_bytes() + b" ")
    ok, err = _errors(root)
    assert not ok and "historisch manifest heeft een andere sha256" in err


def test_windows_hash_must_equal_history_output_sha(root):
    """De Windows-hash moet exact de vastgelegde v1.0 output_sha256 zijn (historie consistent)."""
    h = root / pdb.BATCH_DIR / "history" / "manifest_v1.0.0.json"
    old = json.loads(h.read_text(encoding="utf-8"))
    next(e for e in old["documents"] if e["document_id"] == "DOC-009")["output_sha256"] = "c" * 64
    h.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_sha = hashlib.sha256(h.read_bytes()).hexdigest()
    (h.parent / "manifest_v1.0.0.sha256").write_text(f"{new_sha}  manifest_v1.0.0.json\n", encoding="utf-8")
    m = _manifest(root)
    m["supersedes"]["manifest_sha256"] = new_sha
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-009: validated_windows_output_sha256 is niet de historische v1.0 output_sha256" in err
    assert "historisch manifest heeft een andere sha256" not in err


def test_manifest_v10_is_not_accepted_as_current(root):
    b = root / pdb.BATCH_DIR
    shutil.copy(b / "history" / "manifest_v1.0.0.json", b / "manifest.json")
    _write_manifest(root, _manifest(root))
    ok, err = _errors(root)
    assert not ok and "manifest_version is '1.0.0'" in err


def test_unexpected_file_in_history_fails(root):
    (root / pdb.BATCH_DIR / "history" / "extra.json").write_text("{}\n", encoding="utf-8")
    ok, err = _errors(root)
    assert not ok and "history/extra.json" in err


def test_wrong_manifest_sha256_fails(root):
    (root / pdb.BATCH_DIR / "manifest.sha256").write_text("0" * 64 + "  manifest.json\n", encoding="utf-8")
    ok, err = _errors(root)
    assert not ok and "manifest.sha256 klopt niet" in err


def test_changed_source_sha_fails(root):
    m = _manifest(root)
    _entry(m, "DOC-005")["source_sha256"] = "f" * 64
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-005: source_sha256 wijkt af van document_registry" in err


def test_changed_output_sha_fails(root):
    m = _manifest(root)
    _entry(m, "DOC-007")["repository_output_sha256"] = "e" * 64
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-007: repository_output_sha256 klopt niet" in err


def test_changed_output_file_fails(root):
    p = root / pdb.BATCH_DIR / "DOC-010.json"
    p.write_bytes(p.read_bytes().replace(b'"DOC-010"', b'"DOC-010" ', 1))
    ok, err = _errors(root)
    assert not ok and "DOC-010: repository_output_sha256 klopt niet" in err
    assert "DOC-010: canonical_content_sha256 klopt niet" not in err   # alleen witruimte: inhoud gelijk


def test_missing_pass_document_fails(root):
    m = _manifest(root)
    m["documents"] = [e for e in m["documents"] if e["document_id"] != "DOC-008"]
    _write_manifest(root, m)
    (root / pdb.BATCH_DIR / "DOC-008.json").unlink()
    ok, err = _errors(root)
    assert not ok and "ontbrekende documenten in manifest: ['DOC-008']" in err


def test_unexpected_document_fails(root):
    m = _manifest(root)
    extra = copy.deepcopy(_entry(m, "DOC-010"))
    extra["document_id"] = "DOC-011"
    m["documents"].append(extra)
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "onverwachte documenten in manifest: ['DOC-011']" in err


def test_unexpected_file_in_batch_dir_fails(root):
    (root / pdb.BATCH_DIR / "DOC-011.json").write_text("{}\n", encoding="utf-8")
    ok, err = _errors(root)
    assert not ok and "onverwachte bestanden" in err


def test_doc003_extraction_json_present_fails(root):
    shutil.copy(root / pdb.BATCH_DIR / "DOC-002.json", root / pdb.BATCH_DIR / "DOC-003.json")
    ok, err = _errors(root)
    assert not ok and "DOC-003: DUPLICATE_SKIP maar DOC-003.json staat" in err


@pytest.mark.parametrize("field,value", [("duplicate_of", "DOC-001"), ("relation", "DREL-002")])
def test_wrong_duplicate_skip_record_fails(root, field, value):
    m = _manifest(root)
    _entry(m, "DOC-003")[field] = value
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-003: DUPLICATE_SKIP moet duplicate_of DOC-002 / relation DREL-001 zijn" in err


def test_doc003_as_pass_fails(root):
    m = _manifest(root)
    _entry(m, "DOC-003")["status"] = "PASS"
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-003: moet DUPLICATE_SKIP zijn" in err


def test_wrong_xpdf_version_fails(root):
    m = _manifest(root)
    m["xpdf_version"] = "pdftotext version 4.05"
    _entry(m, "DOC-001")["pdftotext_version"] = "pdftotext version 0.86.1"
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "xpdf_version is" in err and "DOC-001: pdftotext_version is geen xpdf 4.06" in err


def test_missing_profile_metadata_fails(root):
    m = _manifest(root)
    del _entry(m, "DOC-004")["rules_version"]
    _write_manifest(root, m)
    ok, err = _errors(root)
    assert not ok and "DOC-004: PASS-sleutels wijken af" in err


# ------------------------------------------------------------------ normalize_batch: externe elementcodering

LOOKUPS = {k: nb.load_vocab(os.path.join(PROJECT_ROOT, "vocabularies"), v) for k, v in
           [("element_type", "element_type"), ("element_code", "element_code"), ("material", "material"),
            ("unit", "unit"), ("defect_type", "defect_type"), ("action", "maintenance_action")]}


def _load_batch(doc):
    return json.load(open(os.path.join(BATCH, f"{doc}.json"), encoding="utf-8"))


def test_external_element_coding_is_not_normalized():
    rec = nb.normalize_record(_load_batch("DOC-004"), LOOKUPS)
    codes = [e["element_code"] for e in rec["elements"]]
    assert codes and all(c["original_value"] for c in codes)
    assert all(c["normalized_value"] is None for c in codes)
    assert all(c["normalization_skipped_reason"] == "external_element_coding" for c in codes)
    # de interne vocabulaire zou deze codes wél kennen - dat is precies het risico
    assert any(str(c["original_value"]).lower() in LOOKUPS["element_code"] for c in codes)
    assert "element_code_internal" not in json.dumps(rec)


def test_external_flag_in_extraction_metadata_is_respected():
    rec = {"document_id": "DOC-900", "extraction_metadata": {"external_element_coding": True},
           "elements": [{"element_id": "E1", "element_code": {"original_value": "2110", "normalized_value": None}}]}
    nb.normalize_record(rec, LOOKUPS)
    assert rec["elements"][0]["element_code"]["normalized_value"] is None


def test_internal_element_codes_still_normalized():
    rec = nb.normalize_record(_load_batch("DOC-005"), LOOKUPS)
    for e in rec["elements"]:
        c = e["element_code"]
        assert "normalization_skipped_reason" not in c
        assert c["normalized_value"] == LOOKUPS["element_code"].get(str(c["original_value"]).strip().lower())
    assert any(e["element_code"]["normalized_value"] for e in rec["elements"])


@pytest.mark.parametrize("path", sorted(glob.glob(os.path.join(PROJECT_ROOT, "data", "extracted", "DOC-*.json"))))
def test_normalize_record_reproduces_canonical_normalized(path):
    """Bestaande documenten gedragen zich exact zoals voorheen: extracted -> normalize_record
    geeft dezelfde inhoud als de canonieke data/normalized."""
    rec = json.load(open(path, encoding="utf-8"))
    expected = json.load(open(os.path.join(PROJECT_ROOT, "data", "normalized", os.path.basename(path)), encoding="utf-8"))
    assert nb.normalize_record(rec, LOOKUPS) == expected


# ------------------------------------------------------------------ accept-classificatie (synthetisch)

def _new_action(aid, year, amount, text="Reinigen metselwerk", qty="815.95", page=11, block="P11-L010",
                frag="Reinigen metselwerk 815,95m2 2025 7 ..."):
    prov = {"page": page, "block_id": block, "text_fragment": frag}
    return {"action_id": aid, "element_id": "D-EL-001", "source_page": page,
            "action": {"original_value": text, "provenance": prov}, "quantity": {"value": qty},
            "unit": {"original_value": "m2"}, "planned_year": {"value": year}, "total_cost_as_stated": amount}


def _old_action(amount, year=2025, text="Reinigen metselwerk", qty="815,95", page=11):
    return {"action_id": "OLD-1", "source_page": page, "action": {"original_value": text},
            "quantity": {"value": qty}, "unit": {"original_value": "m2"}, "planned_year": {"value": year},
            "total_cost_as_stated": amount}


def test_accept_exact_match_candidate_single_year():
    rows = pdb.new_rows({"maintenance_actions": [_new_action("A1", 2025, "8955")]})
    cls, d = pdb.match_old_action(_old_action("€ 8.955"), rows)
    assert cls == "EXACT_MATCH_CANDIDATE" and d["new_action_ids"] == ["A1"] and d["amount_basis"] == "per_year_amount"


def test_accept_exact_match_candidate_row_total_over_years():
    rows = pdb.new_rows({"maintenance_actions": [_new_action("A1", 2025, "8955"), _new_action("A2", 2032, "8955")]})
    cls, d = pdb.match_old_action(_old_action("€ 17.910"), rows)
    assert cls == "EXACT_MATCH_CANDIDATE" and d["new_action_ids"] == ["A1", "A2"]
    assert d["amount_basis"] == "row_total_over_years"


def test_accept_ambiguous_with_identical_source_rows():
    rows = pdb.new_rows({"maintenance_actions": [_new_action("A1", 2025, "8955", block="P11-L010"),
                                                 _new_action("A2", 2025, "8955", block="P11-L020")]})
    cls, d = pdb.match_old_action(_old_action("€ 8.955"), rows)
    assert cls == "AMBIGUOUS" and d["candidate_action_ids"] == ["A1", "A2"]


@pytest.mark.parametrize("old,reason", [
    (_old_action("€ 8.955", text="Reinigen metselwerk (gevels)"), "no_row_with_same_page_text_quantity_unit"),
    (_old_action("€ 8.955", page=12), "no_row_with_same_page_text_quantity_unit"),
    (_old_action("€ 8.955", qty="815,90"), "no_row_with_same_page_text_quantity_unit"),
    (_old_action("€ 8.956"), "amount_or_year_differs"),
    (_old_action("€ 8.955", year=2026), "amount_or_year_differs"),
])
def test_accept_no_match_without_fuzzy_matching(old, reason):
    rows = pdb.new_rows({"maintenance_actions": [_new_action("A1", 2025, "8955")]})
    cls, d = pdb.match_old_action(old, rows)
    assert cls == "NO_MATCH" and d["reason"] == reason


def test_text_only_difference_is_reported_but_not_matched():
    rows = pdb.new_rows({"maintenance_actions": [_new_action("A1", 2025, "8955")]})
    cls, d = pdb.match_old_action(_old_action("€ 8.955", text="Reinigen metselwerk (gevels)"), rows)
    assert cls == "NO_MATCH" and d["rows_equal_except_action_text"] == 1


# ------------------------------------------------------------------ --dry-run

def test_dry_run_refuses_invalid_handoff_without_explicit_flag(root, tmp_path):
    (root / pdb.BATCH_DIR / "manifest.sha256").write_text("0" * 64 + "  manifest.json\n", encoding="utf-8")
    out = tmp_path / "r.json"
    assert pdb.main(["--dry-run", "--root", str(root), "--report", str(out)]) == 1
    assert not out.exists()


def test_dry_run_changes_no_canonical_data_and_is_byte_stable(tmp_path):
    before = _hashes()
    out1, out2 = tmp_path / "r1.json", tmp_path / "r2.json"
    assert pdb.main(["--dry-run", "--root", PROJECT_ROOT, "--report", str(out1)]) == 0
    assert pdb.main(["--dry-run", "--root", PROJECT_ROOT, "--report", str(out2)]) == 0
    assert _hashes() == before
    b1 = out1.read_bytes()
    assert b1 == out2.read_bytes() and b"\r" not in b1 and b1.endswith(b"}\n")
    rep = json.loads(b1)
    assert rep["handoff_valid"] is True and rep["check"]["errors"] == []
    assert rep["old_accepts"]["total"] == 220
    assert sum(rep["old_accepts"]["counts"].values()) == 220
    assert set(rep["old_accepts"]["counts"]) <= {"EXACT_MATCH_CANDIDATE", "AMBIGUOUS", "NO_MATCH"}
    assert rep["duplicate_skip"][0]["document_id"] == "DOC-003"
    assert all(d["document_id"] != "DOC-003" for d in rep["documents"])
    hd = rep["human_decisions"]["counts"]
    assert hd["records"] == 30 and hd["observation_ids_present"] == 30
    assert "timestamp" not in b1.decode() and "generated_at" not in b1.decode()


def test_committed_dry_run_report_is_current(tmp_path):
    out = tmp_path / "r.json"
    assert pdb.main(["--dry-run", "--root", PROJECT_ROOT, "--report", str(out)]) == 0
    assert out.read_bytes() == open(os.path.join(PROJECT_ROOT, pdb.DEFAULT_REPORT), "rb").read()


def test_dry_run_refuses_to_write_into_data(tmp_path):
    before = _hashes()
    assert pdb.main(["--dry-run", "--root", PROJECT_ROOT, "--report", "data/verified/x.json"]) == 2
    assert _hashes() == before


def test_stable_json_output():
    a = {"b": [1, {"z": "é", "a": None}], "a": 1}
    s = pdb.dumps(a)
    assert s == pdb.dumps(json.loads(s)) and s.endswith("}\n") and "é" in s
    assert s.index('"a"') < s.index('"b"')
