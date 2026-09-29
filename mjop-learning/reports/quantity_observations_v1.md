# Quantity observations v1

Builder `quantity_observations_v1.0.0`, regels `quantity_observation_rules_v1`. Afgeleid uit `data/verified/*.json` (elementenoverzicht); zie `docs/quantity_foundation_v1.md`.

Alle hoeveelheden hieronder zijn **ELEMENT_QUANTITY / SOURCE_REPORTED**: letterlijk gerapporteerd in een historisch MJOP, niet gemeten, niet gemiddeld en niet gekozen.

## Totalen

- Quantity observations: **662** uit 11 documenten
- Documenten zonder elementhoeveelheden: DOC-011, DOC-015
- Meetbaar (m2/m1/m3/stuks): 612
- Provenance compleet (document, pagina, tekstfragment, extractieregel): 662/662
- Hoeveelheid letterlijk teruggevonden in het tekstfragment: 661/662
- Met block_id: 646/662
- REVIEW_REQUIRED: **48**
- Gekoppelde actiehoeveelheden (price observations, alleen verwijzing): 474; price observations zonder elementkoppeling: 7

## Eenheden

| Eenheid | Aantal |
|---|---|
| lump_sum | 48 |
| m1 | 172 |
| m2 | 283 |
| null | 2 |
| piece | 157 |

## Per document en source cluster

| Document | Source cluster | Aantal | Relaties |
|---|---|---|---|
| DOC-001 | SC-DOC-001 | 57 | — |
| DOC-002 | SC-DOC-002 | 119 | DREL-001 duplicate_source ↔ DOC-003, DREL-004 same_building_other_inspection ↔ DOC-004 |
| DOC-004 | SC-DOC-004 | 140 | DREL-004 same_building_other_inspection ↔ DOC-002 |
| DOC-005 | SC-DOC-005+DOC-006 | 36 | DREL-002 version_of_same_mjop ↔ DOC-006 |
| DOC-006 | SC-DOC-005+DOC-006 | 35 | DREL-002 version_of_same_mjop ↔ DOC-005, DREL-005 duplicate_source ↔ DOC-014 |
| DOC-007 | SC-DOC-007 | 50 | — |
| DOC-008 | SC-DOC-008+DOC-009 | 15 | DREL-003 subplans_same_complex ↔ DOC-009 |
| DOC-009 | SC-DOC-008+DOC-009 | 61 | DREL-003 subplans_same_complex ↔ DOC-008 |
| DOC-010 | SC-DOC-010 | 57 | — |
| DOC-012 | SC-DOC-012 | 51 | — |
| DOC-013 | SC-DOC-013 | 41 | — |

## Review-redenen

| Reden | Aantal | Betekenis |
|---|---|---|
| `ACTION_QUANTITY_EXCEEDS_ELEMENT_QUANTITY` | 2 | gekoppelde actiehoeveelheid is groter dan de elementhoeveelheid (zelfde eenheid) |
| `AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH` | 9 | gekoppelde actiehoeveelheid heeft een andere meetbare eenheid dan het element |
| `DUPLICATE_KEY_DIFFERENT_QUANTITY` | 3 | zelfde element + locatie + eenheid komt in dit document vaker voor met een andere hoeveelheid |
| `QUANTITY_ONE_IN_MEASURED_UNIT` | 31 | precies 1 in m2/m1/m3: mogelijk een plaatshouder i.p.v. een gemeten hoeveelheid |
| `QUANTITY_TEXT_NOT_LOCATED` | 1 | de hoeveelheid is niet eenduidig terug te vinden in het brontekstfragment |
| `UNIT_IN_TEXT_DIFFERS` | 2 | de omschrijving noemt een andere eenheid dan de eenheidskolom |
| `UNIT_UNKNOWN` | 2 | eenheid niet in de gecontroleerde vocabulaire (normalized_value null) |

## Caveats (informatief, geen review)

| Caveat | Aantal | Betekenis |
|---|---|---|
| `BLOCK_ID_MISSING` | 16 | geen block_id (regel komt meermaals voor in de tekstlaag); pagina + tekstfragment aanwezig |
| `DIFFERS_FROM_RELATED_DOCUMENT` | 18 | andere hoeveelheid in een document over hetzelfde object (niet opgelost, niet gemiddeld) |
| `ELEMENT_CODE_EXTERNAL` | 140 | document gebruikt externe elementcodering; geen interne element_code |
| `LUMP_SUM_NOT_A_MEASURED_QUANTITY` | 48 | eenheid post: geen meetbare hoeveelheid |
| `SAME_IN_RELATED_DOCUMENT` | 232 | identieke hoeveelheid in een document over hetzelfde object: geen onafhankelijke bevestiging |

## Actiehoeveelheden t.o.v. elementhoeveelheid

Actiehoeveelheden blijven in de price observations; hier alleen de relatie per koppeling.

| Relatie | Aantal |
|---|---|
| ACTION_LUMP_SUM_OR_UNKNOWN_UNIT | 138 |
| DIFFERENT_UNIT | 11 |
| ELEMENT_NOT_MEASURABLE | 3 |
| EXCEEDS_ELEMENT | 2 |
| FRACTION_OF_ELEMENT | 45 |
| SAME_AS_ELEMENT | 275 |

## Afhankelijkheid tussen documenten over hetzelfde object

- Observations met een identieke hoeveelheid in een document over hetzelfde object: 232 (géén onafhankelijke bevestiging)
- Observations met een afwijkende hoeveelheid in zo'n document: 18 (niet opgelost, niet gemiddeld)

| Observation | Element | Locatie | Waarde | Afwijkend in |
|---|---|---|---|---|
| QO-DOC-002-EL-055 | Plafondafwerking pleisterwerk | Th 144 | 21.00 m2 | QO-DOC-004-EL-067 |
| QO-DOC-002-EL-056 | Plafondafwerking pleisterwerk | Th 74 | 21.00 m2 | QO-DOC-004-EL-070 |
| QO-DOC-002-EL-077 | Binnenschilderwerk panelen hout dekkend | Th 144 | 2.50 m2 | QO-DOC-004-EL-096 |
| QO-DOC-002-EL-083 | Binnenschilderwerk panelen hout dekkend | Th 74 | 2.50 m2 | QO-DOC-004-EL-097 |
| QO-DOC-002-EL-096 | Binnenschilderwerk hek hout dekkend | Th 144 | 2.00 m2 | QO-DOC-004-EL-116 |
| QO-DOC-002-EL-097 | Binnenschilderwerk hek hout dekkend | Th 74 | 2.00 m2 | QO-DOC-004-EL-117 |
| QO-DOC-004-EL-067 | Plafondafwerking pleisterwerk | Th 144 | 12.00 m2 | QO-DOC-002-EL-055 |
| QO-DOC-004-EL-070 | Plafondafwerking pleisterwerk | Th 74 | 12.00 m2 | QO-DOC-002-EL-056 |
| QO-DOC-004-EL-096 | Binnenschilderwerk panelen hout dekkend | Th 144 | 1.00 m2 | QO-DOC-002-EL-077 |
| QO-DOC-004-EL-097 | Binnenschilderwerk panelen hout dekkend | Th 74 | 1.50 m2 | QO-DOC-002-EL-083 |
| QO-DOC-004-EL-116 | Binnenschilderwerk hek hout dekkend | Th 144 | 1.00 m2 | QO-DOC-002-EL-096 |
| QO-DOC-004-EL-117 | Binnenschilderwerk hek hout dekkend | Th 74 | 1.00 m2 | QO-DOC-002-EL-097 |
| QO-DOC-005-EL-017 | Buitenschilderwerk leuning staal | Voorgevel - trappenhuizen | 61.00 m1 | QO-DOC-006-EL-017 |
| QO-DOC-005-EL-019 | Buitenschilderwerk (beton) trappen coating (polyurethaan) | Voorgevel - trappenhuizen | 80.00 m2 | QO-DOC-006-EL-019 |
| QO-DOC-005-EL-024 | Binnenschilderwerk plafond hout (multiplex) dekkend | Voorgevel - trappenhuizen | 105.08 m2 | QO-DOC-006-EL-024 |
| QO-DOC-006-EL-017 | Buitenschilderwerk leuning staal | Voorgevel - trappenhuizen | 42.00 m1 | QO-DOC-005-EL-017 |
| QO-DOC-006-EL-019 | Buitenschilderwerk (beton) trappen coating (polyurethaan) | Voorgevel - trappenhuizen | 62.00 m2 | QO-DOC-005-EL-019 |
| QO-DOC-006-EL-024 | Binnenschilderwerk plafond hout (multiplex) dekkend | Voorgevel - trappenhuizen | 85.70 m2 | QO-DOC-005-EL-024 |

## Invoer (sha256)

- `price_observations_sha256`: `903ba8807e334f7d5055d8a47b2547b25455c7befb07d7b4c9a586a1fd488a5b`
- `document_relations_sha256`: `2a1cab33999cf09ec3c25e6d59cacc44928f18cd3fc6559081112cf258f54580`
- `comparability_sha256`: `b9ab04c6759d28f9e74b692921438d92321e9e0ac03f90a0b7c69eb34d190b6e`
- `document_registry_sha256`: `e05de0ca0cd5f528b777b035a7cd8095051784b27f446e512282ad5e788651d9`
