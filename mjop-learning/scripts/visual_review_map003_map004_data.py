"""Handmatige visuele lezing (MANUAL_VISUAL_READING) voor Maldenhof Visual Photo Review v1 - MAP-003 & MAP-004.

Alle bboxen zijn in pixels van het ORIGINELE bestand (2048x1536). Ze zijn handmatig bepaald op een weergave van 2000x1500 en met
SCALE (2048/2000) omgerekend; ze zijn dus een visuele lezing en geen meting. Geen enkele observatie is een instance.
"""
SCALE = 1.024


def D(x0, y0, x1, y1):
    return [round(v * SCALE) for v in (x0, y0, x1, y1)]


# (nr, type, visibility, bbox(display), positie, toelichting, onzekerheid)
# type: WINDOW_OPENING | EXTERIOR_DOOR | WINDOW_DOOR_COMBINATION | ROOF_WINDOW | DORMER_OPENING | UNKNOWN_OPENING
# visibility: FULL | PARTIAL | HEAVILY_OCCLUDED | UNKNOWN_OPENING
MAP003 = [
    (1, "DORMER_OPENING", "FULL", (40, 215, 265, 345), "dakvlak links", "Dakkapel met drie-ruits kozijn (een dakkapelopening).", "LOW"),
    (2, "ROOF_WINDOW", "FULL", (372, 290, 447, 335), "dakvlak links", "Dakraam.", "LOW"),
    (3, "ROOF_WINDOW", "FULL", (918, 311, 972, 358), "dakvlak midden", "Dakraam.", "LOW"),
    (4, "ROOF_WINDOW", "FULL", (1146, 316, 1208, 362), "dakvlak midden-rechts", "Dakraam.", "LOW"),
    (5, "ROOF_WINDOW", "FULL", (1638, 337, 1680, 377), "dakvlak rechts", "Dakraam.", "LOW"),
    (6, "WINDOW_OPENING", "PARTIAL", (0, 433, 150, 528), "bovenste gevelrij links", "Raam met open vleugel rechts; linkerdeel buiten beeld.", "MEDIUM"),
    (7, "WINDOW_OPENING", "FULL", (308, 445, 467, 535), "bovenste gevelrij", "Tweedelig kozijn met zichtbare vleugels; een opening.", "LOW"),
    (8, "WINDOW_OPENING", "FULL", (503, 449, 560, 534), "bovenste gevelrij", "Smal raam; gemetselde penant (zichtbaar metselwerk) tussen 007 en 008.", "LOW"),
    (9, "WINDOW_OPENING", "FULL", (765, 442, 822, 550), "bovenste gevelrij", "Smal linker element naast het hoofdkozijn; of een apart kozijn (zoals in foto 2 bij FC-M2-006-A is besloten) of een vleugel van 010 is op deze resolutie niet te beslissen.", "HIGH"),
    (10, "WINDOW_OPENING", "FULL", (822, 442, 1000, 550), "bovenste gevelrij", "Hoofdkozijn met gordijn en twee open vleugels; een opening (kozijnstijl/vleugel scheidt niet).", "MEDIUM"),
    (11, "WINDOW_OPENING", "FULL", (1140, 470, 1285, 558), "bovenste gevelrij", "Tweedelig kozijn; een opening.", "LOW"),
    (12, "WINDOW_OPENING", "FULL", (1318, 474, 1373, 558), "bovenste gevelrij", "Smal raam; gemetselde penant tussen 011 en 012.", "LOW"),
    (13, "WINDOW_OPENING", "FULL", (1558, 478, 1610, 562), "bovenste gevelrij rechts", "Smal raam met gordijn.", "LOW"),
    (14, "WINDOW_OPENING", "FULL", (1643, 480, 1783, 570), "bovenste gevelrij rechts", "Kozijn met open vleugel rechts; een opening.", "MEDIUM"),
    (15, "WINDOW_OPENING", "PARTIAL", (0, 622, 78, 756), "middelste rij links", "Raam met onderpaneel; linkerdeel buiten beeld.", "MEDIUM"),
    (16, "WINDOW_OPENING", "PARTIAL", (246, 627, 360, 762), "middelste rij", "Raam met onderpaneel; rechterdeel wordt deels door het dakschild van de kap bedekt.", "MEDIUM"),
    (17, "ROOF_WINDOW", "FULL", (530, 660, 657, 738), "kap links", "Dakraam in het dakschild van de linker kap.", "LOW"),
    (18, "WINDOW_OPENING", "FULL", (851, 640, 1010, 770), "middelste rij", "Raam met open vleugel rechts en wit onderpaneel; een opening.", "MEDIUM"),
    (19, "WINDOW_OPENING", "FULL", (1163, 648, 1320, 773), "middelste rij", "Raam met wit onderpaneel; een opening.", "LOW"),
    (20, "WINDOW_OPENING", "PARTIAL", (1818, 655, 1866, 745), "middelste rij rechts", "Smal zichtbaar deel van een raam achter lantaarnpaal en kap-hoek; verder verborgen.", "HIGH"),
    (21, "ROOF_WINDOW", "FULL", (1563, 680, 1690, 755), "kap rechts", "Dakraam in het dakschild van de rechter kap.", "LOW"),
    (22, "WINDOW_OPENING", "FULL", (244, 838, 336, 926), "begane grond, naast plaat 286", "Raam met gordijn in de entreemuur.", "LOW"),
    (23, "WINDOW_OPENING", "FULL", (645, 843, 730, 928), "begane grond, naast plaat 284", "Raam; ruit afgeplakt/beplakt.", "LOW"),
    (24, "WINDOW_OPENING", "FULL", (946, 870, 1050, 962), "begane grond, naast plaat 282", "Raam met zware kozijnstijl.", "LOW"),
    (25, "WINDOW_OPENING", "FULL", (1652, 853, 1732, 935), "begane grond, naast plaat 278", "Raam in de entreemuur.", "LOW"),
    (26, "EXTERIOR_DOOR", "PARTIAL", (432, 860, 492, 1045), "begane grond, entreenis", "Rode deur in de entreenis; deels in schaduw.", "MEDIUM"),
    (27, "EXTERIOR_DOOR", "PARTIAL", (1768, 872, 1822, 935), "begane grond, entreenis rechts", "Donkere deur rechts van het raam bij plaat 278; sterke schaduw.", "HIGH"),
    (28, "UNKNOWN_OPENING", "UNKNOWN_OPENING", (1122, 868, 1138, 892), "begane grond, achter hortensia", "Mogelijke opening naast 024 achter hortensia; niet vast te stellen.", "HIGH"),
]

MAP004 = [
    (1, "ROOF_WINDOW", "FULL", (350, 312, 416, 353), "dakvlak links", "Dakraam.", "LOW"),
    (2, "ROOF_WINDOW", "FULL", (587, 310, 657, 354), "dakvlak midden", "Dakraam.", "LOW"),
    (3, "ROOF_WINDOW", "FULL", (1133, 317, 1193, 361), "dakvlak midden-rechts", "Dakraam.", "LOW"),
    (4, "ROOF_WINDOW", "FULL", (1428, 238, 1505, 285), "dakvlak rechter pand", "Dakraam in het hogere dakvlak rechts.", "LOW"),
    (5, "WINDOW_OPENING", "FULL", (124, 442, 380, 547), "bovenste gevelrij links", "Raam met gordijn en twee open vleugels; een opening (een mogelijk apart smal linker element is niet te onderscheiden).", "MEDIUM"),
    (6, "WINDOW_OPENING", "FULL", (522, 466, 676, 556), "bovenste gevelrij", "Tweedelig kozijn; een opening.", "LOW"),
    (7, "WINDOW_OPENING", "FULL", (712, 468, 772, 552), "bovenste gevelrij", "Smal raam; gemetselde penant tussen 006 en 007.", "LOW"),
    (8, "WINDOW_OPENING", "FULL", (972, 472, 1030, 558), "bovenste gevelrij", "Smal raam met gordijn.", "LOW"),
    (9, "WINDOW_OPENING", "FULL", (1066, 470, 1225, 565), "bovenste gevelrij", "Kozijn met open vleugel rechts; een opening.", "MEDIUM"),
    (10, "WINDOW_OPENING", "FULL", (1433, 396, 1614, 515), "bovenste gevelrij rechter pand", "Kozijn met open vleugel links; een opening.", "MEDIUM"),
    (11, "WINDOW_OPENING", "FULL", (1656, 404, 1730, 512), "bovenste gevelrij rechter pand", "Smal raam/open vleugel rechts naast 010; afzonderlijk door gemetselde penant (indruk).", "MEDIUM"),
    (12, "WINDOW_OPENING", "PARTIAL", (1970, 410, 2000, 497), "bovenste gevelrij rechter pand", "Smalle strook van een raam aan de beeldrand.", "HIGH"),
    (13, "WINDOW_OPENING", "FULL", (135, 643, 305, 780), "middelste rij", "Raam met open vleugel rechts en wit onderpaneel; een opening.", "MEDIUM"),
    (14, "WINDOW_OPENING", "PARTIAL", (460, 650, 570, 782), "middelste rij", "Raam met onderpaneel; rechterdeel achter het dakschild van de kap.", "MEDIUM"),
    (15, "ROOF_WINDOW", "FULL", (745, 678, 872, 745), "kap midden", "Dakraam in het dakschild van de kap.", "LOW"),
    (16, "WINDOW_OPENING", "FULL", (1070, 660, 1265, 795), "middelste rij", "Raam met open vleugel rechts en wit onderpaneel; een opening.", "MEDIUM"),
    (17, "WINDOW_OPENING", "FULL", (1475, 617, 1680, 778), "middelste rij rechter pand", "Groot raam met open vleugel links en onderpaneel; een opening.", "MEDIUM"),
    (18, "WINDOW_OPENING", "FULL", (460, 858, 552, 950), "begane grond, naast plaat 278", "Raam in de entreemuur.", "LOW"),
    (19, "WINDOW_OPENING", "FULL", (866, 865, 958, 958), "begane grond, naast plaat 276", "Raam met gordijn in de entreemuur.", "LOW"),
    (20, "EXTERIOR_DOOR", "PARTIAL", (640, 880, 705, 1100), "begane grond, entreenis", "Rode deur in de entreenis; trap daarachter.", "MEDIUM"),
    (21, "WINDOW_OPENING", "FULL", (1424, 903, 1635, 1025), "begane grond rechter pand", "Groot raam; beplanting voor de onderkant.", "MEDIUM"),
    (22, "EXTERIOR_DOOR", "PARTIAL", (45, 905, 82, 950), "begane grond, beeldrand links", "Rode deur met wit kozijn aan de linkerrand van het beeld (vergroting); grotendeels buiten beeld of achter lantaarnpaal/auto, behoort bij het buurpand links.", "HIGH"),
]

# Huisnummerplaten (display-coordinaten): (nr, leesbaar cijfer, bbox, status, toelichting)
PLATES003 = [
    (288, (16, 860, 48, 884)), (286, (344, 860, 374, 886)), (284, (606, 864, 637, 889)), (282, (910, 866, 940, 891)),
    (280, (1453, 872, 1485, 894)), (278, (1735, 874, 1767, 897)), (276, (1966, 876, 2000, 898)),
]
PLATES004 = [
    (280, (237, 876, 267, 902)), (278, (557, 884, 589, 908)), (276, (830, 888, 861, 912)), (274, (1154, 894, 1185, 918)),
]


# --- Referentiegebieden in de aanvullende foto's (geen observaties; alleen om overlap te kunnen aanwijzen) --------------------------
# (ref_id, foto, bbox in weergave-coordinaten, schaal naar origineel, beschrijving)
REFS = [
    ("REF-MAP009-001", "MAP-009", (905, 640, 1050, 740), "Dakraam in het dakschild van de kap rechts"),
    ("REF-MAP009-002", "MAP-009", (270, 500, 530, 720), "Raam met wit onderpaneel en flessen op de dorpel (links van de kap)"),
    ("REF-MAP009-003", "MAP-009", (1290, 870, 1350, 995), "Raam naast plaat 278"),
    ("REF-MAP009-004", "MAP-009", (1503, 892, 1542, 985), "Raam naast de (deels leesbare) plaat rechts van 278"),
    ("REF-MAP009-005", "MAP-009", (1325, 690, 1395, 795), "Raam met open vleugel en onderpaneel rechts van de kap"),
    ("REF-MAP009-006", "MAP-009", (222, 222, 458, 418), "Tweedelig kozijn bovenste gevelrij (met smal raam rechts ervan)"),
    ("REF-MAP013-001", "MAP-013", (808, 740, 938, 948), "Raam tussen plaat 288 en plaat 286"),
    ("REF-MAP013-002", "MAP-013", (1245, 790, 1305, 925), "Raam rechts van plaat 284"),
    ("REF-MAP013-003", "MAP-013", (458, 448, 665, 585), "Dakraam in het dakschild van de kap links"),
    ("REF-MAP013-004", "MAP-013", (410, 200, 695, 360), "Raam met open vleugels in de bovenste gevelrij"),
    ("REF-MAP013-005", "MAP-013", (822, 372, 992, 495), "Tweedelig kozijn met smal raam in de bovenste gevelrij"),
    ("REF-MAP033-001", "MAP-033", (455, 180, 1380, 1170), "Raam met gordijn rechts van plaat 276 (detailfoto)"),
]
REF_SCALE = 1.632

# Relaties tussen observaties/referenties in verschillende foto's. Alleen kandidaat-relaties; niets is samengevoegd.
# (rel_id, soc, links, rechts, klasse, sterkte, grondslag)
# klasse: SAME_FACADE_SECTION | POSSIBLY_SAME_PHYSICAL_FRAME | DIFFERENT_FRAMES | UNDETERMINABLE
RELATIONS = [
    # --- SOC-001: MAP-002 <-> MAP-003 -----------------------------------------------------------------------------------------------
    ("VR-001", "SOC-001", "MAP-002:plaat 288 + muur", "MAP-003:P-288 + muur", "SAME_FACADE_SECTION", "HIGH", "Plaat 288 met ernaast een raam (rechts van de plaat) en erboven de kap met dakraam; schoorstenen en dakkapel zichtbaar in dezelfde volgorde."),
    ("VR-002", "SOC-001", "MAP-002:FC-M2-009 (FI-M2-012)", "MAP-003:OBS-MAP003-022", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "In beide foto's het raam direct rechts van plaat 288 in dezelfde muur; verschuiving komt overeen met die van de plaat. Alleen aangrenzing, geen bewijs."),
    ("VR-003", "SOC-001", "MAP-002:FC-M2-018 (roof)", "MAP-003:OBS-MAP003-017", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Dakraam in het dakschild van dezelfde kap boven de entreemuur 288/286."),
    ("VR-004", "SOC-001", "MAP-002:FC-M2-008 (FI-M2-011, PARTIAL)", "MAP-003:OBS-MAP003-016", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam met onderpaneel direct links naast de kap; in beide foto's deels door de kap bedekt (PARTIAL)."),
    ("VR-005", "SOC-001", "MAP-002:FC-M2-007 (FI-M2-010)", "MAP-003:OBS-MAP003-015", "POSSIBLY_SAME_PHYSICAL_FRAME", "LOW", "Volgend raam links in dezelfde rij; in MAP-003 aan de beeldrand afgesneden, dus de koppeling berust op de rijvolgorde en niet op een uniek kenmerk."),
    ("VR-006", "SOC-001", "MAP-002:FC-M2-004 (FI-M2-005)", "MAP-003:OBS-MAP003-007", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Tweedelig kozijn in de bovenste rij; smal raam met penant rechts ervan in beide foto's."),
    ("VR-007", "SOC-001", "MAP-002:FC-M2-005 (FI-M2-006)", "MAP-003:OBS-MAP003-008", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Smal raam rechts naast het tweedelige kozijn."),
    ("VR-008", "SOC-001", "MAP-002:FC-M2-006-A (FI-M2-007)", "MAP-003:OBS-MAP003-009", "UNDETERMINABLE", "LOW", "Het smalle linker element is in foto 2 als apart kozijn besloten (PCD); in MAP-003 is niet te zien of dit een apart kozijn of een vleugel is."),
    ("VR-009", "SOC-001", "MAP-002:FC-M2-006-BC (FI-M2-014)", "MAP-003:OBS-MAP003-010", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Hoofdkozijn met gordijn en twee open vleugels; zelfde open vleugels en gordijn in beide foto's."),
    ("VR-010", "SOC-001", "MAP-002:FC-M2-003 (FI-M2-004)", "MAP-003:OBS-MAP003-006", "UNDETERMINABLE", "LOW", "MAP-003 toont slechts de rechterhelft van het kozijn aan de beeldrand; open vleugel rechts komt overeen, maar het kozijn is niet volledig vergelijkbaar."),
    ("VR-011", "SOC-001", "MAP-002:FC-M2-019 (dormer)", "MAP-003:OBS-MAP003-001", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Dakkapel met drie-ruits kozijn links naast de schoorstenen; dormer-opening, geen gewone kozijninstance."),
    ("VR-012", "SOC-001", "MAP-002:FC-M2-015", "MAP-003:OBS-MAP003-002", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Dakraam links van de rechter schoorsteenparen; dakvlak-verschuiving komt overeen."),
    ("VR-013", "SOC-001", "MAP-002:FC-M2-016", "MAP-003:OBS-MAP003-003", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Tweede dakraam rechts van de schoorstenen."),
    # --- SOC-002: MAP-003 <-> MAP-004 --------------------------------------------------------------------------------------------------
    ("VR-020", "SOC-002", "MAP-003:P-280/P-278/P-276", "MAP-004:P-280/P-278/P-276", "SAME_FACADE_SECTION", "HIGH", "Drie platen en de bijbehorende entreemuren in beide foto's (MAP-003 onderrand rechts; MAP-004 links/midden). Plaat bewijst alleen de muur."),
    ("VR-021", "SOC-002", "MAP-003:OBS-MAP003-025", "MAP-004:OBS-MAP004-018", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Raam direct bij plaat 278 in dezelfde muur."),
    ("VR-022", "SOC-002", "MAP-003:OBS-MAP003-027", "MAP-004:OBS-MAP004-020", "POSSIBLY_SAME_PHYSICAL_FRAME", "LOW", "Deur in de entreenis tussen de platen 278 en 276; in MAP-003 zeer donker en bijna aan de rand."),
    ("VR-023", "SOC-002", "MAP-003:OBS-MAP003-021", "MAP-004:OBS-MAP004-015", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Dakraam in het dakschild van de kap boven plaat 280/278 (zelfde kap)."),
    ("VR-024", "SOC-002", "MAP-003:OBS-MAP003-018", "MAP-004:OBS-MAP004-013", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam met open vleugel rechts en onderpaneel links van de kap."),
    ("VR-025", "SOC-002", "MAP-003:OBS-MAP003-019", "MAP-004:OBS-MAP004-014", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam met onderpaneel direct links van de kap; in MAP-004 deels door de kap bedekt."),
    ("VR-026", "SOC-002", "MAP-003:OBS-MAP003-020", "MAP-004:OBS-MAP004-016", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam rechts van de kap met open vleugel en onderpaneel; in MAP-003 grotendeels verborgen."),
    ("VR-027", "SOC-002", "MAP-003:OBS-MAP003-011", "MAP-004:OBS-MAP004-006", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Tweedelig kozijn bovenste rij boven de kap."),
    ("VR-028", "SOC-002", "MAP-003:OBS-MAP003-012", "MAP-004:OBS-MAP004-007", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Smal raam rechts naast het tweedelige kozijn."),
    ("VR-029", "SOC-002", "MAP-003:OBS-MAP003-013", "MAP-004:OBS-MAP004-008", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Smal raam met gordijn in de bovenste rij rechts."),
    ("VR-030", "SOC-002", "MAP-003:OBS-MAP003-014", "MAP-004:OBS-MAP004-009", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Kozijn met open vleugel rechts."),
    ("VR-031", "SOC-002", "MAP-003:OBS-MAP003-009+010", "MAP-004:OBS-MAP004-005", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Zelfde raam met gordijn en twee open vleugels; in MAP-003 twee observaties (smal links + hoofdkozijn), in MAP-004 een observatie: telverschil is een leesverschil, geen extra raam."),
    ("VR-032", "SOC-002", "MAP-003:OBS-MAP003-003", "MAP-004:OBS-MAP004-001", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Dakraam in het hoofddakvlak."),
    ("VR-033", "SOC-002", "MAP-003:OBS-MAP003-004", "MAP-004:OBS-MAP004-002", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Dakraam in het hoofddakvlak."),
    ("VR-034", "SOC-002", "MAP-003:OBS-MAP003-005", "MAP-004:OBS-MAP004-003", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Dakraam in het hoofddakvlak rechts."),
    ("VR-035", "SOC-002", "MAP-003:rechterrand (pand rechts)", "MAP-004:OBS-MAP004-004/010/011/012/017/021", "UNDETERMINABLE", "LOW", "MAP-003 toont aan de rechterrand slechts een smalle strook van het pand rechts; de grote ramen van dat pand in MAP-004 zijn in MAP-003 niet te vergelijken."),
    ("VR-036", "SOC-002", "MAP-003:OBS-MAP003-024 (raam 282)", "MAP-004: buiten beeld", "DIFFERENT_FRAMES", "HIGH", "Het raam bij plaat 282 ligt links van het zichtbare deel van MAP-004; geen overlap."),
    ("VR-037", "SOC-002", "MAP-003:OBS-MAP003-022 / 023 / 026 (platen 288..284)", "MAP-004: buiten beeld", "DIFFERENT_FRAMES", "HIGH", "Objecten links van plaat 282 komen in MAP-004 niet voor."),
    # --- SOC-002 (MAP-009), SOC-003 (MAP-013), SOC-008 (MAP-033): referentiegebieden ------------------------------------------------------------
    ("VR-040", "SOC-002", "MAP-004:OBS-MAP004-015 / MAP-003:OBS-MAP003-021", "MAP-009:REF-MAP009-001", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Dakraam in het dakschild van dezelfde kap, schuin vanaf links gezien."),
    ("VR-041", "SOC-002", "MAP-003:OBS-MAP003-025 / MAP-004:OBS-MAP004-018", "MAP-009:REF-MAP009-003", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Raam direct rechts van plaat 278 (plaat zichtbaar in alle drie)."),
    ("VR-042", "SOC-002", "MAP-004:OBS-MAP004-019", "MAP-009:REF-MAP009-004", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam naast de plaat rechts van 278 (276), plaat in MAP-009 niet volledig leesbaar."),
    ("VR-043", "SOC-002", "MAP-003:OBS-MAP003-019 / MAP-004:OBS-MAP004-014", "MAP-009:REF-MAP009-002", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam met onderpaneel links van de kap; flessen op de dorpel zijn in MAP-003 en MAP-009 zichtbaar."),
    ("VR-044", "SOC-002", "MAP-003:OBS-MAP003-020 / MAP-004:OBS-MAP004-016", "MAP-009:REF-MAP009-005", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam met open vleugel rechts van de kap."),
    ("VR-045", "SOC-002", "MAP-003:OBS-MAP003-011/012 / MAP-004:OBS-MAP004-006/007", "MAP-009:REF-MAP009-006", "POSSIBLY_SAME_PHYSICAL_FRAME", "LOW", "Bovenste rij: kozijn met smal raam; MAP-009 is sterk verkort, dus alleen overeenkomstige indeling."),
    ("VR-050", "SOC-003", "MAP-003:OBS-MAP003-022", "MAP-013:REF-MAP013-001", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Raam tussen de platen 288 en 286 (beide platen in beide foto's leesbaar)."),
    ("VR-051", "SOC-003", "MAP-003:OBS-MAP003-023", "MAP-013:REF-MAP013-002", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Raam direct rechts van plaat 284."),
    ("VR-052", "SOC-003", "MAP-003:OBS-MAP003-017", "MAP-013:REF-MAP013-003", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Dakraam van de kap boven de entreemuren 288/286."),
    ("VR-053", "SOC-003", "MAP-003:OBS-MAP003-009+010", "MAP-013:REF-MAP013-004", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Raam met open vleugels in de bovenste rij."),
    ("VR-054", "SOC-003", "MAP-003:OBS-MAP003-007+008", "MAP-013:REF-MAP013-005", "POSSIBLY_SAME_PHYSICAL_FRAME", "MEDIUM", "Tweedelig kozijn met smal raam in de bovenste rij."),
    ("VR-060", "SOC-008", "MAP-004:OBS-MAP004-019", "MAP-033:REF-MAP033-001", "POSSIBLY_SAME_PHYSICAL_FRAME", "HIGH", "Gordijnraam direct rechts van plaat 276 in dezelfde muur; MAP-033 is een detailfoto met plaat en raam in een beeld."),
]

# Aan te bevelen menselijke vragen: (id, onderwerp, vraag, aanbevolen antwoord, gekoppeld APP-besluit of None)
QUESTIONS = [
    ("HQ-APP-001", "Plaatregel", "Akkoord dat een leesbare plaat alleen de muur met die plaat aan een pand koppelt?", "JA", "APP-001"),
    ("HQ-APP-002", "Plaatlezing MAP-003", "Zijn de zeven platen 288, 286, 284, 282, 280, 278, 276 op de vergrotingen (afbeelding E) correct gelezen?", "JA", "APP-002"),
    ("HQ-APP-003", "Plaatlezing MAP-004", "Zijn de vier platen 280, 278, 276, 274 correct gelezen?", "JA", "APP-003"),
    ("HQ-APP-011", "Overlap MAP-002/MAP-003", "Zijn de ramen/dakramen/dakkapel uit afbeelding D per paar SAME / DIFFERENT / UNDECIDABLE? Aanbevolen: SAME voor VR-002, VR-003, VR-004, VR-006, VR-009; UNDECIDABLE voor VR-005, VR-008, VR-010.", "per paar", "APP-011"),
    ("HQ-APP-012", "Overlap MAP-003/MAP-004/MAP-009", "Zijn de paren uit afbeelding C per paar SAME / DIFFERENT / UNDECIDABLE? Aanbevolen: SAME voor VR-021, VR-023; MEDIUM-paren na eigen controle; UNDECIDABLE voor VR-035.", "per paar", "APP-012"),
    ("HQ-APP-013", "Overlap MAP-003/MAP-013", "Zijn REF-MAP013-001 en -002 dezelfde ramen als OBS-MAP003-022 en -023 (SAME)?", "SAME (aanbevolen)", "APP-013"),
    ("HQ-APP-031", "Overlapzone met bevroren foto 2", "Mogen de MAP-003-kandidaten rond plaat 288 als aparte kandidaten met overlapmarkering blijven staan, zonder optelling bij foto 2?", "JA", "APP-031"),
    ("HQ-APP-034", "Geschiktheid MAP-003", "Is MAP-003 na deze visuele controle geschikt als annotatiebron (READY_FOR_REVIEW), met de open punten OBS-MAP003-009/-020/-027/-028?", "JA", "APP-034"),
    ("HQ-APP-035", "Geschiktheid MAP-004", "Is MAP-004 geschikt als annotatiebron, met de open punten OBS-MAP004-005/-012/-022?", "JA", "APP-035"),
    ("HQ-VR-001", "Smal linker element (MAP-003 OBS-009)", "Is het smalle element links van het hoofdkozijn een apart kozijn (zoals foto 2 FC-M2-006-A) of een vleugel van OBS-010?", "UNDECIDABLE tot betere foto", None),
    ("HQ-VR-002", "Telconventie penant tussen kozijnen", "Bevestigen dat het metselwerk tussen OBS-MAP003-007 en -008 (en 011/012, 013/014) de openingen scheidt (afzonderlijke openingen), conform foto 2 PCD-00004?", "JA", None),
    ("HQ-VR-003", "Deuren in de entreenissen", "Zijn OBS-MAP003-026/027 en OBS-MAP004-020/022 buitendeuren die tot de te tellen elementen behoren (ja/nee), of alleen entree-context?", "later beslissen", None),
    ("HQ-VR-004", "Pandkoppeling per ruimte", "Welke aanvullende bewijsfoto's (plaat op dezelfde muur als het raam) zijn gewenst voor pand 10-13 voordat ramen aan een pand worden gekoppeld?", "extra detailfoto's per plaatmuur", None),
]
