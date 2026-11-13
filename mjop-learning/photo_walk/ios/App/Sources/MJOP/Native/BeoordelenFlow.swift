import MJOPEngine
import SwiftUI
import UIKit

/// De staat van de posten beoordelen, één voor één (NEN 2767-schaal 1–6, vereenvoudigd). Twijfel: overslaan; dan blijft de gebruikelijke levensduur staan.
struct BeoordelenFlow: View {
    @State var model: ProjectModel
    let onDone: (ProjectModel) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var index = 0

    static let scale: [(Int, String, String)] = [
        (1, "Uitstekend", "Als nieuw"), (2, "Goed", "Kleine gebruikssporen"), (3, "Redelijk", "Plaatselijk slijtage of kleine gebreken"),
        (4, "Matig", "Duidelijke gebreken, onderhoud nodig"), (5, "Slecht", "Ernstige gebreken"), (6, "Zeer slecht", "Einde levensduur"),
    ]

    private var el: PlanElement? { model.elements.indices.contains(index) ? model.elements[index] : nil }

    var body: some View {
        NavigationStack {
            Group {
                if let el {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 14) {
                            ProgressView(value: Double(index), total: Double(model.elements.count)).tint(DS.accent)
                            HStack(spacing: 14) {
                                DSIcon(systemName: elementIcon(for: el.key), size: 56)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(el.naam.uppercased()).font(.caption.weight(.bold)).foregroundStyle(DS.accent).lineLimit(2)
                                    Text("\(el.categorie) · elke \(el.cyclus) jaar").font(.footnote).foregroundStyle(DS.text2)
                                }
                            }
                            Text("Hoe ziet het eruit?").font(.system(size: 28, weight: .bold)).foregroundStyle(DS.text)
                            VStack(spacing: 8) {
                                ForEach(Self.scale, id: \.0) { s in
                                    let on = el.conditie == s.0
                                    Button { choose(s.0) } label: {
                                        HStack(spacing: 12) {
                                            Text("\(s.0)").font(.headline).frame(width: 32, height: 32)
                                                .background(on ? Color.white.opacity(0.22) : DS.accentSoft, in: Circle())
                                                .foregroundStyle(on ? Color.white : DS.accent)
                                            VStack(alignment: .leading, spacing: 1) {
                                                Text(s.1).font(.headline)
                                                Text(s.2).font(.caption).opacity(on ? 0.85 : 1).foregroundStyle(on ? Color.white : DS.text2)
                                            }
                                            Spacer()
                                        }
                                        .foregroundStyle(on ? Color.white : DS.text)
                                        .padding(12)
                                        .background(on ? DS.accent : DS.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                                        .shadow(color: on ? DS.accent.opacity(0.3) : .clear, radius: 8, x: 0, y: 5)
                                    }
                                    .buttonStyle(.plain)
                                    .accessibilityIdentifier("score-\(s.0)")
                                }
                            }
                            Text("Schaal volgens NEN 2767 (vereenvoudigd, geen gecertificeerde inspectie). Een beoordeling schuift het jaar van de post naar voren of naar achteren.")
                                .font(.footnote).foregroundStyle(DS.text2)
                        }
                        .padding(.horizontal, DS.pad).padding(.bottom, 110)
                    }
                    .safeAreaInset(edge: .bottom) {
                        HStack(spacing: 10) {
                            Button("Overslaan") { next() }.buttonStyle(DSSecondaryButton())
                            Button("Volgende") { next() }.buttonStyle(DSPrimaryButton()).disabled(el.conditie == nil)
                        }
                        .padding(.horizontal, DS.pad).padding(.vertical, 10)
                        .background(.bar)
                    }
                } else {
                    VStack(spacing: 14) {
                        Spacer()
                        DSIcon(systemName: "checkmark", size: 72)
                        Text("Klaar").font(.title.weight(.bold))
                        Text("\(model.beoordeeld) van \(model.elements.count) posten beoordeeld. De planning is bijgewerkt.").foregroundStyle(DS.text2).multilineTextAlignment(.center)
                        Spacer()
                        Button("Opslaan") { onDone(model); dismiss() }.buttonStyle(DSPrimaryButton()).padding(.horizontal, DS.pad)
                    }
                    .padding(.bottom, 20)
                }
            }
            .background(DS.canvas.ignoresSafeArea())
            .navigationTitle(el == nil ? "" : "\(index + 1) van \(model.elements.count)").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Stop") { onDone(model); dismiss() } }
            }
        }
    }

    private func choose(_ s: Int) {
        UISelectionFeedbackGenerator().selectionChanged()
        model.elements[index].conditie = s
    }

    private func next() { withAnimation(.dsSpring) { index += 1 } }
}
