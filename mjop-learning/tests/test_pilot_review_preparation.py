"""Human Pilot Review Preparation v1: selectie, correctievoorstel OBS-MAP003-009 en onaangetaste brondata."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pilot_review_data as PD  # noqa: E402

REVIEW = ROOT / "reports/frames/photo_review_map003_map004_v1"
REP = json.loads((REVIEW / "maldenhof_pilot_review_preparation_v1.json").read_text())
MD = (REVIEW / "maldenhof_pilot_review_preparation_v1.md").read_text()
CORR = json.loads((REVIEW / "pilot_review/maldenhof_obs_map003_009_visibility_correction_proposal_v1.json").read_text())
REV = json.loads((REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.json").read_text())
QREP = json.loads((REVIEW / "maldenhof_p1_visual_quality_review_v1.json").read_text())
HTML = (REVIEW / "decision_pack/maldenhof_human_visual_decision_pack_v1.html").read_text()
PACK = json.loads(re.search(r"const PACK = (\{.*?\});\n\(function", HTML, re.S).group(1).replace("<\\/", "</"))
ITEMS = {i["review_id"]: i for i in PACK["items"]}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_selection_is_ten_existing_points_covering_all_eight_situations():
    assert len(PD.PILOT_ORDER) == len(set(PD.PILOT_ORDER)) == 10 == len(PD.PILOT) == len(REP["selected"])
    assert set(PD.PILOT_ORDER) <= set(ITEMS)
    assert len(PD.SITUATIONS) == 8 and sorted(r for v in PD.SITUATIONS.values() for r in v) == sorted(PD.PILOT_ORDER)
    q = {r["review_id"]: r for r in QREP["records"]}
    assert q["RV-SEP-001"]["quality_status"] == "VISUALLY_SUPPORTED"
    assert ITEMS["RV-REL-VR-020"]["relation_semantics"]["relation_type"] == "FACADE_SECTION"
    assert q["RV-REL-VR-027"]["evidence_class"] == "STRONG_VISUAL_SUPPORT" and q["RV-REL-VR-024"]["evidence_class"] == "MODERATE_VISUAL_SUPPORT"
    assert q["RV-REL-VR-026"]["evidence_class"] == "INSUFFICIENT_EVIDENCE"
    assert ITEMS["RV-OBS-MAP004-012"]["claude_proposal"] == "UNDECIDABLE" and "PARTIAL" in next(o["visibility"] for o in REV["observations"] if o["obs_id"] == "OBS-MAP004-012")
    assert next(o["observation_type"] for o in REV["observations"] if o["obs_id"] == "OBS-MAP003-027") == "EXTERIOR_DOOR"
    for r in REP["selected"]:                                                      # voorlopige classificaties zijn ongewijzigd overgenomen
        assert r["claude_proposal"] == ITEMS[r["review_id"]]["claude_proposal"] and r["quality_status"] == q[r["review_id"]]["quality_status"]


def test_every_point_has_dutch_explanation_in_all_required_parts():
    for rid, p in PD.PILOT.items():
        for k in ("visible", "decision", "evidence", "uncertain", "does", "doesnt", "title", "reason", "situation"):
            assert len(p[k]) > 20, (rid, k)
        # de gevolgen benoemen altijd wat het niet doet; nooit een pandkoppeling of instance impliceren
        assert re.search(r"geen (pand|instance|telling|samenvoeg)|niets", p["doesnt"], re.I), rid
        assert "automatisch" not in p["does"].lower()
    assert "SAME betekent hier uitsluitend" in PD.PILOT["RV-REL-VR-020"]["decision"] and "hetzelfde kozijn" in PD.PILOT["RV-REL-VR-020"]["doesnt"]


def test_visibility_correction_is_only_a_proposal_and_source_untouched():
    assert CORR["status"] == "PROPOSED_NOT_APPLIED" and CORR["current_value"] == "FULL" and CORR["proposed_value"] == "PARTIAL"
    assert "afzonderlijke menselijke goedkeuring" in CORR["requires"]
    e = CORR["effects_if_applied"]
    assert (e["instances_created"], e["counts_changed"], e["counts_in_any_total"], e["bag_links"], e["photo2_frozen_data_changed"]) == (0, False, False, 0, False)
    o = next(x for x in REV["observations"] if x["obs_id"] == "OBS-MAP003-009")
    assert o["visibility"] == "FULL" and o["is_instance"] is False and o["counts_in_any_total"] is False and o["bag_pand_id"] is None
    assert _sha(REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.json") == "28cccaf2eccfc82aa871b6a66c342043112406fb127d044ddf1f1051703e0719"
    assert _sha(REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.md") == "18e3aa8b7ec5083f1641e7160cc7993c97e166e0b63e2c056d95daac53107ff8"
    assert (REVIEW / "pilot_review/PQ-009_visibility_zoom.jpg").exists() and "Correctievoorstel OBS-MAP003-009" in MD


def test_no_effects_and_other_points_unchanged():
    ef = REP["effects"]
    assert (ef["instances_created"], ef["bag_links_created"], ef["building_totals"], ef["costs"], ef["app_decisions_open"]) == (0, 0, None, None, 48)
    assert REP["status"] == "PREPARATION_NOT_A_HUMAN_APPROVAL" and "Alle niet-geselecteerde punten blijven OPEN" in MD
    inst = json.loads((ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json").read_text())["photo_visible_counts"]
    assert (inst["PHOTO_VISIBLE_FRAME_COUNT"], inst["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"], inst["ordinary_frames_FULL"], inst["ordinary_frames_PARTIAL"]) == (11, 1, 9, 2)
    for f in (ROOT / "data").rglob("*.json"):
        assert "pilot_review" not in f.read_text() and "RV-SEP-" not in f.read_text(), f
