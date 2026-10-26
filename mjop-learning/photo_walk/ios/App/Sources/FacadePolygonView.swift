import SwiftUI
import UIKit
import PhotoWalkCore

/// Het bruto gevelvlak van één foto aangeven: vier hoeken van het gevelvlak (zonder dak). Daarmee berekent de app bruto gevel, openingen en
/// netto gesloten gevel; alleen met betrouwbare schaal (LiDAR-gevelvlak of referentiemaat op een kozijn), anders blijft de maat onbekend.
/// Een eerder getekend vlak blijft bewaard (telt niet meer mee). Pixels zijn ORIGINELE pixels van de foto.
struct FacadePolygonView: View {
    @EnvironmentObject var store: ScanStore
    @Environment(\.dismiss) private var dismiss
    let frame: Keyframe
    @State private var taps: [Pixel] = []
    @State private var image: UIImage? = nil
    private static let names = ["linksboven", "rechtsboven", "rechtsonder", "linksonder"]

    var body: some View {
        VStack {
            Text(taps.count < 4 ? "Tik de vier hoeken van het gevelvlak: \(Self.names[taps.count]). Neem het dak niet mee. Zoom in voor nauwkeurig werken."
                 : "Controleer de hoeken (sleep zo nodig) en sla op.")
                .font(.footnote).padding(.horizontal).accessibilityIdentifier("facadePrompt")
            if let img = image {
                FrameImageCanvas(frame: frame, image: img, points: $taps, maxPoints: 4, overlay: store.facadePolygon(frameId: frame.id)?.corners ?? [], pointNames: Self.names)
            } else { ProgressView() }
            HStack {
                Button("Laatste punt weg") { if !taps.isEmpty { taps.removeLast() } }.disabled(taps.isEmpty)
                Button("Wissen") { taps = [] }
                Button("Opslaan") {
                    store.setFacadePolygon(frameId: frame.id, corners: taps)
                    dismiss()
                }.buttonStyle(.borderedProminent).disabled(taps.count != 4 || !isSimpleConvexQuad(taps)).accessibilityIdentifier("saveFacadeButton")
            }
            Text("Het gevelvlak is alleen voor de gevelopbouw (bruto/netto gevel). Kozijnen en glas blijven apart.").font(.caption2).foregroundStyle(.secondary)
        }
        .navigationTitle("Gevelvlak \(frame.id)")
        .onAppear { if let u = frame.imageURL, let d = try? Data(contentsOf: u) { image = UIImage(data: d) } }
    }
}
