"""BAG/3D BAG-snapshots — onveranderlijke vastlegging van wat PDOK/BAG/3D BAG teruggaven voor een adres.

Zie docs/building_link_3dbag_evidence_v1.md. Een snapshot is BEWIJS voor een building-link-kandidaat en de
bron van 3D BAG-evidence; het bevestigt zelf niets.

Opvraagketen (dezelfde als MJOP-App src/app.js lookupBuilding):
  PDOK Locatieserver 'free' (type:adres) -> centroïde van een EXACT overeenkomend adres
  -> BAG OGC 'pand' items in een bbox rond dat punt -> panden waarvan de polygoon het punt BEVAT
  -> 3D BAG /collections/pand/items/NL.IMBAG.Pand.<id> (attributen ongewijzigd bewaard).

Geen fuzzy matching: een adres telt alleen als straat, huisnummer (+ toevoeging) en, indien opgegeven,
postcode exact overeenkomen (hoofdletters/witruimte genormaliseerd). Niet-exacte PDOK-treffers worden
bewaard als context maar niet gebruikt.

Status: de opvraagroutes zijn NOT_VERIFIED_AGAINST_LIVE_API vanuit de ontwikkelomgeving (egress naar
api.pdok.nl en api.3dbag.nl geweigerd). Tests gebruiken vaste antwoorden.

    python scripts/bag_snapshots.py fetch --document DOC-005 --street Maldenhof --number 240 \
        --postcode "1106 EZ" --city Amsterdam
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "bag_snapshots"
TOOL_VERSION = "bag_snapshots_v1.0.0"
LIVE_API_STATUS = "NOT_VERIFIED_AGAINST_LIVE_API"

PDOK_FREE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
BAG_PAND_ITEMS = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"
BAG3D_ITEM = "https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.{pand_id}"
BBOX_DEG = 0.00018


class SnapshotError(RuntimeError):
    pass


def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def default_http_get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "mjop-learning/" + TOOL_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # netwerk/egress: nooit stil doorgaan
        raise SnapshotError(f"ophalen mislukt voor {url}: {e}") from e


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def norm_postcode(s):
    return re.sub(r"\s+", "", (s or "")).upper()


def exact_address_match(doc, street, number, postcode):
    """PDOK-adresdocument exact gelijk aan de gevraagde straat + huisnummer (+ postcode)?"""
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


def fetch_snapshot(document_id, street, number, postcode=None, city=None, http_get=default_http_get, fetched_at=None):
    fetched_at = fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    requests, raw = [], {}

    def get(url):
        status, body = http_get(url)
        sha = canonical_sha256(body)
        requests.append({"url": url, "http_status": status, "response_sha256": sha})
        raw[sha] = body
        if status != 200:
            raise SnapshotError(f"HTTP {status} voor {url}")
        return body

    q = " ".join(x for x in (street, str(number), postcode or "", city or "") if x).strip()
    free = get(PDOK_FREE + "?" + urllib.parse.urlencode({"q": q, "fq": "type:adres", "rows": 10}))
    docs = (free.get("response") or {}).get("docs") or []
    matches = []
    for d in docs:
        m = re.match(r"POINT\(([-0-9.]+) ([-0-9.]+)\)", d.get("centroide_ll") or "")
        matches.append({
            "pdok_id": d.get("id"), "weergavenaam": d.get("weergavenaam"), "postcode": d.get("postcode"),
            "woonplaatsnaam": d.get("woonplaatsnaam"), "centroide_ll": d.get("centroide_ll"),
            "adresseerbaarobject_id": d.get("adresseerbaarobject_id"),
            "exact_match": exact_address_match(d, street, number, postcode),
            "_point": [float(m.group(1)), float(m.group(2))] if m else None,
        })
    panden = {}
    for m in matches:
        if not m["exact_match"] or not m["_point"]:
            continue
        lon, lat = m["_point"]
        bbox = ",".join(str(v) for v in (lon - BBOX_DEG, lat - BBOX_DEG, lon + BBOX_DEG, lat + BBOX_DEG))
        items = get(BAG_PAND_ITEMS + "?" + urllib.parse.urlencode({"f": "json", "limit": 20, "bbox": bbox}))
        for f in items.get("features") or []:
            if not f.get("geometry"):
                continue
            if not any(point_in_ring(r, lon, lat) for r in outer_rings(f["geometry"])):
                continue
            props = f.get("properties") or {}
            pid = str(props.get("identificatie") or "")
            if not pid:
                continue
            entry = panden.setdefault(pid, {"bag_pand_id": pid, "contains_address_point_of": [], "bag_properties": {
                k: props.get(k) for k in ("identificatie", "bouwjaar", "status", "gebruiksdoel", "aantal_verblijfsobjecten")}})
            entry["contains_address_point_of"].append(m["pdok_id"])
    for pid, entry in sorted(panden.items()):
        url = BAG3D_ITEM.format(pand_id=pid)
        body = get(url)
        co = ((body.get("feature") or {}).get("CityObjects") or {}).get("NL.IMBAG.Pand." + pid) or {}
        entry["threedbag"] = {
            "url": url, "fetched_at": fetched_at,
            "api_version": ((body.get("metadata") or {}).get("version")),
            "response_sha256": canonical_sha256(body),
            "attributes": co.get("attributes"),
        }
    for m in matches:
        m.pop("_point", None)
    body = {
        "snapshot_version": "bag_snapshot_v1",
        "document_id": document_id,
        "query": {"street": street, "number": str(number), "postcode": postcode, "city": city, "q": q},
        "fetched_at": fetched_at,
        "fetch_tool": TOOL_VERSION,
        "live_api_status": LIVE_API_STATUS,
        "requests": requests,
        "address_matches": matches,
        "panden": [panden[k] for k in sorted(panden)],
        "raw_responses": raw,
    }
    body["snapshot_id"] = "BAGSNAP-" + canonical_sha256(body)[:16]
    return body


def snapshot_errors(snap):
    errors = []
    body = {k: v for k, v in snap.items() if k != "snapshot_id"}
    if snap.get("snapshot_id") != "BAGSNAP-" + canonical_sha256(body)[:16]:
        errors.append(f"{snap.get('snapshot_id')}: snapshot_id past niet bij de inhoud (aangepast?)")
    for r in snap.get("requests", []):
        if r["response_sha256"] not in snap.get("raw_responses", {}):
            errors.append(f"{snap.get('snapshot_id')}: ruwe respons {r['response_sha256'][:12]} ontbreekt")
    for p in snap.get("panden", []):
        tb = p.get("threedbag") or {}
        if tb and tb.get("response_sha256") not in snap.get("raw_responses", {}):
            errors.append(f"{snap.get('snapshot_id')}: 3D BAG-respons voor {p['bag_pand_id']} ontbreekt")
    return errors


def load_snapshots(directory=SNAPSHOT_DIR):
    out = []
    for f in sorted(Path(directory).glob("*.json")):
        snap = json.loads(f.read_text(encoding="utf-8"))
        errs = snapshot_errors(snap)
        if errs:
            raise SnapshotError("; ".join(errs))
        out.append(snap)
    return out


def write_snapshot(snap, directory=SNAPSHOT_DIR):
    errs = snapshot_errors(snap)
    if errs:
        raise SnapshotError("; ".join(errs))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{snap['snapshot_id']}.json"
    if path.exists():
        return path  # zelfde inhoud (content-addressed); nooit overschrijven
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="BAG/3D BAG-snapshot ophalen en onveranderlijk vastleggen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--document", required=True)
    f.add_argument("--street", required=True)
    f.add_argument("--number", required=True)
    f.add_argument("--postcode")
    f.add_argument("--city")
    args = ap.parse_args(argv)
    try:
        snap = fetch_snapshot(args.document, args.street, args.number, args.postcode, args.city)
    except SnapshotError as e:
        print(f"FOUT: {e}\nIs api.pdok.nl / api.3dbag.nl bereikbaar vanuit deze omgeving?", file=sys.stderr)
        return 3
    path = write_snapshot(snap)
    print(f"{path}: {len(snap['address_matches'])} adrestreffers, {len(snap['panden'])} kandidaat-panden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
