import SwiftUI

@main
struct PhotoWalkApp: App {
    @StateObject private var store = ScanStore()
    var body: some Scene {
        WindowGroup {
            NavigationStack { StartScanView().environmentObject(store) }
        }
    }
}
