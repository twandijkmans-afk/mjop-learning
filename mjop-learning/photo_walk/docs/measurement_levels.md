# Meetniveaus A / B / C

De modus wordt automatisch bepaald (`pipeline.determine_measurement_mode`): dieptesensor + wereldtracking ⇒ **A** (terugval B, C); alleen metrische tracking ⇒ **B** (terugval C); anders **C**. **LiDAR is nooit verplicht.**
Een niveau dat slaagt levert een waarde; een niveau dat faalt geeft concrete instructies en de pipeline valt terug op het volgende niveau. Bij onderling **inconsistente standpunten** wordt bewust *niet* teruggevallen (dat zou de inconsistentie verbergen): resultaat `UNKNOWN`.

## Niveau A — metrische diepte (LiDAR / ARCore Depth)

*Een dieptepixel op een verre hoek is geen betrouwbare hoekmeting* (randen mengen voorgrond/achtergrond, glas reflecteert, bereik ~5 m). Daarom:

1. Hoekselectie valideren (simpele convexe vierhoek, binnen beeld).
2. **Gevelvlak** aanpassen uit de dieptepunten in een **ring rond** het kozijn (RANSAC + kleinste-kwadraten), niet uit de hoekpixels en niet uit het glas. Poorten: dekking van de ring, bereik, inlierratio, rms (`DEPTH_COVERAGE_LOW`, `DEPTH_RANGE_EXCEEDED`, `MIXED_FACADE_DEPTH`, `PLANE_NOISY`).
3. Elke hoek = **snijpunt van de camerastraal met dat vlak** (met cameraintrinsics en pose). Poort op invalshoek (`OBLIQUE_ANGLE`).
4. Controle dat het resultaat een rechthoek is (`WRONG_CORNER_SELECTION`) en binnen 0,10–10 m valt.
5. Cross-check: diepte op de hoekpixel versus het vlak. Licht afwijkend ⇒ adviserend; ≥ 3 hoeken sterk afwijkend ⇒ blokkerend (het vlak ligt dan waarschijnlijk op een voorsprong/balkon in plaats van op het kozijn — gedekt door een test).
6. Glasbeoordeling (adviserend): ontbrekende of "te diepe" diepte in het glas ⇒ `GLASS_DEPTH_UNRELIABLE`; de maat gebruikt het glas toch nooit.
7. Meerdere standpunten: inverse-variantiegewogen fusie; per paar `|Δ| ≤ k·√(σ₁²+σ₂²)` (k provisional = 3), anders `VIEWS_INCONSISTENT` ⇒ `UNKNOWN`.

Tracking niet `NORMAL` ⇒ het beeld wordt niet gebruikt (`TRACKING_LOST`).

## Niveau B — AR-tracking en geometrie (geen dieptesensor)

* ≥ 2 standpunten van dezelfde hoeken; kleinste-kwadraten-triangulatie van de camerastralen; poorten op parallax (`LOW_PARALLAX`), herprojectiefout (`INCONSISTENT_VIEWS`), punten achter de camera, coplanariteit.
* **Perspectiefcorrectie is geen schaal.** Zonder metrisch verankerde tracking levert B alleen de verhouding breedte/hoogte (`NO_METRIC_SCALE`, geen meters).
* Met door het toestel gedeclareerde metrische tracking (VIO) ontstaat een maat, maar die is `ESTIMATED` + `METRIC_SCALE_UNVERIFIED`: schaal uit VIO is niet *aantoonbaar* betrouwbaar. Een ingevoerde referentie op hetzelfde vlak kan de schaal bevestigen (|verhouding − 1| ≤ 3 %, provisional) ⇒ `DERIVED`; wijkt ze af ⇒ de referentie wordt leidend (niveau C) en de afwijking wordt gemeld.
* Associatie van waarnemingen zonder diepte gebeurt via triangulatie en is altijd `ASSOCIATION_UNVERIFIED`.

## Niveau C — referentiemeting

De inspecteur geeft **één** betrouwbare afstand tussen twee punten op het kozijnvlak. Methode (alleen intrinsics nodig):

1. Een rechthoek op dat vlak (standaard het kozijn zelf, of een ander gemeten kozijn = `anchor`) geeft via de homografie `H` en `K⁻¹H = [m₁ m₂ m₃]` het vlak in cameracoördinaten **tot op schaal**; `m₁ ⟂ m₂` volgt uit de geometrie en wordt als poort gebruikt (`RECT_ASSUMPTION_VIOLATED`).
2. De referentiepixels worden op dat vlak geprojecteerd; de ongeschaalde afstand ⇒ schaalfactor `k = d_referentie / d_ongeschaald`.
3. Doelhoeken op hetzelfde vlak snijden ⇒ metrische hoeken ⇒ breedte/hoogte. Perspectief is daarmee gecorrigeerd (test: camera ca. 54° t.o.v. de gevelnormaal; de pixelverhouding wijkt dan >5 % af van de echte verhouding).
4. **Verkeerd vlak**: ander `plane_id` ⇒ `REFERENCE_PLANE_MISMATCH`; met diepte: referentiepunten > 5 cm (provisional) van het gevelvlak ⇒ geweigerd. Een nieuw kozijn op een *ander* vlak vraagt een nieuwe referentie.
5. Gebruikt een kozijn een referentie via een ander kozijn (`anchor`), dan geldt de aanname dat beide **coplanair** zijn (`COPLANARITY_ASSUMED`): uit één beeld is dat niet te bewijzen.

Er wordt **geen** standaarddeurbreedte, baksteenformaat of verdiepingshoogte als schaal gebruikt.

## Dubbeltelling

Waarnemingen worden alleen samengevoegd bij: zelfde vlak (normaalhoek ≤ 15°, offset ≤ 15 cm), middelpunt binnen `0,5·min(afmeting)`, vergelijkbare maat, en nooit twee waarnemingen uit hetzelfde beeld in één cluster. Twee kandidaten van vergelijkbare afstand in één ander beeld ⇒ `AMBIGUOUS_ASSOCIATION` (niet samengevoegd). Zonder wereldpositie blijft een waarneming apart met `ASSOCIATION_UNVERIFIED`; handmatige koppeling (`explicit_links`) is mogelijk. Een kozijn in 3 beelden telt als **één** object (test).
