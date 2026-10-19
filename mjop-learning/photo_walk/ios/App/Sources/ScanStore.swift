import Foundation
import PhotoWalkCore

/// Een vastgelegd keyframe. Alle wiskunde gebruikt de OpenCV-conventie (zie docs/contract_and_coordinates.md).
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

struct Observation: Identifiable {
    let id: String
    let frameId: String
    var corners: [Pixel]            // TL, TR, BR, BL in PIXELS van het keyframe (native cameraoriëntatie)
    let originalCorners: [Pixel]    // wordt nooit overschreven
    var source: CornerSource
    var revisions: [CornerRevision] = []
    var obstruction = false
}

struct ObjectDraft: Identifiable { let id: String; var observationIds: [String] }

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
    @Published var isSimulation = false

    func newSession() { sessionId = UUID().uuidString; keyframes = []; observations = []; drafts = []; references = [:]; results = []; isSimulation = false }

    func addObservation(_ o: Observation, to draftId: String?) {
        observations.append(o)
        if let id = draftId, let i = drafts.firstIndex(where: { $0.id == id }) { drafts[i].observationIds.append(o.id) }
        else { drafts.append(ObjectDraft(id: "PROV-\(sessionId.prefix(8))-\(String(format: "%03d", drafts.count + 1))", observationIds: [o.id])) }
    }

    /// Menselijke hoekcorrectie: schrijft een revisie; `originalCorners` blijft ongemoeid.
    func correctCorner(observation id: String, index: Int, to p: Pixel, reason: String?) {
        guard let i = observations.firstIndex(where: { $0.id == id }) else { return }
        let before = observations[i].corners[index]
        observations[i].corners[index] = p
        observations[i].source = .MANUAL_CORRECTED
        observations[i].revisions.append(CornerRevision(index: index, before: before, after: p, editedBy: "inspecteur", editedAt: Date(), reason: reason))
    }

    /// Meet alle objecten opnieuw uit de ONVERANDERDE brongegevens (keyframes) en de actuele hoeken.
    func measureAll() {
        var out: [MeasuredObject] = []
        let frames = Dictionary(uniqueKeysWithValues: keyframes.map { ($0.id, $0) })
        for d in drafts {
            let obs = observations.filter { d.observationIds.contains($0.id) }
            var perView: [LevelResult] = []
            for o in obs {
                guard let kf = frames[o.frameId] else { continue }
                let v = ViewInput(frameId: kf.id, intrinsics: kf.intrinsics, pose: kf.pose, trackingNormal: kf.trackingState == "NORMAL", depth: kf.depth)
                perView.append(measureDepthView(v, corners: o.corners, seed: UInt64(truncatingIfNeeded: d.id.hashValue), obstruction: o.obstruction))
            }
            var final = perView.count > 1 ? fuse(perView) : (perView.first ?? LevelResult(level: .A, scaleMethod: "NONE"))
            var viewCount = final.viewIds.count
            if !final.ok, !final.flags.contains(where: { $0.code == "VIEWS_INCONSISTENT" }) {
                for o in obs {
                    if let ref = references[o.frameId], let kf = frames[o.frameId] {
                        let v = ViewInput(frameId: kf.id, intrinsics: kf.intrinsics, pose: kf.pose, trackingNormal: kf.trackingState == "NORMAL", depth: kf.depth)
                        let rc = measureWithReference(view: v, target: o.corners, ref: ref, seed: 1)
                        if rc.ok { final = rc; viewCount = 1; break }
                    }
                }
            }
            if !final.ok && !hasBlocking(final.flags) { final.flags.append(Flags.make("NO_METRIC_SCALE")) }
            var extra: [QualityFlag] = []
            if obs.contains(where: { $0.source == .MANUAL }) { extra.append(Flags.make("MANUAL_CORNERS")) }
            if obs.contains(where: { $0.source == .MANUAL_CORRECTED }) { extra.append(Flags.make("HUMAN_CORRECTED_CORNERS")) }
            let iso = ISO8601DateFormatter()
            let recs = obs.map { o in ObservationRecord(id: o.id, frameId: o.frameId, corners: o.corners, originalCorners: o.originalCorners, source: o.source.rawValue,
                                                        revisions: o.revisions.map { CornerRevisionRecord(index: $0.index, before: $0.before, after: $0.after, editedBy: $0.editedBy, editedAt: iso.string(from: $0.editedAt), reason: $0.reason) }) }
            out.append(makeObject(id: d.id, observations: recs, result: final, viewCount: viewCount, extraFlags: extra))
        }
        results = out
    }
}
