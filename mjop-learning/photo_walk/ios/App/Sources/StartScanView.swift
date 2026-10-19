import ARKit
import SwiftUI

struct StartScanView: View {
    @EnvironmentObject var store: ScanStore
    @State private var goPhoto = false
    @State private var goLegacy = false
    @State private var goSimPhoto = false
    @State private var goResume = false
    @State private var resumable: (SessionSnapshot, URL)? = nil

    var body: some View {
        Form {
            Section("Gebouw en gevel") {
                TextField("Gebouw-ID", text: $store.buildingId)
                TextField("Gevel-ID", text: $store.facadeId)
            }
            Section("Foto-scan (aanbevolen)") {
                Button("Foto-scan starten") { store.newSession(); goPhoto = true }
                    .disabled(store.buildingId.isEmpty || store.facadeId.isEmpty)
                Button("Testfoto met synthetische data (simulatie)") { SimulationRunner.runPhoto(store); goSimPhoto = true }
                if let r = resumable {
                    Button("Laatste scan hervatten (\(r.0.keyframes.count) foto's, \(r.0.buildingId)/\(r.0.facadeId))") {
                        Persistence.restore(r.0, from: r.1, into: store); goResume = true
                    }
                }
                Text("Camera openen, één foto maken: kozijnen worden lokaal herkend (als KANDIDATEN) en direct met kaders en voorlopige maten getoond.").font(.footnote).foregroundStyle(.secondary)
            }
            Section("Sensoren (automatisch bepaald)") {
                let lidar = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
                LabeledContent("AR-wereldtracking", value: ARWorldTrackingConfiguration.isSupported ? "ja" : "nee")
                LabeledContent("LiDAR / sceneDepth", value: lidar ? "ja" : "nee")
                LabeledContent("Meetmodus", value: lidar ? "A: metrische diepte (terugval referentiemaat)" : "C: referentiemeting (geen LiDAR: maten UNKNOWN zonder referentie)")
                Text(DetectorCatalog.statusText).font(.footnote).foregroundStyle(.secondary)
            }
            Section("Geavanceerd (handmatig)") {
                Button("Keyframe-scan starten (handmatig markeren)") { store.newSession(); goLegacy = true }
                    .disabled(store.buildingId.isEmpty || store.facadeId.isEmpty)
                NavigationLink("Testscan met synthetische data (simulatie)") { SimulationView().environmentObject(store) }
            }
            Section("Privacy en status") {
                Text("Alles wordt lokaal verwerkt en bewaard. Er worden geen beelden geupload, geen externe Vision-aanroepen gedaan en geen locatie bewaard. Alle uitkomsten zijn voorlopig, onbevestigd en NIET gevalideerd op echte gebouwen; ze wachten op menselijke goedkeuring.").font(.footnote)
            }
        }
        .onAppear {
            // alleen voor de UI-rooktest in CI: vult de verplichte ID's in zodat geen toetsenbord nodig is
            if CommandLine.arguments.contains("-uitest-prefill") { store.buildingId = "BLD-UITEST"; store.facadeId = "FACADE-UITEST" }
            resumable = Persistence.latest()
        }
        .navigationTitle("Photo Walk")
        .navigationDestination(isPresented: $goPhoto) { PhotoScanView().environmentObject(store) }
        .navigationDestination(isPresented: $goLegacy) { LiveScanView().environmentObject(store) }
        .navigationDestination(isPresented: $goSimPhoto) { PhotoResultView(frameId: "F000").environmentObject(store) }
        .navigationDestination(isPresented: $goResume) { PhotoListView().environmentObject(store) }
    }
}
