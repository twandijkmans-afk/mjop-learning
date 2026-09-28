# Fixture: benaderde `pdftotext -table`-uitvoer voor DOC-010

Doel: de deterministische route (`scripts/deterministic_extraction.py`) testen
zonder xpdf 4.06 in de cloudomgeving. De fixture vervangt **alleen de externe
executable** (via `../fake_pdftotext.py`); `mjop_source_sections.py` wordt
ongewijzigd gebruikt. Er wordt geen nieuwe "waarheid" verzonnen.

Bestanden:
- `make_fixture.py` — genereert `pages.json` (reproduceerbaar, zelfde
  kolomopmaak-aanpak als de helpers in `tests/test_price_observations.py`).
- `pages.json` — 17 pagina's (zoals de echte PDF), alleen pagina 2, 5, 6, 8, 9
  en 10 hebben inhoud; de rest is leeg.

## Herkomst per regel (inhoud is letterlijk DOC-010)

Bronnen:
- **[PO]** `data/price_observations/price_observations_batch1.json`, veld
  `source_representations[].source_text` — dit is vastgelegde echte xpdf
  4.06 `-table`-uitvoer (met `€` verwijderd door `mjop_source_sections._clean`).
- **[CTX]** zelfde bestand, `documents[DOC-010].document_context`
  (echte xpdf-uitvoer van het objectblad/pagina 9).
- **[TL]** de tekstlaag van de echte PDF (`scripts/text_layer.py`,
  pdfplumber), pagina/regel zoals vermeld.

| Pagina | Regel(s) in fixture | Bron |
|---|---|---|
| 2 | `Prijspeil 1-4-2023`, `BTW De bedragen in de begrotingen zijn inclusief BTW`, `BTW tarief Hoog/Laag tarief is toegepast: Hoog = 9,0%; Laag = 21,0%` | [CTX] (`price_level_source`, `vat_source`, `vat_rate_text`) |
| 2 | Code / Object / Naam / Aantal eenheden 4 / Adres / Postcode / Plaats / Inspectiedatum 1-4-2023 / Opdrachtgever / Adres (Uiterwaardestraat) / Postcode / Plaats / Technisch / Bouwjaar 1935 / Renovatiejaar 2005 / Financieel | [TL] P02-L004 … P02-L033 (Inspecteur-regel bewust weggelaten: persoonsnaam, niet nodig) |
| 5 | `Elementenoverzicht`, `1 = Uitstekende conditie` … `9 = Niet te inspecteren` | [TL] P05 |
| 6 | groepen `21 Buitenwanden`, `31 Buitenwandopeningen`; elementrijen 2110 Gevelconstructie metselwerk, 2110 Loodslabben opgaand werk, 2120 Hijsbalk staal, 3120 Kozijn buiten aluminium | [TL] P06-L004 … P06-L016 |
| 8 | groepen 67, 99; elementrijen 6710 Dakbeveiliging algemeen, 9999 Hoogwerker tot 18 meter hoog | [TL] P08 |
| 9 | titel, BTW-regel, indexatiezin, Printdatum | [TL] P09 / [CTX] `indexation_statement` |
| 10 | `Herstellen metselwerk 5,93 m2 2028 12 1.351 1.351` | [PO] p10 l11 |
| 10 | `Keuren hanebalk 1,00 m2 2028 6 491 491 981` (2028 en 2034) | [PO] p10 l23 |
| 10 | `Onderhoud kozijnen (confrom offerte 84,28 m2 2028 11.024 11.024` + vervolgregel `Kemo)` | [PO] p10 l65 + continuation l67 |
| 10 | elementregels 2110 / 2120 / 3120 met locatie; groepen 21 / 31 | [PO] `element` + `element_line` |
| 10 | `Vervangen hijswerk staal 1,00 st 2052 0` (geen bedrag in venster) | [TL] P10-L011 |
| 10 | subtotaalregel groep 21 (2028: 1.841, 2034: 491, Totaal 2.332) | [TL] P10-L013 |

## Wat deze fixture NIET garandeert

- De exacte spatiëring/kolomposities en regelnummers van echte xpdf-uitvoer
  (echte regelnummers staan in [PO]/[CTX], bijv. Prijspeil op p2 regel 59).
- Of echte xpdf-uitvoer van het Elementenoverzicht `148,25m2` aaneen of als
  `148,25 m2` toont — de parser accepteert beide; de lokale pilot is de toets.
- Het `€`-teken ontbreekt in de fixture; `mjop_source_sections._clean`
  verwijdert het in echte uitvoer ook.

De echte pilot draait lokaal met xpdf 4.06 tegen het echte bronbestand
(zie `docs/deterministic_extraction_v1.md`).
