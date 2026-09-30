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

De workflow blijft nieuwe data ophalen, maar alleen naar een **nieuwe versiemap** (`real_validation_v<N>`; v1-v3 zijn in gebruik, de volgende vrije is v4):
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

## Range discovery v2 (`fetch_real_building_validation_v1.3.0`, `real_validation_v2`)

Verbeterde bereik-resolutie, overgezet vanuit de legacy `bag_snapshots fetch-range` naar deze engine (de legacy
BAGSNAP-/building_link-keten zelf is bewust niet overgenomen):

- **Hele bereik, per huisnummer gestructureerd** (bestond al) — nu ook met **meerdere straten per groep** (`segments`,
  sleutels `Straat nummer`) en nummerlijsten (`numbers`, bv. Vechtstraat 13-15-17-19).
- **Huisnummertoevoegingen** (`include_toevoegingen`, aan voor alle echte groepen): 13-H, 14-1, 802A tellen als adres in
  scope (`match_kind: TOEVOEGING`) i.p.v. alleen als context. Een groep zonder opt-in houdt het oude gedrag.
- **Woonplaats verplicht**: met toevoegingen filtert de PDOK-vraag op `woonplaatsnaam` en telt een adres in een andere
  plaats nooit mee (`match_kind: OTHER_CITY`, vlag `EXACT_MATCH_IN_OTHER_CITY`). Zonder dit vond "Vechtstraat 17
  Amsterdam" 82 panden in heel Nederland.
- **Scope-hypotheses ALL/EVEN/ODD** automatisch voor elk bereik met beide pariteiten (`default_hypotheses`); bij meerdere
  straten ook de gemengde combinaties per straat (`MIXED:ALKMAARSTRAAT=ODD|GROETSTRAAT=ALL`). Er wordt nooit een pariteit
  gekozen; `parity_distinction` legt vast of even/oneven op pandniveau (per straat) iets onderscheidt
  (`PARITY_NOT_DISTINGUISHING_AT_PAND_LEVEL`).
- **Niet-actieve panden** (bv. `Pand gesloopt`, waarvan de oude polygoon nog onder een adrespunt ligt): vastgelegd in
  `non_active_bag_panden`, geen kandidaat naast een actief pand; ligt een adres alléén in zo'n pand, dan blokkeert
  `PAND_NOT_IN_USE` STRONG. 3D BAG-fouten (502 voor een onbekend pand) worden vastgelegd, niet ingevuld.
- **Extra STRONG-voorwaarden**: documentadres in scope, alle panden in gebruik, geografisch compact
  (`COMPACT_EXTENT_M` = 300 m). Aantal eenheden = adressen = VBO's blijft de sterke indicator, maar is niet genoeg.
- **Straatalias** alleen expliciet en per woonplaats vastgepind (`STREET_ALIASES`): Utrecht "St. Jacobsstraat" ->
  BAG "St.-Jacobsstraat" (openbare ruimte 0344300000000857; in Utrecht bestaat geen andere Jacobsstraat-variant).
  Geen algemene fuzzy matching.

### Supporting evidence (`data/building_projects/supporting_evidence_records.json`)

`building_projects.py reproduce` legt vast dat een nieuwer package een goedgekeurd project **exact** reproduceert
(panden, adressen incl. nummeraanduiding- en VBO-ID's, huisnummers per pand, VBO-totaal, scope). Bij elk verschil weigert
het met het verschil (geen stille supersede). Het record (`BPEV-…`, rol `SUPPORTING_EVIDENCE`) pint de sha256 van het
project-record en wijzigt het nooit; het gerefereerde package wordt daarmee ook onveranderlijk.

- `BPEV-00001` — `real_validation_v2` reproduceert `BPRJ-00001` (EVEN_ONLY, 15 panden, 29 adressen) exact.
  Geen nieuwe approval; BPRJ-00001 ongewijzigd.

### Rapporten

`python scripts/building_project_discovery_report.py [--check]` →
`reports/building_projects/range_discovery_v2.{json,md}` (per groep en hypothese: adressen, VBO's, panden, bouwjaren,
3D BAG-dekking, MJOP-eenheden, ontbrekend/extra, toevoegingen; klasse APPROVED_PROJECT / STRONG_CANDIDATE /
MODERATE_CANDIDATE / REVIEW_CASE) en `reports/quantity/maldenhof_roof_scope_review_v1.{json,md}`
(`SCOPE_OR_DEFINITION_MISMATCH_REVIEW`; niets gecorrigeerd).

## Evidence-gerichte classificatie (`fetch_real_building_validation_v1.4.0`, `real_validation_v3`)

- **Bouwjaar is ondersteunend bewijs**, geen absolute blocker en geen match-regel. Klassen per hypothese
  (`construction_year_class`): `CONSTRUCTION_YEAR_EXACT`, `CONSTRUCTION_YEAR_NEAR_DIFFERENCE` (alle panden hetzelfde
  BAG-bouwjaar, verschil <= `NEAR_YEAR_SPAN` = 3), `CONSTRUCTION_YEAR_CONFLICT` (groter of niet uniform),
  `CONSTRUCTION_YEAR_UNKNOWN`. Een NEAR-verschil telt nooit als gelijk (`construction_year_matches_all_panden` blijft
  false) en blokkeert STRONG alleen niet als de identiteit verder eenduidig is (`identity_unambiguous`: eenheden = adressen
  = VBO's, volledige dekking, documentadres in scope, compact, panden in gebruik, geen blokkerende vlaggen). Dan wordt het
  een caveat. CONFLICT blokkeert STRONG altijd.
- **Goedkeuren met caveat** vraagt een expliciete bevestiging: `--expect construction_year_class=...` (en
  `--expect construction_year=none`); zonder die bevestiging weigert `approve`.
- **Actieve VBO's**: met VBO-details (`fetch_all_vbo_detail`) tellen ingetrokken/niet-gerealiseerde VBO's niet mee als
  eenheid; `pand.aantal_verblijfsobjecten` (incl. ingetrokken) blijft zichtbaar. Per hypothese: gebruiksdoelen van de
  actieve VBO's (`vbo_detail`).
- **Context-panden zonder adres** (`context_panden_without_vbo`, Maldenhof): BAG-panden in gebruik zonder VBO rond de
  adrespunten, met 3D BAG. Alleen evidence; nooit kandidaat of scope.

Stand v3 (`reports/building_projects/range_discovery_v3.md`): Maldenhof reproduceert BPRJ-00001 opnieuw (`BPEV-00002`);
Vechtstraat (DOC-013) is STRONG met caveat `CONSTRUCTION_YEAR_NEAR_DIFFERENCE: 1921 vs 1923` en heeft een
bevestigingsverzoek (`vechtstraat_confirmation_v1.json`, GEEN approval); DOC-001 en DOC-015 MODERATE; DOC-009 en DOC-012
review. Gerichte rapporten: `alkmaarstraat_candidate_evidence_v1.json`, `groetstraat_vbo_review_v1.json`,
`st_jacobsstraat_unit_mismatch_v1.json` en `reports/quantity/maldenhof_roof_validation_v2.json` (eerste
quantity-validation pilot, LoD2.2-dakvlakken; niets gecorrigeerd).

