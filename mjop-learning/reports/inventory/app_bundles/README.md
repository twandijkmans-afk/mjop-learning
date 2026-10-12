# Component-inventarisbundels (MJOP-App)

Gegenereerd met `scripts/export_app_component_inventory.py` (`--check` controleert actualiteit). Deterministisch, afgeleid van
`data/component_inventory/`, `data/component_presence/` en `vocabularies/app_element_requirements_v1.json`. Niet met de hand aanpassen.

| Bestand | Gebouwscope |
|---|---|
| `maldenhof_component_inventory_v1.json` | Maldenhof 240–296 (DOC-005/006), 15 BAG-panden |
| `doc012_component_inventory_v1.json` | DOC-012 Meppelweg, 1 BAG-pand |

Schema `mjop_app_component_inventory_bundle_v1`: `building`, `components[]` (status PRESENT/ABSENT/UNKNOWN, `presence_basis`,
`decision_ref`, `evidence_refs`, `source_summary`, `material_as_reported`, `last_reviewed`), `maintenance_requirements[]`
(`inventory_result`: APPLICABLE / NOT_APPLICABLE / NEEDS_CONFIRMATION / NEEDS_ATTRIBUTE_CONFIRMATION / NOT_PRESENCE_DRIVEN / USER_SELECTED),
`frame_status` (PHOTO_VISIBLE-bewijs, gebouwtotalen UNKNOWN, historische hoeveelheid NOT_COMPARABLE, legacy fallback, bronvolgorde), `policy`.

Mapping: menselijk besluit -> PRESENT/ABSENT (`HUMAN_DECISION`); bronbewijs zonder besluit -> PRESENT (`SOURCE_EVIDENCE_NOT_CONFIRMED`);
voorgestelde afwezigheid (bijv. 3D BAG nulwaarde) -> UNKNOWN (`PROPOSED_ABSENT_NOT_DECIDED`); geen bewijs -> UNKNOWN. Alleen expliciet ABSENT
geeft NOT_APPLICABLE. Geen scores, geen prijzen, geen hoeveelheden, geen quantity resolutions. Eén bundel hoort bij één VvE (tenant-scheiding).
