import SwiftUI
import UIKit
import Vision
import PhotoWalkCore

/// Handmatige hoekselectie op een vastgelegd keyframe (fallback; label: semi-automatisch). Optioneel stelt het on-device
/// VNDetectRectanglesRequest kandidaten voor; die zijn NIET gevalideerd als kozijndetector en blijven AUTO_DETECTED_UNCONFIRMED tot de gebruiker ze bevestigt.
/// Tikken worden door FrameImageCanvas omgerekend naar PIXELS van de native camerabeeldoriëntatie.
struct CornerPickerView: View {
    @EnvironmentObject var store: ScanStore
    let frame: Keyframe
    @State private var taps: [Pixel] = []
    @State private var candidates: [[Pixel]] = []
    @State private var targetDraft: String? = nil
    @State private var uiImage: UIImage? = nil
    @State private var saved: String? = nil
    private static let names = ["linksboven", "rechtsboven", "rechtsonder", "linksonder"]
    private var prompt: String {
        taps.count < 4
            ? "Hoek \(taps.count + 1) van 4: tik \(Self.names[taps.count]) (buitenhoek, zoals het kozijn rechtop staat). Zoom met twee vingers; sleep een punt om bij te stellen."
            : "Alle vier de hoeken staan. Controleer ze (zoom in, sleep zo nodig) en sla op."
    }

    var body: some View {
        VStack {
            Text(saved ?? prompt).font(.footnote).padding(.horizontal).accessibilityIdentifier("cornerPrompt")
            if let img = uiImage { FrameImageCanvas(frame: frame, image: img, points: $taps, maxPoints: 4, pointNames: Self.names) } else { ProgressView() }
            HStack {
                Button("Laatste punt weg") { if !taps.isEmpty { taps.removeLast() }; saved = nil }.disabled(taps.isEmpty)
                Button("Voorstellen (on-device)") { detectCandidates() }.disabled(uiImage == nil)
                Button("Wissen") { taps = []; saved = nil }
                Button("Opslaan") { save() }.disabled(taps.count != 4).buttonStyle(.borderedProminent)
            }
            if !candidates.isEmpty {
                ScrollView(.horizontal) { HStack { ForEach(Array(candidates.enumerated()), id: \.offset) { i, c in
                    Button("Voorstel \(i + 1) (onbevestigd)") { taps = c; saved = "Voorstel overgenomen - controleer de hoeken (zoom in); opslaan telt als bevestigd." }.buttonStyle(.bordered)
                } } }
            }
            Picker("Koppel aan kozijn", selection: $targetDraft) {
                Text("Nieuw kozijn").tag(String?.none)
                ForEach(store.drafts) { d in Text(d.id).tag(String?.some(d.id)) }
            }
        }
        .navigationTitle(frame.id)
        .onAppear { if let u = frame.imageURL, let d = try? Data(contentsOf: u) { uiImage = UIImage(data: d) } }
    }

    private func save() {
        let fromAuto = candidates.contains { zip($0, taps).allSatisfy { $0 == $1 } }
        let o = Observation(id: "OBS-\(frame.id)-\(store.observations.count + 1)", frameId: frame.id, corners: taps, originalCorners: taps,
                            source: fromAuto ? .AUTO_DETECTED_CONFIRMED : .MANUAL)
        store.addObservation(o, to: targetDraft)
        store.measureAll(); store.persist()
        taps = []; saved = "Opgeslagen (\(o.source.rawValue)). Je kunt een volgend kozijn markeren."
    }

    private func detectCandidates() {
        guard let cg = uiImage?.cgImage else { return }
        let W = Double(cg.width), H = Double(cg.height)
        let req = VNDetectRectanglesRequest { r, _ in
            let obs = (r.results as? [VNRectangleObservation]) ?? []
            let c = obs.prefix(5).map { o -> [Pixel] in
                [o.topLeft, o.topRight, o.bottomRight, o.bottomLeft].map { Pixel(Double($0.x) * W, (1 - Double($0.y)) * H) }
            }
            DispatchQueue.main.async { candidates = c }
        }
        req.maximumObservations = 5; req.minimumConfidence = 0.5; req.minimumAspectRatio = 0.3
        try? VNImageRequestHandler(cgImage: cg, orientation: .up).perform([req])      // on-device; geen netwerk
    }
}
