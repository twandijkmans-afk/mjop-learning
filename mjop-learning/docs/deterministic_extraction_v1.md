# Deterministische extractie v1 — integratie in de bestaande pipeline

Status: integratiefase 2 (voorbereiding). Geen externe AI-API, geen netwerk.
Dit document legt de ontwerpbeslissingen vast die bij de integratie van
"Extractie v1" in deze branch zijn genomen.

## Beslissingen

### C1 — Gezaghebbende bronlaag

- `scripts/mjop_source_sections.py` is de **leidende parser** voor de
  bronformaten die hij ondersteunt (Objectblad-context, Jarenplan
  (Gedetailleerd), Jaarplan, Bevindingen NEN 2767). Hij wordt niet vervangen.
- `scripts/text_layer.py` is een **aanvullende technische laag** voor:
  a. fijnmazige provenance (block-ID's per regel/woord/cel);
  b. documenten/bestandstypen die `mjop_source_sections` niet ondersteunt;
  c. review en debugging.
- Voor één bronveld ontstaat nooit een tweede concurrerende waarde. Levert
  `mjop_source_sections` een veld al, dan blijft die waarde leidend en levert
  de tekstlaag alleen extra provenance.
- De brug is `record_validation.link_source_row_to_blocks(layer, page,
  source_text)`: een bronrij (pagina + `source_text` uit de pdftotext
  -table-weergave) wordt gekoppeld aan precies één tekstlaagregel op dezelfde
  pagina (vergelijking zonder `€` en witruimte). Geen unieke match → `None`.
  Gemeten op de gecommitte `data/price_observations/price_observations_batch1.json`:
  DOC-010 37/37, DOC-006 26/26, DOC-001 63/67 uniek gekoppeld; de rest `None`.

### C3 — Getallen zoals "1.250"

- `scripts/nl_values.py` is generiek conservatief: `"1.250"` → `None` +
  `ambiguous_thousands_or_decimal`.
- Alleen een expliciete profielregel mag zo'n bedrag als duizendtal lezen:
  `nl_values.parse_currency_profile(text, "pdf_whole_euro_dot_thousands", evidence)`.
  De regel vereist documentbewijs (`whole_euro_evidence`: ≥1 bedrag met
  punt-groepering en géén bedrag met decimalen) en geeft de regel-ID terug
  voor `provenance.extraction_rule` (`nl_values.profile:pdf_whole_euro_dot_thousands`).
  DOC-010: 568 bedragtokens, 0 met decimalen → bewijs consistent.
- `normalize_batch.to_decimal` blijft **ongewijzigd** (die leest `"1.250"`
  generiek als 1250). Historische output en hashes veranderen daardoor niet.
  Dit verschil is bewust en gedocumenteerd; harmonisatie is een aparte beslissing.

## Document registry

- `reports/document_registry.json`: permanente koppeling sha256 → document_id.
  DOC-001 t/m DOC-010 zijn exact de ID's van `reports/document_inventory.json`.
- `scripts/inventory_documents.py` haalt de ID's nu uit het registry in plaats
  van uit de volgorde van `os.walk`. Aanleiding (gemeten): de oude code gaf in
  een andere omgeving DOC-002..DOC-007 aan andere bestanden (bijv. Mauritstaete
  DOC-002 i.p.v. DOC-007). Met het registry is de output byte-identiek aan de
  gecommitte inventaris.
- Nieuwe bestanden krijgen alleen via `document_registry.py --register-new`
  (met toestemming) het volgende vrije ID; bestaande ID's verschuiven nooit.

## Provenance-schema

Alleen optionele, aanvullende velden; `additionalProperties: false` blijft:

- `_provenance.schema.json`: `block_id`, `related_block_ids`, `sheet`,
  `cell_ref`, `extraction_rule`.
- Paren (`element_code`, `element_type`, `material`, `unit`, `action`,
  `defect`, `condition_score`, `severity`): optioneel `provenance`.
- `maintenance_action.field_provenance` voor de losse primitieve velden
  `total_cost_as_stated` en `cost_year`.

Alle bestaande records in `data/extracted`, `data/normalized` en
`data/verified` blijven geldig (getest).

## Review

De bestaande reviewlaag blijft leidend (`export_review_sheet.py`,
`apply_review.py`, `_human_verification.schema.json`). Enige wijziging: de
export krijgt achteraan de informatieve kolommen `bron_pagina`,
`bron_block_id`, `bron_fragment` (apply_review leest op kolomnaam; de kolommen
worden nooit als waarde teruggelezen). `review_batch.py`/`review_spec.py` uit
Extractie v1 zijn niet overgenomen.

Bekende gaten in de bestaande reviewlaag (niet opgelost, beslissing nodig):
geen ADD (gemiste waarde/record toevoegen), EDIT alleen op `normalized_value`
van vocabulaire-paren, alleen records met `requires_human_review=True`, geen
append-only log.

## profile_overzicht15 — wat wel/niet

| Regel uit profile_overzicht15 | Status in deze branch | Besluit |
|---|---|---|
| Sectie-indeling op titels/kolomkoppen | aanwezig (`classify_sections`) | duplicaat |
| Prijspeil / BTW / indexatiezin | aanwezig (`parse_document_context`) | duplicaat |
| Jarenplan-rijen, jaarkolom op rechterrand, Stj/Cy | aanwezig (`parse_jarenplan_page`) | duplicaat |
| Vervolgregels element/actie, element over paginagrens | aanwezig | duplicaat |
| Rijtotaal vs som jaarbedragen | aanwezig (`reconcile_row_amounts`, afrondingstolerantie) | duplicaat; niet overnemen |
| Totaal object | aanwezig | duplicaat |
| Eén record per jaarbedrag | price observations hebben `annual_amounts`/`planned_years`/cyclus | ander model; niet overnemen |
| "4,0020" als dubbelzinnig markeren | bestaande parser houdt Hvh `4,00` + eenheid `20` letterlijk | bestaande regel leidend; niet overnemen |
| Bedrag "1.351" als 1351 | bestaand via generieke `to_decimal` | C3: expliciete profielregel in `nl_values` (geïmplementeerd, nog niet aangesloten) |
| Objectblad: Bouwjaar, Aantal eenheden, Adres, Inspectiedatum, Renovatiejaar, Postcode/Plaats | **ontbreekt** (nu alleen via LLM-extractie) | nuttig; fase 3, pas samen met deterministische route in extract_batch |
| Elementenoverzicht: code, element, locatie, hoeveelheid+eenheid, conditie | **ontbreekt** (`ELEMENTEN` alleen geclassificeerd) | nuttig; fase 3 |
| Conditielegenda (1–6, 8, 9) | **ontbreekt** | nuttig (review van 0/8/9); fase 3 |
| Groepssubtotalen reconciliëren | ontbreekt | optioneel, alleen als signalering; later |
| Paginadekking (elke regel geclassificeerd) | deels (`unlinked_section_rows`, checks) | later beoordelen |
| Block-ID-provenance | ontbreekt | geïmplementeerd als aanvullende brug (`link_source_row_to_blocks`) |

`profile_overzicht15.py` zelf is niet overgenomen als zelfstandige parser.

## Plan: extract_batch zonder externe API (fase 3, nog niet gebouwd)

```
extract_batch.py --mode deterministic --document DOC-xxx
  1. registry: sha256-controle van het bronbestand
  2. mjop_source_sections (pdftotext -table, xpdf 4.06) waar het formaat wordt herkend
       -> elementen / onderhoudsacties / prijspeil / BTW (leidende waarden)
  3. nieuwe profielregels rond de bestaande parser voor wat ontbreekt
       (objectblad-gebouwvelden, elementenoverzicht, conditielegenda)
  4. text_layer + link_source_row_to_blocks -> alleen extra provenance (block_id)
  5. bestaande schemas (record_validation.validate_entities + verify_block_provenance)
  6. output naar een eigen pad (bijv. data/extracted_deterministic/ of tijdelijke run-map);
     bestaande LLM-extractie en data/verified/ worden NIET overschreven
  7. bestaande reviewlaag (export_review_sheet / apply_review)
```

De LLM-route blijft zoals hij is (alleen actief met API-key); de
deterministische route wordt ernaast toegevoegd, niet ervoor in de plaats,
totdat een vergelijking per document is beoordeeld.

## pdftotext-afhankelijkheid

De gezaghebbende bronlaag verwacht **`pdftotext version 4.06
[www.xpdfreader.com]`** (xpdf, niet poppler) in `-table`-modus; regelnummers
in de provenance verwijzen naar die weergave (vastgelegd in
`price_observations_batch1.json` → `text_extraction`). Poppler's `pdftotext`
kent geen `-table`. In de huidige ontwikkelcontainer is pdftotext niet
geïnstalleerd; er is bewust niets systeemwijd geïnstalleerd en niet van parser
gewisseld. Twee tests in `test_price_observations.py` worden daarom
overgeslagen.
