"""Facade panorama PoC v1 — gevelbeelden op schaal uit open Amsterdamse panorama's + 3D BAG LoD2.2.

ANALYSE-SCRIPT (proof-of-concept). Schrijft niets in data/, stores of canonical data; alle uitvoer gaat naar --out.
Zie docs/facade_panorama_poc_v1.md.

Keten per BAG-pand:
  3D BAG LoD2.2 (ruwe respons uit een real_validation-package)
  -> verticale WallSurfaces, zonder tussenmuren (vlak tegen een wand van een ander kandidaat-pand)
  -> per wand: panorama's van Gemeente Amsterdam (Kernregistratie Panoramabeelden, CC BY 4.0) die er recht tegenover
     staan (API near=lon,lat)
  -> projectie van het 3D-wandvlak in het equirectangulaire panorama (noorden = beeldmidden; positie + hoogte uit API)
  -> gerectificeerd gevelbeeld op schaal (standaard 2 cm/px)
  -> occlusiecontrole: (a) geometrisch: ligt een ander LoD2.2-vlak tussen camera en wand; (b) vegetatie: aandeel
     groen (excess-green) in het gevelbeeld. Per wand wordt het panorama met de minste occlusie gekozen.

Beperkingen (bewust, PoC):
- Camerahoogte: ellipsoïdische hoogte uit de API min een BENADERDE geoïdehoogte (GEOID_N, ~43,3 m in Amsterdam),
  tenzij pyproj het NLGEO-raster kan laden (EPSG:4979 -> EPSG:7415).
- Pitch/roll worden niet toegepast: de Amsterdamse panorama's zijn genormaliseerd (horizon waterpas, noorden in het
  midden); gecontroleerd op Maldenhof 262-264.
- Geen kozijnherkenning in dit script (volgende stap; vision-model via ANTHROPIC_API_KEY, alleen als aanwijzing,
  meten blijft deterministisch).

    python scripts/facade_panorama_poc.py --group DOC-005-006 --scope EVEN_ONLY \\
        --package data/external/building_validation/real_validation_v3 --out /tmp/facade_poc
"""

import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer

PANO_API = "https://api.data.amsterdam.nl/panorama/panoramas/"
GEOID_N = 43.3          # benadering geoïdehoogte Amsterdam (m), alleen als NLGEO-raster niet beschikbaar is
RES = 0.02              # m per pixel in het gevelbeeld
MAX_DIST, MIN_DIST = 25.0, 4.0
MIN_FACING = 0.7        # cos(hoek) tussen wandnormaal en richting naar camera
MIN_WALL_M2 = 2.0
OCCL_SAMPLES = 12       # raster per as voor de geometrische occlusietest
USABLE_MAX_OCCLUSION = 0.25   # geometrie + vegetatie samen

T_WGS_RD = Transformer.from_crs("EPSG:4326", "EPSG:28992", always_xy=True)
T_RD_WGS = Transformer.from_crs("EPSG:28992", "EPSG:4326", always_xy=True)
try:
    _T_H = Transformer.from_crs("EPSG:4979", "EPSG:7415", always_xy=True)
    _z = _T_H.transform(4.9, 52.37, 45.0)[2]
    # zonder NLGEO-raster geeft pyproj de ellipsoïdische hoogte ongewijzigd terug: dan NIET als raster behandelen
    _ok = math.isfinite(_z) and abs(_z - 45.0) > 10
except Exception:
    _ok = False
HEIGHT_METHOD = "NLGEO_GRID" if _ok else f"APPROX_GEOID_N_{GEOID_N}"


# --- geometrie ------------------------------------------------------------------------------------------------------

def load_surfaces(raw):
    """-> [(type, ring Nx3 in RD/NAP)] voor LoD2.2."""
    f = raw["feature"]
    t = raw["metadata"]["transform"]
    V = np.array(f["vertices"], float) * np.array(t["scale"]) + np.array(t["translate"])
    out = []
    for co in f["CityObjects"].values():
        for g in co.get("geometry") or []:
            if g["type"] != "Solid" or str(g["lod"]) != "2.2":
                continue
            sem = g["semantics"]
            for si, face in enumerate(g["boundaries"][0]):
                st = sem["values"][0][si]
                if st is not None:
                    out.append((sem["surfaces"][st]["type"], V[face[0]]))
    return out


def normal_area(ring):
    n = np.zeros(3)
    for a, b in zip(ring, np.roll(ring, -1, axis=0)):
        n += np.cross(a, b)
    L = np.linalg.norm(n)
    return (n / L if L else n), L / 2


def triangles(ring):
    return [(ring[0], ring[i], ring[i + 1]) for i in range(1, len(ring) - 1)]


def is_party_wall(n, ring, others):
    c, d = ring.mean(0), float(np.dot(n, ring[0]))
    for n2, r2 in others:
        if np.dot(n, n2) < -0.95 and abs(float(np.dot(n, r2[0])) - d) < 0.35 and np.linalg.norm((r2.mean(0) - c)[:2]) < 8:
            return True
    return False


def ray_hits(orig, targets, tris, eps=1e-9):
    """Aandeel van de segmenten orig->target dat een driehoek raakt vóór het doel (Möller–Trumbore, gevectoriseerd)."""
    if not tris:
        return np.zeros(len(targets), bool)
    A = np.array([t[0] for t in tris]); B = np.array([t[1] for t in tris]); C = np.array([t[2] for t in tris])
    e1, e2 = B - A, C - A
    hit = np.zeros(len(targets), bool)
    for k, tgt in enumerate(targets):
        d = tgt - orig
        p = np.cross(d, e2)
        det = np.einsum("ij,ij->i", e1, p)
        ok = np.abs(det) > eps
        inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        s = orig - A
        u = np.einsum("ij,ij->i", s, p) * inv
        q = np.cross(s, e1)
        v = (q @ d) * inv
        tt = np.einsum("ij,ij->i", e2, q) * inv
        m = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (tt > 1e-3) & (tt < 0.98)
        hit[k] = bool(m.any())
    return hit


# --- panorama's -----------------------------------------------------------------------------------------------------

def http_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def panos_near(lon, lat, radius=45):
    q = urllib.parse.urlencode({"format": "json", "near": f"{lon},{lat}", "radius": radius, "page_size": 200})
    return http_json(PANO_API + "?" + q)["_embedded"]["panoramas"]


def cam_rd(p):
    lon, lat, h = p["geometry"]["coordinates"]
    if HEIGHT_METHOD == "NLGEO_GRID":
        x, y, z = _T_H.transform(lon, lat, h)
        return np.array([x, y, z])
    x, y = T_WGS_RD.transform(lon, lat)
    return np.array([x, y, h - GEOID_N])


def project(P, cam, W, H):
    """Equirectangulair, noorden in het beeldmidden (Amsterdamse panorama's)."""
    d = P - cam
    az = np.degrees(np.arctan2(d[..., 0], d[..., 1]))
    el = np.degrees(np.arctan2(d[..., 2], np.hypot(d[..., 0], d[..., 1])))
    return ((az / 360.0 + 0.5) % 1.0) * W, (0.5 - el / 180.0) * H


def fetch_image(p, cache, size="equirectangular_full"):
    fn = cache / f"{p['pano_id']}_{size}.jpg"
    if not fn.exists():
        urllib.request.urlretrieve(p["_links"][size]["href"], fn)
    return Image.open(fn).convert("RGB")


def wall_frame(n, ring):
    u = np.array([-n[1], n[0], 0.0]); u /= np.linalg.norm(u)
    U = (ring - ring[0]) @ u
    return u, U.min(), U.max(), ring[:, 2].min(), ring[:, 2].max()


def rectify(im, cam, n, ring, res=RES):
    u, u0, u1, v0, v1 = wall_frame(n, ring)
    W, H = im.size
    arr = np.asarray(im)
    nu, nv = int((u1 - u0) / res) + 1, int((v1 - v0) / res) + 1
    uu, vv = np.meshgrid(np.linspace(u0, u1, nu), np.linspace(v1, v0, nv))
    P = ring[0][None, None, :] + uu[..., None] * u + (vv[..., None] - ring[0][2]) * np.array([0, 0, 1.0])
    x, y = project(P, cam, W, H)
    img = Image.fromarray(arr[np.clip(y.astype(int), 0, H - 1), np.clip(x.astype(int), 0, W - 1)])
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(list(zip(((ring - ring[0]) @ u - u0) / res, (v1 - ring[:, 2]) / res)), fill=255)
    return img, mask, {"width_m": round(u1 - u0, 2), "height_m": round(v1 - v0, 2), "res_m_per_px": res}


def wall_samples(n, ring, k=OCCL_SAMPLES):
    u, u0, u1, v0, v1 = wall_frame(n, ring)
    pts = []
    poly = [((p - ring[0]) @ u, p[2]) for p in ring]
    for a in np.linspace(0.05, 0.95, k):
        for b in np.linspace(0.05, 0.95, k):
            uu, vv = u0 + a * (u1 - u0), v0 + b * (v1 - v0)
            if point_in_poly(uu, vv, poly):
                pts.append(ring[0] + (uu) * u + np.array([0, 0, vv - ring[0][2]]))
    return pts


def point_in_poly(x, y, poly):
    c, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            c = not c
        j = i
    return c


def vegetation_fraction(img, mask):
    a = np.asarray(img).astype(float) / 255.0
    m = np.asarray(mask) > 0
    if not m.any():
        return None
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    s = r + g + b + 1e-6
    exg = 2 * g / s - r / s - b / s
    return float(((exg > 0.12) & m).sum() / m.sum())


# --- hoofdlijn ------------------------------------------------------------------------------------------------------

def run(package, group, scope, out, max_candidates=4):
    package, out = Path(package), Path(out)
    (out / "cache").mkdir(parents=True, exist_ok=True)
    (out / "facades").mkdir(parents=True, exist_ok=True)
    pkg = json.loads((package / "candidates" / f"{group}.json").read_text(encoding="utf-8"))
    hyp = next(h for h in pkg["building_project_candidate"]["scope_hypotheses"] if h["hypothesis_id"] == scope)
    cand = {c["bag_pand_id"]: c for c in pkg["candidate_panden"] if (c.get("threedbag") or {}).get("raw_response_path")}
    surfaces = {pid: load_surfaces(json.loads((package / c["threedbag"]["raw_response_path"]).read_text(encoding="utf-8")))
                for pid, c in cand.items() if c["threedbag"].get("attributes")}
    all_tris = {pid: [t for typ, r in s for t in triangles(r)] for pid, s in surfaces.items()}
    walls_by_pand = {pid: [(normal_area(r), r) for typ, r in s if typ == "WallSurface"] for pid, s in surfaces.items()}
    rows = []
    for pid in hyp["bag_pand_ids"]:
        others = [(n, r) for q, ws in walls_by_pand.items() if q != pid for (n, a), r in ws]
        ext = [(i, n, a, r) for i, ((n, a), r) in enumerate(walls_by_pand[pid])
               if abs(n[2]) < 0.2 and a >= MIN_WALL_M2 and not is_party_wall(n, r, others)]
        c = np.vstack([r for *_, r in ext]).mean(0)
        lon, lat = T_RD_WGS.transform(c[0], c[1])
        panos = panos_near(lon, lat)
        tris_other = [t for q, ts in all_tris.items() for t in ts]  # alle vlakken, ook eigen aanbouw/dak
        for i, n, a, ring in ext:
            cands = []
            for p in panos:
                cam = cam_rd(p)
                v = cam - ring.mean(0)
                dist = float(np.hypot(v[0], v[1]))
                facing = float(np.dot(n[:2], v[:2]) / (np.linalg.norm(n[:2]) * dist + 1e-9))
                if facing >= MIN_FACING and MIN_DIST <= dist <= MAX_DIST:
                    cands.append((facing * 2 - abs(dist - 10) / 10, p, cam, dist, facing))
            row = {"bag_pand_id": pid, "wall_index": i, "wall_m2": round(a, 2),
                   "wall_azimuth_deg": round(math.degrees(math.atan2(n[0], n[1])) % 360),
                   "panorama": None, "usable": False, "reason": "NO_FACING_PANORAMA"}
            best = None
            own = [t for t in tris_other if not any(np.allclose(t[0], q) for q in ring)]
            samples = wall_samples(n, ring)
            for score, p, cam, dist, facing in sorted(cands, key=lambda x: -x[0])[:max_candidates]:
                geo = float(ray_hits(cam, samples, own).mean()) if samples else 1.0
                img = fetch_image(p, out / "cache", "equirectangular_medium")
                rimg, mask, meta = rectify(img, cam, n, ring, res=RES * 2)
                veg = vegetation_fraction(rimg, mask) or 0.0
                occl = min(1.0, geo + veg)
                if best is None or occl < best[0]:
                    best = (occl, p, cam, dist, facing, geo, veg)
            if best:
                occl, p, cam, dist, facing, geo, veg = best
                full = fetch_image(p, out / "cache")
                rimg, mask, meta = rectify(full, cam, n, ring)
                bg = Image.new("RGB", rimg.size, (40, 40, 40)); bg.paste(rimg, mask=mask)
                fn = out / "facades" / f"{pid}_w{i:02d}.jpg"
                bg.save(fn, quality=88)
                row.update({"panorama": {"pano_id": p["pano_id"], "timestamp": p["timestamp"], "distance_m": round(dist, 1),
                                         "facing": round(facing, 2), "url": p["_links"]["equirectangular_full"]["href"]},
                            "occlusion_geometric": round(geo, 2), "vegetation_fraction": round(veg, 2),
                            "occlusion_total": round(occl, 2), "usable": occl <= USABLE_MAX_OCCLUSION,
                            "reason": None if occl <= USABLE_MAX_OCCLUSION else ("VEGETATION" if veg >= geo else "GEOMETRY"),
                            "facade_image": str(fn.relative_to(out)), **meta})
            rows.append(row)
            print(f"{pid} w{i:02d} {a:6.1f} m2 az{row['wall_azimuth_deg']:3d} -> "
                  f"{'OK ' if row['usable'] else 'NEE'} {row['reason'] or ''} "
                  f"geo={row.get('occlusion_geometric')} veg={row.get('vegetation_fraction')}", flush=True)
    tot = sum(r["wall_m2"] for r in rows)
    ok = sum(r["wall_m2"] for r in rows if r["usable"])
    summary = {"poc_version": "facade_panorama_poc_v1", "group": group, "scope": scope,
               "source_package": str(package), "panorama_source": "Gemeente Amsterdam, Kernregistratie Panoramabeelden (CC BY 4.0)",
               "height_method": HEIGHT_METHOD, "res_m_per_px": RES, "usable_threshold": USABLE_MAX_OCCLUSION,
               "exterior_wall_m2": round(tot, 1), "usable_wall_m2": round(ok, 1),
               "usable_share": round(ok / tot, 3) if tot else None,
               "by_reason": {k: round(sum(r["wall_m2"] for r in rows if r["reason"] == k), 1)
                             for k in sorted({r["reason"] for r in rows if r["reason"]})},
               "walls": rows}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--package", default="data/external/building_validation/real_validation_v3")
    ap.add_argument("--group", default="DOC-005-006")
    ap.add_argument("--scope", default="EVEN_ONLY")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    s = run(a.package, a.group, a.scope, a.out)
    print(f"\nbuitenwand {s['exterior_wall_m2']} m2, bruikbaar {s['usable_wall_m2']} m2 ({(s['usable_share'] or 0) * 100:.0f}%), "
          f"hoogte: {s['height_method']}; niet bruikbaar per reden: {s['by_reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
