"""Tests voor Multi-pand Quantity Scope v1: gebouwscope met meerdere BAG-panden, per-pand-evidence, afgeleide
scope-som (GEOMETRY_DERIVED), range-opvraging zonder pariteit-aanname, app-bundel v2 en 'geen automatische besluiten'.

Alle PDOK/BAG/3D BAG-antwoorden hier zijn vaste, zelfgemaakte testantwoorden (fake_http) — geen echte gebouwdata,
nergens in data/ geschreven. De echte Maldenhof-snapshots worden alleen read-only gecontroleerd.
"""
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

import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import export_app_quantity_bundle as eab  # noqa: E402
import quantity_evidence as qe  # noqa: E402

T = "2026-10-05T10:00:00Z"
D = 0.0001
EVIDENCE_SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "quantity_evidence.schema.json")))
P1, P2, P3 = "0363100000000101", "0363100000000102", "0363100000000103"


def ring(lon, lat):
    return [[lon - D, lat - D], [lon + D, lat - D], [lon + D, lat + D], [lon - D, lat + D], [lon - D, lat - D]]


def fake_http(pand_specs, address_docs, rows_cap=None, fail_3dbag=()):
    calls = []

    def get(url):
        calls.append(url)
        if "locatieserver" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            start = int(q.get("start", ["0"])[0])
            rows = int(q.get("rows", ["10"])[0])
            if rows_cap:
                rows = min(rows, rows_cap)
            return 200, {"response": {"numFound": len(address_docs), "docs": address_docs[start:start + rows]}}
        if "bag/ogc" in url:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            x1, y1, x2, y2 = [float(v) for v in q["bbox"][0].split(",")]
            return 200, {"features": [{"geometry": {"type": "Polygon", "coordinates": [ring(lo, la)]},
                                       "properties": {"identificatie": pid, "bouwjaar": 1981, "status": "Pand in gebruik"}}
                                      for pid, (lo, la, _) in pand_specs.items() if x1 <= lo <= x2 and y1 <= la <= y2]}
        if "3dbag" in url:
            pid = url.rsplit(".", 1)[1]
            if pid in fail_3dbag:
                return 502, {"error": "bad gateway (test)"}
            return 200, {"metadata": {"version": "test"},
                         "feature": {"CityObjects": {"NL.IMBAG.Pand." + pid: {"attributes": pand_specs[pid][2]}}}}
        return 404, {}
    get.calls = calls
    return get


def adr(street, nr, postcode, lon, lat, city="Amsterdam", pid=None, letter=None):
    return {"id": pid or f"adr-{street}-{nr}-{city}", "weergavenaam": f"{street} {nr}, {postcode} {city}", "straatnaam": street,
            "huisnummer": nr, "huisletter": letter, "postcode": postcode.replace(" ", ""), "woonplaatsnaam": city,
            "centroide_ll": f"POINT({lon} {lat})"}


def attrs(flat):
    a = {"b3_opp_dak_schuin": 10, "b3_opp_buitenmuur": 100, "b3_h_dak_max": 10, "b3_h_maaiveld": 0}
    if flat is not None:
        a["b3_opp_dak_plat"] = flat
    return a


# pand 1 bevat 240 en 242 (twee adressen), pand 2 bevat 244, pand 3 bevat 243 (oneven zijde)
SPECS = {P1: (4.950, 52.300, attrs(0.1)), P2: (4.952, 52.300, attrs(0.2)), P3: (4.954, 52.300, attrs(7.61))}


def docs_in_range():
    return [adr("Teststraat", 240, "1106 EZ", 4.950, 52.300), adr("Teststraat", 242, "1106 EZ", 4.95002, 52.30002),
            adr("Teststraat", 243, "1106 EH", 4.954, 52.300), adr("Teststraat", 244, "1106 EZ", 4.952, 52.300),
            adr("Teststraat", 999, "1106 EZ", 4.960, 52.300),                         # buiten het bereik
            adr("Teststraat", 241, "1106 EZ", 4.956, 52.300, city="Diemen"),          # andere woonplaats
            adr("Teststraatje", 241, "1106 EZ", 4.958, 52.300)]                       # andere straat (geen fuzzy)


@pytest.fixture
def range_snap():
    http = fake_http(SPECS, docs_in_range(), rows_cap=3)
    snap = bs.fetch_range_snapshot("DOC-005", "Teststraat", 240, 248, "Amsterdam", "1106 EZ", http_get=http, fetched_at=T)
    snap["_calls"] = http.calls
    return snap


# --- gebouwscope-ID -----------------------------------------------------------------------------------

def test_building_id_stable_order_independent_and_deduplicated():
    a = bqe.building_id_for([P2, P1, P3])
    assert a == bqe.building_id_for([P3, P1, P2]) == bqe.building_id_for([P1, P2, P2, P3, P1])
    assert a == f"BAG:{P1}+{P2}+{P3}"
    assert bqe.building_id_for([P1]) == f"BAG:{P1}"                      # één pand: ongewijzigde conventie
    assert qe.make_building_subject_id(a, "ROOF_FLAT_AREA", "m2") == \
        qe.make_building_subject_id(bqe.building_id_for([P3, P2, P1]), "ROOF_FLAT_AREA", "m2")
    with pytest.raises(ValueError):
        bqe.building_id_for([])


# --- range-opvraging -------------------------------------------------------------------------------------

def test_range_discovery_all_actual_addresses_no_parity_no_fuzzy(range_snap):
    assert bs.snapshot_errors({k: v for k, v in range_snap.items() if k != "_calls"}) == []
    exact = [m for m in range_snap["address_matches"] if m["exact_match"]]
    assert sorted(m["huisnummer"] for m in exact) == [240, 242, 243, 244]     # even én oneven; 999/Diemen/Teststraatje niet
    assert {m["weergavenaam"].split(",")[0] for m in range_snap["address_matches"] if not m["exact_match"]} == \
        {"Teststraat 999", "Teststraat 241", "Teststraatje 241"}
    pdok_pages = [c for c in range_snap["_calls"] if "locatieserver" in c]
    assert len(pdok_pages) == 3                                                 # 7 docs, 3 per pagina -> paginering
    assert all("huisnummer%3A%5B240+TO+248%5D" in c for c in pdok_pages)
    pc = {m["huisnummer"]: m["postcode_matches_document"] for m in exact}
    assert pc == {240: True, 242: True, 243: False, 244: True}                 # vastgelegd, niet gefilterd


def test_range_dedupes_panden_and_fetches_3dbag_once(range_snap):
    panden = {p["bag_pand_id"]: p for p in range_snap["panden"]}
    assert sorted(panden) == [P1, P2, P3]
    assert len(panden[P1]["contains_address_point_of"]) == 2                   # 240 en 242 in hetzelfde pand
    assert sum(1 for c in range_snap["_calls"] if "3dbag" in c) == 3


def test_range_requires_city_and_valid_range():
    with pytest.raises(bs.SnapshotError):
        bs.fetch_range_snapshot("DOC-005", "Teststraat", 240, 248, None, http_get=fake_http(SPECS, []))
    with pytest.raises(bs.SnapshotError):
        bs.fetch_range_snapshot("DOC-005", "Teststraat", 248, 240, "Amsterdam", http_get=fake_http(SPECS, []))


def test_single_address_requires_city_when_given():
    d = [adr("Teststraat", 240, "1106 EZ", 4.950, 52.300, city="Diemen")]
    snap = bs.fetch_snapshot("DOC-005", "Teststraat", "240", None, "Amsterdam", http_get=fake_http(SPECS, d), fetched_at=T)
    assert snap["address_matches"][0]["exact_match"] is False and snap["panden"] == []


def test_3dbag_failure_is_recorded_not_zero():
    http = fake_http(SPECS, docs_in_range(), fail_3dbag={P2})
    snap = bs.fetch_range_snapshot("DOC-005", "Teststraat", 240, 248, "Amsterdam", http_get=http, fetched_at=T)
    p2 = next(p for p in snap["panden"] if p["bag_pand_id"] == P2)
    assert p2["threedbag"]["attributes"] is None and "502" in p2["threedbag"]["error"]
    assert bs.snapshot_errors(snap) == []


def test_lookup_plan_range_is_one_range_query():
    plan = bl.lookup_plan(bl.parse_address("Maldenhof 240 - 296"), "1106 EZ", "Amsterdam")
    assert plan == [{"street": "Maldenhof", "kind": "range", "number_from": "240", "number_to": "296",
                     "postcode": "1106 EZ", "city": "Amsterdam"}]
    # bestaand gedrag: enkel adres en lijst ongewijzigd
    assert bl.lookup_plan(bl.parse_address("Astraat 1"), "1000 AA", "X") == [
        {"street": "Astraat", "number": "1", "postcode": "1000 AA", "city": "X"}]
    assert [p["number"] for p in bl.lookup_plan(bl.parse_address("Vechtstraat 13-15-17-19"), None, "A")] == ["13", "15", "17", "19"]


# --- evidence: per pand + scope-aggregaat ---------------------------------------------------------------

DOCS = {d: {"address_as_stated": "Teststraat 240 - 248", "address_provenance": None, "postcode": "1106 EZ", "city": "Amsterdam",
            "object_name": None, "construction_year": None, "number_of_units": 3, "verified_sha256": "0" * 64}
        for d in ("DOC-005", "DOC-006")}


def linked(snap, pids, docs=("DOC-005",)):
    store = bl.new_store()
    for d in docs:
        s = dict(snap, document_id=d)
        body = {k: v for k, v in s.items() if k not in ("snapshot_id", "_calls")}
        s = dict(body, snapshot_id="BAGSNAP-" + bs.canonical_sha256(body)[:16])
        for p in pids:
            store = bl.record_link(store, document_id=d, bag_pand_id=p, snapshot=s, reviewer_id="test", reason="test",
                                   reviewed_at=T, documents=DOCS)
    return store


def qo(doc, value="425.80", same=("DOC-006",)):
    return {"quantity_observation_id": f"QO-{doc}-EL-025", "document_id": doc, "quantity_kind": "ELEMENT_QUANTITY",
            "source_file": {"relative_path": "x.pdf", "sha256": "0" * 64}, "source_cluster": "SC-DOC-005+DOC-006",
            "element": {"element_id": f"{doc}-EL-025", "element_code_original": "4711", "element_code_internal": "4711",
                        "element_description_original": "Dakbedekking APP", "location_original": "Platte dak",
                        "material_original": None, "material_normalized": None},
            "quantity_value": value, "unit_normalized": "m2", "measurable": True, "quantity_as_stated": value.replace(".", ","),
            "provenance": {"document_id": doc, "page": 7, "text_fragment": "4711 Dakbedekking APP Platte dak"},
            "extraction_method": "profile:test", "caveats": ["SAME_IN_RELATED_DOCUMENT"], "review_reasons": [],
            "requires_human_review": False,
            "dependency": {"same_object_document_ids": list(same), "identical_in_same_object_documents": [],
                           "differs_in_same_object_documents": []}}


def verified_eff():
    props = xw.load_proposals()
    xs = xw.record_decision(xw.new_store(), mapping_id="HSM-ROOF_FLAT_AREA-4711-m2", decision="VERIFY", reviewer_id="t",
                            reason="test", reviewed_at=T, proposals=props)
    xs = xw.record_decision(xs, mapping_id="XW-dak-plat-4711-m2", decision="VERIFY", reviewer_id="t", reason="test",
                            reviewed_at=T, proposals=props)
    return xw.effective(props, xs)


def run(snap, pids, docs=("DOC-005",), qos=None):
    store = linked(snap, pids, docs)
    snaps = [s for s in ({r["evidence"]["snapshot_id"]: None for r in store["records"]})]
    # bouw dezelfde snapshots opnieuw op (linked() herberekent de ID per document)
    built = []
    for d in docs:
        body = {k: v for k, v in dict(snap, document_id=d).items() if k not in ("snapshot_id", "_calls")}
        built.append(dict(body, snapshot_id="BAGSNAP-" + bs.canonical_sha256(body)[:16]))
    assert {s["snapshot_id"] for s in built} == set(snaps)
    return bqe.build(links_store=store, snapshots=built, quantity_observations=qos if qos is not None else [qo(d) for d in docs],
                     crosswalk_effective=verified_eff())


def test_per_pand_evidence_preserved_and_exact_decimal_aggregate(range_snap):
    res = run(range_snap, [P1, P2])
    ev = res["evidence_store"]["evidence"]
    per = [e for e in ev if e["source_type"] == "3D_BAG" and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"
           and not e["source_ref"].get("aggregation")]
    assert sorted((e["building_id"], e["value"]) for e in per) == [(f"BAG:{P1}", "0.1"), (f"BAG:{P2}", "0.2")]
    agg = [e for e in ev if e["source_ref"].get("aggregation") and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"]
    assert len(agg) == 1
    a = agg[0]
    assert a["value"] == "0.3"                                                   # exact, geen 0.30000000000000004
    assert a["method_class"] == "GEOMETRY_DERIVED" and a["quantity_subject"]["quantity_kind"] == "ELEMENT_QUANTITY"
    assert a["building_id"] == f"BAG:{P1}+{P2}"
    assert a["calculation"]["formula"] == "SUM(child_evidence.value)"
    assert a["calculation"]["rule_id"] == "scope.sum_over_confirmed_panden" and a["calculation"]["rule_version"] == "1.0.0"
    assert sorted(a["calculation"]["input_evidence_ids"]) == sorted(e["evidence_id"] for e in per)
    assert a["source_ref"]["bag_pand_ids"] == [P1, P2] and a["source_ref"]["missing_bag_pand_ids"] == []
    assert a["source_ref"]["snapshot_ids"] and a["source_ref"]["building_link_ids"]
    assert a["calculation"]["raw_inputs"] == {P1: "0.1", P2: "0.2"}
    for e in ev:
        jsonschema.validate(e, EVIDENCE_SCHEMA)
        assert qe.evidence_errors(e) == []
    # geen som voor gebouwhoogte
    assert not [e for e in ev if e["source_ref"].get("aggregation") and e["quantity_subject"]["subject_key"] == "BUILDING_HEIGHT"]


def test_missing_pand_value_is_not_zero_and_not_published():
    specs = dict(SPECS)
    specs[P2] = (4.952, 52.300, attrs(None))                                     # b3_opp_dak_plat ontbreekt
    snap = bs.fetch_range_snapshot("DOC-005", "Teststraat", 240, 248, "Amsterdam", http_get=fake_http(specs, docs_in_range()),
                                   fetched_at=T)
    res = run(snap, [P1, P2])
    ev = res["evidence_store"]["evidence"]
    assert not [e for e in ev if e["source_ref"].get("aggregation") and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"]
    np_ = [n for n in res["evidence_store"]["scope_aggregates_not_published"] if n["subject_key"] == "ROOF_FLAT_AREA"]
    assert np_ == [{"building_id": f"BAG:{P1}+{P2}", "subject_key": "ROOF_FLAT_AREA", "rule_id": "scope.sum_over_confirmed_panden",
                    "bag_pand_ids": [P1, P2], "missing_bag_pand_ids": [P2], "reason": "CHILD_EVIDENCE_MISSING_NOT_PUBLISHED"}]
    comp = [c for c in res["report"]["comparisons"] if c["subject_key"] == "ROOF_FLAT_AREA"]
    assert all("MULTI_PAND_AGGREGATE_NOT_PUBLISHED" in c["mismatch_reasons"] and c["bag3d_value"] is None for c in comp)
    # andere onderwerpen (alle panden hebben een waarde) worden wel opgeteld
    assert [e for e in ev if e["source_ref"].get("aggregation") and e["quantity_subject"]["subject_key"] == "ROOF_SLOPED_AREA"]


def test_historical_complex_quantity_unsplit_and_compared_to_aggregate(range_snap):
    res = run(range_snap, [P1, P2], docs=("DOC-005", "DOC-006"))
    ev = res["evidence_store"]["evidence"]
    hist = [e for e in ev if e["source_type"] == "MJOP_ELEMENT_OVERVIEW"]
    assert len(hist) == 2                                                       # één per document, niet per pand
    assert {e["building_id"] for e in hist} == {f"BAG:{P1}+{P2}"} and {e["value"] for e in hist} == {"425.80"}
    assert not [e for e in hist if e["building_id"] in (f"BAG:{P1}", f"BAG:{P2}")]
    agg = next(e for e in ev if e["source_ref"].get("aggregation") and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA")
    assert {e["quantity_subject"]["subject_id"] for e in hist} == {agg["quantity_subject"]["subject_id"]}
    assert [e for e in ev if e["source_ref"].get("aggregation")
            and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA"] == [agg]   # scope één keer, niet per document
    comps = [c for c in res["report"]["comparisons"] if c["subject_key"] == "ROOF_FLAT_AREA"]
    assert {(c["historical_value"], c["bag3d_value"], c["bag3d_method_class"]) for c in comps} == {("425.80", "0.3", "GEOMETRY_DERIVED")}
    assert all(c["dependency_note"] for c in comps)
    text = json.dumps(res).lower()
    for forbidden in ('"confidence"', '"score"', '"average"', '"mean"'):
        assert forbidden not in text


def test_resolution_can_select_but_never_average_multi_pand(range_snap):
    res = run(range_snap, [P1, P2])
    idx = {e["evidence_id"]: e for e in res["evidence_store"]["evidence"]}
    agg = next(e for e in idx.values() if e["source_ref"].get("aggregation") and e["quantity_subject"]["subject_key"] == "ROOF_FLAT_AREA")
    hist = next(e for e in idx.values() if e["source_type"] == "MJOP_ELEMENT_OVERVIEW")
    rec = {"resolution_id": "QRR-00001", "building_id": agg["building_id"], "subject_id": agg["quantity_subject"]["subject_id"],
           "decision": "ACCEPT_EVIDENCE", "selected_evidence_id": agg["evidence_id"], "manual_evidence_id": None,
           "resolved_value": "212.95", "resolved_unit": "m2", "considered_evidence_ids": [agg["evidence_id"], hist["evidence_id"]],
           "decision_reason": "t", "reviewer": {"reviewer_id": "t", "reviewer_type": "human"}}
    assert qe.validate_resolution(rec, idx)                                      # gemiddelde wordt geweigerd


# --- app-bundel -------------------------------------------------------------------------------------------

def test_bundle_v2_multi_pand_with_components_and_v1_single_unchanged(range_snap):
    app = json.load(open(xw.APP_CROSSWALK))
    eff = verified_eff()
    res = run(range_snap, [P1, P2], docs=("DOC-005", "DOC-006"))
    b = eab.build_bundle(f"BAG:{P1}+{P2}", res["evidence_store"]["evidence"], app, eff)
    assert b["bundle_version"] == "mjop_app_quantity_bundle_v2"
    assert b["building_scope"] == {"building_id": f"BAG:{P1}+{P2}", "kind": "MULTI_PAND_SCOPE", "bag_pand_ids": [P1, P2], "pand_count": 2}
    kinds = sorted((e["evidence"]["source_type"], e["evidence"]["method_class"]) for e in b["entries"])
    assert kinds == [("3D_BAG", "GEOMETRY_DERIVED"), ("MJOP_ELEMENT_OVERVIEW", "SOURCE_REPORTED"), ("MJOP_ELEMENT_OVERVIEW", "SOURCE_REPORTED")]
    agg = next(e for e in b["entries"] if e["evidence"]["source_type"] == "3D_BAG")["evidence"]
    assert agg["value"] == "0.3" and agg["formula"] == "SUM(child_evidence.value)"
    assert [(c["bag_pand_id"], c["value"]) for c in agg["components"]] == [(P1, "0.1"), (P2, "0.2")]
    assert all(e["evidence"]["scope_level"] == "COMPLEX" for e in b["entries"])
    # single-pand: exact het v1-formaat, zonder v2-velden
    res1 = run(range_snap, [P1])
    b1 = eab.build_bundle(f"BAG:{P1}", res1["evidence_store"]["evidence"], app, eff)
    assert b1["bundle_version"] == "mjop_app_quantity_bundle_v1" and "building_scope" not in b1
    assert all(set(e["evidence"]) == {"evidence_id", "source_type", "method_class", "value", "unit", "status", "review_reasons",
                                      "scope_caveats", "source_cluster", "same_object_document_ids", "source_ref"}
               for e in b1["entries"])


# --- echte Maldenhof-snapshots (read-only) + geen automatische besluiten ---------------------------------

def test_committed_maldenhof_snapshots_are_canonical_and_complete():
    snaps = [s for s in bs.load_snapshots() if s["document_id"] in ("DOC-005", "DOC-006")]
    assert sorted(s["document_id"] for s in snaps) == ["DOC-005", "DOC-006"]
    for s in snaps:
        assert bs.snapshot_errors(s) == [] and s["snapshot_version"] == "bag_snapshot_v1"
        assert s["query"]["kind"] == "range" and (s["query"]["number_from"], s["query"]["number_to"]) == (240, 296)
        exact = [m for m in s["address_matches"] if m["exact_match"]]
        assert len(exact) == 56 and 267 not in {m["huisnummer"] for m in exact}
        assert sum(1 for m in exact if m["postcode_matches_document"]) == 29
        assert len(s["panden"]) == 40 and all((p["threedbag"] or {}).get("attributes") for p in s["panden"])


def test_no_canonical_approvals_created_and_demo_writes_no_data():
    stores = [bl.LINK_STORE, xw.DECISIONS, os.path.join(ROOT, "data", "quantity_resolutions", "quantity_resolution_records.json")]
    before = [open(p, "rb").read() for p in stores]
    for script, args in (("multi_pand_scope_demo.py", ["--check"]), ("building_links.py", ["candidates", "--check"]),
                         ("build_building_quantity_evidence.py", ["--check"]), ("quantity_engine_activation_review.py", ["--check"])):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script)] + args, cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, script + ": " + r.stdout + r.stderr
    assert [open(p, "rb").read() for p in stores] == before
    assert json.load(open(bl.LINK_STORE))["records"] == [] and json.load(open(xw.DECISIONS))["records"] == []
    ev = json.load(open(bqe.OUT_EVIDENCE))
    assert ev["evidence"] == [] and ev["scope_aggregates_not_published"] == []


def test_maldenhof_demo_values():
    r = json.load(open(os.path.join(ROOT, "reports", "quantity", "maldenhof_multi_pand_scope_demo_v1.json")))
    assert r["preview_scope"]["status"] == "PREVIEW_NOT_HUMAN_CONFIRMED"
    assert (r["preview_scope"]["pand_count"], r["preview_scope"]["address_count"]) == (15, 29)
    assert sum(Decimal(p["b3_opp_dak_plat"]) for p in r["bag3d_per_pand"]) == Decimal(r["derived_complex_total"]["value"]) == Decimal("190.65")
    assert len(r["derived_complex_total"]["child_evidence_ids"]) == 15
    assert r["historical"]["values"] == ["425.80"]
    assert r["difference"]["historical_minus_3dbag_m2"] == "235.15"
    assert all(v != "VERIFIED" for v in r["mapping_status"].values())
