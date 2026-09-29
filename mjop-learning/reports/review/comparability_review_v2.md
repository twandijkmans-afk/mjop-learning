# Comparability review v2

Reviewpakket: **er is niets besloten**. Geen ACTIVE decisions, geen automatische COMPARABLE of NOT_COMPARABLE, geen scores, geen nieuw kengetal. Een familiebesluit wordt alleen toegepast via `scripts/apply_family_decision.py` op exact opgesomde `pair_ids`, gebonden aan `family_input_sha256`.

Invoer: comparability `545070e3d1e9`, genormaliseerd `31fdf85badcc`, beslissingen `bed01185bacb`, relaties `2a1cab33999c`.

## Reviewqueue vóór en na groepering

| | aantal |
|---|---|
| paren in de queue (selectie v1) | 76 |
| paren met status ACTIVE_DECISION | 5 |
| paren met status NO_DECISION | 54 |
| paren met status PREVIOUS_DECISION_REVIEW_REQUIRED | 17 |
| reviewfamilies | 43 |
| open reviewfamilies | 38 |
| families met meer dan één paar | 17 |

Families per bewijscategorie (families / paren):

- `OTHER_REVIEW_REQUIRED`: 1 / 1
- `OBJECT_TEXT_VARIANT`: 21 / 34
- `ACTION_TEXT_VARIANT`: 4 / 16
- `MATERIAL_EVIDENCE_ONE_SIDE`: 7 / 13
- `QUANTITY_SCALE_DIFFERENCE`: 5 / 5
- `EXACT_SAME_SEMANTIC_INPUT`: 5 / 7

Groepering: candidate key + per kant (objectomschrijving en actietekst als woordtokens zonder de vaste gevelzijde-woorden, eenheid in de bron, materiaal + bron, inhoudelijke observation-caveats) + gevelzijde-woorden verschillen + QUANTITY_SCALE_DIFFERENCE + relatierisico. Gevelzijde-woorden: achter, achtergevel, achterzijde, voor, voorgevel, voorzijde.

## 4645|exterior_painting|m2 (prioriteit 1)

- observations: 13 (independent_input: 12)
- source clusters (alle): 7; potentieel beschikbaar (independent_input): 6 - SC-DOC-001, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-011, SC-DOC-015
- paren: 68 (COMPARABLE_WITH_CAVEATS 35, UNKNOWN 33); in de reviewqueue: 22
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): KNOWN:wood: 1, NO_MATERIAL_EVIDENCE: 10, TEXT_EVIDENCE_PENDING_APPROVAL:wood: 1

Zonder materiaalbewijs: PO-DOC-001-P026-L019, PO-DOC-007-P017-L073, PO-DOC-007-P017-L077, PO-DOC-009-P021-L027, PO-DOC-009-P021-L031, PO-DOC-009-P021-L039, PO-DOC-009-P021-L043, PO-DOC-010-P012-L037, PO-DOC-011-P021-L057, PO-DOC-015-S01-R0130. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **wood**: 2 observations, 2 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-011: PO-DOC-011-P021-L047
  - 1 cross-cluster paren zonder ACTIVE positieve beslissing (1 in de queue; families RF-4645-d1a9f6b86e; niet in de queue: )
  - Minder dan 3 onafhankelijke source clusters; ook met alle beslissingen blijft dit INSUFFICIENT_DATA.

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4645-3b30ddccf4` | ACTION_TEXT_VARIANT | 12 | OPEN_MIXED | DOC-007, DOC-009, DOC-010, DOC-011, DOC-015 | HDR-00010, HDR-00011, HDR-00012, HDR-00013 |
| `RF-4645-8d3abeeeb4` | OBJECT_TEXT_VARIANT | 6 | OPEN_MIXED | DOC-009, DOC-010, DOC-011, DOC-015 | HDR-00014, HDR-00015 |
| `RF-4645-909f45c434` | EXACT_SAME_SEMANTIC_INPUT | 2 | OPEN_NO_DECISION | DOC-010, DOC-011, DOC-015 | - |
| `RF-4645-7d44afede6` | QUANTITY_SCALE_DIFFERENCE | 1 | OPEN_NO_DECISION | DOC-010, DOC-011 | - |
| `RF-4645-d1a9f6b86e` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-007, DOC-011 | - |

#### RF-4645-3b30ddccf4 - ACTION_TEXT_VARIANT (12 paren)

- kant 1: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- kant 2: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- bewijs: ACTION_TEXT_VARIANT; paarcaveats {'ACTION_TEXT_VARIANT': 12, 'PRICE_LEVEL_DIFFERENCE': 2}
- actieteksten: Groot schilderwerk betonconstructie plafond, Groot schilderwerk betonconstructie plafond achter, Groot schilderwerk betonconstructie plafond achterzijde, Groot schilderwerk betonconstructie plafond voor, Groot schilderwerk betonconstructie plafond voorzijde
- hoeveelheden: 25.24, 117.18, 130.00, 146, 561.50; prijspeilen: 1-4-2023, 21-4-2025, 28-4-2023, None
- pair_ids: PAIR-00488, PAIR-00490, PAIR-00491, PAIR-00496, PAIR-00498, PAIR-00499, PAIR-00508, PAIR-00510, PAIR-00511, PAIR-00512, PAIR-00514, PAIR-00515
- family_input_sha256: `6532a4ee59bc77bc218e6fb8ecc7d2ab3a3adc5b7eb0ddf8e8d1388085dc9197`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4645-8d3abeeeb4 - OBJECT_TEXT_VARIANT (6 paren)

- kant 1: buitenschilderwerk betonconstructie plafond dakoverstek / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- kant 2: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT; paarcaveats {'ACTION_TEXT_VARIANT': 6, 'GENERIC_VS_SPECIFIC_OBJECT': 6, 'PRICE_LEVEL_DIFFERENCE': 2}
- actieteksten: Groot schilderwerk betonconstructie plafond, Groot schilderwerk betonconstructie plafond achter, Groot schilderwerk betonconstructie plafond voor
- hoeveelheden: 25.24, 104.60, 146, 561.50; prijspeilen: 1-4-2023, 21-4-2025, None
- pair_ids: PAIR-00516, PAIR-00518, PAIR-00519, PAIR-00520, PAIR-00522, PAIR-00523
- family_input_sha256: `0e9ff2d18d3d6c6deca3feb1b7b9db512eada0eaba5668b8bdc0a10d1565a38b`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4645-909f45c434 - EXACT_SAME_SEMANTIC_INPUT (2 paren)

- kant 1: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- kant 2: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- bewijs: EXACT_SAME_SEMANTIC_INPUT; paarcaveats -
- actieteksten: Groot schilderwerk betonconstructie plafond
- hoeveelheden: 25.24, 146, 561.50; prijspeilen: 1-4-2023, None
- pair_ids: PAIR-00526, PAIR-00528
- family_input_sha256: `29ac8c377fb7825e2c41421fafb9bd8c4e29ab616bea190cf3489ffabf58b0be`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4645-7d44afede6 - QUANTITY_SCALE_DIFFERENCE (1 paren)

- kant 1: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- kant 2: buitenschilderwerk betonconstructie plafond / groot schilderwerk betonconstructie plafond / m2 / materiaal onbekend
- bewijs: QUANTITY_SCALE_DIFFERENCE; paarcaveats {'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Groot schilderwerk betonconstructie plafond
- hoeveelheden: 25.24, 561.50; prijspeilen: 1-4-2023, None
- pair_ids: PAIR-00525
- family_input_sha256: `346384691cb1f72e65cf047ee73bcfaa330ae3f186e3d9bacc6060f899ad2464`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4645-d1a9f6b86e - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk plafond hout dekkend dakoverstek / groot schilderwerk plafond hout dekkend / m2 / materiaal onbekend
- kant 2: buitenschilderwerk plafond hout dekkend / groot schilderwerk plafond hout dekkend / m2 / materiaal wood
- bewijs: OBJECT_TEXT_VARIANT, MATERIAL_EVIDENCE_ONE_SIDE; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1}
- actieteksten: Groot schilderwerk plafond hout dekkend
- hoeveelheden: 29.00, 208.20; prijspeilen: 28-4-2023, None
- pair_ids: PAIR-00505
- family_input_sha256: `1845826b42e4bc3b0facfb7c686c695a24f3c2d208c0419f3d5a3e6903bb6794`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 5211|replace|m1 (prioriteit 2)

- observations: 14 (independent_input: 7)
- source clusters (alle): 8; potentieel beschikbaar (independent_input): 5 - SC-DOC-001, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-012, SC-DOC-013
- paren: 69 (COMPARABLE_WITH_CAVEATS 11, NOT_COMPARABLE 10, UNKNOWN 48); in de reviewqueue: 11
- ACTIVE decisions: HDR-00031, HDR-00032, HDR-00033
- bestaande kengetallen: KG-5211-replace-m1-pvc-67920b77 AVAILABLE 51.79 (3 clusters)
- materiaalbewijs (independent_input): KNOWN:pvc: 3, KNOWN:steel: 1, TEXT_EVIDENCE_PENDING_APPROVAL:pvc: 2, TEXT_EVIDENCE_PENDING_APPROVAL:steel: 1

### PVC-semantiek en het bestaande kengetal

- `KG-5211-replace-m1-pvc-67920b77`: AVAILABLE 51.79, 3 clusters, decisions HDR-00031, HDR-00032, HDR-00033
- Het bestaande kengetal blijft ongewijzigd tot er nieuwe geldige ACTIVE decisions zijn; dit pakket wijzigt het niet.

Nieuwe observations (Testbatch 01):

- `NOT_INDEPENDENT_INPUT`: PO-DOC-011-P021-L115 - Hemelwaterafvoer pvc / Vervangen hemelwaterafvoer pvc achtergevel incl. bocht naar horizontaal (140.00, prijs per uitvoering 140.67, prijspeil None)
- `OTHER_MATERIAL:steel`: PO-DOC-012-P015-L039 - Hemelwaterafvoer staal gegalvaniseerd / Vervangen hemelwaterafvoer staal gegalvaniseerd (32.00, prijs per uitvoering 159.75, prijspeil 1-4-2024)
- `PVC_BY_ELEMENT_TEXT_PENDING_MATERIAL_APPROVAL`: PO-DOC-012-P015-L033 - Hemelwaterafvoer pvc / Vervangen hemelwaterafvoer pvc (80.80, prijs per uitvoering 61.09, prijspeil 1-4-2024)
- `PVC_BY_ELEMENT_TEXT_PENDING_MATERIAL_APPROVAL`: PO-DOC-013-P019-L025 - Hemelwaterafvoer pvc / Vervangen hemelwaterafvoer pvc (57.00, prijs per uitvoering 54.39, prijspeil 14-7-2026)

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **pvc**: 5 observations, 5 potentiële clusters, status `REQUIRES_HUMAN_STEPS`, bestaand kengetal KG-5211-replace-m1-pvc-67920b77
  - materiaalgoedkeuring nodig voor DOC-012, DOC-013: PO-DOC-012-P015-L033, PO-DOC-013-P019-L025
  - 7 cross-cluster paren zonder ACTIVE positieve beslissing (7 in de queue; families RF-5211-1e814339c4, RF-5211-4c4e7cd188, RF-5211-4e9a81167e; niet in de queue: )
- materiaal **steel**: 2 observations, 2 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-012: PO-DOC-012-P015-L039
  - 1 cross-cluster paren zonder ACTIVE positieve beslissing (1 in de queue; families RF-5211-44666031e0; niet in de queue: )
  - Minder dan 3 onafhankelijke source clusters; ook met alle beslissingen blijft dit INSUFFICIENT_DATA.

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-5211-1e814339c4` | MATERIAL_EVIDENCE_ONE_SIDE | 4 | OPEN_NO_DECISION | DOC-009, DOC-010, DOC-012, DOC-013 | - |
| `RF-5211-4c4e7cd188` | MATERIAL_EVIDENCE_ONE_SIDE | 2 | OPEN_NO_DECISION | DOC-001, DOC-012, DOC-013 | - |
| `RF-5211-44666031e0` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-010, DOC-012 | - |
| `RF-5211-4e9a81167e` | EXACT_SAME_SEMANTIC_INPUT | 1 | OPEN_NO_DECISION | DOC-012, DOC-013 | - |
| `RF-5211-0fe1340601` | EXACT_SAME_SEMANTIC_INPUT | 1 | DECIDED_ACTIVE | DOC-001, DOC-009 | HDR-00018, HDR-00031 |
| `RF-5211-4ad0a0fd5d` | QUANTITY_SCALE_DIFFERENCE | 1 | DECIDED_ACTIVE | DOC-009, DOC-010 | HDR-00020, HDR-00033 |
| `RF-5211-8d4093291e` | QUANTITY_SCALE_DIFFERENCE | 1 | DECIDED_ACTIVE | DOC-001, DOC-010 | HDR-00019, HDR-00032 |

#### RF-5211-1e814339c4 - MATERIAL_EVIDENCE_ONE_SIDE (4 paren)

- kant 1: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- kant 2: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal onbekend
- bewijs: MATERIAL_EVIDENCE_ONE_SIDE; paarcaveats {'PRICE_LEVEL_DIFFERENCE': 4}
- actieteksten: Vervangen hemelwaterafvoer pvc
- hoeveelheden: 13.00, 57.00, 80.80, 170.20; prijspeilen: 1-4-2023, 1-4-2024, 14-7-2026, 21-4-2025
- pair_ids: PAIR-00632, PAIR-00634, PAIR-00635, PAIR-00637
- family_input_sha256: `b348844768448cd834b8e40e791b57340b0e2414727b76293c3b53fd0acfed76`
- **LET OP**: een positief besluit over alle paren maakt volgens de bestaande regels het AVAILABLE kengetal KG-5211-replace-m1-pvc-67920b77 ongeldig (de groep wordt INSUFFICIENT_DATA ['INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW', 'MATERIAL_UNKNOWN']); vereist expliciete bevestiging bij het toepassen
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-5211-4c4e7cd188 - MATERIAL_EVIDENCE_ONE_SIDE (2 paren)

- kant 1: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- kant 2: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal onbekend
- bewijs: MATERIAL_EVIDENCE_ONE_SIDE; paarcaveats -
- actieteksten: Vervangen hemelwaterafvoer pvc
- hoeveelheden: 57.00, 80.80, 371.00; prijspeilen: 1-4-2024, 14-7-2026, None
- pair_ids: PAIR-00583, PAIR-00585
- family_input_sha256: `52b454a69d1f5edddf9d6256fd7b85d6d5d787986fc1d78931c55d0ea58477ea`
- **LET OP**: een positief besluit over alle paren maakt volgens de bestaande regels het AVAILABLE kengetal KG-5211-replace-m1-pvc-67920b77 ongeldig (de groep wordt INSUFFICIENT_DATA ['INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW', 'MATERIAL_UNKNOWN']); vereist expliciete bevestiging bij het toepassen
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-5211-44666031e0 - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: hemelwaterafvoer staal gegalvaniseerd / vervangen hemelwaterafvoer staal gegalvaniseerd / m1 / materiaal onbekend
- kant 2: hemelwaterafvoer staal / vervangen hemelwaterafvoer staal / m1 / materiaal steel
- bewijs: OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT, MATERIAL_EVIDENCE_ONE_SIDE, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'ACTION_TEXT_VARIANT': 1, 'GENERIC_VS_SPECIFIC_OBJECT': 1, 'PRICE_LEVEL_DIFFERENCE': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Vervangen hemelwaterafvoer staal, Vervangen hemelwaterafvoer staal gegalvaniseerd
- hoeveelheden: 1.82, 32.00; prijspeilen: 1-4-2023, 1-4-2024
- pair_ids: PAIR-00639
- family_input_sha256: `c4aad9ae11a91b4d93cbb853e1f91fbc75580cdc02717e7e6c978722ce2cc0dc`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-5211-4e9a81167e - EXACT_SAME_SEMANTIC_INPUT (1 paren)

- kant 1: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal onbekend
- kant 2: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal onbekend
- bewijs: EXACT_SAME_SEMANTIC_INPUT; paarcaveats {'PRICE_LEVEL_DIFFERENCE': 1}
- actieteksten: Vervangen hemelwaterafvoer pvc
- hoeveelheden: 57.00, 80.80; prijspeilen: 1-4-2024, 14-7-2026
- pair_ids: PAIR-00641
- family_input_sha256: `b2385d43bfe9bcda9e5612244e071c125695b0ef12634865dc315a9a236cd36e`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-5211-0fe1340601 - EXACT_SAME_SEMANTIC_INPUT (1 paren)

- kant 1: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- kant 2: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- bewijs: EXACT_SAME_SEMANTIC_INPUT; paarcaveats -
- actieteksten: Vervangen hemelwaterafvoer pvc
- hoeveelheden: 170.20, 371.00; prijspeilen: 21-4-2025, None
- pair_ids: PAIR-00580
- family_input_sha256: `00c298ffdb1ab05368726c575a0fba25b7ad290900450322392cd3294afc2542`

#### RF-5211-4ad0a0fd5d - QUANTITY_SCALE_DIFFERENCE (1 paren)

- kant 1: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- kant 2: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- bewijs: QUANTITY_SCALE_DIFFERENCE; paarcaveats {'PRICE_LEVEL_DIFFERENCE': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Vervangen hemelwaterafvoer pvc
- hoeveelheden: 13.00, 170.20; prijspeilen: 1-4-2023, 21-4-2025
- pair_ids: PAIR-00630
- family_input_sha256: `095af6ae4524df8052712353d1ea01131aa952cc1a97742255c4b26ff8154cc6`

#### RF-5211-8d4093291e - QUANTITY_SCALE_DIFFERENCE (1 paren)

- kant 1: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- kant 2: hemelwaterafvoer pvc / vervangen hemelwaterafvoer pvc / m1 / materiaal pvc
- bewijs: QUANTITY_SCALE_DIFFERENCE; paarcaveats {'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Vervangen hemelwaterafvoer pvc
- hoeveelheden: 13.00, 371.00; prijspeilen: 1-4-2023, None
- pair_ids: PAIR-00581
- family_input_sha256: `fba8a8cd7181895687e46b9109e6bcd767809c604ef6221c448afbda9eacea59`

## 4621|exterior_painting|m2

- observations: 22 (independent_input: 18)
- source clusters (alle): 7; potentieel beschikbaar (independent_input): 7 - SC-DOC-001, SC-DOC-002, SC-DOC-005+DOC-006, SC-DOC-010, SC-DOC-011, SC-DOC-012, SC-DOC-013
- paren: 193 (COMPARABLE_WITH_CAVEATS 3, NOT_COMPARABLE 5, UNKNOWN 185); in de reviewqueue: 3
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): KNOWN:wood: 6, NO_MATERIAL_EVIDENCE: 9, TEXT_EVIDENCE_PENDING_APPROVAL:wood: 3

Zonder materiaalbewijs: PO-DOC-001-P025-L031, PO-DOC-001-P025-L039, PO-DOC-002-P017-L049, PO-DOC-002-P018-L015, PO-DOC-002-P018-L019, PO-DOC-002-P018-L023, PO-DOC-010-P011-L089, PO-DOC-011-P020-L075, PO-DOC-011-P020-L081. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **wood**: 9 observations, 7 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-011, DOC-012, DOC-013: PO-DOC-011-P020-L067, PO-DOC-012-P014-L013, PO-DOC-013-P018-L059
  - 33 cross-cluster paren zonder ACTIVE positieve beslissing (1 in de queue; families RF-4621-b30de14ab7; niet in de queue: PAIR-00054, PAIR-00056, PAIR-00057, PAIR-00065, PAIR-00066, PAIR-00068, PAIR-00071, PAIR-00072, PAIR-00115, PAIR-00116, PAIR-00118, PAIR-00121, PAIR-00122, PAIR-00139, PAIR-00140, PAIR-00142, PAIR-00145, PAIR-00146, PAIR-00151, PAIR-00152, PAIR-00154, PAIR-00157, PAIR-00158, PAIR-00223, PAIR-00225, PAIR-00228, PAIR-00229, PAIR-00230, PAIR-00234, PAIR-00240, PAIR-00241, PAIR-00246)

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4621-7f61dec7b0` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-010, DOC-011 | - |
| `RF-4621-b30de14ab7` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-010, DOC-012 | - |
| `RF-4621-d67f32f753` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-010, DOC-011 | - |

#### RF-4621-7f61dec7b0 - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk metaal waslijnbeugel / groot schilderwerk metaal / m2 / materiaal onbekend
- kant 2: buitenschilderwerk metaal / groot schilderwerk metaal / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1}
- actieteksten: Groot schilderwerk metaal
- hoeveelheden: 37.16, 72.00; prijspeilen: 1-4-2023, None
- pair_ids: PAIR-00236
- family_input_sha256: `e9ea3241645e291b2984858e70eb09b04a3244cf2ba02fa4ec6670524574282a`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4621-b30de14ab7 - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk diversen hout dekkend alle gevels / groot schilderwerk hout dekkend / m2 / materiaal onbekend
- kant 2: buitenschilderwerk diversen hout dekkend / groot schilderwerk hout dekkend / m2 / materiaal wood
- bewijs: OBJECT_TEXT_VARIANT, MATERIAL_EVIDENCE_ONE_SIDE, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1, 'PRICE_LEVEL_DIFFERENCE': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Groot schilderwerk hout dekkend
- hoeveelheden: 4.13, 1425.95; prijspeilen: 1-4-2023, 1-4-2024
- pair_ids: PAIR-00233
- family_input_sha256: `c817c15d4ea2cb9fdbe4fdc6bd3214c6b7451ffc40d3cb9155442fe53d0f2ee6`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4621-d67f32f753 - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk metaal consoles balkons / groot schilderwerk metaal / m2 / materiaal onbekend
- kant 2: buitenschilderwerk metaal / groot schilderwerk metaal / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1}
- actieteksten: Groot schilderwerk metaal
- hoeveelheden: 36.00, 37.16; prijspeilen: 1-4-2023, None
- pair_ids: PAIR-00237
- family_input_sha256: `f7dd43f13d58b4dca3c2e3fd6ae47880a399c8f0134bb4e3043c12b0ae886c07`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 4622|interior_painting|m2

- observations: 15 (independent_input: 15)
- source clusters (alle): 6; potentieel beschikbaar (independent_input): 6 - SC-DOC-002, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-011, SC-DOC-013
- paren: 91 (COMPARABLE_WITH_CAVEATS 9, UNKNOWN 82); in de reviewqueue: 9
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): KNOWN:wood: 5, NO_MATERIAL_EVIDENCE: 9, TEXT_EVIDENCE_PENDING_APPROVAL:wood: 1

Zonder materiaalbewijs: PO-DOC-002-P018-L055, PO-DOC-002-P018-L083, PO-DOC-007-P017-L013, PO-DOC-009-P020-L023, PO-DOC-009-P020-L035, PO-DOC-010-P012-L011, PO-DOC-010-P012-L017, PO-DOC-013-P019-L077, PO-DOC-013-P019-L083. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **wood**: 6 observations, 5 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-011: PO-DOC-011-P020-L091
  - 14 cross-cluster paren zonder ACTIVE positieve beslissing (0 in de queue; families -; niet in de queue: PAIR-00250, PAIR-00253, PAIR-00256, PAIR-00257, PAIR-00272, PAIR-00275, PAIR-00278, PAIR-00279, PAIR-00304, PAIR-00307, PAIR-00308, PAIR-00325, PAIR-00326, PAIR-00335)

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4622-41fce7f574` | OBJECT_TEXT_VARIANT | 2 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED | DOC-002, DOC-010 | HDR-00005, HDR-00007 |
| `RF-4622-52471f0bfc` | OBJECT_TEXT_VARIANT | 2 | OPEN_NO_DECISION | DOC-002, DOC-013 | - |
| `RF-4622-5556eb7fc2` | OBJECT_TEXT_VARIANT | 2 | OPEN_NO_DECISION | DOC-002, DOC-013 | - |
| `RF-4622-5de32cdb82` | OBJECT_TEXT_VARIANT | 2 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED | DOC-002, DOC-009 | HDR-00004, HDR-00006 |
| `RF-4622-925c9e412c` | OBJECT_TEXT_VARIANT | 1 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED | DOC-007, DOC-009 | HDR-00008 |

#### RF-4622-41fce7f574 - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: binnenschilderwerk stucwerk incl lambrisering / groot schilderwerk stucwerk / m2 / materiaal onbekend
- kant 2: binnenschilderwerk stucwerk / groot schilderwerk stucwerk / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 2, 'PRICE_LEVEL_DIFFERENCE': 2}
- actieteksten: Groot schilderwerk stucwerk
- hoeveelheden: 128.00, 131.00, 257.36; prijspeilen: 1-4-2023, 20-8-2026
- pair_ids: PAIR-00266, PAIR-00288
- family_input_sha256: `f59fa682d7df3c1f6cba1e6f614d0775cfe5dcac97086d82a92247ec006baa25`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4622-52471f0bfc - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: binnenschilderwerk stucwerk plafonds / groot schilderwerk stucwerk / m2 / materiaal onbekend
- kant 2: binnenschilderwerk stucwerk / groot schilderwerk stucwerk / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 2}
- actieteksten: Groot schilderwerk stucwerk
- hoeveelheden: 62.60, 128.00, 131.00; prijspeilen: 14-7-2026, 20-8-2026
- pair_ids: PAIR-00270, PAIR-00292
- family_input_sha256: `6001bcf9598e52e2fe852a15846bf935ec67cf10c8f023a4ab725adc6855215c`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4622-5556eb7fc2 - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: binnenschilderwerk stucwerk wanden / groot schilderwerk stucwerk / m2 / materiaal onbekend
- kant 2: binnenschilderwerk stucwerk / groot schilderwerk stucwerk / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 2}
- actieteksten: Groot schilderwerk stucwerk
- hoeveelheden: 128.00, 131.00, 231.56; prijspeilen: 14-7-2026, 20-8-2026
- pair_ids: PAIR-00269, PAIR-00291
- family_input_sha256: `397dac715435e044416c954123ebc19726b02b62601c84fc1f35e0ea894452d9`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4622-5de32cdb82 - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: binnenschilderwerk stucwerk trappenhuis / groot schilderwerk stucwerk / m2 / materiaal onbekend
- kant 2: binnenschilderwerk stucwerk / groot schilderwerk stucwerk / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 2, 'PRICE_LEVEL_DIFFERENCE': 2}
- actieteksten: Groot schilderwerk stucwerk
- hoeveelheden: 128.00, 131.00, 355.20; prijspeilen: 20-8-2026, 21-4-2025
- pair_ids: PAIR-00262, PAIR-00284
- family_input_sha256: `14b852dbc08ecf9fc775a616c95d04eb844a2643c4e6df4594cd17023bb61270`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4622-925c9e412c - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: binnenschilderwerk metaal liftdeuren en omlijsting / groot schilderwerk metaal / m2 / materiaal onbekend
- kant 2: binnenschilderwerk metaal liftdeuren / groot schilderwerk metaal / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1, 'PRICE_LEVEL_DIFFERENCE': 1}
- actieteksten: Groot schilderwerk metaal
- hoeveelheden: 8.24, 74.02; prijspeilen: 21-4-2025, 28-4-2023
- pair_ids: PAIR-00294
- family_input_sha256: `3bdf6c5d8085d96944b2f8f1381a4eb6f756758b01a1d2758bce75156216f022`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 4631|exterior_painting|m2

- observations: 9 (independent_input: 8)
- source clusters (alle): 6; potentieel beschikbaar (independent_input): 6 - SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-013, SC-DOC-015
- paren: 33 (COMPARABLE_WITH_CAVEATS 5, UNKNOWN 28); in de reviewqueue: 5
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): KNOWN:wood: 4, NO_MATERIAL_EVIDENCE: 1, TEXT_EVIDENCE_PENDING_APPROVAL:wood: 3

Zonder materiaalbewijs: PO-DOC-009-P020-L103. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **wood**: 7 observations, 6 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-011, DOC-013, DOC-015: PO-DOC-011-P021-L025, PO-DOC-013-P018-L069, PO-DOC-015-S01-R0113
  - 20 cross-cluster paren zonder ACTIVE positieve beslissing (5 in de queue; families RF-4631-0514ebe15e, RF-4631-5b3207f54b, RF-4631-625ee73b91; niet in de queue: PAIR-00406, PAIR-00407, PAIR-00408, PAIR-00410, PAIR-00411, PAIR-00412, PAIR-00413, PAIR-00416, PAIR-00418, PAIR-00421, PAIR-00423, PAIR-00424, PAIR-00425, PAIR-00429, PAIR-00431)

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4631-5b3207f54b` | OBJECT_TEXT_VARIANT | 2 | OPEN_NO_DECISION | DOC-007, DOC-015 | - |
| `RF-4631-625ee73b91` | OBJECT_TEXT_VARIANT | 2 | OPEN_NO_DECISION | DOC-007, DOC-011 | - |
| `RF-4631-0514ebe15e` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-011, DOC-015 | - |

#### RF-4631-5b3207f54b - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: buitenschilderwerk kozijn raam hout dekkend m2 / groot schilderwerk kozijn raam hout dekkend / m2 / materiaal onbekend
- kant 2: buitenschilderwerk kozijn raam hout dekkend / groot schilderwerk kozijn raam hout dekkend / m2 / materiaal wood
- bewijs: OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT, MATERIAL_EVIDENCE_ONE_SIDE; paarcaveats {'ACTION_TEXT_VARIANT': 2, 'GENERIC_VS_SPECIFIC_OBJECT': 2}
- actieteksten: Groot schilderwerk kozijn & raam hout dekkend, Groot schilderwerk kozijn & raam hout dekkend achterzijde, Groot schilderwerk kozijn & raam hout dekkend voorzijde
- hoeveelheden: 391.30, 630; prijspeilen: 28-4-2023, None
- pair_ids: PAIR-00417, PAIR-00422
- family_input_sha256: `63ba2687993f95b05e781d601a286c179463e18c258d9aff17fb19c2fb8c4f85`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4631-625ee73b91 - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: buitenschilderwerk kozijn raam hout dekkend m2 bergingen / groot schilderwerk kozijn raam hout dekkend / m2 / materiaal onbekend
- kant 2: buitenschilderwerk kozijn raam hout dekkend / groot schilderwerk kozijn raam hout dekkend / m2 / materiaal wood
- bewijs: OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT, MATERIAL_EVIDENCE_ONE_SIDE, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'ACTION_TEXT_VARIANT': 2, 'GENERIC_VS_SPECIFIC_OBJECT': 2, 'QUANTITY_SCALE_DIFFERENCE': 2}
- actieteksten: Groot schilderwerk kozijn & raam hout dekkend, Groot schilderwerk kozijn & raam hout dekkend achterzijde, Groot schilderwerk kozijn & raam hout dekkend voorzijde
- hoeveelheden: 18.70, 391.30; prijspeilen: 28-4-2023, None
- pair_ids: PAIR-00415, PAIR-00420
- family_input_sha256: `6793b6d25a09b002acd302633d24b520cc8c7a72da87fd3acc0be401f796f435`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4631-0514ebe15e - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk kozijn raam hout dekkend m2 bergingen / groot schilderwerk kozijn raam hout dekkend / m2 / materiaal onbekend
- kant 2: buitenschilderwerk kozijn raam hout dekkend m2 / groot schilderwerk kozijn raam hout dekkend / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Groot schilderwerk kozijn & raam hout dekkend
- hoeveelheden: 18.70, 630; prijspeilen: None
- pair_ids: PAIR-00430
- family_input_sha256: `5a664a54a543f4b636f0ea2af4815b07e46f034768cf0a8dada7b58391ddf884`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 4711|replace|m1

- observations: 8 (independent_input: 8)
- source clusters (alle): 6; potentieel beschikbaar (independent_input): 6 - SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-012, SC-DOC-013
- paren: 26 (COMPARABLE_WITH_CAVEATS 4, NOT_COMPARABLE 1, UNKNOWN 21); in de reviewqueue: 4
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): KNOWN:aluminium: 1, KNOWN:zinc: 1, NO_MATERIAL_EVIDENCE: 3, TEXT_EVIDENCE_PENDING_APPROVAL:aluminium: 2, TEXT_EVIDENCE_PENDING_APPROVAL:zinc: 1

Zonder materiaalbewijs: PO-DOC-007-P018-L015, PO-DOC-007-P018-L033, PO-DOC-012-P014-L111. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **aluminium**: 3 observations, 3 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-011, DOC-012: PO-DOC-011-P021-L083, PO-DOC-012-P014-L107
  - 3 cross-cluster paren zonder ACTIVE positieve beslissing (3 in de queue; families RF-4711-72afa054e3, RF-4711-899cd9d239; niet in de queue: )
- materiaal **zinc**: 2 observations, 2 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-013: PO-DOC-013-P018-L087
  - 1 cross-cluster paren zonder ACTIVE positieve beslissing (1 in de queue; families RF-4711-b9d21ea6f1; niet in de queue: )
  - Minder dan 3 onafhankelijke source clusters; ook met alle beslissingen blijft dit INSUFFICIENT_DATA.

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4711-72afa054e3` | MATERIAL_EVIDENCE_ONE_SIDE | 2 | OPEN_NO_DECISION | DOC-008, DOC-011, DOC-012 | - |
| `RF-4711-899cd9d239` | EXACT_SAME_SEMANTIC_INPUT | 1 | OPEN_NO_DECISION | DOC-011, DOC-012 | - |
| `RF-4711-b9d21ea6f1` | MATERIAL_EVIDENCE_ONE_SIDE | 1 | OPEN_NO_DECISION | DOC-005, DOC-013 | - |

#### RF-4711-72afa054e3 - MATERIAL_EVIDENCE_ONE_SIDE (2 paren)

- kant 1: dakrandafwerking aluminium trim / vervangen daktrim aluminium / m1 / materiaal aluminium
- kant 2: dakrandafwerking aluminium trim / vervangen daktrim aluminium / m1 / materiaal onbekend
- bewijs: MATERIAL_EVIDENCE_ONE_SIDE; paarcaveats -
- actieteksten: Vervangen daktrim aluminium
- hoeveelheden: 119.60, 152.54, 250.20; prijspeilen: 1-4-2024, None
- pair_ids: PAIR-00557, PAIR-00558
- family_input_sha256: `35bdc7228c0e3ab30102c80871d56581445fdf2884574bb53e29f459adb71c16`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4711-899cd9d239 - EXACT_SAME_SEMANTIC_INPUT (1 paren)

- kant 1: dakrandafwerking aluminium trim / vervangen daktrim aluminium / m1 / materiaal onbekend
- kant 2: dakrandafwerking aluminium trim / vervangen daktrim aluminium / m1 / materiaal onbekend
- bewijs: EXACT_SAME_SEMANTIC_INPUT; paarcaveats -
- actieteksten: Vervangen daktrim aluminium
- hoeveelheden: 152.54, 250.20; prijspeilen: 1-4-2024, None
- pair_ids: PAIR-00561
- family_input_sha256: `ab9072e8776de299ae1d3fdb5fbb776566743c2bf4f1dd41aa77333e3f745b2c`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4711-b9d21ea6f1 - MATERIAL_EVIDENCE_ONE_SIDE (1 paren)

- kant 1: dakrandafwerking zink / vervangen dakrandafwerking zink / m1 / materiaal zinc
- kant 2: dakrandafwerking zink / vervangen dakrandafwerking zink / m1 / materiaal onbekend
- bewijs: MATERIAL_EVIDENCE_ONE_SIDE; paarcaveats -
- actieteksten: Vervangen dakrandafwerking zink
- hoeveelheden: 17.80, 70.00; prijspeilen: 1-8-2026, 14-7-2026
- pair_ids: PAIR-00546
- family_input_sha256: `20eab5c1e2d3544404ae04fe2e9ee19e192796d0b8fa0c77c174f0064bea0a3c`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 4628|exterior_painting|m2

- observations: 5 (independent_input: 5)
- source clusters (alle): 4; potentieel beschikbaar (independent_input): 4 - SC-DOC-001, SC-DOC-007, SC-DOC-011, SC-DOC-012
- paren: 9 (COMPARABLE_WITH_CAVEATS 4, UNKNOWN 5); in de reviewqueue: 4
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): NO_MATERIAL_EVIDENCE: 5

Zonder materiaalbewijs: PO-DOC-001-P025-L081, PO-DOC-007-P017-L031, PO-DOC-007-P017-L035, PO-DOC-011-P021-L019, PO-DOC-012-P014-L057. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

Geen enkel materiaal is vastgesteld of afleidbaar; eerst materiaal via verified-element vastleggen (regel 12).


### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4628-8ef58bc3e8` | OBJECT_TEXT_VARIANT | 2 | OPEN_NO_DECISION | DOC-007, DOC-011 | - |
| `RF-4628-cfef08c95e` | OBJECT_TEXT_VARIANT | 2 | OPEN_NO_DECISION | DOC-007, DOC-012 | - |

#### RF-4628-8ef58bc3e8 - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: buitenschilderwerk betonconstructie kolommen berging balkon / groot schilderwerk steenachtig / m2 / materiaal onbekend
- kant 2: buitenschilderwerk betonconstructie / groot schilderwerk steenachtig / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT; paarcaveats {'ACTION_TEXT_VARIANT': 2, 'GENERIC_VS_SPECIFIC_OBJECT': 2}
- actieteksten: Groot schilderwerk steenachtig, Groot schilderwerk steenachtig achterzijde, Groot schilderwerk steenachtig voorzijde
- hoeveelheden: 78.60, 278.00; prijspeilen: 28-4-2023, None
- pair_ids: PAIR-00389, PAIR-00391
- family_input_sha256: `82efbb06d97d1ef14d058cdcddf99cfa0120ee6a2a2da304c024701b700ad0ee`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4628-cfef08c95e - OBJECT_TEXT_VARIANT (2 paren)

- kant 1: buitenschilderwerk betonconstructie betonband / groot schilderwerk steenachtig / m2 / materiaal onbekend
- kant 2: buitenschilderwerk betonconstructie / groot schilderwerk steenachtig / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT; paarcaveats {'ACTION_TEXT_VARIANT': 2, 'GENERIC_VS_SPECIFIC_OBJECT': 2, 'PRICE_LEVEL_DIFFERENCE': 2}
- actieteksten: Groot schilderwerk steenachtig, Groot schilderwerk steenachtig achterzijde, Groot schilderwerk steenachtig voorzijde
- hoeveelheden: 47.88, 278.00; prijspeilen: 1-4-2024, 28-4-2023
- pair_ids: PAIR-00390, PAIR-00392
- family_input_sha256: `f2a462ad8742d424016462115109fc59ca2e243fe3383445a61708b6de5a973a`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 4634|exterior_painting|m2

- observations: 6 (independent_input: 6)
- source clusters (alle): 4; potentieel beschikbaar (independent_input): 4 - SC-DOC-002, SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-012
- paren: 12 (COMPARABLE_WITH_CAVEATS 2, UNKNOWN 10); in de reviewqueue: 2
- ACTIVE decisions: -
- bestaande kengetallen: -
- materiaalbewijs (independent_input): NO_MATERIAL_EVIDENCE: 5, TEXT_EVIDENCE_PENDING_APPROVAL:wood: 1

Zonder materiaalbewijs: PO-DOC-002-P019-L049, PO-DOC-009-P021-L015, PO-DOC-009-P021-L019, PO-DOC-009-P021-L021, PO-DOC-011-P021-L033. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

- materiaal **wood**: 1 observations, 1 potentiële clusters, status `REQUIRES_HUMAN_STEPS`
  - materiaalgoedkeuring nodig voor DOC-012: PO-DOC-012-P014-L071
  - Minder dan 3 onafhankelijke source clusters; ook met alle beslissingen blijft dit INSUFFICIENT_DATA.

### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-4634-77c2e5b5b4` | OBJECT_TEXT_VARIANT | 1 | OPEN_NO_DECISION | DOC-002, DOC-011 | - |
| `RF-4634-ae803a9ef7` | ACTION_TEXT_VARIANT | 1 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED | DOC-002, DOC-009 | HDR-00009 |

#### RF-4634-77c2e5b5b4 - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk hek metaal balkons / groot schilderwerk hek staal / m2 / materiaal onbekend
- kant 2: buitenschilderwerk hek metaal / groot schilderwerk hek staal / m2 / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Groot schilderwerk hek staal
- hoeveelheden: 3.00, 753.00; prijspeilen: 20-8-2026, None
- pair_ids: PAIR-00447
- family_input_sha256: `30aae6607dd1cf8c43763d1af40f8a9030136cb8a88be8641469066e6666e83a`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-4634-ae803a9ef7 - ACTION_TEXT_VARIANT (1 paren)

- kant 1: buitenschilderwerk hek metaal / groot schilderwerk hek staal / m2 / materiaal onbekend
- kant 2: buitenschilderwerk hek metaal / groot schilderwerk hek staal / m2 / materiaal onbekend
- bewijs: ACTION_TEXT_VARIANT, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1, 'PRICE_LEVEL_DIFFERENCE': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Groot schilderwerk hek staal
- hoeveelheden: 3.00, 59.49; prijspeilen: 20-8-2026, 21-4-2025
- pair_ids: PAIR-00444
- family_input_sha256: `b50aafea74193626a4b590a7f3a1af762a11bc159148b9ac2ca6774d6da83314`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## 6311|replace|piece

- observations: 8 (independent_input: 8)
- source clusters (alle): 4; potentieel beschikbaar (independent_input): 4 - SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-011
- paren: 24 (COMPARABLE_WITH_CAVEATS 2, UNKNOWN 22); in de reviewqueue: 2
- ACTIVE decisions: HDR-00034, HDR-00035
- bestaande kengetallen: -
- materiaalbewijs (independent_input): NO_MATERIAL_EVIDENCE: 8

Zonder materiaalbewijs: PO-DOC-007-P018-L079, PO-DOC-007-P018-L087, PO-DOC-009-P022-L033, PO-DOC-009-P022-L043, PO-DOC-010-P013-L035, PO-DOC-010-P013-L039, PO-DOC-011-P022-L045, PO-DOC-011-P022-L049. Geen vastgesteld materiaal en de bestaande tekstregel vindt er ook geen: zonder menselijke verificatie van het elementmateriaal kan deze observation volgens regel 12 in geen enkel kengetal meetellen.

### Wat ontbreekt voor een geldige knowledge candidate

Geen enkel materiaal is vastgesteld of afleidbaar; eerst materiaal via verified-element vastleggen (regel 12).


### Reviewfamilies

| familie | categorie | paren | status | documenten | bestaande beslissingen |
|---|---|---|---|---|---|
| `RF-6311-2fd769e3c6` | OTHER_REVIEW_REQUIRED | 1 | DECIDED_ACTIVE | DOC-007, DOC-009 | HDR-00021, HDR-00034 |
| `RF-6311-45bc691feb` | OBJECT_TEXT_VARIANT | 1 | DECIDED_ACTIVE | DOC-007, DOC-009 | HDR-00022, HDR-00035 |

#### RF-6311-2fd769e3c6 - OTHER_REVIEW_REQUIRED (1 paren)

- kant 1: elektra armaturen binnenlamp trappenhuizen / vervangen armaturen binnenlamp led / st / materiaal onbekend
- kant 2: elektra armaturen binnenlamp / vervangen armaturen binnenlamp / st / materiaal onbekend
- bewijs: OTHER_REVIEW_REQUIRED, OBJECT_TEXT_VARIANT, ACTION_TEXT_VARIANT; paarcaveats {'ACTION_TEXT_VARIANT': 1, 'GENERIC_VS_SPECIFIC_OBJECT': 1, 'PRICE_LEVEL_DIFFERENCE': 1}
- actieteksten: Vervangen armaturen binnenlamp, Vervangen armaturen binnenlamp LED
- hoeveelheden: 21.00, 40.00; prijspeilen: 21-4-2025, 28-4-2023
- pair_ids: PAIR-00660
- family_input_sha256: `e7b8cbf087f8df902f67a12fe3c3bbfcc92e770404457fdc5d1af3d508355384`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

#### RF-6311-45bc691feb - OBJECT_TEXT_VARIANT (1 paren)

- kant 1: elektra armaturen binnenlamp alg ruimte bergingen / vervangen armaturen binnenlamp / st / materiaal onbekend
- kant 2: elektra armaturen binnenlamp / vervangen armaturen binnenlamp / st / materiaal onbekend
- bewijs: OBJECT_TEXT_VARIANT, QUANTITY_SCALE_DIFFERENCE; paarcaveats {'GENERIC_VS_SPECIFIC_OBJECT': 1, 'PRICE_LEVEL_DIFFERENCE': 1, 'QUANTITY_SCALE_DIFFERENCE': 1}
- actieteksten: Vervangen armaturen binnenlamp
- hoeveelheden: 1.00, 40.00; prijspeilen: 21-4-2025, 28-4-2023
- pair_ids: PAIR-00661
- family_input_sha256: `42e075eb1d76c1d1764035ef3dd50f940426644edc3f42df8196d615aa3da025`
- blijft ook na een positieve beslissing blokkeren: MATERIAL_UNKNOWN

## Overige families (buiten de 9 kandidaatgroepen)

| familie | groep | categorie | paren | status |
|---|---|---|---|---|
| `RF-2110-0d074135b4` | 2110|impregnate|m2 | ACTION_TEXT_VARIANT | 2 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED |
| `RF-2716-4641f9baf5` | 2716|clean|m1 | MATERIAL_EVIDENCE_ONE_SIDE | 1 | OPEN_NO_DECISION |
| `RF-2716-e2d3846b4b` | 2716|replace|m1 | MATERIAL_EVIDENCE_ONE_SIDE | 1 | OPEN_NO_DECISION |
| `RF-4321-e60499fe10` | 4321|replace|m2 | OBJECT_TEXT_VARIANT | 1 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED |
| `RF-4634-55c895765a` | 4634|interior_painting|m2 | MATERIAL_EVIDENCE_ONE_SIDE | 2 | OPEN_NO_DECISION |
| `RF-4711-f3bf3537a4` | 4711|install|m2 | ACTION_TEXT_VARIANT | 1 | OPEN_NO_DECISION |
| `RF-4711-40377f0bc8` | 4711|replace|m2 | OBJECT_TEXT_VARIANT | 1 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED |
| `RF-4711-a21389e8cd` | 4711|replace|m2 | OBJECT_TEXT_VARIANT | 1 | OPEN_PREVIOUS_DECISION_REVIEW_REQUIRED |
| `RF-5314-7d965b0af5` | 5314|replace|piece | EXACT_SAME_SEMANTIC_INPUT | 2 | OPEN_NO_DECISION |
| `RF-6710-00645f3dad` | 6710|install|piece | QUANTITY_SCALE_DIFFERENCE | 1 | OPEN_NO_DECISION |
| `RF-8111-0a8cdc9451` | 8111|replace|piece | QUANTITY_SCALE_DIFFERENCE | 1 | OPEN_NO_DECISION |

## Toegestane keuzes (bestaand model)

- `COMPARABLE`: Vergelijkbaar zonder voorbehoud.
- `COMPARABLE_WITH_CAVEATS`: Vergelijkbaar, met de gekozen voorbehouden (decision_caveats).
- `NOT_COMPARABLE`: Niet vergelijkbaar.
- `UNKNOWN`: Niet te beoordelen met het beschikbare bewijs.

Het effect per keuze staat per familie in `comparability_review_v2.json` (`allowed_human_choices`).
