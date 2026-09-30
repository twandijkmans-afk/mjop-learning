# Remote MJOP quantity strategy v1 — kritische haalbaarheidsanalyse

Status: **research / besluitvorming**. Er is geen code, schema, store of canonical data gewijzigd. Alle getallen in dit
document zijn gemeten op de repositories zoals ze op 2026-09-30 staan, tenzij als bron een externe URL staat of
expliciet **[niet geverifieerd]** is vermeld.

Geïnspecteerd:

| Repository / branch | Commit | Rol |
|---|---|---|
| `MJOP-App` `claude/mjop-live-implementation-smz60g` (default) | `fbe09d8` | web-app (statisch JS + Supabase) |
| `mjop-learning` `main` | `09a1052` | quantity observations, building links, crosswalk, kengetallen |
| `mjop-learning` `claude/extractie-v1-integratie` | `02466b7` | building projects, real validation v1–v3 |

**Structurele bevinding vooraf:** `mjop-learning` heeft twee uiteenlopende lijnen. `main` heeft 15 commits die de
integratiebranch mist (quantity observations, building links, crosswalk, kengetal-readiness, semantic review) en de
integratiebranch heeft 13 commits die `main` mist (building projects, real validation). Elk plan dat historische
quantities combineert met building projects moet eerst deze twee lijnen samenbrengen. Dat is geen researchvraag maar
wel een directe blokkade voor PoC #1.

---

## 1. Wat al daadwerkelijk geïmplementeerd is

| Onderwerp | Status | Waar | Toelichting |
|---|---|---|---|
| Oude MJOP-import in de app | PARTIAL / POC | `MJOP-App src/app.js` (`parseCsv`, `extractPdfRegels`, SheetJS) | csv/xlsx per kolom, pdf best-effort op "jaartal + bedrag"; hoeveelheid bewaard als `IMPORTED_MJOP`. Geen layout-analyse. |
| Deterministische extractie | IMPLEMENTED (voor eigen layouts) | `mjop-learning scripts/deterministic_extraction.py`, profielen, incoming pipeline | Werkt op de Pro VvE-layouts (`profile:pro_vve_overzicht15`) + XLS; andere bureaus (bv. Innax DOC-004) apart. Draait niet in de app (geen backend-worker). |
| Quantities in de app | IMPLEMENTED | `MJOP-App src/quantity.js` | Eén quantity-object per post: value/unit/source/status/history; bron `BAG`, `3D_BAG`, `GEOMETRY_DERIVED`, `ESTIMATED`, `IMPORTED_MJOP`, `MANUAL`. |
| Quantity source/status + meerdere bronnen | IMPLEMENTED | `quantity.js` (`evidence`, `selected`), bundelimport | Bronnen naast elkaar, mens kiest; nooit middelen. |
| BAG | IMPLEMENTED | app `lookupBuilding`; learning `fetch_real_building_validation.py` | Adres → pand, VBO's, bouwjaar. |
| 3D BAG attributen | IMPLEMENTED | app (dak plat/schuin, buitenmuur, hoogte); learning (alle b3_-attributen + ruwe respons) | |
| 3D BAG LoD2.2-geometrie | PARTIAL / POC | alleen `reports/quantity/maldenhof_roof_validation_v2.json` (dakvlakken) | Geen dakrand-/gootregels in productie. |
| Building projects | IMPLEMENTED | integratiebranch `building_projects.py`, BPRJ-00001 | 1 goedgekeurd project (Maldenhof). |
| Building links (legacy) | IMPLEMENTED, 0 records | `main` `building_links.py` | 0 bevestigde links. |
| Historische quantity-data | IMPLEMENTED (data) | `main` `data/quantity_observations/quantity_observations_v1.json` | 662 elementhoeveelheden, 11 documenten, 9 source clusters, **8 onafhankelijke gebouwen** (zie §7). |
| Foto's | NOT IMPLEMENTED | — | Alleen een vlag `has_photos` in `schemas/document.schema.json`. Geen upload, opslag of analyse. |
| Tekeningen | DOCUMENTED ONLY | `docs/quantity_engine_feasibility_v1.md` §5–9 | Geen code, geen tekeningcorpus. |
| Crosswalk app ↔ interne codes | PARTIAL | `main` `crosswalk.py`, 0 geverifieerd | Voorstellen PROPOSED/REVIEW_REQUIRED. |
| Prijsbibliotheek | PARTIAL | app: hardgecodeerd `ELEMENT_LIBRARY`; learning: 545 price observations | Geen koppeling app ↔ learning. |
| Kengetallen | PARTIAL | `main` `data/kengetallen/kengetallen_batch1.json` | **2** kengetallen status AVAILABLE. |
| Conditie | PARTIAL | app: handmatige gebreken (ernst/omvang/intensiteit → score) | Geen foto-gebaseerde conditie. |
| Human review | IMPLEMENTED | learning: append-only decision records, review sheets; app: bevestigen/aanpassen | |
| Backend-verwerking (worker) | NOT IMPLEMENTED | — | App heeft alleen Supabase Edge Functions; Python-pipeline draait lokaal/CI. |

Niet opnieuw bouwen: quantity-object met bronnen, BAG/3D BAG-opvraag, building projects, deterministische extractie
van eigen layouts, human-review-patronen.

---

## 2. Kritische beoordeling van de hypothese

Hypothese: *"quantities zijn voldoende te benaderen via oud MJOP + foto's + BAG/3D BAG + LoD2.2 + historische ratio's +
tekeningen indien beschikbaar + menselijke bevestiging; een generieke tekeninglezer is niet de eerstvolgende stap."*

**Wat klopt:** de tekeninglezer moet niet de eerstvolgende stap zijn (§8). En 3D BAG levert voor sommige onderwerpen
een bruikbare onafhankelijke orde-grootte (gemeten, MJOP t.o.v. 3D BAG: Maldenhof gevel −6,6%, hellend dak +4,9%; §5/§11).

**Wat ik afwijs of zwaar relativeer:**

1. **"Historische MJOP-quantities als benchmark" is grotendeels een cirkel.** Gemeten:
   - voegwerk-m² = gevel-m² in **7 van 8** gebouwen (ratio exact 1,00);
   - metselwerk en stucwerk/voegwerk hebben identieke getallen (Alkmaarstraat 2983, Maldenhof 1631,9, Mauritstaete 1065,1);
   - kozijn-m² = kozijnschilderwerk-m² (Maldenhof 756,8 = 756,8);
   - DOC-005/DOC-006: 31 van 35 elementhoeveelheden identiek; DOC-002 (2026) en DOC-004 (2018, ander bureau) identiek
     (`docs/quantity_engine_feasibility_v1.md` §1.4); over alle gerelateerde documenten 232× identiek, 18× anders.
   - 9 van 10 batch-1-documenten komen van dezelfde opsteller.

   Deze getallen zijn dus deels rekenconventies en doorgekopieerde waarden, geen metingen. "Nieuwe methode ≈ oud MJOP"
   bewijst overeenstemming met eerdere praktijk, niet met de werkelijkheid. **Zonder een kleine onafhankelijke
   ground truth kan het kernidee niet bewezen worden** (§10).
2. **Historische ratio's zijn nu niet verdedigbaar** als voorspeller (n = 8, één opsteller, spreiding kozijn/gevel
   0,37–0,98; §7). Ze kunnen hoogstens als plausibiliteitsband dienen.
3. **Street View als fotobron valt af** op licentiegronden (§9), niet op techniek.
4. **"Foto + 3D BAG = maatvast"** geldt alleen voor het vlakke hoofdgevelvlak; niet voor balkons, galerijen,
   terugliggende delen of hekwerk (§5). En dit is nog nergens gemeten.
5. **LoD2.2-dakranden zijn geen goten** (gemeten: gootkandidaten 112,4 m vs MJOP 165,8 m¹, §6).
6. **Voor Service A zijn quantities niet het hoofdprobleem.** Uit de data: hoeveelheden veranderen tussen versies nauwelijks;
   de onzekerheid zit in **conditie, planning en prijs**. Eenheidsprijzen voor hetzelfde element + handeling lopen tussen
   gebouwen een factor **1,2–6,7** uiteen (545 price observations; niet genormaliseerd voor jaar/btw/scope). Het
   investeren van de volgende maanden in quantity-meting optimaliseert de kleinste foutbron van Service A.
7. **"Zonder locatiebezoek"** is voor conditie niet haalbaar voor een relevant deel van de elementen (§10). Dat is een
   product- en aansprakelijkheidsgrens, geen engineeringprobleem.

**Eigen correctie:** in `reports/quantity/maldenhof_roof_validation_v2.json` zijn LoD2.2-hoogtes als "hoogte" gelezen,
maar het zijn **NAP-hoogtes** (maaiveld ≈ −1,37 m NAP). "Platte delen op ~1,6 m en ~4,4 m" zijn in werkelijkheid
~3,0 m en ~5,8 m boven maaiveld. De daaruit afgeleide uitspraak "geen dakkapel-achtige platte delen" is **niet
onderbouwd** en moet in dat rapport gecorrigeerd worden (klein, maar een fout in een gecommit rapport).

---

## 3. Service A — bestaand MJOP actualiseren

| Veld uit oud MJOP | Hergebruik | Validatie nodig | Remote te controleren met |
|---|---|---|---|
| Elementenlijst (code, omschrijving, locatie) | ja, als startpunt | ontbrekende/vervallen elementen | foto's (zichtbare elementen), BAG (installaties niet) |
| Hoeveelheden | ja, **gemarkeerd** als "overgenomen" | alleen verdachte posten | 3D BAG (gevel, dak), onderlinge consistentie (voeg = gevel), cross-check tussen versies |
| Cycli | ja | nauwelijks | — |
| Planning (jaar) | nee, herberekenen | uitgevoerd werk | facturen/offertes, notulen, verklaring beheerder |
| Prijzen | nee | altijd | prijsbibliotheek, indexatie, offertes |
| Conditiescores | **nee** | altijd | foto's slechts deels (§10) |

**Gekopieerde/verouderde quantities opsporen** (grotendeels automatiseerbaar, deterministisch):
- identieke getallen voor verschillende elementen (voeg = gevel, kozijn = kozijnschilderwerk) → markeren als conventie;
- identiek over versies én auteurs (DOC-002 = DOC-004) → "doorgekopieerd, nooit hermeten";
- 3D BAG-plausibiliteit per onderwerp (gevel, hellend dak) met vooraf gedefinieerde band;
- actiehoeveelheid > elementhoeveelheid, eenheidsfouten (al in `quantity_observations`: 48 review-redenen).

**Wat offertes/facturen bevestigen:** uitgevoerd werk (planning verschuift), actuele eenheidsprijzen, soms hoeveelheden
(een offerte schilderwerk noemt m² of stuks). Offertes zijn in de app nu handmatige invoer; OCR bestaat niet.

**Realistisch grotendeels automatiseerbaar:** import eigen layouts, indexatie/prijsactualisatie, markering verdachte
quantities, planning op basis van opgegeven uitgevoerd werk. **Niet:** conditieherbeoordeling van niet-zichtbare
elementen, beslissing of een oude hoeveelheid nog klopt na een verbouwing die niet gemeld is.

Conclusie Service A: **laag technisch risico, hoge waarde, snelste pad naar een verkoopbaar product**, mits eerlijk
gecommuniceerd dat conditie deels op aangeleverd materiaal berust.

---

## 4. Service B — volledig nieuw MJOP

Beoordeling per onderwerp (eerlijk: behalve Maldenhof is niets hiervan gemeten):

| Onderwerp | 3D BAG / LoD2.2 | Foto's | Foto's + 3D BAG | Tekening | Historische ratio | Handmatig |
|---|---|---|---|---|---|---|
| Gevel bruto m² | **goed** (Maldenhof: MJOP −6,6% t.o.v. 3D BAG) | — | — | goed | n.v.t. | — |
| Gevel netto (excl. openingen) | nee | nee | mogelijk | goed | zwak | — |
| Hellend dak m² | **goed** (Maldenhof: MJOP +4,9% t.o.v. 3D BAG) | — | — | goed | — | — |
| Plat dak m² | onzeker (scope: bergingen, luifels) | deels | — | goed | — | ja |
| Kozijnen aantal | nee | **goed (tellen)** | goed | goed | zwak | ja |
| Kozijnen m² / schilder-m² | nee | nee | **onbewezen** | goed | te zwak (0,37–0,98) | ja |
| Goot m¹ | kandidaat, geen goot-classificatie | deels | — | goed | zwak | ja |
| HWA m¹ | nee (verticaal) | tellen, lengte ≈ hoogte | redelijk (hoogte × aantal) | goed | zwak | ja |
| Balkons / hekwerk m¹ | nee | tellen | onbewezen (niet in gevelvlak) | goed | zwak | ja |
| Binnen (trappenhuis, vloer) | nee | deels | nee | plattegrond | zwak | **ja** |
| Installaties | nee | typeplaatjes | nee | nee | nee | **ja** |

Waar geen maatvaste bron is: `ESTIMATED` met expliciete waarschuwing (bestaat al in `quantity.js`). Voor Service B is
de kern niet "meten" maar **welke posten bestaan** (elementinventaris); een vergeten post weegt zwaarder dan 10% op een
bestaande post. Foto's zijn daarvoor de beste remote bron.

---

## 5. Photo + 3D BAG feasibility

**A. Geeft 3D BAG genoeg schaal?** Voor één **vlak** gevelvlak: ja, in principe. Uit LoD2.2 zijn de 3D-hoekpunten van
het gevelvlak (breedte, goot-/nokhoogte) bekend met een opgegeven fout van **b3_rmse_lod22 ≈ 0,13–0,19 m (mediaan
0,19 m) voor Maldenhof** (AHN5, 2023). Vier overeenkomende punten (gevelhoeken) bepalen een homografie van het beeld
naar het gevelvlak; dan zijn maten *in dat vlak* metrisch. Een hoekfout van 0,19 m op een gevel van 10 m is ~2%
schaalfout per as.

**B. Wat ontbreekt:** interne camera (brandpuntsafstand, lensvervorming), camerapositie, en welke beeldpunten bij welke
3D-hoek horen. De gevelhoeken moeten zichtbaar én correct aangewezen zijn; bij rijwoningen is de grens tussen panden
in het beeld vaak niet zichtbaar (Maldenhof: 15 panden, 29 woningen in rijen).

**C. Homografie werkt** voor objecten in hetzelfde vlak als de referentiehoeken (kozijnen in de gevel, gevelbekleding).
**Werkt niet** voor alles buiten dat vlak: balkons, balkonhekwerk, galerijen, luifels, terugliggende gevels, erkers,
dakkapellen. Die krijgen perspectieffouten die groeien met de diepte t.o.v. het vlak en de kijkhoek.

**D. Storingen:** bomen en auto's verbergen onderste kozijnen (tellen faalt stil, niet zichtbaar); groothoek-telefoons
hebben merkbare vervorming (EXIF helpt deels); meerdere panden in één foto vereisen per pand een eigen vlak;
schuine/gebogen gevels breken de vlakaanname.

**E. Realistische nauwkeurigheid [schatting, niet gemeten]:** aantal kozijnen in een vrij zichtbaar gevelvlak: bijna
exact; kozijn-m² in het gevelvlak: ±5–15%; gevelvlak zelf: ±5% (maar dat levert 3D BAG al); schilder-m²: afhankelijk
van definitie (kozijnomtrek × profielbreedte of "kozijn-m²"-conventie) — de definitie is de grootste fout;
balkonhekwerk: ±20% of slechter (buiten vlak).

**F. Varianten:**

| Variant | Schaal | Robuustheid |
|---|---|---|
| PHOTO_ONLY | geen | niet maatvast; alleen tellen |
| PHOTO + ONE_REFERENCE_MEASURE | één as | goed als de maat in het gevelvlak ligt (bv. voordeurbreedte); anisotropie niet gecorrigeerd |
| PHOTO + 3D_BAG | beide assen via hoeken | hangt af van correct aanwijzen hoeken en zichtbaarheid |
| PHOTO + 3D_BAG + USER_ANCHORS | beide + controle | **meest robuust**: 3D BAG geeft schaal, één gebruikersmaat is een onafhankelijke check |

Aanbeveling: niet bouwen voordat een **handmatig geannoteerde** bovengrens (mens wijst hoeken + kozijnen aan) de
drempel haalt (PoC #2). Als zelfs met perfecte menselijke annotatie de fout te groot is, heeft automatisering geen zin.

---

## 6. LoD2.2 dakranden en goten

Gemeten op de 15 Maldenhof-panden (analyse-script, niet gecommit; bron `real_validation_v3` ruwe 3D BAG):

| Randtype (geometrisch) | Lengte (m) |
|---|---|
| Laag horizontaal, vrij (gootkandidaat) | **112,4** |
| Vrij schuin (topgevel/boeiboord, of aansluiting op buurpand die niet exact samenvalt) | **657,9** |
| Rand plat dakdeel | 311,7 |
| Intern (nok/hoek/kil binnen pand) | 110,4 |
| Gedeeld met ander pand in scope (exact samenvallend) | 93,5 |
| Hoog horizontaal (tegen muur) | 28,6 |

MJOP: dakgoot zink **165,8 m¹**, dakrandafwerking zink **70 m¹**, HWA 133 m¹.

- Gootkandidaat t.o.v. MJOP-goot: −32% (112,4 vs 165,8). Mogelijke oorzaken: goten ook langs platte delen/aanbouwen, goten op bergingen
  (buiten scope), MJOP-conventie. **Niet verklaard.**
- 657,9 m "vrije schuine rand" is fysiek onmogelijk als boeiboord voor 15 rijwoningen: het grootste deel zijn
  pandgrenzen die in LoD2.2 niet exact samenvallen (per pand gereconstrueerd). Zonder topologie-opschoning (snapping,
  pand-overschrijdende vlakken, scheidingsmuren) is de classificatie onbruikbaar.

Onderscheid goot / boeiboord / topgevel / aansluiting / gedeelde grens vereist: (1) topologie over panden heen,
(2) koppeling met WallSurfaces (topgevel = schuine rand boven een muur), (3) informatie die LoD2.2 niet heeft
(of er daadwerkelijk een goot hangt, materiaal, bakgoot vs mastgoot).

**Oordeel: sanity-check evidence, geen quantity candidate, zeker niet productiegeschikt.** Noklengte en dakvlakken
(oppervlak, helling) zijn wel betrouwbaar.

---

## 7. Historische ratio's

Gemeten op `main` `quantity_observations_v1.json` (662 observaties), gebouwen samengevoegd waar documenten hetzelfde
object zijn (DOC-002+004, DOC-005+006, DOC-008+009):

- **8 onafhankelijke gebouwen** met quantities (Alkmaarstraat, JP Heijestraat, Maldenhof, Mauritstaete, St Jacobsstraat,
  Zomerdijkstraat, Meppelweg, Vechtstraat). DOC-011 en DOC-015 hebben geen elementhoeveelheden.
- 95 element-eenheid-combinaties; **19** met ≥ 5 gebouwen, 44 met ≥ 3.
- **Eén opsteller** voor 9 van 10 batch-1-documenten → ratio's leren diens conventies.

| Ratio | n | Waarden | Oordeel |
|---|---|---|---|
| kozijn-m² (3120) / gevel-m² (2110) | 8 | 0,37 – 0,98 (mediaan 0,53) | spreiding factor 2,6; noemer is zelf conventie. **Niet verdedigbaar** als voorspeller. |
| voegwerk-m² (4111) / gevel-m² | 8 | 1,00 (7×), 1,29 | **conventie**, geen meting — onbruikbaar |
| goot-m¹ (2716) / gevel-m² | 5 | 0,03 – 0,38 | te klein en te wijd |
| HWA-m¹ (5211) / gevel-m² | 8 | 0,05 – 0,19 | band, geen voorspeller |
| schilder kozijn (4631) / kozijn-m² | 4 | 0,33 – 1,00 | definitieverschil |
| dakrand-m¹ / footprint-omtrek | 1 | alleen Maldenhof heeft een bevestigd pand | **niet meetbaar** |
| balkons / eenheden | ≤ 2 | eenheden alleen bekend voor Maldenhof (29), St Jacobs (30), Vechtstraat (11) | **niet meetbaar** |

Ratio's met een 3D BAG-noemer vereisen bevestigde gebouwkoppelingen; die zijn er nu voor **1** gebouw (BPRJ-00001) plus
kandidaten (Vechtstraat STRONG, DOC-001/DOC-015 MODERATE). Invloed van bouwjaar, type, grootte of materiaal is met n ≤ 8
niet te scheiden. **Conclusie: geen ratio is nu als schatter verdedigbaar; hooguit als plausibiliteitsband met expliciete
n en spreiding.** Pas bij ~30+ onafhankelijke gebouwen van meerdere opstellers wordt dit interessant.

---

## 8. Tekeningen en bouwarchief

| Bron | Meetbaar | Menselijke hulp | Schaalbron | Effort **[schatting]** |
|---|---|---|---|---|
| A. vector-PDF / CAD | lengtes, oppervlakken, aantallen (via blokken) | laag–middel (1 kozijn aanwijzen) | echte eenheden / maatlijnen | middel (3–5 wk voor kozijnen op gevel) |
| B. hoogwaardige raster | idem, met OCR | middel | maatvoering (OCR) | middel–hoog |
| C. slechte oude scan | alleen tellen, grove maten | hoog | maatlijnen, vaak anisotroop vervormd | hoog, onzeker |
| D. splitsingstekening | aantallen, indeling | laag | **schematisch, niet meten** | laag (alleen tellen) |
| E. plattegrond | vloeroppervlak, trappenhuis, binnenposten | middel | maatvoering | middel |
| F. gevelaanzicht | kozijnen, gevelvlakken, hekwerk | middel | maatvoering > nominale schaal | middel |
| G. doorsnede | hoogtes, dakopbouw | middel | maatvoering | middel |

Maatvoering (maatlijnen + getallen) is betrouwbaarder dan de nominale schaal (printformaat, kopieerverkleining,
"1:100" op een A3-verkleining van A1).

**Bouwarchief als programmatische bron:** voor Amsterdam kon geen publieke API of bulk-download gevonden worden; de
gevonden route is aanvragen/inzien per dossier via e-mail of het stadsdeel **[gedeeltelijk geverifieerd via zoekresultaten;
amsterdam.nl was vanuit deze omgeving geblokkeerd]**. Openbaarheid van bouwtekeningen is bovendien beperkt om
veiligheidsredenen (Kamervragen, zie bronnen). Zelfs mét toegang is de keten adres → dossier(s) → tientallen bestanden
→ juiste, actuele tekening kiezen → bruikbaarheid → schaal → meten; **de grootste bottleneck is selectie en actualiteit
(tekening ≠ as-built), niet het meten.** Oordeel: tekeninglezer lager op de roadmap is **terecht**; wel een simpele
handmatige meettool voor aangeleverde tekeningen (NEXT), geen generieke lezer.

---

## 9. Fotobronnen en licenties

| Bron | Technisch | Commerciële verwerking | Opslag | AI-verwerking | Afgeleide quantities opslaan | Kosten / schaal |
|---|---|---|---|---|---|---|
| A/B. Eigen foto's VvE/beheerder/bewoner | goed (mits instructie) | ja, met toestemming in voorwaarden | ja (AVG: personen, kentekens, interieur) | ja, verwerkersovereenkomst bij externe AI | ja | laag; schaal afhankelijk van medewerking |
| C. Google Street View | goed | **nee** voor dit doel | **nee**: "will not … pre-fetch, index, store … Street View images" (3.2.3(a)) | **nee**: gebruik voor ML-modellen uitgesloten | **nee**: "will not create content based on Google Maps Content … (v) construct an index of tree locations within a city from Street View imagery" (3.2.3(c)) | — |
| D. Cyclomedia | zeer goed (gekalibreerd, LiDAR, meettools) | alleen met licentie; API-gebruik "only for the purpose of integrating Cyclomedia software into software owned or used by customers of Cyclomedia" **[fragment; volledige voorwaarden niet te openen]** | **[onzeker]** | **[onzeker]** | **[onzeker]** | commercieel contract, prijs onbekend |
| E. Overig (Mapillary/Panoramax e.d.) | wisselende dekking/kwaliteit | licentie per bron (bv. CC-BY-SA) **[niet onderzocht]** | — | — | — | — |

Bron Google: Google Maps Platform Terms, "Last modified August 26, 2026", §3.2.3, opgehaald op 2026-09-30.
**Conclusie:** Street View is geen optie voor het afleiden en opslaan van hoeveelheden. Cyclomedia is technisch de sterkste
remote bron (metrische panorama's) maar vraagt een commercieel contract; dat is een zakelijke vraag, geen
ontwikkelvraag. Het product moet uitgaan van **door de VvE aangeleverde foto's**.

---

## 10. Conditie zonder locatiebezoek

| Gebrek / element | Klasse | Toelichting |
|---|---|---|
| Afbladderende verf, verkleuring | REMOTE_OBSERVABLE | mits dichtbij en voldoende resolutie |
| Houtrot | PARTIALLY_OBSERVABLE | zichtbaar in gevorderd stadium; beginnend rot vraagt prikken |
| Scheuren metselwerk | PARTIALLY_OBSERVABLE | grote scheuren ja; oorzaak/voortgang nee |
| Voegwerk | PARTIALLY_OBSERVABLE | alleen van dichtbij; hoog gelegen niet |
| Dakbedekking plat | NOT_RELIABLY_OBSERVABLE | niet zichtbaar vanaf straat; drone of dakfoto nodig; blazen/naden niet te beoordelen |
| Dakpannen | PARTIALLY_OBSERVABLE | verschoven/gebroken pannen soms zichtbaar |
| Lekkage | NOT_RELIABLY_OBSERVABLE | alleen gevolgen binnen, via melding bewoner |
| Kitvoegen | PARTIALLY_OBSERVABLE | alleen close-up |
| Bevestigingen, ankers, hekwerk | NOT_RELIABLY_OBSERVABLE | vereist aanraken/belasten |
| Constructieve problemen | NOT_RELIABLY_OBSERVABLE | vereist deskundige ter plaatse |
| Installaties (cv, lift, ventilatie) | NOT_RELIABLY_OBSERVABLE | alleen typeplaatje/bouwjaar remote; werking niet |
| Verborgen gebreken (riolering, fundering, spouwankers) | NOT_RELIABLY_OBSERVABLE | ook ter plaatse vaak alleen met onderzoek |

**NEN 2767:** een fotobeoordeling is geen NEN 2767-conditiemeting en mag niet zo gepresenteerd worden (dat staat al in
`CLAUDE.md` en de app-README). Het product kan hooguit spreken van "conditie-indicatie op basis van aangeleverde foto's"
met per element de bron. Voor een deel van de elementen blijft het oordeel "niet remote vast te stellen" — dat moet
zichtbaar in het MJOP staan, niet weggeschat worden.

---

## 11. Maldenhof als reality check (DOC-005/006, BPRJ-00001)

| Kandidaat | Historische waarde | 3D BAG / LoD2.2 | Foto zichtbaar | Tekening nodig | Objectief meetbaar succes | Oordeel |
|---|---|---|---|---|---|---|
| Gevel bruto (2110) | 1631,9 m² (ook = voegwerk) | 1747,3 m² buitenmuur (MJOP **−6,6%** t.o.v. 3D BAG) | n.v.t. | nee | ja | **sterk** voor PoC #1 |
| Hellend dak (4712) | 1485,6 m² | 1415,57 m² (MJOP **+4,9%** t.o.v. 3D BAG) | deels | nee | ja | **sterk** voor PoC #1 |
| Plat dak (4711) | 425,8 m² | 190,65 m² (+ bergingen 129,6–200,8, scope onbekend) | nauwelijks | mogelijk | pas na scope-definitie | UNRESOLVED; slecht als PoC |
| Dakgoot (2716) | 165,8 m¹ | gootkandidaat 112,4 m | ja | nee | ja, maar classificatie ontbreekt | als **negatieve controle** |
| Kozijnen (3120) | 756,8 m² (= schilder 4631) | — | ja | nee | alleen met onafhankelijke meting | **PoC #2** |
| Raamdorpels (3120 m¹) | 281,2 m¹ | — | ja | nee | ja (lengte in gevelvlak) | goede tweede meetgrootheid PoC #2 |
| Gevelbekleding hout (4112) | 332 m² | — | ja (voorgevel) | nee | ja | goede PoC #2-grootheid (vlak) |
| Balkons (3410/4322) | 59,1 m¹ / 49 m² | — | achtergevel, buiten vlak | nee | moeilijk | niet als eerste |
| Voegwerk (4111) | 1631,9 m² | — | — | — | **nee: conventie** | ongeschikt |

---

## 12. Aanbevolen PoC's (maximaal twee)

### PoC #1 — "Desk benchmark 3D BAG vs MJOP, met een klein onafhankelijk ijkpunt"

- **Vraag:** hoe ver komt een MJOP-hoeveelheid voor geometrie-native onderwerpen uit 3D BAG, en welke historische
  hoeveelheden zijn conventies?
- **Data:** alle gebouwen met een bevestigd of sterk kandidaat-project (nu Maldenhof; Vechtstraat, Alkmaarstraat,
  Groetstraat, St Jacobs, Meppelweg na menselijke bevestiging); `quantity_observations` (moet eerst van `main` naar de
  integratiebranch of andersom).
- **Onderwerpen (vooraf vastgelegd):** gevel bruto (2110 m² vs b3_opp_buitenmuur), hellend dak (4712 vs
  b3_opp_dak_schuin), plat dak (4711 vs b3_opp_dak_plat), dakgoot (2716 vs LoD2.2-gootkandidaat, als negatieve controle).
- **Onafhankelijk ijkpunt:** voor **2 gebouwen** één bron die niet van de MJOP-opsteller komt: een maatvaste tekening
  (splitsings-/bestektekening met maatvoering) of een meting tijdens een reguliere inspectie die toch al gepland is.
  Zonder dit ijkpunt meet PoC #1 alleen overeenstemming met eerdere praktijk.
- **Duur:** 1–2 weken (data en scripts bestaan grotendeels).

### PoC #2 — "Gevelfoto + 3D BAG, eerst met menselijke annotatie (bovengrens)"

- **Vraag:** haalt een door de VvE gemaakte gevelfoto, gerectificeerd met 3D BAG-hoeken, de drempel voor kozijnen en
  gevelbekleding, als een **mens** hoeken en objecten aanwijst? (Als dit faalt, heeft computer vision geen zin.)
- **Data:** Maldenhof (voorgevel met houten gevelbekleding, kozijnen, raamdorpels) + Vechtstraat (vooroorlogs, 3 panden);
  foto's door bewoner/beheerder volgens korte instructie; per gebouw **één** handmatig gemeten referentiemaat
  (bv. voordeurbreedte) als onafhankelijke controle.
- **Meetgrootheden:** aantal kozijnen (per gevel), kozijn-m² (buitenwerks), raamdorpel-m¹, gevelbekleding-m².
- **Ground truth:** het aantal is objectief; voor m²/m¹ een onafhankelijke meting van een steekproef van ≥ 5 kozijnen
  per gebouw (of een maatvaste gevelaanzicht-tekening). De MJOP-waarde (756,8 m²) wordt **alleen** gerapporteerd, niet
  als ground truth gebruikt, omdat die een conventie kan zijn.
- **Duur:** 2 weken, zonder CV-ontwikkeling (annotatie in een eenvoudige tool of zelfs een spreadsheet met pixelcoördinaten).

---

## 13. Succes- en faalmaten (vooraf vastgelegd)

Foutmaat: `absolute error = |Y − X|`, `percentage error = (Y − X) / X`, per gebouw én mediaan over gebouwen; X is de
ground truth (onafhankelijk ijkpunt) of, waar die ontbreekt, de MJOP-waarde **met label "vs. historische praktijk"**.

Onderbouwing drempels: eenheidsprijzen voor hetzelfde element + handeling lopen in de eigen data een factor 1,2–6,7
uiteen; een MJOP-begroting is daarmee op postniveau al ruwweg ±20–30% onzeker door prijs en scope. Een
hoeveelheidsfout moet daar duidelijk onder blijven om niet de dominante fout te worden.

| Grootheid | Succes | Twijfel | Falen |
|---|---|---|---|
| Gevel bruto, hellend dak (3D BAG) | mediaan ≤ 10% én geen gebouw > 20% | 10–20% | > 20% of verschil niet verklaarbaar per gebouw |
| Plat dak (3D BAG) | ≤ 15% **na** vastgelegde scope-definitie | 15–30% | scope niet vast te stellen zonder bezoek |
| Aantal kozijnen (foto) | ≥ 95% van de zichtbare kozijnen, 0 dubbeltellingen | 90–95% | < 90% |
| Kozijn-m², gevelbekleding-m², raamdorpel-m¹ (foto + 3D BAG) | ≤ 10% t.o.v. onafhankelijke meting | 10–20% | > 20% |
| Referentiemaat-check (foto) | gemeten maat binnen 5% van de handmatige maat | 5–10% | > 10% (dan is de rectificatie zelf onbetrouwbaar) |
| Menselijke tijd per gebouw (annotatie + controle) | ≤ 30 min | 30–60 min | > 60 min |

Geen resultaat wordt achteraf "succes" genoemd als het buiten deze grenzen valt; grenzen worden niet na het zien van
de data aangepast.

---

## 14. Kill criteria

| Techniek | CONTINUE IF | PAUSE IF | STOP IF |
|---|---|---|---|
| Photo measurement | PoC #2 haalt succesgrenzen met menselijke annotatie op beide gebouwen | alleen tellen haalt de grens, m² niet; of foto-aanlevering door VvE lukt < 70% van de gevels | referentiemaat-check > 10% of kozijn-m² > 20% ook met perfecte annotatie; of annotatie > 60 min/gebouw |
| LoD2.2 roof edges | na topologie-opschoning gootkandidaat ≤ 15% van onafhankelijke goot op ≥ 3 gebouwen | alleen bruikbaar als sanity-band | pandgrenzen niet betrouwbaar te scheiden van boeiboorden, of > 30% afwijking — dan alleen dakvlakken/nok gebruiken |
| Historical ratios | ≥ 30 onafhankelijke gebouwen, ≥ 2 opstellers, spreiding (P10–P90) binnen factor 1,5 | 10–30 gebouwen: alleen plausibiliteitsband tonen | ratio blijkt conventie (zoals voeg = gevel) of spreiding > factor 2 bij voldoende n |
| Drawing reader | ≥ 50% van de doel-VvE's kan een maatvaste tekening aanleveren **en** een handmatige meettool bespaart aantoonbaar tijd | tekeningen alleen via archief, per dossier handwerk | < 25% beschikbaarheid, of scans zonder maatvoering overheersen |
| Street View | — | — | **nu**: licentie (3.2.3) verbiedt afleiden en opslaan |

---

## 15. Roadmap

### SERVICE A — UPDATE EXISTING MJOP

- **NOW (2–4 wk):** `main` en integratiebranch samenbrengen; deterministische extractie beschikbaar maken voor de app
  (upload → worker → review), want de app-import is best-effort; "verdachte quantity"-regels (conventie-duplicaten,
  doorgekopieerd, 3D BAG-band voor gevel/hellend dak); backtest op de twee versieparen (Maldenhof 2023→2026,
  JP Heijestraat 2018→2026): welke regels veranderden werkelijk (quantity, prijs, jaar)?
- **NEXT:** prijsactualisatie/indexatie met herkomst; uitgevoerd werk uit facturen/offertes (eerst handmatig, dan
  OCR); foto-gebaseerde conditie-indicatie voor de REMOTE_OBSERVABLE-elementen, met expliciet "niet remote vast te
  stellen" voor de rest.
- **LATER:** automatische offerte-OCR; drone/dakfoto's voor platte daken.

### SERVICE B — CREATE NEW MJOP

- **NOW:** PoC #1 en PoC #2 (hierboven); bevestigen van de Vechtstraat-kandidaat en 1–2 andere projecten (menselijke
  stap) zodat PoC #1 meer dan één gebouw heeft; correctie NAP-fout in `maldenhof_roof_validation_v2`.
- **NEXT (alleen als PoC's slagen):** 3D BAG-quantities voor gevel/hellend dak als `GEOMETRY_DERIVED` in de app;
  begeleide foto-upload met instructie; handmatige annotatie-/meettool (foto en aangeleverde tekening) met
  deterministische geometrie; elementinventaris uit foto's (welke posten bestaan).
- **LATER:** computer vision voor kozijndetectie (pas na menselijke bovengrens + gelabelde data uit NEXT); LoD2.2-goten na
  topologiewerk; historische ratio's als schatter bij ≥ 30 gebouwen; Cyclomedia (na contract); tekeninglezer voor
  vector-PDF; bouwarchief-connectors.

---

## 16. Grootste resterende productrisico's

1. **Geen ground truth.** Historische MJOP's zijn geen metingen; zonder een klein onafhankelijk ijkpunt is elke
   nauwkeurigheidsclaim ongefundeerd.
2. **Conditie is de echte grens van "zonder bezoek".** Platte daken, installaties, lekkage, bevestigingen en constructie
   zijn niet remote te beoordelen; een MJOP zonder die oordelen is een ander (beperkter) product, met
   aansprakelijkheidsrisico als dat niet expliciet is.
3. **Medewerking VvE bij foto's.** Kleine VvE's zonder beheerder leveren mogelijk onvolledige of slechte foto's; dat is
   niet getest.
4. **Datasetbias.** 9/10 documenten van één opsteller; ratio's en benchmarks weerspiegelen diens methode.
5. **Twee uiteenlopende codelijnen** in `mjop-learning` en geen backend-worker in de app: de beste extractie en
   quantity-data zijn niet bereikbaar vanuit het product.
6. **Licenties.** De makkelijkste straatbeeldbron is juridisch uitgesloten; de beste (Cyclomedia) kost een contract.

---

## Centrale vragen

**Snelste en goedkoopste bewijs:** PoC #1 (desk, 1–2 weken, bestaande data) voor gevel en hellend dak, plus een
onafhankelijk ijkpunt op 2 gebouwen; daarna PoC #2 met door de VvE aangeleverde foto's en **menselijke** annotatie als
bovengrens, voordat er ook maar één regel computer vision wordt geschreven. Beide kunnen falen op vooraf vastgelegde
grenzen.

**Niet verantwoord remote te automatiseren:** conditie van platte daken, installaties, lekkage, bevestigingen,
constructie en verborgen gebreken; scope-definitie van verzamelposten (plat dak incl. bergingen?); goten/hekwerk/balkons
als maatvaste hoeveelheid; alles uit Street View; en elke claim richting NEN 2767.

---

## Bronnen

- Google Maps Platform Terms of Service, §3.2.3 (last modified August 26, 2026): https://cloud.google.com/maps-platform/terms
- Cyclomedia developer terms (alleen zoekfragment; pagina geblokkeerd vanuit deze omgeving): https://developer.cyclomedia.com/terms/
- Openbaarheid bouwtekeningen (Kamervragen, zoekresultaat): https://omgevingsweb.nl/beleid/beantwoording-kamervragen-over-de-openbaarheid-van-bouwtekening-en-bouwvergunningen/
- 3D BAG attributen en kwaliteit: ruwe responses in `data/external/building_validation/real_validation_v3/raw/3dbag/`
- Historische quantities: `mjop-learning` `main` `data/quantity_observations/quantity_observations_v1.json`
- Prijsspreiding: `mjop-learning` `main` `data/price_observations/price_observations_batch1_normalized.json`
