# Vector Drawing Source Audit v1

Status: **REAL_WORLD_POC_BLOCKED_NO_DRAWING** — er staat geen bruikbare vector bouw-/geveltekening in de repo.

- Unieke PDF's: 13 (16 bestandspaden; duplicaten via sha256 samengevoegd), 323 pagina's onderzocht
- VECTOR_DRAWING_CANDIDATE pagina's: 0
- RASTER_DRAWING_CANDIDATE pagina's: 0
- Pagina's met een sterk tekeninglabel (aanzicht/plattegrond/doorsnede/tekening/maatvoering/schaal 1:N): 0
- Pagina's met >= 30 vector-primitives (vrijwel allemaal tabelrasters/grafieken): 161
- Niet-PDF tekeningachtige bestanden (dwg/dxf/png/jpg/svg/ifc...): 13 (alleen de review-sheets van de eerdere public-image facade-PoC; foto's, geen tekeningen)
- Methode: pdfplumber primitives + tekstlabels; thresholds: sterk label + >= 30 primitives + >= 10 niet-orthogonale lijnen/complexe curves
- Tools: pdfplumber 0.11.10, pdfminer.six 20260107

Interpretatie: 'voorgevel'/'achtergevel'/'kozijn' staan in elke MJOP als tabeltekst en zijn geen tekeningbewijs. De rechthoeken en lijnen in de MJOP-PDF's zijn tabelrasters, grafieken en logo's; geen enkele pagina draagt een tekeninglabel of een schaal/maatvoering. Afbeeldingen zijn omslag- en conditiefoto's (steekproef visueel gecontroleerd: een omslagpagina en een conditiefoto-pagina).

## Per document

| Document (eerste pad) | registry | pagina's | classificatie | pagina's per klasse | max niet-orthogonale lijnen/complexe curves per pagina | pagina's met afbeelding >= 15% |
|---|---|---|---|---|---|---|
| data/incoming/Testbatch 01/Actualisatie MJOP VvE Granidastraat 46-80 2020 pdf.pdf (+1 duplicaat) | DOC-011 | 37 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 37} | 27 | — |
| data/incoming/Testbatch 01/Actualisatie MOP 2024.pdf (+1 duplicaat) | DOC-012 | 21 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 21} | 22 | 1 |
| data/incoming/Testbatch 01/MOP 2026 totaal.pdf (+1 duplicaat) | DOC-013 | 28 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 28} | 27 | 1 |
| data/incoming/Testbatch 01/Meerjarenonderhoudsplan 2023_VvE 9261.pdf | — | 20 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 20} | 23 | 1, 11 |
| data/raw/alkmaarstraat-1-83/9543_vvem_mop_14-01-2022_Pro VVEBeheer B.V._626720.pdf | DOC-001 | 27 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 27} | 38 | — |
| data/raw/jp-heijestraat/2026_Meerjarenonderhoudsplan_VvE 9690.pdf | DOC-002 | 26 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 26} | 24 | 1 |
| data/raw/jp-heijestraat/9690_vvem_mop_v_15-03-2018_Innax_hele_schil_376215.pdf | DOC-004 | 41 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 41} | 44 | 1 |
| data/raw/maldenhof/2026_Meerjarenonderhoudsplan_VvE 9261 Maldenhof 240-296.pdf | DOC-005 | 15 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 15} | 18 | 1 |
| data/raw/maldenhof/9261_vvem_mop_01-03-2023_Pro VVE Beheer B.V._851361.pdf | DOC-006 | 20 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 20} | 23 | 1, 11 |
| data/raw/mauritstaete/Actualisatie MOP 2023 met bijlage.pdf | DOC-007 | 26 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 26} | 27 | 1 |
| data/raw/st-jacobstraat/Hoofd.pdf | DOC-008 | 15 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 15} | 4 | — |
| data/raw/st-jacobstraat/Woningen.pdf | DOC-009 | 30 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 30} | 5 | 1 |
| data/raw/zomerdijkstraat-14/Meerjarenonderhoudsplan 2023_VvE Zomerdijkstraat 14.pdf | DOC-010 | 17 | MJOP_REPORT_ONLY | {"MJOP_REPORT_ONLY": 17} | 24 | 1 |

## Niet-PDF tekeningachtige bestanden

- data/photos/incoming/maldenhof/maldenhof_1.jpg
- data/photos/incoming/maldenhof/maldenhof_2.jpg
- data/photos/incoming/maldenhof/maldenhof_3.jpg
- reports/frames/photo_review_v1/maldenhof_2_frame_overlay.png
- reports/quantity/facade_poc_v2_review_images/round_A_sheet1.jpg
- reports/quantity/facade_poc_v2_review_images/round_A_sheet2.jpg
- reports/quantity/facade_poc_v2_review_images/round_A_sheet3.jpg
- reports/quantity/facade_poc_v2_review_images/round_A_sheet4.jpg
- reports/quantity/facade_poc_v2_review_images/round_B_B1.jpg
- reports/quantity/facade_poc_v2_review_images/round_B_B2.jpg
- reports/quantity/facade_poc_v2_review_images/round_B_B3.jpg
- reports/quantity/facade_poc_v2_review_images/round_B_B4.jpg
- reports/quantity/facade_poc_v2_review_images/round_B_B5.jpg

Paginagegevens (primitive-aantallen, labelhits, redenen) per pagina staan in het JSON-rapport.
