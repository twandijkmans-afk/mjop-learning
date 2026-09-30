# Facade panorama PoC v1 — gevelbeelden op schaal uit open panorama's

Status: **proof-of-concept / analyse**. Geen wijziging aan stores, schema's of canonical data. Script:
`scripts/facade_panorama_poc.py`. Resultaat Maldenhof: `reports/quantity/facade_panorama_poc_v1_maldenhof.json`
(gevelbeelden zelf niet gecommit; per wand staat de bron-URL van het panorama erin).

## Waarom

Volledig automatisch gevelhoeveelheden (kozijnen, gevelbekleding, raamdorpels) bepalen zonder locatiebezoek en zonder
licentierisico. Google (Street View, Earth, 3D Tiles) verbiedt afleiden/meten/objectdetectie
(Maps Platform Terms §3.2.3; Map Tiles API-beleid); Cyclomedia vereist een licentie voor extern gebruik.
Gemeente Amsterdam publiceert haar 360°-straatbeelden als open data (**Kernregistratie Panoramabeelden, CC BY 4.0**):
commercieel gebruik, opslag en AI-analyse zijn toegestaan mits bronvermelding.

## Hoe het werkt

1. BAG-pand → 3D BAG LoD2.2 (ruwe respons uit een real_validation-package).
2. Verticale WallSurfaces; tussenmuren eruit (vlak tegen een wand van een ander kandidaat-pand). Maldenhof: 1537,6 m²
   buitenwand (3D BAG `b3_opp_buitenmuur` 1747,3 m²).
3. Per wand de panorama's die er recht tegenover staan (API `near=lon,lat`, 5–25 m, hoek ≤ ~45°).
4. Projectie van het 3D-wandvlak in het equirectangulaire panorama. **De Amsterdamse panorama's zijn genormaliseerd:
   noorden in het beeldmidden, horizon waterpas**; pitch/roll hoeven niet toegepast te worden (gecontroleerd op
   Maldenhof 262–264: de 3D BAG-omtrek valt op de gevel).
5. Gerectificeerd gevelbeeld op schaal: 2 cm/px (bron op 10 m afstand ≈ 8 mm/px).
6. Occlusiecontrole en keuze van het beste panorama per wand:
   - geometrisch: aandeel van een 12×12-raster wandpunten waarvan de zichtlijn een ander LoD2.2-vlak raakt
     (bv. het dak van de eigen aanbouw);
   - vegetatie: aandeel excess-green-pixels in het gevelbeeld;
   - bruikbaar als geometrie + vegetatie ≤ 0,25.

## Resultaat Maldenhof (BPRJ-00001, 15 panden)

| Gevelzijde | Bruikbaar | Obstructie (geometrie) | Vegetatie | Geen panorama |
|---|---|---|---|---|
| Voorgevels (NW) | **403,5 m² (75%)** | 121,2 | 15,4 | 0 |
| Kop-/zijgevels | 317,9 m² (49%) | 234,2 | 74,7 | 21,4 |
| Achtergevels (ZO) | 112,0 m² (34%) | 29,9 | **191,6** | 0 |
| **Totaal** | **836,3 van 1537,6 m² (54%)** | 387,8 | 286,0 | 27,6 |

Visueel gecontroleerd: goedgekeurde wanden tonen de gevel met kozijnen volledig; afgekeurde wanden zijn terecht afgekeurd
(dak van de eigen aanbouw voor de gevel, bomen/schuttingen in achtertuinen). Eén geval rond de grens (0,29) was grotendeels
bruikbaar — de drempel is conservatief.

## Beperkingen

- **Camerahoogte**: zonder NLGEO-raster (`cdn.proj.org` niet bereikbaar) wordt NAP benaderd met een vaste
  geoïdehoogte (43,3 m). Let op: pyproj geeft zonder raster de hoogte **ongewijzigd** terug; het script detecteert dat
  en valt dan terug op de benadering (`height_method` in de uitvoer).
- **Alleen Amsterdam** (open panorama's); elders: 3D BAG + luchtfoto + foto's van de VvE.
- **Opnames in de zomer**: achtergevels zitten vaak achter bladeren; oudere opnamejaren (2016–2025 beschikbaar) worden
  per wand al meegewogen, maar winterbeelden zijn er nauwelijks.
- LoD2.2-wanden zijn gefragmenteerd; per fragment wordt apart beoordeeld (geen samenvoeging per gevel).
- **Nog geen kozijnherkenning.** Volgende stap: vision-model (via `ANTHROPIC_API_KEY` in de omgevingsinstellingen)
  wijst kozijnen/deuren/balkons aan in de gevelbeelden; randverfijning en alle m²/m¹ blijven deterministische code;
  elke waarde als `ESTIMATED`/"uit panorama" met beeld ter controle.

## Uitvoeren

    python scripts/facade_panorama_poc.py --group DOC-005-006 --scope EVEN_ONLY \
        --package data/external/building_validation/real_validation_v3 --out /tmp/facade_poc

Netwerk: `api.data.amsterdam.nl` en `t1.data.amsterdam.nl` (optioneel `cdn.proj.org` voor het NAP-raster).
Bronvermelding: Gemeente Amsterdam, Kernregistratie Panoramabeelden (CC BY 4.0); 3D BAG (TU Delft, CC BY 4.0).

## Vervolg: elementherkenning (`scripts/facade_element_detection_poc.py`)

Claude Opus 5.5 (structured output, server-side fallback aan) wijst op de 91 bruikbare gevelbeelden (1 cm/px) per
element het type en de omhullende rechthoek aan; code verfijnt de randen op de beeldgradiënt en rekent in meters.
Resultaat: `reports/quantity/facade_element_detection_poc_v1_maldenhof.json`. Kosten van de run: 133.687 input- en
42.846 outputtokens (≈ $1,40).

| Gevelzijde | Wanden | Wand m² | Ramen | Deuren | Kozijn m² | Gevelbekleding m² |
|---|---|---|---|---|---|---|
| Voorgevels | 46 | 403,5 | 42 | 7 (+1 garagedeur, 3 dakkapellen) | 90,0 | 11,6 |
| Kop-/zijgevels | 30 | 320,8 | 19 | 0 | 22,1 | 12,7 |
| Achtergevels | 15 | 112,0 | 11 | 4 (+3 balkons) | 28,7 | 1,3 |
| **Totaal** | **91** | **836,3** | **72** | **11** | **140,9** | **25,6** |

Visueel gecontroleerd op een steekproef voorgevels: kozijnen worden nauwkeurig omlijnd (buitenkozijn incl. paneel),
donkere gevelbekleding en garagedeur herkend; ramen achter struiken worden soms gemist. Het model herkent zelf blinde
kopgevels (0 elementen) en meldt occlusie in `remarks`.

**Vergelijking met het MJOP (DOC-005) — geen nauwkeurigheidsclaim.** MJOP: kozijn buiten hout 756,8 m², raamdorpels
281,2 m¹, gevelbekleding hout (voorgevel) 332 m². Automatisch op de zichtbare 54% van de buitenwand: 140,9 m² kozijn
(kozijnaandeel 17% van de verwerkte wand; voorgevels 22%). Zelfs volledig opgeschaald (≈ 260–400 m²) blijft er een
factor ~2 verschil met het MJOP. Oorzaken die nog niet te scheiden zijn:
1. **Dekking per woning**: per pand (2 woningen) is maar ~26–40 m² voorgevel verwerkt, ongeveer één woningbreedte; de rest
   ligt achter de eigen aanbouwen of is als LoD2.2-fragment afgekeurd.
2. **MJOP-conventie**: kozijn-m² = schilderwerk-kozijn-m² (756,8) en ~49% van de buitenwand zou kozijn zijn; mogelijk
   telt het MJOP panelen/borstweringen of andere zones mee. Historische MJOP-hoeveelheden zijn geen ground truth
   (`docs/remote_mjop_quantity_strategy_v1.md` §2).
3. Gemiste elementen achter begroeiing (het model markeert veel elementen als deels verborgen).

Volgende stap om dit te beslechten: één woning (bv. Maldenhof 264) handmatig of uit een maatvaste tekening opmeten
als ijkpunt, en de dekking per woning verbeteren (aanbouwen apart projecteren, meerdere panorama's per gevel combineren).

## Vervolg: PoC v2 (dekking per gevelpunt, multi-panorama, MJOP-ontleding)

Zie `reports/quantity/facade_element_detection_poc_v2_maldenhof.md`. Correcties op v1:
- `frame_area_m2` heette ten onrechte zo: het is de som van bounding boxes van openingen (`total_opening_bbox_area_m2`);
  de noemer 836,26 m² bevatte 77,81 m² die het model onbruikbaar vond.
- "Per pand is maar één woningbreedte verwerkt" klopt niet: beide adressen per pand delen één voorgevel
  (vermoedelijk beneden-/bovenwoning, niet bevestigd).
- Opnames 2024/2025 hebben in de API hoogte 0,0 en zijn niet te projecteren; vrijstaande bergings-/trappenhuisblokken
  (BAG-panden zonder VBO) ontbraken als occluder.
- De 756,8 m² uit het MJOP is geen geldige benchmark (niet gemeten, ongedefinieerd, overgenomen 2023→2026).
