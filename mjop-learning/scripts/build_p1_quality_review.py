#!/usr/bin/env python3
"""P1 Visual Review - Quality Corrections v1 (alleen rapportage; geen instances, pandkoppelingen, totalen, maten of kosten).

Bibliotheek voor build_human_visual_decision_pack.py: maakt de aanvullende bewijsfiguren uit de originele pixels, voert de technische controle op alle P1-reviewpunten
uit en schrijft het kwaliteitsrapport (maldenhof_p1_visual_quality_review_v1.md + .json). De visuele bevindingen staan in p1_quality_review_data.py; de
kenmerkmatch-resultaten komen uit p1_feature_match_evidence_v1.json (scripts/p1_visual_quality_evidence.py, optioneel opnieuw te draaien met OpenCV).
Een technisch geldige reviewkaart is niet automatisch een visueel bewezen object.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_visual_photo_review_map003_map004 as B  # noqa: E402
import human_decision_pack_data as H  # noqa: E402
import p1_quality_review_data as Q  # noqa: E402
import visual_review_map003_map004_data as V  # noqa: E402

QDIR = B.OUT / "p1_quality_review"
EVIDENCE_JSON = QDIR / "p1_feature_match_evidence_v1.json"
OUT_MD = B.OUT / "maldenhof_p1_visual_quality_review_v1.md"
OUT_JSON = B.OUT / "maldenhof_p1_visual_quality_review_v1.json"
SHEETS = {
    "QREL-sheet-1.jpg": ["VR-002", "VR-004", "VR-005", "VR-006", "VR-007"],
    "QREL-sheet-2.jpg": ["VR-010", "VR-024", "VR-025", "VR-026", "VR-027"],
    "QREL-sheet-3.jpg": ["VR-028", "VR-029", "VR-030", "VR-031", "VR-054"],
    "QREL-sheet-4.jpg": ["VR-050", "VR-041", "VR-043", "VR-044", "VR-045", "VR-022"],
    "QREL-sheet-5.jpg": ["VR-021", "VR-008", "VR-009", "VR-053"],
}
# relaties waarvan de eindpunten twee foto's bevatten ("A / B <-> C"): expliciete tegels
EXPLICIT_TILES = {
    "VR-041": ["MAP-003:OBS-MAP003-025", "MAP-004:OBS-MAP004-018", "MAP-009:REF-MAP009-003"],
    "VR-043": ["MAP-003:OBS-MAP003-019", "MAP-004:OBS-MAP004-014", "MAP-009:REF-MAP009-002"],
    "VR-044": ["MAP-003:OBS-MAP003-020", "MAP-004:OBS-MAP004-016", "MAP-009:REF-MAP009-005"],
    "VR-045": ["MAP-003:OBS-MAP003-011/012", "MAP-004:OBS-MAP004-006/007", "MAP-009:REF-MAP009-006"],
}
D_OBJECTS = ["OBS-MAP003-020", "OBS-MAP003-026", "OBS-MAP003-027", "OBS-MAP003-028", "OBS-MAP004-012", "OBS-MAP004-020", "OBS-MAP004-022"]


# --- meetkunde ----------------------------------------------------------------------------------------------------------------------------
def obs_index():
    idx = {}
    for pid, lst, pre in (("MAP-003", V.MAP003, "OBS-MAP003-"), ("MAP-004", V.MAP004, "OBS-MAP004-")):
        for o in lst:
            idx[f"{pre}{o[0]:03d}"] = (pid, V.D(*o[3]), o[1], o[2])
    return idx


def resolve(ref, ims, obs, boxes):
    """Eindpunt-tekst -> (foto, bbox in pixels) of None (gevel/plaat/buiten beeld)."""
    photo, _, rest = ref.partition(":")
    rest = rest.split(" (")[0].strip()
    if rest.startswith("OBS-"):
        parts = rest.replace("+", "/").split("/")
        first = parts[0]
        pre = first[:-3]
        ids = [first] + [pre + p[-3:] for p in parts[1:]]
        bs = [obs[i][1] for i in ids if i in obs]
        if not bs:
            return None
        return photo, (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
    if rest.startswith("FC-"):
        b = boxes.get(rest)
        if b is None:
            return None
        W, Hh = ims[photo].size
        return photo, (b[0] * W, b[1] * Hh, b[2] * W, b[3] * Hh)
    if rest.startswith("REF-"):
        for r in V.REFS:
            if r[0] == rest:
                s = V.REF_SCALE
                return photo, tuple(v * s for v in r[2])
    return None


def _crop(im, box, margin):
    w, h = box[2] - box[0], box[3] - box[1]
    return im.crop((int(max(0, box[0] - w * margin)), int(max(0, box[1] - h * margin)), int(min(im.width, box[2] + w * margin)), int(min(im.height, box[3] + h * margin))))


def _label(t, text):
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, min(t.width, 9 * len(text) + 12), 20], fill=(0, 0, 0))
    d.text((4, 3), text, font=B.FR(13), fill=(255, 220, 120))
    return t


def tile(ims, ref, obs, boxes, height=250, maxw=380):
    a = resolve(ref, ims, obs, boxes)
    if not a:
        return None
    pid, box = a
    t = _crop(ims[pid], box, 0.2)
    s = min(height / t.height, maxw / t.width)
    short = re.sub(r"OBS-MAP\d{3}-(\d{3})", r"OBS\1", re.sub(r"REF-MAP\d{3}-(\d{3})", r"REF\1", ref.split(" (")[0]))
    return _label(t.resize((max(1, round(t.width * s)), max(1, round(t.height * s))), Image.LANCZOS), short[:40])


def hstack(tiles, gap=10, bg=(255, 255, 255)):
    tiles = [t for t in tiles if t is not None]
    w = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
    c = Image.new("RGB", (w, max(t.height for t in tiles)), bg)
    x = 0
    for t in tiles:
        c.paste(t, (x, 0))
        x += t.width + gap
    return c


def vstack(rows, gap=8, bg=(255, 255, 255)):
    c = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows) + gap * (len(rows) - 1)), bg)
    y = 0
    for r in rows:
        c.paste(r, (0, y))
        y += r.height + gap
    return c


def relation_sheet(ims, ids, rels, obs, boxes):
    rows = []
    for rid in ids:
        r = rels[rid]
        refs = EXPLICIT_TILES.get(rid) or [r["left"], r["right"]]
        row = hstack([tile(ims, x, obs, boxes) for x in refs])
        head = Image.new("RGB", (max(row.width, 760), 22), (30, 30, 30))
        ImageDraw.Draw(head).text((4, 4), f'{rid}  {r["class"]}  (voorstel-sterkte {r["strength"]})  -> bewijs: {Q.REL_ASSESSMENT[rid][0]}', font=B.FR(13), fill=(255, 255, 255))
        rows.append((head, row))
    W = max(max(h.width, r.width) for h, r in rows)
    out = []
    for head, row in rows:
        h2 = Image.new("RGB", (W, head.height), (30, 30, 30))
        h2.paste(head, (0, 0))
        r2 = Image.new("RGB", (W, row.height), (255, 255, 255))
        r2.paste(row, (0, 0))
        out.append(vstack([h2, r2], gap=0))
    return vstack(out)


def make_figures(ims, rev):
    """Maakt de aanvullende bewijsfiguren (alleen echte uitsneden/overlays van de originele pixels). Retourneert {bestandsnaam: PIL-afbeelding}."""
    figs = {}
    obs = obs_index()
    boxes, _ = B.photo2_boxes()
    rels = {r[0]: {"rel_id": r[0], "left": r[2], "right": r[3], "class": r[4], "strength": r[5]} for r in V.RELATIONS}
    # A. scheidingen: ruwe uitsnede + dezelfde uitsnede met de beide kaders
    for sid, photo, a, b, _ in H.SEPARATIONS:
        lst = V.MAP003 if photo == "MAP-003" else V.MAP004
        oa = next(o for o in lst if o[0] == a)
        ob = next(o for o in lst if o[0] == b)
        A, Bb = V.D(*oa[3]), V.D(*ob[3])
        box = [min(A[0], Bb[0]) - 30, min(A[1], Bb[1]) - 30, max(A[2], Bb[2]) + 30, max(A[3], Bb[3]) + 30]
        raw = ims[photo].crop(tuple(int(x) for x in box))
        s = 1000 / raw.width
        raw = raw.resize((1000, round(raw.height * s)), Image.LANCZOS)
        ov = raw.copy()
        d = ImageDraw.Draw(ov)
        for bb, col in ((A, (255, 40, 40)), (Bb, (40, 220, 40))):
            d.rectangle([(bb[0] - box[0]) * s, (bb[1] - box[1]) * s, (bb[2] - box[0]) * s, (bb[3] - box[1]) * s], outline=col, width=3)
        figs[f"QSEP-{sid[-3:]}.jpg"] = vstack([_label(raw, f"{sid} ruwe uitsnede {photo} (geen annotatie)"), _label(ov, f"{sid} dezelfde uitsnede met de kaders OBS {a} (rood) en {b} (groen)")])
    # B. 009/010 in vier foto's
    b2 = boxes["FC-M2-006-A"], boxes["FC-M2-006-BC"]
    W2, H2 = ims["MAP-002"].size
    r2 = (min(b[0] for b in b2) * W2 - 30, min(b[1] for b in b2) * H2 - 30, max(b[2] for b in b2) * W2 + 30, max(b[3] for b in b2) * H2 + 30)
    ref4 = next(r for r in V.REFS if r[0] == "REF-MAP013-004")
    quad = [("MAP-002 (foto 2: FC-M2-006-A + -BC, bestaand besluit)", "MAP-002", r2), ("MAP-003 (OBS-009 + OBS-010)", "MAP-003", (700, 400, 1060, 590)),
            ("MAP-004 (OBS-005)", "MAP-004", (60, 400, 430, 590)),
            ("MAP-013 (REF-004, schuin; metselwerk tussen smal element en hoofdkozijn zichtbaar)", "MAP-013", tuple(v * V.REF_SCALE + d for v, d in zip(ref4[2], (-40, -40, 40, 40))))]
    cells = []
    for cap, pid, box in quad:
        t = ims[pid].crop(tuple(int(x) for x in box))
        cells.append(_label(t.resize((640, round(t.height * 640 / t.width)), Image.LANCZOS), cap))
    rowh = [max(cells[0].height, cells[1].height), max(cells[2].height, cells[3].height)]
    canvas = Image.new("RGB", (1290, sum(rowh) + 10), (24, 24, 24))
    canvas.paste(cells[0], (0, 0)); canvas.paste(cells[1], (650, 0)); canvas.paste(cells[2], (0, rowh[0] + 10)); canvas.paste(cells[3], (650, rowh[0] + 10))
    figs["Q009_010_four_photos.jpg"] = canvas
    # C. relatiebladen
    for name, ids in SHEETS.items():
        figs[name] = relation_sheet(ims, ids, rels, obs, boxes)
    # D. objecten: ruwe uitsnede + uitsnede met kader
    for oid in D_OBJECTS:
        pid, box, typ, vis = obs[oid]
        m = max(60, 0.6 * max(box[2] - box[0], box[3] - box[1]))
        cb = (max(0, box[0] - m), max(0, box[1] - m), min(ims[pid].width, box[2] + m), min(ims[pid].height, box[3] + m))
        raw = ims[pid].crop(tuple(int(x) for x in cb))
        s = min(560 / raw.width, 700 / raw.height)
        raw = raw.resize((max(1, round(raw.width * s)), max(1, round(raw.height * s))), Image.LANCZOS)
        ov = raw.copy()
        ImageDraw.Draw(ov).rectangle([(box[0] - cb[0]) * s, (box[1] - cb[1]) * s, (box[2] - cb[0]) * s, (box[3] - cb[1]) * s], outline=(255, 40, 40), width=2)
        figs[f"QD-{oid[4:]}.jpg"] = hstack([_label(raw, f"{oid} ruwe uitsnede"), _label(ov, f"{oid} met kader ({typ} {vis})")], bg=(24, 24, 24))
    QDIR.mkdir(parents=True, exist_ok=True)
    for n, im in figs.items():
        im.convert("RGB").save(QDIR / n, "JPEG", quality=82, optimize=True)
    return figs


# --- technische controle ------------------------------------------------------------------------------------------------------------------------
def technical_check(item, rev, all_ids, relmap):
    """Controleert een reviewpunt op technische juistheid (verwijzingen, kaders, hashes, keuzes). Zegt niets over visueel bewijs."""
    fails = []
    srcs = {s["photo_id"]: s for s in rev["sources"]}
    obs_ids = {o["obs_id"]: o for o in rev["observations"]}
    if all_ids.count(item["review_id"]) != 1:
        fails.append("review_id niet uniek")
    for o in item["observation_ids"]:
        if o not in obs_ids:
            fails.append(f"onbekende observatie {o}")
    for r in item["relation_ids"]:
        if r not in relmap:
            fails.append(f"onbekende relatie {r}")
    expected = H.CHOICES_OVERLAP if item["review_type"] == "OVERLAP_RELATION" else H.CHOICES_STD
    if set(item["choices"]) != set(expected) or item["claude_proposal"] not in item["choices"]:
        fails.append("keuzes/voorstel ongeldig")
    for e in item["evidence_refs"]:
        if e["type"] == "original_crop":
            s = srcs[e["photo_id"]]
            if e["sha256"] != s["sha256_register"] or e["sha256_verified"] is not True:
                fails.append("SHA256 komt niet overeen met register")
            x0, y0, x1, y1 = e["region_px"]
            if not (0 <= x0 < x1 <= s["width_px"] and 0 <= y0 < y1 <= s["height_px"]):
                fails.append("kader buiten de foto")
            if e.get("observation_id") and e["observation_id"] in obs_ids and list(obs_ids[e["observation_id"]]["bbox_px"]) != list(e["region_px"]) and item["review_type"] != "SEPARATION":
                fails.append("kader wijkt af van de observatie")
        if e["type"] == "report_figure" and not (B.OUT / e["file"]).exists():
            fails.append(f"figuur ontbreekt {e['file']}")
    if not item.get("ref_hash") or item["ref_hash"] != H.ref_hash(item):
        fails.append("ref_hash ontbreekt of klopt niet")
    if item["review_type"] == "OVERLAP_RELATION" and "relation_semantics" not in item:
        fails.append("relatiesemantiek ontbreekt")
    return fails


# --- kwaliteitsrecords per P1-punt ---------------------------------------------------------------------------------------------------------------
def load_feature_evidence():
    d = json.loads(EVIDENCE_JSON.read_text())
    return {e["relation_id"]: e for e in d["relations"]}


def evidence_ref_for_relation(vr):
    for name, ids in SHEETS.items():
        if vr in ids:
            return name
    return {"VR-001": "D1_MAP-002_vs_MAP-003_ground_wall_288.jpg", "VR-020": "E_plates_MAP-003_MAP-004.jpg"}[vr]


def feature_summary(e):
    if not e or e.get("method", "").startswith("NOT_"):
        return None
    out = {"inliers": e.get("inliers"), "good_matches": e.get("good_matches")}
    for k in ("rank_of_partner_among_MAP004", "rank_of_partner_among_MAP003", "best_other_inliers_row", "best_other_inliers_col"):
        if k in e:
            out[k] = e[k]
    return out


def quality_records(items, rev):
    """Per P1-reviewpunt: huidige classificatie, kwaliteitsbevinding, bewijsverwijzing, vervolgstap, status."""
    fe = load_feature_evidence()
    all_ids = [i["review_id"] for i in items]
    relmap = {r["rel_id"]: r for r in rev["relations"]}
    obsmap = {o["obs_id"]: o for o in rev["observations"]}
    recs = []
    for it in items:
        if it["priority"] != "P1":
            continue
        rid = it["review_id"]
        tech = technical_check(it, rev, all_ids, relmap)
        rec = {"review_id": rid, "review_type": it["review_type"], "technically_correct": not tech, "technical_failures": tech,
               "claude_proposal_v1_0_0": it.get("claude_proposal_v1", it["claude_proposal"]), "claude_proposal_now": it["claude_proposal"]}
        if it["review_type"] == "OBSERVATION":
            o = obsmap[it["observation_ids"][0]]
            rec["current_classification"] = f'{o["observation_type"]} {o["visibility"]} (onzekerheid {o["uncertainty"]})'
            f = Q.OBS_FINDINGS[rid]
            rec.update(finding=f[0], visual_evidence=f[1], next_step=f[2], quality_status=f[3], extra_evidence_needed=f[4])
            if o["obs_id"] in Q.OBJ_MATRIX:
                rec["six_questions"] = {k: {"answer": v[0], "note": v[1]} for k, v in Q.OBJ_MATRIX[o["obs_id"]].items()}
        elif it["review_type"] == "OVERLAP_RELATION":
            vr = it["relation_ids"][0]
            r = relmap[vr]
            cls, basis, note = Q.REL_ASSESSMENT[vr]
            rt = it["relation_semantics"]["relation_type"]
            rec["current_classification"] = f'{r["class"]} (sterkte {r["strength"]}); relatietype {rt}'
            rec["relation_type"] = rt
            rec["evidence_class"] = cls
            rec["evidence_basis"] = basis
            rec["feature_match"] = feature_summary(fe.get(vr))
            rec.update(finding=f"{Q.CLASS_NL[cls]}: {note}", visual_evidence=evidence_ref_for_relation(vr), next_step=Q.REL_NEXT[cls],
                       quality_status=Q.relation_status(cls), extra_evidence_needed=Q.REL_EXTRA[cls])
        elif it["review_type"] == "SEPARATION":
            res = Q.SEP_RESULTS[rid]
            rec["current_classification"] = "scheiding door metselwerk (voorstel CONFIRM)"
            rec["separation_checks"] = {"pier_visible": res[0], "separate_openings": res[1], "bbox_correct": res[2], "evidence_sufficient": res[3], "note": res[4]}
            rec.update(finding=f"{Q.SEP_FINDING} {res[4]}", visual_evidence=f"QSEP-{rid[-3:]}.jpg", next_step="Mens bevestigt (telregel PCD-00004 ongewijzigd).",
                       quality_status="VISUALLY_SUPPORTED", extra_evidence_needed="Nee")
        else:
            f = Q.HQ_FINDINGS[rid]
            rec["current_classification"] = f'bestaande vraag ({it["title"]})'
            rec.update(finding=f[0], visual_evidence=f[1], next_step=f[2], quality_status=f[3], extra_evidence_needed=f[4])
        if rid in Q.PROPOSAL_CORRECTIONS:
            rec["proposal_correction"] = dict(zip(("from", "to", "reason"), Q.PROPOSAL_CORRECTIONS[rid]))
        assert rec["quality_status"] in Q.QUALITY_STATUSES, rid
        recs.append(rec)
    return recs


# --- rapport -----------------------------------------------------------------------------------------------------------------------------------
def md_escape(t):
    return str(t).replace("|", "/").replace("\n", " ")


def write_reports(items, rev, recs, pack_version):
    n = len(recs)
    tech_ok = sum(r["technically_correct"] for r in recs)
    by_status = {s: sum(r["quality_status"] == s for r in recs) for s in Q.QUALITY_STATUSES}
    rel = [r for r in recs if r["review_type"] == "OVERLAP_RELATION"]
    by_class = {c: [r["review_id"][-6:] for r in rel if r["evidence_class"] == c] for c in Q.EVIDENCE_CLASSES}
    L = []
    A = L.append
    A("# Maldenhof P1 Visual Review: Quality Corrections v1")
    A("")
    A(f"Pakketversie: `{pack_version}` (Human Visual Decision Pack, PR #41). Status: **aanvullende kwaliteitscontrole, geen menselijke goedkeuring**. Alle 48 APP-besluiten blijven OPEN; er ontstaan geen instances, pandkoppelingen, unieke totalen, maten of kosten; de bevroren foto-2-telling (11 kozijnopeningen, 1 buitendeur, 9 FULL, 2 PARTIAL), de 50 observaties en de 43 relaties zijn ongewijzigd.")
    A("")
    A("> **Een technisch geldige reviewkaart is niet automatisch een visueel bewezen object.** Technische juistheid (ID, verwijzing, kader, hash, keuzes) en visueel bewijs zijn hier gescheiden gemeten.")
    A("")
    A("## 1. Hoe is gecontroleerd")
    A("")
    A("- De bevindingen van de externe review (ChatGPT) zijn als **invoer** gebruikt en **niet** als waarheid overgenomen: elk punt is opnieuw gecontroleerd op de geverifieerde originele pixels (SHA256 uit het foto-archief-register; MAP-003/004 2048x1536).")
    A("- Per punt zijn de ruwe uitsneden bekeken zonder annotatie; kaders zijn alleen als controle eroverheen gelegd (figuren `p1_quality_review/QSEP-*.jpg`, `QD-*.jpg`).")
    A("- Als hulpmiddel is een deterministische kenmerkmatch gebruikt (SIFT, ratio 0.75, RANSAC; `scripts/p1_visual_quality_evidence.py`, resultaten in `p1_quality_review/p1_feature_match_evidence_v1.json`). Niet-partners halen tot 24 inliers: het getal beslist nooit alleen, het ondersteunt de visuele beoordeling. "
      "De woningen zijn identiek (herhalingsrisico): kenmerkmatches tussen buurwoningen kunnen even hoog zijn als tussen dezelfde woning; daarom zijn plaatnummers en onderscheidende voorwerpen (gordijn, flessen, folie, open vleugels) als anker gebruikt.")
    A(f"- Classificatieregel overlapbewijs: {Q.CLASS_RULE}")
    A("")
    A("## 2. Samenvatting (antwoorden op de eindvragen)")
    A("")
    A(f"1. **Technisch correct:** {tech_ok} van de {n} P1-reviewpunten (alle verwijzingen, kaders, SHA256-hashes, keuzes en bronverwijzing-hashes kloppen).")
    A(f"2. **Onafhankelijk visueel bevestigd:** alle zes de penanten (RV-SEP-001..006), de configuratie 009+010 in vier foto's, {len(by_class['STRONG_VISUAL_SUPPORT'])} van de {len(rel)} P1-relaties met sterk bewijs (STRONG), plus alle 11 plaatlezingen. Zie sectie 3 t/m 6.")
    A(f"3. **Nog onzeker:** relaties met matig bewijs: {', '.join('VR-' + x.split('VR-')[-1] for x in by_class['MODERATE_VISUAL_SUPPORT'])}; onvoldoende bewijs: {', '.join('VR-' + x.split('VR-')[-1] for x in by_class['INSUFFICIENT_EVIDENCE'])}; observaties MAP003-020/-026/-027/-028 en MAP004-012/-022 (zie matrix, sectie 6).")
    A("4. **Gevelsectie-overlap en objectoverlap zijn technisch gescheiden** (sectie 7): relatietype in de reviewdata, aparte betekenis van SAME in de export (`SAME_FACADE_SECTION` versus `SAME_PHYSICAL_OBJECT_CANDIDATE`), `same_physical_frame_implied: false` bij gevelrelaties en geen pandkoppeling in beide gevallen.")
    A("5. **JSON-import is veilig gemaakt** (sectie 8): volledige validatie vooraf, bij een fout verandert niets, keuze tussen volledig vervangen en bewust gedeeltelijk samenvoegen.")
    A(f"6. **Kwaliteitsstatus P1:** {', '.join(f'{k} {v}' for k, v in by_status.items())}.")
    A("")
    A("## 3. A. Scheidingen RV-SEP-001..006")
    A("")
    A("| Review-ID | Penant zichtbaar? | Afzonderlijke openingen? | Kaders correct? | Bewijs voldoende? | Bewijsverwijzing | Opmerking |")
    A("|---|---|---|---|---|---|---|")
    for sid, (a, b, c, d, note) in Q.SEP_RESULTS.items():
        A(f"| {sid} | {'ja' if a else 'nee'} | {'ja' if b else 'nee'} | {'ja' if c else 'nee'} | {'ja' if d else 'nee'} | `QSEP-{sid[-3:]}.jpg` | {md_escape(note)} |")
    A("")
    A(Q.SEP_NOTE)
    A("")
    A("De telregel (een meervoudig kozijn of kozijnstijl scheidt niet; zichtbaar metselwerk tussen kozijnen scheidt wel) is **niet gewijzigd**.")
    A("")
    A("## 4. B. OBS-MAP003-009 versus OBS-MAP003-010")
    A("")
    A("Figuur: `p1_quality_review/Q009_010_four_photos.jpg` (MAP-002, MAP-003, MAP-004, MAP-013).")
    A("")
    for t in Q.B009_010:
        A(f"- {t}")
    A("")
    A(Q.B009_CONCLUSION)
    A("")
    A("## 5. C. Overlapbewijs per relatie (P1)")
    A("")
    A("Dit zijn **bewijsbeoordelingen** en geen SAME-besluiten; er is niets samengevoegd. Relatietype: `FACADE_SECTION` (alleen dezelfde gevelsectie) of `PHYSICAL_OBJECT` (kandidaat hetzelfde fysieke object).")
    A("")
    A("| Relatie | Type | Eerder (sterkte) | Bewijsklasse | Grondslag | Kenmerkmatch (inliers / rang) | Toelichting | Figuur |")
    A("|---|---|---|---|---|---|---|---|")
    relmap = {r["rel_id"]: r for r in rev["relations"]}
    for r in rel:
        vr = r["review_id"].replace("RV-REL-", "")
        fm = r["feature_match"]
        fms = "n.v.t." if not fm else f'{fm["inliers"]}' + (f' / rang {fm["rank_of_partner_among_MAP004"]}/{fm["rank_of_partner_among_MAP003"]}' if "rank_of_partner_among_MAP004" in fm else "")
        A(f'| {vr} | {r["relation_type"]} | {relmap[vr]["class"]} ({relmap[vr]["strength"]}) | **{r["evidence_class"]}** | {", ".join(r["evidence_basis"])} | {fms} | {md_escape(r["finding"].split(": ", 1)[1])} | `{r["visual_evidence"]}` |')
    A("")
    A(f"Verdeling: STRONG {len(by_class['STRONG_VISUAL_SUPPORT'])}, MODERATE {len(by_class['MODERATE_VISUAL_SUPPORT'])}, INSUFFICIENT {len(by_class['INSUFFICIENT_EVIDENCE'])} (totaal {len(rel)} P1-relaties).")
    A("")
    A("## 6. D. Objecten met een bijzonder punt: zes afzonderlijke vragen")
    A("")
    A("Zichtbaarheid is niet een enkele status: bestaan, type, volledigheid, afzonderlijke herkenbaarheid, meetbaarheid en pandkoppeling zijn afzonderlijk beantwoord.")
    A("")
    qn = Q.Q6
    A("| Observatie | " + " | ".join(Q.Q6_NL[k] for k in qn) + " | Figuur |")
    A("|---|" + "---|" * (len(qn) + 1))
    for oid, m in Q.OBJ_MATRIX.items():
        A(f"| {oid} | " + " | ".join(f"**{m[k][0]}** {md_escape(m[k][1])}" for k in qn) + f" | `QD-{oid[4:]}.jpg` |")
    A("")
    A("## 7. Gevelsectie-overlap versus objectoverlap")
    A("")
    A("| Relatietype | Relaties | Betekenis van SAME | Impliceert |")
    A("|---|---|---|---|")
    A(f"| FACADE_SECTION | VR-001, VR-020 | {H.MEANING_TEXT[H.FACADE_SECTION]} | `same_physical_frame: false`, geen pandkoppeling, geen merge, geen instance |")
    A(f"| PHYSICAL_OBJECT | alle overige relaties | {H.MEANING_TEXT[H.PHYSICAL_OBJECT]} | geen pandkoppeling, geen merge, geen instance |")
    A("")
    A("`SAME_FACADE_SECTION` wordt nooit als `SAME_PHYSICAL_FRAME` geinterpreteerd: de export zet de betekenis per relatietype (`decision_meaning`) en de verwerkingsregels (`implies`) mee. Een gevelbesluit levert dus geen enkel kozijnbewijs op. Bij relaties met een groep (bijvoorbeeld 009+010 tegenover 005) betekent SAME niet dat de afzonderlijke observaties dezelfde of verschillende objecten zijn.")
    A("")
    A("## 8. JSON-import (gecorrigeerd)")
    A("")
    A("- Exportformaat v2 (`maldenhof_visual_decision_export_v2`): per reviewpunt `human` (beslissing, bron, opmerking, betekenis) strikt gescheiden van `claude_non_binding` (voorstel, bewijsbeoordeling); een bronverwijzing-hash (`source_ref_hash`) bindt elk punt aan zijn bronnen in dit pakket.")
    A("- Import valideert eerst het hele bestand: formaat, `pack_version`, `review_package_version`, scope, review-ID's (onbekend of dubbel wordt geweigerd), keuzewaarden, consistentie tussen keuze en `decision_source`, relatiebetekenis en bronverwijzing-hash. Bij een fout wordt de import volledig afgewezen en verandert er niets aan de keuzes in de browser.")
    A("- Daarna kiest de gebruiker: **volledig vervangen** (alle niet in het bestand genoemde punten gaan naar OPEN en oude opmerkingen verdwijnen) of **bewust gedeeltelijk samenvoegen** (alleen menselijke keuzes en opmerkingen uit het bestand worden toegepast; OPEN-regels overschrijven niets).")
    A("- Een export met `export_scope.kind = FULL` moet alle reviewpunten bevatten; deelexports (`PARTIAL`: alleen beoordeelde punten, P1, P2 of P3) zijn mogelijk. Een oud v1-exportbestand (pakket v1.0.0) wordt in een apart oudere-formaatpad geladen; beslissingen bij de gevelrelaties VR-001/VR-020 worden daarbij niet overgenomen omdat de betekenis van SAME is verduidelijkt.")
    A("- Claude-voorstellen komen nooit in de beslissingen terecht: bij import wordt `claude_non_binding` genegeerd; een bestand met een keuze zonder `decision_source: HUMAN` wordt geweigerd.")
    A("- Getest in Chromium (`tests/test_human_visual_decision_pack.py`): volledige rondreis, onvolledig bestand met vervangen, deelimport met samenvoegen, ongeldige bestanden (afwijkende versie, onbekend of dubbel ID, ongeldige keuze, verkeerde bronhash, inconsistente bron) laten de staat ongewijzigd, resetten, opnieuw exporteren en deelexports.")
    A("")
    A("## 9. Alle 54 P1-reviewpunten")
    A("")
    A("Kwaliteitsstatus: `TECHNICALLY_VALIDATED` (technisch correct, geen visuele claim of regel-/procesvraag), `VISUALLY_SUPPORTED` (opnieuw visueel bevestigd), `NEEDS_MANUAL_REVIEW` (dubbelzinnig, mens beslist), `NEEDS_BETTER_PHOTO`.")
    A("")
    A("| # | Review-ID | Technisch | Huidige voorlopige classificatie | Nieuwe kwaliteitsbevinding | Visueel bewijs | Aanbevolen volgende stap | Kwaliteitsstatus | Extra bewijs nodig? |")
    A("|---|---|---|---|---|---|---|---|---|")
    for k, r in enumerate(recs, 1):
        corr = ""
        if "proposal_correction" in r:
            c = r["proposal_correction"]
            corr = f' **Voorstel gecorrigeerd: {c["from"]} -> {c["to"]}** ({md_escape(c["reason"])})'
        A(f'| {k} | {r["review_id"]} | {"ja" if r["technically_correct"] else "NEE"} | {md_escape(r["current_classification"])}; voorstel v1: {r["claude_proposal_v1_0_0"]} | {md_escape(r["finding"])}{corr} | `{r["visual_evidence"]}` | {md_escape(r["next_step"])} | {r["quality_status"]} | {md_escape(r["extra_evidence_needed"])} |')
    A("")
    A("## 10. Gecorrigeerde voorstellen van Claude (apart vastgelegd voor review)")
    A("")
    A("De 50 observaties en 43 relaties zelf zijn niet gewijzigd. Alleen de niet-bindende voorstellen in het beslispakket zijn aangepast; de oude waarde blijft zichtbaar in de HTML en in dit rapport. Een voorstel is nooit voorgekozen en nooit een besluit.")
    A("")
    A("| Review-ID | Was | Wordt | Reden |")
    A("|---|---|---|---|")
    for k, (a, b, why) in Q.PROPOSAL_CORRECTIONS.items():
        A(f"| {k} | {a} | {b} | {md_escape(why)} |")
    A("")
    A("Overige correcties in de notities (geen wijziging van de brondata): OBS-MAP003-009 heeft zichtbaarheid FULL maar de rechterrand wordt door de open vleugel van 010 overlapt; de kleur `rood` bij OBS-MAP003-026/-027 is op MAP-003 niet te verifieren (alleen op MAP-004 is de deur donkerrood); VR-022 koppelt de te donkere 027 aan MAP004-020, terwijl 026 (bij plaat 286) in uitzicht op MAP004-020 lijkt (herhalingsrisico).")
    A("")
    A("## 11. Onveranderd en niet gedaan")
    A("")
    A("- 48 APP-besluiten OPEN; geen menselijke besluiten genomen of voorgekozen.")
    A("- Geen instances, geen BAG-pandkoppelingen, geen unieke totalen, geen kozijn- of onderhoudskosten, geen herhalingsvermenigvuldigers, geen hoeveelheden.")
    A("- Bevroren foto 2, bestaande instance-stores, foto-/KG-/BAG-data en de scope-guard-baseline ongewijzigd.")
    A("- PR #41 is niet gemerged.")
    OUT_MD.write_text("\n".join(L) + "\n")
    doc = {"report": "maldenhof_p1_visual_quality_review_v1", "pack_version": pack_version, "status": "QUALITY_CHECK_NOT_A_HUMAN_APPROVAL",
           "counts": {"p1_review_points": n, "technically_correct": tech_ok, "by_quality_status": by_status,
                      "relations_by_evidence_class": {k: len(v) for k, v in by_class.items()}},
           "effects": {"instances_created": 0, "bag_links_created": 0, "building_totals": None, "costs": None, "app_decisions_open": 48},
           "feature_match_noise_note": "Niet-partners halen tot 24 inliers; getal beslist nooit alleen.",
           "proposal_corrections": {k: dict(zip(("from", "to", "reason"), v)) for k, v in Q.PROPOSAL_CORRECTIONS.items()},
           "records": recs}
    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return doc
