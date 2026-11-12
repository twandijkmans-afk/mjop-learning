import MJOPIntegration
import SwiftUI
import UIKit

/// Haalt de luchtfoto van een projectadres op (PDOK) en onthoudt coördinaten en beelden, zodat de lijst bij terugkomen direct staat.
/// Mislukt iets (offline, geen adres, geen treffer), dan is het resultaat `nil` en toont de kaart een neutrale plaatshouder: nooit een gok.
actor AerialPhotoLoader {
    static let shared = AerialPhotoLoader()

    private let session: URLSession
    private var memory: [String: UIImage] = [:]
    private var points: [String: AerialPhoto.Point]

    private static let pointsKey = "mjop.aerial.points.v1"

    init() {
        let cfg = URLSessionConfiguration.default
        cfg.urlCache = URLCache(memoryCapacity: 20 * 1024 * 1024, diskCapacity: 100 * 1024 * 1024)
        cfg.requestCachePolicy = .returnCacheDataElseLoad     // een luchtfoto verandert niet van dag tot dag
        cfg.timeoutIntervalForRequest = 12
        session = URLSession(configuration: cfg)
        let saved = UserDefaults.standard.dictionary(forKey: Self.pointsKey) as? [String: [Double]] ?? [:]
        points = saved.compactMapValues { $0.count == 2 ? AerialPhoto.Point(x: $0[0], y: $0[1]) : nil }
    }

    func image(for address: String) async -> UIImage? {
        guard let q = AerialPhoto.query(from: address) else { return nil }
        let key = q.text
        if let hit = memory[key] { return hit }
        guard let p = await point(for: q), let url = AerialPhoto.imageURL(center: p) else { return nil }
        guard let (data, resp) = try? await session.data(from: url),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              (resp.mimeType ?? "").hasPrefix("image/"),
              let img = UIImage(data: data) else { return nil }
        memory[key] = img
        return img
    }

    private func point(for q: AerialPhoto.Query) async -> AerialPhoto.Point? {
        if let p = points[q.text] { return p }
        guard let url = AerialPhoto.geocodeURL(q),
              let (data, resp) = try? await session.data(from: url),
              (resp as? HTTPURLResponse)?.statusCode == 200,
              let p = AerialPhoto.parseCentroid(data, expecting: q) else { return nil }
        points[q.text] = p
        UserDefaults.standard.set(points.mapValues { [$0.x, $0.y] }, forKey: Self.pointsKey)
        return p
    }
}

/// Luchtfoto bij een adres, met bronvermelding. Zonder foto: een neutraal vlak met een gebouwsymbool.
struct AerialPhotoView: View {
    let address: String?
    @State private var image: UIImage?
    @State private var finished = false

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            if let image {
                Image(uiImage: image).resizable().scaledToFill()
                Text(AerialPhoto.attribution)
                    .font(.system(size: 9)).foregroundStyle(.white)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(Color.black.opacity(0.5))
            } else {
                Rectangle().fill(Color(.tertiarySystemFill))
                Image(systemName: finished ? "building.2" : "photo").font(.title2).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task(id: address) {
            image = nil; finished = false
            if let a = address { image = await AerialPhotoLoader.shared.image(for: a) }
            finished = true
        }
        .accessibilityHidden(true)
    }
}

/// Eén project als kaart: luchtfoto, naam, adres, laatst bijgewerkt en de volgende stap. Alleen echte gegevens uit het project.
struct ProjectCard: View {
    let project: ProjectSummary
    let isOpen: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            AerialPhotoView(address: project.adres ?? project.label)
                .frame(height: 150).frame(maxWidth: .infinity).clipped()
            VStack(alignment: .leading, spacing: 5) {
                HStack(alignment: .firstTextBaseline) {
                    Text(project.label).font(.headline).foregroundStyle(Color.primary).multilineTextAlignment(.leading)
                    Spacer(minLength: 8)
                    if isOpen {
                        Text("Geopend").font(.caption.weight(.semibold)).padding(.horizontal, 8).padding(.vertical, 3)
                            .background(MJOPTheme.accent.opacity(0.15)).foregroundStyle(MJOPTheme.accent).clipShape(Capsule())
                    }
                }
                if let a = project.adres, a != project.label {
                    Text(a).font(.subheadline).foregroundStyle(Color.secondary).multilineTextAlignment(.leading)
                }
                Text(project.updatedDate.map { "Laatst bijgewerkt \(relativeDateText($0))" } ?? "Laatst bijgewerkt: onbekend")
                    .font(.caption).foregroundStyle(Color.secondary)
                if let n = project.nextStep {
                    Label(n, systemImage: "arrow.right.circle").font(.caption).foregroundStyle(MJOPTheme.accent).multilineTextAlignment(.leading)
                }
            }
            .padding(12).frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .contentShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}
