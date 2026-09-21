# MJOP Learning Pipeline — projectregels

Deze regels gelden voor elke sessie in dit project. Lees dit bestand als eerste.

## Doel

Bouw een gecontroleerde dataset-/kennispipeline die historische MJOP-documenten
(Meerjarenonderhoudsplannen voor Nederlandse VvE's) omzet in betrouwbare,
herleidbare, gestructureerde data — als context voor een AI-MJOP-platform.

Dit is NIET "geef het model honderden MJOP's en laat het daarvan leren". Oude
MJOP's kunnen fouten, verouderde prijzen, verkeerde aannames of incomplete
informatie bevatten. Het doel is een pipeline waarmee informatie betrouwbaar
wordt geëxtraheerd, genormaliseerd, gecontroleerd, geëvalueerd en pas dan
gebruikt.

## Kernprincipe: de LLM is niet de database

De database bevat de gestructureerde waarheid die uit bronnen is gehaald en
eventueel door een mens is geverifieerd.

AI mag: extraheren, classificeren, normaliseren, patronen herkennen,
aanbevelingen doen, uitleg genereren.

AI mag NOOIT zelfstandig: ontbrekende gegevens verzinnen, hoeveelheden/
onderhoudsjaren/kosten/conditiewaarden verzinnen, aannames als feiten
opslaan, of tegenstrijdige informatie automatisch oplossen zonder dit te
markeren.

- Ontbrekende informatie → `null` of `unknown` (nooit gokken)
- Tegenstrijdige informatie → `requires_human_review: true` + alle gevonden
  waarden bewaren in `possible_values`

## Datalagen

```
data/raw/                 originele documenten — NOOIT automatisch aanpassen
data/extracted/           letterlijk uit het document gehaald, met provenance
data/normalized/          gecontroleerde vocabulaire, original_value bewaard
data/verified/            door een mens gecontroleerd
data/evaluation/          alleen om pipeline-kwaliteit te meten, NOOIT om
                           prompts/regels op te optimaliseren
data/rejected_or_uncertain/  onbetrouwbaar, conflicterend of onduidelijk
```

## Provenance is verplicht

Elk belangrijk gegeven moet herleidbaar zijn naar: document_id, pagina, en
(indien van toepassing) tabel of tekstfragment. Geen duidelijke bron →
`source_confidence: low` + `requires_human_review: true`.

## Berekeningen

Nooit door het taalmodel laten "uitrekenen". Altijd deterministische code:
`direct_cost = quantity × unit_cost`, indexatie expliciet opgeslagen
(`indexation_rate`, `indexation_factor`, `calculated_cost`), decimal
arithmetic, geen floats voor geld.

## Normalisatie

Gecontroleerde vocabularies voor minimaal: element_type, material,
defect_type, severity, condition_score, maintenance_action, priority,
status, unit. Bewaar altijd zowel `original_value` als `normalized_value`.
Onzekere mapping → `normalized_value: null` + `requires_human_review: true`.
Niet gokken.

## Human verification

Elke AI-output moet door een mens te controleren zijn: ACCEPT / EDIT /
REJECT. Bij EDIT: bewaar oorspronkelijke AI-waarde, nieuwe waarde, dat een
mens het aangepast heeft, timestamp en gebruiker.

## Golden dataset vs. evaluation dataset

Golden dataset (door mens gecontroleerd) meet extractie-/normalisatie-
nauwkeurigheid. Evaluation dataset test dezelfde dingen maar wordt NOOIT
gebruikt om prompts of regels op te optimaliseren. Geen accuracy-claims
zonder duidelijke, reproduceerbare meetmethode.

## Batchstrategie

Batch 1 (max. 10) → Batch 2 (~20) → Batch 3 (~50) → Batch 4 (~100) → rest.
Elke batch bestaat uit zoveel mogelijk gevarieerde documenten (bouwjaar,
VvE-grootte, adviesbureau, layout, met/zonder foto's, met/zonder NEN 2767,
met/zonder tabellen). Nooit een volgende batch starten zonder dat de vorige
is beoordeeld. Nooit een massa-import doen zonder expliciete toestemming.

## Altijd / nooit

ALTIJD: provenance en confidence bewaren, onzekerheid markeren, originele
documenten intact laten, AI-output versioneren, berekeningen deterministisch,
tenant/source-scheiding behouden (geen data van VvE A lekt in context voor
VvE B).

NOOIT: ontbrekende data verzinnen, aannames als feiten opslaan, conflicten
automatisch oplossen, oude kosten als actuele marktprijs behandelen, een oud
MJOP als actuele inspectie behandelen, automatisch NEN 2767-certificering
claimen, AI-output als menselijke inspectie presenteren, broninformatie
verwijderen, originele bestanden overschrijven.

## Architectuurkeuzes met grote gevolgen

Kom je tijdens het werk een keuze tegen met grote gevolgen voor
datakwaliteit, databaseontwerp, AI-betrouwbaarheid, provenance,
schaalbaarheid of beveiliging? Meld dit expliciet voordat je het
implementeert, en werk niet verder tot de gebruiker heeft gereageerd.

## Fine-tuning

Nog niet aan de orde. Eerst begrijpen welke informatie aanwezig/betrouwbaar
is via: structured database + document retrieval + vector search/RAG +
verified examples + sterke prompts + human verification.

## Status van dit project

Zie `reports/mjop_inventaris.csv` en `reports/batch1_selectie_voorstel.csv`
voor de documentinventaris en de goedgekeurde Batch-1-selectie (10
documenten, gekozen op basis van variatie in adviesbureau, jaar, layout en
NEN2767-gebruik).
