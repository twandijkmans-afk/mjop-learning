import Foundation

/// Dakscan van boven: een PDOK-luchtfoto (orthofoto, noorden boven) waarop Claude dakvlakken, dakkapellen en dingen op het dak
/// aanwijst (alleen pixels en labels). De schaal is exact bekend uit de kaartuitsnede; de echte helling van schuine vlakken komt
/// uit de 3D BAG. Alles is een voorstel dat de gebruiker bevestigt.
public enum RoofPhoto {
    public static let promptVersion = "dakfoto_v0.1"

    /// Wat op het dak herkend wordt.
    public static let types: [FacadeElementType] = [.dakvlak_plat, .dakvlak_schuin, .dakkapel, .schoorsteen, .lichtkoepel, .zonnepaneel,
                                                     .dakluik, .dakinstallatie, .dakgoot, .daktrim, .boeiboord]
    public static let defectTypes: [FacadeDefectType] = [.plasvorming, .veroudering_dakbedekking]

    /// Relatieve bandbreedte van maten op de luchtfoto: de orthofoto kan bij hoge gebouwen iets scheef staan (±3%).
    public static let relativeBand = 0.03
    /// Extra onzekerheid op schuine vlakken door de verdeling van het 3D BAG-oppervlak naar verhouding (±5%).
    public static let slopeBand = 0.05
    /// Dakoverstek: een element hoort bij het gebouw als zijn midden binnen de BAG-omtrek ligt of hooguit zoveel meter erbuiten.
    public static let overhangM = 0.6
    /// Een schuin dak is van boven gezien 1,0 tot 2,5 keer kleiner dan echt (0° tot ongeveer 66° helling). Daarbuiten klopt er iets niet.
    public static let slopeRange = 1.0...2.5
    /// Boven dit verschil tussen het platte dak op de foto en in de 3D BAG volgt een melding (niet automatisch opgelost).
    public static let flatTolerance = 0.15

    /// Echte meters per pixel van een uitsnede in Web Mercator: mercatormeters worden kleiner met de cosinus van de breedtegraad.
    public static func metersPerPixel(mercatorWidth: Double, pixelWidth: Double, latitude: Double) -> Double? {
        guard mercatorWidth > 0, pixelWidth > 0 else { return nil }
        return mercatorWidth / pixelWidth * cos(latitude * .pi / 180)
    }

    public static func prompt(width W: Int, height H: Int, outline: [[Double]], metersPerPixel mpp: Double) -> String {
        let pts = outline.map { String(format: "(%.0f, %.0f)", $0[0], $0[1]) }.joined(separator: ", ")
        let list = types.map { t -> String in
            let g: String
            switch t.kind {
            case .quad: g = "bounding box, exactly 2 points: top-left and bottom-right"
            case .line: g = "polyline along the element, 2 or more points"
            case .poly: g = "polygon outlining the surface as seen from above, 3 or more points in order"
            }
            return "- \(t.rawValue) (\(t.label)): \(g)"
        }.joined(separator: "\n")
        return """
        This is an aerial orthophoto (straight down, north at the top) of a building in the Netherlands, for a multi-year maintenance plan (MJOP). The image is \(W) x \(H) pixels; one pixel is about \(String(format: "%.2f", mpp)) m.

        The building is outlined in the land registry by this polygon (pixels, origin top-left, x right, y down): \(pts).
        Report only roof elements of this building. Leave out neighbouring roofs, even when they touch the outline, and anything on the ground.

        Element types and the geometry to return for each:
        \(list)

        Guidelines:
        - dakvlak_plat: each continuous flat roof surface. dakvlak_schuin: each sloped roof face separately (split at ridges, hips and valleys). Follow the edges as seen from above, including the eaves overhang.
        - dakkapel (dormer): a box around the dormer's flat roof as seen from above. Do not include the dormer in the sloped roof face around it.
        - schoorsteen, lichtkoepel (skylight or roof window), zonnepaneel (one box per continuous field of solar panels), dakluik (roof hatch), dakinstallatie (ventilation unit, air conditioning, antenna mount): a box around each.
        - dakgoot (gutter), daktrim (roof edge trim on a flat roof), boeiboord (fascia along the eaves): follow the line along the roof edge.
        - Report only elements you are sure exist. When part of an element is hidden under a tree, set "hidden_fraction" (0 = fully visible) and box it as far as its visible edges show it.
        - Defects, only when clearly visible: plasvorming (standing water or water stains on a flat roof) and veroudering_dakbedekking (discoloured or weathered bitumen, loose or shifted tiles, bare patches). One point at the defect and a few Dutch words in "note". Never a condition score.
        - "material": one short Dutch word when clearly recognisable (bitumen, epdm, grind, pannen, leien, zink, glas), otherwise an empty string. "confidence": how sure you are. "note": a few Dutch words when something limits the result, otherwise empty.
        - Use plane 1 for every element, hidden_fraction 0 when fully visible, panes and opening_parts 0.

        Do not estimate sizes, slopes, condition scores or costs: measurements are computed separately from your coordinates.

        Return only a JSON object of this shape, with no other text:
        {"planes": [], "elements": [{"type": "<one of the type keys above>", "points": [{"x": 0, "y": 0}], "material": "", "confidence": "low|medium|high", "note": "", "plane": 1, "hidden_fraction": 0, "panes": 0, "opening_parts": 0}],
         "defects": [{"type": "plasvorming|veroudering_dakbedekking", "point": {"x": 0, "y": 0}, "note": ""}]}
        """
    }

    /// JSON-schema voor afgedwongen uitvoer: hetzelfde als bij de gevel, maar met alleen de dak-soorten en dakgebreken.
    public static var schema: [String: Any] {
        var s = FacadePhoto.schema
        guard var props = s["properties"] as? [String: Any],
              var els = props["elements"] as? [String: Any], var eItem = els["items"] as? [String: Any], var eProps = eItem["properties"] as? [String: Any],
              var defs = props["defects"] as? [String: Any], var dItem = defs["items"] as? [String: Any], var dProps = dItem["properties"] as? [String: Any] else { return s }
        eProps["type"] = ["type": "string", "enum": types.map(\.rawValue)]
        dProps["type"] = ["type": "string", "enum": defectTypes.map(\.rawValue)]
        eItem["properties"] = eProps; els["items"] = eItem; props["elements"] = els
        dItem["properties"] = dProps; defs["items"] = dItem; props["defects"] = defs
        s["properties"] = props
        return s
    }

    public static func requestBody(jpegBase64: String, width W: Int, height H: Int, outline: [[Double]], metersPerPixel mpp: Double, structured: Bool) -> [String: Any] {
        var outputConfig: [String: Any] = ["effort": "high"]
        if structured { outputConfig["format"] = ["type": "json_schema", "schema": schema] }
        return ["model": FacadePhoto.model, "max_tokens": 32000, "output_config": outputConfig,
                "messages": [["role": "user", "content": [
                    ["type": "image", "source": ["type": "base64", "media_type": "image/jpeg", "data": jpegBase64]],
                    ["type": "text", "text": prompt(width: W, height: H, outline: outline, metersPerPixel: mpp)],
                ]]]]
    }

    /// Leest het antwoord: alleen dak-soorten en dakgebreken, alleen wat bij dit gebouw hoort (midden binnen de omtrek plus het overstek).
    public static func parse(_ data: Data, width W: Double, height H: Double, outline: [[Double]], metersPerPixel mpp: Double) throws -> (recognition: FacadeRecognition, outside: Int) {
        var r = try FacadePhoto.parseRecognition(data, width: W, height: H)
        let allowed = Set(types)
        let before = r.elements.count
        r.elements = r.elements.filter { allowed.contains($0.type) }
        r.skipped += before - r.elements.count
        r.planes = []
        for i in r.elements.indices { r.elements[i].plane = nil }
        let c = clip(r.elements, outline: outline, marginPx: overhangM / mpp)
        r.elements = c.kept
        r.defects = r.defects.filter { defectTypes.contains($0.type) && (outline.count < 3 || FacadePhoto.inside($0.point, outline) || distance($0.point, to: outline) <= overhangM / mpp) }
        return (r, c.outside)
    }

    /// Houdt de elementen waarvan het midden binnen de omtrek ligt of hooguit `marginPx` erbuiten.
    public static func clip(_ els: [FacadePhotoElement], outline: [[Double]], marginPx: Double) -> (kept: [FacadePhotoElement], outside: Int) {
        guard outline.count >= 3 else { return (els, 0) }
        var kept: [FacadePhotoElement] = []
        var outside = 0
        for e in els {
            let c = FacadePhoto.centroid(e.points)
            if FacadePhoto.inside(c, outline) || distance(c, to: outline) <= marginPx { kept.append(e) } else { outside += 1 }
        }
        return (kept, outside)
    }

    /// Kortste afstand van een punt tot de rand van een veelhoek.
    static func distance(_ p: [Double], to poly: [[Double]]) -> Double {
        var best = Double.infinity
        for i in 0..<poly.count {
            let a = poly[i], b = poly[(i + 1) % poly.count]
            let dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy
            let t = l2 == 0 ? 0 : max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
            best = min(best, hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)))
        }
        return best
    }

    /// Factor van "oppervlak van boven" naar "echt oppervlak" voor de schuine vlakken: 3D BAG gedeeld door de som van boven.
    /// Nil als de 3D BAG het niet weet of de verhouding niet kan kloppen; dan blijft het schuine oppervlak onbekend.
    public static func slopeFactor(projectedSchuinM2: Double, dakSchuin3DBAG: Double?) -> Double? {
        guard projectedSchuinM2 > 0, let bag = dakSchuin3DBAG, bag > 0 else { return nil }
        let f = bag / projectedSchuinM2
        return slopeRange.contains(f) ? f : nil
    }

    /// Past de hellingfactor toe op de schuine dakvlakken (oppervlak en ±). Zonder factor is hun oppervlak onbekend.
    public static func applySlope(_ ms: [ElementMeasure], factor: Double?) -> [ElementMeasure] {
        ms.map { m in
            guard m.type == .dakvlak_schuin else { return m }
            var o = m
            guard let f = factor, let a = m.areaM2 else { o.areaM2 = nil; o.band = nil; return o }
            let area = a * f
            o.areaM2 = FacadePhoto.round2(area)
            o.band = FacadePhoto.round2((m.band ?? 0) * f + area * slopeBand)
            return o
        }
    }

    /// Vergelijking van het platte dak (plat dakvlak + dakkapellen, gemeten van boven) met de 3D BAG.
    public struct FlatCheck: Equatable {
        public var photoM2: Double
        public var bagM2: Double
        public var differs: Bool
        public init(photoM2: Double, bagM2: Double, differs: Bool) { self.photoM2 = photoM2; self.bagM2 = bagM2; self.differs = differs }
    }
    public static func flatCheck(photoFlatM2: Double?, bag: Double?) -> FlatCheck? {
        guard let p = photoFlatM2, let b = bag, max(p, b) > 0 else { return nil }
        let diff = abs(p - b) / max(p, b)
        return FlatCheck(photoM2: FacadePhoto.round2(p) ?? p, bagM2: b, differs: diff > flatTolerance)
    }
}

/// Advies voor een dakinspectie met vaste regels. De AI geeft alleen hints; alleen door de gebruiker bevestigde gebreken tellen.
public struct InspectionAdvice: Equatable {
    public var year: Int
    public var reasons: [String]
    public init(year: Int, reasons: [String]) { self.year = year; self.reasons = reasons }
}

public enum RoofInspection {
    /// Dakbedekking in het plan: postsleutel, laatste vervanging (nil = onbekend) en levensduur in jaren.
    public struct Covering: Equatable {
        public var key: String
        public var naam: String
        public var lastDone: Int?
        public var cycle: Int
        public init(key: String, naam: String, lastDone: Int?, cycle: Int) { self.key = key; self.naam = naam; self.lastDone = lastDone; self.cycle = cycle }
    }

    /// Het vroegste jaar volgens de regels, met alle redenen; nil als geen regel iets zegt (dan blijft de gewone inspectiecyclus).
    /// - Bevestigd gebrek ernstig of serieus: dit jaar. Gering (of nog geen ernst): volgend jaar.
    /// - Dakbedekking ≥ 80% van de levensduur: dit jaar; ≥ 60%: binnen 2 jaar.
    public static func advice(confirmed: [FacadeDefect], coverings: [Covering], year: Int) -> InspectionAdvice? {
        var candidates: [(Int, String)] = []
        for d in confirmed where d.isConfirmed {
            switch d.ernst {
            case .ernstig, .serieus: candidates.append((year, "\(d.type.label) bevestigd (\(d.ernst!.label.lowercased()))"))
            case .gering, .none: candidates.append((year + 1, "\(d.type.label) bevestigd" + (d.ernst == nil ? "" : " (gering)")))
            }
        }
        for c in coverings {
            guard let last = c.lastDone, c.cycle > 0, last <= year else { continue }
            let share = Double(year - last) / Double(c.cycle)
            let pct = Int((share * 100).rounded())
            if share >= 0.8 { candidates.append((year, "\(c.naam) is \(year - last) jaar oud (\(pct)% van \(c.cycle) jaar levensduur)")) }
            else if share >= 0.6 { candidates.append((year + 2, "\(c.naam) is \(year - last) jaar oud (\(pct)% van \(c.cycle) jaar levensduur)")) }
        }
        guard let first = candidates.map(\.0).min() else { return nil }
        return InspectionAdvice(year: first, reasons: candidates.sorted { $0.0 < $1.0 }.map(\.1))
    }
}
