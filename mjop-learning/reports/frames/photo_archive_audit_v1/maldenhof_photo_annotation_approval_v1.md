# Maldenhof Photo Annotation: Human Approval Preparation v1

Voorbereidend document voor `Maldenhof Photo Annotation v1`. **Alle besluiten staan open en zijn niet namens de gebruiker goedgekeurd.** Er zijn geen instances, objecttotalen, tellingen of onderhoudskosten aangemaakt of gewijzigd.

Bronnen: `reports/frames/photo_archive_audit_v1/maldenhof_photo_archive_audit_v1.json` en `.md` (register MAP-001..036, PR #39, merge 83cceb5), de drie contactbladen in dezelfde map, `data/photo_evidence/maldenhof_address_pand_evidence_v1.json` (BAG-snapshots plus bevestigde building links), `data/frame_inventory/maldenhof_photo_frame_instances_v1.json` (bevroren foto 2) en `reports/frames/maldenhof_frame_coverage_v1.json`. De originele foto's staan in het projectarchief (zip), niet in de repository; ze zijn voor de audit en voor dit document daadwerkelijk bekeken. Visuele observaties zijn handmatige lezing door Claude en voorlopig.

## 1. Samenvatting van de huidige bewijspositie

| Onderdeel | Positie |
|---|---|
| Foto's | 36 originelen toegankelijk; SHA256, bytes en resolutie komen overeen met het manifest (audit). |
| Foto 2 (bevroren) | 11 zichtbare kozijnopeningen, 1 buitendeur, 9 FULL, 2 PARTIAL; ongewijzigd. Bron in archief: MAP-002. |
| Foto 3 | 0 instances; 10 kandidaten met menselijke besluiten (PR #37); pand NOT_PROVEN. Bron in archief: MAP-015. |
| Pandkoppeling | Alleen via leesbare huisnummerplaat plus bestaand BAG-bewijs, en alleen voor de muur met de plaat (15 foto's, MAP-002..005, 008, 009, 013, 029..036). |
| Overlap | 15 SAME_OBJECT_CANDIDATE-groepen, niets samengevoegd, geen unieke totalen. |
| Wat een mens nog moet beslissen | Alle beslispunten in sectie 6 (48). |

**Bewezen:** foto-integriteit (hashes), de adres-naar-pand-relatie uit de BAG-snapshots, de plaatlezingen zoals in het register (door een mens nog te bevestigen, APP-002 e.v.), de bronrelatie maldenhof_2 = MAP-002 en maldenhof_3 = MAP-015 (visuele pixelmatch, niet byte-identiek).
**Niet bewezen:** pand van elke achter-, dak-, tuin- en detailfoto zonder plaat; welke kozijnen op een foto bij welk pand horen; of overlappende foto's hetzelfde fysieke kozijn tonen; de zijde van de achter-/tuinfoto's; iedere uniciteit van een fysiek object.

**Vier niveaus (strikt gescheiden gehouden):** 1 zichtbare observatie; 2 kandidaat voor een fysiek object; 3 bewezen unieke fysieke instance; 4 bewezen koppeling aan een specifiek pand. In dit document bestaan alleen niveau 1 en 2. Niveau 3 komt niet voor. Niveau 4 bestaat alleen als plaat-muur-koppeling uit de audit.

Status per foto: `READY_FOR_REVIEW` = pandkoppeling via plaat staat en de foto is bruikbaar voor menselijke review; `NEEDS_EVIDENCE` = er ontbreekt specifiek bewijs; `NOT_PROVEN` = pand/zijde niet bewezen. De status zegt iets over bewijs, niet over de kwaliteit van het beeld alleen.

## 2. De 15 shortlistfoto's

| Foto | Bestand | Zijde (audit) | Platen | Pandkoppeling | Overlap | Status |
|---|---|---|---|---|---|---|
| MAP-003 | IMG_8518.JPEG | FRONT | 288, 286, 284, 282, 280, 278, 276 | pand 10 (274/276); pand 11 (278/280); pand 12 (282/284); pand 13 (286/288) | SOC-001, SOC-002, SOC-003 | READY_FOR_REVIEW |
| MAP-004 | IMG_8520.JPEG | FRONT | 280, 278, 276, 274 | pand 10 (274/276); pand 11 (278/280) | SOC-002, SOC-008 | READY_FOR_REVIEW |
| MAP-005 | IMG_8523.JPEG | FRONT | 262, 260, 258 | pand 6 (258/260); pand 7 (262/264) | SOC-004, SOC-005 | NEEDS_EVIDENCE |
| MAP-013 | P1000294.JPG | FRONT_OBLIQUE | 288, 286 | pand 13 (286/288) | SOC-003 | READY_FOR_REVIEW |
| MAP-008 | P1000218.JPG | FRONT_OBLIQUE | 268, 266 | pand 8 (266/268) | SOC-006, SOC-007, SOC-015 | READY_FOR_REVIEW |
| MAP-009 | P1000236.JPG | FRONT_OBLIQUE | 280 | pand 11 (278/280) | SOC-002, SOC-015 | READY_FOR_REVIEW |
| MAP-031 | P1000204.JPG | FRONT_OBLIQUE | 250 | pand 4 (250/252) | - | READY_FOR_REVIEW |
| MAP-032 | P1000216.JPG | FRONT_OBLIQUE | 266 | pand 8 (266/268) | SOC-006 | READY_FOR_REVIEW |
| MAP-029 | P1000193.JPG | DETAIL | 248 | pand 3 (246/248) | - | NEEDS_EVIDENCE |
| MAP-014 | P1000252.JPG | REAR_OR_SIDE | - | NOT_PROVEN | SOC-009 | NOT_PROVEN |
| MAP-018 | P1000259.JPG | REAR_OR_SIDE | - | NOT_PROVEN | SOC-011 | NOT_PROVEN |
| MAP-017 | P1000258.JPG | REAR_OR_SIDE | - | NOT_PROVEN | SOC-010 | NOT_PROVEN |
| MAP-019 | P1000261.JPG | ROOF | - | NOT_PROVEN | SOC-011 | NOT_PROVEN |
| MAP-020 | P1000262.JPG | ROOF | - | NOT_PROVEN | SOC-010 | NOT_PROVEN |
| MAP-021 | P1000266.JPG | REAR_OR_SIDE | - | NOT_PROVEN | - | NOT_PROVEN |

### MAP-003 (IMG_8518.JPEG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/IMG_8518.JPEG` (SHA256 `9f121e711b0cea13...`, 2048x1536), register-ID MAP-003.
- **Zijde:** Voorzijde (frontaal). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 10 (274/276, BAG 0363100012144766); pand 11 (278/280, BAG 0363100012091756); pand 12 (282/284, BAG 0363100012143647); pand 13 (286/288, BAG 0363100012121455). Bewijs: leesbare plaat(en) 288, 286, 284, 282, 280, 278, 276 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Drie bouwlagen en dakvlak van de straatzijde; entreemuren van metselwerk met kleine ramen en donkerrode deuren; witte kozijnen met draaivleugels op de verdiepingen; dakramen en een dakkapel linksboven; donkere houten betimmering; auto, lantaarnpaal en struiken voor de begane grond.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Verdiepingskozijnen (meerdere), dakkapelraam, dakramen, deuren en raampjes in entreemuren.
- **Overlap:** SOC-001 met MAP-002 (MEDIUM); SOC-002 met MAP-004, MAP-009 (MEDIUM); SOC-003 met MAP-013 (MEDIUM)
- **Onduidelijkheden en ontbrekend bewijs:** Tegenlicht in de onderste rij; of ramen naast een plaat bij dat adres horen is niet bewezen; overlap met foto 2 en MAP-004/009/013.
- **Statusreden:** Plaatlezing en pandkoppeling klaar voor menselijke controle.
- **Besluiten voor een mens:** APP-002, APP-011, APP-012, APP-013, APP-031, APP-034.

### MAP-004 (IMG_8520.JPEG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/IMG_8520.JPEG` (SHA256 `197556869a8e91a9...`, 2048x1536), register-ID MAP-004.
- **Zijde:** Voorzijde (frontaal). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 10 (274/276, BAG 0363100012144766); pand 11 (278/280, BAG 0363100012091756). Bewijs: leesbare plaat(en) 280, 278, 276, 274 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Zelfde straatzijde als MAP-003, verder naar rechts; lantaarnpaal en auto voor een entree; kozijnen met openstaande vleugels op de verdieping; kopgevel aan de rechterrand.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Verdiepingskozijnen met openstaande vleugels, dakramen, entreedeur en raampjes in entreemuren.
- **Overlap:** SOC-002 met MAP-003, MAP-009 (MEDIUM); SOC-008 met MAP-033 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Auto en lantaarnpaal voor de begane grond; platen alleen bij vergroting leesbaar.
- **Statusreden:** Plaatlezing en pandkoppeling klaar voor menselijke controle.
- **Besluiten voor een mens:** APP-003, APP-012, APP-018, APP-035.

### MAP-005 (IMG_8523.JPEG, voorzijde): NEEDS_EVIDENCE

- **Bron:** `Opname 14-08-2026/IMG_8523.JPEG` (SHA256 `0c4a0afbbcdcb6f2...`, 2048x1536), register-ID MAP-005.
- **Zijde:** Voorzijde (frontaal). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 6 (258/260, BAG 0363100012091974); pand 7 (262/264, BAG 0363100012070344). Bewijs: leesbare plaat(en) 262, 260, 258 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Frontaal beeld met lantaarnpaal midden voor een entree, aanhanger en motor op het voorerf; entreemuren met raampjes en platen; kozijnen op de verdieping; dakramen.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Raampjes in entreemuren, entreedeuren (deels afgedekt), verdiepingskozijnen, dakramen.
- **Overlap:** SOC-004 met MAP-006 (LOW); SOC-005 met MAP-034 (MEDIUM)
- **Onduidelijkheden en ontbrekend bewijs:** Afdekking begane grond; platen alleen bij vergroting leesbaar; twee panden in beeld, alleen de plaatmuren zijn gekoppeld.
- **Statusreden:** Lantaarnpaal, struik, motor en aanhanger dekken de begane grond af; plaatlezing alleen bij vergroting; aanvullend beeld van de onderste bouwlaag nodig.
- **Besluiten voor een mens:** APP-004, APP-014, APP-015, APP-036.

### MAP-013 (P1000294.JPG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/P1000294.JPG` (SHA256 `d7d8839fc966a927...`, 3264x2448), register-ID MAP-013.
- **Zijde:** Voorzijde (schuin). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 13 (286/288, BAG 0363100012121455). Bewijs: leesbare plaat(en) 288, 286 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Schuin beeld; entreemuur met plaat 288 en raam eromheen, plaat 286 rechts; dakraam op de lagere kap; gevelrij loopt door naar achteren.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Raam naast plaat 288, verdiepingskozijnen, dakraam.
- **Overlap:** SOC-003 met MAP-003 (MEDIUM)
- **Onduidelijkheden en ontbrekend bewijs:** Rest van de gevelrij op de achtergrond niet aan een pand gekoppeld.
- **Statusreden:** Twee platen leesbaar; beide horen bij pand 13 (286/288).
- **Besluiten voor een mens:** APP-007, APP-013, APP-037.

### MAP-008 (P1000218.JPG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/P1000218.JPG` (SHA256 `e139392c662ec909...`, 3264x2448), register-ID MAP-008.
- **Zijde:** Voorzijde (schuin). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 8 (266/268, BAG 0363100012107492). Bewijs: leesbare plaat(en) 268, 266 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Schuin beeld langs de gevel; op de voorgrond een muur met een raam met kippengaas naast plaat 268 en plaat 266 rechts; erachter verdiepingskozijnen, houten betimmering en een dakraam.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Raam in muur (plaat 268), verdiepingskozijnen, dakraam.
- **Overlap:** SOC-006 met MAP-032 (MEDIUM); SOC-007 met MAP-036 (HIGH); SOC-015 met MAP-007, MAP-009, MAP-010 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Raamtoewijzing aan plaat 268 niet bewezen; het gebouwdeel erachter is niet aan een pand gekoppeld.
- **Statusreden:** Twee platen leesbaar; beide horen bij pand 8 (266/268).
- **Besluiten voor een mens:** APP-005, APP-016, APP-017, APP-025, APP-038.

### MAP-009 (P1000236.JPG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/P1000236.JPG` (SHA256 `15591a9648ddfec7...`, 3264x2448), register-ID MAP-009.
- **Zijde:** Voorzijde (schuin). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 11 (278/280, BAG 0363100012091756). Bewijs: leesbare plaat(en) 280 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Schuin beeld; groot wit kozijn linksboven, donkere houten kap, plaat 280 op de entreemuur, auto en hortensia voor de onderrand.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Groot verdiepingskozijn links, overige verdiepingskozijnen, dakramen.
- **Overlap:** SOC-002 met MAP-003, MAP-004 (MEDIUM); SOC-015 met MAP-007, MAP-008, MAP-010 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Eén plaat; kozijnen links en erachter zijn niet aan een pand gekoppeld.
- **Statusreden:** Eén plaat (280) leesbaar bij vergroting; menselijke bevestiging van de lezing nodig.
- **Besluiten voor een mens:** APP-006, APP-012, APP-025, APP-039.

### MAP-031 (P1000204.JPG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/P1000204.JPG` (SHA256 `a42961d1f2599412...`, 3264x2448), register-ID MAP-031.
- **Zijde:** Voorzijde (schuin). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 4 (250/252, BAG 0363100012140664). Bewijs: leesbare plaat(en) 250 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Schuin beeld; plaat 250 op de muur links; verdiepingskozijnen, dakraam op de lagere kap, voordeur rechtsonder zichtbaar.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Verdiepingskozijnen, voordeur, dakraam.
- **Overlap:** geen gemarkeerd.
- **Onduidelijkheden en ontbrekend bewijs:** Lensflare linksboven; rest van het beeld niet aan een pand gekoppeld.
- **Statusreden:** Eén plaat (250) leesbaar; alleen de muur met de plaat is aan pand 4 gekoppeld.
- **Besluiten voor een mens:** APP-009, APP-040.

### MAP-032 (P1000216.JPG, voorzijde): READY_FOR_REVIEW

- **Bron:** `Opname 14-08-2026/P1000216.JPG` (SHA256 `888118a65a94a004...`, 3264x2448), register-ID MAP-032.
- **Zijde:** Voorzijde (schuin). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 8 (266/268, BAG 0363100012107492). Bewijs: leesbare plaat(en) 266 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Schuin beeld; plaat 266 op de muur links; verdiepingskozijn met open vleugel; kozijn op de begane grond; struiken voor de gevel.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Verdiepingskozijn met open vleugel, kozijn begane grond.
- **Overlap:** SOC-006 met MAP-008 (MEDIUM)
- **Onduidelijkheden en ontbrekend bewijs:** Struiken voor de begane grond; rest niet aan een pand gekoppeld.
- **Statusreden:** Eén plaat (266) leesbaar; open raamvleugel; overlap met MAP-008 (SOC-006) controleren.
- **Besluiten voor een mens:** APP-010, APP-016, APP-041.

### MAP-029 (P1000193.JPG, voorzijde): NEEDS_EVIDENCE

- **Bron:** `Opname 14-08-2026/P1000193.JPG` (SHA256 `b85192ab5a9886de...`, 3264x2448), register-ID MAP-029.
- **Zijde:** Detail, voorzijde waarschijnlijk (niet bewezen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** pand 3 (246/248, BAG 0363100012078022). Bewijs: leesbare plaat(en) 248 plus BAG-snapshot en bevestigde building links (maldenhof_address_pand_evidence_v1); geldt alleen de plaatmuur.
- **Visueel waarneembaar (voorlopig):** Entreemuur met plaat 248 en een raam links ervan; erboven een dakraam; begroeiing voor de onderkant.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Raam in entreemuur, dakraam.
- **Overlap:** geen gemarkeerd.
- **Onduidelijkheden en ontbrekend bewijs:** Eén muur en één raam; geen overzichtsbeeld van pand 3.
- **Statusreden:** Detailfoto: de plaat bewijst alleen de entreemuur van pand 3; er is geen overzichtsfoto van pand 3.
- **Besluiten voor een mens:** APP-008, APP-042.

### MAP-014 (P1000252.JPG, achterzijde/tuin): NOT_PROVEN

- **Bron:** `Opname 14-08-2026/P1000252.JPG` (SHA256 `11ff84fc4ff0cf96...`, 3264x2448), register-ID MAP-014.
- **Zijde:** Achterzijde of tuin/zijde (nog niet vast te stellen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** NOT_PROVEN (geen bewijs). Geen plaat; geen koppeling.
- **Visueel waarneembaar (voorlopig):** Dakkapel met wit meerdelig kozijn, balkon met rood kozijn en balkondeur onder een lager dakschild, zonwering, houten schutting op de voorgrond, kopgevel rechts; zelfde tafereel als MAP-015 (bron van maldenhof_3).
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Dakkapelraam, balkondeur/raamcombinatie, dakramen (zelfde elementen als de annotatie van maldenhof_3).
- **Overlap:** SOC-009 met MAP-015 (HIGH)
- **Onduidelijkheden en ontbrekend bewijs:** Geen huisnummer; pand en gevelzijde onbekend; begane grond afgedekt door schutting.
- **Statusreden:** Geen leesbaar huisnummer en geen ander bewijs; pand en gevelzijde niet bewezen.
- **Besluiten voor een mens:** APP-019, APP-026, APP-027, APP-032, APP-043.

### MAP-018 (P1000259.JPG, achterzijde/tuin): NOT_PROVEN

- **Bron:** `Opname 14-08-2026/P1000259.JPG` (SHA256 `ce5ad5b4f89b1cde...`, 3264x2448), register-ID MAP-018.
- **Zijde:** Achterzijde of tuin/zijde (nog niet vast te stellen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** NOT_PROVEN (geen bewijs). Geen plaat; geen koppeling.
- **Visueel waarneembaar (voorlopig):** Balkons met witte hekwerken, grote witte kozijnen, rode deuren rechtsonder, donkere schutting; dakramen en dakschild erboven.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Balkondeuren (rood), grote kozijnen, dakramen.
- **Overlap:** SOC-011 met MAP-019 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Geen huisnummer; pand en zijde onbekend; onderste rij deels afgedekt.
- **Statusreden:** Geen leesbaar huisnummer en geen ander bewijs; pand en gevelzijde niet bewezen.
- **Besluiten voor een mens:** APP-021, APP-026, APP-027, APP-044.

### MAP-017 (P1000258.JPG, achterzijde/tuin): NOT_PROVEN

- **Bron:** `Opname 14-08-2026/P1000258.JPG` (SHA256 `98615f0811bba802...`, 3264x2448), register-ID MAP-017.
- **Zijde:** Achterzijde of tuin/zijde (nog niet vast te stellen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** NOT_PROVEN (geen bewijs). Geen plaat; geen koppeling.
- **Visueel waarneembaar (voorlopig):** Tuinafscheiding van gaas en hout met schuurtje en rood dak voor de begane grond; balkon met rode en witte kozijnen op de verdieping; dakramen erboven.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Balkonkozijn(en), dakramen; begane grond afgedekt.
- **Overlap:** SOC-010 met MAP-020 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Geen huisnummer; begroeiing en schutting; pand en zijde onbekend.
- **Statusreden:** Geen leesbaar huisnummer en geen ander bewijs; pand en gevelzijde niet bewezen.
- **Besluiten voor een mens:** APP-020, APP-026, APP-027, APP-045.

### MAP-019 (P1000261.JPG, achterzijde/tuin): NOT_PROVEN

- **Bron:** `Opname 14-08-2026/P1000261.JPG` (SHA256 `a8861c1f512091e5...`, 3264x2448), register-ID MAP-019.
- **Zijde:** Dakvlak met achterzijde (zijde nog niet vast te stellen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** NOT_PROVEN (geen bewijs). Geen plaat; geen koppeling.
- **Visueel waarneembaar (voorlopig):** Dakvlak vult het beeld; balkon met wit hekwerk en groot kozijn met rode randen; dakramen; lantaarn op de voorgrond; opname van onderen.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Balkonkozijn, dakramen.
- **Overlap:** SOC-011 met MAP-018 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Dakvlak dominant; bovenste gevelrij smal en schuin; pand en zijde onbekend.
- **Statusreden:** Geen leesbaar huisnummer en geen ander bewijs; pand en gevelzijde niet bewezen.
- **Besluiten voor een mens:** APP-021, APP-026, APP-027, APP-046.

### MAP-020 (P1000262.JPG, achterzijde/tuin): NOT_PROVEN

- **Bron:** `Opname 14-08-2026/P1000262.JPG` (SHA256 `c37276275bbc9de7...`, 3264x2448), register-ID MAP-020.
- **Zijde:** Dakvlak met achterzijde (zijde nog niet vast te stellen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** NOT_PROVEN (geen bewijs). Geen plaat; geen koppeling.
- **Visueel waarneembaar (voorlopig):** Dakvlak met dakramen en schoorstenen; balkons links; tuinhuis en hekwerk voor de begane grond.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Dakramen, balkonkozijnen.
- **Overlap:** SOC-010 met MAP-017 (LOW)
- **Onduidelijkheden en ontbrekend bewijs:** Dakvlak dominant; begane grond afgedekt; pand en zijde onbekend.
- **Statusreden:** Geen leesbaar huisnummer en geen ander bewijs; pand en gevelzijde niet bewezen.
- **Besluiten voor een mens:** APP-020, APP-026, APP-027, APP-047.

### MAP-021 (P1000266.JPG, achterzijde/tuin): NOT_PROVEN

- **Bron:** `Opname 14-08-2026/P1000266.JPG` (SHA256 `4c76f41fb8eadeab...`, 3264x2448), register-ID MAP-021.
- **Zijde:** Achterzijde of tuin/zijde (nog niet vast te stellen). Methode: handmatige visuele lezing.
- **Pandkoppeling en bewijs:** NOT_PROVEN (geen bewijs). Geen plaat; geen koppeling.
- **Visueel waarneembaar (voorlopig):** Tuinzijde met dakkapel, meerdelig kozijn, schuifpuien/veranda op de begane grond, tuinmeubilair en bomen; zijde (achter of kopgevel) niet vast te stellen.
- **Mogelijke elementen (observaties, geen instances en geen aantallen):** Dakkapelraam, schuifpui(en) begane grond, overige kozijnen onbepaald.
- **Overlap:** geen gemarkeerd.
- **Onduidelijkheden en ontbrekend bewijs:** Zijde (achter of kopgevel) niet vast te stellen; afdekking door boom en tuinmeubilair; pand onbekend.
- **Statusreden:** Geen leesbaar huisnummer en geen ander bewijs; pand en gevelzijde niet bewezen.
- **Besluiten voor een mens:** APP-026, APP-027, APP-048.

## 3. Pandkoppelingen: wel en niet bewezen

| # | Pand (BAG) | Adressen | Bewezen via plaat | Overzichtsfoto's | Detailfoto's |
|---|---|---|---|---|---|
| 1 | 0363100012137996 | 240 | geen | - | - |
| 2 | 0363100012102659 | 242, 244 | 244 | - | MAP-030 |
| 3 | 0363100012078022 | 246, 248 | 248 | - | MAP-029 |
| 4 | 0363100012140664 | 250, 252 | 250 | MAP-031 | - |
| 5 | 0363100012141419 | 254, 256 | geen | - | - |
| 6 | 0363100012091974 | 258, 260 | 258, 260 | MAP-005 | MAP-034 |
| 7 | 0363100012070344 | 262, 264 | 262 | MAP-005 | - |
| 8 | 0363100012107492 | 266, 268 | 266, 268 | MAP-008, MAP-032 | MAP-036 |
| 9 | 0363100012071880 | 270, 272 | 270 | - | MAP-035 |
| 10 | 0363100012144766 | 274, 276 | 274, 276 | MAP-003, MAP-004 | MAP-033 |
| 11 | 0363100012091756 | 278, 280 | 278, 280 | MAP-003, MAP-004, MAP-009 | - |
| 12 | 0363100012143647 | 282, 284 | 282, 284 | MAP-003 | - |
| 13 | 0363100012121455 | 286, 288 | 286, 288 | MAP-002, MAP-003, MAP-013 | - |
| 14 | 0363100012134188 | 290, 292 | 290 | MAP-002 | - |
| 15 | 0363100012127361 | 294, 296 | geen | - | - |

- **Wel bewezen (alleen plaatmuur):** de panden met een leesbare plaat hierboven. Dit bewijst niet dat de overige kozijnen op dezelfde foto bij datzelfde pand horen.
- **Niet bewezen:** panden 1, 5 en 15 (geen archieffoto met plaat); alle achterzijden, kopgevels, dak- en tuinbeelden; de gevelstukken tussen platen.
- **Voorzijde pand 2, 3 en 9:** alleen een detailfoto met plaat (MAP-030, MAP-029, MAP-035).

## 4. Overlapgroepen die menselijke controle vereisen

| Groep | Foto's | Ondersteunende aanwijzing | Ontbrekend bewijs | Zekerheid | Besluit |
|---|---|---|---|---|---|
| SOC-001 | MAP-002, MAP-003 | Plaat 288 en aangrenzende voorgevel in beide frames. | Bevestigen dat dezelfde plaatmuur/kozijnen zichtbaar zijn en niet buurobjecten. | MEDIUM | APP-011 |
| SOC-002 | MAP-003, MAP-004, MAP-009 | Platen 276/278/280 in meerdere frames (MAP-003 en MAP-004: 276, 278, 280; MAP-009: 280). | Bevestigen dat dezelfde plaatmuur/kozijnen zichtbaar zijn en niet buurobjecten. | MEDIUM | APP-012 |
| SOC-003 | MAP-003, MAP-013 | Platen 288/286 en bijbehorende ramen in beide frames. | Bevestigen dat dezelfde plaatmuur/kozijnen zichtbaar zijn en niet buurobjecten. | MEDIUM | APP-013 |
| SOC-004 | MAP-005, MAP-006 | Zelfde stuk straatzijde met aanhanger/kozijnen rond de platen 258-262 (visuele gelijkenis). | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-014 |
| SOC-005 | MAP-005, MAP-034 | Plaat 258 in beide frames. | Bevestigen dat dezelfde plaatmuur/kozijnen zichtbaar zijn en niet buurobjecten. | MEDIUM | APP-015 |
| SOC-006 | MAP-008, MAP-032 | Plaat 266 in beide frames. | Bevestigen dat dezelfde plaatmuur/kozijnen zichtbaar zijn en niet buurobjecten. | MEDIUM | APP-016 |
| SOC-007 | MAP-008, MAP-036 | Plaat 268 met raam met kippengaas in beide frames. | Vergelijking van contouren, kozijnindeling en omgeving door een mens. | HIGH | APP-017 |
| SOC-008 | MAP-004, MAP-033 | Plaat 276 met raam in beide frames (raamtoewijzing aan plaat niet bewezen). | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-018 |
| SOC-009 | MAP-014, MAP-015 | Zelfde dakkapel, dakschild en rode balkondeur vanuit twee opnamepunten; MAP-015 is de bron van maldenhof_3. | Vergelijking van contouren, kozijnindeling en omgeving door een mens. | HIGH | APP-019 |
| SOC-010 | MAP-017, MAP-020 | Tuinafscheiding en schuurtje met rood dak in beide frames. | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-020 |
| SOC-011 | MAP-018, MAP-019 | Balkon met rood kozijn en rode deuren in beide frames. | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-021 |
| SOC-012 | MAP-024, MAP-028 | Twee ramen met open draaidelen in houten betimmering in beide frames. | Bevestigen dat dezelfde plaatmuur/kozijnen zichtbaar zijn en niet buurobjecten. | MEDIUM | APP-022 |
| SOC-013 | MAP-023, MAP-024 | Raam met open boven-/draaideel in houten betimmering; hoek verschilt sterk. | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-023 |
| SOC-014 | MAP-025, MAP-026 | Houten dakschild met raam en deur in beide (gedraaide) frames. | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-024 |
| SOC-015 | MAP-007, MAP-008, MAP-009, MAP-010 | Aansluitende schuine opnamen van dezelfde voorgevelstrook; kozijnen kunnen in meerdere frames voorkomen. | Gelijkenis is globaal; geen gedeeld uniek kenmerk vastgesteld. | LOW | APP-025 |

Alle 15 groepen blijven `SAME_OBJECT_CANDIDATE`. Er is niets samengevoegd en er zijn geen unieke objecttotalen berekend. Een gedeelde huisnummerplaat in twee foto's bewijst dat dezelfde muur is gefotografeerd, niet dat elk kozijn op beide foto's hetzelfde object is.

## 5. Ontbrekend bewijs per pand

| # | Adressen | Ontbreekt |
|---|---|---|
| 1 | 240 | voorzijde: geen archieffoto met plaat; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 2 | 242, 244 | voorzijde: alleen detailfoto, geen overzicht; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 3 | 246, 248 | voorzijde: alleen detailfoto, geen overzicht; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 4 | 250, 252 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 5 | 254, 256 | voorzijde: geen archieffoto met plaat; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 6 | 258, 260 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 7 | 262, 264 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 8 | 266, 268 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 9 | 270, 272 | voorzijde: alleen detailfoto, geen overzicht; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 10 | 274, 276 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 11 | 278, 280 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 12 | 282, 284 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 13 | 286, 288 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 14 | 290, 292 | voorzijde: volledige gevel en begane grond niet beoordeeld; platen bewijzen alleen de plaatmuur; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |
| 15 | 294, 296 | voorzijde: geen archieffoto met plaat; achterzijde: geen bewezen foto; kopgevel/zijgevel: geen bewezen foto |

## 6. Beslispunten (allemaal OPEN)

Elk beslispunt heeft een uniek ID. Het voorstel is een suggestie van Claude, geen besluit. Een antwoord van een mens wordt later append-only vastgelegd in een besluitenregister (zoals eerdere stappen).

| ID | Onderwerp | Foto's/object | Vraag | Voorstel (niet goedgekeurd) | Status |
|---|---|---|---|---|---|
| APP-001 | Plaatregel: een plaat bewijst alleen de muur | alle plaatfoto's | Akkoord dat een leesbare huisnummerplaat alleen de muur met die plaat aan een pand koppelt en niet automatisch de overige ramen/deuren/gevelstukken op dezelfde foto? | JA (huidige regel uit de audit en eerdere stappen). | OPEN |
| APP-002 | Plaatlezing en pandkoppeling MAP-003 | MAP-003 | Zijn de platen 288, 286, 284, 282, 280, 278, 276 correct gelezen en is de koppeling aan pand 10 (274/276), pand 11 (278/280), pand 12 (282/284), pand 13 (286/288) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. Let op: plaat(en) alleen bij vergroting leesbaar. | OPEN |
| APP-003 | Plaatlezing en pandkoppeling MAP-004 | MAP-004 | Zijn de platen 280, 278, 276, 274 correct gelezen en is de koppeling aan pand 10 (274/276), pand 11 (278/280) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. Let op: plaat(en) alleen bij vergroting leesbaar. | OPEN |
| APP-004 | Plaatlezing en pandkoppeling MAP-005 | MAP-005 | Zijn de platen 262, 260, 258 correct gelezen en is de koppeling aan pand 6 (258/260), pand 7 (262/264) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. Let op: plaat(en) alleen bij vergroting leesbaar. | OPEN |
| APP-005 | Plaatlezing en pandkoppeling MAP-008 | MAP-008 | Zijn de platen 268, 266 correct gelezen en is de koppeling aan pand 8 (266/268) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. | OPEN |
| APP-006 | Plaatlezing en pandkoppeling MAP-009 | MAP-009 | Zijn de platen 280 correct gelezen en is de koppeling aan pand 11 (278/280) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. Let op: plaat(en) alleen bij vergroting leesbaar. | OPEN |
| APP-007 | Plaatlezing en pandkoppeling MAP-013 | MAP-013 | Zijn de platen 288, 286 correct gelezen en is de koppeling aan pand 13 (286/288) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. | OPEN |
| APP-008 | Plaatlezing en pandkoppeling MAP-029 | MAP-029 | Zijn de platen 248 correct gelezen en is de koppeling aan pand 3 (246/248) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. | OPEN |
| APP-009 | Plaatlezing en pandkoppeling MAP-031 | MAP-031 | Zijn de platen 250 correct gelezen en is de koppeling aan pand 4 (250/252) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. | OPEN |
| APP-010 | Plaatlezing en pandkoppeling MAP-032 | MAP-032 | Zijn de platen 266 correct gelezen en is de koppeling aan pand 8 (266/268) voldoende bewezen (alleen de plaatmuur)? | JA na visuele controle op het origineel. | OPEN |
| APP-011 | Overlap SOC-001 | MAP-002, MAP-003 | Tonen MAP-002, MAP-003 hetzelfde fysieke object (Plaat 288 en aangrenzende voorgevel in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: MEDIUM. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-012 | Overlap SOC-002 | MAP-003, MAP-004, MAP-009 | Tonen MAP-003, MAP-004, MAP-009 hetzelfde fysieke object (Platen 276/278/280 in meerdere frames (MAP-003 en MAP-004: 276, 278, 280; MAP-009: 280).), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: MEDIUM. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-013 | Overlap SOC-003 | MAP-003, MAP-013 | Tonen MAP-003, MAP-013 hetzelfde fysieke object (Platen 288/286 en bijbehorende ramen in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: MEDIUM. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-014 | Overlap SOC-004 | MAP-005, MAP-006 | Tonen MAP-005, MAP-006 hetzelfde fysieke object (Zelfde stuk straatzijde met aanhanger/kozijnen rond de platen 258-262 (visuele gelijkenis).), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-015 | Overlap SOC-005 | MAP-005, MAP-034 | Tonen MAP-005, MAP-034 hetzelfde fysieke object (Plaat 258 in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: MEDIUM. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-016 | Overlap SOC-006 | MAP-008, MAP-032 | Tonen MAP-008, MAP-032 hetzelfde fysieke object (Plaat 266 in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: MEDIUM. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-017 | Overlap SOC-007 | MAP-008, MAP-036 | Tonen MAP-008, MAP-036 hetzelfde fysieke object (Plaat 268 met raam met kippengaas in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: HIGH. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-018 | Overlap SOC-008 | MAP-004, MAP-033 | Tonen MAP-004, MAP-033 hetzelfde fysieke object (Plaat 276 met raam in beide frames (raamtoewijzing aan plaat niet bewezen).), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-019 | Overlap SOC-009 | MAP-014, MAP-015 | Tonen MAP-014, MAP-015 hetzelfde fysieke object (Zelfde dakkapel, dakschild en rode balkondeur vanuit twee opnamepunten; MAP-015 is de bron van maldenhof_3.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: HIGH. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-020 | Overlap SOC-010 | MAP-017, MAP-020 | Tonen MAP-017, MAP-020 hetzelfde fysieke object (Tuinafscheiding en schuurtje met rood dak in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-021 | Overlap SOC-011 | MAP-018, MAP-019 | Tonen MAP-018, MAP-019 hetzelfde fysieke object (Balkon met rood kozijn en rode deuren in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-022 | Overlap SOC-012 | MAP-024, MAP-028 | Tonen MAP-024, MAP-028 hetzelfde fysieke object (Twee ramen met open draaidelen in houten betimmering in beide frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: MEDIUM. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. Geen shortlistfoto betrokken: lage prioriteit. | OPEN |
| APP-023 | Overlap SOC-013 | MAP-023, MAP-024 | Tonen MAP-023, MAP-024 hetzelfde fysieke object (Raam met open boven-/draaideel in houten betimmering; hoek verschilt sterk.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. Geen shortlistfoto betrokken: lage prioriteit. | OPEN |
| APP-024 | Overlap SOC-014 | MAP-025, MAP-026 | Tonen MAP-025, MAP-026 hetzelfde fysieke object (Houten dakschild met raam en deur in beide (gedraaide) frames.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. Geen shortlistfoto betrokken: lage prioriteit. | OPEN |
| APP-025 | Overlap SOC-015 | MAP-007, MAP-008, MAP-009, MAP-010 | Tonen MAP-007, MAP-008, MAP-009, MAP-010 hetzelfde fysieke object (Aansluitende schuine opnamen van dezelfde voorgevelstrook; kozijnen kunnen in meerdere frames voorkomen.), of zijn het verschillende objecten, of is dat niet vast te stellen? Zekerheid in audit: LOW. | Menselijke visuele vergelijking; antwoord SAME / DIFFERENT / UNDECIDABLE per object. Geen samenvoeging door Claude. | OPEN |
| APP-026 | Achterzijde: bewijsroute voor pandidentificatie | MAP-014, MAP-017, MAP-018, MAP-019, MAP-020, MAP-021 | Hoe wordt het pand van de achter-/tuinfoto's bepaald (kennis van de gebruiker, huisnummers op de achtergevel, extra foto's)? Tot die tijd blijft het pand NOT_PROVEN. | Voorstel: NOT_PROVEN laten; gebruiker geeft aan welke achtergevels (of welk adres) op welke foto staan, of levert foto's met achterzijde-huisnummers. | OPEN |
| APP-027 | Zijde-classificatie achter/zij/tuin/dak | MAP-014, MAP-017, MAP-018, MAP-019, MAP-020, MAP-021 | Bevestig per foto of het de achterzijde, een kopgevel/zijgevel, een tuinzijde of alleen een dakvlak toont (nu REAR_OR_SIDE of ROOF). | Menselijke classificatie per foto. | OPEN |
| APP-028 | Aanvullend fotografisch bewijs | pand 1, 5, 15 (geen frontbewijs); pand 2, 3, 9 (alleen detailfoto) | Zijn aanvullende foto's nodig voor de panden zonder of met alleen detailbewijs, en voor alle achterzijden? | JA voor panden 1, 5 en 15 (geen archieffoto met plaat) en voor alle achterzijden; panden 2, 3 en 9 hebben een overzichtsfoto nodig voor kozijnannotatie. | OPEN |
| APP-029 | Telregel en samengestelde kozijnen hergebruiken | alle nieuwe annotaties | Dezelfde telregel als bij foto 2 en 3 toepassen: een kandidaat = een fysieke opening tussen bouwkundige scheidingen; kozijnstijlen en vleugels scheiden niet; raam-/deurcombinaties in een onafgebroken kozijn zijn een opening (WINDOW_DOOR_COMBINATION)? | JA (bestaande conventie; geen parallel model). | OPEN |
| APP-030 | Zichtbaarheid FULL/PARTIAL | alle nieuwe annotaties | Dezelfde regels toepassen: FULL als de opening volledig begrensd zichtbaar is, PARTIAL bij afsnijding of afdekking, HEAVILY_OCCLUDED en UNKNOWN_OPENING bij te zware afdekking? | JA (bestaande conventie); per kandidaat beslist een mens bij de review. | OPEN |
| APP-031 | Overlapzone met bevroren foto 2 | MAP-002, MAP-003 | Mogen kandidaten op MAP-003 in de zone rond plaat 288 worden geannoteerd als aparte kandidaten met overlapmarkering, zonder optelling bij foto 2 en zonder wijziging van de bevroren telling? | JA, met SAME_OBJECT_CANDIDATE-markering; geen optelling en geen unieke totalen. | OPEN |
| APP-032 | MAP-015 en foto 3 | MAP-015, maldenhof_3, MAP-014 | Blijft de bestaande annotatie op maldenhof_3.jpg leidend, en mag MAP-015 (3264x2448) alleen als referentie met hogere resolutie dienen, zonder bestaande FC-M3-bboxes en besluiten te wijzigen? | JA; nieuwe annotaties op MAP-014 apart houden. | OPEN |
| APP-033 | Volgorde van de annotatiewerkzaamheden | zie sectie 8 | Akkoord met de voorgestelde volgorde (voorzijde met bewezen platen eerst, achterzijde pas na beantwoording van de bewijsroute)? | JA, of aanpassen. | OPEN |
| APP-034 | Geschiktheid als annotatiebron MAP-003 | MAP-003 | Is MAP-003 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-035 | Geschiktheid als annotatiebron MAP-004 | MAP-004 | Is MAP-004 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-036 | Geschiktheid als annotatiebron MAP-005 | MAP-005 | Is MAP-005 geschikt als annotatiebron in de huidige staat (NEEDS_EVIDENCE), of moet eerst bewijs of een betere foto worden toegevoegd? | NEE tot het ontbrekende bewijs is aangevuld; zie de statusreden. | OPEN |
| APP-037 | Geschiktheid als annotatiebron MAP-013 | MAP-013 | Is MAP-013 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-038 | Geschiktheid als annotatiebron MAP-008 | MAP-008 | Is MAP-008 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-039 | Geschiktheid als annotatiebron MAP-009 | MAP-009 | Is MAP-009 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-040 | Geschiktheid als annotatiebron MAP-031 | MAP-031 | Is MAP-031 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-041 | Geschiktheid als annotatiebron MAP-032 | MAP-032 | Is MAP-032 geschikt als annotatiebron in de huidige staat (READY_FOR_REVIEW), of moet eerst bewijs of een betere foto worden toegevoegd? | JA, annotatie voorbereiden na de bijbehorende APP-besluiten. | OPEN |
| APP-042 | Geschiktheid als annotatiebron MAP-029 | MAP-029 | Is MAP-029 geschikt als annotatiebron in de huidige staat (NEEDS_EVIDENCE), of moet eerst bewijs of een betere foto worden toegevoegd? | NEE tot het ontbrekende bewijs is aangevuld; zie de statusreden. | OPEN |
| APP-043 | Geschiktheid als annotatiebron MAP-014 | MAP-014 | Is MAP-014 geschikt als annotatiebron in de huidige staat (NOT_PROVEN), of moet eerst bewijs of een betere foto worden toegevoegd? | Alleen annotatie van zichtbare observaties zonder pandkoppeling, na antwoord op de bewijsroute. | OPEN |
| APP-044 | Geschiktheid als annotatiebron MAP-018 | MAP-018 | Is MAP-018 geschikt als annotatiebron in de huidige staat (NOT_PROVEN), of moet eerst bewijs of een betere foto worden toegevoegd? | Alleen annotatie van zichtbare observaties zonder pandkoppeling, na antwoord op de bewijsroute. | OPEN |
| APP-045 | Geschiktheid als annotatiebron MAP-017 | MAP-017 | Is MAP-017 geschikt als annotatiebron in de huidige staat (NOT_PROVEN), of moet eerst bewijs of een betere foto worden toegevoegd? | Alleen annotatie van zichtbare observaties zonder pandkoppeling, na antwoord op de bewijsroute. | OPEN |
| APP-046 | Geschiktheid als annotatiebron MAP-019 | MAP-019 | Is MAP-019 geschikt als annotatiebron in de huidige staat (NOT_PROVEN), of moet eerst bewijs of een betere foto worden toegevoegd? | Alleen annotatie van zichtbare observaties zonder pandkoppeling, na antwoord op de bewijsroute. | OPEN |
| APP-047 | Geschiktheid als annotatiebron MAP-020 | MAP-020 | Is MAP-020 geschikt als annotatiebron in de huidige staat (NOT_PROVEN), of moet eerst bewijs of een betere foto worden toegevoegd? | Alleen annotatie van zichtbare observaties zonder pandkoppeling, na antwoord op de bewijsroute. | OPEN |
| APP-048 | Geschiktheid als annotatiebron MAP-021 | MAP-021 | Is MAP-021 geschikt als annotatiebron in de huidige staat (NOT_PROVEN), of moet eerst bewijs of een betere foto worden toegevoegd? | Alleen annotatie van zichtbare observaties zonder pandkoppeling, na antwoord op de bewijsroute. | OPEN |

Totaal: 48 beslispunten, 48 OPEN, 0 goedgekeurd.

## 7. Risico's

1. **Onjuiste pandtoewijzing door plaatnabijheid:** een plaat staat naast een raam, maar bewijst het raam niet (MAP-033, 035, 036; ook MAP-008). Mitigatie: plaatregel APP-001.
2. **Twee panden per foto:** MAP-003 toont platen van vier panden, MAP-005 van twee; kozijnen tussen platen horen niet automatisch bij een van beide. Mitigatie: elementen zonder bewijs blijven zonder pand.
3. **Achterzijde zonder huisnummers:** alle zes de achter/tuinfoto's zijn NOT_PROVEN; gelijkenis met foto 3 of de dakkapel/dakramen is geen bewijs.
4. **Dubbeltelling door overlap:** voorzijde-opnamen overlappen elkaar en foto 2 (SOC-001..003, 005..008, 015); achterzijde-opnamen herhalen elementen (SOC-009..011). Mitigatie: geen optelling, kandidaten per foto, mens vergelijkt.
5. **Herhaalde gevelopbouw:** gelijkvormige woningen kunnen als herhaald worden aangezien terwijl het een ander object is; herhaling blijft inactief (multiplier null).
6. **Kleine platen:** 290/288 (MAP-002), 280 (MAP-009) en veel platen in MAP-003/004/005 zijn alleen bij vergroting leesbaar; een misread verschuift een koppeling naar een ander pand.
7. **Gedraaide of schuine opnamen:** vertekening maakt visibility (FULL/PARTIAL) en kozijngrenzen onzeker.
8. **Bronverwarring:** maldenhof_2 en maldenhof_3 zijn herencodeerde versies van MAP-002 en MAP-015; hashes verschillen. Annotaties blijven aan de bestaande bestanden hangen.

## 8. Voorstel voor de volgorde van de annotatiewerkzaamheden

1. Besluiten APP-001 en de plaatbesluiten (APP-002 t/m APP-010) door een mens.
2. Voorzijde met bewezen platen: MAP-003 en MAP-004 (panden 10 t/m 13), daarna MAP-013 en MAP-009; overlap met foto 2 en met elkaar eerst als kandidaat markeren.
3. MAP-008 en MAP-032 (pand 8), MAP-031 (pand 4); overlapbesluit SOC-006 eerst.
4. MAP-005 en MAP-029 pas na aanvullend bewijs (NEEDS_EVIDENCE).
5. Achterzijde/tuin pas na het besluit over de bewijsroute: MAP-014 en MAP-018, dan MAP-017, MAP-019, MAP-020, MAP-021. Annotatie van zichtbare observaties zonder pandkoppeling blijft mogelijk als een mens dat goedkeurt.
6. Elke annotatiestap levert REVIEW_REQUIRED-kandidaten op; instances ontstaan pas na afzonderlijke menselijke besluiten, zoals bij foto 2.

## 9. Checklist menselijke goedkeuring

- [ ] Plaatregel (APP-001) bevestigd
- [ ] Plaatlezingen en pandkoppelingen per foto gecontroleerd op het origineel
- [ ] Elk van de 15 overlapgroepen beoordeeld (SAME / DIFFERENT / UNDECIDABLE)
- [ ] Bewijsroute voor achter/tuin besloten en zijde per foto gekozen
- [ ] Beslissing over aanvullende foto's (panden 1, 5, 15; overzichten voor 2, 3, 9; achterzijden)
- [ ] Telregel, zichtbaarheidsregels en overlapzone met foto 2 bevestigd
- [ ] Rol van MAP-015 ten opzichte van maldenhof_3 bevestigd
- [ ] Volgorde van annotatie goedgekeurd
- [ ] Bevestigd: foto 2 blijft bevroren, geen instances, totalen, repeat of kosten in de volgende fase

## Niet gedaan in deze stap

Geen nieuwe of gewijzigde instances, objecttotalen, tellingen, besluiten, BAG-koppelingen, repeat multipliers, maten, painting area, KG/prijs/onderhoudskosten of App-wijzigingen. NOT_PROVEN is nergens omgezet in PROVEN. STOP: wachten op expliciete goedkeuring.
