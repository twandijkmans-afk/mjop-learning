import Foundation
import MJOPEngine
import SwiftUI
import WidgetKit

/// Het volledige plan van een project (kolom `model` in `projects`, schema_version 1).
struct ProjectModel: Equatable {
    var building: BuildingInput
    var elements: [PlanElement]
    var fonds: Decimal?
    var bijdrage: Decimal?
    /// Gevelscans per gevelzijde (herkende elementen en maat); de foto zelf blijft voorlopig alleen op het toestel.
    var gevels: [FacadeScan] = []
    /// Gevelzijden uit de BAG-omtrek.
    var sides: [FacadeSide] = []
    /// Toegevoegde documenten met hun voorstellen (het bestand zelf blijft voorlopig alleen op het toestel).
    var documents: [ProjectDocument] = []
    /// Keuzes van de gebruiker in de kozijnstaat (samenvoegen, apart zetten).
    var kozijnOverrides: KozijnOverrides? = nil
    /// De BAG-omtrek als [lengtegraad, breedtegraad], voor de kaart in de gevelscan.
    var footprint: [[Double]]? = nil

    /// Kozijnen van alle gescande gevels gegroepeerd per type.
    var kozijnStaat: KozijnStaatResult { KozijnStaat.make(sideResults.flatMap(\.items), overrides: kozijnOverrides ?? KozijnOverrides()) }

    /// Zichtbare gebreken op de (eigen) gevelfoto's, per postsleutel, als hint bij het beoordelen.
    var defectHints: [String: [DefectHint]] {
        DefectHints.byKey(gevels.filter { $0.copiedFromSide == nil }.map { (sideId: $0.sideId, photoWidth: $0.photoWidth, elements: $0.elements, defects: $0.defects ?? []) })
    }

    /// Uitkomst per gevelzijde. Een lange gevel in meerdere foto's wordt aan elkaar gekoppeld via de kozijnen in de overlap.
    struct SideResult {
        var sideId: Int
        var parts: [FacadeScan]
        var summary: FacadePhoto.Summary?
        var items: [KozijnItem]
        var failure: String?
    }

    var sideResults: [SideResult] {
        let bySide = Dictionary(grouping: gevels, by: \.sideId)
        return bySide.keys.sorted().map { sid in
            let parts = bySide[sid]!.sorted { ($0.part ?? 1) < ($1.part ?? 1) }
            if parts.count == 1 { return SideResult(sideId: sid, parts: parts, summary: parts[0].summary, items: parts[0].kozijnItems, failure: nil) }
            var strip: [FacadeStrip.Part] = []
            for p in parts {
                guard let main = p.mainPlane, let r = FacadePerspective.rectify(p.elements, plane: main, widthM: 1, focalPx: p.focalPx, imageWidth: p.photoWidth, imageHeight: p.photoHeight) else {
                    return SideResult(sideId: sid, parts: parts, summary: nil, items: [], failure: "Op foto \(p.part ?? 1) zijn de hoeken van de gevel niet gevonden; zonder hoeken zijn de foto's niet te koppelen.")
                }
                strip.append(FacadeStrip.Part(elements: r.elements, overlap: p.overlapWithPrevious ?? 1))
            }
            switch FacadeStrip.stitch(strip, totalWidthM: parts[0].widthM) {
            case .success(let r):
                let items = r.elements.filter(\.type.isOpening).map { e -> KozijnItem in
                    let q = FacadePhoto.quantities(e, mpp: 1, all: [])
                    return KozijnItem(sideId: sid, elementId: e.id, type: e.type, material: e.material, widthM: q.widthM, heightM: q.heightM, hiddenFraction: e.hiddenFraction)
                }
                return SideResult(sideId: sid, parts: parts, summary: FacadePhoto.summary(r.elements, mpp: 1), items: items, failure: nil)
            case .failure(.noOverlap(let k)):
                return SideResult(sideId: sid, parts: parts, summary: nil, items: [], failure: "Foto \(k) heeft geen kozijn gemeen met foto \(k - 1); zonder overlap is de maat niet te bepalen.")
            case .failure(.mismatch(let k)):
                return SideResult(sideId: sid, parts: parts, summary: nil, items: [], failure: "De kozijnen in de overlap van foto \(k - 1) en \(k) passen niet bij elkaar. Controleer het aantal kozijnen in de overlap.")
            }
        }
    }

    static func parse(_ o: [String: Any]) -> ProjectModel? {
        let dec = JSONDecoder()
        guard let bObj = o["building"], let bData = try? JSONSerialization.data(withJSONObject: bObj),
              let building = try? dec.decode(BuildingInput.self, from: bData),
              let eObj = o["elements"], let eData = try? JSONSerialization.data(withJSONObject: eObj),
              let elements = try? dec.decode([PlanElement].self, from: eData) else { return nil }
        func decimal(_ k: String) -> Decimal? { (o[k] as? NSNumber).map { $0.decimalValue } }
        func decode<T: Decodable>(_ k: String, _ t: T.Type) -> T? {
            // Alleen echte objecten of lijsten: een lege waarde (null) laat JSONSerialization crashen (Objective-C-uitzondering, niet te vangen met try?).
            guard let v = o[k], !(v is NSNull), JSONSerialization.isValidJSONObject(v), let d = try? JSONSerialization.data(withJSONObject: v) else { return nil }
            return try? dec.decode(T.self, from: d)
        }
        return ProjectModel(building: building, elements: elements, fonds: decimal("fonds"), bijdrage: decimal("bijdrage"),
                            gevels: decode("gevels", [FacadeScan].self) ?? [], sides: decode("sides", [FacadeSide].self) ?? [],
                            documents: decode("documents", [ProjectDocument].self) ?? [], kozijnOverrides: decode("kozijn_overrides", KozijnOverrides.self), footprint: o["footprint"] as? [[Double]])
    }

    func json() -> [String: Any] {
        let enc = JSONEncoder()
        return [
            "building": (try? JSONSerialization.jsonObject(with: enc.encode(building))) ?? [:],
            "elements": (try? JSONSerialization.jsonObject(with: enc.encode(elements))) ?? [],
            "fonds": fonds.map { NSDecimalNumber(decimal: $0) } ?? NSNull(),
            "bijdrage": bijdrage.map { NSDecimalNumber(decimal: $0) } ?? NSNull(),
            "gevels": (try? JSONSerialization.jsonObject(with: enc.encode(gevels))) ?? [],
            "sides": (try? JSONSerialization.jsonObject(with: enc.encode(sides))) ?? [],
            "documents": (try? JSONSerialization.jsonObject(with: enc.encode(documents))) ?? [],
            "footprint": footprint ?? [],
            "kozijn_overrides": kozijnOverrides.flatMap { try? JSONSerialization.jsonObject(with: enc.encode($0)) } ?? [String: Any](),
        ]
    }

    static var year: Int { Calendar.current.component(.year, from: Date()) }

    var plan: [PlannedCost] { Engine.plan(elements, year: Self.year) }
    var perYear: [Int: Decimal] { Engine.perYear(plan) }
    var total: Decimal { plan.reduce(Decimal(0)) { $0 + $1.bedrag } }
    var beoordeeld: Int { elements.filter { $0.conditie != nil }.count }
    var peak: (jaar: Int, bedrag: Decimal)? { perYear.max { $0.value < $1.value }.map { ($0.key, $0.value) } }
    var units: Int { building.units }

    /// Fondsstand per jaar; alleen als saldo en bijdrage bekend zijn (anders zegt het niets).
    var fund: [FundYear]? {
        guard let fonds, let bijdrage else { return nil }
        return Engine.fund(fonds: fonds, bijdrage: bijdrage, units: units, perYear: perYear, year: Self.year)
    }
    var required: Int? { fonds.map { Engine.requiredContribution(fonds: $0, units: units, perYear: perYear, year: Self.year) } }

    /// Demo (alleen testbouw): Singelstraat 8 met de echte BAG- en 3D BAG-gegevens.
    static let demo: ProjectModel = {
        let b = BuildingInput(bouwjaar: 1925, units: 1, unitsBAG: 1, footprintM2: 51.42, omtrekM: 32.91, dakPlatM2: 6.3, dakSchuinM2: 61.56, buitenmuurM2: 114.02, hoogteM: 7.7)
        let sides = [FacadeSide(id: 1, lengthM: 8.49, facing: "noord"), FacadeSide(id: 2, lengthM: 2.88, facing: "west"), FacadeSide(id: 3, lengthM: 2.65, facing: "noord"),
                     FacadeSide(id: 4, lengthM: 2.4, facing: "west"), FacadeSide(id: 5, lengthM: 11.16, facing: "zuid"), FacadeSide(id: 6, lengthM: 5.32, facing: "oost")]
        return ProjectModel(building: b, elements: Engine.defaultElements(for: b, year: year), fonds: 5000, bijdrage: 155, sides: sides)
    }()
}

extension ProjectStore {
    func loadModel(_ project: Project, account: Account) async throws -> ProjectModel {
        if account.demo { ProjectModel.demo.updateWidget(for: project); return ProjectModel.demo }
        let s = try await account.validSession()
        let (data, http) = try await BackendClient(session: s).request("rest/v1/projects", query: [URLQueryItem(name: "id", value: "eq.\(project.id)"), URLQueryItem(name: "select", value: "model")])
        guard http.statusCode == 200, let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]], let m = rows.first?["model"] as? [String: Any] else {
            throw BackendError.message(BackendClient.message(data, status: http.statusCode))
        }
        guard let model = ProjectModel.parse(m) else { throw BackendError.message("Dit plan is gemaakt met een andere versie en kan nog niet worden geopend.") }
        if MaintenanceReminders.enabled { Task { await MaintenanceReminders.schedule(project: project, model: model) } }
        model.updateWidget(for: project)
        return model
    }

    /// Bewaart het plan en de samenvatting (aantal posten, beoordeeld, totaal) die de lijsten tonen.
    func saveModel(_ model: ProjectModel, for project: Project, account: Account) async throws {
        if account.demo { return }
        let s = try await account.validSession()
        let total = NSDecimalNumber(decimal: Engine.roundEuro(model.total)).intValue
        let body: [String: Any] = ["model": model.json(), "posten_aantal": model.elements.count, "posten_beoordeeld": model.beoordeeld,
                                   "geraamd_totaal": total, "aantal_appartementen": model.units]
        let (data, http) = try await BackendClient(session: s).request("rest/v1/projects", method: "PATCH", query: [URLQueryItem(name: "id", value: "eq.\(project.id)")], body: body)
        guard (200..<300).contains(http.statusCode) else { throw BackendError.message(BackendClient.message(data, status: http.statusCode)) }
        if MaintenanceReminders.enabled { await MaintenanceReminders.schedule(project: project, model: model) }
        model.updateWidget(for: project)
    }
}

extension ProjectModel {
    /// Zet de samenvatting voor de widget (laatst geopende project) en laat de widget opnieuw tekenen.
    func updateWidget(for project: Project) {
        let year = Self.year
        let low = fund?.min { $0.saldo < $1.saldo }
        let next = plan.filter { $0.jaar >= year }.map(\.jaar).min()
        let items = next.map { y in plan.filter { $0.jaar == y } } ?? []
        var names: [String] = []
        for i in items where !names.contains(i.naam) { names.append(i.naam) }
        func euro(_ d: Decimal) -> Int { NSDecimalNumber(decimal: Engine.roundEuro(d)).intValue }
        WidgetSnapshot(projectId: project.id, naam: project.naam, fondsNu: fonds.map(euro),
                       laagsteStand: low.map { euro($0.saldo) }, laagsteJaar: low?.jaar,
                       volgendJaar: next, volgendPosten: Array(names.prefix(3)),
                       volgendBedrag: next == nil ? nil : euro(items.reduce(Decimal(0)) { $0 + $1.bedrag }),
                       bijgewerkt: Date()).save()
        WidgetCenter.shared.reloadAllTimelines()
    }
}

/// Eén gescande gevel.
struct FacadeScan: Codable, Equatable, Identifiable {
    var id: Int { sideId * 100 + (part ?? 1) }
    /// Deel van een lange gevel (1, 2, 3 van links naar rechts) en hoeveel kozijnen dit deel deelt met het vorige.
    var part: Int? = nil
    var overlapWithPrevious: Int? = nil
    var sideId: Int
    var facing: String
    var widthM: Double
    var photoWidth: Double
    var photoHeight: Double
    var referenceLeftX: Double
    var referenceRightX: Double
    var elements: [FacadePhotoElement]
    var skipped: Int
    var model: String
    var promptVersion: String
    var scannedAt: Date
    /// Hoe de foto is genomen (eigen camera). Leeg bij een foto uit de fotobibliotheek.
    var lens: String? = nil
    var rollDeg: Double? = nil
    var pitchDeg: Double? = nil
    var levelAtCapture: Bool? = nil
    var focal35mm: Double? = nil
    /// Gevelvlakken en gebreken (prompt v0.2).
    var planes: [FacadePlane]? = nil
    var defects: [FacadeDefect]? = nil
    /// Dubbel herkende elementen die zijn samengevoegd, en paren die over elkaar liggen met een verschillende soort.
    var merged: Int? = nil
    /// Herkende elementen die de gebruiker heeft verwijderd (bewaard voor de controle).
    var removedByUser: [FacadePhotoElement]? = nil
    /// Overgenomen van een andere gevel (niet te fotograferen), met de datum van bevestiging door de gebruiker. Een aanname.
    var copiedFromSide: Int? = nil
    /// Pad van de foto in de cloud (bucket gevelfotos); nil = alleen op het toestel gebleven.
    var photoPath: String? = nil
    var copyConfirmedAt: Date? = nil
    var conflicts: [[Int]]? = nil

    var mpp: Double? { FacadePhoto.metersPerPixel(facadeWidthM: widthM, leftX: referenceLeftX, rightX: referenceRightX) }
    /// Het vlak waar de BAG-gevelbreedte bij hoort.
    var mainPlane: FacadePlane? { planes?.first { $0.kind == .hoofdgevel } ?? planes?.first }
    var focalPx: Double? { focal35mm.flatMap { FacadePerspective.focalPx(focal35mm: $0, width: photoWidth, height: photoHeight) } }
    /// Breedte van een vlak en waar die vandaan komt: het hoofdvlak krijgt de BAG-breedte, een ander vlak alleen een eigen maat.
    func width(of p: FacadePlane) -> (m: Double, source: PlaneWidthSource)? {
        if p.id == mainPlane?.id { return (widthM, .bag) }
        if let w = p.widthM, let s = p.widthSource, w > 0 { return (w, s) }
        return nil
    }
    func rectify(_ p: FacadePlane) -> FacadePerspective.Rectified? {
        guard let w = width(of: p) else { return nil }
        return FacadePerspective.rectify(elements, plane: p, widthM: w.m, focalPx: focalPx, imageWidth: photoWidth, imageHeight: photoHeight,
                                         includeUnassigned: p.id == mainPlane?.id)
    }
    /// Rechtgetrokken hoofdvlak; nil zonder bruikbare hoeken (dan de oude methode: breedte over de foto).
    var rectified: FacadePerspective.Rectified? { mainPlane.flatMap(rectify) }

    /// Totalen per soort element over de vlakken met maat (of de hele foto bij een scan zonder vlakken).
    var elementTotals: [FacadePhoto.ElementTotal] {
        guard rectified != nil else { return FacadePhoto.totals(elements, mpp: mpp) }
        let parts = (planes ?? []).compactMap(rectify).flatMap { FacadePhoto.totals($0.elements, mpp: 1) }
        return FacadeElementType.allCases.compactMap { t in
            let sel = parts.filter { $0.type == t }
            guard !sel.isEmpty else { return nil }
            func add(_ f: (FacadePhoto.ElementTotal) -> Double?) -> Double? {
                var v = 0.0
                for x in sel { guard let y = f(x) else { return nil }; v += y }
                return FacadePhoto.round2(v)
            }
            return FacadePhoto.ElementTotal(type: t, count: sel.reduce(0) { $0 + $1.count },
                                            lengthM: t.kind == .line ? add(\.lengthM) : nil, areaM2: t.kind == .line ? nil : add(\.areaM2))
        }
    }

    /// Elementen die buiten de gevel vallen (zijgevel, buurpand) en daarom niet meetellen.
    var outsideCount: Int { (planes ?? []).compactMap(rectify).reduce(0) { $0 + $1.outside } }
    /// Vlakken met elementen maar zonder maat: die tellen (nog) niet mee.
    var unmeasuredPlanes: [FacadePlane] {
        (planes ?? []).filter { p in width(of: p) == nil && elements.contains { $0.plane == p.id } }
    }
    func doorWidth(_ p: FacadePlane) -> Double? {
        FacadePerspective.planeWidthFromDoor(elements, plane: p, focalPx: focalPx, imageWidth: photoWidth, imageHeight: photoHeight)
    }
    /// Kozijnen op deze gevel met hun maat, voor de kozijnstaat. Elementen op een vlak zonder maat doen niet mee.
    var kozijnItems: [KozijnItem] {
        func item(_ e: FacadePhotoElement, _ mpp: Double?) -> KozijnItem {
            let q = FacadePhoto.quantities(e, mpp: mpp, all: [])
            return KozijnItem(sideId: sideId, elementId: e.id, type: e.type, material: e.material, widthM: q.widthM, heightM: q.heightM, hiddenFraction: e.hiddenFraction)
        }
        if rectified != nil {
            return (planes ?? []).compactMap(rectify).flatMap { r in r.elements.filter(\.type.isOpening).map { item($0, 1) } }
        }
        return elements.filter(\.type.isOpening).map { item($0, mpp) }
    }

    /// Relatieve bandbreedte van de maten op deze gevel (vaste regels in MeasureBand); de zwakste maatbron van de meegetelde vlakken telt.
    var bandRelative: Double {
        let sources = (planes ?? []).compactMap { width(of: $0)?.source }
        let worst = sources.max { MeasureBand.relative(.init(widthSource: $0, levelAtCapture: nil, focalSource: nil, rectified: true)) < MeasureBand.relative(.init(widthSource: $1, levelAtCapture: nil, focalSource: nil, rectified: true)) }
        let r = rectified
        return MeasureBand.relative(.init(widthSource: worst ?? .bag, levelAtCapture: levelAtCapture, focalSource: r?.focalSource, rectified: r != nil))
    }

    /// Hoogte van de eerste deur op het hoofdvlak, als controlemaat.
    var doorHeightM: Double? {
        if let r = rectified {
            return r.elements.first { $0.type == .kozijn_deur }.flatMap { FacadePhoto.quantities($0, mpp: 1, all: []).heightM }
        }
        return elements.first { $0.type == .kozijn_deur }.flatMap { FacadePhoto.quantities($0, mpp: mpp, all: []).heightM }
    }

    var summary: FacadePhoto.Summary {
        if rectified != nil {
            return FacadePhoto.combine((planes ?? []).compactMap(rectify).map { FacadePhoto.summary($0.elements, mpp: 1) })
        }
        return FacadePhoto.summary(elements, mpp: mpp)
    }
}
