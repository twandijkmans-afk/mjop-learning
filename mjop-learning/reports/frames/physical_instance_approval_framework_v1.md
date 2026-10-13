# Physical Instance Approval Framework v1

**Status: raamwerk plus één CONCEPTAANVRAAG. Er is geen menselijk instance-besluit genomen, geen instance aangemaakt en niets gemerged.** Een approval request (IAR-*) is geen fysieke instance (FI-*) en reserveert geen instance-id.

Centrale vraag: hoe voorkomen we dat een foutief of onvoldoende onderbouwd kandidaatverband als definitief kozijn in de MJOP-App terechtkomt? Antwoord: drie strikt gescheiden stappen die nooit automatisch in elkaar overgaan, fail-closed gecontroleerd, met een menselijk besluit als enige weg naar goedkeuring en een nog niet bestaand, apart geautoriseerd proces voor activatie.

## 1. Bestaande architectuur en wat ontbreekt

| Onderdeel | Bestaand | Hergebruikt |
|---|---|---|
| Instance-store | `data/frame_inventory/maldenhof_photo_frame_instances_v1.json` (bevroren): 12 actieve + 2 vervangen instances, allemaal `FI-M2-nnn` uit foto 2; id's worden per script (`build_frame_instance_activation.py`) toegekend | alleen lezen (conflictcontrole C9) |
| OIC-model | `scripts/object_identity_pilot.py`: OIC-VR-027 SUPPORTED_CANDIDATE, fail-closed `evaluate_relation` | live her-evaluatie (C2) |
| Menselijke besluiten | pilotregister (10 besluiten, herkomst ChatGPT-bevestiging) | C6 |
| APP-besluiten | 48 rijen, allemaal OPEN, in het goedkeuringsdocument | alleen lezen, C10 |
| Bewijs | P1-kwaliteitsreview, evidence-verificatie (MAP-009), archiefregister (SHA256) | C4, C7, fotobewijs |
| Scopebescherming | `tests/test_scope_guard.py` met bevroren manifest | ongewijzigd |

**Ontbrekend vóór deze PR:** een mechanisme voor menselijke *instance*-goedkeuring bestond niet (geen `approval_request`, geen statusmachine, geen besluit dat bij een exacte aanvraag hoort). Er was ook geen controle dat een observatie niet al aan een bestaande instance hangt of dat twee kandidaten niet dezelfde observaties claimen. Er is bewust géén tweede instance-store gemaakt en geen schrijfpad naar de bestaande.

## 2. Het approval-requestmodel

Velden: `approval_request_id`, `candidate_group_id`, `observation_ids`, `supporting_relation_ids`, `evidence_refs`, `source_hashes`, `candidate_status`, `proposed_instance_type`, `approval_status`, `human_decision`, `decision_provenance`, `unresolved_questions`, `validation_results`, `allowed_effects`, `forbidden_effects`, `decision_levels`, `evidence_reconciliation`, `request_hash`.

- `approval_request_id` = `IAR-<candidate_group_id>`; botst per constructie nooit met `FI-*`. `frame_instance_id` en `reserved_instance_id` zijn altijd `null`; een `FI-`-id ergens in de aanvraag blokkeert.
- `request_hash` bindt het besluit aan de exacte inhoud: wijzigt het bewijs, dan hoort een eerder besluit niet meer bij de aanvraag.
- Een aanvraag mag zelf geen status `APPROVED_FOR_ACTIVATION`, geen `human_decision` en geen inhoud voor niveau B of C dragen.

## 3. De drie besluitvormingsniveaus

| Niveau | Vraag | In deze PR |
|---|---|---|
| A | Fysieke objectidentiteit: tonen de observaties hetzelfde fysieke kozijn? | NOT_DECIDED (aanvraag gaat alleen over A) |
| B | Pandtoewijzing: bij welk gebouw of BAG-pand hoort het kozijn? | NOT_DECIDED, niet aangeroerd |
| C | Hoeveelheid, afmeting, onderhoudsactie en kosten van dat onderdeel. | NOT_DECIDED, niet aangeroerd |

Een goedkeuring op niveau A geeft nooit automatisch goedkeuring voor B (BAG-pand) of C (hoeveelheid, afmeting, onderhoud, kosten). Het menselijke besluitrecord moet precies `covers_levels = ["A"]` zeggen; elk besluit met pand-, hoeveelheid-, kosten- of afmetinginhoud wordt geweigerd.

## 4. Statusmachine

| Status | Betekenis | Toegestaan naar |
|---|---|---|
| `DRAFT` | Aanvraag opgesteld; nog niet technisch beoordeeld. | `READY_FOR_HUMAN_REVIEW`, `NEEDS_MORE_EVIDENCE`, `REJECTED` |
| `READY_FOR_HUMAN_REVIEW` | TECHNISCH GESCHIKT VOOR BEOORDELING. Zegt niets over de identiteit zelf en is geen goedkeuring. | `NEEDS_MORE_EVIDENCE`, `REJECTED`, `APPROVED_FOR_ACTIVATION` |
| `NEEDS_MORE_EVIDENCE` | Technisch niet geschikt: bewijs of menselijk besluit ontbreekt of is onvoldoende. Nieuw bewijs vraagt een nieuwe aanvraag-hash. | `DRAFT`, `REJECTED` |
| `APPROVED_FOR_ACTIVATION` | MENSELIJK GOEDGEKEURD voor fysieke identiteit (alleen niveau A). Alleen via een verifieerbaar menselijk besluit; maakt zelf geen instance. | `NEEDS_MORE_EVIDENCE`, `REJECTED` |
| `REJECTED` | Afgewezen (menselijk besluit) of geblokkeerd door de technische controle (conflict, vervalsing, beschadigde invoer). Eindstatus voor deze aanvraag-hash. | (eindstatus) |

- READY_FOR_HUMAN_REVIEW alleen via de technische validatie, nooit op verzoek.
- APPROVED_FOR_ACTIVATION alleen met een geregistreerd, verifieerbaar menselijk niveau-A-besluit dat de exacte request_hash noemt.
- Geen overgang leidt tot een instance; activatie bestaat in dit framework niet.
- REJECTED door validatie is geen menselijk besluit en is eindstatus voor die request_hash.

Onderscheid dat nooit automatisch overgaat: **technisch geschikt voor beoordeling** (`READY_FOR_HUMAN_REVIEW`) → **menselijk goedgekeurd voor fysieke identiteit** (`APPROVED_FOR_ACTIVATION`) → **geactiveerde instance** (bestaat in deze PR niet; er is geen code die `FI-*` aanmaakt of wijzigt).

## 5. Harde voorwaarden (technisch geschikt voor beoordeling)

- **C1** Het OIC-verband bestaat (OIC-register)
- **C2** Status SUPPORTED_CANDIDATE, live opnieuw bepaald
- **C3** Alle bronobservaties geldig
- **C4** Alle bronhashes komen overeen (review-bron, archiefregister, bewijsreferentie)
- **C5** Relatie is PHYSICAL_OBJECT met exact deze eindpunten
- **C6** Menselijk kandidaatbesluit SAME, menselijke herkomst, hash gevalideerd
- **C7** Onderscheidend bewijs: STRONG + anker, geen blokkade
- **C8** Geen genegeerd DIFFERENT/UNDECIDABLE; open gerelateerde relaties zichtbaar
- **C9** Geen conflict met instances, andere kandidaten of aanvragen
- **C10** Relatie met de 48 APP-besluiten expliciet onderzocht
- **C11** Bewijsverzoening VR-045/MAP-009 consistent met de aanvraag; VR-045 zonder menselijk besluit

Elke voorwaarde faalt gesloten: een fout, ontbrekend of tegenstrijdig gegeven geeft `NEEDS_MORE_EVIDENCE` of `REJECTED` (technische blokkade, geen menselijk besluit), nooit een gunstiger uitkomst. Een geldig SAME-pilotbesluit is een *kandidaat*-besluit en geen instance-goedkeuring.

## 6. Conceptaanvraag OIC-VR-027

- Aanvraag: `IAR-OIC-VR-027` (hash `34c61b5e5f274764e86491a838502ede`), status **`READY_FOR_HUMAN_REVIEW`**, technisch oordeel **SUITABLE_FOR_HUMAN_REVIEW**.
- Observaties: OBS-MAP003-011, OBS-MAP004-006 (foto's MAP-003, MAP-004); relatie VR-027; bronsterkte MEDIUM, kwaliteitsreview STRONG_VISUAL_SUPPORT.
- Voorgesteld type: EXTERIOR_FRAME, materiaal en subtype UNKNOWN (voorstel, niet besloten). Geen BAG-pand, geen hoeveelheid, geen kosten.

| Check | Resultaat | Soort | Detail |
|---|---|---|---|
| S0 Aanvraagstructuur en verboden velden | geslaagd | AUTO_VALIDATED_FACT | alle verplichte velden, geen FI-id, geen niveau B/C-inhoud, geen voorgesteld besluit |
| C1 Het OIC-verband bestaat | geslaagd | AUTO_VALIDATED_FACT | OIC-VR-027 staat in het pilotrapport |
| C2 OIC heeft status SUPPORTED_CANDIDATE | geslaagd | AUTO_VALIDATED_FACT | live status SUPPORTED_CANDIDATE (opnieuw bepaald uit de brondata) |
| C3a Aanvraag komt overeen met het live kandidaatverband | geslaagd | AUTO_VALIDATED_FACT | observaties, foto's, relaties, bronhashes, relatiesterkte en bewijsklasse identiek |
| C3 Alle bronobservaties zijn geldig | geslaagd | AUTO_VALIDATED_FACT | geldig, geen instance, telt nergens, geen pandkoppeling |
| C4 Alle bronhashes komen overeen (review-bron, onafhankelijk archiefregister, bewijsreferentie) | geslaagd | AUTO_VALIDATED_FACT | SHA256 identiek in alle drie de bronnen |
| C5 De onderliggende relatie is een geldige fysieke-objectrelatie met exact deze twee eindpunten | geslaagd | AUTO_VALIDATED_FACT | VR-relatie is PHYSICAL_OBJECT; gevelsectie-relaties (SAME_FACADE_SECTION) tellen niet |
| C6 Menselijk kandidaatbesluit (SAME) is geldig en herleidbaar | geslaagd | AUTO_VALIDATED_FACT | RV-REL-VR-027 = SAME, menselijke herkomst (ChatGPT conversation), source_ref_hash gevalideerd. Dit is een KANDIDAAT-besluit, geen instance-besluit. |
| C7 Visuele onderbouwing is onderscheidend (geen louter gelijkende buurwoningen) | geslaagd | AUTO_VALIDATED_FACT | STRONG_VISUAL_SUPPORT met anker ['UNIQUE_CONFIGURATION']; feature-match is slechts ondersteunend. Let op: alle onderbouwing is visueel; een niet-visueel anker (bv. leesbaar nummer bij dit raam) ontbreekt. |
| C8 Geen tegenstrijdige DIFFERENT- of UNDECIDABLE-besluiten genegeerd | geslaagd | AUTO_VALIDATED_FACT | geen menselijk DIFFERENT/UNDECIDABLE op relaties die deze observaties raken; 1 gerelateerde relatie(s) zonder besluit blijven zichtbaar open |
| C9 Geen conflict met bestaande instances, andere kandidaten of eerder goedgekeurde objectidentiteiten | geslaagd | AUTO_VALIDATED_FACT | instance-store: 12 actieve + 2 vervangen instances, alle foto 2 (maldenhof_2 = MAP-002); geen verwijzing naar deze observaties of foto's; SOC-001: foto-niveau overlap met bevroren foto ['MAP-002']; geen kozijn-niveau claim |
| C10 Relatie met de 48 APP-besluiten expliciet onderzocht | geslaagd | AUTO_VALIDATED_FACT | 15 gerelateerd; direct relevante fotoniveau-overlapvragen ['APP-012', 'APP-025'] (de rest indirect: plaat/pand niveau B, geschiktheid, telregel); alle blijven OPEN; geen wordt door deze aanvraag beantwoord of gewijzigd |
| C11 Bewijsverzoening (VR-045/MAP-009) consistent met de aanvraag | geslaagd | AUTO_VALIDATED_FACT | uitkomst COMPATIBLE_DIFFERENT_SCOPE (AI-uitleg, geen menselijk besluit); MAP-009 ADDITIONAL_EVIDENCE_NOT_RELIED_ON; VR-045 zonder menselijk besluit; aanvraag en record komen overeen |

### Fotobewijs (samenvatting)

- **MAP-009** (STERK_VISUEEL_ONAFHANKELIJK_TOESTEL_EN_HOEK): andere camera (P1000236, 3264x2448, datumstempel) en andere hoek dan de bronfoto's (iPhone IMG_8518/8520); dezelfde combinatie: merktekens links, gordijn + witte voorwerpen midden, folie rechts (de verticale plakstrook is alleen in MAP-003/004 zichtbaar en in MAP-009 niet verifieerbaar; zie reconciliatierapport); positie links boven de kap van de wand met plaat 280, zoals in MAP-003/004; buurramen en MAP-007 tonen rolgordijnen of open vleugels, niet deze combinatie
  - Beperking: zelfde dag (14-08-2026) en tijdelijke kenmerken: onafhankelijk in toestel/hoek, niet in tijd
  - Beperking: geen leesbaar huisnummer bij dit raam; plaat 280 bewijst alleen die muur, niet het pand van het kozijn
  - Beperking: schuin perspectief: feature-match onbruikbaar (8 inliers)
- Tegenvoorbeeld MAP-007 (zelfde raamtype, ander huis) en de buurramen laten zien dat vorm en indeling niet onderscheiden; feature-match is alleen ondersteunend (39 inliers op de observatie-uitsneden, 29 op ruimere uitsneden, buurramen tot 54 bij andere paren; via de schuine MAP-009 slechts 8).
- Zwakte van de verwisseling: Hoog voor alle kenmerken die op de hele rij voorkomen (indeling, kasten); gedekt door de unieke, tijdelijke combinatie die bij geen onderzocht buurraam voorkomt. Geen derde foto op dezelfde plek uit een andere sessie/dag.

### Open onzekerheden (blijven zichtbaar, niet omgezet in goedkeuring)

- Bewijst de visuele combinatie (stickers, merktekens, gordijn) het fysieke object, of staan er identieke woningen met dezelfde inrichting? Alleen een derde onafhankelijke foto of een unieke afwijking kan dat beslissen.
- Beide observaties liggen in dezelfde gevelreeks (SOC-002); die groep is een foto-niveau-kandidaat (confidence MEDIUM), geen bewijs voor het kozijn.
- Geen van beide observaties heeft een bewezen pand (pand_status NOT_PROVEN); een objectidentiteit zegt niets over het BAG-pand.
- De bronrelatie noemt sterkte MEDIUM, de kwaliteitsreview STRONG_VISUAL_SUPPORT; het verschil is niet menselijk opgelost.
- De pilot-SAME is bevestigd via ChatGPT, niet via het HTML-formulier; er is geen instance-besluit gegeven.
- De bronfoto's (MAP-003, MAP-004) en de aanvullende foto MAP-009 zijn van dezelfde dag (14-08-2026): onafhankelijk in toestel en hoek, niet in tijd.
- De onderscheidende kenmerken (merktekens, gordijn met voorwerpen, folie met plakstrook) zijn deels tijdelijk en bewijzen geen blijvende identiteit van het kozijn.
- De MAP-009-beoordeling (PR #42) en de P1-kwaliteitsreview van VR-045 zijn verzoend als COMPATIBLE_DIFFERENT_SCOPE (andere uitsnede en bewijsclaim); dat is een AI-uitleg en geen menselijk besluit, en VR-045 blijft zonder menselijk besluit.
- De plakstrook is in MAP-009 niet verifieerbaar; de PR #42-tekst die dat wel stelde is gecorrigeerd. MAP-009 blijft aanvullend en wordt niet als bewijs gebruikt voor de status van het OIC.
- Gerelateerde relatie VR-045 (zonder menselijk besluit) raakt deze observaties; Claude-voorstel UNDECIDABLE; kwaliteitsreview: onvoldoende bewijs: MAP-009 is sterk verkort: alleen het tweedelige kozijn is herkenbaar, het smalle raam ontbreekt; geen uniek kenmerk.
- APP-012 (Overlap SOC-002) is een open fotoniveau-vraag over dezelfde foto's; die is niet gelijk aan dit kozijnniveau-verband.
- APP-025 (Overlap SOC-015) is een open fotoniveau-vraag over dezelfde foto's; die is niet gelijk aan dit kozijnniveau-verband.

**Let op, tegenstrijdige beoordeling van MAP-009:** de aanvullende MAP-009-lezing uit PR #42 is een handmatige beoordeling door Claude. De bestaande P1-kwaliteitsreview van de open relatie VR-045 (zelfde kozijn, MAP-009 als referentie, andere uitsnede) noemt het bewijs daar onvoldoende en stelt UNDECIDABLE voor. Er is geen menselijk besluit over VR-045. Deze aanvraag steunt daarom niet op MAP-009; het blijft aanvullend en openstaand.

## 6b. Bewijsverzoening VR-045 en MAP-009

Uitkomst **COMPATIBLE_DIFFERENT_SCOPE** (AI-verklaring van het verschil; geen menselijk besluit en geen wijziging van VR-045 of de kwaliteitsreview.).

- De twee beoordelingen gaan over verschillende MAP-009-uitsneden en verschillende bewijsclaims. REF-MAP009-006 bevat alleen het tweedelige kozijn en sluit het smalle raam met folie, het meest onderscheidende kenmerk, buiten; VR-045 vergelijkt bovendien een groep (kozijn plus smal raam) met die enkele uitsnede.
- De P1-review heeft daarom terecht vastgesteld dat deze uitsnede en de feature-match (4 van 7) geen identiteit bewijzen. Mijn PR #42-beoordeling steunt op een ruimere uitsnede met het smalle raam en op een kenmerk-voor-kenmerk lezing. Beide uitspraken kunnen naast elkaar bestaan.
- Twee kanttekeningen: (1) de P1-bevinding 'geen uniek kenmerk' en 'smal raam ontbreekt' is juist voor de uitsnede maar niet voor de foto: het smalle raam staat in MAP-009, net buiten de uitsnede, en F1-F3 waren ook binnen de uitsnede zichtbaar. (2) Mijn PR #42-tekst noemde de plakstrook ook in MAP-009; dat is niet verifieerbaar en is hierbij teruggebracht.

| Kenmerk | Klasse | In VR-045-uitsnede |
|---|---|---|
| F1 Twee witte merktekens in het linkervak (rechtsboven en rechtsonder) | DIRECTLY_VISIBLE | ja |
| F2 Wit geplooid gordijn in het grote vak | DIRECTLY_VISIBLE | ja |
| F3 Vensterbankvoorwerpen: lichte doos plus klein puntig voorwerp | DIRECTLY_VISIBLE_LOW_RESOLUTION | ja |
| F4 Doorschijnende folie in het smalle raam rechts | DIRECTLY_VISIBLE | nee |
| F5 Verticale plakstrook langs de folie | NOT_VERIFIABLE | nee |
| F6 Positie: rechts van het tweedelige kozijn, onder de goot, boven donkere houten bekleding, bij de kaphoek rechtsonder | DIRECTLY_VISIBLE | nee |
| F7 Buurkozijnen: zelfde indeling maar rolgordijnkast en geen folie | DIRECTLY_VISIBLE | nee |

Volledig rapport: `reports/frames/physical_instance_evidence_reconciliation_v1.md`. De aanvraag steunt niet op MAP-009 (`ADDITIONAL_EVIDENCE_NOT_RELIED_ON`); VR-045 blijft zonder menselijk besluit. De eerder gepubliceerde request_hash `aa556297be5d6713d298a06fa40492b8` is verouderd (de aanvraag is inhoudelijk uitgebreid met de bewijsverzoening); er hangt aan die hash geen besluit.

## 7. Relatie met de 48 APP-besluiten

| APP | Onderwerp | Soort | Relevantie | Status |
|---|---|---|---|---|
| APP-001 | Plaatregel: een plaat bewijst alleen de muur | PLATE_RULE_LEVEL_B | INDIRECT | OPEN |
| APP-002 | Plaatlezing en pandkoppeling MAP-003 | PLATE_AND_PAND_LINK_LEVEL_B | INDIRECT | OPEN |
| APP-003 | Plaatlezing en pandkoppeling MAP-004 | PLATE_AND_PAND_LINK_LEVEL_B | INDIRECT | OPEN |
| APP-006 | Plaatlezing en pandkoppeling MAP-009 | PLATE_AND_PAND_LINK_LEVEL_B | INDIRECT | OPEN |
| APP-011 | Overlap SOC-001 | PHOTO_OVERLAP_QUESTION | INDIRECT | OPEN |
| APP-012 | Overlap SOC-002 | PHOTO_OVERLAP_QUESTION | DIRECT | OPEN |
| APP-013 | Overlap SOC-003 | PHOTO_OVERLAP_QUESTION | INDIRECT | OPEN |
| APP-018 | Overlap SOC-008 | PHOTO_OVERLAP_QUESTION | INDIRECT | OPEN |
| APP-025 | Overlap SOC-015 | PHOTO_OVERLAP_QUESTION | DIRECT | OPEN |
| APP-029 | Telregel en samengestelde kozijnen hergebruiken | COUNTING_RULE | INDIRECT | OPEN |
| APP-030 | Zichtbaarheid FULL/PARTIAL | COUNTING_RULE | INDIRECT | OPEN |
| APP-031 | Overlapzone met bevroren foto 2 | OTHER | INDIRECT | OPEN |
| APP-034 | Geschiktheid als annotatiebron MAP-003 | PHOTO_SUITABILITY | INDIRECT | OPEN |
| APP-035 | Geschiktheid als annotatiebron MAP-004 | PHOTO_SUITABILITY | INDIRECT | OPEN |
| APP-039 | Geschiktheid als annotatiebron MAP-009 | PHOTO_SUITABILITY | INDIRECT | OPEN |

Alle 48 blijven OPEN en ongewijzigd. De direct relevante fotoniveau-overlapvragen (APP-012 voor MAP-003/004/009 en APP-025 voor de schuine reeks) gaan over *foto's*, niet over dit kozijn; een instance-besluit moet ze daarom expliciet erkennen (laten openstaan of beantwoorden), maar beantwoordt ze niet. Pandkoppeling (APP-002/003/006) hoort bij niveau B en blijft buiten deze aanvraag.

## 8. Conflicten en dubbeltellingen

- Instance-store: geen verwijzing naar OBS-MAP003-011, OBS-MAP004-006 of OIC-VR-027; alle instances komen uit foto 2 (MAP-002). SOC-001 (MAP-002/MAP-003) is een foto-overlap rond plaat 288, geen claim op dit kozijn.
- Overlap tussen kandidaatgroepen: er is één OIC; twee kandidaten of aanvragen met overlappende observaties worden beide geblokkeerd.
- Geen foto-2-object, APP-besluit of pilotbesluit wordt geraakt (hash-gecontroleerd door de tests en de scope guard).
- Bewijs bestaat uit visuele lezing; een niet-visueel anker (bv. leesbaar nummer bij dit raam) ontbreekt. Dat is zichtbaar gemaakt, niet weggepoetst.

## 9. Verboden effecten (blijven verboden)

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

Technisch onmogelijk gemaakt in deze PR: er bestaat geen functie die de instance-store, het pilotregister, de APP-besluiten of de bronobservaties schrijft; `transition()` is een zuivere functie; `APPROVED_FOR_ACTIVATION` is alleen bereikbaar met een geregistreerd menselijk niveau-A-besluit dat de exacte `request_hash` noemt, en bestaat in deze PR niet als registerbestand.

## 10. Wat is wat

- **AUTO_VALIDATED_FACT**: Door deze code opnieuw uit de brondata gecontroleerd (C1-C10).
- **MANUAL_VISUAL_ASSESSMENT**: Handmatige lezing van foto's door Claude (fotobewijs, MAP-009, tegenvoorbeelden); geen menselijk besluit.
- **HUMAN_DECISION_NOT_YET_TAKEN**: Instance-besluit niveau A; niveau B en C; APP-012; RV-REL-VR-045.

## 11. Nog vereiste menselijke beslissingen

Voor goedkeuring van de fysieke identiteit (alleen niveau A):
1. Het besluit `APPROVE_PHYSICAL_IDENTITY`, `REJECT` of `NEEDS_MORE_EVIDENCE` over de vraag: *tonen OBS-MAP003-011 en OBS-MAP004-006 hetzelfde fysieke kozijn?* (expliciet, met de request_hash, buiten het chat-pilotbesluit en niet door Claude in te vullen).
2. Erkenning (laten openstaan of beantwoorden) van de direct relevante APP-overlapvragen en van VR-045.
3. Daarna, apart en later: B (pand) en C (hoeveelheid/kosten), elk met een eigen besluit.

## 12. Voorstel voor een latere gecontroleerde activatiefase (niet gebouwd)

1. Een apart register van instance-besluiten (append-only, eigen PR) met het besluit APPROVE_PHYSICAL_IDENTITY, de request_hash en erkenning van de APP-overlapvragen.
2. Een afzonderlijk, door jou geautoriseerd activatieproces dat alleen een verifieerbaar APPROVED_FOR_ACTIVATION leest, een nieuw FI-id uit de bestaande nummering toekent, de hele instance-store en scope guard opnieuw valideert en dubbele koppeling uitsluit.
3. Activatie raakt alleen niveau A. Pandkoppeling (B) en hoeveelheid/kosten (C) vragen elk een eigen, later besluit.
4. Dry-run met diff-rapport vóór elke schrijfactie; terugdraaien via de bestaande append-only store.

## 13. Effecten van deze PR

```json
{
  "instances_created": 0,
  "instance_ids_reserved": 0,
  "instance_store_written": false,
  "bag_links_created": 0,
  "merges": 0,
  "building_totals": null,
  "quantities": null,
  "costs": null,
  "human_decisions_created": 0,
  "human_decisions_changed": 0,
  "app_decisions_changed": 0,
  "pilot_decisions_changed": 0,
  "source_observations_changed": 0,
  "photo2_changed": false,
  "approved_requests": 0
}
```

Reviewpakket: `reports/frames/physical_instance_approval_v1/IAR-OIC-VR-027_review_pack.html` (statisch, zelfstandig, zonder formulier).

**STOP.** Stop vóór een menselijk instance-goedkeuringsbesluit, iedere definitieve instance-activatie en het mergen van PR #43.
