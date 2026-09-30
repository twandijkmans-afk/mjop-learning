"""Facade element detection PoC v1 — kozijnen/deuren/balkons in gerectificeerde gevelbeelden.

ANALYSE-SCRIPT (proof-of-concept), vervolg op scripts/facade_panorama_poc.py. Schrijft alleen naar --out.

Rolverdeling (CLAUDE.md: de LLM rekent niet):
- Een vision-model (Claude) WIJST AAN: per element type + omhullende rechthoek in pixels van het gevelbeeld.
- Deterministische code MEET: randen verfijnen op de sterkste beeldgradiënt, pixels -> meters via de bekende schaal,
  en sommeert tot hoeveelheden (aantallen, kozijn-m², raamdorpel-m¹). Alle waarden zijn schattingen
  ("ESTIMATED, uit panorama") met het gevelbeeld als bewijs; niets wordt in canonical data geschreven.

Vereist: ANTHROPIC_API_KEY in de omgeving; netwerk naar api.anthropic.com, api/t1.data.amsterdam.nl.

    python scripts/facade_element_detection_poc.py --poc-out /tmp/facade_poc --out /tmp/facade_det [--limit 3]
"""

import argparse
import base64
import io
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import List, Literal

import anthropic
import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facade_panorama_poc as fp  # noqa: E402

MODEL = "claude-opus-5-5"
RES = 0.01            # m/px voor de detectie (bron ~8 mm/px op 10 m)
MAX_EDGE = 2576       # grootste beeldzijde die 1:1 in pixels wordt verwerkt
SNAP_PX = 6           # zoekbereik randverfijning

ElementType = Literal["window", "door", "garage_door", "balcony", "dormer", "facade_panel", "other"]


class Element(BaseModel):
    type: ElementType
    x0: int = Field(description="linker rand, pixels vanaf links")
    y0: int = Field(description="bovenrand, pixels vanaf boven")
    x1: int = Field(description="rechter rand")
    y1: int = Field(description="onderrand")
    frame_material: Literal["wood", "plastic", "aluminium", "steel", "unknown"]
    partially_hidden: bool = Field(description="deels verborgen door begroeiing, object of beeldrand")
    note: str = Field(description="korte toelichting, max 15 woorden")


class FacadeElements(BaseModel):
    image_usable: bool = Field(description="false als het beeld geen bruikbare gevel toont")
    elements: List[Element]
    remarks: str


PROMPT = """Dit is een gerectificeerd, recht-van-voren gevelbeeld van één wandvlak van een Nederlands woongebouw,
automatisch uitgesneden uit een 360°-straatpanorama. Schaal: 1 pixel = {res_cm} cm; beeld {w}×{h} px
({wm} m breed, {hm} m hoog). Grijze gebieden vallen buiten het wandvlak.

Markeer elk buitenkozijn (raam), elke buitendeur, garagedeur, balkon, dakkapel en houten gevelbekleding (facade_panel)
die IN dit wandvlak zit. Geef per element de omhullende rechthoek van het BUITENKOZIJN (buitenkant van het kozijnhout,
dus inclusief kozijn, niet alleen het glas) in pixelcoördinaten van dit beeld. Een raam met meerdere vakken in één
kozijn is één element. Markeer niets wat je niet duidelijk ziet; zet partially_hidden op true als een deel verborgen is.
Als het beeld geen bruikbare gevel toont (bomen, dak, lucht), zet image_usable op false en geef geen elementen."""


def encode(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def ask_model(client, img, meta):
    w, h = img.size
    msg = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high"},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": encode(img)}},
            {"type": "text", "text": PROMPT.format(res_cm=round(RES * 100, 1), w=w, h=h,
                                                    wm=meta["width_m"], hm=meta["height_m"])},
        ]}],
        output_format=FacadeElements,
    )
    if msg.stop_reason == "refusal":
        return None, msg
    return msg.parsed_output, msg


def snap_edges(gray, e):
    """Verfijn elke rand naar de sterkste gemiddelde gradiënt binnen ±SNAP_PX (deterministisch)."""
    H, W = gray.shape
    gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1]))
    gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
    x0, y0, x1, y1 = e.x0, e.y0, e.x1, e.y1

    def best_col(x, ya, yb):
        cands = range(max(0, x - SNAP_PX), min(W - 1, x + SNAP_PX) + 1)
        return max(cands, key=lambda c: gx[max(0, ya):max(ya + 1, yb), c].mean()) if yb > ya else x

    def best_row(y, xa, xb):
        cands = range(max(0, y - SNAP_PX), min(H - 1, y + SNAP_PX) + 1)
        return max(cands, key=lambda r: gy[r, max(0, xa):max(xa + 1, xb)].mean()) if xb > xa else y
    nx0, nx1 = best_col(x0, y0, y1), best_col(x1, y0, y1)
    ny0, ny1 = best_row(y0, x0, x1), best_row(y1, x0, x1)
    if nx1 - nx0 < 0.5 * (x1 - x0) or ny1 - ny0 < 0.5 * (y1 - y0):  # verfijning onbetrouwbaar: origineel houden
        return x0, y0, x1, y1, False
    return nx0, ny0, nx1, ny1, True


def run(poc_out, out, limit=None, only_usable=True):
    poc_out, out = Path(poc_out), Path(out)
    (out / "annotated").mkdir(parents=True, exist_ok=True)
    summary = json.loads((poc_out / "summary.json").read_text(encoding="utf-8"))
    package = Path(summary["source_package"])
    pkg = json.loads((package / "candidates" / f"{summary['group']}.json").read_text(encoding="utf-8"))
    cand = {c["bag_pand_id"]: c for c in pkg["candidate_panden"]}
    walls = [w for w in summary["walls"] if w.get("panorama") and (w["usable"] or not only_usable)]
    walls.sort(key=lambda w: -w["wall_m2"])
    if limit:
        walls = walls[:limit]
    client = anthropic.Anthropic()
    rows, usage = [], {"input_tokens": 0, "output_tokens": 0}
    surf_cache = {}
    for w in walls:
        pid = w["bag_pand_id"]
        if pid not in surf_cache:
            raw = json.loads((package / cand[pid]["threedbag"]["raw_response_path"]).read_text(encoding="utf-8"))
            surf_cache[pid] = [r for t, r in fp.load_surfaces(raw) if t == "WallSurface"]
        ring = surf_cache[pid][w["wall_index"]]
        n, _ = fp.normal_area(ring)
        p = {"pano_id": w["panorama"]["pano_id"], "_links": {"equirectangular_full": {"href": w["panorama"]["url"]}},
             "geometry": None}
        meta_api = fp.http_json(f"{fp.PANO_API}{w['panorama']['pano_id']}/?format=json")
        p["geometry"] = meta_api["geometry"]
        cam = fp.cam_rd(p)
        img = fp.fetch_image(p, poc_out / "cache")
        rimg, mask, meta = fp.rectify(img, cam, n, ring, res=RES)
        bg = Image.new("RGB", rimg.size, (128, 128, 128)); bg.paste(rimg, mask=mask)
        if max(bg.size) > MAX_EDGE:
            continue
        try:
            parsed, msg = ask_model(client, bg, meta)
        except anthropic.APIStatusError as ex:
            print(f"{pid} w{w['wall_index']:02d}: API-fout {ex.status_code}", flush=True)
            continue
        usage["input_tokens"] += msg.usage.input_tokens
        usage["output_tokens"] += msg.usage.output_tokens
        gray = np.asarray(bg.convert("L"), float)
        els = []
        ann = bg.copy(); d = ImageDraw.Draw(ann)
        if parsed and parsed.image_usable:
            for e in parsed.elements:
                x0, y0, x1, y1, snapped = snap_edges(gray, e)
                wm, hm = Decimal(str(round((x1 - x0) * RES, 3))), Decimal(str(round((y1 - y0) * RES, 3)))
                els.append({**e.model_dump(), "refined_px": [x0, y0, x1, y1], "snapped": snapped,
                            "width_m": str(wm), "height_m": str(hm), "area_m2": str((wm * hm).quantize(Decimal("0.01")))})
                d.rectangle([x0, y0, x1, y1], outline=(255, 0, 0) if e.type == "window" else (0, 120, 255), width=3)
        fn = out / "annotated" / f"{pid}_w{w['wall_index']:02d}.jpg"
        ann.save(fn, quality=88)
        rows.append({"bag_pand_id": pid, "wall_index": w["wall_index"], "wall_m2": w["wall_m2"],
                     "wall_azimuth_deg": w["wall_azimuth_deg"], "panorama": w["panorama"],
                     "image_usable_model": bool(parsed and parsed.image_usable),
                     "refused": parsed is None, "remarks": parsed.remarks if parsed else None,
                     "model_served": msg.model, "elements": els, "annotated_image": str(fn.relative_to(out)),
                     **meta})
        print(f"{pid} w{w['wall_index']:02d} {w['wall_m2']:5.1f} m2: {len(els)} elementen "
              f"({', '.join(sorted({e['type'] for e in els}))})", flush=True)
    agg = aggregate(rows)
    result = {"poc_version": "facade_element_detection_poc_v1", "model": MODEL, "res_m_per_px": RES,
              "source_summary": str(poc_out / "summary.json"), "walls_processed": len(rows), "usage": usage,
              "quantities_on_processed_walls": agg, "walls": rows,
              "label": "ESTIMATED_FROM_PANORAMA — schatting, niet gemeten ter plaatse; alleen verwerkte (zichtbare) wanden"}
    (out / "detections.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def aggregate(rows):
    q = {"window_count": 0, "door_count": 0, "garage_door_count": 0, "balcony_count": 0, "dormer_count": 0,
         "frame_area_m2": Decimal(0), "window_sill_m1": Decimal(0), "facade_panel_m2": Decimal(0),
         "wall_m2_processed": Decimal(0), "elements_partially_hidden": 0}
    for r in rows:
        q["wall_m2_processed"] += Decimal(str(r["wall_m2"]))
        for e in r["elements"]:
            a, wdt = Decimal(e["area_m2"]), Decimal(e["width_m"])
            q["elements_partially_hidden"] += int(e["partially_hidden"])
            if e["type"] in ("window", "door", "garage_door", "dormer"):
                q[f"{e['type']}_count"] += 1
                q["frame_area_m2"] += a
            if e["type"] == "window":
                q["window_sill_m1"] += wdt
            if e["type"] == "balcony":
                q["balcony_count"] += 1
            if e["type"] == "facade_panel":
                q["facade_panel_m2"] += a
    return {k: (str(v.quantize(Decimal("0.01"))) if isinstance(v, Decimal) else v) for k, v in q.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--poc-out", required=True, help="--out-map van facade_panorama_poc.py (summary.json + cache)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    r = run(a.poc_out, a.out, a.limit)
    print(json.dumps({"walls": r["walls_processed"], "usage": r["usage"], **r["quantities_on_processed_walls"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
