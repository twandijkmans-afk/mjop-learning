# MJOP Live in de iPhone-app — fase 1

> **Fase 2 (deze versie):** de schakelaar Mijn MJOP | Gevelscanner is verwijderd. Zie [Fase 2: één interface](#fase-2-één-interface-fotoronde-in-mijn-mjop) onderaan. Fase 1 hieronder is de basis (WebView, veiligheid, foutafhandeling).

De app (bundle `nl.mjop.photowalk.prototype`, weergavenaam **MJOP Live**) toont de bestaande website in één `WKWebView` (`App/Sources/MJOP/`, geen herimplementatie in Swift). De native Photo Walk (ARKit/LiDAR, fotoherkenning, resultaten, meetdiagnose) is een functie van die interface geworden: een **fotoronde** of een **scan vanuit een onderhoudspost** opent de camera schermvullend en keert terug naar hetzelfde scherm in Mijn MJOP. De WebView blijft de hele tijd bestaan, dus webstaat en niet-opgeslagen invoer gaan niet verloren.

## Wat is onderzocht (en hoe sterk is het bewijs)

Bron: statische analyse van `twandijkmans-afk/MJOP-App` (branch `claude/mjop-live-implementation-smz60g`, commit `5319617`) en van deze repository. **Niets hiervan is op een echte iPhone uitgevoerd.** De live-URL `https://twandijkmans-afk.github.io/MJOP-App/` (afgeleid uit `README.md` en `deploy-pages.yml` van de website) was vanuit de ontwikkelomgeving **niet bereikbaar** (netwerkbeleid van de sandbox, HTTP 403); of de site daar nu daadwerkelijk draait is dus **niet geverifieerd**.

| Websitefunctie | Bevinding uit de code | In WKWebView | Status |
|---|---|---|---|
| Mobiele navigatie | `<meta viewport>`, onderste tabbalk (`.tab-bar`), marketing-gate alleen ≥ 960 px | werkt zoals in Safari; de app zet geen eigen onderbalk om dubbele balken te vermijden | handmatig te testen |
| Adres opzoeken | `fetch` naar PDOK/BAG/3D BAG/CBS (CORS-open, sleutelloos) | werkt in WebView (alleen subresource-verkeer; niet door de domeinbeperking geraakt) | handmatig te testen |
| Opslag van sessie | supabase-js bewaart sessie in `localStorage`; werkplan in `sessionStorage` | `WKWebsiteDataStore.default()` is persistent; `sessionStorage` leeft zolang de WebView-instantie leeft (we houden hem in leven) | handmatig te testen |
| **Magic link** | `signInWithOtp({emailRedirectTo: https-pagina})`; de e-maillink opent in **Safari**, niet in de app. De sessie ontstaat dan in Safari's opslag, niet in de WebView | **werkt niet vanzelf** — zie "Inloggen" hieronder | gedocumenteerd, vereist webwijziging |
| Opgeslagen MJOP's | tabel `saved_plans` met RLS, via supabase-js | ongewijzigd, zodra er een sessie in de WebView is | handmatig te testen |
| Import xlsx/csv/pdf | `<input type=file>` + FileReader + SheetJS/pdf.js (CDN, met SRI) | bestandskiezer werkt in WKWebView; CDN-scripts hebben internet nodig | handmatig te testen |
| CSV-export en "mijn gegevens" | `Blob` + `<a download>` | WKWebView doet dit niet vanzelf; de app vangt het af als `WKDownload` en toont het deelblad (Bewaar in Bestanden) | handmatig te testen (blob-downloads zijn het meest kwetsbaar) |
| PDF-rapport | `window.print()` (+ `@media print`) | `window.print()` doet in WKWebView niets; de app injecteert een shim die de native afdrukdialoog opent (daar: *Bewaar als PDF / Deel*) | handmatig te testen |
| Nieuwe vensters / `target=_blank` | geen `_blank`-links in `app.js` | afgehandeld: binnen de site in dezelfde WebView, anders Safari | geautomatiseerd (beleid) |
| JS-dialogen | geen `alert/confirm/prompt` in `app.js` | toch ondersteund via UIAlertController (WKWebView toont ze anders niet) | — |

## Veiligheid

* **Domeinbeperking** (`WebNavigationPolicy`, getest): alleen `https://twandijkmans-afk.github.io/MJOP-App/…` (met padvoorvoegsel — andere Pages-projecten op dat domein dus niet) en `https://<supabase-project>/auth/v1/…` worden in de app geladen. Andere https-links: pas na een tik naar Safari; automatische doorverwijzingen, `http:`, `file:`, `javascript:`, `data:`, vreemde iframes en onbekende schema's worden geblokkeerd, met een melding.
* Subresources (CDN's, PDOK, Supabase REST) worden niet beperkt — dat doet een navigatiedelegate niet. Het script-kanaal naar de app (`window.webkit.messageHandlers.mjopNative`) accepteert alleen de actie `print` en alleen van de eigen site.
* Geen geheimen in de app. De Supabase-URL en de publieke anon-sleutel staan uitsluitend in de website (`src/config.js`); de app bevat alleen het publieke projectadres voor de padbeperking. RLS blijft de enige toegangscontrole; er is geen tweede database of rekenkern.

## Inloggen via magic link — ontwerp en wat daarvoor nodig is

Probleem: de link in de e-mail opent in Safari. Een sessie in Safari is niet beschikbaar in de app-WebView. Tokens van Safari naar de app kopiëren is onveilig en wordt **niet** gedaan.

Ontworpen route (PKCE, alleen een eenmalige code reist mee):

1. In de app vraagt de website (in de WebView) de link aan. supabase-js bewaart de **code-verifier** in de WebView-opslag.
2. De e-maillink gaat via Supabase naar een kleine brugpagina op de website (`…/MJOP-App/app-callback.html?code=…`), geopend in Safari.
3. De brugpagina stuurt door naar `mjoplive://auth-callback?code=…`; iOS vraagt "Openen in MJOP Live?".
4. De app (`AuthCallback.parse`, getest) accepteert **alleen** een plausibele `code` — tokens in de URL, extra parameters of een ander pad worden geweigerd — en laadt `…/MJOP-App/?code=…` in de WebView. supabase-js wisselt de code in met de verifier die al in die WebView staat. Een onderschepte code is zonder verifier nutteloos.

**Dit werkt pas na een aparte wijziging aan de website en Supabase** (niet in deze PR; website-PR: [MJOP-App#13](https://github.com/twandijkmans-afk/MJOP-App/pull/13), draft):

* website: in de app (herkenbaar aan `MJOPLiveApp/1` in de User-Agent) `flowType: 'pkce'` gebruiken en `emailRedirectTo` op de brugpagina laten wijzen; de brugpagina `app-callback.html` toevoegen;
* Supabase → Authentication → URL Configuration → **Redirect URLs**: `https://twandijkmans-afk.github.io/MJOP-App/app-callback.html` toevoegen.

Zolang dat niet gedaan is: inloggen kan in de app wel aangevraagd worden, maar de link voltooit de sessie in Safari (de bestaande website-flow is ongewijzigd). Universal Links zijn geen alternatief: ze vereisen een betaald Apple-account (Associated Domains) en een `apple-app-site-association` op het domeinrootniveau (`twandijkmans-afk.github.io/`), dat niet bij dit project hoort. Een zescijferige e-mailcode zou een wijziging van het Supabase-e-mailsjabloon vergen (zonder eigen SMTP niet aanpasbaar volgens de website-README).

## Foutafhandeling

`WebLoadFailure` (getest) vertaalt `NSURLError`-codes en HTTP-statussen naar Nederlandse meldingen: offline (met knop naar de Gevelscanner — die werkt zonder internet), time-out, niet bereikbaar, TLS-fout, HTTP ≥ 400, geblokkeerde link. Een offline-banner verschijnt zodra de verbinding wegvalt (`NWPathMonitor`); komt de verbinding terug na een offline-fout, dan wordt automatisch opnieuw geladen. Wordt het WebView-proces door iOS beëindigd (geheugen), dan herlaadt de app en meldt dat; niet-opgeslagen invoer kan dan verloren zijn.

## Toekomstig contract: scanvoorstel `mjop_scan_proposal_v1`

Schema: `schemas/mjop_scan_proposal_v1.schema.json`; Swift: `Sources/MJOPIntegration/ScanProposal.swift`; gedeeld voorbeeld: `ios/Tests/MJOPIntegrationTests/Fixtures/scan_proposal_v1_example.json` (door zowel de Swift- als de Python-tests gebruikt; CI valideert daarnaast een door de app zelf gecodeerd voorstel tegen het schema).

Velden: projectidentificatie (`mjop_plan_id` = `saved_plans.id`, `building_id`, `facade_id`, `bag_pand_id`), elementtype (+ optionele `mjop_element_key` uit `ELEMENT_LIBRARY`), afmetingen/hoeveelheid (`unit` m2/m1/st sluit aan op `Q.UNIT_LABELS` van de website), meetmethode, `dimension_status`, onzekerheid (`validated`, `area_sigma_m2`), bronfoto-ID + `PROV-`-ID, en bevestigingsstatus.

Regels (afgedwongen en getest):
* `booking_allowed` is in v1 altijd `false`; een voorstel is nooit een boeking. Geen prijzen of kengetallen in het contract — kosten blijven bij de bestaande kengetallenbibliotheek van het MJOP.
* Start altijd als `PROPOSED`. `CONFIRMED_BY_USER` kan alleen via een expliciete gebruikershandeling met tijdstip.
* Een maat is **onzeker** zolang `dimension_status` ≠ `MEASURED` of de onzekerheid niet gevalideerd is (nu: altijd, `PROVISIONAL_UNVALIDATED`). Bevestigen van een onzekere maat vereist `uncertainty_acknowledged = true`; `UNKNOWN`/ontbrekende waarde is nooit bevestigbaar.
* Versie zit in `contract` (`…_v1`); een andere versie wordt bij het decoderen geweigerd (geen stil half-begrijpen). Het schema is gesloten (`additionalProperties: false`).
* Aansluiting op de hoeveelheidssystematiek: bij het inlezen in het MJOP wordt dit een hoeveelheidsobject met `status = PROPOSED`; een nieuwe bron (bijv. `PHOTO_WALK_SCAN`) naast `Q.SOURCES` is een webwijziging voor fase 2. Een handmatige waarde wordt daarbij — zoals nu — nooit overschreven.

Het transportkanaal (hoe het voorstel naar de WebView gaat) is bewust nog niet gebouwd; voorstel: een `postMessage`-brug met dezelfde afzender- en actiebeperking als `mjopNative`.

## Wat is automatisch getest, en wat niet

Automatisch (CI, `.github/workflows/photo-walk-ios.yml` en `photo-walk-tests.yml`): Swift-build en -tests van `PhotoWalkCore` en `MJOPIntegration` (navigatiebeleid, foutclassificatie, auth-callback, bestandsnamen, sectiekeuze, scanvoorstel), Python-tests (inclusief schema van het scanvoorstel), simulator-UI-tests (wisselen tussen Mijn MJOP en scanner met behoud van webstaat en scannerpositie, offline- en serverfoutscherm), headless selftest van de scanner, schema-validatie van door Swift gecodeerde uitvoer, controle dat de scanner geen netwerkcode bevat.

**Nog handmatig op een echte iPhone te testen** (niet automatisch aangetoond): inloggen met magic link (en pas na de webwijziging/Supabase-configuratie), sessiebehoud na herstart, opgeslagen MJOP's openen/opslaan/synchroniseren, adres opzoeken via BAG/3D BAG, import van Excel/PDF/CSV via de bestandskiezer, CSV-export (blob-download → deelblad), PDF-rapport via de printdialoog, bestanden delen, terugkeren naar de scanner, camera-hervatting na wisselen, LiDAR/ARKit zelf (sowieso alleen op een toestel). **Er wordt dan ook geen volledige functiepariteit geclaimd.**


---

# Fase 2: één interface, Fotoronde in Mijn MJOP

## 1. Inloggen vanuit de app — oorzaak en definitieve activering

**Waarom de link nu naar de website leidt (vastgesteld):** de productiesite wordt gedeployd door `deploy-pages.yml` bij een push op `claude/mjop-live-implementation-smz60g`. De laatste deploy (run #115) is commit `5319617` (Merge PR #12). **Website-PR #13 is nooit gemerged**, dus productie kent de app niet: de aanvraag gebruikt `emailRedirectTo = …/MJOP-App/` en de e-maillink opent als gewone website in Safari — de sessie ontstaat in Safari, niet in de WebView van de app. (De live-URL zelf was vanuit mijn ontwikkelomgeving niet bereikbaar, HTTP 403 van de sandbox-proxy; bovenstaande volgt uit de deploy-geschiedenis, niet uit een bezoek aan de site.)

**Ontwerp (PKCE, geen tokens in URL's):**
1. In de app vraagt de website (WebView, User-Agent `MJOPLiveApp/1`) de link aan met `flowType: 'pkce'`; supabase-js bewaart de *code-verifier* in de localStorage van de WebView (blijft na afsluiten bestaan).
2. De e-maillink gaat via Supabase naar `…/MJOP-App/app-callback.html?code=…` (brugpagina, Safari).
3. De brugpagina opent `mjoplive://auth-callback?code=…` (automatisch + knop **Open MJOP Live**). Kan dat niet (ingebouwde e-mailbrowser): knop **Kopieer inlogcode** en in de app menu **••• → Inloglink of code plakken**.
4. De app accepteert alleen een plausibele code (`AuthCallback`/`AuthPaste`, getest; tokens, extra parameters en vreemde hosts worden geweigerd) en laadt `…/MJOP-App/?code=…` in de WebView; supabase-js wisselt in met de verifier die daar al staat. Een afgevangen code is zonder verifier nutteloos.
5. Sessiebehoud: supabase-js bewaart de sessie in de persistente `WKWebsiteDataStore.default()`; opgeslagen MJOP's (`saved_plans`, RLS) laden met het toegangsbewijs van de sessie. (Aangetoond in de browser-e2e met nagebootst Supabase; **niet** op een echte iPhone.)

**E-mailapps en linkscanners.** Sommige e-mailapps openen links in een ingebouwde browser (custom-scheme dan vaak geblokkeerd → daarom de knop, de kopieerknop en het plakmenu). Virus-/linkscanners kunnen de *e-mailtoken* (Supabase `/auth/v1/verify`) vooraf openen en verbruiken: de gebruiker ziet dan `otp_expired`; de app toont daarvoor een Nederlandse uitleg ("vraag een nieuwe link aan en open die direct in Safari"). De PKCE-code in de brugpagina zelf kan een scanner niet verbruiken. Wie scanners structureel wil uitsluiten: optioneel het e-mailsjabloon omzetten naar een bevestigingspagina met knop (token_hash + `verifyOtp`) — **niet gebouwd** en niet nodig om te beginnen; vergt een sjabloonwijziging in Supabase.

### Checklist — wat jij zelf moet doen (ik heb niets gemerged of in productie gewijzigd)
1. [ ] **Merge de website-PR's in volgorde** (alle vier zijn draft): [#13](https://github.com/twandijkmans-afk/MJOP-App/pull/13) → [#14](https://github.com/twandijkmans-afk/MJOP-App/pull/14) → [#15](https://github.com/twandijkmans-afk/MJOP-App/pull/15) → [#16](https://github.com/twandijkmans-afk/MJOP-App/pull/16). Elke merge naar `claude/mjop-live-implementation-smz60g` deployt naar GitHub Pages. (Alleen de inlogfix? merge #13 + #14. Alleen het toetsenbord? #15 hangt in de keten, maar is inhoudelijk onafhankelijk.)
2. [ ] **Supabase → Authentication → URL Configuration → Redirect URLs**: voeg exact toe `https://twandijkmans-afk.github.io/MJOP-App/app-callback.html`. (Zonder deze regel valt Supabase terug op de Site URL en kom je weer op de website uit.) Laat de bestaande regel `https://twandijkmans-afk.github.io/MJOP-App/` staan: de gewone website blijft die gebruiken.
3. [ ] **Site URL** laten staan op de website (`https://twandijkmans-afk.github.io/MJOP-App/`).
4. [ ] Controleer na de deploy in Safari dat `https://twandijkmans-afk.github.io/MJOP-App/app-callback.html` laadt en "Deze inloglink is niet geldig" toont (bewijst dat #13 live staat).
5. [ ] Geen wijziging nodig aan RLS, tabellen, sleutels of e-mailsjabloon. (Gebruik je een eigen SMTP-provider met een eigen sjabloon: de link moet `{{ .ConfirmationURL }}` blijven gebruiken.)
6. [ ] Installeer de nieuwe IPA (zelfde bundle-ID; de bestaande WebView-opslag blijft behouden) en test op de iPhone:
   - Vraag in de app een inloglink aan → open de mail **op dezelfde iPhone** → tik op de link → Safari toont de brugpagina en vraagt "Openen in MJOP Live?" (of tik op **Open MJOP Live**) → je bent ingelogd, je account en opgeslagen MJOP's staan er.
   - Opent de app niet (e-mailapp met ingebouwde browser)? Kopieer de code (**Kopieer inlogcode**), open MJOP Live, menu ••• → **Inloglink of code plakken**.
   - Sluit de app volledig af (veeg omhoog) en open hem opnieuw: je blijft ingelogd.

## 2. Toetsenbordbug — bewezen oorzaak en oplossing

Zie website-PR [#15](https://github.com/twandijkmans-afk/MJOP-App/pull/15). Kort: `render()` vervangt de volledige `root.innerHTML` na **elke toetsaanslag** (globale `input`-handler) én bij **elke resize** (iOS wijzigt de venstermaat zodra het toetsenbord opent of van ABC naar 123 wisselt). Het veld waarin je typt wordt daardoor vernietigd en als nieuw element gefocust; iOS gooit de toetsenbordstand weg. Bewezen met een reproductietest op de oude code (13 van 15 controles faalden: het element is al na het eerste teken een ander DOM-element, ook na een resize) en dezelfde test groen na de fix. Opgelost met een DOM-patch (`src/dom-patch.js`) die het actieve veld ongemoeid laat, en een `resize`-listener die alleen nog rendert bij een echte schermwissel. Dit geldt voor de gewone mobiele website én de app (zelfde code).

**Op een echte iPhone testen (Safari én MJOP Live):** open achtereenvolgens het adresveld, e-mail en wachtwoord (inlogscherm), "Reservefonds nu", "aantal appartementen" en een hoeveelheid/tarief bij een post. Typ een paar tekens, tik op **123**, typ cijfers, tik terug op **ABC**. Verwacht: het toetsenbord blijft in de gekozen stand, de cursor springt niet naar het begin, de tekst blijft staan en het Overzicht rekent live mee. Controleer ook: het veld "Reservefonds" na verlaten (blur) toont de genormaliseerde waarde.

## 3. Fotoronde — hoe het werkt

**Eén systeem.** De website blijft de MJOP-interface en rekenkern; Swift/ARKit/LiDAR blijft de scanner. Ze praten via een smalle, gevalideerde brug.

**Brug (`window.webkit.messageHandlers.mjopNative`, versie 1).** Website → app: `startPhotoRound`, `startElementScan`, `listProposals`, `ackProposals`, `getCapabilities` (en de oude `print`). Elk bericht heeft `v`, `action`, `requestId` en een `payload`; de app controleert: afzender (hoofdframe op het eigen domein), versie, actie, requestId-formaat, maximale grootte (20 kB) en de volledige projectcontext (`planRef`, gebouwlabel, BAG-pand (16 cijfers), post-sleutel, eenheid, ≤ 20 geplande gevels met geldige windrichting). Ongeldig → genegeerd met een melding. App → website: `window.MJOPNativeBridge.receive({v:1,type:'proposals'|'capabilities'|'round-status'|'error',…})`, **alleen naar een pagina op het eigen domein**; de website controleert opnieuw type, versie, `planRef` en elk voorstel tegen het contract.

**Projectkoppeling.** De website maakt per plan een `planRef` (staat in het plan en wordt mee opgeslagen). De app bewaart die bij de ronde; voorstellen dragen `project.plan_ref`. Een voorstel voor een ander project wordt door de website nooit toegepast; de app biedt per `planRef` alleen eigen, afgeronde rondes aan.

**Een ronde (tab Fotoronde, of knop Scannen met camera bij een post).**
1. Website: *Fotoronde starten* (of *Scannen met camera* bij *Onderhoud buitenkozijnen*; context bevat dan de post en eenheid `st`). De app opent schermvullend; bestaat er al een ronde voor dit project, dan kies je *Hervatten/Aanvullen* of *Nieuwe ronde*.
2. Gevels toevoegen (naam + windrichting waar bekend; vooraf genoteerde gevels van de website staan er al). Per gevel *Foto's maken*: bestaande camera, LiDAR en kozijnherkenning; per foto verschijnen herkende kozijnen met voorlopige maat. Per foto: foutieve detectie uitsluiten (*Geen kozijn*), ontbrekend kozijn handmatig toevoegen, hoeken corrigeren/bevestigen, referentiemaat, meetdiagnose — ongewijzigd bestaande functies.
3. *Overzicht en controle*: voorstellen (live berekend), mogelijke duplicaten, foto's per gevel, en per foto **Niet meetellen (overlapt met andere foto)**.
4. *Onderbreken en bewaren* (lokaal, ook na afsluiten) of *Afronden en naar Mijn MJOP sturen*. Je komt terug op het scherm waar je begon.

**Niet dubbel tellen.** Dezelfde kozijnen op meerdere foto's worden voorgesteld als koppelsuggestie (zelfde vlak/maat/positie) en pas gekoppeld op jouw bevestiging. Dat werkt alleen binnen één AR-sessie: elke camerastart reset tracking en geeft een eigen coördinatenstelsel (`worldId`), foto's uit verschillende sessies zijn niet vergelijkbaar. Daarom krijgt een voorstel `CROSS_SESSION_UNCHECKED` als een gevel foto's uit meer dan één sessie heeft, en `DUPLICATES_UNRESOLVED` voor openstaande suggesties. Totalen tellen alleen uniek, niet-uitgesloten kozijnen; uitgesloten kozijnen en foto's staan in `basis.excluded_objects`.

**Voorstellen (`mjop_scan_proposal_v2`, uitbreiding op v1; v1 blijft geldig).** Per ronde: *Aantal kozijnen* (st) en *Bruto kozijnoppervlak* (m²), voor het gebouw en (bij meerdere gevels) per gevel. Materiaal wordt niet voorgesteld (de scanner ziet het niet betrouwbaar). Regels, afgedwongen in Swift, JavaScript en schema:
- altijd `PROPOSED`, `booking_allowed:false`; geen prijzen/kengetallen;
- onbekend = `null`, nooit 0; een oppervlak wordt **niet** gepubliceerd zolang kozijnen zonder maat meetellen (dan alleen `partial_value`, informatief); de slechtste maatstatus telt;
- `reliability`: `CHECK_REQUIRED` of `INCOMPLETE` met redenen (`UNVALIDATED_LIDAR` altijd, `UNMEASURED_OBJECTS`, `DUPLICATES_UNRESOLVED`, `CROSS_SESSION_UNCHECKED`, `AUTO_DETECTED`, `NO_OBJECTS`);
- `revision`: opnieuw afronden/aanvullen geeft een nieuwe revisie met nieuwe id's; de website vervangt alleen een *onbeslist* voorstel.

**In het MJOP (website).** Detectie → Meting → Voorstel → Bevestiging → Effectieve hoeveelheid zijn zichtbaar gescheiden. Een voorstel komt als **bron** (`PHOTO_WALK_SCAN`, "Fotoronde (voorstel)") naast de bestaande hoeveelheid (`Q.addEvidence`): waarde, status en kosten veranderen niet. Je kunt de waarde corrigeren (oorspronkelijke waarde blijft bewaard), een post kiezen (kozijnrij; het totaal komt op één rij en je verdeelt zo nodig zelf), en pas daarna *Gebruik als hoeveelheid* — met verplichte bevestiging dat het een voorlopige, niet-gevalideerde LiDAR-meting is (`Q.selectEvidence` weigert anders). Staat er een **handmatige waarde**, dan is een extra uitdrukkelijke keuze nodig en blijft die waarde als bron bewaard. Daarna rekenen de bestaande kengetallen en kosten gewoon verder; er worden geen dubbele posten of kosten aangemaakt (de bron hangt aan een bestaande kozijnrij). Oppervlak (m²) is bruto kozijnoppervlak en wordt niet automatisch in een buitenmuur-post gebruikt (andere definitie); het kan als referentie bewaard worden.

**Offline en synchronisatie.** Een ronde en de afgeronde voorstellen worden lokaal bewaard (Application Support, bestandsbescherming, geen back-up) en bij elke vraag opnieuw aangeboden; de website voegt idempotent samen en laat bestaande beslissingen staan. Zo gaat niets verloren als de website-staat verdwijnt voordat het plan is opgeslagen. De website markeert voorstellen als *alleen op dit toestel* zolang het plan niet is opgeslagen; de app toont per ronde of ze zijn overgedragen. Voorstellen zitten in het bestaande planobject en dus in `saved_plans` (RLS) — **geen databasewijziging**.

**Gewone website (geen app).** Tab Fotoronde legt uit dat de LiDAR-scanner op de iPhone zit en biedt een *inspectievoorbereiding* (gevels noteren; wordt met het plan bewaard en in de app voorgesteld). Geen kapotte scanknoppen. Een foto-upload zonder LiDAR is bewust niet gebouwd: zonder schaalbron zijn maten onbetrouwbaar (`UNKNOWN`).

**Wat nog bestaat van de oude scanner.** Menu ••• → *Scanner-testmodus (zonder project)* opent de losse Photo Walk (LiDAR-/meetdiagnose); geen hoofdnavigatie.

## 4. Automatisch getest vs. handmatig op de iPhone

Automatisch (CI): Swift (brugberichten, contextvalidatie, v2-contract, voorstelbouwer incl. dubbele/uitgesloten/onbemeten/meerdere gevels, outbox met verkeerd project en idempotentie, AuthPaste/foutmapping, navigatiebeleid), Python (schema v1/v2), XCUITest in de simulator (geen schakelaar meer; fotoronde starten **via de echte brug**; terugkeer met behoud van webstaat; element-context; ongeldig bericht geweigerd; offline/foutschermen; scanner-testmodus), selftest (door Swift gemaakte v2-voorstellen valideren tegen het schema), website: Node-unit (5 bestanden) en Playwright (18 bestanden) (inloggen/PKCE/sessie, toetsenbord, dom-patch, fotoronde, bestaande kwantiteit-/inventaristests).

**Alleen op een echte iPhone te controleren** (niet aangetoond): inloggen via e-mail en terugkeer in de app; sessiebehoud na afsluiten; het toetsenbordgedrag (123/ABC); camera, LiDAR en kozijnherkenning in een echte ronde; het schermvullend openen/sluiten van de scanner vanuit de WebView; hervatten van een onderbroken ronde na afsluiten van de app; of voorstellen in de website verschijnen na afronden; synchronisatie van het plan met voorstellen (opslaan, heropenen op een tweede apparaat); Excel/PDF-import, CSV-/PDF-export, delen. Er wordt geen functiepariteit geclaimd.
