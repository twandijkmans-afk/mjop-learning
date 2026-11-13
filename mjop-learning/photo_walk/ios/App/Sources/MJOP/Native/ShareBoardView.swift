import MJOPEngine
import Security
import SwiftUI

/// Een bekijklink voor het VvE-bestuur: een momentopname van het plan op een webpagina, zonder account en zonder iets aan te kunnen passen.
struct ShareLinkInfo: Identifiable, Equatable {
    var id: String { token }
    var token: String
    var showAmounts: Bool
    var expiresAt: Date?
    var views: Int
    var url: URL { URL(string: "https://twandijkmans-afk.github.io/MJOP-App/bestuur/?t=\(token)")! }
}

enum BoardShare {
    /// Wat het bestuur te zien krijgt. Alleen samenvattingen uit het plan; bedragen alleen als de gebruiker dat kiest.
    static func snapshot(project: Project, model: ProjectModel, showAmounts: Bool) -> [String: Any] {
        let year = ProjectModel.year, end = year + Engine.horizon - 1
        let per = model.perYear
        let jaren: [[String: Any]] = (year...end).map { j in
            let items = model.plan.filter { $0.jaar == j }.map { c -> [String: Any] in
                showAmounts ? ["naam": c.naam, "bedrag": euroInt(c.bedrag)] : ["naam": c.naam]
            }
            var o: [String: Any] = ["jaar": j, "posten": items]
            if showAmounts { o["bedrag"] = euroInt(per[j] ?? 0) }
            return o
        }
        var s: [String: Any] = [
            "naam": project.naam, "adres": jsonValue(project.fullAddress), "periode": "\(year)–\(end)",
            "posten": model.elements.count, "beoordeeld": model.beoordeeld, "jaren": jaren,
            "gemaakt_op": ISO8601DateFormatter().string(from: Date()),
            "bronnen": [
                "Gebouwgegevens uit de BAG en de 3D BAG (TU Delft).",
                "Kosten geraamd met standaardbedragen (prijspeil \(year)) of met offertes waar die zijn toegevoegd; geen garantie op de uiteindelijke prijs.",
                "Posten zonder beoordeling volgen de gebruikelijke levensduur; beoordelingen volgen een vereenvoudigde NEN 2767-schaal (geen gecertificeerde inspectie).",
                "Momentopname uit MJOP Live; latere wijzigingen staan er pas in na een nieuwe link.",
            ],
        ]
        if showAmounts {
            s["totaal"] = euroInt(model.total)
            if let p = model.peak { s["piek"] = ["jaar": p.jaar, "bedrag": euroInt(p.bedrag)] }
            if let b = model.bijdrage { s["bijdrage"] = euroInt(b) }
            if let r = model.required { s["nodig"] = r }
            if let low = model.fund?.min(by: { $0.saldo < $1.saldo }) { s["laagste"] = ["jaar": low.jaar, "saldo": euroInt(low.saldo)] }
        }
        return s
    }

    static func token() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return Data(bytes).base64URL
    }
}

struct ShareBoardView: View {
    let project: Project
    let model: ProjectModel
    @EnvironmentObject var account: Account
    @Environment(\.dismiss) private var dismiss
    @State private var links: [ShareLinkInfo] = []
    @State private var showAmounts = true
    @State private var busy = false
    @State private var error: String?

    private var active: ShareLinkInfo? { links.first }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Laat het bestuur meekijken").font(.system(size: 28, weight: .bold)).foregroundStyle(DS.text)
                    Text("Een bekijklink naar het plan en het rapport. Zonder account, niets aan te passen. Het is een momentopname: na wijzigingen maak je een nieuwe link.")
                        .foregroundStyle(DS.text2)
                    if let error { DSNotice(kind: .warn, text: error) }
                    Toggle(isOn: $showAmounts) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Bedragen tonen").font(.headline).foregroundStyle(DS.text)
                            Text("Uit: alleen welke posten wanneer aan de beurt zijn.").font(.caption).foregroundStyle(DS.text2)
                        }
                    }
                    .tint(DS.accent)
                    .padding(16).dsCard(radius: 20)
                    if let l = active {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(spacing: 12) {
                                DSIcon(systemName: "link")
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(l.url.absoluteString).font(.footnote.weight(.semibold)).foregroundStyle(DS.text).lineLimit(1).truncationMode(.middle)
                                    Text(sub(l)).font(.caption).foregroundStyle(DS.text2)
                                }
                            }
                            ShareLink(item: l.url, subject: Text("MJOP \(project.naam)"), message: Text("Het meerjarenonderhoudsplan van \(project.naam) om te bekijken:")) {
                                Label("Link versturen", systemImage: "square.and.arrow.up")
                            }
                            .buttonStyle(DSPrimaryButton())
                            Button { UIPasteboard.general.url = l.url } label: { Label("Kopieer link", systemImage: "doc.on.doc") }.buttonStyle(DSSecondaryButton())
                            Button(role: .destructive) { Task { await revoke(l) } } label: { Text("Link intrekken").frame(maxWidth: .infinity) }.padding(.top, 4)
                        }
                        .padding(16).dsCard(radius: 20)
                    }
                    Button { Task { await create() } } label: {
                        if busy { ProgressView().tint(.white) } else { Label(active == nil ? "Maak een bekijklink" : "Nieuwe link met de huidige stand", systemImage: "plus") }
                    }
                    .buttonStyle(active == nil ? AnyButtonStyle(DSPrimaryButton()) : AnyButtonStyle(DSSecondaryButton()))
                    .disabled(busy)
                    .accessibilityIdentifier("createShare")
                }
                .padding(.horizontal, DS.pad).padding(.bottom, 30)
            }
            .background(DS.canvas)
            .navigationTitle("Delen met het bestuur").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Klaar") { dismiss() } } }
            .task { await load() }
        }
    }

    private func sub(_ l: ShareLinkInfo) -> String {
        var parts: [String] = []
        if let d = l.expiresAt { let f = DateFormatter(); f.locale = Locale(identifier: "nl_NL"); f.dateFormat = "d MMMM"; parts.append("geldig tot \(f.string(from: d))") }
        parts.append(l.views == 0 ? "nog niet bekeken" : "\(l.views)× bekeken")
        parts.append(l.showAmounts ? "met bedragen" : "zonder bedragen")
        return parts.joined(separator: " · ")
    }

    private func load() async {
        if account.demo { return }
        do {
            let s = try await account.validSession()
            let (data, http) = try await BackendClient(session: s).request("rest/v1/project_shares", query: [
                URLQueryItem(name: "project_id", value: "eq.\(project.id)"), URLQueryItem(name: "revoked", value: "eq.false"),
                URLQueryItem(name: "select", value: "token,show_amounts,expires_at,views"), URLQueryItem(name: "order", value: "created_at.desc")])
            guard http.statusCode == 200, let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
                error = BackendClient.message(data, status: http.statusCode); return
            }
            links = rows.compactMap { r in
                guard let t = r["token"] as? String else { return nil }
                return ShareLinkInfo(token: t, showAmounts: r["show_amounts"] as? Bool ?? true, expiresAt: (r["expires_at"] as? String).flatMap(Project.parseDate), views: r["views"] as? Int ?? 0)
            }.filter { ($0.expiresAt ?? .distantFuture) > Date() }
            if let l = links.first { showAmounts = l.showAmounts }
        } catch { self.error = error.localizedDescription }
    }

    private func create() async {
        busy = true; defer { busy = false }
        let t = BoardShare.token()
        if account.demo { links.insert(ShareLinkInfo(token: t, showAmounts: showAmounts, expiresAt: Date().addingTimeInterval(30 * 86400), views: 0), at: 0); return }
        do {
            let s = try await account.validSession()
            let row: [String: Any] = ["token": t, "project_id": project.id, "show_amounts": showAmounts,
                                      "snapshot": BoardShare.snapshot(project: project, model: model, showAmounts: showAmounts)]
            let (data, http) = try await BackendClient(session: s).request("rest/v1/project_shares", method: "POST", body: row)
            guard (200..<300).contains(http.statusCode) else { error = BackendClient.message(data, status: http.statusCode); return }
            await load()
        } catch { self.error = error.localizedDescription }
    }

    private func revoke(_ l: ShareLinkInfo) async {
        if account.demo { links.removeAll { $0.token == l.token }; return }
        do {
            let s = try await account.validSession()
            let (data, http) = try await BackendClient(session: s).request("rest/v1/project_shares", method: "PATCH", query: [URLQueryItem(name: "token", value: "eq.\(l.token)")], body: ["revoked": true])
            guard (200..<300).contains(http.statusCode) else { error = BackendClient.message(data, status: http.statusCode); return }
            await load()
        } catch { self.error = error.localizedDescription }
    }
}

/// Type-gewiste knopstijl, om tussen twee stijlen te kunnen kiezen.
struct AnyButtonStyle: ButtonStyle {
    private let make: (Configuration) -> AnyView
    init<S: ButtonStyle>(_ s: S) { make = { AnyView(s.makeBody(configuration: $0)) } }
    func makeBody(configuration: Configuration) -> some View { make(configuration) }
}
