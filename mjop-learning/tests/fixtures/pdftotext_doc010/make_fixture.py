#!/usr/bin/env python3
"""
Genereert tests/fixtures/pdftotext_doc010/pages.json: een KLEINE, handmatig
samengestelde benadering van `pdftotext -table` (xpdf 4.06) voor DOC-010.

Inhoud: uitsluitend letterlijke DOC-010-regels (zie README.md voor de herkomst
per regel). Opmaak (kolomposities, lege regels tussen tabelregels) volgt
dezelfde aanpak als de bestaande helpers in tests/test_price_observations.py.
De exacte spatiëring van echte xpdf-output is hier NIET gegarandeerd; de echte
pilot op een lokale pc met xpdf 4.06 is de toets daarvoor.

Deze fixture vervangt alleen de externe executable (via tests/fixtures/
fake_pdftotext.py); mjop_source_sections zelf wordt ongewijzigd gebruikt.

Gebruik:  python3 tests/fixtures/pdftotext_doc010/make_fixture.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
N_PAGES = 17  # DOC-010 heeft 17 pagina's; paginanummers blijven gelijk aan de PDF

# --- Jarenplan (Gedetailleerd) ---------------------------------------------
YEARS = [str(y) for y in range(2023, 2038)]
JP_HEADER = ("Code/Element/Handeling                   Locatie Element/Gebrek        Hvh     Ehd  Stj   Cy  "
             + "  ".join(f"  {y}" for y in YEARS) + "     Totaal")


def _span(header, col):
    i = header.index(col)
    return i, i + len(col)


def jp_line(left="", loc_text="", cells=()):
    buf = [" "] * (len(JP_HEADER) + 12)

    def put(start, tok):
        for k, ch in enumerate(tok):
            buf[start + k] = ch

    put(0, left)
    if loc_text:
        put(_span(JP_HEADER, "Locatie")[0], loc_text)
    for col, tok in cells:
        s, e = _span(JP_HEADER, col)
        if col in ("Stj", "Cy", "Ehd"):
            put(s, tok)
        else:  # Hvh, jaarkolommen, Totaal: rechts uitgelijnd
            put(e - len(tok), tok)
    return "".join(buf).rstrip()


def jp_page(*lines):
    return "\n\n".join((JP_HEADER,) + lines) + "\n"


# --- Elementenoverzicht -------------------------------------------------------
OV_HEADER = "Code    Element                                   Locatie                     HvhEhd   Conditie"


def ov_row(code, name, loc, qty_unit, cond):
    buf = [" "] * (len(OV_HEADER) + 4)

    def put(start, tok):
        for k, ch in enumerate(tok):
            buf[start + k] = ch

    put(0, code)
    put(OV_HEADER.index("Element"), name)
    if loc:
        put(OV_HEADER.index("Locatie"), loc)
    e = OV_HEADER.index("HvhEhd") + len("HvhEhd")
    put(e - len(qty_unit), qty_unit)
    put(OV_HEADER.index("Conditie") + 3, cond)
    return "".join(buf).rstrip()


def ov_page(*lines):
    return "\n\n".join(("Zomerdijkstraat • VvE Zomerdijkstraat 14", OV_HEADER) + lines) + "\n"


def label(lbl, value=""):
    return f"{lbl:<30}{value}".rstrip()


def build():
    pages = {n: "" for n in range(1, N_PAGES + 1)}
    pages[2] = "\n\n".join([
        "Zomerdijkstraat • VvE Zomerdijkstraat 14",
        "Algemene Objectgegevens",
        "Code",
        label("Code", "Zomerdijkstraat"),
        "Object",
        label("Naam", "VvE Zomerdijkstraat 14"),
        label("Aantal eenheden", "4"),
        label("Adres", "Zomerdijkstraat 14, Uiterwaardenstraat 141"),
        label("Postcode", "1079 XB"),
        label("Plaats", "Amsterdam"),
        label("Inspectiedatum", "1-4-2023"),
        "Opdrachtgever",
        label("Adres", "Zomerdijkstraat 14, Uiterwaardestraat 141"),
        label("Postcode", "1079 XB"),
        label("Plaats", "Amsterdam"),
        "Technisch",
        label("Bouwjaar", "1935"),
        label("Renovatiejaar", "2005"),
        "Financieel",
        label("Prijspeil", "1-4-2023"),
        label("BTW", "De bedragen in de begrotingen zijn inclusief BTW"),
        label("BTW tarief", "Hoog/Laag tarief is toegepast: Hoog = 9,0%; Laag = 21,0%"),
        "13-4-2023 2",
    ]) + "\n"
    pages[5] = "\n\n".join([
        "Elementenoverzicht",
        "Toelichting:",
        "1 = Uitstekende conditie",
        "2 = Goed",
        "3 = Redelijk",
        "4 = Matig",
        "5 = Slecht",
        "6 = Zeer slecht",
        "8 = Nader onderzoek nodig",
        "9 = Niet te inspecteren",
        "13-4-2023 5",
    ]) + "\n"
    pages[6] = ov_page(
        "21      Buitenwanden",
        ov_row("2110", "Gevelconstructie metselwerk", "Voor- en achtergevel", "148,25m2", "2"),
        ov_row("2110", "Loodslabben opgaand werk", "Dak", "10,00m1", "2"),
        ov_row("2120", "Hijsbalk staal", "Achtergevel", "1,00st", "8"),
        "31      Buitenwandopeningen",
        ov_row("3120", "Kozijn buiten aluminium", "Voor- en achtergevel", "84,28m2", "3"),
        "13-4-2023 6",
    )
    pages[8] = ov_page(
        "67      Gebouwbeheersvoorzieningen",
        ov_row("6710", "Dakbeveiliging algemeen", "Dak", "1,00pst", "0"),
        "99      Algemeen",
        ov_row("9999", "Hoogwerker tot 18 meter hoog", "", "1,00pst", "0"),
        "13-4-2023 8",
    )
    pages[9] = "\n\n".join([
        "Overzicht 15 - Jarenplan (Gedetailleerd)",
        "Alle prijzen zijn inclusief BTW - (hoog/laag BTW tarief is toegepast)",
        "De bedragen in deze begroting zijn jaarlijks geindexeerd met 0 Procent (vanaf 2023).",
        "Printdatum: 13-4-2023",
    ]) + "\n"
    subtotal = [(y, "0") for y in YEARS]
    subtotal[YEARS.index("2028")] = ("2028", "1.841")
    subtotal[YEARS.index("2034")] = ("2034", "491")
    pages[10] = jp_page(
        jp_line("21  Buitenwanden"),
        jp_line("2110  Gevelconstructie metselwerk", "Voor- en achtergevel"),
        jp_line("      Herstellen metselwerk", "", [("Hvh", "5,93"), ("Ehd", "m2"), ("Stj", "2028"), ("Cy", "12"),
                                                   ("2028", "1.351"), ("Totaal", "1.351")]),
        jp_line("2120  Hijsbalk staal", "Achtergevel"),
        jp_line("      Vervangen hijswerk staal", "", [("Hvh", "1,00"), ("Ehd", "st"), ("Stj", "2052"),
                                                      ("Totaal", "0")]),
        jp_line("      Keuren hanebalk", "", [("Hvh", "1,00"), ("Ehd", "m2"), ("Stj", "2028"), ("Cy", "6"),
                                             ("2028", "491"), ("2034", "491"), ("Totaal", "981")]),
        jp_line("", "", subtotal + [("Totaal", "2.332")]),
        jp_line("31  Buitenwandopeningen"),
        jp_line("3120  Kozijn buiten aluminium", "Voor- en achtergevel"),
        jp_line("      Onderhoud kozijnen (confrom offerte", "", [("Hvh", "84,28"), ("Ehd", "m2"), ("Stj", "2028"),
                                                                ("2028", "11.024"), ("Totaal", "11.024")]),
        jp_line("      Kemo)"),
        "13-4-2023 10",
    )
    return {"_note": "Zie README.md: letterlijke DOC-010-regels, benaderde pdftotext -table-opmaak.",
            "pages": [pages[n] for n in range(1, N_PAGES + 1)]}


if __name__ == "__main__":
    with open(os.path.join(HERE, "pages.json"), "w", encoding="utf-8") as f:
        json.dump(build(), f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("pages.json geschreven")
