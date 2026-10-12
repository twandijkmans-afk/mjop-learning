#!/usr/bin/env python3
"""Human Pilot Review Preparation v1 (alleen rapportage/presentatie; geen instances, pandkoppelingen, totalen, kosten en geen besluiten).

Bibliotheek voor build_human_visual_decision_pack.py: maakt de pilotfiguren uit de originele pixels, het correctievoorstel voor de zichtbaarheid van
OBS-MAP003-009 (alleen een voorstel; de bronobservatie blijft ongewijzigd) en het pilotrapport.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_p1_quality_review as QR  # noqa: E402
import build_visual_photo_review_map003_map004 as B  # noqa: E402
import human_decision_pack_data as H  # noqa: E402
import p1_quality_review_data as Q  # noqa: E402
import pilot_review_data as PD  # noqa: E402
import visual_review_map003_map004_data as V  # noqa: E402

PDIR = B.OUT / "pilot_review"
OUT_MD = B.OUT / "maldenhof_pilot_review_preparation_v1.md"
OUT_JSON = B.OUT / "maldenhof_pilot_review_preparation_v1.json"
CORR_JSON = PDIR / "maldenhof_obs_map003_009_visibility_correction_proposal_v1.json"


def make_figures(ims, rev):
    PDIR.mkdir(parents=True, exist_ok=True)
    figs = {}
    obs = QR.obs_index()
    boxes, _ = B.photo2_boxes()
    rels = {r[0]: {"rel_id": r[0], "left": r[2], "right": r[3], "class": r[4], "strength": r[5]} for r in V.RELATIONS}
    for vr in ("VR-027", "VR-024", "VR-026"):
        r = rels[vr]
        row = QR.hstack([QR.tile(ims, x, obs, boxes, height=300, maxw=520) for x in (r["left"], r["right"])])
        figs[f"PQ-rel-{vr}.jpg"] = row
    # gevelrelatie VR-020: de platenwand op beide foto's
    cells = []
    for pid, box in (("MAP-003", V.D(1430, 840, 1850, 960)), ("MAP-004", V.D(220, 840, 640, 960))):
        t = ims[pid].crop(tuple(int(x) for x in box))
        cells.append(QR._label(t.resize((520, round(t.height * 520 / t.width)), Image.LANCZOS), f"{pid}: platen 280/278 en entreemuren"))
    figs["PQ-rel-VR-020.jpg"] = QR.hstack(cells)
    # OBS-MAP003-009: rechterrand overlapt door de open vleugel van 010
    o9 = obs["OBS-MAP003-009"][1]
    o10 = obs["OBS-MAP003-010"][1]
    box = (o9[0] - 40, o9[1] - 30, o9[2] + 120, o9[3] + 30)
    raw = ims["MAP-003"].crop(tuple(int(x) for x in box))
    s = 700 / raw.width
    raw = raw.resize((700, round(raw.height * s)), Image.LANCZOS)
    ov = raw.copy()
    d = ImageDraw.Draw(ov)
    for bb, col in ((o9, (255, 40, 40)), (o10, (40, 220, 40))):
        d.rectangle([(bb[0] - box[0]) * s, (bb[1] - box[1]) * s, (bb[2] - box[0]) * s, (bb[3] - box[1]) * s], outline=col, width=3)
    figs["PQ-009_visibility_zoom.jpg"] = QR.hstack([QR._label(raw, "OBS-MAP003-009 en omgeving, ruwe uitsnede MAP-003"), QR._label(ov, "kaders: 009 (rood), 010 (groen)")], bg=(24, 24, 24))
    for n, im in figs.items():
        im.convert("RGB").save(PDIR / n, "JPEG", quality=82, optimize=True)
    return figs


def correction_proposal(rev):
    o = next(x for x in rev["observations"] if x["obs_id"] == "OBS-MAP003-009")
    o10 = next(x for x in rev["observations"] if x["obs_id"] == "OBS-MAP003-010")
    doc = {
        "proposal_id": "CORR-OBS-MAP003-009-VIS-001",
        "status": "PROPOSED_NOT_APPLIED",
        "requires": "afzonderlijke menselijke goedkeuring; de bronobservatie in maldenhof_visual_photo_review_map003_map004_v1.json is NIET gewijzigd",
        "observation_id": "OBS-MAP003-009",
        "field": "visibility",
        "current_value": o["visibility"],
        "proposed_value": "PARTIAL",
        "bbox_px": o["bbox_px"],
        "finding": ("Het label FULL betekent dat de volledige omtrek zichtbaar is. Op MAP-003 wordt de rechterrand van het smalle element in het bovenste deel bedekt door de open, blauw omrande "
                    "vleugel van OBS-MAP003-010; het kader van 009 eindigt precies waar het kader van 010 begint (x=842) en de blauwe vleugel valt voor een deel binnen het kader van 009. Linkerzijde, boven- en onderrand zijn wel zichtbaar."),
        "evidence": {"figure": "pilot_review/PQ-009_visibility_zoom.jpg", "other_photos": "MAP-013 REF-004 toont het element wel volledig met metselwerk ernaast; foto 2 (FC-M2-006-A) is FULL en blijft bevroren",
                     "bbox_overlap_scan": "In MAP-003/MAP-004 raken of overlappen alleen de kaders van OBS-MAP003-009 en -010 elkaar (breedte 0 px); geen andere observatie heeft deze inconsistentie"},
        "neighbour": {"observation_id": "OBS-MAP003-010", "visibility": o10["visibility"], "note": "ongewijzigd"},
        "effects_if_applied": {"instances_created": 0, "counts_changed": False, "counts_in_any_total": False, "bag_links": 0, "photo2_frozen_data_changed": False,
                               "note": "Observaties staan buiten de instance-store en tellen in geen enkel totaal; het is een label-correctie voor de leesbaarheid."},
        "alternative": "FULL behouden met een extra notitie 'rechterrand bedekt door open vleugel van 010'; de zichtbaarheidsdefinitie (FULL = volledige omtrek zichtbaar) pleit voor PARTIAL.",
    }
    CORR_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return doc


def write_report(items, recs, corr, pack_version):
    byid = {i["review_id"]: i for i in items}
    L = []
    A = L.append
    A("# Maldenhof Human Pilot Review Preparation v1")
    A("")
    A(f"Pakketversie `{pack_version}` (PR #41). Dit is een **voorbereiding**: de selectie is geen besluit en geen goedkeuring. Alle niet-geselecteerde punten blijven OPEN, alle 48 APP-besluiten blijven OPEN en er ontstaan geen instances, geen samenvoeging, geen unieke totalen, geen BAG-pandkoppelingen, geen kosten en geen wijziging aan de bevroren foto-2-gegevens.")
    A("")
    A("## 1. Geselecteerde reviewpunten (10)")
    A("")
    A("| # | Review-ID | Situatie | Reden van selectie | Voorstel Claude (niet-bindend) | Kwaliteitsstatus |")
    A("|---|---|---|---|---|---|")
    for k, rid in enumerate(PD.PILOT_ORDER, 1):
        p = PD.PILOT[rid]
        A(f'| {k} | {rid} | {p["situation"]} | {p["reason"]} | {byid[rid]["claude_proposal"]} | {recs[rid]["quality_status"]} |')
    A("")
    A("Alle acht gevraagde situaties zijn afgedekt (de configuratie OBS-MAP003-009/010 met drie punten). Gebruikt zijn uitsluitend bestaande review-ID's, afbeeldingen, bronverwijzingen en voorlopige classificaties; de reviewkaarten zelf zijn niet gewijzigd.")
    A("")
    A("## 2. Uitleg per punt")
    A("")
    for k, rid in enumerate(PD.PILOT_ORDER, 1):
        p = PD.PILOT[rid]
        A(f"### {k}. {rid}: {p['title']}")
        A("")
        for lab, key in (("Wat is zichtbaar", "visible"), ("Welke beslissing is nodig", "decision"), ("Welk bewijs ondersteunt het voorstel", "evidence"), ("Wat is nog onzeker", "uncertain"),
                         ("Wat de keuze wel doet", "does"), ("Wat de keuze niet doet", "doesnt")):
            A(f"- **{lab}:** {p[key]}")
        A("")
    A("## 3. Correctievoorstel OBS-MAP003-009 (zichtbaarheid FULL tegenover bedekte rechterrand)")
    A("")
    A(f"- **Bevinding:** {corr['finding']}")
    A(f"- **Voorstel:** `visibility` {corr['current_value']} naar **{corr['proposed_value']}** voor OBS-MAP003-009. Status: `{corr['status']}`. {corr['requires']}.")
    A(f"- **Onderzoek:** {corr['evidence']['bbox_overlap_scan']}. {corr['evidence']['other_photos']}.")
    A(f"- **Alternatief:** {corr['alternative']}")
    A(f"- **Gevolgen bij doorvoeren:** {corr['effects_if_applied']['note']} Geen telling verandert, geen instance, geen pandkoppeling, foto 2 ongewijzigd.")
    A("- Bestand: `pilot_review/maldenhof_obs_map003_009_visibility_correction_proposal_v1.json`; figuur: `pilot_review/PQ-009_visibility_zoom.jpg`. De bronobservatie (`maldenhof_visual_photo_review_map003_map004_v1.json`/`.md`) is niet aangepast.")
    A("")
    A("## 4. Scheiding van bewijs, goedkeuring, objectidentiteit en pandkoppeling")
    A("")
    A("| Soort uitspraak | Waar vastgelegd | Wat het niet is |")
    A("|---|---|---|")
    A("| Visueel bewijs | Kwaliteitscontrole (`QUALITY`-status, bewijsklasse) | geen besluit |")
    A("| Menselijk (voorlopig) besluit | alleen in `human` van de export, `decision_source: HUMAN` | niet toegepast; geen goedkeuring van een APP-besluit |")
    A("| Fysieke objectidentiteit | alleen als kandidaat (`SAME_PHYSICAL_OBJECT_CANDIDATE`) | geen merge, geen instance |")
    A("| Gevelsectie | `SAME_FACADE_SECTION` | niet hetzelfde kozijn |")
    A("| BAG-pandkoppeling | niet aanwezig voor elk pilotpunt (ONBEWEZEN) | nooit afgeleid uit een plaat of overlap |")
    A("")
    A("## 5. Gebruik in de browser")
    A("")
    A("Open de HTML. Boven aan staat de sectie **Pilot Review**; de knop **Pilot Review** in de kopbalk toont uitsluitend deze 10 punten en het exportgedeelte. Bij het exporteren kies je omvang **Alleen Pilot Review** (deelbestand) of **Alles**. Niet-geselecteerde punten blijven OPEN.")
    A("")
    A("## 6. Tests")
    A("")
    A("`tests/test_human_visual_decision_pack.py` (selectie, filter, export naar JSON, overige punten OPEN, import van een eerdere v1.1.0-export), `tests/test_p1_visual_quality_review.py`, `tests/test_pilot_review_preparation.py` (selectie, correctievoorstel, brondata onveranderd) en `tests/test_scope_guard.py`.")
    OUT_MD.write_text("\n".join(L) + "\n")
    OUT_JSON.write_text(json.dumps({"report": "maldenhof_pilot_review_preparation_v1", "pack_version": pack_version, "status": "PREPARATION_NOT_A_HUMAN_APPROVAL",
                                    "selected": [{"review_id": r, "situation": PD.PILOT[r]["situation"], "reason": PD.PILOT[r]["reason"], "claude_proposal": byid[r]["claude_proposal"],
                                                  "quality_status": recs[r]["quality_status"]} for r in PD.PILOT_ORDER],
                                    "situations": PD.SITUATIONS, "correction_proposal": corr,
                                    "effects": {"instances_created": 0, "bag_links_created": 0, "building_totals": None, "costs": None, "app_decisions_open": 48}},
                                   ensure_ascii=False, indent=1) + "\n")
