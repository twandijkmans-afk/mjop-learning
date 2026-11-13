import SwiftUI

/// Startscherm: inloggen met hetzelfde account als de website. Apple en Google staan er al; die werken zodra ze in Supabase zijn ingesteld.
/// Onderaan de verwijzing naar de website voor een abonnement (in de app wordt niets verkocht).
struct LoginView: View {
    @EnvironmentObject var account: Account
    @State private var email = ""
    @State private var password = ""
    @State private var showPassword = false
    @State private var mode: Mode = .signIn
    @State private var busy = false
    @State private var error: String?
    @State private var providerNote = false
    @FocusState private var focus: FocusField?
    @Environment(\.openURL) private var openURL

    enum Mode { case signIn, signUp, reset }
    enum FocusField { case email, password }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                hero
                VStack(spacing: 10) {
                    if let info = account.info { DSNotice(kind: .info, text: info) }
                    if let error { DSNotice(kind: .bad, text: error).accessibilityIdentifier("loginError") }
                    DSField(icon: "envelope") {
                        TextField("E-mailadres", text: $email)
                            .textContentType(.username).keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .focused($focus, equals: .email).submitLabel(.next)
                            .onSubmit { focus = .password }
                            .accessibilityIdentifier("loginEmail")
                    }
                    if mode != .reset {
                        DSField(icon: "lock") {
                            Group {
                                if showPassword { TextField("Wachtwoord", text: $password) }
                                else { SecureField("Wachtwoord", text: $password) }
                            }
                            .textContentType(mode == .signUp ? .newPassword : .password)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                            .focused($focus, equals: .password).submitLabel(.go)
                            .onSubmit { Task { await submit() } }
                            .accessibilityIdentifier("loginPassword")
                            Button { showPassword.toggle() } label: { Image(systemName: showPassword ? "eye.slash" : "eye").foregroundStyle(DS.text2) }
                                .accessibilityLabel(showPassword ? "Wachtwoord verbergen" : "Wachtwoord tonen")
                        }
                    }
                    if mode == .signIn {
                        HStack {
                            Spacer()
                            Button("Wachtwoord vergeten?") { switchTo(.reset) }.font(.subheadline.weight(.semibold))
                        }
                    }
                    Button { Task { await submit() } } label: {
                        if busy { ProgressView().tint(.white) } else { Text(primaryTitle) }
                    }
                    .buttonStyle(DSPrimaryButton())
                    .disabled(busy || !canSubmit)
                    .accessibilityIdentifier("loginSubmit")
                    .padding(.top, 4)

                    if mode == .signIn {
                        HStack(spacing: 10) {
                            Rectangle().fill(DS.line).frame(height: 1)
                            Text("of").font(.footnote).foregroundStyle(DS.text2)
                            Rectangle().fill(DS.line).frame(height: 1)
                        }
                        .padding(.vertical, 6)
                        Button { providerNote = true } label: { Label("Doorgaan met Apple", systemImage: "apple.logo") }
                            .buttonStyle(DSOutlineButton(filledDark: true))
                        Button { Task { await google() } } label: {
                            HStack(spacing: 10) { Text("G").font(.headline.weight(.heavy)).foregroundStyle(Color(hex: 0x4285F4)); Text("Doorgaan met Google") }
                        }
                        .buttonStyle(DSOutlineButton())
                        .disabled(busy)
                        .accessibilityIdentifier("googleSignIn")
                    }

                    Button(switchTitle) { switchTo(mode == .signIn ? .signUp : .signIn) }
                        .font(.subheadline.weight(.semibold)).padding(.top, 8)
                }
                .padding(.horizontal, 20)

                VStack(spacing: 2) {
                    Text("Nog geen abonnement?").foregroundStyle(DS.text2)
                    Button { openURL(Backend.subscribeURL) } label: { Text("Bekijk de mogelijkheden op de website ↗").fontWeight(.semibold) }
                }
                .font(.footnote)
                .frame(maxWidth: .infinity)
                .padding(.top, 26).padding(.bottom, 30)
            }
        }
        .scrollDismissesKeyboard(.interactively)
        .background(DS.canvas.ignoresSafeArea())
        .ignoresSafeArea(edges: .top)
        .alert("Nog niet beschikbaar", isPresented: $providerNote) {
            Button("OK", role: .cancel) {}
        } message: {
            Text("Inloggen met Apple komt later (daarvoor is een betaald Apple Developer-account nodig). Log in met je e-mailadres of met Google.")
        }
    }

    private var hero: some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(colors: [Color(hex: 0x5D86C9), Color(hex: 0xC9DBF2)], startPoint: .top, endPoint: .bottom)
            Image(systemName: "building.2.fill")
                .font(.system(size: 210))
                .foregroundStyle(.white.opacity(0.35))
                .offset(x: 150, y: 10)
                .accessibilityHidden(true)
            LinearGradient(colors: [DS.canvas.opacity(0), DS.canvas], startPoint: .center, endPoint: .bottom)
            VStack(alignment: .leading, spacing: 8) {
                DSLogo()
                Text("MJOP Live").font(.system(size: 34, weight: .bold)).foregroundStyle(DS.text)
                Text(heroSubtitle).font(.body).foregroundStyle(DS.text2)
            }
            .padding(.horizontal, 24).padding(.bottom, 18)
        }
        .frame(height: 340)
        .clipped()
    }

    private var heroSubtitle: String {
        switch mode {
        case .signIn: return "Onderhoud, helder in beeld."
        case .signUp: return "Maak een account. Hetzelfde account werkt ook op de website."
        case .reset: return "We sturen je een link om een nieuw wachtwoord te kiezen."
        }
    }
    private var primaryTitle: String {
        switch mode { case .signIn: return "Inloggen"; case .signUp: return "Account maken"; case .reset: return "Stuur link" }
    }
    private var switchTitle: String { mode == .signIn ? "Nog geen account? Maak er een" : "Terug naar inloggen" }
    private var canSubmit: Bool {
        let okMail = email.contains("@") && email.contains(".")
        return mode == .reset ? okMail : (okMail && password.count >= (mode == .signUp ? 8 : 1))
    }

    private func switchTo(_ m: Mode) {
        withAnimation(.dsSpring) { mode = m; error = nil; account.info = nil }
    }

    private func google() async {
        guard !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do { try await account.signInWithGoogle() }
        catch is CancellationError {}
        catch { self.error = error.localizedDescription }
    }

    private func submit() async {
        guard canSubmit, !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do {
            switch mode {
            case .signIn: try await account.signIn(email: email, password: password)
            case .signUp: try await account.signUp(email: email, password: password)
            case .reset: try await account.sendPasswordReset(email: email); mode = .signIn
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// Na de link uit de mail: een nieuw wachtwoord kiezen.
struct NewPasswordView: View {
    @EnvironmentObject var account: Account
    @State private var password = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            DSLogo().padding(.top, 60)
            Text("Kies een nieuw wachtwoord").font(.largeTitle.weight(.bold))
            Text("Minstens 8 tekens. Daarmee log je voortaan in, in de app en op de website.").foregroundStyle(DS.text2)
            if let error { DSNotice(kind: .bad, text: error) }
            DSField(icon: "lock") { SecureField("Nieuw wachtwoord", text: $password).textContentType(.newPassword) }
            Button {
                Task {
                    busy = true; defer { busy = false }
                    do { try await account.setPassword(password) } catch { self.error = error.localizedDescription }
                }
            } label: { if busy { ProgressView().tint(.white) } else { Text("Opslaan") } }
            .buttonStyle(DSPrimaryButton()).disabled(password.count < 8 || busy)
            Button("Later") { account.skipNewPassword() }.frame(maxWidth: .infinity).padding(.top, 4)
            Spacer()
        }
        .padding(.horizontal, 20)
        .background(DS.canvas.ignoresSafeArea())
    }
}
