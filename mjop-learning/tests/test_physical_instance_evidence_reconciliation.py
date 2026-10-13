import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import physical_instance_approval as P  # noqa: E402
import physical_instance_approval_report as PR  # noqa: E402
import physical_instance_evidence_reconciliation as RC  # noqa: E402

REC = json.loads(RC.OUT_JSON.read_text(encoding="utf-8"))
CTX = P.load_context()
CTX["soc_groups"] = P.load_soc_groups()
BASE = P.build_request(CTX, "OIC-VR-027")
REP = json.loads(P.OUT_JSON.read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ctx_copy(**kw):
    c = copy.deepcopy(CTX)
    c.update(kw)
    return c


def rehash(r):
    r["request_hash"] = P.request_hash(r)
    return r


def ev(req=None, ctx=None):
    return P.evaluate_request(ctx or CTX, copy.deepcopy(BASE) if req is None else req)


# ---------------------------------------------------------------- het reconciliatierecord zelf
def test_outcome_is_one_of_three_and_explains_the_scope_difference():
    assert REC["outcome"] in RC.OUTCOMES == ("COMPATIBLE_DIFFERENT_SCOPE", "GENUINE_EVIDENCE_CONFLICT", "INSUFFICIENT_TO_RECONCILE")
    assert REC["outcome"] == "COMPATIBLE_DIFFERENT_SCOPE"
    text = " ".join(REC["outcome_explanation"])
    assert "REF-MAP009-006" in text and "smalle raam" in text and "geen menselijk besluit" in REC["not_a_genuine_conflict_because"]


def test_originals_were_checked_against_sha256_and_match_the_archive_register():
    arch = {p["photo_id"]: p for p in json.loads(RC.OI.ARCHIVE_JSON.read_text(encoding="utf-8"))["photos"]}
    assert [p["photo_id"] for p in REC["photos"]] == ["MAP-003", "MAP-004", "MAP-009"]
    for p in REC["photos"]:
        assert p["sha256_verified_against_register"] is True and p["sha256"] == arch[p["photo_id"]]["sha256"]
        assert p["inspection"] == "ORIGINAL_PIXELS_FULL_RESOLUTION" and (p["width_px"], p["height_px"]) == (arch[p["photo_id"]]["width_px"], arch[p["photo_id"]]["height_px"])
        assert p["method"] == "MANUAL_VISUAL_READING"


def test_crops_lie_inside_the_photos_and_the_two_map009_crops_match_their_sources():
    dims = {p["photo_id"]: (p["width_px"], p["height_px"]) for p in REC["photos"]}
    for c in REC["crops"]:
        x0, y0, x1, y1 = c["region_px"]
        assert 0 <= x0 < x1 <= dims[c["photo_id"]][0] and 0 <= y0 < y1 <= dims[c["photo_id"]][1], c
    by = {c["crop_id"]: c for c in REC["crops"]}
    review = json.loads((ROOT / RC.SOURCES["reference_ref009_006"]["file"]).read_text(encoding="utf-8"))
    ref = next(r for r in review["references"] if r["ref_id"] == "REF-MAP009-006")
    assert by["C-VR045-REF"]["region_px"] == ref["bbox_px"]                                                   # exact de VR-045-uitsnede
    pr42 = json.loads(P.EVIDENCE_VERIFICATION_JSON.read_text(encoding="utf-8"))
    assert by["C-PR42-WIDE"]["region_px"] == next(c for c in pr42["crops"] if c["role"] == "ADDITIONAL_VIEW")["region_px"]   # exact de PR #42-uitsnede
    obs = {o["obs_id"]: o for o in review["observations"]}
    assert by["C-M3-OBS"]["region_px"] == obs["OBS-MAP003-011"]["bbox_px"] and by["C-M4-OBS"]["region_px"] == obs["OBS-MAP004-006"]["bbox_px"]


def test_vr045_facts_in_the_record_equal_the_repository_sources():
    review = json.loads((ROOT / RC.SOURCES["relation_vr045"]["file"]).read_text(encoding="utf-8"))
    rel = next(r for r in review["relations"] if r["rel_id"] == "VR-045")
    assert rel["right"] == "MAP-009:REF-MAP009-006" and "OBS-MAP003-011/012" in rel["left"] and rel["strength"] == "LOW" and rel["merged"] is False and rel["confirmed"] is False
    quality = {r["review_id"]: r for r in json.loads((ROOT / RC.SOURCES["quality_review_vr045"]["file"]).read_text(encoding="utf-8"))["records"]}
    q = REC["vr045_as_reviewed"]["quality_record"]
    assert all(quality["RV-REL-VR-045"][k] == q[k] for k in q)
    p1 = next(r for r in json.loads((ROOT / RC.SOURCES["p1_feature_match"]["file"]).read_text(encoding="utf-8"))["relations"] if r["relation_id"] == "VR-045")
    assert (p1["inliers"], p1["good_matches"]) == (4, 7) == (q["feature_match"]["inliers"], q["feature_match"]["good_matches"])
    for src in RC.SOURCES.values():
        assert (ROOT / src["file"]).exists(), src


def test_vr045_has_no_human_decision_and_nothing_original_was_changed():
    reg = json.loads(RC.OI.REGISTER_JSON.read_text(encoding="utf-8"))
    assert "RV-REL-VR-045" not in {d["review_id"] for d in reg["decisions"]} and len(reg["decisions"]) == 10
    assert REC["vr045_as_reviewed"]["human_decision"] is None and REC["vr045_as_reviewed"]["same_question_as_vr027"] is False
    e = REC["effects"]
    assert e["vr045_modified"] is False and e["quality_review_modified"] is False and e["human_decisions_created"] == e["human_decisions_changed"] == 0
    assert e["pilot_register_changed"] is False and e["oic_changed"] is False and e["new_observations"] == e["instances_created"] == e["bag_links_created"] == 0
    assert e["building_totals"] is None and e["quantities"] is None and e["costs"] is None
    inp = REC["inputs"]
    assert inp["review_json_sha256"] == sha(ROOT / RC.SOURCES["relation_vr045"]["file"]) and inp["quality_json_sha256"] == sha(ROOT / RC.SOURCES["quality_review_vr045"]["file"])
    assert inp["register_sha256"] == sha(RC.OI.REGISTER_JSON) and inp["archive_json_sha256"] == sha(RC.OI.ARCHIVE_JSON)
    assert "STERK_VISUEEL_ONAFHANKELIJK_TOESTEL_EN_HOEK" in P.EVIDENCE_VERIFICATION_JSON.read_text(encoding="utf-8")     # PR #42-verslag niet overschreven
    assert "folie met plakstrook rechts" in P.EVIDENCE_VERIFICATION_JSON.read_text(encoding="utf-8")


def test_features_are_classified_and_the_strip_is_not_verifiable_in_map009():
    f = {x["id"]: x for x in REC["features"]}
    assert set(x["class"] for x in f.values()) <= set(RC.CLASSES)
    assert f["F5"]["class"] == "NOT_VERIFIABLE" and f["F5"]["m9"] is None
    assert f["F4"]["in_vr045_crop"] is False and f["F1"]["in_vr045_crop"] is True and f["F2"]["in_vr045_crop"] is True
    assert any("PR #42" in c and "plakstrook" in c.lower() for c in REC["corrections_to_pr42_text"])
    assert REC["neighbour_and_swap_check"]["counter_example"].startswith("MAP-007") and "residual_risk" in REC["neighbour_and_swap_check"]


def test_no_fabricated_identifications_bag_dimensions_counts_or_costs():
    blob = json.dumps(REC)
    assert "FI-" not in blob and "BAG:" not in blob and "0363100012" not in blob and "bag_pand_id" not in blob
    assert not P.FI_PATTERN.search(blob)


def test_markdown_report_is_generated_from_the_record_and_deterministic():
    md = RC.render_md(REC)
    assert md == RC.OUT_MD.read_text(encoding="utf-8") and RC.render_md(REC) == md
    for needle in ("COMPATIBLE_DIFFERENT_SCOPE", "Vergelijkingstabel", "Correctie op PR #42", "STOP", "REF-MAP009-006", "NOT_VERIFIABLE"):
        assert needle in md
    assert md.count("| ") > 40


def test_script_writes_only_its_own_outputs():
    src = (ROOT / "scripts/physical_instance_evidence_reconciliation.py").read_text(encoding="utf-8")
    assert src.count(".write_text(") == 2 and "OUT_JSON.write_text" in src and "OUT_MD.write_text" in src and src.count("cv2.imwrite") == 2
    for bad in ("REGISTER_JSON.write", "ARCHIVE_JSON.write", "unlink", "shutil", "os.remove", "frame_instance"):
        assert bad not in src


# ---------------------------------------------------------------- aanvraag, hash en reviewpakket
def test_request_carries_the_reconciliation_and_the_corrected_claim():
    r = ev()
    assert r["approval_status"] == "READY_FOR_HUMAN_REVIEW" and r["evidence_reconciliation"] == P.reconciliation_summary(CTX)
    s = r["evidence_reconciliation"]
    assert s["outcome"] == "COMPATIBLE_DIFFERENT_SCOPE" and s["is_human_decision"] is False and s["vr045_human_decision"] is None
    assert s["map009_role"] == "ADDITIONAL_EVIDENCE_NOT_RELIED_ON" and s["oic_depends_on_map009"] is False and s["features"]["F5"] == "NOT_VERIFIABLE"
    args = " ".join(a for m in r["additional_evidence"] for a in m["arguments"])
    assert "folie met plakstrook rechts" not in args and "niet verifieerbaar" in args
    assert "C11" in [c["id"] for c in r["validation_results"]["checks"]] and "C11" not in r["validation_results"]["blocked_by"]


def test_required_uncertainties_stay_visible_in_the_request():
    r = ev()
    q = " ".join(r["unresolved_questions"] + r["derived_open_questions"])
    for needle in ("MEDIUM", "STRONG", "dezelfde dag", "tijdelijk", "identieke woningen", "BAG-pand", "geen instance-besluit", "VR-045", "APP-012", "APP-025", "COMPATIBLE_DIFFERENT_SCOPE", "plakstrook"):
        assert needle in q or needle.lower() in q.lower(), needle
    assert all(a["status"] == "OPEN" for a in CTX["app_decisions"].values()) and len(CTX["app_decisions"]) == 48
    assert r["relation_strength_in_source"] == "MEDIUM" and r["evidence_class"] == "STRONG_VISUAL_SUPPORT"          # twee afzonderlijke bronbeoordelingen
    assert r["human_decision"] is None and r["is_instance"] is False and r["approval_status"] != "APPROVED_FOR_ACTIVATION"
    assert not any(t == "APPROVED_FOR_ACTIVATION" for t in P.TRANSITIONS["DRAFT"] + P.TRANSITIONS["NEEDS_MORE_EVIDENCE"])


def test_hash_changed_and_old_hash_is_marked_stale_without_any_decision():
    assert BASE["request_hash"] == REP["draft_request"]["request_hash"] != "aa556297be5d6713d298a06fa40492b8"
    assert BASE["superseded_request_hashes"] == ["aa556297be5d6713d298a06fa40492b8"] and REP["evidence_reconciliation"]["stale_request_hashes"] == ["aa556297be5d6713d298a06fa40492b8"]
    assert CTX["human_approvals"] == [] and REP["draft_request"]["human_decision"] is None
    r = copy.deepcopy(BASE)
    r["superseded_request_hashes"].append(r["request_hash"])
    assert ev(r)["approval_status"] == "REJECTED"
    # een besluit op de verouderde hash werkt niet
    ready = ev()
    rec = {"decision_id": "IAD-T", "request_id": ready["approval_request_id"], "request_hash": "aa556297be5d6713d298a06fa40492b8", "decision": "APPROVE_PHYSICAL_IDENTITY", "level": "A", "covers_levels": ["A"],
           "decided_by": "Test Beslisser", "decision_source": "HUMAN", "statement": "Synthetische testverklaring.", "acknowledged_app_decisions": ["APP-012", "APP-025"]}
    assert P.transition(ctx_copy(human_approvals=[rec]), ready, "APPROVED_FOR_ACTIVATION", rec)["ok"] is False


def test_request_record_and_static_review_pack_state_the_same_claims():
    html = P.PACK_HTML.read_text(encoding="utf-8")
    esc = PR.html.escape
    r = REP["draft_request"]
    assert r["request_hash"] in html and r["evidence_reconciliation"]["outcome"] in html and r["evidence_reconciliation"]["map009_role"] in html
    for q in r["unresolved_questions"] + r["derived_open_questions"]:
        assert esc(q) in html, q[:60]
    for f in REC["features"]:
        assert f["id"] in html and f["class"] in html
    for a in r["additional_evidence"][0]["arguments"]:
        assert esc(a) in html
    for h in REP["evidence_reconciliation"]["stale_request_hashes"]:
        assert h in html
    for k, v in r["decision_levels"].items():
        assert v["status"] == "NOT_DECIDED"
    assert "RC-crop_scope.jpg" in html and "RC-feature_comparison.jpg" in html and "niet ingevuld, niet geregistreerd en zonder werking" in html
    md = P.OUT_MD.read_text(encoding="utf-8")
    assert "6b. Bewijsverzoening" in md and "COMPATIBLE_DIFFERENT_SCOPE" in md


# ---------------------------------------------------------------- C11 faalt gesloten
def test_c11_missing_or_corrupt_reconciliation_blocks():
    for bad in (None, {}, [], "x", {"outcome": "ZOMAAR"}, {**REC, "outcome": "NIETS"}):
        out = ev(ctx=ctx_copy(reconciliation=bad))
        assert out["approval_status"] == "REJECTED" and "C11" in out["validation_results"]["blocked_by"], bad
    c = ctx_copy()
    del c["reconciliation"]
    assert ev(ctx=c)["approval_status"] == "REJECTED"


@pytest.mark.parametrize("mut", ["modified", "decision", "oic", "instances"])
def test_c11_record_claiming_changes_blocks(mut):
    c = ctx_copy()
    rec = c["reconciliation"]
    if mut == "modified":
        rec["effects"]["vr045_modified"] = True
    elif mut == "decision":
        rec["effects"]["human_decisions_created"] = 1
    elif mut == "oic":
        rec["consequences_for_iar_oic_vr_027"]["oic_depends_on_map009"] = True
    else:
        rec["effects"]["instances_created"] = 1
    assert ev(ctx=c)["approval_status"] == "REJECTED"


def test_c11_request_that_misstates_the_reconciliation_is_blocked_or_stale():
    for mutate in (lambda s: s.update(outcome="GENUINE_EVIDENCE_CONFLICT"), lambda s: s.update(is_human_decision=True), lambda s: s.update(vr045_human_decision="SAME"),
                   lambda s: s.update(map009_role="PRIMARY_EVIDENCE"), lambda s: s["features"].update(F5="DIRECTLY_VISIBLE"), lambda s: s.update(record_sha256="0" * 64)):
        r = copy.deepcopy(BASE)
        mutate(r["evidence_reconciliation"])
        out = ev(rehash(r))
        assert out["approval_status"] == "REJECTED" and "C11" in out["validation_results"]["blocked_by"]
    assert ev(copy.deepcopy(BASE))["approval_status"] == "READY_FOR_HUMAN_REVIEW"      # positieve controle: ongewijzigd blijft geldig


def test_c11_a_later_human_decision_on_vr045_makes_the_request_stale_not_approved():
    c = ctx_copy()
    c["decisions"]["RV-REL-VR-045"] = {"review_id": "RV-REL-VR-045", "decision": "SAME", "provenance": {"decision_source": "HUMAN"}}
    out = ev(ctx=c)
    assert out["approval_status"] == "NEEDS_MORE_EVIDENCE" and "C11" in out["validation_results"]["needs_evidence_by"]


def test_other_outcomes_do_not_make_map009_a_requirement():
    for outcome in ("GENUINE_EVIDENCE_CONFLICT", "INSUFFICIENT_TO_RECONCILE"):
        c = ctx_copy()
        c["reconciliation"]["outcome"] = outcome
        c["reconciliation_sha256"] = "1" * 64
        r = P.build_request(c, "OIC-VR-027")
        out = P.evaluate_request(c, r)
        assert out["evidence_reconciliation"]["outcome"] == outcome and out["approval_status"] != "APPROVED_FOR_ACTIVATION"
        assert out["evidence_reconciliation"]["oic_depends_on_map009"] is False
