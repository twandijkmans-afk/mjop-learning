# Photo-to-Quantity Pilot v1 (experimenteel, annotatiegebaseerd)

Lokale pilot die bestaande foto-annotaties omzet naar (A) foto-observaties, (B) voorlopig unieke objecten en (C) experimentele
bruto-m²-schattingen. Geen nieuwe contracten: de v2-schema's, vocabularies en stores blijven ongewijzigd.

- Bibliotheek: `scripts/photo_quantity_pilot.py` (puur, zonder bestandstoegang, netwerk of AI-SDK).
- Runner: `scripts/run_maldenhof_photo_quantity_pilot.py` (leest read-only, schrijft alleen naar `local_output/`, dat in `.gitignore` staat).
- Config: `config/maldenhof_photo_quantity_pilot_v1.json` (alleen ID's, segmentregels en expliciete aannames; geen foto-inhoud).
- Tests: `tests/test_photo_quantity_pilot.py` (synthetisch, plus een rooktest op de ingecheckte pilotbronnen).

Draaien: `python3 scripts/run_maldenhof_photo_quantity_pilot.py` (Pillow vereist; OpenCV/NumPy optioneel via `requirements-photo-pilot.txt`).
Uitvoer: `pilot_report.html`, `pilot_results.json`, `kozijninventaris.csv`, `annotated/*.jpg`, `gevelschema.png`.

## Regels
- Identiteit: alleen 1-op-1 `POSSIBLY_SAME_PHYSICAL_FRAME` met HIGH/MEDIUM voegt samen; LOW = mogelijke dubbeltelling; `UNDETERMINABLE`
  en veel-op-een blijven conflict; samenvoegen van twee observaties van dezelfde foto wordt geweigerd; gelijkenis alleen is nooit genoeg.
- Schaal: Methode A (betrouwbaar) vereist een aantoonbare referentie; zonder die blijft het `UNKNOWN`/Methode B (dimensieloze
  verhoudingen). Methode C levert `PHOTO_ASSUMPTION_ESTIMATE` met onder/centraal/bovengrens uit expliciete aannames; nooit
  MEASURED/CONFIRMED/APPROVED, v2-equivalent blijft `UNKNOWN`.
- Bruto m² = buitenbreedte × buitenhoogte × aantal via `bruto_quantity_core.gross_area_exact` (Decimal); totalen alleen over unieke objecten.
- Geen FI-instances, besluiten, prijzen, kengetallen of externe Vision-aanroepen.
