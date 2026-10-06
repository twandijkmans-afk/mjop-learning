"""Tests voor Building Element Inventory Foundation v1.

Presence is een ander concept dan quantity. Read-only: mutaties gebeuren op kopieën in het geheugen; er worden geen
besluiten, resoluties, bundels of prijzen geschreven.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal

import jsonschema
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import append_only_store as aos  # noqa: E402
import bag3d_quantity_rules as rules_mod  # noqa: E402
import build_component_inventory as bci  # noqa: E402
import building_element_inventory_report as rep_mod  # noqa: E402
import component_presence as cp  # noqa: E402

BUNDLES = os.path.join(ROOT, "reports", "quantity", "app_bundles")
OLD_HASHES = {
    "reports/quantity/app_bundles/doc012_geometry_v3.json": "fe12a4eb7999f784056d46a607e5e37b6223fc30a6eff0c4c86924390f074a87",
    "reports/quantity/app_bundles/doc012_meppelweg_v3.json": "748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191",
    "reports/quantity/app_bundles/maldenhof_DOC-005_DOC-006_v3.json": "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933",
    "reports/quantity/app_bundles/maldenhof_expanded_v3.json": "c78f387e66ce7963d7a434270350f0ee8fa4c9f232099f871e83ed202cd2975d",
    "reports/quantity/app_bundles/maldenhof_geometry_expanded_v3.json": "8264bdceb2c0ee633333b79ac6a073f8c9ea48661659007f69ff22df391a52ca",
    "data/quantity_evidence/building_quantity_evidence_v1.json": "216b2625e2082f2503a764b5d951737e493e9afbd2b494e33fda7e1ee9f3ac1b",
    "data/quantity_resolutions/quantity_resolution_records.json": "73501e9e40da13a8ae8d338665189675a03bf85869d51715e422744e0d02328c",
    "data/crosswalk_decisions/crosswalk_decision_records.json": "bbd2872cf038c6e5e60a0d2a0d44f994831b5c2694c6319d36d1532e05084114",
    "data/building_links/building_link_records.json": "400d368ee91d9353a12846bf089a3d3f17efb926b9fcac7c4d9ba7f86230cd47",
    "data/quantity_observations/quantity_observations_v1.json": "3be69bd3e6dfa5f4bf31c75227684b56e944b4a9f448f4cf470d36b9f3939bd3",
}
DOC012_PAND = "0518100000354752"
FRAME_SUBJECTS = ("FRAME", "WINDOW", "OPENING")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture(scope="module")
def built():
    return bci.build()


@pytest.fixture(scope="module")
def evidence(built):
    return built["evidence_store"]["evidence"]


@pytest.fixture(scope="module")
def inventory(built):
    return built["inventory"]


@pytest.fixture(scope="module")
def comp():
    return load(cp.COMPONENT_TYPES)


@pytest.fixture(scope="module")
def reqs():
    return load(cp.APP_REQUIREMENTS)


@pytest.fixture(scope="module")
def lib():
    return load(rep_mod.APP_LIBRARY)


@pytest.fixture(scope="module")
def rules():
    return load(cp.PRESENCE_RULES)


def building(inventory, doc):
    return next(b for b in inventory["buildings"] if doc in b["document_ids"])


def entry(b, component_type):
    for lst in b["components"].values():
        for e in lst:
            if e["component_type"] == component_type:
                return e
    raise AssertionError(component_type)


# --- vocabulaire en app-requirements ---------------------------------------------------------

def test_every_component_type_is_unique_and_wellformed(comp):
    ids = [c["component_type"] for c in comp["component_types"]]
    assert len(ids) == len(set(ids))
    assert comp["presence_implies_quantity"] is False
    for required in ("ROOF_FLAT_COVERING", "ROOF_SLOPED_COVERING", "RAINWATER_DRAINAGE", "FACADE_MASONRY", "FACADE_CLADDING", "EXTERIOR_FRAME",
                     "EXTERIOR_WINDOW", "EXTERIOR_DOOR", "BALCONY_RAILING", "LIFT_INSTALLATION", "INTERCOM_INSTALLATION", "VENTILATION_INSTALLATION",
                     "COMMON_ELECTRICAL_INSTALLATION", "COMMON_LIGHTING", "COMMON_WATER_INSTALLATION"):
        assert required in ids
    assert "NL-SfB" in comp["description"] and "NIET" in comp["description"]  # geen claim van officiële NL-SfB


def test_every_app_requirement_points_at_an_existing_component_type(comp, reqs):
    ids = {c["component_type"] for c in comp["component_types"]}
    for r in reqs["requirements"]:
        for ct in r["requires"] + r["requires_any"] + r.get("physical_context_any", []):
            assert ct in ids, (r["app_element_key"], ct)
    for r in comp["component_types"]:
        for s in r["related_quantity_subjects"]:
            assert s in {x["subject_key"] for x in load(rep_mod.cp.ROOT / "vocabularies" / "quantity_subjects_v1.json")["subjects"]}


def test_all_24_app_elements_are_classified_exactly_once(lib, reqs):
    keys = [e["key"] for e in lib["elements"]]
    rkeys = [r["app_element_key"] for r in reqs["requirements"]]
    assert len(keys) == 24 and sorted(keys) == sorted(rkeys) and len(set(rkeys)) == 24
    assert reqs["app_source"]["ref"] == lib["source"]["ref"]


def test_special_app_element_classifications(reqs):
    by = {r["app_element_key"]: r for r in reqs["requirements"]}
    assert by["steiger"]["classification"] == "SUPPORT_SERVICE" and by["steiger"]["activation_mode"] == "NOT_PRESENCE_DRIVEN"
    assert by["steiger"]["requires"] == [] and by["steiger"]["requires_any"] == []
    assert by["dakisolatie"]["classification"] == "OPTIONAL_IMPROVEMENT" and by["dakisolatie"]["activation_mode"] == "USER_SELECTED"
    assert by["dakisolatie"]["requires"] == [] and by["dakisolatie"]["requires_any"] == []
    assert by["dakinspectie"]["requires_any"] == ["ROOF_FLAT_COVERING", "ROOF_SLOPED_COVERING"] and by["dakinspectie"]["requires"] == []
    assert by["dak-plat"]["requires"] == ["ROOF_FLAT_COVERING"] and by["dak-hellend"]["requires"] == ["ROOF_SLOPED_COVERING"]
    assert by["kozijnen-onderhoud"]["requires"] == ["EXTERIOR_FRAME"]
    assert by["lift"]["requires"] == ["LIFT_INSTALLATION"] and by["intercom"]["requires"] == ["INTERCOM_INSTALLATION"]
    sw = by["schilderwerk-buiten"]
    assert sw["activation_mode"] == "PRESENCE_AND_ATTRIBUTE" and sw["required_attributes"]  # niet simpelweg 'gevel aanwezig'
    assert "FACADE_MASONRY" not in sw["requires"] + sw["requires_any"]


def test_current_kozijnfactor_is_classified_as_legacy_estimate_fallback(reqs, lib):
    (lef,) = reqs["legacy_estimate_fallbacks"]
    assert lef["classification"] == "LEGACY_ESTIMATE_FALLBACK" and lef["method_class"] == "ESTIMATED"
    assert lef["factors"] == lib["koz_factoren"] == [1, 0.25, 0.125, 0.125]
    assert lef["minima"] == lib["koz_minima"]
    assert "canonical measured evidence" in lef["forbidden_use"]
    assert [r for r in reqs["requirements"] if r["app_element_key"] == "kozijnen-onderhoud"][0]["legacy_estimate_fallback_id"] == lef["fallback_id"]
    assert "ONGEWIJZIGD" in lef["behaviour_in_this_milestone"]


# --- stilte != ABSENT, missing != 0 ----------------------------------------------------------

def _rule(subject_rule_id):
    return next(r for r in load(os.path.join(ROOT, "vocabularies", "quantity_subjects_v1.json"))["bag3d_rules"] if r["rule_id"] == subject_rule_id)


def _sloped():
    pr = next(r for r in load(cp.PRESENCE_RULES)["bag3d_presence_rules"] if r["component_type"] == "ROOF_SLOPED_COVERING")
    return pr, _rule(pr["quantity_subject_rule_id"])


@pytest.mark.parametrize("attrs", [{}, None, {"b3_opp_dak_schuin": None}, {"b3_opp_dak_schuin": True}, {"b3_opp_dak_schuin": [1]},
                                   {"b3_opp_dak_plat": 10.0}])
def test_missing_field_is_unknown_never_absent_never_zero(attrs):
    pr, qr = _sloped()
    assertion, method, basis, res = cp.bag3d_presence(pr, qr, attrs)
    assert (assertion, method, basis) == ("UNKNOWN", "GEOMETRY_FIELD_MISSING", None)
    assert res["status"] == "NOT_AVAILABLE" and res["value"] is None


@pytest.mark.parametrize("val", [0, 0.0, "0", "0.00"])
def test_explicit_zero_is_geometry_absence_and_review_required(val):
    pr, qr = _sloped()
    assertion, method, basis, _ = cp.bag3d_presence(pr, qr, {"b3_opp_dak_schuin": val})
    assert (assertion, method) == ("ABSENT", "GEOMETRY_EXPLICIT_ZERO")
    assert basis["kind"] == "EXPLICIT_ZERO_VALUE_IN_SOURCE_FIELD"


def test_positive_value_is_present_geometry():
    pr, qr = _sloped()
    assert cp.bag3d_presence(pr, qr, {"b3_opp_dak_schuin": 99.91})[:2] == ("PRESENT", "GEOMETRY_POSITIVE_VALUE")


def test_negative_value_is_unknown_not_absent():
    pr, qr = _sloped()
    assert cp.bag3d_presence(pr, qr, {"b3_opp_dak_schuin": -1})[0] == "UNKNOWN"


def test_absent_evidence_requires_explicit_basis_and_review(evidence):
    absent = [e for e in evidence if e["assertion"] == "ABSENT"]
    assert absent, "DOC-012 heeft een expliciete 3D BAG-nul voor hellend dak"
    for e in absent:
        assert e["status"] == "REVIEW_REQUIRED" and e["absence_basis"]["kind"] == "EXPLICIT_ZERO_VALUE_IN_SOURCE_FIELD"
        assert e["source_type"] == "3D_BAG" and e["method_class"] == "GEOMETRY_EXPLICIT_ZERO"
    assert [(e["building_id"], e["component_type"]) for e in absent] == [("BAG:" + DOC012_PAND, "ROOF_SLOPED_COVERING")]


def _ev(**kw):
    base = dict(building_id="BAG:1", scope_level="BUILDING_SCOPE", bag_pand_id=None, component_type="EXTERIOR_FRAME", assertion="PRESENT",
                source_type="MJOP", method_class="SOURCE_EXPLICIT_ELEMENT", source_ref={"document_id": "X"}, created_by="t")
    base.update(kw)
    return cp.make_evidence(**base)


def test_silence_cannot_be_recorded_as_absent():
    for st, mc in (("MJOP", "SOURCE_EXPLICIT_ELEMENT"), ("PHOTO", "MANUAL_STATEMENT"), ("DRAWING", "GEOMETRY_FIELD_MISSING"), ("MJOP", "EXPLICIT_ABSENCE_STATEMENT")):
        with pytest.raises(cp.PresenceError):  # geen absence_basis
            _ev(assertion="ABSENT", source_type=st, method_class=mc, status="REVIEW_REQUIRED")
    with pytest.raises(cp.PresenceError):  # ABSENT zonder REVIEW_REQUIRED
        _ev(assertion="ABSENT", method_class="EXPLICIT_ABSENCE_STATEMENT", absence_basis={"kind": "EXPLICIT_SOURCE_STATEMENT", "statement": "geen lift"})
    with pytest.raises(cp.PresenceError):  # absence_basis bij PRESENT
        _ev(absence_basis={"kind": "EXPLICIT_SOURCE_STATEMENT", "statement": "x"})
    ok = _ev(assertion="ABSENT", method_class="EXPLICIT_ABSENCE_STATEMENT", status="REVIEW_REQUIRED",
             absence_basis={"kind": "EXPLICIT_SOURCE_STATEMENT", "statement": "Het MJOP stelt expliciet: geen lift aanwezig"})
    assert ok["assertion"] == "ABSENT"


def test_no_mjop_evidence_is_ever_absent_and_silent_components_stay_unknown(evidence, inventory):
    assert not [e for e in evidence if e["source_type"] == "MJOP" and e["assertion"] != "PRESENT"]
    d012 = building(inventory, "DOC-012")
    mald = building(inventory, "DOC-005")
    for b, ct in ((d012, "EXTERIOR_WINDOW"), (d012, "INTERCOM_INSTALLATION"), (mald, "LIFT_INSTALLATION"), (mald, "EXTERIOR_DOOR")):
        e = entry(b, ct)
        assert e["state"] == "UNKNOWN_NO_EVIDENCE" and e["evidence_ids"] == []  # niet gevonden != afwezig
    for b in inventory["buildings"]:
        # Frame Inventory Foundation v1: alleen EXTERIOR_FRAME is door de gebruiker bevestigd (PRESENT)
        assert b["components"]["absent"] == [] and [e["component_type"] for e in b["components"]["confirmed"]] == ["EXTERIOR_FRAME"]


def test_missing_snapshot_field_gives_unknown_evidence_in_the_builder(built):
    links, snaps = load(bci.bl.LINK_STORE), copy.deepcopy(bci.bs.load_snapshots())
    for s in snaps:
        for p in s["panden"]:
            if p["bag_pand_id"] == DOC012_PAND:
                del p["threedbag"]["attributes"]["b3_opp_dak_schuin"]
    res = bci.build(links_store=links, snapshots=snaps)
    evs = [e for e in res["evidence_store"]["evidence"] if e["component_type"] == "ROOF_SLOPED_COVERING"]
    mine = [e for e in evs if e["bag_pand_id"] == DOC012_PAND]
    assert [(e["assertion"], e["method_class"]) for e in mine] == [("UNKNOWN", "GEOMETRY_FIELD_MISSING")]
    b = building(res["inventory"], "DOC-012")
    assert entry(b, "ROOF_SLOPED_COVERING")["state"] == "UNKNOWN_FIELD_MISSING"
    assert b["components"]["proposed_absent"] == []


# --- 3D BAG presence --------------------------------------------------------------------------

def test_3d_bag_roof_presence_per_pand(evidence, inventory):
    mald = [e for e in evidence if e["source_type"] == "3D_BAG" and e["building_id"] == building(inventory, "DOC-005")["building_id"]]
    assert len(mald) == 30 and {e["assertion"] for e in mald} == {"PRESENT"}
    assert {e["component_type"] for e in mald} == {"ROOF_FLAT_COVERING", "ROOF_SLOPED_COVERING"}
    assert all(e["scope_level"] == "PAND" and e["bag_pand_id"] for e in mald)
    for e in mald:
        assert e["source_ref"]["quantity_evidence_id"].startswith("QE-")
        assert "details" in e and "value" not in e["details"]  # geen hoeveelheid als presence-detail
    d012 = {(e["component_type"], e["assertion"]) for e in evidence if e["source_type"] == "3D_BAG" and e["bag_pand_id"] == DOC012_PAND}
    assert d012 == {("ROOF_FLAT_COVERING", "PRESENT"), ("ROOF_SLOPED_COVERING", "ABSENT")}
    assert all("universeel" in " ".join(e["scope_caveats"]) or "geometrie" in " ".join(e["scope_caveats"]).lower()
               for e in evidence if e["source_type"] == "3D_BAG")


# --- historisch MJOP als presence-bron ---------------------------------------------------------

def test_explicit_historical_element_gives_present_evidence_with_material(evidence, inventory):
    frames = [e for e in evidence if e["component_type"] == "EXTERIOR_FRAME"]
    assert {(e["source_ref"]["document_id"], e["source_ref"]["quantity_observation_id"]) for e in frames} == {
        ("DOC-005", "QO-DOC-005-EL-007"), ("DOC-006", "QO-DOC-006-EL-007"), ("DOC-012", "QO-DOC-012-EL-007")}
    for e in frames:
        assert (e["assertion"], e["source_type"], e["scope_level"], e["bag_pand_id"]) == ("PRESENT", "MJOP", "BUILDING_SCOPE", None)
        assert e["details"]["material_as_reported"] == "hout"
        assert e["details"]["element_description_as_reported"] == "Kozijn buiten hout"
    mald = building(inventory, "DOC-005")
    assert entry(mald, "EXTERIOR_FRAME")["state"] == "CONFIRMED_PRESENT"  # menselijk besluit (Frame Inventory Foundation v1)
    assert entry(building(inventory, "DOC-012"), "EXTERIOR_FRAME")["state"] == "CONFIRMED_PRESENT"
    bare = bci.build(decisions_store=cp.new_store())["inventory"]  # zonder besluiten blijft het evidence-niveau PROPOSED_PRESENT
    assert entry(building(bare, "DOC-005"), "EXTERIOR_FRAME")["state"] == "PROPOSED_PRESENT"
    assert entry(building(bare, "DOC-012"), "EXTERIOR_FRAME")["state"] == "PROPOSED_PRESENT"


def test_interior_frames_and_painting_lines_are_not_exterior_frame_presence(evidence):
    ids = {e["source_ref"]["quantity_observation_id"] for e in evidence if e["source_type"] == "MJOP"}
    for qo in ("QO-DOC-012-EL-008", "QO-DOC-012-EL-020", "QO-DOC-012-EL-022", "QO-DOC-005-EL-022", "QO-DOC-005-EL-005", "QO-DOC-005-EL-006"):
        assert qo not in ids


def test_historical_quantity_is_context_only_never_geometry_or_presence_quantity(evidence):
    for e in evidence:
        if e["source_type"] != "MJOP":
            continue
        ctx = e["details"]["historical_reported_quantity_context"]
        assert ctx["interpretation"] == "HISTORICAL_REPORTED_QUANTITY_CONTEXT"
        assert {"MEASURED_QUANTITY", "GEOMETRY_QUANTITY"} <= set(ctx["not_interpreted_as"])
        assert "raw_inputs" not in e["source_ref"] and "value" not in e["source_ref"]
        assert set(e["details"]) <= {"element_code_internal", "element_description_as_reported", "location_as_reported", "material_as_reported",
                                     "material_normalized", "presence_rule_id", "presence_rule_inference", "historical_reported_quantity_context"}


def test_maldenhof_756_80_is_not_opening_area_or_frame_quantity(evidence):
    (e,) = [x for x in evidence if x["source_ref"].get("quantity_observation_id") == "QO-DOC-005-EL-007"]
    ctx = e["details"]["historical_reported_quantity_context"]
    assert (ctx["quantity_value"], ctx["unit_normalized"]) == ("756.80", "m2")
    assert {"WINDOW_OPENING_AREA", "FRAME_PAINTING_AREA", "FRAME_COUNT", "FRAME_SURFACE_AREA", "MEASURED_FRAME_AREA"} <= set(ctx["not_interpreted_as"])
    assert e["status"] == "REVIEW_REQUIRED"  # de bestaande observation is REVIEW_REQUIRED (unit-mismatch); presence erft dat
    # nergens een frame-/raam-quantity in de canonical quantity evidence
    qe = load(bci.QE_PATH)["evidence"]
    assert not [x for x in qe if any(k in x["quantity_subject"]["subject_key"] for k in FRAME_SUBJECTS)]
    vocab_subjects = {s["subject_key"] for s in load(os.path.join(ROOT, "vocabularies", "quantity_subjects_v1.json"))["subjects"]}
    assert not [s for s in vocab_subjects if any(k in s for k in FRAME_SUBJECTS)]
    # de oorspronkelijke historische observation is ongewijzigd (sha-gecontroleerd)
    assert sha(bci.QO_PATH) == OLD_HASHES["data/quantity_observations/quantity_observations_v1.json"]


def test_inference_rules_are_always_review_required(evidence, rules):
    inf = {r["rule_id"] for r in rules["historical_mjop_presence_rules"] if r["inference"] != "NONE"}
    assert inf
    for e in evidence:
        if e["source_type"] == "MJOP" and e["details"]["presence_rule_id"] in inf:
            assert e["status"] == "REVIEW_REQUIRED" and e["method_class"] == "SOURCE_EXPLICIT_ELEMENT_WITH_INFERENCE"


def test_historical_rules_are_exact_and_generic(rules):
    src = open(os.path.join(ROOT, "scripts", "build_component_inventory.py"), encoding="utf-8").read() + \
        open(os.path.join(ROOT, "scripts", "component_presence.py"), encoding="utf-8").read()
    for pat in ("DOC-0", "Maldenhof", "Meppelweg", "1106", "756", "BAG:036"):
        assert pat not in src, pat
    for r in rules["historical_mjop_presence_rules"]:
        assert r["element_description_original_exact"] and r["element_code_internal"]
    el = {"element_code_internal": "3120", "element_description_original": "  kozijn BUITEN hout ", "location_original": None}
    rule = next(r for r in rules["historical_mjop_presence_rules"] if r["component_type"] == "EXTERIOR_FRAME")
    assert cp.rule_matches(rule, el)  # genormaliseerde exacte gelijkheid
    assert not cp.rule_matches(rule, dict(el, element_description_original="Kozijn buiten hout en glas"))  # geen fuzzy matching
    assert not cp.rule_matches(rule, dict(el, element_code_internal="3230"))


# --- evidence-integriteit en schema's -----------------------------------------------------------

def test_evidence_is_content_addressed_valid_and_schema_conform(built, evidence, comp):
    ids = {c["component_type"] for c in comp["component_types"]}
    assert len({e["evidence_id"] for e in evidence}) == len(evidence)
    for e in evidence:
        assert cp.evidence_errors(e, ids) == [], e["evidence_id"]
    schema = load(os.path.join(ROOT, "schemas", "component_presence_evidence.schema.json"))
    jsonschema.validate(built["evidence_store"], schema)
    tampered = copy.deepcopy(evidence[0])
    tampered["assertion"] = "ABSENT"
    assert any("evidence_id" in x for x in cp.evidence_errors(tampered))
    bad = copy.deepcopy(built["evidence_store"])
    bad["evidence"][0]["assertion"] = "MAYBE"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_schema_rejects_absent_without_basis():
    schema = load(os.path.join(ROOT, "schemas", "component_presence_evidence.schema.json"))
    ev = _ev()
    store = {"builder_version": "t", "evidence": [dict(ev, assertion="ABSENT", status="REVIEW_REQUIRED", requires_human_review=True)]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(store, schema)


def test_builder_is_deterministic_and_committed_outputs_are_current(built):
    again = bci.build()
    assert bci.dumps(again["evidence_store"]) == bci.dumps(built["evidence_store"])
    assert bci.dumps(again["inventory"]) == bci.dumps(built["inventory"])
    assert open(bci.OUT_EVIDENCE, encoding="utf-8").read() == bci.dumps(built["evidence_store"])
    assert open(bci.OUT_INVENTORY, encoding="utf-8").read() == bci.dumps(built["inventory"])
    for script in ("build_component_inventory.py", "building_element_inventory_report.py"):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), "--check"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


# --- menselijke besluiten --------------------------------------------------------------------

def test_no_decisions_written_and_inventory_is_only_proposed_or_unknown(inventory):
    store = load(cp.DECISIONS)
    # sinds Frame Inventory Foundation v1: precies twee besluiten, alleen EXTERIOR_FRAME = PRESENT (Maldenhof en DOC-012)
    assert [(r["component_type"], r["decision"]) for r in store["records"]] == [("EXTERIOR_FRAME", "PRESENT")] * 2 and store["append_only"] is True
    assert inventory["summary"]["decisions_in_store"] == 2 and inventory["summary"]["active_decisions"] == 2
    for b in inventory["buildings"]:
        assert b["counts"]["confirmed"] == 1 and b["counts"]["absent"] == 0
        assert [e["component_type"] for lst in b["components"].values() for e in lst if e["human_decision_ref"]] == ["EXTERIOR_FRAME"]
    jsonschema.validate(store, load(os.path.join(ROOT, "schemas", "component_presence_decision.schema.json")))


def _decision_setup(built):
    b = building(built["inventory"], "DOC-012")
    ev_index = {e["evidence_id"]: e for e in built["evidence_store"]["evidence"]}
    flat = entry(b, "ROOF_FLAT_COVERING")
    return b, ev_index, flat


def test_human_decision_confirms_component_in_memory_only(built):
    b, ev_index, flat = _decision_setup(built)
    store, rec = cp.record_decision(cp.new_store(), building_id=b["building_id"], component_type="ROOF_FLAT_COVERING", decision="PRESENT",
                                    reason="test", reviewer_id="tester", reviewed_at="2026-10-06T08:00:00Z",
                                    considered_evidence_ids=flat["evidence_ids"], evidence_index=ev_index)
    jsonschema.validate(store, load(os.path.join(ROOT, "schemas", "component_presence_decision.schema.json")))
    res = bci.build(decisions_store=store)
    e = entry(building(res["inventory"], "DOC-012"), "ROOF_FLAT_COVERING")
    assert (e["state"], e["human_decision_ref"]) == ("CONFIRMED_PRESENT", rec["decision_id"])
    assert [r["decision_id"] for r in load(cp.DECISIONS)["records"]] == ["CPD-00001", "CPD-00002"]  # canoniek bestand onaangeroerd (geen ROOF_FLAT_COVERING)


def test_decision_rules(built):
    b, ev_index, flat = _decision_setup(built)
    kw = dict(building_id=b["building_id"], component_type="ROOF_FLAT_COVERING", reason="r", reviewer_id="t", reviewed_at="2026-10-06T08:00:00Z",
              evidence_index=ev_index)
    with pytest.raises(cp.PresenceError):  # PRESENT zonder overwogen evidence
        cp.record_decision(cp.new_store(), decision="PRESENT", considered_evidence_ids=[], **kw)
    with pytest.raises(cp.PresenceError):  # onbekende evidence
        cp.record_decision(cp.new_store(), decision="PRESENT", considered_evidence_ids=["CPE-0000000000000000"], **kw)
    with pytest.raises(cp.PresenceError):  # geen reviewer
        cp.record_decision(cp.new_store(), decision="PRESENT", considered_evidence_ids=flat["evidence_ids"], **dict(kw, reviewer_id=""))
    with pytest.raises(cp.PresenceError):  # evidence van een andere component
        other = entry(b, "RAINWATER_DRAINAGE")["evidence_ids"]
        cp.record_decision(cp.new_store(), decision="PRESENT", considered_evidence_ids=other, **kw)
    s1, r1 = cp.record_decision(cp.new_store(), decision="PRESENT", considered_evidence_ids=flat["evidence_ids"], **kw)
    s2, r2 = cp.record_decision(s1, decision="UNKNOWN", considered_evidence_ids=flat["evidence_ids"], **kw)
    assert r2["supersedes"] == r1["decision_id"] and [r["status"] for r in s2["records"]] == ["SUPERSEDED", "ACTIVE"]
    assert cp.store_errors(s2) == [] and aos.append_only_errors(s1["records"], s2["records"], "decision_id") == []
    assert all(r["reviewer"]["reviewer_type"] == "human" for r in s2["records"])
    # append-only: een record verwijderen of overschrijven wordt gevonden
    assert aos.append_only_errors(s2["records"], s2["records"][1:], "decision_id")
    tampered = copy.deepcopy(s2["records"])
    tampered[0]["decision"] = "ABSENT"
    assert aos.append_only_errors(s2["records"], tampered, "decision_id")
    # nieuwe evidence na het besluit -> opnieuw beoordelen; geen automatische winnaar
    s3, _ = cp.record_decision(cp.new_store(), decision="PRESENT", considered_evidence_ids=[flat["evidence_ids"][0]], **kw)
    e = entry(building(bci.build(decisions_store=s3)["inventory"], "DOC-012"), "ROOF_FLAT_COVERING")
    assert len(flat["evidence_ids"]) > 1 and e["state"] == "DECISION_REVIEW_REQUIRED"


def test_conflicting_evidence_is_never_auto_resolved(built):
    b = building(built["inventory"], "DOC-012")
    mixed = _ev(building_id=b["building_id"], component_type="ROOF_FLAT_COVERING", assertion="ABSENT", method_class="EXPLICIT_ABSENCE_STATEMENT",
                status="REVIEW_REQUIRED", absence_basis={"kind": "EXPLICIT_SOURCE_STATEMENT", "statement": "geen plat dak"}, source_type="DRAWING")
    evs = [e for e in built["evidence_store"]["evidence"] if e["building_id"] == b["building_id"]] + [mixed]
    scopes = bci.gather_scopes(load(bci.bl.LINK_STORE))
    inv = bci.build_inventory({k: v for k, v in scopes.items() if k == b["building_id"]}, evs, cp.component_type_index(), cp.new_store())
    e = entry(inv[0], "ROOF_FLAT_COVERING")
    assert e["state"] == "MIXED_EVIDENCE" and len(e["by_assertion"]["PRESENT"]["evidence_ids"]) >= 2 and e["by_assertion"]["ABSENT"]["evidence_ids"]


# --- niets anders veranderd --------------------------------------------------------------------

def test_existing_artifacts_are_byte_identical():
    for rel, expected in OLD_HASHES.items():
        assert sha(os.path.join(ROOT, rel)) == expected, rel


def test_quantity_resolutions_stay_zero_and_crosswalk_decisions_unchanged():
    assert load(os.path.join(ROOT, "data", "quantity_resolutions", "quantity_resolution_records.json"))["records"] == []
    cw = load(os.path.join(ROOT, "data", "crosswalk_decisions", "crosswalk_decision_records.json"))["records"]
    assert [r["decision_id"] for r in cw] == [f"XWD-0000{i}" for i in range(1, 7)] and all(r["status"] == "ACTIVE" for r in cw)


def test_inventory_and_evidence_contain_no_quantities_or_prices(inventory, evidence):
    text = json.dumps(inventory)
    for forbidden in ("unit_price", "calculated_cost", "kengetal", "resolved_value", "selected_evidence_id"):
        assert forbidden not in text
    assert "FRAME_COUNT" not in text  # alleen in context-lijsten 'not_interpreted_as' van de evidence, niet in de inventaris


def test_app_snapshot_matches_pinned_app_commit(lib):
    assert lib["source"]["ref"] == "eaeb256897d9a643d0a44ba4d298df33d0d4e211"
    assert len(lib["elements"]) == 24 and lib["koz_factoren"] == [1, 0.25, 0.125, 0.125]


def test_report_is_current_and_covers_all_sections():
    rep = rep_mod.build_report()
    assert open(rep_mod.OUT_JSON, encoding="utf-8").read() == rep_mod.dumps(rep)
    assert open(rep_mod.OUT_MD, encoding="utf-8").read() == rep_mod.render_md(rep) + "\n"
    for key in ("A_why_element_library_is_not_an_inventory", "B_component_vocabulary", "C_app_element_requirements", "D_evidence_model",
                "E_human_decision_model", "F_maldenhof_proposed_inventory", "G_doc012_proposed_inventory", "H_frame_findings",
                "I_legacy_apartment_factor", "J_proposed_frame_instance_model", "K_repeat_group_model", "L_human_decisions_next_milestone"):
        assert rep[key]
    assert rep["I_legacy_apartment_factor"]["classification"] == "LEGACY_ESTIMATE_FALLBACK"
    ex = rep["J_proposed_frame_instance_model"]["example"]
    assert Decimal(ex["opening_area_m2"]) == Decimal(ex["count"]) * Decimal(ex["width"]) * Decimal(ex["height"]) == Decimal("14.40")
    assert set(rep["J_proposed_frame_instance_model"]["separate_quantities"]) == {"FRAME_COUNT", "WINDOW_OPENING_AREA", "FRAME_PAINTING_AREA"}
    assert rep["unchanged_guarantees"]["decisions_written"] == 0
    assert "USER_CONFIRMED_REPEAT" in json.dumps(rep["K_repeat_group_model"])
