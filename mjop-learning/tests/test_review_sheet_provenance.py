"""
Backwards-compatible uitbreiding van export_review_sheet: bronkolommen
achteraan, informatief. apply_review.py leest het uitgebreide bestand nog
steeds correct (op kolomnaam).
"""
import json
import os
import subprocess
import sys
import tempfile

from openpyxl import Workbook, load_workbook

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import export_review_sheet as ers  # noqa: E402

PROV = {"document_id": "DOC-010", "page": 10, "text_fragment": "Keuren hanebalk 1,00m2 2028 6 € 491 € 491 € 981",
        "source_confidence": "high", "block_id": "P10-L012-W07"}


def _rec(with_block=True):
    action = {
        "action_id": "A1", "element_id": "E1", "requires_human_review": True,
        "action": {"original_value": "Keuren hanebalk", "normalized_value": None, "requires_human_review": True},
        "unit": {"original_value": "m2", "normalized_value": "m2"},
        "planned_year": {"value": 2028, "requires_human_review": False,
                         "provenance": {k: v for k, v in PROV.items() if k != "block_id"}},
        "total_cost_as_stated": "491", "source_page": 10,
    }
    if with_block:
        action["field_provenance"] = {"total_cost_as_stated": PROV}
    return {"document_id": "DOC-010", "elements": [{"element_id": "E1", "element_type": {"original_value": "Hijsbalk"}}],
            "maintenance_actions": [action], "observations": []}


def test_existing_columns_unchanged_and_new_columns_appended():
    idx = ers.ACTION_COLUMNS.index("NOTITIES")
    assert ers.ACTION_COLUMNS[:idx + 1][-3:] == ["BESLISSING", "GECORRIGEERDE_WAARDE", "NOTITIES"]
    assert ers.ACTION_COLUMNS[idx + 1:] == ["bron_pagina", "bron_block_id", "bron_fragment"]
    assert ers.OBSERVATION_COLUMNS[-3:] == ["bron_pagina", "bron_block_id", "bron_fragment"]


def test_source_columns_filled_from_existing_provenance_only():
    rec = _rec()
    row = ers.build_action_rows(rec, {"E1": rec["elements"][0]})[0]
    assert len(row) == len(ers.ACTION_COLUMNS)
    assert row[-3:] == [10, "P10-L012-W07", PROV["text_fragment"]]
    rec2 = _rec(with_block=False)
    row2 = ers.build_action_rows(rec2, {"E1": rec2["elements"][0]})[0]
    assert row2[-3:] == [10, None, PROV["text_fragment"]]   # geen block_id -> leeg, niets verzonnen


def test_apply_review_still_reads_extended_sheet():
    with tempfile.TemporaryDirectory() as tmp:
        nd, vd = os.path.join(tmp, "normalized"), os.path.join(tmp, "verified")
        os.makedirs(nd)
        rec = _rec()
        json.dump(rec, open(os.path.join(nd, "DOC-010.json"), "w"))
        wb = Workbook()
        wb.remove(wb.active)
        rows = ers.build_action_rows(rec, {"E1": rec["elements"][0]})
        rows[0][ers.ACTION_COLUMNS.index("BESLISSING")] = "edit"
        rows[0][ers.ACTION_COLUMNS.index("GECORRIGEERDE_WAARDE")] = "inspect"
        ers.write_sheet(wb, "maintenance_actions", ers.ACTION_COLUMNS, rows)
        ers.write_sheet(wb, "observations", ers.OBSERVATION_COLUMNS, [])
        x = os.path.join(tmp, "r.xlsx")
        wb.save(x)
        subprocess.run([sys.executable, os.path.join(PROJECT_ROOT, "scripts", "apply_review.py"), "--xlsx", x,
                        "--normalized-dir", nd, "--verified-dir", vd, "--reviewer", "TD"],
                       check=True, capture_output=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        out = json.load(open(os.path.join(vd, "DOC-010.json")))
        a = out["maintenance_actions"][0]
        assert a["action"]["normalized_value"] == "inspect"
        assert a["action"]["human_verification"]["status"] == "edit"
        assert a["field_provenance"]["total_cost_as_stated"]["block_id"] == "P10-L012-W07"  # blijft behouden
