import MJOPEngine
import PDFKit
import SwiftUI
import UniformTypeIdentifiers
import UIKit
import VisionKit

/// Documenten van een project: toevoegen uit Bestanden of Mail (pdf of foto) of papier scannen; Claude leest ze en maakt voorstellen.
struct DocumentsSection: View {
    let project: Project
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @State private var model: ProjectModel?
    @State private var error: String?
    @State private var showImporter = false
    @State private var showScanner = false
    @State private var working: String?
    @State private var reviewing: ProjectDocument?
    @State private var showKey = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Button { start { showImporter = true } } label: { Label("Document", systemImage: "plus") }
                    .buttonStyle(DSPrimaryButton())
                    .accessibilityIdentifier("addDocument")
                Button { start { showScanner = true } } label: { Label("Papier scannen", systemImage: "doc.viewfinder") }
                    .buttonStyle(DSSecondaryButton())
                    .disabled(!VNDocumentCameraViewController.isSupported)
            }
            if let error { DSNotice(kind: .warn, text: error) }
            if let working {
                HStack(spacing: 12) {
                    ProgressView()
                    VStack(alignment: .leading, spacing: 2) {
                        Text(working).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                        Text("Claude leest het document; dit kan een minuut duren.").font(.caption).foregroundStyle(DS.text2)
                    }
                }
                .padding(14).frame(maxWidth: .infinity, alignment: .leading).dsCard(radius: 18)
            }
            if let docs = model?.documents, !docs.isEmpty {
                VStack(spacing: 0) {
                    ForEach(docs.sorted { $0.addedAt > $1.addedAt }) { d in
                        Button { reviewing = d } label: {
                            HStack(spacing: 12) {
                                DSIcon(systemName: icon(d.kind))
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(d.naam).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text).lineLimit(1)
                                    Text("\(d.kind.label)\(d.pages.map { " · \($0) pagina's" } ?? "") · \(DSFormat.relative(d.addedAt))").font(.caption).foregroundStyle(DS.text2)
                                }
                                Spacer(minLength: 6)
                                if d.openCount > 0 { DSChip(text: "\(d.openCount) voorstel\(d.openCount == 1 ? "" : "len")", fg: DS.warn, bg: DS.warnSoft) }
                                else { DSChip(text: "Verwerkt", fg: DS.ok, bg: DS.okSoft) }
                            }
                            .padding(.horizontal, 14).frame(minHeight: 62)
                        }
                        .buttonStyle(DSRowStyle())
                        if d.id != docs.sorted(by: { $0.addedAt > $1.addedAt }).last?.id { Divider().padding(.leading, 60) }
                    }
                }
                .dsCard(radius: 20)
            } else if model != nil && working == nil {
                Text("Voeg een oud MJOP, offertes, facturen of inspectierapporten toe. Claude zet wat erin staat klaar als voorstel, met de pagina als bron; jij beslist wat je overneemt.")
                    .font(.subheadline).foregroundStyle(DS.text2)
            }
            Text("Oude bedragen uit een oud MJOP worden nooit als actuele prijs gebruikt. Een offerte geeft een actuele prijs voor die post.")
                .font(.caption).foregroundStyle(DS.text2)
        }
        .task(id: project.id) { do { model = try await store.loadModel(project, account: account) } catch { self.error = error.localizedDescription } }
        .fileImporter(isPresented: $showImporter, allowedContentTypes: [.pdf, .image], allowsMultipleSelection: false) { r in
            if case .success(let urls) = r, let u = urls.first { Task { await process(file: u) } }
        }
        .fullScreenCover(isPresented: $showScanner) {
            DocumentScanner { images in Task { await process(images: images, naam: "Gescand document") } }.ignoresSafeArea()
        }
        .sheet(item: $reviewing) { d in
            DocumentReviewView(document: d, model: model) { updated in
                guard let updated else { return }
                model = updated
                Task { try? await store.saveModel(updated, for: project, account: account); await store.refresh(account) }
            }
        }
        .sheet(isPresented: $showKey) { ClaudeKeySheet() }
    }

    private func icon(_ k: DocumentKind) -> String {
        switch k { case .oudMJOP: return "doc.text"; case .offerte: return "eurosign"; case .factuur: return "checkmark.seal"; case .inspectie: return "magnifyingglass"; case .overig: return "doc" }
    }

    private func start(_ open: () -> Void) {
        error = nil
        if ClaudeKey.load() == nil && !account.demo { showKey = true; return }
        open()
    }

    private func process(file url: URL) async {
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else { error = "Het bestand kon niet worden gelezen."; return }
        if url.pathExtension.lowercased() == "pdf" {
            let pages = PDFDocument(data: data)?.pageCount
            if data.count > 30_000_000 { error = "Dit pdf-bestand is te groot (meer dan 30 MB)."; return }
            await run(naam: url.deletingPathExtension().lastPathComponent, pages: pages, pdf: data.base64EncodedString(), images: [])
        } else if let img = UIImage(data: data), let prepared = try? ClaudeVision.prepare(img) {
            await run(naam: url.deletingPathExtension().lastPathComponent, pages: 1, pdf: nil, images: [prepared.0.base64EncodedString()])
        } else { error = "Dit bestand wordt niet herkend als pdf of foto." }
    }

    private func process(images: [UIImage], naam: String) async {
        let jpegs = images.prefix(20).compactMap { try? ClaudeVision.prepare($0).0.base64EncodedString() }
        guard !jpegs.isEmpty else { return }
        await run(naam: naam, pages: jpegs.count, pdf: nil, images: Array(jpegs))
    }

    private func run(naam: String, pages: Int?, pdf: String?, images: [String]) async {
        guard var m = model else { return }
        working = "“\(naam)” wordt gelezen"
        defer { working = nil }
        do {
            let r: (kind: DocumentKind, proposals: [DocumentProposal], skipped: Int)
            if account.demo {
                r = (.offerte, [DocumentProposal(id: "p1", elementKey: "schilderwerk-buiten", documentNaam: "Schilderwerk buitenkozijnen", field: .prijs, value: 3875.5,
                                                 unit: "eur", jaar: ProjectModel.year, page: 1, quote: "Totaal schilderwerk € 3.875,50 excl. btw", confidence: "high")], 0)
            } else {
                r = try await ClaudeDocuments.read(pdfBase64: pdf, images: images, key: ClaudeKey.load() ?? "")
            }
            let doc = ProjectDocument(id: UUID().uuidString, naam: naam, kind: r.kind, pages: pages, addedAt: Date(), proposals: r.proposals, skipped: r.skipped,
                                      model: DocumentExtraction.model, promptVersion: DocumentExtraction.promptVersion)
            m.documents.append(doc)
            model = m
            try await store.saveModel(m, for: project, account: account)
            reviewing = doc
        } catch { self.error = error.localizedDescription }
    }
}

/// Aanroep van de Messages API voor een document.
enum ClaudeDocuments {
    static func read(pdfBase64: String?, images: [String], key: String) async throws -> (kind: DocumentKind, proposals: [DocumentProposal], skipped: Int) {
        var r = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        r.httpMethod = "POST"
        r.timeoutInterval = 300
        r.setValue("application/json", forHTTPHeaderField: "content-type")
        r.setValue(key, forHTTPHeaderField: "x-api-key")
        r.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        r.httpBody = try JSONSerialization.data(withJSONObject: DocumentExtraction.requestBody(pdfBase64: pdfBase64, imagesJPEGBase64: images, kind: nil))
        let (data, resp): (Data, URLResponse)
        do { (data, resp) = try await URLSession.shared.data(for: r) } catch { throw BackendError.message("Geen verbinding met de AI-dienst. Controleer je internet.") }
        let status = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
            let detail = (((try? JSONSerialization.jsonObject(with: data)) as? [String: Any])?["error"] as? [String: Any])?["message"] as? String ?? "HTTP \(status)"
            switch status {
            case 401: throw BackendError.message("De Claude-sleutel is niet geldig.")
            case 429: throw BackendError.message("Te veel aanvragen of tegoed op. Probeer het zo opnieuw.")
            default: throw BackendError.message("Het document kon niet worden gelezen: \(detail)")
            }
        }
        return try DocumentExtraction.parse(data, fallbackKind: .overig)
    }
}

/// Voorstellen uit één document nalopen: huidige waarde naast de documentwaarde, met bron. Overnemen, aanpassen of afwijzen.
struct DocumentReviewView: View {
    @State var document: ProjectDocument
    @State var model: ProjectModel?
    let onClose: (ProjectModel?) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var editing: DocumentProposal?
    @State private var editText = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("\(document.openCount) VOORSTELLEN OPEN · \(document.kind.label.uppercased())").font(.caption.weight(.bold)).foregroundStyle(DS.accent)
                    Text("Wat staat erin?").font(.system(size: 28, weight: .bold)).foregroundStyle(DS.text)
                    if document.kind == .oudMJOP {
                        Text("Oude bedragen worden niet als actuele prijs gebruikt; hoeveelheden, jaren en cycli wel als voorstel.").font(.subheadline).foregroundStyle(DS.text2)
                    }
                    if document.proposals.isEmpty {
                        DSNotice(kind: .info, text: "Er is niets gevonden dat in het plan past.")
                    }
                    ForEach(document.proposals) { p in card(p) }
                    if document.skipped > 0 { Text("\(document.skipped) gevonden regel(s) waren niet bruikbaar en zijn overgeslagen.").font(.caption).foregroundStyle(DS.text2) }
                }
                .padding(.horizontal, DS.pad).padding(.bottom, 30)
            }
            .background(DS.canvas)
            .navigationTitle(document.naam).navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Klaar") { onClose(model); dismiss() } } }
            .alert("Waarde aanpassen", isPresented: Binding(get: { editing != nil }, set: { if !$0 { editing = nil } })) {
                TextField("Waarde", text: $editText).keyboardType(.decimalPad)
                Button("Overnemen") {
                    if var p = editing, let v = Double(editText.replacingOccurrences(of: ",", with: ".")) { p.value = v; accept(p) }
                    editing = nil
                }
                Button("Annuleren", role: .cancel) { editing = nil }
            }
        }
    }

    private func label(_ f: ProposalField) -> String {
        switch f { case .hoeveelheid: return "hoeveelheid"; case .laatstUitgevoerd: return "laatst uitgevoerd"; case .cyclus: return "cyclus"; case .prijs: return "prijs (offerte)"; case .conditie: return "staat" }
    }

    private func value(_ p: DocumentProposal) -> String {
        switch p.field {
        case .prijs: return DSFormat.euros(Int((p.value).rounded()))
        case .laatstUitgevoerd: return String(Int(p.value))
        case .cyclus: return "\(Int(p.value)) jaar"
        case .conditie: return String(Int(p.value))
        case .hoeveelheid: return String(format: "%g", p.value).replacingOccurrences(of: ".", with: ",") + (p.unit.map { " \($0)" } ?? "")
        }
    }

    @ViewBuilder private func card(_ p: DocumentProposal) -> some View {
        let el = model?.elements.first { $0.key == p.elementKey }
        VStack(alignment: .leading, spacing: 8) {
            Text("\(el?.naam ?? p.documentNaam) · \(label(p.field))").font(.headline).foregroundStyle(DS.text)
            Text("\(p.page.map { "Pagina \($0) · " } ?? "")“\(p.quote)”").font(.caption).foregroundStyle(DS.text2)
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Nu in je plan").font(.caption2).foregroundStyle(DS.text2)
                    Text(model.map { DocumentExtraction.currentValue(p, in: $0.elements) } ?? "–").font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                }
                .padding(10).frame(maxWidth: .infinity, alignment: .leading).background(DS.surface2, in: RoundedRectangle(cornerRadius: 12))
                VStack(alignment: .leading, spacing: 2) {
                    Text("Uit het document").font(.caption2).foregroundStyle(DS.onAccentSoft)
                    Text(value(p)).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                }
                .padding(10).frame(maxWidth: .infinity, alignment: .leading).background(DS.accentSoft, in: RoundedRectangle(cornerRadius: 12))
            }
            switch p.status {
            case .open:
                if el == nil {
                    Text("Niet gekoppeld aan een post in je plan; daarom niet over te nemen.").font(.caption).foregroundStyle(DS.warn)
                    Button("Afwijzen") { set(p, .afgewezen) }.font(.subheadline.weight(.semibold))
                } else {
                    HStack(spacing: 8) {
                        Button("Overnemen") { accept(p) }.buttonStyle(.borderedProminent).tint(DS.accent)
                        Button("Aanpassen") { editText = String(format: "%g", p.value); editing = p }.buttonStyle(.bordered)
                        Button("Afwijzen") { set(p, .afgewezen) }.buttonStyle(.bordered).tint(.secondary)
                    }
                    .font(.subheadline.weight(.semibold))
                }
            case .overgenomen: Label("Overgenomen", systemImage: "checkmark").font(.subheadline.weight(.semibold)).foregroundStyle(DS.ok)
            case .afgewezen: Text("Afgewezen").font(.subheadline).foregroundStyle(DS.text2)
            }
        }
        .padding(16).dsCard(radius: 20)
    }

    private func accept(_ p: DocumentProposal) {
        guard var m = model else { return }
        guard DocumentExtraction.apply(p, documentNaam: document.naam, to: &m.elements) else { return }
        var q = p; q.status = .overgenomen
        replace(q, in: &m)
    }

    private func set(_ p: DocumentProposal, _ s: ProposalStatus) {
        guard var m = model else { return }
        var q = p; q.status = s
        replace(q, in: &m)
    }

    private func replace(_ p: DocumentProposal, in m: inout ProjectModel) {
        if let i = document.proposals.firstIndex(where: { $0.id == p.id }) { document.proposals[i] = p }
        if let d = m.documents.firstIndex(where: { $0.id == document.id }) { m.documents[d] = document }
        model = m
    }
}

/// Papier scannen met de documentscanner van iOS.
struct DocumentScanner: UIViewControllerRepresentable {
    let done: ([UIImage]) -> Void
    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> VNDocumentCameraViewController {
        let vc = VNDocumentCameraViewController()
        vc.delegate = context.coordinator
        return vc
    }
    func updateUIViewController(_ vc: VNDocumentCameraViewController, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, VNDocumentCameraViewControllerDelegate {
        let parent: DocumentScanner
        init(_ p: DocumentScanner) { parent = p }
        func documentCameraViewController(_ controller: VNDocumentCameraViewController, didFinishWith scan: VNDocumentCameraScan) {
            let images = (0..<scan.pageCount).map { scan.imageOfPage(at: $0) }
            parent.dismiss(); parent.done(images)
        }
        func documentCameraViewControllerDidCancel(_ controller: VNDocumentCameraViewController) { parent.dismiss() }
        func documentCameraViewController(_ controller: VNDocumentCameraViewController, didFailWithError error: Error) { parent.dismiss() }
    }
}
