"""Tests voor Maldenhof Quantity Activation v1.

Controleert de vastgelegde menselijke besluiten (building links, crosswalk) en de daaruit afgeleide echte evidence,
en dat historische dakbedekking (ROOF_COVERING_REPORTED_AREA) en 3D BAG plat dakoppervlak (ROOF_FLAT_AREA)
verwante maar NIET gelijke onderwerpen blijven: naast elkaar, verschil als bronverschil, geen gemiddelde, geen
resolutie over beide, geen automatische winnaar. Alles read-only; er wordt niets in data/ geschreven.
"""
import json
import os
import sys
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import maldenhof_quantity_activation as mqa  # noqa: E402
import quantity_evidence as qe  # noqa: E402

T = "2026-10-05T10:00:00Z"
APPROVED = sorted("""0363100012137996 0363100012102659 0363100012078022 0363100012140664 0363100012141419 0363100012091974
0363100012070344 0363100012107492 0363100012071880 0363100012144766 0363100012091756 0363100012143647 0363100012121455
0363100012134188 0363100012127361""".split())
SCOPE = "BAG:" + "+".join(APPROVED)
DOCS = ("DOC-005", "DOC-006")
NEW_HSM = "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006"
REL = "SREL-ROOF_COVERING_REPORTED_AREA-ROOF_FLAT_AREA"


@pytest.fixture(scope="module")
def links():
    return bl.load_store()


@pytest.fixture(scope="module")
def evidence():
    return json.load(open(bqe.OUT_EVIDENCE, encoding="utf-8"))


@pytest.fixture(scope="module")
def vocab():
    return json.load(open(xw.SUBJECTS, encoding="utf-8"))


def _active(links, doc, status):
    return sorted(r["bag_pand_id"] for r in links["records"]
                  if r["document_id"] == doc and r["status"] == "ACTIVE" and r["link_status"] == status)


# --- building links -----------------------------------------------------------------------

@pytest.mark.parametrize("doc", DOCS)
def test_exactly_the_15_approved_panden_are_confirmed(links, doc):
    assert _active(links, doc, "CONFIRMED") == APPROVED
    assert bl.active_links(links)[doc] == APPROVED


@pytest.mark.parametrize("doc", DOCS)
def test_all_other_candidates_are_rejected_and_have_other_postcode(links, doc):
    rep = json.load(open(bl.OUT_JSON, encoding="utf-8"))
    cands = next(o for o in rep["documents"] if o["document_id"] == doc)["candidate_bag_panden"]
    others = sorted(c["bag_pand_id"] for c in cands if c["bag_pand_id"] not in APPROVED)
    assert len(others) == 25 and _active(links, doc, "REJECTED") == others
    for c in cands:
        pcs = {a["postcode"] for a in c["addresses"]}
        assert pcs == {"1106EZ"} if c["bag_pand_id"] in APPROVED else pcs <= {"1106EH", "1106EJ"}


def test_link_records_are_human_append_only_and_cite_the_snapshot(links):
    mald = [r for r in links["records"] if r["document_id"] in DOCS]  # andere documenten (bijv. DOC-012) tellen niet mee
    assert bl.store_errors(links) == [] and len(mald) == 80
    snaps = {"DOC-005": "BAGSNAP-431559474da45dcf", "DOC-006": "BAGSNAP-e23aa139a8589881"}
    for r in mald:
        assert r["reviewer"] == {"reviewer_id": "user-approved", "reviewer_type": "human"}
        assert r["evidence"]["snapshot_id"] == snaps[r["document_id"]] and r["supersedes"] is None
        assert ("1106 EZ" in r["decision_reason"]) == (r["link_status"] == "CONFIRMED")


def test_multi_pand_scope_is_exactly_the_15_panden(evidence):
    assert bqe.building_id_for(APPROVED) == SCOPE
    scope_ids = {e["building_id"] for e in evidence["evidence"] if "+" in e["building_id"]}
    assert scope_ids == {SCOPE}
    rep = json.load(open(mqa.OUT_JSON, encoding="utf-8"))
    assert rep["building_id"] == SCOPE and rep["scope_identical_for_documents"] and rep["bag_pand_ids"] == APPROVED


# --- crosswalk / mappings -----------------------------------------------------------------

def test_crosswalk_decisions():
    eff = xw.effective()
    assert eff["XW-dak-plat-4711-m2"]["status"] == "VERIFIED" and eff["XW-dak-plat-4711-m2"]["human_verified"]
    assert eff["HSM-ROOF_FLAT_AREA-4711-m2"]["status"] != "VERIFIED"
    assert eff["HSM-ROOF_FLAT_AREA-4711-m2"]["decision_id"] is None
    assert eff[NEW_HSM]["status"] == "VERIFIED"
    recs = {r["mapping_id"]: r for r in xw.load_store()["records"] if r["mapping_id"] in ("XW-dak-plat-4711-m2", NEW_HSM)}
    assert set(recs) == {"XW-dak-plat-4711-m2", NEW_HSM}
    assert [r["decision_id"] for r in xw.load_store()["records"] if r["mapping_id"] in recs] == ["XWD-00001", "XWD-00002"]
    assert "NIET" in recs["XW-dak-plat-4711-m2"]["decision_reason"] and "b3_opp_dak_plat" in recs["XW-dak-plat-4711-m2"]["decision_reason"]
    assert all(r["decision"] == "VERIFY" and r["reviewer"]["reviewer_type"] == "human" for r in recs.values())


def test_new_subject_and_relation(vocab):
    s = next(x for x in vocab["subjects"] if x["subject_key"] == "ROOF_COVERING_REPORTED_AREA")
    assert (s["unit"], s["quantity_kind"], s["method_class"]) == ("m2", "ELEMENT_QUANTITY", "SOURCE_REPORTED")
    assert s["label_nl"] == "Door bron/MJOP gerapporteerde oppervlakte dakbedekking"
    assert not any(r["subject_key"] == "ROOF_COVERING_REPORTED_AREA" for r in vocab["bag3d_rules"])
    assert all("ROOF_COVERING_REPORTED_AREA" not in r["applies_to_subjects"] for r in vocab["scope_aggregation_rules"])
    rel = next(r for r in vocab["subject_relations"] if r["relation_id"] == REL)
    assert rel["relation"] == "RELATED_NOT_EQUIVALENT" and sorted(rel["subjects"]) == ["ROOF_COVERING_REPORTED_AREA", "ROOF_FLAT_AREA"]
    assert rel["resolvable_as_same_quantity"] is False and rel["show_side_by_side"] is True
    assert (rel["average"], rel["single_resolution"], rel["auto_select_winner"]) == (False, False, False)
    assert bqe.related_subjects(vocab, "ROOF_FLAT_AREA") == {"ROOF_COVERING_REPORTED_AREA": REL}


def test_document_specific_mapping_is_exact_not_generic(vocab):
    m = next(x for x in vocab["historical_subject_mappings"] if x["mapping_id"] == NEW_HSM)
    qos = json.load(open(bqe.QO_PATH, encoding="utf-8"))["observations"]
    hits = sorted(o["quantity_observation_id"] for o in qos if bqe.mapping_matches(m, o))
    assert hits == ["QO-DOC-005-EL-025", "QO-DOC-006-EL-025"]
    # andere 4711-m2-rijen (ballast, liftdak, 'Dakbedekking app' kleine letters) en m1-rijen vallen er buiten
    other_4711 = [o for o in qos if o["element"]["element_code_internal"] == "4711" and o["quantity_observation_id"] not in hits]
    assert len(other_4711) > 10 and not any(bqe.mapping_matches(m, o) for o in other_4711)
    o = next(x for x in qos if x["quantity_observation_id"] == "QO-DOC-005-EL-025")
    fuzzy = json.loads(json.dumps(o))
    fuzzy["element"]["element_description_original"] = "Dakbedekking APP "
    assert not bqe.mapping_matches(m, fuzzy)


# --- evidence ---------------------------------------------------------------------------

def test_3dbag_aggregate_is_exactly_190_65(evidence):
    by_id = {e["evidence_id"]: e for e in evidence["evidence"]}
    aggs = [e for e in evidence["evidence"] if e["building_id"] == SCOPE and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"]
    assert len(aggs) == 1
    a = aggs[0]
    assert (a["value"], a["unit_normalized"], a["method_class"], a["status"]) == ("190.65", "m2", "GEOMETRY_DERIVED", "PROPOSED")
    kids = [by_id[c] for c in a["calculation"]["input_evidence_ids"]]
    assert sorted(k["source_ref"]["bag_pand_id"] for k in kids) == APPROVED
    assert all(k["building_id"] == "BAG:" + k["source_ref"]["bag_pand_id"] and k["method_class"] == "DIRECT_MEASURED" for k in kids)
    assert sum(Decimal(k["value"]) for k in kids) == Decimal("190.65")
    assert a["source_ref"]["missing_bag_pand_ids"] == [] and evidence["scope_aggregates_not_published"] == []
    assert all(qe.evidence_errors(e) == [] for e in evidence["evidence"])


def test_historical_is_roof_covering_unsplit_at_complex_level(evidence):
    hist = [e for e in evidence["evidence"] if e["source_type"] == "MJOP_ELEMENT_OVERVIEW" and e["source_ref"]["document_id"] in DOCS
            and e["source_ref"]["subject_mapping_ref"] == NEW_HSM]  # dakpannen (ROOF_TILES) apart, zie test_sloped_roof_activation
    assert sorted(e["source_ref"]["document_id"] for e in hist) == ["DOC-005", "DOC-006"]
    for e in hist:
        assert e["quantity_subject"]["subject_key"] == "ROOF_COVERING_REPORTED_AREA"
        assert e["quantity_subject"]["subject_key"] != "ROOF_FLAT_AREA"
        assert (e["value"], e["unit_normalized"], e["method_class"]) == ("425.80", "m2", "SOURCE_REPORTED")
        assert e["building_id"] == SCOPE  # complexniveau, aan geen enkel pand gehangen
        assert e["source_ref"]["subject_mapping_ref"] == NEW_HSM
    assert not any(e["source_type"] == "MJOP_ELEMENT_OVERVIEW" and "+" not in e["building_id"]
                   for e in evidence["evidence"] if e["source_ref"].get("document_id") in DOCS)
    assert not any(e["source_type"] == "MJOP_ELEMENT_OVERVIEW" and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"
                   for e in evidence["evidence"])


def test_doc005_doc006_dependency_kept_not_two_observations(evidence):
    hist = {e["source_ref"]["document_id"]: e for e in evidence["evidence"]
            if e["source_type"] == "MJOP_ELEMENT_OVERVIEW" and e["source_ref"]["document_id"] in DOCS
            and e["quantity_subject"]["subject_key"] == "ROOF_COVERING_REPORTED_AREA"}
    assert "DOC-006" in hist["DOC-005"]["dependency"]["same_object_document_ids"]
    assert "DOC-005" in hist["DOC-006"]["dependency"]["same_object_document_ids"]
    assert hist["DOC-005"]["dependency"]["identical_in_same_object_documents"] == ["QO-DOC-006-EL-025"]
    assert len({e["dependency"]["source_cluster"] for e in hist.values()}) == 1
    rep = json.load(open(bqe.OUT_JSON, encoding="utf-8"))
    ind = [h for h in rep["summary"]["historical_independent_sources"] if h["building_id"] == SCOPE and h["subject_key"] == "ROOF_COVERING_REPORTED_AREA"]
    assert ind == [{"building_id": SCOPE, "subject_key": "ROOF_COVERING_REPORTED_AREA", "historical_evidences": 2,
                    "independent_source_clusters": 1}]
    assert all(c["dependency_note"] and "geen onafhankelijke bevestiging" in c["dependency_note"]
               for c in rep["comparisons"] if c["building_id"] == SCOPE)


def test_difference_is_source_difference_not_accuracy_statistic():
    rep = json.load(open(bqe.OUT_JSON, encoding="utf-8"))
    cs = [c for c in rep["comparisons"] if c["building_id"] == SCOPE and c["subject_key"] == "ROOF_COVERING_REPORTED_AREA"]
    assert len(cs) == 2
    for c in cs:
        assert (c["subject_key"], c["bag3d_subject_key"]) == ("ROOF_COVERING_REPORTED_AREA", "ROOF_FLAT_AREA")
        assert c["comparison_kind"] == "RELATED_SUBJECT_NOT_EQUIVALENT" and c["subject_relation_id"] == REL
        assert c["review_status"] == "NOT_RESOLVABLE_AS_SAME_QUANTITY" and "DIFFERENT_SUBJECT_DEFINITION" in c["mismatch_reasons"]
        assert c["absolute_difference"] == "235.15" and c["difference_band"] is None
    s = rep["summary"]
    assert s["comparisons_with_difference"] == 0 and s["median_absolute_difference"] is None
    assert sum(1 for c in rep["comparisons"] if c["building_id"] == SCOPE and c["subject_key"] == "ROOF_COVERING_REPORTED_AREA" and c["comparison_kind"] != "SAME_SUBJECT") == 2


# --- geen resolutie, geen middeling -------------------------------------------------------

def test_no_quantity_resolution_written():
    store = json.load(open(os.path.join(ROOT, "data", "quantity_resolutions", "quantity_resolution_records.json"), encoding="utf-8"))
    assert store["records"] == []
    rep = json.load(open(mqa.OUT_JSON, encoding="utf-8"))
    assert rep["quantity_resolution"]["records_for_scope"] == 0
    assert all(v is None for v in rep["quantity_resolution"]["active_resolution"].values())


def test_one_resolution_over_both_subjects_or_an_average_is_refused(evidence):
    idx = {e["evidence_id"]: e for e in evidence["evidence"]}
    flat = next(e for e in evidence["evidence"] if e["building_id"] == SCOPE and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA")
    hist = next(e for e in evidence["evidence"] if e["building_id"] == SCOPE and e["source_type"] == "MJOP_ELEMENT_OVERVIEW")
    assert flat["quantity_subject"]["subject_id"] != hist["quantity_subject"]["subject_id"]
    # één resolutie die beide onderwerpen afweegt: geweigerd (ander onderwerp)
    with pytest.raises(qe.QuantityEvidenceError, match="ander gebouw/onderwerp"):
        qe.record_resolution(qe.new_store(), building_id=SCOPE, subject_id=flat["quantity_subject"]["subject_id"],
                             decision="ACCEPT_EVIDENCE", considered_evidence_ids=[flat["evidence_id"], hist["evidence_id"]],
                             selected_evidence_id=flat["evidence_id"], decision_reason="test", reviewer_id="t",
                             reviewed_at=T, evidence_index=idx)
    # een gemiddelde (308.225) kan nooit als resolved_value ontstaan
    rec = {"resolution_id": "QRR-T", "building_id": SCOPE, "subject_id": flat["quantity_subject"]["subject_id"],
           "decision": "ACCEPT_EVIDENCE", "selected_evidence_id": flat["evidence_id"], "manual_evidence_id": None,
           "resolved_value": str((Decimal(flat["value"]) + Decimal(hist["value"])) / 2), "resolved_unit": "m2",
           "considered_evidence_ids": [flat["evidence_id"]], "decision_reason": "test",
           "reviewer": {"reviewer_id": "t", "reviewer_type": "human"}}
    assert any("middelen" in e for e in qe.validate_resolution(rec, idx))


# --- app-bundel ---------------------------------------------------------------------------

def test_bundle_shows_both_semantics_separately(evidence, vocab):
    app = json.load(open(xw.APP_CROSSWALK, encoding="utf-8"))
    b = eab.build_bundle(SCOPE, evidence["evidence"], app, xw.effective(), vocab, app_elements={"dak-plat"})
    assert b["bundle_version"] == "mjop_app_quantity_bundle_v3"
    assert b["building_scope"] == {"building_id": SCOPE, "kind": "MULTI_PAND_SCOPE", "bag_pand_ids": APPROVED, "pand_count": 15}
    prim = [e for e in b["entries"] if e["role"] == "PRIMARY"]
    ctx = [e for e in b["entries"] if e["role"] == "RELATED_CONTEXT"]
    assert len(prim) == 1 and prim[0]["selectable"] is True and prim[0]["subject_key"] == "ROOF_FLAT_AREA"
    assert prim[0]["evidence"]["value"] == "190.65" and len(prim[0]["evidence"]["components"]) == 15
    assert len(ctx) == 2 and {e["evidence"]["source_ref"]["document_id"] for e in ctx} == set(DOCS)
    for e in ctx:
        assert e["selectable"] is False and e["subject_key"] == "ROOF_COVERING_REPORTED_AREA"
        assert e["primary_subject_key"] == "ROOF_FLAT_AREA" and e["subject_relation"]["relation"] == "RELATED_NOT_EQUIVALENT"
        assert e["subject_relation"]["resolvable_as_same_quantity"] is False
        assert e["evidence"]["value"] == "425.80" and e["evidence"]["scope_level"] == "COMPLEX"
        assert e["app_element_key"] == "dak-plat" and e["crosswalk_mapping_id"] == "XW-dak-plat-4711-m2"


def test_bundle_without_vocab_stays_v2(evidence):
    app = json.load(open(xw.APP_CROSSWALK, encoding="utf-8"))
    b = eab.build_bundle(SCOPE, evidence["evidence"], app, xw.effective(), app_elements={"dak-plat"})
    assert b["bundle_version"] == "mjop_app_quantity_bundle_v2"
    assert [e["subject_key"] for e in b["entries"]] == ["ROOF_FLAT_AREA"] and "role" not in b["entries"][0]


def test_activation_report_up_to_date():
    r = mqa.build()
    assert open(mqa.OUT_JSON, encoding="utf-8").read() == json.dumps(r, ensure_ascii=False, indent=1) + "\n"
    assert open(mqa.OUT_MD, encoding="utf-8").read() == mqa.render(r)
    assert r["historical_independent_source_clusters"] == 1
    assert r["mapping_status"] == {"XW-dak-plat-4711-m2": "VERIFIED", "HSM-ROOF_FLAT_AREA-4711-m2": "PROPOSED", NEW_HSM: "VERIFIED"}
