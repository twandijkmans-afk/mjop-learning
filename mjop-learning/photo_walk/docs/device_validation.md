# Wat nog op een echte iPhone getest moet worden

Alles hieronder is **niet gedaan**: er was geen macOS/Xcode/iOS-hardware.

## Niveaus van bewijs in dit project

| Niveau | Status |
|---|---|
| Gebouwde code (Python-kern, schema, tests, docs) | ja |
| Gecompileerde code | Python: ja. **Swift/iOS: ja, op macOS-CI (Xcode 16.4, Swift 6.1.2; simulator- + unsigned devicebuild).** Kotlin: nee. |
| Simulatie (synthetische gevel/diepte/poses) | ja — 39 Python-tests + 25 Swift-tests + 5 XCUITests groen |
| Echte sensormeting | **nee** |
| Op fysiek toestel gevalideerd | **nee** |

## Compileren en testen

Dit gebeurt in CI (`.github/workflows/photo-walk-ios.yml`, macOS-15 runner). Op een Mac:

1. `cd photo_walk/ios && swift test` — draait `ParityTests` (Swift ↔ Python op gedeelde fixtures). Verwacht: eventuele compilerfouten (de Swift-code is nooit gecompileerd) en daarna groen.
2. `cd photo_walk/ios/App && xcodegen generate && open PhotoWalk.xcodeproj`; ondertekenen met eigen team; draaien op een iPhone met LiDAR (iPhone 12 Pro of nieuwer, Pro-modellen) én op een model zonder LiDAR (modus B/C).
3. Export valideren: `python -m photo_walk_core.validate <export.json>`.

## Validatieprotocol (voorstel)

Voor elke maat een referentie met lasermeter/duimstok (± 1 mm) op minimaal 10 kozijnen, verschillende afstanden (2/3/4/5 m), kijkhoeken (0/20/40°), lichtomstandigheden, glas (helder/reflecterend/gecoat), materialen en verdiepte/vlakke kozijnen. Per meting registreren: modus, status, flags, σ_model, fout. Vaststellen:
* werkelijke foutverdeling per niveau en afstand ⇒ pas dán tolerantie-eisen en drempels in `config.py` vaststellen;
* of σ_model de werkelijke spreiding dekt (kalibratie, mogelijk met bias-term);
* of `MEASURED` (≥ 2 standpunten) daadwerkelijk betrouwbaarder is dan `ESTIMATED`.

## Concrete open vragen voor het toestel

* ARKit-conventies: intrinsics (pixelhoek vs -midden), `depthMap` ↔ `capturedImage` uitlijning, oriëntaties, confidence-drempel, `depth_z`-definitie.
* LiDAR-gedrag op glas, donkere/glanzende gevelstenen, tegenlicht, bereik > 5 m, randvermenging op kozijnhoeken (de aanname "vlak uit ring" is op echte data ongetoetst).
* Lensvervorming aan de beeldranden; autofocus/zoomwisselingen die intrinsics veranderen.
* AR-drift over een lange gevelwandeling (consistentie van poses tussen standpunten, associatiepoorten).
* Bruikbaarheid van `VNDetectRectanglesRequest` als kozijnvoorsteller (verwacht: beperkt) en of een getrainde on-device detector nodig is.
* UX buiten: tikprecisie van hoeken, zonlicht, handschoenen, tijd per kozijn.
* Android: alles (nog geen app).
* Gedeelde sensor-/AR-ruis in de Monte Carlo (nu ongecorreleerd en provisional).

## Aanvullend voor Photo-to-Quantity v2 (foto-workflow)
* Recall en precisie van de rechthoekdetector op echte gevels (ramen vs. deuren/borden/patronen), en of de gevonden vierhoek de buitenmaat of de glasruit is.
* Vlakfit rond echte kozijnen met LiDAR bij de kaders; hoe vaak kaders groen/oranje/grijs worden en of dat klopt met een duimstokmeting.
* Prestaties/geheugen met veel kandidaten en meerdere foto's; app-start met "laatste scan hervatten".
* Koppelsuggesties bij repeterende, identieke kozijnen (kans op verkeerde suggesties).
* Of een getraind Core ML-kozijnmodel nodig is (en trainingsdata met toestemming).
