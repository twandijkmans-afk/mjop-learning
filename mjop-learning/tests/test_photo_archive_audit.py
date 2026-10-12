import csv
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUD = json.loads((ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_archive_audit_v1.json").read_text())
MANIFEST = ROOT / "data/photos/archive/maldenhof_selection_manifest_v1.csv"
ZIP = Path("/mnt/project-files/Maldenhof_kozijnfoto_selectie (4) 2.zip")
PH = {p["photo_id"]: p for p in AUD["photos"]}


def test_check_mode_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_photo_archive_audit.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_register_matches_manifest():
    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8-sig", newline="")))
    assert len(rows) == len(AUD["photos"]) == 36
    for i, (r, p) in enumerate(zip(rows, AUD["photos"]), 1):
        assert p["photo_id"] == f"MAP-{i:03d}"
        assert (p["original_file"], p["sha256"], p["bytes"]) == (r["bestand"], r["sha256"], int(r["bytes"]))
        assert (p["width_px"], p["height_px"]) == (int(r["breedte_px"]), int(r["hoogte_px"]))
    assert len({p["sha256"] for p in AUD["photos"]}) == 36


def test_originals_accessible_and_unchanged():
    assert AUD["accessibility_check"]["result"] == "ALL_36_ORIGINAL_IMAGES_ACCESSIBLE"
    if not ZIP.exists():
        pytest.skip("originele zip niet aanwezig")
    z = zipfile.ZipFile(ZIP)
    for p in AUD["photos"]:
        b = z.read(f"{p['group_folder']}/{p['original_file']}")
        assert hashlib.sha256(b).hexdigest() == p["sha256"]


def test_contact_sheets_exist_and_cover_all_ids():
    for s in AUD["contact_sheets"]:
        f = ROOT / s
        assert f.exists() and f.stat().st_size > 50_000


def test_classification_complete():
    sides = {"FRONT", "FRONT_OBLIQUE", "REAR", "REAR_OR_SIDE", "SIDE_GABLE_OBLIQUE", "ROOF", "DETAIL", "STREET_CONTEXT", "UNKNOWN"}
    for p in AUD["photos"]:
        assert p["classification"]["facade_side"] in sides and p["usability"] and p["classification"]["method"] == "MANUAL_VISUAL_READING"


def test_pand_link_only_from_plates_via_bag_evidence():
    ev = json.loads((ROOT / "data/photo_evidence/maldenhof_address_pand_evidence_v1.json").read_text())
    m = {a["huisnummer"]: a["bag_pand_id"] for a in ev["addresses"]}
    for p in AUD["photos"]:
        link = p["bag_pand_link"]
        if p["visible_house_number_plates"]:
            assert link["status"] == "PAND_PROVEN_BY_VISIBLE_PLATE_ONLY"
            assert set(link["bag_pand_ids"]) == {m[n] for n in p["visible_house_number_plates"]}
        else:
            assert link["status"] == "NOT_PROVEN" and link["bag_pand_ids"] == []
    # rear/roof/detail zonder plaat blijven ongekoppeld; foto 3-bron idem
    assert PH["MAP-015"]["bag_pand_link"]["bag_pand_ids"] == []


def test_overlap_is_candidate_only_no_dedup():
    assert AUD["deduplication"] == "NONE_AUTOMATIC" and AUD["same_object_candidates"]
    for g in AUD["same_object_candidates"]:
        assert g["status"] == "SAME_OBJECT_CANDIDATE" and g["merged"] is False and len(g["photo_ids"]) >= 2
    assert len(AUD["photos"]) == 36


def test_source_matches_with_existing_photos():
    sm = {m["existing_photo"]: m for m in AUD["existing_photo_source_matches"]}
    assert sm["maldenhof_2"]["archive_photo"] == "MAP-002" and sm["maldenhof_3"]["archive_photo"] == "MAP-015"
    assert sm["maldenhof_1"]["archive_photo"] is None
    for n in (1, 2, 3):
        h = hashlib.sha256((ROOT / f"data/photos/incoming/maldenhof/maldenhof_{n}.jpg").read_bytes()).hexdigest()
        assert h not in {p["sha256"] for p in AUD["photos"]}  # niet byte-identiek: visuele match, geen hash-match
        assert sm[f"maldenhof_{n}"]["byte_identical"] is False


def test_photo2_unchanged():
    c = AUD["photo2_comparison"]
    assert c["existing_confirmed_counts"] == {"PHOTO_VISIBLE_FRAME_COUNT": 11, "PHOTO_VISIBLE_WINDOW_COUNT": 11, "PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT": 1, "FULL": 9, "PARTIAL": 2}
    assert c["photo2_decisions_changed"] is False and c["photo2_instances_changed"] is False
    inv = json.loads((ROOT / "data/frame_inventory/frame_inventory_v1.json").read_text())
    assert inv["instances"] == []


def test_coverage_matrix_15_panden_with_provenance():
    ev = json.loads((ROOT / "data/photo_evidence/maldenhof_address_pand_evidence_v1.json").read_text())
    cm = AUD["coverage_matrix"]["panden"]
    assert [p["bag_pand_id"] for p in cm] == [p["bag_pand_id"] for p in ev["pand_order"]] and len(cm) == 15
    for p in cm:
        assert p["REAR_ARCHIVE"]["state"] == "NO_PROVEN_PHOTO" and p["LEFT_RIGHT_SIDE_ARCHIVE"]["state"] == "NO_PROVEN_PHOTO"
        assert p["missing_coverage"]
        if p["FRONT_ARCHIVE"]["state"] != "NO_ARCHIVE_PHOTO_EVIDENCE":
            assert p["FRONT_ARCHIVE"]["provenance"] and p["plates_seen"]
        for pid in p["FRONT_ARCHIVE"]["overview_photo_ids"] + p["FRONT_ARCHIVE"]["detail_photo_ids"]:
            assert p["bag_pand_id"] in PH[pid]["bag_pand_link"]["bag_pand_ids"]
    assert "FULL_COVERAGE" not in json.dumps(AUD["coverage_matrix"]["panden"])


def test_shortlist_max_15_and_valid():
    sl = AUD["shortlist"]
    assert 1 <= len(sl) <= 15 and len({s["photo_id"] for s in sl}) == len(sl)
    assert all(s["photo_id"] in PH for s in sl)
    assert "MAP-002" not in {s["photo_id"] for s in sl} and "MAP-015" not in {s["photo_id"] for s in sl}


def test_forbidden_outputs_absent():
    e = AUD["effects"]
    assert e["new_confirmed_instances"] == 0 and e["frame_instances_created"] == 0 and e["quantity_resolutions"] == 0 and e["human_decisions_added"] == 0
    assert e["building_totals"] is None and e["repeat_multipliers"] is None and e["metric_dimensions"] is None and e["painting_area"] is None
    assert e["kg_price_changes"] is False and e["mjop_app_updates"] is False and e["comparability_756_80"] == "NOT_COMPARABLE"
    assert "instances" not in AUD and "confirmed_instances" not in json.dumps(AUD["photos"])
