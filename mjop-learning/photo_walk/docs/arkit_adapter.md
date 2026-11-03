# ARKit / LiDAR-adapter (`ios/App/Sources/CaptureCoordinator.swift`)

STATUS: **geschreven, niet gecompileerd, niet op een toestel getest.**

| Onderdeel | ARKit | Contract |
|---|---|---|
| Sensordetectie | `ARWorldTrackingConfiguration.isSupported`, `supportsFrameSemantics(.sceneDepth)` | `sensor_capabilities` (modus automatisch) |
| Configuratie | `worldAlignment = .gravity`, `planeDetection = [.vertical]`, `frameSemantics = .sceneDepth` (alleen als ondersteund) | wereld: Y omhoog, m |
| Pose | `ARCamera.transform` (x rechts, y **omhoog**, z **achteruit**) | `R_cv = R_arkit·diag(1,−1,−1)`, `t` ongewijzigd, rij-hoofdvolgorde |
| Intrinsics | `ARCamera.intrinsics` (3x3: `fx = m[0][0]`, `fy = m[1][1]`, `cx = m[2][0]`, `cy = m[2][1]`), `imageResolution` | `camera_intrinsics` in pixels van `capturedImage` |
| Diepte | `ARFrame.sceneDepth.depthMap` (Float32, m, 256x192), `confidenceMap` | `depth_z`; confidence 0 ⇒ NaN (drempel niet gevalideerd) |
| Tracking | `ARCamera.trackingState` (`normal`, `limited(reason)`, `notAvailable`) | `tracking_quality.state` |
| Beeld | `capturedImage` → lokale JPEG in Application Support, uitgesloten van back-up | `image_refs` (`local://…`) |
| Plane detection | wordt aangezet maar **niet gebruikt** voor de maat (eigen vlakfit uit diepte) | – |
| Hoekdetectie | optioneel `VNDetectRectanglesRequest` (on-device) ⇒ `AUTO_DETECTED_UNCONFIRMED`; pas na bevestiging `AUTO_DETECTED_CONFIRMED` | `corner_source`, `scan_label` |

Bekende open punten (alleen op een toestel te beantwoorden):
* of de principal point-conventie van `ARCamera.intrinsics` (pixelhoek vs. pixelmidden) overeenkomt met onze conventie (verschil ≈ 0,5 px);
* uitlijning dieptekaart ↔ `capturedImage` (zelfde oriëntatie aangenomen, schaling `W/Wd`);
* of `depthMap` echt `depth_z` is (aangenomen, conform Apple-documentatie) en hoe de ruis/bias met afstand loopt;
* beeldrotatie in `FrameImageCanvas` (`.right`) voor alle apparaatoriëntaties;
* gedrag van `confidenceMap`-drempel op glas en randen.

Niet geïmplementeerd in de iOS-app (wel in de Python-referentie): automatische associatie over keyframes (de app koppelt via handmatige keuze "koppel aan kozijn"), niveau B, live dekking/overlap-indicator, live markering van kozijnopeningen (alleen op vastgelegde keyframes).
