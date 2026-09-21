# mjop-learning

Gecontroleerde dataset-/kennispipeline die historische MJOP-documenten
(Meerjarenonderhoudsplannen voor Nederlandse VvE's) omzet in betrouwbare,
herleidbare, gestructureerde data als context voor een AI-MJOP-platform.

Lees eerst `CLAUDE.md` — dat zijn de vaste regels voor dit project (provenance
verplicht, nooit gegevens verzinnen, deterministische berekeningen, etc.).

## Status

Batch 1 (10 documenten, zie `reports/batch1_selectie_voorstel.csv`) staat in
`data/raw/` en is volledig geëxtraheerd (`data/extracted/`) en genormaliseerd
(`data/normalized/`) — zie "Volgende stap" hieronder voor de huidige
review-status. Onderstaande onderdelen zijn opgeleverd en getest
(71/71 tests slagen):

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
- `scripts/evaluate_dataset.py` — **werkend, maar nog niets te evalueren**:
  zolang `data/verified/` leeg is (nog geen menselijke verificatie) geeft dit
  script terecht geen accuracy-cijfer — zie CLAUDE.md: geen claims zonder
  meting.
- `tests/` — 71 tests die de belangrijkste regels afdwingen: null-bij-onzeker,
  requires_human_review bij conflicten, deterministische/reproduceerbare
  kostenberekening, dat `data/raw/` niet stilzwijgend verandert
  (`reports/raw_manifest.json` met sha256 per bronbestand), de review-
  ondergrens, id-canonicalisatie, dat normalisatie nooit door het model
  gebeurt, dat een ontbrekend brondocument nooit tot een modelaanroep leidt,
  de schilderwerk-afleidingsregel en de review-vlag-bubbling in
  `normalize_batch.py`, en (nieuw) dat apply_review.py nooit een waarde
  verzint en een correctie altijd op het juiste veld toepast. Deze tests
  gebruiken overal een gestubde `model_fn` — er wordt in de testsuite
  nergens een echte Anthropic-call gemaakt.

## Volgende stap

Batch 1 is geëxtraheerd en genormaliseerd. Van de 670 maintenance_actions
staan er 220 (was 648 vóór de vocabulaire-uitbreiding en de
schilderwerk-afleidingsregel — dat aantal was voorheen niet zichtbaar door
een bug in de review-bubbling) en van de observations 91 met
`requires_human_review: true`, meestal omdat de extractie zelf al een lage
confidence gaf (bijv. ontbrekende unit_cost) of omdat de actietekst een
unieke, niet-generaliseerbare beschrijving is (zie
`vocabularies/maintenance_action.json` voor wat al wel gemapt is).

Menselijke verificatie:
```bash
python3 scripts/export_review_sheet.py            # -> reports/review_batch1.xlsx
# ... vul BESLISSING (accept/edit/reject) + evt. GECORRIGEERDE_WAARDE/NOTITIES in ...
python3 scripts/apply_review.py --reviewer "jij@voorbeeld.nl"   # -> data/verified/*.json
python3 scripts/evaluate_dataset.py                # eerste accuracy-cijfer
```

## Gebruik

```bash
pip install -r requirements.txt

python3 scripts/inventory_documents.py      # data/raw/ -> reports/document_inventory.*
python3 scripts/extract_batch.py            # placeholders, + echte extractie als ANTHROPIC_API_KEY gezet is
python3 scripts/normalize_batch.py          # extracted -> normalized (deterministisch)
python3 scripts/export_review_sheet.py      # normalized -> reports/review_batch1.xlsx (mens vult in)
python3 scripts/apply_review.py --reviewer "jij@voorbeeld.nl"  # ingevuld Excel -> data/verified/
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
