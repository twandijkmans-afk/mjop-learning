import Foundation

/// Hoe het opgeslagen keyframe (native cameraoriëntatie) op het scherm staat.
/// `.right`: het native landscape-beeld wordt 90 graden met de klok mee gedraaid getoond (iPhone in portret, zoals ARKit `capturedImage`).
public enum DisplayOrientation { case up, right }

/// Zoom- en pan-toestand van een beeldweergave plus ALLE omrekening tussen scherm en originele beeldpixels.
///
/// Waarom dit bestaat: zoomen is uitsluitend een weergave-instelling. De meetkern rekent altijd met de originele pixelcoördinaten van het
/// keyframe (de intrinsics horen daarbij); deze struct is de enige plek waar een scherm-tik wordt teruggerekend naar die pixels.
/// Stelsels:
///  - NATIVE  : pixels van het opgeslagen keyframe, (u rechts, v omlaag), oorsprong linkerbovenhoek; hierin staan de hoeken/referenties.
///  - DISPLAY : pixels van het beeld zoals het rechtop wordt getoond (bij `.right`: x = H - v, y = u).
///  - VIEW    : punten in de weergave (UIKit-coördinaten, linksboven = 0,0).
/// `zoom` is relatief aan "passend in beeld" (1 = geheel beeld zichtbaar). Zoom heeft geen invloed op intrinsics, diepte of metrische uitkomst.
public struct ViewportTransform: Equatable {
    public static let minZoom = 1.0
    public static let maxZoom = 8.0

    public let nativeWidth: Double
    public let nativeHeight: Double
    public let orientation: DisplayOrientation
    public private(set) var viewportWidth: Double
    public private(set) var viewportHeight: Double
    public private(set) var zoom: Double = 1
    public private(set) var panX: Double = 0
    public private(set) var panY: Double = 0
    /// Hoeveel punten van het beeld buiten de rand van de weergave mogen schuiven, zodat randhoeken bereikbaar blijven.
    public let edgeMargin: Double

    public init(nativeWidth: Double, nativeHeight: Double, orientation: DisplayOrientation, viewportWidth: Double, viewportHeight: Double, edgeMargin: Double = 40) {
        precondition(nativeWidth > 0 && nativeHeight > 0 && viewportWidth > 0 && viewportHeight > 0)
        self.nativeWidth = nativeWidth; self.nativeHeight = nativeHeight; self.orientation = orientation
        self.viewportWidth = viewportWidth; self.viewportHeight = viewportHeight; self.edgeMargin = edgeMargin
    }

    // MARK: afmetingen
    public var displayWidth: Double { orientation == .right ? nativeHeight : nativeWidth }
    public var displayHeight: Double { orientation == .right ? nativeWidth : nativeHeight }
    /// Punten per displaypixel bij zoom 1.
    public var fitScale: Double { min(viewportWidth / displayWidth, viewportHeight / displayHeight) }
    /// Punten per displaypixel bij de huidige zoom.
    public var scale: Double { fitScale * zoom }
    /// Hoeveel native pixels één schermpunt beslaat: de pointing-precisie. Zoom 4x ⇒ 4x kleiner.
    public var nativePixelsPerPoint: Double { 1 / scale }
    public var contentWidth: Double { displayWidth * scale }
    public var contentHeight: Double { displayHeight * scale }
    public var contentOriginX: Double { (viewportWidth - contentWidth) / 2 + panX }
    public var contentOriginY: Double { (viewportHeight - contentHeight) / 2 + panY }

    // MARK: omrekening
    public func displayPoint(fromNative p: Pixel) -> Pixel {
        switch orientation {
        case .up: return p
        case .right: return Pixel(nativeHeight - p.v, p.u)
        }
    }

    public func nativePoint(fromDisplay d: Pixel) -> Pixel {
        switch orientation {
        case .up: return d
        case .right: return Pixel(d.v, nativeHeight - d.u)
        }
    }

    public func viewPoint(fromNative p: Pixel) -> Pixel {
        let d = displayPoint(fromNative: p)
        return Pixel(contentOriginX + d.u * scale, contentOriginY + d.v * scale)
    }

    /// Scherm -> originele beeldpixels (ongeklemd; gebruik `contains` om te controleren of het punt binnen het beeld valt).
    public func nativePoint(fromView v: Pixel) -> Pixel {
        nativePoint(fromDisplay: Pixel((v.u - contentOriginX) / scale, (v.v - contentOriginY) / scale))
    }

    public func contains(native p: Pixel) -> Bool { p.u >= 0 && p.v >= 0 && p.u <= nativeWidth && p.v <= nativeHeight }

    // MARK: mutaties
    public mutating func setViewport(width: Double, height: Double) {
        guard width > 0, height > 0 else { return }
        viewportWidth = width; viewportHeight = height
        clampPan()
    }

    /// Zoom met een factor rond een ankerpunt in de weergave (het beeldpunt onder het anker blijft onder het anker).
    public mutating func zoom(by factor: Double, anchor: Pixel) { setZoom(zoom * factor, anchor: anchor) }

    public mutating func setZoom(_ z: Double, anchor: Pixel) {
        guard z.isFinite else { return }
        let n = nativePoint(fromView: anchor)
        zoom = min(max(z, Self.minZoom), Self.maxZoom)
        let moved = viewPoint(fromNative: n)
        panX += anchor.u - moved.u; panY += anchor.v - moved.v
        clampPan()
    }

    public mutating func pan(byX dx: Double, y dy: Double) { panX += dx; panY += dy; clampPan() }

    public mutating func reset() { zoom = 1; panX = 0; panY = 0 }

    /// Zet de toestand rechtstreeks (voor animaties).
    public mutating func set(zoom z: Double, panX px: Double, panY py: Double) {
        zoom = min(max(z, Self.minZoom), Self.maxZoom); panX = px; panY = py; clampPan()
    }

    private mutating func clampPan() {
        let maxX = max(0, (contentWidth - viewportWidth) / 2 + (contentWidth > viewportWidth + 1e-6 ? edgeMargin : 0))
        let maxY = max(0, (contentHeight - viewportHeight) / 2 + (contentHeight > viewportHeight + 1e-6 ? edgeMargin : 0))
        panX = min(max(panX, -maxX), maxX); panY = min(max(panY, -maxY), maxY)
    }
}
