import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = json.loads((ROOT / "data/photo_evidence/maldenhof_3_candidate_human_decisions_v1.json").read_text())
STATE = json.loads((ROOT / "data/photo_evidence/maldenhof_3_review_state_v1.json").read_text())
ANN = json.loads((ROOT / "data/photo_evidence/maldenhof_3_frame_annotation_v1.json").read_text())
REC = {r["target_id"]: r for r in STORE["records"]}
CAND = {c["candidate_id"]: c for c in STATE["candidates"]}


def test_check_mode_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_photo3_human_review.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_store_append_only_human():
    assert STORE["append_only"] is True
    ids = [r["decision_id"] for r in STORE["records"]]
    assert ids == sorted(set(ids)) and len(ids) == 9
    for r in STORE["records"]:
        assert r["reviewer_type"] == "human" and r["reviewed_at"] and r["reason"]
        assert r["source_photo"] == "maldenhof_3.jpg" and r["supersedes"] is None


def test_rebuild_does_not_alter_existing_records():
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_photo3_human_review as b
    again = b.build_store(json.loads(json.dumps(STORE)))
    assert again == STORE


def test_unknowns_and_accepted_window():
    for k in ("FC-M3-001", "FC-M3-002"):
        assert CAND[k]["review_status"] == "KEEP_UNKNOWN" and CAND[k]["type"] == "UNKNOWN_OPENING"
    assert CAND["FC-M3-003"]["review_status"] == "ACCEPT_OBSERVATION"
    assert (CAND["FC-M3-003"]["type"], CAND["FC-M3-003"]["visibility"]) == ("WINDOW", "PARTIAL")


def test_window_door_combination_is_one_frame_opening():
    r = STATE["relation_review"]
    assert r["decision"] == "SAME_FRAME_OPENING_WINDOW_DOOR_COMBINATION"
    assert r["frame_subtype"] == "WINDOW_DOOR_COMBINATION" and r["physical_frame_openings"] == 1
    assert STATE["photo_observation_summary"]["WINDOW_DOOR_COMBINATION_FRAME_OPENINGS"] == 1
    comps = {c["component"]: c["count"] for c in r["semantic_subcomponents"]}
    assert comps == {"WINDOW_SECTION": 1, "EXTERIOR_DOOR_SECTION": 1}
    assert r["future_quantity_contributions"] == {"FRAME_COUNT": 1, "WINDOW_COUNT": 1, "EXTERIOR_DOOR_COUNT": 1}
    assert r["material"] == "UNKNOWN" and r["instance_created"] is False
    assert CAND["FC-M3-004"]["review_status"] == CAND["FC-M3-005"]["review_status"] == "PART_OF_REL_M3_001_FRAME_OPENING"


def test_roof_windows_and_dormer_not_instances():
    exp = {"FC-M3-006": "PARTIAL", "FC-M3-007": "FULL", "FC-M3-008": "FULL", "FC-M3-009": "FULL"}
    for k, v in exp.items():
        assert CAND[k]["type"] == "ROOF_WINDOW" and CAND[k]["visibility"] == v
        assert REC[k]["activate_as_exterior_frame"] is False
    d = REC["FC-M3-010"]
    assert d["accepted_type"] == "DORMER_WINDOW" and d["parent"] == "DORMER-M3-001"
    assert d["continuous_frame_openings"] == 1 and d["internal_mullions_are_separations"] is False
    assert all(c["is_frame_instance"] is False for c in STATE["candidates"])


def test_no_pand_no_instances_no_totals():
    assert STATE["bag_pand_id"] is None and STATE["address_scope"] == "NOT_PROVEN"
    assert all(c["bag_pand_id"] is None for c in STATE["candidates"])
    assert ANN["bag_pand_id"] is None and ANN["address_scope"] == "NOT_PROVEN"
    assert STATE["frame_instances_created"] == 0
    assert STATE["photo_observation_summary"]["is_building_total"] is False
    assert STATE["building_total"] is None and STATE["metric_quantities"] is None
    assert STATE["quantity_resolutions"] == 0
    rc = STATE["repeat_candidates"]
    assert rc["active"] is False and rc["multiplier"] is None and rc["user_confirmed_repeat"] is False


def test_original_annotation_untouched_and_photo2_unchanged():
    assert all(c["review_status"] == "REVIEW_REQUIRED" and c["human_decision"] == "PENDING"
               for c in ANN["candidates"])
    assert STATE["photo_2_unchanged"] == {"FRAME": 11, "WINDOW": 11, "EXTERIOR_DOOR": 1, "FULL": 9, "PARTIAL": 2}
    inv = json.loads((ROOT / "data/frame_inventory/frame_inventory_v1.json").read_text())
    assert inv["instances"] == []
