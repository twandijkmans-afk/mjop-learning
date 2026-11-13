import Foundation

// Documenten in een project (oud MJOP, offerte, factuur, inspectierapport): Claude leest het document en zet wat het vindt klaar als voorstel,
// met pagina en letterlijke tekst als bron. Niets wordt automatisch overgenomen; de gebruiker beslist per voorstel.
// Regels (CLAUDE.md van mjop-learning): onbekend blijft nil, oude bedragen uit een oud MJOP gelden nooit als actuele prijs,
// tegenstrijdigheden worden getoond (huidige waarde naast documentwaarde), niet automatisch opgelost.

public enum DocumentKind: String, Codable, CaseIterable {
    case oudMJOP = "oud_mjop", offerte, factuur, inspectie, overig

    public var label: String {
        switch self {
        case .oudMJOP: return "Oud MJOP"
        case .offerte: return "Offerte"
        case .factuur: return "Factuur"
        case .inspectie: return "Inspectierapport"
        case .overig: return "Document"
        }
    }
}

/// Wat een voorstel wil veranderen in een post.
public enum ProposalField: String, Codable {
    /// Hoeveelheid (oud MJOP, offerte, inspectie).
    case hoeveelheid
    /// Jaar waarin het onderhoud het laatst is uitgevoerd (factuur, oud MJOP).
    case laatstUitgevoerd = "laatst_uitgevoerd"
    /// Onderhoudscyclus in jaren (oud MJOP).
    case cyclus
    /// Prijs van één beurt uit een offerte (actuele prijs).
    case prijs
    /// Staat volgens NEN 2767 (inspectierapport).
    case conditie
}

public enum ProposalStatus: String, Codable { case open, overgenomen, afgewezen }

public struct DocumentProposal: Codable, Equatable, Identifiable {
    public var id: String
    /// De post in het plan waar dit bij hoort (sleutel uit de bibliotheek), nil = niet herkend.
    public var elementKey: String?
    /// De naam zoals in het document.
    public var documentNaam: String
    public var field: ProposalField
    /// Getal uit het document (hoeveelheid, jaar, cyclus, bedrag, conditie).
    public var value: Double
    public var unit: String?
    /// Prijspeil of datum van het document (jaar), voor bedragen.
    public var jaar: Int?
    public var page: Int?
    public var quote: String
    public var confidence: String?
    public var status: ProposalStatus = .open

    public init(id: String, elementKey: String?, documentNaam: String, field: ProposalField, value: Double, unit: String?, jaar: Int?, page: Int?, quote: String, confidence: String?) {
        self.id = id; self.elementKey = elementKey; self.documentNaam = documentNaam; self.field = field; self.value = value
        self.unit = unit; self.jaar = jaar; self.page = page; self.quote = quote; self.confidence = confidence
    }
}

public struct ProjectDocument: Codable, Equatable, Identifiable {
    public var id: String
    public var naam: String
    public var kind: DocumentKind
    public var pages: Int?
    public var addedAt: Date
    public var proposals: [DocumentProposal]
    public var skipped: Int
    public var model: String
    public var promptVersion: String

    public init(id: String, naam: String, kind: DocumentKind, pages: Int?, addedAt: Date, proposals: [DocumentProposal], skipped: Int, model: String, promptVersion: String) {
        self.id = id; self.naam = naam; self.kind = kind; self.pages = pages; self.addedAt = addedAt; self.proposals = proposals
        self.skipped = skipped; self.model = model; self.promptVersion = promptVersion
    }

    public var openCount: Int { proposals.filter { $0.status == .open }.count }
}

public enum DocumentExtraction {
    public static let promptVersion = "documenten_v0.1"
    public static let model = "claude-opus-5-5"

    public static func prompt(kind: DocumentKind?) -> String {
        let keys = Engine.library.map { "- \($0.key): \($0.naam)" }.joined(separator: "\n")
        return """
        This document belongs to a Dutch apartment building (VvE) and is used to update its multi-year maintenance plan (MJOP).\(kind.map { " The user says it is: \($0.label)." } ?? "")

        First decide what kind of document it is: "oud_mjop" (an older maintenance plan), "offerte" (a quote from a contractor), "factuur" (an invoice for work that was done), "inspectie" (an inspection or condition report) or "overig".

        Then list the facts in it that matter for the maintenance plan. Each fact is ONE number about ONE maintenance item:
        - "hoeveelheid": a quantity (m2, m1, st, app) of an item.
        - "laatst_uitgevoerd": the year the work on an item was last carried out (for an invoice: the year of the work).
        - "cyclus": the maintenance cycle of an item in years.
        - "prijs": the price of carrying out the work on an item once, in euros excluding VAT if stated, from a QUOTE only. Put the quote date year in "jaar".
        - "conditie": a condition score 1 (excellent) to 6 (very poor) per NEN 2767, from an inspection only.

        Map each item to the closest key from this list, or use null when none fits:
        \(keys)

        Rules:
        - Report only what is literally in the document. Never estimate, convert or calculate a number that is not printed.
        - For an old MJOP, do NOT report prices: old amounts are not current prices. Report quantities, cycles and last-done years only.
        - "page" is the 1-based page number where the fact is printed. "quote" is the exact text (max 160 characters) that shows the fact.
        - "confidence": low, medium or high.

        Return only a JSON object of this shape, with no other text:
        {"kind": "oud_mjop|offerte|factuur|inspectie|overig", "facts": [{"element_key": "<key or null>", "name": "<item name as in the document>", "field": "hoeveelheid|laatst_uitgevoerd|cyclus|prijs|conditie", "value": 0, "unit": "<m2|m1|st|app|jaar|eur|null>", "year": 0, "page": 1, "quote": "", "confidence": "low|medium|high"}]}
        """
    }

    public static func requestBody(pdfBase64: String?, imagesJPEGBase64: [String], kind: DocumentKind?) -> [String: Any] {
        var content: [[String: Any]] = []
        if let pdf = pdfBase64 { content.append(["type": "document", "source": ["type": "base64", "media_type": "application/pdf", "data": pdf]]) }
        for img in imagesJPEGBase64 { content.append(["type": "image", "source": ["type": "base64", "media_type": "image/jpeg", "data": img]]) }
        content.append(["type": "text", "text": prompt(kind: kind)])
        return ["model": model, "max_tokens": 16000, "output_config": ["effort": "high"], "messages": [["role": "user", "content": content]]]
    }

    /// Leest het antwoord. Ongeldige feiten worden overgeslagen en geteld; een prijs uit een oud MJOP wordt altijd overgeslagen.
    public static func parse(_ data: Data, fallbackKind: DocumentKind) throws -> (kind: DocumentKind, proposals: [DocumentProposal], skipped: Int) {
        guard let o = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { throw FacadeError.unreadable }
        if (o["stop_reason"] as? String) == "refusal" { throw FacadeError.refused }
        if (o["stop_reason"] as? String) == "max_tokens" { throw FacadeError.truncated }
        let text = ((o["content"] as? [[String: Any]]) ?? []).filter { ($0["type"] as? String) == "text" }.compactMap { $0["text"] as? String }.joined()
        var obj = (try? JSONSerialization.jsonObject(with: Data(text.utf8))) as? [String: Any]
        if obj == nil, let s = text.firstIndex(of: "{"), let e = text.lastIndex(of: "}"), s < e {
            obj = (try? JSONSerialization.jsonObject(with: Data(text[s...e].utf8))) as? [String: Any]
        }
        guard let obj, let facts = obj["facts"] as? [[String: Any]] else { throw FacadeError.unreadable }
        let kind = (obj["kind"] as? String).flatMap(DocumentKind.init(rawValue:)) ?? fallbackKind
        let r = parseFacts(facts, kind: kind)
        return (kind, r.proposals, r.skipped)
    }

    public static func parseFacts(_ facts: [[String: Any]], kind: DocumentKind) -> (proposals: [DocumentProposal], skipped: Int) {
        let keys = Set(Engine.library.map(\.key))
        var out: [DocumentProposal] = []
        var skipped = 0
        for (i, f) in facts.enumerated() {
            guard let fs = f["field"] as? String, let field = ProposalField(rawValue: fs),
                  let v = (f["value"] as? NSNumber)?.doubleValue, v.isFinite, v >= 0,
                  let quote = (f["quote"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !quote.isEmpty else { skipped += 1; continue }
            if field == .prijs && kind != .offerte { skipped += 1; continue }           // oude of andere bedragen zijn geen actuele prijs
            if field == .conditie && !(1...6).contains(Int(v)) { skipped += 1; continue }
            if field == .laatstUitgevoerd && !(1900...2100).contains(Int(v)) { skipped += 1; continue }
            if field == .cyclus && !(1...100).contains(Int(v)) { skipped += 1; continue }
            let name = ((f["name"] as? String) ?? "").trimmingCharacters(in: .whitespaces)
            var key = (f["element_key"] as? String).flatMap { keys.contains($0) ? $0 : nil }
            if key == nil { key = matchElement(name) }
            let year = ((f["year"] as? NSNumber)?.intValue).flatMap { (1900...2100).contains($0) ? $0 : nil }
            let page = ((f["page"] as? NSNumber)?.intValue).flatMap { $0 > 0 ? $0 : nil }
            let conf = (f["confidence"] as? String).flatMap { ["low", "medium", "high"].contains($0) ? $0 : nil }
            out.append(DocumentProposal(id: "p\(i + 1)", elementKey: key, documentNaam: String(name.prefix(120)), field: field, value: v,
                                        unit: (f["unit"] as? String).flatMap { $0.isEmpty || $0 == "null" ? nil : $0 }, jaar: year, page: page,
                                        quote: String(quote.prefix(160)), confidence: conf))
        }
        return (out, skipped)
    }

    /// Koppelt een naam uit een document aan een post uit de bibliotheek op trefwoorden; nil als het niet duidelijk is (niet gokken).
    public static func matchElement(_ name: String) -> String? {
        let n = name.lowercased()
        let rules: [(String, [String])] = [
            ("dak-hellend", ["pannen", "hellend dak", "dakpan"]),
            ("dak-plat", ["bitumen", "dakbedekking", "plat dak", "epdm"]),
            ("dakgoten", ["goot", "goten", "hemelwaterafvoer", "hwa", "zinkwerk"]),
            ("schilderwerk-buiten", ["schilder", "verfwerk", "buitenschilder"]),
            ("kozijnen-onderhoud", ["kozijn"]),
            ("gevel-metselwerk", ["metselwerk", "gevelreiniging", "gevel reinigen"]),
            ("voegwerk", ["voegwerk", "voegen"]),
            ("steiger", ["steiger", "hoogwerker"]),
            ("intercom", ["intercom", "deurbel", "deuropener"]),
            ("riolering", ["riool", "riolering"]),
            ("trappenhuis", ["trappenhuis", "entree", "portiek"]),
            ("cv-installatie", ["cv", "ketel", "verwarming"]),
            ("lift", ["lift"]),
        ]
        let hits = rules.filter { _, words in words.contains { n.contains($0) } }.map(\.0)
        return hits.count == 1 ? hits[0] : nil
    }

    /// De huidige waarde in het plan voor dit voorstel, als tekst, om naast de documentwaarde te tonen.
    public static func currentValue(_ p: DocumentProposal, in elements: [PlanElement]) -> String {
        guard let el = elements.first(where: { $0.key == p.elementKey }) else { return "geen post" }
        switch p.field {
        case .hoeveelheid: return el.quantity?.value.map { "\($0) \(el.quantity?.unit ?? "")" } ?? "onbekend"
        case .laatstUitgevoerd: return String(el.laatsteBeurt)
        case .cyclus: return "\(el.cyclus) jaar"
        case .prijs: return Engine.cost(el).map { "€ \(Engine.roundEuro($0))" } ?? "onbekend"
        case .conditie: return el.conditie.map(String.init) ?? "niet beoordeeld"
        }
    }

    /// Past een overgenomen voorstel toe op de posten. Geeft false als het niet kan (geen post).
    @discardableResult
    public static func apply(_ p: DocumentProposal, documentNaam: String, to elements: inout [PlanElement]) -> Bool {
        guard let i = elements.firstIndex(where: { $0.key == p.elementKey }) else { return false }
        let bron = "\(documentNaam)\(p.page.map { ", pagina \($0)" } ?? "")"
        let v = Decimal(string: String(format: "%.2f", p.value)) ?? Decimal(p.value)
        switch p.field {
        case .hoeveelheid:
            if elements[i].type == .kozijnen { return false }
            elements[i].quantity = Quantity(value: v, unit: p.unit ?? elements[i].quantity?.unit ?? "", source: .document, basis: "Uit document: \(bron).")
        case .laatstUitgevoerd: elements[i].laatsteBeurt = Int(p.value)
        case .cyclus: elements[i].cyclus = Int(p.value)
        case .prijs:
            elements[i].prijsOfferte = Engine.roundEuro(v)
            elements[i].prijsBron = "Offerte: \(bron)\(p.jaar.map { ", prijspeil \($0)" } ?? "")"
        case .conditie: elements[i].conditie = Int(p.value)
        }
        return true
    }
}
