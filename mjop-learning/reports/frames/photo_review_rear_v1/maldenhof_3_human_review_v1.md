# Maldenhof foto 3: human review v1

Menselijke besluiten (reviewer_type human, user-approved) over de 10 kandidaten van `maldenhof_3.jpg` en relatiegroep REL-M3-001. Append-only register: `data/photo_evidence/maldenhof_3_candidate_human_decisions_v1.json`. Dit zijn **geen** frame instances.

## Status per kandidaat

| Kandidaat | Status | Type | Zichtbaarheid | Besluit |
|---|---|---|---|---|
| FC-M3-001 | KEEP_UNKNOWN | UNKNOWN_OPENING | HEAVILY_OCCLUDED | P3D-00001 |
| FC-M3-002 | KEEP_UNKNOWN | UNKNOWN_OPENING | HEAVILY_OCCLUDED | P3D-00002 |
| FC-M3-003 | ACCEPT_OBSERVATION | WINDOW | PARTIAL | P3D-00003 |
| FC-M3-004 | PART_OF_REL_M3_001_FRAME_OPENING | EXTERIOR_DOOR | PARTIAL | P3D-00004 |
| FC-M3-005 | PART_OF_REL_M3_001_FRAME_OPENING | WINDOW | FULL | P3D-00004 |
| FC-M3-006 | ACCEPT_PHOTO_OBSERVATION | ROOF_WINDOW | PARTIAL | P3D-00005 |
| FC-M3-007 | ACCEPT_PHOTO_OBSERVATION | ROOF_WINDOW | FULL | P3D-00006 |
| FC-M3-008 | ACCEPT_PHOTO_OBSERVATION | ROOF_WINDOW | FULL | P3D-00007 |
| FC-M3-009 | ACCEPT_PHOTO_OBSERVATION | ROOF_WINDOW | FULL | P3D-00008 |
| FC-M3-010 | ACCEPT_PHOTO_OBSERVATION | DORMER_WINDOW | FULL | P3D-00009 |

## REL-M3-001: raam-/deurcombinatie

Besluit P3D-00004: **SAME_FRAME_OPENING_WINDOW_DOOR_COMBINATION**. FC-M3-004 (rode balkondeur) en FC-M3-005 (wit raam) vormen **één** fysieke kozijnopening van subtype WINDOW_DOOR_COMBINATION; ze zijn niet als twee frame openings geteld.

- Semantische onderdelen: 1 raamsectie + 1 buitendeursectie.
- Toekomstige bijdragen (niet nu geactiveerd): FRAME_COUNT 1, WINDOW_COUNT 1, EXTERIOR_DOOR_COUNT 1. Dit zijn drie bijdragen van één opening, niet drie fysieke opening-instances.
- Materiaal: UNKNOWN voor de combinatie; geen visuele WOOD-claim.

## Dakramen en dakkapel

FC-M3-006..009 (dakramen) zijn geaccepteerde fotowaarnemingen en worden niet als gewone EXTERIOR_FRAME-instances geactiveerd. FC-M3-010 (dakkapelraam, parent DORMER-M3-001): het vijfdelige kozijn is één doorlopende kozijnopening; interne stijlen scheiden niet. Ook geen instance.

## Adres/BAG

bag_pand_id blijft `null`, address_scope `NOT_PROVEN`. Geen pandinferentie uit gelijkenis met foto 2, dakraampatroon, dakkapel, kopgevel of camerapositie.

## Niet gedaan

- Foto-3 frame instances: 0. Geen gecombineerd gebouwtotaal. Geen hoeveelheidsresolutie.
- Repeat candidates RC-M3-001/002 blijven REPEAT_CANDIDATE (inactief, multiplier null).
- Geen m2, geen painting area, geen BAG-koppeling, geen App-activatie. 756,80 m2 blijft NOT_COMPARABLE.
- Foto 2 ongewijzigd: FRAME 11, WINDOW 11, EXTERIOR_DOOR 1 (9 FULL / 2 PARTIAL).
