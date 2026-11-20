import MJOPEngine
import MJOPIntegration
import SwiftUI
import UIKit

/// Dakscan van boven: de PDOK-luchtfoto rond de BAG-omtrek ophalen, Claude de dakvlakken laten aanwijzen en er een scan van maken
/// (sideId 0) die dezelfde controle, editor en elementenlijst gebruikt als een gevel.
enum RoofScanner {
    static let pixelWidth = 1600, pixelHeight = 1200

    struct Capture {
        var image: UIImage
        var jpeg: Data
        var frame: FootprintMap.Frame
        var outline: [[Double]]
        var mpp: Double
    }

    private static var cache: [String: UIImage] = [:]

    static func frame(_ footprint: [[Double]]) -> FootprintMap.Frame? {
        FootprintMap.frame(ring: footprint, aspect: Double(pixelWidth) / Double(pixelHeight), marginM: 4)
    }

    static func outline(_ footprint: [[Double]], frame f: FootprintMap.Frame) -> [[Double]] {
        footprint.map { f.pixel($0, w: Double(pixelWidth), h: Double(pixelHeight)) }
    }

    /// Haalt de luchtfoto (PDOK, Actueel_orthoHR) voor een kaartuitsnede op; bewaard in een cache.
    static func image(box f: FootprintMap.Frame) async -> (UIImage, Data)? {
        let key = String(format: "%.1f,%.1f,%.1f,%.1f", f.minX, f.minY, f.maxX, f.maxY)
        guard let url = AerialPhoto.imageURL(mercatorBox: (f.minX, f.minY, f.maxX, f.maxY), pixelWidth: pixelWidth, pixelHeight: pixelHeight),
              let res = try? await URLSession.shared.data(from: url), (res.1 as? HTTPURLResponse)?.statusCode == 200,
              let img = UIImage(data: res.0) else { return nil }
        await MainActor.run { cache[key] = img }
        return (img, res.0)
    }

    /// De luchtfoto bij een bestaande dakscan (opnieuw opgehaald met dezelfde uitsnede).
    static func image(for scan: FacadeScan) async -> UIImage? {
        guard let b = scan.mercatorBox, b.count == 4 else { return nil }
        let f = FootprintMap.Frame(minX: b[0], minY: b[1], maxX: b[2], maxY: b[3])
        let key = String(format: "%.1f,%.1f,%.1f,%.1f", f.minX, f.minY, f.maxX, f.maxY)
        if let c = await MainActor.run(body: { cache[key] }) { return c }
        return await image(box: f)?.0
    }

    static func capture(footprint: [[Double]]) async throws -> Capture {
        guard footprint.count >= 3, let f = frame(footprint) else { throw BackendError.message("Voor dit gebouw is geen BAG-omtrek bekend.") }
        guard let got = await image(box: f) else { throw BackendError.message("De luchtfoto kon niet worden opgehaald (PDOK). Controleer je internet.") }
        let img = got.0, data = got.1
        let lat = footprint.map { $0[1] }.reduce(0, +) / Double(footprint.count)
        guard let mpp = RoofPhoto.metersPerPixel(mercatorWidth: f.maxX - f.minX, pixelWidth: Double(pixelWidth), latitude: lat) else {
            throw BackendError.message("De schaal van de luchtfoto kon niet worden bepaald.")
        }
        return Capture(image: img, jpeg: data, frame: f, outline: outline(footprint, frame: f), mpp: mpp)
    }

    /// Volledige dakscan: luchtfoto, herkenning door Claude, en een scan met de exacte schaal van de uitsnede.
    static func scan(model: ProjectModel, key: String) async throws -> (FacadeScan, UIImage, [[Double]]) {
        let c = try await capture(footprint: model.footprint ?? [])
        let W = Double(pixelWidth), H = Double(pixelHeight)
        let data = try await ClaudeVision.post(key: key) { structured in
            RoofPhoto.requestBody(jpegBase64: c.jpeg.base64EncodedString(), width: pixelWidth, height: pixelHeight, outline: c.outline, metersPerPixel: c.mpp, structured: structured)
        }
        let r = try RoofPhoto.parse(data, width: W, height: H, outline: c.outline, metersPerPixel: c.mpp)
        var s = FacadeScan(sideId: 0, facing: "dak", widthM: c.mpp * W, photoWidth: W, photoHeight: H, referenceLeftX: 0, referenceRightX: W,
                           elements: r.recognition.elements, skipped: r.recognition.skipped, model: FacadePhoto.model, promptVersion: RoofPhoto.promptVersion,
                           scannedAt: Date())
        s.defects = r.recognition.defects
        s.merged = r.recognition.merged
        s.conflicts = r.recognition.conflicts
        s.mercatorBox = [c.frame.minX, c.frame.minY, c.frame.maxX, c.frame.maxY]
        s.bagSchuinM2 = model.building.dakSchuinM2
        s.bagPlatM2 = model.building.dakPlatM2
        s.outsideRoof = r.outside
        return (s, c.image, c.outline)
    }
}

/// Stap 1 van de gevelscan: het dak van boven. Start vanzelf als er nog geen dakscan is (en er een BAG-omtrek en een sleutel zijn).
struct RoofStepCard: View {
    let model: ProjectModel
    let demo: Bool
    let onAccept: (FacadeScan) -> Void
    @State private var running = false
    @State private var error: String?
    @State private var pending: Pending?
    @State private var triedAuto = false
    @State private var opening = false

    struct Pending: Identifiable { let scan: FacadeScan; let image: UIImage; let outline: [[Double]]; let id = UUID() }

    private var canRun: Bool { (model.footprint ?? []).count >= 3 && !demo && ClaudeKey.load() != nil }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                DSIcon(systemName: "square.split.bottomrightquarter")
                VStack(alignment: .leading, spacing: 3) {
                    Text(model.roof == nil ? "Stap 1 · Dak van boven" : "Dak · gescand").font(.headline).foregroundStyle(DS.text)
                    Text(subtitle).font(.subheadline).foregroundStyle(DS.text2)
                }
            }
            if let error { DSNotice(kind: .warn, text: error) }
            if running {
                HStack(spacing: 10) { ProgressView(); Text("Dak wordt herkend op de luchtfoto… (meestal een halve tot een hele minuut)").font(.footnote).foregroundStyle(DS.text2) }
            } else if let roof = model.roof {
                HStack(spacing: 10) {
                    Button { Task { await open(roof) } } label: { Label(opening ? "Laden…" : "Bekijken", systemImage: "eye") }.buttonStyle(DSSecondaryButton())
                    Button { Task { await run() } } label: { Label("Opnieuw", systemImage: "arrow.clockwise") }.buttonStyle(DSSecondaryButton()).disabled(!canRun)
                }
            } else if (model.footprint ?? []).count < 3 {
                Text("Voor dit gebouw is geen BAG-omtrek bekend; de dakscan kan niet. Je kunt gewoon verder met de gevels.").font(.footnote).foregroundStyle(DS.text2)
            } else if !canRun {
                Text(demo ? "In de demo wordt het dak niet gescand." : "Voor de dakscan is een Claude-sleutel nodig. Je kunt ook eerst de gevels doen.").font(.footnote).foregroundStyle(DS.text2)
            } else {
                Button { Task { await run() } } label: { Label("Dak scannen", systemImage: "viewfinder") }.buttonStyle(DSPrimaryButton())
                    .accessibilityIdentifier("roofScan")
            }
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading).dsCard(radius: 20)
        .task {
            guard model.roof == nil, canRun, !triedAuto else { return }
            triedAuto = true
            await run()
        }
        .fullScreenCover(item: $pending) { p in
            RoofResultView(image: p.image, scan: p.scan, outline: p.outline, onAccept: { s in onAccept(s); pending = nil }, onRetry: { pending = nil; Task { await run() } })
        }
    }

    private var subtitle: String {
        if let r = model.roof {
            let flat = r.flatCheck.map { " · plat \(ElementFormat.num($0.photoM2, 1)) m²" } ?? ""
            return "\(r.elements.count) element(en) op de luchtfoto\(flat). Daarna de gevels, één foto per gevel."
        }
        return "Eerst het dak op de PDOK-luchtfoto: dakvlakken, dakkapellen, goten en wat er op het dak staat. De helling van schuine vlakken komt uit de 3D BAG."
    }

    private func run() async {
        guard let key = ClaudeKey.load() else { return }
        running = true; error = nil
        defer { running = false }
        do {
            let (s, img, outline) = try await RoofScanner.scan(model: model, key: key)
            pending = Pending(scan: s, image: img, outline: outline)
        } catch { self.error = error.localizedDescription }
    }

    private func open(_ roof: FacadeScan) async {
        opening = true; defer { opening = false }
        guard let img = await RoofScanner.image(for: roof) else { error = "De luchtfoto kon niet worden opgehaald."; return }
        let outline = (model.footprint).flatMap { fp in roof.mercatorBox.map { b in RoofScanner.outline(fp, frame: FootprintMap.Frame(minX: b[0], minY: b[1], maxX: b[2], maxY: b[3])) } } ?? []
        pending = Pending(scan: roof, image: img, outline: outline)
    }
}

/// Resultaat van de dakscan: luchtfoto met de BAG-omtrek en de gevonden vlakken, wat je moet nalopen, de elementenlijst en de dakgebreken.
struct RoofResultView: View {
    let image: UIImage
    let outline: [[Double]]
    let onAccept: (FacadeScan) -> Void
    let onRetry: () -> Void
    @State private var scan: FacadeScan
    @State private var highlight: Int?
    @State private var editorSelect: Int?
    @State private var showEditor = false
    @State private var showDefects = false
    @Environment(\.dismiss) private var dismiss

    init(image: UIImage, scan: FacadeScan, outline: [[Double]], onAccept: @escaping (FacadeScan) -> Void, onRetry: @escaping () -> Void) {
        self.image = image; self.outline = outline; self.onAccept = onAccept; self.onRetry = onRetry
        _scan = State(initialValue: scan)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    ZStack {
                        FacadeOverlay(image: image, scan: scan, highlight: highlight)
                        GeometryReader { g in
                            let k = g.size.width / scan.photoWidth
                            Path { p in
                                let pts = outline.map { CGPoint(x: $0[0] * k, y: $0[1] * k) }
                                guard let f = pts.first else { return }
                                p.move(to: f); pts.dropFirst().forEach { p.addLine(to: $0) }; p.closeSubpath()
                            }
                            .stroke(Color.yellow, style: StrokeStyle(lineWidth: 1.5, dash: [6, 4]))
                        }
                        .allowsHitTesting(false)
                    }
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    Text("Geel gestippeld: de BAG-omtrek. Luchtfoto PDOK (meest recente vlucht); bomen kunnen delen van het dak verbergen.").font(.caption).foregroundStyle(DS.text2)
                    Button { editorSelect = nil; showEditor = true } label: { Label("Dakvlakken aanpassen", systemImage: "pencil.and.outline") }.buttonStyle(DSSecondaryButton())
                    review
                    notices
                    ElementListCard(groups: scan.elementGroups, title: "Dak: elementen en maten", onSelect: { m in highlight = m.elementId })
                    if let ds = scan.defects, !ds.isEmpty {
                        Button { showDefects = true } label: {
                            HStack {
                                Label("Dakgebreken", systemImage: "exclamationmark.triangle").foregroundStyle(DS.text)
                                Spacer()
                                Text("\(ds.count) gemarkeerd · \(ds.filter(\.isConfirmed).count) bevestigd").font(.subheadline).foregroundStyle(DS.text2)
                                Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(DS.text2)
                            }
                            .padding(.horizontal, 16).frame(minHeight: 54)
                        }
                        .buttonStyle(DSRowStyle()).dsCard(radius: 20)
                        Text("Gebreken op een luchtfoto zijn hints. Bevestig of wijs ze af; alleen bevestigde gebreken tellen mee in het advies voor een dakinspectie.").font(.footnote).foregroundStyle(DS.text2)
                    }
                    Button { onAccept(scan); dismiss() } label: { Label("Klopt, naar de gevels", systemImage: "checkmark") }.buttonStyle(DSPrimaryButton())
                        .accessibilityIdentifier("acceptRoof")
                    Button("Opnieuw scannen") { dismiss(); onRetry() }.buttonStyle(DSSecondaryButton())
                }
                .padding(.horizontal, DS.pad).padding(.bottom, 30)
            }
            .background(DS.canvas)
            .navigationTitle("Dak van boven").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Sluiten") { dismiss() } } }
            .fullScreenCover(isPresented: $showEditor) { FacadeEditorView(image: image, scan: scan, mode: .elements, selected: editorSelect) { scan = $0 } }
            .sheet(isPresented: $showDefects) { DefectListView(image: image, scan: scan) { scan = $0 } }
        }
    }

    @ViewBuilder private var review: some View {
        let items = scan.reviewItems
        let flagged = Set(items.map(\.elementId))
        let rest = scan.elements.filter { $0.confirmedByUser != true && $0.editedByUser != true && $0.addedByUser != true && !flagged.contains($0.id) }.count
        VStack(alignment: .leading, spacing: 8) {
            Text(items.isEmpty ? "Niets opvallends gevonden" : (items.count == 1 ? "1 ding om te checken" : "\(items.count) dingen om te checken")).font(.headline).foregroundStyle(items.isEmpty ? DS.ok : DS.text)
            ForEach(items) { it in
                if let e = scan.elements.first(where: { $0.id == it.elementId }) {
                    Button { editorSelect = e.id; showEditor = true } label: {
                        HStack {
                            Text("\(e.type.label) \(e.id)").font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                            Spacer()
                            Text(it.reasons.map(\.label).joined(separator: " · ")).font(.caption).foregroundStyle(Color.orange)
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            if rest > 0 {
                Button { _ = FacadeReview.confirmRest(&scan.elements, except: flagged) } label: {
                    Label(items.isEmpty ? "Alles klopt (\(rest) bevestigen)" : "De rest klopt (\(rest) bevestigen)", systemImage: "checkmark.circle")
                }
                .buttonStyle(DSSecondaryButton())
            }
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading).dsCard(radius: 20)
    }

    @ViewBuilder private var notices: some View {
        if scan.elements.contains(where: { $0.type == .dakvlak_schuin }) && scan.slopeFactor == nil {
            DSNotice(kind: .info, text: "Het oppervlak van de schuine dakvlakken is onbekend: de 3D BAG geeft voor dit gebouw geen bruikbaar schuin dakoppervlak. Van boven gezien is een schuin dak kleiner dan echt, dus we vullen niets in.")
        }
        if let c = scan.flatCheck, c.differs {
            DSNotice(kind: .warn, text: "Plat dak op de luchtfoto \(ElementFormat.num(c.photoM2, 1)) m², volgens de 3D BAG \(ElementFormat.num(c.bagM2, 1)) m². Dat verschilt meer dan 15%: controleer de platte vlakken en dakkapellen.")
        }
        if let n = scan.outsideRoof, n > 0 {
            Text("\(n) element(en) buiten de BAG-omtrek (bijvoorbeeld het dak van de buren) tellen niet mee.").font(.footnote).foregroundStyle(DS.text2)
        }
    }
}

/// Advies voor een dakinspectie met vaste regels, met de knop om het jaar in de planning over te nemen.
struct RoofAdviceCard: View {
    let model: ProjectModel
    let onAccept: (Int) -> Void

    var body: some View {
        if let a = model.roofAdvice, let el = model.elements.first(where: { $0.key == "dakinspectie" }) {
            let planned = Engine.firstYear(cyclus: el.cyclus, laatsteBeurt: el.laatsteBeurt, conditie: el.conditie, year: ProjectModel.year)
            VStack(alignment: .leading, spacing: 8) {
                Label("Dakinspectie: advies \(String(a.year))", systemImage: "binoculars").font(.headline).foregroundStyle(DS.text)
                ForEach(a.reasons, id: \.self) { r in Text("• " + r).font(.subheadline).foregroundStyle(DS.text2) }
                Text("Nu gepland: \(String(planned)).").font(.footnote).foregroundStyle(DS.text2)
                if planned != a.year {
                    Button { onAccept(a.year) } label: { Label("Overnemen in de planning (\(String(a.year)))", systemImage: "calendar.badge.plus") }.buttonStyle(DSSecondaryButton())
                        .accessibilityIdentifier("acceptRoofAdvice")
                }
                Text("Advies volgens vaste regels uit bevestigde dakgebreken en de leeftijd van de dakbedekking. Hints uit een luchtfoto; geen inspectie ter plaatse.").font(.caption).foregroundStyle(DS.text2)
            }
            .padding(16).frame(maxWidth: .infinity, alignment: .leading).dsCard(radius: 20)
        }
    }

    /// Zet de post Dakinspectie zo dat de eerstvolgende beurt in het geadviseerde jaar valt.
    static func apply(year: Int, to m: inout ProjectModel) {
        guard let i = m.elements.firstIndex(where: { $0.key == "dakinspectie" }) else { return }
        m.elements[i].laatsteBeurt = year - m.elements[i].cyclus
    }
}
