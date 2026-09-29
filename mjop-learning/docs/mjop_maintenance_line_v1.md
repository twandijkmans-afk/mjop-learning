# MJOP maintenance line — versie 1

Beschrijft de implementatie in `scripts/mjop_maintenance_line.py`
(`LINE_VERSION = "mjop_maintenance_line_v1"`); schema
`schemas/mjop_maintenance_line.schema.json`; tests
`tests/test_mjop_maintenance_line.py`. Dit document beschrijft alleen wat
geïmplementeerd is.

## Doel

Eén expliciet domeinobject voor een onderhoudsregel van een **nieuw** MJOP:
wat wordt onderhouden, hoeveel, wanneer, en welk bedrag (met herkomst) er
voor de regel geldt. Een regel mag bestaan zonder bedrag: *geen bedrag* is
geen ongeldige regel.

## Verschil met `maintenance_action`

`schemas/maintenance_action.schema.json` beschrijft historische,
geëxtraheerde posten uit bestaande MJOP-documenten (met extractie-provenance).
De maintenance line is een nieuw domeinobject voor een nieuw MJOP en gebruikt
historische kennis uitsluitend read-only (via de kengetalworkflow). In de
repository bestond geen ander model voor een nieuwe MJOP-regel; de
matchvelden volgen het input-object v1 van `docs/matching_rules_v1.md`.

## Velden

| Groep | Velden |
|---|---|
| Identiteit | `maintenance_line_id`, `mjop_id`, `object_id` (verplicht, niet leeg), `line_version` |
| Wat | `element_code_internal`, `object_description`, `action_normalized`, `action_text`, `unit_normalized`, `unit_text`, `material_normalized`, `material_text`, `material_source`, `vat_basis`, `price_level_requested`, `context` (`building_type`, `construction_year`, `location`, `condition_defect`, `maintenance_type`) |
| Hoeveelheid | `quantity`: Decimal-string > 0, of null |
| Planning | `planned_year`, `proposed_planned_year`, `cycle_years` (≥ 1), `last_maintenance_year`, `last_replacement_year` |
| Status | `line_status`, `price_status` |
| Kengetal/matching | `kengetal_match` (zie hieronder) |
| Financieel | `manual_amount`, `financial` |
| Herkomst | `provenance` |

`kengetal_match` (null tot een workflowresultaat is toegepast):
`workflow_status`, `match_result_id`, `match_status` (final_status van de
match), `match_reasons`, `kengetal_id` (het voorgestelde kengetal),
`system_candidate_amount`, `human_match_decision_id`, `decision_status`
(`NO_DECISION`/`ACCEPTED`/`ADJUSTED`/`REJECTED`), `human_selected_kengetal_id`.

`financial`: `amount_source`, `unit_amount`, `unit_amount_display`, `unit`,
`effective_total`, `effective_total_display`, `total_not_computed_reason`,
`price_level`, `vat_basis`, `indexation` (altijd `none`).

## Statusmodel

Twee aparte velden:

**`price_status`** — de toestand van het bedrag:

| Waarde | Betekenis |
|---|---|
| `NO_AMOUNT` | geen bedrag en geen voorstel (nog niet door de workflow, geen geschikt kengetal, of review zonder kandidaat) |
| `SYSTEM_PROPOSED` | de matching stelt een kengetal voor (`CANDIDATE_FOUND`, of review met één kandidaat); **geen** effectief bedrag |
| `HUMAN_ACCEPTED` | een mens accepteerde het voorgestelde kengetal |
| `HUMAN_ADJUSTED` | een mens paste het voorstel aan (ander kengetal of eigen bedrag) |
| `MANUALLY_SET` | handmatig bedrag (`MANUAL_AMOUNT`) |
| `REJECTED` | een mens wees het voorstel af; geen bedrag |

**`line_status`** — afgeleid uit het bedrag en de workflow:

| Waarde | Wanneer |
|---|---|
| `READY` | `price_status` is `HUMAN_ACCEPTED`, `HUMAN_ADJUSTED` of `MANUALLY_SET`: er is een definitief bedrag voor deze regel |
| `REVIEW_REQUIRED` | anders, als het laatst toegepaste workflowresultaat `MATCH_PENDING_DECISION` of `REVIEW_REQUIRED` is: een mens moet beslissen |
| `DRAFT` | in alle andere gevallen (nieuw, geen kengetal, afgewezen) |

`CANDIDATE_FOUND` uit de matching maakt een regel dus **niet** financieel
definitief: dat wordt `SYSTEM_PROPOSED` + `REVIEW_REQUIRED`. Er is geen
automatische goedkeuring.

## Amount sources

`financial.amount_source` is null of één van:

| Bron | Wanneer | Vereist |
|---|---|---|
| `SYSTEM_KENGETAL` | ACCEPT van het voorgestelde kengetal (workflowbron `SYSTEM_KENGETAL_ACCEPTED`) | `price_status` `HUMAN_ACCEPTED`, actieve beslissing (`human_match_decision_id`), `provenance` |
| `HUMAN_SELECTED_KENGETAL` | ADJUST naar een ander kengetal | `HUMAN_ADJUSTED`, actieve beslissing, `provenance` |
| `HUMAN_ADJUSTMENT` | ADJUST met een eigen bedrag | `HUMAN_ADJUSTED`, actieve beslissing, `provenance` |
| `MANUAL_AMOUNT` | handmatig bedrag | `MANUALLY_SET`, `manual_amount` |

Een bedrag (`unit_amount`) bestaat alleen met een bron, en een bron alleen met
een bedrag; bij `NO_AMOUNT`, `SYSTEM_PROPOSED` en `REJECTED` is er geen bedrag.

## Relatie met Matching v1, Human Match Review en de workflow

De domeinlaag bewaart de toestand; `scripts/mjop_kengetal_workflow.py` blijft
verantwoordelijk voor normalisatie → matching → menselijke beslissing →
effectief bedrag. De koppeling:

- `to_workflow_input(line)`: levert het input-object v1 (`object_id` en de
  gevulde match- en contextvelden; geen planningvelden);
- `apply_workflow_result(line, result)`: neemt het workflowresultaat over.
  Het resultaat moet bij exact deze regel horen (`result.input` ==
  `to_workflow_input(line)`), anders fout. `price_status` volgt uit de
  workflowstatus (`ACCEPTED`→`HUMAN_ACCEPTED`, `ADJUSTED`→`HUMAN_ADJUSTED`,
  `REJECTED`→`REJECTED`, `MATCH_PENDING_DECISION`→`SYSTEM_PROPOSED`,
  `NO_KENGETAL`→`NO_AMOUNT`, `REVIEW_REQUIRED`→`SYSTEM_PROPOSED` met kandidaat
  of anders `NO_AMOUNT`). Het effectieve bedrag, totaal en prijspeil worden
  ongewijzigd uit het workflowresultaat overgenomen;
- `run_workflow_for_line(line, decision_store)`: beide stappen achter elkaar.

Menselijke beslissingen worden alleen via human match review vastgelegd
(`docs/human_match_review_v1.md`); de domeinlaag maakt geen beslissingen.

## Financiële berekening

`effective_total = unit_amount × quantity` in exacte Decimal-rekenkunde,
zonder tussentijdse afronding, alleen als er een bedrag is, `quantity`
aanwezig en positief is, en `financial.unit` exact gelijk is aan
`unit_normalized`. Anders null met `total_not_computed_reason`
(`NO_EFFECTIVE_AMOUNT`, `QUANTITY_MISSING`, `QUANTITY_NOT_POSITIVE`,
`UNIT_MISMATCH`). Dezelfde regel als de workflow. `*_display` = afronding op
0.01 (ROUND_HALF_EVEN), alleen voor weergave. Geen eenheidsconversie, geen
indexatie. Voorbeeld C1: €33,478605…/m² × 80 m² = €2.678,2884…, weergave
€2.678,29.

## Planningvelden

`planned_year`, `last_maintenance_year`, `last_replacement_year` en
`cycle_years` worden alleen door de gebruiker gezet; onbekend blijft null.
Het bouwjaar (`context.construction_year`) wordt **nooit** als onderhouds- of
vervangingsjaar gebruikt. `proposed_planned_year` is gereserveerd voor een
toekomstige planner en wordt in v1 niet gevuld (validatie weigert een waarde).
Er is geen planningslogica.

## Handmatige bedragen

`set_manual_amount(line, amount, unit, price_level, vat_basis, reason)`:
bedrag ≥ 0, `unit` exact gelijk aan `unit_normalized` (geen conversie),
`reason` verplicht; `manual_amount.source` = `MANUAL_AMOUNT`. Een handmatig
bedrag wordt geen historische kennis en verandert niets aan price
observations, comparability of kengetallen. Het blijft leidend: een later
toegepast workflowresultaat werkt alleen `kengetal_match` en `provenance`
bij.

`clear_manual_amount(line)` verwijdert een handmatig bedrag (alleen bij
`MANUALLY_SET`, anders `LineError`): `manual_amount`, de bron
`MANUAL_AMOUNT`, het effectieve bedrag en het totaal vervallen, en ook
`kengetal_match` en `provenance`. De regel wordt `NO_AMOUNT` / `DRAFT`. Er is
**geen fallback** naar een eerder kengetal of bedrag en er wordt geen
matching uitgevoerd; een kengetal komt alleen terug door de workflow opnieuw
te draaien (`run_workflow_for_line`).

## BTW-basis

De maintenance line voert zelf geen BTW-logica, -conversie of -berekening
uit; bedragen worden nooit omgerekend. De BTW-controle zit in de matching
(`VAT_BASIS_DIFFERS` → `HUMAN_REVIEW_REQUIRED`; ontbrekende basis → caveat
`VAT_BASIS_NOT_GIVEN`, zie `docs/matching_rules_v1.md`).

`financial.vat_basis` komt van:

| Bron van het bedrag | `financial.vat_basis` |
|---|---|
| `SYSTEM_KENGETAL` | `vat_basis` van de regel — dezelfde waarde die als input naar de matching ging en daar tegen de BTW-basis van het kengetal is gecontroleerd |
| `HUMAN_SELECTED_KENGETAL` | idem: `vat_basis` van de regel |
| `HUMAN_ADJUSTMENT` | idem: `vat_basis` van de regel (de human match decision legt geen eigen BTW-basis vast; een toelichting staat in `amount_basis`) |
| `MANUAL_AMOUNT` | `manual_amount.vat_basis`, zoals door de gebruiker opgegeven bij het bedrag |

Een onbekende BTW-basis van de regel blijft null en wordt niet uit het
kengetal afgeleid.

## Provenance

`provenance` gebruikt de bestaande IDs en hashes van het workflowresultaat:
`workflow_result_id`, `match_result_sha256`, `decision_store_sha256`,
`rule_versions`, `input_hashes`; samen met `kengetal_match`
(`match_result_id`, `kengetal_id`, `human_match_decision_id`). Er is geen
eigen provenance-systeem.

## User-editable versus system-derived

- **User-editable** (`USER_EDITABLE_FIELDS`, via `new_line` en
  `update_user_fields`): de wat-velden, `vat_basis`, `price_level_requested`,
  `context`, `quantity` en de planningvelden; plus een handmatig bedrag via
  `set_manual_amount` en het wissen daarvan via `clear_manual_amount`.
- **System-derived** (`SYSTEM_DERIVED_FIELDS`): `line_status`,
  `price_status`, `kengetal_match`, `financial`, `provenance`,
  `proposed_planned_year`. `update_user_fields` weigert deze.
- Een wijziging van een veld dat het matchresultaat bepaalt
  (`MATCH_INPUT_FIELDS`, inclusief `quantity`) laat een kengetal-afgeleid
  bedrag en `kengetal_match`/`provenance` vervallen (`NO_AMOUNT`; de workflow
  moet opnieuw draaien). Een handmatig bedrag blijft, met herberekend totaal,
  tenzij de eenheid verandert (dan vervalt het ook). Planningvelden raken het
  bedrag niet.

Alle functies geven een nieuwe regel terug, muteren de invoer niet en
valideren het resultaat (`line_errors`: schema plus totaal = bedrag ×
hoeveelheid, eenheden, display-waarden, samenhang van statussen). Ongeldig →
`LineError`.

## Opslag

Er is in deze repository geen planbeheer of opslag voor nieuwe MJOP's; v1
voegt die niet toe. De regel is een JSON-document dat het (externe)
planbeheer kan bewaren.

## Wat v1 niet doet

Geen opslag, UI, Supabase, BAG/3D BAG, dashboard, automatische planning,
conditie → levensduur, cyclusberekening, reservefonds, cashflow,
offertevergelijking, learning loop, automatische toevoeging aan kengetallen,
AI/foto-matching, fuzzy matching, ranking/scoring/confidence, indexatie of
eenheidsconversie.
