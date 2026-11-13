import SwiftUI
import WidgetKit

/// Widget op het beginscherm: stand van het reservefonds, laagste stand en het eerstvolgende onderhoud van het laatst
/// geopende project. Leest alleen de samenvatting die de app in de App Group zet; zonder samenvatting een uitnodiging om de app te openen.
struct SnapshotEntry: TimelineEntry {
    let date: Date
    let snapshot: WidgetSnapshot?
}

struct SnapshotProvider: TimelineProvider {
    func placeholder(in context: Context) -> SnapshotEntry { SnapshotEntry(date: Date(), snapshot: nil) }
    func getSnapshot(in context: Context, completion: @escaping (SnapshotEntry) -> Void) { completion(SnapshotEntry(date: Date(), snapshot: WidgetSnapshot.load())) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<SnapshotEntry>) -> Void) {
        completion(Timeline(entries: [SnapshotEntry(date: Date(), snapshot: WidgetSnapshot.load())], policy: .never))
    }
}

private let accent = Color(red: 47 / 255, green: 75 / 255, blue: 1)

struct MJOPWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: SnapshotEntry

    var body: some View {
        Group {
            if let s = entry.snapshot { content(s) } else { empty }
        }
        .widgetBackgroundCompat()
    }

    private var empty: some View {
        VStack(alignment: .leading, spacing: 6) {
            logo
            Spacer()
            Text("Open MJOP Live om de widget te vullen").font(.caption.weight(.semibold))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    private var logo: some View {
        Text("M").font(.system(size: 13, weight: .bold)).foregroundStyle(.white)
            .frame(width: 22, height: 22).background(accent, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
    }

    @ViewBuilder private func content(_ s: WidgetSnapshot) -> some View {
        let fund = VStack(alignment: .leading, spacing: 2) {
            Text("Reservefonds").font(.caption2).foregroundStyle(.secondary)
            if let f = s.fondsNu { Text(WidgetSnapshot.euro(f)).font(.headline.weight(.bold)).minimumScaleFactor(0.7).lineLimit(1) }
            else { Text("Vul saldo in").font(.caption.weight(.semibold)) }
            if family != .systemSmall {
                if let l = s.laagsteStand, let j = s.laagsteJaar {
                    Text("Laagste \(WidgetSnapshot.euro(l)) in \(String(j))").font(.caption2).foregroundStyle(l < 0 ? .red : .secondary)
                } else {
                    Text("Laagste stand: vul bijdrage in").font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
        let next = VStack(alignment: .leading, spacing: 2) {
            Text("Volgend onderhoud").font(.caption2).foregroundStyle(.secondary)
            if let y = s.volgendJaar {
                Text(String(y) + (s.volgendBedrag.map { " · " + WidgetSnapshot.euro($0) } ?? "")).font(.subheadline.weight(.semibold)).lineLimit(1).minimumScaleFactor(0.7)
                if family != .systemSmall {
                    ForEach(s.volgendPosten.prefix(3), id: \.self) { Text($0).font(.caption2).lineLimit(1) }
                }
            } else {
                Text("Niets gepland").font(.caption.weight(.semibold))
            }
        }
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) { logo; Text(s.naam).font(.caption.weight(.semibold)).lineLimit(1) }
            if family == .systemSmall {
                fund
                next
            } else {
                HStack(alignment: .top, spacing: 14) { fund.frame(maxWidth: .infinity, alignment: .leading); next.frame(maxWidth: .infinity, alignment: .leading) }
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .widgetURL(URL(string: "mjoplive://project/\(s.projectId)"))
    }
}

extension View {
    /// iOS 17 vraagt een containerachtergrond; op iOS 16 gewoon een achtergrond met eigen marge.
    @ViewBuilder func widgetBackgroundCompat() -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            self.containerBackground(for: .widget) { Color(.systemBackground) }
        } else {
            self.padding().background(Color(.systemBackground))
        }
    }
}

@main
struct MJOPWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "MJOPWidget", provider: SnapshotProvider()) { MJOPWidgetView(entry: $0) }
            .configurationDisplayName("MJOP Live")
            .description("Reservefonds en het eerstvolgende onderhoud van je project.")
            .supportedFamilies([.systemSmall, .systemMedium])
    }
}
