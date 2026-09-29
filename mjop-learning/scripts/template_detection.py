#!/usr/bin/env python3
"""
template_detection.py - bestandsformaat en documentfamilie herkennen (incoming pipeline v1).

Twee stappen, allebei deterministisch en zonder AI:

1. Formaat op basis van de INHOUD (magic bytes), niet de bestandsnaam:
     %PDF-                      -> pdf
     OLE2 (D0 CF 11 E0 ...)     -> xls
     ZIP met xl/workbook.xml    -> xlsx
   De extensie moet daarmee overeenkomen; anders UNSUPPORTED_FORMAT (FORMAT_MISMATCH).

2. Documentfamilie + variant op basis van structurele kenmerken in de tekstlaag (text_layer.py).
   Elke variant noemt expliciet welke kenmerken VERPLICHT aanwezig en welke VERPLICHT afwezig zijn;
   de eerste exacte match wint. Elke andere combinatie = UNKNOWN_TEMPLATE, met per variant uitleg
   waarom niet (explanation). Nooit gokken, nooit op bestandsnaam.

   pro_vve_overzicht15 (vvem-rapportsoftware), kenmerken: 'Algemene Objectgegevens', 'Elementenoverzicht',
   'Overzicht NN - Jarenplan (Gedetailleerd)', kolomkop 'Hvh Ehd Stj Cy', 'Totaal object',
   'Overzicht projecten', 'Overzicht NN - jarenplan' (zonder '(...)'):
     standard                      objectblad + elementenoverzicht + jarenplan (Gedetailleerd) (batch 1)
     multi_object_projects         meer objecten: objectblad + elementenoverzicht + 'Overzicht projecten' /
                                   'Overzicht NN - jarenplan', GEEN '(Gedetailleerd)'-titel
     jarenplan_without_objectblad  jarenplan (Gedetailleerd) ingebed in een rapport, ZONDER objectblad en
                                   elementenoverzicht (elementen uit de jarenplan-elementregels)
   Tijdens de extractie worden de vereiste secties per variant herhaald op de xpdf-tekst.

   pro_vve_overzicht15_spreadsheet (export van het jarenplan, bijv. DOC-003/DOC-015):
     jarenplan_sheet               titel + kolomkop Hvh | Ehd | Stj | Cy + 'Totaal object'
   Deterministische productie-parser: scripts/spreadsheet_extraction.py (xlrd/openpyxl via text_layer).
"""
import os
import re
import zipfile

DETECTION_VERSION = "template_detection_v1"

OLE2_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
EXTENSIONS = {".pdf": "pdf", ".xls": "xls", ".xlsx": "xlsx"}

_TITLE = re.compile(r"Overzicht\s+\d+\s+-\s+Jarenplan\s+\(Gedetailleerd\)")
# titel van de gecombineerde meer-objecten-weergave: 'Overzicht 15 - jarenplan' ZONDER '(...)' erachter
# (de Hoofdgroepen-titel 'Overzicht 15 - Jarenplan (Hoofdgroepen)' valt hier dus niet onder)
_TITLE_PROJECTS = re.compile(r"Overzicht\s+\d+\s+-\s+jarenplan\s*$", re.IGNORECASE)
_PROJECTS = re.compile(r"^\s*Overzicht\s+projecten\s*$")
_HEADER = re.compile(r"Hvh\s*\|?\s*Ehd\s*\|?\s*Stj\s*\|?\s*Cy")
_TOTAAL = re.compile(r"Totaal\s+object")

PDF_MARKERS = {
    "object_sheet": re.compile(r"Algemene\s+Objectgegevens"),
    "element_overview": re.compile(r"Elementenoverzicht"),
    "jarenplan_title": _TITLE,
    "jarenplan_header": _HEADER,
    "totaal_object": _TOTAAL,
    "projects_overview": _PROJECTS,
    "jarenplan_title_projects": _TITLE_PROJECTS,
}
# Varianten van de familie pro_vve_overzicht15 (vvem-rapportsoftware). Elke variant noemt welke
# kenmerken VERPLICHT aanwezig en welke VERPLICHT afwezig zijn; de eerste exacte match wint.
# Andere combinaties = UNKNOWN_TEMPLATE (nooit gokken). De jarenplantabel zelf (kolomkop Hvh Ehd Stj Cy
# + 'Totaal object') is in elke variant verplicht: dat is de tabel die de bestaande parser leest.
PDF_VARIANTS = [
    {"variant": "standard",
     "required": ["object_sheet", "element_overview", "jarenplan_title", "jarenplan_header", "totaal_object"],
     "absent": [],
     "sections": ["OBJECT", "ELEMENTEN", "JARENPLAN"],
     "why": "objectblad, elementenoverzicht en 'Overzicht NN - Jarenplan (Gedetailleerd)' van de vvem-software"},
    {"variant": "multi_object_projects",
     "required": ["object_sheet", "element_overview", "jarenplan_header", "totaal_object", "projects_overview",
                  "jarenplan_title_projects"],
     "absent": ["jarenplan_title"],
     "sections": ["OBJECT", "ELEMENTEN", "JARENPLAN"],
     "why": "zelfde vvem-software, meer objecten: gecombineerd 'Overzicht NN - jarenplan' / 'Overzicht projecten' "
            "met per object een objectregel en objectsubtotaal, en één 'Totaal object'"},
    {"variant": "jarenplan_without_objectblad",
     "required": ["jarenplan_title", "jarenplan_header", "totaal_object"],
     "absent": ["object_sheet", "element_overview"],
     "sections": ["JARENPLAN"],
     "why": "vvem-jarenplan (Gedetailleerd) ingebed in een rapport zonder objectblad en elementenoverzicht; "
            "elementen alleen uit de elementregels van het jarenplan, objectvelden blijven leeg"},
]
SPREADSHEET_MARKERS = {"jarenplan_title": _TITLE, "jarenplan_header": _HEADER, "totaal_object": _TOTAAL}

FAMILIES = {
    "pdf": {"family_id": "pro_vve_overzicht15", "markers": PDF_MARKERS, "variants": PDF_VARIANTS,
            "extraction": "deterministic_xpdf"},
    "spreadsheet": {
        "family_id": "pro_vve_overzicht15_spreadsheet", "markers": SPREADSHEET_MARKERS,
        "variants": [{"variant": "jarenplan_sheet", "required": list(SPREADSHEET_MARKERS), "absent": [],
                      "sections": [],
                      "why": "spreadsheet-export van 'Overzicht NN - Jarenplan (Gedetailleerd)' (kolomkop "
                             "Hvh | Ehd | Stj | Cy, jaarkolommen, 'Totaal object')"}],
        "extraction": "deterministic_xlrd"},
}

# Profielen per (familie, variant). De standaardvariant is exact het batch-1-profiel (geen extra velden),
# zodat bestaande documenten byte-gelijk blijven. Varianten voegen alleen expliciete opties toe.
_BASE_PROFILE = {
    "profile_id": "pro_vve_overzicht15",
    "profile_version": "1.0.0",
    "currency_rule": "pdf_whole_euro_dot_thousands",
    "note": "Nieuw document via de incoming pipeline; familie herkend op structurele kenmerken "
            "(template_detection_v1). Geen documentspecifieke regels.",
}
VARIANT_PROFILES = {
    ("pro_vve_overzicht15", "standard"): dict(_BASE_PROFILE),
    ("pro_vve_overzicht15", "multi_object_projects"): dict(_BASE_PROFILE, profile_variant="multi_object_projects"),
    ("pro_vve_overzicht15", "jarenplan_without_objectblad"): dict(
        _BASE_PROFILE, profile_variant="jarenplan_without_objectblad",
        elements_source="jarenplan_element_lines", jarenplan_vat_fallback=True),
}
FAMILY_PROFILES = {"pro_vve_overzicht15": VARIANT_PROFILES[("pro_vve_overzicht15", "standard")]}

# secties die classify_sections op de xpdf-tekst moet vinden (herhaalde herkenning), per variant
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
    """Returns dict: family_id | None, variant | None, markers {naam: eerste locatie | None}, reason,
    explanation (waarom wel/niet: per variant welke verplichte kenmerken ontbreken of welke
    verplicht-afwezige kenmerken toch aanwezig zijn)."""
    kind = "pdf" if fmt == "pdf" else "spreadsheet"
    fam = FAMILIES[kind]
    lines = layer_lines(layer)
    base = {"detection_version": DETECTION_VERSION, "family_id": None, "variant": None, "extraction": None}
    if fmt == "pdf" and layer.get("pages") and all(p.get("text_status") == "no_text_layer" for p in layer["pages"]):
        return dict(base, markers={k: None for k in fam["markers"]}, reason="NO_TEXT_LAYER",
                    explanation=["geen tekstlaag (gescand?) - geen OCR in v1"])
    found = {name: next((loc for loc, text in lines if rx.search(text)), None) for name, rx in fam["markers"].items()}
    explanation = []
    for v in fam["variants"]:
        missing = [m for m in v["required"] if not found[m]]
        unexpected = [m for m in v["absent"] if found[m]]
        if not missing and not unexpected:
            explanation.insert(0, f"{fam['family_id']}/{v['variant']}: " + ", ".join(
                f"{m}@{found[m]}" for m in v["required"]) + (
                f"; afwezig: {', '.join(v['absent'])}" if v["absent"] else "") + f" - {v['why']}")
            return dict(base, family_id=fam["family_id"], variant=v["variant"], markers=found, reason=None,
                        explanation=explanation, extraction=fam["extraction"], required_sections=v["sections"])
        explanation.append(f"niet {v['variant']}: ontbreekt {missing or '-'}; onverwacht aanwezig {unexpected or '-'}")
    return dict(base, markers=found, explanation=explanation,
                reason="PARTIAL_FAMILY_MARKERS" if any(found.values()) else "NO_FAMILY_MARKERS")


def profile_for(family_id, variant):
    return VARIANT_PROFILES.get((family_id, variant))


def recheck_on_xpdf_pages(sections, required=REQUIRED_XPDF_SECTIONS):
    """sections = mjop_source_sections.classify_sections(pages). Returns lijst ontbrekende secties."""
    present = {s for _, s in sections if s}
    return [s for s in required if s not in present]
