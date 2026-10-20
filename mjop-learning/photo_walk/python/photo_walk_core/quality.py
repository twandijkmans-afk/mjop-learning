"""Kwaliteitspoorten: elke afwijzing of waarschuwing heeft een code, ernst en een concrete opnamestructie (NL).

BLOCKING  -> er wordt GEEN metrische waarde uit dit pad gerapporteerd.
ADVISORY  -> waarde blijft zichtbaar, maar `review_required` en status kan niet 'MEASURED' zijn.
Er is bewust geen enkel samengesteld 'confidence-percentage'.
"""

BLOCKING = "BLOCKING"
ADVISORY = "ADVISORY"

FLAGS = {
    "TRACKING_LOST": (BLOCKING, "AR-tracking was niet 'normal' tijdens dit beeld. Beweeg langzaam, richt op een gevel met textuur en herhaal de opname."),
    "NO_DEPTH": (BLOCKING, "Geen dieptebeeld voor dit standpunt; gebruik een tweede standpunt (niveau B) of voer een referentiemaat in (niveau C)."),
    "CORNER_ORDER_INVALID": (BLOCKING, "De vier hoeken vormen geen simpele vierhoek (verwisselde of dubbele hoeken). Tik de hoeken rond: linksboven, rechtsboven, rechtsonder, linksonder."),
    "CORNER_OUTSIDE_IMAGE": (BLOCKING, "Een hoek ligt buiten het beeld. Sta verder weg zodat het hele kozijn in beeld is."),
    "DEPTH_COVERAGE_LOW": (BLOCKING, "Te weinig geldige dieptepunten rond het kozijn. Ga dichterbij (binnen ca. 5 m), vermijd direct tegenlicht en scan de gevel rond het kozijn rustig."),
    "DEPTH_RANGE_EXCEEDED": (BLOCKING, "Dieptepunten liggen buiten het bereik van de sensor. Ga dichterbij staan."),
    "MIXED_FACADE_DEPTH": (BLOCKING, "Het gevelvlak rond het kozijn is niet vlak (verspringingen, balkon, begroeiing). Kies een standpunt met vrij zicht op de omringende gevel of voer een referentiemaat in."),
    "PLANE_NOISY": (BLOCKING, "Het gevelvlak is te onrustig voor een betrouwbare vlakfit. Herhaal vanaf een ander standpunt."),
    "OBLIQUE_ANGLE": (BLOCKING, "Te schuine kijkhoek op het kozijn. Sta meer recht voor het kozijn."),
    "CORNERS_NOT_ON_PLANE": (BLOCKING, "Een hoekstraal raakt het gevelvlak niet. Controleer de hoekselectie."),
    "WRONG_CORNER_SELECTION": (BLOCKING, "De gekozen hoeken vormen geen rechthoek op het gevelvlak. Corrigeer de hoeken (buitenhoeken van het kozijn)."),
    "DIMENSION_OUT_OF_RANGE": (BLOCKING, "Berekende maat valt buiten 0,10-10 m; controleer hoeken en schaal."),
    "LOW_PARALLAX": (BLOCKING, "Te weinig standpuntverschil voor triangulatie. Loop 1-2 m zijwaarts en maak een tweede opname van hetzelfde kozijn."),
    "INCONSISTENT_VIEWS": (BLOCKING, "De standpunten leveren geen consistente hoekposities (hoge herprojectiefout). Controleer de hoekselectie in beide beelden."),
    "CORNERS_NOT_COPLANAR": (BLOCKING, "De getrianguleerde hoeken liggen niet in een vlak. Controleer de hoekselectie."),
    "BEHIND_CAMERA": (BLOCKING, "Getrianguleerd punt ligt achter de camera; controleer de camerapose en hoekselectie."),
    "NO_METRIC_SCALE": (BLOCKING, "Geen betrouwbare metrische schaal. Voer een referentieafstand in tussen twee punten op het kozijnvlak."),
    "REFERENCE_PLANE_MISMATCH": (BLOCKING, "De referentie ligt niet op hetzelfde vlak als het kozijn. Geef een nieuwe referentie op het gevelvlak van dit kozijn."),
    "REFERENCE_INVALID": (BLOCKING, "De referentie is ongeldig (afstand <= 0 of punten vallen samen)."),
    "RECT_ASSUMPTION_VIOLATED": (BLOCKING, "De hoeken zijn niet consistent met een rechthoek en de cameralenzen. Corrigeer de hoeken."),
    "VIEWS_INCONSISTENT": (BLOCKING, "Metingen vanuit verschillende standpunten komen niet overeen. Herhaal de opname; alle waarnemingen zijn bewaard."),
    "NO_FACADE_PLANE": (BLOCKING, "Rond het kozijn is geen bruikbaar plat wandvlak gevonden. Zorg dat een stuk effen muur naast, boven en onder het kozijn in beeld is en sta recht op de gevel."),
    "FACADE_NOT_PLANAR": (BLOCKING, "Het oppervlak rond het kozijn is te ruw of onregelmatig (reliëf, begroeiing, rommel) voor een betrouwbare vlakfit. Kies een standpunt met meer vlakke muur in beeld."),
    "AMBIGUOUS_FACADE_PLANES": (BLOCKING, "Rond het kozijn liggen meerdere even grote vlakken op verschillende diepte (verspringende gevel). Fotografeer vanaf een standpunt waar één wandvlak duidelijk om het kozijn zit, of gebruik een referentiemaat."),
    "FACADE_NOT_REPRESENTATIVE": (BLOCKING, "Het gekozen vlak is te smal of te klein om de gevel te vertegenwoordigen (bijv. alleen een profiel, dagkant of vensterbank). Houd meer effen muur rondom het kozijn in beeld."),
    "FACADE_ONE_SIDED": (BLOCKING, "Het wandvlak is maar aan één of twee kanten van het kozijn gezien. Houd het kozijn met wand aan alle kanten in beeld."),
    "FRAME_PLANE_UNDETERMINED": (BLOCKING, "De terugligging van het kozijn t.o.v. de wand is niet betrouwbaar te bepalen (te weinig diepte op de kozijnrand). Beweeg langzaam iets naar links en rechts en maak de foto opnieuw, of voer een gemeten referentiemaat in."),
    "FRAME_PLANE_INCONSISTENT": (BLOCKING, "De kozijnrand ligt links/rechts/boven op verschillende diepte. Controleer of het kader precies om de buitenrand van het kozijn ligt."),
    "CORNERS_OFF_PLANE": (BLOCKING, "Drie of vier hoeken liggen niet op het gekozen vlak (de gemeten diepte wijkt af). Controleer of het kader om de buitenrand van het kozijn ligt."),
    "FRAMES_INCONSISTENT": (BLOCKING, "De dieptemetingen uit de korte beweging komen niet overeen (tracking-drift of bewegend object). Houd de telefoon rustig en herhaal de opname."),
    "FRAME_OFFSET_FROM_CORNER_DEPTH": (ADVISORY, "De terugligging van het kozijn is afgeleid uit de diepte op de hoeken; dat is minder betrouwbaar. Beweeg iets zijwaarts voor een betere meting."),
    "LIMITED_SIDE_COVERAGE": (ADVISORY, "Het wandvlak is maar aan twee kanten van het kozijn gezien. Houd wand aan alle vier de kanten in beeld voor een betere meting."),
    "DEPTH_MISALIGNMENT_SUSPECTED": (ADVISORY, "De dieptekaart lijkt verschoven t.o.v. het beeld (randen vallen niet samen). Herhaal de opname; houd de telefoon stil tijdens het richten."),
    "QUAD_LARGER_THAN_OPENING": (ADVISORY, "Het kader lijkt groter dan het kozijn (de gemeten dieptesprong ligt ver binnen het kader). Trek de hoeken naar de buitenrand van het kozijn."),
    "QUAD_INSIDE_OPENING": (ADVISORY, "Het kader lijkt binnen het kozijn te liggen (buiten het kader ligt nog dieper glas of een dieptesprong naar het profiel). Trek de hoeken naar de buitenrand van het kozijn."),
    "REFERENCE_USER_ESTIMATE": (ADVISORY, "De referentiemaat is door jou geschat, niet gemeten. De maat is daarom een schatting zonder metrische bevestiging; meet de referentie met duimstok of laser."),
    "GLASS_DEPTH_UNRELIABLE": (ADVISORY, "Diepte in het glas is onbetrouwbaar (reflectie of ontbrekende data); alleen de omringende gevel is gebruikt. Controleer de hoeken visueel."),
    "CORNER_DEPTH_MISMATCH": (ADVISORY, "Diepte op een hoek wijkt af van het gevelvlak (verdiept kozijn of verkeerd gekozen hoek). Controleer de hoeken."),
    "FACADE_NOT_VERTICAL": (ADVISORY, "Het vlak is niet verticaal; controleer of het een gevel is."),
    "SINGLE_VIEWPOINT": (ADVISORY, "Slechts een standpunt; maak een tweede opname vanaf een ander standpunt voor een consistentiecontrole."),
    "METRIC_SCALE_UNVERIFIED": (ADVISORY, "De metrische schaal komt uit AR-tracking en is niet geverifieerd. Voer een referentiemaat in om de schaal te controleren."),
    "VIO_SCALE_MISMATCH": (ADVISORY, "De AR-schaal wijkt af van de ingevoerde referentie; de referentie is leidend gebruikt."),
    "COPLANARITY_ASSUMED": (ADVISORY, "Het kozijn is op de referentieschaal gezet onder de aanname dat het in hetzelfde vlak ligt. Controleer dit."),
    "REFERENCE_UNCERTAINTY_NOT_PROVIDED": (ADVISORY, "Bij de referentie is geen eigen onzekerheid opgegeven; die is niet in de onzekerheid meegenomen."),
    "AUTO_DETECTED_UNCONFIRMED": (ADVISORY, "Hoeken komen van een automatische kandidaatdetector en zijn niet bevestigd; controleer ze (zoom in) of corrigeer ze."),
    "MANUAL_CORNERS": (ADVISORY, "Hoeken zijn handmatig geselecteerd (semi-automatisch)."),
    "HUMAN_CORRECTED_CORNERS": (ADVISORY, "Hoeken zijn door een mens gecorrigeerd; herberekend zonder brondata te overschrijven."),
    "ASSOCIATION_UNVERIFIED": (ADVISORY, "Niet vastgesteld of dit kozijn ook op andere foto's staat; dubbeltelling is niet uitgesloten."),
    "AMBIGUOUS_ASSOCIATION": (ADVISORY, "Waarneming past bij meerdere kozijnen; handmatig koppelen."),
    "OBSTRUCTION_REPORTED": (ADVISORY, "Gebruiker meldt begroeiing of obstakel voor het kozijn; hoeken kunnen onjuist zijn."),
}


def flag(code, detail=None):
    sev, instr = FLAGS[code]
    return {"code": code, "severity": sev, "detail": detail, "instruction_nl": instr}


def blocking(flags):
    return [f for f in flags if f["severity"] == BLOCKING]


def advisory(flags):
    return [f for f in flags if f["severity"] == ADVISORY]


def dedupe_flags(flags):
    seen, out = set(), []
    for f in flags:
        k = (f["code"], f.get("detail"))
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out
