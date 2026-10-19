import SwiftUI
import PhotoWalkCore

/// Testscan zonder sensoren: laadt de SYNTHETISCHE pariteitsfixture (ruisvrije dieptekaart + hoeken) en meet via PhotoWalkCore.
/// Alleen om de flow (meten -> resultaat -> export) te zien; dit is GEEN sensormeting.
struct SimulationView: View {
    @EnvironmentObject var store: ScanStore
    @State private var text = "Laden..."
    var body: some View {
        ScrollView { Text(text).font(.system(.footnote, design: .monospaced)).padding() }
            .navigationTitle("Simulatie")
            .onAppear(perform: run)
    }

    private func d(_ x: Any?) -> Double { (x as! NSNumber).doubleValue }
    private func run() {
        guard let url = Bundle.main.url(forResource: "parity_cases", withExtension: "json"),
              let c = (try? JSONSerialization.jsonObject(with: Data(contentsOf: url))) as? [String: Any] else { text = "Fixture niet gevonden"; return }
        let i = c["intrinsics"] as! [String: Any], a = c["level_a"] as! [String: Any]
        let intr = Intrinsics(fx: d(i["fx"]), fy: d(i["fy"]), cx: d(i["cx"]), cy: d(i["cy"]), width: Int(d(i["width"])), height: Int(d(i["height"])))
        let depth = DepthMap(width: Int(d(a["depth_width"])), height: Int(d(a["depth_height"])), values: (a["depth"] as! [Any]).map { let z = Float(d($0)); return z == 0 ? .nan : z })
        let pose = Pose(rowMajor: (c["pose_row_major"] as! [Any]).map { d($0) })
        let corners = (a["corners_px"] as! [[Double]]).map { Pixel($0[0], $0[1]) }
        store.newSession(); store.isSimulation = true; store.buildingId = "BLD-SYNTHETIC"; store.facadeId = "FACADE-A"
        store.keyframes = [Keyframe(id: "F000", timestamp: Date(), intrinsics: intr, pose: pose, trackingState: "NORMAL", depth: depth, imageURL: nil)]
        store.addObservation(Observation(id: "OBS-F000-1", frameId: "F000", corners: corners, originalCorners: corners, source: .MANUAL), to: nil)
        store.measureAll()
        let o = store.results[0]
        text = """
        SIMULATIE (synthetische data)
        \(o.id)
        \(o.widthM ?? "UNKNOWN") x \(o.heightM ?? "UNKNOWN") m = \(o.areaM2 ?? "UNKNOWN") m2 [\(o.status.rawValue)]
        vlaggen: \(o.flags.map { $0.code }.joined(separator: ", "))
        Python-referentie: \(d(a["expect_width_m"])) x \(d(a["expect_height_m"])) m
        """
    }
}
