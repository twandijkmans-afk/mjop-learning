"""
Tekstlaag: deterministisch, stabiele blok-ID's, sha256-controle vooraf,
spreadsheets zonder floatverrassingen. Leest data/raw/ alleen (read-only).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import datetime
import json
import os
import re
import tempfile

import pytest

import document_registry as dr
import text_layer as tl

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(PROJECT_ROOT, "data", "raw")
REGISTRY = os.path.join(PROJECT_ROOT, "reports", "document_registry.json")


@pytest.fixture(scope="module")
def doc010_layer():
    return tl.build_text_layer("DOC-010", RAW, REGISTRY)


def test_text_layer_is_deterministic(doc010_layer):
    again = tl.build_text_layer("DOC-010", RAW, REGISTRY)
    assert tl.canonical_json(again) == tl.canonical_json(doc010_layer)
    assert again["text_layer_sha256"] == doc010_layer["text_layer_sha256"]


def test_block_ids_unique_and_well_formed(doc010_layer):
    idx = tl.block_index(doc010_layer)
    pat = re.compile(r"^P\d{2}-(L\d{3}(-W\d{2})?|T\d{2}-R\d{2}-C\d{2})$")
    assert all(pat.match(k) for k in idx)
    ids = []
    for p in doc010_layer["pages"]:
        for line in p["lines"]:
            ids.append(line["id"])
            ids.extend(w["id"] for w in line["words"])
    assert len(ids) == len(set(ids))


def test_page_count_and_text_status(doc010_layer):
    assert doc010_layer["page_count"] == 17
    assert all(p["text_status"] == "ok" for p in doc010_layer["pages"])
    assert doc010_layer["source_sha256"] == dr.get_document(dr.load_registry(REGISTRY), "DOC-010")["sha256"]


def test_no_timestamps_in_text_layer(doc010_layer):
    s = json.dumps(doc010_layer)
    assert "created" not in s.lower() and "generated_at" not in s


def test_line_text_is_join_of_words(doc010_layer):
    for p in doc010_layer["pages"]:
        for line in p["lines"]:
            assert line["text"] == " ".join(w["text"] for w in line["words"])


def test_refuses_when_source_hash_differs():
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "raw")
        os.makedirs(os.path.join(raw, "p"))
        open(os.path.join(raw, "p", "a.pdf"), "wb").write(b"%PDF-1.4 x")
        reg, _ = dr.reconcile({"registry_version": 1, "documents": []}, raw, register_new=True)
        regp = os.path.join(tmp, "reg.json")
        dr.save_registry(reg, regp)
        open(os.path.join(raw, "p", "a.pdf"), "wb").write(b"%PDF-1.4 y")
        with pytest.raises(dr.RegistryError):
            tl.build_text_layer("DOC-001", raw, regp)


def test_xls_text_layer_deterministic_and_exact():
    a = tl.build_text_layer("DOC-003", RAW, REGISTRY)
    b = tl.build_text_layer("DOC-003", RAW, REGISTRY)
    assert a["text_layer_sha256"] == b["text_layer_sha256"]
    idx = tl.block_index(a)
    cells = [v for v in idx.values() if v["kind"] == "sheet_cell"]
    assert cells and all(re.match(r"^[A-Z]+\d+$", c["cell_ref"]) for c in cells)
    # geen float-artefacten zoals 29.039999999
    assert not any(re.search(r"\d\.\d{9,}", c["text"]) for c in cells)


def test_xlsx_text_layer_values():
    import openpyxl
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "t.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Blad1"
        ws.append(["Element", "Bedrag", "Datum"])
        ws.append(["Gevel", 0.1 + 0.2, datetime.date(2023, 4, 1)])
        ws.append(["Dak", 1250, None])
        wb.save(p)
        layer = tl.build_text_layer_for_file(p, "DOC-999", "x", "t.xlsx")
        idx = tl.block_index(layer)
        # Excel bewaart max. 15 significante cijfers; de tekstlaag geeft exact de opgeslagen waarde
        assert idx["S01-R0002-C002"]["text"] == "0.3"
        assert idx["S01-R0002-C002"]["cell_ref"] == "B2"
        assert idx["S01-R0003-C002"]["text"] == "1250"
        assert idx["S01-R0002-C003"]["text"].startswith("2023-04-01")
