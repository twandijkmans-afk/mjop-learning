import PhotoWalkCore

/// Gebruikersadvies "beweeg meer" (ook in Release). Identiek aan de eerdere `DiagnosticsView.needsMotion`: alleen verplaatst zodat het scherm Meetdiagnose
/// (alleen Debug) niet nodig is voor een gebruikersfunctie. Verandert geen meetresultaat, vlag of drempel.
enum MotionAdvice {
    /// Behoefte aan meer beweging: te weinig onafhankelijke frames of een kozijnvlak dat daardoor niet bepaald kon worden.
    static func needsMotion(_ r: LevelResult) -> Bool {
        let codes = Set(r.flags.map { $0.code })
        return r.independentFrames < 2 && r.level == .A || !codes.isDisjoint(with: ["FRAME_PLANE_UNDETERMINED", "FRAME_OFFSET_FROM_CORNER_DEPTH", "FRAMES_INCONSISTENT", "DEPTH_COVERAGE_LOW", "LIMITED_SIDE_COVERAGE"])
    }
}
