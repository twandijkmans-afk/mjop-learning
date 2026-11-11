# Gevelscanner 2.0 — technische handleiding

Gevelscanner 2.0 maakt van een fotoronde een **gevelinventaris**: per gevel en per fysiek kozijn de hoeveelheden, met herkomst, onzekerheid, een uitkomstklasse en bewijs.
Het is geen aparte scanner: het is een laag bovenop de bestaande fotoronde, meetkern en MJOP-brug van de MJOP Live-app (`photo_walk/ios`).

**Lees dit eerst — wat wel en niet is aangetoond**

| | Status |
|---|---|
| Pijplijnlogica (koppelen, tellen, geometrie, uitkomstklassen, contract) | gebouwd en getest op **synthetische** scènes (Swift, 52 tests) |
| App-integratie (schermen, opslag, brug, selftest) | gebouwd; gecompileerd en getest in de **simulator** (CI), **nooit op een echte iPhone gedraaid** |
| Nauwkeurigheid op echte gevels | **niet bewezen**; er zijn geen referentiemetingen. Zie `gevelscanner_2_meetplan.md` |
| Getraind herkenningsmodel (raam/deur, draaiend/vast deel, gebreken) | **niet aanwezig**; alleen de aansluiting is gebouwd |
| Automatische verwerking in het MJOP | **uit**, en in code geblokkeerd tot de pijplijn gevalideerd is |

Alle drempels zijn `PROVISIONAL_UNVALIDATED`: werkwaarden, geen acceptatiegrenzen.

## 1. Overzicht van de pijplijn

```
foto + ARKit-gegevens ─► bestaande analyse (Vision-kandidaten ► ContourOrganizer ► niveau-A-meting per waarneming)
        │                                    (ongewijzigd; ScanStore.analyze / Measurer)
        ▼
GevelscanBuilder (app)  ─ verzamelt uit de sessie ─►  GevelscanInput
        ▼
GevelscanPipeline.run  (Swift-package `Gevelscan`, alleen Foundation, deterministisch)
   A  PhotoQualityRules / FacadePlaneEstimator / FacadeCoverageRules     Capture.swift
   B  RecognitionCapability / ModelLabelMap / PartAssembler              Recognition.swift
   C  ObjectAssociator                                                   Association.swift
   D  FrameGeometryRules                                                 FrameGeometry.swift
   E  ConditionRules                                                     Condition.swift
      OutcomeRules + totalen                                             Inventory.swift
        ▼
GevelscanResult ─► schermen (GevelInventoryViews.swift)
        ▼
InventoryContractBuilder ─► `mjop_gevel_inventory_v1` ─► ProposalOutbox ─► brug ─► website (src/gevel-inventory.js)
```

Verantwoordelijkheden zijn gescheiden: capture, herkenning, associatie, geometrie, meetkwaliteit, conditie, MJOP-koppeling, opslag/bewijs en UI hebben elk een eigen bestand.
De pijplijn is een zuivere functie op waarden: zelfde invoer geeft dezelfde uitvoer (getest, ook bij omgekeerde invoervolgorde).

### Wat is hergebruikt (niet opnieuw gebouwd)
* **Meting van de buitenmaat**: `measureDepthView` (niveau A v2), `Viewpoints.combineLevelA`/`fuse`, `Status.status`, afronding en `grossAreaM2`. Gevelscanner 2.0 rekent geen maat opnieuw uit en wijzigt geen drempel. Een test (`testStatusMatchesTheExistingMeasuringCore`) bewaakt dat status en maat gelijk zijn aan `makeObject`.
* **Herkenning**: Vision-rechthoeken/-contouren + `ContourOrganizer` (buitencontour + glasvlakken), `OuterFrameSearch`.
* **Fotoronde**: `RoundState` (gevels, AR-sessie per foto, uitsluitingen, handmatige duplicaatverklaring), `Persistence`, `RoundCoordinator`.
* **MJOP**: `PhotoRoundContext` (planRef, mjopPlanId, buildingLabel, bagPandId, element, geplande gevels), `ProposalOutbox`, de brug `mjopNative`, de ene gedeelde WKWebView.
* **Kosten**: uitsluitend de bestaande JavaScript-berekeningen en kengetallen van de website. In Swift staat geen prijs en geen kostenberekening.

## 2. Onderdeel A — intelligente fotoronde (`Capture.swift`)

Per foto wordt een `PhotoCapture` vastgelegd: foto-id, gevel, AR-sessie (`worldId`), tijdstip, intrinsics, camerapose, trackingstatus, dieptebron, dieptekwaliteit, aantal ondersteunende LiDAR-kaders, beeldkwaliteit en het dominante gevelvlak.

* **Echte LiDAR of gewone foto**: `depthSource` is `LIDAR_SCENE_DEPTH` of `NONE`. Zonder LiDAR is `metricCapable` false; er komt dan geen maat, geen gevelvlak en geen dekking. Er wordt nooit een schaal uit pixels afgeleid.
* **Dieptekwaliteit** (`DepthQuality`): aandeel geldige punten (pixels met laag vertrouwen staan in de app al op NaN), mediane afstand, aandeel binnen het werkbereik van de meetkern.
* **Beeldkwaliteit** (`ImageQualityMeter`, lokaal, geen AI): scherpte (variantie van de Laplaciaan), over-/onderbelichting, en per glasvlak het aandeel bijna-witte pixels (spiegeling).
* **Gevelvlak** (`FacadePlaneEstimator`): grootste verticale vlak door de LiDAR-punten (bestaande RANSAC-fit), normaal naar de camera.
* **Actieve gevel herkennen** (`FacadeRecognizer`): een foto hoort bij een al gefotografeerde gevel als het vlak overeenkomt, alleen binnen dezelfde AR-sessie. Twee passende gevels of geen vlak geeft `nil` (geen gok). Foto's die duidelijk op een ander vlak liggen dan de rest van hun gevel worden **gemeld** (`mismatchedPhotoIds`), nooit stil verplaatst.
* **Dekking** (`FacadeCoverageRules`): de beeldhoeken van elke foto worden op het gevelvlak geprojecteerd; een raster van 25 cm telt per cel het aantal foto's. Uitvoer: gedekt aandeel, aandeel met ≥ 2 foto's, en de rastercellen (de app tekent ze). Zonder gevelvlak is de dekking **onbekend**, niet "volledig".
* **Gerichte vragen** (`CaptureRequest`): onscherp, spiegeling, te weinig of te verre diepte, slechte tracking, gaten in de dekking, object afgesneden (onderrand: *scan de onderzijde*), één standpunt, mogelijk dubbel, foto's uit verschillende sessies. Elke vraag heeft een Nederlandse aanwijzing.

Beperking: "onderzijde van de gevel" wordt alleen herkend als een kozijn tegen de onderrand van het beeld ligt; de app kent het maaiveld niet.

## 3. Onderdeel B — herkenning (`Recognition.swift`, app: `Detection.swift`)

**Wat er werkelijk herkent.** De app heeft geen getraind kozijnmodel. De herkenning is Apple Vision (algemene rechthoek- en contourzoeker) plus regels die vierhoeken ordenen tot *buitencontour + glasvlakken*. Dat is een kandidaat-generator (`DetectorDescriptor.kind = GEOMETRIC_CANDIDATE`, `validated = false`), geen AI-kozijnherkenning, en zo staat het in elk resultaat en in het contract.

| Element | Hoe | Status |
|---|---|---|
| Kozijn (buitencontour), glasvlak | Vision-kandidaten + `ContourOrganizer` | aanwezig, niet gevalideerd |
| Gevelvlak | LiDAR-vlakfit | aanwezig |
| Tussenstijl, tussendorpel | afgeleid uit de ruimte tussen glasvlakken | aanwezig (afgeleid) |
| Raam of deur, draaiend of vast deel | getraind model **of** invoer van de gebruiker | model ontbreekt; invoer in de app |
| Gevelpaneel, aansluitingen, afwerking | getraind model | ontbreekt |

`RecognitionCapability.summarize` levert deze boekhouding; `not_recognizable` reist mee in het contract en staat in het inventarisscherm.

**Model aansluiten (zonder architectuurwijziging).** Leg een Core ML-objectdetectiemodel `GevelElementDetector.mlmodelc` in de app-bundle. `CoreMLElementDetector` laadt het dan, leest versie en klassen uit de modelmetadata, en vertaalt labels via `ModelLabelMap` (bv. `window`→RAAM, `door`→DEUR, `glass`→GLASVLAK, `operable`/`draaiend`→DRAAIEND_DEEL, `fixed`/`vast`→VAST_DEEL; onbekende labels worden genegeerd). `PartAssembler.attach` hangt de detecties aan het juiste kozijn. De pijplijn gebruikt ze dan vanzelf (`MODEL_CLASSIFICATION`, hoogstens *voorlopig* zolang `validated = false`). Getest met een nagebootst model (`RecognitionTests`). Modeldetecties worden niet met de sessie bewaard; ze zijn opnieuw te berekenen uit de lokale foto.

Er is geen betaalde of externe AI-dienst toegevoegd. Foto's verlaten het toestel niet.

## 4. Onderdeel C — objectassociatie (`Association.swift`)

Doel: hetzelfde kozijn op meerdere foto's is **één object**.

1. Vergelijken kan alleen met ruimtelijk bewijs: beide waarnemingen hebben 3D-hoeken op een gemeten vlak, in dezelfde AR-sessie.
2. Zelfde vlak (normaal ≤ 15°, afstand ≤ 15 cm) en overlap van de twee rechthoeken op dat vlak (IoU ≥ 0,50, maatverhouding ≤ 1,3) ⇒ **zelfde object**.
3. Zwakke overlap (IoU ≥ 0,15 of middelpunten dicht bij elkaar) of twee sterke kandidaten op dezelfde andere foto ⇒ identiteit **UNCERTAIN**: niet samengevoegd en niet als apart geteld.
4. Niet vergelijkbaar (geen meting, onbekende of andere sessie) ⇒ **UNCHECKED**. Dat telt nooit als "geen duplicaat".
5. Zelfde foto: bijna identieke kaders (IoU ≥ 0,80) zijn één object; een kader dat voor ≥ 50 % in een ander ligt is onzeker.
6. Keuzes van de gebruiker gaan voor: gekoppelde waarnemingen (`mustLink`, uit de bestaande koppelfunctie) en afgewezen suggesties (`cannotLink`). De bestaande verklaring "alles nagelopen" maakt UNCHECKED tot `RESOLVED_BY_USER`.

**Gevolg voor hoeveelheden**: zolang een gevel een object met UNCERTAIN of UNCHECKED heeft, krijgt die gevel **geen enkel totaal** (ook geen deelsom). Dit is dezelfde regel als in `mjop_scan_proposal_v2`.

**Stabiele id**: `GO-` + 8 hexadecimalen uit (ronde-id, kleinste waarnemings-id van het object). Een extra foto verandert de id niet (getest). Voegen twee objecten later samen, dan blijft de id van het object met de kleinste waarneming.

Elke beslissing staat in `AssociationResult.decisions` (paar, soort, IoU, afstand): de koppeling is herleidbaar en reproduceerbaar.

## 5. Onderdeel D — geometrie (`FrameGeometry.swift`)

**Buitenmaat** (breedte, hoogte): de bestaande niveau-A-meting per foto (hoekstralen via intrinsics + pose, gesneden met het op LiDAR gefitte kozijnvlak), over foto's gefuseerd door de bestaande code. Herkomst `LIDAR_PLANE_MEASUREMENT`. Oppervlak = breedte × hoogte, herkomst `DERIVED_CALCULATION`. `MEASURED` vraagt ≥ 2 onafhankelijke foto's (bestaande regel).

**Indeling** (per kozijn, nooit als aparte kozijnen):
* elk herkend glascontour wordt via het gemeten kozijnvlak van díe foto omgezet naar relatieve kozijncoördinaten;
* over foto's heen worden glasvlakken samengevoegd (IoU ≥ 0,5); een glasvlak dat niet op elke foto gezien is maakt de indeling voorlopig;
* **vakken** = aantal glasvlakken; **glasoppervlak** = som; herkomst `DERIVED_SEGMENTATION_ON_MEASURED_PLANE`. Dit is nadrukkelijk **geen** directe LiDAR-meting: het contract weigert een glasoppervlak met een meetherkomst;
* **tussenstijlen/-dorpels**: tussenruimte tussen naburige kolommen/rijen glas (inclusief glaslatten en draaiend kader), herkomst `DERIVED_CALCULATION`;
* **draaiende en vaste delen**: alleen van een getraind model of de gebruiker. Zonder beide: onbekend (`GEEN_MODEL_VOOR_DRAAIENDE_DELEN`). Er wordt nooit iets uit de vorm afgeleid;
* overlappende "glasvlakken" of glas groter dan het kozijn ⇒ geen glasoppervlak.

**Onzekerheid**: de buitenmaat draagt de 1-sigma van de bestaande Monte-Carlo (ruismodel, niet gevalideerd). Het glasoppervlak krijgt een eigen sigma (schaal van het kozijn + hoekpixels + een toeslag van 2 % omdat het glas enkele centimeters achter het kozijnvlak ligt). Alle sigma's zijn een rekenmodel; ze zijn niet aan echte metingen getoetst.

Wat ontbreekt en waarom staat per waarde in `missing` (bv. `NO_DEPTH`, `ENKEL_STANDPUNT`, `GLAS_OP_EEN_FOTO`, `SPIEGELING_IN_GLAS`).

## 6. Onderdeel E — conditie (`Condition.swift`)

Er is **geen gebrekenmodel** in dit project. Elk object krijgt daarom de waarneming `NIET_BEOORDEELBAAR` met reden `GEEN_GEBREKENMODEL`. Gebouwd en getest is de laag die een toekomstig model verwerkt:

* drie soorten: `ZICHTBAAR_GEBREK` (alleen bij een **gevalideerde** herkenner en hoge score), `MOGELIJKE_INDICATIE`, `NIET_BEOORDEELBAAR` (onscherp, te donker, te weinig pixels per meter, geen schaal);
* elke waarneming draagt bronfoto, plek (contour), score, herkenner en versie;
* categorieën zijn uitbreidbaar (`DefectCategory`, het contract draagt de code als tekst);
* alleen zichtbare gebreken; geen verborgen houtrot of constructieve schade;
* **geen NEN 2767-conditiescore**: het veld `nen2767_condition_score` is in het contract altijd `null` en schema, Swift en JavaScript weigeren een waarde.

## 7. Uitkomstklassen en automatische verwerking (`Inventory.swift`, `Types.swift`)

| Klasse | Betekenis |
|---|---|
| `BETROUWBAAR_VASTGESTELD` | maat uit ≥ 2 standpunten, identiteit eenduidig, buitencontour zeker, object volledig in beeld, **én een gevalideerde pijplijn** |
| `VOORLOPIG_VASTGESTELD` | er is een resultaat; in `outcome_reasons` staat wat ontbreekt |
| `NIET_VAST_TE_STELLEN` | geen waarde (`null`), met de reden |

**Buitencontour** (`ContourEvidence`): `USER_CONFIRMED`; of `AUTO_CORROBORATED` als op ≥ 2 onafhankelijke foto's de meting een diepte-sprong op de kozijnrand vindt (terugliggend/uitstekend kozijn), er geen aanwijzing is dat het kader te groot of te klein is, en de contour herkende glasvlakken omsluit; anders `AUTO_UNCONFIRMED`. De gebruiker hoeft dus niet elk kozijn te bevestigen; een vlak in de gevel liggend kozijn of een losse rechthoek blijft voorlopig tot er bewijs is.
De bestaande poort `ContourGate` en de v2-voorstellen zijn **ongewijzigd**: daar blijft een onbevestigde automatische contour geblokkeerd.

**De schakelaar** `PipelineValidation.current` staat op *niet gevalideerd* (geometrie en herkenning). Gevolg, afgedwongen in pijplijn, contract, schema en website: geen enkel object en geen enkele gemeten of afgeleide waarde is "betrouwbaar vastgesteld", `auto_processing_allowed` is `false`, en de inventaris blijft een voorstel dat via de outbox loopt. Alleen wat de gebruiker zelf invult (draaiende delen) is `BETROUWBAAR_VASTGESTELD` met herkomst `USER_INPUT`. De schakelaar is bewust een regel code en geen instelling: hij mag pas om na de veldvalidatie (meetplan) en een besluit van de eigenaar. De tests draaien beide standen.

## 8. Koppeling aan het MJOP

### Contract `mjop_gevel_inventory_v1`
Schema: `schemas/mjop_gevel_inventory_v1.schema.json`. Swift: `MJOPIntegration/GevelInventoryV1.swift` (validatie), `Gevelscan/InventoryContract.swift` (opbouw). Gedeeld voorbeeld (door de app zelf gemaakt): `ios/Tests/GevelscanTests/Fixtures/gevel_inventory_v1_example.json`; dezelfde inhoud staat in de website-repo.

Inhoud: project (`plan_ref`, `mjop_plan_id`, `building_id`, `bag_pand_id`), `element_key`, versies van pijplijn en algoritmen, aanwezige herkenners, validatiestand, per gevel: volledigheid, dekking, zes **gescheiden** totalen, gerichte vragen en objecten; per object: klasse, uitkomst, identiteit, contourbewijs, breedte/hoogte/oppervlak, vakken, glasoppervlak, draaiende/vaste delen, glasvlakken, tussenstijlen/-dorpels, conditie, foto's, waarnemingen, herkenners, kwaliteitscodes; en per foto het bewijs (tijdstip, dieptebron en -kwaliteit, tracking, intrinsics, camerapositie en -richting in het lokale AR-stelsel, scherpte).

Elke hoeveelheid heeft dezelfde vorm: `value` (null = onbekend), `unit`, `sigma`, `origin`, `outcome`, `missing`, `partial`.

Regels (Swift, JavaScript en schema): altijd `PROPOSED` en `booking_allowed: false`; geen prijs- of kengetalvelden; onbekend is `null`; geen totaal bij mogelijke dubbeltelling; geen totaaloppervlak met onbemeten kozijnen; glas ≤ kozijn en nooit een meetherkomst; geen NEN-score; niets betrouwbaar zonder validatie.

### Brug (alleen optellend, versie blijft 1)
* Website → app: `listFacadeInventory {planRef}`. App → website: `{type: "facade-inventory", planRef, inventories: [...]}`.
* `capabilities` krijgt het extra veld `features: ["gevelscan2"]`. De website vraagt de inventaris alleen op bij een app die dit meldt.
* Ontvangst wordt bevestigd met de bestaande `ackProposals` (inventaris-id).
* Compatibiliteit: een oudere website stuurt het nieuwe bericht nooit en negeert het onbekende antwoordtype; een oudere app krijgt het nieuwe bericht niet. `mjop_scan_proposal_v2` en alle bestaande berichten zijn ongewijzigd.

### Outbox
`ProposalOutbox.Round.inventory` (optioneel; oude `outbox.json` blijft leesbaar, getest). `inventories(forPlan:)` geeft alleen afgeronde rondes van precies dat project. Een nieuwe revisie heeft een nieuw id.

### Website (`MJOP-App`, `src/gevel-inventory.js`)
Valideert opnieuw, voegt idempotent samen in `photoRound.inventories` (zit in het planobject en wordt dus met de bestaande opslag en concurrencyregels bewaard; **geen databasewijziging**, de app schrijft niets naar `saved_plans`), en koppelt aan de bestaande kozijnrijen:

| Hoeveelheid | Bestaande post (kengetal) |
|---|---|
| Draaiende delen | *Onderhoud buitenkozijnen — Draaiend raam* |
| Vaste delen | *— Vast glas* |
| Deurkozijnen | *— Deur* |
| Aantal kozijnen, kozijnoppervlak, glasoppervlak | **geen passend kengetal** in de bibliotheek: getoond ter referentie, er worden geen kosten uit afgeleid |

Een hoeveelheid wordt eerst een **bron** (`Q.addEvidence`, verandert niets) en pas na een uitdrukkelijke bevestiging van de onzekerheid de effectieve hoeveelheid (`Q.selectEvidence`). Daarna rekenen de bestaande kengetallen, btw-instellingen, steiger en indexering gewoon verder. De module bevat geen prijzen (getest).

## 9. In de app

* **Fotoronde-scherm**: knop *Gevelinventarisatie bekijken* en een korte lijst *Nog nodig voor een volledige inventaris*.
* **Gevelinventarisatie**: voortgang van de analyse; per gevel volledigheid, dekkingsraster, de gescheiden hoeveelheden met herkomst en uitkomst, gerichte vragen en de kozijnen; onderaan wat de app wel en niet herkent.
* **Kozijn**: maten met onzekerheid, indeling, zelf invullen (draaiende/vaste delen, raam of deur), bewijs (foto's met de bestaande contouren-overlay, meetmethode, herkenner, kenmerk).
* **Belasting van het toestel**: de pijplijn draait buiten de hoofdthread met lage prioriteit; per foto worden dieptekwaliteit en gevelvlak één keer berekend en hergebruikt; meerdere aanvragen worden samengevoegd; er is geen extra AR- of camerawerk. De rekentijd op een echt toestel is niet gemeten.
* **Opslag**: beeldkwaliteit en gebruikersinvoer zitten in `session.json` (optionele velden; oudere sessies blijven leesbaar). Foto's en dieptekaarten blijven waar ze waren: lokaal, bestandsbescherming, geen back-up, geen upload.

## 10. Bewijs en privacy

Elke uitkomst is herleidbaar naar object-id → waarnemingen → foto's → meetmethode, herkenner en versie. Originele foto's, dieptekaarten, hoeken en revisies blijven lokaal bewaard (bestaande opslag).
Naar de website gaat alleen de inventaris: getallen, codes, contouren van eventuele gebreken en per foto de camerakenmerken. **Geen foto's, geen dieptekaarten, geen GPS.** Camerapositie en -richting staan in het lokale stelsel van de AR-sessie (meter); de AR-sessie zelf is vervangen door een betekenisloze verwijzing (`S1`, `S2`).
Er zitten geen sleutels in de app. De ontwikkelbundel en meetdiagnose zijn ongewijzigd en blijven Debug-only.

## 11. Tests

| Laag | Waar | Wat |
|---|---|---|
| Unit (Swift) | `ios/Tests/GevelscanTests` | capture/kwaliteit/dekking (9), associatie en deduplicatie (8), geometrie/herkomst/onzekerheid/statussen (12), conditie (6), herkenning/modelaansluiting (3) |
| Integratie (Swift) | `PipelineTests` (14) | volledige ronde → objecten per gevel → contract → outbox → brugbericht; verkeerd project; oude outbox; manipulatie van het contract |
| Schema (Python) | `python/tests/test_mjop_gevel_inventory_v1.py` | app-uitvoer tegen het schema + 18 afgewezen mutaties; v2 ongewijzigd |
| Evaluatie (Python) | `python/tests/test_gevel_eval.py` | het validatiescript zelf |
| App (CI, simulator) | selftest stap 7 + workflow | de app maakt een inventaris die aan het schema voldoet; UI-tests voor het inventarisscherm en de brug |
| Website | `test/gevel-inventory.unit.spec.js`, `test/gevel-inventaris.spec.js` | contract, samenvoegen, kengetalkoppeling, bron → hoeveelheid, oudere app |

Moeilijke situaties die (synthetisch) gedekt zijn: schuine camerahoek, spiegelend glas, kozijnen direct naast elkaar, meerdere foto's per gevel, gedeeltelijke diepte, geen LiDAR, slechte tracking, onscherp/donker, afgesneden kozijn, foto's uit meerdere sessies, tegenstrijdige glasherkenning. **Niet** gedekt: echte schaduwen, echte reflecties, begroeiing, verschillende verdiepingen vanaf de straat; dat kan alleen met echte opnamen.

Lokaal draaien: `cd ios && swift test` (macOS). Op Linux compileert het package ook, op `CryptoKit` in `CaptureBundle.swift` na.
De gedeelde fixture opnieuw maken: `GEVELSCAN_WRITE_FIXTURE=<map> swift test --filter testSharedFixtureIsWhatTheAppProduces`, daarna kopiëren naar de website-repo.

## 12. Onderhoud: waar pas je wat aan

| Wijziging | Plek |
|---|---|
| Drempel | `GevelscanConfig` (één plek); documenteer en houd `PROVISIONAL_UNVALIDATED` tot er veldgegevens zijn |
| Nieuwe elementklasse of modellabel | `ElementClass`, `ModelLabelMap` |
| Nieuwe gebrekscategorie | `DefectCategory` (contract hoeft niet te wijzigen) |
| Nieuwe gerichte vraag | `CaptureRequest.Kind` + tekst; schema-enum en website-test bijwerken |
| Veld in het contract | builder + `GevelInventoryV1.validate` + schema + `src/gevel-inventory.js` + fixture (vier plekken, bewust: elke kant controleert zelf). Een brekende wijziging wordt `…_v2` |
| Pijplijn gevalideerd verklaren | `PipelineValidation.current`, na het meetplan en met een besluit van de eigenaar |

## 13. Bekende beperkingen

* De herkenning is een vormzoeker. Op echte gevels zal ze kozijnen missen en valse kandidaten geven; hoe vaak is onbekend.
* Het glasoppervlak hangt af van die herkenning en is de zwakste hoeveelheid.
* Associatie werkt alleen binnen één AR-sessie. Elke nieuwe camerastart is een nieuwe sessie; loop een gevel dus in één keer af.
* De auto-onderbouwing van de buitencontour werkt niet voor kozijnen die vlak in de gevel liggen.
* De dekking is relatief aan wat gefotografeerd is (omhullende rechthoek van de foto's); de app kent de werkelijke gevelafmeting niet.
* Verschillende verdiepingen: LiDAR reikt ongeveer 5 m. Hogere kozijnen krijgen vanaf de straat geen maat (`DEPTH_RANGE_EXCEEDED`), wel een telling als ze herkend worden.
* Modeldetecties worden niet bewaard; na hervatten van een ronde moeten foto's opnieuw door het model (alleen relevant zodra er een model is).
