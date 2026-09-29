# Quantity Engine — technische haalbaarheid en implementatieplan v1

Status: **ontwerp / onderzoek**. Er is geen productiecode, schema, data of
beslissing gewijzigd. Dit document beschrijft wat er nu bestaat, wat haalbaar is
en in welke volgorde ik het zou bouwen.

## 0. Wat is geïnspecteerd

| Repository | Revisie | Opmerking |
|---|---|---|
| `mjop-learning` | `origin/main` @ `e5e912f` (PR #13) | Source of truth voor de data: **545 price observations**, 13 canonieke documenten. |
| `mjop-learning` | `claude/extractie-v1-integratie` @ `ea172b3` | Deze branch. Hij loopt één bot-commit (incoming batch-verwerking) voor op main; de rest van main zit er niet in. Het document staat op deze branch. De cijfers hieronder komen van `main`. |
| `MJOP-App` | `main` @ `1c8d994` | Statische web-app (`src/app.js`, 4.511 regels) + Supabase (auth, `saved_plans`, Stripe). Read-only gekloond. |

Hoe er gecontroleerd is:
- `src/app.js` is gelezen: lookup, geometrie, `ELEMENT_LIBRARY`, kostenberekening, herkomstlabels en bindings.
- De data in `mjop-learning` is met eigen read-only scripts geteld: observations, elementenoverzichten en documentrelaties.

Wat **niet** live gecontroleerd kon worden:
- De PDOK-, BAG- en 3D BAG-API's en de 3D BAG-documentatie. Het netwerk van de analyse-omgeving blokkeerde ze (HTTP 403 / egress blocked).
- Uitspraken over 3D BAG-attributen die MJOP-App níet gebruikt, gemeentelijke bouwarchieven en API-kosten komen daarom uit algemene kennis. Ze zijn hieronder gemarkeerd met **[te verifiëren]**.

---

## 1. Executive summary

1. **Haalbaar, maar in twee heel verschillende delen.**
   - Deel 1 is een *Quantity Evidence-laag*: bronnen, bewijs, statussen, resolutie en menselijke bevestiging. Die kan nu betrouwbaar gebouwd worden, bijna volledig deterministisch, met patronen die `mjop-learning` al heeft (provenance, append-only decision records, `supersedes`, ACTIVE/SUPERSEDED).
   - Deel 2 is een *Drawing Reader*. Die is voor vector-PDF's haalbaar als semi-automatisch hulpmiddel (mens wijst aan, machine meet en telt). Voor scans en volledig automatische herkenning blijft hij experimenteel.

2. **De grootste winst zit nu níet in tekeningen.** MJOP-App berekent vandaag veel hoeveelheden met vaste factoren en noemt ze toch "BAG":
   - kozijnen = appartementen × 1 / 0,25 / 0,125 / 0,125 stuks;
   - buitenschilderwerk = hele buitenmuur m² × €22;
   - dakgoten = €300 + €90 per appartement, zonder meters.

   Daarnaast zitten er drie concrete integriteitsfouten in de hoeveelheidsinvoer:
   - decimalen verdwijnen: `312,6` wordt `3126`;
   - handmatige aanpassingen worden stil overschreven bij het wijzigen van het aantal appartementen;
   - geïmporteerde MJOP-hoeveelheden worden weggegooid.

   Het repareren en expliciet maken hiervan levert direct meer op dan welke vision-oplossing ook.

3. **De historische MJOP's bevatten al veel hoeveelheden, en ze zijn al geëxtraheerd.**
   - De *elementenoverzichten* van 11 van de 13 canonieke documenten leveren **662 elementhoeveelheden** met provenance (pagina, block_id, regel): 283 m², 172 m1, 157 stuks, 48 post.
   - De 545 price observations bevatten daarnaast **actiehoeveelheden** (hoeveel er per uitvoering wordt gedaan). Dat is een ander begrip: bijvoorbeeld "reinigen 1,00 pst" op een gevel van 2.983 m².

   Een apart `quantity_observation`-model is logisch, mits het dit onderscheid (element vs. actie) hard maakt.

4. **Overeenstemming tussen bronnen is vaak géén bevestiging.**
   - DOC-005 en DOC-006 (zelfde gebouw, 2023 en 2026) hebben 31 van 35 elementhoeveelheden identiek.
   - DOC-002 (2026) en DOC-004 (2018, ander bureau) hebben voor het zelfde gebouw exact dezelfde hoeveelheden: 51 m² kozijn, 22 ramen, 117 m² dak.

   Hoeveelheden worden doorgekopieerd. Bronresolutie moet dus bronafhankelijkheid (source cluster / lineage) meewegen. Het middelen of tellen van "3 bronnen zeggen hetzelfde" is gevaarlijk.

5. **Advies.** Bouw eerst:
   - het evidence-model;
   - 3D BAG-regels (inclusief LoD2.2-geometrie voor dakrand en goot);
   - historische elementhoeveelheden;
   - de MJOP-App-integratie met bron, bevestigen en aanpassen.

   Pas daarna de tekeninglezer. Die begint als "vector-PDF + maatlijn-schaal + mens klikt één kozijn → machine vindt gelijke en rekent", gecontroleerd tegen 3D BAG. Gebruik betaalde vision-AI alleen voor classificatie en herkenning van de restgroep, nooit voor de m²-berekening.

---

## 2. Wat al bestaat

### 2.1 MJOP-App — gebouwdata uit BAG / 3D BAG

Bron: `lookupBuilding()` in `src/app.js:286-350`.

**Keten.** De app zoekt eerst het adres op via de PDOK Locatieserver en haalt daar de centroïde op. Daarna haalt hij BAG-panden op in een bbox van ±0,00018° (±20 m) via de PDOK BAG OGC API. Hij kiest het pand dat het adrespunt bevat, anders het pand met de dichtstbijzijnde centroïde. Tot slot haalt hij het 3D BAG-object op via `api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.<id>`.

| Gegeven | Bron / veld | Opgeslagen als | Gebruikt in berekening? |
|---|---|---|---|
| Footprint m² | BAG-pandpolygoon, zelf berekend (`ringArea`, equirectangulaire benadering) | `building.opp` | Alleen als fallback voor dak m² zonder 3D BAG |
| Omtrek m | BAG-polygoon (`ringOmtrek`) | `building.omtrek` | Alleen als fallback voor gevel: `omtrek × 3 × 3` (aanname: 3 lagen van 3 m) |
| Bouwjaar | BAG `bouwjaar` | `building.bouwjaar` | Ja (laatste beurt = bouwjaar) |
| Gebruiksdoel | BAG `gebruiksdoel` | `building.gebruiksdoel` | Nee |
| Pand-ID | BAG `identificatie` | `building.identificatie` | Voor de 3D BAG-call |
| Aantal verblijfsobjecten | BAG `aantal_verblijfsobjecten` → anders `verblijfsobject.length` → anders **1** | `building.units`, `unitsBron` | Ja, heel breed (zie 2.2). **[te verifiëren]** of de OGC-pandcollectie dit veld levert; zo niet, dan valt het terug op 1. |
| Plat dak m² | 3D BAG `b3_opp_dak_plat` | `d3.plat` (afgerond op hele m²) | Ja: `dak-plat` |
| Schuin dak m² | 3D BAG `b3_opp_dak_schuin` | `d3.schuin` (afgerond) | Ja: `dak-hellend` |
| Dak totaal m² | plat + schuin | `d3.dak`, `building.dakM2` | Ja: dakinspectie, dakisolatie |
| Buitenmuur m² | 3D BAG `b3_opp_buitenmuur` | `d3.gevel`, `building.gevelM2` | Ja: gevel, schilderwerk, voegwerk, steiger |
| Grondvlak m² | 3D BAG `b3_opp_grond` | `d3.grond` | Nee |
| Bouwlagen | 3D BAG `b3_bouwlagen` | `d3.lagen` | Nee |
| Daktype | 3D BAG `b3_dak_type` | `d3.daktype` | Nee |
| Hoogte m | `b3_h_dak_max − b3_h_maaiveld` | `d3.hoogte`, `building.werkhoogte` (afgerond; default 9) | Ja: steigertarief (>8 m) |

**[te verifiëren]** Andere 3D BAG-attributen die bestaan maar niet gebruikt worden:
- `b3_opp_scheidingsmuur`: gedeelde muren. Belangrijk bij rijen en blokken, omdat die niet in de buitenmuur zitten.
- Volumes per LoD (`b3_volume_lod12/13/22`).
- Hoogtepercentielen (`b3_h_dak_min/50p/70p`).
- Puntenwolkdatum/-bron (AHN) en kwaliteits- en validiteitsvlaggen.
- De **LoD2.2-geometrie zelf**. Per dakvlak zitten daarin helling, oriëntatie en randen. Daaruit zijn dakrand-m1 en goot-m1 deterministisch af te leiden.

Zwaktes van de huidige lookup:
- **Precisieverlies.** Alle 3D BAG-waarden worden op hele m² afgerond vóór opslag. De ruwe waarde is weg.
- **Pandkeuze is een heuristiek.** Een VvE met meerdere panden krijgt maar één pand. Een verkeerd pand binnen 20 m is mogelijk. Er is geen bevestigingsstap.
- **Geen herkomst per getal.** Er is geen bewaard 3D BAG-versienummer, geen ophaaldatum en geen ruwe payload.
- **`b3_opp_buitenmuur` is bruto.** Er zijn geen openingen afgetrokken. **[te verifiëren]** of muren boven lagere daken en gedeelde muren wel of niet meetellen.

### 2.2 MJOP-App — huidige hoeveelheden per element

Bron: `ELEMENT_LIBRARY` (`src/app.js:379-408`), `bronWaarde()` (`454-465`), `scaleKozCounts()` (`467-474`), `elementCost()` (`657-668`).

| Element (key) | Hoeveelheid nu | Beoordeling |
|---|---|---|
| `dak-plat` | `b3_opp_dak_plat` (fallback: footprint) | **Redelijk.** Echte meting, maar de fallback "footprint = plat dak" is grof. |
| `dak-hellend` | `b3_opp_dak_schuin` | **Redelijk.** Echt dakvlak (hellend oppervlak). |
| `dakinspectie` | €420 + €2 × dak m² | Grof, maar het is een stelpost. |
| `dakisolatie` | dak totaal m² | Grof: plat en schuin door elkaar. |
| `dakgoten` (27.3) | €300 + **€90 × appartementen** | **Zwak.** Goot/HWA wordt in m1 begroot; hier is er geen enkele meter. |
| `gevel-metselwerk` | hele `b3_opp_buitenmuur` | **Zwak.** Bruto muur inclusief glas, plaat, stuc en niet-metselwerk. |
| `schilderwerk-buiten` (31.2) | hele buitenmuur m² × €22 | **Zeer zwak.** Schilderwerk is kozijn-m1/m² hout, niet muur-m². In `mjop-learning` wordt dit per m1 (kozijn&raam) of per m² (gevelbekleding) begroot. |
| `voegwerk` | hele buitenmuur m² | **Zwak.** Zelfde probleem: openingen niet afgetrokken. |
| `steiger` | buitenmuur m² × €6/€11 (werkhoogte >8 m) | Grof, maar verdedigbaar als indicatie. |
| `kozijnen-onderhoud` | stuks = units × {1; 0,25; 0,125; 0,125} voor draairaam/vast glas/deur/dakkapel, vast tarief per stuk | **Zeer zwak.** Pure schatting, geen m², geen gebouwrelatie. |
| `balkonhekken` | per appartement × €210 | **Zwak.** Hekwerk is m1. Er is geen relatie met het werkelijke aantal of de werkelijke lengte van balkons. |
| `intercom`, `verlichting`, `brandveiligheid`, `ventilatie`, `trappenhuis`, `vloerafwerking`, `fietsenstalling` | per appartement | Schatting, bruikbaar als eerste orde. Trappenhuis per appartement is grof: het aantal trappenhuizen ontbreekt. |
| `riolering`, `elektra`, `waterleiding`, `cv`, `bestrating` | vast + variabel × appartementen | Schatting. |
| `lift` | vast €12.000 | Schatting. |

**Integriteitsfouten in de huidige hoeveelheidsstroom.** Allemaal lokaal geverifieerd; het zijn nog geen fixes.

1. **Decimalen worden verminkt.** `num()` (`src/app.js:21-24`) verwijdert alle niet-cijfers en gebruikt die functie ook voor `el-hoeveelheid`: `num('312,6')` en `num('312.6')` geven allebei **3126**. Wie een correcte hoeveelheid met decimalen invoert, krijgt ×10 zonder waarschuwing.
2. **Handmatige hoeveelheden worden overschreven.** `rescaleElements()` (`src/app.js:950-967`) zet `el.hoeveelheid = bronWaarde(...)` voor elk bibliotheek-element. Dat gebeurt bij iedere wijziging van het aantal appartementen (`BINDS['building-units']`) en bij een nieuw adres. Een door de gebruiker bevestigde dak-m² verdwijnt dan zonder melding.
3. **Misleidend herkomstlabel.** `elementOrigin()` (`src/app.js:2860-2874`) toont **"BAG"** bij elk element met een `bron`, ook als de hoeveelheid "aantal appartementen × factor" is. Het label toont het ook bij kozijnen, die volledig geschat zijn.
4. **MJOP-import gooit hoeveelheden weg.** `STJ_CY_RE` vangt hoeveelheid + eenheid in groep 1, maar `extractPdfRegels()` bewaart alleen naam, jaar, cyclus en bedrag. Geïmporteerde posten worden `custom` met alleen een bedrag.
5. **Geen historie.** Een plan is één JSONB-blob (`saved_plans.state`). Er is geen audit van wie welke hoeveelheid wanneer heeft gewijzigd.

### 2.3 MJOP-App — MJOP/planning/cashflow

Wat er bestaat:
- `elementCost()` (hoeveelheid × kengetal);
- `scheduleFor()` en `fullPlan()` (cycli, conditiescore → jaar);
- `kasstroom()` en `benodigdeBijdrage()`;
- rapport en CSV;
- opslaan in Supabase.

Kengetallen zijn **hardgecodeerd** in `ELEMENT_LIBRARY` en er is **geen koppeling** met `mjop-learning`.

Coderingen verschillen:
- MJOP-App gebruikt NL-SfB-achtig `27.1`, `31.2`;
- `mjop-learning` gebruikt de interne 4-cijferige code `4711`, `4621`, `5211` enzovoort (`vocabularies/element_code.json`).

Een crosswalk is dus nodig; dat is een eigen, niet-triviaal item.

### 2.4 mjop-learning — wat herbruikbaar is voor hoeveelheden

| Onderdeel | Relevantie |
|---|---|
| `schemas/_provenance.schema.json` | `document_id`, `page`, `table_index`, `text_fragment`, `block_id`, `related_block_ids`, `sheet`, `cell_ref`, `extraction_rule`. Direct bruikbaar voor tekstbronnen. Voor tekeningen ontbreken een geometrische locatie (bbox/polygoon op een pagina) en een schaalverwijzing. |
| `schemas/_extracted_value.schema.json` | Het patroon `{value, conflict, possible_values, requires_human_review, provenance}` is precies "bron → bewijs". |
| `schemas/_human_verification.schema.json` | ACCEPT/EDIT/REJECT met oorspronkelijke waarde, nieuwe waarde, reviewer en timestamp. |
| Human decision records (`docs/human_review_v1.md`, `human_match_review_v1.md`) | Append-only, `supersedes`, ACTIVE/SUPERSEDED, `input_hashes`, `rule_version`, `evidence`. **Dit is het juiste patroon voor quantity-resolutie**; er hoeft geen tweede systeem te komen. |
| `mjop_maintenance_line` (`docs/mjop_maintenance_line_v1.md`) | Heeft al `quantity` (Decimal-string of null), een tweeledige status (`price_status` / `line_status`) en `effective_total = unit_amount × quantity` in exacte Decimal. Hier komt de quantity-status naast te staan. |
| `mjop_plan` | Versies met `line_hashes`, `content_sha256` en een statusmodel. Een wijziging van hoeveelheid wordt via een nieuwe planversie auditeerbaar. |
| `text_layer.py`, `record_validation.link_source_row_to_blocks` | Deterministische tekstlaag met block-ID's (pdfplumber/pdfminer). De basis voor tekst en maatvoering in vector-PDF's. |
| `nl_values.py` | Conservatieve NL-getalparsing (`"1.250"` → ambigu). Nodig voor maatvoering (`12400`, `12.400`, `12,4 m`). |
| `document_registry.py`, `raw_manifest.json` | sha256 → document_id. Nodig om tekeningen als immutabele bron te registreren. |
| `document_relations.json`, source clusters (comparability D1–D7) | Afhankelijkheid tussen documenten. **Essentieel** voor bronresolutie van hoeveelheden (zie §12 en §9). |
| Incoming-pipeline, profielen, promotie-ledger | Patroon voor "nieuw bestand → deterministische verwerking → review → canoniek". |
| `requirements-pipeline.txt` | Bevat bewust **geen** AI-SDK. Dat principe moet de tekeninglezer overnemen. |

---

## 3. Technische haalbaarheid (overzicht)

| Onderdeel | Haalbaarheid nu | AI nodig? |
|---|---|---|
| Quantity Evidence-model + resolutie + review | Hoog | Nee |
| 3D BAG-attributen als evidence (dak plat/schuin, muur, hoogte, lagen) | Hoog | Nee |
| 3D BAG LoD2.2-geometrie → dakrand, goot, gevel per oriëntatie | Middel-hoog | Nee |
| BGT/BRK → verharding binnen perceel | Middel | Nee |
| Historische elementhoeveelheden (elementenoverzicht) | Hoog; al geëxtraheerd | Nee |
| Hoeveelheden uit offertes (tekst-PDF) | Middel; lay-out wisselt | Deterministisch per profiel; LLM optioneel voor onbekende lay-out |
| Vector-PDF: tekst, maatvoering, lijnen | Hoog | Nee |
| Vector-PDF: schaal bepalen | Middel-hoog, mits maatlijnen aanwezig | Nee |
| Vector-PDF: kozijnen herkennen | Middel met menselijke seed, laag volledig automatisch | Optioneel |
| Scan/raster: OCR van maten | Middel | Klassieke OCR volstaat meestal |
| Scan/raster: kozijnen herkennen | Laag-middel | Ja, of klassieke CV met mens-in-de-lus |
| Bouwarchief automatisch ophalen | Laag; per gemeente verschillend | Nee |

---

## 4. Quantity source architecture

### 4.1 Bronnen en wat ze kunnen leveren

| Bron | Type | Levert | Beperking |
|---|---|---|---|
| **BAG** | registratie | bouwjaar, pandpolygoon, verblijfsobjecten (aantal, oppervlakte, gebruiksdoel) | Geen bouwdelen. Het pand hoeft niet de VvE te zijn. |
| **3D BAG** | afgeleid model (AHN + BAG) | dak plat/schuin m², buitenmuur m², hoogtes, lagen (schatting), LoD2.2-dakvlakken | Geen openingen, balkons of overstekken. Model-resolutie; datum van de AHN-opname. |
| **AHN** | puntenwolk/hoogtemodel | hoogtes, dakopbouwen, controle op 3D BAG | 3D BAG is er al uit afgeleid; meerwaarde is vooral validatie en detail. |
| **BGT** | grootschalige topografie | verharding, groen, scheidingen (muur/hek), overige bouwwerken; pand incl. overstek | Eigendom ontbreekt, dus combineren met het BRK-perceel. |
| **BRK / splitsingsakte** | Kadaster | perceel; appartementsrechten; splitsingstekening | Splitsingstekeningen zijn schematisch en vaak niet op schaal (§14). |
| **Oude MJOP's** | document | elementhoeveelheden (elementenoverzicht) + actiehoeveelheden | Vaak doorgekopieerd; datum; kan fout zijn. |
| **Offertes** | document | hoeveelheden van een aannemer | Scope = offerte, niet het gebouw. |
| **Bouw-, gevel-, doorsnede- en plattegrondtekeningen** | document | meetbare geometrie | Schaal, versie (ontwerp vs. as-built), verbouwingen sinds. |
| **Handmatige invoer / opname** | mens | alles | Moet als bron met auteur en datum worden vastgelegd. |

### 4.2 Methodeklassen (geen scores)

| Klasse | Definitie | Voorbeeld |
|---|---|---|
| `DIRECT_MEASURED` | Gemeten op een geometrische representatie van **dit** gebouw, zonder aannames buiten de meting. | 3D BAG `b3_opp_dak_plat`; polygoon op een geschaalde geveltekening; inmeting ter plaatse. |
| `SOURCE_REPORTED` | Letterlijk getal uit een document over dit gebouw. | Elementenoverzicht "Dakbedekking bitumen 117,00 m2"; offerte "84 m1 HWA". |
| `GEOMETRY_DERIVED` | Deterministische rekenregel op gemeten of gerapporteerde invoer, met expliciete formule. | Dakrand m1 = buitenrand van platte dakvlakken; kozijn m² = Σ(b × h); balkonhek m1 = aantal balkons × gemeten lengte. |
| `ESTIMATED` | Factor, ratio of aanname die niet uit dit gebouw komt. | Units × 0,25 vaste ramen; gevel = omtrek × 3 × 3; kozijn-m² = 18 % van de buitenmuur. |
| `MANUAL` | Door een mens ingevoerd, zonder document. | Beheerder vult 312,6 m² in. |

Methodeklasse en bevestigingsstatus zijn orthogonaal. Een `ESTIMATED` hoeveelheid kan door een mens `CONFIRMED` worden ("klopt ongeveer, ik accepteer dit"). De klasse blijft dan `ESTIMATED`; de UI toont beide.

---

## 5. Drawing Reader-architectuur

```
upload / bouwarchief
   │  (sha256 → document_registry; origineel immutabel)
   ▼
[1] document- & paginaclassificatie ─ deterministisch: vector vs. raster, paginaformaat,
   │                                   titelblok-tekst ("gevel", "plattegrond", "doorsnede", "1:100")
   │                                   AI optioneel: VLM op thumbnail voor restgroep
   ▼
[2a] vector-extractie                 [2b] raster-extractie
   tekst+coördinaten, paden,             render/deskew, OCR (tekst+bbox),
   Form XObjects/blocks                  lijndetectie (LSD/Hough), contouren
   ▼                                     ▼
[3] tekst + maatvoering + geometrie (één gemeenschappelijk tussenformaat per pagina)
   ▼
[4] scale resolver  ── meerdere onafhankelijke schaalbronnen; weigert bij inconsistentie
   ▼
[5] object recognition ── regels/geometrie → template/symbol matching (mens-seed)
   │                       → (later) getraind detectiemodel → (restgroep) VLM
   ▼
[6] geometry engine ── deterministisch: lengtes, oppervlaktes, aftrek, aantallen (Decimal)
   ▼
[7] quantity evidence ── één record per bron/methode, met overlay-geometrie en regelversie
   ▼
[8] human review ── overlay in viewer; accept / edit / reject; append-only decision record
   ▼
[9] confirmed quantity ── via ACTIVE resolution record naar maintenance line / MJOP-App
```

Antwoorden op de vragen uit de opdracht:

1. **Zonder AI:**
   - registratie en hashing;
   - vector/raster-detectie;
   - tekst- en padextractie;
   - maatlijnherkenning in vector;
   - schaalresolutie;
   - alle geometrie en rekenwerk;
   - templatematching op een door de mens aangewezen voorbeeld;
   - consistentiechecks tegen 3D BAG;
   - evidence, review en resolutie.

   OCR met Tesseract/PaddleOCR is machine learning, maar lokaal, goedkoop en geen generatieve AI.
2. **AI/CV nodig voor:**
   - robuuste paginaclassificatie bij onbekende lay-outs;
   - objectherkenning zonder mens-seed (vooral scans en foto's);
   - het lezen van handgeschreven of slecht gescande maten;
   - legenda- en titelblokinterpretatie bij rommelige tekeningen.
3. **Welke AI:**
   - lokaal: OCR (PaddleOCR / Tesseract / docTR) en een objectdetector (RT-DETR/DETR via Hugging Face `transformers` of Detectron2, beide Apache-2.0), getraind op eigen gelabelde gevelcrops;
   - multimodaal model (bijv. Claude) alleen voor classificatie, het labelen van restgevallen en uitleg, altijd met output die de deterministische laag valideert.
4. **Lokaal/open-source:** ja, voor alles behalve de VLM-restgroep. Let op licenties: PyMuPDF en Ultralytics YOLO zijn **AGPL**. Voor een SaaS betekent dat een commerciële licentie of een alternatief (pdfplumber/pdfminer.six/pypdfium2 zijn MIT/Apache/BSD; Detectron2/RT-DETR zijn Apache-2.0).
5. **Externe vision-API nuttig:**
   - bij het bootstrappen van trainingslabels;
   - bij een onbekend tekeningtype;
   - als tweede mening bij `REVIEW_REQUIRED`;
   - bij scans zonder bruikbare maatlijnen, om maten te lezen (niet om te meten).
6. **Kosten per tekening** (API-prijzen per 2026-09, bron: Anthropic-modeltabel):
   - Sonnet 5.5 kost $2 input / $10 output per 1M tokens, Opus 5.5 $4 / $20, Haiku 4.5 $1 / $5.
   - Een afbeelding kost ordegrootte `breedte × hoogte / 750` tokens, met een maximum per afbeelding dat per model verschilt. Meet vóór de begroting met `count_tokens` **[te verifiëren]**.
   - Een A1-gevel is alleen leesbaar in tegels: 6–12 tegels ≈ 10k–60k inputtokens + 2k–5k output (+ thinking).
   - Dat is ≈ **$0,05–0,20 per blad met Sonnet 5.5** en ≈ **$0,10–0,50 met Opus 5.5**.
   - Een bouwdossier van 20 bladen kost daarmee ≈ $1–10.
   - Paginaclassificatie op een thumbnail met Haiku 4.5 kost < $0,01 per pagina.
   - De Batch API halveert dit bij niet-interactief gebruik.
7. **Routine-tekeningen zonder betaalde AI:** ja, voor vector-PDF's met maatlijnen en een mens die één voorbeeld aanwijst. De dure route is alleen voor scans en de restgroep, en per tekening maar één keer: het resultaat wordt evidence en wordt niet opnieuw bevraagd.

---

## 6. Vector-PDF-aanpak

| Vraag | Antwoord | Hoe / library |
|---|---|---|
| Tekst direct uitlezen? | Ja, als de tekst als tekst in de PDF staat. CAD-exports zetten tekst soms om naar paden ("exploded text"); dan is OCR op een render nodig. | pdfplumber/pdfminer.six (al in de repo, `text_layer.py`), pypdfium2; JS: pdf.js `getTextContent()` (al in MJOP-App) |
| Maatvoering uitlezen? | Ja: maatgetallen zijn tekst met positie en rotatie. Koppelen aan de maatlijn gebeurt geometrisch: de dichtstbijzijnde evenwijdige lijn met eindstrepen of pijlpunten, tekst gecentreerd op die lijn. | pdfplumber `chars` / `words` met `matrix`; eigen regels; `nl_values` voor `12400`, `12.400`, `12,4` |
| Lijnen/polygonen? | Ja: paden (move/line/curve/rect/close) met transformatiematrix, lijndikte en kleur. | pdfplumber `lines` / `rects` / `curves`; pdfminer layout; pypdfium2 page objects; PyMuPDF `get_drawings()` (snel, maar AGPL); pdf.js `getOperatorList()` |
| Schaal bepalen? | Ja, zie §8: tekstlabel "1:100" + maatlijnen + paginaformaat + referentiemaat. | Eigen scale resolver |
| Geometrieën meten? | Ja, in PDF-units (1/72 inch) × schaal. Polygonen sluiten, aftrekken en vereenvoudigen. | `shapely` (BSD) voor polygoon-operaties; `Decimal` voor de eindwaarden |
| Herhaalde objecten? | Vaak eenvoudig: CAD-blokken worden soms als hergebruikte Form XObjects geëxporteerd (zelfde XObject = zelfde symbool). Anders geometrische hashing van padgroepen (genormaliseerd voor translatie en schaal). | pdfminer/pypdfium2 voor XObjects; eigen hashing |
| DWG/DXF? | Beter dan PDF: lagen, blokken en echte eenheden. | `ezdxf` (MIT); DWG → DXF via ODA File Converter (gratis, niet open-source) |
| BIM/IFC? | Beste bron: kozijnen (`IfcWindow`), deuren, wanden en slabs met maten en hoeveelheden (`IfcElementQuantity`). Bij VvE-bestaande bouw zelden beschikbaar. | IfcOpenShell (LGPL) |

**Positie in de stack.** Python. Het past bij `mjop-learning` (pdfplumber, pdfminer, pypdfium2 en Pillow zijn al gepind in `requirements-pipeline.txt`). MJOP-App is een statische frontend met Supabase Edge Functions (Deno); die zijn niet geschikt voor PDF/CV-werk. **Architectuurgevolg:** er is een aparte verwerkingsworker nodig, bijvoorbeeld een Python-container met een wachtrij. Die bestaat nu nergens. Zie §16.

---

## 7. Scan/OCR/vision-aanpak

| Stap | Wat | Deterministisch? |
|---|---|---|
| Render/normaliseren | 300–400 dpi; deskew; perspectiefcorrectie bij foto's (4 hoekpunten, homografie) | Ja (OpenCV) |
| OCR | Maatgetallen, schaaltekst, titelblok, legenda — met bbox en rotatie | ML, lokaal (PaddleOCR / Tesseract / docTR) |
| Lijndetectie | Maatlijnen, gevelcontour, kozijncontouren | Ja (OpenCV LSD / Hough, morfologie) |
| Maatlijn ↔ maatgetal | Geometrische koppeling, zoals bij vector | Ja |
| Schaal | Per as uit ≥ 2 maatlijnen (x en y apart, vanwege vervorming) | Ja |
| Objectherkenning | Templatematching op een mens-seed; later een detector | Klassiek of ML |
| Meten | Pixels × schaal per as | Ja |

**Vision-AI nodig** bij foto's van tekeningen, sterk vervuilde of handgetekende tekeningen, tekeningen zonder bruikbare maatlijnen, en onbekende symbolen.

**Grootste betrouwbaarheidsproblemen:**
1. **Schaalvervorming.** Kopieerlagen, scannerslip en A-formaatverkleining veroorzaken anisotrope schaal (x ≠ y) en niet-lineaire vervorming.
2. **OCR-fouten in cijfers.** `1` vs. `7`, `0` vs. `8`, een ontbrekende punt. Eén cijfer verkeerd geeft een factor 10.
3. **Lijnruis.** Arcering, baksteenpatroon en maatlijnen door kozijnen heen.
4. **Tekening ≠ werkelijkheid.** Ontwerp vs. as-built, latere kozijnvervanging, dichtgezette ramen.
5. **Onvolledigheid.** Een gevel staat op meerdere bladen, of een zijgevel ontbreekt.

---

## 8. Scale detection en maatvoering

### 8.1 Schaalbronnen

| Bron | Methode | Valkuil |
|---|---|---|
| Expliciete schaal ("1:100") | Tekst in titelblok of onder het aanzicht. `m_per_pdf_unit = (25,4/72 mm) × 100 / 1000`. | Geldt alleen op het **origineel formaat**. "1:100 op A1" geprint op A3 geeft een factor 2 fout. Meerdere aanzichten op één blad kunnen een andere schaal hebben. |
| Maatlijnen ("12400") | Gemeten lengte van de maatlijn in PDF-units ↔ het maatgetal. Eenheid afleiden: mm is standaard in NL-bouwtekeningen, maar `12,4` kan m zijn. | Maatgetal wijst naar een ketting (deelmaten) of naar een totaalmaat; tekst verkeerd gekoppeld; maatlijn "niet op schaal" (gewijzigd getal, lijn niet aangepast). |
| Bekende referentiemaat | Mens tekent een lijn en typt de lengte. Of een extern bekende maat: gevelbreedte = lengte van het BAG-footprint-segment; nokhoogte ≈ 3D BAG `b3_h_dak_max − b3_h_maaiveld`. | Footprint = bovenaanzicht incl. overstek, dus kleine afwijking. |
| Paginaformaat + titelblok | A-formaat detecteren; "A1" in het titelblok vs. het werkelijke mediabox-formaat. | Helpt alleen om schaallabel-fouten te ontdekken. |
| Schaalstok (grafisch) | Lijnstuk met "0 1 2 5 m". | Zeldzaam op oude tekeningen. |

### 8.2 Resolver-ontwerp (voorkomt grote fouten)

1. **Verzamel alle kandidaten** per aanzicht, niet per blad. Elke kandidaat heeft een waarde (m per unit, per as voor rasters), een bron en een bewijs.
2. **Consensus zonder middelen.** Een schaal is `RESOLVED` alleen als:
   - ≥ 2 onafhankelijke kandidaten elk binnen een vaste relatieve tolerantie van elkaar liggen (bijvoorbeeld 1 % voor vector en 2–3 % voor scans; als regelversie vastgelegd, niet als score), **en**
   - er geen kandidaat is die meer dan die tolerantie afwijkt en niet als "ketting/deelmaat" of "NTS" verklaard kan worden.

   Gebruikte waarde = de waarde van de maatlijnen: de mediaan van de maatlijn-afgeleide schalen. Het schaallabel valideert alleen.
3. **Weigeren is een geldige uitkomst.**
   - Eén kandidaat of tegenspraak → `SCALE_UNRESOLVED`.
   - De tekening mag dan alleen `SOURCE_REPORTED`-maten opleveren (letterlijke maatgetallen), geen gemeten oppervlakten.
4. **Plausibiliteit tegen het gebouw** (harde check, niet stil corrigeren):
   - gevelbreedte vs. BAG-footprint-randlengte;
   - gevelhoogte vs. 3D BAG-hoogte;
   - totaal gevel-m² over alle aanzichten vs. `b3_opp_buitenmuur`.

   Wijkt het meer af dan de vastgelegde grens (bijvoorbeeld ±10 %), dan wordt de evidence `REVIEW_REQUIRED` met reden `SCALE_INCONSISTENT_WITH_3DBAG`. Een factor 2 of 10 valt zo altijd op.
5. **Niet op schaal ("NTS", "niet op schaal", splitsingstekeningen).** Nooit meten; alleen maatgetallen als `SOURCE_REPORTED`.
6. **Gescande vervorming.**
   - Aparte x- en y-schaal uit orthogonale maatlijnen.
   - Bij ≥ 4 referentiepunten een homografie.
   - Het residu (verschil voorspelde vs. opgegeven maat per maatlijn) wordt als bewijs opgeslagen. Een residu boven de grens → `REVIEW_REQUIRED`.
7. **De mens ziet de schaal.** In de review-overlay staat de gebruikte schaal met de maatlijnen die hem onderbouwen, en de mens bevestigt hem expliciet. Een schaalwijziging herberekent alle afgeleide evidence (nieuwe records, oude `SUPERSEDED`).

---

## 9. Object detection

### 9.1 Opties vergeleken

| Aanpak | Sterk in | Zwak in | Voor ons |
|---|---|---|---|
| **Regels/geometrie** | Vector: gesloten rechthoeken binnen de gevelcontour, met binnenlijnen (roeden), op rijen/kolommen uitgelijnd. Dakrand = bovenste contour; HWA = lange smalle verticale rechthoek aan de gevelrand. | Tekenstijlen verschillen per architect of bureau. | **Ja, als basis voor vector.** |
| **Symbol recognition / herhaling** | Hergebruikte XObjects/blokken; geometrische hash van padgroepen. | Werkt niet als elk kozijn apart getekend is. | **Ja, gratis winst waar aanwezig.** |
| **Mens-seed + templatematching** | Mens klikt één kozijn; systeem vindt alle geometrisch gelijke (vector) of visueel gelijke (raster, OpenCV `matchTemplate` / feature matching) en toont ze. Mens corrigeert. | Vraagt één interactie per type. | **Ja, meest praktisch voor de PoC.** Deterministisch, uitlegbaar, geen training. |
| **Klassieke CV** | Rasters: lijnen, rechthoeken, morfologie. | Ruis, arcering. | Als voorbewerking voor scans. |
| **Objectdetectiemodel** (RT-DETR / Detectron2) | Schaalbaar na training. | Heeft honderden tot duizenden gelabelde crops nodig; domeinverschuiving (stijl, eeuw). | **Later**, gevoed door de correcties uit de review (de review levert gratis labels). |
| **Multimodaal model (VLM)** | Onbekende tekeningen; "wat voor tekening is dit"; legenda lezen. | Tellen en exacte bbox zijn onbetrouwbaar; kost geld; niet reproduceerbaar. | **Alleen restgroep en classificatie**; output = kandidaat, nooit maat. |

### 9.2 Per objecttype (geveltekening)

| Object | Praktische aanpak | Opmerking |
|---|---|---|
| Kozijnen / ramen | Mens-seed + geometrische gelijkenis; rechthoeken binnen de gevelcontour | Onderscheid kozijn vs. raam (draaiend deel) is vaak niet uit het aanzicht te halen. Materiaal staat zelden op het aanzicht → uit de legenda, het bestek of van de mens. |
| Deuren | Rechthoek die tot het maaiveld of de vloerlijn doorloopt | Bij voordeur- en portiekpuien overlapt dit met kozijnen. |
| Balkons | Uitstekende horizontale elementen; in plattegrond of doorsnede beter zichtbaar | Aantal = herhaling per verdieping. |
| Hekwerken | Horizontale bovenregel + verticale spijlen; lengte = breedte van het balkon in het aanzicht | m1 = som van de breedtes (+ zijkanten uit de plattegrond). |
| Dakranden | Bovenste contourlijn van het aanzicht; beter uit 3D BAG | Cross-check. |
| HWA's | Lange smalle verticale elementen langs de gevel | Vaak niet of slordig getekend; lengte ≈ gevelhoogte (3D BAG) × aantal. |

**Advies.** Een combinatie, in deze volgorde: geometrieregels → herhaling/XObjects → mens-seed-matching → (later) een eigen detector op reviewlabels → VLM alleen voor de restgroep.

---

## 10. Geometry engine

- **Invoer:** pagina-geometrie (paden in PDF-units of pixels), resolved scale (met bewijs), herkende objecten (polygonen).
- **Rekenkern:** pure functies, `Decimal` voor eindwaarden, `shapely` voor polygonen. Elke functie heeft een ID + versie (`extraction_rule` / `rule_version`).
- **Basisbewerkingen:**
  - lengte (polyline);
  - oppervlakte (polygon);
  - netto = bruto − Σ openingen;
  - aantal;
  - Σ(b × h);
  - projectie;
  - oppervlakte van een hellend vlak = horizontale projectie / cos(helling) (voor 3D BAG LoD2.2).
- **Output per berekening:** waarde, eenheid, formule als tekst, invoerwaarden met hun evidence-ID's, schaal-ID, regelversie, invoerhashes. Hetzelfde patroon als `effective_total` in `mjop_maintenance_line`.
- **Geen afronding tussendoor.** Afronden gebeurt alleen voor weergave.
- **Rekenregels 3D BAG** (voorbeelden, deterministisch):
  - dakrand m1 = lengte van de buitenrand van de platte-dakvlakken;
  - goot m1 = som van de horizontale onderranden van de schuine dakvlakken;
  - gevel per oriëntatie = som van de muurvlakken per normaalrichting.

---

## 11. Quantity evidence model

### 11.1 Drie lagen, zonder concurrerend systeem

```
quantity_evidence            (immutable; één per bron × methode × berekening)
      │  N:1
      ▼
quantity_resolution_record   (append-only decision record, zelfde patroon als
                              human_decision_record: ACTIVE/SUPERSEDED, supersedes)
      │  1 ACTIVE per (building, quantity_subject)
      ▼
maintenance_line.quantity    (bestaand veld) + nieuw: quantity_ref / quantity_status
```

### 11.2 `quantity_evidence` (concept)

```json
{
  "evidence_id": "QE-…",
  "building_id": "…",
  "quantity_subject": {
    "element_code_internal": "3120",
    "subject_text": "Kozijn buiten hout",
    "material_normalized": "wood",
    "location_scope": "voorgevel",
    "quantity_kind": "ELEMENT_QUANTITY"
  },
  "value": "90.88",
  "unit_normalized": "m2",
  "method_class": "GEOMETRY_DERIVED",
  "source_type": "drawing",
  "source_ref": {
    "document_id": "DRW-…", "source_sha256": "…", "page": 3,
    "view_id": "voorgevel", "geometry_refs": ["OBJ-…"],
    "scale_id": "SC-…", "provenance": { "...": "_provenance.schema.json + bbox/polygon" }
  },
  "calculation": {
    "rule_id": "geometry.window_area_sum", "rule_version": "1.0.0",
    "formula": "Σ(b×h) over 32 objecten", "inputs": ["QE-…", "…"]
  },
  "scope_caveats": ["DESIGN_DRAWING_NOT_AS_BUILT"],
  "dependency": { "source_cluster": "…", "derived_from_documents": [] },
  "status": "PROPOSED",
  "requires_human_review": true,
  "review_reasons": ["SCALE_SINGLE_SOURCE"],
  "created_by": "drawing_reader@0.1.0",
  "input_hashes": {}
}
```

- `quantity_kind` is **verplicht**:
  - `ELEMENT_QUANTITY` (hoeveel er is);
  - `ACTION_QUANTITY` (hoeveel er per uitvoering gedaan wordt, bijvoorbeeld herstel 5 %);
  - `SHARE_QUANTITY` (VvE- of breukdeel).

  De data laat zien dat deze in historische MJOP's door elkaar staan (§12).
- `status`:
  - `PROPOSED`: systeem;
  - `REVIEW_REQUIRED`: harde reden aanwezig;
  - `CONFIRMED` / `USER_OVERRIDDEN`: alleen via een resolution record, nooit door het systeem;
  - `SUPERSEDED`: een nieuwere berekening van dezelfde bron vervangt deze, bijvoorbeeld na een schaalwijziging.
- **Nooit gewijzigd.** Correcties zijn nieuwe records.

### 11.3 `quantity_resolution_record` (concept)

| Veld | Betekenis |
|---|---|
| `resolution_id`, `building_id`, `quantity_subject` | sleutel |
| `decision` | `ACCEPT_EVIDENCE` / `USER_VALUE` / `UNKNOWN` |
| `selected_evidence_id` | bij `ACCEPT_EVIDENCE` |
| `user_value`, `user_unit`, `user_basis_text` | bij `USER_VALUE` (dan wordt ook een `MANUAL`-evidence aangemaakt, zodat de waarde zelf herkomst heeft) |
| `considered_evidence_ids` | alle evidence die de mens zag, ook de afgewezen |
| `decision_reason` | verplicht |
| `reviewer`, `reviewed_at`, `rule_version`, `input_hashes`, `supersedes`, `status` (ACTIVE/SUPERSEDED) | zelfde als de bestaande decision records |

Afgeleide weergavestatus voor de UI: `CONFIRMED` (ACCEPT_EVIDENCE), `USER_OVERRIDDEN` (USER_VALUE), `REVIEW_REQUIRED` (geen ACTIVE record, maar wel evidence met review-redenen) of `PROPOSED`.

### 11.4 Aansluiting op de bestaande architectuur

- **Provenance.** `_provenance.schema.json` hergebruiken. Uitbreiden (optioneel, additief, zoals eerder met `block_id`) met `bbox` / `polygon` in paginacoördinaten, `view_id` en `scale_id` voor tekeningen.
- **Review.** Het decision-record-patroon hergebruiken (append-only, `store_invariant_errors`, `append_only_errors`). ACCEPT/EDIT/REJECT uit `_human_verification` blijft voor extractievelden; resolutie is een keuze tussen evidence en past beter bij de decision records.
- **Maintenance line.** `quantity` blijft de enige rekenwaarde. Voeg `quantity_ref` (resolution_id) en `quantity_status` toe, naast `price_status`. `line_status = READY` vereist dan ook een bevestigde quantity. Dit is een regelversie-wijziging van de maintenance line en vraagt een expliciete beslissing.
- **MJOP-plan.** Een quantity-wijziging verandert de line hash, dus via `submit_for_review` / nieuwe versie is dit automatisch auditeerbaar.

---

## 12. Historische quantity observations

### 12.1 Wat er is (gemeten op `main` @ `e5e912f`)

**Price observations (545, 13 documenten).**

| Eenheid | Aantal |
|---|---|
| m2 | 190 |
| m1 | 108 |
| piece | 85 |
| lump_sum | 156 |
| onbekend | 6 |

- Van de 389 observations die geen post zijn (m2/m1/piece + 6 zonder eenheid) hebben er **344** een hoeveelheid ≠ 1.
- Na ontdubbelen (document × element × locatie × eenheid × hoeveelheid) zijn het **363 unieke hoeveelheidsfeiten**: 177 m², 101 m1, 85 stuks.
- Alle 545 hebben `provenance_status: complete` (pagina, regel, `source_text`).
- **Maar:** dit zijn **actiehoeveelheden**. Voorbeeld DOC-001: de observation `2110 Reinigen` heeft `1,00 pst`, terwijl het elementenoverzicht van hetzelfde document `2110 Gevelconstructie metselwerk 2983,00 m2` geeft. Herstelposten gebruiken vaak een fractie van het element.

**Elementenoverzichten (`data/verified/*.json` → `elements[].quantity`).**
- **662 elementen met hoeveelheid**, allemaal via `profile:pro_vve_overzicht15.elements.overview_row`, met block_id en `text_fragment`.
- Per eenheid: 283 m², 172 m1, 157 stuks, 48 post, 2 overig.
- Verdeeld over 11 documenten. DOC-011 (48 elementen) en DOC-015 (23 elementen, XLS) hebben geen elementhoeveelheden.
- DOC-004 (Innax, externe codering) heeft 140 elementen zonder interne `element_code`.

Voorbeelden van **elementhoeveelheden** (gebouwniveau):

| Document | Code | Element | Hoeveelheid |
|---|---|---|---|
| DOC-001 | 2110 | Gevelconstructie metselwerk | 2.983 m² |
| DOC-001 | 3120 | Kozijn buiten hout | 1.613 m² |
| DOC-001 | 4631 | Buitenschilderwerk kozijn en raam hout dekkend | 5.911,1 m1 |
| DOC-001 | 4712 | Dakpan beton | 1.944 m² |
| DOC-001 | 2716 | Gootbekleding zink | 349 m1 |
| DOC-001 | 5211 | HWA pvc | 371 m1 |
| DOC-001 | 3410 | Balustrade aluminium | 430,5 m1 |
| DOC-005 | 4711 | Dakbedekking APP | 425,8 m² |
| DOC-005 | 4711 | Dakrandafwerking zink | 70 m1 |
| DOC-009 | 2321 | Betonvloer balkons | 234,36 m² |
| DOC-002 | 3122 | Draai/val/uitzet raam hout | 22 st |

### 12.2 Bevindingen die het ontwerp sturen

1. **Kopieergedrag.**
   - DOC-005 ↔ DOC-006 (zelfde object, 2023 → 2026): 35 gemeenschappelijke elementen, 31 met identieke hoeveelheid. De 4 verschillen zijn echte wijzigingen, waaronder een eenheidswissel: balustrades staal 75 m² → 20 m1.
   - DOC-002 (2026) ↔ DOC-004 (2018, Innax): exact dezelfde hoeveelheden voor dak, kozijnen, ramen en HWA.

   Gevolg: gelijkheid tussen documenten is geen onafhankelijke bevestiging. `document_relations.json` / source clusters moeten in de resolutie meetellen.
2. **Actie- vs. element- vs. aandeelhoeveelheid.** Fractionele stuks ("4,40 st", "1,60 st" in DOC-004 bij 22 en 8 ramen = 20 %) en kleine m² bij herstel. Comparability v1 vlagt dit al gedeeltelijk (`FRACTIONAL_PIECE_COUNT`).
3. **Eenheidsfouten in de bron.** Voorbeelden: "Binnenschilderwerk stucwerk" 1.500,75 **stuks** (DOC-011); "Kozijn buiten kunststof" 396 stuks (DOC-009). Die moeten `REVIEW_REQUIRED` worden, niet stil genormaliseerd.
4. **Locatie-opsplitsing.** Hoeveelheden staan per locatie ("Voorgevels woningen", "Achtergevel bog"). Het gebouwtotaal is een som, en die som is een `GEOMETRY_DERIVED`-berekening met eigen evidence, niet een nieuw feit.

### 12.3 Advies `quantity_observation`

**Ja, apart model, maar als bronlaag naast `price_observation`, niet erin.**

- `quantity_observation` = één elementoverzicht-rij (of offerte-regel) → `quantity_kind = ELEMENT_QUANTITY`.
- Actiehoeveelheden blijven in `price_observation.quantity_value`. De quantity-laag verwijst ernaar (`price_observation_ids`) en kopieert ze niet.

Voorgestelde velden:
- `quantity_observation_id`, `document_id`, `source_file.sha256`;
- `source_cluster` / `document_relation_ids`, `building_ref` (document-building_id; koppeling aan een BAG-pand is een aparte, menselijk bevestigde stap);
- `element_code_internal` / `element_code_original`, `element_description_original`, `location_original`, `material` (zelfde herkomstregels als de normalisatielaag: F8);
- `quantity_as_stated`, `quantity_value` (Decimal-string), `unit_original`, `unit_normalized`, `quantity_kind`;
- `source_type` (`mjop_element_overview` / `mjop_jarenplan_row` / `quote` / `drawing` / `manual`), `extraction_method` (profielregel-ID), `provenance` (pagina, regel, block_id, cel);
- `direct_or_derived` (`SOURCE_REPORTED` vs. `GEOMETRY_DERIVED` bij sommen);
- `review_status`, `requires_human_review`, `review_reasons`.

Gebruik:
- **Zelfde gebouw.** Als de historische documenten van een VvE bij díe tenant horen: `SOURCE_REPORTED`-evidence.
- **Andere gebouwen.** Nooit als hoeveelheid (tenant-scheiding, CLAUDE.md). Wel geaggregeerd als **ratio's** voor betere `ESTIMATED`-waarden, bijvoorbeeld kozijn-m² / 3D BAG-buitenmuur-m² of HWA-m1 / gevelomtrek, met spreiding en zonder centrale waarde bij te weinig clusters (zelfde regels als kengetallen v1). Dit vereist dat historische documenten aan een BAG-pand gekoppeld zijn.

---

## 13. Integratie met MJOP-App

### 13.1 Doelweergave per post

```
Plat dak vervangen                              4711 · dakbedekking bitumen
┌──────────────────────────────────────────────────────────────────────────┐
│ Hoeveelheid   312,6 m²      ● Bevestigd door j.jansen · 12-10-2026       │
│ Bron          3D BAG (b3_opp_dak_plat, pand 0363…, opgehaald 2026-10-01) │
│               [bron bekijken]  [andere bronnen (2)]  [aanpassen]         │
│ Kengetal      € xx,xx /m²  · mjop-learning KG-4711-… (historisch, niet   │
│               geïndexeerd, prijspeilen 2022–2026)                        │
│ Totaal        312,6 × € xx,xx = € …  (exact; afgerond voor weergave)     │
└──────────────────────────────────────────────────────────────────────────┘
```

- "Andere bronnen" toont alle evidence naast elkaar: waarde, methodeklasse, bron, datum, afhankelijkheid ("overgenomen uit MJOP 2018").
- "Aanpassen" maakt een `MANUAL`-evidence plus een resolution record met verplichte reden, en overschrijft niets.
- Een schatting blijft zichtbaar als schatting: label **"Schatting"** in plaats van "BAG".

### 13.2 Technische route

1. **Stap 0 (fixes, los van de engine):** decimaalparsing, niet overschrijven van handmatige hoeveelheden, correcte herkomstlabels, en hoeveelheid + eenheid bewaren bij import.
2. **Datamodel in de app:** evidence en resolutions eerst in de bestaande `saved_plans.state`-blob (geen migratie nodig), met append-only arrays. Later eigen tabellen met RLS (`quantity_evidence`, `quantity_resolutions`) als meerdere gebruikers per VvE samenwerken.
3. **Rekenregels delen:** 3D BAG-quantity rules als één pure module met gedeelde testvectoren. Voorkeur: Python in `mjop-learning` als referentie + een JS-port met dezelfde fixtures. Alternatief: een server-endpoint.
4. **Codering:** een crosswalk MJOP-App-bibliotheek (`27.1`, `31.2`, …) ↔ interne `element_code` (4711, 4621, …), als vocabulaire met menselijke review. Zonder die crosswalk kan een kengetal uit `mjop-learning` niet aan een app-post hangen.
5. **Kengetallen:** alleen `AVAILABLE` kengetallen uit `mjop-learning`. Op `main` zijn dat er nu 2 (`KG-4711-replace-m1-aluminium`, `KG-5211-replace-m1-pvc`). De hardgecodeerde bibliotheekprijzen blijven voorlopig als expliciet gelabelde richtprijs.

---

## 14. Bouwarchief-strategie **[grotendeels te verifiëren; netwerk geblokkeerd]**

| Vraag | Beoordeling |
|---|---|
| Landelijke bron voor bouwtekeningen? | **Nee**, voor zover bekend. BAG, BGT en 3D BAG zijn landelijk, maar bevatten geen tekeningen. Het Omgevingsloket (DSO) verwerkt nieuwe aanvragen sinds de Omgevingswet (2024), maar is geen openbaar archief van historische bouwdossiers. |
| Kadaster | Splitsingsakte + splitsingstekening per appartementsrecht, tegen betaling op te vragen. Relevant voor VvE's (appartementsrechten, globale indeling), maar schematisch: **niet meten** (§8.2 punt 5). |
| Gemeentelijk | Elke gemeente (of haar archiefdienst) beheert haar eigen bouwarchief. Vormen: online viewer (gedigitaliseerd), digitalisering op aanvraag (kosten, levertijd), inzage ter plaatse, soms beperkte inzage voor beveiligingsgevoelige panden. |
| Via API | Uitzondering. Waar online inzage bestaat, is het meestal een webviewer, geen gedocumenteerde API. |
| Juridisch automatisch downloaden | Beperkingen door gebruiksvoorwaarden van de viewer (scrapen vaak niet toegestaan), het **auteursrecht** van de architect op tekeningen (opslaan en verveelvoudigen in een platform is iets anders dan inzage), en de AVG (bouwdossiers bevatten namen en adressen van aanvragers). Juridische toets nodig vóór een connector. |
| Gefaseerde connector-aanpak logisch? | **Ja, maar pas laat.** Volgorde: (1) de VvE/beheerder uploadt zelf (die heeft recht op inzage, en het bestand wordt tenant-data); (2) een "vind-hulp": adres → gemeente → link naar het juiste loket plus aanvraaginstructie, zonder download; (3) per gemeente een connector alleen waar een officiële API of expliciete toestemming bestaat. Begin met de gemeente waar de meeste klanten zitten. Batch-1-adressen lijken grotendeels Amsterdam; te verifiëren. |

Keten conceptueel:
1. adres → BAG (gemeentecode via woonplaats/openbare ruimte);
2. gemeente → connector-registry (type: `upload_only` / `link_out` / `api`);
3. dossierlijst → mens kiest tekeningen;
4. download (alleen `api` met toestemming);
5. `document_registry`.

---

## 15. Privacy, security, API-kosten

- **Gevoeligheid.** Plattegronden en doorsneden van woongebouwen zijn beveiligingsgevoelig (indeling, toegangen). Bouwdossiers en splitsingsaktes bevatten persoonsgegevens.
  - Opslag in de EU, per tenant gescheiden (RLS zoals `saved_plans`), met een expliciete bewaartermijn.
  - Originelen immutabel met sha256.
  - Toegangslog.
- **Geen kruisbesmetting.** Hoeveelheden van VvE A verschijnen nooit als evidence bij VvE B. Alleen geaggregeerde, geanonimiseerde ratio's (§12.3).
- **Externe AI.** Standaard uit, zoals nu in `requirements-pipeline.txt`. Aan per tenant of per document, met:
  - een verwerkersovereenkomst;
  - dataminimalisatie (alleen de relevante crop, geen titelblok met namen);
  - gelogde modelversie en prompt-versie;
  - output altijd als `PROPOSED` met `method_class` en `created_by` inclusief model-ID.
- **Kosten.**
  - Deterministische route: rekenkracht verwaarloosbaar (seconden CPU per blad).
  - VLM-route: ≈ $0,05–0,50 per blad (§5.6). Eenmalig per document, want de uitkomst wordt evidence.
  - Kostenbeheersing:
    - VLM alleen na een deterministische poging;
    - thumbnails voor classificatie;
    - Batch API voor niet-interactief werk;
    - caching van de prompt;
    - een harde limiet per tenant.

---

## 16. Belangrijkste technische risico's

| # | Risico | Gevolg | Mitigatie |
|---|---|---|---|
| R1 | Verkeerde schaal (label vs. printformaat, NTS) | Factor 2–10 fout | Consensus van ≥ 2 bronnen, 3D BAG-plausibiliteit, weigeren, mens bevestigt de schaal |
| R2 | Tekening ≠ huidige situatie | Systematische fout | `scope_caveats`, datum, mens; 3D BAG als actualiteitscheck |
| R3 | Doorgekopieerde historische hoeveelheden als "bevestiging" | Schijnzekerheid | Source clusters / lineage in de resolutie |
| R4 | Actie-, element- en aandeelhoeveelheid door elkaar | Te lage of te hoge kosten | Verplicht `quantity_kind`; review bij fracties en eenheidsafwijkingen |
| R5 | Verkeerd BAG-pand / meerdere panden per VvE | Alle hoeveelheden fout | Pand(en) laten bevestigen; multi-pand-ondersteuning |
| R6 | 3D BAG-definities (bruto muur, scheidingsmuren, overstek) | Verkeerde interpretatie | Definities vastleggen per regel; testcases op bekende gebouwen |
| R7 | MJOP-App heeft geen backend-compute | Tekeninglezer kan niet draaien | Aparte worker (Python-container + queue); architectuurbeslissing |
| R8 | Licenties (PyMuPDF AGPL, Ultralytics AGPL) | Juridisch/commercieel | MIT/Apache-alternatieven of een commerciële licentie |
| R9 | Te kleine testset tekeningen | Geen meetbare kwaliteit | Eerst een corpus met ground truth (M5) vóór de reader |
| R10 | Codering MJOP-App ≠ mjop-learning | Kengetal en hoeveelheid hangen niet aan elkaar | Crosswalk met review |
| R11 | Integriteitsfouten in de huidige app (decimalen, overschrijven) | Stille fouten van ×10 | Eerst fixen (M0) |

---

## 17. Concrete proof-of-concept

### 17.1 Beoordeling van het voorstel "geveltekening → kozijnen m²"

Dit is een **goede tweede PoC, maar niet de beste eerste**:
- Het combineert de drie moeilijkste onderdelen tegelijk: schaal, herkenning, en de vraag wat een "kozijn-m²" is (buitenwerks? inclusief glas? per gevel?).
- Er is geen testcorpus: de repository bevat MJOP-documenten, geen losse gevel- of bouwtekeningen. Of er tekeningbijlagen in bijvoorbeeld "Actualisatie MOP 2023 met bijlage.pdf" zitten, is niet gecontroleerd.
- Een PoC zonder ground truth levert geen meetbaar resultaat.

### 17.2 Voorgestelde volgorde van PoC's

**PoC-A (klein, hoge waarde, 2–3 weken): "hoeveelheid met herkomst" voor één gebouw.**
- Evidence-model + resolutie (in `mjop-learning`, met tests).
- 3D BAG-regels: dak plat/schuin, buitenmuur, hoogte, plus dakrand-m1 uit LoD2.2.
- Historische elementhoeveelheden van hetzelfde gebouw als `SOURCE_REPORTED`, met lineage.
- Resolutie-UI-mock (of een eenvoudige Excel-review zoals nu) die de 3 bronnen naast elkaar zet.
- Meetbaar: voor de ~10 batch-1-gebouwen 3D BAG vs. elementenoverzicht (dak m², dakrand m1) → tabel met afwijkingen per regel. Dit test ook de pand-koppeling.

**PoC-B (daarna, 4–6 weken): "semi-automatische kozijnen op een vector-geveltekening".**
- 5–10 vector-geveltekeningen met ground truth (handmatig gemeten of uit een bestek).
- Tekst- en maatlijnextractie → scale resolver met plausibiliteit tegen 3D BAG.
- Mens klikt één kozijn → systeem vindt gelijke → Σ(b × h) → overlay → accept/edit.
- Meetbaar:
  - verschil met ground truth per tekening;
  - aantal kliks;
  - aantal geweigerde schalen (weigeren telt als goed gedrag, niet als fout).

Waarom deze volgorde: PoC-A levert direct betere MJOP's, legt het evidence-model vast waar PoC-B in moet schrijven, en geeft de 3D BAG-referentie die de schaal-check van PoC-B nodig heeft.

---

## 18. Implementatiefasen en milestones

Herziene volgorde. Inspanning in grove ontwikkelweken voor één ervaren ontwikkelaar, exclusief menselijke reviewtijd.

| M | Naam | Inhoud | Afhankelijk van | Inspanning |
|---|---|---|---|---|
| **M0** | Quantity-integriteit MJOP-App | Decimaalparsing; handmatige hoeveelheid niet overschrijven; herkomstlabel "Schatting" vs. "3D BAG"; ruwe 3D BAG-waarden + ophaaldatum bewaren; hoeveelheid + eenheid bij import bewaren | – | 0,5–1 |
| **M1** | Quantity Evidence-model | Schema's `quantity_evidence` + `quantity_resolution_record` (append-only, bestaande invariant-checks), `_provenance` additief (bbox/view/scale), docs + tests. Geen data. | – | 1–2 |
| **M2** | Historische quantity observations | Bronlaag uit bestaande elementenoverzichten (662 rijen) + verwijzing naar actiehoeveelheden; `quantity_kind`; lineage via `document_relations`; review-redenen (eenheid, fractie) | M1 | 1–2 |
| **M3** | 3D BAG/BAG quantity rules v1 | Pure regels + fixtures; attributen **[verifiëren]**; LoD2.2 → dakrand/goot/gevel per oriëntatie; pandbevestiging, multi-pand | M1 | 2–3 |
| **M4** | Calibratie van schattingen | Batch-1-gebouwen koppelen aan BAG-pand (mens bevestigt); ratio's (kozijn-m²/muur-m², HWA-m1/omtrek, …) met spreiding, zonder centrale waarde bij < 3 clusters | M2, M3 | 1–2 |
| **M5** | MJOP-App-integratie + human quantity review | Evidence/resolutie in `saved_plans.state`; UI bron/bekijken/aanpassen/bevestigen; crosswalk codering; kengetal-herkomst | M0–M3 | 2–4 |
| **M6** | Tekeningcorpus + ground truth | 10–20 tekeningen (vector + scan) van bekende gebouwen, gelabeld; registreren via `document_registry` | – (parallel) | 1–2 (veel door de gebruiker) |
| **M7** | Vector Drawing Reader + scale resolver | Worker-architectuur (R7); tekst/maatlijnen/paden → tussenformaat; resolver met consensus en 3D BAG-check | M1, M3, M6 | 3–5 |
| **M8** | Gevel/kozijn-PoC (semi-automatisch) | Mens-seed + matching, geometry engine, overlays, review → evidence | M7 | 3–4 |
| **M9** | Gescande tekeningen | Render/deskew, OCR, per-as-schaal, residu; templatematching | M7, M8 | 4–8 |
| **M10** | Detector op reviewlabels | Eigen objectdetector (Apache-licentie), alleen als M8/M9 genoeg labels opleveren | M8, M9 | 3–6 |
| **M11** | Bouwarchief | Eerst link-out/vind-hulp; connectors per gemeente na juridische toets | M5 | 1–3 per gemeente |

Mijlpaal-poorten (niet doorgaan zonder beoordeling, zoals de batchstrategie in CLAUDE.md):
- M1 → M2/M3: het schema is door de gebruiker goedgekeurd. Het is een architectuurkeuze met grote gevolgen.
- M3 → M5: de 3D BAG-vs.-MJOP-vergelijking (PoC-A) is beoordeeld.
- M6 → M7: het corpus heeft ground truth.
- M8 → M9/M10: de kwaliteit op het vector-corpus is gemeten en beoordeeld.

---

## 19. Antwoorden op de hoofdvragen

1. **Technisch haalbaar?** Ja.
   - Het evidence-, bron- en resolutiegedeelte en de 3D BAG-regels zijn gewoon engineering.
   - De tekeninglezer is voor vector-PDF's met maatlijnen haalbaar als semi-automatisch hulpmiddel.
   - Volledig automatisch lezen van willekeurige (gescande) tekeningen is dat nog niet betrouwbaar.
2. **Nu betrouwbaar te bouwen:**
   - M0 (fixes);
   - het evidence-model met resolutie en review;
   - historische elementhoeveelheden;
   - 3D BAG-attribuutregels;
   - de MJOP-App-weergave bron/bevestigen/aanpassen;
   - tekst- en maatlijnextractie uit vector-PDF.
3. **Experimenteel:**
   - LoD2.2-afgeleide dakrand/goot (tot gevalideerd);
   - de schaalresolver op echte tekeningen;
   - objectherkenning;
   - alles met scans;
   - calibratieratio's (kleine steekproef);
   - bouwarchief-connectors.
4. **AI nodig:**
   - objectherkenning zonder mens-seed;
   - classificatie en legenda-lezen van onbekende tekeningen;
   - slecht leesbare scans;
   - OCR (lokaal ML, geen generatieve AI).
5. **Volledig deterministisch:**
   - registratie;
   - vector-extractie;
   - maatlijnkoppeling;
   - schaalconsensus;
   - geometrie en rekenwerk;
   - 3D BAG-regels;
   - template/geometrische matching op een seed;
   - plausibiliteitschecks;
   - evidence, resolutie en audit.
6. **Eerste PoC:** PoC-A, "hoeveelheid met herkomst". 3D BAG + historisch MJOP + handmatig voor dezelfde batch-1-gebouwen, met resolutie en een meetbare vergelijking. Daarna PoC-B (vector-gevel, kozijnen, semi-automatisch).
7. **Hoeveel nieuw werk:**
   - Evidence-, 3D BAG- en integratiedeel (M0–M5): ≈ 8–14 weken, voor ~50 % hergebruik van patronen en tooling in `mjop-learning` en de bestaande lookup in MJOP-App.
   - Tekeninglezer (M6–M9): ≈ 11–19 weken, ~85–90 % nieuw. Alleen de tekstlaag, NL-getalparsing, registry en reviewpatronen zijn herbruikbaar. Er komt ook nieuwe infrastructuur bij (worker).
8. **Herbruikbaar uit MJOP-App:**
   - PDOK/BAG/3D BAG-lookup (uit te breiden);
   - geometriehelpers (`ringArea`, `ringOmtrek`, `pointInRing`);
   - `elementCost` / `scheduleFor` / `kasstroom`;
   - de pdf.js-tekstextractie;
   - Supabase auth, RLS en `saved_plans`;
   - element-detail-UI (`renderHoeveelheidKengetal`) als plek voor het quantity-paneel;
   - `elementOrigin` als aanzet (te herdefiniëren).
9. **Herbruikbaar uit mjop-learning:**
   - `_provenance`, `_extracted_value`, `_human_verification`;
   - het decision-record-patroon (append-only, supersedes, invariant-checks);
   - `mjop_maintenance_line` (`quantity`, statusmodel, exacte Decimal-berekening);
   - `mjop_plan` (versies, hashes);
   - `text_layer` / `record_validation` (block-provenance);
   - `nl_values`;
   - `document_registry`, raw-manifest;
   - `document_relations` / source clusters;
   - element_code-vocabulaire;
   - de incoming-pipeline als patroon;
   - de 662 elementhoeveelheden;
   - kengetallen v1.
10. **Grootste risico's:**
    - verkeerde schaal (R1);
    - doorgekopieerde hoeveelheden als schijnbevestiging (R3);
    - door elkaar lopende hoeveelheidssoorten (R4);
    - verkeerd pand (R5);
    - geen backend en geen testcorpus (R7, R9);
    - en nu al: stille integriteitsfouten in de app (R11).
11. **Deze architectuur aanraden?** Ja, het principe bron → bewijs → deterministische berekening → proposed → menselijke bevestiging, met twee aanpassingen:
    - begin bij 3D BAG en historische bronnen in plaats van bij tekeningen;
    - maak de tekeninglezer eerst mens-in-de-lus (seed + matching) in plaats van een autonome herkenner.

    Een VLM-first-aanpak zou ik niet kiezen: niet reproduceerbaar, slecht in tellen en maatvoering, en per tekening terugkerende kosten.
12. **Eerstvolgende milestone:**
    - **M0** is klein: vier concrete fixes in MJOP-App, zodat de bestaande hoeveelheden niet stil fout gaan.
    - Direct daarna **M1**: het Quantity Evidence-schema met resolution records, als ontwerp en tests in `mjop-learning`, ter goedkeuring voorgelegd vóór er data wordt aangemaakt.

    Beide zijn voorwaarde voor al het andere en vragen geen AI, geen nieuwe dependencies en geen tekeningen.
