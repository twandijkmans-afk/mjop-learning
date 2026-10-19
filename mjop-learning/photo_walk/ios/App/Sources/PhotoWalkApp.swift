import SwiftUI

@main
struct PhotoWalkApp: App {
    @StateObject private var store = ScanStore()
    var body: some Scene {
        WindowGroup {
            NavigationStack { StartScanView().environmentObject(store) }
                .task { runSelfTestIfRequested() }
        }
    }

    /// CI-rooktest (`-selftest`): voert de synthetische simulatie headless uit, schrijft de export naar Documents en logt het pad.
    /// Raakt geen camera en geen netwerk. Zonder dit argument doet de app niets bijzonders.
    @MainActor private func runSelfTestIfRequested() {
        guard CommandLine.arguments.contains("-selftest") else { return }
        let summary = SimulationRunner.run(store)
        let path = (try? ExportService.write(store))?.path ?? "EXPORT_FAILED"
        print("SELFTEST_SUMMARY_BEGIN\n\(summary)\nSELFTEST_SUMMARY_END")
        print("SELFTEST_EXPORT=\(path)")
    }
}
