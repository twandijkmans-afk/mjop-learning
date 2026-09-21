# mjop-learning

Gecontroleerde dataset-/kennispipeline die historische MJOP-documenten
(Meerjarenonderhoudsplannen voor Nederlandse VvE's) omzet in betrouwbare,
herleidbare, gestructureerde data als context voor een AI-MJOP-platform.

Lees eerst `CLAUDE.md` — dat zijn de vaste regels voor dit project (provenance
verplicht, nooit gegevens verzinnen, deterministische berekeningen, etc.).

## Status

Batch 1 (10 documenten, zie `reports/batch1_selectie_voorstel.csv`) staat in
`data/raw/`. Voor deze batch zijn al opgeleverd en getest (35/35 tests slagen):

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
- `scripts/evaluate_dataset.py` — **werkend, maar nog niets te evalueren**:
  zolang `data/verified/` leeg is (nog geen menselijke verificatie) geeft dit
  script terecht geen accuracy-cijfer — zie CLAUDE.md: geen claims zonder
  meting.
- `tests/` — 35 tests die de belangrijkste regels afdwingen: null-bij-onzeker,
  requires_human_review bij conflicten, deterministische/reproduceerbare
  kostenberekening, dat `data/raw/` niet stilzwijgend verandert
  (`reports/raw_manifest.json` met sha256 per bronbestand), en (nieuw, voor de
  extractiestap) de review-ondergrens, id-canonicalisatie, dat normalisatie
  nooit door het model gebeurt, en dat een ontbrekend brondocument nooit tot
  een modelaanroep leidt. Deze tests gebruiken overal een gestubde `model_fn`
  — er wordt in de testsuite nergens een echte Anthropic-call gemaakt.

## Volgende stap

Batch 1 daadwerkelijk extraheren: `ANTHROPIC_API_KEY` zetten en
`python3 scripts/extract_batch.py --batch batch_1` draaien, de 10
`data/extracted/*.json`-bestanden beoordelen (met name de posten die
`requires_human_review: true` kregen), en pas daarna normaliseren
(`normalize_batch.py`) en evalueren.

## Gebruik

```bash
pip install -r requirements.txt

python3 scripts/inventory_documents.py      # data/raw/ -> reports/document_inventory.*
python3 scripts/extract_batch.py            # placeholders, + echte extractie als ANTHROPIC_API_KEY gezet is
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
