import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "reports/frames/photo_archive_audit_v1"
DOC = (DIR / "maldenhof_photo_annotation_approval_v1.md").read_text()
AUD = json.loads((DIR / "maldenhof_photo_archive_audit_v1.json").read_text())
IDS = {p["photo_id"] for p in AUD["photos"]}
ROWS = [l for l in DOC.splitlines() if re.match(r"\| APP-\d{3} \|", l)]


def test_all_referenced_photo_ids_exist_in_audit_register():
    assert set(re.findall(r"MAP-\d{3}", DOC)) <= IDS


def test_shortlist_complete_with_valid_status():
    sl = [s["photo_id"] for s in AUD["shortlist"]]
    assert len(sl) == 15
    for ph in sl:
        m = re.search(rf"### {ph} \(.*?\): (READY_FOR_REVIEW|NEEDS_EVIDENCE|NOT_PROVEN)", DOC)
        assert m, ph
        if m.group(1) == "READY_FOR_REVIEW":
            assert next(p for p in AUD["photos"] if p["photo_id"] == ph)["bag_pand_link"]["status"] == "PAND_PROVEN_BY_VISIBLE_PLATE_ONLY"
    for ph in ("MAP-014", "MAP-017", "MAP-018", "MAP-019", "MAP-020", "MAP-021"):
        assert re.search(rf"### {ph} \(.*?\): NOT_PROVEN", DOC)  # rear: nooit automatisch PROVEN


def test_decisions_unique_and_all_open():
    ids = [r.split("|")[1].strip() for r in ROWS]
    assert ids == [f"APP-{i:03d}" for i in range(1, 49)]  # 48 unieke, aaneengesloten besluit-ID's
    assert all(r.rstrip().endswith("| OPEN |") for r in ROWS)
    assert not re.search(r"goedgekeurd door|APPROVED|\| GOEDGEKEURD", DOC)
    assert f"Totaal: {len(ids)} beslispunten, {len(ids)} OPEN, 0 goedgekeurd." in DOC


def test_all_overlap_groups_have_a_decision_and_stay_candidates():
    for g in AUD["same_object_candidates"]:
        assert f"Overlap {g['group_id']}" in DOC and g["status"] == "SAME_OBJECT_CANDIDATE" and g["merged"] is False


def test_pand_links_in_doc_match_register():
    for p in AUD["photos"]:
        if p["photo_id"] in {s["photo_id"] for s in AUD["shortlist"]} and not p["visible_house_number_plates"]:
            assert p["bag_pand_link"]["bag_pand_ids"] == []
