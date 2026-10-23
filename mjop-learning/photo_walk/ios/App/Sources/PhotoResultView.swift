import SwiftUI
import UIKit
import PhotoWalkCore

/// Resultaatscherm direct na de foto: de originele foto met kaders rond alle kandidaat-kozijnen, voorlopige maten en een overzicht.
/// Kaders zijn KANDIDATEN van een algemene rechthoekdetector (niet gevalideerd als kozijndetector). Kleuren zijn alleen UI-feedback, geen goedkeuring.
struct PhotoResultView: View {
    @EnvironmentObject var store: ScanStore
    @Environment(\.dismiss) private var dismiss
    let frameId: String
    /// Fotoronde: gewone taal bovenaan; de bestaande technische weergave staat dan achter "Technische details". De losse scanner houdt de technische weergave.
    var simple = false
    @State private var image: UIImage? = nil
    @State private var selected: String? = nil
    @State private var showDetail = false
    @State private var noPoints: [Pixel] = []
    @State private var exportPath: String? = nil
    @AppStorage("hideNeutralBoxes") private var hideNeutral = false

    static func dimsText(_ r: LevelResult) -> String {
        guard r.ok, let w = r.width, let h = r.height else { return "UNKNOWN" }
        let dw = roundedMillimeters(w), dh = roundedMillimeters(h)
        var a = grossAreaM2(width: dw, height: dh), rounded = Decimal()
        NSDecimalRound(&rounded, &a, 2, .plain)
        return "\(decimalString(dw))×\(decimalString(dh)) m · \(NSDecimalNumber(decimal: rounded).stringValue) m²"
    }

    private var frameObservations: [Observation] { store.observations.filter { $0.frameId == frameId && !$0.rejected } }

    private var boxes: [BoxOverlayItem] {
        frameObservations.filter { o in !(hideNeutral && store.measures[o.id]?.feedback == .neutral && o.id != selected) }.map { o in
            let m = store.measures[o.id]
            let label = "\(store.shortName(ofObservation: o.id)) · \(m.map { Self.dimsText($0.result) } ?? "…")"
            return BoxOverlayItem(id: o.id, corners: o.corners, feedback: m?.feedback ?? .neutral, label: label, selected: o.id == selected)
        }
    }

    private func colorName(_ f: BoxFeedback?) -> String { switch f { case .green?: return "groen"; case .orange?: return "oranje"; default: return "grijs" } }

    private func reason(_ r: LevelResult) -> String {
        if r.ok { return r.flags.filter { $0.severity == .ADVISORY }.map { $0.code }.joined(separator: ", ") }
        return r.flags.first { $0.severity == .BLOCKING }.map { $0.instruction_nl } ?? "geen betrouwbare maat"
    }

    var body: some View {
        VStack(spacing: 4) {
            if let kf = store.keyframe(frameId), let img = image {
                FrameImageCanvas(frame: kf, image: img, points: $noPoints, maxPoints: 0, boxes: boxes, boxMode: true,
                                 onBoxTap: { id in selected = id; showDetail = true }, showReadout: false)
                    .accessibilityIdentifier("photoCanvas")
            } else { ProgressView().frame(maxHeight: .infinity) }
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    if simple {
                        simpleBlock()
                        DisclosureGroup("Technische details") { technicalBlock() }.font(.footnote).accessibilityIdentifier("technicalDetails")
                    } else {
                        technicalBlock()
                    }
                    HStack {
                        Button(simple ? "Nog een foto" : "Nieuwe foto") { dismiss() }.buttonStyle(.borderedProminent).accessibilityIdentifier("newPhotoButton")
                        Button(simple ? "Opnieuw zoeken" : "Opnieuw detecteren") { Task { await store.analyze(frameId: frameId) } }.buttonStyle(.bordered)
                    }
                    HStack {
                        if let kf = store.keyframe(frameId) {
                            NavigationLink("Kozijn handmatig toevoegen") { CornerPickerView(frame: kf).environmentObject(store) }.buttonStyle(.bordered)
                        }
                        if !simple { Button("Exporteren") { exportPath = (try? ExportService.write(store))?.path ?? "export mislukt" }.buttonStyle(.bordered).accessibilityIdentifier("exportButton") }
                    }
                    if !simple { Toggle("Grijze kaders (zonder maat) op de foto verbergen", isOn: $hideNeutral).font(.footnote).accessibilityIdentifier("hideNeutralToggle") }
                    if !simple, let n = store.analysisNotes[frameId] { Text(n).font(.caption2).foregroundStyle(.secondary) }
                    Text(simple ? "De herkenning is nog niet getest op echte gebouwen. Het zijn voorlopige schattingen; jij beslist later wat er in je MJOP komt."
                         : "Groen/oranje/grijs = alleen UI-feedback, geen goedkeuring. Herkenning en metingen zijn NIET gevalideerd op echte gebouwen. Zoom verandert geen meting.")
                        .font(.caption2).foregroundStyle(.secondary)
                    if let p = exportPath { Text("Export: \(p)").font(.caption2).textSelection(.enabled) }
                }.padding(.horizontal, 8)
            }.frame(maxHeight: 280)
        }
        .navigationTitle("Foto \(frameId)").navigationBarTitleDisplayMode(.inline)
        .navigationDestination(isPresented: $showDetail) { if let id = selected { BoxDetailView(observationId: id).environmentObject(store) } }
        .onAppear { loadImage(); if store.measures.isEmpty { store.measureAll() }; autoAnalyzeIfNeeded() }
    }

    /// Het bestaande technische overzicht (ongewijzigd): herkenning, aantallen, m² per status, controles en per kader de bron en reden.
    @ViewBuilder private func technicalBlock() -> some View {
        let ov = store.overview(frameId: frameId)
        VStack(alignment: .leading, spacing: 4) {
            if store.analyzing.contains(frameId) { HStack { ProgressView(); Text("Kozijnen herkennen…").font(.footnote) }.accessibilityIdentifier("analyzing") }
            Text("Herkend: \(ov.detected) kandidaat-kozijn(en) op deze foto").font(.footnote.bold()).accessibilityIdentifier("overviewDetected")
            Text("Voorlopig unieke kozijnen (alle foto's): \(ov.unique)").font(.footnote).accessibilityIdentifier("overviewUnique")
            Text(ov.areaByStatus.isEmpty ? "Bruto m² (voorlopig): nog geen meetbare kozijnen"
                 : "Bruto m² waar meetbaar (voorlopig, per status, niet opgeteld tot totaal): " + ov.areaByStatus.map { "\($0.status) \($0.area)" }.joined(separator: " · "))
                .font(.footnote).accessibilityIdentifier("overviewArea")
            Text("Controles (oranje): \(ov.checks) · zonder betrouwbare maat (grijs/UNKNOWN): \(ov.noScale) · meetbaar: \(ov.measurable)").font(.footnote).accessibilityIdentifier("overviewChecks")
            if ov.linkSuggestions > 0 { NavigationLink("Koppelsuggesties bekijken (\(ov.linkSuggestions))") { LinkSuggestionsView().environmentObject(store) }.font(.footnote) }
            ForEach(frameObservations) { o in
                let m = store.measures[o.id]
                Button {
                    selected = o.id; showDetail = true
                } label: {
                    HStack(alignment: .top) {
                        Circle().fill(m?.feedback == .green ? Color.green : m?.feedback == .orange ? Color.orange : Color.gray).frame(width: 12, height: 12).padding(.top, 3)
                        VStack(alignment: .leading) {
                            Text("\(store.shortName(ofObservation: o.id)) (\(colorName(m?.feedback))) · \(m.map { Self.dimsText($0.result) } ?? "…")").font(.footnote.bold())
                            Text("\(o.source == .AUTO_DETECTED_UNCONFIRMED ? "kandidaat, niet bevestigd" : o.source.rawValue) · \(m.map { reason($0.result) } ?? "")").font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }.buttonStyle(.plain).accessibilityIdentifier("boxRow-\(o.id)")
            }
        }
    }

    private func friendly(_ m: ObservationMeasure?) -> String {
        guard let m else { return "Maat wordt berekend…" }
        if !m.result.ok { return "Deze maat is nog niet betrouwbaar genoeg." }
        let base = Self.dimsText(m.result)
        return m.feedback == .green ? base + " · voorlopig" : base + " · controleer deze maat"
    }

    /// Fotoronde-weergave in gewone taal: hoeveel mogelijke kozijnen, en per kozijn de voorlopige maat of de melding dat die nog niet betrouwbaar is.
    @ViewBuilder private func simpleBlock() -> some View {
        let ov = store.overview(frameId: frameId)
        if store.analyzing.contains(frameId) { HStack { ProgressView(); Text("Kozijnen zoeken…").font(.footnote) }.accessibilityIdentifier("analyzing") }
        Text(ov.detected == 0 ? "Er zijn nog geen kozijnen gevonden op deze foto."
             : ov.detected == 1 ? "Er is 1 mogelijk kozijn gevonden." : "Er zijn \(ov.detected) mogelijke kozijnen gevonden.")
            .font(.headline).accessibilityIdentifier("simpleFound")
        Text("Controleer of alle kozijnen kloppen. Tik op een kozijn om het aan te passen.").font(.footnote)
        ForEach(frameObservations) { o in
            let m = store.measures[o.id]
            Button {
                selected = o.id; showDetail = true
            } label: {
                HStack(alignment: .top) {
                    Circle().fill(m?.feedback == .green ? Color.green : m?.feedback == .orange ? Color.orange : Color.gray).frame(width: 12, height: 12).padding(.top, 3)
                    VStack(alignment: .leading) {
                        Text("Kozijn \(store.shortName(ofObservation: o.id))").font(.footnote.bold())
                        Text(friendly(m)).font(.caption)
                    }
                }
            }.buttonStyle(.plain).accessibilityIdentifier("boxRow-\(o.id)")
        }
    }

    private func loadImage() {
        if image == nil, let u = store.keyframe(frameId)?.imageURL, let d = try? Data(contentsOf: u) { image = UIImage(data: d) }
    }

    /// Een foto zonder enige waarneming en zonder lopende analyse wordt eenmalig automatisch geanalyseerd (bijv. de simulatie-testfoto).
    private func autoAnalyzeIfNeeded() {
        if store.analysisNotes[frameId] == nil, !store.analyzing.contains(frameId), !store.observations.contains(where: { $0.frameId == frameId }) {
            Task { await store.analyze(frameId: frameId) }
        }
    }
}

/// Detail van één kader: automatisch ingezoomd, hoeken versleepbaar, referentiemaat, koppelen aan een kozijn van een andere foto. Brondata blijft ongewijzigd.
struct BoxDetailView: View {
    @EnvironmentObject var store: ScanStore
    @Environment(\.dismiss) private var dismiss
    let observationId: String
    @State private var corners: [Pixel] = []
    @State private var image: UIImage? = nil
    private static let names = ["linksboven", "rechtsboven", "rechtsonder", "linksonder"]

    var body: some View {
        let obs = store.observation(observationId)
        let kf = obs.flatMap { store.keyframe($0.frameId) }
        let m = store.measures[observationId]
        VStack(spacing: 4) {
            if let obs, let kf, let img = image {
                FrameImageCanvas(frame: kf, image: img, points: $corners, maxPoints: 4, pointNames: Self.names, fitTo: obs.corners, showReadout: false)
                ScrollView {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(store.shortName(ofObservation: obs.id)) · \(m.map { PhotoResultView.dimsText($0.result) } ?? "…")").font(.headline).accessibilityIdentifier("detailDims")
                        if let m {
                            let r = m.result
                            Text("Bron: \(r.ok ? "\(r.scaleMethod) (niveau \(r.level.rawValue))" : "geen betrouwbare schaal") · hoeken: \(obs.source.rawValue)\(obs.detection.map { " · detector \($0.detector)" } ?? "")")
                                .font(.caption)
                            if r.ok, let sa = r.sigmaArea { Text(String(format: "Onzekerheid 1σ ≈ %.4f m² (modelgebaseerd, NIET gevalideerd)", sa)).font(.caption) }
                            ForEach(Array(r.flags.enumerated()), id: \.offset) { _, f in
                                Text("• \(f.code): \(f.instruction_nl)").font(.caption2).foregroundStyle(f.severity == .BLOCKING ? .red : .secondary)
                            }
                        }
                        Text("Sleep de rode punten naar de BUITENHOEKEN van het kozijn (zoom met twee vingers) en kies 'Toepassen'. Originele hoeken en sensordata blijven bewaard.").font(.caption2)
                        HStack {
                            Button("Toepassen") { apply(obs) }.buttonStyle(.borderedProminent).disabled(corners == obs.corners).accessibilityIdentifier("applyCorners")
                            Button("Herstel detectie") { corners = obs.originalCorners }.buttonStyle(.bordered).disabled(corners == obs.originalCorners)
                            if obs.source == .AUTO_DETECTED_UNCONFIRMED { Button("Hoeken bevestigen") { store.confirmCorners(observation: obs.id); Task { await store.measureAllInBackground(); store.persist() } }.buttonStyle(.bordered) }
                        }
                        if let m, DiagnosticsView.needsMotion(m.result) {
                            Text(CaptureCoordinator.motionHint).font(.footnote.bold()).foregroundStyle(.orange).accessibilityIdentifier("detailMotionHint")
                        }
                        NavigationLink("Meetdiagnose") { DiagnosticsView(observationId: obs.id).environmentObject(store) }
                            .buttonStyle(.bordered).accessibilityIdentifier("diagnosticsLink")
                        HStack {
                            NavigationLink("Referentiemaat") { ReferencePickerView(frame: kf, anchorObservationId: obs.id).environmentObject(store) }.buttonStyle(.bordered)
                            Button("Geen kozijn") { store.setRejected(obs.id, true); dismiss() }.buttonStyle(.bordered).tint(.red).accessibilityIdentifier("rejectButton")
                        }
                        linkControls(obs)
                    }.padding(.horizontal, 8)
                }.frame(maxHeight: 260)
            } else { ProgressView() }
        }
        .navigationTitle("Kozijn").navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if let o = store.observation(observationId) {
                if corners.isEmpty { corners = o.corners }
                if image == nil, let u = store.keyframe(o.frameId)?.imageURL, let d = try? Data(contentsOf: u) { image = UIImage(data: d) }
            }
        }
    }

    private func apply(_ obs: Observation) {
        for i in 0..<4 where corners[i] != obs.corners[i] { store.correctCorner(observation: obs.id, index: i, to: corners[i], reason: "handmatige correctie op ingezoomde foto") }
        Task { await store.measureAllInBackground(); store.persist() }
    }

    @ViewBuilder private func linkControls(_ obs: Observation) -> some View {
        let myDraft = store.draft(of: obs.id)
        let others = store.drafts.filter { d in d.id != myDraft?.id && d.observationIds.contains { oid in store.observation(oid).map { $0.frameId != obs.frameId && !$0.rejected } ?? false } }
        HStack {
            if !others.isEmpty {
                Menu("Koppel aan kozijn van andere foto") {
                    ForEach(others) { d in
                        Button("\(store.shortName(ofDraft: d.id)) (\(d.observationIds.count) foto's)") { if let first = d.observationIds.first { store.link(obs.id, first) } }
                    }
                }.buttonStyle(.bordered)
            }
            if (myDraft?.observationIds.count ?? 0) > 1 { Button("Ontkoppel") { store.unlink(obs.id) }.buttonStyle(.bordered) }
        }
        Text("Koppelen is voorlopig en gebeurt alleen op jouw initiatief; er wordt niets automatisch definitief samengevoegd.").font(.caption2).foregroundStyle(.secondary)
    }
}

struct LinkSuggestionsView: View {
    @EnvironmentObject var store: ScanStore
    var body: some View {
        let s = store.linkSuggestions()
        List {
            Text("Mogelijk hetzelfde kozijn op verschillende foto's (zelfde vlak, nabije positie, vergelijkbare maat). Dit is een SUGGESTIE; koppel alleen als je het zeker weet. Niets wordt automatisch samengevoegd.").font(.footnote)
            ForEach(s, id: \.a) { c in
                VStack(alignment: .leading) {
                    Text("\(store.shortName(ofObservation: c.a)) (\(store.observation(c.a)?.frameId ?? "")) ↔ \(store.shortName(ofObservation: c.b)) (\(store.observation(c.b)?.frameId ?? "")) · afstand \(String(format: "%.2f", c.distanceM)) m").font(.footnote)
                    HStack {
                        Button("Koppel (voorlopig)") { store.link(c.a, c.b) }.buttonStyle(.borderedProminent)
                        Button("Negeer") { store.dismissLink(c.a, c.b) }.buttonStyle(.bordered)
                    }
                }
            }
            if s.isEmpty { Text("Geen openstaande suggesties.") }
        }.navigationTitle("Koppelsuggesties")
    }
}
