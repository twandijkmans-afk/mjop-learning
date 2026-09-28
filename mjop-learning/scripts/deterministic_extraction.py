#!/usr/bin/env python3
"""
deterministic_extraction.py - deterministische extractieroute (geen AI-API, geen netwerk).

Aangeroepen via:  python3 scripts/extract_batch.py --mode deterministic --document DOC-010

Architectuur (docs/deterministic_extraction_v1.md, beslissingen C1/C3):

  bronbestand
    -> document_registry            (sha256-controle; ID's staan vast)
    -> mjop_source_sections          (LEIDENDE waarden: jarenplan-rijen, prijspeil, BTW, indexatie)
    -> documentprofiel-regels        (alleen voor wat de bronlaag niet levert:
                                      objectblad-gebouwvelden, elementenoverzicht, conditielegenda)
    -> text_layer                    (ALLEEN aanvullende block-provenance, nooit een waarde)
    -> bestaande schemas + record_validation
    -> bestaande reviewlaag (export_review_sheet / apply_review)

Harde regels:
  - Vereist xpdf pdftotext 4.06 (-table). Ontbreekt die of is het een andere
    variant/versie (bijv. poppler, xpdf 3.04): vroeg en duidelijk falen. Geen
    fallback naar een andere parser, geen download/installatie.
  - Niets gokken: ontbrekend -> null; onzeker -> requires_human_review.
    building_type, materiaal, bouwjaar per element, gemeenschappelijk/prive,
    unit_cost en cost_year worden niet ingevuld of afgeleid.
  - Bedragen via nl_values: generiek conservatief; alleen de expliciete
    documentprofielregel (bijv. pdf_whole_euro_dot_thousands) mag '1.351'
    als 1351 lezen, en alleen met documentbewijs. De regel staat in
    provenance.extraction_rule.
  - Output alleen naar een pilotmap (standaard data/extracted/_deterministic_pilot/);
    canonieke bestanden in data/extracted, data/normalized en data/verified
    worden nooit geschreven.
  - Geen tijdstempels in de output: twee runs op dezelfde invoer zijn byte-identiek.
"""
import json
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import document_registry  # noqa: E402
import mjop_source_sections as src  # noqa: E402
import nl_values as nv  # noqa: E402
import record_validation as rv  # noqa: E402
import text_layer as tl  # noqa: E402

EXTRACTOR_VERSION = "deterministic_extraction_v1.0.0"
RULES_VERSION = "pro_vve_overzicht_rules_v1"
REQUIRED_PDFTOTEXT = "4.06"
REQUIRED_PDFTOTEXT_RE = re.compile(r"^pdftotext version 4\.06 \[www\.xpdfreader\.com\]$")
PILOT_SUBDIR = os.path.join("data", "extracted", "_deterministic_pilot")
CANONICAL_DIRS = (os.path.join("data", "extracted"), os.path.join("data", "normalized"),
                  os.path.join("data", "verified"))

# Expliciete documentprofielen. Alleen documenten die hier staan kunnen deterministisch
# worden geëxtraheerd; een profiel wordt pas toegevoegd na beoordeling van het bronformaat.
DOCUMENT_PROFILES = {
    "DOC-010": {
        "profile_id": "pro_vve_overzicht15",
        "profile_version": "1.0.0",
        "currency_rule": "pdf_whole_euro_dot_thousands",
        "note": "Pilot. Objectblad + Elementenoverzicht + Overzicht 15 - Jarenplan (Gedetailleerd); "
                "bedragen in hele euro's met punt als duizendtal (bewijs: whole_euro_evidence).",
    },
}

OBJECT_LABELS = [
    # (sectie, label, doel, veld, type)
    ("Object", "Naam", "document", "object_name", "text"),
    ("Object", "Aantal eenheden", "building", "number_of_units", "integer"),
    ("Object", "Adres", "building", "address", "text"),
    ("Object", "Postcode", "document", "object_postcode", "text"),
    ("Object", "Plaats", "document", "object_city", "text"),
    ("Object", "Inspectiedatum", "building", "inspection_date", "date"),
    ("Technisch", "Bouwjaar", "building", "construction_year", "year"),
    ("Technisch", "Renovatiejaar", "document", "renovation_year", "year"),
]
OBJECT_SECTIONS = {"Code", "Object", "Opdrachtgever", "Technisch", "Financieel", "Overige"}
LEGEND_RE = re.compile(r"^\s*(\d)\s+=\s+(\S.*?)\s*$")
QTY_UNIT_RE = re.compile(r"^(\d[\d.]*,\d{2})(\S*)$")
CODE_RE = re.compile(r"^(\d{4}|ZZZZ)$")
GROUP_RE = re.compile(r"^(\d{2}|ZZ)$")


class DependencyError(RuntimeError):
    pass


class ExtractionError(RuntimeError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


# ------------------------------------------------------------------ dependency

def check_pdftotext(explicit=None):
    """Controleert dat xpdf pdftotext 4.06 beschikbaar is. Returns (binary, versieregel).
    Faalt met DependencyError als het programma ontbreekt of een andere variant/versie is.
    Downloadt of installeert nooit iets."""
    binary = src.find_pdftotext(explicit)
    hint = ("De deterministische route vereist xpdf pdftotext 4.06 (www.xpdfreader.com) met "
            "'-table'-ondersteuning. Installeer xpdf-tools 4.06 lokaal en geef het pad mee met "
            "--pdftotext of de omgevingsvariabele PDFTOTEXT. Er is bewust geen fallback naar "
            "poppler of een andere parser.")
    if not binary:
        raise DependencyError(f"pdftotext niet gevonden. {hint}")
    version = src.pdftotext_version(binary)
    if not version or not REQUIRED_PDFTOTEXT_RE.match(version.strip()):
        raise DependencyError(f"Ongeschikte pdftotext ({binary}): {version!r}; vereist "
                              f"'pdftotext version {REQUIRED_PDFTOTEXT} [www.xpdfreader.com]'. {hint}")
    return binary, version.strip()


# ------------------------------------------------------------------ helpers

def _squash(s):
    return re.sub(r"\s+", " ", (s or "").replace("€", " ")).strip()


def _tokens(line):
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", line)]


def _block(layer, page, text):
    """Aanvullende block-provenance: uniek gekoppelde tekstlaagregel, anders None."""
    return rv.link_source_row_to_blocks(layer, page, text)


def _prov(doc_id, page, text, rule, layer, confidence="high", related_texts=()):
    """Provenance met text_fragment; block_id alleen bij een unieke tekstlaagkoppeling
    (dan is text_fragment de letterlijke tekstlaagregel, anders de pdftotext-regel)."""
    link = _block(layer, page, text)
    p = {"document_id": doc_id, "page": page, "table_index": None, "source_confidence": confidence,
         "extraction_rule": rule}
    if link:
        p["block_id"] = link["block_id"]
        frag = [link["text_fragment"]]
        related = []
        for t in related_texts:
            l2 = _block(layer, page, t)
            if l2 is None:
                related = None
                break
            related.append(l2["block_id"])
            frag.append(l2["text_fragment"])
        if related is None:
            # Vervolgregel niet uniek te koppelen (dezelfde tekst komt elders op de pagina nog
            # een keer voor, bijv. een tweede "plafond"-vervolgregel) - de hoofdregel blijft wel
            # gekoppeld: die match was op zichzelf al uniek en ondubbelzinnig. De vervolgtekst
            # wordt NIET aan text_fragment toegevoegd: verify_block_provenance eist dat elke
            # text_fragment-regel letterlijk uit een geciteerd blok komt, en voor de vervolgregel
            # is niet aantoonbaar welke van de identieke tekstlaagregels bedoeld is - geen fuzzy
            # matching, geen verzonnen koppeling, dus ook niet ongekoppeld "erbij plakken".
            p["text_fragment"] = link["text_fragment"]
        else:
            if related:
                p["related_block_ids"] = related
            p["text_fragment"] = "\n".join(frag)
    else:
        p["text_fragment"] = "\n".join([_squash(text)] + [_squash(t) for t in related_texts])
    return p


def _object_field_block(layer, page, text, occurrence_index):
    """Zoals _block(), maar voor OBJECT_LABELS-velden (objectblad) die letterlijk dubbel op
    dezelfde pagina kunnen voorkomen (bijv. Postcode/Plaats in zowel de Object- als de
    Opdrachtgever-sectie, met exact dezelfde tekst). occurrence_index is de rangorde (0 = eerst)
    van deze regel binnen identieke regels op dezelfde pdftotext-pagina, in leesvolgorde -
    parse_object_fields citeert altijd de eerste ('Object'-sectie) instantie, dus occurrence_index
    is voor die kandidaat altijd 0. De tekstlaagregels op een pagina staan (net als de
    pdftotext-regels) al in leesvolgorde (top naar onder), dus de occurrence_index-de match in
    beide onafhankelijk opgebouwde weergaves verwijst naar dezelfde fysieke regel. Is er geen
    tekstlaagregel op die rangorde (aantallen wijken af), dan geen block_id - geen gok."""
    key = rv._source_key(text)
    if not key:
        return None
    pg = next((p for p in layer.get("pages", []) if p["page"] == page), None)
    if pg is None:
        return None
    hits = [l for l in pg["lines"] if rv._source_key(l["text"]) == key]
    if occurrence_index >= len(hits):
        return None
    hit = hits[occurrence_index]
    return {"block_id": hit["id"], "text_fragment": hit["text"]}


def _prov_object_field(doc_id, page, text, rule, layer, occurrence_index, confidence="high"):
    """Zoals _prov(), maar met _object_field_block() (rangorde-bewuste koppeling) i.p.v. _block()."""
    link = _object_field_block(layer, page, text, occurrence_index)
    p = {"document_id": doc_id, "page": page, "table_index": None, "source_confidence": confidence,
         "extraction_rule": rule}
    if link:
        p["block_id"] = link["block_id"]
        p["text_fragment"] = link["text_fragment"]
    else:
        p["text_fragment"] = _squash(text)
    return p


def _ev(value, prov=None, review=False, raw=None):
    out = {"value": value, "requires_human_review": bool(review), "conflict": False}
    if prov is not None:
        out["provenance"] = prov
    if value is None and raw is not None and prov is not None:
        out["possible_values"] = [{"value": raw, "provenance": prov}]
    return out


def _ev_null():
    return {"value": None, "requires_human_review": False, "conflict": False}


def _pair(original, prov=None, review=False):
    out = {"original_value": original, "normalized_value": None}
    if prov is not None:
        out["provenance"] = prov
    if review:
        out["requires_human_review"] = True
    return out


def _unit_needs_review(unit_original):
    """True wanneer de eenheid ontbreekt, of aanwezig is maar niet voorkomt in de bestaande
    eenhedenvocabulaire (vocabularies/unit.json via mjop_source_sections.UNIT_TOKENS) - nooit
    een normalisatie gokken bij een onbekende eenheid, altijd naar een mens."""
    if unit_original is None:
        return True
    return unit_original.strip().lower() not in src.UNIT_TOKENS


def _parse(vtype, text):
    if vtype == "text":
        return (text, None) if text else (None, "empty")
    if vtype == "integer":
        return nv.parse_int(text)
    if vtype == "year":
        return nv.parse_year(text)
    if vtype == "date":
        iso, reason = nv.parse_date_nl(text)
        return (text if iso else None), reason   # letterlijk bewaren (bestaande conventie), wel gevalideerd
    raise ValueError(vtype)


# ------------------------------------------------------------------ profielregels (aanvullend)

def parse_object_fields(pages, sections, doc_id, layer):
    """Objectblad: label + waarde per regel binnen de benoemde subsecties. Een label dat
    meermaals in dezelfde subsectie staat -> conflict, geen keuze.

    Sommige labels (Postcode, Plaats) staan letterlijk nog een keer op dezelfde pagina, in een
    ANDERE subsectie (bijv. Opdrachtgever) die hier niet als kandidaat wordt gebruikt - maar de
    tekstlaag kent geen subsecties, dus een gewone tekstkoppeling zou daar ambigu op stuklopen.
    occurrence_index (rangorde van deze exacte regeltekst op de pagina, in leesvolgorde) lost dat
    op: de Object-sectie-kandidaat is altijd de eerste van zulke identieke regels."""
    found = {}
    for pno, sec in sections:
        if sec != "OBJECT":
            continue
        sub = None
        seen = {}
        for raw in pages[pno - 1].splitlines():
            line = _squash(src._clean(raw))
            if not line:
                continue
            occurrence_index = seen.get(line, 0)
            seen[line] = occurrence_index + 1
            if line in OBJECT_SECTIONS:
                sub = line
                continue
            for s, label, dest, field, vtype in OBJECT_LABELS:
                if s == sub and line.startswith(label + " "):
                    found.setdefault(field, []).append(
                        (pno, line, line[len(label) + 1:].strip(), dest, vtype, label, occurrence_index))
                    break
    building, docvals, flags = {}, {}, []
    for s, label, dest, field, vtype in OBJECT_LABELS:
        target = building if dest == "building" else docvals
        cands = found.get(field, [])
        if not cands:
            target[field] = _ev_null()
            continue
        rule = f"profile:pro_vve_overzicht15.object.{label}"
        if len(cands) > 1:
            target[field] = {"value": None, "requires_human_review": True, "conflict": True,
                             "possible_values": [
                                 {"value": c[2], "provenance": _prov_object_field(doc_id, c[0], c[1], rule, layer, c[6])}
                                 for c in cands]}
            flags.append({"field": field, "reason": "label_multiple_times"})
            continue
        pno, line, rawval, _, vt, _, occurrence_index = cands[0]
        val, reason = _parse(vt, rawval)
        prov = _prov_object_field(doc_id, pno, line, rule, layer, occurrence_index)
        target[field] = _ev(val, prov, review=bool(reason), raw=rawval if reason else None)
        if reason:
            flags.append({"field": field, "reason": reason})
    return building, docvals, flags


def parse_condition_legend(pages, sections, doc_id, layer):
    items, first = [], None
    related = []
    for pno, sec in sections:
        if sec != "ELEMENTEN":
            continue
        for raw in pages[pno - 1].splitlines():
            m = LEGEND_RE.match(src._clean(raw))
            if m:
                items.append(f"{m.group(1)} = {m.group(2)}")
                if first is None:
                    first = (pno, _squash(raw))
                else:
                    related.append(_squash(raw))
    if not items:
        return _ev_null()
    return _ev(items, _prov(doc_id, first[0], first[1], "profile:pro_vve_overzicht15.elements.condition_legend",
                            layer, related_texts=related))


def _overview_header(lines):
    for i, l in enumerate(lines):
        toks = {t: (s, e) for t, s, e in _tokens(l)}
        if "Code" in toks and "Element" in toks and "Locatie" in toks and "Conditie" in toks:
            return i, toks
    return None, None


def parse_element_overview(pages, sections):
    """Elementenoverzicht (Code / Element / Locatie / Hvh+Ehd / Conditie) op kolompositie
    uit de kopregel. Rijen die niet in deze structuur passen worden niet geraden maar
    teruggegeven als 'unclassified'."""
    rows, unclassified = [], []
    group = None
    for pno, sec in sections:
        if sec != "ELEMENTEN":
            continue
        lines = pages[pno - 1].splitlines()
        hi, cols = _overview_header(lines)
        if hi is None:
            continue
        loc_x = cols["Locatie"][0] - 1
        cond_x = cols["Conditie"][0] - 2
        for i in range(hi + 1, len(lines)):
            line = src._clean(lines[i])
            if not line.strip() or src.DATE_FOOTER.match(line) or "Printdatum" in line:
                continue
            toks = _tokens(line)
            if GROUP_RE.match(toks[0][0]) and toks[0][1] < 4 and len(toks) > 1 and \
                    all(not QTY_UNIT_RE.match(t[0]) for t in toks):
                group = {"code": toks[0][0], "label": " ".join(t[0] for t in toks[1:])}
                continue
            if not (CODE_RE.match(toks[0][0]) and toks[0][1] < 4):
                unclassified.append({"page": pno, "line": i + 1, "text": _squash(line)})
                continue
            qi = [j for j, t in enumerate(toks) if QTY_UNIT_RE.match(t[0])]
            cond = [t for t in toks if t[1] >= cond_x]
            if len(qi) != 1 or len(cond) > 1:
                unclassified.append({"page": pno, "line": i + 1, "text": _squash(line)})
                continue
            q = qi[0]
            name = [t[0] for t in toks[1:q] if t[1] < loc_x]
            loc = [t[0] for t in toks[1:q] if t[1] >= loc_x]
            qty_text, unit = QTY_UNIT_RE.match(toks[q][0]).groups()
            after = [t for t in toks[q + 1:] if t[1] < cond_x]
            if not unit and len(after) == 1:
                unit = after[0][0]
            elif after:
                unclassified.append({"page": pno, "line": i + 1, "text": _squash(line)})
                continue
            rows.append({"page": pno, "line": i + 1, "code": toks[0][0], "name": " ".join(name),
                         "location": " ".join(loc) or None, "quantity_as_stated": qty_text,
                         "unit_original": unit or None, "condition": cond[0][0] if cond else None,
                         "group": group, "raw_line": _squash(line)})
    return rows, unclassified


# ------------------------------------------------------------------ opbouw record

def _element_key(code, name, location):
    return (code, _squash(name).lower(), _squash(location or "").lower())


def build_record(doc_id, pages, layer, profile, pdftotext_version, doc_meta):
    sections = src.classify_sections(pages)
    rule_prefix = f"profile:{profile['profile_id']}"
    trace = {"unclassified_element_overview_lines": [], "rows_without_positive_amount": [],
             "row_reconciliation": [], "provenance_without_block_link": 0, "object_flags": []}

    # 1. objectblad (profielregels) + documentcontext (leidend: mjop_source_sections)
    building_fields, docvals, flags = parse_object_fields(pages, sections, doc_id, layer)
    trace["object_flags"] = flags
    ctx = src.parse_document_context(pages)
    for key, text_key, src_key in (("price_level_date", "price_level_date", "price_level_source"),
                                   ("vat_statement", "vat_text", "vat_source")):
        s = ctx.get(src_key)
        docvals[key] = _ev(ctx.get(text_key), _prov(doc_id, s["page"], s["text"],
                                                     f"mjop_source_sections.document_context.{key}", layer)) \
            if s else _ev_null()
    docvals["vat_rate_text"] = _ev_null()
    if ctx.get("vat_rate_text"):
        # parse_document_context bewaart geen bronregel voor de tarieftekst: zelfde regex, eerste treffer
        for pno, text in enumerate(pages, start=1):
            hit = next((l for l in (_squash(src._clean(r)) for r in text.splitlines())
                        if l.startswith("BTW tarief ") and ctx["vat_rate_text"] in l), None)
            if hit:
                docvals["vat_rate_text"] = _ev(ctx["vat_rate_text"], _prov(
                    doc_id, pno, hit, "mjop_source_sections.document_context.vat_rate_text", layer))
                break
    if ctx.get("indexation_source"):
        s = ctx["indexation_source"]
        line = src._clean(pages[s["page"] - 1].splitlines()[s["line"] - 1])
        docvals["indexation_statement"] = _ev(ctx["indexation_statement"], _prov(
            doc_id, s["page"], line, "mjop_source_sections.document_context.indexation_statement", layer))
    else:
        docvals["indexation_statement"] = _ev_null()
    docvals["condition_legend"] = parse_condition_legend(pages, sections, doc_id, layer)

    building = {"building_id": f"{doc_id}-BLD-001", "document_ids": [doc_id]}
    for f in ("construction_year", "number_of_units", "building_type", "address", "inspection_date", "mjop_period"):
        building[f] = building_fields.get(f, _ev_null())

    # 2. elementenoverzicht (profielregels)
    ov_rows, uncl = parse_element_overview(pages, sections)
    trace["unclassified_element_overview_lines"] = uncl
    elements, observations, el_index = [], [], {}
    for n, r in enumerate(ov_rows, start=1):
        eid = f"{doc_id}-EL-{n:03d}"
        prov = _prov(doc_id, r["page"], r["raw_line"], f"{rule_prefix}.elements.overview_row", layer)
        qty, qreason = nv.parse_quantity_nl(r["quantity_as_stated"])
        el = {
            "element_id": eid, "building_id": building["building_id"],
            "element_code": _pair(r["code"], prov),
            "element_type": _pair(r["name"], prov),
            "element_name": _ev(r["name"], prov),
            "location": _ev(r["location"], prov) if r["location"] else _ev_null(),
            "material": {"original_value": None, "normalized_value": None},
            "quantity": _ev(qty, prov, review=bool(qreason), raw=r["quantity_as_stated"] if qreason else None),
            "unit": _pair(r["unit_original"], prov, review=_unit_needs_review(r["unit_original"])),
            "construction_year": _ev_null(),
            "gemeenschappelijk_of_prive": None,
        }
        elements.append(el)
        el_index.setdefault(_element_key(r["code"], r["name"], r["location"]), []).append(eid)
        if r["condition"] is not None:
            review = r["condition"] not in {"1", "2", "3", "4", "5", "6"}
            cs = {"original_value": r["condition"], "normalized_value": None, "scale": None, "provenance": prov}
            observations.append({
                "observation_id": f"{doc_id}-OBS-{len(observations) + 1:03d}", "element_id": eid,
                "description": _ev_null(), "condition_score": cs, "source": prov,
                "requires_human_review": review,
            })

    # 3. jarenplan (LEIDEND: mjop_source_sections)
    jp_rows, carry = [], None
    for pno, sec in sections:
        if sec == "JARENPLAN":
            r, carry, _ = src.parse_jarenplan_page(pages[pno - 1], pno, carry)
            jp_rows.extend(r)
    amount_tokens = [v for row in jp_rows for v in row["annual_amounts_raw"].values()] + \
                    [row["total_as_stated"] for row in jp_rows if row.get("total_as_stated")]
    evidence = nv.whole_euro_evidence([t for raw in amount_tokens for t in raw.split()])
    currency_rule = profile["currency_rule"]

    actions = []
    for row in jp_rows:
        _, _, status = src.reconcile_row_amounts(row)
        trace["row_reconciliation"].append({"page": row["page"], "line": row["line"], "status": status})
        el = row.get("element")
        element_id = None
        if el:
            ids = el_index.get(_element_key(el["code"], el["description"], el["location"]), [])
            if len(ids) == 1:
                element_id = ids[0]
        positive = []
        for year in sorted(row["annual_amounts_raw"]):
            raw = row["annual_amounts_raw"][year]
            val, reason, rule = nv.parse_currency_profile(raw, currency_rule, evidence)
            if val is not None and Decimal(val) == 0 and reason is None:
                continue
            positive.append((year, raw, val, reason, rule))
        if not positive:
            trace["rows_without_positive_amount"].append(
                {"page": row["page"], "line": row["line"], "text": row["raw_line"], "stj": row.get("stj")})
            continue
        cont_texts = []
        page_lines = pages[row["page"] - 1].splitlines()
        for ln in row["continuation_lines"]:
            cont_texts.append(src._clean(page_lines[ln - 1]))
        row_prov = _prov(doc_id, row["page"], row["raw_line"], "mjop_source_sections.jarenplan.row", layer,
                         related_texts=cont_texts)
        qty, qreason = nv.parse_quantity_nl(row["quantity_as_stated"])
        for year, raw, val, reason, rule in positive:
            aid = f"{doc_id}-ACT-{len(actions) + 1:03d}"
            year_prov = dict(row_prov, extraction_rule="mjop_source_sections.jarenplan.year_column")
            amt_prov = dict(row_prov, extraction_rule=rule)
            review = (bool(reason) or bool(qreason) or element_id is None or status in ("mismatch", "unparseable")
                      or _unit_needs_review(row["unit_original"]))
            actions.append({
                "action_id": aid,
                "element_id": element_id or f"{doc_id}-EL-UNLINKED",
                "action": _pair(row["action_text"] or None, row_prov),
                "planned_year": _ev(int(year), year_prov),
                "quantity": _ev(qty, row_prov, review=bool(qreason), raw=row["quantity_as_stated"] if qreason else None),
                "unit": _pair(row["unit_original"], row_prov, review=_unit_needs_review(row["unit_original"])),
                "unit_cost": {"value": None, "is_estimated": False},
                "cost_year": None,
                "total_cost_as_stated": val,
                "field_provenance": {"total_cost_as_stated": amt_prov},
                "requires_human_review": review,
                "source_page": row["page"],
            })

    # mjop_period: niet letterlijk als periode; kandidaat uit het venster van de bronlaag
    win = next((r["window"] for r in jp_rows if r.get("window")), None)
    if win:
        wp = next(r for r in jp_rows if r.get("window"))
        hdr = next(l for l in pages[wp["page"] - 1].splitlines() if src.JARENPLAN_HEADER.search(l))
        p = _prov(doc_id, wp["page"], hdr, "mjop_source_sections.jarenplan.window_candidate", layer, confidence="medium")
        building["mjop_period"] = {"value": None, "requires_human_review": True, "conflict": False,
                                   "provenance": p, "possible_values": [{"value": f"{win[0]}-{win[1]}", "provenance": p}]}

    record = {
        "status": "extracted",
        "document_id": doc_id,
        "batch": "batch_1",
        "extraction_mode": "deterministic",
        "extraction_notes": ("Deterministische pilot-extractie (geen AI-API, geen netwerk). Waarden uit "
                             "mjop_source_sections waar beschikbaar; objectblad, elementenoverzicht en "
                             "conditielegenda via expliciete documentprofielregels; block_id alleen als "
                             "aanvullende provenance. PILOT-output: geen canonieke extractie."),
        "extraction_metadata": {
            "extractor": "deterministic_extraction.py",
            "extractor_version": EXTRACTOR_VERSION,
            "parser": "mjop_source_sections",
            "parser_text_mode": src.PDFTOTEXT_MODE,
            "pdftotext_version": pdftotext_version,
            "document_profile": profile["profile_id"],
            "profile_version": profile["profile_version"],
            "rules_version": RULES_VERSION,
            "currency_rule": currency_rule,
            "currency_evidence": evidence,
            "source_relative_path": doc_meta["relative_path"],
            "source_sha256": doc_meta["sha256"],
            "text_layer_sha256": layer["text_layer_sha256"],
            "text_layer_generator": layer["generator"],
            "uses_ai_api": False,
            "network_calls": False,
        },
        "building": building,
        "elements": elements,
        "observations": observations,
        "maintenance_actions": actions,
        "document_level_values": docvals,
        "deterministic_trace": trace,
    }
    trace["provenance_without_block_link"] = sum(
        1 for _, p in rv.iter_provenance(record) if not p.get("block_id"))
    return record


def validate(record, layer):
    errors = rv.validate_entities(record) + rv.verify_block_provenance(record, layer)
    reg = rv.schema_registry()
    for k, v in record.get("document_level_values", {}).items():
        errors += [f"document_level_values.{k} {e}" for e in rv.schema_errors(v, "_extracted_value.schema.json", reg)]
    return errors


def extract_document(doc_id, project_root, pdftotext_binary, pdftotext_version):
    """Bouwt het pilotrecord in het geheugen. Schrijft niets."""
    profile = DOCUMENT_PROFILES.get(doc_id)
    if profile is None:
        raise ExtractionError(f"{doc_id}: geen documentprofiel voor de deterministische route "
                              f"(beschikbaar: {sorted(DOCUMENT_PROFILES)})")
    raw_dir = os.path.join(project_root, "data", "raw")
    registry_path = os.path.join(project_root, "reports", "document_registry.json")
    registry = document_registry.load_registry(registry_path)
    path, doc_meta = document_registry.verify_file(registry, doc_id, raw_dir)
    pages = src.pdf_pages(path, pdftotext_binary)
    layer = tl.build_text_layer_for_file(path, doc_id, doc_meta["sha256"], doc_meta["relative_path"])
    record = build_record(doc_id, pages, layer, profile, pdftotext_version, doc_meta)
    errors = validate(record, layer)
    if errors:
        raise ExtractionError(f"{doc_id}: validatie mislukt ({len(errors)} fouten)", errors)
    return record


def pilot_output_path(doc_id, project_root, out_dir=None):
    out_dir = out_dir or os.path.join(project_root, PILOT_SUBDIR)
    real = os.path.realpath(out_dir)
    for d in CANONICAL_DIRS:
        if real == os.path.realpath(os.path.join(project_root, d)):
            raise ExtractionError(f"Weigering: {out_dir} is een canonieke datamap; pilot-output hoort in "
                                  f"{PILOT_SUBDIR}/ (of een andere niet-canonieke map)")
    return os.path.join(out_dir, f"{doc_id}.json")


def dumps(record):
    return json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_pilot(record, project_root, out_dir=None):
    out = pilot_output_path(record["document_id"], project_root, out_dir)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(dumps(record))
    return out
