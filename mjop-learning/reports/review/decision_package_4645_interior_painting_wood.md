# Beslispakket 4645|interior_painting|m2|wood

READ-ONLY beslispakket: niets toegepast (geen materiaalbesluit, geen paar- of familiebesluit, geen kengetal). Materiaal-precheck via record_material_decision.validate (schrijft niets); de toestand na het materiaalbesluit is gesimuleerd op een tijdelijke kopie, dus family-ids en family_input_sha256 na het materiaalbesluit zijn indicatief - het echte familiebesluit bindt aan comparability_review_v2.json zoals dat NA het echte materiaalbesluit wordt herbouwd. Simulaties uitsluitend met build_kengetallen.evaluate (kengetallen_rules_v1).

Readiness: rang 50, MATERIAL_AND_REVIEW_NEEDED; blockers MATERIAL_APPROVAL_NEEDED, CROSS_CLUSTER_REVIEW_NEEDED; menselijke acties 6.

ID-controle: observations gelijk aan het readiness-rapport, paren gelijk.

## MATERIAL

| observation | document | cluster | bron | objectomschrijving | actietekst | eenheid | huidig materiaal | voorgesteld | record_material_decision |
|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-006-P015-L059 | DOC-006 | SC-DOC-005+DOC-006 | p15 r59: `Groot schilderwerk plafond hout 85,70 m2 2032 12 4.666 4.666` | Binnenschilderwerk plafond hout (multiplex) dekkend | Groot schilderwerk plafond hout dekkend | m2 | onbekend (-) | wood (woord 'hout') | WOULD_BE_ACCEPTED |
| PO-DOC-007-P017-L097 | DOC-007 | SC-DOC-007 | p17 r97: `Groot schilderwerk plafond hout 580,00 m2 2030 14 25.623 25.623` | Binnenschilderwerk plafond hout / stucwerk dekkend | Groot schilderwerk plafond hout dekkend | m2 | onbekend (-) | wood (woord 'hout') | WOULD_BE_ACCEPTED |
| PO-DOC-012-P014-L085 | DOC-012 | SC-DOC-012 | p14 r85: `Groot schilderwerk plafond hout 12,90 m2 2027 18 591 591` | Binnenschilderwerk plafond hout transparant | Groot schilderwerk plafond hout transparant | m2 | onbekend (-) | wood (woord 'hout') | WOULD_BE_ACCEPTED |

## PAIRS

### PAIR-00529: DOC-006 x DOC-007

- observations: PO-DOC-006-P015-L059 (SC-DOC-005+DOC-006) x PO-DOC-007-P017-L097 (SC-DOC-007)
- brontekst a: `Groot schilderwerk plafond hout 85,70 m2 2032 12 4.666 4.666`
- brontekst b: `Groot schilderwerk plafond hout 580,00 m2 2030 14 25.623 25.623`
- objecttekst: 'Binnenschilderwerk plafond hout (multiplex) dekkend' vs 'Binnenschilderwerk plafond hout / stucwerk dekkend' (alleen a: ['multiplex']; alleen b: ['stucwerk'])
- actietekst: 'Groot schilderwerk plafond hout dekkend' vs 'Groot schilderwerk plafond hout dekkend'
- hoeveelheid: 85.70 vs 580.00; prijs per uitvoering: 54.45 vs 44.18; prijspeil: 1-3-2023 vs 28-4-2023
- system_class: **UNKNOWN**; unknown_reasons: OBJECT_EQUIVALENCE_REQUIRES_REVIEW; hard violations: -
- caveats: paar -; observations a MATERIAL_UNKNOWN, b MATERIAL_UNKNOWN
- UNKNOWN-reviewtrack nu: geblokkeerd door MATERIAL_UNKNOWN
- na het materiaalbesluit: system_class UNKNOWN; caveats observations a -, b -; reviewbaar, familie RF-4645-f273568c78

### PAIR-00531: DOC-006 x DOC-012

- observations: PO-DOC-006-P015-L059 (SC-DOC-005+DOC-006) x PO-DOC-012-P014-L085 (SC-DOC-012)
- brontekst a: `Groot schilderwerk plafond hout 85,70 m2 2032 12 4.666 4.666`
- brontekst b: `Groot schilderwerk plafond hout 12,90 m2 2027 18 591 591`
- objecttekst: 'Binnenschilderwerk plafond hout (multiplex) dekkend' vs 'Binnenschilderwerk plafond hout transparant' (alleen a: ['dekkend', 'multiplex']; alleen b: ['transparant'])
- actietekst: 'Groot schilderwerk plafond hout dekkend' vs 'Groot schilderwerk plafond hout transparant' (alleen a: ['dekkend']; alleen b: ['transparant'])
- hoeveelheid: 85.70 vs 12.90; prijs per uitvoering: 54.45 vs 45.81; prijspeil: 1-3-2023 vs 1-4-2024
- system_class: **UNKNOWN**; unknown_reasons: OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW; hard violations: -
- caveats: paar PRICE_LEVEL_DIFFERENCE; observations a MATERIAL_UNKNOWN, b MATERIAL_UNKNOWN
- UNKNOWN-reviewtrack nu: geblokkeerd door MATERIAL_UNKNOWN
- na het materiaalbesluit: system_class UNKNOWN; caveats observations a -, b -; reviewbaar, familie RF-4645-9ac13fa8d5

### PAIR-00533: DOC-007 x DOC-012

- observations: PO-DOC-007-P017-L097 (SC-DOC-007) x PO-DOC-012-P014-L085 (SC-DOC-012)
- brontekst a: `Groot schilderwerk plafond hout 580,00 m2 2030 14 25.623 25.623`
- brontekst b: `Groot schilderwerk plafond hout 12,90 m2 2027 18 591 591`
- objecttekst: 'Binnenschilderwerk plafond hout / stucwerk dekkend' vs 'Binnenschilderwerk plafond hout transparant' (alleen a: ['dekkend', 'stucwerk']; alleen b: ['transparant'])
- actietekst: 'Groot schilderwerk plafond hout dekkend' vs 'Groot schilderwerk plafond hout transparant' (alleen a: ['dekkend']; alleen b: ['transparant'])
- hoeveelheid: 580.00 vs 12.90; prijs per uitvoering: 44.18 vs 45.81; prijspeil: 28-4-2023 vs 1-4-2024
- system_class: **UNKNOWN**; unknown_reasons: OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW; hard violations: -
- caveats: paar PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE; observations a MATERIAL_UNKNOWN, b MATERIAL_UNKNOWN
- UNKNOWN-reviewtrack nu: geblokkeerd door MATERIAL_UNKNOWN
- na het materiaalbesluit: system_class UNKNOWN; caveats observations a -, b -; reviewbaar, familie RF-4645-203095b1cf

## Reviewfamilies na het materiaalbesluit (indicatief)

| familie | track | categorie | paren | unknown_reasons | keuzes |
|---|---|---|---|---|---|
| RF-4645-203095b1cf | UNKNOWN_PAIR_REVIEW | OBJECT_TEXT_VARIANT | PAIR-00533 | ACTION_EQUIVALENCE_REQUIRES_REVIEW, OBJECT_EQUIVALENCE_REQUIRES_REVIEW | COMPARABLE_WITH_CAVEATS, NOT_COMPARABLE |
| RF-4645-9ac13fa8d5 | UNKNOWN_PAIR_REVIEW | OBJECT_TEXT_VARIANT | PAIR-00531 | ACTION_EQUIVALENCE_REQUIRES_REVIEW, OBJECT_EQUIVALENCE_REQUIRES_REVIEW | COMPARABLE_WITH_CAVEATS, NOT_COMPARABLE |
| RF-4645-f273568c78 | UNKNOWN_PAIR_REVIEW | OBJECT_TEXT_VARIANT | PAIR-00529 | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | COMPARABLE_WITH_CAVEATS, NOT_COMPARABLE |

## SIMULATIES (kengetallen_rules_v1)

| scenario | hypothetische besluiten | materiaal | kengetal | AVAILABLE |
|---|---|---|---|---|
| huidige toestand | - | PO-DOC-006-P015-L059: onbekend, PO-DOC-007-P017-L097: onbekend, PO-DOC-012-P014-L085: onbekend | geen kengetalgroep | nee |
| na alleen de materiaalgoedkeuringen | - | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | geen kengetalgroep | nee |
| materiaal + 1 positief paar/paren (PAIR-00529) | PAIR-00529 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-0a54b8ba` **INSUFFICIENT_DATA**, 2 clusters, min 44.18, max 54.45, redenen FEWER_THAN_3_SOURCE_CLUSTERS | nee |
| materiaal + 1 positief paar/paren (PAIR-00531) | PAIR-00531 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-059f5174` **INSUFFICIENT_DATA**, 2 clusters, min 45.81, max 54.45, redenen FEWER_THAN_3_SOURCE_CLUSTERS | nee |
| materiaal + 1 positief paar/paren (PAIR-00533) | PAIR-00533 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-7b16ab6d` **INSUFFICIENT_DATA**, 2 clusters, min 44.18, max 45.81, redenen FEWER_THAN_3_SOURCE_CLUSTERS | nee |
| materiaal + 2 positief paar/paren (PAIR-00529, PAIR-00531) | PAIR-00529 COMPARABLE_WITH_CAVEATS, PAIR-00531 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **INSUFFICIENT_DATA**, 3 clusters, min 44.18, max 54.45, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW, ontbrekende reviews 1 | nee |
| materiaal + 2 positief paar/paren (PAIR-00529, PAIR-00533) | PAIR-00529 COMPARABLE_WITH_CAVEATS, PAIR-00533 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **INSUFFICIENT_DATA**, 3 clusters, min 44.18, max 54.45, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW, ontbrekende reviews 1 | nee |
| materiaal + 2 positief paar/paren (PAIR-00531, PAIR-00533) | PAIR-00531 COMPARABLE_WITH_CAVEATS, PAIR-00533 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **INSUFFICIENT_DATA**, 3 clusters, min 44.18, max 54.45, redenen INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW, ontbrekende reviews 1 | nee |
| materiaal + alle 3 paren positief | PAIR-00529 COMPARABLE_WITH_CAVEATS, PAIR-00531 COMPARABLE_WITH_CAVEATS, PAIR-00533 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **AVAILABLE** mediaan 45.81, 3 clusters, min 44.18, max 54.45 | ja |
| materiaal + PAIR-00529 NOT_COMPARABLE, de andere twee positief | PAIR-00529 NOT_COMPARABLE, PAIR-00531 COMPARABLE_WITH_CAVEATS, PAIR-00533 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **INSUFFICIENT_DATA**, 3 clusters, min 44.18, max 54.45, redenen NOT_COMPARABLE_WITHIN_GROUP, INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW, ontbrekende reviews 1 | nee |
| materiaal + PAIR-00531 NOT_COMPARABLE, de andere twee positief | PAIR-00529 COMPARABLE_WITH_CAVEATS, PAIR-00531 NOT_COMPARABLE, PAIR-00533 COMPARABLE_WITH_CAVEATS | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **INSUFFICIENT_DATA**, 3 clusters, min 44.18, max 54.45, redenen NOT_COMPARABLE_WITHIN_GROUP, INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW, ontbrekende reviews 1 | nee |
| materiaal + PAIR-00533 NOT_COMPARABLE, de andere twee positief | PAIR-00529 COMPARABLE_WITH_CAVEATS, PAIR-00531 COMPARABLE_WITH_CAVEATS, PAIR-00533 NOT_COMPARABLE | PO-DOC-006-P015-L059: wood, PO-DOC-007-P017-L097: wood, PO-DOC-012-P014-L085: wood | `KG-4645-interior_painting-m2-wood-d8e3183f` **INSUFFICIENT_DATA**, 3 clusters, min 44.18, max 54.45, redenen NOT_COMPARABLE_WITHIN_GROUP, INCOMPLETE_CROSS_CLUSTER_HUMAN_REVIEW, ontbrekende reviews 1 | nee |

Observations en ontbrekende cross-cluster reviews per scenario staan in het JSON-bestand (`simulations[].kengetal_groups[]`).
