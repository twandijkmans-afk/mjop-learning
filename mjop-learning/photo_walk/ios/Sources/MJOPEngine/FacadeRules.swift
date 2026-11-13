import Foundation

/// Zichtbare gebreken op gevelfoto's als hint bij het beoordelen van een post. Nooit een score: die geeft de gebruiker.
public struct DefectHint: Equatable {
    public var sideId: Int
    public var defect: FacadeDefect
    /// Het element waar het gebrek op ligt, als dat te bepalen is.
    public var element: FacadePhotoElement?
}

public enum DefectHints {
    /// Bij welke posten een gebrek hoort. Eerst het element waar het op ligt; anders de soort gebrek.
    public static func keys(for d: FacadeDefect, on element: FacadePhotoElement?) -> [String] {
        if let e = element {
            switch e.type {
            case .kozijn_raam, .kozijn_deur, .garagedeur, .waterslag:
                return d.type == .afbladderende_verf || d.type == .houtrot ? ["kozijnen-onderhoud", "schilderwerk-buiten"] : ["kozijnen-onderhoud"]
            case .boeiboord, .luifel, .gevelbekleding: return ["schilderwerk-buiten"]
            case .hwa, .dakgoot: return ["dakgoten"]
            case .hekwerk, .balkon: return ["balkonhekken"]
            case .metselwerk, .stucwerk:
                return d.type == .voegwerk ? ["voegwerk", "gevel-metselwerk"] : ["gevel-metselwerk"]
            case .rooster, .overig: break
            }
        }
        switch d.type {
        case .afbladderende_verf, .houtrot: return ["schilderwerk-buiten", "kozijnen-onderhoud"]
        case .voegwerk: return ["voegwerk", "gevel-metselwerk"]
        case .scheur, .mos_algen, .vervuiling: return ["gevel-metselwerk"]
        case .roest: return ["balkonhekken"]
        case .losse_delen, .overig: return []
        }
    }

    /// Het kleinste element waar het punt van het gebrek in ligt (of een lijn vlakbij).
    public static func element(at p: [Double], in els: [FacadePhotoElement], tolerance: Double) -> FacadePhotoElement? {
        FacadeEdit.hit(els, at: p, tolerance: tolerance).flatMap { id in els.first { $0.id == id } }
    }

    /// Hints per postsleutel voor een reeks gescande gevels.
    public static func byKey(_ scans: [(sideId: Int, photoWidth: Double, elements: [FacadePhotoElement], defects: [FacadeDefect])]) -> [String: [DefectHint]] {
        var out: [String: [DefectHint]] = [:]
        for s in scans {
            for d in s.defects {
                let e = element(at: d.point, in: s.elements, tolerance: 0.02 * s.photoWidth)
                for k in keys(for: d, on: e) { out[k, default: []].append(DefectHint(sideId: s.sideId, defect: d, element: e)) }
            }
        }
        return out
    }
}

/// Een gevel die niet te fotograferen is, overnemen van een andere gevel: alleen na bevestiging, en alleen als de breedtes uit de BAG
/// binnen 15% van elkaar liggen. De uitkomst is een aanname (gelijk aan de bron, niet geschaald) en blijft zo gemarkeerd.
public enum FacadeCopy {
    public static let widthTolerance = 0.15
    public static func allowed(sourceWidthM: Double, targetWidthM: Double) -> Bool {
        sourceWidthM > 0 && targetWidthM > 0 && abs(targetWidthM - sourceWidthM) / sourceWidthM <= widthTolerance
    }
}
