"""Evidence Reconciliation v1: het verschil tussen de MAP-009-beoordeling uit PR #42 en de bestaande P1-kwaliteitsreview van VR-045.

Handmatig uitvoeren (heeft de originele zip nodig, die niet in de repository staat):
    python3 scripts/physical_instance_evidence_reconciliation.py [pad/naar/zip]

Wijzigt NIETS aan VR-045, de kwaliteitsreview, het pilotregister, de OIC, de bronobservaties of de bewijsrapporten van PR #42. Het schrijft alleen
een nieuw reconciliatierecord (JSON), twee beelden en het rapport. Er is geen menselijk besluit en geen nieuwe observatie.
De beoordeling is handmatige lezing van de originele pixels (MANUAL_VISUAL_READING); feature-match is alleen ondersteunend.
"""
import hashlib
import io
import itertools
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import object_identity_pilot as OI  # noqa: E402

OUT_DIR = ROOT / "reports/frames/physical_instance_approval_v1"
OUT_JSON = OUT_DIR / "physical_instance_evidence_reconciliation_v1.json"
OUT_MD = ROOT / "reports/frames/physical_instance_evidence_reconciliation_v1.md"
FIG_SCOPE = OUT_DIR / "RC-crop_scope.jpg"
FIG_FEATURES = OUT_DIR / "RC-feature_comparison.jpg"
DEFAULT_ZIP = "/mnt/project-files/Maldenhof_kozijnfoto_selectie (4) 2.zip"
MODEL_VERSION = "physical_instance_evidence_reconciliation_v1"
OUTCOMES = ("COMPATIBLE_DIFFERENT_SCOPE", "GENUINE_EVIDENCE_CONFLICT", "INSUFFICIENT_TO_RECONCILE")
CLASSES = ("DIRECTLY_VISIBLE", "DIRECTLY_VISIBLE_LOW_RESOLUTION", "INTERPRETATION", "NOT_VERIFIABLE")

BASE = "reports/frames/photo_review_map003_map004_v1/"
SOURCES = {
    "relation_vr045": {"file": BASE + "maldenhof_visual_photo_review_map003_map004_v1.json", "path": "relations[rel_id=VR-045]"},
    "relation_vr027": {"file": BASE + "maldenhof_visual_photo_review_map003_map004_v1.json", "path": "relations[rel_id=VR-027]"},
    "reference_ref009_006": {"file": BASE + "maldenhof_visual_photo_review_map003_map004_v1.json", "path": "references[ref_id=REF-MAP009-006]"},
    "quality_review_vr045": {"file": BASE + "maldenhof_p1_visual_quality_review_v1.json", "path": "records[review_id=RV-REL-VR-045]"},
    "quality_review_vr027": {"file": BASE + "maldenhof_p1_visual_quality_review_v1.json", "path": "records[review_id=RV-REL-VR-027]"},
    "p1_review_sheet": {"file": BASE + "p1_quality_review/QREL-sheet-4.jpg", "path": "rij VR-045"},
    "p1_feature_match": {"file": BASE + "p1_quality_review/p1_feature_match_evidence_v1.json", "path": "relations[relation_id=VR-045]"},
    "pr42_verification": {"file": "reports/frames/physical_object_identity_evidence_v1/physical_object_identity_evidence_verification_v1.json", "path": "additional_matches[MAP-009]"},
}
# Uitsneden in originele pixels (photo_id, id, [x0,y0,x1,y1], wat)
CROPS = [
    ("MAP-009", "C-VR045-REF", [362, 362, 747, 682], "REF-MAP009-006: de uitsnede van de VR-045-review; alleen het tweedelige kozijn"),
    ("MAP-009", "C-PR42-WIDE", [300, 300, 1050, 800], "PR #42: ruimere uitsnede; tweedelig kozijn + smal raam rechts + omgeving"),
    ("MAP-009", "C-NARROW", [800, 500, 960, 760], "MAP-009: smal raam met folie (buiten de VR-045-uitsnede)"),
    ("MAP-009", "C-LEFTPANE", [362, 362, 520, 600], "MAP-009: linkervak met witte merktekens (binnen de VR-045-uitsnede)"),
    ("MAP-009", "C-SILL", [480, 570, 747, 682], "MAP-009: vensterbank onder het gordijn (binnen de VR-045-uitsnede)"),
    ("MAP-003", "C-M3-OBS", [1167, 481, 1316, 571], "OBS-MAP003-011 (exacte observatie-uitsnede)"),
    ("MAP-003", "C-M3-WIDE", [1150, 470, 1420, 590], "OBS-MAP003-011 plus smal raam rechts"),
    ("MAP-003", "C-M3-NARROW", [1350, 478, 1415, 580], "MAP-003: smal raam met folie"),
    ("MAP-003", "C-M3-LEFTPANE", [1170, 485, 1220, 570], "MAP-003: linkervak"),
    ("MAP-003", "C-M3-SILL", [1215, 535, 1305, 575], "MAP-003: vensterbank"),
    ("MAP-003", "C-M3-NEIGH-L", [300, 440, 600, 580], "MAP-003: linkerbuur, zelfde indeling"),
    ("MAP-004", "C-M4-OBS", [535, 477, 692, 569], "OBS-MAP004-006 (exacte observatie-uitsnede)"),
    ("MAP-004", "C-M4-WIDE", [520, 465, 790, 585], "OBS-MAP004-006 plus smal raam rechts"),
    ("MAP-004", "C-M4-NARROW", [730, 470, 790, 583], "MAP-004: smal raam met folie"),
    ("MAP-004", "C-M4-LEFTPANE", [540, 480, 590, 568], "MAP-004: linkervak"),
    ("MAP-004", "C-M4-SILL", [580, 535, 675, 575], "MAP-004: vensterbank"),
]

# Handmatige beoordeling per kenmerk. m3/m4/m9: in welke foto zichtbaar; in_vr045_crop: zichtbaar binnen REF-MAP009-006.
FEATURES = [
    {"id": "F1", "feature": "Twee witte merktekens in het linkervak (rechtsboven en rechtsonder)", "m3": True, "m4": True, "m9": True, "in_vr045_crop": True,
     "class": "DIRECTLY_VISIBLE", "comment": "Zelfde twee tekens op dezelfde plaats in alle drie de foto's, ook binnen de VR-045-uitsnede. Niet uniek op zichzelf: de linkerbuur in MAP-003 heeft één los merkteken op een andere plaats."},
    {"id": "F2", "feature": "Wit geplooid gordijn in het grote vak", "m3": True, "m4": True, "m9": True, "in_vr045_crop": True,
     "class": "DIRECTLY_VISIBLE", "comment": "Zichtbaar in alle drie, ook in de VR-045-uitsnede. Gordijnen zijn op zichzelf niet onderscheidend; de buurvensters tonen een rolgordijnkast."},
    {"id": "F3", "feature": "Vensterbankvoorwerpen: lichte doos plus klein puntig voorwerp", "m3": True, "m4": True, "m9": True, "in_vr045_crop": True,
     "class": "DIRECTLY_VISIBLE_LOW_RESOLUTION", "comment": "In MAP-009 herkenbaar als lichte doos en wit puntje, maar op lage resolutie en schuin; de kleinere voorwerpen uit MAP-003/004 zijn niet afzonderlijk te onderscheiden."},
    {"id": "F4", "feature": "Doorschijnende folie in het smalle raam rechts", "m3": True, "m4": True, "m9": True, "in_vr045_crop": False,
     "class": "DIRECTLY_VISIBLE", "comment": "Folie is in MAP-009 zichtbaar, maar het smalle raam ligt buiten REF-MAP009-006; dit is het meest onderscheidende kenmerk en ontbrak dus in de VR-045-vergelijking."},
    {"id": "F5", "feature": "Verticale plakstrook langs de folie", "m3": True, "m4": True, "m9": None, "in_vr045_crop": False,
     "class": "NOT_VERIFIABLE", "comment": "In MAP-003/004 duidelijk. In MAP-009 is aan de linkerrand van de folie een lichtere verticale baan te zien, maar dat kan ook een plooi of weerspiegeling zijn. PR #42 stelde de strook ook in MAP-009 vast; dat is hierbij teruggebracht tot niet verifieerbaar."},
    {"id": "F6", "feature": "Positie: rechts van het tweedelige kozijn, onder de goot, boven donkere houten bekleding, bij de kaphoek rechtsonder", "m3": True, "m4": True, "m9": True, "in_vr045_crop": False,
     "class": "DIRECTLY_VISIBLE", "comment": "Dezelfde ruimtelijke combinatie in alle drie; schuin perspectief maakt maten onvergelijkbaar. Plaat 280 bewijst alleen de muur, niet het pand van dit kozijn."},
    {"id": "F7", "feature": "Buurkozijnen: zelfde indeling maar rolgordijnkast en geen folie", "m3": True, "m4": True, "m9": None, "in_vr045_crop": False,
     "class": "DIRECTLY_VISIBLE", "comment": "Linkerbuur in MAP-003 heeft dezelfde indeling met rolgordijnkast op het smalle raam, zonder folie. Slechts enkele buren zijn zichtbaar in een lange rij identieke woningen."},
]

COMPARISON = [
    ("Welke relatie", "VR-045: PHYSICAL_OBJECT, sterkte LOW, groep-tegen-referentie", "VR-027: PHYSICAL_OBJECT, sterkte MEDIUM, paar OBS-MAP003-011 / OBS-MAP004-006; MAP-009 alleen aanvullend"),
    ("Eindpunten", "MAP-003:OBS-MAP003-011/012 en MAP-004:OBS-MAP004-006/007 (tweedelig kozijn plus smal raam) tegen MAP-009:REF-MAP009-006", "OBS-MAP003-011 en OBS-MAP004-006, beide met het smalle raam rechts, tegen een brede MAP-009-uitsnede"),
    ("MAP-009-uitsnede", "[362,362,747,682], 385x320 px, alleen het tweedelige kozijn", "[300,300,1050,800], 750x500 px, tweedelig kozijn plus smal raam met folie"),
    ("Zichtbaar in de MAP-009-uitsnede", "F1, F2, F3; niet F4, F5, F6", "F1, F2, F3, F4, F6; F5 niet verifieerbaar"),
    ("Vraag", "Is de referentie hetzelfde als de groep (met smal raam)? Smal raam ontbreekt in de referentie", "Geeft MAP-009 aanvullende steun voor het paar uit VR-027?"),
    ("Bewijsstandaard", "Uniek kenmerk binnen de uitsnede plus feature-match; indeling alleen telt niet", "Kenmerk-voor-kenmerk lezing van de originele pixels, positie en verwisselingscontrole"),
    ("Feature-match", "4 inliers op 7 matches; methode: CLAHE, +12% marge, max 360 px, groepsuitsnede (alleen ondersteunend)", "8 inliers op 22 matches; methode: zonder CLAHE, hoogte 400 px, ruime uitsneden (alleen ondersteunend). De getallen zijn niet vergelijkbaar"),
    ("Uitkomst", "INSUFFICIENT_EVIDENCE; Claude-voorstel UNDECIDABLE; NEEDS_BETTER_PHOTO", "STERK_VISUEEL_ONAFHANKELIJK_TOESTEL_EN_HOEK (aanvullend; mijn handmatige lezing)"),
    ("Menselijk besluit", "geen", "geen"),
]


def _zip_images(zip_path):
    import cv2
    import numpy as np
    arch = {p["photo_id"]: p for p in json.loads(OI.ARCHIVE_JSON.read_text(encoding="utf-8"))["photos"]}
    zf = zipfile.ZipFile(zip_path)
    names = {Path(n).name: n for n in zf.namelist() if not n.endswith("/")}
    imgs, ok = {}, {}
    for pid in ("MAP-003", "MAP-004", "MAP-009"):
        data = zf.read(names[arch[pid]["original_file"]])
        ok[pid] = hashlib.sha256(data).hexdigest() == arch[pid]["sha256"]
        imgs[pid] = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return arch, imgs, ok


def build(zip_path):
    import cv2
    import numpy as np
    arch, imgs, ok = _zip_images(zip_path)
    if not all(ok.values()):
        raise SystemExit("SHA256 van een originele foto klopt niet; geen reconciliatie: " + str(ok))
    by_id = {c[1]: c for c in CROPS}

    def crop(cid, H=360):
        pid, _, (x0, y0, x1, y1), _ = by_id[cid]
        c = imgs[pid][y0:y1, x0:x1]
        return cv2.resize(c, (int(c.shape[1] * H / c.shape[0]), H), interpolation=cv2.INTER_CUBIC)

    def label(t, text):
        t = t.copy()
        cv2.rectangle(t, (0, 0), (t.shape[1], 24), (20, 20, 20), -1)
        cv2.putText(t, text, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        return t

    def hrow(ts, gap=8):
        H = max(t.shape[0] for t in ts)
        out = []
        for t in ts:
            out += [cv2.copyMakeBorder(t, 0, H - t.shape[0], 0, gap, cv2.BORDER_CONSTANT, value=(30, 30, 30))]
        return np.hstack(out)

    def pad_to(r, W):
        return cv2.copyMakeBorder(r, 0, 0, 0, max(0, W - r.shape[1]), cv2.BORDER_CONSTANT, value=(30, 30, 30))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # beeld 1: wat de VR-045-uitsnede wel en niet toont
    r1 = hrow([label(crop("C-M3-WIDE"), "MAP-003 OBS-011 + smal raam"), label(crop("C-M4-WIDE"), "MAP-004 OBS-006 + smal raam")])
    r2 = hrow([label(crop("C-VR045-REF"), "MAP-009 REF-006 (VR-045): zonder smal raam"), label(crop("C-PR42-WIDE"), "MAP-009 PR42-uitsnede: mét smal raam")])
    W = max(r1.shape[1], r2.shape[1])
    cv2.imwrite(str(FIG_SCOPE), np.vstack([pad_to(r1, W), pad_to(r2, W)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    # beeld 2: de kenmerken naast elkaar (MAP-003 | MAP-004 | MAP-009)
    rows = []
    for title, ids in (("F1 merktekens", ("C-M3-LEFTPANE", "C-M4-LEFTPANE", "C-LEFTPANE")), ("F3 vensterbank", ("C-M3-SILL", "C-M4-SILL", "C-SILL")),
                       ("F4/F5 folie en strook", ("C-M3-NARROW", "C-M4-NARROW", "C-NARROW"))):
        rows.append(hrow([label(crop(i, 300), f"{title} {by_id[i][0]}") for i in ids]))
    W = max(r.shape[1] for r in rows)
    cv2.imwrite(str(FIG_FEATURES), np.vstack([pad_to(r, W) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 85])

    # ondersteunende feature-match (zelfde methode als PR #42): alleen indicatief
    sift, bf = cv2.SIFT_create(), cv2.BFMatcher()

    def match(a, b):
        k1, d1 = sift.detectAndCompute(cv2.cvtColor(crop(a, 400), cv2.COLOR_BGR2GRAY), None)
        k2, d2 = sift.detectAndCompute(cv2.cvtColor(crop(b, 400), cv2.COLOR_BGR2GRAY), None)
        good = [m[0] for m in bf.knnMatch(d1, d2, k=2) if len(m) == 2 and m[0].distance < 0.75 * m[1].distance] if d1 is not None and d2 is not None else []
        inl = 0
        if len(good) >= 4:
            s = np.float32([k1[g.queryIdx].pt for g in good])
            t = np.float32([k2[g.trainIdx].pt for g in good])
            _, i = cv2.estimateAffinePartial2D(s, t, method=cv2.RANSAC, ransacReprojThreshold=6)
            inl = int(i.sum()) if i is not None else 0
        return {"a": a, "b": b, "good_matches": len(good), "inliers": inl}
    pairs = [match(a, b) for a, b in (("C-VR045-REF", "C-M3-OBS"), ("C-VR045-REF", "C-M4-OBS"), ("C-PR42-WIDE", "C-M3-WIDE"), ("C-PR42-WIDE", "C-M4-WIDE"),
                                       ("C-NARROW", "C-M3-NARROW"), ("C-NARROW", "C-M4-NARROW"), ("C-M3-OBS", "C-M4-OBS"), ("C-M3-WIDE", "C-M4-WIDE"))]
    return record(arch, ok, pairs)


def record(arch, ok, pairs):
    quality = {r["review_id"]: r for r in json.loads((ROOT / SOURCES["quality_review_vr045"]["file"]).read_text(encoding="utf-8"))["records"]}
    decisions = {d["review_id"]: d for d in json.loads(OI.REGISTER_JSON.read_text(encoding="utf-8"))["decisions"]}
    return {
        "model_version": MODEL_VERSION,
        "outcome": "COMPATIBLE_DIFFERENT_SCOPE",
        "outcome_explanation": [
            "De twee beoordelingen gaan over verschillende MAP-009-uitsneden en verschillende bewijsclaims. REF-MAP009-006 bevat alleen het tweedelige kozijn en sluit het smalle raam met folie, het meest onderscheidende kenmerk, buiten; VR-045 vergelijkt bovendien een groep (kozijn plus smal raam) met die enkele uitsnede.",
            "De P1-review heeft daarom terecht vastgesteld dat deze uitsnede en de feature-match (4 van 7) geen identiteit bewijzen. Mijn PR #42-beoordeling steunt op een ruimere uitsnede met het smalle raam en op een kenmerk-voor-kenmerk lezing. Beide uitspraken kunnen naast elkaar bestaan.",
            "Twee kanttekeningen: (1) de P1-bevinding 'geen uniek kenmerk' en 'smal raam ontbreekt' is juist voor de uitsnede maar niet voor de foto: het smalle raam staat in MAP-009, net buiten de uitsnede, en F1-F3 waren ook binnen de uitsnede zichtbaar. (2) Mijn PR #42-tekst noemde de plakstrook ook in MAP-009; dat is niet verifieerbaar en is hierbij teruggebracht.",
        ],
        "not_a_genuine_conflict_because": "Dezelfde bewijsclaim (zelfde uitsnede, zelfde eindpunten) heeft geen tegenstrijdige beoordelingen gekregen; er is geen menselijk besluit over VR-045 dat door een AI-beoordeling zou worden vervangen.",
        "sources": SOURCES,
        "photos": [{"photo_id": pid, "file": arch[pid]["original_file"], "sha256": arch[pid]["sha256"], "width_px": arch[pid]["width_px"], "height_px": arch[pid]["height_px"],
                    "sha256_verified_against_register": bool(ok[pid]), "inspection": "ORIGINAL_PIXELS_FULL_RESOLUTION", "method": "MANUAL_VISUAL_READING"} for pid in ("MAP-003", "MAP-004", "MAP-009")],
        "crops": [{"crop_id": c, "photo_id": p, "region_px": b, "what": w} for p, c, b, w in CROPS],
        "vr045_as_reviewed": {"relation_id": "VR-045", "quality_record": {k: quality["RV-REL-VR-045"][k] for k in ("evidence_class", "evidence_basis", "feature_match", "finding", "next_step", "quality_status", "claude_proposal_now")},
                              "human_decision": decisions.get("RV-REL-VR-045", {}).get("decision"), "left_endpoints": ["OBS-MAP003-011", "OBS-MAP003-012", "OBS-MAP004-006", "OBS-MAP004-007"],
                              "right_endpoint": "REF-MAP009-006", "same_question_as_vr027": False,
                              "relation_to_vr027": "Zelfde soort vraag (PHYSICAL_OBJECT) en dezelfde twee observaties in de groep, maar een andere claim: groep tegen een enkele MAP-009-referentie. VR-027 zelf vergelijkt alleen OBS-MAP003-011 met OBS-MAP004-006."},
        "comparison_table": [{"dimension": a, "vr045_p1_review": b, "pr42_verification": c} for a, b, c in COMPARISON],
        "features": FEATURES,
        "feature_classes": list(CLASSES),
        "neighbour_and_swap_check": {"visible_neighbours": ["linkerbuur MAP-003 (zelfde indeling, rolgordijnkast, geen folie, één los merkteken elders)", "rechterbuur MAP-003 (andere indeling, open vleugels)", "buur MAP-004"],
                                     "counter_example": "MAP-007: zelfde raamtype bij een ander huis, rolgordijnen",
                                     "residual_risk": "Laag-tot-matig: de combinatie F1+F2+F3+F4 komt bij geen zichtbare buur voor, maar slechts enkele buren zijn zichtbaar in een rij van identieke woningen; kenmerken zijn deels tijdelijk (zelfde dag, 14-08-2026)."},
        "feature_match_pairs": pairs,
        "feature_match_note": "SIFT/RANSAC is alleen ondersteunend. De waarde hangt sterk af van uitsnede en methode: de exacte REF-MAP009-006-uitsnede geeft hier 35 en 26 inliers tegen de observatie-uitsneden, terwijl de P1-review (CLAHE, +12% marge, 360 px, groepsuitsnede) 4 vond en de ruime uitsneden van PR #42 8 of 5. Dat deze waarden zo uiteenlopen is zelf een reden om er niets op te baseren; hogere waarden komen ook bij niet-partners voor (PR #42: tot 54).",
        "corrections_to_pr42_text": ["Plakstrook (F5) is in MAP-009 niet verifieerbaar; PR #42 noemde die als zichtbaar. De overige MAP-009-argumenten blijven staan."],
        "consequences_for_iar_oic_vr_027": {
            "oic_depends_on_map009": False, "map009_role": "ADDITIONAL_EVIDENCE_NOT_RELIED_ON", "ready_for_human_review_remains": True,
            "reasons": ["OIC-VR-027 is SUPPORTED_CANDIDATE op basis van VR-027 (MEDIUM bron, STRONG kwaliteitsreview, menselijk SAME); MAP-009 speelt daarin geen rol.",
                        "VR-045 heeft geen menselijk besluit; het blijft open en wordt in de aanvraag zo getoond.",
                        "MAP-009 is aanvullend bewijs voor hetzelfde kozijn, geen nieuwe fysieke instance en geen nieuwe observatie."]},
        "advice_for_human_review": ["Laat de reviewer VR-045 apart beoordelen met de ruimere uitsnede (smal raam erbij), niet met REF-MAP009-006 alleen.",
                                    "Leg de beperking vast dat alle bewijs visueel en deels tijdelijk is; een derde foto uit een andere sessie of dag zou de verwisselingsvraag het sterkst beslissen.",
                                    "Neem de plakstrook niet als MAP-009-bewijs mee."],
        "effects": {"vr045_modified": False, "quality_review_modified": False, "human_decisions_created": 0, "human_decisions_changed": 0, "pilot_register_changed": False,
                    "oic_changed": False, "new_observations": 0, "instances_created": 0, "bag_links_created": 0, "building_totals": None, "quantities": None, "costs": None},
        "inputs": {"archive_json_sha256": OI.sha(OI.ARCHIVE_JSON), "review_json_sha256": OI.sha(ROOT / SOURCES["relation_vr045"]["file"]),
                   "quality_json_sha256": OI.sha(ROOT / SOURCES["quality_review_vr045"]["file"]), "register_sha256": OI.sha(OI.REGISTER_JSON)},
        "figures": [FIG_SCOPE.name, FIG_FEATURES.name],
        "stop": "Stop vóór iedere menselijke goedkeuring, instance-activatie en merge.",
    }


def render_md(rec):
    L = ["# Evidence Reconciliation v1: VR-045 en MAP-009", "",
         "Onafhankelijk onderzoek van het verschil tussen de MAP-009-beoordeling uit PR #42 en de bestaande P1-kwaliteitsreview van VR-045. "
         "**VR-045, de kwaliteitsreview, het pilotregister en de OIC zijn niet gewijzigd; er is geen menselijk besluit aangemaakt.** "
         "De originele foto's (zip in de projectbestanden, niet in de repository) zijn tegen het SHA256-register gecontroleerd en op volledige resolutie gelezen. Dit is handmatige lezing (`MANUAL_VISUAL_READING`).", "",
         "## 1. Uitkomst", "", f"**{rec['outcome']}**", ""]
    L += [f"- {x}" for x in rec["outcome_explanation"]]
    L += ["", f"Geen genuine conflict: {rec['not_a_genuine_conflict_because']}", "", "## 2. Bronnen", "", "| Bron | Bestand | Pad |", "|---|---|---|"]
    L += [f"| {k} | `{v['file']}` | {v['path']} |" for k, v in rec["sources"].items()]
    L += ["", "| Foto | Bestand | Afmeting | SHA256 | Controle |", "|---|---|---|---|---|"]
    L += [f"| {p['photo_id']} | {p['file']} | {p['width_px']}x{p['height_px']} | `{p['sha256'][:16]}…` | {'klopt' if p['sha256_verified_against_register'] else 'KLOPT NIET'} |" for p in rec["photos"]]
    v = rec["vr045_as_reviewed"]
    L += ["", "## 3. Wat VR-045 vergelijkt", "",
          f"- Linkereindpunt (groep): {', '.join(v['left_endpoints'])}; rechtereindpunt: {v['right_endpoint']} = MAP-009 [362,362,747,682].",
          f"- Kwaliteitsrecord: {v['quality_record']['evidence_class']}, basis {', '.join(v['quality_record']['evidence_basis'])}, feature-match {v['quality_record']['feature_match']['inliers']} van {v['quality_record']['feature_match']['good_matches']}; "
          f"voorstel Claude {v['quality_record']['claude_proposal_now']}; bevinding: \"{v['quality_record']['finding']}\"",
          f"- Menselijk besluit over VR-045: **{v['human_decision']}** (geen).", f"- Dezelfde vraag als VR-027: **nee**. {v['relation_to_vr027']}", "",
          "## 4. Vergelijkingstabel", "", "| Aspect | P1-review VR-045 | PR #42-verificatie |", "|---|---|---|"]
    L += [f"| {r['dimension']} | {r['vr045_p1_review']} | {r['pr42_verification']} |" for r in rec["comparison_table"]]
    L += ["", "Beeld van het verschil in uitsnede: `physical_instance_approval_v1/RC-crop_scope.jpg` (boven MAP-003/004, onder MAP-009 met de VR-045-uitsnede links en de ruimere uitsnede rechts).", "",
          "## 5. Herbeoordeling kenmerk voor kenmerk", "",
          "Klassen: DIRECTLY_VISIBLE = rechtstreeks zichtbaar in de originele pixels; DIRECTLY_VISIBLE_LOW_RESOLUTION = zichtbaar maar klein of schuin; INTERPRETATION = mijn lezing; NOT_VERIFIABLE = niet vast te stellen.", "",
          "| Nr | Kenmerk | MAP-003 | MAP-004 | MAP-009 | In VR-045-uitsnede | Klasse | Opmerking |", "|---|---|---|---|---|---|---|---|"]
    yn = lambda x: "ja" if x is True else ("onbepaald" if x is None else "nee")   # noqa: E731
    L += [f"| {f['id']} | {f['feature']} | {yn(f['m3'])} | {yn(f['m4'])} | {yn(f['m9'])} | {yn(f['in_vr045_crop'])} | {f['class']} | {f['comment']} |" for f in rec["features"]]
    L += ["", "Beeld: `physical_instance_approval_v1/RC-feature_comparison.jpg` (per kenmerk MAP-003, MAP-004, MAP-009).", "",
          "### Uitsneden (originele pixels)", "", "| Id | Foto | Regio [x0,y0,x1,y1] | Wat |", "|---|---|---|---|"]
    L += [f"| {c['crop_id']} | {c['photo_id']} | {c['region_px']} | {c['what']} |" for c in rec["crops"]]
    n = rec["neighbour_and_swap_check"]
    L += ["", "### Verwisseling met buurkozijnen", "", f"- Zichtbare buren: {'; '.join(n['visible_neighbours'])}.", f"- Tegenvoorbeeld: {n['counter_example']}.", f"- Restrisico: {n['residual_risk']}", "",
          "### Feature-match (alleen ondersteunend)", "", rec["feature_match_note"], "", "| Paar | Goede matches | Inliers |", "|---|---|---|"]
    L += [f"| {p['a']} vs {p['b']} | {p['good_matches']} | {p['inliers']} |" for p in rec["feature_match_pairs"]]
    c = rec["consequences_for_iar_oic_vr_027"]
    L += ["", "## 6. Correctie op PR #42", ""] + [f"- {x}" for x in rec["corrections_to_pr42_text"]]
    L += ["", "## 7. Gevolgen voor IAR-OIC-VR-027", "", f"- READY_FOR_HUMAN_REVIEW kan blijven: **{'ja' if c['ready_for_human_review_remains'] else 'nee'}**; MAP-009-rol: `{c['map009_role']}`; OIC hangt af van MAP-009: **{'ja' if c['oic_depends_on_map009'] else 'nee'}**."]
    L += [f"- {x}" for x in c["reasons"]]
    L += ["", "## 8. Advies voor de menselijke beoordeling", ""] + [f"{i}. {x}" for i, x in enumerate(rec["advice_for_human_review"], 1)]
    L += ["", "## 9. Effecten", "", "```json", json.dumps(rec["effects"], indent=2, ensure_ascii=False), "```", "", f"**STOP.** {rec['stop']}", ""]
    return "\n".join(L)


def main():
    rec = build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ZIP)
    OUT_JSON.write_text(json.dumps(rec, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(json.loads(OUT_JSON.read_text(encoding="utf-8"))), encoding="utf-8")      # rapport komt uit het opgeslagen record
    print(rec["outcome"], [(p["a"], p["b"], p["inliers"]) for p in rec["feature_match_pairs"]])


if __name__ == "__main__":
    main()
