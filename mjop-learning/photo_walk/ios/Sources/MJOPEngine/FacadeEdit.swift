import Foundation

/// Aanpassingen van de gebruiker aan herkende elementen. De oorspronkelijke herkenning blijft altijd bewaard:
/// bij een wijziging in `originalType`/`originalPoints`, bij verwijderen in de lijst `removed`.
public enum FacadeEdit {
    static func markEdited(_ e: inout FacadePhotoElement) {
        guard e.addedByUser != true, e.editedByUser != true else { return }
        e.originalType = e.type
        e.originalPoints = e.points
        e.editedByUser = true
    }

    /// Ander soort element, alleen binnen dezelfde vorm (kader, lijn of vlak); anders gebeurt er niets.
    @discardableResult
    public static func retype(_ els: inout [FacadePhotoElement], id: Int, to t: FacadeElementType) -> Bool {
        guard let i = els.firstIndex(where: { $0.id == id }), els[i].type != t, els[i].type.kind == t.kind else { return false }
        markEdited(&els[i])
        els[i].type = t
        return true
    }

    /// Verschuift een element binnen de foto.
    public static func move(_ els: inout [FacadePhotoElement], id: Int, dx: Double, dy: Double, width W: Double, height H: Double) {
        guard let i = els.firstIndex(where: { $0.id == id }), dx != 0 || dy != 0 else { return }
        let xs = els[i].points.map { $0[0] }, ys = els[i].points.map { $0[1] }
        let cdx = min(max(dx, -(xs.min() ?? 0)), W - (xs.max() ?? W))
        let cdy = min(max(dy, -(ys.min() ?? 0)), H - (ys.max() ?? H))
        markEdited(&els[i])
        els[i].points = els[i].points.map { [$0[0] + cdx, $0[1] + cdy] }
    }

    /// Verwijdert een element; het gaat naar `removed`, zodat te zien blijft wat de herkenning had gevonden.
    public static func delete(_ els: inout [FacadePhotoElement], removed: inout [FacadePhotoElement], id: Int) {
        guard let i = els.firstIndex(where: { $0.id == id }) else { return }
        let e = els.remove(at: i)
        if e.addedByUser != true { removed.append(e) }
    }

    /// Nieuw element, getekend door de gebruiker: een kader (twee hoekpunten) of een lijn (begin en eind). Te klein: niets.
    @discardableResult
    public static func add(_ els: inout [FacadePhotoElement], type t: FacadeElementType, from a: [Double], to b: [Double], plane: Int?, takenIds: Set<Int> = []) -> Int? {
        let pts: [[Double]]
        switch t.kind {
        case .quad:
            pts = FacadePhoto.boxToQuad(a, b)
            guard FacadePhoto.area(pts) >= 16 else { return nil }
        case .line:
            pts = [a, b]
            guard FacadePhoto.length(pts) >= 4 else { return nil }
        case .poly:
            pts = FacadePhoto.boxToQuad(a, b)
            guard FacadePhoto.area(pts) >= 16 else { return nil }
        }
        let id = (els.map(\.id) + Array(takenIds)).max().map { $0 + 1 } ?? 1
        var e = FacadePhotoElement(id: id, type: t, points: pts, material: nil, confidence: nil, note: nil, plane: plane)
        e.addedByUser = true
        els.append(e)
        return id
    }

    /// Het element onder een punt: het kleinste kader of vlak waar het punt in ligt, anders een lijn binnen `tolerance` pixels.
    public static func hit(_ els: [FacadePhotoElement], at p: [Double], tolerance: Double) -> Int? {
        let areas = els.filter { $0.type.kind != .line && FacadePhoto.inside(p, $0.points) }.min { FacadePhoto.area($0.points) < FacadePhoto.area($1.points) }
        if let a = areas, a.type.kind == .quad { return a.id }
        func segDist(_ p: [Double], _ a: [Double], _ b: [Double]) -> Double {
            let dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy
            let t = l2 == 0 ? 0 : max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
            return hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
        }
        let line = els.filter { $0.type.kind == .line }.map { e in (e.id, (1..<e.points.count).map { segDist(p, e.points[$0 - 1], e.points[$0]) }.min() ?? .infinity) }
            .filter { $0.1 <= tolerance }.min { $0.1 < $1.1 }
        return line?.0 ?? areas?.id
    }
}
