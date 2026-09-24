# MJOP kengetal workflow — versie 1

Beschrijft de implementatie in `scripts/mjop_kengetal_workflow.py`
(`WORKFLOW_VERSION = "mjop_kengetal_workflow_v1"`); resultaatschema
`schemas/mjop_kengetal_workflow_result.schema.json`; tests
`tests/test_mjop_kengetal_workflow.py`. Dit document beschrijft alleen wat
geïmplementeerd is.

## Doel

Eén MJOP-onderhoudsregel door de bestaande keten halen:

```
MJOP-input → normalisatie → kengetal retrieval → scope-check → matchresultaat
           → actuele menselijke beslissing → gebruikt bedrag
```

De workflow is een integratielaag. Hij implementeert zelf geen normalisatie-,
matching- of beslisregels, leest alleen, en schrijft niets.

## Input

Het input-object v1 van de matchinglaag (`docs/matching_rules_v1.md`), met
dezelfde betekenis en normalisatie: `object_id`, `element_code_internal`,
`action_normalized` of `action_text`, `unit_normalized` of `unit_text`,
`material_normalized` of `material_text`, `material_source`,
`object_description`; en de contextvelden `quantity`,
`price_level_requested`, `vat_basis`, `building_type`, `construction_year`,
`location`, `condition_defect`, `maintenance_type`. Er is geen apart
workflow-inputmodel. Het input-object staat ongewijzigd in `input`.

## Relatie met de bestaande lagen

| Stap | Laag | Functie |
|---|---|---|
| normalisatie, retrieval, scope-check | Matching v1 (`scripts/match_kengetal.py`), die de vocabularies en regels van de normalisatielaag gebruikt | `match()` |
| actuele menselijke beslissing | Human match review v1 (`scripts/human_match_review.py`) | `current_decision()`, `record_errors()` |
| gebruikt bedrag | deze workflow | alleen uit de actieve beslissing |

`normalization` in het resultaat is `input_normalized` uit het
matchresultaat; `match_result` is het volledige matchresultaat.

## Workflowstatussen

| Situatie | `status` |
|---|---|
| geen actieve beslissing, match `NO_SUITABLE_KENGETAL` | `NO_KENGETAL` |
| geen actieve beslissing, match `HUMAN_REVIEW_REQUIRED` | `REVIEW_REQUIRED` |
| geen actieve beslissing, match `CANDIDATE_FOUND` | `MATCH_PENDING_DECISION` |
| actieve beslissing ACCEPT | `ACCEPTED` |
| actieve beslissing ADJUST | `ADJUSTED` |
| actieve beslissing REJECT | `REJECTED` |

De actieve menselijke beslissing is leidend: met een beslissing bepaalt die
de status, ongeacht de matchstatus.

**CANDIDATE_FOUND versus MATCH_PENDING_DECISION**: `CANDIDATE_FOUND` betekent
alleen dat de matchinglaag precies één kandidaat met een exacte scope heeft
gevonden. Zonder menselijke beslissing geeft de workflow dan
`MATCH_PENDING_DECISION` en **geen** gebruikt bedrag.

## Menselijke beslissing

De workflow roept `current_decision(store, match_result_id)` aan en
interpreteert of reconstrueert zelf geen oude beslissingen. Het actieve
record wordt met `record_errors()` gecontroleerd tegen de huidige
kengetallen-output, en de `match_result_sha256` van het record moet gelijk
zijn aan de hash van het zojuist berekende matchresultaat. Een beslissing
geldt dus alleen voor exact dit matchresultaat; een andere input geeft een
ander `match_result_id` en daarmee `NO_DECISION`.

- **ACCEPTED**: het voorgestelde kengetal (`chosen_kengetal_id`) wordt de basis.
- **ADJUSTED**: exact de aanpassing uit het record — het menselijke bedrag
  (`adjustment.amount_per_unit_exact`), of anders de waarde van het door de
  mens gekozen kengetal (`adjustment.kengetal_id`). Een ADJUST naar een
  kengetal met een **andere eenheid** dan de MJOP-regel is **niet
  toegestaan**: human match review weigert zo'n beslissing bij het toevoegen,
  en een bestaand record dat deze regel schendt laat de workflow falen.
- **REJECTED**: er wordt geen kengetalbedrag gebruikt.

## Bedragen

`financial_result` houdt systeemvoorstel en menselijke keuze gescheiden
(Decimal-strings, geen tussentijdse afronding; `*_display` = afronding op
0.01, ROUND_HALF_EVEN, alleen voor weergave):

| Veld | Inhoud |
|---|---|
| `system_candidate_kengetal_id`, `system_candidate_amount` | het kengetal dat de match voorstelde en de waarde ervan (`historical_range.value_exact`); alleen informatie |
| `human_selected_kengetal_id`, `human_selected_amount` | ACCEPT: het voorgestelde kengetal en de waarde ervan; ADJUST: `adjustment.kengetal_id` en het aangepaste bedrag, of zonder bedrag de waarde van het gekozen kengetal; REJECT / geen beslissing: null |
| `effective_amount`, `effective_amount_unit`, `effective_amount_source` | alleen bij ACCEPTED of ADJUSTED gelijk aan `human_selected_amount`; bron `SYSTEM_KENGETAL_ACCEPTED`, `HUMAN_SELECTED_KENGETAL` of `HUMAN_ADJUSTMENT`; anders null |
| `effective_total` | `effective_amount × quantity`, exact |

Er is geen stilzwijgende fallback: zonder ACCEPTED/ADJUSTED is er geen
effectief bedrag en geen totaal.

## Quantity en totaal

`quantity` is de genormaliseerde hoeveelheid van de input. `effective_total`
wordt alleen berekend als er een effectief bedrag is, de hoeveelheid
aanwezig en positief is, en de eenheid van het effectieve bedrag gelijk is aan
die van de MJOP-regel. Anders is het totaal null met
`total_not_computed_reason`: `NO_EFFECTIVE_AMOUNT`, `QUANTITY_MISSING`,
`QUANTITY_NOT_POSITIVE` of `UNIT_MISMATCH`. Omdat ADJUST naar een andere
eenheid wordt geweigerd en een menselijk bedrag altijd in de eenheid van de
inputregel staat, is `UNIT_MISMATCH` alleen een verdedigende controle.
`calculation` beschrijft de berekening. Geen schaalcorrectie of eigen
prijsmodel.

## Price level

Geen indexatie: `indexation` is altijd `none`. `price_levels` komt van het
gebruikte kengetal (ACCEPT, of ADJUST naar een kengetal); anders van het
matchresultaat. De prijspeilcaveats van de match (bijv. `NOT_INDEXED`,
`PRICE_LEVEL_MIXED`, `PRICE_LEVEL_MISSING_IN_SOURCE`,
`REQUESTED_PRICE_LEVEL_NOT_REPRESENTED`) worden doorgegeven.
`price_level_requested` heeft alleen die informerende rol. Bij een menselijk
bedrag staat de toelichting van de reviewer in `amount_basis`.

## VAT

Exact de matchingregel: een bekend BTW-verschil geeft
`HUMAN_REVIEW_REQUIRED` (`VAT_BASIS_DIFFERS`), dus zonder beslissing
`REVIEW_REQUIRED`; een ontbrekende BTW-basis geeft de caveat
`VAT_BASIS_NOT_GIVEN`. De workflow voegt geen BTW-logica toe.

## Caveats en provenance

`caveats`: de redenen en caveats van het matchresultaat, de decision- en
observation-caveats van het kengetal (via het matchresultaat) en de
`decision_caveats` van de actieve menselijke beslissing.

`provenance` gebruikt bestaande IDs en hashes: `match_result_id`,
`match_result_sha256` (canonieke JSON, zelfde functie als human match review),
`active_decision_id`, `decision_store_sha256`, `rule_versions`
(workflow, matching, kengetallen, human match review) en de `input_hashes`
van het matchresultaat. `current_decision.history` geeft alle
`decision_id`'s voor het matchresultaat, inclusief SUPERSEDED.

## Determinisme

Dezelfde input, dezelfde onderliggende datasets en dezelfde beslissingen
geven een byte-identiek resultaat. `workflow_result_id` = `WF-` + sha256
(canonieke JSON) over workflowversie, `match_result_sha256` en
`active_decision_id`. Er zitten geen tijdstempels of willekeurige waarden in
het resultaat.

## Integriteitsfouten

De workflow faalt expliciet (`WorkflowError`; CLI exitcode 3) en kiest nooit
zelf als:

- er meer dan één ACTIVE beslissing voor het matchresultaat is;
- het actieve record niet door `record_errors()` komt (bijv. gewijzigde
  inhoud, niet-passend ID, ADJUST naar een kengetal met een andere eenheid);
- het actieve record bij een ander matchresultaat hoort (hash wijkt af).

## Append-only beslissingen, geen learning loop, geen mutatie

- Beslissingen worden alleen gelezen; ze worden append-only beheerd door
  human match review (`docs/human_match_review_v1.md`).
- Een ACCEPT, ADJUST of REJECT verandert niets aan price observations,
  genormaliseerde observations, comparability, kengetallen of historische
  brondata. De workflow gebruikt bestaande kennis maar leert er niet van.
- De workflow schrijft geen data; de CLI schrijft alleen naar stdout (UTF-8)
  of naar een `--out`-bestand buiten `data/` (anders exitcode 2).

## Gebruik

```bash
python scripts/mjop_kengetal_workflow.py --input regel.json [--decisions opslag.json] [--out resultaat.json]
```

`--decisions` is standaard
`data/match_review_decisions/human_match_decision_records.json` en wordt
alleen gelezen.

## Wat de workflow niet doet

Geen UI, Supabase, dashboard, adressen/BAG, planning of reservefonds; geen
learning loop of automatische kengetal-updates; geen automatische acceptatie;
geen AI/foto-matching; geen fuzzy matching, ranking, scoring of confidence;
geen schaalcorrectie of indexatie; geen opslag van workflowresultaten.
