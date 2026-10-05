"""Tests voor building links, BAG-snapshots, 3D BAG-regels, crosswalk-verificatie, building quantity evidence,
de 3D BAG-vs-historisch-vergelijking en de app-bundel (docs/building_link_3dbag_evidence_v1.md).

Alle PDOK/BAG/3D BAG-antwoorden in deze tests zijn vaste, zelfgemaakte testantwoorden (fake_http) — geen
echte gebouwgegevens. Ze worden nergens in data/ geschreven."""
import copy
import json
import os
import subprocess
import sys
import urllib.parse
from decimal import Decimal

import jsonschema
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import append_only_store as aos  # noqa: E402
import bag3d_quantity_rules as rules_mod  # noqa: E402
import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import quantity_evidence as qe  # noqa: E402

T = "2026-10-01T10:00:00Z"
LON, LAT, D = 4.95, 52.30, 0.0001
EVIDENCE_SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "quantity_evidence.schema.json")))


# --- fake PDOK / BAG / 3D BAG ----------------------------------------------------

def ring(lon, lat):
    return [[lon - D, lat - D], [lon + D, lat - D], [lon + D, lat + D], [lon - D, lat + D], [lon - D, lat - D]]


def fake_http(pand_specs, address_docs):
    """pand_specs: {pand_id: (lon, lat, attrs)}; address_docs: PDOK-docs."""
    calls = []

    def get(url):
        calls.append(url)
        if "locatieserver" in url:
            return 200, {"response": {"docs": address_docs}}
        if "bag/ogc" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            x1, y1, x2, y2 = [float(v) for v in q["bbox"][0].split(",")]
            feats = [{"geometry": {"type": "Polygon", "coordinates": [ring(lo, la)]},
                      "properties": {"identificatie": pid, "bouwjaar": 1981, "status": "Pand in gebruik"}}
                     for pid, (lo, la, _) in pand_specs.items() if x1 <= lo <= x2 and y1 <= la <= y2]
            return 200, {"features": feats}
        if "3dbag" in url:
            pid = url.rsplit(".", 1)[1]
            return 200, {"metadata": {"version": "v2099.01.01-test"},
                         "feature": {"CityObjects": {"NL.IMBAG.Pand." + pid: {"attributes": pand_specs[pid][2]}}}}
        return 404, {}
    get.calls = calls
    return get


def addr(street, nr, postcode, lon=LON, lat=LAT, pid="adr-1"):
    return {"id": pid, "weergavenaam": f"{street} {nr}, {postcode} Amsterdam", "straatnaam": street, "huisnummer": int(nr),
            "postcode": postcode.replace(" ", ""), "woonplaatsnaam": "Amsterdam", "centroide_ll": f"POINT({lon} {lat})"}


ATTRS = {"b3_opp_dak_plat": 312.64, "b3_opp_dak_schuin": 0, "b3_opp_buitenmuur": 1099.7, "b3_h_dak_max": 13.4,
         "b3_h_maaiveld": 0.6, "b3_opp_grond": 318.2, "b3_bouwlagen": 4, "b3_dak_type": "horizontal"}


@pytest.fixture
def snapshot():
    http = fake_http({"0363100000000001": (LON, LAT, ATTRS)}, [addr("Teststraat", "240", "1106 EZ"), addr("Teststraat", "242", "1106 EZ", pid="x")])
    return bs.fetch_snapshot("DOC-005", "Teststraat", "240", "1106 EZ", "Amsterdam", http_get=http, fetched_at=T)


@pytest.fixture
def docs():
    base = {"address_provenance": {"document_id": "DOC-005", "page": 2, "text_fragment": "Adres Teststraat 240"},
            "postcode": "1106 EZ", "city": "Amsterdam", "object_name": "VvE Teststraat 240", "construction_year": 1981,
            "number_of_units": 29, "verified_sha256": "0" * 64}
    return {"DOC-005": dict(base, address_as_stated="Teststraat 240"),
            "DOC-006": dict(base, address_as_stated="Teststraat 240"),
            "DOC-001": dict(base, address_as_stated="Astraat 1-83 en Bstraat 189-217", postcode=None)}


# --- adres ontleden ---------------------------------------------------------------

def test_parse_address_variants():
    assert [p["kind"] for p in bl.parse_address("Alkmaarstraat 1-83 en Groetstraat 189-217")] == ["range", "range"]
    assert bl.parse_address("Maldenhof 240 - 296")[0]["numbers"] == ["240", "296"]
    assert bl.parse_address("Vechtstraat 13-15-17-19")[0]["numbers"] == ["13", "15", "17", "19"]
    assert bl.parse_address("J.P Heijestraat 144, Wilhelminastraat 74")[0]["street"] == "J.P Heijestraat"
    assert bl.parse_address(None) == []


def test_postcode_only_used_for_single_address():
    plan = bl.lookup_plan(bl.parse_address("Astraat 1, Bstraat 2"), "1000 AA", "Amsterdam")
    assert all(p["postcode"] is None for p in plan)
    assert bl.lookup_plan(bl.parse_address("Astraat 1"), "1000 AA", "X")[0]["postcode"] == "1000 AA"


# --- snapshots --------------------------------------------------------------------

def test_snapshot_is_exact_and_content_addressed(snapshot):
    assert bs.snapshot_errors(snapshot) == []
    assert [m["exact_match"] for m in snapshot["address_matches"]] == [True, False]
    assert [p["bag_pand_id"] for p in snapshot["panden"]] == ["0363100000000001"]
    assert snapshot["panden"][0]["threedbag"]["attributes"]["b3_opp_dak_plat"] == 312.64
    assert snapshot["panden"][0]["threedbag"]["api_version"] == "v2099.01.01-test"
    tampered = copy.deepcopy(snapshot)
    tampered["panden"][0]["threedbag"]["attributes"]["b3_opp_dak_plat"] = 999
    assert bs.snapshot_errors(tampered)


def test_snapshot_no_fuzzy_address_match():
    http = fake_http({"0363100000000001": (LON, LAT, ATTRS)}, [addr("Teststraatje", "240", "1106 EZ")])
    snap = bs.fetch_snapshot("DOC-005", "Teststraat", "240", "1106 EZ", None, http_get=http, fetched_at=T)
    assert snap["address_matches"][0]["exact_match"] is False
    assert snap["panden"] == []                      # geen pand opgevraagd voor een niet-exact adres


def test_snapshot_network_failure_raises():
    def broken(url):
        raise bs.SnapshotError("egress geweigerd")
    with pytest.raises(bs.SnapshotError):
        bs.fetch_snapshot("DOC-005", "Teststraat", "240", None, None, http_get=broken)


def test_write_snapshot_never_overwrites(tmp_path, snapshot):
    p = bs.write_snapshot(snapshot, tmp_path)
    before = p.read_text(encoding="utf-8")
    assert bs.write_snapshot(snapshot, tmp_path) == p and p.read_text(encoding="utf-8") == before
    assert [s["snapshot_id"] for s in bs.load_snapshots(tmp_path)] == [snapshot["snapshot_id"]]


# --- building links ------------------------------------------------------------------

def test_candidates_report_decides_nothing(snapshot, docs):
    rels = {"relations": [{"relation_id": "DREL-X", "type": "version_of_same_mjop", "document_ids": ["DOC-005", "DOC-006"]}]}
    comp = {"source_clusters": [{"source_cluster": "SC-DOC-005+DOC-006", "document_ids": ["DOC-005", "DOC-006"]},
                                {"source_cluster": "SC-DOC-001", "document_ids": ["DOC-001"]}]}
    rep = bl.build_candidates(docs=docs, snapshots=[snapshot], store=bl.new_store(), relations=rels, comparability=comp)
    by = {d["document_id"]: d for d in rep["documents"]}
    assert by["DOC-005"]["status"] == "CANDIDATES_READY_FOR_REVIEW"
    assert by["DOC-005"]["confirmed_bag_pand_ids"] == []
    assert by["DOC-006"]["status"] == "AWAITING_BAG_SNAPSHOT"          # snapshot van DOC-005 geldt niet vanzelf
    assert {"MULTIPLE_STREETS", "ADDRESS_RANGE", "POSTCODE_MISSING"} <= set(by["DOC-001"]["review_reasons"])
    assert rep["summary"]["confirmed_links"] == 0


def test_record_link_requires_human_reviewer_and_candidate(snapshot, docs):
    with pytest.raises(bl.LinkError):
        bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                       reviewer_id="", reason="x", reviewed_at=T, documents=docs)
    with pytest.raises(bl.LinkError):  # vrij ingetypt pand-ID
        bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363199999999999", snapshot=snapshot,
                       reviewer_id="r", reason="x", reviewed_at=T, documents=docs)
    with pytest.raises(bl.LinkError):  # snapshot van een ander document
        bl.record_link(bl.new_store(), document_id="DOC-006", bag_pand_id="0363100000000001", snapshot=snapshot,
                       reviewer_id="r", reason="x", reviewed_at=T, documents=docs)


def test_link_store_append_only_and_supersede(snapshot, docs):
    s1 = bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                        reviewer_id="test-reviewer", reason="adres exact", reviewed_at=T, documents=docs)
    r = s1["records"][0]
    assert r["reviewer"] == {"reviewer_id": "test-reviewer", "reviewer_type": "human"}
    assert r["link_status"] == "CONFIRMED" and r["status"] == "ACTIVE"
    assert bl.active_links(s1) == {"DOC-005": ["0363100000000001"]}
    s2 = bl.record_link(s1, document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                        reviewer_id="test-reviewer", reason="toch niet", reviewed_at=T, link_status="REJECTED", documents=docs)
    assert [x["status"] for x in s2["records"]] == ["SUPERSEDED", "ACTIVE"]
    assert bl.active_links(s2) == {}
    assert aos.append_only_errors(s1["records"], s2["records"], "link_id") == [] and bl.store_errors(s2) == []
    edited = copy.deepcopy(s2)
    edited["records"][0]["reviewer"]["reviewer_id"] = "iemand anders"
    assert aos.append_only_errors(s2["records"], edited["records"], "link_id")
    assert s1["records"][0]["status"] == "ACTIVE"  # invoer niet gemuteerd


def test_multi_pand_links():
    specs = {"0363100000000011": (LON, LAT, ATTRS), "0363100000000012": (LON + 0.001, LAT, ATTRS)}
    docs_ = [addr("Astraat", "1", "1000 AA"), addr("Bstraat", "2", "1000 AB", lon=LON + 0.001, pid="b")]
    http = fake_http(specs, docs_)
    s_a = bs.fetch_snapshot("DOC-001", "Astraat", "1", None, "Amsterdam", http_get=http, fetched_at=T)
    s_b = bs.fetch_snapshot("DOC-001", "Bstraat", "2", None, "Amsterdam", http_get=http, fetched_at=T)
    d = {"DOC-001": {"address_as_stated": "Astraat 1, Bstraat 2", "address_provenance": None, "postcode": None, "city": "Amsterdam",
                     "object_name": None, "construction_year": None, "number_of_units": None, "verified_sha256": "0" * 64}}
    s = bl.record_link(bl.new_store(), document_id="DOC-001", bag_pand_id="0363100000000011", snapshot=s_a,
                       reviewer_id="t", reason="a", reviewed_at=T, documents=d)
    s = bl.record_link(s, document_id="DOC-001", bag_pand_id="0363100000000012", snapshot=s_b,
                       reviewer_id="t", reason="b", reviewed_at=T, documents=d)
    assert bl.active_links(s) == {"DOC-001": ["0363100000000011", "0363100000000012"]}
    assert bqe.building_id_for(bl.active_links(s)["DOC-001"]) == "BAG:0363100000000011+0363100000000012"


def test_committed_stores_contain_only_human_decisions():
    # sinds Maldenhof Quantity Activation v1 bevatten de stores de expliciete menselijke besluiten van de gebruiker
    links = json.load(open(bl.LINK_STORE))
    assert bl.store_errors(links) == []
    assert links["records"] and all(r["reviewer"]["reviewer_type"] == "human" and r["reviewer"]["reviewer_id"] for r in links["records"])
    assert {r["document_id"] for r in links["records"]} == {"DOC-005", "DOC-006", "DOC-012"}
    dec = json.load(open(xw.DECISIONS))
    assert xw.store_errors(dec) == []
    assert all(r["reviewer"]["reviewer_type"] == "human" for r in dec["records"])
    assert {r["mapping_id"] for r in dec["records"]} == {"XW-dak-plat-4711-m2", "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006",
                                                         "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012",
                                                         "XQ-dak-hellend-ROOF_SLOPED_AREA-m2",
                                                         "XQ-steiger-OUTER_WALL_GROSS_AREA-m2",
                                                         "HSM-ROOF_TILES_REPORTED_AREA-4712-m2-DOC-005-006"}
    # snapshots zijn ruwe bronvastleggingen (geen besluiten); sinds multi-pand-quantity-scope-v1 bestaan de
    # canonieke Maldenhof-snapshots voor DOC-005/DOC-006
    assert all(n == "README.md" or n.startswith("BAGSNAP-") for n in os.listdir(bs.SNAPSHOT_DIR))


# --- 3D BAG-regels --------------------------------------------------------------------

def test_rules_exact_no_rounding():
    res = {r["rule_id"]: r for r in rules_mod.apply_rules(ATTRS)}
    assert res["bag3d.roof_flat_area"]["value"] == "312.64"
    assert res["bag3d.roof_sloped_area"]["value"] == "0"
    assert res["bag3d.roof_total_area"]["value"] == "312.64"
    assert res["bag3d.outer_wall_gross_area"]["value"] == "1099.7"
    assert res["bag3d.building_height"]["value"] == "12.8"          # 13.4 - 0.6 exact, geen float-ruis
    assert res["bag3d.roof_flat_area"]["raw_inputs"] == {"b3_opp_dak_plat": 312.64}


def test_rules_missing_field_not_available():
    res = {r["rule_id"]: r for r in rules_mod.apply_rules({"b3_opp_dak_plat": 100})}
    assert res["bag3d.roof_total_area"]["status"] == "NOT_AVAILABLE" and res["bag3d.roof_total_area"]["value"] is None
    assert res["bag3d.building_height"]["missing_fields"] == ["b3_h_dak_max", "b3_h_maaiveld"]


def test_rule_fields_are_used_in_mjop_app():
    _, vocab = rules_mod.load_rules()
    assert vocab["bag3d_field_verification"]["status"] == "USED_IN_MJOP_APP_NOT_VERIFIED_AGAINST_LIVE_API"
    app_fields = {"b3_opp_dak_plat", "b3_opp_dak_schuin", "b3_opp_buitenmuur", "b3_h_dak_max", "b3_h_maaiveld",
                  "b3_opp_grond", "b3_bouwlagen", "b3_dak_type"}
    assert {f for r in vocab["bag3d_rules"] for f in r["fields"]} <= app_fields


# --- crosswalk -----------------------------------------------------------------------------

def test_crosswalk_nothing_verified_without_human_decision():
    eff = xw.effective(store=xw.new_store())
    assert all(not e["human_verified"] for e in eff.values())
    assert all(e["status"] != "VERIFIED" for e in eff.values())
    # gecommitte opslag: alleen de expliciete menselijke besluiten van Maldenhof Quantity Activation v1
    committed = xw.effective()
    assert sorted(k for k, v in committed.items() if v != eff[k]) == ["HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006",
                                                                       "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012",
                                                                       "HSM-ROOF_TILES_REPORTED_AREA-4712-m2-DOC-005-006",
                                                                       "XQ-dak-hellend-ROOF_SLOPED_AREA-m2",
                                                                       "XQ-steiger-OUTER_WALL_GROSS_AREA-m2",
                                                                       "XW-dak-plat-4711-m2"]


def test_crosswalk_verify_reject_and_changed_proposal():
    props = xw.load_proposals()
    s = xw.record_decision(xw.new_store(), mapping_id="XW-dak-plat-4711-m2", decision="VERIFY", reviewer_id="t",
                           reason="m2-dakbedekking = plat dak", reviewed_at=T, proposals=props)
    assert xw.effective(props, s)["XW-dak-plat-4711-m2"]["status"] == "VERIFIED"
    changed = copy.deepcopy(props)
    changed["XW-dak-plat-4711-m2"]["unit"] = "m1"
    assert xw.effective(changed, s)["XW-dak-plat-4711-m2"]["status"] == "REVIEW_REQUIRED"
    s2 = xw.record_decision(s, mapping_id="XW-dak-plat-4711-m2", decision="REJECT", reviewer_id="t", reason="toch niet",
                            reviewed_at=T, proposals=props)
    assert xw.effective(props, s2)["XW-dak-plat-4711-m2"]["status"] == "REJECTED"
    assert aos.append_only_errors(s["records"], s2["records"], "decision_id") == []
    with pytest.raises(xw.CrosswalkError):
        xw.record_decision(xw.new_store(), mapping_id="XW-bestaat-niet", decision="VERIFY", reviewer_id="t", reason="x", reviewed_at=T)


def test_crosswalk_unresolved_items_documented():
    app = json.load(open(xw.APP_CROSSWALK))
    codes = {u.get("internal_element_code") for u in app["unresolved"]}
    assert {"5211", "4711"} <= codes
    assert all(m["status"] in ("PROPOSED", "REVIEW_REQUIRED") for m in app["mappings"])


# --- evidence + vergelijking (volledige keten met testdata) -----------------------------------

def _qo(doc, eid, code, value, unit, cluster, same=(), review=False, desc="Dakbedekking bitumen"):
    return {"quantity_observation_id": f"QO-{doc}-{eid}", "document_id": doc, "quantity_kind": "ELEMENT_QUANTITY",
            "source_file": {"relative_path": "x.pdf", "sha256": "0" * 64}, "source_cluster": cluster,
            "element": {"element_id": f"{doc}-{eid}", "element_code_original": code, "element_code_internal": code,
                        "element_description_original": desc, "location_original": "Dak", "material_original": None,
                        "material_normalized": None},
            "quantity_value": value, "unit_normalized": unit, "measurable": True, "quantity_as_stated": value.replace(".", ","),
            "provenance": {"document_id": doc, "page": 6, "text_fragment": f"{code} {desc} {value}m2"},
            "extraction_method": "profile:test", "caveats": [], "review_reasons": ["QUANTITY_ONE_IN_MEASURED_UNIT"] if review else [],
            "requires_human_review": review,
            "dependency": {"same_object_document_ids": list(same), "identical_in_same_object_documents": [], "differs_in_same_object_documents": []}}


@pytest.fixture
def chain(snapshot, docs):
    store = bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                           reviewer_id="test-reviewer", reason="test", reviewed_at=T, documents=docs)
    qos = [_qo("DOC-005", "EL-001", "4711", "308.00", "m2", "SC-DOC-005+DOC-006", same=["DOC-006"]),
           _qo("DOC-005", "EL-002", "4711", "32.00", "m1", "SC-DOC-005+DOC-006", desc="Dakrand")]
    props = xw.load_proposals()
    xs = xw.record_decision(xw.new_store(), mapping_id="HSM-ROOF_FLAT_AREA-4711-m2", decision="VERIFY", reviewer_id="t",
                            reason="test", reviewed_at=T, proposals=props)
    xs = xw.record_decision(xs, mapping_id="XW-dak-plat-4711-m2", decision="VERIFY", reviewer_id="t", reason="test",
                            reviewed_at=T, proposals=props)
    eff = xw.effective(props, xs)
    res = bqe.build(links_store=store, snapshots=[snapshot], quantity_observations=qos, crosswalk_effective=eff)
    return res, eff


def test_bag3d_evidence_exact(chain):
    res, _ = chain
    ev = [e for e in res["evidence_store"]["evidence"] if e["source_type"] == "3D_BAG"]
    by = {e["quantity_subject"]["subject_key"]: e for e in ev}
    assert by["ROOF_FLAT_AREA"]["value"] == "312.64" and by["ROOF_FLAT_AREA"]["method_class"] == "DIRECT_MEASURED"
    assert by["ROOF_TOTAL_AREA"]["method_class"] == "GEOMETRY_DERIVED" and by["ROOF_TOTAL_AREA"]["calculation"]["formula"]
    assert by["BUILDING_HEIGHT"]["value"] == "12.8" and by["BUILDING_HEIGHT"]["unit_normalized"] == "m"
    for e in ev:
        jsonschema.validate(e, EVIDENCE_SCHEMA)
        assert e["status"] == "PROPOSED" and qe.evidence_errors(e) == []
        assert e["source_ref"]["fetched_at"] == T and e["source_ref"]["api_version"] == "v2099.01.01-test"
        assert e["building_id"] == "BAG:0363100000000001"


def test_historical_evidence_only_via_verified_mapping(chain, snapshot, docs):
    res, _ = chain
    hist = [e for e in res["evidence_store"]["evidence"] if e["source_type"] == "MJOP_ELEMENT_OVERVIEW"]
    assert len(hist) == 1                                    # alleen de m2-rij; m1-dakrand niet
    h = hist[0]
    assert h["value"] == "308.00" and h["method_class"] == "SOURCE_REPORTED"
    assert h["dependency"]["source_cluster"] == "SC-DOC-005+DOC-006" and h["dependency"]["same_object_document_ids"] == ["DOC-006"]
    assert h["source_ref"]["quantity_observation_id"] == "QO-DOC-005-EL-001" and h["source_ref"]["building_link_ref"] == "BLINK-00001"
    jsonschema.validate(h, EVIDENCE_SCHEMA)
    # zonder geverifieerde mapping: geen historische evidence
    store = bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                           reviewer_id="t", reason="t", reviewed_at=T, documents=docs)
    res2 = bqe.build(links_store=store, snapshots=[snapshot], quantity_observations=[_qo("DOC-005", "EL-001", "4711", "308.00", "m2", "SC")],
                     crosswalk_effective=xw.effective(store=xw.new_store()))
    assert not [e for e in res2["evidence_store"]["evidence"] if e["source_type"] != "3D_BAG"]
    assert res2["report"]["comparisons"] == []


def test_no_links_no_evidence(snapshot):
    res = bqe.build(links_store=bl.new_store(), snapshots=[snapshot], quantity_observations=[], crosswalk_effective={})
    assert res["evidence_store"]["evidence"] == []           # een snapshot alleen is geen link


def test_comparison_differences_no_averaging(chain):
    res, _ = chain
    comps = res["report"]["comparisons"]
    assert len(comps) == 1
    c = comps[0]
    assert c["historical_value"] == "308.00" and c["bag3d_value"] == "312.64"
    assert Decimal(c["absolute_difference"]) == Decimal("-4.64")
    assert c["percentage_difference"] == str((Decimal("-4.64") / Decimal("312.64") * 100).quantize(Decimal("0.0001")))
    assert c["difference_band"] == "WITHIN_5_PCT" and c["dependency_note"]
    text = json.dumps(res).lower()
    for forbidden in ('"confidence"', '"score"', '"average"', '"mean"', "average_sources"):
        assert forbidden not in text
    assert res["report"]["summary"]["within_5_pct"] == 1


def test_multiple_rows_and_multi_pand_not_summed(snapshot, docs):
    store = bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                           reviewer_id="t", reason="t", reviewed_at=T, documents=docs)
    qos = [_qo("DOC-005", "EL-001", "4711", "200.00", "m2", "SC"), _qo("DOC-005", "EL-002", "4711", "108.00", "m2", "SC")]
    props = xw.load_proposals()
    eff = xw.effective(props, xw.record_decision(xw.new_store(), mapping_id="HSM-ROOF_FLAT_AREA-4711-m2", decision="VERIFY",
                                                 reviewer_id="t", reason="t", reviewed_at=T, proposals=props))
    res = bqe.build(links_store=store, snapshots=[snapshot], quantity_observations=qos, crosswalk_effective=eff)
    assert all("MULTIPLE_HISTORICAL_ROWS_NOT_SUMMED" in c["mismatch_reasons"] for c in res["report"]["comparisons"])
    assert {c["historical_value"] for c in res["report"]["comparisons"]} == {"200.00", "108.00"}   # niet 308


def test_resolution_selects_explicit_evidence_only(chain):
    res, _ = chain
    idx = {e["evidence_id"]: e for e in res["evidence_store"]["evidence"]}
    bag = next(e for e in idx.values() if e["source_type"] == "3D_BAG" and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA")
    hist = next(e for e in idx.values() if e["source_type"] == "MJOP_ELEMENT_OVERVIEW")
    # historische evidence gebruikt het onderwerp van het gebouw (zelfde subject_id als 3D BAG bij één pand)
    assert hist["quantity_subject"]["subject_id"] == bag["quantity_subject"]["subject_id"]
    store = qe.record_resolution(qe.new_store(), building_id=bag["building_id"], subject_id=bag["quantity_subject"]["subject_id"],
                                 decision="ACCEPT_EVIDENCE", selected_evidence_id=hist["evidence_id"],
                                 considered_evidence_ids=[bag["evidence_id"], hist["evidence_id"]], decision_reason="MJOP recenter",
                                 reviewer_id="t", reviewed_at=T, evidence_index=idx)
    assert store["records"][0]["resolved_value"] == "308.00"
    avg = dict(store["records"][0], resolved_value="310.32")
    assert qe.validate_resolution(avg, idx)


def test_app_bundle_requires_verified_crosswalk(chain):
    res, eff = chain
    app = json.load(open(xw.APP_CROSSWALK))
    b = eab.build_bundle("BAG:0363100000000001", res["evidence_store"]["evidence"], app, eff)
    kinds = sorted(e["evidence"]["source_type"] for e in b["entries"])
    assert kinds == ["3D_BAG", "MJOP_ELEMENT_OVERVIEW"] and all(e["app_element_key"] == "dak-plat" for e in b["entries"])
    with pytest.raises(eab.BundleError):
        eab.build_bundle("BAG:0363100000000001", res["evidence_store"]["evidence"], app, xw.effective(store=xw.new_store()))


# --- gecommitte output + regressie ---------------------------------------------------------

def test_committed_reports_up_to_date():
    for script, args in (("building_links.py", ["candidates", "--check"]), ("build_building_quantity_evidence.py", ["--check"]),
                         ("build_quantity_observations.py", ["--check"]), ("build_kengetallen.py", ["--check"])):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script)] + args, cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, script + ": " + r.stdout + r.stderr


def test_kengetallen_and_observations_unchanged():
    k = {x["kengetal_id"]: x for x in json.load(open(os.path.join(ROOT, "data", "kengetallen", "kengetallen_batch1.json")))["kengetallen"]}
    assert k["KG-5211-replace-m1-pvc-5cb98033"]["value_display"] == "54.39"
    assert k["KG-4711-replace-m1-aluminium-d463b0a2"]["value_display"] == "37.47"
    qo = json.load(open(os.path.join(ROOT, "data", "quantity_observations", "quantity_observations_v1.json")))
    assert qo["summary"]["quantity_observations"] == 662 and qo["summary"]["review_required"] == 48


def test_stores_match_schemas(snapshot, docs):
    link_schema = json.load(open(os.path.join(ROOT, "schemas", "building_link_record.schema.json")))
    xw_schema = json.load(open(os.path.join(ROOT, "schemas", "crosswalk_decision_record.schema.json")))
    jsonschema.validate(json.load(open(bl.LINK_STORE)), link_schema)
    jsonschema.validate(json.load(open(xw.DECISIONS)), xw_schema)
    s = bl.record_link(bl.new_store(), document_id="DOC-005", bag_pand_id="0363100000000001", snapshot=snapshot,
                       reviewer_id="t", reason="t", reviewed_at=T, documents=docs)
    jsonschema.validate(s, link_schema)
    x = xw.record_decision(xw.new_store(), mapping_id="XW-dak-plat-4711-m2", decision="VERIFY", reviewer_id="t", reason="t", reviewed_at=T)
    jsonschema.validate(x, xw_schema)
