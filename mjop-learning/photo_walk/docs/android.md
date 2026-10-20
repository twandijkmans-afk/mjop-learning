# Android (ARCore) — voorbereiding

STATUS: alleen contract + vertaalfuncties (`android/photowalk-contract`, Kotlin); **niet gecompileerd**, geen app, meetkern nog niet geport (bedoeld: Kotlin-port of gedeelde native lib na validatie van de iOS-MVP).

| Gegeven | ARKit | ARCore | Verschil / aandachtspunt |
|---|---|---|---|
| Pose | `ARCamera.transform` | `Camera.getPose()` | Beide camera→wereld met OpenGL-camera (y omhoog, −z vooruit) ⇒ zelfde `diag(1,−1,−1)`-omzetting. ARCore-wereld is gravity-aligned (Y omhoog). |
| Intrinsics | `ARCamera.intrinsics` | `Camera.getImageIntrinsics()` (`focalLength`, `principalPoint`, `imageDimensions`) | CPU-beeldresolutie ≠ texture-resolutie: altijd de intrinsics van het gebruikte beeld nemen. |
| Metrische schaal | VIO, metrisch (+ LiDAR) | VIO, metrisch | Beide **niet** onafhankelijk geverifieerd ⇒ ARCore zonder dieptesensor = niveau B ⇒ `ESTIMATED` tenzij referentie. |
| Diepte | LiDAR `sceneDepth` Float32 m + confidence (0–2), 256x192 | Depth API: `acquireDepthImage16Bits()` uint16 **mm**, `RAW_DEPTH_ONLY` + `acquireRawDepthConfidenceImage()`; resolutie en kwaliteit verschillen per toestel | ARCore-diepte is meestal *depth-from-motion* (bij sommige toestellen ToF) en is veel ruwer, afhankelijk van beweging en textuur, en onbetrouwbaar op effen gevelvlakken. `DepthSource` in de adapter; **voorstel:** `DEPTH_FROM_MOTION` komt hoogstens op `ESTIMATED` totdat validatie anders aantoont. |
| Tracking | `normal / limited(reason) / notAvailable` | `TRACKING / PAUSED` + `TrackingFailureReason` | Mapping in `ArCoreMapping.tracking`. |
| Plane detection | `.vertical` | `Config.PlaneFindingMode.VERTICAL` | Niet gebruikt voor de maat. |
| Sensorbeschikbaarheid | `sceneDepth` ondersteund? | `Session.isDepthModeSupported(AUTOMATIC / RAW_DEPTH_ONLY)` | Vastgelegd in `sensor_capabilities` (`lidar=false` op Android, `depth_api`). |
| Zonder dieptesensor | niveau C of B | niveau C of B | Identiek: modus volgt uit `determine_measurement_mode`. |

Dezelfde regels: één kozijn = één object, bruto buitenmaat (glas, vaste en draaiende delen binnen de maat), `gross_area = w x h`, zelfde statussen, dezelfde `invariants`, hetzelfde schema en dezelfde `validate`-tool. Android hoeft de iPhone-MVP niet te vertragen: er is geen afhankelijkheid van iOS → Android.
