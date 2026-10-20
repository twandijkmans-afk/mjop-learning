# LiDAR-meting v2 (niveau A): oorzaken, aanpak, tests en wat nog fysiek moet

Status: **voorlopig en NIET gevalideerd op echte gevels.** Alles wat hieronder als "getest" staat, is getest op *gesimuleerde* diepte. Echte iPhone-LiDAR (ruis, randvervaging, uitlijning diepte↔beeld, glas/baksteen) is nog niet gemeten; alle drempels zijn `PROVISIONAL_UNVALIDATED` en bedoeld om met de **meetdiagnose-exports** van een echt toestel gekalibreerd te worden.

## 1. Waarom de eerste versie op een echte gevel faalde

Bevindingen van de eerste fysieke test: foto en kaders werken, maar binnen (kozijn) `MIXED_FACADE_DEPTH`, buiten geen betrouwbare maat; alleen een geschatte referentie van ~1 m gaf getallen.

Gereproduceerd/afgeleid uit de code (`LevelA.swift`, `PlaneFit.swift`, `Quality.swift`, `levels.py`):

| # | Oorzaak (v1) | Status |
|---|---|---|
| 1 | Eén RANSAC-vlak door een brede ring (1,08–1,8× kader) met vaste drempel 2 cm en eis ≥ 60 % inliers. Een echte ring bevat wand **en** dagkanten, kozijnprofiel, vensterbank, goot/regenpijp, reliëf. | gereproduceerd (synthetisch) |
| 2 | Vaste inlierdrempel (2 cm) en rms-limiet (2 cm) onafhankelijk van afstand; LiDAR-ruis groeit met de afstand (σ ≈ 4 mm + 4 mm/m, provisional). Op 3–4 m valt een correcte wand dus al snel buiten de drempel. | plausibel; vereist fysieke bevestiging |
| 3 | Hoekstralen werden op het **wandvlak** gesneden. Bij een terugliggend kozijn ligt het buitenkozijn 3–12 cm achter de wand: de maat is dan systematisch 3–8 % **te klein**, zonder waarschuwing (stille, plausibele fout). | gereproduceerd (legacy: 39 van 75 geaccepteerde sweep-scènes > 2 % fout) |
| 4 | Hoekdiepte-controle gebruikte de mediaan van 3×3 pixels *op* de hoek. Een hoek ligt precies op een diepte-sprong (wand ↔ kozijn): de mediaan is willekeurig en gaf `MIXED_FACADE_DEPTH` bij ≥ 3 hoeken (> 25 cm afwijking). Een correct terugliggend kozijn werd zo geweigerd. | gereproduceerd |
| 5 | Eén foutcode (`MIXED_FACADE_DEPTH`) voor oorzaken met verschillende remedies (verspringende gevel, ruwe muur, te weinig dekking, terugligging, verkeerde hoeken). | opgelost: aparte codes |
| 6 | Eén dieptekader: geen onafhankelijke bevestiging, geen manier om terugligging uit parallax/meerdere standpunten te verifiëren. | opgelost: rolling buffer |
| 7 | Een door de gebruiker **geschatte** referentie (≈ 1 m) gaf dezelfde status (`DERIVED`) als een gemeten referentie. | opgelost: `USER_ESTIMATE` ⇒ `ESTIMATED` + `REFERENCE_USER_ESTIMATE` |
| 8 | Diepte↔beeld-uitlijning, camera-intrinsics van het dieptebeeld en de zone van de dieptekaart (256×192 over hetzelfde 4:3-beeld) worden verondersteld te kloppen (ARKit levert `capturedImage`, intrinsics en diepte in dezelfde sensor-oriëntatie). | **niet bewezen**; diagnose bewaart de kantprofielen; zie §7 |

Of het kader de **buitenrand** van het kozijn omvat wordt nu getoetst (`QUAD_LARGER_THAN_OPENING` / `QUAD_INSIDE_OPENING`). Digitale zoom raakt pixels, intrinsics en diepte niet (ongewijzigd, `ZoomTests`).

## 2. Nieuwe aanpak (kort)

Referentie-implementatie: `python/photo_walk_core/depth_plane.py` + `levels.measure_depth_view`; Swift-port: `DepthPlane.swift` + `LevelA.swift`. Pariteit op ruisvrije scènes in `parity_cases.json` (`level_a_v2`).

1. **Gebieden per zijde** (boven/rechts/onder/links) in het capture-beeld: *ring* (1,06–1,6× kader) = wand, *binnenband* (0,88–0,985×) = kozijnprofiel, *glas* (< 0,70×) = nooit gebruikt voor de maat.
2. **Afstandsafhankelijke ruisdrempel**: σ(z) = 4 mm + 4 mm·z; inlierdrempel = 2,5σ + 12 mm (baksteenreliëf).
3. **Meerdere kandidaatvlakken** in de ring (sequentiële RANSAC, ≤ 3) met classificatie: `FACADE` (verticaal, naar de camera gericht), `REVEAL_OR_LEDGE`, `PARALLEL_STEP`. Weigeringen met een eigen code:
   `NO_FACADE_PLANE`, `AMBIGUOUS_FACADE_PLANES` (twee grote parallelle vlakken op verschillende diepte), `FACADE_NOT_PLANAR` (te ruw / te weinig steun / robuuste ruis te hoog), `FACADE_ONE_SIDED` (wand maar aan 1–2 aangrenzende zijden gezien), `DEPTH_COVERAGE_LOW`, `DEPTH_RANGE_EXCEEDED`.
4. **Kozijnvlak ≠ wandvlak.** De terugligging van het kozijn t.o.v. de wand volgt uit de binnenband, per zijde (dichtstbijzijnde cluster met ≥ 35 % van het grootste cluster), en geldt alleen bij groepsconsensus van ≥ 2 zijden (`FLUSH`/`RECESSED`/`PROTRUDING`). Zo niet: `FRAME_PLANE_UNDETERMINED` / `FRAME_PLANE_INCONSISTENT` (geen maat; alleen een *indicatieve* maat in de diagnose). Terugval op hoekdieptes is zwakker en altijd adviserend gemeld (`FRAME_OFFSET_FROM_CORNER_DEPTH`).
5. **Hoekstralen** worden op dat kozijnvlak gesneden (intrinsics + pose); bruto m² = buitenbreedte × buitenhoogte (incl. glas en draaiende delen).
6. **Onafhankelijke hoekcontrole**: in een 5×5-venster rond elke hoek moet *een* dieptewaarde binnen 2σ+2 cm van het verwachte vlak liggen (gemengde waarden op een sprong zijn normaal). Geen enkele ⇒ hoek tegenstrijdig; ≥ 3 ⇒ `CORNERS_OFF_PLANE`.
7. **Kaderomvang**: loodrecht op de kaderranden worden diepte-sprongen gevolgd; sprongen ver binnen het kader ⇒ kader te groot; sprongen naar glas/profiel direct buiten het kader ⇒ kader te klein.
8. **Meerdere dieptekaders** (§3). Resultaat met ≥ 2 onafhankelijke kaders krijgt `scale_method = LIDAR_DEPTH_MULTI_FRAME`.
9. **Onzekerheid**: Monte Carlo (hoekpixels, wandvlak offset+kanteling, kozijnoffset). Modelgebaseerd, niet gevalideerd.

Niet versoepeld: er is geen enkele bestaande drempel losgelaten om meer metingen te laten slagen. Nieuwe controles zijn **toegevoegd** (kozijnvlak, hoekcontrole, kaderomvang, frame-consistentie); afstandsafhankelijke drempels vervangen vaste waarden waar de oude waarde bij echte ruis niet te halen was.

## 3. Meerdere dieptekaders (rolling buffer)

* `DepthRingBuffer` (app) bewaart max. 14 `sceneDepth`-kaders van de laatste 1,8 s (≤ ~12 Hz) met pose, tracking, tijdstempel, geldige-puntenaandeel. Op de foto-knop gaan de ≤ 8 kaders met de grootste baseline mee als `supportDepths` in het keyframe (lokaal bewaard).
* `smoothedSceneDepth` van het hoofdframe wordt alleen als **kruiscontrole** bewaard (gecorreleerd; telt nooit als extra bewijs).
* De kern gebruikt een ondersteunend kader alleen als: tracking `NORMAL`, diepte aanwezig, en ≥ 2 cm verplaatsing **of** ≥ 1,5° rotatie t.o.v. alle al gekozen kaders (max. 5). Bijna identieke kaders (zelfde standpunt) zijn gecorreleerd en tellen niet (test: `spacing = 0`).
* Alle punten worden via pose + intrinsics naar één wereldstelsel gebracht en in de gebieden van het hoofdbeeld ingedeeld; per kader wordt daarnaast zelfstandig vlak + kozijnvlak + maat bepaald. Wijkt een bruikbaar kader af (> 3 % + 1 cm, of normaal > 4°) ⇒ `FRAMES_INCONSISTENT`, geen maat (test: kader met 12 % diepte-schaalfout).
* Hint zolang er te weinig onafhankelijke kaders zijn: *"Beweeg je telefoon langzaam iets naar links en rechts voor een betere meting."* (live in de cameraweergave, na de foto, en in het diagnosescherm).
* Status: `MEASURED` vereist ≥ 2 onafhankelijke standpunten/kaders **en** geen downgrading-adviezen; één kader ⇒ `ESTIMATED` (+ `SINGLE_VIEWPOINT`).

## 4. Meetdiagnose

* Scherm "Meetdiagnose" per kozijn (vanuit het kader-detail): dieptepunten (ring/band/glas, dekking %), frames (gebruikt/verworpen, baseline, per-frame maat), vlakken (gekozen + andere kandidaten, inlier %, rms, normaal), kozijnvlak (modus, terugligging cm, per zijde), afstand, tracking, afwijking op de vier hoeken, specifieke weigeringsreden + advies.
* Knop **"Exporteer meetdiagnose"** schrijft `meetdiagnose_<sessie-ref>_<kozijn>.json` naar de map Documents van de app (Bestanden-app). Schema: `schemas/photo_walk_measure_diagnostics_v1.schema.json`. Inhoud: pixelhoeken, intrinsics, aantallen, afstanden, vlakstatistieken, vlaggen, drempels, hints. **Niet**: foto's, dieptekaarten/puntenwolken, absolute pose, locatie. `session_ref` = eerste 12 hex-tekens van sha256(sessie-ID).
* Valideren/analyseren op de pc: `python -m photo_walk_core.validate meetdiagnose_*.json`.

## 5. Geen valse zekerheid bij referenties

Referentiesoort `GESCHAT` (standaard in de app), `GEMETEN (duimstok/laser)` of `UIT TEKENING`. Alleen de laatste twee kunnen `DERIVED` geven; `GESCHAT` ⇒ `ESTIMATED` + `REFERENCE_USER_ESTIMATE` (oranje). Een geschatte meter is dus geen meting.

## 6. Wat is synthetisch getest

15 scenario's (Python `tests/test_lidar_v2.py`, Swift `LidarV2Tests`; Swift-pariteit op `level_a_v2`): vlakke gevel met raam; terugliggend raam (2/6/12 cm); uitstekende vensterbank; glas zonder/onbetrouwbare diepte; meerdere gevelvlakken in één foto; baksteenreliëf (alleen Python); te weinig dekking; sterk scheve camera (alleen Python: tot 50° goed, 60° geweigerd); juiste/onjuiste buitenhoeken; meerdere LiDAR-frames; tegenstrijdige frames; slechte AR-tracking; verschoven dieptekaart (begrensde fout of weigering); geen metrische schaal; schaalconsistentie bij andere resolutie/intrinsics.
Bewijs dat de nieuwe methode **niet vaker fout accepteert** omdat controles zijn versoepeld: de regressietest (`test_regression_new_never_accepts_more_wrong_sizes_than_legacy`) draait 48 willekeurige scènes (terugligging, reliëf, ruis, vensterbank, glas, afstand, hoek) door v2 én door de oude methode (bewaard als `python/tests/legacy_level_a.py`) en eist: v2 accepteert **0** maten met > 2 % fout, ≤ het aantal van de oude methode, en accepteert ≥ 70 % van de scènes (dus niet veilig door alles te weigeren). In een eerdere verkenning (90 scènes) accepteerde v2 90 maten met 0 > 2 % fout (mediaan 0,3 %); de oude methode accepteerde 75 maten waarvan 39 > 2 % fout (en weigerde 15). Adversariële scènes (ruwe muur, verspringende gevel links/rechts, reliëf 6 cm, ruis 3 cm, 70 % gaten) leveren geen foutieve maat. Python-testsuite: 79 tests.

## 7. Wat nog fysiek bevestigd moet worden

* Echte LiDAR-ruis σ(z) en randvervaging op baksteen, glas, gecoate kozijnen, tegenlicht; of 4 mm + 4 mm/m past.
* Uitlijning diepte↔beeld (de diagnose bewaart kantprofielen; een systematische verschuiving > ~8 dieptepixels kan bij terugliggende kozijnen tot ~2,6 % fout leiden zonder dat het wordt geweigerd — gesimuleerde grootste verschuiving 24–40 px is onrealistisch, maar echte waarde onbekend).
* Of de binnenband (0,88–0,985×) bij echte kozijnprofielen het profiel raakt (smalle/brede profielen, kaders die niet exact op de buitenrand zitten).
* Of de bewegingshint in de praktijk voldoende onafhankelijke kaders oplevert (handtrilling vs. 2 cm/1,5°).
* Dat ARKit `sceneDepth` en `capturedImage` binnen de tolerantie dezelfde geometrie hebben (intrinsics van het diepte-beeld).
* Alle drempels (`config.py` / `Config`): kalibreren op de meetdiagnose-bestanden; pas daarna een nauwkeurigheidsclaim.
