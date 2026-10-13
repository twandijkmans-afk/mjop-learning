# Maldenhof Visual Photo Review v1 - MAP-003 & MAP-004

**Status:** visueel controlepakket, uitsluitend voor menselijke beoordeling. Er zijn geen instances, geen pandkoppelingen, geen unieke aantallen, geen maten, kosten of repeat-multipliers vastgelegd. Alle 48 APP-besluiten uit `maldenhof_photo_annotation_approval_v1.md` blijven OPEN. Foto 2 blijft bevroren (11 gewone kozijnen, 1 buitendeur; 9 FULL, 2 PARTIAL).

Bewijsniveaus: (1) zichtbare observatie, (2) kandidaat voor een fysiek object, (3) bewezen uniek fysiek exemplaar, (4) bewezen koppeling aan een specifiek pand. Dit document komt niet verder dan niveau 1-2; een leesbare plaat bewijst alleen de muur met die plaat (APP-001).

## 1. Bronnen en verificatie

| Foto | Bestand | Pad in zip | Resolutie | SHA256 (register) | Tegen origineel geverifieerd |
|---|---|---|---|---|---|
| MAP-002 | IMG_8517.JPEG | Opname 14-08-2026/IMG_8517.JPEG | 2048x1536 | dacdd5e7c2bdb22e... | JA |
| MAP-003 | IMG_8518.JPEG | Opname 14-08-2026/IMG_8518.JPEG | 2048x1536 | 9f121e711b0cea13... | JA |
| MAP-004 | IMG_8520.JPEG | Opname 14-08-2026/IMG_8520.JPEG | 2048x1536 | 197556869a8e91a9... | JA |
| MAP-009 | P1000236.JPG | Opname 14-08-2026/P1000236.JPG | 3264x2448 | 15591a9648ddfec7... | JA |
| MAP-013 | P1000294.JPG | Opname 14-08-2026/P1000294.JPG | 3264x2448 | d7d8839fc966a927... | JA |
| MAP-033 | P1000229.JPG | Opname 14-08-2026/P1000229.JPG | 3264x2448 | f2d13c4cb991bbb3... | JA |

De originelen (zip in `/mnt/project-files`) zijn op volle resolutie geopend en tegen het register uit de Photo Archive Audit gecontroleerd; de originelen staan niet in Git. De afbeeldingen in deze map bevatten uitsluitend uitsneden, vergrotingen en annotaties van de originele pixels (geen gegenereerde beeldinhoud). MAP-002 is de bron van de bevroren foto 2 (`maldenhof_2`); de foto-2-annotaties zijn uit de bestaande bevroren bestanden overgenomen en niet gewijzigd. MAP-009, MAP-013 en MAP-033 zijn alleen als referentie voor overlap gebruikt (afbeelding F).

## 2. Overzicht van alle voorlopige observatie-ID's

Tijdelijke ID's, buiten het instance-archief. Een observatie is een zichtbare opening en geen telling; bboxen zijn handmatig bepaald op de originele pixels (MANUAL_VISUAL_READING, geen meting).

### MAP-003

| Observatie | Type | Zichtbaarheid | bbox px [x0,y0,x1,y1] | Positie | Onzekerheid | Toelichting |
|---|---|---|---|---|---|---|
| OBS-MAP003-001 | DORMER_OPENING | FULL | [41, 220, 271, 353] | dakvlak links | LOW | Dakkapel met drie-ruits kozijn (een dakkapelopening). |
| OBS-MAP003-002 | ROOF_WINDOW | FULL | [381, 297, 458, 343] | dakvlak links | LOW | Dakraam. |
| OBS-MAP003-003 | ROOF_WINDOW | FULL | [940, 318, 995, 367] | dakvlak midden | LOW | Dakraam. |
| OBS-MAP003-004 | ROOF_WINDOW | FULL | [1174, 324, 1237, 371] | dakvlak midden-rechts | LOW | Dakraam. |
| OBS-MAP003-005 | ROOF_WINDOW | FULL | [1677, 345, 1720, 386] | dakvlak rechts | LOW | Dakraam. |
| OBS-MAP003-006 | WINDOW_OPENING | PARTIAL | [0, 443, 154, 541] | bovenste gevelrij links | MEDIUM | Raam met open vleugel rechts; linkerdeel buiten beeld. |
| OBS-MAP003-007 | WINDOW_OPENING | FULL | [315, 456, 478, 548] | bovenste gevelrij | LOW | Tweedelig kozijn met zichtbare vleugels; een opening. |
| OBS-MAP003-008 | WINDOW_OPENING | FULL | [515, 460, 573, 547] | bovenste gevelrij | LOW | Smal raam; gemetselde penant (zichtbaar metselwerk) tussen 007 en 008. |
| OBS-MAP003-009 | WINDOW_OPENING | FULL | [783, 453, 842, 563] | bovenste gevelrij | HIGH | Smal linker element naast het hoofdkozijn; of een apart kozijn (zoals in foto 2 bij FC-M2-006-A is besloten) of een vleugel van 010 is op deze resolutie niet te beslissen. |
| OBS-MAP003-010 | WINDOW_OPENING | FULL | [842, 453, 1024, 563] | bovenste gevelrij | MEDIUM | Hoofdkozijn met gordijn en twee open vleugels; een opening (kozijnstijl/vleugel scheidt niet). |
| OBS-MAP003-011 | WINDOW_OPENING | FULL | [1167, 481, 1316, 571] | bovenste gevelrij | LOW | Tweedelig kozijn; een opening. |
| OBS-MAP003-012 | WINDOW_OPENING | FULL | [1350, 485, 1406, 571] | bovenste gevelrij | LOW | Smal raam; gemetselde penant tussen 011 en 012. |
| OBS-MAP003-013 | WINDOW_OPENING | FULL | [1595, 489, 1649, 575] | bovenste gevelrij rechts | LOW | Smal raam met gordijn. |
| OBS-MAP003-014 | WINDOW_OPENING | FULL | [1682, 492, 1826, 584] | bovenste gevelrij rechts | MEDIUM | Kozijn met open vleugel rechts; een opening. |
| OBS-MAP003-015 | WINDOW_OPENING | PARTIAL | [0, 637, 80, 774] | middelste rij links | MEDIUM | Raam met onderpaneel; linkerdeel buiten beeld. |
| OBS-MAP003-016 | WINDOW_OPENING | PARTIAL | [252, 642, 369, 780] | middelste rij | MEDIUM | Raam met onderpaneel; rechterdeel wordt deels door het dakschild van de kap bedekt. |
| OBS-MAP003-017 | ROOF_WINDOW | FULL | [543, 676, 673, 756] | kap links | LOW | Dakraam in het dakschild van de linker kap. |
| OBS-MAP003-018 | WINDOW_OPENING | FULL | [871, 655, 1034, 788] | middelste rij | MEDIUM | Raam met open vleugel rechts en wit onderpaneel; een opening. |
| OBS-MAP003-019 | WINDOW_OPENING | FULL | [1191, 664, 1352, 792] | middelste rij | LOW | Raam met wit onderpaneel; een opening. |
| OBS-MAP003-020 | WINDOW_OPENING | PARTIAL | [1862, 671, 1911, 763] | middelste rij rechts | HIGH | Smal zichtbaar deel van een raam achter lantaarnpaal en kap-hoek; verder verborgen. |
| OBS-MAP003-021 | ROOF_WINDOW | FULL | [1601, 696, 1731, 773] | kap rechts | LOW | Dakraam in het dakschild van de rechter kap. |
| OBS-MAP003-022 | WINDOW_OPENING | FULL | [250, 858, 344, 948] | begane grond, naast plaat 286 | LOW | Raam met gordijn in de entreemuur. |
| OBS-MAP003-023 | WINDOW_OPENING | FULL | [660, 863, 748, 950] | begane grond, naast plaat 284 | LOW | Raam; ruit afgeplakt/beplakt. |
| OBS-MAP003-024 | WINDOW_OPENING | FULL | [969, 891, 1075, 985] | begane grond, naast plaat 282 | LOW | Raam met zware kozijnstijl. |
| OBS-MAP003-025 | WINDOW_OPENING | FULL | [1692, 873, 1774, 957] | begane grond, naast plaat 278 | LOW | Raam in de entreemuur. |
| OBS-MAP003-026 | EXTERIOR_DOOR | PARTIAL | [442, 881, 504, 1070] | begane grond, entreenis | MEDIUM | Rode deur in de entreenis; deels in schaduw. |
| OBS-MAP003-027 | EXTERIOR_DOOR | PARTIAL | [1810, 893, 1866, 957] | begane grond, entreenis rechts | HIGH | Donkere deur rechts van het raam bij plaat 278; sterke schaduw. |
| OBS-MAP003-028 | UNKNOWN_OPENING | UNKNOWN_OPENING | [1149, 889, 1165, 913] | begane grond, achter hortensia | HIGH | Mogelijke opening naast 024 achter hortensia; niet vast te stellen. |

### MAP-004

| Observatie | Type | Zichtbaarheid | bbox px [x0,y0,x1,y1] | Positie | Onzekerheid | Toelichting |
|---|---|---|---|---|---|---|
| OBS-MAP004-001 | ROOF_WINDOW | FULL | [358, 319, 426, 361] | dakvlak links | LOW | Dakraam. |
| OBS-MAP004-002 | ROOF_WINDOW | FULL | [601, 317, 673, 362] | dakvlak midden | LOW | Dakraam. |
| OBS-MAP004-003 | ROOF_WINDOW | FULL | [1160, 325, 1222, 370] | dakvlak midden-rechts | LOW | Dakraam. |
| OBS-MAP004-004 | ROOF_WINDOW | FULL | [1462, 244, 1541, 292] | dakvlak rechter pand | LOW | Dakraam in het hogere dakvlak rechts. |
| OBS-MAP004-005 | WINDOW_OPENING | FULL | [127, 453, 389, 560] | bovenste gevelrij links | MEDIUM | Raam met gordijn en twee open vleugels; een opening (een mogelijk apart smal linker element is niet te onderscheiden). |
| OBS-MAP004-006 | WINDOW_OPENING | FULL | [535, 477, 692, 569] | bovenste gevelrij | LOW | Tweedelig kozijn; een opening. |
| OBS-MAP004-007 | WINDOW_OPENING | FULL | [729, 479, 791, 565] | bovenste gevelrij | LOW | Smal raam; gemetselde penant tussen 006 en 007. |
| OBS-MAP004-008 | WINDOW_OPENING | FULL | [995, 483, 1055, 571] | bovenste gevelrij | LOW | Smal raam met gordijn. |
| OBS-MAP004-009 | WINDOW_OPENING | FULL | [1092, 481, 1254, 579] | bovenste gevelrij | MEDIUM | Kozijn met open vleugel rechts; een opening. |
| OBS-MAP004-010 | WINDOW_OPENING | FULL | [1467, 406, 1653, 527] | bovenste gevelrij rechter pand | MEDIUM | Kozijn met open vleugel links; een opening. |
| OBS-MAP004-011 | WINDOW_OPENING | FULL | [1696, 414, 1772, 524] | bovenste gevelrij rechter pand | MEDIUM | Smal raam/open vleugel rechts naast 010; afzonderlijk door gemetselde penant (indruk). |
| OBS-MAP004-012 | WINDOW_OPENING | PARTIAL | [2017, 420, 2048, 509] | bovenste gevelrij rechter pand | HIGH | Smalle strook van een raam aan de beeldrand. |
| OBS-MAP004-013 | WINDOW_OPENING | FULL | [138, 658, 312, 799] | middelste rij | MEDIUM | Raam met open vleugel rechts en wit onderpaneel; een opening. |
| OBS-MAP004-014 | WINDOW_OPENING | PARTIAL | [471, 666, 584, 801] | middelste rij | MEDIUM | Raam met onderpaneel; rechterdeel achter het dakschild van de kap. |
| OBS-MAP004-015 | ROOF_WINDOW | FULL | [763, 694, 893, 763] | kap midden | LOW | Dakraam in het dakschild van de kap. |
| OBS-MAP004-016 | WINDOW_OPENING | FULL | [1096, 676, 1295, 814] | middelste rij | MEDIUM | Raam met open vleugel rechts en wit onderpaneel; een opening. |
| OBS-MAP004-017 | WINDOW_OPENING | FULL | [1510, 632, 1720, 797] | middelste rij rechter pand | MEDIUM | Groot raam met open vleugel links en onderpaneel; een opening. |
| OBS-MAP004-018 | WINDOW_OPENING | FULL | [471, 879, 565, 973] | begane grond, naast plaat 278 | LOW | Raam in de entreemuur. |
| OBS-MAP004-019 | WINDOW_OPENING | FULL | [887, 886, 981, 981] | begane grond, naast plaat 276 | LOW | Raam met gordijn in de entreemuur. |
| OBS-MAP004-020 | EXTERIOR_DOOR | PARTIAL | [655, 901, 722, 1126] | begane grond, entreenis | MEDIUM | Rode deur in de entreenis; trap daarachter. |
| OBS-MAP004-021 | WINDOW_OPENING | FULL | [1458, 925, 1674, 1050] | begane grond rechter pand | MEDIUM | Groot raam; beplanting voor de onderkant. |
| OBS-MAP004-022 | EXTERIOR_DOOR | PARTIAL | [46, 927, 84, 973] | begane grond, beeldrand links | HIGH | Rode deur met wit kozijn aan de linkerrand van het beeld (vergroting); grotendeels buiten beeld of achter lantaarnpaal/auto, behoort bij het buurpand links. |

## 3. Afbeeldingen

| Afb. | Bestand | Inhoud |
|---|---|---|
| A | [A_overview_MAP-003.jpg](A_overview_MAP-003.jpg) | Overzicht MAP-003 met genummerde observaties, platen apart (magenta) en legenda. |
| B | [B_overview_MAP-004.jpg](B_overview_MAP-004.jpg) | Overzicht MAP-004 met genummerde observaties, platen apart en legenda. |
| C1 | [C1_MAP-003_vs_MAP-004_upper_facade.jpg](C1_MAP-003_vs_MAP-004_upper_facade.jpg) | MAP-003 naast MAP-004, bovenste gevelrij (VR-027..031). |
| C2 | [C2_MAP-003_vs_MAP-004_middle_facade.jpg](C2_MAP-003_vs_MAP-004_middle_facade.jpg) | MAP-003 naast MAP-004, middelste rij en kap (VR-023..026). |
| C3 | [C3_MAP-003_vs_MAP-004_roof_kap_ground.jpg](C3_MAP-003_vs_MAP-004_roof_kap_ground.jpg) | MAP-003 naast MAP-004, dakramen en begane grond met platen (VR-020..022, VR-032..034). |
| D1 | [D1_MAP-002_vs_MAP-003_ground_wall_288.jpg](D1_MAP-002_vs_MAP-003_ground_wall_288.jpg) | MAP-002 (bevroren foto-2-annotaties, oranje) naast MAP-003: plaat 288 en raam (VR-001, VR-002). |
| D2 | [D2_MAP-002_vs_MAP-003_kap_and_middle_row.jpg](D2_MAP-002_vs_MAP-003_kap_and_middle_row.jpg) | MAP-002 naast MAP-003: kap met dakraam en middelste rij (VR-003..005). |
| D3 | [D3_MAP-002_vs_MAP-003_upper_row.jpg](D3_MAP-002_vs_MAP-003_upper_row.jpg) | MAP-002 naast MAP-003: bovenste gevelrij (VR-006..010). |
| D4 | [D4_MAP-002_vs_MAP-003_roof_dormer.jpg](D4_MAP-002_vs_MAP-003_roof_dormer.jpg) | MAP-002 naast MAP-003: dakkapel en dakramen (VR-011..013). |
| E | [E_plates_MAP-003_MAP-004.jpg](E_plates_MAP-003_MAP-004.jpg) | Plaatuitsneden (6x) met locatie en voorlopige lezing. |
| F | [F_reference_MAP-009_MAP-013_MAP-033.jpg](F_reference_MAP-009_MAP-013_MAP-033.jpg) | Referentiegebieden op MAP-009, MAP-013 en MAP-033 voor de overlapanalyse (geen observaties). |

Kaders: gele rechthoek = raam, cyaan = dakraam, groen = dakkapel, rood = buitendeur, wit = onbepaald, magenta = huisnummerplaat; doorgetrokken = FULL, gestippeld = PARTIAL/verborgen. In D markeert oranje de bevroren foto-2-kandidaten (FC/FI), `DUP?` een kandidaat op MAP-003 die mogelijk hetzelfde object is als een foto-2-kozijn.

## 4. Objectclassificaties (observaties, geen objecttotalen)

- **MAP-003:** DORMER_OPENING 1, EXTERIOR_DOOR 2, ROOF_WINDOW 6, UNKNOWN_OPENING 1, WINDOW_OPENING 18.
- **MAP-004:** EXTERIOR_DOOR 2, ROOF_WINDOW 5, WINDOW_OPENING 15.

Geldende telregels toegepast: een kozijn met meerdere vleugels/ruiten is een opening; een kozijnstijl of ruitverdeling scheidt niet; gemetseld penant tussen twee kozijnen scheidt wel (zoals foto 2 PCD-00004). Een raam-deurcombinatie in een doorlopend kozijn zou een opening zijn (REL-M3-001); op MAP-003/004 is er geen zekere combinatie gevonden. Dakramen en dakkapellen zijn fotoobservaties (ROOF_WINDOW/DORMER_OPENING), geen gewone EXTERIOR_FRAME-instances. Er zijn geen verborgen kozijnen afgeleid uit herhaling of symmetrie. De aantallen hierboven zijn aantallen observaties per foto; ze overlappen elkaar en met foto 2 en zijn nergens opgeteld.

## 5. Zichtbaarheidsclassificaties

### MAP-003

- **FULL** (21): 001, 002, 003, 004, 005, 007, 008, 009, 010, 011, 012, 013, 014, 017, 018, 019, 021, 022, 023, 024, 025
- **PARTIAL** (6): 006, 015, 016, 020, 026, 027
- **HEAVILY_OCCLUDED** (0): -
- **UNKNOWN_OPENING** (1): 028

### MAP-004

- **FULL** (18): 001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011, 013, 015, 016, 017, 018, 019, 021
- **PARTIAL** (4): 012, 014, 020, 022
- **HEAVILY_OCCLUDED** (0): -
- **UNKNOWN_OPENING** (0): -

Onzekerheid HIGH (handmatige beoordeling nodig): OBS-MAP003-009, OBS-MAP003-020, OBS-MAP003-027, OBS-MAP003-028, OBS-MAP004-012, OBS-MAP004-022.

## 6. Overlaprelaties (alleen kandidaten)

Klassen: SAME_FACADE_SECTION (dezelfde gevelpartij zichtbaar), POSSIBLY_SAME_PHYSICAL_FRAME (mogelijk hetzelfde fysieke kozijn), DIFFERENT_FRAMES (verschillende kozijnen), UNDETERMINABLE (niet te bepalen). Een gedeelde plaat bewijst niet dat de omliggende ramen dezelfde zijn. De verschuiving tussen foto's is diepteafhankelijk (parallax): dichterbij gelegen delen (begane-grondmuur) verschuiven meer dan de gevel en het dakvlak; daarom zijn paren alleen binnen dezelfde laag vergeleken. Geen relatie is bevestigd en niets is samengevoegd of opgeteld.

### SOC-001 MAP-002 vs MAP-003 (afb. D)

| Relatie | Links | Rechts | Klasse | Sterkte | Grondslag |
|---|---|---|---|---|---|
| VR-001 | MAP-002:plaat 288 + muur | MAP-003:P-288 + muur | SAME_FACADE_SECTION | HIGH | Plaat 288 met ernaast een raam (rechts van de plaat) en erboven de kap met dakraam; schoorstenen en dakkapel zichtbaar in dezelfde volgorde. |
| VR-002 | MAP-002:FC-M2-009 (FI-M2-012) | MAP-003:OBS-MAP003-022 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | In beide foto's het raam direct rechts van plaat 288 in dezelfde muur; verschuiving komt overeen met die van de plaat. Alleen aangrenzing, geen bewijs. |
| VR-003 | MAP-002:FC-M2-018 (roof) | MAP-003:OBS-MAP003-017 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Dakraam in het dakschild van dezelfde kap boven de entreemuur 288/286. |
| VR-004 | MAP-002:FC-M2-008 (FI-M2-011, PARTIAL) | MAP-003:OBS-MAP003-016 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam met onderpaneel direct links naast de kap; in beide foto's deels door de kap bedekt (PARTIAL). |
| VR-005 | MAP-002:FC-M2-007 (FI-M2-010) | MAP-003:OBS-MAP003-015 | POSSIBLY_SAME_PHYSICAL_FRAME | LOW | Volgend raam links in dezelfde rij; in MAP-003 aan de beeldrand afgesneden, dus de koppeling berust op de rijvolgorde en niet op een uniek kenmerk. |
| VR-006 | MAP-002:FC-M2-004 (FI-M2-005) | MAP-003:OBS-MAP003-007 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Tweedelig kozijn in de bovenste rij; smal raam met penant rechts ervan in beide foto's. |
| VR-007 | MAP-002:FC-M2-005 (FI-M2-006) | MAP-003:OBS-MAP003-008 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Smal raam rechts naast het tweedelige kozijn. |
| VR-008 | MAP-002:FC-M2-006-A (FI-M2-007) | MAP-003:OBS-MAP003-009 | UNDETERMINABLE | LOW | Het smalle linker element is in foto 2 als apart kozijn besloten (PCD); in MAP-003 is niet te zien of dit een apart kozijn of een vleugel is. |
| VR-009 | MAP-002:FC-M2-006-BC (FI-M2-014) | MAP-003:OBS-MAP003-010 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Hoofdkozijn met gordijn en twee open vleugels; zelfde open vleugels en gordijn in beide foto's. |
| VR-010 | MAP-002:FC-M2-003 (FI-M2-004) | MAP-003:OBS-MAP003-006 | UNDETERMINABLE | LOW | MAP-003 toont slechts de rechterhelft van het kozijn aan de beeldrand; open vleugel rechts komt overeen, maar het kozijn is niet volledig vergelijkbaar. |
| VR-011 | MAP-002:FC-M2-019 (dormer) | MAP-003:OBS-MAP003-001 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Dakkapel met drie-ruits kozijn links naast de schoorstenen; dormer-opening, geen gewone kozijninstance. |
| VR-012 | MAP-002:FC-M2-015 | MAP-003:OBS-MAP003-002 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Dakraam links van de rechter schoorsteenparen; dakvlak-verschuiving komt overeen. |
| VR-013 | MAP-002:FC-M2-016 | MAP-003:OBS-MAP003-003 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Tweede dakraam rechts van de schoorstenen. |

### SOC-002 MAP-003 vs MAP-004, plus MAP-009 (afb. C, F)

| Relatie | Links | Rechts | Klasse | Sterkte | Grondslag |
|---|---|---|---|---|---|
| VR-020 | MAP-003:P-280/P-278/P-276 | MAP-004:P-280/P-278/P-276 | SAME_FACADE_SECTION | HIGH | Drie platen en de bijbehorende entreemuren in beide foto's (MAP-003 onderrand rechts; MAP-004 links/midden). Plaat bewijst alleen de muur. |
| VR-021 | MAP-003:OBS-MAP003-025 | MAP-004:OBS-MAP004-018 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Raam direct bij plaat 278 in dezelfde muur. |
| VR-022 | MAP-003:OBS-MAP003-027 | MAP-004:OBS-MAP004-020 | POSSIBLY_SAME_PHYSICAL_FRAME | LOW | Deur in de entreenis tussen de platen 278 en 276; in MAP-003 zeer donker en bijna aan de rand. |
| VR-023 | MAP-003:OBS-MAP003-021 | MAP-004:OBS-MAP004-015 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Dakraam in het dakschild van de kap boven plaat 280/278 (zelfde kap). |
| VR-024 | MAP-003:OBS-MAP003-018 | MAP-004:OBS-MAP004-013 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam met open vleugel rechts en onderpaneel links van de kap. |
| VR-025 | MAP-003:OBS-MAP003-019 | MAP-004:OBS-MAP004-014 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam met onderpaneel direct links van de kap; in MAP-004 deels door de kap bedekt. |
| VR-026 | MAP-003:OBS-MAP003-020 | MAP-004:OBS-MAP004-016 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam rechts van de kap met open vleugel en onderpaneel; in MAP-003 grotendeels verborgen. |
| VR-027 | MAP-003:OBS-MAP003-011 | MAP-004:OBS-MAP004-006 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Tweedelig kozijn bovenste rij boven de kap. |
| VR-028 | MAP-003:OBS-MAP003-012 | MAP-004:OBS-MAP004-007 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Smal raam rechts naast het tweedelige kozijn. |
| VR-029 | MAP-003:OBS-MAP003-013 | MAP-004:OBS-MAP004-008 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Smal raam met gordijn in de bovenste rij rechts. |
| VR-030 | MAP-003:OBS-MAP003-014 | MAP-004:OBS-MAP004-009 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Kozijn met open vleugel rechts. |
| VR-031 | MAP-003:OBS-MAP003-009+010 | MAP-004:OBS-MAP004-005 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Zelfde raam met gordijn en twee open vleugels; in MAP-003 twee observaties (smal links + hoofdkozijn), in MAP-004 een observatie: telverschil is een leesverschil, geen extra raam. |
| VR-032 | MAP-003:OBS-MAP003-003 | MAP-004:OBS-MAP004-001 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Dakraam in het hoofddakvlak. |
| VR-033 | MAP-003:OBS-MAP003-004 | MAP-004:OBS-MAP004-002 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Dakraam in het hoofddakvlak. |
| VR-034 | MAP-003:OBS-MAP003-005 | MAP-004:OBS-MAP004-003 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Dakraam in het hoofddakvlak rechts. |
| VR-035 | MAP-003:rechterrand (pand rechts) | MAP-004:OBS-MAP004-004/010/011/012/017/021 | UNDETERMINABLE | LOW | MAP-003 toont aan de rechterrand slechts een smalle strook van het pand rechts; de grote ramen van dat pand in MAP-004 zijn in MAP-003 niet te vergelijken. |
| VR-036 | MAP-003:OBS-MAP003-024 (raam 282) | MAP-004: buiten beeld | DIFFERENT_FRAMES | HIGH | Het raam bij plaat 282 ligt links van het zichtbare deel van MAP-004; geen overlap. |
| VR-037 | MAP-003:OBS-MAP003-022 / 023 / 026 (platen 288..284) | MAP-004: buiten beeld | DIFFERENT_FRAMES | HIGH | Objecten links van plaat 282 komen in MAP-004 niet voor. |
| VR-040 | MAP-004:OBS-MAP004-015 / MAP-003:OBS-MAP003-021 | MAP-009:REF-MAP009-001 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Dakraam in het dakschild van dezelfde kap, schuin vanaf links gezien. |
| VR-041 | MAP-003:OBS-MAP003-025 / MAP-004:OBS-MAP004-018 | MAP-009:REF-MAP009-003 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Raam direct rechts van plaat 278 (plaat zichtbaar in alle drie). |
| VR-042 | MAP-004:OBS-MAP004-019 | MAP-009:REF-MAP009-004 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam naast de plaat rechts van 278 (276), plaat in MAP-009 niet volledig leesbaar. |
| VR-043 | MAP-003:OBS-MAP003-019 / MAP-004:OBS-MAP004-014 | MAP-009:REF-MAP009-002 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam met onderpaneel links van de kap; flessen op de dorpel zijn in MAP-003 en MAP-009 zichtbaar. |
| VR-044 | MAP-003:OBS-MAP003-020 / MAP-004:OBS-MAP004-016 | MAP-009:REF-MAP009-005 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam met open vleugel rechts van de kap. |
| VR-045 | MAP-003:OBS-MAP003-011/012 / MAP-004:OBS-MAP004-006/007 | MAP-009:REF-MAP009-006 | POSSIBLY_SAME_PHYSICAL_FRAME | LOW | Bovenste rij: kozijn met smal raam; MAP-009 is sterk verkort, dus alleen overeenkomstige indeling. |

### SOC-003 MAP-003 vs MAP-013 (afb. F)

| Relatie | Links | Rechts | Klasse | Sterkte | Grondslag |
|---|---|---|---|---|---|
| VR-050 | MAP-003:OBS-MAP003-022 | MAP-013:REF-MAP013-001 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Raam tussen de platen 288 en 286 (beide platen in beide foto's leesbaar). |
| VR-051 | MAP-003:OBS-MAP003-023 | MAP-013:REF-MAP013-002 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Raam direct rechts van plaat 284. |
| VR-052 | MAP-003:OBS-MAP003-017 | MAP-013:REF-MAP013-003 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Dakraam van de kap boven de entreemuren 288/286. |
| VR-053 | MAP-003:OBS-MAP003-009+010 | MAP-013:REF-MAP013-004 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Raam met open vleugels in de bovenste rij. |
| VR-054 | MAP-003:OBS-MAP003-007+008 | MAP-013:REF-MAP013-005 | POSSIBLY_SAME_PHYSICAL_FRAME | MEDIUM | Tweedelig kozijn met smal raam in de bovenste rij. |

### SOC-008 MAP-004 vs MAP-033 (afb. F)

| Relatie | Links | Rechts | Klasse | Sterkte | Grondslag |
|---|---|---|---|---|---|
| VR-060 | MAP-004:OBS-MAP004-019 | MAP-033:REF-MAP033-001 | POSSIBLY_SAME_PHYSICAL_FRAME | HIGH | Gordijnraam direct rechts van plaat 276 in dezelfde muur; MAP-033 is een detailfoto met plaat en raam in een beeld. |

Samenvatting relaties (aantal kandidaat-relaties per klasse): DIFFERENT_FRAMES 2, POSSIBLY_SAME_PHYSICAL_FRAME 36, SAME_FACADE_SECTION 2, UNDETERMINABLE 3.

Bevestigd: SOC-003 (MAP-013) en SOC-008 (MAP-033) zijn bronnen waarin plaat en raam in een beeld staan; ze maken de koppeling plaatmuur-raam zichtbaar maar bewijzen die niet voor andere ramen. SOC-002: MAP-009 is sterk verkort en bevat alleen plaat 280 volledig leesbaar; de koppeling op MAP-009 blijft kandidaat.

## 7. Huisnummerplaten en bewijspositie

| Plaat | Foto | Lezing | bbox px | Leesbaarheid | BAG-pand van de plaatmuur | Pandvolgorde |
|---|---|---|---|---|---|---|
| PL-MAP003-288 | MAP-003 | 288 | [16, 881, 49, 905] | LEGIBLE_AT_ENLARGEMENT | 0363100012121455 | 13 |
| PL-MAP003-286 | MAP-003 | 286 | [352, 881, 383, 907] | LEGIBLE_AT_ENLARGEMENT | 0363100012121455 | 13 |
| PL-MAP003-284 | MAP-003 | 284 | [621, 885, 652, 910] | LEGIBLE_AT_ENLARGEMENT | 0363100012143647 | 12 |
| PL-MAP003-282 | MAP-003 | 282 | [932, 887, 963, 912] | LEGIBLE_AT_ENLARGEMENT | 0363100012143647 | 12 |
| PL-MAP003-280 | MAP-003 | 280 | [1488, 893, 1521, 915] | LEGIBLE_AT_ENLARGEMENT | 0363100012091756 | 11 |
| PL-MAP003-278 | MAP-003 | 278 | [1777, 895, 1809, 919] | LEGIBLE_AT_ENLARGEMENT | 0363100012091756 | 11 |
| PL-MAP003-276 | MAP-003 | 276 | [2013, 897, 2048, 920] | LEGIBLE_AT_ENLARGEMENT | 0363100012144766 | 10 |
| PL-MAP004-280 | MAP-004 | 280 | [243, 897, 273, 924] | LEGIBLE_AT_ENLARGEMENT | 0363100012091756 | 11 |
| PL-MAP004-278 | MAP-004 | 278 | [570, 905, 603, 930] | LEGIBLE_AT_ENLARGEMENT | 0363100012091756 | 11 |
| PL-MAP004-276 | MAP-004 | 276 | [850, 909, 882, 934] | LEGIBLE_AT_ENLARGEMENT | 0363100012144766 | 10 |
| PL-MAP004-274 | MAP-004 | 274 | [1182, 915, 1213, 940] | LEGIBLE_AT_ENLARGEMENT | 0363100012144766 | 10 |

Alle elf plaatopnamen zijn bij 6x vergroting duidelijk leesbaar (afb. E); geen plaat is UNCONFIRMED door onleesbaarheid. De lezing blijft voorlopig tot een mens APP-002/APP-003 beantwoordt. De pandkoppeling gaat via bestaand BAG-bewijs (`maldenhof_address_pand_evidence_v1.json`) en geldt alleen voor de muur met de plaat (PAND_PROVEN_BY_VISIBLE_PLATE_ONLY).

## 8. Ontbrekend bewijs voor pandtoewijzing

Geen enkele observatie is aan een pand gekoppeld (alle 50 staan op `bag_pand_id: null`, `NOT_PROVEN`). Per groep:

- **Begane grond naast een plaat** (MAP-003: 022, 023, 024, 025; MAP-004: 018, 019): de plaat staat naast het raam, maar bewijst het raam niet (APP-001). Ontbrekend: een detailfoto waarop plaat en raam samen in een beeld staan (aanwezig voor 022/023 via MAP-013 en voor 019 via MAP-033, nog niet door een mens bevestigd) of een expliciete mensbevestiging.
- **Entreenissen/deuren** (MAP-003: 026, 027; MAP-004: 020, 022): geen plaat op de deur zelf; ontbrekend is een bevestiging welke woning de deur bedient.
- **Bovenste en middelste gevelrij, dakramen en dakkapel** (alle overige observaties): op deze lagen staat geen plaat; pandgrenzen zijn niet leesbaar uit de foto. Ontbrekend: bewijs van de pandgrens (bijv. regenpijp/penant of BAG-footprint met kozijnpositie) of mensbevestiging. De positie in het beeld is geen bewijs.
- **Pand 10-13 (platen 274-288)** hebben op MAP-003/MAP-004 elk minstens een leesbare plaat; panden 1, 5 en 15 hebben geen plaatfoto (zie het goedkeuringsdocument).
- **Partijen aan de beeldrand** (MAP-003: 006, 015, 020; MAP-004: 012, 022): te weinig zichtbaar om te beoordelen.

## 9. Concrete menselijke vragen

| ID | Gekoppeld besluit | Onderwerp | Vraag | Aanbevolen antwoord |
|---|---|---|---|---|
| HQ-APP-001 | APP-001 | Plaatregel | Akkoord dat een leesbare plaat alleen de muur met die plaat aan een pand koppelt? | JA |
| HQ-APP-002 | APP-002 | Plaatlezing MAP-003 | Zijn de zeven platen 288, 286, 284, 282, 280, 278, 276 op de vergrotingen (afbeelding E) correct gelezen? | JA |
| HQ-APP-003 | APP-003 | Plaatlezing MAP-004 | Zijn de vier platen 280, 278, 276, 274 correct gelezen? | JA |
| HQ-APP-011 | APP-011 | Overlap MAP-002/MAP-003 | Zijn de ramen/dakramen/dakkapel uit afbeelding D per paar SAME / DIFFERENT / UNDECIDABLE? Aanbevolen: SAME voor VR-002, VR-003, VR-004, VR-006, VR-009; UNDECIDABLE voor VR-005, VR-008, VR-010. | per paar |
| HQ-APP-012 | APP-012 | Overlap MAP-003/MAP-004/MAP-009 | Zijn de paren uit afbeelding C per paar SAME / DIFFERENT / UNDECIDABLE? Aanbevolen: SAME voor VR-021, VR-023; MEDIUM-paren na eigen controle; UNDECIDABLE voor VR-035. | per paar |
| HQ-APP-013 | APP-013 | Overlap MAP-003/MAP-013 | Zijn REF-MAP013-001 en -002 dezelfde ramen als OBS-MAP003-022 en -023 (SAME)? | SAME (aanbevolen) |
| HQ-APP-031 | APP-031 | Overlapzone met bevroren foto 2 | Mogen de MAP-003-kandidaten rond plaat 288 als aparte kandidaten met overlapmarkering blijven staan, zonder optelling bij foto 2? | JA |
| HQ-APP-034 | APP-034 | Geschiktheid MAP-003 | Is MAP-003 na deze visuele controle geschikt als annotatiebron (READY_FOR_REVIEW), met de open punten OBS-MAP003-009/-020/-027/-028? | JA |
| HQ-APP-035 | APP-035 | Geschiktheid MAP-004 | Is MAP-004 geschikt als annotatiebron, met de open punten OBS-MAP004-005/-012/-022? | JA |
| HQ-VR-001 | (extra, tijdelijk ID) | Smal linker element (MAP-003 OBS-009) | Is het smalle element links van het hoofdkozijn een apart kozijn (zoals foto 2 FC-M2-006-A) of een vleugel van OBS-010? | UNDECIDABLE tot betere foto |
| HQ-VR-002 | (extra, tijdelijk ID) | Telconventie penant tussen kozijnen | Bevestigen dat het metselwerk tussen OBS-MAP003-007 en -008 (en 011/012, 013/014) de openingen scheidt (afzonderlijke openingen), conform foto 2 PCD-00004? | JA |
| HQ-VR-003 | (extra, tijdelijk ID) | Deuren in de entreenissen | Zijn OBS-MAP003-026/027 en OBS-MAP004-020/022 buitendeuren die tot de te tellen elementen behoren (ja/nee), of alleen entree-context? | later beslissen |
| HQ-VR-004 | (extra, tijdelijk ID) | Pandkoppeling per ruimte | Welke aanvullende bewijsfoto's (plaat op dezelfde muur als het raam) zijn gewenst voor pand 10-13 voordat ramen aan een pand worden gekoppeld? | extra detailfoto's per plaatmuur |

De extra vragen HQ-VR-001..004 hebben een tijdelijk ID en zijn geen APP-besluiten; ze zijn niet in het goedkeuringsdocument opgenomen.

## 10. Samenvattend besluitoverzicht

| Onderdeel | Stand |
|---|---|
| Observaties MAP-003 / MAP-004 | 28 / 22 voorlopig, geen instances |
| Overlaprelaties | 43 kandidaat-relaties, geen bevestigd |
| Platen leesbaar | 11 van 11 bij vergroting (voorlopig) |
| Pandkoppelingen toegevoegd | 0 |
| Foto 2 | bevroren, ongewijzigd |
| APP-besluiten | 48 OPEN |
| Unieke totalen, maten, kosten, repeat | geen |

Het pakket stopt na de PR; een mens beslist via de besluiten in sectie 9.
