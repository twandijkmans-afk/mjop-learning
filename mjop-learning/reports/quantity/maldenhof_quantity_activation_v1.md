# Maldenhof Quantity Activation v1 (read-only)

Read-only. Menselijke besluiten zijn vastgelegd in de append-only stores; dit rapport beslist niets. Geen quantity resolution, geen gemiddelde, geen automatische winnaar.

## Building links (menselijk besluit)

| Document | Snapshot | CONFIRMED | REJECTED | Postcodes CONFIRMED | Postcodes REJECTED |
|---|---|---|---|---|---|
| DOC-005 | BAGSNAP-431559474da45dcf | 15 | 25 | 1106EZ | 1106EH, 1106EJ |
| DOC-006 | BAGSNAP-e23aa139a8589881 | 15 | 25 | 1106EZ | 1106EH, 1106EJ |

Gebouwscope (15 panden, gelijk voor DOC-005 en DOC-006: ja): `BAG:0363100012070344+0363100012071880+0363100012078022+0363100012091756+0363100012091974+0363100012102659+0363100012107492+0363100012121455+0363100012127361+0363100012134188+0363100012137996+0363100012140664+0363100012141419+0363100012143647+0363100012144766`

## Crosswalk-besluiten

| Besluit | Mapping | Uitkomst | Reviewer | Reden |
|---|---|---|---|---|
| XWD-00001 | XW-dak-plat-4711-m2 | VERIFY (ACTIVE) | user-approved (human) | De mapping koppelt het app-element 'Dakbedekking plat dak' aan interne elementcode 4711 voor m²-dakbedekking. Dit is een element/code-crosswalk. Deze beslissing verklaart NIET dat een historische 4711-m² hoeveelheid semantisch identiek is aan 3D BAG b3_opp_dak_plat. |
| XWD-00002 | HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006 | VERIFY (ACTIVE) | user-approved (human) | Aangemaakt en geactiveerd op expliciete instructie van de gebruiker (milestone Maldenhof Quantity Activation v1, secties 4 en 6, 2026-10-05): de 4711-m2-rij 'Dakbedekking APP' / 'Platte dak' van DOC-005 en DOC-006 is een door de bron gerapporteerde dakbedekkingsoppervlakte (ROOF_COVERING_REPORTED_AREA, SOURCE_REPORTED, complexniveau). Document-specifiek en exact; GEEN gelijkstelling met ROOF_FLAT_AREA (zie SREL-ROOF_COVERING_REPORTED_AREA-ROOF_FLAT_AREA). |

Effectieve status:

- XW-dak-plat-4711-m2: **VERIFIED**
- HSM-ROOF_FLAT_AREA-4711-m2: **PROPOSED**
- HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006: **VERIFIED**

## Twee onderwerpen, niet gelijkgesteld

- `ROOF_FLAT_AREA` — Plat dakoppervlak (3D BAG, geometrisch).
- `ROOF_COVERING_REPORTED_AREA` — Door bron/MJOP gerapporteerde oppervlakte dakbedekking (m2, ELEMENT_QUANTITY, SOURCE_REPORTED).
- Relatie `SREL-ROOF_COVERING_REPORTED_AREA-ROOF_FLAT_AREA`: **RELATED_NOT_EQUIVALENT**, zelfde bouwdeel (dak (plat dak)); resolveerbaar als dezelfde hoeveelheid: False; naast elkaar: True; verschil als: SOURCE_DIFFERENCE_DIFFERENT_DEFINITION; middelen: False; één resolutie: False; automatische winnaar: False.

## 3D BAG (ROOF_FLAT_AREA)

**190.65 m2** — QE-de5bcca75b309377, GEOMETRY_DERIVED, scope.sum_over_confirmed_panden v1.0.0, `SUM(child_evidence.value)`, 15 child evidence, ontbrekende panden: 0, status PROPOSED.

| BAG-pand | b3_opp_dak_plat (m²) | Evidence | Methode |
|---|---|---|---|
| 0363100012070344 | 7.61 | QE-c0a7a77dfed689d5 | DIRECT_MEASURED |
| 0363100012071880 | 8.8 | QE-d9c4c97864805d9e | DIRECT_MEASURED |
| 0363100012078022 | 16.05 | QE-4f17530f790bb48a | DIRECT_MEASURED |
| 0363100012091756 | 8.27 | QE-43d4e82529464339 | DIRECT_MEASURED |
| 0363100012091974 | 14.56 | QE-ea816e3de9336545 | DIRECT_MEASURED |
| 0363100012102659 | 10.55 | QE-2f34fe96853075ff | DIRECT_MEASURED |
| 0363100012107492 | 15.99 | QE-c618ae1068b0eaac | DIRECT_MEASURED |
| 0363100012121455 | 18.04 | QE-ecd6fb6a75c9673a | DIRECT_MEASURED |
| 0363100012127361 | 10.33 | QE-70c72e3009374da4 | DIRECT_MEASURED |
| 0363100012134188 | 23.56 | QE-95b0720f8dfbcbf7 | DIRECT_MEASURED |
| 0363100012137996 | 12.74 | QE-9cb6be219c2d4e6a | DIRECT_MEASURED |
| 0363100012140664 | 16.31 | QE-e58817976ce36ab2 | DIRECT_MEASURED |
| 0363100012141419 | 9.38 | QE-cf37ff666d79d716 | DIRECT_MEASURED |
| 0363100012143647 | 10.49 | QE-63f182348b77a77c | DIRECT_MEASURED |
| 0363100012144766 | 7.97 | QE-3ca9f54cb900191e | DIRECT_MEASURED |

## Historisch (ROOF_COVERING_REPORTED_AREA, complexniveau)

| Evidence | Document | Waarde | Methode | Pagina | Fragment | Broncluster | Zelfde object als |
|---|---|---|---|---|---|---|---|
| QE-cda20b77ca36b732 | DOC-005 | 425.80 m2 | SOURCE_REPORTED | 7 | `4711 Dakbedekking APP Platte dak 425,80m2 3` | SC-DOC-005+DOC-006 | DOC-006 |
| QE-5993359f27e8dea6 | DOC-006 | 425.80 m2 | SOURCE_REPORTED | 7 | `4711 Dakbedekking APP Platte dak 425,80m2 1` | SC-DOC-005+DOC-006 | DOC-005, DOC-014 |

Onafhankelijke historische bronnen (bronclusters): **1** — DOC-005 en DOC-006 tellen niet als twee waarnemingen.

## Bronverschil (andere definitie; geen keuze, geen statistiek)

| Document | Historisch | 3D BAG | Verschil | % | Soort | Status |
|---|---|---|---|---|---|---|
| DOC-005 | 425.80 (ROOF_COVERING_REPORTED_AREA) | 190.65 (ROOF_FLAT_AREA) | 235.15 | 123.3412 | RELATED_SUBJECT_NOT_EQUIVALENT | NOT_RESOLVABLE_AS_SAME_QUANTITY |
| DOC-006 | 425.80 (ROOF_COVERING_REPORTED_AREA) | 190.65 (ROOF_FLAT_AREA) | 235.15 | 123.3412 | RELATED_SUBJECT_NOT_EQUIVALENT | NOT_RESOLVABLE_AS_SAME_QUANTITY |

## App-bundel (preview, mjop_app_quantity_bundle_v3)

| App-element | Onderwerp | Rol | Kiesbaar | Waarde | Methode | Componenten |
|---|---|---|---|---|---|---|
| dak-plat | ROOF_COVERING_REPORTED_AREA | RELATED_CONTEXT | nee | 425.80 m2 | SOURCE_REPORTED | 0 |
| dak-plat | ROOF_COVERING_REPORTED_AREA | RELATED_CONTEXT | nee | 425.80 m2 | SOURCE_REPORTED | 0 |
| dak-plat | ROOF_FLAT_AREA | PRIMARY | ja | 190.65 m2 | GEOMETRY_DERIVED | 15 |

Niet weggeschreven (tenant-scheiding): de VvE exporteert zelf met scripts/export_app_quantity_bundle.py.

## Quantity resolution

- Records voor deze scope: 0 (totaal 0)
- ROOF_FLAT_AREA: UNRESOLVED (3D BAG-evidence PROPOSED)
- ROOF_COVERING_REPORTED_AREA: UNRESOLVED (historische context; niet resolveerbaar als dezelfde hoeveelheid als ROOF_FLAT_AREA)
