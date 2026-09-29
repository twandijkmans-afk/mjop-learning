#!/usr/bin/env python3
"""
Legt de echte xpdf-4.06-uitvoer (pdftotext -q -table -enc UTF-8, exact de productieroute van
mjop_source_sections.pdf_pages) van PDF's vast als testfixture:
    tests/fixtures/xpdf_pages/<sha256 van de PDF>.json
Alleen bedoeld voor de GitHub Actions-runner met geverifieerde xpdf (xpdf_runner_setup.py).
Tests spelen deze pagina's af via fake_pdftotext.py (FAKE_PDFTOTEXT_PAGES_DIR), zodat parser-
ontwikkeling en regressietests exact de runner-uitvoer gebruiken. Geen AI, geen andere parser.
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import deterministic_extraction as de  # noqa: E402
import mjop_source_sections as src  # noqa: E402

OUT = os.path.join(ROOT, "tests", "fixtures", "xpdf_pages")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdftotext", required=True)
    ap.add_argument("--runner-setup", required=True)
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args(argv)
    binary, version = de.check_pdftotext(args.pdftotext)
    setup = json.load(open(args.runner_setup, encoding="utf-8"))
    if setup.get("status") != "VERIFIED_RUNNER_SETUP":
        sys.exit(f"runner niet geverifieerd: {setup.get('status')}")
    os.makedirs(OUT, exist_ok=True)
    for p in sorted(args.paths):
        if not p.lower().endswith(".pdf"):
            continue
        sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
        pages = src.pdf_pages(p, binary)
        fixture = {"_note": "Echte xpdf-uitvoer (runner), vastgelegd door tests/fixtures/capture_xpdf_pages.py",
                   "source_sha256": sha, "source_name": os.path.basename(p), "pdftotext_version": version,
                   "pdftotext_mode": src.PDFTOTEXT_MODE, "xpdf_archive_sha256": setup.get("observed_archive_sha256"),
                   "runner_setup_status": setup["status"], "pages": pages}
        with open(os.path.join(OUT, f"{sha}.json"), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
        print(f"{sha[:12]} {len(pages):3d} pagina's  {os.path.basename(p)}")


if __name__ == "__main__":
    main()
