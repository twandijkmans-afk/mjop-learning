# Matching — regels versie 1

Status: beschrijft de implementatie in `scripts/match_kengetal.py`
(`RULE_VERSION = "matching_rules_v1"`); resultaatschema
`schemas/match_result.schema.json`; tests `tests/test_match_kengetal.py`.
Dit document introduceert geen regels die niet in de code staan.

Doel: voor één nieuw MJOP-object deterministisch bepalen of er een bestaand
kengetal v1 (`data/kengetallen/kengetallen_batch1.json`,
`docs/kengetallen_rules_v1.md`) als kandidaat getoond kan worden. Het
resultaat is een voorstel; de matchinglaag schrijft **geen** historische
kennis, geen human decisions en past geen prijs aan.

## 1. Input-object

| Veld | Rol in v1 |
|---|---|
| `object_id` | verplicht; identificatie |
| `element_code_internal` | retrieval key (geen automatische codekoppeling) |
| `action_normalized` of `action_text` | retrieval key; tekst → exacte lookup in `vocabularies/maintenance_action.json`, anders de goedgekeurde prefixregel van de normalisatielaag (`vervangen`/`herstellen`/`herstel`/`reinigen`); anders niet genormaliseerd |
| `unit_normalized` of `unit_text` | retrieval key; tekst → exacte lookup in `vocabularies/unit.json` |
| `material_normalized` of `material_text` | retrieval key; tekst → exacte lookup in `vocabularies/material.json`; staat de tekst niet in de vocabulaire, dan telt de tekst zelf (kleine letters) als materiaal |
| `material_source` | wordt doorgegeven (bijv. `user`, `verified_element`, `element_text`) |
| `object_description` | scope-check |
| `quantity` | alleen context/caveat (historisch bereik) |
| `price_level_requested` | alleen context/caveat (geen indexatie) |
| `vat_basis` | vergelijking met de BTW-basis van het kengetal |
| `building_type`, `construction_year`, `location`, `condition_defect`, `maintenance_type` | context/future: alleen doorgegeven, niet gebruikt |

De genormaliseerde input en per veld de normalisatiebasis (`given`,
`vocabulary_lookup`, `prefix_rule:<woord>`, `not_normalized`) staan in
`input_normalized`.

## 2. Candidate retrieval

- **Retrieval key**: `element_code + action + unit + material`, alle vier
  exact gelijk aan het kengetal (materiaal: genormaliseerde waarde, anders de
  originele waarde in kleine letters).
- Alleen kengetallen met status **`AVAILABLE`** zijn kandidaat.
- Een kengetal met status **`INSUFFICIENT_DATA`** en dezelfde sleutel is geen
  kandidaat; het wordt genoemd in `provenance.insufficient_data_kengetal_ids`
  met reden `KENGETAL_INSUFFICIENT_DATA`.
- Ontbreekt element_code, action of unit (of normaliseert de tekst niet):
  `INPUT_KEY_INCOMPLETE`, geen retrieval.
- Onbekend materiaal: `MATERIAL_UNKNOWN`, geen retrieval (alle v1-kengetallen
  zijn materiaalgebonden).
- Geen kengetal met deze sleutel: `NO_KENGETAL_FOR_KEY`.
- Retrieval is **geen** match: de eindstatus neemt ook de scope mee.

`retrieval_status`: `CANDIDATES_RETRIEVED` of `NO_CANDIDATE`.

## 3. Scope-check (per kandidaat)

De objectomschrijving wordt vergeleken als reeks woordtokens (kleine letters,
alleen letters/cijfers). Geen fuzzy matching, geen synoniemen, geen
interpretatie van woordvolgorde, geen semantische overeenkomst.

| Situatie | `scope_status` | reden |
|---|---|---|
| token-gelijk aan de omschrijving van een groepslid van het kengetal | `EXACT_MATCH` | — |
| token-gelijk aan de omschrijving van een observation die met een menselijke NOT_COMPARABLE uit de groep is uitgesloten (`exclusion_reasons` = `HUMAN_NOT_COMPARABLE:...`) | `MISMATCH` | `SCOPE_MISMATCH_HUMAN_NOT_COMPARABLE` |
| token-gelijk aan beide | `HUMAN_REVIEW_REQUIRED` | `CONFLICTING_SCOPE_EVIDENCE` |
| geen van beide | `HUMAN_REVIEW_REQUIRED` | `SCOPE_NOT_DETERMINISTIC` |
| geen objectomschrijving | `HUMAN_REVIEW_REQUIRED` | `OBJECT_DESCRIPTION_MISSING` |

Een inhoudelijk vergelijkbare maar anders geformuleerde omschrijving blijft
in v1 dus `HUMAN_REVIEW_REQUIRED`. `scope_evidence` legt de regel, de
omschrijvingen van de groepsleden, de gematchte (uitgesloten) observations,
het NOT_COMPARABLE-bewijs en de `decision_id`'s van het kengetal vast.

## 4. Eindstatus

- **`CANDIDATE_FOUND`**: precies één kandidaat die geen `MISMATCH` is, met
  `EXACT_MATCH`, en geen reden (zie BTW).
- **`NO_SUITABLE_KENGETAL`**: geen kandidaat (`INPUT_KEY_INCOMPLETE`,
  `MATERIAL_UNKNOWN`, `NO_KENGETAL_FOR_KEY`, `KENGETAL_INSUFFICIENT_DATA`) of
  alle kandidaten `MISMATCH` (`SCOPE_MISMATCH_HUMAN_NOT_COMPARABLE`).
- **`HUMAN_REVIEW_REQUIRED`**: in alle andere gevallen, o.a.
  `SCOPE_NOT_DETERMINISTIC`, `OBJECT_DESCRIPTION_MISSING`,
  `CONFLICTING_SCOPE_EVIDENCE`, `MULTIPLE_CANDIDATES` (meer dan één
  niet-MISMATCH kandidaat; geen keuze, geen rangorde) en
  **`VAT_BASIS_DIFFERS`** (BTW-basis van de input bekend en verschillend van
  de enige BTW-basis van het kengetal; ook bij `EXACT_MATCH`).

Er is nooit een automatische positieve scope-beslissing buiten `EXACT_MATCH`.
Redenen zijn altijd machine-leesbaar (`reasons`, vaste lijst in het schema).

## 5. Context en caveats (veranderen de status niet)

`caveats.match_caveats`:

- quantity: `QUANTITY_WITHIN_HISTORICAL_RANGE`,
  `QUANTITY_OUTSIDE_HISTORICAL_RANGE` of `QUANTITY_NOT_GIVEN` (historisch
  bereik = quantity min/max van het kengetal; geen schaalcorrectie);
- price level: altijd `NOT_INDEXED`; `PRICE_LEVEL_MIXED`,
  `PRICE_LEVEL_MISSING_IN_SOURCE`; `REQUESTED_PRICE_LEVEL_NOT_REPRESENTED`
  als een gevraagd prijsjaar niet (als enig jaar) in het kengetal voorkomt;
  geen indexatie;
- materiaal: `KENGETAL_MATERIAL_PARTLY_FROM_ELEMENT_TEXT` als het kengetal
  (deels) op `MATERIAL_FROM_TEXT` rust;
- BTW: `VAT_BASIS_NOT_GIVEN` als de input geen BTW-basis heeft.

Daarnaast `caveats.decision_caveats` (tellingen uit het kengetal) en
`caveats.observation_caveats` (bijv. `CODE_LABEL_MISMATCH`,
`PRICE_LEVEL_ABSENT`). De historische waarde, het bereik, de source clusters
en de prijspeilen worden ongewijzigd uit het kengetal overgenomen.

## 6. Wat v1 niet doet

- geen fuzzy matching, synoniemen, woordvolgorde-interpretatie of
  semantische overeenkomst;
- geen scoring, ranking of confidence;
- geen indexatie en geen schaalcorrectie;
- geen materiaalhiërarchie;
- geen automatische human decisions en geen transitiviteit;
- geen mutatie van historische data: de laag leest alleen en de CLI weigert
  te schrijven onder `data/`;
- geen opslag van menselijke matchbeslissingen (nog niet gebouwd).

## 7. Herleidbaarheid en determinisme

- `provenance`: kengetallenbestand, `decision_id`'s en observation IDs van de
  kandidaat, INSUFFICIENT_DATA-kengetallen met dezelfde sleutel.
- `input_hashes`: sha256 van de kengetallen-output, de genormaliseerde
  observations en de gebruikte vocabularies (maintenance_action, unit,
  material).
- `match_result_id` = `MR-` + sha256 over: matching-regelversie,
  kengetallen-regelversie, `input_hashes` en de genormaliseerde input. Geen
  tijdstempel of willekeur: dezelfde input op dezelfde basis geeft een
  byte-identiek resultaat; een andere regelversie, kengetallen-output,
  vocabulaire of input geeft een ander ID.
