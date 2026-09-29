# Comparability review v2 — reviewfamilies en familiebesluiten

Doel: de human review van comparability-paren schaalbaar maken zonder iets automatisch te beslissen.
In plaats van elk paar los te beoordelen, beoordeelt een mens één **reviewfamilie**: een set paren die
exact dezelfde reviewvraag stelt. Het besluit wordt daarna per paar vastgelegd, in de bestaande
decision store (`docs/human_review_v1.md`), en alleen voor de paren die de mens expliciet opsomt.

## Bestanden

| Bestand | Rol |
|---|---|
| `scripts/comparability_review_v2.py` | bouwt het reviewpakket (alleen lezen, deterministisch, geen tijdstempels) |
| `reports/review/comparability_review_v2.json` | machineleesbaar pakket (families, kandidaatgroepen, effecten) |
| `reports/review/comparability_review_v2.md` | menselijk leesbaar overzicht |
| `scripts/apply_family_decision.py` | past één expliciet familiebesluit toe (canonieke ketenschakel, rollback) |
| `data/review_decisions/family_decisions/RFD-NNNNN.json` | de toegepaste familiebesluiten (audit trail) |
| `scripts/canonical_change.py` | gedeelde ketenschakel voor menselijke besluiten (snapshot, invarianten, rollback) |

## Reviewfamilies

Basis: exact de queue van v1 (`export_human_review_queue.select_pairs`).

Twee paren zitten in dezelfde familie als het volgende gelijk is:

- de **candidate key** (elementcode, actie en eenheid, genormaliseerd);
- **per kant**:
  - objectomschrijving en actietekst als woordtokens, zonder de vaste, goedgekeurde gevelzijde-woorden
    (`achter`, `voor`, `achterzijde`, `voorzijde`, `achtergevel`, `voorgevel`; zelfde lijst als
    kengetallen regel 3);
  - de eenheid zoals in de bron;
  - het materiaal (waarde en bron uit comparability F8);
  - de inhoudelijke observation-caveats (`UPGRADE`, `COMBINED_EXECUTION`, `PARTIAL_SCOPE`,
    `FRACTIONAL_PIECE_COUNT`, `MIXED_MATERIAL`);
- of de gevelzijde-woorden verschillen;
- of er een `QUANTITY_SCALE_DIFFERENCE` is;
- of er een relatierisico is: een relatie of relatievoorstel tussen de documenten, of `POSSIBLY_DEPENDENT`.

Binnen een familie mogen alleen deze gegevens verschillen: document, source cluster, hoeveelheid, prijs en
prijspeil. Die staan per paar in het pakket. Er is geen fuzzy matching, geen score, geen confidence en
geen rangschikking.

De `review_family_id` is een hash van de familiesleutel en blijft dus gelijk bij gelijke invoer.

De `family_input_sha256` is een hash over alles waarop een besluit rust:

- de paren en hun systeemredenen;
- de genormaliseerde observations en de comparability-beoordelingen;
- de bestaande beslissingen van die paren.

Een bewijscategorie per familie komt uit bestaande velden. De volgorde is:

1. `SOURCE_RELATION_RISK`
2. `UNIT_DIFFERENCE`
3. `OTHER_REVIEW_REQUIRED`
4. `OBJECT_TEXT_VARIANT`
5. `ACTION_TEXT_VARIANT`
6. `MATERIAL_DIFFERENCE_ONLY`
7. `MATERIAL_EVIDENCE_ONE_SIDE`
8. `QUANTITY_SCALE_DIFFERENCE`
9. `EXACT_SAME_SEMANTIC_INPUT`

Alle vlaggen die gelden staan in `evidence_flags`.

## Kandidaatgroepen

Voor de groepen met minimaal 3 clusters toont het pakket per candidate key:

- alle observations;
- de potentieel beschikbare clusters (`independent_input`);
- het materiaalbewijs per observation;
- de concrete stappen die nog ontbreken voordat een groep volgens `docs/kengetallen_rules_v1.md` een
  kengetal kan zijn.

Het materiaalbewijs heeft drie vormen:

- `KNOWN`: verified-element of goedgekeurde tekstregel.
- `TEXT_EVIDENCE_PENDING_APPROVAL`: de bestaande tekstregel zou een materiaal afleiden, maar het document
  valt buiten de goedgekeurde `MATERIAL_FROM_TEXT`-scope. Dit wordt alleen getoond, niet toegepast.
- `NO_MATERIAL_EVIDENCE`: er is geen materiaalbewijs.

De ontbrekende stappen zijn:

- materiaalgoedkeuring;
- ontbrekende cross-cluster-beslissingen (regel 2, geen transitiviteit);
- een ACTIVE `NOT_COMPARABLE`;
- minder dan 3 clusters.

Er wordt **geen kengetal en geen waarde berekend**.

Per familie en per keuze staat het `kengetal_effect`. Dat is een simulatie met de bestaande
kengetalregels. Ze toont alleen status, clusters en redenen, geen waarden.

## Toegestane keuzes (bestaand model)

`COMPARABLE`, `COMPARABLE_WITH_CAVEATS`, `NOT_COMPARABLE`, `UNKNOWN`. Er komt geen nieuwe semantiek bij.

## Een familiebesluit toepassen

Een mens schrijft een besluitbestand; het veldformaat staat in `scripts/apply_family_decision.py`. Daarna:

```
python scripts/apply_family_decision.py --decision besluit.json --dry-run
python scripts/apply_family_decision.py --decision besluit.json
python scripts/apply_family_decision.py --rollback RFD-00001
```

Het besluit wordt alleen toegepast als alle volgende controles slagen:

- het bekeken pakket is byte-gelijk (`review_package_sha256`);
- de comparability-invoer, de genormaliseerde invoer en de relaties zijn ongewijzigd;
- de familie bestaat nog met exact dezelfde `family_input_sha256`. Een gewijzigd paar, een gewijzigde
  observation of een nieuwe beslissing laat het besluit vervallen;
- alleen de opgesomde `pair_ids` worden toegepast, en elk daarvan hoort bij de familie. Er is geen
  dynamische matching;
- een besluit waardoor een AVAILABLE kengetal verdwijnt of ontstaat, moet dat exact bevestigen in
  `acknowledged_kengetal_effects`. Er wordt nooit stil een kengetal gewijzigd.

Zo wordt het besluit vastgelegd:

- Per paar komt er één nieuw ACTIVE HDR-record met `family_decision` (verwijzing naar het besluit, het
  pakket en de familiehash).
- Een bestaand ACTIVE- of REVIEW_REQUIRED-record van dat paar wordt SUPERSEDED. Schema,
  store-invarianten en append-only worden gecontroleerd.
- De kengetallen worden herbouwd met de bestaande regels. De oude versie gaat naar
  `data/kengetallen/history/`.
- Price observations, comparability en `document_relations.json` blijven byte-gelijk.

De hele wijziging is één schakel in de canonieke keten, `data/incoming_promotions/RFD-NNNNN.json` met
status `APPLIED`, met pre/post-manifest en history. Rollback kan alleen van de laatste schakel.

## Relatiebesluiten

`scripts/record_relation_decision.py` legt een menselijk relatiebesluit uit een reviewpakket van
`prepare_relation_review.py` vast in `document_relations.json`:

- alleen met het bestaande relatietype van de gekozen optie (`DUPLICATE_OTHER_BYTES` →
  `duplicate_source`);
- gebonden aan de sha256 van het pakket;
- alleen als het bewijs het besluit niet tegenspreekt.

Een relatie die al volgt uit bestaande relaties wordt niet apart toegevoegd; ze staat als
`implied_relations` bij het besluit. Ook dit is een ketenschakel (`RELDEC-DREL-NNN`) met rollback.

Voorbeeld: DREL-005, DOC-014 `duplicate_source` van DOC-006.

- DOC-014 levert geen observations en krijgt geen eigen cluster. Het valt in `SC-DOC-005+DOC-006`.
- In de incoming-promotie krijgt DOC-014 de beslissing `SKIPPED_DUPLICATE` (`CONFIRMED_DUPLICATE_SOURCE`).

## Materiaalbesluiten per observation

`scripts/record_material_decision.py` legt een menselijk materiaalbesluit vast voor **exact opgesomde
observations**. De besluiten staan in `data/review_decisions/material_decision_records.json` (schema
`material_decision_record.schema.json`, scope `EXACT_OBSERVATION`, append-only). Er is geen documentbrede
`MATERIAL_FROM_TEXT`-scope en geen afleiding voor andere observations.

Het besluit wordt alleen vastgelegd als:

- de opgegeven objectomschrijving, actietekst en eenheid letterlijk gelijk zijn aan de bron;
- het materiaal als los vocabulairewoord in de objectomschrijving staat, zonder ander materiaal in object of
  actie;
- er nog geen materiaal is (het verified-element blijft leidend).

Elk besluit is gebonden aan de sha256 van de bronobservation (`source_observation_sha256`) en van het
brondocument. Wijzigt de bronobservation, dan vervalt het besluit bij de normalisatie en is het materiaal
weer onbekend (`material_decision_input_changed`).

De normalisatie zet `material_source = human_material_decision`
(`MATERIAL_FROM_HUMAN_DECISION`, `material_decision_id`). Comparability F8 neemt dit over als bron tussen
het verified-element en de tekstregel (`docs/comparability_rules_v1.md`, punt 9).

Het besluit is een ketenschakel (`MATDEC-NNNNN`) met rollback, en de invarianten worden gecontroleerd:

- alleen het materiaal van precies deze observations wijzigt;
- bedragen, paren, source clusters, relaties en de human decision store blijven gelijk;
- de kengetallen blijven inhoudelijk gelijk.

Eerste besluit: MATDEC-00001 (MDR-00001 PO-DOC-012-P015-L033 en MDR-00002 PO-DOC-013-P019-L025, pvc).

## Beslispakket 5211 pvc

`scripts/decision_package_5211_pvc.py` schrijft `reports/review/decision_package_5211_pvc.json` en `.md`.
Het pakket bevat:

- alle pvc-observations van 5211 replace m1;
- elk open cross-cluster paar met alle beoordelingsvelden;
- per paar de inhoudelijke controle: zelfde actie, pvc, m1, geen relatie, verschil alleen in prijspeil,
  hoeveelheid en prijs;
- simulaties met `build_kengetallen.evaluate` per open familie en per keuze (`COMPARABLE`,
  `COMPARABLE_WITH_CAVEATS`, `NOT_COMPARABLE`), plus de combinaties.

Er wordt niets toegepast.

Een positief besluit over één familie maakt de groep volgens regel 2 tijdelijk onvolledig
(INSUFFICIENT_DATA). Pas als alle cross-cluster paren positief beoordeeld zijn, is de groep weer volledig.
Het apply-script vraagt daarom per familie om een expliciete bevestiging van het kengetal-effect.

## Atomaire transactie over meerdere families

Een besluitbestand kan in plaats van één familie een lijst `families` bevatten:

```json
{"review_package_sha256": "...", "decision": "COMPARABLE_WITH_CAVEATS", "decision_reason": "...",
 "reviewer": "...", "reviewed_at": "...", "notes": null, "acknowledged_kengetal_effects": ["KG-..."],
 "families": [{"review_family_id": "RF-...", "family_input_sha256": "...", "pair_ids": ["PAIR-..."],
               "decision_caveats": ["PRICE_LEVEL_DIFFERENCE"]}]}
```

Alle families worden samen gevalideerd en toegepast als één ketenschakel (`RFD-NNNNN`), met één rollback.
Faalt één familie, dan wordt niets toegepast.

- Het kengetal-effect wordt over alle paren samen bepaald en moet exact bevestigd zijn. Zo komt een kengetal
  niet tussentijds in een onvolledige toestand.
- `decision_caveats` mogen alleen voorbehouden bevatten die het systeem voor elk genoemd paar al gaf. Er
  komen geen nieuwe caveat-types bij.

Eerste transactie: RFD-00001 (5211 pvc, 7 paren, HDR-00036 t/m HDR-00042) →
KG-5211-replace-m1-pvc-5cb98033 AVAILABLE 54.39 (5 clusters). De vorige versie (67920b77, 51.79) staat in
`data/kengetallen/history/`.
