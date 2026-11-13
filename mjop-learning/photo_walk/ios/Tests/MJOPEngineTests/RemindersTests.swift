import XCTest
@testable import MJOPEngine

final class RemindersTests: XCTestCase {
    var cal: Calendar { var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "Europe/Amsterdam")!; return c }
    func date(_ y: Int, _ m: Int, _ d: Int) -> Date { cal.date(from: DateComponents(year: y, month: m, day: d, hour: 12))! }

    let plan = [
        PlannedCost(key: "a", naam: "Schilderwerk buitenkozijnen", jaar: 2027, bedrag: 4200.4),
        PlannedCost(key: "b", naam: "Dakgoten", jaar: 2027, bedrag: 900),
        PlannedCost(key: "c", naam: "Voegwerk", jaar: 2027, bedrag: 3000),
        PlannedCost(key: "d", naam: "Trappenhuis", jaar: 2026, bedrag: 500),
        PlannedCost(key: "e", naam: "Lift", jaar: 2031, bedrag: 12000),
    ]

    func testOnePerYearAheadOfJanuaryFirst() throws {
        let r = ReminderPlanner.reminders(plan, leadMonths: 3, now: date(2026, 9, 1), calendar: cal)
        XCTAssertEqual(r.map(\.year), [2027], "2026 is al voorbij het meldmoment; 2031 valt buiten de twee jaar")
        let fire = cal.dateComponents([.year, .month, .day, .hour], from: try XCTUnwrap(r.first).fireDate)
        XCTAssertEqual([fire.year, fire.month, fire.day, fire.hour], [2026, 10, 1, 9], "drie maanden voor 1 januari 2027")
    }

    func testNoReminderAfterTheMoment() {
        XCTAssertTrue(ReminderPlanner.reminders(plan, leadMonths: 3, now: date(2026, 11, 13), calendar: cal).isEmpty, "1 oktober 2026 ligt al achter ons")
    }

    func testFutureDateAndTotals() throws {
        let r = try XCTUnwrap(ReminderPlanner.reminders(plan, leadMonths: 1, now: date(2026, 11, 13), calendar: cal).first)
        XCTAssertEqual(r.year, 2027)
        XCTAssertEqual(cal.dateComponents([.month, .day], from: r.fireDate).month, 12)
        XCTAssertEqual(r.total, 8100)
        XCTAssertEqual(ReminderPlanner.body(r), "In 2027 gepland: Schilderwerk buitenkozijnen, Dakgoten en 1 andere post.")
    }

    func testEmptyPlanGivesNothing() {
        XCTAssertTrue(ReminderPlanner.reminders([], leadMonths: 3, now: date(2026, 1, 1), calendar: cal).isEmpty)
    }
}
