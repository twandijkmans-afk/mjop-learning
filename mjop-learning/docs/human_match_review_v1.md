# Human match review — versie 1

Beschrijft de implementatie in `scripts/human_match_review.py`
(`REVIEW_VERSION = "human_match_review_v1"`); schema
`schemas/human_match_decision_record.schema.json`; opslag
`data/match_review_decisions/human_match_decision_records.json`; tests
`tests/test_human_match_review.py`. Dit document beschrijft alleen wat
geïmplementeerd is.

## Doel en relatie met Matching v1

`scripts/match_kengetal.py` (`docs/matching_rules_v1.md`) levert per nieuw
MJOP-object een matchresultaat met `final_status` `CANDIDATE_FOUND`,
`HUMAN_REVIEW_REQUIRED` of `NO_SUITABLE_KENGETAL`. Deze laag legt vast wat een
mens met zo'n matchresultaat doet. Een beslissing is uitsluitend een
beslissing over het **gebruik van dat matchresultaat**. Ze wordt nooit
opgeslagen of gebruikt als historische prijsobservatie, kengetal-observatie,
comparability-beslissing of wijziging van een kengetal.

De structuur volgt de bestaande human review (`docs/human_review_v1.md`):
append-only JSON-opslag met `store_version`, `append_only` en `records`,
`supersedes`, en een aparte controle op invarianten over records heen.

## Decision model

Per record:

- `decision` = `ACCEPT` / `ADJUST` / `REJECT` (niets anders);
- `decision_status` = `ACTIVE` / `SUPERSEDED`.

Elk record bewaart het **volledige, ongewijzigde matchresultaat**
(`match_result`) plus `match_result_sha256` (sha256 van de canonieke JSON:
`sort_keys`, compacte separators, UTF-8) en, uitgelicht, het systeemvoorstel:
`system_final_status`, `system_scope_status`, `system_reasons`,
`system_candidate_kengetal_id`, `system_candidate_kengetal_ids`. Daarnaast de
menselijke keuze (`chosen_kengetal_id`, `adjustment`), `decision_reason`
(verplicht, niet leeg), `decision_caveats` (lijst), `evidence` (lijst van
`{reference, note}`), `reviewer` (`reviewer_type` altijd `human`),
`reviewed_at`, `rule_versions`, `input_hashes`, `notes`, `supersedes`.

Voordat een beslissing wordt toegevoegd, wordt het matchresultaat gecontroleerd:
geldig volgens `schemas/match_result.schema.json`, `rule_version` =
`matching_rules_v1`, en `match_result_id` herberekenbaar uit de inhoud (een
gewijzigd matchresultaat wordt geweigerd).

### ACCEPT

De reviewer accepteert het voorgestelde kengetal. Alleen mogelijk als het
matchresultaat een `candidate_kengetal_id` heeft (bij `CANDIDATE_FOUND` of
`HUMAN_REVIEW_REQUIRED` met één kandidaat). `chosen_kengetal_id` =
`system_candidate_kengetal_id`; `adjustment` = null.

### ADJUST

De reviewer past het voorstel expliciet aan. Het oorspronkelijke voorstel
blijft zichtbaar (`system_candidate_kengetal_id(s)`, `match_result`); de keuze
staat in `adjustment`:

- `kengetal_id`: een ander kengetal, alleen als dat bestaat en status
  `AVAILABLE` heeft in de kengetallen-output; of null;
- `amount_per_unit_exact`: een door de reviewer opgegeven positief bedrag per
  eenheid (Decimal-string), of null;
- `unit`: bij een bedrag altijd de eenheid van het input-object (unit is een
  harde retrieval-sleutel en wordt niet omgezet);
- `amount_basis`: toelichting van de reviewer (bijv. bron of prijspeil); het
  systeem indexeert of rekent niets om.

Minstens één van `kengetal_id` of bedrag is verplicht. Een ADJUST die niets
wijzigt t.o.v. het voorstel (zelfde kengetal, geen bedrag) wordt geweigerd:
dan is het een ACCEPT. `chosen_kengetal_id` = `adjustment.kengetal_id`.

### REJECT

Het voorgestelde kengetal wordt niet gebruikt. `chosen_kengetal_id` en
`adjustment` zijn null; het voorstel blijft zichtbaar in
`system_candidate_kengetal_id(s)` en `match_result`.

## ACTIVE / SUPERSEDED en append-only gedrag

- Per `match_result_id` heeft hoogstens één record `ACTIVE`.
- Een nieuwe beslissing voor hetzelfde `match_result_id` wordt `ACTIVE`,
  verwijst met `supersedes` naar de vorige ACTIVE beslissing, en die vorige
  wordt `SUPERSEDED` — de enige toegestane wijziging aan een bestaand record.
- Er wordt niets verwijderd, overschreven of herschikt; de volledige historie
  blijft bewaard. Er is geen delete- of update-mechanisme.
- Controles:
  - `store_invariant_errors`: unieke `decision_id`, hoogstens één ACTIVE per
    `match_result_id`, `supersedes` verwijst naar een eerder SUPERSEDED record
    van hetzelfde matchresultaat, en elk SUPERSEDED record is door precies één
    later record vervangen;
  - `record_errors`: `match_result_sha256` past bij het bewaarde
    matchresultaat, de uitgelichte systeemvelden en rule versions komen
    overeen met het matchresultaat, `decision_id` past bij de inhoud, en de
    ACCEPT/ADJUST/REJECT-regels hierboven;
  - `append_only_errors`: vergelijkt een oude en nieuwe versie van de opslag;
  - `save_store` schrijft alleen na al deze controles, en weigert als de opslag
    op schijf is gewijzigd sinds het laden.

## Record-ID

`decision_id` = `HMD-` + eerste 16 hex-tekens van de sha256 van de canonieke
JSON van: `match_result_id`, `match_result_sha256`, `decision`,
`chosen_kengetal_id`, `adjustment`, `decision_reason`, `decision_caveats`,
`evidence`, `reviewer`, `notes`, `supersedes`, `rule_versions`,
`input_hashes` (functie `human_match_decision_record_id`). `reviewed_at` en
`decision_status` tellen niet mee: het tijdstip is alleen auditinformatie en
de status mag (ACTIVE → SUPERSEDED) veranderen zonder dat het ID verandert.
Geen willekeur.

## Actuele status

`current_decision(store, match_result_id)` geeft:

| ACTIVE record | status |
|---|---|
| geen | `NO_DECISION` |
| ACCEPT | `ACCEPTED` |
| ADJUST | `ADJUSTED` |
| REJECT | `REJECTED` |

plus het actieve record en de `decision_id`'s van de volledige historie
(inclusief SUPERSEDED). Meer dan één ACTIVE record voor hetzelfde
matchresultaat is een integriteitsfout (`IntegrityError`); dan wordt ook geen
nieuwe beslissing toegevoegd.

## Herleidbaarheid

Per beslissing: exact `match_result_id`, `match_result_sha256` en het volledige
matchresultaat; `rule_versions` (`human_match_review_v1`,
`matching_rule_version`, `kengetallen_rule_version`); `input_hashes` van het
matchresultaat (kengetallen-output, genormaliseerde observations,
vocabularies); reviewer, decision, reason, caveats en evidence; en
`supersedes` naar de vorige beslissing.

## Integriteit

De laag schrijft uitsluitend de beslissingenopslag. Historische bronbestanden,
genormaliseerde observations, comparability-data, human comparability
decisions, kengetallen en matchresultaten worden alleen gelezen (of als kopie
in een record bewaard) en nooit gewijzigd; de tests controleren dit met
sha256 van alle bestanden in `data/` en `vocabularies/`.

## Gebruik

```bash
python scripts/match_kengetal.py --input item.json --out mr.json
python scripts/human_match_review.py record --match-result mr.json --decision ACCEPT \
    --reviewer <id> --reason "..."
python scripts/human_match_review.py record --match-result mr.json --decision ADJUST \
    --reviewer <id> --reason "..." [--kengetal-id KG-...] [--amount 12.34 --amount-basis "..."]
python scripts/human_match_review.py status --match-result-id MR-...
```

Opties voor `record`: `--caveat CODE` (herhaalbaar), `--evidence REF[::NOTE]`
(herhaalbaar), `--notes`, `--store` (andere opslag), `--dry-run`.

## Wat deze laag niet doet

- geen automatische acceptatie of automatische beslissingen;
- geen learning loop en geen automatische update van kengetallen;
- geen nieuwe historische prijsobservaties, kengetal-observaties of
  comparability-beslissingen uit een ADJUST of REJECT;
- geen indexatie of omrekening van bedragen;
- geen AI/LLM-review;
- geen scoring, ranking, confidence of fuzzy matching;
- geen UI, geen Supabase, geen user accounts of permissies (de reviewer is
  een vrij `reviewer_id`, niet geauthenticeerd).
