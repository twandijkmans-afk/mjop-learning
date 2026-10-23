import MJOPIntegration
import SwiftUI

/// Volledig scherm voor een fotoronde (of een scan vanuit één onderhoudselement). Sluit altijd terug naar Mijn MJOP.
struct RoundFlowView: View {
    let context: PhotoRoundContext
    @EnvironmentObject var store: ScanStore
    @EnvironmentObject var coordinator: RoundCoordinator
    @State private var choices: [(SessionSnapshot, URL)] = []
    @State private var decided = false

    var body: some View {
        NavigationStack {
            Group {
                if decided && store.round != nil { RoundHomeView() }
                else { choiceView }
            }
        }
        .onAppear {
            choices = coordinator.resumable(for: context)
            if choices.isEmpty { coordinator.startNew(context); decided = true }
        }
    }

    private var choiceView: some View {
        List {
            Section("Er staat al een ronde voor dit project op dit toestel") {
                ForEach(Array(choices.enumerated()), id: \.offset) { _, c in
                    Button("\(c.0.round?.status == "COMPLETED" ? "Aanvullen" : "Hervatten"): \(c.0.keyframes.count) foto's, \(c.0.drafts.count) kozijnen") {
                        coordinator.resume(c.0, from: c.1); decided = true
                    }.accessibilityIdentifier("roundResume")
                }
                Button("Nieuwe ronde starten") { coordinator.startNew(context); decided = true }.accessibilityIdentifier("roundNew")
            }
            Section { Button("Annuleren", role: .cancel) { coordinator.suspend() } }
        }
        .navigationTitle("Fotoronde")
    }
}

struct RoundHomeView: View {
    @EnvironmentObject var store: ScanStore
    @EnvironmentObject var coordinator: RoundCoordinator
    @State private var showFacadeForm = false
    @State private var goScan = false
    @State private var confirmFinish = false

    private var round: RoundState? { store.round }

    private func counts(_ facade: String) -> (photos: Int, objects: Int) {
        guard let r = round else { return (0, 0) }
        let frames = Set(store.keyframes.map { $0.id }.filter { r.frameFacade[$0] == facade })
        let objs = store.drafts.filter { d in d.observationIds.contains { id in
            guard let o = store.observation(id), !o.rejected else { return false }
            return frames.contains(o.frameId) && !r.excludedFrames.contains(o.frameId) } }
        return (frames.count, objs.count)
    }

    var body: some View {
        let ctx = round?.context
        List {
            Section("Project") {
                LabeledContent("Gebouw", value: ctx?.buildingLabel ?? "")
                if let e = ctx?.element { LabeledContent("Onderhoudspost", value: e.name); LabeledContent("Eenheid", value: e.unit == "st" ? "stuks" : e.unit) }
                Text("De uitkomst is een voorstel voor Mijn MJOP. Er wordt niets automatisch overgenomen.").font(.footnote).foregroundStyle(.secondary)
            }
            Section("Gevels") {
                ForEach(round?.facades ?? []) { f in
                    let c = counts(f.id)
                    HStack {
                        VStack(alignment: .leading) {
                            Text(f.id).font(.headline)
                            Text("\(c.photos) foto's · \(c.objects) kozijnen" + (f.orientation.map { " · \($0)" } ?? "")).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button("Foto's maken") { store.facadeId = f.id; goScan = true }.buttonStyle(.borderedProminent).accessibilityIdentifier("roundShoot-\(f.id)")
                    }
                }
                Button("Gevel toevoegen") { showFacadeForm = true }.accessibilityIdentifier("roundAddFacade")
            }
            Section("Controleren en afronden") {
                NavigationLink("Overzicht en controle") { RoundReviewView() }.accessibilityIdentifier("roundReview")
                Button("Onderbreken en bewaren") { coordinator.suspend() }.accessibilityIdentifier("roundSuspend")
                Button("Afronden en naar Mijn MJOP sturen") { confirmFinish = true }
                    .disabled(store.keyframes.isEmpty).accessibilityIdentifier("roundFinish")
            }
        }
        .navigationTitle("Fotoronde").navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("roundHome")
        .navigationDestination(isPresented: $goScan) { PhotoScanView().environmentObject(store) }
        .sheet(isPresented: $showFacadeForm) { FacadeFormView().environmentObject(coordinator) }
        .confirmationDialog("Ronde afronden?", isPresented: $confirmFinish, titleVisibility: .visible) {
            Button("Afronden en voorstellen sturen") { coordinator.finish() }
            Button("Annuleren", role: .cancel) {}
        } message: {
            let p = coordinator.preview()
            let warn = Set(p.flatMap { $0.reliability.reasons }).subtracting(["UNVALIDATED_LIDAR"]).sorted()
            Text(warn.isEmpty ? "De voorstellen zijn voorlopig (LiDAR niet gevalideerd) en worden pas hoeveelheden nadat jij ze in Mijn MJOP kiest."
                              : "Let op: \(warn.joined(separator: ", ")). De voorstellen zijn voorlopig en worden pas hoeveelheden nadat jij ze in Mijn MJOP kiest.")
        }
    }
}

struct FacadeFormView: View {
    @EnvironmentObject var coordinator: RoundCoordinator
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var orientation = ""
    @State private var failed = false
    private let options = ["", "N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    var body: some View {
        NavigationStack {
            Form {
                TextField("Naam, bv. Voorgevel", text: $name).accessibilityIdentifier("facadeName")
                Picker("Windrichting (indien bekend)", selection: $orientation) {
                    ForEach(options, id: \.self) { Text($0.isEmpty ? "onbekend" : $0).tag($0) }
                }
                if failed { Text("Deze naam is leeg, te lang of bestaat al.").foregroundStyle(.red).font(.footnote) }
            }
            .navigationTitle("Gevel toevoegen").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuleren") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Toevoegen") { if coordinator.addFacade(name: name, orientation: orientation.isEmpty ? nil : orientation) { dismiss() } else { failed = true } }
                        .accessibilityIdentifier("facadeAdd")
                }
            }
        }
    }
}

struct RoundReviewView: View {
    @EnvironmentObject var store: ScanStore
    @EnvironmentObject var coordinator: RoundCoordinator

    var body: some View {
        let proposals = coordinator.preview()
        let dupCount = store.linkSuggestions().count
        List {
            Section("Voorstellen (voorlopig)") {
                if store.keyframes.isEmpty { Text("Nog geen foto's.").foregroundStyle(.secondary) }
                ForEach(store.keyframes.isEmpty ? [] : proposals, id: \.proposalId) { p in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(p.target.quantityKind == .FRAME_COUNT ? "Aantal kozijnen" : "Bruto kozijnoppervlak") · \(p.target.scope.type == .BUILDING ? "hele gebouw" : "gevel \(p.target.scope.facadeId ?? "")")").font(.subheadline)
                        Text(valueText(p)).font(.headline)
                        if p.value == nil, let part = p.partialValue { Text("Alleen gemeten kozijnen: \(fmt(part)) m² — onvolledig").font(.caption).foregroundStyle(.orange) }
                        Text(p.reliability.reasons.filter { $0 != "UNVALIDATED_LIDAR" }.map(label).joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Text("Detectie en meting zijn nog niet gevalideerd op echte gebouwen. Een voorstel wordt pas een hoeveelheid als jij het in Mijn MJOP kiest.").font(.caption2).foregroundStyle(.secondary)
            }
            if dupCount > 0 {
                Section("Mogelijk dubbel geteld") {
                    NavigationLink("Koppelsuggesties bekijken (\(dupCount))") { LinkSuggestionsView().environmentObject(store) }
                }
            }
            ForEach(store.round?.facades ?? []) { f in
                let frames = store.keyframes.filter { store.round?.frameFacade[$0.id] == f.id }
                if !frames.isEmpty {
                    Section("Gevel \(f.id)") {
                        ForEach(frames) { kf in
                            let n = store.observations.filter { $0.frameId == kf.id && !$0.rejected }.count
                            NavigationLink("Foto \(kf.id) · \(n) kozijnen") { PhotoResultView(frameId: kf.id).environmentObject(store) }
                            Toggle("Niet meetellen (overlapt met andere foto)", isOn: Binding(
                                get: { store.round?.excludedFrames.contains(kf.id) ?? false },
                                set: { coordinator.setExcluded(frame: kf.id, $0) })).font(.footnote)
                        }
                    }
                }
            }
        }
        .navigationTitle("Overzicht en controle")
        .onAppear { store.measureAll() }
    }

    private func fmt(_ v: Double) -> String { String(format: "%.2f", v).replacingOccurrences(of: ".", with: ",") }
    private func valueText(_ p: ScanProposalV2) -> String {
        guard let v = p.value else { return "Niet te bepalen" }
        return p.target.unit == "st" ? "\(Int(v)) st." : "\(fmt(v)) m²"
    }
    private func label(_ r: String) -> String {
        switch r {
        case "UNMEASURED_OBJECTS": return "kozijnen zonder maat"
        case "DUPLICATES_UNRESOLVED": return "mogelijk dubbel"
        case "CROSS_SESSION_UNCHECKED": return "overlap tussen scanmomenten niet gecontroleerd"
        case "AUTO_DETECTED": return "automatisch herkend, niet bevestigd"
        case "NO_OBJECTS": return "geen kozijnen"
        default: return r
        }
    }
}
