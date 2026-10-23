import ARKit
import Foundation
import MJOPIntegration
import SwiftUI

struct PresentedRound: Identifiable { let id = UUID(); let context: PhotoRoundContext }

/// Verwerkt de berichten van Mijn MJOP en beheert de levensloop van een fotoronde (starten, hervatten, onderbreken, afronden) en de uitgaande voorstellen.
/// Spreekt alleen over wat de website mag vragen (`BridgeRequest`); alles is al gevalideerd door `BridgeMessage.parse`.
@MainActor
final class RoundCoordinator: ObservableObject, BridgeHandling {
    @Published var presented: PresentedRound?
    @Published private(set) var outbox: ProposalOutbox
    weak var store: ScanStore?
    /// Levert een antwoord aan de WebView (alleen aan de eigen site).
    var deliver: (([String: Any]) -> Void)?
    var notice: ((String) -> Void)?

    init() { outbox = RoundCoordinator.loadOutbox() }

    // MARK: berichten van de website

    func handle(_ request: BridgeRequest) -> [[String: Any]] {
        switch request {
        case .startPhotoRound(let rid, let ctx), .startElementScan(let rid, let ctx):
            guard presented == nil else { return [BridgeReply.error(requestId: rid, message: "Er loopt al een fotoronde.")] }
            presented = PresentedRound(context: ctx)
            return []
        case .listProposals(let rid, let planRef):
            return [proposalsReply(requestId: rid, planRef: planRef)]
        case .ackProposals(_, let planRef, let ids):
            outbox.ack(planRef: planRef, proposalIds: ids); saveOutbox()
            return [["type": "round-status", "planRef": planRef, "rounds": roundSummaries(planRef: planRef)]]
        case .getCapabilities(let rid):
            let lidar = ARWorldTrackingConfiguration.isSupported && ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
            return [BridgeReply.capabilities(requestId: rid, lidar: lidar, appVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1")]
        case .print:
            return []
        }
    }

    func proposalsReply(requestId: String?, planRef: String) -> [String: Any] {
        var m: [String: Any] = ["type": "proposals", "planRef": planRef,
                                "proposals": outbox.proposals(forPlan: planRef).compactMap { $0.jsonObject() }, "rounds": roundSummaries(planRef: planRef)]
        if let r = requestId { m["requestId"] = r }
        return m
    }

    /// Afgeronde rondes (uit de outbox) plus onderbroken rondes die nog op dit toestel staan.
    func roundSummaries(planRef: String) -> [[String: Any]] {
        var out = outbox.summaries(forPlan: planRef)
        let known = Set(outbox.rounds.map { $0.roundId })
        for (snap, _) in Persistence.rounds(planRef: planRef) where !known.contains(snap.sessionId) {
            out.append(["roundId": snap.sessionId, "status": snap.round?.status ?? "IN_PROGRESS", "photos": snap.keyframes.count,
                        "objects": snap.drafts.count, "synced": false])
        }
        return out
    }

    // MARK: levensloop

    func resumable(for ctx: PhotoRoundContext) -> [(SessionSnapshot, URL)] {
        Persistence.rounds(planRef: ctx.planRef).filter { $0.0.round?.context.mode == ctx.mode && $0.0.round?.context.element?.key == ctx.element?.key }
    }

    func startNew(_ ctx: PhotoRoundContext) {
        guard let store else { return }
        store.newSession()
        store.buildingId = ctx.buildingLabel
        // Geen gevel gepland? Dan maakt de app zelf één gevel aan, zodat de gebruiker meteen foto's kan maken (extra gevels kunnen later).
        var facades: [RoundState.Facade] = ctx.plannedFacades.map { .init(id: $0.name, orientation: $0.orientation) }
        if facades.isEmpty { facades = [.init(id: "Gevel 1", orientation: nil)] }
        store.facadeId = facades[0].id
        store.round = RoundState(context: ctx, facades: facades)
    }

    func resume(_ snap: SessionSnapshot, from dir: URL) {
        guard let store else { return }
        Persistence.restore(snap, from: dir, into: store)
        if store.round?.status == "COMPLETED" { store.round?.revision += 1 }     // aanvullen van een afgeronde ronde = nieuwe revisie
        store.round?.status = "IN_PROGRESS"
        store.facadeId = store.round?.facades.first?.id ?? ""
    }

    func addFacade(name: String, orientation: String?) -> Bool {
        let n = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let store, (1...60).contains(n.count), store.round != nil, !(store.round?.facades.contains { $0.id == n } ?? true) else { return false }
        store.round?.facades.append(.init(id: n, orientation: orientation))
        return true
    }

    func setExcluded(frame: String, _ excluded: Bool) {
        guard let store else { return }
        if excluded { store.round?.excludedFrames.insert(frame) } else { store.round?.excludedFrames.remove(frame) }
        store.persist()
    }

    /// Bewaart de ronde en sluit het scherm; later hervatten kan vanuit dezelfde post.
    func suspend() {
        if let store, !store.keyframes.isEmpty { Persistence.saveNow(store); notice?("Je foto's zijn bewaard. Je kunt later verdergaan.") }
        presented = nil
    }

    func preview() -> [ScanProposalV2] {
        guard let store, let input = RoundInputBuilder.build(store: store, createdAt: Self.isoNow()) else { return [] }
        return RoundProposalBuilder.build(input)
    }

    func finish() {
        guard let store, var round = store.round else { return }
        store.measureAll()
        round.status = "COMPLETED"
        store.round = round
        guard let input = RoundInputBuilder.build(store: store, createdAt: Self.isoNow()) else { return }
        let proposals = RoundProposalBuilder.build(input)
        let photos = store.keyframes.filter { !round.excludedFrames.contains($0.id) }.count
        outbox.upsert(.init(roundId: store.sessionId, planRef: round.context.planRef, status: "COMPLETED", photos: photos, objects: input.objects.count,
                            revision: round.revision, proposals: proposals))
        saveOutbox()
        Persistence.saveNow(store)
        presented = nil
        deliver?(proposalsReply(requestId: nil, planRef: round.context.planRef))
        notice?("Klaar. Controleer de voorstellen in Mijn MJOP; er is nog niets overgenomen.")
    }

    // MARK: outbox-opslag (Application Support, uitgesloten van back-up, bestandsbescherming)

    static func isoNow() -> String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        return f.string(from: Date())
    }

    private static var outboxURL: URL? { Persistence.root?.appendingPathComponent("outbox.json") }

    private static func loadOutbox() -> ProposalOutbox {
        guard let u = outboxURL, let d = try? Data(contentsOf: u), let o = try? JSONDecoder().decode(ProposalOutbox.self, from: d) else { return ProposalOutbox() }
        return o
    }

    private func saveOutbox() {
        guard let u = Self.outboxURL, let d = try? JSONEncoder().encode(outbox) else { return }
        try? d.write(to: u, options: [.atomic, .completeFileProtection])
    }
}
