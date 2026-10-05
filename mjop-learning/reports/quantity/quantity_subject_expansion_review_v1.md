# Quantity Subject Expansion Review v1 (read-only)

Read-only readiness review. Geen VERIFY, geen relatie in de vocabulaire, geen bundel, geen resolutie. Voorstellen staan alleen in dit rapport.

App-elementenbibliotheek: `reports/quantity/subject_expansion_inputs/mjop_app_element_library_1afdeca.json` (MJOP-App `1afdeca`).

## A. Huidige quantity coverage

| Categorie | App-elementen |
|---|---|
| READY_NOW | 1 |
| READY_WITHOUT_HISTORICAL_CONTEXT | 3 |
| NEEDS_SEMANTIC_MAPPING | 3 |
| ESTIMATE_ONLY | 16 |
| NO_AUTOMATIC_QUANTITY | 1 |

## B. ROOF_SLOPED_AREA

- 3D BAG `b3_opp_dak_schuin` (bag3d.roof_sloped_area (DIRECT_MEASURED)); app-element `dak-hellend` gebruikt dezelfde bron en eenheid. Missingness: veld ontbreekt -> NOT_AVAILABLE (nooit 0); aanwezige 0 = geldige 0.
- Geometrie: **READY_WITHOUT_HISTORICAL_CONTEXT**.
- `XW-dak-hellend-4712-m2` (REVIEW_REQUIRED) koppelt app-element 'dak-hellend' (27.2, pannen) <-> interne code 4712 in m2, met quantity_subject ROOF_SLOPED_AREA.
  - A. element/code-koppeling: NIET VEILIG zoals hij nu is: 4712 is gemengd (dakpan, leisteen, shingles, zink; plus m1-randen). Alleen veilig als de koppeling wordt beperkt tot expliciete dakpan-omschrijvingen (4 van 8 m2-regels).
  - B. quantity-koppeling: NIET EQUIVALENT: gerapporteerd pannenoppervlak (MJOP) is niet het geometrische hellende dakoppervlak (3D BAG): overstekken, dakkapellen, goten, gemengde materialen en meetwijze verschillen. Hoogstens RELATED_NOT_EQUIVALENT via een apart historisch onderwerp.
  - A en B krijgen een verschillend oordeel; de bestaande mapping combineert ze en blijft dus REVIEW_REQUIRED.

Maldenhof (informatief, RELATED_NOT_EQUIVALENT): QO-DOC-005-EL-027 1485.60 m2 vs 3D BAG 1415.57 m2 → 70.03 (4.9%); QO-DOC-006-EL-027 1485.60 m2 vs 3D BAG 1415.57 m2 → 70.03 (4.9%).

**Voorstel (ACTIVATED_BY_USER_DECISION (Sloped Roof Quantity Activation v1; deze review blijft een momentopname)):** `ROOF_TILES_REPORTED_AREA` — Door bron/MJOP gerapporteerde oppervlakte dakpannen (m2, SOURCE_REPORTED); relatie `RELATED_NOT_EQUIVALENT` met ROOF_SLOPED_AREA. Een breder 'hellend-dak-bedekking'-onderwerp zou shingles, leisteen en zink samennemen met pannen; het app-element 'dak-hellend' is uitdrukkelijk 'pannen'. Mapping: per document exact (document_ids + 4712 + m2 + omschrijving exact uit SAFE_DAKPAN_REPORTED_AREA), zoals HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006. In aanmerking: QO-DOC-001-EL-041 (1944.00 m2), QO-DOC-005-EL-027 (1485.60 m2), QO-DOC-006-EL-027 (1485.60 m2), QO-DOC-013-EL-021 (12.72 m2); met bevestigd gebouw: QO-DOC-005-EL-027, QO-DOC-006-EL-027.

## C. ROOF_TOTAL_AREA

**INFRASTRUCTURE_ONLY** — Gebruikt als basis voor 'dakinspectie' (vast + per m²) en 'dakisolatie'; er is geen historische totaalwaarde om naast te zetten, dus geen bundel-/keuzefunctie nodig. Geen nieuw app-element.
- App-elementen op totaal dak: dakinspectie, dakisolatie.
- Historisch: geen: vocabulaire not_mapped ('Geen historische code voor totaal dakoppervlak; optellen van 4711 + 4712 zou aggregatie zijn').
- Definitie: ROOF_FLAT_AREA + ROOF_SLOPED_AREA (bag3d.roof_total_area, GEOMETRY_DERIVED); app dakM2 alleen bij beide velden.

## D. OUTER_WALL_GROSS_AREA

**PARTIAL: alleen 'steiger' is een directe geometrische toepassing; overige gevelposten zijn benaderingen**. Bron: b3_opp_buitenmuur (bruto: openingen niet afgetrokken) (`gevelM2`).

| App-element | Gebruik | Reden |
|---|---|---|
| steiger | DIRECT_GEOMETRY_USE | steiger/hoogwerker wordt per m² gevel geprijsd; bruto buitenmuur incl. openingen past |
| gevel-metselwerk | ESTIMATED_PROXY | metselwerkherstel = netto metselwerk; bruto muur overschat (ramen, deuren, ander gevelmateriaal). App toont nu bron '3D BAG', geen 'benadering' |
| voegwerk | ESTIMATED_PROXY | voegwerk = netto metselwerk; bruto muur is benadering; crosswalk NOT_SAFE |
| schilderwerk-buiten | NOT_SAFE | schilderwerk is kozijnen/houtwerk; al als ESTIMATED benadering gemarkeerd; crosswalk NOT_SAFE |

- Historisch: 2110 'Gevelconstructie metselwerk' is netto metselwerk — NIET OUTER_WALL_GROSS_AREA (vocabulaire not_mapped, ongewijzigd).
- Bevinding: 'gevel-metselwerk' en 'voegwerk' tonen bruto buitenmuur als bron '3D BAG' (niet als benadering), terwijl 'schilderwerk-buiten' al 'benadering' is. Productkeuze, geen missing-as-zero-bug: niet gewijzigd in deze milestone.

## E. BUILDING_HEIGHT

**CONTEXT_ONLY** — b3_h_dak_max - b3_h_maaiveld (bag3d.building_height, GEOMETRY_DERIVED, per pand, niet opgeteld). App: alleen als werkhoogte voor 'steiger' (tarief tot/boven 8 m); ontbreekt de hoogte, dan standaard 9 m (expliciete aanname).

## F. 4712-inventaris (m2)

Classificatie: AMBIGUOUS_4712 2, OTHER_SLOPED_ROOF_MATERIAL 2, SAFE_DAKPAN_REPORTED_AREA 4.

| Observation | Document | Omschrijving | Locatie | Waarde | Pagina/blok | Klasse | Reden |
|---|---|---|---|---|---|---|---|
| QO-DOC-001-EL-041 | DOC-001 | Dakpan beton | Daken | 1944.00 m2 | p.7 P07-L034 | SAFE_DAKPAN_REPORTED_AREA | expliciet 'dakpan', materiaal beton |
| QO-DOC-002-EL-103 | DOC-002 | dakpannen leisteen | Dak | 37.00 m2 | p.10 P10-L028 | OTHER_SLOPED_ROOF_MATERIAL | bron zegt 'dakpannen', maar het materiaal is leisteen (natuursteen); ander onderhoud dan beton-/keramische pannen — menselijke beoordeling |
| QO-DOC-005-EL-027 | DOC-005 | Dakpan beton | Hellend dak | 1485.60 m2 | p.7 P07-L015 | SAFE_DAKPAN_REPORTED_AREA | expliciet 'dakpan', materiaal beton |
| QO-DOC-006-EL-027 | DOC-006 | Dakpan beton | Hellend dak | 1485.60 m2 | p.7 P07-L009 | SAFE_DAKPAN_REPORTED_AREA | expliciet 'dakpan', materiaal beton |
| QO-DOC-010-EL-034 | DOC-010 | Dakbedekking zink | Dak lichtstraat | 0.78 m2 | p.7 P07-L019 | AMBIGUOUS_4712 | zink kan plat of hellend liggen; de bron zegt niet welk dakvlak; locatie 'Dak lichtstraat' |
| QO-DOC-013-EL-021 | DOC-013 | Dakpan keramisch | Dak | 12.72 m2 | p.7 P07-L006 | SAFE_DAKPAN_REPORTED_AREA | expliciet 'dakpan', materiaal keramisch |
| QO-DOC-013-EL-022 | DOC-013 | Dakbedekking shingles bitumen | Dak | 36.35 m2 | p.7 P07-L007 | OTHER_SLOPED_ROOF_MATERIAL | bitumen shingles: geen dakpan |
| QO-DOC-013-EL-023 | DOC-013 | Dakbedekking zink | Dak | 4.25 m2 | p.7 P07-L008 | AMBIGUOUS_4712 | zink kan plat of hellend liggen; de bron zegt niet welk dakvlak |

Buiten beschouwing (8 rijen in m1): QO-DOC-001-EL-042 Vorsten beton, QO-DOC-001-EL-043 Loodslab/loket hellend dak, QO-DOC-002-EL-102 Loodslab/loket hellend dak, QO-DOC-008-EL-006 Dakrandafwerking bitumen kraal/deklijst, QO-DOC-008-EL-007 Loodslabben plat dak, QO-DOC-009-EL-045 Dakrandafwerking bitumen kraal/deklijst, QO-DOC-009-EL-046 Loodslabben plat dak, QO-DOC-013-EL-024 Loodslab/loket hellend dak.

## G. App ELEMENT_LIBRARY coverage

| Element | Bron | Methode nu | Veilig onderwerp | Categorie | Toelichting |
|---|---|---|---|---|---|
| dak-plat | dakPlatM2 | DIRECT_MEASURED (3D_BAG) | ROOF_FLAT_AREA | READY_NOW | Plat dakoppervlak = 3D BAG b3_opp_dak_plat; XW-dak-plat-4711-m2 VERIFIED; echte bundels Maldenhof en DOC-012 met historische context (ROOF_COVERING_REPORTED_AREA, RELATED_NOT_EQUIVALENT). |
| dakgoten | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Rekent per appartement (BAG-aantal) als benadering van goten/HWA (m1); UNIT_MISMATCH in de crosswalk. |
| dakinspectie | dakM2 | GEOMETRY_DERIVED | ROOF_TOTAL_AREA | READY_WITHOUT_HISTORICAL_CONTEXT | Vast bedrag + € per m² totaal dakoppervlak; 3D BAG-som plat + hellend (GEOMETRY_DERIVED) alleen bij beide velden; geen historische 'totaal dak'-hoeveelheid. |
| dak-hellend | dakSchuinM2 | DIRECT_MEASURED (3D_BAG) | ROOF_SLOPED_AREA | READY_WITHOUT_HISTORICAL_CONTEXT | Geometrie is direct 3D BAG b3_opp_dak_schuin en missing-safe; historische context vraagt een apart onderwerp + smalle mapping (4712 is gemengd); XW-dak-hellend-4712-m2 staat op REVIEW_REQUIRED. |
| dakisolatie | dakM2 | GEOMETRY_DERIVED | ROOF_TOTAL_AREA? | NEEDS_SEMANTIC_MAPPING | Na-isoleren gaat over het te isoleren dakvlak; dat is niet zonder meer het totale 3D BAG-dakoppervlak (bijv. alleen plat dak, of al geïsoleerde delen). |
| gevel-metselwerk | gevelM2 | DIRECT_MEASURED (3D_BAG) | — | NEEDS_SEMANTIC_MAPPING | Gebruikt bruto buitenmuur (incl. ramen/deuren) als metselwerkoppervlak; de app toont dit nu als bron '3D BAG' i.p.v. als benadering. Historisch 2110 is netto metselwerk: niet OUTER_WALL_GROSS_AREA. |
| schilderwerk-buiten | gevelM2 | ESTIMATED (benadering van b3_opp_buitenmuur) | — | ESTIMATE_ONLY | Hele bruto buitenmuur als benadering (al als ESTIMATED gemarkeerd); schilderwerk gaat over kozijnen/houtwerk (46xx), niet over muuroppervlak. |
| kozijnen-onderhoud | — | ESTIMATED | — | ESTIMATE_ONLY | Aantallen = appartementen x vaste factor (1 / 0,25 / 0,125 / 0,125); geen telling. |
| steiger | gevelM2 | DIRECT_MEASURED (3D_BAG) | OUTER_WALL_GROSS_AREA | READY_WITHOUT_HISTORICAL_CONTEXT | Steiger/hoogwerker per m² gevel: bruto buitenmuur (incl. openingen) is de passende maat; werkhoogte komt uit 3D BAG-hoogte (of standaard 9 m). Menselijke bevestiging van deze koppeling nodig. |
| voegwerk | gevelM2 | DIRECT_MEASURED (3D_BAG) | — | NEEDS_SEMANTIC_MAPPING | Voegwerk gaat over metselwerk (netto, zonder openingen); bruto buitenmuur is een benadering. |
| balkonhekken | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als benadering van hekwerk (m1). |
| intercom | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement (BAG-aantal) als prijsbasis; geen hoeveelheidsonderwerp. |
| riolering | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Vast + per appartement als prijsbasis. |
| elektra | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Vast + per appartement als prijsbasis. |
| verlichting | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als benadering van het aantal armaturen. |
| waterleiding | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Vast + per appartement als prijsbasis. |
| brandveiligheid | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als prijsbasis. |
| cv-installatie | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Vast + per appartement als prijsbasis. |
| ventilatie | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als prijsbasis. |
| lift | none | geen automatische hoeveelheid | — | NO_AUTOMATIC_QUANTITY | bron 'none': vast bedrag. |
| trappenhuis | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als benadering van trappenhuisoppervlak. |
| vloerafwerking | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als benadering van vloeroppervlak. |
| bestrating | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Vast + per appartement als benadering van terreinoppervlak. |
| fietsenstalling | units | BAG (of MANUAL) | — | ESTIMATE_ONLY | Per appartement als prijsbasis. |

## H. Maldenhof / DOC-012

**Maldenhof** (`BAG:0363100012070344+0363100012071880+0363100012078022+03631…`, 15 pand(en))

| Onderwerp | Beschikbaar | Waarde | Methode | Compleet | App-kandidaat | Historische context |
|---|---|---|---|---|---|---|
| ROOF_FLAT_AREA | ja | 190.65 | GEOMETRY_DERIVED | ja | dak-plat | ROOF_COVERING_REPORTED_AREA 425.80 (DOC-006); ROOF_COVERING_REPORTED_AREA 425.80 (DOC-005) |
| ROOF_SLOPED_AREA | ja | 1415.57 | GEOMETRY_DERIVED | ja | dak-hellend | ROOF_TILES_REPORTED_AREA 1485.60 (DOC-005); ROOF_TILES_REPORTED_AREA 1485.60 (DOC-006); kandidaat QO-DOC-005-EL-027 Dakpan beton 1485.60 m2; kandidaat QO-DOC-006-EL-027 Dakpan beton 1485.60 m2 |
| ROOF_TOTAL_AREA | ja | 1606.22 | GEOMETRY_DERIVED | ja | dakinspectie, dakisolatie? | — |
| OUTER_WALL_GROSS_AREA | ja | 1747.35 | GEOMETRY_DERIVED | ja | steiger | NIET vergelijkbaar: QO-DOC-005-EL-001 Gevelconstructie metselwerk 1631.90 m2; NIET vergelijkbaar: QO-DOC-006-EL-001 Gevelconstructie metselwerk 1631.90 m2 |
| BUILDING_HEIGHT | ja | per pand (15 waarden; niet opgeteld) | GEOMETRY_DERIVED | ja | — | — |

**DOC-012 Meppelweg** (`BAG:0518100000354752`, 1 pand(en))

| Onderwerp | Beschikbaar | Waarde | Methode | Compleet | App-kandidaat | Historische context |
|---|---|---|---|---|---|---|
| ROOF_FLAT_AREA | ja | 875.63 | DIRECT_MEASURED | ja | dak-plat | ROOF_COVERING_REPORTED_AREA 801.04 (DOC-012) |
| ROOF_SLOPED_AREA | ja | 0.0 | DIRECT_MEASURED | ja | dak-hellend | — |
| ROOF_TOTAL_AREA | ja | 875.63 | GEOMETRY_DERIVED | ja | dakinspectie, dakisolatie? | — |
| OUTER_WALL_GROSS_AREA | ja | 3048.46 | DIRECT_MEASURED | ja | steiger | NIET vergelijkbaar: QO-DOC-012-EL-001 Gevelconstructie metselwerk 1326.46 m2 |
| BUILDING_HEIGHT | ja | 19.55500030517578 | GEOMETRY_DERIVED | ja | — | — |

## I. Aanbevolen volgende activaties

1. **ROOF_SLOPED_AREA-geometrie voor 'dak-hellend' (zonder historische context)** — direct 3D BAG-veld, zelfde eenheid, missing-safe, bestaande pipeline/bundel v3, handmatig overschrijfbaar; beide gebouwen hebben een complete waarde (Maldenhof 1415.57 m2 als scope-som, DOC-012 een gemeten 0.0). Nodig: menselijk besluit over XW-dak-hellend (zie J): de huidige 4712-brede koppeling is niet veilig.
2. **historische dakpannen-context (ROOF_TILES_REPORTED_AREA, RELATED_NOT_EQUIVALENT) — eerst Maldenhof** — Maldenhof DOC-005/DOC-006 'Dakpan beton / Hellend dak' 1485.60 m2 is expliciet; zelfde patroon als plat dak. Nodig: subject + relatie goedkeuren; document-specifieke mapping VERIFY; smalle XW-koppeling.
3. **OUTER_WALL_GROSS_AREA alleen voor 'steiger' (bruto gevel = steigeroppervlak)** — enige gevelpost waar bruto buitenmuur de bedoelde maat is; geen historische context nodig. Nodig: menselijke bevestiging dat steiger per m² bruto gevel geprijsd wordt; (apart) besluit of 'gevel-metselwerk'/'voegwerk' als benadering gemarkeerd moeten worden.

## J. Menselijke beslissingen

- 1. ROOF_TILES_REPORTED_AREA als nieuw historisch onderwerp + relatie RELATED_NOT_EQUIVALENT met ROOF_SLOPED_AREA: goedkeuren of afwijzen.
- 2. XW-dak-hellend-4712-m2: REJECT (te breed) en vervangen door een smalle koppeling 'dak-hellend' <-> 4712 m2 alleen voor expliciete dakpan-omschrijvingen — of de bestaande laten staan op REVIEW_REQUIRED.
- 3. Voor Maldenhof: document-specifieke mapping DOC-005/DOC-006 'Dakpan beton' / 'Hellend dak' (QO-DOC-005-EL-027, QO-DOC-006-EL-027) naar ROOF_TILES_REPORTED_AREA: VERIFY of REJECT.
- 4. 'dakpannen leisteen' (DOC-002): telt leisteen als 'pannen' voor dak-hellend? (nu OTHER_SLOPED_ROOF_MATERIAL).
- 5. ROOF_TOTAL_AREA: bevestigen als INFRASTRUCTURE_ONLY (geen keuzebron in de app).
- 6. OUTER_WALL_GROSS_AREA: koppeling met 'steiger' bevestigen; besluiten of 'gevel-metselwerk' en 'voegwerk' als benadering (ESTIMATED) getoond moeten worden (MJOP-App-wijziging).
- 7. BUILDING_HEIGHT: bevestigen als CONTEXT_ONLY.

Stand: crosswalk-besluiten XWD-00001, XWD-00002, XWD-00003, XWD-00004, XWD-00005, XWD-00006; building links 81; quantity resolutions 0; bundels ongewijzigd: doc012_meppelweg_v3.json ja, maldenhof_DOC-005_DOC-006_v3.json ja.
