import Gevelscan
import PhotoWalkCore
import SwiftUI

/// Teksten in gewone taal voor de gevelinventaris (voor VvE-bestuurders en beheerders).
enum GevelText {
    static func number(_ v: Double, unit: String) -> String {
        if unit == "st" { return "\(Int(v.rounded())) st." }
        let s = String(format: "%.2f", v).replacingOccurrences(of: ".", with: ",")
        return unit == "m2" ? "\(s) m²" : "\(s) m"
    }

    static func value(_ v: ScanValue) -> String {
        guard let x = v.value else { return "Nog niet vast te stellen" }
        return number(x, unit: v.unit)
    }

    static func color(_ o: Outcome) -> Color {
        switch o {
        case .BETROUWBAAR_VASTGESTELD: return .green
        case .VOORLOPIG_VASTGESTELD: return .orange
        case .NIET_VAST_TE_STELLEN: return .gray
        }
    }

    static func origin(_ o: ValueOrigin) -> String {
        switch o {
        case .LIDAR_PLANE_MEASUREMENT: return "gemeten met de dieptesensor (LiDAR)"
        case .REFERENCE_DISTANCE: return "berekend met jouw referentiemaat"
        case .DERIVED_SEGMENTATION_ON_MEASURED_PLANE: return "afgeleid uit de foto, op het gemeten kozijnvlak (geen directe meting)"
        case .DERIVED_CALCULATION: return "berekend uit de gemeten maten"
        case .COUNTED_FROM_ASSOCIATION: return "geteld over alle foto's (zelfde kozijn telt één keer)"
        case .MODEL_CLASSIFICATION: return "herkend door een model (niet gevalideerd)"
        case .USER_INPUT: return "door jou ingevuld"
        case .NONE: return "onbekend"
        }
    }

    /// Reden in gewone taal; onbekende codes worden als code getoond (niets verbergen).
    static func reason(_ code: String) -> String {
        switch code {
        case "GEOMETRIE_NIET_IN_HET_VELD_GEVALIDEERD": return "de meetmethode is nog niet getoetst aan handmetingen"
        case "HERKENNING_NIET_GEVALIDEERD": return "de automatische herkenning is nog niet getoetst op echte gevels"
        case "ENKEL_STANDPUNT": return "er is maar één foto van dit kozijn"
        case "BUITENCONTOUR_NIET_BEVESTIGD": return "niet zeker dat dit de buitenrand van het kozijn is"
        case "IDENTITEIT_ONZEKER", "MOGELIJK_DUBBEL", "MOGELIJK_DUBBEL_GETELD": return "mogelijk hetzelfde kozijn als een ander"
        case "DUBBELTELLING_NIET_UITGESLOTEN": return "dubbel tellen is niet uit te sluiten"
        case "GEEN_RUIMTELIJKE_METING": return "geen dieptemeting om kozijnen te vergelijken"
        case "MEERDERE_SESSIES", "ONBEKENDE_SESSIE": return "foto's uit verschillende scanmomenten"
        case "GEVELS_ONDERLING_NIET_VERGELEKEN": return "gevels zijn onderling niet vergeleken"
        case "OBJECT_AFGESNEDEN": return "het kozijn staat niet helemaal op de foto"
        case "GEEN_MAAT", "GEEN_METING": return "geen betrouwbare maat"
        case "NO_DEPTH", "GEEN_LIDAR": return "geen dieptegegevens (LiDAR) bij deze foto"
        case "GEEN_MODEL_VOOR_DRAAIENDE_DELEN": return "de app kan draaiende delen nog niet zelf herkennen; vul ze in"
        case "GEEN_MODEL_VOOR_DEUR_OF_RAAM": return "de app kan raam en deur nog niet zelf onderscheiden"
        case "NIET_ALLE_KOZIJNEN_GECLASSIFICEERD": return "niet van elk kozijn is bekend of het een raam of deur is"
        case "NIET_ALLE_OBJECTEN_BEPAALD": return "niet voor elk kozijn bekend"
        case "GEEN_GLASVLAKKEN_HERKEND": return "geen glasvlakken herkend"
        case "GLAS_OP_EEN_FOTO": return "glas is maar op één foto gezien"
        case "SPIEGELING_IN_GLAS": return "het glas spiegelt"
        case "GLASVLAKKEN_OVERLAPPEN": return "de herkende glasvlakken overlappen elkaar"
        case "KOZIJNMAAT_VOORLOPIG": return "de kozijnmaat is nog voorlopig"
        case "GEEN_OBJECTEN", "GEEN_OBJECTEN_HERKEND": return "geen kozijnen herkend (dat is geen bewijs dat er geen zijn)"
        case "GEEN_FOTOS": return "nog geen foto's van deze gevel"
        case "DEKKING_ONBEKEND": return "onbekend welk deel van de gevel is gefotografeerd"
        case "GEVELOMVANG_ONBEKEND": return "de app weet niet hoe groot de gevel is; loop na of alle kozijnen zijn vastgelegd"
        case "GATEN_IN_DEKKING": return "een deel van de gevel is nog niet gefotografeerd"
        case "OBJECTEN_NIET_BETROUWBAAR_VASTGESTELD": return "niet alle kozijnen zijn betrouwbaar vastgesteld"
        case "AANVULLENDE_OPNAMES_NODIG": return "er zijn nog extra foto's nodig"
        case "SINGLE_VIEWPOINT": return "maar één standpunt"
        case "GEEN_GEBREKENMODEL": return "de app kan gebreken nog niet zelf herkennen"
        default: return code
        }
    }

    static func reasons(_ codes: [String]) -> String {
        var seen: [String] = []
        for c in codes { let t = reason(c); if !seen.contains(t) { seen.append(t) } }
        return seen.joined(separator: " · ")
    }
}

/// Korte lijst "Nog nodig" op het beginscherm van de fotoronde: gerichte aanwijzingen voor aanvullende foto's.
struct GevelNeededSection: View {
    @EnvironmentObject var store: ScanStore

    var body: some View {
        let requests: [CaptureRequest] = store.gevelscan?.requests ?? []
        if !requests.isEmpty {
            Section("Nog nodig voor een volledige inventaris") {
                ForEach(Array(GevelNeededSection.unique(requests).prefix(3).enumerated()), id: \.offset) { _, text in
                    Label(text, systemImage: "camera.badge.ellipsis").font(.footnote)
                }
            }
            .accessibilityIdentifier("gevelNeeded")
        }
    }

    /// Zelfde aanwijzing voor meerdere kozijnen wordt één regel.
    static func unique(_ requests: [CaptureRequest]) -> [String] {
        var out: [String] = []
        for r in requests where !out.contains(r.textNL) { out.append(r.textNL) }
        return out
    }
}

/// Gevelinventarisatie: voortgang, volledigheid per gevel, gescheiden hoeveelheden, herkende kozijnen en wat nog nodig is.
struct GevelInventoryView: View {
    @EnvironmentObject var store: ScanStore

    var body: some View {
        List {
            statusSection
            if let r = store.gevelscan, !store.keyframes.isEmpty {
                ForEach(r.facades, id: \.facadeId) { f in GevelFacadeSection(facade: f) }
                if r.facades.count > 1 { buildingSection(r) }
                limitsSection(r)
            }
        }
        .navigationTitle("Gevelinventarisatie").navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("gevelInventory")
        .task { await store.runGevelscan() }
    }

    @ViewBuilder private var statusSection: some View {
        Section("Automatische analyse") {
            if store.gevelscanRunning || !store.analyzing.isEmpty {
                HStack { ProgressView(); Text(store.analyzing.isEmpty ? "Inventaris wordt bijgewerkt…" : "Foto's worden geanalyseerd…").font(.subheadline) }
            }
            if store.keyframes.isEmpty {
                Text("Nog geen foto's. Maak eerst foto's van de gevel.").font(.subheadline).foregroundStyle(.secondary).accessibilityIdentifier("gevelEmpty")
            } else if let r = store.gevelscan {
                let objects: [InventoryObject] = r.objects
                let measured: Int = objects.filter { $0.geometry.area.value != nil }.count
                Text("\(r.photoAssessments.count) foto's · \(objects.count) kozijnen herkend · \(measured) met maat").font(.subheadline).accessibilityIdentifier("gevelSummary")
                Text("De uitkomsten zijn voorlopig. De app verwerkt nog niets automatisch in je MJOP: de meetmethode en de herkenning zijn nog niet getoetst aan handmetingen op echte gevels.")
                    .font(.footnote).foregroundStyle(.secondary)
            } else {
                Text("De inventaris wordt opgebouwd…").font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private func buildingSection(_ r: GevelscanResult) -> some View {
        Section("Hele gebouw") { GevelTotalsRows(totals: r.building) }
    }

    @ViewBuilder private func limitsSection(_ r: GevelscanResult) -> some View {
        Section("Wat de app nu wel en niet zelf herkent") {
            Text("Wel: mogelijke kozijnen en glasvlakken (vormherkenning, geen getraind kozijnmodel) en het gevelvlak (dieptesensor).").font(.footnote)
            Text("Nog niet: " + r.recognition.notRecognizable.map { $0.labelNL.lowercased() }.joined(separator: ", ") + ". Dat blijft daarom open of vul je zelf in.")
                .font(.footnote).foregroundStyle(.secondary)
            Text("Gebreken (zoals houtrot of afbladderend schilderwerk) worden nog niet automatisch herkend. De app geeft geen NEN 2767-conditiescore.").font(.footnote).foregroundStyle(.secondary)
            if !r.mismatchedPhotoIds.isEmpty {
                Text("Foto \(r.mismatchedPhotoIds.joined(separator: ", ")) lijkt bij een andere gevel te horen. Controleer de indeling.").font(.footnote).foregroundStyle(.orange)
            }
        }
    }
}

struct GevelOutcomeBadge: View {
    let outcome: Outcome
    var body: some View {
        Text(outcome.labelNL).font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2)
            .background(GevelText.color(outcome).opacity(0.18)).foregroundStyle(GevelText.color(outcome)).clipShape(Capsule())
    }
}

/// De gescheiden hoeveelheden van een gevel of gebouw. Ze worden nooit bij elkaar opgeteld of in elkaar omgerekend.
struct GevelTotalsRows: View {
    let totals: InventoryTotals
    var body: some View {
        GevelQuantityRow(title: "Aantal kozijnen", value: totals.frameCount)
        GevelQuantityRow(title: "Kozijnoppervlak (buitenmaat)", value: totals.frameAreaGross)
        GevelQuantityRow(title: "Glasoppervlak", value: totals.glassArea)
        GevelQuantityRow(title: "Draaiende delen", value: totals.operableParts)
        GevelQuantityRow(title: "Vaste delen", value: totals.fixedParts)
    }
}

struct GevelQuantityRow: View {
    let title: String
    let value: ScanValue
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(title).font(.subheadline)
                Spacer()
                Text(GevelText.value(value)).font(.subheadline.bold()).foregroundStyle(value.value == nil ? .secondary : .primary)
            }
            if value.value != nil {
                HStack(spacing: 6) {
                    GevelOutcomeBadge(outcome: value.outcome)
                    Text(GevelText.origin(value.origin)).font(.caption2).foregroundStyle(.secondary)
                }
            }
            if !value.missing.isEmpty { Text(GevelText.reasons(value.missing)).font(.caption2).foregroundStyle(.secondary) }
            if value.value == nil, let p = value.partial { Text("Voor een deel bekend: \(GevelText.number(p, unit: value.unit)). Het totaal is nog niet compleet.").font(.caption2).foregroundStyle(.orange) }
        }
    }
}

struct GevelFacadeSection: View {
    @EnvironmentObject var store: ScanStore
    let facade: FacadeInventory

    var body: some View {
        Section("Gevel \(facade.facadeId)") {
            HStack {
                Text("Volledigheid").font(.subheadline)
                Spacer()
                GevelOutcomeBadge(outcome: facade.completeness)
            }
            if !facade.completenessReasons.isEmpty { Text(GevelText.reasons(facade.completenessReasons)).font(.caption2).foregroundStyle(.secondary) }
            GevelCoverageView(coverage: facade.coverage)
            GevelTotalsRows(totals: facade.totals)
            ForEach(Array(GevelNeededSection.unique(facade.requests).enumerated()), id: \.offset) { _, text in
                Label(text, systemImage: "camera.badge.ellipsis").font(.footnote).foregroundStyle(.orange)
            }
            ForEach(Array(facade.objects.enumerated()), id: \.element.id) { k, o in
                NavigationLink { GevelObjectView(objectId: o.id).environmentObject(store) } label: { GevelObjectRow(object: o, index: k + 1) }
            }
        }
    }
}

struct GevelObjectRow: View {
    let object: InventoryObject
    let index: Int
    var body: some View {
        let g: FrameGeometry = object.geometry
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text("\(object.elementClass.labelNL) \(index)").font(.subheadline)
                Spacer()
                GevelOutcomeBadge(outcome: object.outcome)
            }
            if let w = g.width.value, let h = g.height.value {
                Text("\(GevelText.number(w, unit: "m")) × \(GevelText.number(h, unit: "m")) · \(object.photoIds.count) \(object.photoIds.count == 1 ? "foto" : "foto's")").font(.caption).foregroundStyle(.secondary)
            } else {
                Text("Geen maat · \(object.photoIds.count) \(object.photoIds.count == 1 ? "foto" : "foto's")").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

/// Welk deel van de gevel is gefotografeerd: een raster van het gevelvlak (donker = meerdere foto's, licht = één foto, leeg = nog niet).
struct GevelCoverageView: View {
    let coverage: FacadeCoverage

    var body: some View {
        if coverage.determinable, coverage.columns > 0, coverage.rows > 0, let f = coverage.coveredFraction {
            VStack(alignment: .leading, spacing: 4) {
                Text("Gefotografeerd: \(Int((f * 100).rounded())) % van het vastgelegde gevelvlak").font(.caption)
                Canvas { context, size in
                    let cw: CGFloat = size.width / CGFloat(coverage.columns), ch: CGFloat = size.height / CGFloat(coverage.rows)
                    for r in 0..<coverage.rows {
                        for c in 0..<coverage.columns {
                            let n: Int = coverage.cellViews[r * coverage.columns + c]
                            let color: Color = n >= 2 ? Color.green.opacity(0.75) : (n == 1 ? Color.green.opacity(0.35) : Color.gray.opacity(0.15))
                            context.fill(Path(CGRect(x: CGFloat(c) * cw, y: CGFloat(r) * ch, width: cw + 0.5, height: ch + 0.5)), with: .color(color))
                        }
                    }
                }
                .frame(height: 70).clipShape(RoundedRectangle(cornerRadius: 4))
                .accessibilityLabel("Dekking van de gevel")
            }
        } else {
            Text("Onbekend welk deel van de gevel is gefotografeerd (daarvoor is een dieptemeting nodig).").font(.caption).foregroundStyle(.secondary)
        }
    }
}

/// Eén kozijn: maten, indeling, herkomst, bewijs (foto's) en wat de gebruiker zelf kan aanvullen.
struct GevelObjectView: View {
    @EnvironmentObject var store: ScanStore
    let objectId: String

    private var object: InventoryObject? { store.gevelscan?.objects.first { $0.id == objectId } }
    @State private var editingParts = false
    @State private var draftOperable = 0
    @State private var draftFixed = 0

    var body: some View {
        List {
            if let o = object {
                dimensionSection(o)
                layoutSection(o)
                userSection(o)
                evidenceSection(o)
            } else {
                Text("Dit kozijn staat niet meer in de inventaris (bijvoorbeeld samengevoegd met een ander kozijn).").font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Kozijn").navigationBarTitleDisplayMode(.inline)
    }

    @ViewBuilder private func dimensionSection(_ o: InventoryObject) -> some View {
        let g: FrameGeometry = o.geometry
        Section("Buitenmaat van het kozijn") {
            HStack { Text("Uitkomst").font(.subheadline); Spacer(); GevelOutcomeBadge(outcome: o.outcome) }
            if !o.outcomeReasons.isEmpty { Text(GevelText.reasons(o.outcomeReasons)).font(.caption2).foregroundStyle(.secondary) }
            GevelQuantityRow(title: "Breedte", value: g.width)
            GevelQuantityRow(title: "Hoogte", value: g.height)
            GevelQuantityRow(title: "Oppervlak (breedte × hoogte)", value: g.area)
            if let s = g.area.sigma, g.area.value != nil {
                Text("Geschatte onzekerheid: ± \(GevelText.number(s, unit: "m2")) (rekenmodel, niet getoetst aan handmetingen)").font(.caption2).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private func layoutSection(_ o: InventoryObject) -> some View {
        let g: FrameGeometry = o.geometry
        Section("Indeling") {
            GevelQuantityRow(title: "Vakken (glasvlakken)", value: g.sections)
            GevelQuantityRow(title: "Glasoppervlak", value: g.glassArea)
            GevelQuantityRow(title: "Draaiende delen", value: g.operableParts)
            GevelQuantityRow(title: "Vaste delen", value: g.fixedParts)
            if !g.mullions.isEmpty || !g.transoms.isEmpty {
                Text("\(g.mullions.count) tussenstijl(en), \(g.transoms.count) tussendorpel(s) (afgeleid uit de ruimte tussen de glasvlakken)").font(.caption).foregroundStyle(.secondary)
            }
            Text("Eén kozijn met meerdere vakken telt als één kozijn. Het glasoppervlak is afgeleid uit de foto en is geen directe meting.").font(.caption2).foregroundStyle(.secondary)
            ForEach(g.notes, id: \.self) { n in Text(n).font(.caption2).foregroundStyle(.orange) }
        }
    }

    @ViewBuilder private func userSection(_ o: InventoryObject) -> some View {
        if let key = o.sightingIds.first {
            let saved: UserParts? = o.sightingIds.compactMap { store.userParts[$0] }.first
            Section("Zelf aanvullen") {
                // Er wordt pas iets vastgelegd als je op "Vastleggen" tikt: een niet-ingevuld aantal is onbekend, geen 0.
                if let p = saved, !editingParts {
                    Text("Door jou ingevuld: \(p.operableParts) draaiend, \(p.fixedParts) vast").font(.subheadline)
                    Button("Wijzigen") { draftOperable = p.operableParts; draftFixed = p.fixedParts; editingParts = true }
                    Button("Invoer verwijderen", role: .destructive) { for id in o.sightingIds { store.userParts[id] = nil }; changed() }
                } else if editingParts {
                    Stepper("Draaiende delen: \(draftOperable)", value: $draftOperable, in: 0...40)
                    Stepper("Vaste delen: \(draftFixed)", value: $draftFixed, in: 0...40)
                    Button("Vastleggen") {
                        // de invoer hangt aan de eerste waarneming van dit kozijn; invoer op een andere waarneming van hetzelfde kozijn vervalt
                        for id in o.sightingIds { store.userParts[id] = nil }
                        store.userParts[key] = UserParts(operableParts: draftOperable, fixedParts: draftFixed)
                        editingParts = false
                        changed()
                    }.accessibilityIdentifier("gevelPartsSave")
                    Button("Annuleren", role: .cancel) { editingParts = false }
                } else {
                    Button("Draaiende en vaste delen zelf invullen") { draftOperable = 0; draftFixed = 0; editingParts = true }
                }
                Picker("Soort", selection: Binding(
                    get: { store.userClasses[key] ?? ElementClass.KOZIJN },
                    set: { c in
                        for id in o.sightingIds { store.userClasses[id] = nil }
                        if c != ElementClass.KOZIJN { store.userClasses[key] = c }
                        changed()
                    })) {
                    Text("Niet aangegeven").tag(ElementClass.KOZIJN)
                    Text("Raamkozijn").tag(ElementClass.RAAM)
                    Text("Deurkozijn").tag(ElementClass.DEUR)
                }
            }
        }
    }

    @ViewBuilder private func evidenceSection(_ o: InventoryObject) -> some View {
        Section("Bewijs") {
            ForEach(o.photoIds, id: \.self) { pid in
                NavigationLink("Foto \(pid) met de herkende contouren") { PhotoResultView(frameId: pid, simple: true).environmentObject(store) }
            }
            Text("Meetmethode: \(o.geometry.scaleMethod) · \(o.geometry.independentViewpoints) onafhankelijke standpunt(en)").font(.caption2).foregroundStyle(.secondary)
            Text("Herkenning: \(o.detectors.map { $0.name }.joined(separator: ", "))").font(.caption2).foregroundStyle(.secondary)
            Text("Kenmerk: \(o.id)").font(.caption2).foregroundStyle(.secondary).textSelection(.enabled)
            ForEach(o.condition, id: \.id) { c in
                Text(c.kind == ConditionKind.NIET_BEOORDEELBAAR ? "Conditie: niet beoordeeld (\(GevelText.reasons(c.reasons)))" : "\(c.category?.labelNL ?? "Waarneming") (mogelijke aanwijzing)")
                    .font(.caption2).foregroundStyle(.secondary)
            }
        }
    }

    private func changed() {
        store.persist()
        Task { await store.runGevelscan() }
    }
}
