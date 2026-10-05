# DOC-012 Quantity Activation v1 (read-only)

Read-only. Menselijke besluiten staan in de append-only stores; geen quantity resolution, geen gemiddelde, geen winnaar.

## Scopebesluit

- Gekozen: **H1** — H1 = het volledige BAG-pand van het canonieke documentadres Meppelweg 819 (pand 0518100000354752: Meppelweg 803-883 oneven, 42 verblijfsobjecten), niet alleen de woning 819.
- H2_FULL_RANGE: **NOT_SELECTED** — De objectnaamrange omvat ook de even straatzijde met andere postcodes, twee gesloopte panden, nieuwbouw uit 2013 en niet-woonfuncties. Dit past niet bij de documentkenmerken. Het pand van het canonieke adres verklaart daarentegen zelfstandig de 42 verblijfsobjecten.
- geen building-link-records: de H2-panden zijn geen canonieke kandidaat (alleen read-only hypothese-opname).
- Gevel: 2110 metselwerk 1326.46 m2 blijft NEEDS_SEMANTIC_REVIEW t.o.v. OUTER_WALL_GROSS_AREA; geen relatie, mapping of bundelregel.

## Building link

| Link | Pand | Status | Snapshot | Reviewer |
|---|---|---|---|---|
| BLINK-00081 | 0518100000354752 | CONFIRMED (ACTIVE) | BAGSNAP-599d2f2004100011 | user-approved (human) |

building_id: `BAG:0518100000354752`

## Mapping

- XWD-00003 HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012: VERIFY (ACTIVE) — Exacte document-specifieke mapping voor DOC-012: code 4711, eenheid m2 en omschrijving 'Dakbedekking app'. De mapping geldt alleen voor QO-DOC-012-EL-024 en omvat niet de 4711-regels in m1 voor randstroken of dakrandafwerking.

## Evidence (PROPOSED)

| Evidence | Onderwerp | Waarde | Methode | Bron |
|---|---|---|---|---|
| QE-0ec156f03368047e | BUILDING_HEIGHT | 19.55500030517578 m | GEOMETRY_DERIVED | BAGSNAP-599d2f2004100011 |
| QE-d614bb24c23d1fab | OUTER_WALL_GROSS_AREA | 3048.46 m2 | DIRECT_MEASURED | BAGSNAP-599d2f2004100011 |
| QE-0cd5f153f2a60245 | ROOF_FLAT_AREA | 875.63 m2 | DIRECT_MEASURED | BAGSNAP-599d2f2004100011 |
| QE-f446e3716ff206e3 | ROOF_SLOPED_AREA | 0.0 m2 | DIRECT_MEASURED | BAGSNAP-599d2f2004100011 |
| QE-34190d144c6ca537 | ROOF_TOTAL_AREA | 875.63 m2 | GEOMETRY_DERIVED | BAGSNAP-599d2f2004100011 |
| QE-bd9ee7e3931f8b77 | ROOF_COVERING_REPORTED_AREA | 801.04 m2 | SOURCE_REPORTED | QO-DOC-012-EL-024 |

## Bronverschil (andere definitie; geen keuze)

- ROOF_COVERING_REPORTED_AREA 801.04 vs ROOF_FLAT_AREA 875.63: -74.59 (-8.5184%) — RELATED_SUBJECT_NOT_EQUIVALENT, NOT_RESOLVABLE_AS_SAME_QUANTITY

## Bundel `reports/quantity/app_bundles/doc012_meppelweg_v3.json`

mjop_app_quantity_bundle_v3, sha256 `748ebcbe53e83afc06fd4dba67467f1014d3cc88c728b55c56c3adfd33e0a191`, scope SINGLE_PAND (1 pand). Validator: GELDIG.

| App-element | Onderwerp | Rol | Kiesbaar | Waarde |
|---|---|---|---|---|
| dak-plat | ROOF_FLAT_AREA | PRIMARY | ja | 875.63 m2 |
| dak-plat | ROOF_COVERING_REPORTED_AREA | RELATED_CONTEXT | nee | 801.04 m2 |

Quantity resolution: 0 voor deze scope (totaal 0). Maldenhof-bundel sha256 `b1ca1d196eb720744ca7dc0fd2a71a59f350bf4dfa0ff2cde4f81fbe3a4a1933`.
