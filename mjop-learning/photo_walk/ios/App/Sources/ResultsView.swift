import SwiftUI
import PhotoWalkCore

struct ResultsView: View {
    @EnvironmentObject var store: ScanStore
    @State private var refDist = ""
    @State private var exportURL: URL? = nil
    var body: some View {
        List {
            if store.isSimulation { Text("SIMULATIE - synthetische data; bewijst geen nauwkeurigheid.").foregroundStyle(.orange) }
            Section("Voorlopige kozijnen") {
                ForEach(store.results, id: \.id) { o in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(o.id).font(.headline)
                        Text(o.status == .UNKNOWN ? "UNKNOWN - geen betrouwbare maat" :
                                "\(o.widthM ?? "?") x \(o.heightM ?? "?") m = \(o.areaM2 ?? "?") m2  [\(o.status.rawValue)]")
                        if o.status != .UNKNOWN, let sa = o.result.sigmaArea {
                            Text("Bron: \(o.result.scaleMethod) (niveau \(o.result.level.rawValue)) - onzekerheid 1σ ≈ \(String(format: "%.4f", sa)) m² (modelgebaseerd, NIET gevalideerd)").font(.caption)
                        }
                        Text("Waarnemingen: \(o.observations.count) - hoeken handmatig geselecteerd (semi-automatisch)").font(.caption)
                        if o.reviewRequired { Text("Review nodig").font(.caption).foregroundStyle(.orange) }
                        ForEach(o.nextSteps, id: \.self) { Text("• \($0)").font(.caption) }
                    }
                }
            }
            Section("Hoeken corrigeren") {
                ForEach(store.observations) { ob in NavigationLink("\(ob.id) (\(ob.source.rawValue))") { CornerEditView(observationId: ob.id).environmentObject(store) } }
            }
            Section {
                Button("Opnieuw berekenen") { store.measureAll() }
                if let u = exportURL { ShareLink(item: u) { Label("Deel exportbestand (lokaal)", systemImage: "square.and.arrow.up") } }
                Button("Exporteer naar bestand") { exportURL = try? ExportService.write(store) }
            }
        }
        .navigationTitle("Resultaten")
        .onAppear { store.measureAll() }
    }
}
