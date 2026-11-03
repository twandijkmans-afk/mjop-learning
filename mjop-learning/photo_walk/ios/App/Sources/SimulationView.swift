import SwiftUI
import PhotoWalkCore

/// Testscan zonder sensoren: laadt de SYNTHETISCHE pariteitsfixture (ruisvrije dieptekaart + hoeken) en meet via PhotoWalkCore.
/// Alleen om de flow (meten -> resultaat -> export) te zien; dit is GEEN sensormeting.
enum SimulationRunner {
    private static func d(_ x: Any?) -> Double { (x as? NSNumber)?.doubleValue ?? 0 }

    /// Alleen de synthetische FOTO (beeld + intrinsics + pose + dieptekaart) zonder waarnemingen: de detectie moet de kozijnen zelf vinden.
    @MainActor @discardableResult static func runPhoto(_ store: ScanStore) -> String {
        guard let (intr, depth, pose, corners, expectW, expectH) = load() else { return "Simulatiefixture niet gevonden of onleesbaar" }
        store.newSession()
        store.isSimulation = true; store.buildingId = "BLD-SYNTHETIC"; store.facadeId = "FACADE-A"
        store.keyframes = [Keyframe(id: "F000", timestamp: Date(), intrinsics: intr, pose: pose, trackingState: "NORMAL", depth: depth,
                                    imageURL: SyntheticImage.make(width: intr.width, height: intr.height, corners: corners, id: "F000", sessionId: store.sessionId))]
        return "SIMULATIE-foto geladen; echte kozijn (synthetisch): \(expectW) x \(expectH) m"
    }

    /// Synthetische LiDAR-v2-scène uit de pariteitsfixture (`level_a_v2`): hoofdframe + ondersteunende dieptekaders met eigen pose. Geen sensormeting.
    @MainActor @discardableResult static func runV2(_ store: ScanStore, name: String) -> String? {
        guard let url = Bundle.main.url(forResource: "parity_cases", withExtension: "json"), let data = try? Data(contentsOf: url),
              let c = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any], let i = c["intrinsics"] as? [String: Any],
              let list = c["level_a_v2"] as? [[String: Any]], let cs = list.first(where: { ($0["name"] as? String) == name }),
              let cap = cs["capture"] as? [String: Any], let rawCorners = cs["corners_px"] as? [[Double]] else { return nil }
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        let dw = Int(d(cs["depth_width"])), dh = Int(d(cs["depth_height"]))
        func depthOf(_ e: [String: Any]) -> DepthMap {
            let vals: [Float] = (e["depth"] as? [Any] ?? []).map { (v: Any) -> Float in let z = Float(d(v)); return z == 0 ? Float.nan : z }
            return DepthMap(width: dw, height: dh, values: vals)
        }
        func poseOf(_ e: [String: Any]) -> Pose { Pose(rowMajor: (e["pose_row_major"] as? [Any] ?? []).map { d($0) }) }
        let corners = rawCorners.map { Pixel($0[0], $0[1]) }
        store.newSession()
        store.isSimulation = true; store.buildingId = "BLD-SYNTHETIC"; store.facadeId = "FACADE-A"
        var kf = Keyframe(id: "F000", timestamp: Date(), intrinsics: intr, pose: poseOf(cap), trackingState: "NORMAL", depth: depthOf(cap),
                          imageURL: SyntheticImage.make(width: intr.width, height: intr.height, corners: corners, id: "F000", sessionId: store.sessionId))
        kf.supportDepths = ((cs["supports"] as? [[String: Any]]) ?? []).enumerated().map { (n, e) in
            SupportDepth(id: "F000-S\(n)", timestamp: Date(), intrinsics: intr, pose: poseOf(e), trackingState: "NORMAL", depth: depthOf(e))
        }
        store.keyframes = [kf]
        store.addObservation(Observation(id: "OBS-F000-1", frameId: "F000", corners: corners, originalCorners: corners, source: .MANUAL), to: nil)
        store.measureAll()
        guard let o = store.results.first else { return "geen resultaat" }
        let r = o.result
        return "name=\(name) status=\(o.status.rawValue) w=\(o.widthM ?? "-") h=\(o.heightM ?? "-") method=\(r.scaleMethod) independent=\(r.independentFrames) flags=\(o.flags.map { $0.code }.joined(separator: ","))"
    }

    private static func load() -> (Intrinsics, DepthMap, Pose, [Pixel], Double, Double)? {
        guard let url = Bundle.main.url(forResource: "parity_cases", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let c = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let i = c["intrinsics"] as? [String: Any], let a = c["level_a"] as? [String: Any],
              let rawDepth = a["depth"] as? [Any], let rawCorners = a["corners_px"] as? [[Double]],
              let rawPose = c["pose_row_major"] as? [Any] else { return nil }
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        let values: [Float] = rawDepth.map { (v: Any) -> Float in let z = Float(d(v)); return z == 0 ? Float.nan : z }
        return (intr, DepthMap(width: Int(d(a["depth_width"])), height: Int(d(a["depth_height"])), values: values), Pose(rowMajor: rawPose.map { d($0) }),
                rawCorners.map { Pixel($0[0], $0[1]) }, d(a["expect_width_m"]), d(a["expect_height_m"]))
    }

    @MainActor static func run(_ store: ScanStore) -> String {
        guard let url = Bundle.main.url(forResource: "parity_cases", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let c = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let i = c["intrinsics"] as? [String: Any], let a = c["level_a"] as? [String: Any],
              let rawDepth = a["depth"] as? [Any], let rawCorners = a["corners_px"] as? [[Double]],
              let rawPose = c["pose_row_major"] as? [Any] else { return "Simulatiefixture niet gevonden of onleesbaar" }
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        let values: [Float] = rawDepth.map { (v: Any) -> Float in let z = Float(d(v)); return z == 0 ? Float.nan : z }
        let depth = DepthMap(width: Int(d(a["depth_width"])), height: Int(d(a["depth_height"])), values: values)
        let pose = Pose(rowMajor: rawPose.map { d($0) })
        let corners = rawCorners.map { Pixel($0[0], $0[1]) }
        store.newSession()
        store.isSimulation = true; store.buildingId = "BLD-SYNTHETIC"; store.facadeId = "FACADE-A"
        store.keyframes = [Keyframe(id: "F000", timestamp: Date(), intrinsics: intr, pose: pose, trackingState: "NORMAL", depth: depth,
                                 imageURL: SyntheticImage.make(width: intr.width, height: intr.height, corners: corners, id: "F000", sessionId: store.sessionId))]
        store.addObservation(Observation(id: "OBS-F000-1", frameId: "F000", corners: corners, originalCorners: corners, source: .MANUAL), to: nil)
        store.measureAll()
        guard let o = store.results.first else { return "Geen resultaat" }
        return """
        SIMULATIE (synthetische data - geen sensormeting)
        \(o.id)
        \(o.widthM ?? "UNKNOWN") x \(o.heightM ?? "UNKNOWN") m = \(o.areaM2 ?? "UNKNOWN") m2 [\(o.status.rawValue)]
        vlaggen: \(o.flags.map { $0.code }.joined(separator: ", "))
        Python-referentie: \(d(a["expect_width_m"])) x \(d(a["expect_height_m"])) m
        """
    }
}

struct SimulationView: View {
    @EnvironmentObject var store: ScanStore
    @State private var text = "Laden..."
    @State private var exported: String? = nil
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text(text).font(.system(.footnote, design: .monospaced))
                NavigationLink("Resultaten openen") { ResultsView().environmentObject(store) }
                if let kf = store.keyframes.first { NavigationLink("Hoeken markeren op testbeeld") { CornerPickerView(frame: kf).environmentObject(store) } }
                Button("Export schrijven") { exported = (try? ExportService.write(store))?.path ?? "mislukt" }
                if let e = exported { Text(e).font(.caption2) }
            }.padding()
        }
        .navigationTitle("Simulatie")
        .onAppear { text = SimulationRunner.run(store) }
    }
}
