# Frame Inventory Foundation v1 + Vector Drawing Reader PoC v1

Kort: datamodel, quantity-semantiek en repeat-contract voor kozijnen, plus een generieke gratis vector-PDF reader. Er staat geen echte
bouwtekening in de repo, dus de real-world PoC is geblokkeerd (`REAL_WORLD_POC_BLOCKED_NO_DRAWING`). Rapporten:
`reports/frames/frame_inventory_foundation_v1.md` en `reports/drawing/vector_drawing_source_audit_v1.md`.

## Onderdelen

| Onderdeel | Bestand |
|---|---|
| Presence-besluiten EXTERIOR_FRAME (CPD-00001 Maldenhof, CPD-00002 Meppelweg) | `scripts/record_frame_presence_decisions.py`, `data/component_presence/component_presence_decision_records.json` |
| Instance-/groepsmodel en afleidingsregels | `schemas/frame_component_instance.schema.json`, `schemas/frame_group.schema.json`, `schemas/frame_inventory.schema.json`, `scripts/frame_inventory.py` |
| Repeat-groepen (alleen na USER_CONFIRMED_REPEAT) | `schemas/component_repeat_group.schema.json`, `data/frame_inventory/component_repeat_groups_v1.json` |
| Zeven quantity-concepten, legacy-fallback, bronprioriteit | `vocabularies/frame_quantity_concepts_v1.json` |
| Source audit | `scripts/vector_drawing_source_audit.py` |
| Primitive reader, schaalbewijs, paginatype, candidates, overlay | `scripts/vector_drawing_reader.py` |
| Synthetische TEST FIXTURE (geen echt gebouw) | `tests/fixtures/drawing/` |

## Dependencies (geen nieuwe)

| Naam | Versie | Licentie | Waarom |
|---|---|---|---|
| pdfplumber | 0.11.10 (reeds in requirements-pipeline.txt) | MIT | lines/rects/curves/tekstspans/afbeeldingen per PDF-pagina |
| pdfminer.six | 20260107 (reeds aanwezig) | MIT | onderliggende PDF-parser van pdfplumber |
| jsonschema + referencing | 4.26.0 / 0.37.0 (reeds aanwezig; `referencing` is een jsonschema-dependency) | MIT | schemavalidatie met kruisverwijzingen tussen de nieuwe schema's |

PyMuPDF (AGPL) is bewust niet gebruikt en niet toegevoegd. Geen OCR, geen LLM/betaalde API, geen netwerk.

## Scale-regels (samengevat)

Punten worden alleen naar meters omgezet met bewijs: (A, voorkeur) maatlijn = numerieke tekst (mm) bij een rechte lijn, meerdere maatlijnen
binnen 2%; of (B) expliciete tekeningschaal 1:N op een standaard ISO-papierformaat (en, indien aanwezig, een maatlijn die binnen 2% klopt).
Anders `UNKNOWN`/`ScaleError`. Beperking: tekeningen met maatlijnen als losse paden/ticks zonder gekoppelde tekst vragen mogelijk aanpassing.
