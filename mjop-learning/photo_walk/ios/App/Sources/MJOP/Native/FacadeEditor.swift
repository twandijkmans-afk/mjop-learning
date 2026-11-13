import MJOPEngine
import SwiftUI

/// Schermvullende editor voor een gevelscan (geen scrollende pagina eronder, zodat slepen en tikken altijd werken).
/// - Elementen: tik kiest het element onder je vinger (nog eens tikken wisselt bij overlap), of kies het in de lijst onderin.
///   Sleep het element om het te verschuiven, of een hoekpunt/eindpunt om alleen dat punt te verplaatsen.
///   Soort wijzigen, verwijderen, een lijn doortrekken tot de dakrand of het maaiveld, en zelf een element tekenen.
/// - Gevelhoeken: de hoeken van het gekozen vlak verslepen.
/// Alle wijzigingen houden de oorspronkelijke herkenning bij (menselijke controle). Pas bij "Klaar" gaat het terug naar de scan.
struct FacadeEditorView: View {
    enum Mode: String, CaseIterable { case elements = "Elementen", corners = "Gevelhoeken" }

    let image: UIImage
    let onDone: (FacadeScan) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var work: FacadeScan
    @State private var mode: Mode
    @State private var selected: Int?
    @State private var plane: Int?
    @State private var drawType: FacadeElementType?
    @State private var zoom: CGFloat = 1
    @State private var pan: CGSize = .zero
    @State private var active: Active?
    @State private var lastPoint: CGPoint = .zero

    private enum Target { case vertex(Int, Int), corner(Int, Int), move(Int), draw, pan(CGSize) }
    private struct Active { var target: Target; var start: CGPoint; var now: CGPoint }

    init(image: UIImage, scan: FacadeScan, mode: Mode = .elements, onDone: @escaping (FacadeScan) -> Void) {
        self.image = image; self.onDone = onDone
        _work = State(initialValue: scan)
        _mode = State(initialValue: mode)
        _plane = State(initialValue: scan.mainPlane?.id)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button("Annuleer") { dismiss() }
                Spacer()
                Picker("", selection: $mode) { ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) } }
                    .pickerStyle(.segmented).frame(width: 230)
                    .disabled(work.planes?.isEmpty ?? true)
                Spacer()
                Button("Klaar") { onDone(work); dismiss() }.fontWeight(.semibold).accessibilityIdentifier("editorDone")
            }
            .padding(.horizontal, 16).padding(.vertical, 10)
            canvas
            panel
        }
        .background(DS.canvas.ignoresSafeArea())
        .onChange(of: mode) { _ in selected = nil; drawType = nil }
    }

    // MARK: foto met elementen

    private var canvas: some View {
        GeometryReader { g in
            let fitK = min(g.size.width / work.photoWidth, g.size.height / work.photoHeight)
            let k = fitK * zoom
            let origin = CGPoint(x: (g.size.width - work.photoWidth * k) / 2 + pan.width, y: (g.size.height - work.photoHeight * k) / 2 + pan.height)
            let v = { (p: [Double]) in CGPoint(x: origin.x + p[0] * k, y: origin.y + p[1] * k) }
            let ph = { (p: CGPoint) in [Double((p.x - origin.x) / k), Double((p.y - origin.y) / k)] }
            ZStack(alignment: .topLeading) {
                Color.black.opacity(0.92)
                Image(uiImage: image).resizable()
                    .frame(width: work.photoWidth * k, height: work.photoHeight * k)
                    .position(x: origin.x + work.photoWidth * k / 2, y: origin.y + work.photoHeight * k / 2)
                ForEach(Array((work.planes ?? []).enumerated()), id: \.element.id) { idx, pl in
                    shape(pl.corners, closed: true, v)
                        .stroke(FacadeOverlay.planeColor(idx), style: StrokeStyle(lineWidth: mode == .corners && pl.id == plane ? 2.5 : 1.2, dash: [6, 5]))
                }
                ForEach(work.elements) { e in
                    shape(e.points, closed: e.type.kind != .line, v)
                        .stroke(e.id == selected ? Color.white : Self.color(e.type), lineWidth: e.id == selected ? 4 : (e.type.kind == .poly ? 1.5 : 2.5))
                        .opacity(mode == .corners ? 0.45 : 1)
                }
                if mode == .elements, let id = selected, let e = work.elements.first(where: { $0.id == id }) {
                    ForEach(Array(e.points.enumerated()), id: \.offset) { _, p in handle(v(p), color: .white) }
                }
                if mode == .corners, let pl = work.planes?.first(where: { $0.id == plane }), let idx = work.planes?.firstIndex(where: { $0.id == plane }) {
                    ForEach(Array(pl.corners.enumerated()), id: \.offset) { _, p in handle(v(p), color: FacadeOverlay.planeColor(idx)) }
                }
                if let a = active, case .draw = a.target, let t = drawType {
                    Path { p in
                        if t.kind == .line { p.move(to: a.start); p.addLine(to: a.now) }
                        else { p.addRect(CGRect(x: min(a.start.x, a.now.x), y: min(a.start.y, a.now.y), width: abs(a.now.x - a.start.x), height: abs(a.now.y - a.start.y))) }
                    }
                    .stroke(.white, style: StrokeStyle(lineWidth: 2.5, dash: [6, 4]))
                }
            }
            .frame(width: g.size.width, height: g.size.height)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { val in changed(val, k: k, v: v, ph: ph) }.onEnded { val in ended(val, k: k, ph: ph) })
            .overlay(alignment: .topTrailing) { zoomButtons.padding(10) }
            .clipped()
        }
    }

    private func shape(_ pts: [[Double]], closed: Bool, _ v: ([Double]) -> CGPoint) -> Path {
        Path { p in
            guard let f = pts.first else { return }
            p.move(to: v(f)); pts.dropFirst().forEach { p.addLine(to: v($0)) }
            if closed { p.closeSubpath() }
        }
    }

    private func handle(_ c: CGPoint, color: Color) -> some View {
        Circle().fill(color).frame(width: 18, height: 18).overlay(Circle().stroke(.black.opacity(0.5), lineWidth: 1))
            .position(c).allowsHitTesting(false)
    }

    private var zoomButtons: some View {
        VStack(spacing: 8) {
            Button { withAnimation(.dsSpring) { zoom = min(4, zoom * 1.5) } } label: { Image(systemName: "plus.magnifyingglass") }
            Button { withAnimation(.dsSpring) { zoom = max(1, zoom / 1.5); if zoom == 1 { pan = .zero } } } label: { Image(systemName: "minus.magnifyingglass") }
        }
        .font(.title3).foregroundStyle(.white).padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .environment(\.colorScheme, .dark)
    }

    // MARK: gebaren

    private func changed(_ val: DragGesture.Value, k: CGFloat, v: ([Double]) -> CGPoint, ph: (CGPoint) -> [Double]) {
        if active == nil {
            let s = val.startLocation
            func near(_ p: [Double]) -> Bool { hypot(v(p).x - s.x, v(p).y - s.y) < 26 }
            var target: Target = .pan(pan)
            if mode == .corners, let pl = work.planes?.first(where: { $0.id == plane }), let i = pl.corners.firstIndex(where: near) {
                target = .corner(pl.id, i)
            } else if mode == .elements, drawType != nil {
                target = .draw
            } else if mode == .elements, let id = selected, let e = work.elements.first(where: { $0.id == id }) {
                if let i = e.points.firstIndex(where: near) { target = .vertex(id, i) }
                else if FacadeEdit.candidates(work.elements, at: ph(s), tolerance: Double(14 / k)).contains(id) { target = .move(id) }
            }
            active = Active(target: target, start: s, now: s)
            lastPoint = s
        }
        guard var a = active else { return }
        a.now = val.location
        let W = work.photoWidth, H = work.photoHeight
        switch a.target {
        case .vertex(let id, let i): FacadeEdit.moveVertex(&work.elements, id: id, index: i, to: ph(val.location), width: W, height: H)
        case .corner(let pid, let i): moveCorner(pid, i, to: ph(val.location))
        case .move(let id):
            let d = ph(val.location), l = ph(lastPoint)
            FacadeEdit.move(&work.elements, id: id, dx: d[0] - l[0], dy: d[1] - l[1], width: W, height: H)
        case .pan(let start) where zoom > 1: pan = CGSize(width: start.width + val.translation.width, height: start.height + val.translation.height)
        default: break
        }
        lastPoint = val.location
        active = a
    }

    private func ended(_ val: DragGesture.Value, k: CGFloat, ph: (CGPoint) -> [Double]) {
        defer { active = nil }
        guard let a = active else { return }
        let moved = hypot(val.translation.width, val.translation.height) > 6
        switch a.target {
        case .draw:
            if moved, let t = drawType { add(t, from: ph(a.start), to: ph(val.location)) }
        case .pan, .move:
            if !moved, mode == .elements {
                selected = FacadeEdit.nextSelection(work.elements, at: ph(val.location), tolerance: Double(14 / k), current: selected)
            }
        default: break
        }
    }

    private func moveCorner(_ pid: Int, _ i: Int, to p: [Double]) {
        guard let pi = work.planes?.firstIndex(where: { $0.id == pid }) else { return }
        var cs = work.planes![pi].corners
        cs[i] = [min(max(p[0], -work.photoWidth), 2 * work.photoWidth), min(max(p[1], -work.photoHeight), 2 * work.photoHeight)]
        guard FacadePerspective.isConvex(cs) else { return }
        if work.planes![pi].originalCorners == nil { work.planes![pi].originalCorners = work.planes![pi].corners }
        work.planes![pi].corners = cs
        work.planes![pi].editedByUser = true
    }

    private func add(_ t: FacadeElementType, from a: [Double], to b: [Double]) {
        let c = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        let pl = work.planes?.first { FacadePhoto.inside(c, $0.corners) && $0.id != work.mainPlane?.id }?.id ?? work.mainPlane?.id
        let taken = Set((work.removedByUser ?? []).map(\.id))
        if let id = FacadeEdit.add(&work.elements, type: t, from: a, to: b, plane: pl, takenIds: taken) { selected = id }
        drawType = nil
    }

    // MARK: onderpaneel

    @ViewBuilder private var panel: some View {
        VStack(alignment: .leading, spacing: 10) {
            if mode == .corners {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Array((work.planes ?? []).enumerated()), id: \.element.id) { idx, pl in
                            chip(pl.kind.label, color: FacadeOverlay.planeColor(idx), on: pl.id == plane) { plane = pl.id }
                        }
                    }
                }
                Text("Sleep de hoekpunten naar de hoeken van het vlak (zonder dak). De maten rekenen mee.").font(.footnote).foregroundStyle(DS.text2)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(work.elements.filter { $0.type.kind != .poly } + work.elements.filter { $0.type.kind == .poly }) { e in
                            chip("\(Self.short(e.type)) \(e.id)", color: Self.color(e.type), on: e.id == selected) { selected = e.id; drawType = nil }
                        }
                    }
                }
                if let id = selected, let e = work.elements.first(where: { $0.id == id }) {
                    HStack(spacing: 8) {
                        Menu {
                            ForEach(FacadeElementType.allCases.filter { $0.kind == e.type.kind }, id: \.self) { t in
                                Button { _ = FacadeEdit.retype(&work.elements, id: id, to: t) } label: {
                                    if t == e.type { Label(t.label, systemImage: "checkmark") } else { Text(t.label) }
                                }
                            }
                        } label: { Label(e.type.label, systemImage: "tag").lineLimit(1).frame(maxWidth: .infinity) }
                        .buttonStyle(DSSecondaryButton())
                        .accessibilityIdentifier("editorType")
                        Button(role: .destructive) {
                            var rem = work.removedByUser ?? []
                            FacadeEdit.delete(&work.elements, removed: &rem, id: id)
                            work.removedByUser = rem
                            selected = nil
                        } label: { Image(systemName: "trash").font(.headline).frame(width: 50, height: 50) }
                        .background(DS.surface, in: Circle())
                        .accessibilityLabel("Verwijderen")
                    }
                    if e.type.kind == .line {
                        HStack(spacing: 8) {
                            Button { extend(id, upward: true) } label: { Label("Tot dakrand", systemImage: "arrow.up.to.line") }.buttonStyle(DSSecondaryButton())
                            Button { extend(id, upward: false) } label: { Label("Tot maaiveld", systemImage: "arrow.down.to.line") }.buttonStyle(DSSecondaryButton())
                        }
                        .disabled(work.mainPlane == nil)
                    }
                    Text(e.addedByUser == true ? "Door jou toegevoegd." : e.editedByUser == true ? "Aangepast; de oorspronkelijke herkenning blijft bewaard." : "Sleep het element of een hoekpunt. Tik nog eens om een element eronder te kiezen.")
                        .font(.caption).foregroundStyle(DS.text2)
                } else {
                    Menu {
                        ForEach(FacadeElementType.allCases.filter { $0.kind != .poly }, id: \.self) { t in Button(t.label) { drawType = t; selected = nil } }
                    } label: { Label(drawType.map { "Teken: \($0.label)" } ?? "Element toevoegen", systemImage: "plus") }
                    .buttonStyle(DSSecondaryButton())
                    Text(drawType == nil ? "Tik op een element in de foto of kies het hierboven." : (drawType!.kind == .line ? "Sleep van begin tot eind." : "Sleep van hoek tot hoek."))
                        .font(.caption).foregroundStyle(DS.text2)
                }
            }
        }
        .padding(16)
        .background(DS.surface)
    }

    /// Doortrekken tot de bovenrand (dakrand) of onderrand (maaiveld) van het hoofdvlak.
    private func extend(_ id: Int, upward: Bool) {
        guard let c = work.mainPlane?.corners, c.count == 4 else { return }
        let edge = upward ? [c[0], c[1]] : [c[3], c[2]]
        _ = FacadeEdit.extendLine(&work.elements, id: id, to: edge, upward: upward, width: work.photoWidth, height: work.photoHeight)
    }

    private func chip(_ text: String, color: Color, on: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Circle().fill(color).frame(width: 9, height: 9)
                Text(text).font(.footnote.weight(.semibold)).foregroundStyle(on ? Color.white : DS.text)
            }
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(on ? AnyShapeStyle(DS.accent) : AnyShapeStyle(DS.surface2), in: Capsule())
        }
        .buttonStyle(.plain)
    }

    static func short(_ t: FacadeElementType) -> String {
        switch t {
        case .kozijn_raam: return "Raam"
        case .kozijn_deur: return "Deur"
        case .hwa: return "Afvoer"
        case .dakgoot: return "Goot"
        case .boeiboord: return "Boeideel"
        default: return t.label
        }
    }

    static func color(_ t: FacadeElementType) -> Color {
        switch t {
        case .kozijn_raam: return Color(hex: 0x5B74FF)
        case .kozijn_deur: return Color(hex: 0xFF5A5F)
        case .metselwerk, .stucwerk, .gevelbekleding: return Color(hex: 0xF59E0B)
        case .hwa, .dakgoot: return Color(hex: 0x2DD4BF)
        case .boeiboord: return Color(hex: 0xC084FC)
        default: return .white
        }
    }
}
