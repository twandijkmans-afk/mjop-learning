"""Facade coverage + element detection PoC v2 — Maldenhof 240-296 (scope EVEN_ONLY, 15 panden, 29 adressen).

ANALYSE-SCRIPT (proof-of-concept), vervolg op facade_panorama_poc.py (v1) en facade_element_detection_poc.py (v1).
Schrijft alleen naar --out; geen stores, schema's of canonical data. Zie reports/quantity/
facade_element_detection_poc_v2_maldenhof.md.

Wat v2 anders doet dan v1:
1. Dekking per GEVELPUNT i.p.v. per wand: elke buitenwand (LoD2.2, geen tussenmuur, >= 0,5 m²) wordt bemonsterd op een
   raster van SAMPLE m. Per punt en per panorama: ligt het in beeld (afstand, kijkhoek), raakt de zichtlijn een ander
   3D BAG-vlak (alle kandidaat-panden, ook de overkant), en is het punt groen (excess-green) in het panorama.
2. Multi-panorama: per wand kiest een greedy set-cover de panorama's (alle jaren/posities) die de meeste NOG NIET
   zichtbare punten toevoegen. Een punt telt één keer (unie van fysieke punten), nooit per panorama.
3. Detectie per gekozen (wand, panorama); het model geeft naast elementen ook afgedekte zones (hek, auto, begroeiing)
   terug. Elementen worden in wandcoördinaten (m) ontdubbeld: overlappende rechthoeken uit verschillende panorama's
   zijn hetzelfde fysieke element; het element uit het panorama met de beste kijkkwaliteit blijft over.
4. Metrics met eerlijke namen: bounding-box-oppervlakken van openingen, geen "kozijn-m²".

Stappen (elk schrijft JSON in --out en kan los opnieuw):
    python scripts/facade_coverage_poc_v2.py coverage --out /tmp/fc2 [--cache /tmp/facade_poc/cache]
    python scripts/facade_coverage_poc_v2.py detect   --out /tmp/fc2      # vereist ANTHROPIC_API_KEY
    python scripts/facade_coverage_poc_v2.py aggregate --out /tmp/fc2

Netwerk: api.data.amsterdam.nl, t1.data.amsterdam.nl, api.anthropic.com (alleen detect).
Bronvermelding: Gemeente Amsterdam, Kernregistratie Panoramabeelden (CC BY 4.0); 3D BAG (TU Delft, CC BY 4.0).
"""

import argparse
import base64
import glob
import io
import json
import math
import sys
import urllib.parse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import List, Literal

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facade_panorama_poc as fp  # noqa: E402

# Slanke Maldenhof-snapshot (uit real_validation_v3 van de integratiebranch; zie inputs/.../SOURCE.json)
PACKAGE = "reports/quantity/facade_poc_v2_run/inputs/maldenhof_DOC-005-006"


def resolve_package(path):
    """Het pakketpad uit een run (coverage.json) als het bestaat, anders de gecommitte snapshot (zelfde bestanden,
    sha256 in SOURCE.json). Zo blijft een run uit een andere checkout reproduceerbaar."""
    if path and Path(path, "candidates", f"{GROUP}.json").exists():
        return path
    return PACKAGE if Path(PACKAGE).exists() else str(Path(__file__).resolve().parents[1] / PACKAGE)
GROUP, SCOPE = "DOC-005-006", "EVEN_ONLY"
SAMPLE = 0.20           # m, rasterafstand gevelpunten
MIN_WALL_M2 = 0.5
MIN_D, MAX_D = 3.0, 30.0
MIN_FACING = 0.5        # cos(kijkhoek) >= 0,5 (<= 60 graden schuin)
EXG_T = 0.12            # excess-green drempel (zelfde als v1)
MIN_GAIN_SHARE = 0.03   # stop greedy als een extra panorama < 3% van de wand toevoegt
MIN_GAIN_PTS = 6
MAX_PANOS_PER_WALL = 4
PANO_RADIUS = 40
DET_RES = 0.01          # m/px voor detectie
MAX_EDGE = 2576
SNAP_PX = 6
MODEL = "claude-opus-5-5"
FRONT_AZ = 331          # voorgevel (MJOP: "Voorgevel locatie Noord"; 3D BAG-wandnormalen ~331°)
BANDS = [(0.0, 2.8, "BG"), (2.8, 5.6, "1e"), (5.6, 99.0, "kap")]   # hoogte boven maaiveld, indicatief


# --- geometrie ------------------------------------------------------------------------------------------------------

def load_package(package):
    package = Path(package)
    pkg = json.loads((package / "candidates" / f"{GROUP}.json").read_text(encoding="utf-8"))
    hyp = next(h for h in pkg["building_project_candidate"]["scope_hypotheses"] if h["hypothesis_id"] == SCOPE)
    cand = {c["bag_pand_id"]: c for c in pkg["candidate_panden"] if (c.get("threedbag") or {}).get("raw_response_path")}
    surfaces, maaiveld = {}, {}
    for pid, c in cand.items():
        if not c["threedbag"].get("attributes"):
            continue
        surfaces[pid] = fp.load_surfaces(json.loads((package / c["threedbag"]["raw_response_path"]).read_text(encoding="utf-8")))
        maaiveld[pid] = float(c["threedbag"]["attributes"].get("b3_h_maaiveld") or 0.0)
    return package, pkg, hyp, cand, surfaces, maaiveld


def zone_of(az, n, ring, pand_centroid):
    d = abs((az - FRONT_AZ + 180) % 360 - 180)
    if d <= 45:
        return "FRONT"
    if d >= 135:
        return "REAR"
    # zijwand: aan de voorkant van het pand (trappenhuisblok/terugsprong) of achterkant, of kopgevel
    fwd = np.array([math.sin(math.radians(FRONT_AZ)), math.cos(math.radians(FRONT_AZ))])
    off = float((ring.mean(0)[:2] - pand_centroid[:2]) @ fwd)
    return "SIDE_FRONT_PART" if off > 0 else "SIDE_REAR_PART"


def wall_samples(n, ring, step=SAMPLE):
    u, u0, u1, v0, v1 = fp.wall_frame(n, ring)
    poly = [((p - ring[0]) @ u, p[2]) for p in ring]
    us = np.arange(u0 + step / 2, u1, step)
    vs = np.arange(v0 + step / 2, v1, step)
    pts, uv = [], []
    for uu in us:
        for vv in vs:
            if fp.point_in_poly(uu, vv, poly):
                pts.append(ring[0] + uu * u + np.array([0, 0, vv - ring[0][2]]) + 0.05 * n)
                uv.append((uu - u0, v1 - vv))       # meters vanaf linksboven in het rectified beeld
    return np.array(pts), np.array(uv)


def segment_hits(orig, targets, A, e1, e2, eps=1e-9):
    """Per target: raakt het segment orig->target een driehoek (vóór het doel)? Gevectoriseerd over targets x tris."""
    if len(A) == 0 or len(targets) == 0:
        return np.zeros(len(targets), bool)
    D = targets - orig                                    # (T,3)
    p = np.cross(D[:, None, :], e2[None, :, :])           # (T,N,3)
    det = np.einsum("nk,tnk->tn", e1, p)
    ok = np.abs(det) > eps
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = orig - A                                          # (N,3)
    u = np.einsum("nk,tnk->tn", s, p) * inv
    q = np.cross(s, e1)                                   # (N,3)
    v = np.einsum("tk,nk->tn", D, q) * inv
    t = np.einsum("nk,nk->n", e2, q)[None, :] * inv
    m = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-3) & (t < 0.995)
    return m.any(1)


# --- panorama's -----------------------------------------------------------------------------------------------------

def panos_near_all(lon, lat, radius):
    q = urllib.parse.urlencode({"format": "json", "near": f"{lon},{lat}", "radius": radius, "page_size": 100})
    url, out = fp.PANO_API + "?" + q, []
    while url:
        j = fp.http_json(url)
        out += j["_embedded"]["panoramas"]
        url = ((j.get("_links") or {}).get("next") or {}).get("href")
    return out


def exg_at(arr, x, y, r=2):
    H, W = arr.shape[:2]
    xs = np.clip(x.astype(int), r, W - r - 1)
    ys = np.clip(y.astype(int), r, H - r - 1)
    acc = np.zeros(len(xs))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            px = arr[ys + dy, xs + dx].astype(float) / 255.0
            s = px.sum(1) + 1e-6
            acc += (2 * px[:, 1] - px[:, 0] - px[:, 2]) / s
    return acc / (2 * r + 1) ** 2


# --- extra occluders -----------------------------------------------------------------------------------------------

BAG_PAND_ITEMS = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"
BAG3D_ITEM = "https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.{}"
OCCLUDER_PAD_M = 30.0


def extra_occluders(surfaces, out):
    """BAG-panden 'in gebruik' rond het complex die niet in het evidence-package zitten (o.a. bergingen/blokken zonder
    verblijfsobject). Alleen gebruikt als OCCLUDER in de zichtlijntest, nooit als gevel van het project. Ruwe
    responses worden in <out>/occluders/ bewaard (reproduceerbaar)."""
    d = Path(out) / "occluders"; d.mkdir(parents=True, exist_ok=True)
    allv = np.vstack([r for s in surfaces.values() for t, r in s])
    x0, y0 = allv[:, :2].min(0) - OCCLUDER_PAD_M; x1, y1 = allv[:, :2].max(0) + OCCLUDER_PAD_M
    lon0, lat0 = fp.T_RD_WGS.transform(x0, y0); lon1, lat1 = fp.T_RD_WGS.transform(x1, y1)
    idx = d / "bag_panden_bbox.json"
    if not idx.exists():
        feats, url = [], BAG_PAND_ITEMS + "?" + urllib.parse.urlencode({"bbox": f"{lon0},{lat0},{lon1},{lat1}", "f": "json", "limit": 500})
        while url:
            j = fp.http_json(url)
            feats += j["features"]
            url = next((lk["href"] for lk in j.get("links", []) if lk.get("rel") == "next"), None)
        idx.write_text(json.dumps({"bbox_wgs84": [lon0, lat0, lon1, lat1], "features": feats}), encoding="utf-8")
    feats = json.loads(idx.read_text(encoding="utf-8"))["features"]
    out_s, info = {}, []
    for f in feats:
        pid = f["properties"]["identificatie"]
        if pid in surfaces or f["properties"].get("status") != "Pand in gebruik":
            continue
        fn = d / f"3dbag_{pid}.json"
        if not fn.exists():
            try:
                raw = fp.http_json(BAG3D_ITEM.format(pid))
            except Exception as ex:  # noqa: BLE001 — 404/502 voor een pand vastleggen, niet afbreken
                info.append({"bag_pand_id": pid, "error": str(ex)[:120]}); continue
            fn.write_text(json.dumps(raw), encoding="utf-8")
        try:
            out_s[pid] = fp.load_surfaces(json.loads(fn.read_text(encoding="utf-8")))
            info.append({"bag_pand_id": pid, "surfaces": len(out_s[pid])})
        except Exception as ex:  # noqa: BLE001
            info.append({"bag_pand_id": pid, "error": str(ex)[:120]})
    return out_s, info


# --- stap 1: dekking ------------------------------------------------------------------------------------------------

def run_coverage(package, out, cache):
    out = Path(out); cache = Path(cache); cache.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    package, pkg, hyp, cand, surfaces, maaiveld = load_package(package)
    walls_by_pand = {pid: [(fp.normal_area(r), r) for t, r in s if t == "WallSurface"] for pid, s in surfaces.items()}
    occ_surfaces, occ_info = extra_occluders(surfaces, out)
    print(f"extra occluders (BAG-panden buiten package): {len(occ_surfaces)}", flush=True)
    # alle driehoeken (alle kandidaat-panden, beide straatzijden, plus extra occluders) voor de zichtlijntest
    tri_list, tri_owner = [], []
    for pid, s in list(surfaces.items()) + list(occ_surfaces.items()):
        for si, (t, r) in enumerate(s):
            for tr in fp.triangles(r):
                tri_list.append(tr); tri_owner.append((pid, si))
    TA = np.array([t[0] for t in tri_list]); TB = np.array([t[1] for t in tri_list]); TC = np.array([t[2] for t in tri_list])
    Te1, Te2 = TB - TA, TC - TA
    tmin = np.minimum(np.minimum(TA, TB), TC); tmax = np.maximum(np.maximum(TA, TB), TC)

    walls = []
    for pid in hyp["bag_pand_ids"]:
        others = [(n, r) for q, ws in walls_by_pand.items() if q != pid for (n, a), r in ws]
        allv = np.vstack([r for t, r in surfaces[pid]])
        pc = allv.mean(0)
        wall_ids = [si for si, (t, r) in enumerate(surfaces[pid]) if t == "WallSurface"]
        for wi, ((n, a), r) in enumerate(walls_by_pand[pid]):
            if abs(n[2]) >= 0.2 or a < MIN_WALL_M2 or fp.is_party_wall(n, r, others):
                continue
            az = math.degrees(math.atan2(n[0], n[1])) % 360
            pts, uv = wall_samples(n, r)
            if len(pts) == 0:
                continue
            walls.append({"bag_pand_id": pid, "wall_index": wi, "surface_index": wall_ids[wi], "n": n, "ring": r,
                          "area": a, "az": az, "zone": zone_of(az, n, r, pc), "pts": pts, "uv": uv,
                          "hag": pts[:, 2] - maaiveld[pid], "vis": {}})
    print(f"{len(walls)} buitenwanden, {sum(len(w['pts']) for w in walls)} gevelpunten", flush=True)

    # panorama's rond elk pand (alle jaren), ontdubbeld op pano_id
    panos = {}
    for pid in hyp["bag_pand_ids"]:
        c = np.vstack([w["ring"] for w in walls if w["bag_pand_id"] == pid]).mean(0)
        lon, lat = fp.T_RD_WGS.transform(c[0], c[1])
        for p in panos_near_all(lon, lat, PANO_RADIUS):
            panos.setdefault(p["pano_id"], p)
    # panorama's zonder geldige ellipsoïdische hoogte (API geeft 0,0; o.a. opnames 2024/2025) zijn niet te projecteren
    no_height = sorted(k for k, p in panos.items() if not (p["geometry"]["coordinates"][2] or 0) > 1.0)
    for k in no_height:
        panos.pop(k)
    print(f"{len(panos)} panorama's (uitgesloten zonder hoogte: {len(no_height)})", flush=True)

    for k, (pano_id, p) in enumerate(sorted(panos.items())):
        cam = fp.cam_rd(p)
        todo = []
        for w in walls:
            v = cam - w["ring"].mean(0)
            dist = float(np.hypot(v[0], v[1]))
            facing = float(np.dot(w["n"][:2], v[:2]) / (np.linalg.norm(w["n"][:2]) * dist + 1e-9))
            if MIN_D <= dist <= MAX_D and facing >= MIN_FACING:
                todo.append((w, dist, facing))
        if not todo:
            continue
        img = fp.fetch_image(p, cache, "equirectangular_medium")
        arr = np.asarray(img); H, W = arr.shape[:2]
        for w, dist, facing in todo:
            pts = w["pts"]
            lo = np.minimum(pts.min(0), cam) - 0.5; hi = np.maximum(pts.max(0), cam) + 0.5
            sel = np.all((tmax >= lo) & (tmin <= hi), axis=1)
            own = [i for i in np.nonzero(sel)[0] if tri_owner[i] != (w["bag_pand_id"], w["surface_index"])]
            own = np.array(own, int)
            geo_block = segment_hits(cam, pts, TA[own], Te1[own], Te2[own]) if len(own) else np.zeros(len(pts), bool)
            x, y = fp.project(pts, cam, W, H)
            veg = exg_at(arr, x, y) > EXG_T
            quality = facing - abs(dist - 10) / 40.0
            w["vis"][pano_id] = {"geo_block": geo_block, "veg": veg, "dist": dist, "facing": facing, "quality": quality,
                                 "timestamp": p["timestamp"], "url": p["_links"]["equirectangular_full"]["href"],
                                 "geometry": p["geometry"]}
        if k % 20 == 0:
            print(f"  panorama {k + 1}/{len(panos)}", flush=True)

    # greedy set cover per wand
    rows = []
    for w in walls:
        N = len(w["pts"])
        clear = {pid: (~v["geo_block"]) & (~v["veg"]) for pid, v in w["vis"].items()}
        covered = np.zeros(N, bool)
        chosen = []
        while len(chosen) < MAX_PANOS_PER_WALL:
            best = None
            for pid, c in clear.items():
                if pid in chosen:
                    continue
                gain = int((c & ~covered).sum())
                key = (gain, w["vis"][pid]["quality"])
                if best is None or key > best[0]:
                    best = (key, pid)
            if best is None or best[0][0] < max(MIN_GAIN_PTS, MIN_GAIN_SHARE * N):
                break
            chosen.append(best[1]); covered |= clear[best[1]]
        # reden per punt (alleen voor niet-gedekte punten)
        reason = np.full(N, "VISIBLE", dtype=object)
        if not w["vis"]:
            reason[:] = "NO_PANORAMA_IN_RANGE"
        else:
            any_geo_clear = np.zeros(N, bool)
            for v in w["vis"].values():
                any_geo_clear |= ~v["geo_block"]
            reason[~covered & ~any_geo_clear] = "GEOMETRY"
            reason[~covered & any_geo_clear] = "VEGETATION_EXG"
        owner = np.full(N, None, dtype=object)
        for i in range(N):
            if covered[i]:
                owner[i] = max((pid for pid in chosen if clear[pid][i]), key=lambda q: w["vis"][q]["quality"])
        rows.append({"bag_pand_id": w["bag_pand_id"], "wall_index": w["wall_index"], "wall_m2": round(w["area"], 2),
                     "azimuth_deg": round(w["az"]), "zone": w["zone"], "n_points": N,
                     "point_m2": round(w["area"] / N, 5),
                     "candidate_panoramas": len(w["vis"]),
                     "chosen_panoramas": [{"pano_id": q, "timestamp": w["vis"][q]["timestamp"],
                                           "distance_m": round(w["vis"][q]["dist"], 1),
                                           "facing": round(w["vis"][q]["facing"], 2),
                                           "quality": round(w["vis"][q]["quality"], 3),
                                           "url": w["vis"][q]["url"], "geometry": w["vis"][q]["geometry"],
                                           "clear_points": int(clear[q].sum()),
                                           "clear_mask": "".join("1" if b else "0" for b in clear[q])} for q in chosen],
                     "point_reason": reason.tolist(), "point_owner": owner.tolist(),
                     "point_uv_m": np.round(w["uv"], 3).tolist(), "point_hag_m": np.round(w["hag"], 2).tolist(),
                     "v1_single_best_pano_points": None})
    cov = {"poc_version": "facade_coverage_poc_v2", "package": str(package), "group": GROUP, "scope": SCOPE,
           "sample_m": SAMPLE, "height_method": fp.HEIGHT_METHOD, "panoramas_considered": len(panos),
           "panoramas_excluded_no_height": no_height, "extra_occluders": occ_info,
           "params": {"MIN_D": MIN_D, "MAX_D": MAX_D, "MIN_FACING": MIN_FACING, "EXG_T": EXG_T,
                      "MIN_GAIN_SHARE": MIN_GAIN_SHARE, "MAX_PANOS_PER_WALL": MAX_PANOS_PER_WALL},
           "walls": rows}
    (out / "coverage.json").write_text(json.dumps(cov, ensure_ascii=False), encoding="utf-8")
    vis = sum(r["point_m2"] * sum(1 for x in r["point_reason"] if x == "VISIBLE") for r in rows)
    tot = sum(r["wall_m2"] for r in rows)
    print(f"buitenwand {tot:.1f} m2, zichtbaar (geometrie+groen, unie) {vis:.1f} m2", flush=True)
    return cov


# --- stap 2: detectie -----------------------------------------------------------------------------------------------

def _models():
    from pydantic import BaseModel, Field

    class Element(BaseModel):
        type: Literal["window", "door", "garage_door", "balcony", "dormer", "facade_panel", "other"]
        x0: int = Field(description="linker rand, pixels vanaf links")
        y0: int = Field(description="bovenrand, pixels vanaf boven")
        x1: int = Field(description="rechter rand")
        y1: int = Field(description="onderrand")
        frame_material: Literal["wood", "plastic", "aluminium", "steel", "unknown"]
        partially_hidden: bool = Field(description="deels verborgen door begroeiing, object of beeldrand")
        note: str = Field(description="korte toelichting, max 15 woorden")

    class Occluder(BaseModel):
        kind: Literal["vegetation", "fence_or_wall", "vehicle", "other_building_part", "object", "image_artifact"]
        x0: int
        y0: int
        x1: int
        y1: int

    class FacadeElements(BaseModel):
        image_usable: bool = Field(description="false als het beeld geen bruikbare gevel toont")
        elements: List[Element]
        occluded_regions: List[Occluder] = Field(description="zones van het wandvlak die de gevel NIET tonen")
        remarks: str

    return FacadeElements


PROMPT = """Dit is een gerectificeerd, recht-van-voren gevelbeeld van één wandvlak van een Nederlands woongebouw,
automatisch uitgesneden uit een 360°-straatpanorama. Schaal: 1 pixel = {res_cm} cm; beeld {w}×{h} px
({wm} m breed, {hm} m hoog). Grijze gebieden vallen buiten het wandvlak.

1. Markeer elk buitenkozijn (raam), elke buitendeur, garage-/bergingsdeur, balkon, dakkapel en houten of plaatvormige
   gevelbekleding (facade_panel) die IN dit wandvlak zit. Geef per element de omhullende rechthoek van het
   BUITENKOZIJN (buitenkant van het kozijnhout, dus inclusief kozijn, niet alleen het glas) in pixelcoördinaten van dit
   beeld. Een raam met meerdere vakken in één kozijn is één element. Markeer niets wat je niet duidelijk ziet; zet
   partially_hidden op true als een deel verborgen is.
2. Geef in occluded_regions de rechthoeken waar het wandvlak NIET zichtbaar is omdat er iets vóór staat (struik/boom,
   schutting/muurtje, auto, ander bouwdeel zoals een dak of luifel, object) of het beeld onbruikbaar is.
Als het beeld geen bruikbare gevel toont, zet image_usable op false en geef geen elementen."""


def rectify_pair(wall_row, pano, cache, geom, res=DET_RES):
    p = {"pano_id": pano["pano_id"], "_links": {"equirectangular_full": {"href": pano["url"]}}, "geometry": pano["geometry"]}
    cam = fp.cam_rd(p)
    img = fp.fetch_image(p, cache)
    n, ring = geom
    rimg, mask, meta = fp.rectify(img, cam, n, ring, res=res)
    bg = Image.new("RGB", rimg.size, (128, 128, 128)); bg.paste(rimg, mask=mask)
    return bg, meta


def snap_edges(gray, x0, y0, x1, y1):
    H, W = gray.shape
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1]))
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))

    def best_col(x, ya, yb):
        cands = range(max(0, x - SNAP_PX), min(W - 1, x + SNAP_PX) + 1)
        return max(cands, key=lambda c: gx[max(0, ya):max(ya + 1, yb), c].mean()) if yb > ya else x

    def best_row(y, xa, xb):
        cands = range(max(0, y - SNAP_PX), min(H - 1, y + SNAP_PX) + 1)
        return max(cands, key=lambda r: gy[r, max(0, xa):max(xa + 1, xb)].mean()) if xb > xa else y
    nx0, nx1 = best_col(x0, y0, y1), best_col(x1, y0, y1)
    ny0, ny1 = best_row(y0, x0, x1), best_row(y1, x0, x1)
    if nx1 - nx0 < 0.5 * (x1 - x0) or ny1 - ny0 < 0.5 * (y1 - y0):
        return x0, y0, x1, y1, False
    return nx0, ny0, nx1, ny1, True


def wall_geometry(package, cand, pid, wall_index):
    raw = json.loads((Path(package) / cand[pid]["threedbag"]["raw_response_path"]).read_text(encoding="utf-8"))
    ring = [r for t, r in fp.load_surfaces(raw) if t == "WallSurface"][wall_index]
    n, _ = fp.normal_area(ring)
    return n, ring


def run_detect(out, cache, limit=None, workers=6):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import anthropic
    FacadeElements = _models()
    out = Path(out); cache = Path(cache)
    cov = json.loads((out / "coverage.json").read_text(encoding="utf-8"))
    package, pkg, hyp, cand, *_ = load_package(resolve_package(cov["package"]))
    det_path = out / "detections_v2.json"
    done = json.loads(det_path.read_text(encoding="utf-8")) if det_path.exists() else {"pairs": {}, "usage": {"input_tokens": 0, "output_tokens": 0}}
    (out / "annotated").mkdir(exist_ok=True)
    client = anthropic.Anthropic()
    lock = threading.Lock()
    pairs = [(w, p) for w in cov["walls"] for p in w["chosen_panoramas"]]
    pairs.sort(key=lambda wp: -wp[0]["wall_m2"])
    todo = [(w, p) for w, p in pairs if f"{w['bag_pand_id']}_w{w['wall_index']:02d}_{p['pano_id']}" not in done["pairs"]]
    if limit is not None:
        todo = todo[:limit]

    def one(wp):
        w, p = wp
        key = f"{w['bag_pand_id']}_w{w['wall_index']:02d}_{p['pano_id']}"
        geom = wall_geometry(package, cand, w["bag_pand_id"], w["wall_index"])
        img, meta = rectify_pair(w, p, cache, geom)
        if max(img.size) > MAX_EDGE:
            with lock:
                done["pairs"][key] = {"skipped": "IMAGE_TOO_LARGE"}
            return
        try:
            parsed, msg = ask(client, FacadeElements, img, meta)
        except anthropic.APIStatusError as ex:
            print(f"{key}: API-fout {ex.status_code}", flush=True)
            return
        except Exception as ex:  # noqa: BLE001 — bv. afgekapte/ongeldige structured output: vastleggen, niet afbreken
            with lock:
                done["pairs"][key] = {"bag_pand_id": w["bag_pand_id"], "wall_index": w["wall_index"], "pano_id": p["pano_id"],
                                      "error": f"{type(ex).__name__}: {str(ex)[:200]}", "image_usable_model": False,
                                      "elements": [], "occluded_regions": []}
            print(f"{key}: FOUT {type(ex).__name__}", flush=True)
            return
        gray = np.asarray(img.convert("L"), float)
        els, occ = [], []
        ann = img.copy(); d = ImageDraw.Draw(ann)
        if parsed and parsed.image_usable:
            for e in parsed.elements:
                x0, y0, x1, y1, snapped = snap_edges(gray, e.x0, e.y0, e.x1, e.y1)
                els.append({**e.model_dump(), "refined_px": [x0, y0, x1, y1], "snapped": snapped})
                d.rectangle([x0, y0, x1, y1], outline=(255, 0, 0) if e.type == "window" else (0, 120, 255), width=3)
        if parsed:
            for o in parsed.occluded_regions:
                occ.append(o.model_dump())
                d.rectangle([o.x0, o.y0, o.x1, o.y1], outline=(255, 200, 0), width=2)
        ann.save(out / "annotated" / f"{key}.jpg", quality=85)
        img.save(out / "annotated" / f"{key}_raw.jpg", quality=90)
        with lock:
            done["usage"]["input_tokens"] += msg.usage.input_tokens
            done["usage"]["output_tokens"] += msg.usage.output_tokens
            done["pairs"][key] = {"bag_pand_id": w["bag_pand_id"], "wall_index": w["wall_index"], "pano_id": p["pano_id"],
                                  "image_usable_model": bool(parsed and parsed.image_usable), "refused": parsed is None,
                                  "remarks": parsed.remarks if parsed else None, "model_served": msg.model,
                                  "elements": els, "occluded_regions": occ, "res_m_per_px": DET_RES, **meta}
            det_path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        print(f"{key}: {len(els)} el, {len(occ)} occl", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))
    det_path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    return done


def ask(client, FacadeElements, img, meta, extra_text=None, extra_image=None):
    import anthropic  # noqa: F401
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=92)
    content = []
    if extra_image is not None:
        b2 = io.BytesIO(); extra_image.save(b2, format="JPEG", quality=92)
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.standard_b64encode(b2.getvalue()).decode("ascii")}})
    content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                "data": base64.standard_b64encode(buf.getvalue()).decode("ascii")}})
    w, h = img.size
    text = PROMPT.format(res_cm=round(DET_RES * 100, 1), w=w, h=h, wm=meta["width_m"], hm=meta["height_m"])
    if extra_text:
        text = extra_text + "\n\n" + text
    content.append({"type": "text", "text": text})
    msg = client.beta.messages.parse(
        model=MODEL, max_tokens=16000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "high"}, messages=[{"role": "user", "content": content}], output_format=FacadeElements)
    if msg.stop_reason == "refusal":
        return None, msg
    return msg.parsed_output, msg


# --- stap 3: aggregatie ---------------------------------------------------------------------------------------------

OPENING_TYPES = {"window": "window_opening_area_m2", "door": "door_opening_area_m2",
                 "garage_door": "garage_door_area_m2", "dormer": "dormer_bbox_area_m2"}


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def same_element(a, b):
    """Zelfde fysieke element: overlappende rechthoeken of middelpunten < 0,6 m bij vergelijkbare maat (registratie-
    afwijking tussen panorama's is enkele decimeters)."""
    if iou(a["box_m"], b["box_m"]) > 0.3:
        return True
    (ax, ay), (bx, by) = centre(a["box_m"]), centre(b["box_m"])
    wa, wb = a["box_m"][2] - a["box_m"][0], b["box_m"][2] - b["box_m"][0]
    return math.hypot(ax - bx, ay - by) < 0.6 and 0.6 < (wa / wb if wb else 0) < 1.67


def band_of(hag):
    for lo, hi, name in BANDS:
        if lo <= hag < hi:
            return name
    return BANDS[0][2] if hag < 0 else BANDS[-1][2]


def empty_q():
    return {"window_count": 0, "door_count": 0, "garage_door_count": 0, "dormer_count": 0, "balcony_count": 0,
            "window_opening_area_m2": Decimal(0), "door_opening_area_m2": Decimal(0), "garage_door_area_m2": Decimal(0),
            "dormer_bbox_area_m2": Decimal(0), "total_opening_bbox_area_m2": Decimal(0),
            "facade_panel_area_m2": Decimal(0), "window_sill_m1": Decimal(0), "elements_partially_hidden": 0}


def add_el(q, e):
    a, wdt = Decimal(e["area_m2"]), Decimal(e["width_m"])
    q["elements_partially_hidden"] += int(e["partially_hidden"])
    if e["type"] in OPENING_TYPES:
        q[f"{e['type']}_count"] += 1
        q[OPENING_TYPES[e["type"]]] += a
        q["total_opening_bbox_area_m2"] += a
    if e["type"] == "window":
        q["window_sill_m1"] += wdt
    if e["type"] == "balcony":
        q["balcony_count"] += 1
    if e["type"] == "facade_panel":
        q["facade_panel_area_m2"] += a


def fmt(q):
    return {k: (str(v.quantize(Decimal("0.01"))) if isinstance(v, Decimal) else v) for k, v in q.items()}


GABLE_MIN_M2 = 13.0   # zijwanden >= 13 m² komen alleen voor bij de twee eindpanden (kopgevels)


def final_zone(w):
    return "GABLE" if w["zone"].startswith("SIDE") and w["wall_m2"] >= GABLE_MIN_M2 else w["zone"]


def run_aggregate(out):
    out = Path(out)
    cov = json.loads((out / "coverage.json").read_text(encoding="utf-8"))
    det = json.loads((out / "detections_v2.json").read_text(encoding="utf-8"))
    package, pkg, hyp, cand, surfaces, maaiveld = load_package(resolve_package(cov["package"]))
    pand_rows = {p["bag_pand_id"]: p for p in hyp["panden"]}
    wall_out, pand_q, pand_cov = [], defaultdict(lambda: defaultdict(empty_q)), defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    tot_attempted = tot_usable = tot_with_el = tot_unusable = Decimal(0)
    for w in cov["walls"]:
        pid, zone = w["bag_pand_id"], final_zone(w)
        pm2 = w["point_m2"]
        uv = np.array(w["point_uv_m"]); hag = np.array(w["point_hag_m"])
        reason = np.array(w["point_reason"], dtype=object)
        owner = np.array(w["point_owner"], dtype=object)
        # model: onbruikbaar beeld / afgedekte zones -> punten van dat panorama vervallen, tenzij een ander gekozen
        # panorama ze wél toont
        pairs = {p["pano_id"]: det["pairs"].get(f"{pid}_w{w['wall_index']:02d}_{p['pano_id']}") for p in w["chosen_panoramas"]}
        chosen_sorted = sorted(w["chosen_panoramas"], key=lambda p: -p["quality"])
        # een punt is BEVESTIGD zichtbaar als het beste gekozen panorama dat het (geometrie + groen) vrij ziet het
        # ook volgens het model toont (niet in een afgedekte zone, beeld bruikbaar); anders het volgende panorama
        confirmed = np.zeros(len(uv), bool)
        for p in chosen_sorted:
            r = pairs[p["pano_id"]]
            if not r or r.get("skipped") or not r.get("image_usable_model"):
                continue
            clear = np.array([c == "1" for c in p["clear_mask"]])
            occl = np.zeros(len(uv), bool)
            for o in r["occluded_regions"]:
                x0, y0, x1, y1 = (np.array([o["x0"], o["y0"], o["x1"], o["y1"]]) * DET_RES)
                occl |= (uv[:, 0] >= x0) & (uv[:, 0] <= x1) & (uv[:, 1] >= y0) & (uv[:, 1] <= y1)
            confirmed |= clear & ~occl
        bands = np.array([band_of(h) for h in hag], dtype=object)
        final_reason = reason.copy()
        final_reason[(reason == "VISIBLE") & ~confirmed] = "MODEL_OCCLUDED_OR_UNUSABLE"
        # elementen in wandcoördinaten, ontdubbelen over panorama's
        cands = []
        for p in chosen_sorted:
            r = pairs[p["pano_id"]]
            if not r or r.get("skipped") or not r.get("image_usable_model"):
                continue
            for e in r["elements"]:
                x0, y0, x1, y1 = [v * DET_RES for v in e["refined_px"]]
                cands.append({**e, "box_m": [x0, y0, x1, y1], "pano_id": p["pano_id"], "quality": p["quality"]})
        kept = []
        for c in sorted(cands, key=lambda c: -c["quality"]):
            dup = next((k for k in kept if same_element(k, c)), None)
            if dup is not None:
                if c["pano_id"] != dup["pano_id"]:
                    cx, cy = centre(c["box_m"]); kx, ky = centre(dup["box_m"])
                    dup.setdefault("also_seen_in", []).append({"pano_id": c["pano_id"], "offset_m": [round(cx - kx, 3), round(cy - ky, 3)]})
                continue
            kept.append(c)
        for k in kept:
            x0, y0, x1, y1 = k["box_m"]
            wm, hm = Decimal(str(round(x1 - x0, 3))), Decimal(str(round(y1 - y0, 3)))
            k["width_m"], k["height_m"] = str(wm), str(hm)
            k["area_m2"] = str((wm * hm).quantize(Decimal("0.01")))
            cy = (y0 + y1) / 2
            # hoogte boven maaiveld van het elementmidden via het dichtstbijzijnde gevelpunt
            j = int(np.argmin((uv[:, 1] - cy) ** 2 + (uv[:, 0] - (x0 + x1) / 2) ** 2)) if len(uv) else 0
            k["band"] = band_of(float(hag[j])) if len(uv) else None
            add_el(pand_q[pid][zone], k)
            add_el(pand_q[pid][f"{zone}|{k['band']}"], k)
        # dekking
        for rr in sorted(set(final_reason.tolist())):
            m2 = float((final_reason == rr).sum()) * pm2
            pand_cov[pid][zone][rr] += m2
        for bname in sorted({band_of(h) for h in hag}):
            bm = np.array([band_of(h) == bname for h in hag])
            pand_cov[pid][f"{zone}|{bname}"]["TOTAL"] += float(bm.sum()) * pm2
            pand_cov[pid][f"{zone}|{bname}"]["CONFIRMED_VISIBLE"] += float((bm & (final_reason == "VISIBLE")).sum()) * pm2
        area = Decimal(str(w["wall_m2"]))
        usable = any(r and not r.get("skipped") and r.get("image_usable_model") for r in pairs.values())
        tot_attempted += area if pairs else Decimal(0)
        tot_usable += area if usable else Decimal(0)
        tot_unusable += area if (pairs and not usable) else Decimal(0)
        tot_with_el += area if kept else Decimal(0)
        wall_out.append({"bag_pand_id": pid, "wall_index": w["wall_index"], "zone": zone, "wall_m2": w["wall_m2"],
                         "azimuth_deg": w["azimuth_deg"],
                         "panoramas_used": [p["pano_id"] for p in chosen_sorted if pairs.get(p["pano_id"])],
                         "points": len(uv),
                         "m2_by_reason": {rr: round(float((final_reason == rr).sum()) * pm2, 2) for rr in sorted(set(final_reason.tolist()))},
                         "m2_by_band_reason": {b: {rr: round(float(((final_reason == rr) & (bands == b)).sum()) * pm2, 2)
                                                   for rr in sorted(set(final_reason[bands == b].tolist()))}
                                               for b in sorted(set(bands.tolist()))},
                         "elements": [{k2: v for k2, v in k.items() if k2 in ("type", "box_m", "width_m", "height_m", "area_m2", "band", "pano_id", "also_seen_in", "partially_hidden", "frame_material")} for k in kept]})
    result = {"poc_version": "facade_element_detection_poc_v2", "model": MODEL, "det_res_m_per_px": DET_RES,
              "coverage_sample_m": cov["sample_m"], "panoramas_considered": cov["panoramas_considered"],
              "usage": det["usage"], "wall_m2": {"wall_m2_total_exterior": str(sum(Decimal(str(w["wall_m2"])) for w in cov["walls"])),
                                                 "wall_m2_attempted": str(tot_attempted), "wall_m2_model_usable": str(tot_usable),
                                                 "wall_m2_model_unusable": str(tot_unusable),
                                                 "wall_m2_with_detected_elements": str(tot_with_el)},
              "per_pand_quantities": {pid: {z: fmt(q) for z, q in zs.items()} for pid, zs in pand_q.items()},
              "per_pand_coverage_m2": {pid: {z: {k: round(v, 2) for k, v in d.items()} for z, d in zs.items()} for pid, zs in pand_cov.items()},
              "walls": wall_out,
              "pand_addresses": {pid: pand_rows[pid]["numbers_in_scope"] for pid in pand_rows},
              "label": "ESTIMATED_FROM_PANORAMA — bounding-box-oppervlakken van openingen, geen kozijn-/schilder-m²"}
    (out / "aggregate_v2.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["coverage", "detect", "aggregate"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache")
    ap.add_argument("--package", default=PACKAGE)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    cache = a.cache or str(Path(a.out) / "cache")
    if a.step == "coverage":
        run_coverage(a.package, a.out, cache)
    elif a.step == "detect":
        r = run_detect(a.out, cache, a.limit)
        print(json.dumps(r["usage"]))
    else:
        r = run_aggregate(a.out)
        print(json.dumps(r["wall_m2"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
