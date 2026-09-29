# Kengetal-readiness v1

Alleen analyse: niets toegepast, geen scoring of confidence. materiaalgoedkeuringen (één per observation) + familiebesluiten (één per open reviewfamilie na materiaalgoedkeuring) + paarbesluiten buiten de reviewqueue (één per paar; daarvoor bestaat in de huidige keten nog geen schakel).

## Samenvatting

- candidate groups: **114** (91 candidate keys met independent_input, 268 observations)
- materiaalgoedkeuringen mogelijk via record_material_decision: 33; geweigerd: 0
- candidate keys zonder independent_input (geen candidate group): 97 (414 observations; redenen ELIGIBILITY_NOT_ELIGIBLE 226, ELIGIBILITY_UNKNOWN 22, NO_DERIVED_PRICE 162, POSSIBLY_DEPENDENT 4)

| readiness | groepen |
|---|---|
| AVAILABLE | 2 |
| READY_AFTER_REVIEW | 0 |
| MATERIAL_APPROVAL_NEEDED | 0 |
| MATERIAL_AND_REVIEW_NEEDED | 0 |
| INSUFFICIENT_CLUSTERS | 99 |
| BLOCKED_OTHER | 13 |

Groepen die met de bestaande ketenschakels (record_material_decision + apply_family_decision) volledig af te ronden zijn: **geen**.

Minste werk onder de eerstvolgende groepen: **4645|interior_painting|m2|wood** (6 menselijke acties; blockers MATERIAL_APPROVAL_NEEDED, PAIRS_OUTSIDE_REVIEW_QUEUE).

## Eerstvolgende 5 niet-AVAILABLE groepen

Definitie: de eerste niet-AVAILABLE groepen in sorteervolgorde waarvoor build_kengetallen na alle menselijke stappen AVAILABLE geeft.

### 50. 4645|interior_painting|m2|wood - BLOCKED_OTHER

- observations: PO-DOC-006-P015-L059, PO-DOC-007-P017-L097, PO-DOC-012-P014-L085
- clusters nu 3; na afronding 3 (SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-012)
- materiaalreview nodig: PO-DOC-006-P015-L059, PO-DOC-007-P017-L097, PO-DOC-012-P014-L085
- open reviewfamilies nu: -
- te beslissen families na materiaalgoedkeuring: -
- paren buiten de reviewqueue: PAIR-00529, PAIR-00531, PAIR-00533
- blockers: MATERIAL_APPROVAL_NEEDED, PAIRS_OUTSIDE_REVIEW_QUEUE
- menselijke acties: 6 (materiaal 3, families 0, paren buiten queue 3)
- verwacht kengetal-effect: AVAILABLE 45.81 (3 clusters; min 44.18, max 54.45, gemengde prijspeilen)
- direct AVAILABLE na deze stappen: nee

### 51. 4632|interior_painting|m2|wood - BLOCKED_OTHER

- observations: PO-DOC-002-P019-L019, PO-DOC-002-P019-L035, PO-DOC-007-P017-L055, PO-DOC-012-P014-L063, PO-DOC-013-P020-L019
- clusters nu 4; na afronding 4 (SC-DOC-002, SC-DOC-007, SC-DOC-012, SC-DOC-013)
- materiaalreview nodig: PO-DOC-012-P014-L063, PO-DOC-013-P020-L019
- open reviewfamilies nu: -
- te beslissen families na materiaalgoedkeuring: -
- paren buiten de reviewqueue: PAIR-00432, PAIR-00433, PAIR-00434, PAIR-00438, PAIR-00439, PAIR-00440, PAIR-00441, PAIR-00442, PAIR-00443
- blockers: MATERIAL_APPROVAL_NEEDED, PAIRS_OUTSIDE_REVIEW_QUEUE
- menselijke acties: 11 (materiaal 2, families 0, paren buiten queue 9)
- verwacht kengetal-effect: AVAILABLE 40.53 (4 clusters; min 37.25, max 44.18, gemengde prijspeilen)
- direct AVAILABLE na deze stappen: nee

### 52. 4622|interior_painting|m2|wood - BLOCKED_OTHER

- observations: PO-DOC-002-P018-L045, PO-DOC-002-P018-L077, PO-DOC-007-P017-L019, PO-DOC-009-P020-L041, PO-DOC-010-P012-L023, PO-DOC-011-P020-L091
- clusters nu 5; na afronding 5 (SC-DOC-002, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-010, SC-DOC-011)
- materiaalreview nodig: PO-DOC-011-P020-L091
- open reviewfamilies nu: -
- te beslissen families na materiaalgoedkeuring: -
- paren buiten de reviewqueue: PAIR-00250, PAIR-00253, PAIR-00256, PAIR-00257, PAIR-00272, PAIR-00275, PAIR-00278, PAIR-00279, PAIR-00304, PAIR-00307, PAIR-00308, PAIR-00325, PAIR-00326, PAIR-00335
- blockers: MATERIAL_APPROVAL_NEEDED, PAIRS_OUTSIDE_REVIEW_QUEUE
- menselijke acties: 15 (materiaal 1, families 0, paren buiten queue 14)
- verwacht kengetal-effect: AVAILABLE 46.52 (5 clusters; min 39.60, max 86.26, gemengde prijspeilen, ontbrekend prijspeil)
- direct AVAILABLE na deze stappen: nee

### 113. 4631|exterior_painting|m2|wood - BLOCKED_OTHER

- observations: PO-DOC-006-P015-L049, PO-DOC-007-P017-L043, PO-DOC-007-P017-L047, PO-DOC-009-P020-L093, PO-DOC-011-P021-L025, PO-DOC-013-P018-L069, PO-DOC-015-S01-R0113
- clusters nu 6; na afronding 6 (SC-DOC-005+DOC-006, SC-DOC-007, SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-013, SC-DOC-015)
- materiaalreview nodig: PO-DOC-011-P021-L025, PO-DOC-013-P018-L069, PO-DOC-015-S01-R0113
- open reviewfamilies nu: RF-4631-0514ebe15e, RF-4631-5b3207f54b, RF-4631-625ee73b91
- te beslissen families na materiaalgoedkeuring: RF-4631-474ed3a23f (PAIR-00415, PAIR-00420), RF-4631-a76b249460 (PAIR-00417, PAIR-00422), RF-4631-be40178fc5 (PAIR-00430)
- paren buiten de reviewqueue: PAIR-00406, PAIR-00407, PAIR-00408, PAIR-00410, PAIR-00411, PAIR-00412, PAIR-00413, PAIR-00416, PAIR-00418, PAIR-00421, PAIR-00423, PAIR-00424, PAIR-00425, PAIR-00429, PAIR-00431
- blockers: MATERIAL_APPROVAL_NEEDED, CROSS_CLUSTER_REVIEW_NEEDED, PAIRS_OUTSIDE_REVIEW_QUEUE
- menselijke acties: 21 (materiaal 3, families 3, paren buiten queue 15)
- verwacht kengetal-effect: AVAILABLE 58.47 (6 clusters; min 51.76, max 136.25, gemengde prijspeilen, ontbrekend prijspeil)
- direct AVAILABLE na deze stappen: nee

### 114. 4621|exterior_painting|m2|wood - BLOCKED_OTHER

- observations: PO-DOC-001-P025-L025, PO-DOC-002-P017-L045, PO-DOC-002-P017-L109, PO-DOC-002-P017-L115, PO-DOC-006-P015-L009, PO-DOC-010-P011-L085, PO-DOC-011-P020-L067, PO-DOC-012-P014-L013, PO-DOC-013-P018-L059
- clusters nu 7; na afronding 7 (SC-DOC-001, SC-DOC-002, SC-DOC-005+DOC-006, SC-DOC-010, SC-DOC-011, SC-DOC-012, SC-DOC-013)
- materiaalreview nodig: PO-DOC-011-P020-L067, PO-DOC-012-P014-L013, PO-DOC-013-P018-L059
- open reviewfamilies nu: RF-4621-b30de14ab7
- te beslissen families na materiaalgoedkeuring: RF-4621-40b6e91317 (PAIR-00233)
- paren buiten de reviewqueue: PAIR-00054, PAIR-00056, PAIR-00057, PAIR-00065, PAIR-00066, PAIR-00068, PAIR-00071, PAIR-00072, PAIR-00115, PAIR-00116, PAIR-00118, PAIR-00121, PAIR-00122, PAIR-00139, PAIR-00140, PAIR-00142, PAIR-00145, PAIR-00146, PAIR-00151, PAIR-00152, PAIR-00154, PAIR-00157, PAIR-00158, PAIR-00223, PAIR-00225, PAIR-00228, PAIR-00229, PAIR-00230, PAIR-00234, PAIR-00240, PAIR-00241, PAIR-00246
- blockers: MATERIAL_APPROVAL_NEEDED, CROSS_CLUSTER_REVIEW_NEEDED, PAIRS_OUTSIDE_REVIEW_QUEUE
- menselijke acties: 36 (materiaal 3, families 1, paren buiten queue 32)
- verwacht kengetal-effect: AVAILABLE 53.17 (7 clusters; min 36.62, max 92.75, gemengde prijspeilen, ontbrekend prijspeil)
- direct AVAILABLE na deze stappen: nee

## Alle candidate groups

| # | candidate group | readiness | materiaal (bekend/wacht/geen) | obs | clusters nu -> na | ACTIVE besluiten | open families nu | materiaalgoedkeuring | overige blockers | acties | direct AVAILABLE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 5211|replace|m1|pvc | AVAILABLE | 5/0/0 | 5 | 5 -> 5 | 10 | 0 | 0 | - | 0 | ja |
| 2 | 4711|replace|m1|aluminium | AVAILABLE | 3/0/0 | 3 | 3 -> 3 | 3 | 0 | 0 | - | 0 | ja |
| 3 | 2110|clean|m2|natural_stone | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 4 | 2120|inspect|m2|steel | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 5 | 2410|clean|piece|steel | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 6 | 2716|repair|m1|wood | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 7 | 2810|repair|piece|steel | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 8 | 3120|clean|m2|aluminium | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 9 | 3120|maintain|piece|pvc | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 10 | 3120|repair|m1|wood | INSUFFICIENT_CLUSTERS | 4/0/0 | 4 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 11 | 3120|replace|m2|pvc | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 12 | 3122|repair|piece|wood | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 13 | 3231|repair|piece|wood | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 14 | 3410|replace|m1|steel | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 15 | 3431|repair|m1|wood | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 16 | 4112|repair|m2|wood | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 17 | 4621|exterior_painting|m1|steel | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 18 | 4621|exterior_painting|m1|wood | INSUFFICIENT_CLUSTERS | 7/0/0 | 7 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 19 | 4621|exterior_painting|piece|steel | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 20 | 4621|exterior_painting|piece|wood | INSUFFICIENT_CLUSTERS | 4/0/0 | 4 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 21 | 4621|install|m1|steel | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 22 | 4622|interior_painting|piece|wood | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 23 | 4628|exterior_painting|m1|concrete | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 24 | 4632|interior_painting|m2|aluminium | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 25 | 4634|interior_painting|m1|wood | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 26 | 4711|replace|m2|bitumen | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 27 | 5211|replace|piece|pvc | INSUFFICIENT_CLUSTERS | 1/0/0 | 1 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 28 | 5211|replace|piece|steel | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 29 | 5710|replace|piece|zinc | INSUFFICIENT_CLUSTERS | 2/0/0 | 2 | 1 -> 1 | 0 | 0 | 0 | INSUFFICIENT_CLUSTERS | 0 | nee |
| 30 | 4645|exterior_painting|m2|unknown | BLOCKED_OTHER | 0/0/10 | 10 | 6 -> 6 | 0 | 4 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 31 | 4622|interior_painting|m2|unknown | BLOCKED_OTHER | 0/0/9 | 9 | 5 -> 5 | 0 | 5 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 32 | 4621|exterior_painting|m2|unknown | BLOCKED_OTHER | 0/0/9 | 9 | 4 -> 4 | 0 | 2 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 33 | 4628|exterior_painting|m1|unknown | BLOCKED_OTHER | 0/0/6 | 6 | 4 -> 4 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 34 | 4628|exterior_painting|m2|unknown | BLOCKED_OTHER | 0/0/5 | 5 | 4 -> 4 | 0 | 2 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 35 | 6311|replace|piece|unknown | BLOCKED_OTHER | 0/0/8 | 8 | 4 -> 4 | 2 | 0 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 36 | 4634|exterior_painting|m2|unknown | BLOCKED_OTHER | 0/0/5 | 5 | 3 -> 3 | 0 | 2 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 37 | 5211|replace|piece|unknown | BLOCKED_OTHER | 0/0/4 | 4 | 3 -> 3 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE | - | nee |
| 38 | 2716|replace|m1|pvc | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 39 | 3120|clean|m2|pvc | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 40 | 3720|replace|m2|steel | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 41 | 4634|exterior_painting|m2|wood | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 42 | 4711|repair|piece|bitumen | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 43 | 4712|replace|m2|bitumen | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 44 | 4712|replace|m2|zinc | INSUFFICIENT_CLUSTERS | 0/1/0 | 1 | 1 -> 1 | 0 | 0 | 1 | INSUFFICIENT_CLUSTERS | 1 | nee |
| 45 | 4624|interior_painting|m2|wood | INSUFFICIENT_CLUSTERS | 3/0/0 | 3 | 2 -> 2 | 0 | 0 | 0 | PAIRS_OUTSIDE_REVIEW_QUEUE, INSUFFICIENT_CLUSTERS | 2 | nee |
| 46 | 2121|repair|m2|concrete | INSUFFICIENT_CLUSTERS | 0/2/0 | 2 | 1 -> 1 | 0 | 0 | 2 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 47 | 3721|replace|piece|pvc | INSUFFICIENT_CLUSTERS | 0/2/0 | 2 | 1 -> 1 | 0 | 0 | 2 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 48 | 4623|exterior_painting|m2|concrete | INSUFFICIENT_CLUSTERS | 0/3/0 | 3 | 1 -> 1 | 0 | 0 | 3 | INSUFFICIENT_CLUSTERS | 3 | nee |
| 49 | 4631|exterior_painting|m1|wood | INSUFFICIENT_CLUSTERS | 5/0/0 | 5 | 2 -> 2 | 0 | 0 | 0 | PAIRS_OUTSIDE_REVIEW_QUEUE, INSUFFICIENT_CLUSTERS | 4 | nee |
| 50 | 4645|interior_painting|m2|wood | BLOCKED_OTHER | 0/3/0 | 3 | 3 -> 3 | 0 | 0 | 3 | PAIRS_OUTSIDE_REVIEW_QUEUE | 6 | nee |
| 51 | 4632|interior_painting|m2|wood | BLOCKED_OTHER | 3/2/0 | 5 | 4 -> 4 | 0 | 0 | 2 | PAIRS_OUTSIDE_REVIEW_QUEUE | 11 | nee |
| 52 | 4622|interior_painting|m2|wood | BLOCKED_OTHER | 5/1/0 | 6 | 5 -> 5 | 0 | 0 | 1 | PAIRS_OUTSIDE_REVIEW_QUEUE | 15 | nee |
| 53 | 2110|impregnate|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 1 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 54 | 2110|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 55 | 2110|replace|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 56 | 3120|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/6 | 6 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 57 | 4111|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 58 | 4321|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 1 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 59 | 4622|interior_painting|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 60 | 4623|install|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 61 | 4623|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 62 | 4628|interior_painting|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 63 | 4711|install|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 1 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 64 | 4711|replace|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 65 | 4711|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/4 | 4 | 2 -> 2 | 0 | 2 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 66 | 5314|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/3 | 3 | 2 -> 2 | 0 | 1 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 67 | 6710|install|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 1 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 68 | 8111|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 2 -> 2 | 0 | 1 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 69 | 2110|repair|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 70 | 2120|inspect|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 71 | 2321|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 72 | 2716|clean|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 73 | 2716|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 74 | 3120|clean|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 75 | 3120|replace|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 76 | 3231|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 77 | 3410|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 78 | 3720|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 79 | 3721|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 80 | 4112|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 81 | 4211|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 82 | 4320|install|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 83 | 4320|replace|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 84 | 4320|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 85 | 4322|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 86 | 4511|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 87 | 4521|repair|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 88 | 4621|exterior_painting|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 89 | 4623|replace|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 90 | 4631|exterior_painting|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 91 | 4634|exterior_painting|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 92 | 4634|interior_painting|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 93 | 4645|interior_painting|m2|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 94 | 4711|install|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 95 | 5124|clean|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 96 | 5124|install|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 97 | 5124|repair|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 98 | 5124|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 99 | 5216|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 100 | 5610|replace|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 101 | 5610|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 102 | 6411|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 103 | 6511|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 104 | 6513|replace|piece|unknown | INSUFFICIENT_CLUSTERS | 0/0/2 | 2 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 105 | 9032|replace|m1|unknown | INSUFFICIENT_CLUSTERS | 0/0/1 | 1 | 1 -> 1 | 0 | 0 | 0 | NO_MATERIAL_EVIDENCE, INSUFFICIENT_CLUSTERS | - | nee |
| 106 | 2716|clean|m1|zinc | INSUFFICIENT_CLUSTERS | 1/1/0 | 2 | 2 -> 2 | 0 | 1 | 1 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 107 | 2716|replace|m1|zinc | INSUFFICIENT_CLUSTERS | 1/1/0 | 2 | 2 -> 2 | 0 | 1 | 1 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 108 | 4634|interior_painting|m2|wood | INSUFFICIENT_CLUSTERS | 2/1/0 | 3 | 2 -> 2 | 0 | 1 | 1 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 109 | 4645|exterior_painting|m2|wood | INSUFFICIENT_CLUSTERS | 1/1/0 | 2 | 2 -> 2 | 0 | 1 | 1 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 110 | 4711|replace|m1|zinc | INSUFFICIENT_CLUSTERS | 1/1/0 | 2 | 2 -> 2 | 0 | 1 | 1 | PAIRS_OUTSIDE_REVIEW_QUEUE, INSUFFICIENT_CLUSTERS | 2 | nee |
| 111 | 5211|replace|m1|steel | INSUFFICIENT_CLUSTERS | 1/1/0 | 2 | 2 -> 2 | 0 | 1 | 1 | INSUFFICIENT_CLUSTERS | 2 | nee |
| 112 | 4622|interior_painting|m1|wood | INSUFFICIENT_CLUSTERS | 2/1/0 | 3 | 2 -> 2 | 0 | 0 | 1 | PAIRS_OUTSIDE_REVIEW_QUEUE, INSUFFICIENT_CLUSTERS | 3 | nee |
| 113 | 4631|exterior_painting|m2|wood | BLOCKED_OTHER | 4/3/0 | 7 | 6 -> 6 | 0 | 3 | 3 | PAIRS_OUTSIDE_REVIEW_QUEUE | 21 | nee |
| 114 | 4621|exterior_painting|m2|wood | BLOCKED_OTHER | 6/3/0 | 9 | 7 -> 7 | 0 | 1 | 3 | PAIRS_OUTSIDE_REVIEW_QUEUE | 36 | nee |

Alleen analyse: geen besluit, geen materiaal, geen kengetal toegepast; geen scoring of confidence. Materiaalgoedkeuringen en de toestand daarna zijn gesimuleerd op een tijdelijke kopie; reviewfamily-ids en family_input_sha256 na goedkeuring zijn indicatief (het echte familiebesluit bindt aan comparability_review_v2.json na het echte materiaalbesluit). Kengetal-effecten komen uitsluitend uit build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische ACTIVE COMPARABLE_WITH_CAVEATS-records voor alle ontbrekende cross-cluster paren.
