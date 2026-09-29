#!/usr/bin/env python3
"""
template_detection.py - bestandsformaat en documentfamilie herkennen (incoming pipeline v1).

Twee stappen, allebei deterministisch en zonder AI:

1. Formaat op basis van de INHOUD (magic bytes), niet de bestandsnaam:
     %PDF-                      -> pdf
     OLE2 (D0 CF 11 E0 ...)     -> xls
     ZIP met xl/workbook.xml    -> xlsx
   De extensie moet daarmee overeenkomen; anders UNSUPPORTED_FORMAT (FORMAT_MISMATCH).

2. Documentfamilie op basis van structurele kenmerken in de tekstlaag (text_layer.py). Een familie
   wordt alleen herkend als ALLE verplichte kenmerken aanwezig zijn. Gedeeltelijk = niet herkend
   (UNKNOWN_TEMPLATE, met de gevonden kenmerken als uitleg). Nooit gokken.

   pro_vve_overzicht15 (vvem-rapportformaat, profiel van batch 1):
     - 'Algemene Objectgegevens'                        (objectblad)
     - 'Elementenoverzicht'
     - 'Overzicht NN - Jarenplan (Gedetailleerd)'       (titel)
     - kolomkop 'Hvh Ehd Stj Cy' op één regel            (jarenplantabel)
     - 'Totaal object'                                  (eigen controletotaal)
   Tijdens de extractie wordt de herkenning herhaald op de xpdf-tekst (classify_sections):
   OBJECT, ELEMENTEN en JARENPLAN moeten daar ook gevonden worden.

   pro_vve_overzicht15_spreadsheet (losse spreadsheet-export van het jarenplan, zoals DOC-003):
     - titel 'Overzicht NN - Jarenplan (Gedetailleerd)'
     - kolomkop met Hvh | Ehd | Stj | Cy
     - 'Totaal object'
   Hiervoor bestaat nog GEEN productie-parser: de pipeline zet zo'n bestand op REVIEW_REQUIRED
   (UNSUPPORTED_EXTRACTION), nooit op een AI-route.
"""
import os
import re
import zipfile

DETECTION_VERSION = "template_detection_v1"

OLE2_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
EXTENSIONS = {".pdf": "pdf", ".xls": "xls", ".xlsx": "xlsx"}

_TITLE = re.compile(r"Overzicht\s+\d+\s+-\s+Jarenplan\s+\(Gedetailleerd\)")
_HEADER = re.compile(r"Hvh\s*\|?\s*Ehd\s*\|?\s*Stj\s*\|?\s*Cy")
_TOTAAL = re.compile(r"Totaal\s+object")

FAMILIES = {
    "pdf": {
        "family_id": "pro_vve_overzicht15",
        "markers": {
            "object_sheet": re.compile(r"Algemene\s+Objectgegevens"),
            "element_overview": re.compile(r"Elementenoverzicht"),
            "jarenplan_title": _TITLE,
            "jarenplan_header": _HEADER,
            "totaal_object": _TOTAAL,
        },
        "extraction": "deterministic_xpdf",
    },
    "spreadsheet": {
        "family_id": "pro_vve_overzicht15_spreadsheet",
        "markers": {
            "jarenplan_title": _TITLE,
            "jarenplan_header": _HEADER,
            "totaal_object": _TOTAAL,
        },
        "extraction": None,   # geen productie-parser -> UNSUPPORTED_EXTRACTION
    },
}

# Profiel voor NIEUWE documenten van een herkende familie. Identiek aan de batch-1-profielen,
# zonder documentspecifieke uitzonderingen: de valutaregel werkt alleen met documentbewijs
# (nl_values.parse_currency_profile), zonder bewijs blijft een bedrag null + review.
FAMILY_PROFILES = {
    "pro_vve_overzicht15": {
        "profile_id": "pro_vve_overzicht15",
        "profile_version": "1.0.0",
        "currency_rule": "pdf_whole_euro_dot_thousands",
        "note": "Nieuw document via de incoming pipeline; familie herkend op structurele kenmerken "
                "(template_detection_v1). Geen documentspecifieke regels.",
    },
}

# secties die classify_sections op de xpdf-tekst moet vinden (herhaalde herkenning)
REQUIRED_XPDF_SECTIONS = ("OBJECT", "ELEMENTEN", "JARENPLAN")


def detect_format(path):
    """Returns (format | None, reason | None). format in {'pdf','xls','xlsx'}."""
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        head = f.read(8)
    if head.startswith(b"%PDF-"):
        content = "pdf"
    elif head == OLE2_MAGIC:
        content = "xls"
    elif head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as z:
                content = "xlsx" if "xl/workbook.xml" in z.namelist() else None
        except zipfile.BadZipFile:
            content = None
    else:
        content = None
    if ext not in EXTENSIONS:
        return None, "UNSUPPORTED_EXTENSION"
    if content is None:
        return None, "UNRECOGNIZED_CONTENT"
    if EXTENSIONS[ext] != content:
        return None, "FORMAT_MISMATCH"
    return content, None


def layer_lines(layer):
    """(locatie, tekst) per regel/rij uit een text_layer, in documentvolgorde."""
    out = []
    for page in layer.get("pages", []):
        for line in page.get("lines", []):
            out.append((f"p{page['page']}", line.get("text", "")))
    for sheet in layer.get("sheets", []):
        for row in sheet.get("rows", []):
            out.append((f"s{sheet['sheet_index']}r{row['row']}", row.get("text", "")))
    return out


def detect_family(fmt, layer):
    """Returns dict: family_id | None, markers {naam: eerste locatie | None}, reason."""
    kind = "pdf" if fmt == "pdf" else "spreadsheet"
    fam = FAMILIES[kind]
    lines = layer_lines(layer)
    if fmt == "pdf" and layer.get("pages") and all(p.get("text_status") == "no_text_layer" for p in layer["pages"]):
        return {"family_id": None, "markers": {k: None for k in fam["markers"]}, "reason": "NO_TEXT_LAYER",
                "detection_version": DETECTION_VERSION}
    found = {}
    for name, rx in fam["markers"].items():
        found[name] = next((loc for loc, text in lines if rx.search(text)), None)
    complete = all(found.values())
    return {
        "family_id": fam["family_id"] if complete else None,
        "markers": found,
        "reason": None if complete else ("PARTIAL_FAMILY_MARKERS" if any(found.values()) else "NO_FAMILY_MARKERS"),
        "detection_version": DETECTION_VERSION,
        "extraction": fam["extraction"] if complete else None,
    }


def recheck_on_xpdf_pages(sections):
    """sections = mjop_source_sections.classify_sections(pages). Returns lijst ontbrekende secties."""
    present = {s for _, s in sections if s}
    return [s for s in REQUIRED_XPDF_SECTIONS if s not in present]
