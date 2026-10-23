import ARKit
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
            Section("Er staat al een fotoronde voor dit gebouw op dit toestel") {
                ForEach(Array(choices.enumerated()), id: \.offset) { _, c in
                    Button("\(c.0.round?.status == "COMPLETED" ? "Foto's aanvullen" : "Verdergaan"): \(c.0.keyframes.count) foto's, \(c.0.drafts.count) mogelijke kozijnen") {
                        coordinator.resume(c.0, from: c.1); decided = true
                    }.accessibilityIdentifier("roundResume")
                }
                Button("Opnieuw beginnen") { coordinator.startNew(context); decided = true }.accessibilityIdentifier("roundNew")
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
    @State private var autoOpened = false

    private var round: RoundState? { store.round }

    /// De gevel waarop de volgende foto's komen: de gekozen gevel, anders de eerste.
    private var activeFacade: String {
        if let r = round, r.facades.contains(where: { $0.id == store.facadeId }) { return store.facadeId }
        return round?.facades.first?.id ?? ""
    }

    private func counts(_ facade: String) -> (photos: Int, objects: Int) {
        guard let r = round else { return (0, 0) }
        let frames = Set(store.keyframes.map { $0.id }.filter { r.frameFacade[$0] == facade })
        let objs = store.drafts.filter { d in d.observationIds.contains { id in
            guard let o = store.observation(id), !o.rejected else { return false }
            return frames.contains(o.frameId) && !r.excludedFrames.contains(o.frameId) } }
        return (frames.count, objs.count)
    }

    private var totals: (photos: Int, objects: Int) {
        (round?.facades ?? []).reduce((photos: 0, objects: 0)) { acc, f in
            let c = counts(f.id)
            return (acc.photos + c.photos, acc.objects + c.objects)
        }
    }

    private func foundText(_ n: Int) -> String {
        n == 0 ? "Er zijn nog geen kozijnen gevonden." : n == 1 ? "Er is 1 mogelijk kozijn gevonden." : "Er zijn \(n) mogelijke kozijnen gevonden."
    }

    var body: some View {
        let ctx = round?.context
        let t = totals
        List {
            // Compact: alles wat de gebruiker nodig heeft past op één scherm, zodat de knoppen niet onder de vouw verdwijnen.
            Section {
                VStack(alignment: .leading, spacing: 3) {
                    Text(ctx?.buildingLabel ?? "").font(.headline)
                    if let e = ctx?.element { Text("Voor: \(e.name) · in \(e.unit == "st" ? "stuks" : e.unit)").font(.subheadline).foregroundStyle(.secondary) }
                    if !activeFacade.isEmpty { Text("Gevel: \(activeFacade)").font(.subheadline).foregroundStyle(.secondary) }
                }
                if store.keyframes.isEmpty {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Zo maak je goede foto's").font(.subheadline.bold())
                        Text("Zorg dat het hele kozijn in beeld staat.").font(.footnote)
                        Text("Sta recht voor de gevel, op 2 tot 4 meter afstand.").font(.footnote)
                        Text("Maak van elke gevel meerdere foto's.").font(.footnote)
                    }
                } else {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("\(t.photos) \(t.photos == 1 ? "foto" : "foto's") gemaakt").font(.subheadline)
                        Text(foundText(t.objects)).font(.headline).accessibilityIdentifier("roundFound")
                        Text("Controleer of alle kozijnen kloppen.").font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            Section {
                Button { store.facadeId = activeFacade; goScan = true } label: {
                    Label(store.keyframes.isEmpty ? "Foto's maken" : "Meer foto's maken", systemImage: "camera.fill").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent).controlSize(.large).accessibilityIdentifier("roundShoot-\(activeFacade)")
                NavigationLink("Controleer de kozijnen") { RoundReviewView() }.accessibilityIdentifier("roundReview")
                Button { confirmFinish = true } label: { Text("Toevoegen aan MJOP").frame(maxWidth: .infinity) }
                    .buttonStyle(.borderedProminent).tint(.green).controlSize(.large)
                    .disabled(store.keyframes.isEmpty).accessibilityIdentifier("roundFinish")
                Button("Later verdergaan") { coordinator.suspend() }.accessibilityIdentifier("roundSuspend")
            } footer: {
                Text("Je foto's worden bewaard, zodat je later kunt verdergaan. Er wordt niets automatisch overgenomen: jij controleert de voorstellen eerst in Mijn MJOP.")
            }
            Section {
                DisclosureGroup("Meer opties") {
                    ForEach(round?.facades ?? []) { f in
                        let c = counts(f.id)
                        Button { store.facadeId = f.id } label: {
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(f.id)
                                    Text("\(c.photos) foto's · \(c.objects) mogelijke kozijnen" + (f.orientation.map { " · \($0)" } ?? "")).font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                if f.id == activeFacade { Image(systemName: "checkmark").foregroundStyle(.tint) }
                            }
                        }
                    }
                    Button("Nog een gevel toevoegen") { showFacadeForm = true }.accessibilityIdentifier("roundAddFacade")
                }
            }
        }
        .navigationTitle("Fotoronde").navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("roundHome")
        .navigationDestination(isPresented: $goScan) { PhotoScanView().environmentObject(store) }
        .sheet(isPresented: $showFacadeForm) { FacadeFormView().environmentObject(coordinator) }
        .onAppear {
            // Op een echt toestel opent de camera meteen voor het juiste project; in de simulator (geen AR) blijft dit scherm staan.
            if !autoOpened, store.keyframes.isEmpty, ARWorldTrackingConfiguration.isSupported, !activeFacade.isEmpty {
                autoOpened = true; store.facadeId = activeFacade; goScan = true
            }
        }
        .confirmationDialog("Toevoegen aan MJOP?", isPresented: $confirmFinish, titleVisibility: .visible) {
            Button("Toevoegen aan MJOP") { coordinator.finish() }
            Button("Annuleren", role: .cancel) {}
        } message: {
            let p = coordinator.preview()
            let warn = Set(p.flatMap { $0.reliability.reasons }).subtracting(["UNVALIDATED_LIDAR"])
            Text(warn.isEmpty ? "Je krijgt voorlopige voorstellen. Pas als jij ze in Mijn MJOP kiest, worden het hoeveelheden."
                              : "Sommige maten zijn nog niet betrouwbaar genoeg. Je krijgt voorlopige voorstellen; pas als jij ze in Mijn MJOP kiest, worden het hoeveelheden.")
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
            Section("Wat de app heeft gevonden (voorlopig)") {
                Text("Controleer of alle kozijnen kloppen.").font(.footnote)
                if store.keyframes.isEmpty { Text("Nog geen foto's.").foregroundStyle(.secondary) }
                ForEach(store.keyframes.isEmpty ? [] : proposals, id: \.proposalId) { p in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(p.target.quantityKind == .FRAME_COUNT ? "Aantal kozijnen" : "Kozijnoppervlak (bruto)") · \(p.target.scope.type == .BUILDING ? "hele gebouw" : "gevel \(p.target.scope.facadeId ?? "")")").font(.subheadline)
                        Text(valueText(p)).font(.headline)
                        if p.value == nil, let part = p.partialValue { Text("Voor een deel van de kozijnen is er een maat: \(fmt(part)) m². Het totaal is nog niet compleet.").font(.caption).foregroundStyle(.orange) }
                        Text(p.reliability.reasons.filter { $0 != "UNVALIDATED_LIDAR" }.map(label).joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Text("De herkenning en de maten zijn nog niet getest op echte gebouwen. Een voorstel wordt pas een hoeveelheid als jij het in Mijn MJOP kiest.").font(.caption2).foregroundStyle(.secondary)
            }
            if dupCount > 0 {
                Section("Misschien dubbel geteld") {
                    NavigationLink("Koppelsuggesties bekijken (\(dupCount))") { LinkSuggestionsView().environmentObject(store) }
                }
            }
            if !store.keyframes.isEmpty {
                Section {
                    DisclosureGroup("Technische details") {
                        ForEach(proposals, id: \.proposalId) { p in
                            Text("\(p.proposalId) · \(p.reliability.reasons.joined(separator: ", "))").font(.caption2).textSelection(.enabled)
                        }
                    }
                }
            }
            ForEach(store.round?.facades ?? []) { f in
                let frames = store.keyframes.filter { store.round?.frameFacade[$0.id] == f.id }
                if !frames.isEmpty {
                    Section("Gevel \(f.id)") {
                        ForEach(frames) { kf in
                            let n = store.observations.filter { $0.frameId == kf.id && !$0.rejected }.count
                            NavigationLink("Foto \(kf.id) · \(n) \(n == 1 ? "mogelijk kozijn" : "mogelijke kozijnen")") { PhotoResultView(frameId: kf.id, simple: true).environmentObject(store) }
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
        guard let v = p.value else { return "Nog niet te bepalen" }
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
