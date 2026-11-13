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
                                VStack(alignment: .leading, spacing: 4) {
                                    StoragePhotoView(path: g.photoPath) { DS.surface2 }
                                        .frame(width: 150, height: 110).clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                                    Text("Gevel op het \(g.facing)" + (g.part.map { " · \($0)" } ?? "")).font(.caption).foregroundStyle(DS.text2)
                                }
                            }
                        }
                    }
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
        .sheet(item: $detail) { t in
            if let m = model { KozijnTypeDetail(type: t, staat: m.kozijnStaat, sides: m.sides, overrides: m.kozijnOverrides ?? KozijnOverrides()) { o in save { $0.kozijnOverrides = o } } }
        }
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
