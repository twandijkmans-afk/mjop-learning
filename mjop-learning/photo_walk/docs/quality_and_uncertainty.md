# Meetkwaliteit en onzekerheid

Er is bewust **geen enkel confidence-percentage**. Kwaliteit is zichtbaar als (1) poorten met een code en een concrete opnamestructie, (2) bewijs in `scale_evidence`, (3) een modelgebaseerde onzekerheid.

## Controles per risico uit de opdracht

| Risico | Hoe afgedekt | Code |
|---|---|---|
| Trackingverlies | beeld wordt niet gebruikt | `TRACKING_LOST` |
| Onvoldoende dieptedekking | dekking van de ring rond het kozijn | `DEPTH_COVERAGE_LOW` |
| Bereik dieptesensor | ≥ 30 % van de ring voorbij 5 m, of te weinig geldige punten | `DEPTH_RANGE_EXCEEDED` |
| Te grote camerabeweging | alleen via de trackingstatus van het toestel (`LIMITED_EXCESSIVE_MOTION`); bewegingsonscherpte op het beeld wordt **niet** gemeten | `TRACKING_LOST` |
| Reflecties in glas | vlak uit de omringende gevel; glasdiepte alleen beoordeeld | `GLASS_DEPTH_UNRELIABLE` |
| Verkeerde hoekselectie | vlinderdas, niet-rechthoek, hoek buiten beeld, hoekdiepte | `CORNER_ORDER_INVALID`, `WRONG_CORNER_SELECTION`, `CORNER_OUTSIDE_IMAGE`, `CORNER_DEPTH_MISMATCH` |
| Begroeiing | **niet detecteerbaar**; alleen via melding van de gebruiker (`obstruction_reported`) | `OBSTRUCTION_REPORTED` |
| Schuine fotohoeken | invalshoek van de hoekstralen op het vlak | `OBLIQUE_ANGLE` |
| Te weinig overlap | `coverage.facade_coverage`: overlap tussen opeenvolgende keyframes en onbezochte cellen, met NL-instructie | guidance |
| Inconsistentie tussen frames | paarsgewijze consistentietoets met de onzekerheden | `VIEWS_INCONSISTENT` |
| Verschillende geveldieptes | inlierratio van de vlakfit; ≥ 3 hoeken ver van het vlak | `MIXED_FACADE_DEPTH` |

## Onzekerheid

`measurement_uncertainty` = 1-σ uit een **Monte Carlo (200 trekkingen, vaste seed)** over: hoekpixelruis (σ = 1,5 px), vlakoffset en -kanteling (uit rms van de vlakfit en aantal punten, effectief ≤ 50 onafhankelijke punten) en, bij niveau C, de opgegeven referentie-onzekerheid. `validated` is altijd `false`.

**Wat dit niet is:** geen gemeten tolerantie. De parameters zijn aannames; systematische fouten (lensvervorming, AR-drift, sensorbias, schaal van LiDAR op verre randen) zitten er niet in. Alle drempels staan in `config.py` en zijn `PROVISIONAL_UNVALIDATED`; ze moeten met metingen op een fysiek toestel worden vastgesteld (zie `device_validation.md`).

## Wat de simulatie wel/niet zegt

In een eenmalige run (40 ruisrealisaties, enkele standpunt, kozijn 1,2 x 1,5 m op 4 m, ruisvrije camera-geometrie, gesimuleerde LiDAR-ruis σ ≈ 5 mm + 0,2 %·afstand, 3 % gaten) was de standaardafwijking van de fout 2,6 mm (breedte) en 2,8 mm (hoogte), maximum 7,2 mm; het Monte-Carlo-model gaf gemiddeld σ ≈ 4 mm (dus conservatief **ten opzichte van het simulatiemodel**). Niveau C: foutspreiding hoogte 4,3 mm, modelσ 11 mm. Dit bewijst alleen dat de geometrie en het ruismodel intern kloppen, niet dat een echte gevel met een echte iPhone dezelfde nauwkeurigheid haalt.
