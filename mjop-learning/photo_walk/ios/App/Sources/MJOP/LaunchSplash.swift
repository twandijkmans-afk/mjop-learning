import SwiftUI

/// Opstartscherm van MJOP Live: het logo (blauw vierkant met M) springt in beeld, de naam schuift erachter omhoog en het scherm gaat zacht over in de app.
/// Het vangt geen tikken af. Bij "Verminder beweging" is er geen animatie: kort zichtbaar en weg.
/// Alleen bij een gewone start: UI-tests en de rooktest (opstartargumenten) slaan het over, zodat ze niet vertragen.
struct LaunchSplashView: View {
    let done: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var markIn = false
    @State private var wordIn = false
    @State private var fadeOut = false

    static var shouldShow: Bool {
        !CommandLine.arguments.contains { $0.hasPrefix("-mjop") || $0.hasPrefix("-scanner") || $0.hasPrefix("-uitest") || $0 == "-selftest" }
    }

    private static let blue = Color(red: 47.0 / 255, green: 75.0 / 255, blue: 255.0 / 255)

    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 18) {
                Text("M").font(.system(size: 44, weight: .bold)).foregroundStyle(.white)
                    .frame(width: 84, height: 84)
                    .background(Self.blue)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .scaleEffect(markIn ? 1 : 0.6).opacity(markIn ? 1 : 0)
                Text("MJOP Live").font(.system(size: 22, weight: .semibold))
                    .opacity(wordIn ? 1 : 0).offset(y: wordIn ? 0 : 10)
            }
        }
        .opacity(fadeOut ? 0 : 1)
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .task {
            if reduceMotion {
                markIn = true; wordIn = true
                try? await Task.sleep(nanoseconds: 500_000_000)
            } else {
                withAnimation(.spring(response: 0.6, dampingFraction: 0.7)) { markIn = true }
                try? await Task.sleep(nanoseconds: 350_000_000)
                withAnimation(.easeOut(duration: 0.5)) { wordIn = true }
                try? await Task.sleep(nanoseconds: 1_150_000_000)
            }
            withAnimation(.easeInOut(duration: 0.45)) { fadeOut = true }
            try? await Task.sleep(nanoseconds: 500_000_000)
            done()
        }
    }
}
