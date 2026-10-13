#!/usr/bin/env python3
"""Maldenhof Visual Photo Review v1 - MAP-003 & MAP-004.

Maakt een visueel controlepakket zodat een mens zelf kan nagaan welke kozijnen/deuren/openingen op MAP-003 en MAP-004 zichtbaar zijn,
welke objecten mogelijk op meerdere foto's staan (MAP-002, MAP-009, MAP-013, MAP-033), welke huisnummerplaten leesbaar zijn en welk
bewijs voor een pandtoewijzing ontbreekt.

Uitsluitend knippen, vergroten en annoteren van de originele pixels (geen gegenereerde beeldinhoud). De originelen blijven buiten de
repository (zip in /mnt/project-files); de SHA256 wordt tegen het archiefregister gecontroleerd. Tijdelijke observatie-ID's
(OBS-MAP003-nnn, OBS-MAP004-nnn) staan buiten het instance-archief; geen instances, geen pandkoppelingen, geen totalen, geen maten,
geen kosten, geen repeat-multipliers. Alle APP-besluiten blijven OPEN.

Gebruik: python3 scripts/build_visual_photo_review_map003_map004.py [--zip PAD]
"""
import argparse
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import visual_review_map003_map004_data as V  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "reports" / "frames" / "photo_archive_audit_v1" / "maldenhof_photo_archive_audit_v1.json"
ADDR = ROOT / "data" / "photo_evidence" / "maldenhof_address_pand_evidence_v1.json"
CAND2 = ROOT / "data" / "photo_evidence" / "maldenhof_2_frame_candidates_corrected_v1.json"
INST2 = ROOT / "data" / "frame_inventory" / "maldenhof_photo_frame_instances_v1.json"
APPROVAL = ROOT / "reports" / "frames" / "photo_archive_audit_v1" / "maldenhof_photo_annotation_approval_v1.md"
OUT = ROOT / "reports" / "frames" / "photo_review_map003_map004_v1"
OUT_JSON = OUT / "maldenhof_visual_photo_review_map003_map004_v1.json"
OUT_MD = OUT / "maldenhof_visual_photo_review_map003_map004_v1.md"
ZIP_DEFAULT = "/mnt/project-files/Maldenhof_kozijnfoto_selectie (4) 2.zip"
VERSION = "visual_photo_review_map003_map004_v1.0.0"
SOURCES = ["MAP-002", "MAP-003", "MAP-004", "MAP-009", "MAP-013", "MAP-033"]
IMG = {
    "A": "A_overview_MAP-003.jpg",
    "B": "B_overview_MAP-004.jpg",
    "C1": "C1_MAP-003_vs_MAP-004_upper_facade.jpg",
    "C2": "C2_MAP-003_vs_MAP-004_middle_facade.jpg",
    "C3": "C3_MAP-003_vs_MAP-004_roof_kap_ground.jpg",
    "D1": "D1_MAP-002_vs_MAP-003_ground_wall_288.jpg",
    "D2": "D2_MAP-002_vs_MAP-003_kap_and_middle_row.jpg",
    "D3": "D3_MAP-002_vs_MAP-003_upper_row.jpg",
    "D4": "D4_MAP-002_vs_MAP-003_roof_dormer.jpg",
    "E": "E_plates_MAP-003_MAP-004.jpg",
    "F": "F_reference_MAP-009_MAP-013_MAP-033.jpg",
}
COL = {"WINDOW_OPENING": (255, 230, 0), "EXTERIOR_DOOR": (255, 70, 70), "WINDOW_DOOR_COMBINATION": (255, 140, 0),
       "ROOF_WINDOW": (0, 230, 255), "DORMER_OPENING": (90, 255, 90), "UNKNOWN_OPENING": (255, 255, 255)}
PLATE_COL = (255, 0, 255)
FC_COL = (255, 150, 0)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
F = lambda s: ImageFont.truetype(FONT, s)  # noqa: E731
FR = lambda s: ImageFont.truetype(FONT_R, s)  # noqa: E731
D = V.D
PHOTO2_DUPS = {1, 2, 3, 6, 7, 8, 9, 10, 15, 16, 17, 22}   # observaties op MAP-003 met kandidaat-relatie naar foto 2 (VR-002..013)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def load_sources(zip_path):
    reg = {p["photo_id"]: p for p in json.load(open(AUDIT))["photos"]}
    z = zipfile.ZipFile(zip_path)
    ims, ver = {}, {}
    for pid in SOURCES:
        p = reg[pid]
        raw = z.read(f"{p['group_folder']}/{p['original_file']}")
        ok = sha(raw) == p["sha256"]
        im = Image.open(io.BytesIO(raw))
        im.load()
        raw_dims = [im.width, im.height]
        orientation = im.getexif().get(274, 1)
        ims[pid] = ImageOps.exif_transpose(im).convert("RGB")   # alleen draaien voor weergave; pixels ongewijzigd
        ver[pid] = {"exif_orientation": orientation, "raw_dims": raw_dims, "photo_id": pid, "file": p["original_file"], "zip_path": p["zip_path"], "sha256_register": p["sha256"],
                    "sha256_verified": ok, "width_px": raw_dims[0], "height_px": raw_dims[1],
                    "dims_match_register": raw_dims == [p["width_px"], p["height_px"]]}
        if not ok or not ver[pid]["dims_match_register"]:
            raise SystemExit(f"{pid}: SHA256/afmeting komt niet overeen met het register; stop.")
    return ims, ver


def dashed(d, box, col, w=2, dash=8):
    x0, y0, x1, y1 = box
    for x in range(x0, x1, dash * 2):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=col, width=w)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=col, width=w)
    for y in range(y0, y1, dash * 2):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=col, width=w)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=col, width=w)


def text(d, xy, s, col, size=20, stroke=2):
    d.text(xy, s, font=F(size), fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0))


def obs_list(photo):
    return V.MAP003 if photo == "MAP-003" else V.MAP004


def plates_of(photo):
    return V.PLATES003 if photo == "MAP-003" else V.PLATES004


def draw_obs(d, obs, tf, size=20, show_plates=None, dup=()):
    """tf(box)->box in doelcoordinaten of None (buiten crop)."""
    for n, t, v, b, *_ in obs:
        bb = tf(D(*b))
        if bb is None:
            continue
        c = COL[t]
        if v == "PARTIAL":
            dashed(d, bb, c, 3)
        elif v in ("HEAVILY_OCCLUDED", "UNKNOWN_OPENING"):
            dashed(d, bb, c, 3, 4)
        else:
            d.rectangle(bb, outline=c, width=3)
        text(d, (bb[0] + 2, max(bb[1] - size - 4, 0)), str(n), c, size)
        if n in dup:
            text(d, (bb[0] + 2, bb[3] + 2), "DUP?", (255, 90, 90), size - 4)
    for nr, b in (show_plates or []):
        bb = tf(D(*b))
        if bb is None:
            continue
        d.rectangle(bb, outline=PLATE_COL, width=3)
        text(d, (bb[0], bb[3] + 2), f"P{nr}", PLATE_COL, size - 2)


def crop_tf(box, s):
    x0, y0, x1, y1 = box

    def tf(bb):
        a, b, c, e = bb
        if c < x0 or a > x1 or e < y0 or b > y1:
            return None
        return [round((max(a, x0) - x0) * s), round((max(b, y0) - y0) * s), round((min(c, x1) - x0) * s), round((min(e, y1) - y0) * s)]
    return tf


# --- A / B -------------------------------------------------------------------------------------------------------------------------
def overview(im, photo, fn, sha256, out):
    obs, plates = obs_list(photo), plates_of(photo)
    W, H = im.size
    legend_w = 700
    canvas = Image.new("RGB", (W + legend_w, H + 70), (20, 20, 20))
    canvas.paste(im, (0, 70))
    d = ImageDraw.Draw(canvas)
    d.text((10, 8), f"{photo} | {fn} | {W}x{H} px originele pixels | SHA256 {sha256[:16]}... geverifieerd", font=F(22), fill=(255, 255, 255))
    d.text((10, 38), "Voorlopige observaties (OBS-" + photo.replace("-", "") + "-nnn); geen instances, geen telling. Stippel = PARTIAL / onzeker; rechthoek = FULL.",
           font=FR(18), fill=(220, 220, 220))
    sub = canvas.crop((0, 70, W, H + 70))
    sd = ImageDraw.Draw(sub)
    draw_obs(sd, obs, lambda bb: bb, 24, plates)
    canvas.paste(sub, (0, 70))
    d = ImageDraw.Draw(canvas)
    x, y = W + 16, 80
    d.text((x, y), "Legenda (nr, type, zichtbaarheid, onzekerheid)", font=F(20), fill=(255, 255, 255))
    y += 34
    for n, t, v, b, pos, note, unc in obs:
        c = COL[t]
        d.rectangle([x, y + 4, x + 18, y + 22], outline=c, width=3)
        d.text((x + 28, y), f"{n:02d} {t.replace('_OPENING', '').replace('EXTERIOR_', '')[:8]:<8} {v[:7]:<7} {unc[:1]}", font=FR(19), fill=(235, 235, 235))
        y += 25
    y += 14
    d.text((x, y), "Huisnummerplaten (magenta, P<nr>):", font=F(20), fill=PLATE_COL)
    y += 30
    d.text((x, y), ", ".join(str(nr) for nr, _ in plates) + "  (alle leesbaar bij vergroting, zie E)", font=FR(19), fill=(235, 235, 235))
    y += 40
    for line in ["Kleuren: geel=raam, cyaan=dakraam, groen=dakkapel,", "rood=buitendeur, wit=onbepaalde opening, magenta=plaat.", "Onzekerheid: L(ow) / M(edium) / H(igh).",
                 "Per-observatie details: .json en .md in deze map."]:
        d.text((x, y), line, font=FR(17), fill=(200, 200, 200))
        y += 24
    canvas.save(out, quality=86, optimize=True)


# --- C / D (naast elkaar) ---------------------------------------------------------------------------------------------------------
def side_by_side(rows, ims, out, left, right, head):
    """rows: (titel, (foto_l, box_l_display), (foto_r, box_r_display), relids). left/right = callables(foto, im, box)->Image."""
    target = 760
    tiles, H = [], 70
    for title, (pl, bl), (pr, br), rels in rows:
        pair = []
        for pid, bx, fn in ((pl, bl, left), (pr, br, right)):
            box = D(*bx)
            s = target / (box[2] - box[0])
            pair.append(fn(pid, ims[pid], box, s))
        h = max(t.height for t in pair)
        tiles.append((title, rels, pair, h))
        H += h + 52
    canvas = Image.new("RGB", (target * 2 + 40, H), (20, 20, 20))
    d = ImageDraw.Draw(canvas)
    d.text((10, 8), head, font=F(22), fill=(255, 255, 255))
    d.text((10, 38), "Alleen uitsneden/vergrotingen van de originele pixels met annotaties. Relaties zijn kandidaten (SAME_OBJECT_CANDIDATE); niets samengevoegd.",
           font=FR(17), fill=(210, 210, 210))
    y = 70
    for title, rels, pair, h in tiles:
        d.text((10, y), f"{title}   [{rels}]", font=F(19), fill=(255, 255, 255))
        y += 30
        canvas.paste(pair[0], (10, y))
        canvas.paste(pair[1], (target + 30, y))
        y += h + 22
    canvas.save(out, quality=86, optimize=True)


def tile_obs(pid, im, box, s, dup=()):
    t = im.crop(tuple(box)).resize((round((box[2] - box[0]) * s), round((box[3] - box[1]) * s)), Image.LANCZOS)
    d = ImageDraw.Draw(t)
    if pid in ("MAP-003", "MAP-004"):
        draw_obs(d, obs_list(pid), crop_tf(box, s), 22, plates_of(pid), dup if pid == "MAP-003" else ())
    d.rectangle([0, 0, 190, 26], fill=(0, 0, 0))
    d.text((4, 3), f"{pid} x{box[0]}-{box[2]} y{box[1]}-{box[3]}", font=FR(16), fill=(255, 255, 255))
    return t


def photo2_boxes():
    c = json.load(open(CAND2))
    inst = json.load(open(INST2))
    fi = {}
    for x in inst["instances"]:
        for r in x["source_refs"]:
            if r.get("candidate_id"):
                fi.setdefault(r["candidate_id"], x["frame_instance_id"])
    boxes = {}
    for k in ("child_candidates",):
        for x in c[k]:
            boxes[x["candidate_id"]] = x["bbox_norm"]
    for x in c["candidate_decisions"]:
        if not x.get("children"):
            boxes[x["candidate_id"]] = x["original_bbox_norm"]
    for x in c["roof_context_observations"] + c["dormer_context_observations"]:
        boxes[x["candidate_id"]] = x["bbox_norm"]
    boxes.pop("FC-M2-006-B", None)
    boxes.pop("FC-M2-006-C", None)
    fi["FC-M2-006-BC"] = "FI-M2-014"
    return boxes, fi


def tile_photo2(pid, im, box, s):
    t = im.crop(tuple(box)).resize((round((box[2] - box[0]) * s), round((box[3] - box[1]) * s)), Image.LANCZOS)
    d = ImageDraw.Draw(t)
    boxes, fi = photo2_boxes()
    W, H = im.size
    for cid, nb in boxes.items():
        bb = [round(nb[0] * W), round(nb[1] * H), round(nb[2] * W), round(nb[3] * H)]
        tb = crop_tf(box, s)(bb)
        if tb is None:
            continue
        d.rectangle(tb, outline=FC_COL, width=3)
        lab = cid.replace("FC-M2-", "FC") + (("/" + fi[cid].replace("FI-M2-", "FI")) if cid in fi else "")
        low = cid.endswith("-A")
        text(d, (tb[0] + 2, tb[3] + 2 if low else max(tb[1] - 22, 28)), lab, FC_COL, 17)
    d.rectangle([0, 0, 330, 26], fill=(0, 0, 0))
    d.text((4, 3), f"{pid} (foto 2, bevroren annotaties) x{box[0]}-{box[2]} y{box[1]}-{box[3]}", font=FR(15), fill=FC_COL)
    return t


def make_C(ims):
    r = "MAP-003", "MAP-004"
    C1 = [
        ("R1 bovenste rij: raam met gordijn en open vleugels", (r[0], (740, 430, 1060, 590)), (r[1], (100, 430, 420, 590)), "VR-031"),
        ("R2 bovenste rij: tweedelig kozijn + smal raam", (r[0], (1110, 440, 1420, 590)), (r[1], (490, 440, 800, 590)), "VR-027, VR-028"),
        ("R3 bovenste rij rechts: smal raam + kozijn met open vleugel", (r[0], (1530, 440, 1830, 590)), (r[1], (940, 440, 1260, 590)), "VR-029, VR-030"),
    ]
    C2 = [
        ("R4 middelste rij links van de kap", (r[0], (830, 610, 1340, 800)), (r[1], (110, 610, 620, 800)), "VR-024, VR-025"),
        ("R5 middelste rij rechts van de kap", (r[0], (1770, 610, 1965, 800)), (r[1], (1040, 610, 1300, 800)), "VR-026"),
        ("R6 dakraam in het dakschild van de kap", (r[0], (1540, 640, 1720, 780)), (r[1], (720, 650, 900, 780)), "VR-023"),
    ]
    C3 = [
        ("R7 dakramen in het hoofddakvlak (2 stuks)", (r[0], (890, 290, 1230, 390)), (r[1], (330, 290, 670, 390)), "VR-032, VR-033"),
        ("R8 dakraam hoofddakvlak rechts", (r[0], (1600, 310, 1720, 400)), (r[1], (1090, 310, 1230, 400)), "VR-034"),
        ("R9 begane grond: platen 280/278 + raam 278 + entreenis", (r[0], (1430, 840, 1850, 960)), (r[1], (220, 840, 640, 960)), "VR-020, VR-021, VR-022"),
    ]
    for key, rows, head in (("C1", C1, "C1: MAP-003 (links) vs MAP-004 (rechts), bovenste gevelrij"),
                            ("C2", C2, "C2: MAP-003 (links) vs MAP-004 (rechts), middelste gevelrij en kap"),
                            ("C3", C3, "C3: MAP-003 (links) vs MAP-004 (rechts), dakramen en begane grond")):
        side_by_side(rows, ims, OUT / IMG[key], lambda pid, im, box, s: tile_obs(pid, im, box, s),
                     lambda pid, im, box, s: tile_obs(pid, im, box, s), head + " | nr = OBS-ID-nummer")


def make_D(ims):
    a, b = "MAP-002", "MAP-003"
    rows = {
        "D1": [("D1 begane grond: plaat 288 + raam rechts ervan", (a, (1690, 860, 2000, 1030)), (b, (0, 840, 400, 1000)), "VR-001, VR-002")],
        "D2": [("D2 kap met dakraam + middelste rij", (a, (1330, 610, 2000, 880)), (b, (240, 540, 700, 800)), "VR-003, VR-004, VR-005")],
        "D3": [("D3 bovenste gevelrij", (a, (1280, 480, 1960, 650)), (b, (290, 405, 1030, 590)), "VR-006, VR-007, VR-008, VR-009, VR-010")],
        "D4": [("D4 dakkapel + dakraam", (a, (1020, 320, 1420, 460)), (b, (30, 200, 470, 372)), "VR-011, VR-012"),
               ("D4b dakraam rechts van de schoorstenen", (a, (1760, 380, 1880, 450)), (b, (900, 300, 990, 370)), "VR-013")],
    }
    for key, rs in rows.items():
        side_by_side(rs, ims, OUT / IMG[key], lambda pid, im, box, s: tile_photo2(pid, im, box, s),
                     lambda pid, im, box, s: tile_obs(pid, im, box, s, PHOTO2_DUPS),
                     f"{key}: MAP-002 (links; oranje = bevroren foto-2-annotaties) vs MAP-003 (rechts; DUP? = mogelijk dubbel van foto 2)")


def make_E(ims, plate_rows):
    tiles = []
    for photo, nr, bb, reading, status in plate_rows:
        im = ims[photo]
        x0, y0, x1, y1 = bb
        pad = 14
        t = im.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
        t = t.resize((t.width * 6, t.height * 6), Image.LANCZOS)
        cap = Image.new("RGB", (max(t.width, 380), t.height + 80), (20, 20, 20))
        cap.paste(t, (0, 0))
        d = ImageDraw.Draw(cap)
        d.text((4, t.height + 4), f"{photo} plaat P{nr}  lezing {reading}", font=F(17), fill=(255, 255, 255))
        d.text((4, t.height + 28), f"origineel x{x0}-{x1} y{y0}-{y1} px", font=FR(15), fill=(210, 210, 210))
        d.text((4, t.height + 50), status, font=FR(15), fill=(255, 220, 120))
        tiles.append(cap)
    cols = 4
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    rh = [max(t.height for t in r) for r in rows]
    W = sum(max(t.width for t in col) + 10 for col in zip(*[r + [Image.new('RGB', (380, 1))] * (cols - len(r)) for r in rows]))
    canvas = Image.new("RGB", (W + 10, sum(rh) + 20 * len(rows) + 60), (20, 20, 20))
    d = ImageDraw.Draw(canvas)
    d.text((10, 8), "E: huisnummerplaten MAP-003 en MAP-004, 6x vergroting van de originele pixels (voorlopige lezing; bevestiging via APP-002/003)", font=F(21), fill=(255, 255, 255))
    y = 50
    for r, h in zip(rows, rh):
        x = 10
        for t in r:
            canvas.paste(t, (x, y))
            x += max(t.width, 380) + 10
        y += h + 20
    canvas.save(OUT / IMG["E"], quality=88, optimize=True)


def make_F(ims):
    parts = []
    for pid in ("MAP-009", "MAP-013", "MAP-033"):
        im = ims[pid].copy()
        d = ImageDraw.Draw(im)
        for rid, ph, bx, desc in V.REFS:
            if ph != pid:
                continue
            bb = [round(v * V.REF_SCALE) for v in bx]
            d.rectangle(bb, outline=(255, 140, 0), width=6)
            text(d, (bb[0] + 4, max(bb[1] - 44, 0)), rid.replace("REF-", ""), (255, 140, 0), 38, 3)
        s = 900 / im.height
        im = im.resize((round(im.width * s), 900), Image.LANCZOS)
        parts.append((pid, im))
    W = sum(p.width for _, p in parts) + 10 * (len(parts) + 1)
    canvas = Image.new("RGB", (W, 960), (20, 20, 20))
    d = ImageDraw.Draw(canvas)
    x = 10
    for pid, im in parts:
        d.text((x, 6), f"{pid}: referentiegebieden (geen observaties)", font=F(22), fill=(255, 255, 255))
        canvas.paste(im, (x, 50))
        x += im.width + 10
    canvas.save(OUT / IMG["F"], quality=82, optimize=True)


# --- gegevens ---------------------------------------------------------------------------------------------------------------------
def pand_of(nr, addr):
    for a in addr["addresses"]:
        if a["huisnummer"] == nr:
            order = {p["bag_pand_id"]: p["order"] for p in addr["pand_order"]}
            return a["bag_pand_id"], order.get(a["bag_pand_id"])
    return None, None


def build_data(ver, addr):
    obs = []
    for photo, lst in (("MAP-003", V.MAP003), ("MAP-004", V.MAP004)):
        W = ver[photo]["width_px"]
        H = ver[photo]["height_px"]
        for n, t, v, b, pos, note, unc in lst:
            bb = D(*b)
            obs.append({
                "obs_id": f"OBS-{photo.replace('-', '')}-{n:03d}", "photo_id": photo, "source_file": ver[photo]["file"],
                "source_sha256": ver[photo]["sha256_verified"] and ver[photo]["sha256_register"], "observation_type": t, "visibility": v,
                "bbox_px": bb, "bbox_norm": [round(bb[0] / W, 4), round(bb[1] / H, 4), round(bb[2] / W, 4), round(bb[3] / H, 4)],
                "position_hint": pos, "note": note, "uncertainty": unc, "method": "MANUAL_VISUAL_READING",
                "is_instance": False, "bag_pand_id": None, "pand_status": "NOT_PROVEN",
                "counts_in_any_total": False,
            })
    plates = []
    for photo, lst in (("MAP-003", V.PLATES003), ("MAP-004", V.PLATES004)):
        for nr, b in lst:
            pid, order = pand_of(nr, addr)
            plates.append({"plate_id": f"PL-{photo.replace('-', '')}-{nr}", "photo_id": photo, "reading": nr, "bbox_px": D(*b),
                           "legibility": "LEGIBLE_AT_ENLARGEMENT", "reading_status": "PROVISIONAL_UNCONFIRMED_BY_HUMAN",
                           "bag_pand_id_for_plate_wall": pid, "pand_order": order,
                           "scope": "ALLEEN_PLAATMUUR (APP-001); omliggende ramen/deuren niet bewezen"})
    return obs, plates


def md_table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    return "\n".join(out)


def counts(obs, photo):
    c = Counter(o["observation_type"] for o in obs if o["photo_id"] == photo)
    v = Counter(o["visibility"] for o in obs if o["photo_id"] == photo)
    return c, v


def build_md(ver, obs, plates, data):
    n3 = sum(1 for o in obs if o["photo_id"] == "MAP-003")
    n4 = sum(1 for o in obs if o["photo_id"] == "MAP-004")
    L = []
    L.append("# Maldenhof Visual Photo Review v1 - MAP-003 & MAP-004\n")
    L.append("**Status:** visueel controlepakket, uitsluitend voor menselijke beoordeling. Er zijn geen instances, geen pandkoppelingen, geen unieke aantallen, "
             "geen maten, kosten of repeat-multipliers vastgelegd. Alle 48 APP-besluiten uit `maldenhof_photo_annotation_approval_v1.md` blijven OPEN. "
             "Foto 2 blijft bevroren (11 gewone kozijnen, 1 buitendeur; 9 FULL, 2 PARTIAL).\n")
    L.append("Bewijsniveaus: (1) zichtbare observatie, (2) kandidaat voor een fysiek object, (3) bewezen uniek fysiek exemplaar, (4) bewezen koppeling aan een specifiek pand. "
             "Dit document komt niet verder dan niveau 1-2; een leesbare plaat bewijst alleen de muur met die plaat (APP-001).\n")
    L.append("## 1. Bronnen en verificatie\n")
    rows = [(v["photo_id"], v["file"], v["zip_path"], f"{v['width_px']}x{v['height_px']}", v["sha256_register"][:16] + "...", "JA" if v["sha256_verified"] else "NEE")
            for v in ver.values()]
    L.append(md_table(rows, ["Foto", "Bestand", "Pad in zip", "Resolutie", "SHA256 (register)", "Tegen origineel geverifieerd"]))
    L.append("\nDe originelen (zip in `/mnt/project-files`) zijn op volle resolutie geopend en tegen het register uit de Photo Archive Audit gecontroleerd; de originelen staan niet in Git. "
             "De afbeeldingen in deze map bevatten uitsluitend uitsneden, vergrotingen en annotaties van de originele pixels (geen gegenereerde beeldinhoud). "
             "MAP-002 is de bron van de bevroren foto 2 (`maldenhof_2`); de foto-2-annotaties zijn uit de bestaande bevroren bestanden overgenomen en niet gewijzigd. "
             "MAP-009, MAP-013 en MAP-033 zijn alleen als referentie voor overlap gebruikt (afbeelding F).\n")
    L.append("## 2. Overzicht van alle voorlopige observatie-ID's\n")
    L.append("Tijdelijke ID's, buiten het instance-archief. Een observatie is een zichtbare opening en geen telling; bboxen zijn handmatig bepaald op de originele pixels (MANUAL_VISUAL_READING, geen meting).\n")
    for photo in ("MAP-003", "MAP-004"):
        L.append(f"### {photo}\n")
        rows = [(o["obs_id"], o["observation_type"], o["visibility"], o["bbox_px"], o["position_hint"], o["uncertainty"], o["note"]) for o in obs if o["photo_id"] == photo]
        L.append(md_table(rows, ["Observatie", "Type", "Zichtbaarheid", "bbox px [x0,y0,x1,y1]", "Positie", "Onzekerheid", "Toelichting"]))
        L.append("")
    L.append("## 3. Afbeeldingen\n")
    desc = {
        "A": "Overzicht MAP-003 met genummerde observaties, platen apart (magenta) en legenda.",
        "B": "Overzicht MAP-004 met genummerde observaties, platen apart en legenda.",
        "C1": "MAP-003 naast MAP-004, bovenste gevelrij (VR-027..031).",
        "C2": "MAP-003 naast MAP-004, middelste rij en kap (VR-023..026).",
        "C3": "MAP-003 naast MAP-004, dakramen en begane grond met platen (VR-020..022, VR-032..034).",
        "D1": "MAP-002 (bevroren foto-2-annotaties, oranje) naast MAP-003: plaat 288 en raam (VR-001, VR-002).",
        "D2": "MAP-002 naast MAP-003: kap met dakraam en middelste rij (VR-003..005).",
        "D3": "MAP-002 naast MAP-003: bovenste gevelrij (VR-006..010).",
        "D4": "MAP-002 naast MAP-003: dakkapel en dakramen (VR-011..013).",
        "E": "Plaatuitsneden (6x) met locatie en voorlopige lezing.",
        "F": "Referentiegebieden op MAP-009, MAP-013 en MAP-033 voor de overlapanalyse (geen observaties).",
    }
    L.append(md_table([(k, f"[{v}]({v})", desc[k]) for k, v in IMG.items()], ["Afb.", "Bestand", "Inhoud"]))
    L.append("\nKaders: gele rechthoek = raam, cyaan = dakraam, groen = dakkapel, rood = buitendeur, wit = onbepaald, magenta = huisnummerplaat; "
             "doorgetrokken = FULL, gestippeld = PARTIAL/verborgen. In D markeert oranje de bevroren foto-2-kandidaten (FC/FI), `DUP?` een kandidaat op MAP-003 die mogelijk hetzelfde object is als een foto-2-kozijn.\n")
    L.append("## 4. Objectclassificaties (observaties, geen objecttotalen)\n")
    for photo in ("MAP-003", "MAP-004"):
        c, v = counts(obs, photo)
        L.append(f"- **{photo}:** " + ", ".join(f"{k} {n}" for k, n in sorted(c.items())) + ".")
    L.append("\nGeldende telregels toegepast: een kozijn met meerdere vleugels/ruiten is een opening; een kozijnstijl of ruitverdeling scheidt niet; gemetseld penant tussen twee kozijnen scheidt wel "
             "(zoals foto 2 PCD-00004). Een raam-deurcombinatie in een doorlopend kozijn zou een opening zijn (REL-M3-001); op MAP-003/004 is er geen zekere combinatie gevonden. "
             "Dakramen en dakkapellen zijn fotoobservaties (ROOF_WINDOW/DORMER_OPENING), geen gewone EXTERIOR_FRAME-instances. Er zijn geen verborgen kozijnen afgeleid uit herhaling of symmetrie. "
             "De aantallen hierboven zijn aantallen observaties per foto; ze overlappen elkaar en met foto 2 en zijn nergens opgeteld.\n")
    L.append("## 5. Zichtbaarheidsclassificaties\n")
    for photo in ("MAP-003", "MAP-004"):
        _, v = counts(obs, photo)
        L.append(f"### {photo}\n")
        for k in ("FULL", "PARTIAL", "HEAVILY_OCCLUDED", "UNKNOWN_OPENING"):
            ids = [o["obs_id"][-3:] for o in obs if o["photo_id"] == photo and o["visibility"] == k]
            L.append(f"- **{k}** ({len(ids)}): {', '.join(ids) if ids else '-'}")
        L.append("")
    L.append("Onzekerheid HIGH (handmatige beoordeling nodig): " + ", ".join(o["obs_id"] for o in obs if o["uncertainty"] == "HIGH") + ".\n")
    L.append("## 6. Overlaprelaties (alleen kandidaten)\n")
    L.append("Klassen: SAME_FACADE_SECTION (dezelfde gevelpartij zichtbaar), POSSIBLY_SAME_PHYSICAL_FRAME (mogelijk hetzelfde fysieke kozijn), DIFFERENT_FRAMES (verschillende kozijnen), UNDETERMINABLE (niet te bepalen). "
             "Een gedeelde plaat bewijst niet dat de omliggende ramen dezelfde zijn. De verschuiving tussen foto's is diepteafhankelijk (parallax): dichterbij gelegen delen (begane-grondmuur) verschuiven meer dan de gevel en het dakvlak; "
             "daarom zijn paren alleen binnen dezelfde laag vergeleken. Geen relatie is bevestigd en niets is samengevoegd of opgeteld.\n")
    names = {"SOC-001": "SOC-001 MAP-002 vs MAP-003 (afb. D)", "SOC-002": "SOC-002 MAP-003 vs MAP-004, plus MAP-009 (afb. C, F)",
             "SOC-003": "SOC-003 MAP-003 vs MAP-013 (afb. F)", "SOC-008": "SOC-008 MAP-004 vs MAP-033 (afb. F)"}
    for soc in ("SOC-001", "SOC-002", "SOC-003", "SOC-008"):
        L.append(f"### {names[soc]}\n")
        rows = [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in V.RELATIONS if r[1] == soc]
        L.append(md_table(rows, ["Relatie", "Links", "Rechts", "Klasse", "Sterkte", "Grondslag"]))
        L.append("")
    cc = Counter(r[4] for r in V.RELATIONS)
    L.append("Samenvatting relaties (aantal kandidaat-relaties per klasse): " + ", ".join(f"{k} {n}" for k, n in sorted(cc.items())) + ".\n")
    L.append("Bevestigd: SOC-003 (MAP-013) en SOC-008 (MAP-033) zijn bronnen waarin plaat en raam in een beeld staan; ze maken de koppeling plaatmuur-raam zichtbaar maar bewijzen die niet voor andere ramen. "
             "SOC-002: MAP-009 is sterk verkort en bevat alleen plaat 280 volledig leesbaar; de koppeling op MAP-009 blijft kandidaat.\n")
    L.append("## 7. Huisnummerplaten en bewijspositie\n")
    rows = [(p["plate_id"], p["photo_id"], p["reading"], p["bbox_px"], p["legibility"], p["bag_pand_id_for_plate_wall"], p["pand_order"]) for p in plates]
    L.append(md_table(rows, ["Plaat", "Foto", "Lezing", "bbox px", "Leesbaarheid", "BAG-pand van de plaatmuur", "Pandvolgorde"]))
    L.append("\nAlle elf plaatopnamen zijn bij 6x vergroting duidelijk leesbaar (afb. E); geen plaat is UNCONFIRMED door onleesbaarheid. De lezing blijft voorlopig tot een mens APP-002/APP-003 beantwoordt. "
             "De pandkoppeling gaat via bestaand BAG-bewijs (`maldenhof_address_pand_evidence_v1.json`) en geldt alleen voor de muur met de plaat (PAND_PROVEN_BY_VISIBLE_PLATE_ONLY).\n")
    L.append("## 8. Ontbrekend bewijs voor pandtoewijzing\n")
    L.append("Geen enkele observatie is aan een pand gekoppeld (alle 50 staan op `bag_pand_id: null`, `NOT_PROVEN`). Per groep:\n")
    L.append("- **Begane grond naast een plaat** (MAP-003: 022, 023, 024, 025; MAP-004: 018, 019): de plaat staat naast het raam, maar bewijst het raam niet (APP-001). Ontbrekend: een detailfoto waarop plaat en raam samen in een beeld staan "
             "(aanwezig voor 022/023 via MAP-013 en voor 019 via MAP-033, nog niet door een mens bevestigd) of een expliciete mensbevestiging.")
    L.append("- **Entreenissen/deuren** (MAP-003: 026, 027; MAP-004: 020, 022): geen plaat op de deur zelf; ontbrekend is een bevestiging welke woning de deur bedient.")
    L.append("- **Bovenste en middelste gevelrij, dakramen en dakkapel** (alle overige observaties): op deze lagen staat geen plaat; pandgrenzen zijn niet leesbaar uit de foto. Ontbrekend: bewijs van de pandgrens (bijv. regenpijp/penant of BAG-footprint met kozijnpositie) of mensbevestiging. De positie in het beeld is geen bewijs.")
    L.append("- **Pand 10-13 (platen 274-288)** hebben op MAP-003/MAP-004 elk minstens een leesbare plaat; panden 1, 5 en 15 hebben geen plaatfoto (zie het goedkeuringsdocument).")
    L.append("- **Partijen aan de beeldrand** (MAP-003: 006, 015, 020; MAP-004: 012, 022): te weinig zichtbaar om te beoordelen.\n")
    L.append("## 9. Concrete menselijke vragen\n")
    rows = [(q[0], q[4] or "(extra, tijdelijk ID)", q[1], q[2], q[3]) for q in V.QUESTIONS]
    L.append(md_table(rows, ["ID", "Gekoppeld besluit", "Onderwerp", "Vraag", "Aanbevolen antwoord"]))
    L.append("\nDe extra vragen HQ-VR-001..004 hebben een tijdelijk ID en zijn geen APP-besluiten; ze zijn niet in het goedkeuringsdocument opgenomen.\n")
    L.append("## 10. Samenvattend besluitoverzicht\n")
    L.append(md_table([
        ("Observaties MAP-003 / MAP-004", f"{n3} / {n4} voorlopig, geen instances"),
        ("Overlaprelaties", f"{len(V.RELATIONS)} kandidaat-relaties, geen bevestigd"),
        ("Platen leesbaar", "11 van 11 bij vergroting (voorlopig)"),
        ("Pandkoppelingen toegevoegd", "0"),
        ("Foto 2", "bevroren, ongewijzigd"),
        ("APP-besluiten", "48 OPEN"),
        ("Unieke totalen, maten, kosten, repeat", "geen"),
    ], ["Onderdeel", "Stand"]))
    L.append("\nHet pakket stopt na de PR; een mens beslist via de besluiten in sectie 9.\n")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=ZIP_DEFAULT)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    ims, ver = load_sources(args.zip)
    addr = json.load(open(ADDR))
    obs, plates = build_data(ver, addr)
    for photo, key in (("MAP-003", "A"), ("MAP-004", "B")):
        overview(ims[photo], photo, ver[photo]["file"], ver[photo]["sha256_register"], OUT / IMG[key])
    make_C(ims)
    make_D(ims)
    plate_rows = [(photo, nr, D(*b), str(nr), "LEGIBLE | provisional") for photo, lst in (("MAP-003", V.PLATES003), ("MAP-004", V.PLATES004)) for nr, b in lst]
    make_E(ims, plate_rows)
    make_F(ims)
    data = {
        "version": VERSION, "sources": list(ver.values()), "observations": obs, "plates": plates,
        "references": [{"ref_id": r[0], "photo_id": r[1], "bbox_px": [round(v * V.REF_SCALE) for v in r[2]], "description": r[3], "is_observation": False} for r in V.REFS],
        "relations": [dict(zip(["rel_id", "soc", "left", "right", "class", "strength", "basis"], r), merged=False, confirmed=False) for r in V.RELATIONS],
        "questions": [dict(zip(["id", "topic", "question", "recommended", "app_decision"], q), status="OPEN") for q in V.QUESTIONS],
        "images": IMG,
        "effects": {"instances_created": 0, "bag_links_created": 0, "building_totals": None, "quantities": None, "costs": None, "repeat_multipliers": None,
                    "app_decisions_open": 48, "photo2_unchanged": True},
        "stop": "Pull Request openen en wachten op menselijke goedkeuring; niet mergen.",
    }
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    OUT_MD.write_text(build_md(ver, obs, plates, data))
    print(f"Observaties: MAP-003 {sum(1 for o in obs if o['photo_id']=='MAP-003')}, MAP-004 {sum(1 for o in obs if o['photo_id']=='MAP-004')}; relaties {len(V.RELATIONS)}")


if __name__ == "__main__":
    main()
