# Human Instance Decision Register v1

**Status: registerframework met een LEEG register. Er is geen menselijk besluit geregistreerd, geen instance (FI-*) aangemaakt en niets gemerged of geactiveerd.**

Doel: een veilig, append-only en controleerbaar register voor menselijke niveau-A-besluiten (fysieke objectidentiteit) over approval requests (IAR-*). Het hergebruikt `physical_instance_approval.py` (live opbouw, C1-C11, statusmachine, `verify_human_approval`) en bouwt geen tweede framework of instance-store.

## 0. Vier stappen die nooit automatisch samenvallen

1. **1_TECHNICALLY_VALID_REQUEST**: De aanvraag slaagt voor C1-C11 (READY_FOR_HUMAN_REVIEW). Geen oordeel over de identiteit.
2. **2_EXPLICIT_HUMAN_DECISION**: Een mens heeft apart en expliciet gekozen (invoerbestand/chatbericht). Dit is bewijs-op-gezag, geen verificatie.
3. **3_TECHNICALLY_VERIFIED_DECISION**: Het besluit is door `verify_human_approval` en de registerregels gecontroleerd en append-only vastgelegd.
4. **4_ACTIVATED_PHYSICAL_INSTANCE**: Bestaat niet in dit register of deze module; vereist een apart, later door de gebruiker geautoriseerd activatieproces.

## 1. Registerschema

Bestand: `data/instance_decisions/human_instance_decision_register_v1.jsonl` (JSON Lines, één canoniek record per regel, nu 0 records, kop = `0000000000000000…`). JSON Schema: `schemas/human_instance_decision.schema.json`. Het schema is gesloten (`additionalProperties: false`); onbekende velden, ook activatiecommando's, worden geweigerd.

| Veld | Betekenis |
|---|---|
| `approval_request_id` | IAR-id van de aanvraag |
| `request_hash` | exacte hash van de live aanvraag waarover besloten wordt |
| `candidate_group_id` | OIC-kandidaat |
| `decision` | APPROVE_PHYSICAL_IDENTITY, REJECT of NEEDS_MORE_EVIDENCE (anders geweigerd) |
| `covers_levels` | uitsluitend ["A"]; B (pand) en C (hoeveelheid/kosten) zijn uitgesloten |
| `decision_source` | HUMAN of HUMAN_CHAT_CONFIRMATION (bestaande menselijke herkomstwaarden) |
| `decided_by` | naam van de beslisser (geen AI-naam) |
| `decision_provenance` | kanaal, invoerwijze, bronbericht-verwijzing, letterlijke verklaring, identity_verification=NONE_SELF_ASSERTED, ai_authored_decision=false |
| `decision_timestamp` | ISO 8601 met tijdzone; niet in de toekomst |
| `acknowledged_open_app_ids` | erkende OPEN APP-vragen (verplicht: alle DIRECT-gerelateerde) |
| `acknowledged_open_relations` | erkende open relaties (verplicht: VR-045) |
| `evidence_reviewed` | verklaring dat observaties, foto's, relaties en MAP-009 zijn bekeken |
| `reviewer_notes` | vrije toelichting (zonder pand-ID of FI-ID) |
| `record_version` | 1 |
| `decision_id` | door het register toegekend (HID-0001, …) |
| `sequence` | volgnummer |
| `previous_record_hash` | hash van het vorige record (GENESIS = nullen) |
| `record_hash` | SHA-256 over het record zonder dit veld |
| `register_version` | human_instance_decision_register_v1 |

## 2. Registratieprocedure

1. Laad de actuele aanvraag (`build_request`) en bouw haar live opnieuw op. 2. `evaluate_request` (C1-C11) en alle bewijsreferenties opnieuw valideren. 3. `request_hash` exact vergelijken (ook tegen de vervangen hashes). 4. Het apart aangeleverde besluit controleren. 5. Gesloten schema toepassen. 6. Bestaande besluiten op duplicaten en conflicten controleren. 7. Alleen het besluit append-only toevoegen. 8. Resultaat rapporteren zonder iets anders te wijzigen.

| Status | Betekenis |
|---|---|
| `DRY_RUN` (standaard) | Alles gevalideerd, **niets geschreven**. |
| `VALIDATION_FAILED` | Minstens één voorwaarde faalt; niets geschreven; redenen genoemd. |
| `REGISTERED` | Alleen met `mode=REGISTER` **en** de bevestigingstoken; één record toegevoegd. |

Echte registratie vraagt een afzonderlijke handeling (`register --decision <bestand> --confirm REGISTER_ONE_HUMAN_DECISION_AS_EXPLICITLY_REQUESTED_BY_USER`). Er bestaat geen codepad dat zelf een besluit genereert, goedkeurt of een instance activeert.

## 3. Autorisatievoorwaarden

- De actuele aanvraag is live opnieuw opgebouwd en slaagt (READY_FOR_HUMAN_REVIEW).
- De `request_hash` komt exact overeen; een vervangen of gewijzigde hash faalt.
- Een expliciete keuze uit de drie toegestane besluiten.
- Herkomst: menselijke bron, niet-AI-beslisser, kanaal en invoerwijze benoemd, `ai_authored_decision=false`, letterlijke verklaring die aanvraag-id, request_hash en keuze noemt.
- Alleen niveau A (`covers_levels == ["A"]`).
- Alle DIRECT-gerelateerde OPEN APP-vragen (APP-012, APP-025) en de open relatie VR-045 zijn expliciet erkend; erkennen van iets dat niet OPEN is faalt.
- Het bewijs (observaties, foto's, relaties, MAP-009) is als bekeken verklaard.
- Geen conflicterend of dubbel besluit voor dezelfde request_hash.
- Het record voldoet aan het gesloten schema én `verify_human_approval` van het bestaande framework.

### Beperkingen van chatbevestiging als bewijs

- Chatbevestiging bewijst geen identiteit: er is geen cryptografische of andere onafhankelijke verificatie van de persoon. `identity_verification` staat daarom vast op NONE_SELF_ASSERTED.
- Het register legt vast WIE zegt WAT via WELK kanaal, met een letterlijke bronverklaring. Het kan niet uitsluiten dat iemand anders (of een AI) die verklaring plaatst.
- Een AI kan een menselijk bericht overnemen (AI_TRANSCRIPTION_OF_HUMAN_MESSAGE) maar nooit zelf een besluit nemen of een formulier invullen en dat als menselijke handeling voorstellen.
- Een AI-aanbeveling, een voorbeeldbestand of een ChatGPT- of Claude-antwoord is op zichzelf nooit een besluit.

## 4. Conflictafhandeling

- Hetzelfde besluit opnieuw aangeboden: `VALIDATION_FAILED` met `DUPLICAAT_BESLUIT`; niets geschreven.
- Ander besluit voor dezelfde request_hash: `CONFLICTEREND_BESLUIT`; nooit overschrijven. Nieuw bewijs betekent een nieuwe aanvraag-hash en dus een nieuwe beoordeling.
- Aanvraag gewijzigd na een besluit: het oude besluit blijft staan maar is `STALE_REQUEST_CHANGED` en geldt niet voor de nieuwe hash (`audit_register`).
- Gelijktijdige registratie: een exclusief lockbestand; wie het niet krijgt faalt gesloten (`REGISTER_VERGRENDELD`). Een achtergebleven slot wordt nooit automatisch opgeruimd.

## 5. Append-only gedrag

- Elk record bevat `previous_record_hash` en `record_hash` (SHA-256-keten, begin = nullen) en een volgnummer; het register is `HID-0001…` zonder gaten.
- Schrijven: oude bytes + één nieuwe regel naar een tijdelijk bestand in dezelfde map, `fsync`, `os.replace` (atomisch), map-`fsync`, daarna volledige nacontrole inclusief controle dat de oude bytes ongewijzigd voorop staan.
- Compare-and-swap onder het slot: is het register tussentijds veranderd, dan faalt de registratie.
- Een beschadigd, gedeeltelijk geschreven (geen regeleinde), niet-canoniek, gebroken-keten of ontbrekend registerbestand stopt alles (`REGISTER_BESCHADIGD`). Niets wordt gerepareerd of herschreven.
- Er is geen functie om een record te wijzigen of te verwijderen.

## 6. De voorbeeldaanvraag

`IAR-OIC-VR-027` (kandidaat `OIC-VR-027`, observaties OBS-MAP003-011, OBS-MAP004-006), status **READY_FOR_HUMAN_REVIEW**, technisch oordeel **SUITABLE_FOR_HUMAN_REVIEW**, live `request_hash` = `e276feeb5849ba8af4c41e2e429aca21` (vervangen: `aa556297be5d6713d298a06fa40492b8`, `34c61b5e5f274764e86491a838502ede`).
Open relaties: VR-045. Gerelateerde APP: APP-001 (INDIRECT, OPEN), APP-002 (INDIRECT, OPEN), APP-003 (INDIRECT, OPEN), APP-006 (INDIRECT, OPEN), APP-011 (INDIRECT, OPEN), APP-012 (DIRECT, OPEN), APP-013 (INDIRECT, OPEN), APP-018 (INDIRECT, OPEN), APP-025 (DIRECT, OPEN), APP-029 (INDIRECT, OPEN), APP-030 (INDIRECT, OPEN), APP-031 (INDIRECT, OPEN), APP-034 (INDIRECT, OPEN), APP-035 (INDIRECT, OPEN), APP-039 (INDIRECT, OPEN).

Het leesbare beslispakket met bewijsbeelden en een leeg invulsjabloon: `reports/frames/human_instance_decision_register_v1/IAR-OIC-VR-027_decision_pack.html` (sjabloon: `…_decision_input_TEMPLATE.json`, alle beslisvelden leeg, geen voorgeselecteerde optie).

## 7. Huidige status zonder besluit

| Stap | Stand |
|---|---|
| 1 technisch geldige aanvraag | ja |
| 2 expliciet menselijk besluit geregistreerd | nee |
| 3 technisch geverifieerd besluit | nee |
| 4 geactiveerde instance | nee (bestaat niet) |
| niveau A / B / C | NOT_DECIDED / NOT_DECIDED / NOT_DECIDED |

Het ingevulde-maar-lege sjabloon geeft in DRY_RUN `VALIDATION_FAILED` (verwacht: het sjabloon is geen besluit). APP-besluiten: 48 van 48 OPEN.

## 8. Verboden effecten

- `create_or_modify_frame_instance`
- `reserve_instance_id`
- `merge_observations`
- `link_bag_pand`
- `set_dimensions`
- `change_building_total`
- `change_unique_count`
- `set_quantity`
- `set_cost`
- `set_maintenance_action`
- `change_photo2_inventory`
- `change_app_decision`
- `change_pilot_decision`
- `change_source_observation`
- `activate_repeat_multiplier`
- `write_instance_store`
- `create_fi_id`
- `activate_instance`
- `write_register_without_confirmation`
- `overwrite_or_delete_registered_decision`
- `generate_decision_by_code`
- `treat_ai_recommendation_as_human_decision`

## 9. Testresultaten

- `tests/test_human_instance_decision_register.py`: 157 tests (registratievalidatie, gesloten schema, hash-integriteit, append-only, duplicaten/conflicten, onbetrouwbare herkomst, vervalste autorisatie, corrupte/gedeeltelijke registers, atomische writes, gelijktijdige registratie, niveau-A-isolatie, verboden activatie, bescherming van bestaande bestanden, deterministische generatie): alle geslaagd.
- Bestaande approval-, reconciliatie- en scope-guard-tests: geslaagd (samen 236 met de registertests).
- Volledige suite: alleen de 3 bekende Xpdf 4.06-downloadfouten (zelfde als op `main`): `test_doc007_dekkend_actions_link_to_element`, `test_known_wrap_and_page_break_cases_on_batch1_sources`, `test_full_build_on_batch1_sources`.
- Het enige aangepaste bestaande bewaker-test (`test_no_other_script_imports_or_drives_the_approval_framework`) is niet verzwakt: alleen de twee registerscripts zijn bij naam toegestaan en een apart registertest bewaakt dat geen ander script het register aanroept.

## 10. De exacte latere handeling om één echt besluit te registreren

1. De gebruiker levert zelf (of bevestigt in een apart bericht) één besluit over IAR-OIC-VR-027 met de actuele request_hash.
2. Een thread zet dat letterlijk in een invoerbestand (entered_by_kind AI_TRANSCRIPTION_OF_HUMAN_MESSAGE, bronbericht-ID en letterlijke tekst) of de gebruiker vult het zelf in.
3. Eerst `python scripts/human_instance_decision_register.py check --decision <bestand>` (DRY_RUN) en het resultaat tonen.
4. Pas na een tweede, expliciete opdracht van de gebruiker: `... register --decision <bestand> --confirm REGISTER_ONE_HUMAN_DECISION_AS_EXPLICITLY_REQUESTED_BY_USER` in een eigen PR.
5. Activatie van een instance blijft een nog later, apart door de gebruiker geautoriseerd proces.

**STOP.** Deze PR registreert geen besluit, maakt geen FI-id en activeert niets. Merge alleen met jouw expliciete opdracht.
