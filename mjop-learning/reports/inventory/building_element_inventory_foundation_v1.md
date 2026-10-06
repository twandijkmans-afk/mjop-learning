# Building Element Inventory Foundation v1

Status: **ANALYSE / FOUNDATION: geen besluiten, geen hoeveelheden, geen productiegedrag**. Alleen de twee bestaande testgebouwen: Maldenhof (DOC-005/006) en DOC-012 Meppelweg. Geen derde gebouw, geen Drawing Reader, geen vision-model, geen prijsactivatie.

Keten: BUILDING SCOPE → COMPONENT PRESENCE EVIDENCE → HUMAN COMPONENT DECISION → COMPONENT INVENTORY → COMPONENT QUANTITIES → MAINTENANCE TEMPLATES → PRICE. Deze milestone bouwt alleen de eerste vier stappen; presence is een ander concept dan quantity.

## A. Waarom de app ELEMENT_LIBRARY geen building inventory is

ELEMENT_LIBRARY (MJOP-App src/app.js) mengt drie concepten: fysieke bouwdelen waarop onderhoud plaatsvindt, onderhoud/service op die bouwdelen en ondersteunende kostenposten. Een post 'aanwezig' in de bibliotheek zegt dus niet dat het gebouw dat bouwdeel heeft: 'dakinspectie' is een service, 'steiger' een kostenpost, 'dakisolatie' een gebruikersgekozen verbetering, 'schilderwerk-buiten' hangt van materiaal/afwerking af. Daarom een aparte Building Element Inventory van FYSIEKE componenten.

Audit van MJOP-App `eaeb256` (24 elementen): ATTRIBUTE_DEPENDENT_MAINTENANCE 1, COMPONENT_SERVICE 1, OPTIONAL_IMPROVEMENT 1, PHYSICAL_COMPONENT_MAINTENANCE 20, SUPPORT_SERVICE 1. Hoeveelheidsbron: autoKozijn (KOZ_FACTOREN) 1, dakM2 2, dakPlatM2 1, dakSchuinM2 1, gevelM2 4, none 1, units 14. Sinds snapshot 1afdeca heeft de app voor gevel-metselwerk en voegwerk het veld 'benadering: true' gekregen (Missingness Safety / Price Source Labels); verder is ELEMENT_LIBRARY ongewijzigd. De MJOP-App is niet aangepast.

| app-element | klasse | activatie | vereist | vereist één van | bron |
|---|---|---|---|---|---|
| dak-plat | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | ROOF_FLAT_COVERING | — | dakPlatM2 |
| dakgoten | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | RAINWATER_DRAINAGE | — | units |
| dakinspectie | COMPONENT_SERVICE | PRESENCE_DRIVEN_ANY | — | ROOF_FLAT_COVERING, ROOF_SLOPED_COVERING | dakM2 |
| dak-hellend | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | ROOF_SLOPED_COVERING | — | dakSchuinM2 |
| dakisolatie | OPTIONAL_IMPROVEMENT | USER_SELECTED | — | — | dakM2 |
| gevel-metselwerk | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | FACADE_MASONRY | — | gevelM2 |
| schilderwerk-buiten | ATTRIBUTE_DEPENDENT_MAINTENANCE | PRESENCE_AND_ATTRIBUTE | — | EXTERIOR_FRAME, FACADE_CLADDING | gevelM2 |
| kozijnen-onderhoud | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | EXTERIOR_FRAME | — | autoKozijn (KOZ_FACTOREN) |
| steiger | SUPPORT_SERVICE | NOT_PRESENCE_DRIVEN | — | — | gevelM2 |
| voegwerk | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | FACADE_MASONRY | — | gevelM2 |
| balkonhekken | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | BALCONY_RAILING | — | units |
| intercom | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | INTERCOM_INSTALLATION | — | units |
| riolering | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | SEWERAGE_DRAINAGE_INTERNAL | — | units |
| elektra | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | COMMON_ELECTRICAL_INSTALLATION | — | units |
| verlichting | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | COMMON_LIGHTING | — | units |
| waterleiding | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | COMMON_WATER_INSTALLATION | — | units |
| brandveiligheid | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | FIRE_SAFETY_INSTALLATION | — | units |
| cv-installatie | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | COLLECTIVE_HEATING_INSTALLATION | — | units |
| ventilatie | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | VENTILATION_INSTALLATION | — | units |
| lift | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | LIFT_INSTALLATION | — | none |
| trappenhuis | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | COMMON_STAIRWELL_ENTRANCE | — | units |
| vloerafwerking | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | COMMON_FLOOR_FINISH | — | units |
| bestrating | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | SITE_PAVING | — | units |
| fietsenstalling | PHYSICAL_COMPONENT_MAINTENANCE | PRESENCE_DRIVEN_ALL | BICYCLE_STORAGE | — | units |

## B. Component-vocabulaire

22 fysieke componenttypes (`vocabularies/building_component_types_v1.json`). Eigen beschrijvende ids; geen claim dat dit of de interne element_code-codes officiële NL-SfB zijn.

| component | categorie | NL | hint |
|---|---|---|---|
| ROOF_FLAT_COVERING | ROOF | Dakbedekking plat dak | 27.1 |
| ROOF_SLOPED_COVERING | ROOF | Dakbedekking hellend dak | 27.2 |
| RAINWATER_DRAINAGE | ROOF | Hemelwaterafvoer (goten en afvoeren) | 27.3/52 |
| FACADE_MASONRY | FACADE | Gevel metselwerk | 21.1 |
| FACADE_CLADDING | FACADE | Gevelbekleding | 41 |
| EXTERIOR_FRAME | OPENINGS | Buitenkozijn | 31.2 |
| EXTERIOR_WINDOW | OPENINGS | Buitenraam / beglazing | 31.3 |
| EXTERIOR_DOOR | OPENINGS | Buitendeur | 31.4 |
| BALCONY_RAILING | BALCONY | Balkonhekwerk / balustrade | 34.1 |
| LIFT_INSTALLATION | SERVICES | Liftinstallatie | 59/66 |
| INTERCOM_INSTALLATION | SERVICES | Intercom-/video-deuropener-installatie | 64/66 |
| VENTILATION_INSTALLATION | SERVICES | Ventilatie-installatie (mechanisch) | 57 |
| COMMON_ELECTRICAL_INSTALLATION | SERVICES | Elektrische installatie gemeenschappelijk | 62/63 |
| COMMON_LIGHTING | SERVICES | Verlichting gemeenschappelijke ruimten/buiten | 63/64 |
| COMMON_WATER_INSTALLATION | SERVICES | Waterinstallatie gemeenschappelijk | 53 |
| SEWERAGE_DRAINAGE_INTERNAL | SERVICES | Binnenriolering | 52 |
| COLLECTIVE_HEATING_INSTALLATION | SERVICES | Collectieve verwarmingsinstallatie | 51/56 |
| FIRE_SAFETY_INSTALLATION | SERVICES | Brandveiligheidsvoorzieningen | 67 |
| COMMON_STAIRWELL_ENTRANCE | INTERIOR | Trappenhuis en entree | 42/43 |
| COMMON_FLOOR_FINISH | INTERIOR | Vloerafwerking gemeenschappelijke ruimten | 43 |
| SITE_PAVING | SITE | Bestrating/terreinverharding | 81/89/90 |
| BICYCLE_STORAGE | SITE | Fietsenstalling en bergingen | 89 |

Geen componenten: SCAFFOLDING_OR_ACCESS_EQUIPMENT (Steiger/hoogwerker is een ondersteunende kostenpost (SUPPORT_SERVICE), geen bouwdeel.); ROOF_INSULATION_IMPROVEMENT (Dakisolatie na-isoleren is een gebruikersgekozen verbetering (OPTIONAL_IMPROVEMENT); aanwezigheid van een dak activeert het niet.); PAINTING (Schilderwerk is onderhoud op een bouwdeel (afhankelijk van materiaal/afwerking), geen bouwdeel.); ROOF_INSPECTION (Dakinspectie is een service op een dak; geen bouwdeel.)

## C. Mapping app-element → vereiste componenten

Volledige tabel in sectie A; vastgelegd in `vocabularies/app_element_requirements_v1.json`. Steiger = SUPPORT_SERVICE (niet presence-driven); dakisolatie = OPTIONAL_IMPROVEMENT (gebruikersgekozen); schilderwerk-buiten = ATTRIBUTE_DEPENDENT (component + materiaal/afwerking). Geen productiegedrag gewijzigd; geen automatische activatie of verwijdering.

## D. Evidence-model

Schema `schemas/component_presence_evidence.schema.json`; id: CPE-<sha256(canonieke inhoud)[:16]> (content-addressed).

- Stilte: Niet gevonden in oud MJOP / niet zichtbaar op foto / niet getekend != ABSENT. Zulke stilte levert geen evidence op; de component blijft 'unknown'. ABSENT vereist een expliciete absence_basis (expliciete nulwaarde of expliciete bronuitspraak) en is altijd REVIEW_REQUIRED.
- Ontbrekend: Ontbrekend 3D BAG-veld = UNKNOWN (GEOMETRY_FIELD_MISSING), nooit ABSENT en nooit 0.
- Historische hoeveelheid: Een historische hoeveelheid bij een expliciete bronregel blijft HISTORICAL_REPORTED_QUANTITY_CONTEXT in details.historical_reported_quantity_context; ze is nooit geometrie, raamopening, kozijnoppervlak, schilderoppervlak of aantal.
- Stand: 64 records; per assertion {'ABSENT': 1, 'PRESENT': 63}; per bron {'3D_BAG': 32, 'MJOP': 32}; per status {'PROPOSED': 57, 'REVIEW_REQUIRED': 7}.

## E. Menselijk besluitmodel

Schema `schemas/component_presence_decision.schema.json`, store `data/component_presence/component_presence_decision_records.json` (2 records; **2 ACTIVE besluiten**; alleen EXTERIOR_FRAME-presence is besloten, zie Frame Inventory Foundation v1).

- append-only (alleen status ACTIVE -> SUPERSEDED / REVIEW_REQUIRED)
- per sleutel hoogstens één ACTIVE record
- geen meerderheidstem, geen middeling, geen automatische winnaar
- PRESENT/ABSENT vereisen overwogen evidence; menselijke kennis zonder document eerst als MANUAL-evidence
- komt er evidence bij na een besluit, dan wordt de component DECISION_REVIEW_REQUIRED

## F. Maldenhof — voorgestelde inventaris

Gebouwscope `BAG:0363100012070344+0363100012071880+0363100012078022+03631…` · documenten DOC-005, DOC-006 · 15 bevestigd(e) pand(en). Geen menselijk besluit: alles is PROPOSED of unknown.

Telling: confirmed 1, proposed 8, proposed_absent 0, absent 0, unknown 13, review_required 0.

| component | staat | 3D BAG per pand | MJOP-documenten | materiaal (zoals gerapporteerd) | review-evidence |
|---|---|---|---|---|---|
| EXTERIOR_FRAME | CONFIRMED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | hout | 1 |
| BALCONY_RAILING | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | staal | 0 |
| COMMON_LIGHTING | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | — | 2 |
| FACADE_CLADDING | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | hout | 0 |
| FACADE_MASONRY | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | metselwerk | 0 |
| RAINWATER_DRAINAGE | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | pvc, staal, zink | 0 |
| ROOF_FLAT_COVERING | PROPOSED_PRESENT | 3D BAG: 15 aanwezig / 0 afwezig / 0 onbekend van 15 | DOC-005, DOC-006 | — | 0 |
| ROOF_SLOPED_COVERING | PROPOSED_PRESENT | 3D BAG: 15 aanwezig / 0 afwezig / 0 onbekend van 15 | DOC-005, DOC-006 | — | 0 |
| SITE_PAVING | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-005, DOC-006 | — | 0 |

Unknown (geen enkel bewijs; stilte is geen afwezigheid): BICYCLE_STORAGE, COLLECTIVE_HEATING_INSTALLATION, COMMON_ELECTRICAL_INSTALLATION, COMMON_FLOOR_FINISH, COMMON_STAIRWELL_ENTRANCE, COMMON_WATER_INSTALLATION, EXTERIOR_DOOR, EXTERIOR_WINDOW, FIRE_SAFETY_INSTALLATION, INTERCOM_INSTALLATION, LIFT_INSTALLATION, SEWERAGE_DRAINAGE_INTERNAL, VENTILATION_INSTALLATION.

## G. DOC-012 — voorgestelde inventaris

Gebouwscope `BAG:0518100000354752` · documenten DOC-012 · 1 bevestigd(e) pand(en). Geen menselijk besluit: alles is PROPOSED of unknown.

Telling: confirmed 1, proposed 8, proposed_absent 1, absent 0, unknown 12, review_required 0.

| component | staat | 3D BAG per pand | MJOP-documenten | materiaal (zoals gerapporteerd) | review-evidence |
|---|---|---|---|---|---|
| EXTERIOR_FRAME | CONFIRMED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | hout | 0 |
| COLLECTIVE_HEATING_INSTALLATION | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | — | 0 |
| COMMON_LIGHTING | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | — | 1 |
| COMMON_WATER_INSTALLATION | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | — | 1 |
| FACADE_MASONRY | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | metselwerk | 0 |
| LIFT_INSTALLATION | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | — | 0 |
| RAINWATER_DRAINAGE | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | — | 0 |
| ROOF_FLAT_COVERING | PROPOSED_PRESENT | 3D BAG: 1 aanwezig / 0 afwezig / 0 onbekend van 1 | DOC-012 | — | 1 |
| SITE_PAVING | PROPOSED_PRESENT | scope-brede bron (geen 3D BAG-regel) | DOC-012 | — | 0 |
| ROOF_SLOPED_COVERING | PROPOSED_ABSENT | 3D BAG: 0 aanwezig / 1 afwezig / 0 onbekend van 1 | — | — | 1 |

Unknown (geen enkel bewijs; stilte is geen afwezigheid): BALCONY_RAILING, BICYCLE_STORAGE, COMMON_ELECTRICAL_INSTALLATION, COMMON_FLOOR_FINISH, COMMON_STAIRWELL_ENTRANCE, EXTERIOR_DOOR, EXTERIOR_WINDOW, FACADE_CLADDING, FIRE_SAFETY_INSTALLATION, INTERCOM_INSTALLATION, SEWERAGE_DRAINAGE_INTERNAL, VENTILATION_INSTALLATION.

## H. Kozijn-specifieke bevindingen

**Wat we weten**

- Maldenhof (DOC-005/006): 3120 'Kozijn buiten hout' (Alle gevels, hout) staat expliciet in beide MJOP's -> EXTERIOR_FRAME PRESENT, material_as_reported = hout (PROPOSED/REVIEW_REQUIRED, geen besluit).
- DOC-012: 3120 'Kozijn buiten hout' staat expliciet -> EXTERIOR_FRAME PRESENT (materiaal komt uit de omschrijving).
- Gevelmateriaal en kozijnmateriaal zijn alleen zoals gerapporteerd (hout); geen meting.

**Wat we niet weten**

- aantal kozijnen (FRAME_COUNT)
- raamopeningoppervlak (WINDOW_OPENING_AREA)
- schilderoppervlak (FRAME_PAINTING_AREA)
- verdeling over gevels/verdiepingen/subtypen (draai-kiep, vast, deur, dakkapel)
- of alle kozijnen hout zijn
- of EXTERIOR_WINDOW en EXTERIOR_DOOR als aparte componenten aanwezig zijn (geen expliciete bronregel)

**756,80 m²:** 756,80 m2 (Maldenhof) en 1296,59 m2 (DOC-012) zijn HISTORICAL_REPORTED_QUANTITY_CONTEXT: niet de raamopening, niet het fysieke kozijnoppervlak, niet het schilderoppervlak en niet het aantal kozijnen. Ze blijven bestaande, aparte historische quantity observations (QO-DOC-005-EL-007 e.d.).

**Facade PoC:** Facade PoC v2 (Maldenhof): openbare panorama's geven onvoldoende dekking voor een complete kozijnhoeveelheid (0 van 29 woningen met voldoende dekking; 41% van de buitengevel bevestigd zichtbaar); 756,8 m2 is volgens de PoC geen geldige benchmark (NOT_COMPARABLE). Geen accuracy-claim.

Relevante bronregels:

*DOC-005*

| observation | code | omschrijving | locatie | materiaal | hoeveelheid | rol |
|---|---|---|---|---|---|---|
| QO-DOC-005-EL-005 | 3120 | Betonband/latei | Alle gevels | — | 196,30 m1 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-005-EL-006 | 3120 | Raamdorpel gres/ijzerklinker | Alle gevels | — | 281,20 m1 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-005-EL-007 | 3120 | Kozijn buiten hout | Alle gevels | hout | 756,80 m2 | PRESENCE_EVIDENCE_EXTERIOR_FRAME |
| QO-DOC-005-EL-022 | 4631 | Buitenschilderwerk kozijn hout dekkend | Alle gevels | hout | 756,80 m2 | NOT_EXTERIOR_FRAME_PRESENCE |

*DOC-006*

| observation | code | omschrijving | locatie | materiaal | hoeveelheid | rol |
|---|---|---|---|---|---|---|
| QO-DOC-006-EL-005 | 3120 | Betonband/latei | Alle gevels | — | 196,30 m1 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-006-EL-006 | 3120 | Raamdorpel gres/ijzerklinker | Alle gevels | — | 281,20 m1 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-006-EL-007 | 3120 | Kozijn buiten hout | Alle gevels | — | 756,80 m2 | PRESENCE_EVIDENCE_EXTERIOR_FRAME |
| QO-DOC-006-EL-022 | 4631 | Buitenschilderwerk kozijn hout dekkend | Alle gevels | hout | 756,80 m2 | NOT_EXTERIOR_FRAME_PRESENCE |

*DOC-012*

| observation | code | omschrijving | locatie | materiaal | hoeveelheid | rol |
|---|---|---|---|---|---|---|
| QO-DOC-012-EL-006 | 3120 | Raamdorpel gres/ijzerklinker | — | — | 174,80 m1 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-012-EL-007 | 3120 | Kozijn buiten hout | — | — | 1296,59 m2 | PRESENCE_EVIDENCE_EXTERIOR_FRAME |
| QO-DOC-012-EL-008 | 3230 | Kozijnen hout | — | — | 129,36 m2 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-012-EL-020 | 4632 | Binnenschilderwerk kozijn en deuren hout dekkend trappenhuis en entree | — | — | 129,36 m2 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-012-EL-021 | 4634 | Buitenschilderwerk hek metaal ( achtergevel ) | — | — | 284,40 m2 | NOT_EXTERIOR_FRAME_PRESENCE |
| QO-DOC-012-EL-022 | 4634 | Buitenschilderwerk kozijn&raam hout transparant ( achtergevel ) | — | — | 824,00 m2 | NOT_EXTERIOR_FRAME_PRESENCE |

## I. Legacy appartementfactor

Classificatie **LEGACY_ESTIMATE_FALLBACK**. App-waarden: factoren [1, 0.25, 0.125, 0.125], minima [1, 0, 1, 0].

- niet verwijderd of gewijzigd in de MJOP-App (productiecode ongewijzigd)
- nooit canonical measured evidence
- later alleen gebruiken als er geen betere component-/instance-evidence is, en dan altijd als ESTIMATED zichtbaar
- de factor staat los van elke historische kozijnhoeveelheid (bijv. 756,80 m2)

Illustratie bij 29 appartementen (geen evidence): Draaiend raam 29, Vast glas 7, Deur 4, Dakkapel 4.

## J. Voorgesteld frame-instance-model (volgende milestone)

VOORSTEL voor de volgende milestone (niet geïmplementeerd; geen schema/store in deze milestone). FRAME_COUNT, WINDOW_OPENING_AREA en FRAME_PAINTING_AREA zijn verschillende hoeveelheden en worden nooit automatisch aan elkaar gelijkgesteld.

```json
{
 "component_type": "EXTERIOR_WINDOW",
 "subtype": "TURN_TILT",
 "material": "WOOD",
 "count": 8,
 "width": "1.20",
 "height": "1.50",
 "dimension_basis": "OPENING",
 "opening_area_m2": "14.40",
 "note": "Alleen een voorbeeld van de vorm; geen data van een echt gebouw."
}
```

Velden: `component_instance_id`, `building_id`, `bag_pand_id`, `component_type`, `facade_side`, `storey`, `subtype`, `material`, `count`, `width`, `height`, `opening_area_m2`, `dimension_basis`, `evidence_refs`, `repeat_group_id`, `status`, `source_type`, `method_class`.

## K. Repeat-group-model (volgende milestone)

VOORSTEL voor de volgende milestone (niet geïmplementeerd).

- alleen na menselijke bevestiging (USER_CONFIRMED_REPEAT)
- geen automatische symmetrie-aanname (ook geen spiegeling)
- geen patroon uit één pand stil over het hele complex kopiëren
- een afwijkend pand valt uit de groep of krijgt een expliciete afwijking
- een groep geldt per componenttype; bevestiging voor kozijnen zegt niets over daken of installaties

Kandidaat-groepen uit Facade PoC v2 (geen besluit): END_OF_ROW_1_ADDR (1), END_OF_ROW_2_ADDR (1), MIDDLE_2_ADDR (13).

## L. Menselijke besluiten voor de volgende milestone

| # | type | besluit | opties | aanbeveling |
|---|---|---|---|---|
| 1 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): BALCONY_RAILING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 2 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): COMMON_LIGHTING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 3 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): FACADE_CLADDING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 4 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): FACADE_MASONRY bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 5 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): RAINWATER_DRAINAGE bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 6 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): ROOF_FLAT_COVERING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 7 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): ROOF_SLOPED_COVERING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 8 | PRESENCE_DECISION | DOC-005+DOC-006 (15 panden): SITE_PAVING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 9 | PRESENCE_DECISION | DOC-012 (1 pand): COLLECTIVE_HEATING_INSTALLATION bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 10 | PRESENCE_DECISION | DOC-012 (1 pand): COMMON_LIGHTING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 11 | PRESENCE_DECISION | DOC-012 (1 pand): COMMON_WATER_INSTALLATION bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 12 | PRESENCE_DECISION | DOC-012 (1 pand): FACADE_MASONRY bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 13 | PRESENCE_DECISION | DOC-012 (1 pand): LIFT_INSTALLATION bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 14 | PRESENCE_DECISION | DOC-012 (1 pand): RAINWATER_DRAINAGE bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 15 | PRESENCE_DECISION | DOC-012 (1 pand): ROOF_FLAT_COVERING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 16 | PRESENCE_DECISION | DOC-012 (1 pand): SITE_PAVING bevestigen als aanwezig? | PRESENT / UNKNOWN | PRESENT |
| 17 | ABSENCE_DECISION | DOC-012 (1 pand): ROOF_SLOPED_COVERING afwezig verklaren op basis van een expliciete 3D BAG-nulwaarde? | ABSENT / UNKNOWN | UNKNOWN (3D BAG-geometrie is geen universeel bewijs; liefst bevestigen met foto/tekening) |
| 18 | RULE_APPROVAL | Zijn de presence-regels met inferentie acceptabel (hpr.common_lighting.armaturen, hpr.common_water.hydrofoor, hpr.roof_flat_covering.app_no_location)? | ACCEPT / REJECT / RESTRICT_TO_EXPLICIT | ACCEPT als REVIEW_REQUIRED-evidence |
| 19 | SEMANTIC_MAPPING | Is 'Deurbelinstallatie' (6411, DOC-012) een INTERCOM_INSTALLATION? | YES / NO / ADD_COMPONENT_TYPE_DOORBELL | NO |
| 20 | SEMANTIC_MAPPING | Welk bouwdeel is 'Standleidingen' (5240, DOC-012): binnenriolering of waterleiding? | SEWERAGE_DRAINAGE_INTERNAL / COMMON_WATER_INSTALLATION / NEITHER | geen mapping zonder bron |
| 21 | ATTRIBUTE_RULE | Welke kozijn-/gevelmaterialen maken 'schilderwerk-buiten' relevant? | WOOD / WOOD+STEEL / ALL_PAINTED_ONLY | WOOD+STEEL, alleen met materiaalbewijs |
| 22 | FRAME_MODEL | Instance-model voor kozijnen goedkeuren (granulariteit: pand x gevel x verdieping x subtype)? | APPROVE / COARSER / FINER | APPROVE |
| 23 | FRAME_QUANTITIES | FRAME_COUNT, WINDOW_OPENING_AREA en FRAME_PAINTING_AREA als drie aparte quantity-onderwerpen vastleggen? | YES / NO | YES |
| 24 | REPEAT_POLICY | Repeat groups alleen na expliciete bevestiging per componenttype en per pand? | YES / NO | YES |
| 25 | LEGACY_FALLBACK | Legacy kozijnfactor mag later alleen als zichtbare ESTIMATED-fallback zonder component-/instance-evidence? | YES / NO / REMOVE_LATER | YES |
| 26 | DRAWING_SOURCE | Welke vectortekening(en) gebruiken we voor de Vector Drawing Reader PoC (Maldenhof en/of Meppelweg)? | MALDENHOF / MEPPELWEG / BOTH | één gebouw eerst |

## Ongewijzigd

MJOP-App-productiecode, quantity bundles, quantity resolutions, crosswalk-besluiten, prijzen en building links zijn ongewijzigd; er zijn 0 presence-besluiten geschreven.

