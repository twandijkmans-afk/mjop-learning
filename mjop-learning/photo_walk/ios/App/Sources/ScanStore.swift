import Foundation
import UIKit
import PhotoWalkCore

/// Een vastgelegde foto: originele camerabeeld + intrinsics + pose + trackingstatus + (indien beschikbaar) LiDAR-diepte, alles ONGEWIJZIGD bewaard.
struct Keyframe: Identifiable {
    let id: String
    let timestamp: Date
    let intrinsics: Intrinsics
    let pose: Pose                  // camera_to_world, OpenCV-camera
    let trackingState: String       // NORMAL | LIMITED_* | NOT_AVAILABLE
    let depth: DepthMap?            // depth_z in meter; laag-vertrouwen-pixels staan op NaN
    let imageURL: URL?              // lokaal bestand in de app-sandbox; nooit geupload
}

enum CornerSource: String { case MANUAL, AUTO_DETECTED_UNCONFIRMED, AUTO_DETECTED_CONFIRMED, MANUAL_CORRECTED }

struct CornerRevision { let index: Int; let before: Pixel; let after: Pixel; let editedBy: String; let editedAt: Date; let reason: String? }

struct DetectionInfo: Equatable { var detector: String; var score: Double }

struct Observation: Identifiable {
    let id: String
    let frameId: String
    var corners: [Pixel]            // TL, TR, BR, BL in PIXELS van het keyframe (native cameraoriëntatie)
    let originalCorners: [Pixel]    // wordt nooit overschreven (bij detectie: de gedetecteerde hoeken)
    var source: CornerSource
    var revisions: [CornerRevision] = []
    var obstruction = false
    var detection: DetectionInfo? = nil
    var rejected = false            // inspecteur: "dit is geen kozijn"; blijft lokaal bewaard, telt niet mee
}

struct ObjectDraft: Identifiable { let id: String; var observationIds: [String] }

/// Meting van EEN waarneming in EEN foto (voor het kader) + UI-kleur. De kleur is alleen feedback, geen goedkeuring.
struct ObservationMeasure {
    var result: LevelResult
    var feedback: BoxFeedback
}

struct Overview {
    var detected = 0
    var unique = 0
    var measurable = 0
    var areaByStatus: [(status: String, area: String)] = []
    var checks = 0                  // oranje kaders
    var noScale = 0                 // neutrale kaders (UNKNOWN)
    var linkSuggestions = 0
}

/// Deterministische seed (FNV-1a); `hashValue` is per proces willekeurig en zou resultaten niet reproduceerbaar maken.
func stableSeed(_ s: String) -> UInt64 {
    var h: UInt64 = 0xcbf29ce484222325
    for b in s.utf8 { h = (h ^ UInt64(b)) &* 0x100000001b3 }
    return h
}

/// Alle rekenwerk op waarden (geen state), zodat het buiten de hoofdthread kan draaien. Gebruikt uitsluitend de originele pixels en de ongewijzigde sensordata.
enum Measurer {
    struct Output { var measures: [String: ObservationMeasure]; var results: [MeasuredObject] }

    static func input(_ kf: Keyframe) -> ViewInput {
        ViewInput(frameId: kf.id, intrinsics: kf.intrinsics, pose: kf.pose, trackingNormal: kf.trackingState == "NORMAL", depth: kf.depth)
    }

    static func measure(_ o: Observation, frames: [String: Keyframe], observations: [String: Observation], references: [String: ReferenceMeasure]) -> LevelResult {
        guard let kf = frames[o.frameId] else {
            var r = LevelResult(level: .A, scaleMethod: "NONE"); r.flags = [Flags.make("NO_DEPTH", "keyframe ontbreekt")]; return r
        }
        let v = input(kf)
        var r = measureDepthView(v, corners: o.corners, seed: stableSeed(o.id), obstruction: o.obstruction)
        if !r.ok, let ref = references[o.frameId] {
            var anchor: [Pixel]? = nil
            if let aid = ref.anchorObservationId, aid != o.id, let a = observations[aid], !a.rejected { anchor = a.corners }
            let rc = measureWithReference(view: v, target: o.corners, ref: ref, anchor: anchor, seed: stableSeed(o.id + "C"))
            if rc.ok { r = rc } else { r.flags += rc.flags.filter { $0.severity == .BLOCKING }.map { QualityFlag(code: $0.code, severity: $0.severity, detail: "[referentie] \($0.detail ?? "")", instruction_nl: $0.instruction_nl) } }
        }
        if !r.ok && !hasBlocking(r.flags) { r.flags.append(Flags.make("NO_METRIC_SCALE")) }
        return r
    }

    static func compute(keyframes: [Keyframe], observations: [Observation], drafts: [ObjectDraft], references: [String: ReferenceMeasure]) -> Output {
        let frames = Dictionary(uniqueKeysWithValues: keyframes.map { ($0.id, $0) })
        let obsById = Dictionary(uniqueKeysWithValues: observations.map { ($0.id, $0) })
        var measures: [String: ObservationMeasure] = [:]
        for o in observations where !o.rejected {
            let r = measure(o, frames: frames, observations: obsById, references: references)
            measures[o.id] = ObservationMeasure(result: r, feedback: Feedback.classify(r))
        }
        let iso = ISO8601DateFormatter()
        var out: [MeasuredObject] = []
        for d in drafts {
            let obs = d.observationIds.compactMap { obsById[$0] }.filter { !$0.rejected }
            if obs.isEmpty { continue }
            let perView = obs.compactMap { measures[$0.id]?.result }
            let okA = perView.filter { $0.ok && $0.level == .A }
            var final: LevelResult
            var viewCount = 1
            if okA.count >= 2 { final = fuse(okA); viewCount = final.viewIds.count }
            else if let a = okA.first { final = a }
            else if let c = perView.first(where: { $0.ok }) { final = c }
            else { final = perView.first ?? LevelResult(level: .A, scaleMethod: "NONE") }
            if !final.ok && !hasBlocking(final.flags) { final.flags.append(Flags.make("NO_METRIC_SCALE")) }
            var extra: [QualityFlag] = []
            if obs.contains(where: { $0.source == .MANUAL }) { extra.append(Flags.make("MANUAL_CORNERS")) }
            if obs.contains(where: { $0.source == .MANUAL_CORRECTED }) { extra.append(Flags.make("HUMAN_CORRECTED_CORNERS")) }
            if obs.contains(where: { $0.source == .AUTO_DETECTED_UNCONFIRMED }) { extra.append(Flags.make("AUTO_DETECTED_UNCONFIRMED")) }
            let recs = obs.map { o in
                ObservationRecord(id: o.id, frameId: o.frameId, corners: o.corners, originalCorners: o.originalCorners, source: o.source.rawValue,
                                  revisions: o.revisions.map { CornerRevisionRecord(index: $0.index, before: $0.before, after: $0.after, editedBy: $0.editedBy, editedAt: iso.string(from: $0.editedAt), reason: $0.reason) })
            }
            out.append(makeObject(id: d.id, observations: recs, result: final, viewCount: viewCount, extraFlags: extra))
        }
        return Output(measures: measures, results: out)
    }
}

@MainActor
final class ScanStore: ObservableObject {
    @Published var sessionId = UUID().uuidString
    @Published var buildingId = ""
    @Published var facadeId = ""
    @Published var keyframes: [Keyframe] = []
    @Published var observations: [Observation] = []
    @Published var drafts: [ObjectDraft] = []
    @Published var references: [String: ReferenceMeasure] = [:]   // per frameId
    @Published var results: [MeasuredObject] = []
    @Published var measures: [String: ObservationMeasure] = [:]
    @Published var analyzing: Set<String> = []
    @Published var analysisNotes: [String: String] = [:]
    @Published var dismissedLinks: Set<String> = []
    @Published var isSimulation = false

    func newSession() {
        sessionId = UUID().uuidString; keyframes = []; observations = []; drafts = []; references = [:]; results = []; measures = [:]
        analyzing = []; analysisNotes = [:]; dismissedLinks = []; isSimulation = false
    }

    // MARK: waarnemingen
    func addObservation(_ o: Observation, to draftId: String?) {
        observations.append(o)
        if let id = draftId, let i = drafts.firstIndex(where: { $0.id == id }) { drafts[i].observationIds.append(o.id) }
        else { drafts.append(ObjectDraft(id: "PROV-\(sessionId.prefix(8))-\(String(format: "%03d", drafts.count + 1))", observationIds: [o.id])) }
    }

    func observation(_ id: String) -> Observation? { observations.first { $0.id == id } }
    func keyframe(_ id: String) -> Keyframe? { keyframes.first { $0.id == id } }
    func draft(of obsId: String) -> ObjectDraft? { drafts.first { $0.observationIds.contains(obsId) } }

    /// "K1", "K2", ...: korte weergavenaam van het voorlopige object (positie in de lijst); het volledige voorlopige object-ID staat in het exportrecord.
    func shortName(ofDraft id: String) -> String { "K\((drafts.firstIndex { $0.id == id } ?? 0) + 1)" }
    func shortName(ofObservation id: String) -> String { draft(of: id).map { shortName(ofDraft: $0.id) } ?? "?" }

    /// Menselijke hoekcorrectie: schrijft een revisie; `originalCorners` blijft ongemoeid.
    func correctCorner(observation id: String, index: Int, to p: Pixel, reason: String?) {
        guard let i = observations.firstIndex(where: { $0.id == id }) else { return }
        let before = observations[i].corners[index]
        observations[i].corners[index] = p
        observations[i].source = .MANUAL_CORRECTED
        observations[i].revisions.append(CornerRevision(index: index, before: before, after: p, editedBy: "inspecteur", editedAt: Date(), reason: reason))
    }

    func confirmCorners(observation id: String) {
        guard let i = observations.firstIndex(where: { $0.id == id }), observations[i].source == .AUTO_DETECTED_UNCONFIRMED else { return }
        observations[i].source = .AUTO_DETECTED_CONFIRMED       // bevestigt alleen de HOEKEN; geen goedkeuring van de hoeveelheid
    }

    func setRejected(_ id: String, _ rejected: Bool) {
        guard let i = observations.firstIndex(where: { $0.id == id }) else { return }
        observations[i].rejected = rejected
        measureAll(); persist()
    }

    func setReference(_ r: ReferenceMeasure) { references[r.frameId] = r }

    // MARK: koppelen over foto's (alleen op initiatief van de inspecteur)
    func linkSuggestions() -> [LinkCandidate] {
        var items: [LinkItem] = []
        for o in observations where !o.rejected {
            guard let m = measures[o.id], m.result.ok, let c = m.result.cornersWorld, let n = m.result.planeN, let d = m.result.planeD, let w = m.result.width, let h = m.result.height else { continue }
            let ctr = c.reduce(Vec3.zero, +) * 0.25
            items.append(LinkItem(id: o.id, frameId: o.frameId, center: ctr, planeN: n, planeD: d, width: w, height: h))
        }
        return Linking.suggest(items).filter { c in
            let da = draft(of: c.a)?.id, db = draft(of: c.b)?.id
            return da != db && !dismissedLinks.contains(c.a + "|" + c.b)
        }
    }

    func link(_ a: String, _ b: String) {
        guard let ia = drafts.firstIndex(where: { $0.observationIds.contains(a) }), let ib = drafts.firstIndex(where: { $0.observationIds.contains(b) }), ia != ib else { return }
        drafts[ia].observationIds += drafts[ib].observationIds
        drafts.remove(at: ib)
        measureAll(); persist()
    }

    func dismissLink(_ a: String, _ b: String) { dismissedLinks.insert(a + "|" + b); persist() }

    func unlink(_ obsId: String) {
        guard let i = drafts.firstIndex(where: { $0.observationIds.contains(obsId) }), drafts[i].observationIds.count > 1 else { return }
        drafts[i].observationIds.removeAll { $0 == obsId }
        drafts.append(ObjectDraft(id: "PROV-\(sessionId.prefix(8))-\(String(format: "%03d", drafts.count + 1))", observationIds: [obsId]))
        measureAll(); persist()
    }

    // MARK: meten
    func measureAll() {
        let o = Measurer.compute(keyframes: keyframes, observations: observations, drafts: drafts, references: references)
        measures = o.measures; results = o.results
    }

    func measureAllInBackground() async {
        let kfs = keyframes, obs = observations, dr = drafts, refs = references
        let o = await Task.detached(priority: .userInitiated) { Measurer.compute(keyframes: kfs, observations: obs, drafts: dr, references: refs) }.value
        measures = o.measures; results = o.results
    }

    /// Foto -> kandidaten (lokaal, Apple Vision / optioneel Core ML) -> waarnemingen -> meting. Bestaande kandidaten van dezelfde foto blijven staan
    /// (nieuwe kandidaten die er sterk mee overlappen worden genegeerd): opnieuw detecteren geeft dus geen dubbele kozijnen.
    func analyze(frameId: String) async {
        guard let kf = keyframe(frameId), let url = kf.imageURL else { analysisNotes[frameId] = "Geen beeld beschikbaar voor detectie."; return }
        analyzing.insert(frameId)
        let detectors = DetectorCatalog.available()
        let found: [WindowCandidate] = await Task.detached(priority: .userInitiated) { () -> [WindowCandidate] in
            guard let cg = UIImage(contentsOfFile: url.path)?.cgImage else { return [] }
            var all: [WindowCandidate] = []
            for d in detectors { all += d.detect(cg) }
            return CandidateFilter.clean(all, imageWidth: Double(cg.width), imageHeight: Double(cg.height))
        }.value
        var added = 0
        for c in found {
            let existing = observations.filter { $0.frameId == frameId && !$0.rejected }
            if existing.contains(where: { CandidateFilter.iou($0.corners, c.corners) > 0.5 }) { continue }
            let id = "OBS-\(frameId)-\(String(format: "%02d", observations.filter { $0.frameId == frameId }.count + 1))"
            addObservation(Observation(id: id, frameId: frameId, corners: c.corners, originalCorners: c.corners, source: .AUTO_DETECTED_UNCONFIRMED,
                                       detection: DetectionInfo(detector: c.detector, score: c.score)), to: nil)
            added += 1
        }
        await measureAllInBackground()
        analyzing.remove(frameId)
        analysisNotes[frameId] = "\(found.count) kandidaat/kandidaten gevonden (\(added) nieuw) met: \(detectors.map { $0.name }.joined(separator: ", ")). Dit zijn KANDIDATEN, geen bevestigde kozijnen."
        persist()
    }

    // MARK: overzicht
    func overview(frameId: String? = nil) -> Overview {
        let obs = observations.filter { !$0.rejected && (frameId == nil || $0.frameId == frameId) }
        var ov = Overview()
        ov.detected = obs.count
        let draftIds = Set(obs.compactMap { draft(of: $0.id)?.id })
        ov.unique = draftIds.count
        var byStatus: [String: Decimal] = [:]
        for r in results where draftIds.contains(r.id) && r.status != .UNKNOWN {
            ov.measurable += 1
            byStatus[r.status.rawValue, default: 0] += Decimal(string: r.areaM2 ?? "0") ?? 0
        }
        ov.areaByStatus = ["MEASURED", "DERIVED", "ESTIMATED"].compactMap { s in byStatus[s].map { (s, decimalString($0)) } }
        for o in obs { switch measures[o.id]?.feedback { case .orange?: ov.checks += 1; case .neutral?, nil: ov.noScale += 1; default: break } }
        ov.linkSuggestions = linkSuggestions().count
        return ov
    }

    func persist() { Persistence.save(self) }
}
