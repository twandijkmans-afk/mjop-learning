import copy
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_photo_frame_review as pfr  # noqa: E402

REVIEWED = {"PHO-M-001", "PHO-M-002", "PHO-M-003", "PHO-M-004", "PHO-M-008", "PHO-M-009", "PHO-M-010", "PHO-M-013", "PHO-M-014", "PHO-M-015", "PHO-M-016"}
UNCHANGED = {  # bestaande evidence, frame store, crosswalk, presence-besluiten en app bundles: ongewijzigd door deze milestone
    "data/photo_evidence/maldenhof_photo_evidence_v1.json": "eeddff838df2b3c5d3bcadc28dfa5a2594a083bff9b90e18bd420840b5e7fae5",
    "data/frame_inventory/component_repeat_groups_v1.json": "4fa2f5bb37d049c4c4614d28097a396d8a4aff324a82b76cf5f66610601b7b49",
    "data/frame_inventory/frame_inventory_v1.json": "2109144babd2024891d9b6cd0047ad9ec73962ea8f21aa3578ca0ed955ebca1b",
    "data/crosswalk_decisions/crosswalk_decision_records.json": "bbd2872cf038c6e5e60a0d2a0d44f994831b5c2694c6319d36d1532e05084114",
    "data/component_presence/component_presence_decision_records.json": "984a6436bababc42c2ea2777476f6b7e08d699774ec5490c96c724c0efe75757",
    "reports/quantity/app_bundles/doc012_geometry_v3.json": "fe12a4eb7999f784056d46a607e5e37b6223fc30a6eff0c4c86924390f074a87",
    "reports/quantity/app_bundles/doc012_meppelweg_v3.json": "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191",
    "reports/quantity/app_bundles/maldenhof_DOC-005_DOC-006_v3.json": "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933",
    "reports/quantity/app_bundles/maldenhof_expanded_v3.json": "c78f387e66ce7963d7a434270350f0ee8fa4c9f232099f871e83ed202cd2975d",
    "reports/quantity/app_bundles/maldenhof_geometry_expanded_v3.json": "8264bdceb2c0ee633333b79ac6a073f8c9ea48661659007f69ff22df391a52ca",
}


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def ann():
    return load("data/photo_evidence/maldenhof_2_frame_annotation_v1.json")


@pytest.fixture(scope="module")
def store():
    return load("data/photo_evidence/maldenhof_photo_human_review_v1.json")


# --- review store --------------------------------------------------------------------------------------------------------
def test_only_named_observations_reviewed(store):
    ids = [r["observation_id"] for r in store["records"]]
    assert set(ids) == REVIEWED and len(ids) == len(set(ids)) == 11
    by = {r["observation_id"]: r for r in store["records"]}
    assert by["PHO-M-001"]["decision"] == "ACCEPT"
    assert all(r["decision"] == "ACCEPT_OBSERVATION" for k, r in by.items() if k != "PHO-M-001")
    assert all(r["reviewer_type"] == "human" and r["reviewer_id"] == "user-approved" and r["reviewed_at"] and r["supersedes"] is None for r in store["records"])
    assert [r["decision_id"] for r in store["records"]] == [f"PHR-{i:05d}" for i in range(1, 12)]


def test_review_store_is_append_only_and_idempotent(store):
    again = pfr.apply_decisions(copy.deepcopy(store))
    assert again == store
    tampered = copy.deepcopy(store)
    tampered["records"][0]["reason"] = "anders"
    assert pfr.append_only_errors(store, tampered) == ["PHR-00001"]
    shorter = copy.deepcopy(store)
    del shorter["records"][-1]
    assert pfr.append_only_errors(store, shorter) == ["PHR-00011"]


def test_existing_evidence_untouched_and_unreviewed_stay_open():
    ev = load("data/photo_evidence/maldenhof_photo_evidence_v1.json")
    assert len(ev["observations"]) == 20
    assert all(o["confirmed"] is False and o["status"] in {"REVIEW_REQUIRED", "REPEAT_CANDIDATE"} for o in ev["observations"])
    rest = [o for o in ev["observations"] if o["observation_id"] not in REVIEWED]
    assert len(rest) == 9 and all(o["status"] in {"REVIEW_REQUIRED", "REPEAT_CANDIDATE"} for o in rest)


def test_repeat_candidates_remain_non_active(ann):
    rm = ann["repeat_modules"]
    assert rm["status"] == "REPEAT_CANDIDATE" and rm["active"] is False and rm["multiplier"] is None and rm["user_confirmed_repeat"] is False
    groups = load("data/frame_inventory/component_repeat_groups_v1.json")
    assert groups["groups"] == []
    assert "ACTIVE" not in json.dumps(ann["repeat_modules"])


# --- annotatie -------------------------------------------------------------------------------------------------------------
def test_candidate_ids_unique_and_bboxes_in_range(ann):
    ids = [c["candidate_id"] for c in ann["candidates"]]
    assert len(ids) == len(set(ids)) == 19
    for c in ann["candidates"]:
        x1, y1, x2, y2 = c["bbox_norm"]
        assert 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1
    pfr.validate_annotation(ann)
    assert pfr.dumps(pfr.build_annotation()) == pfr.dumps(ann)


def test_all_candidates_review_required_and_manual(ann):
    assert all(c["review_status"] == "REVIEW_REQUIRED" and c["human_decision"] == "PENDING" and c["annotation_method"] == "MANUAL_VISUAL_READING" for c in ann["candidates"])
    assert ann["annotation_method"] == "MANUAL_VISUAL_READING" and "geen automatische detectie" in ann["annotation_note"].lower()
    assert all(c["occlusion_reason"] for c in ann["candidates"] if c["visibility"] != "FULL")


def test_roof_windows_and_dormer_windows_separated(ann):
    roof = [c for c in ann["candidates"] if c["candidate_type"] == "ROOF_WINDOW"]
    dormer = [c for c in ann["candidates"] if c["parent"]]
    assert len(roof) == 5 and all(c["parent"] is None and c["storey"] == "ROOF" for c in roof)
    assert len(dormer) == 1 and dormer[0]["candidate_type"] == "WINDOW" and dormer[0]["parent"]["type"] == "ROOF_DORMER"
    vc = ann["visible_counts"]
    assert vc["ROOF_WINDOWS"] == 5 and vc["DORMER_WINDOWS"] == 1
    assert vc["VISIBLE_WINDOW_CANDIDATE_COUNT"] == vc["FULL_VISIBLE_WINDOWS"] + vc["PARTIAL_WINDOWS"] == 9


def test_visible_count_is_not_building_total(ann):
    vc = ann["visible_counts"]
    assert vc["count_basis"] == "VISIBLE_COUNT_ON_PHOTO" and vc["is_building_total"] is False and vc["photo"] == "maldenhof_2.jpg"
    assert "BUILDING_TOTAL" not in vc and "building_total" not in json.dumps(ann).replace('"is_building_total"', "")
    assert (vc["FULL_VISIBLE_WINDOWS"], vc["PARTIAL_WINDOWS"], vc["EXTERIOR_DOORS"], vc["UNKNOWN_OPENINGS"]) == (7, 2, 1, 3)


def test_duplicates_flagged_not_merged(ann):
    flagged = {c["candidate_id"] for c in ann["candidates"] if c["duplicate_review"] == "DUPLICATE_REVIEW_REQUIRED"}
    assert flagged == {"FC-M2-002", "FC-M2-003", "FC-M2-004", "FC-M2-005"}
    assert len(ann["candidates"]) == 19  # niet samengevoegd
    assert ann["visible_counts"]["FULL_WINDOWS_IF_DUPLICATE_GROUPS_COUNT_ONCE"] == 5


def test_no_dimensions_areas_or_painting_area(ann):
    text = json.dumps(ann).lower()
    for key in ("width_m", "height_m", "area_m2", "painting_area_m2", "scale_m_per"):
        assert key not in text
    assert ann["metric_scale"] == "NONE_PROVEN"
    assert not any(k.endswith("_m") or k.endswith("_m2") for c in ann["candidates"] for k in c)
    report = open(os.path.join(ROOT, "reports/frames/photo_review_v1/maldenhof_photo_frame_review_v1.md"), encoding="utf-8").read()
    assert "painting area" in report.lower()  # alleen als expliciete uitsluiting


def test_no_frame_instances_or_quantity_resolution(ann):
    inv = load("data/frame_inventory/frame_inventory_v1.json")
    assert inv["instances"] == [] and inv["frame_groups"] == []
    assert ann["frame_inventory_effect"].startswith("NONE")
    assert load("data/quantity_resolutions/quantity_resolution_records.json")["records"] == []
    ev = load("data/photo_evidence/maldenhof_photo_evidence_v1.json")
    assert set(ev["quantity_concepts_status"].values()) == {"UNKNOWN"}
    assert not [c for c in ann["candidates"] if c["review_status"] != "REVIEW_REQUIRED"]


def test_photo_roles_and_hash(ann):
    assert ann["photo_roles"] == {"maldenhof_1": "CONTEXT_ONLY", "maldenhof_2": "FIRST_FRAME_ANNOTATION_SOURCE", "maldenhof_3": "REAR_DETAIL"}
    with open(pfr.PHOTO_2, "rb") as f:
        assert hashlib.sha256(f.read()).hexdigest() == ann["photo"]["sha256"]


# --- ongewijzigde bestaande artefacten ---------------------------------------------------------------------------------------
def test_existing_stores_and_bundles_unchanged():
    for path, digest in UNCHANGED.items():
        with open(os.path.join(ROOT, path), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == digest, path


def test_cpd_decisions_unchanged():
    recs = load("data/component_presence/component_presence_decision_records.json")["records"]
    cpd = {r["decision_id"]: r for r in recs}
    for d in ("CPD-00001", "CPD-00002"):
        assert cpd[d]["component_type"] == "EXTERIOR_FRAME" and cpd[d]["decision"] == "PRESENT" and cpd[d]["status"] == "ACTIVE"


def test_756_80_stays_not_comparable():
    import test_frame_inventory_foundation as t  # noqa: F401
    text = open(os.path.join(ROOT, "reports/frames/photo_review_v1/maldenhof_photo_frame_review_v1.md"), encoding="utf-8").read()
    assert "756,80 blijft NOT_COMPARABLE" in text
    assert "756.80" not in json.dumps(load("data/photo_evidence/maldenhof_2_frame_annotation_v1.json"))


def test_committed_outputs_current_and_overlay_exists():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_photo_frame_review.py"), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.getsize(pfr.OVERLAY) > 10000 and pfr.SHEET.exists()
    sheet = pfr.SHEET.read_text(encoding="utf-8")
    assert sheet.count("| PENDING |") == 19
