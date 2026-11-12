// swift-tools-version:5.9
// PhotoWalkCore: platformonafhankelijke Swift-port van de meetkern (geen ARKit). De ARKit-app staat in App/.
// STATUS: wordt door GitHub Actions op macOS gebouwd en getest (photo-walk-ios.yml). Zie ../README.md.
import PackageDescription

let package = Package(
    name: "PhotoWalkCore",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "PhotoWalkCore", targets: ["PhotoWalkCore"]),
        .library(name: "MJOPIntegration", targets: ["MJOPIntegration"]),
        .library(name: "Gevelscan", targets: ["Gevelscan"]),
        .library(name: "MJOPEngine", targets: ["MJOPEngine"]),
    ],
    targets: [
        .target(name: "PhotoWalkCore"),
        // MJOP-integratie: alleen Foundation (geen WebKit/ARKit), zodat navigatiebeleid, foutafhandeling en contracten op macOS testbaar zijn.
        .target(name: "MJOPIntegration"),
        // Gevelscanner 2.0: pijplijn foto's -> herkende elementen -> fysieke objecten -> geometrie -> inventaris (docs/gevelscanner_2.md).
        // Alleen Foundation; bouwt op de bestaande meetkern (PhotoWalkCore) en het MJOP-contract (MJOPIntegration). Geen tweede rekenkern.
        .target(name: "Gevelscan", dependencies: ["PhotoWalkCore", "MJOPIntegration"]),
        // MJOP Live 3: het rekenmodel (posten, kosten, planning, reservefonds), overgezet uit de website. Alleen Foundation, geld als Decimal.
        .target(name: "MJOPEngine"),
        .testTarget(name: "MJOPEngineTests", dependencies: ["MJOPEngine"], exclude: ["make_fixtures.js"], resources: [.copy("Fixtures")]),
        .testTarget(name: "GevelscanTests", dependencies: ["Gevelscan", "PhotoWalkCore", "MJOPIntegration"], resources: [.copy("Fixtures")]),
        .testTarget(name: "MJOPIntegrationTests", dependencies: ["MJOPIntegration"], resources: [.copy("Fixtures")]),
        .testTarget(name: "PhotoWalkCoreTests", dependencies: ["PhotoWalkCore"], resources: [.copy("Fixtures")]),
    ]
)
