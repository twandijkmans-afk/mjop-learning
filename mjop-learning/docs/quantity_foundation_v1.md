# Quantity Foundation v1 — quantity observations, evidence-contract en resolutie

Uitvoering van milestone M1/M2 uit [quantity_engine_feasibility_v1.md](quantity_engine_feasibility_v1.md)
(§11 Quantity evidence model, §12 Historische quantity observations). Dit document beschrijft alleen wat
geïmplementeerd is.

| Onderdeel | Bestand |
|---|---|
| Builder (deterministisch) | `scripts/build_quantity_observations.py` |
| Evidence-contract + resolutie | `scripts/quantity_evidence.py` |
| Schema's | `schemas/quantity_observation.schema.json`, `schemas/quantity_evidence.schema.json`, `schemas/quantity_resolution_record.schema.json` |
| Output (afgeleid) | `data/quantity_observations/quantity_observations_v1.json`, `reports/quantity_observations_v1.md` |
| Resolutie-opslag (append-only, nu leeg) | `data/quantity_resolutions/quantity_resolution_records.json` |
| Tests | `tests/test_quantity_observations.py`, `tests/test_quantity_evidence.py` |

Niet in deze versie:
- Drawing Reader, OCR en vision-AI; AHN en BGT.
- Scores of confidence; fuzzy matching.
- Hoeveelheidsratio's of het "leren" van hoeveelheden.
- Nieuwe kengetallen, of wijzigingen aan price observations, comparability en kengetallen.

## Twee soorten hoeveelheid

| `quantity_kind` | Betekenis | Waar |
|---|---|---|
| `ELEMENT_QUANTITY` | hoeveel er van het element is (bijv. gevel 2.983 m²) | elementenoverzicht → **quantity observation** |
| `ACTION_QUANTITY` | hoeveel er per uitvoering gedaan wordt (bijv. herstel 5,93 m², reinigen 1 post) | jarenplanrij → **price observation** (ongewijzigd) |
| `SHARE_QUANTITY` | aandeel/breukdeel (gereserveerd in het contract; nog niet gebruikt) | — |

Een quantity observation verwijst naar de actiehoeveelheden van hetzelfde element (`linked_action_quantities`,
via `element.element_id`) met alleen `price_observation_id`, `quantity_value`, `unit_normalized`,
`action_normalized` en de relatie tot de elementhoeveelheid. Die relatie is een van:

- `SAME_AS_ELEMENT`
- `FRACTION_OF_ELEMENT`
- `EXCEEDS_ELEMENT`
- `DIFFERENT_UNIT`
- `ACTION_LUMP_SUM_OR_UNKNOWN_UNIT`
- `ELEMENT_NOT_MEASURABLE`

Er wordt niets gekopieerd of aangepast in de price observations.

## Quantity observation

Eén record per elementoverzicht-rij met een hoeveelheid in `data/verified/*.json`, met:

- **Identiteit en bron:** `quantity_observation_id` (`QO-<element_id>`), `document_id`, `source_file` (pad + sha256 uit `reports/document_registry.json`).
- **Afhankelijkheid:**
  - `source_cluster`: ongewijzigd uit `data/comparability/comparability_batch1.json`;
  - `document_relations`: uit `document_relations.json`, met `quantity_semantics`.
- **Element:** `element` (code origineel/intern, omschrijving, locatie, materiaal zoals verified het heeft).
- **Classificatie:**
  - `quantity_kind = ELEMENT_QUANTITY`;
  - `method_class = SOURCE_REPORTED`;
  - `source_type = MJOP_ELEMENT_OVERVIEW`;
  - `direct_or_derived = DIRECT`.
- **Waarde:** `quantity_value` (Decimal-string, exact zoals verified) en `quantity_as_stated` (de letterlijke tekst, bijv. `2983,00`). Die laatste is teruggevonden in het brontekstfragment en wordt niet aangenomen.
- **Eenheid:** `unit_original` / `unit_normalized` en `measurable` (m2/m1/m3/stuks).
- **Provenance:** `provenance` wordt volledig overgenomen. `provenance_check` legt vast of de verplichte velden aanwezig zijn en of de hoeveelheid letterlijk in het fragment staat.
- **Review:** `caveats` (informatief), `review_reasons` (vereisen een mens), `requires_human_review`, `status` (`SOURCE_REPORTED` / `REVIEW_REQUIRED`).

### Documentrelaties voor hoeveelheden

| Relatietype | `quantity_semantics` | Gevolg |
|---|---|---|
| `duplicate_source`, `version_of_same_mjop`, `same_building_other_inspection` | `SAME_OBJECT` | Exacte vergelijking op (code, omschrijving, locatie, eenheid). Een gelijke waarde → caveat `SAME_IN_RELATED_DOCUMENT` (**geen** onafhankelijke bevestiging). Een andere waarde → `DIFFERS_FROM_RELATED_DOCUMENT` (bewaard, niet opgelost, niet gemiddeld). |
| `subplans_same_complex` | `SAME_COMPLEX_OTHER_SCOPE` | Geen vergelijking: ander deelplan, ander onderwerp. |

Let op: DOC-002 en DOC-004 liggen in verschillende **prijs**-source clusters (op rijniveau geen
prijsafhankelijkheid vastgesteld), maar gaan over hetzelfde gebouw. Hun elementhoeveelheden zijn grotendeels
identiek, en worden daarom als afhankelijk gemarkeerd. De source clusters zelf zijn niet gewijzigd.

### Review-redenen (deterministisch)

| Reden | Regel |
|---|---|
| `UNIT_UNKNOWN` | `unit_normalized` is null |
| `FRACTIONAL_PIECE_COUNT` | stuks met een niet-geheel aantal |
| `ZERO_QUANTITY` | hoeveelheid 0 |
| `QUANTITY_ONE_IN_MEASURED_UNIT` | precies 1 in m2/m1/m3 (mogelijk plaatshouder) |
| `UNIT_IN_TEXT_DIFFERS` | omschrijving noemt een andere eenheid (m2/m1/m3/st) dan de eenheidskolom |
| `QUANTITY_TEXT_NOT_LOCATED` | hoeveelheid niet eenduidig in het tekstfragment gevonden |
| `PROVENANCE_INCOMPLETE` | `document_id`, `page`, `text_fragment` of `extraction_rule` ontbreekt |
| `SOURCE_FLAGGED` | verified markeert de hoeveelheid al (`conflict` / `requires_human_review`) |
| `DUPLICATE_KEY_DIFFERENT_QUANTITY` | zelfde code + omschrijving + locatie + eenheid met een andere hoeveelheid in één document |
| `AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH` | een gekoppelde actiehoeveelheid heeft een andere meetbare eenheid dan het element |
| `ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY` | een gekoppelde actiehoeveelheid (zelfde eenheid) is groter dan de elementhoeveelheid |

Caveats (geen review):
- `LUMP_SUM_NOT_A_MEASURED_QUANTITY`
- `ELEMENT_CODE_EXTERNAL`
- `BLOCK_ID_MISSING`
- `DUPLICATE_KEY_SAME_QUANTITY`
- `SAME_IN_RELATED_DOCUMENT`
- `DIFFERS_FROM_RELATED_DOCUMENT`

### Resultaat (main, batch 1 + testbatch 01)

- **Aantallen:** 662 quantity observations uit 11 documenten. DOC-011 en DOC-015 hebben geen elementhoeveelheden.
- **Eenheden:** m2 283, m1 172, stuks 157, post 48, onbekend 2.
- **Provenance:**
  - compleet: 662/662;
  - hoeveelheid letterlijk teruggevonden: 661/662;
  - block_id: 646/662.
- **REVIEW_REQUIRED: 48.** Uitgesplitst:
  - `QUANTITY_ONE_IN_MEASURED_UNIT` 31
  - `AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH` 9
  - `DUPLICATE_KEY_DIFFERENT_QUANTITY` 3
  - `ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY` 2
  - `UNIT_IN_TEXT_DIFFERS` 2
  - `UNIT_UNKNOWN` 2
  - `QUANTITY_TEXT_NOT_LOCATED` 1
- **Afhankelijkheid tussen documenten over hetzelfde object:**
  - 232 observations met een identieke hoeveelheid in zo'n document;
  - 18 met een afwijkende hoeveelheid.

Details staan in `reports/quantity_observations_v1.md`.

## Quantity evidence (contract)

`quantity_evidence` is bewijs voor een hoeveelheid van een **concreet gebouw**.

- **Onveranderlijk:** `evidence_id = "QE-" + sha256(inhoud)[:16]`, dus een aangepast record valt op (`evidence_errors`).
- **`method_class`:** `DIRECT_MEASURED`, `SOURCE_REPORTED`, `GEOMETRY_DERIVED` (vereist `calculation`), `ESTIMATED` of `MANUAL`.
- **`source_type`:** `MJOP_ELEMENT_OVERVIEW`, `MJOP_JARENPLAN_ROW`, `BAG`, `3D_BAG`, `QUOTE`, `DRAWING` of `MANUAL`.
- **`quantity_subject.subject_id`:** `make_subject_id(building_id, element_code_internal, location_scope, unit, quantity_kind)`. De sleutel bevat geen vrije tekst, zodat 3D BAG, een oud MJOP en een tekening naar hetzelfde onderwerp kunnen verwijzen.
- **`status`:** `PROPOSED`, `REVIEW_REQUIRED` of `SUPERSEDED`. Er is geen score.
- **Koppeling aan een gebouw:** `evidence_from_quantity_observation(qo, building_id=…, subject_id=…, building_link_ref=…)` weigert zonder `building_link_ref`. De koppeling "dit historische MJOP gaat over dit gebouw" is een menselijke stap. Een `building_id` wordt nooit afgeleid uit document-ID's (tenant-/bronscheiding).

In deze versie wordt nog **geen** evidence-data aangemaakt: er is nog geen bevestigde koppeling tussen
historische documenten en gebouwen in MJOP-App.

## Quantity resolution records (append-only)

Hetzelfde patroon als de human decision records (`docs/human_review_v1.md`):

- Per `(building_id, subject_id)` is er hoogstens één `ACTIVE` record.
- Een herziening is een nieuw record met `supersedes`; het vorige record wordt `SUPERSEDED`. Een `REVIEW_REQUIRED` record (invoer veranderd) wordt ook vervangen, nooit verwijderd.
- `append_only_errors(old, new)` staat alleen deze statusovergangen toe:
  - `ACTIVE → SUPERSEDED`
  - `ACTIVE → REVIEW_REQUIRED`
  - `REVIEW_REQUIRED → SUPERSEDED`
- `decision` is een van:
  - `ACCEPT_EVIDENCE`: `resolved_value` is **exact** de waarde van `selected_evidence_id`;
  - `USER_VALUE`: de waarde staat zelf als `MANUAL`-evidence vast (`manual_evidence_id`);
  - `UNKNOWN`: geen waarde.
- `considered_evidence_ids` bewaart alle bronnen die de mens zag. `decision_reason` is verplicht; `reviewer_type` is altijd `human`.
- **Nooit middelen.** `validate_resolution` weigert elke `resolved_value` die niet exact gelijk is aan de gekozen evidence. Voorbeeld uit de haalbaarheidsanalyse: 3D BAG 312,6, oud MJOP 308, tekening 311,8. Kiezen kan; 310,8 vastleggen kan niet (getest).

`data/quantity_resolutions/quantity_resolution_records.json` is nu een lege, geldige opslag.

## Gebruik

```bash
python3 scripts/build_quantity_observations.py            # schrijft de output (weigert andere bestaande inhoud)
python3 scripts/build_quantity_observations.py --check    # 0 = output hoort bij de invoer, schrijft niets
python3 scripts/build_quantity_observations.py --replace  # bewust vervangen na gewijzigde invoer
python3 -m pytest tests/test_quantity_observations.py tests/test_quantity_evidence.py
```
