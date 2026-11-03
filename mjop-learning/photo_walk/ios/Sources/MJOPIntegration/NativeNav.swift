import Foundation

/// Native navigatie (app-versie 2): contract tussen de app en de website. Zie `photo_walk/docs/mjop_integration.md` en in de website `docs/native-bridge-v2.md`.
/// Alleen Foundation, zodat alles op macOS testbaar is. Alles is ALLEEN LEZEN/NAVIGEREN: de app schrijft nooit naar de planopslag (`saved_plans`).
public enum NativeNav {
    /// Waarde van `MJOPLiveApp/<n>` in de User-Agent; de website verbergt daarmee zijn eigen tabbalk.
    public static let appLevel = 2
    /// Wat de app meldt in `nativeReady`: de app toont zelf de tabbalk.
    public static let tabsFeature = "tabs1"
    /// Wat de website meldt in `webReady`: de website kent de navigatiecommando's.
    public static let webNavFeature = "nav1"
    /// Zo lang wacht de app na het laden van de pagina op `webReady`, voordat hij terugvalt op de klassieke weergave (oudere website).
    public static let readyTimeout: TimeInterval = 6
    /// Antwoordtijd op een commando.
    public static let commandTimeout: TimeInterval = 25

    public static let allowedTabs: Set<String> = ["start", "home", "gebouw", "fotoronde", "planning", "rapport", "account", "instellingen", "mijngebouwen"]
    public static let allowedSubs: Set<String> = ["profiel", "organisatie", "weergave", "rapport", "abonnement"]

    static func match(_ s: String, _ pattern: String) -> Bool { s.range(of: pattern, options: .regularExpression) != nil }
    /// Zelfde patroon als `PLAN_ID_RE` in de website.
    public static func isValidPlanId(_ s: String) -> Bool { match(s, "^[A-Za-z0-9-]{8,64}$") }
}

// MARK: - commando's (app → website)

public enum NativeCommand: Equatable {
    case navigate(tab: String, sub: String?)
    case getProjects
    case openProject(id: String, tab: String?, force: Bool)
    case startMeasurement(mode: PhotoRoundContext.Mode, planId: String?, elementKey: String?, force: Bool)
    case getStatus
    case getProposals
    case signOut
    case newProject

    public var name: String {
        switch self {
        case .navigate: return "navigate"
        case .getProjects: return "getProjects"
        case .openProject: return "openProject"
        case .startMeasurement: return "startMeasurement"
        case .getStatus: return "getStatus"
        case .getProposals: return "getProposals"
        case .signOut: return "signOut"
        case .newProject: return "newProject"
        }
    }

    /// Past binnen het gesloten schema van de website? Ongeldige commando's worden nooit verstuurd.
    public var isValid: Bool {
        switch self {
        case .navigate(let tab, let sub):
            guard NativeNav.allowedTabs.contains(tab) else { return false }
            if let sub { return NativeNav.allowedSubs.contains(sub) && (tab == "account" || tab == "instellingen") }
            return true
        case .openProject(let id, let tab, _):
            if let tab, !NativeNav.allowedTabs.contains(tab) { return false }
            return NativeNav.isValidPlanId(id)
        case .startMeasurement(let mode, let planId, let key, _):
            if let planId, !NativeNav.isValidPlanId(planId) { return false }
            if mode == .element { return key.map { NativeNav.match($0, "^[a-z0-9-]{1,80}$") } ?? false }
            return true
        case .getProjects, .getStatus, .getProposals, .signOut, .newProject:
            return true
        }
    }

    /// Het bericht zoals de website het verwacht (de envelop `v` wordt door `BridgeReply.script` toegevoegd).
    public func message(requestId: String) -> [String: Any] {
        var m: [String: Any] = ["type": "command", "command": name, "requestId": requestId]
        switch self {
        case .navigate(let tab, let sub):
            m["tab"] = tab
            if let sub { m["sub"] = sub }
        case .openProject(let id, let tab, let force):
            m["id"] = id
            if let tab { m["tab"] = tab }
            if force { m["force"] = true }
        case .startMeasurement(let mode, let planId, let key, let force):
            m["mode"] = mode.rawValue
            if let planId { m["planId"] = planId }
            if let key { m["elementKey"] = key }
            if force { m["force"] = true }
        case .getProjects, .getStatus, .getProposals, .signOut, .newProject:
            break
        }
        return m
    }
}

/// Antwoord van de website op een commando (`webReply`).
public struct WebCommandResult: Equatable {
    public var command: String
    public var ok: Bool
    public var data: JSONValue?
    public var errorCode: String?
    public var errorMessage: String?

    public init(command: String, ok: Bool, data: JSONValue? = nil, errorCode: String? = nil, errorMessage: String? = nil) {
        self.command = command; self.ok = ok; self.data = data; self.errorCode = errorCode; self.errorMessage = errorMessage
    }
    /// Lokaal gemaakt resultaat als de website niet (op tijd) antwoordt.
    public static func failure(command: String, code: String, message: String) -> WebCommandResult {
        WebCommandResult(command: command, ok: false, data: nil, errorCode: code, errorMessage: message)
    }
}

// MARK: - secties van de tabs

/// De vier onderdelen van de tab MJOP en het tabblad van de website waar ze op uitkomen.
public enum MJOPSection: String, CaseIterable, Equatable {
    case planning, maatregelen, begroting, rapportage

    public var title: String {
        switch self {
        case .planning: return "Planning"
        case .maatregelen: return "Maatregelen"
        case .begroting: return "Begroting"
        case .rapportage: return "Rapportage"
        }
    }
    /// Maatregelen = de onderhoudsposten (tabblad Gebouw); Begroting = Overzicht met bijdrage en reservefonds.
    public var webTab: String {
        switch self {
        case .planning: return "planning"
        case .maatregelen: return "gebouw"
        case .begroting: return "home"
        case .rapportage: return "rapport"
        }
    }
    public static func from(webTab: String) -> MJOPSection? { allCases.first { $0.webTab == webTab } }
}

/// De onderdelen van Profiel die de website tonen.
public enum ProfileSection: String, CaseIterable, Equatable {
    case account, organisatie, weergave, abonnement, privacy

    public var title: String {
        switch self {
        case .account: return "Account"
        case .organisatie: return "Organisatie"
        case .weergave: return "Weergave"
        case .abonnement: return "Abonnement"
        case .privacy: return "Privacy"
        }
    }
    /// Privacy staat op de website op de profielpagina (blok "Gegevens en privacy").
    public var target: (tab: String, sub: String) {
        switch self {
        case .account: return ("account", "profiel")
        case .organisatie: return ("account", "organisatie")
        case .weergave: return ("account", "weergave")
        case .abonnement: return ("account", "abonnement")
        case .privacy: return ("account", "profiel")
        }
    }
}

// MARK: - gegevens uit de website (gevalideerd, alleen lezen)

public enum NativeDates {
    /// ISO-8601 zoals Supabase het levert, ook met microseconden ("2026-10-30T09:15:00.123456+00:00").
    public static func parse(_ s: String) -> Date? {
        let trimmed = s.replacingOccurrences(of: "\\.\\d+", with: "", options: .regularExpression)
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: trimmed)
    }
}

public struct ProjectSummary: Equatable, Identifiable {
    public var id: String
    public var label: String
    public var adres: String?
    public var updatedAt: String?
    public var nextStep: String?
    public var isCurrent: Bool

    public var updatedDate: Date? { updatedAt.flatMap(NativeDates.parse) }

    public init(id: String, label: String, adres: String? = nil, updatedAt: String? = nil, nextStep: String? = nil, isCurrent: Bool = false) {
        self.id = id; self.label = label; self.adres = adres; self.updatedAt = updatedAt; self.nextStep = nextStep; self.isCurrent = isCurrent
    }

    static func parse(_ v: JSONValue) -> ProjectSummary? {
        guard let id = v["id"]?.string, NativeNav.isValidPlanId(id), let label = v["label"]?.string, !label.isEmpty, label.count <= 200 else { return nil }
        func opt(_ k: String) -> String? { if let s = v[k]?.string, !s.isEmpty, s.count <= 200 { return s }; return nil }
        return ProjectSummary(id: id, label: label, adres: opt("adres"), updatedAt: opt("updatedAt"), nextStep: opt("nextStep"), isCurrent: v["current"]?.bool ?? false)
    }
}

public struct ProjectList: Equatable {
    public var loggedIn: Bool
    public var projects: [ProjectSummary]

    /// Ongeldige regels worden overgeslagen (nooit geraden); een lijst zonder `loggedIn` is ongeldig.
    public static func parse(_ data: JSONValue?) -> ProjectList? {
        guard let d = data, let li = d["loggedIn"]?.bool, let arr = d["projects"]?.array, arr.count <= 200 else { return nil }
        return ProjectList(loggedIn: li, projects: arr.compactMap(ProjectSummary.parse))
    }
}

public enum SaveStatus: String, Equatable {
    case notLoggedIn = "NOT_LOGGED_IN", notSaved = "NOT_SAVED", pending = "PENDING", saved = "SAVED", error = "ERROR", unknown = "UNKNOWN"
}

/// Status van de website (alleen lezen): welk project is geopend, op welk tabblad, is er iets niet opgeslagen, hoeveel voorstellen wachten.
public struct WebStatus: Equatable {
    public var loggedIn: Bool
    public var subscribed: Bool
    public var planId: String?
    public var hasBuilding: Bool
    public var isExample: Bool
    public var label: String?
    public var tab: String
    public var screen: String
    public var dirty: Bool
    public var saveStatus: SaveStatus
    public var pendingProposals: Int
    public var planRef: String?
    public var nextStep: String?

    public static func parse(_ v: JSONValue?) -> WebStatus? {
        guard let v, v.object != nil else { return nil }
        func opt(_ k: String) -> String? { if let s = v[k]?.string, !s.isEmpty, s.count <= 200 { return s }; return nil }
        let planId = v["planId"]?.string.flatMap { NativeNav.isValidPlanId($0) ? $0 : nil }
        return WebStatus(
            loggedIn: v["loggedIn"]?.bool ?? false, subscribed: v["subscribed"]?.bool ?? false, planId: planId,
            hasBuilding: v["hasBuilding"]?.bool ?? false, isExample: v["example"]?.bool ?? false, label: opt("label"),
            tab: opt("tab") ?? "", screen: opt("screen") ?? "", dirty: v["dirty"]?.bool ?? false,
            saveStatus: v["saveStatus"]?.string.flatMap { SaveStatus(rawValue: $0) } ?? .unknown,
            pendingProposals: max(0, min(v["pendingProposals"]?.int ?? 0, 9999)), planRef: opt("planRef"), nextStep: opt("nextStep"))
    }
}

/// Een openstaand voorstel zoals de website het toont. Een onbekende waarde is `nil`, nooit 0.
public struct ProposalSummary: Equatable, Identifiable {
    public var id: String
    public var kind: String
    public var unit: String
    public var scope: String
    public var value: Double?
    public var partialValue: Double?
    public var level: String

    static func parse(_ v: JSONValue) -> ProposalSummary? {
        guard let id = v["id"]?.string, !id.isEmpty, id.count <= 80, let kind = v["kind"]?.string, let unit = v["unit"]?.string,
              let scope = v["scope"]?.string, let level = v["level"]?.string else { return nil }
        return ProposalSummary(id: id, kind: kind, unit: unit, scope: String(scope.prefix(80)), value: v["value"]?.double, partialValue: v["partialValue"]?.double, level: level)
    }
}

public struct ProposalList: Equatable {
    public var planRef: String?
    public var total: Int
    public var pending: [ProposalSummary]

    public static func parse(_ data: JSONValue?) -> ProposalList? {
        guard let d = data, let arr = d["pending"]?.array, arr.count <= 100 else { return nil }
        return ProposalList(planRef: d["planRef"]?.string, total: max(0, d["total"]?.int ?? 0), pending: arr.compactMap(ProposalSummary.parse))
    }
}
