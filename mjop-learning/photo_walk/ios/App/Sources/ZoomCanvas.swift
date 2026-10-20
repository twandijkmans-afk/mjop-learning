import SwiftUI
import UIKit
import PhotoWalkCore

/// Verbinding tussen de SwiftUI-bediening (knoppen, slider) en de UIKit-canvas.
final class CanvasController: ObservableObject {
    @Published var zoom: Double = 1
    @Published var nativePerPoint: Double = 1
    fileprivate weak var canvas: ZoomCanvasView?
    func setZoom(_ z: Double, animated: Bool) { canvas?.setZoom(z, animated: animated) }
    func resetView() { canvas?.resetView(animated: true) }
}

/// Een kader op de foto (kandidaat-kozijn). De kleur is UITSLUITEND UI-feedback en geen goedkeuring.
struct BoxOverlayItem: Equatable {
    var id: String
    var corners: [Pixel]           // NATIVE pixels, TL, TR, BR, BL
    var feedback: BoxFeedback
    var label: String
    var selected = false
}

func polygonContains(_ poly: [Pixel], _ p: Pixel) -> Bool {
    var inside = false
    var j = poly.count - 1
    for i in 0..<poly.count {
        let a = poly[i], b = poly[j]
        if (a.v > p.v) != (b.v > p.v), p.u < (b.u - a.u) * (p.v - a.v) / (b.v - a.v) + a.u { inside.toggle() }
        j = i
    }
    return inside
}

/// Inzoombare, verschuifbare keyframe-weergave met nauwkeurige puntselectie.
///
/// Alle posities die naar buiten gaan zijn ORIGINELE pixels van het keyframe (native oriëntatie); de omrekening zit uitsluitend in
/// `ViewportTransform` (PhotoWalkCore, getest). Zoom/pan is alleen weergave: intrinsics, diepte en meetkern zijn onaangetast.
/// Bediening: pinch = zoom rond de vingers, één vinger slepen = beeld verschuiven (of een bestaand punt verslepen als je er dichtbij begint),
/// tik = punt plaatsen, dubbel tikken = zoom resetten. Tijdens het slepen/plaatsen toont een vergrootglas de omgeving van het punt.
final class ZoomCanvasView: UIView, UIGestureRecognizerDelegate {
    private(set) var vp: ViewportTransform
    private let imageView = UIImageView()
    private let markers = MarkerOverlayView()
    private let loupe = LoupeView(frame: CGRect(x: 0, y: 0, width: 128, height: 128))
    private var dragIndex: Int?
    private var link: CADisplayLink?
    private var animStart: ViewportTransform?
    private var animTarget: ViewportTransform?
    private var animT0: CFTimeInterval = 0
    private var loupeHideWork: DispatchWorkItem?
    private let impact = UIImpactFeedbackGenerator(style: .medium)
    private let select = UISelectionFeedbackGenerator()

    var boxMode = false                                  // true: tikken selecteert een kader i.p.v. een punt te plaatsen
    var boxes: [BoxOverlayItem] = [] { didSet { markers.boxes = boxes; markers.setNeedsDisplay() } }
    var onBoxTap: ((String) -> Void)?
    var fitOnFirstLayout: [Pixel]?                       // eenmalig inzoomen op een kozijn (detailweergave)
    private var didInitialFit = false
    var maxPoints = 4
    var points: [Pixel] = [] { didSet { markers.points = points; markers.setNeedsDisplay() } }
    var overlay: [Pixel] = [] { didSet { markers.overlay = overlay; markers.setNeedsDisplay() } }
    var onPointsChanged: (([Pixel]) -> Void)?
    var onViewChanged: ((ViewportTransform) -> Void)?

    init(image: UIImage, nativeWidth: Double, nativeHeight: Double) {
        vp = ViewportTransform(nativeWidth: nativeWidth, nativeHeight: nativeHeight, orientation: .right, viewportWidth: 100, viewportHeight: 100)
        super.init(frame: .zero)
        backgroundColor = .black
        clipsToBounds = true
        let cg = image.cgImage!
        imageView.image = UIImage(cgImage: cg, scale: 1, orientation: .right)      // native landscape -> rechtop getoond
        imageView.contentMode = .scaleToFill
        addSubview(imageView)
        markers.isUserInteractionEnabled = false; markers.backgroundColor = .clear
        addSubview(markers)
        loupe.isUserInteractionEnabled = false; loupe.isHidden = true; loupe.source = imageView
        addSubview(loupe)
        isAccessibilityElement = true
        accessibilityIdentifier = "frameCanvas"
        accessibilityLabel = "Keyframe. Pinch om te zoomen, tik om een punt te plaatsen, sleep een punt om bij te stellen, dubbel tikken om te resetten."

        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(handlePinch(_:)))
        let pan = UIPanGestureRecognizer(target: self, action: #selector(handlePan(_:)))
        pan.maximumNumberOfTouches = 2
        let doubleTap = UITapGestureRecognizer(target: self, action: #selector(handleDoubleTap(_:)))
        doubleTap.numberOfTapsRequired = 2
        let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap(_:)))
        tap.require(toFail: doubleTap)
        for g in [pinch, pan, doubleTap, tap] as [UIGestureRecognizer] { g.delegate = self; addGestureRecognizer(g) }
    }
    required init?(coder: NSCoder) { fatalError("niet gebruikt") }

    deinit { link?.invalidate() }
    override func willMove(toWindow newWindow: UIWindow?) { if newWindow == nil { stopAnimation() } }

    override func layoutSubviews() {
        super.layoutSubviews()
        guard bounds.width > 1, bounds.height > 1 else { return }
        vp.setViewport(width: Double(bounds.width), height: Double(bounds.height))
        if let f = fitOnFirstLayout, !didInitialFit { vp.fit(native: f); didInitialFit = true }
        markers.frame = bounds
        apply()
    }

    func gestureRecognizer(_ g: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith o: UIGestureRecognizer) -> Bool {
        (g is UIPinchGestureRecognizer && o is UIPanGestureRecognizer) || (g is UIPanGestureRecognizer && o is UIPinchGestureRecognizer)
    }

    private func apply() {
        imageView.frame = CGRect(x: vp.contentOriginX, y: vp.contentOriginY, width: vp.contentWidth, height: vp.contentHeight)
        markers.vp = vp
        markers.setNeedsDisplay()
        onViewChanged?(vp)
    }

    private func px(_ p: CGPoint) -> Pixel { Pixel(Double(p.x), Double(p.y)) }
    private func pt(_ p: Pixel) -> CGPoint { CGPoint(x: p.u, y: p.v) }

    // MARK: zoomen met knoppen/slider (vloeiend)
    func setZoom(_ z: Double, animated: Bool) {
        var t = vp
        t.setZoom(z, anchor: Pixel(Double(bounds.midX), Double(bounds.midY)))
        go(to: t, animated: animated)
    }

    func resetView(animated: Bool) {
        var t = vp; t.reset()
        go(to: t, animated: animated)
    }

    private func go(to target: ViewportTransform, animated: Bool) {
        stopAnimation()
        guard animated, !UIAccessibility.isReduceMotionEnabled, abs(target.zoom - vp.zoom) + abs(target.panX - vp.panX) + abs(target.panY - vp.panY) > 0.01 else {
            vp.set(zoom: target.zoom, panX: target.panX, panY: target.panY); apply(); return
        }
        animStart = vp; animTarget = target; animT0 = CACurrentMediaTime()
        let l = CADisplayLink(target: self, selector: #selector(step))
        l.add(to: .main, forMode: .common)
        link = l
    }

    @objc private func step() {
        guard let a = animStart, let b = animTarget else { stopAnimation(); return }
        let p = min(1, (CACurrentMediaTime() - animT0) / 0.22)
        let e = p * p * (3 - 2 * p)
        let z = a.zoom * pow(b.zoom / a.zoom, e)                                    // log-interpolatie: gelijkmatig tempo
        vp.set(zoom: z, panX: a.panX + (b.panX - a.panX) * e, panY: a.panY + (b.panY - a.panY) * e)
        apply()
        if p >= 1 { stopAnimation() }
    }

    private func stopAnimation() { link?.invalidate(); link = nil; animStart = nil; animTarget = nil }

    // MARK: gebaren
    @objc private func handlePinch(_ g: UIPinchGestureRecognizer) {
        guard g.state == .began || g.state == .changed else { return }
        stopAnimation()
        vp.zoom(by: Double(g.scale), anchor: px(g.location(in: self)))
        g.scale = 1
        apply()
    }

    private func hitMarker(at p: CGPoint) -> Int? {
        var best: (Int, CGFloat)? = nil
        for (i, q) in points.enumerated() {
            let c = pt(vp.viewPoint(fromNative: q)); let d = hypot(c.x - p.x, c.y - p.y)
            if d <= 44 && (best == nil || d < best!.1) { best = (i, d) }
        }
        return best?.0
    }

    @objc private func handlePan(_ g: UIPanGestureRecognizer) {
        let t = g.translation(in: self)
        switch g.state {
        case .began:
            stopAnimation()
            let start = CGPoint(x: g.location(in: self).x - t.x, y: g.location(in: self).y - t.y)
            dragIndex = g.numberOfTouches == 1 ? hitMarker(at: start) : nil
            if dragIndex != nil { select.selectionChanged() }
        case .changed:
            g.setTranslation(.zero, in: self)
            if let i = dragIndex, g.numberOfTouches == 1 {
                // relatief slepen: het punt volgt de vingerbeweging, zodat de vinger het punt niet bedekt
                let cur = pt(vp.viewPoint(fromNative: points[i]))
                var n = vp.nativePoint(fromView: px(CGPoint(x: cur.x + t.x, y: cur.y + t.y)))
                n = Pixel(min(max(n.u, 0), vp.nativeWidth), min(max(n.v, 0), vp.nativeHeight))
                points[i] = n
                markers.activeIndex = i
                showLoupe(at: n)
                onPointsChanged?(points)
            } else {
                dragIndex = nil
                vp.pan(byX: Double(t.x), y: Double(t.y)); apply()
            }
        case .ended, .cancelled, .failed:
            if dragIndex != nil { onPointsChanged?(points); scheduleLoupeHide(after: 0.8) }
            dragIndex = nil; markers.activeIndex = nil; markers.setNeedsDisplay()
        default: break
        }
    }

    @objc private func handleTap(_ g: UITapGestureRecognizer) {
        let loc = g.location(in: self)
        if boxMode {
            let n = vp.nativePoint(fromView: px(loc))
            let hit = boxes.filter { polygonContains($0.corners, n) }.min { CandidateFilter.area($0.corners) < CandidateFilter.area($1.corners) }
            if let h = hit { select.selectionChanged(); onBoxTap?(h.id) }
            return
        }
        if let i = hitMarker(at: loc) { markers.activeIndex = i; showLoupe(at: points[i]); scheduleLoupeHide(after: 1.0); return }   // bestaand punt: niets plaatsen
        guard points.count < maxPoints else { UINotificationFeedbackGenerator().notificationOccurred(.warning); return }
        let n = vp.nativePoint(fromView: px(loc))
        guard vp.contains(native: n) else { UINotificationFeedbackGenerator().notificationOccurred(.warning); return }
        points.append(n)
        impact.impactOccurred()
        markers.activeIndex = points.count - 1                       // zichtbare bevestiging: groot gemarkeerd + vergrootglas
        showLoupe(at: n)
        scheduleLoupeHide(after: 1.2)
        onPointsChanged?(points)
    }

    @objc private func handleDoubleTap(_ g: UITapGestureRecognizer) { resetView(animated: true) }

    // MARK: vergrootglas
    private func showLoupe(at n: Pixel) {
        loupeHideWork?.cancel()
        let c = vp.viewPoint(fromNative: n)
        loupe.viewPoint = CGPoint(x: c.u, y: c.v)
        let corner = CGPoint(x: 12, y: 12)
        loupe.frame.origin = (c.u < 12 + 128 + 40 && c.v < 12 + 128 + 40) ? CGPoint(x: bounds.width - 128 - 12, y: 12) : corner
        loupe.magnification = 3
        loupe.isHidden = false
        loupe.setNeedsDisplay()
    }

    private func scheduleLoupeHide(after s: Double) {
        loupeHideWork?.cancel()
        let w = DispatchWorkItem { [weak self] in self?.loupe.isHidden = true; self?.markers.activeIndex = nil; self?.markers.setNeedsDisplay() }
        loupeHideWork = w
        DispatchQueue.main.asyncAfter(deadline: .now() + s, execute: w)
    }
}

/// Tekent punten als kruis + ring (dubbele lijn: donkere rand + kleur) zodat ze in fel buitenlicht en op lichte gevels zichtbaar blijven.
final class MarkerOverlayView: UIView {
    var vp: ViewportTransform?
    var points: [Pixel] = []
    var overlay: [Pixel] = []
    var boxes: [BoxOverlayItem] = []
    var activeIndex: Int?

    private func boxColor(_ f: BoxFeedback) -> UIColor {
        switch f { case .green: return .systemGreen; case .orange: return .systemOrange; case .neutral: return UIColor(white: 0.88, alpha: 1) }
    }

    private func drawBox(_ ctx: CGContext, _ b: BoxOverlayItem, _ v: (Pixel) -> CGPoint) {
        let pts = b.corners.map(v), color = boxColor(b.feedback)
        ctx.saveGState()
        ctx.beginPath(); ctx.move(to: pts[0]); for p in pts.dropFirst() { ctx.addLine(to: p) }; ctx.closePath()
        ctx.setFillColor(color.withAlphaComponent(b.selected ? 0.25 : 0.12).cgColor); ctx.drawPath(using: .fill)
        for (w, c) in [(b.selected ? 7.0 : 5.0, UIColor.black.withAlphaComponent(0.7)), (b.selected ? 4.0 : 2.5, color)] as [(CGFloat, UIColor)] {
            ctx.setLineWidth(w); ctx.setStrokeColor(c.cgColor)
            ctx.beginPath(); ctx.move(to: pts[0]); for p in pts.dropFirst() { ctx.addLine(to: p) }; ctx.closePath(); ctx.strokePath()
        }
        ctx.restoreGState()
        // label boven het bovenste punt
        let top = pts.min { ($0.y, $0.x) < ($1.y, $1.x) }!
        let attrs: [NSAttributedString.Key: Any] = [.font: UIFont.boldSystemFont(ofSize: 12), .foregroundColor: UIColor.black]
        let size = (b.label as NSString).size(withAttributes: attrs)
        var r = CGRect(x: top.x - 2, y: top.y - size.height - 6, width: size.width + 10, height: size.height + 4)
        r.origin.x = min(max(r.origin.x, 2), max(2, bounds.width - r.width - 2)); r.origin.y = max(r.origin.y, 2)
        ctx.setFillColor(color.withAlphaComponent(0.92).cgColor)
        UIBezierPath(roundedRect: r, cornerRadius: 5).fill()
        (b.label as NSString).draw(at: CGPoint(x: r.minX + 5, y: r.minY + 2), withAttributes: attrs)
    }

    override func draw(_ rect: CGRect) {
        guard let ctx = UIGraphicsGetCurrentContext(), let vp = vp else { return }
        func v(_ p: Pixel) -> CGPoint { let q = vp.viewPoint(fromNative: p); return CGPoint(x: q.u, y: q.v) }
        for b in boxes.sorted(by: { CandidateFilter.area($0.corners) > CandidateFilter.area($1.corners) }) where !b.selected { drawBox(ctx, b, v) }
        for b in boxes where b.selected { drawBox(ctx, b, v) }
        for (i, p) in overlay.enumerated() { marker(ctx, v(p), .systemGreen, "\(i + 1)", big: false) }
        if overlay.count >= 2 { outline(ctx, overlay.map(v), .systemGreen) }
        if points.count >= 2 { outline(ctx, points.map(v), .systemYellow) }
        for (i, p) in points.enumerated() { marker(ctx, v(p), i == activeIndex ? .systemYellow : .systemRed, "\(i + 1)", big: i == activeIndex) }
    }

    private func outline(_ ctx: CGContext, _ pts: [CGPoint], _ color: UIColor) {
        ctx.saveGState()
        ctx.setLineDash(phase: 0, lengths: [6, 4])
        for (w, c) in [(3.0, UIColor.black.withAlphaComponent(0.5)), (1.5, color)] as [(CGFloat, UIColor)] {
            ctx.setLineWidth(w); ctx.setStrokeColor(c.cgColor)
            ctx.beginPath(); ctx.move(to: pts[0]); for p in pts.dropFirst() { ctx.addLine(to: p) }
            if pts.count == 4 { ctx.closePath() }
            ctx.strokePath()
        }
        ctx.restoreGState()
    }

    private func marker(_ ctx: CGContext, _ c: CGPoint, _ color: UIColor, _ label: String, big: Bool) {
        let r: CGFloat = big ? 15 : 11, gap: CGFloat = 3, arm: CGFloat = big ? 24 : 19
        for (w, col) in [(4.0, UIColor.black.withAlphaComponent(0.75)), (2.0, color)] as [(CGFloat, UIColor)] {
            ctx.setLineWidth(w); ctx.setStrokeColor(col.cgColor)
            ctx.beginPath()
            ctx.move(to: CGPoint(x: c.x - arm, y: c.y)); ctx.addLine(to: CGPoint(x: c.x - gap, y: c.y))
            ctx.move(to: CGPoint(x: c.x + gap, y: c.y)); ctx.addLine(to: CGPoint(x: c.x + arm, y: c.y))
            ctx.move(to: CGPoint(x: c.x, y: c.y - arm)); ctx.addLine(to: CGPoint(x: c.x, y: c.y - gap))
            ctx.move(to: CGPoint(x: c.x, y: c.y + gap)); ctx.addLine(to: CGPoint(x: c.x, y: c.y + arm))
            ctx.strokePath()
            ctx.strokeEllipse(in: CGRect(x: c.x - r, y: c.y - r, width: 2 * r, height: 2 * r))
        }
        let attrs: [NSAttributedString.Key: Any] = [.font: UIFont.boldSystemFont(ofSize: 13), .foregroundColor: UIColor.white,
                                                    .strokeColor: UIColor.black, .strokeWidth: -3.0]
        (label as NSString).draw(at: CGPoint(x: c.x + r + 3, y: c.y - r - 15), withAttributes: attrs)
    }
}

/// Vergrootglas: toont de omgeving van een punt 3x extra vergroot, met kruis in het midden.
final class LoupeView: UIView {
    weak var source: UIImageView?
    var viewPoint: CGPoint = .zero
    var magnification: CGFloat = 3

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .clear
        isAccessibilityElement = true
        accessibilityIdentifier = "loupe"
    }
    required init?(coder: NSCoder) { fatalError("niet gebruikt") }

    override func draw(_ rect: CGRect) {
        guard let ctx = UIGraphicsGetCurrentContext(), let src = source else { return }
        let circle = bounds.insetBy(dx: 2, dy: 2)
        ctx.saveGState()
        ctx.addEllipse(in: circle); ctx.clip()
        UIColor.darkGray.setFill(); ctx.fill(bounds)
        let k = magnification
        let local = CGPoint(x: viewPoint.x - src.frame.origin.x, y: viewPoint.y - src.frame.origin.y)       // punt in de coordinaten van de afbeeldingslaag
        ctx.translateBy(x: bounds.midX - local.x * k, y: bounds.midY - local.y * k)
        ctx.scaleBy(x: k, y: k)
        src.layer.render(in: ctx)
        ctx.restoreGState()
        for (w, col) in [(3.0, UIColor.black.withAlphaComponent(0.8)), (1.2, UIColor.white)] as [(CGFloat, UIColor)] {
            ctx.setLineWidth(w); ctx.setStrokeColor(col.cgColor)
            ctx.beginPath()
            ctx.move(to: CGPoint(x: bounds.midX - 14, y: bounds.midY)); ctx.addLine(to: CGPoint(x: bounds.midX - 3, y: bounds.midY))
            ctx.move(to: CGPoint(x: bounds.midX + 3, y: bounds.midY)); ctx.addLine(to: CGPoint(x: bounds.midX + 14, y: bounds.midY))
            ctx.move(to: CGPoint(x: bounds.midX, y: bounds.midY - 14)); ctx.addLine(to: CGPoint(x: bounds.midX, y: bounds.midY - 3))
            ctx.move(to: CGPoint(x: bounds.midX, y: bounds.midY + 3)); ctx.addLine(to: CGPoint(x: bounds.midX, y: bounds.midY + 14))
            ctx.strokePath()
            ctx.strokeEllipse(in: circle)
        }
    }
}

struct ZoomableFrameCanvas: UIViewRepresentable {
    let image: UIImage
    @Binding var points: [Pixel]
    let maxPoints: Int
    var overlay: [Pixel]
    var boxes: [BoxOverlayItem] = []
    var boxMode = false
    var onBoxTap: ((String) -> Void)? = nil
    var fitTo: [Pixel]? = nil
    @ObservedObject var controller: CanvasController

    func makeUIView(context: Context) -> ZoomCanvasView {
        let cg = image.cgImage!
        let v = ZoomCanvasView(image: image, nativeWidth: Double(cg.width), nativeHeight: Double(cg.height))
        v.maxPoints = maxPoints
        v.boxMode = boxMode; v.onBoxTap = onBoxTap; v.fitOnFirstLayout = fitTo
        v.points = points; v.overlay = overlay; v.boxes = boxes
        controller.canvas = v
        v.onPointsChanged = { new in DispatchQueue.main.async { if new != points { points = new } } }
        v.onViewChanged = { vp in DispatchQueue.main.async { controller.zoom = vp.zoom; controller.nativePerPoint = vp.nativePixelsPerPoint } }
        return v
    }

    func updateUIView(_ v: ZoomCanvasView, context: Context) {
        v.maxPoints = maxPoints
        if v.points != points { v.points = points }
        if v.overlay != overlay { v.overlay = overlay }
        v.onBoxTap = onBoxTap; v.boxMode = boxMode
        if v.boxes != boxes { v.boxes = boxes }
    }
}
