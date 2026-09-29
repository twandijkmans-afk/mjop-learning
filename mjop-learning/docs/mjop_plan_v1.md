# MJOP Plan v1

Pure domeinlaag voor **een versie van een nieuw MJOP**. Een MJOP (`mjop_id`) heeft een
of meer versies (`version_id`). Elke versie verwijst naar een vaste set Maintenance Lines
(Maintenance Line v1, [mjop_maintenance_line_v1.md](mjop_maintenance_line_v1.md)).

| Onderdeel | Bestand |
|---|---|
| Schema | `schemas/mjop_plan.schema.json` |
| Module | `scripts/mjop_plan.py` |
| Tests | `tests/test_mjop_plan.py` |

**Wat deze laag niet doet.** Er is geen opslag: het productplatform bewaart plannen. Er is
ook geen database, UI, BAG-koppeling, reservefonds, cashflow, indexatie, cyclusdoorrekening,
automatische planning, score, ranking of confidence.

De laag bevat geen eigen provenance- of kennissysteem. De herkomst komt uit de bestaande
`provenance` van de regels.

Maintenance Line v1 is ongewijzigd. Alle functies zijn puur: ze geven een nieuwe versie
terug, muteren hun invoer niet en valideren het resultaat met `plan_errors`. Bij een
ongeldige bewerking geven ze `PlanError`.

## Velden

| Groep | Velden |
|---|---|
| Identiteit | `plan_model_version` (`mjop_plan_v1`), `mjop_id`, `version_id` = `{mjop_id}-V{version_number:03d}`, `version_number` (≥ 1), `supersedes_version_id` |
| Gebouw | `building_id` (verplicht, niet leeg) |
| Metadata | `name`, `address`, `building_type`, `construction_year`, `renovation_year`, `number_of_units`, `inspection_date`; `metadata_source` is altijd `USER_ENTERED` |
| Horizon | `plan_start_year`, `plan_end_year` |
| Regels | `maintenance_line_ids` (uniek), `line_hashes` |
| Vastlegging | `content_sha256`, `knowledge_basis`, `readiness_warnings` |
| Historie | `plan_status`, `status_history` (events `{event, at, by, reason}`), `created_at`, `updated_at` |

Over `building_id`:
- Het staat los van `maintenance_line.object_id`.
- Het wordt nooit afgeleid uit historische document-IDs.
- Er is geen regex-, prefix- of patrooncontrole. Een waarde zoals `DOC-002-BLD-001` wordt
  dus niet geweigerd.

Alle metadata wordt door de gebruiker ingevoerd. Onbekende waarden blijven `null`. Het
bouwjaar is geen onderhoudsjaar.

## Statusmodel

```
DRAFT --submit_for_review--> IN_REVIEW --approve--> READY --(approve van opvolger)--> SUPERSEDED
  ^                              |                    |
  +------return_to_draft---------+                    +--create_next_draft--> nieuwe versie (DRAFT)
```

| Functie | Van → naar | Voorwaarden | Effect |
|---|---|---|---|
| `new_plan(mjop_id, building_id, *, at, by=None, **metadata)` | → DRAFT (v1) | – | event CREATED |
| `update_plan_metadata(v, *, at, **changes)` | DRAFT | alleen metadata en `building_id` | alleen `updated_at` verandert mee |
| `set_horizon(v, start, end, *, at)` | DRAFT | `start ≤ end`; lengte vrij | idem |
| `set_line_ids(v, ids, *, at)` | DRAFT | IDs uniek | idem |
| `submit_for_review(v, lines, *, at, by, reason=None)` | DRAFT → IN_REVIEW | zie onder | legt `line_hashes` vast |
| `return_to_draft(v, *, at, by, reason)` | IN_REVIEW → DRAFT | `reason` verplicht | `line_hashes` vervalt |
| `approve(v, lines, *, at, by, reason, previous_ready=None)` | IN_REVIEW → READY | zie onder | geeft `(ready, superseded_or_None)` |
| `create_next_draft(ready, *, at, by=None)` | READY → nieuwe DRAFT | – | zie onder |

**Voorwaarden voor `submit_for_review`:**
- De horizon is ingevuld.
- De meegegeven regels zijn exact de set `maintenance_line_ids`: niet meer, niet minder,
  geen dubbelen.
- Elke regel heeft hetzelfde `mjop_id`.
- `line_errors` is leeg voor elke regel.

**Voorwaarden voor `approve`:**
- Er is een expliciete menselijke actie: `by` en `reason` zijn verplicht.
- De regels zijn ongewijzigd sinds indienen: hun hash is gelijk aan `line_hashes`.
- Geen regel heeft `line_status` REVIEW_REQUIRED.
- Heeft de versie een `supersedes_version_id`? Dan moet die READY-versie als
  `previous_ready` worden meegegeven. Die wordt als SUPERSEDED teruggegeven, met event
  SUPERSEDED.

**Wat blokkeert READY niet.** Regels zonder bedrag, afgewezen regels, regels buiten de
horizon, regels zonder `planned_year` en bedragen zonder totaal blokkeren READY niet. Ze
worden vastgelegd in `readiness_warnings`, met de tellers `no_amount`, `rejected`,
`amount_without_total`, `outside_horizon` en `without_planned_year`.

Er zijn geen automatische overgangen.

**Status en laatste event.** De laatste gebeurtenis in `status_history` moet bij de status
passen:

| Status | Toegestane laatste event |
|---|---|
| DRAFT | CREATED of RETURNED_TO_DRAFT |
| IN_REVIEW | SUBMITTED_FOR_REVIEW |
| READY | APPROVED |
| SUPERSEDED | SUPERSEDED |

**Velden per status (schema):**

| Status | Horizon (integer) | `line_hashes` | `content_sha256`, `knowledge_basis`, `readiness_warnings` |
|---|---|---|---|
| DRAFT | – | `null` | `null` |
| IN_REVIEW | verplicht | verplicht | – |
| READY / SUPERSEDED | verplicht | verplicht | verplicht |

## Versies en immutability

- **Alleen DRAFT is bewerkbaar.** Elke bewerkfunctie weigert IN_REVIEW, READY en SUPERSEDED.
- **`line_hashes`** is `canonical_sha256(line)` per regel, uit `human_match_review`. Deze
  hashes worden vastgelegd bij indienen en gecontroleerd bij goedkeuren. Daarna meldt
  `plan_errors(version, lines)` elke afwijking als `line_hash wijkt af`.
- **Een regel is gewijzigd?** Dan krijgt de nieuwe versie een regel met een nieuw
  `maintenance_line_id` (zelfde `mjop_id`). De oude versie blijft zo geldig tegen de oude
  regel.
- **Een regel is ongewijzigd?** Dan mag die door meerdere versies van hetzelfde MJOP worden
  gebruikt. Voorbeeld: versie 1 → regel A; versie 2 → regel A + nieuwe regel B.
- **`content_sha256`** wordt gezet bij APPROVED. Het is de canonieke sha256 over:
  - `plan_model_version`, `mjop_id`, `version_id`, `version_number`, `supersedes_version_id`;
  - `building_id`, alle metadata en `metadata_source`;
  - de horizon;
  - `maintenance_line_ids` en `line_hashes`.

  Status, `status_history`, tijdstempels, `knowledge_basis` en `readiness_warnings` tellen
  niet mee. Daardoor blijft de hash gelijk bij de overgang READY → SUPERSEDED.
  `plan_errors` meldt elke inhoudswijziging.
- **`create_next_draft`** maakt een nieuwe DRAFT:
  - `version_number + 1`, met `supersedes_version_id` gezet;
  - metadata, horizon en ID-set worden overgenomen;
  - event CREATED;
  - de READY-versie zelf blijft ongewijzigd.
- **`versions_errors(versions)`** controleert over alle versies van één MJOP:
  - Alle versies hebben hetzelfde `mjop_id`.
  - `version_number` is uniek en aaneengesloten vanaf 1.
  - `supersedes_version_id` wijst naar een bestaande, eerdere versie, en elke versie wordt
    hooguit één keer opgevolgd.
  - Er is hooguit één READY-versie.
  - Er is hooguit één open versie (DRAFT of IN_REVIEW).
  - Elke SUPERSEDED-versie heeft een vastgestelde opvolger (READY of SUPERSEDED).

## Totalen (`plan_totals(version, lines)`)

`plan_totals` is read-only en wordt afgeleid. Het resultaat wordt niet in de versie
opgeslagen.

**Welke regels tellen financieel mee.** Een regel telt mee als aan alle vier voorwaarden is
voldaan:
- `price_status` is HUMAN_ACCEPTED, HUMAN_ADJUSTED of MANUALLY_SET;
- `effective_total` is aanwezig;
- `planned_year` is aanwezig;
- `planned_year` ligt binnen de horizon.

Zonder horizon telt geen enkele regel financieel mee.

**BTW-basis.** Alle uitsplitsingen zijn per BTW-basis: `inclusive`, `exclusive`, of
`unknown` als `vat_basis` null is. Er is geen totaal over BTW-bases heen.

| Uitsplitsing | Sleutel |
|---|---|
| `per_vat_basis` | BTW-basis |
| `per_planned_year` | jaar → BTW-basis |
| `per_action` | `action_normalized` → BTW-basis (null wordt `unknown`) |
| `per_element_code` | `element_code_internal` → BTW-basis (null wordt `unknown`) |

Elk blad heeft de vorm `{total_exact, total_display, lines}`. Er wordt exact met Decimal
gerekend, zonder tussentijdse afronding. `total_display` is afgerond op 0,01 met
ROUND_HALF_EVEN.

**Tellers (`counts`).** De tellers kunnen overlappen:

| Teller | Wat wordt geteld |
|---|---|
| `lines_total` | alle regels |
| `in_financial_totals` | regels die financieel meetellen |
| `no_amount` | regels met `price_status` NO_AMOUNT |
| `system_proposed` | regels met `price_status` SYSTEM_PROPOSED |
| `review_required` | regels met `line_status` REVIEW_REQUIRED |
| `rejected` | regels met `price_status` REJECTED |
| `amount_without_total` | definitieve regels zonder `effective_total` |
| `outside_horizon` | regels met een `planned_year` buiten de horizon |
| `without_planned_year` | regels zonder `planned_year` |

**Prijspeil (`price_levels`).**
- De kengetal-prijspeiljaren en de handmatige prijspeilen worden gerapporteerd, samen met
  `any_mixed_price_level` en `any_missing_price_level`.
- `indexation` is altijd `"none"`.
- Een notitie vermeldt dat het om historische, niet-geïndexeerde bedragen gaat. Een totaal
  is dus geen prijs van één specifiek jaar.

Er is geen cyclusdoorrekening: elke regel telt één keer, in zijn `planned_year`.

## Provenance (`knowledge_basis`)

`knowledge_basis` wordt bij APPROVED afgeleid uit de bestaande `provenance` van de regels.
Er is geen tweede herkomstsysteem. Het bevat:
- de gesorteerde sets van `kengetallen_output_sha256`, `normalized_observations_sha256` en
  `decision_store_sha256`;
- `rule_versions` per sleutel, met alle voorkomende waarden;
- `amount_sources`: het aantal regels per `amount_source` (`none` als dat null is);
- `lines_without_provenance`.

Uit de `line_hashes` plus de regels is de volledige herkomst per regel te herleiden: de
workflow, het matchresultaat, de beslissing en de kengetallen.

## Tests

`tests/test_mjop_plan.py` bevat 45 tests. De regels zijn echte C1/C2-regels via
`run_workflow_for_line`, met beslissingen alleen in het geheugen. Gedekt zijn:
- aanmaken en metadata;
- `building_id` zonder patrooncontrole;
- horizon;
- unieke regel-IDs;
- de voorwaarden bij indienen (exacte set, zelfde `mjop_id`, geldige regels);
- terug naar DRAFT;
- goedkeuren: mens en reden verplicht, REVIEW_REQUIRED blokkeert, waarschuwingen blokkeren
  niet, drift van regels;
- READY is niet bewerkbaar;
- detectie van manipulatie en van drift na READY;
- de reikwijdte van de content-hash;
- consistentie van `status_history`;
- volgende versie en opvolging, hergebruik van ongewijzigde regels, een nieuw ID bij een
  gewijzigde regel;
- `versions_errors`;
- totalen: populatie, scheiding per BTW-basis, horizon, exacte Decimal, prijspeil;
- `knowledge_basis`;
- geen eigen provenance- of scorevelden;
- puurheid en determinisme;
- data-integriteit.
