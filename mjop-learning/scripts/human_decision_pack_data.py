"""Gegevens voor het Maldenhof Human Visual Decision Pack v1: reviewgroepen, prioriteiten en voorlopige (niet-bindende) voorstellen.

Hergebruikt de bestaande observaties, bboxen en 43 kandidaat-relaties uit visual_review_map003_map004_data.py ongewijzigd. Hier staat alleen
de indeling voor menselijke beoordeling. Een voorstel van Claude is nooit een menselijk besluit.
"""

# Paneel-specificatie: (bijschrift, [(foto, soort, waarde), ...])
#   soort "disp": weergave-coordinaten (2000x1500) van een 2048x1536-foto (MAP-002/003/004)
#   soort "ref":  REF-ID uit visual_review_map003_map004_data.REFS (uitsnede rond het referentiegebied)
# Groepen: (sleutel, prioriteit, titel, [relatie-ID's], [panelen], waarom, aanwijzingen, onzekerheden, APP-links, foto's)
GROUPS = [
    ("plaat288", "P1", "Begane grond: plaat 288 en het raam ernaast", ["VR-001", "VR-002", "VR-050"],
     [("Plaatmuur 288 en raam rechts van de plaat", [("MAP-002", "disp", (1690, 860, 2000, 1030)), ("MAP-003", "disp", (0, 840, 400, 1000)), ("MAP-013", "ref", "REF-MAP013-001")])],
     "In MAP-002, MAP-003 en MAP-013 staat dezelfde muur met plaat 288 met het raam direct rechts van de plaat. Overlap met de bevroren foto 2 (FC-M2-009 / FI-M2-012).",
     "Plaat 288 links van het raam; gordijn; houten rand boven het raam; steenverband; kozijnvorm met brede onderdorpel.",
     "Een plaat bewijst alleen de muur (APP-001): het raam krijgt geen pand. De pandhint van FI-M2-012 is nog niet bevestigd. MAP-013 is een schuine opname.",
     ["APP-001", "APP-011", "APP-013", "APP-031"], ["MAP-002", "MAP-003", "MAP-013"]),
    ("midrij_links", "P1", "Middelste rij links van de linker kap (MAP-002 en MAP-003)", ["VR-004", "VR-005"],
     [("FC-M2-007/008 en OBS-MAP003-015/016", [("MAP-002", "disp", (1030, 690, 1520, 860)), ("MAP-003", "disp", (0, 610, 380, 780))])],
     "De twee ramen links van de linker kap staan in beide foto's; OBS-MAP003-015 is aan de beeldrand afgesneden. Overlap met bevroren foto 2.",
     "Raam met onderpaneel direct naast de kap; in beide foto's wordt het deels door het dakschild van de kap bedekt.",
     "OBS-MAP003-015 is te klein om uniek te herkennen; de koppeling berust daar op de volgorde in de rij.",
     ["APP-011", "APP-031"], ["MAP-002", "MAP-003"]),
    ("bovenrij_007_008", "P1", "Bovenste rij: tweedelig kozijn en smal raam (007/008)", ["VR-006", "VR-007", "VR-054"],
     [("FC-M2-004/005 en OBS-MAP003-007/008", [("MAP-002", "disp", (1290, 520, 1560, 640)), ("MAP-003", "disp", (290, 430, 600, 545)), ("MAP-013", "ref", "REF-MAP013-005")])],
     "Tweedelig kozijn met een smal raam eronder rechts; in MAP-002 en MAP-003 dezelfde indeling met gemetselde penant ertussen. Overlap met bevroren foto 2.",
     "Tweedelig kozijn, smal raam met gordijn/folie rechts, penant ertussen, dezelfde regenpijp links.",
     "Beide kozijnen zijn onderling vrijwel gelijk aan buurkozijnen; herkenning berust op de relatieve positie ten opzichte van de kap en schoorstenen.",
     ["APP-011", "APP-013", "APP-031"], ["MAP-002", "MAP-003", "MAP-013"]),
    ("bovenrij_009_010", "P1", "Bovenste rij: raam met gordijn en open vleugels (009/010)", ["VR-008", "VR-009", "VR-031", "VR-053"],
     [("FC-M2-006-A/BC, OBS-MAP003-009/010 en OBS-MAP004-005", [("MAP-002", "disp", (1700, 515, 1960, 635)), ("MAP-003", "disp", (740, 430, 1060, 590)), ("MAP-004", "disp", (100, 430, 420, 590)), ("MAP-013", "ref", "REF-MAP013-004")])],
     "Hetzelfde raam met gordijn en twee open vleugels is in vier foto's te zien. In foto 2 is het smalle linker element als apart kozijn besloten (FC-M2-006-A); in MAP-003 zijn dat twee observaties, in MAP-004 een.",
     "Twee open vleugels, gordijn in het midden, donkere kozijnstijl, dakgoot erboven.",
     "Of het smalle linker element een apart kozijn of een vleugel is, is op deze foto's niet vast te stellen (HQ-VR-001). Een telverschil tussen 2 en 1 observaties is een leesverschil, geen extra raam.",
     ["APP-011", "APP-012", "APP-013", "APP-031"], ["MAP-002", "MAP-003", "MAP-004", "MAP-013"]),
    ("rand_006", "P1", "Raam aan de beeldrand links van MAP-003 (006)", ["VR-010"],
     [("FC-M2-003 en OBS-MAP003-006", [("MAP-002", "disp", (1030, 515, 1210, 625)), ("MAP-003", "disp", (0, 425, 170, 540))])],
     "MAP-003 toont slechts de rechterhelft van een raam met open vleugel aan de beeldrand; in foto 2 (FC-M2-003) staat een raam met open vleugel rechts.",
     "Open vleugel rechts; vergelijkbare hoogte in de bovenste rij.",
     "Het raam is aan de rand afgesneden; het kan een buurraam zijn. Niet te bepalen zonder bredere opname.",
     ["APP-011", "APP-031"], ["MAP-002", "MAP-003"]),
    ("bovenrij_rechts", "P1", "Bovenste rij rechts: ramen 011-014 (MAP-003) en 006-009 (MAP-004)", ["VR-027", "VR-028", "VR-029", "VR-030", "VR-045"],
     [("OBS-MAP003-011/012 en OBS-MAP004-006/007", [("MAP-003", "disp", (1110, 440, 1420, 590)), ("MAP-004", "disp", (490, 440, 800, 590)), ("MAP-009", "ref", "REF-MAP009-006")]),
      ("OBS-MAP003-013/014 en OBS-MAP004-008/009", [("MAP-003", "disp", (1530, 440, 1830, 590)), ("MAP-004", "disp", (940, 440, 1260, 590))])],
     "Dezelfde twee gevelgroepen boven de kap zijn in MAP-003 en MAP-004 zichtbaar (verschuiving per laag, parallax). Risico op dubbeltelling bij annoteren.",
     "Tweedelig kozijn + smal raam; smal raam met gordijn + kozijn met open vleugel rechts; dezelfde volgorde en afstanden.",
     "MAP-009 is sterk verkort, daar blijft alleen de indeling over. De ramen lijken sterk op elkaar; de koppeling steunt op de volgorde rond de kap.",
     ["APP-012"], ["MAP-003", "MAP-004", "MAP-009"]),
    ("midrij_kap_links", "P1", "Middelste rij links van de rechter kap (018/019)", ["VR-024", "VR-025", "VR-043"],
     [("OBS-MAP003-018/019 en OBS-MAP004-013/014", [("MAP-003", "disp", (830, 610, 1340, 800)), ("MAP-004", "disp", (110, 610, 620, 800)), ("MAP-009", "ref", "REF-MAP009-002")])],
     "Twee ramen met onderpaneel links van de rechter kap staan op MAP-003 en MAP-004; MAP-009 toont het rechter raam met flessen op de dorpel.",
     "Open vleugel rechts, wit onderpaneel, gordijn links; flessen op de dorpel (019 / 014); spiegeling van een boom.",
     "OBS-MAP004-014 wordt deels door de kap bedekt (PARTIAL).",
     ["APP-012"], ["MAP-003", "MAP-004", "MAP-009"]),
    ("midrij_kap_rechts", "P1", "Middelste rij rechts van de rechter kap (020)", ["VR-026", "VR-044"],
     [("OBS-MAP003-020 en OBS-MAP004-016", [("MAP-003", "disp", (1770, 610, 1965, 800)), ("MAP-004", "disp", (1040, 610, 1300, 800)), ("MAP-009", "ref", "REF-MAP009-005")])],
     "In MAP-003 zit een raam met open vleugel grotendeels achter de lantaarnpaal en de kap; in MAP-004 is het hele raam zichtbaar.",
     "Open vleugel en onderpaneel; positie rechts van de kap, onder de dakgoot.",
     "In MAP-003 is slechts een smalle strook zichtbaar (PARTIAL, hoge onzekerheid).",
     ["APP-012"], ["MAP-003", "MAP-004", "MAP-009"]),
    ("begane_grond_278", "P1", "Begane grond bij de platen 280, 278 en 276: raam 278 en entreenisdeur", ["VR-020", "VR-021", "VR-022", "VR-041"],
     [("Platen 280/278 en raam naast plaat 278", [("MAP-003", "disp", (1430, 840, 1850, 960)), ("MAP-004", "disp", (220, 840, 640, 960)), ("MAP-009", "ref", "REF-MAP009-003")])],
     "De platen 280, 278 (en 276) en het raam bij plaat 278 zijn op MAP-003, MAP-004 en MAP-009 te zien. De deur in de entreenis is in MAP-003 zeer donker.",
     "Plaat 278 direct rechts van het raam; plaat 280 links; raamvorm met gordijn/spiegeling; entreenis rechts van plaat 278.",
     "Een gedeelde plaat bewijst niet dat omliggende ramen of de deur hetzelfde object zijn (APP-001). De deur is onduidelijk (HQ-VR-003).",
     ["APP-001", "APP-012"], ["MAP-003", "MAP-004", "MAP-009"]),
    ("dakkapel", "P2", "Dakkapel links van de schoorstenen", ["VR-011"],
     [("FC-M2-019 en OBS-MAP003-001", [("MAP-002", "disp", (1020, 320, 1210, 460)), ("MAP-003", "disp", (30, 200, 300, 372))])],
     "Dezelfde dakkapel met drie-ruits kozijn naast de schoorstenen; in foto 2 als dormer-observatie (geen gewone kozijn-instance).",
     "Drie-ruits kozijn, houten wangen, naastgelegen schoorstenen.", "Alleen een andere kijkhoek; geen reden tot twijfel over de klasse DORMER_OPENING.",
     ["APP-011", "APP-031"], ["MAP-002", "MAP-003"]),
    ("dakramen_midden", "P2", "Dakramen links en midden in het hoofddakvlak", ["VR-012", "VR-013"],
     [("FC-M2-015 en OBS-MAP003-002", [("MAP-002", "disp", (1260, 380, 1400, 440)), ("MAP-003", "disp", (350, 275, 470, 350))]),
      ("FC-M2-016 en OBS-MAP003-003", [("MAP-002", "disp", (1760, 380, 1880, 450)), ("MAP-003", "disp", (900, 300, 990, 370))])],
     "De twee dakramen rechts van de dakkapel zijn op MAP-002 en MAP-003 zichtbaar, op gelijke onderlinge afstand.",
     "Dakraam-vorm en positie ten opzichte van de schoorstenen.", "Schuine kijkhoek in foto 2 vertekent de vorm; roof windows tellen niet mee in de bevroren foto-2-telling.",
     ["APP-011", "APP-031"], ["MAP-002", "MAP-003"]),
    ("dakraam_kap_links", "P2", "Dakraam in de kap boven de entreemuur 288/286", ["VR-003", "VR-052"],
     [("FC-M2-018, OBS-MAP003-017 en MAP-013", [("MAP-002", "disp", (1700, 700, 2000, 830)), ("MAP-003", "disp", (500, 640, 700, 760)), ("MAP-013", "ref", "REF-MAP013-003")])],
     "Het dakraam in de kap boven de entreemuur staat op MAP-002, MAP-003 en MAP-013.",
     "Tweedelig dakraam met loodslab onder het raam.", "Hoek verschilt per foto; verder weinig twijfel.",
     ["APP-011", "APP-013", "APP-031"], ["MAP-002", "MAP-003", "MAP-013"]),
    ("dakraam_kap_rechts", "P2", "Dakraam in de kap boven plaat 280/278", ["VR-023", "VR-040"],
     [("OBS-MAP003-021, OBS-MAP004-015 en MAP-009", [("MAP-003", "disp", (1540, 640, 1720, 780)), ("MAP-004", "disp", (720, 650, 900, 780)), ("MAP-009", "ref", "REF-MAP009-001")])],
     "Hetzelfde dakraam in de rechter kap op drie foto's.", "Tweedelig dakraam met loodslab; positie in het dakschild.",
     "Hoek verschilt per foto; verder weinig twijfel.", ["APP-012"], ["MAP-003", "MAP-004", "MAP-009"]),
    ("dakramen_hoofd", "P2", "Dakramen in het hoofddakvlak (MAP-003 en MAP-004)", ["VR-032", "VR-033", "VR-034"],
     [("OBS-MAP003-003/004 en OBS-MAP004-001/002", [("MAP-003", "disp", (890, 290, 1230, 390)), ("MAP-004", "disp", (330, 290, 670, 390))]),
      ("OBS-MAP003-005 en OBS-MAP004-003", [("MAP-003", "disp", (1600, 310, 1720, 400)), ("MAP-004", "disp", (1090, 310, 1230, 400))])],
     "De dakramen in het hoofddakvlak komen op beide foto's voor met een verschuiving van ongeveer 560 px.",
     "Gelijke onderlinge afstanden en positie onder de schoorsteen.", "Vormen verschillen door de kijkhoek; er is geen verborgen dakraam afgeleid.",
     ["APP-012"], ["MAP-003", "MAP-004"]),
    ("raam_276", "P2", "Raam bij plaat 276 (MAP-004, MAP-009 en detailfoto MAP-033)", ["VR-042", "VR-060"],
     [("OBS-MAP004-019 en MAP-033 / MAP-009", [("MAP-004", "disp", (800, 850, 1000, 970)), ("MAP-033", "ref", "REF-MAP033-001"), ("MAP-009", "ref", "REF-MAP009-004")])],
     "MAP-033 toont plaat 276 en het raam in één beeld; dat maakt de relatie plaatmuur-raam zichtbaar.",
     "Gordijn, raamverdeling, plaat 276 direct links van het raam.", "Alleen de plaatmuur is bewezen; MAP-009 toont de plaat niet volledig leesbaar.",
     ["APP-001", "APP-012"], ["MAP-004", "MAP-009", "MAP-033"]),
    ("ramen_284", "P2", "Raam bij plaat 284 (MAP-003 en MAP-013)", ["VR-051"],
     [("OBS-MAP003-023 en MAP-013", [("MAP-003", "disp", (600, 830, 790, 960)), ("MAP-013", "ref", "REF-MAP013-002")])],
     "MAP-013 toont de platen 288/286/284 in een schuine opname met het raam rechts van plaat 284.",
     "Plaat 284 links van het raam; beplakte ruit.", "Het raam krijgt geen pand tenzij de plaat-raamrelatie door een mens is bevestigd.",
     ["APP-001", "APP-013"], ["MAP-003", "MAP-013"]),
    ("rand_rechts", "P3", "Pand rechts aan de rand van MAP-003 en de grote ramen in MAP-004", ["VR-035"],
     [("Rechterrand MAP-003 en rechter pand MAP-004", [("MAP-003", "disp", (1750, 200, 2000, 700)), ("MAP-004", "disp", (1280, 160, 2000, 700))])],
     "Aan de rechterrand van MAP-003 is slechts een smalle strook van het pand zichtbaar dat in MAP-004 uitgebreid te zien is.",
     "Dakvorm en dakgoot lijken overeen te komen.", "Te weinig zichtbaar op MAP-003: niet te bepalen zonder aanvullende foto.",
     ["APP-012"], ["MAP-003", "MAP-004"]),
    ("links_alleen", "P3", "Linkerdeel van MAP-003 zonder tegenhanger op MAP-004", ["VR-036", "VR-037"],
     [("Links in MAP-003 (platen 288..282) en linker rand van MAP-004", [("MAP-003", "disp", (0, 830, 1000, 1010)), ("MAP-004", "disp", (0, 830, 400, 1010))])],
     "Objecten links van plaat 282 (en het raam bij plaat 282) liggen buiten MAP-004; geen overlap.",
     "Platen en muren verschillen; de linker rand van MAP-004 toont een ander pand.", "Geen; het is een afbakening van niet-overlappende delen.",
     ["APP-012"], ["MAP-003", "MAP-004"]),
]

# Voorlopige, niet-bindende voorstellen van Claude per klasse/sterkte (nooit een menselijk besluit)
def proposal_for_relation(klass, strength):
    if klass == "DIFFERENT_FRAMES":
        return "DIFFERENT"
    if klass == "UNDETERMINABLE":
        return "UNDECIDABLE"
    if klass == "SAME_FACADE_SECTION":
        return "SAME"
    return "SAME" if strength in ("HIGH", "MEDIUM") else "UNDECIDABLE"


def proposal_for_observation(o):
    if o["observation_type"] in ("EXTERIOR_DOOR", "UNKNOWN_OPENING") or o["uncertainty"] == "HIGH":
        return "UNDECIDABLE"
    return "CONFIRM"


def observation_priority(o, special):
    if o["observation_type"] in ("EXTERIOR_DOOR", "UNKNOWN_OPENING") or o["uncertainty"] == "HIGH" or o["obs_id"] in special:
        return "P1"
    if o["visibility"] != "FULL" or o["observation_type"] in ("ROOF_WINDOW", "DORMER_OPENING") or o["uncertainty"] == "MEDIUM":
        return "P2"
    return "P3"


# Waarneming die in sectie C (bijzondere aandacht) worden beoordeeld i.p.v. in sectie A
SPECIAL_THEMES = {
    "OBS-MAP003-009": ["onduidelijk object (apart smal raam of onderdeel van 010)"],
    "OBS-MAP003-010": ["onduidelijk object (hoort het smalle element bij dit kozijn?)"],
    "OBS-MAP003-006": ["gedeeltelijk zichtbaar", "beeldrand"],
    "OBS-MAP003-015": ["gedeeltelijk zichtbaar", "beeldrand"],
    "OBS-MAP003-016": ["gedeeltelijk zichtbaar", "afgedekt door de kap"],
    "OBS-MAP003-020": ["gedeeltelijk zichtbaar", "afgedekt door lantaarnpaal en kap", "beeldrand"],
    "OBS-MAP003-026": ["deur in entreenis"],
    "OBS-MAP003-027": ["deur in entreenis", "donker/schaduw"],
    "OBS-MAP003-028": ["afgedekt door begroeiing", "onbepaalde opening"],
    "OBS-MAP004-012": ["gedeeltelijk zichtbaar", "beeldrand"],
    "OBS-MAP004-014": ["gedeeltelijk zichtbaar", "afgedekt door de kap"],
    "OBS-MAP004-020": ["deur in entreenis"],
    "OBS-MAP004-021": ["afgedekt door begroeiing"],
    "OBS-MAP004-022": ["deur aan de beeldrand", "afgedekt door lantaarnpaal en auto"],
}

# Scheiding tussen kozijnen bij gemetselde penanten: (id, foto, obs links, obs rechts, toelichting)
SEPARATIONS = [
    ("RV-SEP-001", "MAP-003", 7, 8, "Penant tussen het tweedelige kozijn (007) en het smalle raam (008). Foto 2: FC-M2-002/003 zijn met een penant ertussen besloten als afzonderlijke kozijnen (PCD-00004)."),
    ("RV-SEP-002", "MAP-003", 11, 12, "Metselwerk tussen het tweedelige kozijn (011) en het smalle raam (012)."),
    ("RV-SEP-003", "MAP-003", 13, 14, "Metselwerk tussen het smalle raam (013) en het kozijn met open vleugel (014)."),
    ("RV-SEP-004", "MAP-004", 6, 7, "Penant tussen het tweedelige kozijn (006) en het smalle raam (007)."),
    ("RV-SEP-005", "MAP-004", 8, 9, "Metselwerk tussen het smalle raam (008) en het kozijn met open vleugel (009)."),
    ("RV-SEP-006", "MAP-004", 10, 11, "Metselwerk tussen het kozijn met open vleugel (010) en het smalle raam/de open vleugel (011) in het rechter pand."),
]

CHOICES_STD = ["CONFIRM", "REJECT", "UNDECIDABLE", "NEEDS_BETTER_PHOTO"]
CHOICES_OVERLAP = ["SAME", "DIFFERENT", "UNDECIDABLE"]

# Gevelsectie-overlap en objectoverlap zijn verschillende uitspraken. De waarde SAME betekent per relatietype iets anders en bewijst nooit een pandkoppeling.
FACADE_SECTION = "FACADE_SECTION"
PHYSICAL_OBJECT = "PHYSICAL_OBJECT"
MEANING = {
    FACADE_SECTION: {"SAME": "SAME_FACADE_SECTION", "DIFFERENT": "DIFFERENT_FACADE_SECTION", "UNDECIDABLE": "UNDECIDABLE"},
    PHYSICAL_OBJECT: {"SAME": "SAME_PHYSICAL_OBJECT_CANDIDATE", "DIFFERENT": "DIFFERENT_PHYSICAL_OBJECTS", "UNDECIDABLE": "UNDECIDABLE"},
}
MEANING_TEXT = {
    FACADE_SECTION: "Gevelsectie-overlap: SAME betekent uitsluitend dat beide foto's dezelfde gevelsectie (muur met plaat en omgeving) tonen. SAME betekent NIET dat een kozijn "
                    "hetzelfde fysieke kozijn is en bewijst geen pandkoppeling.",
    PHYSICAL_OBJECT: "Objectoverlap: SAME betekent dat de beide observaties, afzonderlijk beoordeeld, vermoedelijk hetzelfde fysieke object tonen (kandidaat). Het voegt niets samen, "
                     "maakt geen instance en bewijst geen pandkoppeling.",
}
IMPLIES_NONE = {"same_facade_section": False, "same_physical_object_candidate": False, "same_physical_frame_proven": False, "bag_pand_link": False, "merge": False, "unique_instance": False}


def ref_hash(item):
    """Stabiele korte hash van de bronverwijzingen van een reviewpunt; de import controleert dat een bestand bij dit pakket hoort."""
    import hashlib
    import json
    core = [item["review_id"], item["review_type"], item["observation_ids"], item["relation_ids"], item["evidence_refs"]]
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def relation_type(klass):
    """SAME_FACADE_SECTION is gevelniveau; alle andere klassen gaan over fysieke objecten."""
    return FACADE_SECTION if klass == "SAME_FACADE_SECTION" else PHYSICAL_OBJECT


def relation_semantics(klass, left, right):
    rt = relation_type(klass)
    n_to_1 = any(c in (left + right) for c in ("+", " / ", "/"))
    imp = dict(IMPLIES_NONE)
    if rt == FACADE_SECTION:
        imp["same_facade_section"] = True            # SAME bij een gevelrelatie = alleen dezelfde gevelsectie; same_physical_frame_proven blijft altijd False
    else:
        imp["same_physical_object_candidate"] = True  # SAME bij een objectrelatie = kandidaat; nooit bewezen, nooit samengevoegd
    return {"relation_type": rt, "endpoint_cardinality": "GROUP" if n_to_1 else "ONE_TO_ONE", "same_means": MEANING[rt]["SAME"], "meaning_text": MEANING_TEXT[rt],
            "implies_when_same": imp}


CHOICE_HELP = {
    "CONFIRM": "Klopt zoals voorgesteld",
    "REJECT": "Klopt niet",
    "UNDECIDABLE": "Niet te beslissen",
    "NEEDS_BETTER_PHOTO": "Betere foto nodig",
    "SAME": "Gevelsectie: dezelfde gevelsectie. Object: vermoedelijk hetzelfde fysieke object (kandidaat). Nooit een pandkoppeling.",
    "DIFFERENT": "Verschillende objecten",
}

# Bestaande vragen (HQ) -> prioriteit en voorlopig voorstel
HQ_PRIORITY = {
    "HQ-APP-001": "P1", "HQ-APP-002": "P1", "HQ-APP-003": "P1", "HQ-APP-011": "P1", "HQ-APP-012": "P1", "HQ-APP-013": "P1", "HQ-APP-031": "P1",
    "HQ-APP-034": "P1", "HQ-APP-035": "P1", "HQ-VR-001": "P1", "HQ-VR-002": "P1", "HQ-VR-003": "P1", "HQ-VR-004": "P3",
}
HQ_PROPOSAL = {
    "HQ-APP-001": "CONFIRM", "HQ-APP-002": "CONFIRM", "HQ-APP-003": "CONFIRM", "HQ-APP-011": "UNDECIDABLE", "HQ-APP-012": "UNDECIDABLE",
    "HQ-APP-013": "CONFIRM", "HQ-APP-031": "CONFIRM", "HQ-APP-034": "CONFIRM", "HQ-APP-035": "CONFIRM", "HQ-VR-001": "UNDECIDABLE",
    "HQ-VR-002": "CONFIRM", "HQ-VR-003": "UNDECIDABLE", "HQ-VR-004": "NEEDS_BETTER_PHOTO",
}
