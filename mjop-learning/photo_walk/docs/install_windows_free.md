# Photo Walk op je iPhone zetten — Windows-pc, gratis Apple-account, geen Mac

**Kort:** dit is *waarschijnlijk haalbaar*, maar het is hier **nog nooit op een echte iPhone geprobeerd**. De CI bouwt een **niet-ondertekende** IPA; een gratis installatietool op je pc ondertekent die met jouw Apple-account en zet hem op je telefoon. Geen Apple-wachtwoord of code hoeft met Claude gedeeld te worden: je voert die zelf alleen in het installatieprogramma op je eigen pc in.

## Drie soorten builds (niet door elkaar halen)

| Build | Wat het is | Op je iPhone te installeren? |
|---|---|---|
| **Simulatorbuild** (`PhotoWalk-simulator.app.zip`) | draait alleen in de iOS-simulator op een Mac | **Nee** (andere processorarchitectuur/SDK) |
| **Unsigned devicebuild** (`PhotoWalk-UNSIGNED-device.ipa`) | echte iPhone-code, zonder handtekening/provisioning | **Niet rechtstreeks.** iOS weigert apps zonder geldige handtekening. Een tool moet hem eerst ondertekenen. |
| **Ondertekende IPA** | ondertekend met een certificaat + provisioning profile voor jouw toestel | Ja — maar die krijg je pas na stap hieronder (Sideloadly/AltStore doen dit op je pc) of met een betaald Apple Developer-account (TestFlight/Ad Hoc) |

GitHub Actions kan zónder jouw Apple-gegevens dus nooit een direct installeerbare IPA maken. Er worden bewust geen certificaten of accountgegevens in de repo of in CI gezet.

## Beperkingen van een gratis Apple-account (bron: Apple, *Compare memberships*)

* Apps verlopen na **7 dagen** en moeten opnieuw worden geïnstalleerd/vernieuwd.
* Max. **3 apps** tegelijk per toestel, max. **10 App-ID's per 7 dagen**.
* Geen TestFlight, geen App Store.
* Of ARKit/camera onder een gratis profiel zonder beperking werkt is **niet geverifieerd**; ARKit en cameratoegang vragen geen speciale entitlement, dus dat zou moeten werken — te bevestigen op je toestel.

## Route A — Sideloadly (aanbevolen voor een eigen IPA)

Vereist: Windows 10/11, USB-kabel, iPhone met iOS 16 of nieuwer, **Developer Mode aan** (Instellingen → Privacy en beveiliging → Ontwikkelaarsmodus), de *web*-versies van **iTunes** en **iCloud** (niet uit de Microsoft Store), je Apple-ID.
1. Download de IPA: log in op GitHub → PR #57 → *Checks* → workflow **Photo walk iOS build** → run openen → onderaan *Artifacts* → **`photo-walk-UNSIGNED-device-ipa`** (zip; uitpakken geeft `PhotoWalk-UNSIGNED-device.ipa`). Artifacts verlopen na 14 dagen; start de workflow dan opnieuw (*Run workflow*).
2. Installeer iTunes + iCloud (web-versies) en sideloadly.io; sluit de iPhone aan en kies "Vertrouwen".
3. Sideloadly: sleep de IPA erin, vul je Apple-ID in (gebruik bij voorkeur een apart gratis Apple-ID), *Start*. Voer wachtwoord/2FA **alleen daar** in.
4. iPhone: Instellingen → Algemeen → VPN en apparaatbeheer → je Apple-ID → *Vertrouw*. Start Photo Walk; sta de camera toe.
5. Na 7 dagen: opnieuw installeren (Sideloadly kan automatisch vernieuwen zolang de iPhone bereikbaar is).

## Route B — AltStore Classic

Hetzelfde principe: AltServer op Windows (met iTunes/iCloud web-versies) ondertekent en installeert de IPA via de AltStore-app ("My Apps → +"), en vernieuwt wekelijks zolang pc en iPhone op hetzelfde wifi zitten. Iets meer opzet dan Sideloadly; zelfde 7-dagen/3-apps-limiet.

## Als het niet lukt

* Foutmelding over bundle-ID / "maximum number of apps": wacht of gebruik een ander gratis Apple-ID.
* Apps starten niet na installatie: Developer Mode of "Vertrouw" ontbreekt.
* Blijft ondertekenen mislukken: alternatief is een geleend Mac-toestel met Xcode (gratis account werkt daar ook), of later een betaald Developer-account (99 USD/jaar) en een CI-workflow met jouw eigen certificaat als *GitHub-secret* — pas doen na jouw uitdrukkelijke keuze.

## Later: distributie met een eigen (betaald) Apple Developer-account

1. Certificaat (Apple Distribution) + provisioning profile + App-ID aanmaken in developer.apple.com.
2. In de repo-instellingen als *secrets* opslaan (p12 + wachtwoord, profile, team-ID) — nooit in Git.
3. Workflow uitbreiden met `xcodebuild archive` + `-exportArchive` (ExportOptions.plist, method `ad-hoc` of `app-store-connect`) en upload naar TestFlight via `xcrun altool`/App Store Connect API-sleutel.
4. In `project.yml` `DEVELOPMENT_TEAM` en een eigen bundle-ID zetten.
Dit is niet ingericht; zie de volgende stap alleen met jouw toestemming.

## Eerste meting op de telefoon (foto-workflow)
1. Open Photo Walk → gebouw-/gevel-ID invullen → **Foto-scan starten** → camera toestaan.
2. Sta 2–4 m recht voor de gevel (hele kozijn in beeld; zoom is alleen voorvertoning) en tik de **ronde fotoknop**.
3. Direct verschijnen kaders op de foto: **groen** = voorlopig bruikbare maat, **oranje** = controle nodig, **grijs** = geen betrouwbare maat (`UNKNOWN`). De kaders zijn *kandidaten* van een algemene rechthoekdetector: controleer ze en verwijder valse met *Geen kozijn*.
4. Tik een kader: automatisch ingezoomd; sleep de hoeken naar de buitenhoeken en kies *Toepassen*; of voeg één *Referentiemaat* toe (twee punten + zelf gemeten afstand) als er geen LiDAR/diepte is.
5. Onder de foto staat het overzicht (herkend, voorlopig unieke kozijnen, bruto m² waar meetbaar, controles). Maak een tweede foto van dezelfde gevel; bij *Koppelsuggesties* kun je hetzelfde kozijn voorlopig koppelen.
6. *Exporteren* → JSON in Bestanden → Op mijn iPhone → Photo Walk. Meet het kozijn ook met een duimstok en vergelijk; alles is voorlopig en niet gevalideerd.

## Nieuwe LiDAR-meting + meetdiagnose (LiDAR-v2)
1. Foto-scan starten, 2–4 m **recht** voor de gevel, hele kozijn én wat muur rondom (alle vier de kanten) in beeld. Houd de telefoon rustig.
2. Staat er in beeld *"Beweeg je telefoon langzaam iets naar links en rechts voor een betere meting."*: beweeg 2–5 cm zijwaarts (links-rechts) terwijl je richt, en tik daarna de fotoknop. De app bewaart tot ~1,8 s aan dieptekaders vóór de foto; de berekening gebruikt alleen kaders met voldoende verplaatsing.
3. Tik het kader van het kozijn. Een automatische LiDAR-maat toont `LIDAR_DEPTH_MULTI_FRAME` (≥ 2 onafhankelijke kaders) onder *Meetdiagnose*; `LIDAR_DEPTH_PLANE` = één kader (altijd `ESTIMATED`).
4. Geen maat (grijs/oranje)? Open **Meetdiagnose**: daar staat de specifieke reden (bijv. verspringende gevel, te ruwe muur, kader te groot/klein, kozijnvlak niet te bepalen) en wat je kunt doen.
5. **Exporteer meetdiagnose**: schrijft `meetdiagnose_….json` (alleen getallen, geen foto's/puntenwolk/locatie) naar Bestanden → Op mijn iPhone → Photo Walk. Zet dat bestand (en de duimstokmaat van het kozijn) hier in een sessie, zodat de drempels op echte data gekalibreerd kunnen worden. Controleer op de pc met `python -m photo_walk_core.validate meetdiagnose_*.json`.
6. *Referentiemaat*: kies **Gemeten** (duimstok/laser) of **Uit tekening** voor een echte referentie; **Geschat** blijft `ESTIMATED` en geldt niet als meting.

## Een nieuwe versie installeren (update)
1. Download opnieuw de artifact `photo-walk-UNSIGNED-device-ipa` van het nieuwste groene run van PR #57 (zie hierboven).
2. Open Sideloadly, sleep de nieuwe IPA erin, zelfde Apple-ID, *Start*. Het bundle-ID blijft hetzelfde, dus de nieuwe versie wordt **over de oude heen** geïnstalleerd en je bewaarde scans/exports (Bestanden → Photo Walk) blijven behouden. Wil je schoon beginnen: verwijder de app eerst op de iPhone.
3. Het 7-dagen-venster van het gratis profiel begint opnieuw bij elke installatie.
