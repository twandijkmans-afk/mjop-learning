# Photo Walk & Scale Capture v1 — iPhone-MVP (Android-ready)

Prototype van een gevelscanner voor inspecteurs: foto's/keyframes, camerapose, intrinsics en dieptegegevens verzamelen, kozijnen laten aanwijzen, **buitenmaat en bruto m² uitrekenen** en alles als voorlopig, reviewbaar `photo_walk_capture_v1`-record exporteren.
Zelfstandige component in `mjop-learning` met een duidelijke integratie-interface (het JSON-contract). Er is **geen** bestaande mobiele repo aangepast: `twandijkmans-afk/MJOP-App` is een JavaScript-PWA zonder iOS/Android-code en is ongemoeid gelaten.

## Wat is er echt gedaan? (lees dit eerst)

| Onderdeel | Gebouwd | Gecompileerd/uitgevoerd | Gesimuleerd | Echte sensor | Op toestel gevalideerd |
|---|---|---|---|---|---|
| Python-meetkern (`python/photo_walk_core`) — geometrie, niveau A/B/C, kwaliteitspoorten, dedup, dekking, contract, export | ja | **ja (39 tests groen)** | ja | nee | nee |
| JSON-schema `photo_walk_capture_v1` | ja | ja (validatie in tests) | – | – | – |
| Swift-package `PhotoWalkCore` + pariteits-/workflowtests | ja | **ja, op macOS-CI (Xcode 16.4): 12 tests groen** | ja | nee | nee |
| iOS-app (SwiftUI/ARKit) | ja | **ja: simulator- en unsigned devicebuild groen in CI; XCUITest-rooktest + headless selftest** | simulatieflow | nee | **nee — nooit op een fysieke iPhone gedraaid** |
| Android-contract/adapter (Kotlin) | ja (klein) | **nee** | – | nee | nee |

CI-workflow `photo-walk-ios.yml` bouwt Swift + app op `macos-15` (zonder code signing). Installatie op een iPhone: `docs/install_windows_free.md`.

Een synthetisch succesvolle test bewijst **geen** nauwkeurigheid op een echte gevel. Lokaal was er geen macOS/Xcode/iPhone; de Swift-code wordt door GitHub Actions op macOS gecompileerd en getest. Kotlin is nog niet gecompileerd. Wat nog op een toestel moet: `docs/device_validation.md`.

## Mappen

```
photo_walk/
  schemas/photo_walk_capture_v1.schema.json   gesloten, versieerbaar contract
  python/photo_walk_core/                     meetkern (numpy + jsonschema; geen netwerk, geen AI-SDK)
  python/tests/                               39 tests (synthetisch)
  ios/Package.swift, ios/Sources/PhotoWalkCore  Swift-port van de kern (zonder ARKit)
  ios/Tests/…/Fixtures/parity_cases.json      Python-uitkomsten waar de Swift-tests tegen toetsen
  ios/App/                                    SwiftUI/ARKit-app (XcodeGen project.yml)
  android/photowalk-contract/                 Kotlin-adaptercontract + ARCore-vertaalfuncties
  examples/                                   gesimuleerde exportrecords (JSON/CSV)
  docs/                                       contract+coördinaten, meetniveaus, kwaliteit, ARKit, Android, privacy, validatie
```

## Snel proberen (zonder iPhone): simulatie en tests

```bash
cd mjop-learning/photo_walk/python
python -m pip install -r requirements.txt
python -m pytest -q -p no:cacheprovider tests            # 39 tests
python -m photo_walk_core.demo --out /pad/buiten/de/repo   # demonstratie: 1 kozijn (stappen 1-11) + 4 kozijnen over 7 keyframes
python -m photo_walk_core.validate examples/walk_measurement.json
```

De demo toont o.a. een misgeklikte hoek (resultaat `UNKNOWN`, want de standpunten zijn inconsistent), de menselijke correctie (origineel blijft bewaard, revisie erbij), de herberekening en de export. Voorbeeld (gesimuleerd, kozijn 1,200 x 1,500 m):

```
voor correctie : UNKNOWN (geen waarde) - ['VIEWS_INCONSISTENT']
na correctie   : 1.202 x 1.496 m = 1.80 m2  [MEASURED]  sigma_area=0.0051  afwijking t.o.v. simulatiewaarheid -0.0018 m2
9 waarnemingen over 7 keyframes -> 4 unieke kozijnen (werkelijk 4)
```

Export: `export_record(...)` schrijft `<naam>.json` + `<naam>.csv` naar een map **buiten** de repo (binnen de repo geweigerd; alleen synthetische voorbeelden in `examples/`).

## iPhone-app openen en starten (op een Mac)

Vereist: macOS met Xcode ≥ 15, iOS ≥ 16, iPhone met ARKit. **LiDAR is niet verplicht** (iPhone 12 Pro en nieuwer/Pro-modellen hebben `sceneDepth`; andere toestellen gebruiken B/C).

```bash
cd photo_walk/ios
swift test                      # Swift ↔ Python-pariteit + workflowtests (draait groen in CI)
cd App && brew install xcodegen && xcodegen generate && open PhotoWalk.xcodeproj
```
Ondertekenen met eigen team en op een toestel draaien (de simulator heeft geen ARKit-camera).

**Toestemmingen:** alleen camera (`NSCameraUsageDescription`). Bewust geen locatie.
**Ondersteunde sensoren:** camera + ARKit-wereldtracking (vereist); LiDAR/`sceneDepth` (optioneel); intrinsics en pose per frame. Plane detection staat aan maar wordt niet voor de maat gebruikt.

**Testscan zonder sensoren:** startscherm → *Testscan met synthetische data (simulatie)* — laadt de gesimuleerde dieptekaart, meet met `PhotoWalkCore` en toont resultaat naast de Python-referentie.
**Echte scan:** gebouw-/gevel-ID invullen → *Nieuwe scan starten* → camera langs de gevel bewegen → *Keyframe* per standpunt (≥ 2 standpunten per kozijn voor `MEASURED`) → *Kozijnen markeren*: per keyframe vier buitenhoeken tikken (volgorde linksboven, rechtsboven, rechtsonder, linksonder), optioneel on-device voorstellen (onbevestigd) → *Koppel aan kozijn* kiezen als het kozijn al op een ander keyframe staat → optioneel *Referentiemaat* (twee punten + afstand) → *Resultaten*: lijst met breedte, hoogte, bruto m², status, bron, onzekerheid (in export), reviewmarkering en concrete vervolgacties; *Hoeken corrigeren* herberekent zonder brondata te overschrijven → *Exporteer naar bestand* → valideren met `python -m photo_walk_core.validate`.

De scan is **semi-automatisch**: hoeken komen van de gebruiker (of van een onbevestigd voorstel). Er wordt geen automatische kozijnherkenning geclaimd.

## Meetpijplijn in het kort

Niveau **A** (diepte): vlak uit de gevel *rond* het kozijn, hoekstralen snijden dat vlak — een dieptepixel op een hoek wordt niet blind vertrouwd. Niveau **B** (AR-triangulatie): zonder dieptesensor; schaal alleen metrisch bij gedeclareerde VIO-tracking en dan `ESTIMATED` tot een referentie ze bevestigt. Niveau **C** (referentie): één ingevoerde afstand op hetzelfde vlak + rechthoek-geometrie + intrinsics; verkeerd vlak wordt geweigerd. Geen standaarddeurbreedte/baksteen/verdiepingshoogte als schaal. Details: `docs/measurement_levels.md`.
Kwaliteit en onzekerheid zonder confidence-percentage: `docs/quality_and_uncertainty.md`. Alle drempels zijn `PROVISIONAL_UNVALIDATED`.

## Regels die hier gelden

Eén kozijn = één object; glas, vaste en draaiende delen binnen de buitenmaat; bruto m² = buitenbreedte x buitenhoogte (zelfde regel als Bruto Quantity Model v2, getest tegen `bruto_quantity_core`); gemeten/afgeleid/geschat/onbekend blijven gescheiden (samenvatting per status, nooit opgeteld); alles `PROVISIONAL` met `PENDING_HUMAN_APPROVAL`; **geen** besluitregistratie, goedkeuring, kosten, kengetallen of prijzen; geen externe Vision-aanroepen; geen media of locatie in Git. Bestaande v1/v2-contracten, Maldenhof-besluiten en bevroren stores zijn niet gewijzigd (scope-guard- en schema-tests blijven groen).
