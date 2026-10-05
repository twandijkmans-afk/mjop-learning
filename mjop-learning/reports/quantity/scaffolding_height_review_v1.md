# Scaffolding height review v1

Read-only, uit de canonieke evidence. Tariefklasse volgens de huidige app-regel (werkhoogte = gebouwhoogte op 0,1 m en dan op hele meters; > 8 m -> EUR 11/m2, anders EUR 6/m2). Geen nieuwe tarieven, geen indexatie, geen netwerk.

## DOC-005 + DOC-006 — MULTI_PAND_SCOPE, 15 pand(en)

| BAG pand | OUTER_WALL_GROSS_AREA (m2) | BUILDING_HEIGHT (m) | werkhoogte app | tariefklasse | EUR/m2 |
|---|---:|---:|---:|---|---:|
| 0363100012070344 | 100.84 | 12.175 | 12 | > 8 m | 11 |
| 0363100012071880 | 132.64 | 12.187 | 12 | > 8 m | 11 |
| 0363100012078022 | 99.61 | 12.143 | 12 | > 8 m | 11 |
| 0363100012091756 | 99.06 | 12.159 | 12 | > 8 m | 11 |
| 0363100012091974 | 98.09 | 12.150 | 12 | > 8 m | 11 |
| 0363100012102659 | 150.33 | 12.164 | 12 | > 8 m | 11 |
| 0363100012107492 | 103.5 | 12.247 | 12 | > 8 m | 11 |
| 0363100012121455 | 101.13 | 12.110 | 12 | > 8 m | 11 |
| 0363100012127361 | 197.42 | 12.127 | 12 | > 8 m | 11 |
| 0363100012134188 | 116.45 | 12.095 | 12 | > 8 m | 11 |
| 0363100012137996 | 118.32 | 9.444 | 9 | > 8 m | 11 |
| 0363100012140664 | 99.35 | 12.138 | 12 | > 8 m | 11 |
| 0363100012141419 | 106.74 | 12.137 | 12 | > 8 m | 11 |
| 0363100012143647 | 102.5 | 12.167 | 12 | > 8 m | 11 |
| 0363100012144766 | 121.37 | 12.121 | 12 | > 8 m | 11 |

- Totaal OUTER_WALL_GROSS_AREA: **1747.35 m2** (`QE-bbcbef41efede680`; som van de panden = totaal: ja).
- Hoogte min/max: 9.444 / 12.247 m. Panden per tariefklasse: > 8 m: 15.
- Eén tariefklasse: **ja**.
- A (foutgevoelig, scopetotaal x tarief van één planpand): EUR 19221.
- B (correct, som per pand): EUR 19221. A = B: ja.

## DOC-012 — SINGLE_PAND, 1 pand(en)

| BAG pand | OUTER_WALL_GROSS_AREA (m2) | BUILDING_HEIGHT (m) | werkhoogte app | tariefklasse | EUR/m2 |
|---|---:|---:|---:|---|---:|
| 0518100000354752 | 3048.46 | 19.555 | 20 | > 8 m | 11 |

- Totaal OUTER_WALL_GROSS_AREA: **3048.46 m2** (`QE-d614bb24c23d1fab`; som van de panden = totaal: ja).
- Hoogte min/max: 19.555 / 19.555 m. Panden per tariefklasse: > 8 m: 1.
- Eén tariefklasse: **ja**.
- A (foutgevoelig, scopetotaal x tarief van één planpand): EUR 33533.
- B (correct, som per pand): EUR 33533. A = B: ja.

## Generieke regel

- **SINGLE_PAND**: hoeveelheid OUTER_WALL_GROSS_AREA x tarief(werkhoogte van het pand)
- **MULTI_PAND_SAME_BAND**: scopetotaal OUTER_WALL_GROSS_AREA x gemeenschappelijk tarief
- **MULTI_PAND_MIXED_BANDS**: SOM(pand OUTER_WALL_GROSS_AREA x tarief(eigen BUILDING_HEIGHT)); geen gemiddelde hoogte, geen max-hoogte, geen stille fallback
- **MISSING_HEIGHT**: kosten onbekend / review required (nooit EUR 0, nooit een willekeurige hoogte)
- **carrier**: bundel v3 PRIMARY-regel steiger: optionele pricing_context met per pand BUILDING_HEIGHT-evidence-ref + waarde (geen schema-ophoging)

## Stand

- XQ-steiger-OUTER_WALL_GROSS_AREA-m2: VERIFIED (XWD-00006).
- BUILDING_HEIGHT product_role: CONTEXT_ONLY. Geverifieerde 2110-mappings: geen.
- Crosswalk-besluiten: XWD-00001, XWD-00002, XWD-00003, XWD-00004, XWD-00005, XWD-00006. Quantity resolutions: 0.
- Referentiebundels ongewijzigd: doc012_meppelweg_v3.json ja, maldenhof_DOC-005_DOC-006_v3.json ja, maldenhof_expanded_v3.json ja.
