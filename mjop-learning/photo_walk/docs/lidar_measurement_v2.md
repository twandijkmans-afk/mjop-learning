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


## 8. Reparatie FACADE_NOT_PLANAR (echte iPhone-diagnose, binnenopname)

**Casus** (`photo_walk_ios_lidar_v2/1`, foto F000, OBS-F000-02): 56 401 ringpunten op 1,26 m, drie vlakken (REVEAL 23 707 · FACADE 13 408, rms 13,7 mm · REVEAL 9 039), zijdeverdeling van het gevelvlak `[49, 10586, 1423, 1350]`; geweigerd met `FACADE_NOT_PLANAR`, "robuuste ruis 0,426 m". Er is **geen ruwe puntenwolk**; een exacte replay is niet mogelijk. De casus is nagebootst met synthetische scènes en een puntenwolk met dezelfde verdeling (`test_facade_plane_fix.py`, `facade_point_cases` in de pariteitsfixture).

**Bevestigde oorzaak.** `pick_facade` (Python) / `pickFacade` (Swift) berekende `robust_sigma = 1,4826 · mediaan(|afstand tot gekozen vlak|)` over **alle** ringpunten (`_resid`), dus ook over de dagkanten, vensterbank en andere lagen die al als apart vlak waren herkend. Als het gevelvlak minder dan de helft van de ring is (hier 24 %), bepaalt de mediaan de afstand tot die andere lagen. Een lokaal vlak met rms 13,7 mm werd zo met 0,426 m "ruw" genoemd. Gereproduceerd in een gesimuleerde binnenopname met diepe dagkanten (ringspreiding 0,047 m tegen limiet 0,031 m, lokale spreiding 8,7 mm).

**Correctie (geen gate versoepeld).** De ene gate is vervangen door afzonderlijke controles (`depth_plane.pick_facade`, `DepthPlane.swift`):
1. *Lokale vlakkwaliteit*: rms van de inliers én robuuste spreiding van uitsluitend de lokale populatie = eigen inliers + niet-toegewezen punten + **parallelle** vlakken dichtbij, binnen ±3×drempel. Niet-parallelle herkende vlakken (dagkant, vensterbank) tellen niet mee. Parallelle nabije "schijven" moeten wel meetellen: een écht ruw oppervlak splitst RANSAC in schijven en zou anders ontsnappen (gevonden door een test; `noise_on_chosen_plane`). Limieten ongewijzigd (rms ≤ 1,5σ+8 mm, robuust ≤ 2σ+12 mm).
2. *Conflicterende vlakken*: naast parallelle stappen nu ook een tweede, even groot verticaal vlak met andere richting ⇒ `AMBIGUOUS_FACADE_PLANES`.
3. *Ondersteuning*: ongewijzigd (≥ 50 % van de niet door andere structuur verklaarde punten) plus onverklaard aandeel ≤ 60 % (`FACADE_NOT_PLANAR`).
4. *Zijdeverdeling*: een zijde telt als gedekt bij ≥ max(15 punten, 5 % van de vlakpunten); 49 punten naast 10 586 telt dus niet. ≥ 3 gedekte zijden, of 2 tegenover elkaar; minder dan 4 ⇒ `LIMITED_SIDE_COVERAGE` (voorkomt `MEASURED`). Aandeel per zijde staat in de diagnose.
5. *Ruimtelijke omvang*: kleinste in-vlak spreiding ≥ 4 % van de kaderdiagonaal, anders `FACADE_NOT_REPRESENTATIVE` (alleen een smal profiel, dagkant of vensterbank is geen gevel). Een vlak dat alleen een horizontale dagkant/vensterbank is, valt al af als niet-verticaal (`NO_FACADE_PLANE`).

Kozijnvlak (terugligging), hoekcontrole en kaderomvang blijven na een goed wandvlak volledig gelden: een goed gevelvlak bewijst niet dat de vier punten de buitenhoeken zijn.

**Tweede, bestaande fout gevonden en hersteld.** Bij diepe dagkanten (≥ 0,4 m, gesimuleerd) werd het kozijnvlak via de *terugval op hoekdieptes* bepaald; dat cluster pakte de dagkant en gaf **3–9,5 % te kleine maten** die als `ESTIMATED` werden geaccepteerd. De terugval wordt nu niet meer als maat gebruikt (alleen `indicative_corner_offset_m` in de diagnose); de uitkomst is `FRAME_PLANE_UNDETERMINED`. De reparatie van de vlakgate had deze fout zichtbaar gemaakt, omdat zulke scènes eerder al vóór dat punt werden geweigerd.

**Rotatie en onafhankelijkheid.** Frames kunnen op rotatie (≥ 1,5°) worden *geselecteerd* en leveren dan extra punten, maar tellen nu **niet** meer als onafhankelijk standpunt. Alleen verschillende posities (≥ 2 cm) tellen voor `LIDAR_DEPTH_MULTI_FRAME` en `MEASURED`. Zes geselecteerde frames met 6,5 mm baseline (zoals in de echte scan) geven dus één standpunt: `LIDAR_DEPTH_PLANE`, `ESTIMATED`. Dit is een aanscherping, geen versoepeling. De diagnose toont geselecteerde/bruikbare frames, verschillende standpunten, alleen-gedraaide frames en per frame baseline en rotatie.

**Nieuwe diagnose** (`algorithm.facade_assessment`, `algorithm.independence`; zichtbaar in het Meetdiagnose-scherm): punten op het gekozen vlak; aantal/aandeel als andere dieptelaag uitgesloten; onverklaard aandeel; rms en robuuste spreiding van uitsluitend het gekozen vlak met limieten; totale ringspreiding (uitsluitend achtergrond); aantallen en aandeel per zijde en welke zijden gedekt zijn; in-vlak omvang; reden en exacte blokkerende controle. Geen foto's, puntenwolk, locatie of absolute pose.

**Niet bewezen.** Dit is aangetoond op gesimuleerde scènes. Of de echte scan nu slaagt, of het kader de volledige buitenmaat is (de foto toont meerdere dieptelagen) en hoe nauwkeurig de maat is, kan pas met een nieuwe meting en een fysieke vergelijking.
