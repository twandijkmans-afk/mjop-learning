"""Maldenhof Rear Facade Annotation + Coverage Plan v1.

1. Address -> BAG pand evidence (alleen bestaande BAG-snapshots en bevestigde building links; geen netwerk):
   data/photo_evidence/maldenhof_address_pand_evidence_v1.json. Foto-2 instances krijgen GEEN pand/adres-scope tenzij de koppeling bewezen is.
2. Handmatige annotatie van maldenhof_3.jpg (REAR_DETAIL): data/photo_evidence/maldenhof_3_frame_annotation_v1.json, alle kandidaten
   REVIEW_REQUIRED, geen instances, geen maten. De bboxes en het captureplan zijn een handmatige lezing door Claude (MANUAL_VISUAL_READING).
3. Overlay en review sheet onder reports/frames/photo_review_rear_v1/.
4. Coverage matrix (zichtbaarheid, geen compleetheid) en MISSING_PHOTOS_NEEDED: reports/frames/maldenhof_frame_coverage_v1.json/.md.

Foto 2 is bevroren (PR #35); foto 1 blijft CONTEXT_ONLY. Geen building total, geen repeat-activatie, geen maten, geen painting area,
geen quantity-resolutie, geen cross-photo deduplicatie voor/achter. Deterministisch.
"""
import argparse
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
SNAP_FILES = {"DOC-005": D / "bag_snapshots" / "BAGSNAP-431559474da45dcf.json", "DOC-006": D / "bag_snapshots" / "BAGSNAP-e23aa139a8589881.json"}
LINKS = D / "building_links" / "building_link_records.json"
INVENTORY = D / "frame_inventory" / "frame_inventory_v1.json"
INSTANCES = D / "frame_inventory" / "maldenhof_photo_frame_instances_v1.json"
EVIDENCE = D / "photo_evidence" / "maldenhof_photo_evidence_v1.json"
ANN2 = D / "photo_evidence" / "maldenhof_2_frame_annotation_v1.json"
PHOTO_3 = D / "photos" / "incoming" / "maldenhof" / "maldenhof_3.jpg"
OUT_ADDR = D / "photo_evidence" / "maldenhof_address_pand_evidence_v1.json"
OUT_ANN3 = D / "photo_evidence" / "maldenhof_3_frame_annotation_v1.json"
REAR_DIR = ROOT / "reports" / "frames" / "photo_review_rear_v1"
OVERLAY = REAR_DIR / "maldenhof_3_frame_overlay.png"
SHEET = REAR_DIR / "maldenhof_3_review_sheet.md"
REPORT = REAR_DIR / "maldenhof_rear_annotation_v1.md"
COV_JSON = ROOT / "reports" / "frames" / "maldenhof_frame_coverage_v1.json"
COV_MD = ROOT / "reports" / "frames" / "maldenhof_frame_coverage_v1.md"
VERSION = "rear_annotation_coverage_v1.0.0"
BASE_W, BASE_H = 2000.0, 1500.0
REQUESTED = (288, 290)

COUNTING_UNIT = ("Een frame instance/candidate is een fysieke kozijn-/gevelopening tussen bouwkundige scheidingen. Meerdere glasvlakken of vleugels "
                 "binnen een onafgebroken kozijn zijn een opening; een kozijnstijl (mullion) is geen nieuwe opening; metselwerk/bouwkundige scheiding is wel een aparte opening.")

# --- foto 3: handmatige annotatie (bbox in 2000x1500-pixels) -------------------------------------------------------------------
# (nr, type, bbox, storey, visibility, occlusion, parent, note, relation_group)
RAW3 = [
    (1, "UNKNOWN_OPENING", (300, 1005, 490, 1065), "UNKNOWN", "HEAVILY_OCCLUDED", "Houten scherm, bloembakken en palmblad verbergen een lichte strook onder de dakgoot links",
     None, "Mogelijk een raam achter het scherm; type niet te bepalen", None),
    (2, "UNKNOWN_OPENING", (300, 1100, 395, 1160), "UNKNOWN", "HEAVILY_OCCLUDED", "Palmbladeren en bloembakkenmuur verbergen een kozijn met witte onderdorpel",
     None, "Kozijnrand en dorpel zichtbaar, de opening zelf niet", None),
    (3, "WINDOW", (546, 1010, 665, 1119), "UNKNOWN", "PARTIAL", "Dakschild snijdt de rechterzijde af; balkonhekwerk en bloemen voor de onderrand",
     None, "Kozijn met lamellen/jaloezie onder een uitgeklapte zonwering (PHO-M-016)", None),
    (4, "EXTERIOR_DOOR", (1232, 945, 1343, 1050), "UNKNOWN", "PARTIAL", "Balkonhekwerk en glasvulling verbergen de onderzijde",
     None, "Rode balkondeur (PHO-M-015); het rode paneel links ervan hoort bij dezelfde rode kozijnopbouw en is niet apart geannoteerd; deurtype en materiaal niet te beoordelen", "REL-M3-001"),
    (5, "WINDOW", (1346, 922, 1589, 1050), "UNKNOWN", "FULL", None,
     None, "Wit kozijn met roedeverdeling en gordijnen naast de balkondeur; rechts begrensd door het metselwerk van de kopgevel (PHO-M-016)", "REL-M3-001"),
    (6, "ROOF_WINDOW", (0, 895, 87, 950), "ROOF", "PARTIAL", "Beeldrand snijdt het dakraam af; palmblad voor de onderrand", None, "Dakraam linksonder in het dakvlak", None),
    (7, "ROOF_WINDOW", (66, 873, 174, 940), "ROOF", "FULL", None, None, "Geopend dakraam links (PHO-M-014)", None),
    (8, "ROOF_WINDOW", (470, 786, 620, 890), "ROOF", "FULL", None, None, "Dakraam links van de dakkapel", None),
    (9, "ROOF_WINDOW", (1528, 576, 1668, 700), "ROOF", "FULL", None, None, "Geopend dakraam rechts (PHO-M-014)", None),
    (10, "DORMER_WINDOW", (639, 662, 987, 853), "ROOF", "FULL", None, "DORMER-M3-001",
     "Vijfdelig wit kozijn in een onafgebroken kozijnopening onder de groene dakrand (PHO-M-013); posten zijn kozijnstijlen, geen metselwerk, dus een opening", None),
]
DORMER3 = {"object_id": "DORMER-M3-001", "object_type": "ROOF_DORMER", "bbox_norm": [round(635 / BASE_W, 4), round(619 / BASE_H, 4), round(1087 / BASE_W, 4), round(865 / BASE_H, 4)],
           "related_observation": "PHO-M-013", "counts_as_window_candidate": False, "note": "Dakkapel zelf; geen EXTERIOR_FRAME quantity-koppeling."}
RELATION_GROUPS = [
    {"group_id": "REL-M3-001", "candidate_ids": ["FC-M3-004", "FC-M3-005"], "status": "SAME_FRAME_OPENING_REVIEW_REQUIRED",
     "question": ("Vormen de rode balkondeur (004) en het witte raam (005) een onafgebroken raam-deurcombinatie (een opening) of twee openingen? "
                  "Op de foto loopt een doorlopende witte kozijnbovenregel over beide en ligt er geen metselwerk tussen; de kozijnstijl alleen is geen scheiding. "
                  "Niet samengevoegd; de mens beslist.")},
]
COVERAGE_GAPS_3 = [
    "Begane grond: golfplaten overkapping en houten schutting verbergen de volledige begane grond; geen enkele opening op de begane grond is beoordeelbaar.",
    "Linkerhelft: palmbladeren, bloembakken en een houten scherm verbergen de openingen in de linker woning (candidates 001 en 002 zijn heavily occluded).",
    "Rechterrand: de kopgevel (zijgevel) is slechts als bakstenen wand zichtbaar, zonder zichtbare openingen; zijgevel niet gedekt.",
    "Opname van onderen met dakvlak dominant: de bovenste gevelrij onder de dakgoot is smal en schuin in beeld (bouwlagen niet vast te stellen).",
    "Foto 3 toont een deel van de achterzijde: de woningen links en rechts van de zichtbare delen zijn niet in beeld.",
    "Het exacte adres/pand van foto 3 is niet bewezen (geen huisnummers in beeld); bag_pand_id blijft null.",
]
REPEAT_CANDIDATES_3 = {
    "status": "REPEAT_CANDIDATE", "active": False, "multiplier": None, "user_confirmed_repeat": False,
    "candidates": [
        {"repeat_candidate_id": "RC-M3-001", "kind": "SAME_REAR_ASSEMBLY_OR_MIRRORED",
         "members": ["linker woning: kozijn onder zonwering met bloembakkenbalkon (FC-M3-003)", "rechter woning: balkon met rode deur en raam (FC-M3-004/005)"],
         "note": "Beide woningen tonen een terugliggende bouwlaag met balkon onder een lager dakschild; mogelijk een gespiegeld/gelijk achtergeveltype. Zichtbare inhoud verschilt (kozijnindeling) en de linker woning is grotendeels afgedekt."},
        {"repeat_candidate_id": "RC-M3-002", "kind": "SAME_REAR_ROOF_WINDOW_PATTERN",
         "members": ["FC-M3-006", "FC-M3-007", "FC-M3-008", "FC-M3-009"], "note": "Verspreide dakramen in het achterdakvlak; patroon niet regelmatig genoeg voor een module."},
    ],
    "conclusion": "Alleen kandidaten; multiplier = null, active = false. Geen extrapolatie en geen koppeling aan de voorgevelmodules MOD-M2-A/B.",
}


def norm(b):
    return [round(b[0] / BASE_W, 4), round(b[1] / BASE_H, 4), round(b[2] / BASE_W, 4), round(b[3] / BASE_H, 4)]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dumps(o):
    return json.dumps(o, indent=2, ensure_ascii=False) + "\n"


# --- 1. address -> pand evidence -------------------------------------------------------------------------------------------------
def address_pand_evidence():
    inv = load(INVENTORY)
    building = next(b for b in inv["buildings"] if b["label"].startswith("Maldenhof"))
    scope = list(building["bag_pand_ids"])
    links = load(LINKS)["records"]
    active_links = {(r["document_id"], r["bag_pand_id"]): r for r in links if r["link_status"] == "CONFIRMED" and r["status"] == "ACTIVE"}
    snaps = {doc: load(f) for doc, f in SNAP_FILES.items()}
    per_doc = {}
    for doc, s in snaps.items():
        am = {a["pdok_id"]: a for a in s["address_matches"]}
        rows = {}
        for p in s["panden"]:
            if p["bag_pand_id"] not in scope:
                continue
            for pid in p["contains_address_point_of"]:
                a = am[pid]
                rows[a["huisnummer"]] = {"huisnummer": a["huisnummer"], "weergavenaam": a["weergavenaam"], "adresseerbaarobject_id": a["adresseerbaarobject_id"],
                                         "pdok_id": pid, "bag_pand_id": p["bag_pand_id"], "centroide_ll": a["centroide_ll"]}
        per_doc[doc] = rows
    assert per_doc["DOC-005"] == per_doc["DOC-006"], "snapshots wijken af"
    rows = per_doc["DOC-005"]
    addresses = []
    for n in sorted(rows):
        r = dict(rows[n])
        r["snapshot_ids"] = [snaps["DOC-005"]["snapshot_id"], snaps["DOC-006"]["snapshot_id"]]
        r["building_link_ids"] = [active_links[(doc, r["bag_pand_id"])]["link_id"] for doc in ("DOC-005", "DOC-006")]
        r["pand_in_confirmed_scope"] = r["bag_pand_id"] in scope
        r["requested"] = n in REQUESTED
        addresses.append(r)
    by_pand = {}
    for r in addresses:
        by_pand.setdefault(r["bag_pand_id"], []).append(r["huisnummer"])
    order = sorted(by_pand, key=lambda p: min(by_pand[p]))
    res = {}
    for n in REQUESTED:
        r = rows[n]
        res[f"Maldenhof {n}"] = {"huisnummer": n, "adresseerbaarobject_id": r["adresseerbaarobject_id"], "pdok_id": r["pdok_id"], "bag_pand_id": r["bag_pand_id"],
                                 "pand_addresses": by_pand[r["bag_pand_id"]], "building_link_ids": next(a for a in addresses if a["huisnummer"] == n)["building_link_ids"],
                                 "status": "PROVEN_BY_BAG_SNAPSHOT_AND_CONFIRMED_BUILDING_LINK"}
    ins = load(INSTANCES)
    ann2 = {i: a for i, a in ins["instance_annotations"].items()}
    assign = []
    for i in ins["instances"]:
        a = ann2[i["frame_instance_id"]]
        hint = a["address_hint"]
        rec = {"frame_instance_id": i["frame_instance_id"], "candidate_id": a["candidate_id"], "address_hint": hint,
               "bag_pand_id_in_instance_store": i["bag_pand_id"], "assignment": "NOT_ASSIGNED"}
        if hint:
            rec["hint_basis"] = "ADJACENT_TO_HOUSE_NUMBER_PLATE"
            rec["reason"] = ("Het huisnummer is alleen als hint uit de ligging naast de huisnummerplaat afgeleid. Het adres->pand verband is bewezen, maar dat de opening bij dat adres "
                             "(en dit pand) hoort niet: de pandgrens tussen de aangrenzende panden is niet in het evidence en de plaat bepaalt de eigenaar van de opening niet. Geen positional guessing.")
            rec["candidate_pand_for_human_confirmation"] = rows[int(re.search(r"\d+", hint)[0])]["bag_pand_id"]
        else:
            rec["hint_basis"] = None
            rec["reason"] = "Geen aantoonbaar adres bij deze opening; positie in het beeld is geen bewijs voor een adres of pand."
        assign.append(rec)
    return {
        "evidence_version": "maldenhof_address_pand_evidence_v1", "builder_version": VERSION, "network_calls": False,
        "method": "BAG-snapshots (contains_address_point_of) van DOC-005 en DOC-006 plus mens-bevestigde building links (BLINK-records); geen nieuwe BAG/PDOK-aanroep.",
        "building_id": building["building_id"], "confirmed_pand_count": len(scope), "address_count": len(addresses),
        "resolution": res, "same_pand": res["Maldenhof 288"]["bag_pand_id"] == res["Maldenhof 290"]["bag_pand_id"],
        "street_order_note": ("De volgorde van de panden volgt de laagste even huisnummers (afgeleid van de BAG-adrespunten). Het is een volgorde langs de straat, geen bewijs "
                              "over bouwblokgrenzen, kopgevels of gevelposities."),
        "pand_order": [{"order": k + 1, "bag_pand_id": p, "addresses": by_pand[p]} for k, p in enumerate(order)],
        "addresses": addresses,
        "photo2_instance_assignment_policy": ("Alleen toewijzen als de bbox aantoonbaar bij een adres hoort. Foto-2 instances blijven bevroren (PR #35); de instance-store is niet gewijzigd. "
                                              "Onderstaande records leggen vast waarom niets is toegewezen."),
        "photo2_instance_assignment": assign,
        "photo3_scope": {"building_scope": "Maldenhof", "bag_pand_id": None, "address_scope": "NOT_PROVEN",
                         "reason": "Geen huisnummers in beeld; geen bestaand evidence dat foto 3 aan een adres of pand koppelt."},
        "hypothesis_not_evidence": [
            "De huisnummers nemen op foto 2 naar rechts af (290 links, 288 rechts); de linker rand van foto 2 ligt dus aan de kant van de hogere nummers. Dit is een leesrichting, geen bewijs voor kopgevelposities."],
    }


# --- 2. foto-3 annotatie -----------------------------------------------------------------------------------------------------------
def category3(c):
    return {"WINDOW": "WINDOW_" + ("FULL" if c["visibility"] == "FULL" else "PARTIAL"), "EXTERIOR_DOOR": "EXTERIOR_DOOR", "ROOF_WINDOW": "ROOF_WINDOW",
            "DORMER_WINDOW": "DORMER_WINDOW", "UNKNOWN_OPENING": "UNKNOWN_OPENING"}[c["candidate_type"]]


def summarize3(cands):
    cats = {}
    for c in cands:
        cats.setdefault(category3(c), []).append(c["candidate_id"])
    rel = {i for g in RELATION_GROUPS for i in g["candidate_ids"]}
    rw = [c for c in cands if c["candidate_type"] == "ROOF_WINDOW"]
    return {"count_basis": "VISIBLE_COUNT_ON_PHOTO_3", "photo": "maldenhof_3.jpg", "is_building_total": False, "confirmed_instances": 0,
            "FULL_WINDOWS": len(cats.get("WINDOW_FULL", [])), "PARTIAL_WINDOWS": len(cats.get("WINDOW_PARTIAL", [])),
            "EXTERIOR_DOORS": len(cats.get("EXTERIOR_DOOR", [])), "ROOF_WINDOWS": len(rw),
            "ROOF_WINDOWS_FULL": len([c for c in rw if c["visibility"] == "FULL"]), "ROOF_WINDOWS_PARTIAL": len([c for c in rw if c["visibility"] == "PARTIAL"]),
            "DORMER_WINDOWS": len(cats.get("DORMER_WINDOW", [])), "UNKNOWN_OPENINGS": len(cats.get("UNKNOWN_OPENING", [])),
            "TOTAL_ANNOTATION_CANDIDATES": len(cands), "candidates_in_open_relation_review": sorted(rel),
            "OPENINGS_IF_RELATION_GROUPS_COUNT_ONCE": len([c for c in cands if c["candidate_type"] in {"WINDOW", "EXTERIOR_DOOR"}]) - len(RELATION_GROUPS),
            "candidate_ids_by_category": cats}


def build_ann3():
    ev = load(EVIDENCE)
    p3 = next(p for p in ev["photos"] if p["photo_id"] == "maldenhof_3")
    rel = {i: g["group_id"] for g in RELATION_GROUPS for i in g["candidate_ids"]}
    cands = []
    for n, ctype, bbox, storey, vis, occ, parent, note, grp in RAW3:
        cid = f"FC-M3-{n:03d}"
        cands.append({"candidate_id": cid, "photo": "maldenhof_3.jpg", "facade_side": "REAR", "candidate_type": ctype, "bbox_norm": norm(bbox),
                      "bag_address_scope_hint": None, "bag_pand_id": None, "storey": storey, "visibility": vis, "occlusion_reason": occ,
                      "parent": ({"type": "ROOF_DORMER", "ref": parent} if parent else None), "relation_review": rel.get(cid), "note": note,
                      "annotation_method": "MANUAL_VISUAL_READING", "review_status": "REVIEW_REQUIRED", "human_decision": "PENDING"})
    return {
        "builder_version": VERSION, "photo": {"photo_id": "maldenhof_3", "path": p3["path"], "sha256": p3["sha256"], "role": "REAR_DETAIL"},
        "building_scope": "Maldenhof", "bag_pand_id": None, "address_scope": "NOT_PROVEN", "facade_side": "REAR",
        "annotation_method": "MANUAL_VISUAL_READING",
        "annotation_note": "Handmatige visuele lezing van de foto door Claude; geen automatische detectie en geen foto-AI-model. Alle kandidaten wachten op menselijke review; er zijn geen instances.",
        "counting_unit": COUNTING_UNIT, "coordinate_system": "bbox_norm = [x1, y1, x2, y2] genormaliseerd 0..1 over de beeldbreedte/-hoogte, oorsprong linksboven. Alleen beeldcoordinaten.",
        "metric_scale": "NONE_PROVEN", "no_scale_note": "Geen schaalbewijs; geen afmetingen, oppervlakken, painting area of glasoppervlak.",
        "candidates": cands, "context_objects": [DORMER3], "relation_reviews": RELATION_GROUPS,
        "cross_photo_deduplication": {"status": "NONE", "rule": "Foto 2 (voorzijde) en foto 3 (achterzijde) tonen verschillende gevelzijden; kandidaten worden nooit tussen voor- en achterzijde als duplicate samengevoegd."},
        "visible_counts": summarize3(cands), "repeat_candidates": REPEAT_CANDIDATES_3, "coverage_gaps": COVERAGE_GAPS_3,
        "frame_inventory_effect": "NONE: geen frame instances/groups aangemaakt; kandidaten blijven REVIEW_REQUIRED.",
    }


def validate_ann3(doc):
    ids = [c["candidate_id"] for c in doc["candidates"]]
    assert len(ids) == len(set(ids)) and all(i.startswith("FC-M3-") for i in ids)
    for c in doc["candidates"]:
        x1, y1, x2, y2 = c["bbox_norm"]
        assert 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1, c["candidate_id"]
        assert c["candidate_type"] in {"WINDOW", "EXTERIOR_DOOR", "ROOF_WINDOW", "DORMER_WINDOW", "UNKNOWN_OPENING"}
        assert c["storey"] in {"GROUND", "FIRST", "ROOF", "UNKNOWN"} and c["visibility"] in {"FULL", "PARTIAL", "HEAVILY_OCCLUDED"}
        assert c["review_status"] == "REVIEW_REQUIRED" and c["human_decision"] == "PENDING" and c["bag_pand_id"] is None and c["facade_side"] == "REAR"
        assert not ({"width_m", "height_m", "area_m2"} & set(c))
        assert (c["visibility"] == "FULL") or c["occlusion_reason"], c["candidate_id"]
        assert (c["candidate_type"] == "DORMER_WINDOW") == bool(c["parent"])


# --- 3. coverage matrix + capture plan -----------------------------------------------------------------------------------------------
FACE_STATES = ("FULL_COVERAGE", "PARTIAL_COVERAGE", "NO_COVERAGE", "UNKNOWN")
PANDEN_PER_PHOTO = 3  # planningsaanname, zie capture_plan_basis


def build_coverage(addr, ann2, ann3, inst):
    order = addr["pand_order"]
    pand_of = {r["huisnummer"]: r["bag_pand_id"] for r in addr["addresses"]}
    p288, p290 = pand_of[288], pand_of[290]
    obscured2 = ann2["coverage_gaps"]
    rows = []
    for o in order:
        pid = o["bag_pand_id"]
        links = sorted({lid for r in addr["addresses"] if r["bag_pand_id"] == pid for lid in r["building_link_ids"]})
        photo2 = pid in (p288, p290)
        plate = [n for n in o["addresses"] if n in REQUESTED]
        front = {"coverage": "PARTIAL_COVERAGE" if photo2 else "UNKNOWN",
                 "source_photo_ids": ["maldenhof_2"] if photo2 else [],
                 "context_only_photo_ids": ["maldenhof_1"],
                 "evidence_refs": ([f"maldenhof_2: huisnummerplaat {plate[0]} leesbaar (PHO-M-001)", "PHR-00001"] if photo2 else []),
                 "obscured_areas": (obscured2 if photo2 else []),
                 "note": ("Zichtbaar op foto 2 (huisnummerplaat leesbaar), maar de naastliggende woning(en) en de begane grond zijn deels niet in beeld of afgedekt; alleen zichtbaarheid, geen compleet aantal." if photo2
                          else "Geen bevestigde foto; foto 1 is CONTEXT_ONLY en kan niet aan dit pand worden gekoppeld.")}
        rows.append({"order": o["order"], "bag_pand_id": pid, "addresses": o["addresses"], "building_link_ids": links,
                     "faces": {"FRONT": front,
                               "REAR": {"coverage": "UNKNOWN", "source_photo_ids": [], "evidence_refs": [], "obscured_areas": [],
                                        "note": "Foto 3 (REAR_DETAIL) is niet aan dit pand te koppelen; zie unassigned_photo_coverage."},
                               "LEFT_SIDE": {"coverage": "UNKNOWN", "source_photo_ids": [], "evidence_refs": [], "obscured_areas": [], "note": "Niet bekend of dit pand een kopgevel heeft."},
                               "RIGHT_SIDE": {"coverage": "UNKNOWN", "source_photo_ids": [], "evidence_refs": [], "obscured_areas": [], "note": "Niet bekend of dit pand een kopgevel heeft."}},
                     "confirmed_frame_instances_assigned": 0, "pending_candidates_assigned": 0})
    s3 = ann3["visible_counts"]
    pc = inst["photo_visible_counts"]
    unassigned = [
        {"photo_id": "maldenhof_2", "side": "FRONT", "role": "BEST_FOR_STREET_FACADE", "pand_assignment": "PROVEN_FOR_HOUSE_NUMBERS_ONLY",
         "confirmed_frame_instances": len(inst["instances"]), "pending_candidates": 0,
         "note": "De 12 gewone kozijnen en 1 deur zijn bevestigd, maar niet aan een pand toegewezen (zie photo2_instance_assignment)."},
        {"photo_id": "maldenhof_3", "side": "REAR", "role": "REAR_DETAIL", "pand_assignment": "NOT_PROVEN", "confirmed_frame_instances": 0,
         "pending_candidates": s3["TOTAL_ANNOTATION_CANDIDATES"], "note": "Achterzijde van een onbekend pand binnen Maldenhof; een kopgevel is aan de rechterrand zichtbaar."},
        {"photo_id": "maldenhof_1", "side": "FRONT_OBLIQUE", "role": "CONTEXT_ONLY", "pand_assignment": "NOT_USED", "confirmed_frame_instances": 0, "pending_candidates": 0,
         "note": "Context: zie photo1_context. Niet voor frame instances."},
    ]
    counts = {"front_photo2": {"count_basis": pc["count_basis"], "PHOTO_VISIBLE_FRAME_COUNT": pc["PHOTO_VISIBLE_FRAME_COUNT"], "PHOTO_VISIBLE_WINDOW_COUNT": pc["PHOTO_VISIBLE_WINDOW_COUNT"],
                            "PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT": pc["PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT"], "FULL": pc["ordinary_frames_FULL"], "PARTIAL": pc["ordinary_frames_PARTIAL"]},
              "rear_photo3": {k: s3[k] for k in ("count_basis", "FULL_WINDOWS", "PARTIAL_WINDOWS", "EXTERIOR_DOORS", "ROOF_WINDOWS", "DORMER_WINDOWS", "UNKNOWN_OPENINGS", "confirmed_instances")},
              "combined_building_total": "NOT_COMPUTED"}
    context = {"photo_id": "maldenhof_1", "role": "CONTEXT_ONLY", "status": "VISUAL_CONTEXT_READING_NOT_EVIDENCE", "not_used_for": "frame instances, counts, adres- of pandkoppeling",
               "readings": [
                   "Op foto 1 staan dezelfde lantaarnpaal, struik en fiets als op foto 2; foto 2 is dus een frontaal detail uit het middendeel van deze straatzijde.",
                   "Links van de lantaarnpaal loopt de straatzijde nog door tot een kopgevel achter een grote boom: dat deel valt buiten foto 2 (linkerrand) en is niet gedekt.",
                   "Rechts van de lantaarnpaal loopt de gevel door tot een terugspringend deel; daarachter begint een tweede, aangrenzend bouwblok (PHO-M-012, buiten scope tot de gebouwgrens is vastgesteld).",
                   "Begroeiing (boom, struiken, haag) verbergt vooral de begane grond links en in het midden; huisnummers zijn niet leesbaar, dus de positie ten opzichte van de adressen is niet te bewijzen."]}
    return {"coverage_version": "maldenhof_frame_coverage_v1", "builder_version": VERSION,
            "definition": "Coverage betekent alleen zichtbaarheid van de gevel op een bevestigde foto, NIET dat het aantal kozijnen compleet is vastgesteld.",
            "states": list(FACE_STATES), "building_id": addr["building_id"], "pand_count": len(rows), "panden": rows,
            "unassigned_photo_coverage": unassigned, "photo1_context": context, "counts": counts, "summary": coverage_summary(rows),
            "repeat_candidates": {"status": "REPEAT_CANDIDATE", "active": False, "multiplier": None, "user_confirmed_repeat": False,
                                  "front": "MOD-M2-A en MOD-M2-B blijven REPEAT_CANDIDATE (DO_NOT_ACTIVATE_REPEAT_YET).", "rear": ann3["repeat_candidates"]["candidates"]},
            "missing_photos_needed": capture_plan(rows), "historical_context": {"756.80_m2": "NOT_COMPARABLE", "ratio_or_m2_per_frame": "NOT_COMPUTED"}}


def coverage_summary(rows):
    s = {}
    for face in ("FRONT", "REAR", "LEFT_SIDE", "RIGHT_SIDE"):
        s[face] = {st: len([r for r in rows if r["faces"][face]["coverage"] == st]) for st in FACE_STATES}
    return s


def fmt_addr(r):
    n = r["addresses"]
    return str(n[0]) if len(n) == 1 else f"{n[0]}-{n[-1]}"


def capture_plan(rows):
    by_order = {r["order"]: r for r in rows}
    n = len(rows)
    groups = []  # van het oostelijke (hoogste nummer) naar het westelijke uiteinde
    k = n
    while k >= 1:
        groups.append([by_order[i] for i in range(k, max(k - PANDEN_PER_PHOTO, 0), -1)])
        k -= PANDEN_PER_PHOTO
    photos = []
    for gi, g in enumerate(groups, 1):
        addrs = ", ".join(fmt_addr(r) for r in g)
        pids = [r["bag_pand_id"] for r in g]
        has_p2 = any(r["faces"]["FRONT"]["coverage"] == "PARTIAL_COVERAGE" for r in g)
        photos.append({
            "photo_id": f"PHOTO-F{gi}", "facade": "FRONT", "addresses": addrs, "bag_pand_ids": pids, "orientation": "LANDSCAPE", "framing": "HELE_GEVEL",
            "stand": ("Op het voetpad voor de lage haag, recht tegenover het midden van deze groep (zelfde type standpunt als foto 2), gevel loodrecht in beeld, camera horizontaal."
                      + (" Kies een standpunt zonder lantaarnpaal, boom of fiets voor de entrees (verschuif zijwaarts) zodat de begane grond van 290 en 288 vrij komt." if has_p2 else "")),
            "must_show": "Van dakgoot tot maaiveld, linker en rechter buurwoning half in beeld voor overlap, en minstens twee leesbare huisnummerplaten (zo is de adres->pand koppeling bewijsbaar).",
            "why_needed": ("Foto 2 dekt dit deel maar met afgedekte begane grond; nodig om entrees en begane-grondkozijnen te kunnen beoordelen." if has_p2
                           else "Geen bevestigde voorgevelfoto voor deze panden."),
            "closes_gap": "FRONT UNKNOWN/PARTIAL -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden"})
    base = len(photos)
    for gi, g in enumerate(groups, 1):
        photos.append({
            "photo_id": f"PHOTO-R{gi}", "facade": "REAR", "addresses": ", ".join(fmt_addr(r) for r in g), "bag_pand_ids": [r["bag_pand_id"] for r in g], "orientation": "LANDSCAPE",
            "framing": "HELE_GEVEL",
            "stand": "Aan de achterzijde (achterpad of openbare ruimte achter de tuinen), recht tegenover het midden van deze groep; camera horizontaal op ooghoogte, niet van onderen zoals foto 3.",
            "must_show": "Van dakgoot tot en met de begane grond (zo mogelijk over de overkapping/schutting heen), buurwoningen half in beeld, en bij elke foto een herkenningspunt (achterpad-ingang of huisnummer achter) of noteer de wandelvolgorde.",
            "why_needed": "Er is geen achtergevelfoto die aan een pand is gekoppeld; foto 3 toont de achterzijde van een onbekend pand met afgedekte begane grond.",
            "closes_gap": "REAR UNKNOWN -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden"})
    ends = [("PHOTO-G1", "hoogste-nummerzijde (nabij 296)", rows[-1]), ("PHOTO-G2", "laagste-nummerzijde (nabij 240)", rows[0])]
    for pid, side, r in ends:
        photos.append({
            "photo_id": pid, "facade": "SIDE_GABLE", "addresses": fmt_addr(r), "bag_pand_ids": [r["bag_pand_id"]], "orientation": "PORTRAIT",
            "framing": "HELE_GEVEL",
            "stand": f"Loodrecht voor de kopgevel aan de {side} van de reeks, vanaf het zijpad of de aangrenzende straat; camera horizontaal.",
            "must_show": "De volledige zijgevel van maaiveld tot nok.",
            "why_needed": "Foto 3 laat zien dat er minstens een kopgevel bestaat; of de uiteinden van de reeks 240-296 bouwblokeinden zijn is niet bewezen. Ter plaatse controleren; geen foto nodig als het uiteinde tegen een volgend blok aansluit.",
            "closes_gap": "LEFT_SIDE/RIGHT_SIDE UNKNOWN -> bekend"})
    return {"label": "MISSING_PHOTOS_NEEDED", "minimum_extra_photos": len(photos), "front_photos": len(groups), "rear_photos": len(groups), "gable_photos": len(ends),
            "capture_plan_basis": (f"Planningsaanname: {PANDEN_PER_PHOTO} aaneengesloten panden per frontale foto. Op foto 2 liggen de huisnummerplaten van twee naast elkaar gelegen panden (290 en 288) "
                                   "ca. 27% van de beeldbreedte uit elkaar; er passen dus ca. 3,7 pandbreedtes in beeld; met een pand overlap blijven 3 panden per foto over. "
                                   "Dit is een planning (handmatige lezing), geen meting."),
            "assumptions": ["Alle panden en beide zijden worden direct gefotografeerd; er is geen repeat-extrapolatie toegepast.", "Het aantal kopgevelfoto's is een maximum: ter plaatse bepalen of de uiteinden echt kopgevels zijn."],
            "alternative_if_repeat_confirmed_later": ("Alleen na een latere menselijke repeat-bevestiging zou een kleinere representatieve set kunnen volstaan (bijv. PHOTO-F1, PHOTO-F5, PHOTO-R1, PHOTO-R5, een kopgevel). "
                                                       "Dat is nu NIET geactiveerd en leidt niet tot telling."),
            "photos": photos}


# --- rendering ---------------------------------------------------------------------------------------------------------------------
def render_overlay(doc):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(PHOTO_3).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im, "RGBA")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 19)
    COL = {"WINDOW": (46, 204, 113), "EXTERIOR_DOOR": (255, 0, 200), "ROOF_WINDOW": (0, 200, 255), "DORMER_WINDOW": (255, 140, 0), "UNKNOWN_OPENING": (255, 255, 255)}
    TP = {"WINDOW": "W", "EXTERIOR_DOOR": "DOOR", "ROOF_WINDOW": "RW", "DORMER_WINDOW": "DORMER-W", "UNKNOWN_OPENING": "UNK"}
    VIS = {"FULL": "FULL", "PARTIAL": "PARTIAL", "HEAVILY_OCCLUDED": "OCCL"}
    place = {1: "a1", 2: "b", 3: "b", 4: "b", 5: "a1", 6: "b", 7: "a1", 8: "b", 9: "b", 10: "a1"}

    def box(b, col, dashed, w=4):
        x1, y1, x2, y2 = b[0] * W, b[1] * H, b[2] * W, b[3] * H
        if not dashed:
            d.rectangle([x1, y1, x2, y2], outline=col, width=w)
            return
        step = 14
        for x in range(int(x1), int(x2), step * 2):
            d.line([x, y1, min(x + step, x2), y1], fill=col, width=w)
            d.line([x, y2, min(x + step, x2), y2], fill=col, width=w)
        for y in range(int(y1), int(y2), step * 2):
            d.line([x1, y, x1, min(y + step, y2)], fill=col, width=w)
            d.line([x2, y, x2, min(y + step, y2)], fill=col, width=w)

    box(DORMER3["bbox_norm"], COL["DORMER_WINDOW"], True, 3)
    for c in doc["candidates"]:
        col = COL[c["candidate_type"]]
        box(c["bbox_norm"], col, c["visibility"] != "FULL")
        n = int(c["candidate_id"][-3:])
        label = f"{c['candidate_id'][-3:]} {TP[c['candidate_type']]} {VIS[c['visibility']]}" + (" *" if c["relation_review"] else "")
        tw = d.textlength(label, font=font)
        x = max(2, min(c["bbox_norm"][0] * W, W - tw - 12))
        y = {"a1": c["bbox_norm"][1] * H - 28, "a2": c["bbox_norm"][1] * H - 56, "b": c["bbox_norm"][3] * H + 4}[place[n]]
        d.rectangle([x, y, x + tw + 8, y + 26], fill=(0, 0, 0, 200))
        d.text((x + 4, y + 1), label, fill=col, font=font)
    leg = ["Foto 3 (achterzijde, REAR_DETAIL): handmatige annotatie, alle kandidaten REVIEW_REQUIRED / human decision PENDING, geen instances; beeldcoordinaten, geen maten.",
           "* = relation review (004/005). Doorgetrokken = FULL, gestippeld = PARTIAL/OCCL; groen=raam, magenta=deur, cyaan=dakraam, oranje=dakkapel(raam), wit=onbekend"]
    d.rectangle([0, H - 64, W, H], fill=(0, 0, 0, 215))
    for k, t in enumerate(leg):
        d.text((10, H - 60 + k * 28), t, fill=(255, 255, 255), font=small)
    im = im.resize((1600, 1200), Image.LANCZOS)
    OVERLAY.parent.mkdir(parents=True, exist_ok=True)
    im.save(OVERLAY, optimize=True)


def render_sheet(doc):
    L = ["# Review sheet maldenhof_3.jpg (rear annotation v1)", "",
         "Handmatige visuele lezing door Claude; alle kandidaten REVIEW_REQUIRED, human decision PENDING. bbox = genormaliseerde beeldcoordinaten, geen maten. "
         "Dit is GEEN gebouwtotaal en er zijn geen frame instances. Foto 3 is de achterzijde; bag_pand_id = null (adres/pand niet bewezen).", "",
         "| Candidate ID | Type | Storey | Visibility | bbox_norm | Parent | Relation review | Human decision |", "|---|---|---|---|---|---|---|---|"]
    for c in doc["candidates"]:
        L.append(f"| {c['candidate_id']} | {c['candidate_type']} | {c['storey']} | {c['visibility']} | {c['bbox_norm']} | {c['parent']['ref'] if c['parent'] else '-'} | {c['relation_review'] or '-'} | PENDING |")
    L += ["", "Relation review: " + " ".join(f"{g['group_id']} ({', '.join(g['candidate_ids'])}): {g['question']}" for g in doc["relation_reviews"]), "",
          "Overlay: `reports/frames/photo_review_rear_v1/maldenhof_3_frame_overlay.png`", ""]
    return "\n".join(L)


def render_report(addr, doc):
    vc = doc["visible_counts"]
    L = ["# Maldenhof Rear Frame Annotation + Coverage Plan v1", "",
         "Scope: adres->pand evidence voor Maldenhof 288/290, handmatige annotatie van de achterzijdefoto (foto 3), coverage matrix en captureplan. Foto 2 is bevroren (11 gewone kozijnen, "
         "9 FULL / 2 PARTIAL, 1 deur PARTIAL). Geen building total, geen repeat-activatie, geen maten, geen painting area, geen quantity-resolutie, geen MJOP-App wijziging.", "",
         "## 1. Maldenhof 288 en 290 naar BAG-pand", ""]
    for k, r in addr["resolution"].items():
        L.append(f"- {k}: pand `{r['bag_pand_id']}` (adressen {', '.join(map(str, r['pand_addresses']))}); adresseerbaar object `{r['adresseerbaarobject_id']}`; building links {', '.join(r['building_link_ids'])}.")
    L += ["", f"288 en 290 liggen in verschillende panden (same_pand = {str(addr['same_pand']).lower()}); beide panden horen bij de 15 bevestigde Maldenhof-panden. "
          "Basis: de bestaande BAG-snapshots van DOC-005 en DOC-006 (identiek) en de mens-bevestigde building links; er is geen netwerkaanroep gedaan.", "",
          "### Foto-2 instances en adres-scope", "",
          "Geen van de 13 foto-2 instances is aan een pand toegewezen. Het adres->pand verband is bewezen, maar een opening aan een adres koppelen kan alleen als zij aantoonbaar bij dat adres hoort; "
          "de twee adreshints (FI-M2-012 bij 288 en de deur FI-M2-013 bij 290) volgen uit de ligging naast een huisnummerplaat en de pandgrens is niet in het evidence. "
          "Geen positional guessing. De instance-store is ongewijzigd. De mens kan beide hints later expliciet bevestigen.", "",
          "| Instance | Kandidaat | Adreshint | Toewijzing | Kandidaat-pand ter bevestiging |", "|---|---|---|---|---|"]
    for a in addr["photo2_instance_assignment"]:
        if a["address_hint"]:
            L.append(f"| {a['frame_instance_id']} | {a['candidate_id']} | {a['address_hint']} | {a['assignment']} | `{a['candidate_pand_for_human_confirmation']}` |")
    L += ["", f"Overige {len([a for a in addr['photo2_instance_assignment'] if not a['address_hint']])} instances: geen adreshint, NOT_ASSIGNED.", "",
          "## 2. Foto 3: handmatige annotatie (REAR_DETAIL)", "",
          "Building scope Maldenhof, bag_pand_id = null, adres niet bewezen. Dezelfde counting unit als PR #35 (opening tussen bouwkundige scheidingen; kozijnstijl is geen opening). "
          "De bboxes zijn een eigen handmatige lezing door Claude, geen automatische detectie. Alle kandidaten zijn REVIEW_REQUIRED; er zijn geen instances.", "",
          "### VISIBLE_COUNT_ON_PHOTO_3 (niet BUILDING_TOTAL)", "", "| Categorie | Aantal | Kandidaten |", "|---|---|---|"]
    cats = vc["candidate_ids_by_category"]
    for k, label in (("WINDOW_FULL", "FULL windows"), ("WINDOW_PARTIAL", "PARTIAL windows"), ("EXTERIOR_DOOR", "Exterior doors"), ("ROOF_WINDOW", "Roof windows"),
                     ("DORMER_WINDOW", "Dormer windows"), ("UNKNOWN_OPENING", "Unknown openings")):
        ids = cats.get(k, [])
        L.append(f"| {label} | {len(ids)} | {', '.join(i[-3:] for i in ids)} |")
    L += ["", f"Totaal {vc['TOTAL_ANNOTATION_CANDIDATES']} kandidaten, 0 confirmed instances. Roof windows: {vc['ROOF_WINDOWS_FULL']} FULL, {vc['ROOF_WINDOWS_PARTIAL']} PARTIAL.", "",
          "Relation review REL-M3-001: de rode balkondeur (004) en het witte raam (005) staan onder een doorlopende kozijnbovenregel zonder metselwerk ertussen; of dit een raam-deurcombinatie "
          f"(een opening) is, beslist de mens. Telt het als een opening, dan zijn er {vc['OPENINGS_IF_RELATION_GROUPS_COUNT_ONCE']} raam/deur-openingen in plaats van 3.", "",
          "Geen cross-photo deduplicatie: kandidaten van foto 3 (achterzijde) worden nooit met foto 2 (voorzijde) samengevoegd.", "",
          "Overlay: `reports/frames/photo_review_rear_v1/maldenhof_3_frame_overlay.png`; sheet: `maldenhof_3_review_sheet.md`.", "", "### Coverage gaps foto 3", ""]
    L += [f"- {g}" for g in doc["coverage_gaps"]]
    L += ["", "## 3. Repeat candidates (alleen kandidaten, multiplier null, active false)", ""]
    L += [f"- {c['repeat_candidate_id']} ({c['kind']}): {c['note']}" for c in doc["repeat_candidates"]["candidates"]]
    L += ["", doc["repeat_candidates"]["conclusion"], "",
          "## 4. Historische data", "", "756,80 m2 blijft NOT_COMPARABLE; geen ratio m2/ramen, geen m2 per frame.", "",
          "## 5. Volgende stap", "", "Menselijke review van de foto-3 kandidaten. Coverage matrix en captureplan: `reports/frames/maldenhof_frame_coverage_v1.md`.", ""]
    return "\n".join(L)


def render_coverage_md(cov):
    L = ["# Maldenhof frame coverage v1", "", cov["definition"], "",
         "Scope: de 15 bevestigde Maldenhof-panden (240-296). Volgorde langs de straat op laagste huisnummer; dit is geen bewijs voor bouwblokgrenzen.", "",
         "## Coverage per pand", "", "| # | Pand | Adressen | FRONT | REAR | LEFT_SIDE | RIGHT_SIDE | Foto's | Confirmed instances | Pending candidates |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in cov["panden"]:
        f = r["faces"]
        L.append(f"| {r['order']} | `{r['bag_pand_id']}` | {', '.join(map(str, r['addresses']))} | {f['FRONT']['coverage']} | {f['REAR']['coverage']} | {f['LEFT_SIDE']['coverage']} | "
                 f"{f['RIGHT_SIDE']['coverage']} | {', '.join(sorted({p for k in f.values() for p in k['source_photo_ids']})) or '-'} | {r['confirmed_frame_instances_assigned']} | {r['pending_candidates_assigned']} |")
    sm = cov["summary"]
    L += ["", "Samenvatting (aantal panden per status): " + "; ".join(f"{face}: " + ", ".join(f"{st} {n}" for st, n in v.items()) for face, v in sm.items()), "",
          "Alleen foto 2 dekt (deels) twee panden aan de voorzijde (288 en 290). Voor alle andere gevels bestaat geen aan een pand gekoppelde bevestigde foto.", "",
          "### Obscured areas, panden 288 en 290 (foto 2)", ""]
    L += [f"- {g}" for g in cov["panden"][-2]["faces"]["FRONT"]["obscured_areas"]]
    L += ["", "## Foto's zonder bewezen pand", "", "| Foto | Zijde | Rol | Pand | Confirmed instances | Pending candidates | Opmerking |", "|---|---|---|---|---|---|---|"]
    for u in cov["unassigned_photo_coverage"]:
        L.append(f"| {u['photo_id']} | {u['side']} | {u['role']} | {u['pand_assignment']} | {u['confirmed_frame_instances']} | {u['pending_candidates']} | {u['note']} |")
    c = cov["counts"]
    L += ["", "## Tellingen per foto (niet combineren)", "",
          f"- Foto 2 (voor): PHOTO_VISIBLE_FRAME_COUNT {c['front_photo2']['PHOTO_VISIBLE_FRAME_COUNT']}, WINDOW {c['front_photo2']['PHOTO_VISIBLE_WINDOW_COUNT']}, "
          f"EXTERIOR_DOOR {c['front_photo2']['PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT']} (FULL {c['front_photo2']['FULL']}, PARTIAL {c['front_photo2']['PARTIAL']}).",
          f"- Foto 3 (achter): VISIBLE_COUNT_ON_PHOTO_3: FULL windows {c['rear_photo3']['FULL_WINDOWS']}, PARTIAL {c['rear_photo3']['PARTIAL_WINDOWS']}, doors {c['rear_photo3']['EXTERIOR_DOORS']}, "
          f"roof windows {c['rear_photo3']['ROOF_WINDOWS']}, dormer {c['rear_photo3']['DORMER_WINDOWS']}, unknown {c['rear_photo3']['UNKNOWN_OPENINGS']}; 0 confirmed.",
          "- BUILDING_TOTAL: niet berekend. 756,80 m2 blijft NOT_COMPARABLE.", "", "## Repeat candidates", "", cov["repeat_candidates"]["front"], ""]
    L += [f"- {r['repeat_candidate_id']}: {r['note']}" for r in cov["repeat_candidates"]["rear"]]
    mp = cov["missing_photos_needed"]
    L += ["", "## MISSING_PHOTOS_NEEDED", "", f"**Minimum aantal extra foto's voor directe dekking (zonder repeat-extrapolatie): {mp['minimum_extra_photos']}** "
          f"({mp['front_photos']} voorzijde, {mp['rear_photos']} achterzijde, {mp['gable_photos']} kopgevel).", "", mp["capture_plan_basis"], ""]
    for a in mp["assumptions"]:
        L.append(f"- {a}")
    L += ["", mp["alternative_if_repeat_confirmed_later"], "", "| Foto | Gevel | Adressen | Formaat | Waar staan | Waarom | Sluit gap |", "|---|---|---|---|---|---|---|"]
    for p in mp["photos"]:
        L.append(f"| {p['photo_id']} | {p['facade']} | {p['addresses']} | {p['orientation']}, {p['framing']} | {p['stand']} | {p['why_needed']} | {p['closes_gap']} |")
    seen = {}
    for p in mp["photos"]:
        seen.setdefault(p["facade"], p["must_show"])
    L += ["", "### Wat moet in beeld zijn", ""] + [f"- {k}: {v}" for k, v in seen.items()]
    L += ["", "## Foto 1 (CONTEXT_ONLY): wat de foto helpt te begrijpen", ""] + [f"- {r}" for r in cov["photo1_context"]["readings"]] + [""]
    return "\n".join(L)


def build_all():
    addr = address_pand_evidence()
    ann2 = load(ANN2)
    ann3 = build_ann3()
    validate_ann3(ann3)
    inst = load(INSTANCES)
    cov = build_coverage(addr, ann2, ann3, inst)
    return addr, ann3, cov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    addr, ann3, cov = build_all()
    outs = {OUT_ADDR: dumps(addr), OUT_ANN3: dumps(ann3), SHEET: render_sheet(ann3), REPORT: render_report(addr, ann3), COV_JSON: dumps(cov), COV_MD: render_coverage_md(cov)}
    if a.check:
        for p, t in outs.items():
            assert p.read_text(encoding="utf-8") == t, f"{p.name} verouderd"
        return
    REAR_DIR.mkdir(parents=True, exist_ok=True)
    for p, t in outs.items():
        p.write_text(t, encoding="utf-8")
    render_overlay(ann3)


if __name__ == "__main__":
    main()
