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
    var body: some View {
        ZStack(alignment: .bottom) {
            ARViewContainer(session: cap.session).ignoresSafeArea()
            VStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Tracking: \(cap.trackingText)")
                    Text(cap.sensorText)
                    Text("Modus: \(cap.modeText) - keyframes: \(cap.keyframeCount)")
                    if let h = cap.hint { Text(h).foregroundStyle(.yellow) }
                }
                .font(.caption).padding(8).background(.black.opacity(0.6)).foregroundStyle(.white).cornerRadius(8)
                HStack {
                    Button { cap.captureKeyframe() } label: { Label("Keyframe", systemImage: "camera") }.buttonStyle(.borderedProminent)
                    NavigationLink("Kozijnen markeren") { KeyframeListView().environmentObject(store) }.buttonStyle(.bordered)
                    NavigationLink("Resultaten") { ResultsView().environmentObject(store) }.buttonStyle(.bordered)
                }
            }.padding()
        }
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
