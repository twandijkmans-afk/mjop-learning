import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_rear_annotation_coverage as rac  # noqa: E402

FROZEN = {  # PR #35-state van foto 2: ongewijzigd door deze milestone
    "data/frame_inventory/maldenhof_photo_frame_instances_v1.json": "b18c36eb4c21abcb25bb9ff2162fcfd06a164b3f9e490aa11af858ef33b02378",
    "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json": "520e5e11f8a7b8600c8a03d4b93afb452fd8d0c9da14d5c729a8f5cae1a36e9d",
    "data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json": "3e4c8916957184a13cfb75308546011b8dacdc2542bf758b84ca9118f5e748a9",
    "data/photo_evidence/maldenhof_2_frame_annotation_v1.json": "55cab9e5797d1f4f3a37ff785a687be03792aba84892e130677c98a6b745eac6",
    "data/photo_evidence/maldenhof_photo_evidence_v1.json": "eeddff838df2b3c5d3bcadc28dfa5a2594a083bff9b90e18bd420840b5e7fae5",
    "data/photo_evidence/maldenhof_photo_human_review_v1.json": "4624854e067c5c28f3009a881139a813c94dfd9f5de6e71c2af03e3c16699443",
    "data/bag_snapshots/BAGSNAP-431559474da45dcf.json": "ed5f6cc9065afa1ddd4ed46016c0607f42ce14b5fbb34cd6d8a58a7556402446",
    "data/bag_snapshots/BAGSNAP-e23aa139a8589881.json": "5684777ad0ee0f6d6bc367e11c67eb7323bfe2f645178fc02f8dbe6bf3f037de",
    "data/building_links/building_link_records.json": "400d368ee91d9353a12846bf089a3d3f17efb926b9fcac7c4d9ba7f86230cd47",
}


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def addr():
    return load("data/photo_evidence/maldenhof_address_pand_evidence_v1.json")


@pytest.fixture(scope="module")
def ann3():
    return load("data/photo_evidence/maldenhof_3_frame_annotation_v1.json")


@pytest.fixture(scope="module")
def cov():
    return load("reports/frames/maldenhof_frame_coverage_v1.json")


@pytest.fixture(scope="module")
def inst():
    return load("data/frame_inventory/maldenhof_photo_frame_instances_v1.json")


# --- foto 2 bevroren -----------------------------------------------------------------------------------------------------------
def test_frozen_photo2_state_and_sources_unchanged():
    for path, digest in FROZEN.items():
        with open(os.path.join(ROOT, path), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == digest, path


def test_pr35_active_front_instances_and_counts_unchanged(inst):
    ids = [i["frame_instance_id"] for i in inst["instances"]]
    assert ids == [f"FI-M2-{n:03d}" for n in (1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14)]
    pc = inst["photo_visible_counts"]
    assert (pc["PHOTO_VISIBLE_FRAME_COUNT"], pc["PHOTO_VISIBLE_WINDOW_COUNT"], pc["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"]) == (11, 11, 1)
    assert (pc["ordinary_frames_FULL"], pc["ordinary_frames_PARTIAL"], pc["exterior_doors_PARTIAL"]) == (9, 2, 1)
    assert [x["instance"]["frame_instance_id"] for x in inst["superseded_instances"]] == ["FI-M2-008", "FI-M2-009"]
    assert next(i for i in inst["instances"] if i["frame_instance_id"] == "FI-M2-014")["source_refs"]
    assert all(i["bag_pand_id"] is None for i in inst["instances"])  # niets toegewezen zonder bewijs


# --- address -> pand --------------------------------------------------------------------------------------------------------------
def test_288_and_290_map_to_different_confirmed_panden_with_canonical_evidence(addr):
    r = addr["resolution"]
    assert r["Maldenhof 288"]["bag_pand_id"] == "0363100012121455" and r["Maldenhof 290"]["bag_pand_id"] == "0363100012134188"
    assert addr["same_pand"] is False and addr["network_calls"] is False
    assert r["Maldenhof 288"]["pand_addresses"] == [286, 288] and r["Maldenhof 290"]["pand_addresses"] == [290, 292]
    assert r["Maldenhof 288"]["building_link_ids"] == ["BLINK-00008", "BLINK-00048"] and r["Maldenhof 290"]["building_link_ids"] == ["BLINK-00010", "BLINK-00050"]
    scope = load("data/frame_inventory/frame_inventory_v1.json")["buildings"][0]["bag_pand_ids"]
    assert len(scope) == addr["confirmed_pand_count"] == 15 and all(a["pand_in_confirmed_scope"] and a["bag_pand_id"] in scope for a in addr["addresses"])
    assert len(addr["addresses"]) == 29


def test_mapping_is_rederived_from_snapshots_and_links_only(addr):
    """Het bewijs komt uitsluitend uit de bevroren snapshots + building links; herberekenen geeft precies hetzelfde."""
    assert rac.dumps(rac.address_pand_evidence()) == rac.dumps(addr)
    snap = load("data/bag_snapshots/BAGSNAP-431559474da45dcf.json")
    pdok = {a["huisnummer"]: a["pdok_id"] for a in snap["address_matches"]}
    for n, pand in ((288, "0363100012121455"), (290, "0363100012134188")):
        p = next(p for p in snap["panden"] if p["bag_pand_id"] == pand)
        assert pdok[n] in p["contains_address_point_of"]
    links = {(r["document_id"], r["bag_pand_id"]): r for r in load("data/building_links/building_link_records.json")["records"]}
    for doc in ("DOC-005", "DOC-006"):
        for pand in ("0363100012121455", "0363100012134188"):
            assert links[(doc, pand)]["link_status"] == "CONFIRMED" and links[(doc, pand)]["status"] == "ACTIVE"


def test_no_positional_guessing_for_photo2_instances(addr):
    rows = addr["photo2_instance_assignment"]
    assert len(rows) == 12 and all(r["assignment"] == "NOT_ASSIGNED" and r["bag_pand_id_in_instance_store"] is None for r in rows)
    hinted = {r["frame_instance_id"]: r for r in rows if r["address_hint"]}
    assert set(hinted) == {"FI-M2-012", "FI-M2-013"} and all("positional guessing" in r["reason"].lower() for r in hinted.values())
    assert all(r["hint_basis"] == "ADJACENT_TO_HOUSE_NUMBER_PLATE" for r in hinted.values())
    assert addr["photo3_scope"]["bag_pand_id"] is None and addr["photo3_scope"]["address_scope"] == "NOT_PROVEN"


# --- foto 3 ----------------------------------------------------------------------------------------------------------------------
def test_photo3_candidates_review_required_and_unpromoted(ann3, inst):
    assert ann3["photo"]["photo_id"] == "maldenhof_3" and ann3["photo"]["role"] == "REAR_DETAIL" and ann3["bag_pand_id"] is None
    assert [c["candidate_id"] for c in ann3["candidates"]] == [f"FC-M3-{n:03d}" for n in range(1, 11)]
    for c in ann3["candidates"]:
        assert c["review_status"] == "REVIEW_REQUIRED" and c["human_decision"] == "PENDING" and c["bag_pand_id"] is None and c["bag_address_scope_hint"] is None
        assert c["annotation_method"] == "MANUAL_VISUAL_READING" and c["facade_side"] == "REAR"
    rac.validate_ann3(ann3)
    assert ann3["frame_inventory_effect"].startswith("NONE") and ann3["visible_counts"]["confirmed_instances"] == 0
    assert not any(i["frame_instance_id"].startswith(("FI-M3", "FC-M3")) for i in inst["instances"])
    assert not any("maldenhof_3" in json.dumps(i["source_refs"]) for i in inst["instances"])
    assert load("data/frame_inventory/frame_inventory_v1.json")["instances"] == []


def test_photo3_visible_counts_by_category(ann3):
    vc = ann3["visible_counts"]
    assert vc["count_basis"] == "VISIBLE_COUNT_ON_PHOTO_3" and vc["is_building_total"] is False
    assert (vc["FULL_WINDOWS"], vc["PARTIAL_WINDOWS"], vc["EXTERIOR_DOORS"], vc["ROOF_WINDOWS"], vc["DORMER_WINDOWS"], vc["UNKNOWN_OPENINGS"]) == (1, 1, 1, 4, 1, 2)
    assert vc["TOTAL_ANNOTATION_CANDIDATES"] == 10 and (vc["ROOF_WINDOWS_FULL"], vc["ROOF_WINDOWS_PARTIAL"]) == (3, 1)
    assert rac.summarize3(ann3["candidates"]) == vc
    dormer = [c for c in ann3["candidates"] if c["candidate_type"] == "DORMER_WINDOW"]
    assert len(dormer) == 1 and dormer[0]["parent"]["type"] == "ROOF_DORMER" and ann3["context_objects"][0]["counts_as_window_candidate"] is False
    assert all(c["storey"] == "ROOF" for c in ann3["candidates"] if c["candidate_type"] in {"ROOF_WINDOW", "DORMER_WINDOW"})
    assert all(c["occlusion_reason"] for c in ann3["candidates"] if c["visibility"] != "FULL")


def test_relation_review_is_not_merged_and_no_cross_photo_dedup(ann3):
    g = ann3["relation_reviews"]
    assert len(g) == 1 and g[0]["candidate_ids"] == ["FC-M3-004", "FC-M3-005"] and g[0]["status"] == "SAME_FRAME_OPENING_REVIEW_REQUIRED"
    assert len(ann3["candidates"]) == 10  # niet samengevoegd
    assert ann3["cross_photo_deduplication"]["status"] == "NONE"
    assert not any(c.get("duplicate_group") or c.get("duplicate_of") for c in ann3["candidates"])
    ids3 = {c["candidate_id"] for c in ann3["candidates"]}
    ann2 = load("data/photo_evidence/maldenhof_2_frame_annotation_v1.json")
    assert not ids3 & {c["candidate_id"] for c in ann2["candidates"]}
    assert "FC-M2" not in json.dumps(ann3["candidates"])  # geen verwijzing naar voorgevelkandidaten


def test_no_metrics_painting_area_building_total_or_repeat_activation(ann3, cov, addr):
    text = json.dumps(ann3).lower() + json.dumps(cov).lower()
    for key in ("width_m", "height_m", "area_m2", "painting_area_m2", "glass_area_m2"):
        assert key not in text
    assert ann3["metric_scale"] == "NONE_PROVEN"
    assert cov["counts"]["combined_building_total"] == "NOT_COMPUTED" and cov["historical_context"]["ratio_or_m2_per_frame"] == "NOT_COMPUTED"
    assert cov["historical_context"]["756.80_m2"] == "NOT_COMPARABLE"
    rc = ann3["repeat_candidates"]
    assert rc["status"] == "REPEAT_CANDIDATE" and rc["active"] is False and rc["multiplier"] is None and rc["user_confirmed_repeat"] is False
    assert cov["repeat_candidates"]["active"] is False and cov["repeat_candidates"]["multiplier"] is None
    assert "ACTIVE" not in json.dumps(rc)
    assert load("data/frame_inventory/component_repeat_groups_v1.json")["groups"] == []
    assert load("data/quantity_resolutions/quantity_resolution_records.json")["records"] == []


# --- coverage --------------------------------------------------------------------------------------------------------------------
def test_coverage_matrix_semantics(cov, addr):
    assert cov["pand_count"] == len(cov["panden"]) == 15 and "NIET dat het aantal kozijnen compleet" in cov["definition"]
    allowed = set(rac.FACE_STATES)
    for r in cov["panden"]:
        assert set(r["faces"]) == {"FRONT", "REAR", "LEFT_SIDE", "RIGHT_SIDE"}
        assert all(f["coverage"] in allowed for f in r["faces"].values())
        assert r["confirmed_frame_instances_assigned"] == 0 and r["pending_candidates_assigned"] == 0
        assert r["faces"]["REAR"]["coverage"] == "UNKNOWN"  # foto 3 is aan geen pand gekoppeld
    covered = {r["bag_pand_id"] for r in cov["panden"] if r["faces"]["FRONT"]["coverage"] != "UNKNOWN"}
    assert covered == {addr["resolution"]["Maldenhof 288"]["bag_pand_id"], addr["resolution"]["Maldenhof 290"]["bag_pand_id"]}
    assert all(r["faces"]["FRONT"]["coverage"] == "PARTIAL_COVERAGE" and r["faces"]["FRONT"]["source_photo_ids"] == ["maldenhof_2"] for r in cov["panden"] if r["bag_pand_id"] in covered)
    assert not any("maldenhof_1" in f["source_photo_ids"] for r in cov["panden"] for f in r["faces"].values())  # foto 1 is CONTEXT_ONLY
    assert cov["photo1_context"]["role"] == "CONTEXT_ONLY"
    assert cov["counts"]["front_photo2"]["PHOTO_VISIBLE_FRAME_COUNT"] == 11 and cov["counts"]["rear_photo3"]["confirmed_instances"] == 0


def test_capture_plan_is_exact_and_complete(cov):
    mp = cov["missing_photos_needed"]
    assert mp["label"] == "MISSING_PHOTOS_NEEDED" and mp["minimum_extra_photos"] == len(mp["photos"]) == mp["front_photos"] + mp["rear_photos"] + mp["gable_photos"]
    assert (mp["front_photos"], mp["rear_photos"], mp["gable_photos"]) == (5, 5, 2)
    for p in mp["photos"]:
        assert all(p[k] for k in ("photo_id", "facade", "addresses", "orientation", "framing", "stand", "why_needed", "closes_gap"))
    for side in ("FRONT", "REAR"):  # elk pand precies in een groep per zijde
        pids = [x for p in mp["photos"] if p["facade"] == side for x in p["bag_pand_ids"]]
        assert sorted(pids) == sorted(r["bag_pand_id"] for r in cov["panden"])


def test_outputs_deterministic_and_current():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_rear_annotation_coverage.py"), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert rac.dumps(rac.build_all()[2]) == rac.dumps(rac.build_all()[2])
    assert os.path.getsize(rac.OVERLAY) > 10000
    sheet = rac.SHEET.read_text(encoding="utf-8")
    assert sheet.count("| PENDING |") == 10
    rep = rac.REPORT.read_text(encoding="utf-8")
    assert "VISIBLE_COUNT_ON_PHOTO_3" in rep and "756,80 m2 blijft NOT_COMPARABLE" in rep


def test_existing_bundles_kg_crosswalk_unchanged():
    import test_photo_frame_review as t
    for path, digest in t.UNCHANGED.items():
        if path.endswith("frame_inventory_v1.json"):
            continue
        with open(os.path.join(ROOT, path), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == digest, path
