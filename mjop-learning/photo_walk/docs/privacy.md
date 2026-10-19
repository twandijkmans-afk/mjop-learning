# Privacy en gegevensbescherming

* **Lokaal**: alle verwerking op het toestel / in de testomgeving. De meetkern importeert geen netwerkbibliotheken (AST-test) en de tests blokkeren sockets (test 19).
* **Geen uploads**: `images_uploaded=false` en `external_vision_calls=0` zijn schema-constanten; de app bevat geen netwerkcode; delen van een exportbestand is een handmatige actie (share sheet). Er is **geen** aanroep van de bestaande External Vision Safety Gate nodig en die wordt niet omzeild of aangeroepen.
* **Hoekdetectie** (`VNDetectRectanglesRequest`) draait on-device in Apple Vision; er verlaat niets het toestel. Voorstellen blijven onbevestigd tot een mens ze accepteert.
* **Geen media in Git**: het contract bevat alleen `local://`-verwijzingen; een test faalt als er afbeeldings-/dieptebestanden onder `photo_walk/` staan; `.gitignore` sluit ze uit. Publieke tests en voorbeelden zijn 100 % synthetisch.
* **Geen onnodige locatie**: geen GPS, geen `NSLocation…`-toestemming, `location_stored=false`. Gebouw-/gevel-ID's zijn door de gebruiker gekozen labels.
* **Lokale opslag**: keyframes in Application Support, `isExcludedFromBackup`, exportbestand met `completeFileProtection`.
* **Gevoelige inhoud** (huisnummers, personen, kentekens): niet automatisch herkend of gemaskeerd; daarom blijven beelden lokaal. Voorstel voor een latere fase: gezichts-/kentekenmaskering vóór elke deling.
* **Bewaartermijn (voorstel, niet vastgesteld)**: ruwe beelden/diepte verwijderen na afronding van de review of uiterlijk 30 dagen na de scan; het exportrecord (zonder media/locatie) mag bij het dossier blijven. Herleidbaarheid: `session_id`, `processing_version`, `measurement_method_version`, drempels en corrigeerrevisies staan in het record.
* Geen wijziging van Maldenhof-besluiten of andere canonieke brongegevens; geen cost-/kengetalkoppeling.
