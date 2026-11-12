import MJOPEngine
import SwiftUI

/// Ophalen bij de openbare diensten (PDOK, BAG, 3D BAG). Het lezen van de antwoorden staat in MJOPEngine.BuildingLookup.
enum BuildingService {
    static func get(_ url: URL?, timeout: TimeInterval = 12) async throws -> Data {
        guard let url else { throw BackendError.message("Ongeldig adres.") }
        var r = URLRequest(url: url)
        r.timeoutInterval = timeout
        do {
            let (data, resp) = try await URLSession.shared.data(for: r)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { throw BackendError.message("De dienst gaf geen antwoord (\((resp as? HTTPURLResponse)?.statusCode ?? 0)).") }
            return data
        } catch let e as URLError where BackendClient.offlineCodes.contains(e.code) {
            throw BackendError.offline
        }
    }

    static func suggest(_ q: String) async throws -> [AddressSuggestion] {
        BuildingLookup.parseSuggest(try await get(BuildingLookup.suggestURL(q)))
    }

    /// Adres → pand (BAG) → 3D BAG. De 3D BAG is aanvullend: lukt die niet, dan rekent het plan met de BAG-schatting.
    static func building(for s: AddressSuggestion) async throws -> FoundBuilding {
        guard let a = BuildingLookup.parseLookup(try await get(BuildingLookup.lookupURL(s.id))) else { throw BackendError.message("Geen coördinaat gevonden voor dit adres.") }
        guard let pand = BuildingLookup.pickPand(try await get(BuildingLookup.bagURL(lon: a.lon, lat: a.lat)), lon: a.lon, lat: a.lat) else {
            throw BackendError.message("Geen pand gevonden op dit adres in de BAG.")
        }
        let d3 = try? await BuildingLookup.parse3DBAG(get(BuildingLookup.threeDURL(pand.identificatie), timeout: 15), pandId: pand.identificatie)
        return FoundBuilding(address: a, pand: pand, threeD: d3)
    }
}

struct FoundBuilding: Equatable {
    var address: AddressDetails
    var pand: PandInfo
    var threeD: ThreeDBAGInfo?
}

/// Nieuw project: adres zoeken, gebouw bevestigen, plan maken.
struct NewProjectFlow: View {
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @Environment(\.dismiss) private var dismiss
    let onCreated: (Project) -> Void

    @State private var query = ""
    @State private var results: [AddressSuggestion] = []
    @State private var searching = false
    @State private var error: String?
    @State private var chosen: AddressSuggestion?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Welk gebouw?").font(.system(size: 30, weight: .bold)).foregroundStyle(DS.text)
                    Text("Zoek op adres. De gegevens komen uit de BAG en de 3D BAG.").foregroundStyle(DS.text2)
                    DSField(icon: "magnifyingglass") {
                        TextField("Straat en huisnummer", text: $query)
                            .textInputAutocapitalization(.words).autocorrectionDisabled()
                            .accessibilityIdentifier("addressSearch")
                        if searching { ProgressView() }
                    }
                    if let error { DSNotice(kind: .warn, text: error) }
                    if !results.isEmpty {
                        VStack(spacing: 0) {
                            ForEach(results) { r in
                                NavigationLink(value: r) {
                                    HStack(spacing: 12) {
                                        DSIcon(systemName: "mappin.and.ellipse")
                                        Text(r.naam).foregroundStyle(DS.text).multilineTextAlignment(.leading)
                                        Spacer()
                                        Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(DS.text2.opacity(0.6))
                                    }
                                    .padding(.horizontal, 14).frame(minHeight: 58)
                                }
                                .buttonStyle(DSRowStyle())
                                .accessibilityIdentifier("address-\(r.naam)")
                                if r.id != results.last?.id { Divider().padding(.leading, 60) }
                            }
                        }
                        .dsCard(radius: 20)
                    }
                }
                .padding(.horizontal, DS.pad).padding(.top, 8).padding(.bottom, 30)
            }
            .background(DS.canvas)
            .navigationTitle("Nieuw project").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annuleer") { dismiss() } } }
            .navigationDestination(for: AddressSuggestion.self) { s in
                ConfirmBuildingView(suggestion: s, onCreated: { p in dismiss(); onCreated(p) })
            }
            .task(id: query) { await search() }
        }
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 3 else { results = []; return }
        try? await Task.sleep(nanoseconds: 300_000_000)   // even wachten tot de gebruiker stopt met typen
        guard !Task.isCancelled else { return }
        searching = true; defer { searching = false }
        do { results = try await BuildingService.suggest(q); error = results.isEmpty ? "Geen adres gevonden. Controleer de spelling." : nil }
        catch { if !Task.isCancelled { self.error = error.localizedDescription } }
    }
}

extension AddressSuggestion: Hashable {
    public func hash(into h: inout Hasher) { h.combine(id) }
}

/// Het gevonden gebouw bevestigen: luchtfoto, BAG- en 3D BAG-gegevens, aantal appartementen aanpassen, en het plan maken.
struct ConfirmBuildingView: View {
    let suggestion: AddressSuggestion
    let onCreated: (Project) -> Void
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @State private var found: FoundBuilding?
    @State private var units = 1
    @State private var error: String?
    @State private var saving = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Color.clear.frame(height: 260)
                    .background { AerialPhotoView(address: found?.address.naam ?? suggestion.naam) }
                    .clipped()
                VStack(alignment: .leading, spacing: 14) {
                    Text("GEVONDEN IN DE BAG").font(.caption.weight(.bold)).foregroundStyle(DS.accent)
                    Text(found?.address.naam ?? suggestion.naam).font(.system(size: 24, weight: .bold)).foregroundStyle(DS.text)
                    if let error { DSNotice(kind: .warn, text: error) }
                    if let f = found {
                        HStack(spacing: 10) {
                            StatTile(icon: "calendar", value: f.pand.bouwjaar.map(String.init) ?? "–", label: "Bouwjaar · BAG")
                            StatTile(icon: "house", value: roofText(f.threeD), label: "Dak · 3D BAG")
                            StatTile(icon: "ruler", value: f.threeD?.hoogteM.map { String(format: "%.1f m", $0).replacingOccurrences(of: ".", with: ",") } ?? "–", label: "Hoogte")
                        }
                        Stepper(value: $units, in: 1...999) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Appartementen: \(units)").font(.headline).foregroundStyle(DS.text)
                                Text(f.pand.verblijfsobjecten.map { "BAG: \($0) verblijfsobject\($0 == 1 ? "" : "en")" } ?? "Niet bekend in de BAG").font(.footnote).foregroundStyle(DS.text2)
                            }
                        }
                        .padding(16).dsCard(radius: 20)
                        if f.threeD == nil {
                            DSNotice(kind: .info, text: "Geen 3D BAG-gegevens gevonden. Dak en gevel worden geschat uit de plattegrond; na de gevelscan wordt het nauwkeuriger.")
                        } else if f.threeD?.kwaliteitGoed == false {
                            DSNotice(kind: .info, text: "De 3D BAG geeft aan dat het 3D-model van dit pand gecontroleerd moet worden. De maten zijn een voorstel.")
                        }
                        Button { Task { await create(f) } } label: {
                            if saving { ProgressView().tint(.white) } else { Label("Plan maken", systemImage: "sparkles") }
                        }
                        .buttonStyle(DSPrimaryButton()).disabled(saving)
                        .accessibilityIdentifier("createProject")
                        Text("Daarna kun je het rondje om het gebouw doen met de gevelscan.").font(.footnote).foregroundStyle(DS.text2).frame(maxWidth: .infinity)
                    } else if error == nil {
                        HStack(spacing: 10) { ProgressView(); Text("Gebouw ophalen uit de BAG…").foregroundStyle(DS.text2) }.padding(.top, 10)
                    }
                }
                .padding(.horizontal, DS.pad).padding(.top, 22).padding(.bottom, 40)
                .background(DS.canvas, in: UnevenRoundedTop(radius: 28))
                .offset(y: -28)
            }
        }
        .background(DS.canvas)
        .navigationTitle("Gebouw").navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func roofText(_ d: ThreeDBAGInfo?) -> String {
        guard let d else { return "–" }
        if (d.dakSchuinM2 ?? 0) > (d.dakPlatM2 ?? 0) { return "Hellend" }
        if d.dakPlatM2 != nil { return "Plat" }
        return "–"
    }

    private func load() async {
        guard found == nil else { return }
        do {
            let f = try await BuildingService.building(for: suggestion)
            found = f
            units = f.pand.verblijfsobjecten ?? 1
        } catch { self.error = error.localizedDescription }
    }

    private func create(_ f: FoundBuilding) async {
        saving = true; defer { saving = false }
        do {
            let p = try await store.create(from: f, units: units, account: account)
            onCreated(p)
        } catch { self.error = error.localizedDescription }
    }
}
