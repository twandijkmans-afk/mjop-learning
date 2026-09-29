# Nieuwe MJOP's toevoegen

Deze pagina legt uit hoe je nieuwe (oude) MJOP's en offertes aan het systeem toevoegt. Je hoeft
daarvoor niet te programmeren en niets op je eigen computer te installeren: alles draait in de
cloud (GitHub).

## In het kort

1. **Bestanden uploaden** naar de map `mjop-learning/data/incoming/`.
2. **Workflow laten draaien** ("Process incoming MJOPs" in GitHub Actions).
3. **Batchrapport bekijken** in `mjop-learning/reports/incoming/<batch_id>.json`.
4. **Uitzonderingen reviewen** (documenten met REVIEW_REQUIRED, UNKNOWN_TEMPLATE, ...).
5. **Goedgekeurde batch later promoveren**: dat is een aparte stap. Tot die tijd verandert er
   niets aan de bestaande kennis (kengetallen, prijsobservaties, enzovoort).

## 1. Bestanden uploaden

- Ga in GitHub naar de branch waarop je werkt en open `mjop-learning/data/incoming/`.
- Kies **Add file → Upload files** en sleep je bestanden erin.
- Toegestaan: **PDF**, **XLS** en **XLSX**. Submappen mogen (bijvoorbeeld één map per gebouw).
- De bestandsnaam maakt niet uit. Het systeem herkent een document aan de inhoud (een
  vingerafdruk, "sha256"). Twee keer hetzelfde bestand uploaden, ook onder een andere naam, wordt
  herkend als dubbel.
- Laat de bestanden in `data/incoming/` staan totdat de batch gepromoveerd is.

## 2. Workflow laten draaien

- Na het uploaden start de workflow **vanzelf** (bij elke wijziging in `data/incoming/`).
- Je kunt hem ook met de hand starten: GitHub → **Actions** → **Process incoming MJOPs** →
  **Run workflow**. (Die knop verschijnt pas als de workflow op de hoofdbranch staat; tot dan
  start je hem door te uploaden.)
- De workflow installeert zelf de vaste PDF-lezer (xpdf 4.06), controleert die, verwerkt de
  bestanden en zet het resultaat terug in de repository. Er wordt **geen AI** gebruikt.

## 3. Batchrapport bekijken

Open `mjop-learning/reports/incoming/<batch_id>.json` (of de samenvatting onderaan de
workflow-run in GitHub Actions). Daarin staat onder meer:

| veld | betekenis |
|---|---|
| `total_files` | aantal bestanden in `data/incoming/` |
| `new_documents` | documenten die in deze batch een nieuw DOC-nummer kregen |
| `duplicates` | exacte kopieën (worden overgeslagen) |
| `supported_templates` | documenten waarvan het rapportformaat wordt herkend |
| `extracted_successfully` | documenten die automatisch zijn uitgelezen |
| `review_required` | documenten waar een mens naar moet kijken |
| `unknown_templates` | rapportformaat nog niet ondersteund |
| `unsupported_formats` | geen PDF/XLS/XLSX (of beschadigd) |
| `validation_failures` | uitlezen gelukt maar de controles faalden |
| `new_price_observation_candidates` | posten met een bedrag die later prijsinformatie kunnen worden |
| `relation_candidates` | mogelijke relaties met bestaande documenten (zelfde gebouw, nieuwe versie, ...) |

Onderaan staat per document de status en wat er nog moet gebeuren (`next_steps`).

## 4. Statussen

| status | wat betekent het | wat moet je doen |
|---|---|---|
| `DUPLICATE_SKIP` | exact hetzelfde bestand bestaat al | niets |
| `READY_FOR_EXTRACTION` | ondersteund, maar nog niet uitgelezen (PDF-lezer ontbrak) | workflow opnieuw draaien |
| `EXTRACTED` | uitgelezen en alle blokkerende controles in orde | klaar voor een promotievoorstel |
| `REVIEW_REQUIRED` | uitgelezen of herkend, maar er is iets dat een mens moet beoordelen | zie `open_review_items` |
| `UNKNOWN_TEMPLATE` | rapportformaat past bij geen enkele ondersteunde familie/variant (zie hieronder) | nieuw profiel = aparte beslissing |
| `UNSUPPORTED_FORMAT` | geen PDF/XLS/XLSX, of inhoud past niet bij de extensie | ander bestand aanleveren |
| `FAILED_VALIDATION` | uitlezen of controle mislukt | zie `validation/<DOC-ID>.json` |

`NEW` is de beginstatus van elk bestand; in `status_history` zie je de hele route.

Veelvoorkomende redenen voor `REVIEW_REQUIRED`:

- `RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION`: het document lijkt bij een bekend gebouw te
  horen (zelfde postcode of adres). Een mens bevestigt of het een nieuwe versie, een deelplan, een
  dubbel met andere bytes of een andere inspectie is. Het systeem neemt dat nooit zelf aan.
- `spreadsheet_structure`: een spreadsheetrij past in geen enkele bekende rijvorm (actie, element,
  groep, subtotaal, Totaal object, kop- of voettekst). Zo'n rij wordt nooit geraden.
- `totaal_object_reconciliation`: de som van de rijen wijkt meer af van het eigen 'Totaal object'
  van het document dan afronding kan verklaren (mogelijk een meegelezen subtotaal of een gemiste rij).
- `UNSUPPORTED_EXTRACTION`: een spreadsheet die wel als familie herkend is, maar waarvoor geen
  productie-parser bestaat. Voor de jarenplan-export (`pro_vve_overzicht15_spreadsheet`) is die er nu wel.
- `unlinked_records`, `amounts`, `template_recheck_xpdf`: zie het validatiebestand.

## 5. Promoveren (aparte, expliciete stap)

Na het batchrapport beslis je welke documenten canoniek worden. Alleen `APPROVED_FOR_PROMOTION` wordt
opgenomen in de kennislaag.

| beslissing | betekenis |
|---|---|
| `APPROVED_FOR_PROMOTION` | door jou goedgekeurd; wordt canoniek |
| `REVIEW_REQUIRED` | wacht op je goedkeuring (`AWAITING_HUMAN_APPROVAL`) of heeft open reviewpunten |
| `SKIPPED_DUPLICATE` | exact dubbel bestand; wordt nooit opgenomen |
| `BLOCKED` | kan niet: onbekend sjabloon, niet-ondersteund spreadsheetformaat, validatiefout, runner niet geverifieerd, ... |

**Stap A: proefdraaien (dry-run).**

- Start de workflow **"Promote incoming MJOP batch"** met je batch-id en actie `dry-run`.
- De workflow simuleert de hele promotie op een tijdelijke kopie en schrijft het reviewrapport
  `reports/incoming/<batch_id>.promotion_review.json`. Canonieke data verandert niet.
- In het rapport staan:
  - wat direct gepromoveerd kan worden;
  - wat review nodig heeft;
  - mogelijke duplicaten en relaties;
  - hoeveel nieuwe prijsobservaties erbij komen;
  - de impact op de vergelijkbaarheid;
  - de kengetallen vóór en na.

**Stap B: goedkeuren en promoveren.**

- Start dezelfde workflow met actie `approve-and-promote` en je naam als `reviewer`.
- Alle documenten met status EXTRACTED worden goedgekeurd.
- Een document met REVIEW_REQUIRED neem je alleen mee door het DOC-ID in te vullen bij
  `include_review`. Daarmee accepteer je de open punten van dat document. Een relatiekandidaat
  wordt daarmee **niet** bevestigd: die blijft een voorstel.

**Terugdraaien:** actie `rollback`. Dat kan alleen voor de laatste promotie. De oude toestand komt
exact terug; de history blijft bewaard.

Zolang de workflow nog niet op de hoofdbranch staat, verschijnt de knop "Run workflow" niet. Maak dan
in de batchmap een bestand `promotion_request.json` aan, bijvoorbeeld:

```json
{"action": "approve-and-promote", "reviewer": "twandijkmans", "include_review": ["DOC-012"]}
```

De workflow start vanzelf. Gebruik `{"action": "dry-run"}` om eerst proef te draaien.

---

## Technische achtergrond

### Route

```
data/incoming/  ->  formaat (op inhoud)  ->  sha256  ->  duplicate-controle  ->  DOC-ID
  ->  data/incoming_registry.json  ->  familieherkenning  ->  xpdf 4.06-extractie (indien ondersteund)
  ->  validatie  ->  data/incoming_batches/<batch_id>/  +  reports/incoming/<batch_id>.json
```

Script: `scripts/process_incoming_batch.py`

```
python scripts/process_incoming_batch.py                # dry-run: toont wat er zou gebeuren, schrijft niets
python scripts/process_incoming_batch.py --process      # schrijft de staging-batch (transactioneel)
python scripts/process_incoming_batch.py --check        # controleert register en bestaande batches
  --batch-id ID       eigen batch-id (standaard IB-<inhoudshash van alle invoer>)
  --pdftotext PAD     xpdf pdftotext 4.06
  --require-xpdf      stoppen als xpdf ontbreekt
  --runner-setup JSON uitkomst van scripts/xpdf_runner_setup.py
```

### Identiteit, register en duplicates

- Identiteit = sha256 van de bytes. Bestandsnaam en map zijn alleen metadata (`input_path`,
  `first_observed_path`).
- Staat de sha256 al in het canonieke register (`reports/document_registry.json`), dan krijgt het
  bestand `DUPLICATE_SKIP` en geen nieuw ID. Hetzelfde geldt voor een tweede kopie binnen dezelfde
  batch.
- Nieuwe documenten krijgen het eerstvolgende vrije DOC-ID: max(canoniek ∪ incoming) + 1, in
  gesorteerde padvolgorde. Het incoming-register is append-only; bestaande ID's verschuiven nooit
  en worden nooit hergebruikt. Het canonieke register wordt alleen gelezen.
- Een document dat al in het incoming-register staat, houdt zijn ID (ook na hernoemen).
- Alleen PDF/XLS/XLSX krijgen een DOC-ID; niet-ondersteunde bestanden krijgen de sleutel
  `INPUT-<sha12>`.

### Familieherkenning (`scripts/template_detection.py`)

Herkenning gaat op structurele kenmerken in de tekstlaag, nooit op de bestandsnaam. Elke variant
noemt welke kenmerken **verplicht aanwezig** en welke **verplicht afwezig** zijn. De eerste exacte
match wint; elke andere combinatie is `UNKNOWN_TEMPLATE`. Het documentrecord (`family.explanation`)
zegt per variant waarom een document er wel of niet bij hoort.

**Ondersteunde PDF-varianten** van familie `pro_vve_overzicht15` (vvem-rapportsoftware):

| variant | verplicht aanwezig | verplicht afwezig | voorbeeld |
|---|---|---|---|
| `standard` | objectblad, elementenoverzicht, "Overzicht NN - Jarenplan (Gedetailleerd)", kolomkop "Hvh Ehd Stj Cy", "Totaal object" | - | batch 1, DOC-012, DOC-014 |
| `multi_object_projects` | objectblad, elementenoverzicht, "Overzicht projecten", "Overzicht NN - jarenplan", kolomkop, "Totaal object" | titel "(Gedetailleerd)" | DOC-013 (meer objecten, per object een objectregel en subtotaal) |
| `jarenplan_without_objectblad` | "Overzicht NN - Jarenplan (Gedetailleerd)", kolomkop, "Totaal object" | objectblad, elementenoverzicht | DOC-011 (jarenplan ingebed in een rapport van een ander bureau) |

Alle varianten gebruiken dezelfde jarenplanparser (geen gedupliceerde parsercode). De verschillen zijn
alleen profielopties:

- `jarenplan_without_objectblad`: de elementen komen uit de elementregels van het jarenplan zelf (code,
  omschrijving en locatie, letterlijk; hoeveelheid en conditie blijven leeg). Objectvelden blijven
  leeg. De BTW komt uit de letterlijke toelichtingsregel "Alle prijzen zijn inclusief BTW ..." van het
  jarenplan (regel `jarenplan_toelichting_vat_fallback`). Staat er geen prijspeil in de bron, dan blijft
  het leeg.
- Tijdens de extractie worden de vereiste secties per variant opnieuw gecontroleerd op de xpdf-tekst.

**Ondersteunde spreadsheetfamilie:** `pro_vve_overzicht15_spreadsheet`, variant `jarenplan_sheet`
(spreadsheet-export van het jarenplan, zoals DOC-003 en DOC-015). Zie hieronder.

### Extractie

Dezelfde deterministische extractie als batch 1 (`deterministic_extraction.extract_file`,
profiel `pro_vve_overzicht15` zonder documentspecifieke regels). De valutaregel werkt alleen met
bewijs uit het document zelf. Zonder xpdf pdftotext 4.06 blijft een PDF op
`READY_FOR_EXTRACTION`: er is geen andere parser en geen AI als fallback.

### Spreadsheets (`scripts/spreadsheet_extraction.py`)

Spreadsheets worden **deterministisch** uitgelezen: `.xls` met xlrd en `.xlsx` met openpyxl, via de
bestaande tekstlaag. Er is geen conversie (geen LibreOffice), geen AI en geen externe dienst.

- De kolommen komen uit de kopregel (`Code/Element/Handeling` ... `Hvh`, `Ehd`, `Stj`, `Cy`, jaren,
  `Totaal`), nooit uit vaste posities.
- Elke rij wordt ingedeeld als groep, element, actie, subtotaal, "Totaal object", herhaalde kopregel of
  voettekst (datum of paginanummer). Subtotalen, "Totaal object", kop- en voettekst worden nooit acties.
  Een rij die nergens in past, wordt `spreadsheet_structure` (REVIEW).
- Bedragen zijn de exacte celwaarden, tot op de cent. De som van de acties wordt gecontroleerd tegen
  het eigen "Totaal object".
- Cy = 0 is de spreadsheetweergave van een lege cyclus: de PDF van hetzelfde plan (DOC-002 ↔ DOC-003)
  toont daar niets. Cy = 0 wordt daarom als leeg gelezen.
- Provenance per waarde: werkblad + celadres (A1) + blok-ID (bijv. `S01-R0025-C003`). Een price
  observation krijgt het ID `PO-DOC-015-S01-R0025` en verwijst naar werkblad, rij en celadressen.
  Er is geen nieuw datamodel; de schemas zijn alleen additief uitgebreid.
- **Export van een bekend MJOP?** Voor elke spreadsheet worden de rijen (elementcode, actietekst,
  hoeveelheid, eenheid, startjaar, totaal afgerond op de euro) vergeleken met alle PDF's (canoniek en in
  de batch). Het rapport toont dat als `spreadsheet_content_overlap`. Komt een PDF voor ≥ 90% overeen,
  dan volgt een relatiekandidaat `POSSIBLE_DUPLICATE_OTHER_BYTES` met dat bewijs. Dat is nooit een
  automatische duplicate: een mens bevestigt het.

### Validatie (per document, `validation/<DOC-ID>.json`)

schema, source_hash, no_ai, template_recheck_xpdf, provenance, provenance_block_links, elements,
maintenance_actions, unlinked_records, quantities, units, amounts (bedragen, rijcontrole,
valutabewijs; bij spreadsheets exacte celwaarden), vat, price_level, condition_legend, review_flags,
price_observations, totaal_object_reconciliation (som van de rijtotalen tegen het eigen 'Totaal object';
afrondingsgrens 0,5 per rijtotaal + 0,5), en bij spreadsheets spreadsheet_structure en
provenance op werkblad + celadres.

- `FAIL` = `FAILED_VALIDATION`.
- `REVIEW` = `REVIEW_REQUIRED` (blokkeert promotie).
- `WARN` = zichtbaar; wordt in de normale human review afgehandeld.

### Staging-batch

```
data/incoming_batches/<batch_id>/
  manifest.json            invoer, runner, toolversies, sha256 van elk bestand (geen tijdstempels)
  documents/<DOC-ID>.json  intake-record per bestand (status, redenen, familie, open punten)
  extracted/<DOC-ID>.json  deterministische extractie
  validation/<DOC-ID>.json controles
  promotion_proposal.json  alleen een voorstel; requires_separate_promotion_step = true
  history/<sha12>/         vorige versie als dezelfde batch-id opnieuw met andere uitkomst draait
reports/incoming/<batch_id>.json
```

Schrijven gebeurt transactioneel: eerst alles in het geheugen opbouwen en tegen de schemas
(`schemas/incoming_*.schema.json`) valideren, dan via tijdelijke bestanden + `os.replace`, het
register als laatste. Bij een fout wordt alles teruggezet. Alleen `data/incoming_registry.json`,
`data/incoming_batches/` en `reports/incoming/` zijn schrijfbaar; canonieke paden worden
geweigerd. Dezelfde invoer in dezelfde omgeving geeft byte-identieke uitvoer, en een herhaalde run
schrijft niets.

### Cloud-runner (GitHub Actions)

Workflow: `.github/workflows/process-incoming-mjops.yml`. Die draait bij uploads in
`data/incoming/` en via "Run workflow", en doet het volgende:

1. Installeert de vastgepinde Python-afhankelijkheden (`requirements-pipeline.txt`, zonder
   AI-SDK's).
2. Installeert xpdf via `scripts/xpdf_runner_setup.py`: vastgepinde URL's en sha256 in
   `config/xpdf_pin.json`, en een exacte versiecontrole
   (`pdftotext version 4.06 [www.xpdfreader.com]`).
3. Doet een reproductiecontrole: de negen batch-1-documenten worden opnieuw geëxtraheerd en moeten
   exact de gevalideerde `canonical_content_sha256` uit `batch1_v1` opleveren.
4. Draait de tests, `--check`, `--process` en opnieuw `--check`.
5. Uploadt de artifacts en commit alleen de staging-uitvoer terug.

Daarna draait een end-to-end zelftest: een gewijzigde kopie van DOC-010 gaat met echte xpdf door de
incoming-pipeline, in een tijdelijke map.

`VERIFIED_RUNNER_SETUP` = gepinde sha256 klopt, versie klopt en alle reproducties zijn identiek.

**Text-layer-platformbeleid (besluit twandijkmans, 2026-09-29).**

`text_layer_sha256` is de hash van de aanvullende pdfplumber-tekstlaag. Die hash telt als
platform/toolchain-provenance. Voor DOC-007 en DOC-009 valt hij op Linux anders uit dan in de
Windows-referentie van batch1_v1, bij dezelfde bibliotheekversies.

- Het besluit is vastgelegd in `config/xpdf_pin.json` onder `accepted_text_layer_platform_variance`.
  Daarin staan per document de Windows-referentiehash en de geaccepteerde Linux-hash.
- `xpdf_runner_setup.classify_reproduction` accepteert een afwijking alleen als drie dingen tegelijk
  gelden:
  1. het document staat in die lijst;
  2. de waargenomen hash is exact de geaccepteerde Linux-hash;
  3. na terugzetten van de referentiehash is de `canonical_content_sha256` van het **hele** record
     identiek.
- De harde checks blijven dus ongewijzigd: elementen, maintenance actions, condities, bedragen,
  hoeveelheden, eenheden, jaren, provenance-links en block-references.
- Elk ander verschil is een harde failure (`REPRODUCTION_MISMATCH`). Dat geldt ook voor een
  text-layer-afwijking bij een ander document of met een andere hash. Er is geen algemene
  hash-ignore-regel.
- De runner krijgt daarmee `VERIFIED_RUNNER_SETUP` met de metadata
  `text_layer_platform_variance: ["DOC-007", "DOC-009"]`.

Anders `UNVERIFIED_RUNNER_SETUP` of `FAILED_RUNNER_SETUP`. In dat geval blijft promotie
geblokkeerd (`global_blockers` in het voorstel), maar de rest van de pipeline werkt wel.

### Promotie (`scripts/promote_incoming_batch.py`)

```
python scripts/promote_incoming_batch.py --check
python scripts/promote_incoming_batch.py --dry-run  --batch-id ID [--documents DOC-...]   # alleen reviewrapport
python scripts/promote_incoming_batch.py --approve  --batch-id ID --reviewer NAAM [--include-review DOC-...] \
                                         [--exclude DOC-... --exclude-reason "waarom"]
python scripts/promote_incoming_batch.py --promote  --batch-id ID
python scripts/promote_incoming_batch.py --rollback --batch-id ID
```

**Selectie en uitsluiting:**

- `--dry-run` zonder `approval.json` simuleert alle promoveerbare documenten; met `--documents` alleen
  die documenten. Dat mogen alleen documenten met status EXTRACTED zijn die verder promoveerbaar zijn
  (REVIEW_REQUIRED-documenten nooit via deze route).
- `--dry-run` met een `approval.json` simuleert exact die goedkeuring (`--documents` is dan niet toegestaan).
- `--approve --exclude DOC-...` sluit documenten expliciet uit. Ze staan met de reden in `approval.json`
  (`excluded_document_ids`, `exclusion_reason`) en krijgen de beslissing `REVIEW_REQUIRED` met als
  eerste reden `EXCLUDED_BY_REVIEWER`. Een document kan niet tegelijk goedgekeurd en uitgesloten zijn.

**Preflight** (alles verplicht):

- het manifest is geldig en de hashes van de batchbestanden kloppen;
- de runner is geverifieerd;
- elk document heeft een expliciete status;
- de canonieke keten is schoon (`promotion_ledger.chain_errors`, batch-1 `--verify`);
- register en `data/raw` zijn in lijn;
- de decision store voldoet aan zijn invarianten;
- de kengetallen zijn actueel;
- `approval.json` is gebonden aan de manifest-sha256 en noemt alleen promoveerbare documenten.

**Downstream per goedgekeurd document** (bestaande regels, niets nieuws):

- De bron gaat naar `data/raw/incoming/<DOC>/<bestand>`, met append in register, `raw_manifest` en
  inventaris.
- `data/extracted`, `normalized` en `verified` komen uit de staging. Verified is het genormaliseerde
  record, zonder human verification op veldniveau: de documentgoedkeuring staat in de promotiestatus.
- Price observations: de price observations uit de staging (gemaakt op de runner met
  `build_price_observations.build_document`) worden toegevoegd. De relatie-ID's worden hernummerd.
- Daarna worden de genormaliseerde PO, comparability en kengetallen opnieuw gebouwd.
- Relatiekandidaten gaan alleen naar `data/price_observations/relation_proposals.json`.
  `document_relations.json` wijzigt nooit automatisch. Elk gepromoveerd document is daardoor zijn
  eigen source cluster totdat een mens een relatie vastlegt. De review toont paren tussen
  documenten met een open relatiekandidaat apart.

**Harde invarianten** (bij een fout wordt alles automatisch teruggezet):

- bestaande price observations blijven byte-gelijk;
- bestaande genormaliseerde observations blijven gelijk, op `source_ref.source_file_sha256` na;
- bestaande paren (identiteit = observation-set) blijven inhoudelijk gelijk;
- bestaande observation-beoordelingen blijven gelijk, op de afgeleide velden `pair_ids`,
  `comparison_class`, `comparison_class_reason` en `tariff_group_id` na;
- de human decision store blijft ongewijzigd;
- de kengetallen blijven inhoudelijk gelijk. Nieuwe data telt pas mee na comparability-review met
  ACTIVE human decisions.

**History en rollback:**

- De snapshot van alle gevolgde bestanden staat in `data/history/incoming_promotions/<promotion_id>/`
  (`pre/` plus `pre_manifest.json`).
- De status staat in `data/incoming_promotions/<promotion_id>.json`, met pre- en post-manifest,
  beslissingen en goedkeuring.
- Rollback kan alleen voor de laatste promotie. De tracked hashes komen exact terug op het
  pre-manifest, en `rolled_back_state.json` blijft in de history.

**Tests na een echte promotie:** de batch-1-snapshottests tellen gepromoveerde documenten en
observations mee via `promotion_ledger` (bijvoorbeeld 404 + toegevoegde observations).

### Relatievoorstellen

Relaties tussen documenten (zelfde gebouw, nieuwe versie, deelplan, dubbel met andere bytes) zijn altijd
alleen **voorstellen** (`CANDIDATE_REQUIRES_HUMAN_CONFIRMATION`, `source_cluster: NOT_ASSUMED`). Het
bewijs is:

- postcode of adres gelijk;
- prijspeil en inspectiedatum gelijk;
- of inhoudelijke overlap van spreadsheetrijen.

`document_relations.json` wijzigt nooit automatisch. Een document met een open relatiekandidaat blijft
`REVIEW_REQUIRED` totdat een mens het beoordeelt.

**Reviewpakket** (`scripts/prepare_relation_review.py`, alleen lezen):

```
python scripts/prepare_relation_review.py --document DOC-014 --batch-id IB-ad209360ab07 \
    --against DOC-005 DOC-006 --out reports/review/relation_review_DOC-014.json
```

Het pakket vergelijkt het incoming document met de genoemde canonieke documenten op:

- bron (sha256, grootte, pagina's) en objectmetadata;
- elementen en condities;
- price observations: exacte en gedeeltelijke rij-overlap en unieke rijen;
- totalen;
- tekstlaagverschillen.

Het geeft de beslisopties met hun gevolgen: `DUPLICATE_OTHER_BYTES`, `SAME_MJOP_VERSION`,
`SAME_BUILDING_DIFFERENT_INSPECTION` en `INDEPENDENT_SOURCE`. Het beslist zelf niets: status
`OPEN_REQUIRES_HUMAN_DECISION`, `decision: null`. De uitvoer is deterministisch.

### xpdf-fixtures voor ontwikkeling en tests

De workflow **Capture xpdf fixtures** (`.github/workflows/capture-xpdf-fixtures.yml`) legt de echte
xpdf-4.06-uitvoer van de PDF's in `data/incoming` vast als `tests/fixtures/xpdf_pages/<sha256>.json`.
Dat gebeurt op de geverifieerde runner, via exact de productieroute. Tests spelen die pagina's af via
`tests/fixtures/fake_pdftotext.py` (`FAKE_PDFTOTEXT_PAGES_DIR`). Zo draaien parser-ontwikkeling en
regressietests op precies dezelfde tekst als productie.
