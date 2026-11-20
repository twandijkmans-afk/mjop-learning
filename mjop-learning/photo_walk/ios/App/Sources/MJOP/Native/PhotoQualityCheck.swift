import MJOPEngine
import UIKit

/// Maakt een klein grijsbeeld van de foto (ongeveer 512 pixels breed, rechtop) en laat de rekenkern de kwaliteit beoordelen.
enum PhotoQualityCheck {
    static func issues(_ image: UIImage) -> [PhotoIssue] {
        guard image.size.width > 0, image.size.height > 0 else { return [] }
        let w = 512, h = max(8, Int((512 * image.size.height / image.size.width).rounded()))
        var buf = [UInt8](repeating: 0, count: w * h)
        let ok: Bool = buf.withUnsafeMutableBytes { raw -> Bool in
            guard let ctx = CGContext(data: raw.baseAddress, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w,
                                      space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return false }
            ctx.translateBy(x: 0, y: CGFloat(h)); ctx.scaleBy(x: 1, y: -1)   // UIKit-tekenen: oorsprong linksboven
            UIGraphicsPushContext(ctx)
            image.draw(in: CGRect(x: 0, y: 0, width: w, height: h))
            UIGraphicsPopContext()
            return true
        }
        return ok ? PhotoQuality.assess(gray: buf, width: w, height: h) : []
    }
}
