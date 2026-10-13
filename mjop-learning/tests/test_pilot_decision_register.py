import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import register_pilot_decisions as R  # noqa: E402

BASE = ROOT / "reports/frames/photo_review_map003_map004_v1"
PACK = R.load_pack()
SRC = json.loads(R.SRC.read_text(encoding="utf-8"))
REG = json.loads(R.OUT_JSON.read_text(encoding="utf-8"))
EXPECTED = {
    "RV-SEP-001": "CONFIRM", "RV-REL-VR-027": "SAME", "RV-REL-VR-020": "SAME", "RV-REL-VR-024": "UNDECIDABLE",
    "RV-REL-VR-026": "UNDECIDABLE", "RV-OBS-MAP004-012": "CONFIRM", "RV-OBS-MAP003-027": "NEEDS_BETTER_PHOTO",
    "RV-OBS-MAP003-009": "UNDECIDABLE", "RV-OBS-MAP003-010": "CONFIRM", "HQ-VR-001": "CONFIRM",
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_source_validates_against_pack():
    assert R.validate(SRC, PACK) == []


def test_register_has_exactly_the_ten_confirmed_decisions():
    assert {r["review_id"]: r["decision"] for r in REG["decisions"]} == EXPECTED
    assert REG["decision_count"] == 10
    assert all(r["source_ref_hash_validated"] for r in REG["decisions"])


def test_register_is_reproducible_from_source():
    assert R.build_register(SRC, PACK) == REG


def test_provenance_is_chat_not_html():
    assert REG["approval"]["channel"] == "ChatGPT conversation"
    assert REG["approval"]["via_html_form"] is False and REG["approval"]["is_html_export"] is False
    assert REG["approval"]["source_file_sha256"] == sha(R.SRC)
    for r in REG["decisions"]:
        p = r["provenance"]
        assert p["decision_source"] == "HUMAN_CHAT_CONFIRMATION" and p["via_html_form"] is False and p["is_html_export"] is False
    assert REG["format"] != "maldenhof_visual_decision_export_v2"


def test_facade_section_vs_physical_object_kept_apart():
    lab = {r["review_id"]: r["decision_label"] for r in REG["decisions"]}
    assert lab["RV-REL-VR-020"] == "SAME_FACADE_SECTION"
    assert lab["RV-REL-VR-027"] == "SAME_PHYSICAL_OBJECT_CANDIDATE"
    assert all(r["never"]["same_physical_frame_proven"] is False for r in REG["decisions"])


def test_nothing_else_decided_or_authorized():
    assert REG["other_review_points_open"] == len(PACK["items"]) - 10 == 113
    assert REG["existing_app_decisions_open_unchanged"] == 48
    assert not any(REG["authorized"].values())
    for r in REG["decisions"]:
        assert not any(r["never"].values())
    c = REG["separate_correction_proposal"]
    assert c["status"] == "PROPOSED_NOT_APPLIED" and c["approved"] is False
    # de pack zelf bevat geen menselijke besluiten
    assert not any(i.get("human") for i in PACK["items"])


def test_source_observations_and_approval_doc_untouched():
    assert sha(BASE / "maldenhof_visual_photo_review_map003_map004_v1.json") == "28cccaf2eccfc82aa871b6a66c342043112406fb127d044ddf1f1051703e0719"
    assert sha(BASE / "maldenhof_visual_photo_review_map003_map004_v1.md") == "18e3aa8b7ec5083f1641e7160cc7993c97e166e0b63e2c056d95daac53107ff8"
    assert sha(ROOT / "scripts/visual_review_map003_map004_data.py") == "560931f95ab58dfcd0dbedd4e57edac4cba66afec1f64eee82ba90a2c202c176"
    doc = ROOT / "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md"
    assert doc.read_text(encoding="utf-8").count("OPEN") >= 48


def mutate(fn):
    s = copy.deepcopy(SRC)
    fn(s)
    return R.validate(s, PACK)


@pytest.mark.parametrize("fn,frag", [
    (lambda s: s["pilot_decisions"][0].update(source_ref_hash="0" * 16), "hash"),
    (lambda s: s["pilot_decisions"][0].update(review_id="RV-NIET-BESTAAND"), "onbekend"),
    (lambda s: s["pilot_decisions"][0].update(decision="SAME"), "keuze"),
    (lambda s: s["pilot_decisions"][1].update(review_id="RV-SEP-001"), "dubbel"),
    (lambda s: s["pilot_decisions"][0].update(approval_scope="ALL"), "herkomst"),
    (lambda s: s["pilot_decisions"][0].update(approval_provenance="HTML_FORM"), "herkomst"),
    (lambda s: s.update(apply_to_instances_authorized=True), "onbevoegd"),
    (lambda s: s.update(merges_authorized=True), "onbevoegd"),
    (lambda s: s.update(bag_links_authorized=True), "onbevoegd"),
    (lambda s: s.update(costs_authorized=True), "onbevoegd"),
    (lambda s: s["pilot_decisions"].pop(), "aantal"),
    (lambda s: s.update(pack_version="human_visual_decision_pack_v1.1.0"), "pack_version"),
    (lambda s: s.update(format="maldenhof_visual_decision_export_v2"), "format"),
])
def test_unauthorized_or_inconsistent_input_is_rejected(fn, frag):
    errs = mutate(fn)
    assert errs and any(frag in e for e in errs), errs


def test_non_pilot_review_point_is_rejected():
    non_pilot = next(i for i in PACK["items"] if not i.get("pilot"))
    errs = mutate(lambda s: s["pilot_decisions"][0].update(review_id=non_pilot["review_id"], source_ref_hash=non_pilot["ref_hash"],
                                                           decision=non_pilot["choices"][0]))
    assert any("geen pilotpunt" in e for e in errs)
