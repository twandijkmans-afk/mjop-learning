import SwiftUI

@main
struct PhotoWalkApp: App {
    @StateObject private var store = ScanStore()
    var body: some Scene {
        WindowGroup {
            NavigationStack { StartScanView().environmentObject(store) }
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
        await store.analyze(frameId: "F000")
        let boxes = store.observations.filter { $0.detection != nil && !$0.rejected }
        for o in boxes {
            let m = store.measures[o.id]
            let dims = m.map { PhotoResultView.dimsText($0.result) } ?? "?"
            print("SELFTEST_DETECT \(o.id) detector=\(o.detection?.detector ?? "") feedback=\(m?.feedback.rawValue ?? "?") \(dims)")
        }
        let ov = store.overview(frameId: "F000")
        print("SELFTEST_OVERVIEW detected=\(ov.detected) unique=\(ov.unique) measurable=\(ov.measurable) checks=\(ov.checks) noScale=\(ov.noScale)")
        // 3) lokale opslag: bewaren en terugladen
        Persistence.save(store)
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        if let (snap, dir) = Persistence.latestAny() {
            let other = ScanStore()
            Persistence.restore(snap, from: dir, into: other)
            let same = other.observations.count == store.observations.count && other.keyframes.first?.depth?.values.count == store.keyframes.first?.depth?.values.count
                && other.keyframes.first?.depth?.values == store.keyframes.first?.depth?.values
            print("SELFTEST_PERSIST observations=\(other.observations.count) identicalDepth=\(same) results=\(other.results.count)")
        } else { print("SELFTEST_PERSIST none") }
        let path = (try? ExportService.write(store))?.path ?? "EXPORT_FAILED"
        print("SELFTEST_EXPORT=\(path)")
    }
}
