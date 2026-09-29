# mjop-learning

Gecontroleerde dataset-/kennispipeline die historische MJOP-documenten
(Meerjarenonderhoudsplannen voor Nederlandse VvE's) omzet in betrouwbare,
herleidbare, gestructureerde data als context voor een AI-MJOP-platform.

Lees eerst `CLAUDE.md` — dat zijn de vaste regels voor dit project (provenance
verplicht, nooit gegevens verzinnen, deterministische berekeningen, etc.).

## Nieuwe MJOP's toevoegen

Upload nieuwe PDF/XLS/XLSX-bestanden naar `data/incoming/`. De GitHub Actions-workflow
"Process incoming MJOPs" verwerkt ze tot een staging-batch en een rapport in
`reports/incoming/<batch_id>.json`, zonder AI en zonder canonieke data te wijzigen.
Uitleg voor niet-programmeurs: `docs/incoming_pipeline_v1.md`.

## Status

Batch 1 (10 documenten, zie `reports/batch1_selectie_voorstel.csv`) staat in
`data/raw/` en is volledig geëxtraheerd (`data/extracted/`) en genormaliseerd
(`data/normalized/`). 9 van de 10 documenten zijn door onszelf opgesteld (in
opdracht van Pro VvE Beheer / VvE Beheer B.V.); alleen DOC-004 (Innax, 2018)
is van een andere partij en telt niet mee voor de eigen-stijl-categorisering
hieronder. Zie "Volgende stap" hieronder voor de huidige review-status.
Onderstaande onderdelen zijn opgeleverd en getest (91/91 tests slagen):

- `schemas/` — datamodel voor document, building, element, observation,
  maintenance_action, plus twee gedeelde bouwstenen
  (`_extracted_value.schema.json`, `_provenance.schema.json`) die het
  "null i.p.v. gokken" + provenance-patroon afdwingen.
- `vocabularies/` — gecontroleerde termenlijsten (element_type, material,
  defect_type, condition_score, severity, maintenance_action, priority,
  status, unit), grotendeels gevalideerd tegen een woordfrequentie-scan van
  de 10 batch-1-documenten (`validated_against_batch1: true/false` per
  term).
- `vocabularies/element_code.json` — **nieuw**: het eigen NL-SfB-achtige
  coderingssysteem (29 hoofdgroepen, ~65 subcodes, plus `ZZZZ` voor
  staartkosten-percentages) zoals dat letterlijk in de 9 door onszelf
  opgestelde documenten staat (de 'Code'-kolom van het elementenoverzicht).
  Dit is de basis voor kentallen "op de manier waarop wij onze MJOP's
  opbouwen" i.p.v. een generieke, vrij-tekst-gebaseerde indeling.
- `scripts/inventory_documents.py` — **werkend**: bouwt
  `reports/document_inventory.{csv,json}` uit `data/raw/`.
- `scripts/normalize_batch.py` — **werkend**: deterministische
  vocabulaire-lookup + kostenberekening (quantity × unit_cost, Decimal).
  Onbekende termen worden nooit geraden (`normalized_value: null` +
  `requires_human_review: true`); een afwijkend vermeld totaalbedrag wordt
  gemarkeerd als `cost_conflict`, niet automatisch opgelost. Een nested
  review-vlag (op de action- of eenheidsterm) telt nu ook mee in het
  top-level `requires_human_review` van de maintenance_action/observation
  zelf, anders verdween zo'n post stilzwijgend uit de review-wachtrij.
  Kale "schilderwerk"-actieteksten (buiten/binnen niet gespecificeerd)
  worden deterministisch opgelost via het gekoppelde element
  (`derive_action_from_linked_element`) i.p.v. altijd voor een mens te
  blijven staan.
- `scripts/extract_batch.py` — **werkend** (na overleg over het extractie-
  ontwerp geïmplementeerd): zet voor elk document in de batch eerst een
  `data/extracted/<document_id>.json` placeholder neer, en voert daarna —
  alleen als `ANTHROPIC_API_KEY` gezet is (anders, of met `--dry-run`, blijft
  het bij placeholders) — de daadwerkelijke extractie uit via een
  Claude tool-use-call met een schema-afgeleid input-schema. Elke waarde komt
  terug als `{value, confidence, requires_human_review, provenance}`; de
  output wordt na ontvangst gevalideerd tegen de echte schemas in `schemas/`
  (1 herhaling bij een schemafout, daarna `status: "extraction_failed"`,
  nooit verzonnen data). Een deterministische ondergrens
  (`enforce_review_floor`) zet `requires_human_review` altijd op `true` bij
  lage confidence, `source_confidence: "low"` of een conflict — los van wat
  het model zelf claimt. `normalized_value` wordt door dit script altijd op
  `null` gehouden (`strip_normalization`); de vocabulaire-mapping blijft
  uitsluitend in `normalize_batch.py`. Elk bestand krijgt versie-metadata
  (`extraction_model`, `extraction_prompt_version`, `extracted_at`,
  `temperature`).
- `scripts/export_review_sheet.py` — **werkend**: bouwt
  `reports/review_batch1.xlsx` (2 tabbladen: maintenance_actions,
  observations) met alle posten die `requires_human_review: true` hebben,
  inclusief een REDEN-kolom (onbekende actieterm/eenheid, kostenconflict,
  afgeleide eenheidsprijs) en lege BESLISSING/GECORRIGEERDE_WAARDE/NOTITIES-
  kolommen voor de mens.
- `scripts/apply_review.py` — **werkend**: leest het ingevulde Excel-bestand
  terug en schrijft `data/verified/*.json`. Legt ACCEPT/EDIT/REJECT vast als
  `human_verification` op het juiste vocabulaire-veld (actie/eenheid/defect
  - nooit het verkeerde veld, ook niet als alleen de eenheid onbekend was)
  en als leesbare `review_note` op de post zelf, ook wanneer er geen
  vocabulaire-veld bij hoort (bijv. bij een kostenconflict). Een `edit`
  zonder ingevulde correctie wordt geweigerd (nooit zelf een waarde
  verzinnen); een `reject` blijft `requires_human_review: true` - dat
  betekent "ook een mens weet het niet", niet "opgelost".
- `scripts/backfill_element_codes.py` — **nieuw, eenmalige migratie**: vult
  `element_code` met terugwerkende kracht in voor de 9 al-geëxtraheerde
  eigen documenten (element_code bestond nog niet toen ze geëxtraheerd
  werden). Methode A: het document citeert de code al letterlijk in een
  bestaand `provenance.text_fragment` (492 van de 549 elementen). Methode B
  (alleen DOC-001, dat vóór provenance-tracking handmatig is opgebouwd):
  positionele koppeling aan een herscan van de brontekst, alleen als de
  beschrijving daadwerkelijk overeenkomt (52 elementen). 5 restgevallen met
  een regel-wrap in de PDF zijn stuk voor stuk tegen de brontekst geverifieerd
  (`DOC_001_MANUAL_OVERRIDES`). 0 van de 549 bleef onopgelost.
- `scripts/evaluate_dataset.py` — **werkend, maar het cijfer dat nu uitkomt
  is nog geen echte meting**: `data/verified/` bestaat, maar is nu alleen
  een kopie van `data/normalized/` waarin de eerder gevlagde posten
  bevestigd zijn (zie hieronder) - niet elk veld is onafhankelijk
  herleid uit het brondocument. Zie CLAUDE.md: geen accuracy-claims zonder
  een cijfer dat dat ook echt meet.
- `scripts/compute_kentallen.py` — **LEGACY / EARLIER EXPERIMENTAL CALCULATION**:
  niet de huidige kengetallen v1-pipeline (zie `scripts/build_kengetallen.py`
  hieronder; actuele output onder `data/kengetallen/`). Blijft voorlopig
  staan en kan later apart worden opgeschoond. Oorspronkelijke beschrijving:
  de eerste kentallen-
  berekening. Groepeert `data/verified/*.json` per (element_code, actie,
  eenheid) - dus op onze eigen indeling - en berekent per groep min/max/
  gemiddelde/mediaan, apart voor `literal` (letterlijke documentprijs,
  `unit_cost.value`) en `calculated` (afgeleid uit total/hoeveelheid,
  minder betrouwbaar). Telt alleen mee zonder `cost_conflict` en zonder
  openstaande `requires_human_review`. Schrijft naar
  `data/kentallen/kentallen_batch1.json` en `reports/kentallen_batch1.xlsx`.
  **Belangrijke bevinding onderweg**: `total_cost_as_stated: "€ 0"` betekent
  in deze documenten niet "gratis" - het item valt vaak buiten het getoonde
  jarenvenster (planned_year kan decennia verderop liggen), dus het totaal
  in de huidige weergave is 0 terwijl de kosten pas in een latere cyclus
  vallen. `normalize_batch.py` berekent nu geen `unit_cost_calculated` meer
  als het totaal exact 0 is - dat leverde eerst 32 valse "€0,00 per m²"
  kentallen op.
- `scripts/build_price_observations.py` + `scripts/mjop_source_sections.py`
  — **nieuw**: de price observation source layer. Leest de bron-PDF's
  opnieuw (via `pdftotext -table`, xpdf 4.06) en maakt van elke rij in
  "Overzicht NN - Jarenplan (Gedetailleerd)" met een bedrag > 0 binnen het
  venster precies één price observation, met Stj/Cy letterlijk (lege Cy =
  null), jaarbedragen, `total_scope` (ONE_/MULTIPLE_EXECUTIONS binnen het
  venster), prijspeil/BTW/indexatiezin letterlijk uit het document (geen
  prijspeil afgeleid als de bron er geen geeft) en pagina/regel-provenance.
  Jaarplan- en Bevindingen-regels worden als extra bronweergave aan dezelfde
  observation gekoppeld, nooit als extra observation; wat niet eenduidig te
  koppelen is, staat in `unlinked_section_rows` (UNKNOWN). DOC-003 (XLS van
  DOC-002) levert als duplicate source geen observations op. Afhankelijkheid
  alleen voor vastgestelde relaties (`data/price_observations/document_relations.json`);
  `NO_DEPENDENCY_FOUND` betekent niet onafhankelijk. Koppeling aan de
  bestaande `data/verified/`-acties is heuristisch (methode + score per
  observation bewaard). Schrijft naar
  `data/price_observations/price_observations_batch1.json`
  (schema: `schemas/price_observation.schema.json`). Geen matching, geen
  vergelijkbaarheid, geen kengetallen.
  Elementvelden per observation (`element`): een elementomschrijving die in
  de PDF over meerdere regels doorloopt wordt samengevoegd in
  `element_description_original`; de eerste bronregel blijft bewaard in
  `element_description_first_line` en de regelnummers van de samengevoegde
  vervolgregels in `element_description_continuation_lines`. Een laatste
  token op een vervolgregel dat exact een bekende eenheid is (bijv. `m2`)
  wordt niet samengevoegd maar met regel en reden vastgelegd in
  `element_description_excluded_tokens`. `element_context_source` zegt waar
  de elementregel vandaan komt: `same_page`, of `previous_page` als het
  element zonder groep-/subtotaal-/totaalgrens doorloopt vanaf de vorige
  pagina. Is dat niet eenduidig, dan blijft het element leeg en staat de
  laatste elementregel van de vorige pagina alleen als kandidaat in
  `element_candidate_previous_page` (niet toegekend).
- `scripts/normalize_price_observations.py` — afgeleide normalisatie-/
  validatielaag op de price observations (actie, eenheid, element,
  prijsvalidatie, review-redenen). Schrijft naar
  `data/price_observations/price_observations_batch1_normalized.json`
  (schema: `schemas/price_observation_normalized.schema.json`); de source
  observations worden niet aangepast.
  Materiaalblok per observation (`material`):
  `material_original` / `material_normalized` komen ongewijzigd uit het
  gekoppelde verified-element (`verified_material_field` = `present`,
  `absent` of `no_element_link`). `material_from_text` is een aparte
  afleiding uit `element_description_original`, alleen voor documenten
  waarvan de extractie geen materiaalveld had en die daarvoor zijn
  goedgekeurd (nu alleen DOC-001): precies één los woord dat letterlijk in
  `vocabularies/material.json` staat, geen ander of wisselend materiaal in
  de actietekst, en niet aangehouden voor menselijke interpretatie
  (`MATERIAL_FROM_TEXT_HOLD`). `material_source` = `verified_element` of
  `element_text`; `material_status` = `MATERIAL_FROM_VERIFIED`,
  `MATERIAL_FROM_TEXT` of `MATERIAL_UNKNOWN`; `material_not_derived_reason`
  zegt waarom er geen materiaal is (bijv.
  `no_vocabulary_token_in_element_text`, `held_for_human_interpretation`,
  `material_field_absent_document_not_in_scope`). Verified materiaal blijft
  leidend; in batch 1 hebben alleen de 10 goedgekeurde DOC-001-afleidingen
  `MATERIAL_FROM_TEXT`. Gevallen die interpretatie vragen worden niet
  automatisch afgeleid, en originele materiaaldata wordt nooit
  overschreven.
- `scripts/build_comparability.py` — **nieuw**: vergelijkbaarheidsregels
  versie 1 (`docs/comparability_rules_v1.md`) op de genormaliseerde price
  observations: eligibility per observation (O1–O11), source clusters uit
  de documentrelaties (D1–D7) en beoordeling per observation-paar uit
  verschillende clusters (P1–P11). Signaalwoorden uitsluitend uit
  `vocabularies/comparability_signal_words.json`. Leidt waar toegestaan
  `derived_unit_price_per_execution` af naast de ongewijzigde bronprijs.
  Schrijft naar `data/comparability/comparability_batch1.json`. Geen
  kengetallen, scores, indexatie of matching-aanbevelingen.
  Per observation onderscheidt de output een technisch afgeleide prijs
  (`derived_unit_price_per_execution`, ook bewaard bij NOT_ELIGIBLE/UNKNOWN
  voor auditeerbaarheid) van `independent_input`: of die prijs als
  onafhankelijke input voor tariefgroepen/latere aggregatie mag dienen
  (eligible, afgeleide prijs aanwezig en niet `POSSIBLY_DEPENDENT`).
  `independent_input_exclusion_reasons` geeft de redenen als dat niet zo is
  (`NO_DERIVED_PRICE`, `ELIGIBILITY_NOT_ELIGIBLE`, `ELIGIBILITY_UNKNOWN`,
  `POSSIBLY_DEPENDENT`, `EXECUTED_DURING_INSPECTION_PRICE_MEANING_UNCLEAR`).
  `dependency_status` wordt ongewijzigd overgenomen.
  F7: een observation met de letterlijke bronmarkering `(uitgevoerd JJJJ)` in
  de actietekst (in batch 1: 8 rijen van DOC-005) blijft bestaan met
  ongewijzigde bron, prijs, eligibility, dependency en paarbeoordeling, maar
  is voorlopig geen onafhankelijke input
  (`EXECUTED_DURING_INSPECTION_PRICE_MEANING_UNCLEAR`), omdat de
  prijsbetekenis van die rijen niet uit de bron blijkt.
  F8: het materiaal voor O9/P4/P9 komt in deze volgorde uit 1) het
  verified-element (leidend), 2) anders `material.material_from_text` uit de
  normalisatielaag, alleen bij `material_status = MATERIAL_FROM_TEXT` en
  `material_source = element_text`, 3) anders onbekend. Spreken 1 en 2
  elkaar tegen, dan blijft het materiaal onbekend
  (`conflict_verified_vs_element_text`). De gebruikte bron staat per
  observation in `material.source`. De regels P4/P9 zelf zijn ongewijzigd.
- Human-reviewlaag v1 (`docs/human_review_v1.md`) — **nieuw**: een mens
  beoordeelt observation-paren voordat ze als vergelijkbare kengetal-input
  mogen dienen. Een human decision record
  (`schemas/human_decision_record.schema.json`) legt per paar vast:
  `system_class` en `system_reasons` (wat comparability v1 zei) en, apart
  daarvan, de menselijke `decision` (COMPARABLE / COMPARABLE_WITH_CAVEATS /
  NOT_COMPARABLE / UNKNOWN) met verplichte `decision_reason`,
  `decision_caveats`, `reviewer` (altijd `human`), `reviewed_at`,
  `rule_version`, `input_hashes`, `evidence` (document/pagina/regel),
  `notes`, `supersedes` en `status`. De menselijke beslissing vervangt de
  systeemklasse nooit. Geen scores of confidence. Opslag:
  `data/review_decisions/human_decision_records.json` (source of truth,
  nu nog leeg). Append-only: bestaande beslissingen worden nooit
  overschreven; een herziening is een nieuw record met nieuw `decision_id`
  en `supersedes` naar de vorige, die van `ACTIVE` naar `SUPERSEDED` gaat;
  per `pair_id` hoogstens één `ACTIVE` record (gecontroleerd door
  `store_invariant_errors` / `append_only_errors`). Een gewijzigde
  `input_hashes` of `rule_version` markeert een record ter controle maar
  verwijdert het niet.
  `scripts/export_human_review_queue.py` bouwt reproduceerbaar (byte-identiek)
  `reports/human_review_queue_v1.xlsx`: de CW-paren waarvan beide
  observations onafhankelijke input zijn en geen onopgelost DOC-001-materiaal
  hebben (batch 1: 22 paren), met bronverwijzingen en lege kolommen voor de
  menselijke beslissing. De Excel is een reviewinstrument, niet de source of
  truth; het script maakt nooit zelf een beslissing aan.
- Kengetallen v1 — **nieuw**: de actuele kengetallenlaag. Regels:
  `docs/kengetallen_rules_v1.md` (definitief v1). Generator:
  `scripts/build_kengetallen.py` (deterministisch; leest alleen de
  genormaliseerde observations, de comparability-output en de human decision
  records). Schema: `schemas/kengetal.schema.json`. Huidige output:
  `data/kengetallen/kengetallen_batch1.json`. Tests: `tests/test_kengetallen.py`.
  Begrippen:
  - *observation* — één jarenplanrij met prijs per uitvoering (source layer);
  - *comparable group* — observations met dezelfde element_code, action,
    unit en hetzelfde bekende materiaal, allemaal `independent_input`, waarvan
    elke combinatie tussen verschillende source clusters een ACTIVE menselijke
    COMPARABLE/COMPARABLE_WITH_CAVEATS-beslissing heeft, zonder
    NOT_COMPARABLE en zonder aangenomen transitiviteit;
  - *source cluster* — de onafhankelijke bewijs-eenheid (documenten die geen
    onafhankelijke bronnen van elkaar zijn);
  - *cluster contribution* — één waarde per cluster: mediaan van de
    postwaarden, na post consolidation (voor/achter onder dezelfde
    elementregel wordt één post; alle observations blijven bewaard);
  - *kengetal* — mediaan van de cluster contributions bij minimaal 3 source
    clusters, altijd met minimum, maximum, range, prijspeilen,
    caveats en volledige herleiding naar observations, posten, clusters en
    `decision_id`'s;
  - `INSUFFICIENT_DATA` — geen centrale waarde (bijv. minder dan 3 clusters,
    onvolledige menselijke review, NOT_COMPARABLE in de groep, materiaal
    onbekend/verschillend); de reden en de spreiding blijven zichtbaar.

  Batch 1: C1 betonplafond (4645 buitenschilderwerk, m²) en C2 hemelwaterafvoer
  pvc (5211 vervangen, m1) zijn AVAILABLE (€33,48/m² resp. €51,79/m1, beide
  met gemengde prijspeilen; C2 ook met een ontbrekend prijspeil); de overige
  vier huidige groepen (stucwerk, impregneren, hek, tapijt) zijn
  `INSUFFICIENT_DATA` (2 source clusters). Een kengetal is historisch, niet
  geïndexeerd, geen marktprijs en geen normprijs. Er wordt geen confidence,
  score of weging gebruikt. Er ontstaat nooit een kengetal alleen omdat
  observations dezelfde code/actie/eenheid hebben. De generator overschrijft
  een bestaande output met andere inhoud niet stilzwijgend (`--supersede`
  bewaart de oude versie in `data/kengetallen/history/`; `--check` meldt of de
  output nog bij de invoer hoort).
- `tests/` — 91 tests die de belangrijkste regels afdwingen: null-bij-onzeker,
  requires_human_review bij conflicten, deterministische/reproduceerbare
  kostenberekening, dat `data/raw/` niet stilzwijgend verandert
  (`reports/raw_manifest.json` met sha256 per bronbestand), de review-
  ondergrens, id-canonicalisatie, dat normalisatie nooit door het model
  gebeurt, dat een ontbrekend brondocument nooit tot een modelaanroep leidt,
  de schilderwerk-afleidingsregel en de review-vlag-bubbling in
  `normalize_batch.py`, dat apply_review.py nooit een waarde verzint en een
  correctie altijd op het juiste veld toepast, dat de element_code-backfill
  nooit een code raadt/forceert, en (nieuw) dat een `total_cost_as_stated`
  van 0 nooit tot een vals "gratis" kental leidt. Deze tests gebruiken
  overal een gestubde `model_fn` — er wordt in de testsuite nergens een
  echte Anthropic-call gemaakt.

## Volgende stap

Batch 1 is geëxtraheerd, genormaliseerd, en de review-ronde is afgerond: van
de 670 maintenance_actions waren er 220 (was eerlijk gezegd 648 vóór de
vocabulaire-uitbreiding/schilderwerk-afleidingsregel - dat lagere aantal
klopte niet, zie git-historie) `requires_human_review: true`; deze zijn via
`reports/review_batch1.xlsx` allemaal met "accept" bevestigd (geen edits/
rejects nodig bevonden). De 91 gevlagde observations zijn nog niet
doorlopen.

**Kentallen — LEGACY / EARLIER EXPERIMENTAL CALCULATION** (niet de huidige
kengetallen v1-pipeline; die staat onder `data/kengetallen/`, zie hierboven):
`scripts/compute_kentallen.py` levert
nu 59 kentallen-groepen op uit 358 bruikbare prijspunten, gegroepeerd per
onze eigen `element_code`. Belangrijke kanttekening: **alle 358 punten zijn
`calculated` (afgeleid uit total/hoeveelheid) - nog geen enkele komt uit een
letterlijke documentprijs (`unit_cost.value`)**, simpelweg omdat deze 9
documenten zelf zelden een expliciete eenheidsprijs vermelden, alleen een
totaalbedrag per post. De kentallen zijn dus bruikbaar, maar minder
betrouwbaar dan een kental uit een letterlijke prijs zou zijn (zie
`schemas/maintenance_action.schema.json`). Ook zijn de prijzen NIET
geïndexeerd naar één prijspeiljaar (zie `cost_years` per groep in de
output) - vergelijk dus geen prijzen uit 2022 direct met 2026 zonder eerst
te indexeren.

Ook nog open: het accuracy-cijfer uit `evaluate_dataset.py` is nog geen
echte, onafhankelijke meting (zie hierboven) - dat kan later alsnog met een
blinde steekproef als daar behoefte aan is, maar staat niet in de weg van de
kentallen-berekening.

Menselijke verificatie (herhaalbaar zodra er nieuwe posten zijn):
```bash
python3 scripts/export_review_sheet.py            # -> reports/review_batch1.xlsx
# ... vul BESLISSING (accept/edit/reject) + evt. GECORRIGEERDE_WAARDE/NOTITIES in ...
python3 scripts/apply_review.py --reviewer "jij@voorbeeld.nl"   # -> data/verified/*.json
python3 scripts/compute_kentallen.py               # LEGACY -> data/kentallen/ + reports/kentallen_batch1.xlsx
python3 scripts/evaluate_dataset.py                # accuracy-cijfer (zie caveat hierboven)
```

## Gebruik

```bash
pip install -r requirements.txt

python3 scripts/inventory_documents.py      # data/raw/ -> reports/document_inventory.*
python3 scripts/extract_batch.py            # placeholders, + echte extractie als ANTHROPIC_API_KEY gezet is
python3 scripts/normalize_batch.py          # extracted -> normalized (deterministisch)
python3 scripts/export_review_sheet.py      # normalized -> reports/review_batch1.xlsx (mens vult in)
python3 scripts/apply_review.py --reviewer "jij@voorbeeld.nl"  # ingevuld Excel -> data/verified/
python3 scripts/compute_kentallen.py        # LEGACY / experimenteel: verified -> data/kentallen/
python3 scripts/evaluate_dataset.py         # normalized vs. verified -> reports/evaluation_report.json
python3 scripts/build_price_observations.py --dry-run   # raw PDF + verified -> controles, niets geschreven
python3 scripts/build_price_observations.py             # -> data/price_observations/price_observations_batch1.json
                                                        # (vereist pdftotext van xpdf 4.06 in PATH, of --pdftotext / $PDFTOTEXT)
python3 scripts/normalize_price_observations.py         # -> ..._normalized.json
python3 scripts/build_comparability.py                  # -> data/comparability/comparability_batch1.json
python3 scripts/export_human_review_queue.py            # -> reports/human_review_queue_v1.xlsx
python3 scripts/build_kengetallen.py                    # -> data/kengetallen/kengetallen_batch1.json (kengetallen v1)

python3 -m pytest tests/ -v
```

## Projectstructuur

```
data/
  raw/                 originele batch-1-documenten (nooit aanpassen)
  extracted/            letterlijk uit het document, incl. element_code
  normalized/           gecontroleerde vocabulaire toegepast
  verified/              door een mens gecontroleerd (review-ronde 1 verwerkt)
  kentallen/             LEGACY / EARLIER EXPERIMENTAL CALCULATION (niet de v1-pipeline)
  kengetallen/           kengetallen v1 (actuele output)
  price_observations/    source layer: 1 observation per jarenplan-rij + vastgestelde documentrelaties
  evaluation/            evaluatieset (nog leeg, nooit gebruiken om op te optimaliseren)
  rejected_or_uncertain/ onbetrouwbaar/conflicterend (nog leeg)
schemas/                datamodel (JSON Schema)
vocabularies/            gecontroleerde termenlijsten, incl. element_code.json (eigen coderingssysteem)
scripts/                 pipeline-scripts
reports/                 inventaris, batch-selectie, raw-manifest, review-/kentallen-Excel
tests/                   pytest-tests voor de validatieregels
```
