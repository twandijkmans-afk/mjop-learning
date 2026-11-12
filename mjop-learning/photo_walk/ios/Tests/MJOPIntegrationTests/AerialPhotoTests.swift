import XCTest
@testable import MJOPIntegration

/// Luchtfoto voor projectkaarten: alleen een foto bij een echt adres (postcode + huisnummer) en nooit van een ander gebouw.
final class AerialPhotoTests: XCTestCase {
    func testQueryFromTypicalAddresses() {
        XCTAssertEqual(AerialPhoto.query(from: "Singelstraat 8, 1398BN Muiden"), AerialPhoto.Query(postcode: "1398BN", huisnummer: "8"))
        XCTAssertEqual(AerialPhoto.query(from: "Zomerdijkstraat 14-1, 1079XB Amsterdam"), AerialPhoto.Query(postcode: "1079XB", huisnummer: "14"))
        XCTAssertEqual(AerialPhoto.query(from: "Venetiëstraat 12, 1019 nh Amsterdam"), AerialPhoto.Query(postcode: "1019NH", huisnummer: "12"))
        XCTAssertEqual(AerialPhoto.query(from: "Singelstraat 8, 1398BN Muiden")?.text, "1398BN 8")
    }

    func testNoQueryWithoutPostcodeAndHouseNumber() {
        XCTAssertNil(AerialPhoto.query(from: "Voorbeeldgebouw — portiekflat"), "geen adres: geen foto")
        XCTAssertNil(AerialPhoto.query(from: "Singelstraat Muiden"), "geen postcode")
        XCTAssertNil(AerialPhoto.query(from: "1398BN Muiden"), "geen huisnummer")
        XCTAssertNil(AerialPhoto.query(from: "Singelstraat 0, 1398BN Muiden"), "huisnummer 0 bestaat niet")
        XCTAssertNil(AerialPhoto.query(from: ""))
        XCTAssertNil(AerialPhoto.query(from: String(repeating: "a", count: 300)))
    }

    func testGeocodeURLAsksForAddressesOnly() throws {
        let q = try XCTUnwrap(AerialPhoto.query(from: "Singelstraat 8, 1398BN Muiden"))
        let url = try XCTUnwrap(AerialPhoto.geocodeURL(q)).absoluteString
        XCTAssertTrue(url.hasPrefix("https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?"))
        XCTAssertTrue(url.contains("fq=type:adres"))
        XCTAssertTrue(url.contains("rows=1"))
    }

    private func response(postcode: String, centroid: String) -> Data {
        Data(#"{"response":{"numFound":1,"docs":[{"postcode":"\#(postcode)","huisnummer":8,"centroide_rd":"\#(centroid)"}]}}"#.utf8)
    }

    func testCentroidParsedOnlyForTheRequestedPostcode() throws {
        let q = try XCTUnwrap(AerialPhoto.query(from: "Singelstraat 8, 1398BN Muiden"))
        XCTAssertEqual(AerialPhoto.parseCentroid(response(postcode: "1398BN", centroid: "POINT(133171.93 482504.727)"), expecting: q),
                       AerialPhoto.Point(x: 133171.93, y: 482504.727))
        XCTAssertNil(AerialPhoto.parseCentroid(response(postcode: "1079XB", centroid: "POINT(133171.93 482504.727)"), expecting: q), "andere postcode: negeren")
    }

    func testCentroidRejectsGarbageAndPlacesOutsideTheNetherlands() throws {
        let q = try XCTUnwrap(AerialPhoto.query(from: "Singelstraat 8, 1398BN Muiden"))
        for bad in ["POINT(1 2)", "POINT(133171.93)", "POINT(abc def)", "LINESTRING(1 2, 3 4)", "", "POINT(133171.93 482504.727) extra", "POINT(-5 482504)"] {
            XCTAssertNil(AerialPhoto.parseCentroid(response(postcode: "1398BN", centroid: bad), expecting: q), bad)
        }
        XCTAssertNil(AerialPhoto.parseCentroid(Data("geen json".utf8), expecting: q))
        XCTAssertNil(AerialPhoto.parseCentroid(Data(#"{"response":{"docs":[]}}"#.utf8), expecting: q), "geen resultaat")
        XCTAssertNil(AerialPhoto.parseCentroid(Data(#"{"response":{"docs":[{"postcode":"1398BN"}]}}"#.utf8), expecting: q), "geen coördinaat")
    }

    func testImageURLCoversAboutOneHundredTwentyMetersAroundThePoint() throws {
        let url = try XCTUnwrap(AerialPhoto.imageURL(center: AerialPhoto.Point(x: 133171.9, y: 482504.7))).absoluteString
        XCTAssertTrue(url.hasPrefix("https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0?"))
        XCTAssertTrue(url.contains("layers=Actueel_orthoHR"))
        XCTAssertTrue(url.contains("crs=EPSG:28992"))
        XCTAssertTrue(url.contains("bbox=133111.9,482468.7,133231.9,482540.7"), url)
        XCTAssertTrue(url.contains("width=600"))
        XCTAssertTrue(url.contains("height=360"))
    }

    func testImageURLRefusesAbsurdSizes() {
        let p = AerialPhoto.Point(x: 133171.9, y: 482504.7)
        XCTAssertNil(AerialPhoto.imageURL(center: p, widthM: 5))
        XCTAssertNil(AerialPhoto.imageURL(center: p, widthM: 5000))
        XCTAssertNil(AerialPhoto.imageURL(center: p, pixelWidth: 50))
        XCTAssertNil(AerialPhoto.imageURL(center: p, pixelWidth: 5000))
    }
}
