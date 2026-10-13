# Agent-tools — fase 1 (alleen-lezen)

Status: fase 1 van de MJOP AI-agent. Dit document beschrijft alleen wat in `agent/` is geïmplementeerd.
Er is geen agent, geen modelaanroep en geen netwerkverkeer: alleen deterministische, alleen-lezen tools
bovenop de bestaande pipeline.

## Doel en grenzen

- Eén tool, `get_kengetal_candidates`: voor één MJOP-onderhoudsregel de bestaande kengetallen v1 opvragen,
  met herleiding naar bronnen.
- Een model (of agent-framework) kan deze tool later aanroepen, maar de tool zelf is modelonafhankelijk: de
  toolbeschrijving is `{name, description, input_schema}` met een JSON Schema (`agent.tool_specs()`).
- Geen nieuwe dependencies: `jsonschema` (al aanwezig) en de bestaande scripts.
- De tool schrijft nooit: geen canonieke data, geen menselijke besluiten, geen prijsobservaties, geen rapporten.

## Hergebruikte functies (alleen lezen)

| Bestaande functie | Gebruik |
|---|---|
| `match_kengetal.load_context(root)` | leest kengetallen v1, genormaliseerde observations, vocabularies en hun hashes |
| `human_match_review.load_json` | leest de beslissingenopslag (`data/match_review_decisions/...`) |
| `mjop_kengetal_workflow.run(raw, store, ctx, root)` | normalisatie → matching → actuele menselijke beslissing → bedrag |
| `human_match_review.canonical_sha256` | canonieke hash voor `call_id` en `decision_store_sha256` |

De tool rekent niets zelf. Bedragen zijn de Decimal-strings uit de bronbestanden, ongewijzigd.

## Contract

- Invoer: `agent/schemas/get_kengetal_candidates.input.schema.json` — het input-object v1 van
  `docs/matching_rules_v1.md`, strikt (`additionalProperties: false`). Er is **geen** pad-, bestands- of
  URL-veld; de gegevensroot komt uit de bestandslocatie van het pakket (`agent.contract.PROJECT_ROOT`) en is
  niet via `call_tool` te kiezen. Hoeveelheden zijn Decimal-strings (geen floats).
- Uitvoer: `agent/schemas/get_kengetal_candidates.output.schema.json`. Per kandidaat verplicht: kengetal-ID,
  `source_cluster_ids`, `source_clusters` met `observation_ids`, `observation_ids`; op het resultaat de
  bronhashes (`kengetallen_output_sha256`, `normalized_observations_sha256`, `decision_store_sha256`,
  `vocabularies_sha256`). `call_id` is een hash van invoer + bronhashes (geen tijd of willekeur).
- Fouten (`ToolError`): `INVALID_INPUT`, `SOURCE_INTEGRITY_ERROR`, `OUTPUT_CONTRACT_VIOLATION`,
  `UNKNOWN_TOOL`. Nooit een gegokte waarde.

## Prijsregel: voorstel is geen prijs

`price_presentation.is_accepted_price` is alleen `true` bij een actief menselijk besluit ACCEPT of ADJUST.
Zonder besluit (of na REJECT) geldt: `is_accepted_price=false`, `effective_amount=null`, en
`financial_result.effective_amount/effective_total=null`; het systeemvoorstel staat apart in
`system_candidate_amount`. Dit wordt drie keer afgedwongen: door de workflow zelf, door het uitvoerschema
(`if/then`) en door een fail-closed controle in de tool (`_traceability_errors`).

## Alleen-lezen: hoe het wordt geborgd

1. Statisch (`tests/agent_tools/test_agent_tool_readonly.py`): importallowlist, alleen de vermelde
   script-functies, geen schrijf-/proces-/netwerkaanroepen, geen `eval`/`exec`, geen padparameter in een toolschema.
2. Dynamisch: de tool draait in een sandbox waarin schrijven, verwijderen, procesaanroepen en netwerk een
   exception geven; de gelezen bestanden worden gecontroleerd.
3. Hashes: een sha256-manifest van `data/`, `reports/`, `schemas/`, `vocabularies/`, `config/`, `docs/` en
   `promotion_ledger.tracked_hashes()` is vóór en na uitvoering identiek.
4. Alle agent-tests blokkeren netwerk (`tests/agent_tools/conftest.py`).

## Tests en baseline

- `python -m pytest -q tests/agent_tools` — de agent-tests; gebruikt de vaste pre-promotie-fixture
  (`promotion_history.pre_promotion_fixture_root`) zodat nieuwe kengetallen de tests niet breken, plus één
  live-smoketest met alleen invarianten.
- `scripts/check_test_baseline.py` + `config/known_environment_failures.json`: onderscheidt nieuwe fouten
  van de drie bekende xpdf-omgevingsproblemen. Een bekende test wordt alleen getolereerd als xpdf 4.06
  ontbreekt én de foutmelding de bekende afhankelijkheidsfout is; met xpdf 4.06 wordt niets getolereerd.
  Gebruik:

  ```
  python -m pytest -q --junitxml=junit.xml || true
  python scripts/check_test_baseline.py junit.xml
  ```
- CI: `.github/workflows/agent-tests.yml` (alleen lezen, `contents: read`) draait de agent-tests en, met de
  gepinde xpdf 4.06, de volledige suite met de baselinecontrole.

## Privacy

- Geen modelprompts, geen runlogs en geen externe tracing; er is geen modelroute in dit pakket.
- De tests gebruiken uitsluitend data die al in de repository staat; er zijn geen nieuwe VvE-documenten of
  persoonsgegevens toegevoegd.
- Bestaande kwestie, buiten deze fase: de repository is publiek en bevat bron-MJOP's van VvE's (`data/raw/`) en
  app-bundels. Of dat zo moet blijven is een aparte beslissing.

## Bewust niet in fase 1

Geen agent-loop, geen modelaanroep, geen schrijf-tools, geen extractie van nieuwe documenten, geen wijziging
aan MJOP-App of bestaande scripts.
