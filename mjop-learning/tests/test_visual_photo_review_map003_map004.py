import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "reports/frames/photo_review_map003_map004_v1"
J = json.loads((DIR / "maldenhof_visual_photo_review_map003_map004_v1.json").read_text())
MD = (DIR / "maldenhof_visual_photo_review_map003_map004_v1.md").read_text()
AUD = json.loads((ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_archive_audit_v1.json").read_text())
APPROVAL = (ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md").read_text()
ADDR = json.loads((ROOT / "data/photo_evidence/maldenhof_address_pand_evidence_v1.json").read_text())
INST = json.loads((ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json").read_text())
REG = {p["photo_id"]: p for p in AUD["photos"]}
OBS = J["observations"]
TYPES = {"WINDOW_OPENING", "EXTERIOR_DOOR", "WINDOW_DOOR_COMBINATION", "ROOF_WINDOW", "DORMER_OPENING", "UNKNOWN_OPENING"}
VIS = {"FULL", "PARTIAL", "HEAVILY_OCCLUDED", "UNKNOWN_OPENING"}


def test_sources_verified_against_register():
    assert {s["photo_id"] for s in J["sources"]} == {"MAP-002", "MAP-003", "MAP-004", "MAP-009", "MAP-013", "MAP-033"}
    for s in J["sources"]:
        r = REG[s["photo_id"]]
        assert s["sha256_verified"] is True and s["sha256_register"] == r["sha256"]
        assert [s["width_px"], s["height_px"]] == [r["width_px"], r["height_px"]]


def test_observation_ids_unique_traceable_and_not_instances():
    assert len({o["obs_id"] for o in OBS}) == len(OBS)
    assert sum(o["photo_id"] == "MAP-003" for o in OBS) == 28 and sum(o["photo_id"] == "MAP-004" for o in OBS) == 22
    for o in OBS:
        assert re.fullmatch(r"OBS-MAP00[34]-\d{3}", o["obs_id"])
        assert o["photo_id"] in ("MAP-003", "MAP-004") and o["obs_id"].startswith("OBS-" + o["photo_id"].replace("-", ""))
        r = REG[o["photo_id"]]
        assert o["source_file"] == r["original_file"] and o["source_sha256"] == r["sha256"]
        x0, y0, x1, y1 = o["bbox_px"]
        assert 0 <= x0 < x1 <= r["width_px"] and 0 <= y0 < y1 <= r["height_px"]
        assert o["bbox_norm"] == [round(x0 / r["width_px"], 4), round(y0 / r["height_px"], 4), round(x1 / r["width_px"], 4), round(y1 / r["height_px"], 4)]
        assert o["observation_type"] in TYPES and o["visibility"] in VIS and o["uncertainty"] in ("LOW", "MEDIUM", "HIGH")
        assert o["is_instance"] is False and o["bag_pand_id"] is None and o["pand_status"] == "NOT_PROVEN" and o["counts_in_any_total"] is False


def test_temporary_ids_not_in_any_instance_or_data_store():
    for f in (ROOT / "data").rglob("*.json"):
        assert "OBS-MAP003-" not in f.read_text() and "OBS-MAP004-" not in f.read_text(), f


def test_photo2_frozen_counts_unchanged():
    c = INST["photo_visible_counts"]
    assert (c["PHOTO_VISIBLE_FRAME_COUNT"], c["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"], c["ordinary_frames_FULL"], c["ordinary_frames_PARTIAL"]) == (11, 1, 9, 2)
    assert all(v["value"] is None for v in INST["building_totals"].values())
    assert J["effects"]["photo2_unchanged"] is True and J["effects"]["instances_created"] == 0 and J["effects"]["bag_links_created"] == 0
    assert J["effects"]["building_totals"] is None and J["effects"]["costs"] is None and J["effects"]["repeat_multipliers"] is None


def test_plates_match_bag_evidence_and_scope_rule():
    assert len(J["plates"]) == 11
    by_nr = {a["huisnummer"]: a["bag_pand_id"] for a in ADDR["addresses"]}
    for p in J["plates"]:
        assert p["bag_pand_id_for_plate_wall"] == by_nr[p["reading"]]
        assert p["reading"] in REG[p["photo_id"]]["visible_house_number_plates"]
        assert p["reading_status"] == "PROVISIONAL_UNCONFIRMED_BY_HUMAN" and "PLAATMUUR" in p["scope"]
    assert {p["reading"] for p in J["plates"] if p["photo_id"] == "MAP-003"} == {288, 286, 284, 282, 280, 278, 276}
    assert {p["reading"] for p in J["plates"] if p["photo_id"] == "MAP-004"} == {280, 278, 276, 274}


def test_relations_are_candidates_only_and_refer_to_known_ids():
    ids = {o["obs_id"] for o in OBS}
    refs = {r["ref_id"] for r in J["references"]}
    groups = {g["group_id"] for g in AUD["same_object_candidates"]}
    assert all(r["is_observation"] is False for r in J["references"])
    assert len({r["rel_id"] for r in J["relations"]}) == len(J["relations"])
    for r in J["relations"]:
        assert r["soc"] in groups and r["merged"] is False and r["confirmed"] is False
        assert r["class"] in {"SAME_FACADE_SECTION", "POSSIBLY_SAME_PHYSICAL_FRAME", "DIFFERENT_FRAMES", "UNDETERMINABLE"}
        for side in (r["left"], r["right"]):
            for m in re.findall(r"OBS-MAP00[34]-\d{3}", side):
                assert m in ids
            for m in re.findall(r"REF-MAP\d{3}-\d{3}", side):
                assert m in refs
    assert {"SOC-001", "SOC-002", "SOC-003", "SOC-008"} <= {r["soc"] for r in J["relations"]}


def test_questions_link_to_existing_open_app_decisions_and_all_48_stay_open():
    rows = [l for l in APPROVAL.splitlines() if re.match(r"\| APP-\d{3} \|", l)]
    assert len(rows) == 48 and all(r.rstrip().endswith("| OPEN |") for r in rows)
    linked = {q["app_decision"] for q in J["questions"] if q["app_decision"]}
    assert {"APP-001", "APP-002", "APP-003", "APP-011", "APP-012", "APP-031", "APP-034", "APP-035"} <= linked
    for q in J["questions"]:
        assert q["status"] == "OPEN"
        if q["app_decision"]:
            assert f"| {q['app_decision']} |" in APPROVAL
        else:
            assert q["id"].startswith("HQ-VR-")


def test_images_exist_and_document_complete():
    for name in J["images"].values():
        f = DIR / name
        assert f.exists() and f.stat().st_size > 10_000, name
        assert name in MD
    for n in range(1, 11):
        assert re.search(rf"^## {n}\. ", MD, re.M), n
    for o in OBS:
        assert o["obs_id"] in MD
    assert "Alle 48 APP-besluiten" in MD and "48 OPEN" in MD


def test_no_metric_or_cost_claims_in_package():
    blob = json.dumps(J, ensure_ascii=False)
    assert not re.search(r'"(area|m2|cost|price|multiplier)"\s*:\s*[0-9]', blob)
    assert not re.search(r"\b\d+(?:,\d+)?\s?(m2|m²|euro|€)\b", MD)
