import Charts
import MJOPEngine
import SwiftUI

/// MJOP van één project: Planning, Kosten en Rapport. Alles wordt in de app berekend met MJOPEngine; niets wordt geschat zonder dat te zeggen.
struct MJOPView: View {
    let project: Project
    var showsTitle = true
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @State private var model: ProjectModel?
    @State private var error: String?
    @State private var section: Part = .planning

    enum Part: String, CaseIterable { case planning = "Planning", kosten = "Kosten", rapport = "Rapport" }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if showsTitle {
                VStack(alignment: .leading, spacing: 2) {
                    Text(project.naam).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text2)
                    Text("MJOP").font(.system(size: 32, weight: .bold)).foregroundStyle(DS.text)
                }
                .padding(.horizontal, 4)
            }
            DSSegmented(selection: $section, options: Part.allCases, title: \.rawValue)
            if let error { DSNotice(kind: .warn, text: error) }
            if let m = model {
                switch section {
                case .planning: PlanningSection(model: m)
                case .kosten: KostenSection(model: Binding(get: { m }, set: { model = $0 }), save: save)
                case .rapport: RapportSection(project: project, model: m)
                }
            } else if error == nil {
                ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
            }
        }
        .task(id: project.id) { await load() }
    }

    private func load() async {
        do { model = try await store.loadModel(project, account: account); error = nil }
        catch { self.error = error.localizedDescription }
    }

    private func save(_ m: ProjectModel) {
        model = m
        Task {
            do { try await store.saveModel(m, for: project, account: account) }
            catch { self.error = error.localizedDescription }
        }
    }
}

/// Keuzebalk met blauwe pil.
struct DSSegmented<T: Hashable>: View {
    @Binding var selection: T
    let options: [T]
    let title: KeyPath<T, String>

    var body: some View {
        HStack(spacing: 4) {
            ForEach(options, id: \.self) { o in
                Button { withAnimation(.dsSpring) { selection = o } } label: {
                    Text(o[keyPath: title]).font(.subheadline.weight(.semibold)).lineLimit(1)
                        .foregroundStyle(selection == o ? Color.white : DS.text2)
                        .frame(maxWidth: .infinity, minHeight: 36)
                        .background(selection == o ? DS.accent : Color.clear, in: Capsule())
                        .shadow(color: DS.accent.opacity(selection == o ? 0.3 : 0), radius: 6, x: 0, y: 3)
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(selection == o ? .isSelected : [])
                .accessibilityIdentifier("seg-\(o[keyPath: title])")
            }
        }
        .padding(4)
        .background(DS.accentSoft.opacity(0.7), in: Capsule())
    }
}

// MARK: - Planning

struct PlanningSection: View {
    let model: ProjectModel

    var body: some View {
        let per = model.perYear
        let years = Array(ProjectModel.year...(ProjectModel.year + Engine.horizon - 1))
        let maxV = max(per.values.max() ?? 1, 1)
        let peak = model.peak?.jaar
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Onderhoud \(years.first!)–\(years.last!)").font(.footnote).foregroundStyle(DS.text2)
                        Text(DSFormat.euros(euroInt(model.total))).font(.system(size: 28, weight: .bold)).foregroundStyle(DS.text)
                    }
                    Spacer()
                    Text("\(model.elements.count) posten").font(.footnote.weight(.semibold)).foregroundStyle(DS.text2)
                }
                HStack(alignment: .bottom, spacing: 6) {
                    ForEach(years, id: \.self) { y in
                        let v = per[y] ?? 0
                        let h = max(4, CGFloat(truncating: NSDecimalNumber(decimal: v / maxV)) * 110)
                        VStack(spacing: 5) {
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .fill(y == peak ? AnyShapeStyle(LinearGradient(colors: [Color(hex: 0x5B74FF), DS.accent], startPoint: .top, endPoint: .bottom)) : AnyShapeStyle(DS.accent.opacity(0.22)))
                                .frame(height: h)
                            Text(String(y % 100)).font(.system(size: 10, weight: y == peak ? .bold : .regular)).foregroundStyle(y == peak ? DS.text : DS.text2)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .frame(height: 130, alignment: .bottom)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Kosten per jaar; duurste jaar \(peak.map(String.init) ?? "onbekend")")
            }
            .padding(16).dsCard()

            ForEach(years.filter { per[$0] != nil }, id: \.self) { y in
                let items = model.plan.filter { $0.jaar == y }
                VStack(alignment: .leading, spacing: 8) {
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(String(y)).font(.title3.weight(.bold)).foregroundStyle(DS.text)
                        if y == peak { DSChip(text: "Duurste jaar", fg: .white, bg: Color(hex: 0x0E1424)) }
                        Spacer()
                        Text(DSFormat.euros(euroInt(per[y] ?? 0))).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text2)
                    }
                    .padding(.horizontal, 4).padding(.top, 6)
                    VStack(spacing: 0) {
                        ForEach(Array(items.enumerated()), id: \.offset) { i, c in
                            HStack(spacing: 12) {
                                DSIcon(systemName: elementIcon(for: c.key), size: 32)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(c.naam).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text).lineLimit(2)
                                    Text(meta(c.key)).font(.caption).foregroundStyle(DS.text2)
                                }
                                Spacer(minLength: 6)
                                Text(DSFormat.euros(euroInt(c.bedrag))).font(.subheadline.weight(.semibold)).foregroundStyle(DS.text)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10)
                            if i < items.count - 1 { Divider().padding(.leading, 58) }
                        }
                    }
                    .dsCard(radius: 18)
                }
            }
            Text("Bedragen zijn geraamd met standaardbedragen (geen offertes), prijspeil \(ProjectModel.year).").font(.caption).foregroundStyle(DS.text2).padding(.horizontal, 4)
        }
    }

    private func meta(_ key: String) -> String {
        guard let el = model.elements.first(where: { $0.key == key }) else { return "" }
        var parts = ["\(el.categorie) · elke \(el.cyclus) jaar"]
        if el.conditie == nil { parts.append("niet beoordeeld") }
        return parts.joined(separator: " · ")
    }
}

func elementIcon(for key: String) -> String {
    if key.hasPrefix("dak") { return "house" }
    if key.contains("kozijn") || key.contains("schilder") { return "window.casement" }
    if key.contains("gevel") || key.contains("voeg") { return "square.grid.3x3" }
    if key == "steiger" { return "ladder" }
    if key == "intercom" { return "bell" }
    if key == "riolering" { return "drop" }
    if key == "trappenhuis" { return "stairs" }
    return "wrench.and.screwdriver"
}

func euroInt(_ d: Decimal) -> Int { NSDecimalNumber(decimal: Engine.roundEuro(d)).intValue }

// MARK: - Kosten

struct KostenSection: View {
    @Binding var model: ProjectModel
    let save: (ProjectModel) -> Void
    @State private var fondsText = ""
    @State private var bijdrage: Double = 0
    @State private var sliderMax: Double = 300

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if model.fonds == nil || model.bijdrage == nil {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Vul twee bedragen in").font(.headline).foregroundStyle(DS.text)
                    Text("Met het saldo van het reservefonds en de huidige bijdrage rekent de app uit of het fonds genoeg is. Onbekend blijft leeg.").font(.subheadline).foregroundStyle(DS.text2)
                    DSField(icon: "eurosign") {
                        TextField("Saldo reservefonds op 1 januari", text: $fondsText).keyboardType(.numberPad).accessibilityIdentifier("fondsField")
                    }
                    Button("Opslaan") {
                        var m = model
                        m.fonds = Decimal(string: fondsText.filter(\.isNumber))
                        if m.bijdrage == nil { m.bijdrage = Decimal(Int(bijdrage.rounded())) }
                        model = m; save(m)
                    }
                    .buttonStyle(DSPrimaryButton()).disabled(Decimal(string: fondsText.filter(\.isNumber)) == nil)
                }
                .padding(16).dsCard()
            }
            contribution
            if let fund = model.fund { fundChart(fund) }
            HStack(spacing: 10) {
                StatTile(icon: "chart.bar", value: DSFormat.euros(euroInt(model.total)), label: "Onderhoud 10 jaar")
                StatTile(icon: "flame", value: model.peak.map { String($0.jaar) } ?? "–", label: "Duurste jaar")
            }
        }
        .onAppear {
            bijdrage = NSDecimalNumber(decimal: model.bijdrage ?? 55).doubleValue
            sliderMax = max(300, (bijdrage * 2 / 50).rounded(.up) * 50, Double(model.required ?? 0) * 1.5)
        }
    }

    private var contribution: some View {
        let lowest = model.fund?.map(\.saldo).min()
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Bijdrage per maand").font(.footnote).foregroundStyle(DS.text2)
                Spacer()
                if let lowest {
                    lowest >= 0 ? DSChip(text: "Op schema", fg: DS.ok, bg: DS.okSoft) : DSChip(text: "Tekort", fg: DS.bad, bg: DS.warnSoft)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(DSFormat.euros(Int(bijdrage.rounded()))).font(.system(size: 44, weight: .bold)).foregroundStyle(DS.text).monospacedDigit()
                Text("per appartement").font(.subheadline).foregroundStyle(DS.text2)
            }
            Slider(value: $bijdrage, in: 0...sliderMax, step: 5, onEditingChanged: { editing in
                if !editing { var m = model; m.bijdrage = Decimal(Int(bijdrage.rounded())); model = m; save(m) }
            })
            .tint(DS.accent)
            HStack { Text("€ 0"); Spacer(); Text(DSFormat.euros(Int(sliderMax))) }.font(.caption).foregroundStyle(DS.text2)
                .accessibilityIdentifier("bijdrageSlider")
            if let r = model.required {
                Text("Nodig om het fonds tot \(ProjectModel.year + Engine.horizon - 1) niet onder € 0 te laten komen: **\(DSFormat.euros(r))** per maand.").font(.footnote).foregroundStyle(DS.text2)
            }
        }
        .padding(16).dsCard()
    }

    private func fundChart(_ fund: [FundYear]) -> some View {
        let low = fund.min { $0.saldo < $1.saldo }
        return VStack(alignment: .leading, spacing: 8) {
            Text("Stand reservefonds").font(.headline).foregroundStyle(DS.text)
            Chart {
                RuleMark(y: .value("Nul", 0)).foregroundStyle(DS.line).lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 4]))
                ForEach(fund, id: \.jaar) { f in
                    AreaMark(x: .value("Jaar", f.jaar), y: .value("Saldo", NSDecimalNumber(decimal: f.saldo).doubleValue))
                        .foregroundStyle(LinearGradient(colors: [DS.accent.opacity(0.25), DS.accent.opacity(0)], startPoint: .top, endPoint: .bottom))
                        .interpolationMethod(.monotone)
                    LineMark(x: .value("Jaar", f.jaar), y: .value("Saldo", NSDecimalNumber(decimal: f.saldo).doubleValue))
                        .foregroundStyle(DS.accent).lineStyle(StrokeStyle(lineWidth: 2.6, lineCap: .round)).interpolationMethod(.monotone)
                }
                if let low {
                    PointMark(x: .value("Jaar", low.jaar), y: .value("Saldo", NSDecimalNumber(decimal: low.saldo).doubleValue))
                        .foregroundStyle(low.saldo < 0 ? DS.bad : Color.orange).symbolSize(70)
                }
            }
            .chartXAxis { AxisMarks(values: [ProjectModel.year, ProjectModel.year + 4, ProjectModel.year + 9]) { v in AxisValueLabel { if let y = v.as(Int.self) { Text(String(y)) } } } }
            .chartYAxis(.hidden)
            .frame(height: 130)
            if let low {
                Text("Laagste stand \(DSFormat.euros(euroInt(low.saldo))) in \(String(low.jaar))").font(.footnote).foregroundStyle(low.saldo < 0 ? DS.bad : DS.text2)
            }
        }
        .padding(16).dsCard()
    }
}

// MARK: - Rapport

struct RapportSection: View {
    let project: Project
    let model: ProjectModel

    var body: some View {
        VStack(spacing: 14) {
            VStack(alignment: .leading, spacing: 8) {
                DSLogo(size: 26)
                Text("MJOP \(ProjectModel.year)–\(ProjectModel.year + Engine.horizon - 1)").font(.headline).foregroundStyle(Color(hex: 0x0E1424))
                Text(project.fullAddress ?? project.naam).font(.caption2).foregroundStyle(Color(hex: 0x667085))
                Color.clear.frame(height: 60).background { AerialPhotoView(address: project.fullAddress ?? project.naam) }.clipShape(RoundedRectangle(cornerRadius: 6))
                ForEach(0..<3, id: \.self) { i in RoundedRectangle(cornerRadius: 2).fill(Color(hex: 0xE1E6F0)).frame(width: CGFloat([150, 120, 140][i]), height: 4) }
            }
            .padding(16).frame(width: 200, height: 260, alignment: .topLeading)
            .background(Color.white, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .shadow(color: .black.opacity(0.16), radius: 20, x: 0, y: 14)
            .accessibilityHidden(true)
            DSChip(text: "Indicatie · \(model.beoordeeld) van \(model.elements.count) posten beoordeeld", fg: DS.warn, bg: DS.warnSoft)
            Text("Het rapport als PDF om te delen met het bestuur maak ik in een volgende stap.").font(.footnote).foregroundStyle(DS.text2).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 6)
    }
}
