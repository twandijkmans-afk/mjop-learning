#!/usr/bin/env python3
"""
nl_values.py - deterministische conversie van letterlijke brontekst naar
canonieke waarden (Nederlandse notatie).

Regels (zie CLAUDE.md):
  - Alleen omzetten wat eenduidig is. Twijfel -> (None, reden), nooit gokken.
  - Geen floats: bedragen en hoeveelheden worden Decimal / canonieke string
    ("1250.00" -> "1250.00", "5,93" -> "5.93").
  - Elke functie geeft (waarde, reden) terug. reden is None bij succes, anders
    een korte code die in de review-export verschijnt.

Getalnotatie:
  - Komma = decimaalteken, punt = duizendtalscheiding (NL).
  - "1.250" (punt + exact 3 cijfers, geen komma) is dubbelzinnig (1250 of
    1,25). In de generieke modus -> None + "ambiguous_thousands_or_decimal".
    Alleen met allow_dot_thousands=True (expliciete profielregel, bijv. voor
    bedragen in hele euro's) wordt dit als duizendtal gelezen.
"""
import datetime
import re
from decimal import Decimal, InvalidOperation

_INT_RE = re.compile(r"^\d+$")
_NL_GROUPED_INT_RE = re.compile(r"^\d{1,3}(\.\d{3})+$")          # 1.250 / 11.024
_NL_DECIMAL_RE = re.compile(r"^(\d{1,3}(\.\d{3})+|\d+),(\d+)$")   # 5,93 / 1.234,50
_YEAR_RE = re.compile(r"^(1[89]\d{2}|20\d{2}|21\d{2})$")
_DATE_NL_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")
_QTY_UNIT_RE = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+),(\d{2})(.*)$")
_UNIT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9²³]*$")
_EURO_RE = re.compile(r"^€\s*(.+)$")

# Voorbehouden die een waarde onzeker maken - dan nooit een waarde invullen.
QUALIFIER_RE = re.compile(r"(?i)\b(ca\.?|circa|ongeveer|p\.?m\.?|n\.?t\.?b\.?|nader te bepalen)(?=\s|$)|±|~")


def canonical_decimal(d):
    """Decimal -> string zonder exponent en zonder floats."""
    if d is None:
        return None
    s = format(d, "f")
    return s


def has_qualifier(text):
    return bool(text) and bool(QUALIFIER_RE.search(text))


def parse_decimal_nl(text, allow_dot_thousands=False):
    """Letterlijke NL-getalnotatie -> (Decimal, None) of (None, reden)."""
    if text is None:
        return None, "empty"
    t = text.strip().replace(" ", " ")
    if t == "":
        return None, "empty"
    if has_qualifier(t):
        return None, "qualifier_present"
    m = _EURO_RE.match(t)
    if m:
        t = m.group(1).strip()
    if _INT_RE.match(t):
        return Decimal(t), None
    if _NL_GROUPED_INT_RE.match(t):
        if allow_dot_thousands:
            return Decimal(t.replace(".", "")), None
        return None, "ambiguous_thousands_or_decimal"
    m = _NL_DECIMAL_RE.match(t)
    if m:
        whole = m.group(1).replace(".", "")
        try:
            return Decimal(f"{whole}.{m.group(3)}"), None
        except InvalidOperation:
            return None, "not_a_number"
    return None, "not_a_number"


def parse_currency_nl(text, allow_dot_thousands=False):
    """'€ 1.351' -> ('1351', None). Canonieke string, nooit float."""
    d, reason = parse_decimal_nl(text, allow_dot_thousands=allow_dot_thousands)
    return canonical_decimal(d), reason


# ---------------------------------------------------------------- expliciete profielregels
#
# Generiek blijft "1.250" dubbelzinnig (None + reden). Alleen een expliciet
# benoemde profielregel mag zo'n bedrag als duizendtal lezen, en alleen als de
# bedragen van dat document aantoonbaar hele euro's zijn (bewijs via
# whole_euro_evidence). De regel-ID komt terug zodat hij in
# provenance.extraction_rule zichtbaar wordt.

PROFILE_RULES = {
    "pdf_whole_euro_dot_thousands": (
        "Bedragen in hele euro's met punt als duizendtalscheiding ('€ 1.351' = 1351). "
        "Alleen toepassen op bedragtokens van een document waarvan alle bedragtokens "
        "dit patroon volgen (geen enkel bedrag met decimalen)."
    ),
}

_WHOLE_EURO_TOKEN_RE = re.compile(r"^\d{1,3}(\.\d{3})*$")
_AMOUNT_WITH_DECIMALS_RE = re.compile(r"^\d{1,3}(\.\d{3})*,\d+$|^\d+,\d+$")


def whole_euro_evidence(amount_tokens):
    """Deterministisch bewijs voor de profielregel: telt bedragtokens (zonder '€')
    in hele euro's versus met decimalen. consistent=True alleen als er minstens
    één token met punt-groepering is en géén enkel token decimalen heeft."""
    tokens = [t.strip().lstrip("€").strip() for t in amount_tokens if t and t.strip()]
    whole = [t for t in tokens if _WHOLE_EURO_TOKEN_RE.match(t)]
    grouped = [t for t in whole if "." in t]
    decimals = [t for t in tokens if _AMOUNT_WITH_DECIMALS_RE.match(t)]
    other = [t for t in tokens if t not in whole and t not in decimals]
    return {
        "tokens": len(tokens), "whole_euro": len(whole), "dot_grouped": len(grouped),
        "with_decimals": len(decimals), "other": len(other),
        "consistent": bool(grouped) and not decimals and not other,
    }


def parse_currency_profile(text, rule_id, evidence):
    """Bedrag lezen onder een expliciete profielregel.
    Returns (canonieke_string | None, reden | None, extraction_rule).
    extraction_rule is 'nl_values.generic' als de generieke parser volstond en
    'nl_values.profile:<rule_id>' als de profielregel de doorslag gaf."""
    if rule_id not in PROFILE_RULES:
        raise ValueError(f"onbekende profielregel {rule_id!r}")
    val, reason = parse_currency_nl(text)
    if reason is None:
        return val, None, "nl_values.generic"
    if reason != "ambiguous_thousands_or_decimal":
        return None, reason, "nl_values.generic"
    if not (evidence and evidence.get("consistent")):
        return None, "profile_rule_not_supported_by_document_evidence", f"nl_values.profile:{rule_id}"
    val, reason = parse_currency_nl(text, allow_dot_thousands=True)
    return val, reason, f"nl_values.profile:{rule_id}"


def parse_quantity_nl(text):
    d, reason = parse_decimal_nl(text)
    return canonical_decimal(d), reason


def parse_year(text):
    if text is None:
        return None, "empty"
    t = text.strip()
    if has_qualifier(t):
        return None, "qualifier_present"
    if _YEAR_RE.match(t):
        return int(t), None
    return None, "not_a_year"


def parse_int(text):
    if text is None:
        return None, "empty"
    t = text.strip()
    if has_qualifier(t):
        return None, "qualifier_present"
    if _INT_RE.match(t):
        return int(t), None
    return None, "not_an_integer"


def parse_date_nl(text):
    """'1-4-2023' -> ('2023-04-01', None). Andere vormen -> None + reden."""
    if text is None:
        return None, "empty"
    t = text.strip()
    m = _DATE_NL_RE.match(t)
    if not m:
        return None, "not_a_dd-mm-yyyy_date"
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime.date(year, month, day).isoformat(), None
    except ValueError:
        return None, "invalid_date"


def split_quantity_unit(token):
    """'148,25m2' -> (('148.25', 'm2'), None).

    Profielregel (Overzicht 15-formaat): hoeveelheid heeft altijd exact twee
    decimalen, direct gevolgd door de eenheid. Past het restant niet op een
    eenheid (bijv. '4,0020'), dan is het token dubbelzinnig -> beide None.
    """
    if token is None:
        return (None, None), "empty"
    m = _QTY_UNIT_RE.match(token.strip())
    if not m:
        return (None, None), "not_quantity_unit"
    whole = m.group(1).replace(".", "")
    qty = canonical_decimal(Decimal(f"{whole}.{m.group(2)}"))
    unit = m.group(3)
    if unit == "":
        return (qty, None), "unit_missing"
    if not _UNIT_RE.match(unit):
        return (None, None), "ambiguous_quantity_unit"
    return (qty, unit), None


def parse_human_value(text, value_type):
    """Conversie van een door een reviewer ingevulde waarde (EDIT/ADD).
    Accepteert NL-komma of canonieke punt-decimaal, maar niet dubbelzinnig."""
    if text is None:
        return None, None
    t = str(text).strip()
    if t == "" or t.lower() in ("<null>", "null"):
        return None, None
    if value_type == "text":
        return t, None
    if value_type == "year":
        return parse_year(t)
    if value_type == "integer":
        return parse_int(t)
    if value_type == "date":
        if re.match(r"^\d{4}-\d{2}-\d{2}$", t):
            try:
                return datetime.date.fromisoformat(t).isoformat(), None
            except ValueError:
                return None, "invalid_date"
        return parse_date_nl(t)
    if value_type == "decimal":
        if re.match(r"^\d+(\.\d+)?$", t) and not _NL_GROUPED_INT_RE.match(t):
            return canonical_decimal(Decimal(t)), None
        if re.match(r"^\d+\.\d+$", t):
            return None, "ambiguous_thousands_or_decimal"
        d, reason = parse_decimal_nl(t)
        return canonical_decimal(d), reason
    raise ValueError(f"onbekend value_type {value_type}")
