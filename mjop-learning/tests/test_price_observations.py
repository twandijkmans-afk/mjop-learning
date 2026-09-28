"""
Tests voor de price observation source layer (scripts/mjop_source_sections.py
en scripts/build_price_observations.py). Getest worden vooral de regels uit
de bronanalyse:

  - 1 jarenplan-rij met bedrag > 0 = 1 observation; rijen zonder bedrag niet
  - total_scope / occurrences_in_window uit de jaarkolommen, alleen binnen het venster
  - lege Cy blijft null; Stj letterlijk
  - geen prijspeil afleiden als de bron geen 'Prijspeil' geeft
  - unit_price_calculated niet bij stelposten; bij meerdere uitvoeringen
    expliciet gemarkeerd als verhouding over het rijtotaal
  - Jaarplan/Bevindingen worden bronweergave, nooit een extra observation
  - DOC-003 (duplicate_source) levert geen observations op
  - NO_DEPENDENCY_FOUND is geen INDEPENDENT; identieke rijen -> UNKNOWN

De integratietest onderaan draait op de echte PDF's en wordt overgeslagen als
pdftotext (xpdf 4.06) niet beschikbaar is.
"""
import copy
import json
import os
import sys

import jsonschema
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import build_price_observations as bpo  # noqa: E402
import mjop_source_sections as src  # noqa: E402
from normalize_batch import load_vocab  # noqa: E402

HEADER = ("Code/Element/Handeling                              Locatie Element/Gebrek        Hvh     Ehd  Stj   Cy    "
          "2026    2027    2028    Totaal")


def _span(col):
    i = HEADER.index(col)
    return i, i + len(col)


def line(left="", loc_text="", cells=()):
    """Bouwt een tabelregel zoals pdftotext -table die oplevert: tekst links,
    hoeveelheid/eenheid onder Hvh/Ehd, Stj/Cy gecentreerd, bedragen rechts
    uitgelijnd onder hun jaarkolom/Totaal."""
    buf = [" "] * (len(HEADER) + 12)

    def put(start, tok):
        for k, ch in enumerate(tok):
            buf[start + k] = ch

    put(0, left)
    if loc_text:
        put(_span("Locatie")[0], loc_text)
    for col, tok in cells:
        s, e = _span(col)
        if col in ("Stj", "Cy", "Ehd"):
            put(s, tok)
        else:  # Hvh, jaarkolommen en Totaal rechts uitgelijnd
            put(e - len(tok), tok)
    return "".join(buf).rstrip()


def page(*lines_):
    # pdftotext -table zet lege regels tussen de tabelregels
    return "\n\n".join((HEADER,) + lines_)


DOC = {"document_id": "DOC-900", "relative_path": "x/test.pdf", "sha256": "abc", "file_type": "pdf"}
CTX_EXPLICIT = {"price_level_date": "1-8-2026", "price_level_basis": "explicit", "vat_basis": "inclusive",
                "vat_text": "De bedragen in de begrotingen zijn inclusief BTW", "vat_rate_text": None,
                "indexation_statement": None}
UNITS = load_vocab(os.path.join(PROJECT_ROOT, "vocabularies"), "unit")
PDFTOTEXT = src.find_pdftotext()


def one_row(text, page_no=11, carry=None):
    rows, _, _ = src.parse_jarenplan_page(text, page_no, carry)
    assert len(rows) == 1
    return rows[0]


def obs_for(row):
    return bpo.build_row_observation(DOC, row, CTX_EXPLICIT, UNITS)


# --------------------------------------------------------------------------
# Jarenplan-rijen
# --------------------------------------------------------------------------

def test_multiple_executions_row_scope_and_cycle():
    text = page(
        line("2110  Gevelconstructie metselwerk", "Alle gevels"),
        line("      Reinigen metselwerk", "", [("Hvh", "815,95"), ("Ehd", "m2"), ("Stj", "2026"), ("Cy", "2"),
                                                ("2026", "8.955"), ("2028", "8.955"), ("Totaal", "17.910")]),
    )
    o = obs_for(one_row(text))
    assert o["total_scope"] == "MULTIPLE_EXECUTIONS"
    assert o["occurrences_in_window"] == 2
    assert o["annual_amounts"] == {"2026": "8955", "2028": "8955"}
    assert o["cycle_start_year"] == 2026 and o["cycle_length_years"] == 2
    assert o["element"]["element_code_original"] == "2110"
    assert o["execution_window_start"] == 2026 and o["execution_window_end"] == 2028


def test_multiple_executions_calculated_price_is_marked_as_row_total_ratio():
    text = page(line("2110  Gevelconstructie metselwerk", "Alle gevels"),
                line("      Reinigen metselwerk", "", [("Hvh", "815,95"), ("Ehd", "m2"), ("Stj", "2026"), ("Cy", "2"),
                                                        ("2026", "8.955"), ("2028", "8.955"), ("Totaal", "17.910")]))
    o = obs_for(one_row(text))
    assert o["unit_price_calculated"] == "21.95"  # 17.910 / 815,95 - over het rijtotaal
    assert o["calculated_unit_price_basis"] == "row_total_over_multiple_executions_in_window"
    assert o["unit_price_literal"] is None


def test_blank_cy_stays_null_and_is_not_invented():
    text = page(line("4320  Parkeerdek vloer"),
                line("      Herstellen", "Lekkage", [("Hvh", "1,00"), ("Ehd", "pst"), ("Stj", "2027"),
                                                     ("2027", "10.285"), ("Totaal", "10.285")]))
    o = obs_for(one_row(text))
    assert o["cycle_length_years"] is None
    assert o["cycle_length_as_stated"] is None
    assert o["cycle_start_year"] == 2027


def test_lump_sum_gets_no_calculated_unit_price():
    text = page(line("4320  Parkeerdek vloer"),
                line("      Herstellen", "Lekkage", [("Hvh", "1,00"), ("Ehd", "pst"), ("Stj", "2027"),
                                                     ("2027", "10.285"), ("Totaal", "10.285")]))
    o = obs_for(one_row(text))
    assert o["unit_price_calculated"] is None
    assert o["price_type"] is None
    assert "lump_sum" in o["calculated_unit_price_not_computed_reason"]


def test_rounded_amounts_still_reconcile():
    """Bron: 7.400 + 7.400 bij Totaal 14.799 (afronding in de bron)."""
    text = page(line("2110  Gevelconstructie metselwerk"),
                line("      Reinigen metselwerk", "", [("Hvh", "815,95"), ("Ehd", "m2"), ("Stj", "2026"), ("Cy", "2"),
                                                        ("2026", "7.400"), ("2028", "7.400"), ("Totaal", "14.799")]))
    o = obs_for(one_row(text))
    assert o["amount_reconciliation"] == "consistent"
    assert o["total_scope"] == "MULTIPLE_EXECUTIONS"


def test_non_reconciling_row_gets_unknown_scope_and_no_price():
    text = page(line("2110  Gevelconstructie metselwerk"),
                line("      Reinigen metselwerk", "", [("Hvh", "10,00"), ("Ehd", "m2"), ("Stj", "2026"), ("Cy", "2"),
                                                        ("2026", "100"), ("Totaal", "900")]))
    o = obs_for(one_row(text))
    assert o["total_scope"] == "UNKNOWN"
    assert o["unit_price_calculated"] is None
    assert o["requires_human_review"] is True


def test_zero_total_row_is_parsed_but_not_an_observation():
    row = one_row(page(line("2110  Loodslabben"),
                       line("      Vervangen loodslabben", "", [("Hvh", "1,00"), ("Ehd", "m1"), ("Stj", "2070"),
                                                                ("Cy", "48"), ("Totaal", "0")])))
    total, amounts, status = src.reconcile_row_amounts(row)
    assert total == 0 and amounts == {} and status == "zero"


def test_continuation_line_is_appended_across_blank_line():
    text = page(line("2121  Gevelelementen prefab beton"),
                line("      Herstellen ondergrond gelijktijdig", "", [("Hvh", "278,00"), ("Ehd", "m2"), ("Stj", "2028"),
                                                                     ("2028", "952"), ("Totaal", "952")]),
                line("      met schilderwerk achterzijde"))
    row = one_row(text)
    assert row["action_text"] == "Herstellen ondergrond gelijktijdig met schilderwerk achterzijde"


def test_euro_sign_tokens_do_not_break_amounts():
    raw = line("      Reinigen metselwerk", "", [("Hvh", "815,95"), ("Ehd", "m2"), ("Stj", "2026"), ("Cy", "2"),
                                                  ("2026", "8.955"), ("2028", "8.955"), ("Totaal", "17.910")])
    raw = raw.replace("  8.955", "€ 8.955")
    text = page(line("2110  Gevelconstructie metselwerk"), raw)
    o = obs_for(one_row(text))
    assert o["annual_amounts"] == {"2026": "8955", "2028": "8955"}


def test_zzzz_staartkosten_element_line_is_recognised():
    """Regressie: 'ZZZZ Directievoering (4%)' is een elementregel; de rij mag
    niet het vorige element (bijv. '9052 Vloerputten') erven."""
    text = page(line("9052  Vloerputten"),
                line("ZZ    Staartkosten"),
                line("ZZZZ  Directievoering (4%)"),
                line("      Directievoering 2026", "", [("Hvh", "0,04"), ("Ehd", "pst"), ("Stj", "2026"),
                                                       ("2026", "6.641"), ("Totaal", "6.641")]))
    o = obs_for(one_row(text))
    assert o["element"]["element_code_original"] == "ZZZZ"
    assert o["element"]["element_description_original"] == "Directievoering (4%)"


def test_numeric_token_in_unit_column_stays_unit_and_not_cycle():
    """Regressie: in DOC-009/010 staat in de Ehd-kolom letterlijk '20'. Dat is
    de (onbekende) eenheid; Cy moet de letterlijke 18 blijven."""
    text = page(line("6411  Deurbelinstallatie"),
                line("      Vervangen deurbelinstallatie", "", [("Hvh", "30,00"), ("Ehd", "20"), ("Stj", "2027"),
                                                               ("Cy", "18"), ("2027", "17.243"), ("Totaal", "17.243")]))
    o = obs_for(one_row(text))
    assert o["unit_original"] == "20"
    assert o["unit_normalized"] is None
    assert o["cycle_length_years"] == 18
    assert o["cycle_start_year"] == 2027


# --------------------------------------------------------------------------
# Vervolgregels van elementomschrijvingen (source-layer fix 1)
# --------------------------------------------------------------------------

def _row_line(action="      Groot schilderwerk", qty="10,00", unit="m2"):
    return line(action, "", [("Hvh", qty), ("Ehd", unit), ("Stj", "2026"), ("Cy", "6"),
                             ("2026", "100"), ("Totaal", "100")])


@pytest.mark.parametrize("first,continuation,expected", [
    ("4621  Buitenschilderwerk gevelbekleding", "      hout dekkend", "Buitenschilderwerk gevelbekleding hout dekkend"),
    ("4631  Buitenschilderwerk kozijn en", "      draaiende delen hout dekkend",
     "Buitenschilderwerk kozijn en draaiende delen hout dekkend"),
    ("4632  Binnenschilderwerk kozijn,ramen en", "      deuren hout dekkend",
     "Binnenschilderwerk kozijn,ramen en deuren hout dekkend"),
    ("4624  Binnenschilderwerk trap hout", "      dekkend", "Binnenschilderwerk trap hout dekkend"),
    ("4624  Binnenschilderwerk trap hout", "      transparant", "Binnenschilderwerk trap hout transparant"),
    ("6311  Elektra armaturen binnen TL naar", "      led", "Elektra armaturen binnen TL naar led"),
    ("5211  Doorvoer staal (onderuitlopen platte", "      daken)", "Doorvoer staal (onderuitlopen platte daken)"),
])
def test_wrapped_element_description_is_joined(first, continuation, expected):
    row = one_row(page(line(first), line(continuation), _row_line()))
    el = row["element"]
    assert el["description"] == expected
    assert el["description_first_line"] == first.split(None, 1)[1].strip()  # eerste regel blijft bewaard
    assert len(el["continuation_lines"]) == 1
    assert row["action_text"] == "Groot schilderwerk"  # actietekst ongewijzigd


def test_unit_token_at_end_of_continuation_is_kept_not_excluded():
    """DOC-007 p17 r39: 'Buitenschilderwerk kozijn&raam hout' + 'dekkend m2' moet dezelfde
    letterlijke naam opleveren als het Elementenoverzicht ('...dekkend m2', p8 r23) - anders
    koppelt de jarenplanregel niet aan zijn element (element-linking key wijkt af)."""
    row = one_row(page(line("4631  Buitenschilderwerk kozijn&raam hout"), line("      dekkend m2"), _row_line()))
    el = row["element"]
    assert el["description"] == "Buitenschilderwerk kozijn&raam hout dekkend m2"
    assert el["excluded_tokens"] == []


def test_non_unit_last_word_is_kept():
    row = one_row(page(line("4631  Buitenschilderwerk kozijn hout"), line("      dekkend achtergevel"), _row_line()))
    assert row["element"]["description"] == "Buitenschilderwerk kozijn hout dekkend achtergevel"
    assert row["element"]["excluded_tokens"] == []


def test_element_continuation_unit_word_does_not_leak_into_row_unit_or_action_text():
    """De fix raakt alleen de ELEMENTOMSCHRIJVING; de eenheid van de daaropvolgende rij zelf
    (Ehd-kolom) blijft gewoon apart herkend en action_text bevat het woord 'm2' niet."""
    row = one_row(page(line("4631  Buitenschilderwerk kozijn&raam hout"), line("      dekkend m2"),
                       _row_line("      Groot schilderwerk kozijn & raam", qty="391,30", unit="m2")))
    assert row["element"]["description"] == "Buitenschilderwerk kozijn&raam hout dekkend m2"
    assert row["unit_original"] == "m2"
    assert row["action_text"] == "Groot schilderwerk kozijn & raam"
    assert "m2" not in row["action_text"]


def test_text_after_action_row_is_action_continuation_not_element():
    row = one_row(page(line("4631  Buitenschilderwerk kozijn hout"), _row_line("      Groot schilderwerk kozijn"),
                       line("      hout dekkend achterzijde")))
    assert row["element"]["description"] == "Buitenschilderwerk kozijn hout"
    assert row["action_text"] == "Groot schilderwerk kozijn hout dekkend achterzijde"


def test_group_line_is_not_an_element_continuation():
    rows, _, _ = src.parse_jarenplan_page(page(line("4621  Buitenschilderwerk deur hout"), line("46    Schilderwerk"),
                                               _row_line()), 11)
    # na de groepregel geen element meer open: rij krijgt het element (zelfde pagina) maar zonder vervolgtekst
    assert rows[0]["element"]["description"] == "Buitenschilderwerk deur hout"


# --------------------------------------------------------------------------
# Elementcontext over een paginagrens (source-layer fix 2)
# --------------------------------------------------------------------------

def _carry(open_=True):
    return {"code": "4621", "description": "Buitenschilderwerk gevelbekleding hout", "description_first_line":
            "Buitenschilderwerk gevelbekleding", "location": "", "page": 14, "line": 89, "continuation_lines": [91],
            "excluded_tokens": [], "open_at_page_end": open_}


def test_previous_page_element_assigned_when_open_and_no_boundary():
    row = one_row(page(_row_line("      Aanbrengen vervolgsysteem")), page_no=15, carry=_carry())
    assert row["element"]["code"] == "4621" and row["element_context_source"] == "previous_page"
    assert row["element"]["page"] == 14 and row["element"]["line"] == 89   # herleidbaar naar de bronregel
    assert "open_at_page_end" not in row["element"]
    o = obs_for(row)
    assert o["element"]["element_context_source"] == "previous_page" and o["provenance_status"] == "complete"


def test_previous_page_element_not_assigned_after_group_boundary():
    row = one_row(page(line("46    Schilderwerk"), _row_line()), page_no=15, carry=_carry())
    assert row["element"] is None and row["element_candidate_previous_page"]["code"] == "4621"


def test_previous_page_element_not_assigned_when_closed_by_subtotal():
    row = one_row(page(_row_line()), page_no=15, carry=_carry(open_=False))
    assert row["element"] is None


def test_page_ending_with_subtotal_closes_the_element():
    subtotal = line("", "", [("2026", "100"), ("Totaal", "100")])
    _, carry, _ = src.parse_jarenplan_page(page(line("4621  Buitenschilderwerk deur hout"), _row_line(), subtotal), 14)
    assert carry["open_at_page_end"] is False


@pytest.mark.skipif(not PDFTOTEXT, reason="pdftotext (xpdf 4.06) niet beschikbaar")
def test_known_wrap_and_page_break_cases_on_batch1_sources():
    result = bpo.build(PROJECT_ROOT, PDFTOTEXT, document_ids={"DOC-002", "DOC-006", "DOC-007", "DOC-009", "DOC-010"})
    obs = {o["observation_id"]: o for o in result["observations"]}
    expected_prev = {"PO-DOC-002-P015-L007": "3122", "PO-DOC-006-P015-L007": "4621", "PO-DOC-006-P015-L009": "4621",
                     "PO-DOC-009-P019-L007": "3120", "PO-DOC-009-P021-L007": "4634"}
    for oid, code in expected_prev.items():
        el = obs[oid]["element"]
        assert el["element_context_source"] == "previous_page" and el["element_code_original"] == code, oid
    assert sum(1 for o in obs.values() if o["element"]["element_context_source"] == "previous_page") == 5
    desc = lambda oid: obs[oid]["element"]["element_description_original"]
    assert desc("PO-DOC-002-P018-L109") == "Buitenschilderwerk kozijn en draaiende delen hout dekkend"
    assert desc("PO-DOC-007-P017-L055") == "Binnenschilderwerk kozijn,ramen en deuren hout dekkend"
    assert desc("PO-DOC-002-P018-L093") == "Binnenschilderwerk trap hout dekkend"
    assert desc("PO-DOC-007-P017-L025") == "Binnenschilderwerk trap hout transparant"
    assert desc("PO-DOC-010-P013-L035") == "Elektra armaturen binnen TL naar led"
    assert desc("PO-DOC-007-P018-L059") == "Doorvoer staal (onderuitlopen platte daken)"
    assert desc("PO-DOC-007-P017-L043") == "Buitenschilderwerk kozijn&raam hout dekkend m2"
    assert obs["PO-DOC-007-P017-L043"]["element"]["element_description_excluded_tokens"] == []


def test_element_on_previous_page_is_candidate_not_assigned():
    carry = {"code": "4621", "description": "Buitenschilderwerk gevelbekleding hout", "location": "", "page": 14, "line": 99}
    text = page(line("      Aanbrengen vervolgsysteem", "Krijten", [("Hvh", "1,00"), ("Ehd", "pst"), ("Stj", "2026"),
                                                                    ("2026", "15.901"), ("Totaal", "15.901")]))
    o = obs_for(one_row(text, page_no=15, carry=carry))
    assert o["element"]["element_code_original"] is None
    assert o["element"]["element_candidate_previous_page"]["code"] == "4621"
    assert o["provenance_status"] == "incomplete"


# --------------------------------------------------------------------------
# Prijspeil / BTW
# --------------------------------------------------------------------------

def test_price_level_not_derived_from_inspection_date():
    pages = ["Algemene Objectgegevens\nInspectiedatum 16-4-2025\n"
             "BTW De bedragen in de begrotingen zijn inclusief BTW\n"
             "Printdatum: 2-5-2025\n"]
    ctx = src.parse_document_context(pages)
    assert ctx["price_level_date"] is None
    assert ctx["price_level_basis"] == "absent"
    assert ctx["vat_basis"] == "inclusive"


def test_explicit_price_level_and_exclusive_vat_are_read_literally():
    pages = ["Algemene Objectgegevens\nPrijspeil               17-3-2018\n"
             "BTW                     De bedragen in de begrotingen zijn exclusief BTW\n"]
    ctx = src.parse_document_context(pages)
    assert ctx["price_level_date"] == "17-3-2018"
    assert ctx["price_level_basis"] == "explicit"
    assert ctx["vat_basis"] == "exclusive"


# --------------------------------------------------------------------------
# Jaarplan / Bevindingen: bronweergave, geen extra observation
# --------------------------------------------------------------------------

def _obs_2025():
    text = page(line("4320  Parkeerdek vloer"),
                line("      Herstellen", "Lekkage", [("Hvh", "1,00"), ("Ehd", "pst"), ("Stj", "2027"),
                                                     ("2027", "10.285"), ("Totaal", "10.285")]))
    return obs_for(one_row(text))


def test_matching_jaarplan_row_becomes_representation_not_observation():
    o = _obs_2025()
    jp = [{"page": 15, "line": 7, "year": "2027", "element_code": "4320", "element_text": "Parkeerdek vloer",
           "action_text": "Herstellen", "quantity_as_stated": "1,00", "unit_original": "pst",
           "amount_as_stated": "10.285", "raw_line": "4320 Parkeerdek vloer Herstellen 1,00 pst 10.285"}]
    linked, unlinked = bpo.link_section_rows([o], jp, "JAARPLAN")
    assert len(linked) == 1 and not unlinked
    assert [r["section"] for r in o["source_representations"]] == ["JARENPLAN_GEDETAILLEERD", "JAARPLAN"]


def test_bevinding_without_matching_row_stays_unknown_and_unlinked():
    """Zoals DOC-007: bedrag alleen in Bevindingen, activiteitsjaar voor het venster."""
    o = _obs_2025()
    bev = [{"page": 13, "line": 21, "year": "2020", "element": {"code": "2320", "description": "Vloerconstructie"},
            "tag_location": "Bergingsgang", "defect": None, "inspection_scores_raw": None, "action_text": "Coaten",
            "quantity_as_stated": "1,00", "unit_original": "pst", "amount_as_stated": "11.810", "raw_line": "Coaten 1,00 pst 11.810"}]
    linked, unlinked = bpo.link_section_rows([o], bev, "BEVINDINGEN")
    assert not linked
    assert len(unlinked) == 1 and unlinked[0]["status"] == "UNKNOWN"
    assert len(o["source_representations"]) == 1


# --------------------------------------------------------------------------
# Afhankelijkheden en duplicate source
# --------------------------------------------------------------------------

def test_identical_rows_are_unknown_and_other_rows_no_dependency_found():
    a = _obs_2025()
    b = copy.deepcopy(a)
    b["observation_id"] = "PO-DOC-900-P011-L099"
    c = copy.deepcopy(a)
    c["observation_id"] = "PO-DOC-900-P011-L101"
    c["quantity_value"] = "2.00"
    rels = bpo.build_relations({"DOC-900": [a, b, c]}, [])
    assert len(rels) == 1 and rels[0]["dependency_status"] == "UNKNOWN"
    assert a["dependency_status"] == b["dependency_status"] == "UNKNOWN"
    assert c["dependency_status"] == "NO_DEPENDENCY_FOUND"  # niet 'INDEPENDENT'


def test_duplicate_source_document_yields_no_observations():
    result = bpo.build(PROJECT_ROOT, pdftotext_bin=None, document_ids={"DOC-003"})
    assert result["observations"] == []
    doc = result["documents"][0]
    assert doc["status"] == "duplicate_source_no_observations"
    assert doc["duplicate_of"] == "DOC-002"


def test_observation_validates_against_schema():
    schema = json.load(open(os.path.join(PROJECT_ROOT, "schemas", "price_observation.schema.json"), encoding="utf-8"))
    jsonschema.validate(_obs_2025(), schema)


# --------------------------------------------------------------------------
# Integratie op de echte bronbestanden
# --------------------------------------------------------------------------

@pytest.mark.skipif(not PDFTOTEXT, reason="pdftotext (xpdf 4.06) niet beschikbaar")
def test_full_build_on_batch1_sources():
    result = bpo.build(PROJECT_ROOT, PDFTOTEXT)
    per_doc = result["checks"]["per_document"]
    expected = {"DOC-001": 31, "DOC-002": 75, "DOC-003": 0, "DOC-004": 58, "DOC-005": 20, "DOC-006": 20,
                "DOC-007": 56, "DOC-008": 22, "DOC-009": 85, "DOC-010": 37}
    assert {d: c["observations"] for d, c in per_doc.items()} == expected
    totals = result["checks"]["totals"]
    assert totals["total_scope"] == {"ONE_EXECUTION": 308, "MULTIPLE_EXECUTIONS": 96}
    assert totals["cycle_length_blank_in_source"] == 105
    assert totals["price_level_basis"] == {"explicit": 351, "absent": 53}
    # som van de observation-totalen sluit op het eigen 'Totaal object' (afronding)
    for d, c in per_doc.items():
        if c.get("totaal_object_difference") is not None:
            assert abs(float(c["totaal_object_difference"])) <= 5, d
    # DOC-007: de twee Bevindingen-bedragen voor het venster worden geen observation
    unlinked_bev = [u for u in result["unlinked_section_rows"] if u["section"] == "BEVINDINGEN"]
    assert {(u["document_id"], u["amount_as_stated"]) for u in unlinked_bev} == {("DOC-007", "1.860"), ("DOC-007", "11.810")}
    errors = bpo.validate_observations(result, os.path.join(PROJECT_ROOT, "schemas", "price_observation.schema.json"))
    assert errors == []


# --------------------------------------------------------------------------
# 'Totaal object' - witruimte-tolerant (DOC-004: "Totaal  object")
# --------------------------------------------------------------------------

@pytest.mark.parametrize("label", ["Totaal object", "Totaal  object", "Totaal   object"])
def test_totaal_object_is_recognised_with_any_whitespace(label):
    text = page(
        line("2110  Gevelconstructie metselwerk", "Alle gevels"),
        _row_line(),
        line(label, "", [("2026", "100"), ("Totaal", "17.080")]),
    )
    rows, _, totaal = src.parse_jarenplan_page(text, 11)
    assert totaal == src.to_decimal("17.080")
    assert len(rows) == 1   # de totaalregel is geen rij


@pytest.mark.parametrize("label", ["Totaal object", "Totaal  object"])
def test_totaal_object_line_is_skipped_in_jaarplan(label):
    text = ("Code  Element/Locatie                  Handeling - Gebrek          Hvh    Ehd    2025\n\n"
            f"{label}                                                                  10.285\n")
    assert src.parse_jaarplan_page(text, 15) == []


def test_totaal_without_object_is_not_a_totaal_object():
    text = page(line("2110  Gevelconstructie metselwerk", "Alle gevels"), _row_line(),
                line("Totaal Buitenwanden", "", [("Totaal", "100")]))
    _, _, totaal = src.parse_jarenplan_page(text, 11)
    assert totaal is None
