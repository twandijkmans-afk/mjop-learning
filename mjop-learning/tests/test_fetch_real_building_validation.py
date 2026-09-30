"""Tests voor scripts/fetch_real_building_validation.py.

Alle PDOK/BAG/3D BAG-antwoorden hier zijn vaste, zelfgemaakte testantwoorden (fake http) — geen echte
gebouwgegevens; uitvoer gaat naar tmp_path, nooit naar data/."""
import json
import os
import re
import sys
from collections import Counter

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fetch_real_building_validation as frbv  # noqa: E402

NOW = lambda: "2026-10-01T10:00:00Z"  # noqa: E731
NOSLEEP = lambda s: None  # noqa: E731
D = 0.0001
GROUP = {"group_id": "T-1", "document_ids": ["DOC-T"], "label": "test", "street": "Teststraat",
         "numbers": ["1"], "postcode": "1000 AA", "city": "Testdam"}
BY_ID = {g["group_id"]: g for g in frbv.GROUPS}


def ring(lon, lat):
    return [[lon - D, lat - D], [lon + D, lat - D], [lon + D, lat + D], [lon - D, lat + D], [lon - D, lat - D]]


def jb(obj):
    return json.dumps(obj).encode()


def ok(body):
    return {"status": 200, "body": body, "content_type": "application/json", "error": None}


class World:
    """addresses: {nummer: pand_id}; panden: {pand_id: (vbo_count, bouwjaar)}. Panden liggen ver uit elkaar."""

    def __init__(self, street, addresses, panden, place="Testdam", postcode="1000AA", threed_status=200,
                 pdok_raw=None, threed_raw=None, extra_docs=None):
        self.street, self.addresses, self.panden, self.place, self.postcode = street, addresses, panden, place, postcode
        self.pos = {pid: (4.0 + i * 0.01, 52.0 + i * 0.01) for i, pid in enumerate(sorted(panden))}
        self.threed_status, self.pdok_raw, self.threed_raw, self.extra_docs = threed_status, pdok_raw, threed_raw, extra_docs or {}
        self.calls = []

    def doc(self, number):
        lon, lat = self.pos[self.addresses[number]]
        return {"id": "adr-" + number, "weergavenaam": f"{self.street} {number}, {self.postcode} {self.place}",
                "straatnaam": self.street, "huisnummer": int(number), "postcode": self.postcode,
                "woonplaatsnaam": self.place, "woonplaatscode": "9999", "centroide_ll": f"POINT({lon} {lat})",
                "adresseerbaarobject_id": "0100" + number.zfill(10), "nummeraanduiding_id": "0200" + number.zfill(10)}

    VBO_BASE = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items/"

    def vbo_ids(self, pid):
        ids = sorted({self.doc(n)["adresseerbaarobject_id"] for n, p in self.addresses.items() if p == pid})
        return ids + [f"UNMATCHED{pid}{k}" for k in range(self.panden[pid][0] - len(ids))]

    def vbo_hrefs(self, pid):
        return [self.VBO_BASE + f"{pid}~{v}" for v in self.vbo_ids(pid)]

    def __call__(self, url):
        self.calls.append(url)
        if "/verblijfsobject/items/" in url:
            vid = url.rsplit("~", 1)[1]
            return ok(jb({"type": "Feature", "properties": {"identificatie": vid, "status": "Verblijfsobject in gebruik",
                                                            "gebruiksdoel": "woonfunctie", "oppervlakte": 50}}))
        if "locatieserver" in url:
            if self.pdok_raw is not None:
                return ok(self.pdok_raw)
            q = re.search(r"[?&]q=([^&]*)", url).group(1).replace("+", " ").split()
            number = q[1]
            docs = [self.doc(number)] if number in self.addresses else []
            docs += self.extra_docs.get(number, [])
            return ok(jb({"response": {"docs": docs}}))
        if "bag/ogc" in url:
            bbox = re.search(r"bbox=([^&]*)", url).group(1).replace("%2C", ",")
            x1, y1, x2, y2 = [float(v) for v in bbox.split(",")]
            feats = [{"geometry": {"type": "Polygon", "coordinates": [ring(lo, la)]},
                      "properties": {"identificatie": pid, "bouwjaar": self.panden[pid][1], "status": "Pand in gebruik",
                                     "aantal_verblijfsobjecten": self.panden[pid][0],
                                     "verblijfsobject.href": self.vbo_hrefs(pid)}}
                     for pid, (lo, la) in self.pos.items() if x1 <= lo <= x2 and y1 <= la <= y2]
            return ok(jb({"features": feats}))
        if "3dbag" in url:
            pid = url.rsplit(".", 1)[1]
            if self.threed_status != 200:
                return {"status": self.threed_status, "body": jb({"detail": "nope"}), "content_type": "application/json",
                        "error": f"HTTP {self.threed_status}"}
            body = self.threed_raw if self.threed_raw is not None else jb({
                "id": "NL.IMBAG.Pand." + pid, "metadata": {"version": "vTEST"},
                "feature": {"id": "NL.IMBAG.Pand." + pid, "type": "CityJSONFeature", "CityObjects": {
                    "NL.IMBAG.Pand." + pid: {"type": "Building", "children": ["NL.IMBAG.Pand." + pid + "-0"],
                                             "geometry": [{"type": "MultiSurface", "lod": "0"}],
                                             "attributes": {"b3_opp_grond": 70.5, "b3_h_dak_50p": 6.5, "b3_dak_type": "slanted",
                                                            "b3_volume_lod22": 500.0, "identificatie": "NL.IMBAG.Pand." + pid,
                                                            "oorspronkelijkbouwjaar": self.panden[pid][1]}},
                    "NL.IMBAG.Pand." + pid + "-0": {"type": "BuildingPart", "parents": ["NL.IMBAG.Pand." + pid],
                                                    "geometry": [{"type": "Solid", "lod": "2.2"}]}}}})
            return ok(body)
        return {"status": 404, "body": b"{}", "content_type": None, "error": "HTTP 404"}


def simple_world(**kw):
    return World("Teststraat", {"1": "P1"}, {"P1": (1, 1981)}, **kw)


def mjop_fake(units=None, year=None, postcode=None, city=None):
    def load(ids):
        return [{"document_id": i, "number_of_units": units, "construction_year": year, "postcode": postcode, "city": city,
                 "address": None, "object_name": None} for i in ids]
    return load


def run_group(tmp_path, world, group=GROUP, loader=None):
    return frbv.run([group], tmp_path, http_get=world, now=NOW, mjop_loader=loader or mjop_fake(), sleep=NOSLEEP)


def pkg(tmp_path, gid="T-1"):
    return json.loads((tmp_path / "candidates" / f"{gid}.json").read_text())


def maldenhof_world(with_odd=False):
    nums = [str(n) for n in range(240, 297, 2)]
    addr, panden = {nums[0]: "P00"}, {"P00": (1, 1981)}
    for i, (a, b) in enumerate(zip(nums[1::2], nums[2::2]), start=1):
        addr[a] = addr[b] = f"P{i:02d}"
        panden[f"P{i:02d}"] = (2, 1981)
    if with_odd:
        for n in range(241, 297, 2):
            addr[str(n)] = "PODD"
        panden["PODD"] = (28, 1981)
    return World("Maldenhof", addr, panden, place="Amsterdam", postcode="1106EZ")


MALDENHOF_MJOP = dict(units=29, year=1981, postcode="1106 EZ", city="Amsterdam")


def meppelweg_world(with_even=False, **kw):
    addr = {str(n): "PM" for n in range(801, 884, 2)}
    panden = {"PM": (42, 1957)}
    if with_even:
        for n in range(802, 884, 2):
            addr[str(n)] = "PE"
        panden["PE"] = (41, 1957)
    return World("Meppelweg", addr, panden, place="'s-Gravenhage", postcode="2544AW", **kw)


MEPPELWEG_MJOP = dict(units=None, year=1956, postcode="2544 AW", city="Den Haag")


# --- basis: parsing, ontbrekende resultaten, kwaadaardige/kapotte antwoorden --------------------------------

def test_response_parsing_single_candidate(tmp_path):
    m = run_group(tmp_path, simple_world())
    p = pkg(tmp_path)
    assert [x["bag_pand_id"] for x in p["candidate_panden"]] == ["P1"]
    tb = p["candidate_panden"][0]["threedbag"]
    assert tb["attributes"]["b3_opp_grond"] == 70.5 and tb["api_version"] == "vTEST"
    assert p["address_results"][0]["address_matches"][0]["exact_match"] is True
    assert m["network_ok"] is True
    pd = [r for r in m["requests"] if r["purpose"] == "locatieserver"][0]
    assert pd["retrieved_identifiers"]["adresseerbaarobject_ids"] == ["01000000000001"]
    assert pd["retrieved_identifiers"]["nummeraanduiding_ids"] == ["02000000000001"]
    assert pd["retrieved_identifiers"]["woonplaatscodes"] == ["9999"]


def test_missing_results(tmp_path):
    m = run_group(tmp_path, World("Teststraat", {}, {"P1": (1, 1981)}))
    p = pkg(tmp_path)
    assert p["candidate_panden"] == []
    assert "NO_EXACT_ADDRESS_MATCH" in p["address_results"][0]["flags"]
    assert "GROUP: NO_CANDIDATE_PAND" in p["review_flags"]
    assert p["building_project_candidate"]["strength"] == "NO_BUILDING_PROJECT_CANDIDATE"
    assert len(m["requests"]) == 1  # geen BAG/3D BAG-calls zonder exact adres


def test_non_exact_address_is_not_used(tmp_path):
    w = World("Teststraat", {}, {"P1": (1, 1981)}, extra_docs={"1": [dict(simple_world().doc("1"), huisnummer=2)]})
    run_group(tmp_path, w)
    assert pkg(tmp_path)["candidate_panden"] == []


def test_housenumber_variant_is_context_not_match(tmp_path):
    w = simple_world(extra_docs={"1": [dict(simple_world().doc("1"), id="adr-1A", huisletter="A", weergavenaam="Teststraat 1A")]})
    run_group(tmp_path, w)
    ar = pkg(tmp_path)["address_results"][0]
    assert "HOUSENUMBER_VARIANTS_PRESENT" in ar["flags"] and ar["housenumber_variants"] == ["Teststraat 1A"]
    assert sum(1 for m in ar["address_matches"] if m["exact_match"]) == 1


def test_multiple_exact_address_matches_flagged(tmp_path):
    w = simple_world(extra_docs={"1": [dict(simple_world().doc("1"), id="adr-x", woonplaatsnaam="Elders")]})
    run_group(tmp_path, w)
    flags = pkg(tmp_path)["address_results"][0]["flags"]
    assert "MULTIPLE_EXACT_ADDRESS_MATCHES" in flags and "EXACT_MATCH_IN_OTHER_CITY" in flags


def test_malformed_pdok_response(tmp_path):
    m = run_group(tmp_path, simple_world(pdok_raw=b"<html>not json"))
    r = m["requests"][0]
    assert r["parse_status"] == "MALFORMED_RESPONSE" and "MALFORMED_RESPONSE" in r["flags"]
    assert (tmp_path / r["raw_response_path"]).read_bytes() == b"<html>not json"  # ruwe bytes bewaard
    assert "ADDRESS_LOOKUP_FAILED" in pkg(tmp_path)["address_results"][0]["flags"]


def test_unexpected_shape_and_malformed_3dbag(tmp_path):
    m = run_group(tmp_path, simple_world(threed_raw=jb({"feature": {"CityObjects": {}}})))
    tb = [r for r in m["requests"] if r["purpose"] == "3dbag-pand"][0]
    assert "UNEXPECTED_SHAPE" in tb["flags"]
    assert any("THREEDBAG_ATTRIBUTES_MISSING" in f for f in pkg(tmp_path)["review_flags"])
    assert pkg(tmp_path)["candidate_panden"][0]["quantity_evidence"] is None
    m2 = run_group(tmp_path / "b", simple_world(threed_raw=b"{oops"))
    assert "MALFORMED_RESPONSE" in [r for r in m2["requests"] if r["purpose"] == "3dbag-pand"][0]["flags"]


def test_threedbag_404(tmp_path):
    m = run_group(tmp_path, simple_world(threed_status=404))
    tb = [r for r in m["requests"] if r["purpose"] == "3dbag-pand"][0]
    assert tb["http_status"] == 404 and "THREEDBAG_NOT_FOUND" in tb["flags"]


def test_network_error_recorded_and_not_ok(tmp_path):
    def down(url):
        return {"status": None, "body": b"", "content_type": None, "error": "URLError: 403 CONNECT"}
    m = frbv.run([GROUP], tmp_path, http_get=down, now=NOW, mjop_loader=mjop_fake(), sleep=NOSLEEP)
    assert m["network_ok"] is False
    assert m["requests"][0]["parse_status"] == "NETWORK_ERROR" and m["requests"][0]["raw_response_path"] is None


# --- Maldenhof: exact 29 adressen, 15 panden, STRONG maar niet approved ----------------------------------

def test_maldenhof_config_is_exactly_29_even_numbers():
    g = BY_ID["DOC-005-006"]
    nums = frbv.group_numbers(g)
    assert nums[0] == "240" and nums[-1] == "296" and len(nums) == len(set(nums)) == 57
    even = frbv.hypothesis_numbers(g["scope_hypotheses"][0], nums)
    assert g["scope_hypotheses"][0]["hypothesis_id"] == "EVEN_ONLY"
    assert even == [str(n) for n in range(240, 297, 2)] and len(even) == 29


def test_maldenhof_29_addresses_15_panden_strong_candidate(tmp_path):
    run_group(tmp_path, maldenhof_world(), BY_ID["DOC-005-006"], mjop_fake(**MALDENHOF_MJOP))
    bpc = pkg(tmp_path, "DOC-005-006")["building_project_candidate"]
    even = next(h for h in bpc["scope_hypotheses"] if h["hypothesis_id"] == "EVEN_ONLY")
    c = even["counts"]
    assert (c["requested_addresses"], c["unique_requested_addresses"], c["exact_bag_matches"], c["unique_bag_addresses"]) == (29, 29, 29, 29)
    assert c["missing"] == 0 and c["unique_bag_panden"] == 15 and c["vbo_total_bag"] == 29
    assert c["addresses_per_pand_histogram"] == {"1": 1, "2": 14}
    assert even["duplicate_bag_addresses"] == [] and even["mjop_number_of_units"] == 29
    assert even["checks"]["units_equal_addresses_and_vbo"] is True and even["checks"]["vbo_fully_covered"] is True
    assert even["strength"] == "STRONG_BUILDING_PROJECT_CANDIDATE"
    assert bpc["strength"] == "STRONG_BUILDING_PROJECT_CANDIDATE" and bpc["best_supported_hypothesis_id"] == "EVEN_ONLY"
    all_h = next(h for h in bpc["scope_hypotheses"] if h["hypothesis_id"] == "ALL_NUMBERS")
    assert all_h["strength"] == "WEAK_BUILDING_PROJECT_CANDIDATE" and len(all_h["addresses_missing"]) == 28


def test_maldenhof_odd_neighbours_do_not_join_the_scope(tmp_path):
    run_group(tmp_path, maldenhof_world(with_odd=True), BY_ID["DOC-005-006"], mjop_fake(**MALDENHOF_MJOP))
    bpc = pkg(tmp_path, "DOC-005-006")["building_project_candidate"]
    even = next(h for h in bpc["scope_hypotheses"] if h["hypothesis_id"] == "EVEN_ONLY")
    assert even["counts"]["unique_bag_panden"] == 15 and "PODD" not in even["bag_pand_ids"]
    assert bpc["best_supported_hypothesis_id"] == "EVEN_ONLY"


def test_strong_is_not_approval_and_multi_pand_has_no_single_building(tmp_path):
    m = run_group(tmp_path, maldenhof_world(), BY_ID["DOC-005-006"], mjop_fake(**MALDENHOF_MJOP))
    p = pkg(tmp_path, "DOC-005-006")
    bpc = p["building_project_candidate"]
    assert p["status"] == "CANDIDATE_UNREVIEWED" and bpc["status"] == "CANDIDATE_UNREVIEWED"
    assert p["approval"] == {"building_link_approved": False, "approved_by": None, "approved_at": None}
    assert bpc["selected_scope"] is None and bpc["canonical_building_project_written"] is False
    assert bpc["kind"] == "LOGICAL_BUILDING_PROJECT_CANDIDATE" and len(bpc["scope_hypotheses"][0]["bag_pand_ids"]) == 15
    assert any("BUILDING_PROJECT_BESTAAT_UIT_15_BAG_PANDEN" in f for f in p["review_flags"])
    assert "building_pand_id" not in bpc and "pand_id" not in bpc
    assert set(p["not_done_in_this_step"].values()) == {False}
    assert m["approval_summary"]["any_building_link_approved"] is False
    assert frbv.manifest_errors(tmp_path) == []


def test_units_mismatch_prevents_strong(tmp_path):
    run_group(tmp_path, maldenhof_world(), BY_ID["DOC-005-006"], mjop_fake(units=30, year=1981, postcode="1106 EZ", city="Amsterdam"))
    assert pkg(tmp_path, "DOC-005-006")["building_project_candidate"]["strength"] == "WEAK_BUILDING_PROJECT_CANDIDATE"


def test_no_duplicate_address_requests(tmp_path):
    m = run_group(tmp_path, maldenhof_world(), BY_ID["DOC-005-006"], mjop_fake(**MALDENHOF_MJOP))
    endpoints = [r["endpoint"] for r in m["requests"]]
    assert len(endpoints) == len(set(endpoints))
    loc = [r["requested_address"] for r in m["requests"] if r["purpose"] == "locatieserver"]
    assert len(loc) == len(set(loc)) == 57
    threed = [r["endpoint"] for r in m["requests"] if r["purpose"] == "3dbag-pand"]
    assert len(threed) == len(set(threed)) == 15  # één 3D BAG-call per uniek pand, niet per adres


# --- Meppelweg: volledig bereik, geen gegokte pariteit -----------------------------------------------------

def test_meppelweg_full_range_retrieval(tmp_path):
    w = meppelweg_world()
    m = run_group(tmp_path, w, BY_ID["DOC-012"], mjop_fake(**MEPPELWEG_MJOP))
    loc = [r for r in m["requests"] if r["purpose"] == "locatieserver"]
    assert len(loc) == 83  # 801..883, alle nummers: pariteit staat niet in de bron
    assert len(frbv.group_numbers(BY_ID["DOC-012"])) == 83
    bpc = pkg(tmp_path, "DOC-012")["building_project_candidate"]
    odd = next(h for h in bpc["scope_hypotheses"] if h["hypothesis_id"] == "ODD_ONLY")
    assert odd["counts"]["exact_bag_matches"] == 42 and odd["counts"]["unique_bag_panden"] == 1
    assert odd["counts"]["vbo_total_bag"] == 42 and odd["addresses_missing"] == []
    assert odd["checks"]["units_known"] is False and odd["checks"]["units_equal_addresses_and_vbo"] is None
    assert odd["strength"] == "MODERATE_BUILDING_PROJECT_CANDIDATE"  # geen eenheden in bron => nooit STRONG
    assert any("CONSTRUCTION_YEAR_MISMATCH_MJOP_VS_BAG" in f for f in odd["flags"])
    alln = next(h for h in bpc["scope_hypotheses"] if h["hypothesis_id"] == "ALL_NUMBERS")
    assert len(alln["addresses_missing"]) == 41 and alln["strength"] == "WEAK_BUILDING_PROJECT_CANDIDATE"
    assert bpc["best_supported_hypothesis_id"] == "ODD_ONLY" and bpc["selected_scope"] is None
    p = pkg(tmp_path, "DOC-012")
    assert [o["field"] for o in p["mjop_context"]["source_observations"]] == ["object_code", "opdrachtgever_naam", "unit_count"]


def test_meppelweg_scope_ambiguous_when_both_parities_exist(tmp_path):
    run_group(tmp_path, meppelweg_world(with_even=True), BY_ID["DOC-012"], mjop_fake(**MEPPELWEG_MJOP))
    p = pkg(tmp_path, "DOC-012")
    bpc = p["building_project_candidate"]
    assert bpc["best_supported_hypothesis_id"] is None and bpc["selected_scope"] is None
    assert any(f.startswith("SCOPE_AMBIGUOUS") for f in p["review_flags"])


def test_source_observations_match_mjop_text_layer():
    fixture = os.path.join(ROOT, "tests", "fixtures", "xpdf_pages",
                           "86bf554e24b00f976b72465e2ceb3ce20db6083b7c487a77310a476054a7e716.json")
    if not os.path.exists(fixture):
        pytest.skip("xpdf-fixture niet aanwezig")
    text = re.sub(r"\s+", " ", " ".join(json.load(open(fixture))["pages"][:3]))
    for o in BY_ID["DOC-012"]["mjop_source_observations"]:
        if o["text_fragment"]:
            assert o["text_fragment"] in text


# --- Den Haag == 's-Gravenhage ------------------------------------------------------------------------------

def test_place_alias_helpers():
    assert frbv.place_equivalent("Den Haag", "'s-Gravenhage")
    assert frbv.place_equivalent("'s-Gravenhage", "Den Haag")
    assert frbv.place_equivalent("’s-Gravenhage", "s-gravenhage")
    assert frbv.place_equivalent("Amsterdam", " amsterdam ")
    assert not frbv.place_equivalent("Amsterdam", "Diemen")
    assert not frbv.place_equivalent("Den Haag", "Rijswijk")


@pytest.mark.parametrize("requested_city,postcode", [("Den Haag", None), ("Den Haag", "2544 AW"), ("'s-Gravenhage", "2544 AW")])
def test_den_haag_vs_sgravenhage_gives_no_other_city_warning(tmp_path, requested_city, postcode):
    g = dict(GROUP, street="Meppelweg", numbers=["819"], city=requested_city, postcode=postcode)
    w = World("Meppelweg", {"819": "PM"}, {"PM": (42, 1957)}, place="'s-Gravenhage", postcode="2544AW")
    run_group(tmp_path, w, g)
    ar = pkg(tmp_path)["address_results"][0]
    assert "EXACT_MATCH_IN_OTHER_CITY" not in ar["flags"] and ar["candidate_pand_ids"] == ["PM"]
    assert ar["address_matches"][0]["woonplaatscode"] == "9999"


def test_really_other_city_still_warns(tmp_path):
    g = dict(GROUP, street="Meppelweg", numbers=["819"], city="Den Haag", postcode=None)
    w = World("Meppelweg", {"819": "PM"}, {"PM": (42, 1957)}, place="Rijswijk", postcode="2544AW")
    run_group(tmp_path, w, g)
    assert "EXACT_MATCH_IN_OTHER_CITY" in pkg(tmp_path)["address_results"][0]["flags"]


# --- quantity evidence: alleen evidence -------------------------------------------------------------------------

def test_quantity_evidence_is_evidence_only_with_provenance(tmp_path):
    m = run_group(tmp_path, simple_world())
    ev = pkg(tmp_path)["candidate_panden"][0]["quantity_evidence"]
    assert ev["evidence_only"] is True and ev["translated_to_maintenance_quantities"] is False
    assert ev["ground_area_m2"] == 70.5 and ev["roof"]["b3_dak_type"] == "slanted" and ev["roof"]["b3_h_dak_50p"] == 6.5
    assert ev["volume_m3"]["b3_volume_lod22"] == 500.0
    g = ev["geometry_identifiers"]
    assert g["cityobject_id"] == "NL.IMBAG.Pand.P1" and g["building_parts"][0]["id"] == "NL.IMBAG.Pand.P1-0"
    assert g["building_parts"][0]["geometry"] == [{"type": "Solid", "lod": "2.2"}]
    raw = (tmp_path / ev["source"]["raw_response_path"]).read_bytes()
    assert ev["source"]["raw_response_sha256"] == frbv.sha256_bytes(raw)
    assert ev["source"]["request_id"] in {r["request_id"] for r in m["requests"]}
    text = json.dumps(pkg(tmp_path)).lower()
    assert "cost_per_m2" not in text and "element_quantity" not in text and "maintenance_quantity" not in text.replace(
        "translated_to_maintenance_quantities", "")


# --- manifest / provenance / hashes / geen approval -----------------------------------------------------------------

def test_manifest_hashes_and_tamper_detection(tmp_path):
    m = run_group(tmp_path, simple_world())
    assert frbv.manifest_errors(tmp_path) == []
    for r in m["requests"]:
        data = (tmp_path / r["raw_response_path"]).read_bytes()
        assert r["raw_response_sha256"] == frbv.sha256_bytes(data) and r["raw_response_bytes"] == len(data)
        assert r["endpoint"] and r["http_status"] == 200 and r["requested_address"] and r["retrieval_source"]
    assert (tmp_path / "raw" / "pdok").is_dir() and (tmp_path / "raw" / "3dbag").is_dir()
    victim = tmp_path / m["requests"][0]["raw_response_path"]
    victim.write_bytes(b"{}")
    assert any("sha256" in e for e in frbv.manifest_errors(tmp_path))


def test_manifest_reproducible(tmp_path):
    run_group(tmp_path / "a", simple_world())
    run_group(tmp_path / "b", simple_world())
    assert (tmp_path / "a" / "manifest.json").read_bytes() == (tmp_path / "b" / "manifest.json").read_bytes()


def test_no_automatic_building_approval(tmp_path):
    m = run_group(tmp_path, simple_world())
    p = pkg(tmp_path)
    assert p["status"] == "CANDIDATE_UNREVIEWED"
    assert p["approval"] == {"building_link_approved": False, "approved_by": None, "approved_at": None}
    assert p["human_confirmation_required"]
    assert set(p["not_done_in_this_step"].values()) == {False}
    assert m["approval_summary"]["any_building_link_approved"] is False
    path = tmp_path / "candidates" / "T-1.json"
    for mutate in (lambda d: d["approval"].__setitem__("building_link_approved", True),
                   lambda d: d["building_project_candidate"].__setitem__("canonical_building_project_written", True)):
        d = json.loads(path.read_text())
        mutate(d)
        path.write_text(json.dumps(d))
        assert frbv.manifest_errors(tmp_path)  # sha-mismatch én verboden status worden afgewezen
        path.write_text(json.dumps(p, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def test_only_candidates_written_no_canonical_paths(tmp_path):
    run_group(tmp_path, simple_world())
    assert {x.name for x in tmp_path.iterdir()} == {"raw", "candidates", "manifest.json"}


def test_mjop_loader_reads_extracted_read_only(tmp_path):
    d = tmp_path / "data" / "extracted"
    d.mkdir(parents=True)
    (d / "DOC-X.json").write_text(json.dumps({
        "building": {"address": {"value": "Straat 1"}, "number_of_units": {"value": 5, "provenance": {"page": 2, "text_fragment": "Aantal eenheden 5"}},
                     "construction_year": {"value": 1990}},
        "document_level_values": {"object_postcode": {"value": "1000 AA"}, "object_city": {"value": "Testdam"}},
        "extraction_metadata": {"source_sha256": "abc"}}))
    docs = frbv.load_mjop_context(["DOC-X", "DOC-Y"], root=tmp_path)
    assert docs[0]["number_of_units"] == 5 and docs[0]["provenance"]["number_of_units"]["page"] == 2
    assert docs[1]["error"] == "EXTRACTED_FILE_MISSING"
    combined, conflicts = frbv.combine_mjop([{"number_of_units": 29}, {"number_of_units": 30}])
    assert combined["number_of_units"] is None and conflicts == ["MJOP_DOCUMENTS_DISAGREE:number_of_units"]


def test_real_extracted_mjop_context_for_target_documents():
    docs = frbv.load_mjop_context(["DOC-005", "DOC-006", "DOC-012"])
    if any("error" in d for d in docs):
        pytest.skip("data/extracted niet beschikbaar")
    by = {d["document_id"]: d for d in docs}
    assert by["DOC-005"]["number_of_units"] == by["DOC-006"]["number_of_units"] == 29
    assert by["DOC-005"]["postcode"] == "1106 EZ" and by["DOC-012"]["postcode"] == "2544 AW"
    assert by["DOC-012"]["number_of_units"] is None
    assert Counter(d["construction_year"] for d in docs) == Counter({1981: 2, 1956: 1})


# --- robuustheid: retries, gestructureerde zoekopdracht, VBO-detail ---------------------------------------------------

def test_transient_errors_are_retried_and_last_outcome_recorded(tmp_path):
    w = simple_world()
    seen = {"n": 0}

    def flaky(url):
        if "3dbag" in url:
            seen["n"] += 1
            if seen["n"] < 3:
                return {"status": 502, "body": b"bad gateway", "content_type": None, "error": "HTTP 502"}
        return w(url)
    slept = []
    m = frbv.run([GROUP], tmp_path, http_get=flaky, now=NOW, mjop_loader=mjop_fake(), sleep=slept.append)
    tb = [r for r in m["requests"] if r["purpose"] == "3dbag-pand"][0]
    assert tb["http_status"] == 200 and tb["attempts"] == 3 and slept == [2, 4]
    assert pkg(tmp_path)["candidate_panden"][0]["quantity_evidence"] is not None


def test_persistent_5xx_is_recorded_not_hidden(tmp_path):
    w = simple_world(threed_status=502)
    m = run_group(tmp_path, w)
    tb = [r for r in m["requests"] if r["purpose"] == "3dbag-pand"][0]
    assert tb["http_status"] == 502 and tb["attempts"] == frbv.MAX_ATTEMPTS and "HTTP_502" in tb["flags"]
    assert any("THREEDBAG_ATTRIBUTES_MISSING" in f for f in pkg(tmp_path)["review_flags"])


def test_locatieserver_query_is_structured_by_street_and_number(tmp_path):
    w = simple_world()
    run_group(tmp_path, w)
    url = [u for u in w.calls if "locatieserver" in u][0]
    assert "fq=huisnummer%3A1" in url and "fq=straatnaam%3A%22Teststraat%22" in url and "fq=type%3Aadres" in url


def test_missing_address_explained_by_vbo_detail(tmp_path):
    """Pand heeft 42 VBO's maar slechts 41 adressen (801 ontbreekt): het VBO zonder adres wordt zichtbaar gemaakt."""
    addr = {str(n): "PM" for n in range(803, 884, 2)}
    w = World("Meppelweg", addr, {"PM": (42, 1957)}, place="'s-Gravenhage", postcode="2544AW")
    run_group(tmp_path, w, BY_ID["DOC-012"], mjop_fake(**MEPPELWEG_MJOP))
    bpc = pkg(tmp_path, "DOC-012")["building_project_candidate"]
    odd = next(h for h in bpc["scope_hypotheses"] if h["hypothesis_id"] == "ODD_ONLY")
    assert odd["addresses_missing"] == ["801"] and odd["counts"]["exact_bag_matches"] == 41
    row = odd["panden"][0]
    assert row["aantal_verblijfsobjecten_bag"] == 42 and row["distinct_vbo_ids_in_scope"] == 41
    assert row["vbo_fully_covered_by_scope"] is False
    assert row["vbo_without_matched_address"] == ["UNMATCHEDPM0"]
    assert odd["strength"] == "WEAK_BUILDING_PROJECT_CANDIDATE"
    assert bpc["best_supported_hypothesis_id"] is None
    assert any(f.startswith("NO_HYPOTHESIS_SUFFICIENTLY_SUPPORTED") for f in pkg(tmp_path, "DOC-012")["review_flags"])
    assert not any(f.startswith("SCOPE_AMBIGUOUS") for f in pkg(tmp_path, "DOC-012")["review_flags"])
    assert frbv.manifest_errors(tmp_path) == []


def test_vbo_detail_not_fetched_when_all_vbo_explained(tmp_path):
    w = maldenhof_world()
    run_group(tmp_path, w, BY_ID["DOC-005-006"], mjop_fake(**MALDENHOF_MJOP))
    assert not any("/verblijfsobject/items/" in u for u in w.calls)


def test_two_addresses_on_one_vbo_do_not_break_coverage(tmp_path):
    w = World("Teststraat", {"1": "P1", "2": "P1"}, {"P1": (1, 1981)})
    w.doc_orig = w.doc

    def doc(number, _w=w):
        d = _w.doc_orig(number)
        d["adresseerbaarobject_id"] = "0100SHARED"  # nevenadres: beide nummers op hetzelfde VBO
        return d
    w.doc = doc
    g = dict(GROUP, numbers=["1", "2"], postcode=None)
    run_group(tmp_path, w, g)
    h = pkg(tmp_path)["building_project_candidate"]["scope_hypotheses"][0]
    assert h["panden"][0]["distinct_vbo_ids_in_scope"] == 1 and h["panden"][0]["vbo_fully_covered_by_scope"] is True
    assert h["counts"]["exact_bag_matches"] == 2
