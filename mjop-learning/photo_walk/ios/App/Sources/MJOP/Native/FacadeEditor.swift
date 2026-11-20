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
    /// Ongedaan maken: eerdere versies van de scan (hooguit 30).
    @State private var history: [FacadeScan] = []
    /// Meerdere elementen tegelijk kiezen.
    @State private var multi = false
    @State private var multiSel: Set<Int> = []
    /// Het laatst gesleepte hoekpunt, voor fijn schuiven met de pijltjes.
    @State private var selVertex: VertexRef?
    @State private var pinchBase: CGFloat?
    @State private var lastTap: (time: Date, point: CGPoint, prev: Int?)?

    private enum VertexRef: Equatable { case element(Int, Int), corner(Int, Int) }
    static let maxZoom: CGFloat = 8

    private enum Target { case vertex(Int, Int), corner(Int, Int), move(Int), draw, pan(CGSize) }
    private struct Active { var target: Target; var start: CGPoint; var now: CGPoint }

    init(image: UIImage, scan: FacadeScan, mode: Mode = .elements, selected: Int? = nil, onDone: @escaping (FacadeScan) -> Void) {
        self.image = image; self.onDone = onDone
        _selected = State(initialValue: selected)
        _work = State(initialValue: scan)
        _mode = State(initialValue: mode)
        _plane = State(initialValue: scan.mainPlane?.id)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Button("Annuleer") { dismiss() }
                Button { undo() } label: { Image(systemName: "arrow.uturn.backward") }
                    .disabled(history.isEmpty).padding(.leading, 6)
                    .accessibilityLabel("Ongedaan maken").accessibilityIdentifier("editorUndo")
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
        .onChange(of: mode) { _ in selected = nil; drawType = nil; selVertex = nil; multi = false; multiSel = [] }
        .onChange(of: selected) { _ in selVertex = nil }
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
                if multi {
                    ForEach(work.elements.filter { multiSel.contains($0.id) }) { e in
                        shape(e.points, closed: e.type.kind != .line, v).stroke(Color.white, style: StrokeStyle(lineWidth: 3.5, dash: [5, 3]))
                    }
                }
                if mode == .elements, !multi, let id = selected, let e = work.elements.first(where: { $0.id == id }) {
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
                if let a = active, isPointDrag(a.target) {
                    loupe(at: a.now, photo: ph(a.now), k: k, canvas: g.size)
                }
            }
            .frame(width: g.size.width, height: g.size.height)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { val in changed(val, k: k, v: v, ph: ph) }.onEnded { val in ended(val, k: k, ph: ph, canvas: g.size) })
            .simultaneousGesture(MagnificationGesture()
                .onChanged { m in
                    if pinchBase == nil { pinchBase = zoom; active = nil }
                    let z = min(Self.maxZoom, max(1, (pinchBase ?? 1) * m))
                    let f = z / zoom
                    pan = CGSize(width: pan.width * f, height: pan.height * f)
                    zoom = z
                }
                .onEnded { _ in
                    pinchBase = nil
                    if zoom <= 1.01 { zoom = 1; pan = .zero }
                })
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
            Button { withAnimation(.dsSpring) { let z = min(Self.maxZoom, zoom * 1.5); pan = CGSize(width: pan.width * z / zoom, height: pan.height * z / zoom); zoom = z } } label: { Image(systemName: "plus.magnifyingglass") }
            Button { withAnimation(.dsSpring) { let z = max(1, zoom / 1.5); pan = z == 1 ? .zero : CGSize(width: pan.width * z / zoom, height: pan.height * z / zoom); zoom = z } } label: { Image(systemName: "minus.magnifyingglass") }
            if zoom > 1 { Text(String(format: "%.1f×", Double(zoom)).replacingOccurrences(of: ".", with: ",")).font(.caption2.weight(.bold)) }
        }
        .font(.title3).foregroundStyle(.white).padding(10)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .environment(\.colorScheme, .dark)
    }

    /// Vergrootglas boven de vinger tijdens het slepen van een hoekpunt: 3× sterker vergroot dan het beeld, met een kruisje.
    private func loupe(at finger: CGPoint, photo p: [Double], k: CGFloat, canvas: CGSize) -> some View {
        let L: CGFloat = 120, kk = k * 3
        let o = CGPoint(x: L / 2 - CGFloat(p[0]) * kk, y: L / 2 - CGFloat(p[1]) * kk)
        let v2 = { (q: [Double]) in CGPoint(x: o.x + CGFloat(q[0]) * kk, y: o.y + CGFloat(q[1]) * kk) }
        let above = finger.y - 100 > L / 2
        let cx = min(max(finger.x, L / 2 + 4), canvas.width - L / 2 - 4)
        let cy = above ? finger.y - 100 : finger.y + 100
        return ZStack(alignment: .topLeading) {
            Color.black
            Image(uiImage: image).resizable()
                .frame(width: work.photoWidth * kk, height: work.photoHeight * kk)
                .position(x: o.x + work.photoWidth * kk / 2, y: o.y + work.photoHeight * kk / 2)
            ForEach(work.planes ?? []) { pl in shape(pl.corners, closed: true, v2).stroke(Color.yellow, lineWidth: 1.5) }
            ForEach(work.elements) { e in
                shape(e.points, closed: e.type.kind != .line, v2).stroke(e.id == selected ? Color.white : Self.color(e.type), lineWidth: e.id == selected ? 2.5 : 1.5)
            }
            Path { pth in pth.move(to: CGPoint(x: L / 2 - 14, y: L / 2)); pth.addLine(to: CGPoint(x: L / 2 + 14, y: L / 2))
                pth.move(to: CGPoint(x: L / 2, y: L / 2 - 14)); pth.addLine(to: CGPoint(x: L / 2, y: L / 2 + 14)) }
                .stroke(Color.red, lineWidth: 1.5)
        }
        .frame(width: L, height: L)
        .clipShape(Circle())
        .overlay(Circle().stroke(.white, lineWidth: 3))
        .shadow(color: .black.opacity(0.5), radius: 6)
        .position(x: cx, y: cy)
        .allowsHitTesting(false)
    }

    private func isPointDrag(_ t: Target) -> Bool {
        switch t { case .vertex, .corner: return true; default: return false }
    }

    private func snapshot() {
        history.append(work)
        if history.count > 30 { history.removeFirst() }
    }

    private func undo() {
        guard let last = history.popLast() else { return }
        work = last
        if let s = selected, !work.elements.contains(where: { $0.id == s }) { selected = nil }
        multiSel = multiSel.filter { id in work.elements.contains { $0.id == id } }
        selVertex = nil
    }

    // MARK: gebaren

    private func changed(_ val: DragGesture.Value, k: CGFloat, v: ([Double]) -> CGPoint, ph: (CGPoint) -> [Double]) {
        if pinchBase != nil { return }   // twee vingers: alleen zoomen
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
            if multi, case .move = target { target = .pan(pan) }
            if multi, case .vertex = target { target = .pan(pan) }
            switch target { case .vertex, .corner, .move: snapshot(); default: break }
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

    private func ended(_ val: DragGesture.Value, k: CGFloat, ph: (CGPoint) -> [Double], canvas: CGSize) {
        defer { active = nil }
        guard let a = active, pinchBase == nil else { return }
        let moved = hypot(val.translation.width, val.translation.height) > 6
        switch a.target {
        case .draw:
            if moved, let t = drawType { add(t, from: ph(a.start), to: ph(val.location)) }
        case .vertex(let id, let i):
            if moved { selVertex = .element(id, i) } else if history.last == work { _ = history.popLast() }
        case .corner(let pid, let i):
            if moved { selVertex = .corner(pid, i) } else if history.last == work { _ = history.popLast() }
        case .pan, .move:
            if case .move = a.target, !moved, history.last == work { _ = history.popLast() }
            guard !moved else { break }
            let loc = val.location
            // Dubbeltik: inzoomen op die plek (3×), of terug naar het hele beeld.
            if let t = lastTap, Date().timeIntervalSince(t.time) < 0.35, hypot(t.point.x - loc.x, t.point.y - loc.y) < 30 {
                selected = t.prev
                lastTap = nil
                doubleTap(at: ph(loc), k: k)
                return
            }
            lastTap = (Date(), loc, selected)
            guard mode == .elements else { break }
            if multi {
                if let id = FacadeEdit.hit(work.elements, at: ph(loc), tolerance: Double(14 / k)) {
                    if multiSel.contains(id) { multiSel.remove(id) } else { multiSel.insert(id) }
                }
            } else {
                selected = FacadeEdit.nextSelection(work.elements, at: ph(loc), tolerance: Double(14 / k), current: selected)
            }
        }
    }

    /// Dubbeltik: bij het hele beeld inzoomen tot 3× met dat punt in het midden; anders terug naar het hele beeld.
    private func doubleTap(at p: [Double], k: CGFloat) {
        withAnimation(.dsSpring) {
            if zoom > 1.01 { zoom = 1; pan = .zero; return }
            let fitK = k / zoom, z: CGFloat = 3, k2 = fitK * z
            pan = CGSize(width: k2 * (work.photoWidth / 2 - CGFloat(p[0])), height: k2 * (work.photoHeight / 2 - CGFloat(p[1])))
            zoom = z
        }
    }

    /// Pijltjes: het gekozen hoekpunt één fotopixel verschuiven.
    private func nudge(_ dx: Double, _ dy: Double) {
        guard let sv = selVertex else { return }
        snapshot()
        switch sv {
        case .element(let id, let i):
            guard let e = work.elements.first(where: { $0.id == id }), e.points.indices.contains(i) else { return }
            FacadeEdit.moveVertex(&work.elements, id: id, index: i, to: [e.points[i][0] + dx, e.points[i][1] + dy], width: work.photoWidth, height: work.photoHeight)
        case .corner(let pid, let i):
            guard let pl = work.planes?.first(where: { $0.id == pid }), pl.corners.indices.contains(i) else { return }
            moveCorner(pid, i, to: [pl.corners[i][0] + dx, pl.corners[i][1] + dy])
        }
    }

    private var nudgePad: some View {
        HStack(spacing: 8) {
            Text("Punt fijn schuiven").font(.caption.weight(.semibold)).foregroundStyle(DS.text2)
            Spacer()
            let icons = ["arrow.left", "arrow.up", "arrow.down", "arrow.right"]
            let steps: [(Double, Double)] = [(-1, 0), (0, -1), (0, 1), (1, 0)]
            ForEach(0..<4, id: \.self) { i in
                Button { nudge(steps[i].0, steps[i].1) } label: { Image(systemName: icons[i]).font(.headline).frame(width: 44, height: 40) }
                    .background(DS.surface2, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .buttonStyle(.plain)
            }
        }
        .accessibilityIdentifier("nudgePad")
    }

    private func planeOf(_ e: FacadePhotoElement) -> FacadePlane? {
        if let p = e.plane { return work.planes?.first { $0.id == p } }
        return work.mainPlane
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
        snapshot()
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
                if case .corner = selVertex { nudgePad }
                Text("Sleep de hoekpunten naar de hoeken van het vlak (zonder dak). Knijp of dubbeltik om in te zoomen; tijdens het slepen zie je een vergrootglas.").font(.footnote).foregroundStyle(DS.text2)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        chip(multi ? "Klaar met kiezen" : "Kiezen", color: DS.accent, on: multi) { multi.toggle(); multiSel = []; selected = nil; drawType = nil }
                        ForEach(work.elements.filter { $0.type.kind != .poly } + work.elements.filter { $0.type.kind == .poly }) { e in
                            chip("\(Self.short(e.type)) \(e.id)", color: Self.color(e.type), on: multi ? multiSel.contains(e.id) : e.id == selected) {
                                if multi { if multiSel.contains(e.id) { multiSel.remove(e.id) } else { multiSel.insert(e.id) } } else { selected = e.id; drawType = nil }
                            }
                        }
                    }
                }
                if multi {
                    multiPanel
                } else if let id = selected, let e = work.elements.first(where: { $0.id == id }) {
                    HStack(spacing: 8) {
                        Menu {
                            ForEach(FacadeElementType.allCases.filter { $0.kind == e.type.kind }, id: \.self) { t in
                                Button { snapshot(); _ = FacadeEdit.retype(&work.elements, id: id, to: t) } label: {
                                    if t == e.type { Label(t.label, systemImage: "checkmark") } else { Text(t.label) }
                                }
                            }
                        } label: { Label(e.type.label, systemImage: "tag").lineLimit(1).frame(maxWidth: .infinity) }
                        .buttonStyle(DSSecondaryButton())
                        .accessibilityIdentifier("editorType")
                        Button(role: .destructive) {
                            snapshot()
                            var rem = work.removedByUser ?? []
                            FacadeEdit.delete(&work.elements, removed: &rem, id: id)
                            work.removedByUser = rem
                            selected = nil
                        } label: { Image(systemName: "trash").font(.headline).frame(width: 50, height: 50) }
                        .background(DS.surface, in: Circle())
                        .accessibilityLabel("Verwijderen")
                    }
                    if case .element(let vid, _) = selVertex, vid == id { nudgePad }
                    HStack(spacing: 8) {
                        if e.type.kind == .quad {
                            let refs = work.elements.filter { $0.id != id && $0.type.kind == .quad && $0.type == e.type }
                            Menu {
                                ForEach(refs) { r in
                                    Button("\(r.type.label) \(r.id)") {
                                        snapshot()
                                        _ = FacadeEdit.matchSize(&work.elements, id: id, to: r.id, plane: planeOf(e), width: work.photoWidth, height: work.photoHeight)
                                    }
                                }
                            } label: { Label("Gelijk maken aan", systemImage: "equal.square") }
                            .buttonStyle(DSSecondaryButton())
                            .disabled(refs.isEmpty)
                        }
                        Button {
                            snapshot()
                            let xs = e.points.map { $0[0] }
                            let w = (xs.max() ?? 0) - (xs.min() ?? 0)
                            let taken = Set((work.removedByUser ?? []).map(\.id))
                            if let n = FacadeEdit.duplicate(&work.elements, id: id, dx: e.type.kind == .line ? max(20, w + 20) : w * 1.1, dy: 0,
                                                            width: work.photoWidth, height: work.photoHeight, takenIds: taken) { selected = n }
                        } label: { Label("Kopie", systemImage: "plus.square.on.square") }
                        .buttonStyle(DSSecondaryButton())
                        .accessibilityIdentifier("editorCopy")
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

    /// Meerdere elementen tegelijk: soort wijzigen (alleen als ze dezelfde vorm hebben) of verwijderen.
    @ViewBuilder private var multiPanel: some View {
        let sel = work.elements.filter { multiSel.contains($0.id) }
        let kinds = Set(sel.map { $0.type.kind })
        HStack(spacing: 8) {
            Menu {
                if let kind = kinds.first, kinds.count == 1 {
                    ForEach(FacadeElementType.allCases.filter { $0.kind == kind }, id: \.self) { t in
                        Button(t.label) { snapshot(); for e in sel { _ = FacadeEdit.retype(&work.elements, id: e.id, to: t) } }
                    }
                }
            } label: { Label("Soort wijzigen", systemImage: "tag").frame(maxWidth: .infinity) }
            .buttonStyle(DSSecondaryButton())
            .disabled(sel.isEmpty || kinds.count != 1)
            Button(role: .destructive) {
                snapshot()
                var rem = work.removedByUser ?? []
                for e in sel { FacadeEdit.delete(&work.elements, removed: &rem, id: e.id) }
                work.removedByUser = rem
                multiSel = []
            } label: { Label("Verwijder \(sel.count)", systemImage: "trash").frame(maxWidth: .infinity) }
            .buttonStyle(DSSecondaryButton())
            .disabled(sel.isEmpty)
        }
        Text(sel.isEmpty ? "Tik op elementen in de foto of hierboven om ze te kiezen." : (kinds.count == 1 ? "\(sel.count) gekozen." : "\(sel.count) gekozen; soort wijzigen kan alleen bij dezelfde vorm (kader, lijn of vlak)."))
            .font(.caption).foregroundStyle(DS.text2)
    }

    /// Doortrekken tot de bovenrand (dakrand) of onderrand (maaiveld) van het hoofdvlak.
    private func extend(_ id: Int, upward: Bool) {
        guard let c = work.mainPlane?.corners, c.count == 4 else { return }
        snapshot()
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
