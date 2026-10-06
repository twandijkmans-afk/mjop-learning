# Maldenhof Rear Frame Annotation + Coverage Plan v1

Scope: adres->pand evidence voor Maldenhof 288/290, handmatige annotatie van de achterzijdefoto (foto 3), coverage matrix en captureplan. Foto 2 is bevroren (11 gewone kozijnen, 9 FULL / 2 PARTIAL, 1 deur PARTIAL). Geen building total, geen repeat-activatie, geen maten, geen painting area, geen quantity-resolutie, geen MJOP-App wijziging.

## 1. Maldenhof 288 en 290 naar BAG-pand

- Maldenhof 288: pand `0363100012121455` (adressen 286, 288); adresseerbaar object `0363010000900076`; building links BLINK-00008, BLINK-00048.
- Maldenhof 290: pand `0363100012134188` (adressen 290, 292); adresseerbaar object `0363010000900078`; building links BLINK-00010, BLINK-00050.

288 en 290 liggen in verschillende panden (same_pand = false); beide panden horen bij de 15 bevestigde Maldenhof-panden. Basis: de bestaande BAG-snapshots van DOC-005 en DOC-006 (identiek) en de mens-bevestigde building links; er is geen netwerkaanroep gedaan.

### Foto-2 instances en adres-scope

Geen van de 13 foto-2 instances is aan een pand toegewezen. Het adres->pand verband is bewezen, maar een opening aan een adres koppelen kan alleen als zij aantoonbaar bij dat adres hoort; de twee adreshints (FI-M2-012 bij 288 en de deur FI-M2-013 bij 290) volgen uit de ligging naast een huisnummerplaat en de pandgrens is niet in het evidence. Geen positional guessing. De instance-store is ongewijzigd. De mens kan beide hints later expliciet bevestigen.

| Instance | Kandidaat | Adreshint | Toewijzing | Kandidaat-pand ter bevestiging |
|---|---|---|---|---|
| FI-M2-012 | FC-M2-009 | Maldenhof 288 | NOT_ASSIGNED | `0363100012121455` |
| FI-M2-013 | FC-M2-011 | Maldenhof 290 | NOT_ASSIGNED | `0363100012134188` |

Overige 10 instances: geen adreshint, NOT_ASSIGNED.

## 2. Foto 3: handmatige annotatie (REAR_DETAIL)

Building scope Maldenhof, bag_pand_id = null, adres niet bewezen. Dezelfde counting unit als PR #35 (opening tussen bouwkundige scheidingen; kozijnstijl is geen opening). De bboxes zijn een eigen handmatige lezing door Claude, geen automatische detectie. Alle kandidaten zijn REVIEW_REQUIRED; er zijn geen instances.

### VISIBLE_COUNT_ON_PHOTO_3 (niet BUILDING_TOTAL)

| Categorie | Aantal | Kandidaten |
|---|---|---|
| FULL windows | 1 | 005 |
| PARTIAL windows | 1 | 003 |
| Exterior doors | 1 | 004 |
| Roof windows | 4 | 006, 007, 008, 009 |
| Dormer windows | 1 | 010 |
| Unknown openings | 2 | 001, 002 |

Totaal 10 kandidaten, 0 confirmed instances. Roof windows: 3 FULL, 1 PARTIAL.

Relation review REL-M3-001: de rode balkondeur (004) en het witte raam (005) staan onder een doorlopende kozijnbovenregel zonder metselwerk ertussen; of dit een raam-deurcombinatie (een opening) is, beslist de mens. Telt het als een opening, dan zijn er 2 raam/deur-openingen in plaats van 3.

Geen cross-photo deduplicatie: kandidaten van foto 3 (achterzijde) worden nooit met foto 2 (voorzijde) samengevoegd.

Overlay: `reports/frames/photo_review_rear_v1/maldenhof_3_frame_overlay.png`; sheet: `maldenhof_3_review_sheet.md`.

### Coverage gaps foto 3

- Begane grond: golfplaten overkapping en houten schutting verbergen de volledige begane grond; geen enkele opening op de begane grond is beoordeelbaar.
- Linkerhelft: palmbladeren, bloembakken en een houten scherm verbergen de openingen in de linker woning (candidates 001 en 002 zijn heavily occluded).
- Rechterrand: de kopgevel (zijgevel) is slechts als bakstenen wand zichtbaar, zonder zichtbare openingen; zijgevel niet gedekt.
- Opname van onderen met dakvlak dominant: de bovenste gevelrij onder de dakgoot is smal en schuin in beeld (bouwlagen niet vast te stellen).
- Foto 3 toont een deel van de achterzijde: de woningen links en rechts van de zichtbare delen zijn niet in beeld.
- Het exacte adres/pand van foto 3 is niet bewezen (geen huisnummers in beeld); bag_pand_id blijft null.

## 3. Repeat candidates (alleen kandidaten, multiplier null, active false)

- RC-M3-001 (SAME_REAR_ASSEMBLY_OR_MIRRORED): Beide woningen tonen een terugliggende bouwlaag met balkon onder een lager dakschild; mogelijk een gespiegeld/gelijk achtergeveltype. Zichtbare inhoud verschilt (kozijnindeling) en de linker woning is grotendeels afgedekt.
- RC-M3-002 (SAME_REAR_ROOF_WINDOW_PATTERN): Verspreide dakramen in het achterdakvlak; patroon niet regelmatig genoeg voor een module.

Alleen kandidaten; multiplier = null, active = false. Geen extrapolatie en geen koppeling aan de voorgevelmodules MOD-M2-A/B.

## 4. Historische data

756,80 m2 blijft NOT_COMPARABLE; geen ratio m2/ramen, geen m2 per frame.

## 5. Volgende stap

Menselijke review van de foto-3 kandidaten. Coverage matrix en captureplan: `reports/frames/maldenhof_frame_coverage_v1.md`.
