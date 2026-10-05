# Quantity Engine Activation Review v1 — Maldenhof (DOC-005 / DOC-006)

Read-only bronnenvergelijking. **Geen accuracy-benchmark, geen besluiten, geen evidence, geen API- of netwerkcalls.** Gegenereerd door `scripts/quantity_engine_activation_review.py`.

Stand menselijke besluiten: building links 0, crosswalk-besluiten 0, quantity resolutions 0, building evidence 0.

## A — Maldenhof-inputs (PoC v2-snapshot)

- BAG-panden in scope: **15**; VBO's/adressen: **29** (per pand: 1 VBO: 1 panden, 2 VBO: 14 panden).
- Huisnummers = alle even nummers 240–296: **ja** (29 even van 57 nummers in het bereik; document: 29 eenheden).
- VBO-punten binnen de BAG-polygoon van hun pand: 29/29.
- Ruwe bestanden met kloppende sha256: 69/69; fetched_at niet vastgelegd op main.
- Overige kandidaat-panden (oneven zijde, context): 25.
- **Oordeel: NOT_FEEDABLE_OFFLINE_INTO_CANONICAL_PIPELINE** — De PoC-inputs bevatten 3D BAG en VBO's met sha256, maar niet de PDOK-adresrespons en de BAG-pandrespons per adres die bag_snapshot_v1 vereist. Een BAGSNAP samenstellen uit andere queries zou de opvraagketen veinzen; dat is niet gedaan. Er is geen adapter naar data/ geschreven en geen tweede snapshotsysteem gemaakt.

| Veld | Canoniek (bag_snapshot_v1) | PoC-snapshot |
|---|---|---|
| requests[] + raw PDOK Locatieserver 'free' respons | verplicht (bag_snapshot_v1: elke request + ruwe respons, exacte adresmatch) | ontbreekt (adressen staan alleen als afgeleide lijst addresses_found) |
| BAG OGC pand-items per adrespunt (bbox rond het adres) + punt-in-polygoon | verplicht; bepaalt welke panden kandidaat zijn | niet per adres; wel één bbox-respons rond het hele complex (bag_panden_bbox.json, zonder request-URL/sha in een snapshot) |
| 3D BAG-respons per pand | ruwe respons + canonical_sha256 + url + fetched_at + api_version | ruwe respons + bestands-sha256 (andere hash-conventie); fetched_at en url niet vastgelegd op main |
| snapshot_id (BAGSNAP-…) | content-addressed per (document, adres-query) | geen; één snapshot voor het hele complex en beide documenten |
| document_id | één document per snapshot | groep DOC-005-006 |

Context: 21 BAG-panden zonder VBO binnen 2 m (14 in gebruik, samen 69.6 m² footprint, ~5 m² per stuk). Context, geen kandidaat en geen evidence. BAG-panden zonder verblijfsobject binnen 2 m van de 15 panden (bron: bag_panden_bbox.json). Het MJOP sluit 'tuinopstallen' en 'aan-, uit- en/of dakopbouwen' als bewonerseigen uit (DOC-005 p.3).

## B — Building link review

Canoniek opvraagplan: huisnummers 240, 296 → bereikbaar: 0363100012127361, 0363100012137996 (2 van 15). Geen link is CONFIRMED of REJECTED. Een link ontstaat alleen via 'scripts/building_links.py record' door een mens, en vereist een canonieke BAG-snapshot (netwerk) met het pand als kandidaat.

### BUILDING LINK REVIEW (beslislijst — nog niets vastgelegd)

| BAG-pand | Adressen | DOC-005 | DOC-006 | Waarom in scope | Ambiguïteit |
|---|---|---|---|---|---|
| 0363100012070344 | Maldenhof 262, Maldenhof 264 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012071880 | Maldenhof 270, Maldenhof 272 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012078022 | Maldenhof 246, Maldenhof 248 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012091756 | Maldenhof 278, Maldenhof 280 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012091974 | Maldenhof 258, Maldenhof 260 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012102659 | Maldenhof 242, Maldenhof 244 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012107492 | Maldenhof 266, Maldenhof 268 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012121455 | Maldenhof 286, Maldenhof 288 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012127361 | Maldenhof 294, Maldenhof 296 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012134188 | Maldenhof 290, Maldenhof 292 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012137996 | Maldenhof 240 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 1/1 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE |
| 0363100012140664 | Maldenhof 250, Maldenhof 252 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012141419 | Maldenhof 254, Maldenhof 256 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012143647 | Maldenhof 282, Maldenhof 284 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |
| 0363100012144766 | Maldenhof 274, Maldenhof 276 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen | 2/2 VBO-punten liggen in de BAG-polygoon van dit pand | ADDRESS_RANGE; NOT_REACHABLE_VIA_CANONICAL_LOOKUP_PLAN; MULTIPLE_ADDRESSES_IN_PAND |

Oneven zijde (kandidaten uit de ALL_NUMBERS-hypothese; adressen niet in de main-snapshot; inschatting: buiten scope):

| BAG-pand | DOC-005 | DOC-006 |
|---|---|---|
| 0363100012061310 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012063561 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012064674 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012065912 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012077783 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012077984 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012078472 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012081986 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012083986 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012084256 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012087184 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012100140 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012102257 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012105151 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012108812 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012123643 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012125929 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012129433 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012135143 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012137009 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012138208 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012148993 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012151715 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012152265 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |
| 0363100012154610 | [ ] accepteren [ ] afwijzen | [ ] accepteren [ ] afwijzen |

## C — Historische hoeveelheden DOC-005 / DOC-006

- Observations: DOC-005 36, DOC-006 35; status {'REVIEW_REQUIRED': 3, 'SOURCE_REPORTED': 68}.
- Vergelijkbaarheid met 3D BAG: {'COMPARABLE_CANDIDATE': 4, 'NOT_A_MEASURED_QUANTITY': 7, 'NOT_COMPARABLE': 2, 'NO_3DBAG_SUBJECT': 58}.
- DOC-005 t.o.v. DOC-006: {'DIFFERS_IN_DOC-006': 3, 'IDENTICAL_IN_DOC-006': 31, 'NO_COUNTERPART_SAME_KEY': 2}.
- DOC-005 (MJOP 2026) en DOC-006 (MJOP 2023) zijn versies van hetzelfde MJOP (DREL-002, SAME_OBJECT; zelfde source cluster). Identieke waarden zijn GEEN twee onafhankelijke metingen. DOC-006 is daarnaast duplicate_source van DOC-014 (DREL-005; DOC-014 heeft geen quantity observations op main).
- **756,80 m²** (QO-DOC-005-EL-007, QO-DOC-005-EL-022, QO-DOC-006-EL-007, QO-DOC-006-EL-022): **NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY** — blijft bestaan als SOURCE_REPORTED-observation (niet verwijderd, niet gewijzigd).

| Observation | Code | Omschrijving | Locatie | Waarde | Eenh. | Status | Caveats | DOC-005↔006 | Vs 3D BAG | Labels |
|---|---|---|---|---|---|---|---|---|---|---|
| QO-DOC-005-EL-001 | 2110 | Gevelconstructie metselwerk | Alle gevels | 1631.90 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NOT_COMPARABLE | — |
| QO-DOC-005-EL-002 | 2110 | Loodslabben opgaand werk | Platte dak | 1.00 | m1 | REVIEW_REQUIRED | SAME_IN_RELATED_DOCUMENT, QUANTITY_ONE_IN_MEASURED_UNIT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-003 | 2110 | Dilatatie kitvoeg | Alle gevels | 10.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-004 | 2716 | Dakgoot zink | Alle gevels | 165.80 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-005 | 3120 | Betonband/latei | Alle gevels | 196.30 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-006 | 3120 | Raamdorpel gres/ijzerklinker | Alle gevels | 281.20 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-007 | 3120 | Kozijn buiten hout | Alle gevels | 756.80 | m2 | REVIEW_REQUIRED | SAME_IN_RELATED_DOCUMENT, AMBIGUOUS_QUANTITY_KIND_UNIT_MISMATCH | gelijk | NO_3DBAG_SUBJECT | NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY |
| QO-DOC-005-EL-008 | 3410 | Balustrade afdekking beton | Achtergevel - balkons | 59.10 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-009 | 3410 | Balustrade staal | Achtergevel - balkons | 20.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-010 | 3420 | Leuning staal | Voorgevel - trappenhuizen | 42.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-011 | 4111 | Gevelafwerking voegwerk platvol | Alle gevels | 1631.90 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-012 | 4112 | Gevelbekleding hout | Voorgevel - gevelbekleding | 332.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-013 | 4322 | Balkon afwerking betontegels | Achtergevel - balkons | 49.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-014 | 4511 | Plafondafwerking multiplex | Voorgevel - trappenhuizen | 85.70 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-015 | 4621 | Buitenschilderwerk gevelbekleding hout | Voorgevel - gevelbekleding | 332.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-016 | 4621 | Buitenschilderwerk balustrades staal | Achtergevel - balkons | 75.00 | m2 | SOURCE_REPORTED | — | — | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-017 | 4621 | Buitenschilderwerk leuning staal | Voorgevel - trappenhuizen | 61.00 | m1 | SOURCE_REPORTED | DIFFERS_FROM_RELATED_DOCUMENT | verschilt | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-018 | 4621 | Buitenschilderwerk metselwerk | Achtergevel - balkons | 34.90 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-019 | 4623 | Buitenschilderwerk (beton) trappen coating (polyurethaan) | Voorgevel - trappenhuizen | 80.00 | m2 | SOURCE_REPORTED | DIFFERS_FROM_RELATED_DOCUMENT | verschilt | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-020 | 4628 | Buitenschilderwerk afdekking beton | Achtergevel - balkons | 59.10 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-021 | 4628 | Buitenschilderwerk betonlateien | Alle gevels | 196.30 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-022 | 4631 | Buitenschilderwerk kozijn hout dekkend | Alle gevels | 756.80 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY |
| QO-DOC-005-EL-023 | 4645 | Buitenschilderwerk betonconstructie plafond | Voorgevel - trappenhuizen | 50.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-024 | 4645 | Binnenschilderwerk plafond hout (multiplex) dekkend | Voorgevel - trappenhuizen | 105.08 | m2 | SOURCE_REPORTED | DIFFERS_FROM_RELATED_DOCUMENT | verschilt | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-025 | 4711 | Dakbedekking APP | Platte dak | 425.80 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | COMPARABLE_CANDIDATE (HSM-ROOF_FLAT_AREA-4711-m2) | — |
| QO-DOC-005-EL-026 | 4711 | Dakrandafwerking zink | Alle gevels | 70.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-027 | 4712 | Dakpan beton | Hellend dak | 1485.60 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | COMPARABLE_CANDIDATE (HSM-ROOF_SLOPED_AREA-4712-m2) | — |
| QO-DOC-005-EL-028 | 5124 | Schoorsteen aluminium | Hellend dak | 14.00 | piece | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-029 | 5211 | Hemelwaterafvoer staal | Alle gevels | 41.40 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-030 | 5211 | Hemelwaterafvoer pvc | Alle gevels | 91.60 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-031 | 6311 | Elektra armaturen buiten LED | Voorgevel - trappenhuizen | 1.00 | piece | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-032 | 6710 | Valbeveiliging algemeen | Platte dak | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY, SAME_IN_RELATED_DOCUMENT | gelijk | NOT_A_MEASURED_QUANTITY | — |
| QO-DOC-005-EL-033 | 9041 | Betontegels | Terrein | 200.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-005-EL-034 | 9999 | Herinspectie / actualisatie MJOP | — | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY, SAME_IN_RELATED_DOCUMENT | gelijk | NOT_A_MEASURED_QUANTITY | — |
| QO-DOC-005-EL-035 | 9999 | Inspectie conditie dak | — | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY | — | NOT_A_MEASURED_QUANTITY | — |
| QO-DOC-005-EL-036 | 9999 | Bereikbaarheidskosten | — | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY, SAME_IN_RELATED_DOCUMENT | gelijk | NOT_A_MEASURED_QUANTITY | — |
| QO-DOC-006-EL-001 | 2110 | Gevelconstructie metselwerk | Alle gevels | 1631.90 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NOT_COMPARABLE | — |
| QO-DOC-006-EL-002 | 2110 | Loodslabben opgaand werk | Platte dak | 1.00 | m1 | REVIEW_REQUIRED | SAME_IN_RELATED_DOCUMENT, QUANTITY_ONE_IN_MEASURED_UNIT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-003 | 2110 | Dilatatie kitvoeg | Alle gevels | 10.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-004 | 2716 | Dakgoot zink | Alle gevels | 165.80 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-005 | 3120 | Betonband/latei | Alle gevels | 196.30 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-006 | 3120 | Raamdorpel gres/ijzerklinker | Alle gevels | 281.20 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-007 | 3120 | Kozijn buiten hout | Alle gevels | 756.80 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY |
| QO-DOC-006-EL-008 | 3410 | Balustrade afdekking beton | Achtergevel - balkons | 59.10 | m1 | SOURCE_REPORTED | BLOCK_ID_MISSING, SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-009 | 3410 | Balustrade staal | Achtergevel - balkons | 20.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-010 | 3420 | Leuning staal | Voorgevel - trappenhuizen | 42.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-011 | 4111 | Gevelafwerking voegwerk platvol | Alle gevels | 1631.90 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-012 | 4112 | Gevelbekleding hout | Voorgevel - gevelbekleding | 332.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-013 | 4322 | Balkon afwerking betontegels | Achtergevel - balkons | 49.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-014 | 4511 | Plafondafwerking multiplex | Voorgevel - trappenhuizen | 85.70 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-015 | 4621 | Buitenschilderwerk gevelbekleding hout | Voorgevel - gevelbekleding | 332.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-016 | 4621 | Buitenschilderwerk balustrades staal | Achtergevel - balkons | 20.00 | m1 | SOURCE_REPORTED | — | — | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-017 | 4621 | Buitenschilderwerk leuning staal | Voorgevel - trappenhuizen | 42.00 | m1 | SOURCE_REPORTED | DIFFERS_FROM_RELATED_DOCUMENT | verschilt | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-018 | 4621 | Buitenschilderwerk metselwerk | Achtergevel - balkons | 34.90 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-019 | 4623 | Buitenschilderwerk (beton) trappen coating (polyurethaan) | Voorgevel - trappenhuizen | 62.00 | m2 | SOURCE_REPORTED | DIFFERS_FROM_RELATED_DOCUMENT | verschilt | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-020 | 4628 | Buitenschilderwerk afdekking beton | Achtergevel - balkons | 59.10 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-021 | 4628 | Buitenschilderwerk betonlateien | Alle gevels | 196.30 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-022 | 4631 | Buitenschilderwerk kozijn hout dekkend | Alle gevels | 756.80 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY |
| QO-DOC-006-EL-023 | 4645 | Buitenschilderwerk betonconstructie plafond | Voorgevel - trappenhuizen | 50.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-024 | 4645 | Binnenschilderwerk plafond hout (multiplex) dekkend | Voorgevel - trappenhuizen | 85.70 | m2 | SOURCE_REPORTED | DIFFERS_FROM_RELATED_DOCUMENT | verschilt | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-025 | 4711 | Dakbedekking APP | Platte dak | 425.80 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | COMPARABLE_CANDIDATE (HSM-ROOF_FLAT_AREA-4711-m2) | — |
| QO-DOC-006-EL-026 | 4711 | Dakrandafwerking zink | Alle gevels | 70.00 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-027 | 4712 | Dakpan beton | Hellend dak | 1485.60 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | COMPARABLE_CANDIDATE (HSM-ROOF_SLOPED_AREA-4712-m2) | — |
| QO-DOC-006-EL-028 | 5124 | Schoorsteen aluminium | Hellend dak | 14.00 | piece | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-029 | 5211 | Hemelwaterafvoer staal | Alle gevels | 41.40 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-030 | 5211 | Hemelwaterafvoer pvc | Alle gevels | 91.60 | m1 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-031 | 6311 | Elektra armaturen buiten LED | Voorgevel - trappenhuizen | 1.00 | piece | SOURCE_REPORTED | BLOCK_ID_MISSING, SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-032 | 6710 | Valbeveiliging algemeen | Platte dak | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY, SAME_IN_RELATED_DOCUMENT | gelijk | NOT_A_MEASURED_QUANTITY | — |
| QO-DOC-006-EL-033 | 9041 | Betontegels | Terrein | 200.00 | m2 | SOURCE_REPORTED | SAME_IN_RELATED_DOCUMENT | gelijk | NO_3DBAG_SUBJECT | — |
| QO-DOC-006-EL-034 | 9999 | Herinspectie / actualisatie MJOP | — | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY, SAME_IN_RELATED_DOCUMENT | gelijk | NOT_A_MEASURED_QUANTITY | — |
| QO-DOC-006-EL-035 | 9999 | Bereikbaarheidskosten | — | 1.00 | lump_sum | SOURCE_REPORTED | LUMP_SUM_NOT_A_MEASURED_QUANTITY, SAME_IN_RELATED_DOCUMENT | gelijk | NOT_A_MEASURED_QUANTITY | — |

## D — 3D BAG-preview (geen evidence) en crosswalk review

PREVIEW van de bestaande 3D BAG-regels op de PoC-snapshot. GEEN evidence. Bron: 3D BAG-respons per pand (sha256 gecontroleerd), fetched_at niet vastgelegd op main.

| BAG-pand | Adressen | Plat dak m² | Hellend dak m² | Buitenmuur bruto m² |
|---|---|---|---|---|
| 0363100012070344 | Maldenhof 262, Maldenhof 264 | 7.61 | 99.91 | 100.84 |
| 0363100012071880 | Maldenhof 270, Maldenhof 272 | 8.8 | 101.57 | 132.64 |
| 0363100012078022 | Maldenhof 246, Maldenhof 248 | 16.05 | 91.19 | 99.61 |
| 0363100012091756 | Maldenhof 278, Maldenhof 280 | 8.27 | 101.68 | 99.06 |
| 0363100012091974 | Maldenhof 258, Maldenhof 260 | 14.56 | 88.42 | 98.09 |
| 0363100012102659 | Maldenhof 242, Maldenhof 244 | 10.55 | 99.32 | 150.33 |
| 0363100012107492 | Maldenhof 266, Maldenhof 268 | 15.99 | 90.34 | 103.5 |
| 0363100012121455 | Maldenhof 286, Maldenhof 288 | 18.04 | 89.12 | 101.13 |
| 0363100012127361 | Maldenhof 294, Maldenhof 296 | 10.33 | 98.56 | 197.42 |
| 0363100012134188 | Maldenhof 290, Maldenhof 292 | 23.56 | 87.94 | 116.45 |
| 0363100012137996 | Maldenhof 240 | 12.74 | 74.07 | 118.32 |
| 0363100012140664 | Maldenhof 250, Maldenhof 252 | 16.31 | 87.81 | 99.35 |
| 0363100012141419 | Maldenhof 254, Maldenhof 256 | 9.38 | 105.92 | 106.74 |
| 0363100012143647 | Maldenhof 282, Maldenhof 284 | 10.49 | 93.57 | 102.5 |
| 0363100012144766 | Maldenhof 274, Maldenhof 276 | 7.97 | 106.15 | 121.37 |
| **Σ 15 panden (informatief)** | | 190.65 | 1415.57 | 1747.35 |

Informatief. De bestaande pipeline telt bewust NIET op over panden (MULTI_PAND_NOT_SUMMED); een som als evidence vereist eerst een menselijk architectuurbesluit (zie E).

| Voorstel | Historisch | App-element | Onderwerp | Eenh. | Huidige status | Advies | Risico |
|---|---|---|---|---|---|---|---|
| HSM-ROOF_FLAT_AREA-4711-m2 | 4711 m2 (alle documenten) | — | ROOF_FLAT_AREA | m2 | PROPOSED | **NEEDS_REVIEW** | Maldenhof: 425,80 vs Σ 190,65 (factor ~2,2). Onbekend welke dakdelen 'Platte dak' omvat; de 3D BAG-som betreft alleen de 15 woonpanden. Verschil is een feit, geen fout van één bron. |
| XW-dak-plat-4711-m2 | 4711 m2 | dak-plat (27.1 'Dakbedekking plat dak') | ROOF_FLAT_AREA | m2 | PROPOSED | **SAFE_TO_VERIFY** | laag op element-niveau (zelfde bouwdeel); m1-rijen (dakrand) vallen buiten door de eenheid |
| HSM-ROOF_SLOPED_AREA-4712-m2 | 4712 m2 (alle documenten) | — | ROOF_SLOPED_AREA | m2 | PROPOSED | **NEEDS_REVIEW** | Generiek verifiëren brengt ook zink-/shinglerijen onder ROOF_SLOPED_AREA. Voor Maldenhof is de rij wel 'Dakpan beton / Hellend dak'. |
| XW-dak-hellend-4712-m2 | 4712 m2 | dak-hellend (27.2 'Dakbedekking hellend dak (pannen)') | ROOF_SLOPED_AREA | m2 | REVIEW_REQUIRED | **NEEDS_REVIEW** | zink/shingles onder 'pannen' |
| XW-gevel-metselwerk-2110-m2 | 2110 m2 | gevel-metselwerk (21.1) | — | m2 | REVIEW_REQUIRED | **NEEDS_REVIEW** | bruto ≠ netto; quantity_subject staat terecht op null (vocabulary not_mapped) |
| NO_MAPPING (kozijn/schilderwerk) | 3120 m2 'Kozijn buiten hout', 4631 m2 'Buitenschilderwerk kozijn hout dekkend' | schilderwerk-buiten (31.2) is UNRESOLVED (NOT_SAFE) | — | m2 | UNRESOLVED | **REJECT** | hoog: NOT_GROUND_TRUTH / NOT_VALIDATED_FOR_ACCURACY |
| NO_MAPPING (dakrand/goot/HWA) | 4711 m1 dakrand 70,00; 2716 m1 dakgoot 165,80; 5211 m1 HWA 41,40 + 91,60 | UNRESOLVED (APP_HAS_NO_EQUIVALENT_ELEMENT / UNIT_MISMATCH) | — | m1 | UNRESOLVED | **REJECT** | geen vergelijkbaar onderwerp |

Semantiek per voorstel:

- **HSM-ROOF_FLAT_AREA-4711-m2** — historisch: dakbedekking (APP/bitumen) in m2 zoals de adviseur noteerde, kan opstanden/overlappen bevatten; 3D BAG: b3_opp_dak_plat = plat dakoppervlak per pand volgens de attribuutnaam; de precieze definitie is in deze repo niet tegen de 3D BAG-documentatie gecontroleerd (USED_IN_MJOP_APP_NOT_VERIFIED_AGAINST_LIVE_API). Advies-reden: Code-semantiek is homogeen (dakbedekking m2), maar scope van 'plat dak' verschilt per document; verifiëren zet ALLE 4711-m2-rijen naast b3_opp_dak_plat. Acceptabel als 'naast elkaar tonen', niet als gelijkstelling.
- **XW-dak-plat-4711-m2** — element-identiteit: app 'Dakbedekking plat dak' ↔ intern 4711 'Dakbedekking (APP/bitumen)'; app rekent met b3_opp_dak_plat. Advies-reden: Koppelt alleen het bouwdeel; de hoeveelheden blijven naast elkaar staan en een mens kiest via quantity_resolution.
- **HSM-ROOF_SLOPED_AREA-4712-m2** — historisch: 4712 is een gemengde code; 3D BAG: b3_opp_dak_schuin = hellend vlak (niet de projectie). Advies-reden: Gemengde code; een mapping per omschrijving bestaat niet in v1.
- **XW-dak-hellend-4712-m2** — app 'pannen' ↔ gemengde code 4712. Advies-reden: zelfde reden als HSM-ROOF_SLOPED_AREA-4712-m2
- **XW-gevel-metselwerk-2110-m2** — historisch: metselwerk 'Alle gevels' 1631,90 m2 (netto of bruto onbekend); 3D BAG b3_opp_buitenmuur = bruto buitenmuur incl. openingen. Advies-reden: Alleen als code-koppeling zonder hoeveelheidsonderwerp; NIET als ROOF/OUTER_WALL-vergelijking gebruiken.
- **NO_MAPPING (kozijn/schilderwerk)** — kozijn-/schilderhoeveelheid, ongedefinieerd ('incl. draaiende delen'); geen 3D BAG-onderwerp. Advies-reden: Geen mapping maken naar een 3D BAG-onderwerp; de rijen blijven SOURCE_REPORTED.
- **NO_MAPPING (dakrand/goot/HWA)** — strekkende meters; 3D BAG heeft geen m1-onderwerp. Advies-reden: Niet in deze milestone; geen 3D BAG-regel voor m1.

## E — Eerste end-to-end demo

- Aanbevolen eerste onderwerp: **ROOF_FLAT_AREA (plat dak / dakbedekking, app-element dak-plat)** — Schoonste element-koppeling (4711 m2 is overal dakbedekking; XW-dak-plat-4711-m2 is element-identiteit) en de app rekent al met b3_opp_dak_plat. Het grote verschil is juist wat het demo moet tonen: twee bronnen naast elkaar, geen winnaar. ROOF_SLOPED_AREA ligt numeriek dichter bij elkaar, maar 4712 is een gemengde code.
- Status: **BLOCKED_BY_HUMAN_DECISIONS (B1–B3)**

Blokkades:

- **B1_NO_CANONICAL_SNAPSHOT** — Er is geen bag_snapshot_v1 voor DOC-005/DOC-006; de PoC-inputs voldoen niet aan het contract (zie A). → netwerktoegang tot api.pdok.nl en api.3dbag.nl + scripts/bag_snapshots.py fetch (expliciete toestemming nodig)
- **B2_LOOKUP_PLAN_RANGE_ENDPOINTS_ONLY** — Het opvraagplan vraagt alleen 240, 296 op; daarmee zijn 2 van 15 panden kandidaat (0363100012127361, 0363100012137996). 'record' weigert panden buiten de snapshot. → menselijk besluit: opvraagplan voor een bereik uitbreiden (bv. elk huisnummer van de bevestigde pariteit) — toolingwijziging, nog niet gedaan
- **B3_MULTI_PAND_BUILDING** — 15 panden. De evidence-builder telt niet op (MULTI_PAND_NOT_SUMMED): historische evidence krijgt building_id BAG:<15 ids>, 3D BAG-evidence BAG:<1 id> per pand; export_app_quantity_bundle neemt voor één building_id dus niet beide bronnen mee; MJOP-App bundleEntries weigert bundels met >1 pand. → ARCHITECTUURBESLUIT (CLAUDE.md: eerst melden): (a) VvE-gebouw = meerdere panden met een expliciete, menselijk goedgekeurde 3D BAG-somregel (GEOMETRY_DERIVED) en een app die meerdere panden per plan accepteert; of (b) per pand werken, waarbij de historische complexwaarde niet aan één pand gehangen kan worden
- **B4_ROOF_FLAT_SCOPE** — Historisch 4711 'Dakbedekking APP / Platte dak' = 425,80 m2 vs 3D BAG Σ b3_opp_dak_plat = 190.65 m2 (informatief). → geen correctie; beide naast elkaar tonen, een mens beslist in quantity_resolution

Menselijke besluiten (volgorde):

- 1. Building links: per pand per document accepteren/afwijzen (checklist B) — pas vast te leggen na B1/B2.
- 2. HSM-ROOF_FLAT_AREA-4711-m2: VERIFY of REJECT (advies NEEDS_REVIEW → als 'naast elkaar tonen' verantwoord).
- 3. XW-dak-plat-4711-m2: VERIFY of REJECT (advies SAFE_TO_VERIFY).
- 4. Architectuur B3: (a) meerdere panden per VvE-gebouw incl. 3D BAG-somregel + app-aanpassing, of (b) per pand.
- 5. Toestemming netwerk (B1) en opvraagplan voor bereiken (B2).

Historische evidence die daarna ontstaat (SOURCE_REPORTED):

- QO-DOC-005-EL-025: 425.80 m2 (p.7: "4711 Dakbedekking APP Platte dak 425,80m2 3") — DOC-005 en DOC-006 zelfde object: geen onafhankelijke bevestiging
- QO-DOC-006-EL-025: 425.80 m2 (p.7: "4711 Dakbedekking APP Platte dak 425,80m2 1") — DOC-005 en DOC-006 zelfde object: geen onafhankelijke bevestiging

3D BAG-evidence die daarna ontstaat (bag3d.roof_flat_area, DIRECT_MEASURED): per pand 0363100012070344 7.61 m²; 0363100012071880 8.8 m²; 0363100012078022 16.05 m²; 0363100012091756 8.27 m²; 0363100012091974 14.56 m²; 0363100012102659 10.55 m²; 0363100012107492 15.99 m²; 0363100012121455 18.04 m²; 0363100012127361 10.33 m²; 0363100012134188 23.56 m²; 0363100012137996 12.74 m²; 0363100012140664 16.31 m²; 0363100012141419 9.38 m²; 0363100012143647 10.49 m²; 0363100012144766 7.97 m². Complexsom 190.65 m² — alleen als evidence na besluit B3(a), dan als GEOMETRY_DERIVED met somregel.

Wat MJOP-App daarna conceptueel zou tonen:

> **Dakbedekking plat dak (dak-plat)**  
> Uit oud MJOP: 425,80 m² — DOC-005 (2026) en DOC-006 (2023), elementenoverzicht p.7 — SOURCE_REPORTED; zelfde waarde in beide versies, geen onafhankelijke bevestiging  
> 3D BAG: 190.65 m² over 15 panden (pas na besluit B3a) of per pand (B3b) — b3_opp_dak_plat — DIRECT_MEASURED per pand  
> Status: Nog niet door gebruiker bevestigd (geen quantity_resolution)  
> geen gemiddelde, geen score, geen automatische keuze; effectieve waarde pas via een ACTIVE quantity_resolution

MJOP-App: twandijkmans-afk/MJOP-App @ fbe09d8 (claude/mjop-live-implementation-smz60g); Quantity Sources v1 aanwezig (PR #2, merge fbe09d8). src/quantity.js bundleEntries: een bundel met bag_pand_ids.length !== 1 wordt geweigerd ('De bundel gaat over N panden; de app werkt per pand.'); het pand moet gelijk zijn aan het pand van het plan.
