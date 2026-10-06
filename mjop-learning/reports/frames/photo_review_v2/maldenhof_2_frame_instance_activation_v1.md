# Maldenhof Frame Instance Activation v1 (incl. Counting Semantics Correction v1)

Scope: menselijke kandidaat-correctie en activatie van foto-gebaseerde frame instances voor maldenhof_2.jpg. Geen gebouwtotaal, geen maten, geen painting area, geen quantity-resolutie, geen repeat-activatie, geen MJOP-App wijziging.

## Counting unit

Een frame instance is een fysieke kozijn-/gevelopening tussen bouwkundige scheidingen. Meerdere raamvleugels binnen een onafgebroken kozijnopening zijn een instance; twee openingen gescheiden door metselwerk zijn twee instances. Niet iedere glasruit of draaivleugel apart.

## 1. Human candidate decisions (append-only)

| Decision | Target | Besluit | Reviewer |
|---|---|---|---|
| PCD-00001 | CANDIDATE FC-M2-001 | SPLIT_REQUIRED | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00002 | CANDIDATE FC-M2-002 | ACCEPT_DISTINCT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00003 | CANDIDATE FC-M2-003 | ACCEPT_DISTINCT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00004 | DUPLICATE_GROUP DUP-M2-001 | NOT_DUPLICATES | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00005 | CANDIDATE FC-M2-004 | ACCEPT_DISTINCT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00006 | CANDIDATE FC-M2-005 | ACCEPT_DISTINCT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00007 | DUPLICATE_GROUP DUP-M2-002 | NOT_DUPLICATES | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00008 | CANDIDATE FC-M2-006 | SPLIT_REQUIRED | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00009 | CANDIDATE FC-M2-007 | ACCEPT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00010 | CANDIDATE FC-M2-008 | ACCEPT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00011 | CANDIDATE FC-M2-009 | ACCEPT_FRAME | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00012 | CANDIDATE FC-M2-010 | REJECT | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00013 | CANDIDATE FC-M2-011 | ACCEPT_EXTERIOR_DOOR | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00014 | CANDIDATE FC-M2-012 | KEEP_UNKNOWN | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00015 | CANDIDATE FC-M2-013 | REJECT | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00016 | CANDIDATE FC-M2-014 | ACCEPT_PHOTO_OBSERVATION | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00017 | CANDIDATE FC-M2-015 | ACCEPT_PHOTO_OBSERVATION | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00018 | CANDIDATE FC-M2-016 | ACCEPT_PHOTO_OBSERVATION | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00019 | CANDIDATE FC-M2-017 | ACCEPT_PHOTO_OBSERVATION | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00020 | CANDIDATE FC-M2-018 | ACCEPT_PHOTO_OBSERVATION | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00021 | CANDIDATE FC-M2-019 | ACCEPT_PHOTO_OBSERVATION | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00022 | REPEAT_MODULE MOD-M2-A | DO_NOT_ACTIVATE_REPEAT_YET | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00023 | REPEAT_MODULE MOD-M2-B | DO_NOT_ACTIVATE_REPEAT_YET | human (user-approved), 2026-10-06T13:00:56Z |
| PCD-00024 | CHILD_CANDIDATES FC-M2-006-B+FC-M2-006-C | MERGE_AS_SINGLE_FRAME_OPENING | human (user-approved), 2026-10-06T13:32:03Z |

## 2. Corrected child candidates

Child bbox is een eigen handmatige visuele lezing van maldenhof_2.jpg door Claude (geen automatische detectie, geen foto-AI-model); de parent-bbox is niet overschreven.

| Child | Parent | Split decision | Visibility | Lifecycle | bbox_norm |
|---|---|---|---|---|---|
| FC-M2-001-A | FC-M2-001 | PCD-00001 | PARTIAL | ACTIVE | [0.2765, 0.348, 0.3275, 0.4067] |
| FC-M2-001-B | FC-M2-001 | PCD-00001 | FULL | ACTIVE | [0.345, 0.348, 0.375, 0.4067] |
| FC-M2-006-A | FC-M2-006 | PCD-00008 | FULL | ACTIVE | [0.859, 0.3587, 0.889, 0.4147] |
| FC-M2-006-B | FC-M2-006 | PCD-00008 | FULL | SUPERSEDED door FC-M2-006-BC (PCD-00024) | [0.8915, 0.3587, 0.946, 0.4147] |
| FC-M2-006-C | FC-M2-006 | PCD-00008 | FULL | SUPERSEDED door FC-M2-006-BC (PCD-00024) | [0.9465, 0.3587, 0.975, 0.4147] |
| FC-M2-006-BC | FC-M2-006 | PCD-00008 | FULL | ACTIVE | [0.8915, 0.3587, 0.975, 0.4147] |

FC-M2-006-B en FC-M2-006-C zijn na de counting-semantics-correctie SUPERSEDED door FC-M2-006-BC (zie sectie 3a); beide blijven met hun oorspronkelijke bbox bewaard. Bij FC-M2-001-B: de rechter opening is zichtbaar en niet door lantaarnpaal of boom afgedekt, daarom FULL; alleen de linker opening is PARTIAL.

## 3a. Counting semantics correction (PCD-00024)

De splitsing van FC-M2-006 in drie openingen (PCD-00008) was te ruim: de scheiding tussen de middenopening (B) en de rechter opening (C) is op de foto een kozijnstijl (mullion) binnen een onafgebroken kozijn en geen metselwerk. FC-M2-006-A blijft een afzonderlijke opening; B en C vormen samen een opening.

**Waarom een kozijnstijl geen bouwkundige scheiding is.** Een kozijnstijl is een onderdeel van het kozijn zelf: hij verdeelt een opening in vakken maar maakt geen nieuwe opening in de gevel. Een bouwkundige scheiding is metselwerk (een penant) of ander gevelvlak tussen twee openingen. De counting unit telt openingen tussen bouwkundige scheidingen, dus een stijl binnen een kozijn telt niet mee.

| Begrip | Wat het is | Telt als frame instance? |
|---|---|---|
| GLAZING / OPERABLE LEAF | glasvlak, draaiende of kierende vleugel binnen een kozijn | Nee: nooit per ruit of vleugel |
| MULLION (kozijnstijl) | verdeling binnen een onafgebroken kozijnopening | Nee: geen scheiding tussen instances |
| FRAME OPENING | fysieke kozijn-/gevelopening tussen bouwkundige scheidingen (metselwerk) | Ja: een instance per opening |

PCD-00008 en de oorspronkelijke child candidates en instances zijn niet verwijderd of overschreven; PCD-00024 supersedet PCD-00008 alleen voor de splitsing in B en C.

## 3. Duplicate groups

| Groep | Oorspronkelijke status (bewaard) | Menselijke resolutie |
|---|---|---|
| DUP-M2-001 (FC-M2-002, FC-M2-003) | DUPLICATE_REVIEW_REQUIRED | NOT_DUPLICATES (PCD-00004) |
| DUP-M2-002 (FC-M2-004, FC-M2-005) | DUPLICATE_REVIEW_REQUIRED | NOT_DUPLICATES (PCD-00007) |

## 4. Confirmed frame instances

| Instance | Kandidaat | Origin | Visibility | Material | Decision |
|---|---|---|---|---|---|
| FI-M2-001 | FC-M2-001-A | FC-M2-001 | PARTIAL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00001 |
| FI-M2-002 | FC-M2-001-B | FC-M2-001 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00001 |
| FI-M2-003 | FC-M2-002 | FC-M2-002 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00002 |
| FI-M2-004 | FC-M2-003 | FC-M2-003 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00003 |
| FI-M2-005 | FC-M2-004 | FC-M2-004 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00005 |
| FI-M2-006 | FC-M2-005 | FC-M2-005 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00006 |
| FI-M2-007 | FC-M2-006-A | FC-M2-006 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00008 |
| FI-M2-010 | FC-M2-007 | FC-M2-007 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00009 |
| FI-M2-011 | FC-M2-008 | FC-M2-008 | PARTIAL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00010 |
| FI-M2-012 | FC-M2-009 | FC-M2-009 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00011 |
| FI-M2-013 | FC-M2-011 | FC-M2-011 | PARTIAL | UNKNOWN (UNKNOWN) | PCD-00013 |
| FI-M2-014 | FC-M2-006-BC | FC-M2-006 | FULL | WOOD (SOURCE_REPORTED_BUILDING_LEVEL) | PCD-00024 |

Vervangen (SUPERSEDED, ongewijzigd bewaard in `superseded_instances`):

| Instance | Kandidaat | Vervangen door | Besluit |
|---|---|---|---|
| FI-M2-008 | FC-M2-006-B | FI-M2-014 | PCD-00024 |
| FI-M2-009 | FC-M2-006-C | FI-M2-014 | PCD-00024 |

Materiaal WOOD op de gewone kozijnen komt uit de historische MJOP-vermelding op gebouwniveau (material_as_reported hout, CPD-00001) en is niet per kozijn visueel bewezen. De deur heeft materiaal UNKNOWN.

## 5. PHOTO_VISIBLE counts (maldenhof_2.jpg, NIET BUILDING_TOTAL)

| Concept | Waarde |
|---|---|
| PHOTO_VISIBLE_FRAME_COUNT | 11 |
| PHOTO_VISIBLE_WINDOW_COUNT | 11 |
| PHOTO_VISIBLE_EXTERIOR_DOOR_COUNT | 1 |
| Gewone kozijnen FULL / PARTIAL | 9 / 2 |
| Deuren PARTIAL | 1 |

De actieve instances leveren 11 gewone gevelopeningen op (11 verwacht na de correctie; de stopregel is gecontroleerd). Voor de correctie waren dat er 12 (FI-M2-001..012). De verdeling FULL/PARTIAL volgt uit de visibility van de actieve instances.

Buiten de count: dakramen FC-M2-014..018 (aparte physical/maintenance context), dakkapelraam FC-M2-019 (aparte dakkapelraam-context, niet samengevoegd), afgewezen FC-M2-010 en FC-M2-013, FC-M2-012 KEEP_UNKNOWN. Geen van deze heeft een instance.

## 6. Building totals en quantity-status

FRAME_COUNT, WINDOW_COUNT en EXTERIOR_DOOR_COUNT als BUILDING_TOTAL = UNKNOWN. WINDOW_OPENING_AREA, FRAME_OUTER_AREA, FRAME_PAINTING_AREA en GLASS_AREA = UNKNOWN: geen maten en geen foto-schaal. Geen quantity_resolution record. 756,80 blijft NOT_COMPARABLE (historische context).

## 7. Repeat modules

MOD-M2-A en MOD-M2-B blijven REPEAT_CANDIDATE, active = false, multiplier = null. Besluit DO_NOT_ACTIVATE_REPEAT_YET. Geen x2, geen x13, geen extrapolatie.

## 8. Herleidbaarheid

parent candidate -> human split decision -> child candidates -> (eventuele human correction -> superseded children + merged child) -> confirmed frame instance; parent-evidence en superseded children/besluiten worden nooit overschreven of verwijderd.

Opslag: `data/photo_evidence/maldenhof_2_candidate_human_decisions_v1.json`, `data/photo_evidence/maldenhof_2_frame_candidates_corrected_v1.json`, `data/frame_inventory/maldenhof_photo_frame_instances_v1.json`. De bestaande annotatie en `frame_inventory_v1.json` zijn ongewijzigd.

## 9. Overlay

`reports/frames/photo_review_v2/maldenhof_2_frame_overlay_corrected.png`
