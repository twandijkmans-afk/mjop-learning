#!/usr/bin/env python3
"""
mjop_reserve_fund.py  (RESERVEFONDS-DOORREKENING OVER DE PLANHORIZON, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md.

Per jaar t van de horizon (exact Decimal; elk jaarbedrag afgerond op centen, ROUND_HALF_EVEN):
  uitgaven_t  = som over regels en voorkomens in jaar t van bedrag_per_keer x (1 + kosteninflatie)^(t - prijspeiljaar)
  storting_t  = C x (1 + stortingsgroei)^(t - start)
  rente_t     = saldo_{t-1} x rente
  saldo_t     = saldo_{t-1} + rente_t + storting_t - uitgaven_t

Bedrag per keer: zie mjop_maintenance_line_v2.cost_per_occurrence (definitief bedrag >
geaccepteerd geïndexeerd bedrag > alleen bij include_proposals een voorgesteld bedrag).
Planjaren: occurrence_years (menselijk vastgesteld; voorstellen alleen bij include_proposals).
Een doorrekening met voorstellen is een CONCEPT en wordt zo gemarkeerd.

Advies (deterministisch): de laagste storting C (in centen) waarbij het saldo in geen enkel jaar
onder min_balance komt — gelijkblijvend en, als een groei is opgegeven, jaarlijks geïndexeerd.
Saldo is lineair in C: eerst analytisch berekend, daarna door simulatie bevestigd.
Alle parameters zijn invoer van de gebruiker; er worden geen standaardpercentages verzonnen.
"""
import os
import sys
from collections import Counter, defaultdict
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_maintenance_line_v2 as line_v2  # noqa: E402

CENT = Decimal("0.01")
MODEL_VERSION = "mjop_reserve_fund_v1"


class FundError(ValueError):
    pass


def _d(x, name):
    if x is None:
        raise FundError(f"{name} is verplicht")
    try:
        return Decimal(str(x))
    except Exception as e:  # noqa: BLE001
        raise FundError(f"{name}: geen getal ({x!r})") from e


def _c(x):
    return x.quantize(CENT, rounding=ROUND_HALF_EVEN)


def _s(x):
    return format(_c(x), "f")


def yearly_expenses(lines, start, end, *, price_level_year, cost_inflation, include_proposals):
    """({jaar: Decimal}, details). Uitgaven op prijspeil price_level_year, verhoogd met kosteninflatie."""
    raw = defaultdict(Decimal)
    basis_count, vat = Counter(), Counter()
    without_amount, without_schedule, per_line, no_cycle = [], [], [], []
    for l in lines:
        years = line_v2.occurrence_years(l, start, end, include_proposals=include_proposals)
        if not years:
            without_schedule.append(l["maintenance_line_id"])
            continue
        amount, basis = line_v2.cost_per_occurrence(l, include_proposals=include_proposals)
        if amount is None:
            without_amount.append(l["maintenance_line_id"])
            continue
        basis_count[basis] += 1
        sched = line_v2.schedule(l)
        if sched and sched[1] is None:
            no_cycle.append(l["maintenance_line_id"])
        vat[l["vat_basis"] or "unknown"] += 1
        for y in years:
            raw[y] += amount * (1 + cost_inflation) ** (y - price_level_year)
        per_line.append({"maintenance_line_id": l["maintenance_line_id"], "years": years, "amount_per_occurrence": _s(amount),
                         "cost_basis": basis})
    expenses = {y: _c(raw.get(y, Decimal(0))) for y in range(start, end + 1)}
    return expenses, {"lines_in_cashflow": len(per_line), "cost_basis_counts": dict(sorted(basis_count.items())),
                      "vat_basis_counts": dict(sorted(vat.items())), "lines_without_amount": without_amount,
                      "lines_without_schedule_in_horizon": without_schedule,
                      "lines_without_cycle": no_cycle, "per_line": per_line}


def simulate(expenses, start, end, *, opening_balance, contribution, contribution_growth, interest_rate):
    rows, saldo = [], opening_balance
    for t in range(start, end + 1):
        storting = _c(contribution * (1 + contribution_growth) ** (t - start))
        rente = _c(saldo * interest_rate)
        saldo = saldo + rente + storting - expenses[t]
        rows.append({"year": t, "opening": None, "contribution": storting, "interest": rente,
                     "expenses": expenses[t], "closing": saldo})
    prev = opening_balance
    for r in rows:
        r["opening"], prev = prev, r["closing"]
    return rows


def minimum_contribution(expenses, start, end, *, opening_balance, contribution_growth, interest_rate, min_balance):
    """Laagste C (centen, >= 0) waarbij saldo_t >= min_balance voor alle t."""
    a, b, need = opening_balance, Decimal(0), Decimal(0)
    for t in range(start, end + 1):
        a = a * (1 + interest_rate) - expenses[t]
        b = b * (1 + interest_rate) + (1 + contribution_growth) ** (t - start)
        need = max(need, (min_balance - a) / b)
    c = need.quantize(CENT, rounding=ROUND_CEILING)
    for _ in range(10000):   # afronding per jaar kan een paar cent schelen: bevestig door simulatie
        rows = simulate(expenses, start, end, opening_balance=opening_balance, contribution=c,
                        contribution_growth=contribution_growth, interest_rate=interest_rate)
        if all(r["closing"] >= min_balance for r in rows):
            return c
        c += CENT
    raise FundError("minimale storting niet gevonden")


def run(lines, *, start, end, price_level_year, opening_balance, annual_contribution, contribution_growth="0",
        interest_rate="0", cost_inflation="0", min_balance="0", include_proposals=True, rebuild_value=None):
    ob, ac = _d(opening_balance, "opening_balance"), _d(annual_contribution, "annual_contribution")
    g, r, i, mb = (_d(contribution_growth, "contribution_growth"), _d(interest_rate, "interest_rate"),
                   _d(cost_inflation, "cost_inflation"), _d(min_balance, "min_balance"))
    if price_level_year is None:
        raise FundError("price_level_year is verplicht")
    expenses, details = yearly_expenses(lines, start, end, price_level_year=price_level_year, cost_inflation=i,
                                        include_proposals=include_proposals)
    rows = simulate(expenses, start, end, opening_balance=ob, contribution=ac, contribution_growth=g, interest_rate=r)
    shortfall = [row["year"] for row in rows if row["closing"] < mb]
    lowest = min(rows, key=lambda row: (row["closing"], row["year"]))
    advice = {"level_contribution": _s(minimum_contribution(expenses, start, end, opening_balance=ob, contribution_growth=Decimal(0),
                                                          interest_rate=r, min_balance=mb))}
    if g != 0:
        advice["indexed_contribution_first_year"] = _s(minimum_contribution(
            expenses, start, end, opening_balance=ob, contribution_growth=g, interest_rate=r, min_balance=mb))
        advice["indexed_growth_rate"] = format(g, "f")
    if rebuild_value is not None:
        advice["comparison_half_percent_rebuild_value"] = _s(_d(rebuild_value, "rebuild_value") * Decimal("0.005"))
    warnings = []
    if include_proposals and details["cost_basis_counts"].get("PROPOSED_INDEXED_HISTORICAL"):
        warnings.append("CONCEPT: bevat geïndexeerde historische bedragen die nog niet door een mens zijn geaccepteerd.")
    if include_proposals:
        warnings.append("CONCEPT: planjaren omvatten voorstellen van de horizon-planner.")
    if len([k for k in details["vat_basis_counts"] if k != "unknown"]) > 1:
        warnings.append("Regels inclusief en exclusief btw zijn samengeteld; controleer de btw-basis.")
    if details["lines_without_cycle"]:
        warnings.append(f"{len(details['lines_without_cycle'])} regels zonder cyclus komen maar één keer voor in de horizon: "
                        "de uitgaven in latere jaren zijn daardoor waarschijnlijk te laag. Leg cycli vast.")
    if details["lines_without_amount"]:
        warnings.append(f"{len(details['lines_without_amount'])} ingeplande regels zonder bedrag tellen niet mee.")
    return {
        "model_version": MODEL_VERSION,
        "parameters": {"start": start, "end": end, "price_level_year": price_level_year, "opening_balance": _s(ob),
                       "annual_contribution": _s(ac), "contribution_growth": format(g, "f"), "interest_rate": format(r, "f"),
                       "cost_inflation": format(i, "f"), "min_balance": _s(mb), "include_proposals": include_proposals,
                       "rebuild_value": None if rebuild_value is None else _s(_d(rebuild_value, "rebuild_value"))},
        "status": "CONCEPT" if include_proposals else "ACCEPTED_ONLY",
        "years": [{k: (v if k == "year" else _s(v)) for k, v in row.items()} for row in rows],
        "total_expenses": _s(sum(expenses.values(), Decimal(0))),
        "shortfall_years": shortfall,
        "lowest_balance": {"year": lowest["year"], "closing": _s(lowest["closing"])},
        "advice": advice,
        "details": details,
        "warnings": warnings,
    }
