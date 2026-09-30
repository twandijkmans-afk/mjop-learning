"""Real Building Validation v1 — DATA RETRIEVAL + CANDIDATE GENERATION (geen goedkeuring).

Haalt voor opgegeven adressen publieke PDOK/BAG- en 3D BAG-antwoorden op (bedoeld voor GitHub Actions,
omdat egress vanuit de Claude Cloud-omgeving naar api.pdok.nl / api.3dbag.nl wordt geweigerd), bewaart de
RUWE responsbytes onveranderd, en genereert een kandidatenpakket + manifest met provenance en sha256's.

Dit script schrijft NOOIT: een building-link, legal_vve, crosswalk of canonical MJOP-data, en keurt nooit
automatisch een kandidaat goed. Elk kandidaatpakket heeft status CANDIDATE_UNREVIEWED en
approval.building_link_approved = false; een mens moet het pakket beoordelen.

Opvraagketen (gelijk aan scripts/bag_snapshots.py en MJOP-App src/app.js lookupBuilding):
  PDOK Locatieserver 'free' (type:adres) -> centroide van een EXACT overeenkomend adres
  -> BAG OGC 'pand' items in een bbox rond dat punt -> panden waarvan de polygoon het punt BEVAT
  -> 3D BAG /collections/pand/items/NL.IMBAG.Pand.<id>.

Uitvoer (onder --out, standaard data/external/building_validation/real_validation_v1/):
  raw/pdok/*.json, raw/3dbag/*.json   ruwe responsbytes, bestandsnaam bevat sha256-prefix
  candidates/<GROUP>.json             kandidatenpakket per documentgroep
  manifest.json                       per request: adres, endpoint, status, bron, identifiers, pad, sha256, flags

    python scripts/fetch_real_building_validation.py --out data/external/building_validation/real_validation_v1
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bag_snapshots import (  # noqa: E402  (pure hulpfuncties, geen netwerk)
    BAG3D_ITEM, BAG_PAND_ITEMS, BBOX_DEG, PDOK_FREE, exact_address_match, norm, outer_rings, point_in_ring,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "external" / "building_validation" / "real_validation_v1"
TOOL_VERSION = "fetch_real_building_validation_v1.0.0"

# Documentgroepen. Maldenhof 240-296: DOC-005/DOC-006 noemen het complex als bereik; alle even huisnummers
# in het bereik worden opgevraagd zodat zichtbaar wordt over hoeveel panden het bereik verdeeld is.
GROUPS = [
    {"group_id": "DOC-005-006", "document_ids": ["DOC-005", "DOC-006"], "label": "VvE Maldenhof 240-296",
     "street": "Maldenhof", "numbers": [str(n) for n in range(240, 297, 2)], "postcode": None, "city": "Amsterdam"},
    {"group_id": "DOC-012", "document_ids": ["DOC-012"], "label": "VvE Meppelweg 801-883 (adres Meppelweg 819)",
     "street": "Meppelweg", "numbers": ["819"], "postcode": "2544 AW", "city": "Den Haag"},
]

HUMAN_CONFIRMATION_REQUIRED = [
    "Bevestig dat het beschreven adres/bereik in het MJOP-document overeenkomt met de kandidaat-BAG-panden.",
    "Bevestig per kandidaat-pand of het (deel van) het gebouw van dit document is (geen buurpand/aanbouw).",
    "Bevestig dat 3D BAG-attributen bij het gekozen pand horen vóór gebruik als quantity-evidence.",
    "Beslis pas daarna over building_project-koppeling, legal_vve-koppeling en crosswalk (niet in deze stap).",
]
NOT_DONE = {"building_project_linked": False, "legal_vve_linked": False, "crosswalk_written": False,
            "canonical_mjop_data_modified": False}


class RetrievalError(RuntimeError):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def default_http_get(url):
    """-> {status, body(bytes), content_type, error}. HTTP-fouten leveren status+body; netwerkfouten status None."""
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "mjop-learning/" + TOOL_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {"status": resp.status, "body": resp.read(), "content_type": resp.headers.get("Content-Type"), "error": None}
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return {"status": e.code, "body": body, "content_type": e.headers.get("Content-Type") if e.headers else None,
                "error": f"HTTP {e.code}"}
    except Exception as e:  # netwerk/proxy/TLS: nooit stil doorgaan
        return {"status": None, "body": b"", "content_type": None, "error": f"{type(e).__name__}: {e}"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class Fetcher:
    def __init__(self, out_dir, http_get=default_http_get, now=None):
        self.out_dir = Path(out_dir)
        self.http_get = http_get
        self.now = now or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.requests = []
        self._by_url = {}

    def request(self, source, retrieval_source, purpose, url, requested_address):
        """Doet één GET (of hergebruikt dezelfde URL), bewaart de ruwe bytes, geeft (record, parsed_json|None)."""
        if url in self._by_url:
            rec = self._by_url[url]
            return rec, rec.get("_cached")
        r = self.http_get(url)
        body = r.get("body") or b""
        rec = {
            "request_id": f"REQ-{len(self.requests) + 1:03d}",
            "requested_address": requested_address,
            "purpose": purpose,
            "retrieval_source": retrieval_source,
            "endpoint": url,
            "retrieved_at": self.now(),
            "http_status": r.get("status"),
            "content_type": r.get("content_type"),
            "raw_response_path": None,
            "raw_response_sha256": None,
            "raw_response_bytes": len(body),
            "parse_status": None,
            "retrieved_identifiers": {},
            "normalized_candidate_data": {},
            "flags": [],
        }
        parsed = None
        if r.get("status") is None:
            rec["parse_status"] = "NETWORK_ERROR"
            rec["error"] = r.get("error")
            rec["flags"].append("NETWORK_ERROR")
        else:
            sha = sha256_bytes(body)
            rel = f"raw/{source}/{slug(requested_address)}__{purpose}__{sha[:12]}.json"
            path = self.out_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)  # ruwe bytes, ongewijzigd
            rec["raw_response_path"], rec["raw_response_sha256"] = rel, sha
            if r["status"] != 200:
                rec["parse_status"] = "HTTP_ERROR"
                rec["flags"].append(f"HTTP_{r['status']}")
            else:
                try:
                    parsed = json.loads(body.decode("utf-8"))
                    rec["parse_status"] = "OK"
                except (UnicodeDecodeError, ValueError):
                    rec["parse_status"] = "MALFORMED_RESPONSE"
                    rec["flags"].append("MALFORMED_RESPONSE")
        self.requests.append(rec)
        self._by_url[url] = rec
        rec["_cached"] = parsed
        return rec, parsed


def _flag(rec, flag):
    if flag not in rec["flags"]:
        rec["flags"].append(flag)


def parse_pdok_docs(rec, parsed):
    """-> docs-lijst of None (en zet vlag op rec)."""
    if parsed is None:
        return None
    docs = ((parsed.get("response") or {}).get("docs")) if isinstance(parsed, dict) else None
    if not isinstance(docs, list):
        rec["parse_status"] = "UNEXPECTED_SHAPE"
        _flag(rec, "UNEXPECTED_SHAPE")
        return None
    return docs


def parse_bag_features(rec, parsed):
    feats = parsed.get("features") if isinstance(parsed, dict) else None
    if not isinstance(feats, list):
        if parsed is not None:
            rec["parse_status"] = "UNEXPECTED_SHAPE"
            _flag(rec, "UNEXPECTED_SHAPE")
        return None
    return feats


def parse_3dbag(rec, parsed, pand_id):
    """-> (attributes|None, api_version)."""
    if not isinstance(parsed, dict):
        return None, None
    cos = (parsed.get("feature") or {}).get("CityObjects") if isinstance(parsed.get("feature"), dict) else None
    co = (cos or {}).get("NL.IMBAG.Pand." + pand_id) if isinstance(cos, dict) else None
    if not isinstance(co, dict):
        rec["parse_status"] = "UNEXPECTED_SHAPE"
        _flag(rec, "UNEXPECTED_SHAPE")
        return None, None
    return co.get("attributes"), (parsed.get("metadata") or {}).get("version")


def process_address(fetcher, street, number, postcode, city, panden):
    """Eén adres -> address_result. `panden` is een gedeelde dict bag_pand_id -> candidate-pand (cache over adressen)."""
    requested = " ".join(x for x in (street, number, postcode or "", city or "") if x)
    res = {"requested_address": requested, "street": street, "number": number, "postcode_hint": postcode,
           "city": city, "pdok_request_id": None, "address_matches": [], "candidate_pand_ids": [], "flags": []}
    q = " ".join(x for x in (street, number, postcode or "", city or "") if x)
    url = PDOK_FREE + "?" + urllib.parse.urlencode({"q": q, "fq": "type:adres", "rows": 10})
    rec, parsed = fetcher.request("pdok", "PDOK Locatieserver v3_1 free", "locatieserver", url, requested)
    res["pdok_request_id"] = rec["request_id"]
    docs = parse_pdok_docs(rec, parsed)
    if docs is None:
        res["flags"].append("ADDRESS_LOOKUP_FAILED")
        return res
    exact = []
    for d in docs:
        if not isinstance(d, dict):
            continue
        m = re.match(r"POINT\(([-0-9.]+) ([-0-9.]+)\)", d.get("centroide_ll") or "")
        is_exact = exact_address_match(d, street, number, postcode)
        entry = {"pdok_id": d.get("id"), "weergavenaam": d.get("weergavenaam"), "postcode": d.get("postcode"),
                 "woonplaatsnaam": d.get("woonplaatsnaam"), "centroide_ll": d.get("centroide_ll"),
                 "nummeraanduiding_id": d.get("nummeraanduiding_id"),
                 "adresseerbaarobject_id": d.get("adresseerbaarobject_id"), "exact_match": is_exact}
        res["address_matches"].append(entry)
        if is_exact and m:
            exact.append((entry, float(m.group(1)), float(m.group(2))))
    rec["retrieved_identifiers"] = {"adresseerbaarobject_ids": sorted({e["adresseerbaarobject_id"] for e, _, _ in exact if e["adresseerbaarobject_id"]}),
                                    "nummeraanduiding_ids": sorted({e["nummeraanduiding_id"] for e, _, _ in exact if e["nummeraanduiding_id"]})}
    rec["normalized_candidate_data"] = {"exact_address_matches": len(exact), "total_docs": len(docs)}
    if not exact:
        res["flags"].append("NO_EXACT_ADDRESS_MATCH")
        _flag(rec, "NO_EXACT_ADDRESS_MATCH")
        return res
    if len(exact) > 1:
        res["flags"].append("MULTIPLE_EXACT_ADDRESS_MATCHES")
        _flag(rec, "MULTIPLE_EXACT_ADDRESS_MATCHES")
    if city and any(norm(e["woonplaatsnaam"]) != norm(city) for e, _, _ in exact):
        res["flags"].append("EXACT_MATCH_IN_OTHER_CITY")
        _flag(rec, "EXACT_MATCH_IN_OTHER_CITY")

    found = set()
    for entry, lon, lat in exact:
        bbox = ",".join(str(v) for v in (lon - BBOX_DEG, lat - BBOX_DEG, lon + BBOX_DEG, lat + BBOX_DEG))
        burl = BAG_PAND_ITEMS + "?" + urllib.parse.urlencode({"f": "json", "limit": 20, "bbox": bbox})
        brec, bparsed = fetcher.request("pdok", "PDOK BAG OGC v2 pand", "bag-pand", burl, requested)
        feats = parse_bag_features(brec, bparsed)
        if feats is None:
            res["flags"].append("PAND_LOOKUP_FAILED")
            continue
        hits = []
        for f in feats:
            if not isinstance(f, dict) or not f.get("geometry"):
                continue
            try:
                inside = any(point_in_ring(r, lon, lat) for r in outer_rings(f["geometry"]))
            except (KeyError, TypeError, ValueError, IndexError):
                _flag(brec, "MALFORMED_GEOMETRY")
                continue
            if not inside:
                continue
            props = f.get("properties") or {}
            pid = str(props.get("identificatie") or "")
            if not pid:
                continue
            hits.append(pid)
            found.add(pid)
            cand = panden.setdefault(pid, {"bag_pand_id": pid, "addresses_containing_point": [], "bag_properties": {
                k: props.get(k) for k in ("identificatie", "bouwjaar", "status", "gebruiksdoel", "aantal_verblijfsobjecten")},
                "bag_request_ids": [], "threedbag": None})
            if requested not in cand["addresses_containing_point"]:
                cand["addresses_containing_point"].append(requested)
            if brec["request_id"] not in cand["bag_request_ids"]:
                cand["bag_request_ids"].append(brec["request_id"])
        brec["retrieved_identifiers"] = {"bag_pand_ids": sorted(set(hits))}
        brec["normalized_candidate_data"] = {"features_returned": len(feats), "panden_containing_address_point": sorted(set(hits))}
        if not hits:
            _flag(brec, "NO_PAND_CONTAINS_POINT")
        if len(set(hits)) > 1:
            _flag(brec, "MULTIPLE_PANDEN_CONTAIN_POINT")
            res["flags"].append("MULTIPLE_PANDEN_FOR_ADDRESS")
    res["candidate_pand_ids"] = sorted(found)
    if not found:
        res["flags"].append("NO_PAND_FOR_ADDRESS")
    return res


def fetch_3dbag(fetcher, pand):
    pid = pand["bag_pand_id"]
    url = BAG3D_ITEM.format(pand_id=pid)
    rec, parsed = fetcher.request("3dbag", "3D BAG API collections/pand", "3dbag-pand", url, f"BAG pand {pid}")
    attrs, version = parse_3dbag(rec, parsed, pid) if rec["parse_status"] == "OK" else (None, None)
    if rec["http_status"] == 404:
        _flag(rec, "THREEDBAG_NOT_FOUND")
    rec["retrieved_identifiers"] = {"bag_pand_id": pid}
    rec["normalized_candidate_data"] = {"api_version": version, "attributes": attrs}
    pand["threedbag"] = {"request_id": rec["request_id"], "url": url, "http_status": rec["http_status"],
                         "raw_response_path": rec["raw_response_path"], "raw_response_sha256": rec["raw_response_sha256"],
                         "api_version": version, "attributes": attrs, "flags": list(rec["flags"])}


def build_candidate_package(group, address_results, panden, run_id):
    flags = []
    for a in address_results:
        for f in a["flags"]:
            flags.append(f"{a['requested_address']}: {f}")
    pand_list = [panden[k] for k in sorted(panden)]
    if not pand_list:
        flags.append("GROUP: NO_CANDIDATE_PAND")
    if len(pand_list) > 1:
        flags.append(f"GROUP: MULTIPLE_CANDIDATE_PANDEN ({len(pand_list)}); menselijke selectie vereist")
    for p in pand_list:
        tb = p["threedbag"] or {}
        if not tb or tb.get("attributes") is None:
            flags.append(f"{p['bag_pand_id']}: THREEDBAG_ATTRIBUTES_MISSING")
    return {
        "package_version": "real_validation_candidates_v1",
        "run_id": run_id,
        "group_id": group["group_id"],
        "document_ids": group["document_ids"],
        "label": group["label"],
        "status": "CANDIDATE_UNREVIEWED",
        "requested_addresses": [a["requested_address"] for a in address_results],
        "address_results": address_results,
        "candidate_panden": pand_list,
        "review_flags": flags,
        "approval": {"building_link_approved": False, "approved_by": None, "approved_at": None},
        "human_confirmation_required": HUMAN_CONFIRMATION_REQUIRED,
        "not_done_in_this_step": dict(NOT_DONE),
    }


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def run(groups, out_dir, http_get=default_http_get, now=None):
    """Voert alle groepen uit; schrijft raw/, candidates/ en manifest.json. -> manifest."""
    out_dir = Path(out_dir)
    fetcher = Fetcher(out_dir, http_get=http_get, now=now)
    started = fetcher.now()
    run_id = "RBV1-" + started.replace(":", "").replace("-", "")
    packages = {}
    for g in groups:
        panden = {}
        results = [process_address(fetcher, g["street"], n, g.get("postcode"), g.get("city"), panden) for n in g["numbers"]]
        for pid in sorted(panden):
            fetch_3dbag(fetcher, panden[pid])
        packages[g["group_id"]] = build_candidate_package(g, results, panden, run_id)
    for gid, pkg in packages.items():
        write_json(out_dir / "candidates" / f"{gid}.json", pkg)
    reqs = []
    for r in fetcher.requests:
        r = {k: v for k, v in r.items() if not k.startswith("_")}
        reqs.append(r)
    manifest = {
        "manifest_version": "real_validation_manifest_v1",
        "run_id": run_id,
        "tool": TOOL_VERSION,
        "generated_at": started,
        "network_ok": all(r["http_status"] is not None for r in reqs) and bool(reqs),
        "requests": reqs,
        "candidate_packages": {gid: {"path": f"candidates/{gid}.json",
                                     "sha256": sha256_bytes((out_dir / "candidates" / f"{gid}.json").read_bytes()),
                                     "status": p["status"], "review_flags": p["review_flags"],
                                     "candidate_pand_ids": [x["bag_pand_id"] for x in p["candidate_panden"]]}
                               for gid, p in packages.items()},
        "approval_summary": {"any_building_link_approved": False, **NOT_DONE},
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest


def manifest_errors(out_dir):
    """Controleert manifest tegen de bestanden: bestaan + sha256 van elke raw response en elk kandidatenpakket."""
    out_dir = Path(out_dir)
    m = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    errs = []
    for r in m["requests"]:
        if r["raw_response_path"] is None:
            continue
        p = out_dir / r["raw_response_path"]
        if not p.exists():
            errs.append(f"{r['request_id']}: raw bestand ontbreekt")
        elif sha256_bytes(p.read_bytes()) != r["raw_response_sha256"]:
            errs.append(f"{r['request_id']}: sha256 komt niet overeen")
    for gid, c in m["candidate_packages"].items():
        p = out_dir / c["path"]
        if not p.exists() or sha256_bytes(p.read_bytes()) != c["sha256"]:
            errs.append(f"{gid}: kandidatenpakket ontbreekt of sha256 komt niet overeen")
        elif json.loads(p.read_text(encoding="utf-8"))["approval"]["building_link_approved"]:
            errs.append(f"{gid}: kandidaat is goedgekeurd — niet toegestaan in deze stap")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Real Building Validation v1: PDOK/BAG + 3D BAG ophalen (alleen kandidaten)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    manifest = run(GROUPS, args.out)
    errs = manifest_errors(args.out)
    bad = [r for r in manifest["requests"] if r["http_status"] != 200]
    for gid, c in manifest["candidate_packages"].items():
        print(f"{gid}: {len(c['candidate_pand_ids'])} kandidaat-panden, {len(c['review_flags'])} review-vlaggen")
    print(f"{len(manifest['requests'])} requests, {len(bad)} niet-200")
    for r in bad:
        print(f"  {r['request_id']} {r['endpoint']} -> {r['http_status']} {r.get('error') or ''}", file=sys.stderr)
    if errs:
        print("MANIFEST-FOUT: " + "; ".join(errs), file=sys.stderr)
        return 4
    if not manifest["network_ok"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
