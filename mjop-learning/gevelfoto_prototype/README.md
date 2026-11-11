# Gevelfoto naar hoeveelheden — prototype

Eén webpagina (`index.html`, geen installatie, geen build): foto van een gevel → herkende elementen (kozijnen, deuren, metselwerk, hwa, dakgoot, …) → hoeveelheden → aanvinken wat in het MJOP moet → export.

**Status: prototype, niet gevalideerd.** Het staat los van de gevalideerde pijplijnen in deze repository (`photo_walk/`, `agent/photo/`) en schrijft niets naar canonieke data. Alles wat eruit komt is een voorstel (`status: PROPOSED`, `booking_allowed: false`).

## Gebruiken

1. Open `index.html` in een browser (Chrome, Edge, Safari).
2. Kies een foto, of klik **Voorbeeldgevel** om het zonder foto en zonder sleutel te proberen.
3. Vul een Anthropic API-sleutel in en klik **Herken elementen**. Zonder sleutel kun je elementen zelf intekenen.
4. Geef één bekende maat op (bijvoorbeeld de deurhoogte). Zonder maat blijven alle meters *onbekend*.
5. Controleer de elementen, sleep hoekpunten goed, vink aan wat je wilt en exporteer (tekst, CSV of JSON).

## Wat doet wat

| Onderdeel | Hoe |
|---|---|
| Waar zit welk element | AI-model (Claude, `claude-opus-5-5`) geeft posities in pixels en een materiaalinschatting |
| Meters | vaste rekenregels in de pagina, uit de aangewezen punten en jouw referentiemaat; het model rekent niets uit |
| Metselwerk netto | bruto vlak min de kozijnen en deuren die erin liggen |
| Schuine foto | alleen gecorrigeerd als je een grote rechthoek met bekende breedte en hoogte aanwijst (minstens 20 % van de foto); een kleine rechthoek geeft uitsluitend een schaal |
| Ontbrekende maat | blijft `null` / *onbekend*; er komt dan ook geen deelsom |

Niet aanwezig: conditiescore, gebreken, prijzen, kengetallen, NEN 2767.

## Privacy — bewuste afwijking

Elders in deze repository geldt dat foto's het toestel niet verlaten (`photo_walk/docs/privacy.md`). **Dit prototype wijkt daar bewust van af** (besluit van de eigenaar, november 2026): bij *Herken elementen* gaat de foto, verkleind tot maximaal 2000 pixels, rechtstreeks vanuit de browser naar de Anthropic API. Stuur geen foto's met herkenbare personen of kentekens. De export bevat geen foto.

De API-sleutel staat alleen in de pagina en, als je dat aanvinkt, in de browseropslag van dat apparaat. Zet deze pagina daarom niet met een ingevulde sleutel op een openbare plek en gebruik bij voorkeur een sleutel met een laag bestedingslimiet. Voor echt gebruik hoort de sleutel op een server.

## Wat is getest

Met een geautomatiseerde browser (desktop en telefoonformaat): de voorbeeldgevel met bekende maten geeft de verwachte hoeveelheden, hoekpunten slepen, zelf intekenen, beide manieren van maat opgeven, de perspectiefcorrectie tegen een bekende projectie, en de AI-aanroep tegen een **nagebootst** antwoord.

**Niet getest:** een echte aanroep van de Anthropic API, echte gevelfoto's en een echte telefoon. Hoe goed het model elementen op echte gevels aanwijst is dus onbekend; reken op missers bij dunne elementen zoals hwa's.

## Nog niet

Koppeling met Mijn MJOP (de website staat in een andere repository), meerdere foto's per gebouw, automatische schaal (LiDAR of BAG), opslaan van correcties.
