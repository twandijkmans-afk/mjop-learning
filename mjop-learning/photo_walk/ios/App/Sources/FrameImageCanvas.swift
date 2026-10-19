import SwiftUI
import UIKit
import PhotoWalkCore

/// Keyframe met zoom/pan en nauwkeurige puntselectie plus bediening (zoomindicator, 1x/2x/4x/8x, slider, reset).
/// `points` zijn ORIGINELE pixels van het keyframe (native oriëntatie), ongeacht zoom, pan of schermformaat.
/// Zoom is alleen een weergave-instelling: hij geeft GEEN extra metrische nauwkeurigheid; hij maakt alleen preciezer aanwijzen mogelijk.
struct FrameImageCanvas: View {
    let frame: Keyframe
    let image: UIImage
    @Binding var points: [Pixel]
    let maxPoints: Int
    var overlay: [Pixel] = []                 // bestaande hoeken (groen), alleen weergave
    var pointNames: [String] = []             // voor de uitlezing, bv. ["linksboven", ...]
    @StateObject private var controller = CanvasController()

    private var sizeMismatch: Bool {
        guard let cg = image.cgImage else { return false }
        return cg.width != frame.intrinsics.width || cg.height != frame.intrinsics.height
    }

    private var readout: String {
        if points.isEmpty { return "Nog geen punten. Tik op het beeld; zoom in voor nauwkeurig werken." }
        return points.enumerated().map { (i, p) in
            let name = i < pointNames.count ? " \(pointNames[i])" : ""
            return String(format: "%d%@: (%.1f, %.1f) px", i + 1, name, p.u, p.v)
        }.joined(separator: "\n")
    }

    var body: some View {
        VStack(spacing: 6) {
            ZStack(alignment: .topTrailing) {
                ZoomableFrameCanvas(image: image, points: $points, maxPoints: maxPoints, overlay: overlay, controller: controller)
                    .frame(maxWidth: .infinity, minHeight: 200, maxHeight: .infinity)
                Text(String(format: "%.1f×", controller.zoom))
                    .font(.system(.subheadline, design: .rounded).bold()).monospacedDigit()
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(.black.opacity(0.7)).foregroundStyle(.white).cornerRadius(8).padding(8)
                    .accessibilityIdentifier("zoomIndicator")
            }
            HStack(spacing: 8) {
                ForEach([1.0, 2.0, 4.0, 8.0], id: \.self) { z in
                    Button(String(format: "%.0f×", z)) { controller.setZoom(z, animated: true) }
                        .buttonStyle(.bordered).accessibilityIdentifier("zoomButton\(Int(z))")
                }
                Slider(value: Binding(get: { log2(controller.zoom) }, set: { controller.setZoom(pow(2, $0), animated: false) }), in: 0...3)
                    .accessibilityIdentifier("zoomSlider")
                Button("Reset") { controller.resetView() }.buttonStyle(.bordered).accessibilityIdentifier("zoomReset")
            }.padding(.horizontal, 8)
            Text(String(format: "1 schermpunt ≈ %.2f beeldpixel · zoom = alleen weergave, geen extra meetnauwkeurigheid", controller.nativePerPoint))
                .font(.caption2).foregroundStyle(.secondary).padding(.horizontal, 8)
            if sizeMismatch { Text("Let op: beeldafmeting wijkt af van de camera-intrinsics; resultaten zijn onbetrouwbaar.").font(.caption2).foregroundStyle(.red) }
            Text(readout).font(.system(.caption, design: .monospaced)).frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 8)
                .accessibilityIdentifier("pointsReadout")
        }
    }
}

/// Referentiemeting (niveau C): twee punten op het kozijnvlak + een door de inspecteur gemeten/bekende afstand.
struct ReferencePickerView: View {
    @EnvironmentObject var store: ScanStore
    let frame: Keyframe
    @State private var taps: [Pixel] = []
    @State private var distance = ""
    @State private var sigma = ""
    @State private var planeId = "P1"
    @State private var image: UIImage? = nil

    private func num(_ s: String) -> Double? { Double(s.replacingOccurrences(of: ",", with: ".")) }

    var body: some View {
        VStack {
            Group {
                Text("Zoom in en tik twee punten op HETZELFDE vlak als het kozijn (bv. beide zijden van een gemeten kozijnbreedte). Sleep een punt om het bij te stellen. Voer daarna de afstand in.").font(.footnote).padding(.horizontal)
                if let img = image { FrameImageCanvas(frame: frame, image: img, points: $taps, maxPoints: 2, pointNames: ["begin", "eind"]) } else { ProgressView() }
                TextField("Afstand in meter (bv. 1.200)", text: $distance).keyboardType(.decimalPad).textFieldStyle(.roundedBorder).padding(.horizontal)
                TextField("Onzekerheid in meter (optioneel)", text: $sigma).keyboardType(.decimalPad).textFieldStyle(.roundedBorder).padding(.horizontal)
                TextField("Vlak-ID", text: $planeId).textFieldStyle(.roundedBorder).padding(.horizontal)
                HStack {
                    Button("Laatste punt weg") { if !taps.isEmpty { taps.removeLast() } }.disabled(taps.isEmpty)
                    Button("Wissen") { taps = [] }
                    Button("Opslaan") {
                        if let d = num(distance), taps.count == 2 {
                            store.references[frame.id] = ReferenceMeasure(referenceId: "REF-\(frame.id)", p1: taps[0], p2: taps[1], distanceM: d,
                                                                          distanceSigmaM: num(sigma), planeId: planeId)
                        }
                    }.buttonStyle(.borderedProminent).disabled(taps.count != 2 || num(distance) == nil)
                }
            }
        }
        .navigationTitle("Referentie \(frame.id)")
        .onAppear { if let u = frame.imageURL, let d = try? Data(contentsOf: u) { image = UIImage(data: d) } }
    }
}

/// Stap 9: de gebruiker corrigeert een hoek. De brondata (keyframe, originele hoeken) blijft ongemoeid; er komt een revisie bij en alles wordt herberekend.
struct CornerEditView: View {
    @EnvironmentObject var store: ScanStore
    let observationId: String
    @State private var index = 0
    @State private var taps: [Pixel] = []
    @State private var image: UIImage? = nil
    var body: some View {
        let obs = store.observations.first { $0.id == observationId }
        let frame = store.keyframes.first { $0.id == obs?.frameId }
        Group {
            VStack {
                if let obs, let frame, let img = image {
                    Text("Groen = huidige hoeken. Kies hoek 1-4, zoom in en tik de juiste plek (of sleep het rode punt) en kies 'Corrigeer'.").font(.footnote).padding(.horizontal)
                    FrameImageCanvas(frame: frame, image: img, points: $taps, maxPoints: 1, overlay: obs.corners, pointNames: ["nieuw"])
                    Picker("Hoek", selection: $index) {
                        ForEach(0..<4) { Text("\($0 + 1)").tag($0) }
                    }.pickerStyle(.segmented).padding(.horizontal)
                    HStack {
                        Button("Wissen") { taps = [] }
                        Button("Corrigeer hoek \(index + 1)") {
                            if let p = taps.first { store.correctCorner(observation: obs.id, index: index, to: p, reason: "handmatige correctie (ingezoomd)"); store.measureAll(); taps = [] }
                        }.buttonStyle(.borderedProminent).disabled(taps.isEmpty)
                    }
                    Text("Revisies: \(obs.revisions.count) - originele hoeken blijven bewaard.").font(.footnote)
                } else { ProgressView() }
            }
        }
        .navigationTitle("Hoek corrigeren")
        .onAppear { if let u = frame?.imageURL, let d = try? Data(contentsOf: u) { image = UIImage(data: d) } }
    }
}
