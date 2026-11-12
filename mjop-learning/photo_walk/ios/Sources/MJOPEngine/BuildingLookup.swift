import Foundation

// Gebouw opzoeken bij een adres: het lezen van de antwoorden van de openbare diensten (PDOK-locatieserver, BAG via PDOK, 3D BAG van de TU Delft).
// Alleen het lezen staat hier (testbaar, alleen Foundation); het ophalen zelf doet de app. Zelfde werkwijze als de website (lookupBuilding, fetch3dbag).

public struct AddressSuggestion: Identifiable, Equatable {
    public var id: String
    public var naam: String
}

public struct AddressDetails: Equatable {
    public var naam: String
    public var straat: String?
    public var huisnummer: String?
    public var postcode: String?
    public var plaats: String?
    public var lon: Double
    public var lat: Double
}

public struct PandInfo: Equatable {
    public var identificatie: String
    public var bouwjaar: Int?
    public var verblijfsobjecten: Int?
    public var footprintM2: Double
    public var omtrekM: Double
    /// Ligt het adrespunt binnen dit pand (anders: het dichtstbijzijnde pand).
    public var bevatAdres: Bool
    /// Gevelzijden uit de omtrek (lengte en windrichting), voor de maat van de gevelscan.
    public var sides: [FacadeSide] = []
}

public struct ThreeDBAGInfo: Equatable {
    public var dakPlatM2: Double?
    public var dakSchuinM2: Double?
    public var buitenmuurM2: Double?
    public var hoogteM: Double?
    /// b3_kwaliteitsindicator: true = betrouwbaar, false = reconstructie controleren, nil = onbekend.
    public var kwaliteitGoed: Bool?
}

public enum BuildingLookup {
    public static let suggestBase = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/suggest"
    public static let lookupBase = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/lookup"
    public static let bagBase = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items"
    public static let threeDBase = "https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand."

    public static func suggestURL(_ q: String) -> URL? {
        var c = URLComponents(string: suggestBase)
        c?.queryItems = [URLQueryItem(name: "q", value: q), URLQueryItem(name: "fq", value: "type:adres"), URLQueryItem(name: "rows", value: "6")]
        return c?.url
    }

    public static func lookupURL(_ id: String) -> URL? {
        var c = URLComponents(string: lookupBase)
        c?.queryItems = [URLQueryItem(name: "id", value: id), URLQueryItem(name: "fl", value: "weergavenaam,centroide_ll,postcode,woonplaatsnaam,straatnaam,huis_nlt")]
        return c?.url
    }

    public static func bagURL(lon: Double, lat: Double) -> URL? {
        let d = 0.00018
        let bbox = [lon - d, lat - d, lon + d, lat + d].map { String($0) }.joined(separator: ",")
        return URL(string: "\(bagBase)?f=json&limit=20&bbox=\(bbox)")
    }

    public static func threeDURL(_ pandId: String) -> URL? { URL(string: threeDBase + pandId) }

    static func json(_ data: Data) -> [String: Any]? { (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] }

    public static func parseSuggest(_ data: Data) -> [AddressSuggestion] {
        let docs = (json(data)?["response"] as? [String: Any])?["docs"] as? [[String: Any]] ?? []
        return docs.compactMap { d in
            guard let id = d["id"] as? String, let n = d["weergavenaam"] as? String else { return nil }
            return AddressSuggestion(id: id, naam: n)
        }
    }

    public static func parseLookup(_ data: Data) -> AddressDetails? {
        guard let doc = ((json(data)?["response"] as? [String: Any])?["docs"] as? [[String: Any]])?.first,
              let naam = doc["weergavenaam"] as? String, let p = doc["centroide_ll"] as? String else { return nil }
        let nums = p.replacingOccurrences(of: "POINT(", with: "").replacingOccurrences(of: ")", with: "").split(separator: " ").compactMap { Double($0) }
        guard nums.count == 2 else { return nil }
        let straat = doc["straatnaam"] as? String, nr = doc["huis_nlt"] as? String
        return AddressDetails(naam: naam, straat: straat, huisnummer: nr, postcode: formatPostcode(doc["postcode"] as? String),
                              plaats: doc["woonplaatsnaam"] as? String, lon: nums[0], lat: nums[1])
    }

    /// "1398BN" → "1398 BN".
    public static func formatPostcode(_ p: String?) -> String? {
        guard let p = p?.replacingOccurrences(of: " ", with: ""), p.count == 6 else { return p }
        return String(p.prefix(4)) + " " + String(p.suffix(2))
    }

    /// Kiest het pand op het adres: eerst het pand waar het adrespunt in ligt, anders het dichtstbijzijnde (zoals de website).
    public static func pickPand(_ data: Data, lon: Double, lat: Double) -> PandInfo? {
        let feats = json(data)?["features"] as? [[String: Any]] ?? []
        var best: (PandInfo, Double)?
        for f in feats {
            guard let g = f["geometry"] as? [String: Any], let type = g["type"] as? String, let ring = outerRing(g["coordinates"], type: type), ring.count > 3 else { continue }
            let p = f["properties"] as? [String: Any] ?? [:]
            guard let id = p["identificatie"] as? String else { continue }
            let c = ring.reduce((0.0, 0.0)) { ($0.0 + $1.0 / Double(ring.count), $0.1 + $1.1 / Double(ring.count)) }
            let dist = hypot(c.0 - lon, c.1 - lat)
            let inside = pointInRing(ring, lon, lat)
            let units = (p["aantal_verblijfsobjecten"] as? Int).flatMap { $0 > 0 ? $0 : nil }
            let info = PandInfo(identificatie: id, bouwjaar: p["bouwjaar"] as? Int, verblijfsobjecten: units, footprintM2: ringArea(ring), omtrekM: ringPerimeter(ring), bevatAdres: inside,
                                sides: FootprintSides.sides(FootprintSides.meters(ring)))
            if let b = best {
                if (inside && !b.0.bevatAdres) || (inside == b.0.bevatAdres && dist < b.1) { best = (info, dist) }
            } else { best = (info, dist) }
        }
        return best?.0
    }

    static func outerRing(_ coords: Any?, type: String) -> [(Double, Double)]? {
        let raw: [[Double]]?
        if type == "Polygon" { raw = (coords as? [[[Double]]])?.first }
        else if type == "MultiPolygon" { raw = (coords as? [[[[Double]]]])?.first?.first }
        else { raw = nil }
        return raw?.compactMap { $0.count >= 2 ? ($0[0], $0[1]) : nil }
    }

    public static func ringArea(_ ring: [(Double, Double)]) -> Double {
        let lat0 = ring[0].1 * .pi / 180
        let kx = 111_320 * cos(lat0), ky = 110_540.0
        var a = 0.0
        for i in 0..<(ring.count - 1) {
            a += ring[i].0 * kx * ring[i + 1].1 * ky - ring[i + 1].0 * kx * ring[i].1 * ky
        }
        return abs(a / 2)
    }

    public static func ringPerimeter(_ ring: [(Double, Double)]) -> Double {
        let lat0 = ring[0].1 * .pi / 180
        let kx = 111_320 * cos(lat0), ky = 110_540.0
        var p = 0.0
        for i in 0..<(ring.count - 1) {
            let dx = (ring[i + 1].0 - ring[i].0) * kx, dy = (ring[i + 1].1 - ring[i].1) * ky
            p += (dx * dx + dy * dy).squareRoot()
        }
        return p
    }

    static func pointInRing(_ ring: [(Double, Double)], _ x: Double, _ y: Double) -> Bool {
        var c = false
        var j = ring.count - 2
        for i in 0..<(ring.count - 1) {
            let (xi, yi) = ring[i], (xj, yj) = ring[j]
            if (yi > y) != (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi { c.toggle() }
            j = i
        }
        return c
    }

    /// Leest de 3D BAG-attributen van één pand. Ontbrekend blijft nil; een aanwezige 0 blijft 0.
    public static func parse3DBAG(_ data: Data, pandId: String) -> ThreeDBAGInfo? {
        guard let co = (json(data)?["feature"] as? [String: Any])?["CityObjects"] as? [String: Any],
              let obj = co["NL.IMBAG.Pand.\(pandId)"] as? [String: Any] else { return nil }
        let a = obj["attributes"] as? [String: Any] ?? [:]
        func num(_ k: String) -> Double? { (a[k] as? NSNumber).map { $0.doubleValue }.flatMap { $0.isFinite ? $0 : nil } }
        var hoogte: Double?
        if let top = num("b3_h_dak_max"), let floor = num("b3_h_maaiveld") { hoogte = ((top - floor) * 10).rounded(.toNearestOrAwayFromZero) / 10 }
        return ThreeDBAGInfo(dakPlatM2: num("b3_opp_dak_plat"), dakSchuinM2: num("b3_opp_dak_schuin"), buitenmuurM2: num("b3_opp_buitenmuur"),
                             hoogteM: hoogte, kwaliteitGoed: a["b3_kwaliteitsindicator"] as? Bool)
    }

    /// Combineert BAG en 3D BAG tot de invoer van het rekenmodel.
    public static func buildingInput(pand: PandInfo, threeD: ThreeDBAGInfo?, units: Int? = nil) -> BuildingInput {
        let u = units ?? pand.verblijfsobjecten ?? 1
        return BuildingInput(bouwjaar: pand.bouwjaar, units: u, unitsBAG: pand.verblijfsobjecten ?? 1, footprintM2: pand.footprintM2, omtrekM: pand.omtrekM,
                             dakPlatM2: threeD?.dakPlatM2, dakSchuinM2: threeD?.dakSchuinM2, buitenmuurM2: threeD?.buitenmuurM2, hoogteM: threeD?.hoogteM)
    }
}
