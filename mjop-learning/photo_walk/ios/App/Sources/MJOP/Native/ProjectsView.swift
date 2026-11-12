import SwiftUI

/// Projecten: zoeken, filteren en de lijst met kaarten. Een nieuw project starten komt in het volgende deel (adres zoeken en meteen scannen).
struct ProjectsView: View {
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    let startScan: () -> Void
    @State private var query = ""
    @State private var showNew = false

    private var shown: [Project] {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return store.projects }
        return store.projects.filter { p in
            [p.naam, p.fullAddress ?? ""].contains { $0.range(of: q, options: [.caseInsensitive, .diacriticInsensitive]) != nil }
        }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Projecten").font(.system(size: 32, weight: .bold)).foregroundStyle(DS.text).padding(.horizontal, 4).padding(.top, 12)
                    HStack(spacing: 10) {
                        HStack(spacing: 8) {
                            Image(systemName: "magnifyingglass").foregroundStyle(DS.text2)
                            TextField("Zoek op adres of naam", text: $query).textInputAutocapitalization(.never).autocorrectionDisabled()
                                .accessibilityIdentifier("projectSearch")
                        }
                        .padding(.horizontal, 16).frame(height: 46)
                        .background(DS.surface, in: Capsule())
                        .overlay(Capsule().strokeBorder(DS.line, lineWidth: 1))
                    }
                    if let e = store.error { DSNotice(kind: .warn, text: e) }
                    if store.loading && !store.loadedOnce { ProgressView().frame(maxWidth: .infinity).padding(.top, 30) }
                    ForEach(shown) { p in
                        NavigationLink { ProjectDetailNativeView(project: p) } label: { ProjectRowCard(project: p) }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("project-\(p.naam)")
                    }
                    if store.loadedOnce && shown.isEmpty && !query.isEmpty {
                        Text("Geen project gevonden voor “\(query)”.").font(.subheadline).foregroundStyle(DS.text2).frame(maxWidth: .infinity).padding(.top, 20)
                    }
                    Button { showNew = true } label: {
                        HStack(spacing: 12) {
                            DSIcon(systemName: "plus")
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Nieuw project").font(.headline).foregroundStyle(DS.text)
                                Text("Adres zoeken en meteen scannen").font(.footnote).foregroundStyle(DS.text2)
                            }
                            Spacer()
                        }
                        .padding(16)
                        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(DS.accent.opacity(0.35), style: StrokeStyle(lineWidth: 1.5, dash: [6, 5])))
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("newProject")
                }
                .padding(.horizontal, DS.pad).padding(.bottom, 120)
            }
            .background(DS.canvas)
            .refreshable { await store.refresh(account) }
            .task { if !store.loadedOnce { await store.refresh(account) } }
            .toolbar(.hidden, for: .navigationBar)
            .sheet(isPresented: $showNew) { ComingNextSheet(title: "Nieuw project", text: "Adres zoeken, het gebouw bevestigen met luchtfoto en BAG-gegevens, en daarna meteen het rondje om het gebouw. Dit bouw ik in het volgende deel.") }
        }
    }
}

/// Projectkaart in een lijst: foto, naam, plaats en een echte stand van zaken.
struct ProjectRowCard: View {
    let project: Project

    var body: some View {
        HStack(spacing: 14) {
            Color.clear.frame(width: 76, height: 76)
                .background { AerialPhotoView(address: project.fullAddress ?? project.naam) }
                .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                Text(project.naam).font(.headline).foregroundStyle(DS.text).lineLimit(1)
                Text(project.subtitle).font(.subheadline).foregroundStyle(DS.text2).lineLimit(1)
                if let s = status { Text(s).font(.caption.weight(.semibold)).foregroundStyle(DS.accent).lineLimit(1).padding(.top, 2) }
            }
            Spacer(minLength: 4)
            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(DS.text2.opacity(0.6))
        }
        .padding(10)
        .dsCard(radius: 20)
        .contentShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    private var status: String? {
        var parts: [String] = []
        if let n = project.postenAantal { parts.append("\(project.beoordeeld ?? 0) van \(n) beoordeeld") }
        if let d = project.updatedAt { parts.append(DSFormat.relative(d)) }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }
}

/// Eerlijke melding voor onderdelen die in een volgend deel komen.
struct ComingNextSheet: View {
    let title: String
    let text: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 16) {
            Spacer()
            DSIcon(systemName: "hammer", size: 64)
            Text(title).font(.title2.weight(.bold))
            Text(text).foregroundStyle(DS.text2).multilineTextAlignment(.center).padding(.horizontal, 28)
            Spacer()
            Button("Sluiten") { dismiss() }.buttonStyle(DSSecondaryButton()).padding(.horizontal, 20).padding(.bottom, 20)
        }
        .frame(maxWidth: .infinity)
        .background(DS.canvas.ignoresSafeArea())
        .presentationDetents([.medium])
    }
}
