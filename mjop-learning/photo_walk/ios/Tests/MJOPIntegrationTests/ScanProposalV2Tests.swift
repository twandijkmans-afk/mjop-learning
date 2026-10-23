import XCTest
@testable import MJOPIntegration

final class ScanProposalV2Tests: XCTestCase {
    func fixture(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: name, withExtension: "json", subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }

    func testSharedFixturesDecodeAndAreValid() throws {
        let c = try ScanProposalV2.decode(try fixture("count_building_v2"))
        XCTAssertEqual(c.value, 12); XCTAssertEqual(c.target.quantityKind, .FRAME_COUNT); XCTAssertEqual(c.target.unit, "st")
        XCTAssertEqual(c.project.planRef, "plan-0123456789ab"); XCTAssertFalse(c.bookingAllowed)
        let a = try ScanProposalV2.decode(try fixture("area_building_incomplete_v2"))
        XCTAssertNil(a.value, "onbekend is nil, nooit 0"); XCTAssertEqual(a.partialValue, 17.4); XCTAssertEqual(a.reliability.level, "INCOMPLETE")
    }

    func testRoundTripKeepsRequiredNullKeys() throws {
        let a = try ScanProposalV2.decode(try fixture("area_building_incomplete_v2"))
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: try a.encoded()) as? [String: Any])
        XCTAssertTrue(obj["value"] is NSNull)
        XCTAssertTrue((obj["project"] as? [String: Any])?["mjop_plan_id"] is NSNull)
        XCTAssertTrue(((obj["target"] as? [String: Any])?["scope"] as? [String: Any])?["facade_id"] is NSNull)
        XCTAssertTrue((obj["confirmation"] as? [String: Any])?["confirmed_at"] is NSNull)
        XCTAssertEqual(try ScanProposalV2.decode(try a.encoded()), a)
    }

    func testRuleViolationsAreRejectedOnDecode() throws {
        var s = try XCTUnwrap(String(data: try fixture("count_building_v2"), encoding: .utf8))
        s = s.replacingOccurrences(of: "\"booking_allowed\": false", with: "\"booking_allowed\": true")
        XCTAssertThrowsError(try ScanProposalV2.decode(Data(s.utf8))) { XCTAssertEqual($0 as? ScanProposalV2.DecodeError, .invalid([.bookingMustBeDisallowed])) }
        let v1 = try XCTUnwrap(String(data: try fixture("count_building_v2"), encoding: .utf8)).replacingOccurrences(of: "mjop_scan_proposal_v2", with: "mjop_scan_proposal_v1")
        XCTAssertThrowsError(try ScanProposalV2.decode(Data(v1.utf8))) { XCTAssertEqual($0 as? ScanProposalV2.DecodeError, .unsupportedContract("mjop_scan_proposal_v1")) }
        let conf = try XCTUnwrap(String(data: try fixture("count_building_v2"), encoding: .utf8)).replacingOccurrences(of: "\"status\": \"PROPOSED\"", with: "\"status\": \"CONFIRMED_BY_USER\"")
        XCTAssertThrowsError(try ScanProposalV2.decode(Data(conf.utf8))) { XCTAssertEqual($0 as? ScanProposalV2.DecodeError, .invalid([.notProposed])) }
    }

    func testAreaWithUnmeasuredObjectsMustNotCarryAValue() throws {
        var a = try ScanProposalV2.decode(try fixture("area_building_incomplete_v2"))
        a.value = 17.4
        XCTAssertTrue(a.validate().contains(.areaWithUnmeasured))
        var c = try ScanProposalV2.decode(try fixture("count_building_v2")); c.target.unit = "m2"
        XCTAssertTrue(c.validate().contains(.unitMismatch))
    }
}
