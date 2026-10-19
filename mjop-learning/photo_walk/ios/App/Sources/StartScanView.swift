import ARKit
import SwiftUI

struct StartScanView: View {
    @EnvironmentObject var store: ScanStore
    @State private var go = false
    var body: some View {
        Form {
            Section("Gebouw en gevel") {
                TextField("Gebouw-ID", text: $store.buildingId)
                TextField("Gevel-ID", text: $store.facadeId)
            }
            Section("Sensoren (automatisch bepaald)") {
                let lidar = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
                LabeledContent("AR-wereldtracking", value: ARWorldTrackingConfiguration.isSupported ? "ja" : "nee")
                LabeledContent("LiDAR / sceneDepth", value: lidar ? "ja" : "nee")
                LabeledContent("Meetmodus", value: lidar ? "A: metrische diepte (terugval B/C)" : (ARWorldTrackingConfiguration.isSupported ? "B/C: AR-geometrie of referentie" : "C: referentiemeting"))
                Text("LiDAR is niet verplicht: zonder dieptesensor wordt een referentieafstand gevraagd.").font(.footnote).foregroundStyle(.secondary)
            }
            Section {
                Button("Nieuwe scan starten") { store.newSession(); go = true }
                    .disabled(store.buildingId.isEmpty || store.facadeId.isEmpty)
                NavigationLink("Testscan met synthetische data (simulatie)") { SimulationView().environmentObject(store) }
            }
            Section("Privacy") {
                Text("Alles wordt lokaal verwerkt. Er worden geen beelden geupload, geen externe Vision-aanroepen gedaan en geen locatie bewaard. Alle uitkomsten zijn voorlopig en wachten op menselijke goedkeuring.").font(.footnote)
            }
        }
        .onAppear {
            // alleen voor de UI-rooktest in CI: vult de verplichte ID's in zodat geen toetsenbord nodig is
            if CommandLine.arguments.contains("-uitest-prefill") { store.buildingId = "BLD-UITEST"; store.facadeId = "FACADE-UITEST" }
        }
        .navigationTitle("Photo Walk")
        .navigationDestination(isPresented: $go) { LiveScanView().environmentObject(store) }
    }
}
