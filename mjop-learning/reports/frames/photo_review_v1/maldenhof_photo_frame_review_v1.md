# Maldenhof Frame Photo Human Review v1

Scope: menselijke review van de 20 photo observations en handmatige annotatie van foto 2. Geen gebouwtotaal, geen maten, geen painting area, geen frame instances, geen quantity-resolutie, geen MJOP-App wijziging.

## 1. Review decisions (append-only)

| Decision | Observation | Besluit | Reviewer |
|---|---|---|---|
| PHR-00001 | PHO-M-001 | ACCEPT | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00002 | PHO-M-002 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00003 | PHO-M-008 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00004 | PHO-M-016 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00005 | PHO-M-015 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00006 | PHO-M-003 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00007 | PHO-M-009 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00008 | PHO-M-013 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00009 | PHO-M-004 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00010 | PHO-M-010 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |
| PHR-00011 | PHO-M-014 | ACCEPT_OBSERVATION | human (user-approved), 2026-10-06T12:02:45Z |

Geaccepteerd: 11 van 20. Niet gereviewd en dus nog REVIEW_REQUIRED / REPEAT_CANDIDATE: PHO-M-005, PHO-M-006, PHO-M-007, PHO-M-011, PHO-M-012, PHO-M-017, PHO-M-018, PHO-M-019, PHO-M-020.

PHO-M-001 beantwoordt de open vraag: huisnummers 288 en 290 vallen binnen Maldenhof 240-296. ACCEPT_OBSERVATION bevestigt alleen dat het element op de foto zichtbaar is; het levert geen aantal, materiaal of maat op.

## 2. Rol van de foto's

- maldenhof_2.jpg: eerste telfoto (bijna frontaal, 288/290 zichtbaar).
- maldenhof_1.jpg: CONTEXT_ONLY.
- maldenhof_3.jpg: REAR_DETAIL.
- Geen gecombineerde telling over de drie foto's.

## 3. Annotatie foto 2 (handmatige lezing, geen automatische detectie)

19 kandidaten, allemaal REVIEW_REQUIRED, human decision PENDING.

### VISIBLE_COUNT_ON_PHOTO (maldenhof_2.jpg; NIET BUILDING_TOTAL)

| Categorie | Aantal | Kandidaten |
|---|---|---|
| FULL visible windows | 7 | 002, 003, 004, 005, 006, 007, 009 |
| PARTIAL windows | 2 | 001, 008 |
| Deuren (EXTERIOR_DOOR) | 1 | 011 |
| Dakramen (ROOF_WINDOW) | 5 | 014, 015, 016, 017, 018 |
| Dakkapelramen (parent ROOF_DORMER) | 1 | 019 |
| UNKNOWN_OPENING (niet als raam geteld) | 3 | 010, 012, 013 |

VISIBLE_WINDOW_CANDIDATE_COUNT (gevelramen FULL + PARTIAL, zonder dakramen en dakkapelraam): 9.

Duplicate review: 4 van de 7 FULL ramen zitten in twee mogelijke dubbele paren (002/003 en 004/005). Ze zijn niet samengevoegd. Tellen elk paar als een kozijn, dan zijn er 5 FULL ramen in plaats van 7.

Dit zijn zichtbare kandidaten op een foto, geen gebouwtotaal: het gebouw heeft meer ramen dan op de straatzijde van foto 2 zichtbaar zijn.

## 4. Repeat module candidates (REPEAT_CANDIDATE, non-active, geen multiplier)

| Module | Ramen gevel | Deuren | Onbekende openingen | Dakramen | Dakkapelramen |
|---|---|---|---|---|---|
| MOD-M2-A | 4 | 1 | 2 | 2 | 1 |
| MOD-M2-B | 5 | 0 | 1 | 3 | 0 |

Module A en B vertonen een mogelijk gespiegelde opbouw (lager dakschild met dakraam, terugliggend kozijn, bakstenen entreemuur met huisnummer), maar de zichtbare inhoud is niet gelijk; geen multiplier en geen USER_CONFIRMED_REPEAT.

Mogelijk hetzelfde: lager dakschild met dakraam (017 en 018), terugliggend kozijn op de eerste verdieping (007 en 008), bakstenen entreemuur met huisnummer (290 en 288). Verschillen: de dakkapel staat alleen in module A; de bovenste gevelrij en de zichtbare begane grond verschillen, deels door begroeiing. Nog geen USER_CONFIRMED_REPEAT.

## 5. Overlay

`reports/frames/photo_review_v1/maldenhof_2_frame_overlay.png`; review sheet: `reports/frames/photo_review_v1/maldenhof_2_review_sheet.md`.

## 6. Coverage gaps (begroeiing, tegenlicht, bereik)

- Begane grond links (x < 0,35): lantaarnpaal, fiets, boom en struiken verbergen alle gevelopeningen links van het portiek.
- Begane grond midden (x 0,45-0,80): struiken, fietsen en houten bergkasten verbergen het gevelvlak tussen de muren van 290 en 288; mogelijke ramen/deuren (FC-M2-012/013) zijn niet te beoordelen.
- Entree 290: deur en trap liggen in schaduw onder het portiek; alleen een donkere deuropening zichtbaar.
- Entree 288: de entree rechts bij nummer 288 is niet zichtbaar (struiken, muur, buiten beeld rechts).
- Rechterrand: de foto snijdt het gebouw af; de gevel loopt rechts door buiten beeld (naastliggende woningen niet geannoteerd).
- Linkerrand: een naastliggend bouwblok (kozijn en dakraam bij x < 0,05) is niet geannoteerd; waarschijnlijk buiten Maldenhof 240-296.
- Tegenlicht rechtsboven en bij de linker dakraam maakt dakramen minder goed leesbaar.
- De bouwlaag van de bovenste gevelrij is niet vast te stellen met GROUND/FIRST/ROOF/UNKNOWN; die ramen staan op UNKNOWN.
- Achterzijde, dakvlakken achter en zijgevels ontbreken volledig op foto 2 (zie foto 3 voor achterdetail; niet gecombineerd).

## 7. Wat nu wel en niet

Wel betrouwbaar: de kandidaten bestaan als zichtbare aanduidingen op foto 2 met een beeldlocatie, bouwlaag en zichtbaarheid; de FULL-kandidaten buiten de duplicate-paren zijn het sterkst. Nog geen gebouwtotaal, geen maten of oppervlakken, geen painting area en geen quantity-resolutie; alle zeven quantity-concepten blijven UNKNOWN. 756,80 blijft NOT_COMPARABLE (historische context). CPD-00001 en CPD-00002 zijn ongewijzigd.

## 8. Volgende stap

Menselijke review van de kandidaten (sheet), daarna pas frame instances/groups. Niets is vandaag aangemaakt.
