# Eén gedeelde rekenkern voor website en iPhone-app — onderzoek en voorstel

**Status:** onderzoek en voorstel. In deze opdracht is **niets verplaatst of herschreven**: de bestaande berekeningen in de website zijn ongewijzigd en blijven leidend.
De iPhone-app bevat **geen** tweede (Swift-)implementatie van MJOP-berekeningen en schrijft niet naar `saved_plans.state`.

Besluit van de eigenaar: er komt uiteindelijk één gedeelde rekenkern voor de website en de app, zodat er geen afwijkende uitkomsten kunnen ontstaan.

Bron van de feiten hieronder: website `twandijkmans-afk/MJOP-App`, productiebranch `claude/mjop-live-implementation-smz60g` (commit `404b22f`). Regelnummers verwijzen daarnaar.
Wat is vastgesteld door de code te lezen/uit te voeren staat als **[V]**, wat is afgeleid als **[A]**, wat nog onbekend is als **[O]**.

## 1. Welke berekeningen staan nu waar

| Onderwerp | Waar | Opmerking |
|---|---|---|
| **Hoeveelheden** (parsen, bronnen, voorstellen als bron, bevestigen, steiger) | `src/quantity.js` (759 regels, 42 publieke functies, `MJOPQuantity`) | Al een los, DOM-vrij UMD-bestand met 54 unit-tests **[V]** |
| **Componentinventaris** | `src/inventory.js` (171 regels, 15 functies, `MJOPInventory`) | Idem, 13 unit-tests **[V]** |
| **Kengetallen en cycli per onderhoudspost** | `src/app.js` `ELEMENT_LIBRARY` (r. 516) | Een JavaScript-array in code, geen gegevensbestand |
| **Conditie en gebreken** | `gebrekScore` (r. 720), `conditionScore` (r. 730) | |
| **Onderhoudscycli en jaren** | `nextOccurrence` (r. 869), `yearForCycle` (r. 878), `conditionYear` (r. 885), `scheduleFor` (r. 896) | |
| **Onderhoudskosten** | `elementCost` (r. 828), `kozGroepen` (r. 752), offertes: `offerteBedragen` (r. 4667), `offerteTotal` (r. 4671) | |
| **Indexering** | `indexeerBedrag` (r. 820), CBS-aanroep `laadCbsIndexatie` (r. 779, tabel 83547NED, terugval 3% per jaar, cache in `localStorage`) | Tijds- en netwerkafhankelijk |
| **Reserveringen, begroting, bijdrage** | `fullPlan` (r. 950), `categorieTotalen` (r. 963), `perJaarKosten` (r. 977), `simuleerSaldi` (r. 985), `kasstroom` (r. 997), `benodigdeBijdrage` (r. 1010) | |

Het rekenblok in `app.js` (r. 516 t/m ± 1035, ongeveer 520 regels) is vrijwel een functie van het `state`-object. Gemeten **[V]**:

* Het blok gebruikt maar **10 namen die buiten het blok zijn gedefinieerd**: `Q` (quantity.js), `CURRENT_YEAR`, `HORIZON`, `KOZ_MATERIAAL`, `KOZ_DEF` (constanten), `eur`, `meervoud`, `esc` (opmaak) en alleen `currentScreen` en `render` (scherm; uitsluitend in de CBS-laadfunctie).
* Niet-zuivere onderdelen: `Date.now`, `fetch` (CBS) en `localStorage` (CBS-cache).
* Er is **geen** decimale/centenrekenning: de website rekent met JavaScript-getallen (≈ 70 plekken met `Math.round`/`toFixed`/`Number` in `app.js`).
* `quantity.js` en `inventory.js` laden en draaien in een kale JavaScript-omgeving zonder `window`, `document`, `console` of `module` (gecontroleerd met Node `vm`). Dat is precies wat JavaScriptCore biedt.

## 2. Wat kan gedeeld worden

* **Direct:** `quantity.js`, `inventory.js` (al los).
* **Na loskoppelen:** het rekenblok in `app.js`. Nodig: de 10 afhankelijkheden hierboven injecteren (jaar, indexering, constanten, opmaak), de twee scherm-aanroepen in de CBS-laadfunctie weghalen, en de kengetallenbibliotheek als gegevens laden.
* **Niet delen:** schermcode, de CBS-aanroep zelf (netwerk blijft aan de website/host; de rekenkern krijgt de indexering als invoer), opslag (`saved_plans`).

## 3. Mogelijke oplossingen

| | Oplossing | Voordelen | Nadelen |
|---|---|---|---|
| **A** | Alles opnieuw in Swift met pariteitstests | Native, snel | **Twee implementaties**; elke wijziging op twee plekken; juist wat we willen voorkomen |
| **B** | **Eén JavaScript-rekenkern**, in de website gebruikt en in de app uitgevoerd via **JavaScriptCore** (zit in iOS, geen extra bibliotheek) | Eén bestand, één uitkomst; sluit aan op wat al los staat (`quantity.js`); past bij de bestaande Swift↔Python-pariteitsaanpak | Getallen blijven JS-getallen; app moet een gebundelde kopie van het bestand meeleveren (versiebeheer nodig) |
| **C** | Rekenkern als server-functie (Supabase Edge Function) | Eén plek | Werkt niet offline; backendwijziging; apart beheer |
| **D** | WebAssembly/Rust | Eén bron, ook buiten JS bruikbaar | Grote herschrijving van werkende code; hoog risico voor bestaande MJOP's |

**Aanbeveling: B.** Reden: de code staat al grotendeels los (zie boven), er hoeft niets herschreven te worden maar alleen verplaatst, en de Swift-kant krijgt geen rekenwerk. C en D blijven alternatieven als het ooit nodig is buiten JavaScript te rekenen.

### Voorgestelde opbouw
* `src/engine/mjop-engine.js` (UMD, zonder DOM): zuivere functies `(state, env) → resultaat`, met `env = { jaar, indexering, … }` als invoer en een `ENGINE_VERSION`.
* De kengetallenbibliotheek (`ELEMENT_LIBRARY`) later als **versiegebonden gegevensbestand** (JSON). Dezelfde bibliotheek kan dan ook de AI-gevelscanner voeden ("eigen kengetallenbibliotheek"): het model stelt hoeveelheden voor, de rekenkern berekent de kosten **deterministisch** (dit sluit aan bij de projectregel dat berekeningen nooit door het taalmodel worden gedaan).
* De website importeert de engine; de CI van de app kopieert **hetzelfde bestand** (met sha256) in de app-bundel; Swift laadt het in een `JSContext` en geeft alleen JSON door. In Swift komt **geen** rekenwerk.
* Bij verschil in `ENGINE_VERSION` tussen app en plan toont de app de uitkomst niet maar verwijst naar de website.

## 4. Hoe bewijzen we dat uitkomsten gelijk blijven

1. **Stap 0 (voor elke wijziging):** leg de huidige uitkomsten vast als *golden master*: voor de bestaande fixtures (Maldenhof, DOC-012, voorbeeldgebouw) en een aantal geanonimiseerde opgeslagen plannen: kosten per post, schema per jaar, `kasstroom`, `benodigdeBijdrage`, offertetotalen. Jaar en indexering **vastzetten** (anders verandert de uitkomst met de tijd).
2. **Stap 1:** knip het rekenblok zonder gedragswijziging uit `app.js`; bewijs in Node dat álle golden-master-uitkomsten **exact gelijk** zijn (tekstuele vergelijking van de JSON, geen tolerantie).
3. **Stap 2:** laat dezelfde golden-master-bestanden in **JavaScriptCore** draaien op de macOS-CI (XCTest) en vergelijk exact.
4. **Stap 3:** een browsertest die dezelfde plannen in de echte website laadt en de getoonde bedragen met de engine-uitvoer vergelijkt.
5. De website- en app-CI falen bij elk verschil. Een uitkomst die alleen slaagt omdat de CBS-aanroep niet bereikbaar is, telt niet.

## 5. Risico's voor bestaande MJOP's

| Risico | Maatregel |
|---|---|
| Uitkomst hangt af van het jaar en de CBS-index (`Date.now`, `fetch`) | Jaar en indexering als expliciete invoer; golden-master met vaste waarden |
| Afronding: JavaScript rondt halven naar boven, Swift standaard van nul af | Alle rekenwerk blijft in JS; Swift rondt nooit opnieuw af |
| Rekenfuncties wijzigen objecten (bijvoorbeeld `ensureQuantity`) | Eerst in kaart brengen en testen vóór het loskoppelen |
| Oudere opgeslagen plannen zonder nieuwere velden | De engine leest met dezelfde standaardwaarden als `applyPlanBlob`; golden-master met oude plannen |
| Versieverschil tussen app en website | `ENGINE_VERSION` en controle zoals boven |
| Native schrijven naar `saved_plans.state` | **Blijft verboden** zolang gelijktijdig schrijven (de website slaat automatisch op) en behoud van onbekende velden niet aantoonbaar veilig zijn |
| Float-geld (geen centen) | Bestaand gedrag; niet in deze stap veranderen. Eventueel later apart voorstel (met golden-master) |
| App Store-regels voor gebundelde JavaScript **[O]** | Voor sideloaden niet van belang; vóór eventuele publicatie controleren |

## 6. Wat dit voorstel niet doet
Geen verplaatsing van code, geen wijziging van berekeningen, geen wijziging van het opslagformaat. Pas na akkoord en na stap 0 (golden master) begint het loskoppelen.
