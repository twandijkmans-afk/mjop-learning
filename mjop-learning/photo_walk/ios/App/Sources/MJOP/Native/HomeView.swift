import SwiftUI

/// Home: begroeting, het laatst bijgewerkte project groot met foto, snelle acties, wat eraan komt en recente projecten.
struct HomeView: View {
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    let openTab: (NativeTab) -> Void
    let startScan: () -> Void

    private var current: Project? { store.projects.first }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    header
                    if let e = store.error { DSNotice(kind: .warn, text: e).padding(.horizontal, DS.pad).padding(.top, 14) }
                    if let p = current {
                        NavigationLink { ProjectDetailNativeView(project: p) } label: { ProjectHero(project: p) }
                            .buttonStyle(.plain)
                            .padding(.horizontal, DS.pad).padding(.top, 18)
                            .accessibilityIdentifier("homeHero")
                    } else if store.loadedOnce {
                        emptyHero.padding(.horizontal, DS.pad).padding(.top, 18)
                    } else {
                        RoundedRectangle(cornerRadius: DS.radiusHero, style: .continuous).fill(DS.surface2)
                            .frame(height: 230).padding(.horizontal, DS.pad).padding(.top, 18)
                            .overlay(ProgressView())
                    }

                    sectionTitle("Snelle acties")
                    HStack(spacing: 10) {
                        QuickAction(icon: "viewfinder", label: "Scan gevel", action: startScan)
                        QuickAction(icon: "plus", label: "Nieuw project") { openTab(.projects) }
                        QuickAction(icon: "chart.bar.fill", label: "Planning") { openTab(.mjop) }
                    }
                    .padding(.horizontal, DS.pad)

                    if store.projects.count > 1 {
                        sectionTitle("Recente projecten", trailing: "Alles") { openTab(.projects) }
                        VStack(spacing: 10) {
                            ForEach(store.projects.dropFirst().prefix(3)) { p in
                                NavigationLink { ProjectDetailNativeView(project: p) } label: { ProjectRowCard(project: p) }.buttonStyle(.plain)
                            }
                        }
                        .padding(.horizontal, DS.pad)
                    }
                }
                .padding(.bottom, 120)
            }
            .background(DS.canvas)
            .refreshable { await store.refresh(account) }
            .task { if !store.loadedOnce { await store.refresh(account) } }
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(DSFormat.today()).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text2)
                Text(account.firstName.map { "\(DSFormat.greeting()), \($0)" } ?? DSFormat.greeting())
                    .font(.system(size: 30, weight: .bold)).foregroundStyle(DS.text)
                    .accessibilityIdentifier("homeGreeting")
            }
            Spacer(minLength: 8)
        }
        .padding(.horizontal, 20).padding(.top, 12)
    }

    private var emptyHero: some View {
        VStack(alignment: .leading, spacing: 10) {
            DSIcon(systemName: "building.2", size: 46)
            Text("Nog geen projecten").font(.title3.weight(.bold))
            Text("Start met een adres. De app haalt het gebouw uit de BAG en maakt een eerste plan.").font(.subheadline).foregroundStyle(DS.text2)
            Button { openTab(.projects) } label: { Label("Nieuw project", systemImage: "plus") }.buttonStyle(DSPrimaryButton()).padding(.top, 6)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .dsCard(radius: DS.radiusHero)
    }

    private func sectionTitle(_ t: String, trailing: String? = nil, action: (() -> Void)? = nil) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(t).font(.system(size: 19, weight: .bold)).foregroundStyle(DS.text)
            Spacer()
            if let trailing, let action { Button(trailing, action: action).font(.subheadline.weight(.semibold)) }
        }
        .padding(.horizontal, 20).padding(.top, 24).padding(.bottom, 10)
        .accessibilityAddTraits(.isHeader)
    }
}

/// Grote projectkaart met luchtfoto (later: eigen gevelfoto) en de belangrijkste cijfers erop.
struct ProjectHero: View {
    let project: Project

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            LinearGradient(colors: [.black.opacity(0), .black.opacity(0.75)], startPoint: .center, endPoint: .bottom)
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(project.naam).font(.title2.weight(.bold)).lineLimit(2)
                    Text(heroLine).font(.subheadline).opacity(0.85).lineLimit(1)
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right").font(.system(size: 16, weight: .bold))
                    .frame(width: 40, height: 40).background(.ultraThinMaterial, in: Circle()).environment(\.colorScheme, .dark)
            }
            .foregroundStyle(.white)
            .padding(18)
            if let d = project.updatedAt {
                DSGlassChip(text: "Bijgewerkt \(DSFormat.relative(d))", dot: Color(hex: 0x6BE39A))
                    .padding(14).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
        }
        .frame(maxWidth: .infinity).frame(height: 230)
        .background { AerialPhotoView(address: project.fullAddress ?? project.naam) }
        .clipShape(RoundedRectangle(cornerRadius: DS.radiusHero, style: .continuous))
        .shadow(color: DS.accent.opacity(0.18), radius: 20, x: 0, y: 14)
        .accessibilityElement(children: .combine)
    }

    private var heroLine: String {
        var parts: [String] = []
        if let p = project.plaats { parts.append(p) }
        if let n = project.postenAantal { parts.append("\(n) posten") }
        if let t = project.geraamdTotaal { parts.append(DSFormat.euros(t) + (project.periodeTot.map { " tot \($0)" } ?? "")) }
        return parts.isEmpty ? (project.fullAddress ?? "") : parts.joined(separator: " · ")
    }
}

struct QuickAction: View {
    let icon: String
    let label: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                DSIcon(systemName: icon, size: 44)
                Text(label).font(.footnote.weight(.semibold)).foregroundStyle(DS.text).multilineTextAlignment(.center).lineLimit(2)
            }
            .frame(maxWidth: .infinity).padding(.vertical, 14)
            .dsCard(radius: 20)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("quick-\(label)")
    }
}
