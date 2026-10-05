# Building link + 3D BAG evidence v1

Vervolg op [quantity_foundation_v1.md](quantity_foundation_v1.md). Doel: historische elementhoeveelheden
voor het eerst verbinden met echte gebouwdata (BAG/3D BAG). Alle bronnen blijven naast elkaar als evidence
bestaan, en een mens kiest of bevestigt. Dit document beschrijft wat geïmplementeerd is en wat nog
geblokkeerd is.

```
historisch MJOP-document
  → BAG/3D BAG-snapshot (ruwe antwoorden, content-addressed)       scripts/bag_snapshots.py
  → kandidatenrapport (beslist niets)                               scripts/building_links.py candidates
  → menselijk bevestigde building link (append-only)                scripts/building_links.py record
  → 3D BAG-evidence (regels)  +  historische evidence (via geverifieerde mapping)
                                                                    scripts/build_building_quantity_evidence.py
  → vergelijking 3D BAG vs historisch (alleen verschil, geen score) reports/quantity/3dbag_vs_historical_v1.*
  → menselijke resolutie (bestaand: quantity_resolution_records)    scripts/quantity_evidence.py
  → app-bundel voor de eigen VvE (alleen geverifieerde crosswalk)   scripts/export_app_quantity_bundle.py
```

## Stand bij oplevering

| Onderdeel | Stand |
|---|---|
| Snapshots | **0**. `api.pdok.nl` en `api.3dbag.nl` zijn vanuit de ontwikkelomgeving geweigerd (egress-beleid). De opvraagroute volgt MJOP-App (`lookupBuilding`), maar is `NOT_VERIFIED_AGAINST_LIVE_API`. |
| Building links | **0** bevestigd. Het kandidatenrapport dekt 13 documenten: 11 `AWAITING_BAG_SNAPSHOT`, 2 `NO_ADDRESS` (DOC-007 heeft alleen een objectnaam en plaats; DOC-011 heeft geen objectgegevens). |
| Crosswalk / onderwerp-mappings | **0** geverifieerd. Alle mappings zijn voorstellen (`PROPOSED` / `REVIEW_REQUIRED`). |
| 3D BAG- en historische evidence | **0**, omdat er geen links zijn. |
| Vergelijkingen | **0**. |

Er is bewust niets bevestigd of geverifieerd zonder mens, en er zijn geen gebouwgegevens verzonnen. De tests
gebruiken zelfgemaakte, als zodanig gemarkeerde testantwoorden die niet in `data/` terechtkomen.

## 1. BAG/3D BAG-snapshots (`scripts/bag_snapshots.py`)

De opvraagketen is dezelfde als in MJOP-App:

1. PDOK Locatieserver `free` (`type:adres`);
2. alleen een adres waarvan straat, huisnummer en (indien opgegeven) postcode **exact** gelijk zijn;
3. BAG OGC-panden in een bbox rond dat punt, en alleen panden waarvan de polygoon het punt **bevat**;
4. 3D BAG `/collections/pand/items/NL.IMBAG.Pand.<id>`.

Wat een snapshot bewaart:
- elke request (URL, HTTP-status, sha256 van de respons) plus de ruwe respons zelf;
- de 3D BAG-attributen ongewijzigd, met `fetched_at` en `api_version` (indien aanwezig in `metadata.version`).

`snapshot_id` = `BAGSNAP-` + sha256 van de inhoud. Een aangepaste snapshot valt dus op, en schrijven
overschrijft nooit. Niet-exacte PDOK-treffers worden bewaard als context, maar er worden geen panden voor
opgevraagd (geen fuzzy matching).

## 2. Building links (`scripts/building_links.py`)

### Kandidatenrapport

`reports/quantity/building_link_candidates_v1.{json,md}` bevat per document:
- het adres zoals vermeld, met provenance;
- postcode, plaats en objectnaam;
- de deterministisch ontlede adresdelen (enkel / bereik / lijst);
- `normalized_address` en de opvraagplanning. De postcode wordt alleen gebruikt bij één enkel adres.
- source cluster, documentrelaties en documenten over hetzelfde object;
- bevestigde links binnen hetzelfde cluster;
- kandidaat-panden uit snapshots;
- review-redenen en status.

De review-redenen zijn:
- `NO_STATED_ADDRESS`
- `ADDRESS_FROM_OBJECT_NAME`
- `ADDRESS_NOT_PARSED`
- `MULTIPLE_STREETS`
- `ADDRESS_RANGE`
- `POSTCODE_MISSING`
- `CITY_MISSING`
- `OBJECT_NAME_ADDRESS_DIFFERS`
- `ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT` (bijv. DOC-002 "Jan Pieter Heijestraat" vs DOC-004 "J.P Heijestraat")
- `SUBPLAN_SCOPE`
- `NO_BAG_SNAPSHOT`
- `SNAPSHOT_WITHOUT_EXACT_ADDRESS_MATCH`
- `MULTIPLE_CANDIDATE_PANDEN`

Het rapport bevestigt niets.

### Link-records

`data/building_links/building_link_records.json` (schema: `schemas/building_link_record.schema.json`) bevat
één record per `(document_id, bag_pand_id)`, met de velden:
- `link_id`, `document_id`, `bag_pand_id`;
- `link_status`: `CONFIRMED` of `REJECTED`;
- `address_as_stated`, `normalized_address`;
- `evidence`: snapshot, adrestreffers die in het pand liggen, adresprovenance, BAG-eigenschappen;
- `decision_reason`, `reviewer` (`reviewer_type: human`), `reviewed_at`, `rule_version`, `input_hashes`;
- `supersedes` en `status` (`ACTIVE` / `SUPERSEDED` / `REVIEW_REQUIRED`).

`record` weigert in deze gevallen:
- zonder reviewer of reden;
- bij een snapshot van een ander document;
- bij een pand dat niet als kandidaat in de snapshot staat (geen vrij ingetypte ID's).

Meerdere panden per document zijn meerdere records. Er is geen één-pand-aanname. Invarianten en
append-only-controle staan in `scripts/append_only_store.py` (zelfde regels als de bestaande decision records).

## 3. 3D BAG-regels (`vocabularies/quantity_subjects_v1.json`, `scripts/bag3d_quantity_rules.py`)

| Regel | Onderwerp | Methode | Formule |
|---|---|---|---|
| `bag3d.roof_flat_area` | `ROOF_FLAT_AREA` (m2) | DIRECT_MEASURED | `b3_opp_dak_plat` |
| `bag3d.roof_sloped_area` | `ROOF_SLOPED_AREA` (m2) | DIRECT_MEASURED | `b3_opp_dak_schuin` |
| `bag3d.roof_total_area` | `ROOF_TOTAL_AREA` (m2) | GEOMETRY_DERIVED | `b3_opp_dak_plat + b3_opp_dak_schuin` |
| `bag3d.outer_wall_gross_area` | `OUTER_WALL_GROSS_AREA` (m2) | DIRECT_MEASURED | `b3_opp_buitenmuur` |
| `bag3d.building_height` | `BUILDING_HEIGHT` (m) | GEOMETRY_DERIVED | `b3_h_dak_max - b3_h_maaiveld` |

- **Veldnamen:** alle velden worden al door MJOP-App gelezen. Ze zijn niet opnieuw tegen de live API
  gecontroleerd (`USED_IN_MJOP_APP_NOT_VERIFIED_AGAINST_LIVE_API`).
- **Contextvelden:** `b3_opp_grond`, `b3_bouwlagen` en `b3_dak_type` worden als context bewaard, niet als hoeveelheid.
- **Rekenwerk:** waarden zijn exact (Decimal vanaf de JSON-tekst, geen afronding).
- **Ontbrekende velden:** een ontbrekend veld geeft `NOT_AVAILABLE`, nooit 0.

## 4. Crosswalk en onderwerp-mappings (`scripts/crosswalk.py`)

- `vocabularies/quantity_subjects_v1.json` → `historical_subject_mappings`: interne element_code + eenheid → onderwerp.
  - `HSM-ROOF_FLAT_AREA-4711-m2` (PROPOSED)
  - `HSM-ROOF_SLOPED_AREA-4712-m2` (PROPOSED; 4712 is een gemengde code)
- `vocabularies/app_element_crosswalk_v1.json` → MJOP-App-element ↔ interne code:
  - `XW-dak-plat-4711-m2` (PROPOSED)
  - `XW-dak-hellend-4712-m2` (REVIEW_REQUIRED)
  - `XW-gevel-metselwerk-2110-m2` (REVIEW_REQUIRED: bruto buitenmuur ≠ netto metselwerk; geen gedeeld onderwerp)
- **UNRESOLVED:**
  - HWA pvc (5211, m1, KG-5211) en aluminium daktrim (4711-m1, KG-4711): de app heeft geen element in m1;
  - `dakgoten` (appartementen als eenheid);
  - `schilderwerk-buiten` en `voegwerk`.

Een mapping is alleen **VERIFIED** met een ACTIVE `VERIFY`-besluit van een mens in
`data/crosswalk_decisions/crosswalk_decision_records.json`. Dat besluit is gebonden aan de sha256 van het
voorstel: wijzigt het voorstel, dan wordt de status `REVIEW_REQUIRED`. Er wordt niets op naam geraden.

## 5. Evidence en vergelijking (`scripts/build_building_quantity_evidence.py`)

- **`building_id`:** `BAG:` + gesorteerde, door een mens bevestigde pand-ID's. Wordt nooit uit een document-ID afgeleid.
- **3D BAG-evidence:** per bevestigd pand per regel, met:
  - `source_type = 3D_BAG`, status `PROPOSED`;
  - ruwe invoer, veldnamen, `fetched_at`, `api_version`, `rule_id`/`rule_version`, snapshot-ID en respons-sha256.
- **Historische evidence (`SOURCE_REPORTED`):** alleen voor documenten met ACTIVE links en alleen via een
  geverifieerde onderwerp-mapping. De quantity observation zelf blijft onveranderd; de evidence verwijst ernaar.
  Source cluster en afhankelijkheid van documenten over hetzelfde object blijven zichtbaar.
- **Vergelijking** (`reports/quantity/3dbag_vs_historical_v1.{json,md}`):
  - verschil = historisch − 3D BAG; percentage ten opzichte van 3D BAG;
  - banden ≤ 5 %, 5–15 % en > 15 %;
  - redenen: `MULTI_PAND_NOT_SUMMED`, `MULTIPLE_HISTORICAL_ROWS_NOT_SUMMED`, `NO_3DBAG_VALUE`, `UNIT_MISMATCH`,
    `HISTORICAL_OBSERVATION_REVIEW_REQUIRED`;
  - samenvatting met medianen van het absolute verschil;
  - geen kwaliteitsscore, niets opgeteld of gemiddeld.
- **Resolutie:** via de bestaande `quantity_resolution_records` (ACCEPT_EVIDENCE / USER_VALUE / UNKNOWN; een
  gemiddelde wordt geweigerd).

## 6. Naar MJOP-App: bundel per VvE (`scripts/export_app_quantity_bundle.py`)

**Architectuurkeuze (tenant-scheiding).** Historische hoeveelheden van een VvE komen niet in de publieke
app-code of in een gedeelde dataset. De beheerder exporteert een bundel voor zijn eigen gebouw en importeert
die zelf in zijn eigen plan in MJOP-App. Een gedeelde, server-side evidence-opslag met RLS per organisatie is
een latere stap.

- De bundel bevat alleen evidence voor onderwerpen met een door een mens geverifieerde app-crosswalk.
  Zonder zo'n crosswalk weigert het script.
- 3D BAG en historisch staan naast elkaar in de bundel; er wordt niets gekozen.

## 7. Deblokkeren (volgorde)

1. **Netwerk:** sta in de omgeving `api.pdok.nl` en `api.3dbag.nl` toe.
2. **Snapshots:** haal ze op volgens de opvraagplanning in het kandidatenrapport, bijvoorbeeld:
   `python scripts/bag_snapshots.py fetch --document DOC-005 --street Maldenhof --number 240 --postcode "1106 EZ" --city Amsterdam`
3. **Kandidaten:** `python scripts/building_links.py candidates`.
4. **Links:** een mens bevestigt per document en pand:
   `python scripts/building_links.py record --document DOC-005 --bag-pand-id <id> --snapshot <BAGSNAP-…> --reviewer <naam> --reason "…"`
5. **Mappings:** een mens verifieert de mapping(s):
   `python scripts/crosswalk.py record --mapping HSM-ROOF_FLAT_AREA-4711-m2 --decision VERIFY --reviewer <naam> --reason "…"`
   (en `XW-dak-plat-4711-m2` voor de app).
6. **Evidence en vergelijking:** `python scripts/build_building_quantity_evidence.py`.
7. **Bundel:** `python scripts/export_app_quantity_bundle.py --building BAG:<id> --out exports/<vve>.json`, en die
   importeren in MJOP-App.

Kandidaat voor de eerste echte demo:
- DOC-005/DOC-006 (Maldenhof 240–296, 1106 EZ): postcode aanwezig, één straat, 4711-m2-rij "Dakbedekking APP"
  425,80 m2. Het nummerbereik kan meerdere panden opleveren.
- DOC-012 (Meppelweg 819, 2544 AW): één adres. De objectnaam noemt 801–883.

## 8. Gebouwscope met meerdere panden (Multi-pand Quantity Scope v1)

Architectuurbesluit (gebruiker, 2026-10-05, optie a): één VvE-/gebouwscope mag uit meerdere BAG-panden bestaan.

- **Gebouwscope = bestaande `building_id`-conventie.**
  - `BAG:` + gesorteerde, ontdubbelde pand-ID's van de ACTIVE + CONFIRMED building links van een document.
  - Volgorde en dubbelingen veranderen de ID niet; één pand blijft `BAG:<id>`.
  - Er is geen tweede ID-mechanisme. (`building_project` bestaat alleen op de integratiebranch en is niet
    overgenomen.)
- **Per-pand-evidence blijft bestaan.** 3D BAG-evidence wordt per bevestigd pand aangemaakt (`building_id = BAG:<pand>`),
  zoals in §5.
- **Scope-aggregaat** (`vocabularies/quantity_subjects_v1.json` → `scope_aggregation_rules`, regel
  `scope.sum_over_confirmed_panden` v1.0.0):
  - Wanneer: alleen voor scopes met meer dan één bevestigd pand.
  - Welke onderwerpen: ROOF_FLAT_AREA, ROOF_SLOPED_AREA, ROOF_TOTAL_AREA en OUTER_WALL_GROSS_AREA. BUILDING_HEIGHT
    wordt niet opgeteld.
  - Wat er ontstaat: één afgeleide evidence per scope en onderwerp, met:
    - `method_class = GEOMETRY_DERIVED`, `source_type = 3D_BAG` en `quantity_kind = ELEMENT_QUANTITY`;
    - `building_id` = de scope;
    - `calculation.formula = SUM(child_evidence.value)` en `calculation.input_evidence_ids` = alle child evidence;
    - `raw_inputs` per pand en een exacte Decimal-som;
    - `source_ref` met `bag_pand_ids`, `child_evidence_ids`, `snapshot_ids`, `building_link_ids` en
      `missing_bag_pand_ids`.
  - Ontbreekt een pandwaarde (veld afwezig, 3D BAG-fout, geen snapshot)? Dan wordt het aggregaat **niet
    gepubliceerd** (`scope_aggregates_not_published`, `CHILD_EVIDENCE_MISSING_NOT_PUBLISHED`). Een ontbrekende waarde
    telt nooit als 0.
- **Historische complexhoeveelheden** (bv. DOC-005/DOC-006 "Dakbedekking APP / Platte dak" 425,80 m²):
  - blijven `SOURCE_REPORTED` met `building_id` = de scope;
  - worden niet over panden verdeeld en niet gedeeld door het aantal panden of woningen;
  - DOC-005 en DOC-006 blijven afhankelijk (`version_of_same_mjop`).
- **Vergelijking:** historisch (scope) tegenover scope-aggregaat (zelfde `subject_id`). Zonder gepubliceerd
  aggregaat geldt de reden `MULTI_PAND_AGGREGATE_NOT_PUBLISHED`. Er wordt niet gemiddeld, er is geen score en geen
  winnaar. Een resolutie kiest precies één evidence, of USER_VALUE of UNKNOWN.
- **App-bundel:**
  - `mjop_app_quantity_bundle_v1` (één pand) is ongewijzigd;
  - `mjop_app_quantity_bundle_v2` (meerdere panden) bevat `building_scope` met alle pand-ID's. Het 3D
    BAG-scope-aggregaat bevat `components` (de pandwaarden), en de historische evidence heeft `scope_level = COMPLEX`;
  - pandwaarden zijn geen losse, kiesbare bronnen.

### Nummerbereik opvragen (`bag_snapshots.py fetch-range`)

`building_links.lookup_plan` maakt van een bereik ("Maldenhof 240 - 296") één range-opvraging in plaats van alleen de
eindpunten. `fetch_range_snapshot` werkt zo:

1. Eén Locatieserver-query, `fq=type:adres`, woonplaats en straat exact, `huisnummer:[van TO tot]`, gepagineerd.
2. In code wordt elk adres opnieuw exact gecontroleerd: straat, woonplaats en huisnummer (geheel getal) binnen het
   bereik.
3. Er is geen pariteit-aanname en geen fuzzy match. Toevoegingen worden gemarkeerd (`has_suffix`). Niet-bestaande
   nummers vallen vanzelf weg.
4. De postcode is geen filter, maar wordt per adres vastgelegd (`postcode_matches_document`).
5. Panden worden per adrespunt bepaald (bbox plus punt-in-polygoon, zoals bij één adres) en ontdubbeld op pand-ID;
   3D BAG wordt één keer per pand opgehaald.
6. Een 3D BAG-fout voor één pand wordt vastgelegd (`threedbag.error`, geen attributen) zonder de snapshot af te breken.

Ook bij één adres wordt de woonplaats nu exact gecontroleerd als die is opgegeven.

Stand op 2026-10-05: canonieke snapshots `BAGSNAP-431559474da45dcf` (DOC-005) en `BAGSNAP-e23aa139a8589881`
(DOC-006).

- 56 bestaande adressen in 240–296 (267 bestaat niet), waarvan 29 met postcode 1106EZ (de documentpostcode, de even
  nummers).
- 40 kandidaat-panden, waarvan 15 met alleen documentpostcode-adressen.
- Alle 97 requests per snapshot HTTP 200.

Welke panden bij de VvE horen, is een **menselijk besluit** (`building_links.py record`). Er is niets bevestigd. Zie
`reports/quantity/maldenhof_multi_pand_scope_demo_v1.md` (read-only demo, scope = PREVIEW).

### Externe definitie 3D BAG-veld

`b3_opp_dak_plat`: "Totale oppervlakte van de platte delen van het dak" (m²). Bron: de officiële
3DBAG-documentatie (attributenschema), aangeleverd door de gebruiker op 2026-10-05. Die is vanuit de
ontwikkelomgeving niet opnieuw opgehaald. Vastgelegd in `vocabularies/quantity_subjects_v1.json` →
`bag3d_field_definitions_external`.

Dit is **geen** bewijs dat een historische regel zoals "Dakbedekking APP / Platte dak 425,80 m²" dezelfde scope heeft.


## 9. Maldenhof Quantity Activation v1 — verwante, niet gelijke onderwerpen

Menselijke besluiten (append-only, reviewer `user-approved`, `reviewer_type` human):

- **Building links** DOC-005 en DOC-006: 15 panden CONFIRMED (alleen adressen 1106 EZ, de 29 even nummers 240–296),
  25 panden REJECTED (1106 EH/EJ). Gebouwscope `BAG:<15 gesorteerde pand-ID's>`, gelijk voor beide documenten.
- **XW-dak-plat-4711-m2**: VERIFY als element/code-crosswalk. Dit verklaart níet dat een historische 4711-m2-hoeveelheid
  gelijk is aan 3D BAG `b3_opp_dak_plat`.
- **HSM-ROOF_FLAT_AREA-4711-m2**: bewust NIET geverifieerd.
- **HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-005-006**: document-specifieke mapping (exacte match op document,
  code 4711, m2, omschrijving 'Dakbedekking APP', locatie 'Platte dak'), geactiveerd op instructie van de gebruiker.

Nieuw onderwerp `ROOF_COVERING_REPORTED_AREA` ("Door bron/MJOP gerapporteerde oppervlakte dakbedekking", m2,
ELEMENT_QUANTITY, SOURCE_REPORTED): geen 3D BAG-regel, geen scope-aggregatie, nooit over panden verdeeld.

Relatie `SREL-ROOF_COVERING_REPORTED_AREA-ROOF_FLAT_AREA` (`subject_relations`): **RELATED_NOT_EQUIVALENT**.
Naast elkaar tonen: ja. Verschil tonen: ja, als bronverschil/andere definitie (`comparison_kind`
RELATED_SUBJECT_NOT_EQUIVALENT, niet in de verschilstatistiek). Middelen, één resolutie over beide, automatische
winnaar: nee. De subject_id's verschillen, dus `quantity_evidence.validate_resolution` weigert een resolutie die
evidence van beide onderwerpen afweegt.

App-bundel v3 (`export_app_quantity_bundle.py` met de onderwerpenvocabulaire): de evidence van het onderwerp van de
app-mapping is PRIMARY (kiesbaar); historische evidence van een RELATED_NOT_EQUIVALENT-onderwerp met de interne code
van de mapping komt mee als `role` RELATED_CONTEXT, `selectable` false. Zonder context-regels blijft de uitvoer v1/v2.

Rapport: `scripts/maldenhof_quantity_activation.py` → `reports/quantity/maldenhof_quantity_activation_v1.{json,md}`.
Quantity resolution: niet vastgelegd (UNRESOLVED; 3D BAG-evidence PROPOSED).

## 10. Echte Maldenhof-bundel v3

`reports/quantity/app_bundles/maldenhof_DOC-005_DOC-006_v3.json` is de eerste echte app-bundel: gegenereerd met
`scripts/export_app_quantity_bundle.py` voor de 15 bevestigde panden, deterministisch (byte-identiek bij een nieuwe
export) en gevalideerd met `scripts/validate_app_quantity_bundle.py --expect-panden 15 --check-export`.

v3-bundels hebben per evidence een `evidence_refs`-blok (regel, snapshots, building links, child evidence,
quantity observation, bronbestand-hash, mapping, dependency). v1/v2-bundels blijven ongewijzigd.

De validator controleert o.a.: versie en scope, geen dubbele panden, aggregaat = exacte som van de components,
historische context op complexniveau en niet kiesbaar, contextonderwerp ≠ kiesbaar onderwerp, relatie
RELATED_NOT_EQUIVALENT, geen keuze/resolutie in de bundel en geen ACTIVE quantity resolution, alle verwijzingen
bestaan, source cluster behouden, geen secrets. Een keuze in MJOP-App wordt nooit teruggeschreven als
quantity resolution.

## 11. Quantity Engine Generalization v1 — DOC-012

Tweede testcase buiten Maldenhof, alleen discovery + review (`scripts/doc012_generalization_review.py` →
`reports/quantity/doc012_generalization_review_v1.{json,md}`); geen building links, geen mapping-besluiten, geen
resolutie, geen bundel.

- **H1** (adresveld `building.address` "Meppelweg 819"): canonieke snapshot via de bestaande lookup_plan-route.
- **H2** (objectnaam "VvE Meppelweg 801-883"): `bag_snapshot_v1` legt geen query-bron vast, dus een bereik uit de
  objectnaam is geen document-adres-snapshot. De range-opvraging (zelfde code, `fetch_range_snapshot`) staat als
  read-only hypothese-opname in `reports/quantity/doc012_scope_hypotheses/` en wordt niet door `building_links.py`
  als kandidaat gezien.
- **Woonplaats-alias**: documenten noemen soms een gangbare naam ("Den Haag") terwijl BAG de officiële naam gebruikt
  ("'s-Gravenhage"). `vocabularies/woonplaats_aliases_v1.json` vertaalt alleen bij exacte gelijkheid; de toepassing
  staat in de snapshot-query (`city_bag_woonplaatsnaam`, `city_alias_ref`). Geen fuzzy matching; straat, huisnummer en
  postcode blijven exact. Snapshots zonder alias zijn ongewijzigd.
- Voorgestelde mapping `HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012` (PROPOSED, exact op document, code, eenheid
  en omschrijving 'Dakbedekking app'); de 4711-m1-randen vallen erbuiten.

## 12. DOC-012 Quantity Activation + tweede echte bundel v3

Menselijke besluiten (reviewer `user-approved`): H1 gekozen = het volledige BAG-pand `0518100000354752` van het
canonieke documentadres Meppelweg 819 (`BLINK-00081`, snapshot `BAGSNAP-599d2f2004100011`); H2 (objectnaamrange)
NOT_SELECTED — zonder REJECT-records, omdat die panden geen canonieke kandidaat zijn. Mapping
`HSM-ROOF_COVERING_REPORTED_AREA-4711-m2-DOC-012` VERIFY (`XWD-00003`). Gevel (2110) blijft NEEDS_SEMANTIC_REVIEW.

Bundel `reports/quantity/app_bundles/doc012_meppelweg_v3.json` (single-pand v3) via dezelfde exporter en validator
als Maldenhof (multi-pand). De validator controleert generiek ook dat een context-regel dezelfde eenheid heeft als het
kiesbare onderwerp. Rapport: `scripts/doc012_quantity_activation.py`. Geen quantity resolution.

## 13. Sloped Roof Quantity Activation v1

Besluiten van de gebruiker (2026-10-05), vastgelegd in de bestaande stores (geen nieuw systeem):

- **App-onderwerpmapping** `XQ-dak-hellend-ROOF_SLOPED_AREA-m2` (`mapping_kind: APP_QUANTITY_SUBJECT`,
  `internal_element_code: null`): app-element `dak-hellend` → `ROOF_SLOPED_AREA` (3D BAG `b3_opp_dak_schuin`).
  VERIFIED via `XWD-00004`. Dit besluit zegt niets over code 4712 of historische dakpannenoppervlakken.
- **Historisch onderwerp** `ROOF_TILES_REPORTED_AREA` (SOURCE_REPORTED, `source_reported_only`), met de relatie
  `ROOF_TILES_REPORTED_AREA ~ ROOF_SLOPED_AREA` = `RELATED_NOT_EQUIVALENT` (naast elkaar tonen; verschil = andere
  definitie; geen gemiddelde, geen enkele resolutie, geen automatische winnaar).
- **Smalle HSM** `HSM-ROOF_TILES_REPORTED_AREA-4712-m2-DOC-005-006`: exact DOC-005/DOC-006, 4712, m2,
  "Dakpan beton", "Hellend dak". Matcht alleen `QO-DOC-005-EL-027` en `QO-DOC-006-EL-027` (één source cluster).
  VERIFIED via `XWD-00005`. "Dakpannen leisteen" blijft OTHER_SLOPED_ROOF_MATERIAL zonder mapping.
- `XW-dak-hellend-4712-m2` blijft REVIEW_REQUIRED.
- `product_role`: `ROOF_TOTAL_AREA` = INFRASTRUCTURE_ONLY, `BUILDING_HEIGHT` = CONTEXT_ONLY; de export en de validator
  laten zulke onderwerpen nooit PRIMARY worden.

Exporter: PRIMARY komt uit een geverifieerde app-element→onderwerp-mapping; RELATED_CONTEXT alleen via een
vastgelegde relatie + een effectief VERIFIED HSM (exacte match) + dezelfde scope en eenheid, nooit via een gedeelde
elementcode. De validator controleert dit per app-element (hoogstens één PRIMARY per element+onderwerp).

Bundels: `maldenhof_expanded_v3.json` (dak-plat + dak-hellend; dak-hellend PRIMARY 1415.57 m² als som van 15 panden,
context 1485.60 m² dakpannen uit DOC-005 en DOC-006). De referentiebundels (`b1ca1d19…`, `748ebcbe…`) blijven
byte-identiek met `--app-elements dak-plat`. DOC-012 heeft een gemeten `ROOF_SLOPED_AREA` van 0.0 (geldig, geen
missing) en geen historische dakpannencontext.

Niet in deze stap: OUTER_WALL_GROSS_AREA, een derde gebouw, quantity resolutions.

## 14. Outer Wall + Scaffolding Semantics v1

- **App-semantiek (MJOP-App, Facade Quantity Semantics v1)**:
  - `gevel-metselwerk` en `voegwerk` gebruiken het bruto 3D BAG-buitenmuuroppervlak alleen als benadering (ESTIMATED), net als `schilderwerk-buiten`. Dezelfde getallen en kosten blijven staan; er komt geen historische 2110-mapping bij.
  - Een ontbrekende 3D BAG-hoogte geeft een onbekende werkhoogte. Dat betekent kosten onbekend, en niet meer stil 9 m.
- **Steiger**: de mapping `XQ-steiger-OUTER_WALL_GROSS_AREA-m2` (APP_QUANTITY_SUBJECT, geen interne code) is VERIFIED via `XWD-00006`, met de reden van de gebruiker letterlijk overgenomen.
  - Het VERIFY-besluit is pas vastgelegd nadat de kostenlogica per pand in de app geïmplementeerd en getest was.
  - De mapping declareert `pricing_context` (BUILDING_HEIGHT per pand).
- **Generieke regel** (app, `Q.scaffoldPricing`). Het tarief is de bestaande app-regel: werkhoogte = gebouwhoogte op 0,1 m en dan op hele meters; meer dan 8 m geeft € 11/m², anders € 6/m².
  - Enkel pand: hoeveelheid × tarief.
  - Scope waarin alle panden in één tariefklasse vallen: scopetotaal × dat tarief.
  - Scope met verschillende tariefklassen: SOM(pand-m² × tarief(eigen hoogte)).
  - Ontbrekende hoogte: kosten onbekend.
- **Bundels**:
  - De export hangt per pand een `pricing_context` aan de PRIMARY-regel, met BUILDING_HEIGHT-evidence-ref plus waarde, of MISSING/null.
  - De validator controleert:
    - dat de mapping de context declareert;
    - dat het onderwerp CONTEXT_ONLY is;
    - de exacte pandset;
    - dat de waarden canoniek zijn;
    - dat een MISSING-pand nooit 0 is en niet voorkomt terwijl er evidence bestaat.
  - Nieuw: `maldenhof_geometry_expanded_v3.json` en `doc012_geometry_v3.json`. De drie oudere bundels blijven byte-identiek.
- **Review**: `reports/quantity/scaffolding_height_review_v1.{json,md}` (`scripts/scaffolding_height_review.py`).
  - Maldenhof: alle 15 panden vallen in de klasse > 8 m (9,44 tot 12,25 m). A = B = € 19.221.
  - DOC-012: 3048,46 m², 19,56 m, € 33.533.

Niet in deze stap: historische gevelcontext (2110), quantity resolutions, een derde gebouw.
