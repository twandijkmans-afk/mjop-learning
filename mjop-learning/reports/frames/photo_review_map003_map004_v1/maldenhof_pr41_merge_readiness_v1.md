# Maldenhof PR #41 — merge-readinessrapport v1

Onafhankelijke eindcontrole van de branch van PR #41 tegen `origin/main` (merge-base af11a76, branch 10 commits voor, 0 achter). Er is niets gemerged en niets toegepast.

## A. Scopecontrole
- 69 bestanden: **64 nieuw, 5 gewijzigd, 0 verwijderd**.
- De 5 gewijzigde bestanden zijn uitsluitend: `scripts/doc012_generalization_review.py` (REPORT_ONLY_SCRIPTS uitgebreid met de nieuwe Maldenhof-scripts) en de vier regenereerbare audits (`vector_drawing_source_audit_v1.json/.md`, `doc012_generalization_review_v1.json/.md`; alleen toevoegingen/1 regel samenvatting).
- Geen enkel bevroren bestand (photo-2, instance-store, evidence, KG, quantity resolutions, BAG, building links, APP-goedkeuringsdocument) is gewijzigd.
- Nieuwe inhoud: 12 scripts, 5 testbestanden, `reports/frames/photo_review_map003_map004_v1/` (review-JSON/MD, 11 overzichtsbeelden, decision pack 9,2 MB, p1_quality_review, pilot_review, pilot_decisions).
- Geen tijdelijke debug-, log-, `.pyc`-, `.bak`- of scratchbestanden. Geen enkel script, pipeline-, app- of instancecode buiten de review-scripts leest de nieuwe bestanden (geen indirecte verwerkingsroute).

## B. Bewijsintegriteit
- Review-JSON en -MD en `visual_review_map003_map004_data.py` zijn bytegelijk aan de vastgelegde SHA256 (getest; opnieuw genereren geeft een schone `git status`).
- Alle 50 observaties: `is_instance=false`, `counts_in_any_total=false`, `bag_pand_id=null`, `pand_status=NOT_PROVEN`. Alle 43 relaties: `merged=false`, `confirmed=false`. `effects`: 0 instances, 0 BAG-links, totalen/hoeveelheden/kosten/multipliers null, photo-2 ongewijzigd, 48 APP open.
- Gevelsectierelaties (VR-001, VR-020) zijn klasse `SAME_FACADE_SECTION`; `same_physical_frame_proven` is overal false. Objectrelaties zijn kandidaat, nooit samengevoegd. Plaatnummer bewijst alleen de plaatmuur; geen koppeling op nabijheid; identieke woningen geven geen merge (tests en data).
- Begrippen in de repository: PHOTO_OBSERVATION = `OBS-*`; PHYSICAL_OBJECT_CANDIDATE = `POSSIBLY_SAME_PHYSICAL_FRAME`/`SAME_PHYSICAL_OBJECT_CANDIDATE`; FACADE_SECTION = `SAME_FACADE_SECTION`; HUMAN_DECISION = register/export; CONFIRMED_PHYSICAL_INSTANCE en BAG_BUILDING_LINK bestaan voor deze review niet (0).
- Reproduceerbaar: `build_visual_photo_review_map003_map004.py`, `build_human_visual_decision_pack.py` (incl. kwaliteitsreview en pilotrapport) en `register_pilot_decisions.py` opnieuw uitgevoerd: geen enkel verschil.

## C. Pilotregistratie
- `pilot_decisions/maldenhof_pilot_decision_register_v1.json` bevat exact de tien bevestigde besluiten; review-ID, keuze en `source_ref_hash` zijn gevalideerd tegen pack v1.2.0 (en tegen het bevestigde bestand, sha256 vastgelegd). Elke tabelrij uit de opdracht klopt.
- Herkomst: `HUMAN_CHAT_CONFIRMATION`, kanaal ChatGPT, `via_html_form=false`, `is_html_export=false`. Het register en het bevestigde bestand worden door de HTML-import afgewezen (getest); het register kan geen bronobservatie, APP-besluit, instance, merge, BAG-link, totaal of kosten veroorzaken (alle `never`-vlaggen false, geen consument).
- `SAME` bij VR-020 = `SAME_FACADE_SECTION`; bij VR-027 = `SAME_PHYSICAL_OBJECT_CANDIDATE`. MAP004-012 CONFIRM = alleen deels zichtbaar raam. HQ-VR-001 CONFIRM = regel, geen extra telling. 113 punten en 48 APP-besluiten OPEN.
- Het voorstel van Claude uit het pack staat per besluit apart (`claude_proposal_in_pack`); drie besluiten wijken daar bewust van af (VR-024, MAP004-012, HQ-VR-001).

## D. Testresultaten
- Volledige suite op de branch: **1462 passed, 1 skipped, 3 failed**.
- De 3 failed zijn de bekende Xpdf-fouten (`test_doc007_dekkend_actions_link_to_element`, `test_known_wrap_and_page_break_cases_on_batch1_sources`, `test_full_build_on_batch1_sources`). Op een schone checkout van `origin/main` falen exact dezelfde 3 (`pdftotext 24.02.0` aanwezig in plaats van Xpdf 4.06). Geen andere fout wordt erdoor verborgen.
- Scope guard: groen. Chromium-browsertests (formulier, import/export, pilotfilter, nieuwe injectietests): groen. Registertests: groen. 1 skipped = bestaande skip, niet van deze PR.

## E. Bevindingen
BLOCKER: 0. MAJOR: 0. MINOR: 2. INFORMATIONAL: 3.

- MINOR-1: het AI-adviesbestand (`maldenhof_pilot_ai_beoordeling.json`) staat niet in de repository; het register bewaart alleen het pack-voorstel en markeert afwijkingen. Herleidbaarheid van het advies zelf ontbreekt. Niet gecorrigeerd (zou nieuw bronmateriaal toevoegen); optioneel als apart bestand.
- MINOR-2: de browsertests vereisen Playwright en Chromium, die niet in `requirements-pipeline.txt` staan; zonder die tools worden ze overgeslagen. Gevolg: lokale/CI-run zonder Playwright toetst de HTML niet.
- INFO-1: OBS-MAP003-009 blijft UNDECIDABLE terwijl HQ-VR-001 (hetzelfde element) CONFIRM is. Geen tegenspraak: 009 gaat over wat MAP-003 zelf toont, HQ-VR-001 over de regel op basis van MAP-002/013 en foto 2.
- INFO-2: correctievoorstel CORR-OBS-MAP003-009-VIS-001 (FULL → PARTIAL) klopt met de bronbbox (783–842, grenst exact aan 010) en de definitie van FULL; bronobservatie is ongewijzigd; geen effect op totalen of photo-2 (FC-M2-006-A blijft FULL). Status PROPOSED_NOT_APPLIED; vereist afzonderlijke menselijke goedkeuring.
- INFO-3: de PR voegt ca. 15 MB beelden en een 9,2 MB HTML toe.

Security/integriteit HTML: import valideert het hele bestand voordat iets verandert; ongeldige of gemanipuleerde bestanden worden volledig afgewezen (onbekende en dubbele ID's, verkeerde versie/hash/type, `__proto__`/`constructor` als ID of sleutel, ongeldige keuze of bron, voorstel als menselijk besluit). Opmerkingen worden alleen als tekst of `value` gezet; geen `eval`, `document.write` of onveilige `innerHTML`. Een HTML-injectie in een opmerking voert niets uit. Er is geen automatische goedkeuring; een deelexport bewaart de andere punten.

## F. Eindadvies
**READY_WITH_NON_BLOCKING_NOTES**

Er zijn geen blokkades. Voor de merge zijn de twee MINOR-opmerkingen niet nodig. Het correctievoorstel op OBS-MAP003-009 en de formele relatie van de pilotbesluiten tot de 48 APP-besluiten blijven afzonderlijke menselijke besluiten.

Toegevoegd in deze controle: `tests/test_pr41_final_review.py` (3 regressietests).
