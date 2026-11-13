import Foundation

/// Herinneringen voor gepland onderhoud. Het plan kent alleen jaren, dus één herinnering per jaar met posten:
/// `leadMonths` maanden vóór 1 januari van dat jaar, om 9:00. Alleen data in de toekomst; geen herinneringen achteraf.
public struct MaintenanceReminder: Equatable {
    public var year: Int
    public var fireDate: Date
    /// Namen van de geplande posten in dat jaar, in planvolgorde, zonder dubbele.
    public var items: [String]
    /// Geraamd totaal van dat jaar (afgerond op euro's), uit het plan.
    public var total: Decimal
}

public enum ReminderPlanner {
    public static let leadChoices = [1, 3, 6]

    public static func reminders(_ plan: [PlannedCost], leadMonths: Int, now: Date, years: Int = 2, calendar cal0: Calendar = Calendar(identifier: .gregorian)) -> [MaintenanceReminder] {
        var cal = cal0
        cal.timeZone = cal0.timeZone
        let thisYear = cal.component(.year, from: now)
        var out: [MaintenanceReminder] = []
        for y in thisYear...(thisYear + years) {
            let items = plan.filter { $0.jaar == y }
            guard !items.isEmpty,
                  let jan1 = cal.date(from: DateComponents(year: y, month: 1, day: 1, hour: 9)),
                  let fire = cal.date(byAdding: .month, value: -max(0, leadMonths), to: jan1),
                  fire > now else { continue }
            var names: [String] = []
            for i in items where !names.contains(i.naam) { names.append(i.naam) }
            let total = Engine.roundEuro(items.reduce(Decimal(0)) { $0 + $1.bedrag })
            out.append(MaintenanceReminder(year: y, fireDate: fire, items: names, total: total))
        }
        return out
    }

    /// Korte tekst voor de melding: de eerste twee posten en hoeveel er nog meer zijn.
    public static func body(_ r: MaintenanceReminder) -> String {
        let shown = r.items.prefix(2).joined(separator: ", ")
        let more = r.items.count > 2 ? " en \(r.items.count - 2) andere post\(r.items.count - 2 == 1 ? "" : "en")" : ""
        return "In \(r.year) gepland: \(shown)\(more)."
    }
}
