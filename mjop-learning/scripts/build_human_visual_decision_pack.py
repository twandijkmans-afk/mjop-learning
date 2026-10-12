#!/usr/bin/env python3
"""Maldenhof Human Visual Decision Pack v1.1 (voortbouwend op Visual Photo Review MAP-003 & MAP-004; P1 Quality Corrections v1).

Bouwt een zelfstandig HTML-beoordelingspakket (geen externe scripts of netwerk; afbeeldingen als data-URI) waarmee een mens de voorlopige
observaties en de 43 kandidaat-overlaprelaties kan beoordelen, met prioriteiten (P1/P2/P3), een beslisformulier (keuzerondjes, opmerking, OPEN
terugzetten) en een JSON-export van het voorlopige reviewresultaat. Hergebruikt de bestaande observaties, bboxen en relaties ongewijzigd.

Uitsluitend echte uitsneden/vergrotingen/annotaties van de originele pixels. Geen instances, pandkoppelingen, totalen, maten of kosten. De export
activeert niets en past geen APP-besluit aan; een voorstel van Claude wordt nooit als menselijk besluit geexporteerd.

Gebruik: python3 scripts/build_human_visual_decision_pack.py [--zip PAD]
"""
import argparse
import base64
import html
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_visual_photo_review_map003_map004 as B  # noqa: E402
import build_p1_quality_review as QR  # noqa: E402
import human_decision_pack_data as H  # noqa: E402
import p1_quality_review_data as Q  # noqa: E402
import visual_review_map003_map004_data as V  # noqa: E402

ROOT = B.ROOT
REVIEW_DIR = B.OUT
PACK_DIR = REVIEW_DIR / "decision_pack"
OUT_HTML = PACK_DIR / "maldenhof_human_visual_decision_pack_v1.html"
OUT_INDEX = PACK_DIR / "maldenhof_human_visual_decision_pack_v1_index.json"
TEMPLATE = Path(__file__).resolve().parent / "human_decision_pack_template.html"
PACK_VERSION = "human_visual_decision_pack_v1.1.0"
LEGACY_PACK_VERSION = "human_visual_decision_pack_v1.0.0"
E = html.escape
TYPE_NL = {"WINDOW_OPENING": "raam/kozijn", "EXTERIOR_DOOR": "buitendeur", "ROOF_WINDOW": "dakraam", "DORMER_OPENING": "dakkapel", "UNKNOWN_OPENING": "onbepaald",
           "WINDOW_DOOR_COMBINATION": "raam-deurcombinatie"}


def P(rid, proposal):
    """Voorstel van Claude na de kwaliteitscontrole (apart vastgelegde correctie); controleert dat de oude waarde klopt."""
    c = Q.PROPOSAL_CORRECTIONS.get(rid)
    if not c:
        return proposal
    assert c[0] == proposal, (rid, c, proposal)
    return c[1]


def jpeg_uri(im, q=80, max_w=None):
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def img_tag(im, cls, alt, q=80, max_w=None):
    return f'<img class="{cls}" alt="{E(alt)}" src="{jpeg_uri(im, q, max_w)}">'


# --- uitsneden -----------------------------------------------------------------------------------------------------------------------
def obs_crop(ims, o, target_w, pad_min=40):
    im = ims[o["photo_id"]]
    x0, y0, x1, y1 = o["bbox_px"]
    pad = max(pad_min, round(0.5 * max(x1 - x0, y1 - y0)))
    box = [max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)]
    s = target_w / (box[2] - box[0])
    t = im.crop(tuple(box)).resize((round((box[2] - box[0]) * s), round((box[3] - box[1]) * s)), Image.LANCZOS)
    d = ImageDraw.Draw(t)
    lst = V.MAP003 if o["photo_id"] == "MAP-003" else V.MAP004
    tf = B.crop_tf(box, s)
    this = int(o["obs_id"][-3:])
    for n, typ, vis, b, *_ in lst:
        bb = tf(V.D(*b))
        if bb is None:
            continue
        c = B.COL[typ]
        if n == this:
            d.rectangle(bb, outline=(255, 255, 255), width=6)
            d.rectangle(bb, outline=c, width=3)
        else:
            B.dashed(d, bb, c, 2)
        B.text(d, (bb[0] + 2, max(bb[1] - 22, 0)), str(n), c, 20)
    for nr, b in B.plates_of(o["photo_id"]):
        bb = tf(V.D(*b))
        if bb:
            d.rectangle(bb, outline=B.PLATE_COL, width=3)
    return t


def ref_crop(ims, ref, target_w):
    rid, photo, bx, desc = ref
    im = ims[photo]
    x0, y0, x1, y1 = [round(v * V.REF_SCALE) for v in bx]
    pad = round(0.6 * max(x1 - x0, y1 - y0))
    box = [max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)]
    s = target_w / (box[2] - box[0])
    t = im.crop(tuple(box)).resize((round((box[2] - box[0]) * s), round((box[3] - box[1]) * s)), Image.LANCZOS)
    d = ImageDraw.Draw(t)
    tf = B.crop_tf(box, s)
    for r2 in V.REFS:
        if r2[1] != photo:
            continue
        bb = tf([round(v * V.REF_SCALE) for v in r2[2]])
        if bb:
            d.rectangle(bb, outline=(255, 140, 0), width=3)
            B.text(d, (bb[0] + 2, max(bb[1] - 20, 0)), r2[0].replace("REF-", ""), (255, 140, 0), 16)
    d.rectangle([0, 0, 360, 26], fill=(0, 0, 0))
    d.text((4, 3), f"{photo} (referentiegebied, geen observatie)", font=B.FR(15), fill=(255, 180, 90))
    return t


def panel_cell(ims, spec, target_w):
    photo, kind, val = spec
    if kind == "ref":
        ref = next(r for r in V.REFS if r[0] == val)
        return ref_crop(ims, ref, target_w)
    box = B.D(*val)
    s = target_w / (box[2] - box[0])
    if photo == "MAP-002":
        return B.tile_photo2(photo, ims[photo], box, s)
    return B.tile_obs(photo, ims[photo], box, s)


def compose(cells, cols=2, gap=14):
    cw = max(c.width for c in cells)
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    rh = [max(c.height for c in r) for r in rows]
    canvas = Image.new("RGB", (cols * cw + gap * (cols - 1), sum(rh) + gap * (len(rows) - 1)), (24, 24, 24))
    y = 0
    for r, h in zip(rows, rh):
        x = 0
        for c in r:
            canvas.paste(c, (x, y))
            x += cw + gap
        y += h + gap
    return canvas


# --- gegevens --------------------------------------------------------------------------------------------------------------------------
def load_review():
    return json.loads(B.OUT_JSON.read_text())


def source_ref(rev, photo_id, region=None, kind="original_crop", extra=None):
    s = next(x for x in rev["sources"] if x["photo_id"] == photo_id)
    d = {"type": kind, "photo_id": photo_id, "file": s["file"], "sha256": s["sha256_register"], "sha256_verified": s["sha256_verified"]}
    if region:
        d["region_px"] = region
    if extra:
        d.update(extra)
    return d


def photo2_px(ims):
    boxes, fi = B.photo2_boxes()
    im = ims["MAP-002"]
    return {k: [round(v[0] * im.width), round(v[1] * im.height), round(v[2] * im.width), round(v[3] * im.height)] for k, v in boxes.items()}, fi


def side_refs(rev, text, p2px):
    refs = []
    for m in re.findall(r"OBS-MAP00[34]-\d{3}", text):
        o = next(x for x in rev["observations"] if x["obs_id"] == m)
        refs.append(source_ref(rev, o["photo_id"], o["bbox_px"], extra={"observation_id": m}))
    for m in re.findall(r"REF-MAP\d{3}-\d{3}", text):
        r = next(x for x in rev["references"] if x["ref_id"] == m)
        refs.append(source_ref(rev, r["photo_id"], r["bbox_px"], extra={"reference_id": m}))
    for m in re.findall(r"FC-M2-\d{3}(?:-[A-Z]+)?", text):
        if m in p2px:
            refs.append(source_ref(rev, "MAP-002", p2px[m], extra={"frozen_photo2_candidate": m}))
    return refs


def radio_block(rid, choices, proposal, rtype=None):
    out = ['<fieldset class="choices" aria-label="Beslissing">']
    out.append(f'<label title="Nog niets gekozen"><input type="radio" name="d-{E(rid)}" value="OPEN" checked> <b>OPEN</b></label>')
    for c in choices:
        help_ = H.CHOICE_HELP.get(c, c)
        extra = ""
        if rtype:                                  # overlap: de betekenis van SAME/DIFFERENT hangt van het relatietype af
            meaning = H.MEANING[rtype][c]
            help_ = {"SAME_FACADE_SECTION": "Dezelfde gevelsectie. Dit zegt niets over hetzelfde kozijn en bewijst geen pandkoppeling.",
                     "DIFFERENT_FACADE_SECTION": "Verschillende gevelsecties.",
                     "SAME_PHYSICAL_OBJECT_CANDIDATE": "De observaties tonen vermoedelijk hetzelfde fysieke object (kandidaat; geen merge, geen pandkoppeling).",
                     "DIFFERENT_PHYSICAL_OBJECTS": "Verschillende fysieke objecten."}.get(meaning, help_)
            if meaning != c:
                extra = f' <span class="meaning">= {meaning}</span>'
        out.append(f'<label title="{E(help_)}"><input type="radio" name="d-{E(rid)}" value="{c}"> {c}{extra}</label>')
    out.append("</fieldset>")
    return "".join(out)


def item_shell(rid, priority, inner, extra_cls=""):
    return f'<article class="review-item open {extra_cls}" id="item-{E(rid)}" data-id="{E(rid)}" data-priority="{priority}">{inner}</article>'


def controls(rid, choices, proposal, nonbinding_label="Voorstel Claude (niet-bindend)", rtype=None):
    corr = Q.PROPOSAL_CORRECTIONS.get(rid)
    note = (f' <span class="chip corr">gecorrigeerd t.o.v. v1.0.0: was {corr[0]}</span>' if corr else "")
    return (f'<div class="proposal">{nonbinding_label}: <b>{E(proposal)}</b>{note} &mdash; dit is geen besluit; er is niets voorgekozen.</div>' + f"<!--QA:{rid}-->"
            + radio_block(rid, choices, proposal, rtype)
            + f'<button class="sec small" data-reset="{E(rid)}" type="button">OPEN zetten</button>'
            + f'<textarea class="cmt" id="c-{E(rid)}" placeholder="Opmerking (optioneel)" aria-label="Opmerking bij {E(rid)}"></textarea>')


def build(args):
    ims, ver = B.load_sources(args.zip)
    rev = load_review()
    obs = {o["obs_id"]: o for o in rev["observations"]}
    rels = {r["rel_id"]: r for r in rev["relations"]}
    p2px, fi = photo2_px(ims)
    items = []
    body = []

    def add_item(review_id, review_type, priority, title, photos, obs_ids, rel_ids, app_links, proposal, choices, evidence, semantics=None):
        it = {"review_id": review_id, "review_type": review_type, "priority": priority, "title": title, "photo_ids": photos,
              "observation_ids": obs_ids, "relation_ids": rel_ids, "app_links": app_links, "claude_proposal": proposal, "choices": choices,
              "evidence_refs": evidence}
        if semantics:
            it["relation_semantics"] = semantics
        items.append(it)

    # ------------------------------------------------------------------ Sectie A: overzicht per foto + observatie-items
    special = set(H.SPECIAL_THEMES)
    in_c = {k for k in special}
    body.append("<h1>Maldenhof Human Visual Decision Pack v1.1</h1>")
    body.append('<div class="note warn"><b>Alleen voor menselijke beoordeling.</b> Alle beslissingen staan op OPEN. Dit pakket maakt geen instances, voegt niets samen, koppelt geen kozijnen aan een pand en berekent geen totalen, maten of kosten. '
                'Voorstellen van Claude zijn niet-bindend en staan nooit voorgekozen. Alle 48 APP-besluiten blijven OPEN en onveranderd; de bevroren foto-2-telling (11 kozijnopeningen, 1 buitendeur, 9 FULL, 2 PARTIAL) blijft ongewijzigd.</div>')
    body.append("__HOWTO__")
    body.append("__PRIO_TABLE__")
    body.append('<h2 id="A">A. Overzicht per foto</h2>')
    body.append('<p>Kaders: <span class="chip t-WINDOW_OPENING">WINDOW_OPENING</span><span class="chip t-EXTERIOR_DOOR">EXTERIOR_DOOR</span><span class="chip t-ROOF_WINDOW">ROOF_WINDOW</span>'
                '<span class="chip t-DORMER_OPENING">DORMER_OPENING</span><span class="chip t-UNKNOWN_OPENING">UNKNOWN_OPENING</span> &mdash; doorgetrokken kader = FULL, gestippeld = PARTIAL/verborgen, magenta = huisnummerplaat. '
                'Een observatie is een zichtbare opening en <b>geen</b> geteld kozijn.</p>')
    for photo, fig in (("MAP-003", "A"), ("MAP-004", "B")):
        s = next(x for x in ver.values() if x["photo_id"] == photo)
        body.append(f'<h3>{photo} &mdash; {E(s["file"])} (SHA256 {s["sha256_register"][:16]}&hellip;, geverifieerd)</h3>')
        body.append(img_tag(Image.open(REVIEW_DIR / B.IMG[fig]), "fig", f"Overzicht {photo} met genummerde observaties", 78, 2000))
        photo_obs = [o for o in rev["observations"] if o["photo_id"] == photo]
        # tabel met classificatie en zichtbaarheid van alle observaties
        rows = ["<table><tr><th>Observatie</th><th>Type</th><th>Zichtbaarheid</th><th>Onzekerheid</th><th>Positie</th><th>Toelichting</th><th>Beslissing</th></tr>"]
        for o in photo_obs:
            where = "sectie C" if o["obs_id"] in in_c else "hieronder"
            rows.append(f'<tr><td><b>{o["obs_id"]}</b></td><td><span class="chip t-{o["observation_type"]}">{o["observation_type"]}</span> {TYPE_NL[o["observation_type"]]}</td>'
                        f'<td>{o["visibility"]}</td><td>{o["uncertainty"]}</td><td>{E(o["position_hint"])}</td><td>{E(o["note"])}</td><td><a href="#item-RV-OBS-{o["obs_id"][4:]}">{where}</a></td></tr>')
        rows.append("</table>")
        body.append("".join(rows))
    body.append("<h3>Beoordeel observaties (alle observaties die niet in sectie C staan)</h3>")
    body.append('<p class="evid">Per observatie: de originele uitsnede met de eigen kaders. CONFIRM betekent: de observatie (type, zichtbaarheid, kader) klopt als voorlopige zichtbare opening. Het is geen telling of instance.</p>')
    special_ids = []
    for o in rev["observations"]:
        rid = "RV-OBS-" + o["obs_id"][4:]
        prio = H.observation_priority(o, {"OBS-MAP003-009", "OBS-MAP003-010"})
        proposal = P(rid, H.proposal_for_observation(o))
        evid = [source_ref(rev, o["photo_id"], o["bbox_px"], extra={"observation_id": o["obs_id"]}),
                {"type": "report_figure", "file": B.IMG["A" if o["photo_id"] == "MAP-003" else "B"]}]
        add_item(rid, "OBSERVATION", prio, f'{o["obs_id"]} {o["observation_type"]} {o["visibility"]}', [o["photo_id"]], [o["obs_id"]], [], [],
                 proposal, H.CHOICES_STD, evid)
        if o["obs_id"] in in_c:
            special_ids.append(o["obs_id"])
            continue
        crop = obs_crop(ims, o, 420)
        inner = (img_tag(crop, "thumb", f'Uitsnede {o["obs_id"]}', 80) +
                 f'<div class="body"><h4>{o["obs_id"]} <span class="chip t-{o["observation_type"]}">{o["observation_type"]}</span> {o["visibility"]} '
                 f'<span class="chip">onzekerheid {o["uncertainty"]}</span> <span class="prio {prio}">{prio}</span></h4>'
                 f'<p>{E(o["note"])}</p>'
                 f'<p class="evid">Bron: {o["photo_id"]} {E(o["source_file"])}, regio px {o["bbox_px"]}; bevestigt alleen de zichtbare opening. Pand: ONBEWEZEN.</p>'
                 + controls(rid, H.CHOICES_STD, proposal) + "</div>")
        body.append(("OBSCARD", prio, rid, item_shell(rid, prio, inner)))

    # ------------------------------------------------------------------ Sectie B: reviewgroepen
    body.append('<h2 id="B">B. Mogelijke duplicaten: reviewgroepen</h2>')
    body.append('<p>De 43 kandidaat-relaties zijn gegroepeerd per gevelzone (<b>18 reviewgroepen</b>). Je hoeft niet alles te beoordelen: begin bij P1. '
                '<b>SAME</b> betekent uitsluitend dat twee observaties vermoedelijk hetzelfde fysieke object zijn; het bewijst geen pandkoppeling en voegt niets samen. '
                'Foto-2-annotaties zijn oranje (FC = kandidaat, FI = bestaande instance, ongewijzigd). Gele/cyaan/rode kaders = observaties op MAP-003/MAP-004; oranje labels op MAP-009/013/033 = referentiegebieden.</p>')
    group_index = []
    used_rels = set()
    for gi, (key, prio, title, rel_ids, panels, why, clues, unc, apps, photos) in enumerate(H.GROUPS, 1):
        gid = f"RG-{gi:02d}"
        parts = [f'<section class="group" id="{gid}"><h3>{gid} <span class="prio {prio}">{prio}</span> {E(title)}</h3>']
        for cap, specs in panels:
            cells = [panel_cell(ims, sp, 700) for sp in specs]
            parts.append(f'<p class="evid"><b>{E(cap)}</b> &mdash; ' + ", ".join(f"{sp[0]}" for sp in specs) + "</p>")
            parts.append(img_tag(compose(cells, 2 if len(cells) != 1 else 1), "panel", f"{gid} {cap}", 78, 1500))
        parts.append(f'<div class="cols"><div><h4>Waarom overlap mogelijk is</h4><p>{E(why)}</p></div><div><h4>Overeenkomende aanwijzingen</h4><p>{E(clues)}</p></div>'
                     f'<div><h4>Onzekerheden</h4><p>{E(unc)}</p></div></div>')
        parts.append(f'<p class="evid">Gekoppelde APP-besluiten (blijven OPEN): {", ".join(apps)}. Foto&apos;s: {", ".join(photos)}.</p>')
        for rid_vr in rel_ids:
            r = rels[rid_vr]
            used_rels.add(rid_vr)
            rid = "RV-REL-" + rid_vr
            proposal = P(rid, H.proposal_for_relation(r["class"], r["strength"]))
            sem = H.relation_semantics(r["class"], r["left"], r["right"])
            rtype = sem["relation_type"]
            evid = side_refs(rev, r["left"], p2px) + side_refs(rev, r["right"], p2px) + [{"type": "review_group", "group_id": gid}]
            for f in (("D1", "D2", "D3", "D4") if r["soc"] == "SOC-001" else ("C1", "C2", "C3") if r["soc"] == "SOC-002" else ("F",)):
                evid.append({"type": "report_figure", "file": B.IMG[f]})
            obs_ids = sorted(set(re.findall(r"OBS-MAP00[34]-\d{3}", r["left"] + " " + r["right"])))
            phs = sorted(set(re.findall(r"MAP-\d{3}", r["left"] + " " + r["right"])))
            add_item(rid, "OVERLAP_RELATION", prio, f'{rid_vr} {r["left"]} <-> {r["right"]}', phs, obs_ids, [rid_vr], apps, proposal, H.CHOICES_OVERLAP, evid, sem)
            tchip = ('<span class="chip rt-FACADE">GEVELSECTIE-overlap</span>' if rtype == H.FACADE_SECTION else '<span class="chip rt-OBJECT">OBJECT-overlap</span>')
            inner = (f'<div class="body"><h4>{rid_vr} {tchip} <span class="chip">{r["class"]}</span> <span class="chip">sterkte {r["strength"]}</span> <span class="prio {prio}">{prio}</span></h4>'
                     f'<p><b>Links:</b> {E(r["left"])}<br><b>Rechts:</b> {E(r["right"])}</p><p>{E(r["basis"])}</p>'
                     f'<p class="semantics {"sem-facade" if rtype == H.FACADE_SECTION else "sem-object"}"><b>Wat SAME hier betekent:</b> {E(sem["meaning_text"])}</p>'
                     + controls(rid, H.CHOICES_OVERLAP, proposal, rtype=rtype) + "</div>")
            parts.append(item_shell(rid, prio, inner))
        parts.append("</section>")
        body.append("".join(parts))
        group_index.append({"group_id": gid, "key": key, "priority": prio, "title": title, "relation_ids": rel_ids, "photo_ids": photos})
    assert used_rels == set(rels), set(rels) - used_rels

    # ------------------------------------------------------------------ Sectie C: bijzondere aandacht
    body.append('<h2 id="C">C. Extra aandacht voor onduidelijke objecten</h2>')
    body.append('<div class="note">Vergrote uitsneden van de originele pixels. Er is niets afgeleid of aangevuld: wat niet zichtbaar is, blijft onbekend.</div>')
    body.append('<h3 id="C1">C.1 OBS-MAP003-009: afzonderlijk smal raam of onderdeel van OBS-MAP003-010?</h3>')
    cells = [B.tile_photo2("MAP-002", ims["MAP-002"], B.D(1700, 515, 1960, 635), 700 / (B.D(1700, 515, 1960, 635)[2] - B.D(1700, 515, 1960, 635)[0])),
             B.tile_obs("MAP-003", ims["MAP-003"], B.D(750, 430, 1020, 570), 700 / (B.D(750, 430, 1020, 570)[2] - B.D(750, 430, 1020, 570)[0])),
             B.tile_obs("MAP-004", ims["MAP-004"], B.D(110, 435, 390, 555), 700 / (B.D(110, 435, 390, 555)[2] - B.D(110, 435, 390, 555)[0])),
             ref_crop(ims, next(r for r in V.REFS if r[0] == "REF-MAP013-004"), 700)]
    body.append(img_tag(compose(cells, 2), "panel", "009 versus 010 in vier foto's", 80, 1500))
    body.append('<p>Foto 2 (links boven) heeft het smalle linker element als apart kozijn besloten (FC-M2-006-A, PCD). In MAP-003 (rechts boven) is dat element door een open vleugel deels bedekt; in MAP-004 (links onder) valt het in een observatie en in MAP-013 (rechts onder) is het te schuin. '
                'Een betere frontale opname of een detailfoto zou dit oplossen.</p>')
    for rid_o in ("OBS-MAP003-009", "OBS-MAP003-010"):
        o = obs[rid_o]
        rid = "RV-OBS-" + rid_o[4:]
        proposal = P(rid, H.proposal_for_observation(o))
        inner = (img_tag(obs_crop(ims, o, 640), "thumb", f"Uitsnede {rid_o}", 82) +
                 f'<div class="body"><h4>{rid_o} <span class="chip t-{o["observation_type"]}">{o["observation_type"]}</span> {o["visibility"]} <span class="chip">onzekerheid {o["uncertainty"]}</span> <span class="prio P1">P1</span></h4>'
                 f'<p>{E(o["note"])}</p><p class="evid">Bron: {o["photo_id"]} {E(o["source_file"])}, regio px {o["bbox_px"]}. Thema: {E("; ".join(H.SPECIAL_THEMES[rid_o]))}.</p>'
                 + controls(rid, H.CHOICES_STD, proposal) + "</div>")
        body.append(item_shell(rid, "P1", inner))
    # HQ-VR-001 control
    hq = {q["id"]: q for q in rev["questions"]}
    hq_items = {}

    def hq_item(qid):
        q = hq[qid]
        rid = qid
        prio = H.HQ_PRIORITY[qid]
        proposal = H.HQ_PROPOSAL[qid]
        refs = [{"type": "review_document", "file": "maldenhof_visual_photo_review_map003_map004_v1.md", "section": 9}]
        if q["app_decision"]:
            refs.append({"type": "approval_document", "file": "reports/frames/photo_archive_audit_v1/maldenhof_photo_annotation_approval_v1.md", "decision": q["app_decision"]})
        add_item(rid, "EXISTING_QUESTION", prio, q["topic"], [], [], [], [q["app_decision"]] if q["app_decision"] else [], proposal, H.CHOICES_STD, refs)
        app = (f'Gekoppeld APP-besluit: <b>{q["app_decision"]}</b> (blijft OPEN; dit item is een voorlopig reviewresultaat)' if q["app_decision"] else "Aanvullende tijdelijke vraag (geen APP-besluit)")
        inner = (f'<div class="body"><h4>{qid} <span class="chip">{E(q["topic"])}</span> <span class="prio {prio}">{prio}</span></h4><p>{E(q["question"])}</p>'
                 f'<p class="evid">{app}. Aanbevolen antwoord in het review-document: {E(q["recommended"])}.</p>' + controls(rid, H.CHOICES_STD, proposal) + "</div>")
        return item_shell(rid, prio, inner)

    body.append(hq_item("HQ-VR-001"))

    body.append('<h3 id="C2">C.2 Scheiding tussen kozijnen bij gemetselde penanten</h3>')
    body.append('<p>Telregel: een kozijn met meerdere vleugels of een kozijnstijl scheidt niet; zichtbaar metselwerk tussen twee kozijnen scheidt wel (zoals bij foto 2, PCD-00004). '
                'Beoordeel per paar: CONFIRM = het metselwerk scheidt twee afzonderlijke openingen (zoals nu voorgesteld); REJECT = het is één opening. Nieuwe review-ID&apos;s (RV-SEP) zijn nodig omdat HQ-VR-002 alleen de regel zelf betreft.</p>')
    for sid, photo, a, b, text in H.SEPARATIONS:
        oa, ob = obs[f"OBS-{photo.replace('-', '')}-{a:03d}"], obs[f"OBS-{photo.replace('-', '')}-{b:03d}"]
        x0 = min(oa["bbox_px"][0], ob["bbox_px"][0]); y0 = min(oa["bbox_px"][1], ob["bbox_px"][1])
        x1 = max(oa["bbox_px"][2], ob["bbox_px"][2]); y1 = max(oa["bbox_px"][3], ob["bbox_px"][3])
        im = ims[photo]
        box = [max(0, x0 - 25), max(0, y0 - 25), min(im.width, x1 + 25), min(im.height, y1 + 25)]
        s = 760 / (box[2] - box[0])
        t = B.tile_obs(photo, im, box, s)
        proposal = "CONFIRM"
        evid = [source_ref(rev, photo, box, extra={"observation_ids": [oa["obs_id"], ob["obs_id"]]})]
        add_item(sid, "SEPARATION", "P1", f'{oa["obs_id"]} | {ob["obs_id"]}: gescheiden door metselwerk?', [photo], [oa["obs_id"], ob["obs_id"]], [], ["HQ-VR-002"], proposal, H.CHOICES_STD, evid)
        inner = (img_tag(t, "thumb", f"Scheiding {sid}", 82) + f'<div class="body" style="min-width:300px"><h4>{sid} {oa["obs_id"]} | {ob["obs_id"]} <span class="prio P1">P1</span></h4><p>{E(text)}</p>'
                 f'<p class="evid">Bron: {photo} {E(oa["source_file"])}, regio px {box}.</p>' + controls(sid, H.CHOICES_STD, proposal) + "</div>")
        body.append(item_shell(sid, "P1", inner))

    body.append('<h3 id="C3">C.3 Deuren, gedeeltelijk zichtbare kozijnen, beeldranden en afgedekte objecten</h3>')
    body.append('<p>Deze observaties hebben een bijzonder punt (thema&apos;s per kaart). Beoordeel alleen wat te zien is; een deur of raam dat niet zichtbaar is, wordt niet aangevuld.</p>')
    for oid in sorted(special_ids):
        if oid in ("OBS-MAP003-009", "OBS-MAP003-010"):
            continue
        o = obs[oid]
        rid = "RV-OBS-" + oid[4:]
        prio = next(i["priority"] for i in items if i["review_id"] == rid)
        proposal = next(i["claude_proposal"] for i in items if i["review_id"] == rid)
        inner = (img_tag(obs_crop(ims, o, 640, 60), "thumb", f"Uitsnede {oid}", 82) +
                 f'<div class="body"><h4>{oid} <span class="chip t-{o["observation_type"]}">{o["observation_type"]}</span> {o["visibility"]} <span class="chip">onzekerheid {o["uncertainty"]}</span> <span class="prio {prio}">{prio}</span></h4>'
                 f'<p>{E(o["note"])}</p><p><b>Thema&apos;s:</b> {E("; ".join(H.SPECIAL_THEMES[oid]))}</p>'
                 f'<p class="evid">Bron: {o["photo_id"]} {E(o["source_file"])}, regio px {o["bbox_px"]}. Pand: ONBEWEZEN.</p>' + controls(rid, H.CHOICES_STD, proposal) + "</div>")
        body.append(item_shell(rid, prio, inner))

    # ------------------------------------------------------------------ Sectie D: platen
    body.append('<h2 id="D">D. Huisnummerplaten en pandbewijs</h2>')
    body.append('<div class="note">Drie verschillende uitspraken (niet door elkaar halen):<ol><li><b>Voorlopig gelezen huisnummer:</b> wat Claude op de vergroting leest; nog niet door een mens bevestigd (APP-002/APP-003).</li>'
                '<li><b>Relatie huisnummer &harr; BAG-pand:</b> bestaand bewijs uit de BAG-snapshots voor dat adres; de plaat bewijst <u>alleen de muur</u> waaraan hij hangt (APP-001).</li>'
                '<li><b>Relatie kozijn &harr; BAG-pand:</b> <b>ONBEWEZEN</b> voor elk kozijn. Geen kozijn krijgt automatisch een pand-ID.</li></ol></div>')
    for p in rev["plates"]:
        photo = p["photo_id"]
        rid = f'RV-PLATE-{photo.replace("-", "")}-{p["reading"]}'
        im = ims[photo]
        x0, y0, x1, y1 = p["bbox_px"]
        t = im.crop((max(0, x0 - 14), max(0, y0 - 14), min(im.width, x1 + 14), min(im.height, y1 + 14)))
        t = t.resize((t.width * 8, t.height * 8), Image.LANCZOS)
        proposal = "CONFIRM"
        evid = [source_ref(rev, photo, p["bbox_px"], extra={"plate_id": p["plate_id"]}), {"type": "report_figure", "file": B.IMG["E"]},
                {"type": "bag_evidence", "file": "data/photo_evidence/maldenhof_address_pand_evidence_v1.json", "address": f'Maldenhof {p["reading"]}', "bag_pand_id": p["bag_pand_id_for_plate_wall"]}]
        add_item(rid, "PLATE_READING", "P2", f'{photo} plaat {p["reading"]}', [photo], [], [], ["APP-002" if photo == "MAP-003" else "APP-003"], proposal, H.CHOICES_STD, evid)
        inner = (img_tag(t, "thumb", f'Plaat {p["reading"]}', 85) +
                 f'<div class="body"><h4>{p["plate_id"]} <span class="prio P2">P2</span></h4>'
                 f'<table><tr><th>Voorlopig gelezen huisnummer</th><td><b>{p["reading"]}</b> (leesbaar bij vergroting; niet door een mens bevestigd)</td></tr>'
                 f'<tr><th>Huisnummer &harr; BAG-pand</th><td>Bestaand BAG-bewijs voor Maldenhof {p["reading"]}: pand {p["bag_pand_id_for_plate_wall"]} (volgorde {p["pand_order"]}); geldt alleen voor de plaatmuur</td></tr>'
                 f'<tr><th>Kozijn &harr; BAG-pand</th><td><b>ONBEWEZEN</b></td></tr></table>'
                 f'<p class="evid">Bron: {photo} {E(next(x for x in ver.values() if x["photo_id"] == photo)["file"])}, regio px {p["bbox_px"]}. CONFIRM = de lezing klopt.</p>' + controls(rid, H.CHOICES_STD, proposal) + "</div>")
        body.append(item_shell(rid, "P2", inner))

    # ------------------------------------------------------------------ Sectie E: bestaande vragen en APP-besluiten
    body.append('<h2 id="E">E. Bestaande besluiten en vragen</h2>')
    body.append('<div class="note">De 48 APP-besluiten blijven OPEN en worden hier niet gewijzigd. De items hieronder zijn voorlopige reviewresultaten bij de bestaande vragen (HQ-APP-xxx hoort bij het APP-besluit met hetzelfde nummer; HQ-VR-xxx zijn tijdelijke aanvullende vragen). '
                'Een CONFIRM hier is geen goedkeuring van het APP-besluit zelf; het wordt later gecontroleerd verwerkt.</div>')
    for qid in H.HQ_PRIORITY:
        if qid == "HQ-VR-001":
            continue
        body.append(hq_item(qid))

    # ------------------------------------------------------------------ Sectie F: kwaliteitscontrole P1 (v1.1)
    for it in items:
        it["ref_hash"] = H.ref_hash(it)
        if it["review_id"] in Q.PROPOSAL_CORRECTIONS:
            it["claude_proposal_v1"] = Q.PROPOSAL_CORRECTIONS[it["review_id"]][0]
    recs = QR.quality_records(items, rev)
    recmap = {r["review_id"]: r for r in recs}
    for it in items:
        r = recmap.get(it["review_id"])
        if r:
            it["quality"] = {"quality_status": r["quality_status"], "evidence_class": r.get("evidence_class"), "technically_correct": r["technically_correct"]}
    figs = QR.make_figures(ims, rev)
    body.append(f'<h2 id="F">F. Kwaliteitscontrole P1 (v1.1)</h2>')
    body.append('<div class="note warn"><b>Een technisch geldige reviewkaart is niet automatisch een visueel bewezen object.</b> Alle P1-punten zijn opnieuw met de originele pixels vergeleken. '
                'De bevindingen van een externe review zijn als invoer gebruikt, niet als waarheid. Dit is geen menselijke goedkeuring: alle 48 APP-besluiten blijven OPEN en er ontstaan geen instances, pandkoppelingen, totalen of kosten.</div>')
    cnt_st = Counter(r["quality_status"] for r in recs)
    body.append('<p>' + " ".join(f'<span class="chip st-{k}">{k}: {cnt_st.get(k, 0)}</span>' for k in Q.QUALITY_STATUSES) + f' &mdash; technisch correct: <b>{sum(r["technically_correct"] for r in recs)}</b> van {len(recs)} P1-punten.</p>')
    body.append('<p class="evid">' + E(Q.CLASS_RULE) + '</p>')
    rows = ["<table><tr><th>#</th><th>Review-ID</th><th>Kwaliteitsstatus</th><th>Bevinding</th><th>Volgende stap</th></tr>"]
    for k, r in enumerate(recs, 1):
        rows.append(f'<tr><td>{k}</td><td><a href="#item-{E(r["review_id"])}">{E(r["review_id"])}</a></td><td><span class="chip st-{r["quality_status"]}">{r["quality_status"]}</span></td>'
                    f'<td>{E(r["finding"])}</td><td>{E(r["next_step"])}</td></tr>')
    rows.append("</table>")
    body.append("".join(rows))
    body.append("<h3>Extra bewijs (originele pixels)</h3>")
    caps = {"QSEP": "Scheiding (penant): ruwe uitsnede en kaders", "Q009": "OBS-MAP003-009 versus 010 in vier foto's", "QREL": "Relatieblad: de gekoppelde uitsneden naast elkaar", "QD-": "Object met bijzonder punt: ruwe uitsnede en kader"}
    gal = ['<div class="gallery">']
    for name, im in sorted(figs.items()):
        cap = next(v for k, v in caps.items() if name.startswith(k))
        gal.append(f'<figure id="fig-{E(name[:-4])}">{img_tag(im, "fig", name, 74, 1100)}<figcaption><b>{E(name)}</b> &mdash; {E(cap)}</figcaption></figure>')
    gal.append("</div>")
    body.append("".join(gal))

    def qa_block(rec):
        st = rec["quality_status"]
        out = [f'<div class="qa st-{st}"><b>Kwaliteitscontrole v1.1 (extra, niet-bindend)</b> <span class="chip st-{st}">{st}</span>']
        if rec.get("evidence_class"):
            out.append(f'<span class="chip">{rec["evidence_class"]}</span>')
        out.append(f'<span class="chip">{"technisch correct" if rec["technically_correct"] else "TECHNISCHE FOUT"}</span>')
        out.append(f'<p>{E(rec["finding"])}</p>')
        if rec.get("six_questions"):
            out.append("<table>" + "".join(f'<tr><th>{E(Q.Q6_NL[k])}</th><td><b>{E(v["answer"])}</b> {E(v["note"])}</td></tr>' for k, v in rec["six_questions"].items()) + "</table>")
        if rec.get("separation_checks"):
            c = rec["separation_checks"]
            out.append(f'<p class="evid">Penant zichtbaar: {"ja" if c["pier_visible"] else "nee"}; afzonderlijke openingen: {"ja" if c["separate_openings"] else "nee"}; kaders correct: {"ja" if c["bbox_correct"] else "nee"}; bewijs voldoende: {"ja" if c["evidence_sufficient"] else "nee"}.</p>')
        fm = rec.get("feature_match")
        if fm:
            out.append(f'<p class="evid">Kenmerkmatch (hulpmiddel, beslist niet): {fm["inliers"]} inliers' + (f', rang {fm["rank_of_partner_among_MAP004"]} / {fm["rank_of_partner_among_MAP003"]}' if "rank_of_partner_among_MAP004" in fm else "") + ".</p>")
        out.append(f'<p class="evid">Bewijs: <code>{E(rec["visual_evidence"])}</code> (sectie F). Volgende stap: {E(rec["next_step"])} Extra bewijs nodig: {E(rec["extra_evidence_needed"])}.</p>')
        if "proposal_correction" in rec:
            c = rec["proposal_correction"]
            out.append(f'<p class="evid"><b>Voorstel gecorrigeerd:</b> {c["from"]} &rarr; {c["to"]}. {E(c["reason"])}</p>')
        out.append("</div>")
        return "".join(out)

    # ------------------------------------------------------------------ samenstellen
    obscards = [b for b in body if isinstance(b, tuple)]
    html_parts = []
    placed = False
    for b in body:
        if isinstance(b, tuple):
            if not placed:
                html_parts.extend(c[3] for c in obscards)
                placed = True
            continue
        html_parts.append(b)
    # prioriteit-overzicht
    cats = [("OBSERVATION", "Observaties (sectie A en C)"), ("OVERLAP_RELATION", "Kandidaat-overlaprelaties (sectie B)"), ("SEPARATION", "Scheiding bij penanten (sectie C.2)"),
            ("PLATE_READING", "Plaatlezingen (sectie D)"), ("EXISTING_QUESTION", "Bestaande vragen HQ (sectie C.1 en E)")]
    cnt = Counter((i["review_type"], i["priority"]) for i in items)
    rows = ["<table><tr><th>Soort reviewpunt</th><th>P1 kritiek</th><th>P2 belangrijk</th><th>P3 later</th><th>Totaal</th></tr>"]
    tot = Counter()
    for k, label in cats:
        rows.append(f"<tr><td>{label}</td>" + "".join(f"<td>{cnt[(k, p)]}</td>" for p in ("P1", "P2", "P3")) + f"<td>{sum(cnt[(k, p)] for p in ('P1', 'P2', 'P3'))}</td></tr>")
        for p in ("P1", "P2", "P3"):
            tot[p] += cnt[(k, p)]
    rows.append("<tr><th>Totaal reviewpunten</th>" + "".join(f"<th>{tot[p]}</th>" for p in ("P1", "P2", "P3")) + f"<th>{sum(tot.values())}</th></tr></table>")
    prio_html = ('<h2 id="prio">Prioriteiten</h2><p><b>P1 kritiek:</b> mogelijke dubbeltellingen, mogelijke verkeerde scheiding tussen kozijnen, onduidelijke deuren, overlap met bevroren foto 2 en besluiten die nodig zijn voordat instance-creatie verantwoord is. '
                 '<b>P2 belangrijk:</b> FULL/PARTIAL, dakramen en dakkapel, relaties met MAP-009/013/033, onzekerheden in de classificatie. <b>P3 later:</b> detailcorrecties zonder directe invloed op unieke objectidentificatie en punten die eerst extra fotobewijs vragen.</p>'
                 + "".join(rows) + '<p class="evid">Dit zijn <b>reviewpunten</b>, geen aantallen unieke fysieke kozijnen: observaties en relaties overlappen elkaar en foto 2. Je hoeft niet alles te beoordelen; gebruik de filterknoppen bovenaan.</p>')
    howto = ('<h2 id="howto">Zo gebruik je dit pakket</h2><ol><li>Open dit bestand in een browser (dubbelklik; geen server of internet nodig).</li>'
             '<li>Begin met <b>P1</b> (filterknop bovenaan). Bekijk de uitsnede, lees de toelichting en het voorstel van Claude (nooit voorgekozen).</li>'
             '<li>Kies per punt een keuzerondje (CONFIRM/REJECT/UNDECIDABLE/NEEDS_BETTER_PHOTO; bij overlap SAME/DIFFERENT/UNDECIDABLE). Optioneel: opmerking. Met <b>OPEN zetten</b> maak je een keuze ongedaan.</li>'
             '<li>Klik bovenaan of onderaan op <b>Exporteer JSON</b>. Het bestand bevat per punt de beslissing (OPEN als je niets koos), je opmerking, foto-/observatie-ID&apos;s en de bronverwijzing. Onderaan kies je de omvang: alles, alleen beoordeelde punten of P1/P2/P3.</li>'
             '<li><b>Overlap heeft twee soorten.</b> Bij GEVELSECTIE-overlap betekent SAME alleen dezelfde gevelsectie (niet hetzelfde kozijn); bij OBJECT-overlap betekent SAME dat de observaties vermoedelijk hetzelfde fysieke object tonen. Geen van beide is een pandkoppeling.</li>'
             '<li>Een eerder bewaard bestand laad je met <b>Eerdere export laden</b>: het bestand wordt eerst volledig gecontroleerd; bij een fout verandert er niets. Daarna kies je tussen volledig vervangen en gedeeltelijk samenvoegen.</li>'
             '<li>Stuur het exportbestand terug; het wordt pas na controle verwerkt. De export zelf wijzigt niets.</li></ol>')
    page = TEMPLATE.read_text()
    bodyhtml = "\n".join(html_parts).replace("__HOWTO__", howto).replace("__PRIO_TABLE__", prio_html)
    for it in items:
        bodyhtml = bodyhtml.replace(f'<!--QA:{it["review_id"]}-->', qa_block(recmap[it["review_id"]]) if it["review_id"] in recmap else "")
    assert "<!--QA:" not in bodyhtml
    page = page.replace("__BODY__", bodyhtml)
    pack_json = {"pack_version": PACK_VERSION, "legacy_pack_version": LEGACY_PACK_VERSION, "review_package_version": B.VERSION, "meaning": H.MEANING, "items": items}
    page = page.replace("__PACK__", json.dumps(pack_json, ensure_ascii=False).replace("</", "<\\/"))
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(page)
    index = {"pack_version": PACK_VERSION, "review_package_version": B.VERSION, "html": OUT_HTML.name,
             "sources": list(ver.values()), "counts": {"observations": len(obs), "relations": len(rels), "review_groups": len(H.GROUPS), "review_points": len(items),
                                                         "by_type_priority": {f"{k}|{p}": n for (k, p), n in sorted(cnt.items())},
                                                         "by_priority": dict(tot)},
             "review_groups": group_index, "review_ids": [i["review_id"] for i in items],
             "effects": {"instances_created": 0, "bag_links_created": 0, "building_totals": None, "costs": None, "app_decisions_open": 48, "photo2_unchanged": True,
                         "default_decision": "OPEN", "claude_proposals_exported_as_human_decisions": False},
             "quality_review": {"report": QR.OUT_MD.name, "p1_points": len(recs), "technically_correct": sum(r["technically_correct"] for r in recs),
                                "by_quality_status": dict(cnt_st), "proposal_corrections": sorted(Q.PROPOSAL_CORRECTIONS)},
             "export_format": "maldenhof_visual_decision_export_v2", "legacy_export_format_accepted": "maldenhof_visual_decision_export_v1",
             "network_dependencies": "none (alle afbeeldingen als data-URI; geen externe scripts)"}
    OUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    QR.write_reports(items, rev, recs, PACK_VERSION)
    print(f"HTML {OUT_HTML.stat().st_size/1e6:.1f} MB; reviewpunten {len(items)}; per prioriteit {dict(tot)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=B.ZIP_DEFAULT)
    build(ap.parse_args())
