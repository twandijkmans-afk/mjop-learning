# Facade Ground Truth Quantity PoC v1 — resultaten

Gegenereerd door `scripts/facade_ground_truth_poc.py` uit de manifesten in `reports/quantity/facade_ground_truth_poc_v1/cases/`. Toelichting, protocol en keuzes: `docs/facade_ground_truth_poc_v1.md`.

- Definitie: **PROJECTED_OPENING_BBOX_AREA_IN_FACADE_PLANE** — breedte x hoogte van de omhullende rechthoek van het BUITENKOZIJN (buitenkant kozijnhout tot buitenkant kozijnhout; boven tot onderkant onderdorpel, excl. stenen raamdorpel), loodrecht geprojecteerd op het gevelvlak, in meters. Een paneel binnen hetzelfde kozijn hoort erbij. Dit is GEEN schilderoppervlak en GEEN "kozijn-m²" in MJOP-zin.
- Ground truth: **MISSING**; accuracy-claim: **NEE**

| Case | Scope | GT-status | Model | GT-objecten | TP | FP | Gemist | Precision | Recall | GT m² | Berekend m² | Δ m² | Δ % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GT-MAL-01 | FRONT_MAIN | MISSING | 2 openingen, 5.46 m² | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| GT-MAL-01 | REAR | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| GT-MAL-02 | FRONT_MAIN | MISSING | 2 openingen, 5.38 m² | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| GT-MAL-02 | REAR | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| GT-MAL-03 | FRONT_MAIN | MISSING | 3 openingen, 4.01 m² | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| GT-MAL-03 | REAR | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |

Verschil per oorzaak (alleen bij COMPLETE):

- MISSING — er is nog geen echte meting of maatvaste tekening; er wordt geen nauwkeurigheid geclaimd.

Modelkant per scope (bestaande gecommitte detecties; geen nieuwe API-calls):

- GT-MAL-01/FRONT_MAIN: 2 openingen, ruw 5.46 m², volgens definitie 5.46 m² (panelen binnen kozijn samengevoegd: 0)
- GT-MAL-01/REAR: MISSING
- GT-MAL-02/FRONT_MAIN: 2 openingen, ruw 4.63 m², volgens definitie 5.38 m² (panelen binnen kozijn samengevoegd: 1)
- GT-MAL-02/REAR: MISSING
- GT-MAL-03/FRONT_MAIN: 3 openingen, ruw 4.01 m², volgens definitie 4.01 m² (panelen binnen kozijn samengevoegd: 0)
- GT-MAL-03/REAR: MISSING
