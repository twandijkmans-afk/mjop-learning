import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_app_component_inventory as ex  # noqa: E402

BUNDLES = ROOT / "reports/inventory/app_bundles"
M = json.loads((BUNDLES / "maldenhof_component_inventory_v1.json").read_text())
D = json.loads((BUNDLES / "doc012_component_inventory_v1.json").read_text())
REQS = json.loads((ROOT / "vocabularies/app_element_requirements_v1.json").read_text())


def comp(b, t):
    return next(c for c in b["components"] if c["component_type"] == t)


def req(b, k):
    return next(r for r in b["maintenance_requirements"] if r["app_element_id"] == k)


def test_check_mode_current_and_deterministic():
    r = subprocess.run([sys.executable, str(ROOT / "scripts/export_app_component_inventory.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    assert ex.render_all() == ex.render_all()


def test_no_scores_or_confidence():
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k.lower()
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    bad = [k for k in keys([M, D]) if any(w in k for w in ("confidence", "score", "probability", "percent"))]
    assert not bad


def test_every_requirement_and_component_exported():
    ids = {r["app_element_key"] for r in REQS["requirements"]}
    for b in (M, D):
        assert {r["app_element_id"] for r in b["maintenance_requirements"]} == ids
        assert len(b["components"]) == 22
        assert {c["status"] for c in b["components"]} <= {"PRESENT", "ABSENT", "UNKNOWN"}


def test_unknown_is_not_absent_and_proposed_absent_not_silent():
    assert comp(M, "LIFT_INSTALLATION")["status"] == "UNKNOWN"
    assert req(M, "lift")["inventory_result"] == "NEEDS_CONFIRMATION"
    sloped = comp(D, "ROOF_SLOPED_COVERING")
    assert sloped["presence_basis"] == "PROPOSED_ABSENT_NOT_DECIDED" and sloped["status"] == "UNKNOWN"
    assert req(D, "dak-hellend")["inventory_result"] == "NEEDS_CONFIRMATION"
    for b in (M, D):
        assert not any(c["status"] == "ABSENT" for c in b["components"])
        assert not any(r["inventory_result"] == "NOT_APPLICABLE" for r in b["maintenance_requirements"])


def test_present_applicable_and_rule_engine():
    assert req(M, "dak-plat")["inventory_result"] == "APPLICABLE"
    assert req(D, "lift")["inventory_result"] == "APPLICABLE"
    r_all = next(r for r in REQS["requirements"] if r["app_element_key"] == "lift")
    assert ex.requirement_result(r_all, {"LIFT_INSTALLATION": "ABSENT"}, {})[0] == "NOT_APPLICABLE"
    assert ex.requirement_result(r_all, {"LIFT_INSTALLATION": "UNKNOWN"}, {})[0] == "NEEDS_CONFIRMATION"
    assert ex.requirement_result(r_all, {"LIFT_INSTALLATION": "PRESENT"}, {})[0] == "APPLICABLE"
    r_any = next(r for r in REQS["requirements"] if r["app_element_key"] == "dakinspectie")
    assert ex.requirement_result(r_any, {"ROOF_FLAT_COVERING": "ABSENT", "ROOF_SLOPED_COVERING": "ABSENT"}, {})[0] == "NOT_APPLICABLE"
    assert ex.requirement_result(r_any, {"ROOF_FLAT_COVERING": "ABSENT", "ROOF_SLOPED_COVERING": "UNKNOWN"}, {})[0] == "NEEDS_CONFIRMATION"
    assert ex.requirement_result(r_any, {"ROOF_FLAT_COVERING": "ABSENT", "ROOF_SLOPED_COVERING": "PRESENT"}, {})[0] == "APPLICABLE"


def test_non_presence_driven_items():
    for b in (M, D):
        assert req(b, "steiger")["inventory_result"] == "NOT_PRESENCE_DRIVEN"
        assert req(b, "dakisolatie")["inventory_result"] == "USER_SELECTED"
        assert req(b, "dakisolatie")["classification"] == "OPTIONAL_IMPROVEMENT"
        assert req(b, "schilderwerk-buiten")["inventory_result"] == "NEEDS_ATTRIBUTE_CONFIRMATION"


def test_maldenhof_exterior_frame():
    f = comp(M, "EXTERIOR_FRAME")
    assert (f["status"], f["decision_ref"], f["material_as_reported"], f["material_basis"]) == (
        "PRESENT", "CPD-00001", "hout", "SOURCE_REPORTED_BUILDING_LEVEL")
    assert f["presence_basis"] == "HUMAN_DECISION" and f["user_confirmed"] is False
    assert req(M, "kozijnen-onderhoud")["inventory_result"] == "APPLICABLE"
    assert comp(D, "EXTERIOR_FRAME")["decision_ref"] == "CPD-00002"


def test_maldenhof_photo_visible_vs_building_totals():
    fs = M["frame_status"]
    pv = fs["photo_visible_evidence"]
    assert (pv["PHOTO_VISIBLE_FRAME_COUNT"], pv["PHOTO_VISIBLE_WINDOW_COUNT"], pv["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"]) == (11, 11, 1)
    assert pv["is_building_total"] is False and pv["count_basis"] == "PHOTO_VISIBLE_CONFIRMED_COUNT"
    for t in fs["building_totals"].values():
        assert t == {"status": "UNKNOWN", "value": None}
    assert fs["repeat_groups"] == "NOT_ACTIVE" and fs["quantity_resolution"] == "NOT_WRITTEN"
    assert D["frame_status"]["photo_visible_evidence"] is None


def test_historical_756_80_not_comparable():
    h = M["frame_status"]["historical_reported_quantity_context"]
    assert {x["quantity_value"] for x in h} == {"756.80"}
    for x in h:
        assert x["interpretation"] == "HISTORICAL_REPORTED_QUANTITY_CONTEXT" and x["comparability_to_frame_count"] == "NOT_COMPARABLE"
        assert "FRAME_COUNT" in x["not_interpreted_as"]


def test_legacy_fallback_labelled_and_source_priority():
    for b in (M, D):
        lef = b["frame_status"]["legacy_estimate_fallback"]
        assert lef["ui_label_nl"] == "Schatting op basis van aantal appartementen" and lef["classification"] == "LEGACY_ESTIMATE_FALLBACK"
        assert req(b, "kozijnen-onderhoud")["legacy_estimate_fallback_id"] == lef["fallback_id"]
        assert b["frame_status"]["source_priority"] == ["USER_CONFIRMED_MANUAL", "DRAWING_MEASURED", "USER_ASSISTED_PHOTO",
                                                         "SOURCE_REPORTED_HISTORICAL", "LEGACY_ESTIMATE_FALLBACK"]
        assert "zelfde" in b["frame_status"]["source_priority_scope"].lower() or "EXACT" in b["frame_status"]["source_priority_scope"]


def test_official_kengetallen_and_resolutions_unchanged():
    sha = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()  # noqa: E731
    assert sha("data/kengetallen/kengetallen_batch1.json") == "e8b9b2260fb681da242817e51dfdb5ca3b1ab3ec1e3e5dcd6b56d3cc71761897"
    assert sha("data/kentallen/kentallen_batch1.json") == "c9d5a5d64a5795b20f25ba0688cd05194e44141a2bb8113f27c35fc0ef179f02"
    assert json.loads((ROOT / "data/quantity_resolutions/quantity_resolution_records.json").read_text())["records"] == []
    assert M["policy"]["prices"] == "NOT_CHANGED" and M["policy"]["quantity_resolutions"] == "NOT_WRITTEN"
