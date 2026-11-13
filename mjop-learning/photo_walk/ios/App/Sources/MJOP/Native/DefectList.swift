import MJOPEngine
import SwiftUI
import UIKit

/// Uitsnede van de gevelfoto rond een punt (in fotopixels van de scan), voor de gebrekenlijst en het rapport.
enum DefectCrop {
    static func crop(_ image: UIImage, around p: [Double], scanWidth: Double, fraction: Double = 0.22) -> UIImage? {
        guard let cg = image.cgImageUpright else { return nil }
        let k = Double(cg.width) / scanWidth
        let side = Double(cg.width) * fraction
        let x = min(max(p[0] * k - side / 2, 0), Double(cg.width) - side), y = min(max(p[1] * k - side / 2, 0), Double(cg.height) - side)
        guard let c = cg.cropping(to: CGRect(x: x, y: y, width: side, height: min(side, Double(cg.height)))) else { return nil }
        return UIImage(cgImage: c)
    }
}

extension UIImage {
    /// CGImage in de juiste stand (camerafoto's hebben vaak een draaiing in de metadata).
    var cgImageUpright: CGImage? {
        if imageOrientation == .up, let cg = cgImage { return cg }
        let fmt = UIGraphicsImageRendererFormat(); fmt.scale = 1
        return UIGraphicsImageRenderer(size: size, format: fmt).image { _ in draw(at: .zero) }.cgImage
    }
}

/// Gebrekenlijst van één gevel: per gebrek een uitsnede van de foto, bevestigen of afwijzen, en bij bevestigen ernst,
/// omvang en intensiteit. Afgewezen gebreken blijven bewaard (te herstellen) maar tellen niet mee.
struct DefectListView: View {
    let image: UIImage
    let onDone: (FacadeScan) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var work: FacadeScan
    @State private var crops: [Int: UIImage] = [:]

    init(image: UIImage, scan: FacadeScan, onDone: @escaping (FacadeScan) -> Void) {
        self.image = image; self.onDone = onDone
        _work = State(initialValue: scan)
    }

    private var defects: [FacadeDefect] { work.defects ?? [] }

    var body: some View {
        NavigationStack {
            List {
                if defects.isEmpty {
                    Text("Op deze foto zijn geen gebreken gemarkeerd.").foregroundStyle(DS.text2)
                }
                ForEach(defects) { d in
                    Section { row(d) }
                }
                Section {
                    Text("Een gebrek is een voorstel uit de foto tot jij het bevestigt. Bevestigde gebreken staan bij de juiste post bij 'Staat beoordelen' en in het rapport; de conditiescore geef je zelf. Dit is geen gecertificeerde NEN 2767-inspectie.")
                        .font(.footnote).foregroundStyle(DS.text2)
                }
            }
            .navigationTitle("Gebreken · gevel op het \(work.facing)").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Annuleer") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Klaar") { onDone(work); dismiss() }.fontWeight(.semibold) }
            }
            .task {
                for d in defects { crops[d.id] = DefectCrop.crop(image, around: d.point, scanWidth: work.photoWidth) }
            }
        }
    }

    @ViewBuilder private func row(_ d: FacadeDefect) -> some View {
        let el = DefectHints.element(at: d.point, in: work.elements, tolerance: 0.02 * work.photoWidth)
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                if let c = crops[d.id] { Image(uiImage: c).resizable().scaledToFill() } else { DS.surface2 }
            }
            .frame(width: 84, height: 84).clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(alignment: .center) { Circle().stroke(Color.orange, lineWidth: 2).frame(width: 22, height: 22) }
            VStack(alignment: .leading, spacing: 4) {
                Text(d.type.label).font(.headline).foregroundStyle(d.isRejected ? DS.text2 : DS.text).strikethrough(d.isRejected)
                if let el { Text("Op \(el.type.label.lowercased()) \(el.id)").font(.caption).foregroundStyle(DS.text2) }
                if let n = d.note { Text("\u{201C}\(n)\u{201D}").font(.caption).foregroundStyle(DS.text2) }
                Text(d.isConfirmed ? "Bevestigd" : d.isRejected ? "Afgewezen" : "Voorgesteld door de herkenning")
                    .font(.caption.weight(.semibold)).foregroundStyle(d.isConfirmed ? DS.ok : d.isRejected ? DS.text2 : DS.warn)
            }
        }
        HStack(spacing: 10) {
            Button { set(d.id) { $0.status = $0.isConfirmed ? nil : .bevestigd } } label: {
                Label(d.isConfirmed ? "Bevestigd" : "Bevestig", systemImage: d.isConfirmed ? "checkmark.circle.fill" : "checkmark.circle")
            }
            .buttonStyle(.bordered).tint(DS.ok)
            Button { set(d.id) { $0.status = $0.isRejected ? nil : .afgewezen } } label: {
                Label(d.isRejected ? "Herstel" : "Wijs af", systemImage: d.isRejected ? "arrow.uturn.backward" : "xmark.circle")
            }
            .buttonStyle(.bordered).tint(DS.text2)
        }
        if d.isConfirmed {
            Picker("Ernst", selection: Binding(get: { d.ernst }, set: { v in set(d.id) { $0.ernst = v } })) {
                Text("Kies").tag(DefectSeverity?.none)
                ForEach(DefectSeverity.allCases, id: \.self) { Text($0.label).tag(DefectSeverity?.some($0)) }
            }
            Picker("Omvang", selection: Binding(get: { d.omvang }, set: { v in set(d.id) { $0.omvang = v } })) {
                Text("Kies").tag(DefectExtent?.none)
                ForEach(DefectExtent.allCases, id: \.self) { Text($0.label).tag(DefectExtent?.some($0)) }
            }
            Picker("Intensiteit", selection: Binding(get: { d.intensiteit }, set: { v in set(d.id) { $0.intensiteit = v } })) {
                Text("Kies").tag(DefectIntensity?.none)
                ForEach(DefectIntensity.allCases, id: \.self) { Text($0.label).tag(DefectIntensity?.some($0)) }
            }
        }
    }

    private func set(_ id: Int, _ change: (inout FacadeDefect) -> Void) {
        guard var ds = work.defects, let i = ds.firstIndex(where: { $0.id == id }) else { return }
        change(&ds[i])
        ds[i].reviewedAt = Date()
        work.defects = ds
    }
}
