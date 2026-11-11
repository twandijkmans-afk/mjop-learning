import Foundation

/// Contract `mjop_gevel_inventory_v1`: gevelinventaris van Gevelscanner 2.0 (per gevel en per object, met herkomst, onzekerheid en bewijs).
/// Schema: schemas/mjop_gevel_inventory_v1.schema.json. Staat NAAST `mjop_scan_proposal_v2` (dat ongewijzigd blijft): een oudere website kent
/// dit contract niet en vraagt het nooit op.
///
/// Het contract is een gevalideerde JSON-boom (geen tientallen Codable-structs): de inhoud wordt in `Gevelscan.InventoryContractBuilder`
/// opgebouwd en hier — net als aan de websitekant en in het schema — streng gecontroleerd. Regels die altijd gelden:
/// * altijd een VOORSTEL: `booking_allowed = false`, `confirmation.status = PROPOSED`; geen prijzen of kengetallen (die blijven bij het MJOP);
/// * onbekend = `null` (nooit 0), met uitkomst `NIET_VAST_TE_STELLEN`;
/// * aantal kozijnen, kozijnoppervlak, draaiende delen, vaste delen en glasoppervlak zijn aparte hoeveelheden;
/// * geen aantal zolang dubbeltelling niet is uitgesloten;
/// * glasoppervlak is nooit een directe LiDAR-meting; er is geen NEN 2767-conditiescore;
/// * zolang de pijplijn niet gevalideerd is, is niets `BETROUWBAAR_VASTGESTELD` behalve wat de gebruiker zelf heeft ingevoerd.
public struct GevelInventoryV1: Equatable {
    public static let contractID = "mjop_gevel_inventory_v1"
    public static let outcomes = ["BETROUWBAAR_VASTGESTELD", "VOORLOPIG_VASTGESTELD", "NIET_VAST_TE_STELLEN"]
    public static let origins = ["LIDAR_PLANE_MEASUREMENT", "REFERENCE_DISTANCE", "DERIVED_SEGMENTATION_ON_MEASURED_PLANE", "DERIVED_CALCULATION", "COUNTED_FROM_ASSOCIATION",
                                 "MODEL_CLASSIFICATION", "USER_INPUT", "NONE"]
    public static let totalKeys = ["frame_count", "frame_area_gross", "operable_parts", "fixed_parts", "glass_area", "door_count"]
    public static let totalUnits = ["frame_count": "st", "frame_area_gross": "m2", "operable_parts": "st", "fixed_parts": "st", "glass_area": "m2", "door_count": "st"]

    public private(set) var body: JSONValue

    public var inventoryId: String { body["inventory_id"]?.string ?? "" }
    public var roundId: String { body["round_id"]?.string ?? "" }
    public var revision: Int { body["revision"]?.int ?? 0 }
    public var planRef: String { body["project"]?["plan_ref"]?.string ?? "" }

    public enum ContractError: Error, Equatable { case invalid([String]) }

    /// Weigert alles wat niet aan het contract voldoet (geen stil half-begrijpen).
    public init(validating body: JSONValue) throws {
        let e = Self.validate(body)
        if !e.isEmpty { throw ContractError.invalid(e) }
        self.body = body
    }

    public func jsonObject() -> [String: Any]? { body.foundationValue as? [String: Any] }
    public func encoded() throws -> Data {
        let e = JSONEncoder(); e.outputFormatting = [.sortedKeys, .prettyPrinted]
        return try e.encode(body)
    }
    public static func decode(_ data: Data) throws -> GevelInventoryV1 {
        guard let v = JSONValue.decode(data) else { throw ContractError.invalid(["geen JSON"]) }
        return try GevelInventoryV1(validating: v)
    }

    // MARK: validatie (zelfde regels als src/gevel-inventory.js van de website en het JSON-schema)

    static func match(_ s: String?, _ pattern: String) -> Bool { s.map { $0.range(of: pattern, options: .regularExpression) != nil } ?? false }

    static func quantityErrors(_ q: JSONValue?, _ path: String, unit: String?) -> [String] {
        guard let o = q?.object else { return ["\(path): geen hoeveelheid"] }
        var e: [String] = []
        let allowed: Set<String> = ["value", "unit", "sigma", "origin", "outcome", "missing", "partial"]
        if !Set(o.keys).isSubset(of: allowed) || !allowed.isSubset(of: Set(o.keys)) { e.append("\(path): velden") }
        let value = o["value"] ?? .null, partial = o["partial"] ?? .null, sigma = o["sigma"] ?? .null
        for (k, v) in [("value", value), ("partial", partial), ("sigma", sigma)] {
            if !v.isNull, !(v.double.map { $0.isFinite && $0 >= 0 } ?? false) { e.append("\(path).\(k): geen getal >= 0") }
        }
        let u = o["unit"]?.string ?? ""
        if !["st", "m", "m2"].contains(u) || (unit != nil && u != unit) { e.append("\(path): eenheid") }
        let origin = o["origin"]?.string ?? "", outcome = o["outcome"]?.string ?? ""
        if !origins.contains(origin) { e.append("\(path): herkomst") }
        if !outcomes.contains(outcome) { e.append("\(path): uitkomst") }
        if !(o["missing"]?.array?.allSatisfy { match($0.string, "^[A-Z0-9_]{1,60}$") } ?? false) || (o["missing"]?.array?.count ?? 0) > 40 { e.append("\(path): missing") }
        if value.isNull && outcome != "NIET_VAST_TE_STELLEN" { e.append("\(path): onbekende waarde moet NIET_VAST_TE_STELLEN zijn") }
        if !value.isNull && outcome == "NIET_VAST_TE_STELLEN" { e.append("\(path): waarde bij NIET_VAST_TE_STELLEN") }
        if !value.isNull && !partial.isNull { e.append("\(path): deelwaarde alleen bij een onbekende waarde") }
        if !value.isNull && origin == "NONE" { e.append("\(path): waarde zonder herkomst") }
        if u == "st", let v = value.double, v != v.rounded() { e.append("\(path): aantal is geen geheel getal") }
        return e
    }

    public static func validate(_ v: JSONValue) -> [String] {
        guard let d = v.object else { return ["geen object"] }
        var e: [String] = []
        let top: Set<String> = ["contract", "inventory_id", "round_id", "revision", "created_at", "project", "element_key", "versions", "recognition", "validation", "facades",
                                "building_totals", "photos", "confirmation", "booking_allowed"]
        if Set(d.keys) != top { e.append("onbekende of ontbrekende velden") }
        if d["contract"]?.string != contractID { e.append("contract/versie") }
        if !match(d["inventory_id"]?.string, "^[A-Za-z0-9_.-]{8,80}$") { e.append("inventory_id") }
        if !match(d["round_id"]?.string, "^[A-Za-z0-9_.-]{8,80}$") { e.append("round_id") }
        if (d["revision"]?.int ?? 0) < 1 { e.append("revision") }
        if !match(d["created_at"]?.string, "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?Z$") { e.append("created_at") }
        let p = d["project"]
        if !match(p?["plan_ref"]?.string, "^[A-Za-z0-9_-]{8,80}$") || !((p?["building_id"]?.string?.count).map { (1...200).contains($0) } ?? false)
            || !(p?["bag_pand_id"]?.isNull ?? false || match(p?["bag_pand_id"]?.string, "^[0-9]{16}$"))
            || !(p?["mjop_plan_id"]?.isNull ?? false || (p?["mjop_plan_id"]?.string?.count).map { (1...80).contains($0) } ?? false) { e.append("project") }
        if !(d["element_key"]?.isNull ?? false || match(d["element_key"]?.string, "^[a-z0-9-]{1,80}$")) { e.append("element_key") }
        if d["booking_allowed"]?.bool != false { e.append("booking_allowed moet false zijn") }
        if d["confirmation"]?["status"]?.string != "PROPOSED" { e.append("confirmation (altijd PROPOSED)") }
        if d["versions"]?["pipeline"]?.string == nil || d["versions"]?["thresholds_status"]?.string == nil { e.append("versions") }
        if d["recognition"]?["detectors"]?.array == nil || d["recognition"]?["not_recognizable"]?.array == nil { e.append("recognition") }
        let val = d["validation"]
        let geoV = val?["geometry_field_validated"]?.bool, detV = val?["detector_validated"]?.bool, auto = val?["auto_processing_allowed"]?.bool
        if geoV == nil || detV == nil || auto == nil || val?["reasons"]?.array == nil { e.append("validation") }
        let validated = geoV == true && detV == true
        if auto == true && !validated { e.append("automatische verwerking zonder gevalideerde pijplijn") }
        guard let facades = d["facades"]?.array, facades.count <= 40 else { return e + ["facades"] }
        guard let photos = d["photos"]?.array, photos.count <= 2000 else { return e + ["photos"] }
        for (i, ph) in photos.enumerated() {
            if !match(ph["photo_id"]?.string, "^.{1,80}$") || ph["facade_id"]?.string == nil || !["LIDAR_SCENE_DEPTH", "NONE"].contains(ph["depth_source"]?.string ?? "") { e.append("photos[\(i)]") }
        }
        func totalsErrors(_ t: JSONValue?, _ path: String) -> [String] {
            guard let o = t?.object, Set(o.keys) == Set(totalKeys) else { return ["\(path): totalen"] }
            return totalKeys.flatMap { quantityErrors(o[$0], "\(path).\($0)", unit: totalUnits[$0]) }
        }
        /// Zonder gevalideerde pijplijn mag alleen gebruikersinvoer BETROUWBAAR_VASTGESTELD zijn.
        func reliableWithoutValidation(_ q: JSONValue?) -> Bool {
            !validated && q?["outcome"]?.string == "BETROUWBAAR_VASTGESTELD" && q?["origin"]?.string != "USER_INPUT"
        }
        e += totalsErrors(d["building_totals"], "building_totals")
        if totalKeys.contains(where: { reliableWithoutValidation(d["building_totals"]?[$0]) }) { e.append("building_totals: betrouwbaar zonder validatie") }
        var ids = Set<String>()
        for (i, f) in facades.enumerated() {
            let path = "facades[\(i)]"
            if !((f["facade_id"]?.string?.count).map { (1...120).contains($0) } ?? false) { e.append("\(path).facade_id") }
            if !outcomes.contains(f["completeness"]?.string ?? "") { e.append("\(path).completeness") }
            if !validated && f["completeness"]?.string == "BETROUWBAAR_VASTGESTELD" { e.append("\(path): volledig zonder validatie") }
            if f["coverage"]?["determinable"]?.bool == nil || f["capture_requests"]?.array == nil || f["photo_ids"]?.array == nil { e.append("\(path): dekking/verzoeken/foto's") }
            if !((f["capture_requests"]?.array ?? []).allSatisfy { r in
                match(r["kind"]?.string, "^[A-Z_]{1,40}$") && ((r["text_nl"]?.string?.count).map { $0 <= 300 } ?? false) && match(r["reason"]?.string, "^[A-Z0-9_]{0,60}$")
            }) || (f["capture_requests"]?.array?.count ?? 0) > 500 { e.append("\(path): vraag om extra foto's") }
            e += totalsErrors(f["totals"], "\(path).totals")
            if totalKeys.contains(where: { reliableWithoutValidation(f["totals"]?[$0]) }) { e.append("\(path).totals: betrouwbaar zonder validatie") }
            guard let objects = f["objects"]?.array, objects.count <= 500 else { e.append("\(path).objects"); continue }
            var identityOpen = false, areaMissing = false
            for (k, o) in objects.enumerated() {
                let op = "\(path).objects[\(k)]"
                guard let oid = o["object_id"]?.string, match(oid, "^[A-Za-z0-9_.-]{4,80}$") else { e.append("\(op).object_id"); continue }
                if !ids.insert(oid).inserted { e.append("\(op): object_id komt vaker voor") }
                if !outcomes.contains(o["outcome"]?.string ?? "") { e.append("\(op).outcome") }
                if !["KOZIJN", "RAAM", "DEUR"].contains(o["element_class"]?.string ?? "") { e.append("\(op).element_class") }
                if (o["panes"]?.array?.count ?? 0) > 60 { e.append("\(op).panes") }
                if !validated && o["outcome"]?.string == "BETROUWBAAR_VASTGESTELD" { e.append("\(op): betrouwbaar zonder validatie") }
                let identity = o["identity"]?.string ?? ""
                if !["RESOLVED", "RESOLVED_BY_USER", "UNCERTAIN", "UNCHECKED"].contains(identity) { e.append("\(op).identity") }
                if identity == "UNCERTAIN" || identity == "UNCHECKED" { identityOpen = true }
                if !["USER_CONFIRMED", "AUTO_CORROBORATED", "AUTO_UNCONFIRMED"].contains(o["contour_evidence"]?.string ?? "") { e.append("\(op).contour_evidence") }
                if o["count"]?.int != 1 { e.append("\(op).count") }
                for (key, unit) in [("width", "m"), ("height", "m"), ("area", "m2"), ("glass_area", "m2"), ("sections", "st"), ("operable_parts", "st"), ("fixed_parts", "st")] {
                    e += quantityErrors(o[key], "\(op).\(key)", unit: unit)
                    if reliableWithoutValidation(o[key]) { e.append("\(op).\(key): betrouwbaar zonder validatie") }
                }
                let area = o["area"]?["value"]?.double
                if area == nil { areaMissing = true }
                if area != nil && (o["width"]?["value"]?.double == nil || o["height"]?["value"]?.double == nil) { e.append("\(op): oppervlak zonder breedte en hoogte") }
                if let g = o["glass_area"]?["value"]?.double {
                    if let a = area, g > a + 1e-9 { e.append("\(op): glas groter dan het kozijn") }
                    if area == nil { e.append("\(op): glasoppervlak zonder kozijnmaat") }
                    if ["LIDAR_PLANE_MEASUREMENT", "REFERENCE_DISTANCE"].contains(o["glass_area"]?["origin"]?.string ?? "") { e.append("\(op): glasoppervlak is geen directe meting") }
                }
                if !(o["nen2767_condition_score"]?.isNull ?? false) { e.append("\(op): geen NEN 2767-score in dit contract") }
                guard let cond = o["condition"]?.array, o["photo_ids"]?.array != nil, o["panes"]?.array != nil else { e.append("\(op): conditie/foto's/glasvlakken"); continue }
                for c in cond {
                    let kind = c["kind"]?.string ?? ""
                    if !["ZICHTBAAR_GEBREK", "MOGELIJKE_INDICATIE", "NIET_BEOORDEELBAAR"].contains(kind) { e.append("\(op): conditiesoort") }
                    if kind != "NIET_BEOORDEELBAAR" && (c["photo_id"]?.string == nil || c["region_px"]?.array == nil || c["category"]?.string == nil) { e.append("\(op): gebrek zonder bronfoto, plek of categorie") }
                    if kind == "ZICHTBAAR_GEBREK" && c["detector"]?["validated"]?.bool != true { e.append("\(op): zichtbaar gebrek vraagt een gevalideerde herkenner") }
                }
            }
            // geen aantal zolang dubbeltelling niet is uitgesloten; geen totaaloppervlak met onbemeten kozijnen
            if identityOpen {
                for key in totalKeys where !(f["totals"]?[key]?["value"]?.isNull ?? true) || !(f["totals"]?[key]?["partial"]?.isNull ?? true) { e.append("\(path).totals.\(key): waarde ondanks mogelijke dubbeltelling") }
            }
            if areaMissing && !(f["totals"]?["frame_area_gross"]?["value"]?.isNull ?? true) { e.append("\(path).totals.frame_area_gross: oppervlak ondanks onbemeten kozijnen") }
            if objects.isEmpty && !(f["totals"]?["frame_count"]?["value"]?.isNull ?? true) { e.append("\(path).totals.frame_count: aantal zonder objecten") }
        }
        return e
    }
}

extension GevelInventoryV1: Codable {
    public init(from decoder: Decoder) throws { try self.init(validating: try JSONValue(from: decoder)) }
    public func encode(to encoder: Encoder) throws { try body.encode(to: encoder) }
}
