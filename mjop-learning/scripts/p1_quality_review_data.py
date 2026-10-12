"""Gegevens voor de P1 Visual Review - Quality Corrections v1 (alleen rapportage/review; geen instances, pandkoppelingen, totalen of kosten).

Alle beoordelingen hieronder zijn onafhankelijk opnieuw gedaan op de geverifieerde originele pixels (SHA256 uit het foto-archief-register) en
zijn bewijsbeoordelingen, geen SAME-besluiten en geen menselijke goedkeuring. De bestaande 50 observaties en 43 relaties staan ongewijzigd in
visual_review_map003_map004_data.py; een gecorrigeerd Claude-voorstel staat uitsluitend in PROPOSAL_CORRECTIONS (apart, voor review).
"""

QUALITY_STATUSES = ("TECHNICALLY_VALIDATED", "VISUALLY_SUPPORTED", "NEEDS_MANUAL_REVIEW", "NEEDS_BETTER_PHOTO")
EVIDENCE_CLASSES = ("STRONG_VISUAL_SUPPORT", "MODERATE_VISUAL_SUPPORT", "INSUFFICIENT_EVIDENCE")
STATUS_NL = {
    "TECHNICALLY_VALIDATED": "technisch gecontroleerd (nog geen onafhankelijk visueel bewijs; regel-, lees- of procesvraag)",
    "VISUALLY_SUPPORTED": "visueel ondersteund (opnieuw met de originele pixels gecontroleerd)",
    "NEEDS_MANUAL_REVIEW": "menselijke beoordeling nodig (bewijs is dubbelzinnig of tegenstrijdig)",
    "NEEDS_BETTER_PHOTO": "betere foto nodig",
}
CLASS_NL = {
    "STRONG_VISUAL_SUPPORT": "sterke visuele ondersteuning",
    "MODERATE_VISUAL_SUPPORT": "matige visuele ondersteuning",
    "INSUFFICIENT_EVIDENCE": "onvoldoende bewijs",
}
CLASS_RULE = (
    "STRONG: in beide beelden is een onderscheidende combinatie van kenmerken zichtbaar (open vleugels, gordijn/folie, voorwerpen op de dorpel, leesbaar plaatnummer "
    "naast het raam) die buurramen niet delen. MODERATE: dezelfde indeling en positie, maar zonder uniek onderscheidend kenmerk in beide beelden, of het beeld is "
    "deels bedekt/schuin; steunt mede op de volgorde in de rij. INSUFFICIENT: te weinig zichtbaar of te donker; alleen positie/volgorde. De kenmerkmatch (SIFT) is "
    "slechts ondersteunend: niet-partners halen tot 24 inliers (meestal 8-17), dus een aantal inliers alleen beslist nooit."
)

# --- A. scheidingen (RV-SEP-001..006) ---------------------------------------------------------------------------------------------------
# (penant zichtbaar, afzonderlijke openingen, bbox correct, bewijs voldoende, opmerking)
SEP_RESULTS = {
    "RV-SEP-001": (True, True, True, True, "Doorlopend metselwerk (steenverband) tussen kozijn 007 en raam 008; beide kaders sluiten op de kozijnbuitenkant."),
    "RV-SEP-002": (True, True, True, True, "Metselwerk tussen 011 en 012 volledig zichtbaar; folie op de ruit van 012."),
    "RV-SEP-003": (True, True, True, True, "Penant tussen 013 (open vleugel links) en 014; het linkerkader van 013 raakt de buitenrand van de open vleugel (<=5 px)."),
    "RV-SEP-004": (True, True, True, True, "Zelfde indeling als MAP-003 007|008, ander standpunt; penant volledig zichtbaar."),
    "RV-SEP-005": (True, True, True, True, "Metselwerk tussen 008 en 009; de linkervleugel van 008 staat iets open maar het kader sluit aan."),
    "RV-SEP-006": (True, True, True, True, "Metselwerk tussen 010 (open vleugel links) en 011 in het rechterpand; kader 010 omvat de open vleugel."),
}
SEP_NOTE = ("Opvallend in alle zes: boven de penant loopt een dunne lichte doorlopende strip (waarschijnlijk afdekprofiel/latei) die de twee kozijnen visueel verbindt. "
            "Onder die strip is het metselwerk ononderbroken. Dit is dezelfde configuratie als bij foto 2 (PCD-00004, zichtbaar metselwerk tussen kozijnen scheidt); de "
            "telregel wordt niet gewijzigd. De strip is een aandachtspunt voor de menselijke beoordelaar, geen reden om de scheiding te verwerpen.")

# --- B. OBS-MAP003-009 versus 010 --------------------------------------------------------------------------------------------------------
B009_010 = [
    "MAP-002 (FC-M2-006-A en -BC, bestaand besluit PCD): smal linker element met open vleugel, daarnaast zichtbaar metselwerk, dan het hoofdkozijn met een blauw-omrande open vleugel, gordijn en rechter open vleugel.",
    "MAP-003 (OBS-009 en -010): zelfde combinatie; de blauw-omrande open vleugel van 010 overlapt de rechterrand van het smalle element, waardoor het metselwerk daartussen verborgen is.",
    "MAP-004 (OBS-005): zelfde combinatie; het smalle element is grotendeels achter de blauw-omrande vleugel verborgen (alleen onderrand en linkerzijde zichtbaar).",
    "MAP-013 (REF-004, schuin): het metselwerk tussen het smalle linker element en het hoofdkozijn is zichtbaar; dat is onafhankelijk bewijs dat het smalle element een afzonderlijk kozijn is (zelfde conclusie als het bestaande foto-2-besluit).",
]
B009_CONCLUSION = (
    "De configuratie 009+010 is in vier foto's herkenbaar (STRONG voor het hoofdkozijn 010). Het bestaande foto-2-besluit (smal linker element = apart kozijn FC-M2-006-A) wordt door "
    "MAP-013 onafhankelijk ondersteund; MAP-003 en MAP-004 kunnen dit zelf niet beslissen omdat een open vleugel het metselwerk bedekt. Er ontstaat geen nieuwe unieke instance en "
    "009+010 worden niet automatisch dubbel geteld; een telverschil tussen MAP-003 (2 observaties) en MAP-004 (1 observatie) is een leesverschil. HQ-VR-001 blijft een menselijk besluit."
)

# --- C. overlap-bewijs per relatie ----------------------------------------------------------------------------------------------------
# rel -> (klasse, bewijsgrondslag[], toelichting)
REL_ASSESSMENT = {
    "VR-001": ("STRONG_VISUAL_SUPPORT", ["PLATE_ANCHOR", "FACADE_CONTEXT"], "Plaat 288, muurverband, kap/dakraam en het raam rechts van de plaat staan in dezelfde onderlinge ligging op MAP-002 en MAP-003. Dit bewijst alleen dezelfde gevelsectie."),
    "VR-002": ("STRONG_VISUAL_SUPPORT", ["PLATE_ANCHOR", "UNIQUE_CONFIGURATION"], "Raam met gordijn tussen plaat 288 en plaat 286 onder dezelfde donkere latei; zelfde kozijnvorm met brede onderdorpel. Kenmerkmatch zwak door kijkhoek (6 inliers), visueel eenduidig."),
    "VR-050": ("MODERATE_VISUAL_SUPPORT", ["PLATE_ANCHOR", "OBLIQUE_VIEW"], "MAP-013 is schuin; raam naast een gedeeltelijk zichtbare plaat met kantgordijn. Zelfde positie, maar de schuine opname laat geen unieke details vergelijken."),
    "VR-004": ("MODERATE_VISUAL_SUPPORT", ["SAME_LAYOUT", "SEQUENCE_ORDER", "PARTIAL_OVERLAP"], "Raam met onderpaneel naast de kap; in MAP-003 deels door het dakschild bedekt. Indeling gelijk, geen uniek kenmerk in beide beelden."),
    "VR-005": ("INSUFFICIENT_EVIDENCE", ["SEQUENCE_ORDER", "REPETITION_RISK", "PARTIAL_OVERLAP"], "In MAP-003 is slechts de rechtervleugel aan de beeldrand zichtbaar; de woningen zijn identiek, dus herkenning berust alleen op de volgorde."),
    "VR-006": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "FEATURE_MATCH"], "Tweedelig kozijn (smalle linkervleugel, groot rechterdeel met rolkast) met identieke merktekens op de stijl; 22 kenmerkmatches (inliers)."),
    "VR-007": ("MODERATE_VISUAL_SUPPORT", ["SAME_LAYOUT", "SEQUENCE_ORDER"], "Smal raam met rolkast direct rechts van de penant; vorm gelijk, kleine details zijn door resolutie niet te vergelijken."),
    "VR-054": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "OBLIQUE_VIEW"], "Tweedelig kozijn + penant + smal los kozijn in dezelfde volgorde op MAP-003 en MAP-013 (schuin); penant in beide zichtbaar."),
    "VR-008": ("MODERATE_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "PARTIAL_OVERLAP"], "Het smalle linker element staat in alle foto's links van het unieke hoofdkozijn 010; in MAP-003 deels door de open vleugel van 010 bedekt. Dat het een afzonderlijk kozijn is, volgt uit MAP-002/MAP-013, niet uit MAP-003."),
    "VR-009": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION"], "Gordijn, blauw-omrande open vleugel links en open vleugel rechts: onderscheidende combinatie, identiek op MAP-002 en MAP-003."),
    "VR-031": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "FEATURE_MATCH"], "Zelfde combinatie op MAP-003 en MAP-004 (24 inliers). Het telverschil 2 observaties versus 1 is een leesverschil: het smalle element is op MAP-004 grotendeels bedekt."),
    "VR-053": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "OBLIQUE_VIEW"], "MAP-013 (schuin) toont dezelfde combinatie: smal element, metselwerk, hoofdkozijn met blauw-omrande open vleugel, rechter open vleugel."),
    "VR-010": ("INSUFFICIENT_EVIDENCE", ["SAME_LAYOUT", "REPETITION_RISK", "PARTIAL_OVERLAP"], "Raam aan de beeldrand van MAP-003; vergelijkbare open vleugel en rolkast, maar afgesneden en identiek aan buurramen: kan een buurraam zijn."),
    "VR-027": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "FEATURE_MATCH"], "Tweedelig kozijn met identieke merktekens, stickers en gordijn; 39 inliers, mutueel beste partner (volgende 24)."),
    "VR-028": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "FEATURE_MATCH"], "Smal raam met afgeplakte/foliebedekte ruit, identiek patroon; 20 inliers, mutueel beste partner (volgende 8)."),
    "VR-029": ("MODERATE_VISUAL_SUPPORT", ["SEQUENCE_ORDER", "SAME_LAYOUT"], "Smal raam met rolkast tussen twee sterk gematchte buren (012 en 014); in beide beelden iets openstaande vleugel, maar de ruitinhoud verschilt door de kijkhoek. Weinig kenmerken (5 inliers); koppeling steunt op de volgorde."),
    "VR-030": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION", "FEATURE_MATCH"], "Kozijn met rolkast en donkere open vleugel rechts; 28 inliers, mutueel beste partner (volgende 15)."),
    "VR-045": ("INSUFFICIENT_EVIDENCE", ["OBLIQUE_VIEW", "PARTIAL_OVERLAP"], "MAP-009 is sterk verkort: alleen het tweedelige kozijn is herkenbaar, het smalle raam ontbreekt; geen uniek kenmerk."),
    "VR-024": ("MODERATE_VISUAL_SUPPORT", ["SAME_LAYOUT", "FEATURE_MATCH", "REPETITION_RISK"], "Open vleugel rechts, onderpaneel en tak-spiegeling gelijk (28 inliers, mutueel beste). De gordijnen lijken op MAP-003 en MAP-004 verschillend (kijkhoek/glans): geen uniek kenmerk, dus MODERATE."),
    "VR-025": ("MODERATE_VISUAL_SUPPORT", ["SAME_LAYOUT", "PARTIAL_OVERLAP"], "Linkervleugel met spiegeling en onderpaneel gelijk; de flessen op de dorpel (uniek kenmerk) zijn in MAP-004 door de kap bedekt. Inliers 20 tegen 19 voor de beste andere partner: geen marge."),
    "VR-043": ("STRONG_VISUAL_SUPPORT", ["UNIQUE_CONFIGURATION"], "Flessen op de dorpel, tak voor het onderpaneel en dezelfde raamverdeling op MAP-003 en MAP-009."),
    "VR-026": ("INSUFFICIENT_EVIDENCE", ["HIDDEN", "REPETITION_RISK"], "In MAP-003 is slechts een smalle strook achter lantaarnpaal en kap zichtbaar; het raam rechts van de kap lijkt op het raam links van de kap (identieke woningen). Geen vergelijkbaar kenmerk zichtbaar."),
    "VR-044": ("INSUFFICIENT_EVIDENCE", ["OBLIQUE_VIEW", "HIDDEN", "REPETITION_RISK"], "MAP-009 toont het raam vanaf de andere kant met de vleugel op een andere plaats; combinatie met een verborgen strook in MAP-003 levert geen controleerbaar kenmerk."),
    "VR-020": ("STRONG_VISUAL_SUPPORT", ["PLATE_ANCHOR", "FACADE_CONTEXT"], "De drie platen 280/278/276 zijn in beide foto's leesbaar en staan in dezelfde volgorde met de bijbehorende entreemuren. Dit bewijst alleen dezelfde gevelsectie."),
    "VR-021": ("STRONG_VISUAL_SUPPORT", ["PLATE_ANCHOR", "UNIQUE_CONFIGURATION"], "Raam direct links van het leesbare plaatnummer 278 met dezelfde latei en dorpel. Kenmerkmatch zwak (10 inliers, rang 2) door identieke buurramen en spiegelingen: de plaat is hier het anker, niet het raamdetail."),
    "VR-022": ("INSUFFICIENT_EVIDENCE", ["TOO_DARK", "REPETITION_RISK"], "OBS-MAP003-027 is te donker (0 bruikbare kenmerken). De entreenis met regenpijp, trap en deur is bij elke woning identiek: OBS-MAP003-026 lijkt in uitzicht sterker op MAP004-020 dan 027, maar die ligt bij plaat 286. Alleen de plaatpositie (278) en de verschuiving passen bij 027."),
    "VR-041": ("STRONG_VISUAL_SUPPORT", ["PLATE_ANCHOR", "UNIQUE_CONFIGURATION"], "Raam links van plaat 278 op MAP-003, MAP-004 en (schuin) MAP-009; zelfde latei en spiegeling van de boom."),
}
# volgorde voor het rapport en de HTML
P1_REL_ORDER = ["VR-001", "VR-002", "VR-050", "VR-004", "VR-005", "VR-006", "VR-007", "VR-054", "VR-008", "VR-009", "VR-031", "VR-053", "VR-010",
                "VR-027", "VR-028", "VR-029", "VR-030", "VR-045", "VR-024", "VR-025", "VR-043", "VR-026", "VR-044", "VR-020", "VR-021", "VR-022", "VR-041"]

# --- D. objecten met een bijzonder punt: zes afzonderlijke vragen ------------------------------------------------------------------------------
# obs -> dict(vraag -> (antwoord, toelichting))   antwoorden: YES / NO / UNCERTAIN / PLAUSIBLE / PARTIAL / NOT_PROVEN
Q6 = ("exists_visibly", "object_type", "full_or_partial", "separately_identifiable", "measurable", "pand_link_proven")
Q6_NL = {"exists_visibly": "Bestaat visueel?", "object_type": "Objecttype", "full_or_partial": "Volledig of deels zichtbaar", "separately_identifiable": "Afzonderlijk te onderscheiden?",
         "measurable": "Meetbaar?", "pand_link_proven": "Pandkoppeling bewezen?"}
OBJ_MATRIX = {
    "OBS-MAP003-020": {
        "exists_visibly": ("YES", "Kozijnhoek en ruit zichtbaar tussen dakschild en lantaarnpaal."),
        "object_type": ("WINDOW", "Raam met wit kozijn en ruit; geen deur of dakraam."),
        "full_or_partial": ("PARTIAL", "Alleen de linkerbovenhoek en een deel van de ruit; rest achter dak en paal."),
        "separately_identifiable": ("UNCERTAIN", "Als zichtbaar raamdeel wel; de koppeling met OBS-MAP004-016 is onvoldoende onderbouwd (VR-026)."),
        "measurable": ("NO", "Deels bedekt, geen schaal."),
        "pand_link_proven": ("NOT_PROVEN", "Geen leesbare plaat bij dit raam."),
    },
    "OBS-MAP003-026": {
        "exists_visibly": ("YES", "Donker paneel in de entreenis met wit kozijnprofiel rechts."),
        "object_type": ("PLAUSIBLE_DOOR", "Deurvorm in de entreenis; de kleur 'rood' in de observatienotitie is op deze belichting niet te verifieren (donkerblauw/zwart)."),
        "full_or_partial": ("PARTIAL", "Onderkant door begroeiing bedekt; schaduw."),
        "separately_identifiable": ("YES", "Binnen de entreenis, naast regenpijp en trap. Let op: alle entreeen zijn identiek (herhalingsrisico)."),
        "measurable": ("NO", "Deels bedekt, geen schaalreferentie."),
        "pand_link_proven": ("NOT_PROVEN", "Plaat 286 hangt ernaast; die bewijst alleen de plaatmuur."),
    },
    "OBS-MAP003-027": {
        "exists_visibly": ("UNCERTAIN", "Zeer donker rechthoekig vlak rechts van plaat 278; twee donkere vlakken naast elkaar."),
        "object_type": ("UNDETERMINED", "Deur of donkere doorgang niet te onderscheiden."),
        "full_or_partial": ("UNDETERMINED", "Niet te bepalen door ontbrekend contrast."),
        "separately_identifiable": ("NO", "Vloeit samen met het tweede donkere vlak."),
        "measurable": ("NO", "Geen bruikbare randen."),
        "pand_link_proven": ("NOT_PROVEN", "Plaat 278 bewijst alleen de plaatmuur."),
    },
    "OBS-MAP003-028": {
        "exists_visibly": ("UNCERTAIN", "Wit verticaal kozijnprofiel met donkere ruit achter hortensia's; kan een raam zijn."),
        "object_type": ("UNKNOWN", "Raam plausibel, niet vast te stellen; blijft UNKNOWN_OPENING."),
        "full_or_partial": ("PARTIAL", "Grotendeels door begroeiing bedekt."),
        "separately_identifiable": ("NO", "Alleen een kozijnstijl te zien."),
        "measurable": ("NO", "Niet meetbaar."),
        "pand_link_proven": ("NOT_PROVEN", "Geen plaat in de buurt."),
    },
    "OBS-MAP004-012": {
        "exists_visibly": ("YES", "Wit kozijn met ruit en rolkast aan de beeldrand."),
        "object_type": ("WINDOW", "Raam."),
        "full_or_partial": ("PARTIAL", "Door de beeldrand afgesneden; ongeveer de linkerhelft van een raam."),
        "separately_identifiable": ("NO", "Niet te koppelen aan het rechterpand op MAP-003 (VR-035 UNDETERMINABLE)."),
        "measurable": ("NO", "Afgesneden."),
        "pand_link_proven": ("NOT_PROVEN", "Geen plaat zichtbaar."),
    },
    "OBS-MAP004-020": {
        "exists_visibly": ("YES", "Donkerrode deur met wit kozijnprofiel rechts, regenpijp links, trap erachter."),
        "object_type": ("PLAUSIBLE_DOOR", "Deurblad met kozijn in de entreenis (nog geen besluit of deuren meetellen: HQ-VR-003)."),
        "full_or_partial": ("PARTIAL", "Regenpijp links en de onderkant deels bedekt; PARTIAL blijft."),
        "separately_identifiable": ("YES", "Binnen de entreenis rechts van plaat 278."),
        "measurable": ("NO", "Deels bedekt; geen schaalreferentie."),
        "pand_link_proven": ("NOT_PROVEN", "Plaat 278 bewijst alleen de plaatmuur."),
    },
    "OBS-MAP004-022": {
        "exists_visibly": ("YES", "Klein deurblad met wit kozijn achter hortensia's."),
        "object_type": ("PLAUSIBLE_DOOR", "Deurvorm; te klein voor zekerheid."),
        "full_or_partial": ("PARTIAL", "Grotendeels door begroeiing en de beeldrand bedekt."),
        "separately_identifiable": ("UNCERTAIN", "Hoort bij het buurpand links; niets te koppelen."),
        "measurable": ("NO", "Niet meetbaar."),
        "pand_link_proven": ("NOT_PROVEN", "Geen leesbare plaat."),
    },
}

# --- Proposal-correcties (voorstellen van Claude, niet-bindend; apart vastgelegd voor review) -----------------------------------------------------
# review_id -> (van, naar, reden)
PROPOSAL_CORRECTIONS = {
    "RV-OBS-MAP003-027": ("UNDECIDABLE", "NEEDS_BETTER_PHOTO", "Te donker: zonder betere belichting of een nieuwe foto is geen enkele uitspraak mogelijk."),
    "RV-OBS-MAP004-022": ("UNDECIDABLE", "NEEDS_BETTER_PHOTO", "Klein, bedekt door begroeiing en de beeldrand: een nieuwe foto lost dit op, extra onderzoek op deze foto niet."),
    "RV-REL-VR-008": ("UNDECIDABLE", "SAME", "Het smalle element staat in alle vier de foto's links van het unieke hoofdkozijn (MODERATE); of het een apart kozijn is, blijft een apart besluit (HQ-VR-001)."),
    "RV-REL-VR-026": ("SAME", "UNDECIDABLE", "Onvoldoende bewijs: in MAP-003 slechts een strook; identieke buurramen."),
    "RV-REL-VR-044": ("SAME", "UNDECIDABLE", "Onvoldoende bewijs: schuine opname met afwijkende vleugelpositie en verborgen strook in MAP-003."),
}

# --- Kwaliteitsregels per P1-reviewpunt ----------------------------------------------------------------------------------------------------------
# id -> (bevinding, bewijsverwijzing, volgende stap, status, extra bewijs nodig)
# Bewijsverwijzingen verwijzen naar bestanden in reports/frames/photo_review_map003_map004_v1/p1_quality_review/
OBS_FINDINGS = {
    "RV-OBS-MAP003-009": ("Zichtbaar raamelement links van 010; de rechterrand wordt door de open vleugel van 010 overlapt (zichtbaarheid is dus niet echt FULL). Apart kozijn volgens MAP-002 en MAP-013 (metselwerk ertussen), niet zelfstandig af te leiden uit MAP-003.",
                          "Q009_010_four_photos.jpg", "Mens beslist HQ-VR-001 (apart kozijn of vleugel); geen extra telling.", "NEEDS_MANUAL_REVIEW", "Nee: MAP-013 levert het bewijs, een frontale foto bevestigt het."),
    "RV-OBS-MAP003-010": ("Hoofdkozijn met gordijn en twee open vleugels, eenduidig herkenbaar in vier foto's; kader klopt.",
                          "Q009_010_four_photos.jpg", "Beoordelen als voorlopige zichtbare opening (geen instance).", "VISUALLY_SUPPORTED", "Nee"),
    "RV-OBS-MAP003-020": ("Zichtbaar raamdeel (hoek en ruit) achter lantaarnpaal en kap; partieel, niet meetbaar; identiteit met MAP004-016 niet onderbouwd.",
                          "QD-MAP003-020.jpg", "Menselijk bevestigen dat alleen de zichtbare opening telt; geen koppeling.", "NEEDS_MANUAL_REVIEW", "Ja: een foto van rechts of dichterbij"),
    "RV-OBS-MAP003-026": ("Deurvorm in entreenis met kozijnprofiel; de kleur 'rood' is op deze belichting niet te verifieren; onderkant bedekt. Alle entreeen zijn identiek (herhalingsrisico).",
                          "QD-MAP003-026.jpg", "HQ-VR-003 (tellen deuren mee?) beslissen; kleur niet gebruiken.", "NEEDS_MANUAL_REVIEW", "Ja: betere belichting (flits/avond is niet nodig; schaduwloze opname)"),
    "RV-OBS-MAP003-027": ("Zeer donker: een rechthoekig vlak naast het plaatje 278, geen contrast, twee donkere vlakken. Geen enkele uitspraak over type of zichtbaarheid mogelijk.",
                          "QD-MAP003-027.jpg", "Betere foto nodig; geen koppeling met MAP004-020 afdwingen.", "NEEDS_BETTER_PHOTO", "Ja: opname met voldoende licht of nabij"),
    "RV-OBS-MAP003-028": ("Wit kozijnprofiel met donkere ruit achter hortensia's; kan een raam zijn, kan ook een muurband zijn. Blijft UNKNOWN_OPENING.",
                          "QD-MAP003-028.jpg", "Mens kan REJECT (geen opening) of UNDECIDABLE kiezen; geen type toekennen.", "NEEDS_MANUAL_REVIEW", "Ja: foto zonder begroeiing"),
    "RV-OBS-MAP004-012": ("Raamstrook aan de beeldrand; bestaat zichtbaar (kozijn, ruit, rolkast) maar is afgesneden en niet te koppelen.",
                          "QD-MAP004-012.jpg", "UNDECIDABLE laten; geen koppeling met MAP-003.", "NEEDS_MANUAL_REVIEW", "Ja: bredere opname van het rechterpand"),
    "RV-OBS-MAP004-020": ("Deurblad met wit kozijn in de entreenis, regenpijp links en trap erachter; kleur donkerrood (op MAP-004 wel te zien); PARTIAL blijft juist.",
                          "QD-MAP004-020.jpg", "HQ-VR-003 beslissen (deuren tellen mee of context).", "VISUALLY_SUPPORTED", "Nee"),
    "RV-OBS-MAP004-022": ("Klein deurblad met kozijn achter hortensia's aan de beeldrand; grotendeels bedekt; hoort bij het buurpand.",
                          "QD-MAP004-022.jpg", "Betere foto nodig.", "NEEDS_BETTER_PHOTO", "Ja: opname van het buurpand links"),
}
SEP_FINDING = "Penant (doorlopend metselwerk) zichtbaar, afzonderlijke openingen, kaders correct (zie QSEP-figuur)."
HQ_FINDINGS = {
    "HQ-VR-001": ("Extra bewijs: MAP-013 toont metselwerk tussen het smalle element en het hoofdkozijn; ondersteunt 'apart kozijn' maar kan de keuze niet vervangen.",
                  "Q009_010_four_photos.jpg", "Mens beslist.", "NEEDS_MANUAL_REVIEW", "Nee"),
    "HQ-VR-002": ("Alle zes de penanten zijn volledig zichtbaar (metselwerk scheidt); telregel en bestaand foto-2-besluit ongewijzigd.",
                  "QSEP-001.jpg .. QSEP-006.jpg", "Mens bevestigt.", "VISUALLY_SUPPORTED", "Nee"),
    "HQ-VR-003": ("Vier deurobservaties met verschillende kwaliteit: MAP004-020 goed, MAP003-026 matig, MAP003-027 en MAP004-022 onbruikbaar.",
                  "QD-MAP004-020.jpg e.a.", "Mens beslist of deuren meetellen.", "NEEDS_MANUAL_REVIEW", "Ja voor 027 en 022"),
    "HQ-APP-001": ("Regelvraag: een plaat bewijst alleen de plaatmuur. Beide plaatrelaties (VR-001/VR-020) bewijzen alleen gevelsecties.",
                   "-", "Mens bevestigt de regel.", "TECHNICALLY_VALIDATED", "Nee"),
    "HQ-APP-002": ("Alle zeven platen MAP-003 (288..276) opnieuw gelezen op afbeelding E: leesbaar en correct.",
                   "E_plates_MAP-003_MAP-004.jpg", "Mens bevestigt de lezing.", "VISUALLY_SUPPORTED", "Nee"),
    "HQ-APP-003": ("Alle vier platen MAP-004 (280..274) opnieuw gelezen: leesbaar en correct.",
                   "E_plates_MAP-003_MAP-004.jpg", "Mens bevestigt de lezing.", "VISUALLY_SUPPORTED", "Nee"),
    "HQ-APP-011": ("Mengbeeld: VR-002/006/009 sterk, VR-004/007/008 matig, VR-005/010 onvoldoende (zie relatietabel).",
                   "QREL-sheet-1.jpg, QREL-sheet-5.jpg", "Mens beslist per paar.", "NEEDS_MANUAL_REVIEW", "Ja voor VR-005 en VR-010"),
    "HQ-APP-012": ("Mengbeeld: VR-021/027/028/030/031 sterk, VR-024/025/029 matig, VR-022/026/044/045 onvoldoende.",
                   "QREL-sheet-2.jpg, QREL-sheet-3.jpg, QREL-sheet-4.jpg", "Mens beslist per paar.", "NEEDS_MANUAL_REVIEW", "Ja voor VR-022, VR-026, VR-044, VR-045"),
    "HQ-APP-013": ("VR-050 matig (schuine opname); VR-051 is P2 en hier niet opnieuw beoordeeld.",
                   "QREL-sheet-4.jpg", "Mens beslist.", "TECHNICALLY_VALIDATED", "Nee"),
    "HQ-APP-031": ("Procesvraag (overlapmarkering zonder optelling). Geen visuele claim; de relaties met foto 2 zijn technisch consistent.",
                   "-", "Mens beslist.", "TECHNICALLY_VALIDATED", "Nee"),
    "HQ-APP-034": ("Geschiktheidsvraag: de lijst open punten (009/-020/-027/-028) mist MAP003-026 (kleurclaim niet te verifieren).",
                   "QD-MAP003-026.jpg", "Open-puntenlijst aanvullen bij de beslissing.", "TECHNICALLY_VALIDATED", "Nee"),
    "HQ-APP-035": ("Geschiktheidsvraag: de lijst open punten (005/-012/-022) mist MAP004-020 (deur deels bedekt, PARTIAL).",
                   "QD-MAP004-020.jpg", "Open-puntenlijst aanvullen bij de beslissing.", "TECHNICALLY_VALIDATED", "Nee"),
}
REL_NEXT = {
    "STRONG_VISUAL_SUPPORT": "Mens kan SAME overwegen (bewijs ondersteunt de kandidaatrelatie; geen merge).",
    "MODERATE_VISUAL_SUPPORT": "Mens beoordeelt de uitsnedes zelf; SAME alleen met eigen visuele bevestiging.",
    "INSUFFICIENT_EVIDENCE": "UNDECIDABLE of NEEDS_BETTER_PHOTO; geen SAME op deze foto's.",
}
REL_EXTRA = {"STRONG_VISUAL_SUPPORT": "Nee", "MODERATE_VISUAL_SUPPORT": "Nee (optioneel een frontale foto)", "INSUFFICIENT_EVIDENCE": "Ja"}


def relation_status(cls):
    """STRONG -> visueel ondersteund; MODERATE -> mens moet zelf kijken; INSUFFICIENT -> betere foto nodig."""
    return {"STRONG_VISUAL_SUPPORT": "VISUALLY_SUPPORTED", "MODERATE_VISUAL_SUPPORT": "NEEDS_MANUAL_REVIEW", "INSUFFICIENT_EVIDENCE": "NEEDS_BETTER_PHOTO"}[cls]
