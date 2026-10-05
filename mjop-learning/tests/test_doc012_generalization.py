"""Tests voor Quantity Engine Generalization v1 — DOC-012 (read-only discovery + review).

Geen netwerk: de canonieke H1-snapshot en de H2-hypothese-opname zijn al vastgelegd; synthetische gevallen gebruiken
vaste testantwoorden. Er wordt niets in data/ geschreven.
"""
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import bag3d_quantity_rules as rules_mod  # noqa: E402
import bag_snapshots as bs  # noqa: E402
import build_building_quantity_evidence as bqe  # noqa: E402
import building_links as bl  # noqa: E402
import crosswalk as xw  # noqa: E402
import doc012_generalization_review as rev  # noqa: E402
import test_multi_pand_quantity_scope as t  # noqa: E402

H1_SNAP = "BAGSNAP-599d2f2004100011"
H1_PAND = "0518100000354752"
NEW_MAP = "HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012"
STORES = [bl.LINK_STORE, xw.DECISIONS, rev.RESOLUTIONS, bqe.OUT_EVIDENCE]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture(scope="module")
def report():
    before = [sha(p) for p in STORES]
    r = rev.build()
    assert [sha(p) for p in STORES] == before, "de review mag geen store wijzigen"
    return r


def test_committed_report_is_up_to_date(report):
    assert open(rev.OUT_JSON, encoding="utf-8").read() == json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    assert open(rev.OUT_MD, encoding="utf-8").read() == rev.render(report)


# --- H1 / H2 provenance --------------------------------------------------------------------

def test_h1_and_h2_provenance_stay_separate(report):
    h1, h2 = report["hypotheses"]["H1"], report["hypotheses"]["H2"]
    assert (h1["query_source"], h1["canonical"], h1["snapshot_id"]) == ("building.address", True, H1_SNAP)
    assert h1["query_provenance"]["text_fragment"] == "Adres Meppelweg 819" and h1["query_provenance"]["page"] == 2
    assert (h2["query_source"], h2["canonical"]) == ("document_level_values.object_name", False)
    assert h2["object_name"] == "VvE Meppelweg 801-883"
    assert h2["capture_path"].startswith("reports/quantity/doc012_scope_hypotheses/")


def test_object_name_range_is_not_treated_as_stated_address(report):
    # canonieke snapshots voor DOC-012: alleen H1; de H2-opname staat buiten data/bag_snapshots
    doc_snaps = [s for s in bs.load_snapshots() if s["document_id"] == "DOC-012"]
    assert [s["snapshot_id"] for s in doc_snaps] == [H1_SNAP]
    assert doc_snaps[0]["query"]["number"] == "819" and doc_snaps[0]["query"].get("kind") != "range"
    cand = next(o for o in bl.build_candidates()["documents"] if o["document_id"] == "DOC-012")
    assert cand["lookup_plan"] == [{"street": "Meppelweg", "number": "819", "postcode": "2544 AW", "city": "Den Haag"}]
    assert [c["bag_pand_id"] for c in cand["candidate_bag_panden"]] == [H1_PAND]
    assert "OBJECT_NAME_ADDRESS_DIFFERS" in cand["review_reasons"]
    # 'record' kan geen H2-pand vastleggen voor DOC-012: dat pand staat niet in de canonieke snapshot
    _, h2 = rev.load_h2_capture()
    with pytest.raises(bl.LinkError):
        bl.record_link(bl.new_store(), document_id="DOC-012", bag_pand_id="0518100001631386", snapshot=doc_snaps[0],
                       reviewer_id="t", reason="test", reviewed_at=t.T)


def test_h2_capture_is_integrity_checked_and_only_real_addresses(report):
    _, h2 = rev.load_h2_capture()
    assert bs.snapshot_errors(h2) == []
    assert h2["query"]["fq"][1] == "woonplaatsnaam:\"'s-Gravenhage\"" and h2["query"]["city"] == "Den Haag"
    h = report["hypotheses"]["H2"]
    assert h["addresses_found"] == 82 and h["addresses_by_parity"] == {"even": 41, "oneven": 41}
    assert 801 in h["numbers_in_range_without_address"]  # bestaat niet in BAG: niet verzonnen
    rel = report["hypothesis_relation"]
    assert rel["h1_subset_of_h2"] and rel["h2_odd_addresses_all_in_h1_pand"] and rel["h1_panden"] == [H1_PAND]
    assert len(report["hypotheses"]["H2"]["panden"]) == 6


def test_parse_object_name_range_is_exact():
    assert rev.parse_object_name_range("VvE Meppelweg 801-883") == ("Meppelweg", 801, 883)
    assert rev.parse_object_name_range("Meppelweg 801 t/m 883") is None
    assert rev.parse_object_name_range("VvE Meppelweg 819") is None
    assert rev.parse_object_name_range("VvE Meppelweg 801-883 en Beukstraat 1-9") is None


# --- geen fuzzy matching; woonplaats-alias exact -------------------------------------------

def test_city_alias_is_exact_not_fuzzy():
    assert bs.official_city("Den Haag") == ("'s-Gravenhage", "WPA-den-haag")
    assert bs.official_city("  den   haag ") == ("'s-Gravenhage", "WPA-den-haag")  # alleen hoofdletters/witruimte
    assert bs.official_city("Den Haag Centrum") == ("Den Haag Centrum", None)
    assert bs.official_city("Denhaag") == ("Denhaag", None)
    assert bs.official_city("Amsterdam") == ("Amsterdam", None)
    doc = {"straatnaam": "Meppelweg", "huisnummer": 819, "postcode": "2544AW", "woonplaatsnaam": "'s-Gravenhage"}
    assert bs.exact_address_match(doc, "Meppelweg", "819", "2544 AW", "Den Haag")
    assert not bs.exact_address_match(doc, "Meppelweg", "819", "2544 AW", "Den Haag Centrum")
    assert not bs.exact_address_match(doc, "Meppelweg", "817", "2544 AW", "Den Haag")
    assert not bs.exact_address_match(doc, "Meppelweg", "819", "2544 AX", "Den Haag")


def test_alias_only_added_to_query_when_used():
    specs = {t.P1: (4.95, 52.3, t.attrs(10))}
    snap = bs.fetch_snapshot("DOC-T", "Teststraat", 1, "1000 AA", "Amsterdam",
                             http_get=t.fake_http(specs, [t.adr("Teststraat", 1, "1000 AA", 4.95, 52.3)]), fetched_at=t.T)
    assert "city_alias_ref" not in snap["query"] and "city_bag_woonplaatsnaam" not in snap["query"]
    for s in bs.load_snapshots():
        if s["document_id"] in ("DOC-005", "DOC-006"):
            assert "city_alias_ref" not in s["query"]


def test_document_specific_mapping_exact_and_not_verified(report):
    eff = xw.effective()
    assert eff[NEW_MAP]["status"] == "PROPOSED" and not eff[NEW_MAP]["human_verified"]
    vocab = json.load(open(xw.SUBJECTS, encoding="utf-8"))
    m = next(x for x in vocab["historical_subject_mappings"] if x["mapping_id"] == NEW_MAP)
    qos = json.load(open(bqe.QO_PATH, encoding="utf-8"))["observations"]
    assert [o["quantity_observation_id"] for o in qos if bqe.mapping_matches(m, o)] == ["QO-DOC-012-EL-024"]
    o = json.loads(json.dumps(next(x for x in qos if x["quantity_observation_id"] == "QO-DOC-012-EL-024")))
    o["element"]["element_description_original"] = "Dakbedekking APP"  # andere schrijfwijze: geen match
    assert not bqe.mapping_matches(m, o)
    assert [p["matches"] for p in report["proposed_mappings"]] == [["QO-DOC-012-EL-024"]]


# --- 4711 m2 vs m1 ------------------------------------------------------------------------

def test_roof_covering_m2_distinguished_from_4711_m1_edges(report):
    roof = report["roof_4711"]["m2_cover"]
    assert (roof["quantity_observation_id"], roof["quantity"], roof["unit"]) == ("QO-DOC-012-EL-024", "801.04", "m2")
    assert roof["classification"] == "RELATED_NOT_EQUIVALENT" and roof["possible_subject"] == "ROOF_COVERING_REPORTED_AREA"
    assert roof["subject_relation"]["related_subject"] == "ROOF_FLAT_AREA"
    m1 = report["roof_4711"]["m1_rows"]
    assert sorted((r["description"], r["quantity"], r["unit"]) for r in m1) == [
        ("Dakrandafwerking aluminium trim", "152.54", "m1"), ("Randstrook APP", "152.54", "m1")]
    assert all(r["possible_subject"] is None and r["classification"] == "NO_3DBAG_COUNTERPART" for r in m1)
    assert all(r["quantity"] == "801.04" for r in [roof])  # niets opgeteld


def test_classification_counts_and_facade(report):
    hq = report["historical_quantities"]
    assert hq["count"] == 51 and sum(hq["by_classification"].values()) == 51
    assert hq["by_classification"]["DIRECTLY_COMPARABLE"] == 0
    wall = next(o for o in hq["observations"] if o["quantity_observation_id"] == "QO-DOC-012-EL-001")
    assert wall["classification"] == "NEEDS_SEMANTIC_REVIEW" and wall["possible_subject"] == "OUTER_WALL_GROSS_AREA"
    assert all(o["classification"] == "NOT_MEASURED_QUANTITY" for o in hq["observations"] if o["unit"] in ("lump_sum", None))


# --- 3D BAG-preview ------------------------------------------------------------------------

def test_missing_3dbag_is_never_zero(report):
    h2 = report["bag3d_preview"]["H2"]
    gesloopt = [p for p in report["hypotheses"]["H2"]["panden"] if p["status"] == "Pand gesloopt"]
    assert len(gesloopt) == 2 and not any(p["threedbag_available"] for p in gesloopt)
    for row in h2["per_pand"]:
        if row["bag_pand_id"] in {p["bag_pand_id"] for p in gesloopt}:
            assert all(v is None for v in row["values"].values())
    for k in ("ROOF_FLAT_AREA", "ROOF_SLOPED_AREA", "ROOF_TOTAL_AREA", "OUTER_WALL_GROSS_AREA"):
        a = h2["scope_aggregate"][k]
        assert a["status"] == "NOT_PUBLISHED" and sorted(a["missing_bag_pand_ids"]) == sorted(p["bag_pand_id"] for p in gesloopt)
    assert h2["scope_aggregate"]["BUILDING_HEIGHT"]["status"] == "NOT_AGGREGATED"
    assert next(r for r in report["roof_comparison"]["rows"] if r["hypothesis"] == "H2")["bag3d_value"] is None


def test_h1_preview_values_and_roof_comparison(report):
    h1 = report["bag3d_preview"]["H1"]
    assert h1["pand_count"] == 1 and h1["scope_aggregate"] is None
    v = h1["per_pand"][0]["values"]
    assert (v["ROOF_FLAT_AREA"]["value"], v["ROOF_FLAT_AREA"]["method_class"]) == ("875.63", "DIRECT_MEASURED")
    c = next(r for r in report["roof_comparison"]["rows"] if r["hypothesis"] == "H1")
    assert c["kind"] == "RELATED_SUBJECT_NOT_EQUIVALENT" and c["difference_historical_minus_3dbag"] == "-74.59"


def test_multi_pand_aggregation_stays_generic(report):
    agg = report["bag3d_preview"]["H2_IN_USE_ONLY_INFORMATIVE"]
    vals = [r["values"]["ROOF_FLAT_AREA"]["value"] for r in agg["per_pand"]]
    assert agg["pand_count"] == 4 and Decimal(agg["scope_aggregate"]["ROOF_FLAT_AREA"]["value"]) == sum(Decimal(x) for x in vals)
    assert agg["scope_aggregate"]["ROOF_FLAT_AREA"]["method_class"] == "GEOMETRY_DERIVED"
    # dezelfde functies op synthetische data in een andere stad
    rules, vocab = rules_mod.load_rules()
    specs = {t.P1: (5.10, 52.09, t.attrs(1.5)), t.P2: (5.12, 52.09, t.attrs(2.25))}
    snap = bs.fetch_range_snapshot("DOC-T", "Teststraat", 1, 3, "Utrecht", http_get=t.fake_http(
        specs, [t.adr("Teststraat", 1, "3500 AA", 5.10, 52.09, city="Utrecht"), t.adr("Teststraat", 3, "3500 AA", 5.12, 52.09, city="Utrecht")]),
        fetched_at=t.T)
    p = rev.preview(snap, [t.P1, t.P2], rules, vocab)
    assert p["scope_aggregate"]["ROOF_FLAT_AREA"]["value"] == "3.75"


# --- geen besluiten; Maldenhof-regressie ----------------------------------------------------

def test_no_decisions_written(report):
    st = report["state"]
    assert st["building_link_records_for_doc"] == 0 and st["building_link_records_total"] == 80
    assert st["crosswalk_decisions"] == ["XWD-00001", "XWD-00002"]
    assert st["quantity_resolutions"] == 0
    assert report["app_readiness"]["bundle_generated"] is False
    assert not any(e["building_id"].startswith("BAG:0518") for e in json.load(open(bqe.OUT_EVIDENCE))["evidence"])


def test_maldenhof_bundle_sha256_unchanged(report):
    assert sha(rev.MALDENHOF_BUNDLE) == "b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933"
    assert report["state"]["maldenhof_bundle_unchanged"] is True


def test_generalization_audit_has_no_open_generic_problem(report):
    kinds = {h["classification"] for h in report["generalization_audit"]}
    assert "GENERIC_CODE_PROBLEM" not in kinds
    fixed = [h for h in report["generalization_audit"] if h["classification"] == "GENERIC_CODE_PROBLEM_FIXED"]
    assert [h["file"] for h in fixed] == ["scripts/bag_snapshots.py"]


def test_review_script_check_mode():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "doc012_generalization_review.py"), "--check"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
