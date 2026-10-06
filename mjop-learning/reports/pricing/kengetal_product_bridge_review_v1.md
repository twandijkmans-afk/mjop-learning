# Kengetal Product Bridge Review v1

read-only review; geen activatie, geen prijswijziging, geen nieuw kengetal, geen indexatie, geen besluit.

Officiële bron: `data/kengetallen/kengetallen_batch1.json` (niet: data/kentallen/, data/kengetallen/history/, scripts/compute_kentallen.py). App-prijzen: MJOP-App `b77909a` en `eaeb256` (prijswaarden identiek: ja).

## A. Officiële kengetallen (2 AVAILABLE)

Historisch, niet geïndexeerd; geen actuele marktprijs, geen normprijs, geen prijspeil van één jaar.

| kengetal | code | actie | materiaal | eenheid | waarde | min–max | clusters | prijspeilen per cluster | btw | indexatie |
|---|---|---|---|---|---:|---|---:|---|---|---|
| KG-4711-replace-m1-aluminium-d463b0a2 | 4711 | replace | aluminium | m1 | 37.47 | 33.88–39.06 | 3 | SC-DOC-008+DOC-009: —; SC-DOC-011: —; SC-DOC-012: 1-4-2024 | inclusive | INDEXATION_NOT_POSSIBLE |
| KG-5211-replace-m1-pvc-5cb98033 | 5211 | replace | pvc | m1 | 54.39 | 45.23–61.09 | 5 | SC-DOC-001: —; SC-DOC-008+DOC-009: 21-4-2025; SC-DOC-010: 1-4-2023; SC-DOC-012: 1-4-2024; SC-DOC-013: 14-7-2026 | inclusive | INDEXATION_NOT_POSSIBLE |

- `KG-4711-replace-m1-aluminium-d463b0a2`: median of source-cluster contributions; contribution = median of post values within the cluster; post value = median of its observations' derived_unit_price_per_execution (annual_amount_used / quantity_value); exact Decimal; no weighting; no indexation. Caveats: {'PRICE_LEVEL_ABSENT': 3}; objecten: Dakrandafwerking aluminium trim.
- `KG-5211-replace-m1-pvc-5cb98033`: median of source-cluster contributions; contribution = median of post values within the cluster; post value = median of its observations' derived_unit_price_per_execution (annual_amount_used / quantity_value); exact Decimal; no weighting; no indexation. Caveats: {'PRICE_LEVEL_ABSENT': 4, 'PRICE_LEVEL_DIFFERENCE': 6, 'QUANTITY_SCALE_DIFFERENCE': 2}; objecten: Hemelwaterafvoer pvc.

## B. App-prijsinventaris

Per categorie: APP_DEFAULT_ESTIMATE 33, FORMULA_DEFAULT 6, IMPORTED_HISTORICAL_PRICE 1, OFFER_PRICE 1, USER_OVERRIDE 2, NO_PRICE 1. OFFICIAL_INTERNAL_KENGETAL in de app: 0.

| component | waarde | eenheid | categorie | aanpasbaar | aanpassing herleidbaar | offerte vervangt | bron |
|---|---|---|---|---|---|---|---|
| dak-plat.kengetal | 165 | €/m² | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| dakgoten.basis | 300 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| dakgoten.perEenheid | 90 | €/appartement | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| dakinspectie.basis | 420 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| dakinspectie.perEenheid | 2 | €/m² | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| dak-hellend.kengetal | 95 | €/m² | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| dakisolatie.kengetal | 60 | €/m² | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| gevel-metselwerk.kengetal | 26 | €/m² | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| schilderwerk-buiten.kengetal | 22 | €/m² | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| voegwerk.kengetal | 45 | €/m² | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| balkonhekken.kengetal | 210 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| intercom.kengetal | 575 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| riolering.basis | 1100 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| riolering.perEenheid | 120 | €/appartement | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| elektra.basis | 800 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| elektra.perEenheid | 90 | €/appartement | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| verlichting.kengetal | 65 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| waterleiding.basis | 600 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| waterleiding.perEenheid | 55 | €/appartement | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| brandveiligheid.kengetal | 45 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| cv-installatie.basis | 3500 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| cv-installatie.perEenheid | 350 | €/appartement | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| ventilatie.kengetal | 220 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| lift.basis | 12000 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| lift.perEenheid | 0 | € | NO_PRICE | nee | nee | nee | bron 'none': geen hoeveelheid, alleen vast bedrag |
| trappenhuis.kengetal | 480 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| vloerafwerking.kengetal | 120 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| bestrating.basis | 500 | € vast per beurt | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| bestrating.perEenheid | 60 | €/appartement | APP_DEFAULT_ESTIMATE | nee | nee | nee | hardcoded ELEMENT_LIBRARY, geen bron/prijspeil |
| fietsenstalling.kengetal | 150 | €/appartement | APP_DEFAULT_ESTIMATE | ja | nee | nee | hardcoded ELEMENT_LIBRARY (MJOP-App src/app.js), geen bron/prijspeil |
| steiger.tarief | € 6 (werkhoogte <= 8 m) / € 11 (> 8 m) | €/m² bruto buitenmuur | FORMULA_DEFAULT | nee | nee | nee | hardcoded tariefregel (MJOP-App src/quantity.js), sinds de eerste commit; geen bron |
| kozijnen.Draaiend raam | 174 | €/stuk (houten kozijn, vóór materiaalfactor) | APP_DEFAULT_ESTIMATE | ja | ja | nee | hardcoded KOZ_DEF, geen bron |
| kozijnen.Vast glas | 96 | €/stuk (houten kozijn, vóór materiaalfactor) | APP_DEFAULT_ESTIMATE | ja | ja | nee | hardcoded KOZ_DEF, geen bron |
| kozijnen.Deur | 240 | €/stuk (houten kozijn, vóór materiaalfactor) | APP_DEFAULT_ESTIMATE | ja | ja | nee | hardcoded KOZ_DEF, geen bron |
| kozijnen.Dakkapel | 320 | €/stuk (houten kozijn, vóór materiaalfactor) | APP_DEFAULT_ESTIMATE | ja | ja | nee | hardcoded KOZ_DEF, geen bron |
| kozijnen.materiaalfactor.aluminium | 0.35 | factor op het houten tarief | FORMULA_DEFAULT | nee | nee | nee | hardcoded KOZ_MATERIAAL, geen bron |
| kozijnen.materiaalfactor.hout | 1 | factor op het houten tarief | FORMULA_DEFAULT | nee | nee | nee | hardcoded KOZ_MATERIAAL, geen bron |
| kozijnen.materiaalfactor.kunststof | 0.2 | factor op het houten tarief | FORMULA_DEFAULT | nee | nee | nee | hardcoded KOZ_MATERIAAL, geen bron |
| kozijnen.materiaalfactor.staal | 1.1 | factor op het houten tarief | FORMULA_DEFAULT | nee | nee | nee | hardcoded KOZ_MATERIAAL, geen bron |
| custom.bedrag (geïmporteerd oud MJOP) | — | € per post | IMPORTED_HISTORICAL_PRICE | ja | nee | nee | MJOP-upload; prijspeil (basisjaar) door de gebruiker ingevuld |
| offerte (per post) | — | € per offerteregel | OFFER_PRICE | ja | ja | nee | handmatig ingevoerde offertes (state.offertes) |
| kengetal handmatig aangepast | — | zoals het element | USER_OVERRIDE | ja | nee | nee | invoerveld 'Prijs per m²/unit' overschrijft el.kengetal |
| kozijnen eigen tarief | — | €/stuk | USER_OVERRIDE | ja | ja | nee | k.eigenTarief |
| indexatie | CBS 83547NED BestaandeWoningen_7 (laatste jaarmutatie) of terugval 3%/jaar | %/jaar | FORMULA_DEFAULT | nee | nee | nee | CBS OData; vaste terugval 3% |

## C. App-element × kengetal

| app-element | hoeveelheid (eenheid) | formule | prijs | veilige code | kandidaatcodes | officieel KG (unit/actie/materiaal/semantiek) | beste prijsgroep | resultaat |
|---|---|---|---|---|---|---|---|---|
| dak-plat | 3D BAG b3_opp_dak_plat (ROOF_FLAT_AREA) (m2) | hoeveelheid × kengetal | kengetal=165 | 4711 | 4711 | KG-4711-replace-m1-aluminium-d463b0a2 (✗/✓/✗/✗) | 4711|install|m2|unknown (INSUFFICIENT_CLUSTERS, 2 cl., unit =) | **KG_EXISTS_BUT_NOT_COMPATIBLE** |
| dakgoten | aantal appartementen (BAG verblijfsobjecten) (app) | basis + hoeveelheid × perEenheid | basis=300, perEenheid=90 | — | 5211, 2716 | KG-5211-replace-m1-pvc-5cb98033 (✗/✓/✗/✗) | 5211|replace|piece|unknown (BLOCKED_OTHER, 3 cl., unit ≠) | **KG_EXISTS_BUT_NOT_COMPATIBLE** |
| dakinspectie | 3D BAG plat + schuin (ROOF_TOTAL_AREA) (m2) | basis + hoeveelheid × perEenheid | basis=420, perEenheid=2 | — | — | — | — | **FORMULA_PRICING_ONLY** |
| dak-hellend | 3D BAG b3_opp_dak_schuin (ROOF_SLOPED_AREA) (m2) | hoeveelheid × kengetal | kengetal=95 | — | 4712 | — | 4712|replace|m2|bitumen (INSUFFICIENT_CLUSTERS, 1 cl., unit =) | **NO_KG_AVAILABLE** |
| dakisolatie | 3D BAG plat + schuin (ROOF_TOTAL_AREA) (m2) | hoeveelheid × kengetal | kengetal=60 | — | — | — | — | **NO_KG_AVAILABLE** |
| gevel-metselwerk | 3D BAG b3_opp_buitenmuur (OUTER_WALL_GROSS_AREA, bruto) (m2) — proxy | hoeveelheid × kengetal | kengetal=26 | — | 2110 | — | 2110|impregnate|m2|unknown (INSUFFICIENT_CLUSTERS, 2 cl., unit =) | **NO_KG_AVAILABLE** |
| schilderwerk-buiten | 3D BAG b3_opp_buitenmuur (OUTER_WALL_GROSS_AREA, bruto) (m2) — proxy | hoeveelheid × kengetal | kengetal=22 | — | 4621, 4631 | — | 4621|exterior_painting|m2|wood (MATERIAL_AND_REVIEW_NEEDED, 7 cl., unit =) | **NO_KG_AVAILABLE** |
| kozijnen-onderhoud | per kozijnrij (schatting uit appartementen) (piece) | Σ aantal × round(tarief × materiaalfactor) per kozijnrij | KOZ_DEF=zie B | — | 3120, 3122, 3131, 4631 | — | 4631|exterior_painting|m2|wood (MATERIAL_AND_REVIEW_NEEDED, 6 cl., unit ≠) | **FORMULA_PRICING_ONLY** |
| steiger | 3D BAG b3_opp_buitenmuur (OUTER_WALL_GROSS_AREA, bruto) (m2) | hoeveelheid × tarief(werkhoogte) (per pand bij een scope) | tarief_laag=6, tarief_hoog=11 | — | 9999 | — | — | **FORMULA_PRICING_ONLY** |
| voegwerk | 3D BAG b3_opp_buitenmuur (OUTER_WALL_GROSS_AREA, bruto) (m2) — proxy | hoeveelheid × kengetal | kengetal=45 | — | 4111, 2110 | — | 2110|impregnate|m2|unknown (INSUFFICIENT_CLUSTERS, 2 cl., unit =) | **NO_KG_AVAILABLE** |
| balkonhekken | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=210 | — | 3410 | — | 3410|replace|m1|steel (INSUFFICIENT_CLUSTERS, 1 cl., unit ≠) | **NO_KG_AVAILABLE** |
| intercom | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=575 | — | 6422 | — | — | **NO_KG_AVAILABLE** |
| riolering | aantal appartementen (BAG verblijfsobjecten) (app) | basis + hoeveelheid × perEenheid | basis=1100, perEenheid=120 | — | 5240, 5211 | KG-5211-replace-m1-pvc-5cb98033 (✗/✓/✗/✗) | 5211|replace|piece|unknown (BLOCKED_OTHER, 3 cl., unit ≠) | **KG_EXISTS_BUT_NOT_COMPATIBLE** |
| elektra | aantal appartementen (BAG verblijfsobjecten) (app) | basis + hoeveelheid × perEenheid | basis=800, perEenheid=90 | — | 6111 | — | — | **FORMULA_PRICING_ONLY** |
| verlichting | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=65 | — | 6311 | — | 6311|replace|piece|unknown (BLOCKED_OTHER, 4 cl., unit ≠) | **NO_KG_AVAILABLE** |
| waterleiding | aantal appartementen (BAG verblijfsobjecten) (app) | basis + hoeveelheid × perEenheid | basis=600, perEenheid=55 | — | 5310 | — | — | **FORMULA_PRICING_ONLY** |
| brandveiligheid | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=45 | — | 6511, 6513 | — | 6511|replace|piece|unknown (INSUFFICIENT_CLUSTERS, 1 cl., unit ≠) | **NO_KG_AVAILABLE** |
| cv-installatie | aantal appartementen (BAG verblijfsobjecten) (app) | basis + hoeveelheid × perEenheid | basis=3500, perEenheid=350 | — | — | — | — | **FORMULA_PRICING_ONLY** |
| ventilatie | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=220 | — | 5721 | — | — | **NO_KG_AVAILABLE** |
| lift | geen hoeveelheid (vast bedrag) (—) | basis + hoeveelheid × perEenheid | basis=12000, perEenheid=0 | — | 6611, 6612 | — | — | **FORMULA_PRICING_ONLY** |
| trappenhuis | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=480 | — | 2410, 4211 | — | 2410|clean|piece|steel (INSUFFICIENT_CLUSTERS, 1 cl., unit ≠) | **NO_KG_AVAILABLE** |
| vloerafwerking | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=120 | — | 4321, 4322 | — | 4321|replace|m2|unknown (INSUFFICIENT_CLUSTERS, 2 cl., unit ≠) | **NO_KG_AVAILABLE** |
| bestrating | aantal appartementen (BAG verblijfsobjecten) (app) | basis + hoeveelheid × perEenheid | basis=500, perEenheid=60 | — | 9041 | — | — | **FORMULA_PRICING_ONLY** |
| fietsenstalling | aantal appartementen (BAG verblijfsobjecten) (app) | hoeveelheid × kengetal | kengetal=150 | — | — | — | — | **NO_KG_AVAILABLE** |

## D. Plat dak (4711, m2)

- Officieel AVAILABLE m2-kengetal: geen.
- Prijsregels m2: 12 in clusters SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-012, SC-DOC-013; als onafhankelijke invoer: SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-013.
- Dakbedekkingsregels (zonder grind) per actie: install: SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-013; onbekend: SC-DOC-011, SC-DOC-012; replace: SC-DOC-007, SC-DOC-008+DOC-009.
- Per materiaalterm in de tekst: app: SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-012, SC-DOC-013; ballast: SC-DOC-008+DOC-009, SC-DOC-011; bitumen: SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-012.
- Readiness-groepen: 4711|replace|m2|bitumen INSUFFICIENT_CLUSTERS (1 clusters); 4711|install|m2|unknown INSUFFICIENT_CLUSTERS (2 clusters); 4711|replace|m2|unknown INSUFFICIENT_CLUSTERS (2 clusters).

| observation | cluster | actie | omschrijving / actietekst | €/m² | prijspeil | onafhankelijk |
|---|---|---|---|---:|---|---|
| PO-DOC-005-P012-L077 | SC-DOC-005+DOC-006 | install | Dakbedekking APP / Aanbrengen nieuwe laag dakbedekking APP | 76.47 | 1-8-2026 | nee: POSSIBLY_DEPENDENT |
| PO-DOC-006-P015-L079 | SC-DOC-005+DOC-006 | install | Dakbedekking APP / Aanbrengen nieuwe laag dakbedekking APP | 63.20 | 1-3-2023 | nee: POSSIBLY_DEPENDENT |
| PO-DOC-007-P017-L119 | SC-DOC-007 | replace | Dakbedekking APP / Vervangen dakbedekking APP dakvlak 2 | 138.63 | 28-4-2023 | ja |
| PO-DOC-007-P017-L123 | SC-DOC-007 | replace | Dakbedekking APP / Vervangen dakbedekking APP dakvlak 3 | 138.63 | 28-4-2023 | ja |
| PO-DOC-007-P017-L127 | SC-DOC-007 | install | Dakbedekking APP / Aanbrengen nieuwe laag dakbedekking APP dakvlak 1-4-5 | 83.19 | 28-4-2023 | ja |
| PO-DOC-008-P009-L035 | SC-DOC-008+DOC-009 | replace | Dakbedekking APP+ballast (hoofddak) / Vervangen dakbedekking APP | 175.45 | — | ja |
| PO-DOC-008-P009-L041 | SC-DOC-008+DOC-009 | replace | Dakbedekking APP+ballast (hoofddak) / Vervangen grind | 22.51 | — | ja |
| PO-DOC-008-P009-L051 | SC-DOC-008+DOC-009 | replace | Dakbedekking bitumen ballast (liftdak) / Vervangen dakbedekking bitumen geballast | 175.45 | — | ja |
| PO-DOC-008-P009-L059 | SC-DOC-008+DOC-009 | replace | Dakbedekking bitumen ballast (liftdak) / Vervangen grind | 22.51 | — | ja |
| PO-DOC-011-P021-L077 | SC-DOC-011 | None | Dakbedekking bitumen / Aanbrengen nieuwe laag dakbedekking bitumen ongeballast | 72.60 | — | nee: ELIGIBILITY_UNKNOWN |
| PO-DOC-012-P014-L097 | SC-DOC-012 | None | Dakbedekking app / Aanbrengen nieuwe laag dakbedekking bitumen | 78.65 | 1-4-2024 | nee: ELIGIBILITY_UNKNOWN |
| PO-DOC-013-P018-L081 | SC-DOC-013 | install | Dakbedekking APP / Aanbrengen nieuwe laag dakbedekking APP | 102.85 | 14-7-2026 | ja |

Geen officieel AVAILABLE m2-kengetal voor 4711. Het enige 4711-kengetal is aluminium daktrim in m1 en is niet koppelbaar aan dak-plat (m2). De dakbedekkingsregels (zonder grind) noemen APP en/of bitumen; één bron noemt beide in dezelfde regel (APP is in de bronnen een bitumineuze dakbedekking). Volgens de huidige regels is elke 4711 m2-groep INSUFFICIENT_CLUSTERS. Blokkades voor één generiek dak-plat-kengetal: (1) APP en bitumen: één materiaalfamilie of twee (menselijk materiaalbesluit); (2) 'aanbrengen nieuwe laag' (overlagen) versus 'vervangen' (incl. ballast) zijn verschillende acties; (3) ballast/grind is een aparte deelpost; (4) twee bronnen hebben eligibility UNKNOWN (actie niet genormaliseerd) en DOC-005/DOC-006 vormen samen één source cluster (mogelijk afhankelijk). De 'aanbrengen nieuwe laag'-regels raken na die besluiten potentieel de meeste clusters en zijn de meest kansrijke toekomstige kandidaat. Readiness: NIET klaar; geen kengetal gemaakt.

## E. Hellend dak (4712, m2)

- Officieel AVAILABLE m2-kengetal: geen.
- Prijsregels m2: 2 in clusters SC-DOC-013; als onafhankelijke invoer: SC-DOC-013.
- Dakbedekkingsregels (zonder grind) per actie: replace: SC-DOC-013.
- Per materiaalterm in de tekst: bitumen: SC-DOC-013; shingles: SC-DOC-013; zink: SC-DOC-013.
- Readiness-groepen: 4712|replace|m2|bitumen INSUFFICIENT_CLUSTERS (1 clusters); 4712|replace|m2|zinc INSUFFICIENT_CLUSTERS (1 clusters).

| observation | cluster | actie | omschrijving / actietekst | €/m² | prijspeil | onafhankelijk |
|---|---|---|---|---:|---|---|
| PO-DOC-013-P019-L007 | SC-DOC-013 | replace | Dakbedekking shingles bitumen / Vervangen dakbedekking shingles bitumen | 78.65 | 14-7-2026 | ja |
| PO-DOC-013-P019-L013 | SC-DOC-013 | replace | Dakbedekking zink / Vervangen dakbedekking zink | 211.76 | 14-7-2026 | ja |

Dakpan-prijsregels: 0. Dakpanregels met alleen een hoeveelheid: QO-DOC-001-EL-041, QO-DOC-005-EL-027, QO-DOC-006-EL-027, QO-DOC-013-EL-021.

Geen enkele dakpan-prijsobservation (beton of keramisch): de 4712 m2-prijsregels zijn alleen shingles en zink uit één bron. De dakpanregels bestaan alleen als hoeveelheid (zie tile_quantity_observations_without_price), zonder prijsregel. Leisteen, shingles, zink en loodslabben blijven aparte materialen. Readiness: geen kandidaat mogelijk met de huidige data (0 onafhankelijke dakpan-clusters); niets samengevoegd op basis van code 4712.

## F. Steiger-prijsbron

- Regel: € 6/m² bruto buitenmuur bij werkhoogte <= 8 m, € 11/m² daarboven (per pand bij een scope).
- Herkomst: hardcoded sinds de eerste commits van MJOP-App (2026-09-19); geen bron, geen prijspeil. Categorie: FORMULA_DEFAULT (tariefregel) met APP_DEFAULT_ESTIMATE-tarieven.
- Historisch: 5 steiger-/hoogwerkerposten, eenheden ['pst']; per-m²-onderbouwing: 0.

Alle historische steigerposten zijn lump sums (pst) per project, zonder m² of hoogte: er is geen historische onderbouwing voor € 6 of € 11 per m². OUTER_WALL_GROSS_AREA en BUILDING_HEIGHT zijn betrouwbare hoeveelheid/context, maar dat maakt het tarief niet betrouwbaar. Geen tarief gewijzigd.

## G. Gevel: hoeveelheid versus prijs per eenheid

- `gevel-metselwerk`: hoeveelheid PROXY: bruto buitenmuur (ESTIMATED); prijs APP_DEFAULT_ESTIMATE (geen bron); prijsgroepen: 2110|impregnate|m2|unknown (INSUFFICIENT_CLUSTERS), 2110|repair|m2|unknown (INSUFFICIENT_CLUSTERS), 2110|replace|m1|unknown (INSUFFICIENT_CLUSTERS)
- `schilderwerk-buiten`: hoeveelheid PROXY: bruto buitenmuur (ESTIMATED); prijs APP_DEFAULT_ESTIMATE (geen bron); prijsgroepen: 4621|exterior_painting|m2|wood (MATERIAL_AND_REVIEW_NEEDED), 4631|exterior_painting|m2|wood (MATERIAL_AND_REVIEW_NEEDED), 4621|exterior_painting|m2|unknown (BLOCKED_OTHER)
- `voegwerk`: hoeveelheid PROXY: bruto buitenmuur (ESTIMATED); prijs APP_DEFAULT_ESTIMATE (geen bron); prijsgroepen: 2110|impregnate|m2|unknown (INSUFFICIENT_CLUSTERS), 2110|repair|m2|unknown (INSUFFICIENT_CLUSTERS), 2110|replace|m1|unknown (INSUFFICIENT_CLUSTERS)

Hoeveelheidsonzekerheid en prijs-per-eenheid-onzekerheid zijn twee aparte problemen: een goed kengetal per m² maakt een proxy-hoeveelheid (bruto buitenmuur incl. ramen) niet goed. Historische 2110-hoeveelheden zijn geen bruto buitenmuur en worden er niet aan gelijkgesteld. Eerst een eigen hoeveelheidsdefinitie (bijv. geschilderd oppervlak, metselwerkoppervlak), daarna pas een kengetal.

## H. Offerte- en override-flow

- Effectieve prijs per element = el.kengetal (default uit de bibliotheek, in place overschreven als de gebruiker het veld 'Prijs per m²/unit' aanpast; daarna niet meer te onderscheiden van de default).
- Kozijnen: k.eigenTarief (apart bewaard) gaat vóór round(tarief × materiaalfactor).
- Vast + variabel (basis/perEenheid) en steigertarieven hebben geen prijsinvoer: alleen hoeveelheid/werkhoogte zijn aanpasbaar.
- Geïmporteerde/eigen posten: el.bedrag + basisjaar, geïndexeerd naar het uitvoeringsjaar.
- Offertes worden per post opgeslagen, gelezen (Q.parseOfferteAmounts) en vergeleken, maar komen NIET in elementCost of de planning. Er is geen 'offerte accepteren'.

Werkelijke hiërarchie nu: USER_OVERRIDE (kengetal in place / eigenTarief) > APP_DEFAULT_ESTIMATE / FORMULA_DEFAULT > (OFFER_PRICE: alleen weergave).
Voorstel (niet geïmplementeerd): USER_OVERRIDE of geaccepteerde OFFER_PRICE > OFFICIAL_INTERNAL_KENGETAL > APP_DEFAULT_ESTIMATE.

Conflicten:
- Een offerte heeft nu geen effect op de kosten; 'geaccepteerde offerte' bestaat nog niet (eerst productbesluit).
- Een aangepast kengetal verliest zijn herkomst (geen USER_OVERRIDE-markering, geen oude waarde bewaard).
- Offertevergelijking vult ontbrekende regels met het gemiddelde van de andere offertes (alleen weergave); bij integratie in kosten mag dat geen bron worden.
- Een offerte is een totaalbedrag per post (regels), een kengetal is een prijs per eenheid: koppelen vraagt een expliciete keuze (offerte vervangt de post, niet het kengetal).
- UI beweerde 'een offerte overschrijft het tarief' (onjuist): gecorrigeerd in MJOP-App 'Price Source Labels v1'.

## I. Indexatie

CBS 83547NED 'BestaandeWoningen' — alleen de LAATSTE jaarmutatie, als vast percentage samengesteld vanaf basisjaar; terugval 3%/jaar. Alleen op custom/geïmporteerde posten; bibliotheekprijzen worden niet geïndexeerd.

- `KG-4711-replace-m1-aluminium-d463b0a2`: **INDEXATION_NOT_POSSIBLE**
- `KG-5211-replace-m1-pvc-5cb98033`: **INDEXATION_NOT_POSSIBLE**

READY alleen als ALLE source clusters één bekend prijspeil hebben; gemengde prijspeilen = AMBIGUOUS; een ontbrekend prijspeil = NOT_POSSIBLE. Nooit stil naar één jaar omrekenen. Ook bij READY is de huidige app-logica (laatste jaarmutatie als vast percentage) geen exacte indexreeks.

## J. UI-bronlabels

Aantoonbaar misleidend (opgelost in MJOP-App 'Price Source Labels v1' (geen prijswaarden gewijzigd)):
- Overzicht 'Waar komen deze cijfers vandaan?': 'indicatieve richtprijzen (… prijspeil <huidig jaar>)' — het jaar schoof elk jaar mee zonder prijsbron.
- Printrapport 'Kosten.': idem 'prijspeil <huidig jaar>'.
- Voetnoten start/scherm: 'Kengetallen zijn indicatieve richtprijzen' — app-defaults heten nu app-schattingen.
- Kozijnen: 'een offerte overschrijft het tarief' — onjuist, offertes komen niet in de kosten.
- Vast + variabel per appartement toonde '12 m² × € 90' — nu '12 app. × € 90'.

Nog te doen (geen kleine fix):
- Het prijsinvoerveld 'Prijs per m²/unit' toont geen bronlabel (App-schatting / Intern kengetal / Offerte / Door gebruiker aangepast).
- Het herkomstlabel van een post volgt de HOEVEELHEID (bijv. '3D BAG'), niet de prijs; een aangepaste prijs wordt niet als 'Door gebruiker aangepast' getoond.

## K. Dekking

24 app-elementen:
- READY_FOR_KG_INTEGRATION: 0 — —
- KG_EXISTS_BUT_NOT_COMPATIBLE: 3 — dak-plat, dakgoten, riolering
- REVIEWABLE_KG_CANDIDATE: 0 — —
- NO_KG_AVAILABLE: 13 — balkonhekken, brandveiligheid, dak-hellend, dakisolatie, fietsenstalling, gevel-metselwerk, intercom, schilderwerk-buiten, trappenhuis, ventilatie, verlichting, vloerafwerking, voegwerk
- FORMULA_PRICING_ONLY: 8 — bestrating, cv-installatie, dakinspectie, elektra, kozijnen-onderhoud, lift, steiger, waterleiding

Prioriteit voor een echt intern kengetal (geen score):
1. `dak-plat` — grootste bedragen (€ 165/m²), hoeveelheid betrouwbaar (ROOF_FLAT_AREA), meeste 4711 m2-prijsregels (meerdere clusters), semantiek redelijk helder; vraagt alleen menselijke groepsbesluiten.
2. `schilderwerk-buiten` — hoogste frequentie (6 jaar) en de sterkste prijsdata (4621/4631 buitenschilderwerk hout m2, 6–7 potentiële clusters), maar eerst een eigen hoeveelheidsdefinitie (geen bruto buitenmuur).
3. `kozijnen-onderhoud` — grote post met prijs per stuk; interne kozijn-/schilderwerkdata bestaat maar per stuk/m1 en met materiaal; vraagt een stuks-hoeveelheid die nu een schatting is.
4. `dakgoten` — officieel kengetal 5211 pvc m1 bestaat al, maar de app rekent per appartement: pas bruikbaar met een m1-hoeveelheid (nu geen bron; geen nieuwe subjects in deze stap).

## L. Volgende 3 prijs-milestones

1. **Price Source Model v1 (MJOP-App)** — prijsobject per post naast het hoeveelheidsobject: bron (APP_DEFAULT_ESTIMATE / OFFICIAL_INTERNAL_KENGETAL / OFFER_PRICE / USER_OVERRIDE), oude waarde bewaren bij aanpassen, bronlabel in de UI; nog geen kengetal-waarden activeren.
2. **Flat Roof Price Group Review (mjop-learning)** — besluitpakket voor de 4711 m2-regels: APP vs bitumen, overlagen vs vervangen, ballast/grind apart, eligibility DOC-011/DOC-012, afhankelijkheid DOC-005/006 — doel: een eerste m2-kengetal-kandidaat voor dak-plat (niet automatisch AVAILABLE).
3. **Offer Acceptance Decision (product)** — beslissen of en hoe een geaccepteerde offerte de kosten van een post vervangt (totaal per post, niet per eenheid), inclusief prijspeil/indexatie van offertes.

## M. Menselijke beslissingen

- Prijsbronhiërarchie: USER_OVERRIDE/geaccepteerde OFFER_PRICE > OFFICIAL_INTERNAL_KENGETAL > APP_DEFAULT_ESTIMATE — akkoord?
- Mag een geaccepteerde offerte de kosten van een post vervangen (totaal per post), en wat is dan het prijspeil?
- Indexatiebeleid voor kengetallen met ontbrekende/gemengde prijspeilen: niet tonen, of ongeïndexeerd tonen met caveat?
- 4711 dakbedekking: is APP een eigen materiaal of een bitumen-subtype? Zijn 'aanbrengen nieuwe laag' en 'vervangen' één actie of twee?
- 4711: ballast/grind-regels als aparte deelpost uitsluiten van een dakbedekkingskengetal?
- Steigertarief € 6/€ 11: als app-schatting behouden en zo labelen, of een bron zoeken?
- Gevel: eerst een eigen hoeveelheidsdefinitie (geschilderd oppervlak / metselwerkoppervlak) vóór een gevel-kengetal?
- Moeten basis/perEenheid (vast + variabel) door de gebruiker aanpasbaar worden?

## Ongewijzigd

- Officiële kengetallen sha256 `e8b9b2260fb681da242817e51dfdb5ca3b1ab3ec1e3e5dcd6b56d3cc71761897`.
- Crosswalk-besluiten XWD-00001, XWD-00002, XWD-00003, XWD-00004, XWD-00005, XWD-00006; quantity resolutions 0; app-prijswaarden identiek: ja.
- Bundels: doc012_geometry_v3.json `fe12a4eb7999`, doc012_meppelweg_v3.json `748ebcbe53e8`, maldenhof_DOC-005_DOC-006_v3.json `b1ca1d196eb7`, maldenhof_expanded_v3.json `c78f387e66ce`, maldenhof_geometry_expanded_v3.json `8264bdceb2c0`.
