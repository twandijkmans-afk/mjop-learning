# Range discovery v2

Read-only rapport over `data/external/building_validation/real_validation_v2` (fetch_real_building_validation_v1.3.0). Er wordt geen pariteit gekozen en niets goedgekeurd. 3D BAG-sommen zijn evidence, geen onderhoudshoeveelheden.

| Groep | Documenten | Klasse | Meest ondersteund | Goedgekeurd / bewijs / unresolved |
|---|---|---|---|---|
| DOC-001 | DOC-001 | MODERATE_CANDIDATE | MIXED:ALKMAARSTRAAT=ODD\|GROETSTRAAT=ALL | — |
| DOC-005-006 | DOC-005, DOC-006 | APPROVED_PROJECT | EVEN_ONLY | BPRJ-00001, BPEV-00001 |
| DOC-009 | DOC-009 | REVIEW_CASE | — | — |
| DOC-012 | DOC-012 | REVIEW_CASE | — | UCASE-00001 |
| DOC-013 | DOC-013 | REVIEW_CASE | — | — |
| DOC-015 | DOC-015 | REVIEW_CASE | — | — |

## DOC-001 — VvE Alkmaarstraat 1-83 en Groetstraat 189-217

- MJOP: eenheden — (niet in bron), bouwjaar 1966, postcode —, plaats Amsterdam; documentadres `Alkmaarstraat 1`
- Klasse: **MODERATE_CANDIDATE** — beste hypothese is MODERATE (bijv. MJOP noemt geen aantal eenheden); menselijke beoordeling nodig
- Pariteit onderscheidend op pandniveau: nee; Alkmaarstraat: ja; Groetstraat: nee
- `PARITY_NOT_DISTINGUISHING_AT_PAND_LEVEL[Groetstraat]: even en oneven nummers delen 4 BAG-panden`
- `PARITY_NOT_DISTINGUISHING_AT_PAND_LEVEL: EVEN_ONLY en ODD_ONLY delen 4 BAG-panden; pariteit is geen projectidentiteit, geen pariteit gekozen`
- `GROUP: BUILDING_PROJECT_BESTAAT_UIT_10_BAG_PANDEN (geen enkel pand is 'het gebouw')`
- `0363100012571474: THREEDBAG_ATTRIBUTES_MISSING`

| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |
|---|---|---|---|---|---|---|---|---|---|
| ALL_NUMBERS | WEAK | 74 (73+1) | 74 | 13 | 1966, 1982, 2017, 2025 | 12/13 | 39 | 0 | all_requested_found, construction_year_matches_all_panden, threedbag_coverage_complete, units_known |
| EVEN_ONLY | WEAK | 17 (16+1) | 31 | 7 | 1966, 1982, 2017, 2025 | 6/7 | 39 | 0 | all_requested_found, construction_year_matches_all_panden, document_address_number_in_scope, threedbag_coverage_complete, units_known, vbo_fully_covered |
| ODD_ONLY | WEAK | 57 (57+0) | 71 | 10 | 1966 | 10/10 | 0 | 0 | units_known, vbo_fully_covered |
| MIXED:ALKMAARSTRAAT=ALL\|GROETSTRAAT=EVEN | WEAK | 59 (58+1) | 74 | 13 | 1966, 1982, 2017, 2025 | 12/13 | 39 | 0 | all_requested_found, construction_year_matches_all_panden, threedbag_coverage_complete, units_known, vbo_fully_covered |
| MIXED:ALKMAARSTRAAT=ALL\|GROETSTRAAT=ODD | WEAK | 60 (59+1) | 74 | 13 | 1966, 1982, 2017, 2025 | 12/13 | 39 | 0 | all_requested_found, construction_year_matches_all_panden, threedbag_coverage_complete, units_known, vbo_fully_covered |
| MIXED:ALKMAARSTRAAT=EVEN\|GROETSTRAAT=ALL | WEAK | 32 (31+1) | 39 | 8 | 1966, 1982, 2017, 2025 | 7/8 | 39 | 0 | all_requested_found, construction_year_matches_all_panden, document_address_number_in_scope, threedbag_coverage_complete, units_known, vbo_fully_covered |
| MIXED:ALKMAARSTRAAT=EVEN\|GROETSTRAAT=ODD | WEAK | 18 (17+1) | 39 | 8 | 1966, 1982, 2017, 2025 | 7/8 | 39 | 0 | all_requested_found, construction_year_matches_all_panden, document_address_number_in_scope, threedbag_coverage_complete, units_known, vbo_fully_covered |
| MIXED:ALKMAARSTRAAT=ODD\|GROETSTRAAT=ALL | MODERATE | 71 (71+0) | 71 | 10 | 1966 | 10/10 | 0 | 0 | units_known |
| MIXED:ALKMAARSTRAAT=ODD\|GROETSTRAAT=EVEN | WEAK | 56 (56+0) | 71 | 10 | 1966 | 10/10 | 0 | 0 | units_known, vbo_fully_covered |

Toevoegingen in scope: Alkmaarstraat 10B, 1024TT Amsterdam

## DOC-005-006 — VvE Maldenhof 240-296

- MJOP: eenheden 29, bouwjaar 1981, postcode 1106 EZ, plaats Amsterdam; documentadres `240`
- Klasse: **APPROVED_PROJECT** — document zit in een ACTIVE building_project; dit package is alleen ondersteunend bewijs
- Pariteit onderscheidend op pandniveau: ja
- `GROUP: BUILDING_PROJECT_BESTAAT_UIT_15_BAG_PANDEN (geen enkel pand is 'het gebouw')`

| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |
|---|---|---|---|---|---|---|---|---|---|
| EVEN_ONLY | STRONG | 29 (29+0) | 29 | 15 | 1981 | 15/15 | 0 | 0 | — |
| ALL_NUMBERS | WEAK | 56 (56+0) | 56 | 40 | 1981 | 40/40 | 1 | 0 | all_requested_found, units_equal_addresses_and_vbo |
| ODD_ONLY | WEAK | 27 (27+0) | 27 | 25 | 1981 | 25/25 | 1 | 0 | all_requested_found, document_address_number_in_scope, units_equal_addresses_and_vbo |

## DOC-009 — VvE St. Jacobsstraat 251-321 Woningen

- MJOP: eenheden 30, bouwjaar 1955, postcode —, plaats Utrecht; documentadres `251`
- Klasse: **REVIEW_CASE** — geen hypothese voldoende bevestigd, of tegenstrijdig bewijs; zie blokkerende checks
- Pariteit onderscheidend op pandniveau: ja
- `STREET_ALIAS_APPLIED: 'St. Jacobsstraat' -> 'St.-Jacobsstraat' (STREET_ALIAS_UTRECHT_ST_JACOBSSTRAAT_V1)`
- `NO_HYPOTHESIS_SUFFICIENTLY_SUPPORTED: geen scope-hypothese wordt door de BAG-data voldoende bevestigd`

| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |
|---|---|---|---|---|---|---|---|---|---|
| ALL_NUMBERS | WEAK | 37 (37+0) | 45 | 10 | 1950, 1955, 1987 | 10/10 | 34 | 8 | all_requested_found, construction_year_matches_all_panden, units_equal_addresses_and_vbo, vbo_fully_covered |
| EVEN_ONLY | WEAK | 1 (1+0) | 9 | 1 | 1987 | 1/1 | 34 | 8 | all_requested_found, construction_year_matches_all_panden, document_address_number_in_scope, units_equal_addresses_and_vbo, vbo_fully_covered |
| ODD_ONLY | WEAK | 36 (36+0) | 36 | 9 | 1950, 1955 | 9/9 | 0 | 0 | construction_year_matches_all_panden, units_equal_addresses_and_vbo |

## DOC-012 — VvE Meppelweg 801-883 (documentadres Meppelweg 819)

- MJOP: eenheden — (niet in bron), bouwjaar 1956, postcode 2544 AW, plaats Den Haag; documentadres `819`
- Klasse: **REVIEW_CASE** — geen hypothese voldoende bevestigd, of tegenstrijdig bewijs; zie blokkerende checks
- Pariteit onderscheidend op pandniveau: ja
- `NO_HYPOTHESIS_SUFFICIENTLY_SUPPORTED: geen scope-hypothese wordt door de BAG-data voldoende bevestigd`

| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |
|---|---|---|---|---|---|---|---|---|---|
| ODD_ONLY | WEAK | 41 (41+0) | 42 | 1 | 1957 | 1/1 | 1 | 1 | all_requested_found, construction_year_matches_all_panden, units_known, vbo_fully_covered |
| ALL_NUMBERS | WEAK | 82 (52+30) | 221 | 4 | 1957, 1965, 2009, 2013 | 4/4 | 31 | 1 | all_requested_found, construction_year_matches_all_panden, units_known, vbo_fully_covered |
| EVEN_ONLY | WEAK | 41 (11+30) | 179 | 3 | 1965, 2009, 2013 | 3/3 | 30 | 0 | all_requested_found, construction_year_matches_all_panden, document_address_number_in_scope, units_known, vbo_fully_covered |

Toevoegingen in scope: Meppelweg 802A, 2544BV 's-Gravenhage, Meppelweg 802B, 2544BV 's-Gravenhage, Meppelweg 802C, 2544BV 's-Gravenhage, Meppelweg 804A, 2544BV 's-Gravenhage, Meppelweg 804B, 2544BV 's-Gravenhage, Meppelweg 804C, 2544BV 's-Gravenhage, Meppelweg 806A, 2544BV 's-Gravenhage, Meppelweg 806B, 2544BV 's-Gravenhage, Meppelweg 806C, 2544BV 's-Gravenhage, Meppelweg 808A, 2544BV 's-Gravenhage, Meppelweg 808B, 2544BV 's-Gravenhage, Meppelweg 808C, 2544BV 's-Gravenhage, Meppelweg 810A, 2544BV 's-Gravenhage, Meppelweg 810B, 2544BV 's-Gravenhage, Meppelweg 810C, 2544BV 's-Gravenhage, Meppelweg 812A, 2544BV 's-Gravenhage, Meppelweg 812B, 2544BV 's-Gravenhage, Meppelweg 812C, 2544BV 's-Gravenhage, Meppelweg 814A, 2544BV 's-Gravenhage, Meppelweg 814B, 2544BV 's-Gravenhage, Meppelweg 814C, 2544BV 's-Gravenhage, Meppelweg 816A, 2544BV 's-Gravenhage, Meppelweg 816B, 2544BV 's-Gravenhage, Meppelweg 816C, 2544BV 's-Gravenhage, Meppelweg 818A, 2544BV 's-Gravenhage, Meppelweg 818B, 2544BV 's-Gravenhage, Meppelweg 818C, 2544BV 's-Gravenhage, Meppelweg 820A, 2544BV 's-Gravenhage, Meppelweg 820T, 's-Gravenhage, Meppelweg 882T, 's-Gravenhage

## DOC-013 — VVE Gebouwen Vechtstraat 13-15-17-19

- MJOP: eenheden 11, bouwjaar 1921, postcode —, plaats Amsterdam; documentadres `13`
- Klasse: **REVIEW_CASE** — geen hypothese voldoende bevestigd, of tegenstrijdig bewijs; zie blokkerende checks
- `GROUP: BUILDING_PROJECT_BESTAAT_UIT_3_BAG_PANDEN (geen enkel pand is 'het gebouw')`

| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |
|---|---|---|---|---|---|---|---|---|---|
| REQUESTED_NUMBERS | WEAK | 11 (1+10) | 11 | 3 | 1923 | 3/3 | 0 | 0 | construction_year_matches_all_panden |

Toevoegingen in scope: Vechtstraat 13-1, 1078RE Amsterdam, Vechtstraat 13-2, 1078RE Amsterdam, Vechtstraat 13-3, 1078RE Amsterdam, Vechtstraat 13-H, 1078RE Amsterdam, Vechtstraat 15-1, 1078RE Amsterdam, Vechtstraat 15-2, 1078RE Amsterdam, Vechtstraat 15-3, 1078RE Amsterdam, Vechtstraat 19-1, 1078RG Amsterdam, Vechtstraat 19-2, 1078RG Amsterdam, Vechtstraat 19-H, 1078RG Amsterdam

## DOC-015 — VvE Groetstraat 110-140

- MJOP: eenheden — (niet in bron), bouwjaar —, postcode —, plaats Amsterdam; documentadres `110`
- Klasse: **REVIEW_CASE** — geen hypothese voldoende bevestigd, of tegenstrijdig bewijs; zie blokkerende checks
- Pariteit onderscheidend op pandniveau: nee
- `PARITY_NOT_DISTINGUISHING_AT_PAND_LEVEL: EVEN_ONLY en ODD_ONLY leveren dezelfde BAG-panden; pariteit is geen projectidentiteit, geen pariteit gekozen`
- `NO_HYPOTHESIS_SUFFICIENTLY_SUPPORTED: geen scope-hypothese wordt door de BAG-data voldoende bevestigd`

| Hypothese | Sterkte | Adressen (exact+toev.) | VBO | Panden | Bouwjaren | 3D BAG | Ontbrekend | Extra VBO | Falende checks |
|---|---|---|---|---|---|---|---|---|---|
| ALL_NUMBERS | WEAK | 31 (31+0) | 34 | 4 | 1966 | 4/4 | 0 | 3 | units_known, vbo_fully_covered |
| EVEN_ONLY | WEAK | 16 (16+0) | 34 | 4 | 1966 | 4/4 | 0 | 3 | units_known, vbo_fully_covered |
| ODD_ONLY | WEAK | 15 (15+0) | 34 | 4 | 1966 | 4/4 | 0 | 3 | document_address_number_in_scope, units_known, vbo_fully_covered |
