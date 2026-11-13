import MJOPEngine
import MJOPIntegration
import SwiftUI

/// Luchtfoto van boven met de BAG-omtrek: elke gevelzijde genummerd, de gekozen zijde blauw en een camera-icoon op de
/// aanbevolen standplaats. Zonder luchtfoto (offline) blijft de omtrek zichtbaar op een effen achtergrond.
struct FacadeSiteMap: View {
    let footprint: [[Double]]
    let sides: [FacadeSide]
    let selected: Int?
    let done: Set<Int>
    var onSelect: (Int) -> Void = { _ in }
    @State private var image: UIImage?

    var body: some View {
        GeometryReader { g in
            let w = g.size.width, h = g.size.height
            if let f = FootprintMap.frame(ring: footprint, aspect: w / max(h, 1), marginM: 14) {
                let px = { (ll: [Double]) -> CGPoint in let p = f.pixel(ll, w: w, h: h); return CGPoint(x: p[0], y: p[1]) }
                let origin = footprint[0]
                let ll = { (m: [Double]) in FootprintMap.lonLat(meters: m, origin: origin) }
                ZStack(alignment: .topLeading) {
                    if let image { Image(uiImage: image).resizable() } else { DS.surface2 }
                    Path { p in
                        guard let first = footprint.first else { return }
                        p.move(to: px(first)); footprint.dropFirst().forEach { p.addLine(to: px($0)) }; p.closeSubpath()
                    }
                    .fill(Color.white.opacity(image == nil ? 0.6 : 0.18))
                    ForEach(sides) { s in
                        if let a = s.from, let b = s.to {
                            let pa = px(ll(a)), pb = px(ll(b))
                            let on = s.id == selected
                            Path { p in p.move(to: pa); p.addLine(to: pb) }
                                .stroke(on ? DS.accent : (done.contains(s.id) ? DS.ok : Color.white), style: StrokeStyle(lineWidth: on ? 6 : 3, lineCap: .round))
                                .shadow(color: .black.opacity(0.35), radius: 2)
                                .contentShape(Path { p in p.move(to: pa); p.addLine(to: pb) }.strokedPath(StrokeStyle(lineWidth: 34, lineCap: .round)))
                                .onTapGesture { onSelect(s.id) }
                                .accessibilityLabel("Gevel \(s.id) op het \(s.facing)")
                            Text("\(s.id)").font(.caption2.weight(.bold)).foregroundStyle(on ? Color.white : DS.text)
                                .frame(width: 20, height: 20).background(on ? DS.accent : Color.white, in: Circle())
                                .position(x: (pa.x + pb.x) / 2, y: (pa.y + pb.y) / 2)
                                .allowsHitTesting(false)
                        }
                    }
                    if let s = sides.first(where: { $0.id == selected }), let a = s.from, let b = s.to {
                        let ringM = FootprintSides.meters(footprint.map { ($0[0], $0[1]) })
                        let st = FootprintMap.standpoint(from: a, to: b, ringM: ringM)
                        let cam = px(ll(st.point)), mid = px(ll([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]))
                        Path { p in p.move(to: cam); p.addLine(to: mid) }
                            .stroke(DS.accent, style: StrokeStyle(lineWidth: 2, dash: [5, 4]))
                        Image(systemName: "camera.fill").font(.caption.weight(.bold)).foregroundStyle(.white)
                            .frame(width: 30, height: 30).background(DS.accent, in: Circle())
                            .overlay(Circle().stroke(.white, lineWidth: 2))
                            .position(cam)
                            .allowsHitTesting(false)
                    }
                    if image != nil {
                        Text(AerialPhoto.attribution).font(.system(size: 9)).foregroundStyle(.white.opacity(0.85))
                            .padding(.horizontal, 6).padding(.vertical, 2).background(.black.opacity(0.35), in: Capsule())
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing).padding(6)
                    }
                }
                .task(id: Int(w)) { await load(f, w: w, h: h) }
            } else {
                DS.surface2
            }
        }
        .frame(height: 230)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
    }

    private func load(_ f: FootprintMap.Frame, w: CGFloat, h: CGFloat) async {
        guard image == nil, w > 0, h > 0 else { return }
        let scale = min(2, 1600 / max(w, h))
        guard let url = AerialPhoto.imageURL(mercatorBox: (f.minX, f.minY, f.maxX, f.maxY), pixelWidth: Int(w * scale), pixelHeight: Int(h * scale)) else { return }
        var r = URLRequest(url: url); r.timeoutInterval = 15
        if let res = try? await URLSession.shared.data(for: r), (res.1 as? HTTPURLResponse)?.statusCode == 200, let img = UIImage(data: res.0) { image = img }
    }
}

extension FootprintMap {
    /// Advies in woorden voor een zijde: hoe ver van de gevel te gaan staan.
    static func advice(for s: FacadeSide, footprint: [[Double]]) -> String? {
        guard let a = s.from, let b = s.to, footprint.count >= 3 else { return nil }
        let d = standpoint(from: a, to: b, ringM: FootprintSides.meters(footprint.map { ($0[0], $0[1]) })).distanceM
        return String(format: "Sta ongeveer %.0f m recht voor het midden van de gevel (camera-icoon), telefoon rechtop, 0,5×.", d)
    }
}
