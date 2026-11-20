#!/usr/bin/env python3
"""
mjop_actualisatie.py  (MJOP-ACTUALISERINGSTOOL "LIGHT": BESTAAND MJOP -> 30-JAARS CONCEPT, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md.

Stappen (allemaal deterministisch; voorstellen worden pas definitief na een menselijke beslissing):
  1. import       bestaand MJOP (data/verified/<DOC>.json) -> Maintenance Lines v2
  2. prijs        historisch bedrag per keer -> expliciet geïndexeerd (config/price_index.json)
  3. horizon      30-jaars voorstellen + toegevoegde langcyclische vervangingen
  4. reservefonds jaarlijks verloop + advies minimale storting (CONCEPT zolang er voorstellen in zitten)
  5. uitvoer      plan.json, lines.json, planner_report.json, reserve_fund.json,
                  review.xlsx (ACCEPT/EDIT/REJECT per regel) en rapport.md

Gebruik:
  python scripts/mjop_actualisatie.py run --document DOC-010 --building-id BLD-X --start-year 2027 \
      --opening-balance 50000 --annual-contribution 12000 [--cost-inflation 0.02] [--accepted-only] \
      [--last-replacement 4711=2010] [--out-dir reports/actualisatie]
  python scripts/mjop_actualisatie.py apply --dir reports/actualisatie/<mjop_id> --by NAAM
      (leest de ingevulde review.xlsx terug, legt beslissingen vast en rekent het reservefonds opnieuw door)

Het resultaat is een CONCEPT-MJOP op basis van een bestaand plan: NIET geïnspecteerd, geen
NEN 2767-conditiemeting en geen actuele marktprijzen.
"""
import argparse
import datetime
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_horizon_planner  # noqa: E402
import mjop_import_existing  # noqa: E402
import mjop_lifecycle  # noqa: E402
import mjop_maintenance_line_v2 as line_v2  # noqa: E402
import mjop_plan  # noqa: E402
import mjop_price_index  # noqa: E402
import mjop_reserve_fund  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_VERSION = "mjop_actualisatie_light_v1"
DISCLAIMER = ("CONCEPT op basis van een bestaand MJOP. Niet geïnspecteerd (geen NEN 2767-conditiemeting), "
              "geen actuele marktprijzen: bedragen zijn historische bedragen, expliciet geïndexeerd. "
              "Planjaren en bedragen zijn voorstellen tot een mens ze accepteert.")
FLAG_NL = {
    "NOT_INSPECTED": "niet geïnspecteerd", "CYCLE_UNKNOWN": "cyclus onbekend",
    "CYCLE_FROM_DOCUMENT_IRREGULAR": "onregelmatige jaren in oud MJOP", "CYCLE_DOCUMENT_TABLE_DIFFER": "cyclus oud MJOP wijkt af van levensduurtabel",
    "OVERDUE_NO_CYCLE": "planjaar verstreken, geen cyclus", "BASE_YEAR_UNKNOWN": "basisjaar onbekend",
    "ASSUMED_FROM_CONSTRUCTION_YEAR": "AANNAME: bouwjaar als laatste vervanging", "ELEMENT_CODE_MISSING": "geen elementcode",
    "ACTION_UNKNOWN": "actie niet genormaliseerd", "BEYOND_HORIZON": "valt na de horizon",
    "PRICE_LEVEL_UNKNOWN": "prijspeil oud MJOP onbekend", "INDEX_MISSING": "indexjaar ontbreekt"}
COLUMNS = ["maintenance_line_id", "herkomst", "elementcode", "omschrijving", "actie", "actie_tekst", "hoeveelheid",
           "eenheid", "planjaren_oud_mjop", "voorstel_jaar", "cyclus", "cyclus_bron", "basisjaar", "basisjaar_bron",
           "doorgerold", "vlaggen", "bedrag_oud_mjop", "prijspeil_oud", "factor", "bedrag_per_keer_voorstel",
           "planning_status", "bedrag_status", "BESLISSING_PLANNING", "JAAR", "CYCLUS", "BESLISSING_BEDRAG", "NOTITIE"]


def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load(path):
    return json.load(open(path, encoding="utf-8"))


def build(doc, *, mjop_id, building_id, start_year, target_price_year, index, table, fund_params, at,
          last_replacement_years=None, by=None):
    """Volledige run in het geheugen. Geeft dict met plan, lines, planner_report, import_summary, reserve_fund."""
    lines, import_summary = mjop_import_existing.import_document(doc, mjop_id=mjop_id, target_price_year=target_price_year,
                                                                 index=index)
    lines, planner_report = mjop_horizon_planner.run(doc, lines, table, start_year=start_year, mjop_id=mjop_id,
                                                     last_replacement_years=last_replacement_years)
    start, end = planner_report["horizon_start"], planner_report["horizon_end"]
    plan = mjop_plan.new_plan(mjop_id, building_id, at=at, by=by)
    plan = mjop_plan.set_horizon(plan, start, end, at=at)
    plan = mjop_plan.set_line_ids(plan, [l["maintenance_line_id"] for l in lines], at=at)
    mjop_plan.validated(plan, lines)
    fund = mjop_reserve_fund.run(lines, start=start, end=end, price_level_year=target_price_year, **fund_params)
    return {"plan": plan, "lines": lines, "planner_report": planner_report, "import_summary": import_summary,
            "reserve_fund": fund}


# --------------------------------------------------------------------------
# Review-sheet
# --------------------------------------------------------------------------

def review_rows(lines):
    rows = []
    for l in lines:
        b, src, pu = l["planning_basis"] or {}, l["origin_source"] or {}, l["price_update"] or {}
        rows.append([
            l["maintenance_line_id"], l["origin"], l["element_code_internal"], l["object_description"], l["action_normalized"],
            l["action_text"], l["quantity"], l["unit_normalized"],
            ", ".join(str(y) for y in src.get("document_planned_years", [])), l["proposed_planned_year"],
            b.get("cycle_years_used"), b.get("cycle_source"), b.get("base_year"), b.get("base_year_source"),
            "ja" if b.get("rolled_forward") else "", "; ".join(FLAG_NL.get(f, f) for f in l["planner_flags"]),
            pu.get("source_total_as_stated"), pu.get("base_price_level_year"), pu.get("indexation_factor"),
            pu.get("indexed_total_display"), l["planning_status"], pu.get("status"), None, None, None, None, None])
    return rows


def write_review_xlsx(result, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "Regels"
    ws.append(COLUMNS)
    for c in ws[1]:
        c.font = Font(bold=True)
        if c.value.isupper():
            c.fill = PatternFill("solid", fgColor="FFF2CC")
    for row in review_rows(result["lines"]):
        ws.append(row)
    n = ws.max_row
    col = {name: i + 1 for i, name in enumerate(COLUMNS)}
    for name, options in (("BESLISSING_PLANNING", '"ACCEPT,EDIT,REJECT"'), ("BESLISSING_BEDRAG", '"ACCEPT,REJECT"')):
        dv = DataValidation(type="list", formula1=options, allow_blank=True)
        letter = ws.cell(row=1, column=col[name]).column_letter
        dv.add(f"{letter}2:{letter}{max(n, 2)}")
        ws.add_data_validation(dv)
    ws.freeze_panes = "B2"

    fs = wb.create_sheet("Reservefonds")
    fund = result["reserve_fund"]
    fs.append(["Status", fund["status"]])
    for w in fund["warnings"]:
        fs.append(["Let op", w])
    fs.append([])
    fs.append(["jaar", "beginsaldo", "storting", "rente", "uitgaven", "eindsaldo"])
    for c in fs[fs.max_row]:
        c.font = Font(bold=True)
    for y in fund["years"]:
        fs.append([y["year"]] + [float(Decimal(y[k])) for k in ("opening", "contribution", "interest", "expenses", "closing")])
    fs.append([])
    for k, v in fund["advice"].items():
        fs.append([k, v])

    us = wb.create_sheet("Levensduur onbekend")
    us.append(["elementcode", "element_id", "element", "vervanging waargenomen in # documenten", "toelichting"])
    for u in result["planner_report"]["lifecycle_unknown"]:
        us.append([u["element_code"], u["element_id"], u["element_name"], u["replace_observed_in_documents"], u["reason"]])

    ts = wb.create_sheet("Toelichting")
    for line in [DISCLAIMER, "",
                 "BESLISSING_PLANNING: ACCEPT = voorstel overnemen; EDIT = eigen JAAR en/of CYCLUS invullen; REJECT = niet inplannen.",
                 "BESLISSING_BEDRAG: ACCEPT = geïndexeerd historisch bedrag gebruiken; REJECT = niet gebruiken "
                 "(een eigen bedrag gaat via kengetal of handmatig bedrag).",
                 "Daarna: python scripts/mjop_actualisatie.py apply --dir <map> --by <naam>"]:
        ts.append([line])
    wb.save(path)


def read_review_xlsx(path):
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=True)["Regels"]
    header = [c.value for c in ws[1]]
    if header != COLUMNS:
        raise SystemExit("review.xlsx heeft onverwachte kolommen; niet verwerkt")
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        r = dict(zip(header, row))
        if r["maintenance_line_id"]:
            out[r["maintenance_line_id"]] = r
    return out


def _int_or_none(v, name, line_id):
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise SystemExit(f"{line_id}: {name} moet een geheel getal zijn, niet {v!r}") from None


def apply_decisions(lines, decisions, *, by, at):
    """Verwerkt BESLISSING_PLANNING / BESLISSING_BEDRAG. Lege cellen = geen beslissing."""
    out, counts = [], {"planning": 0, "price": 0}
    for l in lines:
        r = decisions.get(l["maintenance_line_id"])
        if r:
            note = r.get("NOTITIE")
            dp = (r.get("BESLISSING_PLANNING") or "").strip().upper()
            if dp and l["planning_status"] in line_v2.HUMAN_PLANNED + ("REJECTED",):
                raise SystemExit(f"{l['maintenance_line_id']}: heeft al een planningsbeslissing ({l['planning_status']})")
            if dp:
                l = line_v2.decide_planning(l, dp, by=by, at=at, note=note,
                                            year=_int_or_none(r.get("JAAR"), "JAAR", l["maintenance_line_id"]),
                                            cycle_years=_int_or_none(r.get("CYCLUS"), "CYCLUS", l["maintenance_line_id"]))
                counts["planning"] += 1
            db = (r.get("BESLISSING_BEDRAG") or "").strip().upper()
            if db and (l["price_update"] is None or l["price_update"]["status"] != "PROPOSED"):
                raise SystemExit(f"{l['maintenance_line_id']}: geen open bedragvoorstel")
            if db:
                l = line_v2.decide_price_update(l, db, by=by, at=at, note=note)
                counts["price"] += 1
        out.append(l)
    return out, counts


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

def euro(s):
    whole = f"{Decimal(s).quantize(Decimal('1')):,.0f}".replace(",", ".")
    return f"€ {whole}"


def write_report(result, meta, path):
    p, f, imp = result["planner_report"], result["reserve_fund"], result["import_summary"]
    L = [f"# Actualisatie MJOP — {meta['document_id']} → 30 jaar ({p['horizon_start']}–{p['horizon_end']})", "",
         f"> {DISCLAIMER}", "",
         f"Tool: `{TOOL_VERSION}` · gemaakt: {meta['at']} · MJOP-id: `{result['plan']['mjop_id']}`", "",
         "## Wat er is gedaan", "",
         f"- {imp['source_actions']} posten uit het bestaande MJOP ingelezen → {imp['lines']} regels "
         f"({imp['without_element_code']} zonder elementcode, {imp['without_action']} zonder genormaliseerde actie).",
         f"- Prijspeil oud MJOP: {imp['price_level_year'] or 'onbekend'}; geïndexeerd naar {meta['target_price_year']} "
         f"(index: {meta['index_source'] or 'geen reeks ingevoerd'}).",
         f"- Planner: {p['lines_with_proposal']} regels met een jaarvoorstel, {p['lines_rolled_forward']} doorgerold, "
         f"{p['lines_added_from_lifecycle']} langcyclische vervangingen toegevoegd.",
         f"- {len(p['lifecycle_unknown'])} elementen zonder vastgestelde vervangingscyclus (zie review.xlsx, tabblad 'Levensduur onbekend').",
         "", "## Aandachtspunten (vlaggen)", "", "| vlag | regels |", "|---|---|"]
    L += [f"| {FLAG_NL.get(k, k)} | {v} |" for k, v in p["flag_counts"].items()]
    L += ["", f"## Reservefonds ({f['status']})", ""]
    L += [f"- ⚠️ {w}" for w in f["warnings"]]
    pr = f["parameters"]
    L += ["", f"Beginsaldo {euro(pr['opening_balance'])}, huidige storting {euro(pr['annual_contribution'])}/jaar, "
              f"kosteninflatie {pr['cost_inflation']}, rente {pr['interest_rate']}.", "",
          f"- Totale uitgaven {p['horizon_start']}–{p['horizon_end']}: **{euro(f['total_expenses'])}**",
          f"- Laagste saldo: {euro(f['lowest_balance']['closing'])} in {f['lowest_balance']['year']}",
          f"- Tekortjaren met huidige storting: {', '.join(map(str, f['shortfall_years'])) or 'geen'}",
          f"- Advies minimale gelijkblijvende storting: **{euro(f['advice']['level_contribution'])}/jaar**"]
    if "indexed_contribution_first_year" in f["advice"]:
        L.append(f"- Advies geïndexeerde storting (groei {f['advice']['indexed_growth_rate']}): "
                 f"{euro(f['advice']['indexed_contribution_first_year'])} in het eerste jaar")
    if "comparison_half_percent_rebuild_value" in f["advice"]:
        L.append(f"- Ter vergelijking 0,5% van de herbouwwaarde: {euro(f['advice']['comparison_half_percent_rebuild_value'])}/jaar")
    L += ["", "| jaar | storting | uitgaven | eindsaldo |", "|---|---:|---:|---:|"]
    L += [f"| {y['year']} | {euro(y['contribution'])} | {euro(y['expenses'])} | {euro(y['closing'])} |" for y in f["years"]]
    L += ["", "## Volgende stap", "",
          "Vul in `review.xlsx` per regel BESLISSING_PLANNING en BESLISSING_BEDRAG in en verwerk met "
          "`python scripts/mjop_actualisatie.py apply --dir <deze map> --by <naam>`. "
          "Leg ontbrekende levensduren vast met `python scripts/mjop_lifecycle.py decide ...`.", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


def write_outputs(result, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    _dump(result["plan"], os.path.join(out_dir, "plan.json"))
    _dump(result["lines"], os.path.join(out_dir, "lines.json"))
    _dump({"import_summary": result["import_summary"], **result["planner_report"]}, os.path.join(out_dir, "planner_report.json"))
    _dump(result["reserve_fund"], os.path.join(out_dir, "reserve_fund.json"))
    _dump(meta, os.path.join(out_dir, "run_meta.json"))
    write_review_xlsx(result, os.path.join(out_dir, "review.xlsx"))
    write_report(result, meta, os.path.join(out_dir, "rapport.md"))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _fund_params(a):
    return {"opening_balance": a.opening_balance, "annual_contribution": a.annual_contribution,
            "contribution_growth": a.contribution_growth, "interest_rate": a.interest_rate,
            "cost_inflation": a.cost_inflation, "min_balance": a.min_balance,
            "include_proposals": not a.accepted_only, "rebuild_value": a.rebuild_value}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--document", required=True)
    r.add_argument("--building-id", required=True, help="fysiek gebouw; wordt niet afgeleid")
    r.add_argument("--mjop-id")
    r.add_argument("--start-year", type=int, required=True)
    r.add_argument("--target-price-year", type=int, help="prijspeil voor indexatie en reservefonds (standaard: start-year)")
    r.add_argument("--last-replacement", action="append", default=[], metavar="CODE=JAAR")
    r.add_argument("--out-dir", default=os.path.join(ROOT, "reports", "actualisatie"))
    r.add_argument("--lifecycle-table", default=mjop_lifecycle.DEFAULT_TABLE)
    r.add_argument("--price-index", default=mjop_price_index.DEFAULT_INDEX)
    r.add_argument("--by")
    a2 = sub.add_parser("apply")
    a2.add_argument("--dir", required=True)
    a2.add_argument("--by", required=True)
    for sp in (r, a2):
        sp.add_argument("--opening-balance", required=sp is r)
        sp.add_argument("--annual-contribution", required=sp is r)
        sp.add_argument("--contribution-growth", default=None if sp is a2 else "0")
        sp.add_argument("--interest-rate", default=None if sp is a2 else "0")
        sp.add_argument("--cost-inflation", default=None if sp is a2 else "0")
        sp.add_argument("--min-balance", default=None if sp is a2 else "0")
        sp.add_argument("--rebuild-value")
        sp.add_argument("--accepted-only", action="store_true", help="alleen door een mens geaccepteerde jaren/bedragen")
    a = p.parse_args(argv)
    at = now()
    if a.cmd == "run":
        doc = _load(os.path.join(ROOT, "data", "verified", f"{a.document}.json"))
        target = a.target_price_year or a.start_year
        mjop_id = a.mjop_id or f"MJOP-{a.document}-ACT{a.start_year}"
        last_repl = {}
        for item in a.last_replacement:
            code, _, year = item.partition("=")
            if not year.isdigit():
                raise SystemExit(f"--last-replacement verwacht CODE=JAAR, niet {item!r}")
            last_repl[code] = int(year)
        index = mjop_price_index.load_index(a.price_index)
        table = mjop_lifecycle.load_table(a.lifecycle_table)
        result = build(doc, mjop_id=mjop_id, building_id=a.building_id, start_year=a.start_year, target_price_year=target,
                       index=index, table=table, fund_params=_fund_params(a), at=at, last_replacement_years=last_repl, by=a.by)
        meta = {"tool_version": TOOL_VERSION, "at": at, "document_id": a.document, "target_price_year": target,
                "index_source": index.get("index_source"), "lifecycle_table_generated_at": table["generated_at"],
                "fund_params": _fund_params(a), "last_replacement_years": last_repl}
        out_dir = os.path.join(a.out_dir, mjop_id)
        write_outputs(result, meta, out_dir)
        f = result["reserve_fund"]
        print(f"{len(result['lines'])} regels, {result['planner_report']['lines_added_from_lifecycle']} toegevoegd; "
              f"reservefonds {f['status']}: advies {f['advice']['level_contribution']}/jaar -> {out_dir}")
        return 0
    meta = _load(os.path.join(a.dir, "run_meta.json"))
    plan, lines = _load(os.path.join(a.dir, "plan.json")), _load(os.path.join(a.dir, "lines.json"))
    lines, counts = apply_decisions(lines, read_review_xlsx(os.path.join(a.dir, "review.xlsx")), by=a.by, at=at)
    mjop_plan.validated(plan, lines)
    params = dict(meta["fund_params"])
    for k, v in _fund_params(a).items():
        if v is not None and not (k == "include_proposals" and v):
            params[k] = v
    fund = mjop_reserve_fund.run(lines, start=plan["plan_start_year"], end=plan["plan_end_year"],
                                 price_level_year=meta["target_price_year"], **params)
    report = _load(os.path.join(a.dir, "planner_report.json"))
    imp = report.pop("import_summary")
    result = {"plan": plan, "lines": lines, "planner_report": report, "import_summary": imp, "reserve_fund": fund}
    meta = {**meta, "applied_at": at, "applied_by": a.by, "fund_params": params}
    write_outputs(result, meta, a.dir)
    print(f"{counts['planning']} planningsbeslissingen, {counts['price']} bedragbeslissingen verwerkt; "
          f"reservefonds {fund['status']}: advies {fund['advice']['level_contribution']}/jaar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
