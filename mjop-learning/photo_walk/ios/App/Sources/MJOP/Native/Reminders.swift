import MJOPEngine
import SwiftUI
import UserNotifications

/// Lokale herinneringen voor gepland onderhoud (geen server). Per project één melding per jaar met posten,
/// een instelbaar aantal maanden vóór 1 januari van dat jaar. Wordt bijgewerkt telkens als een plan wordt geladen of bewaard.
enum MaintenanceReminders {
    private static let enabledKey = "mjop.reminders.enabled", leadKey = "mjop.reminders.lead"

    static var enabled: Bool {
        get { UserDefaults.standard.bool(forKey: enabledKey) }
        set { UserDefaults.standard.set(newValue, forKey: enabledKey) }
    }
    static var leadMonths: Int {
        get { let v = UserDefaults.standard.integer(forKey: leadKey); return ReminderPlanner.leadChoices.contains(v) ? v : 3 }
        set { UserDefaults.standard.set(newValue, forKey: leadKey) }
    }

    static func prefix(_ projectId: String) -> String { "mjop.reminder.\(projectId)." }

    /// Vraagt toestemming voor meldingen. Geeft terug of meldingen mogen.
    static func requestPermission() async -> Bool {
        (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Vervangt de herinneringen van één project door die uit het huidige plan.
    static func schedule(project: Project, model: ProjectModel) async {
        let center = UNUserNotificationCenter.current()
        let pending = await center.pendingNotificationRequests().map(\.identifier).filter { $0.hasPrefix(prefix(project.id)) }
        center.removePendingNotificationRequests(withIdentifiers: pending)
        guard enabled else { return }
        for r in ReminderPlanner.reminders(model.plan, leadMonths: leadMonths, now: Date()) {
            let c = UNMutableNotificationContent()
            c.title = "\(project.naam): onderhoud in \(r.year)"
            c.body = ReminderPlanner.body(r) + " Geraamd \(DSFormat.euros(NSDecimalNumber(decimal: r.total).intValue))."
            c.sound = .default
            c.userInfo = ["project": project.id, "year": r.year]
            let comps = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: r.fireDate)
            let req = UNNotificationRequest(identifier: prefix(project.id) + String(r.year), content: c,
                                            trigger: UNCalendarNotificationTrigger(dateMatching: comps, repeats: false))
            try? await center.add(req)
        }
    }

    static func removeAll() async {
        let center = UNUserNotificationCenter.current()
        let ids = await center.pendingNotificationRequests().map(\.identifier).filter { $0.hasPrefix("mjop.reminder.") }
        center.removePendingNotificationRequests(withIdentifiers: ids)
    }

    /// Alle projecten opnieuw inplannen (na aanzetten of een andere termijn).
    static func refreshAll(store: ProjectStore, account: Account) async {
        guard enabled else { await removeAll(); return }
        for p in store.projects {
            if let m = try? await store.loadModel(p, account: account) { await schedule(project: p, model: m) }
        }
    }

    /// Overzicht van wat er gepland staat, voor het instellingenscherm.
    static func upcoming() async -> [(date: Date, title: String)] {
        await UNUserNotificationCenter.current().pendingNotificationRequests()
            .filter { $0.identifier.hasPrefix("mjop.reminder.") }
            .compactMap { r -> (date: Date, title: String)? in
                guard let t = r.trigger as? UNCalendarNotificationTrigger, let d = t.nextTriggerDate() else { return nil }
                return (date: d, title: r.content.title)
            }
            .sorted { $0.date < $1.date }
    }
}

/// Instellingen voor herinneringen: aan/uit, hoe ver vooruit, en wat er gepland staat.
struct RemindersSettingsView: View {
    @EnvironmentObject var account: Account
    @EnvironmentObject var store: ProjectStore
    @Environment(\.dismiss) private var dismiss
    @State private var on = MaintenanceReminders.enabled
    @State private var lead = MaintenanceReminders.leadMonths
    @State private var upcoming: [(date: Date, title: String)] = []
    @State private var denied = false
    @State private var busy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("Herinneringen voor onderhoud", isOn: Binding(get: { on }, set: { v in Task { await setOn(v) } }))
                        .tint(DS.accent)
                        .accessibilityIdentifier("remindersToggle")
                    Picker("Hoe ver vooruit", selection: Binding(get: { lead }, set: { v in lead = v; MaintenanceReminders.leadMonths = v; Task { await refresh() } })) {
                        ForEach(ReminderPlanner.leadChoices, id: \.self) { m in Text(m == 1 ? "1 maand" : "\(m) maanden").tag(m) }
                    }
                    .disabled(!on)
                } footer: {
                    Text("Per project één melding voor elk jaar met gepland onderhoud, zoveel maanden vóór 1 januari van dat jaar. Meldingen staan alleen op deze iPhone en worden bijgewerkt als het plan verandert.")
                }
                if denied {
                    Section { Text("Meldingen staan uit voor MJOP Live. Zet ze aan bij Instellingen → Meldingen → MJOP Live.").foregroundStyle(DS.warn) }
                }
                if on {
                    Section("Gepland") {
                        if busy { ProgressView() }
                        else if upcoming.isEmpty { Text("Geen herinneringen in de komende twee jaar (of het meldmoment is al voorbij).").foregroundStyle(DS.text2) }
                        ForEach(Array(upcoming.enumerated()), id: \.offset) { _, u in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(u.title).font(.subheadline.weight(.semibold))
                                Text(u.date.formatted(.dateTime.day().month(.wide).year().locale(Locale(identifier: "nl_NL")))).font(.caption).foregroundStyle(DS.text2)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Herinneringen").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Klaar") { dismiss() } } }
            .task { upcoming = await MaintenanceReminders.upcoming() }
        }
    }

    private func setOn(_ v: Bool) async {
        if v {
            guard await MaintenanceReminders.requestPermission() else { denied = true; on = false; return }
            denied = false
        }
        on = v
        MaintenanceReminders.enabled = v
        await refresh()
    }

    private func refresh() async {
        busy = true; defer { busy = false }
        await MaintenanceReminders.refreshAll(store: store, account: account)
        upcoming = await MaintenanceReminders.upcoming()
    }
}
