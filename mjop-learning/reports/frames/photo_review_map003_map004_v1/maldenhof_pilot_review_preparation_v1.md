# Maldenhof Human Pilot Review Preparation v1

Pakketversie `human_visual_decision_pack_v1.2.0` (PR #41). Dit is een **voorbereiding**: de selectie is geen besluit en geen goedkeuring. Alle niet-geselecteerde punten blijven OPEN, alle 48 APP-besluiten blijven OPEN en er ontstaan geen instances, geen samenvoeging, geen unieke totalen, geen BAG-pandkoppelingen, geen kosten en geen wijziging aan de bevroren foto-2-gegevens.

## 1. Geselecteerde reviewpunten (10)

| # | Review-ID | Situatie | Reden van selectie | Voorstel Claude (niet-bindend) | Kwaliteitsstatus |
|---|---|---|---|---|---|
| 1 | RV-SEP-001 | Duidelijke bouwkundige penantscheiding | Een van de zes penanten; alle zes zijn visueel bevestigd. Een goed eerste punt om te wennen aan het formulier. | CONFIRM | VISUALLY_SUPPORTED |
| 2 | RV-REL-VR-027 | Sterke kandidaat-objectoverlap | Duidelijk voorbeeld waarbij het bewijs sterk is: een kozijn met herkenbare merktekens, gezien vanaf twee standpunten. | SAME | VISUALLY_SUPPORTED |
| 3 | RV-REL-VR-020 | Gevelsectie-overlap zonder objectbewijs | Laat het verschil zien tussen dezelfde gevelsectie en hetzelfde kozijn: hier gaat het alleen om de muur. | SAME | VISUALLY_SUPPORTED |
| 4 | RV-REL-VR-024 | Matige kandidaat-overlap | Voorbeeld waarbij de indeling klopt maar uniek bewijs ontbreekt: jij moet zelf wegen. | SAME | NEEDS_MANUAL_REVIEW |
| 5 | RV-REL-VR-026 | Onvoldoende overlapbewijs | Voorbeeld waarbij de foto's te weinig tonen: hier hoort UNDECIDABLE het gewone antwoord te zijn. | UNDECIDABLE | NEEDS_BETTER_PHOTO |
| 6 | RV-OBS-MAP004-012 | Een deels zichtbaar kozijn | Het eenvoudigste voorbeeld van een deels zichtbaar kozijn: afgesneden door de beeldrand. | UNDECIDABLE | NEEDS_MANUAL_REVIEW |
| 7 | RV-OBS-MAP003-027 | Een onduidelijke buitendeur | Voorbeeld van een object dat de foto niet laat beoordelen. | NEEDS_BETTER_PHOTO | NEEDS_BETTER_PHOTO |
| 8 | RV-OBS-MAP003-009 | De configuratie OBS-MAP003-009/010 | Eerste van drie punten over dezelfde configuratie: het smalle linkerelement. Hier zit ook het gevonden label-probleem (zie correctievoorstel). | UNDECIDABLE | NEEDS_MANUAL_REVIEW |
| 9 | RV-OBS-MAP003-010 | De configuratie OBS-MAP003-009/010 | Tweede punt van de configuratie: dit kozijn is wel eenduidig herkenbaar. | CONFIRM | VISUALLY_SUPPORTED |
| 10 | HQ-VR-001 | De configuratie OBS-MAP003-009/010 | Derde punt van de configuratie: de eigenlijke vraag waar de foto's zelf niet uitkomen. Gebruik de afbeelding bij punt 8. | UNDECIDABLE | NEEDS_MANUAL_REVIEW |

Alle acht gevraagde situaties zijn afgedekt (de configuratie OBS-MAP003-009/010 met drie punten). Gebruikt zijn uitsluitend bestaande review-ID's, afbeeldingen, bronverwijzingen en voorlopige classificaties; de reviewkaarten zelf zijn niet gewijzigd.

## 2. Uitleg per punt

### 1. RV-SEP-001: Staat er echt een muur tussen deze twee ramen?

- **Wat is zichtbaar:** Op foto MAP-003 staan in de bovenste rij twee ramen naast elkaar: links een groot tweedelig kozijn, rechts een smal raam. Ertussen is een stuk gewone baksteenmuur (een penant) te zien.
- **Welke beslissing is nodig:** Kies CONFIRM als het metselwerk de twee ramen echt scheidt (twee afzonderlijke openingen), REJECT als je het toch als een opening ziet, of UNDECIDABLE / NEEDS_BETTER_PHOTO.
- **Welk bewijs ondersteunt het voorstel:** Bij de kwaliteitscontrole is op de originele pixels gezien dat het metselwerk doorlopend zichtbaar is en dat beide kaders kloppen. Dit is dezelfde situatie als bij foto 2, waar het besluit PCD-00004 al bepaalt dat zichtbaar metselwerk tussen kozijnen scheidt.
- **Wat is nog onzeker:** Boven de penant loopt een dunne lichte strip die de ramen bovenaan verbindt (waarschijnlijk een latei of afdekprofiel). Onder die strip is het metselwerk ononderbroken.
- **Wat de keuze wel doet:** Je legt voorlopig vast dat deze twee ramen als afzonderlijke openingen worden gezien.
- **Wat de keuze niet doet:** Het maakt geen instance, geen telling en geen totaal; de telregel van foto 2 verandert niet; er is geen koppeling met een pand.

### 2. RV-REL-VR-027: Is dit hetzelfde kozijn op twee foto's?

- **Wat is zichtbaar:** Het tweedelige kozijn boven de kap staat op MAP-003 (observatie 011) en op MAP-004 (observatie 006). De twee uitsneden staan naast elkaar.
- **Welke beslissing is nodig:** SAME betekent hier: de twee observaties tonen vermoedelijk hetzelfde fysieke kozijn (een kandidaat). DIFFERENT: het zijn twee verschillende kozijnen. UNDECIDABLE: niet te zeggen.
- **Welk bewijs ondersteunt het voorstel:** Sterke visuele ondersteuning: dezelfde merktekens op de kozijnstijl, dezelfde stickers en hetzelfde gordijn. De automatische kenmerkmatch (alleen hulpmiddel) vindt 39 overeenkomsten en dit is het beste paar in beide richtingen.
- **Wat is nog onzeker:** De woningen zijn identiek, dus alleen details maken het verschil; je moet zelf kijken of je de merktekens herkent.
- **Wat de keuze wel doet:** Je legt voorlopig vast dat dit paar als hetzelfde kandidaat-object geldt, zodat het later niet dubbel wordt geteld.
- **Wat de keuze niet doet:** Er wordt niets samengevoegd en er ontstaat geen instance of unieke teller; er is geen pandkoppeling.

### 3. RV-REL-VR-020: Tonen beide foto's hetzelfde stuk gevel?

- **Wat is zichtbaar:** Op MAP-003 en MAP-004 zijn de huisnummerplaten 280, 278 en 276 met de bijbehorende entreemuren te zien, in dezelfde volgorde.
- **Welke beslissing is nodig:** SAME betekent hier uitsluitend: beide foto's tonen dezelfde gevelsectie. DIFFERENT: andere gevelsecties. UNDECIDABLE.
- **Welk bewijs ondersteunt het voorstel:** De platen zijn in beide foto's leesbaar (alle 11 plaatlezingen zijn opnieuw gecontroleerd) en staan in dezelfde volgorde.
- **Wat is nog onzeker:** Niets over een los kozijn of een deur: dit is gevelniveau. Een plaat bewijst alleen de muur waaraan hij hangt (APP-001).
- **Wat de keuze wel doet:** Je legt vast dat de twee foto's op deze muur overlappen.
- **Wat de keuze niet doet:** Het zegt niet dat een kozijn hetzelfde kozijn is (dat is een apart objectpunt), het bewijst geen pand voor kozijnen en maakt geen instance.

### 4. RV-REL-VR-024: Zelfde raam links van de kap? (matig bewijs)

- **Wat is zichtbaar:** Een raam met een open vleugel rechts en een wit onderpaneel, links van de rechter kap. MAP-003 (observatie 018) en MAP-004 (observatie 013).
- **Welke beslissing is nodig:** SAME / DIFFERENT / UNDECIDABLE, met dezelfde betekenis als bij het vorige objectpunt.
- **Welk bewijs ondersteunt het voorstel:** Matige visuele ondersteuning: dezelfde indeling, positie en spiegeling van een tak; de kenmerkmatch (28) is het beste paar in beide richtingen.
- **Wat is nog onzeker:** De gordijnen lijken op de twee foto's verschillend (hoek en glans) en er is geen uniek kenmerk. Rechts van de kap staat een vrijwel identiek raam.
- **Wat de keuze wel doet:** Bij SAME leg je voorlopig vast dat je dit als hetzelfde kandidaat-object ziet.
- **Wat de keuze niet doet:** Geen samenvoeging, geen instance, geen telling, geen pand. Kies liever UNDECIDABLE dan SAME als je het zelf niet overtuigend ziet.

### 5. RV-REL-VR-026: Zelfde raam rechts van de kap? (onvoldoende bewijs)

- **Wat is zichtbaar:** Links (MAP-003, observatie 020) is alleen een smalle strook van een raam te zien achter de lantaarnpaal en de kap. Rechts (MAP-004, observatie 016) is het hele raam met open vleugel zichtbaar.
- **Welke beslissing is nodig:** SAME / DIFFERENT / UNDECIDABLE. Het voorstel van Claude is nu UNDECIDABLE (eerder SAME; gecorrigeerd na de kwaliteitscontrole).
- **Welk bewijs ondersteunt het voorstel:** Onvoldoende bewijs: van het raam op MAP-003 is bijna niets zichtbaar en er is geen herkenbaar kenmerk om te vergelijken.
- **Wat is nog onzeker:** Alles: het kan hetzelfde raam zijn, maar identieke woningen maken een verwisseling mogelijk.
- **Wat de keuze wel doet:** UNDECIDABLE legt vast dat deze foto's de vraag niet kunnen beantwoorden; een nieuwe foto kan dat later wel.
- **Wat de keuze niet doet:** Er gaat niets verloren en er wordt niets gekoppeld. Kies geen SAME zonder bewijs; er ontstaat ook dan geen instance of pandkoppeling.

### 6. RV-OBS-MAP004-012: Klopt de aanduiding van dit afgesneden raam?

- **Wat is zichtbaar:** Aan de rechterrand van MAP-004 is het linkerdeel van een raam te zien (kozijn, ruit en rolkast). De rest valt buiten de foto.
- **Welke beslissing is nodig:** CONFIRM: dit is een deels zichtbaar raam zoals aangeduid. REJECT: het klopt niet. UNDECIDABLE of NEEDS_BETTER_PHOTO. Het voorstel van Claude is UNDECIDABLE (er valt niet meer over te zeggen dan dat er een strook is).
- **Welk bewijs ondersteunt het voorstel:** Bij de kwaliteitscontrole is vastgesteld dat het raam zichtbaar bestaat, van het type raam is en gedeeltelijk zichtbaar is; het kader klopt.
- **Wat is nog onzeker:** Het is niet te koppelen aan het rechterpand op MAP-003, niet meetbaar en de pandkoppeling is onbewezen.
- **Wat de keuze wel doet:** Je legt voorlopig vast dat hier een deels zichtbaar raam staat.
- **Wat de keuze niet doet:** Het is geen telling, geen instance, geen maat en geen pandkoppeling.

### 7. RV-OBS-MAP003-027: Is dit een buitendeur? (te donker)

- **Wat is zichtbaar:** Rechts van huisnummerplaat 278 is een zeer donker rechthoekig vlak te zien in de entreenis. Er zijn twee donkere vlakken naast elkaar.
- **Welke beslissing is nodig:** Het voorstel van Claude is NEEDS_BETTER_PHOTO (eerder UNDECIDABLE; gecorrigeerd). Je kunt dat volgen, UNDECIDABLE kiezen, of REJECT als je er geen opening in ziet.
- **Welk bewijs ondersteunt het voorstel:** Bij de kwaliteitscontrole bleek er geen contrast: type, volledigheid en afzonderlijke herkenbaarheid zijn niet vast te stellen.
- **Wat is nog onzeker:** Of het een deur of een donkere doorgang is, en hoe groot het object is. De kleur uit de oude notitie is op deze foto niet te controleren.
- **Wat de keuze wel doet:** Je vraagt om een betere foto van deze entreenis.
- **Wat de keuze niet doet:** Het telt niet mee, er wordt niets aan de deur op MAP-004 gekoppeld en er is geen pandkoppeling (plaat 278 bewijst alleen de muur).

### 8. RV-OBS-MAP003-009: Het smalle element links van het hoofdkozijn

- **Wat is zichtbaar:** Links van het hoofdkozijn zit een smal element met een open vleugel. De rechterkant wordt op MAP-003 deels bedekt door de open, blauw omrande vleugel van het hoofdkozijn.
- **Welke beslissing is nodig:** CONFIRM: de observatie klopt als voorlopige zichtbare opening. UNDECIDABLE (voorstel van Claude) als je het te onzeker vindt. Of het een apart kozijn is, beoordeel je bij het laatste pilotpunt (HQ-VR-001).
- **Welk bewijs ondersteunt het voorstel:** In foto 2 is het element al besloten als apart kozijn (FC-M2-006-A). MAP-013 laat metselwerk tussen dit element en het hoofdkozijn zien. Op MAP-003 en MAP-004 zelf is dat niet te beslissen.
- **Wat is nog onzeker:** Het bestaande label FULL klopt niet helemaal: de rechterrand is bedekt. Een correctievoorstel (FULL naar PARTIAL) staat in het pilotrapport en is nog niet doorgevoerd.
- **Wat de keuze wel doet:** Je legt voorlopig vast dat hier een zichtbare opening is.
- **Wat de keuze niet doet:** Geen nieuwe instance, geen dubbele telling met het hoofdkozijn, het foto-2-besluit verandert niet en er is geen pandkoppeling.

### 9. RV-OBS-MAP003-010: Het hoofdkozijn met gordijn en twee open vleugels

- **Wat is zichtbaar:** Een groot kozijn met een gordijn, een blauw omrande open vleugel links en een open vleugel rechts. Vleugels en kozijnstijlen binnen een kozijn scheiden niet.
- **Welke beslissing is nodig:** CONFIRM: de observatie klopt als een voorlopige zichtbare opening (een opening). REJECT, UNDECIDABLE of NEEDS_BETTER_PHOTO.
- **Welk bewijs ondersteunt het voorstel:** Sterk: dezelfde combinatie van gordijn en open vleugels is in vier foto's (MAP-002, 003, 004 en 013) terug te vinden.
- **Wat is nog onzeker:** Weinig; alleen de kijkhoek verschilt per foto.
- **Wat de keuze wel doet:** Je bevestigt voorlopig dit kozijn als zichtbare opening.
- **Wat de keuze niet doet:** Geen instance, geen telling, geen pandkoppeling; het foto-2-besluit (FC-M2-006-BC) verandert niet.

### 10. HQ-VR-001: Is het smalle element een apart kozijn of een vleugel?

- **Wat is zichtbaar:** Zie de vier foto's bij het punt over het smalle element: bij MAP-002 en MAP-013 is metselwerk tussen het smalle element en het hoofdkozijn te zien, bij MAP-003 en MAP-004 bedekt een open vleugel dat.
- **Welke beslissing is nodig:** Lees de keuzes zo: CONFIRM = apart kozijn (zoals foto 2); REJECT = vleugel van het hoofdkozijn; UNDECIDABLE = niet te zeggen; NEEDS_BETTER_PHOTO = betere foto nodig. Het voorstel van Claude is UNDECIDABLE.
- **Welk bewijs ondersteunt het voorstel:** MAP-013 en foto 2 ondersteunen 'apart kozijn'. Op MAP-003 en MAP-004 is het door de open vleugel niet af te leiden.
- **Wat is nog onzeker:** Een frontale foto zou het beslissen. De bestaande foto-2-telling blijft dit gewoon als apart kozijn volgen.
- **Wat de keuze wel doet:** Je geeft een voorlopig antwoord op de telvraag voor MAP-003/004 (niet voor foto 2).
- **Wat de keuze niet doet:** Het verandert foto 2 niet, maakt geen instance en telt niets automatisch dubbel of apart; er is geen pandkoppeling.

## 3. Correctievoorstel OBS-MAP003-009 (zichtbaarheid FULL tegenover bedekte rechterrand)

- **Bevinding:** Het label FULL betekent dat de volledige omtrek zichtbaar is. Op MAP-003 wordt de rechterrand van het smalle element in het bovenste deel bedekt door de open, blauw omrande vleugel van OBS-MAP003-010; het kader van 009 eindigt precies waar het kader van 010 begint (x=842) en de blauwe vleugel valt voor een deel binnen het kader van 009. Linkerzijde, boven- en onderrand zijn wel zichtbaar.
- **Voorstel:** `visibility` FULL naar **PARTIAL** voor OBS-MAP003-009. Status: `PROPOSED_NOT_APPLIED`. afzonderlijke menselijke goedkeuring; de bronobservatie in maldenhof_visual_photo_review_map003_map004_v1.json is NIET gewijzigd.
- **Onderzoek:** In MAP-003/MAP-004 raken of overlappen alleen de kaders van OBS-MAP003-009 en -010 elkaar (breedte 0 px); geen andere observatie heeft deze inconsistentie. MAP-013 REF-004 toont het element wel volledig met metselwerk ernaast; foto 2 (FC-M2-006-A) is FULL en blijft bevroren.
- **Alternatief:** FULL behouden met een extra notitie 'rechterrand bedekt door open vleugel van 010'; de zichtbaarheidsdefinitie (FULL = volledige omtrek zichtbaar) pleit voor PARTIAL.
- **Gevolgen bij doorvoeren:** Observaties staan buiten de instance-store en tellen in geen enkel totaal; het is een label-correctie voor de leesbaarheid. Geen telling verandert, geen instance, geen pandkoppeling, foto 2 ongewijzigd.
- Bestand: `pilot_review/maldenhof_obs_map003_009_visibility_correction_proposal_v1.json`; figuur: `pilot_review/PQ-009_visibility_zoom.jpg`. De bronobservatie (`maldenhof_visual_photo_review_map003_map004_v1.json`/`.md`) is niet aangepast.

## 4. Scheiding van bewijs, goedkeuring, objectidentiteit en pandkoppeling

| Soort uitspraak | Waar vastgelegd | Wat het niet is |
|---|---|---|
| Visueel bewijs | Kwaliteitscontrole (`QUALITY`-status, bewijsklasse) | geen besluit |
| Menselijk (voorlopig) besluit | alleen in `human` van de export, `decision_source: HUMAN` | niet toegepast; geen goedkeuring van een APP-besluit |
| Fysieke objectidentiteit | alleen als kandidaat (`SAME_PHYSICAL_OBJECT_CANDIDATE`) | geen merge, geen instance |
| Gevelsectie | `SAME_FACADE_SECTION` | niet hetzelfde kozijn |
| BAG-pandkoppeling | niet aanwezig voor elk pilotpunt (ONBEWEZEN) | nooit afgeleid uit een plaat of overlap |

## 5. Gebruik in de browser

Open de HTML. Boven aan staat de sectie **Pilot Review**; de knop **Pilot Review** in de kopbalk toont uitsluitend deze 10 punten en het exportgedeelte. Bij het exporteren kies je omvang **Alleen Pilot Review** (deelbestand) of **Alles**. Niet-geselecteerde punten blijven OPEN.

## 6. Tests

`tests/test_human_visual_decision_pack.py` (selectie, filter, export naar JSON, overige punten OPEN, import van een eerdere v1.1.0-export), `tests/test_p1_visual_quality_review.py`, `tests/test_pilot_review_preparation.py` (selectie, correctievoorstel, brondata onveranderd) en `tests/test_scope_guard.py`.
