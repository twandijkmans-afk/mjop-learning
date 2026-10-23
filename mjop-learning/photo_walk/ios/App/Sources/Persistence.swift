import Foundation
import MJOPIntegration
import PhotoWalkCore

/// Lokale opslag van een scansessie (Application Support, uitgesloten van back-up, bestandsbescherming). Geen upload, geen iCloud.
/// Per sessie een map met `session.json`, per foto het originele camerabeeld (`F000.jpg`) en de ongewijzigde LiDAR-dieptekaart (`F000.depth`,
/// Float32 little-endian, depth_z in meter, NaN = ongeldig). Bestandsnamen zijn RELATIEF: het containerpad verandert bij een herinstallatie.
struct SessionSnapshot: Codable {
    struct KF: Codable { var id: String; var timestamp: Date; var intrinsics: Intrinsics; var pose: Pose; var trackingState: String
        var imageFile: String?; var depthFile: String?; var depthWidth: Int; var depthHeight: Int
        var smoothedFile: String? = nil
        var supports: [Sup]? = nil }
    struct Sup: Codable { var id: String; var timestamp: Date; var intrinsics: Intrinsics; var pose: Pose; var trackingState: String; var depthFile: String; var depthWidth: Int; var depthHeight: Int }
    struct Rev: Codable { var index: Int; var before: Pixel; var after: Pixel; var editedBy: String; var editedAt: Date; var reason: String? }
    struct Obs: Codable { var id: String; var frameId: String; var corners: [Pixel]; var originalCorners: [Pixel]; var source: String; var revisions: [Rev]
        var obstruction: Bool; var detector: String?; var score: Double?; var rejected: Bool }
    struct Ref: Codable { var referenceId: String; var frameId: String; var p1: Pixel; var p2: Pixel; var distanceM: Double; var distanceSigmaM: Double?
        var planeId: String?; var anchorObservationId: String?; var kind: String? = nil }
    struct Draft: Codable { var id: String; var observationIds: [String] }
    var version = 1
    var sessionId: String
    var buildingId: String
    var facadeId: String
    var isSimulation: Bool
    var savedAt: Date
    var keyframes: [KF]
    var observations: [Obs]
    var drafts: [Draft]
    var references: [Ref]
    var dismissedLinks: [String]
    /// Alleen bij een fotoronde (optioneel: oudere sessies zonder dit veld blijven leesbaar).
    var round: RoundSnapshot? = nil
}

struct RoundSnapshot: Codable {
    var context: PhotoRoundContext
    var status: String
    var revision: Int
    var facades: [RoundState.Facade]
    var frameFacade: [String: String]
    var frameWorld: [String: String]
    var excludedFrames: [String]
}

enum Persistence {
    static var root: URL? {
        guard var dir = try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true).appendingPathComponent("PhotoWalk", isDirectory: true) else { return nil }
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        var rv = URLResourceValues(); rv.isExcludedFromBackup = true; try? dir.setResourceValues(rv)
        return dir
    }

    static func sessionDir(_ id: String) -> URL? {
        guard let d = root?.appendingPathComponent(id, isDirectory: true) else { return nil }
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }

    static func writeDepth(_ d: DepthMap, to url: URL) throws {
        var data = Data(capacity: d.values.count * 4)
        for v in d.values { var b = v.bitPattern.littleEndian; withUnsafeBytes(of: &b) { data.append(contentsOf: $0) } }
        try data.write(to: url, options: [.atomic, .completeFileProtection])
    }

    static func readDepth(_ url: URL, width: Int, height: Int) -> DepthMap? {
        guard let data = try? Data(contentsOf: url), data.count == width * height * 4 else { return nil }
        var vals = [Float](repeating: .nan, count: width * height)
        data.withUnsafeBytes { raw in
            for i in 0..<(width * height) { vals[i] = Float(bitPattern: UInt32(littleEndian: raw.loadUnaligned(fromByteOffset: i * 4, as: UInt32.self))) }
        }
        return DepthMap(width: width, height: height, values: vals)
    }

    @MainActor static func snapshot(_ s: ScanStore) -> SessionSnapshot {
        SessionSnapshot(
            sessionId: s.sessionId, buildingId: s.buildingId, facadeId: s.facadeId, isSimulation: s.isSimulation, savedAt: Date(),
            keyframes: s.keyframes.map { k in
                SessionSnapshot.KF(id: k.id, timestamp: k.timestamp, intrinsics: k.intrinsics, pose: k.pose, trackingState: k.trackingState,
                                   imageFile: k.imageURL?.lastPathComponent, depthFile: k.depth != nil ? "\(k.id).depth" : nil,
                                   depthWidth: k.depth?.width ?? 0, depthHeight: k.depth?.height ?? 0,
                                   smoothedFile: k.smoothedDepth != nil ? "\(k.id).smooth.depth" : nil,
                                   supports: k.supportDepths.map { SessionSnapshot.Sup(id: $0.id, timestamp: $0.timestamp, intrinsics: $0.intrinsics, pose: $0.pose, trackingState: $0.trackingState,
                                                                                       depthFile: "\($0.id).depth", depthWidth: $0.depth.width, depthHeight: $0.depth.height) }) },
            observations: s.observations.map { o in
                SessionSnapshot.Obs(id: o.id, frameId: o.frameId, corners: o.corners, originalCorners: o.originalCorners, source: o.source.rawValue,
                                    revisions: o.revisions.map { SessionSnapshot.Rev(index: $0.index, before: $0.before, after: $0.after, editedBy: $0.editedBy, editedAt: $0.editedAt, reason: $0.reason) },
                                    obstruction: o.obstruction, detector: o.detection?.detector, score: o.detection?.score, rejected: o.rejected) },
            drafts: s.drafts.map { SessionSnapshot.Draft(id: $0.id, observationIds: $0.observationIds) },
            references: s.references.values.sorted { $0.referenceId < $1.referenceId }.map {
                SessionSnapshot.Ref(referenceId: $0.referenceId, frameId: $0.frameId, p1: $0.p1, p2: $0.p2, distanceM: $0.distanceM, distanceSigmaM: $0.distanceSigmaM,
                                    planeId: $0.planeId, anchorObservationId: $0.anchorObservationId, kind: $0.kind.rawValue) },
            dismissedLinks: s.dismissedLinks.sorted(),
            round: s.round.map { RoundSnapshot(context: $0.context, status: $0.status, revision: $0.revision, facades: $0.facades, frameFacade: $0.frameFacade,
                                               frameWorld: $0.frameWorld, excludedFrames: $0.excludedFrames.sorted()) })
    }

    /// Schrijft de sessie (best effort; fouten worden niet gemeld aan de gebruiker maar breken niets). Asynchroon, zodat de UI niet wacht.
    @MainActor static func save(_ s: ScanStore) {
        guard let job = makeWriteJob(s) else { return }
        DispatchQueue.global(qos: .utility).async { job() }
    }

    /// Zelfde als `save`, maar synchroon (voor de CI-selftest en voor afsluiten).
    @MainActor static func saveNow(_ s: ScanStore) { makeWriteJob(s)?() }

    @MainActor private static func makeWriteJob(_ s: ScanStore) -> (() -> Void)? {
        guard !s.sessionId.isEmpty, !s.keyframes.isEmpty, let dir = sessionDir(s.sessionId) else { return nil }
        let snap = snapshot(s)
        var depths = s.keyframes.compactMap { k in k.depth.map { (k.id, $0) } }
        for k in s.keyframes {
            if let sm = k.smoothedDepth { depths.append(("\(k.id).smooth", sm)) }
            for sup in k.supportDepths { depths.append((sup.id, sup.depth)) }
        }
        let depthFiles = depths
        return {
            for (id, d) in depthFiles {
                let url = dir.appendingPathComponent("\(id).depth")
                if !FileManager.default.fileExists(atPath: url.path) { try? writeDepth(d, to: url) }     // brondata wordt nooit overschreven
            }
            let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601; enc.outputFormatting = [.sortedKeys]
            if let data = try? enc.encode(snap) { try? data.write(to: dir.appendingPathComponent("session.json"), options: [.atomic, .completeFileProtection]) }
        }
    }

    /// Nieuwste opgeslagen sessie (voor "Laatste scan hervatten").
    static func latest() -> (SessionSnapshot, URL)? {
        guard let root, let dirs = try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) else { return nil }
        var best: (SessionSnapshot, URL)? = nil
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        for d in dirs {
            guard let data = try? Data(contentsOf: d.appendingPathComponent("session.json")), let s = try? dec.decode(SessionSnapshot.self, from: data), !s.isSimulation else { continue }
            if best == nil || s.savedAt > best!.0.savedAt { best = (s, d) }
        }
        return best
    }

    /// Alle bewaarde fotorondes (nieuwste eerst), eventueel beperkt tot één project (planRef).
    static func rounds(planRef: String? = nil) -> [(SessionSnapshot, URL)] {
        guard let root, let dirs = try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) else { return [] }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return dirs.compactMap { d -> (SessionSnapshot, URL)? in
            guard let data = try? Data(contentsOf: d.appendingPathComponent("session.json")), let s = try? dec.decode(SessionSnapshot.self, from: data),
                  let r = s.round, !s.isSimulation, planRef == nil || r.context.planRef == planRef else { return nil }
            return (s, d)
        }.sorted { $0.0.savedAt > $1.0.savedAt }
    }

    static func latestAny() -> (SessionSnapshot, URL)? {      // incl. simulatie (voor tests)
        guard let root, let dirs = try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) else { return nil }
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return dirs.compactMap { d -> (SessionSnapshot, URL)? in
            guard let data = try? Data(contentsOf: d.appendingPathComponent("session.json")), let s = try? dec.decode(SessionSnapshot.self, from: data) else { return nil }
            return (s, d)
        }.max { $0.0.savedAt < $1.0.savedAt }
    }

    @MainActor static func restore(_ snap: SessionSnapshot, from dir: URL, into s: ScanStore) {
        s.newSession()
        s.sessionId = snap.sessionId; s.buildingId = snap.buildingId; s.facadeId = snap.facadeId; s.isSimulation = snap.isSimulation
        s.keyframes = snap.keyframes.map { k -> Keyframe in
            var kf = Keyframe(id: k.id, timestamp: k.timestamp, intrinsics: k.intrinsics, pose: k.pose, trackingState: k.trackingState,
                              depth: k.depthFile.flatMap { readDepth(dir.appendingPathComponent($0), width: k.depthWidth, height: k.depthHeight) },
                              imageURL: k.imageFile.map { dir.appendingPathComponent($0) })
            kf.smoothedDepth = k.smoothedFile.flatMap { readDepth(dir.appendingPathComponent($0), width: k.depthWidth, height: k.depthHeight) }
            kf.supportDepths = (k.supports ?? []).compactMap { sp in
                readDepth(dir.appendingPathComponent(sp.depthFile), width: sp.depthWidth, height: sp.depthHeight).map {
                    SupportDepth(id: sp.id, timestamp: sp.timestamp, intrinsics: sp.intrinsics, pose: sp.pose, trackingState: sp.trackingState, depth: $0)
                }
            }
            return kf
        }
        s.observations = snap.observations.map { o in
            Observation(id: o.id, frameId: o.frameId, corners: o.corners, originalCorners: o.originalCorners, source: CornerSource(rawValue: o.source) ?? .MANUAL,
                        revisions: o.revisions.map { CornerRevision(index: $0.index, before: $0.before, after: $0.after, editedBy: $0.editedBy, editedAt: $0.editedAt, reason: $0.reason) },
                        obstruction: o.obstruction, detection: o.detector.map { DetectionInfo(detector: $0, score: o.score ?? 0) }, rejected: o.rejected)
        }
        s.drafts = snap.drafts.map { ObjectDraft(id: $0.id, observationIds: $0.observationIds) }
        for r in snap.references {
            var m = ReferenceMeasure(referenceId: r.referenceId, p1: r.p1, p2: r.p2, distanceM: r.distanceM, distanceSigmaM: r.distanceSigmaM, planeId: r.planeId, anchorObservationId: r.anchorObservationId,
                                      kind: ReferenceMeasure.Kind(rawValue: r.kind ?? "USER_ESTIMATE") ?? .userEstimate)
            m.frameId = r.frameId
            s.references[r.frameId] = m
        }
        s.dismissedLinks = Set(snap.dismissedLinks)
        s.round = snap.round.map { RoundState(context: $0.context, status: $0.status, revision: $0.revision, facades: $0.facades, frameFacade: $0.frameFacade,
                                              frameWorld: $0.frameWorld, excludedFrames: Set($0.excludedFrames)) }
        s.measureAll()
    }
}
