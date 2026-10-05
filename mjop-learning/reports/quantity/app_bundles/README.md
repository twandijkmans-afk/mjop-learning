# App-bundels (MJOP-App)

Echte, gegenereerde hoeveelhedenbundels voor MJOP-App. Gemaakt met `scripts/export_app_quantity_bundle.py`
uit de canonieke evidence (`data/quantity_evidence/`), de menselijke besluiten (`data/building_links/`,
`data/crosswalk_decisions/`) en de onderwerpenvocabulaire. Deterministisch: een nieuwe export op dezelfde
invoer is byte-identiek. Gevalideerd met `scripts/validate_app_quantity_bundle.py`.

| Bestand | Versie | Gebouwscope |
|---|---|---|
| `maldenhof_DOC-005_DOC-006_v3.json` | `mjop_app_quantity_bundle_v3` | Maldenhof 240–296 (even), 15 BAG-panden |

```
python scripts/export_app_quantity_bundle.py --building "BAG:<15 pand-ID's>" \
    --out reports/quantity/app_bundles/maldenhof_DOC-005_DOC-006_v3.json
python scripts/validate_app_quantity_bundle.py reports/quantity/app_bundles/maldenhof_DOC-005_DOC-006_v3.json \
    --expect-panden 15 --check-export
```

Tenant-scheiding: de bundel bevat historische hoeveelheden van één VvE en is alleen bedoeld voor een plan van
die VvE. Een bundel bevat nooit een keuze of quantity resolution: dat besluit de gebruiker (in de app) of een
mens (in `data/quantity_resolutions/`).
