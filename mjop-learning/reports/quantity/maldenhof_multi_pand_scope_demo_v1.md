# Maldenhof multi-pand scope demo v1 (read-only)

SOURCE COMPARISON, geen accuracy-benchmark. Niets opgeslagen; scope is een PREVIEW-hypothese, niet door een mens bevestigd.

## Canonieke snapshots (bag_snapshot_v1)

| Document | Snapshot | Opgehaald | Query | Requests | Adressen | Postcode = document | Kandidaat-panden |
|---|---|---|---|---|---|---|---|
| DOC-005 | BAGSNAP-431559474da45dcf | 2026-10-05T09:15:50Z | Maldenhof 240-296 Amsterdam | 97 | 56 | 29 | 40 |
| DOC-006 | BAGSNAP-e23aa139a8589881 | 2026-10-05T09:16:52Z | Maldenhof 240-296 Amsterdam | 97 | 56 | 29 | 40 |

DOC-006-snapshot: zelfde panden en dezelfde plat-dakwaarden als DOC-005: ja.

## Gebouwscope (PREVIEW, niet bevestigd): 15 panden, 29 adressen

Regel: panden waarvan alle adrespunten de documentpostcode (1106 EZ) hebben. building_id: `BAG:0363100012070344+0363100012071880+0363100012078022+0363100012091756+0363100012091974+0363100012102659+0363100012107492+0363100012121455+0363100012127361+0363100012134188+0363100012137996+0363100012140664+0363100012141419+0363100012143647+0363100012144766`. Overige kandidaat-panden in de snapshot (oneven zijde): 25.

| BAG-pand | Adressen | 3D BAG plat dak (m²) | Methode | Evidence (preview, niet opgeslagen) |
|---|---|---|---|---|
| 0363100012070344 | Maldenhof 262, Maldenhof 264 | 7.61 | DIRECT_MEASURED | QE-d4ced8c60e41bc4b |
| 0363100012071880 | Maldenhof 270, Maldenhof 272 | 8.8 | DIRECT_MEASURED | QE-eab79c35b96e5ab5 |
| 0363100012078022 | Maldenhof 246, Maldenhof 248 | 16.05 | DIRECT_MEASURED | QE-c7bfea612dc02224 |
| 0363100012091756 | Maldenhof 278, Maldenhof 280 | 8.27 | DIRECT_MEASURED | QE-71f72b28cc933ec8 |
| 0363100012091974 | Maldenhof 258, Maldenhof 260 | 14.56 | DIRECT_MEASURED | QE-59edcfebdefb3e2b |
| 0363100012102659 | Maldenhof 242, Maldenhof 244 | 10.55 | DIRECT_MEASURED | QE-aca817ad5a7c6abd |
| 0363100012107492 | Maldenhof 266, Maldenhof 268 | 15.99 | DIRECT_MEASURED | QE-e9e96dfac8f1bd20 |
| 0363100012121455 | Maldenhof 286, Maldenhof 288 | 18.04 | DIRECT_MEASURED | QE-db5575dbe0c47934 |
| 0363100012127361 | Maldenhof 294, Maldenhof 296 | 10.33 | DIRECT_MEASURED | QE-1645c97f228aef65 |
| 0363100012134188 | Maldenhof 290, Maldenhof 292 | 23.56 | DIRECT_MEASURED | QE-26a5c90b4e84589b |
| 0363100012137996 | Maldenhof 240 | 12.74 | DIRECT_MEASURED | QE-1532a5ed2efb07f8 |
| 0363100012140664 | Maldenhof 250, Maldenhof 252 | 16.31 | DIRECT_MEASURED | QE-bd83c103e6f0d61d |
| 0363100012141419 | Maldenhof 254, Maldenhof 256 | 9.38 | DIRECT_MEASURED | QE-c9f5b847e340d195 |
| 0363100012143647 | Maldenhof 282, Maldenhof 284 | 10.49 | DIRECT_MEASURED | QE-558a8eab4d516f4b |
| 0363100012144766 | Maldenhof 274, Maldenhof 276 | 7.97 | DIRECT_MEASURED | QE-aa7e067d4f0fbdd7 |

**Afgeleid complextotaal (3D BAG): 190.65 m2** — GEOMETRY_DERIVED, ELEMENT_QUANTITY, scope.sum_over_confirmed_panden v1.0.0, formule `SUM(child_evidence.value)`, 15 child evidence, ontbrekende panden: 0. Preview-ID QE-4d83681541ac35b3.

## Historisch MJOP (complexniveau)

| Observation | Document | Omschrijving | Locatie | Waarde | Pagina | Fragment |
|---|---|---|---|---|---|---|
| QO-DOC-005-EL-025 | DOC-005 | Dakbedekking APP | Platte dak | 425.80 m2 | 7 | `4711 Dakbedekking APP Platte dak 425,80m2 3` |
| QO-DOC-006-EL-025 | DOC-006 | Dakbedekking APP | Platte dak | 425.80 m2 | 7 | `4711 Dakbedekking APP Platte dak 425,80m2 1` |

- Niveau: COMPLEX (hele VvE-scope; niet over panden verdeeld).
- DOC-005 en DOC-006 zijn version_of_same_mjop (DREL-002): één historische bron, geen twee metingen.

## Naast elkaar (geen keuze)

| Plat dak | Waarde | Methode | Bron |
|---|---|---|---|
| Historisch MJOP | 425.80 m² | SOURCE_REPORTED | DOC-005 / DOC-006, complexniveau |
| 3D BAG | 190.65 m² | GEOMETRY_DERIVED | som van 15 panden (preview-scope) |

Verschil historisch − 3D BAG: 235.15 m² (123.34% van 3D BAG) — feitelijk verschil; geen fout van één bron, geen gemiddelde, geen winnaar.

## Definitie 3D BAG-veld

`b3_opp_dak_plat`: "Totale oppervlakte van de platte delen van het dak" (m2) — officiële 3DBAG-documentatie (attributenschema), aangeleverd door de gebruiker op 2026-10-05; niet opnieuw opgehaald vanuit de ontwikkelomgeving. Externe definitie van het 3D BAG-veld. GEEN bewijs dat een historische MJOP-regel (bijv. 'Dakbedekking APP / Platte dak') dezelfde scope heeft.

## Status mappings en resolutie

- HSM-ROOF_FLAT_AREA-4711-m2: PROPOSED
- XW-dak-plat-4711-m2: VERIFIED
- HSM-ROOF_SLOPED_AREA-4712-m2: PROPOSED
- XW-dak-hellend-4712-m2: REVIEW_REQUIRED
- XW-gevel-metselwerk-2110-m2: REVIEW_REQUIRED

Actuele stand van de menselijke besluiten (zie reports/quantity/maldenhof_quantity_activation_v1.md):

- building links (ACTIVE): 31 CONFIRMED, 50 REJECTED (menselijke besluiten; de preview-scope hierboven is zelf geen besluit)
- HSM-ROOF_FLAT_AREA-4711-m2: PROPOSED
- XW-dak-plat-4711-m2: VERIFIED
- quantity_resolution_records: 0 — een resolutie is altijd een menselijk besluit
