import ARKit
import SceneKit
import SwiftUI

struct ARViewContainer: UIViewRepresentable {
    let session: ARSession
    func makeUIView(context: Context) -> ARSCNView { let v = ARSCNView(); v.session = session; v.automaticallyUpdatesLighting = true; return v }
    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}

struct LiveScanView: View {
    @EnvironmentObject var store: ScanStore
    @StateObject private var cap = CaptureCoordinator()
    /// VISUELE zoom van de cameravoorvertoning. De ARKit-sessie, de capturedImage, de intrinsics en de LiDAR-diepte blijven onaangetast:
    /// een vastgelegd keyframe is altijd de volledige, onvergrote opname. Visuele zoom geeft GEEN extra metrische nauwkeurigheid.
    @State private var zoom: CGFloat = 1
    @State private var baseZoom: CGFloat = 1
    @State private var offset: CGSize = .zero
    @State private var baseOffset: CGSize = .zero
    private let maxZoom: CGFloat = 4

    private func clampOffset(_ o: CGSize, _ size: CGSize, _ z: CGFloat) -> CGSize {
        let mx = max(0, (z - 1) * size.width / 2), my = max(0, (z - 1) * size.height / 2)
        return CGSize(width: min(max(o.width, -mx), mx), height: min(max(o.height, -my), my))
    }

    private func setZoom(_ z: CGFloat, size: CGSize, animated: Bool = true) {
        let c = min(max(z, 1), maxZoom)
        let apply = { zoom = c; baseZoom = c; offset = clampOffset(offset, size, c); baseOffset = offset }
        if animated { withAnimation(.easeInOut(duration: 0.25)) { apply() } } else { apply() }
    }

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                ARViewContainer(session: cap.session)
                    .scaleEffect(zoom)
                    .offset(offset)
                    .frame(width: geo.size.width, height: geo.size.height)
                    .clipped()
                    .gesture(MagnificationGesture()
                        .onChanged { v in zoom = min(max(baseZoom * v, 1), maxZoom); offset = clampOffset(baseOffset, geo.size, zoom) }
                        .onEnded { _ in baseZoom = zoom; baseOffset = offset })
                    .simultaneousGesture(DragGesture()
                        .onChanged { g in if zoom > 1 { offset = clampOffset(CGSize(width: baseOffset.width + g.translation.width, height: baseOffset.height + g.translation.height), geo.size, zoom) } }
                        .onEnded { _ in baseOffset = offset })
                    .simultaneousGesture(TapGesture(count: 2).onEnded { setZoom(1, size: geo.size) })
                VStack(spacing: 8) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Tracking: \(cap.trackingText)")
                        Text(cap.sensorText)
                        Text("Modus: \(cap.modeText) - keyframes: \(cap.keyframeCount)")
                        if let h = cap.hint { Text(h).foregroundStyle(.yellow) }
                        Text("Zoom = alleen voorvertoning; keyframe en meting gebruiken de volledige, onvergrote opname (geen extra nauwkeurigheid).").font(.caption2).foregroundStyle(.white.opacity(0.8))
                    }
                    .font(.caption).padding(8).background(.black.opacity(0.6)).foregroundStyle(.white).cornerRadius(8)
                    HStack(spacing: 8) {
                        ForEach([1, 2, 4], id: \.self) { z in
                            Button("\(z)×") { setZoom(CGFloat(z), size: geo.size) }.buttonStyle(.bordered).tint(.white).accessibilityIdentifier("liveZoom\(z)")
                        }
                        Slider(value: Binding(get: { Double(zoom) }, set: { setZoom(CGFloat($0), size: geo.size, animated: false) }), in: 1...Double(maxZoom))
                            .accessibilityIdentifier("liveZoomSlider")
                    }.padding(8).background(.black.opacity(0.5)).cornerRadius(8)
                    HStack {
                        Button { cap.captureKeyframe() } label: { Label("Keyframe", systemImage: "camera") }.buttonStyle(.borderedProminent)
                        NavigationLink("Kozijnen markeren") { KeyframeListView().environmentObject(store) }.buttonStyle(.bordered)
                        NavigationLink("Resultaten") { ResultsView().environmentObject(store) }.buttonStyle(.bordered)
                    }
                }.padding()
                VStack { HStack { Spacer()
                    Text(String(format: "%.1f×", Double(zoom))).font(.system(.headline, design: .rounded).bold()).monospacedDigit()
                        .padding(.horizontal, 10).padding(.vertical, 5).background(.black.opacity(0.65)).foregroundStyle(.white).cornerRadius(8)
                        .accessibilityIdentifier("liveZoomIndicator")
                }.padding(); Spacer() }
            }
        }
        .ignoresSafeArea(edges: .top)
        .onAppear { cap.start(store: store) }
        .onDisappear { cap.session.pause() }
        .navigationTitle("Gevelscan").navigationBarTitleDisplayMode(.inline)
    }
}

struct KeyframeListView: View {
    @EnvironmentObject var store: ScanStore
    var body: some View {
        List(store.keyframes) { kf in
            VStack(alignment: .leading) {
                NavigationLink("\(kf.id) - tracking \(kf.trackingState)\(kf.depth == nil ? " - geen diepte" : "")") { CornerPickerView(frame: kf).environmentObject(store) }
                NavigationLink("Referentiemaat voor \(kf.id)\(store.references[kf.id] != nil ? " (ingevoerd)" : "")") { ReferencePickerView(frame: kf).environmentObject(store) }.font(.footnote)
            }
        }.navigationTitle("Keyframes")
    }
}
