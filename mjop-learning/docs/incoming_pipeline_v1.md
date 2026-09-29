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
| `UNKNOWN_TEMPLATE` | rapportformaat wordt (nog) niet herkend | nieuw profiel = aparte beslissing |
| `UNSUPPORTED_FORMAT` | geen PDF/XLS/XLSX, of inhoud past niet bij de extensie | ander bestand aanleveren |
| `FAILED_VALIDATION` | uitlezen of controle mislukt | zie `validation/<DOC-ID>.json` |

`NEW` is de beginstatus van elk bestand; in `status_history` zie je de hele route.

Veelvoorkomende redenen voor `REVIEW_REQUIRED`:

- `RELATION_CANDIDATE_REQUIRES_HUMAN_CONFIRMATION`: het document lijkt bij een bekend gebouw te
  horen (zelfde postcode of adres). Een mens bevestigt of het een nieuwe versie, een deelplan, een
  dubbel met andere bytes of een andere inspectie is. Het systeem neemt dat nooit zelf aan.
- `UNSUPPORTED_EXTRACTION`: een spreadsheet (bijv. een losse export van het jarenplan). Daarvoor is
  nog geen vaste uitleesroute; er wordt bewust niet gegokt.
- `unlinked_records`, `amounts`, `template_recheck_xpdf`: zie het validatiebestand.

## 5. Promoveren (later, aparte stap)

In elke batchmap staat `promotion_proposal.json`. Dat is alleen een **voorstel**: welke documenten
in aanmerking komen (`CANDIDATE_FOR_PROMOTION`) en wat nog blokkeert. De promotie zelf gebeurt in
een aparte, expliciete stap, net als bij batch 1. Zolang die niet is uitgevoerd, veranderen de
bestaande kengetallen, prijsobservaties en andere canonieke gegevens niet.

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

Op structurele kenmerken in de tekstlaag, nooit op de bestandsnaam. `pro_vve_overzicht15`
(vvem-formaat, batch 1) vereist alle vijf: "Algemene Objectgegevens", "Elementenoverzicht",
"Overzicht NN - Jarenplan (Gedetailleerd)", de kolomkop "Hvh Ehd Stj Cy" en "Totaal object".
Tijdens de extractie wordt dat herhaald op de xpdf-tekst (secties OBJECT, ELEMENTEN, JARENPLAN).
Een deel van de kenmerken = `UNKNOWN_TEMPLATE` (`PARTIAL_FAMILY_MARKERS`). Een spreadsheet-export
van het jarenplan wordt herkend als `pro_vve_overzicht15_spreadsheet`, maar krijgt
`REVIEW_REQUIRED` / `UNSUPPORTED_EXTRACTION`.

### Extractie

Dezelfde deterministische extractie als batch 1 (`deterministic_extraction.extract_file`,
profiel `pro_vve_overzicht15` zonder documentspecifieke regels). De valutaregel werkt alleen met
bewijs uit het document zelf. Zonder xpdf pdftotext 4.06 blijft een PDF op
`READY_FOR_EXTRACTION`: er is geen andere parser en geen AI als fallback.

### Validatie (per document, `validation/<DOC-ID>.json`)

schema, source_hash, no_ai, template_recheck_xpdf, provenance, provenance_block_links, elements,
maintenance_actions, unlinked_records, quantities, units, amounts (bedragen, rijcontrole,
valutabewijs), vat, price_level, condition_legend, review_flags.

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

Stand op 2026-09-29 (runs 2 en 3):

- Het archief wordt gedownload van `dl.xpdfreader.com`; de sha256 is vastgepind.
- De versieregel klopt exact.
- 7 van de 9 batch-1-documenten zijn byte-identiek.
- Bij DOC-007 en DOC-009 zijn alle waarden, provenance en block_id's gelijk. Alleen
  `text_layer_sha256` verschilt: de hash van de aanvullende pdfplumber-tekstlaag, die op Windows
  anders uitvalt dan op Linux, bij dezelfde bibliotheekversies.

De runner meldt daarom `UNVERIFIED_RUNNER_SETUP` met de reden
`TEXT_LAYER_PLATFORM_DIFFERENCE:DOC-007,DOC-009`. Dit verschil wordt niet automatisch
goedgekeurd: accepteren is een menselijke beslissing.
Anders `UNVERIFIED_RUNNER_SETUP` of `FAILED_RUNNER_SETUP`. In dat geval blijft promotie
geblokkeerd (`global_blockers` in het voorstel), maar de rest van de pipeline werkt wel.
