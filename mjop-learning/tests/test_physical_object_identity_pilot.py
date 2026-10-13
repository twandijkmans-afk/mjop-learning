import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import object_identity_pilot as OI  # noqa: E402

CTX = OI.load_context()
REP = json.loads(OI.OUT_JSON.read_text(encoding="utf-8"))
FALSE_FLAGS = ("is_instance", "counts_in_any_total", "merged", "same_physical_frame_proven")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ctx_copy():
    return copy.deepcopy(CTX)


def test_vr027_gives_one_supported_candidate_from_existing_evidence_only():
    assert len(REP["candidates"]) == 1
    c = REP["candidates"][0]
    assert c["candidate_group_id"] == "OIC-VR-027" and c["identity_status"] == "SUPPORTED_CANDIDATE"
    assert c["observation_ids"] == ["OBS-MAP003-011", "OBS-MAP004-006"] and c["supporting_relation_ids"] == ["VR-027"]
    assert c["source_hashes"] == {"MAP-003": CTX["observations"]["OBS-MAP003-011"]["source_sha256"], "MAP-004": CTX["observations"]["OBS-MAP004-006"]["source_sha256"]}
    assert {e["type"] for e in c["evidence_refs"]} >= {"original_crop", "feature_match_support_only"}
    assert c["unresolved_questions"]


def test_pilot_decision_is_read_as_candidate_evidence_not_permission():
    c = REP["candidates"][0]
    d = c["decision_refs"][0]
    assert d["review_id"] == "RV-REL-VR-027" and d["decision"] == "SAME" and d["decision_label"] == "SAME_PHYSICAL_OBJECT_CANDIDATE"
    assert d["source_ref_hash"] == CTX["pack"]["RV-REL-VR-027"]["ref_hash"] and d["decision_source"] == "HUMAN_CHAT_CONFIRMATION"
    assert "niet bewezen" in d["meaning"] and "niet samengevoegd" in d["meaning"]


def test_candidate_never_becomes_instance_merge_pand_or_count():
    c = REP["candidates"][0]
    assert all(c[k] is False for k in FALSE_FLAGS)
    assert c["bag_pand_id"] is None and c["frame_instance_id"] is None and c["quantity"] is None and c["cost"] is None
    e = REP["effects"]
    assert e["instances_created"] == e["bag_links_created"] == e["merges"] == e["new_observations"] == e["human_decisions_changed"] == e["app_decisions_changed"] == 0
    assert e["building_totals"] is None and e["quantities"] is None and e["costs"] is None and e["definitive_instance_transition_exists"] is False
    assert "NOOIT_AUTOMATISCH" in OI.TRANSITIONS


def test_frozen_stores_and_decisions_unchanged_and_no_oic_leak():
    assert sha(ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json") == "b18c36eb4c21abcb25bb9ff2162fcfd06a164b3f9e490aa11af858ef33b02378"
    assert sha(ROOT / "data/frame_inventory/component_repeat_groups_v1.json") == "4fa2f5bb37d049c4c4614d28097a396d8a4aff324a82b76cf5f66610601b7b49"
    assert sha(ROOT / "data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json") == "520e5e11f8a7b8600c8a03d4b93afb452fd8d0c9da14d5c729a8f5cae1a36e9d"
    inst = (ROOT / "data/frame_inventory/maldenhof_photo_frame_instances_v1.json").read_text(encoding="utf-8")
    assert "OIC-" not in inst
    for p in (ROOT / "data").rglob("*.json"):
        assert "OIC-VR" not in p.read_text(encoding="utf-8", errors="ignore"), p
    reg = json.loads(OI.REGISTER_JSON.read_text(encoding="utf-8"))
    assert {d["review_id"]: d["decision"] for d in reg["decisions"]}["RV-REL-VR-027"] == "SAME" and reg["decision_count"] == 10


def test_facade_section_same_cannot_create_object_identity():
    ev = OI.evaluate_relation(CTX, "VR-020")
    assert CTX["decisions"]["RV-REL-VR-020"]["decision"] == "SAME"
    assert ev["identity_status"] == "REJECTED" and not ev["creates_identity_link"] and any("GEVELSECTIE" in r for r in ev["reasons"])
    assert not OI.evaluate_relation(CTX, "VR-020", "SAME")["creates_identity_link"]


@pytest.mark.parametrize("rid", ["VR-024", "VR-026"])
def test_undecidable_relations_create_no_link_even_if_hypothetically_same(rid):
    assert CTX["decisions"]["RV-REL-" + rid]["decision"] == "UNDECIDABLE"
    assert OI.evaluate_relation(CTX, rid)["identity_status"] == "UNRESOLVED"
    hyp = OI.evaluate_relation(CTX, rid, "SAME")
    assert not hyp["creates_identity_link"] and hyp["identity_status"] == "UNRESOLVED"


def test_repeating_houses_look_alike_is_insufficient():
    # zonder onderscheidend anker en/of met herhalingsrisico nooit SUPPORTED
    for rid, q in CTX["quality"].items():
        if q["review_type"] != "OVERLAP_RELATION" or q["relation_type"] != "PHYSICAL_OBJECT":
            continue
        ev = OI.evaluate_relation(CTX, rid.replace("RV-REL-", ""), "SAME")
        basis = set(q["evidence_basis"])
        if ev["identity_status"] == "SUPPORTED_CANDIDATE":
            assert basis & OI.ANCHORS and not basis & OI.BLOCKING_BASIS and q["evidence_class"] == "STRONG_VISUAL_SUPPORT", rid
        if basis & OI.BLOCKING_BASIS:
            assert not ev["creates_identity_link"], rid
    only_similarity = ctx_copy()
    only_similarity["quality"]["RV-REL-VR-027"]["evidence_basis"] = ["SAME_LAYOUT", "FEATURE_MATCH"]
    assert OI.evaluate_relation(only_similarity, "VR-027")["identity_status"] == "CANDIDATE"
    with_repetition = ctx_copy()
    with_repetition["quality"]["RV-REL-VR-027"]["evidence_basis"] = ["UNIQUE_CONFIGURATION", "REPETITION_RISK"]
    assert not OI.evaluate_relation(with_repetition, "VR-027")["creates_identity_link"]
    assert REP["repetition_risk"]["best_non_partner_inliers_vr027"] >= 20


def _pairs(*p):
    return [{"observation_ids": list(x), "identity_status": "SUPPORTED_CANDIDATE"} for x in p]


def test_identity_is_not_transitive():
    r = OI.resolve_groups(_pairs(("A", "B"), ("B", "C")))
    assert r["groups"] == [] and r["chains"][0]["status"] == "UNRESOLVED_CHAIN" and r["chains"][0]["missing_direct_pairs"] == [["A", "C"]]
    assert r["chains"][0]["transitive_merge_performed"] is False
    assert OI.resolve_groups(_pairs(("A", "B"), ("B", "C"), ("A", "C")))["groups"] == [["A", "B", "C"]]
    assert OI.resolve_groups(_pairs(("A", "B"), ("C", "D")))["groups"] == [["A", "B"], ["C", "D"]]
    weak = [{"observation_ids": ["A", "B"], "identity_status": "SUPPORTED_CANDIDATE"}, {"observation_ids": ["B", "C"], "identity_status": "CANDIDATE"}]
    assert OI.resolve_groups(weak)["groups"] == [["A", "B"]]


def test_wrong_or_missing_references_are_refused():
    assert OI.evaluate_relation(CTX, "VR-999")["identity_status"] == "REJECTED"
    c = ctx_copy()
    c["relations"]["VR-027"]["left"] = "MAP-003:OBS-MAP003-999"
    assert any("ONBEKENDE_OBSERVATIE" in r for r in OI.evaluate_relation(c, "VR-027")["reasons"])
    c = ctx_copy()
    c["photo_sha"]["MAP-003"] = "0" * 64
    assert any("BRONHASH" in r for r in OI.evaluate_relation(c, "VR-027")["reasons"])
    c = ctx_copy()
    del c["pack"]["RV-REL-VR-027"]
    assert any("ONTBREKENDE_BRONVERWIJZING" in r for r in OI.evaluate_relation(c, "VR-027")["reasons"])
    c = ctx_copy()
    del c["quality"]["RV-REL-VR-027"]
    assert not OI.evaluate_relation(c, "VR-027")["creates_identity_link"]
    c = ctx_copy()
    c["decisions"]["RV-REL-VR-027"]["source_ref_hash"] = "0" * 16
    assert OI.evaluate_relation(c, "VR-027")["identity_status"] == "REJECTED"
    c = ctx_copy()
    del c["decisions"]["RV-REL-VR-027"]
    ev = OI.evaluate_relation(c, "VR-027")
    assert ev["identity_status"] == "CANDIDATE"     # zonder menselijk besluit nooit SUPPORTED
    c = ctx_copy()
    c["decisions"]["RV-REL-VR-027"]["decision"] = "DIFFERENT"
    assert OI.evaluate_relation(c, "VR-027")["identity_status"] == "REJECTED"


def test_relations_with_group_or_frozen_photo2_endpoints_are_refused():
    for rid, rel in CTX["relations"].items():
        ev = OI.evaluate_relation(CTX, rid, "SAME")
        eps = rel["left"] + rel["right"]
        if "/" in eps or "FC-M2" in eps or "FI-M2" in eps:
            assert not ev["creates_identity_link"], rid


def test_two_observations_in_one_photo_cannot_be_the_same_object():
    c = ctx_copy()
    a, b = [o["obs_id"] for o in CTX["observations"].values() if o["photo_id"] == "MAP-003"][:2]
    c["relations"]["VR-X"] = {"rel_id": "VR-X", "left": "MAP-003:" + a, "right": "MAP-003:" + b, "class": "POSSIBLY_SAME_PHYSICAL_FRAME", "strength": "MEDIUM"}
    c["pack"]["RV-REL-VR-X"] = c["pack"]["RV-REL-VR-027"]
    c["quality"]["RV-REL-VR-X"] = c["quality"]["RV-REL-VR-027"]
    assert not OI.evaluate_relation(c, "VR-X", "SAME")["creates_identity_link"]


def test_negative_controls_all_pass_in_committed_report():
    assert [k["control"] for k in REP["negative_controls"]] == ["A", "B", "C", "C2", "D1", "D2", "D3", "E", "E2", "F"]
    assert all(k["passed"] for k in REP["negative_controls"])


def test_status_model_is_complete_and_has_no_instance_transition():
    assert set(OI.STATUS_MODEL) == set(OI.STATUSES)
    for m in OI.STATUS_MODEL.values():
        assert m["voorwaarden"] and m["beslissing_nodig"] and m["toegestaan"] and m["verboden"]
    assert all(s in OI.STATUSES for tgt in OI.TRANSITIONS.values() if isinstance(tgt, list) for s in tgt)
    assert OI.TRANSITIONS["REJECTED"] == []


def test_output_is_deterministic_and_matches_committed_files():
    a, b = OI.build_report(), OI.build_report()
    assert a == b
    assert json.dumps(a, ensure_ascii=False, indent=2, sort_keys=True) + "\n" == OI.OUT_JSON.read_text(encoding="utf-8")
    assert OI.render_md(a, CTX) == OI.OUT_MD.read_text(encoding="utf-8")
    assert a["inputs"]["review_json_sha256"] == sha(OI.REVIEW_JSON) and a["inputs"]["register_sha256"] == sha(OI.REGISTER_JSON)


def test_pilot_does_not_modify_its_sources():
    before = {p: sha(p) for p in (OI.REVIEW_JSON, OI.QUALITY_JSON, OI.EVIDENCE_JSON, OI.REGISTER_JSON)}
    OI.build_report()
    assert before == {p: sha(p) for p in before}
    assert sha(OI.REVIEW_JSON) == "28cccaf2eccfc82aa871b6a66c342043112406fb127d044ddf1f1051703e0719"


# --- regressietests uit de onafhankelijke bewijscontrole (concrete tekortkomingen) ---

@pytest.mark.parametrize("mutate", [
    lambda d: d["provenance"].update(decision_source="CLAUDE_PROPOSAL"),
    lambda d: d["provenance"].update(decision_source="NONE"),
    lambda d: d.pop("provenance"),
    lambda d: d.update(source_ref_hash_validated=False),
    lambda d: d.update(decision="MAYBE"),
    lambda d: d.update(decision="CONFIRM"),     # geen geldige keuze voor een overlaprelatie
])
def test_invalid_or_non_human_register_decision_is_never_treated_as_approval(mutate):
    c = ctx_copy()
    mutate(c["decisions"]["RV-REL-VR-027"])
    ev = OI.evaluate_relation(c, "VR-027")
    assert ev["identity_status"] != "SUPPORTED_CANDIDATE"
    assert ev["identity_status"] == "CANDIDATE" and "ONGELDIG_OF_NIET_MENSELIJK_BESLUIT_GENEGEERD" in ev["reasons"]
    assert ev["_decision"] is None and OI.to_candidate(c, ev)["decision_refs"] == []


def test_source_hash_is_also_checked_against_the_independent_archive_register():
    c = ctx_copy()
    c["archive_sha"]["MAP-004"] = "0" * 64
    ev = OI.evaluate_relation(c, "VR-027")
    assert ev["identity_status"] == "REJECTED" and any("BRONHASH" in r for r in ev["reasons"])
    c = ctx_copy()
    del c["archive_sha"]["MAP-003"]
    assert not OI.evaluate_relation(c, "VR-027")["creates_identity_link"]
    assert CTX["archive_sha"]["MAP-003"] == CTX["observations"]["OBS-MAP003-011"]["source_sha256"]


def test_relation_type_must_agree_between_review_json_and_decision_pack():
    c = ctx_copy()
    c["relations"]["VR-027"]["class"] = "SAME_FACADE_SECTION"        # JSON zegt gevelsectie, pack zegt object
    ev = OI.evaluate_relation(c, "VR-027")
    assert ev["identity_status"] == "REJECTED" and any("RELATIETYPE_INCONSISTENT" in r for r in ev["reasons"])
    c = ctx_copy()
    c["relations"]["VR-020"]["class"] = "POSSIBLY_SAME_PHYSICAL_FRAME"   # omgekeerd: pack zegt gevelsectie
    assert not OI.evaluate_relation(c, "VR-020", "SAME")["creates_identity_link"]
