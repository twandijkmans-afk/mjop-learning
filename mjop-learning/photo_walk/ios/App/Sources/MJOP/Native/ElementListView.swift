import MJOPEngine
import SwiftUI

/// Notatie van maten in de elementenlijst (komma, eenheid, ±).
enum ElementFormat {
    static func num(_ v: Double, _ d: Int = 2) -> String { String(format: "%.\(d)f", v).replacingOccurrences(of: ".", with: ",") }
    private static func unit(_ k: FacadeKind) -> String { k == .line ? "m" : "m²" }

    /// Hoofdmaat van één element: lengte, breedte × hoogte, of oppervlak.
    static func value(_ m: ElementMeasure) -> String {
        switch m.type.kind {
        case .line: return m.lengthM.map { num($0, 1) + " m" } ?? "maat onbekend"
        case .quad:
            guard let w = m.widthM, let h = m.heightM else { return "maat onbekend" }
            return "\(num(w)) × \(num(h)) m"
        case .poly: return m.areaM2.map { num($0, 1) + " m² netto" } ?? "maat onbekend"
        }
    }
    /// Bandbreedte van één element, op de hoofdmaat (bij een kader het oppervlak).
    static func band(_ m: ElementMeasure) -> String? {
        guard let b = m.band, let v = m.value else { return nil }
        let pre = m.type.kind == .quad ? num(v, 2) + " m², " : ""
        return pre + "± " + num(b, b < 10 ? 2 : 1) + " " + unit(m.type.kind)
    }
    /// Totaal van een soort met ±; nil als het totaal onbekend is.
    static func total(_ g: ElementGroup) -> String {
        guard let t = g.total else { return "totaal onbekend" }
        let net = g.type.kind == .poly ? " netto" : ""
        return num(t, 1) + " " + unit(g.type.kind) + net
    }
    static func totalBand(_ g: ElementGroup) -> String? {
        guard let b = g.band, g.total != nil else { return nil }
        return "± " + num(b, b < 10 ? 2 : 1) + " " + unit(g.type.kind)
    }
    static func name(_ m: ElementMeasure) -> String {
        var s = "\(m.type.label) \(m.elementId)"
        if (m.hiddenFraction ?? 0) > FacadeReview.hiddenLimit { s += " (deels verborgen)" }
        return s
    }
}

/// Elementenlijst: per soort het aantal en de totale maat met ±, uit te klappen naar elk los element.
/// Tikken op een element (als `onSelect` is gezet) laat het oplichten op de foto.
struct ElementListCard: View {
    let groups: [ElementGroup]
    var title = "Elementen en maten"
    /// Extra regel per element, bijv. de gevel ("Gevel op het zuid") in de lijst van het hele gebouw.
    var subtitle: ((ElementMeasure) -> String?)? = nil
    var onSelect: ((ElementMeasure) -> Void)? = nil
    @State private var open: Set<String> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.headline).foregroundStyle(DS.text)
            if groups.isEmpty {
                Text("Nog geen elementen herkend.").font(.subheadline).foregroundStyle(DS.text2)
            } else {
                VStack(spacing: 0) {
                    ForEach(groups) { g in
                        groupRow(g)
                        if open.contains(g.id) {
                            ForEach(g.items) { m in itemRow(m) }
                        }
                        if g.id != groups.last?.id { Divider().padding(.leading, 34) }
                    }
                }
                .dsCard(radius: 20)
                Text("Maten berekend uit de foto met de gevelbreedte uit de BAG; ± volgens vaste regels. Een voorstel, geen inmeting." + (onSelect != nil ? " Tik op een element om het op de foto te zien." : ""))
                    .font(.footnote).foregroundStyle(DS.text2)
            }
        }
    }

    private func groupRow(_ g: ElementGroup) -> some View {
        Button {
            withAnimation(.dsSpring) { if open.contains(g.id) { open.remove(g.id) } else { open.insert(g.id) } }
        } label: {
            HStack(spacing: 10) {
                Circle().fill(FacadeEditorView.color(g.type)).frame(width: 10, height: 10)
                VStack(alignment: .leading, spacing: 1) {
                    Text(g.type.label).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                    Text("\(g.count) st" + (g.materials.isEmpty ? "" : " · " + g.materials.joined(separator: ", "))).font(.caption).foregroundStyle(DS.text2)
                }
                Spacer(minLength: 6)
                VStack(alignment: .trailing, spacing: 1) {
                    Text(ElementFormat.total(g)).font(.subheadline.weight(.semibold)).foregroundStyle(g.total == nil ? Color.orange : DS.text)
                    if let b = ElementFormat.totalBand(g) { Text(b).font(.caption).foregroundStyle(DS.text2) }
                }
                Image(systemName: open.contains(g.id) ? "chevron.up" : "chevron.down").font(.caption.weight(.semibold)).foregroundStyle(DS.text2)
            }
            .padding(.horizontal, 14).frame(minHeight: 56)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("elementGroup-\(g.type.rawValue)")
    }

    private func itemRow(_ m: ElementMeasure) -> some View {
        Button { onSelect?(m) } label: {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(ElementFormat.name(m)).font(.subheadline).foregroundStyle(DS.text)
                    let sub = [subtitle?(m), m.material].compactMap { $0 }.joined(separator: " · ")
                    if !sub.isEmpty { Text(sub).font(.caption).foregroundStyle(DS.text2) }
                }
                Spacer(minLength: 6)
                VStack(alignment: .trailing, spacing: 1) {
                    Text(ElementFormat.value(m)).font(.subheadline).foregroundStyle(m.value == nil ? Color.orange : DS.text)
                    if let b = ElementFormat.band(m) { Text(b).font(.caption).foregroundStyle(DS.text2) }
                }
                if onSelect != nil { Image(systemName: "scope").font(.caption).foregroundStyle(DS.accent) }
            }
            .padding(.leading, 34).padding(.trailing, 14).padding(.vertical, 8)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(onSelect == nil)
    }
}

/// Eén element oplichten op de gevelfoto (vanuit de lijst van het hele gebouw).
struct ElementHighlightSheet: View {
    let image: UIImage
    let scan: FacadeScan
    let measure: ElementMeasure
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    FacadeOverlay(image: image, scan: scan, highlight: measure.elementId)
                        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    Text(ElementFormat.name(measure)).font(.title3.weight(.bold)).foregroundStyle(DS.text)
                    Text(ElementFormat.value(measure) + (ElementFormat.band(measure).map { " · " + $0 } ?? "")).foregroundStyle(DS.text)
                    if let mat = measure.material { Text("Materiaal: \(mat)").font(.subheadline).foregroundStyle(DS.text2) }
                }
                .padding(DS.pad)
            }
            .background(DS.canvas)
            .navigationTitle("Gevel op het \(scan.facing)").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Klaar") { dismiss() } } }
        }
    }
}
