#!/usr/bin/env python3
"""
mjop_couplings.py  (KOPPELINGEN TUSSEN PLANMATIGE HANDELINGEN, v1)

Register: vocabularies/lifecycle_couplings.json (schema schemas/lifecycle_couplings.schema.json);
documentatie: docs/mjop_actualisatie_light_v1.md (sectie Koppelingen).

Na de jaarvoorstellen van de horizon-planner legt deze module volgers op het ritme van hun leider:

  SAMEN        bij elke ingreep van de leider              (eerste leiderjaar, leidercyclus)
  ELKE_N       bij elke n-de ingreep van de leider         (eerste leiderjaar, n x leidercyclus)
  MEESCHUIVEN  eigen cyclus; eerste jaar naar het dichtstbijzijnde leiderjaar binnen max_shift_years
  VERSCHOVEN   offset_years na de leider, ritme van de leider (bijv. overlagen 25 jaar na vervangen)

Ritme van een leider = de vereniging van de uitvoeringsjaren van alle passende regels binnen de
horizon. Is die regelmatig (vast interval), dan is dat het ritme (zo geeft 'elke dakingreep'
vervangen + overlagen samen een ritme van 25 jaar). Anders het meest voorkomende (eerste jaar,
cyclus) van de leiderregels (COUPLING_IRREGULAR_LEADER).

Regels:
  - alleen volgers zonder menselijke planningsbeslissing (PROPOSED/NOT_PLANNED) worden aangepast;
  - een koppeling zonder human_verification wordt niet toegepast;
  - planmatig onderhoud alleen: gebreken (B-posten) worden nooit gekoppeld of verschoven;
  - VERSCHOVEN met omgekeerde verankering: berust de leider alleen op een aanname (toegevoegd op
    basis van het bouwjaar of zonder basisjaar) en heeft de volger een jaar uit het oude MJOP, dan
    wordt de leider aan de volger verankerd (COUPLING_REANCHORED_LEADER);
  - VERSCHOVEN-volgers die ontbreken (bijv. overlagen bij een toegevoegde dakvervanging) worden als
    ADDED_FROM_LIFECYCLE toegevoegd als de levensduurtabel er een vastgestelde cyclus voor heeft.
"""
import copy
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_lifecycle  # noqa: E402
import mjop_maintenance_line_v2 as line_v2  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REGISTER = os.path.join(ROOT, "vocabularies", "lifecycle_couplings.json")
SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "lifecycle_couplings.schema.json"), encoding="utf-8"))
RESOLVED_BY_COUPLING = ("CYCLE_UNKNOWN", "OVERDUE_NO_CYCLE", "BASE_YEAR_UNKNOWN", "CYCLE_FROM_DOCUMENT_IRREGULAR")
COUPLING_FLAGS = ("COUPLED", "COUPLING_LEADER_ABSENT", "COUPLING_IRREGULAR_LEADER", "COUPLING_NO_LEADER_YEAR_IN_RANGE",
                  "COUPLING_REANCHORED_LEADER")
ASSUMED_BASES = ("CONSTRUCTION_YEAR_ASSUMPTION", None)


class CouplingError(ValueError):
    pass


def load_register(path=DEFAULT_REGISTER):
    import jsonschema
    reg = json.load(open(path, encoding="utf-8"))
    errors = [e.message for e in jsonschema.Draft7Validator(SCHEMA).iter_errors(reg)]
    for c in reg["couplings"]:
        if "group" in c["leader"] and c["leader"]["group"] not in reg["groups"]:
            errors.append(f"{c['id']}: onbekende groep {c['leader']['group']}")
        if c["type"] == "VERSCHOVEN" and c["offset_years"] is None:
            errors.append(f"{c['id']}: VERSCHOVEN zonder offset_years")
        if c["type"] == "ELKE_N" and not c["every_n"]:
            errors.append(f"{c['id']}: ELKE_N zonder every_n")
    if errors:
        raise CouplingError("; ".join(errors))
    return reg


def _matches(line, spec):
    return line["action_normalized"] == spec["action"] and (
        spec["element_code"] is None or line["element_code_internal"] == spec["element_code"])


def _leader_specs(coupling, reg):
    leader = coupling["leader"]
    return reg["groups"][leader["group"]]["members"] if "group" in leader else [leader]


def _leader_label(coupling, reg):
    leader = coupling["leader"]
    if "group" in leader:
        return reg["groups"][leader["group"]]["label_nl"]
    return f"{leader['element_code'] or '*'} {leader['action']}"


RHYTHM_WINDOW = 100   # ritme over een ruimer venster dan de horizon, zodat één ingreep in de horizon geen vals ritme geeft


def _schedules(lines, start, end):
    out = []
    for l in lines:
        years = line_v2.occurrence_years(l, start, end + RHYTHM_WINDOW, include_proposals=True)
        if years:
            sched = line_v2.schedule(l)
            out.append((l, years, sched[1]))
    return out


def rhythm(scheds):
    """(eerste jaar, cyclus of None, alle jaren, onregelmatig?) uit [(regel, jaren, cyclus)]."""
    years = sorted({y for _, ys, _ in scheds for y in ys})
    if not years:
        return None
    diffs = {b - a for a, b in zip(years, years[1:])}
    if len(diffs) <= 1:
        return years[0], (diffs.pop() if diffs else next((c for _, _, c in scheds if c), None)), years, False
    first, cycle = Counter((ys[0], c) for _, ys, c in scheds).most_common(1)[0][0]
    return first, cycle, years, True


def _normalize(year, cycle, start):
    """Jaar in de reeks year + k x cycle (k mag negatief) dat het eerst op of na start valt."""
    if not cycle:
        return year
    while year - cycle >= start:
        year -= cycle
    while year < start:
        year += cycle
    return year


def _propose(line, first, cycle, coupling, reg, leader_years, start, end, *, extra_flags=(), shift=None, reverse=False):
    basis = copy.deepcopy(line["planning_basis"]) if line["planning_basis"] else {
        "planner_version": "mjop_couplings_v1", "horizon_start": start, "horizon_end": end, "rolled_forward": False}
    basis.update({"cycle_years_used": cycle or None, "cycle_source": "COUPLING", "base_year": leader_years[0] if leader_years else first,
                  "base_year_source": "COUPLING_LEADER", "rolled_forward": False, "horizon_start": start, "horizon_end": end,
                  "coupling": {"id": coupling["id"], "type": coupling["type"], "label_nl": coupling["label_nl"],
                               "leader_years": leader_years[:12], "shift_years": shift, "reverse_anchor": reverse}})
    flags = {f for f in line["planner_flags"] if f in line_v2.PLANNING_FLAGS} - set(RESOLVED_BY_COUPLING) - set(COUPLING_FLAGS)
    flags |= {"COUPLED", *extra_flags}
    proposed = first
    if proposed is not None and proposed > end:
        flags.add("BEYOND_HORIZON")
    return line_v2.set_planner_proposal(line, proposed, basis, sorted(flags))


def _flag(line, flag):
    if line["planning_status"] != "PROPOSED" and line["planning_status"] != "NOT_PLANNED":
        return line
    flags = sorted(set(line["planner_flags"]) | {flag})
    new = copy.deepcopy(line)
    new["planner_flags"] = flags
    return line_v2.validated(new)


def _editable(line):
    return line["planning_status"] in ("PROPOSED", "NOT_PLANNED")


def apply_coupling(lines, coupling, reg, start, end):
    """Past één koppeling toe; geeft (nieuwe regels, aantal aangepaste volgers)."""
    by_id = {l["maintenance_line_id"]: l for l in lines}
    specs = _leader_specs(coupling, reg)
    same_key = "group" not in coupling["leader"] and coupling["leader"] == coupling["follower"]
    followers = [l for l in lines if _matches(l, coupling["follower"]) and _editable(l)]
    if same_key:
        candidates = sorted((l for l in lines if _matches(l, coupling["leader"]) and line_v2.schedule(l)),
                            key=lambda l: l["maintenance_line_id"])
        if len(candidates) < 2:
            return lines, 0
        leaders = [candidates[0]]
        followers = [l for l in candidates[1:] if _editable(l)]
    else:
        leaders = [l for l in lines if any(_matches(l, s) for s in specs) and not _matches(l, coupling["follower"])]
    if not followers:
        return lines, 0
    scheds = _schedules(leaders, start, end)
    changed = 0

    # omgekeerde verankering (VERSCHOVEN): leider berust op een aanname, volger op het oude MJOP
    if coupling["type"] == "VERSCHOVEN" and leaders and all(
            (l["planning_basis"] or {}).get("base_year_source") in ASSUMED_BASES and l["origin"] == "ADDED_FROM_LIFECYCLE"
            and _editable(l) for l in leaders):
        anchor = next((f for f in followers if (f["planning_basis"] or {}).get("base_year_source") == "DOCUMENT_PLANNED_YEAR"
                       and line_v2.schedule(f)), None)
        if anchor is not None:
            f0 = line_v2.schedule(anchor)[0]
            for l in leaders:
                cyc = line_v2.schedule(l)[1] if line_v2.schedule(l) else (l["planning_basis"] or {}).get("cycle_years_used")
                y = _normalize(f0 - coupling["offset_years"], cyc, start)
                by_id[l["maintenance_line_id"]] = _propose(l, y, cyc, coupling, reg, [f0], start, end,
                                                           extra_flags=("COUPLING_REANCHORED_LEADER",), reverse=True)
            lines = [by_id[l["maintenance_line_id"]] for l in lines]
            leaders = [by_id[l["maintenance_line_id"]] for l in leaders]
            scheds = _schedules(leaders, start, end)

    r = rhythm(scheds)
    for f in followers:
        if r is None:
            by_id[f["maintenance_line_id"]] = _flag(f, "COUPLING_LEADER_ABSENT")
            continue
        first, cycle, years, irregular = r
        extra = ("COUPLING_IRREGULAR_LEADER",) if irregular else ()
        own = line_v2.schedule(f)
        own_cycle = own[1] if own else (f["planning_basis"] or {}).get("cycle_years_used")
        if coupling["type"] == "SAMEN":
            new = _propose(f, first, cycle or own_cycle, coupling, reg, years, start, end, extra_flags=extra)
        elif coupling["type"] == "ELKE_N":
            new = _propose(f, first, (cycle * coupling["every_n"]) if cycle else own_cycle, coupling, reg, years, start, end,
                           extra_flags=extra)
        elif coupling["type"] == "VERSCHOVEN":
            cyc = cycle or own_cycle
            new = _propose(f, _normalize(first + coupling["offset_years"], cyc, start), cyc, coupling, reg, years, start, end,
                           extra_flags=extra)
        else:   # MEESCHUIVEN
            if not own:
                by_id[f["maintenance_line_id"]] = _flag(f, "COUPLING_NO_LEADER_YEAR_IN_RANGE")
                continue
            target = min((y for y in years if abs(y - own[0]) <= reg["max_shift_years"] and y >= start),
                         key=lambda y: (abs(y - own[0]), y), default=None)
            if target is None:
                by_id[f["maintenance_line_id"]] = _flag(f, "COUPLING_NO_LEADER_YEAR_IN_RANGE")
                continue
            new = _propose(f, target, own[1], coupling, reg, years, start, end, extra_flags=extra, shift=target - own[0])
        by_id[f["maintenance_line_id"]] = new
        changed += 1
    return [by_id[l["maintenance_line_id"]] for l in lines], changed


def add_missing_followers(lines, reg, table, *, mjop_id, line_prefix=None):
    """VERSCHOVEN-volgers die ontbreken bij een aanwezige leider (bijv. overlagen bij dakvervanging)."""
    prefix, added, n = line_prefix or mjop_id, [], 0
    for c in reg["couplings"]:
        if c["type"] != "VERSCHOVEN" or not c["human_verification"] or "group" in c["leader"] or c["follower"]["element_code"] is None:
            continue
        fol = c["follower"]
        if any(_matches(l, fol) for l in lines + added):
            continue
        cycle = mjop_lifecycle.effective_cycle(table, fol["element_code"], fol["action"])
        leader = next((l for l in lines if _matches(l, c["leader"])), None)
        if cycle is None or leader is None:
            continue
        n += 1
        src = line_v2.origin_source("LIFECYCLE_TABLE", document_id=(leader["origin_source"] or {}).get("document_id"),
                                    source_element_id=leader["object_id"], lifecycle_key=dict(fol),
                                    note=f"Toegevoegd via koppeling {c['id']}: {c['label_nl']}.")
        line = line_v2.new_line(f"{prefix}-C{n:04d}", mjop_id, leader["object_id"], origin="ADDED_FROM_LIFECYCLE",
                                origin_source=src, planner_flags=["NOT_INSPECTED"], element_code_internal=fol["element_code"],
                                object_description=leader["object_description"], action_normalized=fol["action"],
                                unit_normalized=leader["unit_normalized"], unit_text=leader["unit_text"], quantity=leader["quantity"],
                                context=dict(leader["context"]))
        added.append(line)
    return added


def apply_all(lines, reg, start, end):
    """Alle goedgekeurde koppelingen in registervolgorde. Geeft (regels, {id: aantal})."""
    counts = {}
    for c in reg["couplings"]:
        if not c["human_verification"]:
            continue
        lines, counts[c["id"]] = apply_coupling(lines, c, reg, start, end)
    return lines, counts
