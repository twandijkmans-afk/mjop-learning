#!/usr/bin/env python3
"""
inventory_documents.py

Stap 1-2 van het masterplan: inventariseer alle bestanden in data/raw/ en
schrijf een overzicht (CSV + JSON) conform schemas/document.schema.json naar
reports/. Dit script raadt NIETS over de inhoud dat het niet kan onderbouwen
uit de tekst zelf (zie CLAUDE.md) - onduidelijke velden worden null.

Gebruik:
    python3 scripts/inventory_documents.py [--raw-dir data/raw] [--out-dir reports]

Vereist: pdfplumber, openpyxl, xlrd, python-docx (pip install ...)
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")
PERIOD_RE = re.compile(r"\b(20[0-4]\d)\s*[-/tot]{1,4}\s*(20[0-4]\d)\b")
MONEY_RE = re.compile(r"€\s?\d[\d.]*(,\d{2})?")
QUANT_RE = re.compile(r"\b\d+([.,]\d+)?\s?(m1|m2|m²|m³|st\.|stuks|stk)\b", re.IGNORECASE)
NEN_RE = re.compile(r"NEN\s?2767", re.IGNORECASE)
CONDITIE_RE = re.compile(r"conditie\s?score|conditiescore", re.IGNORECASE)
INSPECTIE_RE = re.compile(r"opname\s?d\.?d\.?|inspectiedatum|datum\s?opname|opnamedatum", re.IGNORECASE)


def sha256_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def analyze_pdf(path, max_pages=40):
    """Bepaalt page_count, text-vs-scan, tabellen, foto's en een aantal
    tekstuele signalen. Retourneert een dict met alleen wat betrouwbaar uit
    de tekst is af te leiden - GEEN gegokte waarden."""
    result = {}
    if pdfplumber is None:
        result["error"] = "pdfplumber niet geinstalleerd"
        return result
    try:
        with pdfplumber.open(path) as pdf:
            n_pages = len(pdf.pages)
            result["page_count"] = n_pages
            total_chars, n_tables, n_images, text_parts = 0, 0, 0, []
            for i in range(min(n_pages, max_pages)):
                page = pdf.pages[i]
                t = page.extract_text() or ""
                total_chars += len(t)
                text_parts.append(t)
                try:
                    n_tables += len(page.find_tables())
                except Exception:
                    pass
                try:
                    n_images += len(page.images)
                except Exception:
                    pass
            full_text = "\n".join(text_parts)
            avg = total_chars / max(1, min(n_pages, max_pages))
            result["text_pdf_or_scan"] = (
                "text_pdf" if avg > 80 else "scan_or_image" if avg < 15 else "mixed_low_text"
            )
            result["has_tables"] = n_tables > 0
            result["has_photos"] = n_images > 0
            result["has_costs"] = bool(MONEY_RE.search(full_text))
            result["has_quantities"] = bool(QUANT_RE.search(full_text))
            result["has_condition_scores"] = bool(CONDITIE_RE.search(full_text)) or bool(NEN_RE.search(full_text))
            result["has_inspection_data"] = bool(INSPECTIE_RE.search(full_text))
            period_m = PERIOD_RE.search(full_text)
            result["possible_mjop_period"] = f"{period_m.group(1)}-{period_m.group(2)}" if period_m else None
    except Exception as e:
        result["error"] = str(e)
    return result


def build_inventory(raw_dir):
    records = []
    counter = 0
    for root, dirs, files in os.walk(raw_dir):
        for fn in sorted(files):
            if fn.lower() == "thumbs.db":
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, raw_dir)
            counter += 1
            ext = os.path.splitext(fn)[1].lower().lstrip(".")
            rec = {
                "document_id": f"DOC-{counter:03d}",
                "filename": fn,
                "relative_path": rel,
                "project_folder": rel.split(os.sep)[0],
                "file_type": ext,
                "file_size_bytes": os.path.getsize(full),
                "sha256": sha256_of(full),
                # onbekende velden expliciet null - niet weglaten, niet gokken:
                "document_type": None,
                "possible_building_year": None,
                "possible_number_of_units": None,
                "possible_inspection_date": None,
                "possible_advisor": None,
                "quality_estimate": None,
            }
            if ext == "pdf":
                rec.update(analyze_pdf(full))
            records.append(rec)
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    if not os.path.isdir(args.raw_dir):
        print(f"Raw-map niet gevonden: {args.raw_dir}", file=sys.stderr)
        sys.exit(1)

    records = build_inventory(args.raw_dir)
    os.makedirs(args.out_dir, exist_ok=True)

    json.dump(records, open(os.path.join(args.out_dir, "document_inventory.json"), "w"),
               ensure_ascii=False, indent=2)

    fields = ["document_id", "project_folder", "relative_path", "filename", "file_type",
              "file_size_bytes", "sha256", "page_count", "text_pdf_or_scan", "has_tables",
              "has_photos", "has_inspection_data", "has_quantities", "has_costs",
              "has_condition_scores", "possible_mjop_period", "document_type",
              "quality_estimate"]
    with open(os.path.join(args.out_dir, "document_inventory.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)

    print(f"{len(records)} documenten geinventariseerd -> {args.out_dir}/document_inventory.{{csv,json}}")


if __name__ == "__main__":
    main()
