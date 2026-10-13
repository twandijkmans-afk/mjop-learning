# PR #42 — merge-readinessrapport v1 (Physical Object Identity Pilot)

Onafhankelijke eindcontrole van de branch van PR #42 tegen `origin/main` (c87a246, merge van PR #41; branch is 0 commits achter). Gecontroleerde code-SHA: `1d7efc7` (dit rapport volgt als laatste commit). Er is niets gemerged en geen instance geactiveerd.

## 1. Scope en gewijzigde bestanden
Ten opzichte van `main`: **9 nieuw, 5 gewijzigd, 0 verwijderd** (vóór dit rapport).
- Nieuw: `scripts/object_identity_pilot.py`, `scripts/object_identity_evidence_verification.py`, `tests/test_physical_object_identity_pilot.py`, `tests/test_object_identity_evidence_verification.py`, `reports/frames/physical_object_identity_pilot_v1.md/.json`, `reports/frames/physical_object_identity_evidence_verification_v1.md`, `reports/frames/physical_object_identity_evidence_v1/` (bewijs-JSON + vergelijkingsbeeld).
- Gewijzigd: `scripts/doc012_generalization_review.py` (REPORT_ONLY_SCRIPTS) en de vier regenereerbare audits.
- Niets in `data/`, `frame_inventory`, `photo_review_map003_map004_v1`, `photo_archive_audit_v1` of `pilot_decisions` is gewijzigd (0 treffers in de diff).

## 2. Bescherming van oorspronkelijke gegevens
- Foto-2-gegevens, instance-store, pilotbesluiten, APP-goedkeuringsdocument, review-JSON/MD en archiefaudit: **byte-ongewijzigd** (diff leeg; review-JSON sha256 `28cccaf2…` zoals vastgelegd; tests pinnen de hashes van instance-store, repeat-groups en foto-2-besluiten).
- Scope guard: 6 passed.
- Geen BAG-koppelingen, unieke totalen, hoeveelheden of kosten: `bag_pand_id=null`, `counts_in_any_total=false`, `quantity/cost=null` (getest op het OIC en alle 50 observaties).
- Deterministisch: pilot-, bewijs- en registerscripts opnieuw uitgevoerd geeft geen enkel verschil. Het bewijsrapport wordt uit zijn JSON gerenderd en een test bewijst dat beide overeenkomen.

## 3. Identiteits- en veiligheidsregels (opnieuw getest)
| Regel | Uitkomst |
|---|---|
| SAME_FACADE_SECTION (VR-020) is geen objectidentiteit | geweigerd, REJECTED |
| UNDECIDABLE (VR-024, VR-026) | geen verband, UNRESOLVED, ook niet bij hypothetisch SAME |
| Identieke buurwoningen op uiterlijk | zonder onderscheidend anker of met REPETITION_RISK/HIDDEN/TOO_DARK nooit SUPPORTED |
| Twee observaties in dezelfde foto | geweigerd (regel getest op de redencode, niet toevallig) |
| Niet-transitief A~B, B~C, A≁C | geen groep; groep van 3 alleen als elk paar direct ondersteund is |
| OIC is geen FI-instance | OIC bevat `frame_instance_id=null`; geen enkele overgang naar een instance bestaat; `OIC-` komt niet voor in `data/` |
| Overgangen naar instances, BAG, tellingen, kosten | geen |

## 4. Validatie MAP-009-bewijs
- `OBS-MAP003-011` en `OBS-MAP004-006` blijven de twee bronobservaties; MAP-009 staat alleen in het bewijsrecord, niet in het OIC (`photo_ids`/`source_hashes`) en er is geen MAP-009-observatie (getest). Drie aanzichten geven daarom geen dubbele telling.
- Status blijft `SUPPORTED_CANDIDATE` (record: `status_changed=false`, OIC-hash vastgelegd).
- Relatiesterkte uit de bron (MEDIUM) en kwaliteitsklasse (STRONG_VISUAL_SUPPORT) staan in aparte velden en zijn apart getest.
- Plaat 280 bewijst alleen de muur; er is geen BAG-koppeling.
- **Feature-match**: twee verschillende metingen worden nu expliciet gedocumenteerd (FM-QUALITY-REVIEW: 39 inliers uit 82 matches op de exacte observatie-uitsneden; FM-EVIDENCE-VERIFICATION: 29 inliers uit 61 matches op ruimere uitsneden incl. het smalle raam). Ze zijn niet uitwisselbaar en geen van beide is identiteitsbewijs. Dit was een documentatietekort; gerepareerd en getest.
- MAP-009 steunt op unieke, tijdelijke kenmerken (merktekens, gordijn met voorwerpen, folie met plakstrook) en is onafhankelijk in toestel en hoek, niet in tijd (zelfde dag).

## 5. De drie gerepareerde problemen — opnieuw geauditeerd
1. **Besluit zonder menselijke herkomst**: wordt genegeerd (herkomst moet `HUMAN`/`HUMAN_CHAT_CONFIRMATION` zijn, hash gevalideerd); verband blijft CANDIDATE, `decision_refs` leeg.
2. **Ongeldige keuze**: een keuze buiten de toegestane keuzes of niet-tekst telt nooit als SAME.
3. **Fotohash**: wordt tegen de review-JSON én het onafhankelijke archiefregister gecontroleerd; ontbrekende of afwijkende hash weigert.
4. **Relatietype**: Decision Pack en review-JSON moeten overeenkomen, anders weigering.

**Nieuw gevonden bij deze eindcontrole (gerepareerd, met regressietests die vóór de fix faalden):** de eerdere correcties dekten gedeeltelijk corrupte invoer niet volledig. Een fuzz van 600+ gevallen op alle velden van VR-027 liet zien dat de volgende invoer nog een ondersteund verband kon opleveren of een uitzondering gaf: lege of ontbrekende bewijsverwijzingen, een relatieklasse `DIFFERENT_FRAMES`/`UNDETERMINABLE`, een relatie of observatie met `merged`/`is_instance`/`counts_in_any_total`/`bag_pand_id` aangetast, en een beschadigd record dat een uitzondering gaf. Nu: vorm- en invariantcontrole van alle bronrecords, verplichte originele uitsnede per observatie met kloppende hash, en een veilige ingang die elke fout of beschadiging omzet in een weigering. Er ontstaat nooit een ondersteund verband uit ongeldige of tegenstrijdige invoer.

## 6. Testresultaten
- Nieuwe OIC-tests: 37 (pilot 29 + bewijs 8) groen, inclusief fuzz, regressie en determinisme.
- Scope guard: 6 passed.
- Volledige suite: **1499 passed, 1 skipped, 3 failed**.
- De 3 failed zijn de bekende Xpdf-fouten (`test_doc007_dekkend_actions_link_to_element`, `test_known_wrap_and_page_break_cases_on_batch1_sources`, `test_full_build_on_batch1_sources`); ze falen ook op `main` (pdftotext 24.02.0 in plaats van Xpdf 4.06). Geen nieuwe failures.

## 7. Bevindingen
- BLOCKER: 0.
- MAJOR: 1, **gerepareerd**: onvolledige fail-closed validatie bij corrupte of tegenstrijdige invoer (zie 5).
- MINOR: 2, gerepareerd of genoteerd: (a) 39 en 29 niet als aparte metingen gedocumenteerd (gerepareerd); (b) de bewijsscript heeft de originele zip nodig die niet in de repo staat (bewust; tests gebruiken de vastgelegde JSON).
- INFORMATIONAL: de browsertests van PR #41 vereisen Playwright; MAP-009 is hetzelfde-dag-bewijs.

## 8. Resterende onzekerheden
- Alle foto's zijn van dezelfde dag; de kenmerken zijn tijdelijk. Een foto van een andere dag zou het sterkst zijn.
- Identieke buurwoningen blijven een structureel risico; alleen de unieke combinatie draagt het bewijs.
- Het pand van het kozijn is niet bewezen.
- Het verschil tussen relatiesterkte MEDIUM en kwaliteitsklasse STRONG is niet menselijk beslist.
- Een instance-besluit bestaat niet en wordt niet voorgesteld.

## 9. Eindadvies
**READY_WITH_NON_BLOCKING_NOTES**

Geen blokkades; de MAJOR-bevinding is gerepareerd en getest. De PR voegt alleen een kandidaatmodel, bewijs, tests en rapporten toe; een definitieve instance, merge, BAG-koppeling, telling of kosten blijft afzonderlijke menselijke besluitvorming.
