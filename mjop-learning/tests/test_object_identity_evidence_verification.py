import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import object_identity_evidence_verification as EV  # noqa: E402
import object_identity_pilot as OI  # noqa: E402

REC = json.loads(EV.OUT_JSON.read_text(encoding="utf-8"))
ARCH = {p["photo_id"]: p for p in json.loads(OI.ARCHIVE_JSON.read_text(encoding="utf-8"))["photos"]}
OIC = json.loads(OI.OUT_JSON.read_text(encoding="utf-8"))["candidates"][0]


def test_all_36_originals_covered_verified_and_assessed():
    ph = {p["photo_id"]: p for p in REC["photos"]}
    assert set(ph) == set(ARCH) and len(ph) == 36
    for pid, p in ph.items():
        assert p["sha256"] == ARCH[pid]["sha256"] and p["sha256_verified_against_register"] is True
        assert p["inspection"] in ("DETAIL", "SHEET") and p["relevance"] and p["note"] and p["method"] == "MANUAL_VISUAL_READING"
    assert REC["originals_in_repository"] is False


def test_oic_is_unchanged_and_status_not_changed():
    assert REC["candidate_group_id"] == OIC["candidate_group_id"] == "OIC-VR-027"
    assert REC["identity_status_before"] == REC["identity_status_after"] == OIC["identity_status"] == "SUPPORTED_CANDIDATE" and REC["status_changed"] is False
    assert REC["observation_ids"] == OIC["observation_ids"]
    assert REC["inputs"]["oic_json_sha256"] == OI.sha(OI.OUT_JSON)
    assert all(OIC[k] is False for k in ("is_instance", "merged", "counts_in_any_total", "same_physical_frame_proven")) and OIC["bag_pand_id"] is None


def test_crops_are_inside_the_original_images_and_reference_known_photos():
    for c in REC["crops"]:
        a = ARCH[c["photo_id"]]
        x0, y0, x1, y1 = c["region_px"]
        assert 0 <= x0 < x1 <= a["width_px"] and 0 <= y0 < y1 <= a["height_px"], c
    assert (EV.OUT_DIR / Path(REC["figure"]).name).exists()
    am = REC["additional_matches"][0]
    assert am["photo_id"] in ARCH and am["photo_id"] not in ("MAP-003", "MAP-004") and am["limits"] and am["arguments"]


def test_feature_match_is_documented_as_non_identifying():
    pairs = REC["feature_match_pairs"]
    true_view = next(p for p in pairs if "MAP-009" in p["b"] and p["a"].startswith("MAP-003:OBS"))
    different_windows = [p for p in pairs if "MAP-007" in p["a"] + p["b"] and "MAP-009" not in p["a"] + p["b"]]
    assert max(p["inliers"] for p in different_windows) > true_view["inliers"]      # hoge score is geen identiteitsbewijs
    ident = {f["feature"]: f["identifying"] for f in REC["features"]}
    assert ident["Hoge feature-matchscore"] is False
    assert any(not v for v in ident.values()) and any(v for v in ident.values())


def test_conclusion_is_cautious_and_no_activation_effects():
    assert REC["conclusion"] in ("AANVULLEND_BEWIJS_GEVONDEN", "ONVOLDOENDE_BEWIJS", "TEGENBEWIJS_GEVONDEN")
    assert "geen activatie" in REC["recommendation"] and "SUPPORTED_CANDIDATE" in REC["recommendation"]
    e = REC["effects"]
    assert e["instances_created"] == e["bag_links_created"] == e["merges"] == e["new_observations"] == e["human_decisions_changed"] == 0
    assert e["building_totals"] is None and e["quantities"] is None and e["costs"] is None and e["oic_changed"] is False
    assert REC["contradictions"] == [] and REC["swap_risk"]


def test_report_is_rendered_from_the_json_and_is_deterministic():
    assert EV.render_md(REC) == EV.OUT_MD.read_text(encoding="utf-8")
    assert EV.render_md(REC) == EV.render_md(json.loads(json.dumps(REC)))
    assert "bewijst alleen de muur" in EV.OUT_MD.read_text(encoding="utf-8")


def test_two_feature_match_measurements_are_documented_separately():
    m = {x["id"]: x for x in REC["feature_match_measurements"]}
    assert m["FM-QUALITY-REVIEW"]["inliers"] == 39 and m["FM-QUALITY-REVIEW"]["good_matches"] == 82
    assert m["FM-EVIDENCE-VERIFICATION"]["inliers"] == 29 and m["FM-EVIDENCE-VERIFICATION"]["good_matches"] == 61
    assert m["FM-QUALITY-REVIEW"]["crops"] != m["FM-EVIDENCE-VERIFICATION"]["crops"]
    orig = next(r for r in json.loads(OI.EVIDENCE_JSON.read_text(encoding="utf-8"))["relations"] if r["relation_id"] == "VR-027")
    assert (orig["inliers"], orig["good_matches"]) == (39, 82)
    text = EV.OUT_MD.read_text(encoding="utf-8")
    assert "FM-QUALITY-REVIEW" in text and "FM-EVIDENCE-VERIFICATION" in text and "niet uitwisselbaar" in text


def test_relation_strength_and_quality_class_are_kept_apart():
    assert OIC["relation_strength_in_source"] == "MEDIUM" and OIC["evidence_class"] == "STRONG_VISUAL_SUPPORT"
    assert OIC["relation_strength_in_source"] != OIC["evidence_strength"]
