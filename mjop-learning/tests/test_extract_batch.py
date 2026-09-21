"""
Tests voor scripts/extract_batch.py. Zolang de echte LLM-extractie nog niet
is geimplementeerd, is het BELANGRIJKSTE dat dit script niets verzint: elk
aangemaakt bestand moet status "pending_extraction" hebben met lege
building/elements/observations/maintenance_actions, nooit gevulde data.
"""
import glob
import importlib.util
import json
import os
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "extract_batch", os.path.join(PROJECT_ROOT, "scripts", "extract_batch.py")
)
extract_batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract_batch)


def test_placeholder_has_no_fabricated_content():
    tmpl = extract_batch.EXTRACTED_RECORD_TEMPLATE
    assert tmpl["status"] == "pending_extraction"
    assert tmpl["building"] is None
    assert tmpl["elements"] == []
    assert tmpl["observations"] == []
    assert tmpl["maintenance_actions"] == []


def test_extract_batch_does_not_overwrite_existing_file():
    with tempfile.TemporaryDirectory() as tmp:
        reports_dir = os.path.join(tmp, "reports")
        out_dir = os.path.join(tmp, "extracted")
        os.makedirs(reports_dir)
        os.makedirs(out_dir)

        inventory = [{"document_id": "DOC-001"}]
        json.dump(inventory, open(os.path.join(reports_dir, "document_inventory.json"), "w"))

        # simuleer dat er al (mensgecontroleerde of eerder geëxtraheerde) data staat
        existing = {"status": "extracted_by_human", "elements": [{"echt": "iets"}]}
        json.dump(existing, open(os.path.join(out_dir, "DOC-001.json"), "w"))

        import sys
        old_argv = sys.argv
        sys.argv = [
            "extract_batch.py",
            "--reports-dir", reports_dir,
            "--out-dir", out_dir,
        ]
        try:
            extract_batch.main()
        finally:
            sys.argv = old_argv

        result = json.load(open(os.path.join(out_dir, "DOC-001.json")))
        assert result == existing, "extract_batch.py mag bestaande data nooit overschrijven"
