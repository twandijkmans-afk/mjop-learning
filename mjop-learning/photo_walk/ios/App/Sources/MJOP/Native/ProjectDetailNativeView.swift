import SwiftUI

/// Projectscherm: foto bovenaan, daaronder de tabs Overzicht, MJOP, Gevels en Documenten. Deel 1 toont het Overzicht met echte gegevens;
/// de andere tabs worden in de volgende delen gebouwd.
struct ProjectDetailNativeView: View {
    let project: Project
    @Environment(\.dismiss) private var dismiss
    @State private var tab: Tab = .overzicht
    @State private var showScan = false

    enum Tab: String, CaseIterable { case overzicht = "Overzicht", mjop = "MJOP", gevels = "Gevels", documenten = "Documenten" }

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                Color.clear.frame(height: 300)
                    .background { ProjectPhotoView(project: project, attribution: .bottomTrailing) }
                    .clipped()
                VStack(alignment: .leading, spacing: 16) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(project.naam).font(.system(size: 26, weight: .bold)).foregroundStyle(DS.text).accessibilityIdentifier("projectTitle")
                            if let a = project.fullAddress {
                                Label(a, systemImage: "mappin.and.ellipse").font(.subheadline).foregroundStyle(DS.text2)
                            }
                        }
                        Spacer()
                    }
                    tabPicker
                    switch tab {
                    case .overzicht: overzicht
                    case .mjop: MJOPView(project: project, showsTitle: false)
                    case .gevels:
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(alignment: .top, spacing: 12) {
                                DSIcon(systemName: "viewfinder")
                                VStack(alignment: .leading, spacing: 3) {
                                    Text("Rondje om het gebouw").font(.headline).foregroundStyle(DS.text)
                                    Text("Per gevel één foto. Claude herkent kozijnen, metselwerk en afvoeren; de app rekent de maten met de gevelbreedte uit de BAG.").font(.subheadline).foregroundStyle(DS.text2)
                                }
                            }
                            Button { showScan = true } label: { Label("Gevels scannen", systemImage: "camera.fill") }.buttonStyle(DSPrimaryButton())
                                .accessibilityIdentifier("projectScan")
                        }
                        .padding(16).dsCard(radius: 20)
                        KozijnStaatSection(project: project) { showScan = true }
                    case .documenten: DocumentsSection(project: project)
                    }
                }
                .padding(.horizontal, DS.pad).padding(.top, 22).padding(.bottom, 120)
                .background(DS.canvas, in: UnevenRoundedTop(radius: 30))
                .offset(y: -30)
            }
        }
        .background(DS.canvas)
        .ignoresSafeArea(edges: .top)
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: $showScan) { GevelscanFlow(initialProject: project) }
        .overlay(alignment: .topLeading) {
            Button { dismiss() } label: { DSGlassCircle(systemName: "chevron.left") }
                .padding(.leading, 16).padding(.top, 6)
                .accessibilityLabel("Terug")
        }
    }

    private var tabPicker: some View {
        HStack(spacing: 4) {
            ForEach(Tab.allCases, id: \.self) { t in
                Button { withAnimation(.dsSpring) { tab = t } } label: {
                    Text(t.rawValue).font(.subheadline.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.8)
                        .foregroundStyle(tab == t ? Color.white : DS.text2)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(tab == t ? DS.accent : Color.clear, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(tab == t ? .isSelected : [])
            }
        }
        .padding(4)
        .background(DS.accentSoft.opacity(0.7), in: Capsule())
    }

    private var overzicht: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                StatTile(icon: "house", value: project.bouwjaar.map(String.init) ?? "–", label: "Bouwjaar")
                StatTile(icon: "doc.text", value: project.postenAantal.map(String.init) ?? "–", label: "Posten")
                StatTile(icon: "chart.bar", value: project.geraamdTotaal.map(DSFormat.euros) ?? "–", label: project.periodeTot.map { "Tot \($0)" } ?? "Geraamd")
            }
            if let n = project.appartementen {
                Text(n == 1 ? "1 appartement" : "\(n) appartementen").font(.subheadline).foregroundStyle(DS.text2).padding(.horizontal, 4)
            }
        }
    }

    private func next(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            DSIcon(systemName: "hammer")
            VStack(alignment: .leading, spacing: 3) {
                Text("Volgt in een volgend deel").font(.headline).foregroundStyle(DS.text)
                Text(text).font(.subheadline).foregroundStyle(DS.text2)
            }
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading).dsCard(radius: 20)
    }
}

struct StatTile: View {
    let icon: String
    let value: String
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            DSIcon(systemName: icon, size: 30)
            VStack(alignment: .leading, spacing: 1) {
                Text(value).font(.system(size: 19, weight: .bold)).foregroundStyle(DS.text).lineLimit(1).minimumScaleFactor(0.7)
                Text(label).font(.caption).foregroundStyle(DS.text2).lineLimit(1)
            }
        }
        .padding(12).frame(maxWidth: .infinity, alignment: .leading)
        .dsCard(radius: 18)
        .accessibilityElement(children: .combine)
    }
}

/// Vorm met alleen bovenaan ronde hoeken (UnevenRoundedRectangle bestaat pas vanaf iOS 17).
struct UnevenRoundedTop: Shape {
    let radius: CGFloat
    func path(in rect: CGRect) -> Path {
        Path(UIBezierPath(roundedRect: rect, byRoundingCorners: [.topLeft, .topRight], cornerRadii: CGSize(width: radius, height: radius)).cgPath)
    }
}
