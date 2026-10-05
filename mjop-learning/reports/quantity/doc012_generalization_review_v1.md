# Quantity Engine Generalization v1 — DOC-012 (review, read-only)

Read-only discovery + review. Geen building links, geen mapping-besluiten, geen quantity resolution, geen app-bundel. 3D BAG-waarden zijn PREVIEW (niet opgeslagen). Geen accuracy-claim.

Document: Meppelweg 819 · 2544 AW Den Haag · objectnaam "VvE Meppelweg 801-883" · bouwjaar 1956 · cluster SC-DOC-012

## A. Scope-hypotheses

| | Definitie | Query-bron | Canoniek | Opname | Adressen | Panden |
|---|---|---|---|---|---|---|
| H1 | scope = alleen het opgegeven adres Meppelweg 819 | `building.address` (p.2) | ja | `BAGSNAP-599d2f2004100011` | 1 | 1 |
| H2 | scope = huisnummerbereik Meppelweg 801-883 uit de objectnaam | `document_level_values.object_name` | **nee** | `BAGSNAP-68f484badbce9837` | 82 (41 oneven, 41 even) | 6 |

H2 is niet canoniek: bag_snapshot_v1 legt geen query-bron vast; een range uit de objectnaam is geen document-adres. In data/bag_snapshots zou 'building_links.py record' deze panden als kandidaat accepteren. Daarom alleen als read-only hypothese-opname (zelfde structuur, hash gecontroleerd).

Relatie: H1-pand ⊂ H2: True; alle oneven adressen van H2 liggen in het H1-pand: True; even zijde = 5 andere panden. H1-pand heeft 42 verblijfsobjecten; het document noemt Deurbelinstallatie 42.00 piece, Postkasten 42.00 piece.

## B. BAG-panden en adressen (H2 bevat H1)

| BAG-pand | In H1 | Huisnummers | Zijde | Postcodes | VBO (BAG) | Bouwjaar | Gebruiksdoel | Status | 3D BAG |
|---|---|---|---|---|---|---|---|---|---|
| 0518100000208891 | nee | 802–818 (11 adr.) | even | 2544BV | 8 | 1954 | woonfunctie | Pand gesloopt | nee |
| 0518100000219868 | nee | 802–820 (8 adr.) | even | 2544BV, GEEN | 8 | 1954 | woonfunctie | Pand gesloopt | nee |
| 0518100000243139 | nee | 882–882 (1 adr.) | even | GEEN | 1 | 2009 | overige gebruiksfunctie | Pand in gebruik | ja |
| 0518100000277993 | nee | 882–882 (1 adr.) | even | 2544BW | 1 | 1965 | bijeenkomstfunctie | Pand in gebruik | ja |
| 0518100000354752 | ja | 803–883 (41 adr.) | oneven | 2544AW, 2544AX | 42 | 1957 | woonfunctie | Pand in gebruik | ja |
| 0518100001631386 | nee | 802–820 (39 adr.) | even | 2544BV, GEEN | 177 | 2013 | industriefunctie,kantoorfunctie,overige gebruiksfunctie,woonfunctie | Pand in gebruik | ja |

Ambiguïteiten:

- Het adresveld noemt één adres (819); de objectnaam een bereik (801-883). Geen van beide is automatisch de scope.
- Het bereik 801-883 bevat in BAG beide straatzijden: oneven (2544AW/AX) en even (2544BV/BW, andere panden). De objectnaam zegt niets over even/oneven.
- Nummer(s) zonder BAG-adres in het bereik: 801, 822, 824, 826, 828 (o.a. 801 bestaat niet).
- Twee kandidaat-panden aan de even zijde hebben status 'Pand gesloopt' (bouwjaar 1954) en geen 3D BAG-object.
- Adressen met huisletter T (bijv. 820T, 882T) hebben in PDOK geen postcode.
- Bouwjaar document 1956 vs BAG 1957 voor het pand van Meppelweg 819.
- Woonplaats in het document is 'Den Haag'; BAG-woonplaatsnaam is 's-Gravenhage (expliciete alias WPA-den-haag).

## C. Historische hoeveelheden (51 observations)

Classificatie: DIRECTLY_COMPARABLE 0, RELATED_NOT_EQUIVALENT 1, NO_3DBAG_COUNTERPART 40, NEEDS_SEMANTIC_REVIEW 1, NOT_MEASURED_QUANTITY 9.

| Observation | Code | Omschrijving | Hoeveelheid | Klasse | Onderwerp / relatie | App-crosswalk |
|---|---|---|---|---|---|---|
| QO-DOC-012-EL-001 (p.6) | 2110 | Gevelconstructie metselwerk | 1326.46 m2 | NEEDS_SEMANTIC_REVIEW | OUTER_WALL_GROSS_AREA | XW-gevel-metselwerk-2110-m2 |
| QO-DOC-012-EL-024 (p.7) | 4711 | Dakbedekking app | 801.04 m2 | RELATED_NOT_EQUIVALENT | ROOF_COVERING_REPORTED_AREA ~ ROOF_FLAT_AREA | XW-dak-plat-4711-m2 |
| QO-DOC-012-EL-025 (p.7) | 4711 | Randstrook APP | 152.54 m1 | NO_3DBAG_COUNTERPART | — | — |
| QO-DOC-012-EL-026 (p.7) | 4711 | Dakrandafwerking aluminium trim | 152.54 m1 | NO_3DBAG_COUNTERPART | — | — |

Overige 47 observations: NO_3DBAG_COUNTERPART of NOT_MEASURED_QUANTITY (volledige lijst in de JSON).

## D. 3D BAG-preview H1 (1 pand(en); preview, niet opgeslagen)

| BAG-pand | ROOF_FLAT_AREA | ROOF_SLOPED_AREA | ROOF_TOTAL_AREA | OUTER_WALL_GROSS_AREA | BUILDING_HEIGHT |
|---|---|---|---|---|---|
| 0518100000354752 | 875.63 | 0.0 | 875.63 | 3048.46 | 19.55500030517578 |

## E. 3D BAG-preview H2 (6 pand(en); preview, niet opgeslagen)

| BAG-pand | ROOF_FLAT_AREA | ROOF_SLOPED_AREA | ROOF_TOTAL_AREA | OUTER_WALL_GROSS_AREA | BUILDING_HEIGHT |
|---|---|---|---|---|---|
| 0518100000208891 | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE |
| 0518100000219868 | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE | NOT_AVAILABLE |
| 0518100000243139 | 35.13 | 0.0 | 35.13 | 74.85 | 3.1520000100135805 |
| 0518100000277993 | 130.56 | 123.15 | 253.71 | 277.17 | 5.37899991869926484 |
| 0518100000354752 | 875.63 | 0.0 | 875.63 | 3048.46 | 19.55500030517578 |
| 0518100001631386 | 4172.83 | 186.74 | 4359.57 | 12700.49 | 51.64499853551387787 |
| **scope-som** | NOT_PUBLISHED | NOT_PUBLISHED | NOT_PUBLISHED | NOT_PUBLISHED | NOT_AGGREGATED |

NOT_PUBLISHED (ROOF_FLAT_AREA, ROOF_SLOPED_AREA, ROOF_TOTAL_AREA, OUTER_WALL_GROSS_AREA): ontbrekende pandwaarde(n) 0518100000208891, 0518100000219868 — een ontbrekende waarde telt nooit als 0.

## E2. Informatief: H2 alleen panden 'in gebruik' (4 pand(en); preview, niet opgeslagen)

| BAG-pand | ROOF_FLAT_AREA | ROOF_SLOPED_AREA | ROOF_TOTAL_AREA | OUTER_WALL_GROSS_AREA | BUILDING_HEIGHT |
|---|---|---|---|---|---|
| 0518100000243139 | 35.13 | 0.0 | 35.13 | 74.85 | 3.1520000100135805 |
| 0518100000277993 | 130.56 | 123.15 | 253.71 | 277.17 | 5.37899991869926484 |
| 0518100000354752 | 875.63 | 0.0 | 875.63 | 3048.46 | 19.55500030517578 |
| 0518100001631386 | 4172.83 | 186.74 | 4359.57 | 12700.49 | 51.64499853551387787 |
| **scope-som** | 5214.15 | 309.89 | 5524.04 | 16100.97 | NOT_AGGREGATED |

## F. Dakvergelijking (RELATED_NOT_EQUIVALENT — geen accuracy-claim)

| Hypothese | 3D BAG ROOF_FLAT_AREA | Status | Historisch (ROOF_COVERING_REPORTED_AREA) | Verschil | % |
|---|---|---|---|---|---|
| H1 | 875.63 | PREVIEW | 801.04 m2 | -74.59 | -8.5 |
| H2 | — | NOT_PUBLISHED | 801.04 m2 | — | — |
| H2_IN_USE_ONLY_INFORMATIVE | 5214.15 | PREVIEW | 801.04 m2 | -4413.11 | -84.6 |

RELATED_NOT_EQUIVALENT: naast elkaar, verschil tonen; geen accuracy-claim, geen gemiddelde, geen resolutie, geen winnaar.

4711 apart houden: Randstrook APP 152.54 m1 (NO_3DBAG_COUNTERPART); Dakrandafwerking aluminium trim 152.54 m1 (NO_3DBAG_COUNTERPART) — niet bij de dakbedekking optellen.

## G. Gevelvergelijking

| Hypothese | 3D BAG OUTER_WALL_GROSS_AREA | Status | Historisch 2110 metselwerk | Verschil |
|---|---|---|---|---|
| H1 | 3048.46 | PREVIEW | 1326.46 m2 | -1722.00 |
| H2 | — | NOT_PUBLISHED | 1326.46 m2 | — |
| H2_IN_USE_ONLY_INFORMATIVE | 16100.97 | PREVIEW | 1326.46 m2 | -14774.51 |

netto/gerapporteerd metselwerk (2110) is niet de bruto 3D BAG-buitenmuur; geen subject_relation vastgelegd -> NEEDS_SEMANTIC_REVIEW.

## H. Voorgestelde mappings (NIET geverifieerd)

- `HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012` → ROOF_COVERING_REPORTED_AREA (VERIFIED); exacte match {"document_ids": ["DOC-012"], "element_description_original_exact": ["Dakbedekking app"], "location_original_exact": [null]}; matcht: QO-DOC-012-EL-024

## I. App-readiness

- dak-plat (XW-dak-plat-4711-m2 VERIFIED): PRIMARY 3D BAG ROOF_FLAT_AREA (per pand DIRECT_MEASURED, of scope-aggregaat GEOMETRY_DERIVED); RELATED_CONTEXT historische dakbedekking 801.04 m2 (ROOF_COVERING_REPORTED_AREA, na VERIFY van de DOC-012-mapping).
  Niet meer geblokkeerd; bundel: `reports/quantity/app_bundles/doc012_meppelweg_v3.json`.
- dak-hellend: DOC-012 heeft geen 4712-rij; alleen 3D BAG ROOF_SLOPED_AREA zou beschikbaar zijn.
- gevel-metselwerk: geen gedeeld hoeveelheidsonderwerp (netto vs bruto).

## J. Generalisatie-audit

Gezocht naar: DOC-005, DOC-006, Maldenhof, 1106EZ, 1106 EZ, 190.65, 425.80, 15 panden in scripts/, tests/, vocabularies/, schemas/. GENERIC_CODE_PROBLEM_FIXED 1, NOT_A_PROBLEM 10, REPORT_ONLY 10, TEST_ONLY 20.

| Bestand | Klasse | Patronen | Toelichting |
|---|---|---|---|
| `scripts/backfill_element_codes.py` | NOT_A_PROBLEM | DOC-005, DOC-006, Maldenhof | PER_DOCUMENT_CONFIG: bronbestand per document (alle documenten, niet alleen Maldenhof) |
| `scripts/bag_snapshots.py` | NOT_A_PROBLEM | DOC-005, Maldenhof, 1106 EZ | DOCSTRING_EXAMPLE: CLI-voorbeelden en een docstring-voorbeeld ('Maldenhof 240 - 296') |
| `scripts/build_comparability.py` | NOT_A_PROBLEM | DOC-005 | COMMENT: herkomst van regel F7 |
| `scripts/building_links.py` | NOT_A_PROBLEM | DOC-005 | DOCSTRING_EXAMPLE: CLI-voorbeeld '--document DOC-005' |
| `scripts/decision_package_4645_interior_painting_wood.py` | NOT_A_PROBLEM | DOC-006 | DOCUMENT_SPECIFIC_DECISION_PACKAGE: vaste observation-ID's van een beslispakket |
| `scripts/deterministic_extraction.py` | NOT_A_PROBLEM | DOC-005, DOC-006 | PER_DOCUMENT_CONFIG: extractieprofiel per document (alle documenten) |
| `scripts/doc012_generalization_review.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof, 1106EZ, 1106 EZ, 190.65, 425.80, 15 panden | — |
| `scripts/doc012_quantity_activation.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof | — |
| `scripts/export_human_review_queue.py` | NOT_A_PROBLEM | DOC-005 | COMMENT: uitleg bij een regel |
| `scripts/facade_coverage_poc_v2.py` | REPORT_ONLY | DOC-005, Maldenhof, 15 panden | — |
| `scripts/facade_panorama_poc.py` | REPORT_ONLY | DOC-005, Maldenhof | — |
| `scripts/facade_poc_v2_report.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof, 15 panden | — |
| `scripts/maldenhof_quantity_activation.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof | — |
| `scripts/multi_pand_scope_demo.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof, 1106 EZ | — |
| `scripts/prepare_relation_review.py` | NOT_A_PROBLEM | DOC-005, DOC-006 | DOCSTRING_EXAMPLE: CLI-voorbeeld |
| `scripts/quantity_engine_activation_review.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof, 15 panden | — |
| `scripts/quantity_subject_expansion_review.py` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof | — |
| `scripts/record_relation_decision.py` | NOT_A_PROBLEM | DOC-006 | DOCSTRING_EXAMPLE: CLI-voorbeeld |
| `scripts/validate_app_quantity_bundle.py` | NOT_A_PROBLEM | DOC-005, DOC-006 | DOCSTRING_EXAMPLE: CLI-voorbeeld met het pad van de Maldenhof-bundel |
| `vocabularies/quantity_subjects_v1.json` | REPORT_ONLY | DOC-005, DOC-006, Maldenhof | — |
| `scripts/bag_snapshots.py` | GENERIC_CODE_PROBLEM_FIXED | — | exact_address_match/range-filter vergeleken de woonplaats uit het document letterlijk met de BAG-woonplaatsnaam; 'Den Haag' (DOC-012) vond daardoor zelfs het exacte adres niet ('s-Gravenhage). Opgelost met de expliciete aliaslijst vocabularies/woonplaats_aliases_v1.json (exacte gelijkheid, vastgelegd in de snapshot-query; bestaande snapshots ongewijzigd). |

Plus 20 testbestanden/fixtures (TEST_ONLY).
MJOP-App (MJOP-App 9be178c23f9789dd49e7de7e9bb9bc0fb936c14e (src/, index.html, debug/)): `src/quantity.js:104` NOT_A_PROBLEM (COMMENT: voorbeeld '425.80' -> '425,80' bij formatSourceValue).

Stand: building links voor DOC-012 1 (totaal 81); crosswalk-besluiten XWD-00001, XWD-00002, XWD-00003; quantity resolutions 0; Maldenhof-bundel ongewijzigd: True.

## K. Menselijke beslissingen nodig

SCOPE DECISION DOC-012

- [ ] H1 — alleen Meppelweg 819 (pand 0518100000354752)
- [ ] H2 — volledige VvE Meppelweg 801-883 (6 panden, beide straatzijden)
- [ ] anders / UNKNOWN

Per kandidaat-pand:

| BAG-pand | Adressen | CONFIRM | REJECT |
|---|---|---|---|
| 0518100000208891 | 802–818 (even, Pand gesloopt) | [ ] | [ ] |
| 0518100000219868 | 802–820 (even, Pand gesloopt) | [ ] | [ ] |
| 0518100000243139 | 882–882 (even, Pand in gebruik) | [ ] | [ ] |
| 0518100000277993 | 882–882 (even, Pand in gebruik) | [ ] | [ ] |
| 0518100000354752 | 803–883 (oneven, Pand in gebruik) | [ ] | [ ] |
| 0518100001631386 | 802–820 (even, Pand in gebruik) | [ ] | [ ] |

Daarna (pas na de scope):

- [ ] VERIFY / REJECT `HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012`
- [ ] (later) quantity resolution plat dak — niet in deze milestone
