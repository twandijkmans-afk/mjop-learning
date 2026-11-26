#!/usr/bin/env python3
"""
mjop_horizon_planner.py  (DETERMINISTISCHE 30-JAARS HORIZON-PLANNER, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md.

Doet VOORSTELLEN (proposed_planned_year + planning_basis + planner_flags); een mens beslist via
mjop_maintenance_line_v2.decide_planning. Regels met een menselijke planningsbeslissing worden
nooit overschreven.

Per bestaande regel:
  cyclus      : line.cycle_years (LINE) > gelijkmatige intervallen in het bron-document
                (DOCUMENT_INTERVAL) > door een mens vastgestelde levensduurtabel (LIFECYCLE_TABLE).
                Onregelmatige intervallen -> CYCLE_FROM_DOCUMENT_IRREGULAR; document en tabel
                verschillen -> CYCLE_DOCUMENT_TABLE_DIFFER (document wint, mens beslist).
  eerste jaar : vroegste document-planjaar >= start (niet doorgerold); anders laatste
                document-planjaar of last_replacement/maintenance_year + n x cyclus (doorgerold).
                Zonder cyclus en met alleen jaren vóór start -> OVERDUE_NO_CYCLE (geen voorstel).
                Na het einde van de horizon -> BEYOND_HORIZON (voorstel blijft staan; telt niet mee in de horizon).

Gaten (langcyclische vervangingen die in een 10-15-jaars plan ontbreken):
  voor elk fysiek element (met code) uit het bron-document waarvoor de levensduurtabel een
  menselijk vastgestelde 'replace'-cyclus heeft en waarvoor geen vervanging binnen de horizon
  gepland staat, wordt een regel ADDED_FROM_LIFECYCLE voorgesteld. Basisjaar: een door de
  gebruiker opgegeven laatste vervangingsjaar, anders het bouwjaar (ASSUMED_FROM_CONSTRUCTION_YEAR,
  altijd een aanname), anders geen voorstel (BASE_YEAR_UNKNOWN).
  Elementen zonder vastgestelde vervangingscyclus komen op de checklist 'lifecycle_unknown'.
"""
import os
import sys
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_couplings  # noqa: E402
import mjop_defects  # noqa: E402
import mjop_lifecycle  # noqa: E402
import mjop_maintenance_line_v2 as line_v2  # noqa: E402

PLANNER_VERSION = "mjop_horizon_planner_v1"
DEFAULT_POLICY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vocabularies", "planning_policy.json")


def load_policy(path=DEFAULT_POLICY):
    import json
    return json.load(open(path, encoding="utf-8"))


def apply_policy(line, policy):
    """Beleid (vocabularies/planning_policy.json): uitgesloten handelingen (bijv. reinigen) worden niet
    standaard opgenomen. Planningsbeslissing REJECT namens de beslisser van het beleid."""
    rule = (policy or {}).get("excluded_actions", {}).get(line["action_normalized"] or "")
    if not rule or line["planning_status"] in line_v2.HUMAN_PLANNED + ("REJECTED",):
        return line
    new = line_v2.decide_planning(line, "REJECT", by=rule["by"], at=rule["at"], note=f"beleid: {rule['note']}")
    new = dict(new, planner_flags=sorted(set(new["planner_flags"]) | {"EXCLUDED_BY_POLICY"}))
    return line_v2.validated(new)
DEFAULT_HORIZON_YEARS = 30


def _v(field):
    if isinstance(field, dict):
        return field.get("normalized_value", field.get("value"))
    return field


def _positive(q):
    try:
        d = Decimal(str(q))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return format(d, "f") if q is not None and d > 0 else None


def horizon(start_year, horizon_years=DEFAULT_HORIZON_YEARS):
    return start_year, start_year + horizon_years - 1


def document_cycle(years):
    """(cyclus of None, onregelmatig?) uit de planjaren van één regel in het bron-document."""
    ys = sorted(set(years))
    intervals = {b - a for a, b in zip(ys, ys[1:])}
    if len(intervals) == 1:
        return intervals.pop(), False
    return None, len(intervals) > 1


def roll_forward(base, cycle, start):
    if base >= start:
        return base
    k = -(-(start - base) // cycle)   # plafond-deling
    return base + k * cycle


def plan_line(line, table, start, end):
    """(proposed_year, planning_basis, flags) voor één regel."""
    flags = []
    src = line["origin_source"] or {}
    doc_years = src.get("document_planned_years") or []
    doc_cycle, irregular = document_cycle(doc_years)
    table_cycle = None
    if line["element_code_internal"] and line["action_normalized"]:
        table_cycle = mjop_lifecycle.effective_cycle(table, line["element_code_internal"], line["action_normalized"])
    if line["cycle_years"]:
        cycle, cycle_source = line["cycle_years"], "LINE"
    elif doc_cycle:
        cycle, cycle_source = doc_cycle, "DOCUMENT_INTERVAL"
        if table_cycle and table_cycle != doc_cycle:
            flags.append("CYCLE_DOCUMENT_TABLE_DIFFER")
    elif table_cycle:
        cycle, cycle_source = table_cycle, "LIFECYCLE_TABLE"
    else:
        cycle, cycle_source = None, None
        flags.append("CYCLE_UNKNOWN")
    if irregular:
        flags.append("CYCLE_FROM_DOCUMENT_IRREGULAR")

    future_doc = [y for y in doc_years if y >= start]
    if line["action_normalized"] == "replace" and line["last_replacement_year"]:
        base, base_source = line["last_replacement_year"] + (cycle or 0), "LAST_REPLACEMENT_YEAR"
    elif line["action_normalized"] != "replace" and line["last_maintenance_year"]:
        base, base_source = line["last_maintenance_year"] + (cycle or 0), "LAST_MAINTENANCE_YEAR"
    elif future_doc:
        base, base_source = min(future_doc), "DOCUMENT_PLANNED_YEAR"
    elif doc_years:
        base, base_source = max(doc_years), "DOCUMENT_PLANNED_YEAR"
    else:
        base, base_source = None, None
        flags.append("BASE_YEAR_UNKNOWN")

    proposed, rolled = None, False
    if base is not None:
        if base >= start:
            proposed = base
        elif cycle:
            proposed, rolled = roll_forward(base, cycle, start), True
        else:
            flags.append("OVERDUE_NO_CYCLE")
    if proposed is not None and proposed > end:
        flags.append("BEYOND_HORIZON")   # voorstel blijft: telt niet in de horizon, wel voor ritme en OPrognose
    basis = {"planner_version": PLANNER_VERSION, "horizon_start": start, "horizon_end": end,
             "cycle_years_used": cycle, "cycle_source": cycle_source, "base_year": base,
             "base_year_source": base_source, "rolled_forward": rolled}
    return proposed, basis, flags


def _replacement_in_horizon(lines, code, start, end):
    """Is er al een vervanging gepland: binnen de horizon, of met een (voorgesteld) jaar daarna of een
    bekend laatste vervangingsjaar? Dan niet nogmaals toevoegen."""
    for l in lines:
        if l["element_code_internal"] == code and l["action_normalized"] == "replace":
            if line_v2.occurrence_years(l, start, end, include_proposals=True):
                return True
            sched = line_v2.schedule(l)
            if (sched and sched[0] > end) or l["last_replacement_year"]:
                return True
    return False


def added_lifecycle_lines(doc, lines, table, start, end, *, mjop_id, last_replacement_years=None, line_prefix=None):
    """(nieuwe regels, checklist lifecycle_unknown). Eén regel per fysiek element zonder vervanging
    binnen de horizon, alleen met een menselijk vastgestelde vervangingscyclus."""
    last_replacement_years = last_replacement_years or {}
    construction_year = _v(doc["building"].get("construction_year"))
    prefix = line_prefix or mjop_id
    added, unknown, seen = [], [], set()
    n = 0
    for el in sorted(doc["elements"], key=lambda e: e["element_id"]):
        code = _v(el.get("element_code"))
        if not code or code in mjop_lifecycle.NON_PHYSICAL_CODES or code in seen:
            continue
        seen.add(code)
        if _replacement_in_horizon(lines + added, code, start, end):
            continue
        cycle = mjop_lifecycle.effective_cycle(table, code, "replace")
        if cycle is None:
            entry = mjop_lifecycle.entry_for(table, code, "replace")
            unknown.append({"element_code": code, "element_id": el["element_id"], "element_name": _v(el.get("element_name")),
                            "replace_observed_in_documents": entry["observed"]["n_documents"] if entry else 0,
                            "reason": "Geen door een mens vastgestelde vervangingscyclus; vervanging binnen 30 jaar onbekend."})
            continue
        flags = ["NOT_INSPECTED"]
        if code in last_replacement_years:
            install, base_source, last_repl = last_replacement_years[code], "LAST_REPLACEMENT_YEAR", last_replacement_years[code]
        elif construction_year:
            install, base_source, last_repl = construction_year, "CONSTRUCTION_YEAR_ASSUMPTION", None
            flags.append("ASSUMED_FROM_CONSTRUCTION_YEAR")
        else:
            install, base_source, last_repl = None, None, None
            flags.append("BASE_YEAR_UNKNOWN")
        n += 1
        src = line_v2.origin_source("LIFECYCLE_TABLE", document_id=doc["document_id"], source_element_id=el["element_id"],
                                    lifecycle_key={"element_code": code, "action": "replace"},
                                    note=f"Toegevoegd: geen vervanging binnen {start}-{end} in het bestaande MJOP.")
        quantity = _positive(_v(el.get("quantity")))
        line = line_v2.new_line(
            f"{prefix}-A{n:04d}", mjop_id, el["element_id"], origin="ADDED_FROM_LIFECYCLE", origin_source=src,
            planner_flags=flags, element_code_internal=code, object_description=_v(el.get("element_name")),
            action_normalized="replace", action_text=None, unit_normalized=_v(el.get("unit")),
            unit_text=(el.get("unit") or {}).get("original_value") if isinstance(el.get("unit"), dict) else None,
            quantity=quantity, last_replacement_year=last_repl,
            context={"construction_year": construction_year, "location": _v(el.get("location"))})
        proposed, rolled = None, False
        if install is not None:
            proposed = roll_forward(install + cycle, cycle, start)
            rolled = install + cycle < start
        if proposed is not None and proposed > end:
            flags.append("BEYOND_HORIZON")
        basis = {"planner_version": PLANNER_VERSION, "horizon_start": start, "horizon_end": end,
                 "cycle_years_used": cycle, "cycle_source": "LIFECYCLE_TABLE", "base_year": install,
                 "base_year_source": base_source, "rolled_forward": rolled}
        added.append(line_v2.set_planner_proposal(line, proposed, basis, flags))
    return added, unknown


def run(doc, lines, table, *, start_year, mjop_id, horizon_years=DEFAULT_HORIZON_YEARS,
        last_replacement_years=None, line_prefix=None, couplings=None, defects=None, policy=None):
    """Voorstellen voor alle regels + toegevoegde vervangingen + koppelingen. Geeft (lines, report).
    couplings: register (mjop_couplings.load_register()); None = het standaardregister, {} = geen koppelingen."""
    if couplings is None:
        couplings = mjop_couplings.load_register()
    if policy is None:
        policy = load_policy()
    lines = [apply_policy(l, policy) for l in lines]
    start, end = horizon(start_year, horizon_years)
    restarted = set()
    if defects:   # gebrek dat tot uitvoering leidt: ritme herstart vanaf het gebreksjaar
        lines, by_code, restarted = mjop_defects.apply_restarts(lines, defects)
        last_replacement_years = {**(last_replacement_years or {}), **by_code}
    out = []
    for l in lines:
        if l["planning_status"] in line_v2.HUMAN_PLANNED + ("REJECTED",):
            out.append(l)
            continue
        proposed, basis, flags = plan_line(l, table, start, end)
        out.append(line_v2.set_planner_proposal(l, proposed, basis, flags))
    added, unknown = added_lifecycle_lines(doc, out, table, start, end, mjop_id=mjop_id,
                                           last_replacement_years=last_replacement_years, line_prefix=line_prefix)
    all_lines = out + added
    coupling_counts, coupled_added = {}, []
    if couplings:
        coupled_added = mjop_couplings.add_missing_followers(all_lines, couplings, table, mjop_id=mjop_id, line_prefix=line_prefix)
        all_lines, coupling_counts = mjop_couplings.apply_all(all_lines + coupled_added, couplings, start, end)
    if restarted:
        all_lines = mjop_defects.mark_restarted(all_lines, restarted)
    flag_counts = {}
    for l in all_lines:
        for f in l["planner_flags"]:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    report = {"planner_version": PLANNER_VERSION, "horizon_start": start, "horizon_end": end,
              "lines_existing": len(out), "lines_added_from_lifecycle": len(added) + len(coupled_added),
              "lines_added_via_coupling": len(coupled_added), "lines_restarted_by_defect": len(restarted),
              "defects": len((defects or {}).get("defects", [])),
              "excluded_by_policy": [{"maintenance_line_id": l["maintenance_line_id"], "element_code": l["element_code_internal"],
                                      "action": l["action_normalized"], "text": l["action_text"]}
                                     for l in lines if "EXCLUDED_BY_POLICY" in l["planner_flags"]],
              "coupling_counts": {k: v for k, v in coupling_counts.items() if v},
              "lines_with_proposal": sum(1 for l in all_lines if l["planning_status"] == "PROPOSED"),
              "lines_rolled_forward": sum(1 for l in all_lines if (l["planning_basis"] or {}).get("rolled_forward")),
              "flag_counts": dict(sorted(flag_counts.items())), "lifecycle_unknown": unknown}
    return all_lines, report
