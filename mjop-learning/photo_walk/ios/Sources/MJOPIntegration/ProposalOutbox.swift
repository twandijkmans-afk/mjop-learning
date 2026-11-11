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
        /// Gevelinventaris van Gevelscanner 2.0 (`mjop_gevel_inventory_v1`). Optioneel: outbox-bestanden van vóór 2.0 hebben dit veld niet en blijven leesbaar.
        public var inventory: GevelInventoryV1?
        public var inventoryDelivered: Bool?
        public init(roundId: String, planRef: String, status: String, photos: Int, objects: Int, revision: Int, proposals: [ScanProposalV2], deliveredIds: [String] = [],
                    inventory: GevelInventoryV1? = nil, inventoryDelivered: Bool? = nil) {
            self.roundId = roundId; self.planRef = planRef; self.status = status; self.photos = photos; self.objects = objects
            self.revision = revision; self.proposals = proposals; self.deliveredIds = deliveredIds; self.inventory = inventory; self.inventoryDelivered = inventoryDelivered }
        /// Tolerant voor de inventaris: voldoet een eerder opgeslagen inventaris niet (meer) aan het contract, dan vervalt alleen die inventaris.
        /// De ronde en haar v2-voorstellen blijven leesbaar; anders zou één onleesbaar veld de hele outbox leegmaken.
        public init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            roundId = try c.decode(String.self, forKey: .roundId); planRef = try c.decode(String.self, forKey: .planRef); status = try c.decode(String.self, forKey: .status)
            photos = try c.decode(Int.self, forKey: .photos); objects = try c.decode(Int.self, forKey: .objects); revision = try c.decode(Int.self, forKey: .revision)
            proposals = try c.decode([ScanProposalV2].self, forKey: .proposals); deliveredIds = try c.decode([String].self, forKey: .deliveredIds)
            inventory = try? c.decodeIfPresent(GevelInventoryV1.self, forKey: .inventory)
            inventoryDelivered = inventory == nil ? nil : (try? c.decodeIfPresent(Bool.self, forKey: .inventoryDelivered))
        }
        public var isSynced: Bool { !proposals.isEmpty && proposals.allSatisfy { deliveredIds.contains($0.proposalId) } }
    }
    public var rounds: [Round] = []
    public init(rounds: [Round] = []) { self.rounds = rounds }

    public mutating func upsert(_ r: Round) {
        if let i = rounds.firstIndex(where: { $0.roundId == r.roundId }) {
            var n = r
            // een eerder overgedragen voorstel (zelfde id) blijft als overgedragen gemarkeerd; nieuwe revisies hebben nieuwe id's
            n.deliveredIds = rounds[i].deliveredIds.filter { id in r.proposals.contains { $0.proposalId == id } }
            // dezelfde inventaris (zelfde id) blijft als overgedragen gemarkeerd; een nieuwe revisie heeft een nieuw id
            n.inventoryDelivered = (r.inventory != nil && r.inventory?.inventoryId == rounds[i].inventory?.inventoryId) ? rounds[i].inventoryDelivered : nil
            rounds[i] = n
        } else { rounds.append(r) }
    }

    /// Alleen voorstellen van dit project (planRef); nooit van een ander project. Een voorstel met een mogelijke dubbeltelling gaat altijd
    /// zonder waarde de deur uit (ook als het eerder, vóór deze regel, met een waarde is opgeslagen); het opgeslagen bestand blijft ongewijzigd.
    public func proposals(forPlan planRef: String) -> [ScanProposalV2] {
        rounds.filter { $0.planRef == planRef && $0.status == "COMPLETED" }.flatMap { $0.proposals }.filter { $0.project.planRef == planRef }
            .map { $0.withUncheckedQuantitiesBlocked() }
    }

    /// Gevelinventarissen van dit project (alleen afgeronde rondes, nooit van een ander project). Worden bij elke vraag opnieuw aangeboden;
    /// de website voegt idempotent samen op `inventory_id`.
    public func inventories(forPlan planRef: String) -> [GevelInventoryV1] {
        rounds.filter { $0.planRef == planRef && $0.status == "COMPLETED" }.compactMap { $0.inventory }.filter { $0.planRef == planRef }
    }

    public func summaries(forPlan planRef: String) -> [[String: Any]] {
        rounds.filter { $0.planRef == planRef }.map { ["roundId": $0.roundId, "status": $0.status, "photos": $0.photos, "objects": $0.objects, "synced": $0.isSynced] }
    }

    /// Markeert alleen id's die echt bij dit project horen; onbekende of vreemde id's worden genegeerd.
    public mutating func ack(planRef: String, proposalIds: [String]) {
        for i in rounds.indices where rounds[i].planRef == planRef {
            let own = Set(rounds[i].proposals.map { $0.proposalId })
            for id in proposalIds where own.contains(id) && !rounds[i].deliveredIds.contains(id) { rounds[i].deliveredIds.append(id) }
            if let inv = rounds[i].inventory, proposalIds.contains(inv.inventoryId) { rounds[i].inventoryDelivered = true }
        }
    }
}
