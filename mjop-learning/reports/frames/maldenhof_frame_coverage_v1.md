# Maldenhof frame coverage v1

Coverage betekent alleen zichtbaarheid van de gevel op een bevestigde foto, NIET dat het aantal kozijnen compleet is vastgesteld.

Scope: de 15 bevestigde Maldenhof-panden (240-296). Volgorde langs de straat op laagste huisnummer; dit is geen bewijs voor bouwblokgrenzen.

## Coverage per pand

| # | Pand | Adressen | FRONT | REAR | LEFT_SIDE | RIGHT_SIDE | Foto's | Confirmed instances | Pending candidates |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `0363100012137996` | 240 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 2 | `0363100012102659` | 242, 244 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 3 | `0363100012078022` | 246, 248 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 4 | `0363100012140664` | 250, 252 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 5 | `0363100012141419` | 254, 256 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 6 | `0363100012091974` | 258, 260 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 7 | `0363100012070344` | 262, 264 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 8 | `0363100012107492` | 266, 268 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 9 | `0363100012071880` | 270, 272 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 10 | `0363100012144766` | 274, 276 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 11 | `0363100012091756` | 278, 280 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 12 | `0363100012143647` | 282, 284 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |
| 13 | `0363100012121455` | 286, 288 | PARTIAL_COVERAGE | UNKNOWN | UNKNOWN | UNKNOWN | maldenhof_2 | 0 | 0 |
| 14 | `0363100012134188` | 290, 292 | PARTIAL_COVERAGE | UNKNOWN | UNKNOWN | UNKNOWN | maldenhof_2 | 0 | 0 |
| 15 | `0363100012127361` | 294, 296 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | - | 0 | 0 |

Samenvatting (aantal panden per status): FRONT: FULL_COVERAGE 0, PARTIAL_COVERAGE 2, NO_COVERAGE 0, UNKNOWN 13; REAR: FULL_COVERAGE 0, PARTIAL_COVERAGE 0, NO_COVERAGE 0, UNKNOWN 15; LEFT_SIDE: FULL_COVERAGE 0, PARTIAL_COVERAGE 0, NO_COVERAGE 0, UNKNOWN 15; RIGHT_SIDE: FULL_COVERAGE 0, PARTIAL_COVERAGE 0, NO_COVERAGE 0, UNKNOWN 15

Alleen foto 2 dekt (deels) twee panden aan de voorzijde (288 en 290). Voor alle andere gevels bestaat geen aan een pand gekoppelde bevestigde foto.

### Obscured areas, panden 288 en 290 (foto 2)

- Begane grond links (x < 0,35): lantaarnpaal, fiets, boom en struiken verbergen alle gevelopeningen links van het portiek.
- Begane grond midden (x 0,45-0,80): struiken, fietsen en houten bergkasten verbergen het gevelvlak tussen de muren van 290 en 288; mogelijke ramen/deuren (FC-M2-012/013) zijn niet te beoordelen.
- Entree 290: deur en trap liggen in schaduw onder het portiek; alleen een donkere deuropening zichtbaar.
- Entree 288: de entree rechts bij nummer 288 is niet zichtbaar (struiken, muur, buiten beeld rechts).
- Rechterrand: de foto snijdt het gebouw af; de gevel loopt rechts door buiten beeld (naastliggende woningen niet geannoteerd).
- Linkerrand: een naastliggend bouwblok (kozijn en dakraam bij x < 0,05) is niet geannoteerd; waarschijnlijk buiten Maldenhof 240-296.
- Tegenlicht rechtsboven en bij de linker dakraam maakt dakramen minder goed leesbaar.
- De bouwlaag van de bovenste gevelrij is niet vast te stellen met GROUND/FIRST/ROOF/UNKNOWN; die ramen staan op UNKNOWN.
- Achterzijde, dakvlakken achter en zijgevels ontbreken volledig op foto 2 (zie foto 3 voor achterdetail; niet gecombineerd).

## Foto's zonder bewezen pand

| Foto | Zijde | Rol | Pand | Confirmed instances | Pending candidates | Opmerking |
|---|---|---|---|---|---|---|
| maldenhof_2 | FRONT | BEST_FOR_STREET_FACADE | PROVEN_FOR_HOUSE_NUMBERS_ONLY | 12 | 0 | De 12 gewone kozijnen en 1 deur zijn bevestigd, maar niet aan een pand toegewezen (zie photo2_instance_assignment). |
| maldenhof_3 | REAR | REAR_DETAIL | NOT_PROVEN | 0 | 10 | Achterzijde van een onbekend pand binnen Maldenhof; een kopgevel is aan de rechterrand zichtbaar. |
| maldenhof_1 | FRONT_OBLIQUE | CONTEXT_ONLY | NOT_USED | 0 | 0 | Context: zie photo1_context. Niet voor frame instances. |

## Tellingen per foto (niet combineren)

- Foto 2 (voor): PHOTO_VISIBLE_FRAME_COUNT 11, WINDOW 11, EXTERIOR_DOOR 1 (FULL 9, PARTIAL 2).
- Foto 3 (achter): VISIBLE_COUNT_ON_PHOTO_3: FULL windows 1, PARTIAL 1, doors 1, roof windows 4, dormer 1, unknown 2; 0 confirmed.
- BUILDING_TOTAL: niet berekend. 756,80 m2 blijft NOT_COMPARABLE.

## Repeat candidates

MOD-M2-A en MOD-M2-B blijven REPEAT_CANDIDATE (DO_NOT_ACTIVATE_REPEAT_YET).

- RC-M3-001: Beide woningen tonen een terugliggende bouwlaag met balkon onder een lager dakschild; mogelijk een gespiegeld/gelijk achtergeveltype. Zichtbare inhoud verschilt (kozijnindeling) en de linker woning is grotendeels afgedekt.
- RC-M3-002: Verspreide dakramen in het achterdakvlak; patroon niet regelmatig genoeg voor een module.

## MISSING_PHOTOS_NEEDED

**Minimum aantal extra foto's voor directe dekking (zonder repeat-extrapolatie): 12** (5 voorzijde, 5 achterzijde, 2 kopgevel).

Planningsaanname: 3 aaneengesloten panden per frontale foto. Op foto 2 liggen de huisnummerplaten van twee naast elkaar gelegen panden (290 en 288) ca. 27% van de beeldbreedte uit elkaar; er passen dus ca. 3,7 pandbreedtes in beeld; met een pand overlap blijven 3 panden per foto over. Dit is een planning (handmatige lezing), geen meting.

- Alle panden en beide zijden worden direct gefotografeerd; er is geen repeat-extrapolatie toegepast.
- Het aantal kopgevelfoto's is een maximum: ter plaatse bepalen of de uiteinden echt kopgevels zijn.

Alleen na een latere menselijke repeat-bevestiging zou een kleinere representatieve set kunnen volstaan (bijv. PHOTO-F1, PHOTO-F5, PHOTO-R1, PHOTO-R5, een kopgevel). Dat is nu NIET geactiveerd en leidt niet tot telling.

| Foto | Gevel | Adressen | Formaat | Waar staan | Waarom | Sluit gap |
|---|---|---|---|---|---|---|
| PHOTO-F1 | FRONT | 294-296, 290-292, 286-288 | LANDSCAPE, HELE_GEVEL | Op het voetpad voor de lage haag, recht tegenover het midden van deze groep (zelfde type standpunt als foto 2), gevel loodrecht in beeld, camera horizontaal. Kies een standpunt zonder lantaarnpaal, boom of fiets voor de entrees (verschuif zijwaarts) zodat de begane grond van 290 en 288 vrij komt. | Foto 2 dekt dit deel maar met afgedekte begane grond; nodig om entrees en begane-grondkozijnen te kunnen beoordelen. | FRONT UNKNOWN/PARTIAL -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-F2 | FRONT | 282-284, 278-280, 274-276 | LANDSCAPE, HELE_GEVEL | Op het voetpad voor de lage haag, recht tegenover het midden van deze groep (zelfde type standpunt als foto 2), gevel loodrecht in beeld, camera horizontaal. | Geen bevestigde voorgevelfoto voor deze panden. | FRONT UNKNOWN/PARTIAL -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-F3 | FRONT | 270-272, 266-268, 262-264 | LANDSCAPE, HELE_GEVEL | Op het voetpad voor de lage haag, recht tegenover het midden van deze groep (zelfde type standpunt als foto 2), gevel loodrecht in beeld, camera horizontaal. | Geen bevestigde voorgevelfoto voor deze panden. | FRONT UNKNOWN/PARTIAL -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-F4 | FRONT | 258-260, 254-256, 250-252 | LANDSCAPE, HELE_GEVEL | Op het voetpad voor de lage haag, recht tegenover het midden van deze groep (zelfde type standpunt als foto 2), gevel loodrecht in beeld, camera horizontaal. | Geen bevestigde voorgevelfoto voor deze panden. | FRONT UNKNOWN/PARTIAL -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-F5 | FRONT | 246-248, 242-244, 240 | LANDSCAPE, HELE_GEVEL | Op het voetpad voor de lage haag, recht tegenover het midden van deze groep (zelfde type standpunt als foto 2), gevel loodrecht in beeld, camera horizontaal. | Geen bevestigde voorgevelfoto voor deze panden. | FRONT UNKNOWN/PARTIAL -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-R1 | REAR | 294-296, 290-292, 286-288 | LANDSCAPE, HELE_GEVEL | Aan de achterzijde (achterpad of openbare ruimte achter de tuinen), recht tegenover het midden van deze groep; camera horizontaal op ooghoogte, niet van onderen zoals foto 3. | Er is geen achtergevelfoto die aan een pand is gekoppeld; foto 3 toont de achterzijde van een onbekend pand met afgedekte begane grond. | REAR UNKNOWN -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-R2 | REAR | 282-284, 278-280, 274-276 | LANDSCAPE, HELE_GEVEL | Aan de achterzijde (achterpad of openbare ruimte achter de tuinen), recht tegenover het midden van deze groep; camera horizontaal op ooghoogte, niet van onderen zoals foto 3. | Er is geen achtergevelfoto die aan een pand is gekoppeld; foto 3 toont de achterzijde van een onbekend pand met afgedekte begane grond. | REAR UNKNOWN -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-R3 | REAR | 270-272, 266-268, 262-264 | LANDSCAPE, HELE_GEVEL | Aan de achterzijde (achterpad of openbare ruimte achter de tuinen), recht tegenover het midden van deze groep; camera horizontaal op ooghoogte, niet van onderen zoals foto 3. | Er is geen achtergevelfoto die aan een pand is gekoppeld; foto 3 toont de achterzijde van een onbekend pand met afgedekte begane grond. | REAR UNKNOWN -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-R4 | REAR | 258-260, 254-256, 250-252 | LANDSCAPE, HELE_GEVEL | Aan de achterzijde (achterpad of openbare ruimte achter de tuinen), recht tegenover het midden van deze groep; camera horizontaal op ooghoogte, niet van onderen zoals foto 3. | Er is geen achtergevelfoto die aan een pand is gekoppeld; foto 3 toont de achterzijde van een onbekend pand met afgedekte begane grond. | REAR UNKNOWN -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-R5 | REAR | 246-248, 242-244, 240 | LANDSCAPE, HELE_GEVEL | Aan de achterzijde (achterpad of openbare ruimte achter de tuinen), recht tegenover het midden van deze groep; camera horizontaal op ooghoogte, niet van onderen zoals foto 3. | Er is geen achtergevelfoto die aan een pand is gekoppeld; foto 3 toont de achterzijde van een onbekend pand met afgedekte begane grond. | REAR UNKNOWN -> FULL_COVERAGE (zichtbaarheid) voor de genoemde panden |
| PHOTO-G1 | SIDE_GABLE | 294-296 | PORTRAIT, HELE_GEVEL | Loodrecht voor de kopgevel aan de hoogste-nummerzijde (nabij 296) van de reeks, vanaf het zijpad of de aangrenzende straat; camera horizontaal. | Foto 3 laat zien dat er minstens een kopgevel bestaat; of de uiteinden van de reeks 240-296 bouwblokeinden zijn is niet bewezen. Ter plaatse controleren; geen foto nodig als het uiteinde tegen een volgend blok aansluit. | LEFT_SIDE/RIGHT_SIDE UNKNOWN -> bekend |
| PHOTO-G2 | SIDE_GABLE | 240 | PORTRAIT, HELE_GEVEL | Loodrecht voor de kopgevel aan de laagste-nummerzijde (nabij 240) van de reeks, vanaf het zijpad of de aangrenzende straat; camera horizontaal. | Foto 3 laat zien dat er minstens een kopgevel bestaat; of de uiteinden van de reeks 240-296 bouwblokeinden zijn is niet bewezen. Ter plaatse controleren; geen foto nodig als het uiteinde tegen een volgend blok aansluit. | LEFT_SIDE/RIGHT_SIDE UNKNOWN -> bekend |

### Wat moet in beeld zijn

- FRONT: Van dakgoot tot maaiveld, linker en rechter buurwoning half in beeld voor overlap, en minstens twee leesbare huisnummerplaten (zo is de adres->pand koppeling bewijsbaar).
- REAR: Van dakgoot tot en met de begane grond (zo mogelijk over de overkapping/schutting heen), buurwoningen half in beeld, en bij elke foto een herkenningspunt (achterpad-ingang of huisnummer achter) of noteer de wandelvolgorde.
- SIDE_GABLE: De volledige zijgevel van maaiveld tot nok.

## Foto 1 (CONTEXT_ONLY): wat de foto helpt te begrijpen

- Op foto 1 staan dezelfde lantaarnpaal, struik en fiets als op foto 2; foto 2 is dus een frontaal detail uit het middendeel van deze straatzijde.
- Links van de lantaarnpaal loopt de straatzijde nog door tot een kopgevel achter een grote boom: dat deel valt buiten foto 2 (linkerrand) en is niet gedekt.
- Rechts van de lantaarnpaal loopt de gevel door tot een terugspringend deel; daarachter begint een tweede, aangrenzend bouwblok (PHO-M-012, buiten scope tot de gebouwgrens is vastgesteld).
- Begroeiing (boom, struiken, haag) verbergt vooral de begane grond links en in het midden; huisnummers zijn niet leesbaar, dus de positie ten opzichte van de adressen is niet te bewijzen.
