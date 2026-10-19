# Zoom en nauwkeurige selectie (Zoom & Precision Selection v1)

## Uitgangspunt
Zoom is **uitsluitend een weergave-instelling**. Hij verandert niets aan de ARKit-sessie, de camera-intrinsics, de poses, de LiDAR-dieptekaart of het opgeslagen keyframe. Hij geeft **geen extra metrische nauwkeurigheid**: hij maakt alleen preciezer *aanwijzen* mogelijk (dezelfde vingerfout in schermpunten = een kleinere fout in beeldpixels). De meetkern rekent altijd met de **originele pixelcoördinaten** van het keyframe.

## Coördinaten (waarom ze correct blijven)
`PhotoWalkCore/ViewportTransform.swift` is de enige plek waar scherm ↔ beeld wordt omgerekend:

| Stelsel | Betekenis |
|---|---|
| NATIVE | pixels van het opgeslagen keyframe (1920x1440 landscape), waarin hoeken/referenties worden bewaard en gemeten |
| DISPLAY | het rechtop getoonde beeld (oriëntatie `.right`: `x = H − v`, `y = u`) |
| VIEW | punten in de weergave (UIKit) |

`viewPoint = origin(zoom, pan) + display · (fit · zoom)`; terugrekenen is de exacte inverse + de oriëntatie-inverse. Zoomen rond een ankerpunt (pinch) houdt het beeldpunt onder de vingers vast; pan wordt begrensd (met 40 pt marge zodat randhoeken bereikbaar blijven); bij zoom 1 past het hele beeld (geen uitsnede). De waarden die de UI doorgeeft (`points`) zijn altijd NATIVE; ze worden opgeslagen in `Observation.corners`/`originalCorners` en `ReferenceMeasure`.
Elke uitlezing toont de beeldpixels (`1 linksboven: (960.4, 719.8) px`) zodat dit controleerbaar is.

## Bediening
**Hoeken markeren / referentie / hoek corrigeren** (`FrameImageCanvas` → `ZoomCanvasView`, UIKit):
* pinch = zoom rond de vingers (1×–8×), met zoomindicator, knoppen 1×/2×/4×/8×, slider (logaritmisch) en *Reset*; knoppen/dubbeltik zoomen vloeiend (0,22 s, uitgeschakeld bij "Beweging verminderen");
* één vinger slepen = beeld verschuiven; begint de vinger binnen 44 pt van een eigen punt, dan wordt dat punt *relatief* versleept (de vinger bedekt het punt niet);
* tik = punt plaatsen (kruis + ring, donkere rand + kleur voor zichtbaarheid in fel licht; haptische bevestiging; groot gemarkeerd + vergrootglas 1,2 s); dubbel tikken = zoom resetten;
* vergrootglas (3× extra) toont tijdens slepen/plaatsen de omgeving van het punt; gestippelde omlijning verbindt de punten;
* "Laatste punt weg" en "Wissen" — niet meer een hele foto opnieuw maken om één hoek te herstellen;
* hoekcorrectie: groene bestaande hoeken blijven zichtbaar en bewegen mee met zoom/pan; nieuwe positie plaatsen/slepen, dan *Corrigeer* (revisie, origineel blijft).

**Live camera** (`LiveScanView`): pinch-to-zoom, zoomindicator, 1×/2×/4× en slider (1×–4×), dubbeltik = 1×, verschuiven bij zoom > 1. Dit is een *visuele vergroting van de voorvertoning*: de fysieke camera, `ARWorldTrackingConfiguration` en de frames waaruit keyframes worden vastgelegd zijn ongewijzigd; een keyframe is altijd de volledige, onvergrote opname (ook als je hebt ingezoomd). De app zegt dat ook op het scherm.

## Tests
* Swift (`ZoomTests`, macOS-CI): zelfde fysieke hoek op 1×/2×/4×/8× en na pannen → identieke native pixel (1e-9); round-trip; schermformaten (SE tot iPad-achtig) en rotatie; oriëntatie `.right`/`.up`; ankerbehoud; pan-klem; reset; **Level A, referentiemeting en hoekcorrectie leveren bij elke zoom dezelfde breedte/hoogte/bruto m²**; intrinsics en dieptedata ongewijzigd; dezelfde vingerfout geeft bij 4× een ~4× kleinere pixelfout en kleinere oppervlaktefout.
* XCUITest (simulator): pinch → zoomindicator stijgt; tik in het midden op 1× en op hoge zoom → dezelfde originele pixel (±25 px); pannen verandert de zoom niet maar wel de beeldplek; dubbeltik/Reset/knoppen/slider; vier hoeken plaatsen en opslaan op 2×; live-zoombediening.
* Niet te testen zonder toestel: vingergevoel, prestaties op oudere toestellen, helderheid van de markers in zonlicht, interactie met de échte camerabeelden. Zie `device_validation.md`.

## Beperkingen
* Boven ca. 4–5× is het 1920x1440-keyframe (≈ 1 beeldpixel per scherm-pixel) niet scherper; 8× is er voor het gemak, niet voor extra detail.
* Het vergrootglas gebruikt het opgeslagen keyframe (niet een live hogere resolutie).
* Een nieuw punt plaatsen heeft ~0,3 s vertraging vanwege de dubbeltik-herkenning.
