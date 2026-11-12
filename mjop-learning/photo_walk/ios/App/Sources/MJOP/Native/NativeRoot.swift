import MJOPIntegration
import SwiftUI

/// MJOP Live 3: volledig native. Eerst inloggen (zelfde account als de website), daarna vier tabs in een zwevende balk met in het midden de scanknop.
struct NativeRoot: View {
    @StateObject private var account = Account()
    @StateObject private var projects = ProjectStore()
    @State private var tab: NativeTab = .home
    @State private var showScan = false
    @State private var showSplash = LaunchSplashView.shouldShow

    var body: some View {
        ZStack {
            DS.canvas.ignoresSafeArea()
            switch account.state {
            case .loading:
                ProgressView().tint(DS.accent)
            case .signedOut:
                LoginView()
                    .transition(.opacity)
            case .newPassword:
                NewPasswordView()
            case .signedIn:
                tabs
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: account.state)
        .environmentObject(account)
        .environmentObject(projects)
        .tint(DS.accent)
        .overlay { if showSplash { LaunchSplashView(done: { showSplash = false }) } }
        .task { await account.start() }
        .onOpenURL { url in
            guard url.scheme?.lowercased() == MJOPConfig.appURLScheme else { return }
            Task { await account.handle(url: url) }
        }
        .onChange(of: account.state) { s in
            if s == .signedOut { projects.clear(); tab = .home }
        }
        .sheet(isPresented: $showScan) { ScanPlaceholderView() }
    }

    private var tabs: some View {
        ZStack(alignment: .bottom) {
            Group {
                switch tab {
                case .home: HomeView(openTab: { tab = $0 }, startScan: { showScan = true })
                case .projects: ProjectsView(startScan: { showScan = true })
                case .mjop: MJOPPlaceholderView(openTab: { tab = $0 })
                case .profile: ProfileView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            FloatingTabBar(selected: $tab, scan: { showScan = true })
                .padding(.horizontal, 18)
                .padding(.bottom, 8)
        }
        .ignoresSafeArea(.keyboard)
    }
}

enum NativeTab: Hashable { case home, projects, mjop, profile }

/// Zwevende ovale tabbalk met vier tabs en in het midden een ronde blauwe scanknop.
struct FloatingTabBar: View {
    @Binding var selected: NativeTab
    let scan: () -> Void
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        HStack(spacing: 0) {
            item(.home, "Home", "house", "house.fill")
            item(.projects, "Projecten", "folder", "folder.fill")
            Button(action: scan) {
                Image(systemName: "viewfinder")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 58, height: 58)
                    .background(LinearGradient(colors: [Color(hex: 0x4D66FF), DS.accentDeep], startPoint: .topLeading, endPoint: .bottomTrailing), in: Circle())
                    .overlay(Circle().strokeBorder(DS.canvas, lineWidth: 4))
                    .shadow(color: DS.accent.opacity(0.45), radius: 11, x: 0, y: 8)
            }
            .offset(y: -18)
            .frame(maxWidth: .infinity)
            .accessibilityLabel("Gevel scannen")
            .accessibilityIdentifier("tabScan")
            item(.mjop, "MJOP", "calendar", "calendar")
            item(.profile, "Profiel", "person.crop.circle", "person.crop.circle.fill")
        }
        .frame(height: 64)
        .background(.regularMaterial, in: Capsule())
        .overlay(Capsule().strokeBorder(Color.primary.opacity(scheme == .dark ? 0.1 : 0.05), lineWidth: 0.5))
        .shadow(color: .black.opacity(scheme == .dark ? 0.5 : 0.14), radius: 17, x: 0, y: 12)
    }

    private func item(_ t: NativeTab, _ label: String, _ icon: String, _ iconOn: String) -> some View {
        let on = selected == t
        return Button {
            if !on { UISelectionFeedbackGenerator().selectionChanged() }
            withAnimation(.dsSpring) { selected = t }
        } label: {
            VStack(spacing: 2) {
                Image(systemName: on ? iconOn : icon).font(.system(size: 20, weight: on ? .semibold : .regular))
                Text(label).font(.system(size: 10, weight: .semibold))
            }
            .foregroundStyle(on ? DS.accent : DS.text2)
            .frame(maxWidth: .infinity, minHeight: 50)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier("tab-\(label)")
    }
}

extension Animation {
    /// Korte, strakke veer voor tabwissels en kleine overgangen.
    static var dsSpring: Animation { .spring(response: 0.3, dampingFraction: 0.85) }
}

/// Plaats voor de gevelscan tot die in de app is gebouwd (volgende deel). Eerlijk, geen nepfunctie.
struct ScanPlaceholderView: View {
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        VStack(spacing: 18) {
            Capsule().fill(DS.line).frame(width: 40, height: 5).padding(.top, 10)
            Spacer()
            DSIcon(systemName: "viewfinder", size: 72)
            Text("Gevelscan").font(.title.weight(.bold))
            Text("Het rondje om het gebouw komt in een volgende versie van deze testbouw: per gevel een foto, Claude herkent de elementen en de app rekent de hoeveelheden.")
                .font(.body).foregroundStyle(DS.text2).multilineTextAlignment(.center).padding(.horizontal, 28)
            Spacer()
            Button("Sluiten") { dismiss() }.buttonStyle(DSSecondaryButton()).padding(.horizontal, 20).padding(.bottom, 20)
        }
        .frame(maxWidth: .infinity)
        .background(DS.canvas.ignoresSafeArea())
        .presentationDetents([.medium, .large])
    }
}

/// MJOP-tab: het plan van het laatst bijgewerkte project (wisselen via de projectnaam).
struct MJOPPlaceholderView: View {
    let openTab: (NativeTab) -> Void
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @State private var selectedId: String?

    private var project: Project? { store.projects.first { $0.id == selectedId } ?? store.projects.first }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if let p = project {
                    if store.projects.count > 1 {
                        Menu {
                            ForEach(store.projects) { q in Button(q.naam) { selectedId = q.id } }
                        } label: {
                            Label(p.naam, systemImage: "chevron.up.chevron.down").font(.subheadline.weight(.semibold))
                        }
                        .padding(.horizontal, 4).padding(.top, 12)
                    }
                    MJOPView(project: p).padding(.top, store.projects.count > 1 ? 0 : 12)
                } else if store.loadedOnce {
                    Text("MJOP").font(.system(size: 32, weight: .bold)).padding(.top, 12)
                    VStack(alignment: .leading, spacing: 10) {
                        DSIcon(systemName: "calendar", size: 46)
                        Text("Nog geen project").font(.title3.weight(.bold))
                        Text("Maak eerst een project bij Projecten; dan zie je hier de planning, de kosten en het rapport.").font(.subheadline).foregroundStyle(DS.text2)
                        Button("Naar Projecten") { openTab(.projects) }.buttonStyle(DSSecondaryButton()).padding(.top, 6)
                    }
                    .padding(18).dsCard()
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                }
            }
            .padding(.horizontal, DS.pad).padding(.bottom, 120)
        }
        .background(DS.canvas)
        .task { if !store.loadedOnce { await store.refresh(account) } }
    }
}
