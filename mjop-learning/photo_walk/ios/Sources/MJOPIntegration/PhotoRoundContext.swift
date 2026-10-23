import Foundation

/// Context waarmee de website een fotoronde (of een scan vanuit één onderhoudselement) start. Wordt volledig gevalideerd vóór er iets gebeurt;
/// de app vertrouwt alleen wat hier door de controles komt.
public struct PhotoRoundContext: Codable, Equatable {
    public struct Element: Codable, Equatable {
        public var key: String
        public var name: String
        public var unit: String          // st | m2 | m1
        public init(key: String, name: String, unit: String) { self.key = key; self.name = name; self.unit = unit }
    }
    public struct PlannedFacade: Codable, Equatable {
        public var name: String
        public var orientation: String?
        public init(name: String, orientation: String?) { self.name = name; self.orientation = orientation }
    }
    public enum Mode: String, Codable { case round, element }

    public var planRef: String
    public var mjopPlanId: String?
    public var buildingLabel: String
    public var bagPandId: String?
    public var mode: Mode
    public var element: Element?
    public var plannedFacades: [PlannedFacade]

    public init(planRef: String, mjopPlanId: String?, buildingLabel: String, bagPandId: String?, mode: Mode, element: Element?, plannedFacades: [PlannedFacade]) {
        self.planRef = planRef; self.mjopPlanId = mjopPlanId; self.buildingLabel = buildingLabel; self.bagPandId = bagPandId
        self.mode = mode; self.element = element; self.plannedFacades = plannedFacades
    }

    public static let orientations: Set<String> = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

    public enum Invalid: Error, Equatable { case field(String) }

    static func match(_ s: String, _ pattern: String) -> Bool { s.range(of: pattern, options: .regularExpression) != nil }

    /// Strikte validatie van een JSON-waarde (zoals die uit de WebView komt). Onbekende velden worden genegeerd, ontbrekende of ongeldige geweigerd.
    public static func validate(_ raw: Any?) -> Result<PhotoRoundContext, Invalid> {
        guard let d = raw as? [String: Any] else { return .failure(.field("context")) }
        guard let planRef = d["planRef"] as? String, match(planRef, "^[A-Za-z0-9_-]{8,80}$") else { return .failure(.field("planRef")) }
        var planId: String? = nil
        if let v = d["mjopPlanId"], !(v is NSNull) {
            guard let s = v as? String, (1...80).contains(s.count) else { return .failure(.field("mjopPlanId")) }
            planId = s
        }
        guard let labelRaw = d["buildingLabel"] as? String else { return .failure(.field("buildingLabel")) }
        let label = labelRaw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard (1...200).contains(label.count), label.unicodeScalars.allSatisfy({ !CharacterSet.controlCharacters.contains($0) }) else { return .failure(.field("buildingLabel")) }
        var bag: String? = nil
        if let v = d["bagPandId"], !(v is NSNull) {
            guard let s = v as? String, match(s, "^[0-9]{16}$") else { return .failure(.field("bagPandId")) }
            bag = s
        }
        guard let modeRaw = d["mode"] as? String, let mode = Mode(rawValue: modeRaw) else { return .failure(.field("mode")) }
        var element: Element? = nil
        if let ev = d["element"], !(ev is NSNull) {
            guard let e = ev as? [String: Any], let key = e["key"] as? String, match(key, "^[a-z0-9-]{1,80}$"),
                  let name = e["name"] as? String, (1...120).contains(name.count),
                  let unit = e["unit"] as? String, ["st", "m2", "m1"].contains(unit) else { return .failure(.field("element")) }
            element = Element(key: key, name: name, unit: unit)
        }
        if mode == .element && element == nil { return .failure(.field("element")) }
        if mode == .round && element != nil { return .failure(.field("element")) }
        var facades: [PlannedFacade] = []
        if let fv = d["plannedFacades"], !(fv is NSNull) {
            guard let arr = fv as? [[String: Any]], arr.count <= 20 else { return .failure(.field("plannedFacades")) }
            for f in arr {
                guard let n = f["name"] as? String, (1...60).contains(n.trimmingCharacters(in: .whitespacesAndNewlines).count) else { return .failure(.field("plannedFacades")) }
                var o: String? = nil
                if let ov = f["orientation"], !(ov is NSNull) {
                    guard let s = ov as? String, orientations.contains(s) else { return .failure(.field("plannedFacades")) }
                    o = s
                }
                facades.append(PlannedFacade(name: n.trimmingCharacters(in: .whitespacesAndNewlines), orientation: o))
            }
        }
        return .success(PhotoRoundContext(planRef: planRef, mjopPlanId: planId, buildingLabel: label, bagPandId: bag, mode: mode, element: element, plannedFacades: facades))
    }
}
