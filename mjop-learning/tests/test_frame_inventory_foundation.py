"""Tests voor Frame Inventory Foundation v1 + Vector Drawing Reader PoC v1.

De drawing-tests draaien uitsluitend op de synthetische TEST FIXTURE (tests/fixtures/drawing); er zijn geen real-world resultaten.
Read-only: er worden geen canonieke besluiten, resoluties, bundels of prijzen geschreven.
"""
import copy
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
from decimal import Decimal

import jsonschema
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures", "drawing"))

import append_only_store as aos  # noqa: E402
import build_component_inventory as bci  # noqa: E402
import build_frame_inventory as bfi  # noqa: E402
import component_presence as cp  # noqa: E402
import fixture_builder as fb  # noqa: E402
import frame_inventory as fi  # noqa: E402
import record_frame_presence_decisions as rfd  # noqa: E402
import vector_drawing_reader as vdr  # noqa: E402
import vector_drawing_source_audit as vda  # noqa: E402
from test_building_element_inventory import OLD_HASHES  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "drawing", "TEST_FIXTURE_synthetic_facade_v1.pdf")
OVERLAY = os.path.join(ROOT, "reports", "drawing", "overlays", "TEST_FIXTURE_synthetic_facade_v1_p1_overlay.svg")
FROZEN = {
    "data/kengetallen/kengetallen_batch1.json": "e8b9b2260fb681da242817e51dfdb5ca3b1ab3ec1e3e5dcd6b56d3cc71761897",  # officiële KG-data
    "data/kentallen/kentallen_batch1.json": "c9d5a5d64a5795b20f25ba0688cd05194e44141a2bb8113f27c35fc0ef179f02",
    # MJOP-App snapshots in deze repo (de App-repo zelf is niet aangeraakt)
    "reports/pricing/inputs/mjop_app_price_inventory.json": "7a17c9e924deb6104e3dea110715d59510e1e1a9d656b3938cd5b7a7e8c9ec49",
    "reports/quantity/subject_expansion_inputs/mjop_app_element_library_1afdeca.json": "374abd3ede5b5b65a5f3852ce09bbce9541704c580ff2e0c043f8e79b396c98c",
    "reports/quantity/subject_expansion_inputs/mjop_app_element_library_eaeb256.json": "a508e160db225bbe9ccb43f94e1c4fff7e9b05fd0a8658d3727f178fb7430eec",
}
HIST = {"Maldenhof": "756.80", "Meppelweg": "1296.59"}


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
def frame_build():
    return bfi.build()


@pytest.fixture(scope="module")
def fixture_doc():
    return vdr.read_document(FIXTURE, "TESTFIX", is_test_fixture=True)


def analyse(page_obs):
    scale = vdr.determine_scale(page_obs)
    info = vdr.classify_page_type(page_obs)
    cands, groups, diag = vdr.find_opening_candidates(page_obs, info, scale, "TESTFIX")
    return scale, info, cands, groups, diag


def pdf_page(tmp_path, name, **kw):
    p = tmp_path / name
    p.write_bytes(fb.build_pdf(**kw))
    doc = vdr.read_document(p, "TESTFIX", is_test_fixture=True)
    return doc["pages"][0]


def instance(**over):
    base = {"frame_instance_id": "FI-TEST-1", "building_id": "BAG:0518100000354752", "bag_pand_id": "0518100000354752", "component_type": "EXTERIOR_WINDOW",
            "facade_side": "FRONT", "storey": 1, "subtype": "TURN_TILT", "material": "WOOD", "count": 8, "width_m": "1.20", "height_m": "1.50",
            "dimension_basis": "OPENING", "opening_area_m2": None, "frame_outer_area_m2": None,
            "source_refs": [{"kind": "TEST"}], "provenance": {"source_type": "USER_CONFIRMED_MANUAL"}, "status": "CONFIRMED", "human_decision_ref": "TEST-DECISION"}
    base.update(over)
    return base


# --- presence-besluiten ----------------------------------------------------------------------

def test_exterior_frame_decisions_are_append_only():
    store = cp.load_store()
    assert store["append_only"] is True and [r["decision_id"] for r in store["records"]] == ["CPD-00001", "CPD-00002"]
    assert cp.store_errors(store) == []
    jsonschema.validate(store, load(os.path.join(ROOT, "schemas", "component_presence_decision.schema.json")))
    assert aos.append_only_errors(store["records"], store["records"], "decision_id") == []
    assert aos.append_only_errors(store["records"], store["records"][1:], "decision_id")  # verwijderen wordt gevonden
    tampered = copy.deepcopy(store["records"])
    tampered[0]["decision"] = "UNKNOWN"
    assert aos.append_only_errors(store["records"], tampered, "decision_id")  # overschrijven wordt gevonden


def test_applying_decisions_is_idempotent(built):
    store, added = rfd.apply(cp.load_store(), built["evidence_store"]["evidence"])
    assert added == [] and store == cp.load_store()  # niets dubbel, niets overschreven


def test_maldenhof_and_doc012_exterior_frame_present(built):
    active = cp.active_decisions(cp.load_store())
    inv = {b["building_id"]: b for b in built["inventory"]["buildings"]}
    keys = {k: r for k, r in active.items()}
    assert {k[2] for k in keys} == {"EXTERIOR_FRAME"} and all(k[1] is None for k in keys)
    labels = {}
    for (bid, _, _), rec in keys.items():
        docs = tuple(inv[bid]["document_ids"])
        labels[docs] = rec
        assert rec["decision"] == "PRESENT" and rec["status"] == "ACTIVE"
        assert rec["reviewer"] == {"reviewer_id": "user-approved", "reviewer_type": "human"}
        assert "Kozijn buiten hout" in rec["decision_reason"] and "zegt niets over aantal" in rec["decision_reason"]
        every = sorted(e["evidence_id"] for e in built["evidence_store"]["evidence"] if e["building_id"] == bid and e["component_type"] == "EXTERIOR_FRAME")
        assert rec["considered_evidence_ids"] == every
        entry = next(e for lst in inv[bid]["components"].values() for e in lst if e["component_type"] == "EXTERIOR_FRAME")
        assert entry["state"] == "CONFIRMED_PRESENT" and entry["human_decision_ref"] == rec["decision_id"]
    assert set(labels) == {("DOC-005", "DOC-006"), ("DOC-012",)}


def test_no_other_presence_decisions(built):
    store = cp.load_store()
    assert len(store["records"]) == 2 and {r["component_type"] for r in store["records"]} == {"EXTERIOR_FRAME"}
    assert built["inventory"]["summary"]["active_decisions"] == 2
    for b in built["inventory"]["buildings"]:
        decided = [e for lst in b["components"].values() for e in lst if e["human_decision_ref"]]
        assert [e["component_type"] for e in decided] == ["EXTERIOR_FRAME"]
        assert b["counts"]["absent"] == 0
    # materiaal blijft evidence-detail; het besluit is alleen PRESENT
    ev = [e for e in built["evidence_store"]["evidence"] if e["component_type"] == "EXTERIOR_FRAME"]
    assert all(e["details"]["material_as_reported"] == "hout" for e in ev)
    assert not any("material" in r for r in store["records"])


# --- 756,80 / quantity-semantiek -------------------------------------------------------------

def test_historical_756_80_never_becomes_frame_quantity(frame_build):
    store, _, rep = frame_build
    for b in store["buildings"]:
        assert all(q["status"] == "UNKNOWN" and q["value"] is None for q in b["quantities"].values())
        hist = b["historical_reported_quantity_context"]
        assert hist and all(h["interpretation"] == "HISTORICAL_REPORTED_QUANTITY_CONTEXT" for h in hist)
        assert set(h["quantity_value"] for h in hist) == {next(v for k, v in HIST.items() if k in b["label"])}
        assert set(hist[0]["never_interpreted_as"]) == set(bfi.SEVEN)
    assert store["instances"] == [] and store["frame_groups"] == []
    text = json.dumps({k: v for k, v in store.items() if k != "buildings"})
    assert "756" not in text and "1296" not in text
    # een instance die 756,80 als oppervlak claimt wordt geweigerd (geen afleiding uit historische context)
    bad = instance(opening_area_m2="756.80")
    assert any("opening_area_m2" in e for e in fi.instance_errors(bad))
    assert any("frame_outer_area_m2" in e for e in fi.instance_errors(instance(frame_outer_area_m2="756.80", dimension_basis="FRAME_OUTER")))
    cross = rep["J_maldenhof_historical_cross_check"]
    assert cross["classification"] == "NOT_COMPARABLE" and cross["accuracy_percentage"] is None
    assert all(v is None for v in cross["drawing_derived"].values())


def test_frame_window_door_are_separate_and_concepts_never_auto_equal():
    voc = load(fi.CONCEPTS_VOCAB)
    by = {c["concept"]: c for c in voc["concepts"]}
    assert list(by) == ["FRAME_COUNT", "WINDOW_COUNT", "EXTERIOR_DOOR_COUNT", "WINDOW_OPENING_AREA", "FRAME_OUTER_AREA", "FRAME_PAINTING_AREA", "GLASS_AREA"]
    assert all(c["auto_equal_to"] == [] for c in voc["concepts"])
    assert by["FRAME_COUNT"]["component_types"] == ["EXTERIOR_FRAME"] and by["WINDOW_COUNT"]["component_types"] == ["EXTERIOR_WINDOW"]
    assert by["EXTERIOR_DOOR_COUNT"]["component_types"] == ["EXTERIOR_DOOR"]
    assert set(fi.COMPONENT_TYPES) == {"EXTERIOR_FRAME", "EXTERIOR_WINDOW", "EXTERIOR_DOOR"}
    assert fi.instance_errors(instance(component_type="WINDOW"))  # geen vrije of samengevoegde types
    assert fi.instance_errors(instance(component_type="EXTERIOR_WINDOW_OR_DOOR"))


def test_painting_area_is_never_auto_derived():
    voc = {c["concept"]: c for c in load(fi.CONCEPTS_VOCAB)["concepts"]}
    assert voc["FRAME_PAINTING_AREA"]["derivation"] == "NEVER_AUTOMATIC" and voc["FRAME_PAINTING_AREA"]["auto_derivable"] is False
    assert voc["GLASS_AREA"]["auto_derivable"] is False
    with pytest.raises(fi.FrameError):
        fi.derive_area(instance(), "PAINTING")
    assert any("painting_area" in e for e in fi.instance_errors(instance(painting_area_m2="14.40")))
    ok = instance()
    assert fi.derive_area(ok, "OPENING") == {"status": "DERIVED", "value_m2": "14.40"}  # 8 x 1,20 x 1,50
    stored = instance(opening_area_m2="14.40")
    assert fi.instance_errors(stored) == [] and "painting" not in json.dumps(stored)
    assert any("wijkt af" in e for e in fi.instance_errors(instance(opening_area_m2="14.41")))
    # opening-area alleen onder de voorwaarden
    assert fi.derive_area(instance(dimension_basis="FRAME_OUTER"), "OPENING")["status"] == "UNKNOWN"
    assert fi.derive_area(instance(dimension_basis="DRAWING_DIMENSION"), "OPENING")["status"] == "UNKNOWN"
    assert fi.derive_area(instance(status="PROPOSED", human_decision_ref=None), "OPENING")["status"] == "UNKNOWN"  # count niet bevestigd
    assert fi.derive_area(instance(status="REVIEW_REQUIRED", human_decision_ref=None), "OPENING")["status"] == "UNKNOWN"
    assert fi.instance_errors(instance(status="PROPOSED", human_decision_ref=None, opening_area_m2="14.40"))
    assert fi.derive_area(instance(dimension_basis="FRAME_OUTER"), "FRAME_OUTER")["value_m2"] == "14.40"
    assert not fi.instance_errors(instance(dimension_basis="FRAME_OUTER", frame_outer_area_m2="14.40"))


def test_floats_are_not_accepted_for_quantities():
    with pytest.raises(fi.FrameError):
        fi.dec(1.2)
    assert fi.instance_errors(instance(width_m=1.2))
    assert Decimal(fi.derive_area(instance(width_m="1.15", height_m="1.15", count=3), "OPENING")["value_m2"]) == Decimal("3.97")


def test_missing_dimension_stays_unknown():
    assert fi.derive_area(instance(width_m=None, height_m=None), "OPENING")["status"] == "UNKNOWN"
    assert fi.instance_errors(instance(width_m="1.20", height_m=None))
    assert fi.instance_errors(instance(dimension_basis="UNKNOWN"))  # maten zonder bekende basis
    assert fi.instance_errors(instance(provenance={"source_type": "DRAWING_MEASURED"}))  # tekening-maten zonder scale_evidence
    ok = instance(width_m=None, height_m=None, dimension_basis="UNKNOWN")
    assert fi.instance_errors(ok) == []


def test_instance_and_group_contract():
    jsonschema.validate(instance(), load(os.path.join(ROOT, "schemas", "frame_component_instance.schema.json")))
    assert fi.instance_errors(instance()) == []
    for field in ("facade_side", "subtype", "material"):
        assert fi.instance_errors(instance(**{field: "NOPE"}))
    assert fi.instance_errors(instance(count=0)) and fi.instance_errors(instance(storey=None))
    assert fi.instance_errors(instance(source_refs=[]))
    assert fi.instance_errors(instance(status="CONFIRMED", human_decision_ref=None))  # bevestigen kan alleen een mens
    rep = instance(count=1, frame_instance_id="FI-REP")
    grp = {"frame_group_id": "FG-1", "building_id": rep["building_id"], "representative_instance": rep, "count": 8,
           "applies_to": [{"scope": "FACADE", "bag_pand_id": rep["bag_pand_id"], "facade_side": "FRONT"}], "occurrence_basis": "USER_CONFIRMED_IDENTICAL",
           "source_refs": [{"kind": "TEST"}], "status": "CONFIRMED", "human_decision_ref": "TEST", "opening_area_m2": "14.40"}
    assert fi.group_errors(grp) == []
    assert fi.group_errors(dict(grp, opening_area_m2="14.41"))
    assert fi.group_errors(dict(grp, applies_to=[{"scope": "BUILDING_WIDE"}], human_decision_ref=None, status="REVIEW_REQUIRED"))  # geen gebouwbrede multiplier
    same = dict(grp, occurrence_basis="SAME_DRAWING_SYMBOL")
    assert fi.group_errors(same)  # per-occurrence bewijs ontbreekt
    assert fi.group_errors(dict(same, occurrence_evidence_refs=[{"r": 1}] * 7))
    assert fi.group_errors(dict(same, occurrence_evidence_refs=[{"r": i} for i in range(8)])) == []
    assert fi.group_errors(dict(grp, count=1))
    assert fi.group_errors(dict(grp, representative_instance=dict(rep, count=3)))
    store = {"store_version": "frame_inventory_v1", "instances": [instance()], "frame_groups": [grp], "buildings": [], "policy": {}}
    assert fi.store_errors(store) == []
    bfi.validate_schema(store, "frame_inventory")
    with pytest.raises(jsonschema.ValidationError):
        bfi.validate_schema(dict(store, instances=[dict(instance(), painting_area_m2="1.00")]), "frame_inventory")


# --- repeat groups ---------------------------------------------------------------------------

def test_repeat_group_unusable_without_user_confirmed_repeat():
    cand = fi.repeat_group_candidate(repeat_group_id="RG-TEST-1", building_id="BAG:0363100012070344+0363100012071880", component_type="EXTERIOR_WINDOW",
                                     representative_pand_id="0363100012070344", applies_to_pand_ids=["0363100012071880"], transformation="SAME",
                                     evidence_refs=[{"kind": "TEST"}])
    assert cand["status"] == "REPEAT_CANDIDATE" and cand["decision_ref"] is None and not fi.repeat_group_usable(cand)
    active_no_ref = dict(cand, status="ACTIVE")
    assert fi.repeat_group_errors(active_no_ref) and not fi.repeat_group_usable(active_no_ref)
    for bad_ref in ({"decision_type": "SOMETHING_ELSE", "decision_id": "X", "reviewer": {"reviewer_id": "u", "reviewer_type": "human"}, "reviewed_at": "2026-10-06T08:00:00Z"},
                    {"decision_type": "USER_CONFIRMED_REPEAT", "decision_id": "X", "reviewer": {"reviewer_id": "bot", "reviewer_type": "agent"}, "reviewed_at": "2026-10-06T08:00:00Z"}):
        assert not fi.repeat_group_usable(dict(cand, status="ACTIVE", decision_ref=bad_ref))
    good = dict(cand, status="ACTIVE", decision_ref={"decision_type": "USER_CONFIRMED_REPEAT", "decision_id": "TEST-RPD-1",
                                                      "reviewer": {"reviewer_id": "tester", "reviewer_type": "human"}, "reviewed_at": "2026-10-06T08:00:00Z"})
    assert fi.repeat_group_errors(good) == [] and fi.repeat_group_usable(good)
    schema = load(os.path.join(ROOT, "schemas", "component_repeat_group.schema.json"))
    bfi.validate_schema({"store_version": "component_repeat_group_v1", "groups": [cand, good]}, "component_repeat_group")
    assert fi.repeat_group_errors(dict(cand, transformation="ROTATED")) and fi.repeat_group_errors(dict(cand, component_type="ROOF_FLAT_COVERING"))
    assert fi.repeat_group_errors(dict(cand, applies_to_pand_ids=[cand["representative_pand_id"]]))
    with pytest.raises(fi.FrameError):  # een candidate kan niet met decision_ref/ACTIVE gemaakt worden
        fi.repeat_group_candidate(repeat_group_id="RG-X", building_id="BAG:1", component_type="EXTERIOR_FRAME", representative_pand_id="1",
                                  applies_to_pand_ids=["1"], transformation="SAME", evidence_refs=[])
    assert schema["properties"]["groups"]
    stored = load(fi.REPEAT_GROUPS)
    assert stored["groups"] == []  # geen enkele bevestigde herhaling; geen automatische x13


def test_source_priority_only_within_same_subject():
    subj = {"concept": "FRAME_COUNT", "building_id": "B"}
    cands = [{"subject": subj, "source": s, "value": s} for s in ("LEGACY_ESTIMATE_FALLBACK", "USER_ASSISTED_PHOTO", "DRAWING_MEASURED")]
    assert fi.select_quantity(cands)["source"] == "DRAWING_MEASURED"
    assert fi.select_quantity(cands + [{"subject": subj, "source": "USER_CONFIRMED_MANUAL", "value": 1}])["source"] == "USER_CONFIRMED_MANUAL"
    with pytest.raises(fi.FrameError):  # geen winnaar tussen verschillende subjects
        fi.select_quantity(cands + [{"subject": {"concept": "WINDOW_OPENING_AREA", "building_id": "B"}, "source": "USER_CONFIRMED_MANUAL", "value": 1}])
    assert fi.select_quantity([]) is None
    assert fi.legacy_fallback_allowed({"has_confirmed_manual_or_drawing_inventory": False}) is True
    assert fi.legacy_fallback_allowed({"has_confirmed_manual_or_drawing_inventory": True}) is False
    leg = load(fi.CONCEPTS_VOCAB)["legacy_estimate_fallback"]
    assert leg["source"] == "LEGACY_ESTIMATE_FALLBACK" and leg["factors"] == ["1", "0.25", "0.125", "0.125"] and leg["app_constant"] == "KOZ_FACTOREN"
    assert leg["priority"] == "ONLY_WHEN_NO_CONFIRMED_MANUAL_OR_DRAWING_BASED_FRAME_INVENTORY"
    assert load(fi.CONCEPTS_VOCAB)["future_source_priority"] == ["USER_CONFIRMED_MANUAL", "DRAWING_MEASURED", "USER_ASSISTED_PHOTO", "SOURCE_REPORTED_HISTORICAL", "LEGACY_ESTIMATE_FALLBACK"]


def test_store_state_for_both_buildings(frame_build):
    store, repeat, rep = frame_build
    assert len(store["buildings"]) == 2
    for b in store["buildings"]:
        assert b["exterior_frame_presence"]["state"] == "CONFIRMED_PRESENT" and b["exterior_frame_presence"]["material_as_reported"] == "hout"
        assert b["legacy_estimate_fallback"] == {"source": "LEGACY_ESTIMATE_FALLBACK", "applies": True, "reason": b["legacy_estimate_fallback"]["reason"]}
        assert b["drawing_source_status"] == "REAL_WORLD_POC_BLOCKED_NO_DRAWING"
    assert {b["exterior_frame_presence"]["decision_id"] for b in store["buildings"]} == {"CPD-00001", "CPD-00002"}
    assert rep["H_opening_candidates"]["real_world_count"] is None and rep["E_chosen_pdf_page"] is None
    assert repeat["groups"] == []


# --- bron-audit ------------------------------------------------------------------------------

def test_audit_committed_is_current_and_blocks_real_world_poc():
    fresh = vda.audit()
    assert json.dumps(fresh, ensure_ascii=False, indent=1) + "\n" == open(vda.OUT_JSON, encoding="utf-8").read()
    assert vda.render_md(fresh) == open(vda.OUT_MD, encoding="utf-8").read()
    assert fresh["real_world_status"] == "REAL_WORLD_POC_BLOCKED_NO_DRAWING"
    s = fresh["summary"]
    assert s["unique_pdfs"] == 13 and s["total_pdf_paths"] == 16 and s["total_pages"] == 323
    assert s["vector_drawing_candidate_pages"] == 0 and s["raster_drawing_candidate_pages"] == 0 and s["pages_with_strong_drawing_label"] == 0
    assert all(d["classification"] == "MJOP_REPORT_ONLY" for d in fresh["documents"])
    pdfs = {p for d in fresh["documents"] for p in d["paths"]}
    assert pdfs == {str(p.relative_to(ROOT)) for p in vda.find_pdfs()}  # alle repo-PDF's onderzocht
    assert not any("TEST_FIXTURE" in p for p in pdfs)


def test_audit_classifies_the_fixture_as_vector_drawing_candidate():
    import pdfplumber
    with pdfplumber.open(FIXTURE) as pdf:
        a = vda.audit_page(pdf.pages[0], 1)
    a["classification"], _ = vda.classify_page(a, doc_is_mjop=False)
    # de fixture heeft een titel/schaal maar te weinig vectorprimitives met niet-orthogonale delen -> conservatief GEEN kandidaat
    assert a["strong_drawing_labels"] and a["classification"] == "NO_DRAWING_FOUND"
    # tabelraster met sterk label blijft geen tekening; een rijke vectorpagina met label wel
    rich = dict(a, vector_primitives={"lines": 40, "rects": 10, "curves": 5, "total": 55, "non_orthogonal_lines_or_complex_curves": 20})
    assert vda.classify_page(rich, False)[0] == "VECTOR_DRAWING_CANDIDATE"
    assert vda.classify_page(dict(rich, strong_drawing_labels=[]), True)[0] == "MJOP_REPORT_ONLY"
    assert vda.classify_page(dict(rich, vector_primitives=dict(rich["vector_primitives"], non_orthogonal_lines_or_complex_curves=0)), True)[0] == "MJOP_REPORT_ONLY"
    raster = dict(a, strong_drawing_labels=[], image_area_ratio=0.9, chars=10, vector_primitives=dict(rich["vector_primitives"], total=0))
    assert vda.classify_page(raster, False)[0] == "RASTER_DRAWING_CANDIDATE"
    photo_cover = dict(raster, chars=113)
    assert vda.classify_page(photo_cover, True)[0] == "MJOP_REPORT_ONLY"


# --- vector primitives -----------------------------------------------------------------------

def test_reader_stores_raw_primitives_with_provenance(fixture_doc):
    assert fixture_doc["contract_version"] == "drawing_observation_v1" and fixture_doc["is_test_fixture"] is True
    assert fixture_doc["source"]["sha256"] == sha(FIXTURE) and fixture_doc["source"]["file"].endswith("TEST_FIXTURE_synthetic_facade_v1.pdf")
    ex = fixture_doc["extraction"]
    assert ex["reader_version"] == vdr.READER_VERSION and ex["pdfplumber"] and ex["pdfminer.six"]
    assert fixture_doc["interpretation"].startswith("RAW_PRIMITIVES_ONLY")
    p = fixture_doc["pages"][0]
    assert (p["page"], p["width_pt"], p["height_pt"]) == (1, 1190.55, 841.89) and p["units"] == "pdf_points_origin_top_left"
    assert p["raw_counts"] == {"lines": 8, "rects": 10, "curves": 0, "text_spans": 15, "images": 0}
    assert p["layers"]["optional_content_present"] is False
    for key in ("lines", "rects", "curves"):
        for prim in p[key]:
            assert len(prim["bbox"]) == 4 and prim["id"][0] == key[0].upper()
    assert {d["value_mm"] for d in p["dimension_texts"]} == {1200, 1500}
    assert all(d["line_ref"] for d in p["dimension_texts"])
    # ruwe primitives: geen classificatievelden
    assert not any(k in json.dumps(p) for k in ("opening_candidate", "possible_type", "page_type"))


def test_reader_is_deterministic(fixture_doc):
    again = vdr.read_document(FIXTURE, "TESTFIX", is_test_fixture=True)
    assert vdr.dumps(again) == vdr.dumps(fixture_doc)
    assert fb.build_pdf() == open(FIXTURE, "rb").read()  # fixture reproduceerbaar
    a1, a2 = analyse(fixture_doc["pages"][0]), analyse(again["pages"][0])
    assert json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True)
    svg = vdr.render_overlay_svg(fixture_doc["pages"][0], a1[2], fixture_doc["pages"][0]["dimension_texts"], "TEST FIXTURE overlay - synthetisch, geen echt gebouw")
    assert svg == open(OVERLAY, encoding="utf-8").read()
    assert svg.count("OC-") == 0 and "<svg" in svg and "TEST FIXTURE" in svg


def test_fixture_is_clearly_marked():
    assert "TEST_FIXTURE" in os.path.basename(FIXTURE)
    assert "TEST FIXTURE" in fb.__doc__ and "GEEN ECHTE BOUWTEKENING" in fb.__doc__
    assert b"TEST FIXTURE - SYNTHETISCH - GEEN ECHT GEBOUW" in open(FIXTURE, "rb").read()
    assert os.listdir(os.path.join(ROOT, "data", "drawing_observations")) == ["README.md"]  # geen fixture-data als real-world observatie


# --- schaal / maatvoering --------------------------------------------------------------------

def test_no_points_to_meters_without_scale_evidence(tmp_path):
    with pytest.raises(vdr.ScaleError):
        vdr.to_meters(100, None)
    with pytest.raises(vdr.ScaleError):
        vdr.to_meters(100, {"status": "UNKNOWN", "scale_value": None})
    page = pdf_page(tmp_path, "noscale.pdf", scale_label=False, dim_lines=False)
    scale, info, cands, _, _ = analyse(page)
    assert scale["status"] == "UNKNOWN" and scale["scale_source"] is None and scale["scale_value"] is None and scale["reason"].startswith("NO_SCALE_EVIDENCE")
    assert cands and all(c["width_m"] is None and c["height_m"] is None and c["scale_ref"] is None and c["dimension_basis"] == "UNKNOWN" for c in cands)
    with pytest.raises(vdr.ScaleError):
        vdr.to_meters(34.016, scale)


def test_scale_from_dimension_lines_is_preferred_and_cross_checked(fixture_doc):
    page = fixture_doc["pages"][0]
    scale = vdr.determine_scale(page)
    assert scale["status"] == "KNOWN" and scale["scale_source"] == "DIMENSION_LINE" and scale["dimension_evidence_refs"] == ["D0001", "D0002"]
    assert abs(Decimal(scale["scale_value"]) - Decimal("35.2778")) < Decimal("0.001") and scale["drawing_scale_label"] == "1:100" and scale["label_consistent"] is True
    assert vdr.fmt_m(vdr.to_meters(34.016, scale)) == "1.200"
    # conflicterende maatlijnen -> UNKNOWN
    bad = copy.deepcopy(page)
    bad["dimension_texts"][0]["value_mm"] = 3000
    s = vdr.determine_scale(bad)
    assert s["status"] == "UNKNOWN" and s["reason"].startswith("CONFLICTING_DIMENSION_EVIDENCE")
    # maattekst zonder gekoppelde lijn is geen bewijs
    nolink = copy.deepcopy(page)
    for d in nolink["dimension_texts"]:
        d["line_ref"], d["line_length_pt"] = None, None
    s = vdr.determine_scale(nolink)  # valt terug op label 1:100 + A3
    assert s["scale_source"] == "DRAWING_SCALE_LABEL" and s["ratio"] == 100 and s["dimension_evidence_refs"] == []
    assert abs(Decimal(s["scale_value"]) - Decimal("35.277778")) < Decimal("0.00001")


def test_scale_label_requires_standard_paper_and_a_single_ratio(tmp_path):
    page = pdf_page(tmp_path, "label.pdf", dim_lines=False)
    s = vdr.determine_scale(page)
    assert s["scale_source"] == "DRAWING_SCALE_LABEL" and s["paper_size"] == "A3"
    resized = dict(page, width_pt=1000.0, height_pt=700.0)  # geschaald/niet-standaard papier -> PDF-geometrie niet te vertrouwen
    s = vdr.determine_scale(resized)
    assert s["status"] == "UNKNOWN" and s["reason"].startswith("SCALE_LABEL_WITHOUT_STANDARD_PAPER")
    two = pdf_page(tmp_path, "two.pdf", dim_lines=False, extra_scale_label="schaal 1:50")
    s = vdr.determine_scale(two)
    assert s["status"] == "UNKNOWN" and s["reason"].startswith("AMBIGUOUS_SCALE_LABELS")
    _, _, cands, _, _ = analyse(two)
    assert all(c["width_m"] is None for c in cands)


def test_missing_dimension_stays_unknown_on_candidates(fixture_doc):
    _, _, cands, _, _ = analyse(fixture_doc["pages"][0])
    with_dim = [c for c in cands if c["dimension_evidence_refs"]]
    assert len(with_dim) == 1 and (with_dim[0]["width_m"], with_dim[0]["height_m"], with_dim[0]["dimension_basis"]) == ("1.200", "1.500", "DRAWING_DIMENSION")
    without = [c for c in cands if not c["dimension_evidence_refs"]]
    assert without and all(c["dimension_basis"] == "UNKNOWN" for c in without)  # maat uit geometrie x schaal, basis (opening/kozijn) onbekend


# --- paginatype en candidates ----------------------------------------------------------------

def test_page_type_uses_explicit_labels_only(tmp_path, fixture_doc):
    info = vdr.classify_page_type(fixture_doc["pages"][0])
    assert (info["page_type"], info["facade_side"], info["reason"]) == ("FACADE_ELEVATION", "FRONT", "EXPLICIT_LABEL")
    for title, expected in (("PLATTEGROND BEGANE GROND", "FLOOR_PLAN"), ("DOORSNEDE A-A", "SECTION"), ("KOZIJNSTAAT", "SCHEDULE"), ("ACHTERGEVEL AANZICHT", "FACADE_ELEVATION")):
        assert vdr.classify_page_type(pdf_page(tmp_path, f"{expected}.pdf", title=title))["page_type"] == expected
    assert vdr.classify_page_type(pdf_page(tmp_path, "rear.pdf", title="ACHTERGEVEL AANZICHT"))["facade_side"] == "REAR"
    for title in ("TEKENING 12", "Voorgevel", "WONING"):  # zonder expliciet typelabel: UNKNOWN
        got = vdr.classify_page_type(pdf_page(tmp_path, "u.pdf", title=title))
        assert got["page_type"] == "UNKNOWN"
    assert vdr.classify_page_type(pdf_page(tmp_path, "mixed.pdf", title="PLATTEGROND EN DOORSNEDE"))["page_type"] == "UNKNOWN"
    # 'detail' telt alleen met een expliciete schaal
    assert vdr.classify_page_type(pdf_page(tmp_path, "d.pdf", title="DETAIL KOZIJN", scale_label=False))["page_type"] == "UNKNOWN"
    assert vdr.classify_page_type(pdf_page(tmp_path, "d2.pdf", title="DETAIL KOZIJN"))["page_type"] == "DETAIL"


def test_opening_candidates_are_conservative_and_never_confirmed_frames(tmp_path, fixture_doc):
    scale, info, cands, groups, diag = analyse(fixture_doc["pages"][0])
    assert len(cands) == 7 and diag["considered_boxes"] == 9 and diag["rejected_not_inside_facade_plane"] == 1 and diag["rejected_no_supporting_evidence"] == 1
    boxes = {tuple(c["bbox"]) for c in cands}
    assert not any(abs(b[0] - 700) < 1 for b in boxes)  # losse ongelabelde rechthoek in de gevel is GEEN candidate
    assert not any(abs(b[0] - 950) < 1 for b in boxes)  # rechthoek buiten het gevelvlak is GEEN candidate
    for c in cands:
        assert c["status"] == "REVIEW_REQUIRED" and c["is_confirmed_frame"] is False and c["evidence"]["inside_facade_plane"]
        assert c["evidence"]["repetition"] or c["evidence"]["explicit_label"] or c["evidence"]["dimension_context"]
        assert c["source_primitive_refs"] and c["page"] == 1 and c["facade_side"] == "FRONT"
    door = [c for c in cands if c["possible_type"] == "EXTERIOR_DOOR"]
    assert len(door) == 1 and door[0]["nearby_labels"] == [{"text_span_ref": door[0]["nearby_labels"][0]["text_span_ref"], "text": "deur"}]
    # candidates vormen nooit instances: geen frame-store, geen instance-validatie
    assert load(fi.FRAME_INVENTORY)["instances"] == [] and all("frame_instance_id" not in c for c in cands)
    # geen gevel-/aanzichttekening -> geen candidates
    for title in ("PLATTEGROND", "WONING", "DOORSNEDE"):
        _, _, none_, g_, d_ = analyse(pdf_page(tmp_path, f"{title}.pdf", title=title))
        assert none_ == [] and g_ == [] and "skipped" in d_


def test_same_symbol_candidates_are_not_same_physical_components(fixture_doc):
    _, _, cands, groups, _ = analyse(fixture_doc["pages"][0])
    assert len(groups) == 1 and groups[0]["count"] == 6 and groups[0]["status"] == "SAME_SYMBOL_CANDIDATE" and groups[0]["same_physical_component"] is False
    members = set(groups[0]["member_candidate_ids"])
    door = next(c for c in cands if c["possible_type"] == "EXTERIOR_DOOR")
    assert door["candidate_id"] not in members  # andere structuur/afmeting
    page = fixture_doc["pages"][0]
    sigs = {vdr.symbol_signature(page, c["bbox"]) for c in cands if c["candidate_id"] in members}
    assert len(sigs) == 1


# --- geen netwerk / betaalde API / niets veranderd --------------------------------------------

def test_no_paid_api_or_network_in_new_code(monkeypatch, tmp_path):
    forbidden = re.compile(r"^\s*(import|from)\s+(anthropic|openai|requests|urllib|http|socket|fitz|pymupdf|pytesseract|easyocr|httpx|aiohttp)\b", re.M)
    for name in ("frame_inventory.py", "vector_drawing_reader.py", "vector_drawing_source_audit.py", "build_frame_inventory.py", "record_frame_presence_decisions.py"):
        src = open(os.path.join(ROOT, "scripts", name), encoding="utf-8").read()
        assert not forbidden.search(src), name
    for req in ("requirements-pipeline.txt",):
        text = "\n".join(ln for ln in open(os.path.join(ROOT, req), encoding="utf-8").read().lower().splitlines() if not ln.lstrip().startswith("#"))
        assert "pymupdf" not in text and "fitz" not in text and "anthropic" not in text and "openai" not in text

    def blocked(*a, **k):
        raise AssertionError("netwerkverkeer is niet toegestaan")
    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    doc = vdr.read_document(FIXTURE, "TESTFIX", is_test_fixture=True)
    analyse(doc["pages"][0])
    bfi.build()


def test_existing_artifacts_unchanged():
    for rel, expected in OLD_HASHES.items():
        assert sha(os.path.join(ROOT, rel)) == expected, rel  # quantity bundles, evidence, resoluties, crosswalk, links, observaties
    for rel, expected in FROZEN.items():
        assert sha(os.path.join(ROOT, rel)) == expected, rel  # officiële KG-data en MJOP-App-snapshots


def test_quantity_resolutions_zero_and_crosswalk_decisions_unchanged():
    assert load(os.path.join(ROOT, "data", "quantity_resolutions", "quantity_resolution_records.json"))["records"] == []
    cw = load(os.path.join(ROOT, "data", "crosswalk_decisions", "crosswalk_decision_records.json"))["records"]
    assert [r["decision_id"] for r in cw] == [f"XWD-0000{i}" for i in range(1, 7)] and all(r["status"] == "ACTIVE" for r in cw)


def test_no_app_code_in_repo_and_no_quantity_bundle_for_frames():
    assert not [p for p in os.listdir(os.path.join(ROOT, "..")) if p.lower().startswith("mjop-app")]
    bundles = os.path.join(ROOT, "reports", "quantity", "app_bundles")
    for name in os.listdir(bundles):
        text = open(os.path.join(bundles, name), encoding="utf-8").read()
        assert "frame_inventory" not in text and "FRAME_PAINTING_AREA" not in text and "EXTERIOR_WINDOW" not in text


def test_committed_frame_outputs_are_current():
    for script in ("build_frame_inventory.py", "build_component_inventory.py", "building_element_inventory_report.py"):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), "--check"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, script + r.stdout + r.stderr
    store, repeat, rep = bfi.build()
    assert open(fi.FRAME_INVENTORY, encoding="utf-8").read() == fi.dumps(store)
    assert open(fi.REPEAT_GROUPS, encoding="utf-8").read() == fi.dumps(repeat)
    assert fi.dumps(bfi.build()[2]) == fi.dumps(rep)
    again = bfi.build()
    assert fi.dumps(again[0]) == fi.dumps(store)


def test_schemas_are_valid_json_schema():
    for n in ("frame_component_instance", "frame_group", "frame_inventory", "component_repeat_group"):
        jsonschema.Draft7Validator.check_schema(load(os.path.join(ROOT, "schemas", f"{n}.schema.json")))
    bfi.validate_schema(load(fi.FRAME_INVENTORY), "frame_inventory")
    bfi.validate_schema(load(fi.REPEAT_GROUPS), "component_repeat_group")
