import MJOPEngine
import Security
import SwiftUI
import UIKit

/// De Claude-sleutel voor de gevelscan, alleen in de Keychain van dit toestel. (Voor een openbare app hoort de herkenning via de server te lopen.)
enum ClaudeKey {
    private static let service = "nl.mjop.live.claude"
    static func save(_ key: String?) {
        let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "default"]
        SecItemDelete(base as CFDictionary)
        guard let key, !key.isEmpty else { return }
        var add = base
        add[kSecValueData as String] = Data(key.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }
    static func load() -> String? {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "default",
                                kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }
}

/// Herkenning via de Messages API van Anthropic. Valt bij een 400-fout terug op een aanvraag zonder afgedwongen schema.
enum ClaudeVision {
    static func recognize(image: UIImage, key: String) async throws -> (recognition: FacadeRecognition, size: CGSize) {
        let (jpeg, size) = try prepare(image)
        let W = Int(size.width), H = Int(size.height)
        var lastError: Error = BackendError.message("De herkenning is mislukt.")
        for structured in [true, false] {
            var r = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
            r.httpMethod = "POST"
            r.timeoutInterval = 180
            r.setValue("application/json", forHTTPHeaderField: "content-type")
            r.setValue(key, forHTTPHeaderField: "x-api-key")
            r.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
            r.httpBody = try JSONSerialization.data(withJSONObject: FacadePhoto.requestBody(jpegBase64: jpeg.base64EncodedString(), width: W, height: H, structured: structured))
            let (data, resp): (Data, URLResponse)
            do { (data, resp) = try await URLSession.shared.data(for: r) }
            catch { throw BackendError.message("Geen verbinding met de AI-dienst. Controleer je internet.") }
            let status = (resp as? HTTPURLResponse)?.statusCode ?? 0
            if status == 200 {
                return (try FacadePhoto.parseRecognition(data, width: Double(W), height: Double(H)), size)
            }
            let detail = (((try? JSONSerialization.jsonObject(with: data)) as? [String: Any])?["error"] as? [String: Any])?["message"] as? String ?? "HTTP \(status)"
            switch status {
            case 401: throw BackendError.message("De Claude-sleutel is niet geldig.")
            case 403: throw BackendError.message("Deze Claude-sleutel mag dit niet doen: \(detail)")
            case 429: throw BackendError.message("Te veel aanvragen of tegoed op. Probeer het zo opnieuw.")
            case 500...: throw BackendError.message("De AI-dienst heeft een storing. Probeer het zo opnieuw.")
            case 400: lastError = BackendError.message("De aanvraag is geweigerd: \(detail)")
            default: throw BackendError.message("De aanvraag is geweigerd: \(detail)")
            }
        }
        throw lastError
    }

    /// Verkleint tot hooguit 2000 pixels aan de lange zijde, rechtop, als JPEG.
    static func prepare(_ image: UIImage) throws -> (Data, CGSize) {
        let s = image.size
        let k = min(1, FacadePhoto.maxEdge / max(s.width, s.height))
        let size = CGSize(width: (s.width * k).rounded(), height: (s.height * k).rounded())
        let fmt = UIGraphicsImageRendererFormat(); fmt.scale = 1
        let out = UIGraphicsImageRenderer(size: size, format: fmt).image { _ in image.draw(in: CGRect(origin: .zero, size: size)) }
        guard let data = out.jpegData(compressionQuality: 0.85) else { throw BackendError.message("De foto kon niet worden verwerkt.") }
        return (data, size)
    }
}

/// Rondje om het gebouw: kies een gevel, maak een foto, Claude herkent de elementen, de app rekent de hoeveelheden. Resultaat: voorstellen.
struct GevelscanFlow: View {
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @Environment(\.dismiss) private var dismiss
    var initialProject: Project?

    @State private var projectId: String?
    @State private var model: ProjectModel?
    @State private var error: String?
    @State private var side: FacadeSide?
    @State private var showCamera = false
    @State private var photo: UIImage?
    @State private var phase: Phase = .choose
    @State private var lastScan: FacadeScan?
    @State private var showKey = false
    @State private var captureMeta: CaptureMeta?
    @State private var editCorners = false
    @State private var selectedPlane: Int?
    @State private var widthFor: FacadePlane?
    @State private var widthText = ""

    enum Phase { case choose, working, result }

    private var project: Project? { store.projects.first { $0.id == (projectId ?? initialProject?.id) } ?? initialProject ?? store.projects.first }
    private var usableSides: [FacadeSide] { (model?.sides ?? []).filter { $0.lengthM >= 2 } }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if let error { DSNotice(kind: .warn, text: error) }
                    switch phase {
                    case .choose: chooser
                    case .working: working
                    case .result: result
                    }
                }
                .padding(.horizontal, DS.pad).padding(.bottom, 30)
            }
            .background(DS.canvas)
            .navigationTitle("Gevelscan").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Sluiten") { dismiss() } } }
            .task(id: project?.id) { await loadModel() }
            .fullScreenCover(isPresented: $showCamera) {
                if FacadeCameraSupport.available, let side {
                    FacadeCameraView(title: "Gevel op het \(side.facing)", step: "\((usableSides.firstIndex(of: side) ?? 0) + 1) van \(usableSides.count)") { img, meta in
                        captureMeta = meta
                        photo = img
                    }
                } else {
                    CameraPicker(image: $photo).ignoresSafeArea()
                }
            }
            .onChange(of: photo) { p in if p != nil { Task { await recognize() } } }
            .sheet(isPresented: $showKey) { ClaudeKeySheet() }
        }
    }

    // MARK: kiezen

    @ViewBuilder private var chooser: some View {
        if let p = project {
            VStack(alignment: .leading, spacing: 4) {
                Text("Rondje om het gebouw").font(.system(size: 28, weight: .bold)).foregroundStyle(DS.text)
                Text("\(p.naam) · één foto per gevel, recht van voren met de hele gevel in beeld.").foregroundStyle(DS.text2)
            }
            if store.projects.count > 1 {
                Menu { ForEach(store.projects) { q in Button(q.naam) { projectId = q.id } } } label: { Label("Ander project", systemImage: "chevron.up.chevron.down") }
            }
            let done = Set(model?.gevels.map(\.sideId) ?? [])
            if !usableSides.isEmpty {
                ProgressView(value: Double(done.intersection(usableSides.map(\.id)).count), total: Double(usableSides.count)).tint(DS.ok)
                Text("\(done.intersection(usableSides.map(\.id)).count) van \(usableSides.count) gevels klaar").font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                VStack(spacing: 0) {
                    ForEach(usableSides) { s in
                        Button { side = s; startCamera() } label: {
                            HStack(spacing: 12) {
                                ZStack {
                                    Circle().fill(done.contains(s.id) ? DS.ok : DS.accentSoft).frame(width: 30, height: 30)
                                    if done.contains(s.id) { Image(systemName: "checkmark").font(.footnote.weight(.bold)).foregroundStyle(.white) }
                                    else { Text("\(s.id)").font(.footnote.weight(.bold)).foregroundStyle(DS.accent) }
                                }
                                VStack(alignment: .leading, spacing: 1) {
                                    Text("Gevel op het \(s.facing)").font(.headline).foregroundStyle(DS.text)
                                    Text(String(format: "%.1f m breed volgens de BAG", s.lengthM).replacingOccurrences(of: ".", with: ",") + (done.contains(s.id) ? " · gescand" : ""))
                                        .font(.caption).foregroundStyle(DS.text2)
                                }
                                Spacer()
                                Image(systemName: "camera.fill").foregroundStyle(DS.accent)
                            }
                            .padding(.horizontal, 14).frame(minHeight: 60)
                        }
                        .buttonStyle(DSRowStyle())
                        .accessibilityIdentifier("side-\(s.id)")
                        if s.id != usableSides.last?.id { Divider().padding(.leading, 56) }
                    }
                }
                .dsCard(radius: 20)
            } else if model != nil {
                DSNotice(kind: .info, text: "Voor dit project zijn geen gevelzijden uit de BAG bekend. Maak het project opnieuw aan via een adres om de gevels te kunnen scannen.")
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.top, 30)
            }
            if ClaudeKey.load() == nil && !account.demo {
                DSNotice(kind: .info, text: "Voor de herkenning is een Claude-sleutel nodig (in deze testfase je eigen sleutel).")
                Button("Claude-sleutel instellen") { showKey = true }.buttonStyle(DSSecondaryButton())
            }
            Text("Claude herkent alleen wat er op de foto staat. De maten rekent de app uit met de gevelbreedte uit de BAG; de uitkomst is een voorstel.")
                .font(.footnote).foregroundStyle(DS.text2)
        } else {
            DSNotice(kind: .info, text: "Maak eerst een project bij Projecten; daarna kun je de gevels scannen.")
        }
    }

    private func startCamera() {
        error = nil
        if ClaudeKey.load() == nil && !account.demo { showKey = true; return }
        photo = nil
        captureMeta = nil
        showCamera = true
    }

    // MARK: verwerken

    private var working: some View {
        VStack(spacing: 18) {
            if let photo { Image(uiImage: photo).resizable().scaledToFit().clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous)).frame(maxHeight: 260) }
            VStack(alignment: .leading, spacing: 10) {
                step(true, "Foto ontvangen")
                step(false, "Elementen herkennen met Claude")
                step(nil, "Hoeveelheden uitrekenen met vaste regels")
            }
            .padding(16).frame(maxWidth: .infinity, alignment: .leading).dsCard()
            Text("Dit duurt meestal een halve tot een hele minuut.").font(.footnote).foregroundStyle(DS.text2)
        }
        .padding(.top, 8)
    }

    private func step(_ state: Bool?, _ text: String) -> some View {
        HStack(spacing: 12) {
            if state == true { Image(systemName: "checkmark.circle.fill").foregroundStyle(DS.ok) }
            else if state == false { ProgressView() }
            else { Image(systemName: "circle").foregroundStyle(DS.text2) }
            Text(text).foregroundStyle(state == nil ? DS.text2 : DS.text)
        }
    }

    private func recognize() async {
        guard let photo, let side else { return }
        phase = .working
        do {
            let r: (recognition: FacadeRecognition, size: CGSize)
            if account.demo { r = demoRecognition(photo) }
            else { r = try await ClaudeVision.recognize(image: photo, key: ClaudeKey.load() ?? "") }
            let ref = FacadePhoto.defaultReference(r.recognition.elements) ?? (left: 0, right: Double(r.size.width))
            var scan = FacadeScan(sideId: side.id, facing: side.facing, widthM: side.lengthM, photoWidth: Double(r.size.width), photoHeight: Double(r.size.height),
                                  referenceLeftX: ref.left, referenceRightX: ref.right, elements: r.recognition.elements, skipped: r.recognition.skipped,
                                  model: FacadePhoto.model, promptVersion: FacadePhoto.promptVersion, scannedAt: Date(),
                                  lens: captureMeta?.lens, rollDeg: captureMeta?.rollDeg, pitchDeg: captureMeta?.pitchDeg, levelAtCapture: captureMeta?.level)
            scan.focal35mm = captureMeta?.focal35mm
            scan.planes = r.recognition.planes
            scan.defects = r.recognition.defects
            editCorners = false
            selectedPlane = nil
            lastScan = scan
            phase = .result
        } catch {
            self.error = error.localizedDescription
            phase = .choose
        }
    }

    private func demoRecognition(_ img: UIImage) -> (recognition: FacadeRecognition, size: CGSize) {
        let w = Double(img.size.width), h = Double(img.size.height)
        let els = [
            FacadePhotoElement(id: 1, type: .metselwerk, points: [[0, h * 0.1], [w, h * 0.1], [w, h], [0, h]], material: "baksteen", confidence: "high", note: nil),
            FacadePhotoElement(id: 2, type: .kozijn_raam, points: [[w * 0.1, h * 0.2], [w * 0.35, h * 0.2], [w * 0.35, h * 0.5], [w * 0.1, h * 0.5]], material: "hout", confidence: "high", note: nil),
            FacadePhotoElement(id: 3, type: .kozijn_deur, points: [[w * 0.6, h * 0.55], [w * 0.75, h * 0.55], [w * 0.75, h], [w * 0.6, h]], material: "hout", confidence: "medium", note: nil),
        ]
        let plane = FacadePlane(id: 1, kind: .hoofdgevel, corners: [[w * 0.02, h * 0.1], [w * 0.98, h * 0.12], [w * 0.97, h * 0.98], [w * 0.03, h]])
        let uitbouw = FacadePlane(id: 2, kind: .uitbouw, corners: [[w * 0.52, h * 0.5], [w * 0.88, h * 0.5], [w * 0.88, h], [w * 0.52, h]])
        return (FacadeRecognition(elements: els.map { var e = $0; e.plane = $0.type == .kozijn_deur ? 2 : 1; return e }, skipped: 0, planes: [plane, uitbouw], defects: []), img.size)
    }

    // MARK: resultaat

    @ViewBuilder private var result: some View {
        if let scan = lastScan, let photo {
            Text("Gevel op het \(scan.facing)").font(.system(size: 26, weight: .bold)).foregroundStyle(DS.text)
            let activePlane = selectedPlane ?? scan.mainPlane?.id
            FacadeOverlay(image: photo, scan: scan, editCorners: editCorners, activePlane: activePlane) { corners in
                guard var s = lastScan, let i = s.planes?.firstIndex(where: { $0.id == activePlane }) else { return }
                if s.planes![i].originalCorners == nil { s.planes![i].originalCorners = s.planes![i].corners }
                s.planes![i].corners = corners
                s.planes![i].editedByUser = true
                lastScan = s
            }
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            if scan.mainPlane != nil {
                Button { withAnimation(.dsSpring) { editCorners.toggle() } } label: {
                    Label(editCorners ? "Klaar met hoeken" : "Hoeken aanpassen", systemImage: editCorners ? "checkmark" : "perspective")
                }
                .buttonStyle(DSSecondaryButton())
                .accessibilityIdentifier("editCorners")
                if editCorners {
                    Text("Sleep de vier punten naar de hoeken van het gekozen vlak (zonder dak). Kies hieronder een ander vlak om dat aan te passen. De maten rekenen meteen mee.").font(.footnote).foregroundStyle(DS.text2)
                }
                if (scan.planes ?? []).count > 1 { planeList(scan, active: activePlane) }
            }
            let s = scan.summary
            VStack(spacing: 0) {
                resultRow("square.grid.3x3", "Metselwerk", "netto, openingen afgetrokken", s.metselwerkNetM2.map { m2($0) } ?? "maat onbekend")
                Divider().padding(.leading, 60)
                resultRow("window.casement", "Raamkozijnen", "herkend door Claude", "\(s.raamkozijnen) st")
                Divider().padding(.leading, 60)
                resultRow("door.left.hand.closed", "Deurkozijnen", "herkend door Claude", "\(s.deurkozijnen) st")
                Divider().padding(.leading, 60)
                resultRow("drop", "Hemelwaterafvoer", "lengte op de foto", s.hwaM1.map { m1($0) } ?? "–")
            }
            .dsCard(radius: 20)
            if scan.skipped > 0 { Text("\(scan.skipped) element(en) niet bruikbaar en overgeslagen.").font(.footnote).foregroundStyle(DS.text2) }
            if let r = scan.rectified {
                let open = scan.unmeasuredPlanes
                if !open.isEmpty {
                    let n = scan.elements.filter { e in open.contains { $0.id == e.plane } }.count
                    DSNotice(kind: .info, text: "\(n) element(en) op \(open.map { $0.kind.label.lowercased() }.joined(separator: " en ")) tellen nog niet mee: dat vlak heeft nog geen eigen maat.")
                }
                Text("Rechtgetrokken: gevel \(m1(r.widthM)) breed (BAG) en \(m1(r.heightM)) hoog (afgeleid uit de foto, \(focalText(r.focalSource))). De BAG-omtrek kan enkele decimeters afwijken; dit is een voorstel.")
                    .font(.footnote).foregroundStyle(DS.text2)
            } else {
                Text("Maat: gevelbreedte \(m1(scan.widthM)) uit de BAG, gelegd op de buitenranden van het metselwerk, zonder perspectiefcorrectie (de hoeken van de gevel zijn niet gevonden). Dit is een voorstel.")
                    .font(.footnote).foregroundStyle(DS.text2)
            }
            Button { Task { await accept(scan) } } label: { Label("Overnemen in het plan", systemImage: "checkmark") }
                .buttonStyle(DSPrimaryButton())
                .accessibilityIdentifier("acceptScan")
            Button("Opnieuw") { phase = .choose; startCamera() }.buttonStyle(DSSecondaryButton())
        }
    }

    private func resultRow(_ icon: String, _ title: String, _ sub: String, _ value: String) -> some View {
        HStack(spacing: 12) {
            DSIcon(systemName: icon)
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                Text(sub).font(.caption).foregroundStyle(DS.text2)
            }
            Spacer()
            Text(value).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
        }
        .padding(.horizontal, 14).frame(minHeight: 58)
    }

    private func planeList(_ scan: FacadeScan, active: Int?) -> some View {
        VStack(spacing: 0) {
            ForEach(Array((scan.planes ?? []).enumerated()), id: \.element.id) { idx, p in
                let w = scan.width(of: p)
                HStack(spacing: 12) {
                    Button { selectedPlane = p.id } label: {
                        HStack(spacing: 12) {
                            Circle().fill(FacadeOverlay.planeColor(idx)).frame(width: 14, height: 14)
                                .overlay(Circle().stroke(DS.text, lineWidth: p.id == active ? 2 : 0).padding(-3))
                            VStack(alignment: .leading, spacing: 1) {
                                Text(p.kind.label).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                                Text(w.map { "\(m1($0.m)) breed · \($0.source.label)" } ?? "nog geen maat · telt niet mee").font(.caption).foregroundStyle(w == nil ? Color.orange : DS.text2)
                            }
                            Spacer(minLength: 0)
                        }
                    }
                    .buttonStyle(.plain)
                    if p.id != scan.mainPlane?.id {
                        Menu {
                            Button { widthText = p.widthM.map { String(format: "%.2f", $0).replacingOccurrences(of: ".", with: ",") } ?? ""; widthFor = p } label: {
                                Label("Breedte invoeren", systemImage: "ruler")
                            }
                            if let dw = scan.doorWidth(p) {
                                Button { setWidth(p.id, dw, .deurAanname) } label: { Label("Deur als maat (2,1 m, aanname): \(m1(dw))", systemImage: "door.left.hand.closed") }
                            }
                            if w != nil { Button(role: .destructive) { setWidth(p.id, nil, nil) } label: { Label("Maat weghalen", systemImage: "xmark") } }
                        } label: {
                            Text(w == nil ? "Maat geven" : "Wijzig").font(.subheadline.weight(.semibold)).foregroundStyle(DS.accent)
                                .padding(.horizontal, 12).padding(.vertical, 7).background(DS.accentSoft, in: Capsule())
                        }
                        .accessibilityIdentifier("planeWidth-\(p.id)")
                    }
                }
                .padding(.horizontal, 14).frame(minHeight: 58)
                if p.id != scan.planes?.last?.id { Divider().padding(.leading, 40) }
            }
        }
        .dsCard(radius: 20)
        .alert("Breedte van het vlak", isPresented: Binding(get: { widthFor != nil }, set: { if !$0 { widthFor = nil } })) {
            TextField("bijv. 3,60", text: $widthText).keyboardType(.decimalPad)
            Button("Opslaan") {
                if let p = widthFor, let v = Double(widthText.replacingOccurrences(of: ",", with: ".")), v > 0.3, v < 200 { setWidth(p.id, v, .gebruiker) }
                widthFor = nil
            }
            Button("Annuleer", role: .cancel) { widthFor = nil }
        } message: {
            Text("In meters, gemeten langs de bovenrand van het vlak (bijvoorbeeld met een duimstok of uit een tekening).")
        }
    }

    private func setWidth(_ planeId: Int, _ w: Double?, _ source: PlaneWidthSource?) {
        guard var s = lastScan, let i = s.planes?.firstIndex(where: { $0.id == planeId }) else { return }
        s.planes![i].widthM = w
        s.planes![i].widthSource = source
        lastScan = s
    }

    private func focalText(_ s: FacadePerspective.FocalSource) -> String {
        switch s {
        case .exif: return "lens uit de foto"
        case .geschat: return "lens geschat uit de hoeken"
        case .aangenomen: return "foto vrijwel recht van voren"
        }
    }

    private func m2(_ v: Double) -> String { String(format: "%.1f m²", v).replacingOccurrences(of: ".", with: ",") }
    private func m1(_ v: Double) -> String { String(format: "%.1f m", v).replacingOccurrences(of: ".", with: ",") }

    /// Bewaart de scan en zet de opgetelde gevelmaten als voorstel-overgenomen hoeveelheid in het plan (bron: gevelfoto).
    private func accept(_ scan: FacadeScan) async {
        guard var m = model, let p = project else { return }
        m.gevels.removeAll { $0.sideId == scan.sideId }
        m.gevels.append(scan)
        let sums = m.gevels.map(\.summary)
        if !sums.contains(where: { $0.metselwerkNetM2 == nil }) {
            let total = sums.compactMap(\.metselwerkNetM2).reduce(0, +)
            if let i = m.elements.firstIndex(where: { $0.key == "gevel-metselwerk" }), total > 0 {
                m.elements[i].quantity = Quantity(value: Decimal(string: String(format: "%.2f", total)), unit: "m2", source: .gevelfoto,
                                                  basis: "Netto metselwerk van \(m.gevels.count) gescande gevel(s), gemeten op gevelfoto's.")
            }
        }
        if let i = m.elements.firstIndex(where: { $0.key == "kozijnen-onderhoud" }), var rows = m.elements[i].kozijnen, rows.count >= 3 {
            let ramen = m.gevels.reduce(0) { $0 + $1.summary.raamkozijnen }, deuren = m.gevels.reduce(0) { $0 + $1.summary.deurkozijnen }
            rows[0].aantal = Quantity(value: Decimal(ramen), unit: "st", source: .gevelfoto, basis: "Geteld op \(m.gevels.count) gevelfoto('s).")
            rows[2].aantal = Quantity(value: Decimal(deuren), unit: "st", source: .gevelfoto, basis: "Geteld op \(m.gevels.count) gevelfoto('s).")
            m.elements[i].kozijnen = rows
        }
        model = m
        do { try await store.saveModel(m, for: p, account: account); await store.refresh(account); phase = .choose; photo = nil }
        catch { self.error = error.localizedDescription }
    }

    private func loadModel() async {
        guard let p = project else { return }
        do { model = try await store.loadModel(p, account: account) } catch { self.error = error.localizedDescription }
    }
}

/// De foto met de herkende elementen erop getekend.
struct FacadeOverlay: View {
    let image: UIImage
    let scan: FacadeScan
    var editCorners = false
    var activePlane: Int? = nil
    var onCorners: (([[Double]]) -> Void)? = nil

    static func planeColor(_ i: Int) -> Color { [Color.yellow, Color(hex: 0xFF5FD2), Color(hex: 0x22D3EE), Color(hex: 0xA3E635)][i % 4] }

    var body: some View {
        Image(uiImage: image).resizable().scaledToFit()
            .overlay {
                GeometryReader { g in
                    let k = g.size.width / scan.photoWidth
                    ForEach(scan.elements) { e in
                        Path { path in
                            let pts = e.points.map { CGPoint(x: $0[0] * k, y: $0[1] * k) }
                            guard let f = pts.first else { return }
                            path.move(to: f)
                            pts.dropFirst().forEach { path.addLine(to: $0) }
                            if e.type.kind != .line { path.closeSubpath() }
                        }
                        .stroke(color(e.type), lineWidth: e.type.kind == .poly ? 2 : 2.5)
                        .allowsHitTesting(false)
                    }
                    ForEach(Array((scan.planes ?? []).enumerated()), id: \.element.id) { idx, pl in
                        Path { path in
                            let pts = pl.corners.map { CGPoint(x: $0[0] * k, y: $0[1] * k) }
                            path.move(to: pts[0]); pts.dropFirst().forEach { path.addLine(to: $0) }; path.closeSubpath()
                        }
                        .stroke(FacadeOverlay.planeColor(idx), style: StrokeStyle(lineWidth: editCorners && pl.id == active ? 2.5 : 1.5, dash: editCorners && pl.id == active ? [] : [6, 5]))
                        .allowsHitTesting(false)
                    }
                    if let plane = scan.planes?.first(where: { $0.id == active }) {
                        if editCorners {
                            ForEach(0..<4, id: \.self) { i in
                                let c = plane.corners[i]
                                Circle().fill(FacadeOverlay.planeColor(activeIndex)).frame(width: 22, height: 22)
                                    .overlay(Circle().stroke(.black.opacity(0.4), lineWidth: 1))
                                    .frame(width: 44, height: 44).contentShape(Rectangle())
                                    .position(x: min(max(c[0] * k, 0), g.size.width), y: min(max(c[1] * k, 0), g.size.height))
                                    .gesture(DragGesture(minimumDistance: 0, coordinateSpace: .named("facade")).onChanged { v in
                                        var cs = plane.corners
                                        cs[i] = [min(max(v.location.x, 0), g.size.width) / k, min(max(v.location.y, 0), g.size.height) / k]
                                        if FacadePerspective.isConvex(cs) { onCorners?(cs) }
                                    })
                                    .accessibilityLabel(["Hoek linksboven", "Hoek rechtsboven", "Hoek rechtsonder", "Hoek linksonder"][i])
                            }
                        }
                    }
                }
            }
            .coordinateSpace(name: "facade")
            .accessibilityLabel("Foto van de gevel met \(scan.elements.count) herkende elementen")
    }

    private var active: Int? { activePlane ?? scan.mainPlane?.id }
    private var activeIndex: Int { scan.planes?.firstIndex { $0.id == active } ?? 0 }

    private func color(_ t: FacadeElementType) -> Color {
        switch t {
        case .kozijn_raam: return Color(hex: 0x2F4BFF)
        case .kozijn_deur: return Color(hex: 0xD1242F)
        case .metselwerk, .stucwerk, .gevelbekleding: return Color(hex: 0xF59E0B)
        case .hwa, .dakgoot: return Color(hex: 0x0E9384)
        default: return .white
        }
    }
}

/// Camera (of fotobibliotheek in de simulator).
struct CameraPicker: UIViewControllerRepresentable {
    @Binding var image: UIImage?
    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let p = UIImagePickerController()
        p.sourceType = UIImagePickerController.isSourceTypeAvailable(.camera) ? .camera : .photoLibrary
        p.delegate = context.coordinator
        return p
    }
    func updateUIViewController(_ vc: UIImagePickerController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: CameraPicker
        init(_ p: CameraPicker) { parent = p }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            parent.image = info[.originalImage] as? UIImage
            parent.dismiss()
        }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { parent.dismiss() }
    }
}

/// Claude-sleutel invoeren (alleen op dit toestel bewaard).
struct ClaudeKeySheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var key = ClaudeKey.load() ?? ""

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 14) {
                Text("Claude-sleutel").font(.title2.weight(.bold))
                Text("Nodig om elementen op een gevelfoto te herkennen. De sleutel blijft in de Keychain van deze iPhone en gaat alleen naar Anthropic.").foregroundStyle(DS.text2)
                DSField(icon: "key") { SecureField("sk-ant-…", text: $key).textInputAutocapitalization(.never).autocorrectionDisabled() }
                Button("Opslaan") { ClaudeKey.save(key.trimmingCharacters(in: .whitespacesAndNewlines)); dismiss() }.buttonStyle(DSPrimaryButton()).disabled(key.count < 20)
                if ClaudeKey.load() != nil { Button("Sleutel verwijderen", role: .destructive) { ClaudeKey.save(nil); dismiss() }.frame(maxWidth: .infinity) }
                Spacer()
            }
            .padding(20)
            .background(DS.canvas.ignoresSafeArea())
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annuleer") { dismiss() } } }
        }
        .presentationDetents([.medium])
    }
}
