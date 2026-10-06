# Frame Inventory Foundation v1 + Vector Drawing Reader PoC v1

Status real-world PoC: **REAL_WORLD_POC_BLOCKED_NO_DRAWING**. De foundation (model, semantiek, repeat-contract, presence-besluiten) is gebouwd; er is geen echte vector-tekening, dus geen real-world kozijnextractie en geen accuracy-claim.

## Presence-besluiten (EXTERIOR_FRAME)

| Besluit | Gebouw | Besluit | Reviewer | Evidence |
|---|---|---|---|---|
| CPD-00001 | Maldenhof 240-296 (DOC-005 + DOC-006) | EXTERIOR_FRAME = PRESENT | user-approved (human) | CPE-1887622943b3d8bb, CPE-747f24497e7b23d4 |
| CPD-00002 | Meppelweg (DOC-012) | EXTERIOR_FRAME = PRESENT | user-approved (human) | CPE-90e3d60a9a12689c |

Het besluit zegt alleen PRESENT. `material_as_reported = hout` blijft evidence-detail. Geen uitspraak over aantal, oppervlak, afmetingen, ramen/deuren of schilderoppervlak.

## A. Frame data model

- Component types: EXTERIOR_FRAME, EXTERIOR_WINDOW, EXTERIOR_DOOR (frame, raam en deur zijn gescheiden)
- facade_side: FRONT, REAR, LEFT, RIGHT, COURTYARD, UNKNOWN; subtype: FIXED_WINDOW, TURN_TILT, CASEMENT, SLIDING, EXTERIOR_DOOR, FRENCH_DOOR, WINDOW_DOOR_COMBINATION, OTHER, UNKNOWN
- material: WOOD, PVC, ALUMINIUM, STEEL, OTHER, UNKNOWN; dimension_basis: OPENING, FRAME_OUTER, DRAWING_DIMENSION, UNKNOWN; status: PROPOSED, REVIEW_REQUIRED, CONFIRMED, USER_OVERRIDDEN
- Instance: frame_instance_id, building_id, bag_pand_id, component_type, facade_side, storey, subtype, material, count, optioneel width_m/height_m/dimension_basis, optioneel opening_area_m2/frame_outer_area_m2, source_refs, provenance, status. Maten als Decimal-strings.
- Er bestaat bewust GEEN `painting_area_m2`: schilderoppervlak wordt nooit automatisch afgeleid.
- Groep (`frame_group`): representative_instance + count + applies_to + source_refs; één tekeningsymbool meerdere keren alleen met per-occurrence bewijs; geen gebouwbrede multiplier zonder menselijk besluit.
- Store: 0 instances, 0 groepen (niets verzonnen).

## B. Quantity semantics

Zeven aparte concepten, nooit automatisch gelijk:

| Concept | Eenheid | Afleiding |
|---|---|---|
| FRAME_COUNT | count | SUM_OF_CONFIRMED_INSTANCE_COUNTS |
| WINDOW_COUNT | count | SUM_OF_CONFIRMED_INSTANCE_COUNTS |
| EXTERIOR_DOOR_COUNT | count | SUM_OF_CONFIRMED_INSTANCE_COUNTS |
| WINDOW_OPENING_AREA | m2 | COUNT_X_WIDTH_X_HEIGHT_ONLY_IF_DIMENSION_BASIS_OPENING_AND_COUNT_CONFIRMED |
| FRAME_OUTER_AREA | m2 | COUNT_X_WIDTH_X_HEIGHT_ONLY_IF_DIMENSION_BASIS_FRAME_OUTER_AND_COUNT_CONFIRMED |
| FRAME_PAINTING_AREA | m2 | NEVER_AUTOMATIC |
| GLASS_AREA | m2 | NEVER_AUTOMATIC |

Voorbeeld: 8 ramen x 1,20 x 1,50 mag alleen WINDOW_OPENING_AREA = 14,40 m2 opleveren als de maten over de opening gaan EN count = 8 bevestigd is; nooit automatisch FRAME_PAINTING_AREA = 14,40.

Historische context: Maldenhof 'Kozijn buiten hout' 756,80 m2 blijft uitsluitend HISTORICAL_REPORTED_QUANTITY_CONTEXT; niet FRAME_COUNT, WINDOW_COUNT, EXTERIOR_DOOR_COUNT, WINDOW_OPENING_AREA, FRAME_OUTER_AREA, FRAME_PAINTING_AREA of GLASS_AREA. Geen ratio, geen conversiefactor, geen accuracy-claim.

## C. Repeat groups

- Contract: repeat_group_id, building_id, component_type, representative_pand_id, applies_to_pand_ids, transformation (SAME/MIRRORED), evidence_refs, decision_ref, status (REPEAT_CANDIDATE/ACTIVE/REJECTED).
- ACTIVE (bruikbaar) uitsluitend na een menselijk USER_CONFIRMED_REPEAT; vision/tekening stelt alleen een REPEAT_CANDIDATE voor. Geen automatische '13 middenpanden lijken hetzelfde dus x13'.
- Store: 0 groepen.

## D. Source audit

Zie `reports/drawing/vector_drawing_source_audit_v1.md`. 13 unieke PDF's (16 paden), 323 pagina's: {'VECTOR_DRAWING_CANDIDATE': 0, 'RASTER_DRAWING_CANDIDATE': 0, 'MJOP_REPORT_ONLY': 13, 'NO_DRAWING_FOUND': 0}. Pagina's met een sterk tekeninglabel: 0.

## E. Gekozen PDF/pagina

Geen: er is geen VECTOR_DRAWING_CANDIDATE. Een MJOP-tabel is niet als tekening behandeld.

## F. Vector primitives

De generieke reader (`scripts/vector_drawing_reader.py`: lines, rectangles, curves, text spans, coordinates, paginamaten, optional-content-aanwezigheid, dimension texts, provenance met source, sha256, pagina, bbox en extractiemethode/versie) is unit-getest op een kleine, duidelijk gemarkeerde synthetische TEST FIXTURE. Er zijn geen real-world observaties (`data/drawing_observations/` bevat geen tekeningdata).

## G. Scale evidence

Real-world: geen. Regels: maatlijn (voorkeur) of expliciete tekeningschaal + standaard papierformaat + consistente geometrie; anders dimensions = UNKNOWN. Nooit punten/pixels naar meters zonder bewijs.

## H. Opening candidates

Real-world: niet mogelijk, 0 gerapporteerd. De candidate-logica (alleen op een FACADE_ELEVATION; REVIEW_REQUIRED; gevelvlak + herhaling/label/maatvoering; SAME_SYMBOL_CANDIDATE != hetzelfde component) is alleen op de fixture getest.

## I. Real-world beperkingen

- geen enkele bouwtekening in de repo; alleen MJOP-rapporten (tabellen, grafieken, foto's)
- reader gevalideerd op synthetische fixture; nooit op een echte tekening
- maatlijn-detectie veronderstelt losse numerieke tekst (mm) bij een rechte lijn; echte tekeningen met pijlen/ticks/tekst-als-paden kunnen aanpassing vragen
- geen OCR; tekst-als-afbeelding of tekst-als-paden wordt niet gelezen
- geen accuracy-claim mogelijk

## J. Maldenhof historical cross-check

Classificatie: **NOT_COMPARABLE**. Drawing-derived: count, opening area, frame outer area = geen (geen tekening). Historisch: 756,80 m2 'Kozijn buiten hout' (DOC-005 en DOC-006). Geen percentage accuracy.

Publieke straatbeelden (eerdere Maldenhof-PoC: confirmed exterior facade coverage ca. 41%, achtergevel ca. 26%, geen pand >= 80% voor+achter) zijn geen ground truth en geen volledige frame-inventaris; ze zijn niet met tekeningmetingen gemengd.

## Legacy appartementfactor en bronprioriteit

- `KOZ_FACTOREN = [1, 0.25, 0.125, 0.125]` blijft bestaan als **LEGACY_ESTIMATE_FALLBACK**: alleen gebruiken als er geen confirmed/manual/drawing-based frame inventory is. App-code is niet gewijzigd.
- Toekomstige prioriteit: USER_CONFIRMED_MANUAL > DRAWING_MEASURED > USER_ASSISTED_PHOTO > SOURCE_REPORTED_HISTORICAL > LEGACY_ESTIMATE_FALLBACK. Alleen binnen EXACT hetzelfde quantity-subject (zelfde concept, zelfde gebouw/scope). Geen automatische winnaar tussen verschillende subjects.

## K. Volgende menselijke besluiten

- welke tekening(en)/gebouw voor de eerste echte PoC (Maldenhof of Meppelweg)
- goedkeuring frame-instance-model (granulariteit: pand x gevel x verdieping x subtype)
- bevestiging dat de zeven quantity-concepten gescheiden blijven
- repeat-policy: alleen na USER_CONFIRMED_REPEAT per componenttype
- legacy kozijnfactor: zichtbare ESTIMATED-fallback behouden / later verwijderen
- overige presence-besluiten (26 openstaand) blijven bij de gebruiker

## L. Exact volgende input

Nodig: **originele vector-PDF (geen scan/foto/screenshot) van een gevelaanzicht met zichtbare maatvoering**.

- voorgevel en achtergevel (liefst beide)
- maatlijnen/maatvoering zichtbaar of expliciete schaal (1:50/1:100) op een standaard papierformaat (A0-A3), niet 'passend' geschaald
- liefst dezelfde VvE: Maldenhof 240-296 of Meppelweg (DOC-012)
- ook welkom: kozijnstaat (kozijnenstaat) als PDF met tekst-laag
