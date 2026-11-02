import MJOPIntegration
import PhotoWalkCore
import SwiftUI

@main
struct PhotoWalkApp: App {
    @StateObject private var store = ScanStore()
    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(store)
                .task { await runSelfTestIfRequested() }
        }
    }

    /// CI-rooktest (`-selftest`): voert de synthetische simulatie headless uit, schrijft de export naar Documents en logt het pad.
    /// Raakt geen camera en geen netwerk. Zonder dit argument doet de app niets bijzonders.
    /// Oude sessie (van vóór de gevelopbouw) nabootsen door de nieuwe velden uit het opgeslagen JSON te halen: moet leesbaar blijven, LEGACY worden
    /// en zich gedragen als vroeger (geen contourpoort). De export daarvan moet aan het schema voldoen.
    @MainActor private func selfTestLegacy(_ snap: SessionSnapshot, dir: URL) {
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        guard let data = try? enc.encode(snap), var obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { print("SELFTEST_LEGACY decoded=false"); return }
        obj["facadeElements"] = nil
        if var obs = obj["observations"] as? [[String: Any]] {
            for i in obs.indices { obs[i]["outerContour"] = nil; obs[i]["evidence"] = nil; obs[i]["proposedOuter"] = nil }
            obj["observations"] = obs
        }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        guard let legacyData = try? JSONSerialization.data(withJSONObject: obj), let legacy = try? dec.decode(SessionSnapshot.self, from: legacyData) else {
            print("SELFTEST_LEGACY decoded=false"); return
        }
        let ls = ScanStore()
        Persistence.restore(legacy, from: dir, into: ls)
        let allLegacy = ls.observations.allSatisfy { $0.outerContour == .LEGACY && $0.evidence == .LEGACY }
        let noGate = ls.observations.allSatisfy { o in !(ls.measures[o.id]?.result.flags.contains { $0.code == "OUTER_CONTOUR_UNVERIFIED" } ?? false) }
        print("SELFTEST_LEGACY decoded=true observations=\(ls.observations.count) allLegacy=\(allLegacy) noGate=\(noGate) elements=\(ls.facadeElements.count)")
        if let out = try? JSONSerialization.data(withJSONObject: ExportService.record(ls), options: [.sortedKeys, .prettyPrinted]),
           let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            try? out.write(to: docs.appendingPathComponent("legacy_selftest_export.json"))
        }
    }

    /// Selftest issue D: één hoek 1 px verschuiven bevestigt niets; "Herstel detectie" + "Toepassen" ook niet; alleen "Dit is de buitenmaat".
    /// Controleert ook dat er tussendoor geen maat, exportwaarde, aantal of oppervlakvoorstel uit de bewerkte contour komt.
    @MainActor private func selfTestCornerEdit() {
        guard let o = store.observations.first(where: { !$0.rejected && $0.detection != nil && $0.outerContour.blocksArea }) else {
            print("SELFTEST_CORNER_EDIT skipped=no-unconfirmed-detection"); return
        }
        let id = o.id
        func draftId() -> String? { store.draft(of: id)?.id }
        func objectArea() -> String { draftId().flatMap { d in store.results.first { $0.id == d } }.map { $0.areaM2 ?? "null" } ?? "none" }
        func exportArea() -> String {
            let objs = (ExportService.record(store)["objects"] as? [[String: Any]]) ?? []
            let mine = objs.first { (($0["observation_refs"] as? [String]) ?? []).contains(id) }
            guard let mine else { return "none" }
            if let a = mine["gross_area_m2"] as? String { return a }
            return mine["gross_area_m2"] is NSNull ? "null" : "?"
        }
        func exportContour() -> String {
            let obs = (ExportService.record(store)["observations"] as? [[String: Any]]) ?? []
            return ((obs.first { ($0["observation_id"] as? String) == id }?["facade_role"] as? [String: Any])?["outer_contour_status"] as? String) ?? "none"
        }
        func proposals() -> String {
            store.round = RoundState(context: PhotoRoundContext(planRef: "plan-selftest0003", mjopPlanId: nil, buildingLabel: "Selftestgebouw", bagPandId: nil, mode: .round,
                                                               element: nil, plannedFacades: []), facades: [.init(id: "Voorgevel", orientation: "S")])
            defer { store.round = nil }
            guard let input = RoundInputBuilder.build(store: store, createdAt: RoundCoordinator.isoNow()) else { return "none" }
            let ps = RoundProposalBuilder.build(input)
            func v(_ k: ScanProposalV2.Target.Kind) -> String { ps.first { $0.target.quantityKind == k && $0.target.scope.type == .BUILDING }.map { $0.value.map { String($0) } ?? "null" } ?? "none" }
            let mineUnconfirmed = input.objects.first { $0.id == draftId() }.map { $0.contourUnconfirmed } ?? false
            return "count=\(v(.FRAME_COUNT)) area=\(v(.FRAME_AREA_GROSS)) objectUnconfirmed=\(mineUnconfirmed) valid=\(ps.allSatisfy { $0.validate().isEmpty })"
        }
        let before = o.corners
        // 1) één hoek 1 pixel
        store.correctCorner(observation: id, index: 0, to: Pixel(before[0].u + 1, before[0].v), reason: "selftest: 1 pixel")
        store.measureAll()
        guard let e = store.observation(id), let m = store.measures[id] else { print("SELFTEST_CORNER_EDIT lost"); return }
        let showsConfirm = OuterContourStatus.showsConfirmAction(status: e.outerContour, autoDetectedUnconfirmed: e.source == .AUTO_DETECTED_UNCONFIRMED)
        print("SELFTEST_CORNER_EDIT step=edit contour=\(e.outerContour.rawValue) source=\(e.source.rawValue) measurementOk=\(m.result.ok) gate=\(m.result.flags.contains { $0.code == "OUTER_CONTOUR_UNVERIFIED" }) confirmVisible=\(showsConfirm) objectArea=\(objectArea()) exportArea=\(exportArea()) exportContour=\(exportContour()) \(proposals())")
        // 2) "Herstel detectie" + "Toepassen": dezelfde lus als PhotoResultView.apply (alleen gewijzigde hoeken)
        let detected = e.originalCorners
        for i in 0..<4 where detected[i] != e.corners[i] { store.correctCorner(observation: id, index: i, to: detected[i], reason: "selftest: herstel detectie + toepassen") }
        store.measureAll()
        guard let r = store.observation(id), let mr = store.measures[id] else { return }
        print("SELFTEST_CORNER_EDIT step=restore contour=\(r.outerContour.rawValue) restored=\(r.corners == r.originalCorners) revisions=\(r.revisions.count) measurementOk=\(mr.result.ok) confirmVisible=\(OuterContourStatus.showsConfirmAction(status: r.outerContour, autoDetectedUnconfirmed: r.source == .AUTO_DETECTED_UNCONFIRMED)) objectArea=\(objectArea()) exportArea=\(exportArea()) \(proposals())")
        // 3) pas nu expliciet bevestigen: alleen de contourpoort gaat open; schaal, standpunten en overige regels blijven gelden
        store.confirmCorners(observation: id)
        store.measureAll()
        guard let c = store.observation(id), let mc = store.measures[id] else { return }
        let status = draftId().flatMap { d in store.results.first { $0.id == d } }?.status.rawValue ?? "none"
        print("SELFTEST_CORNER_EDIT step=confirm contour=\(c.outerContour.rawValue) source=\(c.source.rawValue) revisions=\(c.revisions.count) gate=\(mc.result.flags.contains { $0.code == "OUTER_CONTOUR_UNVERIFIED" }) measurementOk=\(mc.result.ok) status=\(status) exportContour=\(exportContour())")
    }

    /// Selftest duplicaatcontrole via RoundInputBuilder + RoundProposalBuilder (dezelfde code als de fotoronde) op een aparte sessie met twee foto's
    /// van HETZELFDE kozijn: foto F001 heeft geen diepte (dus geen ruimtelijke meting). Er is geen enkele koppelsuggestie, en toch mag er geen
    /// aantal of oppervlak komen tot de inspecteur alles heeft nagelopen; een wijziging laat die verklaring vervallen.
    @MainActor private func selfTestDuplicateCoverage() {
        // bronkader: een waarneming waarvan de meting zelf lukte (vóór de contourpoort: indicatieve maat aanwezig), zodat F000 een ruimtelijke meting heeft
        let measurable = store.observations.first { o in
            guard !o.rejected, let m = store.measures[o.id] else { return false }
            return m.result.ok || ContourGate.indicativeDims(m.result) != nil
        }
        guard let k0 = store.keyframe("F000"), let src = measurable ?? store.observations.first(where: { !$0.rejected }) else { print("SELFTEST_DUP_COVERAGE skipped"); return }
        let dc = ScanStore()
        dc.isSimulation = true; dc.facadeId = "Voorgevel"
        let k1 = Keyframe(id: "F001", timestamp: k0.timestamp, intrinsics: k0.intrinsics, pose: k0.pose, trackingState: k0.trackingState, depth: nil, imageURL: k0.imageURL)
        dc.keyframes = [k0, k1]
        for f in ["F000", "F001"] {
            dc.addObservation(Observation(id: "OBS-\(f)-1", frameId: f, corners: src.corners, originalCorners: src.corners, source: .MANUAL), to: nil)
        }
        dc.round = RoundState(context: PhotoRoundContext(planRef: "plan-selftest0004", mjopPlanId: nil, buildingLabel: "Selftestgebouw", bagPandId: nil, mode: .round,
                                                        element: nil, plannedFacades: []), facades: [.init(id: "Voorgevel", orientation: "S")])
        dc.round?.frameFacade = ["F000": "Voorgevel", "F001": "Voorgevel"]
        dc.measureAll()
        func line(_ step: String) {
            guard let input = RoundInputBuilder.build(store: dc, createdAt: RoundCoordinator.isoNow()) else { print("SELFTEST_DUP_COVERAGE step=\(step) noinput"); return }
            let ps = RoundProposalBuilder.build(input)
            guard let c = ps.first(where: { $0.target.quantityKind == .FRAME_COUNT && $0.target.scope.type == .BUILDING }),
                  let a = ps.first(where: { $0.target.quantityKind == .FRAME_AREA_GROSS && $0.target.scope.type == .BUILDING }) else { return }
            let reasons = c.reliability.reasons.filter { $0 != "UNVALIDATED_LIDAR" }.joined(separator: ",")
            print("SELFTEST_DUP_COVERAGE step=\(step) suggestions=\(dc.linkSuggestions().count) objects=\(input.objects.count) checkable=\(input.objects.filter { $0.duplicateCheckable }.count) count=\(c.value.map { String($0) } ?? "null") area=\(a.value.map { String($0) } ?? "null") partial=\(a.partialValue.map { String($0) } ?? "null") level=\(c.reliability.level) complete=\(c.basis.duplicateReviewComplete.map { String($0) } ?? "nil") manual=\(c.basis.duplicateReviewManual.map { String($0) } ?? "nil") unchecked=\(c.basis.duplicateCheckUncheckedObjects ?? -1) unknownWorld=\(c.basis.duplicateCheckUnknownWorldPhotos ?? -1) cross=\(c.basis.crossSessionUnchecked) reasons=\(reasons.isEmpty ? "-" : reasons) valid=\(ps.allSatisfy { $0.validate().isEmpty })")
        }
        line("no-world")                                                  // geen AR-sessie bekend (simulatie)
        dc.round?.frameWorld = ["F000": "w-a", "F001": "w-b"]
        line("two-worlds")                                                // twee scanmomenten
        dc.round?.duplicateReview = DuplicateReview(reviewedAt: Date(), fingerprint: RoundInputBuilder.reviewFingerprint(store: dc))
        line("reviewed")                                                  // inspecteur heeft alles nagelopen
        dc.round?.frameWorld["F001"] = "w-c"
        line("stale")                                                     // iets gewijzigd: verklaring vervalt
    }

    /// Selftest hoekkiezer (ScanStore.addPickedQuad, dezelfde functie als de knop Opslaan) op een aparte sessie.
    @MainActor private func selfTestPickedQuad() {
        let pq = ScanStore()
        let cand = [Pixel(200, 150), Pixel(420, 150), Pixel(420, 450), Pixel(200, 450)]
        var moved = cand; moved[1] = Pixel(421, 150)
        for (name, corners, candidate) in [("self_drawn", cand, nil as [Pixel]?), ("candidate_unchanged", cand, cand), ("candidate_moved", moved, cand)] {
            let o = pq.addPickedQuad(frameId: "F000", corners: corners, candidate: candidate, candidateScore: candidate == nil ? nil : 0.8, to: nil)
            print("SELFTEST_PICKED name=\(name) source=\(o.source.rawValue) contour=\(o.outerContour.rawValue) originalIsCandidate=\(candidate.map { o.originalCorners == $0 } ?? false) cornersKept=\(o.corners == corners) revisions=\(o.revisions.count) detector=\(o.detection?.detector ?? "none")")
        }
    }

    @MainActor private func runSelfTestIfRequested() async {
        guard CommandLine.arguments.contains("-selftest") else { return }
        // 1) legacy: handmatige hoeken
        let summary = SimulationRunner.run(store)
        print("SELFTEST_SUMMARY_BEGIN\n\(summary)\nSELFTEST_SUMMARY_END")
        // 2) foto -> automatische detectie -> meting (lokaal, Apple Vision op de synthetische foto)
        SimulationRunner.runPhoto(store)
        let t0 = Date()
        await store.analyze(frameId: "F000")
        print("SELFTEST_TIMING analyze_seconds=\(String(format: "%.1f", Date().timeIntervalSince(t0)))")
        let boxes = store.observations.filter { $0.detection != nil && !$0.rejected }
        for o in boxes {
            let m = store.measures[o.id]
            let dims = m.map { PhotoResultView.dimsText($0.result) } ?? "?"
            print("SELFTEST_DETECT \(o.id) detector=\(o.detection?.detector ?? "") feedback=\(m?.feedback.rawValue ?? "?") \(dims) flags=\(m?.result.flags.map { $0.code }.joined(separator: ",") ?? "")")
        }
        for o in store.observations where !o.rejected {
            let m = store.measures[o.id]
            print("SELFTEST_ROLE \(o.id) contour=\(o.outerContour.rawValue) evidence=\(o.evidence.rawValue) panes=\(store.glassPanes(ofObservation: o.id).count) proposal=\(o.proposedOuter != nil) \(m.map { PhotoResultView.dimsText($0.result) } ?? "?")")
        }
        if let n = store.analysisNotes["F000"] { print("SELFTEST_NOTE \(n)") }
        let ov = store.overview(frameId: "F000")
        print("SELFTEST_OVERVIEW detected=\(ov.detected) unique=\(ov.unique) measurable=\(ov.measurable) checks=\(ov.checks) noScale=\(ov.noScale) outerUnverified=\(ov.outerUnverified) glassPanes=\(ov.glassPanes)")
        // 2b) opnieuw zoeken op dezelfde foto mag geen kozijnen, glasvlakken of afgewezen kandidaten dubbel/terug toevoegen
        let obsBefore = store.observations.count, elemBefore = store.facadeElements.count
        await store.analyze(frameId: "F000")
        print("SELFTEST_REANALYZE added=\(store.observations.count - obsBefore) glassAdded=\(store.facadeElements.count - elemBefore)")
        // 3) lokale opslag: bewaren en terugladen
        Persistence.saveNow(store)
        if let (snap, dir) = Persistence.latestAny() {
            let other = ScanStore()
            Persistence.restore(snap, from: dir, into: other)
            let same = other.observations.count == store.observations.count && other.keyframes.first?.depth?.values.count == store.keyframes.first?.depth?.values.count
                && other.keyframes.first?.depth?.values == store.keyframes.first?.depth?.values
            print("SELFTEST_PERSIST observations=\(other.observations.count) identicalDepth=\(same) results=\(other.results.count)")
            let sameRoles = other.observations.map { "\($0.id)|\($0.outerContour.rawValue)|\($0.evidence.rawValue)" } == store.observations.map { "\($0.id)|\($0.outerContour.rawValue)|\($0.evidence.rawValue)" }
                && other.facadeElements == store.facadeElements
            print("SELFTEST_PERSIST_FACADE identical=\(sameRoles) elements=\(other.facadeElements.count)")
            selfTestLegacy(snap, dir: dir)
        } else { print("SELFTEST_PERSIST none") }
        let path = (try? ExportService.write(store))?.path ?? "EXPORT_FAILED"
        print("SELFTEST_EXPORT=\(path)")
        // 3a) MJOP-voorstellen uit de ONBEVESTIGDE automatische toestand: geen aantal en geen oppervlak mogen er doorheen glippen
        store.round = RoundState(context: PhotoRoundContext(planRef: "plan-selftest0002", mjopPlanId: nil, buildingLabel: "Selftestgebouw", bagPandId: nil, mode: .round,
                                                           element: nil, plannedFacades: []), facades: [.init(id: "Voorgevel", orientation: "S")])
        if let input = RoundInputBuilder.build(store: store, createdAt: RoundCoordinator.isoNow()) {
            let ps = RoundProposalBuilder.build(input)
            if let data = try? JSONSerialization.data(withJSONObject: ps.compactMap { $0.jsonObject() }, options: [.sortedKeys]),
               let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
                try? data.write(to: docs.appendingPathComponent("mjop_round_proposals_unconfirmed.json"))
            }
            print("SELFTEST_ROUND_UNCONFIRMED proposals=\(ps.count) valid=\(ps.allSatisfy { $0.validate().isEmpty }) values=\(ps.map { $0.value.map { String($0) } ?? "null" }.joined(separator: ","))")
        }
        store.round = nil
        // 3a2) hoek verslepen is BEWERKEN, geen bevestiging (issue D): 1 pixel verschuiven, daarna "Herstel detectie" + "Toepassen", daarna pas
        //      expliciet "Dit is de buitenmaat". Via dezelfde ScanStore-functies als de knoppen; de hoeken komen terug op de detectie.
        selfTestCornerEdit()
        // 3a3) duplicaatcontrole: nul suggesties is geen bewijs; aparte sessie zodat de rest van de selftest ongewijzigd blijft
        selfTestDuplicateCoverage()
        // 3a4) hoekkiezer: een gekozen voorstel blijft een voorstel, ook na het verschuiven van een hoek (aparte sessie)
        selfTestPickedQuad()
        // 3b) gevelopbouw: gesimuleerde gebruiker bevestigt onbevestigde buitencontouren en tekent het gevelvlak (NA de export hierboven,
        //     die dus de automatische, onbevestigde toestand bevat). Toont dat er pas na bevestiging een kozijnmaat komt.
        for o in store.observations where !o.rejected && o.outerContour.blocksArea {
            let before = store.measures[o.id].map { PhotoResultView.dimsText($0.result) } ?? "?"
            store.confirmCorners(observation: o.id)
            store.measureAll()
            print("SELFTEST_CONFIRM \(o.id) before=\(before) after=\(store.measures[o.id].map { PhotoResultView.dimsText($0.result) } ?? "?")")
        }
        for o in store.observations where !o.rejected {
            if let r = store.measures[o.id]?.result, r.ok, let w = r.width, let h = r.height {
                print("SELFTEST_AFTER_CONFIRM \(o.id) contour=\(o.outerContour.rawValue) w=\(String(format: "%.4f", w)) h=\(String(format: "%.4f", h))")
            }
        }
        if let kf = store.keyframe("F000") {
            let W = Double(kf.intrinsics.width), H = Double(kf.intrinsics.height)
            store.setFacadePolygon(frameId: "F000", corners: [Pixel(W * 0.05, H * 0.05), Pixel(W * 0.95, H * 0.05), Pixel(W * 0.95, H * 0.95), Pixel(W * 0.05, H * 0.95)])
            if let fc = store.facadeComposition(frameId: "F000") {
                let q = fc.result
                func t(_ x: FacadeQuantity) -> String { "\(x.valueM2.map { decimalString($0) } ?? "null")/\(x.status.rawValue)" }
                print("SELFTEST_FACADE plane=\(fc.planeSource.rawValue) gross=\(t(q.facadeGross)) frame=\(t(q.frameOuter)) glass=\(t(q.glass)) net=\(t(q.closedFacadeNet)) maintainable=\(t(q.maintainableFrameSurface)) flags=\(q.flags.joined(separator: ","))")
            }
            // aparte bestandsnaam: de eerste export (automatisch, onbevestigd) blijft ongewijzigd voor de CI-controles
            if let data = try? JSONSerialization.data(withJSONObject: ExportService.record(store), options: [.sortedKeys, .prettyPrinted]),
               let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
                let u = docs.appendingPathComponent("facade_selftest_export.json")
                try? data.write(to: u)
                print("SELFTEST_EXPORT_FACADE=\(u.path)")
            }
            // 3c) handmatige correctie, opslaan, sluiten en herstellen: hoeken, originele hoeken, revisies, contourstatus, glasvlakken en maten identiek
            if let o = store.observations.first(where: { !$0.rejected && store.measures[$0.id]?.result.ok == true }) {
                store.correctCorner(observation: o.id, index: 0, to: Pixel(o.corners[0].u + 1, o.corners[0].v + 1), reason: "selftest: handmatige correctie")
                store.measureAll()
            }
            Persistence.saveNow(store)
            if let (snap2, dir2) = Persistence.latestAny() {
                let back = ScanStore()
                Persistence.restore(snap2, from: dir2, into: back)
                func sig(_ s: ScanStore) -> [String] {
                    s.observations.map { o in "\(o.id)|\(o.corners)|\(o.originalCorners)|\(o.revisions.count)|\(o.source.rawValue)|\(o.outerContour.rawValue)|\(o.rejected)|" +
                        (s.measures[o.id].map { PhotoResultView.dimsText($0.result) } ?? "?") }
                }
                let same = sig(back) == sig(store) && back.facadeElements == store.facadeElements
                print("SELFTEST_PERSIST_AFTER_EDIT identical=\(same) revisions=\(back.observations.map { $0.revisions.count }.reduce(0, +)) contours=\(back.observations.map { $0.outerContour.rawValue }.joined(separator: ","))")
            }
        }
        // 4) LiDAR v2: synthetische scènes met meerdere dieptekaders; diagnose-export per scène
        let t1 = Date()
        for name in ["flush", "recessed_8cm", "recessed_8cm_multi_frame", "ambiguous_planes"] {
            guard let line = SimulationRunner.runV2(store, name: name) else { print("SELFTEST_V2 name=\(name) NIET GELADEN"); continue }
            print("SELFTEST_V2 \(line)")
            if let oid = store.observations.first?.id, let u = try? DiagnosticsExport.write(store, observationId: oid) { print("SELFTEST_DIAG name=\(name) path=\(u.path)") }
        }
        // 5) MJOP-scanvoorstel (contract mjop_scan_proposal_v1): Swift-codering naar Documents; CI valideert tegen het JSON-schema
        let proposal = ScanProposal(
            proposalId: "prop-selftest-0001", createdAt: "2026-10-20T10:00:00Z",
            project: .init(mjopPlanId: nil, buildingId: store.buildingId.isEmpty ? "BLD-SELFTEST" : store.buildingId, facadeId: store.facadeId.isEmpty ? "FACADE-SELFTEST" : store.facadeId, bagPandId: nil),
            element: .init(type: .FRAME, mjopElementKey: nil),
            quantity: .init(unit: .m2, value: 1.8, widthM: 1.2, heightM: 1.5),
            measurement: .init(method: .LIDAR_DEPTH_MULTI_FRAME, dimensionStatus: .ESTIMATED,
                               uncertainty: .init(validated: false, areaSigmaM2: nil, note: "PROVISIONAL_UNVALIDATED")),
            evidence: .init(sourcePhotoId: "F000", provisionalObjectId: "PROV-0001", qualityFlags: ["AUTO_DETECTED_UNCONFIRMED"]))
        if let data = try? proposal.encode(), let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            try? data.write(to: docs.appendingPathComponent("mjop_scan_proposal_selftest.json"))
            print("SELFTEST_PROPOSAL ok=\(((try? ScanProposal.decode(data)) != nil))")
        }
        // 6) Fotoronde-voorstellen (mjop_scan_proposal_v2) uit de huidige sessie; CI valideert ze tegen het JSON-schema
        store.round = RoundState(context: PhotoRoundContext(planRef: "plan-selftest0001", mjopPlanId: nil, buildingLabel: "Selftestgebouw", bagPandId: nil, mode: .round,
                                                           element: nil, plannedFacades: []), facades: [.init(id: "Voorgevel", orientation: "S")])
        store.measureAll()
        if let input = RoundInputBuilder.build(store: store, createdAt: RoundCoordinator.isoNow()) {
            let ps = RoundProposalBuilder.build(input)
            let objs = ps.compactMap { $0.jsonObject() }
            if let data = try? JSONSerialization.data(withJSONObject: objs, options: [.sortedKeys]), let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
                try? data.write(to: docs.appendingPathComponent("mjop_round_proposals_selftest.json"))
                print("SELFTEST_ROUND proposals=\(ps.count) valid=\(ps.allSatisfy { $0.validate().isEmpty })")
            }
        }
        print("SELFTEST_TIMING v2_seconds=\(String(format: "%.1f", Date().timeIntervalSince(t1)))")
        print("SELFTEST_DONE")
    }
}
