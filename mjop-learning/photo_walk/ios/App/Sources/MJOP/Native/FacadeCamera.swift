import AVFoundation
import ImageIO
import CoreMotion
import MJOPEngine
import SwiftUI
import UIKit

/// Hoe de foto is genomen: lens en stand van de telefoon. Gaat mee in de scan (voor de bandbreedte van de maten).
struct CaptureMeta: Equatable {
    var lens: String          // "0,5×" of "1×"
    var rollDeg: Double       // draaiing om de kijkas (scheef)
    var pitchDeg: Double      // voorover of achterover gekanteld
    var focal35mm: Double?    // brandpunt (35mm-equivalent) uit de EXIF, voor de perspectiefcorrectie
    var headingDeg: Double? = nil   // kijkrichting van de camera volgens het kompas (graden vanaf magnetisch noord), als die bekend was
    var level: Bool { abs(rollDeg) <= 2 && abs(pitchDeg) <= 4 }
}

/// Camera en waterpas voor de gevelscan.
@MainActor
final class FacadeCameraModel: NSObject, ObservableObject, AVCapturePhotoCaptureDelegate {
    @Published var rollDeg: Double = 0
    @Published var pitchDeg: Double = 0
    @Published var wide = false
    @Published var hasWide = false
    @Published var authorized: Bool?
    @Published var capturing = false
    /// Kijkrichting van de camera volgens het kompas; nil als het kompas niet beschikbaar of niet gekalibreerd is.
    @Published var headingDeg: Double?
    private var headingVec: (s: Double, c: Double)?

    let session = AVCaptureSession()
    private let output = AVCapturePhotoOutput()
    private let motion = CMMotionManager()
    private var input: AVCaptureDeviceInput?
    private var completion: ((UIImage, CaptureMeta) -> Void)?
    private let queue = DispatchQueue(label: "nl.mjop.camera")

    var isLevel: Bool { abs(rollDeg) <= 2 && abs(pitchDeg) <= 4 }

    func start() async {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: authorized = true
        case .notDetermined: authorized = await AVCaptureDevice.requestAccess(for: .video)
        default: authorized = false
        }
        guard authorized == true else { return }
        hasWide = AVCaptureDevice.default(.builtInUltraWideCamera, for: .video, position: .back) != nil
        wide = hasWide           // standaard groothoek: de hele gevel past er makkelijker op
        configure()
        let s = session
        queue.async { s.startRunning() }
        startMotion()
    }

    func stop() {
        motion.stopDeviceMotionUpdates()
        let s = session
        queue.async { s.stopRunning() }
    }

    func toggleLens() { wide.toggle(); configure() }

    private func configure() {
        let type: AVCaptureDevice.DeviceType = wide && hasWide ? .builtInUltraWideCamera : .builtInWideAngleCamera
        guard let device = AVCaptureDevice.default(type, for: .video, position: .back), let newInput = try? AVCaptureDeviceInput(device: device) else { return }
        session.beginConfiguration()
        session.sessionPreset = .photo
        if let input { session.removeInput(input) }
        if session.canAddInput(newInput) { session.addInput(newInput); input = newInput }
        if !session.outputs.contains(output), session.canAddOutput(output) { session.addOutput(output) }
        output.connection(with: .video)?.videoOrientation = .portrait
        session.commitConfiguration()
    }

    private func startMotion() {
        guard motion.isDeviceMotionAvailable else { return }
        motion.deviceMotionUpdateInterval = 1.0 / 20
        // Met magneetveld (kompas) als dat kan; geen locatietoestemming nodig.
        let frame: CMAttitudeReferenceFrame = CMMotionManager.availableAttitudeReferenceFrames().contains(.xMagneticNorthZVertical) ? .xMagneticNorthZVertical : .xArbitraryZVertical
        motion.startDeviceMotionUpdates(using: frame, to: .main) { [weak self] m, _ in
            guard let self, let m else { return }
            let g = m.gravity
            self.updateHeading(m)
            // Telefoon rechtop (portret) richting de gevel: zwaartekracht ≈ (0, −1, 0).
            let roll = atan2(g.x, -g.y) * 180 / .pi
            let pitch = atan2(g.z, -g.y) * 180 / .pi
            self.rollDeg = (self.rollDeg * 0.6) + (roll * 0.4)      // licht gedempt, zodat het niet trilt
            self.pitchDeg = (self.pitchDeg * 0.6) + (pitch * 0.4)
        }
    }

    private func updateHeading(_ m: CMDeviceMotion) {
        let f = m.magneticField
        guard f.accuracy != .uncalibrated,
              let h = CompassCheck.heading(gravity: [m.gravity.x, m.gravity.y, m.gravity.z], magnetic: [f.field.x, f.field.y, f.field.z]) else {
            headingDeg = nil; headingVec = nil; return
        }
        // Dempen via sinus en cosinus, zodat de overgang 359° → 0° niet springt.
        let r = h * .pi / 180
        let v = headingVec.map { (s: $0.s * 0.8 + sin(r) * 0.2, c: $0.c * 0.8 + cos(r) * 0.2) } ?? (s: sin(r), c: cos(r))
        headingVec = v
        headingDeg = (atan2(v.s, v.c) * 180 / .pi + 360).truncatingRemainder(dividingBy: 360)
    }

    func capture(_ done: @escaping (UIImage, CaptureMeta) -> Void) {
        guard !capturing else { return }
        capturing = true
        completion = done
        output.capturePhoto(with: AVCapturePhotoSettings(), delegate: self)
    }

    nonisolated func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let data = photo.fileDataRepresentation()
        let exif = photo.metadata[kCGImagePropertyExifDictionary as String] as? [String: Any]
        let f35 = (exif?[kCGImagePropertyExifFocalLenIn35mmFilm as String] as? NSNumber)?.doubleValue
        Task { @MainActor in
            self.capturing = false
            guard let data, let img = UIImage(data: data) else { return }
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            self.completion?(img, CaptureMeta(lens: self.wide ? "0,5×" : "1×", rollDeg: self.rollDeg, pitchDeg: self.pitchDeg, focal35mm: f35, headingDeg: self.headingDeg))
        }
    }
}

struct CameraPreview: UIViewRepresentable {
    let session: AVCaptureSession
    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
    func makeUIView(context: Context) -> PreviewView {
        let v = PreviewView()
        v.preview.session = session
        v.preview.videoGravity = .resizeAspectFill
        return v
    }
    func updateUIView(_ v: PreviewView, context: Context) {}
}

/// Camerascherm voor één gevel: kader, waterpas, lenswissel en sluiter. Bij scheef houden een waarschuwing (de foto kan wel).
struct FacadeCameraView: View {
    let title: String
    let step: String
    /// Windrichting van de gekozen gevel (voor de kompascheck); nil = geen check.
    var facing: String? = nil
    let done: (UIImage, CaptureMeta) -> Void
    @Environment(\.dismiss) private var dismiss
    @StateObject private var cam = FacadeCameraModel()
    @State private var confirmTilt = false
    @State private var confirmSide = false

    /// Afwijking van de kijkrichting voor de gekozen gevel, als het kompas iets zegt.
    private var sideDeviation: Double? {
        guard let facing, let h = cam.headingDeg else { return nil }
        return CompassCheck.deviation(cameraHeading: h, facing: facing)
    }
    private var wrongSide: Bool { (sideDeviation ?? 0) > CompassCheck.warnAbove }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if cam.authorized == true {
                CameraPreview(session: cam.session).ignoresSafeArea()
                frameCorners.padding(.horizontal, 34).padding(.vertical, 150).allowsHitTesting(false)
            } else if cam.authorized == false {
                VStack(spacing: 12) {
                    Image(systemName: "camera.fill").font(.largeTitle).foregroundStyle(.white)
                    Text("Geen toegang tot de camera").font(.headline).foregroundStyle(.white)
                    Text("Zet de camera aan voor MJOP Live bij Instellingen → Privacy → Camera.").font(.subheadline).foregroundStyle(.white.opacity(0.7)).multilineTextAlignment(.center)
                }
                .padding(30)
            }
            VStack {
                HStack {
                    Button { cam.stop(); dismiss() } label: {
                        Image(systemName: "xmark").font(.headline).foregroundStyle(.white).frame(width: 42, height: 42).background(.ultraThinMaterial, in: Circle())
                    }
                    .accessibilityLabel("Sluiten")
                    Spacer()
                    HStack(spacing: 6) { Circle().fill(Color(hex: 0x6BE39A)).frame(width: 8, height: 8); Text("\(step) · \(title)").font(.subheadline.weight(.semibold)) }
                        .foregroundStyle(.white).padding(.horizontal, 14).padding(.vertical, 9).background(.ultraThinMaterial, in: Capsule())
                    Spacer()
                    Color.clear.frame(width: 42, height: 42)
                }
                .environment(\.colorScheme, .dark)
                .padding(.horizontal, 16).padding(.top, 8)
                Spacer()
                if wrongSide, let facing, let h = cam.headingDeg {
                    Label("De camera wijst richting \(CompassCheck.name(of: h)). Voor deze gevel kijk je richting \(CompassCheck.viewingHeading(facing: facing).map { CompassCheck.name(of: $0) } ?? "?").", systemImage: "location.north.line")
                        .font(.footnote.weight(.semibold)).foregroundStyle(.white).multilineTextAlignment(.center)
                        .padding(.horizontal, 14).padding(.vertical, 9).background(Color.orange.opacity(0.85), in: Capsule())
                        .padding(.horizontal, 20).padding(.bottom, 10)
                        .accessibilityIdentifier("compassWarning")
                }
                level
                Spacer().frame(height: 26)
                HStack {
                    Color.clear.frame(width: 64, height: 64)
                    Spacer()
                    Button { shoot() } label: {
                        ZStack {
                            Circle().stroke(.white, lineWidth: 5).frame(width: 80, height: 80)
                            Circle().fill(cam.capturing ? Color.gray : .white).frame(width: 64, height: 64)
                        }
                    }
                    .disabled(cam.authorized != true || cam.capturing)
                    .accessibilityLabel("Foto maken")
                    .accessibilityIdentifier("shutter")
                    Spacer()
                    if cam.hasWide {
                        Button { cam.toggleLens() } label: {
                            Text(cam.wide ? "0,5×" : "1×").font(.footnote.weight(.bold)).frame(width: 52, height: 52)
                                .foregroundStyle(cam.wide ? Color.black : .white)
                                .background(cam.wide ? AnyShapeStyle(Color.white) : AnyShapeStyle(.ultraThinMaterial), in: Circle())
                        }
                        .environment(\.colorScheme, .dark)
                        .frame(width: 64)
                        .accessibilityLabel(cam.wide ? "Groothoek aan" : "Groothoek uit")
                    } else { Color.clear.frame(width: 64, height: 64) }
                }
                .padding(.horizontal, 24).padding(.bottom, 30)
            }
        }
        .statusBarHidden()
        .task { await cam.start() }
        .onDisappear { cam.stop() }
        .alert("De telefoon staat scheef", isPresented: $confirmTilt) {
            Button("Toch foto maken") { take() }
            Button("Opnieuw richten", role: .cancel) {}
        } message: {
            Text("Een scheve foto geeft minder nauwkeurige maten. Houd de telefoon recht en sta recht voor de gevel.")
        }
        .alert("Is dit de goede gevel?", isPresented: $confirmSide) {
            Button("Ja, foto maken") { take() }
            Button("Opnieuw richten", role: .cancel) {}
        } message: {
            Text("Volgens het kompas wijst de camera niet naar de gevel die je hebt gekozen. Het kompas kan afwijken bij staal of auto's in de buurt; weet je het zeker, maak dan gewoon de foto.")
        }
    }

    private var level: some View {
        let ok = cam.isLevel
        return VStack(spacing: 10) {
            ZStack {
                Capsule().fill(.white.opacity(0.35)).frame(width: 170, height: 4)
                Circle().stroke(ok ? Color(hex: 0x6BE39A) : Color.orange, lineWidth: 3).frame(width: 22, height: 22)
                    .offset(x: CGFloat(max(-80, min(80, cam.rollDeg * 4))))
            }
            .rotationEffect(.degrees(-cam.rollDeg))
            Text(ok ? "Recht · hele gevel in beeld" : (abs(cam.pitchDeg) > 4 ? "Houd de telefoon rechtop" : "Houd de telefoon recht"))
                .font(.footnote.weight(.semibold)).foregroundStyle(.white)
                .padding(.horizontal, 12).padding(.vertical, 6).background(.ultraThinMaterial, in: Capsule())
                .environment(\.colorScheme, .dark)
        }
        .animation(.easeOut(duration: 0.15), value: ok)
        .accessibilityElement(children: .combine)
    }

    private var frameCorners: some View {
        GeometryReader { g in
            let w = g.size.width, h = g.size.height, l: CGFloat = 36
            Path { p in
                p.move(to: CGPoint(x: 0, y: l)); p.addLine(to: .zero); p.addLine(to: CGPoint(x: l, y: 0))
                p.move(to: CGPoint(x: w - l, y: 0)); p.addLine(to: CGPoint(x: w, y: 0)); p.addLine(to: CGPoint(x: w, y: l))
                p.move(to: CGPoint(x: w, y: h - l)); p.addLine(to: CGPoint(x: w, y: h)); p.addLine(to: CGPoint(x: w - l, y: h))
                p.move(to: CGPoint(x: l, y: h)); p.addLine(to: CGPoint(x: 0, y: h)); p.addLine(to: CGPoint(x: 0, y: h - l))
            }
            .stroke(.white, style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
        }
    }

    private func shoot() {
        if !cam.isLevel { confirmTilt = true } else if wrongSide { confirmSide = true } else { take() }
    }

    private func take() {
        cam.capture { img, meta in
            cam.stop()
            done(img, meta)
            dismiss()
        }
    }
}

enum FacadeCameraSupport {
    /// Echte camera aanwezig (niet in de simulator).
    static var available: Bool { AVCaptureDevice.default(for: .video) != nil }
}
