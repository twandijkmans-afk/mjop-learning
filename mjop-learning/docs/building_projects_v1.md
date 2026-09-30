# Building projects v1

Vervolg op [building_link_3dbag_evidence_v1.md](building_link_3dbag_evidence_v1.md) en Real Building Validation v1
(`scripts/fetch_real_building_validation.py`, `data/external/building_validation/`). Deze stap legt een menselijk
besluit vast over welke BAG-panden samen één VvE/complex vormen. Er is nog geen quantity- of crosswalk-koppeling.

## Twee verschillende concepten

| | **building_link** (legacy) | **building_project** (nieuw) |
|---|---|---|
| Betekent | één document <-> één BAG-pand | één logisch project (VvE/complex) met 1..n BAG-panden |
| Bewijs | BAGSNAP-snapshot (`scripts/bag_snapshots.py`) | candidate package van Real Building Validation (raw responses + manifest + hashes) |
| Store | `data/building_links/building_link_records.json` | `data/building_projects/building_project_records.json` |
| Script | `scripts/building_links.py` | `scripts/building_projects.py` |

Deze twee zijn **niet hetzelfde** en er is bewust **geen compatibiliteitslaag**. De legacy store en de crosswalk-store
worden door building_projects nooit geschreven of gelezen. Een project verwijst nooit naar "het" pand: er is geen
veld voor één pand, alleen `bag_pand_ids`.

## Stores (append-only)

- `data/building_projects/building_project_records.json` — schema `schemas/building_project_record.schema.json`.
  Eén ACTIVE record per `candidate_id`; geen pand mag in twee ACTIVE projecten zitten.
- `data/building_projects/unresolved_case_records.json` — schema `schemas/unresolved_case_record.schema.json`.
  Compacte records van kandidaten die niet zijn goedgekeurd: `selected_scope: null`, geen link, met de open punten
  en verwijzingen naar het bewijs zodat het onderzoek niet opnieuw hoeft.
- Invarianten uit `scripts/append_only_store.py` (getest in `tests/test_append_only_store.py`): records worden nooit
  verwijderd of overschreven; alleen `ACTIVE -> SUPERSEDED` (of `REVIEW_REQUIRED`); een wijziging is een **nieuw record met
  `supersedes`**. `BPRJ-00001` kan dus niet stil worden gewijzigd.

Een goedgekeurd record pint minimaal: `building_project_id`, `document_ids`, `candidate_id`, `selected_scope`,
`bag_pand_ids` (+ per pand de huisnummers/VBO's), `provenance` (evidence-map, pad + sha256 van candidate package en
manifest; het manifest pint elke raw response), `project_status`/`approval` (reviewer, tijdstip, reden, bron van het
besluit, bevestigde feiten), `supersedes` en `status`.

## Goedkeuren

`python scripts/building_projects.py approve --group ... --scope ... --reviewer ... --reason ... --expect pand_count=15 ...`

Het script weigert tenzij: een menselijke reviewer + reden is opgegeven; het candidate package ongewijzigd en
hash-consistent is (`manifest_errors`); de scope `STRONG_BUILDING_PROJECT_CANDIDATE` is; de door de mens bevestigde
feiten (`--expect`) exact overeenkomen met het package; en de panden niet al bij een ander actief project horen.
3D BAG blijft **evidence** (alleen verwijzing + hash per pand); niets wordt vertaald naar hoeveelheden.

`legal_vve` wordt alleen gekoppeld als een juridische identifier (KvK/RSIN) onafhankelijk in bestaande data staat;
anders `OPEN`. Klantcode/objectcodes in een MJOP zijn geen juridische identifiers.

## Onveranderlijk bewijs

Een evidence package (map) dat door een building_project-record wordt gerefereerd — ook door een SUPERSEDED record —
is onveranderlijk:

- `python scripts/building_projects.py guard --out DIR` faalt hard (exit 1) voor zo'n map;
- `fetch_real_building_validation.py` weigert er te schrijven (exit 5);
- de workflow `real-building-validation.yml` draait de guard **vóór** elke `rm -rf`, en `building_projects.py check`
  controleert bij elke run dat package, manifest en alle raw responses nog bij de vastgelegde hashes passen.

De workflow blijft nieuwe data ophalen, maar alleen naar een **nieuwe versiemap** (`real_validation_v<N>`):
via `workflow_dispatch` (input `out_dir`) of door die map in
`data/external/building_validation/fetch_target.txt` te zetten en te pushen. Zonder doelmap draaien alleen de tests
en de integriteitscontrole.

## Stand

- `BPRJ-00001` — Maldenhof 240-296 (DOC-005 + DOC-006), scope `EVEN_ONLY`, 15 BAG-panden, 29 adressen/VBO's,
  goedgekeurd door `twandijkmans`; `legal_vve` OPEN. Evidence: `real_validation_v1`.
- `UCASE-00001` — Meppelweg (DOC-012), niet goedgekeurd, geen scope gekozen, vijf open punten (801 ontbreekt in de BAG;
  pand `0518100000354752` bevat 803-883 oneven plus 885; MJOP noemt geen aantal eenheden; bouwjaar MJOP 1956 vs BAG
  1957; objectnaam 801-883 vs opdrachtgevernaam 801-803).
- Niet gedaan (bewust): legacy per-pand links, crosswalk, quantity-vertaling van 3D BAG, legal_vve.
