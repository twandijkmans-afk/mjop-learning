# Automatic Photo-to-Quantity v2 — foto → kaders → voorlopige maten

## Workflow (iPhone)
1. **Foto-scan starten** → camera met één fotoknop, pinch-to-zoom, zoomindicator, 1×/2×/4× en slider (visuele zoom van de voorvertoning; raakt ARKit, intrinsics en LiDAR niet aan).
2. **Foto maken**: tegelijk worden het originele camerabeeld (JPEG, volledig onvergroot), de intrinsics, de camerapose (camera→wereld), de trackingstatus en — indien beschikbaar — de LiDAR-dieptekaart (`depth_z`, Float32) vastgelegd. Brondata wordt nooit overschreven.
3. **Automatische herkenning (lokaal)** → kandidaat-kozijnen → kaders op de originele foto → per kozijn een voorlopig object-ID (`PROV-…`, in de app als K1, K2, …).
4. **Meting** via de bestaande meetkern (niveau A: vlak uit de omringende LiDAR-gevel; terugval niveau C: één referentiemaat). Maat, bruto m² en onzekerheid worden direct bij het kader getoond; zonder betrouwbare schaal staat er `UNKNOWN`.
5. **Overzicht onder de foto**: herkende kandidaten, voorlopig unieke kozijnen, bruto m² waar meetbaar (per status, niet opgeteld tot totaal), controles (oranje), zonder maat (grijs), koppelsuggesties.
6. Tik op een kader → ingezoomd detail: hoeken verslepen/corrigeren, **één referentiemaat** toevoegen, hoeken bevestigen, "geen kozijn" (afwijzen; lokaal bewaard, telt niet mee), koppelen aan een kozijn van een andere foto.

## Welke herkenning is daadwerkelijk geïmplementeerd?
| Onderdeel | Status |
|---|---|
| **Apple Vision `VNDetectRectanglesRequest`** (on-device) als kandidaat-generator | **Geïmplementeerd.** Een algemene rechthoekdetector: vindt ook deuren, borden, steenpatronen, schaduwen en mogelijk de glasruit i.p.v. het kozijn. Daarom alleen *kandidaten*; elke kandidaat heeft `AUTO_DETECTED_UNCONFIRMED` en `CANDIDATE_UNVERIFIED`. Filtering: te klein/te groot/niet-convex weg, overlap (IoU > 0,55) en binnenvakken (> 85 % binnen een grotere, niet-gevelgrote kandidaat) worden ontdubbeld waarbij de grotere (buitenmaat) blijft. |
| **Core ML-kozijnmodel** | **Haak aanwezig, geen model.** Staat er een `WindowDetector.mlmodelc` (objectdetectie, klasse window/kozijn/raam) in de app-bundle, dan wordt het gebruikt en wordt de uitvoer samengevoegd met de rechthoekdetector. Er is **geen model meegeleverd**: er zijn geen gelabelde kozijnbeelden van Nederlandse gevels in deze repository, en een extern model downloaden of beelden uploaden is niet toegestaan zonder jouw toestemming. |
| Handmatige selectie | Fallback blijft: "Kozijn handmatig toevoegen" (vier hoeken tikken op de ingezoomde foto) en hoeken slepen in het detail. |
| Andere iOS-opties onderzocht | `VNDetectContoursRequest` (contouren; zou meer ruis geven), `VNClassifyImageRequest` (scène-labels, geen locaties), RoomPlan (ontworpen voor binnenruimtes; niet voor gevels geverifieerd) — niet gebruikt. |

Verbeterpad voor kwaliteit: met toestemming de door de inspecteur bevestigde/gecorrigeerde hoeken en afgewezen kandidaten (de app bewaart die lokaal) verzamelen als trainingsdata, een objectdetectiemodel trainen (Create ML) en als `WindowDetector.mlmodelc` toevoegen.

## Kaderkleuren (alleen UI-feedback, géén goedkeuring)
* **Groen** — meting gelukt en geen controle-waarschuwing (glas, hoekdiepte, coplanariteit, …). Blijft voorlopig, onbevestigd en niet gevalideerd.
* **Oranje** — controle nodig: meting met waarschuwing, of twijfel aan hoeken/geometrie (geen rechthoek op het vlak, gemengde gevelvlakken, schuine hoek, …).
* **Neutraal (grijs)** — geen betrouwbare schaal/diepte (geen LiDAR, trackingverlies, te weinig diepte, geen referentie): de maat is `UNKNOWN`.
Implementatie: `PhotoWalkCore/Feedback.swift` (getest). De kleur komt nooit in het contract of de status terecht.

## Meetketen en eerlijkheid over schaal
Metrisch alleen via: (A) LiDAR-gevelvlak rond het kozijn + hoekstralen met de originele intrinsics, of (C) een door de inspecteur ingevoerde referentieafstand op hetzelfde vlak. Zoom verandert geen enkele invoer (originele pixels). Een enkele foto geeft nooit `MEASURED` (één standpunt ⇒ `ESTIMATED`); `AUTO_DETECTED_UNCONFIRMED` sluit `MEASURED` ook uit. Een referentie op één kozijn geldt voor andere kozijnen op dezelfde foto alleen met de aanname dat ze coplanair zijn (`COPLANARITY_ASSUMED` ⇒ oranje).

## Koppelen over foto's (geen automatische samenvoeging)
Waarnemingen met een meting krijgen suggesties als ze op hetzelfde vlak liggen (normaal ≤ 15°, offset ≤ 15 cm), nabij zijn (≤ 0,5 × kleinste afmeting), vergelijkbare maat hebben en uit verschillende foto's komen; onduidelijke gevallen krijgen geen suggestie. Een koppeling gebeurt **alleen op knop** (en kan ongedaan worden gemaakt). Elke waarneming hoort bij precies één voorlopig object ⇒ geen dubbele kozijnoppervlakken; "voorlopig unieke kozijnen" telt voorlopige objecten (suggesties tellen niet mee tot je koppelt, dus dat getal kan te hoog zijn).

## Lokale opslag en export
* Opslag: `Application Support/PhotoWalk/<sessie>/` met `session.json`, `F000.jpg`, `F000.depth` (ongewijzigde dieptekaart); uitgesloten van back-up, bestandsbescherming, geen iCloud/netwerk. *Laatste scan hervatten* op het startscherm. Bestandsnamen zijn relatief (overleeft herinstallatie van de app niet automatisch: bij verwijderen van de app verdwijnen de gegevens).
* Export (knop *Exporteren*): `photo_walk_capture_v1` **1.1.0** (JSON in Documents → Bestanden-app) met o.a. `capture_mode`, per waarneming `detection` (detector, score, `CANDIDATE_UNVERIFIED`), `rejected_candidates`, `detection_summary` (`validated_on_real_buildings: false`). Het schema blijft gesloten; 1.1.0-velden zijn optioneel (v1.0.0-records blijven geldig).
* **Naar de bestaande hoeveelheidsmodule** (Bruto Quantity Model v2): `python -m photo_walk_core.to_bruto export.json uit.json` maakt `bruto_observation_v2`- en `bruto_quantity_object_v2`-records (gevalideerd met de bestaande v2-schema's en rekenkern), met **alle maten UNKNOWN** (geen geforceerde statussen; MEASURED is in v2 een menselijke meting) en de voorgestelde maten in `sensor_proposals` voor menselijke intake. Geen FI-id's, geen goedkeuringen, geen kosten; nooit in de laag CONFIRMED.

## Nog niet gevalideerd op echte gebouwen (fysieke validatie nodig)
Kwaliteit en recall van de rechthoekdetector op echte gevels (verwacht: veel gemiste en valse kandidaten), of de gevonden vierhoek de buitenmaat of de glasruit is, LiDAR-vlakfit rond echte kozijnen, de tolerantie van de maten (alle drempels `PROVISIONAL_UNVALIDATED`), prestaties met veel kandidaten, bruikbaarheid van de kleuren in zonlicht, gedrag van de koppelsuggesties bij repeterende kozijnen, opslag/herstel na app-update.
In de simulator is alleen een **synthetische** foto (getekende gevel met één kozijn + synthetische diepte) getest: Vision vond daar 3 kandidaten waarvan 1 een maat kreeg (1,232 × 1,54 m op een ware 1,2 × 1,5 m, door de witte kozijnrand in het testbeeld) — dat bewijst de keten, niet de herkenning op echte gevels.
