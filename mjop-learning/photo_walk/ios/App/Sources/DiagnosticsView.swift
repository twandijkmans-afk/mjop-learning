import SwiftUI
import PhotoWalkCore

/// Meetdiagnose van één kozijn: waarom is er wel/geen maat, welke vlakken zijn gevonden, hoeveel frames/punten zijn gebruikt en wat kan beter.
/// Alles hier is numerieke diagnostiek van de LiDAR-berekening (modelgebaseerd, NIET gevalideerd tegen echte metingen).
struct DiagnosticsView: View {
    @EnvironmentObject var store: ScanStore
    let observationId: String
    @State private var exportPath: String? = nil
    @State private var exportURL: URL? = nil

    private func d(_ x: Any?) -> Double? { (x as? NSNumber)?.doubleValue ?? (x as? Double) }
    private func i(_ x: Any?) -> Int? { (x as? NSNumber)?.intValue ?? (x as? Int) }
    private func f(_ x: Any?, _ digits: Int = 3, scale: Double = 1, unit: String = "") -> String {
        guard let v = d(x) else { return "–" }
        return String(format: "%.\(digits)f", v * scale) + unit
    }
    private func line(_ k: String, _ v: String) -> some View {
        HStack(alignment: .top) { Text(k).font(.footnote).foregroundStyle(.secondary); Spacer(); Text(v).font(.footnote).multilineTextAlignment(.trailing) }
    }

    /// Behoefte aan meer beweging: te weinig onafhankelijke frames of een kozijnvlak dat daardoor niet bepaald kon worden.
    static func needsMotion(_ r: LevelResult) -> Bool {
        let codes = Set(r.flags.map { $0.code })
        return r.independentFrames < 2 && r.level == .A || !codes.isDisjoint(with: ["FRAME_PLANE_UNDETERMINED", "FRAME_OFFSET_FROM_CORNER_DEPTH", "FRAMES_INCONSISTENT", "DEPTH_COVERAGE_LOW", "LIMITED_SIDE_COVERAGE"])
    }

    var body: some View {
        let obs = store.observation(observationId)
        let m = store.measures[observationId]
        List {
            if let obs, let m {
                let r = m.result, g = r.diag
                Section("Uitkomst") {
                    line("Kozijn", store.shortName(ofObservation: obs.id))
                    line("Maat", PhotoResultView.dimsText(r))
                    line("Methode", r.ok ? "\(r.scaleMethod) (niveau \(r.level.rawValue))" : "geen betrouwbare maat")
                    line("Onafhankelijke frames gebruikt", "\(r.independentFrames)")
                    line("Tracking (foto)", (g["tracking_capture"] as? String) ?? "–")
                    line("Indicatieve afstand tot kozijn", f(g["distance_to_frame_m"], 2, unit: " m"))
                    if r.ok, r.scaleMethod == "REFERENCE_DISTANCE", let k = r.scaleEvidence["reference_kind"] as? String {
                        line("Soort referentie", k == "USER_ESTIMATE" ? "door gebruiker GESCHAT (geen meting)" : k)
                    }
                }
                Section("Reden en advies") {
                    ForEach(Array(r.flags.enumerated()), id: \.offset) { _, fl in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(fl.severity == .BLOCKING ? "✖" : "⚠") \(fl.code)").font(.footnote.bold()).foregroundStyle(fl.severity == .BLOCKING ? .red : .orange)
                            if let det = fl.detail, !det.isEmpty { Text(det).font(.caption2).foregroundStyle(.secondary) }
                            Text(fl.instruction_nl).font(.caption)
                        }
                    }
                    if r.flags.isEmpty { Text("Geen waarschuwingen.").font(.footnote) }
                    if Self.needsMotion(r) { Text(CaptureCoordinator.motionHint).font(.footnote.bold()).accessibilityIdentifier("motionHint") }
                }
                Section("Dieptepunten") {
                    line("Ringpixels (wand rond kozijn)", "\(i(g["ring_pixels"]) ?? 0)")
                    line("Geldig in bereik", "\(i(g["ring_valid"]) ?? 0) (\(f(g["ring_coverage"], 0, scale: 100, unit: " %")))")
                    line("Punten totaal / ring / profielband / glas", "\(i(g["points_valid_total"]) ?? 0) / \(i(g["points_ring"]) ?? 0) / \(i(g["points_band"]) ?? 0) / \(i(g["points_glass"]) ?? 0)")
                }
                Section("Frames") {
                    line("Beschikbaar / onafhankelijk", "\(i(g["frames_total"]) ?? 0) / \(i(g["frames_independent_candidates"]) ?? 0)")
                    line("Baseline", f(g["baseline_m"], 3, scale: 100, unit: " cm"))
                    ForEach(Array(((g["frames_rejected"] as? [[String: Any]]) ?? []).enumerated()), id: \.offset) { _, fr in
                        line("Verworpen \((fr["frame"] as? String) ?? "?")", (fr["why"] as? String) ?? "")
                    }
                    ForEach(Array(((g["per_frame"] as? [[String: Any]]) ?? []).enumerated()), id: \.offset) { _, pf in
                        let okf = (pf["ok"] as? Bool) == true
                        line("\((pf["frame"] as? String) ?? "?")", okf ? "\(f(pf["width_m"]))×\(f(pf["height_m"])) m\((pf["agrees"] as? Bool) == false ? " ✖ wijkt af" : "")" : "niet bruikbaar: \((pf["why"] as? String) ?? "")")
                    }
                    if let sc = g["smoothed_cross_check"] as? [String: Any] { line("Kruiscontrole smoothedSceneDepth (gecorreleerd)", (sc["ok"] as? Bool) == true ? "Δb \(f(sc["delta_width_m"], 3, unit: " m")) Δh \(f(sc["delta_height_m"], 3, unit: " m"))" : "geen maat") }
                }
                Section("Gevonden vlakken") {
                    if let sp = g["selected_plane"] as? [String: Any] {
                        line("Gekozen wandvlak", "inliers \(f(sp["inlier_ratio"], 0, scale: 100, unit: " %")) · rms \(f(sp["rms_m"], 1, scale: 1000, unit: " mm")) · zijden \(i(sp["sides_covered"]) ?? 0)/4")
                    }
                    if let st = g["stats"] as? [String: Any] {
                        line("Ruismodel σ(z) / drempel", "\(f(st["sigma_m"], 1, scale: 1000, unit: " mm")) / \(f(st["threshold_m"], 1, scale: 1000, unit: " mm"))")
                    }
                    ForEach(Array(((g["planes"] as? [[String: Any]]) ?? []).enumerated()), id: \.offset) { n, p in
                        line("Kandidaat \(n + 1): \((p["role"] as? String) ?? "")", "\(i(p["count"]) ?? 0) punten · rms \(f(p["rms_m"], 1, scale: 1000, unit: " mm")) · cos \(f(p["facing"], 2))")
                    }
                }
                if let fa = g["facade_assessment"] as? [String: Any] {
                    Section("Vlakbeoordeling (waarom wel/niet representatief)") {
                        let loc = fa["local"] as? [String: Any], sd = fa["sides"] as? [String: Any], ex = fa["extent"] as? [String: Any]
                        let xo = fa["excluded_other_layer"] as? [String: Any], un = fa["unexplained"] as? [String: Any]
                        line("Punten op het gekozen vlak", "\(i(fa["facade_points"]) ?? 0) van \(i(fa["ring_points"]) ?? 0) ringpunten")
                        line("Uitgesloten als andere dieptelaag", "\(i(xo?["count"]) ?? 0) (\(f(xo?["share"], 0, scale: 100, unit: " %")))")
                        line("Niet bij een herkend vlak", "\(i(un?["count"]) ?? 0) (\(f(un?["share"], 0, scale: 100, unit: " %")))")
                        line("Alleen dit vlak: rms / robuuste spreiding", "\(f(loc?["rms_m"], 1, scale: 1000, unit: " mm")) / \(f(loc?["robust_sigma_m"], 1, scale: 1000, unit: " mm"))")
                        line("Toegestaan (rms / robuust)", "\(f(loc?["rms_limit_m"], 1, scale: 1000, unit: " mm")) / \(f(loc?["robust_limit_m"], 1, scale: 1000, unit: " mm"))")
                        line("Totale ringspreiding (alleen achtergrond)", f(fa["ring_total_spread_m"], 1, scale: 1000, unit: " mm"))
                        line("Punten per zijde (boven/rechts/onder/links)", ((sd?["counts"] as? [Any]) ?? []).map { "\(i($0) ?? 0)" }.joined(separator: " / "))
                        line("Zijde voldoende gedekt", ((sd?["covered"] as? [Bool]) ?? []).map { $0 ? "ja" : "nee" }.joined(separator: " / "))
                        line("In-vlak spreiding (min.) / vereist", "\(f(ex?["minor_std_m"], 2, unit: " m")) / \(f(ex?["min_required_m"], 2, unit: " m"))")
                        line("Representatief", (fa["representative"] as? Bool) == true ? "ja" : "nee")
                        if let rs = fa["reasons"] as? [String] { ForEach(rs, id: \.self) { Text($0).font(.caption2).foregroundStyle(.secondary) } }
                        if let gt = fa["gate"] as? String { line("Blokkerende controle", gt) }
                    }
                }
                if let ind = g["independence"] as? [String: Any] {
                    Section("Onafhankelijkheid van de frames") {
                        line("Frames geselecteerd / bruikbaar", "\(i(ind["frames_selected"]) ?? 0) / \(i(ind["frames_usable"]) ?? 0)")
                        line("Verschillende standpunten (telt als onafhankelijk)", "\(i(ind["distinct_viewpoints"]) ?? 0)")
                        line("Alleen gedraaid (zelfde plek, telt niet)", "\(i(ind["rotation_only_frames"]) ?? 0)")
                        Text("Een kader telt als ander standpunt bij ≥ 2 cm verplaatsing; rotatie alleen geeft extra punten maar geen onafhankelijke bevestiging.").font(.caption2).foregroundStyle(.secondary)
                    }
                }
                Section("Kozijnvlak t.o.v. wand") {
                    if let fp = g["frame_plane"] as? [String: Any] {
                        line("Modus", (fp["final_mode"] as? String) ?? (fp["mode"] as? String) ?? "–")
                        line("Terugligging (neg. = achter de wand)", f(fp["final_offset_m"] ?? fp["offset_m"], 1, scale: 100, unit: " cm"))
                        if let ps = fp["per_side"] as? [String: Any] {
                            ForEach(sideNames, id: \.self) { s in
                                if let e = ps[s] as? [String: Any] { line(s, "\(f(e["offset_m"], 1, scale: 100, unit: " cm")) · steun \(i(e["support"]) ?? 0)") }
                            }
                        }
                    }
                }
                Section("Controle van de vier hoeken") {
                    let dev = (g["corner_deviation_m"] as? [Any]) ?? []
                    ForEach(Array(dev.enumerated()), id: \.offset) { n, v in
                        line(["linksboven", "rechtsboven", "rechtsonder", "linksonder"][min(n, 3)], "afwijking \(f(v, 1, scale: 1000, unit: " mm"))")
                    }
                    line("Hoeken tegenstrijdig", "\(i(g["corners_contradicting"]) ?? 0) van \(i(g["corners_checked"]) ?? 0)")
                }
                Section {
                    Button("Exporteer meetdiagnose") {
                        if let u = try? DiagnosticsExport.write(store, observationId: observationId) { exportPath = u.path; exportURL = u } else { exportPath = "export mislukt" }
                    }.buttonStyle(.borderedProminent).accessibilityIdentifier("exportDiagnosticsButton")
                    if let p = exportPath { Text("Bestand: \(p)").font(.caption2).textSelection(.enabled).accessibilityIdentifier("diagnosticsExportPath") }
                    if let u = exportURL { ShareLink(item: u) { Label("Delen (alleen naar jezelf)", systemImage: "square.and.arrow.up") } }
                    Text("Het diagnosebestand bevat alleen getallen (pixelhoeken, aantallen, afstanden, vlakstatistieken, vlaggen en drempels): geen foto's, geen puntenwolk, geen locatie, geen absolute camerapositie. Het gaat nergens heen tenzij jij het deelt.")
                        .font(.caption2).foregroundStyle(.secondary)
                }
            } else { Text("Geen meting gevonden.") }
        }
        .navigationTitle("Meetdiagnose").accessibilityIdentifier("diagnosticsView")
    }
}
