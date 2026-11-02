import Foundation
import MJOPIntegration
import PhotoWalkCore

/// Zet de scansessie van een fotoronde om naar de neutrale invoer van `RoundProposalBuilder` (uniek per kozijn, per gevel, met uitsluitingen en onbeoordeelde duplicaten).
/// Alle rekenregels voor de voorstellen staan in `MJOPIntegration` (getest); hier alleen het verzamelen uit de sessie.
@MainActor
enum RoundInputBuilder {
    static let methods: Set<String> = ["LIDAR_DEPTH_PLANE", "LIDAR_DEPTH_MULTI_FRAME", "AR_TRIANGULATION_VIO", "REFERENCE_DISTANCE", "MANUAL_CORNERS", "NONE"]

    static func facadeId(of frameId: String, in store: ScanStore) -> String {
        store.round?.frameFacade[frameId] ?? (store.facadeId.isEmpty ? "Gevel" : store.facadeId)
    }

    static func build(store: ScanStore, createdAt: String) -> RoundBuildInput? {
        guard let round = store.round else { return nil }
        let excludedFrames = round.excludedFrames
        func counts(_ o: Observation) -> Bool { !o.rejected && !excludedFrames.contains(o.frameId) }

        var excluded: [String: Int] = [:]
        for o in store.observations where !counts(o) { excluded[facadeId(of: o.frameId, in: store), default: 0] += 1 }

        var objects: [RoundObject] = []
        for d in store.drafts {
            let obs = d.observationIds.compactMap { store.observation($0) }.filter(counts)
            guard let first = obs.first else { continue }
            let res = store.results.first { $0.id == d.id }
            let status: RoundObject.Status
            switch res?.status { case .MEASURED?: status = .measured; case .DERIVED?: status = .derived; case .ESTIMATED?: status = .estimated; default: status = .unknown }
            let area: Decimal? = (status != .unknown) ? res?.areaM2.flatMap { Decimal(string: $0) } : nil
            let scale = res?.result.scaleMethod ?? "NONE"
            let detected = obs.filter { $0.detection != nil }
            objects.append(RoundObject(
                id: d.id, facadeId: facadeId(of: first.frameId, in: store), frameIds: Array(Set(obs.map { $0.frameId })).sorted(), areaM2: area,
                areaSigmaM2: area == nil ? nil : res?.result.sigmaArea, status: status, method: methods.contains(scale) ? scale : "NONE",
                // bevestigd = elke herkende waarneming expliciet bevestigd; alleen hoeken verschoven (EDITED_UNCONFIRMED) telt niet als bevestigd
                autoDetected: !detected.isEmpty, userConfirmed: !detected.isEmpty && detected.allSatisfy { $0.source != .AUTO_DETECTED_UNCONFIRMED && !$0.outerContour.blocksArea },
                manual: obs.contains { $0.detection == nil && $0.source == .MANUAL }, flags: res?.flags.map { $0.code } ?? [],
                // gevelopbouw: alleen als ALLE waarnemingen van dit object een onbevestigde automatische buitencontour hebben (LEGACY telt niet)
                contourUnconfirmed: obs.allSatisfy { $0.outerContour.blocksArea },
                // duplicaatcontrole over foto's heen kan alleen met een ruimtelijke meting (zelfde criterium als de koppelsuggesties)
                duplicateCheckable: obs.contains { store.linkItem($0) != nil }))
        }

        // mogelijk dubbele kozijnen (zelfde AR-sessie, nog niet gekoppeld of genegeerd) per gevel. Een suggestie tussen twee gevels blokkeert
        // beide gevels (het mogelijke duplicaat kan in elk van beide meetellen); voor het gebouw telt elke suggestie één keer.
        var dups: [String: Int] = [:]
        var dupTotal = 0
        for c in store.linkSuggestions() {
            guard let a = store.observation(c.a), let b = store.observation(c.b), counts(a), counts(b) else { continue }
            let fa = facadeId(of: a.frameId, in: store), fb = facadeId(of: b.frameId, in: store)
            dups[fa, default: 0] += 1
            if fb != fa { dups[fb, default: 0] += 1 }
            dupTotal += 1
        }

        var facadeIds: [String] = round.facades.map { $0.id }
        for o in objects where !facadeIds.contains(o.facadeId) { facadeIds.append(o.facadeId) }
        let facades = facadeIds.map { fid -> RoundFacade in
            let frames = store.keyframes.map { $0.id }.filter { facadeId(of: $0, in: store) == fid && !excludedFrames.contains($0) }
            let worlds = Set(frames.compactMap { round.frameWorld[$0] })
            return RoundFacade(id: fid, orientation: round.facades.first { $0.id == fid }?.orientation, worldIds: worlds)
        }
        // foto -> AR-sessie, alleen voor meetellende foto's; een foto zonder bekende sessie ontbreekt (= onbekend, niet "zelfde sessie")
        var frameWorld: [String: String] = [:]
        for kf in store.keyframes where !excludedFrames.contains(kf.id) { if let w = round.frameWorld[kf.id] { frameWorld[kf.id] = w } }
        let fp = reviewFingerprint(store: store)
        let reviewed = round.duplicateReview.map { $0.fingerprint == fp } ?? false
        let ctx = round.context
        return RoundBuildInput(
            roundId: store.sessionId, revision: round.revision, createdAt: createdAt,
            project: .init(planRef: ctx.planRef, mjopPlanId: ctx.mjopPlanId, buildingId: ctx.buildingLabel, bagPandId: ctx.bagPandId),
            elementKey: ctx.element?.key, objects: objects, facades: facades, excludedObjectsByFacade: excluded, duplicatesUnresolvedByFacade: dups,
            duplicatesUnresolvedTotal: dupTotal, frameWorld: frameWorld, duplicateReviewConfirmed: reviewed)
    }

    /// Mag de inspecteur nu verklaren dat alles is nagelopen? Alleen als er een ronde is en GEEN openstaande koppelsuggestie meer is (in de
    /// meetellende foto's). Geldt voor de knop én voor het vastleggen zelf (RoundCoordinator.setDuplicateReview), niet alleen in de weergave.
    static func canRecordDuplicateReview(store: ScanStore) -> Bool {
        guard let input = build(store: store, createdAt: "1970-01-01T00:00:00Z") else { return false }
        return (input.duplicatesUnresolvedTotal ?? input.duplicatesUnresolvedByFacade.values.reduce(0, +)) == 0
    }

    /// Vingerafdruk van alles waarop een handmatige duplicaatcontrole betrekking heeft: meetellende foto's (met gevel en AR-sessie), waarnemingen
    /// (met kozijn en hoeken) en uitsluitingen. Een nieuwe foto, waarneming, koppeling, ontkoppeling, afwijzing of uitsluiting laat de verklaring vervallen.
    static func reviewFingerprint(store: ScanStore) -> String {
        guard let round = store.round else { return "" }
        var parts: [String] = []
        for kf in store.keyframes { parts.append("photo:\(kf.id)|\(round.frameFacade[kf.id] ?? "-")|\(round.frameWorld[kf.id] ?? "-")|\(round.excludedFrames.contains(kf.id) ? "excluded" : "in")") }
        for o in store.observations where !o.rejected {
            let c = o.corners.map { String(format: "%.1f,%.1f", $0.u, $0.v) }.joined(separator: ";")
            parts.append("obs:\(o.id)|\(o.frameId)|\(store.draft(of: o.id)?.id ?? "-")|\(c)")
        }
        return DuplicateCoverage.fingerprint(parts)
    }
}
