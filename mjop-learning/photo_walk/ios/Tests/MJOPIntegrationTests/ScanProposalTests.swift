import XCTest
@testable import MJOPIntegration

final class ScanProposalTests: XCTestCase {
    func fixture() throws -> Data {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "scan_proposal_v1_example", withExtension: "json", subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }

    func make(status: ScanProposal.Measurement.DimensionStatus = .MEASURED, validated: Bool = false, value: Double? = 1.8) -> ScanProposal {
        ScanProposal(proposalId: "prop-0001-demo", createdAt: "2026-10-20T10:00:00Z",
                     project: .init(mjopPlanId: nil, buildingId: "B", facadeId: "F", bagPandId: nil),
                     element: .init(type: .FRAME, mjopElementKey: nil),
                     quantity: .init(unit: .m2, value: value, widthM: 1.2, heightM: 1.5),
                     measurement: .init(method: .LIDAR_DEPTH_MULTI_FRAME, dimensionStatus: status, uncertainty: .init(validated: validated, areaSigmaM2: 0.04, note: "PROVISIONAL_UNVALIDATED")),
                     evidence: .init(sourcePhotoId: "F000", provisionalObjectId: "PROV-0001", qualityFlags: []))
    }

    func testSharedFixtureDecodesAndRoundTrips() throws {
        let p = try ScanProposal.decode(try fixture())
        XCTAssertEqual(p.contract, "mjop_scan_proposal_v1")
        XCTAssertEqual(p.confirmation.status, .PROPOSED)
        XCTAssertFalse(p.bookingAllowed)
        XCTAssertEqual(p.quantity.value, 1.8)
        let again = try ScanProposal.decode(try p.encode())
        XCTAssertEqual(p, again)
    }

    func testNewProposalIsAlwaysAProposalAndNeverBookable() {
        let p = make()
        XCTAssertEqual(p.confirmation.status, .PROPOSED)
        XCTAssertFalse(p.bookingAllowed)
        XCTAssertEqual(p.validate(), [])
    }

    func testUnvalidatedLidarIsUncertainEvenWhenMeasured() {
        XCTAssertTrue(make(status: .MEASURED, validated: false).isUncertain)
        XCTAssertTrue(make(status: .ESTIMATED, validated: true).isUncertain)
        XCTAssertFalse(make(status: .MEASURED, validated: true).isUncertain)
    }

    func testUncertainCannotBeConfirmedWithoutAcknowledgement() {
        XCTAssertThrowsError(try make().confirmed(byUserAt: "2026-10-20T11:00:00Z", acknowledgingUncertainty: false)) { e in
            XCTAssertEqual(e as? ScanProposal.ConfirmationError, .notAllowed([.uncertainConfirmedWithoutAcknowledgement]))
        }
        let ok = try? make().confirmed(byUserAt: "2026-10-20T11:00:00Z", acknowledgingUncertainty: true)
        XCTAssertEqual(ok?.confirmation.status, .CONFIRMED_BY_USER)
        XCTAssertEqual(ok?.confirmation.uncertaintyAcknowledged, true)
        XCTAssertEqual(ok?.bookingAllowed, false, "bevestigen is nog steeds geen boeking")
    }

    func testUnknownOrMissingValueCanNeverBeConfirmed() {
        XCTAssertThrowsError(try make(status: .UNKNOWN, value: nil).confirmed(byUserAt: "t", acknowledgingUncertainty: true))
        XCTAssertThrowsError(try make(value: nil).confirmed(byUserAt: "t", acknowledgingUncertainty: true))
    }

    func testDecisionIsFinal() throws {
        let c = try make().confirmed(byUserAt: "t", acknowledgingUncertainty: true)
        XCTAssertThrowsError(try c.rejected(byUserAt: "t"))
        XCTAssertThrowsError(try c.confirmed(byUserAt: "t", acknowledgingUncertainty: true))
    }

    func testDecodeRejectsRuleViolationsAndOtherVersions() throws {
        var json = try XCTUnwrap(String(data: try fixture(), encoding: .utf8))
        let booking = json.replacingOccurrences(of: "\"booking_allowed\": false", with: "\"booking_allowed\": true")
        XCTAssertThrowsError(try ScanProposal.decode(Data(booking.utf8))) { XCTAssertEqual($0 as? ScanProposal.DecodeError, .invalid([.bookingMustBeDisallowed])) }
        json = json.replacingOccurrences(of: "mjop_scan_proposal_v1", with: "mjop_scan_proposal_v2")
        XCTAssertThrowsError(try ScanProposal.decode(Data(json.utf8))) { XCTAssertEqual($0 as? ScanProposal.DecodeError, .unsupportedContract("mjop_scan_proposal_v2")) }
        let confirmedUncertain = try XCTUnwrap(String(data: try fixture(), encoding: .utf8))
            .replacingOccurrences(of: "\"status\": \"PROPOSED\"", with: "\"status\": \"CONFIRMED_BY_USER\"")
        XCTAssertThrowsError(try ScanProposal.decode(Data(confirmedUncertain.utf8))) { e in
            guard case ScanProposal.DecodeError.invalid(let issues) = e else { return XCTFail() }
            XCTAssertTrue(issues.contains(.uncertainConfirmedWithoutAcknowledgement))
        }
    }

    func testEncodedKeysMatchTheSchemaNames() throws {
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: try make().encode()) as? [String: Any])
        XCTAssertEqual(Set(obj.keys), ["contract", "proposal_id", "created_at", "project", "element", "quantity", "measurement", "evidence", "confirmation", "booking_allowed"])
    }

    func testEncodingKeepsRequiredNullKeys() throws {
        let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: try make(value: nil).encode()) as? [String: Any])
        let project = try XCTUnwrap(obj["project"] as? [String: Any])
        XCTAssertTrue(project["mjop_plan_id"] is NSNull)
        XCTAssertTrue(project["bag_pand_id"] is NSNull)
        XCTAssertTrue((obj["quantity"] as? [String: Any])?["value"] is NSNull)
        XCTAssertTrue((obj["confirmation"] as? [String: Any])?["confirmed_at"] is NSNull)
    }
}
