# Beslispakket 5211 replace m1 - pvc

Geen besluit: niets toegepast. Simulaties gebruiken alleen de bestaande kengetalregels en worden nergens vastgelegd.

## Bestaand kengetal

`KG-5211-replace-m1-pvc-67920b77`: AVAILABLE, 51.79, 3 clusters (SC-DOC-001, SC-DOC-008+DOC-009, SC-DOC-010); decisions HDR-00031, HDR-00032, HDR-00033.

## PVC-observations (independent_input)

| observation | document | cluster | object | actie | materiaal (bron) | eenheid | hoeveelheid | prijspeil | prijs/uitvoering |
|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-001-P026-L029 | DOC-001 | SC-DOC-001 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (element_text) | m1 | 371.00 | - | 51.79 |
| PO-DOC-009-P021-L095 | DOC-009 | SC-DOC-008+DOC-009 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (verified_element) | m1 | 170.20 | 21-4-2025 | 54.91 |
| PO-DOC-010-P012-L093 | DOC-010 | SC-DOC-010 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (verified_element) | m1 | 13.00 | 1-4-2023 | 45.23 |
| PO-DOC-012-P015-L033 | DOC-012 | SC-DOC-012 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (human_material_decision, MDR-00001) | m1 | 80.80 | 1-4-2024 | 61.09 |
| PO-DOC-013-P019-L025 | DOC-013 | SC-DOC-013 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (human_material_decision, MDR-00002) | m1 | 57.00 | 14-7-2026 | 54.39 |

Potentiële pvc source clusters: **5** (SC-DOC-001, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-012, SC-DOC-013).

## Open cross-cluster paren (7)

| paar | familie (vorige id) | documenten | klasse | paarcaveats | hard | observation-caveats | verschillen | controle |
|---|---|---|---|---|---|---|---|---|
| PAIR-00583 | RF-5211-0ad5841f33 (RF-5211-4c4e7cd188) | DOC-001 x DOC-012 | COMPARABLE_WITH_CAVEATS | - | - | a: PRICE_LEVEL_ABSENT; b: - | price_level, quantity, price | OK |
| PAIR-00585 | RF-5211-0ad5841f33 (RF-5211-4c4e7cd188) | DOC-001 x DOC-013 | COMPARABLE_WITH_CAVEATS | - | - | a: PRICE_LEVEL_ABSENT; b: - | price_level, quantity, price | OK |
| PAIR-00632 | RF-5211-6d02e2e719 (RF-5211-1e814339c4) | DOC-009 x DOC-012 | COMPARABLE_WITH_CAVEATS | PRICE_LEVEL_DIFFERENCE | - | a: -; b: - | price_level, quantity, price | OK |
| PAIR-00634 | RF-5211-6d02e2e719 (RF-5211-1e814339c4) | DOC-009 x DOC-013 | COMPARABLE_WITH_CAVEATS | PRICE_LEVEL_DIFFERENCE | - | a: -; b: - | price_level, quantity, price | OK |
| PAIR-00635 | RF-5211-6d02e2e719 (RF-5211-1e814339c4) | DOC-010 x DOC-012 | COMPARABLE_WITH_CAVEATS | PRICE_LEVEL_DIFFERENCE | - | a: -; b: - | price_level, quantity, price | OK |
| PAIR-00637 | RF-5211-6d02e2e719 (RF-5211-1e814339c4) | DOC-010 x DOC-013 | COMPARABLE_WITH_CAVEATS | PRICE_LEVEL_DIFFERENCE | - | a: -; b: - | price_level, quantity, price | OK |
| PAIR-00641 | RF-5211-76b81abb4c (RF-5211-4e9a81167e) | DOC-012 x DOC-013 | COMPARABLE_WITH_CAVEATS | PRICE_LEVEL_DIFFERENCE | - | a: -; b: - | price_level, quantity, price | OK |

Paren die NIET aan de beschrijving voldoen (zelfde actie, pvc, m1, geen relatie; verschil alleen prijspeil/hoeveelheid/prijs): geen.

## Simulaties per open familie

### RF-5211-0ad5841f33 (was RF-5211-4c4e7cd188) - EXACT_SAME_SEMANTIC_INPUT, 2 paren

- paren: PAIR-00583, PAIR-00585; documenten DOC-001, DOC-012, DOC-013
- paarcaveats: -; observation-caveats: {'PRICE_LEVEL_ABSENT': 2}
- family_input_sha256: `760513e2b18dc45a97c0c0180d910cb091ba1a6783579579647a5b393d77f127`

- **COMPARABLE** -> bestaand kengetal: `REPLACED_BY:KG-5211-replace-m1-pvc-5cb98033(INSUFFICIENT_DATA)`; KG-5211-replace-m1-pvc-5cb98033 INSUFFICIENT_DATA  (5 clusters, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW)
- **COMPARABLE_WITH_CAVEATS** -> bestaand kengetal: `REPLACED_BY:KG-5211-replace-m1-pvc-5cb98033(INSUFFICIENT_DATA)`; KG-5211-replace-m1-pvc-5cb98033 INSUFFICIENT_DATA  (5 clusters, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW)
- **NOT_COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters)

### RF-5211-6d02e2e719 (was RF-5211-1e814339c4) - EXACT_SAME_SEMANTIC_INPUT, 4 paren

- paren: PAIR-00632, PAIR-00634, PAIR-00635, PAIR-00637; documenten DOC-009, DOC-010, DOC-012, DOC-013
- paarcaveats: {'PRICE_LEVEL_DIFFERENCE': 4}; observation-caveats: -
- family_input_sha256: `878abf5892bffb487bd75c677fa965a8b8fc5c338f85413799f75ca1416b1560`

- **COMPARABLE** -> bestaand kengetal: `REPLACED_BY:KG-5211-replace-m1-pvc-5cb98033(INSUFFICIENT_DATA)`; KG-5211-replace-m1-pvc-5cb98033 INSUFFICIENT_DATA  (5 clusters, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW)
- **COMPARABLE_WITH_CAVEATS** -> bestaand kengetal: `REPLACED_BY:KG-5211-replace-m1-pvc-5cb98033(INSUFFICIENT_DATA)`; KG-5211-replace-m1-pvc-5cb98033 INSUFFICIENT_DATA  (5 clusters, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW)
- **NOT_COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters)

### RF-5211-76b81abb4c (was RF-5211-4e9a81167e) - EXACT_SAME_SEMANTIC_INPUT, 1 paren

- paren: PAIR-00641; documenten DOC-012, DOC-013
- paarcaveats: {'PRICE_LEVEL_DIFFERENCE': 1}; observation-caveats: -
- family_input_sha256: `172756d55b9720cb3271100af7644a8f4e8b6c8f966f3bbc76a09d203ad710ed`

- **COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters); KG-5211-replace-m1-pvc-73cbcafe INSUFFICIENT_DATA  (2 clusters, redenen FEWER_THAN_3_SOURCE_CLUSTERS)
- **COMPARABLE_WITH_CAVEATS** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters); KG-5211-replace-m1-pvc-73cbcafe INSUFFICIENT_DATA  (2 clusters, redenen FEWER_THAN_3_SOURCE_CLUSTERS)
- **NOT_COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters)

## Gecombineerde scenario's (alle open families dezelfde keuze)

- **ALL_OPEN_FAMILIES_COMPARABLE** -> bestaand kengetal: `REPLACED_BY:KG-5211-replace-m1-pvc-5cb98033(AVAILABLE)`; KG-5211-replace-m1-pvc-5cb98033 AVAILABLE 54.39 (5 clusters; min 45.23, max 61.09, gemengde prijspeilen, ontbrekend prijspeil)
- **ALL_OPEN_FAMILIES_COMPARABLE_WITH_CAVEATS** -> bestaand kengetal: `REPLACED_BY:KG-5211-replace-m1-pvc-5cb98033(AVAILABLE)`; KG-5211-replace-m1-pvc-5cb98033 AVAILABLE 54.39 (5 clusters; min 45.23, max 61.09, gemengde prijspeilen, ontbrekend prijspeil)
- **ALL_OPEN_FAMILIES_NOT_COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters; min 45.23, max 54.91, gemengde prijspeilen, ontbrekend prijspeil)

Beslispakket, geen besluit. Simulaties gebruiken uitsluitend build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische ACTIVE records; ze worden nergens vastgelegd. COMPARABLE en COMPARABLE_WITH_CAVEATS tellen in de regels hetzelfde (regel 2); het verschil is de vastgelegde voorbehoud-informatie. Toepassen alleen via scripts/apply_family_decision.py.
