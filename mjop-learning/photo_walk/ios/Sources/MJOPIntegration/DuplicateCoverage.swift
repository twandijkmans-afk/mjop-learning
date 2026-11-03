import Foundation

/// Is de controle op dubbel getelde kozijnen VOLLEDIG? Python-referentie: photo_walk/python/photo_walk_core/duplicate_coverage.py
/// (pariteit via Tests/MJOPIntegrationTests/Fixtures/duplicate_coverage_cases.json).
///
/// Nul koppelsuggesties is GEEN bewijs dat er geen duplicaten zijn. De automatische suggesties (ScanStore.linkSuggestions) vergelijken alleen
/// waarnemingen met een ruimtelijke meting (3D-hoeken + vlak) binnen één AR-sessie (coördinatenstelsel). Wat daarbuiten valt, is NIET
/// gecontroleerd en telt dus niet als "geen duplicaat":
/// * een object zonder bruikbare geometrie (geen LiDAR-vlak, alleen referentiemaat, geen schaal) terwijl er andere objecten zijn;
/// * een foto zonder bekende AR-sessie (worldId) terwijl de objecten op twee of meer foto's staan;
/// * foto's uit meer dan één AR-sessie (elke nieuwe camerastart is een nieuwe sessie; posities zijn dan niet vergelijkbaar).
///
/// Bereik. Voor een GEVEL tellen alleen de foto's en objecten van die gevel: een gevelvoorstel telt de kozijnen die op die gevel zijn
/// vastgelegd, dus een kozijn dat óók bij een andere gevel staat, is binnen deze gevel geen duplicaat (dat raakt alleen de optelsom).
/// Voor het GEBOUW (som van alle gevels) tellen alle foto's met objecten samen: twee gevels met elk één, maar verschillende AR-sessie
/// zijn onderling NIET gecontroleerd.
///
/// Handmatige controle. De inspecteur kan verklaren dat hij alle foto's heeft nagelopen ("geen kozijn dubbel geteld"). Die verklaring geldt
/// alleen zolang foto's, waarnemingen, koppelingen en uitsluitingen gelijk blijven (vingerafdruk). Openstaande koppelsuggesties moeten
/// altijd afzonderlijk worden beoordeeld (koppelen of negeren); de verklaring vervangt die niet.
public enum DuplicateCoverage {
    public struct Result: Equatable {
        /// Foto's uit meer dan één AR-sessie, niet handmatig nagelopen.
        public var crossSessionUnchecked: Bool
        /// Objecten die niet automatisch vergeleken konden worden (diagnose; ook na handmatige controle zichtbaar).
        public var uncheckedObjects: Int
        /// Foto's met objecten zonder bekende AR-sessie (diagnose).
        public var unknownWorldPhotos: Int
        /// Niet-vergelijkbare objecten of foto's zonder sessie, niet handmatig nagelopen.
        public var checkIncomplete: Bool
        /// De dekking komt (deels) uit de handmatige verklaring van de inspecteur.
        public var manual: Bool
        /// Geen openstaande suggesties en geen ongecontroleerde delen: alleen dan mag er een hoeveelheid zijn.
        public var complete: Bool
    }

    /// - objects: de meetellende objecten in dit bereik (gevel of gebouw).
    /// - facadeWorldIds: AR-sessies per gevel in dit bereik (alle niet-uitgesloten foto's van die gevel; bestaande regel per gevel).
    /// - frameWorld: foto -> AR-sessie. nil = onbekend voor alle foto's in deze invoer (oude invoer zonder deze gegevens: alleen de
    ///   bestaande gevelregel geldt). Een foto die ontbreekt in de tabel heeft een ONBEKENDE sessie.
    /// - duplicatesUnresolved: openstaande koppelsuggesties in dit bereik.
    /// - reviewed: geldige handmatige verklaring (vingerafdruk klopt).
    public static func evaluate(objects: [RoundObject], facadeWorldIds: [Set<String>], frameWorld: [String: String]?, duplicatesUnresolved: Int,
                                reviewed: Bool) -> Result {
        let photos = Array(Set(objects.flatMap { $0.frameIds })).sorted()
        var autoCrossSession = facadeWorldIds.contains { $0.count > 1 }
        var unknownWorldPhotos = 0
        if let fw = frameWorld {
            let worlds = Set(photos.compactMap { fw[$0] })
            if worlds.count > 1 { autoCrossSession = true }
            unknownWorldPhotos = photos.filter { fw[$0] == nil }.count
        }
        let worldUnknown = unknownWorldPhotos > 0 && photos.count >= 2
        let uncheckedObjects = objects.count >= 2 ? objects.filter { !$0.duplicateCheckable }.count : 0
        let gaps = autoCrossSession || worldUnknown || uncheckedObjects > 0
        let crossSessionUnchecked = autoCrossSession && !reviewed
        let checkIncomplete = (worldUnknown || uncheckedObjects > 0) && !reviewed
        return Result(crossSessionUnchecked: crossSessionUnchecked, uncheckedObjects: uncheckedObjects, unknownWorldPhotos: unknownWorldPhotos,
                      checkIncomplete: checkIncomplete, manual: reviewed && gaps,
                      complete: duplicatesUnresolved == 0 && !crossSessionUnchecked && !checkIncomplete)
    }

    /// Stabiele vingerafdruk (FNV-1a 64 bit, hex) van de toestand waarop een handmatige controle betrekking heeft. Verandert er iets aan de
    /// meetellende foto's, waarnemingen, koppelingen of uitsluitingen, dan verandert de vingerafdruk en vervalt de verklaring.
    public static func fingerprint(_ parts: [String]) -> String {
        var h: UInt64 = 0xcbf29ce484222325
        for byte in parts.sorted().joined(separator: "\n").utf8 { h ^= UInt64(byte); h = h &* 0x100000001b3 }
        return String(format: "%016llx", h)
    }
}
