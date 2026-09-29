# Semantische candidate review v1

READ-ONLY: geen besluit, geen materiaal, geen kengetal, geen score/ranking/confidence. Verschillen zijn feitelijk gemarkeerd op exacte woordtokens met vaste termlijsten; er wordt NIET uitgesproken dat verschillen vergelijkbaar of onvergelijkbaar zijn. Family-ids met status INDICATIVE_AFTER_MATERIAL_DECISION komen uit kengetal_readiness_v1 (gesimuleerd materiaalbesluit).

Termlijsten: FINISH_SYSTEM: dekkend, transparant, beits, beitsen, beitswerk, lak, lakken, lakwerk, vernis, olie, coating, blank; MATERIAL: hout, houten, multiplex, stucwerk, metaal, staal, aluminium, kunststof, beton, steen, zink, pvc, glas, trespa; COMPONENT: kozijn, kozijnen, raam, ramen, deur, deuren, draaiende, delen, panelen, gevelbekleding, boeiboord, boeiboorden, boeidelen, leuning, leuningen, puivulling, pui, puien, entreepuien, balkonkastdeuren, plafond, plafonds, dakoverstek, hekwerk, lijsten, luiken, dakrand, betonconstructie, diversen; LOCATION: entree, berging, bergingen, trappenhuis, gevel, gevels, balkon, balkons, galerij, portiek; ACTION: groot, klein, schilderwerk, binnenschilderwerk, buitenschilderwerk, bijwerken, reinigen, herstel, onderhoud, vervangen; FACADE_SIDE: achter, achtergevel, achterzijde, voor, voorgevel, voorzijde.

## Werklijst

| # | groep | categorie | menselijke acties |
|---|---|---|---|
| 1 | 4645|interior_painting|m2|wood | CLEAR_MAINTENANCE_CONTENT_DIFFERENCES | 6 |
| 2 | 4632|interior_painting|m2|wood | CLEAR_MAINTENANCE_CONTENT_DIFFERENCES | 9 |
| 3 | 4622|interior_painting|m2|wood | CLEAR_MAINTENANCE_CONTENT_DIFFERENCES | 11 |
| 4 | 4631|exterior_painting|m2|wood | CLEAR_MAINTENANCE_CONTENT_DIFFERENCES | 18 |
| 5 | 4621|exterior_painting|m2|wood | CLEAR_MAINTENANCE_CONTENT_DIFFERENCES | 30 |

## 4645|interior_painting|m2|wood - CLEAR_MAINTENANCE_CONTENT_DIFFERENCES

- onafhankelijke clusters 3; materiaalgoedkeuringen 3; reviewfamilies 3; menselijke acties 6
- paren 3: exact dezelfde semantiek 0, beperkte tekstvariant 0, duidelijk inhoudelijk verschil 3
- gesimuleerd kengetal (alles positief): AVAILABLE mediaan 45.81, min 44.18, max 54.45, 3 clusters
- prijspeil 1-3-2023 - 1-4-2024; hoeveelheid 12.90 - 580.00

Verschillen die menselijke beoordeling vereisen (CONTRAST):

- FINISH_SYSTEM: dekkend vs transparant (PAIR-00531, PAIR-00533)
- MATERIAL: hout multiplex vs hout stucwerk (PAIR-00529)

Algemeen vs specifiek (ONE_SIDED, ter controle):

- MATERIAL: hout vs hout multiplex (PAIR-00531)
- MATERIAL: hout vs hout stucwerk (PAIR-00533)

### Observations

| observation | document | cluster | object | actie | bron | materiaal nu/voorgesteld | eenheid | hoeveelheid | prijs/uitv. | prijspeil | cyclus | caveats |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-006-P015-L059 | DOC-006 | SC-DOC-005+DOC-006 | Binnenschilderwerk plafond hout (multiplex) dekkend | Groot schilderwerk plafond hout dekkend | p15 r59: `Groot schilderwerk plafond hout 85,70 m2 2032 12 4.666 4.666` | - / wood | m2 | 85.70 | 54.45 | 1-3-2023 | 2032/12 | MATERIAL_UNKNOWN |
| PO-DOC-007-P017-L097 | DOC-007 | SC-DOC-007 | Binnenschilderwerk plafond hout / stucwerk dekkend | Groot schilderwerk plafond hout dekkend | p17 r97: `Groot schilderwerk plafond hout 580,00 m2 2030 14 25.623 25.623` | - / wood | m2 | 580.00 | 44.18 | 28-4-2023 | 2030/14 | MATERIAL_UNKNOWN |
| PO-DOC-012-P014-L085 | DOC-012 | SC-DOC-012 | Binnenschilderwerk plafond hout transparant | Groot schilderwerk plafond hout transparant | p14 r85: `Groot schilderwerk plafond hout 12,90 m2 2027 18 591 591` | - / wood | m2 | 12.90 | 45.81 | 1-4-2024 | 2027/18 | MATERIAL_UNKNOWN |

### Paren

| paar | familie | system_class | unknown_reasons | hard | paarcaveats | object alleen a / b | actie alleen a / b | materiaal | hoeveelheid | prijspeil | prijs | klasse | inhoudelijke verschillen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAIR-00529 | RF-4645-f273568c78 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | - | multiplex / stucwerk | - / - | wood / wood | 85.70 / 580.00 | 1-3-2023 / 28-4-2023 | 54.45 / 44.18 | SUBSTANTIVE_DIFFERENCE | MATERIAL: hout multiplex vs hout stucwerk |
| PAIR-00531 | RF-4645-9ac13fa8d5 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | dekkend multiplex / transparant | dekkend / transparant | wood / wood | 85.70 / 12.90 | 1-3-2023 / 1-4-2024 | 54.45 / 45.81 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant |
| PAIR-00533 | RF-4645-203095b1cf (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | dekkend stucwerk / transparant | dekkend / transparant | wood / wood | 580.00 / 12.90 | 28-4-2023 / 1-4-2024 | 44.18 / 45.81 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant |

## 4632|interior_painting|m2|wood - CLEAR_MAINTENANCE_CONTENT_DIFFERENCES

- onafhankelijke clusters 4; materiaalgoedkeuringen 2; reviewfamilies 7; menselijke acties 9
- paren 9: exact dezelfde semantiek 0, beperkte tekstvariant 3, duidelijk inhoudelijk verschil 6
- gesimuleerd kengetal (alles positief): AVAILABLE mediaan 40.53, min 37.25, max 44.18, 4 clusters
- prijspeil 28-4-2023 - 20-8-2026; hoeveelheid 23.76 - 360.92

Verschillen die menselijke beoordeling vereisen (CONTRAST):

- COMPONENT: delen draaiende kozijn vs deuren kozijn raam (PAIR-00433, PAIR-00439)
- COMPONENT: delen draaiende kozijn vs deuren kozijn raam ramen (PAIR-00432, PAIR-00438)
- COMPONENT: delen draaiende kozijn vs kozijn raam (PAIR-00434, PAIR-00440)

Algemeen vs specifiek (ONE_SIDED, ter controle):

- COMPONENT: deuren kozijn raam ramen vs kozijn raam (PAIR-00442)
- COMPONENT: deuren kozijn raam vs deuren kozijn raam ramen (PAIR-00441)
- COMPONENT: deuren kozijn raam vs kozijn raam (PAIR-00443)
- LOCATION: - vs entree trappenhuis (PAIR-00433, PAIR-00439, PAIR-00441, PAIR-00443)

### Observations

| observation | document | cluster | object | actie | bron | materiaal nu/voorgesteld | eenheid | hoeveelheid | prijs/uitv. | prijspeil | cyclus | caveats |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-002-P019-L019 | DOC-002 | SC-DOC-002 | Binnenschilderwerk kozijn en draaiende delen hout dekkend | Groot schilderwerk kozijn en draaiende delen hout dekkend | p19 r19: `Groot schilderwerk kozijn en 48,00 m2 2036 12 1.831 1.831` | wood / - | m2 | 48.00 | 38.15 | 20-8-2026 | 2036/12 | - |
| PO-DOC-002-P019-L035 | DOC-002 | SC-DOC-002 | Binnenschilderwerk kozijn en draaiende delen hout dekkend | Groot schilderwerk kozijn en draaiende delen hout dekkend | p19 r35: `Groot schilderwerk kozijn en 35,00 m2 2036 12 1.717 1.717` | wood / - | m2 | 35.00 | 49.06 | 20-8-2026 | 2036/12 | - |
| PO-DOC-007-P017-L055 | DOC-007 | SC-DOC-007 | Binnenschilderwerk kozijn,ramen en deuren hout dekkend | Groot schilderwerk kozijn&raam hout dekkend | p17 r55: `Groot schilderwerk kozijn&raam hout 360,92 m2 2030 14 15.945 15.945` | wood / - | m2 | 360.92 | 44.18 | 28-4-2023 | 2030/14 | - |
| PO-DOC-012-P014-L063 | DOC-012 | SC-DOC-012 | Binnenschilderwerk kozijn en deuren hout dekkend trappenhuis en entree | Groot schilderwerk kozijn&raam hout dekkend | p14 r63: `Groot schilderwerk kozijn&raam hout 129,36 m2 2027 12 4.846 4.846` | - / wood | m2 | 129.36 | 37.46 | 1-4-2024 | 2027/12 | MATERIAL_UNKNOWN |
| PO-DOC-013-P020-L019 | DOC-013 | SC-DOC-013 | Binnenschilderwerk kozijn en raam hout dekkend | Groot schilderwerk kozijn en raam hout dekkend | p20 r19: `Groot schilderwerk kozijn en raam 23,76 m2 2031 21 885 885` | - / wood | m2 | 23.76 | 37.25 | 14-7-2026 | 2031/21 | MATERIAL_UNKNOWN |

### Paren

| paar | familie | system_class | unknown_reasons | hard | paarcaveats | object alleen a / b | actie alleen a / b | materiaal | hoeveelheid | prijspeil | prijs | klasse | inhoudelijke verschillen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAIR-00432 | RF-4632-611a2f74bf (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | delen draaiende / deuren ramen | delen draaiende en / raam | wood / wood | 48.00 / 360.92 | 20-8-2026 / 28-4-2023 | 38.15 / 44.18 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs deuren kozijn raam ramen |
| PAIR-00433 | RF-4632-db0fe26fd7 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | delen draaiende / deuren entree trappenhuis | delen draaiende en / raam | wood / wood | 48.00 / 129.36 | 20-8-2026 / 1-4-2024 | 38.15 / 37.46 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs deuren kozijn raam |
| PAIR-00434 | RF-4632-85a71e1609 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | delen draaiende / raam | delen draaiende / raam | wood / wood | 48.00 / 23.76 | 20-8-2026 / 14-7-2026 | 38.15 / 37.25 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00438 | RF-4632-52d231366e (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | delen draaiende / deuren ramen | delen draaiende en / raam | wood / wood | 35.00 / 360.92 | 20-8-2026 / 28-4-2023 | 49.06 / 44.18 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs deuren kozijn raam ramen |
| PAIR-00439 | RF-4632-db0fe26fd7 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | delen draaiende / deuren entree trappenhuis | delen draaiende en / raam | wood / wood | 35.00 / 129.36 | 20-8-2026 / 1-4-2024 | 49.06 / 37.46 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs deuren kozijn raam |
| PAIR-00440 | RF-4632-85a71e1609 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | delen draaiende / raam | delen draaiende / raam | wood / wood | 35.00 / 23.76 | 20-8-2026 / 14-7-2026 | 49.06 / 37.25 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00441 | RF-4632-db2353a39c (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | ramen / entree trappenhuis | - / - | wood / wood | 360.92 / 129.36 | 28-4-2023 / 1-4-2024 | 44.18 / 37.46 | LIMITED_TEXT_VARIANT | - |
| PAIR-00442 | RF-4632-fd803a49c6 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | deuren ramen / raam | - / en | wood / wood | 360.92 / 23.76 | 28-4-2023 / 14-7-2026 | 44.18 / 37.25 | LIMITED_TEXT_VARIANT | - |
| PAIR-00443 | RF-4632-9358a3b02a (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | deuren entree trappenhuis / raam | - / en | wood / wood | 129.36 / 23.76 | 1-4-2024 / 14-7-2026 | 37.46 / 37.25 | LIMITED_TEXT_VARIANT | - |

## 4622|interior_painting|m2|wood - CLEAR_MAINTENANCE_CONTENT_DIFFERENCES

- onafhankelijke clusters 5; materiaalgoedkeuringen 1; reviewfamilies 10; menselijke acties 11
- paren 14: exact dezelfde semantiek 0, beperkte tekstvariant 4, duidelijk inhoudelijk verschil 10
- gesimuleerd kengetal (alles positief): AVAILABLE mediaan 46.52, min 39.60, max 86.26, 5 clusters
- prijspeil 1-4-2023 - 20-8-2026 (1 zonder prijspeil); hoeveelheid 2.50 - 120.96

Verschillen die menselijke beoordeling vereisen (CONTRAST):

- COMPONENT: deur vs diversen (PAIR-00335)
- COMPONENT: deur vs leuningen (PAIR-00308)
- COMPONENT: deur vs panelen (PAIR-00257, PAIR-00279)
- COMPONENT: diversen vs leuningen (PAIR-00307)
- COMPONENT: diversen vs panelen (PAIR-00256, PAIR-00278)
- COMPONENT: leuningen vs panelen (PAIR-00250, PAIR-00272)
- FINISH_SYSTEM: dekkend vs transparant (PAIR-00250, PAIR-00272, PAIR-00304, PAIR-00307, PAIR-00308)

Algemeen vs specifiek (ONE_SIDED, ter controle):

- COMPONENT: - vs deur (PAIR-00326)
- COMPONENT: - vs diversen (PAIR-00325)
- COMPONENT: - vs leuningen (PAIR-00304)
- COMPONENT: - vs panelen (PAIR-00253, PAIR-00275)
- LOCATION: - vs bergingen entree (PAIR-00253, PAIR-00275, PAIR-00304, PAIR-00325, PAIR-00326)

### Observations

| observation | document | cluster | object | actie | bron | materiaal nu/voorgesteld | eenheid | hoeveelheid | prijs/uitv. | prijspeil | cyclus | caveats |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-002-P018-L045 | DOC-002 | SC-DOC-002 | Binnenschilderwerk panelen hout dekkend | Groot schilderwerk panelen hout dekkend | p18 r45: `Groot schilderwerk panelen hout 2,50 m2 2030 12 136 136` | wood / - | m2 | 2.50 | 54.40 | 20-8-2026 | 2030/12 | - |
| PO-DOC-002-P018-L077 | DOC-002 | SC-DOC-002 | Binnenschilderwerk panelen hout dekkend | Groot schilderwerk panelen hout dekkend | p18 r77: `Groot schilderwerk panelen hout 2,50 m2 2030 12 136 136` | wood / - | m2 | 2.50 | 54.40 | 20-8-2026 | 2030/12 | - |
| PO-DOC-007-P017-L019 | DOC-007 | SC-DOC-007 | Binnenschilderwerk leuningen hout transparant | Groot schilderwerk leuningen | p17 r19: `Groot schilderwerk leuningen 13,20 m2 2028 8 614 614 1.229` | wood / - | m2 | 13.20 | 46.52 | 28-4-2023 | 2028/8 | - |
| PO-DOC-009-P020-L041 | DOC-009 | SC-DOC-008+DOC-009 | Binnenschilderwerk hout dekkend entree bergingen | Groot schilderwerk hout dekkend | p20 r41: `Groot schilderwerk hout dekkend 62,00 m2 2029 18 2.455 2.455` | wood / - | m2 | 62.00 | 39.60 | 21-4-2025 | 2029/18 | - |
| PO-DOC-010-P012-L023 | DOC-010 | SC-DOC-010 | Binnenschilderwerk diversen hout dekkend | Groot schilderwerk hout dekkend | p12 r23: `Groot schilderwerk hout dekkend 30,05 m2 2030 12 1.207 1.207` | wood / - | m2 | 30.05 | 40.17 | 1-4-2023 | 2030/12 | - |
| PO-DOC-011-P020-L091 | DOC-011 | SC-DOC-011 | Binnenschilderwerk deur hout dekkend | Groot schilderwerk deur hout dekkend | p20 r91: `Groot schilderwerk deur hout 120,96 m2 2029 12 10.434 10.434` | - / wood | m2 | 120.96 | 86.26 | - | 2029/12 | MATERIAL_UNKNOWN, PRICE_LEVEL_ABSENT |

### Paren

| paar | familie | system_class | unknown_reasons | hard | paarcaveats | object alleen a / b | actie alleen a / b | materiaal | hoeveelheid | prijspeil | prijs | klasse | inhoudelijke verschillen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAIR-00250 | RF-4622-6a5b692ee7 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | dekkend panelen / leuningen transparant | dekkend hout panelen / leuningen | wood / wood | 2.50 / 13.20 | 20-8-2026 / 28-4-2023 | 54.40 / 46.52 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant; COMPONENT: leuningen vs panelen |
| PAIR-00253 | RF-4622-11d576c7dc (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | panelen / bergingen entree | panelen / - | wood / wood | 2.50 / 62.00 | 20-8-2026 / 21-4-2025 | 54.40 / 39.60 | LIMITED_TEXT_VARIANT | - |
| PAIR-00256 | RF-4622-46a974b31b (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | panelen / diversen | panelen / - | wood / wood | 2.50 / 30.05 | 20-8-2026 / 1-4-2023 | 54.40 / 40.17 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs panelen |
| PAIR-00257 | RF-4622-65dd31a8d3 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | panelen / deur | panelen / deur | wood / wood | 2.50 / 120.96 | 20-8-2026 / - | 54.40 / 86.26 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs panelen |
| PAIR-00272 | RF-4622-6a5b692ee7 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | dekkend panelen / leuningen transparant | dekkend hout panelen / leuningen | wood / wood | 2.50 / 13.20 | 20-8-2026 / 28-4-2023 | 54.40 / 46.52 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant; COMPONENT: leuningen vs panelen |
| PAIR-00275 | RF-4622-11d576c7dc (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | panelen / bergingen entree | panelen / - | wood / wood | 2.50 / 62.00 | 20-8-2026 / 21-4-2025 | 54.40 / 39.60 | LIMITED_TEXT_VARIANT | - |
| PAIR-00278 | RF-4622-46a974b31b (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | panelen / diversen | panelen / - | wood / wood | 2.50 / 30.05 | 20-8-2026 / 1-4-2023 | 54.40 / 40.17 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs panelen |
| PAIR-00279 | RF-4622-65dd31a8d3 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | panelen / deur | panelen / deur | wood / wood | 2.50 / 120.96 | 20-8-2026 / - | 54.40 / 86.26 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs panelen |
| PAIR-00304 | RF-4622-8cf1dacd6d (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | leuningen transparant / bergingen dekkend entree | leuningen / dekkend hout | wood / wood | 13.20 / 62.00 | 28-4-2023 / 21-4-2025 | 46.52 / 39.60 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant |
| PAIR-00307 | RF-4622-354fcb80f6 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | leuningen transparant / dekkend diversen | leuningen / dekkend hout | wood / wood | 13.20 / 30.05 | 28-4-2023 / 1-4-2023 | 46.52 / 40.17 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant; COMPONENT: diversen vs leuningen |
| PAIR-00308 | RF-4622-034f0e58c7 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | leuningen transparant / dekkend deur | leuningen / dekkend deur hout | wood / wood | 13.20 / 120.96 | 28-4-2023 / - | 46.52 / 86.26 | SUBSTANTIVE_DIFFERENCE | FINISH_SYSTEM: dekkend vs transparant; COMPONENT: deur vs leuningen |
| PAIR-00325 | RF-4622-a30aa9fefe (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | bergingen entree / diversen | - / - | wood / wood | 62.00 / 30.05 | 21-4-2025 / 1-4-2023 | 39.60 / 40.17 | LIMITED_TEXT_VARIANT | - |
| PAIR-00326 | RF-4622-51cb0dd068 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | bergingen entree / deur | - / deur | wood / wood | 62.00 / 120.96 | 21-4-2025 / - | 39.60 / 86.26 | LIMITED_TEXT_VARIANT | - |
| PAIR-00335 | RF-4622-66494f8df6 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | diversen / deur | - / deur | wood / wood | 30.05 / 120.96 | 1-4-2023 / - | 40.17 / 86.26 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs diversen |

## 4631|exterior_painting|m2|wood - CLEAR_MAINTENANCE_CONTENT_DIFFERENCES

- onafhankelijke clusters 6; materiaalgoedkeuringen 3; reviewfamilies 15; menselijke acties 18
- paren 20: exact dezelfde semantiek 0, beperkte tekstvariant 14, duidelijk inhoudelijk verschil 6
- gesimuleerd kengetal (alles positief): AVAILABLE mediaan 58.47, min 51.76, max 136.25, 6 clusters
- prijspeil 1-3-2023 - 14-7-2026 (2 zonder prijspeil); hoeveelheid 18.70 - 756.80

Verschillen die menselijke beoordeling vereisen (CONTRAST):

- COMPONENT: delen draaiende kozijn vs deur kozijn raam (PAIR-00408)
- COMPONENT: delen draaiende kozijn vs kozijn raam (PAIR-00406, PAIR-00407, PAIR-00410, PAIR-00411, PAIR-00412)

Algemeen vs specifiek (ONE_SIDED, ter controle):

- COMPONENT: deur kozijn raam vs kozijn raam (PAIR-00413, PAIR-00418, PAIR-00423, PAIR-00424, PAIR-00425)
- LOCATION: - vs bergingen (PAIR-00410, PAIR-00415, PAIR-00420, PAIR-00423, PAIR-00429, PAIR-00430)

### Observations

| observation | document | cluster | object | actie | bron | materiaal nu/voorgesteld | eenheid | hoeveelheid | prijs/uitv. | prijspeil | cyclus | caveats |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-006-P015-L049 | DOC-006 | SC-DOC-005+DOC-006 | Buitenschilderwerk kozijn hout dekkend | Groot schilderwerk kozijn (en draaiende delen) hout dekkend (conform PO cyclus) | p15 r49: `Groot schilderwerk kozijn (en 756,80 m2 2032 7 40.237 40.237` | wood / - | m2 | 756.80 | 53.17 | 1-3-2023 | 2032/7 | - |
| PO-DOC-007-P017-L043 | DOC-007 | SC-DOC-007 | Buitenschilderwerk kozijn&raam hout dekkend | Groot schilderwerk kozijn & raam hout dekkend achterzijde | p17 r43: `Groot schilderwerk kozijn & raam 391,30 m2 2028 7 22.217 22.217 44.435` | wood / - | m2 | 391.30 | 56.78 | 28-4-2023 | 2028/7 | - |
| PO-DOC-007-P017-L047 | DOC-007 | SC-DOC-007 | Buitenschilderwerk kozijn&raam hout dekkend | Groot schilderwerk kozijn & raam hout dekkend voorzijde | p17 r47: `Groot schilderwerk kozijn & raam 391,30 m2 2028 7 22.217 22.217 44.435` | wood / - | m2 | 391.30 | 56.78 | 28-4-2023 | 2028/7 | - |
| PO-DOC-009-P020-L093 | DOC-009 | SC-DOC-008+DOC-009 | Buitenschilderwerk kozijn,raam en deur hout dekkend achtergevel | Groot schilderwerk kozijn en raam hout dekkend | p20 r93: `Groot schilderwerk kozijn en raam 53,52 m2 2032 7 3.255 3.255 6.510` | wood / - | m2 | 53.52 | 60.82 | 21-4-2025 | 2032/7 | - |
| PO-DOC-011-P021-L025 | DOC-011 | SC-DOC-011 | Buitenschilderwerk kozijn&raam hout dekkend m2 bergingen | Groot schilderwerk kozijn & raam hout dekkend | p21 r25: `Groot schilderwerk kozijn & raam 18,70 m2 2025 8 968 968 1.936` | - / wood | m2 | 18.70 | 51.76 | - | 2025/8 | MATERIAL_UNKNOWN, PRICE_LEVEL_ABSENT |
| PO-DOC-013-P018-L069 | DOC-013 | SC-DOC-013 | Buitenschilderwerk kozijn en raam hout dekkend | Groot schilderwerk kozijn en raam hout dekkend | p18 r69: `Groot schilderwerk kozijn en raam 106,90 m2 2033 7 14.565 14.565 29.130` | - / wood | m2 | 106.90 | 136.25 | 14-7-2026 | 2033/7 | MATERIAL_UNKNOWN |
| PO-DOC-015-S01-R0113 | DOC-015 | SC-DOC-015 | Buitenschilderwerk kozijn&raam hout dekkend m2 | Groot schilderwerk kozijn & raam hout dekkend | Sheet r113: `Groot schilderwerk kozijn & raam hout dekkend | 630 | m2 | 2028 | 7 | 0 | 0 | 0 | 0 | 37905.84 | 0 | 0 | 0 | 0 | 0 | 0 | 37905.84 | 0 | 0 | 0 | 75811.68` | - / wood | m2 | 630 | 60.17 | - | 2028/7 | MATERIAL_UNKNOWN, PRICE_LEVEL_ABSENT |

### Paren

| paar | familie | system_class | unknown_reasons | hard | paarcaveats | object alleen a / b | actie alleen a / b | materiaal | hoeveelheid | prijspeil | prijs | klasse | inhoudelijke verschillen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAIR-00406 | RF-4631-5f58c3592f (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | - / raam | conform cyclus delen draaiende en po / achterzijde raam | wood / wood | 756.80 / 391.30 | 1-3-2023 / 28-4-2023 | 53.17 / 56.78 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00407 | RF-4631-5f58c3592f (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | - / raam | conform cyclus delen draaiende en po / raam voorzijde | wood / wood | 756.80 / 391.30 | 1-3-2023 / 28-4-2023 | 53.17 / 56.78 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00408 | RF-4631-e554146912 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | - / achtergevel deur en raam | conform cyclus delen draaiende po / raam | wood / wood | 756.80 / 53.52 | 1-3-2023 / 21-4-2025 | 53.17 / 60.82 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs deur kozijn raam |
| PAIR-00410 | RF-4631-5023971a0d (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | - / bergingen m2 raam | conform cyclus delen draaiende en po / raam | wood / wood | 756.80 / 18.70 | 1-3-2023 / - | 53.17 / 51.76 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00411 | RF-4631-01fabc7da5 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | - / en raam | conform cyclus delen draaiende po / raam | wood / wood | 756.80 / 106.90 | 1-3-2023 / 14-7-2026 | 53.17 / 136.25 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00412 | RF-4631-b42c8dd8c1 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | - / m2 raam | conform cyclus delen draaiende en po / raam | wood / wood | 756.80 / 630 | 1-3-2023 / - | 53.17 / 60.17 | SUBSTANTIVE_DIFFERENCE | COMPONENT: delen draaiende kozijn vs kozijn raam |
| PAIR-00413 | RF-4631-8b375feff1 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | - / achtergevel deur en | achterzijde / en | wood / wood | 391.30 / 53.52 | 28-4-2023 / 21-4-2025 | 56.78 / 60.82 | LIMITED_TEXT_VARIANT | - |
| PAIR-00415 | RF-4631-625ee73b91 (CURRENT:OPEN_NO_DECISION) | COMPARABLE_WITH_CAVEATS | - | - | ACTION_TEXT_VARIANT, GENERIC_VS_SPECIFIC_OBJECT, QUANTITY_SCALE_DIFFERENCE | - / bergingen m2 | achterzijde / - | wood / wood | 391.30 / 18.70 | 28-4-2023 / - | 56.78 / 51.76 | LIMITED_TEXT_VARIANT | - |
| PAIR-00416 | RF-4631-ef2eeb54f2 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | - / en | achterzijde / en | wood / wood | 391.30 / 106.90 | 28-4-2023 / 14-7-2026 | 56.78 / 136.25 | LIMITED_TEXT_VARIANT | - |
| PAIR-00417 | RF-4631-5b3207f54b (CURRENT:OPEN_NO_DECISION) | COMPARABLE_WITH_CAVEATS | - | - | ACTION_TEXT_VARIANT, GENERIC_VS_SPECIFIC_OBJECT | - / m2 | achterzijde / - | wood / wood | 391.30 / 630 | 28-4-2023 / - | 56.78 / 60.17 | LIMITED_TEXT_VARIANT | - |
| PAIR-00418 | RF-4631-8b375feff1 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | - / achtergevel deur en | voorzijde / en | wood / wood | 391.30 / 53.52 | 28-4-2023 / 21-4-2025 | 56.78 / 60.82 | LIMITED_TEXT_VARIANT | - |
| PAIR-00420 | RF-4631-625ee73b91 (CURRENT:OPEN_NO_DECISION) | COMPARABLE_WITH_CAVEATS | - | - | ACTION_TEXT_VARIANT, GENERIC_VS_SPECIFIC_OBJECT, QUANTITY_SCALE_DIFFERENCE | - / bergingen m2 | voorzijde / - | wood / wood | 391.30 / 18.70 | 28-4-2023 / - | 56.78 / 51.76 | LIMITED_TEXT_VARIANT | - |
| PAIR-00421 | RF-4631-ef2eeb54f2 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | - / en | voorzijde / en | wood / wood | 391.30 / 106.90 | 28-4-2023 / 14-7-2026 | 56.78 / 136.25 | LIMITED_TEXT_VARIANT | - |
| PAIR-00422 | RF-4631-5b3207f54b (CURRENT:OPEN_NO_DECISION) | COMPARABLE_WITH_CAVEATS | - | - | ACTION_TEXT_VARIANT, GENERIC_VS_SPECIFIC_OBJECT | - / m2 | voorzijde / - | wood / wood | 391.30 / 630 | 28-4-2023 / - | 56.78 / 60.17 | LIMITED_TEXT_VARIANT | - |
| PAIR-00423 | RF-4631-cf6bdf3a4a (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | achtergevel deur en / bergingen m2 | en / - | wood / wood | 53.52 / 18.70 | 21-4-2025 / - | 60.82 / 51.76 | LIMITED_TEXT_VARIANT | - |
| PAIR-00424 | RF-4631-7510f90c47 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | achtergevel deur / - | - / - | wood / wood | 53.52 / 106.90 | 21-4-2025 / 14-7-2026 | 60.82 / 136.25 | LIMITED_TEXT_VARIANT | - |
| PAIR-00425 | RF-4631-c8411da63d (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | achtergevel deur en / m2 | en / - | wood / wood | 53.52 / 630 | 21-4-2025 / - | 60.82 / 60.17 | LIMITED_TEXT_VARIANT | - |
| PAIR-00429 | RF-4631-1acde90dae (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | bergingen m2 / en | - / en | wood / wood | 18.70 / 106.90 | - / 14-7-2026 | 51.76 / 136.25 | LIMITED_TEXT_VARIANT | - |
| PAIR-00430 | RF-4631-0514ebe15e (CURRENT:OPEN_NO_DECISION) | COMPARABLE_WITH_CAVEATS | - | - | GENERIC_VS_SPECIFIC_OBJECT, QUANTITY_SCALE_DIFFERENCE | bergingen / - | - / - | wood / wood | 18.70 / 630 | - / - | 51.76 / 60.17 | LIMITED_TEXT_VARIANT | - |
| PAIR-00431 | RF-4631-a03802a83b (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | en / m2 | en / - | wood / wood | 106.90 / 630 | 14-7-2026 / - | 136.25 / 60.17 | LIMITED_TEXT_VARIANT | - |

## 4621|exterior_painting|m2|wood - CLEAR_MAINTENANCE_CONTENT_DIFFERENCES

- onafhankelijke clusters 7; materiaalgoedkeuringen 3; reviewfamilies 27; menselijke acties 30
- paren 33: exact dezelfde semantiek 0, beperkte tekstvariant 2, duidelijk inhoudelijk verschil 31
- gesimuleerd kengetal (alles positief): AVAILABLE mediaan 53.17, min 36.62, max 92.75, 7 clusters
- prijspeil 1-3-2023 - 20-8-2026 (2 zonder prijspeil); hoeveelheid 1.00 - 1425.95

Verschillen die menselijke beoordeling vereisen (CONTRAST):

- COMPONENT: balkonkastdeuren entreepuien puivulling vs boeiboord (PAIR-00241)
- COMPONENT: balkonkastdeuren entreepuien puivulling vs deur (PAIR-00068)
- COMPONENT: balkonkastdeuren entreepuien puivulling vs diversen (PAIR-00230, PAIR-00240)
- COMPONENT: balkonkastdeuren entreepuien puivulling vs gevelbekleding (PAIR-00118, PAIR-00225)
- COMPONENT: balkonkastdeuren entreepuien puivulling vs panelen (PAIR-00142, PAIR-00154)
- COMPONENT: boeiboord vs deur (PAIR-00072)
- COMPONENT: boeiboord vs diversen (PAIR-00234, PAIR-00246)
- COMPONENT: boeiboord vs gevelbekleding (PAIR-00122, PAIR-00229)
- COMPONENT: boeiboord vs panelen (PAIR-00146, PAIR-00158)
- COMPONENT: deur vs diversen (PAIR-00066, PAIR-00071)
- COMPONENT: deur vs gevelbekleding (PAIR-00054, PAIR-00065)
- COMPONENT: deur vs panelen (PAIR-00056, PAIR-00057)
- COMPONENT: diversen vs gevelbekleding (PAIR-00116, PAIR-00121, PAIR-00223, PAIR-00228)
- COMPONENT: diversen vs panelen (PAIR-00140, PAIR-00145, PAIR-00152, PAIR-00157)
- COMPONENT: gevelbekleding vs panelen (PAIR-00139, PAIR-00151)

Algemeen vs specifiek (ONE_SIDED, ter controle):

- LOCATION: - vs gevels (PAIR-00071, PAIR-00121, PAIR-00145, PAIR-00157, PAIR-00228, PAIR-00233, PAIR-00240, PAIR-00246)

### Observations

| observation | document | cluster | object | actie | bron | materiaal nu/voorgesteld | eenheid | hoeveelheid | prijs/uitv. | prijspeil | cyclus | caveats |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PO-DOC-001-P025-L025 | DOC-001 | SC-DOC-001 | Buitenschilderwerk deur hout dekkend | Groot schilderwerk deur hout dekkend | p25 r25: `Groot schilderwerk deur hout 293,60 m2 2022 7 10.753 10.753 10.753 32.258` | wood / - | m2 | 293.60 | 36.62 | - | 2022/7 | PRICE_LEVEL_ABSENT |
| PO-DOC-002-P017-L045 | DOC-002 | SC-DOC-002 | Buitenschilderwerk gevelbekleding hout dekkend | Groot schilderwerk hout dekkend | p17 r45: `Groot schilderwerk hout dekkend 2,00 m2 2030 6 85 85 169` | wood / - | m2 | 2.00 | 42.50 | 20-8-2026 | 2030/6 | - |
| PO-DOC-002-P017-L109 | DOC-002 | SC-DOC-002 | Buitenschilderwerk panelen hout dekkend | Groot schilderwerk hout dekkend | p17 r109: `Groot schilderwerk hout dekkend 1,00 m2 2030 6 42 42 85` | wood / - | m2 | 1.00 | 42.00 | 20-8-2026 | 2030/6 | - |
| PO-DOC-002-P017-L115 | DOC-002 | SC-DOC-002 | Buitenschilderwerk panelen hout dekkend | Groot schilderwerk hout dekkend | p17 r115: `Groot schilderwerk hout dekkend 1,00 m2 2030 6 42 42 85` | wood / - | m2 | 1.00 | 42.00 | 20-8-2026 | 2030/6 | - |
| PO-DOC-006-P015-L009 | DOC-006 | SC-DOC-005+DOC-006 | Buitenschilderwerk gevelbekleding hout | Groot schilderwerk gevelbekleding hout dekkend | p15 r9: `Groot schilderwerk gevelbekleding 332,00 m2 2032 7 17.652 17.652` | wood / - | m2 | 332.00 | 53.17 | 1-3-2023 | 2032/7 | - |
| PO-DOC-010-P011-L085 | DOC-010 | SC-DOC-010 | Buitenschilderwerk diversen hout dekkend | Groot schilderwerk hout dekkend | p11 r85: `Groot schilderwerk hout dekkend 4,13 m2 2028 6 207 207 415` | wood / - | m2 | 4.13 | 50.12 | 1-4-2023 | 2028/6 | - |
| PO-DOC-011-P020-L067 | DOC-011 | SC-DOC-011 | Buitenschilderwerk hout dekkend (entreepuien, balkonkastdeuren) | Groot schilderwerk puivulling hout dekkend | p20 r67: `Groot schilderwerk puivulling hout 43,10 m2 2028 8 2.838 2.838` | - / wood | m2 | 43.10 | 65.85 | - | 2028/8 | MATERIAL_UNKNOWN, PRICE_LEVEL_ABSENT |
| PO-DOC-012-P014-L013 | DOC-012 | SC-DOC-012 | Buitenschilderwerk diversen hout dekkend ( alle gevels ) | Groot schilderwerk hout dekkend | p14 r13: `Groot schilderwerk hout dekkend 1425,95 m2 2025 6 82.626 82.626 82.626 247.877` | - / wood | m2 | 1425.95 | 57.94 | 1-4-2024 | 2025/6 | MATERIAL_UNKNOWN |
| PO-DOC-013-P018-L059 | DOC-013 | SC-DOC-013 | Buitenschilderwerk boeiboord hout dekkend | Groot schilderwerk boeiboord hout dekkend | p18 r59: `Groot schilderwerk boeiboord hout 4,14 m2 2026 7 384 384 384 1.151` | - / wood | m2 | 4.14 | 92.75 | 14-7-2026 | 2026/7 | MATERIAL_UNKNOWN |

### Paren

| paar | familie | system_class | unknown_reasons | hard | paarcaveats | object alleen a / b | actie alleen a / b | materiaal | hoeveelheid | prijspeil | prijs | klasse | inhoudelijke verschillen |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PAIR-00054 | RF-4621-004dc9d137 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | deur / gevelbekleding | deur / - | wood / wood | 293.60 / 2.00 | - / 20-8-2026 | 36.62 / 42.50 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs gevelbekleding |
| PAIR-00056 | RF-4621-188ea6a44e (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | deur / panelen | deur / - | wood / wood | 293.60 / 1.00 | - / 20-8-2026 | 36.62 / 42.00 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs panelen |
| PAIR-00057 | RF-4621-188ea6a44e (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | deur / panelen | deur / - | wood / wood | 293.60 / 1.00 | - / 20-8-2026 | 36.62 / 42.00 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs panelen |
| PAIR-00065 | RF-4621-a41aa495eb (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | dekkend deur / gevelbekleding | deur / gevelbekleding | wood / wood | 293.60 / 332.00 | - / 1-3-2023 | 36.62 / 53.17 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs gevelbekleding |
| PAIR-00066 | RF-4621-cab376a22f (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | deur / diversen | deur / - | wood / wood | 293.60 / 4.13 | - / 1-4-2023 | 36.62 / 50.12 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs diversen |
| PAIR-00068 | RF-4621-175e6d6524 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | deur / balkonkastdeuren entreepuien | deur / puivulling | wood / wood | 293.60 / 43.10 | - / - | 36.62 / 65.85 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs deur |
| PAIR-00071 | RF-4621-0f48fdef2d (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | deur / alle diversen gevels | deur / - | wood / wood | 293.60 / 1425.95 | - / 1-4-2024 | 36.62 / 57.94 | SUBSTANTIVE_DIFFERENCE | COMPONENT: deur vs diversen |
| PAIR-00072 | RF-4621-eabdf2ab4e (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | deur / boeiboord | deur / boeiboord | wood / wood | 293.60 / 4.14 | - / 14-7-2026 | 36.62 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs deur |
| PAIR-00115 | RF-4621-907dfd2c65 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | GENERIC_VS_SPECIFIC_OBJECT, PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | dekkend / - | - / gevelbekleding | wood / wood | 2.00 / 332.00 | 20-8-2026 / 1-3-2023 | 42.50 / 53.17 | LIMITED_TEXT_VARIANT | - |
| PAIR-00116 | RF-4621-bb9df7a5d2 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | gevelbekleding / diversen | - / - | wood / wood | 2.00 / 4.13 | 20-8-2026 / 1-4-2023 | 42.50 / 50.12 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs gevelbekleding |
| PAIR-00118 | RF-4621-be79d914a8 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | gevelbekleding / balkonkastdeuren entreepuien | - / puivulling | wood / wood | 2.00 / 43.10 | 20-8-2026 / - | 42.50 / 65.85 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs gevelbekleding |
| PAIR-00121 | RF-4621-4d24de9650 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | gevelbekleding / alle diversen gevels | - / - | wood / wood | 2.00 / 1425.95 | 20-8-2026 / 1-4-2024 | 42.50 / 57.94 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs gevelbekleding |
| PAIR-00122 | RF-4621-d5ea2f46ef (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | gevelbekleding / boeiboord | - / boeiboord | wood / wood | 2.00 / 4.14 | 20-8-2026 / 14-7-2026 | 42.50 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs gevelbekleding |
| PAIR-00139 | RF-4621-af2b890f8f (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | dekkend panelen / gevelbekleding | - / gevelbekleding | wood / wood | 1.00 / 332.00 | 20-8-2026 / 1-3-2023 | 42.00 / 53.17 | SUBSTANTIVE_DIFFERENCE | COMPONENT: gevelbekleding vs panelen |
| PAIR-00140 | RF-4621-df3c57f3ca (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | panelen / diversen | - / - | wood / wood | 1.00 / 4.13 | 20-8-2026 / 1-4-2023 | 42.00 / 50.12 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs panelen |
| PAIR-00142 | RF-4621-75b34f9647 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | panelen / balkonkastdeuren entreepuien | - / puivulling | wood / wood | 1.00 / 43.10 | 20-8-2026 / - | 42.00 / 65.85 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs panelen |
| PAIR-00145 | RF-4621-2b42c09458 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | panelen / alle diversen gevels | - / - | wood / wood | 1.00 / 1425.95 | 20-8-2026 / 1-4-2024 | 42.00 / 57.94 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs panelen |
| PAIR-00146 | RF-4621-5f62f8d61f (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | panelen / boeiboord | - / boeiboord | wood / wood | 1.00 / 4.14 | 20-8-2026 / 14-7-2026 | 42.00 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs panelen |
| PAIR-00151 | RF-4621-af2b890f8f (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | dekkend panelen / gevelbekleding | - / gevelbekleding | wood / wood | 1.00 / 332.00 | 20-8-2026 / 1-3-2023 | 42.00 / 53.17 | SUBSTANTIVE_DIFFERENCE | COMPONENT: gevelbekleding vs panelen |
| PAIR-00152 | RF-4621-df3c57f3ca (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | panelen / diversen | - / - | wood / wood | 1.00 / 4.13 | 20-8-2026 / 1-4-2023 | 42.00 / 50.12 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs panelen |
| PAIR-00154 | RF-4621-75b34f9647 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | panelen / balkonkastdeuren entreepuien | - / puivulling | wood / wood | 1.00 / 43.10 | 20-8-2026 / - | 42.00 / 65.85 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs panelen |
| PAIR-00157 | RF-4621-2b42c09458 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | panelen / alle diversen gevels | - / - | wood / wood | 1.00 / 1425.95 | 20-8-2026 / 1-4-2024 | 42.00 / 57.94 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs panelen |
| PAIR-00158 | RF-4621-5f62f8d61f (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | panelen / boeiboord | - / boeiboord | wood / wood | 1.00 / 4.14 | 20-8-2026 / 14-7-2026 | 42.00 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs panelen |
| PAIR-00223 | RF-4621-8656071600 (CURRENT:OPEN_NO_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | gevelbekleding / dekkend diversen | gevelbekleding / - | wood / wood | 332.00 / 4.13 | 1-3-2023 / 1-4-2023 | 53.17 / 50.12 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs gevelbekleding |
| PAIR-00225 | RF-4621-ebf49919b5 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | - | gevelbekleding / balkonkastdeuren dekkend entreepuien | gevelbekleding / puivulling | wood / wood | 332.00 / 43.10 | 1-3-2023 / - | 53.17 / 65.85 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs gevelbekleding |
| PAIR-00228 | RF-4621-a35f445afa (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | gevelbekleding / alle dekkend diversen gevels | gevelbekleding / - | wood / wood | 332.00 / 1425.95 | 1-3-2023 / 1-4-2024 | 53.17 / 57.94 | SUBSTANTIVE_DIFFERENCE | COMPONENT: diversen vs gevelbekleding |
| PAIR-00229 | RF-4621-0ed4cdf3bf (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | gevelbekleding / boeiboord dekkend | gevelbekleding / boeiboord | wood / wood | 332.00 / 4.14 | 1-3-2023 / 14-7-2026 | 53.17 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs gevelbekleding |
| PAIR-00230 | RF-4621-0e58576565 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | diversen / balkonkastdeuren entreepuien | - / puivulling | wood / wood | 4.13 / 43.10 | 1-4-2023 / - | 50.12 / 65.85 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs diversen |
| PAIR-00233 | RF-4621-b30de14ab7 (CURRENT:OPEN_NO_DECISION) | COMPARABLE_WITH_CAVEATS | - | - | GENERIC_VS_SPECIFIC_OBJECT, PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | - / alle gevels | - / - | wood / wood | 4.13 / 1425.95 | 1-4-2023 / 1-4-2024 | 50.12 / 57.94 | LIMITED_TEXT_VARIANT | - |
| PAIR-00234 | RF-4621-2b335b1676 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE | diversen / boeiboord | - / boeiboord | wood / wood | 4.13 / 4.14 | 1-4-2023 / 14-7-2026 | 50.12 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs diversen |
| PAIR-00240 | RF-4621-d5aecc3141 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | balkonkastdeuren entreepuien / alle diversen gevels | puivulling / - | wood / wood | 43.10 / 1425.95 | - / 1-4-2024 | 65.85 / 57.94 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs diversen |
| PAIR-00241 | RF-4621-6c1ca39386 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | QUANTITY_SCALE_DIFFERENCE | balkonkastdeuren entreepuien / boeiboord | puivulling / boeiboord | wood / wood | 43.10 / 4.14 | - / 14-7-2026 | 65.85 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: balkonkastdeuren entreepuien puivulling vs boeiboord |
| PAIR-00246 | RF-4621-64f92e19e4 (INDICATIVE_AFTER_MATERIAL_DECISION) | UNKNOWN | OBJECT_EQUIVALENCE_REQUIRES_REVIEW, ACTION_EQUIVALENCE_REQUIRES_REVIEW | - | PRICE_LEVEL_DIFFERENCE, QUANTITY_SCALE_DIFFERENCE | alle diversen gevels / boeiboord | - / boeiboord | wood / wood | 1425.95 / 4.14 | 1-4-2024 / 14-7-2026 | 57.94 / 92.75 | SUBSTANTIVE_DIFFERENCE | COMPONENT: boeiboord vs diversen |
