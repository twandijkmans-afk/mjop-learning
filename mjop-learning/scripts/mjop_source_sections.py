#!/usr/bin/env python3
"""
mjop_source_sections.py  (bronlaag: PDF-tekstlaag -> gestructureerde bronrijen)

Pure parse-functies voor de drie secties van de MJOP-rapporten in batch 1
(het rapportformaat van DOC-001, 002, 004-010), plus het objectblad:

  - "Overzicht NN - Jarenplan (Gedetailleerd)"  -> JARENPLAN-rijen
  - "Jaarplan <jaar>"                           -> JAARPLAN-regels
  - "Bevindingen NEN 2767"                       -> BEVINDINGEN-activiteiten
  - "Algemene Objectgegevens"                    -> prijspeil / BTW (letterlijk)

Invoer is de tekst die `pdftotext -table` (xpdf 4.06) per pagina oplevert.
Dat is bewust gekozen: in die modus staan de kolommen van een jarenplan-rij
(Hvh, Ehd, Stj, Cy, jaarkolommen, Totaal) op dezelfde tekstregel, en de
bronanalyse is met precies deze weergave gevalideerd (som van de rijtotalen
= eigen "Totaal object" van elk document). Regelnummers in de provenance
verwijzen naar die tekstweergave, niet naar PDF-coordinaten.

Niets hier verzint waarden: een lege Cy blijft None, een ontbrekend
prijspeil blijft None, en bedragen blijven Decimal (via
normalize_batch.to_decimal) - nooit float.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize_batch import to_decimal  # noqa: E402

PDFTOTEXT_MODE = "-table"

JARENPLAN_HEADER = re.compile(r"Hvh +Ehd +Stj +Cy")
JAARPLAN_HEADER = re.compile(r"Handeling +- +Gebrek +Hvh +Ehd +\d{4}")
QTY_TOKEN = re.compile(r"\d[\d.]*,\d{2}")
YEAR_TOKEN = re.compile(r"(19|20)\d\d")
FOOTER_STAMP = re.compile(r"Pro VVE Beheer B\.V\. \d+ - \d+")
DATE_FOOTER = re.compile(r"^\s*\d{1,2}-\d{1,2}-20\d\d\s")
# Elementcodes zijn 4 cijfers, behalve de staartkosten: groep 'ZZ' met
# element 'ZZZZ' (directievoering/onvoorzien) in DOC-008/009/010.
ELEMENT_LINE = re.compile(r"^(\d{4}|ZZZZ)\s+(.*)$")


def _load_unit_tokens():
    """Letterlijke eenheden uit vocabularies/unit.json (UTF-8), alleen gebruikt om
    een losse eenheid aan het eind van een element-vervolgregel te herkennen."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vocabularies", "unit.json")
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except OSError:
        return frozenset()
    return frozenset(str(v).strip().lower() for e in doc.get("entries", []) for v in e.get("known_original_values", []))


UNIT_TOKENS = _load_unit_tokens()
GROUP_LINE = re.compile(r"^(\d{2}|ZZ)\s+")


# --------------------------------------------------------------------------
# PDF -> pagina's
# --------------------------------------------------------------------------

def find_pdftotext(explicit=None):
    return explicit or os.environ.get("PDFTOTEXT") or shutil.which("pdftotext")


def pdftotext_version(binary):
    if not binary:
        return None
    try:
        out = subprocess.run([binary, "-v"], capture_output=True, text=True)
        text = (out.stdout or "") + (out.stderr or "")
        return text.strip().splitlines()[0] if text.strip() else None
    except OSError:
        return None


def pdf_pages(path, binary):
    """Geeft een lijst paginateksten (index 0 = pagina 1)."""
    out = subprocess.run(
        [binary, "-q", PDFTOTEXT_MODE, "-enc", "UTF-8", path, "-"],
        capture_output=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"pdftotext faalde voor {path}: {out.stderr.decode('utf-8', 'replace')}")
    text = out.stdout.decode("utf-8", "replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


# --------------------------------------------------------------------------
# Sectie-indeling
# --------------------------------------------------------------------------

def classify_sections(pages):
    """Kent elke pagina een sectie toe op basis van de sectietitels die in de
    bron staan. Een sectie loopt door tot de volgende titel. Returns: lijst
    (1-based paginanummer, sectie) met sectie in
    {None, 'OBJECT', 'ELEMENTEN', 'BEVINDINGEN', 'JARENPLAN', 'HOOFDGROEPEN', 'JAARPLAN'}."""
    result = []
    section = None
    for i, text in enumerate(pages, start=1):
        if "Algemene Objectgegevens" in text:
            section = "OBJECT"
        if "Elementenoverzicht" in text:
            section = "ELEMENTEN"
        if "Bevindingen NEN 2767" in text:
            section = "BEVINDINGEN"
        if re.search(r"Overzicht +\d+ +- +Jarenplan +\(Gedetailleerd\)", text):
            section = "JARENPLAN"
        if re.search(r"Overzicht +\d+ +- +Jarenplan +\(Hoofdgroepen\)", text):
            section = "HOOFDGROEPEN"
        if re.search(r"^\s*Jaarplan\b", text, re.M):
            section = "JAARPLAN"
        # De kolomkoppen zijn doorslaggevend: een pagina met de jarenplan-
        # of jaarplan-tabelkop hoort bij die sectie, ongeacht de titel.
        if JARENPLAN_HEADER.search(text):
            section = "JARENPLAN"
        elif JAARPLAN_HEADER.search(text):
            section = "JAARPLAN"
        result.append((i, section))
    return result


def _clean(line):
    """Verwijdert de paginavoet-stempel en het valutateken. pdftotext zet '€'
    als los token in/naast de bedragkolommen; het is geen waarde en zou de
    kolomtoewijzing verstoren. Bedragen zelf blijven ongewijzigd."""
    return FOOTER_STAMP.sub("", line).replace("€", " ").rstrip()


def _squash(s):
    return re.sub(r" +", " ", (s or "").strip())


# --------------------------------------------------------------------------
# Objectblad: prijspeil / BTW / indexatie (letterlijk, niet afgeleid)
# --------------------------------------------------------------------------

def parse_document_context(pages):
    """Leest prijspeil, BTW-basis, BTW-tarieftekst en de indexatiezin letterlijk
    uit de bron. Staat er geen 'Prijspeil'-veld, dan blijft het prijspeil None
    met basis 'absent' - het wordt NOOIT afgeleid uit inspectie- of printdatum."""
    ctx = {
        "price_level_date": None,
        "price_level_basis": "absent",
        "price_level_source": None,
        "vat_basis": None,
        "vat_text": None,
        "vat_rate_text": None,
        "vat_source": None,
        "indexation_statement": None,
        "indexation_source": None,
    }
    for pno, text in enumerate(pages, start=1):
        for lno, raw in enumerate(text.splitlines(), start=1):
            line = _squash(_clean(raw))
            if ctx["price_level_date"] is None:
                m = re.match(r"^Prijspeil (\d{1,2}-\d{1,2}-\d{4})\b", line)
                if m:
                    ctx.update(price_level_date=m.group(1), price_level_basis="explicit",
                               price_level_source={"page": pno, "line": lno, "text": line})
            if ctx["vat_text"] is None:
                m = re.match(r"^BTW (De bedragen in de begrotingen zijn (inclusief|exclusief) BTW)", line)
                if m:
                    ctx.update(vat_text=m.group(1),
                               vat_basis="inclusive" if m.group(2) == "inclusief" else "exclusive",
                               vat_source={"page": pno, "line": lno, "text": line})
            if ctx["vat_rate_text"] is None:
                m = re.match(r"^BTW tarief (Hoog/Laag tarief is toegepast: .*?%; Laag = [\d,]+%)", line)
                if m:
                    ctx["vat_rate_text"] = m.group(1)
            if ctx["indexation_statement"] is None:
                m = re.search(r"De bedragen in deze begroting zijn jaarlijks geindexeerd met .*?\(vanaf \d{4}\)\.?", line)
                if m:
                    ctx.update(indexation_statement=m.group(0),
                               indexation_source={"page": pno, "line": lno})
    return ctx


# --------------------------------------------------------------------------
# Jarenplan (Gedetailleerd)
# --------------------------------------------------------------------------

def _header_columns(header):
    cols = {}
    for m in re.finditer(r"\S+", header):
        tok = m.group()
        if tok in ("Hvh", "Ehd", "Stj", "Cy", "Totaal", "Locatie") or YEAR_TOKEN.fullmatch(tok):
            cols.setdefault(tok, (m.start(), m.end()))
    return cols


def parse_jarenplan_page(text, page_no, carry_element=None):
    """Parset één jarenplan-pagina. Returns (rows, last_element, totaal_object).

    Een rij = een regel met een hoeveelheid ('815,95') in/rond de Hvh-kolom.
    Tokens rechts daarvan worden op kolompositie toegewezen: Stj/Cy op
    kolommidden, jaarkolommen en Totaal op rechterrand (bedragen zijn
    rechts uitgelijnd). Een lege Cy-kolom levert cy=None op.

    Elementregels die in de PDF op een volgende regel doorlopen (alleen tekst
    in de elementkolom, alleen lege regels ertussen, vóór de eerste rij) worden
    letterlijk aan de elementomschrijving toegevoegd. De eerste regel blijft
    bewaard in `description_first_line`, de vervolgregels in
    `continuation_lines`. Geen enkel woord van de vervolgregel wordt
    uitgesloten - ook niet als het toevallig een bekende eenheid is (bijv.
    'dekkend m2', DOC-007 p17): de Elementenoverzicht-naamparsing sluit zulke
    woorden ook niet uit, en deze functie moet dezelfde letterlijke naam
    opleveren als die kant, anders koppelt een jarenplanregel niet aan zijn
    element. `excluded_tokens` blijft aanwezig (nu altijd leeg) voor
    compatibiliteit met bestaande consumenten van dit veld.

    carry_element: laatste elementregel van de vorige pagina, met
    `open_at_page_end` = er kwam na dat element geen groep-, subtotaal- of
    totaalgrens meer. Rijen vóór de eerste elementregel op deze pagina krijgen
    dat element alleen als het element open was én er op deze pagina nog geen
    grens voorafging (element_context_source='previous_page'); anders blijft
    element=None met element_candidate_previous_page als kandidaat."""
    lines = text.splitlines()
    hi = next((i for i, l in enumerate(lines) if JARENPLAN_HEADER.search(l)), None)
    if hi is None:
        return [], carry_element, None
    cols = _header_columns(lines[hi])
    years = [k for k in cols if YEAR_TOKEN.fullmatch(k)]
    hv = cols["Hvh"][0]
    loc = cols["Locatie"][0] if "Locatie" in cols else hv
    numcols = [k for k in cols if k != "Locatie"]

    rows = []
    element = None
    cur = None
    last_cont = None
    totaal_object = None
    elem_last = None          # regelindex van de elementregel (of laatste vervolgregel) zolang hij open is
    boundary_before_element = False   # groep/subtotaal/totaal op deze pagina vóór de eerste elementregel
    open_at_end = bool(carry_element and carry_element.get("open_at_page_end"))
    for i in range(hi + 1, len(lines)):
        line = _clean(lines[i])
        if not line.strip():
            continue
        if "Totaal object" in line:
            nums = re.findall(r"[\d.]+", line.split("Totaal object", 1)[1])
            if nums:
                totaal_object = to_decimal(nums[-1])
            cur = None
            elem_last = None
            open_at_end = False
            if element is None:
                boundary_before_element = True
            continue
        if "Printdatum" in line or DATE_FOOTER.match(line):
            cur = None
            continue
        toks = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", line)]
        qi = [j for j, t in enumerate(toks) if QTY_TOKEN.fullmatch(t[0]) and t[1] >= hv - 15]
        if qi:
            j = qi[0]
            left, right = toks[:j], toks[j:]
            text_a = " ".join(t[0] for t in left if t[1] < loc - 1)
            text_b = " ".join(t[0] for t in left if t[1] >= loc - 1)
            unit = None
            rest = right[1:]
            if rest:
                # eenheid = token in de Ehd-kolom; een numerieke waarde daar
                # (bijv. '20' in DOC-009/010) blijft letterlijk de eenheid en
                # mag niet in Stj/Cy terechtkomen
                c0 = (rest[0][1] + rest[0][2]) / 2
                nearest = min(("Ehd", "Stj", "Cy"),
                              key=lambda k: abs((cols[k][0] + cols[k][1]) / 2 - c0) if k in cols else 1e9)
                if not re.fullmatch(r"[\d.,]+", rest[0][0]) or nearest == "Ehd":
                    unit, rest = rest[0][0], rest[1:]
            assigned = {}
            for tok, s, e in rest:
                c = (s + e) / 2
                def dist(k):
                    if k in ("Hvh", "Ehd", "Stj", "Cy"):
                        return abs((cols[k][0] + cols[k][1]) / 2 - c)
                    return abs(cols[k][1] - e)
                k = min(numcols, key=dist)
                if k in ("Hvh", "Ehd"):
                    k = "Stj" if re.fullmatch(r"\d{4}", tok) else "Cy"
                assigned.setdefault(k, []).append(tok)
            row_element = element
            context_source = "same_page" if element is not None else None
            m = ELEMENT_LINE.match(text_a)
            action_text = text_a
            if m:  # element en actie op dezelfde regel
                row_element = element = _new_element(m, text_b, page_no, i + 1)
                context_source = "same_page"
                action_text = ""
            elif row_element is None and open_at_end and not boundary_before_element:
                # element loopt door vanaf de vorige pagina (geen grens ertussen)
                row_element = {k: v for k, v in carry_element.items() if k != "open_at_page_end"}
                context_source = "previous_page"
            elem_last = None
            open_at_end = row_element is not None
            annual_raw = {y: " ".join(assigned[y]) for y in years if y in assigned}
            cur = {
                "page": page_no,
                "line": i + 1,
                "action_text": _squash(action_text),
                "gebrek_or_location_text": _squash(text_b) if not m else "",
                "quantity_as_stated": right[0][0],
                "unit_original": unit,
                "stj": " ".join(assigned.get("Stj", [])) or None,
                "cy": " ".join(assigned.get("Cy", [])) or None,
                "annual_amounts_raw": annual_raw,
                "total_as_stated": " ".join(assigned.get("Totaal", [])) or None,
                "window": [years[0], years[-1]] if years else None,
                "element": row_element,
                "element_context_source": context_source,
                "element_candidate_previous_page": carry_element if row_element is None else None,
                "raw_line": _squash(line),
                "continuation_lines": [],
            }
            rows.append(cur)
            last_cont = i
            continue
        right = [t for t in toks if t[1] >= hv]
        text_a = " ".join(t[0] for t in toks if t[1] < loc - 1)
        text_b = " ".join(t[0] for t in toks if loc - 1 <= t[1] < hv)
        m = ELEMENT_LINE.match(text_a)
        if m and not right:
            element = _new_element(m, text_b, page_no, i + 1)
            cur = None
            elem_last = i
            open_at_end = True
        elif GROUP_LINE.match(text_a):
            cur = None
            elem_last = None
            open_at_end = False
            if element is None:
                boundary_before_element = True
        elif (element is not None and elem_last is not None and not right and text_a and not text_b
              and all(not lines[k].strip() for k in range(elem_last + 1, i))):
            # vervolgregel van de elementomschrijving (alleen elementkolom): altijd
            # letterlijk toevoegen, ook een woord dat toevallig een bekende eenheid is
            # (bijv. 'dekkend m2') - de Elementenoverzicht-naamparsing sluit zulke
            # woorden ook niet uit, en anders koppelt deze jarenplanregel niet aan
            # zijn element (verschillende elementnaam aan beide kanten).
            words = text_a.split()
            element["description"] = _squash(element["description"] + " " + " ".join(words))
            element["continuation_lines"].append(i + 1)
            elem_last = i
        elif (cur is not None and not right and last_cont is not None and (text_a or text_b)
              and all(not lines[k].strip() for k in range(last_cont + 1, i))):
            # directe vervolgregel van de actietekst (pdftotext -table zet
            # lege regels tussen tabelregels; alleen lege regels ertussen)
            if text_a:
                cur["action_text"] = _squash(cur["action_text"] + " " + text_a)
            if text_b:
                cur["gebrek_or_location_text"] = _squash(cur["gebrek_or_location_text"] + " " + text_b)
            cur["continuation_lines"].append(i + 1)
            last_cont = i
        elif right:
            # subtotaalregel (alleen bedragen): grens
            cur = None
            elem_last = None
            open_at_end = False
            if element is None:
                boundary_before_element = True
        else:
            elem_last = None
    last = element or carry_element
    carry = dict(last, open_at_page_end=open_at_end) if last else None
    return rows, carry, totaal_object


def _new_element(match, location_text, page_no, line_no):
    desc = _squash(match.group(2))
    return {"code": match.group(1), "description": desc, "description_first_line": desc,
            "location": _squash(location_text), "page": page_no, "line": line_no,
            "continuation_lines": [], "excluded_tokens": []}


def reconcile_row_amounts(row):
    """Controleert of de jaarbedragen optellen tot het rijtotaal. De bron toont
    afgeronde bedragen (bijv. 7.400 + 7.400 bij Totaal 14.799), dus een
    afwijking tot 0,5 per getoond bedrag (+0,5 voor het totaal) geldt als
    afronding. Returns (total, amounts_dict, status)."""
    total = to_decimal(row["total_as_stated"]) if row.get("total_as_stated") else None
    amounts = {}
    for y, raw in row["annual_amounts_raw"].items():
        val = to_decimal(raw.split()[0]) if raw else None
        if val is None or len(raw.split()) > 1:
            return total, amounts, "unparseable"
        amounts[y] = val
    positive = {y: v for y, v in amounts.items() if v > 0}
    if total is None:
        return (Decimal("0") if not positive else None), positive, ("no_total" if positive else "zero")
    if total == 0 and not positive:
        return total, positive, "zero"
    s = sum(positive.values(), Decimal("0"))
    tolerance = Decimal("0.5") * (len(positive) + 1)
    status = "consistent" if abs(s - total) <= tolerance else "mismatch"
    return total, positive, status


def total_scope(n_positive, reconciliation):
    if reconciliation != "consistent" or n_positive == 0:
        return "UNKNOWN"
    return "ONE_EXECUTION" if n_positive == 1 else "MULTIPLE_EXECUTIONS"


# --------------------------------------------------------------------------
# Jaarplan
# --------------------------------------------------------------------------

JAARPLAN_ROW = re.compile(
    r"^\s*(?:(\d{4}|ZZZZ)\s{2,}(\S.*?)\s{2,})?(\S.*?)\s{2,}(\d[\d.]*,\d{2})\s+(?:([A-Za-z]\S*)\s+)?([\d.]+)\s*$")


def parse_jaarplan_page(text, page_no):
    """Jaarplan-tabel: 'Code  Element/Locatie  Handeling - Gebrek  Hvh Ehd <jaar>'."""
    lines = text.splitlines()
    hi = next((i for i, l in enumerate(lines) if JAARPLAN_HEADER.search(l)), None)
    if hi is None:
        return []
    year = re.search(r"(\d{4})\s*$", lines[hi].strip()).group(1)
    out = []
    for i in range(hi + 1, len(lines)):
        line = _clean(lines[i])
        if "Totaal object" in line or not line.strip():
            continue
        m = JAARPLAN_ROW.match(line)
        if m:
            out.append({
                "page": page_no, "line": i + 1, "year": year,
                "element_code": m.group(1), "element_text": _squash(m.group(2)) if m.group(2) else None,
                "action_text": _squash(m.group(3)), "quantity_as_stated": m.group(4),
                "unit_original": m.group(5), "amount_as_stated": m.group(6), "raw_line": _squash(line),
            })
    return out


# --------------------------------------------------------------------------
# Bevindingen
# --------------------------------------------------------------------------

BEV_ACTIVITY_LINE = re.compile(r"^\s*(\S.*?)\s{2,}(\d[\d.]*,\d{2})\s+(\S+)(?:\s+([\d.]+))?\s*$")


def parse_bevindingen_page(text, page_no):
    """Bevindingen-blokken: element, Tag/locatie, gebrek (code + naam), een
    regel met Ernst/Intensiteit/Omvang/Conditie (letterlijk bewaard, niet
    geinterpreteerd) en 'Activiteit: <jaar>' gevolgd door actie + Hvh (+ Totaal).
    Een activiteit zonder bedrag krijgt amount_as_stated=None."""
    out = []
    element = loc = defect = year = None
    expect_loc = expect_scores = False
    scores = None
    for i, raw in enumerate(text.splitlines()):
        line = _clean(raw)
        s = line.strip()
        if not s:
            continue
        m = ELEMENT_LINE.match(s)
        if m and "  " in s and not QTY_TOKEN.search(s):
            element = {"code": m.group(1), "description": _squash(m.group(2))}
            year = loc = defect = scores = None
            continue
        if s == "Tag":
            expect_loc = True
            continue
        if expect_loc:
            loc, expect_loc = _squash(s), False
            continue
        m = re.match(r"^([A-Z]\d+[A-Z]{2}\d+)\s+(.*)$", s)
        if m:
            defect = {"code": m.group(1), "name": _squash(m.group(2))}
            continue
        if s.startswith("Ernst") and "Intensiteit" in s:  # kopregel, niet 'Ernstig 2 2 2'
            expect_scores = True
            continue
        if expect_scores:
            scores, expect_scores = _squash(s), False
            continue
        m = re.match(r"^Activiteit:\s+(\d{4})", s)
        if m:
            year = m.group(1)
            continue
        m = BEV_ACTIVITY_LINE.match(line)
        if m and year:
            out.append({
                "page": page_no, "line": i + 1, "year": year, "element": element,
                "tag_location": loc, "defect": defect, "inspection_scores_raw": scores,
                "action_text": _squash(m.group(1)), "quantity_as_stated": m.group(2),
                "unit_original": m.group(3), "amount_as_stated": m.group(4), "raw_line": _squash(line),
            })
    return out
