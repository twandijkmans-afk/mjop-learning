import Combine
import MJOPIntegration
import SwiftUI
import UIKit

/// Meldingen die de gebruiker te zien krijgt (één tegelijk).
enum NavAlert: Identifiable {
    case info(title: String, message: String)
    /// Het huidige project heeft niet-opgeslagen wijzigingen: pas na een uitdrukkelijke bevestiging wordt het vervangen (`force`).
    case unsavedOpen(ProjectSummary)
    case unsavedMeasure(ProjectSummary)

    var id: String {
        switch self {
        case .info(let t, let m): return "info-\(t)-\(m)"
        case .unsavedOpen(let p): return "open-\(p.id)"
        case .unsavedMeasure(let p): return "measure-\(p.id)"
        }
    }
}

/// Navigatiestatus en -acties van de native tabs. Alleen lezen/navigeren: alles loopt via gevalideerde commando's aan de website (`MJOPWebController.send`);
/// de app schrijft nooit zelf naar de planopslag (`saved_plans`).
@MainActor
final class AppNavigator: ObservableObject {
    enum Tab: Hashable { case home, projects, measure, mjop, profile }

    @Published var selected: Tab = .home
    @Published var mjopSection: MJOPSection = .planning
    @Published var showScannerTest = CommandLine.arguments.contains("-scanner-test")
    @Published var alert: NavAlert?
    @Published private(set) var busy = false

    /// Laatste goede projectlijst uit de backend (alleen in het geheugen; er wordt niets op schijf bewaard). Bij offline blijft die zichtbaar.
    @Published private(set) var projectList: ProjectList?
    @Published private(set) var projectsLoading = false
    @Published private(set) var projectsError: String?
    /// Door de gebruiker gekozen project voor Meten (anders het project dat nu in de website is geopend).
    @Published var measureProjectId: String?

    weak var web: MJOPWebController?
    weak var rounds: RoundCoordinator?

    // MARK: projecten

    func refreshProjects() async {
        guard let web, web.navMode == .tabs else { return }
        projectsLoading = true
        defer { projectsLoading = false }
        let r = await web.send(.getProjects)
        if r.ok, let list = ProjectList.parse(r.data) {
            projectList = list
            projectsError = nil
        } else {
            projectsError = Self.message(for: r)
        }
    }

    /// Het project waarmee Meten werkt: de keuze van de gebruiker, anders het project dat in de website geopend is. Nooit een verzonnen project.
    var measureProject: ProjectSummary? {
        if let id = measureProjectId {
            if let p = projectList?.projects.first(where: { $0.id == id }) { return p }
            if let s = web?.webStatus, s.planId == id { return ProjectSummary(id: id, label: s.label ?? "Geopend project", isCurrent: true) }
            return nil
        }
        if let s = web?.webStatus, let id = s.planId { return projectList?.projects.first(where: { $0.id == id }) ?? ProjectSummary(id: id, label: s.label ?? "Geopend project", nextStep: s.nextStep, isCurrent: true) }
        return nil
    }

    /// Opent een project in de website en toont het in het MJOP-gedeelte.
    func open(_ project: ProjectSummary, force: Bool = false) async {
        guard let web else { return }
        busy = true
        defer { busy = false }
        let r = await web.send(.openProject(id: project.id, tab: MJOPSection.planning.webTab, force: force))
        if r.ok {
            mjopSection = .planning
            measureProjectId = project.id
            selected = .mjop
            await refreshProjects()
        } else if r.errorCode == "UNSAVED_CHANGES" {
            alert = .unsavedOpen(project)
        } else {
            alert = .info(title: "Project openen mislukt", message: Self.message(for: r))
        }
    }

    /// De gebruiker bevestigde dat het huidige, niet-opgeslagen werk vervangen mag worden.
    func confirmOpenAnyway(_ project: ProjectSummary) async { await open(project, force: true) }

    // MARK: meten

    /// Start een nieuwe fotoronde voor het gekozen project. De website opent het project en start daarna zelf de bestaande scanner-brug
    /// (`startPhotoRound`); de ronde opent daarna op de gewone manier schermvullend. Er wordt niets geboekt of overgenomen.
    func startMeasurement(force: Bool = false) async {
        guard let web else { return }
        guard let project = measureProject else {
            alert = .info(title: "Kies eerst een project", message: "Een meting hoort altijd bij een project. Kies hierboven een project.")
            return
        }
        busy = true
        defer { busy = false }
        let r = await web.send(.startMeasurement(mode: .round, planId: project.id, elementKey: nil, force: force))
        if r.ok { return }
        if r.errorCode == "UNSAVED_CHANGES" { alert = .unsavedMeasure(project) } else {
            alert = .info(title: "Meting starten mislukt", message: Self.message(for: r))
        }
    }

    // MARK: onderdelen tonen

    func showMJOPSection() async {
        guard let web, web.navMode == .tabs, web.webStatus?.hasBuilding == true else { return }
        _ = await web.send(.navigate(tab: mjopSection.webTab, sub: nil))
    }

    func show(_ section: ProfileSection) async {
        guard let web else { return }
        let t = section.target
        _ = await web.send(.navigate(tab: t.tab, sub: t.sub))
    }

    func showNewProject() async {
        guard let web else { return }
        let r = await web.send(.newProject)
        if !r.ok { alert = .info(title: "Nieuw project", message: Self.message(for: r)) }
    }

    func signOut() async {
        guard let web else { return }
        let r = await web.send(.signOut)
        if r.ok {
            projectList = nil
            measureProjectId = nil
            selected = .profile
        } else {
            alert = .info(title: "Uitloggen mislukt", message: Self.message(for: r))
        }
    }

    // MARK: teksten

    static func message(for r: WebCommandResult) -> String {
        switch r.errorCode {
        case "NOT_LOGGED_IN": return "Je bent niet ingelogd. Log in via Profiel."
        case "TIMEOUT": return "De website reageerde niet op tijd. Controleer je verbinding en probeer het opnieuw."
        case "NOT_READY", "NOT_DELIVERED": return "De website is nog niet geladen. Probeer het over een paar seconden opnieuw."
        case "NO_PROJECT": return "Er is geen project geopend."
        default: return r.errorMessage ?? "Er ging iets mis. Probeer het opnieuw."
        }
    }
}

/// Huisstijl van de website (`--green` en `--ink` uit src/style.css).
enum MJOPTheme {
    /// Alleen voor positieve statussen ("Verbonden", "Overgedragen"). De merkkleur is `accent`.
    static let green = Color(red: 78.0 / 255, green: 143.0 / 255, blue: 110.0 / 255)
    /// Merkkleur: het kobaltblauw van de website (`--blue`), in donkere weergave lichter zodat het leesbaar blijft.
    static let accent = Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(red: 126.0 / 255, green: 143.0 / 255, blue: 255.0 / 255, alpha: 1) : UIColor(red: 47.0 / 255, green: 75.0 / 255, blue: 255.0 / 255, alpha: 1) })
    static let ink = Color(red: 16.0 / 255, green: 18.0 / 255, blue: 17.0 / 255)
}
