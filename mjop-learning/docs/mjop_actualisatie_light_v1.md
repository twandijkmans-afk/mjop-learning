# MJOP-actualiseringstool "Light" — versie 1

Aanleiding: het wetsvoorstel *Versnelling verduurzaming en onderhoud VvE's* (internetconsultatie
juli–september 2026) wil de minimale looptijd van een MJOP verlengen van 10 naar 30 jaar en een
duurzaamheidsparagraaf verplicht maken. Het is nog geen wet. Wordt het aangenomen, dan moeten
bestaande MJOP's naar een 30-jaarshorizon. Deze tool zet een bestaand MJOP (van onszelf of van een
ander bureau) om naar een **30-jaars concept** met een advies voor de reservefondsstorting.

> Het resultaat is een CONCEPT op basis van een bestaand plan. Het is niet geïnspecteerd (geen
> NEN 2767-conditiemeting) en bevat geen actuele marktprijzen. Planjaren en bedragen blijven
> voorstellen. De beoordeling gebeurt na import in OPrognose: elke handeling vermeldt daar in de
> opmerking herkomst, aannames en vlaggen.

Niet in v1: verwerken van uitgevoerd onderhoud, hoeveelheden herijken (3DBAG/gevelscanner), conditie
via een app-schouw, en de duurzaamheidsparagraaf.

## Onderdelen

| Stap | Script | Wat |
|---|---|---|
| Levensduurtabel | `scripts/mjop_lifecycle.py`, `vocabularies/lifecycle_table.json`, `schemas/lifecycle_table.schema.json` | cycli per (elementcode, actie), waargenomen in eigen MJOP's; effectief na een menselijke beslissing |
| Regelmodel | `scripts/mjop_maintenance_line_v2.py`, `schemas/mjop_maintenance_line_v2.schema.json` | Maintenance Line v2: herkomst, planningsvoorstel en geïndexeerd historisch bedrag |
| Import | `scripts/mjop_import_existing.py` | `data/verified/<DOC>.json` → v2-regels (`FROM_EXISTING_MJOP`) |
| Prijs | `scripts/mjop_price_index.py`, `config/price_index.json` | expliciete indexatie met een door een mens ingevoerde reeks |
| Horizon | `scripts/mjop_horizon_planner.py` | 30-jaars jaarvoorstellen, doorrollen en toegevoegde langcyclische vervangingen |
| Reservefonds | `scripts/mjop_reserve_fund.py` | jaarlijks verloop, tekortjaren en minimale storting |
| OPrognose-export | `scripts/mjop_oprognose_export.py`, `config/oprognose/` | XML-importbestand voor OPrognose + formaatcontrole |
| CLI | `scripts/mjop_actualisatie.py` | `run`: alles in één keer → OPrognose-XML + rapport.md |
| Tests | `tests/test_mjop_actualisatie.py` | |

## Levensduurtabel

`python scripts/mjop_lifecycle.py build` leest `data/verified/` en meet per document de intervallen
tussen de planjaren van dezelfde (element, actie). Alleen posten **met** elementcode tellen mee. Dat
zijn onze eigen MJOP's: documenten van derden zoals DOC-004 hebben geen code. Codes `ZZZZ` en `9999`
(staartkosten, advies) tellen niet mee. Per combinatie: aantal documenten, min/mediaan/max en
`proposed_cycle_years`. Dat laatste veld wordt alleen gevuld als de mediaan een geheel getal is; er
wordt niet afgerond. `max_observable_interval` is de langste planperiode van de bron-documenten.

**Belangrijke beperking.** De historische MJOP's beslaan 10–15 jaar. Korte cycli (schilderwerk,
reinigen, kleine herstellingen) zijn goed waarneembaar. Vervangingen van dak, kozijnen, lift en
installaties komen hooguit één keer voor, dus hun levensduur is **niet** waarneembaar. Die moet een
mens vastleggen:

```
python scripts/mjop_lifecycle.py decide 4711 replace EDIT --value 25 --by <naam> --note "bron ..."
python scripts/mjop_lifecycle.py decide 4621 exterior_painting ACCEPT --by <naam>
```

Pas daarna is `cycle_years` effectief. Bij elke beslissing worden het oorspronkelijke voorstel, de
waarde, de gebruiker en het tijdstip bewaard. Bij `build` blijven eerdere beslissingen behouden. De
tabel bevat geen VvE-specifieke inhoud: alleen document-, element-IDs en jaren.

### Tweede bron: cycli uit OPrognose-exports

`python scripts/mjop_lifecycle.py oprognose <exports...> [--local-report <pad buiten de repo>]` leest
OPrognose-exports in. Dat kunnen losse `.xml`-bestanden zijn, mappen of `.zip`-bestanden; foto's worden
genegeerd en dubbele exports tellen één keer. Per (elementcode, actie) komen de cycli die adviseurs in
OPrognose hebben gezet in `observed_oprognose` te staan: aantal bestanden, aantal handelingen, aantal
eenmalige handelingen, min/mediaan/max, de verdeling en een voorstel bij een gehele mediaan.

- Alleen geplande handelingen (`han_type H`) met een 4-cijferige `ele_nlsfb` tellen mee; `9999` en
  `ZZZZ` niet.
- De actie wordt eerst exact opgezocht in `vocabularies/maintenance_action.json`. Daarna gelden de
  trefwoordregels in `config/oprognose/action_text_rules.json`. Bij schilderwerk beslist "buiten" of
  "binnen" in de tekst, anders het label van de elementcode. Een tekst die op meer dan één actie past,
  of op geen enkele, wordt niet ingedeeld. Zulke teksten staan in het lokale rapport.
- In de tabel komen geen klantgegevens: alleen codes, cycli, aantallen en per bronbestand een sha256
  (`oprognose_sources`). Het lokale rapport bevat wel handelingsteksten en hoort buiten de repository.
- Een cyclus wordt pas effectief na een menselijke beslissing:
  `python scripts/mjop_lifecycle.py decide 6611 replace ACCEPT --source OPROGNOSE --by <naam>`.
  `proposal_source` legt vast welk voorstel is geaccepteerd.

Waarneming op 10 exports (ter indicatie; regels v2 strippen planningsnotities als "gelijktijdig met …" en tekst tussen haakjes, en lezen "vervangen schilderwerk" als schilderwerk):

- 90 combinaties, waarvan 61 met een voorstel; 29 handelingen niet ingedeeld. Vrijwel alle grote vervangingen zitten erbij.
- De waarde 48 komt vaak voor bij kozijnen, balkons en hekwerk. Dat lijkt een vaste waarde voor
  "buiten de planperiode".
- Bij 4711 zijn "nieuwe laag aanbrengen" (`install`, 25 jaar) en "vervangen" (`replace`, meestal
  50 jaar) verschillende ingrepen.
- Binnenschilderwerk staat in OPrognose op 14–21 jaar, in de oude MJOP's op 5–8 jaar.

Een mens moet deze punten beoordelen.

## Maintenance Line v2

v2 = alle velden en regels van v1, plus de onderstaande. Een v2-regel wordt gevalideerd door het
v2-schema, door de volledige v1-validatie op `to_v1_view(line)` en door de v2-invarianten.
Bedragbewerkingen (kengetalworkflow, handmatig bedrag) lopen via de v1-functies. `financial.indexation`
blijft `none`. `mjop_plan` valideert v1- en v2-regels elk met hun eigen regels
(`mjop_maintenance_line_v2.any_line_errors`). Bestaande v1-regels blijven geldig. Migreren gebeurt
alleen expliciet, met `upgrade_v1`.

| Veld | Betekenis |
|---|---|
| `origin` | `FROM_EXISTING_MJOP` / `ADDED_FROM_LIFECYCLE` / `MANUAL` |
| `origin_source` | document-ID, pagina's, bron-action-IDs, **planjaren uit het oude MJOP**, of de levensduurtabel-sleutel |
| `proposed_planned_year`, `planning_basis` | voorstel van de planner: gebruikte cyclus en bron, basisjaar en bron, doorgerold ja/nee |
| `planner_flags` | o.a. `NOT_INSPECTED`, `CYCLE_UNKNOWN`, `OVERDUE_NO_CYCLE`, `ASSUMED_FROM_CONSTRUCTION_YEAR`, `CYCLE_DOCUMENT_TABLE_DIFFER`, `ELEMENT_CODE_MISSING`, `PRICE_LEVEL_UNKNOWN`, `INDEX_MISSING` |
| `planning_status`, `planning_verification` | `NOT_PLANNED` → `PROPOSED` → `HUMAN_ACCEPTED` / `HUMAN_ADJUSTED` / `REJECTED` (ACCEPT/EDIT/REJECT, met het oorspronkelijke voorstel) |
| `price_update` | historisch bedrag per keer × indexfactor; `PROPOSED` → `HUMAN_ACCEPTED` / `REJECTED` |

Een planjaar uit een oud MJOP wordt **niet** als `planned_year` overgenomen. Het staat als herkomst in
`origin_source.document_planned_years`. `planned_year` en `cycle_years` worden pas gezet na
ACCEPT of EDIT, of als een gebruiker ze zelf invult.

## Prijsactualisatie

`config/price_index.json` bevat een indexreeks per jaar (bijvoorbeeld CBS/BDB) met `index_source`. Een
mens vult die in; de tool haalt niets automatisch op. In de repository is de reeks bewust leeg.
`factor = round(index[doel] / index[basis], 6)` (ROUND_HALF_EVEN) en
`indexed_total = bedrag × factor` (exact Decimal). Het basisjaar is het jaar van `price_level_date`
uit het document. Dat jaar wordt niet afgeleid uit de inspectiedatum. Ontbreekt iets, dan wordt
niets berekend en vermeldt het resultaat de reden: `SOURCE_AMOUNT_MISSING`,
`SOURCE_AMOUNTS_DIFFER` (verschillende bedragen per keer), `PRICE_LEVEL_UNKNOWN` of
`INDEX_MISSING`. Een geïndexeerd historisch bedrag is geen marktprijs. Een actueel bedrag loopt via de
kengetalworkflow of een handmatig bedrag.

## Gefaseerde uitvoering in het oude MJOP

Soms liggen de planjaren van dezelfde post in het oude MJOP 1 of 2 jaar uit elkaar. Een voorbeeld is
riolering die per stijgleiding wordt vervangen in 2026, 2027 en 2028. Dat is gefaseerde uitvoering,
geen cyclus.

- `mjop_import_existing` maakt dan per fase een eigen, eenmalige regel met de vlag
  `PHASED_IN_DOCUMENT`.
- `mjop_lifecycle` telt zulke intervallen niet mee als levensduur.
- Vanaf 3 jaar geldt een interval wel als cyclus, zoals een herinspectie om de 3 jaar.

## Horizon-planner

Horizon: `start .. start + 29`. Per regel zonder menselijke planningsbeslissing:

- **Cyclus.** De volgorde is: `cycle_years` van de regel, dan gelijkmatige intervallen in het oude
  MJOP, dan de door een mens vastgestelde levensduurtabel. Wijken het oude MJOP en de tabel af, dan
  wint het document voor dit gebouw en krijgt de regel de vlag `CYCLE_DOCUMENT_TABLE_DIFFER`.
- **Eerste jaar.** Eerst het vroegste planjaar uit het oude MJOP dat op of na de start valt. Anders
  het laatste planjaar (of `last_replacement_year` / `last_maintenance_year`) plus n × cyclus
  (doorgerold). Zonder cyclus en met alleen verstreken jaren: `OVERDUE_NO_CYCLE` en geen voorstel.
  Na de horizon: `BEYOND_HORIZON` en geen voorstel.
- **Toegevoegde vervangingen.** Een fysiek element uit het oude MJOP krijgt een regel
  `ADDED_FROM_LIFECYCLE` als aan twee voorwaarden is voldaan: er staat binnen de horizon geen
  vervanging gepland, en de levensduurtabel heeft een door een mens vastgestelde `replace`-cyclus.
  Het basisjaar is het laatste vervangingsjaar dat de gebruiker opgeeft
  (`--last-replacement CODE=JAAR`), anders het bouwjaar. Dat laatste is altijd een aanname en krijgt
  de vlag `ASSUMED_FROM_CONSTRUCTION_YEAR`.
- Elementen zonder vastgestelde vervangingscyclus komen op de checklist `lifecycle_unknown`
  (in rapport.md onder "Wat er is gedaan").

## Koppelingen

Register: `vocabularies/lifecycle_couplings.json`; schema: `schemas/lifecycle_couplings.schema.json`;
module: `scripts/mjop_couplings.py`. TD heeft het model en de lijst op 2026-11-26 goedgekeurd. Een
koppeling zonder `human_verification` wordt niet toegepast.

Koppelingen gelden alleen voor planmatig onderhoud. Een gebrek krijgt altijd een eigen eenmalige
B-post en wacht nooit op een koppeling.

| Soort | Werking |
|---|---|
| SAMEN | bij elke ingreep van de leider: eerste leiderjaar, ritme van de leider |
| ELKE_N | bij elke n-de ingreep: eerste leiderjaar, n × het ritme van de leider |
| MEESCHUIVEN | eigen cyclus; het eerste jaar schuift naar het dichtstbijzijnde leiderjaar, maximaal 3 jaar (`max_shift_years`) |
| VERSCHOVEN | `offset_years` na de leider, in het ritme van de leider |

Het **ritme van een leider** is de vereniging van de uitvoeringsjaren van alle passende regels, over
een venster van 100 jaar voorbij de horizon.

- Is het interval vast, dan is dat het ritme. Zo geven dakbedekking vervangen (50) en overlagen
  (50, 25 jaar verschoven) samen het ritme van een "dakingreep": elke 25 jaar.
- Is het interval niet vast, zoals bij buitenschilderwerk met cycli van 6 en 7 jaar, dan wordt het
  meest voorkomende ritme gekozen. De regel krijgt dan de vlag `COUPLING_IRREGULAR_LEADER`.

Verdere regels:

- Alleen volgers zonder menselijke planningsbeslissing worden aangepast.
- Omgekeerde verankering bij VERSCHOVEN: berust de dakvervanging alleen op een aanname (het bouwjaar)
  en staat de overlaging met een jaar in het oude MJOP, dan wordt de vervanging aan dat jaar
  verankerd (`COUPLING_REANCHORED_LEADER`).
- Een VERSCHOVEN-volger die ontbreekt, zoals de overlaging bij een toegevoegde dakvervanging, wordt
  toegevoegd als de levensduurtabel er een vastgestelde cyclus voor heeft.
- Voorstellen na het einde van de horizon blijven staan, met de vlag `BEYOND_HORIZON`. Ze tellen niet
  mee in het reservefonds, maar wel voor het ritme. OPrognose slaat ze op dankzij het bitpatroon tot
  2199.
- In de OPrognose-opmerking staat `GEKOPPELD (<soort>[, ±n jr geschoven]): <koppeling>`.

Koppelingen in het register: K01 valbeveiliging samen met elke dakingreep; K02 dakrand, vorsten en
lood samen met dakbedekking vervangen; K03 overlagen 25 jaar na vervangen; K04 houtrotherstel
kozijnen samen met buitenschilderwerk; K05a/b hang- en sluitwerk bij elke 2e schilderbeurt; K06
kilgoot meeschuiven naar een schilderjaar; K07a/b steiger- en bereikbaarheidskosten samen met
buitenschilderwerk; K08 schilderwerk metalen hekwerk samen met schilderwerk buitenkozijnen; K09
hemelwaterafvoeren samen; K10 liftonderdelen samen; K11–K13 gevelreiniging, impregneren en
kitvoegen/voegwerk meeschuiven naar een schilderjaar (groep 2, TD); K14 kozijnen reinigen meeschuiven
naar een schilderjaar (groep 3, TD).

Vervangingen met een cyclus van 60 jaar (balkonconstructie 2322, trappen 2410, gevelbekleding 4112)
vallen bij gebouwen uit ongeveer 1967–1996 binnen de horizon. Zonder bekend laatste vervangingsjaar
is dat altijd op basis van de bouwjaar-aanname, met de vlag `ASSUMED_FROM_CONSTRUCTION_YEAR`. Geef
zo nodig het werkelijke jaar mee met `--last-replacement CODE=JAAR`.

## Gebreken (B-posten)

Schema: `schemas/defect_input.schema.json`; module: `scripts/mjop_defects.py`; invulvoorbeeld:
`config/oprognose/defects_template.json`. Gebruik: `--defects <bestand>` bij `run`. Het bestand
bevat VvE-specifieke gegevens en hoort niet in de repository.

Een adviseur voert de gebreken in. De tool leidt zelf geen gebreken af: een oud MJOP is geen
inspectie. Besluiten van TD (2026-11-26):

- Elk gebrek wordt een eenmalige **B-post** in OPrognose met cyclus 0, urgentie 1–3, eigen bedrag en
  eventueel een NEN 2767-code. De vaste waarden komen uit de voorbeeldexport (`oph_bevinding`:
  B, 100, actie A, factor 0).
- Een gebrek wacht nooit op een cyclus of koppeling.
- Leidt een gebrek tot uitvoering van een planmatige handeling (`restart.action`, bijvoorbeeld
  `replace`), dan **herstart het ritme** vanaf het gebreksjaar. Het gebreksjaar wordt dan het laatste
  uitvoeringsjaar van die handeling, en de gekoppelde handelingen schuiven mee. Bestaat de regel nog
  niet, dan geldt het jaar voor een toe te voegen vervanging. De regel krijgt de vlag
  `RESTARTED_BY_DEFECT`.
- Een vervanging die al gepland staat, ook na de horizon, wordt niet nogmaals toegevoegd.
- Gebreken tellen als definitieve uitgaven in het reservefonds, op hun eigen prijspeil
  (`price_level_year`). Het rapport waarschuwt als dat prijspeil afwijkt van `obj_prijspeil`.
- Een gebrek zonder prijs krijgt prijs 0 en de opmerking "GEEN PRIJS".

## Reservefonds

Bij een kosteninflatie `i` ziet de berekening er per jaar `t` zo uit:

- uitgaven = Σ bedrag per keer × (1+i)^(t − prijspeiljaar)
- storting = C × (1+g)^(t − start)
- rente = saldo × r

Elk jaarbedrag wordt afgerond op centen. Het bedrag per keer komt in deze volgorde: een definitief
v1-bedrag, dan een geaccepteerd geïndexeerd bedrag, dan (alleen in de CONCEPT-modus) een voorgesteld
geïndexeerd bedrag. Het advies is de laagste storting in centen waarbij het saldo nooit onder
`min_balance` komt. Dat wordt gegeven als gelijkblijvend bedrag en, bij een opgegeven groei `g`, als
geïndexeerd bedrag. De berekening is eerst analytisch (het saldo is lineair in C) en wordt daarna met
een simulatie bevestigd. Optioneel staat ter vergelijking 0,5% van een opgegeven herbouwwaarde
vermeld. Alle percentages zijn invoer; de tool vult geen standaardwaarden in.

De status is `CONCEPT`: voorstellen tellen mee. De waarschuwingen melden:

- regels zonder cyclus: die komen maar één keer voor, waardoor latere jaren te laag uitvallen;
- regels zonder bedrag;
- gemengde btw-basis.

Bedragen uit kengetallen houden hun eigen prijspeil (zie `mjop_plan.plan_totals`). In v1 worden ze
niet herindexeerd.

## OPrognose-export

Het formaat is overgenomen uit een echte OPrognose-export. Het is een .NET DataSet-XML:
`<NewDataSet>`, gevolgd door het ingebouwde XSD-schema, gevolgd door één object. Het schemablok
staat letterlijk in `config/oprognose/dataset_schema.xml`; dat bestand bevat alleen velddefinities.
Het voorbeeldbestand zelf bevat klantgegevens en staat niet in de repository.

Structuur:

- `opo`: het object, 133 kolommen;
- `ope`: de elementen, 64 kolommen;
- `oph`: de handelingen per element, 76 kolommen;
- daarnaast kent het schema `opu` (uitmeting), `ops` (historie) en `opm` (metingen). Die worden niet
  gevuld.

Elk record bevat alle kolommen in schemavolgorde. Lege waarden worden geschreven zoals OPrognose dat
doet: `<veld />`, `0`, `false` of `1900-01-01T00:00:00+01:00`. Het bestand gebruikt CRLF-regeleinden
en springt 2 spaties in. De kop en het schema van een gegenereerd bestand zijn byte-voor-byte gelijk
aan de voorbeeldexport.

Deze regels zijn afgeleid uit de voorbeeldexport en gelden voor alle handelingen daarin:

| OPrognose | Waarde |
|---|---|
| `ele_nlsfb` / `ele_nlsfbhoofd` | elementcode (4 cijfers) / eerste 2 cijfers |
| `ele_tekst`, `ele_hvh`, `ele_eenheid`, `ele_locatie` | element uit het oude MJOP |
| `han_tekst` | actietekst uit het oude MJOP (of "Vervangen" bij een toegevoegde regel) |
| `han_startjaar`, `han_cyclus` | (voorgesteld) eerste jaar en cyclus; `0`/`0` als er geen jaar is |
| `han_bitpatroon` | 200 tekens; positie 0 is het jaar 2000; `1` = uitvoering |
| `han_hvhreken`, `han_prijs`, `han_totaal` | hoeveelheid, eenheidsprijs (afgerond op centen), `hvhreken × prijs` |
| `han_hvh` | `hvhreken / ele_hvh` (6 decimalen); `1` bij een andere eenheid |
| `han_opm` | herkomst (document en pagina), VOORSTEL of definitief, cyclusbron, basisjaar, vlaggen en bedragbasis |
| vaste velden | `config/oprognose/export_defaults.json` (H, A, 101, fonds 10, btw H, …) |

Geplande handelingen worden geëxporteerd als `han_type H`. Gebreken die een adviseur invoert, gaan
mee als `han_type B` (zie Gebreken).

Prijs:

- Heeft elk historisch bedrag een indexfactor, dan krijgen de handelingen geïndexeerde bedragen en is
  `obj_prijspeil` het doelprijspeil.
- Zo niet, dan krijgen ze de historische bedragen en is `obj_prijspeil` het prijspeil van het oude
  MJOP. OPrognose kan dan zelf indexeren.
- Is dat prijspeil onbekend, dan is de prijs `0` en staat het historische bedrag in de opmerking.
  Een bedrag met een verkeerd prijspeil is erger dan geen bedrag.

Het reservefonds wordt doorgerekend op precies dezelfde bedragen en hetzelfde prijspeil als het
XML-bestand.

`validate_xml` controleert elk bestand vóór het wordt weggeschreven op:

- kolommen en volgorde;
- typen;
- unieke sleutels en verwijzingen;
- of het bitpatroon past bij startjaar en cyclus;
- of het totaal gelijk is aan hoeveelheid × prijs.

De echte voorbeeldexport komt foutloos door deze controle. Met
`OPROGNOSE_SAMPLE_XML=<pad>` draait de test daarop.

Nog te verifiëren met een proefimport in OPrognose:

- of OPrognose de primaire sleutels uit het bestand overneemt of zelf nummert (`pk_base` is
  instelbaar);
- de betekenis van `han_hierarchie`, `han_blaag` en `han_fonds`;
- of `obj_saldo` en `obj_reservering` gevuld moeten worden.

## Gebruik

```
python scripts/mjop_actualisatie.py run --document DOC-010 --building-id <gebouw> --start-year 2027 \
    --opening-balance 20000 --annual-contribution 5000 [--cost-inflation 0.02] [--contribution-growth 0.02] \
    [--rebuild-value 2000000] [--last-replacement 4711=2010] [--oprognose-code 9349-2027] [--target-price-year 2027]
```

Uitvoer in `reports/actualisatie/<mjop_id>/`:

- `<mjop_id>.xml`: het OPrognose-importbestand;
- `rapport.md`;
- `plan.json`;
- `lines.json`;
- `planner_report.json`;
- `oprognose_export_report.json`;
- `reserve_fund.json`;
- `run_meta.json`.

De functies voor menselijke beslissingen per regel (`decide_planning`, `decide_price_update`) blijven
in het regelmodel bestaan. De tool gebruikt ze niet meer: de beoordeling gebeurt in OPrognose.

## Waarneming op batch 1 (ter indicatie, geen accuracy-claim)

Uit de 12 geverifieerde documenten met elementcodes komen 76 combinaties van (code, actie). Daarvan
hebben er 23 een voorstel, allemaal korte cycli (schilderwerk 6–7 jaar, reinigen 7 jaar). Geen enkele
`replace`-combinatie heeft een waarneembaar interval. Bij een 30-jaars MJOP vallen dus vrijwel alle
grote vervangingen buiten wat uit oude plannen af te leiden is. Daarom zijn de menselijke
levensduurbeslissingen het belangrijkste werk vóór gebruik.
