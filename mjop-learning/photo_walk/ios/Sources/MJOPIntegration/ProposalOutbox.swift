import Foundation

/// Uitgaande voorstellen van afgeronde rondes, per ronde bewaard. Zuivere logica (opslag doet de app): welke voorstellen horen bij welk project,
/// wat is al overgedragen. Voorstellen worden bij elke vraag opnieuw aangeboden (de website voegt idempotent samen), zodat niets verloren gaat als de
/// website-staat verdwijnt voordat het plan is opgeslagen.
public struct ProposalOutbox: Codable, Equatable {
    public struct Round: Codable, Equatable {
        public var roundId: String
        public var planRef: String
        public var status: String              // IN_PROGRESS | COMPLETED
        public var photos: Int
        public var objects: Int
        public var revision: Int
        public var proposals: [ScanProposalV2]
        public var deliveredIds: [String]
        public init(roundId: String, planRef: String, status: String, photos: Int, objects: Int, revision: Int, proposals: [ScanProposalV2], deliveredIds: [String] = []) {
            self.roundId = roundId; self.planRef = planRef; self.status = status; self.photos = photos; self.objects = objects
            self.revision = revision; self.proposals = proposals; self.deliveredIds = deliveredIds }
        public var isSynced: Bool { !proposals.isEmpty && proposals.allSatisfy { deliveredIds.contains($0.proposalId) } }
    }
    public var rounds: [Round] = []
    public init(rounds: [Round] = []) { self.rounds = rounds }

    public mutating func upsert(_ r: Round) {
        if let i = rounds.firstIndex(where: { $0.roundId == r.roundId }) {
            var n = r
            // een eerder overgedragen voorstel (zelfde id) blijft als overgedragen gemarkeerd; nieuwe revisies hebben nieuwe id's
            n.deliveredIds = rounds[i].deliveredIds.filter { id in r.proposals.contains { $0.proposalId == id } }
            rounds[i] = n
        } else { rounds.append(r) }
    }

    /// Alleen voorstellen van dit project (planRef); nooit van een ander project.
    public func proposals(forPlan planRef: String) -> [ScanProposalV2] {
        rounds.filter { $0.planRef == planRef && $0.status == "COMPLETED" }.flatMap { $0.proposals }.filter { $0.project.planRef == planRef }
    }

    public func summaries(forPlan planRef: String) -> [[String: Any]] {
        rounds.filter { $0.planRef == planRef }.map { ["roundId": $0.roundId, "status": $0.status, "photos": $0.photos, "objects": $0.objects, "synced": $0.isSynced] }
    }

    /// Markeert alleen id's die echt bij dit project horen; onbekende of vreemde id's worden genegeerd.
    public mutating func ack(planRef: String, proposalIds: [String]) {
        for i in rounds.indices where rounds[i].planRef == planRef {
            let own = Set(rounds[i].proposals.map { $0.proposalId })
            for id in proposalIds where own.contains(id) && !rounds[i].deliveredIds.contains(id) { rounds[i].deliveredIds.append(id) }
        }
    }
}
