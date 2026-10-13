"""Onafhankelijke bewijscontrole voor OIC-VR-027 met de 36 originele Maldenhof-foto's.

Handmatig uitvoeren (heeft de originele zip nodig, die niet in de repository staat):
    python3 scripts/object_identity_evidence_verification.py [pad/naar/zip]
Schrijft het bewijsrecord (JSON), het vergelijkingsbeeld en het rapport. De tests gebruiken alleen de vastgelegde
JSON; het rapport wordt uit die JSON gerenderd. Er worden geen nieuwe observaties, besluiten, instances of
koppelingen aangemaakt; het OIC-verband zelf blijft ongewijzigd.
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

OUT_DIR = ROOT / "reports/frames/physical_object_identity_evidence_v1"
OUT_JSON = OUT_DIR / "physical_object_identity_evidence_verification_v1.json"
OUT_MD = ROOT / "reports/frames/physical_object_identity_evidence_verification_v1.md"
FIGURE = OUT_DIR / "EV-window_comparison.jpg"
DEFAULT_ZIP = "/mnt/project-files/Maldenhof_kozijnfoto_selectie (4) 2.zip"
MODEL_VERSION = "physical_object_identity_evidence_verification_v1"

# Uitsneden in originele pixels: (photo_id, label, [x0, y0, x1, y1], rol)
CROPS = [
    ("MAP-003", "OBS-MAP003-011 (+ smal raam rechts)", [1150, 470, 1420, 590], "SOURCE_OBSERVATION"),
    ("MAP-004", "OBS-MAP004-006 (+ smal raam rechts)", [520, 465, 790, 585], "SOURCE_OBSERVATION"),
    ("MAP-009", "zelfde positie, schuin van links, andere camera", [300, 300, 1050, 800], "ADDITIONAL_VIEW"),
    ("MAP-007", "zelfde raamtype boven een kap met twee dakramen (ander huis)", [650, 980, 1300, 1320], "COUNTER_EXAMPLE_OTHER_HOUSE"),
    ("MAP-003", "linkerbuur-raam", [300, 440, 600, 580], "NEIGHBOUR"),
    ("MAP-003", "rechterbuur-raam", [1580, 470, 1850, 590], "NEIGHBOUR"),
    ("MAP-004", "buur-raam", [980, 455, 1280, 590], "NEIGHBOUR"),
]

# Handmatige visuele beoordeling per foto (MANUAL_VISUAL_READING). level: DETAIL = op volle resolutie bekeken, SHEET = contactblad.
PHOTO_ASSESSMENT = {
    "MAP-003": ("DETAIL", "BRONFOTO", "Bronfoto van OBS-MAP003-011."),
    "MAP-004": ("DETAIL", "BRONFOTO", "Bronfoto van OBS-MAP004-006; zelfde camera/sessie als MAP-003 (niet onderling onafhankelijk)."),
    "MAP-009": ("DETAIL", "EXTRA_MATCH", "Schuin van links met plaat 280; ander toestel (P1000236) en andere hoek. Het raam links boven de kap toont dezelfde combinatie: witte merktekens in het linkervak, gordijn met witte voorwerpen op de vensterbank in het middenvak, smal raam rechts met doorschijnende folie en verticale plakstrook."),
    "MAP-007": ("DETAIL", "TEGENVOORBEELD", "Zelfde raamtype (tweedelig + smal raam) boven een kap met twee dakramen; rolgordijnen, geen gordijn, geen folie: ander huis. Laat zien dat het type herhaald wordt."),
    "MAP-010": ("DETAIL", "HERHALINGSCONTEXT", "Schuin langs de rij vanaf plaat 288; dezelfde raamtypen herhalen zich op elk huis, te klein voor identificatie."),
    "MAP-006": ("DETAIL", "HERHALINGSCONTEXT", "Breed beeld van andere huizen (platen 260-246) met exact hetzelfde tweedelige raam met smal raam rechts op elke woning."),
    "MAP-027": ("DETAIL", "MOGELIJK_NIET_BRUIKBAAR", "Bovenste raamrij van onderen met tegenlicht; locatie niet vast te stellen, geen herkenbare kenmerken (geen folie/gordijn herkenbaar)."),
    "MAP-001": ("SHEET", "NIET_BRUIKBAAR", "Schuin van de kopgevel, rij te verkort."),
    "MAP-002": ("SHEET", "TOONT_SECTIE_NIET", "Frontaal, andere sectie (platen 290/288)."),
    "MAP-005": ("SHEET", "HERHALINGSCONTEXT", "Frontaal, andere sectie (262-258); zelfde raamtypen."),
    "MAP-008": ("SHEET", "TOONT_SECTIE_NIET", "Schuin bij 266/268."),
    "MAP-011": ("SHEET", "NIET_BRUIKBAAR", "Straat met schutting en boom, rij ver weg."),
    "MAP-012": ("SHEET", "NIET_BRUIKBAAR", "Straatperspectief, rij verborgen achter beplanting."),
    "MAP-013": ("SHEET", "TOONT_SECTIE_NIET", "Schuin bij 288/286; rij te ver weg voor het raam."),
    "MAP-014": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde."),
    "MAP-015": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde."),
    "MAP-016": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde."),
    "MAP-017": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde."),
    "MAP-018": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde."),
    "MAP-019": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde/dakvlak."),
    "MAP-020": ("SHEET", "TOONT_SECTIE_NIET", "Achterzijde/dakvlak."),
    "MAP-021": ("SHEET", "TOONT_SECTIE_NIET", "Tuinzijde."),
    "MAP-022": ("SHEET", "TOONT_SECTIE_NIET", "Detail, zijde onbekend."),
    "MAP-023": ("SHEET", "MOGELIJK_NIET_BRUIKBAAR", "Detail tweede verdieping met open vleugel en lamellen; locatie onbekend, geen herkenbare folie/gordijn-combinatie."),
    "MAP-024": ("SHEET", "MOGELIJK_NIET_BRUIKBAAR", "Detail van onderen; zelfde onzekerheid."),
    "MAP-025": ("SHEET", "MOGELIJK_NIET_BRUIKBAAR", "Detail tussen kappen; locatie niet vast te stellen."),
    "MAP-026": ("SHEET", "MOGELIJK_NIET_BRUIKBAAR", "Detail; locatie niet vast te stellen."),
    "MAP-028": ("SHEET", "MOGELIJK_NIET_BRUIKBAAR", "Detail met open vleugels; geen herkenbare kenmerken van het kandidaatraam."),
    "MAP-029": ("SHEET", "TOONT_SECTIE_NIET", "Entreemuur plaat 248."),
    "MAP-030": ("SHEET", "TOONT_SECTIE_NIET", "Entree plaat 244."),
    "MAP-031": ("SHEET", "TOONT_SECTIE_NIET", "Plaat 250."),
    "MAP-032": ("SHEET", "TOONT_SECTIE_NIET", "Plaat 266."),
    "MAP-033": ("SHEET", "TOONT_SECTIE_NIET", "Begane-grondraam plaat 276; geen bovenste rij."),
    "MAP-034": ("SHEET", "TOONT_SECTIE_NIET", "Plaat 258."),
    "MAP-035": ("SHEET", "TOONT_SECTIE_NIET", "Begane-grondraam plaat 270."),
    "MAP-036": ("SHEET", "TOONT_SECTIE_NIET", "Begane-grondraam plaat 268."),
}

FEATURE_TABLE = [
    ("Kozijnindeling: tweedelig raam + los smal raam rechts", False, "Komt op vrijwel elke woning in de rij voor (MAP-003/004/006/007/010)."),
    ("Rolgordijn-/lamellenkast boven de ruiten", False, "Standaard op de naastgelegen woningen."),
    ("Positie links boven de kap van de wand met plaat 280", True, "Beperkt de kandidaten tot één plek in de gevelsectie; bewijst het pand niet."),
    ("Witte merktekens (stickers) in het linkervak", True, "In MAP-003, MAP-004 en MAP-009 herkenbaar; tijdelijk van aard."),
    ("Gordijn in het middenvak met witte voorwerpen op de vensterbank", True, "In alle drie de foto's; buurramen hebben rolgordijnen of open vleugels."),
    ("Smal raam rechts met doorschijnende folie en verticale plakstrook", True, "In alle drie de foto's; bij geen enkel onderzocht buurraam gezien."),
    ("Hoge feature-matchscore", False, "Niet identificerend: verschillende ramen halen tot 54 inliers, het echte paar via MAP-009 slechts 8."),
]


def _images(zip_path):
    import cv2
    import numpy as np
    arch = {p["photo_id"]: p for p in OI._load(OI.ARCHIVE_JSON)["photos"]}
    zf = zipfile.ZipFile(zip_path)
    names = {Path(n).name: n for n in zf.namelist() if not n.endswith("/")}
    imgs, verified = {}, {}
    for pid, p in arch.items():
        data = zf.read(names[p["original_file"]])
        verified[pid] = hashlib.sha256(data).hexdigest() == p["sha256"]
        imgs[pid] = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return arch, imgs, verified


def build(zip_path):
    import cv2
    import numpy as np
    arch, imgs, verified = _images(zip_path)

    def crop(pid, box, H=360):
        x0, y0, x1, y1 = box
        c = imgs[pid][y0:y1, x0:x1]
        return cv2.resize(c, (int(c.shape[1] * H / c.shape[0]), H), interpolation=cv2.INTER_CUBIC)

    tiles = []
    for pid, label, box, role in CROPS:
        t = crop(pid, box)
        cv2.putText(t, f"{pid} {role}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(t)
    W = max(t.shape[1] for t in tiles[:3])
    row1 = np.vstack([cv2.copyMakeBorder(t, 0, 0, 0, W - t.shape[1], cv2.BORDER_CONSTANT) for t in tiles[:3]])
    W2 = max(t.shape[1] for t in tiles[3:])
    row2 = np.vstack([cv2.copyMakeBorder(t, 0, 0, 0, W2 - t.shape[1], cv2.BORDER_CONSTANT) for t in tiles[3:]])
    H = max(row1.shape[0], row2.shape[0])
    pad = lambda r: cv2.copyMakeBorder(r, 0, H - r.shape[0], 0, 0, cv2.BORDER_CONSTANT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(FIGURE), np.hstack([pad(row1), pad(row2)]), [cv2.IMWRITE_JPEG_QUALITY, 85])

    sift, bf = cv2.SIFT_create(), cv2.BFMatcher()
    names = [f"{pid}:{label}" for pid, label, _, _ in CROPS]
    kp = {n: sift.detectAndCompute(cv2.cvtColor(crop(pid, box, 400), cv2.COLOR_BGR2GRAY), None) for n, (pid, label, box, _) in zip(names, CROPS)}
    pairs = []
    for x, y in itertools.combinations(names, 2):
        (k1, d1), (k2, d2) = kp[x], kp[y]
        good = [m[0] for m in bf.knnMatch(d1, d2, k=2) if len(m) == 2 and m[0].distance < 0.75 * m[1].distance] if d1 is not None and d2 is not None else []
        inl = 0
        if len(good) >= 4:
            s = np.float32([k1[g.queryIdx].pt for g in good])
            t = np.float32([k2[g.trainIdx].pt for g in good])
            _, i = cv2.estimateAffinePartial2D(s, t, method=cv2.RANSAC, ransacReprojThreshold=6)
            inl = int(i.sum()) if i is not None else 0
        pairs.append({"a": x, "b": y, "good_matches": len(good), "inliers": inl})
    rec = record(arch, verified, pairs)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(rec), encoding="utf-8")
    return rec


def record(arch, verified, pairs):
    oic = json.loads(OI.OUT_JSON.read_text(encoding="utf-8"))["candidates"][0]
    photos = []
    for pid in sorted(arch):
        lvl, rel, note = PHOTO_ASSESSMENT[pid]
        photos.append({"photo_id": pid, "file": arch[pid]["original_file"], "sha256": arch[pid]["sha256"], "sha256_verified_against_register": bool(verified[pid]),
                       "inspection": lvl, "relevance": rel, "note": note, "method": "MANUAL_VISUAL_READING"})
    return {
        "model_version": MODEL_VERSION, "candidate_group_id": oic["candidate_group_id"], "observation_ids": oic["observation_ids"], "relation_id": "VR-027",
        "identity_status_before": oic["identity_status"], "identity_status_after": oic["identity_status"], "status_changed": False,
        "originals_in_repository": False, "source_zip": "Maldenhof_kozijnfoto_selectie (4) 2.zip (projectbestanden)",
        "photos": photos, "crops": [{"photo_id": p, "label": l, "region_px": b, "role": r} for p, l, b, r in CROPS], "figure": "physical_object_identity_evidence_v1/" + FIGURE.name,
        "features": [{"feature": f, "identifying": i, "comment": c} for f, i, c in FEATURE_TABLE],
        "feature_match_pairs": pairs,
        "feature_match_measurements": measurements(pairs),
        "feature_match_note": "SIFT/RANSAC op uitsneden; alleen ondersteunend en hier aantoonbaar niet-identificerend.",
        "additional_matches": [{"photo_id": "MAP-009", "file": "P1000236.JPG", "strength": "STERK_VISUEEL_ONAFHANKELIJK_TOESTEL_EN_HOEK",
                                "arguments": ["andere camera (P1000236, 3264x2448, datumstempel) en andere hoek dan de bronfoto's (iPhone IMG_8518/8520)",
                                              "dezelfde combinatie: merktekens links, gordijn + witte voorwerpen midden, folie met plakstrook rechts",
                                              "positie links boven de kap van de wand met plaat 280, zoals in MAP-003/004",
                                              "buurramen en MAP-007 tonen rolgordijnen of open vleugels, niet deze combinatie"],
                                "limits": ["zelfde dag (14-08-2026) en tijdelijke kenmerken: onafhankelijk in toestel/hoek, niet in tijd",
                                           "geen leesbaar huisnummer bij dit raam; plaat 280 bewijst alleen die muur, niet het pand van het kozijn",
                                           "schuin perspectief: feature-match onbruikbaar (8 inliers)"]}],
        "contradictions": [], "conclusion": "AANVULLEND_BEWIJS_GEVONDEN",
        "recommendation": "SUPPORTED_CANDIDATE behouden en voorbereiden voor een afzonderlijke menselijke instance-review; geen activatie.",
        "swap_risk": "Hoog voor alle kenmerken die op de hele rij voorkomen (indeling, kasten); gedekt door de unieke, tijdelijke combinatie die bij geen onderzocht buurraam voorkomt. Geen derde foto op dezelfde plek uit een andere sessie/dag.",
        "inputs": {"oic_json_sha256": OI.sha(OI.OUT_JSON), "archive_json_sha256": OI.sha(OI.ARCHIVE_JSON)},
        "effects": {"instances_created": 0, "bag_links_created": 0, "merges": 0, "building_totals": None, "quantities": None, "costs": None, "new_observations": 0,
                    "human_decisions_changed": 0, "oic_changed": False},
        "stop": "Stop vóór instance-activatie en vóór het mergen van PR #42.",
    }


def measurements(pairs):
    """Twee verschillende metingen voor VR-027; niet met elkaar te verwarren en geen van beide is identiteitsbewijs."""
    orig = next(r for r in OI._load(OI.EVIDENCE_JSON)["relations"] if r["relation_id"] == "VR-027")
    new = next(p for p in pairs if p["a"].startswith("MAP-003:OBS-MAP003-011") and p["b"].startswith("MAP-004:OBS-MAP004-006"))
    return [
        {"id": "FM-QUALITY-REVIEW", "source": "p1_quality_review/p1_feature_match_evidence_v1.json", "method": orig["method"],
         "crops": "exacte observatie-uitsneden (OBS-MAP003-011, OBS-MAP004-006)", "good_matches": orig["good_matches"], "inliers": orig["inliers"],
         "best_other_inliers_row": orig["best_other_inliers_row"], "best_other_inliers_col": orig["best_other_inliers_col"],
         "meaning": "oorspronkelijke meting uit de P1-kwaliteitsreview; partner is wederzijds beste, volgende 24"},
        {"id": "FM-EVIDENCE-VERIFICATION", "source": "dit rapport (physical_object_identity_evidence_verification_v1.json)", "method": "SIFT_RATIO_RANSAC_SIMILARITY",
         "crops": "ruimere uitsneden inclusief het smalle raam rechts (zie regio's)", "good_matches": new["good_matches"], "inliers": new["inliers"],
         "meaning": "nieuwe meting op andere uitsneden en schaal; geeft een andere waarde dan 39 zonder dat het bewijs verandert"},
    ]


def render_md(rec):
    ph = rec["photos"]
    cnt = lambda lvl: sum(1 for p in ph if p["inspection"] == lvl)
    L = ["# Aanvullend bewijsrapport OIC-VR-027", "",
         "Onafhankelijke controle met de 36 originele Maldenhof-foto's. Er is **niets** gewijzigd aan OIC-VR-027, de besluiten of de bronobservaties; dit is bewijs en advies. "
         "De originelen staan niet in de repository; de zip in de projectbestanden is gebruikt, alle 36 bestanden zijn tegen het SHA256-register gecontroleerd. "
         "Gegenereerd uit `physical_object_identity_evidence_verification_v1.json` (handmatige visuele beoordeling, `MANUAL_VISUAL_READING`).", "",
         "## 1. Conclusie", "",
         f"**{rec['conclusion']}** voor {rec['candidate_group_id']} ({', '.join(rec['observation_ids'])}, relatie {rec['relation_id']}). Status blijft **{rec['identity_status_after']}**; geen tegenbewijs gevonden.", "",
         f"Aanbeveling: {rec['recommendation']}", "",
         "## 2. Onderzochte foto's", "",
         f"Alle {len(ph)} originelen zijn gelezen en tegen het register geverifieerd ({sum(p['sha256_verified_against_register'] for p in ph)}/{len(ph)} kloppen). "
         f"Op volledige resolutie bekeken: {cnt('DETAIL')} foto's ({', '.join(p['photo_id'] for p in ph if p['inspection'] == 'DETAIL')}); de overige {cnt('SHEET')} via contactbladen. "
         "Een oordeel is nooit uit bestandsnamen of bestaande annotaties afgeleid.", "",
         "| Foto | Bestand | SHA ok | Bekeken | Beoordeling | Toelichting |", "|---|---|---|---|---|---|"]
    L += [f"| {p['photo_id']} | {p['file']} | {'ja' if p['sha256_verified_against_register'] else 'NEE'} | {p['inspection']} | {p['relevance']} | {p['note']} |" for p in ph]
    am = rec["additional_matches"][0]
    L += ["", "## 3. Foto's met mogelijke extra match", "",
          f"**{am['photo_id']}** (`{am['file']}`): {am['strength']}.", "", "Visuele argumenten:"] + [f"- {a}" for a in am["arguments"]] + ["", "Beperkingen:"] + [f"- {a}" for a in am["limits"]]
    L += ["", f"Vergelijkingsbeeld: `{rec['figure']}` (bronuitsneden MAP-003/004, extra beeld MAP-009, tegenvoorbeeld MAP-007 en buurramen). Uitsneden (originele pixels):", "",
          "| Foto | Rol | Regio [x0,y0,x1,y1] | Wat |", "|---|---|---|---|"]
    L += [f"| {c['photo_id']} | {c['role']} | {c['region_px']} | {c['label']} |" for c in rec["crops"]]
    L += ["", "## 4. Kenmerken: identificerend of niet", "", "| Kenmerk | Identificerend | Opmerking |", "|---|---|---|"]
    L += [f"| {f['feature']} | {'ja' if f['identifying'] else 'nee'} | {f['comment']} |" for f in rec["features"]]
    L += ["", "## 5. Feature-match (alleen ondersteunend)", "", rec["feature_match_note"], "",
          "Twee verschillende metingen voor hetzelfde paar (VR-027); ze zijn niet uitwisselbaar en geen van beide bewijst identiteit:", "",
          "| Meting | Bron | Uitsneden | Goede matches | Inliers |", "|---|---|---|---|---|"]
    L += [f"| {m['id']} | {m['source']} | {m['crops']} | {m['good_matches']} | {m['inliers']} |" for m in rec["feature_match_measurements"]]
    L += ["", "Alle paren van de nieuwe meting:", "", "| Paar | Goede matches | Inliers |", "|---|---|---|"]
    L += [f"| {p['a']} ↔ {p['b']} | {p['good_matches']} | {p['inliers']} |" for p in rec["feature_match_pairs"]]
    L += ["", "## 6. Tegenspraak, verwisselingsrisico, openstaande punten", "",
          "- Tegenspraak met bestaand bewijs: geen gevonden.", f"- Verwisselingsrisico: {rec['swap_risk']}",
          "- MAP-007 toont hetzelfde raamtype met rolgordijnen op een ander huis: het type zegt niets, de combinatie van tijdelijke kenmerken wel.",
          "- Een leesbare plaat (280) bewijst alleen de muur waarop die zit, niet het BAG-pand van het kozijn. Geen BAG-koppeling gemaakt.",
          "- Kenmerken zijn tijdelijk (gordijn, folie, merktekens) en alle foto's zijn van dezelfde dag; een foto van een andere dag zou het sterkst zijn.",
          "- De relatie met de gevelsectie wordt iets duidelijker (positie links boven de kap bij plaat 280), maar blijft een kandidaat.", "",
          "## 7. Aanbeveling", "",
          "`SUPPORTED_CANDIDATE` behouden. Voorbereiden voor een afzonderlijke menselijke instance-review met het vergelijkingsbeeld; de review beslist of het kozijn een instance wordt. "
          "Terugzetten naar UNRESOLVED is niet nodig. Geen automatische overgang.", "", rec["stop"]]
    return "\n".join(L) + "\n"


def main():
    rec = build(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ZIP)
    print("OK", rec["conclusion"], sum(p["sha256_verified_against_register"] for p in rec["photos"]), "/36")


if __name__ == "__main__":
    main()
