import Foundation
import UIKit
import MJOPIntegration
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
    /// Ondersteunende LiDAR-dieptekaders uit de korte buffer vlak voor de foto (eigen pose/tracking). Alleen geometrisch onafhankelijke kaders worden door de kern gebruikt.
    var supportDepths: [SupportDepth] = []
    /// ARKit smoothedSceneDepth van HETZELFDE frame: sterk gecorreleerd met `depth`, daarom uitsluitend een kruiscontrole in de diagnose (nooit extra bewijs).
    var smoothedDepth: DepthMap? = nil
}

struct SupportDepth: Identifiable {
    let id: String
    let timestamp: Date
    let intrinsics: Intrinsics
    let pose: Pose
    let trackingState: String
    let depth: DepthMap
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
    /// Zekerheid van de BUITENCONTOUR (gevelopbouw). Handmatig getekend = MANUAL; oudere opgeslagen waarnemingen worden LEGACY (ongewijzigd gedrag).
    /// UNVERIFIED (glas of kozijn?) en PROPOSED_EXPANSION (voorstel vanaf het glas) geven geen kozijnmaat tot de gebruiker bevestigt.
    var outerContour: OuterContourStatus = .MANUAL
    var evidence: OpeningEvidence = .MANUAL
    /// Voorgestelde buitencontour (randzoeker) bij een losse rechthoek; wordt alleen op knop toegepast en moet daarna bevestigd worden.
    var proposedOuter: [Pixel]? = nil
}

/// Gevelonderdeel dat GEEN kozijn is: een glasvlak binnen een kozijn of het getekende bruto gevelvlak van een foto.
/// Glasvlakken tellen nooit als kozijn en hebben geen eigen voorlopig object; originele contour en bron blijven bewaard.
struct FacadeElement: Identifiable, Equatable {
    let id: String
    let frameId: String
    var role: FacadeRole                    // GLASS_PANE | FACADE_GROSS
    var corners: [Pixel]
    let originalCorners: [Pixel]
    var source: CornerSource
    var parentObservationId: String?        // GLASS_PANE -> het kozijn
    var rejected = false
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
    var outerUnverified = 0         // glas of kozijn? / voorgestelde buitencontour: nog bevestigen
    var glassPanes = 0              // herkende glasvlakken (tellen niet als kozijn)
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
        let sup = kf.supportDepths.map { ViewInput(frameId: $0.id, intrinsics: $0.intrinsics, pose: $0.pose, trackingNormal: $0.trackingState == "NORMAL", depth: $0.depth) }
        return ViewInput(frameId: kf.id, intrinsics: kf.intrinsics, pose: kf.pose, trackingNormal: kf.trackingState == "NORMAL", depth: kf.depth, supports: sup)
    }

    static func measure(_ o: Observation, frames: [String: Keyframe], observations: [String: Observation], references: [String: ReferenceMeasure]) -> LevelResult {
        guard let kf = frames[o.frameId] else {
            var r = LevelResult(level: .A, scaleMethod: "NONE"); r.flags = [Flags.make("NO_DEPTH", "keyframe ontbreekt")]; return r
        }
        let v = input(kf)
        var r = measureDepthView(v, corners: o.corners, seed: stableSeed(o.id), obstruction: o.obstruction)
        if let sm = kf.smoothedDepth {          // kruiscontrole op de gladgestreken diepte van hetzelfde frame (gecorreleerd: alleen diagnose)
            var vs = v; vs.depth = sm; vs.supports = []
            let rs = measureDepthView(vs, corners: o.corners, seed: stableSeed(o.id))
            r.diag["smoothed_cross_check"] = ["ok": rs.ok, "width_m": rdOpt(rs.width), "height_m": rdOpt(rs.height),
                                              "delta_width_m": rdOpt(rs.ok && r.ok ? (rs.width ?? 0) - (r.width ?? 0) : nil),
                                              "delta_height_m": rdOpt(rs.ok && r.ok ? (rs.height ?? 0) - (r.height ?? 0) : nil),
                                              "note": "gecorreleerd met de hoofdmeting; geen onafhankelijk bewijs"] as [String: Any]
        }
        if !r.ok, let ref = references[o.frameId] {
            var anchor: [Pixel]? = nil
            if let aid = ref.anchorObservationId, aid != o.id, let a = observations[aid], !a.rejected { anchor = a.corners }
            let rc = measureWithReference(view: v, target: o.corners, ref: ref, anchor: anchor, seed: stableSeed(o.id + "C"))
            if rc.ok { var rc2 = rc; rc2.diag = r.diag; rc2.diag["fallback"] = "REFERENCE_DISTANCE (niveau A gaf geen maat)"; rc2.diag["lidar_flags_before_fallback"] = r.flags.map { $0.code }; r = rc2 } else { r.flags += rc.flags.filter { $0.severity == .BLOCKING }.map { QualityFlag(code: $0.code, severity: $0.severity, detail: "[referentie] \($0.detail ?? "")", instruction_nl: $0.instruction_nl) } }
        }
        // glas of kozijn? / voorgestelde vergroting: geen kozijnmaat tot de gebruiker de buitencontour bevestigt of zelf aangeeft
        if o.outerContour.blocksArea { r.flags.append(Flags.make("OUTER_CONTOUR_UNVERIFIED", o.outerContour.rawValue)) }
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
            else if let a = okA.first { final = a; viewCount = max(1, a.independentFrames) }      // onafhankelijke diepteframes tellen als standpunten
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

/// Fotoronde-gegevens van een scansessie (alleen aanwezig als de sessie vanuit Mijn MJOP is gestart). De metingen zelf staan in de gewone sessiegegevens.
struct RoundState: Equatable {
    struct Facade: Equatable, Codable, Identifiable { var id: String; var orientation: String?
        init(id: String, orientation: String?) { self.id = id; self.orientation = orientation } }
    var context: PhotoRoundContext
    var status = "IN_PROGRESS"                 // IN_PROGRESS | COMPLETED
    var revision = 1                           // verhoogt als een afgeronde ronde opnieuw wordt afgerond
    var facades: [Facade] = []
    var frameFacade: [String: String] = [:]    // foto -> gevel
    var frameWorld: [String: String] = [:]     // foto -> AR-sessie (eigen coördinatenstelsel); alleen binnen één sessie zijn kozijnen vergelijkbaar
    var excludedFrames: Set<String> = []       // foto's die de inspecteur niet wil laten meetellen (overlap)
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
    @Published var round: RoundState? = nil
    @Published var facadeElements: [FacadeElement] = []

    func newSession() {
        sessionId = UUID().uuidString; keyframes = []; observations = []; drafts = []; references = [:]; results = []; measures = [:]
        analyzing = []; analysisNotes = [:]; dismissedLinks = []; isSimulation = false; round = nil; facadeElements = []
    }

    /// Legt bij een nieuwe foto vast bij welke gevel en in welk AR-coördinatenstelsel hij is gemaakt (alleen in een fotoronde).
    func tagKeyframe(_ id: String, world: String) {
        guard round != nil else { return }
        round?.frameFacade[id] = facadeId
        round?.frameWorld[id] = world
        if !facadeId.isEmpty, !(round?.facades.contains { $0.id == facadeId } ?? true) { round?.facades.append(.init(id: facadeId, orientation: nil)) }
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
        // de inspecteur heeft de hoeken zelf naar de buitenrand gesleept: dit is nu een door de gebruiker aangegeven buitencontour
        if observations[i].outerContour != .LEGACY { observations[i].outerContour = .MANUAL }
    }

    /// "Dit is de buitenmaat": bevestigt de HOEKEN als buitencontour van het kozijn (geen goedkeuring van de hoeveelheid).
    func confirmCorners(observation id: String) {
        guard let i = observations.firstIndex(where: { $0.id == id }) else { return }
        if observations[i].source == .AUTO_DETECTED_UNCONFIRMED { observations[i].source = .AUTO_DETECTED_CONFIRMED }
        if observations[i].outerContour != .LEGACY && observations[i].outerContour != .MANUAL { observations[i].outerContour = .USER_CONFIRMED }
    }

    /// Past de voorgestelde buitencontour (randzoeker) toe: de oude vierhoek wordt een glasvlak van dit kozijn. Daarna blijft de maat
    /// geblokkeerd (PROPOSED_EXPANSION) tot de gebruiker "Dit is de buitenmaat" kiest of de hoeken zelf versleept.
    func applyProposedOuter(observation id: String) {
        guard let i = observations.firstIndex(where: { $0.id == id }), let prop = observations[i].proposedOuter, prop.count == 4 else { return }
        let o = observations[i]
        facadeElements.append(FacadeElement(id: nextElementId(frameId: o.frameId, prefix: "GLS"), frameId: o.frameId, role: .GLASS_PANE, corners: o.corners,
                                            originalCorners: o.corners, source: o.source == .AUTO_DETECTED_UNCONFIRMED ? .AUTO_DETECTED_UNCONFIRMED : .MANUAL, parentObservationId: o.id))
        for k in 0..<4 where o.corners[k] != prop[k] {
            observations[i].revisions.append(CornerRevision(index: k, before: o.corners[k], after: prop[k], editedBy: "app-voorstel", editedAt: Date(),
                                                            reason: "voorgestelde buitencontour (randzoeker); nog niet bevestigd"))
        }
        observations[i].corners = prop
        observations[i].outerContour = .PROPOSED_EXPANSION
        observations[i].proposedOuter = nil
    }

    /// "Dit is een glasvlak": de vierhoek is geen kozijn. Hij wordt een glasvlak van het kleinste kozijn op dezelfde foto dat hem omsluit
    /// (indien aanwezig) en telt niet meer als kozijn. Bron en hoeken blijven bewaard.
    func markAsGlass(observation id: String) {
        guard let i = observations.firstIndex(where: { $0.id == id }) else { return }
        let o = observations[i]
        let parent = observations.filter { $0.id != o.id && $0.frameId == o.frameId && !$0.rejected && ContourOrganizer.contains($0.corners, o.corners, ContourConfig()) }
            .min { polygonArea($0.corners) < polygonArea($1.corners) }
        facadeElements.append(FacadeElement(id: nextElementId(frameId: o.frameId, prefix: "GLS"), frameId: o.frameId, role: .GLASS_PANE, corners: o.corners,
                                            originalCorners: o.originalCorners, source: o.source, parentObservationId: parent?.id))
        observations[i].rejected = true
        measureAll(); persist()
    }

    func setElementRejected(_ id: String, _ rejected: Bool) {
        guard let i = facadeElements.firstIndex(where: { $0.id == id }) else { return }
        facadeElements[i].rejected = rejected
        persist()
    }

    /// Bruto gevelvlak van een foto (door de gebruiker getekend). Een eerder vlak blijft bewaard maar telt niet meer mee.
    func setFacadePolygon(frameId: String, corners: [Pixel]) {
        for k in facadeElements.indices where facadeElements[k].frameId == frameId && facadeElements[k].role == .FACADE_GROSS { facadeElements[k].rejected = true }
        facadeElements.append(FacadeElement(id: nextElementId(frameId: frameId, prefix: "GEV"), frameId: frameId, role: .FACADE_GROSS, corners: corners,
                                            originalCorners: corners, source: .MANUAL, parentObservationId: nil))
        persist()
    }

    func facadePolygon(frameId: String) -> FacadeElement? { facadeElements.last { $0.frameId == frameId && $0.role == .FACADE_GROSS && !$0.rejected } }
    func glassPanes(frameId: String) -> [FacadeElement] { facadeElements.filter { $0.frameId == frameId && $0.role == .GLASS_PANE && !$0.rejected } }
    func glassPanes(ofObservation id: String) -> [FacadeElement] { facadeElements.filter { $0.parentObservationId == id && $0.role == .GLASS_PANE && !$0.rejected } }

    private func nextElementId(frameId: String, prefix: String) -> String {
        "\(prefix)-\(frameId)-\(String(format: "%02d", facadeElements.filter { $0.frameId == frameId }.count + 1))"
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
            guard da != db && !dismissedLinks.contains(c.a + "|" + c.b) else { return false }
            // Foto's uit verschillende AR-sessies hebben een eigen coördinatenstelsel: posities zijn dan niet vergelijkbaar, dus geen automatische suggestie.
            if let r = round, let fa = observation(c.a)?.frameId, let fb = observation(c.b)?.frameId, let wa = r.frameWorld[fa], let wb = r.frameWorld[fb], wa != wb { return false }
            return true
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

    /// Foto -> kandidaten (lokaal: Apple Vision-rechthoeken, -contouren, optioneel Core ML) -> ordenen tot kozijnen met glasvlakken -> meting.
    /// * Een vierhoek die glasvlakken omsluit wordt het kozijn (buitencontour); de glasvlakken worden glas, nooit aparte kozijnen.
    /// * Losse vierhoeken naast elkaar zijn de glasvlakken van één kozijn: de buitencontour is dan een VOORSTEL (randzoeker), geen maat.
    /// * Een losse vierhoek kan glas of kozijn zijn: geen maat tot bevestiging; een voorstel voor de buitencontour wordt klaargezet.
    /// Bestaande kandidaten van dezelfde foto blijven staan (nieuwe die er sterk mee overlappen worden genegeerd): opnieuw zoeken geeft geen dubbele kozijnen.
    typealias AnalysisOutput = (groups: [OpeningGroup], ignored: Int, raw: Int, proposals: [Int: ExpansionProposal])

    func analyze(frameId: String) async {
        guard let kf = keyframe(frameId), let url = kf.imageURL else { analysisNotes[frameId] = "Geen beeld beschikbaar voor detectie."; return }
        analyzing.insert(frameId)
        let detectors = DetectorCatalog.available()
        let out: AnalysisOutput = await Task.detached(priority: .userInitiated) { () -> AnalysisOutput in
            guard let cg = UIImage(contentsOfFile: url.path)?.cgImage else { return ([], 0, 0, [:]) }
            var all: [WindowCandidate] = []
            for d in detectors { all += d.detect(cg) }
            let cands = all.map { QuadCandidate(corners: $0.corners, detector: $0.detector, score: $0.score) }
            let (groups, ignored) = ContourOrganizer.organize(cands, imageWidth: Double(cg.width), imageHeight: Double(cg.height))
            var props: [Int: ExpansionProposal] = [:]
            if groups.contains(where: { $0.evidence != .NESTED_PANES }), let gray = GrayImageLoader.gray(cg) {
                for (k, g) in groups.enumerated() where g.evidence != .NESTED_PANES {
                    if let p = OuterFrameSearch.proposeOuter(gray, quad: g.outer) { props[k] = p }
                }
            }
            return (groups, ignored.count, all.count, props)
        }.value
        var added = 0, panesAdded = 0
        for (k, g) in out.groups.enumerated() {
            var corners = g.outer
            var proposed: [Pixel]? = nil
            if g.evidence == .PANE_GROUP, let p = out.proposals[k] { corners = p.quad }          // voorstel; blijft geblokkeerd tot bevestiging
            if g.evidence == .SINGLE { proposed = out.proposals[k]?.quad }                      // alleen klaarzetten, niet toepassen
            let existing = observations.filter { $0.frameId == frameId && !$0.rejected }
            if existing.contains(where: { CandidateFilter.iou($0.corners, corners) > 0.5 }) { continue }
            let id = "OBS-\(frameId)-\(String(format: "%02d", observations.filter { $0.frameId == frameId }.count + 1))"
            var o = Observation(id: id, frameId: frameId, corners: corners, originalCorners: corners, source: .AUTO_DETECTED_UNCONFIRMED,
                                detection: DetectionInfo(detector: g.detector, score: g.score))
            o.outerContour = g.status
            o.evidence = g.evidence
            o.proposedOuter = proposed
            addObservation(o, to: nil)
            added += 1
            for p in g.panes {
                facadeElements.append(FacadeElement(id: "GLS-\(frameId)-\(String(format: "%02d", facadeElements.filter { $0.frameId == frameId }.count + 1))", frameId: frameId,
                                                    role: .GLASS_PANE, corners: p, originalCorners: p, source: .AUTO_DETECTED_UNCONFIRMED, parentObservationId: id))
                panesAdded += 1
            }
        }
        await measureAllInBackground()
        analyzing.remove(frameId)
        let check = out.groups.filter { $0.status.blocksArea }.count
        analysisNotes[frameId] = "\(out.raw) vierhoek(en) van \(detectors.map { $0.name }.joined(separator: ", ")) -> \(out.groups.count) mogelijk(e) kozijn(en) (\(added) nieuw), " +
            "\(panesAdded) glasvlak(ken) (tellen niet als kozijn), \(check) met onbevestigde buitencontour, \(out.ignored) genegeerd. Dit zijn KANDIDATEN, geen bevestigde kozijnen."
        persist()
    }

    // MARK: gevelopbouw (bruto gevel, openingen, buitenkozijn, glas, netto gesloten gevel) per foto
    enum FacadePlaneSource: String { case LIDAR_FIT, REFERENCE_COPLANAR, NONE }

    func facadeComposition(frameId: String) -> (result: FacadeCompositionResult, planeSource: FacadePlaneSource)? {
        guard let kf = keyframe(frameId) else { return nil }
        let obs = observations.filter { $0.frameId == frameId && !$0.rejected }
        let openings = obs.map { o -> FacadeOpeningInput in
            let r = measures[o.id]?.result
            var area: Decimal? = nil
            var status: DimensionStatus = .UNKNOWN
            if let r, r.ok, let w = r.width, let h = r.height {
                area = grossAreaM2(width: roundedMillimeters(w), height: roundedMillimeters(h))
                status = Status.status(for: r, viewCount: 1)
            }
            return FacadeOpeningInput(id: o.id, outerPx: o.corners, areaM2: area, status: status, planeN: r?.ok == true ? r?.planeN : nil,
                                      planeD: r?.ok == true ? r?.planeD : nil, panesPx: glassPanes(ofObservation: o.id).map { $0.corners })
        }
        let facade = facadePolygon(frameId: frameId)?.corners
        var plane: (n: Vec3, d: Double)? = nil
        var source = FacadePlaneSource.NONE
        if let f = facade, let fit = FacadeComposition.fitFacadePlane(view: Measurer.input(kf), polygon: f, exclude: obs.map { $0.corners }, seed: stableSeed(frameId + "GEVEL")),
           kf.trackingState == "NORMAL" {
            plane = (fit.n, fit.d); source = .LIDAR_FIT
        } else if facade != nil, let ref = obs.compactMap({ measures[$0.id]?.result }).first(where: { $0.ok && $0.level == .C && $0.planeN != nil && $0.planeD != nil }) {
            plane = (ref.planeN!, ref.planeD!); source = .REFERENCE_COPLANAR        // aanname: gevel ligt in hetzelfde vlak als het kozijn met de referentie
        }
        let r = FacadeComposition.compose(openings: openings, pose: kf.pose, intr: kf.intrinsics, facadePx: facade, facadePlane: plane,
                                          facadePlaneStatus: plane == nil ? .UNKNOWN : .ESTIMATED)
        var res = r
        if source == .REFERENCE_COPLANAR { res.flags.append("COPLANARITY_ASSUMED") }
        return (res, source)
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
        ov.outerUnverified = obs.filter { $0.outerContour.blocksArea }.count
        ov.glassPanes = facadeElements.filter { $0.role == .GLASS_PANE && !$0.rejected && (frameId == nil || $0.frameId == frameId) }.count
        return ov
    }

    func persist() { Persistence.save(self) }
}
