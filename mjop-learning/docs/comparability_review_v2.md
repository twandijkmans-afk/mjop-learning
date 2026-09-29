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
