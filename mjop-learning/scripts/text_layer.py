#!/usr/bin/env python3
"""
text_layer.py - stap 1 van Extractie v1: RAW -> deterministische tekstlaag.

Leest één brondocument (na sha256-controle tegen het document registry) en
schrijft data/extracted/_text_layer/<document_id>.json met stabiele blok-ID's.
Er wordt niets geïnterpreteerd; dit is alleen een traceerbare weergave van wat
er letterlijk in het bestand staat. Geen OCR (v1): pagina's zonder tekstlaag
worden gemarkeerd als "no_text_layer".

Blok-ID's (per document uniek, stabiel zolang bestand + generatorversie gelijk zijn):
  PDF
    P{pagina:02d}-L{regel:03d}             regel (woorden gegroepeerd op verticale positie)
    P{pagina:02d}-L{regel:03d}-W{woord:02d} woord binnen die regel (met x/y-coördinaten)
    P{pagina:02d}-T{tabel:02d}-R{rij:02d}-C{kolom:02d}  cel uit pdfplumber.find_tables()
  Spreadsheet (xls/xlsx)
    S{blad:02d}-R{rij:04d}                 rij
    S{blad:02d}-R{rij:04d}-C{kolom:03d}    cel (plus cell_ref in A1-notatie)

Determinisme: geen tijdstempels in de uitvoer, coördinaten afgerond op 2
decimalen, JSON met sort_keys. De sha256 van de canonieke JSON wordt in het
bestand zelf vastgelegd (text_layer_sha256, berekend zonder dat veld).

Gebruik:
    python3 scripts/text_layer.py --document DOC-010
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import document_registry  # noqa: E402

GENERATOR = "text_layer.py"
GENERATOR_VERSION = "1.0.0"
LINE_TOLERANCE = 3.0          # woorden binnen 3pt verticaal = zelfde regel
NO_TEXT_THRESHOLD = 15        # < 15 tekens op een pagina = geen bruikbare tekstlaag
DEFAULT_OUT_DIR = "data/extracted/_text_layer"


def _r(x):
    return round(float(x), 2)


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1)


def with_hash(layer):
    body = dict(layer)
    body.pop("text_layer_sha256", None)
    layer["text_layer_sha256"] = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return layer


# ---------------------------------------------------------------- PDF

def group_lines(words, page_no):
    """Groepeer pdfplumber-woorden tot regels (deterministisch: sorteer op top, x0)."""
    ws = sorted(words, key=lambda w: (_r(w["top"]), _r(w["x0"])))
    rows = []
    for w in ws:
        if rows and abs(_r(w["top"]) - rows[-1]["anchor_top"]) <= LINE_TOLERANCE:
            rows[-1]["words"].append(w)
        else:
            rows.append({"anchor_top": _r(w["top"]), "words": [w]})
    lines = []
    for li, row in enumerate(rows, start=1):
        lid = f"P{page_no:02d}-L{li:03d}"
        row_words = sorted(row["words"], key=lambda w: _r(w["x0"]))
        out_words = []
        for wi, w in enumerate(row_words, start=1):
            out_words.append({
                "id": f"{lid}-W{wi:02d}",
                "text": w["text"],
                "x0": _r(w["x0"]), "x1": _r(w["x1"]),
                "top": _r(w["top"]), "bottom": _r(w["bottom"]),
            })
        lines.append({
            "id": lid,
            "text": " ".join(w["text"] for w in out_words),
            "top": row["anchor_top"],
            "x0": min(w["x0"] for w in out_words),
            "x1": max(w["x1"] for w in out_words),
            "words": out_words,
        })
    return lines


def pdf_text_layer(path):
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            chars = len(page.chars)
            lines = group_lines(words, pno)
            tables = []
            try:
                found = page.find_tables()
            except Exception:  # pragma: no cover - pdfplumber-fout op één pagina
                found = []
            for ti, t in enumerate(found, start=1):
                rows = []
                for ri, row in enumerate(t.extract(), start=1):
                    rows.append({
                        "id": f"P{pno:02d}-T{ti:02d}-R{ri:02d}",
                        "cells": [
                            {"id": f"P{pno:02d}-T{ti:02d}-R{ri:02d}-C{ci:02d}", "text": cell}
                            for ci, cell in enumerate(row, start=1)
                        ],
                    })
                tables.append({"id": f"P{pno:02d}-T{ti:02d}", "bbox": [_r(v) for v in t.bbox], "rows": rows})
            pages.append({
                "page": pno,
                "width": _r(page.width), "height": _r(page.height),
                "char_count": chars,
                "text_status": "ok" if chars >= NO_TEXT_THRESHOLD else "no_text_layer",
                "lines": lines,
                "tables": tables,
            })
    return pages


# ---------------------------------------------------------------- spreadsheets

def _col_letters(ci):
    s = ""
    ci += 1
    while ci:
        ci, rem = divmod(ci - 1, 26)
        s = chr(65 + rem) + s
    return s


def _raw_repr(value):
    """Spreadsheetwaarde -> string zonder floatverrassingen (repr is exact-kortste)."""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        d = Decimal(repr(value))
        if d == d.to_integral_value():
            return format(d.quantize(Decimal(1)), "f")
        return format(d.normalize(), "f")
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return str(value)


def _sheet_block(si, name, rows_values):
    rows = []
    for ri, row in enumerate(rows_values, start=1):
        cells = []
        for ci, (ctype, value) in enumerate(row):
            if value is None or value == "":
                continue
            cells.append({
                "id": f"S{si:02d}-R{ri:04d}-C{ci + 1:03d}",
                "cell_ref": f"{_col_letters(ci)}{ri}",
                "type": ctype,
                "text": _raw_repr(value),
            })
        if cells:
            rows.append({
                "id": f"S{si:02d}-R{ri:04d}",
                "row": ri,
                "text": " | ".join(c["text"] for c in cells),
                "cells": cells,
            })
    return {"sheet_index": si, "sheet": name, "rows": rows}


def xls_text_layer(path):
    import xlrd
    type_names = {0: "empty", 1: "text", 2: "number", 3: "date", 4: "boolean", 5: "error", 6: "blank"}
    book = xlrd.open_workbook(path)
    sheets = []
    for si, sh in enumerate(book.sheets(), start=1):
        rows_values = []
        for r in range(sh.nrows):
            row = []
            for c in range(sh.ncols):
                ctype = sh.cell_type(r, c)
                value = sh.cell_value(r, c)
                if ctype == 3:  # datum: xlrd levert een float - expliciet omzetten
                    value = xlrd.xldate.xldate_as_datetime(value, book.datemode)
                row.append((type_names.get(ctype, str(ctype)), value))
            rows_values.append(row)
        sheets.append(_sheet_block(si, sh.name, rows_values))
    return sheets


def xlsx_text_layer(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = []
    for si, ws in enumerate(wb.worksheets, start=1):
        rows_values = []
        for row in ws.iter_rows(values_only=True):
            rows_values.append([(type(v).__name__, v) for v in row])
        sheets.append(_sheet_block(si, ws.title, rows_values))
    wb.close()
    return sheets


# ---------------------------------------------------------------- orchestration

def library_versions(file_type):
    versions = {}
    if file_type == "pdf":
        import pdfplumber
        import pdfminer
        versions = {"pdfplumber": pdfplumber.__version__, "pdfminer.six": pdfminer.__version__}
    elif file_type == "xls":
        import xlrd
        versions = {"xlrd": xlrd.__version__}
    elif file_type == "xlsx":
        import openpyxl
        versions = {"openpyxl": openpyxl.__version__}
    return versions


def build_text_layer_for_file(path, document_id, source_sha256, relative_path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    layer = {
        "document_id": document_id,
        "source_relative_path": relative_path,
        "source_sha256": source_sha256,
        "file_type": ext,
        "generator": {
            "script": GENERATOR, "version": GENERATOR_VERSION,
            "libraries": library_versions(ext),
            "params": {"line_tolerance_pt": LINE_TOLERANCE, "no_text_threshold_chars": NO_TEXT_THRESHOLD},
        },
    }
    if ext == "pdf":
        layer["pages"] = pdf_text_layer(path)
        layer["page_count"] = len(layer["pages"])
    elif ext == "xls":
        layer["sheets"] = xls_text_layer(path)
    elif ext == "xlsx":
        layer["sheets"] = xlsx_text_layer(path)
    else:
        raise ValueError(f"bestandstype {ext} wordt in v1 niet ondersteund")
    return with_hash(layer)


def build_text_layer(document_id, raw_dir="data/raw", registry_path="reports/document_registry.json"):
    registry = document_registry.load_registry(registry_path)
    path, doc = document_registry.verify_file(registry, document_id, raw_dir)
    return build_text_layer_for_file(path, document_id, doc["sha256"], doc["relative_path"])


def write_text_layer(layer, out_dir=DEFAULT_OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{layer['document_id']}.json")
    with open(out, "w") as f:
        f.write(canonical_json(layer))
        f.write("\n")
    return out


def load_text_layer(document_id, out_dir=DEFAULT_OUT_DIR):
    with open(os.path.join(out_dir, f"{document_id}.json")) as f:
        return json.load(f)


def block_index(layer):
    """id -> blok (regel, woord, tabelcel, spreadsheetrij of -cel) met paginanummer."""
    idx = {}
    for p in layer.get("pages", []):
        for line in p["lines"]:
            idx[line["id"]] = {"kind": "line", "page": p["page"], "text": line["text"], "obj": line}
            for w in line["words"]:
                idx[w["id"]] = {"kind": "word", "page": p["page"], "text": w["text"], "obj": w, "line_id": line["id"]}
        for t in p["tables"]:
            for row in t["rows"]:
                for c in row["cells"]:
                    idx[c["id"]] = {"kind": "table_cell", "page": p["page"], "text": c["text"], "obj": c}
    for s in layer.get("sheets", []):
        for row in s["rows"]:
            idx[row["id"]] = {"kind": "sheet_row", "page": None, "sheet": s["sheet"], "text": row["text"], "obj": row}
            for c in row["cells"]:
                idx[c["id"]] = {"kind": "sheet_cell", "page": None, "sheet": s["sheet"], "text": c["text"],
                                "cell_ref": c["cell_ref"], "obj": c}
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--document", required=True, action="append", help="document_id, bijv. DOC-010 (herhaalbaar)")
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--registry", default="reports/document_registry.json")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    for doc_id in args.document:
        layer = build_text_layer(doc_id, args.raw_dir, args.registry)
        out = write_text_layer(layer, args.out_dir)
        n = layer.get("page_count", len(layer.get("sheets", [])))
        print(f"{doc_id}: tekstlaag -> {out} ({n} pagina's/bladen, sha256 {layer['text_layer_sha256'][:12]}…)")


if __name__ == "__main__":
    main()
