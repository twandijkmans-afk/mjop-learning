"""Photo Evidence PoC v1 (Maldenhof): manifest + visuele observaties als REVIEW_REQUIRED kandidaten.

Output: data/photo_evidence/maldenhof_photo_evidence_v1.json en reports/photos/maldenhof_photo_evidence_v1.md.
Deterministisch, geen netwerk, geen AI-aanroep: de observaties hieronder zijn een handmatige visuele eerste lezing
(AI_VISUAL_FIRST_PASS) van de drie foto's en dus nooit bevestigd. Geen aantallen, maten of oppervlakken; herhalende elementen
zijn hooguit REPEAT_CANDIDATE. Foto's zijn geen tekening: ze vervangen CPD-besluiten of quantity-concepten niet.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTO_DIR = ROOT / "data" / "photos" / "incoming" / "maldenhof"
OUT_JSON = ROOT / "data" / "photo_evidence" / "maldenhof_photo_evidence_v1.json"
OUT_MD = ROOT / "reports" / "photos" / "maldenhof_photo_evidence_v1.md"
VERSION = "photo_evidence_poc_v1.0.0"
QUANTITY_CONCEPTS = ["FRAME_COUNT", "WINDOW_COUNT", "EXTERIOR_DOOR_COUNT", "WINDOW_OPENING_AREA",
                     "FRAME_OUTER_AREA", "FRAME_PAINTING_AREA", "GLASS_AREA"]
STATUSES = {"REVIEW_REQUIRED", "REPEAT_CANDIDATE"}
FORBIDDEN_KEYS = {"count", "quantity", "area", "width", "height", "value", "instances"}

PHOTOS = {
    "maldenhof_1.jpg": {"view": "STREET_SIDE_OBLIQUE", "usability": "CONTEXT_ONLY",
                        "notes": "Brede schuine straatzijde; veel begroeiing voor de onderbouw, aangrenzende blokken rechts maken de gebouwgrens onduidelijk. Zonnig, geen huisnummers leesbaar."},
    "maldenhof_2.jpg": {"view": "STREET_SIDE_FRONTAL", "usability": "BEST_FOR_STREET_FACADE",
                        "notes": "Bijna frontale straatzijde met huisnummers 290 en 288 leesbaar; tegenlicht rechtsboven, lantaarnpaal en begroeiing verbergen delen van de begane grond."},
    "maldenhof_3.jpg": {"view": "REAR_SIDE_OBLIQUE_FROM_BELOW", "usability": "ROOF_AND_REAR_DETAIL",
                        "notes": "Achterzijde, opname van onderen met datumstempel 14.AUG.2026 in beeld; dakvlak domineert, begane grond deels door overkapping en schutting verborgen. Was byte-identiek aan het inmiddels verwijderde data/download.jpg."},
}

def _obs(oid, photo, element, desc, status, regions="", limits=""):
    return {"observation_id": oid, "photo": photo, "element_type_candidate": element, "description": desc,
            "status": status, "location_hint": regions, "limitations": limits,
            "method": "AI_VISUAL_FIRST_PASS", "requires_human_review": True, "confirmed": False}

OBSERVATIONS = [
    _obs("PHO-M-001", "maldenhof_2.jpg", "HOUSE_NUMBER_PLATE", "Huisnummers 290 en 288 leesbaar op gemetselde borstweringen bij de entrees.", "REVIEW_REQUIRED", "benedenste helft, midden en rechts", "Alleen twee nummers zichtbaar; koppeling aan DOC-005 (Maldenhof 240-296) is een hint, geen bevestiging."),
    _obs("PHO-M-002", "maldenhof_2.jpg", "WINDOW_FRAME", "Lichte (wit ogende) kozijnen met draai/kiep-delen op de eerste verdieping en bij entrees; materiaal niet vast te stellen.", "REPEAT_CANDIDATE", "tweede bouwlaag over de volle breedte", "Materiaal, afmeting en aantal onbekend; deels geopend of door bomen verborgen."),
    _obs("PHO-M-003", "maldenhof_2.jpg", "ROOF_DORMER", "Dakkapel met drie-delig kozijn in het bovendakvlak.", "REVIEW_REQUIRED", "bovenaan midden", "Dakkapel hoort mogelijk bij ander onderhoudselement dan EXTERIOR_FRAME."),
    _obs("PHO-M-004", "maldenhof_2.jpg", "ROOF_WINDOW", "Meerdere dakramen (Velux-achtig) in het dakvlak en op de lagere dakschilden.", "REPEAT_CANDIDATE", "dakvlak links, midden en rechts", "Zichtbare dakramen zijn niet hetzelfde als het totaal; achterzijde niet meegeteld."),
    _obs("PHO-M-005", "maldenhof_2.jpg", "CHIMNEY_OR_VENT_STACK", "Paren schoorsteen-/ventilatiekoppen op de nok.", "REPEAT_CANDIDATE", "nok, twee groepen", ""),
    _obs("PHO-M-006", "maldenhof_2.jpg", "ENTRANCE_PORTICO", "Entreeportiek onder het lagere dakschild met trap en voordeur in schaduw.", "REVIEW_REQUIRED", "linksonder", "Deur zelf niet te beoordelen (donker)."),
    _obs("PHO-M-007", "maldenhof_2.jpg", "BRICKWORK_PARAPET", "Metselwerk borstweringen/erfafscheidingen met houten beplating en bergkasten ervoor.", "REVIEW_REQUIRED", "onderste helft", "Gevelmetselwerk en bergkasten zijn geen onderdeel van het kozijnenonderzoek."),
    _obs("PHO-M-008", "maldenhof_1.jpg", "WINDOW_FRAME", "Kozijnen op de tweede bouwlaag en bij de terugliggende gevelvlakken; herhaald patroon langs de straat.", "REPEAT_CANDIDATE", "midden tot rechts", "Perspectief en begroeiing maken individuele kozijnen niet betrouwbaar te onderscheiden."),
    _obs("PHO-M-009", "maldenhof_1.jpg", "ROOF_DORMER", "Dakkapel linksboven met wit kozijn.", "REVIEW_REQUIRED", "linksboven", ""),
    _obs("PHO-M-010", "maldenhof_1.jpg", "ROOF_WINDOW", "Verspreide dakramen in het dakvlak en op lage dakschilden.", "REPEAT_CANDIDATE", "dakvlak", ""),
    _obs("PHO-M-011", "maldenhof_1.jpg", "CHIMNEY_OR_VENT_STACK", "Meerdere schoorsteen-/ventilatiekoppen op de nok.", "REPEAT_CANDIDATE", "nok", ""),
    _obs("PHO-M-012", "maldenhof_1.jpg", "ADJACENT_BUILDING_BLOCK", "Aangrenzend bouwblok rechts met vergelijkbare opbouw.", "REVIEW_REQUIRED", "rechts achter", "Buiten scope tot gebouwgrens is vastgesteld; niet meetellen."),
    _obs("PHO-M-013", "maldenhof_3.jpg", "ROOF_DORMER", "Dakkapel met groene dakrand en wit vierdelig kozijn; houten/lichte wangen.", "REVIEW_REQUIRED", "midden", "Kleur/materiaal wangen en kozijn niet te bevestigen."),
    _obs("PHO-M-014", "maldenhof_3.jpg", "ROOF_WINDOW", "Dakramen in het achterdakvlak, een daarvan geopend.", "REPEAT_CANDIDATE", "dakvlak rechts en links", ""),
    _obs("PHO-M-015", "maldenhof_3.jpg", "EXTERIOR_DOOR", "Rode deur naast kozijn op balkon-/terrasniveau.", "REVIEW_REQUIRED", "rechtsonder midden", "Deurtype en -materiaal niet te beoordelen."),
    _obs("PHO-M-016", "maldenhof_3.jpg", "WINDOW_FRAME", "Wit kozijn met roedeverdeling naast balkondeur; kozijn onder dakoverstek links.", "REPEAT_CANDIDATE", "rechtsonder en linksonder", "Gedeeltelijk verborgen door overkapping en planten."),
    _obs("PHO-M-017", "maldenhof_3.jpg", "BALCONY_RAILING", "Wit balkonhekwerk met glasvulling.", "REVIEW_REQUIRED", "rechtsonder", ""),
    _obs("PHO-M-018", "maldenhof_3.jpg", "CHIMNEY_OR_VENT_STACK", "Schoorsteenkoppen en ventilatie-/afvoerpijpen op de nok en het dakvlak.", "REPEAT_CANDIDATE", "nok", ""),
    _obs("PHO-M-019", "maldenhof_3.jpg", "RAINWATER_GUTTER", "Dakgoten en hemelwaterafvoer langs het dakschild.", "REVIEW_REQUIRED", "onderrand dakvlak", ""),
    _obs("PHO-M-020", "maldenhof_3.jpg", "GARDEN_CANOPY", "Doorzichtige/lichte golfplaten overkapping op de begane grond.", "REVIEW_REQUIRED", "onderin", "Waarschijnlijk niet-VvE; eigendom onbekend."),
]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    from PIL import Image
    files = sorted(PHOTO_DIR.glob("*.jpg"))
    photos = []
    for f in files:
        im = Image.open(f)
        meta = PHOTOS.get(f.name, {"view": "UNKNOWN", "usability": "UNASSESSED", "notes": ""})
        photos.append({"photo_id": f.stem, "path": f"data/photos/incoming/maldenhof/{f.name}", "sha256": sha256(f),
                       "width_px": im.size[0], "height_px": im.size[1], "view": meta["view"],
                       "usability_as_evidence": meta["usability"], "notes": meta["notes"],
                       "exif_present": bool(im.getexif())})
    return {
        "builder_version": VERSION, "building_label": "Maldenhof 240-296 (DOC-005 + DOC-006)", "building_link_status": "REVIEW_REQUIRED",
        "scope": "Foto-evidence; geen tekening. EXTERIOR_FRAME=PRESENT blijft CPD-00001; alle quantity-concepten blijven UNKNOWN.",
        "quantity_concepts_status": {k: "UNKNOWN" for k in QUANTITY_CONCEPTS},
        "photos": photos, "observations": OBSERVATIONS,
        "removed_duplicates": [{"path": "data/download.jpg", "sha256": "52866e56eda4887fd1c14d0b1b42d69639582d4fb03dabecccf8afd248572a71", "byte_identical_to": "maldenhof_3", "status": "REMOVED_CANONICAL_IS_PHOTO_INPUT"}],
        "open_questions": ["Welke gevel(s) en bouwlagen horen bij DOC-005/006 en vallen binnen de VvE-scope?",
                           "Is een vector-gevelaanzicht beschikbaar om kozijnen te kunnen tellen en meten?",
                           "Bevestigt een reviewer de huisnummers 288/290 als onderdeel van DOC-005 (Maldenhof 240-296)?"],
    }


def validate(doc):
    ids = {p["photo_id"] for p in doc["photos"]}
    seen = set()
    for o in doc["observations"]:
        assert o["observation_id"] not in seen, o["observation_id"]
        seen.add(o["observation_id"])
        assert o["photo"].rsplit(".", 1)[0] in ids, o
        assert o["status"] in STATUSES and o["requires_human_review"] is True and o["confirmed"] is False
        assert not (FORBIDDEN_KEYS & set(o)), o
    assert all(v == "UNKNOWN" for v in doc["quantity_concepts_status"].values())


def render_md(doc):
    L = ["# Maldenhof foto-evidence PoC v1", "", f"Gebouw: {doc['building_label']} (koppeling: {doc['building_link_status']})", "",
         "Alle observaties zijn een AI-eerste lezing: REVIEW_REQUIRED of REPEAT_CANDIDATE, nooit bevestigd. Geen aantallen, maten of oppervlakken; alle zeven quantity-concepten blijven UNKNOWN.", "", "## Foto's", ""]
    for p in doc["photos"]:
        L += [f"- **{p['photo_id']}** ({p['width_px']}x{p['height_px']}, {p['view']}, {p['usability_as_evidence']}): {p['notes']}"]
    L += ["", "## Observaties", "", "| ID | Foto | Element | Status | Beperking |", "|---|---|---|---|---|"]
    for o in doc["observations"]:
        L.append(f"| {o['observation_id']} | {o['photo']} | {o['element_type_candidate']} | {o['status']} | {o['limitations'] or '-'} |")
    L += ["", "## Open vragen", ""] + [f"- {q}" for q in doc["open_questions"]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    doc = build()
    validate(doc)
    js = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if a.check:
        assert OUT_JSON.read_text(encoding="utf-8") == js, "foto-evidence is verouderd"
        return
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(render_md(doc), encoding="utf-8")


if __name__ == "__main__":
    main()
