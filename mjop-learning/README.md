# mjop-learning

Gecontroleerde dataset-/kennispipeline die historische MJOP-documenten
(Meerjarenonderhoudsplannen voor Nederlandse VvE's) omzet in betrouwbare,
herleidbare, gestructureerde data als context voor een AI-MJOP-platform.

Lees eerst `CLAUDE.md` — dat zijn de vaste regels voor dit project (provenance
verplicht, nooit gegevens verzinnen, deterministische berekeningen, etc.).

## Status

Batch 1 (10 documenten, zie `reports/batch1_selectie_voorstel.csv`) staat in
`data/raw/`. Voor deze batch zijn al opgeleverd en getest (23/23 tests slagen):

- `schemas/` — datamodel voor document, building, element, observation,
  maintenance_action, plus twee gedeelde bouwstenen
  (`_extracted_value.schema.json`, `_provenance.schema.json`) die het
  "null i.p.v. gokken" + provenance-patroon afdwingen.
- `vocabularies/` — eerste voorstel voor gecontroleerde termenlijsten
  (element_type, material, defect_type, condition_score, severity,
  maintenance_action, priority, status, unit), grotendeels gevalideerd tegen
  een woordfrequentie-scan van de 10 batch-1-documenten
  (`validated_against_batch1: true/false` per term).
- `scripts/inventory_documents.py` — **werkend**: bouwt
  `reports/document_inventory.{csv,json}` uit `data/raw/`.
- `scripts/normalize_batch.py` — **werkend**: deterministische
  vocabulaire-lookup + kostenberekening (quantity × unit_cost, Decimal).
  Onbekende termen worden nooit geraden (`normalized_value: null` +
  `requires_human_review: true`); een afwijkend vermeld totaalbedrag wordt
  gemarkeerd als `cost_conflict`, niet automatisch opgelost.
- `scripts/extract_batch.py` — **skeleton**: zet voor elk document in de
  batch een `data/extracted/<document_id>.json` neer met
  `status: "pending_extraction"`. Bevat nog GEEN LLM-call — dat is expliciet
  de volgende stap (zie TODO's in het bestand), en mag pas na overleg
  geïmplementeerd worden zodat de prompt/aanpak samen bepaald wordt.
- `scripts/evaluate_dataset.py` — **werkend, maar nog niets te evalueren**:
  zolang `data/verified/` leeg is (nog geen menselijke verificatie) geeft dit
  script terecht geen accuracy-cijfer — zie CLAUDE.md: geen claims zonder
  meting.
- `tests/` — 23 tests die de belangrijkste regels afdwingen: null-bij-onzeker,
  requires_human_review bij conflicten, deterministische/reproduceerbare
  kostenberekening, en dat `data/raw/` niet stilzwijgend verandert
  (`reports/raw_manifest.json` met sha256 per bronbestand).

## Volgende stap (nog NIET gedaan — wacht op overleg)

De daadwerkelijke extractiestap in `scripts/extract_batch.py` (LLM leest een
document en vult building/elements/observations/maintenance_actions volgens
de schemas in `schemas/`, met provenance en confidence per veld). Dit raakt
direct aan datakwaliteit en AI-betrouwbaarheid — dus eerst de aanpak
(prompt-ontwerp, welk model, hoe confidence bepaald wordt) samen vaststellen
voordat dit wordt geïmplementeerd, conform CLAUDE.md.

## Gebruik

```bash
pip install -r requirements.txt

python3 scripts/inventory_documents.py      # data/raw/ -> reports/document_inventory.*
python3 scripts/extract_batch.py            # placeholders in data/extracted/
python3 scripts/normalize_batch.py          # extracted -> normalized (deterministisch)
python3 scripts/evaluate_dataset.py         # normalized vs. verified -> reports/evaluation_report.json

python3 -m pytest tests/ -v
```

## Projectstructuur

```
data/
  raw/                 originele batch-1-documenten (nooit aanpassen)
  extracted/            letterlijk uit het document (nu: placeholders)
  normalized/           gecontroleerde vocabulaire toegepast
  verified/              door een mens gecontroleerd (nog leeg)
  evaluation/            evaluatieset (nog leeg, nooit gebruiken om op te optimaliseren)
  rejected_or_uncertain/ onbetrouwbaar/conflicterend (nog leeg)
schemas/                datamodel (JSON Schema)
vocabularies/            gecontroleerde termenlijsten
scripts/                 pipeline-scripts
reports/                 inventaris, batch-selectie, raw-manifest
tests/                   pytest-tests voor de validatieregels
```
