import Foundation

/// Kleine, vergelijkbare JSON-waarde (alleen Foundation) voor berichten van de website. Onbekende velden blijven bewaard zoals ze zijn; de app
/// leest er alleen uit wat hij kent en schrijft nooit terug naar de planopslag.
public enum JSONValue: Equatable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])
}

extension JSONValue: Decodable {
    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null; return }
        if let b = try? c.decode(Bool.self) { self = .bool(b); return }
        if let n = try? c.decode(Double.self) { self = .number(n); return }
        if let s = try? c.decode(String.self) { self = .string(s); return }
        if let a = try? c.decode([JSONValue].self) { self = .array(a); return }
        if let o = try? c.decode([String: JSONValue].self) { self = .object(o); return }
        throw DecodingError.dataCorruptedError(in: c, debugDescription: "Onbekende JSON-waarde")
    }
}

public extension JSONValue {
    /// Zet een met JSONSerialization gemaakte structuur (zoals een WebKit-bericht) om. Geeft nil bij iets dat geen geldige JSON is.
    static func from(any value: Any) -> JSONValue? {
        guard JSONSerialization.isValidJSONObject(value), let data = try? JSONSerialization.data(withJSONObject: value) else { return nil }
        return try? JSONDecoder().decode(JSONValue.self, from: data)
    }

    static func decode(_ data: Data) -> JSONValue? { try? JSONDecoder().decode(JSONValue.self, from: data) }

    subscript(key: String) -> JSONValue? {
        if case .object(let o) = self { return o[key] }
        return nil
    }

    var isNull: Bool { if case .null = self { return true }; return false }
    var string: String? { if case .string(let s) = self { return s }; return nil }
    var bool: Bool? { if case .bool(let b) = self { return b }; return nil }
    var double: Double? { if case .number(let n) = self { return n }; return nil }
    /// Alleen hele getallen binnen een redelijk bereik; alles anders is nil (geen stil afronden).
    var int: Int? {
        if case .number(let n) = self, n == n.rounded(), abs(n) < 1_000_000_000 { return Int(n) }
        return nil
    }
    var array: [JSONValue]? { if case .array(let a) = self { return a }; return nil }
    var object: [String: JSONValue]? { if case .object(let o) = self { return o }; return nil }
}

extension JSONValue: Encodable {
    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .null: try c.encodeNil()
        case .bool(let b): try c.encode(b)
        case .number(let n): try c.encode(n)
        case .string(let s): try c.encode(s)
        case .array(let a): try c.encode(a)
        case .object(let o): try c.encode(o)
        }
    }
}

public extension JSONValue {
    /// Foundation-structuur (voor JSONSerialization en de brug naar de WebView). null wordt NSNull, zodat een verplichte sleutel met null behouden blijft.
    var foundationValue: Any {
        switch self {
        case .null: return NSNull()
        case .bool(let b): return b
        case .number(let n): return n == n.rounded() && abs(n) < 1e15 ? NSNumber(value: Int64(n)) : NSNumber(value: n)
        case .string(let s): return s
        case .array(let a): return a.map { $0.foundationValue }
        case .object(let o): return o.mapValues { $0.foundationValue }
        }
    }
    static func optional(_ s: String?) -> JSONValue { s.map { .string($0) } ?? .null }
    static func optional(_ d: Double?) -> JSONValue { d.map { .number($0) } ?? .null }
    static func strings(_ a: [String]) -> JSONValue { .array(a.map { .string($0) }) }
}
