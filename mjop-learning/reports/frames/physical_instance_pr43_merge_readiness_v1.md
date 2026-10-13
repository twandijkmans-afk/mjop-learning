# PR #43 Merge-readinessrapport v1

Onafhankelijke technische eindcontrole van PR #43 (Physical Instance Approval Framework v1 plus bewijsverzoening VR-045/MAP-009).
**Er is niets gemerged, geen menselijk instance-besluit geregistreerd en geen instance geactiveerd.**

**Eindadvies: `READY_WITH_NON_BLOCKING_NOTES`.** Merge is technisch veilig na jouw expliciete toestemming. Een menselijk niveau-A-besluit en iedere activatie blijven buiten deze PR.

Gecontroleerd: branch `claude/maldenhof-frame-instance-activation-v1-dno7ma`, basis `origin/main` = 9478194 (merge PR #42), merge-base gelijk aan main (0 commits achter). De head-SHA staat in het eindbericht; dit rapport zelf is de laatste commit (het rapport kan zijn eigen SHA niet bevatten).

## 1. Volledige scope en gewijzigde bestanden

17 bestanden tegen `origin/main` (14 nieuw, 3 aangepast), 0 bestanden verwijderd.

| Soort | Bestand | Status |
|---|---|---|
| Code | `scripts/physical_instance_approval.py` | nieuw: framework, validatie C1-C11, statusmachine |
| Code | `scripts/physical_instance_approval_report.py` | nieuw: alleen weergave (md en statische html) |
| Code | `scripts/physical_instance_evidence_reconciliation.py` | nieuw: handmatig (zip nodig), schrijft alleen eigen uitvoer |
| Code | `scripts/doc012_generalization_review.py` | aangepast: drie nieuwe scripts in `REPORT_ONLY_SCRIPTS` |
| Tests | `tests/test_physical_instance_approval.py` (49), `tests/test_physical_instance_evidence_reconciliation.py` (24) | nieuw |
| Rapporten | `reports/frames/physical_instance_approval_framework_v1.md/.json` | nieuw |
| Rapporten | `reports/frames/physical_instance_evidence_reconciliation_v1.md` en `physical_instance_approval_v1/physical_instance_evidence_reconciliation_v1.json` | nieuw |
| Pakket | `physical_instance_approval_v1/IAR-OIC-VR-027_review_pack.html`, `RC-crop_scope.jpg`, `RC-feature_comparison.jpg` | nieuw |
| Audits | `reports/quantity/doc012_generalization_review_v1.*`, `reports/drawing/vector_drawing_source_audit_v1.*` | regeneratie (lijsten van bestanden/scripts) |
| Dit rapport | `physical_instance_pr43_merge_readiness_v1.md` | nieuw |

Er is geen bestand in `data/`, geen bestaand rapport en geen bestaand script inhoudelijk gewijzigd. Geen ander script importeert of start het framework (test `test_no_other_script_imports_or_drives_the_approval_framework`).

## 2. Bron- en instancebescherming

- `git diff origin/main...HEAD` raakt geen pad in `data/` (instance-store, foto 2, photo_evidence, BAG-snapshots, building links, quantity resolutions), `photo_review_map003_map004_v1/` (waaronder het pilotregister, review-JSON en P1-review met VR-045), `photo_archive_audit_v1/` (waaronder de 48 APP-besluiten) of de PR #42-rapporten: leeg. Dat is byte-identiek aan main.
- Zeven sleutelbestanden staan bovendien met SHA256 vastgepind in een test (VR-045-review-JSON, kwaliteitsreview, feature-match-JSON, QREL-sheet-4, pilot-OIC-JSON, PR #42-bewijsrapport, pilotregister).
- Scope guard: 6 passed; `allowed_additions` is leeg gebleven (alle nieuwe bestanden staan buiten de bevroren mappen).
- Nieuwe FI-ID's: **geen gereserveerd of aangemaakt.** De `FI-`-tekens in de diff zijn uitsluitend (a) `FI-M2-001`/`FI-M2-nnn` als verwijzing naar bestaande instances in documentatie en (b) synthetische `FI-M2-099`/`FI-M3-001`/`FI-M3-777` in negatieve tests. De aanvraag zelf bevat geen `FI-`-id (`frame_instance_id`, `reserved_instance_id` zijn `null`; een FI-id ergens in de aanvraag blokkeert).
- Schrijfpaden: `physical_instance_approval.py` schrijft drie eigen uitvoerbestanden; `transition()` en `verify_human_approval()` zijn zuivere functies. Het reconciliatiescript schrijft alleen zijn JSON, md en twee beelden (bronscan in test).
- BAG-koppelingen, totalen, hoeveelheden en kosten: niet aangeraakt; de aanvraag weigert elk niveau-B/C-veld (pand, hoeveelheid, kosten, afmetingen, m², totalen).

## 3. Resultaten C1-C11 voor `IAR-OIC-VR-027`

| Check | Eis | Resultaat |
|---|---|---|
| S0 | structuur, geen FI-id, geen niveau-B/C-inhoud, geen voorgesteld besluit, hash klopt | PASS |
| C1 | OIC bestaat in het register | PASS |
| C2 | status SUPPORTED_CANDIDATE, **live opnieuw bepaald** (register en live moeten gelijk zijn) | PASS |
| C3a | alle bewijsclaims gelijk aan een vers uit de brondata opgebouwde aanvraag | PASS |
| C3 | bronobservaties geldig | PASS |
| C4 | bronhashes gelijk in review-bron, archiefregister en bewijsreferentie | PASS |
| C5 | PHYSICAL_OBJECT-relatie met exact deze eindpunten (geen gevelsectie) | PASS |
| C6 | menselijk SAME (herkomst `HUMAN_CHAT_CONFIRMATION`, hash gevalideerd), als kandidaatbesluit | PASS |
| C7 | STRONG plus onderscheidend anker, geen blokkade; feature-match alleen ondersteunend | PASS |
| C8 | geen genegeerd DIFFERENT/UNDECIDABLE; open gerelateerde relatie VR-045 blijft zichtbaar | PASS |
| C9 | geen conflict met 12 actieve + 2 vervangen instances, andere OIC's of aanvragen | PASS |
| C10 | 48 APP-rijen onderzocht; APP-012 en APP-025 direct relevant, allemaal OPEN | PASS |
| C11 | bewijsverzoening consistent met de aanvraag; VR-045 zonder menselijk besluit | PASS |

Technisch oordeel: `SUITABLE_FOR_HUMAN_REVIEW`, status `READY_FOR_HUMAN_REVIEW` (technisch geschikt voor beoordeling, niet goedgekeurd).

**Fail-closed:** ontbrekende, corrupte of tegenstrijdige invoer geeft nooit meer dan `NEEDS_MORE_EVIDENCE`/`REJECTED` (fuzz over alle verplichte velden, 15 junkwaarden, 200 corrupte contexten; elke uitzondering wordt een BLOCK). **Statusmachine en code komen exact overeen:** een test loopt alle 25 (huidige status, doelstatus)-paren door; alleen toegestane overgangen slagen, `APPROVED_FOR_ACTIVATION` is uitsluitend bereikbaar vanuit `READY_FOR_HUMAN_REVIEW` met een geregistreerd menselijk record, `REJECTED` is eindstatus.

## 4. Correctheid van de bewijsverzoening (VR-045 en MAP-009)

- **`COMPATIBLE_DIFFERENT_SCOPE` is onderbouwd** met exacte bronnen: de VR-045-uitsnede REF-MAP009-006 = MAP-009 [362,362,747,682] (test vergelijkt met de review-JSON) bevat alleen het tweedelige kozijn; de PR #42-uitsnede [300,300,1050,800] bevat het smalle raam [800,500,960,760] volledig, de VR-045-uitsnede niet (geometrietest). Daarnaast verschilt de claim (groep tegen referentie, LOW, tegenover aanvullend bewijs bij het paar van VR-027) en de methode van feature-match (P1: CLAHE, 360 px, 4 van 7; hier en in PR #42: andere uitsneden, 5 tot 35).
- **VR-045 en de kwaliteitsreview zijn niet overschreven** (SHA256 identiek aan main; record meldt `vr045_modified: false`).
- **Plakstrook:** `F5` staat vast als `NOT_VERIFIABLE`; de aanvraag toont de gecorrigeerde claim; het PR #42-rapport is bewust onaangetast gelaten.
- **Feature-match-inliers** worden nergens als poort of identiteitsbewijs gebruikt: een bronscan weigert `inliers` in een voorwaarde; alleen-feature-match zonder anker laat het OIC zakken (test).
- **MAP-009** is `ADDITIONAL_EVIDENCE_NOT_RELIED_ON`, geen observatie en geen instance; de OIC hangt er niet van af.
- **MEDIUM (bronrelatie) en STRONG (kwaliteitsklasse)** staan in afzonderlijke velden en blijven gelijk aan de bronnen.
- **Beperkingen blijven zichtbaar**: zelfde dag, tijdelijke kenmerken, identieke buurwoningen, pand onbewezen, geen instance-besluit, VR-045 en APP-012/025 open.
- **Reviewpakket (statische html)** komt overeen met aanvraag en rapport: een test controleert hash, uitkomst, alle onzekerheden, alle kenmerkklassen, de gecorrigeerde argumenten en de verouderde hashes in de html; geen formulier, script of invoerveld; alles ge-escaped.
- Een beperking van de verzoening zelf: de uitkomst is mijn uitleg (handmatige lezing van de originele pixels, SHA256 gecontroleerd), geen menselijk besluit.

## 5. Actuele aanvraaghash

- Actueel: `e276feeb5849ba8af4c41e2e429aca21` (in het json-rapport, het md-rapport en het reviewpakket).
- Verouderd en als zodanig in de aanvraag opgenomen: `aa556297be5d6713d298a06fa40492b8` (de gevraagde oude hash) en `34c61b5e5f274764e86491a838502ede` (de hash uit het vorige tussenbericht). Een aanvraag die zijn eigen hash als verouderd opvoert, of een andere lijst, wordt geblokkeerd; een besluit op een verouderde hash wordt geweigerd (test).
- De hash is deterministisch (canonieke JSON, sha256, 32 tekens) en gebonden aan: id, kandidaat, observaties, foto's, relaties, bronhashes, status, voorgesteld type, bewijsverwijzingen, besluitniveaus, onzekerheden, bewijsverzoening (inclusief de sha256 van het reconciliatierecord), aanvullend bewijs en besluitherkomst. Elke wijziging van zo'n veld maakt de aanvraag ongeldig, óók wanneer de hash opnieuw wordt berekend, omdat de claims daarna nog tegen een verse live opbouw worden vergeleken.
- De hash is nooit een goedkeuring: zonder geregistreerd menselijk record blijft het `human_decision: null`. Er bestaat geen niveau-A-instancebesluit en geen register ervan (`human_approvals` is leeg).

## 6. APP- en VR-045-statussen

- 48 APP-besluiten: allemaal **OPEN**, ongewijzigd (tabel gelezen, document byte-identiek). Direct relevant: APP-012 (SOC-002: MAP-003/004/009) en APP-025 (SOC-015). Het instance-besluit moet beide **expliciet erkennen** (laten openstaan mag); de verificatie weigert een record zonder die erkenning.
- VR-045: **geen menselijk besluit** (niet in het pilotregister met 10 besluiten); Claude-voorstel UNDECIDABLE, kwaliteitsklasse INSUFFICIENT_EVIDENCE. Een record moet ook VR-045 erkennen (`acknowledged_open_relations`). Komt er later toch een besluit over VR-045, dan wordt de aanvraag `NEEDS_MORE_EVIDENCE` (verouderd) en moet opnieuw worden opgesteld.
- Niveau-isolatie: een toekomstig niveau-A-besluit moet exact `covers_levels = ["A"]` zijn; extra velden zoals pand, hoeveelheid, kosten of een activatievlag worden geweigerd (gesloten schema). Niveau B (pand) en C (hoeveelheid/kosten) blijven `NOT_DECIDED` in de aanvraag en in het resultaat van een goedgekeurde overgang (test).

## 7. Testresultaten

| Onderdeel | Resultaat |
|---|---|
| Approval-framework (49 tests, o.a. 15 gevraagde negatieve scenario's, fuzz, statusmachine-pairs) | 49 passed |
| Reconciliatie (24 tests) | 24 passed |
| Bestaande OIC/pilot/register/scope guard (`test_physical_object_identity_pilot`, `test_object_identity_evidence_verification`, `test_pilot_decision_register`, `test_scope_guard`) | 64 passed |
| Deterministische regeneratie (json, md en html uit dezelfde bron; beschermde bestanden ongewijzigd) | passed |
| **Volledige suite** | **1572 passed, 1 skipped, 3 failed** |

De drie fouten zijn dezelfde Xpdf 4.06-downloadfouten die ook op ongewijzigde `main` falen (de sandbox blokkeert dl.xpdfreader.com): `test_deterministic_extraction.py::test_doc007_dekkend_actions_link_to_element`, `test_price_observations.py::test_known_wrap_and_page_break_cases_on_batch1_sources`, `::test_full_build_on_batch1_sources`. Xpdf-versie, downloadfallback en tests zijn niet gewijzigd.

## 8. Bevindingen

Alle bevindingen zijn in deze eindcontrole gevonden en gerepareerd met regressietests die vóór de fix faalden; er is geen openstaande BLOCKER of MAJOR.

| Ernst | Bevinding | Status |
|---|---|---|
| BLOCKER | geen | n.v.t. |
| MAJOR | Alleen een deel van de bewijsclaims zat in de hash en alleen de hashes van bronnen werden tegen de live brondata gecontroleerd. `additional_evidence` en `decision_provenance` zaten niet in de hash; `proposed_instance_type` en `evidence_refs` waren alleen via de hash beschermd, dus een met opnieuw berekende hash geknutselde aanvraag (ander type, andere regio, extra bewijsclaim) had READY kunnen blijven. | **Gerepareerd:** alle claims worden vergeleken met een vers opgebouwde aanvraag (C3a), twee velden in de hash opgenomen. Gevolg: nieuwe hash; `34c61b5e…` ook verouderd. |
| MINOR | Het menselijke besluitrecord had een open schema (extra velden zoals een activatievlag werden niet geweigerd). | Gerepareerd: gesloten schema. |
| MINOR | Erkenning van de open relatie VR-045 werd niet afgedwongen in het besluitrecord (alleen APP-012/025). | Gerepareerd: `acknowledged_open_relations` verplicht. |
| MINOR | `verify_human_approval` vertrouwde een door de aanroeper meegegeven validatieresultaat. | Gerepareerd: beoordeelt de aanvraag zelf opnieuw en eist READY. |
| MINOR | De FI-id-controle sloeg het veld `request_note` over. | Gerepareerd: volledige aanvraag gescand. |
| MINOR | De vensterbank-uitsnede (F3) reikte onder de VR-045-uitsnede uit, waardoor "in VR-045-uitsnede: ja" niet strikt klopte. | Gerepareerd: uitsnede verkleind, beeld opnieuw gemaakt en gecontroleerd, geometrietest. |
| MINOR | Een testje voor byte-identiteit was leeg te laten slagen (git-foutcodes). | Vervangen door vastgepinde SHA256-waarden. |
| INFORMATIONAL | Het besluitenregister voor instance-besluiten bestaat bewust niet; `transition()` is alleen een functie en wordt nergens aangeroepen met een echt record. | Beoogd. |
| INFORMATIONAL | `READY_FOR_HUMAN_REVIEW` in het json-rapport is een momentopname op deze brondata; de status wordt bij elke aanroep opnieuw bepaald. | Beoogd. |
| INFORMATIONAL | De drie bekende Xpdf-fouten. | Omgevingsprobleem, ook op main. |

## 9. Resterende risico's

1. **Bewijs is volledig visueel en deels tijdelijk** (zelfde dag, merktekens, gordijn, folie); alleen een derde foto uit een andere sessie of dag, of een unieke blijvende afwijking, beslist de verwisseling met identieke buurwoningen echt.
2. **MAP-009- en verzoeningsuitkomst zijn handmatige lezing door Claude**, niet door een mens bevestigd; VR-045 en APP-012/025 blijven open tot jij beslist.
3. **C10 leest de APP-tabel uit het goedkeuringsdocument en eist exact 48 rijen.** Wijzigt het tabelformaat, dan faalt de controle gesloten (geen onverwacht groen).
4. **Het latere activatieproces en het besluitenregister zijn alleen voorgesteld.** Pas daar ontstaat een schrijfpad naar de instance-store; dat vraagt een eigen PR, eigen tests en jouw expliciete autorisatie.
5. De koppeling tussen de foto-bestandsnamen in de instance-store en de archief-id's (`maldenhof_2` = MAP-002, `maldenhof_3` = MAP-015) is vastgelegd in een kleine vaste tabel; een derde bron zou die moeten uitbreiden.

## 10. Eindadvies

**`READY_WITH_NON_BLOCKING_NOTES`.** PR #43 raakt geen bevroren data, maakt geen instance of FI-id, registreert geen besluit en voert niets uit buiten eigen rapporten. De enige route naar `APPROVED_FOR_ACTIVATION` loopt via een geregistreerd, menselijk, niveau-A-besluit met de exacte `request_hash`, erkenning van APP-012, APP-025 en VR-045, en blijft zelf geen instance. De resterende punten zijn beperkingen van het bewijs en bewust uitgestelde vervolgstappen, geen defecten in deze PR.

**STOP.** Geen merge, geen menselijk instance-goedkeuringsbesluit en geen instance-activatie zonder jouw afzonderlijke, expliciete opdracht.
