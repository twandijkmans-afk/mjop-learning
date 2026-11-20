import MJOPEngine
import UIKit

/// Het MJOP-document als PDF, in de opbouw van een gangbaar MJOP-exportrapport, in de huisstijl van MJOP Live:
/// voorblad, algemene objectgegevens, elementenoverzicht met conditie, bevindingen, de meerjarentabel (liggend, per NL-SfB-hoofdgroep),
/// de hoofdgroepen per jaar, het jaarplan, het reservefonds, de elementen per gevel en dak, en de gevelfoto's.
/// Alleen echte gegevens; onbekend staat er als onbekend, een niet te berekenen post als "bedrag onbekend" (nooit € 0).
enum RapportPDF {
    /// `photos`: bijschrift en foto per gevelfoto (bijlage). `scanPhotos`: dezelfde foto's per opslagpad, voor de uitsnede bij een bevinding.
    static func make(project: Project, model: ProjectModel, photos: [(String, UIImage)] = [], scanPhotos: [String: UIImage] = [:]) throws -> URL {
        let year = ProjectModel.year, end = year + Engine.horizon - 1
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("MJOP \(project.naam) \(year)-\(end).pdf")
        let doc = Doc(project: project)
        let renderer = UIGraphicsPDFRenderer(bounds: Doc.portrait)
        try renderer.writePDF(to: url) { ctx in
            doc.ctx = ctx
            cover(doc, project: project, model: model, photo: photos.first?.1)
            objectData(doc, project: project, model: model)
            elementOverview(doc, model: model)
            findings(doc, model: model, scanPhotos: scanPhotos)
            let table = MeerjarenTabel.make(elements: model.elements, year: year)
            multiYear(doc, table: table)
            mainGroups(doc, table: table)
            yearPlan(doc, table: table, year: year)
            fund(doc, model: model)
            measured(doc, model: model)
            appendix(doc, photos: photos)
        }
        return url
    }

    // MARK: - Opmaak

    static let blue = UIColor(hex: 0x2F4BFF), blueSoft = UIColor(hex: 0xEEF1FF), ink = UIColor(hex: 0x0E1424)
    static let grey = UIColor(hex: 0x667085), line = UIColor(hex: 0xD9DEE8), zebra = UIColor(hex: 0xF6F7FA), panel = UIColor(hex: 0xF3F4F7)
    static let objectBar = UIColor(hex: 0x3A4256)

    /// Kleur en naam per conditie (NEN 2767: 1 uitstekend … 6 zeer slecht).
    static func condition(_ c: Int?) -> (UIColor, String) {
        switch c {
        case 1: return (UIColor(hex: 0x1E7B4B), "Uitstekend")
        case 2: return (UIColor(hex: 0x3BA66B), "Goed")
        case 3: return (UIColor(hex: 0xF2A93B), "Redelijk")
        case 4: return (UIColor(hex: 0xEE8A2E), "Matig")
        case 5: return (UIColor(hex: 0xE8735A), "Slecht")
        case 6: return (UIColor(hex: 0xD93A3A), "Zeer slecht")
        default: return (UIColor(hex: 0xB8C0CF), "Niet beoordeeld")
        }
    }

    static func euro(_ d: Decimal) -> String { DSFormat.euros(euroInt(d)) }

    static let qtyFormat: NumberFormatter = {
        let f = NumberFormatter(); f.locale = Locale(identifier: "nl_NL"); f.numberStyle = .decimal
        f.minimumFractionDigits = 2; f.maximumFractionDigits = 2
        return f
    }()
    static func unitLabel(_ u: String) -> String {
        switch u.lowercased() { case "m2": return "m²"; case "m1", "m": return "m"; case "units": return "app."; default: return u }
    }
    static func quantity(_ q: Decimal?, _ unit: String?) -> String {
        guard let q, let unit else { return "–" }
        return (qtyFormat.string(from: NSDecimalNumber(decimal: q)) ?? "\(q)") + " " + unitLabel(unit)
    }
    static func m2(_ v: Double?) -> String {
        guard let v else { return "onbekend" }
        return (qtyFormat.string(from: NSNumber(value: v)) ?? "\(v)") + " m²"
    }
    static var printDate: String {
        let f = DateFormatter(); f.locale = Locale(identifier: "nl_NL"); f.dateFormat = "d-M-yyyy"
        return f.string(from: Date())
    }

    /// Tekenhulp: pagina's (staand of liggend) met kop en voet, een schrijfpositie en tekst in een kolom.
    final class Doc {
        static let portrait = CGRect(x: 0, y: 0, width: 595, height: 842)
        static let landscape = CGRect(x: 0, y: 0, width: 842, height: 595)
        var ctx: UIGraphicsPDFRendererContext!
        var page = Doc.portrait
        var y: CGFloat = 0
        var pageNo = 0
        let margin: CGFloat = 40
        let project: Project
        /// Herhaalde tabelkop na een paginawissel.
        var repeatHeader: (() -> Void)?
        init(project: Project) { self.project = project }

        var left: CGFloat { margin }
        var width: CGFloat { page.width - 2 * margin }
        var bottom: CGFloat { page.height - margin - 18 }

        @discardableResult
        func text(_ s: String, _ size: CGFloat, _ color: UIColor = RapportPDF.ink, weight: UIFont.Weight = .regular, x: CGFloat, w: CGFloat,
                  align: NSTextAlignment = .left, at yy: CGFloat? = nil, advance: Bool = false) -> CGFloat {
            let p = NSMutableParagraphStyle(); p.alignment = align; p.lineBreakMode = .byWordWrapping
            let a: [NSAttributedString.Key: Any] = [.font: UIFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color, .paragraphStyle: p]
            let r = (s as NSString).boundingRect(with: CGSize(width: w, height: 2000), options: .usesLineFragmentOrigin, attributes: a, context: nil)
            let top = yy ?? y
            (s as NSString).draw(with: CGRect(x: x, y: top, width: w, height: ceil(r.height)), options: .usesLineFragmentOrigin, attributes: a, context: nil)
            if advance { y = top + ceil(r.height) }
            return ceil(r.height)
        }
        func height(_ s: String, _ size: CGFloat, weight: UIFont.Weight = .regular, w: CGFloat) -> CGFloat {
            let a: [NSAttributedString.Key: Any] = [.font: UIFont.systemFont(ofSize: size, weight: weight)]
            return ceil((s as NSString).boundingRect(with: CGSize(width: w, height: 2000), options: .usesLineFragmentOrigin, attributes: a, context: nil).height)
        }
        func fill(_ r: CGRect, _ c: UIColor) { c.setFill(); UIRectFill(r) }
        func rule(_ yy: CGFloat, x: CGFloat? = nil, w: CGFloat? = nil, color: UIColor = RapportPDF.line, thickness: CGFloat = 0.5) {
            fill(CGRect(x: x ?? left, y: yy, width: w ?? width, height: thickness), color)
        }

        func newPage(landscape: Bool = false, header: Bool = true) {
            page = landscape ? Doc.landscape : Doc.portrait
            ctx.beginPage(withBounds: page, pageInfo: [:])
            pageNo += 1
            y = margin
            if header { drawHeader() }
            text(RapportPDF.printDate, 8, RapportPDF.grey, x: left, w: 200, at: page.height - margin)
            text("\(pageNo)", 8, RapportPDF.grey, x: page.width - margin - 60, w: 60, align: .right, at: page.height - margin)
        }

        func drawHeader() {
            let addr = [project.adres, project.plaats].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " • ")
            text(project.naam, 9.5, weight: .bold, x: left, w: width - 140, at: y)
            if !addr.isEmpty { text(addr, 9.5, weight: .semibold, x: left, w: width - 140, at: y + 12) }
            logo(x: page.width - margin - 92, y: y - 2, size: 22)
            y += 30
        }

        func logo(x: CGFloat, y yy: CGFloat, size: CGFloat) {
            RapportPDF.blue.setFill()
            UIBezierPath(roundedRect: CGRect(x: x, y: yy, width: size, height: size), cornerRadius: size * 0.26).fill()
            let f = UIFont.systemFont(ofSize: size * 0.6, weight: .bold)
            let m = ("M" as NSString).size(withAttributes: [.font: f])
            ("M" as NSString).draw(at: CGPoint(x: x + (size - m.width) / 2, y: yy + (size - m.height) / 2), withAttributes: [.font: f, .foregroundColor: UIColor.white])
            ("MJOP Live" as NSString).draw(at: CGPoint(x: x + size + 6, y: yy + (size - 14) / 2), withAttributes: [.font: UIFont.systemFont(ofSize: 11.5, weight: .semibold), .foregroundColor: RapportPDF.ink])
        }

        /// Nieuwe pagina als `h` niet meer past; herhaalt dan de tabelkop.
        func ensure(_ h: CGFloat) {
            guard y + h > bottom else { return }
            newPage(landscape: page.width > page.height)
            repeatHeader?()
        }

        /// Gekleurde titelbalk over de volle breedte.
        func bar(_ title: String, color: UIColor = RapportPDF.blue, size: CGFloat = 12) {
            fill(CGRect(x: left, y: y, width: width, height: 22), color)
            text(title, size, .white, weight: .bold, x: left + 8, w: width - 16, at: y + (22 - size * 1.2) / 2)
            y += 26
        }

        func sectionTitle(_ s: String, _ size: CGFloat = 16) { text(s, size, weight: .bold, x: left, w: width, advance: true); y += 8 }

        /// Grijs vak met toelichting: per regel een term en een uitleg.
        func explanation(_ rows: [(String, String)]) {
            text("Toelichting:", 11, weight: .bold, x: left, w: width, advance: true); y += 6
            let termW: CGFloat = 130, pad: CGFloat = 14
            let inner = min(width, 520) - termW - 2 * pad - 8
            let h = rows.reduce(CGFloat(2 * pad)) { $0 + max(height($1.1, 8.5, w: inner), 11) + 7 }
            fill(CGRect(x: left, y: y, width: min(width, 520), height: h), RapportPDF.panel)
            var yy = y + pad
            for (term, uitleg) in rows {
                text(term.isEmpty ? "" : term + ":", 8.5, RapportPDF.grey, x: left + pad, w: termW, align: .right, at: yy)
                let hh = text(uitleg, 8.5, x: left + pad + termW + 8, w: inner, at: yy)
                yy += max(hh, 11) + 7
            }
            y += h + 14
        }

        func conditionLegend() {
            text("Conditie (NEN 2767, zoals beoordeeld in de app):", 9, weight: .semibold, x: left, w: width, advance: true); y += 4
            var x = left
            for c in [1, 2, 3, 4, 5, 6, nil] as [Int?] {
                let name = RapportPDF.condition(c).1
                badge(c, x: x, y: y)
                text(name, 8, x: x + 24, w: 70, at: y + 2)
                x += 76
                if x + 76 > left + width { x = left; y += 18 }
            }
            y += 24
        }

        func badge(_ c: Int?, x: CGFloat, y yy: CGFloat) {
            let (col, _) = RapportPDF.condition(c)
            col.setFill(); UIBezierPath(roundedRect: CGRect(x: x, y: yy, width: 20, height: 13), cornerRadius: 3).fill()
            text(c.map(String.init) ?? "–", 8, .white, weight: .bold, x: x, w: 20, align: .center, at: yy + 1.5)
        }

        /// Sleutel–waarde-regel in een gegevensblok.
        func field(_ k: String, _ v: String) {
            let h = max(height(v, 9.5, w: width - 190), 12)
            ensure(h + 6)
            text(k, 9.5, RapportPDF.grey, x: left + 10, w: 170, at: y)
            text(v, 9.5, x: left + 190, w: width - 190, at: y)
            y += h + 6
        }
        func subBar(_ s: String) {
            ensure(40)
            fill(CGRect(x: left, y: y, width: width, height: 18), RapportPDF.blueSoft)
            text(s, 10, RapportPDF.blue, weight: .bold, x: left + 8, w: width - 16, at: y + 3)
            y += 24
        }
    }

    // MARK: - Voorblad

    static func cover(_ d: Doc, project: Project, model: ProjectModel, photo: UIImage?) {
        let year = ProjectModel.year, end = year + Engine.horizon - 1
        d.newPage(header: false)
        d.logo(x: d.page.width - d.margin - 92, y: d.margin, size: 26)
        d.y = 150
        d.text("Meerjarenonderhoudsplan", 28, weight: .bold, x: d.left, w: d.width, advance: true)
        d.y += 4
        d.text("Planperiode \(year) – \(end)", 13, grey, weight: .semibold, x: d.left, w: d.width, advance: true)
        d.y += 26
        d.text(project.naam, 15, weight: .bold, x: d.left, w: d.width, advance: true)
        if let a = project.adres, a != project.naam { d.text(a, 13, x: d.left, w: d.width, advance: true) }
        let pc = [project.postcode, project.plaats].compactMap { $0 }.joined(separator: " ")
        if !pc.isEmpty { d.text(pc, 13, x: d.left, w: d.width, advance: true) }
        d.y += 24
        if let img = photo {
            let maxW = d.width, maxH: CGFloat = 340
            let k = min(maxW / img.size.width, maxH / img.size.height)
            let s = CGSize(width: img.size.width * k, height: img.size.height * k)
            img.draw(in: CGRect(x: d.left, y: d.y, width: s.width, height: s.height))
            d.y += s.height + 6
            d.text("Eigen gevelfoto", 8.5, grey, x: d.left, w: d.width, advance: true)
        }
        d.y = d.page.height - 150
        d.rule(d.y)
        d.y += 10
        d.text("Opgesteld met MJOP Live · printdatum \(printDate)", 9, grey, x: d.left, w: d.width, advance: true)
        d.text("Indicatie: \(model.beoordeeld) van \(model.elements.count) posten beoordeeld. Geraamd met standaardbedragen en eigen beoordelingen; geen gecertificeerde NEN 2767-inspectie.",
               9, grey, x: d.left, w: d.width, advance: true)
    }

    // MARK: - Algemene objectgegevens

    static func objectData(_ d: Doc, project: Project, model: ProjectModel) {
        let year = ProjectModel.year, end = year + Engine.horizon - 1
        let b = model.building
        d.newPage()
        d.bar("Algemene objectgegevens")
        d.subBar("Object")
        d.field("Naam", project.naam)
        d.field("Adres", project.adres ?? "onbekend")
        d.field("Postcode en plaats", [project.postcode, project.plaats].compactMap { $0 }.joined(separator: " ").nonEmpty ?? "onbekend")
        d.y += 4
        d.subBar("Technisch")
        d.field("Bouwjaar", b.bouwjaar.map(String.init) ?? "onbekend")
        d.field("Appartementen", "\(b.units)" + (b.unitsBAG.map { $0 == b.units ? " (BAG)" : " (BAG: \($0))" } ?? ""))
        d.field("Bebouwd oppervlak", m2(b.footprintM2))
        d.field("Buitenmuur", m2(b.buitenmuurM2))
        d.field("Dak plat · hellend", "\(m2(b.dakPlatM2)) · \(m2(b.dakSchuinM2))")
        d.field("Hoogte", b.hoogteM.map { (qtyFormat.string(from: NSNumber(value: $0)) ?? "\($0)") + " m" } ?? "onbekend")
        d.field("Gescand", (model.roof == nil ? "dak niet gescand" : "dak gescand") + " · \(Set(model.gevels.map(\.sideId)).count) gevel(s) gescand")
        d.y += 4
        d.subBar("Financieel")
        d.field("Planperiode", "\(year) – \(end) (\(Engine.horizon) jaar)")
        d.field("Prijspeil", "\(year); bedragen zijn niet geïndexeerd")
        d.field("Btw", "niet apart gespecificeerd in de standaardbedragen")
        d.field("Geraamd onderhoud", euro(model.total))
        d.field("Duurste jaar", model.peak.map { "\($0.jaar) · \(euro($0.bedrag))" } ?? "onbekend")
        d.field("Reservefonds (saldo nu)", model.fonds.map(euro) ?? "niet ingevuld")
        d.field("Bijdrage per appartement per maand", model.bijdrage.map(euro) ?? "niet ingevuld")
        d.field("Nodig om niet onder € 0 te komen", model.required.map { DSFormat.euros($0) + " per appartement per maand" } ?? "onbekend (saldo niet ingevuld)")
        d.field("Laagste stand reservefonds", model.fund?.min { $0.saldo < $1.saldo }.map { "\(euro($0.saldo)) in \($0.jaar)" } ?? "onbekend")
        d.y += 4
        d.subBar("Opmerkingen")
        let notes = [
            "Gebouwgegevens uit de BAG en de 3D BAG (TU Delft). Een geschat oppervlak is in de app als schatting gemarkeerd.",
            "Kosten zijn geraamd met standaardbedragen (prijspeil \(year)), tenzij een post een prijs uit een offerte heeft. Oude MJOP-bedragen gelden niet als actuele prijs. Exclusief onvoorziene kosten.",
            "Posten zonder beoordeling volgen de gebruikelijke levensduur. Beoordelingen volgen een vereenvoudigde NEN 2767-schaal en zijn door de gebruiker gegeven; dit is geen gecertificeerde inspectie.",
            model.gevels.isEmpty ? "Er zijn nog geen gevels gescand." : "Gevels gescand met gevelfoto's: elementen herkend door Claude en door de gebruiker gecontroleerd, maten berekend met vaste regels uit de gevelbreedte van de BAG.",
            "Niet beoordeeld: onderdelen die niet op een foto of luchtfoto te zien zijn (binnen, installaties, constructie). Specialistisch onderzoek (asbest, constructie, installaties) valt buiten dit plan.",
        ]
        for n in notes {
            let h = d.height("• " + n, 9, w: d.width - 10)
            d.ensure(h + 4)
            d.text("• " + n, 9, x: d.left + 10, w: d.width - 10, advance: true); d.y += 4
        }
    }

    // MARK: - Elementenoverzicht

    static func elementOverview(_ d: Doc, model: ProjectModel) {
        let table = MeerjarenTabel.make(elements: model.elements, year: ProjectModel.year)
        d.newPage()
        d.sectionTitle("Elementenoverzicht")
        d.explanation([("Code", "De NL-SfB-code van het element."), ("Element", "Het onderdeel van het gebouw dat onderhoud vraagt."),
                       ("Hoeveelheid", "Aantal met de meeteenheid; – als die onbekend is of de post een vast bedrag heeft."),
                       ("Cyclus", "Om de hoeveel jaar het onderhoud terugkomt."), ("Conditie", "De staat zoals door de gebruiker beoordeeld; – is nog niet beoordeeld.")])
        d.conditionLegend()
        let cols: [CGFloat] = [d.left, d.left + 50, d.left + 300, d.left + 400, d.left + 455]
        func header() {
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blue)
            for (i, t) in ["Code", "Element", "Hvh Ehd", "Cyclus", "Conditie"].enumerated() {
                d.text(t, 8.5, .white, weight: .semibold, x: cols[i] + 4, w: 100, at: d.y + 4)
            }
            d.y += 20
        }
        d.ensure(60); header()
        d.repeatHeader = header
        for g in table.groups {
            d.ensure(40)
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blueSoft)
            d.text("\(g.code)   \(g.naam)", 10, weight: .bold, x: d.left + 4, w: d.width, at: d.y + 3)
            d.y += 20
            for (i, r) in g.rows.enumerated() {
                let h = max(d.height(r.naam, 8.5, w: 240), 11) + 6
                d.ensure(h)
                if i % 2 == 0 { d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: h), zebra) }
                d.text(r.sfb ?? "–", 8.5, grey, x: cols[0] + 4, w: 44, at: d.y + 3)
                d.text(r.naam, 8.5, x: cols[1] + 4, w: 240, at: d.y + 3)
                d.text(quantity(r.quantity, r.unit), 8.5, x: cols[2] + 4, w: 92, at: d.y + 3)
                d.text(r.cycles.map(String.init).joined(separator: "/") + " jr", 8.5, x: cols[3] + 4, w: 50, at: d.y + 3)
                d.badge(r.conditie, x: cols[4] + 4, y: d.y + (h - 13) / 2)
                d.text(condition(r.conditie).1, 8, grey, x: cols[4] + 28, w: 80, at: d.y + 3)
                d.y += h
            }
            d.y += 4
        }
        d.repeatHeader = nil
    }

    // MARK: - Bevindingen

    static func findings(_ d: Doc, model: ProjectModel, scanPhotos: [String: UIImage]) {
        var items: [(scan: FacadeScan, defect: FacadeDefect, location: String)] = []
        for g in model.gevels.sorted(by: { ($0.sideId, $0.part ?? 1) < ($1.sideId, $1.part ?? 1) }) where g.copiedFromSide == nil {
            for x in (g.defects ?? []).filter(\.isConfirmed) { items.append((g, x, "Gevel op het \(g.facing)" + (g.part.map { " · foto \($0)" } ?? ""))) }
        }
        if let r = model.roof { for x in (r.defects ?? []).filter(\.isConfirmed) { items.append((r, x, "Dak (luchtfoto)")) } }
        guard !items.isEmpty else { return }
        d.newPage()
        d.sectionTitle("Bevindingen")
        d.explanation([("Gebrek", "Een zichtbaar gebrek op een gevelfoto of de luchtfoto, als hint herkend en door de gebruiker bevestigd."),
                       ("Locatie", "De gevel of het dak en, als dat bekend is, het element waarop het gebrek ligt."),
                       ("Ernst, omvang, intensiteit", "Zoals door de gebruiker beoordeeld (NEN 2767-begrippen, vereenvoudigd)."),
                       ("", "Geen inspectie ter plaatse en geen gecertificeerde NEN 2767-inspectie.")])
        let order: [DefectSeverity?] = [.ernstig, .serieus, .gering, nil]
        for sev in order {
            let group = items.filter { $0.defect.ernst == sev }
            guard !group.isEmpty else { continue }
            d.ensure(160)
            let col: UIColor = sev == .ernstig ? condition(6).0 : sev == .serieus ? condition(4).0 : sev == .gering ? condition(2).0 : condition(nil).0
            d.bar("Ernst: " + (sev?.label ?? "niet beoordeeld"), color: col, size: 11)
            for it in group {
                let photo = it.scan.photoPath.flatMap { scanPhotos[$0] }
                let crop = photo.flatMap { cropAround($0, point: it.defect.point, photoWidth: it.scan.photoWidth) }
                let textW = d.width - (crop == nil ? 16 : 150)
                let el = DefectHints.element(at: it.defect.point, in: it.scan.elements, tolerance: 0.02 * it.scan.photoWidth)
                let noteH = it.defect.note.map { d.height($0, 9, w: textW) } ?? 0
                let h = max(crop == nil ? 0 : 128, 86 + noteH)
                d.ensure(h + 8)
                let top = d.y
                UIColor.white.setFill()
                let box = UIBezierPath(rect: CGRect(x: d.left, y: top, width: d.width, height: h)); line.setStroke(); box.lineWidth = 0.6; box.stroke()
                d.text(it.defect.type.label, 10, weight: .bold, x: d.left + 8, w: textW, at: top + 8)
                d.text(it.location + (el.map { " · " + $0.type.label.lowercased() + " \($0.id)" } ?? ""), 9, grey, x: d.left + 8, w: textW, at: top + 23)
                let heads = ["Ernst", "Omvang", "Intensiteit"]
                let vals = [it.defect.ernst?.label ?? "–", it.defect.omvang?.label ?? "–", it.defect.intensiteit?.label ?? "–"]
                let cw = min(textW / 3, 110)
                d.rule(top + 40, x: d.left + 8, w: cw * 3)
                for i in 0..<3 {
                    d.text(heads[i], 8, grey, x: d.left + 8 + CGFloat(i) * cw, w: cw, at: top + 43)
                    d.text(vals[i], 9, weight: .semibold, x: d.left + 8 + CGFloat(i) * cw, w: cw, at: top + 55)
                }
                d.rule(top + 70, x: d.left + 8, w: cw * 3)
                if let n = it.defect.note { d.text(n, 9, x: d.left + 8, w: textW, at: top + 76) }
                if let c = crop {
                    let s: CGFloat = 120
                    c.draw(in: CGRect(x: d.left + d.width - s - 4, y: top + 4, width: s, height: s))
                }
                d.y = top + h + 8
            }
        }
    }

    /// Vierkante uitsnede (een kwart van de fotobreedte) rond een punt in pixels van de foto zoals herkend.
    static func cropAround(_ img: UIImage, point: [Double], photoWidth: Double) -> UIImage? {
        guard point.count == 2, photoWidth > 0, let cg = img.cgImage else { return nil }
        let k = Double(cg.width) / photoWidth
        let side = Double(cg.width) * 0.25
        let x = min(max(point[0] * k - side / 2, 0), Double(cg.width) - side)
        let y = min(max(point[1] * k - side / 2, 0), max(Double(cg.height) - side, 0))
        guard let c = cg.cropping(to: CGRect(x: x, y: y, width: side, height: min(side, Double(cg.height)))) else { return nil }
        return UIImage(cgImage: c)
    }

    // MARK: - Meerjarentabel

    static func multiYear(_ d: Doc, table: MeerjarenTabel.Result) {
        let first = table.years.first ?? ProjectModel.year, last = table.years.last ?? first
        d.newPage(landscape: true)
        d.sectionTitle("Meerjarentabel \(first) – \(last)")
        d.explanation([("Element", "De post in het plan, gegroepeerd per NL-SfB-hoofdgroep."),
                       ("Hoeveelheid", "Aantal met de meeteenheid; – als die onbekend is of de post een vast bedrag heeft."),
                       ("Startjaar en cyclus", "Stj is het eerste jaar binnen de planperiode, Cy om de hoeveel jaar het onderhoud terugkomt. Een beoordeling schuift het startjaar."),
                       ("Bedragen", "De kosten van de beurt in dat jaar; per hoofdgroep een subtotaal en onderaan het totaal per jaar."),
                       ("Bedrag onbekend", "De kosten zijn niet te berekenen omdat een hoeveelheid ontbreekt; vul die in de app in. Zo'n post telt niet mee in de totalen.")])
        d.text("Bedragen op prijspeil \(first), niet geïndexeerd. Standaardbedragen tenzij gemarkeerd met (offerte). Printdatum \(printDate).", 8.5, grey, x: d.left, w: d.width, advance: true)

        let yearW: CGFloat = 40, totalW: CGFloat = 56
        let totalX = d.left + d.width - totalW
        let yearsX = totalX - CGFloat(table.years.count) * yearW
        let nameW = yearsX - d.left - 150
        let qtyX = d.left + 34 + nameW, stjX = qtyX + 70, cyX = stjX + 28
        func yearX(_ i: Int) -> CGFloat { yearsX + CGFloat(i) * yearW }
        func amounts(_ py: [Int: Decimal], total: String, size: CGFloat, weight: UIFont.Weight, at yy: CGFloat, zeros: Bool) {
            for (i, j) in table.years.enumerated() {
                if let v = py[j], v != 0 { d.text(euro(v), size, weight: weight, x: yearX(i), w: yearW - 3, align: .right, at: yy) }
                else if zeros { d.text("€ 0", size, grey, x: yearX(i), w: yearW - 3, align: .right, at: yy) }
            }
            d.text(total, size, weight: .bold, x: totalX, w: totalW - 3, align: .right, at: yy)
        }
        func header() {
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blue)
            d.text("Code / element", 7.5, .white, weight: .semibold, x: d.left + 3, w: 150, at: d.y + 4)
            d.text("Hvh Ehd", 7.5, .white, weight: .semibold, x: qtyX, w: 66, align: .right, at: d.y + 4)
            d.text("Stj", 7.5, .white, weight: .semibold, x: stjX + 4, w: 26, at: d.y + 4)
            d.text("Cy", 7.5, .white, weight: .semibold, x: cyX + 4, w: 24, at: d.y + 4)
            for (i, j) in table.years.enumerated() { d.text(String(j), 7.5, .white, weight: .semibold, x: yearX(i), w: yearW - 3, align: .right, at: d.y + 4) }
            d.text("Totaal", 7.5, .white, weight: .semibold, x: totalX, w: totalW - 3, align: .right, at: d.y + 4)
            d.y += 20
        }
        d.newPage(landscape: true)
        header()
        d.repeatHeader = header
        for g in table.groups {
            d.ensure(52)
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 16), blueSoft)
            d.text("\(g.code)   \(g.naam)", 9, weight: .bold, x: d.left + 3, w: 300, at: d.y + 2.5)
            d.y += 18
            for (i, r) in g.rows.enumerated() {
                let name = r.naam + (r.fromQuote ? " (offerte)" : "")
                let h = max(d.height(name, 7.5, w: nameW - 4), 10) + 5
                d.ensure(h)
                if i % 2 == 0 { d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: h), zebra) }
                let yy = d.y + 2.5
                d.text(r.sfb ?? "–", 7.5, grey, x: d.left + 3, w: 30, at: yy)
                d.text(name, 7.5, x: d.left + 34, w: nameW - 4, at: yy)
                d.text(quantity(r.quantity, r.unit), 7.5, x: qtyX, w: 66, align: .right, at: yy)
                d.text(r.startYear.map(String.init) ?? "–", 7.5, x: stjX + 4, w: 26, at: yy)
                d.text(r.cycles.map(String.init).joined(separator: "/"), 7.5, x: cyX + 4, w: 24, at: yy)
                if r.costUnknown {
                    d.text("bedrag onbekend", 7.5, condition(5).0, weight: .semibold, x: yearsX, w: CGFloat(table.years.count) * yearW + totalW - 3, align: .right, at: yy)
                } else {
                    amounts(r.perYear, total: euro(r.total), size: 7.5, weight: .regular, at: yy, zeros: false)
                }
                d.y += h
            }
            d.ensure(16)
            d.rule(d.y + 1, x: yearsX, w: d.left + d.width - yearsX, color: ink, thickness: 0.6)
            amounts(g.perYear, total: euro(g.total), size: 7.5, weight: .semibold, at: d.y + 3, zeros: true)
            d.y += 20
        }
        d.ensure(24)
        d.rule(d.y, color: ink, thickness: 1)
        d.text("Totaal", 9, weight: .bold, x: d.left + 3, w: 150, at: d.y + 5)
        amounts(table.perYear, total: euro(table.total), size: 7.5, weight: .bold, at: d.y + 6, zeros: true)
        d.y += 22
        if table.hasUnknown {
            d.text("Let op: posten met \"bedrag onbekend\" tellen niet mee in de totalen.", 8.5, condition(5).0, weight: .semibold, x: d.left, w: d.width, advance: true)
        }
        d.repeatHeader = nil
    }

    static func mainGroups(_ d: Doc, table: MeerjarenTabel.Result) {
        d.newPage(landscape: true)
        d.sectionTitle("Meerjarentabel per hoofdgroep", 14)
        let yearW: CGFloat = 46, totalW: CGFloat = 62
        let totalX = d.left + d.width - totalW
        let yearsX = totalX - CGFloat(table.years.count) * yearW
        func header() {
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blue)
            d.text("Code", 8, .white, weight: .semibold, x: d.left + 3, w: 40, at: d.y + 4)
            d.text("Hoofdgroep", 8, .white, weight: .semibold, x: d.left + 40, w: 200, at: d.y + 4)
            for (i, j) in table.years.enumerated() { d.text(String(j), 8, .white, weight: .semibold, x: yearsX + CGFloat(i) * yearW, w: yearW - 3, align: .right, at: d.y + 4) }
            d.text("Totaal", 8, .white, weight: .semibold, x: totalX, w: totalW - 3, align: .right, at: d.y + 4)
            d.y += 22
        }
        header()
        d.repeatHeader = header
        for (n, g) in table.groups.enumerated() {
            d.ensure(18)
            if n % 2 == 0 { d.fill(CGRect(x: d.left, y: d.y - 2, width: d.width, height: 17), zebra) }
            d.text(g.code, 8, grey, x: d.left + 3, w: 36, at: d.y + 1)
            d.text(g.naam + (g.hasUnknown ? " *" : ""), 8, x: d.left + 40, w: yearsX - d.left - 44, at: d.y + 1)
            for (i, j) in table.years.enumerated() where (g.perYear[j] ?? 0) != 0 {
                d.text(euro(g.perYear[j]!), 8, x: yearsX + CGFloat(i) * yearW, w: yearW - 3, align: .right, at: d.y + 1)
            }
            d.text(euro(g.total), 8, weight: .semibold, x: totalX, w: totalW - 3, align: .right, at: d.y + 1)
            d.y += 17
        }
        d.ensure(26)
        d.y += 6
        d.rule(d.y, color: ink, thickness: 1)
        d.text("Totaal", 9, weight: .bold, x: d.left + 3, w: 150, at: d.y + 5)
        for (i, j) in table.years.enumerated() {
            d.text(euro(table.perYear[j] ?? 0), 8, weight: .bold, x: yearsX + CGFloat(i) * yearW, w: yearW - 3, align: .right, at: d.y + 6)
        }
        d.text(euro(table.total), 8, weight: .bold, x: totalX, w: totalW - 3, align: .right, at: d.y + 6)
        d.y += 24
        if table.hasUnknown { d.text("* Bevat een post met een onbekend bedrag; die telt niet mee.", 8.5, grey, x: d.left, w: d.width, advance: true) }
        d.repeatHeader = nil
    }

    // MARK: - Jaarplan

    static func yearPlan(_ d: Doc, table: MeerjarenTabel.Result, year: Int) {
        d.newPage()
        d.sectionTitle("Jaarplan \(year)")
        let groups = table.groups.compactMap { g -> (MeerjarenTabel.Group, [MeerjarenTabel.Row])? in
            let rows = g.rows.filter { ($0.perYear[year] ?? 0) != 0 }
            return rows.isEmpty ? nil : (g, rows)
        }
        guard !groups.isEmpty else {
            d.text("In \(year) is geen onderhoud gepland.", 10, x: d.left, w: d.width, advance: true)
            return
        }
        let cols: [CGFloat] = [d.left, d.left + 50, d.left + 340, d.left + 430]
        func header() {
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blue)
            d.text("Code", 8.5, .white, weight: .semibold, x: cols[0] + 4, w: 44, at: d.y + 4)
            d.text("Element", 8.5, .white, weight: .semibold, x: cols[1] + 4, w: 280, at: d.y + 4)
            d.text("Hvh Ehd", 8.5, .white, weight: .semibold, x: cols[2], w: 84, align: .right, at: d.y + 4)
            d.text(String(year), 8.5, .white, weight: .semibold, x: cols[3], w: d.left + d.width - cols[3] - 4, align: .right, at: d.y + 4)
            d.y += 20
        }
        header()
        d.repeatHeader = header
        for (g, rows) in groups {
            d.ensure(36)
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blueSoft)
            d.text("\(g.code)   \(g.naam)", 10, weight: .bold, x: d.left + 4, w: d.width, at: d.y + 3)
            d.y += 20
            for (i, r) in rows.enumerated() {
                let h = max(d.height(r.naam, 9, w: 280), 11) + 6
                d.ensure(h)
                if i % 2 == 0 { d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: h), zebra) }
                d.text(r.sfb ?? "–", 9, grey, x: cols[0] + 4, w: 44, at: d.y + 3)
                d.text(r.naam + (r.fromQuote ? " (offerte)" : ""), 9, x: cols[1] + 4, w: 280, at: d.y + 3)
                d.text(quantity(r.quantity, r.unit), 9, x: cols[2], w: 84, align: .right, at: d.y + 3)
                d.text(euro(r.perYear[year] ?? 0), 9, x: cols[3], w: d.left + d.width - cols[3] - 4, align: .right, at: d.y + 3)
                d.y += h
            }
        }
        d.ensure(30)
        d.y += 6
        d.rule(d.y, color: ink, thickness: 1)
        d.text("Totaal \(year)", 10, weight: .bold, x: d.left + 4, w: 200, at: d.y + 6)
        d.text(euro(table.perYear[year] ?? 0), 10, weight: .bold, x: cols[3], w: d.left + d.width - cols[3] - 4, align: .right, at: d.y + 6)
        d.y += 26
        d.repeatHeader = nil
    }

    // MARK: - Reservefonds

    static func fund(_ d: Doc, model: ProjectModel) {
        d.ensure(140)
        d.y += 10
        d.sectionTitle("Reservefonds", 14)
        guard let fund = model.fund else {
            d.text("Het verloop van het reservefonds is niet te berekenen: vul in de app het saldo en de maandelijkse bijdrage in.", 9.5, grey, x: d.left, w: d.width, advance: true)
            return
        }
        d.text("Saldo nu \(model.fonds.map(euro) ?? "–"), bijdrage \(model.bijdrage.map(euro) ?? "–") per appartement per maand, \(model.units) appartement(en). Zonder rente en indexatie.",
               9, grey, x: d.left, w: d.width, advance: true)
        d.y += 6
        let cols: [CGFloat] = [d.left, d.left + 120, d.left + 300]
        func header() {
            d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 18), blue)
            d.text("Jaar", 8.5, .white, weight: .semibold, x: cols[0] + 4, w: 100, at: d.y + 4)
            d.text("Uitgaven", 8.5, .white, weight: .semibold, x: cols[1], w: 160, align: .right, at: d.y + 4)
            d.text("Saldo eind van het jaar", 8.5, .white, weight: .semibold, x: cols[2], w: d.left + d.width - cols[2] - 4, align: .right, at: d.y + 4)
            d.y += 20
        }
        d.ensure(40); header()
        d.repeatHeader = header
        for (i, f) in fund.enumerated() {
            d.ensure(16)
            if i % 2 == 0 { d.fill(CGRect(x: d.left, y: d.y, width: d.width, height: 16), zebra) }
            d.text(String(f.jaar), 9, x: cols[0] + 4, w: 100, at: d.y + 2)
            d.text(euro(f.kosten), 9, x: cols[1], w: 160, align: .right, at: d.y + 2)
            d.text(euro(f.saldo), 9, f.saldo < 0 ? condition(6).0 : ink, weight: .semibold, x: cols[2], w: d.left + d.width - cols[2] - 4, align: .right, at: d.y + 2)
            d.y += 16
        }
        d.repeatHeader = nil
    }

    // MARK: - Elementen per gevel en dak, staat van het dak

    static func measured(_ d: Doc, model: ProjectModel) {
        var sides: [(title: String, measures: [ElementMeasure])] = model.sideResults.filter { !$0.measures.isEmpty }.map { r in
            let facing = model.sides.first { $0.id == r.sideId }?.facing ?? "?"
            let copied = r.parts.first?.copiedFromSide != nil
            return ("Gevel op het \(facing)" + (copied ? " (overgenomen van een gelijke gevel, aanname)" : ""), r.measures)
        }
        if let roof = model.roof, !roof.elementMeasures.isEmpty { sides.insert(("Dak (PDOK-luchtfoto, helling uit de 3D BAG)", roof.elementMeasures), at: 0) }
        let roofDefects = (model.roof?.defects ?? []).filter(\.isConfirmed)
        let advice = model.roofAdvice
        guard !sides.isEmpty || advice != nil || !roofDefects.isEmpty else { return }
        d.newPage()
        if !sides.isEmpty {
            d.sectionTitle("Elementen per gevel en dak")
            let leftW: CGFloat = 300
            for r in sides {
                d.ensure(60)
                d.subBar(r.title)
                for g in ElementList.groups(r.measures) {
                    d.ensure(30)
                    d.rule(d.y); d.y += 3
                    let l = "\(g.type.label) · \(g.count) st" + (g.materials.isEmpty ? "" : " · " + g.materials.joined(separator: ", "))
                    let rt = ElementFormat.total(g) + (ElementFormat.totalBand(g).map { "  " + $0 } ?? "")
                    d.text(l, 9.5, weight: .semibold, x: d.left, w: leftW)
                    d.text(rt, 9.5, weight: .semibold, x: d.left + leftW, w: d.width - leftW, align: .right, advance: true)
                    for m in g.items {
                        d.ensure(13)
                        d.text(ElementFormat.name(m) + (m.material.map { " · \($0)" } ?? ""), 8.5, grey, x: d.left + 14, w: leftW - 14)
                        d.text(ElementFormat.value(m) + (ElementFormat.band(m).map { "  " + $0 } ?? ""), 8.5, grey, x: d.left + leftW, w: d.width - leftW, align: .right, advance: true)
                    }
                    d.y += 3
                }
                d.y += 8
            }
            d.ensure(30)
            d.text("Maten berekend uit gevelfoto's met de gevelbreedte uit de BAG en uit de PDOK-luchtfoto; ± volgens vaste regels. Een voorstel, geen inmeting.", 8.5, grey, x: d.left, w: d.width, advance: true)
            d.y += 14
        }
        if advice != nil || !roofDefects.isEmpty {
            d.ensure(90)
            d.sectionTitle("Staat van het dak", 14)
            for x in roofDefects {
                d.ensure(22)
                d.text("• " + x.type.label + (DefectHints.assessment(x).map { " — " + $0 } ?? "") + (x.note.map { " (\($0))" } ?? ""), 9.5, x: d.left, w: d.width, advance: true)
            }
            if let a = advice {
                d.ensure(22)
                d.text("Advies: dakinspectie in \(a.year). " + a.reasons.joined(separator: "; ") + ".", 9.5, weight: .semibold, x: d.left, w: d.width, advance: true)
            }
            d.text("Hints uit een luchtfoto, bevestigd door de gebruiker; geen inspectie ter plaatse en geen NEN 2767-certificering.", 8.5, grey, x: d.left, w: d.width, advance: true)
        }
    }

    // MARK: - Bijlage

    static func appendix(_ d: Doc, photos: [(String, UIImage)]) {
        guard !photos.isEmpty else { return }
        d.newPage()
        d.sectionTitle("Bijlage: gevelfoto's")
        for (caption, img) in photos {
            let k = min(d.width / img.size.width, 330 / img.size.height)
            let s = CGSize(width: img.size.width * k, height: img.size.height * k)
            d.ensure(s.height + 30)
            img.draw(in: CGRect(x: d.left, y: d.y, width: s.width, height: s.height))
            d.y += s.height + 4
            d.text(caption, 9, grey, x: d.left, w: d.width, advance: true)
            d.y += 14
        }
    }
}

private extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
