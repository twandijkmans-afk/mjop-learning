import SwiftUI
import UIKit

/// Gevelfoto's in de privé Supabase-bucket `gevelfotos` (pad: {project_id}/gevel-{zijde}-{deel}.jpg).
enum GevelFotos {
    static let bucket = "gevelfotos"
    static func path(project: String, side: Int, part: Int) -> String { "\(project)/gevel-\(side)-\(part).jpg" }

    @MainActor private static var cache: [String: UIImage] = [:]

    static func upload(_ image: UIImage, path: String, session: Session) async throws {
        let (jpeg, _) = try ClaudeVision.prepare(image)
        var r = URLRequest(url: Backend.url.appendingPathComponent("storage/v1/object/\(bucket)/\(path)"))
        r.httpMethod = "POST"
        r.timeoutInterval = 60
        r.setValue(Backend.anonKey, forHTTPHeaderField: "apikey")
        r.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        r.setValue("image/jpeg", forHTTPHeaderField: "Content-Type")
        r.setValue("true", forHTTPHeaderField: "x-upsert")
        let (data, resp) = try await URLSession.shared.upload(for: r, from: jpeg)
        let status = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            let msg = String(data: data, encoding: .utf8) ?? ""
            if msg.contains("Bucket not found") { throw BackendError.message("De opslag voor gevelfoto's is nog niet ingericht (SQL nog niet uitgevoerd).") }
            throw BackendError.message(BackendClient.message(data, status: status))
        }
        await MainActor.run { cache[path] = image }
    }

    @MainActor static func cached(_ path: String) -> UIImage? { cache[path] }

    static func load(_ path: String, session: Session) async -> UIImage? {
        if let c = await cached(path) { return c }
        var r = URLRequest(url: Backend.url.appendingPathComponent("storage/v1/object/authenticated/\(bucket)/\(path)"))
        r.timeoutInterval = 30
        r.setValue(Backend.anonKey, forHTTPHeaderField: "apikey")
        r.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        guard let res = try? await URLSession.shared.data(for: r), (res.1 as? HTTPURLResponse)?.statusCode == 200, let img = UIImage(data: res.0) else { return nil }
        await MainActor.run { cache[path] = img }
        return img
    }
}

/// Een gevelfoto uit de cloud; zolang hij laadt of als hij er niet is: `fallback`.
struct StoragePhotoView<Fallback: View>: View {
    let path: String?
    @ViewBuilder var fallback: () -> Fallback
    @EnvironmentObject var account: Account
    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image { Image(uiImage: image).resizable().scaledToFill() } else { fallback() }
        }
        .task(id: path) {
            guard let path, !account.demo else { image = nil; return }
            if let c = GevelFotos.cached(path) { image = c; return }
            guard let s = try? await account.validSession() else { return }
            image = await GevelFotos.load(path, session: s)
        }
    }
}

/// Projectfoto: de eigen gevelfoto als die er is, anders de luchtfoto.
struct ProjectPhotoView: View {
    let project: Project
    var attribution: Alignment? = .bottomLeading
    var body: some View {
        StoragePhotoView(path: project.photoPath) { AerialPhotoView(address: project.fullAddress ?? project.naam, attribution: attribution) }
    }
}
