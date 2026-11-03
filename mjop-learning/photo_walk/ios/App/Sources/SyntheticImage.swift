import UIKit
import PhotoWalkCore

/// Genereert een SYNTHETISCH testbeeld (geen foto): muur met bakstenen/voegen en een kozijn op de opgegeven hoeken, in de native afmeting van de camera.
/// Alleen voor de simulatiemodus en UI-tests; bevat geen persoonsgegevens en komt nooit uit een camera.
enum SyntheticImage {
    static func make(width: Int, height: Int, corners: [Pixel], id: String, sessionId: String) -> URL? {
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
            if corners.count == 4 {
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
