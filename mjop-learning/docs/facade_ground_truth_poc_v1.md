# Facade Ground Truth Quantity PoC v1 — framework, testcases en capture-protocol

Status: **framework klaar, ground truth MISSING**. Er is nog geen echte meting of maatvaste tekening, dus er is
**geen accuracy-claim**. Resultaten (automatisch, nu overal MISSING): `reports/quantity/facade_ground_truth_poc_v1.md`
en `.json`. Script: `scripts/facade_ground_truth_poc.py`. Schema: `schemas/facade_ground_truth_case.schema.json`.
Manifesten: `reports/quantity/facade_ground_truth_poc_v1/cases/GT-MAL-0{1,2,3}.json`.

## Vraag

"Als we voldoende goede beelden hebben, hoe dicht komt de berekende hoeveelheid bij de echte fysieke hoeveelheid?"
Het gaat niet opnieuw om de vraag óf het model kozijnen herkent; dat is in PoC v2 al gemeten (recall 0,93 op goed
zichtbare gevels).

## Eén geometrische definitie

**PROJECTED_OPENING_BBOX_AREA_IN_FACADE_PLANE**: breedte × hoogte van de omhullende rechthoek van het
**buitenkozijn**, in meters, gemeten in het gevelvlak.

- **Breedte:** buitenkant kozijnhout links tot buitenkant kozijnhout rechts.
- **Hoogte:** bovenkant kozijn tot onderkant onderdorpel, **zonder** de stenen raamdorpel.
- **Paneel binnen het kozijn:** een borstweringspaneel binnen hetzelfde kozijn hoort erbij; de donkere
  gevelbekleding erboven niet.

Dit is **geen** schilderoppervlak, **geen** "kozijn-m²" in MJOP-zin en **niet** de MJOP-756,8.

Het model meldt een paneel binnen het kozijn soms apart. Het script voegt een paneel daarom bij het raam als het
**direct onder** het raam ligt (naad ≤ 0,10 m) en **binnen de raambreedte** valt (≥ 80%). Het rapporteert zowel de
ruwe som als de som volgens de definitie; het verschil heet `semantic_definition_difference_m2`. Dit is een
heuristiek: de meting (`includes_panel_in_frame`) is leidend.

## Gekozen testcases

| Case | Pand / adressen | Waarom |
|---|---|---|
| **GT-MAL-01** (primair) | 0363100012143647 — Maldenhof 282 / 284 | Middenwoning. Best gedekte hoofdvoorgevel van alle 13 middenpanden (89% bevestigd zichtbaar), frontaal panorama op 12,6 m, review ronde B 3/3 juist en 0 onterecht. Representatief voor het gespiegelde rijtype. |
| **GT-MAL-02** | 0363100012070344 — Maldenhof 262 / 264 | Tweede middenwoning van hetzelfde type (81%). Het model meldt hier het witte paneel binnen het kozijn apart, dus deze case test de definitie-afhandeling. Ook het referentiepand uit v1. |
| **GT-MAL-03** | 0363100012127361 — Maldenhof 294 / 296 | Eindwoning. Voorgevel maar 48% zichtbaar: het kozijn op de begane grond staat achter struiken (het model ziet 0,44 m hoogte). Laat het effect van dekking op de m² zien. Niet extreem afgedekt zoals 240 (0%), dat bewust niet is gekozen. |

Per case zijn er twee scopes:

- **FRONT_MAIN**: de terugliggende hoofdvoorgevel, 3D BAG-wand ~17–19 m², begane grond en 1e verdieping. De
  modelkant komt uit de gecommitte v2-run, zonder nieuwe API-calls.
  - GT-MAL-01: 5,46 m²;
  - GT-MAL-02: 5,38 m² volgens de definitie (ruw 4,63);
  - GT-MAL-03: 4,01 m² (inclusief een randstrook en een half verborgen kozijn).
- **REAR**: de achtergevel. In v2 is die grotendeels onzichtbaar, dus hier is een bewonersfoto nodig. Modelkant en
  ground truth zijn MISSING.

De woningindeling (vermoedelijk beneden/boven) is niet bevestigd. De scope is daarom de fysieke gevel van het pand,
niet één woning.

## Wat er gemeten en vergeleken wordt

**Per scope (`compare_scope`):**
- **Ground truth:**
  - aantal openingen;
  - per object de breedte, hoogte en m² (Decimal);
  - het totaal.
- **Model:**
  - de gedetecteerde openingen met hun m²;
  - het totaal, ruw en volgens de definitie.

**Koppeling:**
- per laag (BG / 1e / kap) en type op volgorde van links naar rechts;
- bij een ongelijk aantal: status **NEEDS_MANUAL_MATCH**. Een mens legt de koppeling vast in `manual_matches`;
  er wordt niet gegokt.

**Uitkomst (alleen als de koppeling compleet is):**
- TP, FP, gemist, precision en recall;
- GT-m², berekende m², het absolute verschil en het verschil in %.

**Verschil per oorzaak:**
- `DETECTION_ERROR`: zichtbaar object gemist (vlag `visible_in_images` = true), of een door een mens bevestigd
  onterecht object;
- `MEASUREMENT_PROJECTION_ERROR`: object gevonden, maar de maat wijkt af (rectificatie, registratie, randverfijning);
- `COVERAGE_OCCLUSION`: object niet of deels zichtbaar (vlag = false, of het model meldt het als deels verborgen);
- `SEMANTIC_DEFINITION_DIFFERENCE`: het model meet iets anders dan de definitie (paneel apart, kozijn gesplitst);
- `UNDETERMINED`: de feiten ontbreken, bijvoorbeeld een onterecht object zonder menselijke uitspraak.

Ground-truth-status: `MISSING` / `PARTIAL` / `MEASURED` (rolmaat/laser) / `DRAWING_DERIVED` (maatvaste tekening).
Het script weigert inconsistente manifesten, bijvoorbeeld MISSING mét objecten, of MEASURED met een tekening als
bron. Er is geen confidence score.

## Capture-protocol voor bewoners (foto's)

1. Gebruik de **gewone camera-app**: geen panorama-modus, geen groothoek- of 0,5×-lens, **niet digitaal zoomen**.
2. Sta **recht voor het midden** van de gevel en houd de telefoon **rechtop en waterpas**, op borsthoogte, met het
   scherm evenwijdig aan de gevel.
3. Zet de **hele gevel van het pand** in beeld: beide woningen, van maaiveld tot dakgoot, met wat marge aan alle
   kanten.
4. Neem zo **veel afstand** als de tuin toelaat. Noteer die afstand bij benadering (bv. "ca. 6 m").
5. Zit er iets vóór (schutting, struik, tuinmeubel)? Maak **één extra foto** van dat deel vanaf een andere plek, of
   haal het weg als dat kan.
6. **Niet bijsnijden of bewerken** vóór het uploaden. Upload het originele bestand, zodat ook de opname-info
   (EXIF) behouden blijft.
7. **Liefst bij bewolkt weer**, zonder harde schaduwen of tegenlicht.

**Schaalreferentie (verplicht per foto).** Uit één gewone foto is de schaal **niet** betrouwbaar af te leiden.
Daarom komt er een bekende maat in het gevelvlak:

- **Voorkeur:** plak met schilderstape een **vierkant van 1,00 × 1,00 m** op de gevel, op een vlak metselwerkdeel
  rond borsthoogte. Meet de zijden met een rolmaat en controleer of de diagonalen gelijk zijn (≈ 1,414 m).
- Uit de 4 hoeken van het vierkant berekent het script een homografie: van foto-pixels naar meters in het gevelvlak
  (`homography`, `box_px_to_facade_m`).
- De hoekpunten worden door Claude aangewezen en door jou bevestigd; ze worden vastgelegd als
  `provenance`/`decided_by`.
- **Alternatief:** de hoeken van de 3D BAG-wand. Die zijn minder nauwkeurig (RMSE LoD2.2 ≈ 0,09 m) en worden dan
  als zodanig gelabeld.
- **Gebruik nooit een van de testkozijnen als referentie**: dan meet je jezelf na.

## Meetprotocol (de echte ground truth)

- **Gereedschap:** een stalen rolmaat (of laser). Noteer in meters met 2 of 3 decimalen, bijvoorbeeld `1.985`.
- **Wat per object:**
  - **breedte buitenwerks**: buitenkant kozijnhout tot buitenkant kozijnhout, horizontaal, op halve hoogte;
  - **hoogte buitenwerks**: bovenkant kozijnhout tot onderkant onderdorpel, zonder de stenen raamdorpel;
  - noteer of er een **paneel binnen hetzelfde kozijn** zit (`includes_panel_in_frame`).
- **Volgorde:** nummer de objecten per laag van links naar rechts, gezien vanaf de plek waar de foto is gemaakt.
- **Welke objecten:**
  - FRONT_MAIN: het kozijn op de begane grond en het kozijn op de 1e verdieping (met paneel). Optioneel, apart: de
    donkere gevelbekleding boven het 1e-verdiepingkozijn;
  - REAR: alle kozijnen en (balkon)deuren in de achtergevel, op de begane grond en de 1e verdieping.
- **Niet bereikbaar** (1e verdieping zonder veilige ladder)? **Niet schatten en niet van binnen meten.** Binnen meet
  je een andere maat (dagmaat), dus die telt niet. Laat het object weg; de scope wordt dan `PARTIAL`.
- **Maatvaste tekening als alternatief** (`DRAWING_DERIVED`): een gevelaanzicht met maatvoering of een schaal
  (bijvoorbeeld de bouwtekening uit het VvE-archief of van de beheerder, of het bouwdossier bij de gemeente). Noteer
  het tekeningnummer, de datum en de schaal als provenance.
- Per object noteer je ook `measured_by` en `measured_at`.
- Noteer per foto of het object **zichtbaar** is (`visible_in_images`). Dat is nodig om een gemist object als
  DETECTION_ERROR of als COVERAGE_OCCLUSION te kunnen indelen.

## Wat er na upload gebeurt

1. De foto's komen in `reports/quantity/facade_ground_truth_poc_v1/photos/` en de maten in het case-manifest (status
   `MEASURED`, `PARTIAL` of `DRAWING_DERIVED`).
2. De hoeken van de referentie (tape-vierkant) worden aangewezen en door jou bevestigd. Daarna volgen de homografie
   en de gerectificeerde gevelfoto.
3. **Detectie: alleen voor deze 2–3 cases.** Eén call per gerectificeerde foto:
   - per case de achtergevel, plus optioneel een frontale voorgevelfoto: **3–6 calls**;
   - hooguit 1 herhaling per foto bij een afgebroken antwoord: **maximaal ~10 calls**;
   - in v2 was dat ongeveer 2.000 input- en 520 outputtokens per call; reken op orde 12k input en 3k output tokens.
   - **Ik vraag vooraf expliciet toestemming** voor deze betaalde calls. De API-key gaat alleen via de environment
     variable `ANTHROPIC_API_KEY`.
4. `python scripts/facade_ground_truth_poc.py` vult de vergelijking. Pas dan, en alleen per scope met status
   COMPLETE, is er een accuracy-uitspraak, en alleen voor deze definitie.

## Bewust niet gedaan

- Geen drawing reader en geen modeltraining.
- Geen verdere optimalisatie van de straatbeeld-dekking en geen panorama-rerun.
- De historische 756,8 m² wordt niet als ground truth gebruikt.
- Geen extrapolatie naar het complex, geen canonical quantities, geen kengetallen, geen confidence of ranking,
  geen nieuwe betaalde diensten.
- De ground-truth-manifesten staan bewust onder `reports/` en niet in `data/evaluation/`. Of echte metingen later
  naar de evaluatielaag gaan, is een keuze voor de gebruiker.
