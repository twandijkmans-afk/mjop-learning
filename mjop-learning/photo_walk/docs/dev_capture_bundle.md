# Ontwikkelbundel (`photo_walk_capture_bundle_v1`)

Alleen voor **ontwikkeling en kalibratie**. Doel: een echte meting later exact kunnen herhalen (replay) zonder ruwe sensordata in Git, in een PR, in CI-artifacts of in externe opslag te zetten.

## Alleen in Debug-builds
De hele ontwikkelinterface (scherm *Meetdiagnose*, de diagnose-export, de ontwikkelbundel met schakelaars, schrijf- en verwijderknop) is afgeschermd met `#if DEBUG` en bestaat **niet** in een Release-build:
* `DiagnosticsView.swift`, `DiagnosticsExport.swift` en `DevBundleStore.swift` staan volledig binnen `#if DEBUG`; de link *Meetdiagnose* in `PhotoResultView` en de diagnose-aanroep in de selftest ook.
* `project.yml` zet `DEBUG` alleen in de Debug-configuratie (`SWIFT_ACTIVE_COMPILATION_CONDITIONS`).
* Het gebruikersadvies "beweeg meer" (voorheen een hulpfunctie in `DiagnosticsView`) staat nu in `MotionAdvice.swift`, ongewijzigd en ook in Release beschikbaar.
* Bewijs: statische test `python/tests/test_release_isolation.py` (elke PR) en de macOS-CI-stap "Release-binary bevat geen meetdiagnose/ontwikkelbundel", die symbolen en strings van het Release-binary scant en als positieve controle hetzelfde in de Debug-binary vindt.
* De bibliotheekcode (`CaptureBundle`, `ExtendedDiagnostics` in PhotoWalkCore) is platformonafhankelijk en blijft compileren voor de tests; de app heeft in Release geen aanroeper ervan.

## Standaard uit, lokaal
* Schakelaar (alleen Debug): meetdiagnose-scherm → *Ontwikkelbundel opslaan* (`UserDefaults`-sleutel `photowalk.devBundle.enabled`, standaard `false`). De volledige foto is een tweede, aparte schakelaar (`photowalk.devBundle.includePhoto`, standaard `false`).
* Er wordt alleen een bundel geschreven na de expliciete knop *Bewaar ontwikkelbundel van deze meting*. De gewone meetflow, de diagnose-export en de selftest schrijven nooit een bundel.
* Locatie: `Application Support/devbundles/bundle_<sessie-ref>_<observatie>/` op het toestel, uitgesloten van iCloud/iTunes-back-ups, bestandsbescherming `completeFileProtection`. Er is geen upload, geen netwerkcode en geen deelknop voor de bundel.

## Wat wordt opgeslagen
| Bestand | Inhoud |
|---|---|
| `manifest.json` | contract en versie, tijdstip (UTC), app-build, sessie-ref (12 hex-tekens van een sha256), observatie- en frame-id, kaderhoeken in pixels, intrinsics per frame, tracking per frame, **helling**: de richting van "omhoog" in het camerastelsel van het hoofdframe, poses van de steunframes **relatief aan het hoofdframe**, sha256 van de gebruikte drempels, bestandslijst met sha256, privacyvlaggen |
| `depth_<frame>.f32` | dieptekaart per frame, little-endian float32, rij-hoofdvolgorde (0/NaN = ongeldig) |
| `photo.jpg` | volledige foto, **alleen** als *Volledige foto meenemen* aanstaat |

## Wat niet wordt opgeslagen
Locatie/GPS, kompas of richting op aarde, absolute positie of oriëntatie van het toestel (alleen relatieve poses en de helling), gebruikers-, project- of adresgegevens, de ongehashte sessie-id.

## Verwijderen
* In de app: meetdiagnose-scherm → *Verwijder ontwikkelbundels* (verwijdert alle bundels met foto's en dieptekaarten; de knop toont het aantal).
* Of de app van het toestel verwijderen (de sandbox verdwijnt).
* Een bundel die als bestand wordt gedeeld (bv. handmatig via Bestanden/Xcode) valt buiten de app: verwijder die kopie zelf.

## Replay
`python/photo_walk_core/capture_bundle.py` (`read_bundle`) controleert alle sha256's en bouwt de views opnieuw op; Swift: `CaptureBundle.read`. Replay geeft dezelfde meetuitkomst (gelijke vlaggen, schaalmethode en frames; maten binnen 1e-4 m) — gedekt door `python/tests/test_capture_bundle.py` en `CaptureBundleTests.swift`.

## Bewaking
* Python-test: geen `.f32`-, beeld- of `bundle_*`-bestanden in de repository.
* CI (macOS): de selftest maakt geen `devbundles`-map en er staan geen `.f32`/`photo.jpg`/`bundle_*` in de CI-logs.
* Bundels worden nergens als CI-artifact geüpload.

## Bekende beperkingen en openstaande aandachtspunten
* **Ongebruikte bibliotheekcode in de Release-binary.** `CaptureBundle` en `ExtendedDiagnostics` (PhotoWalkCore) compileren ook in Release en worden door de linker niet volledig weggelaten; de CI-scan meldt ze als "info" (o.a. `CaptureBundle`: 128 treffers in Release, `photo_walk_capture_bundle_v1`: 1). De app heeft in Release **geen enkele aanroeper**: scherm, schakelaars, schrijf-, export- en verwijderknop en de opslaglocatie (`DevBundleStore`) bestaan niet in Release (CI: alle acht app-markers 0 keer in de Release-binary, wel in de Debug-binary). De ontwikkelfuncties zijn dus niet bereikbaar; alleen niet-aangeroepen code is aanwezig.
* **OPENSTAAND: nog niet gevalideerd met echte iPhone-opnames.** Alle Swift-, UI- en selftests draaien op de simulator met synthetische data; alleen de twee echte metingen F005 en F014 (als exportbestanden, zonder foto's) zijn als replay-test in Python gebruikt. Niet op een echt toestel gecontroleerd: schrijven en lezen van een bundel met echte diepte en foto, verwijderen, uitsluiting van back-ups, de randsterkte-getallen uit een echte foto, de schaduwpoorten op rommelige echte diepte, en een Release-app die op een toestel draait (de Release-devicebuild is unsigned en niet geïnstalleerd).
* **Pariteit Swift/Python:** in twee interieurscenes met 3 vlakken wijken inlier-tellingen (±3), aandelen (±0,015) en vlakhoek (±0,2°) af omdat Python (numpy `default_rng`) en Swift (`SplitMix64`) in de bestaande meetcode verschillende RANSAC-steekproeven trekken. Alle andere scenes en alle statussen, vlaggen, poortuitkomsten en maten zijn exact gelijk getest.
* **Nog te leveren:** profielbreedtes links, rechts, boven en onder als aanvullende referentiemeting.
