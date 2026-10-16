# MJOP Photo Reviewer — offline Proof of Concept v1

Status: **PoC, volledig offline**. Er is geen externe visionaanroep gedaan, geen echte foto gelezen en niets aan canonieke data, menselijke
besluiten, instances of de MJOP-App gewijzigd. Ontwerp: fase-0-rapport (goedgekeurd); dit document beschrijft alleen wat in deze PR is gebouwd.

## Wat het doet

Foto → **voorstellen** (`PROPOSED`) → verifier → apart hoeveelhedencontract → reviewpagina. Een voorstel is een waarneming op niveau 1 uit het
bestaande vier-niveausmodel (waarneming → kandidaat → instance → pandkoppeling). Dit pakket maakt nooit een `FI-*`-instance, nooit een pandkoppeling,
nooit een besluit en nooit een koppeling aan kengetallen of prijzen.

| Onderdeel | Bestand |
|---|---|
| Voorstelcontract (strikt, draft-07) | `schemas/photo_proposal_set.schema.json` |
| Hoeveelhedencontract (apart, naast de observaties) | `schemas/photo_quantity_state.schema.json`, invoer: `schemas/photo_dimension_input.schema.json` |
| Toestemmings- en privacyrecord | `schemas/photo_consent_record.schema.json`, `agent/photo/consent.py` |
| Verifier | `agent/photo/verifier.py` |
| Vision-interface: `ReplayProvider`, `HumanImportProvider`, `NullProvider`, `ClaudeVisionProvider` (standaard uit) | `agent/photo/providers.py` |
| Deterministische bruto-oppervlaktemodule | `agent/photo/quantity.py` |
| Evaluatie (precisie, recall, telfout) | `agent/photo/evaluate.py` |
| Synthetische testgevel | `agent/photo/synthetic.py`, `tests/fixtures/photo_reviewer/` |
| HTML-reviewpagina (lokaal, zelfstandig) | `agent/photo/review_page.py` |
| CLI (schrijft alleen buiten de repository) | `scripts/photo_reviewer_demo.py` |
| Tests | `tests/photo_reviewer/`, CI: `.github/workflows/photo-reviewer-tests.yml` |

`agent/photo/` volgt het patroon van `agent/` (PR #44): eigen `contract.py`, schema-validatie, geen padinvoer van buiten, alleen-lezen (statisch bewaakt),
geen netwerk in de tests. De bestaande agent-tests bewaken alleen het kengetallenpakket (`agent/photo/` is daar uitgezonderd, één regel in
`tests/agent_tools/test_agent_tool_readonly.py`).

## Voorstelcontract (`photo_proposal_set_v1`)

Per foto één set: `photo` (`photo_id`, `source_sha256` van het ongewijzigde origineel, `derivative_sha256` van de geanalyseerde kopie, afmetingen,
transformaties), `provider` (adapter, versie, `response_sha256`, `consent_ref`), `policy` (`PHOTO_VISIBLE_ONLY`, `is_building_total=false`),
`proposals[]` en `hidden_element_hypotheses[]`. Per voorstel: `observation_id` (`PO-nnn`), `element_type`, `bbox_norm` (`[x1,y1,x2,y2]`, 0..1, zelfde
conventie als `maldenhof_2_frame_annotation_v1`), `visibility` (`FULL` / `PARTIAL` / `OCCLUDED`), `visible_quantity` (altijd 1), `uncertainties[]`,
`observation`, en de vaste invarianten `review_status=PROPOSED`, `human_decision=null`, `is_instance=false`, `counts_in_any_total=false`,
`bag_pand_id=null`. Typen: de bestaande observatietypen (`WINDOW_OPENING`, `EXTERIOR_DOOR`, `ROOF_WINDOW`, `DORMER_OPENING`, `UNKNOWN_OPENING`) plus
`BALCONY_DOOR`, `BALCONY_STRUCTURE`, `BALCONY_RAILING` (uitbreiding uit het fase-0-rapport; of balkon een eigen componenttype krijgt is nog een
vocabulairebeslissing). Alleen `WINDOW_OPENING`, `EXTERIOR_DOOR`, `BALCONY_DOOR` tellen mee in kozijnaantallen; dakramen en dakkapellen zijn context
(bestaande telregel).

**Telsemantiek.** Een fysieke kozijnopening is één opening, ook met meerdere vaste of draaiende delen: `visible_quantity` is vast 1 en het aantal delen staat
informatief in `parts_visible`. De verifier wijst af: `visible_quantity ≠ 1`, dubbele observaties (zelfde type, IoU ≥ 0,85) en een vak dat (bijna) volledig
binnen een ander vak van hetzelfde telbare type ligt (waarschijnlijk een los geteld vleugeldeel).

### Wat de verifier afwijst (fail-closed)

Ongeldige hashes (formaat; hash ≠ afbeelding; `source_sha256` ≠ fotoregister), gewijzigde inhoud (content-addressed `set_id`), ongeldige of te kleine bbox
en coördinaten buiten 0..1, dubbele `observation_id`/vakken, onbekende typen, `PARTIAL`/`OCCLUDED` zonder onzekerheid, verboden beslissingen
(`human_decision`, `review_status ≠ PROPOSED`, `is_instance`, `counts_in_any_total`, `bag_pand_id`), verboden velden (instance-id, kosten, oppervlak, maten) en
verboden claims in vrije tekst (FI-id, "goedgekeurd", kosten, m², NEN 2767, "vastgesteld", gebreken). Materiaal, conditie en gebreken bestaan niet in dit schema
(fase 1 = alleen openingen, deuren, balkons). Verborgen elementen staan alleen als hypothese (`hypothesis_only`, geen aantal, tellen nergens).

## Vision-interface

* `ReplayProvider` — speelt opgeslagen antwoorden terug (sleutel `derivative_sha256`); geen netwerk, leest de afbeelding niet; reproduceerbaar tot op de hash.
* `HumanImportProvider` — voert bestaande handmatige annotaties in (o.a. `maldenhof_*_frame_annotation_v1`). Menselijke besluiten worden **niet** overgenomen:
  het resultaat blijft `PROPOSED` met `human_decision=null`.
* `ClaudeVisionProvider` — optioneel, **standaard uitgeschakeld**. Alle waarden (modelnaam, `max_tokens`, maximale lange zijde, maximale base64-grootte) komen van de
  operator; er zijn bewust geen ingebouwde modelnamen of limieten. Een call vereist `enabled=True`, een volledige configuratie, een geldig `PCON-`record
  (menselijke goedkeuring, per foto/hash privacycontrole `ALLOW`, geverifieerde provider-voorwaarden, looptijd, budget) **en** de tweede sleutel
  `MJOP_PHOTO_EXTERNAL_CONSENT_ID` = `consent_id` in de omgeving. De SDK wordt pas bij een echte call geïmporteerd (of een client wordt geïnjecteerd, zoals in de tests).
  De call bevat alleen een image- en een tekstblok: geen sampling-, thinking-, tool- of tracingopties; geen adres-, BAG- of VvE-context. Onbruikbare antwoorden
  (refusal, `max_tokens`, geen JSON, onbekende velden) worden nooit hersteld of aangevuld.
* Elke provider levert een **ruw** antwoord; `build_proposal_set` zet dat deterministisch om en zet alle invarianten zelf. Een model kan `PROPOSED`,
  `human_decision`, `is_instance` e.d. dus niet beïnvloeden; extra velden in het ruwe antwoord geven een fout.

### Gecontroleerde API-specificaties (Anthropic, gecontroleerd 2026-10-13)

Bron: officiële documentatie, <https://platform.claude.com/docs/en/build-with-claude/vision> (docs.anthropic.com was vanuit deze omgeving niet bereikbaar). Gebruikt in de adapter:
een `image`-contentblok met `source.type = "base64"`, `media_type` en `data`; ondersteunde formaten JPEG, PNG, GIF, WebP (`MEDIA_TYPES`; dit is de enige
ingebakken specificatie). Alleen als achtergrond voor de operator (**niet** in code vastgelegd): per afbeelding max. 10 MB base64 (Claude API), max. 8000×8000 px;
vanaf 21 afbeeldingen per request een strengere maatlimiet; kosten ⌈breedte/28⌉ × ⌈hoogte/28⌉ visuele tokens; modellen schalen af boven hun maximale native
resolutie (per modelklasse verschillend); Claude geeft pixelcoördinaten ten opzichte van het beeld **zoals het na eventuele herschaling is gezien**, daarom weigert de
adapter een afgeleide kopie boven de door de operator opgegeven lange zijde (verklein zelf, zodat coördinaten kloppen); Claude leest geen beeldmetadata; de docs stellen dat
geüploade afbeeldingen niet worden bewaard na de request en niet voor training worden gebruikt — de operator moet dit zelf bevestigen in het consentrecord. Telnauwkeurigheid van
het model is volgens de docs bij veel kleine objecten niet gegarandeerd: reden voor menselijke review en evaluatie.

## Hoeveelhedencontract (`photo_quantity_state_v1`)

Een afzonderlijk contract naast de foto-observaties; bestaande velden veranderen niet van betekenis. Methode `GROSS_FRAME_AREA_OUTER_V1`:

> bruto m² = buitenbreedte × buitenhoogte × aantal  (volledige kozijn, glas telt mee, vaste en draaiende delen binnen de buitenmaat, draaiende delen niet extra)

* **Maten komen nooit uit AI.** Invoer `photo_dimension_input_v1`: `source.kind` ∈ {`VALIDATED_REFERENCE_MEASURE`, `BUILDING_DRAWING`, `HUMAN_INPUT`}, gevalideerd door een mens;
  een voorstel mag geen maatvelden bevatten (verifier). Decimal-strings (geen floats), plausibiliteit 0,10–10 m, afronding half-up op 2 decimalen, ook de exacte waarde wordt bewaard.
* **Groeperen naar type** alleen waar onderbouwd: een menselijke type-toewijzing of een goedgekeurde zelfde-type-relatie. Niet-toegewezen openingen vormen een `UNASSIGNED_*`-groep met oppervlakte `null`.
* **Zonder maten blijft de oppervlakte `null`** (nooit 0), per groep met reden (`NULL_NO_TYPE_ASSIGNMENT`, `NULL_NO_DIMENSION_REFERENCE`, `NULL_INVALID_DIMENSIONS`, `NULL_ELEMENT_TYPE_MISMATCH`, `NULL_NO_FULL_MEMBERS`).
* **`PARTIAL` en `OCCLUDED` tellen nooit mee** in oppervlakte en worden nooit als volledig gemeten behandeld (`partial_treated_as_fully_measured` is vast `false`).
* **PHOTO_VISIBLE ≠ gebouwtotaal.** `photo_visible_counts.is_building_total=false`, `building_total = {status: UNKNOWN, value: null}`. Het totaal voor de foto is alleen gevuld als elke volledig zichtbare opening in een berekende groep valt; anders `null` met een informatief subtotaal.
* Vaste `invariants`: geen instance, geen onderhoudshoeveelheid, `painting_area_m2=null` (nooit automatisch), geen kengetal- of prijskoppeling.

## Reviewpagina en demo

```
python scripts/photo_reviewer_demo.py demo --out /pad/buiten/de/repo                  # synthetische gevel, replay, verifier, hoeveelheden, evaluatie, review.html
python scripts/photo_reviewer_demo.py eval-reference-mock --reference-set maldenhof_2 --out /pad/buiten/de/repo   # evaluatieharnas op de menselijke referentie van foto 2 met GEMOCKTE resultaten
```

Uitvoerpaden worden door `run_demo` en `run_reference_mock` zelf gecontroleerd (`safe_out_dir`), dus ook bij direct gebruik buiten de CLI: een map in of boven de repository, een map met bestanden die het script niet zelf schrijft, en symlinks als uitvoerbestand worden geweigerd (testresultaten horen niet in de publieke repo; `.gitignore` is een extra vangnet). Het demo-script bevat geen enkel schrijfpad in de repository; de synthetische fixtures worden uitsluitend opnieuw gegenereerd met het aparte ontwikkelaarshulpmiddel `tests/photo_reviewer/regenerate_fixtures.py` (vereist `MJOP_PHOTO_REGENERATE_FIXTURES=1` en `--confirm-overwrite-fixtures`).
`render_review_page` controleert zijn invoer zelf (voorstelset via de verifier, afbeeldingshash, maatinvoer, en de hoeveelhedenstaat tegen de deterministische herberekening) en weigert met `PhotoError` bij een ongeldige of gemanipuleerde invoer. `review.html` is zelfstandig (afbeelding als
data-URI, geen externe bronnen), escapet alle tekst, toont boxes met ID, onzekerheid, aantallen per type, de gevalideerde maten, bruto m² en een vaste banner dat alles voorstellen zijn.

## Evaluatie

`evaluate.py` koppelt voorstellen één-op-één aan een menselijke referentie (IoU ≥ 0,5, deterministisch) en rapporteert per type TP/FP/FN, precisie, recall, telfout en
zichtbaarheidsovereenkomst. De referentie van Maldenhof-foto 2 (11 kozijnopeningen, 1 buitendeur, 5 dakramen, 1 dakkapel; alleen JSON-coördinaten uit de bevroren stores) wordt
uitsluitend voor evaluatie gelezen; de foto zelf wordt nergens gelezen of als modelinvoer gebruikt (test). **Cijfers uit mock- of replay-antwoorden zeggen niets over de nauwkeurigheid van een echt model.**
Het opzetten van een onafhankelijke DEV/VAL/TEST-splitsing blijft werk voor de volgende fase (zie fase-0-rapport §9).

## Veiligheid

Geen wijziging aan originele foto's, `data/`, `reports/`, menselijke besluiten, instances of MJOP-App (tests hashen de canonieke lagen vóór/na en bewaken het bevroren manifest). Geen automatische
`ACCEPT` of instance-activatie, geen koppeling aan kengetallen of prijzen. Geen ruwe responsen, prompts of runresultaten in de repository; geen API-sleutels in code of logs; geen tracing.
`agent/photo/` bevat geen schrijfaanroepen (statisch getest) en geen SDK-import op moduleniveau; de CI-runner mag geen AI-SDK hebben.

## Wat nodig is voor de eerste echte Claude Vision-test

Zie het eindrapport van de PR: (1) privacy- en toestemmingsbesluit per foto, (2) provider-voorwaarden controleren en vastleggen, (3) afgeleide kopieën maken (EXIF/GPS weg, lange zijde binnen de limiet),
(4) privé-opslag voor runartefacten, (5) operatorconfiguratie (model, limieten, budget), (6) blind gelabelde evaluatiefoto's en vastgelegde drempels, (7) menselijke maatinvoer.

## External Vision Safety Gate v1 (voorwaarden voor de eerste externe Vision-test)

De drie verplichte voorwaarden uit de vorige release zijn technisch ingebouwd in `agent/photo/safety_gate.py` (+ `scripts/vision_budget_ledger.py`).
Er is **nog steeds geen echte aanroep mogelijk**: `PROVIDER_APPROVALS["anthropic"]` staat op `NOT_APPROVED` en kan alleen door een menselijk
gereviewde codewijziging worden omgezet (definitieve provider- en privacygoedkeuring blijft een menselijk besluit).

Elke externe aanroep loopt via `authorize_external_call`, in deze volgorde; het grootboek wordt als laatste geraakt, dus een weigering verbruikt niets:
1. **Providerregister**: alleen status exact `APPROVED`.
2. **Grootboek**: een `BudgetLedger` met `persistent` en `cross_process_safe` (geen geheugen- of eigen implementatie).
3. **Authentiek consentrecord**: strikt schema (nu met `allowed_models`, `derivative_policy.max_file_bytes` en `authorization`), HMAC-SHA256-handtekening van de menselijke
   goedkeurder (`MJOP_VISION_AUTH_KEY`, minstens 32 tekens, nooit in de repository; `sign_consent` is voor de goedkeurder), plus de inhoudelijke controles
   (foto+hash eenduidig, DENY wint altijd, redactie, geldigheid, model, tokens, bestandsgrootte) en de tweede sleutel `MJOP_PHOTO_EXTERNAL_CONSENT_ID`.
4. **Werkelijke afbeelding** (`inspect_image`): echte bytes, niet de claim: bestandskop = declared media type, containerstructuur per formaat (PNG-CRC's, JPEG-segmenten,
   GIF-blokken, WEBP-chunks), EXIF/GPS/XMP/ICC/commentaar/onbekende chunks geweigerd, geen data na het einde, geen animatie, volledige decodering, echte afmetingen gelijk aan het
   verzoek en binnen `max_long_edge_px`, echte bytegrootte binnen `max_file_bytes` en een harde absolute grens, pixelgrens tegen decompressiebommen vóór decodering, hash gelijk aan het verzoek en aan het consentrecord.
5. **Procesoverstijgend budget**: `FileBudgetLedger` reserveert atomair (`flock`) in een hash-geketend append-only JSONL buiten de repository (`MJOP_VISION_LEDGER_DIR`, 0700, geen symlinks).
   `max_calls` en `max_output_tokens` gelden als totaal per `consent_id` over alle processen; een gewijzigd record onder hetzelfde id wordt geweigerd; corrupte of aangepaste keten = alles geweigerd.
   Een niet-verzonden call (bv. ontbrekende SDK) wordt vrijgegeven; een verzonden of mislukt-onzeker verzonden call blijft verbruikt.
6. **Niet te omzeilen**: de gate levert een eenmalig, aan bytes, model, tokens en prompt gebonden `GateAuthorization` (niet zelf te construeren); `_send_authorized` is de enige plek met
   `client.messages.create`; een externe `VisionProvider` kan `analyze` niet overschrijven (de basisklasse draait eerst de poort; `TypeError` bij definitie); tests bewaken dit statisch.

Bekende grenzen: het grootboek beschermt tegen vergissingen, races en onopgemerkte wijzigingen, niet tegen iemand met schrijfrechten op de grootboekmap (die kan het vervangen of de staart afkappen);
de HMAC bewijst dat het record met de sleutel van de goedkeurder is gemaakt, niet wie de sleutel bewaart. Wat nog menselijk moet gebeuren vóór de eerste echte test: provider- en privacygoedkeuring
(`PROVIDER_APPROVALS`), het ondertekenen van een consentrecord met waarden uit de actuele providerdocumentatie, en het instellen van sleutel en grootboekmap.
