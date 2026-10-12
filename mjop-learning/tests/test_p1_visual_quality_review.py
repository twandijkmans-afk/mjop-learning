"""P1 Visual Review - Quality Corrections v1: het kwaliteitsrapport, de bewijsclassificatie en de onaangetaste brondata."""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import human_decision_pack_data as H  # noqa: E402
import p1_quality_review_data as Q  # noqa: E402

REVIEW = ROOT / "reports/frames/photo_review_map003_map004_v1"
QDIR = REVIEW / "p1_quality_review"
REP = json.loads((REVIEW / "maldenhof_p1_visual_quality_review_v1.json").read_text())
MD = (REVIEW / "maldenhof_p1_visual_quality_review_v1.md").read_text()
REV = json.loads((REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.json").read_text())
HTML = (REVIEW / "decision_pack/maldenhof_human_visual_decision_pack_v1.html").read_text()
PACK = json.loads(re.search(r"const PACK = (\{.*?\});\n\(function", HTML, re.S).group(1).replace("<\\/", "</"))
ITEMS = {i["review_id"]: i for i in PACK["items"]}
P1 = [i["review_id"] for i in PACK["items"] if i["priority"] == "P1"]
RECS = {r["review_id"]: r for r in REP["records"]}
FEAT = json.loads((QDIR / "p1_feature_match_evidence_v1.json").read_text())


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_report_covers_all_54_p1_points_with_required_columns():
    assert len(P1) == 54 and set(RECS) == set(P1) and len(REP["records"]) == 54
    for rid, r in RECS.items():
        for k in ("current_classification", "finding", "visual_evidence", "next_step", "quality_status", "extra_evidence_needed", "technically_correct"):
            assert r[k] not in (None, ""), (rid, k)
        assert r["quality_status"] in Q.QUALITY_STATUSES
        assert f"| {rid} |" in MD                                                  # elk P1-ID staat in het rapport
    assert REP["counts"]["p1_review_points"] == 54 and sum(REP["counts"]["by_quality_status"].values()) == 54
    assert "Een technisch geldige reviewkaart is niet automatisch een visueel bewezen object" in MD
    assert REP["status"] == "QUALITY_CHECK_NOT_A_HUMAN_APPROVAL"


def test_technical_correctness_is_separate_from_visual_evidence():
    assert REP["counts"]["technically_correct"] == sum(r["technically_correct"] for r in REP["records"]) == 54
    # 'technisch correct' mag nooit automatisch tot 'visueel ondersteund' leiden: er zijn technisch correcte punten die betere foto's of menselijke beoordeling vragen
    assert REP["counts"]["by_quality_status"]["NEEDS_BETTER_PHOTO"] > 0 and REP["counts"]["by_quality_status"]["NEEDS_MANUAL_REVIEW"] > 0
    assert all(r["technically_correct"] for r in REP["records"] if r["quality_status"] in ("NEEDS_BETTER_PHOTO", "NEEDS_MANUAL_REVIEW"))
    for rid, i in ITEMS.items():                                                   # de pagina draagt dezelfde status als het rapport
        if rid in RECS:
            assert i["quality"]["quality_status"] == RECS[rid]["quality_status"]


def test_all_six_separations_verified_and_counting_rule_unchanged():
    assert set(Q.SEP_RESULTS) == {f"RV-SEP-00{k}" for k in range(1, 7)}
    for rid, (pier, sep, bbox, enough, note) in Q.SEP_RESULTS.items():
        assert (pier, sep, bbox, enough) == (True, True, True, True) and RECS[rid]["separation_checks"]["pier_visible"] is True
        assert (QDIR / f"QSEP-{rid[-3:]}.jpg").exists()
    assert "telregel" in MD and "PCD-00004" in MD


def test_relation_evidence_classes_cover_all_p1_relations_and_are_not_decisions():
    rel_items = [i for i in ITEMS.values() if i["review_type"] == "OVERLAP_RELATION" and i["priority"] == "P1"]
    assert len(rel_items) == 27 == len(Q.REL_ASSESSMENT) == len(Q.P1_REL_ORDER)
    assert {i["relation_ids"][0] for i in rel_items} == set(Q.REL_ASSESSMENT)
    for vr, (cls, basis, note) in Q.REL_ASSESSMENT.items():
        assert cls in Q.EVIDENCE_CLASSES and basis and note
        r = RECS[f"RV-REL-{vr}"]
        assert r["evidence_class"] == cls and r["quality_status"] == Q.relation_status(cls)
        prop = ITEMS[f"RV-REL-{vr}"]["claude_proposal"]
        if cls == "INSUFFICIENT_EVIDENCE":
            assert prop == "UNDECIDABLE", vr                                      # onvoldoende bewijs -> nooit een SAME-voorstel
        else:
            assert prop == "SAME", vr
        assert (QDIR / r["visual_evidence"]).exists() or (REVIEW / r["visual_evidence"]).exists(), r["visual_evidence"]
    for vr in ("VR-021", "VR-027", "VR-028", "VR-029", "VR-030", "VR-024", "VR-025", "VR-026"):   # prioriteitsrelaties uit de opdracht
        assert vr in Q.REL_ASSESSMENT
    assert Q.REL_ASSESSMENT["VR-026"][0] == "INSUFFICIENT_EVIDENCE" and Q.REL_ASSESSMENT["VR-027"][0] == "STRONG_VISUAL_SUPPORT"
    assert REP["counts"]["relations_by_evidence_class"] == {"STRONG_VISUAL_SUPPORT": 14, "MODERATE_VISUAL_SUPPORT": 7, "INSUFFICIENT_EVIDENCE": 6}
    # facade-relaties blijven gevelniveau
    assert RECS["RV-REL-VR-001"]["relation_type"] == "FACADE_SECTION" and RECS["RV-REL-VR-020"]["relation_type"] == "FACADE_SECTION"


def test_feature_match_is_supporting_only_and_has_noise_floor():
    rels = {e["relation_id"]: e for e in FEAT["relations"]}
    assert len(rels) == 43 == len(REV["relations"])
    assert FEAT["method"].startswith("SIFT")
    nonpartner = [max(e.get("best_other_inliers_row", 0), e.get("best_other_inliers_col", 0)) for e in rels.values() if "best_other_inliers_row" in e]
    assert max(nonpartner) >= 17                                                   # niet-partners halen hoge scores: een getal alleen bewijst niets
    # VR-021 is STRONG ondanks lage kenmerkmatch (plaat 278 is het anker); VR-025 is MODERATE ondanks 20 inliers (geen marge)
    assert rels["VR-021"]["inliers"] <= 10 and Q.REL_ASSESSMENT["VR-021"][0] == "STRONG_VISUAL_SUPPORT" and "PLATE_ANCHOR" in Q.REL_ASSESSMENT["VR-021"][1]
    assert Q.REL_ASSESSMENT["VR-025"][0] == "MODERATE_VISUAL_SUPPORT"


def test_object_matrix_answers_six_separate_questions():
    assert set(Q.OBJ_MATRIX) == {"OBS-MAP003-020", "OBS-MAP003-026", "OBS-MAP003-027", "OBS-MAP003-028", "OBS-MAP004-012", "OBS-MAP004-020", "OBS-MAP004-022"}
    for oid, m in Q.OBJ_MATRIX.items():
        assert tuple(m) == Q.Q6 and all(v[0] and v[1] for v in m.values())
        assert m["pand_link_proven"][0] == "NOT_PROVEN"                           # geen enkele pandkoppeling
        assert m["measurable"][0] == "NO"
        assert (QDIR / f"QD-{oid[4:]}.jpg").exists()
    assert Q.OBJ_MATRIX["OBS-MAP003-027"]["exists_visibly"][0] == "UNCERTAIN" and RECS["RV-OBS-MAP003-027"]["quality_status"] == "NEEDS_BETTER_PHOTO"
    assert RECS["RV-OBS-MAP004-022"]["quality_status"] == "NEEDS_BETTER_PHOTO"
    assert Q.OBJ_MATRIX["OBS-MAP004-020"]["full_or_partial"][0] == "PARTIAL"
    # de zes vragen staan als afzonderlijke velden, niet als een enkele zichtbaarheidsstatus
    assert set(RECS["RV-OBS-MAP003-020"]["six_questions"]) == set(Q.Q6)


def test_proposal_corrections_are_recorded_separately_and_sources_untouched():
    assert set(Q.PROPOSAL_CORRECTIONS) == set(REP["proposal_corrections"]) == {"RV-OBS-MAP003-027", "RV-OBS-MAP004-022", "RV-REL-VR-008", "RV-REL-VR-026", "RV-REL-VR-044"}
    for rid, (old, new, why) in Q.PROPOSAL_CORRECTIONS.items():
        assert RECS[rid]["proposal_correction"]["from"] == old and ITEMS[rid]["claude_proposal_v1"] == old and ITEMS[rid]["claude_proposal"] == new and why
    # de oorspronkelijke 50 observaties, 43 relaties en het review-document zijn onveranderd
    assert len(REV["observations"]) == 50 and len(REV["relations"]) == 43
    assert _sha(REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.json") == "28cccaf2eccfc82aa871b6a66c342043112406fb127d044ddf1f1051703e0719"
    assert _sha(REVIEW / "maldenhof_visual_photo_review_map003_map004_v1.md") == "18e3aa8b7ec5083f1641e7160cc7993c97e166e0b63e2c056d95daac53107ff8"
    assert _sha(ROOT / "scripts/visual_review_map003_map004_data.py") == "560931f95ab58dfcd0dbedd4e57edac4cba66afec1f64eee82ba90a2c202c176"


def test_no_effects_no_automatic_human_decisions_in_quality_report():
    e = REP["effects"]
    assert (e["instances_created"], e["bag_links_created"], e["building_totals"], e["costs"], e["app_decisions_open"]) == (0, 0, None, None, 48)
    assert "PR #41 is niet gemerged" in MD and "48 APP-besluiten OPEN" in MD
    approval = (ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md").read_text()
    rows = [l for l in approval.splitlines() if re.match(r"\| APP-\d{3} \|", l)]
    assert len(rows) == 48 and all(r.rstrip().endswith("| OPEN |") for r in rows)
    inst = json.loads((ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json").read_text())["photo_visible_counts"]
    assert (inst["PHOTO_VISIBLE_FRAME_COUNT"], inst["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"], inst["ordinary_frames_FULL"], inst["ordinary_frames_PARTIAL"]) == (11, 1, 9, 2)
    for r in REP["records"]:                                                      # niets in de kwaliteitsdata beweert een pandkoppeling of unieke telling
        assert "BAG-pand" not in r["finding"] or "niet" in r["finding"] or "bewijst" in r["finding"]
    for f in (ROOT / "data").rglob("*.json"):
        t = f.read_text()
        assert "RV-OBS-" not in t and "p1_visual_quality_review" not in t, f


def test_009_010_conclusion_keeps_photo2_decision():
    assert any("MAP-013" in t and "metselwerk" in t for t in Q.B009_010)
    assert "geen nieuwe unieke instance" in Q.B009_CONCLUSION and "niet automatisch dubbel" in Q.B009_CONCLUSION and "HQ-VR-001 blijft een menselijk besluit" in Q.B009_CONCLUSION
    assert RECS["RV-OBS-MAP003-009"]["quality_status"] == "NEEDS_MANUAL_REVIEW" and RECS["RV-OBS-MAP003-010"]["quality_status"] == "VISUALLY_SUPPORTED"
    assert (QDIR / "Q009_010_four_photos.jpg").exists()
