import Foundation

// Gevelfoto: herkenning door Claude (alleen WAT er staat en WAAR, in pixels) en hoeveelheden met vaste regels (deze code).
// Overgezet uit MJOP-App gevelfoto/index.html (PROMPT_VERSION gevelfoto_v0.1). De maat komt uit de gevelbreedte van de BAG-omtrek.
// De uitkomst is altijd een voorstel; de gebruiker beslist wat in het plan komt.

public enum FacadeKind: String, Codable { case quad, line, poly }

public enum FacadeElementType: String, Codable, CaseIterable {
    case kozijn_raam, kozijn_deur, garagedeur, metselwerk, stucwerk, gevelbekleding, hwa, dakgoot, boeiboord, waterslag, hekwerk, balkon, luifel, rooster, overig

    public var label: String {
        switch self {
        case .kozijn_raam: return "Raamkozijn"
        case .kozijn_deur: return "Deurkozijn / buitendeur"
        case .garagedeur: return "Garagedeur"
        case .metselwerk: return "Metselwerk"
        case .stucwerk: return "Stucwerk"
        case .gevelbekleding: return "Gevelbekleding"
        case .hwa: return "Hemelwaterafvoer"
        case .dakgoot: return "Dakgoot"
        case .boeiboord: return "Boeiboord / dakrand"
        case .waterslag: return "Waterslag / lekdorpel"
        case .hekwerk: return "Hekwerk / balustrade"
        case .balkon: return "Balkon"
        case .luifel: return "Luifel"
        case .rooster: return "Ventilatierooster"
        case .overig: return "Overig"
        }
    }

    public var kind: FacadeKind {
        switch self {
        case .metselwerk, .stucwerk, .gevelbekleding: return .poly
        case .hwa, .dakgoot, .boeiboord, .waterslag, .hekwerk: return .line
        default: return .quad
        }
    }

    public var isOpening: Bool { self == .kozijn_raam || self == .kozijn_deur || self == .garagedeur }
    public var isWall: Bool { kind == .poly }
}

public struct FacadeElement: Codable, Equatable, Identifiable {
    public var id: Int
    public var type: FacadeElementType
    /// Punten in pixels van de foto (quad: linksboven, rechtsboven, rechtsonder, linksonder).
    public var points: [[Double]]
    public var material: String?
    public var confidence: String?
    public var note: String?
}

public struct FacadeQuantities: Equatable {
    public var widthM: Double?
    public var heightM: Double?
    public var areaM2: Double?
    public var lengthM: Double?
    public var grossM2: Double?
    public var openingsM2: Double?
    public var netM2: Double?
}

public enum FacadeError: LocalizedError, Equatable {
    case refused, truncated, unreadable
    public var errorDescription: String? {
        switch self {
        case .refused: return "Het model heeft deze foto geweigerd."
        case .truncated: return "Het antwoord van het model is afgekapt. Probeer een foto met minder elementen."
        case .unreadable: return "Het antwoord van het model was niet leesbaar."
        }
    }
}

public enum FacadePhoto {
    public static let promptVersion = "gevelfoto_v0.1"
    public static let model = "claude-opus-5-5"
    public static let maxEdge: Double = 2000

    public static func prompt(width W: Int, height H: Int) -> String {
        let list = FacadeElementType.allCases.map { t -> String in
            let g: String
            switch t.kind {
            case .quad: g = "bounding box, exactly 2 points: top-left and bottom-right"
            case .line: g = "polyline along the element, 2 or more points"
            case .poly: g = "polygon outlining the surface, 3 or more points in order"
            }
            return "- \(t.rawValue) (\(t.label)): \(g)"
        }.joined(separator: "\n")
        return """
        This is one photo of a building facade in the Netherlands, taken for a multi-year maintenance plan (MJOP). The image is \(W) x \(H) pixels.

        Find the building elements that are clearly visible on the facade in the foreground and report where they are. Coordinates are pixels in this image: origin at the top-left corner, x to the right, y down.

        Element types and the geometry to return for each:
        \(list)

        Guidelines:
        - One physical frame (kozijn) is one element, even when it holds several panes or opening sashes. Box the outer edge of the frame, not the glass.
        - For a wall surface (metselwerk, stucwerk, gevelbekleding) return one polygon per continuous surface of one material, following its outer edge and including the window and door openings that lie in it. The openings are subtracted afterwards by the calling program.
        - For hwa (downpipe), dakgoot (gutter), boeiboord (fascia), waterslag (sill) and hekwerk (railing), follow the centre line of the element from one end to the other.
        - Report only what you can actually see. Leave out elements that are hidden, that belong to a neighbouring building, or that you would have to guess.
        - "material": one short Dutch word when the material is clearly recognisable (for example hout, kunststof, aluminium, staal, baksteen, zink, pvc, beton), otherwise an empty string.
        - "confidence": how sure you are that the element exists and is of this type.
        - "note": at most a few words in Dutch when something limits the result (for example "deels achter boom"), otherwise an empty string.

        Do not estimate sizes in metres, condition, defects or costs: measurements are computed separately from your coordinates.

        Return only a JSON object of this shape, with no other text:
        {"elements": [{"type": "<one of the type keys above>", "points": [{"x": 0, "y": 0}], "material": "", "confidence": "low|medium|high", "note": ""}]}
        """
    }

    /// JSON-schema voor afgedwongen uitvoer.
    public static var schema: [String: Any] {
        ["type": "object", "additionalProperties": false, "required": ["elements"],
         "properties": ["elements": ["type": "array", "items": [
            "type": "object", "additionalProperties": false, "required": ["type", "points", "material", "confidence", "note"],
            "properties": [
                "type": ["type": "string", "enum": FacadeElementType.allCases.map(\.rawValue)],
                "points": ["type": "array", "items": ["type": "object", "additionalProperties": false, "required": ["x", "y"],
                                                     "properties": ["x": ["type": "number"], "y": ["type": "number"]]]],
                "material": ["type": "string"],
                "confidence": ["type": "string", "enum": ["low", "medium", "high"]],
                "note": ["type": "string"],
            ]]]]]
    }

    /// Body voor de Messages API (afbeelding als base64-JPEG).
    public static func requestBody(jpegBase64: String, width W: Int, height H: Int, structured: Bool) -> [String: Any] {
        var outputConfig: [String: Any] = ["effort": "high"]
        if structured { outputConfig["format"] = ["type": "json_schema", "schema": schema] }
        return ["model": model, "max_tokens": 16000, "output_config": outputConfig,
                "messages": [["role": "user", "content": [
                    ["type": "image", "source": ["type": "base64", "media_type": "image/jpeg", "data": jpegBase64]],
                    ["type": "text", "text": prompt(width: W, height: H)],
                ]]]]
    }

    /// Haalt de elementen uit het modelantwoord. Ongeldige elementen worden overgeslagen en geteld, nooit gerepareerd door te gokken.
    public static func parseResponse(_ data: Data, width W: Double, height H: Double, scale: Double = 1) throws -> (elements: [FacadeElement], skipped: Int) {
        guard let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { throw FacadeError.unreadable }
        if (o["stop_reason"] as? String) == "refusal" { throw FacadeError.refused }
        if (o["stop_reason"] as? String) == "max_tokens" { throw FacadeError.truncated }
        let text = ((o["content"] as? [[String: Any]]) ?? []).filter { ($0["type"] as? String) == "text" }.compactMap { $0["text"] as? String }.joined()
        var obj = (try? JSONSerialization.jsonObject(with: Data(text.utf8))) as? [String: Any]
        if obj == nil, let s = text.firstIndex(of: "{"), let e = text.lastIndex(of: "}"), s < e {
            obj = (try? JSONSerialization.jsonObject(with: Data(text[s...e].utf8))) as? [String: Any]
        }
        guard let elements = obj?["elements"] as? [[String: Any]] else { throw FacadeError.unreadable }
        return parseElements(elements, width: W, height: H, scale: scale)
    }

    public static func parseElements(_ raw: [[String: Any]], width W: Double, height H: Double, scale: Double) -> (elements: [FacadeElement], skipped: Int) {
        var out: [FacadeElement] = []
        var skipped = 0
        for r in raw {
            guard let ts = r["type"] as? String, let t = FacadeElementType(rawValue: ts) else { skipped += 1; continue }
            let rawPts = (r["points"] as? [[String: Any]]) ?? []
            var pts: [[Double]] = []
            var bad = false
            for p in rawPts {
                guard let x = (p["x"] as? NSNumber)?.doubleValue, let y = (p["y"] as? NSNumber)?.doubleValue, x.isFinite, y.isFinite else { bad = true; break }
                pts.append([min(W, max(0, x * scale)), min(H, max(0, y * scale))])
            }
            if bad { skipped += 1; continue }
            switch t.kind {
            case .quad:
                if pts.count == 2 { pts = boxToQuad(pts[0], pts[1]) } else if pts.count == 4 { pts = orderQuad(pts) } else { skipped += 1; continue }
                if area(pts) < 16 { skipped += 1; continue }
            case .line:
                if pts.count < 2 || length(pts) < 4 { skipped += 1; continue }
            case .poly:
                if pts.count < 3 || area(pts) < 16 { skipped += 1; continue }
            }
            func s(_ k: String, _ maxLen: Int) -> String? {
                guard let v = (r[k] as? String)?.trimmingCharacters(in: .whitespaces), !v.isEmpty else { return nil }
                return String(v.prefix(maxLen))
            }
            let conf = (r["confidence"] as? String).flatMap { ["low", "medium", "high"].contains($0) ? $0 : nil }
            out.append(FacadeElement(id: out.count + 1, type: t, points: pts, material: s("material", 40), confidence: conf, note: s("note", 120)))
        }
        return (out, skipped)
    }

    // MARK: meetkunde

    static func dist(_ a: [Double], _ b: [Double]) -> Double { hypot(a[0] - b[0], a[1] - b[1]) }

    public static func area(_ pts: [[Double]]) -> Double {
        var s = 0.0
        for i in 0..<pts.count { let a = pts[i], b = pts[(i + 1) % pts.count]; s += a[0] * b[1] - b[0] * a[1] }
        return abs(s) / 2
    }

    public static func length(_ pts: [[Double]]) -> Double {
        guard pts.count > 1 else { return 0 }
        return (1..<pts.count).reduce(0) { $0 + dist(pts[$1 - 1], pts[$1]) }
    }

    static func centroid(_ pts: [[Double]]) -> [Double] {
        [pts.reduce(0) { $0 + $1[0] } / Double(pts.count), pts.reduce(0) { $0 + $1[1] } / Double(pts.count)]
    }

    static func inside(_ p: [Double], _ pts: [[Double]]) -> Bool {
        var c = false
        var j = pts.count - 1
        for i in 0..<pts.count {
            let a = pts[i], b = pts[j]
            if (a[1] > p[1]) != (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0] { c.toggle() }
            j = i
        }
        return c
    }

    static func boxToQuad(_ a: [Double], _ b: [Double]) -> [[Double]] {
        let x1 = min(a[0], b[0]), x2 = max(a[0], b[0]), y1 = min(a[1], b[1]), y2 = max(a[1], b[1])
        return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    }

    static func orderQuad(_ pts: [[Double]]) -> [[Double]] {
        let c = centroid(pts)
        let s = pts.sorted { atan2($0[1] - c[1], $0[0] - c[0]) < atan2($1[1] - c[1], $1[0] - c[0]) }
        var k = 0
        for (i, p) in s.enumerated() where p[0] + p[1] < s[k][0] + s[k][1] { k = i }
        return Array(s[k...] + s[..<k])
    }

    // MARK: maat en hoeveelheden

    /// De horizontale uitersten van de gevelvlakken (metselwerk e.d.), als standaardplek voor de referentiepunten van de gevelbreedte.
    public static func defaultReference(_ els: [FacadeElement]) -> (left: Double, right: Double)? {
        let xs = els.filter { $0.type.isWall }.flatMap { $0.points.map { $0[0] } }
        guard let l = xs.min(), let r = xs.max(), r - l > 10 else { return nil }
        return (l, r)
    }

    /// Meters per pixel: de gevelbreedte uit de BAG gedeeld door de afstand tussen de twee referentiepunten (foto recht van voren).
    public static func metersPerPixel(facadeWidthM: Double, leftX: Double, rightX: Double) -> Double? {
        let d = abs(rightX - leftX)
        guard facadeWidthM > 0, d >= 2 else { return nil }
        return facadeWidthM / d
    }

    /// Hoeveelheden van één element. Zonder maat (`mpp == nil`) zijn alle maten onbekend; het aantal is altijd 1.
    public static func quantities(_ el: FacadeElement, mpp: Double?, all: [FacadeElement]) -> FacadeQuantities {
        var q = FacadeQuantities()
        guard let mpp else { return q }
        let m = el.points.map { [$0[0] * mpp, $0[1] * mpp] }
        switch el.type.kind {
        case .line: q.lengthM = length(m)
        case .quad:
            q.widthM = (dist(m[0], m[1]) + dist(m[3], m[2])) / 2
            q.heightM = (dist(m[0], m[3]) + dist(m[1], m[2])) / 2
            q.areaM2 = area(m)
        case .poly:
            let gross = area(m)
            let openings = all.filter { $0.type.isOpening && inside(centroid($0.points), el.points) }.reduce(0.0) { $0 + area($1.points.map { [$0[0] * mpp, $0[1] * mpp] }) }
            q.grossM2 = gross; q.openingsM2 = openings; q.netM2 = max(0, gross - openings)
        }
        return q
    }

    public static func round2(_ v: Double?) -> Double? { v.map { ($0 * 100).rounded(.toNearestOrAwayFromZero) / 100 } }

    /// Samenvatting van één gevel voor het plan.
    public struct Summary: Equatable {
        public var metselwerkNetM2: Double?
        public var gevelvlakNetM2: Double?
        public var raamkozijnen: Int
        public var deurkozijnen: Int
        public var kozijnOppervlakM2: Double?
        public var hwaM1: Double?
        public var dakgootM1: Double?
    }

    public static func summary(_ els: [FacadeElement], mpp: Double?) -> Summary {
        func sum(_ types: Set<FacadeElementType>, _ f: (FacadeQuantities) -> Double?) -> Double? {
            let sel = els.filter { types.contains($0.type) }
            guard !sel.isEmpty else { return 0 }
            var total = 0.0
            for e in sel { guard let v = f(quantities(e, mpp: mpp, all: els)) else { return nil }; total += v }
            return round2(total)
        }
        return Summary(metselwerkNetM2: sum([.metselwerk]) { $0.netM2 },
                       gevelvlakNetM2: sum([.metselwerk, .stucwerk, .gevelbekleding]) { $0.netM2 },
                       raamkozijnen: els.filter { $0.type == .kozijn_raam }.count,
                       deurkozijnen: els.filter { $0.type == .kozijn_deur }.count,
                       kozijnOppervlakM2: sum([.kozijn_raam, .kozijn_deur]) { $0.areaM2 },
                       hwaM1: sum([.hwa]) { $0.lengthM }, dakgootM1: sum([.dakgoot]) { $0.lengthM })
    }
}

// MARK: - Gevelzijden uit de BAG-omtrek

public struct FacadeSide: Codable, Equatable, Identifiable {
    public var id: Int
    public var lengthM: Double
    /// Windrichting waar de gevel naar kijkt (noord, noordoost, …).
    public var facing: String
}

public enum FootprintSides {
    /// Zet een BAG-ring (lon, lat) om naar meters rond het eerste punt.
    public static func meters(_ ring: [(Double, Double)]) -> [[Double]] {
        guard let first = ring.first else { return [] }
        let lat0 = first.1 * .pi / 180
        let kx = 111_320 * cos(lat0), ky = 110_540.0
        return ring.map { [($0.0 - first.0) * kx, ($0.1 - first.1) * ky] }
    }

    /// Voegt opeenvolgende, bijna rechte stukken van de omtrek samen tot gevelzijden (zoals footprintSides op de website). Ring in meters (x = oost, y = noord).
    public static func sides(_ ringM: [[Double]], tolDeg: Double = 10) -> [FacadeSide] {
        var pts = ringM
        if pts.count > 1, FacadePhoto.dist(pts[0], pts[pts.count - 1]) < 1e-6 { pts.removeLast() }
        let all = pts
        pts = all.enumerated().filter { i, p in FacadePhoto.dist(p, all[(i + 1) % all.count]) > 0.01 }.map(\.element)
        guard pts.count >= 3 else { return [] }
        let n = pts.count
        func dir(_ i: Int) -> Double { atan2(pts[(i + 1) % n][1] - pts[i][1], pts[(i + 1) % n][0] - pts[i][0]) }
        func turn(_ i: Int) -> Double { var d = abs(dir(i) - dir((i + n - 1) % n)) * 180 / .pi; if d > 180 { d = 360 - d }; return d }
        let corners = (0..<n).filter { turn($0) > tolDeg }
        guard corners.count >= 3 else { return [] }
        var signed = 0.0
        for i in 0..<n { signed += pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] }
        let names = ["noord", "noordoost", "oost", "zuidoost", "zuid", "zuidwest", "west", "noordwest"]
        return corners.enumerated().map { k, c in
            let a = pts[c], b = pts[corners[(k + 1) % corners.count]]
            let dx = b[0] - a[0], dy = b[1] - a[1]
            let nx = signed > 0 ? dy : -dy, ny = signed > 0 ? -dx : dx
            let az = (atan2(nx, ny) * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)
            return FacadeSide(id: k + 1, lengthM: hypot(dx, dy), facing: names[Int((az / 45).rounded(.toNearestOrAwayFromZero)) % 8])
        }
    }
}
