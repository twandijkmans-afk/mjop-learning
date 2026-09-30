"""Real Building Validation v1 — DATA RETRIEVAL + CANDIDATE GENERATION (geen goedkeuring).

Haalt voor opgegeven adressen publieke PDOK/BAG- en 3D BAG-antwoorden op (bedoeld voor GitHub Actions,
omdat egress vanuit de Claude Cloud-omgeving naar api.pdok.nl / api.3dbag.nl wordt geweigerd), bewaart de
RUWE responsbytes onveranderd, en genereert een kandidatenpakket + manifest met provenance en sha256's.

Dit script schrijft NOOIT: een building-link, legal_vve, crosswalk of canonical MJOP-data, en keurt nooit
automatisch een kandidaat goed. Elk kandidaatpakket heeft status CANDIDATE_UNREVIEWED en
approval.building_link_approved = false; een mens moet het pakket beoordelen.

Opvraagketen (gelijk aan MJOP-App src/app.js lookupBuilding):
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
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Endpoints en pure hulpfuncties (gelijk aan scripts/bag_snapshots.py; hier bewust zelfstandig zodat dit script
# ook zonder dat bestand werkt).
PDOK_FREE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
BAG_PAND_ITEMS = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"
BAG3D_ITEM = "https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.{pand_id}"
BBOX_DEG = 0.00018


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def norm_postcode(s):
    return re.sub(r"\s+", "", (s or "")).upper()


def exact_address_match(doc, street, number, postcode):
    """PDOK-adresdocument exact gelijk aan de gevraagde straat + huisnummer (+ postcode)? Geen fuzzy matching."""
    if norm(doc.get("straatnaam")) != norm(street):
        return False
    nr = str(doc.get("huisnummer", "")) + (doc.get("huisletter") or "") + \
        (("-" + doc["huisnummertoevoeging"]) if doc.get("huisnummertoevoeging") else "")
    if norm(nr) != norm(str(number)):
        return False
    if postcode and norm_postcode(doc.get("postcode")) != norm_postcode(postcode):
        return False
    return True


def point_in_ring(ring, x, y):
    c = False
    j = len(ring) - 2
    for i in range(len(ring) - 1):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            c = not c
        j = i
    return c


def outer_rings(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    if geometry["type"] == "MultiPolygon":
        return [p[0] for p in geometry["coordinates"]]
    return []


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "external" / "building_validation" / "real_validation_v1"
TOOL_VERSION = "fetch_real_building_validation_v1.2.0"
MAX_ATTEMPTS = 3
MAX_VBO_DETAIL = 60  # alleen voor panden met een onverklaard verschil tussen aantal VBO en gevonden adressen

# Documentgroepen. Per groep wordt het HELE huisnummerbereik uit de MJOP-bron opgevraagd (range_from..range_to,
# alle gehele nummers). Welke nummers daadwerkelijk bij de VvE horen (alleen even/oneven, of alle) staat NIET in
# de MJOP-bron en wordt niet gegokt: elke mogelijkheid is een scope_hypothese die apart wordt beoordeeld.
GROUPS = [
    {"group_id": "DOC-005-006", "document_ids": ["DOC-005", "DOC-006"], "label": "VvE Maldenhof 240-296",
     "street": "Maldenhof", "range_from": 240, "range_to": 296, "city": "Amsterdam", "document_address_number": 240,
     "scope_hypotheses": [
         {"hypothesis_id": "EVEN_ONLY", "parity": "even",
          "description": "Alleen even huisnummers 240,242,...,296",
          "basis": "Documentadres is 240 (even); het aantal even nummers in 240-296 is 29 = MJOP number_of_units."},
         {"hypothesis_id": "ALL_NUMBERS", "parity": "all", "description": "Alle huisnummers 240..296",
          "basis": "Bereik '240 - 296' zonder pariteit gelezen."}]},
    {"group_id": "DOC-012", "document_ids": ["DOC-012"], "label": "VvE Meppelweg 801-883 (documentadres Meppelweg 819)",
     "street": "Meppelweg", "range_from": 801, "range_to": 883, "city": "Den Haag", "document_address_number": 819,
     "scope_hypotheses": [
         {"hypothesis_id": "ODD_ONLY", "parity": "odd", "description": "Alleen oneven huisnummers 801,803,...,883",
          "basis": "Documentadres is 819 (oneven); bron noemt pariteit en aantal eenheden niet."},
         {"hypothesis_id": "ALL_NUMBERS", "parity": "all", "description": "Alle huisnummers 801..883",
          "basis": "Bereik '801-883' zonder pariteit gelezen."}],
     # Waarnemingen uit de MJOP-tekstlaag (pagina 2, xpdf-fixture sha256 86bf554e...), niet uit BAG:
     "mjop_source_observations": [
         {"document_id": "DOC-012", "page": 2, "field": "object_code", "value": "91154-2024", "text_fragment": "Code 91154-2024"},
         {"document_id": "DOC-012", "page": 2, "field": "opdrachtgever_naam", "value": "VvE Meppelweg 801-803",
          "text_fragment": "Naam VvE Meppelweg 801-803",
          "note": "Wijkt af van objectnaam 'VvE Meppelweg 801-883' (waarschijnlijk typfout; niet opgelost)."},
         {"document_id": "DOC-012", "page": 2, "field": "unit_count", "value": None,
          "text_fragment": None, "note": "Bron noemt geen aantal eenheden en geen pariteit van het bereik."}]},
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
    def __init__(self, out_dir, http_get=default_http_get, now=None, sleep=time.sleep):
        self.out_dir = Path(out_dir)
        self.http_get = http_get
        self.sleep = sleep
        self.now = now or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.requests = []
        self._by_url = {}

    def request(self, source, retrieval_source, purpose, url, requested_address):
        """Doet één GET (of hergebruikt dezelfde URL), bewaart de ruwe bytes, geeft (record, parsed_json|None)."""
        if url in self._by_url:
            rec = self._by_url[url]
            return rec, rec.get("_cached")
        attempts = 0
        while True:  # tijdelijke fouten (netwerk, 429, 5xx) opnieuw proberen; de laatste uitkomst wordt vastgelegd
            attempts += 1
            r = self.http_get(url)
            transient = r.get("status") is None or r["status"] == 429 or r["status"] >= 500
            if not transient or attempts >= MAX_ATTEMPTS:
                break
            self.sleep(2 * attempts)
        body = r.get("body") or b""
        rec = {
            "request_id": f"REQ-{len(self.requests) + 1:03d}",
            "requested_address": requested_address,
            "purpose": purpose,
            "retrieval_source": retrieval_source,
            "endpoint": url,
            "retrieved_at": self.now(),
            "http_status": r.get("status"),
            "attempts": attempts,
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
    """-> (attributes|None, api_version, cityobject|None, cityjson_feature|None)."""
    if not isinstance(parsed, dict):
        return None, None, None, None
    feat = parsed.get("feature") if isinstance(parsed.get("feature"), dict) else None
    cos = feat.get("CityObjects") if feat else None
    co = (cos or {}).get("NL.IMBAG.Pand." + pand_id) if isinstance(cos, dict) else None
    if not isinstance(co, dict):
        rec["parse_status"] = "UNEXPECTED_SHAPE"
        _flag(rec, "UNEXPECTED_SHAPE")
        return None, None, None, None
    return co.get("attributes"), (parsed.get("metadata") or {}).get("version"), co, feat


# --- plaatsnamen: Den Haag == 's-Gravenhage ---------------------------------------------------------
PLACE_ALIASES = {"den-haag": "s-gravenhage", "the-hague": "s-gravenhage"}


def canonical_place(name):
    """Normaliseert een plaatsnaam zodat tekstvarianten van dezelfde BAG-woonplaats gelijk zijn
    (bv. 'Den Haag' en "'s-Gravenhage"). Alleen bekende aliassen; geen fuzzy matching."""
    n = norm(name).replace("’", "'")
    n = re.sub(r"^'", "", n).replace(" ", "-")
    return PLACE_ALIASES.get(n, n)


def place_equivalent(a, b):
    return canonical_place(a) == canonical_place(b)


# --- opvraag per adres -------------------------------------------------------------------------------
def group_numbers(group):
    if group.get("numbers"):
        return [str(n) for n in group["numbers"]]
    return [str(n) for n in range(int(group["range_from"]), int(group["range_to"]) + 1)]


def process_address(fetcher, street, number, postcode, city, panden):
    """Eén adres -> address_result. `panden` is een gedeelde dict bag_pand_id -> candidate-pand (cache over adressen)."""
    requested = " ".join(x for x in (street, number, postcode or "", city or "") if x)
    res = {"requested_address": requested, "street": street, "number": number, "postcode_hint": postcode,
           "city": city, "pdok_request_id": None, "address_matches": [], "candidate_pand_ids": [], "flags": []}
    q = requested
    # Gestructureerd (fq op straat + huisnummer) zodat de ranking van vrije tekst een bestaand adres niet kan verbergen;
    # rows=20 laat ook huisletter-varianten (802A, 802B, ...) zien.
    url = PDOK_FREE + "?" + urllib.parse.urlencode(
        {"q": q, "fq": ["type:adres", f"huisnummer:{number}", f'straatnaam:"{street}"'], "rows": 20}, doseq=True)
    rec, parsed = fetcher.request("pdok", "PDOK Locatieserver v3_1 free", "locatieserver", url, requested)
    res["pdok_request_id"] = rec["request_id"]
    docs = parse_pdok_docs(rec, parsed)
    if docs is None:
        res["flags"].append("ADDRESS_LOOKUP_FAILED")
        return res
    exact = []
    variants = []
    for d in docs:
        if not isinstance(d, dict):
            continue
        m = re.match(r"POINT\(([-0-9.]+) ([-0-9.]+)\)", d.get("centroide_ll") or "")
        is_exact = exact_address_match(d, street, number, postcode)
        entry = {"pdok_id": d.get("id"), "weergavenaam": d.get("weergavenaam"), "postcode": d.get("postcode"),
                 "woonplaatsnaam": d.get("woonplaatsnaam"), "woonplaatscode": d.get("woonplaatscode"),
                 "centroide_ll": d.get("centroide_ll"), "nummeraanduiding_id": d.get("nummeraanduiding_id"),
                 "adresseerbaarobject_id": d.get("adresseerbaarobject_id"), "exact_match": is_exact}
        res["address_matches"].append(entry)
        if is_exact and m:
            exact.append((entry, float(m.group(1)), float(m.group(2))))
        elif (not is_exact and norm(d.get("straatnaam")) == norm(street) and str(d.get("huisnummer", "")) == str(number)):
            variants.append(entry["weergavenaam"])  # zelfde nummer met huisletter/toevoeging: context, geen match
    if variants:
        res["flags"].append("HOUSENUMBER_VARIANTS_PRESENT")
        res["housenumber_variants"] = sorted(v for v in variants if v)
    rec["retrieved_identifiers"] = {"adresseerbaarobject_ids": sorted({e["adresseerbaarobject_id"] for e, _, _ in exact if e["adresseerbaarobject_id"]}),
                                    "nummeraanduiding_ids": sorted({e["nummeraanduiding_id"] for e, _, _ in exact if e["nummeraanduiding_id"]}),
                                    "woonplaatscodes": sorted({e["woonplaatscode"] for e, _, _ in exact if e["woonplaatscode"]})}
    rec["normalized_candidate_data"] = {"exact_address_matches": len(exact), "total_docs": len(docs)}
    if not exact:
        res["flags"].append("NO_EXACT_ADDRESS_MATCH")
        _flag(rec, "NO_EXACT_ADDRESS_MATCH")
        return res
    if len(exact) > 1:
        res["flags"].append("MULTIPLE_EXACT_ADDRESS_MATCHES")
        _flag(rec, "MULTIPLE_EXACT_ADDRESS_MATCHES")
    # Alleen een echt andere plaats (niet Den Haag == 's-Gravenhage) geeft een waarschuwing.
    if city and any(not place_equivalent(e["woonplaatsnaam"], city) for e, _, _ in exact):
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
            vbo_hrefs = props.get("verblijfsobject.href")
            cand = panden.setdefault(pid, {"bag_pand_id": pid, "addresses_containing_point": [], "bag_properties": {
                **{k: props.get(k) for k in ("identificatie", "bouwjaar", "status", "gebruiksdoel", "aantal_verblijfsobjecten")},
                "verblijfsobject_href_count": len(vbo_hrefs) if isinstance(vbo_hrefs, list) else None},
                "verblijfsobject_hrefs": [h for h in vbo_hrefs if isinstance(h, str)] if isinstance(vbo_hrefs, list) else [],
                "bag_request_ids": [], "threedbag": None, "quantity_evidence": None, "verblijfsobjecten": None})
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
        entry["bag_pand_ids"] = sorted(set(hits))
    res["candidate_pand_ids"] = sorted(found)
    if not found:
        res["flags"].append("NO_PAND_FOR_ADDRESS")
    return res


# --- 3D BAG: alleen evidence -------------------------------------------------------------------------
EVIDENCE_GROUPS = {
    "ground_area_m2": ("b3_opp_grond",),
    "roof": ("b3_dak_type", "b3_opp_dak_plat", "b3_opp_dak_schuin", "b3_h_dak_min", "b3_h_dak_50p", "b3_h_dak_70p",
             "b3_h_dak_max", "b3_h_nok", "b3_n_nok", "b3_n_vlakken", "b3_is_glas_dak"),
    "walls_m2": ("b3_opp_buitenmuur", "b3_opp_scheidingsmuur"),
    "height_reference_m": ("b3_h_maaiveld",),
    "volume_m3": ("b3_volume_lod12", "b3_volume_lod13", "b3_volume_lod22"),
    "quality": ("b3_kwaliteitsindicator", "b3_pw_bron", "b3_pw_datum", "b3_rmse_lod12", "b3_rmse_lod13", "b3_rmse_lod22",
                "b3_val3dity_lod12", "b3_val3dity_lod13", "b3_val3dity_lod22"),
    "bag_reference": ("identificatie", "oorspronkelijkbouwjaar", "status", "fid", "documentnummer", "documentdatum"),
}


def geometry_identifiers(pand_id, co, feat, parsed):
    cos = (feat or {}).get("CityObjects") or {}
    parts = []
    for cid in (co or {}).get("children") or []:
        pc = cos.get(cid) or {}
        parts.append({"id": cid, "type": pc.get("type"),
                      "geometry": [{"type": g.get("type"), "lod": g.get("lod")} for g in pc.get("geometry") or []]})
    return {"cityjson_feature_id": (parsed or {}).get("id"), "cityobject_id": "NL.IMBAG.Pand." + pand_id,
            "cityobject_type": (co or {}).get("type"),
            "geometry": [{"type": g.get("type"), "lod": g.get("lod")} for g in (co or {}).get("geometry") or []],
            "building_parts": parts,
            "reference_system": (((parsed or {}).get("metadata") or {}).get("referenceSystem")
                                 or (((feat or {}).get("metadata") or {}).get("referenceSystem")))}


def build_quantity_evidence(attrs, geom, source):
    """Alleen doorgeven wat 3D BAG zegt (ongewijzigde waarden). GEEN vertaling naar onderhoudshoeveelheden,
    cost_per_m2 of MJOP-elementhoeveelheden: dat komt later via een expliciete crosswalk."""
    attrs = attrs or {}
    ev = {"evidence_only": True, "translated_to_maintenance_quantities": False, "source": source,
          "geometry_identifiers": geom}
    for name, keys in EVIDENCE_GROUPS.items():
        if name == "ground_area_m2":
            ev[name] = attrs.get(keys[0])
        else:
            ev[name] = {k: attrs.get(k) for k in keys}
    return ev


def fetch_3dbag(fetcher, pand):
    pid = pand["bag_pand_id"]
    url = BAG3D_ITEM.format(pand_id=pid)
    rec, parsed = fetcher.request("3dbag", "3D BAG API collections/pand", "3dbag-pand", url, f"BAG pand {pid}")
    attrs = version = co = feat = None
    if rec["parse_status"] == "OK":
        attrs, version, co, feat = parse_3dbag(rec, parsed, pid)
    if rec["http_status"] == 404:
        _flag(rec, "THREEDBAG_NOT_FOUND")
    rec["retrieved_identifiers"] = {"bag_pand_id": pid}
    rec["normalized_candidate_data"] = {"api_version": version, "attributes": attrs}
    source = {"request_id": rec["request_id"], "url": url, "http_status": rec["http_status"], "api_version": version,
              "raw_response_path": rec["raw_response_path"], "raw_response_sha256": rec["raw_response_sha256"]}
    pand["threedbag"] = {**source, "attributes": attrs, "flags": list(rec["flags"])}
    if attrs is not None:
        pand["quantity_evidence"] = build_quantity_evidence(attrs, geometry_identifiers(pid, co, feat, parsed), source)


def fetch_vbo_detail(fetcher, pand, exact_vbo_ids):
    """Voor een pand met meer VBO's dan gevonden adressen: haal de VBO's op om te zien WELK VBO geen adres heeft.
    Alleen retrieval; er wordt niets aan een adres of gebouw gekoppeld."""
    rows = []
    for href in pand["verblijfsobject_hrefs"]:
        rec, parsed = fetcher.request("pdok", "PDOK BAG OGC v2 verblijfsobject", "bag-vbo", href, f"BAG pand {pand['bag_pand_id']}")
        props = parsed.get("properties") if isinstance(parsed, dict) and isinstance(parsed.get("properties"), dict) else None
        if rec["parse_status"] == "OK" and props is None:
            rec["parse_status"] = "UNEXPECTED_SHAPE"
            _flag(rec, "UNEXPECTED_SHAPE")
        vid = str(props.get("identificatie")) if props and props.get("identificatie") else None
        rec["retrieved_identifiers"] = {"verblijfsobject_id": vid, "bag_pand_id": pand["bag_pand_id"]}
        rec["normalized_candidate_data"] = {"properties": props}
        rows.append({"request_id": rec["request_id"], "href": href, "http_status": rec["http_status"],
                     "raw_response_path": rec["raw_response_path"], "raw_response_sha256": rec["raw_response_sha256"],
                     "verblijfsobject_id": vid, "matched_to_exact_address": vid in exact_vbo_ids if vid else None,
                     "properties": props})
    pand["verblijfsobjecten"] = rows


def pand_exact_vbo_ids(address_results, pid):
    ids = set()
    for a in address_results:
        e = exact_entry(a)
        if e and pid in a["candidate_pand_ids"] and e.get("adresseerbaarobject_id"):
            ids.add(e["adresseerbaarobject_id"])
    return ids


# --- MJOP-context (uit data/extracted, alleen lezen) ---------------------------------------------------
def load_mjop_context(doc_ids, root=ROOT):
    """Leest building/object-velden uit data/extracted/<DOC>.json (read-only) met provenance. Verzint niets."""
    docs = []
    for d in doc_ids:
        p = Path(root) / "data" / "extracted" / f"{d}.json"
        if not p.exists():
            docs.append({"document_id": d, "error": "EXTRACTED_FILE_MISSING"})
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        b, dl, meta = j.get("building") or {}, j.get("document_level_values") or {}, j.get("extraction_metadata") or {}

        def val(x):
            return x.get("value") if isinstance(x, dict) else None

        def prov(x):
            pr = (x or {}).get("provenance") or {} if isinstance(x, dict) else {}
            return {"page": pr.get("page"), "text_fragment": pr.get("text_fragment")}
        docs.append({"document_id": d, "object_name": val(dl.get("object_name")), "address": val(b.get("address")),
                     "postcode": val(dl.get("object_postcode")), "city": val(dl.get("object_city")),
                     "number_of_units": val(b.get("number_of_units")), "construction_year": val(b.get("construction_year")),
                     "inspection_date": val(b.get("inspection_date")),
                     "source_sha256": meta.get("source_sha256"), "source_relative_path": meta.get("source_relative_path"),
                     "provenance": {k: prov(v) for k, v in (("address", b.get("address")), ("number_of_units", b.get("number_of_units")),
                                                            ("construction_year", b.get("construction_year")),
                                                            ("postcode", dl.get("object_postcode")), ("city", dl.get("object_city")))}})
    return docs


def combine_mjop(docs):
    """Eén waarde per veld als alle documenten het eens zijn; anders None + conflict (niet automatisch oplossen)."""
    out, conflicts = {}, []
    for f in ("number_of_units", "construction_year", "postcode", "city", "address", "object_name"):
        vals = {json.dumps(d.get(f)) for d in docs if d.get(f) is not None}
        if len(vals) == 1:
            out[f] = json.loads(next(iter(vals)))
        else:
            out[f] = None
            if len(vals) > 1:
                conflicts.append(f"MJOP_DOCUMENTS_DISAGREE:{f}")
    return out, conflicts


# --- scope-hypotheses en beoordeling ---------------------------------------------------------------------
def hypothesis_numbers(h, numbers):
    par = h.get("parity", "all")
    return [n for n in numbers if par == "all" or (par == "even") == (int(n) % 2 == 0)]


BLOCKING_ADDRESS_FLAGS = {"MULTIPLE_EXACT_ADDRESS_MATCHES", "EXACT_MATCH_IN_OTHER_CITY", "NO_PAND_FOR_ADDRESS",
                          "MULTIPLE_PANDEN_FOR_ADDRESS", "ADDRESS_LOOKUP_FAILED", "PAND_LOOKUP_FAILED",
                          "HOUSENUMBER_VARIANTS_PRESENT"}
STRENGTH_ORDER = {"STRONG_BUILDING_PROJECT_CANDIDATE": 3, "MODERATE_BUILDING_PROJECT_CANDIDATE": 2,
                  "WEAK_BUILDING_PROJECT_CANDIDATE": 1, "NO_BUILDING_PROJECT_CANDIDATE": 0}


def exact_entry(ar):
    ex = [m for m in ar["address_matches"] if m["exact_match"]]
    return ex[0] if ex else None


def unmatched_vbo_details(pand, numbers):
    """Adres-/VBO-gegevens (uit BAG) van VBO's in het pand zonder exact adres in de opgevraagde nummers."""
    rows = pand.get("verblijfsobjecten")
    if not rows:
        return None
    lo, hi = min(int(n) for n in numbers), max(int(n) for n in numbers)
    out = []
    for v in rows:
        if v["matched_to_exact_address"] is True:
            continue
        pr = v.get("properties") or {}
        hn = pr.get("huisnummer")
        out.append({"verblijfsobject_id": v["verblijfsobject_id"], "huisnummer": hn, "huisletter": pr.get("huisletter"),
                    "toevoeging": pr.get("toevoeging"), "postcode": pr.get("postcode"), "status": pr.get("status"),
                    "gebruiksdoel": pr.get("gebruiksdoel"), "oppervlakte": pr.get("oppervlakte"),
                    "outside_requested_number_range": (not (lo <= int(hn) <= hi)) if isinstance(hn, int) else None,
                    "raw_response_sha256": v["raw_response_sha256"]})
    return out


def assess_hypothesis(h, numbers, by_number, panden, mjop, doc_address_number):
    nums = hypothesis_numbers(h, numbers)
    in_scope = set(nums)
    found, missing, flags = [], [], []
    per_pand, per_pand_vbo = {}, {}
    for n in nums:
        ar = by_number[n]
        e = exact_entry(ar)
        if not e:
            missing.append(n)
            continue
        found.append({"number": n, "weergavenaam": e["weergavenaam"], "postcode": e["postcode"],
                      "woonplaatsnaam": e["woonplaatsnaam"], "woonplaatscode": e["woonplaatscode"],
                      "nummeraanduiding_id": e["nummeraanduiding_id"],
                      "adresseerbaarobject_id": e["adresseerbaarobject_id"], "bag_pand_ids": ar["candidate_pand_ids"],
                      "flags": ar["flags"]})
        for pid in ar["candidate_pand_ids"]:
            per_pand.setdefault(pid, []).append(n)
            per_pand_vbo.setdefault(pid, set()).add(e["adresseerbaarobject_id"] or ("NR" + n))
        flags += [f"{n}: {f}" for f in ar["flags"] if f in BLOCKING_ADDRESS_FLAGS]
    ids = [f["nummeraanduiding_id"] or f["number"] for f in found]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    pand_rows, vbo_total, covered = [], 0, True
    for pid in sorted(per_pand):
        bp = panden[pid]["bag_properties"]
        outside = sorted((n for n in numbers if n not in in_scope and pid in by_number[n]["candidate_pand_ids"]), key=int)
        vbo = bp.get("aantal_verblijfsobjecten")
        full = vbo is not None and vbo == len(per_pand_vbo[pid]) and not outside
        covered = covered and full
        vbo_total += vbo or 0
        ev = panden[pid].get("quantity_evidence") or {}
        pand_rows.append({"bag_pand_id": pid, "bouwjaar": bp.get("bouwjaar"), "aantal_verblijfsobjecten_bag": vbo,
                          "verblijfsobject_href_count": bp.get("verblijfsobject_href_count"),
                          "numbers_in_scope": sorted(per_pand[pid], key=int), "distinct_vbo_ids_in_scope": len(per_pand_vbo[pid]),
                          "numbers_queried_outside_scope": outside,
                          "vbo_without_matched_address": [v["verblijfsobject_id"] or v["href"] for v in (panden[pid].get("verblijfsobjecten") or [])
                                                          if v["matched_to_exact_address"] is not True] if panden[pid].get("verblijfsobjecten") else None,
                          "vbo_without_matched_address_details": unmatched_vbo_details(panden[pid], numbers),
                          "vbo_fully_covered_by_scope": full, "ground_area_m2": ev.get("ground_area_m2"),
                          "has_3dbag_evidence": bool(ev)})
    hist = {}
    for r in pand_rows:
        k = str(len(r["numbers_in_scope"]))
        hist[k] = hist.get(k, 0) + 1
    units = mjop.get("number_of_units")
    doc_e = exact_entry(by_number[str(doc_address_number)]) if doc_address_number is not None and str(doc_address_number) in by_number else None
    checks = {
        "all_requested_found": not missing and bool(nums),
        "no_blocking_address_flags": not flags and not dup,
        "vbo_fully_covered": bool(pand_rows) and covered,
        "units_known": units is not None,
        "units_equal_addresses_and_vbo": (units == len(found) == vbo_total) if units is not None else None,
        "postcode_matches_document_address": (norm(mjop.get("postcode") or "").replace(" ", "") == norm(doc_e["postcode"]).replace(" ", ""))
        if (doc_e and mjop.get("postcode")) else None,
        "place_matches_document_city": place_equivalent(doc_e["woonplaatsnaam"], mjop["city"]) if (doc_e and mjop.get("city")) else None,
        "construction_year_matches_all_panden": (all(r["bouwjaar"] == mjop["construction_year"] for r in pand_rows)
                                                 if (mjop.get("construction_year") is not None and pand_rows) else None),
        "document_address_number_in_scope": (str(doc_address_number) in in_scope) if doc_address_number is not None else None,
    }
    base = checks["all_requested_found"] and checks["no_blocking_address_flags"] and checks["vbo_fully_covered"] \
        and checks["postcode_matches_document_address"] is not False and checks["place_matches_document_city"] is not False
    if not found:
        strength = "NO_BUILDING_PROJECT_CANDIDATE"
    elif base and checks["units_equal_addresses_and_vbo"] is True and checks["construction_year_matches_all_panden"] is not False:
        strength = "STRONG_BUILDING_PROJECT_CANDIDATE"
    elif base and checks["units_equal_addresses_and_vbo"] is None:
        strength = "MODERATE_BUILDING_PROJECT_CANDIDATE"  # aantal eenheden ontbreekt in MJOP: geen sterke bevestiging mogelijk
    else:
        strength = "WEAK_BUILDING_PROJECT_CANDIDATE"
    if checks["construction_year_matches_all_panden"] is False:
        flags.append("CONSTRUCTION_YEAR_MISMATCH_MJOP_VS_BAG")
    for r in pand_rows:
        for d in r["vbo_without_matched_address_details"] or []:
            if d["outside_requested_number_range"]:
                flags.append(f"PAND_{r['bag_pand_id']}_HAS_VBO_OUTSIDE_REQUESTED_RANGE: huisnummer {d['huisnummer']}"
                             f"{d['huisletter'] or ''} ({d['postcode']}, {d['status']})")
    if missing:
        flags.append("ADDRESSES_MISSING_IN_BAG: " + ",".join(missing))
    if dup:
        flags.append("DUPLICATE_BAG_ADDRESSES: " + ",".join(dup))
    return {"hypothesis_id": h["hypothesis_id"], "description": h.get("description"), "basis": h.get("basis"),
            "requested_numbers": nums,
            "counts": {"requested_addresses": len(nums), "unique_requested_addresses": len(set(nums)),
                       "exact_bag_matches": len(found), "unique_bag_addresses": len(set(ids)),
                       "missing": len(missing), "unique_bag_panden": len(pand_rows), "vbo_total_bag": vbo_total,
                       "addresses_per_pand_histogram": dict(sorted(hist.items()))},
            "addresses_found": found, "addresses_missing": missing, "duplicate_bag_addresses": dup,
            "bag_pand_ids": [r["bag_pand_id"] for r in pand_rows], "panden": pand_rows,
            "mjop_number_of_units": units, "checks": checks, "strength": strength, "flags": flags}


def build_candidate_package(group, address_results, panden, run_id, mjop_docs=None):
    numbers = [a["number"] for a in address_results]
    by_number = {a["number"]: a for a in address_results}
    mjop_docs = mjop_docs or []
    mjop, conflicts = combine_mjop(mjop_docs)
    hyps = group.get("scope_hypotheses") or [{"hypothesis_id": "REQUESTED_NUMBERS", "parity": "all",
                                              "description": "Alle opgevraagde huisnummers", "basis": "Geen pariteit opgegeven."}]
    assessed = [assess_hypothesis(h, numbers, by_number, panden, mjop, group.get("document_address_number")) for h in hyps]
    top = max((STRENGTH_ORDER[a["strength"]] for a in assessed), default=0)
    best = [a for a in assessed if STRENGTH_ORDER[a["strength"]] == top]
    flags = list(conflicts)
    if len(best) == 1:
        best_id, strength = best[0]["hypothesis_id"], best[0]["strength"]
    else:
        best_id, strength = None, best[0]["strength"] if best else "NO_BUILDING_PROJECT_CANDIDATE"
        if top >= STRENGTH_ORDER["MODERATE_BUILDING_PROJECT_CANDIDATE"]:
            flags.append("SCOPE_AMBIGUOUS: meerdere hypotheses even sterk (" + ", ".join(a["hypothesis_id"] for a in best)
                         + "); menselijke keuze vereist")
        else:
            flags.append("NO_HYPOTHESIS_SUFFICIENTLY_SUPPORTED: geen scope-hypothese wordt door de BAG-data voldoende bevestigd")
    for a in assessed:
        flags += [f"[{a['hypothesis_id']}] {f}" for f in a["flags"]]
    pand_list = [panden[k] for k in sorted(panden)]
    for pnd in pand_list:
        pnd["referenced_by_hypotheses"] = [a["hypothesis_id"] for a in assessed if pnd["bag_pand_id"] in a["bag_pand_ids"]]
    for a in assessed:
        if a["hypothesis_id"] == best_id and len(a["bag_pand_ids"]) > 1:
            flags.append(f"GROUP: BUILDING_PROJECT_BESTAAT_UIT_{len(a['bag_pand_ids'])}_BAG_PANDEN (geen enkel pand is 'het gebouw')")
    if not pand_list:
        flags.append("GROUP: NO_CANDIDATE_PAND")
    for p in pand_list:
        tb = p["threedbag"] or {}
        if not tb or tb.get("attributes") is None:
            flags.append(f"{p['bag_pand_id']}: THREEDBAG_ATTRIBUTES_MISSING")
    return {
        "package_version": "real_validation_candidates_v2",
        "run_id": run_id,
        "group_id": group["group_id"],
        "document_ids": group["document_ids"],
        "label": group["label"],
        "status": "CANDIDATE_UNREVIEWED",
        "mjop_context": {"documents": mjop_docs, "combined": mjop, "conflicts": conflicts,
                         "document_address_number": group.get("document_address_number"),
                         "source_observations": group.get("mjop_source_observations") or []},
        "building_project_candidate": {
            "candidate_id": "BPC-" + group["group_id"],
            "kind": "LOGICAL_BUILDING_PROJECT_CANDIDATE",
            "note": "Een building_project/VvE kan uit meerdere BAG-panden bestaan; geen individueel pand is automatisch 'het gebouw'.",
            "status": "CANDIDATE_UNREVIEWED",
            "strength": strength,
            "best_supported_hypothesis_id": best_id,
            "selected_scope": None,
            "scope_hypotheses": assessed,
            "canonical_building_project_written": False,
        },
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


def run(groups, out_dir, http_get=default_http_get, now=None, mjop_loader=load_mjop_context, sleep=time.sleep):
    """Voert alle groepen uit; schrijft raw/, candidates/ en manifest.json. -> manifest."""
    out_dir = Path(out_dir)
    fetcher = Fetcher(out_dir, http_get=http_get, now=now, sleep=sleep)
    started = fetcher.now()
    run_id = "RBV1-" + started.replace(":", "").replace("-", "")
    packages = {}
    for g in groups:
        panden = {}
        results = [process_address(fetcher, g["street"], n, g.get("postcode"), g.get("city"), panden) for n in group_numbers(g)]
        for pid in sorted(panden):
            fetch_3dbag(fetcher, panden[pid])
            n_vbo = panden[pid]["bag_properties"].get("aantal_verblijfsobjecten")
            exact_ids = pand_exact_vbo_ids(results, pid)
            if (isinstance(n_vbo, int) and 0 < n_vbo <= MAX_VBO_DETAIL and n_vbo > len(exact_ids)
                    and len(panden[pid]["verblijfsobject_hrefs"]) == n_vbo):
                fetch_vbo_detail(fetcher, panden[pid], exact_ids)
        packages[g["group_id"]] = build_candidate_package(g, results, panden, run_id, mjop_loader(g["document_ids"]))
    for gid, pkg in packages.items():
        write_json(out_dir / "candidates" / f"{gid}.json", pkg)
    reqs = [{k: v for k, v in r.items() if not k.startswith("_")} for r in fetcher.requests]
    manifest = {
        "manifest_version": "real_validation_manifest_v2",
        "run_id": run_id,
        "tool": TOOL_VERSION,
        "generated_at": started,
        "network_ok": all(r["http_status"] is not None for r in reqs) and bool(reqs),
        "requests": reqs,
        "candidate_packages": {gid: {"path": f"candidates/{gid}.json",
                                     "sha256": sha256_bytes((out_dir / "candidates" / f"{gid}.json").read_bytes()),
                                     "status": p["status"],
                                     "strength": p["building_project_candidate"]["strength"],
                                     "best_supported_hypothesis_id": p["building_project_candidate"]["best_supported_hypothesis_id"],
                                     "review_flags": p["review_flags"],
                                     "candidate_pand_ids": [x["bag_pand_id"] for x in p["candidate_panden"]],
                                     "hypothesis_counts": {a["hypothesis_id"]: a["counts"] for a in p["building_project_candidate"]["scope_hypotheses"]}}
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
        else:
            pkg = json.loads(p.read_text(encoding="utf-8"))
            if pkg["approval"]["building_link_approved"] or pkg.get("building_project_candidate", {}).get("canonical_building_project_written"):
                errs.append(f"{gid}: kandidaat is goedgekeurd/canonical geschreven — niet toegestaan in deze stap")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Real Building Validation v1: PDOK/BAG + 3D BAG ophalen (alleen kandidaten)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    manifest = run(GROUPS, args.out)
    errs = manifest_errors(args.out)
    bad = [r for r in manifest["requests"] if r["http_status"] != 200]
    for gid, c in manifest["candidate_packages"].items():
        print(f"{gid}: {len(c['candidate_pand_ids'])} kandidaat-panden, {c['strength']}, {len(c['review_flags'])} review-vlaggen")
        for hid, cnt in c["hypothesis_counts"].items():
            print(f"  {hid}: {cnt}")
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
