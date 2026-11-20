import MJOPEngine
import SwiftUI

/// Eén regel in de kozijnstaat: "A · Raamkozijn hout · 1,20 × 1,50 m · 8×".
struct KozijnTypeRow: View {
    let t: KozijnType
    var body: some View {
        HStack(spacing: 12) {
            Text(t.letter).font(.headline).foregroundStyle(DS.accent).frame(width: 34, height: 34).background(DS.accentSoft, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 1) {
                Text(t.label).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                Text(KozijnFormat.size(t) + (t.derivedCount > 0 ? " · \(t.derivedCount) maat afgeleid" : "") + (t.editedByUser ? " · aangepast" : ""))
                    .font(.caption).foregroundStyle(DS.text2)
            }
            Spacer(minLength: 0)
            Text("\(t.count)×").font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
        }
        .padding(.horizontal, 14).frame(minHeight: 58)
        .accessibilityElement(children: .combine)
    }
}

enum KozijnFormat {
    static func m(_ v: Double) -> String { String(format: "%.2f", v).replacingOccurrences(of: ".", with: ",") }
    static func size(_ t: KozijnType) -> String { "\(m(t.widthM)) × \(m(t.heightM)) m" }
}

/// Kozijnen van één gevel, op het resultaatscherm van de scan.
struct KozijnScanCard: View {
    let result: KozijnStaatResult
    var body: some View {
        if result.total > 0 {
            VStack(alignment: .leading, spacing: 8) {
                Text("Kozijnen op deze gevel").font(.headline).foregroundStyle(DS.text)
                VStack(spacing: 0) {
                    ForEach(result.types) { t in
                        KozijnTypeRow(t: t)
                        if t.id != result.types.last?.id { Divider().padding(.leading, 60) }
                    }
                }
                .dsCard(radius: 20)
                if !result.unassigned.isEmpty {
                    DSNotice(kind: .warn, text: "\(result.unassigned.count) kozijn(en) grotendeels verborgen zonder gelijk type: ze tellen mee, maar de maat is onbekend. Maak een extra foto vanuit een andere hoek.")
                }
            }
        }
    }
}

/// Kozijnstaat van het hele gebouw in de projecttab Gevels: typen samenvoegen of een kozijn apart zetten.
struct KozijnStaatSection: View {
    let project: Project
    var onScan: () -> Void
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @State private var model: ProjectModel?
    @State private var detail: KozijnType?
    @State private var error: String?
    @State private var editing: FacadeScan?
    @State private var editImage: UIImage?
    @State private var loadingPhoto: Int?
    @State private var defectScan: FacadeScan?
    @State private var highlightItem: HighlightItem?
    @State private var highlightImage: UIImage?

    struct HighlightItem: Identifiable { let scan: FacadeScan; let measure: ElementMeasure; var id: String { measure.id } }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let error { DSNotice(kind: .warn, text: error) }
            if let m = model, !m.gevels.isEmpty {
                let withPhoto = m.gevels.filter { $0.photoPath != nil && $0.copiedFromSide == nil }.sorted { ($0.sideId, $0.part ?? 1) < ($1.sideId, $1.part ?? 1) }
                if !withPhoto.isEmpty {
                    Text("Gevelfoto's").font(.title3.weight(.bold)).foregroundStyle(DS.text)
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            ForEach(withPhoto) { g in
                                Button { Task { await openEditor(g) } } label: {
                                    VStack(alignment: .leading, spacing: 4) {
                                        StoragePhotoView(path: g.photoPath) { DS.surface2 }
                                            .frame(width: 150, height: 110).clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                                            .overlay { if loadingPhoto == g.id { ProgressView().tint(.white) } }
                                        Text("Gevel op het \(g.facing)" + (g.part.map { " · \($0)" } ?? "")).font(.caption).foregroundStyle(DS.text2)
                                        Text("Tik om aan te passen").font(.caption2).foregroundStyle(DS.accent)
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                let withDefects = m.gevels.filter { !($0.defects ?? []).isEmpty && $0.copiedFromSide == nil && $0.photoPath != nil }
                if !withDefects.isEmpty {
                    Text("Gebreken").font(.title3.weight(.bold)).foregroundStyle(DS.text)
                    VStack(spacing: 0) {
                        ForEach(withDefects) { g in
                            Button { Task { await openDefects(g) } } label: {
                                HStack(spacing: 12) {
                                    DSIcon(systemName: "exclamationmark.triangle")
                                    VStack(alignment: .leading, spacing: 1) {
                                        Text("Gevel op het \(g.facing)" + (g.part.map { " · foto \($0)" } ?? "")).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                                        let ds = g.defects ?? []
                                        Text("\(ds.count) gemarkeerd · \(ds.filter(\.isConfirmed).count) bevestigd · \(ds.filter { $0.status == nil }.count) nog te bekijken").font(.caption).foregroundStyle(DS.text2)
                                    }
                                    Spacer()
                                    if loadingPhoto == g.id { ProgressView() } else { Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(DS.text2) }
                                }
                                .padding(.horizontal, 14).frame(minHeight: 58)
                            }
                            .buttonStyle(DSRowStyle())
                            if g.id != withDefects.last?.id { Divider().padding(.leading, 60) }
                        }
                    }
                    .dsCard(radius: 20)
                }
                RoofAdviceCard(model: m) { y in save { RoofAdviceCard.apply(year: y, to: &$0) } }
                let groups = m.buildingGroups
                if !groups.isEmpty {
                    ElementListCard(groups: groups, title: "Elementen van het gebouw", subtitle: { meas in sideText(meas, m) }, onSelect: { meas in
                        Task { await openHighlight(meas, m) }
                    })
                }
                let staat = m.kozijnStaat
                HStack {
                    Text("Kozijnstaat").font(.title3.weight(.bold)).foregroundStyle(DS.text)
                    Spacer()
                    Text("\(staat.total) kozijnen · \(m.gevels.count) gevel(s)").font(.caption).foregroundStyle(DS.text2)
                }
                if staat.types.isEmpty && staat.unassigned.isEmpty {
                    Text("Op de gescande gevels zijn geen kozijnen met een maat gevonden.").font(.subheadline).foregroundStyle(DS.text2)
                } else {
                    VStack(spacing: 0) {
                        ForEach(staat.types) { t in
                            Button { detail = t } label: { KozijnTypeRow(t: t) }.buttonStyle(DSRowStyle())
                            if t.id != staat.types.last?.id { Divider().padding(.leading, 60) }
                        }
                    }
                    .dsCard(radius: 20)
                }
                if !staat.unassigned.isEmpty {
                    DSNotice(kind: .warn, text: "\(staat.unassigned.count) kozijn(en) grotendeels verborgen zonder gelijk type: ze tellen mee, maar de maat is onbekend.")
                    Button("Extra foto maken", action: onScan).buttonStyle(DSSecondaryButton())
                }
                if m.kozijnOverrides.map({ !$0.isEmpty }) ?? false {
                    Button("Automatische indeling herstellen") { save { $0.kozijnOverrides = nil } }.font(.footnote)
                }
                Text("Kozijnen met dezelfde soort en materiaal, en breedte en hoogte binnen 7%, vormen één type. Het best zichtbare kozijn geeft de maat; een deels verborgen kozijn krijgt de maat van zijn type.")
                    .font(.footnote).foregroundStyle(DS.text2)
            }
        }
        .task(id: project.id) { await load() }
        .onReceive(store.$projects) { _ in Task { await load() } }
        .fullScreenCover(item: $editing) { g in
            if let img = editImage {
                FacadeEditorView(image: img, scan: g) { updated in
                    save { m in
                        if let i = m.gevels.firstIndex(where: { $0.id == updated.id }) { m.gevels[i] = updated }
                        GevelscanFlow.applyQuantities(&m)
                    }
                }
            }
        }
        .sheet(item: $defectScan) { g in
            if let img = editImage {
                DefectListView(image: img, scan: g) { updated in
                    save { m in if let i = m.gevels.firstIndex(where: { $0.id == updated.id }) { m.gevels[i] = updated } }
                }
            }
        }
        .sheet(item: $highlightItem) { h in
            if let img = highlightImage { ElementHighlightSheet(image: img, scan: h.scan, measure: h.measure) }
        }
        .sheet(item: $detail) { t in
            if let m = model { KozijnTypeDetail(type: t, staat: m.kozijnStaat, sides: m.sides, overrides: m.kozijnOverrides ?? KozijnOverrides()) { o in save { $0.kozijnOverrides = o } } }
        }
    }

    /// Bij welke gevel een element hoort, voor de lijst van het hele gebouw.
    private func sideText(_ meas: ElementMeasure, _ m: ProjectModel) -> String? {
        if meas.sideId == 0 { return "Dak (luchtfoto)" }
        guard let sid = meas.sideId, let side = m.sides.first(where: { $0.id == sid }) else { return nil }
        let copied = m.gevels.contains { $0.sideId == sid && $0.copiedFromSide != nil }
        return "Gevel op het \(side.facing)" + (copied ? " · overgenomen (aanname)" : "")
    }

    /// Laat een element oplichten op de foto van zijn gevel. Een lange gevel in meerdere foto's of een overgenomen gevel heeft
    /// geen eigen foto met dezelfde nummers; dan alleen een melding.
    private func openHighlight(_ meas: ElementMeasure, _ m: ProjectModel) async {
        if meas.sideId == 0, let roof = m.roof {
            guard let img = await RoofScanner.image(for: roof) else { error = "De luchtfoto kon niet worden opgehaald."; return }
            error = nil
            highlightImage = img
            highlightItem = HighlightItem(scan: roof, measure: meas)
            return
        }
        let parts = m.gevels.filter { $0.sideId == meas.sideId }
        guard parts.count == 1, let g = parts.first, g.copiedFromSide == nil else {
            error = "Deze gevel bestaat uit meerdere foto's of is overgenomen van een andere gevel; aanwijzen op de foto kan hier niet."
            return
        }
        guard let path = g.photoPath, let s = try? await account.validSession() else {
            error = "De foto van deze gevel is niet in de cloud bewaard; alleen de maat is bekend."
            return
        }
        loadingPhoto = g.id; defer { loadingPhoto = nil }
        guard let img = await GevelFotos.load(path, session: s) else { error = "De foto kon niet worden geladen."; return }
        error = nil
        highlightImage = img
        highlightItem = HighlightItem(scan: g, measure: meas)
    }

    private func openDefects(_ g: FacadeScan) async {
        guard let path = g.photoPath, let s = try? await account.validSession() else { return }
        loadingPhoto = g.id; defer { loadingPhoto = nil }
        guard let img = await GevelFotos.load(path, session: s) else { error = "De foto kon niet worden geladen."; return }
        editImage = img
        defectScan = g
    }

    private func openEditor(_ g: FacadeScan) async {
        guard let path = g.photoPath, let s = try? await account.validSession() else { return }
        loadingPhoto = g.id; defer { loadingPhoto = nil }
        guard let img = await GevelFotos.load(path, session: s) else { error = "De foto kon niet worden geladen."; return }
        editImage = img
        editing = g
    }

    private func load() async {
        do { model = try await store.loadModel(project, account: account) } catch { self.error = error.localizedDescription }
    }

    private func save(_ change: (inout ProjectModel) -> Void) {
        guard var m = model else { return }
        change(&m)
        model = m
        Task { do { try await store.saveModel(m, for: project, account: account) } catch { self.error = error.localizedDescription } }
    }
}

struct KozijnTypeDetail: View {
    let type: KozijnType
    let staat: KozijnStaatResult
    let sides: [FacadeSide]
    @State var overrides: KozijnOverrides
    let onChange: (KozijnOverrides) -> Void
    @Environment(\.dismiss) private var dismiss

    init(type: KozijnType, staat: KozijnStaatResult, sides: [FacadeSide], overrides: KozijnOverrides, onChange: @escaping (KozijnOverrides) -> Void) {
        self.type = type; self.staat = staat; self.sides = sides; _overrides = State(initialValue: overrides); self.onChange = onChange
    }

    private var others: [KozijnType] { staat.types.filter { $0.id != type.id && $0.type == type.type } }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    KozijnTypeRow(t: type).listRowInsets(EdgeInsets())
                }
                if !others.isEmpty {
                    Section("Samenvoegen") {
                        ForEach(others) { o in
                            Button { overrides.merge[type.id] = o.id; commit() } label: {
                                Label("Voeg samen met type \(o.letter) (\(KozijnFormat.size(o)), \(o.count)×)", systemImage: "arrow.triangle.merge")
                            }
                        }
                    }
                }
                Section {
                    ForEach(type.members) { mb in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Gevel op het \(sides.first { $0.id == mb.item.sideId }?.facing ?? "?") · kozijn \(mb.item.elementId)").font(.subheadline)
                                Text(memberText(mb)).font(.caption).foregroundStyle(DS.text2)
                            }
                            Spacer()
                            if type.count > 1, !mb.derived {
                                Button("Zet apart") { overrides.separate.append(mb.id); commit() }.font(.footnote.weight(.semibold))
                            }
                        }
                    }
                } header: { Text("Kozijnen") } footer: {
                    Text("Samenvoegen en apart zetten worden bewaard als jouw keuze; de automatische indeling blijft te herstellen.")
                }
                if overrides.merge[type.id] != nil || overrides.separate.contains(type.id) {
                    Button("Keuze voor dit type ongedaan maken") {
                        overrides.merge[type.id] = nil; overrides.separate.removeAll { $0 == type.id }; commit()
                    }
                }
            }
            .navigationTitle("Type \(type.letter)").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Klaar") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
    }

    private func memberText(_ mb: KozijnMember) -> String {
        if mb.derived { return "deels verborgen · maat afgeleid van type \(type.letter)" }
        guard let w = mb.item.widthM, let h = mb.item.heightM else { return "maat onbekend" }
        return "gemeten \(KozijnFormat.m(w)) × \(KozijnFormat.m(h)) m"
    }

    private func commit() { onChange(overrides); dismiss() }
}
