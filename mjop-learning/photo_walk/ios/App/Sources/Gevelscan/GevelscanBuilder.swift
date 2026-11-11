import Foundation
import UIKit
import Gevelscan
import MJOPIntegration
import PhotoWalkCore

/// Zet de scansessie van een fotoronde om naar de invoer van de Gevelscanner 2.0-pijplijn (`Gevelscan.GevelscanPipeline`).
/// Alle regels (koppelen, geometrie, uitkomstklassen, contract) staan in het Swift-package `Gevelscan` en zijn daar getest; hier alleen het
/// verzamelen uit de sessie. De bestaande meting per waarneming (`store.measures`) wordt hergebruikt: er wordt niets opnieuw gemeten.
@MainActor
enum GevelscanBuilder {
    static func iso(_ d: Date) -> String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        return f.string(from: d)
    }

    /// Bewijsrecord van één foto (dieptekwaliteit + gevelvlak). Eenmalig per foto berekend en daarna hergebruikt.
    nonisolated static func capture(view: ViewInput, capturedAt: String) -> PhotoCapture {
        PhotoCapture.from(view: view, facadeId: "", worldId: nil, capturedAt: capturedAt, imageQuality: nil)
    }

    static func input(store: ScanStore) -> GevelscanInput? {
        guard let round = store.round else { return nil }
        let excluded = round.excludedFrames
        var photos: [PhotoCapture] = []
        for kf in store.keyframes {
            var p: PhotoCapture
            if let cached = store.captureCache[kf.id] { p = cached }
            else { p = capture(view: Measurer.input(kf), capturedAt: iso(kf.timestamp)); store.captureCache[kf.id] = p }
            p.facadeId = RoundInputBuilder.facadeId(of: kf.id, in: store)
            p.worldId = round.frameWorld[kf.id]
            p.imageQuality = store.photoQuality[kf.id]
            p.excluded = excluded.contains(kf.id)
            photos.append(p)
        }
        var sightings: [FrameSighting] = []
        for o in store.observations where !o.rejected && !excluded.contains(o.frameId) {
            guard let kf = store.keyframe(o.frameId) else { continue }
            let panes: [ElementDetection] = store.glassPanes(ofObservation: o.id).map { e in
                ElementDetection(id: e.id, photoId: e.frameId, elementClass: .GLASVLAK, polygon: e.corners, score: nil,
                                 detector: e.source == .MANUAL ? DetectorDescriptor.user : DetectorDescriptor.visionCandidates, parentId: o.id)
            }
            var glare: [String: Double] = [:]
            for p in panes { if let g = store.paneGlare[p.id] { glare[p.id] = g } }
            let detector: DetectorDescriptor = o.detection.map { DetectorCatalog.descriptor(for: $0.detector) } ?? DetectorDescriptor.user
            let result: LevelResult? = store.measures[o.id].map { SightingMeasurement.ungated($0.result) }
            sightings.append(FrameSighting(id: o.id, photoId: o.frameId, facadeId: RoundInputBuilder.facadeId(of: o.frameId, in: store), worldId: round.frameWorld[o.frameId],
                                           polygon: o.corners, pose: kf.pose, intrinsics: kf.intrinsics, result: result,
                                           contourUserConfirmed: !o.outerContour.blocksArea, contourStatus: o.outerContour, evidence: o.evidence,
                                           detector: detector, score: o.detection?.score, panes: panes, glareFractionByPane: glare))
        }
        // detecties van een getraind model (alleen als er een model in de app zit): glas, draaiende/vaste delen en raam/deur aan het juiste kozijn hangen
        let modelDetections: [ElementDetection] = store.modelDetections.keys.sorted().filter { !excluded.contains($0) }.flatMap { store.modelDetections[$0] ?? [] }
        if !modelDetections.isEmpty { sightings = PartAssembler.attach(modelDetections, to: sightings).sightings }

        let mustLink: [[String]] = store.drafts.map { $0.observationIds }.filter { $0.count > 1 }
        let cannotLink: [[String]] = store.dismissedLinks.map { $0.split(separator: "|").map(String.init) }.filter { $0.count == 2 }
        let reviewed: Bool = round.duplicateReview.map { $0.fingerprint == RoundInputBuilder.reviewFingerprint(store: store) } ?? false
        return GevelscanInput(roundId: store.sessionId, facades: round.facades.map { GevelscanInput.Facade(id: $0.id, orientation: $0.orientation) }, photos: photos, sightings: sightings,
                              constraints: AssociationConstraints(mustLink: mustLink, cannotLink: cannotLink), userReviewedAllDuplicates: reviewed,
                              userParts: store.userParts, userClasses: store.userClasses, detectors: DetectorCatalog.descriptors(), conditionDetector: nil, defectDetections: [],
                              validation: PipelineValidation.current)
    }

    /// Gevelinventaris (`mjop_gevel_inventory_v1`) van de huidige ronde. nil = geen ronde, of de inventaris voldeed niet aan het contract
    /// (dan gaat er niets de deur uit; de bestaande v2-voorstellen blijven gewoon werken).
    static func contract(store: ScanStore, createdAt: String) -> (inventory: GevelInventoryV1, result: GevelscanResult)? {
        guard let round = store.round, let input = input(store: store) else { return nil }
        let result = GevelscanPipeline.run(input)
        let ctx = round.context
        let project = ScanProposalV2.Project(planRef: ctx.planRef, mjopPlanId: ctx.mjopPlanId, buildingId: ctx.buildingLabel, bagPandId: ctx.bagPandId)
        guard let inv = try? InventoryContractBuilder.build(result: result, photos: input.photos, project: project, elementKey: ctx.element?.key, revision: round.revision, createdAt: createdAt) else { return nil }
        return (inv, result)
    }
}

extension ScanStore {
    /// Draait de pijplijn op de achtergrond en publiceert het resultaat. Meerdere aanvragen tegelijk worden samengevoegd tot één extra ronde,
    /// zodat een reeks foto's het toestel niet onnodig belast.
    func runGevelscan() async {
        guard round != nil else { gevelscan = nil; return }
        if gevelscanRunning { gevelscanPending = true; return }
        gevelscanRunning = true
        repeat {
            gevelscanPending = false
            // 1. bewijsrecords van nieuwe foto's buiten de hoofdthread (dieptekwaliteit en gevelvlak)
            let missing: [(String, ViewInput, String)] = keyframes.filter { captureCache[$0.id] == nil }.map { ($0.id, Measurer.input($0), GevelscanBuilder.iso($0.timestamp)) }
            if !missing.isEmpty {
                let made: [(String, PhotoCapture)] = await Task.detached(priority: .utility) { () -> [(String, PhotoCapture)] in missing.map { ($0.0, GevelscanBuilder.capture(view: $0.1, capturedAt: $0.2)) } }.value
                for (id, p) in made { captureCache[id] = p }
            }
            // 2. de pijplijn zelf (zuivere functie op waarden)
            guard let input = GevelscanBuilder.input(store: self) else { break }
            let result: GevelscanResult = await Task.detached(priority: .utility) { () -> GevelscanResult in GevelscanPipeline.run(input) }.value
            gevelscan = result
        } while gevelscanPending
        gevelscanRunning = false
    }

    /// Beeldkwaliteit van een foto, spiegeling per glasvlak en (als er een model in de app zit) modeldetecties. Lokaal; de foto verlaat het toestel niet.
    func measureImageQuality(frameId: String) async {
        guard let kf = keyframe(frameId), let url = kf.imageURL else { return }
        let panes: [(String, [Pixel])] = glassPanes(frameId: frameId).map { ($0.id, $0.corners) }
        let model = CoreMLElementDetector()
        let out: (ImageQuality?, [String: Double], [ElementDetection]) = await Task.detached(priority: .utility) { () -> (ImageQuality?, [String: Double], [ElementDetection]) in
            guard let cg = UIImage(contentsOfFile: url.path)?.cgImage, let gray = GrayImageLoader.gray(cg) else { return (nil, [:], []) }
            var glare: [String: Double] = [:]
            for (id, c) in panes { if let g = ImageQualityMeter.glareFraction(gray, polygon: c) { glare[id] = g } }
            return (ImageQualityMeter.measure(gray), glare, model?.detect(cg, photoId: frameId) ?? [])
        }.value
        if let q = out.0 { photoQuality[frameId] = q }
        for (k, v) in out.1 { paneGlare[k] = v }
        if !out.2.isEmpty { modelDetections[frameId] = out.2 }
    }
}
