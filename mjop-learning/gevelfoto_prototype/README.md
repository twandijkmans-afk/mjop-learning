# Gevelfoto naar hoeveelheden — prototype

Eén webpagina (`index.html`, geen installatie, geen build): foto van een gevel → herkende elementen (kozijnen, deuren, metselwerk, hwa, dakgoot, …) → hoeveelheden → aanvinken wat in het MJOP moet → export.

**Status: prototype, niet gevalideerd.** Het staat los van de gevalideerde pijplijnen in deze repository (`photo_walk/`, `agent/photo/`) en schrijft niets naar canonieke data. Alles wat eruit komt is een voorstel (`status: PROPOSED`, `booking_allowed: false`).

## Gebruiken

1. Open `index.html` in een browser (Chrome, Edge, Safari).
2. Kies een foto, maak er een met **Camera met waterpas**, of klik **Voorbeeldgevel** om het zonder foto en zonder sleutel te proberen.
3. Vul een Anthropic API-sleutel in en klik **Herken elementen**. Zonder sleutel kun je elementen zelf intekenen.
4. Stel de maat in: zoek het adres op en tik in het kaartje op de gevelzijde die op de foto staat (breedte uit de BAG), of geef zelf één bekende maat op (bijvoorbeeld de deurhoogte). Zonder maat blijven alle meters *onbekend*. Met een **controlemaat** toets je de schaal aan iets wat je zelf hebt opgemeten.
5. Controleer de elementen, sleep hoekpunten goed, vink aan wat je wilt en exporteer (tekst, CSV of JSON).

## Wat doet wat

| Onderdeel | Hoe |
|---|---|
| Waar zit welk element | AI-model (Claude, `claude-opus-5-5`) geeft posities in pixels en een materiaalinschatting |
| Meters | vaste rekenregels in de pagina, uit de aangewezen punten en jouw referentiemaat; het model rekent niets uit |
| Maat via het adres | PDOK Locatieserver → BAG-omtrek van het pand → lengte van de aangewezen zijde. Daarna wijs je op de foto de linker- en rechterhoek van die gevel aan. De omtrek is van boven ingemeten: reken op enkele decimeters afwijking. Hoogtes uit 3D BAG worden alleen ter controle getoond, niet gebruikt |
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
