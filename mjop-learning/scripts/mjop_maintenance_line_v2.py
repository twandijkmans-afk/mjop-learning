#!/usr/bin/env python3
"""
mjop_maintenance_line_v2.py  (DOMEINMODEL: ONDERHOUDSREGEL VAN EEN NIEUW MJOP, v2)

Schema: schemas/mjop_maintenance_line_v2.schema.json; documentatie: docs/mjop_actualisatie_light_v1.md.

v2 = v1 + drie blokken voor de 30-jaars actualisering. Alle v1-velden en -regels blijven
ongewijzigd gelden: een v2-regel wordt gevalideerd door (a) het v2-schema, (b) de volledige
v1-validatie op de v1-weergave van de regel (to_v1_view) en (c) de v2-invarianten hieronder.
Bedragbewerkingen (workflow, handmatig bedrag) lopen via de v1-functies; v1-regels blijven
geldig en worden niet gemigreerd tenzij expliciet (upgrade_v1).

Toegevoegd in v2:
  - herkomst: origin (FROM_EXISTING_MJOP / ADDED_FROM_LIFECYCLE / MANUAL) + origin_source;
  - planning: proposed_planned_year + planning_basis + planner_flags (gezet door de
    horizon-planner), planning_status en planning_verification (ACCEPT/EDIT/REJECT door een
    mens). planned_year/cycle_years worden pas na een menselijke beslissing gezet;
  - price_update: een expliciet geïndexeerd bedrag per keer, afgeleid van een historisch
    MJOP-bedrag (basis HISTORICAL_DOCUMENT_COST). Geen marktprijs; telt pas als
    HUMAN_ACCEPTED als definitief mee. financial.indexation blijft 'none'.

Alle functies zijn puur (geven een nieuwe regel terug) en valideren het resultaat.
"""
import copy
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_maintenance_line as v1  # noqa: E402

LINE_VERSION = "mjop_maintenance_line_v2"
V2_FIELDS = ("origin", "origin_source", "planning_basis", "planner_flags", "planning_status",
             "planning_verification", "price_update")
PLANNING_FLAGS = ("CYCLE_UNKNOWN", "CYCLE_FROM_DOCUMENT_IRREGULAR", "CYCLE_DOCUMENT_TABLE_DIFFER", "OVERDUE_NO_CYCLE",
                  "BASE_YEAR_UNKNOWN", "ASSUMED_FROM_CONSTRUCTION_YEAR", "BEYOND_HORIZON", "COUPLED",
                  "COUPLING_LEADER_ABSENT", "COUPLING_IRREGULAR_LEADER", "COUPLING_NO_LEADER_YEAR_IN_RANGE",
                  "COUPLING_REANCHORED_LEADER", "RESTARTED_BY_DEFECT")
HUMAN_PLANNED = ("HUMAN_ACCEPTED", "HUMAN_ADJUSTED")
LineError = v1.LineError

SCHEMA = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas",
                                     "mjop_maintenance_line_v2.schema.json"), encoding="utf-8"))


def origin_source(kind, *, document_id=None, pages=(), source_action_ids=(), source_element_id=None,
                  document_planned_years=(), lifecycle_key=None, note=None):
    return {"kind": kind, "document_id": document_id, "pages": sorted(set(pages)),
            "source_action_ids": list(source_action_ids), "source_element_id": source_element_id,
            "document_planned_years": sorted(set(document_planned_years)), "lifecycle_key": lifecycle_key, "note": note}


def to_v1_view(line):
    """De regel zoals v1 hem ziet: v2-velden weg, geen planner-voorstel."""
    view = {k: copy.deepcopy(v) for k, v in line.items() if k not in V2_FIELDS}
    view["line_version"], view["proposed_planned_year"] = v1.LINE_VERSION, None
    return view


def _merge(v1_line, v2_source):
    new = copy.deepcopy(v1_line)
    new["line_version"] = LINE_VERSION
    new["proposed_planned_year"] = v2_source["proposed_planned_year"]
    for k in V2_FIELDS:
        new[k] = copy.deepcopy(v2_source[k])
    return new


# --------------------------------------------------------------------------
# Validatie
# --------------------------------------------------------------------------

def line_errors(line):
    import jsonschema
    errors = [f"{'/'.join(str(x) for x in e.path) or '(regel)'}: {e.message}"
              for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(line)]
    if errors:
        return errors
    errors += v1.line_errors(to_v1_view(line))
    src, origin = line["origin_source"], line["origin"]
    if origin == "FROM_EXISTING_MJOP" and (src is None or src["kind"] != "DOCUMENT" or not src["document_id"]):
        errors.append("origin FROM_EXISTING_MJOP vereist origin_source van soort DOCUMENT met document_id")
    if origin == "ADDED_FROM_LIFECYCLE" and (src is None or src["kind"] != "LIFECYCLE_TABLE" or not src["lifecycle_key"]):
        errors.append("origin ADDED_FROM_LIFECYCLE vereist origin_source van soort LIFECYCLE_TABLE met lifecycle_key")
    if origin == "MANUAL" and src is not None and src["kind"] != "USER":
        errors.append("origin MANUAL past alleen bij origin_source USER of null")
    ps, pv = line["planning_status"], line["planning_verification"]
    if ps == "PROPOSED" and (line["proposed_planned_year"] is None or line["planning_basis"] is None):
        errors.append("planning_status PROPOSED zonder proposed_planned_year/planning_basis")
    if ps == "NOT_PLANNED" and (line["proposed_planned_year"] is not None or pv is not None):
        errors.append("planning_status NOT_PLANNED met een voorstel of beslissing")
    expected_decision = {"HUMAN_ACCEPTED": "ACCEPT", "HUMAN_ADJUSTED": "EDIT", "REJECTED": "REJECT"}.get(ps)
    if expected_decision and (pv is None or pv["decision"] != expected_decision):
        errors.append(f"planning_status {ps} zonder beslissing {expected_decision}")
    if expected_decision is None and pv is not None:
        errors.append(f"planning_verification aanwezig bij planning_status {ps}")
    if ps in HUMAN_PLANNED and (line["planned_year"] != pv["value_year"] or line["cycle_years"] != pv["value_cycle_years"]):
        errors.append("planned_year/cycle_years wijken af van de menselijke planningsbeslissing")
    pu = line["price_update"]
    if pu is not None:
        computed = pu["indexed_total"] is not None
        if computed != (pu["not_computed_reason"] is None):
            errors.append("price_update: indexed_total en not_computed_reason sluiten elkaar uit")
        if computed:
            if None in (pu["source_total_as_stated"], pu["indexation_factor"], pu["base_price_level_year"],
                        pu["target_price_level_year"]):
                errors.append("price_update: berekend bedrag zonder bronbedrag/factor/prijspeilen")
            elif Decimal(pu["source_total_as_stated"]) * Decimal(pu["indexation_factor"]) != Decimal(pu["indexed_total"]):
                errors.append("price_update: indexed_total != source_total_as_stated x indexation_factor")
            elif pu["indexed_total_display"] != v1.display(pu["indexed_total"]):
                errors.append("price_update: indexed_total_display past niet")
        exp = {"PROPOSED": None, "HUMAN_ACCEPTED": "ACCEPT", "REJECTED": "REJECT"}[pu["status"]]
        if (pu["verification"] or {}).get("decision") != exp:
            errors.append(f"price_update: status {pu['status']} past niet bij de beslissing")
        if pu["status"] == "HUMAN_ACCEPTED" and not computed:
            errors.append("price_update: accepteren zonder berekend bedrag")
    return errors


def validated(line):
    errors = line_errors(line)
    if errors:
        raise LineError("; ".join(errors))
    return line


def any_line_errors(line):
    """Dispatcher voor de planlaag: valideert v1- en v2-regels elk met hun eigen regels."""
    if line.get("line_version") == LINE_VERSION:
        return line_errors(line)
    return v1.line_errors(line)


# --------------------------------------------------------------------------
# Aanmaken en migreren
# --------------------------------------------------------------------------

def _v2_defaults(origin, src):
    return {"proposed_planned_year": None, "origin": origin, "origin_source": src, "planning_basis": None,
            "planner_flags": [], "planning_status": "NOT_PLANNED", "planning_verification": None, "price_update": None}


def new_line(maintenance_line_id, mjop_id, object_id, *, origin, origin_source=None, planner_flags=(), **fields):
    base = v1.new_line(maintenance_line_id, mjop_id, object_id, **fields)
    defaults = _v2_defaults(origin, origin_source)
    defaults["planner_flags"] = sorted(set(planner_flags))
    return validated(_merge(base, defaults))


def upgrade_v1(line, *, origin="MANUAL", origin_source=None):
    """Expliciete migratie v1 -> v2. Bedrag, status en provenance blijven ongewijzigd."""
    if line["line_version"] != v1.LINE_VERSION:
        raise LineError(f"geen v1-regel: {line['line_version']}")
    v1.validated(line)
    return validated(_merge(line, _v2_defaults(origin, origin_source)))


# --------------------------------------------------------------------------
# Bedrag: via v1 (geen dubbele logica)
# --------------------------------------------------------------------------

def _via_v1(fn, line, *args, **kwargs):
    result = fn(to_v1_view(line), *args, **kwargs)
    return validated(_merge(result, line))


def update_user_fields(line, **changes):
    """Zoals v1. Wijzigt een gebruiker planned_year/cycle_years e.d. rechtstreeks, dan vervalt het
    planner-voorstel en de planningsbeslissing (de ingevoerde waarden zijn dan zelf menselijk)."""
    v1_line = v1.update_user_fields(to_v1_view(line), **changes)
    new = _merge(v1_line, line)
    if any(new[k] != line[k] for k in v1.PLANNING_FIELDS):
        new["proposed_planned_year"], new["planning_basis"], new["planning_verification"] = None, None, None
        new["planning_status"] = "NOT_PLANNED"
        new["planner_flags"] = [f for f in new["planner_flags"] if f not in PLANNING_FLAGS]
    return validated(new)


def apply_workflow_result(line, workflow_result):
    return _via_v1(v1.apply_workflow_result, line, workflow_result)


def set_manual_amount(line, amount, unit, price_level, vat_basis, reason):
    return _via_v1(v1.set_manual_amount, line, amount, unit, price_level, vat_basis, reason)


def clear_manual_amount(line):
    return _via_v1(v1.clear_manual_amount, line)


def to_workflow_input(line):
    return v1.to_workflow_input(to_v1_view(line))


# --------------------------------------------------------------------------
# Planning (planner stelt voor, mens beslist)
# --------------------------------------------------------------------------

def set_planner_proposal(line, proposed_year, planning_basis, flags=()):
    """System-derived: voorstel van de horizon-planner. Een regel met een menselijke
    planningsbeslissing wordt niet overschreven."""
    if line["planning_status"] in HUMAN_PLANNED + ("REJECTED",):
        raise LineError("regel heeft al een menselijke planningsbeslissing; voorstel niet overschreven")
    new = copy.deepcopy(line)
    new["proposed_planned_year"] = proposed_year
    new["planning_basis"] = copy.deepcopy(planning_basis)
    keep = [f for f in new["planner_flags"] if f not in PLANNING_FLAGS]
    new["planner_flags"] = sorted(set(keep) | set(flags))
    new["planning_status"] = "PROPOSED" if proposed_year is not None else "NOT_PLANNED"
    return validated(new)


def decide_planning(line, decision, *, by, at, year=None, cycle_years=None, note=None):
    """ACCEPT: voorstel overnemen (jaar + gebruikte cyclus). EDIT: eigen jaar en/of cyclus.
    REJECT: regel niet inplannen. Legt oorspronkelijke voorstel, nieuwe waarde, gebruiker en tijd vast."""
    if not by:
        raise LineError("'by' is verplicht")
    proposed = line["proposed_planned_year"]
    proposed_cycle = (line["planning_basis"] or {}).get("cycle_years_used")
    new = copy.deepcopy(line)
    if decision == "ACCEPT":
        if line["planning_status"] != "PROPOSED":
            raise LineError("er is geen voorstel om te accepteren")
        year, cycle_years, status = proposed, proposed_cycle, "HUMAN_ACCEPTED"
    elif decision == "EDIT":
        year = proposed if year is None else year
        cycle_years = proposed_cycle if cycle_years is None else cycle_years
        if year is None:
            raise LineError("EDIT vereist een jaar (er is geen voorstel)")
        status = "HUMAN_ADJUSTED"
    elif decision == "REJECT":
        year, cycle_years, status = line["planned_year"], line["cycle_years"], "REJECTED"
    else:
        raise LineError(f"onbekende beslissing {decision!r}")
    if status in HUMAN_PLANNED:
        new["planned_year"], new["cycle_years"] = year, cycle_years
    new["planning_status"] = status
    planned = status in HUMAN_PLANNED
    new["planning_verification"] = {"decision": decision, "original_proposed_year": proposed,
                                    "original_cycle_years": proposed_cycle,
                                    "value_year": year if planned else None,
                                    "value_cycle_years": cycle_years if planned else None,
                                    "by": by, "at": at, "note": note}
    return validated(new)


def schedule(line):
    """(eerste jaar, cyclus of None, definitief?) of None als de regel niet ingepland is.
    Definitief = door een mens bepaald (beslissing of zelf ingevoerd planned_year)."""
    ps = line["planning_status"]
    if ps == "REJECTED":
        return None
    if ps in HUMAN_PLANNED:
        return line["planned_year"], line["cycle_years"], True
    if ps == "PROPOSED":
        return line["proposed_planned_year"], line["planning_basis"]["cycle_years_used"], False
    if line["planned_year"] is not None:
        return line["planned_year"], line["cycle_years"], True
    return None


def occurrence_years(line, start, end, include_proposals=True):
    s = schedule(line)
    if s is None or (not s[2] and not include_proposals):
        return []
    first, cycle, _ = s
    if cycle is None:
        return [first] if start <= first <= end else []
    years, y = [], first
    while y <= end:
        if y >= start:
            years.append(y)
        y += cycle
    return years


# --------------------------------------------------------------------------
# Prijsactualisatie (expliciet geïndexeerd historisch bedrag)
# --------------------------------------------------------------------------

def set_price_update(line, price_update):
    """System-derived voorstel (status PROPOSED). Een geaccepteerd/afgewezen voorstel wordt niet overschreven."""
    if line["price_update"] is not None and line["price_update"]["status"] != "PROPOSED":
        raise LineError("price_update heeft al een menselijke beslissing")
    new = copy.deepcopy(line)
    new["price_update"] = copy.deepcopy(price_update)
    flags = set(new["planner_flags"]) - {"PRICE_LEVEL_UNKNOWN", "INDEX_MISSING"}
    reason = price_update["not_computed_reason"]
    if reason in ("PRICE_LEVEL_UNKNOWN", "INDEX_MISSING"):
        flags.add(reason)
    new["planner_flags"] = sorted(flags)
    return validated(new)


def decide_price_update(line, decision, *, by, at, note=None):
    if line["price_update"] is None:
        raise LineError("geen price_update om over te beslissen")
    if decision not in ("ACCEPT", "REJECT"):
        raise LineError("alleen ACCEPT of REJECT; een eigen bedrag gaat via set_manual_amount")
    if not by:
        raise LineError("'by' is verplicht")
    new = copy.deepcopy(line)
    new["price_update"]["status"] = "HUMAN_ACCEPTED" if decision == "ACCEPT" else "REJECTED"
    new["price_update"]["verification"] = {"decision": decision, "by": by, "at": at, "note": note}
    return validated(new)


def cost_per_occurrence(line, include_proposals=True):
    """(bedrag per keer als Decimal, basis) of (None, reden).
    Volgorde: definitief v1-bedrag (kengetal/handmatig) > geaccepteerd geïndexeerd bedrag >
    (alleen met include_proposals) voorgesteld geïndexeerd bedrag."""
    f = line["financial"]
    if line["price_status"] in v1.DEFINITIVE:
        if f["effective_total"] is not None:
            return Decimal(f["effective_total"]), "DEFINITIVE_AMOUNT"
        return None, f["total_not_computed_reason"]
    pu = line["price_update"]
    if pu is not None and pu["indexed_total"] is not None:
        if pu["status"] == "HUMAN_ACCEPTED":
            return Decimal(pu["indexed_total"]), "ACCEPTED_INDEXED_HISTORICAL"
        if pu["status"] == "PROPOSED" and include_proposals:
            return Decimal(pu["indexed_total"]), "PROPOSED_INDEXED_HISTORICAL"
    return None, "NO_AMOUNT"
