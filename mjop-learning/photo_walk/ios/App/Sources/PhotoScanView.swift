import ARKit
import SwiftUI

/// Eenvoudige foto-workflow: camera -> één fotoknop -> automatische kandidaat-kozijnen met kaders en voorlopige maten op de foto.
/// Bij de foto worden het originele camerabeeld, de intrinsics, de camerapose, de trackingstatus en (indien beschikbaar) de LiDAR-diepte gelijktijdig vastgelegd.
/// De zoom hier is een VISUELE vergroting van de voorvertoning; hij raakt ARKit, intrinsics, diepte en de vastgelegde foto niet.
struct PhotoScanView: View {
    @EnvironmentObject var store: ScanStore
    @StateObject private var cap = CaptureCoordinator()
    @State private var zoom: CGFloat = 1
    @State private var baseZoom: CGFloat = 1
    @State private var offset: CGSize = .zero
    @State private var baseOffset: CGSize = .zero
    @State private var resultFrame: String? = nil
    @State private var showResult = false
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

    private func shoot() {
        guard let kf = cap.captureKeyframe() else { return }
        UIImpactFeedbackGenerator(style: .heavy).impactOccurred()
        store.tagKeyframe(kf.id, world: cap.worldId)
        resultFrame = kf.id
        showResult = true
        store.persist()
        Task { await store.analyze(frameId: kf.id) }
    }

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                ARViewContainer(session: cap.session)
                    .scaleEffect(zoom).offset(offset)
                    .frame(width: geo.size.width, height: geo.size.height).clipped()
                    .gesture(MagnificationGesture()
                        .onChanged { v in zoom = min(max(baseZoom * v, 1), maxZoom); offset = clampOffset(baseOffset, geo.size, zoom) }
                        .onEnded { _ in baseZoom = zoom; baseOffset = offset })
                    .simultaneousGesture(DragGesture()
                        .onChanged { g in if zoom > 1 { offset = clampOffset(CGSize(width: baseOffset.width + g.translation.width, height: baseOffset.height + g.translation.height), geo.size, zoom) } }
                        .onEnded { _ in baseOffset = offset })
                    .simultaneousGesture(TapGesture(count: 2).onEnded { setZoom(1, size: geo.size) })
                VStack(spacing: 10) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Tracking: \(cap.trackingText)")
                        Text(cap.sensorText)
                        if let h = cap.hint { Text(h).foregroundStyle(.yellow) }
                        Text("Houd het hele kozijn/de gevel in beeld, recht op de gevel, 2-4 m afstand. Zoom = alleen voorvertoning; de foto wordt volledig en onvergroot vastgelegd.")
                            .font(.caption2).foregroundStyle(.white.opacity(0.85))
                    }
                    .font(.caption).padding(8).background(.black.opacity(0.6)).foregroundStyle(.white).cornerRadius(8)
                    HStack(spacing: 8) {
                        ForEach([1, 2, 4], id: \.self) { z in
                            Button("\(z)×") { setZoom(CGFloat(z), size: geo.size) }.buttonStyle(.bordered).tint(.white).accessibilityIdentifier("photoZoom\(z)")
                        }
                        Slider(value: Binding(get: { Double(zoom) }, set: { setZoom(CGFloat($0), size: geo.size, animated: false) }), in: 1...Double(maxZoom))
                            .accessibilityIdentifier("photoZoomSlider")
                    }.padding(8).background(.black.opacity(0.5)).cornerRadius(8)
                    HStack(alignment: .center) {
                        NavigationLink("Foto's (\(store.keyframes.count))") { PhotoListView().environmentObject(store) }
                            .buttonStyle(.bordered).tint(.white).accessibilityIdentifier("photoListLink")
                        Spacer()
                        Button(action: shoot) {
                            ZStack { Circle().fill(.white).frame(width: 74, height: 74); Circle().stroke(.black.opacity(0.6), lineWidth: 3).frame(width: 62, height: 62) }
                        }.disabled(!cap.hasFrame).opacity(cap.hasFrame ? 1 : 0.4).accessibilityIdentifier("shutterButton").accessibilityLabel("Foto maken")
                        Spacer()
                        NavigationLink("Overzicht") { ResultsView().environmentObject(store) }.buttonStyle(.bordered).tint(.white)
                    }
                }.padding()
                VStack { HStack { Spacer()
                    Text(String(format: "%.1f×", Double(zoom))).font(.system(.headline, design: .rounded).bold()).monospacedDigit()
                        .padding(.horizontal, 10).padding(.vertical, 5).background(.black.opacity(0.65)).foregroundStyle(.white).cornerRadius(8)
                        .accessibilityIdentifier("photoZoomIndicator")
                }.padding(); Spacer() }
            }
        }
        .ignoresSafeArea(edges: .top)
        .onAppear { cap.start(store: store) }
        .onDisappear { cap.session.pause() }
        .navigationTitle(store.round != nil && !store.facadeId.isEmpty ? "Gevel: \(store.facadeId)" : "Foto-scan").navigationBarTitleDisplayMode(.inline)
        .navigationDestination(isPresented: $showResult) {
            if let id = resultFrame { PhotoResultView(frameId: id).environmentObject(store) }
        }
    }
}

struct PhotoListView: View {
    @EnvironmentObject var store: ScanStore
    var body: some View {
        List(store.keyframes) { kf in
            NavigationLink("\(kf.id) - \(store.observations.filter { $0.frameId == kf.id && !$0.rejected }.count) kandidaten - tracking \(kf.trackingState)\(kf.depth == nil ? " - geen diepte" : "")") {
                PhotoResultView(frameId: kf.id).environmentObject(store)
            }
        }.navigationTitle("Foto's")
    }
}
