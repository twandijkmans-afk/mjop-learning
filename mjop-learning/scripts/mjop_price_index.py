#!/usr/bin/env python3
"""
mjop_price_index.py  (EXPLICIETE PRIJSINDEXATIE VAN HISTORISCHE MJOP-BEDRAGEN, v1)

Config: config/price_index.json (door een mens ingevoerde reeks; nooit automatisch opgehaald of
aangevuld). Documentatie: docs/mjop_actualisatie_light_v1.md.

  factor = round(index[doel] / index[basis], 6)   (ROUND_HALF_EVEN, expliciet opgeslagen)
  indexed_total = source_total x factor           (exact Decimal)

Ontbreekt een prijspeil of een indexjaar, dan wordt NIETS berekend (not_computed_reason).
Het resultaat is een historisch bedrag op een nieuw prijspeil — geen actuele marktprijs.
"""
import json
import os
from decimal import ROUND_HALF_EVEN, Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INDEX = os.path.join(ROOT, "config", "price_index.json")
FACTOR_PRECISION = Decimal("0.000001")


class IndexError_(ValueError):
    pass


def load_index(path=DEFAULT_INDEX):
    data = json.load(open(path, encoding="utf-8"))
    validate_index(data)
    return data


def validate_index(data):
    if data.get("index_version") != "price_index_v1":
        raise IndexError_("onbekende index_version")
    for year, value in data["series"].items():
        if not (year.isdigit() and len(year) == 4):
            raise IndexError_(f"ongeldig jaar {year!r}")
        if not isinstance(value, str) or Decimal(value) <= 0:
            raise IndexError_(f"indexwaarde voor {year} moet een positieve Decimal-string zijn")
    if data["series"] and not data.get("index_source"):
        raise IndexError_("index_source is verplicht zodra er een reeks is ingevoerd")
    return data


def factor(index, base_year, target_year):
    """(factor, base_value, target_value) of None als een jaar ontbreekt."""
    s = index["series"]
    b, t = s.get(str(base_year)), s.get(str(target_year))
    if b is None or t is None:
        return None
    f = (Decimal(t) / Decimal(b)).quantize(FACTOR_PRECISION, rounding=ROUND_HALF_EVEN)
    return format(f, "f"), b, t


def price_update(*, source_document_id, source_action_id, source_total, source_vat_statement, base_year,
                 target_year, index, not_computed_reason=None):
    """Bouwt een price_update-blok (status PROPOSED) voor mjop_maintenance_line_v2."""
    pu = {"basis": "HISTORICAL_DOCUMENT_COST", "source_document_id": source_document_id,
          "source_action_id": source_action_id,
          "source_total_as_stated": None if source_total is None else format(Decimal(source_total), "f"),
          "source_vat_statement": source_vat_statement, "base_price_level_year": base_year,
          "target_price_level_year": target_year, "index_source": index.get("index_source"),
          "index_base_value": None, "index_target_value": None, "indexation_factor": None,
          "indexed_total": None, "indexed_total_display": None, "not_computed_reason": None,
          "status": "PROPOSED", "verification": None}
    reason = not_computed_reason
    if reason is None and source_total is None:
        reason = "SOURCE_AMOUNT_MISSING"
    if reason is None and base_year is None:
        reason = "PRICE_LEVEL_UNKNOWN"
    fx = None if reason else factor(index, base_year, target_year)
    if reason is None and fx is None:
        reason = "INDEX_MISSING"
    if reason:
        pu["not_computed_reason"] = reason
        return pu
    f, b, t = fx
    total = Decimal(pu["source_total_as_stated"]) * Decimal(f)
    pu.update({"index_base_value": b, "index_target_value": t, "indexation_factor": f,
               "indexed_total": format(total, "f"),
               "indexed_total_display": format(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), "f")})
    return pu
