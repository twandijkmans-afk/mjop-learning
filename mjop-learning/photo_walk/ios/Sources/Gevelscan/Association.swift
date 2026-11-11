import Foundation
import PhotoWalkCore

// Onderdeel C — objectassociatie: welke waarnemingen op verschillende foto's zijn hetzelfde fysieke kozijn?
//
// Regels (deterministisch, getest):
// * Vergelijken kan alleen met ruimtelijk bewijs: beide waarnemingen hebben 3D-hoeken op een gemeten vlak, in DEZELFDE AR-sessie.
// * Sterke overlap van de twee rechthoeken op het gedeelde vlak => zelfde object (samengevoegd).
// * Zwakke of dubbelzinnige overlap => identiteit ONZEKER: niet samengevoegd, niet als apart geteld; het aantal wordt dan niet vastgesteld
//   en er wordt een gerichte extra opname gevraagd.
// * Niet vergelijkbaar (geen meting, onbekende of andere sessie) => NIET GECONTROLEERD. Dat telt nooit als "geen duplicaat".
// * Uitdrukkelijke keuzes van de gebruiker (koppelen / "dit zijn verschillende kozijnen") gaan altijd voor.

/// Eén waarneming van een kozijn-achtig object op één foto, met (indien beschikbaar) de bestaande niveau-A/C-meting.
public struct FrameSighting {
    public var id: String
    public var photoId: String
    public var facadeId: String
    public var worldId: String?
    public var elementClass: ElementClass                   // KOZIJN (onbepaald), RAAM of DEUR
    public var polygon: [Pixel]                             // buitencontour, TL TR BR BL
    public var pose: Pose
    public var intrinsics: Intrinsics
    /// Bestaande meting van deze waarneming, ZONDER de contourpoort (zie `SightingMeasurement.ungated`). nil = niet gemeten.
    public var result: LevelResult?
    /// Buitencontour door de gebruiker bevestigd of zelf getekend.
    public var contourUserConfirmed: Bool
    public var contourStatus: OuterContourStatus
    public var evidence: OpeningEvidence
    public var detector: DetectorDescriptor
    public var score: Double?
    public var panes: [ElementDetection]                    // GLASVLAK binnen dit kozijn
    public var parts: [ElementDetection]                    // DRAAIEND_DEEL / VAST_DEEL (alleen van een getraind model of de gebruiker)
    public var glareFractionByPane: [String: Double]        // glasvlak-id -> aandeel bijna-wit (spiegeling)
    public init(id: String, photoId: String, facadeId: String, worldId: String?, elementClass: ElementClass = .KOZIJN, polygon: [Pixel], pose: Pose, intrinsics: Intrinsics,
                result: LevelResult?, contourUserConfirmed: Bool, contourStatus: OuterContourStatus, evidence: OpeningEvidence, detector: DetectorDescriptor, score: Double? = nil,
                panes: [ElementDetection] = [], parts: [ElementDetection] = [], glareFractionByPane: [String: Double] = [:]) {
        self.id = id; self.photoId = photoId; self.facadeId = facadeId; self.worldId = worldId; self.elementClass = elementClass; self.polygon = polygon; self.pose = pose
        self.intrinsics = intrinsics; self.result = result; self.contourUserConfirmed = contourUserConfirmed; self.contourStatus = contourStatus; self.evidence = evidence
        self.detector = detector; self.score = score; self.panes = panes; self.parts = parts; self.glareFractionByPane = glareFractionByPane
    }
    /// Ruimtelijk vergelijkbaar: geldige maat met 3D-hoeken en vlak.
    public var spatial: (corners: [Vec3], n: Vec3, d: Double, width: Double, height: Double)? {
        guard let r = result, r.ok, let c = r.cornersWorld, c.count == 4, let n = r.planeN, let d = r.planeD, let w = r.width, let h = r.height else { return nil }
        return (c, n, d, w, h)
    }
}

public enum SightingMeasurement {
    /// De app zet op een onbevestigde automatische buitencontour de blokkerende code OUTER_CONTOUR_UNVERIFIED (ContourGate). Gevelscanner 2.0
    /// behandelt de contourzekerheid als APART bewijs (zie OutcomeRules) en haalt die ene code hier van de meting af. Alle andere poorten
    /// (schaal, vlak, hoeken, bereik) blijven ongewijzigd gelden; er wordt geen drempel aangepast.
    public static func ungated(_ r: LevelResult) -> LevelResult {
        var g = r
        g.flags.removeAll { $0.code == "OUTER_CONTOUR_UNVERIFIED" }
        return g
    }
}

public struct AssociationConstraints: Equatable {
    public var mustLink: [[String]]                         // groepen waarnemingen die de gebruiker als één kozijn heeft gekoppeld
    public var cannotLink: [[String]]                       // paren die de gebruiker uitdrukkelijk als verschillend heeft aangemerkt
    public init(mustLink: [[String]] = [], cannotLink: [[String]] = []) { self.mustLink = mustLink; self.cannotLink = cannotLink }
}

public struct AssociationDecision: Equatable {
    public enum Kind: String, Codable, Sendable {
        case SAME_STRONG, SAME_USER, SAME_PHOTO_DUPLICATE, UNCERTAIN_WEAK_OVERLAP, UNCERTAIN_AMBIGUOUS, UNCERTAIN_SAME_PHOTO_OVERLAP, UNCERTAIN_PLANE_MISMATCH, DISTINCT_USER
    }
    public var a: String, b: String
    public var kind: Kind
    public var iou: Double?                                 // overlap van de rechthoeken op het gedeelde vlak (of in pixels op dezelfde foto)
    public var centerDistanceM: Double?
}

public struct PhysicalObject: Equatable {
    public enum Identity: String, Codable, Sendable {
        /// Eenduidig: geen onzekere of ongecontroleerde vergelijkingen.
        case RESOLVED
        /// Uniek volgens een uitdrukkelijke verklaring van de gebruiker (alle foto's nagelopen).
        case RESOLVED_BY_USER
        /// Mogelijk hetzelfde als een ander object.
        case UNCERTAIN
        /// Kon niet met alle andere objecten vergeleken worden.
        case UNCHECKED
    }
    public var id: String
    public var facadeId: String
    public var sightingIds: [String]
    public var photoIds: [String]
    public var identity: Identity
    public var identityReasons: [String]                    // MOGELIJK_DUBBEL, GEEN_RUIMTELIJKE_METING, ONBEKENDE_SESSIE, MEERDERE_SESSIES, TEGENSTRIJDIGE_KOPPELING
    public var possibleSameAs: [String]                     // id's van objecten waarmee de identiteit onzeker is
    public var facadeConflict: Bool                         // waarnemingen van dit object staan bij verschillende gevels ingedeeld
}

public struct AssociationResult: Equatable {
    public var objects: [PhysicalObject]
    public var decisions: [AssociationDecision]
    public var requests: [CaptureRequest]
    /// Zijn er objecten op VERSCHILLENDE gevels die niet met elkaar vergeleken konden worden (bv. een hoekkozijn dat bij twee gevels is
    /// gefotografeerd in aparte sessies)? Dan is een gebouwtotaal niet vrij van mogelijke dubbeltelling.
    public var crossFacadeUnchecked: Bool
}

public enum ObjectAssociator {
    public static func objectId(roundId: String, firstSightingId: String) -> String {
        "GO-" + String(format: "%08x", UInt32(truncatingIfNeeded: gevelscanHash(roundId + "|" + firstSightingId)))
    }

    static func rectIoUOnPlane(_ a: FrameSighting, _ b: FrameSighting) -> (iou: Double, centerDist: Double)? {
        guard let sa = a.spatial, let sb = b.spatial, let frame = PlaneFrame2D(n: sa.n, d: sa.d) else { return nil }
        let pa = sa.corners.map { frame.to2D($0) }, pb = sb.corners.map { frame.to2D($0) }
        let ca = sa.corners.reduce(Vec3.zero, +) * 0.25, cb = sb.corners.reduce(Vec3.zero, +) * 0.25
        return (polygonIoU(pa, pb), (ca - cb).norm)
    }

    public static func associate(_ sightings: [FrameSighting], roundId: String, constraints: AssociationConstraints = .init(), userReviewedAll: Bool = false,
                                 cfg: GevelscanConfig = GevelscanConfig()) -> AssociationResult {
        let items = sightings.sorted { $0.id < $1.id }
        let n = items.count
        var parent = Array(0..<n)
        func find(_ i: Int) -> Int { var x = i; while parent[x] != x { x = parent[x] }; return x }
        func union(_ i: Int, _ j: Int) { let a = find(i), b = find(j); if a != b { parent[max(a, b)] = min(a, b) } }
        let index = Dictionary(uniqueKeysWithValues: items.enumerated().map { ($1.id, $0) })
        var cannot = Set<String>()
        for pair in constraints.cannotLink where pair.count == 2 { cannot.insert(pair.sorted().joined(separator: "|")) }
        func isCannot(_ i: Int, _ j: Int) -> Bool { cannot.contains([items[i].id, items[j].id].sorted().joined(separator: "|")) }

        var decisions: [AssociationDecision] = []
        var userLinked = Set<String>()
        for group in constraints.mustLink {
            let idx = group.compactMap { index[$0] }
            for k in idx.dropFirst() {
                union(idx[0], k)
                decisions.append(.init(a: items[min(idx[0], k)].id, b: items[max(idx[0], k)].id, kind: .SAME_USER, iou: nil, centerDistanceM: nil))
                userLinked.insert([items[idx[0]].id, items[k].id].sorted().joined(separator: "|"))
            }
        }

        // 1. kandidaten per paar
        struct Cand { var i: Int, j: Int, iou: Double, dist: Double, strong: Bool }
        var cands: [Cand] = []
        var uncertain: [(Int, Int, AssociationDecision.Kind, Double?, Double?)] = []
        for i in 0..<n { for j in (i + 1)..<max(n, i + 1) where j < n {
            let a = items[i], b = items[j]
            if isCannot(i, j) { decisions.append(.init(a: a.id, b: b.id, kind: .DISTINCT_USER, iou: nil, centerDistanceM: nil)); continue }
            if a.photoId == b.photoId {
                let iou = polygonIoU(a.polygon, b.polygon)
                let inter = convexIntersectionArea(a.polygon, b.polygon), small = min(polygonArea(a.polygon), polygonArea(b.polygon))
                if iou >= cfg.samePhotoMergeIoU { union(i, j); decisions.append(.init(a: a.id, b: b.id, kind: .SAME_PHOTO_DUPLICATE, iou: round(iou, 3), centerDistanceM: nil)) }
                else if small > 0 && inter / small >= cfg.samePhotoOverlap { uncertain.append((i, j, .UNCERTAIN_SAME_PHOTO_OVERLAP, round(iou, 3), nil)) }
                continue
            }
            guard let wa = a.worldId, let wb = b.worldId, wa == wb, let sa = a.spatial, let sb = b.spatial else { continue }
            let cosA = max(-1, min(1, abs(sa.n.normalized.dot(sb.n.normalized))))
            let sgn: Double = sa.n.dot(sb.n) >= 0 ? 1 : -1
            let minDim = min(sa.width, sa.height, sb.width, sb.height)
            if acos(cosA) * 180 / Double.pi > cfg.sameNormalDeg || abs(sa.d - sgn * sb.d) > cfg.samePlaneOffsetM {
                // Vlakken komen niet overeen (ander vlak, of een slechte vlakfit / tracking-drift). Liggen de middelpunten toch dicht bij elkaar,
                // dan is "verschillend" niet bewezen: onzeker, niet stil als twee kozijnen tellen.
                let dist = ((sa.corners.reduce(Vec3.zero, +) * 0.25) - (sb.corners.reduce(Vec3.zero, +) * 0.25)).norm
                if dist <= cfg.weakCenterFactor * minDim { uncertain.append((i, j, .UNCERTAIN_PLANE_MISMATCH, nil, round(dist, 3))) }
                continue
            }
            guard let m = rectIoUOnPlane(a, b) else { continue }
            let ratio = max(max(sa.width, sb.width) / max(min(sa.width, sb.width), 1e-9), max(sa.height, sb.height) / max(min(sa.height, sb.height), 1e-9))
            if m.iou >= cfg.strongIoU && ratio <= cfg.strongSizeRatio { cands.append(Cand(i: i, j: j, iou: m.iou, dist: m.centerDist, strong: true)) }
            else if m.iou >= cfg.weakIoU || m.centerDist <= cfg.weakCenterFactor * minDim { cands.append(Cand(i: i, j: j, iou: m.iou, dist: m.centerDist, strong: false)) }
        } }
        // 2. dubbelzinnig: één waarneming past sterk op twee waarnemingen van dezelfde andere foto => geen van beide automatisch
        func partnersInSamePhoto(_ c: Cand, of x: Int) -> Int {
            let other = c.i == x ? c.j : c.i
            return cands.filter { $0.strong && ($0.i == x || $0.j == x) && items[$0.i == x ? $0.j : $0.i].photoId == items[other].photoId }.count
        }
        for c in cands {
            let a = items[c.i], b = items[c.j]
            if !c.strong { uncertain.append((c.i, c.j, .UNCERTAIN_WEAK_OVERLAP, round(c.iou, 3), round(c.dist, 3))); continue }
            if partnersInSamePhoto(c, of: c.i) > 1 || partnersInSamePhoto(c, of: c.j) > 1 { uncertain.append((c.i, c.j, .UNCERTAIN_AMBIGUOUS, round(c.iou, 3), round(c.dist, 3))); continue }
            union(c.i, c.j)
            decisions.append(.init(a: a.id, b: b.id, kind: .SAME_STRONG, iou: round(c.iou, 3), centerDistanceM: round(c.dist, 3)))
        }

        // 3. clusters -> objecten
        var clusters: [Int: [Int]] = [:]
        for i in 0..<n { clusters[find(i), default: []].append(i) }
        let roots = clusters.keys.sorted()
        var usedIds = Set<String>()
        var objects: [PhysicalObject] = roots.map { r in
            let mem = clusters[r]!
            let facades = Dictionary(grouping: mem) { items[$0].facadeId }
            // gevel = die van de meeste waarnemingen (bij gelijkspel de alfabetisch eerste); verschil wordt gemeld, nooit stil opgelost
            let facade = facades.max { ($0.value.count, $1.key) < ($1.value.count, $0.key) }!.key
            // de id is een korte hash; bij een (zeldzame) botsing binnen één ronde krijgt het latere object een volgnummer
            var oid = objectId(roundId: roundId, firstSightingId: items[mem[0]].id)
            var n = 2
            while !usedIds.insert(oid).inserted { oid = objectId(roundId: roundId, firstSightingId: items[mem[0]].id) + "-\(n)"; n += 1 }
            return PhysicalObject(id: oid, facadeId: facade, sightingIds: mem.map { items[$0].id },
                                  photoIds: Array(Set(mem.map { items[$0].photoId })).sorted(), identity: .RESOLVED, identityReasons: [], possibleSameAs: [],
                                  facadeConflict: facades.count > 1)
        }
        let objIndexOfRoot = Dictionary(uniqueKeysWithValues: roots.enumerated().map { ($1, $0) })
        func obj(_ i: Int) -> Int { objIndexOfRoot[find(i)]! }
        func addReason(_ k: Int, _ r: String) { if !objects[k].identityReasons.contains(r) { objects[k].identityReasons.append(r) } }

        // 3a. een cluster met twee verschillende waarnemingen op dezelfde foto (niet als duplicaat samengevoegd) is tegenstrijdig
        let dupSamePhoto = Set(decisions.filter { $0.kind == .SAME_PHOTO_DUPLICATE || $0.kind == .SAME_USER }.map { [$0.a, $0.b].sorted().joined(separator: "|") })
        for (k, r) in roots.enumerated() {
            let mem = clusters[r]!
            outer: for x in mem { for y in mem where x < y && items[x].photoId == items[y].photoId {
                if !dupSamePhoto.contains([items[x].id, items[y].id].sorted().joined(separator: "|")) { addReason(k, "TEGENSTRIJDIGE_KOPPELING"); break outer }
            } }
        }
        //     ... en ook een cluster waarin (via een derde waarneming) twee waarnemingen zitten die de gebruiker uitdrukkelijk als verschillend aanmerkte
        for (k, r) in roots.enumerated() {
            let mem = clusters[r]!
            outer2: for x in mem { for y in mem where x < y && isCannot(x, y) { addReason(k, "TEGENSTRIJDIGE_KOPPELING"); break outer2 } }
        }
        // 3b. onzekere paren tussen verschillende objecten
        for (i, j, kind, iou, dist) in uncertain {
            let a = obj(i), b = obj(j)
            if a == b { continue }
            decisions.append(.init(a: items[i].id, b: items[j].id, kind: kind, iou: iou, centerDistanceM: dist))
            addReason(a, "MOGELIJK_DUBBEL"); addReason(b, "MOGELIJK_DUBBEL")
            if !objects[a].possibleSameAs.contains(objects[b].id) { objects[a].possibleSameAs.append(objects[b].id) }
            if !objects[b].possibleSameAs.contains(objects[a].id) { objects[b].possibleSameAs.append(objects[a].id) }
        }
        // 3c. dekking van de vergelijking per gevel: kon elk paar objecten wel vergeleken worden?
        //     Vergelijkbaar = samen op één foto, of beide een ruimtelijke meting in dezelfde bekende sessie.
        func comparable(_ ka: Int, _ kb: Int) -> (Bool, String) {
            let ma = clusters[roots[ka]]!, mb = clusters[roots[kb]]!
            for x in ma { for y in mb where items[x].photoId == items[y].photoId { return (true, "") } }
            let sa = ma.filter { items[$0].spatial != nil }, sb = mb.filter { items[$0].spatial != nil }
            if sa.isEmpty || sb.isEmpty { return (false, "GEEN_RUIMTELIJKE_METING") }
            let wa = Set(sa.compactMap { items[$0].worldId }), wb = Set(sb.compactMap { items[$0].worldId })
            if wa.isEmpty || wb.isEmpty { return (false, "ONBEKENDE_SESSIE") }
            return wa.isDisjoint(with: wb) ? (false, "MEERDERE_SESSIES") : (true, "")
        }
        var crossFacadeUnchecked = false
        for a in 0..<objects.count { for b in (a + 1)..<max(objects.count, a + 1) where b < objects.count {
            if isUserDistinct(objects[a], objects[b], cannot) { continue }
            let (ok, why) = comparable(a, b)
            if ok { continue }
            // binnen één gevel raakt dit de objecten zelf; tussen gevels alleen het gebouwtotaal
            if objects[a].facadeId == objects[b].facadeId { addReason(a, why); addReason(b, why) } else { crossFacadeUnchecked = true }
        } }
        var requests: [CaptureRequest] = []
        for k in objects.indices {
            let rs = objects[k].identityReasons
            if rs.contains("MOGELIJK_DUBBEL") || rs.contains("TEGENSTRIJDIGE_KOPPELING") { objects[k].identity = .UNCERTAIN }
            else if !rs.isEmpty { objects[k].identity = userReviewedAll ? .RESOLVED_BY_USER : .UNCHECKED }
            switch objects[k].identity {
            case .UNCERTAIN: requests.append(.init(kind: .OVERZICHTSFOTO, facadeId: objects[k].facadeId, objectId: objects[k].id, reason: "MOGELIJK_DUBBEL"))
            case .UNCHECKED:
                if rs.contains("MEERDERE_SESSIES") || rs.contains("ONBEKENDE_SESSIE") { requests.append(.init(kind: .ZELFDE_SCANSESSIE, facadeId: objects[k].facadeId, objectId: objects[k].id, reason: rs.first ?? "")) }
                else { requests.append(.init(kind: .BETERE_DIEPTE, facadeId: objects[k].facadeId, objectId: objects[k].id, reason: "GEEN_RUIMTELIJKE_METING")) }
            default: break
            }
            objects[k].possibleSameAs.sort()
            objects[k].identityReasons.sort()
        }
        decisions.sort { ($0.a, $0.b, $0.kind.rawValue) < ($1.a, $1.b, $1.kind.rawValue) }
        return AssociationResult(objects: objects.sorted { $0.id < $1.id }, decisions: decisions, requests: requests, crossFacadeUnchecked: crossFacadeUnchecked && !userReviewedAll)
    }

    /// Heeft de gebruiker ALLE waarnemingsparen van deze twee objecten uitdrukkelijk als verschillend aangemerkt?
    static func isUserDistinct(_ a: PhysicalObject, _ b: PhysicalObject, _ cannot: Set<String>) -> Bool {
        for x in a.sightingIds { for y in b.sightingIds where !cannot.contains([x, y].sorted().joined(separator: "|")) { return false } }
        return true
    }
}
