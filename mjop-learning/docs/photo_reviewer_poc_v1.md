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
python scripts/photo_reviewer_demo.py eval-maldenhof-mock --out /pad/buiten/de/repo   # evaluatieharnas op de menselijke referentie van foto 2 met GEMOCKTE resultaten
```

De CLI weigert een uitvoermap binnen de repository (testresultaten horen niet in de publieke repo; `.gitignore` is een extra vangnet). `review.html` is zelfstandig (afbeelding als
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
