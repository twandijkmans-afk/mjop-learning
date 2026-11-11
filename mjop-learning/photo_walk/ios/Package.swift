// swift-tools-version:5.9
// PhotoWalkCore: platformonafhankelijke Swift-port van de meetkern (geen ARKit). De ARKit-app staat in App/.
// STATUS: gebouwd (geschreven) maar NIET gecompileerd in de ontwikkelomgeving (geen Xcode/Swift beschikbaar). Zie ../README.md.
import PackageDescription

let package = Package(
    name: "PhotoWalkCore",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "PhotoWalkCore", targets: ["PhotoWalkCore"]),
        .library(name: "MJOPIntegration", targets: ["MJOPIntegration"]),
        .library(name: "Gevelscan", targets: ["Gevelscan"]),
    ],
    targets: [
        .target(name: "PhotoWalkCore"),
        // MJOP-integratie: alleen Foundation (geen WebKit/ARKit), zodat navigatiebeleid, foutafhandeling en contracten op macOS testbaar zijn.
        .target(name: "MJOPIntegration"),
        // Gevelscanner 2.0: pijplijn foto's -> herkende elementen -> fysieke objecten -> geometrie -> inventaris (docs/gevelscanner_2.md).
        // Alleen Foundation; bouwt op de bestaande meetkern (PhotoWalkCore) en het MJOP-contract (MJOPIntegration). Geen tweede rekenkern.
        .target(name: "Gevelscan", dependencies: ["PhotoWalkCore", "MJOPIntegration"]),
        .testTarget(name: "GevelscanTests", dependencies: ["Gevelscan", "PhotoWalkCore", "MJOPIntegration"], resources: [.copy("Fixtures")]),
        .testTarget(name: "MJOPIntegrationTests", dependencies: ["MJOPIntegration"], resources: [.copy("Fixtures")]),
        .testTarget(name: "PhotoWalkCoreTests", dependencies: ["PhotoWalkCore"], resources: [.copy("Fixtures")]),
    ]
)
