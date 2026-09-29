# Beslispakket 4711 replace m1 - aluminium

Dit pakket neemt zelf geen besluit. Waar een materiaalbesluit nog ontbreekt, is de toestand daarna gesimuleerd op een tijdelijke kopie; waar het al vastligt, toont het pakket de huidige toestand en de ACTIVE besluiten. Simulaties gebruiken alleen de bestaande regels en worden nergens vastgelegd.

## Bestaande kengetallen

`KG-4711-replace-m1-aluminium-d463b0a2` AVAILABLE 37.47

## Alle observations van 4711|replace|m1

| observation | document | cluster | object | actie | materiaalstatus | eenheid | hoeveelheid | prijspeil | prijs/uitvoering |
|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-005-P012-L083 | DOC-005 | SC-DOC-005+DOC-006 | Dakrandafwerking zink | Vervangen dakrandafwerking zink | KNOWN:zinc (verified_element) | m1 | 70.00 | 1-8-2026 | 62.10 |
| PO-DOC-007-P018-L015 | DOC-007 | SC-DOC-007 | Dakbedekking APP dakopstanden opgaande gevel | Vervangen dakbedekking APP dakvlak 2-3 | NO_MATERIAL_EVIDENCE (-) | m1 | 15.40 | 28-4-2023 | 138.64 |
| PO-DOC-007-P018-L033 | DOC-007 | SC-DOC-007 | Dakrandafwerking Plastisol afdekkap | Vervangen dakrandafwerking metaal 2-3 | NO_MATERIAL_EVIDENCE (-) | m1 | 245.38 | 28-4-2023 | 98.68 |
| PO-DOC-008-P009-L045 | DOC-008 | SC-DOC-008+DOC-009 | Dakrandafwerking aluminium trim | Vervangen daktrim aluminium | KNOWN:aluminium (verified_element) | m1 | 119.60 | - | 39.06 |
| PO-DOC-011-P021-L083 | DOC-011 | SC-DOC-011 | Dakrandafwerking aluminium trim | Vervangen daktrim aluminium | KNOWN:aluminium (human_material_decision) | m1 | 250.20 | - | 33.88 |
| PO-DOC-012-P014-L107 | DOC-012 | SC-DOC-012 | Dakrandafwerking aluminium trim | Vervangen daktrim aluminium | KNOWN:aluminium (human_material_decision) | m1 | 152.54 | 1-4-2024 | 37.47 |
| PO-DOC-012-P014-L111 | DOC-012 | SC-DOC-012 | Randstrook APP | Vervangen randstrook APP | NO_MATERIAL_EVIDENCE (-) | m1 | 152.54 | 1-4-2024 | 45.59 |
| PO-DOC-013-P018-L087 | DOC-013 | SC-DOC-013 | Dakrandafwerking zink | Vervangen dakrandafwerking zink | TEXT_EVIDENCE_PENDING_APPROVAL:zinc (-) | m1 | 17.80 | 14-7-2026 | 56.97 |

## aluminium (3 potentiële source clusters, minimum 3)

Observations: PO-DOC-008-P009-L045, PO-DOC-011-P021-L083, PO-DOC-012-P014-L107; clusters SC-DOC-008+DOC-009, SC-DOC-011, SC-DOC-012.

### Stap 1 - materiaalbesluit (record_material_decision.py)

Geen observations die een materiaalbesluit nodig hebben.

Met de huidige materiaalstatus (zonder nieuw materiaalbesluit), als alle cross-cluster paren positief beoordeeld worden: KG-4711-replace-m1-aluminium-d463b0a2 AVAILABLE 37.47 (3 clusters; min 33.88, max 39.06, ontbrekend prijspeil).

### Stap 2 - cross-cluster paren na het materiaalbesluit (0 open, 3 totaal)

| paar | familie vóór -> na materiaalbesluit | documenten | klasse | paarcaveats | hard | observation-caveats | verschillen | controle | ACTIVE besluit |
|---|---|---|---|---|---|---|---|---|---|
| PAIR-00557 | RF-4711-17297bd2b3 -> RF-4711-17297bd2b3 | DOC-008 x DOC-011 | COMPARABLE_WITH_CAVEATS | - | - | a: PRICE_LEVEL_ABSENT; b: PRICE_LEVEL_ABSENT | quantity, price | OK | HDR-00043 COMPARABLE_WITH_CAVEATS |
| PAIR-00558 | RF-4711-17297bd2b3 -> RF-4711-17297bd2b3 | DOC-008 x DOC-012 | COMPARABLE_WITH_CAVEATS | - | - | a: PRICE_LEVEL_ABSENT; b: - | price_level, quantity, price | OK | HDR-00044 COMPARABLE_WITH_CAVEATS |
| PAIR-00561 | RF-4711-0f1822792b -> RF-4711-0f1822792b | DOC-011 x DOC-012 | COMPARABLE_WITH_CAVEATS | - | - | a: PRICE_LEVEL_ABSENT; b: - | price_level, quantity, price | OK | HDR-00045 COMPARABLE_WITH_CAVEATS |

Paren die NIET aan de beschrijving voldoen (zelfde actie- en objecttekst, aluminium, m1, geen relatie; verschil alleen prijspeil/hoeveelheid/prijs): geen.

Gecombineerd (alle open families dezelfde keuze):

- **ALL_OPEN_FAMILIES_COMPARABLE** -> KG-4711-replace-m1-aluminium-d463b0a2 AVAILABLE 37.47 (3 clusters; min 33.88, max 39.06, ontbrekend prijspeil)
- **ALL_OPEN_FAMILIES_COMPARABLE_WITH_CAVEATS** -> KG-4711-replace-m1-aluminium-d463b0a2 AVAILABLE 37.47 (3 clusters; min 33.88, max 39.06, ontbrekend prijspeil)
- **ALL_OPEN_FAMILIES_NOT_COMPARABLE** -> KG-4711-replace-m1-aluminium-d463b0a2 AVAILABLE 37.47 (3 clusters; min 33.88, max 39.06, ontbrekend prijspeil)

## zinc (2 potentiële source clusters, minimum 3)

Observations: PO-DOC-005-P012-L083, PO-DOC-013-P018-L087; clusters SC-DOC-005+DOC-006, SC-DOC-013.

### Stap 1 - materiaalbesluit (record_material_decision.py)

| observation | document | objectomschrijving | actietekst | eenheid | bron | precheck |
|---|---|---|---|---|---|---|
| PO-DOC-013-P018-L087 | DOC-013 | Dakrandafwerking zink | Vervangen dakrandafwerking zink | m1 | p18 r87: `Vervangen dakrandafwerking zink 17,80 m1 2037 25 1.014 1.014` | WOULD_BE_ACCEPTED |

Met de huidige materiaalstatus (zonder nieuw materiaalbesluit), als alle cross-cluster paren positief beoordeeld worden: KG-4711-replace-m1-zinc-5e892215 INSUFFICIENT_DATA (2 clusters; min 56.97, max 62.10; redenen FEWER_THAN_3_SOURCE_CLUSTERS, MATERIAL_UNKNOWN).

### Stap 2 - cross-cluster paren na het materiaalbesluit (1 open, 1 totaal)

| paar | familie vóór -> na materiaalbesluit | documenten | klasse | paarcaveats | hard | observation-caveats | verschillen | controle | ACTIVE besluit |
|---|---|---|---|---|---|---|---|---|---|
| PAIR-00546 | RF-4711-b9d21ea6f1 -> - (niet in de queue) | DOC-005 x DOC-013 | COMPARABLE | - | - | a: -; b: - | price_level, quantity, price | OK | - |

Paren die NIET aan de beschrijving voldoen (zelfde actie- en objecttekst, zinc, m1, geen relatie; verschil alleen prijspeil/hoeveelheid/prijs): geen.

Gecombineerd (alle open families dezelfde keuze):

- **ALL_OPEN_FAMILIES_COMPARABLE** -> KG-4711-replace-m1-zinc-5e892215 INSUFFICIENT_DATA (2 clusters; min 56.97, max 62.10; redenen FEWER_THAN_3_SOURCE_CLUSTERS)
- **ALL_OPEN_FAMILIES_COMPARABLE_WITH_CAVEATS** -> KG-4711-replace-m1-zinc-5e892215 INSUFFICIENT_DATA (2 clusters; min 56.97, max 62.10; redenen FEWER_THAN_3_SOURCE_CLUSTERS)
- **ALL_OPEN_FAMILIES_NOT_COMPARABLE** -> geen kengetalgroep

## Volgorde als een mens besluit

1. Materiaalbesluit met `scripts/record_material_decision.py --decision <besluit.json>` (eerst `--dry-run`) voor exact de observations uit stap 1; reviewer, tijdstip en reden vult de mens in.
2. `python scripts/comparability_review_v2.py` opnieuw draaien; de family-ids en family_input_sha256 uit dat herbouwde pakket (niet de indicatieve waarden hierboven) gaan in het familiebesluit.
3. Familiebesluit(en) met `scripts/apply_family_decision.py --decision <besluit.json>` (eerst `--dry-run`); een nieuw AVAILABLE kengetal moet in `acknowledged_kengetal_effects` staan.

Beslispakket, geen besluit. Materiaal-precheck: record_material_decision.validate met een placeholder-reviewer (schrijft niets). De toestand na het materiaalbesluit is gesimuleerd met record_material_decision.record op een tijdelijke kopie; family_input_sha256 daarvan is alleen indicatief - het echte familiebesluit bindt aan comparability_review_v2.json zoals dat NA het echte materiaalbesluit wordt herbouwd. Kengetalsimulaties gebruiken uitsluitend build_kengetallen.evaluate (kengetallen_rules_v1) met hypothetische ACTIVE records en worden nergens vastgelegd. COMPARABLE en COMPARABLE_WITH_CAVEATS tellen in de regels hetzelfde (regel 2). Toepassen alleen via scripts/record_material_decision.py en daarna scripts/apply_family_decision.py.
