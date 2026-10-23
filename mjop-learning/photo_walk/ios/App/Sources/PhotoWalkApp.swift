import MJOPIntegration
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
        let ov = store.overview(frameId: "F000")
        print("SELFTEST_OVERVIEW detected=\(ov.detected) unique=\(ov.unique) measurable=\(ov.measurable) checks=\(ov.checks) noScale=\(ov.noScale)")
        // 3) lokale opslag: bewaren en terugladen
        Persistence.saveNow(store)
        if let (snap, dir) = Persistence.latestAny() {
            let other = ScanStore()
            Persistence.restore(snap, from: dir, into: other)
            let same = other.observations.count == store.observations.count && other.keyframes.first?.depth?.values.count == store.keyframes.first?.depth?.values.count
                && other.keyframes.first?.depth?.values == store.keyframes.first?.depth?.values
            print("SELFTEST_PERSIST observations=\(other.observations.count) identicalDepth=\(same) results=\(other.results.count)")
        } else { print("SELFTEST_PERSIST none") }
        let path = (try? ExportService.write(store))?.path ?? "EXPORT_FAILED"
        print("SELFTEST_EXPORT=\(path)")
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
