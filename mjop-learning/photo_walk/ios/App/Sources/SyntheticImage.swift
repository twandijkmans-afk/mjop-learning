import UIKit
import PhotoWalkCore

/// Genereert een SYNTHETISCH testbeeld (geen foto): muur met bakstenen/voegen en een kozijn op de opgegeven hoeken, in de native afmeting van de camera.
/// Alleen voor de simulatiemodus en UI-tests; bevat geen persoonsgegevens en komt nooit uit een camera.
enum SyntheticImage {
    /// framed = true: realistischer kozijn: wit profiel tot precies op de buitencontour (`corners`), daarbinnen twee glasvlakken met een tussenstijl.
    /// Zo ligt de rand glas/kozijn BINNEN de buitenmaat, zoals bij een echt kozijn (test voor buitencontour versus glas).
    static func make(width: Int, height: Int, corners: [Pixel], id: String, sessionId: String, framed: Bool = false) -> URL? {
        let size = CGSize(width: width, height: height)
        let fmt = UIGraphicsImageRendererFormat(); fmt.scale = 1; fmt.opaque = true
        let img = UIGraphicsImageRenderer(size: size, format: fmt).image { rc in
            let ctx = rc.cgContext
            UIColor(red: 0.74, green: 0.45, blue: 0.36, alpha: 1).setFill(); ctx.fill(CGRect(origin: .zero, size: size))
            UIColor(white: 0.9, alpha: 1).setStroke(); ctx.setLineWidth(2)
            var y: CGFloat = 0, row = 0
            while y < size.height { ctx.move(to: CGPoint(x: 0, y: y)); ctx.addLine(to: CGPoint(x: size.width, y: y))
                var x: CGFloat = row % 2 == 0 ? 0 : 30; while x < size.width { ctx.move(to: CGPoint(x: x, y: y)); ctx.addLine(to: CGPoint(x: x, y: min(y + 24, size.height))); x += 60 }
                y += 24; row += 1 }
            ctx.strokePath()
            if corners.count == 4 && framed {
                func poly(_ q: [Pixel]) -> UIBezierPath {
                    let p = UIBezierPath(); p.move(to: CGPoint(x: q[0].u, y: q[0].v)); for c in q.dropFirst() { p.addLine(to: CGPoint(x: c.u, y: c.v)) }; p.close(); return p
                }
                UIColor(white: 0.93, alpha: 1).setFill(); poly(corners).fill()                       // kozijnprofiel tot de buitenrand
                let glass = scalePolygon(corners, 0.84)
                UIColor(red: 0.16, green: 0.22, blue: 0.3, alpha: 1).setFill(); poly(glass).fill()   // glas
                let top = Pixel((glass[0].u + glass[1].u) / 2, (glass[0].v + glass[1].v) / 2), bottom = Pixel((glass[3].u + glass[2].u) / 2, (glass[3].v + glass[2].v) / 2)
                let bar = UIBezierPath(); bar.move(to: CGPoint(x: top.u, y: top.v)); bar.addLine(to: CGPoint(x: bottom.u, y: bottom.v))
                bar.lineWidth = CGFloat(max(4, hypot(corners[1].u - corners[0].u, corners[1].v - corners[0].v) * 0.05)); UIColor(white: 0.93, alpha: 1).setStroke(); bar.stroke()   // tussenstijl
            } else if corners.count == 4 {
                let path = UIBezierPath(); path.move(to: CGPoint(x: corners[0].u, y: corners[0].v))
                for c in corners.dropFirst() { path.addLine(to: CGPoint(x: c.u, y: c.v)) }; path.close()
                UIColor(red: 0.2, green: 0.3, blue: 0.4, alpha: 1).setFill(); path.fill()
                UIColor.white.setStroke(); path.lineWidth = 14; path.stroke()
            }
        }
        guard let data = img.jpegData(compressionQuality: 0.9), let dir = Persistence.sessionDir(sessionId) else { return nil }
        let url = dir.appendingPathComponent("\(id).jpg")
        return (try? data.write(to: url)) != nil ? url : nil
    }
}
