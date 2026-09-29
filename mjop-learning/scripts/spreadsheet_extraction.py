#!/usr/bin/env python3
"""
spreadsheet_extraction.py - deterministische extractie van spreadsheet-exports van
'Overzicht NN - Jarenplan (Gedetailleerd)' (familie pro_vve_overzicht15_spreadsheet).

Bron = de bestaande deterministische tekstlaag (scripts/text_layer.py, xlrd voor .xls /
openpyxl voor .xlsx): elke cel met exacte waarde (repr van het getal, geen afronding), stabiel
blok-ID (S01-R0024-C003) en A1-celadres. Geen conversie, geen AI, geen externe service.

Structuur (dezelfde vvem-software als de PDF-familie):
  titelrij        'Overzicht NN - Jarenplan (Gedetailleerd)'
  objectcel       '<nummer> • <objectnaam>' + adresregel + [postcode] plaats
  BTW-cel         'Alle prijzen zijn inclusief/exclusief BTW ...' (+ indexatiezin)
  kopregel        Code/Element/Handeling | Locatie Element/Gebrek | Hvh | Ehd | Stj | Cy | <jaren> | Totaal
  groepsregel     2-cijferige code + naam
  elementregel    4-cijferige code (of ZZZZ) + naam [+ locatie]
  actieregel      actietekst [+ gebrek] + hoeveelheid + eenheid + Stj + Cy + jaarbedragen + totaal
  subtotaalregel  alleen bedragen (geen tekst)          -> NOOIT een actie
  Totaal object   'Totaal object' + bedragen            -> alleen voor controle
  voettekst       losse tekstcel zonder bedragen (paginanummer)

Kolommen worden uit de kopregel gehaald (nooit vaste posities: DOC-003 en DOC-015 verschillen).
Regels die in geen van deze vormen passen worden niet geraden maar als 'unclassified' gerapporteerd
(-> REVIEW_REQUIRED). Cy = 0 is de spreadsheetweergave van een lege cyclus (bewijs: DOC-003 vs
DOC-002, zelfde MJOP) en wordt als null gelezen (regel spreadsheet.cy_zero_is_blank).

Uitvoer: exact dezelfde recordvorm en schemas als deterministic_extraction.py, met provenance
sheet + cell_ref + block_id (page = null).
"""
import copy
import re
import sys
import os
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nl_values as nv  # noqa: E402
import record_validation as rv  # noqa: E402

EXTRACTOR_VERSION = "spreadsheet_extraction_v1.0.0"
RULES_VERSION = "pro_vve_overzicht15_spreadsheet_rules_v1"
PROFILE = {"profile_id": "pro_vve_overzicht15_spreadsheet", "profile_version": "1.0.0",
           "currency_rule": "spreadsheet_numeric_cell_exact"}
RULE = "profile:pro_vve_overzicht15_spreadsheet"

TITLE_RE = re.compile(r"Overzicht\s+\d+\s+-\s+Jarenplan\s+\(Gedetailleerd\)")
HEADER_LABELS = {"code": "Code/Element/Handeling", "location": "Locatie Element/Gebrek", "qty": "Hvh",
                 "unit": "Ehd", "stj": "Stj", "cy": "Cy", "total": "Totaal"}
GROUP_RE = re.compile(r"^(\d{2}|ZZ)$")
CODE_RE = re.compile(r"^(\d{4}|ZZZZ)$")
YEAR_RE = re.compile(r"^(19|20)\d\d$")
TOTAAL_RE = re.compile(r"^\s*Totaal\s+object\s*$")
POSTCODE_RE = re.compile(r"^([1-9]\d{3}\s?[A-Z]{2})\s+(.+)$")
VAT_RE = re.compile(r"^(Alle prijzen zijn (inclusief|exclusief) BTW\b.*)$")
FOOTER_TOKEN_RE = re.compile(r"^(\d{1,2}-\d{1,2}-\d{4}|\d{1,3})$")   # printdatum en/of paginanummer
INDEX_RE = re.compile(r"De bedragen in deze begroting zijn jaarlijks geindexeerd met .*?\(vanaf \d{4}\)\.?")


class SpreadsheetError(RuntimeError):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


def _squash(s):
    return " ".join(str(s).split())


def _dec(text):
    try:
        return Decimal(str(text))
    except (InvalidOperation, ValueError):
        return None


def _canon(d):
    """Decimal -> canonieke string zonder exponent en zonder overbodige nullen (bijv. '27339.85', '137')."""
    if d is None:
        return None
    s = format(d.normalize(), "f")
    return s


# ------------------------------------------------------------------ bladstructuur

def find_sheet(layer):
    """Het werkblad met de jarenplan-kopregel. Returns (sheet, header_row, kolommen) of SpreadsheetError."""
    for sheet in layer.get("sheets", []):
        for row in sheet["rows"]:
            cols = header_columns(row)
            if cols:
                return sheet, row, cols
    raise SpreadsheetError("geen jarenplan-kopregel (Code/Element/Handeling ... Hvh Ehd Stj Cy ... Totaal) gevonden")


def _cells(row):
    return {int(c["id"].split("-C")[1]): c for c in row["cells"]}


def header_columns(row):
    by_text = {}
    years = {}
    for col, c in _cells(row).items():
        t = _squash(c["text"])
        if YEAR_RE.match(t):
            years[col] = t
        for key, label in HEADER_LABELS.items():
            if t == label:
                by_text[key] = col
    if set(HEADER_LABELS) - set(by_text) or not years:
        return None
    cols = dict(by_text, years=dict(sorted(years.items())))
    if not (cols["code"] < cols["location"] < cols["qty"] < cols["unit"] < cols["stj"] < cols["cy"]
            < min(years) and max(years) < cols["total"]):
        return None
    return cols


def classify_rows(sheet, header, cols):
    """Classificeert elke rij na de kopregel. Returns lijst (soort, rij, info)."""
    out = []
    year_cols = set(cols["years"])
    labels = set(HEADER_LABELS.values())
    for row in sheet["rows"]:
        if row["row"] <= header["row"]:
            continue
        cells = _cells(row)
        text_cells = {c: v for c, v in cells.items() if v["type"] in ("text", "str") and _squash(v["text"])}
        num_cells = {c: v for c, v in cells.items() if v["type"] in ("number", "float", "int")}
        left = [cells[c] for c in sorted(cells) if cols["code"] <= c < cols["location"]
                and cells[c]["type"] in ("text", "str") and _squash(cells[c]["text"])]
        amounts = {c: v for c, v in num_cells.items() if c in year_cols or c == cols["total"]}
        if {_squash(v["text"]) for v in text_cells.values()} & labels and header_columns(row):
            out.append(("repeated_header", row, {}))
            continue
        if left and TOTAAL_RE.match(left[0]["text"]):
            out.append(("totaal_object", row, {"amounts": amounts}))
            continue
        if not amounts and text_cells and all(FOOTER_TOKEN_RE.match(_squash(v["text"])) for v in text_cells.values()) \
                and not num_cells:
            out.append(("footer", row, {}))
            continue
        first = cells.get(cols["code"])
        first_text = _squash(first["text"]) if first is not None else ""
        if first is not None and GROUP_RE.match(first_text) and len(left) >= 2 and not amounts:
            out.append(("group", row, {"code": first, "name": left[1:]}))
            continue
        if first is not None and CODE_RE.match(first_text) and len(left) >= 2 and not amounts:
            loc = cells.get(cols["location"])
            out.append(("element", row, {"code": first, "name": left[1:],
                                         "location": loc if loc is not None and _squash(loc["text"]) else None}))
            continue
        qty = cells.get(cols["qty"])
        if left and (first is None or not (GROUP_RE.match(first_text) or CODE_RE.match(first_text))) \
                and qty is not None:
            out.append(("action", row, {"text": left, "gebrek": cells.get(cols["location"]), "qty": qty,
                                        "unit": cells.get(cols["unit"]), "stj": cells.get(cols["stj"]),
                                        "cy": cells.get(cols["cy"]), "amounts": amounts}))
            continue
        if not left and not text_cells and amounts:
            out.append(("subtotal", row, {"amounts": amounts}))
            continue
        if not amounts and not left and text_cells and all(c > max(cols["years"]) or c == cols["total"]
                                                          for c in text_cells):
            out.append(("footer", row, {}))
            continue
        out.append(("unclassified", row, {}))
    return out


def context_cells(sheet, header):
    """Titel-, object-, BTW- en indexatiecellen vóór de kopregel (letterlijk)."""
    ctx = {"title": None, "object": None, "vat": None, "indexation": None}
    for row in sheet["rows"]:
        if row["row"] >= header["row"]:
            break
        for c in row["cells"]:
            text = c["text"]
            if ctx["title"] is None and TITLE_RE.search(text):
                ctx["title"] = c
            elif ctx["object"] is None and ctx["title"] is not None and "•" in text.split("\n")[0]:
                ctx["object"] = c
            for line in text.split("\n"):
                line = _squash(line)
                if ctx["vat"] is None and VAT_RE.match(line):
                    ctx["vat"] = (c, line)
                m = INDEX_RE.search(line)
                if ctx["indexation"] is None and m:
                    ctx["indexation"] = (c, m.group(0))
    return ctx


# ------------------------------------------------------------------ record

def _prov(doc_id, sheet, cell, rule, text=None, confidence="high", related=()):
    p = {"document_id": doc_id, "page": None, "table_index": None, "source_confidence": confidence,
         "extraction_rule": rule, "sheet": sheet["sheet"], "cell_ref": cell["cell_ref"], "block_id": cell["id"],
         "text_fragment": _squash(text if text is not None else cell["text"])}
    if related:
        p["related_block_ids"] = [r["id"] for r in related]
    return p


def _ev(value, prov=None, review=False):
    out = {"value": value, "requires_human_review": bool(review), "conflict": False}
    if prov is not None:
        out["provenance"] = prov
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


def parse_object_cell(cell):
    """'<nummer> • <naam>\\n\\n<adres>\\n[postcode ]plaats' -> (naam, adres, postcode, plaats). Letterlijk."""
    lines = [_squash(x) for x in cell["text"].split("\n") if _squash(x)]
    name = lines[0].split("•", 1)[1].strip() if "•" in lines[0] else None
    address = lines[1] if len(lines) >= 3 else None
    postcode, city = None, None
    if len(lines) >= 3:
        m = POSTCODE_RE.match(lines[-1])
        postcode, city = (m.group(1), m.group(2)) if m else (None, lines[-1])
    return name, address, postcode, city


def build_record(doc_id, layer, doc_meta, unit_tokens):
    sheet, header, cols = find_sheet(layer)
    rows = classify_rows(sheet, header, cols)
    ctx = context_cells(sheet, header)
    if ctx["title"] is None:
        raise SpreadsheetError("titel 'Overzicht NN - Jarenplan (Gedetailleerd)' ontbreekt boven de kopregel")
    header_cells = _cells(header)
    trace = {"row_reconciliation": [], "rows_without_positive_amount": [], "subtotal_rows": [],
             "repeated_header_rows": [], "footer_rows": [], "unclassified_rows": [], "totaal_object": None,
             "provenance_without_block_link": 0, "unclassified_element_overview_lines": [],
             "sheet": sheet["sheet"], "header_row": header["row"],
             "columns": {k: (v if k != "years" else {str(c): y for c, y in v.items()}) for k, v in cols.items()}}

    building = {"building_id": f"{doc_id}-BLD-001", "document_ids": [doc_id]}
    for f in ("construction_year", "number_of_units", "building_type", "inspection_date"):
        building[f] = _ev_null()
    docvals = {k: _ev_null() for k in ("object_name", "object_postcode", "object_city", "renovation_year",
                                       "price_level_date", "vat_statement", "vat_rate_text",
                                       "indexation_statement", "condition_legend")}
    building["address"] = _ev_null()
    if ctx["object"] is not None:
        name, address, postcode, city = parse_object_cell(ctx["object"])
        prov = _prov(doc_id, sheet, ctx["object"], f"{RULE}.object_cell")
        for key, val in (("object_name", name), ("object_postcode", postcode), ("object_city", city)):
            if val:
                docvals[key] = _ev(val, prov)
        if address:
            building["address"] = _ev(address, prov)
    if ctx["vat"] is not None:
        cell, line = ctx["vat"]
        docvals["vat_statement"] = _ev(line, _prov(doc_id, sheet, cell, f"{RULE}.vat_statement", text=line))
    if ctx["indexation"] is not None:
        cell, line = ctx["indexation"]
        docvals["indexation_statement"] = _ev(line, _prov(doc_id, sheet, cell, f"{RULE}.indexation_statement",
                                                          text=line))
    years = sorted(cols["years"].values())
    window_prov = _prov(doc_id, sheet, header_cells[min(cols["years"])], f"{RULE}.jarenplan.window_candidate",
                        text=header["text"], confidence="medium")
    building["mjop_period"] = {"value": None, "requires_human_review": True, "conflict": False,
                               "provenance": window_prov,
                               "possible_values": [{"value": f"{years[0]}-{years[-1]}", "provenance": window_prov}]}

    elements, el_by_row, actions, parsed_rows = [], {}, [], []
    current = None
    for kind, row, info in rows:
        if kind == "element":
            name = " ".join(_squash(c["text"]) for c in info["name"])
            loc = _squash(info["location"]["text"]) if info["location"] else None
            eid = f"{doc_id}-EL-{len(elements) + 1:03d}"
            prov = _prov(doc_id, sheet, info["code"], f"{RULE}.elements.element_row", text=row["text"],
                         related=info["name"] + ([info["location"]] if info["location"] else []))
            elements.append({
                "element_id": eid, "building_id": building["building_id"],
                "element_code": _pair(_squash(info["code"]["text"]), prov), "element_type": _pair(name, prov),
                "element_name": _ev(name, prov), "location": _ev(loc, prov) if loc else _ev_null(),
                "material": {"original_value": None, "normalized_value": None},
                "quantity": _ev_null(), "unit": {"original_value": None, "normalized_value": None},
                "construction_year": _ev_null(), "gemeenschappelijk_of_prive": None,
            })
            current = {"element_id": eid, "code": _squash(info["code"]["text"]), "description": name,
                       "location": loc or "", "row": row["row"], "cell": info["code"]}
            continue
        if kind == "group":
            current = None
            continue
        if kind in ("subtotal", "repeated_header", "footer", "unclassified"):
            trace[{"subtotal": "subtotal_rows", "repeated_header": "repeated_header_rows", "footer": "footer_rows",
                   "unclassified": "unclassified_rows"}[kind]].append({"row": row["row"], "text": row["text"][:200]})
            continue
        if kind == "totaal_object":
            trace["totaal_object"] = {"row": row["row"], "total": _canon(_dec(info["amounts"][cols["total"]]["text"]))
                                      if cols["total"] in info["amounts"] else None}
            continue
        # actierij
        amounts = {cols["years"][c]: _dec(v["text"]) for c, v in info["amounts"].items() if c in cols["years"]}
        total_cell = info["amounts"].get(cols["total"])
        total = _dec(total_cell["text"]) if total_cell else None
        positive = {y: a for y, a in sorted(amounts.items()) if a is not None and a != 0}
        s = sum(amounts.values(), Decimal("0")) if all(a is not None for a in amounts.values()) else None
        if total is None or s is None:
            status = "unparseable"
        elif total == 0 and not positive:
            status = "zero"
        else:
            status = "consistent" if s.quantize(Decimal("0.01")) == total.quantize(Decimal("0.01")) else "mismatch"
        trace["row_reconciliation"].append({"sheet": sheet["sheet"], "row": row["row"], "status": status})
        qty_cell, unit_cell = info["qty"], info["unit"]
        qty = _dec(qty_cell["text"]) if qty_cell["type"] in ("number", "float", "int") else None
        unit = _squash(unit_cell["text"]) if unit_cell is not None and _squash(unit_cell["text"]) else None
        action_text = " ".join(_squash(c["text"]) for c in info["text"])
        gebrek = _squash(info["gebrek"]["text"]) if info["gebrek"] is not None else None
        stj = _canon(_dec(info["stj"]["text"])) if info["stj"] is not None else None
        cy_raw = _canon(_dec(info["cy"]["text"])) if info["cy"] is not None else None
        parsed_rows.append({"row": row, "info": info, "element": current, "action_text": action_text,
                            "gebrek": gebrek, "qty": qty, "unit": unit, "stj": stj,
                            "cy": None if cy_raw in (None, "0") else cy_raw, "cy_raw": cy_raw,
                            "amounts": amounts, "positive": positive, "total": total, "status": status,
                            "total_cell": total_cell})
        if not positive:
            trace["rows_without_positive_amount"].append({"row": row["row"], "text": row["text"][:200], "stj": stj})
            continue
        row_prov = _prov(doc_id, sheet, info["text"][0], f"{RULE}.jarenplan.row", text=row["text"],
                         related=[c for c in (qty_cell, unit_cell, total_cell) if c is not None])
        unit_review = unit is None or unit.lower() not in unit_tokens
        for year, amount in positive.items():
            col = next(c for c, y in cols["years"].items() if y == year)
            amount_cell = info["amounts"][col]
            year_prov = dict(_prov(doc_id, sheet, amount_cell, f"{RULE}.jarenplan.year_column", text=row["text"],
                                   related=[header_cells[col]]))
            amt_prov = _prov(doc_id, sheet, amount_cell, f"{RULE}.{PROFILE['currency_rule']}", text=row["text"])
            review = (current is None or status in ("mismatch", "unparseable") or qty is None or unit_review)
            actions.append({
                "action_id": f"{doc_id}-ACT-{len(actions) + 1:03d}",
                "element_id": current["element_id"] if current else f"{doc_id}-EL-UNLINKED",
                "action": _pair(action_text or None, row_prov),
                "planned_year": _ev(int(year), year_prov),
                "quantity": _ev(_canon(qty), row_prov, review=qty is None),
                "unit": _pair(unit, row_prov, review=unit_review),
                "unit_cost": {"value": None, "is_estimated": False},
                "cost_year": None,
                "total_cost_as_stated": _canon(amount),
                "field_provenance": {"total_cost_as_stated": amt_prov},
                "requires_human_review": review,
                "source_page": None,
            })
    record = {
        "status": "extracted", "document_id": doc_id, "batch": "incoming", "extraction_mode": "deterministic",
        "extraction_notes": ("Deterministische spreadsheet-extractie (xlrd/openpyxl via text_layer, geen AI, geen "
                             "netwerk). Kolommen uit de kopregel; subtotaal-, Totaal object-, kop- en voettekstregels "
                             "worden nooit acties. Provenance = werkblad + celadres + blok-ID."),
        "extraction_metadata": {
            "extractor": "spreadsheet_extraction.py", "extractor_version": EXTRACTOR_VERSION,
            "parser": "spreadsheet_extraction", "document_profile": PROFILE["profile_id"],
            "profile_version": PROFILE["profile_version"], "rules_version": RULES_VERSION,
            "currency_rule": PROFILE["currency_rule"], "source_relative_path": doc_meta["relative_path"],
            "source_sha256": doc_meta["sha256"], "text_layer_sha256": layer["text_layer_sha256"],
            "text_layer_generator": layer["generator"], "file_type": layer["file_type"],
            "uses_ai_api": False, "network_calls": False,
        },
        "building": building, "elements": elements, "observations": [], "maintenance_actions": actions,
        "document_level_values": docvals, "deterministic_trace": trace,
    }
    return record, {"sheet": sheet, "header": header, "cols": cols, "rows": parsed_rows, "ctx": ctx}


def validate(record):
    errors = rv.validate_entities(record)
    reg = rv.schema_registry()
    for k, v in record.get("document_level_values", {}).items():
        errors += [f"document_level_values.{k} {e}" for e in rv.schema_errors(v, "_extracted_value.schema.json", reg)]
    return errors


def extract_spreadsheet(doc_id, layer, doc_meta, unit_tokens):
    """Returns (record, parse). Gooit SpreadsheetError bij een structuur die niet past of schemafouten."""
    record, parse = build_record(doc_id, layer, doc_meta, unit_tokens)
    errors = validate(record)
    if errors:
        raise SpreadsheetError(f"{doc_id}: validatie mislukt ({len(errors)} fouten)", errors)
    return record, parse


# ------------------------------------------------------------------ price observations (zelfde regels als PDF)

def _nl(d):
    """Decimal -> NL-notatie voor build_price_observations (komma = decimaal, geen duizendtal)."""
    return None if d is None else _canon(d).replace(".", ",")


def build_observations(record, parse, doc, doc_ctx, unit_lookup, verified):
    """Price observations per actierij met exact de bestaande regels (build_row_observation,
    link_verified_actions, build_relations). Alleen de bronverwijzing is spreadsheet-specifiek."""
    import build_price_observations as bpo
    sheet, cols = parse["sheet"], parse["cols"]
    si = sheet["sheet_index"]
    years = sorted(cols["years"].values())
    obs = []
    for pr in parse["rows"]:
        el = pr["element"]
        row = {
            "page": 1, "line": 1,
            "action_text": pr["action_text"], "gebrek_or_location_text": pr["gebrek"] or "",
            "quantity_as_stated": _nl(pr["qty"]) if pr["qty"] is not None else "",
            "unit_original": pr["unit"], "stj": pr["stj"], "cy": pr["cy"],
            "annual_amounts_raw": {y: _nl(a) for y, a in pr["positive"].items()},
            "total_as_stated": _nl(pr["total"]), "window": [years[0], years[-1]],
            "element_context_source": "same_sheet" if el else None, "element_candidate_previous_page": None,
            "raw_line": _squash(pr["row"]["text"]), "continuation_lines": [],
            "element": ({"code": el["code"], "description": el["description"], "location": el["location"],
                         "page": 1, "line": 1, "description_first_line": el["description"],
                         "continuation_lines": [], "excluded_tokens": []} if el else None),
        }
        o = bpo.build_row_observation(doc, row, doc_ctx, unit_lookup)
        if o["total_value"] is not None and Decimal(o["total_value"]) == 0 and not o["annual_amounts"]:
            continue
        info = pr["info"]
        refs = {"action_text": info["text"][0]["cell_ref"], "quantity": info["qty"]["cell_ref"]}
        for k in ("unit", "stj", "cy", "gebrek"):
            if info.get(k) is not None:
                refs[k] = info[k]["cell_ref"]
        if pr["total_cell"] is not None:
            refs["total"] = pr["total_cell"]["cell_ref"]
        for c, v in info["amounts"].items():
            if c in cols["years"] and cols["years"][c] in pr["positive"]:
                refs[f"amount_{cols['years'][c]}"] = v["cell_ref"]
        o["observation_id"] = f"PO-{doc['document_id']}-S{si:02d}-R{pr['row']['row']:04d}"
        rep = o["source_representations"][0]
        rep.update(page=None, line=None, sheet=sheet["sheet"], row=pr["row"]["row"], cell_refs=refs,
                   continuation_lines=[],
                   element_line=({"page": None, "line": None, "sheet": sheet["sheet"], "row": el["row"],
                                  "cell_ref": el["cell"]["cell_ref"]} if el else None))
        if pr["cy_raw"] == "0":
            o["cycle_length_as_stated"] = None
            o.setdefault("provenance_gaps", [])
        obs.append(o)
    bpo.link_verified_actions(obs, verified)
    relations = bpo.build_relations({doc["document_id"]: obs}, [])
    return obs, relations
