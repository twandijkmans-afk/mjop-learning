import SwiftUI

/// Profiel: naam en e-mail, abonnement (beheer op de website), voorkeuren en uitloggen.
struct ProfileView: View {
    @EnvironmentObject var account: Account
    @Environment(\.openURL) private var openURL
    @State private var confirmSignOut = false
    @State private var showKey = false
    @State private var lockOn = BiometricLock.enabled

    /// Aan- of uitzetten vraagt eerst om Face ID, zodat niemand anders het ongemerkt uitzet.
    private func setLock(_ on: Bool) async {
        guard await BiometricLock.authenticate(reason: on ? "Zet openen met \(BiometricLock.name) aan" : "Zet openen met \(BiometricLock.name) uit") else { return }
        BiometricLock.enabled = on
        lockOn = on
    }

    private var initials: String {
        let n = [account.firstName, account.lastName].compactMap { $0?.first.map(String.init) }.joined()
        if !n.isEmpty { return n.uppercased() }
        return (account.session?.email?.first.map(String.init) ?? "?").uppercased()
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Profiel").font(.system(size: 32, weight: .bold)).foregroundStyle(DS.text).padding(.horizontal, 4).padding(.top, 12)
                    HStack(spacing: 14) {
                        Text(initials).font(.title2.weight(.bold)).foregroundStyle(.white)
                            .frame(width: 60, height: 60)
                            .background(LinearGradient(colors: [Color(hex: 0x4D66FF), DS.accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing), in: Circle())
                        VStack(alignment: .leading, spacing: 2) {
                            Text(account.displayName ?? "Je account").font(.title3.weight(.bold)).foregroundStyle(DS.text)
                            Text(account.session?.email ?? "").font(.subheadline).foregroundStyle(DS.text2).accessibilityIdentifier("profileEmail")
                        }
                        Spacer()
                    }
                    .padding(18).dsCard()

                    Button { openURL(Backend.subscribeURL) } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Abonnement").font(.footnote).opacity(0.8)
                                Text("Beheer op de website").font(.headline)
                            }
                            Spacer()
                            Image(systemName: "arrow.up.right").font(.headline)
                        }
                        .foregroundStyle(.white)
                        .padding(16)
                        .background(LinearGradient(colors: [Color(hex: 0x2F4BFF), DS.accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing),
                                    in: RoundedRectangle(cornerRadius: DS.radiusCard, style: .continuous))
                        .shadow(color: DS.accent.opacity(0.3), radius: 14, x: 0, y: 10)
                    }
                    .buttonStyle(.plain)

                    VStack(spacing: 0) {
                        row("bell", "Herinneringen", "Volgt")
                        Divider().padding(.leading, 62)
                        if BiometricLock.available {
                            Toggle(isOn: Binding(get: { lockOn }, set: { v in Task { await setLock(v) } })) {
                                HStack(spacing: 12) {
                                    DSIcon(systemName: BiometricLock.icon)
                                    VStack(alignment: .leading, spacing: 1) {
                                        Text("Openen met \(BiometricLock.name)").foregroundStyle(DS.text)
                                        Text("Bij openen en na 5 minuten weg").font(.caption).foregroundStyle(DS.text2)
                                    }
                                }
                            }
                            .tint(DS.accent)
                            .padding(.horizontal, 16).frame(minHeight: 58)
                            .accessibilityIdentifier("biometricLock")
                        } else {
                            row("faceid", "Face ID", "Niet beschikbaar")
                        }
                        Divider().padding(.leading, 62)
                        row("lock.shield", "Privacy en gegevens", nil)
                        Divider().padding(.leading, 62)
                        Button { showKey = true } label: { row("key", "Claude-sleutel", ClaudeKey.load() == nil ? "Niet ingesteld" : "Ingesteld") }
                            .buttonStyle(DSRowStyle())
                            .accessibilityIdentifier("claudeKey")
                    }
                    .dsCard(radius: 20)

                    Button(role: .destructive) { confirmSignOut = true } label: {
                        Text("Uitloggen").font(.headline).foregroundStyle(DS.bad).frame(maxWidth: .infinity, minHeight: 52)
                    }
                    .dsCard(radius: 20)
                    .accessibilityIdentifier("signOut")

                    Text("MJOP Live \(DeviceCapabilities.appVersion) (build \(DeviceCapabilities.buildNumber))")
                        .font(.caption).foregroundStyle(DS.text2).frame(maxWidth: .infinity).padding(.top, 6)
                }
                .padding(.horizontal, DS.pad).padding(.bottom, 120)
            }
            .background(DS.canvas)
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showKey) { ClaudeKeySheet() }
            .confirmationDialog("Uitloggen?", isPresented: $confirmSignOut, titleVisibility: .visible) {
                Button("Uitloggen", role: .destructive) { Task { await account.signOut() } }
                Button("Annuleren", role: .cancel) {}
            }
        }
    }

    private func row(_ icon: String, _ title: String, _ value: String?) -> some View {
        HStack(spacing: 12) {
            DSIcon(systemName: icon)
            Text(title).foregroundStyle(DS.text)
            Spacer()
            if let value { Text(value).font(.subheadline).foregroundStyle(DS.text2) }
            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(DS.text2.opacity(0.6))
        }
        .padding(.horizontal, 16).frame(minHeight: 54)
    }
}
