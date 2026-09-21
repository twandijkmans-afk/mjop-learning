Dit is de eerste werksessie voor het "mjop-learning" project. Lees eerst
CLAUDE.md in de projectroot — dat zijn de vaste regels waar je je aan houdt,
elke sessie, niet alleen deze.

## Context

Ik beheer meerjarenonderhoudsplannen (MJOP's) voor VvE's. Er is al een
documentinventaris en een goedgekeurde Batch-1-selectie gemaakt (bijgevoegd:
`mjop_inventaris.csv` / `mjop_inventaris.json` met alle 26 geïnventariseerde
bronbestanden, en `batch1_selectie_voorstel.csv` met de 10 gekozen
documenten + onderbouwing). Gebruik deze als startpunt — doe de
inventarisatie niet opnieuw.

## Stap 0: brondocumenten kopiëren

De 10 batch-1-documenten staan hier (netwerkschijf):

```
M:\Algemeen\Website\MJOP Website\Maldenhof\9261_vvem_mop_01-03-2023_Pro VVE Beheer B.V._851361.pdf
M:\Algemeen\Website\MJOP Website\Maldenhof\2026_Meerjarenonderhoudsplan_VvE 9261 Maldenhof 240-296.pdf
M:\Algemeen\Website\MJOP Website\Alkmaarstraat 1-83\MJOP 2026\9543_vvem_mop_14-01-2022_Pro VVEBeheer B.V._626720.pdf
M:\Algemeen\Website\MJOP Website\J.P. Heijestraat\MOP 2026\9690_vvem_mop_v_15-03-2018_Innax_hele_schil_376215.pdf
M:\Algemeen\Website\MJOP Website\J.P. Heijestraat\MOP 2026\2026_Meerjarenonderhoudsplan_VvE 9690.pdf
M:\Algemeen\Website\MJOP Website\Zomerdijkstraat 14\Meerjarenonderhoudsplan 2023_VvE Zomerdijkstraat 14.pdf
M:\Algemeen\Website\MJOP Website\Mauritstaete\MOP 2023\Actualisatie MOP 2023 met bijlage.pdf
M:\Algemeen\Website\MJOP Website\VVe st. jacobstraat\Mop 2025\Hoofd.pdf
M:\Algemeen\Website\MJOP Website\VVe st. jacobstraat\Mop 2025\Woningen.pdf
M:\Algemeen\Website\MJOP Website\J.P. Heijestraat\MOP 2026\2026_Overzicht 15 - Jarenplan (Gedetailleerd)_VvE 9690.xls
```

Kopieer ze 1-op-1 (nooit verplaatsen/aanpassen) naar `data/raw/<vve-naam>/`
in dit project, bijvoorbeeld `data/raw/maldenhof/`, `data/raw/alkmaarstraat/`,
`data/raw/jp-heijestraat/`, `data/raw/zomerdijkstraat/`,
`data/raw/mauritstaete/`, `data/raw/st-jacobstraat/`. Behoud de originele
bestandsnamen. Als je (Claude Code) geen toegang hebt tot deze netwerkschijf,
stop dan en vraag mij om de bestanden aan te leveren — verzin geen
plaatsvervangende inhoud.

## Wat ik in deze sessie wél wil, en wat niet

Doe ALLEEN het volgende, en stop daarna zodat ik kan meekijken voordat je
verder gaat naar echte extractie:

1. **Projectstructuur opzetten** zoals beschreven in CLAUDE.md:
   `data/{raw,extracted,normalized,verified,evaluation,rejected_or_uncertain}/`,
   `schemas/`, `prompts/`, `scripts/`, `reports/`, `tests/`, `README.md`.
   Zet `mjop_inventaris.csv/json` en `batch1_selectie_voorstel.csv` in
   `reports/`.

2. **Eerste datamodel voorstellen**: `schemas/document.schema.json`,
   `building.schema.json`, `element.schema.json`, `observation.schema.json`,
   `maintenance_action.schema.json`. Baseer de velden op sectie 6 van het
   masterplan (building: construction_year, number_of_units, building_type,
   address, inspection_date, mjop_period; element: element_type,
   element_name, location, material, quantity, unit, construction_year;
   observation: description, defect, condition_score, severity, source,
   source_page; maintenance_action: action, planned_year, quantity, unit,
   unit_cost, total_cost, cost_year, source_page). Elk belangrijk veld moet
   een verplichte provenance-referentie kunnen dragen (document_id, page,
   evt. table/text-fragment) en een `confidence`/`requires_human_review`-veld.

3. **Gecontroleerde vocabularies voorstellen** voor element_type, material,
   defect_type, severity, condition_score, maintenance_action, priority,
   status, unit — als JSON/YAML met ruimte voor `original_value` +
   `normalized_value` per gemapte term. Baseer een eerste versie op wat je
   in de 10 batch-1-documenten aantreft (zonder ze al volledig te
   verwerken — een snelle scan volstaat om categorieën te herkennen).

4. **Technische batchworkflow bouwen** als scripts: `inventory_documents`,
   `extract_batch`, `normalize_batch`, `evaluate_dataset`. Het is prima als
   `extract_batch`/`normalize_batch` nu nog stubs/skeletons zijn — laat
   duidelijk zien waar een LLM-call hoort, waar een deterministische
   berekening hoort, en waar een human-verification-stap hoort (ACCEPT /
   EDIT / REJECT, met opslag van originele AI-waarde + eventuele
   correctie + timestamp + gebruiker).

5. **Tests schrijven** voor de belangrijkste validatieregels: ontbrekende
   data wordt `null` (nooit verzonnen), conflicten krijgen
   `requires_human_review: true` met alle gevonden waarden bewaard,
   kostenberekeningen zijn deterministisch en reproduceerbaar (geen
   floating-point verrassingen), en `data/raw/` wordt door niets in de
   pipeline overschreven.

6. Kom je een architectuurkeuze tegen met grote gevolgen voor datakwaliteit,
   databaseontwerp, AI-betrouwbaarheid, provenance, schaalbaarheid of
   beveiliging? Meld dat expliciet en wacht op mijn reactie voordat je het
   implementeert.

**Verwerk in deze sessie GEEN documentinhoud** — geen echte extractie of
normalisatie van de 10 batch-1-bestanden. Dat is de volgende stap, pas na
mijn goedkeuring van het datamodel en de vocabularies.
