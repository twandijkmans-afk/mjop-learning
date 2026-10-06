import copy
import hashlib
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import build_frame_instance_activation as fia  # noqa: E402
import frame_inventory as fi  # noqa: E402

def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def store():
    return load("data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json")


@pytest.fixture(scope="module")
def corrected():
    return load("data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json")


@pytest.fixture(scope="module")
def inst():
    return load("data/frame_inventory/maldenhof_photo_frame_instances_v1.json")


@pytest.fixture(scope="module")
def ann():
    return load("data/photo_evidence/maldenhof_2_frame_annotation_v1.json")


def by_target(store):
    return {(r["target_type"], r["target_id"]): r for r in store["records"]}


# --- human decisions --------------------------------------------------------------------------------------------------------
def test_decisions_append_only_and_idempotent(store):
    assert fia.apply_decisions(copy.deepcopy(store)) == store
    assert [r["decision_id"] for r in store["records"]] == [f"PCD-{i:05d}" for i in range(1, len(store["records"]) + 1)]
    assert all(r["reviewer_type"] == "human" and r["reviewer_id"] == "user-approved" and r["status"] == "ACTIVE" for r in store["records"])
    assert all(r["supersedes"] is None for r in store["records"] if r["decision_id"] != "PCD-00024")
    t = copy.deepcopy(store)
    t["records"][0]["reason"] = "anders"
    assert fia.append_only_errors(store, t) == ["PCD-00001"]
    s = copy.deepcopy(store)
    del s["records"][-1]
    assert fia.append_only_errors(store, s) == [store["records"][-1]["decision_id"]]


def test_user_decisions_recorded(store):
    d = by_target(store)
    expect = {"FC-M2-001": "SPLIT_REQUIRED", "FC-M2-002": "ACCEPT_DISTINCT_FRAME", "FC-M2-003": "ACCEPT_DISTINCT_FRAME", "FC-M2-004": "ACCEPT_DISTINCT_FRAME",
              "FC-M2-005": "ACCEPT_DISTINCT_FRAME", "FC-M2-006": "SPLIT_REQUIRED", "FC-M2-007": "ACCEPT_FRAME", "FC-M2-008": "ACCEPT_FRAME", "FC-M2-009": "ACCEPT_FRAME",
              "FC-M2-010": "REJECT", "FC-M2-011": "ACCEPT_EXTERIOR_DOOR", "FC-M2-012": "KEEP_UNKNOWN", "FC-M2-013": "REJECT"}
    expect.update({f"FC-M2-{n:03d}": "ACCEPT_PHOTO_OBSERVATION" for n in range(14, 20)})
    for cid, dec in expect.items():
        assert d[("CANDIDATE", cid)]["decision"] == dec, cid
    assert d[("CANDIDATE", "FC-M2-008")]["visibility"] == "PARTIAL" and d[("CANDIDATE", "FC-M2-009")]["address_hint"] == "Maldenhof 288"
    assert d[("CANDIDATE", "FC-M2-011")]["material"] == "UNKNOWN" and d[("CANDIDATE", "FC-M2-011")]["visibility"] == "PARTIAL"
    assert len(store["records"]) == 24  # 23 uit PR #34 + PCD-00024 (correction)


def test_duplicates_resolved_not_duplicates_history_kept(store, corrected, ann):
    d = by_target(store)
    assert d[("DUPLICATE_GROUP", "DUP-M2-001")]["decision"] == "NOT_DUPLICATES" and d[("DUPLICATE_GROUP", "DUP-M2-002")]["decision"] == "NOT_DUPLICATES"
    g = {x["group_id"]: x for x in corrected["duplicate_groups"]}
    assert g["DUP-M2-001"]["candidate_ids"] == ["FC-M2-002", "FC-M2-003"] and g["DUP-M2-002"]["candidate_ids"] == ["FC-M2-004", "FC-M2-005"]
    assert all(x["original_status"] == "DUPLICATE_REVIEW_REQUIRED" and x["human_resolution"] == "NOT_DUPLICATES" for x in g.values())
    assert [x["status"] for x in ann["duplicate_groups"]] == ["DUPLICATE_REVIEW_REQUIRED"] * 2  # oorspronkelijke evidence ongewijzigd


# --- splits ------------------------------------------------------------------------------------------------------------------
def test_splits_exact_children_inside_parent_and_disjoint(corrected, ann):
    assert fia.geometry_errors(ann, corrected) == []
    k1 = [k for k in corrected["child_candidates"] if k["parent_candidate_id"] == "FC-M2-001"]
    k6 = [k for k in corrected["child_candidates"] if k["parent_candidate_id"] == "FC-M2-006" and "merged_from" not in k]
    assert len(k1) == 2 and len(k6) == 3 and len(corrected["child_candidates"]) == 6  # historische B/C blijven bewaard naast de merged child
    assert all(k["bbox_method"] == "MANUAL_VISUAL_READING_CORRECTION" and "handmatige" in k["bbox_method_note"] for k in k1 + k6)
    pm = {c["candidate_id"]: c for c in ann["candidates"]}
    for k in corrected["child_candidates"]:
        assert k["original_parent_bbox_norm"] == pm[k["parent_candidate_id"]]["bbox_norm"]
        assert k["split_decision_id"] in {"PCD-00001", "PCD-00008"}


def test_split_geometry_check_detects_errors(corrected, ann):
    bad = copy.deepcopy(corrected)
    bad["child_candidates"] = [k for k in bad["child_candidates"] if k["candidate_id"] != "FC-M2-006-A"]
    assert fia.geometry_errors(ann, bad)
    bad2 = copy.deepcopy(corrected)
    k = next(k for k in bad2["child_candidates"] if k["candidate_id"] == "FC-M2-006-BC")
    k["bbox_norm"] = list(k["bbox_norm"])
    k["bbox_norm"][2] = 0.90  # omvat C niet meer
    assert fia.geometry_errors(ann, bad2)


def test_parent_evidence_never_overwritten(ann):
    assert hashlib.sha256(open(fia.ANNOTATION, "rb").read()).hexdigest() == hashlib.sha256(json.dumps(ann, indent=2, ensure_ascii=False).encode("utf-8") + b"\n").hexdigest()
    assert len(ann["candidates"]) == 19
    assert all(c["review_status"] == "REVIEW_REQUIRED" and c["human_decision"] == "PENDING" for c in ann["candidates"])


# --- instances ---------------------------------------------------------------------------------------------------------------
def test_ordinary_candidate_count_verified_from_bboxes_not_hardcoded(ann, corrected):
    assert len(fia.ordinary_window_candidates(ann, corrected, baseline=True)) == fia.EXPECTED_BASELINE_ORDINARY_WINDOW_CANDIDATES == 12
    cands = fia.ordinary_window_candidates(ann, corrected)
    assert len(cands) == fia.EXPECTED_ORDINARY_WINDOW_CANDIDATES == 11
    assert {c["candidate_id"] for c in cands} & {"FC-M2-006-B", "FC-M2-006-C"} == set() and "FC-M2-006-BC" in {c["candidate_id"] for c in cands}
    shrunk = copy.deepcopy(corrected)
    shrunk["child_candidates"] = [k for k in shrunk["child_candidates"] if k["candidate_id"] != "FC-M2-001-B"]
    assert len(fia.ordinary_window_candidates(ann, shrunk)) == 10  # stopregel zou afgaan


def test_stop_rule_raises_before_activation(ann, corrected, store):
    shrunk = copy.deepcopy(corrected)
    shrunk["child_candidates"] = [k for k in shrunk["child_candidates"] if k["candidate_id"] != "FC-M2-001-B"]
    with pytest.raises(fia.CountMismatch):
        fia.build_instances(ann, shrunk, store, load("data/frame_inventory/frame_inventory_v1.json"))


# --- counting semantics correction (PCD-00024) ---------------------------------------------------------------------------------
def test_correction_is_append_only_and_preserves_pcd_00008(store):
    recs = {r["decision_id"]: r for r in store["records"]}
    assert recs["PCD-00008"]["decision"] == "SPLIT_REQUIRED" and recs["PCD-00008"]["target_id"] == "FC-M2-006" and recs["PCD-00008"]["child_count"] == 3
    assert recs["PCD-00008"]["status"] == "ACTIVE" and recs["PCD-00008"]["supersedes"] is None and "drie afzonderlijke" in recs["PCD-00008"]["reason"]
    c = recs["PCD-00024"]
    assert c["decision"] == "MERGE_AS_SINGLE_FRAME_OPENING" and c["supersedes"] == "PCD-00008" and c["merge_children"] == ["FC-M2-006-B", "FC-M2-006-C"]
    assert c["unchanged_child"] == "FC-M2-006-A" and c["merged_child_id"] == "FC-M2-006-BC" and c["reviewer_type"] == "human"
    assert "kozijnstijl" in c["reason"] and store["records"][-1]["decision_id"] == "PCD-00024"
    # PCD-00001..23 zijn ongewijzigd t.o.v. PR #34 (alleen toevoeging): opnieuw toepassen verandert niets en een gewijzigd oud record wordt gedetecteerd
    assert fia.apply_decisions(copy.deepcopy(store)) == store
    t = copy.deepcopy(store)
    t["records"][7]["child_count"] = 2
    assert fia.append_only_errors(store, t) == ["PCD-00008"]


def test_merged_child_lineage_and_superseded_children_kept(corrected):
    kids = {k["candidate_id"]: k for k in corrected["child_candidates"]}
    bc = kids["FC-M2-006-BC"]
    assert bc["lifecycle"] == "ACTIVE" and bc["merged_from"] == ["FC-M2-006-B", "FC-M2-006-C"] and bc["correction_decision_id"] == "PCD-00024"
    assert bc["parent_candidate_id"] == "FC-M2-006" and bc["split_decision_id"] == "PCD-00008"
    assert bc["refs"] == ["FC-M2-006", "FC-M2-006-B", "FC-M2-006-C", "PCD-00008", "PCD-00024"]
    b, c = kids["FC-M2-006-B"], kids["FC-M2-006-C"]
    assert b["lifecycle"] == c["lifecycle"] == "SUPERSEDED" and b["superseded_by"] == c["superseded_by"] == "FC-M2-006-BC"
    assert bc["bbox_norm"][0] == b["bbox_norm"][0] and bc["bbox_norm"][2] == c["bbox_norm"][2]
    a = kids["FC-M2-006-A"]
    assert a["lifecycle"] == "ACTIVE" and a["bbox_norm"][2] <= bc["bbox_norm"][0]  # A ongewijzigd en apart
    assert b["visibility"] == "FULL" and c["visibility"] == "FULL" and b["bbox_norm"] == [0.8915, 0.3587, 0.946, 0.4147]
    assert {k["lifecycle"] for k in corrected["child_candidates"] if k["parent_candidate_id"] == "FC-M2-001"} == {"ACTIVE"}


def test_b_plus_c_produce_exactly_one_active_instance_and_a_stays_separate(inst):
    ann = inst["instance_annotations"]
    of_006 = [i for i, a in ann.items() if a["origin_candidate_id"] == "FC-M2-006"]
    assert len(of_006) == 2
    assert {ann[i]["candidate_id"] for i in of_006} == {"FC-M2-006-A", "FC-M2-006-BC"}
    merged = next(i for i in inst["instances"] if i["frame_instance_id"] == next(x for x in of_006 if ann[x]["candidate_id"] == "FC-M2-006-BC"))
    assert merged["frame_instance_id"] == "FI-M2-014" and merged["status"] == "CONFIRMED" and merged["count"] == 1 and merged["human_decision_ref"] == "PCD-00024"
    refs = merged["source_refs"]
    assert {r["candidate_id"] for r in refs if r["ref_type"] == "SUPERSEDED_CHILD_CANDIDATE"} == {"FC-M2-006-B", "FC-M2-006-C"}
    assert {r["frame_instance_id"] for r in refs if r["ref_type"] == "SUPERSEDED_INSTANCE"} == {"FI-M2-008", "FI-M2-009"}
    assert {r["decision_id"] for r in refs if r["ref_type"] in ("HUMAN_DECISION", "HUMAN_CORRECTION_DECISION")} == {"PCD-00008", "PCD-00024"}
    assert ann["FI-M2-014"]["quantity_contributions"] == {"FRAME_COUNT": 1, "WINDOW_COUNT": 1}
    a_inst = next(i for i in inst["instances"] if i["frame_instance_id"] == "FI-M2-007")
    assert ann["FI-M2-007"]["candidate_id"] == "FC-M2-006-A" and a_inst["human_decision_ref"] == "PCD-00008"


def test_superseded_instances_kept_not_active(inst):
    active = {i["frame_instance_id"] for i in inst["instances"]}
    sup = {x["instance"]["frame_instance_id"]: x for x in inst["superseded_instances"]}
    assert set(sup) == {"FI-M2-008", "FI-M2-009"} and not (set(sup) & active)
    for iid, x in sup.items():
        assert x["lifecycle"] == "SUPERSEDED" and x["superseded_by_instance"] == "FI-M2-014" and x["supersession_decision_id"] == "PCD-00024"
        assert x["instance"]["status"] == "CONFIRMED" and x["instance"]["human_decision_ref"] == "PCD-00008"  # historische record ongewijzigd
        assert x["annotation"]["candidate_id"] in {"FC-M2-006-B", "FC-M2-006-C"}
    assert inst["photo_visible_counts"]["superseded_instance_ids"] == ["FI-M2-008", "FI-M2-009"]
    assert fia.instance_store_errors(inst) == []


def test_confirmed_instances_for_accepted_frames(inst, corrected):
    frames = [i for i in inst["instances"] if i["component_type"] == "EXTERIOR_FRAME"]
    assert len(frames) == 11
    assert [i["frame_instance_id"] for i in inst["instances"]] == [f"FI-M2-{n:03d}" for n in (1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14)]
    ann = inst["instance_annotations"]
    assert {ann[i["frame_instance_id"]]["candidate_id"] for i in frames} == (set(fia.FRAME_ORDER) - {"FC-M2-006-B", "FC-M2-006-C"}) | {"FC-M2-006-BC"}
    for i in frames:
        assert i["status"] == "CONFIRMED" and i["provenance"]["source_type"] == "USER_ASSISTED_PHOTO" and i["count"] == 1 and i["human_decision_ref"].startswith("PCD-")
        refs = {r["ref_type"] for r in i["source_refs"]}
        assert {"PHOTO", "ORIGINAL_CANDIDATE", "HUMAN_DECISION", "MATERIAL_BASIS"} <= refs
        assert i["material"] == "WOOD" and ann[i["frame_instance_id"]]["material_basis"] == "SOURCE_REPORTED_BUILDING_LEVEL"
        mat = next(r for r in i["source_refs"] if r["ref_type"] == "MATERIAL_BASIS")
        assert mat["presence_decision_id"] == "CPD-00001" and mat["material_as_reported"] == "hout"
        assert ann[i["frame_instance_id"]]["quantity_contributions"] == {"FRAME_COUNT": 1, "WINDOW_COUNT": 1}
    children = [i for i in frames if ann[i["frame_instance_id"]]["candidate_id"].count("-") == 3]
    assert len(children) == 4 and all("CORRECTED_CHILD_CANDIDATE" in {r["ref_type"] for r in i["source_refs"]} for i in children)
    assert fia.instance_store_errors(inst) == []


def test_full_partial_split_follows_bboxes(inst):
    pc = inst["photo_visible_counts"]
    ann = inst["instance_annotations"]
    frames = [i for i in inst["instances"] if i["component_type"] == "EXTERIOR_FRAME"]
    assert pc["ordinary_frames_FULL"] == len([i for i in frames if ann[i["frame_instance_id"]]["photo_visibility"] == "FULL"]) == 9
    assert pc["ordinary_frames_PARTIAL"] == 2
    assert {ann[i["frame_instance_id"]]["candidate_id"] for i in frames if ann[i["frame_instance_id"]]["photo_visibility"] == "PARTIAL"} == {"FC-M2-001-A", "FC-M2-008"}


def test_door_is_separate_instance(inst):
    doors = [i for i in inst["instances"] if i["component_type"] == "EXTERIOR_DOOR"]
    assert len(doors) == 1 and doors[0]["material"] == "UNKNOWN" and doors[0]["status"] == "CONFIRMED"
    a = inst["instance_annotations"][doors[0]["frame_instance_id"]]
    assert a["candidate_id"] == "FC-M2-011" and a["photo_visibility"] == "PARTIAL" and a["quantity_contributions"] == {"EXTERIOR_DOOR_COUNT": 1}
    assert inst["photo_visible_counts"]["PHOTO_VISIBLE_WINDOW_COUNT"] == 11  # deur niet in WINDOW_COUNT


def test_rejected_unknown_roof_dormer_create_no_instance(inst):
    cands = {a["origin_candidate_id"] for a in inst["instance_annotations"].values()}
    for cid in ("FC-M2-010", "FC-M2-012", "FC-M2-013", "FC-M2-019") + tuple(f"FC-M2-{n:03d}" for n in range(14, 19)):
        assert cid not in cands, cid
    assert cands == {"FC-M2-001", "FC-M2-002", "FC-M2-003", "FC-M2-004", "FC-M2-005", "FC-M2-006", "FC-M2-007", "FC-M2-008", "FC-M2-009", "FC-M2-011"}


def test_roof_and_dormer_stay_separate(corrected):
    assert [r["candidate_id"] for r in corrected["roof_context_observations"]] == [f"FC-M2-{n:03d}" for n in range(14, 19)]
    assert all(r["category"] == "ROOF_WINDOW" for r in corrected["roof_context_observations"])
    d = corrected["dormer_context_observations"]
    assert len(d) == 1 and d[0]["candidate_id"] == "FC-M2-019" and d[0]["parent"]["type"] == "ROOF_DORMER" and d[0]["category"] == "DORMER_WINDOW"
    assert {r["candidate_id"] for r in corrected["rejected_or_unknown"]} == {"FC-M2-010", "FC-M2-012", "FC-M2-013"}


# --- verboden afgeleiden ------------------------------------------------------------------------------------------------------
def test_no_metrics_painting_area_or_building_total(inst, corrected):
    for i in inst["instances"]:
        assert not ({"width_m", "height_m", "opening_area_m2", "frame_outer_area_m2", "painting_area_m2", "scale_evidence"} & set(i)) or all(
            i.get(k) is None for k in ("width_m", "height_m", "opening_area_m2", "frame_outer_area_m2", "scale_evidence"))
        assert "painting_area_m2" not in i
    assert inst["policy"]["metric_dimensions"] == "NONE" and inst["policy"]["painting_area"] == "NEVER_AUTOMATIC"
    pc = inst["photo_visible_counts"]
    assert pc["count_basis"] == "PHOTO_VISIBLE_CONFIRMED_COUNT" and pc["is_building_total"] is False
    assert (pc["PHOTO_VISIBLE_FRAME_COUNT"], pc["PHOTO_VISIBLE_WINDOW_COUNT"], pc["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"]) == (11, 11, 1)
    assert all(v == {"status": "UNKNOWN", "value": None} for v in inst["building_totals"].values())
    text = json.dumps(inst) + json.dumps(corrected)
    assert "756.80" not in text and "BUILDING_TOTAL\": " not in text
    assert inst["policy"]["historical_756_80_m2"] == "NOT_COMPARABLE"


def test_counting_unit_documented(inst, corrected):
    for t in (inst["counting_unit"], corrected["counting_unit"]):
        assert "kozijn-/gevelopening" in t and "metselwerk" in t and "glasruit" in t


def test_no_repeat_activation(corrected):
    assert [m["module_id"] for m in corrected["repeat_modules"]] == ["MOD-M2-A", "MOD-M2-B"]
    for m in corrected["repeat_modules"]:
        assert m["status"] == "REPEAT_CANDIDATE" and m["active"] is False and m["multiplier"] is None and m["human_decision"] == "DO_NOT_ACTIVATE_REPEAT_YET"
    assert load("data/frame_inventory/component_repeat_groups_v1.json")["groups"] == []


def test_no_quantity_resolution_and_existing_stores_unchanged():
    assert load("data/quantity_resolutions/quantity_resolution_records.json")["records"] == []
    inv = load("data/frame_inventory/frame_inventory_v1.json")
    assert inv["instances"] == [] and inv["frame_groups"] == []
    for b in inv["buildings"]:
        assert all(q["status"] == "UNKNOWN" and q["value"] is None for q in b["quantities"].values())
    import test_photo_frame_review as t
    for path, digest in t.UNCHANGED.items():
        with open(os.path.join(ROOT, path), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == digest, path
    recs = {r["decision_id"]: r for r in load("data/component_presence/component_presence_decision_records.json")["records"]}
    assert recs["CPD-00001"]["decision"] == "PRESENT" and recs["CPD-00002"]["decision"] == "PRESENT"


def test_committed_outputs_current_and_overlay_exists():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_frame_instance_activation.py"), "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.getsize(fia.OVERLAY) > 10000
    text = fia.REPORT.read_text(encoding="utf-8")
    assert "756,80 blijft NOT_COMPARABLE" in text and "PHOTO_VISIBLE_FRAME_COUNT | 11" in text
