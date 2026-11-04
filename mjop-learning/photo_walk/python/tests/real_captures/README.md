# Echte metingen (REAL_SENSOR) als replay-fixtures

Bevat uitsluitend **numerieke meetdiagnoses** (`photo_walk_measure_diagnostics_v1`) van twee echte iPhone-LiDAR-metingen en de door de eigenaar opgegeven werkelijke maten.
**Geen foto's, geen dieptekaarten, geen puntenwolken, geen locatie, geen absolute pose.** Foto's horen niet in Git, in de PR of in CI-artifacts.

| Bestand | Inhoud |
|---|---|
| `meetdiagnose_acb1d24b5cd6_OBS-F005-04.json` | echte meting; blokkade `AMBIGUOUS_FACADE_PLANES` + `OUTER_CONTOUR_UNVERIFIED` |
| `meetdiagnose_acb1d24b5cd6_OBS-F014-03.json` | echte meting; blokkade `FACADE_ONE_SIDED` + `OUTER_CONTOUR_UNVERIFIED` |
| `ground_truth_kozijn_F005_F014.json` | kozijn 92 x 210 cm, glas 79 x 198 cm; profielbreedtes per zijde volgen later |

De replay-tests (`test_real_captures.py`) bewaken het **huidige** gedrag (karakteriseringstests) en de pose-vrije feiten; ze veranderen geen drempel of poort.
