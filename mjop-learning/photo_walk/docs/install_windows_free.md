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

## Eerste meting op de telefoon

1. Open Photo Walk → gebouw-/gevel-ID invullen → *Nieuwe scan starten* → camera toestaan.
2. Sta ca. 2–4 m recht voor één kozijn, houd het hele kozijn in beeld, tik *Keyframe*. Loop 1–2 m zijwaarts en tik nog een *Keyframe* (twee standpunten geeft een consistentiecontrole).
3. *Kozijnen markeren* → keyframe kiezen → vier **buitenhoeken** tikken (linksboven, rechtsboven, rechtsonder, linksonder) → *Opslaan*. Tweede keyframe: *Koppel aan kozijn* → hetzelfde kozijn kiezen.
4. Zonder LiDAR (alleen Pro-modellen hebben het): bij *Referentiemaat voor …* twee punten op het kozijnvlak tikken en een zelf gemeten afstand invoeren (bv. de kozijnbreedte met duimstok).
5. *Resultaten*: breedte, hoogte, bruto m², status (MEASURED/DERIVED/ESTIMATED/UNKNOWN), bron en onzekerheid. *Hoeken corrigeren* herberekent zonder brondata te overschrijven. *Exporteer naar bestand* → het JSON staat in de Bestanden-app → "Op mijn iPhone" → Photo Walk.
6. Meet het kozijn ook met een duimstok en vergelijk; de uitkomst is **voorlopig** en onvalideerd — geen basis voor een MJOP-hoeveelheid zonder menselijke goedkeuring.
