# Building link candidates v1

Read-only. Dit rapport bevestigt niets; een link ontstaat alleen door een menselijk besluit (`scripts/building_links.py record`). Zie `docs/building_link_3dbag_evidence_v1.md`.

- Documenten: 13
- Status: AWAITING_BAG_SNAPSHOT 11, NO_ADDRESS 2
- Bevestigde links (ACTIVE): 0
- Documenten met meerdere bevestigde panden: —

| Document | Adres (zoals vermeld) | Postcode | Plaats | Cluster | Kandidaat-panden | Status | Review-redenen |
|---|---|---|---|---|---|---|---|
| DOC-001 | Alkmaarstraat 1-83 en Groetstraat 189-217 | — | Amsterdam | SC-DOC-001 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, MULTIPLE_STREETS, NO_BAG_SNAPSHOT, POSTCODE_MISSING |
| DOC-002 | Jan Pieter Heijestraat 144, Wilhelminastraat 74 | 1054 VZ | Amsterdam | SC-DOC-002 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT, MULTIPLE_STREETS, NO_BAG_SNAPSHOT |
| DOC-004 | J.P Heijestraat 144, Wilhelminastraat 74 | — | Amsterdam | SC-DOC-004 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT, MULTIPLE_STREETS, NO_BAG_SNAPSHOT, POSTCODE_MISSING |
| DOC-005 | Maldenhof 240 - 296 | 1106 EZ | Amsterdam | SC-DOC-005+DOC-006 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, NO_BAG_SNAPSHOT |
| DOC-006 | Maldenhof 240 - 296 | 1106 EZ | Amsterdam | SC-DOC-005+DOC-006 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, NO_BAG_SNAPSHOT |
| DOC-007 | (VvE Mauritsstaete) | — | Leiderdorp | SC-DOC-007 | — | NO_ADDRESS | NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING |
| DOC-008 | (VvE St. Jacobsstraat 251-321 Hoofddak) | — | — | SC-DOC-008+DOC-009 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_FROM_OBJECT_NAME, ADDRESS_RANGE, CITY_MISSING, NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING, SUBPLAN_SCOPE |
| DOC-009 | (VvE St. Jacobsstraat 251-321 Woningen) | — | Utrecht | SC-DOC-008+DOC-009 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_FROM_OBJECT_NAME, ADDRESS_RANGE, NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING, SUBPLAN_SCOPE |
| DOC-010 | Zomerdijkstraat 14, Uiterwaardenstraat 141 | 1079 XB | Amsterdam | SC-DOC-010 | — | AWAITING_BAG_SNAPSHOT | MULTIPLE_STREETS, NO_BAG_SNAPSHOT, OBJECT_NAME_ADDRESS_DIFFERS |
| DOC-011 | — | — | — | SC-DOC-011 | — | NO_ADDRESS | CITY_MISSING, NO_BAG_SNAPSHOT, NO_STATED_ADDRESS, POSTCODE_MISSING |
| DOC-012 | Meppelweg 819 | 2544 AW | Den Haag | SC-DOC-012 | — | AWAITING_BAG_SNAPSHOT | NO_BAG_SNAPSHOT, OBJECT_NAME_ADDRESS_DIFFERS |
| DOC-013 | Vechtstraat 13-15-17-19 | — | Amsterdam | SC-DOC-013 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, NO_BAG_SNAPSHOT, OBJECT_NAME_ADDRESS_DIFFERS, POSTCODE_MISSING |
| DOC-015 | Groetstraat 110-140 | — | Amsterdam | SC-DOC-015 | — | AWAITING_BAG_SNAPSHOT | ADDRESS_RANGE, NO_BAG_SNAPSHOT, POSTCODE_MISSING |

## Opvraagplanning (voor het ophalen van snapshots)

- DOC-001: Alkmaarstraat 1 Amsterdam; Alkmaarstraat 83 Amsterdam; Groetstraat 189 Amsterdam; Groetstraat 217 Amsterdam
- DOC-002: Jan Pieter Heijestraat 144 Amsterdam; Wilhelminastraat 74 Amsterdam
- DOC-004: J.P Heijestraat 144 Amsterdam; Wilhelminastraat 74 Amsterdam
- DOC-005: Maldenhof 240 Amsterdam; Maldenhof 296 Amsterdam
- DOC-006: Maldenhof 240 Amsterdam; Maldenhof 296 Amsterdam
- DOC-008: St. Jacobsstraat 251; St. Jacobsstraat 321
- DOC-009: St. Jacobsstraat 251 Utrecht; St. Jacobsstraat 321 Utrecht
- DOC-010: Zomerdijkstraat 14 Amsterdam; Uiterwaardenstraat 141 Amsterdam
- DOC-012: Meppelweg 819 2544 AW Den Haag
- DOC-013: Vechtstraat 13 Amsterdam; Vechtstraat 15 Amsterdam; Vechtstraat 17 Amsterdam; Vechtstraat 19 Amsterdam
- DOC-015: Groetstraat 110 Amsterdam; Groetstraat 140 Amsterdam

## Review-redenen

| Reden | Documenten | Betekenis |
|---|---|---|
| `ADDRESS_DIFFERS_FROM_SAME_OBJECT_DOCUMENT` | 2 | een document over hetzelfde object noemt het adres anders (geen fuzzy gelijkstelling) |
| `ADDRESS_FROM_OBJECT_NAME` | 2 | adres alleen afgeleid uit de objectnaam (VvE-naam), niet uit een adresveld |
| `ADDRESS_RANGE` | 7 | huisnummerbereik: aantal panden en even/oneven onbekend |
| `CITY_MISSING` | 2 | geen plaats in het document |
| `MULTIPLE_STREETS` | 4 | meerdere straten: waarschijnlijk meerdere panden |
| `NO_BAG_SNAPSHOT` | 13 | nog geen BAG/3D BAG-snapshot voor dit document (ophalen vereist netwerktoegang) |
| `NO_STATED_ADDRESS` | 4 | het document noemt geen adres in het objectblad |
| `OBJECT_NAME_ADDRESS_DIFFERS` | 3 | adres in de objectnaam verschilt van het adresveld |
| `POSTCODE_MISSING` | 8 | geen postcode in het document |
| `SUBPLAN_SCOPE` | 2 | deelplan van een complex: de panden kunnen gelijk zijn, de scope van de hoeveelheden niet |
