import MJOPIntegration
import SwiftUI

/// Een onderbroken fotoronde op dit toestel (uit de bestaande lokale opslag).
struct ResumableRound: Identifiable {
    let id: String
    let label: String
    let photos: Int
    let savedAt: Date
    let context: PhotoRoundContext

    static func load() -> [ResumableRound] {
        Persistence.rounds().compactMap { pair -> ResumableRound? in
            let snap = pair.0
            guard let r = snap.round, r.status != "COMPLETED" else { return nil }
            return ResumableRound(id: snap.sessionId, label: r.context.buildingLabel, photos: snap.keyframes.count, savedAt: snap.savedAt, context: r.context)
        }
    }
}

/// Meten: het centrale onderdeel van de gevelscanner. Project kiezen, een fotoronde starten of hervatten, resultaten bekijken.
/// De scanner zelf (camera, ARKit, LiDAR, kozijnherkenning, Persistence, ProposalOutbox) is ongewijzigd; dit scherm start hem alleen met de juiste projectcontext.
struct MeasureTabView: View {
    @EnvironmentObject var nav: AppNavigator
    @EnvironmentObject var rounds: RoundCoordinator
    @ObservedObject var web: MJOPWebController
    @State private var showPicker = false
    @State private var resumable: [ResumableRound] = []
    @State private var local = LocalMeasureSummary()

    var body: some View {
        NavigationStack {
            List {
                if !web.isOnline {
                    Section { Label("Je bent offline. Een nieuwe meting starten vraagt internet om het project te openen; onderbroken rondes kun je wel hervatten.", systemImage: "wifi.slash").font(.footnote).foregroundStyle(.orange) }
                }
                Section("Project") {
                    Button { showPicker = true } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(nav.measureProject?.label ?? "Geen project gekozen").font(.headline).foregroundStyle(.primary)
                                Text(projectHint).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text("Kies").foregroundStyle(.tint)
                        }
                    }
                    .accessibilityIdentifier("measureProjectButton")
                }
                Section {
                    Button { Task { @MainActor in await nav.startMeasurement(); local = LocalMeasureSummary.load(rounds) } } label: {
                        HStack {
                            Label("Nieuwe fotoronde starten", systemImage: "camera.viewfinder")
                            if nav.busy { Spacer(); ProgressView() }
                        }
                    }
                    .disabled(nav.measureProject == nil || nav.busy || web.navMode != .tabs)
                    .accessibilityIdentifier("measureStart")
                } header: {
                    Text("Gevel meten")
                } footer: {
                    Text("Maak foto's van de gevel. De uitkomst is een voorstel: er wordt niets automatisch aan het MJOP toegevoegd. Onbekende maten blijven onbekend.")
                }
                Section("Onderbroken fotorondes hervatten") {
                    if resumable.isEmpty {
                        Text("Geen onderbroken fotorondes op dit toestel.").foregroundStyle(.secondary).accessibilityIdentifier("measureNoResumable")
                    } else {
                        ForEach(resumable) { r in
                            Button { rounds.presented = PresentedRound(context: r.context) } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(r.label).font(.headline).foregroundStyle(.primary)
                                    Text("\(r.photos) foto's · bewaard \(relativeDateText(r.savedAt))").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            .accessibilityIdentifier("resume-\(r.label)")
                        }
                    }
                }
                Section("Resultaten") {
                    NavigationLink { MeasurementResultsView(web: web) } label: {
                        Label("Meetresultaten bekijken", systemImage: "list.bullet.rectangle")
                    }
                    .accessibilityIdentifier("measureResults")
                    StatusRow(label: "Nog niet overgedragen aan MJOP", value: "\(local.unsynced)", tint: local.unsynced > 0 ? .orange : .primary, identifier: "measureUnsynced")
                }
                Section("Geavanceerd") {
                    Button { nav.showScannerTest = true } label: { Label("Scanner-testmodus (zonder project)", systemImage: "wrench.and.screwdriver") }
                        .accessibilityIdentifier("measureScannerTest")
                }
            }
            .navigationTitle("Meten")
            .sheet(isPresented: $showPicker) { ProjectPickerView() }
            .task { @MainActor in await nav.refreshProjects(); reload() }
            .onAppear { reload() }
            .onChange(of: rounds.presented == nil) { _ in reload() }
        }
    }

    private var projectHint: String {
        if nav.measureProject == nil { return web.webStatus?.loggedIn == false ? "Log eerst in via Profiel" : "Kies het project waar de meting bij hoort" }
        return "De meting hoort bij dit project"
    }

    private func reload() {
        resumable = ResumableRound.load()
        local = LocalMeasureSummary.load(rounds)
    }
}

struct ProjectPickerView: View {
    @EnvironmentObject var nav: AppNavigator
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if let list = nav.projectList, list.loggedIn, !list.projects.isEmpty {
                    List(list.projects) { p in
                        Button {
                            nav.measureProjectId = p.id
                            dismiss()
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(p.label).font(.headline).foregroundStyle(.primary)
                                    if let a = p.adres, a != p.label { Text(a).font(.caption).foregroundStyle(.secondary) }
                                }
                                Spacer()
                                if nav.measureProject?.id == p.id { Image(systemName: "checkmark").foregroundStyle(MJOPTheme.green) }
                            }
                        }
                        .accessibilityIdentifier("pickProject-\(p.label)")
                    }
                } else if nav.projectList?.loggedIn == false {
                    EmptyStateView(icon: "person.crop.circle.badge.exclamationmark", title: "Niet ingelogd", message: "Log in via Profiel om een project te kiezen.")
                } else if nav.projectList != nil {
                    EmptyStateView(icon: "folder", title: "Nog geen opgeslagen projecten", message: "Maak eerst een project aan en sla het op.")
                } else if let e = nav.projectsError {
                    EmptyStateView(icon: "exclamationmark.triangle", title: "Projecten laden mislukt", message: e, actionTitle: "Opnieuw proberen", action: { Task { await nav.refreshProjects() } })
                } else {
                    ProgressView("Projecten laden…")
                }
            }
            .navigationTitle("Project kiezen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Sluiten") { dismiss() } } }
        }
    }
}

// MARK: - meetresultaten (lokale voorstellen en synchronisatiestatus)

struct MeasurementResultsView: View {
    @EnvironmentObject var rounds: RoundCoordinator
    @ObservedObject var web: MJOPWebController

    var body: some View {
        List {
            if rounds.outbox.rounds.isEmpty {
                Section { Text("Nog geen afgeronde fotorondes op dit toestel.").foregroundStyle(.secondary).accessibilityIdentifier("resultsEmpty") }
            } else {
                Section {
                    ForEach(rounds.outbox.rounds.reversed(), id: \.roundId) { r in
                        NavigationLink { RoundResultDetailView(round: r, web: web) } label: {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(Self.projectLabel(planRef: r.planRef)).font(.headline)
                                Text("\(r.photos) foto's · \(r.objects) kozijnen · \(r.proposals.count) voorstellen").font(.caption).foregroundStyle(.secondary)
                                Text(r.isSynced ? "Overgedragen aan Mijn MJOP" : "Alleen op dit toestel")
                                    .font(.caption.weight(.semibold)).foregroundStyle(r.isSynced ? MJOPTheme.green : Color.orange)
                            }
                        }
                    }
                } footer: {
                    Text("Dit zijn voorstellen. Ze worden pas onderdeel van het MJOP als je ze in MJOP bevestigt. Onbekende waarden blijven onbekend.")
                }
            }
        }
        .navigationTitle("Meetresultaten")
        .navigationBarTitleDisplayMode(.inline)
    }

    static func projectLabel(planRef: String) -> String {
        Persistence.rounds(planRef: planRef).first?.0.round?.context.buildingLabel ?? "Fotoronde"
    }
}

struct RoundResultDetailView: View {
    let round: ProposalOutbox.Round
    @ObservedObject var web: MJOPWebController

    var body: some View {
        List {
            Section("Samenvatting") {
                StatusRow(label: "Project", value: MeasurementResultsView.projectLabel(planRef: round.planRef))
                StatusRow(label: "Foto's", value: "\(round.photos)")
                StatusRow(label: "Kozijnen", value: "\(round.objects)")
                StatusRow(label: "Status", value: round.isSynced ? "Overgedragen" : "Alleen op dit toestel", tint: round.isSynced ? MJOPTheme.green : .orange)
            }
            Section("Voorstellen") {
                if round.proposals.isEmpty { Text("Deze ronde heeft geen voorstellen opgeleverd.").foregroundStyle(.secondary) }
                ForEach(round.proposals, id: \.proposalId) { p in ProposalRow(proposal: p) }
            }
            Section {
                if web.webStatus?.planRef == round.planRef {
                    NavigationLink {
                        WebScreenPage(title: "Voorstellen controleren", command: .navigate(tab: "fotoronde", sub: nil), web: web)
                    } label: {
                        Label("Voorstellen controleren in MJOP", systemImage: "checkmark.seal")
                    }
                    .accessibilityIdentifier("reviewInMJOP")
                } else {
                    Text("Open het bijbehorende project om de voorstellen te controleren.").foregroundStyle(.secondary)
                }
            } footer: {
                Text("Er is niets automatisch aan het MJOP toegevoegd. Een voorstel wordt pas een hoeveelheid als je het in MJOP bevestigt.")
            }
        }
        .navigationTitle("Fotoronde")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct ProposalRow: View {
    let proposal: ScanProposalV2

    private var unit: String { proposal.target.quantityKind == .FRAME_COUNT ? "st" : "m²" }
    private var title: String { proposal.target.quantityKind == .FRAME_COUNT ? "Aantal kozijnen" : "Bruto kozijnoppervlak" }
    private var scope: String {
        proposal.target.scope.type == .BUILDING ? "Hele gebouw" : "Gevel \(proposal.target.scope.facadeId ?? "onbekend")"
    }
    private func number(_ v: Double) -> String {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "nl_NL"); f.maximumFractionDigits = 2; f.minimumFractionDigits = 0
        return f.string(from: NSNumber(value: v)) ?? "\(v)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text("\(title) · \(scope)").font(.headline)
            // Onbekend is onbekend: nooit 0 tonen voor een ontbrekende waarde.
            if let v = proposal.value {
                Text("\(number(v)) \(unit)").font(.title3)
            } else {
                Text("Onbekend").font(.title3).foregroundStyle(.secondary)
                if let p = proposal.partialValue { Text("Deelwaarde (onvolledig, niet bruikbaar als totaal): \(number(p)) \(unit)").font(.caption).foregroundStyle(.secondary) }
            }
            Text(proposal.reliability.level == "INCOMPLETE" ? "Onvolledig" : "Controle nodig").font(.caption.weight(.semibold)).foregroundStyle(.orange)
            ForEach(proposal.reliability.reasons, id: \.self) { code in
                Text("• \(Self.reasonText(code))").font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }

    static func reasonText(_ code: String) -> String {
        switch code {
        case "UNVALIDATED_LIDAR": return "De LiDAR-nauwkeurigheid is nog niet gevalideerd op echte gebouwen."
        case "UNMEASURED_OBJECTS": return "Bij een deel van de kozijnen kon geen maat bepaald worden."
        case "DUPLICATES_UNRESOLVED": return "Mogelijk dubbel getelde kozijnen zijn nog niet beoordeeld."
        case "DUPLICATE_CHECK_INCOMPLETE": return "De controle op dubbele kozijnen is nog niet af."
        case "CROSS_SESSION_UNCHECKED": return "Foto's van verschillende scanmomenten zijn niet automatisch aan elkaar gekoppeld."
        case "AUTO_DETECTED": return "Kozijnen zijn automatisch herkend en nog niet allemaal bevestigd."
        case "NO_OBJECTS": return "Geen kozijnen gevonden."
        default: return code
        }
    }
}
