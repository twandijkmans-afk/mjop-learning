# mjop-learning

Gecontroleerde dataset-/kennispipeline die historische MJOP-documenten
(Meerjarenonderhoudsplannen voor Nederlandse VvE's) omzet in betrouwbare,
herleidbare, gestructureerde data als context voor een AI-MJOP-platform.

Lees eerst `CLAUDE.md` — dat zijn de vaste regels voor dit project (provenance
verplicht, nooit gegevens verzinnen, deterministische berekeningen, etc.).

## Status

Batch 1 (10 documenten, zie `reports/batch1_selectie_voorstel.csv`) staat in
`data/raw/` en is volledig geëxtraheerd (`data/extracted/`) en genormaliseerd
(`data/normalized/`). 9 van de 10 documenten zijn door onszelf opgesteld (in
opdracht van Pro VvE Beheer / VvE Beheer B.V.); alleen DOC-004 (Innax, 2018)
is van een andere partij en telt niet mee voor de eigen-stijl-categorisering
hieronder. Zie "Volgende stap" hieronder voor de huidige review-status.
Onderstaande onderdelen zijn opgeleverd en getest (80/80 tests slagen):

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
- `tests/` — 80 tests die de belangrijkste regels afdwingen: null-bij-onzeker,
  requires_human_review bij conflicten, deterministische/reproduceerbare
  kostenberekening, dat `data/raw/` niet stilzwijgend verandert
  (`reports/raw_manifest.json` met sha256 per bronbestand), de review-
  ondergrens, id-canonicalisatie, dat normalisatie nooit door het model
  gebeurt, dat een ontbrekend brondocument nooit tot een modelaanroep leidt,
  de schilderwerk-afleidingsregel en de review-vlag-bubbling in
  `normalize_batch.py`, dat apply_review.py nooit een waarde verzint en een
  correctie altijd op het juiste veld toepast, en (nieuw) dat de
  element_code-backfill nooit een code raadt/forceert. Deze tests gebruiken
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

**Wat nu ontbreekt (de kern van het doel: kentallen)**: er bestaat nog geen
script dat `data/normalized/` (of `verified/`) omzet in daadwerkelijke
kentallen (bijv. "gemiddelde/mediane prijs per m² voor element_code 4711 -
Dakbedekking APP, over N documenten, met bandbreedte"). `element_code` (zie
hierboven) geeft nu de sleutel om dat te doen op de manier waarop wij onze
eigen MJOP's opbouwen, i.p.v. een generieke indeling. Dat is de volgende
bouwsteen.

Ook nog open: het accuracy-cijfer uit `evaluate_dataset.py` is nog geen
echte, onafhankelijke meting (zie hierboven) - dat kan later alsnog met een
blinde steekproef als daar behoefte aan is, maar staat niet in de weg voor
het bouwen van de kentallen-berekening.

Menselijke verificatie (herhaalbaar zodra er nieuwe posten zijn):
```bash
python3 scripts/export_review_sheet.py            # -> reports/review_batch1.xlsx
# ... vul BESLISSING (accept/edit/reject) + evt. GECORRIGEERDE_WAARDE/NOTITIES in ...
python3 scripts/apply_review.py --reviewer "jij@voorbeeld.nl"   # -> data/verified/*.json
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
