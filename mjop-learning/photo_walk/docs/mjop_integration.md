# MJOP Live in de iPhone-app — fase 1

De app (bundle `nl.mjop.photowalk.prototype`, weergavenaam **MJOP Live**) heeft twee onderdelen, te kiezen met de schakelaar bovenin:

| Onderdeel | Wat | Techniek |
|---|---|---|
| **Mijn MJOP** | de bestaande mobiele website (BAG/3D BAG, onderhoudselementen, kosten, planning, rapport, Supabase) | `WKWebView` in `App/Sources/MJOP/` — geen herimplementatie in Swift |
| **Gevelscanner** | ongewijzigde Photo Walk (ARKit/LiDAR, fotoherkenning, resultaten, meetdiagnose) | bestaande SwiftUI/ARKit-code |

Beide onderdelen blijven levend bij wisselen (één `WKWebView`-instantie, scanner-`NavigationStack` blijft bestaan): webstaat, ingevulde velden en de plek in de scanner gaan niet verloren. De camera wordt gepauzeerd zodra je naar Mijn MJOP gaat en hervat (zonder tracking-reset) bij terugkeren. De laatst gekozen sectie wordt onthouden.

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

**Dit werkt pas na een aparte wijziging aan de website en Supabase** (niet in deze PR; zie de aparte web-PR / hieronder):

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
