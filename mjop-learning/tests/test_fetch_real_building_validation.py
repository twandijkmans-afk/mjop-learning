"""Tests voor scripts/fetch_real_building_validation.py.

Alle PDOK/BAG/3D BAG-antwoorden hier zijn vaste, zelfgemaakte testantwoorden (fake http) — geen echte
gebouwgegevens; uitvoer gaat naar tmp_path, nooit naar data/."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fetch_real_building_validation as frbv  # noqa: E402

NOW = lambda: "2026-10-01T10:00:00Z"  # noqa: E731
LON, LAT, D = 4.95, 52.30, 0.0001
GROUP = {"group_id": "T-1", "document_ids": ["DOC-T"], "label": "test", "street": "Teststraat",
         "numbers": ["1"], "postcode": "1000 AA", "city": "Testdam"}


def ring(lon, lat):
    return [[lon - D, lat - D], [lon + D, lat - D], [lon + D, lat + D], [lon - D, lat + D], [lon - D, lat - D]]


def addr_doc(number="1", lon=LON, lat=LAT, city="Testdam"):
    return {"id": "adr-" + number, "weergavenaam": f"Teststraat {number}", "straatnaam": "Teststraat",
            "huisnummer": int(number), "postcode": "1000AA", "woonplaatsnaam": city,
            "centroide_ll": f"POINT({lon} {lat})", "adresseerbaarobject_id": "0000000000000" + number,
            "nummeraanduiding_id": "1111" + number}


def jb(obj):
    return json.dumps(obj).encode()


def make_http(docs, pand_ids=("0000000000000001",), threed_status=200, pdok_raw=None, threed_raw=None):
    calls = []

    def get(url):
        calls.append(url)
        if "locatieserver" in url:
            body = pdok_raw if pdok_raw is not None else jb({"response": {"docs": docs}})
            return {"status": 200, "body": body, "content_type": "application/json", "error": None}
        if "bag/ogc" in url:
            feats = [{"geometry": {"type": "Polygon", "coordinates": [ring(LON, LAT)]},
                      "properties": {"identificatie": pid, "bouwjaar": 1981, "status": "Pand in gebruik"}} for pid in pand_ids]
            return {"status": 200, "body": jb({"features": feats}), "content_type": "application/json", "error": None}
        if "3dbag" in url:
            pid = url.rsplit(".", 1)[1]
            if threed_status != 200:
                return {"status": threed_status, "body": jb({"detail": "nope"}), "content_type": "application/json", "error": f"HTTP {threed_status}"}
            body = threed_raw if threed_raw is not None else jb({"metadata": {"version": "vTEST"}, "feature": {"CityObjects": {
                "NL.IMBAG.Pand." + pid: {"attributes": {"b3_h_dak_50p": 12.5}}}}})
            return {"status": 200, "body": body, "content_type": "application/json", "error": None}
        return {"status": 404, "body": b"{}", "content_type": None, "error": "HTTP 404"}
    get.calls = calls
    return get


def run_group(tmp_path, http):
    return frbv.run([GROUP], tmp_path, http_get=http, now=NOW)


def pkg(tmp_path):
    return json.loads((tmp_path / "candidates" / "T-1.json").read_text())


def test_response_parsing_single_candidate(tmp_path):
    m = run_group(tmp_path, make_http([addr_doc()]))
    p = pkg(tmp_path)
    assert [x["bag_pand_id"] for x in p["candidate_panden"]] == ["0000000000000001"]
    tb = p["candidate_panden"][0]["threedbag"]
    assert tb["attributes"] == {"b3_h_dak_50p": 12.5} and tb["api_version"] == "vTEST"
    ar = p["address_results"][0]
    assert ar["address_matches"][0]["exact_match"] is True
    assert m["network_ok"] is True
    pd = [r for r in m["requests"] if r["purpose"] == "locatieserver"][0]
    assert pd["retrieved_identifiers"]["adresseerbaarobject_ids"] == ["00000000000001"]
    assert pd["retrieved_identifiers"]["nummeraanduiding_ids"] == ["11111"]


def test_missing_results(tmp_path):
    m = run_group(tmp_path, make_http([]))
    p = pkg(tmp_path)
    assert p["candidate_panden"] == []
    assert "NO_EXACT_ADDRESS_MATCH" in p["address_results"][0]["flags"]
    assert "GROUP: NO_CANDIDATE_PAND" in p["review_flags"]
    assert p["status"] == "CANDIDATE_UNREVIEWED"
    assert len(m["requests"]) == 1  # geen BAG/3D BAG-calls zonder exact adres


def test_non_exact_address_is_not_used(tmp_path):
    d = addr_doc()
    d["huisnummer"] = 2
    run_group(tmp_path, make_http([d]))
    assert pkg(tmp_path)["candidate_panden"] == []


def test_multiple_candidates_flagged(tmp_path):
    run_group(tmp_path, make_http([addr_doc()], pand_ids=("0000000000000001", "0000000000000002")))
    p = pkg(tmp_path)
    assert len(p["candidate_panden"]) == 2
    assert any("MULTIPLE_CANDIDATE_PANDEN" in f for f in p["review_flags"])
    assert "MULTIPLE_PANDEN_FOR_ADDRESS" in p["address_results"][0]["flags"]
    assert p["approval"]["building_link_approved"] is False


def test_multiple_exact_address_matches_flagged(tmp_path):
    run_group(tmp_path, make_http([addr_doc(), addr_doc(city="Elders")]))
    flags = pkg(tmp_path)["address_results"][0]["flags"]
    assert "MULTIPLE_EXACT_ADDRESS_MATCHES" in flags and "EXACT_MATCH_IN_OTHER_CITY" in flags


def test_malformed_pdok_response(tmp_path):
    m = run_group(tmp_path, make_http([], pdok_raw=b"<html>not json"))
    r = m["requests"][0]
    assert r["parse_status"] == "MALFORMED_RESPONSE" and "MALFORMED_RESPONSE" in r["flags"]
    assert (tmp_path / r["raw_response_path"]).read_bytes() == b"<html>not json"  # ruwe bytes bewaard
    assert "ADDRESS_LOOKUP_FAILED" in pkg(tmp_path)["address_results"][0]["flags"]


def test_unexpected_shape_and_malformed_3dbag(tmp_path):
    m = run_group(tmp_path, make_http([addr_doc()], threed_raw=jb({"feature": {"CityObjects": {}}})))
    tb = [r for r in m["requests"] if r["purpose"] == "3dbag-pand"][0]
    assert "UNEXPECTED_SHAPE" in tb["flags"]
    assert any("THREEDBAG_ATTRIBUTES_MISSING" in f for f in pkg(tmp_path)["review_flags"])
    m2 = run_group(tmp_path / "b", make_http([addr_doc()], threed_raw=b"{oops"))
    assert "MALFORMED_RESPONSE" in [r for r in m2["requests"] if r["purpose"] == "3dbag-pand"][0]["flags"]


def test_threedbag_404(tmp_path):
    m = run_group(tmp_path, make_http([addr_doc()], threed_status=404))
    tb = [r for r in m["requests"] if r["purpose"] == "3dbag-pand"][0]
    assert tb["http_status"] == 404 and "THREEDBAG_NOT_FOUND" in tb["flags"]


def test_network_error_recorded_and_not_ok(tmp_path):
    def down(url):
        return {"status": None, "body": b"", "content_type": None, "error": "URLError: 403 CONNECT"}
    m = run_group(tmp_path, down)
    assert m["network_ok"] is False
    assert m["requests"][0]["parse_status"] == "NETWORK_ERROR" and m["requests"][0]["raw_response_path"] is None


def test_manifest_hashes_and_tamper_detection(tmp_path):
    m = run_group(tmp_path, make_http([addr_doc()]))
    assert frbv.manifest_errors(tmp_path) == []
    for r in m["requests"]:
        data = (tmp_path / r["raw_response_path"]).read_bytes()
        assert r["raw_response_sha256"] == frbv.sha256_bytes(data) and r["raw_response_bytes"] == len(data)
        assert r["endpoint"] and r["http_status"] == 200 and r["requested_address"]
    assert (tmp_path / "raw" / "pdok").is_dir() and (tmp_path / "raw" / "3dbag").is_dir()
    victim = tmp_path / m["requests"][0]["raw_response_path"]
    victim.write_bytes(b"{}")
    assert any("sha256" in e for e in frbv.manifest_errors(tmp_path))


def test_manifest_reproducible(tmp_path):
    run_group(tmp_path / "a", make_http([addr_doc()]))
    run_group(tmp_path / "b", make_http([addr_doc()]))
    assert (tmp_path / "a" / "manifest.json").read_bytes() == (tmp_path / "b" / "manifest.json").read_bytes()


def test_no_automatic_building_approval(tmp_path):
    m = run_group(tmp_path, make_http([addr_doc()]))
    p = pkg(tmp_path)
    assert p["status"] == "CANDIDATE_UNREVIEWED"
    assert p["approval"] == {"building_link_approved": False, "approved_by": None, "approved_at": None}
    assert p["human_confirmation_required"]
    assert set(p["not_done_in_this_step"].values()) == {False}
    assert m["approval_summary"]["any_building_link_approved"] is False
    # tamper: goedgekeurde kandidaat moet door manifest_errors worden afgewezen
    path = tmp_path / "candidates" / "T-1.json"
    p["approval"]["building_link_approved"] = True
    path.write_text(json.dumps(p))
    assert frbv.manifest_errors(tmp_path)


def test_only_candidates_written_no_canonical_paths(tmp_path):
    run_group(tmp_path, make_http([addr_doc()]))
    top = {p.name for p in tmp_path.iterdir()}
    assert top == {"raw", "candidates", "manifest.json"}


def test_default_groups_cover_required_addresses():
    ids = {g["group_id"]: g for g in frbv.GROUPS}
    assert ids["DOC-005-006"]["document_ids"] == ["DOC-005", "DOC-006"]
    assert ids["DOC-005-006"]["numbers"][0] == "240" and ids["DOC-005-006"]["numbers"][-1] == "296"
    assert ids["DOC-012"]["numbers"] == ["819"] and ids["DOC-012"]["street"] == "Meppelweg"
