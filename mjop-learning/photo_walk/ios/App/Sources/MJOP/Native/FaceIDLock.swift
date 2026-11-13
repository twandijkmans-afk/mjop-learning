import LocalAuthentication
import SwiftUI

/// Openen met Face ID (of Touch ID). Standaard aan zodra het toestel het kan; uit te zetten in Profiel.
/// De app vergrendelt bij het opstarten met een bewaarde sessie en na meer dan vijf minuten op de achtergrond.
/// Lukt Face ID niet, dan kan de toegangscode van het toestel; of uitloggen en opnieuw inloggen met het wachtwoord.
enum BiometricLock {
    static let backgroundGrace: TimeInterval = 5 * 60
    private static let key = "mjop.biometricLock"

    static var biometry: LABiometryType {
        let c = LAContext()
        var e: NSError?
        return c.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &e) ? c.biometryType : .none
    }

    static var available: Bool { biometry != .none }

    static var name: String {
        switch biometry {
        case .touchID: return "Touch ID"
        case .opticID: return "Optic ID"
        default: return "Face ID"
        }
    }

    static var icon: String { biometry == .touchID ? "touchid" : "faceid" }

    /// Aan zolang de gebruiker het niet heeft uitgezet en het toestel het kan.
    static var enabled: Bool {
        get { available && (UserDefaults.standard.object(forKey: key) as? Bool ?? true) }
        set { UserDefaults.standard.set(newValue, forKey: key) }
    }

    /// Vraagt Face ID; als dat niet lukt, mag de toegangscode van het toestel.
    static func authenticate(reason: String) async -> Bool {
        let c = LAContext()
        c.localizedCancelTitle = "Annuleer"
        do { return try await c.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason) }
        catch { return false }
    }
}

/// Vergrendelscherm: logo, naam en de knop om te ontgrendelen. Vraagt bij het openen meteen om Face ID.
struct LockScreenView: View {
    @EnvironmentObject var account: Account
    @State private var busy = false
    @State private var failed = false

    var body: some View {
        VStack(spacing: 18) {
            Spacer()
            Text("M").font(.system(size: 40, weight: .bold)).foregroundStyle(.white)
                .frame(width: 84, height: 84)
                .background(LinearGradient(colors: [Color(hex: 0x4D66FF), DS.accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing),
                            in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                .shadow(color: DS.accent.opacity(0.35), radius: 18, x: 0, y: 12)
            VStack(spacing: 4) {
                Text("MJOP Live").font(.title2.weight(.bold)).foregroundStyle(DS.text)
                if let n = account.displayName ?? account.session?.email { Text(n).font(.subheadline).foregroundStyle(DS.text2) }
            }
            Spacer()
            if failed {
                Text("Niet ontgrendeld. Probeer het opnieuw.").font(.footnote).foregroundStyle(DS.text2)
            }
            Button { Task { await unlock() } } label: {
                Label("Ontgrendel met \(BiometricLock.name)", systemImage: BiometricLock.icon)
            }
            .buttonStyle(DSPrimaryButton())
            .disabled(busy)
            .accessibilityIdentifier("unlock")
            Button("Inloggen met wachtwoord") { Task { await account.signOut() } }
                .font(.subheadline.weight(.semibold))
                .padding(.bottom, 24)
        }
        .padding(.horizontal, 28)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(DS.canvas.ignoresSafeArea())
        .task { await unlock() }
    }

    private func unlock() async {
        guard !busy else { return }
        busy = true; defer { busy = false }
        if await BiometricLock.authenticate(reason: "Ontgrendel MJOP Live") { account.unlock() } else { failed = true }
    }
}
