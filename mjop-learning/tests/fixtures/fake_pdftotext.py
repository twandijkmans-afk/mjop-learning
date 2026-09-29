#!/usr/bin/env python3
"""
Test-vervanger voor de EXTERNE executable `pdftotext` (alleen voor tests).

Gedraagt zich als de aanroepen die scripts/mjop_source_sections.py doet:
  pdftotext -v                                   -> versieregel (FAKE_PDFTOTEXT_VERSION)
  pdftotext -q -table -enc UTF-8 <pdf> -          -> pagina's uit FAKE_PDFTOTEXT_PAGES, gescheiden door \\f

Weigert elke andere modus dan -table (exit 2), zodat een test nooit stil een
andere weergave krijgt. mjop_source_sections zelf wordt niet vervangen.
"""
import json
import os
import sys

args = sys.argv[1:]
if "-v" in args:
    sys.stderr.write(os.environ.get("FAKE_PDFTOTEXT_VERSION", "pdftotext version 4.06 [www.xpdfreader.com]") + "\n")
    sys.stderr.write("Copyright 1996-2024 Glyph & Cog, LLC (test-vervanger)\n")
    sys.exit(0)
if "-table" not in args:
    sys.stderr.write("fake_pdftotext: alleen -table wordt ondersteund\n")
    sys.exit(2)
if os.environ.get("FAKE_PDFTOTEXT_PAGES_DIR"):
    # per document: echte runner-uitvoer, gekozen op sha256 van de PDF (tests/fixtures/xpdf_pages)
    import hashlib
    pdf = next(a for a in args if a.lower().endswith(".pdf"))
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    path = os.path.join(os.environ["FAKE_PDFTOTEXT_PAGES_DIR"], f"{sha}.json")
    if not os.path.exists(path):
        sys.stderr.write(f"fake_pdftotext: geen fixture voor {sha}\n")
        sys.exit(3)
    with open(path, encoding="utf-8") as f:
        pages = json.load(f)["pages"]
else:
    with open(os.environ["FAKE_PDFTOTEXT_PAGES"], encoding="utf-8") as f:
        pages = json.load(f)["pages"]
sys.stdout.buffer.write("".join(p + "\f" for p in pages).encode("utf-8"))
