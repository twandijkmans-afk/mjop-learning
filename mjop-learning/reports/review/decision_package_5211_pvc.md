# Beslispakket 5211 replace m1 - pvc

Geen besluit: niets toegepast. Simulaties gebruiken alleen de bestaande kengetalregels en worden nergens vastgelegd.

## Bestaand kengetal

`KG-5211-replace-m1-pvc-5cb98033`: AVAILABLE, 54.39, 5 clusters (SC-DOC-001, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-012, SC-DOC-013); decisions HDR-00031, HDR-00032, HDR-00033, HDR-00036, HDR-00037, HDR-00038, HDR-00039, HDR-00040, HDR-00041, HDR-00042.

## PVC-observations (independent_input)

| observation | document | cluster | object | actie | materiaal (bron) | eenheid | hoeveelheid | prijspeil | prijs/uitvoering |
|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-001-P026-L029 | DOC-001 | SC-DOC-001 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (element_text) | m1 | 371.00 | - | 51.79 |
| PO-DOC-009-P021-L095 | DOC-009 | SC-DOC-008+DOC-009 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (verified_element) | m1 | 170.20 | 21-4-2025 | 54.91 |
| PO-DOC-010-P012-L093 | DOC-010 | SC-DOC-010 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (verified_element) | m1 | 13.00 | 1-4-2023 | 45.23 |
| PO-DOC-012-P015-L033 | DOC-012 | SC-DOC-012 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (human_material_decision, MDR-00001) | m1 | 80.80 | 1-4-2024 | 61.09 |
| PO-DOC-013-P019-L025 | DOC-013 | SC-DOC-013 | Hemelwaterafvoer pvc | Vervangen hemelwaterafvoer pvc | pvc (human_material_decision, MDR-00002) | m1 | 57.00 | 14-7-2026 | 54.39 |

Potentiële pvc source clusters: **5** (SC-DOC-001, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-012, SC-DOC-013).

## Open cross-cluster paren (0)

| paar | familie (vorige id) | documenten | klasse | paarcaveats | hard | observation-caveats | verschillen | controle |
|---|---|---|---|---|---|---|---|---|

Paren die NIET aan de beschrijving voldoen (zelfde actie, pvc, m1, geen relatie; verschil alleen prijspeil/hoeveelheid/prijs): geen.

## Simulaties per open familie

## Gecombineerde scenario's (alle open families dezelfde keuze)

- **ALL_OPEN_FAMILIES_COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-5cb98033 AVAILABLE 54.39 (5 clusters; min 45.23, max 61.09, gemengde prijspeilen, ontbrekend prijspeil)
- **ALL_OPEN_FAMILIES_COMPARABLE_WITH_CAVEATS** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-5cb98033 AVAILABLE 54.39 (5 clusters; min 45.23, max 61.09, gemengde prijspeilen, ontbrekend prijspeil)
- **ALL_OPEN_FAMILIES_NOT_COMPARABLE** -> bestaand kengetal: `UNCHANGED`; KG-5211-replace-m1-pvc-5cb98033 AVAILABLE 54.39 (5 clusters; min 45.23, max 61.09, gemengde prijspeilen, ontbrekend prijspeil)

Beslispakket, geen besluit. Simulaties gebruiken uitsluitend build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische ACTIVE records; ze worden nergens vastgelegd. COMPARABLE en COMPARABLE_WITH_CAVEATS tellen in de regels hetzelfde (regel 2); het verschil is de vastgelegde voorbehoud-informatie. Toepassen alleen via scripts/apply_family_decision.py.
