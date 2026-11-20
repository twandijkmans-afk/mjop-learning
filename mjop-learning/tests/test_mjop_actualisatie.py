"""
Tests voor de MJOP-actualiseringstool "Light" (docs/mjop_actualisatie_light_v1.md):
levensduurtabel, Maintenance Line v2, prijsindex, import, horizon-planner, reservefonds en
de OPrognose XML-export en de end-to-end CLI. Synthetische documenten;
alleen tmp_path wordt beschreven.
"""
import copy
import json
import os
import sys
from decimal import Decimal

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

import mjop_actualisatie as A  # noqa: E402
import mjop_horizon_planner as H  # noqa: E402
import mjop_import_existing as I  # noqa: E402
import mjop_lifecycle as LC  # noqa: E402
import mjop_maintenance_line as L1  # noqa: E402
import mjop_maintenance_line_v2 as L2  # noqa: E402
import mjop_oprognose_export as X  # noqa: E402
import mjop_plan as P  # noqa: E402
import mjop_price_index as PI  # noqa: E402
import mjop_reserve_fund as RF  # noqa: E402

T0 = "2026-11-20T10:00:00Z"
INDEX = {"index_version": "price_index_v1", "index_source": "TEST", "series": {"2020": "100", "2027": "125"}}
EMPTY_INDEX = {"index_version": "price_index_v1", "index_source": None, "series": {}}


# --------------------------------------------------------------------------
# Synthetische documenten
# --------------------------------------------------------------------------

def _el(eid, code, name, qty="10", unit="m2"):
    return {"element_id": eid, "element_code": {"normalized_value": code, "original_value": code},
            "element_name": {"value": name}, "location": {"value": None}, "material": {"normalized_value": None, "original_value": None},
            "quantity": {"value": qty}, "unit": {"normalized_value": unit, "original_value": unit}}


def _act(aid, eid, action, year, cost, unit="m2", qty="10", page=5):
    return {"action_id": aid, "element_id": eid, "action": {"normalized_value": action, "original_value": f"tekst {action}"},
            "planned_year": {"value": year}, "quantity": {"value": qty}, "unit": {"normalized_value": unit, "original_value": unit},
            "total_cost_as_stated": cost, "source_page": page}


def make_doc(doc_id="DOC-T1", price_date="1-3-2020", construction_year=1980, actions=None, elements=None):
    elements = elements if elements is not None else [_el("E1", "4621", "Buitenschilderwerk"), _el("E2", "4711", "Dakbedekking"),
                                                      _el("E3", "6612", "Lift", qty="1", unit="pcs")]
    actions = actions if actions is not None else [
        _act("A1", "E1", "exterior_painting", 2020, "1000"), _act("A2", "E1", "exterior_painting", 2026, "1000"),
        _act("A3", "E1", "exterior_painting", 2032, "1000"),
        _act("A4", "E2", "repair", 2022, "500")]
    return {"document_id": doc_id, "building": {"construction_year": {"value": construction_year}},
            "document_level_values": {"price_level_date": {"value": price_date},
                                      "vat_statement": {"value": "De bedragen in de begrotingen zijn inclusief BTW"}},
            "elements": elements, "maintenance_actions": actions}


def table_with(*decisions):
    t = LC.build_table([make_doc(), make_doc("DOC-T2", actions=[
        _act("B1", "E1", "exterior_painting", 2021, "900"), _act("B2", "E1", "exterior_painting", 2027, "900")])], T0)
    for code, action, decision, value in decisions:
        t = LC.decide(t, code, action, decision, by="tester", at=T0, value=value)
    return t


# --------------------------------------------------------------------------
# Levensduurtabel
# --------------------------------------------------------------------------

def test_lifecycle_observes_intervals_and_proposes_only_whole_median():
    t = table_with()
    e = LC.entry_for(t, "4621", "exterior_painting")
    assert e["observed"]["n_documents"] == 2 and e["observed"]["n_intervals"] == 3
    assert e["observed"]["proposed_cycle_years"] == 6 and e["cycle_years"] is None   # niet effectief zonder mens
    assert LC.effective_cycle(t, "4621", "exterior_painting") is None
    repair = LC.entry_for(t, "4711", "repair")
    assert repair["observed"]["n_single_occurrence"] == 1 and repair["observed"]["proposed_cycle_years"] is None
    assert repair["observed"]["max_observable_interval"] == 12


def test_lifecycle_half_median_is_not_rounded():
    doc = make_doc(actions=[_act("A1", "E1", "exterior_painting", 2020, "1"), _act("A2", "E1", "exterior_painting", 2026, "1"),
                            _act("A3", "E1", "exterior_painting", 2033, "1")])
    e = LC.entry_for(LC.build_table([doc], T0), "4621", "exterior_painting")
    assert e["observed"]["interval_median"] == "6.5" and e["observed"]["proposed_cycle_years"] is None


def test_lifecycle_skips_documents_without_codes_and_non_physical():
    third = make_doc("DOC-X", elements=[_el("E1", None, "x")], actions=[_act("A1", "E1", "repair", 2020, "1")])
    t = LC.build_table([third], T0)
    assert t["entries"] == [] and t["skipped"]["groups_without_element_code"] == 1 and t["source_documents"] == []


def test_lifecycle_decisions_accept_edit_reject_and_unobserved():
    t = table_with(("4621", "exterior_painting", "ACCEPT", None))
    assert LC.effective_cycle(t, "4621", "exterior_painting") == 6
    hv = LC.entry_for(t, "4621", "exterior_painting")["human_verification"]
    assert hv["decision"] == "ACCEPT" and hv["original_proposed_value"] == 6 and hv["by"] == "tester"
    t = LC.decide(t, "6612", "replace", "EDIT", by="tester", at=T0, value=25)   # nooit waargenomen
    assert LC.effective_cycle(t, "6612", "replace") == 25
    t = LC.decide(t, "4621", "exterior_painting", "REJECT", by="tester", at=T0)
    assert LC.effective_cycle(t, "4621", "exterior_painting") is None
    with pytest.raises(LC.LifecycleError):
        LC.decide(t, "4711", "repair", "ACCEPT", by="tester", at=T0)          # geen voorstel
    with pytest.raises(LC.LifecycleError):
        LC.decide(t, "9000", "replace", "ACCEPT", by="tester", at=T0)          # niet waargenomen
    with pytest.raises(LC.LifecycleError):
        LC.decide(t, "6612", "replace", "EDIT", by="tester", at=T0, value=0)


def test_lifecycle_rebuild_keeps_human_decisions():
    t = table_with(("6612", "replace", "EDIT", 30))
    rebuilt = LC.build_table([make_doc()], T0, previous=t)
    assert LC.effective_cycle(rebuilt, "6612", "replace") == 30


def test_lifecycle_tampered_cycle_is_invalid():
    t = table_with()
    t["entries"][0]["cycle_years"] = 5
    assert LC.table_errors(t)


def test_repository_lifecycle_table_is_valid_and_has_no_unreviewed_cycles():
    t = LC.load_table()
    assert all(e["cycle_years"] is None or e["human_verification"] for e in t["entries"])


# --------------------------------------------------------------------------
# Maintenance Line v2
# --------------------------------------------------------------------------

def v2_line(**kw):
    src = L2.origin_source("DOCUMENT", document_id="DOC-T1", document_planned_years=[2020, 2026])
    fields = dict(element_code_internal="4621", action_normalized="exterior_painting", unit_normalized="m2", quantity="10")
    fields.update(kw)
    return L2.new_line("M-L0001", "M", "E1", origin="FROM_EXISTING_MJOP", origin_source=src, **fields)


def test_v2_line_valid_and_v1_rules_still_apply():
    line = v2_line()
    assert L2.line_errors(line) == [] and line["planning_status"] == "NOT_PLANNED"
    bad = copy.deepcopy(line)
    bad["line_status"] = "READY"                                               # v1-invariant
    assert any("line_status" in e for e in L2.line_errors(bad))
    bad = copy.deepcopy(line)
    bad["financial"]["indexation"] = "cbs"                                    # financial blijft zonder indexatie
    assert L2.line_errors(bad)


def test_v2_origin_requires_matching_source():
    with pytest.raises(L2.LineError):
        L2.new_line("M-L1", "M", "E1", origin="FROM_EXISTING_MJOP", origin_source=None)
    with pytest.raises(L2.LineError):
        L2.new_line("M-L1", "M", "E1", origin="ADDED_FROM_LIFECYCLE",
                    origin_source=L2.origin_source("LIFECYCLE_TABLE", lifecycle_key=None))


def test_v2_upgrade_from_v1_keeps_amount():
    v1 = L1.set_manual_amount(L1.new_line("X-1", "M", "E1", unit_normalized="m2", quantity="2"), "10", "m2", "2026", "inclusive", "offerte")
    v2 = L2.upgrade_v1(v1)
    assert v2["line_version"] == L2.LINE_VERSION and v2["financial"] == v1["financial"] and v2["origin"] == "MANUAL"
    assert L2.cost_per_occurrence(v2) == (Decimal("20"), "DEFINITIVE_AMOUNT")


def test_v2_planning_proposal_and_human_decisions():
    basis = {"planner_version": "t", "horizon_start": 2027, "horizon_end": 2056, "cycle_years_used": 6,
             "cycle_source": "DOCUMENT_INTERVAL", "base_year": 2026, "base_year_source": "DOCUMENT_PLANNED_YEAR", "rolled_forward": True}
    line = L2.set_planner_proposal(v2_line(), 2032, basis, ["CYCLE_UNKNOWN"])
    assert line["planning_status"] == "PROPOSED" and line["planned_year"] is None
    assert L2.occurrence_years(line, 2027, 2056) == [2032, 2038, 2044, 2050, 2056]
    assert L2.occurrence_years(line, 2027, 2056, include_proposals=False) == []
    acc = L2.decide_planning(line, "ACCEPT", by="tester", at=T0)
    assert acc["planned_year"] == 2032 and acc["cycle_years"] == 6 and acc["planning_status"] == "HUMAN_ACCEPTED"
    assert L2.occurrence_years(acc, 2027, 2056, include_proposals=False)[0] == 2032
    edit = L2.decide_planning(line, "EDIT", by="tester", at=T0, year=2030, cycle_years=8, note="schouw")
    pv = edit["planning_verification"]
    assert (edit["planned_year"], edit["cycle_years"]) == (2030, 8)
    assert (pv["original_proposed_year"], pv["original_cycle_years"], pv["by"]) == (2032, 6, "tester")
    rej = L2.decide_planning(line, "REJECT", by="tester", at=T0)
    assert L2.occurrence_years(rej, 2027, 2056) == []
    with pytest.raises(L2.LineError):
        L2.set_planner_proposal(acc, 2040, basis)                             # menselijke beslissing blijft
    tampered = copy.deepcopy(acc)
    tampered["planned_year"] = 2040
    assert L2.line_errors(tampered)


def test_v2_user_edit_of_planning_field_drops_proposal():
    basis = {"planner_version": "t", "horizon_start": 2027, "horizon_end": 2056, "cycle_years_used": 6,
             "cycle_source": "LINE", "base_year": 2030, "base_year_source": "PLANNED_YEAR", "rolled_forward": False}
    line = L2.set_planner_proposal(v2_line(), 2030, basis)
    edited = L2.update_user_fields(line, planned_year=2031, cycle_years=7)
    assert edited["planning_status"] == "NOT_PLANNED" and edited["proposed_planned_year"] is None
    assert L2.occurrence_years(edited, 2027, 2045) == [2031, 2038, 2045]


def test_v2_price_update_accept_reject_and_integrity():
    pu = PI.price_update(source_document_id="DOC-T1", source_action_id="A1", source_total="1000", source_vat_statement=None,
                         base_year=2020, target_year=2027, index=INDEX)
    assert pu["indexation_factor"] == "1.250000" and pu["indexed_total"] == "1250.000000"
    line = L2.set_price_update(v2_line(), pu)
    assert L2.cost_per_occurrence(line) == (Decimal("1250.000000"), "PROPOSED_INDEXED_HISTORICAL")
    assert L2.cost_per_occurrence(line, include_proposals=False) == (None, "NO_AMOUNT")
    acc = L2.decide_price_update(line, "ACCEPT", by="tester", at=T0)
    assert L2.cost_per_occurrence(acc, include_proposals=False)[1] == "ACCEPTED_INDEXED_HISTORICAL"
    assert L2.cost_per_occurrence(L2.decide_price_update(line, "REJECT", by="tester", at=T0)) == (None, "NO_AMOUNT")
    tampered = copy.deepcopy(line)
    tampered["price_update"]["indexed_total"] = "9999"
    assert L2.line_errors(tampered)


def test_plan_accepts_v1_and_v2_lines():
    v1 = L1.new_line("M-X", "M", "E9")
    v2 = v2_line()
    plan = P.set_line_ids(P.set_horizon(P.new_plan("M", "BLD", at=T0), 2027, 2056, at=T0), ["M-X", "M-L0001"], at=T0)
    assert P.plan_errors(plan, [v1, v2]) == []
    bad = copy.deepcopy(v2)
    bad["planning_status"] = "PROPOSED"
    assert P.plan_errors(plan, [v1, bad])


# --------------------------------------------------------------------------
# Prijsindex
# --------------------------------------------------------------------------

def test_price_index_missing_data_is_never_guessed():
    kw = dict(source_document_id="D", source_action_id=None, source_vat_statement=None, target_year=2027)
    assert PI.price_update(source_total=None, base_year=2020, index=INDEX, **kw)["not_computed_reason"] == "SOURCE_AMOUNT_MISSING"
    assert PI.price_update(source_total="1", base_year=None, index=INDEX, **kw)["not_computed_reason"] == "PRICE_LEVEL_UNKNOWN"
    assert PI.price_update(source_total="1", base_year=2019, index=INDEX, **kw)["not_computed_reason"] == "INDEX_MISSING"
    assert PI.price_update(source_total="1", base_year=2020, index=EMPTY_INDEX, **kw)["indexed_total"] is None


def test_price_index_validation_and_repository_config():
    PI.validate_index(PI.load_index())
    with pytest.raises(PI.IndexError_):
        PI.validate_index({"index_version": "price_index_v1", "index_source": None, "series": {"2020": "100"}})
    with pytest.raises(PI.IndexError_):
        PI.validate_index({"index_version": "price_index_v1", "index_source": "x", "series": {"2020": 100}})


# --------------------------------------------------------------------------
# Import
# --------------------------------------------------------------------------

def test_import_keeps_document_years_as_provenance_not_as_planned_year():
    lines, s = I.import_document(make_doc(), mjop_id="M", target_price_year=2027, index=INDEX)
    paint = next(l for l in lines if l["action_normalized"] == "exterior_painting")
    assert paint["planned_year"] is None and paint["origin_source"]["document_planned_years"] == [2020, 2026, 2032]
    assert paint["origin_source"]["source_action_ids"] == ["A1", "A2", "A3"]
    assert "NOT_INSPECTED" in paint["planner_flags"] and paint["vat_basis"] == "inclusive"
    assert paint["price_update"]["indexed_total"] == "1250.000000" and paint["price_status"] == "NO_AMOUNT"
    assert s["lines"] == 2 and s["price_level_year"] == 2020


def test_import_third_party_and_conflicting_amounts():
    doc = make_doc(price_date=None, elements=[_el("E1", None, "Kozijnen")],
                   actions=[_act("A1", "E1", "repair", 2020, "100"), _act("A2", "E1", "repair", 2025, "150")])
    lines, s = I.import_document(doc, mjop_id="M", target_price_year=2027, index=INDEX)
    assert "ELEMENT_CODE_MISSING" in lines[0]["planner_flags"]
    assert lines[0]["price_update"]["not_computed_reason"] == "SOURCE_AMOUNTS_DIFFER" and s["amounts_differ"] == 1
    doc = make_doc(price_date=None)
    lines, _ = I.import_document(doc, mjop_id="M", target_price_year=2027, index=INDEX)
    assert all("PRICE_LEVEL_UNKNOWN" in l["planner_flags"] for l in lines)


def test_import_real_verified_documents_validate():
    for doc_id in ("DOC-001", "DOC-004", "DOC-010"):
        doc = json.load(open(os.path.join(PROJECT_ROOT, "data", "verified", f"{doc_id}.json"), encoding="utf-8"))
        lines, s = I.import_document(doc, mjop_id=f"M-{doc_id}", target_price_year=2027, index=EMPTY_INDEX)
        assert lines and all(L2.line_errors(l) == [] for l in lines)


# --------------------------------------------------------------------------
# Horizon-planner
# --------------------------------------------------------------------------

def _plan(doc=None, table=None, start=2027, **kw):
    doc = doc or make_doc()
    lines, _ = I.import_document(doc, mjop_id="M", target_price_year=start, index=INDEX)
    return H.run(doc, lines, table or table_with(), start_year=start, mjop_id="M", **kw)


def test_planner_uses_next_document_year_and_document_cycle():
    lines, r = _plan()
    paint = next(l for l in lines if l["action_normalized"] == "exterior_painting")
    assert paint["proposed_planned_year"] == 2032 and paint["planning_basis"]["cycle_source"] == "DOCUMENT_INTERVAL"
    assert paint["planning_basis"]["rolled_forward"] is False
    assert L2.occurrence_years(paint, 2027, 2056) == [2032, 2038, 2044, 2050, 2056]
    assert (r["horizon_start"], r["horizon_end"]) == (2027, 2056)


def test_planner_rolls_forward_and_flags_overdue():
    doc = make_doc(actions=[_act("A1", "E1", "exterior_painting", 2014, "1"), _act("A2", "E1", "exterior_painting", 2020, "1"),
                            _act("A3", "E2", "repair", 2022, "1")])
    lines, r = _plan(doc)
    paint = next(l for l in lines if l["action_normalized"] == "exterior_painting")
    assert paint["proposed_planned_year"] == 2032 and paint["planning_basis"]["rolled_forward"] is True
    repair = next(l for l in lines if l["action_normalized"] == "repair")
    assert repair["proposed_planned_year"] is None and repair["planning_status"] == "NOT_PLANNED"
    assert {"OVERDUE_NO_CYCLE", "CYCLE_UNKNOWN"} <= set(repair["planner_flags"])


def test_planner_uses_lifecycle_table_only_after_human_decision_and_flags_difference():
    doc = make_doc(actions=[_act("A3", "E2", "repair", 2022, "1")])
    lines, _ = _plan(doc, table_with(("4711", "repair", "EDIT", 10)))
    assert lines[0]["proposed_planned_year"] == 2032 and lines[0]["planning_basis"]["cycle_source"] == "LIFECYCLE_TABLE"
    lines, _ = _plan(make_doc(), table_with(("4621", "exterior_painting", "EDIT", 8)))
    paint = next(l for l in lines if l["action_normalized"] == "exterior_painting")
    assert paint["planning_basis"]["cycle_years_used"] == 6 and "CYCLE_DOCUMENT_TABLE_DIFFER" in paint["planner_flags"]


def test_planner_beyond_horizon():
    doc = make_doc(actions=[_act("A1", "E1", "exterior_painting", 2070, "1")])
    lines, _ = _plan(doc)
    assert lines[0]["proposed_planned_year"] is None and "BEYOND_HORIZON" in lines[0]["planner_flags"]


def test_planner_adds_long_cycle_replacements_with_explicit_assumption():
    lines, r = _plan(table=table_with(("4711", "replace", "EDIT", 25), ("6612", "replace", "EDIT", 25)))
    added = {l["element_code_internal"]: l for l in lines if l["origin"] == "ADDED_FROM_LIFECYCLE"}
    roof = added["4711"]
    assert roof["proposed_planned_year"] == 2030                              # 1980 + 2 x 25, doorgerold
    assert "ASSUMED_FROM_CONSTRUCTION_YEAR" in roof["planner_flags"]
    assert roof["planning_basis"]["base_year_source"] == "CONSTRUCTION_YEAR_ASSUMPTION"
    assert roof["origin_source"]["lifecycle_key"] == {"element_code": "4711", "action": "replace"}
    assert r["lines_added_from_lifecycle"] == 2
    assert {u["element_code"] for u in r["lifecycle_unknown"]} == {"4621"}   # geen vastgestelde vervangingscyclus


def test_planner_last_replacement_year_overrides_construction_year():
    lines, _ = _plan(table=table_with(("4711", "replace", "EDIT", 25)), last_replacement_years={"4711": 2015})
    roof = next(l for l in lines if l["element_code_internal"] == "4711" and l["origin"] == "ADDED_FROM_LIFECYCLE")
    assert roof["proposed_planned_year"] == 2040 and roof["last_replacement_year"] == 2015
    assert "ASSUMED_FROM_CONSTRUCTION_YEAR" not in roof["planner_flags"]


def test_planner_does_not_add_when_replacement_already_planned():
    doc = make_doc(actions=[_act("A1", "E2", "replace", 2035, "1")])
    lines, r = _plan(doc, table_with(("4711", "replace", "EDIT", 25)))
    assert not [l for l in lines if l["origin"] == "ADDED_FROM_LIFECYCLE" and l["element_code_internal"] == "4711"]


def test_planner_does_not_override_human_decision():
    lines, _ = _plan()
    decided = [L2.decide_planning(l, "EDIT", by="t", at=T0, year=2040, cycle_years=9) if l["planning_status"] == "PROPOSED" else l
               for l in lines if l["origin"] == "FROM_EXISTING_MJOP"]
    again, _ = H.run(make_doc(), decided, table_with(), start_year=2027, mjop_id="M")
    paint = next(l for l in again if l["action_normalized"] == "exterior_painting")
    assert (paint["planned_year"], paint["cycle_years"]) == (2040, 9)


# --------------------------------------------------------------------------
# Reservefonds
# --------------------------------------------------------------------------

def _fund_line(year, cycle, amount, accepted=True):
    pu = PI.price_update(source_document_id="D", source_action_id=None, source_total=amount, source_vat_statement=None,
                         base_year=2020, target_year=2020, index={"index_version": "price_index_v1", "index_source": "T",
                                                                  "series": {"2020": "1"}})
    line = L2.set_price_update(L2.update_user_fields(v2_line(), planned_year=year, cycle_years=cycle), pu)
    return L2.decide_price_update(line, "ACCEPT", by="t", at=T0) if accepted else line


def test_reserve_fund_yearly_balance_by_hand():
    lines = [_fund_line(2028, None, "3000")]
    f = RF.run(lines, start=2027, end=2029, price_level_year=2027, opening_balance="1000", annual_contribution="1000",
               include_proposals=False)
    assert [y["closing"] for y in f["years"]] == ["2000.00", "0.00", "1000.00"]
    assert f["shortfall_years"] == [] and f["advice"]["level_contribution"] == "1000.00"
    assert f["status"] == "ACCEPTED_ONLY"


def test_reserve_fund_inflation_interest_growth_and_shortfall():
    lines = [_fund_line(2028, None, "3000")]
    f = RF.run(lines, start=2027, end=2028, price_level_year=2027, opening_balance="0", annual_contribution="1000",
               contribution_growth="0.10", interest_rate="0.05", cost_inflation="0.02", include_proposals=False)
    y = f["years"]
    assert y[1]["expenses"] == "3060.00" and y[1]["contribution"] == "1100.00" and y[1]["interest"] == "50.00"
    assert y[1]["closing"] == "-910.00" and f["shortfall_years"] == [2028]


def test_reserve_fund_minimum_contribution_is_tight():
    lines = [_fund_line(2029, 3, "10000"), _fund_line(2028, None, "2500")]
    kw = dict(start=2027, end=2040, price_level_year=2027, opening_balance="1234.56", interest_rate="0.013",
              cost_inflation="0.021", include_proposals=False)
    f = RF.run(lines, annual_contribution="0", contribution_growth="0.03", **kw)
    for key, growth in (("level_contribution", "0"), ("indexed_contribution_first_year", "0.03")):
        c = Decimal(f["advice"][key])
        ok = RF.run(lines, annual_contribution=str(c), contribution_growth=growth, **kw)
        low = RF.run(lines, annual_contribution=str(c - Decimal("0.01")), contribution_growth=growth, **kw)
        assert ok["shortfall_years"] == [] and low["shortfall_years"] != []


def test_reserve_fund_concept_vs_accepted_and_warnings():
    lines = [_fund_line(2028, None, "100", accepted=False)]
    concept = RF.run(lines, start=2027, end=2030, price_level_year=2027, opening_balance="0", annual_contribution="0")
    assert concept["status"] == "CONCEPT" and concept["total_expenses"] == "100.00"
    assert any("CONCEPT" in w for w in concept["warnings"]) and any("één keer" in w for w in concept["warnings"])
    accepted = RF.run(lines, start=2027, end=2030, price_level_year=2027, opening_balance="0", annual_contribution="0",
                      include_proposals=False)
    assert accepted["total_expenses"] == "0.00" and accepted["details"]["lines_without_amount"]
    with pytest.raises(RF.FundError):
        RF.run(lines, start=2027, end=2030, price_level_year=2027, opening_balance=None, annual_contribution="0")


# --------------------------------------------------------------------------
# End-to-end
# --------------------------------------------------------------------------

def _result(index=INDEX, doc=None, **kw):
    params = {"opening_balance": "5000", "annual_contribution": "500", "contribution_growth": "0", "interest_rate": "0",
              "cost_inflation": "0", "min_balance": "0", "rebuild_value": "1000000"}
    return A.build(doc or make_doc(), mjop_id="M", building_id="BLD", start_year=2027, target_price_year=2027, index=index,
                   table=table_with(("4711", "replace", "EDIT", 25)), fund_params=params, at=T0, **kw)


def _xml(result):
    return X.serialize(result["dataset"], result["fmt"])


def test_export_format_columns_and_schema_block_from_real_export():
    fmt = X.load_format()
    assert {t: len(c) for t, c in fmt["columns"].items()} == {"opo": 133, "ope": 64, "opu": 22, "oph": 76, "ops": 33, "opm": 18}
    assert fmt["children"]["opo"] == ["ope"] and "oph" in fmt["children"]["ope"]
    assert X.bitpattern(2031, 12, fmt)[31] == "1" and X.bitpattern(2031, 12, fmt)[43] == "1"
    assert X.bitpattern(2031, 12, fmt).count("1") == 15 and len(X.bitpattern(0, 0, fmt)) == 200
    assert X.bitpattern(2030, 0, fmt).count("1") == 1
    with pytest.raises(X.ExportError):
        X.bitpattern(1999, 5, fmt)


def test_export_xml_is_valid_crlf_and_contains_schema_verbatim():
    result = _result()
    text = _xml(result)
    assert X.validate_xml(text, result["fmt"]) == []
    assert text.startswith("<NewDataSet>\r\n  <xs:schema id=\"NewDataSet\"") and text.endswith("</NewDataSet>")
    assert "\n" not in text.replace("\r\n", "")
    assert result["fmt"]["schema_text"].replace("\n", "\r\n") in text


def test_export_mapping_of_actions_years_and_amounts():
    result = _result()
    obj, opes = result["dataset"]
    assert obj["obj_prijspeil"] == "2027-01-01T00:00:00+01:00" and obj["obj_btw"] == "true" and obj["obj_bouwjaar"] == "1980"
    assert result["export_report"]["price_mode"] == "indexed"
    hans = [h for _, hs in opes for h in hs]
    assert all(h["han_type"] == "H" for h in hans)                                    # geen bevindingen
    paint = next(h for h in hans if h["han_tekst"] == "tekst exterior_painting")
    assert (paint["han_startjaar"], paint["han_cyclus"]) == ("2032", "6")
    assert paint["han_hvhreken"] == "10" and paint["han_prijs"] == "125" and paint["han_totaal"] == "1250"
    assert "VOORSTEL" in paint["han_opm"] and "DOC-T1" in paint["han_opm"] and "indexfactor 1.250000" in paint["han_opm"]
    ele = next(e for e, hs in opes if paint in hs)
    assert ele["ele_nlsfb"] == "4621" and ele["ele_nlsfbhoofd"] == "46" and ele["ele_eenheid"] == "m2"
    added = next(h for h in hans if h["han_tekst"] == "Vervangen")
    assert "TOEGEVOEGD" in added["han_opm"] and "AANNAME bouwjaar" in added["han_opm"] and added["han_prijs"] == "0"


def test_export_without_year_writes_zero_and_empty_pattern():
    doc = make_doc(actions=[_act("A1", "E2", "repair", 2020, "500")])                 # verstreken, geen cyclus
    result = _result(doc=doc)
    han = result["dataset"][1][0][1][0]
    assert han["han_startjaar"] == "0" and han["han_cyclus"] == "0" and "1" not in han["han_bitpatroon"]
    assert "GEEN PLANJAAR" in han["han_opm"] and result["export_report"]["actions_without_year"] == 1


def test_export_price_modes_without_index():
    result = _result(index=EMPTY_INDEX)
    assert result["export_report"]["price_mode"] == "historical"
    assert result["dataset"][0]["obj_prijspeil"] == "2020-01-01T00:00:00+01:00"
    paint = next(h for _, hs in result["dataset"][1] for h in hs if h["han_tekst"] == "tekst exterior_painting")
    assert paint["han_totaal"] == "1000" and "niet geïndexeerd" in paint["han_opm"]
    assert result["reserve_fund"]["parameters"]["price_level_year"] == 2020
    unknown = _result(index=EMPTY_INDEX, doc=make_doc(price_date=None))
    assert unknown["export_report"]["price_mode"] == "historical_unknown_level"
    assert unknown["dataset"][0]["obj_prijspeil"] == "1900-01-01T00:00:00+01:00"
    hans = [h for _, hs in unknown["dataset"][1] for h in hs]
    assert all(h["han_prijs"] == "0" for h in hans) and any("prijspeil onbekend" in h["han_opm"] for h in hans)


def test_export_unit_price_rounding_and_fraction_of_element():
    doc = make_doc(elements=[_el("E1", "4621", "Kozijnen", qty="9", unit="m2")],
                   actions=[_act("A1", "E1", "repair", 2030, "100", qty="3")])
    result = _result(doc=doc)
    ele, hans = result["dataset"][1][0]
    h = hans[0]
    assert h["han_prijs"] == "41.67" and h["han_totaal"] == "125.01" and h["han_hvh"] == "0.333333"
    assert ele["ele_hvh"] == "9"
    assert Decimal(result["export_report"]["rounding_deviation_total"]) == Decimal("0.01")


def test_validator_detects_broken_files():
    result = _result()
    fmt, text = result["fmt"], _xml(result)
    pattern = result["dataset"][1][0][1][0]["han_bitpatroon"]
    assert X.validate_xml(text.replace(pattern, "-" * 200, 1), fmt)
    assert X.validate_xml(text.replace("<han_totaal>1250</han_totaal>", "<han_totaal>1</han_totaal>", 1), fmt)
    assert X.validate_xml(text.replace("<han_nhg />", "", 1), fmt)
    assert X.validate_xml("<x/>", fmt) and X.validate_xml("geen xml", fmt)


def test_real_oprognose_export_passes_validator_if_available():
    path = os.environ.get("OPROGNOSE_SAMPLE_XML")
    if not path or not os.path.exists(path):
        pytest.skip("geen echte OPrognose-export opgegeven (OPROGNOSE_SAMPLE_XML); bevat klantgegevens, niet in de repo")
    assert X.validate_xml(open(path, encoding="utf-8").read(), X.load_format()) == []


def test_end_to_end_outputs(tmp_path):
    result = _result()
    meta = {"tool_version": A.TOOL_VERSION, "at": T0, "document_id": "DOC-T1", "target_price_year": 2027,
            "index_source": "TEST", "fund_params": {}, "last_replacement_years": {}}
    xml_path = A.write_outputs(result, meta, str(tmp_path / "M"))
    names = {p.name for p in (tmp_path / "M").iterdir()}
    assert {"M.xml", "plan.json", "lines.json", "reserve_fund.json", "oprognose_export_report.json", "rapport.md"} <= names
    assert "review.xlsx" not in names
    with open(xml_path, encoding="utf-8", newline="") as f:
        assert X.validate_xml(f.read(), result["fmt"]) == []
    report = (tmp_path / "M" / "rapport.md").read_text(encoding="utf-8")
    assert "M.xml" in report and "Niet geïnspecteerd" in report
    fund = result["reserve_fund"]
    assert fund["status"] == "CONCEPT" and fund["advice"]["comparison_half_percent_rebuild_value"] == "5000.00"


def test_cli_run_on_real_verified_document(tmp_path):
    assert A.main(["run", "--document", "DOC-010", "--building-id", "BLD", "--start-year", "2027",
                   "--opening-balance", "1000", "--annual-contribution", "100", "--out-dir", str(tmp_path)]) == 0
    out = tmp_path / "MJOP-DOC-010-ACT2027"
    with open(out / "MJOP-DOC-010-ACT2027.xml", encoding="utf-8", newline="") as f:
        assert X.validate_xml(f.read(), X.load_format()) == []
