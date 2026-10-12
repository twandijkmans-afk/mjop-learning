#!/usr/bin/env python3
"""Maldenhof Photo Archive Audit v1.

Registreert de 36 aangeleverde originele Maldenhof-foto's (zip + manifest) met SHA256, resolutie, ID (MAP-001..036), classificatie en
bruikbaarheid; markeert mogelijke overlap als SAME_OBJECT_CANDIDATE (nooit automatisch samengevoegd); koppelt panden alleen via leesbare
huisnummerplaten die via bestaand BAG-bewijs naar een pand leiden; maakt een voorlopige coverage matrix over de 15 bevestigde panden en
een shortlist (max 15) voor vervolgannotatie.

Geen nieuwe instances, geen building totals, geen repeat multipliers, geen maten, geen painting area, geen KG/prijs/App-wijzigingen.
De originelen blijven buiten de repository (zip in /mnt/project-files); de repo bevat een ongewijzigde kopie van manifest.csv, het
register (JSON/MD) en downscaled contactbladen.

Gebruik: python3 scripts/build_photo_archive_audit.py [--check] [--zip PAD]   (--zip: verifieert de originelen en maakt de contactbladen)
"""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
MANIFEST = D / "photos" / "archive" / "maldenhof_selection_manifest_v1.csv"
ADDR = D / "photo_evidence" / "maldenhof_address_pand_evidence_v1.json"
INSTANCES = D / "frame_inventory" / "maldenhof_photo_frame_instances_v1.json"
OUT_DIR = ROOT / "reports" / "frames" / "photo_archive_audit_v1"
OUT_JSON = OUT_DIR / "maldenhof_photo_archive_audit_v1.json"
OUT_MD = OUT_DIR / "maldenhof_photo_archive_audit_v1.md"
SHEET_PREFIX = "maldenhof_archive_contact_sheet_"
VERSION = "photo_archive_audit_v1.0.0"
ZIP_NAME = "Maldenhof_kozijnfoto_selectie (4) 2.zip"
REPO_PHOTOS = {n: D / "photos" / "incoming" / "maldenhof" / f"maldenhof_{n}.jpg" for n in (1, 2, 3)}

# --- handmatige visuele lezing (Claude, MANUAL_VISUAL_READING) per foto ------------------------------------------------------------
# id: (side, view, usability, plates, rotated, note)
# side: FRONT | FRONT_OBLIQUE | REAR | REAR_OR_SIDE | SIDE_GABLE_OBLIQUE | ROOF | DETAIL | STREET_CONTEXT
# usability: FRAME_ANNOTATION_HIGH | _MEDIUM | _LOW | DETAIL_ONLY | CONTEXT_ONLY
P = {
    1: ("SIDE_GABLE_OBLIQUE", "Straatzijde schuin vanaf de kopgevel; dakkapel en dakramen zichtbaar", "CONTEXT_ONLY", [], False, "Schuine, verkorte gevelrij; kopgevel links; kozijnen te klein/verkort voor annotatie."),
    2: ("FRONT", "Frontale straatzijde, voorgevel", "FRAME_ANNOTATION_HIGH", [290, 288], False, "Bron van maldenhof_2.jpg (pixelmatch). Platen 290/288 klein maar leesbaar bij vergroting."),
    3: ("FRONT", "Frontale straatzijde, voorgevel", "FRAME_ANNOTATION_HIGH", [288, 286, 284, 282, 280, 278, 276], False, "Zeven platen leesbaar bij vergroting; tegenlicht, bomen en auto beperken de onderste rij."),
    4: ("FRONT", "Frontale straatzijde, voorgevel", "FRAME_ANNOTATION_HIGH", [280, 278, 276, 274], False, "Lantaarnpaal en auto voor de begane grond; platen leesbaar bij vergroting."),
    5: ("FRONT", "Frontale straatzijde, voorgevel", "FRAME_ANNOTATION_MEDIUM", [262, 260, 258], False, "Lantaarnpaal, struik, motor en aanhanger voor de begane grond; platen leesbaar bij vergroting."),
    6: ("FRONT", "Brede straatzijde, voorgevel op afstand", "FRAME_ANNOTATION_LOW", [], False, "Sterk tegenlicht en zonnevlek; kozijnen klein; geen leesbare huisnummers."),
    7: ("FRONT_OBLIQUE", "Voorgevel schuin van onderen", "FRAME_ANNOTATION_MEDIUM", [], False, "Boom/conifeer voor de rechterhelft; geen leesbare platen."),
    8: ("FRONT_OBLIQUE", "Voorgevel schuin, entreemuur 266/268 op de voorgrond", "FRAME_ANNOTATION_MEDIUM", [268, 266], False, "Beide platen leesbaar; raam met kippengaas bij plaat 268."),
    9: ("FRONT_OBLIQUE", "Voorgevel schuin, entreemuur met plaat", "FRAME_ANNOTATION_MEDIUM", [280], False, "Plaat 280 leesbaar bij vergroting; auto en hortensia voor de onderkant."),
    10: ("FRONT_OBLIQUE", "Voorgevel schuin met straatperspectief", "FRAME_ANNOTATION_LOW", [], False, "Plaat(en) mogelijk aanwezig maar niet leesbaar vastgesteld; sterke vooruitzichtvervorming."),
    11: ("STREET_CONTEXT", "Straat met schutting en boom; gevelrij ver weg", "CONTEXT_ONLY", [], False, "Gevel grotendeels afgedekt door boom en schutting."),
    12: ("STREET_CONTEXT", "Straatperspectief langs de gevelrij", "CONTEXT_ONLY", [], False, "Gevelrij sterk verkort en verborgen achter beplanting."),
    13: ("FRONT_OBLIQUE", "Voorgevel schuin, entreemuren 288/286", "FRAME_ANNOTATION_MEDIUM", [288, 286], False, "Beide platen leesbaar; raam naast plaat 288."),
    14: ("REAR_OR_SIDE", "Achterzijde/dakvlak met kopgevel rechts, balkons en dakkapel", "FRAME_ANNOTATION_MEDIUM", [], False, "Houten schutting voor de begane grond; geen huisnummers. Zelfde tafereel als maldenhof_3 (foto 15) vanuit iets andere positie."),
    15: ("REAR_OR_SIDE", "Achterzijde/dakvlak met kopgevel rechts, balkons en dakkapel", "FRAME_ANNOTATION_MEDIUM", [], False, "Bron van maldenhof_3.jpg (pixelmatch, hogere resolutie 3264x2448). Pand nog NOT_PROVEN."),
    16: ("REAR_OR_SIDE", "Achterzijde/dakvlak, tuinafscheiding en boom voor de gevel", "FRAME_ANNOTATION_LOW", [], False, "Boom en hekwerk verbergen de onderste bouwlagen."),
    17: ("REAR_OR_SIDE", "Achterzijde met tuinafscheiding, schuurtje en balkon", "FRAME_ANNOTATION_LOW", [], False, "Begroeiing en schutting verbergen het grootste deel van de begane grond."),
    18: ("REAR_OR_SIDE", "Achterzijde met balkons, rode deuren en dakschild", "FRAME_ANNOTATION_MEDIUM", [], False, "Rode deur en balkons zichtbaar; schutting onderrand."),
    19: ("ROOF", "Achterzijde, dakvlak dominant met balkon en dakramen", "FRAME_ANNOTATION_LOW", [], False, "Dakvlak vult het beeld; opname van onderen; bovenste gevelrij smal."),
    20: ("ROOF", "Achterzijde, dakvlak met dakramen en tuinhuis", "FRAME_ANNOTATION_LOW", [], False, "Dakvlak dominant; tuinhuis en hekwerk voor de begane grond."),
    21: ("REAR_OR_SIDE", "Tuinzijde met dakkapel, veranda en tuin", "FRAME_ANNOTATION_MEDIUM", [], False, "Boom en tuinmeubilair afdekking; zijde (achter of kopgevel) niet vast te stellen."),
    22: ("DETAIL", "Detail raam en houten betimmering naast dakschild", "DETAIL_ONLY", [], False, "Zijde onbekend; geen plaat."),
    23: ("DETAIL", "Detail ramen met open draaideel naast een houten bouwdeel", "DETAIL_ONLY", [], True, "Camera sterk gekanteld; zijde onbekend."),
    24: ("DETAIL", "Detail ramen met open draaideel in houten betimmering", "DETAIL_ONLY", [], False, "Van onderen; zijde onbekend."),
    25: ("DETAIL", "Detail ramen en balkondeur aan houten dakschild", "DETAIL_ONLY", [], True, "Beeld 90 graden gedraaid weergegeven; zijde onbekend."),
    26: ("DETAIL", "Detail raam en deur aan houten betimmering", "DETAIL_ONLY", [], True, "Beeld 90 graden gedraaid weergegeven; zijde onbekend."),
    27: ("DETAIL", "Detail ramen onder de dakgoot met schoorstenen, van onderen", "DETAIL_ONLY", [], False, "Zijde niet vast te stellen; gelijkenis met bovenverdieping voorzijde is een hypothese."),
    28: ("DETAIL", "Detail twee ramen met open draaideel en houten betimmering", "DETAIL_ONLY", [], False, "Zijde onbekend."),
    29: ("DETAIL", "Entreemuur met plaat 248 en raam, voorgevelzijde waarschijnlijk", "DETAIL_ONLY", [248], False, "Plaat 248 leesbaar; zijde FRONT_PROBABLE (entreemuur zoals op foto 2)."),
    30: ("DETAIL", "Entree met trap en plaat 244, voorgevelzijde waarschijnlijk", "DETAIL_ONLY", [244], False, "Plaat 244 leesbaar; tegenlicht en bladeren."),
    31: ("FRONT_OBLIQUE", "Voorgevel schuin met entreemuur 250", "FRAME_ANNOTATION_MEDIUM", [250], False, "Plaat 250 leesbaar; lensflare linksboven."),
    32: ("FRONT_OBLIQUE", "Voorgevel schuin met entreemuur 266 en open raamvleugel", "FRAME_ANNOTATION_MEDIUM", [266], False, "Plaat 266 leesbaar; struiken voor de begane grond."),
    33: ("DETAIL", "Raamdetail met plaat 276 (houten kozijn, verwering zichtbaar)", "DETAIL_ONLY", [276], False, "Plaat onder het raam; plaat bewijst het adres van de muur, niet automatisch dat het raam bij 276 hoort."),
    34: ("DETAIL", "Entreemuur met plaat 258, dakvlak en balkon, 90 graden gedraaid", "DETAIL_ONLY", [258], True, "Beeld 90 graden gedraaid weergegeven; plaat 258 leesbaar."),
    35: ("DETAIL", "Raamdetail met plaat 270", "DETAIL_ONLY", [270], False, "Plaat 270 rechtsboven het raam; zelfde voorbehoud over elementtoewijzing."),
    36: ("DETAIL", "Raamdetail met plaat 268 en kippengaas", "DETAIL_ONLY", [268], False, "Plaat 268 links naast het raam; zelfde voorbehoud over elementtoewijzing."),
}

# bestaande repo-foto's tegenover de archieffoto's (Pearson-correlatie op 128x96 grijswaarden na autocontrast; gemeten bij deze audit)
SOURCE_MATCHES = [
    {"existing_photo": "maldenhof_2", "archive_photo": "MAP-002", "pearson": 1.0, "status": "SAME_SOURCE_PHOTO_VISUAL_MATCH", "byte_identical": False,
     "note": "Zelfde opname, ander bestand (herbewerkt/herencodeerd; SHA256 verschilt). Foto-2 besluiten en instances blijven gebaseerd op maldenhof_2.jpg."},
    {"existing_photo": "maldenhof_3", "archive_photo": "MAP-015", "pearson": 1.0, "status": "SAME_SOURCE_PHOTO_VISUAL_MATCH", "byte_identical": False,
     "note": "maldenhof_3.jpg is een verkleinde versie van P1000254.JPG (3264x2448). Pand van foto 3 blijft NOT_PROVEN."},
    {"existing_photo": "maldenhof_1", "archive_photo": None, "pearson": 0.598, "status": "NO_SOURCE_MATCH_IN_ARCHIVE", "byte_identical": False,
     "note": "Beste archiefkandidaat is MAP-001 (andere opname, andere camerapositie); maldenhof_1 blijft CONTEXT_ONLY."},
]

# overlap tussen archieffoto's: nooit automatisch samengevoegd
OVERLAPS = [
    ("SOC-001", ["MAP-002", "MAP-003"], "Plaat 288 en aangrenzende voorgevel in beide frames.", "MEDIUM"),
    ("SOC-002", ["MAP-003", "MAP-004", "MAP-009"], "Platen 276/278/280 in meerdere frames (MAP-003 en MAP-004: 276, 278, 280; MAP-009: 280).", "MEDIUM"),
    ("SOC-003", ["MAP-003", "MAP-013"], "Platen 288/286 en bijbehorende ramen in beide frames.", "MEDIUM"),
    ("SOC-004", ["MAP-005", "MAP-006"], "Zelfde stuk straatzijde met aanhanger/kozijnen rond de platen 258-262 (visuele gelijkenis).", "LOW"),
    ("SOC-005", ["MAP-005", "MAP-034"], "Plaat 258 in beide frames.", "MEDIUM"),
    ("SOC-006", ["MAP-008", "MAP-032"], "Plaat 266 in beide frames.", "MEDIUM"),
    ("SOC-007", ["MAP-008", "MAP-036"], "Plaat 268 met raam met kippengaas in beide frames.", "HIGH"),
    ("SOC-008", ["MAP-004", "MAP-033"], "Plaat 276 met raam in beide frames (raamtoewijzing aan plaat niet bewezen).", "LOW"),
    ("SOC-009", ["MAP-014", "MAP-015"], "Zelfde dakkapel, dakschild en rode balkondeur vanuit twee opnamepunten; MAP-015 is de bron van maldenhof_3.", "HIGH"),
    ("SOC-010", ["MAP-017", "MAP-020"], "Tuinafscheiding en schuurtje met rood dak in beide frames.", "LOW"),
    ("SOC-011", ["MAP-018", "MAP-019"], "Balkon met rood kozijn en rode deuren in beide frames.", "LOW"),
    ("SOC-012", ["MAP-024", "MAP-028"], "Twee ramen met open draaidelen in houten betimmering in beide frames.", "MEDIUM"),
    ("SOC-013", ["MAP-023", "MAP-024"], "Raam met open boven-/draaideel in houten betimmering; hoek verschilt sterk.", "LOW"),
    ("SOC-014", ["MAP-025", "MAP-026"], "Houten dakschild met raam en deur in beide (gedraaide) frames.", "LOW"),
    ("SOC-015", ["MAP-007", "MAP-008", "MAP-009", "MAP-010"], "Aansluitende schuine opnamen van dezelfde voorgevelstrook; kozijnen kunnen in meerdere frames voorkomen.", "LOW"),
]

SHORTLIST = [
    ("MAP-003", "Frontaal 276-288, hoogste dekking voorgevel naast foto 2; overlap met MAP-002/004/013 expliciet markeren."),
    ("MAP-004", "Frontaal 274-280; sluit links aan op MAP-003."),
    ("MAP-005", "Frontaal 258-262: enige frontale foto van panden 6 en 7 (afdekking door lantaarn en aanhanger)."),
    ("MAP-013", "Schuin 286/288, dekking aan de hogere nummers van de rij."),
    ("MAP-008", "Schuin 266/268, enige schuine foto van pand 8 met twee platen."),
    ("MAP-009", "Schuin met plaat 280, tweede opname van het stuk rond 280."),
    ("MAP-031", "Schuin met plaat 250, enige foto van pand 4 met volledige gevelstrook."),
    ("MAP-032", "Schuin met plaat 266 en open raamvleugel; controleer overlap met MAP-008."),
    ("MAP-029", "Entreemuur met plaat 248 en raam, enige foto van pand 3."),
    ("MAP-014", "Achterzijde met dakkapel, balkons en rood kozijn; vult het beeld van maldenhof_3 links aan (pand NOT_PROVEN)."),
    ("MAP-018", "Achterzijde met rode deuren/balkons; onderste bouwlagen deels zichtbaar."),
    ("MAP-017", "Achterzijde met balkon en schuurtje; begane grond afgedekt."),
    ("MAP-019", "Achterzijde met balkon en dakramen (dakvlak dominant)."),
    ("MAP-020", "Achterzijde met dakramen en tuinhuis."),
    ("MAP-021", "Tuinzijde met dakkapel en veranda; afwijkend type, zijde nog onbekend."),
]


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def load_manifest():
    with open(MANIFEST, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build():
    rows = load_manifest()
    assert len(rows) == 36 and len(P) == 36
    addr = json.loads(ADDR.read_text())
    plate_to_pand = {a["huisnummer"]: a["bag_pand_id"] for a in addr["addresses"]}
    order = {p["bag_pand_id"]: p for p in addr["pand_order"]}
    photos = []
    for i, r in enumerate(rows, 1):
        side, view, use, plates, rotated, note = P[i]
        for n in plates:
            assert n in plate_to_pand, n
        panden = sorted({plate_to_pand[n] for n in plates}, key=lambda p: order[p]["order"])
        photos.append({
            "photo_id": f"MAP-{i:03d}", "original_file": r["bestand"], "zip_path": r["origineel_zip_pad"], "group_folder": r["groep"],
            "sha256": r["sha256"], "width_px": int(r["breedte_px"]), "height_px": int(r["hoogte_px"]), "bytes": int(r["bytes"]),
            "manifest_status": r["status"],
            "classification": {"facade_side": side, "view": view, "rotated_in_display": rotated, "method": "MANUAL_VISUAL_READING"},
            "usability": use, "visible_house_number_plates": plates,
            "plate_reading_basis": "Handmatige lezing; bij kleine platen vergroting nodig." if plates else None,
            "bag_pand_link": {
                "status": "PAND_PROVEN_BY_VISIBLE_PLATE_ONLY" if plates else "NOT_PROVEN",
                "bag_pand_ids": panden,
                "scope_note": ("Alleen de muur met de leesbare plaat is aan het pand gekoppeld; kozijnen/elementen krijgen geen pand tenzij apart bewezen. "
                               "Een plaat op een detail bewijst niet de rest van de fotoreeks.") if plates else "Geen leesbaar huisnummer; geen pandkoppeling."},
            "note": note,
        })
    pid = {p["photo_id"]: p for p in photos}
    for s in SHORTLIST:
        assert s[0] in pid
    for o in OVERLAPS:
        assert all(m in pid for m in o[1])

    # coverage matrix over de 15 panden
    cov = []
    for pand in sorted(order, key=lambda p: order[p]["order"]):
        plate_photos = [p for p in photos if pand in p["bag_pand_link"]["bag_pand_ids"]]
        nums = sorted({n for p in plate_photos for n in p["visible_house_number_plates"] if plate_to_pand[n] == pand})
        overview = [p["photo_id"] for p in plate_photos if p["usability"].startswith("FRAME_ANNOTATION")]
        detail = [p["photo_id"] for p in plate_photos if p["usability"] == "DETAIL_ONLY"]
        cov.append({
            "order": order[pand]["order"], "bag_pand_id": pand, "addresses": order[pand]["addresses"], "plates_seen": nums,
            "FRONT_ARCHIVE": {"state": ("PLATE_SEEN_IN_OVERVIEW_PHOTO" if overview else ("PLATE_SEEN_IN_DETAIL_PHOTO_ONLY" if detail else "NO_ARCHIVE_PHOTO_EVIDENCE")),
                              "overview_photo_ids": overview, "detail_photo_ids": detail,
                              "provenance": "Huisnummerplaat via BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1)." if plate_photos else None},
            "REAR_ARCHIVE": {"state": "NO_PROVEN_PHOTO", "photo_ids": []},
            "LEFT_RIGHT_SIDE_ARCHIVE": {"state": "NO_PROVEN_PHOTO", "photo_ids": []},
            "missing_coverage": ([] if overview else ["Geen frontale/schuine overzichtsfoto met leesbare plaat voor dit pand."]) + ["Achterzijde niet aan dit pand gekoppeld.", "Kopgevel/zijgevel niet aan dit pand gekoppeld."]})
    unassigned = [p["photo_id"] for p in photos if not p["visible_house_number_plates"]]
    ins = json.loads(INSTANCES.read_text())
    pv = ins["photo_visible_counts"]
    summary = {"panden_total": len(cov),
               "front_overview_with_plate": sum(c["FRONT_ARCHIVE"]["state"] == "PLATE_SEEN_IN_OVERVIEW_PHOTO" for c in cov),
               "front_detail_plate_only": sum(c["FRONT_ARCHIVE"]["state"] == "PLATE_SEEN_IN_DETAIL_PHOTO_ONLY" for c in cov),
               "front_no_evidence": sum(c["FRONT_ARCHIVE"]["state"] == "NO_ARCHIVE_PHOTO_EVIDENCE" for c in cov),
               "rear_proven": 0, "side_proven": 0}
    counts = {}
    for p in photos:
        counts[p["classification"]["facade_side"]] = counts.get(p["classification"]["facade_side"], 0) + 1
    use_counts = {}
    for p in photos:
        use_counts[p["usability"]] = use_counts.get(p["usability"], 0) + 1
    return {
        "audit_version": VERSION, "photo_count": len(photos),
        "accessibility_check": {
            "result": "ALL_36_ORIGINAL_IMAGES_ACCESSIBLE",
            "method": "Zip volledig geopend (testzip OK), alle 36 afbeeldingen gedecodeerd, SHA256, bytes en resolutie per bestand vergeleken met manifest.csv: 0 afwijkingen; alle contactbladen visueel gecontroleerd.",
            "source_zip": ZIP_NAME, "originals_in_repository": False,
            "originals_note": "De originelen staan niet in de repository (circa 61 MB); de zip blijft in het projectbestand. Het register + manifest bewijzen de bytes via SHA256. Originelen zijn niet gewijzigd."},
        "manifest_copy": str(MANIFEST.relative_to(ROOT)), "manifest_unmodified_copy": True,
        "photos": photos,
        "classification_counts": counts, "usability_counts": use_counts,
        "existing_photo_source_matches": SOURCE_MATCHES,
        "same_object_candidates": [{"group_id": g, "photo_ids": m, "basis": b, "confidence": c, "status": "SAME_OBJECT_CANDIDATE", "merged": False} for g, m, b, c in OVERLAPS],
        "deduplication": "NONE_AUTOMATIC",
        "photo2_comparison": {
            "photo": "maldenhof_2", "archive_source": "MAP-002",
            "existing_confirmed_counts": {"PHOTO_VISIBLE_FRAME_COUNT": pv.get("PHOTO_VISIBLE_FRAME_COUNT"), "PHOTO_VISIBLE_WINDOW_COUNT": pv.get("PHOTO_VISIBLE_WINDOW_COUNT"),
                                          "PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT": pv.get("PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"), "FULL": pv.get("ordinary_frames_FULL"), "PARTIAL": pv.get("ordinary_frames_PARTIAL")},
            "archive_photos_overlapping_photo2_scene": ["MAP-003"],
            "result": "Geen wijziging aan besluiten of instances; MAP-002 is dezelfde opname als maldenhof_2. MAP-003 overlapt mogelijk met kozijnen rond plaat 288 (SOC-001) en wordt niet als extra kozijnen geteld.",
            "photo2_decisions_changed": False, "photo2_instances_changed": False},
        "coverage_matrix": {"definition": "Voorlopige dekking: alleen of een foto met leesbare plaat per pand bestaat. Geen compleetheid van kozijnen; geen FULL_COVERAGE-claim.",
                            "panden": cov, "summary": summary, "unassigned_photo_ids_without_plate": unassigned,
                            "note_unassigned": "Foto's zonder leesbare plaat (inclusief alle achterzijde/dak/detailfoto's zonder plaat en maldenhof_3/MAP-015) zijn niet aan een pand gekoppeld."},
        "shortlist": [{"rank": i, "photo_id": pid_, "reason": r, "photo_file": pid[pid_]["original_file"], "usability": pid[pid_]["usability"]} for i, (pid_, r) in enumerate(SHORTLIST, 1)],
        "shortlist_note": "Maximaal 15; MAP-002 (bron foto 2) en MAP-015 (bron foto 3) zijn al geannoteerd en staan er niet op.",
        "contact_sheets": [f"reports/frames/photo_archive_audit_v1/{SHEET_PREFIX}{n}.jpg" for n in (1, 2, 3)],
        "effects": {"new_confirmed_instances": 0, "frame_instances_created": 0, "building_totals": None, "repeat_multipliers": None, "metric_dimensions": None, "painting_area": None,
                    "kg_price_changes": False, "mjop_app_updates": False, "quantity_resolutions": 0, "human_decisions_added": 0,
                    "comparability_756_80": "NOT_COMPARABLE"},
        "stop": "STOP voor menselijke goedkeuring of instance-activatie.",
    }


def render_md(a):
    L = ["# Maldenhof Photo Archive Audit v1", "",
         f"36 originele foto's uit `{ZIP_NAME}` geregistreerd (ID MAP-001..036). Alle afbeeldingen zijn werkelijk toegankelijk en per bestand gecontroleerd tegen het manifest (SHA256, bytes en resolutie: 0 afwijkingen). Geen originelen gewijzigd, niet in de repository.", "",
         "Dit is een register en voorlopige dekking, geen inventaris: geen nieuwe instances, geen totalen, geen maten.", "",
         "## Bronnen en bestaande foto's", ""]
    for m in a["existing_photo_source_matches"]:
        L.append(f"- {m['existing_photo']} ↔ {m['archive_photo'] or 'geen'}: {m['status']} (Pearson {m['pearson']}). {m['note']}")
    L += ["", "## Register", "", "| ID | Bestand | Zijde | Gebruik | Platen | Pand-koppeling | px |", "|---|---|---|---|---|---|---|"]
    for p in a["photos"]:
        pl = ", ".join(map(str, p["visible_house_number_plates"])) or "-"
        L.append(f"| {p['photo_id']} | {p['original_file']} | {p['classification']['facade_side']} | {p['usability']} | {pl} | {p['bag_pand_link']['status']} | {p['width_px']}x{p['height_px']} |")
    L += ["", "Classificatie en platen zijn handmatige visuele lezing; plaat bewijst alleen de gekoppelde muur, niet de rest van de fotoreeks of een raam.", "",
          "## Mogelijke overlap (SAME_OBJECT_CANDIDATE, niet samengevoegd)", "", "| Groep | Foto's | Basis | Zekerheid |", "|---|---|---|---|"]
    for g in a["same_object_candidates"]:
        L.append(f"| {g['group_id']} | {', '.join(g['photo_ids'])} | {g['basis']} | {g['confidence']} |")
    c = a["photo2_comparison"]["existing_confirmed_counts"]
    L += ["", "## Vergelijking met foto 2", "",
          f"Bestaand bevroren: {c['PHOTO_VISIBLE_FRAME_COUNT']} zichtbare kozijnopeningen, {c['PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT']} buitendeur, {c['FULL']} FULL en {c['PARTIAL']} PARTIAL. {a['photo2_comparison']['result']}", "",
          "## Voorlopige coverage matrix (15 panden)", "", a["coverage_matrix"]["definition"], "",
          "| # | Pand | Adressen | Platen gezien | Voorzijde (archief) | Achter | Zijkant |", "|---|---|---|---|---|---|---|"]
    for p in a["coverage_matrix"]["panden"]:
        f = p["FRONT_ARCHIVE"]
        ph = ", ".join(f["overview_photo_ids"] + f["detail_photo_ids"]) or "-"
        L.append(f"| {p['order']} | {p['bag_pand_id']} | {', '.join(map(str, p['addresses']))} | {', '.join(map(str, p['plates_seen'])) or '-'} | {f['state']} ({ph}) | {p['REAR_ARCHIVE']['state']} | {p['LEFT_RIGHT_SIDE_ARCHIVE']['state']} |")
    s = a["coverage_matrix"]["summary"]
    L += ["", f"Samenvatting: {s['front_overview_with_plate']} panden met plaat in een overzichtsfoto, {s['front_detail_plate_only']} alleen in een detailfoto, {s['front_no_evidence']} zonder archiefbewijs; achterzijde en zijkant bewezen voor 0 panden.", "",
          "Ontbrekende dekking: zie `missing_coverage` per pand in de JSON. Achter-, dak- en detailfoto's zonder plaat (en MAP-015/maldenhof_3) blijven NOT_PROVEN.", "",
          "## Shortlist vervolgannotatie (max 15)", ""]
    for r in a["shortlist"]:
        L.append(f"{r['rank']}. {r['photo_id']} ({r['photo_file']}, {r['usability']}): {r['reason']}")
    L += ["", a["shortlist_note"], "", "## Contactbladen", ""] + [f"- `{x}`" for x in a["contact_sheets"]]
    L += ["", "## Niet gedaan", "", "Geen nieuwe instances, building totals, repeat multipliers, maten, painting area, KG/prijswijzigingen of App-updates; geen menselijke besluiten toegevoegd; 756,80 m2 blijft NOT_COMPARABLE.", "", a["stop"], ""]
    return "\n".join(L)


def contact_sheets(zip_path, photos):
    from PIL import Image, ImageDraw
    z = zipfile.ZipFile(zip_path)
    per, cols, tw, th, head = 12, 4, 480, 360, 22
    for si in range(3):
        chunk = photos[si * per:(si + 1) * per]
        sh = Image.new("RGB", (cols * tw, 3 * (th + head)), "white")
        d = ImageDraw.Draw(sh)
        for k, p in enumerate(chunk):
            im = Image.open(io.BytesIO(z.read(f"{p['group_folder']}/{p['original_file']}"))).convert("RGB")
            im.thumbnail((tw, th))
            x, y = (k % cols) * tw, (k // cols) * (th + head)
            sh.paste(im, (x, y + head))
            d.text((x + 4, y + 5), f"{p['photo_id']}  {p['original_file']}  {p['classification']['facade_side']}", fill="black")
        sh.save(OUT_DIR / f"{SHEET_PREFIX}{si + 1}.jpg", quality=72, optimize=True)


def verify_zip(zip_path, photos):
    z = zipfile.ZipFile(zip_path)
    assert z.testzip() is None
    from PIL import Image
    for p in photos:
        b = z.read(f"{p['group_folder']}/{p['original_file']}")
        assert sha256(b) == p["sha256"] and len(b) == p["bytes"], p["photo_id"]
        assert Image.open(io.BytesIO(b)).size == (p["width_px"], p["height_px"]), p["photo_id"]


def dump(o):
    return json.dumps(o, indent=2, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--zip")
    a = ap.parse_args()
    audit = build()
    outs = {OUT_JSON: dump(audit), OUT_MD: render_md(audit)}
    if a.zip:
        verify_zip(a.zip, audit["photos"])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        contact_sheets(a.zip, audit["photos"])
        print("zip verified; contact sheets written")
    if a.check:
        bad = [str(p) for p, t in outs.items() if not p.exists() or p.read_text() != t]
        print("OUT OF DATE: " + ", ".join(bad) if bad else "OK")
        return 1 if bad else 0
    for p, t in outs.items():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(t)
    print("written", OUT_JSON.name, OUT_MD.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
