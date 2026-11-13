import MJOPEngine
import UIKit

/// Het MJOP-rapport als PDF (A4), gemaakt op het toestel uit het plan. Alleen echte gegevens; onbekend staat er als onbekend.
enum RapportPDF {
    static func make(project: Project, model: ProjectModel, photos: [(String, UIImage)] = []) throws -> URL {
        let page = CGRect(x: 0, y: 0, width: 595, height: 842)
        let margin: CGFloat = 48
        let blue = UIColor(hex: 0x2F4BFF), ink = UIColor(hex: 0x0E1424), grey = UIColor(hex: 0x667085), line = UIColor(hex: 0xE6EAF2)
        let year = ProjectModel.year, end = year + Engine.horizon - 1
        let per = model.perYear
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("MJOP \(project.naam) \(year)-\(end).pdf")

        let renderer = UIGraphicsPDFRenderer(bounds: page)
        try renderer.writePDF(to: url) { ctx in
            var y: CGFloat = 0
            var pageNo = 0
            func text(_ s: String, _ size: CGFloat, _ color: UIColor, weight: UIFont.Weight = .regular, x: CGFloat, w: CGFloat, align: NSTextAlignment = .left, advance: Bool = false) {
                let p = NSMutableParagraphStyle(); p.alignment = align
                let a: [NSAttributedString.Key: Any] = [.font: UIFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color, .paragraphStyle: p]
                let r = (s as NSString).boundingRect(with: CGSize(width: w, height: 1000), options: .usesLineFragmentOrigin, attributes: a, context: nil)
                (s as NSString).draw(with: CGRect(x: x, y: y, width: w, height: r.height), options: .usesLineFragmentOrigin, attributes: a, context: nil)
                if advance { y += ceil(r.height) }
            }
            func newPage() {
                ctx.beginPage(); pageNo += 1; y = margin
                text("MJOP Live · \(project.naam)", 9, grey, x: margin, w: 300)
                text("Pagina \(pageNo)", 9, grey, x: page.width - margin - 100, w: 100, align: .right)
                y += 22
            }
            func ensure(_ h: CGFloat) { if y + h > page.height - margin { newPage() } }
            func euro(_ d: Decimal) -> String { DSFormat.euros(euroInt(d)) }

            newPage()
            // titel
            UIColor(hex: 0x2F4BFF).setFill(); UIBezierPath(roundedRect: CGRect(x: margin, y: y, width: 34, height: 34), cornerRadius: 9).fill()
            ("M" as NSString).draw(at: CGPoint(x: margin + 9, y: y + 5), withAttributes: [.font: UIFont.systemFont(ofSize: 20, weight: .bold), .foregroundColor: UIColor.white])
            y += 48
            text("Meerjarenonderhoudsplan \(year)–\(end)", 24, ink, weight: .bold, x: margin, w: page.width - 2 * margin, advance: true)
            y += 4
            text(project.fullAddress ?? project.naam, 13, grey, x: margin, w: page.width - 2 * margin, advance: true)
            y += 22

            // kerncijfers
            let facts: [(String, String)] = [
                ("Geraamd onderhoud \(year)–\(end)", euro(model.total)),
                ("Duurste jaar", model.peak.map { "\($0.jaar) · \(euro($0.bedrag))" } ?? "onbekend"),
                ("Bijdrage per appartement per maand", model.bijdrage.map(euro) ?? "niet ingevuld"),
                ("Nodig om het fonds niet onder € 0 te laten komen", model.required.map { DSFormat.euros($0) } ?? "onbekend (saldo niet ingevuld)"),
                ("Laagste stand reservefonds", model.fund?.min { $0.saldo < $1.saldo }.map { "\(euro($0.saldo)) in \($0.jaar)" } ?? "onbekend"),
                ("Bouwjaar · appartementen", "\(model.building.bouwjaar.map(String.init) ?? "onbekend") · \(model.units)"),
                ("Beoordeeld", "\(model.beoordeeld) van \(model.elements.count) posten"),
            ]
            for (k, v) in facts {
                text(k, 11, grey, x: margin, w: 300)
                text(v, 11, ink, weight: .semibold, x: margin + 300, w: page.width - 2 * margin - 300, align: .right)
                y += 20
                line.setFill(); UIRectFill(CGRect(x: margin, y: y - 5, width: page.width - 2 * margin, height: 0.5))
            }
            y += 18

            // planning per jaar
            text("Planning", 16, ink, weight: .bold, x: margin, w: 300, advance: true)
            y += 8
            for j in year...end {
                let items = model.plan.filter { $0.jaar == j }
                guard !items.isEmpty else { continue }
                ensure(30 + CGFloat(items.count) * 18)
                text(String(j), 13, ink, weight: .bold, x: margin, w: 100)
                text(euro(per[j] ?? 0), 13, blue, weight: .semibold, x: page.width - margin - 150, w: 150, align: .right)
                y += 20
                for c in items {
                    text(c.naam, 10.5, ink, x: margin + 14, w: 360)
                    text(euro(c.bedrag), 10.5, ink, x: page.width - margin - 150, w: 150, align: .right)
                    y += 17
                }
                y += 6
            }

            // bronnen en aannames
            ensure(140)
            y += 10
            text("Bronnen en aannames", 16, ink, weight: .bold, x: margin, w: 300, advance: true)
            y += 6
            let notes = [
                "Gebouwgegevens uit de BAG en de 3D BAG (TU Delft). Een oppervlak dat geschat is, is als schatting gemarkeerd in de app.",
                "Kosten zijn geraamd met standaardbedragen (prijspeil \(year)), geen offertes. Bedragen zijn exclusief onvoorziene kosten.",
                "Posten zonder beoordeling volgen de gebruikelijke levensduur. Beoordelingen volgen een vereenvoudigde NEN 2767-schaal; dit is geen gecertificeerde inspectie.",
                model.gevels.isEmpty ? "Er zijn nog geen gevels gescand." : "\(model.gevels.count) gevel(s) gescand met een gevelfoto: elementen herkend door Claude, maten berekend met de gevelbreedte uit de BAG.",
            ]
            for n in notes { ensure(40); text("• " + n, 10, grey, x: margin, w: page.width - 2 * margin, advance: true); y += 6 }

            // bijlage: gevelfoto's
            if !photos.isEmpty {
                newPage()
                text("Bijlage: gevelfoto's", 16, ink, weight: .bold, x: margin, w: 300, advance: true)
                y += 10
                let maxW = page.width - 2 * margin
                for (caption, img) in photos {
                    let k = min(maxW / img.size.width, 330 / img.size.height)
                    let size = CGSize(width: img.size.width * k, height: img.size.height * k)
                    ensure(size.height + 30)
                    img.draw(in: CGRect(x: margin, y: y, width: size.width, height: size.height))
                    y += size.height + 4
                    text(caption, 10, grey, x: margin, w: maxW, advance: true)
                    y += 14
                }
            }
        }
        return url
    }
}
