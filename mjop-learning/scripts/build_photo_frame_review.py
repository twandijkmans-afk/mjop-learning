"""Maldenhof Frame Photo Human Review v1.

1. Legt de door de gebruiker goedgekeurde menselijke review-besluiten over photo observations vast in een append-only store
   (data/photo_evidence/maldenhof_photo_human_review_v1.json). Bestaande evidence (maldenhof_photo_evidence_v1.json) blijft ongewijzigd.
2. Bouwt de handmatige annotatie van maldenhof_2.jpg (data/photo_evidence/maldenhof_2_frame_annotation_v1.json): kandidaat-openingen
   met genormaliseerde bbox, alles REVIEW_REQUIRED. De bboxes zijn een handmatige visuele lezing (MANUAL_VISUAL_READING), GEEN
   automatische detectie. Geen maten, geen oppervlakken, geen gebouwtotaal, geen frame instances.
3. Genereert overlay (PNG), review sheet en rapport onder reports/frames/photo_review_v1/.

Deterministisch; de review store is idempotent en append-only.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "data" / "photo_evidence" / "maldenhof_photo_evidence_v1.json"
REVIEW_STORE = ROOT / "data" / "photo_evidence" / "maldenhof_photo_human_review_v1.json"
ANNOTATION = ROOT / "data" / "photo_evidence" / "maldenhof_2_frame_annotation_v1.json"
PHOTO_2 = ROOT / "data" / "photos" / "incoming" / "maldenhof" / "maldenhof_2.jpg"
OUT_DIR = ROOT / "reports" / "frames" / "photo_review_v1"
OVERLAY = OUT_DIR / "maldenhof_2_frame_overlay.png"
SHEET = OUT_DIR / "maldenhof_2_review_sheet.md"
REPORT = OUT_DIR / "maldenhof_photo_frame_review_v1.md"
VERSION = "photo_frame_review_v1.0.0"
REVIEWER_ID = "user-approved"
REVIEWED_AT = "2026-10-06T12:02:45Z"

# observation_id -> (decision, reason); precies de door de gebruiker genoemde observaties.
_DORMER = "Dakkapel zichtbaar. Nog geen automatische koppeling aan EXTERIOR_FRAME quantity."
_ROOFWIN = "Dakraam zichtbaar. Dit bewijst aanwezigheid op de foto, niet het totaal voor het gebouw."
USER_DECISIONS = [
    ("PHO-M-001", "ACCEPT", "Huisnummers 288 en 290 zijn zichtbaar en vallen binnen de bevestigde Maldenhof 240-296 building scope."),
    ("PHO-M-002", "ACCEPT_OBSERVATION", "Foto 2 toont meerdere buitenkozijnen/ramen. De observatie bewijst zichtbare frame/window presence, maar nog geen betrouwbaar totaal aantal, materiaal of maat."),
    ("PHO-M-008", "ACCEPT_OBSERVATION", "Foto 1 toont een herhalend buitenkozijn-/raampatroon, maar perspectief en begroeiing verhinderen betrouwbare individuele telling."),
    ("PHO-M-016", "ACCEPT_OBSERVATION", "Foto 3 toont buitenkozijnen aan de achterzijde; delen zijn verborgen."),
    ("PHO-M-015", "ACCEPT_OBSERVATION", "Foto 3 toont een buitendeur. Type en materiaal blijven UNKNOWN."),
    ("PHO-M-003", "ACCEPT_OBSERVATION", _DORMER), ("PHO-M-009", "ACCEPT_OBSERVATION", _DORMER), ("PHO-M-013", "ACCEPT_OBSERVATION", _DORMER),
    ("PHO-M-004", "ACCEPT_OBSERVATION", _ROOFWIN), ("PHO-M-010", "ACCEPT_OBSERVATION", _ROOFWIN), ("PHO-M-014", "ACCEPT_OBSERVATION", _ROOFWIN),
]
DECISIONS = {"ACCEPT", "ACCEPT_OBSERVATION"}

PHOTO_ROLES = {"maldenhof_1": "CONTEXT_ONLY", "maldenhof_2": "FIRST_FRAME_ANNOTATION_SOURCE", "maldenhof_3": "REAR_DETAIL"}

# --- annotatie maldenhof_2.jpg -----------------------------------------------------------------------------------------
# bbox in beeldpixels van een 2000x1500 weergave van de 2048x1536 foto (zelfde beeldverhouding); opgeslagen genormaliseerd.
BASE_W, BASE_H = 2000.0, 1500.0
UPPER = "Bovenste gevelrij direct onder de dakgoot; bouwlaag niet vast te stellen met de toegestane waarden"

# (suffix, type, bbox px, storey, visibility, occlusion reason, address hint, module, parent, note)
RAW = [
    (1, "WINDOW", (553, 505, 750, 615), "UNKNOWN", "PARTIAL", "Lantaarnpaal en boom verbergen het linkerdeel; twee geopende vleugels", None, "A", None, UPPER),
    (2, "WINDOW", (940, 528, 997, 615), "UNKNOWN", "FULL", None, None, "A", None, UPPER + "; smalle draaivleugel links van het hoofdkozijn, mogelijk eigen kozijn"),
    (3, "WINDOW", (1028, 530, 1195, 618), "UNKNOWN", "FULL", None, None, "A", None, UPPER + "; hoofdkozijn met geopende vleugel rechts"),
    (4, "WINDOW", (1308, 535, 1452, 620), "UNKNOWN", "FULL", None, None, "B", None, UPPER),
    (5, "WINDOW", (1483, 535, 1540, 620), "UNKNOWN", "FULL", None, None, "B", None, UPPER + "; losse draaivleugel naast kozijn 004, mogelijk onderdeel daarvan"),
    (6, "WINDOW", (1718, 523, 1950, 622), "UNKNOWN", "FULL", None, None, "B", None, UPPER + "; kozijn met geopende vleugels en gordijn"),
    (7, "WINDOW", (1055, 708, 1195, 832), "FIRST", "FULL", None, None, "A", None, "Kozijn met wit onderpaneel; terugliggend gevelvlak"),
    (8, "WINDOW", (1345, 710, 1505, 832), "FIRST", "PARTIAL", "Takken van struik voor de linkerrand", None, "B", None, "Kozijn met wit onderpaneel; terugliggend gevelvlak"),
    (9, "WINDOW", (1912, 912, 1995, 995), "GROUND", "FULL", None, "Maldenhof 288", "B", None, "Klein kozijn met vitrage direct rechts van huisnummerplaat 288"),
    (10, "UNKNOWN_OPENING", (928, 908, 1012, 968), "GROUND", "HEAVILY_OCCLUDED", "Takken en struiken voor een lichte opening boven de entree bij nummer 290", "Maldenhof 290", "A", None, "Opening bij entree 290; type (raam/glas in deur) niet te bepalen"),
    (11, "EXTERIOR_DOOR", (720, 905, 885, 1150), "GROUND", "PARTIAL", "Donkere entree onder portiek, schaduw, struiken en lantaarnpaal", "Maldenhof 290", "A", None, "Donkere deur/trap onder het portiek links van het baksteen met nummer 290; materiaal en type onbekend"),
    (12, "UNKNOWN_OPENING", (1213, 930, 1245, 1012), "GROUND", "HEAVILY_OCCLUDED", "Dichte struiken voor smalle lichte strook rechts van de muur met nummer 290", None, "A", None, "Mogelijk glasstrook of deur; niet te bepalen"),
    (13, "UNKNOWN_OPENING", (1310, 925, 1515, 985), "GROUND", "HEAVILY_OCCLUDED", "Struiken en bergkast verbergen het gevelvlak; alleen een lichte band (dorpel/kozijnrand) zichtbaar", None, "B", None, "Alleen afgeleid uit lichte horizontale band; kan ook geen opening zijn"),
    (14, "ROOF_WINDOW", (555, 370, 625, 415), "ROOF", "FULL", None, None, "A", None, "Dakraam bovendakvlak links; tegenlicht"),
    (15, "ROOF_WINDOW", (1300, 388, 1368, 432), "ROOF", "FULL", None, None, "B", None, "Dakraam bovendakvlak midden-rechts"),
    (16, "ROOF_WINDOW", (1787, 393, 1860, 438), "ROOF", "FULL", None, None, "B", None, "Dakraam bovendakvlak rechts"),
    (17, "ROOF_WINDOW", (765, 732, 875, 800), "ROOF", "FULL", None, None, "A", None, "Dakraam op het lagere dakschild boven portiek 290"),
    (18, "ROOF_WINDOW", (1763, 737, 1900, 810), "ROOF", "FULL", None, None, "B", None, "Dakraam op het lagere dakschild boven entree 288"),
    (19, "WINDOW", (1040, 352, 1178, 440), "ROOF", "FULL", None, None, "A", "DORMER-M2-001", "Drie-delig kozijn in de dakkapel (PHO-M-003); wordt als dakkapelraam apart gerapporteerd"),
]
DORMER_OBJECT = {"object_id": "DORMER-M2-001", "object_type": "ROOF_DORMER", "bbox_norm": [round(1022 / BASE_W, 4), round(330 / BASE_H, 4), round(1192 / BASE_W, 4), round(452 / BASE_H, 4)],
                 "related_observation": "PHO-M-003", "counts_as_window_candidate": False,
                 "note": "Dakkapel zelf; geen EXTERIOR_FRAME quantity-koppeling."}
DUPLICATE_GROUPS = [
    {"group_id": "DUP-M2-001", "candidate_ids": ["FC-M2-002", "FC-M2-003"], "status": "DUPLICATE_REVIEW_REQUIRED",
     "question": "Zijn 002 (smalle vleugel) en 003 (hoofdkozijn) hetzelfde fysieke kozijn of twee kozijnen?"},
    {"group_id": "DUP-M2-002", "candidate_ids": ["FC-M2-004", "FC-M2-005"], "status": "DUPLICATE_REVIEW_REQUIRED",
     "question": "Zijn 004 (kozijn) en 005 (losse vleugel) hetzelfde fysieke kozijn of twee kozijnen?"},
]
MODULES = [
    {"module_id": "MOD-M2-A", "label": "Module A: omgeving huisnummer 290", "anchor": "huisnummerplaat 290",
     "x_range_norm": [round(460 / BASE_W, 4), round(1250 / BASE_W, 4)]},
    {"module_id": "MOD-M2-B", "label": "Module B: omgeving huisnummer 288", "anchor": "huisnummerplaat 288",
     "x_range_norm": [round(1250 / BASE_W, 4), 1.0]},
]
COVERAGE_GAPS = [
    "Begane grond links (x < 0,35): lantaarnpaal, fiets, boom en struiken verbergen alle gevelopeningen links van het portiek.",
    "Begane grond midden (x 0,45-0,80): struiken, fietsen en houten bergkasten verbergen het gevelvlak tussen de muren van 290 en 288; mogelijke ramen/deuren (FC-M2-012/013) zijn niet te beoordelen.",
    "Entree 290: deur en trap liggen in schaduw onder het portiek; alleen een donkere deuropening zichtbaar.",
    "Entree 288: de entree rechts bij nummer 288 is niet zichtbaar (struiken, muur, buiten beeld rechts).",
    "Rechterrand: de foto snijdt het gebouw af; de gevel loopt rechts door buiten beeld (naastliggende woningen niet geannoteerd).",
    "Linkerrand: een naastliggend bouwblok (kozijn en dakraam bij x < 0,05) is niet geannoteerd; waarschijnlijk buiten Maldenhof 240-296.",
    "Tegenlicht rechtsboven en bij de linker dakraam maakt dakramen minder goed leesbaar.",
    "De bouwlaag van de bovenste gevelrij is niet vast te stellen met GROUND/FIRST/ROOF/UNKNOWN; die ramen staan op UNKNOWN.",
    "Achterzijde, dakvlakken achter en zijgevels ontbreken volledig op foto 2 (zie foto 3 voor achterdetail; niet gecombineerd).",
]


def norm(b):
    return [round(b[0] / BASE_W, 4), round(b[1] / BASE_H, 4), round(b[2] / BASE_W, 4), round(b[3] / BASE_H, 4)]


def build_candidates():
    dup = {c: g["group_id"] for g in DUPLICATE_GROUPS for c in g["candidate_ids"]}
    out = []
    for n, ctype, bbox, storey, vis, occ, addr, module, parent, note in RAW:
        cid = f"FC-M2-{n:03d}"
        out.append({
            "candidate_id": cid, "photo": "maldenhof_2.jpg", "candidate_type": ctype, "bbox_norm": norm(bbox),
            "bag_address_scope_hint": addr, "storey": storey, "visibility": vis, "occlusion_reason": occ,
            "parent": ({"type": "ROOF_DORMER", "ref": parent} if parent else None), "module_hint": f"MOD-M2-{module}",
            "duplicate_review": ("DUPLICATE_REVIEW_REQUIRED" if cid in dup else None), "duplicate_group": dup.get(cid),
            "note": note, "annotation_method": "MANUAL_VISUAL_READING", "review_status": "REVIEW_REQUIRED", "human_decision": "PENDING",
        })
    return out


def category(c):
    if c["candidate_type"] == "ROOF_WINDOW":
        return "ROOF_WINDOW"
    if c["candidate_type"] == "WINDOW" and c["parent"]:
        return "DORMER_WINDOW"
    if c["candidate_type"] == "WINDOW":
        return "WINDOW_" + ("FULL" if c["visibility"] == "FULL" else "PARTIAL")
    return c["candidate_type"]


def summarize(cands):
    cats = {}
    for c in cands:
        cats.setdefault(category(c), []).append(c["candidate_id"])
    dup_ids = {i for g in DUPLICATE_GROUPS for i in g["candidate_ids"]}
    full_w = cats.get("WINDOW_FULL", [])
    counts = {
        "count_basis": "VISIBLE_COUNT_ON_PHOTO", "photo": "maldenhof_2.jpg", "is_building_total": False,
        "VISIBLE_WINDOW_CANDIDATE_COUNT": sum(len(cats.get(k, [])) for k in ("WINDOW_FULL", "WINDOW_PARTIAL")),
        "FULL_VISIBLE_WINDOWS": len(full_w), "PARTIAL_WINDOWS": len(cats.get("WINDOW_PARTIAL", [])),
        "EXTERIOR_DOORS": len(cats.get("EXTERIOR_DOOR", [])), "ROOF_WINDOWS": len(cats.get("ROOF_WINDOW", [])),
        "DORMER_WINDOWS": len(cats.get("DORMER_WINDOW", [])), "UNKNOWN_OPENINGS": len(cats.get("UNKNOWN_OPENING", [])),
        "TOTAL_ANNOTATION_CANDIDATES": len(cands),
        "FULL_WINDOWS_IN_DUPLICATE_REVIEW": len([i for i in full_w if i in dup_ids]),
        "FULL_WINDOWS_IF_DUPLICATE_GROUPS_COUNT_ONCE": len(full_w) - len([i for i in full_w if i in dup_ids]) + len(DUPLICATE_GROUPS),
        "candidate_ids_by_category": cats,
    }
    return counts


def module_comparison(cands):
    rows = []
    for m in MODULES:
        mine = [c for c in cands if c["module_hint"] == m["module_id"]]
        rows.append({"module_id": m["module_id"],
                     "facade_windows": len([c for c in mine if category(c).startswith("WINDOW_")]),
                     "exterior_doors": len([c for c in mine if c["candidate_type"] == "EXTERIOR_DOOR"]),
                     "unknown_openings": len([c for c in mine if c["candidate_type"] == "UNKNOWN_OPENING"]),
                     "roof_windows": len([c for c in mine if c["candidate_type"] == "ROOF_WINDOW"]),
                     "dormer_windows": len([c for c in mine if category(c) == "DORMER_WINDOW"]),
                     "candidate_ids": [c["candidate_id"] for c in mine]})
    return rows


def build_annotation():
    ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    p2 = next(p for p in ev["photos"] if p["photo_id"] == "maldenhof_2")
    cands = build_candidates()
    cmp_rows = module_comparison(cands)
    return {
        "builder_version": VERSION, "photo": {"photo_id": "maldenhof_2", "path": p2["path"], "sha256": p2["sha256"], "role": "FIRST_FRAME_ANNOTATION_SOURCE"},
        "photo_roles": PHOTO_ROLES,
        "annotation_method": "MANUAL_VISUAL_READING",
        "annotation_note": "Handmatige visuele lezing van de foto door Claude; geen automatische detectie en geen foto-AI-model. Alle kandidaten wachten op menselijke review.",
        "coordinate_system": "bbox_norm = [x1, y1, x2, y2] genormaliseerd 0..1 over de beeldbreedte/-hoogte, oorsprong linksboven. Alleen beeldcoordinaten.",
        "metric_scale": "NONE_PROVEN",
        "no_scale_note": "Geen deurstandaardmaat, baksteenmaat of BAG-hoogte als kalibratie; geen afmetingen en oppervlakken.",
        "candidates": cands, "context_objects": [DORMER_OBJECT], "duplicate_groups": DUPLICATE_GROUPS,
        "visible_counts": summarize(cands),
        "repeat_modules": {"status": "REPEAT_CANDIDATE", "active": False, "multiplier": None, "user_confirmed_repeat": False,
                           "modules": MODULES, "comparison": cmp_rows,
                           "conclusion": "Module A en B vertonen een mogelijk gespiegelde opbouw (lager dakschild met dakraam, terugliggend kozijn, bakstenen entreemuur met huisnummer), maar de zichtbare inhoud is niet gelijk; geen multiplier en geen USER_CONFIRMED_REPEAT."},
        "coverage_gaps": COVERAGE_GAPS,
        "frame_inventory_effect": "NONE: geen frame instances/groups aangemaakt; kandidaten blijven REVIEW_REQUIRED.",
    }


def validate_annotation(doc):
    ids = [c["candidate_id"] for c in doc["candidates"]]
    assert len(ids) == len(set(ids)), "candidate_id niet uniek"
    allowed_types = {"WINDOW", "EXTERIOR_DOOR", "UNKNOWN_OPENING", "ROOF_WINDOW"}
    for c in doc["candidates"]:
        x1, y1, x2, y2 = c["bbox_norm"]
        assert 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1, c["candidate_id"]
        assert c["candidate_type"] in allowed_types and c["storey"] in {"GROUND", "FIRST", "ROOF", "UNKNOWN"}
        assert c["visibility"] in {"FULL", "PARTIAL", "HEAVILY_OCCLUDED"}
        assert c["review_status"] == "REVIEW_REQUIRED" and c["human_decision"] == "PENDING"
        assert not ({"width_m", "height_m", "area_m2"} & set(c))
        if c["visibility"] != "FULL":
            assert c["occlusion_reason"], c["candidate_id"]


# --- review store (append-only) -----------------------------------------------------------------------------------------
def new_store():
    return {"store_version": "photo_human_review_v1", "append_only": True,
            "note": "Menselijke review-besluiten over photo observations. Records worden nooit overschreven; correcties gaan via supersedes.",
            "records": []}


def apply_decisions(store):
    """Voegt ontbrekende besluiten toe; bestaande records blijven ongewijzigd (idempotent)."""
    have = {r["observation_id"] for r in store["records"] if r["status"] == "ACTIVE"}
    for obs, decision, reason in USER_DECISIONS:
        if obs in have:
            continue
        store["records"].append({
            "decision_id": f"PHR-{len(store['records']) + 1:05d}", "observation_id": obs, "decision": decision, "reason": reason,
            "reviewer_type": "human", "reviewer_id": REVIEWER_ID, "reviewed_at": REVIEWED_AT, "supersedes": None, "status": "ACTIVE"})
    return store


def append_only_errors(old, new):
    errs = []
    n = {r["decision_id"]: r for r in new["records"]}
    for r in old["records"]:
        if n.get(r["decision_id"]) != r:
            errs.append(r["decision_id"])
    return errs


def effective_status(evidence, store):
    active = {r["observation_id"]: r for r in store["records"] if r["status"] == "ACTIVE"}
    out = []
    for o in evidence["observations"]:
        r = active.get(o["observation_id"])
        out.append((o, r))
    return out


# --- overlay / rapport --------------------------------------------------------------------------------------------------
COLORS = {"WINDOW": (46, 204, 113), "ROOF_WINDOW": (0, 200, 255), "EXTERIOR_DOOR": (255, 0, 200), "UNKNOWN_OPENING": (255, 255, 255)}
DORMER_COLOR = (255, 140, 0)


def render_overlay(doc):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(PHOTO_2).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    def box(b, col, dashed, w=4):
        x1, y1, x2, y2 = b[0] * W, b[1] * H, b[2] * W, b[3] * H
        if not dashed:
            d.rectangle([x1, y1, x2, y2], outline=col, width=w)
            return x1, y1
        step = 14
        for x in range(int(x1), int(x2), step * 2):
            d.line([x, y1, min(x + step, x2), y1], fill=col, width=w)
            d.line([x, y2, min(x + step, x2), y2], fill=col, width=w)
        for y in range(int(y1), int(y2), step * 2):
            d.line([x1, y, x1, min(y + step, y2)], fill=col, width=w)
            d.line([x2, y, x2, min(y + step, y2)], fill=col, width=w)
        return x1, y1

    do = DORMER_OBJECT["bbox_norm"]
    box(do, DORMER_COLOR, True, 3)
    for c in doc["candidates"]:
        col = DORMER_COLOR if c["parent"] else COLORS[c["candidate_type"]]
        dashed = c["visibility"] != "FULL"
        x, y = box(c["bbox_norm"], col, dashed)
        vis = {"FULL": "FULL", "PARTIAL": "PARTIAL", "HEAVILY_OCCLUDED": "OCCL"}[c["visibility"]]
        tp = {"WINDOW": "W", "ROOF_WINDOW": "RW", "EXTERIOR_DOOR": "DOOR", "UNKNOWN_OPENING": "UNK"}[c["candidate_type"]]
        if c["parent"]:
            tp = "DORMER-W"
        label = f"{c['candidate_id'][-3:]} {tp} {vis}" + (" *" if c["duplicate_review"] else "")
        tw = d.textlength(label, font=font)
        x = min(x, W - tw - 12)
        below = c["candidate_id"][-3:] in {"002", "005", "010", "012"}
        ly = (c["bbox_norm"][3] * H + 3) if below else (y - 28 if y > 30 else y + 4)
        d.rectangle([x, ly, x + tw + 8, ly + 26], fill=(0, 0, 0, 190))
        d.text((x + 4, ly + 1), label, fill=col, font=font)
    # legenda
    leg = ["Handmatige annotatie (REVIEW_REQUIRED) - bbox = beeldcoordinaten, geen maten",
           "* = DUPLICATE_REVIEW_REQUIRED. Doorgetrokken = FULL, gestippeld = PARTIAL/OCCL; groen=raam, cyaan=dakraam, magenta=deur, wit=onbekend, oranje=dakkapel"]
    d.rectangle([0, H - 62, W, H], fill=(0, 0, 0, 200))
    for i, t in enumerate(leg):
        d.text((10, H - 58 + i * 28), t, fill=(255, 255, 255), font=font)
    im = im.resize((1600, 1200), Image.LANCZOS)
    OVERLAY.parent.mkdir(parents=True, exist_ok=True)
    im.save(OVERLAY, optimize=True)


def render_sheet(doc):
    L = ["# Review sheet maldenhof_2.jpg (frame annotation v1)", "",
         "Handmatige visuele lezing; alle kandidaten REVIEW_REQUIRED. bbox = genormaliseerde beeldcoordinaten, geen maten. Dit is GEEN gebouwtotaal.", "",
         "| Candidate ID | Type | Storey | Visibility | Locatie/adres hint | Duplicate | Parent | Human decision |", "|---|---|---|---|---|---|---|---|"]
    for c in doc["candidates"]:
        hint = c["bag_address_scope_hint"] or "niet aantoonbaar"
        L.append(f"| {c['candidate_id']} | {c['candidate_type']} | {c['storey']} | {c['visibility']} | {hint}; {c['module_hint']} | "
                 f"{c['duplicate_group'] or '-'} | {c['parent']['type'] if c['parent'] else '-'} | PENDING |")
    L += ["", "Overlay: `reports/frames/photo_review_v1/maldenhof_2_frame_overlay.png`", ""]
    return "\n".join(L)


def render_report(doc, store, evidence):
    vc = doc["visible_counts"]
    L = ["# Maldenhof Frame Photo Human Review v1", "",
         "Scope: menselijke review van de 20 photo observations en handmatige annotatie van foto 2. Geen gebouwtotaal, geen maten, geen painting area, "
         "geen frame instances, geen quantity-resolutie, geen MJOP-App wijziging.", "",
         "## 1. Review decisions (append-only)", "", "| Decision | Observation | Besluit | Reviewer |", "|---|---|---|---|"]
    for r in store["records"]:
        L.append(f"| {r['decision_id']} | {r['observation_id']} | {r['decision']} | {r['reviewer_type']} ({r['reviewer_id']}), {r['reviewed_at']} |")
    left = [o["observation_id"] for o, r in effective_status(evidence, store) if r is None]
    L += ["", f"Geaccepteerd: {len(store['records'])} van 20. Niet gereviewd en dus nog REVIEW_REQUIRED / REPEAT_CANDIDATE: {', '.join(left)}.", "",
          "PHO-M-001 beantwoordt de open vraag: huisnummers 288 en 290 vallen binnen Maldenhof 240-296. ACCEPT_OBSERVATION bevestigt alleen dat het "
          "element op de foto zichtbaar is; het levert geen aantal, materiaal of maat op.", "",
          "## 2. Rol van de foto's", "", "- maldenhof_2.jpg: eerste telfoto (bijna frontaal, 288/290 zichtbaar).", "- maldenhof_1.jpg: CONTEXT_ONLY.",
          "- maldenhof_3.jpg: REAR_DETAIL.", "- Geen gecombineerde telling over de drie foto's.", "",
          "## 3. Annotatie foto 2 (handmatige lezing, geen automatische detectie)", "",
          f"{vc['TOTAL_ANNOTATION_CANDIDATES']} kandidaten, allemaal REVIEW_REQUIRED, human decision PENDING.", "",
          "### VISIBLE_COUNT_ON_PHOTO (maldenhof_2.jpg; NIET BUILDING_TOTAL)", "", "| Categorie | Aantal | Kandidaten |", "|---|---|---|"]
    cats = vc["candidate_ids_by_category"]
    names = [("WINDOW_FULL", "FULL visible windows"), ("WINDOW_PARTIAL", "PARTIAL windows"), ("EXTERIOR_DOOR", "Deuren (EXTERIOR_DOOR)"),
             ("ROOF_WINDOW", "Dakramen (ROOF_WINDOW)"), ("DORMER_WINDOW", "Dakkapelramen (parent ROOF_DORMER)"), ("UNKNOWN_OPENING", "UNKNOWN_OPENING (niet als raam geteld)")]
    for k, label in names:
        ids = cats.get(k, [])
        L.append(f"| {label} | {len(ids)} | {', '.join(i[-3:] for i in ids)} |")
    L += ["", f"VISIBLE_WINDOW_CANDIDATE_COUNT (gevelramen FULL + PARTIAL, zonder dakramen en dakkapelraam): {vc['VISIBLE_WINDOW_CANDIDATE_COUNT']}.", "",
          f"Duplicate review: {vc['FULL_WINDOWS_IN_DUPLICATE_REVIEW']} van de {vc['FULL_VISIBLE_WINDOWS']} FULL ramen zitten in twee mogelijke dubbele paren "
          "(002/003 en 004/005). Ze zijn niet samengevoegd. Tellen elk paar als een kozijn, dan zijn er "
          f"{vc['FULL_WINDOWS_IF_DUPLICATE_GROUPS_COUNT_ONCE']} FULL ramen in plaats van {vc['FULL_VISIBLE_WINDOWS']}.", "",
          "Dit zijn zichtbare kandidaten op een foto, geen gebouwtotaal: het gebouw heeft meer ramen dan op de straatzijde van foto 2 zichtbaar zijn.", "",
          "## 4. Repeat module candidates (REPEAT_CANDIDATE, non-active, geen multiplier)", "",
          "| Module | Ramen gevel | Deuren | Onbekende openingen | Dakramen | Dakkapelramen |", "|---|---|---|---|---|---|"]
    for r in doc["repeat_modules"]["comparison"]:
        L.append(f"| {r['module_id']} | {r['facade_windows']} | {r['exterior_doors']} | {r['unknown_openings']} | {r['roof_windows']} | {r['dormer_windows']} |")
    L += ["", doc["repeat_modules"]["conclusion"], "",
          "Mogelijk hetzelfde: lager dakschild met dakraam (017 en 018), terugliggend kozijn op de eerste verdieping (007 en 008), bakstenen entreemuur met "
          "huisnummer (290 en 288). Verschillen: de dakkapel staat alleen in module A; de bovenste gevelrij en de zichtbare begane grond verschillen, deels door "
          "begroeiing. Nog geen USER_CONFIRMED_REPEAT.", "",
          "## 5. Overlay", "", "`reports/frames/photo_review_v1/maldenhof_2_frame_overlay.png`; review sheet: `reports/frames/photo_review_v1/maldenhof_2_review_sheet.md`.", "",
          "## 6. Coverage gaps (begroeiing, tegenlicht, bereik)", ""] + [f"- {g}" for g in doc["coverage_gaps"]]
    L += ["", "## 7. Wat nu wel en niet", "",
          "Wel betrouwbaar: de kandidaten bestaan als zichtbare aanduidingen op foto 2 met een beeldlocatie, bouwlaag en zichtbaarheid; de FULL-kandidaten buiten "
          "de duplicate-paren zijn het sterkst. Nog geen gebouwtotaal, geen maten of oppervlakken, geen painting area en geen quantity-resolutie; alle zeven "
          "quantity-concepten blijven UNKNOWN. 756,80 blijft NOT_COMPARABLE (historische context). CPD-00001 en CPD-00002 zijn ongewijzigd.", "",
          "## 8. Volgende stap", "", "Menselijke review van de kandidaten (sheet), daarna pas frame instances/groups. Niets is vandaag aangemaakt.", ""]
    return "\n".join(L)


def dumps(o):
    return json.dumps(o, indent=2, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    old = json.loads(REVIEW_STORE.read_text(encoding="utf-8")) if REVIEW_STORE.exists() else new_store()
    store = apply_decisions(json.loads(json.dumps(old)))
    assert not append_only_errors(old, store)
    doc = build_annotation()
    validate_annotation(doc)
    if a.check:
        assert REVIEW_STORE.read_text(encoding="utf-8") == dumps(store), "review store verouderd"
        assert ANNOTATION.read_text(encoding="utf-8") == dumps(doc), "annotatie verouderd"
        assert SHEET.read_text(encoding="utf-8") == render_sheet(doc) and REPORT.read_text(encoding="utf-8") == render_report(doc, store, evidence)
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_STORE.write_text(dumps(store), encoding="utf-8")
    ANNOTATION.write_text(dumps(doc), encoding="utf-8")
    SHEET.write_text(render_sheet(doc), encoding="utf-8")
    REPORT.write_text(render_report(doc, store, evidence), encoding="utf-8")
    render_overlay(doc)


if __name__ == "__main__":
    main()
