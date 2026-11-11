# Gevelfoto naar hoeveelheden — prototype

Eén webpagina (`index.html`, geen installatie, geen build): foto van een gevel → herkende elementen (kozijnen, deuren, metselwerk, hwa, dakgoot, …) → hoeveelheden → aanvinken wat in het MJOP moet → export.

**Status: prototype, niet gevalideerd.** Het staat los van de gevalideerde pijplijnen in deze repository (`photo_walk/`, `agent/photo/`) en schrijft niets naar canonieke data. Alles wat eruit komt is een voorstel (`status: PROPOSED`, `booking_allowed: false`).

## Gebruiken

1. Open `index.html` in een browser (Chrome, Edge, Safari).
2. Kies een foto, maak er een met **Camera met waterpas**, of klik **Voorbeeldgevel** om het zonder foto en zonder sleutel te proberen.
3. Vul een Anthropic API-sleutel in en klik **Herken elementen**. Zonder sleutel kun je elementen zelf intekenen.
4. Stel de maat in: zoek het adres op en tik in het kaartje op de gevelzijde die op de foto staat. De maten worden dan vanzelf ingevuld. Zonder adres kun je zelf één bekende maat opgeven (bijvoorbeeld de deurhoogte). Zonder maat blijven alle meters *onbekend*. De **controlemaat** is optioneel en verandert niets aan de hoeveelheden.
5. Controleer de elementen, sleep hoekpunten goed, vink aan wat je wilt en exporteer (tekst, CSV of JSON).

## Gehoste variant (claude.ai-artifact)

`python build_artifact.py <uitvoer.html>` maakt dezelfde pagina zonder documentskelet, om als artifact op claude.ai te publiceren. Daar gebruikt de pagina voor het herkennen Claude via het account van de kijker (geen API-sleutel; de foto gaat verkleind tot ongeveer 1,1 megapixel) en slaat hij bestanden op via de host. **Maat via het adres en de camera met waterpas werken daar niet**: het platform blokkeert verzoeken naar andere websites en de toegang tot camera en bewegingssensor. Die twee werken alleen als `index.html` zelf via https wordt aangeboden.

## Wat doet wat

| Onderdeel | Hoe |
|---|---|
| Waar zit welk element | AI-model (Claude, `claude-opus-5-5`) geeft posities in pixels en een materiaalinschatting |
| Meters | vaste rekenregels in de pagina, uit de aangewezen punten en jouw referentiemaat; het model rekent niets uit |
| Maat via het adres | PDOK Locatieserver → BAG-omtrek van het pand → lengte van de aangewezen zijde. De breedte van het grootste herkende gevelvlak wordt daaraan gelijkgesteld (herkomst `AUTO_WALL_WIDTH`). Dat is een aanname: de foto moet precies deze gevel van dit pand tonen. De gele punten zijn versleepbaar (`USER_ADJUSTED`) of zelf aan te wijzen (`USER_POINTS`). De omtrek is van boven ingemeten: reken op enkele decimeters afwijking. Hoogtes uit 3D BAG worden alleen ter controle getoond, niet gebruikt |
| Aanwijzen en slepen | een punt komt waar je loslaat; een vergrootglas laat zien wat onder je vinger ligt. De foto blijft bovenaan in beeld |
| Controlemaat | vergelijkt de ingestelde schaal met een zelf opgemeten afstand en meldt het verschil; verandert de schaal niet |
| Camera met waterpas | live camerabeeld met een bolletje dat naar het midden moet; groen binnen 3° (omhoog/omlaag en scheef). De stand bij het afdrukken gaat mee in de export. Draaiing ten opzichte van de gevel (links/rechts) is met de sensoren van een telefoon niet te meten |
| Metselwerk netto | bruto vlak min de kozijnen en deuren die erin liggen |
| Schuine foto | alleen gecorrigeerd als je een grote rechthoek met bekende breedte en hoogte aanwijst (minstens 20 % van de foto); een kleine rechthoek geeft uitsluitend een schaal |
| Ontbrekende maat | blijft `null` / *onbekend*; er komt dan ook geen deelsom |

Niet aanwezig: conditiescore, gebreken, prijzen, kengetallen, NEN 2767.

## Privacy — bewuste afwijking

Elders in deze repository geldt dat foto's het toestel niet verlaten (`photo_walk/docs/privacy.md`). **Dit prototype wijkt daar bewust van af** (besluit van de eigenaar, november 2026): bij *Herken elementen* gaat de foto, verkleind tot maximaal 2000 pixels, rechtstreeks vanuit de browser naar de Anthropic API. Stuur geen foto's met herkenbare personen of kentekens. De export bevat geen foto.

Bij *Maat via het adres* gaat het ingetypte adres naar de openbare diensten van PDOK (BAG) en 3D BAG. Die vragen geen sleutel.

De API-sleutel staat alleen in de pagina en, als je dat aanvinkt, in de browseropslag van dat apparaat. Zet deze pagina daarom niet met een ingevulde sleutel op een openbare plek en gebruik bij voorkeur een sleutel met een laag bestedingslimiet. Voor echt gebruik hoort de sleutel op een server.

## Wat is getest

Met een geautomatiseerde browser (desktop en telefoonformaat): de voorbeeldgevel met bekende maten geeft de verwachte hoeveelheden, hoekpunten slepen, zelf intekenen, beide manieren van maat opgeven, de perspectiefcorrectie tegen een bekende projectie, de AI-aanroep tegen een **nagebootst** antwoord, het opzoeken van een echt adres bij PDOK/BAG/3D BAG, en de camera met een nagebootste camera en hellingsensor.

**Niet getest:** een echte aanroep van de Anthropic API, echte gevelfoto's en een echte telefoon (dus ook niet de waterpas met een echte sensor). De camera met waterpas werkt alleen als de pagina via https wordt geopend; vanaf een los bestand valt hij terug op *Foto maken of kiezen*. Hoe goed het model elementen op echte gevels aanwijst is dus onbekend; reken op missers bij dunne elementen zoals hwa's.

## Nog niet

Koppeling met Mijn MJOP (de website staat in een andere repository), meerdere foto's per gebouw, schaal uit LiDAR, automatisch rechttrekken met de gemeten kanteling, opslaan van correcties.
