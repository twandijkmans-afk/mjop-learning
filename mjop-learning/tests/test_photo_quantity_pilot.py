"""Photo-to-Quantity Pilot v1: uitsluitend synthetische fixtures (geen foto-inhoud, geen netwerk, geen besluiten).

De rooktest op de echte repositorygegevens draait alleen als Pillow en de ingecheckte pilotbronnen beschikbaar zijn en schrijft
uitsluitend naar tmp_path.
"""
import ast
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bruto_quantity_core as core  # noqa: E402
import photo_quantity_pilot as pq  # noqa: E402


def obs(oid, photo, bbox, typ="WINDOW_OPENING", vis="FULL", note=""):
    return pq.normalise_observation(obs_id=oid, photo_id=photo, observation_type=typ, visibility=vis, bbox_px=bbox, note=note)


def rel(rid, left, right, cls="POSSIBLY_SAME_PHYSICAL_FRAME", strength="MEDIUM"):
    return {"rel_id": rid, "left": left, "right": right, "class": cls, "strength": strength, "basis": "synthetisch"}


A3, A4 = "MAP-003:OBS-MAP003-", "MAP-004:OBS-MAP004-"


def three_obs():
    return [obs("OBS-MAP003-001", "MAP-003", [100, 100, 200, 180]), obs("OBS-MAP004-001", "MAP-004", [40, 100, 140, 180]),
            obs("OBS-MAP003-002", "MAP-003", [300, 100, 400, 180])]


def test_parse_refs_handles_lists_and_fc_ids_and_ignores_plates():
    o, r = pq.parse_refs("MAP-003:OBS-MAP003-009+010 / MAP-004:OBS-MAP004-004/010/011")
    assert ("MAP-003", "OBS-MAP003-010") in o and ("MAP-004", "OBS-MAP004-011") in o and len(o) == 5
    o, r = pq.parse_refs("MAP-002:FC-M2-006-BC (FI-M2-014)")
    assert o == [("MAP-002", "FC-M2-006-BC")]
    assert pq.parse_refs("MAP-002:plaat 288 + muur") == ([], [])
    assert pq.parse_refs("MAP-009:REF-MAP009-003")[1] == ["REF-MAP009-003"]


def test_overlap_merges_one_to_one_medium_and_counts_once():
    ident = pq.build_identity(three_obs(), [rel("R1", A3 + "001", A4 + "001")])
    assert len(ident["objects"]) == 2
    merged = [o for o in ident["objects"] if len(o["members"]) == 2][0]
    assert merged["photos"] == ["MAP-003", "MAP-004"] and merged["identity_status"] == "CROSS_PHOTO_PROBABLE_MEDIUM"


def test_low_strength_is_possible_double_count_not_merge():
    ident = pq.build_identity(three_obs(), [rel("R1", A3 + "001", A4 + "001", strength="LOW")])
    assert len(ident["objects"]) == 3 and len(ident["possible_duplicates"]) == 1
    flagged = [o for o in ident["objects"] if "POSSIBLE_DOUBLE_COUNT" in o["identity_flags"]]
    assert len(flagged) == 2


def test_similar_frames_without_relation_are_not_merged():
    o = [obs("OBS-MAP003-001", "MAP-003", [100, 100, 200, 180]), obs("OBS-MAP003-002", "MAP-003", [300, 100, 400, 180]),
         obs("OBS-MAP004-001", "MAP-004", [100, 100, 200, 180])]  # identieke geometrie, geen relatie
    ident = pq.build_identity(o, [])
    assert len(ident["objects"]) == 3


def test_many_to_one_and_undeterminable_stay_unresolved():
    o = three_obs()
    ident = pq.build_identity(o, [rel("R1", A3 + "001+002", A4 + "001"), rel("R2", A3 + "002", A4 + "001", cls="UNDETERMINABLE")])
    assert len(ident["objects"]) == 3
    assert {u["reason"] for u in ident["unresolved"]} == {"MANY_TO_ONE", "UNDETERMINABLE"}
    assert all("UNRESOLVED_IDENTITY_CONFLICT" in x["identity_flags"] for x in ident["objects"])


def test_same_photo_merge_is_refused():
    o = three_obs()
    ident = pq.build_identity(o, [rel("R1", A3 + "001", A4 + "001", strength="HIGH"), rel("R2", A3 + "002", A4 + "001")])
    assert len(ident["refused_links"]) == 1 and len(ident["objects"]) == 2


def test_different_frames_block_recorded_and_not_violated():
    ident = pq.build_identity(three_obs(), [rel("R1", A3 + "002", A4 + "001", cls="DIFFERENT_FRAMES", strength="HIGH")])
    assert len(ident["blocks"]) == 1 and ident["blocks_violated"] == [] and len(ident["objects"]) == 3


def test_reference_fragments_are_evidence_not_observations():
    refs = [{"ref_id": "REF-MAP009-001", "photo_id": "MAP-009"}]
    ident = pq.build_identity(three_obs(), [rel("R1", A3 + "001", "MAP-009:REF-MAP009-001")], refs)
    assert len(ident["objects"]) == 3
    ev = [o for o in ident["objects"] if o["reference_evidence"]]
    assert len(ev) == 1 and ev[0]["reference_evidence"][0]["photo_id"] == "MAP-009"


def test_identity_bounds_bracket_provisional_count():
    ident = pq.build_identity(three_obs(), [rel("R1", A3 + "001", A4 + "001"), rel("R2", A3 + "002", A4 + "001", strength="LOW")])
    b = pq.identity_bounds(ident)
    assert b["lower"] <= b["provisional"] <= b["upper_no_cross_photo_merge"]


def test_multi_pane_frame_is_one_frame_and_door_is_separate_category():
    f = obs("OBS-MAP003-001", "MAP-003", [0, 0, 300, 100], note="Tweedelig kozijn met drie ramen; een opening")
    assert pq.classify_frame_type(f)[0] == "MULTI_PANE_WINDOW" and pq.category_of(f["observation_type"]) == "FACADE_FRAME"
    d = obs("OBS-MAP003-002", "MAP-003", [0, 0, 60, 190], typ="EXTERIOR_DOOR", vis="PARTIAL")
    assert pq.category_of(d["observation_type"]) == "DOOR" and pq.classify_frame_type(d)[0] == "EXTERIOR_DOOR"
    assert pq.classify_frame_type(obs("X", "P", [0, 0, 50, 90], note="Smal raam"))[0] == "NARROW_WINDOW"
    assert pq.classify_frame_type(obs("X", "P", [0, 0, 50, 90], note="Hoofdkozijn naast een smal element"))[0] == "MULTI_PANE_WINDOW"


def test_row_layers_split_into_three_rows():
    o = [obs(f"O{i}", "P", [i * 100, y, i * 100 + 80, y + 80]) for i, y in enumerate([100, 105, 300, 310, 500])]
    layers = pq.classify_row_layers(o)
    assert [layers[("P", f"O{i}")] for i in range(5)] == ["UPPER_ROW", "UPPER_ROW", "MIDDLE_ROW", "MIDDLE_ROW", "GROUND_ROW"]


def _scales():
    obs_ = [obs("U", "P", [0, 100, 160, 190]), obs("M", "P", [0, 300, 160, 430]), obs("G", "P", [0, 500, 90, 590])]
    layers = pq.classify_row_layers(obs_)
    pitches = {"P": pq.storey_pitch_px(pq.row_pitches(obs_, layers)["P"])}
    sc = pq.scale_scenarios(pitches, {"lo": "2.5", "central": "2.7", "hi": "2.9"}, None, Decimal("0.10"))
    return obs_, layers, sc


def test_estimates_are_labelled_assumption_with_ordered_band_and_decimal_math():
    obs_, layers, sc = _scales()
    e = pq.estimate_observation(obs_[0], layers[("P", "U")], sc["scales"]["P"])
    for k in ("low", "central", "high"):
        w, h, a = Decimal(e[k]["width_m"]), Decimal(e[k]["height_m"]), Decimal(e[k]["gross_m2"])
        assert a == core.gross_area_exact(str(w), str(h), 1)
    assert Decimal(e["low"]["gross_m2"]) < Decimal(e["central"]["gross_m2"]) < Decimal(e["high"]["gross_m2"])
    comb = pq.combine_object_estimates([("P:U", e)])
    assert comb["status"] == "PHOTO_ASSUMPTION_ESTIMATE" and comb["status"] not in ("MEASURED", "CONFIRMED", "APPROVED")


def test_missing_scale_row_and_partial_visibility_give_no_estimate():
    obs_, layers, sc = _scales()
    partial = obs("PP", "P", [0, 100, 160, 190], vis="PARTIAL")
    assert pq.estimate_observation(partial, "UPPER_ROW", sc["scales"]["P"]) is None
    assert pq.estimate_observation(obs_[0], "UPPER_ROW", {}) is None
    door = obs("D", "P", [0, 0, 60, 190], typ="EXTERIOR_DOOR")
    assert pq.estimate_observation(door, "GROUND_ROW", sc["scales"]["P"]) is None


def test_out_of_core_range_gives_no_estimate_instead_of_a_guess():
    obs_, layers, sc = _scales()
    huge = obs("H", "P", [0, 0, 5000, 90])
    assert pq.estimate_observation(huge, "UPPER_ROW", sc["scales"]["P"]) is None


def test_sum_counts_unique_objects_once_and_flags_incomplete():
    obs_, layers, sc = _scales()
    e = pq.estimate_observation(obs_[0], "UPPER_ROW", sc["scales"]["P"])
    one = {"estimate": pq.combine_object_estimates([("A", e)])}
    two_obs_same_object = {"estimate": pq.combine_object_estimates([("A", e), ("B", e)])}
    unknown = {"estimate": None}
    s1 = pq.sum_estimates([one, unknown])
    s2 = pq.sum_estimates([two_obs_same_object, unknown])
    assert s1["gross_m2_central_exact"] == s2["gross_m2_central_exact"]  # twee foto's van hetzelfde object tellen niet dubbel
    assert s1["n_without_estimate"] == 1 and s1["incomplete"] is True


def test_anchor_disagreement_widens_band_and_central_is_compromise():
    pitches = {"P": {"UPPER_ROW": 200.0, "MIDDLE_ROW": 200.0, "GROUND_ROW": 200.0}}
    base = pq.scale_scenarios(pitches, {"lo": "2.5", "central": "2.7", "hi": "2.9"}, None)
    a2 = {"P": Decimal("0.0067")}  # half zo groot als A1 (0.0135)
    wide = pq.scale_scenarios(pitches, {"lo": "2.5", "central": "2.7", "hi": "2.9"}, a2)
    assert wide["a2_over_a1_ratio"] < 1
    assert wide["scales"]["P"]["UPPER_ROW"]["low"] < base["scales"]["P"]["UPPER_ROW"]["low"]
    assert wide["scales"]["P"]["UPPER_ROW"]["central"] < base["scales"]["P"]["UPPER_ROW"]["central"]


def test_relative_geometry_has_no_meters():
    rec = pq.relative_geometry(obs("X", "P", [0, 0, 160, 80]), 200.0)
    assert set(rec) == {"aspect_w_over_h", "width_pitch_units", "height_pitch_units"} and rec["aspect_w_over_h"] == 2.0


def test_deviating_sizes_and_geometry_groups_do_not_merge_identity():
    rows = [{"id": f"PU-{i}", "layer": "UPPER_ROW", "frame_type": "WINDOW_STANDARD", "aspect_w_over_h": 1.5, "width_pitch_units": w}
            for i, w in enumerate([0.8, 0.8, 0.82, 1.6])]
    assert list(pq.deviating_sizes(rows)) == ["PU-3"]
    groups, lst = pq.geometry_groups(rows)
    assert groups["PU-0"] == groups["PU-1"] and groups["PU-3"] != groups["PU-0"]


def test_layer_shift_monotone_parallax_check():
    shifts = {"UPPER_ROW": {"median_shift_px": 600}, "GROUND_ROW": {"median_shift_px": 1200}}
    assert pq.parallax_consistency(shifts, ["UPPER_ROW", "GROUND_ROW"])[0] is True
    assert pq.parallax_consistency(shifts, ["GROUND_ROW", "UPPER_ROW"])[0] is False


def test_iou_and_detection_agreement_is_not_accuracy():
    assert pq.iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0 and pq.iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    c = pq.compare_detections([[0, 0, 10, 10]], [("A", [0, 0, 10, 10]), ("B", [50, 50, 60, 60])])
    assert c["n_agree"] == 1 and c["annotations_without_detection"] == ["B"] and "grondwaarheid" in c["note"]


def test_white_frame_detector_on_synthetic_image():
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    img = np.full((300, 400, 3), 40, np.uint8)
    img[100:180, 100:220] = 240
    img[110:170, 110:210] = 90  # donker glas binnen een wit kader
    boxes = pq.detect_white_frames(img, min_w=30, min_h=30)
    assert any(pq.iou(b, [100, 100, 220, 180]) > 0.8 for b in boxes)


def test_invariants_and_no_network_or_ai_imports():
    inv = pq.INVARIANTS
    assert inv["fi_ids_created"] is False and inv["decisions_registered"] is False and inv["external_vision_calls"] == 0
    assert inv["measured_or_confirmed_from_photo"] is False and inv["building_total_claimed"] is False
    banned = {"socket", "requests", "urllib", "urllib3", "http", "anthropic", "openai", "httpx", "subprocess"}
    for name in ("photo_quantity_pilot.py", "run_maldenhof_photo_quantity_pilot.py"):
        tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        assert not (mods & banned), (name, mods & banned)


def test_library_never_writes_files():
    src = (ROOT / "scripts" / "photo_quantity_pilot.py").read_text(encoding="utf-8")
    assert "open(" not in src and "write_text" not in src and ".save(" not in src


def test_pilot_config_has_no_photo_content():
    cfg = json.loads((ROOT / "config" / "maldenhof_photo_quantity_pilot_v1.json").read_text(encoding="utf-8"))
    assert "bbox" not in json.dumps(cfg).lower()


def _tree_hash(rel_paths):
    out = {}
    for rel_ in rel_paths:
        base = ROOT / rel_
        for f in ([base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())):
            out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def test_pipeline_smoke_on_repository_data_is_readonly_and_consistent(tmp_path):
    pytest.importorskip("PIL")
    run = pytest.importorskip("run_maldenhof_photo_quantity_pilot")
    cfg = json.loads(run.CONFIG.read_text(encoding="utf-8"))
    needed = [ROOT / cfg["sources"][k] for k in ("review_json", "map002_annotation", "map002_corrected", "frame_instances_readonly", "bag_snapshot")]
    if not all(p.exists() for p in needed) or not (ROOT / cfg["photo_sources"]["MAP-002"]["path"]).exists():
        pytest.skip("pilotbronnen niet aanwezig")
    before = _tree_hash(run.GUARDED)
    state = run.run_pipeline(cfg)
    recs, summary = run.build_outputs(state, cfg)
    assert _tree_hash(run.GUARDED) == before
    B, C = summary["B_PROVISIONAL_UNIQUE"], summary["C_PHOTO_ESTIMATED_AREA"]
    assert B["different_frames_blocks_violated"] == [] and C["reliable_scale_available"] is False
    assert C["measured_or_drawing_derived_objects"] == 0
    assert B["unique_frame_bounds"]["lower"] <= B["unique_facade_frames_provisional"] <= B["unique_frame_bounds"]["upper_no_cross_photo_merge"]
    # geen observatie in twee objecten; elk object hoogstens een observatie per foto
    seen = [k for o in state["objects"] for k in o["raw"]["members"]]
    assert len(seen) == len(set(seen)) == len(state["observations"])
    for o in state["objects"]:
        photos = [k[0] for k in o["raw"]["members"]]
        assert len(photos) == len(set(photos))
    assert all(r["dimension_status"] in ("UNKNOWN", "PHOTO_ASSUMPTION_ESTIMATE") for r in recs)
    assert all(r["v2_dimension_status_equivalent"] == "UNKNOWN" for r in recs)
    assert all(r["gross_m2_central"] is None for r in recs if r["category"] != "FACADE_FRAME")
    exp = sum(Decimal(r["gross_m2_central"]) for r in recs if r["in_analysed_segment"] and r["gross_m2_central"])
    assert Decimal(C["assumption_estimate_sum"]["gross_m2_central_exact"]) == exp
    rc = run.main(["--out", str(tmp_path / "out"), "--tests-info", "test"])
    assert rc == 0 and (tmp_path / "out" / "pilot_report.html").exists()
