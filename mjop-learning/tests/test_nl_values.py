"""
Getalconversie: NL-notatie -> canonieke strings, nooit floats, nooit gokken.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from decimal import Decimal

import pytest

import nl_values as nv


@pytest.mark.parametrize("text,expected", [
    ("€ 1.351", "1351"),
    ("€ 11.024", "11024"),
    ("€ 53.678", "53678"),
    ("€ 0", "0"),
    ("491", "491"),
    ("1.234,50", "1234.50"),
])
def test_currency_with_profile_thousands_rule(text, expected):
    val, reason = nv.parse_currency_nl(text, allow_dot_thousands=True)
    assert reason is None
    assert val == expected
    assert isinstance(val, str)


def test_dot_thousands_is_ambiguous_without_explicit_profile_rule():
    val, reason = nv.parse_currency_nl("1.250")
    assert val is None
    assert reason == "ambiguous_thousands_or_decimal"


@pytest.mark.parametrize("text,expected", [("5,93", "5.93"), ("148,25", "148.25"), ("12", "12"), ("0,06", "0.06")])
def test_quantity(text, expected):
    assert nv.parse_quantity_nl(text) == (expected, None)


@pytest.mark.parametrize("text", ["ca. 2027", "circa 1.250", "p.m.", "± 12", "n.t.b."])
def test_qualifier_never_yields_value(text):
    assert nv.parse_decimal_nl(text)[0] is None
    assert nv.parse_year(text)[0] is None


@pytest.mark.parametrize("token,expected", [
    ("148,25m2", ("148.25", "m2")),
    ("10,00m1", ("10.00", "m1")),
    ("1,00st", ("1.00", "st")),
    ("2,00pst", ("2.00", "pst")),
    ("2,00Ver", ("2.00", "Ver")),
    ("0,06pst", ("0.06", "pst")),
    ("1.234,56m2", ("1234.56", "m2")),
])
def test_split_quantity_unit(token, expected):
    assert nv.split_quantity_unit(token) == (expected, None)


def test_ambiguous_quantity_unit_is_not_guessed():
    # DOC-010 p13: '4,0020' - 4,00 + eenheid '20'? of 4,0020? -> niet raden
    (qty, unit), reason = nv.split_quantity_unit("4,0020")
    assert qty is None and unit is None
    assert reason == "ambiguous_quantity_unit"


def test_year_and_date():
    assert nv.parse_year("2028") == (2028, None)
    assert nv.parse_year("20288")[0] is None
    assert nv.parse_date_nl("1-4-2023") == ("2023-04-01", None)
    assert nv.parse_date_nl("31-2-2023")[0] is None
    assert nv.parse_date_nl("april 2023")[0] is None


def test_no_float_artifacts():
    # 0.1 + 0.2 als float = 0.30000000000000004; als Decimal-string exact
    a, _ = nv.parse_quantity_nl("0,1")
    b, _ = nv.parse_quantity_nl("0,2")
    assert Decimal(a) + Decimal(b) == Decimal("0.3")


@pytest.mark.parametrize("text,vtype,expected", [
    ("1250", "decimal", "1250"),
    ("1250,00", "decimal", "1250.00"),
    ("5.93", "decimal", "5.93"),
    ("1-4-2023", "date", "2023-04-01"),
    ("2023-04-01", "date", "2023-04-01"),
    ("2030", "year", 2030),
    ("<null>", "text", None),
])
def test_human_values(text, vtype, expected):
    assert nv.parse_human_value(text, vtype) == (expected, None)


def test_human_value_ambiguous_rejected():
    assert nv.parse_human_value("1.250", "decimal")[1] == "ambiguous_thousands_or_decimal"
