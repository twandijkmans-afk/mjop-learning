# Human review — versie 1

Doel: een mens beoordeelt observation-paren uit de comparability-laag
(`data/comparability/comparability_batch1.json`, regels
`docs/comparability_rules_v1.md`) voordat ze als vergelijkbare input voor een
kengetal mogen dienen. Deze laag bouwt geen kengetallen en geen matching.

## Bestanden

| Bestand | Rol |
|---|---|
| `schemas/human_decision_record.schema.json` | schema van de opslag en van één beslissing |
| `data/review_decisions/human_decision_records.json` | de opslag (**source of truth** voor menselijke beslissingen) |
| `scripts/export_human_review_queue.py` | bouwt de reviewqueue reproduceerbaar uit de comparability-output |
| `reports/human_review_queue_v1.xlsx` | reviewinstrument voor de mens; **niet** de source of truth |

## Regels

1. **Alleen een mens beslist.** `reviewer.reviewer_type` is altijd `human`.
   Het systeem maakt nooit zelf een beslissing aan; er zijn geen scores,
   confidence of rangschikking.
2. **Append-only.** Bestaande beslissingen worden nooit overschreven of
   verwijderd. Een herziening is altijd een nieuw record:
   - het nieuwe record krijgt een nieuw `decision_id` en status `ACTIVE`;
   - `supersedes` verwijst naar het `decision_id` van de vorige beslissing
     van hetzelfde paar; **een paar is de set `observation_ids`**, `pair_id` is
     alleen een volgnummer van `build_comparability` en kan na een herbouw anders zijn;
   - de vorige beslissing krijgt status `SUPERSEDED`;
   - toegestane statuswijzigingen aan een bestaand record: `ACTIVE` → `SUPERSEDED`,
     `ACTIVE` → `REVIEW_REQUIRED` (invoer veranderd, bijv. deterministische promotie:
     record blijft bewaard, telt niet mee in kengetallen, wacht op een nieuwe menselijke
     beslissing) en `REVIEW_REQUIRED` → `SUPERSEDED`;
   - **per paar heeft hoogstens één record de status `ACTIVE`.**

   Het JSON-schema controleert één record tegelijk en dwingt deze
   invarianten over records heen niet af. Dat doen
   `store_invariant_errors` (unieke `decision_id`, hoogstens één `ACTIVE`
   per paar, geldige `supersedes`) en `append_only_errors` (vergelijking van
   een oude en nieuwe versie van de opslag) in
   `scripts/export_human_review_queue.py`.
3. **Systeem en mens blijven gescheiden.** `system_class` en `system_reasons`
   leggen vast wat comparability v1 op het moment van de review zei, en
   blijven altijd bewaard. `decision`, `decision_reason` en
   `decision_caveats` zijn de menselijke beslissing; die vervangen de
   systeemklasse niet.
4. **Toegestane beslissingen:** `COMPARABLE`, `COMPARABLE_WITH_CAVEATS`,
   `NOT_COMPARABLE`, `UNKNOWN`. `decision_reason` is verplicht.
5. **Herleidbaar.** `evidence` verwijst per observation naar document, pagina
   en regel (en de brontekst) die de reviewer bekeek. `rule_version` en
   `input_hashes` (sha256 van de comparability-output en de genormaliseerde
   observations) leggen vast op welke invoer de beslissing is gebaseerd.
6. **Veranderde invoer verwijdert niets.** Wijkt de huidige `input_hashes` of
   `rule_version` af van een record, dan wordt het record ter controle
   gemarkeerd; het blijft bestaan en wordt niet automatisch verwijderd,
   aangepast of vervangen.

## Eerste reviewqueue (v1)

Selectie, vastgelegd in `scripts/export_human_review_queue.py`:

- alleen paren met systeemklasse `COMPARABLE_WITH_CAVEATS`;
- beide observations `independent_input = true` (daarmee vallen o.a. de
  DOC-005-rijen met "(uitgevoerd JJJJ)" en `POSSIBLY_DEPENDENT` af);
- geen DOC-001-observation zonder materiaal (`material.source` leeg: de nog
  onopgeloste DOC-001-materiaalgevallen);
- geen UNKNOWN-paren.

De Excel bevat lege kolommen voor de menselijke beslissing. Ingevulde
beslissingen worden pas na een aparte, nog te bouwen stap als records in
`data/review_decisions/human_decision_records.json` opgenomen.
