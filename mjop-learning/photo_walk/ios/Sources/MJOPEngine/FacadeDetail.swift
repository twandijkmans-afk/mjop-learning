import Foundation

/// Tweede kijkronde voor kleine elementen (afvoeren, goten, boeiboorden, daktrim, waterslagen, lateien, plinten, roosters, lampen):
/// Claude kijkt op ingezoomde stroken van de foto op volle resolutie. Alleen op verzoek van de gebruiker.
/// De gevonden elementen worden teruggerekend naar de hele foto en alleen toegevoegd als ze er nog niet zijn.
public enum FacadeDetail {
    public static let promptVersion = "gevelfoto_detail_v0.1"
    public static let types: [FacadeElementType] = [.hwa, .dakgoot, .boeiboord, .daktrim, .waterslag, .latei, .plint, .rooster, .buitenlamp]

    /// Een uitsnede van de foto: rechthoek in pixels van de hele foto (x, y, breedte, hoogte) en een naam voor de prompt.
    public struct Crop: Equatable {
        public var name: String
        public var x: Double, y: Double, w: Double, h: Double
        public init(name: String, x: Double, y: Double, w: Double, h: Double) { self.name = name; self.x = x; self.y = y; self.w = w; self.h = h }
        /// Punt in de uitsnede (pixels van een beeld van `imageW` breed) terug naar de hele foto.
        public func mapBack(_ p: [Double], imageW: Double) -> [Double] {
            let k = w / imageW
            return [x + p[0] * k, y + p[1] * k]
        }
    }

    /// Drie stroken: de dakrand (boven) en de linker- en rechterzijde. Met een hoofdvlak rond de bovenrand daarvan.
    public static func crops(photoW W: Double, photoH H: Double, plane: FacadePlane?) -> [Crop] {
        var topY = 0.0, topH = H * 0.25
        if let p = plane, p.corners.count == 4 {
            let edge = min(p.corners[0][1], p.corners[1][1])
            topY = max(0, edge - H * 0.12)
            topH = min(H - topY, H * 0.25)
        }
        let side = W * 0.22
        return [Crop(name: "dakrand", x: 0, y: topY, w: W, h: topH),
                Crop(name: "links", x: 0, y: 0, w: side, h: H),
                Crop(name: "rechts", x: W - side, y: 0, w: side, h: H)]
    }

    public static func prompt(crops: [Crop], sizes: [(Int, Int)]) -> String {
        let list = types.map { t -> String in
            "- \(t.rawValue) (\(t.label)): " + (t.kind == .line ? "polyline along the centre line, 2 or more points" : "bounding box, exactly 2 points: top-left and bottom-right")
        }.joined(separator: "\n")
        let imgs = crops.enumerated().map { i, c in "Image \(i) (\(c.name)): \(sizes[i].0) x \(sizes[i].1) pixels" }.joined(separator: "\n")
        return """
        These \(crops.count) images are zoomed-in strips of one photo of a building facade in the Netherlands (the roof edge and the left and right sides), for a multi-year maintenance plan.
        \(imgs)

        Look closely for small and thin elements only:
        \(list)

        Guidelines:
        - Report each element in the image where it is visible, with coordinates in pixels of that image (origin top-left) and its index in "image".
        - A downpipe (hwa) usually runs from the gutter to the ground; follow it as far as you can be sure. Report a fascia (boeiboord) or gutter (dakgoot) along the whole visible roof edge.
        - Only elements that belong to the facade the photo is aimed at; leave out neighbouring buildings and side facades seen at an angle.
        - Report only elements you are sure exist. Do not estimate sizes.

        Return only a JSON object of this shape, with no other text:
        {"elements": [{"image": 0, "type": "<one of the type keys above>", "points": [{"x": 0, "y": 0}], "material": "", "confidence": "low|medium|high"}]}
        """
    }

    public static var schema: [String: Any] {
        let point: [String: Any] = ["type": "object", "additionalProperties": false, "required": ["x", "y"], "properties": ["x": ["type": "number"], "y": ["type": "number"]]]
        return ["type": "object", "additionalProperties": false, "required": ["elements"],
                "properties": ["elements": ["type": "array", "items": [
                    "type": "object", "additionalProperties": false, "required": ["image", "type", "points", "material", "confidence"],
                    "properties": ["image": ["type": "integer"], "type": ["type": "string", "enum": types.map(\.rawValue)],
                                   "points": ["type": "array", "items": point], "material": ["type": "string"],
                                   "confidence": ["type": "string", "enum": ["low", "medium", "high"]]]]]]]
    }

    public static func requestBody(jpegs: [String], crops: [Crop], sizes: [(Int, Int)], structured: Bool) -> [String: Any] {
        var outputConfig: [String: Any] = ["effort": "high"]
        if structured { outputConfig["format"] = ["type": "json_schema", "schema": schema] }
        var content: [[String: Any]] = jpegs.map { ["type": "image", "source": ["type": "base64", "media_type": "image/jpeg", "data": $0]] }
        content.append(["type": "text", "text": prompt(crops: crops, sizes: sizes)])
        return ["model": FacadePhoto.model, "max_tokens": 16000, "output_config": outputConfig, "messages": [["role": "user", "content": content]]]
    }

    /// Leest het antwoord en rekent alles terug naar pixels van de hele foto. Ongeldige elementen worden overgeslagen.
    public static func parse(_ data: Data, crops: [Crop], sizes: [(Int, Int)], photoW W: Double, photoH H: Double) throws -> [FacadePhotoElement] {
        guard let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { throw FacadeError.unreadable }
        if (o["stop_reason"] as? String) == "refusal" { throw FacadeError.refused }
        if (o["stop_reason"] as? String) == "max_tokens" { throw FacadeError.truncated }
        let text = ((o["content"] as? [[String: Any]]) ?? []).filter { ($0["type"] as? String) == "text" }.compactMap { $0["text"] as? String }.joined()
        var obj = (try? JSONSerialization.jsonObject(with: Data(text.utf8))) as? [String: Any]
        if obj == nil, let s = text.firstIndex(of: "{"), let e = text.lastIndex(of: "}"), s < e {
            obj = (try? JSONSerialization.jsonObject(with: Data(text[s...e].utf8))) as? [String: Any]
        }
        guard let raw = obj?["elements"] as? [[String: Any]] else { throw FacadeError.unreadable }
        var out: [[String: Any]] = []
        for r in raw {
            guard let i = (r["image"] as? NSNumber)?.intValue, crops.indices.contains(i), let t = r["type"] as? String,
                  let tt = FacadeElementType(rawValue: t), types.contains(tt), let pts = r["points"] as? [[String: Any]] else { continue }
            var mapped: [[String: Any]] = []
            for p in pts {
                guard let x = (p["x"] as? NSNumber)?.doubleValue, let y = (p["y"] as? NSNumber)?.doubleValue else { continue }
                let q = crops[i].mapBack([x, y], imageW: Double(sizes[i].0))
                mapped.append(["x": q[0], "y": q[1]])
            }
            var e = r; e["points"] = mapped
            out.append(e)
        }
        var els = FacadePhoto.parseElements(out, width: W, height: H, scale: 1).elements
        for k in els.indices { els[k].detailPass = true; els[k].note = "tweede ronde" }
        return els
    }

    /// Voegt alleen elementen toe die er nog niet zijn: een lijn van dezelfde soort met het midden dichtbij en ongeveer evenwijdig,
    /// of een kader van dezelfde soort dat er grotendeels overheen ligt, telt als "al gevonden". Nieuwe id's, nooit een id die al bezet is.
    public static func merge(existing: [FacadePhotoElement], found: [FacadePhotoElement], photoW W: Double, takenIds: Set<Int> = []) -> [FacadePhotoElement] {
        var all = existing
        var nextId = ((existing.map(\.id) + Array(takenIds)).max() ?? 0) + 1
        func dir(_ e: FacadePhotoElement) -> Double {
            guard let a = e.points.first, let b = e.points.last else { return 0 }
            return atan2(b[1] - a[1], b[0] - a[0])
        }
        for f in found {
            let dup = all.contains { e in
                guard e.type == f.type else { return false }
                if f.type.kind == .line {
                    let d = FacadePhoto.dist(FacadePhoto.centroid(e.points), FacadePhoto.centroid(f.points))
                    var a = abs(dir(e) - dir(f)).truncatingRemainder(dividingBy: .pi)
                    if a > .pi / 2 { a = .pi - a }
                    return d < 0.03 * W && a < 0.26
                }
                return FacadePhoto.overlap(e.points, f.points) > 0.5
            }
            if dup { continue }
            var n = f; n.id = nextId; nextId += 1
            all.append(n)
        }
        return all
    }
}
