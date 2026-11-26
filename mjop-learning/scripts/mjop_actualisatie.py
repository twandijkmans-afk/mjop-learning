#!/usr/bin/env python3
"""
mjop_actualisatie.py  (MJOP-ACTUALISERINGSTOOL "LIGHT": BESTAAND MJOP -> 30-JAARS CONCEPT, v1)

Documentatie: docs/mjop_actualisatie_light_v1.md.

Stappen (allemaal deterministisch; voorstellen worden pas definitief na een menselijke beslissing):
  1. import       bestaand MJOP (data/verified/<DOC>.json) -> Maintenance Lines v2
  2. prijs        historisch bedrag per keer -> expliciet geïndexeerd (config/price_index.json)
  3. horizon      30-jaars voorstellen + toegevoegde langcyclische vervangingen
  4. reservefonds jaarlijks verloop + advies minimale storting (CONCEPT zolang er voorstellen in zitten)
  5. uitvoer      <mjop_id>.xml (OPrognose-importbestand), rapport.md en JSON (plan, regels,
                  planner- en exportrapport, reservefonds)

De beoordeling van de voorstellen gebeurt na import in OPrognose; elke handeling vermeldt daar in
de opmerking (han_opm) herkomst, aannames en vlaggen.

Gebruik:
  python scripts/mjop_actualisatie.py run --document DOC-010 --building-id BLD-X --start-year 2027 \
      --opening-balance 50000 --annual-contribution 12000 [--cost-inflation 0.02] \
      [--last-replacement 4711=2010] [--oprognose-code 9349-2027] [--out-dir reports/actualisatie]

Het resultaat is een CONCEPT-MJOP op basis van een bestaand plan: NIET geïnspecteerd, geen
NEN 2767-conditiemeting en geen actuele marktprijzen.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mjop_defects  # noqa: E402
import mjop_horizon_planner  # noqa: E402
import mjop_import_existing  # noqa: E402
import mjop_lifecycle  # noqa: E402
import mjop_oprognose_export  # noqa: E402
import mjop_plan  # noqa: E402
import mjop_price_index  # noqa: E402
import mjop_reserve_fund  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_VERSION = "mjop_actualisatie_light_v1"
DISCLAIMER = ("CONCEPT op basis van een bestaand MJOP. Niet geïnspecteerd (geen NEN 2767-conditiemeting), "
              "geen actuele marktprijzen: bedragen zijn historische bedragen uit het oude MJOP (geïndexeerd als er een indexreeks is). "
              "Planjaren en bedragen zijn voorstellen tot een mens ze accepteert.")
FLAG_NL = {
    "NOT_INSPECTED": "niet geïnspecteerd", "CYCLE_UNKNOWN": "cyclus onbekend",
    "CYCLE_FROM_DOCUMENT_IRREGULAR": "onregelmatige jaren in oud MJOP", "CYCLE_DOCUMENT_TABLE_DIFFER": "cyclus oud MJOP wijkt af van levensduurtabel",
    "OVERDUE_NO_CYCLE": "planjaar verstreken, geen cyclus", "BASE_YEAR_UNKNOWN": "basisjaar onbekend",
    "ASSUMED_FROM_CONSTRUCTION_YEAR": "AANNAME: bouwjaar als laatste vervanging", "ELEMENT_CODE_MISSING": "geen elementcode",
    "ACTION_UNKNOWN": "actie niet genormaliseerd", "BEYOND_HORIZON": "valt na de horizon",
    "PRICE_LEVEL_UNKNOWN": "prijspeil oud MJOP onbekend", "INDEX_MISSING": "indexjaar ontbreekt",
    "COUPLED": "gekoppeld", "COUPLING_LEADER_ABSENT": "koppeling: leider ontbreekt", "COUPLING_IRREGULAR_LEADER": "koppeling: leider zonder vast ritme",
    "COUPLING_NO_LEADER_YEAR_IN_RANGE": "koppeling: geen leiderjaar binnen schuifruimte",
    "COUPLING_REANCHORED_LEADER": "leider verankerd aan oud MJOP", "RESTARTED_BY_DEFECT": "ritme herstart na gebrek",
    "PHASED_IN_DOCUMENT": "gefaseerd in oud MJOP: elke fase eenmalig"}
def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dump(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load(path):
    return json.load(open(path, encoding="utf-8"))


def build(doc, *, mjop_id, building_id, start_year, target_price_year, index, table, fund_params, at,
          last_replacement_years=None, by=None, obj_code=None, fmt=None, defects=None):
    """Volledige run in het geheugen: regels, plan, OPrognose-dataset en reservefonds.
    defects: gevalideerde invoer van mjop_defects (B-posten, herstart van het ritme)."""
    lines, import_summary = mjop_import_existing.import_document(doc, mjop_id=mjop_id, target_price_year=target_price_year,
                                                                 index=index)
    lines, planner_report = mjop_horizon_planner.run(doc, lines, table, start_year=start_year, mjop_id=mjop_id,
                                                     last_replacement_years=last_replacement_years, defects=defects)
    start, end = planner_report["horizon_start"], planner_report["horizon_end"]
    plan = mjop_plan.new_plan(mjop_id, building_id, at=at, by=by)
    plan = mjop_plan.set_horizon(plan, start, end, at=at)
    plan = mjop_plan.set_line_ids(plan, [l["maintenance_line_id"] for l in lines], at=at)
    mjop_plan.validated(plan, lines)
    fmt = fmt or mjop_oprognose_export.load_format()
    source_year = import_summary["price_level_year"]
    when = datetime.datetime.fromisoformat(at.replace("Z", "+00:00"))
    dataset, export_report = mjop_oprognose_export.build_dataset(
        doc, lines, mjop_id=mjop_id, start_year=start, target_price_year=target_price_year,
        source_price_year=source_year, fmt=fmt, at=when, obj_code=obj_code, defects=defects)
    # reservefonds op dezelfde bedragen en hetzelfde prijspeil als het XML-bestand
    mode = export_report["price_mode"]
    fund_price_year = export_report["obj_prijspeil_year"] or target_price_year

    def amount(line, include_proposals=True):
        value, _ = mjop_oprognose_export.line_amount(line, mode)
        return (value, f"EXPORT_{mode.upper()}") if value is not None else (None, "NO_AMOUNT")

    fund = mjop_reserve_fund.run(lines, start=start, end=end, price_level_year=fund_price_year, amount_fn=amount,
                                 extra_expenses=mjop_defects.fund_expenses(defects) if defects else None, **fund_params)
    return {"plan": plan, "lines": lines, "planner_report": planner_report, "import_summary": import_summary,
            "reserve_fund": fund, "dataset": dataset, "export_report": export_report, "fmt": fmt}


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------

def euro(s):
    whole = f"{Decimal(s).quantize(Decimal('1')):,.0f}".replace(",", ".")
    return f"€ {whole}"


PRICE_MODE_NL = {"indexed": "geïndexeerde historische bedragen",
                 "historical": "historische bedragen, niet geïndexeerd (prijspeil oud MJOP; OPrognose kan indexeren)",
                 "historical_unknown_level": "geen bedragen ingevuld: prijspeil oud MJOP onbekend (bedrag staat in de opmerking)"}


def write_report(result, meta, path):
    p, f, imp, x = result["planner_report"], result["reserve_fund"], result["import_summary"], result["export_report"]
    L = [f"# Actualisatie MJOP — {meta['document_id']} → 30 jaar ({p['horizon_start']}–{p['horizon_end']})", "",
         f"> {DISCLAIMER}", "",
         f"Tool: `{TOOL_VERSION}` · gemaakt: {meta['at']} · MJOP-id: `{result['plan']['mjop_id']}`", "",
         "## OPrognose-importbestand", "",
         f"- Bestand: `{meta['xml_file']}` — {x['elements']} elementen, {x['actions']} handelingen.",
         f"- Bedragen: {PRICE_MODE_NL[x['price_mode']]}; obj_prijspeil {x['obj_prijspeil_year'] or 'leeg'}.",
         f"- {x['actions_proposed']} handelingen met een voorgesteld (niet beoordeeld) planjaar, "
         f"{x['actions_without_year']} zonder planjaar (startjaar 0), {x['actions_without_amount']} zonder bedrag.",
         f"- Afrondingsverschil door eenheidsprijs op centen (totaal): € {x['rounding_deviation_total']}.",
         f"- Gebreken (B-posten, ingevoerd door een adviseur): {x.get('defects', 0)}"
         + (f", waarvan {x['defects_without_price']} zonder prijs" if x.get("defects_without_price") else "")
         + (" — LET OP: prijspeil van de gebreken wijkt af van obj_prijspeil" if x.get("defect_price_level_differs") else "") + ".",
         "- Beoordeel na import in OPrognose vooral de handelingen met 'VOORSTEL', 'GEEN PLANJAAR', 'TOEGEVOEGD' of "
         "'AANNAME' in de opmerking.", "",
         "## Wat er is gedaan", "",
         f"- {imp['source_actions']} posten uit het bestaande MJOP ingelezen → {imp['lines']} regels "
         f"({imp['without_element_code']} zonder elementcode, {imp['without_action']} zonder genormaliseerde actie).",
         f"- Prijspeil oud MJOP: {imp['price_level_year'] or 'onbekend'}; index: {meta['index_source'] or 'geen reeks ingevoerd'}.",
         f"- Planner: {p['lines_with_proposal']} regels met een jaarvoorstel, {p['lines_rolled_forward']} doorgerold, "
         f"{p['lines_added_from_lifecycle']} langcyclische vervangingen toegevoegd.",
         f"- {len(p['lifecycle_unknown'])} elementen zonder vastgestelde vervangingscyclus:"]
    L += [f"  - {u['element_code']} {u['element_name'] or ''}" for u in p["lifecycle_unknown"]]
    L += ["", "## Aandachtspunten (vlaggen)", "", "| vlag | regels |", "|---|---|"]
    L += [f"| {FLAG_NL.get(k, k)} | {v} |" for k, v in p["flag_counts"].items()]
    L += ["", f"## Reservefonds ({f['status']})", ""]
    L += [f"- ⚠️ {w}" for w in f["warnings"]]
    pr = f["parameters"]
    L += ["", f"Prijspeil {pr['price_level_year']}; beginsaldo {euro(pr['opening_balance'])}, huidige storting "
              f"{euro(pr['annual_contribution'])}/jaar, kosteninflatie {pr['cost_inflation']}, rente {pr['interest_rate']}.", "",
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
          f"Importeer `{meta['xml_file']}` in OPrognose en beoordeel daar de voorstellen. Leg ontbrekende levensduren vast "
          "met `python scripts/mjop_lifecycle.py decide ...` en draai de actualisatie opnieuw.", ""]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


def write_outputs(result, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    xml_file = f"{result['plan']['mjop_id']}.xml"
    meta = {**meta, "xml_file": xml_file}
    mjop_oprognose_export.write(result["dataset"], result["fmt"], os.path.join(out_dir, xml_file))
    _dump(result["plan"], os.path.join(out_dir, "plan.json"))
    _dump(result["lines"], os.path.join(out_dir, "lines.json"))
    _dump({"import_summary": result["import_summary"], **result["planner_report"]}, os.path.join(out_dir, "planner_report.json"))
    _dump(result["export_report"], os.path.join(out_dir, "oprognose_export_report.json"))
    _dump(result["reserve_fund"], os.path.join(out_dir, "reserve_fund.json"))
    _dump(meta, os.path.join(out_dir, "run_meta.json"))
    write_report(result, meta, os.path.join(out_dir, "rapport.md"))
    return os.path.join(out_dir, xml_file)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--document", required=True)
    r.add_argument("--building-id", required=True, help="fysiek gebouw; wordt niet afgeleid")
    r.add_argument("--mjop-id")
    r.add_argument("--oprognose-code", help="obj_code in OPrognose (standaard: mjop-id)")
    r.add_argument("--start-year", type=int, required=True)
    r.add_argument("--target-price-year", type=int, help="prijspeil voor indexatie (standaard: start-year)")
    r.add_argument("--last-replacement", action="append", default=[], metavar="CODE=JAAR")
    r.add_argument("--out-dir", default=os.path.join(ROOT, "reports", "actualisatie"))
    r.add_argument("--lifecycle-table", default=mjop_lifecycle.DEFAULT_TABLE)
    r.add_argument("--price-index", default=mjop_price_index.DEFAULT_INDEX)
    r.add_argument("--by")
    r.add_argument("--opening-balance", required=True)
    r.add_argument("--annual-contribution", required=True)
    r.add_argument("--contribution-growth", default="0")
    r.add_argument("--interest-rate", default="0")
    r.add_argument("--cost-inflation", default="0")
    r.add_argument("--min-balance", default="0")
    r.add_argument("--rebuild-value")
    r.add_argument("--defects", help="JSON met door een adviseur ingevoerde gebreken (schemas/defect_input.schema.json)")
    a = p.parse_args(argv)
    at = now()
    doc = _load(os.path.join(ROOT, "data", "verified", f"{a.document}.json"))
    target = a.target_price_year or a.start_year
    mjop_id = a.mjop_id or f"MJOP-{a.document}-ACT{a.start_year}"
    last_repl = {}
    for item in a.last_replacement:
        code, _, year = item.partition("=")
        if not year.isdigit():
            raise SystemExit(f"--last-replacement verwacht CODE=JAAR, niet {item!r}")
        last_repl[code] = int(year)
    fund_params = {"opening_balance": a.opening_balance, "annual_contribution": a.annual_contribution,
                   "contribution_growth": a.contribution_growth, "interest_rate": a.interest_rate,
                   "cost_inflation": a.cost_inflation, "min_balance": a.min_balance, "rebuild_value": a.rebuild_value}
    index = mjop_price_index.load_index(a.price_index)
    table = mjop_lifecycle.load_table(a.lifecycle_table)
    defects = mjop_defects.load(a.defects, doc) if a.defects else None
    result = build(doc, mjop_id=mjop_id, building_id=a.building_id, start_year=a.start_year, target_price_year=target,
                   index=index, table=table, fund_params=fund_params, at=at, last_replacement_years=last_repl, by=a.by,
                   obj_code=a.oprognose_code, defects=defects)
    meta = {"tool_version": TOOL_VERSION, "at": at, "document_id": a.document, "target_price_year": target,
            "index_source": index.get("index_source"), "lifecycle_table_generated_at": table["generated_at"],
            "fund_params": fund_params, "last_replacement_years": last_repl,
            "defects_file_sha256": None if not a.defects else hashlib.sha256(open(a.defects, "rb").read()).hexdigest()}
    xml_path = write_outputs(result, meta, os.path.join(a.out_dir, mjop_id))
    x, f = result["export_report"], result["reserve_fund"]
    print(f"{x['elements']} elementen, {x['actions']} handelingen ({x['price_mode']}) -> {xml_path}; "
          f"reservefonds: advies {f['advice']['level_contribution']}/jaar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
