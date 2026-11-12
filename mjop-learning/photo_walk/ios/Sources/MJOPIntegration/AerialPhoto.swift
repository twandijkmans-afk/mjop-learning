import Foundation

/// Luchtfoto voor een projectkaart: adres -> coördinaat (PDOK Locatieserver) -> luchtfoto (PDOK WMS "Actueel_orthoHR").
/// Alleen openbare Nederlandse bronnen; het adres wordt alleen naar PDOK gestuurd (zoals de website ook doet).
///
/// Voorzichtig met matchen: een label zonder postcode en huisnummer (bijvoorbeeld "Voorbeeldgebouw") krijgt géén foto, en een antwoord
/// met een andere postcode dan gevraagd wordt genegeerd. Liever geen foto dan een foto van het verkeerde gebouw.
public enum AerialPhoto {
    public static let attribution = "Luchtfoto: Beeldmateriaal Nederland"

    /// Rijksdriehoekscoördinaten (EPSG:28992), in meters.
    public struct Point: Equatable {
        public var x: Double
        public var y: Double
        public init(x: Double, y: Double) { self.x = x; self.y = y }
    }

    /// Postcode (zonder spatie, hoofdletters) en het eerste huisnummer uit een adres als "Singelstraat 8, 1398BN Muiden".
    public struct Query: Equatable {
        public var postcode: String
        public var huisnummer: String
        /// Vrije zoektekst voor de Locatieserver, bijvoorbeeld "1398BN 8".
        public var text: String { postcode + " " + huisnummer }
    }

    /// Haalt postcode en huisnummer uit een adres. `nil` zonder allebei: dan wordt er niets gezocht.
    public static func query(from address: String) -> Query? {
        let s = address.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty, s.count <= 200 else { return nil }
        guard let pcRange = s.range(of: #"\b[1-9][0-9]{3} ?[A-Za-z]{2}\b"#, options: .regularExpression) else { return nil }
        let postcode = String(s[pcRange]).replacingOccurrences(of: " ", with: "").uppercased()
        // Het huisnummer staat vóór de postcode ("Zomerdijkstraat 14-1, 1079XB"); neem het eerste getal van 1 tot 5 cijfers.
        let before = String(s[s.startIndex..<pcRange.lowerBound])
        guard let nrRange = before.range(of: #"\b[0-9]{1,5}\b"#, options: .regularExpression) else { return nil }
        let huisnummer = String(before[nrRange])
        guard let n = Int(huisnummer), n > 0 else { return nil }
        return Query(postcode: postcode, huisnummer: String(n))
    }

    public static func geocodeURL(_ q: Query) -> URL? {
        guard var c = URLComponents(string: "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free") else { return nil }
        c.queryItems = [
            URLQueryItem(name: "q", value: q.text),
            URLQueryItem(name: "fq", value: "type:adres"),
            URLQueryItem(name: "rows", value: "1"),
            URLQueryItem(name: "fl", value: "centroide_rd,postcode,huisnummer"),
        ]
        return c.url
    }

    /// Leest het eerste resultaat. Alleen als de postcode klopt met de vraag, en alleen met een coördinaat binnen Nederland.
    public static func parseCentroid(_ data: Data, expecting q: Query) -> Point? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let resp = obj["response"] as? [String: Any],
              let docs = resp["docs"] as? [[String: Any]],
              let first = docs.first,
              let pc = first["postcode"] as? String,
              pc.replacingOccurrences(of: " ", with: "").uppercased() == q.postcode,
              let s = first["centroide_rd"] as? String else { return nil }
        return parsePoint(s)
    }

    /// "POINT(133171.93 482504.727)". Buiten het RD-bereik van Nederland wordt geweigerd.
    static func parsePoint(_ s: String) -> Point? {
        guard s.hasPrefix("POINT("), s.hasSuffix(")") else { return nil }
        let parts = s.dropFirst(6).dropLast().split(separator: " ")
        guard parts.count == 2, let x = Double(parts[0]), let y = Double(parts[1]) else { return nil }
        guard (0...300_000).contains(x), (289_000...629_000).contains(y) else { return nil }
        return Point(x: x, y: y)
    }

    /// Kaartbeeld van ongeveer `widthM` bij 0,6 × `widthM` meter rond het punt.
    public static func imageURL(center p: Point, widthM: Double = 120, pixelWidth: Int = 600) -> URL? {
        guard widthM >= 20, widthM <= 500, pixelWidth >= 100, pixelWidth <= 1200 else { return nil }
        let heightM = widthM * 0.6
        let pixelHeight = Int((Double(pixelWidth) * 0.6).rounded())
        func f(_ v: Double) -> String { String(format: "%.1f", v) }
        let bbox = [p.x - widthM / 2, p.y - heightM / 2, p.x + widthM / 2, p.y + heightM / 2].map(f).joined(separator: ",")
        guard var c = URLComponents(string: "https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0") else { return nil }
        c.queryItems = [
            URLQueryItem(name: "service", value: "WMS"),
            URLQueryItem(name: "version", value: "1.3.0"),
            URLQueryItem(name: "request", value: "GetMap"),
            URLQueryItem(name: "layers", value: "Actueel_orthoHR"),
            URLQueryItem(name: "styles", value: ""),
            URLQueryItem(name: "crs", value: "EPSG:28992"),
            URLQueryItem(name: "bbox", value: bbox),
            URLQueryItem(name: "width", value: String(pixelWidth)),
            URLQueryItem(name: "height", value: String(pixelHeight)),
            URLQueryItem(name: "format", value: "image/jpeg"),
        ]
        return c.url
    }
}
