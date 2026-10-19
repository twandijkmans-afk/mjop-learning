import SwiftUI
import UIKit
import PhotoWalkCore

/// Toont het keyframe rechtop (native landscape-beeld 90 graden gedraaid, orientation .right) en zet tikken om naar PIXELS van het native beeld.
/// Weergave: native (u,v) -> portret (x = H - v, y = u); inverse: u = y, v = H - x. NIET op een toestel gevalideerd.
struct FrameImageCanvas: View {
    let frame: Keyframe
    let image: UIImage
    @Binding var taps: [Pixel]
    let maxTaps: Int
    var overlay: [Pixel] = []          // bestaande hoeken (groen), alleen weergave

    var body: some View {
        GeometryReader { geo in
            let H = Double(frame.intrinsics.height), W = Double(frame.intrinsics.width)
            let pw = H, ph = W
            let scale = min(geo.size.width / pw, geo.size.height / ph)
            let ox = (geo.size.width - pw * scale) / 2, oy = (geo.size.height - ph * scale) / 2
            ZStack(alignment: .topLeading) {
                Image(uiImage: UIImage(cgImage: image.cgImage!, scale: 1, orientation: .right)).resizable().frame(width: pw * scale, height: ph * scale).offset(x: ox, y: oy)
                ForEach(Array(overlay.enumerated()), id: \.offset) { i, p in
                    let vp = CGPoint(x: ox + (H - p.v) * scale, y: oy + p.u * scale)
                    Circle().stroke(.green, lineWidth: 2).frame(width: 14, height: 14).position(vp)
                    Text("\(i + 1)").font(.caption2).foregroundStyle(.green).position(CGPoint(x: vp.x + 12, y: vp.y - 12))
                }
                ForEach(Array(taps.enumerated()), id: \.offset) { i, p in
                    let vp = CGPoint(x: ox + (H - p.v) * scale, y: oy + p.u * scale)
                    Circle().fill(.red).frame(width: 12, height: 12).position(vp)
                    Text("\(i + 1)").font(.caption2).foregroundStyle(.white).position(vp)
                }
            }
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onEnded { g in
                guard taps.count < maxTaps else { return }
                let xp = (g.location.x - ox) / scale, yp = (g.location.y - oy) / scale
                guard xp >= 0, yp >= 0, xp <= pw, yp <= ph else { return }
                taps.append(Pixel(yp, H - xp))
            })
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

    var body: some View {
        VStack {
            Text("Tik twee punten op HETZELFDE vlak als het kozijn (bv. beide zijden van een gemeten kozijnbreedte) en voer de afstand in.").font(.footnote).padding(.horizontal)
            if let img = image { FrameImageCanvas(frame: frame, image: img, taps: $taps, maxTaps: 2) } else { ProgressView() }
            TextField("Afstand in meter (bv. 1.200)", text: $distance).keyboardType(.decimalPad).textFieldStyle(.roundedBorder).padding(.horizontal)
            TextField("Onzekerheid in meter (optioneel)", text: $sigma).keyboardType(.decimalPad).textFieldStyle(.roundedBorder).padding(.horizontal)
            TextField("Vlak-ID", text: $planeId).textFieldStyle(.roundedBorder).padding(.horizontal)
            HStack {
                Button("Wissen") { taps = [] }
                Button("Opslaan") {
                    if let d = Double(distance.replacingOccurrences(of: ",", with: ".")), taps.count == 2 {
                        store.references[frame.id] = ReferenceMeasure(referenceId: "REF-\(frame.id)", p1: taps[0], p2: taps[1], distanceM: d,
                                                                      distanceSigmaM: Double(sigma.replacingOccurrences(of: ",", with: ".")), planeId: planeId)
                    }
                }.buttonStyle(.borderedProminent).disabled(taps.count != 2 || Double(distance.replacingOccurrences(of: ",", with: ".")) == nil)
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
        VStack {
            if let obs, let frame, let img = image {
                FrameImageCanvas(frame: frame, image: img, taps: $taps, maxTaps: 1, overlay: obs.corners)
                Picker("Hoek", selection: $index) { ForEach(0..<4) { Text("\($0 + 1)").tag($0) } }.pickerStyle(.segmented).padding(.horizontal)
                HStack {
                    Button("Wissen") { taps = [] }
                    Button("Corrigeer hoek \(index + 1)") {
                        if let p = taps.first { store.correctCorner(observation: obs.id, index: index, to: p, reason: "handmatige correctie"); store.measureAll(); taps = [] }
                    }.buttonStyle(.borderedProminent).disabled(taps.isEmpty)
                }
                Text("Revisies: \(obs.revisions.count) - originele hoeken blijven bewaard.").font(.footnote)
            } else { ProgressView() }
        }
        .navigationTitle("Hoek corrigeren")
        .onAppear { if let u = frame?.imageURL, let d = try? Data(contentsOf: u) { image = UIImage(data: d) } }
    }
}
