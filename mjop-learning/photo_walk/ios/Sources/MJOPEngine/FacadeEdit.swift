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

    /// Alle elementen onder een punt, kleinste eerst (kaders, dan lijnen binnen de tolerantie, muren als laatste).
    /// Herhaald tikken op dezelfde plek loopt zo door overlappende elementen heen.
    public static func candidates(_ els: [FacadePhotoElement], at p: [Double], tolerance: Double) -> [Int] {
        func segDist(_ a: [Double], _ b: [Double]) -> Double {
            let dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy
            let t = l2 == 0 ? 0 : max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
            return hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
        }
        let quads = els.filter { $0.type.kind == .quad && $0.points.count >= 3 && FacadePhoto.inside(p, $0.points) }
            .sorted { FacadePhoto.area($0.points) < FacadePhoto.area($1.points) }.map(\.id)
        let lines = els.filter { $0.type.kind == .line && $0.points.count >= 2 }
            .map { e in (e.id, (1..<e.points.count).map { segDist(e.points[$0 - 1], e.points[$0]) }.min() ?? .infinity) }
            .filter { $0.1 <= tolerance }.sorted { $0.1 < $1.1 }.map(\.0)
        let walls = els.filter { $0.type.kind == .poly && $0.points.count >= 3 && FacadePhoto.inside(p, $0.points) }
            .sorted { FacadePhoto.area($0.points) < FacadePhoto.area($1.points) }.map(\.id)
        return quads + lines + walls
    }

    /// Volgende keuze bij tikken: het eerste element onder het punt, of het volgende na het al gekozen element.
    public static func nextSelection(_ els: [FacadePhotoElement], at p: [Double], tolerance: Double, current: Int?) -> Int? {
        let c = candidates(els, at: p, tolerance: tolerance)
        guard !c.isEmpty else { return nil }
        if let cur = current, let i = c.firstIndex(of: cur) { return c[(i + 1) % c.count] }
        return c[0]
    }

    /// Verplaatst één hoekpunt (kader, vlak) of eindpunt (lijn), binnen de foto.
    public static func moveVertex(_ els: inout [FacadePhotoElement], id: Int, index: Int, to p: [Double], width W: Double, height H: Double) {
        guard let i = els.firstIndex(where: { $0.id == id }), els[i].points.indices.contains(index) else { return }
        markEdited(&els[i])
        els[i].points[index] = [min(max(p[0], 0), W), min(max(p[1], 0), H)]
    }

    /// Trekt een lijn (bijv. een hemelwaterafvoer achter planten) door tot een rand: het bovenste of onderste eindpunt
    /// schuift in de richting van de lijn tot waar die de rand (twee punten, bijv. de bovenrand van het gevelvlak) snijdt.
    /// Lukt dat niet (evenwijdig, of de rand ligt aan de verkeerde kant), dan verandert er niets.
    @discardableResult
    public static func extendLine(_ els: inout [FacadePhotoElement], id: Int, to edge: [[Double]], upward: Bool, width W: Double, height H: Double) -> Bool {
        guard let i = els.firstIndex(where: { $0.id == id }), els[i].type.kind == .line, els[i].points.count >= 2, edge.count == 2 else { return false }
        var pts = els[i].points
        // Het eindpunt aan de gevraagde kant en zijn buurpunt geven de richting.
        let topFirst = pts[0][1] <= pts[pts.count - 1][1]
        let endIdx = (upward == topFirst) ? 0 : pts.count - 1
        let nbIdx = endIdx == 0 ? 1 : pts.count - 2
        let e = pts[endIdx], n = pts[nbIdx]
        let d = [e[0] - n[0], e[1] - n[1]], f = [edge[1][0] - edge[0][0], edge[1][1] - edge[0][1]]
        let den = d[0] * f[1] - d[1] * f[0]
        guard abs(den) > 1e-9 else { return false }
        let t = ((edge[0][0] - e[0]) * f[1] - (edge[0][1] - e[1]) * f[0]) / den
        guard t > 0 else { return false }   // de rand ligt niet verder in deze richting
        let q = [min(max(e[0] + t * d[0], 0), W), min(max(e[1] + t * d[1], 0), H)]
        markEdited(&els[i])
        pts[endIdx] = q
        els[i].points = pts
        return true
    }
}
