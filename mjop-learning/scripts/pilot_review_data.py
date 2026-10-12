"""Pilot Review (Human Pilot Review Preparation v1): selectie van 10 bestaande reviewpunten met uitleg in begrijpelijke taal.

Uitsluitend bestaande review-ID's, afbeeldingen, bronverwijzingen en voorlopige classificaties; er wordt niets aan de punten zelf gewijzigd. De selectie is geen besluit en
geen goedkeuring; de gebruiker beslist per punt. Een voorstel van Claude blijft niet-bindend en nooit voorgekozen.
"""

PILOT_ORDER = ["RV-SEP-001", "RV-REL-VR-027", "RV-REL-VR-020", "RV-REL-VR-024", "RV-REL-VR-026", "RV-OBS-MAP004-012", "RV-OBS-MAP003-027",
               "RV-OBS-MAP003-009", "RV-OBS-MAP003-010", "HQ-VR-001"]

# situatie -> reviewpunt (alle acht gevraagde situaties zijn afgedekt)
SITUATIONS = {
    "Duidelijke bouwkundige penantscheiding": ["RV-SEP-001"],
    "Sterke kandidaat-objectoverlap": ["RV-REL-VR-027"],
    "Gevelsectie-overlap zonder objectbewijs": ["RV-REL-VR-020"],
    "Matige kandidaat-overlap": ["RV-REL-VR-024"],
    "Onvoldoende overlapbewijs": ["RV-REL-VR-026"],
    "Een deels zichtbaar kozijn": ["RV-OBS-MAP004-012"],
    "Een onduidelijke buitendeur": ["RV-OBS-MAP003-027"],
    "De configuratie OBS-MAP003-009/010": ["RV-OBS-MAP003-009", "RV-OBS-MAP003-010", "HQ-VR-001"],
}

# id -> dict(title, situation, reason, visible, decision, evidence, uncertain, does, doesnt, figure)
#   figure: "item" (de reviewkaart heeft een eigen uitsnede), "rel:VR-xxx" (twee uitsneden naast elkaar), "q009" (vier foto's), "plates020"
PILOT = {
    "RV-SEP-001": dict(
        title="Staat er echt een muur tussen deze twee ramen?", situation="Duidelijke bouwkundige penantscheiding", figure="item",
        reason="Een van de zes penanten; alle zes zijn visueel bevestigd. Een goed eerste punt om te wennen aan het formulier.",
        visible="Op foto MAP-003 staan in de bovenste rij twee ramen naast elkaar: links een groot tweedelig kozijn, rechts een smal raam. Ertussen is een stuk gewone baksteenmuur (een penant) te zien.",
        decision="Kies CONFIRM als het metselwerk de twee ramen echt scheidt (twee afzonderlijke openingen), REJECT als je het toch als een opening ziet, of UNDECIDABLE / NEEDS_BETTER_PHOTO.",
        evidence="Bij de kwaliteitscontrole is op de originele pixels gezien dat het metselwerk doorlopend zichtbaar is en dat beide kaders kloppen. Dit is dezelfde situatie als bij foto 2, waar het besluit PCD-00004 al bepaalt dat zichtbaar metselwerk tussen kozijnen scheidt.",
        uncertain="Boven de penant loopt een dunne lichte strip die de ramen bovenaan verbindt (waarschijnlijk een latei of afdekprofiel). Onder die strip is het metselwerk ononderbroken.",
        does="Je legt voorlopig vast dat deze twee ramen als afzonderlijke openingen worden gezien.",
        doesnt="Het maakt geen instance, geen telling en geen totaal; de telregel van foto 2 verandert niet; er is geen koppeling met een pand."),
    "RV-REL-VR-027": dict(
        title="Is dit hetzelfde kozijn op twee foto's?", situation="Sterke kandidaat-objectoverlap", figure="rel:VR-027",
        reason="Duidelijk voorbeeld waarbij het bewijs sterk is: een kozijn met herkenbare merktekens, gezien vanaf twee standpunten.",
        visible="Het tweedelige kozijn boven de kap staat op MAP-003 (observatie 011) en op MAP-004 (observatie 006). De twee uitsneden staan naast elkaar.",
        decision="SAME betekent hier: de twee observaties tonen vermoedelijk hetzelfde fysieke kozijn (een kandidaat). DIFFERENT: het zijn twee verschillende kozijnen. UNDECIDABLE: niet te zeggen.",
        evidence="Sterke visuele ondersteuning: dezelfde merktekens op de kozijnstijl, dezelfde stickers en hetzelfde gordijn. De automatische kenmerkmatch (alleen hulpmiddel) vindt 39 overeenkomsten en dit is het beste paar in beide richtingen.",
        uncertain="De woningen zijn identiek, dus alleen details maken het verschil; je moet zelf kijken of je de merktekens herkent.",
        does="Je legt voorlopig vast dat dit paar als hetzelfde kandidaat-object geldt, zodat het later niet dubbel wordt geteld.",
        doesnt="Er wordt niets samengevoegd en er ontstaat geen instance of unieke teller; er is geen pandkoppeling."),
    "RV-REL-VR-020": dict(
        title="Tonen beide foto's hetzelfde stuk gevel?", situation="Gevelsectie-overlap zonder objectbewijs", figure="rel:VR-020",
        reason="Laat het verschil zien tussen dezelfde gevelsectie en hetzelfde kozijn: hier gaat het alleen om de muur.",
        visible="Op MAP-003 en MAP-004 zijn de huisnummerplaten 280, 278 en 276 met de bijbehorende entreemuren te zien, in dezelfde volgorde.",
        decision="SAME betekent hier uitsluitend: beide foto's tonen dezelfde gevelsectie. DIFFERENT: andere gevelsecties. UNDECIDABLE.",
        evidence="De platen zijn in beide foto's leesbaar (alle 11 plaatlezingen zijn opnieuw gecontroleerd) en staan in dezelfde volgorde.",
        uncertain="Niets over een los kozijn of een deur: dit is gevelniveau. Een plaat bewijst alleen de muur waaraan hij hangt (APP-001).",
        does="Je legt vast dat de twee foto's op deze muur overlappen.",
        doesnt="Het zegt niet dat een kozijn hetzelfde kozijn is (dat is een apart objectpunt), het bewijst geen pand voor kozijnen en maakt geen instance."),
    "RV-REL-VR-024": dict(
        title="Zelfde raam links van de kap? (matig bewijs)", situation="Matige kandidaat-overlap", figure="rel:VR-024",
        reason="Voorbeeld waarbij de indeling klopt maar uniek bewijs ontbreekt: jij moet zelf wegen.",
        visible="Een raam met een open vleugel rechts en een wit onderpaneel, links van de rechter kap. MAP-003 (observatie 018) en MAP-004 (observatie 013).",
        decision="SAME / DIFFERENT / UNDECIDABLE, met dezelfde betekenis als bij het vorige objectpunt.",
        evidence="Matige visuele ondersteuning: dezelfde indeling, positie en spiegeling van een tak; de kenmerkmatch (28) is het beste paar in beide richtingen.",
        uncertain="De gordijnen lijken op de twee foto's verschillend (hoek en glans) en er is geen uniek kenmerk. Rechts van de kap staat een vrijwel identiek raam.",
        does="Bij SAME leg je voorlopig vast dat je dit als hetzelfde kandidaat-object ziet.",
        doesnt="Geen samenvoeging, geen instance, geen telling, geen pand. Kies liever UNDECIDABLE dan SAME als je het zelf niet overtuigend ziet."),
    "RV-REL-VR-026": dict(
        title="Zelfde raam rechts van de kap? (onvoldoende bewijs)", situation="Onvoldoende overlapbewijs", figure="rel:VR-026",
        reason="Voorbeeld waarbij de foto's te weinig tonen: hier hoort UNDECIDABLE het gewone antwoord te zijn.",
        visible="Links (MAP-003, observatie 020) is alleen een smalle strook van een raam te zien achter de lantaarnpaal en de kap. Rechts (MAP-004, observatie 016) is het hele raam met open vleugel zichtbaar.",
        decision="SAME / DIFFERENT / UNDECIDABLE. Het voorstel van Claude is nu UNDECIDABLE (eerder SAME; gecorrigeerd na de kwaliteitscontrole).",
        evidence="Onvoldoende bewijs: van het raam op MAP-003 is bijna niets zichtbaar en er is geen herkenbaar kenmerk om te vergelijken.",
        uncertain="Alles: het kan hetzelfde raam zijn, maar identieke woningen maken een verwisseling mogelijk.",
        does="UNDECIDABLE legt vast dat deze foto's de vraag niet kunnen beantwoorden; een nieuwe foto kan dat later wel.",
        doesnt="Er gaat niets verloren en er wordt niets gekoppeld. Kies geen SAME zonder bewijs; er ontstaat ook dan geen instance of pandkoppeling."),
    "RV-OBS-MAP004-012": dict(
        title="Klopt de aanduiding van dit afgesneden raam?", situation="Een deels zichtbaar kozijn", figure="item",
        reason="Het eenvoudigste voorbeeld van een deels zichtbaar kozijn: afgesneden door de beeldrand.",
        visible="Aan de rechterrand van MAP-004 is het linkerdeel van een raam te zien (kozijn, ruit en rolkast). De rest valt buiten de foto.",
        decision="CONFIRM: dit is een deels zichtbaar raam zoals aangeduid. REJECT: het klopt niet. UNDECIDABLE of NEEDS_BETTER_PHOTO. Het voorstel van Claude is UNDECIDABLE (er valt niet meer over te zeggen dan dat er een strook is).",
        evidence="Bij de kwaliteitscontrole is vastgesteld dat het raam zichtbaar bestaat, van het type raam is en gedeeltelijk zichtbaar is; het kader klopt.",
        uncertain="Het is niet te koppelen aan het rechterpand op MAP-003, niet meetbaar en de pandkoppeling is onbewezen.",
        does="Je legt voorlopig vast dat hier een deels zichtbaar raam staat.",
        doesnt="Het is geen telling, geen instance, geen maat en geen pandkoppeling."),
    "RV-OBS-MAP003-027": dict(
        title="Is dit een buitendeur? (te donker)", situation="Een onduidelijke buitendeur", figure="item",
        reason="Voorbeeld van een object dat de foto niet laat beoordelen.",
        visible="Rechts van huisnummerplaat 278 is een zeer donker rechthoekig vlak te zien in de entreenis. Er zijn twee donkere vlakken naast elkaar.",
        decision="Het voorstel van Claude is NEEDS_BETTER_PHOTO (eerder UNDECIDABLE; gecorrigeerd). Je kunt dat volgen, UNDECIDABLE kiezen, of REJECT als je er geen opening in ziet.",
        evidence="Bij de kwaliteitscontrole bleek er geen contrast: type, volledigheid en afzonderlijke herkenbaarheid zijn niet vast te stellen.",
        uncertain="Of het een deur of een donkere doorgang is, en hoe groot het object is. De kleur uit de oude notitie is op deze foto niet te controleren.",
        does="Je vraagt om een betere foto van deze entreenis.",
        doesnt="Het telt niet mee, er wordt niets aan de deur op MAP-004 gekoppeld en er is geen pandkoppeling (plaat 278 bewijst alleen de muur)."),
    "RV-OBS-MAP003-009": dict(
        title="Het smalle element links van het hoofdkozijn", situation="De configuratie OBS-MAP003-009/010", figure="q009",
        reason="Eerste van drie punten over dezelfde configuratie: het smalle linkerelement. Hier zit ook het gevonden label-probleem (zie correctievoorstel).",
        visible="Links van het hoofdkozijn zit een smal element met een open vleugel. De rechterkant wordt op MAP-003 deels bedekt door de open, blauw omrande vleugel van het hoofdkozijn.",
        decision="CONFIRM: de observatie klopt als voorlopige zichtbare opening. UNDECIDABLE (voorstel van Claude) als je het te onzeker vindt. Of het een apart kozijn is, beoordeel je bij het laatste pilotpunt (HQ-VR-001).",
        evidence="In foto 2 is het element al besloten als apart kozijn (FC-M2-006-A). MAP-013 laat metselwerk tussen dit element en het hoofdkozijn zien. Op MAP-003 en MAP-004 zelf is dat niet te beslissen.",
        uncertain="Het bestaande label FULL klopt niet helemaal: de rechterrand is bedekt. Een correctievoorstel (FULL naar PARTIAL) staat in het pilotrapport en is nog niet doorgevoerd.",
        does="Je legt voorlopig vast dat hier een zichtbare opening is.",
        doesnt="Geen nieuwe instance, geen dubbele telling met het hoofdkozijn, het foto-2-besluit verandert niet en er is geen pandkoppeling."),
    "RV-OBS-MAP003-010": dict(
        title="Het hoofdkozijn met gordijn en twee open vleugels", situation="De configuratie OBS-MAP003-009/010", figure="q009",
        reason="Tweede punt van de configuratie: dit kozijn is wel eenduidig herkenbaar.",
        visible="Een groot kozijn met een gordijn, een blauw omrande open vleugel links en een open vleugel rechts. Vleugels en kozijnstijlen binnen een kozijn scheiden niet.",
        decision="CONFIRM: de observatie klopt als een voorlopige zichtbare opening (een opening). REJECT, UNDECIDABLE of NEEDS_BETTER_PHOTO.",
        evidence="Sterk: dezelfde combinatie van gordijn en open vleugels is in vier foto's (MAP-002, 003, 004 en 013) terug te vinden.",
        uncertain="Weinig; alleen de kijkhoek verschilt per foto.",
        does="Je bevestigt voorlopig dit kozijn als zichtbare opening.",
        doesnt="Geen instance, geen telling, geen pandkoppeling; het foto-2-besluit (FC-M2-006-BC) verandert niet."),
    "HQ-VR-001": dict(
        title="Is het smalle element een apart kozijn of een vleugel?", situation="De configuratie OBS-MAP003-009/010", figure="none",
        reason="Derde punt van de configuratie: de eigenlijke vraag waar de foto's zelf niet uitkomen. Gebruik de afbeelding bij punt 8.",
        visible="Zie de vier foto's bij het punt over het smalle element: bij MAP-002 en MAP-013 is metselwerk tussen het smalle element en het hoofdkozijn te zien, bij MAP-003 en MAP-004 bedekt een open vleugel dat.",
        decision="Lees de keuzes zo: CONFIRM = apart kozijn (zoals foto 2); REJECT = vleugel van het hoofdkozijn; UNDECIDABLE = niet te zeggen; NEEDS_BETTER_PHOTO = betere foto nodig. Het voorstel van Claude is UNDECIDABLE.",
        evidence="MAP-013 en foto 2 ondersteunen 'apart kozijn'. Op MAP-003 en MAP-004 is het door de open vleugel niet af te leiden.",
        uncertain="Een frontale foto zou het beslissen. De bestaande foto-2-telling blijft dit gewoon als apart kozijn volgen.",
        does="Je geeft een voorlopig antwoord op de telvraag voor MAP-003/004 (niet voor foto 2).",
        doesnt="Het verandert foto 2 niet, maakt geen instance en telt niets automatisch dubbel of apart; er is geen pandkoppeling."),
}
