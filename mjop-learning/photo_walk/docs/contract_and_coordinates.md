# Capture-contract en coördinatenstelsels — `photo_walk_capture_v1`

Schema: `photo_walk/schemas/photo_walk_capture_v1.schema.json` (JSON Schema draft-07, **gesloten**: `additionalProperties: false`).
Validatie: `python -m photo_walk_core.validate <bestand.json>` (ook voor exports van de iPhone-app).
Versiebeleid: `contract_version` is `1.x.y`; een wijziging die bestaande velden hernoemt/verwijdert is `2.0.0` en een nieuw schemabestand. Bestaande v1-/v2-contracten van `mjop-learning` zijn niet aangeraakt.

## Stelsels en eenheden (verwar ze niet)

| Stelsel | Definitie | Eenheid |
|---|---|---|
| **PIXEL** | `u` naar rechts, `v` naar beneden; oorsprong = linkerbovenhoek van de linkerbovenpixel (pixelmiddens op +0,5). Intrinsics `fx, fy, cx, cy` zijn in pixels van **hetzelfde** beeld (`width` x `height`). Beeld = native cameraoriëntatie (op iPhone landscape), **niet** de portretweergave. | px |
| **CAMERA** | OpenCV: `x` rechts, `y` omlaag, `z` vooruit (optische as). | m (als schaal metrisch is) |
| **WERELD** | rechtshandig, `Y` omhoog (zwaartekracht-uitgelijnd), oorsprong = start van de AR-sessie. | m |
| **POSE** | `camera_to_world`, 4x4 rij-hoofdvolgorde als 16 getallen: `x_wereld = R·x_camera + t`. | m |
| **DIEPTE** | `depth_z` = afstand **langs de optische as** (niet de straallengte). `0`/`NaN`/`inf` = ongeldig. De dieptekaart heeft een lagere resolutie dan het beeld; pixel `(j,i)` hoort bij beeldpixel `((j+0,5)·W/Wd, (i+0,5)·H/Hd)`. | m |
| **VLAK** | `n·x = d`, `|n| = 1`; vlakcoördinaten `(u,v)` in meter via `plane_basis` (`e_v` = omhoog geprojecteerd op het vlak). | m |

ARKit/ARCore leveren een camera met `y` omhoog en `-z` vooruit; de adapters vermenigvuldigen de rotatie met `diag(1,-1,-1)` (zie `arkit_adapter.md`, `android.md`).
Niet gemodelleerd: lensvervorming (pinhole). Gevolg: aan de beeldranden kunnen hoeken enkele pixels afwijken; de onzekerheid dekt dat **niet** aantoonbaar.

## Sessievelden

`session_id, building_id, facade_id, platform (IOS|ANDROID|SIMULATION), device_model, data_origin (SIMULATION|REAL_SENSOR),
validation_level (BUILT|COMPILED|SIMULATED|REAL_SENSOR_UNVALIDATED|DEVICE_VALIDATED), sensor_capabilities, coordinate_system,
camera_intrinsics[], camera_poses[], capture_timestamp, image_refs[], depth_refs[], tracking_quality[], measurement_mode, scale_method,
scale_evidence[], measurement_method_version, processing_version, thresholds, references[], observations[], objects[], coverage, summary,
scan_label, privacy, invariants`.

* `image_refs` / `depth_refs` zijn **opake `local://`-verwijzingen**; het schema weigert paden en bevat nooit mediadata.
* `scale_method`: `LIDAR_DEPTH_PLANE | AR_TRIANGULATION_VIO | REFERENCE_DISTANCE | MIXED | NONE`. `scale_evidence` bevat per object het bewijs (vlakfit-statistiek, referentie-id, wel/niet geverifieerd).
* `thresholds` bevat alle gate-drempels met `threshold_status: PROVISIONAL_UNVALIDATED`.
* `invariants` is vastgezet (`const`): `is_final=false`, `human_decision_registered=false`, `approvals_simulated=false`, geen kosten/kengetal/prijs, `external_vision_calls=0`, `images_uploaded=false`. Een record dat dit overtreedt is ongeldig.

## Kozijn (`objects[]`)

`provisional_object_id, observation_refs, frame_type (FRAME|FRAME_WITH_DOOR|DOOR|UNKNOWN), parts, detection_method, corner_sources, corner_order,
outer_corner_coordinates (WORLD_M_Y_UP, m), corner_pixels (px; punten, originele punten, revisies), outer_width_m, outer_height_m, gross_area_m2,
gross_area_m2_presented, dimension_status, measurement_uncertainty, measurement_source, review_required, quality_flags, next_steps_nl,
quantity_layer (=PROVISIONAL), approval_state (=PENDING_HUMAN_APPROVAL)`.

* Maten zijn **Decimal-strings** (zoals Bruto Quantity Model v2): breedte/hoogte op millimeter (half-up), `gross_area_m2` = exact product van de getoonde maten, `gross_area_m2_presented` op 2 decimalen.
* `UNKNOWN` ⇒ `outer_*`, `gross_area_m2` en `measurement_uncertainty` zijn `null` (schema-afgedwongen) en `review_required` is `true`.
* `corner_order`: `TOP_LEFT, TOP_RIGHT, BOTTOM_RIGHT, BOTTOM_LEFT` (omloopvolgorde; breedte/hoogte worden bepaald met de wereld-omhoog-as, dus een 90° gedraaide startpositie verwisselt de maten niet; verwisselde hoeken = vlinderdas ⇒ `CORNER_ORDER_INVALID`).
* `parts` (vaste/draaiende delen) is informatief en heeft **geen** invloed op het oppervlak.

## Statussen en relatie met Bruto Quantity Model v2

| `dimension_status` | betekenis hier |
|---|---|
| `MEASURED` | niveau A, ≥ 2 onderling consistente standpunten, geen verlagende waarschuwing (glas, hoekdiepte, enkel standpunt, …) |
| `DERIVED` | uit een referentieafstand (C) of uit AR-triangulatie waarvan de schaal door een referentie is bevestigd |
| `ESTIMATED` | metrisch berekend maar niet volledig onderbouwd: één standpunt, onbevestigde AR-schaal, of adviserende waarschuwingen |
| `UNKNOWN` | geen betrouwbare waarde; waarnemingen blijven bewaard |

Deze statussen zijn **niet** dezelfde als `dimension_status` in `bruto_dimension_v2` (daar betekent `MEASURED` een menselijke meting). Er worden daarom **geen** v2-objecten aangemaakt of status-mappingen geforceerd: een sensorresultaat is een *voorstel* dat een mens in een latere fase als `bruto_observation_v2`/`bruto_quantity_object_v2` kan overnemen (bron: eigen meting met `authentication: NONE_SELF_ASSERTED`). De rekenregel is identiek aan `GROSS_FRAME_AREA_OUTER_V2` (breedte x hoogte, glas niet afgetrokken, delen niet apart) en wordt in een test tegen `bruto_quantity_core.gross_area_exact` vergeleken.

## Kwaliteitscodes (`quality_flags`)

| Code | Ernst | Instructie aan de gebruiker |
|---|---|---|
| `BEHIND_CAMERA` | BLOCKING | Getrianguleerd punt ligt achter de camera; controleer de camerapose en hoekselectie. |
| `CORNERS_NOT_COPLANAR` | BLOCKING | De getrianguleerde hoeken liggen niet in een vlak. Controleer de hoekselectie. |
| `CORNERS_NOT_ON_PLANE` | BLOCKING | Een hoekstraal raakt het gevelvlak niet. Controleer de hoekselectie. |
| `CORNER_ORDER_INVALID` | BLOCKING | De vier hoeken vormen geen simpele vierhoek (verwisselde of dubbele hoeken). Tik de hoeken rond: linksboven, rechtsboven, rechtsonder, linksonder. |
| `CORNER_OUTSIDE_IMAGE` | BLOCKING | Een hoek ligt buiten het beeld. Sta verder weg zodat het hele kozijn in beeld is. |
| `DEPTH_COVERAGE_LOW` | BLOCKING | Te weinig geldige dieptepunten rond het kozijn. Ga dichterbij (binnen ca. 5 m), vermijd direct tegenlicht en scan de gevel rond het kozijn rustig. |
| `DEPTH_RANGE_EXCEEDED` | BLOCKING | Dieptepunten liggen buiten het bereik van de sensor. Ga dichterbij staan. |
| `DIMENSION_OUT_OF_RANGE` | BLOCKING | Berekende maat valt buiten 0,10-10 m; controleer hoeken en schaal. |
| `INCONSISTENT_VIEWS` | BLOCKING | De standpunten leveren geen consistente hoekposities (hoge herprojectiefout). Controleer de hoekselectie in beide beelden. |
| `LOW_PARALLAX` | BLOCKING | Te weinig standpuntverschil voor triangulatie. Loop 1-2 m zijwaarts en maak een tweede opname van hetzelfde kozijn. |
| `MIXED_FACADE_DEPTH` | BLOCKING | Het gevelvlak rond het kozijn is niet vlak (verspringingen, balkon, begroeiing). Kies een standpunt met vrij zicht op de omringende gevel of voer een referentiemaat in. |
| `NO_DEPTH` | BLOCKING | Geen dieptebeeld voor dit standpunt; gebruik een tweede standpunt (niveau B) of voer een referentiemaat in (niveau C). |
| `NO_METRIC_SCALE` | BLOCKING | Geen betrouwbare metrische schaal. Voer een referentieafstand in tussen twee punten op het kozijnvlak. |
| `OBLIQUE_ANGLE` | BLOCKING | Te schuine kijkhoek op het kozijn. Sta meer recht voor het kozijn. |
| `PLANE_NOISY` | BLOCKING | Het gevelvlak is te onrustig voor een betrouwbare vlakfit. Herhaal vanaf een ander standpunt. |
| `RECT_ASSUMPTION_VIOLATED` | BLOCKING | De hoeken zijn niet consistent met een rechthoek en de cameralenzen. Corrigeer de hoeken. |
| `REFERENCE_INVALID` | BLOCKING | De referentie is ongeldig (afstand <= 0 of punten vallen samen). |
| `REFERENCE_PLANE_MISMATCH` | BLOCKING | De referentie ligt niet op hetzelfde vlak als het kozijn. Geef een nieuwe referentie op het gevelvlak van dit kozijn. |
| `TRACKING_LOST` | BLOCKING | AR-tracking was niet 'normal' tijdens dit beeld. Beweeg langzaam, richt op een gevel met textuur en herhaal de opname. |
| `VIEWS_INCONSISTENT` | BLOCKING | Metingen vanuit verschillende standpunten komen niet overeen. Herhaal de opname; alle waarnemingen zijn bewaard. |
| `WRONG_CORNER_SELECTION` | BLOCKING | De gekozen hoeken vormen geen rechthoek op het gevelvlak. Corrigeer de hoeken (buitenhoeken van het kozijn). |
| `AMBIGUOUS_ASSOCIATION` | ADVISORY | Waarneming past bij meerdere kozijnen; handmatig koppelen. |
| `ASSOCIATION_UNVERIFIED` | ADVISORY | Niet vastgesteld of dit kozijn ook op andere foto's staat; dubbeltelling is niet uitgesloten. |
| `COPLANARITY_ASSUMED` | ADVISORY | Het kozijn is op de referentieschaal gezet onder de aanname dat het in hetzelfde vlak ligt. Controleer dit. |
| `CORNER_DEPTH_MISMATCH` | ADVISORY | Diepte op een hoek wijkt af van het gevelvlak (verdiept kozijn of verkeerd gekozen hoek). Controleer de hoeken. |
| `FACADE_NOT_VERTICAL` | ADVISORY | Het vlak is niet verticaal; controleer of het een gevel is. |
| `GLASS_DEPTH_UNRELIABLE` | ADVISORY | Diepte in het glas is onbetrouwbaar (reflectie of ontbrekende data); alleen de omringende gevel is gebruikt. Controleer de hoeken visueel. |
| `HUMAN_CORRECTED_CORNERS` | ADVISORY | Hoeken zijn door een mens gecorrigeerd; herberekend zonder brondata te overschrijven. |
| `MANUAL_CORNERS` | ADVISORY | Hoeken zijn handmatig geselecteerd (semi-automatisch). |
| `METRIC_SCALE_UNVERIFIED` | ADVISORY | De metrische schaal komt uit AR-tracking en is niet geverifieerd. Voer een referentiemaat in om de schaal te controleren. |
| `OBSTRUCTION_REPORTED` | ADVISORY | Gebruiker meldt begroeiing of obstakel voor het kozijn; hoeken kunnen onjuist zijn. |
| `REFERENCE_UNCERTAINTY_NOT_PROVIDED` | ADVISORY | Bij de referentie is geen eigen onzekerheid opgegeven; die is niet in de onzekerheid meegenomen. |
| `SINGLE_VIEWPOINT` | ADVISORY | Slechts een standpunt; maak een tweede opname vanaf een ander standpunt voor een consistentiecontrole. |
| `VIO_SCALE_MISMATCH` | ADVISORY | De AR-schaal wijkt af van de ingevoerde referentie; de referentie is leidend gebruikt. |

`BLOCKING` ⇒ er komt uit dat pad geen metrische waarde; `ADVISORY` ⇒ waarde zichtbaar maar `review_required` en nooit `MEASURED` (voor de lijst in `DOWNGRADING`).
