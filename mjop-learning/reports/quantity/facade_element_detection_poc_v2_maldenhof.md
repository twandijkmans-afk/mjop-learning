# Facade element detection PoC v2 — Maldenhof 240-296 (BPRJ-00001)

Status: **analyse / proof-of-concept**. Geen wijziging aan stores, schema's of canonical data; geen nieuwe approvals.
Alle hoeveelheden zijn `ESTIMATED_FROM_PANORAMA` (bounding-box-aanzicht), geen inspectie en geen kozijn-/schilder-m².

- Data: `facade_element_detection_poc_v2_maldenhof.json` (alle cijfers hieronder), ruwe run in `facade_poc_v2_run/`
  (`coverage.json`, `detections_v2.json`, `aggregate_v2.json`), visuele review in
  `facade_detection_review_v2_maldenhof.json` + `facade_poc_v2_review_images/`.
- Scripts: `scripts/facade_coverage_poc_v2.py` (dekking, detectie, aggregatie) en `scripts/facade_poc_v2_report.py`
  (rapportdata).
- Model: Claude Opus 5.5 (structured output). Tokens voor alle v2-runs samen, inclusief twee afgebroken runs
  (zie §3): 681.883 input en 178.531 output, ongeveer 4–5× de v1-run.

## Antwoorden A–G

| Vraag | Antwoord (gemeten) |
|---|---|
| **A.** Hoeveel van de 29 woningen hebben voldoende dekking? | **0 van 29** volgens de norm "≥ 80% van voor- én achtergevel bevestigd zichtbaar". De terugliggende **hoofdvoorgevel** (grootste voorwand per pand, ~17 m²) is wél bij **10 van 15 panden (20 van 29 adressen)** voor ≥ 70% bevestigd zichtbaar. |
| **B.** Hoeveel unieke buitengevel-m² is werkelijk zichtbaar? | **639,0 van 1563,4 m² (41%)** bevestigd zichtbaar: vrij volgens de 3D-zichtlijn, niet groen, én door het model niet als afgedekt gemeld. Op alleen 3D-zichtlijn + groenfilter zou het 1264,8 m² (81%) zijn; het verschil zit vooral in schuttingen en tuinen (achterzijde, benedenverdieping) en begroeiing. |
| **C.** Hoe goed is de detectie op goed zichtbare gevels? | Visuele review (door Claude, **niet door een mens**) van 14 hoofdvoorgevels van 14 panden: 42 zichtbare objecten, **39 juist, 3 gemist, 8 onterecht** (precision 0,83, recall 0,93). De onterechte zijn vooral randstroken en typeverwarring, geen gemiste kozijnen. **Detectie is niet het hoofdprobleem.** |
| **D.** Openingen per woningtype? | Middenpand (2 woningen, 13 panden), terugliggende hoofdvoorgevel: mediaan **5,18 m²** openings-bbox en 2 kozijnen. Bij goede dekking (≥ 70%) ligt dat tussen 4,6 en 6,5 m². Hele voorzijde (incl. blokken en zijwangen, gemiddeld ~50% gedekt): mediaan 11,39 m² (min. 8,82, max. 17,78). |
| **E.** Waarom wijkt het af van 756,8 m²? | 756,8 is geen gemeten openingsoppervlak: het is één ongedefinieerde regel, identiek overgenomen van 2023 naar 2026, "incl. draaiende delen", in rapporten die zeggen dat er niet gemeten en niet gerekend is (§5). Daarnaast is onze dekking 41%. |
| **F.** Is 756,8 een geldige benchmark? | **Nee, NOT_COMPARABLE** (§6). |
| **G.** Welke foto's moet een bewoner leveren? | Per pand vooral de **benedenverdieping voor en achter** (achter staan schuttingen en tuinen), plus de zijwangen van de trappenhuis-/bergingsblokken. Pand 240 heeft volledig bewonersfoto's nodig (alles achter bomen). Zie §7. |

**Beslissing: ITERATE_COVERAGE** (§9).

## 1. Metrics: eerlijke namen en noemers (ook v1 gecorrigeerd)

`frame_area_m2` bestaat niet meer. Het was de som van bounding boxes van ramen, deuren, garagedeuren en dakkapellen.
Een kozijn- of schilder-m² rapporteren we pas als daar een expliciete rekenregel voor is. Een wand waarvoor het model
`image_usable=false` gaf, telt niet mee in de noemer.

| | v1 (hernoemd) | v2 |
|---|---|---|
| wall_m2_attempted | 836,26 | 1539,71 |
| wall_m2_model_usable | 758,45 | 1281,28 |
| wall_m2_model_unusable | 77,81 | 258,43 |
| wall_m2_with_detected_elements | 611,31 | 996,02 |
| unieke bevestigd zichtbare m² (per gevelpunt) | — | 638,96 |
| window_opening_area_m2 | 120,28 (72 ramen) | 186,99 (149 ramen) |
| door_opening_area_m2 | 14,53 (11) | 33,07 (25) |
| garage_door_area_m2 | 2,19 (1) | 0,00 (0)* |
| dormer_bbox_area_m2 | 3,89 (3) | 2,70 (5) |
| **total_opening_bbox_area_m2** | **140,89** | **222,76** |
| facade_panel_area_m2 | 25,58 | 85,81 |
| window_sill_m1 (som raambreedtes) | 91,98 | 175,71 |

\* v2 bevat geen `garage_door`-label; niet nagegaan of het v1-element nu als `door` is gelabeld.

Openingen gedeeld door model-bruikbare wand: v1 18,6%, v2 voorzijde 17,9% (166,94 / 933,9 m²), v2 achterzijde
22,7% (54,59 / 240,6 m²). Gedeeld door de bevestigd zichtbare m² is het aandeel hoger (voorzijde 36%). Dat is een
bovengrens, want deels verborgen elementen tellen in de teller wel mee.

## 2. Dekking per adres/woning

**Woningindeling.** Per pand horen 2 adressen bij één voorgevel: BAG-VBO's van 57 m² plus 74 of 101 m², drie lagen,
en een trappenhuis-/bergingsblok aan de voorzijde (MJOP: "Voorgevel - trappenhuizen"). Dat past bij een
beneden-/bovenwoning, maar dat is **niet bevestigd**. Welk huisnummer welke verdieping heeft, is uit BAG niet af te
leiden. Het idee uit v1 ("per pand is maar één woningbreedte verwerkt") klopt dus niet: de voorgevel is gedeeld.
Daarom wordt dekking per pand gemeten en per adres herhaald (`address_records`, `dwelling_zone_assignment:
UNRESOLVED`).

**Methode.** Elke buitenwand (LoD2.2, ≥ 0,5 m², zonder tussenmuren) wordt bemonsterd op een raster van 0,20 m:
39.022 gevelpunten op 206 wanden. Per punt en per panorama worden getoetst: afstand 3–30 m, kijkhoek ≤ 60°, de
3D-zichtlijn, groen (ExG) en, na detectie, de door het model gemelde afgedekte zones. Een punt telt één keer, hoeveel
panorama's het ook zien. Per adres legt het JSON vast: de verwachte gevelzijden, de bevestigd zichtbare m², de
gebruikte panorama_ids, afgedekte m² per oorzaak, en ontbrekende m² per zijde en laag.

| Zijde | Wand m² | Bevestigd zichtbaar | Model: afgedekt/onbruikbaar | 3D-zichtlijn | Groen (ExG) |
|---|---|---|---|---|---|
| Voorgevel, hoofdvlakken (FRONT) | 543,3 | 321,0 (59%) | 188,5 | 21,9 | 11,8 |
| Voorzijde, zijwangen blokken/terugsprongen | 499,5 | 142,0 (28%) | 150,3 | 187,1 | 20,0 |
| Achterzijde incl. zijwangen | 399,8 | 105,9 (26%) | 237,8 | 34,8 | 21,3 |
| Kopgevels (2 eindpanden) | 120,8 | 69,9 (58%) | 49,3 | 0 | 1,6 |
| **Totaal** | **1563,4** | **639,0 (41%)** | 625,9 | 243,7 | 54,8 |

Hoofdvoorgevelwand per pand, bevestigd zichtbaar:
- ≥ 70% bij 10 panden;
- 68% bij 270/272 (boom);
- 48% bij 294/296;
- 44% bij 274/276 (wand in LoD2.2 anders opgeknipt);
- 21% bij 242/244 (struiken);
- 0% bij 240 (geheel achter bomen).

Achterzijden: 0–50% per pand; benedenverdiepingen achter liggen vrijwel altijd achter schuttingen.

## 3. Multi-panorama en ontdubbeling

- 401 panorama's gevonden (2016–2025), waarvan 25 uitgesloten: de opnames van 2024/2025 hebben in de API hoogte 0,0,
  wat een camera 42 m onder NAP zou geven. v1 was daar niet op gecontroleerd.
- Greedy per wand: het panorama dat de meeste nog niet zichtbare punten toevoegt, tot 4 per wand. Verdeling:
  12 wanden 0, 126 wanden 1, 39 wanden 2, 18 wanden 3, 11 wanden 4 panorama's.
- **Winst van multi-panorama** (vóór modelcontrole): 1176,3 → 1264,9 m², **+88,5 m²** (+7,5%). Beperkt, omdat de
  jaren vanaf ongeveer dezelfde fietspaden zijn opgenomen: hetzelfde standpunt levert dezelfde verborgen zones.
- **Ontdubbeling** gebeurt in wandcoördinaten (meters). Twee detecties zijn hetzelfde element bij IoU > 0,3, of bij
  een middelpuntafstand < 0,6 m en vergelijkbare breedte. Het element uit het panorama met de beste kijkkwaliteit
  blijft. Zo zijn 56 dubbel geziene elementen samengevoegd.
- De verschuiving tussen panorama's op dezelfde wand is mediaan **0,24 m** (p90 0,56 m). Dat is de
  registratie-onnauwkeurigheid van positie en hoogte uit de API. Hoeveelheden uit verschillende panorama's worden
  nooit opgeteld.

**Fout gevonden en gecorrigeerd tijdens de run.** In het evidence-package ontbreken de vrijstaande
bergings-/trappenhuisblokken vóór de gevels (BAG-panden zonder verblijfsobject). Daardoor zag de 3D-zichtlijntest
niet dat die blokken bij schuine opnames de benedenverdieping van het búrenpand afdekken. Het model markeerde dan het
raam in het blok als raam van de achterliggende gevel; de huisnummerbordjes 262, 278 en 286 stonden op het verkeerde
pand. De correctie: 210 omliggende BAG-panden (3D BAG) zijn als **occluder** toegevoegd, alleen voor de zichtlijn en
nooit als gevel van het project (index in `facade_poc_v2_run/bag_panden_bbox.json`). Daarna kiest de selectie
frontale beelden (kijkhoek-cosinus 0,92–1,0) en verdween de fout in de review. Twee eerdere detectieruns zijn daarom
weggegooid; hun tokens staan in het totaal.

## 4. Herhaling als interne controle (alleen diagnostiek, geen imputatie)

Visueel is de rij één gespiegeld type. Afwijkend zijn eindpand 240 (1 woning) en eindpand 294/296. Voor de 13
middenpanden, op de terugliggende hoofdvoorgevelwand (17–19 m²):

| Pand | Adressen | Openings-bbox m² | Ramen | Bevestigd zichtbaar | Diagnose |
|---|---|---|---|---|---|
| 0344 | 262/264 | 4,63 | 2 | 81% | |
| 8022 | 246/248 | 5,18 | 2 | 80% | |
| 1756 | 278/280 | 6,51 | 2 | 84% | + randstroken (FP) |
| 1974 | 258/260 | 5,55 | 3 | 82% | 1 randstrook |
| 7492 | 266/268 | 5,34 | 2 | 82% | |
| 1455 | 286/288 | 4,68 | 2 | 71% | |
| 4188 | 290/292 | 5,21 | 2 | 75% | |
| 0664 | 250/252 | 4,99 | 3 | 74% | kozijn in tweeën gesplitst |
| 1419 | 254/256 | 5,47 | 2 | 78% | |
| 3647 | 282/284 | 5,46 | 2 | 89% | |
| 1880 | 270/272 | **2,93** | 3 | 68% | uitschieter: boom voor 1e verdieping (opname op 27 m) |
| 2659 | 242/244 | **3,33** | 2 | 21% | dekking: struiken |
| 4766 | 274/276 | **2,38** | 3 | 44% | uitschieter: andere wand gekozen (LoD2.2-fragmentatie) |

Bij goede dekking liggen de 10 panden tussen **4,6 en 6,5 m²** (mediaan ~5,2). Alle drie de uitschieters vallen
samen met lage dekking of een geometrieprobleem, **niet** met een detectiefout. Hele voorzijde per middenpand:
openingen min. 8,82, mediaan 11,39, max. 17,78 m²; ramen min. 4, mediaan 8, max. 11. Die spreiding volgt de dekking
van de zijwangen en blokken (28%).

## 5. Ontleding van de 756,8 m² (DOC-005 = MJOP 2026, DOC-006 = MJOP 2023)

Alle records met bron staan in `mjop_decomposition.records`.

| Document | Element / handeling | Locatie | Hoeveelheid | Pagina | Bron |
|---|---|---|---|---|---|
| DOC-005 | 3120 Kozijn buiten hout (elementenoverzicht) | Alle gevels | 756,80 m2 | 6 | extracted EL-007 |
| DOC-005 | Reinigen en controleren ventilatierooster | Alle gevels | **756,80 st** | 11 | extracted ACT-004 |
| DOC-005 | Vervangen kozijn hout (2070, € 0 in horizon) | Alle gevels | 756,80 m2 | 11 | alleen PDF-tekst |
| DOC-005 | 4631 Buitenschilderwerk kozijn hout dekkend | Alle gevels | 756,80 m2 | 7 | extracted EL-022 |
| DOC-005 | Groot schilderwerk kozijn (en draaiende delen) hout dekkend (uitgevoerd 2026), 2033 en 2040, € 32.823 | Alle gevels | 756,80 m2 | 12 | ACT-015/016 |
| DOC-006 | 3120 Kozijn buiten hout | Alle gevels | 756,80 m2 | 6 | extracted EL-007 |
| DOC-006 | Vervangen kozijn hout (2070) | Alle gevels | 756,80 m2 | 14 | alleen PDF-tekst |
| DOC-006 | 4631 … Aanbrengen vervolgsysteem (Barsten), 2025 | Alle gevels | 1,00 pst (€ 36.247) | 15 (gebrek p.11) | ACT-014 |
| DOC-006 | Groot schilderwerk kozijn (en draaiende delen) hout dekkend (conform PO cyclus), 2032, € 40.237 | Alle gevels | 756,80 m2 | 15 | ACT-015 |

Bijbehorende regels, in beide documenten gelijk:
- 3120 Raamdorpel gres/ijzerklinker 281,20 m1;
- 4112/4621 Gevelbekleding hout, "Voorgevel - gevelbekleding", 332,00 m2;
- 2110/4111 metselwerk "Alle gevels" 1631,90 m2.

Materiaal: "hout" staat in de elementnaam, het veld `material` is niet ingevuld.

- **Eén regel of een som?** Eén regel (element 3120), hergebruikt bij schilderwerk, vervanging en (DOC-005)
  ventilatieroosters. De bron toont geen deelregels.
- **Raam-/kozijnoppervlak?** Niet uit de bron af te leiden; er is geen meetinstructie.
- **Schilderoppervlak?** De hoeveelheid dient als schilder-m², en de omschrijving zegt "(en draaiende delen)". Hoe die
  m² is bepaald staat er niet.
- **Deuren inbegrepen?** Onbekend. Er is geen aparte deurregel in beide MJOP's.
- **Panelen/borstweringen?** Onbekend. Houten gevelbekleding staat apart (332 m²).
- **Gevelzijden?** "Alle gevels", zonder uitsplitsing.
- **DOC-005 = DOC-006?** De hoeveelheden zijn identiek (ook 1631,90 / 281,20 / 332,00): overgenomen, niet opnieuw
  bepaald. Alleen de bedragen verschillen.
- **Aanwijzingen voor een rekenconventie:**
  - beide rapporten zeggen op p.4 letterlijk: "er geen metingen worden verricht, er geen berekeningen worden
    uitgevoerd";
  - "756,80 **st** ventilatierooster" is hetzelfde getal met een andere eenheid, dus een hergebruikte hoeveelheid en
    geen telling;
  - 756,8 m² is 46% van de 1631,9 m² metselwerk en 43% van de 3D BAG-buitenwand (1747,3 m²). Als aanzicht van
    openingen is dat niet plausibel: wij meten ~18–23% op model-bruikbare wand, en de visuele review bevestigt ~30%
    op de terugliggende hoofdwand. Als ontwikkeld schilderoppervlak inclusief draaiende delen is het denkbaar. **Dat
    is een hypothese, geen bronfeit.**

## 6. Semantische benchmarks

| Onze grootheid | Waarde | MJOP | Klasse | Waarom |
|---|---|---|---|---|
| total_opening_bbox_area_m2 (zichtbaar) | 222,76 | Kozijn / schilderwerk kozijn 756,80 m2 | **NOT_COMPARABLE** | MJOP-grootheid ongedefinieerd, niet gemeten, incl. draaiende delen, overgenomen 2023→2026 |
| window_sill_m1 | 175,71 | Raamdorpel gres/klinker 281,20 m1 | PARTIAL_COMPARABLE | Zelfde soort grootheid, maar niet elk raam heeft een klinkerdorpel, dekking 41%, MJOP niet gemeten |
| facade_panel_area_m2 voorzijde | 76,06 | Gevelbekleding hout voorgevel 332,00 m2 | PARTIAL_COMPARABLE | Zelfde element en zijde; rechthoeken onderschatten doorlopende vlakken; MJOP niet gemeten |
| exterior wall m² (LoD2.2) | 1563,43 | Metselwerk "Alle gevels" 1631,90 m2 | PARTIAL_COMPARABLE | Beide bruto-achtig; het MJOP zegt niet of openingen zijn afgetrokken |

Er is geen DIRECT_COMPARABLE benchmark, dus er is geen foutpercentage berekend. Voor PARTIAL tonen we beide waarden
zonder accuracy-claim.

## 7. Detectiekwaliteit (steekproef) en USER_ASSISTED

De reviewer is Claude (AI) die de gevelbeelden bekijkt. Dit is **geen menselijke controle** en moet door een mens
bevestigd worden; de beelden staan in `facade_poc_v2_review_images/`.

- Objectdefinitie: kozijneenheid inclusief paneel binnen hetzelfde kozijn, buitendeur, en donkere gevelbekleding.
- Wat achter een blok of struik zit, telt niet als "zichtbaar".

| Ronde | Beelden/panden | Zichtbaar | Juist | Onterecht | Gemist (begroeiing / model) |
|---|---|---|---|---|---|
| A: selectie vóór occluder-fix | 12/12 | 33 | 32 | 12 (5 buurblok, 6 rand, 1 type) | 1 (0/1) |
| **B: definitieve selectie** | **14/14** | **42** | **39** | **8** (3 type, 4 rand/strook, 1 gesplitst) | **3** (1/2) |

- Gemist door crop of dekking: 0. Wat de dekking wegneemt, telt al niet als zichtbaar (zie §2).
- Onterecht:
  - randstroken: de onderrand van ramen uit de laag erboven, op de wandgrens van LoD2.2. Die zijn met een simpele
    regel te filteren: een element langs de beeldrand met een hoogte < 0,15 m;
  - typeverwarring: het witte paneel binnen het kozijn gelabeld als `facade_panel`.
- Deels verborgen ramen worden alleen op het zichtbare deel omlijnd, wat de m² onderschat.
- **USER_ASSISTED_REFERENCE niet uitgevoerd.** FULL_AUTO mist op goed zichtbare gevels 2 van 42 objecten door het
  model; dat is niet "duidelijk objecten missen". Het probleem is dekking, niet herkenning.

**Ontbrekende dekking die een bewoner met foto's zou moeten aanvullen** (≥ 1 m² per pand/zijde/laag;
`missing_for_resident_photos_m2` per pand):
- voorzijde BG: 15 panden, 335 m² (vooral zijwangen van blokken en tuinstroken);
- voorzijde 1e: 15 panden, 152 m²;
- voorzijde kap: 14 panden, 91 m²;
- achterzijde BG: 14 panden, 189 m² (schuttingen);
- achterzijde 1e: 14 panden, 95 m²;
- kopgevels: 2 panden.

Concreet per woning: één foto recht op de achtergevel vanuit de tuin, plus één foto van de benedenverdieping aan de
voorzijde tussen de blokken.

## 8. Beperkingen

- Camerahoogte: de API-hoogte min een benaderde geoïde (43,3 m), zoals in v1; er is geen NLGEO-raster. Pitch/roll uit
  de API worden niet toegepast. Een eerste poging tot registratie per panorama (fit op modelranden) gaf geen
  eenduidige verbetering en is niet gebruikt. De registratiefout blijkt uit de 0,24 m mediane verschuiving tussen
  panorama's.
- Het groenfilter (ExG) mist veel begroeiing; het model vangt die op (pand 240).
- "Bevestigd zichtbaar" leunt op de door het model gemelde afgedekte zones (rechthoeken). Die kunnen royaal zijn.
- LoD2.2-fragmentatie: randstroken en een soms andere "hoofdwand" (274/276).
- Detectie-review door AI, niet door een mens; er is geen ground truth op maat (geen tekening, geen meting).

## 9. Beslissing: **ITERATE_COVERAGE**

- Detectie is op goed zichtbare vlakken bruikbaar: recall 0,93, precision 0,83. De onterechte detecties zijn met
  regels te filteren.
- Op de 10 goed gedekte middenpanden is de spreiding klein: 4,6–6,5 m² op de hoofdwand. **ITERATE_DETECTION is dus
  niet de bottleneck.**
- De bottleneck is dekking: 41% van de buitengevel is bevestigd zichtbaar, achterzijden 26%, zijwangen van de blokken
  28%, en geen enkel pand haalt ≥ 80% voor en achter. Extra panorama's leveren weinig op (+7,5%), omdat alle jaren
  vanaf dezelfde paden zijn opgenomen. **Openbare straatbeelden alleen zijn voor dit complextype onvoldoende voor
  volledige hoeveelheden.**
- De MJOP-hoeveelheid 756,8 is **BENCHMARK_NOT_COMPARABLE**. Dat verklaart het "factor 2"-verschil uit v1, maar
  betekent niet dat wij goed zitten: een echte ijking ontbreekt nog.

**Volgende stap binnen ITERATE_COVERAGE** (geen productiearchitectuur):
1. Voor 2–3 woningen bewonersfoto's (achtergevel en benedenverdieping voor) door dezelfde keten halen: rectificeren
   op 3D BAG, dezelfde detectie. Meten hoeveel dekking dat per woning oplevert.
2. Eén woning met een maatvaste tekening of handmeting als echte ijking van de openings-m².
3. Het randstrook-filter en de typeregel ("paneel binnen kozijn") toevoegen, en de review herhalen met een mens.

## Reproduceren

    python scripts/facade_coverage_poc_v2.py coverage  --out RUN [--cache CACHE]
    python scripts/facade_coverage_poc_v2.py detect    --out RUN [--cache CACHE]   # ANTHROPIC_API_KEY in de omgeving
    python scripts/facade_coverage_poc_v2.py aggregate --out RUN
    python scripts/facade_poc_v2_report.py --run-dir RUN

Het rapport is zonder API opnieuw te maken uit de gecommitte run:

    python scripts/facade_poc_v2_report.py --run-dir reports/quantity/facade_poc_v2_run

Bronvermelding: Gemeente Amsterdam, Kernregistratie Panoramabeelden (CC BY 4.0); 3D BAG (TU Delft, CC BY 4.0);
BAG (Kadaster, PDOK).
