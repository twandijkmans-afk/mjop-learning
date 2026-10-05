# Building link candidates v1

Read-only. Dit rapport bevestigt niets; een link ontstaat alleen door een menselijk besluit (`scripts/building_links.py record`). Zie `docs/building_link_3dbag_evidence_v1.md`.

- Documenten: 13
- Status: AWAITING_BAG_SNAPSHOT 9, LINKED 2, NO_ADDRESS 2
- Bevestigde links (ACTIVE): 30
- Documenten met meerdere bevestigde panden: DOC-005, DOC-006

| Document | Adres (zoals vermeld) | Postcode | Plaats | Cluster | Kandidaat-panden | Status | Review-redenen |
|---|---|---|---|---|---|---|---|
| DOC-001 | Alkmaarstraat 1-83 en Groetstraat 189-217 | — | Amsterdam | SC-DOC-001 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, MULTIPLE_STREETS, NO_BAG_SNAPSHOT, POSTCODE_MISSING |
| DOC-002 | Jan Pieter Heijestraat 144, Wilhelminastraat 74 | 1054 VZ | Amsterdam | SC-DOC-002 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT, MULTIPLE_STREETS, NO_BAG_SNAPSHOT |
| DOC-004 | J.P Heijestraat 144, Wilhelminastraat 74 | — | Amsterdam | SC-DOC-004 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT, MULTIPLE_STREETS, NO_BAG_SNAPSHOT, POSTCODE_MISSING |
| DOC-005 | Maldenhof 240 - 296 | 1106 EZ | Amsterdam | SC-DOC-005+DOC-006 | 0363100012061310, 0363100012063561, 0363100012064674, 0363100012065912, 0363100012070344, 0363100012071880, 0363100012077783, 0363100012077984, 0363100012078022, 0363100012078472, 0363100012081986, 0363100012083986, 0363100012084256, 0363100012087184, 0363100012091756, 0363100012091974, 0363100012100140, 0363100012102257, 0363100012102659, 0363100012105151, 0363100012107492, 0363100012108812, 0363100012121455, 0363100012123643, 0363100012125929, 0363100012127361, 0363100012129433, 0363100012134188, 0363100012135143, 0363100012137009, 0363100012137996, 0363100012138208, 0363100012140664, 0363100012141419, 0363100012143647, 0363100012144766, 0363100012148993, 0363100012151715, 0363100012152265, 0363100012154610 | LINKED | ADDRESS_RANGE, MULTIPLE_CANDIDATE_PANDEN |
| DOC-006 | Maldenhof 240 - 296 | 1106 EZ | Amsterdam | SC-DOC-005+DOC-006 | 0363100012061310, 0363100012063561, 0363100012064674, 0363100012065912, 0363100012070344, 0363100012071880, 0363100012077783, 0363100012077984, 0363100012078022, 0363100012078472, 0363100012081986, 0363100012083986, 0363100012084256, 0363100012087184, 0363100012091756, 0363100012091974, 0363100012100140, 0363100012102257, 0363100012102659, 0363100012105151, 0363100012107492, 0363100012108812, 0363100012121455, 0363100012123643, 0363100012125929, 0363100012127361, 0363100012129433, 0363100012134188, 0363100012135143, 0363100012137009, 0363100012137996, 0363100012138208, 0363100012140664, 0363100012141419, 0363100012143647, 0363100012144766, 0363100012148993, 0363100012151715, 0363100012152265, 0363100012154610 | LINKED | ADDRESS_RANGE, MULTIPLE_CANDIDATE_PANDEN |
| DOC-007 | (VvE Mauritsstaete) | — | Leiderdorp | SC-DOC-007 | — | NO_ADDRESS | NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING |
| DOC-008 | (VvE St. Jacobsstraat 251-321 Hoofddak) | — | — | SC-DOC-008+DOC-009 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_FROM_OBJECT_NAME, ADDRESS_RANGE, CITY_MISSING, NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING, SUBPLAN_SCOPE |
| DOC-009 | (VvE St. Jacobsstraat 251-321 Woningen) | — | Utrecht | SC-DOC-008+DOC-009 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_FROM_OBJECT_NAME, ADDRESS_RANGE, NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING, SUBPLAN_SCOPE |
| DOC-010 | Zomerdijkstraat 14, Uiterwaardenstraat 141 | 1079 XB | Amsterdam | SC-DOC-010 | — | AWAITING_BAG_SNAPSHOT | MULTIPLE_STREETS, NO_BAG_SNAPSHOT, OBJECT_NAME_ADDRESS_DIFFERS |
| DOC-011 | — | — | — | SC-DOC-011 | — | NO_ADDRESS | CITY_MISSING, NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING |
| DOC-012 | Meppelweg 819 | 2544 AW | Den Haag | SC-DOC-012 | — | AWAITING_BAG_SNAPSHOT | NO_BAG_SNAPSHOT, OBJECT_NAME_ADDRESS_DIFFERS |
| DOC-013 | Vechtstraat 13-15-17-19 | — | Amsterdam | SC-DOC-013 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, NO_BAG_SNAPSHOT, OBJECT_NAME_ADDRESS_DIFFERS, POSTCODE_MISSING |
| DOC-015 | Groetstraat 110-140 | — | Amsterdam | SC-DOC-015 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, NO_BAG_SNAPSHOT, POSTCODE_MISSING |

## Opvraagplanning (voor het ophalen van snapshots)

- DOC-001: Alkmaarstraat 1-83 (bereik, fetch-range) Amsterdam; Groetstraat 189-217 (bereik, fetch-range) Amsterdam
- DOC-002: Jan Pieter Heijestraat 144 Amsterdam; Wilhelminastraat 74 Amsterdam
- DOC-004: J.P Heijestraat 144 Amsterdam; Wilhelminastraat 74 Amsterdam
- DOC-005: Maldenhof 240-296 (bereik, fetch-range) 1106 EZ Amsterdam
- DOC-006: Maldenhof 240-296 (bereik, fetch-range) 1106 EZ Amsterdam
- DOC-008: St. Jacobsstraat 251-321 (bereik, fetch-range)
- DOC-009: St. Jacobsstraat 251-321 (bereik, fetch-range) Utrecht
- DOC-010: Zomerdijkstraat 14 Amsterdam; Uiterwaardenstraat 141 Amsterdam
- DOC-012: Meppelweg 819 2544 AW Den Haag
- DOC-013: Vechtstraat 13 Amsterdam; Vechtstraat 15 Amsterdam; Vechtstraat 17 Amsterdam; Vechtstraat 19 Amsterdam
- DOC-015: Groetstraat 110-140 (bereik, fetch-range) Amsterdam

## Kandidaat-panden DOC-005 (beslist niets)

| BAG-pand | Adressen in het pand | Postcode = document? | 3D BAG |
|---|---|---|---|
| 0363100012061310 | Maldenhof 289, 1106EJ Amsterdam | False | ja |
| 0363100012063561 | Maldenhof 257, 1106EH Amsterdam | False | ja |
| 0363100012064674 | Maldenhof 245, 1106EH Amsterdam | False | ja |
| 0363100012065912 | Maldenhof 273, 1106EJ Amsterdam | False | ja |
| 0363100012070344 | Maldenhof 262, 1106EZ Amsterdam, Maldenhof 264, 1106EZ Amsterdam | True | ja |
| 0363100012071880 | Maldenhof 270, 1106EZ Amsterdam, Maldenhof 272, 1106EZ Amsterdam | True | ja |
| 0363100012077783 | Maldenhof 281, 1106EJ Amsterdam | False | ja |
| 0363100012077984 | Maldenhof 283, 1106EJ Amsterdam | False | ja |
| 0363100012078022 | Maldenhof 246, 1106EZ Amsterdam, Maldenhof 248, 1106EZ Amsterdam | True | ja |
| 0363100012078472 | Maldenhof 287, 1106EJ Amsterdam | False | ja |
| 0363100012081986 | Maldenhof 285, 1106EJ Amsterdam | False | ja |
| 0363100012083986 | Maldenhof 277, 1106EJ Amsterdam | False | ja |
| 0363100012084256 | Maldenhof 255, 1106EH Amsterdam | False | ja |
| 0363100012087184 | Maldenhof 241, 1106EH Amsterdam | False | ja |
| 0363100012091756 | Maldenhof 278, 1106EZ Amsterdam, Maldenhof 280, 1106EZ Amsterdam | True | ja |
| 0363100012091974 | Maldenhof 258, 1106EZ Amsterdam, Maldenhof 260, 1106EZ Amsterdam | True | ja |
| 0363100012100140 | Maldenhof 291, 1106EJ Amsterdam | False | ja |
| 0363100012102257 | Maldenhof 295, 1106EJ Amsterdam | False | ja |
| 0363100012102659 | Maldenhof 242, 1106EZ Amsterdam, Maldenhof 244, 1106EZ Amsterdam | True | ja |
| 0363100012105151 | Maldenhof 269, 1106EJ Amsterdam | False | ja |
| 0363100012107492 | Maldenhof 266, 1106EZ Amsterdam, Maldenhof 268, 1106EZ Amsterdam | True | ja |
| 0363100012108812 | Maldenhof 249, 1106EH Amsterdam | False | ja |
| 0363100012121455 | Maldenhof 286, 1106EZ Amsterdam, Maldenhof 288, 1106EZ Amsterdam | True | ja |
| 0363100012123643 | Maldenhof 243, 1106EH Amsterdam | False | ja |
| 0363100012125929 | Maldenhof 293, 1106EJ Amsterdam | False | ja |
| 0363100012127361 | Maldenhof 294, 1106EZ Amsterdam, Maldenhof 296, 1106EZ Amsterdam | True | ja |
| 0363100012129433 | Maldenhof 279, 1106EJ Amsterdam | False | ja |
| 0363100012134188 | Maldenhof 290, 1106EZ Amsterdam, Maldenhof 292, 1106EZ Amsterdam | True | ja |
| 0363100012135143 | Maldenhof 247, 1106EH Amsterdam | False | ja |
| 0363100012137009 | Maldenhof 261, 1106EH Amsterdam, Maldenhof 263, 1106EH Amsterdam, Maldenhof 265, 1106EH Amsterdam | False | ja |
| 0363100012137996 | Maldenhof 240, 1106EZ Amsterdam | True | ja |
| 0363100012138208 | Maldenhof 271, 1106EJ Amsterdam | False | ja |
| 0363100012140664 | Maldenhof 250, 1106EZ Amsterdam, Maldenhof 252, 1106EZ Amsterdam | True | ja |
| 0363100012141419 | Maldenhof 254, 1106EZ Amsterdam, Maldenhof 256, 1106EZ Amsterdam | True | ja |
| 0363100012143647 | Maldenhof 282, 1106EZ Amsterdam, Maldenhof 284, 1106EZ Amsterdam | True | ja |
| 0363100012144766 | Maldenhof 274, 1106EZ Amsterdam, Maldenhof 276, 1106EZ Amsterdam | True | ja |
| 0363100012148993 | Maldenhof 275, 1106EJ Amsterdam | False | ja |
| 0363100012151715 | Maldenhof 253, 1106EH Amsterdam | False | ja |
| 0363100012152265 | Maldenhof 251, 1106EH Amsterdam | False | ja |
| 0363100012154610 | Maldenhof 259, 1106EH Amsterdam | False | ja |

## Kandidaat-panden DOC-006 (beslist niets)

| BAG-pand | Adressen in het pand | Postcode = document? | 3D BAG |
|---|---|---|---|
| 0363100012061310 | Maldenhof 289, 1106EJ Amsterdam | False | ja |
| 0363100012063561 | Maldenhof 257, 1106EH Amsterdam | False | ja |
| 0363100012064674 | Maldenhof 245, 1106EH Amsterdam | False | ja |
| 0363100012065912 | Maldenhof 273, 1106EJ Amsterdam | False | ja |
| 0363100012070344 | Maldenhof 262, 1106EZ Amsterdam, Maldenhof 264, 1106EZ Amsterdam | True | ja |
| 0363100012071880 | Maldenhof 270, 1106EZ Amsterdam, Maldenhof 272, 1106EZ Amsterdam | True | ja |
| 0363100012077783 | Maldenhof 281, 1106EJ Amsterdam | False | ja |
| 0363100012077984 | Maldenhof 283, 1106EJ Amsterdam | False | ja |
| 0363100012078022 | Maldenhof 246, 1106EZ Amsterdam, Maldenhof 248, 1106EZ Amsterdam | True | ja |
| 0363100012078472 | Maldenhof 287, 1106EJ Amsterdam | False | ja |
| 0363100012081986 | Maldenhof 285, 1106EJ Amsterdam | False | ja |
| 0363100012083986 | Maldenhof 277, 1106EJ Amsterdam | False | ja |
| 0363100012084256 | Maldenhof 255, 1106EH Amsterdam | False | ja |
| 0363100012087184 | Maldenhof 241, 1106EH Amsterdam | False | ja |
| 0363100012091756 | Maldenhof 278, 1106EZ Amsterdam, Maldenhof 280, 1106EZ Amsterdam | True | ja |
| 0363100012091974 | Maldenhof 258, 1106EZ Amsterdam, Maldenhof 260, 1106EZ Amsterdam | True | ja |
| 0363100012100140 | Maldenhof 291, 1106EJ Amsterdam | False | ja |
| 0363100012102257 | Maldenhof 295, 1106EJ Amsterdam | False | ja |
| 0363100012102659 | Maldenhof 242, 1106EZ Amsterdam, Maldenhof 244, 1106EZ Amsterdam | True | ja |
| 0363100012105151 | Maldenhof 269, 1106EJ Amsterdam | False | ja |
| 0363100012107492 | Maldenhof 266, 1106EZ Amsterdam, Maldenhof 268, 1106EZ Amsterdam | True | ja |
| 0363100012108812 | Maldenhof 249, 1106EH Amsterdam | False | ja |
| 0363100012121455 | Maldenhof 286, 1106EZ Amsterdam, Maldenhof 288, 1106EZ Amsterdam | True | ja |
| 0363100012123643 | Maldenhof 243, 1106EH Amsterdam | False | ja |
| 0363100012125929 | Maldenhof 293, 1106EJ Amsterdam | False | ja |
| 0363100012127361 | Maldenhof 294, 1106EZ Amsterdam, Maldenhof 296, 1106EZ Amsterdam | True | ja |
| 0363100012129433 | Maldenhof 279, 1106EJ Amsterdam | False | ja |
| 0363100012134188 | Maldenhof 290, 1106EZ Amsterdam, Maldenhof 292, 1106EZ Amsterdam | True | ja |
| 0363100012135143 | Maldenhof 247, 1106EH Amsterdam | False | ja |
| 0363100012137009 | Maldenhof 261, 1106EH Amsterdam, Maldenhof 263, 1106EH Amsterdam, Maldenhof 265, 1106EH Amsterdam | False | ja |
| 0363100012137996 | Maldenhof 240, 1106EZ Amsterdam | True | ja |
| 0363100012138208 | Maldenhof 271, 1106EJ Amsterdam | False | ja |
| 0363100012140664 | Maldenhof 250, 1106EZ Amsterdam, Maldenhof 252, 1106EZ Amsterdam | True | ja |
| 0363100012141419 | Maldenhof 254, 1106EZ Amsterdam, Maldenhof 256, 1106EZ Amsterdam | True | ja |
| 0363100012143647 | Maldenhof 282, 1106EZ Amsterdam, Maldenhof 284, 1106EZ Amsterdam | True | ja |
| 0363100012144766 | Maldenhof 274, 1106EZ Amsterdam, Maldenhof 276, 1106EZ Amsterdam | True | ja |
| 0363100012148993 | Maldenhof 275, 1106EJ Amsterdam | False | ja |
| 0363100012151715 | Maldenhof 253, 1106EH Amsterdam | False | ja |
| 0363100012152265 | Maldenhof 251, 1106EH Amsterdam | False | ja |
| 0363100012154610 | Maldenhof 259, 1106EH Amsterdam | False | ja |

## Review-redenen

| Reden | Documenten | Betekenis |
|---|---|---|
| `ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT` | 2 | een document over hetzelfde object noemt het adres anders (geen fuzzy gelijkstelling) |
| `ADDRESS_FROM_OBJECT_NAME` | 2 | adres alleen afgeleid uit de objectnaam (VvE-naam), niet uit een adresveld |
| `ADDRESS_RANGE` | 7 | huisnummerbereik: aantal panden en even/oneven onbekend |
| `CITY_MISSING` | 2 | geen plaats in het document |
| `MULTIPLE_CANDIDATE_PANDEN` | 2 | meerdere kandidaat-panden: elk pand apart bevestigen of afwijzen |
| `MULTIPLE_STREETS` | 4 | meerdere straten: waarschijnlijk meerdere panden |
| `NO_BAG_SNAPSHOT` | 11 | nog geen BAG/3D BAG-snapshot voor dit document (ophalen vereist netwerktoegang) |
| `NO_STATED_ADDRESS` | 4 | het document noemt geen adres in het objectblad |
| `OBJECT_NAME_ADDRESS_DIFFERS` | 3 | adres in de objectnaam verschilt van het adresveld |
| `POSTCODE_MISSING` | 8 | geen postcode in het document |
| `SUBPLAN_SCOPE` | 2 | deelplan van een complex: de panden kunnen gelijk zijn, de scope van de hoeveelheden niet |
